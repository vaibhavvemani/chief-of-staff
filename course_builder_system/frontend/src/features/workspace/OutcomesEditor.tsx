import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import type {
  Outcome,
  OutcomeAdvisory,
  OutcomeCognitiveLevel,
  OutcomeDecisionDraft,
  OutcomeEditableField,
  OutcomePriority,
  OutcomeValidationIssue,
} from "../../types";

interface OutcomeDraftItem {
  key: string;
  id?: string;
  statement: string;
  evidence: string;
  cognitiveLevel: OutcomeCognitiveLevel;
  priority: OutcomePriority;
}

type OutcomeFieldErrors = Record<string, Partial<Record<"statement" | "evidence", string>>>;
type OutcomeMergeConflict = {
  serverValue: OutcomeDraftItem[OutcomeEditableField];
  localValue: OutcomeDraftItem[OutcomeEditableField];
};
type OutcomeMergeConflicts = Record<
  string,
  Partial<Record<OutcomeEditableField, OutcomeMergeConflict>>
>;

export interface OutcomesEditorProps {
  outcomes: Outcome[];
  advisories: OutcomeAdvisory[];
  canEdit: boolean;
  editing: boolean;
  busy: boolean;
  conflict: boolean;
  serverError?: string;
  serverIssues?: OutcomeValidationIssue[];
  onStartEdit: () => void;
  onCancel: () => void;
  onSave: (decision: OutcomeDecisionDraft) => void;
  onResolveConflict: (choice: "latest" | "keep") => void;
  onDirtyChange?: (dirty: boolean) => void;
}

const cognitiveLevels: OutcomeCognitiveLevel[] = [
  "remember",
  "understand",
  "apply",
  "analyze",
  "evaluate",
  "create",
];

const priorities: OutcomePriority[] = ["core", "supporting", "optional"];

function displayCode(value: string): string {
  const normalized = value.replaceAll("_", " ");
  return normalized ? normalized[0].toUpperCase() + normalized.slice(1) : value;
}

function draftsFromOutcomes(outcomes: Outcome[]): OutcomeDraftItem[] {
  return outcomes.map((outcome) => ({ ...outcome, key: outcome.id }));
}

function isDirty(drafts: OutcomeDraftItem[], baseline: Outcome[]): boolean {
  if (drafts.length !== baseline.length) return true;
  return drafts.some((draft, index) => {
    const outcome = baseline[index];
    return draft.id !== outcome.id
      || draft.statement.trim() !== outcome.statement
      || draft.evidence.trim() !== outcome.evidence
      || draft.cognitiveLevel !== outcome.cognitiveLevel
      || draft.priority !== outcome.priority;
  });
}

export function buildOutcomeDecisionDraft(
  baseline: Outcome[],
  drafts: OutcomeDraftItem[],
): OutcomeDecisionDraft {
  const baselineById = new Map(baseline.map((outcome) => [outcome.id, outcome]));
  const selectedIds: string[] = [];
  const edits: OutcomeDecisionDraft["edits"] = {};
  const additions: OutcomeDecisionDraft["additions"] = [];

  drafts.forEach((draft) => {
    const normalized = {
      statement: draft.statement.trim(),
      evidence: draft.evidence.trim(),
      cognitiveLevel: draft.cognitiveLevel,
      priority: draft.priority,
    };
    if (!draft.id) {
      additions.push({ clientKey: draft.key, ...normalized });
      return;
    }
    selectedIds.push(draft.id);
    const original = baselineById.get(draft.id);
    if (!original) return;
    const edit: OutcomeDecisionDraft["edits"][string] = {};
    (Object.keys(normalized) as OutcomeEditableField[]).forEach((field) => {
      if (normalized[field] !== original[field]) edit[field] = normalized[field] as never;
    });
    if (Object.keys(edit).length) edits[draft.id] = edit;
  });

  return {
    selectedIds,
    edits,
    additions,
    priorityOrder: drafts.map((draft) => draft.id ?? draft.key),
  };
}

function normalizedFieldValue(
  field: OutcomeEditableField,
  value: OutcomeDraftItem[OutcomeEditableField],
) {
  return field === "statement" || field === "evidence"
    ? String(value).trim()
    : value;
}

function sameOrder(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function rebaseDrafts(
  drafts: OutcomeDraftItem[],
  priorBaseline: Outcome[],
  latest: Outcome[],
): {
  drafts: OutcomeDraftItem[];
  fieldConflicts: OutcomeMergeConflicts;
  serverOrder?: string[];
} {
  const priorById = new Map(priorBaseline.map((outcome) => [outcome.id, outcome]));
  const latestById = new Map(latest.map((outcome) => [outcome.id, outcome]));
  const fieldConflicts: OutcomeMergeConflicts = {};
  const fields: OutcomeEditableField[] = [
    "statement",
    "evidence",
    "cognitiveLevel",
    "priority",
  ];
  const rebased = drafts.flatMap((draft) => {
    if (!draft.id) return [draft];
    const latestOutcome = latestById.get(draft.id);
    if (!latestOutcome) return [];
    const prior = priorById.get(draft.id);
    if (!prior) return [{ ...latestOutcome, key: latestOutcome.id }];
    const merged: OutcomeDraftItem = { ...latestOutcome, key: latestOutcome.id };
    fields.forEach((field) => {
      const localValue = normalizedFieldValue(field, draft[field]);
      const priorValue = normalizedFieldValue(field, prior[field]);
      const serverValue = normalizedFieldValue(field, latestOutcome[field]);
      const localChanged = localValue !== priorValue;
      const serverChanged = serverValue !== priorValue;
      if (localChanged) merged[field] = draft[field] as never;
      if (localChanged && serverChanged && localValue !== serverValue) {
        fieldConflicts[draft.key] = {
          ...fieldConflicts[draft.key],
          [field]: { localValue: draft[field], serverValue: latestOutcome[field] },
        };
      }
    });
    return [merged];
  });
  const priorIds = new Set(priorBaseline.map((outcome) => outcome.id));
  latest.forEach((outcome) => {
    if (!priorIds.has(outcome.id)) rebased.push({ ...outcome, key: outcome.id });
  });

  const currentCanonicalIds = new Set(
    drafts.flatMap((draft) => draft.id && latestById.has(draft.id) ? [draft.id] : []),
  );
  const priorCommonOrder = priorBaseline
    .map((outcome) => outcome.id)
    .filter((id) => currentCanonicalIds.has(id));
  const localCommonOrder = drafts
    .flatMap((draft) => draft.id && currentCanonicalIds.has(draft.id) ? [draft.id] : []);
  const serverCommonOrder = latest
    .map((outcome) => outcome.id)
    .filter((id) => currentCanonicalIds.has(id));
  const localOrderChanged = !sameOrder(localCommonOrder, priorCommonOrder)
    || drafts.some((draft) => !draft.id);
  const serverOrderChanged = !sameOrder(serverCommonOrder, priorCommonOrder);
  const serverOrder = latest
    .map((outcome) => outcome.id)
    .filter((id) => rebased.some((draft) => draft.id === id));
  const localAdditionKeys = rebased.filter((draft) => !draft.id).map((draft) => draft.key);
  const completeServerOrder = [...serverOrder, ...localAdditionKeys];

  if (serverOrderChanged && !localOrderChanged) {
    const byKey = new Map(rebased.map((draft) => [draft.key, draft]));
    return {
      drafts: completeServerOrder.flatMap((key) => byKey.get(key) ? [byKey.get(key)!] : []),
      fieldConflicts,
    };
  }
  return {
    drafts: rebased,
    fieldConflicts,
    serverOrder: serverOrderChanged && localOrderChanged
      && !sameOrder(localCommonOrder, serverCommonOrder)
      ? completeServerOrder
      : undefined,
  };
}

function OutcomeAdvisories({ advisories, editing }: { advisories: OutcomeAdvisory[]; editing: boolean }) {
  if (!advisories.length) {
    return (
      <div className="quality-note outcome-quality-clear">
        <span aria-hidden="true">✓</span>
        <div>
          <strong>No deterministic advisory flags</strong>
          <small>These checks support review; they do not judge final pedagogical quality.</small>
        </div>
      </div>
    );
  }
  return (
    <section className="outcome-advisories" aria-label="Outcome advisory checks">
      <div className="outcome-advisory-heading">
        <span aria-hidden="true">i</span>
        <div>
          <strong>{advisories.length} advisory check{advisories.length === 1 ? "" : "s"}</strong>
          <small>{editing ? "These describe the saved version and will refresh after save." : "Review these signals before approval; they are not structural blockers."}</small>
        </div>
      </div>
      <ul>
        {advisories.map((advisory, index) => (
          <li key={`${advisory.code}:${advisory.outcomeId}:${advisory.relatedOutcomeId ?? ""}:${index}`}>
            <code>{advisory.outcomeId}</code>
            <span>{advisory.reason}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function RemovalDialog({
  outcome,
  busy,
  onCancel,
  onConfirm,
}: {
  outcome: OutcomeDraftItem;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const confirmRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    confirmRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
      if (event.key !== "Tab") return;
      const focusable = [...(dialogRef.current?.querySelectorAll<HTMLElement>(
        "button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled)",
      ) ?? [])];
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable.at(-1)!;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onCancel]);
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.currentTarget === event.target) onCancel();
    }}>
      <div ref={dialogRef} className="feedback-dialog outcome-removal-dialog" role="dialog" aria-modal="true" aria-labelledby="remove-outcome-title">
        <header>
          <span className="eyebrow">Structural decision</span>
          <h2 id="remove-outcome-title">Remove this Outcome?</h2>
          <p>{outcome.id ? <>Removing <code>{outcome.id}</code> omits it from the retained selection.</> : "This unsaved Outcome will be discarded."}</p>
        </header>
        <blockquote>{outcome.statement.trim() || "Untitled Outcome"}</blockquote>
        <footer>
          <button className="button button-quiet" disabled={busy} onClick={onCancel}>Keep Outcome</button>
          <button ref={confirmRef} className="button button-danger" disabled={busy} onClick={onConfirm}>Remove Outcome</button>
        </footer>
      </div>
    </div>
  );
}

export function OutcomesEditor({
  outcomes,
  advisories,
  canEdit,
  editing,
  busy,
  conflict,
  serverError,
  serverIssues = [],
  onStartEdit,
  onCancel,
  onSave,
  onResolveConflict,
  onDirtyChange,
}: OutcomesEditorProps) {
  const [baseline, setBaseline] = useState<Outcome[]>(outcomes);
  const [drafts, setDrafts] = useState<OutcomeDraftItem[]>(() => draftsFromOutcomes(outcomes));
  const [fieldErrors, setFieldErrors] = useState<OutcomeFieldErrors>({});
  const [collectionError, setCollectionError] = useState<string>();
  const [pendingRemovalKey, setPendingRemovalKey] = useState<string>();
  const [mergeConflicts, setMergeConflicts] = useState<OutcomeMergeConflicts>({});
  const [serverOrder, setServerOrder] = useState<string[]>();
  const nextNewIndex = useRef(1);
  const previousEditing = useRef(false);
  const errorSummaryRef = useRef<HTMLDivElement>(null);
  const conflictRef = useRef<HTMLDivElement>(null);
  const addButtonRef = useRef<HTMLButtonElement>(null);
  const removalTriggerRef = useRef<HTMLElement | null>(null);

  const resetToCanonical = (canonical = outcomes) => {
    setBaseline(canonical.map((outcome) => ({ ...outcome })));
    setDrafts(draftsFromOutcomes(canonical));
    setFieldErrors({});
    setCollectionError(undefined);
    setPendingRemovalKey(undefined);
    setMergeConflicts({});
    setServerOrder(undefined);
    nextNewIndex.current = 1;
  };

  useEffect(() => {
    if (editing && !previousEditing.current) resetToCanonical(outcomes);
    previousEditing.current = editing;
  }, [editing, outcomes]);

  useEffect(() => {
    if (serverError) errorSummaryRef.current?.focus();
  }, [serverError]);

  useEffect(() => {
    if (conflict) conflictRef.current?.focus();
  }, [conflict]);

  const dirty = useMemo(() => isDirty(drafts, baseline), [baseline, drafts]);
  const mergeConflictCount = useMemo(
    () => Object.values(mergeConflicts).reduce(
      (total, conflicts) => total + Object.keys(conflicts).length,
      serverOrder ? 1 : 0,
    ),
    [mergeConflicts, serverOrder],
  );
  useEffect(() => {
    if (mergeConflictCount) conflictRef.current?.focus();
  }, [mergeConflictCount]);
  useEffect(() => onDirtyChange?.(editing && dirty), [dirty, editing, onDirtyChange]);
  const serverFieldErrors = useMemo<OutcomeFieldErrors>(() => {
    const next: OutcomeFieldErrors = {};
    const additions = drafts.filter((draft) => !draft.id);
    serverIssues.forEach((issue) => {
      if (issue.field !== "statement" && issue.field !== "evidence") return;
      const key = issue.outcomeId
        ? drafts.find((draft) => draft.id === issue.outcomeId)?.key
        : issue.index != null
          ? additions[issue.index]?.key
          : undefined;
      if (!key) return;
      next[key] = { ...next[key], [issue.field]: issue.message };
    });
    return next;
  }, [drafts, serverIssues]);
  const pendingRemoval = drafts.find((draft) => draft.key === pendingRemovalKey);

  const focusStatement = (key: string) => {
    window.setTimeout(() => document.getElementById(`outcome-${key}-statement`)?.focus(), 0);
  };

  const updateDraft = <K extends OutcomeEditableField>(
    key: string,
    field: K,
    value: OutcomeDraftItem[K],
  ) => {
    setDrafts((current) => current.map((draft) => draft.key === key ? { ...draft, [field]: value } : draft));
    setFieldErrors((current) => {
      if (!current[key]?.[field as "statement" | "evidence"]) return current;
      const next = { ...current, [key]: { ...current[key] } };
      delete next[key][field as "statement" | "evidence"];
      if (!Object.keys(next[key]).length) delete next[key];
      return next;
    });
  };

  const resolveFieldConflict = (
    key: string,
    field: OutcomeEditableField,
    choice: "local" | "server",
  ) => {
    const conflict = mergeConflicts[key]?.[field];
    if (!conflict) return;
    if (choice === "server") {
      setDrafts((current) => current.map((draft) => draft.key === key
        ? { ...draft, [field]: conflict.serverValue }
        : draft));
    }
    setMergeConflicts((current) => {
      const next = { ...current, [key]: { ...current[key] } };
      delete next[key][field];
      if (!Object.keys(next[key]).length) delete next[key];
      return next;
    });
  };

  const resolveOrderConflict = (choice: "local" | "server") => {
    if (choice === "server" && serverOrder) {
      setDrafts((current) => {
        const byKey = new Map(current.map((draft) => [draft.key, draft]));
        return serverOrder.flatMap((key) => byKey.get(key) ? [byKey.get(key)!] : []);
      });
    }
    setServerOrder(undefined);
  };

  const addOutcome = () => {
    const used = new Set(drafts.map((draft) => draft.id ?? draft.key));
    let key = `new_${nextNewIndex.current}`;
    while (used.has(key)) {
      nextNewIndex.current += 1;
      key = `new_${nextNewIndex.current}`;
    }
    nextNewIndex.current += 1;
    setDrafts((current) => [...current, {
      key,
      statement: "",
      evidence: "",
      cognitiveLevel: "apply",
      priority: "supporting",
    }]);
    setCollectionError(undefined);
    focusStatement(key);
  };

  const requestRemoval = (key: string, trigger: HTMLElement) => {
    removalTriggerRef.current = trigger;
    setPendingRemovalKey(key);
  };

  const cancelRemoval = () => {
    setPendingRemovalKey(undefined);
    window.setTimeout(() => removalTriggerRef.current?.focus(), 0);
  };

  const confirmRemoval = () => {
    if (!pendingRemovalKey) return;
    const index = drafts.findIndex((draft) => draft.key === pendingRemovalKey);
    const remaining = drafts.filter((draft) => draft.key !== pendingRemovalKey);
    const focusKey = remaining[Math.min(index, remaining.length - 1)]?.key;
    setDrafts(remaining);
    setPendingRemovalKey(undefined);
    setFieldErrors((current) => {
      const next = { ...current };
      delete next[pendingRemovalKey];
      return next;
    });
    if (focusKey) focusStatement(focusKey);
    else window.setTimeout(() => addButtonRef.current?.focus(), 0);
  };

  const moveOutcome = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= drafts.length) return;
    setDrafts((current) => {
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
    window.setTimeout(() => document.getElementById(`outcome-${drafts[index].key}-move-${direction < 0 ? "up" : "down"}`)?.focus(), 0);
  };

  const validate = (): boolean => {
    const nextErrors: OutcomeFieldErrors = {};
    drafts.forEach((draft) => {
      const errors: OutcomeFieldErrors[string] = {};
      if (!draft.statement.trim()) errors.statement = "Enter a meaningful Outcome statement.";
      else if (draft.statement.trim().length > 300) errors.statement = "Keep the statement to 300 characters or fewer.";
      if (!draft.evidence.trim()) errors.evidence = "Describe observable evidence of learning.";
      else if (draft.evidence.trim().length > 300) errors.evidence = "Keep the evidence to 300 characters or fewer.";
      if (Object.keys(errors).length) nextErrors[draft.key] = errors;
    });
    const nextCollectionError = drafts.length ? undefined : "Keep or add at least one Outcome.";
    setFieldErrors(nextErrors);
    setCollectionError(nextCollectionError);
    if (nextCollectionError || Object.keys(nextErrors).length) {
      window.setTimeout(() => errorSummaryRef.current?.focus(), 0);
      return false;
    }
    return true;
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (busy || conflict || mergeConflictCount || !dirty || !validate()) return;
    onSave(buildOutcomeDecisionDraft(baseline, drafts));
  };

  const cancel = () => {
    resetToCanonical();
    onCancel();
  };

  const useLatest = () => {
    resetToCanonical(outcomes);
    onResolveConflict("latest");
  };

  const keepAgainstLatest = () => {
    const rebased = rebaseDrafts(drafts, baseline, outcomes);
    setDrafts(rebased.drafts);
    setMergeConflicts(rebased.fieldConflicts);
    setServerOrder(rebased.serverOrder);
    setBaseline(outcomes.map((outcome) => ({ ...outcome })));
    setFieldErrors({});
    setCollectionError(undefined);
    onResolveConflict("keep");
  };

  if (!editing || !canEdit) {
    return (
      <>
        <div className="outcome-toolbar">
          <OutcomeAdvisories advisories={advisories} editing={false} />
          {canEdit ? <button className="button button-secondary" disabled={busy} onClick={onStartEdit}>Edit Outcomes</button> : null}
        </div>
        <ol className="outcome-list">
          {outcomes.map((outcome, index) => (
            <li key={outcome.id} className="outcome-card">
              <span className="outcome-order">{String(index + 1).padStart(2, "0")}</span>
              <div className="outcome-main">
                <div className="outcome-meta">
                  <span className={`priority priority-${outcome.priority}`}>{outcome.priority}</span>
                  <span>{displayCode(outcome.cognitiveLevel)}</span>
                  <code>{outcome.id}</code>
                </div>
                <h3>{outcome.statement}</h3>
                <div className="evidence-line"><span>Evidence of learning</span><p>{outcome.evidence}</p></div>
              </div>
            </li>
          ))}
        </ol>
      </>
    );
  }

  return (
    <form className="outcomes-editor" onSubmit={submit} noValidate aria-busy={busy || undefined}>
      <div className="outcomes-editor-toolbar">
        <div>
          <span className="eyebrow">Structured editor</span>
          <h2>Shape the learning contract</h2>
          <p>Canonical IDs stay fixed while statements, evidence, levels, priorities, and display order change.</p>
        </div>
        <div className="outcomes-editor-state" role="status" aria-live="polite">
          <span className={dirty ? "dirty" : "clean"} />
          <strong>{dirty ? "Unsaved changes" : "Matches saved draft"}</strong>
        </div>
      </div>

      {conflict ? (
        <div className="outcome-conflict" role="alert" tabIndex={-1} ref={conflictRef}>
          <div><strong>These Outcomes changed elsewhere.</strong><p>The latest canonical version has been loaded without discarding your local edits. Choose how to continue.</p></div>
          <div><button type="button" className="button button-secondary" onClick={useLatest}>Use latest server version</button><button type="button" className="button button-primary" onClick={keepAgainstLatest}>Keep my edits against latest</button></div>
        </div>
      ) : null}

      {mergeConflictCount ? (
        <div className="outcome-conflict outcome-merge-conflict" role="alert" tabIndex={-1} ref={conflictRef}>
          <div>
            <strong>Resolve {mergeConflictCount} overlapping server change{mergeConflictCount === 1 ? "" : "s"}.</strong>
            <p>Your nonconflicting edits were rebased. Choose explicitly for each overlapping field or order change before saving.</p>
          </div>
          {serverOrder ? (
            <div className="outcome-conflict-actions">
              <span>The server and this editor both changed display order.</span>
              <button type="button" className="button button-secondary" onClick={() => resolveOrderConflict("server")}>Use server order</button>
              <button type="button" className="button button-primary" onClick={() => resolveOrderConflict("local")}>Keep my order</button>
            </div>
          ) : null}
        </div>
      ) : null}

      {(collectionError || Object.keys(fieldErrors).length || serverError || serverIssues.length) ? (
        <div className="outcome-error-summary" role="alert" tabIndex={-1} ref={errorSummaryRef}>
          <strong>{serverError || serverIssues.length ? "Outcomes were not saved." : "Review the highlighted Outcome fields."}</strong>
          <p>{serverError ?? serverIssues[0]?.message ?? collectionError ?? `${Object.keys(fieldErrors).length} Outcome${Object.keys(fieldErrors).length === 1 ? " needs" : "s need"} attention.`}</p>
        </div>
      ) : null}

      <OutcomeAdvisories advisories={advisories} editing />

      <ol className="outcome-editor-list">
        {drafts.map((draft, index) => {
          const statementError = fieldErrors[draft.key]?.statement ?? serverFieldErrors[draft.key]?.statement;
          const evidenceError = fieldErrors[draft.key]?.evidence ?? serverFieldErrors[draft.key]?.evidence;
          const statementConflict = mergeConflicts[draft.key]?.statement;
          const evidenceConflict = mergeConflicts[draft.key]?.evidence;
          const levelConflict = mergeConflicts[draft.key]?.cognitiveLevel;
          const priorityConflict = mergeConflicts[draft.key]?.priority;
          const label = draft.id ?? `new Outcome ${index + 1}`;
          return (
            <li key={draft.key} className={`outcome-editor-card ${statementError || evidenceError ? "has-error" : ""}`}>
              <div className="outcome-editor-sequence"><span>{String(index + 1).padStart(2, "0")}</span><code>{draft.id ?? "ID assigned on save"}</code></div>
              <div className="outcome-editor-fields">
                <label htmlFor={`outcome-${draft.key}-statement`}>
                  <span>Outcome statement <small>Observable learner result</small></span>
                  <textarea
                    id={`outcome-${draft.key}-statement`}
                    rows={3}
                    value={draft.statement}
                    disabled={busy}
                    aria-label={`Outcome statement for ${label}`}
                    aria-invalid={statementError || statementConflict ? "true" : undefined}
                    aria-describedby={statementError ? `outcome-${draft.key}-statement-error` : undefined}
                    onChange={(event) => updateDraft(draft.key, "statement", event.target.value)}
                  />
                </label>
                {statementError ? <p className="outcome-field-error" id={`outcome-${draft.key}-statement-error`}>{statementError}</p> : null}
                {statementConflict ? <div className="outcome-field-conflict"><p>The server now has: “{String(statementConflict.serverValue)}”</p><button type="button" onClick={() => resolveFieldConflict(draft.key, "statement", "server")}>Use server statement</button><button type="button" onClick={() => resolveFieldConflict(draft.key, "statement", "local")}>Keep my statement</button></div> : null}
                <label htmlFor={`outcome-${draft.key}-evidence`}>
                  <span>Evidence of learning <small>What the learner produces or demonstrates</small></span>
                  <textarea
                    id={`outcome-${draft.key}-evidence`}
                    rows={3}
                    value={draft.evidence}
                    disabled={busy}
                    aria-label={`Evidence of learning for ${label}`}
                    aria-invalid={evidenceError || evidenceConflict ? "true" : undefined}
                    aria-describedby={evidenceError ? `outcome-${draft.key}-evidence-error` : undefined}
                    onChange={(event) => updateDraft(draft.key, "evidence", event.target.value)}
                  />
                </label>
                {evidenceError ? <p className="outcome-field-error" id={`outcome-${draft.key}-evidence-error`}>{evidenceError}</p> : null}
                {evidenceConflict ? <div className="outcome-field-conflict"><p>The server now has: “{String(evidenceConflict.serverValue)}”</p><button type="button" onClick={() => resolveFieldConflict(draft.key, "evidence", "server")}>Use server evidence</button><button type="button" onClick={() => resolveFieldConflict(draft.key, "evidence", "local")}>Keep my evidence</button></div> : null}
                <div className="outcome-enum-grid">
                  <label htmlFor={`outcome-${draft.key}-level`}><span>Cognitive level</span><select id={`outcome-${draft.key}-level`} aria-label={`Cognitive level for ${label}`} aria-invalid={levelConflict ? "true" : undefined} value={draft.cognitiveLevel} disabled={busy} onChange={(event) => updateDraft(draft.key, "cognitiveLevel", event.target.value as OutcomeCognitiveLevel)}>{cognitiveLevels.map((level) => <option key={level} value={level}>{displayCode(level)}</option>)}</select>{levelConflict ? <span className="outcome-field-conflict"><span>Server: {displayCode(String(levelConflict.serverValue))}</span><button type="button" onClick={() => resolveFieldConflict(draft.key, "cognitiveLevel", "server")}>Use server level</button><button type="button" onClick={() => resolveFieldConflict(draft.key, "cognitiveLevel", "local")}>Keep my level</button></span> : null}</label>
                  <label htmlFor={`outcome-${draft.key}-priority`}><span>Priority</span><select id={`outcome-${draft.key}-priority`} aria-label={`Priority for ${label}`} aria-invalid={priorityConflict ? "true" : undefined} value={draft.priority} disabled={busy} onChange={(event) => updateDraft(draft.key, "priority", event.target.value as OutcomePriority)}>{priorities.map((priority) => <option key={priority} value={priority}>{displayCode(priority)}</option>)}</select>{priorityConflict ? <span className="outcome-field-conflict"><span>Server: {displayCode(String(priorityConflict.serverValue))}</span><button type="button" onClick={() => resolveFieldConflict(draft.key, "priority", "server")}>Use server priority</button><button type="button" onClick={() => resolveFieldConflict(draft.key, "priority", "local")}>Keep my priority</button></span> : null}</label>
                </div>
              </div>
              <div className="outcome-editor-actions" aria-label={`Reorder and remove ${label}`}>
                <button id={`outcome-${draft.key}-move-up`} type="button" disabled={busy || index === 0} aria-label={`Move ${label} up`} onClick={() => moveOutcome(index, -1)}>↑</button>
                <button id={`outcome-${draft.key}-move-down`} type="button" disabled={busy || index === drafts.length - 1} aria-label={`Move ${label} down`} onClick={() => moveOutcome(index, 1)}>↓</button>
                <button type="button" className="remove" disabled={busy} aria-label={`Remove ${label}`} onClick={(event) => requestRemoval(draft.key, event.currentTarget)}>Remove</button>
              </div>
            </li>
          );
        })}
      </ol>

      <div className="outcomes-editor-footer">
        <button ref={addButtonRef} type="button" className="button button-secondary" disabled={busy} onClick={addOutcome}>+ Add Outcome</button>
        <div><button type="button" className="button button-quiet" disabled={busy} onClick={cancel}>Cancel changes</button><button type="submit" className="button button-primary" disabled={busy || conflict || Boolean(mergeConflictCount) || !dirty}>{busy ? "Saving draft…" : "Save Outcomes draft"}</button></div>
      </div>

      {pendingRemoval ? <RemovalDialog outcome={pendingRemoval} busy={busy} onCancel={cancelRemoval} onConfirm={confirmRemoval} /> : null}
    </form>
  );
}
