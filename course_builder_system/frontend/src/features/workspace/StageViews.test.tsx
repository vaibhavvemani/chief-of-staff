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
        contentCapabilities={{ review: false, revise: false, contentRepair: false, repair: false }}
      />,
    );

    expect(screen.queryByRole("button", { name: /find better evidence/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /revise with approved evidence/i })).not.toBeInTheDocument();
    expect(screen.getByText(/no automated repair is registered/i)).toBeInTheDocument();
    expect(screen.getByText(/review decisions are unavailable/i)).toBeInTheDocument();
  });

  it("routes verifier repair through the typed command while keeping generic revision separate", () => {
    const onContentAction = vi.fn();
    render(
      <StageView
        stage="content"
        workspace={demoWorkspace}
        contentCapabilities={{ review: true, revise: true, contentRepair: true, repair: false }}
        onContentAction={onContentAction}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /revise with approved evidence/i }));
    expect(onContentAction).toHaveBeenCalledWith(
      "repair_existing",
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

  it("offers both bounded repair strategies independently of generic scoped revision", () => {
    const onContentAction = vi.fn();
    render(
      <StageView
        stage="content"
        workspace={demoWorkspace}
        contentCapabilities={{ review: true, revise: false, contentRepair: true, repair: true }}
        onContentAction={onContentAction}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /find better evidence/i }));
    expect(onContentAction).toHaveBeenCalledWith(
      "source_repair",
      expect.objectContaining({ id: "m1_s4_cc" }),
      expect.objectContaining({ id: "cl2" }),
    );
    fireEvent.click(screen.getByRole("button", { name: /revise with approved evidence/i }));
    expect(onContentAction).toHaveBeenLastCalledWith(
      "repair_existing",
      expect.objectContaining({ id: "m1_s4_cc" }),
      expect.objectContaining({ id: "cl2" }),
    );
    expect(screen.queryByRole("button", { name: /request scoped revision/i })).not.toBeInTheDocument();
  });

  it("groups advisory repair findings and shows their current state", () => {
    const workspace: Workspace = {
      ...demoWorkspace,
      contentRepairs: {
        findings: [
          {
            id: "m1_s4_cc:cl2",
            subtopicId: "m1_s4",
            assetId: "m1_s4_cc",
            claimId: "cl2",
            findingId: "cl2",
            text: "The extraction claim lacks supporting evidence.",
            note: "No relevant passage was found.",
            classification: "insufficient_evidence",
            classificationReason: "The assigned source does not cover the claim.",
            recommendedStrategy: "better_evidence",
            blocking: true,
            state: "awaiting_content_repair",
            sourceRepairId: "repair_1",
          },
          {
            id: "m1_s4_cc:cl1",
            subtopicId: "m1_s4",
            assetId: "m1_s4_cc",
            claimId: "cl1",
            findingId: "cl1",
            text: "The passage only partially supports the wording.",
            note: "Human judgment is required.",
            classification: "human_review",
            classificationReason: "Partial support is advisory and nonblocking.",
            recommendedStrategy: null,
            blocking: false,
            state: "ready",
            sourceRepairId: null,
          },
        ],
        groups: {
          likely_content_error: 0,
          missing_attribution: 0,
          insufficient_evidence: 1,
          human_review: 1,
        },
        hardBlockerTotal: 1,
        partialTotal: 1,
        readyForPackage: false,
      },
    };

    render(
      <StageView
        stage="content"
        workspace={workspace}
        contentCapabilities={{ review: true, revise: false, contentRepair: true, repair: true }}
      />,
    );

    const queue = screen.getByRole("region", { name: "Content repair queue" });
    expect(queue).toHaveTextContent("Insufficient evidence");
    expect(queue).toHaveTextContent("Human review");
    expect(queue).toHaveTextContent("Awaiting content repair");
    expect(queue).toHaveTextContent("1 blocking · 1 review");
    expect(screen.getByRole("button", {
      name: "Revise with approved evidence for m1_s4_cc, finding cl2",
    })).toBeInTheDocument();
    expect(screen.getByRole("button", {
      name: "Find better evidence for m1_s4_cc, finding cl2",
    })).toBeInTheDocument();
  });

  it("keeps source-less claims and unattributed findings blocking in the review UI", () => {
    const baseAsset = demoWorkspace.content.assets[0];
    const asset = {
      ...baseAsset,
      reviewStatus: "pending" as const,
      claims: [{
        ...baseAsset.claims[0],
        sourceId: null,
        support: "supported" as const,
      }],
      verification: {
        supported: 0,
        partial: 0,
        unsupported: 0,
        ungrounded: 1,
        unattributed: 1,
      },
    };
    const workspace: Workspace = {
      ...demoWorkspace,
      content: { ...demoWorkspace.content, assets: [asset], completed: 1, expected: 1 },
      contentRepairs: {
        findings: [
          {
            id: `${asset.id}:${asset.claims[0].id}`,
            subtopicId: asset.subtopicId,
            assetId: asset.id,
            claimId: asset.claims[0].id,
            findingId: asset.claims[0].id,
            text: asset.claims[0].text,
            note: "No approved source attribution.",
            classification: "missing_attribution",
            classificationReason: "The claim has no approved source.",
            recommendedStrategy: "existing_evidence",
            blocking: true,
            state: "ready",
          },
          {
            id: `${asset.id}:unattributed_1`,
            subtopicId: asset.subtopicId,
            assetId: asset.id,
            claimId: null,
            findingId: "unattributed_1",
            text: "A second factual statement is not attributed.",
            note: "The verifier found an unattributed statement.",
            classification: "missing_attribution",
            classificationReason: "No approved source attribution is attached.",
            recommendedStrategy: "existing_evidence",
            blocking: true,
            state: "ready",
          },
        ],
        groups: {
          likely_content_error: 0,
          missing_attribution: 2,
          insufficient_evidence: 0,
          human_review: 0,
        },
        hardBlockerTotal: 2,
        partialTotal: 0,
        readyForPackage: false,
      },
    };

    render(
      <StageView
        stage="content"
        workspace={workspace}
        contentCapabilities={{ review: true, revise: false, contentRepair: true, repair: true }}
        onContentAction={vi.fn()}
      />,
    );

    expect(screen.getByText("2 blocking verification findings")).toBeInTheDocument();
    expect(screen.getByText("No ground").parentElement).toHaveTextContent("2");
    expect(screen.getByText("1 to inspect")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Mark asset reviewed" })).toBeDisabled();
    expect(screen.getByText("2 blocking findings must be repaired first.")).toBeInTheDocument();
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
