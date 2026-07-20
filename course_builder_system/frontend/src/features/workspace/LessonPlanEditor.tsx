import { useEffect, useMemo, useRef, useState } from "react";
import type {
  LessonMode,
  LessonPlanDecisionDraft,
  LessonPlanOperation,
  Workspace,
} from "../../types";

interface SegmentDraft {
  subtopicId: string;
  mode: LessonMode;
  originalMode: LessonMode;
  originalSessionId: string;
  sessionId: string;
}

interface LessonPlanEditorDraft {
  constraints: Workspace["lessonPlan"]["constraints"];
  sessionOrder: string[];
  segments: SegmentDraft[];
  rationale: string;
  constraintIntent: Array<keyof Workspace["lessonPlan"]["constraints"]>;
  modeIntentIds: string[];
  placementIntentIds: string[];
  placementConflicts: string[];
  sessionOrderIntent: boolean;
}

export interface LessonPlanEditorProps {
  lessonPlan: Workspace["lessonPlan"];
  subtopicNames: Record<string, string>;
  canEdit: boolean;
  editing: boolean;
  busy: boolean;
  conflict: boolean;
  serverError?: string;
  onStartEdit: () => void;
  onCancel: () => void;
  onSave: (decision: LessonPlanDecisionDraft) => void;
  onResolveConflict: (choice: "reapply" | "discard") => void;
  onDirtyChange?: (dirty: boolean) => void;
}

function asLessonMode(value: string): LessonMode {
  return value === "self_study" ? "self_study" : "live";
}

function initialDraft(lessonPlan: Workspace["lessonPlan"]): LessonPlanEditorDraft {
  return {
    constraints: structuredClone(lessonPlan.constraints),
    sessionOrder: lessonPlan.sessions.map((session) => session.id),
    segments: lessonPlan.sessions.flatMap((session) => session.covers.map((cover) => ({
      subtopicId: cover.subtopicId,
      mode: asLessonMode(cover.mode),
      originalMode: asLessonMode(cover.mode),
      originalSessionId: session.id,
      sessionId: session.id,
    }))),
    rationale: "Human Lesson Plan checkpoint.",
    constraintIntent: [],
    modeIntentIds: [],
    placementIntentIds: [],
    placementConflicts: [],
    sessionOrderIntent: false,
  };
}

function lessonPlanSignature(lessonPlan: Workspace["lessonPlan"]): string {
  return JSON.stringify({
    constraints: lessonPlan.constraints,
    sessions: lessonPlan.sessions,
    expectedSubtopicIds: lessonPlan.expectedSubtopicIds,
  });
}

function rebaseDraft(
  current: LessonPlanEditorDraft,
  latestLessonPlan: Workspace["lessonPlan"],
): LessonPlanEditorDraft {
  const rebased = initialDraft(latestLessonPlan);
  Object.assign(rebased.constraints, Object.fromEntries(
    current.constraintIntent.map((field) => [field, structuredClone(current.constraints[field])]),
  ));
  if (current.constraintIntent.includes("defaultMode")) {
    rebased.segments.forEach((segment) => {
      segment.mode = current.constraints.defaultMode;
    });
  }
  for (const subtopicId of current.modeIntentIds) {
    const source = current.segments.find((segment) => segment.subtopicId === subtopicId);
    const target = rebased.segments.find((segment) => segment.subtopicId === subtopicId);
    if (source && target) target.mode = source.mode;
  }
  const latestSessionIds = new Set(rebased.sessionOrder);
  for (const subtopicId of current.placementIntentIds) {
    const source = current.segments.find((segment) => segment.subtopicId === subtopicId);
    const target = rebased.segments.find((segment) => segment.subtopicId === subtopicId);
    if (!source || !target) continue;
    if (latestSessionIds.has(source.sessionId)) target.sessionId = source.sessionId;
    else rebased.placementConflicts.push(subtopicId);
  }
  if (current.sessionOrderIntent) {
    rebased.sessionOrder = [
      ...current.sessionOrder.filter((sessionId) => latestSessionIds.has(sessionId)),
      ...rebased.sessionOrder.filter((sessionId) => !current.sessionOrder.includes(sessionId)),
    ];
  }
  rebased.rationale = current.rationale;
  rebased.constraintIntent = [...current.constraintIntent];
  rebased.modeIntentIds = [...current.modeIntentIds];
  rebased.placementIntentIds = [...current.placementIntentIds];
  rebased.sessionOrderIntent = current.sessionOrderIntent;
  return rebased;
}

function contractSignature(draft: LessonPlanEditorDraft): string {
  return JSON.stringify({
    constraints: draft.constraints,
    sessionOrder: draft.sessionOrder,
    segments: draft.segments.map(({ subtopicId, mode, sessionId }) => ({ subtopicId, mode, sessionId })),
  });
}

function operationsFromDraft(
  draft: LessonPlanEditorDraft,
  original: Workspace["lessonPlan"],
): LessonPlanOperation[] {
  const defaultChanged = draft.constraints.defaultMode !== original.constraints.defaultMode;
  const operations: LessonPlanOperation[] = draft.segments.flatMap((segment) => {
    const expectedMode = defaultChanged ? draft.constraints.defaultMode : segment.originalMode;
    return segment.mode === expectedMode
      ? []
      : [{ op: "set_mode" as const, targetId: segment.subtopicId, value: segment.mode }];
  });
  for (const segment of draft.segments) {
    if (segment.sessionId === segment.originalSessionId) continue;
    const position = draft.segments
      .filter((candidate) => candidate.sessionId === segment.sessionId)
      .findIndex((candidate) => candidate.subtopicId === segment.subtopicId) + 1;
    operations.push({
      op: "move_segment",
      targetId: segment.subtopicId,
      value: segment.sessionId,
      position,
    });
  }
  const originalOrder = original.sessions.map((session) => session.id);
  if (draft.sessionOrder.some((sessionId, index) => sessionId !== originalOrder[index])) {
    operations.push({ op: "reorder_session", sessionIds: draft.sessionOrder });
  }
  return operations;
}

function decisionFromDraft(
  draft: LessonPlanEditorDraft,
  original: Workspace["lessonPlan"],
): LessonPlanDecisionDraft {
  const constraints = structuredClone(draft.constraints);
  constraints.calendarDates = constraints.calendarDates
    .map((value) => value.trim())
    .filter(Boolean);
  return {
    constraints,
    operations: operationsFromDraft(draft, original),
    rationale: draft.rationale.trim(),
  };
}

function sessionIdsForOperation(
  operation: LessonPlanOperation,
  draft: LessonPlanEditorDraft,
): string[] {
  if (operation.op === "reorder_session") return operation.sessionIds;
  const segment = draft.segments.find((candidate) => candidate.subtopicId === operation.targetId);
  if (!segment) return [];
  return operation.op === "move_segment"
    ? [segment.originalSessionId, segment.sessionId]
    : [segment.sessionId];
}

export function LessonPlanEditor({
  lessonPlan,
  subtopicNames,
  canEdit,
  editing,
  busy,
  conflict,
  serverError,
  onStartEdit,
  onCancel,
  onSave,
  onResolveConflict,
  onDirtyChange,
}: LessonPlanEditorProps) {
  const [draft, setDraft] = useState(() => initialDraft(lessonPlan));
  const [acknowledged, setAcknowledged] = useState(false);
  const baselineRef = useRef(contractSignature(initialDraft(lessonPlan)));
  const sourceSignature = lessonPlanSignature(lessonPlan);
  const sourceSignatureRef = useRef(sourceSignature);
  const conflictReviewRef = useRef<HTMLButtonElement>(null);
  const dirty = contractSignature(draft) !== baselineRef.current;

  useEffect(() => {
    if (sourceSignatureRef.current === sourceSignature) return;
    sourceSignatureRef.current = sourceSignature;
    const latest = initialDraft(lessonPlan);
    setDraft((current) => {
      const currentDirty = contractSignature(current) !== baselineRef.current;
      baselineRef.current = contractSignature(latest);
      return editing && currentDirty ? rebaseDraft(current, lessonPlan) : latest;
    });
    setAcknowledged(false);
  }, [editing, lessonPlan, sourceSignature]);
  useEffect(() => onDirtyChange?.(editing && dirty), [dirty, editing, onDirtyChange]);
  useEffect(() => {
    if (conflict) conflictReviewRef.current?.focus();
  }, [conflict]);

  const operations = useMemo(() => operationsFromDraft(draft, lessonPlan), [draft, lessonPlan]);
  const maxChanged = draft.constraints.maxSessionHours !== lessonPlan.constraints.maxSessionHours;
  const layoutChanged = operations.some((operation) => operation.op !== "set_mode");
  const coveredIds = draft.sessionOrder.flatMap((sessionId) => draft.segments
    .filter((segment) => segment.sessionId === sessionId)
    .map((segment) => segment.subtopicId));
  const exactCoverage = coveredIds.length === lessonPlan.expectedSubtopicIds.length
    && new Set(coveredIds).size === coveredIds.length
    && coveredIds.every((id) => lessonPlan.expectedSubtopicIds.includes(id));
  const errors = [
    ...(draft.constraints.maxSessionHours <= 0 ? ["Maximum session duration must be positive."] : []),
    ...(draft.constraints.instructorCount !== null && draft.constraints.instructorCount < 1
      ? ["Instructor count must be positive or left unresolved."]
      : []),
    ...(!draft.rationale.trim() ? ["Record a concise rationale for this Lesson Plan decision."] : []),
    ...(!exactCoverage ? ["Every generated subtopic must appear exactly once."] : []),
    ...(draft.sessionOrder.some((sessionId) => !draft.segments.some((segment) => segment.sessionId === sessionId))
      ? ["A Lesson Plan session cannot be empty."]
      : []),
    ...(maxChanged && layoutChanged
      ? ["Save the maximum-duration change before moving or reordering sessions."]
      : []),
    ...draft.placementConflicts.map((subtopicId) =>
      `${subtopicNames[subtopicId] ?? subtopicId} targeted a session that no longer exists; choose a new placement.`,
    ),
  ];
  const constraintChanged = JSON.stringify(draft.constraints) !== JSON.stringify(lessonPlan.constraints);
  const modeAffectedSessionIds = lessonPlan.sessions.flatMap((session) =>
    session.covers.some((cover) =>
      draft.segments.find((segment) => segment.subtopicId === cover.subtopicId)?.mode !== cover.mode,
    ) ? [session.id] : [],
  );
  const affectedSessionIds = [...new Set([
    ...modeAffectedSessionIds,
    ...operations
      .filter((operation) => operation.op !== "set_mode")
      .flatMap((operation) => sessionIdsForOperation(operation, draft)),
  ])];

  const commit = (mutate: (next: LessonPlanEditorDraft) => void) => {
    const next = structuredClone(draft);
    mutate(next);
    setDraft(next);
    setAcknowledged(false);
  };
  const changeConstraint = <K extends keyof LessonPlanEditorDraft["constraints"]>(
    field: K,
    value: LessonPlanEditorDraft["constraints"][K],
  ) => commit((next) => {
    next.constraints[field] = value;
    next.constraintIntent = JSON.stringify(value) === JSON.stringify(lessonPlan.constraints[field])
      ? next.constraintIntent.filter((candidate) => candidate !== field)
      : [...new Set([...next.constraintIntent, field])];
    if (field === "defaultMode") {
      next.segments.forEach((segment) => {
        segment.mode = value as LessonMode;
      });
      next.modeIntentIds = [];
    }
  });
  const moveSession = (sessionId: string, direction: -1 | 1) => commit((next) => {
    const index = next.sessionOrder.indexOf(sessionId);
    const target = index + direction;
    if (target < 0 || target >= next.sessionOrder.length) return;
    [next.sessionOrder[index], next.sessionOrder[target]] = [next.sessionOrder[target], next.sessionOrder[index]];
    next.sessionOrderIntent = next.sessionOrder.some(
      (candidate, candidateIndex) => candidate !== lessonPlan.sessions[candidateIndex]?.id,
    );
  });

  if (!editing) {
    return canEdit ? <button className="button button-secondary" onClick={onStartEdit}>Edit Lesson Plan</button> : null;
  }

  return <div className="lesson-plan-editor">
    <div className="stage-intro"><div><span className="eyebrow">Typed delivery decision</span><h1>Edit Lesson Plan</h1><p>Set the delivery contract, place segments deliberately, and preserve exact Course Model coverage.</p></div><div className="lesson-editor-total"><strong>{draft.sessionOrder.length}</strong><span>planned sessions</span></div></div>
    {serverError ? <div className="lesson-editor-error" role="alert"><strong>The Lesson Plan decision could not be saved.</strong><p>{serverError}</p></div> : null}
    {errors.length ? <div className="lesson-editor-error" role="alert"><strong>Resolve these delivery requirements before save.</strong><ul>{errors.map((error) => <li key={error}>{error}</li>)}</ul></div> : null}
    <fieldset disabled={busy} aria-busy={busy || undefined}>
      <section className="lesson-editor-card lesson-constraint-editor"><header><span className="micro-label">Course-wide delivery contract</span><h2>Constraints and delivery details</h2></header><div className="lesson-constraint-fields">
        <label><span>Maximum session hours</span><input aria-label="Maximum session hours" type="number" min="0.25" max="24" step="0.25" value={draft.constraints.maxSessionHours} onChange={(event) => changeConstraint("maxSessionHours", Number(event.target.value))} /></label>
        <label><span>Default delivery mode</span><select aria-label="Default delivery mode" value={draft.constraints.defaultMode} onChange={(event) => changeConstraint("defaultMode", asLessonMode(event.target.value))}><option value="live">Live</option><option value="self_study">Self-study</option></select></label>
        <label><span>Instructor count</span><input aria-label="Instructor count" type="number" min="1" value={draft.constraints.instructorCount ?? ""} placeholder="Unresolved" onChange={(event) => changeConstraint("instructorCount", event.target.value ? Number(event.target.value) : null)} /></label>
        <label><span>Delivery platform</span><input aria-label="Delivery platform" value={draft.constraints.deliveryPlatform ?? ""} placeholder="Unresolved" onChange={(event) => changeConstraint("deliveryPlatform", event.target.value.trimStart() || null)} /></label>
        <label className="lesson-calendar-field"><span>Calendar dates (one per line)</span><textarea aria-label="Calendar dates" value={draft.constraints.calendarDates.join("\n")} onChange={(event) => changeConstraint("calendarDates", event.target.value.split("\n").map((value) => value.trim()))} /></label>
      </div></section>
      <section className="lesson-session-editors" aria-label="Editable Lesson Plan sessions">{draft.sessionOrder.map((sessionId, sessionIndex) => {
        const segments = draft.segments.filter((segment) => segment.sessionId === sessionId);
        const original = lessonPlan.sessions.find((session) => session.id === sessionId);
        return <article className="lesson-editor-card lesson-session-editor" key={sessionId}><header><div><span className="micro-label">Session {sessionIndex + 1}</span><h2>{original?.title ?? sessionId}</h2><code>{sessionId}</code></div><div className="lesson-session-order"><button type="button" aria-label={`Move session ${sessionId} earlier`} disabled={sessionIndex === 0} onClick={() => moveSession(sessionId, -1)}>↑</button><button type="button" aria-label={`Move session ${sessionId} later`} disabled={sessionIndex === draft.sessionOrder.length - 1} onClick={() => moveSession(sessionId, 1)}>↓</button></div></header><div className="lesson-segment-editors">{segments.map((segment, segmentIndex) => <div className="lesson-segment-editor" key={segment.subtopicId}><div><span>{sessionIndex + 1}.{segmentIndex + 1}</span><strong>{subtopicNames[segment.subtopicId] ?? segment.subtopicId}</strong><code>{segment.subtopicId}</code></div><label><span>Delivery mode</span><select aria-label={`Delivery mode for ${subtopicNames[segment.subtopicId] ?? segment.subtopicId}`} value={segment.mode} onChange={(event) => commit((next) => { const item = next.segments.find((candidate) => candidate.subtopicId === segment.subtopicId)!; item.mode = asLessonMode(event.target.value); const effectiveDefault = next.constraintIntent.includes("defaultMode") ? next.constraints.defaultMode : item.originalMode; next.modeIntentIds = item.mode === effectiveDefault ? next.modeIntentIds.filter((id) => id !== segment.subtopicId) : [...new Set([...next.modeIntentIds, segment.subtopicId])]; })}><option value="live">Live</option><option value="self_study">Self-study</option></select></label><label><span>Session placement</span><select aria-label={`Session placement for ${subtopicNames[segment.subtopicId] ?? segment.subtopicId}`} value={segment.sessionId} disabled={segments.length === 1} onChange={(event) => commit((next) => { const item = next.segments.find((candidate) => candidate.subtopicId === segment.subtopicId)!; item.sessionId = event.target.value; next.placementIntentIds = item.sessionId === item.originalSessionId ? next.placementIntentIds.filter((id) => id !== segment.subtopicId) : [...new Set([...next.placementIntentIds, segment.subtopicId])]; next.placementConflicts = next.placementConflicts.filter((id) => id !== segment.subtopicId); })}>{draft.sessionOrder.map((value, index) => <option key={value} value={value}>Session {index + 1} · {value}</option>)}</select></label></div>)}</div></article>;
      })}</section>
      <section className="lesson-editor-card lesson-reconciliation" aria-labelledby="lesson-reconciliation-title"><header><span className="micro-label">Affected-session preview</span><h2 id="lesson-reconciliation-title">What delivery planning will change</h2></header><div className="lesson-reconciliation-grid"><div><strong>Constraint contract</strong><p>{constraintChanged ? "Course-wide constraints or delivery details will change." : "No constraint changes."}</p></div><div><strong>Affected sessions</strong>{maxChanged ? <p>Duration regrouping will report exact changed session IDs after save.</p> : null}{affectedSessionIds.length ? <ul>{affectedSessionIds.map((id) => <li key={id}><code>{id}</code></li>)}</ul> : !maxChanged ? <p>No session bodies will change.</p> : null}</div><div><strong>Exact coverage</strong><p>{exactCoverage ? `${coveredIds.length} subtopics, each exactly once.` : "Coverage is invalid."}</p></div></div>
        <label><span>Decision rationale</span><textarea aria-label="Lesson Plan decision rationale" value={draft.rationale} onChange={(event) => commit((next) => { next.rationale = event.target.value; })} /></label>
        <label className="impact-ack"><input type="checkbox" checked={acknowledged} disabled={!dirty || Boolean(errors.length)} onChange={(event) => setAcknowledged(event.target.checked)} /><span>I reviewed the changed constraints, affected sessions, delivery modes, and exact Course Model coverage.</span></label>
        <button type="button" className="button button-primary" disabled={!dirty || Boolean(errors.length) || !acknowledged || busy || conflict} onClick={() => onSave(decisionFromDraft(draft, lessonPlan))}>{busy ? "Saving Lesson Plan…" : "Save Lesson Plan draft"}</button>
        <button type="button" className="button button-quiet" disabled={busy} onClick={() => { if (!dirty || window.confirm("Discard all unsaved Lesson Plan changes?")) onCancel(); }}>Cancel editing</button>
      </section>
    </fieldset>
    <div className="sr-status" role="status" aria-live="polite">{busy ? "Lesson Plan request in progress." : dirty ? "Affected-session preview is ready for review." : "Lesson Plan editor ready."}</div>
    {conflict ? <div className="modal-backdrop" role="presentation"><div className="feedback-dialog course-model-dialog" role="dialog" aria-modal="true" aria-labelledby="lesson-plan-conflict-title"><header><span className="eyebrow">Lesson Plan decision</span><h2 id="lesson-plan-conflict-title">The Lesson Plan changed elsewhere</h2></header><p>Your local delivery settings remain visible. Review them against the latest Lesson Plan before saving again, or discard them and use the latest artifact.</p><footer><button className="button button-quiet" onClick={() => onResolveConflict("discard")}>Use latest Lesson Plan</button><button ref={conflictReviewRef} className="button button-primary" onClick={() => { setAcknowledged(false); onResolveConflict("reapply"); }}>Review local decision again</button></footer></div></div> : null}
  </div>;
}
