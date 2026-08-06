import type { UiStatus } from "../types";

/**
 * The nine lifecycle states a director has to tell apart at a glance.
 *
 * Each one carries a unique glyph as well as a unique colour, because the
 * previous scale encoded status in hue alone and collapsed nine states into
 * six treatments: `stale` had no rule at all and rendered identically to
 * `locked`, `ready` matched `awaiting_review`, and `failed` matched
 * `requires_attention`. Glyphs keep the scale readable in greyscale and for
 * colour-blind operators.
 *
 * `hint` answers the only question the operator is actually asking: is this
 * waiting on me, on the agent, or on nothing?
 */
const statusMeta: Record<UiStatus, { label: string; glyph: string; hint: string }> = {
  locked: { label: "Locked", glyph: "·", hint: "Waiting on an earlier stage" },
  needs_input: { label: "Needs input", glyph: "?", hint: "Waiting on your answers" },
  ready: { label: "Ready to run", glyph: "▷", hint: "Ready for you to start" },
  running: { label: "Running", glyph: "◍", hint: "The agent is working" },
  awaiting_review: { label: "Awaiting review", glyph: "◆", hint: "Waiting on your review" },
  approved: { label: "Approved", glyph: "✓", hint: "Done" },
  requires_attention: { label: "Needs attention", glyph: "!", hint: "Blockers to resolve" },
  stale: { label: "Out of date", glyph: "↻", hint: "Needs running again" },
  failed: { label: "Failed", glyph: "✕", hint: "The run failed — retry it" },
};

export function statusLabel(status: UiStatus) {
  return statusMeta[status].label;
}

export function statusHint(status: UiStatus) {
  return statusMeta[status].hint;
}

export function statusGlyph(status: UiStatus) {
  return statusMeta[status].glyph;
}

export function StatusBadge({ status, count }: { status: UiStatus; count?: number }) {
  const meta = statusMeta[status];
  return (
    <span className={`status-badge status-${status}`}>
      <span className="status-mark" aria-hidden="true">
        {meta.glyph}
      </span>
      {meta.label}
      {typeof count === "number" && count > 0 ? (
        <strong className="count-bubble">
          {count}
          <span className="visually-hidden"> items need attention</span>
        </strong>
      ) : null}
    </span>
  );
}

const sourceMeta: Record<string, { label: string; glyph: string }> = {
  approved: { label: "Approved", glyph: "✓" },
  selected: { label: "Selected", glyph: "+" },
  rejected: { label: "Rejected", glyph: "✕" },
  proposed: { label: "Candidate", glyph: "·" },
  unavailable: { label: "Unavailable", glyph: "⊘" },
};

export function SourceStatus({ status }: { status: string }) {
  const normalized = status in sourceMeta ? status : "proposed";
  const meta = sourceMeta[normalized];
  return (
    <span className={`source-status source-${normalized}`}>
      <span aria-hidden="true">{meta.glyph}</span>
      {meta.label}
    </span>
  );
}

/**
 * Verifier outcomes. `unsupported`, `ungrounded` and `unattributed` are hard
 * blockers; `partial` needs human judgement but does not block. The labels say
 * which is which instead of leaving the operator to infer it from a raw enum.
 */
const verificationMeta: Record<string, { label: string; glyph: string }> = {
  supported: { label: "Supported", glyph: "✓" },
  partial: { label: "Partly supported", glyph: "◐" },
  unsupported: { label: "Unsupported", glyph: "✕" },
  ungrounded: { label: "No source", glyph: "✕" },
  unattributed: { label: "Unattributed", glyph: "✕" },
};

export function VerificationBadge({ support }: { support: string }) {
  const normalized = support in verificationMeta ? support : "partial";
  const meta = verificationMeta[normalized];
  return (
    <span className={`verification-badge verify-${normalized}`}>
      <span aria-hidden="true">{meta.glyph}</span>
      {meta.label}
    </span>
  );
}
