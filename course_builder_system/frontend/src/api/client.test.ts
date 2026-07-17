import { afterEach, describe, expect, it, vi } from "vitest";
import {
  approveStage,
  createCourse,
  getBriefQuestions,
  getWorkspace,
  normalizeStatus,
  previewStageImpact,
  reopenStage,
  reviseStage,
  reviewContentAsset,
  runStage,
  saveBriefAnswers,
  saveBriefUpdates,
  saveSourceDecision,
} from "./client";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function requestBody(fetchMock: ReturnType<typeof vi.fn>, index = -1): Record<string, unknown> {
  const call = index === -1 ? fetchMock.mock.calls.at(-1) : fetchMock.mock.calls[index];
  const init = call?.[1] as RequestInit;
  return JSON.parse(String(init.body)) as Record<string, unknown>;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("typed API commands", () => {
  it("normalizes every lifecycle state exhaustively", () => {
    const states = [
      "locked",
      "needs_input",
      "ready",
      "running",
      "awaiting_review",
      "requires_attention",
      "approved",
      "stale",
      "failed",
    ] as const;

    expect(states.map((state) => normalizeStatus(state))).toEqual(states);
    expect(normalizeStatus("unknown-state")).toBe("ready");
  });

  it("normalizes needs_input and backend-projected actions without inventing controls", async () => {
    const fetchMock = vi.fn((path: string) => {
      if (path.endsWith("/workspace")) {
        return Promise.resolve(jsonResponse({
          course_id: "herb-course",
          title: "Indoor herbs",
          current_stage: "brief",
          operator_status: "needs_input",
          stages: [
            {
              slug: "brief",
              label: "Brief",
              state: "needs_input",
              checksum: "brief-checksum",
              dependencies: ["subject_request"],
              downstream_stages: ["outcomes", "research"],
              prerequisites_ready: true,
              actions: [{ id: "edit", label: "Provide required input", enabled: true, requires_impact_confirmation: false }],
            },
            {
              slug: "outcomes",
              label: "Outcomes",
              state: "locked",
              prerequisites_ready: false,
              actions: [{ id: "go_to_blocker", label: "Go to Brief", enabled: true, target_stage: "brief", requires_impact_confirmation: false }],
            },
          ],
        }));
      }
      if (path.endsWith("/stages/brief")) {
        return Promise.resolve(jsonResponse({
          slug: "brief",
          artifacts: [{
            artifact_type: "brief",
            checksum: "brief-artifact-checksum",
            body: {
              course_title: "Indoor herbs",
              subject: "Indoor herb gardening",
              audience: "General adult learners",
              prior_knowledge: "No prior knowledge assumed.",
              purpose: "Grow herbs indoors.",
              level: "beginner",
              duration: "3 hours",
              modality: "self_paced",
              language: "English",
              assessment_expectations: null,
              assumptions: [{ field: "language", value: "English", rationale: "Safe default." }],
              provenance: [{ field: "audience", source: "user", confidence: "explicit" }],
              intake_state: {
                explicit_fields: ["audience"],
                accepted_default_fields: [],
                unresolved_required_fields: ["language_default_acceptance"],
                answered_question_ids: ["brief_audience"],
                last_gap_analysis: [],
              },
            },
          }],
        }));
      }
      return Promise.resolve(jsonResponse({ slug: path.split("/").at(-1), artifacts: [] }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getWorkspace("herb-course");
    expect(result.workspace.stages[0]).toMatchObject({
      slug: "brief",
      status: "needs_input",
      dependencies: ["subject_request"],
      downstreamStages: ["outcomes", "research"],
      actions: [{ id: "edit", label: "Provide required input", enabled: true }],
    });
    expect(result.workspace.stages[1]?.actions).toEqual([expect.objectContaining({
      id: "go_to_blocker",
      targetStage: "brief",
    })]);
    expect(result.workspace.brief.intakeState).toEqual({
      explicitFields: ["audience"],
      acceptedDefaultFields: [],
      unresolvedRequiredFields: ["language_default_acceptance"],
      answeredQuestionIds: ["brief_audience"],
      lastGapAnalysis: [],
    });
    expect(result.workspace.brief.provenance).toEqual([
      { field: "audience", source: "user", confidence: "explicit" },
    ]);
    expect(result.workspace.brief.assessmentExpectations).toBeNull();
    expect(result.workspace.briefChecksum).toBe("brief-artifact-checksum");
  });

  it("normalizes the complete backend-owned Brief question contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      questions: [
        {
          id: "brief_modality",
          field: "modality",
          prompt: "How will the course be delivered?",
          rationale: "Delivery mode controls later asset and lesson choices.",
          answer_type: "single_choice",
          options: ["self_paced", "live", "blended"],
          default: "self_paced",
          required: true,
          allow_skip: false,
          visibility: { resolved: true },
        },
        {
          id: "brief_live_teaching_constraints",
          field: "live_teaching_constraints",
          prompt: "What live-teaching constraints apply?",
          rationale: "The Lesson Plan must fit the teaching environment.",
          answer_type: "free_text",
          options: [],
          default: null,
          required: false,
          allow_skip: true,
          visibility: { modality: ["live", "blended"] },
        },
      ],
      round_kind: "clarification",
      gap_analysis: [{ id: "gap-live", kind: "missing", field: "live_teaching_constraints", severity: "medium", message: "Blended delivery needs a live constraint." }],
      intake_state: {
        explicit_fields: ["modality"],
        accepted_default_fields: ["language"],
        unresolved_required_fields: ["live_teaching_constraints"],
        answered_question_ids: ["brief_modality", "brief_language"],
        last_gap_analysis: [{ id: "gap-live", kind: "missing", field: "live_teaching_constraints", severity: "medium", message: "Blended delivery needs a live constraint." }],
      },
      checksum: "brief-checksum",
    }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getBriefQuestions("herb-course")).resolves.toEqual({
      questions: [
        expect.objectContaining({
          id: "brief_modality",
          answerType: "single_choice",
          options: ["self_paced", "live", "blended"],
          defaultValue: "self_paced",
          required: true,
          allowSkip: false,
          visibility: { resolved: true },
        }),
        expect.objectContaining({
          id: "brief_live_teaching_constraints",
          defaultValue: undefined,
          required: false,
          allowSkip: true,
          visibility: { modality: ["live", "blended"] },
        }),
      ],
      roundKind: "clarification",
      gapAnalysis: [expect.objectContaining({ id: "gap-live", severity: "medium" })],
      intakeState: {
        explicitFields: ["modality"],
        acceptedDefaultFields: ["language"],
        unresolvedRequiredFields: ["live_teaching_constraints"],
        answeredQuestionIds: ["brief_modality", "brief_language"],
        lastGapAnalysis: [expect.objectContaining({ id: "gap-live" })],
      },
      checksum: "brief-checksum",
    });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/courses/herb-course/brief/questions");
  });

  it("maps sparse course creation to one atomic backend request", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ course_id: "herb-course", workspace: { course_id: "herb-course" } }, 201));
    vi.stubGlobal("fetch", fetchMock);

    const created = await createCourse({
      courseId: "herb-course",
      subject: "Indoor herb gardening",
      description: "For apartment renters",
      constraints: "No outdoor beds\nKeep it compact",
      sourceUrls: ["https://example.test/herbs"],
    });

    expect(created).toEqual({ courseId: "herb-course" });
    expect(requestBody(fetchMock, 0)).toEqual({
      course_id: "herb-course",
      subject: "Indoor herb gardening",
      description: "For apartment renters",
      constraints: ["No outdoor beds", "Keep it compact"],
      known_source_locators: ["https://example.test/herbs"],
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("serializes typed Brief answers, default acceptance, and optional skip", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ checksum: "brief-next" }));
    vi.stubGlobal("fetch", fetchMock);

    await saveBriefAnswers("herb-course", [
      { questionId: "brief_audience", value: "Apartment renters" },
      { questionId: "brief_language", acceptDefault: true },
      { questionId: "brief_tools_or_equipment", skip: true },
    ], "brief-before");

    expect(requestBody(fetchMock)).toEqual({
      answers: [
        { question_id: "brief_audience", value: "Apartment renters" },
        { question_id: "brief_language", accept_default: true },
        { question_id: "brief_tools_or_equipment", skip: true },
      ],
      expected_checksum: "brief-before",
    });
  });

  it("sends only changed direct Brief fields through the PATCH contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ checksum: "brief-next" }));
    vi.stubGlobal("fetch", fetchMock);

    await saveBriefUpdates("herb-course", {
      audience: "Apartment renters",
      mustHaveTopics: ["Watering", "Lighting"],
      assessmentExpectations: "",
    }, "brief-before");

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/courses/herb-course/brief");
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBe("PATCH");
    expect(requestBody(fetchMock)).toEqual({
      updates: {
        audience: "Apartment renters",
        must_have_topics: ["Watering", "Lighting"],
        assessment_expectations: "",
      },
      expected_checksum: "brief-before",
    });
  });

  it("surfaces an atomic course creation connection failure", async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError("connection lost"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(createCourse({ subject: "Resilient course" })).rejects.toMatchObject({
      status: 0,
      message: "connection lost",
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("uses checksums and typed targets for runnable stage commands", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({ job: { job_id: "job-run", status: "queued" } }, 202),
      )
      .mockResolvedValueOnce(jsonResponse({ stage: { state: "approved" } }))
      .mockResolvedValueOnce(
        jsonResponse({ job: { job_id: "job-change", status: "queued" } }, 202),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      runStage("herb-course", "brief", { expectedChecksum: "checksum-1" }),
    ).resolves.toEqual({
      job: { job_id: "job-run", status: "queued" },
      events_url: "/api/jobs/job-run/events",
    });
    expect(requestBody(fetchMock)).toEqual({
      expected_checksum: "checksum-1",
      mode: "deterministic",
    });

    await approveStage("herb-course", "brief", { expectedChecksum: "checksum-2" });
    expect(requestBody(fetchMock)).toEqual({ expected_checksum: "checksum-2" });

    await expect(
      reviseStage("herb-course", "content", {
        expectedChecksum: "checksum-3",
        targetType: "asset",
        targetIds: ["m1_s1_cc"],
        category: "clarity",
        instruction: "Clarify the opening example.",
        mode: "deterministic",
        impactChecksum: "impact-checksum",
      }),
    ).resolves.toEqual({
      job: { job_id: "job-change", status: "queued" },
      events_url: "/api/jobs/job-change/events",
    });
    expect(requestBody(fetchMock)).toEqual({
      expected_checksum: "checksum-3",
      target_type: "asset",
      target_ids: ["m1_s1_cc"],
      category: "clarity",
      instruction: "Clarify the opening example.",
      mode: "deterministic",
      impact_acknowledged: true,
      expected_impact_checksum: "impact-checksum",
    });
    expect(fetchMock.mock.calls.at(-1)?.[0]).toBe("/api/courses/herb-course/stages/content/revisions");
  });

  it("normalizes a typed impact preview and sends its checksum when reopening", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        action: "reopen",
        stage: "course-model",
        operation_summary: "Reopen Course Model",
        direct_artifacts: ["course_model"],
        stale_artifacts: ["blueprint", "content_package"],
        targeted_assets: ["m1_s1_cc"],
        preserved_assets: ["m1_s2_cc"],
        requires_rerun_stages: ["blueprint", "content"],
        warnings: ["Stale artifact bodies remain inspectable."],
        impact_level: "downstream",
        impact_checksum: "impact-checksum",
      }))
      .mockResolvedValueOnce(jsonResponse({ stage: { state: "awaiting_review" } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(previewStageImpact("herb-course", "course-model", "stage-checksum", {
      action: "reopen",
      operationSummary: "Adjust structure",
    })).resolves.toMatchObject({
      stage: "course-model",
      staleArtifacts: ["blueprint", "content_package"],
      requiresRerunStages: ["blueprint", "content"],
      impactChecksum: "impact-checksum",
    });
    expect(requestBody(fetchMock)).toEqual({
      action: "reopen",
      expected_checksum: "stage-checksum",
      operation_summary: "Adjust structure",
      target_ids: [],
    });

    await reopenStage("herb-course", "course-model", {
      expectedChecksum: "stage-checksum",
      impactChecksum: "impact-checksum",
      reason: "Fix the sequence",
    });
    expect(requestBody(fetchMock)).toEqual({
      expected_checksum: "stage-checksum",
      reason: "Fix the sequence",
      impact_acknowledged: true,
      expected_impact_checksum: "impact-checksum",
    });
  });

  it("maps a durable content review decision to the canonical command", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ artifact: { artifact_type: "content_review" }, checksum: "next" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await reviewContentAsset(
      "herb-course",
      "m1-s1-summary",
      "changes_requested",
      "checksum-4",
      "Remove the unsupported claim",
    );

    expect(requestBody(fetchMock)).toEqual({
      decision: "changes_requested",
      expected_checksum: "checksum-4",
      feedback: "Remove the unsupported claim",
    });
  });

  it("persists an explicit source selection with stage concurrency control", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ artifact: { artifact_type: "approved_source_registry" }, checksum: "next" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await saveSourceDecision("herb-course", ["source-1", "source-3"], "checksum-5");

    expect(requestBody(fetchMock)).toEqual({
      selected_ids: ["source-1", "source-3"],
      expected_checksum: "checksum-5",
    });
  });
});
