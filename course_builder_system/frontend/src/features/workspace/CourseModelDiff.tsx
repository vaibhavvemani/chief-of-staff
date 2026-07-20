import type {
  CourseModelData,
  CourseModelPreview,
} from "../../types";

type StructuralFamily = "module" | "subtopic" | "concept" | "coverage";

interface RecordSnapshot {
  family: StructuralFamily;
  id: string;
  label: string;
  parentId?: string;
  parentLabel?: string;
  order?: number;
  purpose?: string;
  inScope?: string[];
  outOfScope?: string[];
  sourceIds: string[];
  hierarchyIndex: number;
}

export interface CourseModelDiffValue {
  field: string;
  before: string;
  after: string;
}

export interface CourseModelDiffEntry {
  family: StructuralFamily;
  id: string;
  label: string;
  clientRef?: string;
  location?: string;
  cascaded?: boolean;
  values: CourseModelDiffValue[];
  addedSources: string[];
  removedSources: string[];
  sortOrder: number;
}

export interface CourseModelDetailedDiff {
  added: CourseModelDiffEntry[];
  removed: CourseModelDiffEntry[];
  renamed: CourseModelDiffEntry[];
  moved: CourseModelDiffEntry[];
  scope: CourseModelDiffEntry[];
  sources: CourseModelDiffEntry[];
  total: number;
}

const familyLabels: Record<StructuralFamily, string> = {
  module: "Module",
  subtopic: "Subtopic",
  concept: "Concept",
  coverage: "Coverage requirement",
};

function recordKey(family: StructuralFamily, id: string): string {
  return `${family}:${id}`;
}

function collectSnapshots(model: CourseModelData): Map<string, RecordSnapshot> {
  const records = new Map<string, RecordSnapshot>();
  let hierarchyIndex = 0;
  model.modules.forEach((module) => {
    records.set(recordKey("module", module.id), {
      family: "module",
      id: module.id,
      label: module.title,
      order: module.order,
      purpose: module.purpose,
      inScope: module.inScope,
      outOfScope: module.outOfScope,
      sourceIds: [],
      hierarchyIndex: hierarchyIndex++,
    });
    module.subtopics.forEach((subtopic) => {
      records.set(recordKey("subtopic", subtopic.id), {
        family: "subtopic",
        id: subtopic.id,
        label: subtopic.title,
        parentId: module.id,
        parentLabel: module.title,
        order: subtopic.order,
        purpose: subtopic.purpose,
        inScope: subtopic.inScope,
        outOfScope: subtopic.outOfScope,
        sourceIds: subtopic.approvedSourceIds,
        hierarchyIndex: hierarchyIndex++,
      });
      subtopic.concepts.forEach((concept) => {
        records.set(recordKey("concept", concept.id), {
          family: "concept",
          id: concept.id,
          label: concept.name,
          parentId: subtopic.id,
          parentLabel: subtopic.title,
          sourceIds: concept.sourceIds,
          hierarchyIndex: hierarchyIndex++,
        });
      });
      subtopic.coverageRequirements.forEach((coverage) => {
        records.set(recordKey("coverage", coverage.id), {
          family: "coverage",
          id: coverage.id,
          label: coverage.statement,
          parentId: subtopic.id,
          parentLabel: subtopic.title,
          sourceIds: coverage.sourceIds,
          hierarchyIndex: hierarchyIndex++,
        });
      });
    });
  });
  return records;
}

function formatList(values: string[] | undefined): string {
  return values?.length ? values.join("; ") : "None";
}

function formatLocation(record: RecordSnapshot): string | undefined {
  if (record.family === "module") return `Position ${record.order}`;
  if (record.family === "subtopic") {
    return `${record.parentLabel ?? record.parentId ?? "Unknown module"} · position ${record.order}`;
  }
  return record.parentLabel ? `Within ${record.parentLabel}` : undefined;
}

function compareArrays(left: string[] | undefined, right: string[] | undefined): boolean {
  return JSON.stringify(left ?? []) === JSON.stringify(right ?? []);
}

function structuralFamily(value: string): value is StructuralFamily {
  return value === "module" || value === "subtopic" || value === "concept" || value === "coverage";
}

function entry(
  record: RecordSnapshot,
  sortOrder: number,
  extras: Partial<CourseModelDiffEntry> = {},
): CourseModelDiffEntry {
  return {
    family: record.family,
    id: record.id,
    label: record.label,
    location: formatLocation(record),
    values: [],
    addedSources: [],
    removedSources: [],
    sortOrder,
    ...extras,
  };
}

function orderEntries(entries: CourseModelDiffEntry[]): CourseModelDiffEntry[] {
  return entries.sort((left, right) => left.sortOrder - right.sortOrder || left.label.localeCompare(right.label));
}

export function buildCourseModelDiff(
  original: CourseModelData,
  preview: CourseModelPreview,
): CourseModelDetailedDiff {
  const before = collectSnapshots(original);
  const after = collectSnapshots(preview.candidate);
  const operationOrder = new Map<string, number>();
  let nextOrder = 0;
  [...preview.changeRecords]
    .sort((left, right) => left.operationIndex - right.operationIndex)
    .forEach((change) => {
      if (!structuralFamily(change.recordType)) return;
      const ids = change.recordId ? [change.recordId] : change.recordIds;
      ids.forEach((id) => {
        const key = recordKey(change.recordType as StructuralFamily, id);
        if (!operationOrder.has(key)) operationOrder.set(key, nextOrder++);
      });
    });
  const fallbackOrder = (record: RecordSnapshot) => 10_000 + record.hierarchyIndex;
  const sortOrder = (record: RecordSnapshot) => operationOrder.get(recordKey(record.family, record.id)) ?? fallbackOrder(record);
  const directlyRemoved = new Set(
    preview.changeRecords.flatMap((change) =>
      change.action === "removed" && change.recordId && structuralFamily(change.recordType)
        ? [recordKey(change.recordType, change.recordId)]
        : [],
    ),
  );
  const clientRefByCanonicalId = new Map(
    Object.entries(preview.allocatedIds).map(([clientRef, canonicalId]) => [canonicalId, clientRef]),
  );
  const sourceLabels = new Map(
    [...original.eligibleSources, ...preview.candidate.eligibleSources].map((source) => [
      source.id,
      `${source.title} (${source.id})`,
    ]),
  );
  const sourceLabel = (id: string) => sourceLabels.get(id) ?? id;

  const added: CourseModelDiffEntry[] = [];
  const removed: CourseModelDiffEntry[] = [];
  const renamed: CourseModelDiffEntry[] = [];
  const moved: CourseModelDiffEntry[] = [];
  const scope: CourseModelDiffEntry[] = [];
  const sources: CourseModelDiffEntry[] = [];

  (["module", "subtopic", "concept", "coverage"] as StructuralFamily[]).forEach((family) => {
    const confirmed = preview.affectedRecords[family];
    const changedIds = new Set(confirmed?.changedIds ?? []);
    const removedIds = new Set(confirmed?.removedIds ?? []);

    changedIds.forEach((id) => {
      const current = after.get(recordKey(family, id));
      if (!current) return;
      const prior = before.get(recordKey(family, id));
      if (!prior) {
        added.push(entry(current, sortOrder(current), { clientRef: clientRefByCanonicalId.get(id) }));
        return;
      }

      if (prior.label !== current.label) {
        renamed.push(entry(current, sortOrder(current), {
          values: [{ field: family === "coverage" ? "Statement" : "Name", before: prior.label, after: current.label }],
        }));
      }

      if (
        (family === "module" || family === "subtopic")
        && (prior.parentId !== current.parentId || prior.order !== current.order)
      ) {
        moved.push(entry(current, sortOrder(current), {
          values: [{
            field: prior.parentId !== current.parentId ? "Module and position" : "Position",
            before: formatLocation(prior) ?? "Unknown",
            after: formatLocation(current) ?? "Unknown",
          }],
        }));
      }

      if (family === "module" || family === "subtopic") {
        const values: CourseModelDiffValue[] = [];
        if (prior.purpose !== current.purpose) {
          values.push({ field: "Purpose", before: prior.purpose ?? "None", after: current.purpose ?? "None" });
        }
        if (!compareArrays(prior.inScope, current.inScope)) {
          values.push({ field: "In scope", before: formatList(prior.inScope), after: formatList(current.inScope) });
        }
        if (!compareArrays(prior.outOfScope, current.outOfScope)) {
          values.push({ field: "Out of scope", before: formatList(prior.outOfScope), after: formatList(current.outOfScope) });
        }
        if (values.length) scope.push(entry(current, sortOrder(current), { values }));
      }

      if (!compareArrays(prior.sourceIds, current.sourceIds)) {
        const priorIds = new Set(prior.sourceIds);
        const currentIds = new Set(current.sourceIds);
        sources.push(entry(current, sortOrder(current), {
          addedSources: current.sourceIds.filter((id) => !priorIds.has(id)).map(sourceLabel),
          removedSources: prior.sourceIds.filter((id) => !currentIds.has(id)).map(sourceLabel),
        }));
      }
    });

    removedIds.forEach((id) => {
      const prior = before.get(recordKey(family, id));
      if (!prior) return;
      removed.push(entry(prior, sortOrder(prior), {
        cascaded: !directlyRemoved.has(recordKey(family, id)),
      }));
    });
  });

  const categories = [added, removed, renamed, moved, scope, sources];
  return {
    added: orderEntries(added),
    removed: orderEntries(removed),
    renamed: orderEntries(renamed),
    moved: orderEntries(moved),
    scope: orderEntries(scope),
    sources: orderEntries(sources),
    total: categories.reduce((count, category) => count + category.length, 0),
  };
}

function DiffCategory({
  title,
  entries,
  tone,
}: {
  title: string;
  entries: CourseModelDiffEntry[];
  tone: string;
}) {
  if (!entries.length) return null;
  return (
    <section className={`course-model-diff-category diff-${tone}`} aria-label={`${title}: ${entries.length}`}>
      <header><h4>{title}</h4><span>{entries.length}</span></header>
      <ul>
        {entries.map((item) => (
          <li key={`${title}:${item.family}:${item.id}`}>
            <div className="course-model-diff-record">
              <div><strong>{item.label}</strong><span>{familyLabels[item.family]}</span></div>
              <code>{item.id}</code>
            </div>
            {item.clientRef ? <p className="course-model-diff-ref"><code>{item.clientRef}</code> → <code>{item.id}</code></p> : null}
            {item.location ? <p className="course-model-diff-location">{item.location}</p> : null}
            {item.cascaded ? <p className="course-model-diff-cascade">Removed with its parent record</p> : null}
            {item.values.length ? <dl className="course-model-diff-values">{item.values.map((value) => <div key={value.field}><dt>{value.field}</dt><dd><span className="diff-before"><small>Before</small>{value.before}</span><span aria-hidden="true">→</span><span className="diff-after"><small>After</small>{value.after}</span></dd></div>)}</dl> : null}
            {item.addedSources.length ? <p className="course-model-source-change"><strong>Added sources:</strong> {item.addedSources.join(", ")}</p> : null}
            {item.removedSources.length ? <p className="course-model-source-change"><strong>Removed sources:</strong> {item.removedSources.join(", ")}</p> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function CourseModelDiff({
  original,
  preview,
}: {
  original: CourseModelData;
  preview: CourseModelPreview;
}) {
  const diff = buildCourseModelDiff(original, preview);
  const summaries = [
    ["Added", diff.added.length],
    ["Removed", diff.removed.length],
    ["Renamed", diff.renamed.length],
    ["Moved", diff.moved.length],
    ["Purpose/scope", diff.scope.length],
    ["Sources", diff.sources.length],
  ] as const;
  return (
    <section className="course-model-diff" aria-labelledby="course-model-diff-title">
      <header>
        <span className="micro-label">Detailed structural diff</span>
        <h3 id="course-model-diff-title">What will change</h3>
        <p>{preview.changeRecords.length} ordered backend change record{preview.changeRecords.length === 1 ? "" : "s"} produced this validated candidate. Unchanged records are omitted.</p>
      </header>
      {diff.total ? <>
        <dl className="course-model-diff-counts" aria-label="Course Model diff category counts">
          {summaries.filter(([, count]) => count > 0).map(([label, count]) => <div key={label}><dt>{label}</dt><dd>{count}</dd></div>)}
        </dl>
        <div className="course-model-diff-categories">
          <DiffCategory title="Added records" entries={diff.added} tone="added" />
          <DiffCategory title="Removed records" entries={diff.removed} tone="removed" />
          <DiffCategory title="Renamed records" entries={diff.renamed} tone="renamed" />
          <DiffCategory title="Moved or reordered records" entries={diff.moved} tone="moved" />
          <DiffCategory title="Purpose and scope changes" entries={diff.scope} tone="scope" />
          <DiffCategory title="Source-assignment changes" entries={diff.sources} tone="sources" />
        </div>
      </> : <p className="course-model-diff-empty">The validated preview contains no changes in the NC-405 diff categories.</p>}
    </section>
  );
}
