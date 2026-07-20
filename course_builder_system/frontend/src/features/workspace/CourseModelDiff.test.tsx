import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { CourseModelData, CourseModelPreview } from "../../types";
import { buildCourseModelDiff, CourseModelDiff } from "./CourseModelDiff";

const sourceRegistry = [
  { id: "src1", title: "Original source", publisher: "Publisher" },
  { id: "src2", title: "Replacement source", publisher: "Publisher" },
];

const original: CourseModelData = {
  modules: [
    {
      id: "m1", order: 1, title: "Foundations", purpose: "Build the baseline.", inScope: ["Basics"], outOfScope: ["Advanced"], prerequisiteModuleIds: [],
      subtopics: [
        {
          id: "s1", order: 1, title: "Starting point", purpose: "Choose a starting point.", inScope: ["First steps"], outOfScope: ["Later work"], prerequisiteSubtopicIds: [], approvedSourceIds: ["src1"],
          concepts: [{ id: "c1", name: "Starting concept", summary: "A useful concept.", dependsOn: [], sourceIds: ["src1"] }],
          coverageRequirements: [{ id: "cr1", statement: "Explain the starting concept.", conceptIds: ["c1"], sourceIds: ["src1"] }],
        },
        { id: "s0", order: 2, title: "Retained topic", purpose: "Keep this topic.", inScope: ["Retained"], outOfScope: ["None"], prerequisiteSubtopicIds: [], approvedSourceIds: [], concepts: [], coverageRequirements: [] },
      ],
    },
    {
      id: "m2", order: 2, title: "Removed module", purpose: "Remove this branch.", inScope: ["Old"], outOfScope: ["New"], prerequisiteModuleIds: [],
      subtopics: [{
        id: "s2", order: 1, title: "Removed subtopic", purpose: "Remove this topic.", inScope: ["Old"], outOfScope: ["New"], prerequisiteSubtopicIds: [], approvedSourceIds: ["src1"],
        concepts: [{ id: "c2", name: "Removed concept", summary: "Old concept.", dependsOn: [], sourceIds: ["src1"] }],
        coverageRequirements: [{ id: "cr2", statement: "Removed requirement.", conceptIds: ["c2"], sourceIds: ["src1"] }],
      }],
    },
    {
      id: "m3", order: 3, title: "Practice", purpose: "Practice safely.", inScope: ["Practice"], outOfScope: ["Expert work"], prerequisiteModuleIds: [],
      subtopics: [{
        id: "s3", order: 1, title: "Steady topic", purpose: "Stay unchanged.", inScope: ["Same"], outOfScope: ["Same"], prerequisiteSubtopicIds: [], approvedSourceIds: [],
        concepts: [{ id: "c3", name: "Unchanged detail", summary: "This record is unchanged.", dependsOn: [], sourceIds: [] }],
        coverageRequirements: [],
      }],
    },
  ],
  courseOutcomeIds: ["co1"],
  rationales: [],
  eligibleSources: sourceRegistry,
};

const movedSubtopic = {
  ...structuredClone(original.modules[0].subtopics[0]),
  order: 2,
  title: "Controlled starting point",
  purpose: "Choose and justify a controlled starting point.",
  inScope: ["First steps", "Controlled adjustment"],
  outOfScope: ["Commercial work"],
  approvedSourceIds: ["src2"],
  concepts: [{ ...structuredClone(original.modules[0].subtopics[0].concepts[0]), name: "Controlled concept", sourceIds: ["src2"] }],
  coverageRequirements: [{ ...structuredClone(original.modules[0].subtopics[0].coverageRequirements[0]), statement: "Explain and apply the controlled concept.", sourceIds: ["src2"] }],
};

const candidate: CourseModelData = {
  ...original,
  modules: [
    { ...structuredClone(original.modules[2]), order: 1, subtopics: [structuredClone(original.modules[2].subtopics[0]), movedSubtopic] },
    {
      ...structuredClone(original.modules[0]),
      order: 2,
      title: "Core foundations",
      purpose: "Build and check the baseline.",
      inScope: ["Basics", "Checks"],
      outOfScope: ["Specialist work"],
      subtopics: [{ ...structuredClone(original.modules[0].subtopics[1]), order: 1 }],
    },
    {
      id: "m4", order: 3, title: "New applied module", purpose: "Apply the course.", inScope: ["Application"], outOfScope: ["Operations"], prerequisiteModuleIds: [],
      subtopics: [{
        id: "s4", order: 1, title: "New applied subtopic", purpose: "Apply the method.", inScope: ["Application"], outOfScope: ["Operations"], prerequisiteSubtopicIds: [], approvedSourceIds: [],
        concepts: [{ id: "c4", name: "New concept", summary: "A new concept.", dependsOn: [], sourceIds: [] }],
        coverageRequirements: [{ id: "cr4", statement: "Demonstrate the new concept.", conceptIds: ["c4"], sourceIds: [] }],
      }],
    },
  ],
};

const comprehensivePreview: CourseModelPreview = {
  candidate,
  allocatedIds: {
    new_module_ui: "m4",
    new_subtopic_ui: "s4",
    new_concept_ui: "c4",
    new_coverage_ui: "cr4",
  },
  changeRecords: [
    { operationIndex: 0, op: "remove_module", action: "removed", recordType: "module", recordId: "m2", recordIds: [] },
    { operationIndex: 1, op: "move_subtopic", action: "moved", recordType: "subtopic", recordId: "s1", recordIds: [], parentId: "m3" },
    { operationIndex: 2, op: "reorder_modules", action: "reordered", recordType: "module", recordIds: ["m3", "m1", "m4"] },
    { operationIndex: 3, op: "update_module", action: "updated", recordType: "module", recordId: "m1", recordIds: [] },
    { operationIndex: 4, op: "update_subtopic", action: "updated", recordType: "subtopic", recordId: "s1", recordIds: [] },
    { operationIndex: 5, op: "update_concept", action: "updated", recordType: "concept", recordId: "c1", recordIds: [] },
    { operationIndex: 6, op: "update_coverage", action: "updated", recordType: "coverage", recordId: "cr1", recordIds: [] },
    { operationIndex: 7, op: "assign_sources", action: "sources_assigned", recordType: "subtopic", recordId: "s1", recordIds: [] },
    { operationIndex: 8, op: "add_module", action: "added", recordType: "module", recordId: "m4", recordIds: [] },
    { operationIndex: 9, op: "add_subtopic", action: "added", recordType: "subtopic", recordId: "s4", recordIds: [], parentId: "m4" },
    { operationIndex: 10, op: "add_concept", action: "added", recordType: "concept", recordId: "c4", recordIds: [], parentId: "s4" },
    { operationIndex: 11, op: "add_coverage", action: "added", recordType: "coverage", recordId: "cr4", recordIds: [], parentId: "s4" },
  ],
  affectedRecords: {
    module: { changedIds: ["m3", "m1", "m4"], removedIds: ["m2"] },
    subtopic: { changedIds: ["s1", "s0", "s4"], removedIds: ["s2"] },
    concept: { changedIds: ["c1", "c4"], removedIds: ["c2"] },
    coverage: { changedIds: ["cr1", "cr4"], removedIds: ["cr2"] },
  },
  impact: {
    action: "edit", stage: "course-model", directArtifacts: ["course_model"], staleArtifacts: ["blueprint"], targetedAssets: [], preservedAssets: [], requiresRerunStages: ["blueprint"], warnings: [], impactLevel: "downstream", impactChecksum: "impact-1",
  },
};

describe("CourseModelDiff", () => {
  it("covers simultaneous additions, cascaded removals, renames, moves, scope, and source changes", () => {
    const diff = buildCourseModelDiff(original, comprehensivePreview);

    expect(diff.added.map((item) => item.id)).toEqual(["m4", "s4", "c4", "cr4"]);
    expect(diff.added.find((item) => item.id === "cr4")?.clientRef).toBe("new_coverage_ui");
    expect(diff.removed.map((item) => item.id)).toEqual(["m2", "s2", "c2", "cr2"]);
    expect(diff.removed.find((item) => item.id === "m2")?.cascaded).toBe(false);
    expect(diff.removed.filter((item) => item.cascaded).map((item) => item.id)).toEqual(["s2", "c2", "cr2"]);
    expect(diff.renamed.map((item) => item.id)).toEqual(expect.arrayContaining(["m1", "s1", "c1", "cr1"]));
    expect(diff.moved.map((item) => item.id)).toEqual(expect.arrayContaining(["m3", "m1", "s1", "s0"]));
    expect(diff.scope.map((item) => item.id)).toEqual(expect.arrayContaining(["m1", "s1"]));
    expect(diff.sources.map((item) => item.id)).toEqual(["s1", "c1", "cr1"]);
    expect(diff.sources[0].addedSources).toEqual(["Replacement source (src2)"]);
    expect(diff.sources[0].removedSources).toEqual(["Original source (src1)"]);
  });

  it("renders concise before/after values, canonical allocations, and omits unchanged records", () => {
    render(<CourseModelDiff original={original} preview={comprehensivePreview} />);

    expect(screen.getByRole("heading", { name: "What will change" })).toBeVisible();
    expect(screen.getByText(/12 ordered backend change records/)).toBeVisible();
    const added = screen.getByRole("region", { name: "Added records: 4" });
    expect(within(added).getByText("New applied module")).toBeVisible();
    expect(within(added).getByText("new_coverage_ui")).toBeVisible();
    const removed = screen.getByRole("region", { name: "Removed records: 4" });
    expect(within(removed).getByText("Removed module")).toBeVisible();
    expect(within(removed).getAllByText("Removed with its parent record")).toHaveLength(3);
    const renamed = screen.getByRole("region", { name: "Renamed records: 4" });
    expect(within(renamed).getByText("Foundations")).toBeVisible();
    expect(within(renamed).getAllByText("Core foundations")).toHaveLength(2);
    const moved = screen.getByRole("region", { name: "Moved or reordered records: 4" });
    expect(within(moved).getByText("Foundations · position 1")).toBeVisible();
    expect(within(moved).getAllByText("Practice · position 2")).toHaveLength(2);
    const scope = screen.getByRole("region", { name: "Purpose and scope changes: 2" });
    expect(within(scope).getByText("Build the baseline.")).toBeVisible();
    expect(within(scope).getByText("Build and check the baseline.")).toBeVisible();
    const sources = screen.getByRole("region", { name: "Source-assignment changes: 3" });
    expect(within(sources).getAllByText(/Added sources:/)).toHaveLength(3);
    expect(within(sources).getAllByText(/Removed sources:/)).toHaveLength(3);
    expect(screen.queryByText("Unchanged detail")).not.toBeInTheDocument();
  });

  it("reports a reorder-only candidate without inventing other changes", () => {
    const reordered = structuredClone(original);
    reordered.modules = [
      { ...reordered.modules[2], order: 1 },
      { ...reordered.modules[1], order: 2 },
      { ...reordered.modules[0], order: 3 },
    ];
    const preview: CourseModelPreview = {
      ...comprehensivePreview,
      candidate: reordered,
      allocatedIds: {},
      changeRecords: [{ operationIndex: 0, op: "reorder_modules", action: "reordered", recordType: "module", recordIds: ["m3", "m2", "m1"] }],
      affectedRecords: { module: { changedIds: ["m3", "m1"], removedIds: [] } },
    };

    const diff = buildCourseModelDiff(original, preview);
    expect(diff.moved.map((item) => item.id)).toEqual(["m3", "m1"]);
    expect(diff.total).toBe(2);
    expect(diff.added).toEqual([]);
    expect(diff.removed).toEqual([]);
    expect(diff.renamed).toEqual([]);
    expect(diff.scope).toEqual([]);
    expect(diff.sources).toEqual([]);
  });
});
