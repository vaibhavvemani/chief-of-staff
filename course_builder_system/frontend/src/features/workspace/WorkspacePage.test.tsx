import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { demoWorkspace } from "../../data/demo";
import { briefSectionUpdates, WorkspacePage } from "./WorkspacePage";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderWorkspace() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/courses/herb-course/outcomes?mode=deterministic"]}>
        <Routes>
          <Route path="/courses/:courseId/:stage" element={<WorkspacePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const initialOutcomes = [{
  id: "co1",
  statement: "Explain the core growing conditions for indoor herbs.",
  evidence: "Learner explains light, water, and soil needs.",
  cognitive_level: "understand",
  priority: "core",
}];

function outcomesFetch(options: { conflict?: boolean } = {}) {
  let artifactChecksum = "outcomes-artifact-checksum-1";
  let outcomes = initialOutcomes.map((outcome) => ({ ...outcome }));
  let decisionBody: Record<string, unknown> | undefined;
  let conflictReturned = false;
  const fetchMock = vi.fn(async (pathValue: string | URL | Request, init?: RequestInit) => {
    const path = String(pathValue);
    if (path.endsWith("/outcomes/decision") && init?.method === "PUT") {
      decisionBody = JSON.parse(String(init.body)) as Record<string, unknown>;
      if (options.conflict && !conflictReturned) {
        conflictReturned = true;
        artifactChecksum = "outcomes-artifact-checksum-2";
        outcomes = [{ ...outcomes[0], statement: "The newer server Outcome statement." }];
        return jsonResponse({
          error: {
            message: "artifact changed",
            actual_checksum: artifactChecksum,
          },
        }, 409);
      }
      const edits = decisionBody.edits as Record<string, Record<string, unknown>>;
      outcomes = outcomes.map((outcome) => ({ ...outcome, ...edits[outcome.id] }));
      artifactChecksum = "outcomes-artifact-checksum-3";
      return jsonResponse({
        artifact: { body: { outcomes } },
        checksum: artifactChecksum,
        advisories: [],
      });
    }
    if (path.endsWith("/workspace")) {
      return jsonResponse({
        course_id: "herb-course",
        title: "Indoor herbs",
        current_stage: "outcomes",
        operator_status: "pending_review",
        stages: [{
          slug: "outcomes",
          label: "Outcomes",
          state: "awaiting_review",
          checksum: "outcomes-stage-checksum",
          dependencies: ["brief"],
          downstream_stages: ["research"],
          prerequisites_ready: true,
          approval_failures: [],
          actions: [
            { id: "edit", label: "Edit Outcomes", enabled: true, requires_impact_confirmation: false },
            { id: "approve", label: "Approve Outcomes", enabled: true, requires_impact_confirmation: false },
          ],
          advisories: [],
        }],
      });
    }
    if (path.endsWith("/stages/outcomes")) {
      return jsonResponse({
        slug: "outcomes",
        advisories: [],
        artifacts: [{
          artifact_type: "course_outcomes",
          checksum: artifactChecksum,
          envelope: { status: "draft" },
          body: { outcomes },
        }],
      });
    }
    return jsonResponse({ slug: path.split("/").at(-1), artifacts: [] });
  });
  return { fetchMock, getDecisionBody: () => decisionBody };
}

afterEach(() => vi.unstubAllGlobals());

describe("Brief direct-edit merge payloads", () => {
  it("sends only changed fields from the edited section", () => {
    const original = demoWorkspace.brief;
    const edited = {
      ...original,
      audience: "Adults learning to brew coffee at home",
      purpose: "Diagnose common taste problems",
    };

    expect(briefSectionUpdates("learner", edited, original)).toEqual({
      audience: "Adults learning to brew coffee at home",
      purpose: "Diagnose common taste problems",
    });
  });

  it("does not reset unrelated answers or accepted defaults", () => {
    const original = demoWorkspace.brief;
    const edited = {
      ...original,
      mustHaveTopics: [...original.mustHaveTopics, "Taste troubleshooting"],
    };

    expect(briefSectionUpdates("coverage", edited, original)).toEqual({
      mustHaveTopics: [...original.mustHaveTopics, "Taste troubleshooting"],
    });
    expect(briefSectionUpdates("coverage", edited, original)).not.toHaveProperty("language");
    expect(original.intakeState.acceptedDefaultFields).toEqual(["audience", "duration", "level"]);
  });

  it("supports sparse edits to conditional requirements and source materials", () => {
    const original = demoWorkspace.brief;
    const edited = {
      ...original,
      liveTeachingConstraints: "Keep instructor-led blocks under 45 minutes.",
      availableMaterials: [...original.availableMaterials, "https://example.test/coffee"],
    };

    expect(briefSectionUpdates("requirements", edited, original)).toEqual({
      liveTeachingConstraints: "Keep instructor-led blocks under 45 minutes.",
      availableMaterials: [...original.availableMaterials, "https://example.test/coffee"],
    });
    expect(briefSectionUpdates("requirements", edited, original)).not.toHaveProperty("audience");
  });
});

describe("Workspace Outcomes decisions", () => {
  it("routes the projected Edit action to Outcomes and submits the individual artifact checksum", async () => {
    const user = userEvent.setup();
    const backend = outcomesFetch();
    vi.stubGlobal("fetch", backend.fetchMock);
    const view = renderWorkspace();

    await screen.findByRole("heading", { name: "Course Outcomes" });
    const decisionBar = view.container.querySelector(".decision-bar");
    expect(decisionBar).not.toBeNull();
    await user.click(within(decisionBar as HTMLElement).getByRole("button", { name: "Edit Outcomes" }));
    expect(screen.getByRole("heading", { name: "Shape the learning contract" })).toBeVisible();
    expect(screen.queryByRole("dialog", { name: /Learner and intent/i })).not.toBeInTheDocument();

    const statement = screen.getByLabelText("Outcome statement for co1");
    await user.clear(statement);
    await user.type(statement, "Apply a healthy indoor herb growing routine.");
    await user.click(screen.getByRole("button", { name: "Save Outcomes draft" }));

    await waitFor(() => expect(backend.getDecisionBody()).toMatchObject({
      expected_checksum: "outcomes-artifact-checksum-1",
      selected_ids: ["co1"],
      edits: { co1: { statement: "Apply a healthy indoor herb growing routine." } },
      priority_order: ["co1"],
    }));
    expect(backend.getDecisionBody()?.expected_checksum).not.toBe("outcomes-stage-checksum");
    expect(await screen.findByText("Apply a healthy indoor herb growing routine.")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Shape the learning contract" })).not.toBeInTheDocument();
  });

  it("keeps local edits after a true checksum conflict and requires an explicit recovery choice", async () => {
    const user = userEvent.setup();
    const backend = outcomesFetch({ conflict: true });
    vi.stubGlobal("fetch", backend.fetchMock);
    const view = renderWorkspace();

    await screen.findByRole("heading", { name: "Course Outcomes" });
    const decisionBar = view.container.querySelector(".decision-bar");
    await user.click(within(decisionBar as HTMLElement).getByRole("button", { name: "Edit Outcomes" }));
    const statement = screen.getByLabelText("Outcome statement for co1");
    await user.clear(statement);
    await user.type(statement, "My unsaved local Outcome statement.");
    await user.click(screen.getByRole("button", { name: "Save Outcomes draft" }));

    expect(await screen.findByText("These Outcomes changed elsewhere.")).toBeVisible();
    expect(screen.getByLabelText("Outcome statement for co1")).toHaveValue("My unsaved local Outcome statement.");
    expect(screen.getByRole("button", { name: "Save Outcomes draft" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Use latest server version" }));
    expect(screen.getByLabelText("Outcome statement for co1")).toHaveValue("The newer server Outcome statement.");
    expect(screen.queryByText("These Outcomes changed elsewhere.")).not.toBeInTheDocument();
  });

  it("warns before internal navigation would discard unsaved Outcomes", async () => {
    const user = userEvent.setup();
    const backend = outcomesFetch();
    const confirm = vi.fn(() => false);
    vi.stubGlobal("fetch", backend.fetchMock);
    vi.stubGlobal("confirm", confirm);
    const view = renderWorkspace();

    await screen.findByRole("heading", { name: "Course Outcomes" });
    const decisionBar = view.container.querySelector(".decision-bar");
    await user.click(within(decisionBar as HTMLElement).getByRole("button", { name: "Edit Outcomes" }));
    await user.type(screen.getByLabelText("Outcome statement for co1"), " revised");
    await user.click(screen.getByRole("link", { name: "Courses" }));

    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("unsaved Outcomes changes"));
    expect(screen.getByRole("heading", { name: "Course Outcomes" })).toBeVisible();
  });
});
