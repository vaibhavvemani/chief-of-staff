import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import type { Outcome, OutcomeAdvisory } from "../../types";
import { OutcomesEditor, type OutcomesEditorProps } from "./OutcomesEditor";

const outcomes: Outcome[] = [
  {
    id: "co1",
    statement: "Explain the core growing conditions for indoor herbs.",
    evidence: "Learner explains light, water, and soil needs.",
    cognitiveLevel: "understand",
    priority: "core",
  },
  {
    id: "co2",
    statement: "Apply a repeatable watering routine.",
    evidence: "Learner completes a realistic watering scenario.",
    cognitiveLevel: "apply",
    priority: "supporting",
  },
];

const advisories: OutcomeAdvisory[] = [{
  code: "vague_verb",
  outcomeId: "co1",
  field: "statement",
  reason: "Consider a more observable verb.",
  level: "advisory",
}];

function props(overrides: Partial<OutcomesEditorProps> = {}): OutcomesEditorProps {
  return {
    outcomes,
    advisories,
    canEdit: true,
    editing: true,
    busy: false,
    conflict: false,
    onStartEdit: vi.fn(),
    onCancel: vi.fn(),
    onSave: vi.fn(),
    onResolveConflict: vi.fn(),
    ...overrides,
  };
}

function ConflictHarness({
  latest,
  onResolveConflict,
  initial = outcomes,
}: {
  latest: Outcome[];
  onResolveConflict: (choice: "latest" | "keep") => void;
  initial?: Outcome[];
}) {
  const [canonical, setCanonical] = useState(initial);
  const [conflict, setConflict] = useState(false);
  return (
    <>
      <button onClick={() => { setCanonical(latest); setConflict(true); }}>Simulate concurrent update</button>
      <OutcomesEditor
        {...props({
          outcomes: canonical,
          conflict,
          onResolveConflict: (choice) => {
            onResolveConflict(choice);
            setConflict(false);
          },
        })}
      />
    </>
  );
}

describe("OutcomesEditor", () => {
  it("compares canonical fields semantically rather than by object insertion order", () => {
    const apiNormalizedOrder: Outcome[] = [{
      id: "co1",
      statement: "Explain the core growing conditions for indoor herbs.",
      cognitiveLevel: "understand",
      evidence: "Learner explains light, water, and soil needs.",
      priority: "core",
    }];
    render(<OutcomesEditor {...props({ outcomes: apiNormalizedOrder, advisories: [] })} />);

    expect(screen.getByRole("status")).toHaveTextContent("Matches saved draft");
    expect(screen.getByRole("button", { name: "Save Outcomes draft" })).toBeDisabled();
    expect(screen.getAllByText(/Canonical IDs stay fixed/)).toHaveLength(1);
  });

  it("keeps approved or locked Outcomes read-only while showing structured advisories", () => {
    render(<OutcomesEditor {...props({ canEdit: false, editing: false })} />);

    expect(screen.queryByRole("button", { name: "Edit Outcomes" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Add Outcome/i })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Outcome advisory checks")).toHaveTextContent("co1");
    expect(screen.getByText("Consider a more observable verb.")).toBeVisible();
  });

  it("edits, adds, reorders, confirms removal, and submits one complete typed decision", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(<OutcomesEditor {...props({ onSave })} />);

    const statement = screen.getByLabelText("Outcome statement for co1");
    await user.clear(statement);
    await user.type(statement, "Create a healthy indoor herb growing plan.");
    const evidence = screen.getByLabelText("Evidence of learning for co1");
    await user.clear(evidence);
    await user.type(evidence, "Learner produces and justifies a complete growing plan.");
    await user.selectOptions(screen.getByLabelText("Cognitive level for co1"), "create");
    await user.selectOptions(screen.getByLabelText("Priority for co1"), "optional");
    expect(screen.getByRole("status")).toHaveTextContent("Unsaved changes");

    await user.click(screen.getByRole("button", { name: "+ Add Outcome" }));
    const newStatement = screen.getByLabelText("Outcome statement for new Outcome 3");
    expect(newStatement).toHaveFocus();
    await user.type(newStatement, "Analyze symptoms of an unhealthy indoor herb.");
    await user.type(
      screen.getByLabelText("Evidence of learning for new Outcome 3"),
      "Learner diagnoses a scenario and recommends one next action.",
    );
    await user.selectOptions(screen.getByLabelText("Cognitive level for new Outcome 3"), "analyze");
    await user.selectOptions(screen.getByLabelText("Priority for new Outcome 3"), "core");
    await user.click(screen.getByRole("button", { name: "Move new Outcome 3 up" }));

    await user.click(screen.getByRole("button", { name: "Remove co2" }));
    expect(screen.getByRole("dialog", { name: "Remove this Outcome?" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Remove Outcome" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Keep Outcome" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Keep Outcome" }));
    expect(screen.getByLabelText("Outcome statement for co2")).toBeVisible();
    await waitFor(() => expect(screen.getByRole("button", { name: "Remove co2" })).toHaveFocus());
    await user.click(screen.getByRole("button", { name: "Remove co2" }));
    await user.click(screen.getByRole("button", { name: "Remove Outcome" }));
    expect(screen.queryByLabelText("Outcome statement for co2")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("Outcome statement for new Outcome 2")).toHaveFocus());

    await user.click(screen.getByRole("button", { name: "Save Outcomes draft" }));

    expect(onSave).toHaveBeenCalledWith({
      selectedIds: ["co1"],
      edits: {
        co1: {
          statement: "Create a healthy indoor herb growing plan.",
          evidence: "Learner produces and justifies a complete growing plan.",
          cognitiveLevel: "create",
          priority: "optional",
        },
      },
      additions: [{
        clientKey: "new_1",
        statement: "Analyze symptoms of an unhealthy indoor herb.",
        evidence: "Learner diagnoses a scenario and recommends one next action.",
        cognitiveLevel: "analyze",
        priority: "core",
      }],
      priorityOrder: ["co1", "new_1"],
    });
  });

  it("validates fields accessibly, focuses the summary, and locks duplicate submission while busy", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    const view = render(<OutcomesEditor {...props({ onSave })} />);

    expect(screen.getByRole("status")).toHaveTextContent("Matches saved draft");
    expect(screen.getByRole("button", { name: "Save Outcomes draft" })).toBeDisabled();
    await user.clear(screen.getByLabelText("Outcome statement for co1"));
    await user.clear(screen.getByLabelText("Evidence of learning for co1"));
    await user.click(screen.getByRole("button", { name: "Save Outcomes draft" }));

    const summary = screen.getByRole("alert");
    expect(summary).toHaveFocus();
    expect(screen.getByLabelText("Outcome statement for co1")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Evidence of learning for co1")).toHaveAttribute("aria-invalid", "true");
    expect(onSave).not.toHaveBeenCalled();

    view.rerender(<OutcomesEditor {...props({ busy: true, onSave })} />);
    expect(screen.getByRole("button", { name: "Saving draft…" })).toBeDisabled();
    expect(screen.getByLabelText("Outcome statement for co1")).toBeDisabled();
  });

  it("places structured server validation beside the affected canonical field", () => {
    render(<OutcomesEditor {...props({
      serverError: "Evidence cannot be blank.",
      serverIssues: [{
        code: "empty_evidence",
        message: "Evidence cannot be blank.",
        outcomeId: "co1",
        field: "evidence",
      }],
    })} />);

    expect(screen.getByLabelText("Evidence of learning for co1")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getAllByText("Evidence cannot be blank.").length).toBeGreaterThanOrEqual(1);
  });

  it("cancels local changes back to canonical state", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(<OutcomesEditor {...props({ onCancel })} />);

    const statement = screen.getByLabelText("Outcome statement for co1");
    await user.clear(statement);
    await user.type(statement, "A local change that should be discarded.");
    await user.click(screen.getByRole("button", { name: "Cancel changes" }));

    expect(statement).toHaveValue(outcomes[0].statement);
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("preserves local edits across a conflict until the operator chooses the latest version", async () => {
    const user = userEvent.setup();
    const onResolveConflict = vi.fn();
    const latest = [{ ...outcomes[0], statement: "The newer server Outcome statement." }, outcomes[1]];
    render(<ConflictHarness latest={latest} onResolveConflict={onResolveConflict} />);
    const statement = screen.getByLabelText("Outcome statement for co1");
    await user.clear(statement);
    await user.type(statement, "My local Outcome statement.");

    await user.click(screen.getByRole("button", { name: "Simulate concurrent update" }));

    expect(screen.getByLabelText("Outcome statement for co1")).toHaveValue("My local Outcome statement.");
    expect(screen.getByRole("button", { name: "Save Outcomes draft" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Use latest server version" }));
    expect(screen.getByLabelText("Outcome statement for co1")).toHaveValue("The newer server Outcome statement.");
    expect(onResolveConflict).toHaveBeenCalledWith("latest");
  });

  it("rebases explicit local field edits when the operator keeps them against the latest version", async () => {
    const user = userEvent.setup();
    const onResolveConflict = vi.fn();
    const latest = [
      { ...outcomes[0], statement: "The server changed this statement." },
      outcomes[1],
      {
        id: "co3",
        statement: "Evaluate a growing location.",
        evidence: "Learner compares two locations.",
        cognitiveLevel: "evaluate" as const,
        priority: "supporting" as const,
      },
    ];
    render(<ConflictHarness latest={latest} onResolveConflict={onResolveConflict} />);
    const evidence = screen.getByLabelText("Evidence of learning for co1");
    await user.clear(evidence);
    await user.type(evidence, "My local evidence description.");
    await user.click(screen.getByRole("button", { name: "Simulate concurrent update" }));
    await user.click(screen.getByRole("button", { name: "Keep my edits against latest" }));

    expect(screen.getByLabelText("Outcome statement for co1")).toHaveValue("The server changed this statement.");
    expect(screen.getByLabelText("Evidence of learning for co1")).toHaveValue("My local evidence description.");
    expect(screen.getByLabelText("Outcome statement for co3")).toBeVisible();
    expect(onResolveConflict).toHaveBeenCalledWith("keep");
  });

  it("requires explicit resolution when local and server edits overlap", async () => {
    const user = userEvent.setup();
    const latest = [{ ...outcomes[0], statement: "The server changed this statement." }, outcomes[1]];
    render(<ConflictHarness latest={latest} onResolveConflict={vi.fn()} />);
    const statement = screen.getByLabelText("Outcome statement for co1");
    await user.clear(statement);
    await user.type(statement, "My local Outcome statement.");
    await user.click(screen.getByRole("button", { name: "Simulate concurrent update" }));
    await user.click(screen.getByRole("button", { name: "Keep my edits against latest" }));

    expect(screen.getByText(/Resolve 1 overlapping server change/)).toBeVisible();
    expect(statement).toHaveValue("My local Outcome statement.");
    expect(statement).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("button", { name: "Save Outcomes draft" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Keep my statement" }));
    expect(statement).toHaveValue("My local Outcome statement.");
    expect(statement).not.toHaveAttribute("aria-invalid");
    expect(screen.getByRole("button", { name: "Save Outcomes draft" })).toBeEnabled();
  });

  it("reports semantic dirty state to the workspace navigation guard", async () => {
    const user = userEvent.setup();
    const onDirtyChange = vi.fn();
    render(<OutcomesEditor {...props({ onDirtyChange })} />);

    await waitFor(() => expect(onDirtyChange).toHaveBeenLastCalledWith(false));
    await user.type(screen.getByLabelText("Outcome statement for co1"), " revised");
    await waitFor(() => expect(onDirtyChange).toHaveBeenLastCalledWith(true));
  });

  it("preserves local additions and removals without restoring server-deleted Outcomes", async () => {
    const user = userEvent.setup();
    const latest: Outcome[] = [{
      id: "co3",
      statement: "Evaluate a growing location.",
      evidence: "Learner compares two locations.",
      cognitiveLevel: "evaluate",
      priority: "supporting",
    }];
    render(<ConflictHarness latest={latest} onResolveConflict={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "+ Add Outcome" }));
    await user.type(
      screen.getByLabelText("Outcome statement for new Outcome 3"),
      "Create a local herb care plan.",
    );
    await user.type(
      screen.getByLabelText("Evidence of learning for new Outcome 3"),
      "Learner produces a complete care plan.",
    );
    await user.click(screen.getByRole("button", { name: "Remove co1" }));
    await user.click(screen.getByRole("button", { name: "Remove Outcome" }));
    await user.clear(screen.getByLabelText("Outcome statement for co2"));
    await user.type(screen.getByLabelText("Outcome statement for co2"), "A local edit.");

    await user.click(screen.getByRole("button", { name: "Simulate concurrent update" }));
    await user.click(screen.getByRole("button", { name: "Keep my edits against latest" }));

    expect(screen.queryByLabelText("Outcome statement for co1")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Outcome statement for co2")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Outcome statement for co3")).toBeVisible();
    expect(screen.getByDisplayValue("Create a local herb care plan.")).toBeVisible();
  });

  it("requires an explicit choice when both sides changed canonical order", async () => {
    const user = userEvent.setup();
    const third: Outcome = {
      id: "co3",
      statement: "Evaluate a growing location.",
      evidence: "Learner compares two locations.",
      cognitiveLevel: "evaluate",
      priority: "supporting",
    };
    const initial = [...outcomes, third];
    const latest = [outcomes[1], outcomes[0], third];
    render(<ConflictHarness initial={initial} latest={latest} onResolveConflict={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Move co3 up" }));
    await user.click(screen.getByRole("button", { name: "Simulate concurrent update" }));
    await user.click(screen.getByRole("button", { name: "Keep my edits against latest" }));

    expect(screen.getByText(/both changed display order/i)).toBeVisible();
    expect(screen.getByRole("button", { name: "Save Outcomes draft" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Use server order" }));
    expect(screen.queryByText(/both changed display order/i)).not.toBeInTheDocument();
    expect(screen.getAllByLabelText(/Outcome statement for/).map((field) => field.getAttribute("aria-label"))).toEqual([
      "Outcome statement for co2",
      "Outcome statement for co1",
      "Outcome statement for co3",
    ]);
  });
});
