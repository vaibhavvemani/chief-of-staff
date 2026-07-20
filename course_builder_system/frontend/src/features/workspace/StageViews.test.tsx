import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { demoWorkspace } from "../../data/demo";
import type { Workspace } from "../../types";
import { StageView } from "./StageViews";

describe("truthful lifecycle controls", () => {
  it("distinguishes explicit Brief answers from accepted defaults", () => {
    render(<StageView stage="brief" workspace={demoWorkspace} />);

    const provenance = screen.getByLabelText("Brief answer provenance");
    expect(provenance).toHaveTextContent(/1 provided directly/i);
    expect(provenance).toHaveTextContent(/3 defaults accepted/i);
    expect(screen.getAllByText("Accepted default")).toHaveLength(3);
  });

  it("labels a saved incomplete Brief as input required and exposes all direct-edit groups", () => {
    const onEditBrief = vi.fn();
    const workspace: Workspace = {
      ...demoWorkspace,
      stages: demoWorkspace.stages.map((stage) => stage.slug === "brief"
        ? { ...stage, status: "needs_input" }
        : stage),
    };

    render(
      <StageView
        stage="brief"
        workspace={workspace}
        onEditBrief={onEditBrief}
      />,
    );

    expect(screen.getByText("Input required", { exact: true })).toBeInTheDocument();
    const requirements = screen.getByRole("button", {
      name: "Adjust additional requirements and materials in Course Brief",
    });
    fireEvent.click(requirements);
    expect(onEditBrief).toHaveBeenCalledWith("requirements");
  });

  it("does not expose unsupported content repairs or review mutations", () => {
    render(
      <StageView
        stage="content"
        workspace={demoWorkspace}
        contentCapabilities={{ review: false, revise: false, repair: false }}
      />,
    );

    expect(screen.queryByRole("button", { name: /find better evidence/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /revise with approved evidence/i })).not.toBeInTheDocument();
    expect(screen.getByText(/no automated repair is registered/i)).toBeInTheDocument();
    expect(screen.getByText(/review decisions are unavailable/i)).toBeInTheDocument();
  });

  it("offers the registered scoped asset revision only when projected", () => {
    const onContentAction = vi.fn();
    render(
      <StageView
        stage="content"
        workspace={demoWorkspace}
        contentCapabilities={{ review: true, revise: true, repair: false }}
        onContentAction={onContentAction}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /revise with approved evidence/i }));
    expect(onContentAction).toHaveBeenCalledWith(
      "revise",
      expect.objectContaining({ id: "m1_s4_cc" }),
      expect.objectContaining({ id: "cl2" }),
    );
    fireEvent.click(screen.getByRole("button", { name: /request scoped revision/i }));
    expect(onContentAction).toHaveBeenLastCalledWith(
      "revise",
      expect.objectContaining({ id: "m1_s4_cc" }),
    );
    expect(screen.queryByRole("button", { name: /find better evidence/i })).not.toBeInTheDocument();
  });

  it("offers the registered bounded source repair independently of scoped revision", () => {
    const onContentAction = vi.fn();
    render(
      <StageView
        stage="content"
        workspace={demoWorkspace}
        contentCapabilities={{ review: true, revise: false, repair: true }}
        onContentAction={onContentAction}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /find better evidence/i }));
    expect(onContentAction).toHaveBeenCalledWith(
      "source_repair",
      expect.objectContaining({ id: "m1_s4_cc" }),
      expect.objectContaining({ id: "cl2" }),
    );
    expect(screen.queryByRole("button", { name: /revise with approved evidence/i })).not.toBeInTheDocument();
  });

  it("keeps source mutation controls disabled without a projected source decision", () => {
    render(<StageView stage="research" workspace={demoWorkspace} />);

    const sourceButtons = [
      ...screen.getAllByRole("button", { name: "Remove" }),
      ...screen.getAllByRole("button", { name: "Select" }),
    ];
    expect(sourceButtons.length).toBeGreaterThan(0);
    sourceButtons.forEach((button) => expect(button).toBeDisabled());
  });

  it("labels package inspection truthfully instead of fabricating file contents", () => {
    render(<StageView stage="package" workspace={demoWorkspace} />);

    expect(screen.getByText(/an inline renderer is not implemented/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open raw file/i })).toHaveAttribute("href", expect.stringContaining("/outputs/"));
  });

  it("renders Outcomes editing only when the backend-projected edit capability is wired", () => {
    const onStartOutcomesEdit = vi.fn();
    const workspace: Workspace = {
      ...demoWorkspace,
      outcomeAdvisories: [{
        code: "weak_evidence",
        outcomeId: "co2",
        field: "evidence",
        reason: "Describe a more observable learner product.",
        level: "advisory",
      }],
    };
    const view = render(<StageView stage="outcomes" workspace={workspace} />);

    expect(screen.queryByRole("button", { name: "Edit Outcomes" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Outcome advisory checks")).toHaveTextContent("co2");

    view.rerender(
      <StageView
        stage="outcomes"
        workspace={workspace}
        onStartOutcomesEdit={onStartOutcomesEdit}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Edit Outcomes" }));
    expect(onStartOutcomesEdit).toHaveBeenCalledOnce();
  });

  it("routes the controlled Outcomes edit state and save callback", () => {
    const onSaveOutcomes = vi.fn();
    render(
      <StageView
        stage="outcomes"
        workspace={demoWorkspace}
        outcomesEditing
        onStartOutcomesEdit={vi.fn()}
        onSaveOutcomes={onSaveOutcomes}
      />,
    );

    fireEvent.change(screen.getByLabelText("Outcome statement for co1"), {
      target: { value: "Explain a revised set of core coffee concepts." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save Outcomes draft" }));

    expect(onSaveOutcomes).toHaveBeenCalledWith(expect.objectContaining({
      selectedIds: ["co1", "co2", "co3", "co4"],
      edits: { co1: { statement: "Explain a revised set of core coffee concepts." } },
      priorityOrder: ["co1", "co2", "co3", "co4"],
    }));
  });

  it("exposes Course Model editing only when the backend edit action is wired", () => {
    const onStartCourseModelEdit = vi.fn();
    const view = render(<StageView stage="course-model" workspace={demoWorkspace} />);
    expect(screen.queryByRole("button", { name: "Edit Course Model" })).not.toBeInTheDocument();
    view.rerender(<StageView stage="course-model" workspace={demoWorkspace} onStartCourseModelEdit={onStartCourseModelEdit} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit Course Model" }));
    expect(onStartCourseModelEdit).toHaveBeenCalledOnce();
  });
});
