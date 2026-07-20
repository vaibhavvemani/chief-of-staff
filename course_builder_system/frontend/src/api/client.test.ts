import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  addKnownSource,
  approveStage,
  confirmSourceRepairRoute,
  createCourse,
  courseModelValidationIssues,
  decideSourceRepair,
  getBriefQuestions,
  getWorkspace,
  normalizeStatus,
  outcomeValidationIssues,
  previewCourseModelDecision,
  previewStageImpact,
  reopenStage,
  requestContentRepair,
  requestSourceRepair,
  reviseStage,
  reviewContentAsset,
  runStage,
  runBriefClarifications,
  saveBriefAnswers,
  saveBriefUpdates,
  saveBlueprintDecision,
  saveCourseModelDecision,
  saveLessonPlanDecision,
  saveOutcomeDecision,
  saveSourceDecision,
  versionConflictChecksum,
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
  it("sends only typed Course Model operations through preview and acknowledged save", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({
        candidate_artifact: { body: { course_metadata: { course_outcome_ids: ["co1"] }, modules: [], structural_rationale: [], source_registry: [] } },
        allocated_ids: { new_coverage_ui: "cr3" },
        change_records: [{ operation_index: 0, op: "update_subtopic", action: "updated", record_type: "subtopic", record_id: "s1" }],
        affected_records: { subtopic: { changed_ids: ["s1"], removed_ids: [] } },
        impact: { direct_artifacts: ["course_model"], stale_artifacts: ["blueprint"], requires_rerun_stages: ["blueprint"], warnings: [], impact_level: "downstream", impact_checksum: "impact-1" },
      }))
      .mockResolvedValueOnce(jsonResponse({
        artifact: { body: { course_metadata: { course_outcome_ids: ["co1"] }, modules: [], structural_rationale: [], source_registry: [] } },
        checksum: "course-model-2",
        allocated_ids: { new_coverage_ui: "cr3" },
        impact: { direct_artifacts: ["course_model"], stale_artifacts: ["blueprint"], requires_rerun_stages: ["blueprint"], warnings: [], impact_level: "downstream", impact_checksum: "impact-1" },
      }));
    vi.stubGlobal("fetch", fetchMock);
    const operations = [
      { op: "update_subtopic" as const, targetId: "s1", title: "Renamed" },
      { op: "add_coverage" as const, clientRef: "new_coverage_ui", parentId: "s1", position: 2, statement: "Cover the new requirement.", conceptIds: ["c1"] },
      { op: "reorder_subtopics" as const, parentId: "m1", subtopicIds: ["s2", "s1"] },
    ];

    const preview = await previewCourseModelDecision("herb-course", operations, "course-model-1");
    expect(requestBody(fetchMock, 0)).toEqual({
      expected_checksum: "course-model-1",
      operations: [
        { op: "update_subtopic", target_id: "s1", title: "Renamed" },
        { op: "add_coverage", client_ref: "new_coverage_ui", parent_id: "s1", position: 2, statement: "Cover the new requirement.", concept_ids: ["c1"] },
        { op: "reorder_subtopics", parent_id: "m1", subtopic_ids: ["s2", "s1"] },
      ],
    });
    expect(preview.allocatedIds).toEqual({ new_coverage_ui: "cr3" });
    expect(preview.changeRecords).toEqual([{
      operationIndex: 0,
      op: "update_subtopic",
      action: "updated",
      recordType: "subtopic",
      recordId: "s1",
      recordIds: [],
      parentId: undefined,
    }]);
    expect(preview.impact.impactChecksum).toBe("impact-1");

    await saveCourseModelDecision("herb-course", operations, "course-model-1", "impact-1");
    expect(requestBody(fetchMock, 1)).toMatchObject({
      expected_checksum: "course-model-1",
      impact_acknowledged: true,
      expected_impact_checksum: "impact-1",
    });
    expect(requestBody(fetchMock, 1)).not.toHaveProperty("body");
  });

  it("normalizes structured Course Model validation issues", () => {
    const error = new ApiError("invalid", 400, { error: { issues: [{ code: "unknown_reference", message: "Unknown concept.", operation_index: 2, record_type: "coverage", record_id: "cr1", field: "concept_ids", path: "$.operations[2]" }] } });
    expect(courseModelValidationIssues(error)).toEqual([{
      code: "unknown_reference",
      message: "Unknown concept.",
      operationIndex: 2,
      recordType: "coverage",
      recordId: "cr1",
      field: "concept_ids",
      path: "$.operations[2]",
    }]);
  });

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

  it("requests live Brief clarifications without changing mode implicitly", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      questions: [],
      round_kind: "complete",
      gap_analysis: [],
      intake_state: {
        explicit_fields: [],
        accepted_default_fields: [],
        unresolved_required_fields: [],
        answered_question_ids: [],
        last_gap_analysis: [],
      },
      checksum: "brief-live",
    }));
    vi.stubGlobal("fetch", fetchMock);

    await runBriefClarifications("herb-course", "live", "brief-before");

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/courses/herb-course/brief/clarifications/run",
    );
    expect(requestBody(fetchMock)).toEqual({
      mode: "live",
      expected_checksum: "brief-before",
    });
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
      mode: "deterministic",
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

  it("serializes Blueprint defaults, explicit exceptions, and anchor waivers", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      artifact: {
        body: {
          course_defaults: {
            default_asset_types: ["course_content", "summary"],
            depth_budget: {
              level: "standard",
              target_learning_minutes: 20,
              target_word_range: { minimum: 600, target: 800, maximum: 1000 },
              required_example_count: 2,
              case_depth: "brief",
              assessment_complexity: "application",
            },
          },
          subtopic_plans: [{
            subtopic_id: "s1",
            anchor_asset_waiver_confirmed: true,
            depth_budget: {
              level: "deep",
              target_learning_minutes: 35,
              target_word_range: { minimum: 900, target: 1200, maximum: 1500 },
              required_example_count: 3,
              case_depth: "detailed",
              assessment_complexity: "analysis",
            },
            asset_plan: [{
              id: "s1-summary",
              asset_type: "summary",
              title: "Troubleshooting summary",
              selection_status: "selected",
              source_ids: ["source-1"],
            }],
          }],
        },
      },
      checksum: "blueprint-next",
    }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await saveBlueprintDecision("herb-course", {
      defaultAssetTypes: ["course_content", "summary"],
      defaultDepth: {
        depth: "standard",
        minutes: 20,
        wordMinimum: 600,
        wordTarget: 800,
        wordMaximum: 1000,
        examples: 2,
        caseDepth: "brief",
        assessmentComplexity: "application",
      },
      selectedAssetTypes: { s1: ["summary"] },
      depthOverrides: {
        s1: {
          depth: "deep",
          minutes: 35,
          wordMinimum: 900,
          wordTarget: 1200,
          wordMaximum: 1500,
          examples: 3,
          caseDepth: "detailed",
          assessmentComplexity: "analysis",
        },
      },
      anchorWaivers: ["s1"],
      rationale: "The troubleshooting topic needs a deeper applied treatment.",
    }, "blueprint-before");

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/courses/herb-course/blueprint/decision");
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBe("PUT");
    expect(requestBody(fetchMock)).toEqual({
      expected_checksum: "blueprint-before",
      default_asset_types: ["course_content", "summary"],
      default_depth: {
        level: "standard",
        target_learning_minutes: 20,
        target_word_range: { minimum: 600, target: 800, maximum: 1000 },
        required_example_count: 2,
        case_depth: "brief",
        assessment_complexity: "application",
      },
      selected_asset_types: { s1: ["summary"] },
      depth_overrides: {
        s1: {
          level: "deep",
          target_learning_minutes: 35,
          target_word_range: { minimum: 900, target: 1200, maximum: 1500 },
          required_example_count: 3,
          case_depth: "detailed",
          assessment_complexity: "analysis",
        },
      },
      anchor_waivers: ["s1"],
      rationale: "The troubleshooting topic needs a deeper applied treatment.",
    });
    expect(result).toMatchObject({
      checksum: "blueprint-next",
      blueprint: {
        defaults: {
          assetTypes: ["course_content", "summary"],
          wordMinimum: 600,
          wordTarget: 800,
          wordMaximum: 1000,
        },
        plans: [{
          subtopicId: "s1",
          anchorWaiverConfirmed: true,
          exception: true,
          assets: [{ assetType: "summary", sourceIds: ["source-1"] }],
        }],
      },
    });
  });

  it("serializes typed Lesson Plan constraints and operations", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      artifact: {
        body: {
          session_constraints: {
            max_session_hours: 0.5,
            default_mode: "live",
            calendar_dates: ["2026-08-03"],
            instructor_count: 1,
            delivery_platform: "Studio classroom",
          },
          unresolved_session_constraints: [],
          coverage_summary: {
            expected_subtopic_ids: ["s1", "s2"],
            covered_subtopic_ids: ["s1", "s2"],
            total_duration_minutes: 40,
          },
          sessions: [{
            id: "sess1",
            order: 1,
            title: "Foundations",
            duration_minutes: 40,
            covers: [
              { subtopic_id: "s1", mode: "live", talking_points: ["Teach first."] },
              { subtopic_id: "s2", mode: "self_study", talking_points: ["Study second."] },
            ],
          }],
          decision_log: [{ affected_session_ids: ["sess1", "sess2"] }],
        },
      },
      checksum: "lesson-plan-next",
    }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await saveLessonPlanDecision("herb-course", {
      constraints: {
        maxSessionHours: 0.5,
        defaultMode: "live",
        calendarDates: ["2026-08-03"],
        instructorCount: 1,
        deliveryPlatform: "Studio classroom",
      },
      operations: [
        { op: "set_mode", targetId: "s2", value: "self_study" },
        { op: "move_segment", targetId: "s2", value: "sess2", position: 1 },
        { op: "reorder_session", sessionIds: ["sess2", "sess1"] },
      ],
      rationale: "Use a shorter blended delivery sequence.",
    }, "lesson-plan-before");

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/courses/herb-course/lesson-plan/decision");
    expect(requestBody(fetchMock)).toEqual({
      expected_checksum: "lesson-plan-before",
      constraints: {
        max_session_hours: 0.5,
        default_mode: "live",
        calendar_dates: ["2026-08-03"],
        instructor_count: 1,
        delivery_platform: "Studio classroom",
      },
      operations: [
        { op: "set_mode", target_id: "s2", value: "self_study" },
        { op: "move_segment", target_id: "s2", value: "sess2", position: 1 },
        { op: "reorder_session", session_ids: ["sess2", "sess1"] },
      ],
      rationale: "Use a shorter blended delivery sequence.",
    });
    expect(result).toMatchObject({
      checksum: "lesson-plan-next",
      lessonPlan: {
        totalDurationMinutes: 40,
        constraints: {
          maxSessionHours: 0.5,
          deliveryPlatform: "Studio classroom",
        },
        unresolvedConstraints: [],
        affectedSessionIds: ["sess1", "sess2"],
        sessions: [{
          id: "sess1",
          covers: [
            { subtopicId: "s1", mode: "live" },
            { subtopicId: "s2", mode: "self_study" },
          ],
        }],
      },
    });
  });

  it("preserves the individual Outcomes checksum and normalizes projected advisories", async () => {
    const fetchMock = vi.fn((path: string) => {
      if (path.endsWith("/workspace")) {
        return Promise.resolve(jsonResponse({
          course_id: "herb-course",
          title: "Indoor herbs",
          current_stage: "outcomes",
          operator_status: "pending_review",
          stages: [{
            slug: "outcomes",
            label: "Outcomes",
            state: "awaiting_review",
            checksum: "stage-checksum",
            actions: [{ id: "edit", label: "Edit Outcomes", enabled: true }],
            advisories: [{
              severity: "advisory",
              code: "vague_verb",
              outcome_id: "co1",
              field: "statement",
              message: "Use a more observable verb.",
            }],
          }],
        }));
      }
      if (path.endsWith("/stages/outcomes")) {
        return Promise.resolve(jsonResponse({
          slug: "outcomes",
          advisories: [{
            severity: "advisory",
            code: "vague_verb",
            outcome_id: "co1",
            field: "statement",
            message: "Use a more observable verb.",
          }],
          artifacts: [{
            artifact_type: "course_outcomes",
            checksum: "outcomes-artifact-checksum",
            body: {
              outcomes: [{
                id: "co1",
                statement: "Understand indoor herbs.",
                evidence: "Learner explains a growing decision.",
                cognitive_level: "understand",
                priority: "core",
              }],
            },
          }],
        }));
      }
      return Promise.resolve(jsonResponse({ slug: path.split("/").at(-1), artifacts: [] }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await getWorkspace("herb-course");

    expect(result.workspace.outcomesChecksum).toBe("outcomes-artifact-checksum");
    expect(result.workspace.outcomes).toEqual([expect.objectContaining({
      id: "co1",
      cognitiveLevel: "understand",
      priority: "core",
    })]);
    expect(result.workspace.outcomeAdvisories).toEqual([{
      code: "vague_verb",
      outcomeId: "co1",
      relatedOutcomeId: undefined,
      field: "statement",
      reason: "Use a more observable verb.",
      level: "advisory",
    }]);
    expect(result.workspace.stages[0]?.checksum).toBe("stage-checksum");
  });

  it("serializes a complete typed Outcomes decision and returns the canonical draft", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      artifact: {
        body: {
          outcomes: [
            {
              id: "co2",
              statement: "Apply a safe watering routine.",
              evidence: "Learner completes a watering scenario.",
              cognitive_level: "apply",
              priority: "core",
            },
            {
              id: "co3",
              statement: "Evaluate an indoor growing location.",
              evidence: "Learner compares two locations.",
              cognitive_level: "evaluate",
              priority: "supporting",
            },
          ],
        },
      },
      checksum: "outcomes-next",
      advisories: [],
    }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await saveOutcomeDecision("herb-course", {
      expectedChecksum: "outcomes-before",
      selectedIds: ["co2"],
      edits: {
        co2: {
          statement: "Apply a safe watering routine.",
          cognitiveLevel: "apply",
          priority: "core",
        },
      },
      additions: [{
        clientKey: "new_1",
        statement: "Evaluate an indoor growing location.",
        evidence: "Learner compares two locations.",
        cognitiveLevel: "evaluate",
        priority: "supporting",
      }],
      priorityOrder: ["co2", "new_1"],
    });

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/courses/herb-course/outcomes/decision");
    expect((fetchMock.mock.calls[0]?.[1] as RequestInit).method).toBe("PUT");
    expect(requestBody(fetchMock)).toEqual({
      expected_checksum: "outcomes-before",
      selected_ids: ["co2"],
      edits: {
        co2: {
          statement: "Apply a safe watering routine.",
          cognitive_level: "apply",
          priority: "core",
        },
      },
      additions: [{
        client_key: "new_1",
        statement: "Evaluate an indoor growing location.",
        evidence: "Learner compares two locations.",
        cognitive_level: "evaluate",
        priority: "supporting",
      }],
      priority_order: ["co2", "new_1"],
    });
    expect(result).toMatchObject({
      checksum: "outcomes-next",
      outcomes: [
        { id: "co2", cognitiveLevel: "apply" },
        { id: "co3", cognitiveLevel: "evaluate" },
      ],
      advisories: [],
    });
  });

  it("serializes known-source, Source Repair, and both typed Content Repair strategies", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ artifact: {}, checksum: "dossier-next" }, 201))
      .mockResolvedValueOnce(jsonResponse({
        repair_id: "repair_1",
        job: { job_id: "job-1", status: "queued" },
        events_url: "/api/jobs/job-1/events",
      }, 202))
      .mockResolvedValueOnce(jsonResponse({ checksum: "repair-decision" }))
      .mockResolvedValueOnce(jsonResponse({
        source_id: "repair_src_1",
        affected_asset_ids: ["m1_s1_cc"],
        checksum: "repair-routed",
      }))
      .mockResolvedValueOnce(jsonResponse({
        strategy: "existing_evidence",
        target_asset_ids: ["m1_s2_cc"],
        job: { job_id: "job-2", status: "queued" },
      }, 202))
      .mockResolvedValueOnce(jsonResponse({
        strategy: "better_evidence",
        target_asset_ids: ["m1_s1_cc"],
        source_repair_id: "repair_1",
        job: { job_id: "job-3", status: "queued" },
        events_url: "/api/jobs/job-3/events",
      }, 202));
    vi.stubGlobal("fetch", fetchMock);

    await addKnownSource("course-1", {
      expectedChecksum: "dossier-before",
      locator: "https://example.edu/guide",
      title: "Focused guide",
      relevance: "Supports the named gap.",
    });
    const requested = await requestSourceRepair("course-1", {
      expectedContentChecksum: "content-before",
      subtopicId: "m1_s1",
      assetId: "m1_s1_cc",
      claimId: "cl1",
      findingId: "cl1",
      evidenceGap: "Unsupported claim needs a focused source.",
      mode: "deterministic",
    });
    await decideSourceRepair("course-1", "repair_1", {
      expectedChecksum: "repair-before",
      candidateId: "repair_src_1",
      decision: "approved",
      rationale: "The bounded preview covers the gap.",
    });
    const routed = await confirmSourceRepairRoute("course-1", "repair_1", {
      expectedChecksum: "repair-decision",
      subtopicIds: ["m1_s1"],
      assetIds: ["m1_s1_cc"],
    });
    const existingRepair = await requestContentRepair("course-1", {
      expectedContentChecksum: "content-before",
      strategy: "existing_evidence",
      targets: [{ assetId: "m1_s2_cc", claimIds: ["cl2"], findingIds: ["cl2"] }],
      mode: "deterministic",
    });
    const betterEvidenceRepair = await requestContentRepair("course-1", {
      expectedContentChecksum: "content-after-existing",
      strategy: "better_evidence",
      targets: [{ assetId: "m1_s1_cc", claimIds: ["cl1"], findingIds: ["cl1"] }],
      sourceRepairId: "repair_1",
      expectedSourceRepairChecksum: "repair-routed",
      mode: "deterministic",
    });

    expect(requestBody(fetchMock, 0)).toMatchObject({
      expected_checksum: "dossier-before",
      locator: "https://example.edu/guide",
      title: "Focused guide",
    });
    expect(requestBody(fetchMock, 1)).toEqual({
      expected_content_checksum: "content-before",
      subtopic_id: "m1_s1",
      asset_id: "m1_s1_cc",
      claim_id: "cl1",
      finding_id: "cl1",
      evidence_gap: "Unsupported claim needs a focused source.",
      mode: "deterministic",
    });
    expect(requestBody(fetchMock, 2)).toEqual({
      expected_checksum: "repair-before",
      candidate_id: "repair_src_1",
      decision: "approved",
      rationale: "The bounded preview covers the gap.",
    });
    expect(requestBody(fetchMock, 3)).toEqual({
      expected_checksum: "repair-decision",
      subtopic_ids: ["m1_s1"],
      asset_ids: ["m1_s1_cc"],
    });
    expect(requestBody(fetchMock, 4)).toEqual({
      expected_content_checksum: "content-before",
      strategy: "existing_evidence",
      targets: [{ asset_id: "m1_s2_cc", claim_ids: ["cl2"], finding_ids: ["cl2"] }],
      mode: "deterministic",
    });
    expect(requestBody(fetchMock, 5)).toEqual({
      expected_content_checksum: "content-after-existing",
      strategy: "better_evidence",
      targets: [{ asset_id: "m1_s1_cc", claim_ids: ["cl1"], finding_ids: ["cl1"] }],
      source_repair_id: "repair_1",
      expected_source_repair_checksum: "repair-routed",
      mode: "deterministic",
    });
    expect(requested.repairId).toBe("repair_1");
    expect(routed).toEqual({
      sourceId: "repair_src_1",
      affectedAssetIds: ["m1_s1_cc"],
      checksum: "repair-routed",
    });
    expect(existingRepair).toMatchObject({
      strategy: "existing_evidence",
      targetAssetIds: ["m1_s2_cc"],
      events_url: "/api/jobs/job-2/events",
    });
    expect(betterEvidenceRepair).toMatchObject({
      strategy: "better_evidence",
      targetAssetIds: ["m1_s1_cc"],
      sourceRepairId: "repair_1",
      events_url: "/api/jobs/job-3/events",
    });
  });

  it("distinguishes checksum conflicts from other 409 responses", () => {
    expect(versionConflictChecksum(new ApiError("changed", 409, {
      error: { message: "changed", actual_checksum: "latest-checksum" },
    }))).toBe("latest-checksum");
    expect(versionConflictChecksum(new ApiError("course busy", 409, {
      error: { message: "course busy" },
    }))).toBeUndefined();
    expect(versionConflictChecksum(new ApiError("invalid", 400, {
      error: { actual_checksum: "irrelevant" },
    }))).toBeUndefined();
    expect(outcomeValidationIssues(new ApiError("invalid decision", 400, {
      error: {
        code: "invalid_outcome_decision",
        issues: [{
          code: "empty_evidence",
          message: "Evidence cannot be blank.",
          outcome_id: "co1",
          field: "evidence",
        }],
      },
    }))).toEqual([{
      code: "empty_evidence",
      message: "Evidence cannot be blank.",
      outcomeId: "co1",
      field: "evidence",
      index: undefined,
    }]);
  });
});
