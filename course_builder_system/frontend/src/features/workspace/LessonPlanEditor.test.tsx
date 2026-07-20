import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Workspace } from "../../types";
import { LessonPlanEditor, type LessonPlanEditorProps } from "./LessonPlanEditor";

const lessonPlan: Workspace["lessonPlan"] = {
  sessions: [
    {
      id: "sess1",
      order: 1,
      title: "Foundations",
      durationMinutes: 40,
      covers: [
        { subtopicId: "s1", mode: "live", talkingPoints: ["Teach first."] },
        { subtopicId: "s2", mode: "live", talkingPoints: ["Teach second."] },
      ],
    },
    {
      id: "sess2",
      order: 2,
      title: "Practice",
      durationMinutes: 40,
      covers: [
        { subtopicId: "s3", mode: "live", talkingPoints: ["Practise."] },
        { subtopicId: "s4", mode: "live", talkingPoints: ["Troubleshoot."] },
      ],
    },
  ],
  totalDurationMinutes: 80,
  expectedSubtopicIds: ["s1", "s2", "s3", "s4"],
  coveredSubtopicIds: ["s1", "s2", "s3", "s4"],
  constraints: {
    maxSessionHours: 2,
    defaultMode: "live",
    calendarDates: [],
    instructorCount: null,
    deliveryPlatform: null,
  },
  unresolvedConstraints: ["calendar_dates", "instructor_count", "delivery_platform"],
  affectedSessionIds: [],
};

function props(overrides: Partial<LessonPlanEditorProps> = {}): LessonPlanEditorProps {
  return {
    lessonPlan,
    subtopicNames: {
      s1: "First topic",
      s2: "Second topic",
      s3: "Practice topic",
      s4: "Troubleshooting topic",
    },
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

describe("LessonPlanEditor", () => {
  it("submits exact constraints and a bounded mode operation with affected sessions", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(<LessonPlanEditor {...props({ onSave })} />);

    await user.clear(screen.getByLabelText("Maximum session hours"));
    await user.type(screen.getByLabelText("Maximum session hours"), "0.5");
    await user.selectOptions(
      screen.getByLabelText("Delivery mode for Troubleshooting topic"),
      "self_study",
    );
    await user.type(screen.getByLabelText("Instructor count"), "1");
    await user.type(screen.getByLabelText("Delivery platform"), "Studio classroom");
    await user.type(screen.getByLabelText("Calendar dates"), "2026-08-03{enter}2026-08-10");

    const preview = screen.getByRole("region", { name: "What delivery planning will change" });
    expect(within(preview).getByText("sess2")).toBeVisible();
    expect(within(preview).getByText("Duration regrouping will report exact changed session IDs after save.")).toBeVisible();
    expect(within(preview).getByText("4 subtopics, each exactly once.")).toBeVisible();
    await user.click(screen.getByRole("checkbox", { name: /reviewed the changed constraints/i }));
    await user.click(screen.getByRole("button", { name: "Save Lesson Plan draft" }));

    expect(onSave).toHaveBeenCalledWith({
      constraints: {
        maxSessionHours: 0.5,
        defaultMode: "live",
        calendarDates: ["2026-08-03", "2026-08-10"],
        instructorCount: 1,
        deliveryPlatform: "Studio classroom",
      },
      operations: [{ op: "set_mode", targetId: "s4", value: "self_study" }],
      rationale: "Human Lesson Plan checkpoint.",
    });
  });

  it("builds typed segment placement and session ordering and resets acknowledgement", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(<LessonPlanEditor {...props({ onSave })} />);

    await user.selectOptions(screen.getByLabelText("Session placement for Second topic"), "sess2");
    const acknowledgement = screen.getByRole("checkbox", { name: /reviewed the changed constraints/i });
    await user.click(acknowledgement);
    expect(screen.getByRole("button", { name: "Save Lesson Plan draft" })).toBeEnabled();
    await user.click(screen.getByRole("button", { name: "Move session sess2 earlier" }));
    expect(acknowledgement).not.toBeChecked();
    await user.click(acknowledgement);
    await user.click(screen.getByRole("button", { name: "Save Lesson Plan draft" }));

    expect(onSave.mock.calls[0][0].operations).toEqual([
      { op: "move_segment", targetId: "s2", value: "sess2", position: 1 },
      { op: "reorder_session", sessionIds: ["sess2", "sess1"] },
    ]);
  });

  it("previews only sessions whose modes actually change with a new default", async () => {
    const user = userEvent.setup();
    const mixed = structuredClone(lessonPlan);
    mixed.sessions[1].covers.forEach((cover) => {
      cover.mode = "self_study";
    });
    render(<LessonPlanEditor {...props({ lessonPlan: mixed })} />);

    await user.selectOptions(screen.getByLabelText("Default delivery mode"), "self_study");

    const preview = screen.getByRole("region", { name: "What delivery planning will change" });
    expect(within(preview).getByText("sess1")).toBeVisible();
    expect(within(preview).queryByText("sess2")).not.toBeInTheDocument();
  });

  it("blocks ambiguous max-duration plus layout edits and focuses conflict recovery", async () => {
    const user = userEvent.setup();
    const onResolveConflict = vi.fn();
    render(<LessonPlanEditor {...props({ conflict: true, onResolveConflict })} />);

    const reviewLocal = screen.getByRole("button", { name: "Review local decision again" });
    expect(reviewLocal).toHaveFocus();
    await user.clear(screen.getByLabelText("Maximum session hours"));
    await user.type(screen.getByLabelText("Maximum session hours"), "1");
    await user.click(screen.getByRole("button", { name: "Move session sess2 earlier" }));
    expect(screen.getByText(/Save the maximum-duration change before moving/i)).toBeVisible();
    expect(screen.getByRole("button", { name: "Save Lesson Plan draft" })).toBeDisabled();
    await user.click(reviewLocal);
    expect(onResolveConflict).toHaveBeenCalledWith("reapply");
  });
});
