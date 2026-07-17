import { FormEvent, useEffect, useRef, useState } from "react";
import type {
  BriefQuestionAnswer,
  BriefQuestionRound as BriefQuestionRoundData,
  BriefQuestionSpec,
  QuestionAnswerValue,
} from "../../types";

interface DraftAnswer {
  value?: QuestionAnswerValue;
  choice?: "default" | "skip";
}

interface BriefQuestionRoundProps {
  round: BriefQuestionRoundData;
  busy: boolean;
  serverError?: string;
  onSubmit: (answers: BriefQuestionAnswer[]) => void;
}

function displayValue(value: QuestionAnswerValue): string {
  if (Array.isArray(value)) return value.map(displayOption).join(", ");
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function displayOption(value: string): string {
  const normalized = value.replaceAll("_", " ");
  return normalized ? normalized[0].toUpperCase() + normalized.slice(1) : value;
}

function hasValue(value: QuestionAnswerValue | undefined): boolean {
  if (typeof value === "string") return Boolean(value.trim());
  if (Array.isArray(value)) return value.length > 0;
  return value !== undefined && value !== null;
}

function QuestionControl({
  question,
  draft,
  describedBy,
  invalid,
  onValue,
}: {
  question: BriefQuestionSpec;
  draft: DraftAnswer;
  describedBy: string;
  invalid: boolean;
  onValue: (value: QuestionAnswerValue) => void;
}) {
  if (question.answerType === "single_choice") {
    return (
      <div className="question-options question-options-single">
        {question.options.map((option) => (
          <label key={option}>
            <input
              type="radio"
              name={question.id}
              value={option}
              checked={draft.choice == null && draft.value === option}
              onChange={() => onValue(option)}
              aria-describedby={describedBy}
              aria-invalid={invalid || undefined}
            />
            <span>{displayOption(option)}</span>
          </label>
        ))}
      </div>
    );
  }

  if (question.answerType === "multiple_choice") {
    const selected = Array.isArray(draft.value) ? draft.value : [];
    return (
      <div className="question-options question-options-multiple">
        {question.options.map((option) => (
          <label key={option}>
            <input
              type="checkbox"
              value={option}
              checked={draft.choice == null && selected.includes(option)}
              onChange={(event) => onValue(
                event.target.checked
                  ? [...selected, option]
                  : selected.filter((item) => item !== option),
              )}
              aria-describedby={describedBy}
              aria-invalid={invalid || undefined}
            />
            <span>{displayOption(option)}</span>
          </label>
        ))}
      </div>
    );
  }

  if (question.answerType === "confirmation") {
    return (
      <div className="question-options question-options-single">
        {[true, false].map((value) => (
          <label key={String(value)}>
            <input
              type="radio"
              name={question.id}
              checked={draft.choice == null && draft.value === value}
              onChange={() => onValue(value)}
              aria-describedby={describedBy}
              aria-invalid={invalid || undefined}
            />
            <span>{value ? "Yes" : "No"}</span>
          </label>
        ))}
      </div>
    );
  }

  if (question.answerType === "number") {
    return (
      <input
        className="question-input"
        type="number"
        value={draft.choice == null && typeof draft.value === "string" ? draft.value : typeof draft.value === "number" ? draft.value : ""}
        onChange={(event) => onValue(event.target.value)}
        aria-label={question.prompt}
        aria-describedby={describedBy}
        aria-invalid={invalid || undefined}
      />
    );
  }

  if (question.answerType === "duration") {
    return (
      <input
        className="question-input"
        type="text"
        value={draft.choice == null && typeof draft.value === "string" ? draft.value : ""}
        onChange={(event) => onValue(event.target.value)}
        aria-label={question.prompt}
        aria-describedby={describedBy}
        aria-invalid={invalid || undefined}
        placeholder="For example, 3 hours"
      />
    );
  }

  return (
    <textarea
      className="question-input"
      rows={3}
      value={draft.choice == null && typeof draft.value === "string" ? draft.value : ""}
      onChange={(event) => onValue(event.target.value)}
      aria-label={question.prompt}
      aria-describedby={describedBy}
      aria-invalid={invalid || undefined}
    />
  );
}

export function BriefQuestionRound({ round, busy, serverError, onSubmit }: BriefQuestionRoundProps) {
  const questions = round.questions;
  const roundKey = `${round.checksum}:${questions.map((question) => question.id).join(":")}`;
  const [drafts, setDrafts] = useState<Record<string, DraftAnswer>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const errorSummaryRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setDrafts({});
    setErrors({});
  }, [roundKey]);

  useEffect(() => {
    if (Object.keys(errors).length) errorSummaryRef.current?.focus();
  }, [errors]);

  const updateDraft = (questionId: string, next: DraftAnswer) => {
    setDrafts((current) => ({ ...current, [questionId]: next }));
    setErrors((current) => {
      if (!(questionId in current)) return current;
      const nextErrors = { ...current };
      delete nextErrors[questionId];
      return nextErrors;
    });
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const nextErrors: Record<string, string> = {};
    const answers: BriefQuestionAnswer[] = [];

    questions.forEach((question) => {
      const draft = drafts[question.id] ?? {};
      if (draft.choice === "default") {
        answers.push({ questionId: question.id, acceptDefault: true });
        return;
      }
      if (draft.choice === "skip") {
        answers.push({ questionId: question.id, skip: true });
        return;
      }
      if (!hasValue(draft.value)) {
        if (question.required || question.allowSkip) {
          nextErrors[question.id] = question.allowSkip
            ? "Answer this question or explicitly choose Skip."
            : question.defaultValue !== undefined
              ? "Provide an answer or explicitly accept the suggested default."
              : "This question requires an answer.";
        }
        return;
      }
      const value = question.answerType === "number" && typeof draft.value === "string"
        ? Number(draft.value)
        : draft.value;
      answers.push({ questionId: question.id, value });
    });

    if (Object.keys(nextErrors).length) {
      setErrors(nextErrors);
      return;
    }
    onSubmit(answers);
  };

  const clarification = round.roundKind === "clarification";
  return (
    <section className="brief-intake-panel" aria-labelledby="brief-intake-title">
      <div className="brief-intake-heading">
        <div>
          <span className="eyebrow">{clarification ? "Focused clarification" : "Guided Brief intake"}</span>
          <h2 id="brief-intake-title">{clarification ? "Resolve the remaining Brief gaps" : "Confirm the course direction"}</h2>
          <p>{clarification
            ? "These questions come from the current Brief gaps. Your earlier answers remain saved."
            : "Answer this short round. Suggested defaults count only when you explicitly accept them."}</p>
        </div>
        <span className="question-count">{questions.length} backend-selected question{questions.length === 1 ? "" : "s"}</span>
      </div>

      {round.gapAnalysis.length ? (
        <div className="gap-analysis-summary" aria-label="Brief gap analysis">
          <strong>Why this round appeared</strong>
          {round.gapAnalysis.map((gap) => <p key={gap.id}>{gap.message}</p>)}
        </div>
      ) : null}

      <form onSubmit={submit} noValidate>
        {Object.keys(errors).length ? (
          <div className="question-error-summary" role="alert" tabIndex={-1} ref={errorSummaryRef}>
            <strong>Review {Object.keys(errors).length} question{Object.keys(errors).length === 1 ? "" : "s"} before continuing.</strong>
            <p>Each required answer, accepted default, or optional skip must be explicit.</p>
          </div>
        ) : null}
        {serverError ? <div className="question-server-error" role="alert"><strong>Answers were not saved.</strong> {serverError}</div> : null}

        <div className="question-list">
          {questions.map((question, index) => {
            const draft = drafts[question.id] ?? {};
            const rationaleId = `${question.id}-rationale`;
            const errorId = `${question.id}-error`;
            const describedBy = errors[question.id] ? `${rationaleId} ${errorId}` : rationaleId;
            return (
              <fieldset
                className={`question-card ${errors[question.id] ? "question-card-error" : ""}`}
                key={question.id}
                data-question-id={question.id}
                disabled={busy}
              >
                <legend><span>{String(index + 1).padStart(2, "0")}</span>{question.prompt}</legend>
                <p className="question-rationale" id={rationaleId}><strong>Why this matters:</strong> {question.rationale}</p>
                <QuestionControl
                  question={question}
                  draft={draft}
                  describedBy={describedBy}
                  invalid={Boolean(errors[question.id])}
                  onValue={(value) => updateDraft(question.id, { value })}
                />
                <div className="question-resolution-actions">
                  {question.defaultValue !== undefined ? (
                    <button
                      type="button"
                      className={draft.choice === "default" ? "selected" : ""}
                      aria-pressed={draft.choice === "default"}
                      aria-label={`Accept suggested default for ${question.prompt}: ${displayValue(question.defaultValue)}`}
                      onClick={() => updateDraft(question.id, { choice: "default" })}
                    >
                      <span aria-hidden="true">✓</span>
                      <span><strong>Accept suggested default</strong><small>{displayValue(question.defaultValue)}</small></span>
                    </button>
                  ) : null}
                  {question.allowSkip ? (
                    <button
                      type="button"
                      className={draft.choice === "skip" ? "selected" : ""}
                      aria-pressed={draft.choice === "skip"}
                      aria-label={`Skip ${question.prompt}`}
                      onClick={() => updateDraft(question.id, { choice: "skip" })}
                    >
                      <span aria-hidden="true">→</span>
                      <span><strong>Skip this optional question</strong><small>No value will be assumed.</small></span>
                    </button>
                  ) : null}
                </div>
                {errors[question.id] ? <p className="question-error" id={errorId}>{errors[question.id]}</p> : null}
              </fieldset>
            );
          })}
        </div>
        <div className="brief-intake-footer">
          <p>Answers are saved to the Brief after every round and will survive refresh.</p>
          <button className="button button-primary" type="submit" disabled={busy || questions.length === 0}>
            {busy ? "Saving answers…" : "Save answers and continue"}<span aria-hidden="true">→</span>
          </button>
        </div>
      </form>
    </section>
  );
}
