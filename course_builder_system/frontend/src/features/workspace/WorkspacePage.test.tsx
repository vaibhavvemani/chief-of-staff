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

function renderCourseModelWorkspace() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const view = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/courses/herb-course/course-model?mode=deterministic"]}>
        <Routes>
          <Route path="/courses/:courseId/:stage" element={<WorkspacePage />} />
          <Route path="/courses" element={<h1>Courses list</h1>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...view, queryClient };
}

const courseModelBody = {
  course_metadata: { course_title: "Indoor herbs", course_outcome_ids: ["co1"] },
  structural_rationale: [{ id: "sr1", statement: "Start with conditions.", related_outcome_ids: ["co1"] }],
  source_registry: [{ id: "src1", title: "Indoor herb guide", publisher: "Example", source_type: "web", locator: "https://example.test/herbs", content_ref: "sources/src1.md" }],
  modules: [{
    id: "m1", order: 1, title: "Growing foundations", context: { purpose: "Build a healthy baseline.", in_scope: ["Light"], out_of_scope: ["Commercial farms"] }, prerequisite_module_ids: [],
    subtopics: [
      { id: "s1", order: 1, title: "Light and placement", context: { purpose: "Choose a useful location.", in_scope: ["Window light"], out_of_scope: ["Greenhouses"] }, prerequisite_subtopic_ids: [], concepts: [{ id: "c1", name: "Light", summary: "Match plants to available light.", depends_on: [], source_ids: ["src1"] }], coverage_requirements: [{ id: "cr1", statement: "Choose a placement.", concept_ids: ["c1"], source_ids: ["src1"] }], approved_source_ids: ["src1"] },
      { id: "s2", order: 2, title: "Water and drainage", context: { purpose: "Water safely.", in_scope: ["Drainage"], out_of_scope: ["Hydroponics"] }, prerequisite_subtopic_ids: ["s1"], concepts: [{ id: "c2", name: "Drainage", summary: "Avoid standing water.", depends_on: ["c1"], source_ids: ["src1"] }], coverage_requirements: [{ id: "cr2", statement: "Check drainage.", concept_ids: ["c2"], source_ids: ["src1"] }], approved_source_ids: ["src1"] },
    ],
  }],
};

function courseModelFetch(options: { previewConflict?: boolean; saveConflict?: boolean; approved?: boolean; readOnly?: boolean; activeJob?: boolean } = {}) {
  let checksum = "course-model-artifact-1";
  let body = structuredClone(courseModelBody);
  let approved = Boolean(options.approved);
  let previewConflictReturned = false;
  let saveConflictReturned = false;
  const requests: Array<{ path: string; body?: Record<string, unknown> }> = [];
  const stagePayload = () => ({
    slug: "course-model", label: "Course Model", state: approved ? "approved" : "awaiting_review", checksum: "course-model-stage-checksum", dependencies: ["brief", "course_outcomes", "research_dossier", "approved_source_registry"], downstream_stages: ["blueprint"], prerequisites_ready: true, approval_failures: [],
    actions: options.readOnly || options.activeJob ? [] : approved
      ? [{ id: "reopen", label: "Reopen Course Model", enabled: true, requires_impact_confirmation: true }, { id: "continue", label: "Continue to Blueprint", enabled: true, target_stage: "blueprint" }]
      : [{ id: "edit", label: "Edit Course Model", enabled: true }, { id: "approve", label: "Approve Course Model", enabled: true }],
  });
  const fetchMock = vi.fn(async (pathValue: string | URL | Request, init?: RequestInit) => {
    const path = String(pathValue);
    const requestBody = init?.body ? JSON.parse(String(init.body)) as Record<string, unknown> : undefined;
    requests.push({ path, body: requestBody });
    if (path.endsWith("/workspace")) return jsonResponse({ course_id: "herb-course", title: "Indoor herbs", current_stage: "course-model", operator_status: approved ? "in_progress" : "pending_review", read_only: options.readOnly, active_job: options.activeJob ? { job_id: "job-1", status: "running", stage: "course-model" } : undefined, stages: [stagePayload()] });
    if (path.endsWith("/stages/course-model")) return jsonResponse({ ...stagePayload(), artifacts: [{ artifact_type: "course_model", checksum, envelope: { status: approved ? "approved" : "draft" }, body }] });
    if (path.endsWith("/stages/outcomes")) return jsonResponse({ slug: "outcomes", artifacts: [{ artifact_type: "course_outcomes", checksum: "outcomes-1", envelope: { status: "approved" }, body: { outcomes: [{ id: "co1", statement: "Choose conditions for healthy herbs.", cognitive_level: "apply", evidence: "Placement plan", priority: "core" }] } }] });
    if (path.endsWith("/stages/research")) return jsonResponse({ slug: "research", artifacts: [{ artifact_type: "research_dossier", checksum: "research-1", envelope: { status: "approved" }, body: { source_candidates: [] } }, { artifact_type: "approved_source_registry", checksum: "sources-1", envelope: { status: "approved" }, body: { source_registry: [] } }] });
    if (path.endsWith("/course-model/decision/preview")) {
      if (options.previewConflict && !previewConflictReturned) {
        previewConflictReturned = true;
        checksum = "course-model-artifact-2";
        body = structuredClone(courseModelBody);
        body.modules[0].subtopics[0].title = "Latest server title";
        return jsonResponse({ error: { code: "version_conflict", message: "changed", actual_checksum: checksum } }, 409);
      }
      const operations = requestBody?.operations as Array<Record<string, unknown>>;
      const candidate = structuredClone(body);
      for (const operation of operations) {
        if (operation.op === "update_subtopic" && operation.target_id === "s1") candidate.modules[0].subtopics[0].title = String(operation.title);
        if (operation.op === "add_coverage") candidate.modules[0].subtopics[0].coverage_requirements.push({ id: "cr3", statement: String(operation.statement), concept_ids: operation.concept_ids as string[], source_ids: [] });
        if (operation.op === "reorder_subtopics") candidate.modules[0].subtopics.reverse();
      }
      return jsonResponse({ candidate_artifact: { body: candidate }, allocated_ids: { new_coverage_ui: "cr3" }, change_records: [], affected_records: { subtopic: { changed_ids: ["s1", "s2"], removed_ids: [] }, coverage: { changed_ids: ["cr3"], removed_ids: [] } }, impact: { direct_artifacts: ["course_model"], stale_artifacts: ["blueprint"], requires_rerun_stages: ["blueprint"], warnings: ["Blueprint will become stale."], impact_level: "downstream", impact_checksum: "impact-1" } });
    }
    if (path.endsWith("/course-model/decision") && init?.method === "PUT") {
      if (options.saveConflict && !saveConflictReturned) {
        saveConflictReturned = true;
        checksum = "course-model-artifact-2";
        body = structuredClone(courseModelBody);
        body.modules[0].subtopics[0].title = "Latest title after impact conflict";
        return jsonResponse({ error: { code: "stale_impact_preview", message: "impact changed" } }, 409);
      }
      const operations = requestBody?.operations as Array<Record<string, unknown>>;
      for (const operation of operations) {
        if (operation.op === "update_subtopic" && operation.target_id === "s1") body.modules[0].subtopics[0].title = String(operation.title);
      }
      checksum = "course-model-artifact-3";
      return jsonResponse({ artifact: { status: "draft", body }, checksum, allocated_ids: {}, impact: { direct_artifacts: ["course_model"], stale_artifacts: ["blueprint"], requires_rerun_stages: ["blueprint"], warnings: [], impact_level: "downstream", impact_checksum: "impact-1" } });
    }
    if (path.endsWith("/stages/course-model/approve")) { approved = true; return jsonResponse({}); }
    return jsonResponse({ slug: path.split("/").at(-1), artifacts: [] });
  });
  return { fetchMock, requests, getBody: () => body, getChecksum: () => checksum };
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

describe("Workspace Course Model decisions", () => {
  it("previews typed operations, replaces local state with the canonical draft, persists refresh, and approves separately", async () => {
    const user = userEvent.setup();
    const backend = courseModelFetch();
    vi.stubGlobal("fetch", backend.fetchMock);
    const view = renderCourseModelWorkspace();
    await screen.findByRole("heading", { name: "Course Model" });
    const decisionBar = view.container.querySelector<HTMLElement>(".decision-bar")!;
    await user.click(within(decisionBar).getByRole("button", { name: "Edit Course Model" }));
    const title = screen.getByLabelText("Subtopic title for s1");
    await user.clear(title);
    await user.type(title, "Light, placement, and rotation");
    expect(screen.queryByRole("button", { name: "Save Course Model draft" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Preview impact" }));
    await screen.findByText("Backend validation passed");
    expect(screen.getByRole("region", { name: "Renamed records: 1" })).toBeVisible();
    expect(screen.getByText("Light and placement", { exact: true })).toBeVisible();
    expect(screen.getAllByText("Light, placement, and rotation", { exact: true })).not.toHaveLength(0);
    await user.click(screen.getByRole("checkbox", { name: /reviewed the detailed structural diff/i }));
    await user.click(screen.getByRole("button", { name: "Save Course Model draft" }));

    expect(await screen.findByRole("heading", { name: "Light, placement, and rotation" })).toBeVisible();
    const saveRequest = backend.requests.find((request) => request.path.endsWith("/course-model/decision") && request.body?.impact_acknowledged === true);
    expect(saveRequest?.body).toMatchObject({ expected_checksum: "course-model-artifact-1", expected_impact_checksum: "impact-1" });
    expect(saveRequest?.body).not.toHaveProperty("body");
    await view.queryClient.invalidateQueries({ queryKey: ["workspace", "herb-course"] });
    expect(await screen.findByRole("heading", { name: "Light, placement, and rotation" })).toBeVisible();

    await user.click(within(decisionBar).getByRole("button", { name: "Approve Course Model" }));
    await waitFor(() => expect(backend.requests.some((request) => request.path.endsWith("/stages/course-model/approve"))).toBe(true));
    expect(await within(decisionBar).findByRole("button", { name: "Reopen Course Model" })).toBeVisible();
  });

  it("preserves the operation batch across a stale Course Model conflict and requires a new preview against the latest checksum", async () => {
    const user = userEvent.setup();
    const backend = courseModelFetch({ previewConflict: true });
    vi.stubGlobal("fetch", backend.fetchMock);
    const view = renderCourseModelWorkspace();
    await screen.findByRole("heading", { name: "Course Model" });
    await user.click(within(view.container.querySelector(".decision-bar")!).getByRole("button", { name: "Edit Course Model" }));
    const title = screen.getByLabelText("Subtopic title for s1");
    await user.clear(title);
    await user.type(title, "My retained local title");
    await user.click(screen.getByRole("button", { name: "Preview impact" }));
    const dialog = await screen.findByRole("dialog", { name: "The Course Model changed elsewhere" });
    expect(screen.getByLabelText("Subtopic title for s1")).toHaveValue("My retained local title");
    expect(within(dialog).getByText("Latest server title")).toBeVisible();
    await user.click(within(dialog).getByRole("button", { name: "Reapply operation batch" }));
    expect(screen.queryByText("Backend validation passed")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Preview impact" }));
    await screen.findByText("Backend validation passed");
    const previews = backend.requests.filter((request) => request.path.endsWith("/course-model/decision/preview"));
    expect(previews).toHaveLength(2);
    expect(previews[1].body?.expected_checksum).toBe("course-model-artifact-2");
  });

  it("does not reuse stale impact acknowledgement and can explicitly discard local work", async () => {
    const user = userEvent.setup();
    const backend = courseModelFetch({ saveConflict: true });
    vi.stubGlobal("fetch", backend.fetchMock);
    const view = renderCourseModelWorkspace();
    await screen.findByRole("heading", { name: "Course Model" });
    await user.click(within(view.container.querySelector(".decision-bar")!).getByRole("button", { name: "Edit Course Model" }));
    await user.type(screen.getByLabelText("Subtopic title for s1"), " locally revised");
    await user.click(screen.getByRole("button", { name: "Preview impact" }));
    await screen.findByText("Backend validation passed");
    await user.click(screen.getByRole("checkbox", { name: /reviewed the detailed structural diff/i }));
    await user.click(screen.getByRole("button", { name: "Save Course Model draft" }));
    const dialog = await screen.findByRole("dialog", { name: "The Course Model changed elsewhere" });
    expect(screen.queryByText("Backend validation passed")).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Discard local work" }));
    expect(await screen.findByRole("heading", { name: "Course Model" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Edit Course Model" })).not.toBeInTheDocument();
    await user.click(within(view.container.querySelector(".decision-bar")!).getByRole("button", { name: "Edit Course Model" }));
    expect(screen.getByLabelText("Subtopic title for s1")).toHaveValue("Latest title after impact conflict");
    expect(screen.getByRole("button", { name: "Preview impact" })).toBeDisabled();
  });

  it("protects unsaved Course Model operations during internal navigation", async () => {
    const user = userEvent.setup();
    const backend = courseModelFetch();
    const confirm = vi.fn(() => false);
    vi.stubGlobal("fetch", backend.fetchMock);
    vi.stubGlobal("confirm", confirm);
    const view = renderCourseModelWorkspace();
    await screen.findByRole("heading", { name: "Course Model" });
    await user.click(within(view.container.querySelector(".decision-bar")!).getByRole("button", { name: "Edit Course Model" }));
    await user.type(screen.getByLabelText("Subtopic title for s1"), " unsaved");
    await user.click(screen.getByRole("link", { name: "Courses" }));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining("unsaved Course Model changes"));
    expect(screen.getByRole("heading", { name: "Edit Course Model" })).toBeVisible();
  });

  it("blocks approved-before-reopen, read-only, and active-job editing", async () => {
    const approvedBackend = courseModelFetch({ approved: true });
    vi.stubGlobal("fetch", approvedBackend.fetchMock);
    let view = renderCourseModelWorkspace();
    await screen.findByRole("heading", { name: "Course Model" });
    expect(screen.queryByRole("button", { name: "Edit Course Model" })).not.toBeInTheDocument();
    expect(within(view.container.querySelector(".decision-bar")!).getByRole("button", { name: "Reopen Course Model" })).toBeVisible();
    view.unmount();

    const readOnlyBackend = courseModelFetch({ readOnly: true });
    vi.stubGlobal("fetch", readOnlyBackend.fetchMock);
    view = renderCourseModelWorkspace();
    await screen.findByRole("heading", { name: "Course Model" });
    expect(screen.queryByRole("button", { name: "Edit Course Model" })).not.toBeInTheDocument();
    view.unmount();

    const activeBackend = courseModelFetch({ activeJob: true });
    vi.stubGlobal("fetch", activeBackend.fetchMock);
    vi.stubGlobal("EventSource", class {
      addEventListener() {}
      removeEventListener() {}
      close() {}
    });
    renderCourseModelWorkspace();
    expect(await screen.findByRole("heading", { name: "The agent is building Course Model" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Edit Course Model" })).not.toBeInTheDocument();
  });
});
