import { useEffect, useMemo, useRef, useState } from "react";
import type {
  Concept,
  CourseModelData,
  CourseModelOperation,
  CourseModelPreview,
  CourseModelValidationIssue,
  CourseModule,
  Outcome,
  Subtopic,
} from "../../types";
import { CourseModelDiff } from "./CourseModelDiff";

type RemovalTarget = { type: "module" | "subtopic" | "concept" | "coverage"; id: string; label: string };

export interface CourseModelEditorProps {
  model: CourseModelData;
  outcomes: Outcome[];
  canEdit: boolean;
  editing: boolean;
  busy: boolean;
  conflict: boolean;
  serverError?: string;
  serverIssues?: CourseModelValidationIssue[];
  preview?: CourseModelPreview | null;
  onStartEdit: () => void;
  onCancel: () => void;
  onPreview: (operations: CourseModelOperation[]) => void;
  onSave: (operations: CourseModelOperation[], impactChecksum: string) => void;
  onInvalidatePreview: () => void;
  onRecoverConflict: (choice: "reapply" | "discard") => void;
  onDirtyChange?: (dirty: boolean) => void;
}

const cloneModel = (model: CourseModelData): CourseModelData => JSON.parse(JSON.stringify(model)) as CourseModelData;
const listText = (values: string[]) => values.join("\n");
const parseList = (value: string) => value.split("\n").map((item) => item.trim()).filter(Boolean);
const refPrefix = (family: string) => `new_${family}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
const valuesEqual = (left: unknown, right: unknown) => JSON.stringify(left) === JSON.stringify(right);

function deriveDraftOrders(model: CourseModelData): CourseModelData {
  model.modules.forEach((module, moduleIndex) => {
    module.order = moduleIndex + 1;
    module.subtopics.forEach((subtopic, subtopicIndex) => { subtopic.order = subtopicIndex + 1; });
  });
  return model;
}

function editableRecord(
  model: CourseModelData,
  family: "module" | "subtopic" | "concept" | "coverage",
  targetId: string,
): Record<string, unknown> | undefined {
  if (family === "module") return model.modules.find((module) => module.id === targetId) as unknown as Record<string, unknown> | undefined;
  const subtopics = model.modules.flatMap((module) => module.subtopics);
  if (family === "subtopic") return subtopics.find((subtopic) => subtopic.id === targetId) as unknown as Record<string, unknown> | undefined;
  if (family === "concept") return subtopics.flatMap((subtopic) => subtopic.concepts).find((concept) => concept.id === targetId) as unknown as Record<string, unknown> | undefined;
  return subtopics.flatMap((subtopic) => subtopic.coverageRequirements).find((coverage) => coverage.id === targetId) as unknown as Record<string, unknown> | undefined;
}

function baselineUpdateValue(
  baseModel: CourseModelData,
  operations: CourseModelOperation[],
  family: "module" | "subtopic" | "concept" | "coverage",
  targetId: string,
  field: string,
): unknown {
  const existing = editableRecord(baseModel, family, targetId);
  if (existing) return existing[field];
  const add = operations.find((operation) =>
    operation.op === `add_${family}`
    && "clientRef" in operation
    && operation.clientRef === targetId,
  );
  return add ? (add as unknown as Record<string, unknown>)[field] : undefined;
}

function recordError(
  issues: CourseModelValidationIssue[],
  recordId: string,
  field?: string,
): boolean {
  return issues.some((issue) =>
    issue.recordId === recordId
    && (!field || !issue.field || issue.field === field),
  );
}

function fieldError(issues: CourseModelValidationIssue[], field: string): boolean {
  return issues.some((issue) => issue.field === field);
}

function sameStructure(left: CourseModelData, right: CourseModelData): boolean {
  const shape = (model: CourseModelData) => model.modules.map((module) => ({
    id: module.id,
    subtopicIds: module.subtopics.map((subtopic) => subtopic.id),
  }));
  return valuesEqual(shape(left), shape(right));
}

function pruneRestoredStructuralOperations(
  baseModel: CourseModelData,
  draft: CourseModelData,
  operations: CourseModelOperation[],
): CourseModelOperation[] {
  if (!sameStructure(baseModel, draft)) return operations;
  return operations.filter((operation) => ![
    "move_module",
    "reorder_modules",
    "move_subtopic",
    "reorder_subtopics",
  ].includes(operation.op));
}

function selectedValues(event: React.ChangeEvent<HTMLSelectElement>): string[] {
  return [...event.currentTarget.selectedOptions].map((option) => option.value);
}

function Modal({
  title,
  children,
  confirmLabel,
  cancelLabel = "Cancel",
  busy,
  onCancel,
  onConfirm,
}: {
  title: string;
  children: React.ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  busy?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const onCancelRef = useRef(onCancel);
  useEffect(() => { onCancelRef.current = onCancel; }, [onCancel]);
  useEffect(() => {
    const restore = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    confirmRef.current?.focus();
    const keydown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancelRef.current();
      if (event.key !== "Tab") return;
      const focusable = [...(dialogRef.current?.querySelectorAll<HTMLElement>("button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled)") ?? [])];
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
    window.addEventListener("keydown", keydown);
    return () => {
      window.removeEventListener("keydown", keydown);
      restore?.focus();
    };
  }, []);
  return (
    <div className="modal-backdrop" role="presentation">
      <div ref={dialogRef} className="feedback-dialog course-model-dialog" role="dialog" aria-modal="true" aria-labelledby="course-model-dialog-title">
        <header><span className="eyebrow">Course Model decision</span><h2 id="course-model-dialog-title">{title}</h2></header>
        {children}
        <footer><button className="button button-quiet" disabled={busy} onClick={onCancel}>{cancelLabel}</button><button ref={confirmRef} className="button button-primary" disabled={busy} onClick={onConfirm}>{confirmLabel}</button></footer>
      </div>
    </div>
  );
}

function MultiSelect({
  label,
  value,
  options,
  onChange,
  invalid,
}: {
  label: string;
  value: string[];
  options: Array<{ id: string; label: string }>;
  onChange: (value: string[]) => void;
  invalid?: boolean;
}) {
  return (
    <div className="course-model-multi"><label><span>{label}</span><select aria-label={label} multiple value={value} aria-invalid={invalid || undefined} onChange={(event) => onChange(selectedValues(event))}>{options.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}</select></label><div className="course-model-multi-help"><small>Use Ctrl/⌘ or Shift to select more than one.</small><button type="button" disabled={!value.length} onClick={() => onChange([])}>Clear selection</button></div></div>
  );
}

function OutcomeOrder({
  value,
  options,
  invalid,
  onChange,
}: {
  value: string[];
  options: Array<{ id: string; label: string }>;
  invalid?: boolean;
  onChange: (value: string[]) => void;
}) {
  const labels = new Map(options.map((option) => [option.id, option.label]));
  const move = (from: number, to: number) => onChange(moveItem(value, from, to));
  return (
    <div className="course-outcome-order" aria-invalid={invalid || undefined}>
      <span>Course Model outcome order</span>
      <p>Every approved Course Outcome remains linked. Use the arrow controls to change their supported order.</p>
      <ol>
        {value.map((id, index) => <li key={id}>
          <span>{labels.get(id) ?? id}</span>
          <div className="record-actions">
            <button type="button" aria-label={`Move Course Outcome ${id} up`} disabled={index === 0} onClick={() => move(index, index - 1)}>↑</button>
            <button type="button" aria-label={`Move Course Outcome ${id} down`} disabled={index === value.length - 1} onClick={() => move(index, index + 1)}>↓</button>
          </div>
        </li>)}
      </ol>
    </div>
  );
}

function moveItem<T>(items: T[], from: number, to: number): T[] {
  const copy = [...items];
  const [item] = copy.splice(from, 1);
  copy.splice(to, 0, item);
  return copy;
}

function lastMatchingIndex<T>(items: T[], predicate: (item: T) => boolean): number {
  for (let index = items.length - 1; index >= 0; index -= 1) {
    if (predicate(items[index])) return index;
  }
  return -1;
}

export function CourseModelEditor(props: CourseModelEditorProps) {
  const {
    model, outcomes, canEdit, editing, busy, conflict, serverError,
    serverIssues = [], preview, onStartEdit, onCancel, onPreview, onSave,
    onInvalidatePreview, onRecoverConflict, onDirtyChange,
  } = props;
  const [draft, setDraft] = useState(() => cloneModel(model));
  const [operations, setOperations] = useState<CourseModelOperation[]>([]);
  const [selectedId, setSelectedId] = useState(model.modules[0]?.subtopics[0]?.id ?? "");
  const [removal, setRemoval] = useState<RemovalTarget | null>(null);
  const [impactAcknowledged, setImpactAcknowledged] = useState(false);
  const [previewedBatchSignature, setPreviewedBatchSignature] = useState("");
  const errorSummaryRef = useRef<HTMLDivElement>(null);
  const baseModelRef = useRef(cloneModel(model));

  useEffect(() => {
    const canonical = cloneModel(model);
    if (editing && operations.length) {
      if (conflict) baseModelRef.current = canonical;
      return;
    }
    baseModelRef.current = canonical;
    setDraft(cloneModel(canonical));
    if (!editing) {
      setOperations([]);
      setImpactAcknowledged(false);
      setRemoval(null);
    }
    setSelectedId((current) => model.modules.some((module) => module.subtopics.some((subtopic) => subtopic.id === current)) ? current : model.modules[0]?.subtopics[0]?.id ?? "");
  }, [conflict, editing, model, operations.length]);
  useEffect(() => onDirtyChange?.(operations.length > 0), [onDirtyChange, operations.length]);
  useEffect(() => {
    if (serverError || serverIssues.length) errorSummaryRef.current?.focus();
  }, [serverError, serverIssues]);
  useEffect(() => {
    setImpactAcknowledged(false);
    setPreviewedBatchSignature(preview ? JSON.stringify(operations) : "");
  // The operation snapshot is intentionally captured only when a new backend preview arrives.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preview]);

  const allSubtopics = useMemo(() => draft.modules.flatMap((module) => module.subtopics), [draft.modules]);
  const allConcepts = useMemo(() => allSubtopics.flatMap((subtopic) => subtopic.concepts), [allSubtopics]);
  const selectedLocation = useMemo(() => {
    for (const module of draft.modules) {
      const subtopic = module.subtopics.find((item) => item.id === selectedId);
      if (subtopic) return { module, subtopic };
    }
    return undefined;
  }, [draft.modules, selectedId]);

  const commit = (nextDraft: CourseModelData, nextOperations: CourseModelOperation[]) => {
    const orderedDraft = deriveDraftOrders(nextDraft);
    const compactedOperations = pruneRestoredStructuralOperations(baseModelRef.current, orderedDraft, nextOperations);
    const effectiveOperations = valuesEqual(orderedDraft, baseModelRef.current) ? [] : compactedOperations;
    setDraft(orderedDraft);
    setOperations(effectiveOperations);
    setImpactAcknowledged(false);
    onInvalidatePreview();
  };
  const append = (operation: CourseModelOperation, mutate: (next: CourseModelData) => void) => {
    const next = cloneModel(draft);
    mutate(next);
    commit(next, [...operations, operation]);
  };
  const updateOperation = (
    family: "module" | "subtopic" | "concept" | "coverage",
    targetId: string,
    changes: Record<string, unknown>,
    mutate: (next: CourseModelData) => void,
  ) => {
    const next = cloneModel(draft);
    mutate(next);
    const nextOperations = [...operations];
    const updateName = `update_${family}`;
    const updateIndex = lastMatchingIndex(nextOperations, (operation) => operation.op === updateName && "targetId" in operation && operation.targetId === targetId);
    const merged = {
      ...(updateIndex >= 0 ? nextOperations[updateIndex] : { op: updateName, targetId }),
      ...changes,
    } as unknown as Record<string, unknown>;
    Object.keys(merged).filter((field) => !["op", "targetId"].includes(field)).forEach((field) => {
      if (valuesEqual(merged[field], baselineUpdateValue(baseModelRef.current, operations, family, targetId, field))) delete merged[field];
    });
    if (Object.keys(merged).length === 2) {
      if (updateIndex >= 0) nextOperations.splice(updateIndex, 1);
    } else if (updateIndex >= 0) nextOperations[updateIndex] = merged as unknown as CourseModelOperation;
    else nextOperations.push(merged as unknown as CourseModelOperation);
    commit(next, nextOperations);
  };
  const assignSources = (targetType: "subtopic" | "concept" | "coverage", targetId: string, sourceIds: string[]) => {
    const next = cloneModel(draft);
    for (const subtopic of next.modules.flatMap((module) => module.subtopics)) {
      if (targetType === "subtopic" && subtopic.id === targetId) subtopic.approvedSourceIds = sourceIds;
      if (targetType === "concept") subtopic.concepts.forEach((concept) => { if (concept.id === targetId) concept.sourceIds = sourceIds; });
      if (targetType === "coverage") subtopic.coverageRequirements.forEach((coverage) => { if (coverage.id === targetId) coverage.sourceIds = sourceIds; });
    }
    const nextOperations = [...operations];
    const index = lastMatchingIndex(nextOperations, (operation) => operation.op === "assign_sources" && operation.targetType === targetType && operation.targetId === targetId);
    const operation: CourseModelOperation = { op: "assign_sources", targetType, targetId, sourceIds };
    const family = targetType === "coverage" ? "coverage" : targetType;
    const baseRecord = editableRecord(baseModelRef.current, family, targetId);
    const baseSources = baseRecord?.[targetType === "subtopic" ? "approvedSourceIds" : "sourceIds"] ?? [];
    if (valuesEqual(sourceIds, baseSources)) {
      if (index >= 0) nextOperations.splice(index, 1);
    } else if (index >= 0) nextOperations[index] = operation;
    else nextOperations.push(operation);
    commit(next, nextOperations);
  };

  const setOutcomeLinks = (targetId: string | undefined, outcomeIds: string[]) => {
    const next = cloneModel(draft);
    const nextOperations = [...operations];
    const operation = targetId
      ? { op: "set_rationale_outcome_links" as const, targetId, outcomeIds }
      : { op: "set_course_outcome_links" as const, outcomeIds };
    if (targetId) next.rationales.find((item) => item.id === targetId)!.relatedOutcomeIds = outcomeIds;
    else next.courseOutcomeIds = outcomeIds;
    const index = lastMatchingIndex(nextOperations, (item) =>
      item.op === operation.op
      && (item.op !== "set_rationale_outcome_links" || item.targetId === targetId),
    );
    const baseIds = targetId
      ? baseModelRef.current.rationales.find((item) => item.id === targetId)?.relatedOutcomeIds ?? []
      : baseModelRef.current.courseOutcomeIds;
    if (valuesEqual(outcomeIds, baseIds)) {
      if (index >= 0) nextOperations.splice(index, 1);
    } else if (index >= 0) nextOperations[index] = operation;
    else nextOperations.push(operation);
    commit(next, nextOperations);
  };

  const addModule = () => {
    const moduleRef = refPrefix("module");
    const subtopicRef = refPrefix("subtopic");
    const next = cloneModel(draft);
    const module: CourseModule = { id: moduleRef, order: next.modules.length + 1, title: "New module", purpose: "Describe why this module belongs in the course.", inScope: ["Define the included learning boundary."], outOfScope: ["Define an excluded boundary."], prerequisiteModuleIds: [], subtopics: [] };
    const subtopic: Subtopic = { id: subtopicRef, order: 1, title: "New subtopic", purpose: "Describe what learners will achieve in this subtopic.", inScope: ["Define the included learning boundary."], outOfScope: ["Define an excluded boundary."], prerequisiteSubtopicIds: [], concepts: [], coverageRequirements: [], approvedSourceIds: [] };
    module.subtopics.push(subtopic);
    next.modules.push(module);
    commit(next, [...operations,
      { op: "add_module", clientRef: moduleRef, position: next.modules.length, title: module.title, purpose: module.purpose, inScope: module.inScope, outOfScope: module.outOfScope, prerequisiteModuleIds: [] },
      { op: "add_subtopic", clientRef: subtopicRef, parentId: moduleRef, position: 1, title: subtopic.title, purpose: subtopic.purpose, inScope: subtopic.inScope, outOfScope: subtopic.outOfScope, prerequisiteSubtopicIds: [] },
    ]);
    setSelectedId(subtopicRef);
  };
  const addSubtopic = (moduleId: string) => {
    const clientRef = refPrefix("subtopic");
    const next = cloneModel(draft);
    const module = next.modules.find((item) => item.id === moduleId)!;
    const subtopic: Subtopic = { id: clientRef, order: module.subtopics.length + 1, title: "New subtopic", purpose: "Describe what learners will achieve in this subtopic.", inScope: ["Define the included learning boundary."], outOfScope: ["Define an excluded boundary."], prerequisiteSubtopicIds: [], concepts: [], coverageRequirements: [], approvedSourceIds: [] };
    module.subtopics.push(subtopic);
    commit(next, [...operations, { op: "add_subtopic", clientRef, parentId: moduleId, position: module.subtopics.length, title: subtopic.title, purpose: subtopic.purpose, inScope: subtopic.inScope, outOfScope: subtopic.outOfScope, prerequisiteSubtopicIds: [] }]);
    setSelectedId(clientRef);
  };
  const addConcept = (subtopicId: string) => {
    const clientRef = refPrefix("concept");
    append({ op: "add_concept", clientRef, parentId: subtopicId, position: (selectedLocation?.subtopic.concepts.length ?? 0) + 1, name: "New concept", summary: "Describe the learner-facing concept.", dependsOn: [] }, (next) => {
      const subtopic = next.modules.flatMap((module) => module.subtopics).find((item) => item.id === subtopicId)!;
      subtopic.concepts.push({ id: clientRef, name: "New concept", summary: "Describe the learner-facing concept.", dependsOn: [], sourceIds: [] });
    });
  };
  const addCoverage = (subtopicId: string) => {
    const clientRef = refPrefix("coverage");
    append({ op: "add_coverage", clientRef, parentId: subtopicId, position: (selectedLocation?.subtopic.coverageRequirements.length ?? 0) + 1, statement: "Describe the required learner coverage.", conceptIds: [] }, (next) => {
      const subtopic = next.modules.flatMap((module) => module.subtopics).find((item) => item.id === subtopicId)!;
      subtopic.coverageRequirements.push({ id: clientRef, statement: "Describe the required learner coverage.", conceptIds: [], sourceIds: [] });
    });
  };

  const reorderModule = (moduleId: string, delta: number) => {
    const from = draft.modules.findIndex((module) => module.id === moduleId);
    const to = from + delta;
    if (from < 0 || to < 0 || to >= draft.modules.length) return;
    const reordered = moveItem(draft.modules, from, to);
    const nextOperations = operations.filter((operation) => operation.op !== "reorder_modules");
    const next = cloneModel(draft);
    next.modules = reordered.map((module, index) => ({ ...module, order: index + 1 }));
    commit(next, [...nextOperations, { op: "reorder_modules", moduleIds: reordered.map((module) => module.id) }]);
  };
  const moveModule = (moduleId: string, position: number) => {
    const from = draft.modules.findIndex((module) => module.id === moduleId);
    const to = position - 1;
    if (from < 0 || from === to) return;
    const reordered = moveItem(draft.modules, from, to);
    const nextOperations = operations.filter((operation) => !(operation.op === "move_module" && operation.targetId === moduleId));
    const next = cloneModel(draft);
    next.modules = reordered.map((module, index) => ({ ...module, order: index + 1 }));
    commit(next, [...nextOperations, { op: "move_module", targetId: moduleId, position }]);
  };
  const reorderSubtopic = (moduleId: string, subtopicId: string, delta: number) => {
    const module = draft.modules.find((item) => item.id === moduleId)!;
    const from = module.subtopics.findIndex((subtopic) => subtopic.id === subtopicId);
    const to = from + delta;
    if (from < 0 || to < 0 || to >= module.subtopics.length) return;
    const reordered = moveItem(module.subtopics, from, to);
    const nextOperations = operations.filter((operation) => !(operation.op === "reorder_subtopics" && operation.parentId === moduleId));
    const next = cloneModel(draft);
    next.modules.find((item) => item.id === moduleId)!.subtopics = reordered.map((subtopic, index) => ({ ...subtopic, order: index + 1 }));
    commit(next, [...nextOperations, { op: "reorder_subtopics", parentId: moduleId, subtopicIds: reordered.map((subtopic) => subtopic.id) }]);
  };
  const moveSubtopic = (subtopicId: string, parentId: string, position: number) => {
    const nextOperations = operations.filter((operation) => !(operation.op === "move_subtopic" && operation.targetId === subtopicId));
    const next = cloneModel(draft);
    {
      let moving: Subtopic | undefined;
      next.modules.forEach((module) => {
        const index = module.subtopics.findIndex((subtopic) => subtopic.id === subtopicId);
        if (index >= 0) [moving] = module.subtopics.splice(index, 1);
      });
      const destination = next.modules.find((module) => module.id === parentId)!;
      destination.subtopics.splice(Math.max(0, position - 1), 0, moving!);
      next.modules.forEach((module) => module.subtopics.forEach((subtopic, index) => { subtopic.order = index + 1; }));
    }
    commit(next, [...nextOperations, { op: "move_subtopic", targetId: subtopicId, parentId, position }]);
  };

  const confirmRemoval = () => {
    if (!removal) return;
    const opName = `remove_${removal.type}` as CourseModelOperation["op"];
    const removedIds = new Set([removal.id]);
    if (removal.type === "module") {
      const module = draft.modules.find((item) => item.id === removal.id);
      module?.subtopics.forEach((subtopic) => {
        removedIds.add(subtopic.id);
        subtopic.concepts.forEach((concept) => removedIds.add(concept.id));
        subtopic.coverageRequirements.forEach((coverage) => removedIds.add(coverage.id));
      });
    }
    if (removal.type === "subtopic") {
      const subtopic = allSubtopics.find((item) => item.id === removal.id);
      subtopic?.concepts.forEach((concept) => removedIds.add(concept.id));
      subtopic?.coverageRequirements.forEach((coverage) => removedIds.add(coverage.id));
    }
    const next = cloneModel(draft);
    if (removal.type === "module") next.modules = next.modules.filter((module) => module.id !== removal.id);
    next.modules.forEach((module) => {
      if (removal.type === "subtopic") module.subtopics = module.subtopics.filter((subtopic) => subtopic.id !== removal.id);
      module.subtopics.forEach((subtopic) => {
        if (removal.type === "concept") subtopic.concepts = subtopic.concepts.filter((concept) => concept.id !== removal.id);
        if (removal.type === "coverage") subtopic.coverageRequirements = subtopic.coverageRequirements.filter((coverage) => coverage.id !== removal.id);
      });
    });
    const retainedOperations = operations.filter((operation) => {
      if ("targetId" in operation && removedIds.has(operation.targetId)) return false;
      if ("clientRef" in operation && removedIds.has(operation.clientRef)) return false;
      if ("parentId" in operation && removedIds.has(operation.parentId)) return false;
      return true;
    });
    const family = removal.type === "coverage" ? "coverage" : removal.type;
    const existedAtEditStart = Boolean(editableRecord(baseModelRef.current, family, removal.id));
    commit(next, existedAtEditStart
      ? [...retainedOperations, { op: opName, targetId: removal.id } as CourseModelOperation]
      : retainedOperations);
    if (removal.type === "subtopic" || removal.type === "module") {
      setSelectedId(next.modules[0]?.subtopics[0]?.id ?? "");
    }
    setRemoval(null);
  };

  if (!editing) {
    const subtopics = model.modules.flatMap((module) => module.subtopics);
    const selected = subtopics.find((subtopic) => subtopic.id === selectedId) ?? subtopics[0];
    return (
      <div className="stage-view model-view">
        <div className="stage-intro"><div><span className="eyebrow">04 · Structural source of truth</span><h1>Course Model</h1><p>Modules, subtopics, coverage, and stable IDs form the compact contract every downstream artifact references.</p></div><div className="stage-intro-aside"><div className="model-validation-summary"><span aria-hidden="true">✓</span><div><strong>References valid</strong><small>Structural checks passed</small></div></div>{canEdit ? <button className="button button-secondary" disabled={busy} onClick={onStartEdit}>Edit Course Model</button> : null}</div></div>
        <div className="model-workspace">
          <aside className="model-tree"><div className="tree-heading"><div><span className="micro-label">Course hierarchy</span><strong>{model.modules.length} modules · {subtopics.length} subtopics</strong></div></div>{model.modules.map((module) => <div className="tree-module" key={module.id}><div className="module-row"><div className="module-copy"><code>{module.id}</code><strong>{module.title}</strong></div></div><div className="subtopic-tree">{module.subtopics.map((subtopic) => <button key={subtopic.id} className={selected?.id === subtopic.id ? "active" : ""} onClick={() => setSelectedId(subtopic.id)}><span className="tree-sequence">{String(subtopic.order).padStart(2, "0")}</span><span className="tree-item-copy"><strong>{subtopic.title}</strong><small>{subtopic.approvedSourceIds.length} sources · {subtopic.coverageRequirements.length} requirements</small></span></button>)}</div></div>)}</aside>
          {selected ? <section className="model-detail"><header className="model-detail-head"><div className="model-detail-title"><code>{selected.id}</code><h2>{selected.title}</h2><p>{selected.purpose}</p></div></header><dl className="model-metadata"><div><dt>Prerequisites</dt><dd>{selected.prerequisiteSubtopicIds.join(", ") || "None"}</dd></div><div><dt>Approved sources</dt><dd>{selected.approvedSourceIds.length}</dd></div><div><dt>Coverage</dt><dd>{selected.coverageRequirements.length}</dd></div></dl><section className="detail-section"><h3>Scope contract</h3><p><strong>In scope:</strong> {selected.inScope.join(", ")}</p><p><strong>Out of scope:</strong> {selected.outOfScope.join(", ")}</p></section><section className="detail-section"><h3>Concepts</h3>{selected.concepts.map((concept) => <p key={concept.id}><code>{concept.id}</code> <strong>{concept.name}</strong> — {concept.summary}</p>)}</section><section className="detail-section"><h3>Coverage requirements</h3>{selected.coverageRequirements.map((coverage) => <p key={coverage.id}><code>{coverage.id}</code> {coverage.statement}</p>)}</section></section> : null}
        </div>
      </div>
    );
  }

  const selected = selectedLocation?.subtopic;
  const selectedModule = selectedLocation?.module;
  const sourceOptions = model.eligibleSources.map((source) => ({ id: source.id, label: `${source.title} (${source.id})` }));
  const outcomeOptions = outcomes.map((outcome) => ({ id: outcome.id, label: `${outcome.id}: ${outcome.statement}` }));
  const operationErrors = new Map<number, CourseModelValidationIssue[]>();
  const previewMatchesOperations = Boolean(preview) && previewedBatchSignature === JSON.stringify(operations);
  const currentPreview = previewMatchesOperations ? preview : null;
  serverIssues.forEach((issue) => {
    if (issue.operationIndex === undefined) return;
    operationErrors.set(issue.operationIndex, [...(operationErrors.get(issue.operationIndex) ?? []), issue]);
  });

  return (
    <div className="stage-view course-model-editor">
      <div className="stage-intro"><div><span className="eyebrow">Typed structural decision</span><h1>Edit Course Model</h1><p>Changes stay local until this exact operation batch passes backend preview and you confirm its impact.</p></div><div className="stage-intro-aside"><div className="operation-count"><strong>{operations.length}</strong><span>typed operation{operations.length === 1 ? "" : "s"}</span></div></div></div>
      {(serverError || serverIssues.length) ? <div ref={errorSummaryRef} className="course-model-error-summary" role="alert" tabIndex={-1}><strong>The operation batch needs attention.</strong>{serverError ? <p>{serverError}</p> : null}<ul>{serverIssues.map((issue, index) => <li key={`${issue.code}:${index}`}>{issue.operationIndex !== undefined ? `Operation ${issue.operationIndex + 1}: ` : ""}{issue.message}</li>)}</ul></div> : null}
      <fieldset className="course-model-edit-fieldset" disabled={busy} aria-busy={busy || undefined}>
      <div className="course-model-edit-grid">
        <aside className="course-model-structure" aria-label="Editable Course Model hierarchy">
          <div className="editor-section-heading"><div><span className="micro-label">Hierarchy</span><strong>Modules and subtopics</strong></div><button className="button button-secondary" disabled={busy} onClick={addModule}>Add module</button></div>
          {draft.modules.map((module, moduleIndex) => <section className="editable-module" key={module.id} aria-label={`Module ${module.title}`}>
            <header><button className="module-select" onClick={() => setSelectedId(module.subtopics[0]?.id ?? "")}><code>{module.id}</code><strong>{module.title}</strong></button><div className="record-actions"><button aria-label={`Reorder module ${module.title} up`} disabled={moduleIndex === 0 || busy} onClick={() => reorderModule(module.id, -1)}>↑</button><button aria-label={`Reorder module ${module.title} down`} disabled={moduleIndex === draft.modules.length - 1 || busy} onClick={() => reorderModule(module.id, 1)}>↓</button><button aria-label={`Remove module ${module.title}`} disabled={busy} onClick={() => setRemoval({ type: "module", id: module.id, label: module.title })}>×</button></div></header>
            <label><span>Module position</span><select aria-label={`Move module ${module.id} to position`} value={moduleIndex + 1} onChange={(event) => moveModule(module.id, Number(event.target.value))}>{draft.modules.map((_, position) => <option key={position + 1} value={position + 1}>{position + 1}</option>)}</select></label>
            <label><span>Module title</span><input aria-label={`Module title for ${module.id}`} aria-invalid={recordError(serverIssues, module.id, "title") || undefined} value={module.title} onChange={(event) => updateOperation("module", module.id, { title: event.target.value }, (next) => { next.modules.find((item) => item.id === module.id)!.title = event.target.value; })} /></label>
            <label><span>Module purpose</span><textarea aria-label={`Module purpose for ${module.id}`} aria-invalid={recordError(serverIssues, module.id, "purpose") || undefined} value={module.purpose} onChange={(event) => updateOperation("module", module.id, { purpose: event.target.value }, (next) => { next.modules.find((item) => item.id === module.id)!.purpose = event.target.value; })} /></label>
            <div className="scope-input-grid"><label><span>Module in scope</span><textarea aria-label={`Module in scope for ${module.id}`} aria-invalid={recordError(serverIssues, module.id, "in_scope") || undefined} value={listText(module.inScope)} onChange={(event) => { const value = parseList(event.target.value); updateOperation("module", module.id, { inScope: value }, (next) => { next.modules.find((item) => item.id === module.id)!.inScope = value; }); }} /></label><label><span>Module out of scope</span><textarea aria-label={`Module out of scope for ${module.id}`} aria-invalid={recordError(serverIssues, module.id, "out_of_scope") || undefined} value={listText(module.outOfScope)} onChange={(event) => { const value = parseList(event.target.value); updateOperation("module", module.id, { outOfScope: value }, (next) => { next.modules.find((item) => item.id === module.id)!.outOfScope = value; }); }} /></label></div>
            <MultiSelect label={`Module prerequisites for ${module.id}`} value={module.prerequisiteModuleIds} options={draft.modules.filter((item) => item.id !== module.id).map((item) => ({ id: item.id, label: item.title }))} invalid={recordError(serverIssues, module.id, "prerequisite_module_ids")} onChange={(value) => updateOperation("module", module.id, { prerequisiteModuleIds: value }, (next) => { next.modules.find((item) => item.id === module.id)!.prerequisiteModuleIds = value; })} />
            <div className="editable-subtopic-list">{module.subtopics.map((subtopic, subtopicIndex) => <div key={subtopic.id} className={selected?.id === subtopic.id ? "active" : ""}><button className="subtopic-select" onClick={() => setSelectedId(subtopic.id)}><span>{subtopicIndex + 1}</span><strong>{subtopic.title}</strong><code>{subtopic.id}</code></button><div className="record-actions"><button aria-label={`Reorder subtopic ${subtopic.title} up`} disabled={subtopicIndex === 0 || busy} onClick={() => reorderSubtopic(module.id, subtopic.id, -1)}>↑</button><button aria-label={`Reorder subtopic ${subtopic.title} down`} disabled={subtopicIndex === module.subtopics.length - 1 || busy} onClick={() => reorderSubtopic(module.id, subtopic.id, 1)}>↓</button><button aria-label={`Remove subtopic ${subtopic.title}`} disabled={busy} onClick={() => setRemoval({ type: "subtopic", id: subtopic.id, label: subtopic.title })}>×</button></div></div>)}</div>
            <button className="button button-quiet add-record" disabled={busy} onClick={() => addSubtopic(module.id)}>Add subtopic to {module.title}</button>
          </section>)}
        </aside>
        <main className="course-model-record-editor">
          {selected && selectedModule ? <>
            <section className="editor-card"><div className="editor-section-heading"><div><span className="micro-label">Selected subtopic</span><h2>{selected.title}</h2><code>{selected.id}</code></div></div>
              <div className="field-grid"><label><span>Subtopic title</span><input aria-label={`Subtopic title for ${selected.id}`} aria-invalid={recordError(serverIssues, selected.id, "title") || undefined} value={selected.title} onChange={(event) => updateOperation("subtopic", selected.id, { title: event.target.value }, (next) => { next.modules.flatMap((module) => module.subtopics).find((item) => item.id === selected.id)!.title = event.target.value; })} /></label><label><span>Parent module</span><select aria-label={`Parent module for ${selected.id}`} value={selectedModule.id} onChange={(event) => moveSubtopic(selected.id, event.target.value, draft.modules.find((module) => module.id === event.target.value)!.subtopics.length + 1)}>{draft.modules.map((module) => <option key={module.id} value={module.id}>{module.title}</option>)}</select></label></div>
              <label><span>Subtopic purpose</span><textarea aria-label={`Subtopic purpose for ${selected.id}`} aria-invalid={recordError(serverIssues, selected.id, "purpose") || undefined} value={selected.purpose} onChange={(event) => updateOperation("subtopic", selected.id, { purpose: event.target.value }, (next) => { next.modules.flatMap((module) => module.subtopics).find((item) => item.id === selected.id)!.purpose = event.target.value; })} /></label>
              <div className="scope-input-grid"><label><span>In scope</span><textarea aria-label={`In scope for ${selected.id}`} aria-invalid={recordError(serverIssues, selected.id, "in_scope") || undefined} value={listText(selected.inScope)} onChange={(event) => { const value = parseList(event.target.value); updateOperation("subtopic", selected.id, { inScope: value }, (next) => { next.modules.flatMap((module) => module.subtopics).find((item) => item.id === selected.id)!.inScope = value; }); }} /></label><label><span>Out of scope</span><textarea aria-label={`Out of scope for ${selected.id}`} aria-invalid={recordError(serverIssues, selected.id, "out_of_scope") || undefined} value={listText(selected.outOfScope)} onChange={(event) => { const value = parseList(event.target.value); updateOperation("subtopic", selected.id, { outOfScope: value }, (next) => { next.modules.flatMap((module) => module.subtopics).find((item) => item.id === selected.id)!.outOfScope = value; }); }} /></label></div>
              <MultiSelect label={`Subtopic prerequisites for ${selected.id}`} value={selected.prerequisiteSubtopicIds} options={allSubtopics.filter((item) => item.id !== selected.id).map((item) => ({ id: item.id, label: item.title }))} invalid={recordError(serverIssues, selected.id, "prerequisite_subtopic_ids")} onChange={(value) => updateOperation("subtopic", selected.id, { prerequisiteSubtopicIds: value }, (next) => { next.modules.flatMap((module) => module.subtopics).find((item) => item.id === selected.id)!.prerequisiteSubtopicIds = value; })} />
              <MultiSelect label={`Approved sources for subtopic ${selected.id}`} value={selected.approvedSourceIds} options={sourceOptions} invalid={recordError(serverIssues, selected.id, "approved_source_ids")} onChange={(value) => assignSources("subtopic", selected.id, value)} />
            </section>
            <section className="editor-card"><div className="editor-section-heading"><div><span className="micro-label">Knowledge structure</span><h2>Concepts</h2></div><button className="button button-secondary" onClick={() => addConcept(selected.id)}>Add concept</button></div>{selected.concepts.map((concept: Concept) => <article className="editable-record" key={concept.id}><header><code>{concept.id}</code><button aria-label={`Remove concept ${concept.name}`} onClick={() => setRemoval({ type: "concept", id: concept.id, label: concept.name })}>Remove</button></header><label><span>Concept name</span><input aria-label={`Concept name for ${concept.id}`} aria-invalid={recordError(serverIssues, concept.id, "name") || undefined} value={concept.name} onChange={(event) => updateOperation("concept", concept.id, { name: event.target.value }, (next) => { next.modules.flatMap((module) => module.subtopics).flatMap((item) => item.concepts).find((item) => item.id === concept.id)!.name = event.target.value; })} /></label><label><span>Concept summary</span><textarea aria-label={`Concept summary for ${concept.id}`} aria-invalid={recordError(serverIssues, concept.id, "summary") || undefined} value={concept.summary} onChange={(event) => updateOperation("concept", concept.id, { summary: event.target.value }, (next) => { next.modules.flatMap((module) => module.subtopics).flatMap((item) => item.concepts).find((item) => item.id === concept.id)!.summary = event.target.value; })} /></label><MultiSelect label={`Dependencies for concept ${concept.id}`} value={concept.dependsOn} options={allConcepts.filter((item) => item.id !== concept.id).map((item) => ({ id: item.id, label: item.name }))} invalid={recordError(serverIssues, concept.id, "depends_on")} onChange={(value) => updateOperation("concept", concept.id, { dependsOn: value }, (next) => { next.modules.flatMap((module) => module.subtopics).flatMap((item) => item.concepts).find((item) => item.id === concept.id)!.dependsOn = value; })} /><MultiSelect label={`Approved sources for concept ${concept.id}`} value={concept.sourceIds} options={sourceOptions} invalid={recordError(serverIssues, concept.id, "source_ids")} onChange={(value) => assignSources("concept", concept.id, value)} /></article>)}</section>
            <section className="editor-card"><div className="editor-section-heading"><div><span className="micro-label">Coverage contract</span><h2>Coverage requirements</h2></div><button className="button button-secondary" onClick={() => addCoverage(selected.id)}>Add coverage requirement</button></div>{selected.coverageRequirements.map((coverage) => <article className="editable-record" key={coverage.id}><header><code>{coverage.id}</code><button aria-label={`Remove coverage ${coverage.statement}`} onClick={() => setRemoval({ type: "coverage", id: coverage.id, label: coverage.statement })}>Remove</button></header><label><span>Coverage statement</span><textarea aria-label={`Coverage statement for ${coverage.id}`} aria-invalid={recordError(serverIssues, coverage.id, "statement") || undefined} value={coverage.statement} onChange={(event) => updateOperation("coverage", coverage.id, { statement: event.target.value }, (next) => { next.modules.flatMap((module) => module.subtopics).flatMap((item) => item.coverageRequirements).find((item) => item.id === coverage.id)!.statement = event.target.value; })} /></label><MultiSelect label={`Concept references for coverage ${coverage.id}`} value={coverage.conceptIds} options={selected.concepts.map((concept) => ({ id: concept.id, label: concept.name }))} invalid={recordError(serverIssues, coverage.id, "concept_ids")} onChange={(value) => updateOperation("coverage", coverage.id, { conceptIds: value }, (next) => { next.modules.flatMap((module) => module.subtopics).flatMap((item) => item.coverageRequirements).find((item) => item.id === coverage.id)!.conceptIds = value; })} /><MultiSelect label={`Approved sources for coverage ${coverage.id}`} value={coverage.sourceIds} options={sourceOptions} invalid={recordError(serverIssues, coverage.id, "source_ids")} onChange={(value) => assignSources("coverage", coverage.id, value)} /></article>)}</section>
          </> : <div className="editor-card"><h2>Select a subtopic</h2><p>Choose a retained subtopic or add a new one.</p></div>}
          <section className="editor-card"><div className="editor-section-heading"><div><span className="micro-label">Supported links</span><h2>Course Outcomes</h2></div></div><OutcomeOrder value={draft.courseOutcomeIds} options={outcomeOptions} invalid={fieldError(serverIssues, "course_outcome_ids")} onChange={(value) => setOutcomeLinks(undefined, value)} />{draft.rationales.map((rationale) => <MultiSelect key={rationale.id} label={`Outcome links for rationale ${rationale.id}`} value={rationale.relatedOutcomeIds} options={outcomeOptions} invalid={recordError(serverIssues, rationale.id, "related_outcome_ids")} onChange={(value) => setOutcomeLinks(rationale.id, value)} />)}</section>
        </main>
        <aside className="course-model-preview-panel" aria-label="Course Model operation preview">
          <div className="editor-section-heading"><div><span className="micro-label">Ordered operation batch</span><h2>Review and validate</h2></div></div>
          {operations.length ? <ol className="operation-ledger">{operations.map((operation, index) => <li key={`${operation.op}:${index}`} className={operationErrors.has(index) ? "invalid" : ""}><strong>{operation.op.replaceAll("_", " ")}</strong><code>{"targetId" in operation ? operation.targetId : "clientRef" in operation ? operation.clientRef : "batch"}</code>{operationErrors.get(index)?.map((issue) => <span key={issue.code}>{issue.message}</span>)}</li>)}</ol> : <p className="muted">Use the typed controls to build a decision batch.</p>}
          <button className="button button-primary full-width" disabled={!operations.length || busy || conflict} onClick={() => onPreview(operations)}>{busy ? "Validating…" : currentPreview ? "Preview again" : "Preview impact"}</button>
          {currentPreview ? <section className="course-model-preview-result" aria-live="polite">
            <div className="preview-ready"><span aria-hidden="true">✓</span><div><strong>Backend validation passed</strong><small>This preview is bound to the current artifact and operation batch.</small></div></div>
            <dl><div><dt>Allocated IDs</dt><dd>{Object.keys(currentPreview.allocatedIds).length || "None"}</dd></div><div><dt>Affected families</dt><dd>{Object.keys(currentPreview.affectedRecords).length}</dd></div><div><dt>Downstream stages</dt><dd>{currentPreview.impact.requiresRerunStages.length}</dd></div></dl>
            {Object.keys(currentPreview.allocatedIds).length ? <ul>{Object.entries(currentPreview.allocatedIds).map(([local, canonical]) => <li key={local}><code>{local}</code> → <code>{canonical}</code></li>)}</ul> : null}
            <CourseModelDiff original={baseModelRef.current} preview={currentPreview} />
            <p><strong>Downstream impact:</strong> {currentPreview.impact.staleArtifacts.map((item) => item.replaceAll("_", " ")).join(", ") || "No existing downstream artifacts"}</p>
            {currentPreview.impact.warnings.map((warning) => <p className="preview-warning" key={warning}>{warning}</p>)}
            <label className="impact-ack"><input type="checkbox" checked={impactAcknowledged} onChange={(event) => setImpactAcknowledged(event.target.checked)} /><span>I reviewed the detailed structural diff, allocated IDs, warnings, and downstream impact for this current preview.</span></label>
            <button className="button button-primary full-width" disabled={!impactAcknowledged || busy} onClick={() => onSave(operations, currentPreview.impact.impactChecksum)}>{busy ? "Saving canonical draft…" : "Save Course Model draft"}</button>
          </section> : null}
          <button className="button button-quiet full-width" disabled={busy} onClick={() => { if (!operations.length || window.confirm("Discard all unsaved Course Model changes?")) onCancel(); }}>Cancel editing</button>
          <p className="separate-approval-note">Saving creates a canonical draft. Approval remains a separate checkpoint in the stage action bar.</p>
        </aside>
      </div>
      </fieldset>
      <div className="sr-status" role="status" aria-live="polite">{busy ? "Course Model request in progress." : currentPreview ? "Course Model detailed preview is ready for acknowledgement." : operations.length ? `${operations.length} unsaved Course Model operations.` : "Course Model editor ready."}</div>
      {removal ? <Modal title={`Remove ${removal.label}?`} confirmLabel="Remove record" busy={busy} onCancel={() => setRemoval(null)} onConfirm={confirmRemoval}><p>This typed removal may also remove contained records. Backend validation will reject unresolved references before anything is saved.</p></Modal> : null}
      {conflict ? <Modal title="The Course Model changed elsewhere" cancelLabel="Discard local work" confirmLabel="Reapply operation batch" busy={busy} onCancel={() => onRecoverConflict("discard")} onConfirm={() => onRecoverConflict("reapply")}><p>The latest canonical Course Model is shown below for comparison. No structural operations were merged or submitted automatically.</p><div className="course-model-conflict-latest"><strong>Latest server structure</strong><p>{model.modules.length} modules · {model.modules.reduce((count, module) => count + module.subtopics.length, 0)} subtopics</p><ul>{model.modules.map((module) => <li key={module.id}><code>{module.id}</code> {module.title}<ul>{module.subtopics.map((subtopic) => <li key={subtopic.id}><code>{subtopic.id}</code> {subtopic.title}</li>)}</ul></li>)}</ul></div><p>Reapply keeps your ordered local batch against the latest checksum, but you must inspect the records and run a new preview before save. Discard removes the local batch and shows this latest server state.</p></Modal> : null}
    </div>
  );
}
