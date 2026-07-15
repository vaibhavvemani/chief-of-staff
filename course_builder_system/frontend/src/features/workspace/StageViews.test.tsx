import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { demoWorkspace } from "../../data/demo";
import { StageView } from "./StageViews";

describe("truthful lifecycle controls", () => {
  it("does not expose unsupported content repairs or review mutations", () => {
    render(
      <StageView
        stage="content"
        workspace={demoWorkspace}
        contentCapabilities={{ review: false, revise: false }}
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
        contentCapabilities={{ review: true, revise: true }}
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
});
