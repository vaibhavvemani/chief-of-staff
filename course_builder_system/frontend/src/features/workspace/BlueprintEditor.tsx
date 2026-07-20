import { useEffect, useMemo, useRef, useState } from "react";
import type {
  BlueprintAssetType,
  BlueprintDecisionDraft,
  BlueprintDepthValues,
  ContentAsset,
  Workspace,
} from "../../types";

const assetCatalog: Array<[BlueprintAssetType, string]> = [
  ["course_content", "Course Content"],
  ["learning_objectives", "Learning Objectives"],
  ["summary", "Summary"],
  ["case_study", "Case Study"],
  ["assessment", "Assessment"],
  ["activities", "Activity"],
  ["resources", "Resources"],
];

const depthFields: Array<keyof BlueprintDepthValues> = [
  "depth",
  "minutes",
  "wordMinimum",
  "wordTarget",
  "wordMaximum",
  "examples",
  "caseDepth",
  "assessmentComplexity",
];

interface BlueprintPlanDraft extends BlueprintDepthValues {
  subtopicId: string;
  selectedAssetTypes: BlueprintAssetType[];
  anchorWaiverConfirmed: boolean;
}

interface BlueprintEditorDraft {
  defaults: BlueprintDepthValues & { assetTypes: BlueprintAssetType[] };
  plans: BlueprintPlanDraft[];
  rationale: string;
}

export interface BlueprintEditorProps {
  blueprint: Workspace["blueprint"];
  contentAssets: ContentAsset[];
  subtopicNames: Record<string, string>;
  canEdit: boolean;
  editing: boolean;
  busy: boolean;
  conflict: boolean;
  serverError?: string;
  onStartEdit: () => void;
  onCancel: () => void;
  onSave: (decision: BlueprintDecisionDraft) => void;
  onResolveConflict: (choice: "reapply" | "discard") => void;
  onDirtyChange?: (dirty: boolean) => void;
}

function selectedAssets(plan: Workspace["blueprint"]["plans"][number]): BlueprintAssetType[] {
  return plan.assets
    .filter((asset) => asset.selectionStatus === "selected")
    .map((asset) => asset.assetType);
}

function initialDraft(blueprint: Workspace["blueprint"]): BlueprintEditorDraft {
  return {
    defaults: structuredClone(blueprint.defaults),
    plans: blueprint.plans.map((plan) => ({
      subtopicId: plan.subtopicId,
      depth: plan.depth,
      minutes: plan.minutes,
      wordMinimum: plan.wordMinimum,
      wordTarget: plan.wordTarget,
      wordMaximum: plan.wordMaximum,
      examples: plan.examples,
      caseDepth: plan.caseDepth,
      assessmentComplexity: plan.assessmentComplexity,
      selectedAssetTypes: selectedAssets(plan),
      anchorWaiverConfirmed: plan.anchorWaiverConfirmed,
    })),
    rationale: "Human Blueprint checkpoint.",
  };
}

function contractSignature(draft: BlueprintEditorDraft): string {
  return JSON.stringify({ defaults: draft.defaults, plans: draft.plans });
}

function sameAssets(left: BlueprintAssetType[], right: BlueprintAssetType[]): boolean {
  return left.length === right.length && left.every((value) => right.includes(value));
}

function validRange(values: Pick<BlueprintDepthValues, "wordMinimum" | "wordTarget" | "wordMaximum">): boolean {
  return values.wordMinimum >= 0
    && values.wordTarget >= 1
    && values.wordMaximum >= 1
    && values.wordMinimum <= values.wordTarget
    && values.wordTarget <= values.wordMaximum;
}

function decisionFromDraft(draft: BlueprintEditorDraft): BlueprintDecisionDraft {
  const selectedAssetTypes = Object.fromEntries(
    draft.plans.flatMap((plan) => sameAssets(plan.selectedAssetTypes, draft.defaults.assetTypes)
      ? []
      : [[plan.subtopicId, plan.selectedAssetTypes]]),
  );
  const depthOverrides = Object.fromEntries(
    draft.plans.flatMap((plan) => {
      const override = Object.fromEntries(
        depthFields.flatMap((field) => plan[field] === draft.defaults[field]
          ? []
          : [[field, plan[field]]]),
      ) as Partial<BlueprintDepthValues>;
      if (override.wordMinimum !== undefined || override.wordTarget !== undefined || override.wordMaximum !== undefined) {
        override.wordMinimum = plan.wordMinimum;
        override.wordTarget = plan.wordTarget;
        override.wordMaximum = plan.wordMaximum;
      }
      return Object.keys(override).length ? [[plan.subtopicId, override]] : [];
    }),
  );
  return {
    defaultAssetTypes: draft.defaults.assetTypes,
    defaultDepth: {
      depth: draft.defaults.depth,
      minutes: draft.defaults.minutes,
      wordMinimum: draft.defaults.wordMinimum,
      wordTarget: draft.defaults.wordTarget,
      wordMaximum: draft.defaults.wordMaximum,
      examples: draft.defaults.examples,
      caseDepth: draft.defaults.caseDepth,
      assessmentComplexity: draft.defaults.assessmentComplexity,
    },
    selectedAssetTypes,
    depthOverrides,
    anchorWaivers: draft.plans
      .filter((plan) => !plan.selectedAssetTypes.includes("course_content") && plan.anchorWaiverConfirmed)
      .map((plan) => plan.subtopicId),
    rationale: draft.rationale.trim(),
  };
}

function depthInputs(
  values: BlueprintDepthValues,
  prefix: string,
  onChange: (field: keyof BlueprintDepthValues, value: string | number) => void,
) {
  const rangeInvalid = !validRange(values);
  return <div className="blueprint-depth-fields">
    <label><span>Depth</span><select aria-label={`${prefix} depth`} value={values.depth} onChange={(event) => onChange("depth", event.target.value)}><option value="introductory">Introductory</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option><option value="custom">Custom</option></select></label>
    <label><span>Learning time (minutes)</span><input aria-label={`${prefix} learning time`} type="number" min="1" value={values.minutes} onChange={(event) => onChange("minutes", Number(event.target.value))} /></label>
    <label><span>Minimum words</span><input aria-label={`${prefix} minimum words`} aria-invalid={rangeInvalid || undefined} type="number" min="0" value={values.wordMinimum} onChange={(event) => onChange("wordMinimum", Number(event.target.value))} /></label>
    <label><span>Target words</span><input aria-label={`${prefix} target words`} aria-invalid={rangeInvalid || undefined} type="number" min="1" value={values.wordTarget} onChange={(event) => onChange("wordTarget", Number(event.target.value))} /></label>
    <label><span>Maximum words</span><input aria-label={`${prefix} maximum words`} aria-invalid={rangeInvalid || undefined} type="number" min="1" value={values.wordMaximum} onChange={(event) => onChange("wordMaximum", Number(event.target.value))} /></label>
    <label><span>Required examples</span><input aria-label={`${prefix} required examples`} type="number" min="0" value={values.examples} onChange={(event) => onChange("examples", Number(event.target.value))} /></label>
    <label><span>Case depth</span><select aria-label={`${prefix} case depth`} value={values.caseDepth} onChange={(event) => onChange("caseDepth", event.target.value)}><option value="none">None</option><option value="brief">Brief</option><option value="detailed">Detailed</option></select></label>
    <label><span>Assessment complexity</span><select aria-label={`${prefix} assessment complexity`} value={values.assessmentComplexity} onChange={(event) => onChange("assessmentComplexity", event.target.value)}><option value="none">None</option><option value="recall">Recall</option><option value="application">Application</option><option value="analysis">Analysis</option></select></label>
  </div>;
}

export function BlueprintEditor({
  blueprint,
  contentAssets,
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
}: BlueprintEditorProps) {
  const [draft, setDraft] = useState(() => initialDraft(blueprint));
  const [acknowledged, setAcknowledged] = useState(false);
  const baselineRef = useRef(contractSignature(initialDraft(blueprint)));
  const conflictReviewRef = useRef<HTMLButtonElement>(null);
  const dirty = contractSignature(draft) !== baselineRef.current;

  useEffect(() => {
    if (editing && dirty) return;
    const next = initialDraft(blueprint);
    baselineRef.current = contractSignature(next);
    setDraft(next);
    setAcknowledged(false);
  }, [blueprint, dirty, editing]);
  useEffect(() => onDirtyChange?.(editing && dirty), [dirty, editing, onDirtyChange]);
  useEffect(() => {
    if (conflict) conflictReviewRef.current?.focus();
  }, [conflict]);

  const originalSelected = useMemo(() => new Set(
    blueprint.plans.flatMap((plan) => plan.assets
      .filter((asset) => asset.selectionStatus === "selected")
      .map((asset) => asset.id)),
  ), [blueprint.plans]);
  const nextSelected = useMemo(() => new Set(
    draft.plans.flatMap((plan) => {
      const original = blueprint.plans.find((item) => item.subtopicId === plan.subtopicId);
      return original?.assets
        .filter((asset) => plan.selectedAssetTypes.includes(asset.assetType))
        .map((asset) => asset.id) ?? [];
    }),
  ), [blueprint.plans, draft.plans]);
  const addedAssets = [...nextSelected].filter((id) => !originalSelected.has(id));
  const removedAssets = [...originalSelected].filter((id) => !nextSelected.has(id));
  const errors = [
    ...(!draft.defaults.assetTypes.length ? ["Course defaults must select at least one asset."] : []),
    ...(!validRange(draft.defaults) ? ["Course default word range must satisfy minimum ≤ target ≤ maximum."] : []),
    ...(draft.defaults.minutes < 1 || draft.defaults.examples < 0 ? ["Course default time and example budgets must be valid."] : []),
    ...draft.plans.flatMap((plan) => [
      ...(!plan.selectedAssetTypes.length ? [`${subtopicNames[plan.subtopicId] ?? plan.subtopicId} must select at least one asset.`] : []),
      ...(!plan.selectedAssetTypes.includes("course_content") && !plan.anchorWaiverConfirmed ? [`${subtopicNames[plan.subtopicId] ?? plan.subtopicId} requires an explicit Course Content anchor waiver.`] : []),
      ...(!validRange(plan) ? [`${subtopicNames[plan.subtopicId] ?? plan.subtopicId} has an invalid word range.`] : []),
      ...(plan.minutes < 1 || plan.examples < 0 ? [`${subtopicNames[plan.subtopicId] ?? plan.subtopicId} has an invalid time or example budget.`] : []),
    ]),
    ...(!draft.rationale.trim() ? ["Record a concise rationale for this Blueprint decision."] : []),
  ];

  const commit = (mutate: (next: BlueprintEditorDraft) => void) => {
    const next = structuredClone(draft);
    mutate(next);
    setDraft(next);
    setAcknowledged(false);
  };
  const toggleDefaultAsset = (assetType: BlueprintAssetType) => commit((next) => {
    const oldDefaults = next.defaults.assetTypes;
    const selected = oldDefaults.includes(assetType)
      ? oldDefaults.filter((value) => value !== assetType)
      : assetCatalog.map(([value]) => value).filter((value) => value === assetType || oldDefaults.includes(value));
    next.plans.forEach((plan) => {
      if (!sameAssets(plan.selectedAssetTypes, oldDefaults)) return;
      plan.selectedAssetTypes = selected;
      if (selected.includes("course_content")) plan.anchorWaiverConfirmed = false;
    });
    next.defaults.assetTypes = selected;
  });
  const changeDefaultDepth = (field: keyof BlueprintDepthValues, value: string | number) => commit((next) => {
    const prior = next.defaults[field];
    next.plans.forEach((plan) => {
      if (plan[field] === prior) (plan as unknown as Record<string, string | number>)[field] = value;
    });
    (next.defaults as unknown as Record<string, string | number>)[field] = value;
  });
  const changePlanDepth = (subtopicId: string, field: keyof BlueprintDepthValues, value: string | number) => commit((next) => {
    const plan = next.plans.find((item) => item.subtopicId === subtopicId)!;
    (plan as unknown as Record<string, string | number>)[field] = value;
  });
  const togglePlanAsset = (subtopicId: string, assetType: BlueprintAssetType) => commit((next) => {
    const plan = next.plans.find((item) => item.subtopicId === subtopicId)!;
    plan.selectedAssetTypes = plan.selectedAssetTypes.includes(assetType)
      ? plan.selectedAssetTypes.filter((value) => value !== assetType)
      : assetCatalog.map(([value]) => value).filter((value) => value === assetType || plan.selectedAssetTypes.includes(value));
    if (assetType === "course_content") plan.anchorWaiverConfirmed = false;
  });

  if (!editing) {
    return canEdit ? <button className="button button-secondary" onClick={onStartEdit}>Edit Blueprint</button> : null;
  }

  return <div className="blueprint-editor">
    <div className="stage-intro"><div><span className="eyebrow">Typed generation decision</span><h1>Edit Blueprint</h1><p>Set the course baseline, keep only deliberate subtopic exceptions, and review exact content reconciliation before saving.</p></div><div className="stage-intro-aside"><strong>{nextSelected.size}</strong><span>selected learner assets</span></div></div>
    {serverError ? <div className="blueprint-error-summary" role="alert"><strong>The Blueprint decision could not be saved.</strong><p>{serverError}</p></div> : null}
    {errors.length ? <div className="blueprint-error-summary" role="alert"><strong>Resolve these Blueprint requirements before save.</strong><ul>{errors.map((error) => <li key={error}>{error}</li>)}</ul></div> : null}
    <fieldset disabled={busy} aria-busy={busy || undefined}>
      <section className="blueprint-editor-card blueprint-default-editor"><header><span className="micro-label">Course-wide baseline</span><h2>Defaults</h2><p>Plans that still match the baseline follow these changes. Existing exceptions stay explicit.</p></header>
        <div className="blueprint-asset-buttons" role="group" aria-label="Course default assets">{assetCatalog.map(([assetType, label]) => <button type="button" key={assetType} aria-pressed={draft.defaults.assetTypes.includes(assetType)} onClick={() => toggleDefaultAsset(assetType)}><span aria-hidden="true">{draft.defaults.assetTypes.includes(assetType) ? "✓" : "+"}</span>{label}</button>)}</div>
        {depthInputs(draft.defaults, "Course default", changeDefaultDepth)}
      </section>
      <section className="blueprint-plan-editors" aria-label="Blueprint subtopic exceptions">{draft.plans.map((plan) => {
        const assetException = !sameAssets(plan.selectedAssetTypes, draft.defaults.assetTypes);
        const depthExceptionCount = depthFields.filter((field) => plan[field] !== draft.defaults[field]).length;
        return <article className="blueprint-editor-card blueprint-plan-editor" key={plan.subtopicId}>
          <header><div><code>{plan.subtopicId}</code><h2>{subtopicNames[plan.subtopicId] ?? "Untitled subtopic"}</h2></div><span className={assetException || depthExceptionCount ? "exception-badge" : "baseline-badge"}>{assetException || depthExceptionCount ? `${Number(assetException) + depthExceptionCount} exception${Number(assetException) + depthExceptionCount === 1 ? "" : "s"}` : "Uses baseline"}</span></header>
          <div className="blueprint-asset-buttons" role="group" aria-label={`Assets for ${subtopicNames[plan.subtopicId] ?? plan.subtopicId}`}>{assetCatalog.map(([assetType, label]) => <button type="button" key={assetType} aria-pressed={plan.selectedAssetTypes.includes(assetType)} onClick={() => togglePlanAsset(plan.subtopicId, assetType)}><span aria-hidden="true">{plan.selectedAssetTypes.includes(assetType) ? "✓" : "+"}</span>{label}</button>)}</div>
          {!plan.selectedAssetTypes.includes("course_content") ? <label className="anchor-waiver"><input type="checkbox" checked={plan.anchorWaiverConfirmed} onChange={(event) => commit((next) => { next.plans.find((item) => item.subtopicId === plan.subtopicId)!.anchorWaiverConfirmed = event.target.checked; })} /><span><strong>Confirm Course Content anchor waiver</strong>I understand this subtopic will generate supporting assets without the normal Course Content anchor.</span></label> : null}
          {depthInputs(plan, subtopicNames[plan.subtopicId] ?? plan.subtopicId, (field, value) => changePlanDepth(plan.subtopicId, field, value))}
        </article>;
      })}</section>
      <section className="blueprint-editor-card blueprint-reconciliation" aria-labelledby="blueprint-reconciliation-title"><header><span className="micro-label">Reconciliation preview</span><h2 id="blueprint-reconciliation-title">What generation will change</h2></header>
        <div className="blueprint-reconciliation-grid"><div><strong>Added assets</strong>{addedAssets.length ? <ul>{addedAssets.map((id) => <li key={id}><code>{id}</code></li>)}</ul> : <p>None</p>}</div><div><strong>Removed assets</strong>{removedAssets.length ? <ul>{removedAssets.map((id) => <li key={id}><code>{id}</code></li>)}</ul> : <p>None</p>}</div><div><strong>Existing content that becomes stale</strong>{dirty && contentAssets.length ? <ul>{contentAssets.map((asset) => <li key={asset.id}><code>{asset.id}</code> {asset.title}</li>)}</ul> : <p>{contentAssets.length ? "No Blueprint change yet." : "No generated content exists yet."}</p>}</div></div>
        <label><span>Decision rationale</span><textarea aria-label="Blueprint decision rationale" value={draft.rationale} onChange={(event) => commit((next) => { next.rationale = event.target.value; })} /></label>
        <label className="impact-ack"><input type="checkbox" checked={acknowledged} disabled={!dirty || Boolean(errors.length)} onChange={(event) => setAcknowledged(event.target.checked)} /><span>I reviewed the exact asset additions/removals, subtopic exceptions, anchor waivers, and existing content that will become stale.</span></label>
        <button type="button" className="button button-primary" disabled={!dirty || Boolean(errors.length) || !acknowledged || busy || conflict} onClick={() => onSave(decisionFromDraft(draft))}>{busy ? "Saving Blueprint…" : "Save Blueprint draft"}</button>
        <button type="button" className="button button-quiet" disabled={busy} onClick={() => { if (!dirty || window.confirm("Discard all unsaved Blueprint changes?")) onCancel(); }}>Cancel editing</button>
      </section>
    </fieldset>
    <div className="sr-status" role="status" aria-live="polite">{busy ? "Blueprint request in progress." : dirty ? "Blueprint reconciliation preview is ready for review." : "Blueprint editor ready."}</div>
    {conflict ? <div className="modal-backdrop" role="presentation"><div className="feedback-dialog course-model-dialog" role="dialog" aria-modal="true" aria-labelledby="blueprint-conflict-title"><header><span className="eyebrow">Blueprint decision</span><h2 id="blueprint-conflict-title">The Blueprint changed elsewhere</h2></header><p>Your local settings remain visible. Review them against the latest Blueprint and run the reconciliation again before saving, or discard them and use the latest artifact.</p><footer><button className="button button-quiet" onClick={() => onResolveConflict("discard")}>Use latest Blueprint</button><button ref={conflictReviewRef} className="button button-primary" onClick={() => { setAcknowledged(false); onResolveConflict("reapply"); }}>Review local decision again</button></footer></div></div> : null}
  </div>;
}
