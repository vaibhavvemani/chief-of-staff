import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { BriefQuestionRound as BriefQuestionRoundData, BriefQuestionRoundKind, BriefQuestionSpec } from "../../types";
import { BriefQuestionRound } from "./BriefQuestionRound";

function question(overrides: Partial<BriefQuestionSpec> & Pick<BriefQuestionSpec, "id" | "field" | "prompt">): BriefQuestionSpec {
  return {
    rationale: `Why ${overrides.field} matters.`,
    answerType: "free_text",
    options: [],
    required: true,
    allowSkip: false,
    visibility: {},
    ...overrides,
  };
}

function round(questions: BriefQuestionSpec[], roundKind: BriefQuestionRoundKind = "mandatory"): BriefQuestionRoundData {
  return {
    questions,
    roundKind,
    gapAnalysis: [],
    intakeState: {
      explicitFields: [],
      acceptedDefaultFields: [],
      unresolvedRequiredFields: questions.filter((item) => item.required).map((item) => item.field),
      answeredQuestionIds: [],
      lastGapAnalysis: [],
    },
    checksum: "brief-checksum",
  };
}

describe("BriefQuestionRound", () => {
  it("renders the backend-selected mandatory round and submits typed values", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(
      <BriefQuestionRound
        round={round([
          question({ id: "brief_audience", field: "audience", prompt: "Who is this course for?" }),
          question({ id: "brief_level", field: "level", prompt: "What level should the course target?", answerType: "single_choice", options: ["beginner", "advanced"] }),
          question({ id: "brief_topics", field: "must_have_topics", prompt: "Which topics are required?", answerType: "multiple_choice", options: ["brewing", "troubleshooting"] }),
          question({ id: "brief_sessions", field: "sessions", prompt: "How many sessions?", answerType: "number" }),
          question({ id: "brief_duration", field: "duration", prompt: "How much learning time is available?", answerType: "duration", defaultValue: "3 hours" }),
        ])}
        busy={false}
        onSubmit={onSubmit}
      />,
    );

    expect(document.querySelectorAll("[data-question-id]")).toHaveLength(5);
    expect(screen.getByText("5 backend-selected questions")).toBeVisible();
    expect(screen.getByText("Why audience matters.")).toBeVisible();

    await user.type(screen.getByLabelText("Who is this course for?"), "Home coffee beginners");
    await user.click(screen.getByRole("radio", { name: "Beginner" }));
    await user.click(screen.getByRole("checkbox", { name: "Troubleshooting" }));
    await user.type(screen.getByLabelText("How many sessions?"), "4");
    await user.click(screen.getByRole("button", { name: /Accept suggested default for How much learning time is available\?: 3 hours/ }));
    await user.click(screen.getByRole("button", { name: "Save answers and continue" }));

    expect(onSubmit).toHaveBeenCalledWith([
      { questionId: "brief_audience", value: "Home coffee beginners" },
      { questionId: "brief_level", value: "beginner" },
      { questionId: "brief_topics", value: ["troubleshooting"] },
      { questionId: "brief_sessions", value: 4 },
      { questionId: "brief_duration", acceptDefault: true },
    ]);
  });

  it("requires explicit default acceptance and optional skipping, then submits confirmation", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(
      <BriefQuestionRound
        round={round([
          question({ id: "brief_language", field: "language", prompt: "What language should the course use?", defaultValue: "English" }),
          question({ id: "brief_tools", field: "tools", prompt: "Are special tools required?", required: false, allowSkip: true }),
          question({ id: "brief_confirm", field: "confirmed", prompt: "Confirm the final direction?", answerType: "confirmation" }),
        ], "clarification")}
        busy={false}
        serverError="The previous answer used a stale checksum."
        onSubmit={onSubmit}
      />,
    );

    expect(screen.getByRole("heading", { name: "Resolve the remaining Brief gaps" })).toBeVisible();
    expect(screen.getByText(/stale checksum/i)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Save answers and continue" }));

    const summary = screen.getAllByRole("alert").find((item) => item.classList.contains("question-error-summary"));
    expect(summary).toHaveFocus();
    expect(screen.getByLabelText("What language should the course use?")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByLabelText("Are special tools required?")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("radio", { name: "No" })).toHaveAttribute("aria-invalid", "true");
    expect(onSubmit).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: /Accept suggested default for What language should the course use\?: English/ }));
    await user.click(screen.getByRole("button", { name: "Skip Are special tools required?" }));
    await user.click(screen.getByRole("radio", { name: "No" }));
    await user.click(screen.getByRole("button", { name: "Save answers and continue" }));

    expect(onSubmit).toHaveBeenCalledWith([
      { questionId: "brief_language", acceptDefault: true },
      { questionId: "brief_tools", skip: true },
      { questionId: "brief_confirm", value: false },
    ]);
  });

  it("renders a conditional question exactly when the backend includes it", () => {
    render(
      <BriefQuestionRound
        round={round([
          question({
            id: "brief_live_teaching_constraints",
            field: "live_teaching_constraints",
            prompt: "What live-teaching constraints apply?",
            visibility: { modality: ["live", "blended"] },
          }),
        ])}
        busy={false}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("What live-teaching constraints apply?")).toBeVisible();
  });
});
