import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { BlueprintAssetType, ContentAsset, Workspace } from "../../types";
import { BlueprintEditor, type BlueprintEditorProps } from "./BlueprintEditor";

const assetTypes: BlueprintAssetType[] = [
  "course_content",
  "learning_objectives",
  "summary",
  "case_study",
  "assessment",
  "activities",
  "resources",
];

function plan(subtopicId: string): Workspace["blueprint"]["plans"][number] {
  return {
    subtopicId,
    depth: "introductory",
    minutes: 20,
    wordMinimum: 700,
    wordTarget: 1000,
    wordMaximum: 1400,
    examples: 2,
    caseDepth: "brief",
    assessmentComplexity: "application",
    exception: false,
    anchorWaiverConfirmed: false,
    assets: assetTypes.map((assetType) => ({
      id: `${subtopicId}_${assetType}`,
      assetType,
      title: assetType,
      selectionStatus: ["course_content", "summary"].includes(assetType) ? "selected" : "proposed",
      sourceIds: ["src1"],
    })),
  };
}

const blueprint: Workspace["blueprint"] = {
  defaults: {
    depth: "introductory",
    minutes: 20,
    wordMinimum: 700,
    wordTarget: 1000,
    wordMaximum: 1400,
    examples: 2,
    caseDepth: "brief",
    assessmentComplexity: "application",
    assetTypes: ["course_content", "summary"],
  },
  plans: [plan("s1"), plan("s2")],
};

const existingContent: ContentAsset[] = [{
  id: "s1_course_content",
  subtopicId: "s1",
  type: "course_content",
  title: "Existing lesson",
  format: "pptx",
  content: "Existing content",
  status: "done",
  reviewStatus: "approved",
  claims: [],
  verification: { supported: 0, partial: 0, unsupported: 0, ungrounded: 0, unattributed: 0 },
}];

function props(overrides: Partial<BlueprintEditorProps> = {}): BlueprintEditorProps {
  return {
    blueprint,
    contentAssets: existingContent,
    subtopicNames: { s1: "First topic", s2: "Second topic" },
    canEdit: true,
    editing: true,
    busy: false,
    conflict: false,
    onStartEdit: vi.fn(),
    onCancel: vi.fn(),
    onSave: vi.fn(),
    onResolveConflict: vi.fn(),
    onDirtyChange: vi.fn(),
    ...overrides,
  };
}

describe("BlueprintEditor", () => {
  it("applies editable defaults, preserves explicit exceptions, and submits exact reconciliation", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(<BlueprintEditor {...props({ onSave })} />);

    const defaults = screen.getByLabelText("Course default assets");
    await user.click(within(defaults).getByRole("button", { name: /Activity/ }));
    expect(within(defaults).getByRole("button", { name: /Activity/ })).toHaveAttribute("aria-pressed", "true");
    const firstAssets = screen.getByLabelText("Assets for First topic");
    await user.click(within(firstAssets).getByRole("button", { name: /Activity/ }));
    await user.clear(screen.getByLabelText("First topic learning time"));
    await user.type(screen.getByLabelText("First topic learning time"), "45");

    expect(screen.getByText("s2_activities")).toBeVisible();
    expect(screen.getByText("Existing lesson")).toBeVisible();
    const acknowledgement = screen.getByRole("checkbox", { name: /reviewed the exact asset additions/i });
    await user.click(acknowledgement);
    await user.click(screen.getByRole("button", { name: "Save Blueprint draft" }));

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      defaultAssetTypes: ["course_content", "summary", "activities"],
      selectedAssetTypes: { s1: ["course_content", "summary"] },
      depthOverrides: { s1: { minutes: 45 } },
      anchorWaivers: [],
    }));
  });

  it("requires an explicit anchor waiver and invalidates acknowledgement after any change", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(<BlueprintEditor {...props({ onSave })} />);

    const firstAssets = screen.getByLabelText("Assets for First topic");
    await user.click(within(firstAssets).getByRole("button", { name: /Course Content/ }));
    expect(screen.getByText(/requires an explicit Course Content anchor waiver/)).toBeVisible();
    expect(screen.getByRole("button", { name: "Save Blueprint draft" })).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: /Confirm Course Content anchor waiver/i }));
    const acknowledgement = screen.getByRole("checkbox", { name: /reviewed the exact asset additions/i });
    await user.click(acknowledgement);
    expect(screen.getByRole("button", { name: "Save Blueprint draft" })).toBeEnabled();

    await user.click(within(firstAssets).getByRole("button", { name: /Assessment/ }));
    expect(acknowledgement).not.toBeChecked();
    await user.click(acknowledgement);
    await user.click(screen.getByRole("button", { name: "Save Blueprint draft" }));
    expect(onSave.mock.calls[0][0].anchorWaivers).toEqual(["s1"]);
  });

  it("marks invalid ranges accessibly and offers explicit stale-conflict recovery", async () => {
    const user = userEvent.setup();
    const onResolveConflict = vi.fn();
    render(<BlueprintEditor {...props({ conflict: true, onResolveConflict })} />);

    const reviewLocal = screen.getByRole("button", { name: "Review local decision again" });
    expect(reviewLocal).toHaveFocus();
    await user.clear(screen.getByLabelText("Course default minimum words"));
    await user.type(screen.getByLabelText("Course default minimum words"), "1600");
    expect(screen.getByLabelText("Course default minimum words")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText(/Course default word range must satisfy/)).toBeVisible();
    expect(screen.getByRole("dialog", { name: "The Blueprint changed elsewhere" })).toBeVisible();
    await user.click(reviewLocal);
    expect(onResolveConflict).toHaveBeenCalledWith("reapply");
  });
});
