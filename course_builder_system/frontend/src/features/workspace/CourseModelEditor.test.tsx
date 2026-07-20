import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { CourseModelData, CourseModelPreview, Outcome } from "../../types";
import { CourseModelEditor, type CourseModelEditorProps } from "./CourseModelEditor";

const outcomes: Outcome[] = [
  { id: "co1", statement: "Explain foundations.", cognitiveLevel: "understand", evidence: "Explanation", priority: "core" },
  { id: "co2", statement: "Apply the process.", cognitiveLevel: "apply", evidence: "Demonstration", priority: "core" },
];

const model: CourseModelData = {
  modules: [
    {
      id: "m1", order: 1, title: "Foundations", purpose: "Build foundations.", inScope: ["Basics"], outOfScope: ["Advanced"], prerequisiteModuleIds: [],
      subtopics: [{
        id: "s1", order: 1, title: "First topic", purpose: "Learn the first topic.", inScope: ["First"], outOfScope: ["Later"], prerequisiteSubtopicIds: [], approvedSourceIds: ["src1"],
        concepts: [{ id: "c1", name: "First concept", summary: "A first concept.", dependsOn: [], sourceIds: ["src1"] }],
        coverageRequirements: [{ id: "cr1", statement: "Explain the first concept.", conceptIds: ["c1"], sourceIds: ["src1"] }],
      }],
    },
    {
      id: "m2", order: 2, title: "Practice", purpose: "Practice the skills.", inScope: ["Practice"], outOfScope: ["Operations"], prerequisiteModuleIds: ["m1"],
      subtopics: [{
        id: "s2", order: 1, title: "Second topic", purpose: "Learn the second topic.", inScope: ["Second"], outOfScope: ["Expert"], prerequisiteSubtopicIds: ["s1"], approvedSourceIds: ["src1"],
        concepts: [{ id: "c2", name: "Second concept", summary: "A second concept.", dependsOn: ["c1"], sourceIds: ["src1"] }],
        coverageRequirements: [{ id: "cr2", statement: "Apply the second concept.", conceptIds: ["c2"], sourceIds: ["src1"] }],
      }],
    },
  ],
  courseOutcomeIds: ["co1", "co2"],
  rationales: [{ id: "sr1", statement: "Foundations before practice.", relatedOutcomeIds: ["co1", "co2"] }],
  eligibleSources: [{ id: "src1", title: "Approved guide", publisher: "Publisher" }, { id: "src2", title: "Approved handbook", publisher: "Publisher" }],
};

const preview: CourseModelPreview = {
  candidate: model,
  allocatedIds: { new_coverage_test: "cr3" },
  changeRecords: [],
  affectedRecords: { subtopic: { changedIds: ["s1"], removedIds: [] } },
  impact: {
    action: "edit", stage: "course-model", directArtifacts: ["course_model"], staleArtifacts: ["blueprint"], targetedAssets: [], preservedAssets: [], requiresRerunStages: ["blueprint"], warnings: ["Blueprint will require rerun."], impactLevel: "downstream", impactChecksum: "impact-checksum",
  },
};

function editorProps(overrides: Partial<CourseModelEditorProps> = {}): CourseModelEditorProps {
  return {
    model,
    outcomes,
    canEdit: true,
    editing: true,
    busy: false,
    conflict: false,
    onStartEdit: vi.fn(),
    onCancel: vi.fn(),
    onPreview: vi.fn(),
    onSave: vi.fn(),
    onInvalidatePreview: vi.fn(),
    onRecoverConflict: vi.fn(),
    ...overrides,
  };
}

describe("CourseModelEditor", () => {
  it("derives edit availability from the wired capability", async () => {
    const user = userEvent.setup();
    const onStartEdit = vi.fn();
    const view = render(<CourseModelEditor {...editorProps({ editing: false, canEdit: false, onStartEdit })} />);
    expect(screen.queryByRole("button", { name: "Edit Course Model" })).not.toBeInTheDocument();
    view.rerender(<CourseModelEditor {...editorProps({ editing: false, canEdit: true, onStartEdit })} />);
    await user.click(screen.getByRole("button", { name: "Edit Course Model" }));
    expect(onStartEdit).toHaveBeenCalledOnce();
  });

  it("builds typed field, dependency, source, and Outcome link operations", async () => {
    const user = userEvent.setup();
    const onPreview = vi.fn();
    render(<CourseModelEditor {...editorProps({ onPreview })} />);

    const moduleTitle = screen.getByLabelText("Module title for m1");
    await user.clear(moduleTitle);
    await user.type(moduleTitle, "Revised foundations");
    await user.deselectOptions(screen.getByLabelText("Module prerequisites for m2"), ["m1"]);

    await user.click(screen.getByText("First topic", { selector: "strong" }).closest("button")!);
    const subtopicTitle = screen.getByLabelText("Subtopic title for s1");
    await user.clear(subtopicTitle);
    await user.type(subtopicTitle, "Extraction basics");
    await user.selectOptions(screen.getByLabelText("Approved sources for subtopic s1"), ["src1", "src2"]);
    await user.selectOptions(screen.getByLabelText("Dependencies for concept c1"), ["c2"]);
    await user.selectOptions(screen.getByLabelText("Approved sources for concept c1"), ["src1", "src2"]);
    await user.selectOptions(screen.getByLabelText("Approved sources for coverage cr1"), ["src1", "src2"]);
    await user.click(screen.getByRole("button", { name: "Move Course Outcome co1 down" }));
    await user.deselectOptions(screen.getByLabelText("Outcome links for rationale sr1"), ["co2"]);
    await user.click(screen.getByRole("button", { name: "Preview impact" }));

    const operations = onPreview.mock.calls[0][0];
    expect(operations).toEqual(expect.arrayContaining([
      expect.objectContaining({ op: "update_module", targetId: "m1", title: "Revised foundations" }),
      expect.objectContaining({ op: "update_module", targetId: "m2", prerequisiteModuleIds: [] }),
      expect.objectContaining({ op: "update_subtopic", targetId: "s1", title: "Extraction basics" }),
      { op: "assign_sources", targetType: "subtopic", targetId: "s1", sourceIds: ["src1", "src2"] },
      expect.objectContaining({ op: "update_concept", targetId: "c1", dependsOn: ["c2"] }),
      { op: "assign_sources", targetType: "concept", targetId: "c1", sourceIds: ["src1", "src2"] },
      { op: "assign_sources", targetType: "coverage", targetId: "cr1", sourceIds: ["src1", "src2"] },
      { op: "set_course_outcome_links", outcomeIds: ["co2", "co1"] },
      { op: "set_rationale_outcome_links", targetId: "sr1", outcomeIds: ["co1"] },
    ]));
  });

  it("moves and reorders records without changing their canonical IDs", async () => {
    const user = userEvent.setup();
    const onPreview = vi.fn();
    const threeModuleModel: CourseModelData = {
      ...model,
      modules: [...model.modules, {
        id: "m3", order: 3, title: "Mastery", purpose: "Build mastery.", inScope: ["Mastery"], outOfScope: ["None"], prerequisiteModuleIds: ["m2"],
        subtopics: [{ id: "s3", order: 1, title: "Third topic", purpose: "Learn the third topic.", inScope: ["Third"], outOfScope: ["None"], prerequisiteSubtopicIds: ["s2"], approvedSourceIds: ["src1"], concepts: [], coverageRequirements: [] }],
      }],
    };
    render(<CourseModelEditor {...editorProps({ model: threeModuleModel, onPreview })} />);
    await user.selectOptions(screen.getByLabelText("Move module m1 to position"), "3");
    await user.click(screen.getByRole("button", { name: "Reorder module Practice down" }));
    await user.selectOptions(screen.getByLabelText("Parent module for s1"), "m2");
    await user.click(screen.getByRole("button", { name: "Reorder subtopic First topic up" }));
    await user.click(screen.getByRole("button", { name: "Preview impact" }));
    const operations = onPreview.mock.calls[0][0];
    expect(operations).toEqual(expect.arrayContaining([
      { op: "move_module", targetId: "m1", position: 3 },
      { op: "reorder_modules", moduleIds: ["m3", "m2", "m1"] },
      expect.objectContaining({ op: "move_subtopic", targetId: "s1", parentId: "m2" }),
      { op: "reorder_subtopics", parentId: "m2", subtopicIds: ["s1", "s2"] },
    ]));
    expect(threeModuleModel.modules.map((module) => module.id)).toEqual(["m1", "m2", "m3"]);
  });

  it("uses valid request-local references for all additions", async () => {
    const user = userEvent.setup();
    const onPreview = vi.fn();
    render(<CourseModelEditor {...editorProps({ onPreview })} />);
    await user.click(screen.getByRole("button", { name: "Add module" }));
    await user.click(screen.getByRole("button", { name: /Add concept/ }));
    await user.click(screen.getByRole("button", { name: /Add coverage requirement/ }));
    await user.click(screen.getByRole("button", { name: "Preview impact" }));
    const operations = onPreview.mock.calls[0][0];
    const addModule = operations.find((operation: { op: string }) => operation.op === "add_module");
    const addSubtopic = operations.find((operation: { op: string }) => operation.op === "add_subtopic");
    const addConcept = operations.find((operation: { op: string }) => operation.op === "add_concept");
    const addCoverage = operations.find((operation: { op: string }) => operation.op === "add_coverage");
    expect(addModule.clientRef).toMatch(/^new_module_/);
    expect(addSubtopic.clientRef).toMatch(/^new_subtopic_/);
    expect(addSubtopic.parentId).toBe(addModule.clientRef);
    expect(addConcept.clientRef).toMatch(/^new_concept_/);
    expect(addConcept.parentId).toBe(addSubtopic.clientRef);
    expect(addCoverage.clientRef).toMatch(/^new_coverage_/);
    expect(addCoverage.parentId).toBe(addSubtopic.clientRef);
  });

  it("declares later request-local references before updates that use them", async () => {
    const user = userEvent.setup();
    const onPreview = vi.fn();
    render(<CourseModelEditor {...editorProps({ onPreview })} />);

    await user.click(screen.getByRole("button", { name: "Add concept" }));
    await user.click(screen.getByRole("button", { name: "Add concept" }));
    const dependencySelects = screen.getAllByLabelText(/^Dependencies for concept new_concept_/);
    const firstConceptRef = dependencySelects[0].getAttribute("aria-label")!.replace("Dependencies for concept ", "");
    const secondConceptRef = dependencySelects[1].getAttribute("aria-label")!.replace("Dependencies for concept ", "");
    await user.selectOptions(dependencySelects[0], secondConceptRef);

    await user.click(screen.getByRole("button", { name: "Add coverage requirement" }));
    await user.click(screen.getByRole("button", { name: "Add concept" }));
    const coverageSelect = screen.getAllByLabelText(/^Concept references for coverage new_coverage_/).at(-1)!;
    const laterConceptSelect = screen.getAllByLabelText(/^Dependencies for concept new_concept_/).at(-1)!;
    const laterConceptRef = laterConceptSelect.getAttribute("aria-label")!.replace("Dependencies for concept ", "");
    await user.selectOptions(coverageSelect, laterConceptRef);
    await user.click(screen.getByRole("button", { name: "Preview impact" }));

    const operations = onPreview.mock.calls[0][0];
    const firstAdd = operations.find((operation: { op: string; clientRef?: string }) => operation.op === "add_concept" && operation.clientRef === firstConceptRef);
    const dependencyUpdateIndex = operations.findIndex((operation: { op: string; targetId?: string }) => operation.op === "update_concept" && operation.targetId === firstConceptRef);
    const secondAddIndex = operations.findIndex((operation: { op: string; clientRef?: string }) => operation.op === "add_concept" && operation.clientRef === secondConceptRef);
    const coverageUpdate = operations.find((operation: { op: string; targetId?: string }) => operation.op === "update_coverage" && operation.targetId === coverageSelect.getAttribute("aria-label")!.replace("Concept references for coverage ", ""));
    const laterConceptAddIndex = operations.findIndex((operation: { op: string; clientRef?: string }) => operation.op === "add_concept" && operation.clientRef === laterConceptRef);
    const coverageUpdateIndex = operations.indexOf(coverageUpdate);
    expect(firstAdd.dependsOn).toEqual([]);
    expect(secondAddIndex).toBeLessThan(dependencyUpdateIndex);
    expect(coverageUpdate.conceptIds).toEqual([laterConceptRef]);
    expect(laterConceptAddIndex).toBeLessThan(coverageUpdateIndex);
  });

  it("removes restored values and structural reversals from the operation ledger", async () => {
    const user = userEvent.setup();
    const onPreview = vi.fn();
    render(<CourseModelEditor {...editorProps({ onPreview })} />);
    const title = screen.getByLabelText("Module title for m1");
    await user.clear(title);
    await user.type(title, "Temporary title");
    await user.click(screen.getByRole("button", { name: "Reorder module Temporary title down" }));
    await user.click(screen.getByRole("button", { name: "Reorder module Temporary title up" }));
    await user.selectOptions(screen.getByLabelText("Approved sources for subtopic s1"), ["src1", "src2"]);
    await user.deselectOptions(screen.getByLabelText("Approved sources for subtopic s1"), ["src2"]);
    await user.click(screen.getByRole("button", { name: "Move Course Outcome co1 down" }));
    await user.click(screen.getByRole("button", { name: "Move Course Outcome co1 up" }));
    await user.clear(title);
    await user.type(title, "Foundations");
    expect([...document.querySelectorAll(".operation-ledger strong")].map((item) => item.textContent)).toEqual([]);
    expect(screen.getByRole("button", { name: "Preview impact" })).toBeDisabled();
  });

  it("drops edits to records removed directly or by a container deletion", async () => {
    const user = userEvent.setup();
    const onPreview = vi.fn();
    render(<CourseModelEditor {...editorProps({ onPreview })} />);
    await user.type(screen.getByLabelText("Concept name for c1"), " revised");
    await user.click(screen.getByRole("button", { name: "Remove module Foundations" }));
    await user.click(screen.getByRole("button", { name: "Remove record" }));
    await user.click(screen.getByRole("button", { name: "Preview impact" }));
    const operations = onPreview.mock.calls[0][0];
    expect(operations).toContainEqual({ op: "remove_module", targetId: "m1" });
    expect(operations).not.toContainEqual(expect.objectContaining({ targetId: "c1" }));
  });

  it("removes a newly added record without leaving an add/remove no-op pair", async () => {
    const user = userEvent.setup();
    render(<CourseModelEditor {...editorProps()} />);
    await user.click(screen.getByRole("button", { name: "Add concept" }));
    await user.click(screen.getByRole("button", { name: "Remove concept New concept" }));
    await user.click(screen.getByRole("button", { name: "Remove record" }));
    expect(screen.getByText("0", { selector: ".operation-count strong" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Preview impact" })).toBeDisabled();
  });

  it("clears discarded operations before a later edit session", async () => {
    const user = userEvent.setup();
    const view = render(<CourseModelEditor {...editorProps()} />);
    await user.type(screen.getByLabelText("Subtopic title for s1"), " revised");
    expect(screen.getByText("1", { selector: ".operation-count strong" })).toBeVisible();
    view.rerender(<CourseModelEditor {...editorProps({ editing: false })} />);
    view.rerender(<CourseModelEditor {...editorProps({ editing: true })} />);
    await waitFor(() => expect(screen.getByLabelText("Subtopic title for s1")).toHaveValue("First topic"));
    expect(screen.getByRole("button", { name: "Preview impact" })).toBeDisabled();
  });

  it("requires confirmation before adding a typed removal", async () => {
    const user = userEvent.setup();
    const onPreview = vi.fn();
    render(<CourseModelEditor {...editorProps({ onPreview })} />);
    await user.click(screen.getByRole("button", { name: "Remove concept First concept" }));
    expect(screen.getByRole("dialog", { name: "Remove First concept?" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Remove record" }));
    await user.click(screen.getByRole("button", { name: "Preview impact" }));
    expect(onPreview.mock.calls[0][0]).toContainEqual({ op: "remove_concept", targetId: "c1" });
  });

  it("traps modal focus, closes with Escape, and restores the removal trigger", async () => {
    const user = userEvent.setup();
    render(<CourseModelEditor {...editorProps()} />);
    const trigger = screen.getByRole("button", { name: "Remove concept First concept" });
    await user.click(trigger);
    const confirm = screen.getByRole("button", { name: "Remove record" });
    expect(confirm).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("enforces preview and current impact acknowledgement before save", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    const view = render(<CourseModelEditor {...editorProps({ onSave })} />);
    expect(screen.queryByRole("button", { name: "Save Course Model draft" })).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Subtopic title for s1"), " revised");
    view.rerender(<CourseModelEditor {...editorProps({ onSave, preview })} />);
    const save = screen.getByRole("button", { name: "Save Course Model draft" });
    expect(save).toBeDisabled();
    expect(screen.getByText(/new_coverage_test/)).toBeVisible();
    expect(screen.getByText(/Blueprint will require rerun/)).toBeVisible();
    await user.click(screen.getByRole("checkbox", { name: /reviewed the allocated ids/i }));
    await user.type(screen.getByLabelText("Subtopic title for s1"), " again");
    expect(save).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: /reviewed the allocated ids/i })).toBeDisabled();
    const currentPreview = { ...preview, impact: { ...preview.impact, impactChecksum: "current-impact-checksum" } };
    view.rerender(<CourseModelEditor {...editorProps({ onSave, preview: currentPreview })} />);
    await waitFor(() => expect(screen.getByRole("checkbox", { name: /reviewed the allocated ids/i })).toBeEnabled());
    await user.click(screen.getByRole("checkbox", { name: /reviewed the allocated ids/i }));
    await user.click(save);
    expect(onSave).toHaveBeenCalledWith(expect.any(Array), "current-impact-checksum");
  });

  it("maps backend validation failures to the operation ledger and focuses the summary", () => {
    render(<CourseModelEditor {...editorProps({
      serverError: "The batch is invalid.",
      serverIssues: [{ code: "unknown_reference", message: "Concept c9 does not exist.", operationIndex: 0, recordType: "coverage", recordId: "cr1", field: "concept_ids" }],
    })} />);
    expect(screen.getByRole("alert")).toHaveFocus();
    expect(screen.getByText(/Concept c9 does not exist/)).toBeVisible();
    expect(screen.getByLabelText("Concept references for coverage cr1")).toHaveAttribute("aria-invalid", "true");
  });

  it("blocks editing controls during active work and offers explicit conflict recovery", async () => {
    const user = userEvent.setup();
    const onRecoverConflict = vi.fn();
    const view = render(<CourseModelEditor {...editorProps({ busy: true })} />);
    expect(screen.getByLabelText("Subtopic title for s1")).toBeDisabled();
    view.rerender(<CourseModelEditor {...editorProps({ conflict: true, onRecoverConflict })} />);
    const dialog = screen.getByRole("dialog", { name: "The Course Model changed elsewhere" });
    expect(within(dialog).getByText(/No structural operations were merged/i)).toBeVisible();
    await user.click(within(dialog).getByRole("button", { name: "Reapply operation batch" }));
    expect(onRecoverConflict).toHaveBeenCalledWith("reapply");
  });
});
