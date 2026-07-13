import { afterEach, describe, expect, it, vi } from "vitest";
import {
  approveStage,
  createCourse,
  requestStageChanges,
  reviewContentAsset,
  runStage,
  saveSourceDecision,
} from "./client";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function requestBody(fetchMock: ReturnType<typeof vi.fn>): Record<string, unknown> {
  const init = fetchMock.mock.calls.at(-1)?.[1] as RequestInit;
  return JSON.parse(String(init.body)) as Record<string, unknown>;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("typed API commands", () => {
  it("maps the course creation form to the backend request contract", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ course_id: "herb-course", workspace: { course_id: "herb-course" } }, 201),
    );
    vi.stubGlobal("fetch", fetchMock);

    const created = await createCourse({
      subject: "Indoor herb gardening",
      description: "For apartment renters",
      constraints: "No outdoor beds\nKeep it compact",
      sourceUrls: ["https://example.test/herbs"],
    });

    expect(created).toEqual({ courseId: "herb-course" });
    expect(requestBody(fetchMock)).toEqual({
      subject: "Indoor herb gardening",
      description: "For apartment renters",
      constraints: ["No outdoor beds", "Keep it compact"],
      known_source_locators: ["https://example.test/herbs"],
    });
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
