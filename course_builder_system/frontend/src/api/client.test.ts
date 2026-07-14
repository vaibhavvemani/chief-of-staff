import { afterEach, describe, expect, it, vi } from "vitest";
import {
  approveStage,
  createCourse,
  requestStageChanges,
  reviewContentAsset,
  runStage,
  saveBriefAnswers,
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
  it("maps the course creation form to the backend request contract", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ course_id: "herb-course", workspace: { course_id: "herb-course" } }, 201))
      .mockResolvedValueOnce(jsonResponse({ artifact: { artifact_type: "brief" }, checksum: "brief-checksum" }));
    vi.stubGlobal("fetch", fetchMock);

    const created = await createCourse({
      subject: "Indoor herb gardening",
      description: "For apartment renters",
      constraints: "No outdoor beds\nKeep it compact",
      sourceUrls: ["https://example.test/herbs"],
      briefAnswers: {
        audience: "Apartment renters new to gardening",
        priorKnowledge: "No prior knowledge assumed.",
        purpose: "Grow a useful windowsill herb garden.",
        level: "beginner",
        duration: "3 hours of self-paced learning",
        modality: "self_paced",
        language: "English",
        constraints: ["No outdoor beds", "Keep it compact"],
      },
    });

    expect(created).toEqual({ courseId: "herb-course", briefInitialized: true });
    expect(requestBody(fetchMock, 0)).toEqual({
      subject: "Indoor herb gardening",
      description: "For apartment renters",
      constraints: ["No outdoor beds", "Keep it compact"],
      known_source_locators: ["https://example.test/herbs"],
    });
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/courses/herb-course/brief/answers");
    expect(requestBody(fetchMock)).toEqual({
      answers: {
        audience: "Apartment renters new to gardening",
        prior_knowledge: "No prior knowledge assumed.",
        purpose: "Grow a useful windowsill herb garden.",
        level: "beginner",
        duration: "3 hours of self-paced learning",
        modality: "self_paced",
        language: "English",
        constraints: ["No outdoor beds", "Keep it compact"],
      },
    });
  });

  it("saves typed Brief edits with artifact concurrency control", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ checksum: "brief-next" }));
    vi.stubGlobal("fetch", fetchMock);

    await saveBriefAnswers("herb-course", {
      courseTitle: "Indoor herbs",
      audience: "Apartment renters",
      priorKnowledge: "None",
      purpose: "Grow herbs indoors",
      level: "beginner",
      duration: "2 hours",
      modality: "self_paced",
      language: "English",
      inScope: ["Lighting"],
      outOfScope: ["Outdoor beds"],
      mustHaveTopics: ["Watering"],
      constraints: ["Small spaces"],
      assessmentExpectations: "A short practical check",
    }, "brief-before");

    expect(requestBody(fetchMock)).toEqual({
      answers: {
        course_title: "Indoor herbs",
        audience: "Apartment renters",
        prior_knowledge: "None",
        purpose: "Grow herbs indoors",
        level: "beginner",
        duration: "2 hours",
        modality: "self_paced",
        language: "English",
        in_scope: ["Lighting"],
        out_of_scope: ["Outdoor beds"],
        must_have_topics: ["Watering"],
        constraints: ["Small spaces"],
        assessment_expectations: "A short practical check",
      },
      expected_checksum: "brief-before",
    });
  });

  it("preserves a created course when Brief initialization loses the connection", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ course_id: "resilient-course" }, 201))
      .mockRejectedValueOnce(new TypeError("connection lost"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(createCourse({
      subject: "Resilient course",
      briefAnswers: {
        audience: "New learners",
        priorKnowledge: "None",
        level: "beginner",
        duration: "3 hours",
        modality: "self_paced",
        language: "English",
      },
    })).resolves.toEqual({ courseId: "resilient-course", briefInitialized: false });
  });

  it("uses checksums and normalizes nested job responses for stage commands", async () => {
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
      requestStageChanges("herb-course", "brief", {
        expectedChecksum: "checksum-3",
        note: "Narrow the scope",
      }),
    ).resolves.toEqual({
      job: { job_id: "job-change", status: "queued" },
      events_url: "/api/jobs/job-change/events",
    });
    expect(requestBody(fetchMock)).toEqual({
      expected_checksum: "checksum-3",
      feedback: "Narrow the scope",
      mode: "deterministic",
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
