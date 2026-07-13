import type { UiStatus } from "../types";

const statusLabels: Record<UiStatus, string> = {
  locked: "Locked",
  ready: "Ready",
  running: "Running",
  awaiting_review: "Awaiting review",
  approved: "Approved",
  requires_attention: "Needs attention",
  stale: "Stale",
  failed: "Failed",
};

export function StatusBadge({ status, count }: { status: UiStatus; count?: number }) {
  return (
    <span className={`status-badge status-${status}`}>
      <span className="status-mark" aria-hidden="true" />
      {statusLabels[status]}
      {typeof count === "number" && count > 0 ? <strong>{count}</strong> : null}
    </span>
  );
}

export function SourceStatus({ status }: { status: string }) {
  const normalized = ["approved", "rejected", "proposed", "unavailable"].includes(status)
    ? status
    : "proposed";
  return (
    <span className={`source-status source-${normalized}`}>
      <span aria-hidden="true">{normalized === "approved" ? "✓" : normalized === "rejected" ? "×" : "·"}</span>
      {normalized.charAt(0).toUpperCase() + normalized.slice(1)}
    </span>
  );
}

export function VerificationBadge({ support }: { support: string }) {
  const normalized = ["supported", "partial", "unsupported", "ungrounded", "unattributed"].includes(support)
    ? support
    : "partial";
  return <span className={`verification-badge verify-${normalized}`}>{normalized.replace("_", " ")}</span>;
}

