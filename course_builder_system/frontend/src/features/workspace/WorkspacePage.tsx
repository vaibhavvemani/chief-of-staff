import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  ApiError,
  addKnownSource,
  approveStage,
  confirmSourceRepairRoute,
  courseModelValidationIssues,
  decideSourceRepair,
  getBriefQuestions,
  getWorkspace,
  outcomeValidationIssues,
  previewStageImpact,
  previewCourseModelDecision,
  reopenStage,
  requestContentRepair,
  requestSourceRepair,
  reviseStage,
  reviewContentAsset,
  runStage,
  runBriefClarifications,
  saveBriefAnswers,
  saveBriefUpdates,
  saveBlueprintDecision,
  saveCourseModelDecision,
  saveLessonPlanDecision,
  saveOutcomeDecision,
  saveSourceDecision,
  subscribeToJob,
  versionConflictChecksum,
} from "../../api/client";
import { AppBrand } from "../../components/AppBrand";
import { ErrorState, LoadingState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";
import type { BlueprintDecisionDraft, BriefData, BriefQuestionAnswer, BriefUpdates, Claim, ContentAsset, CourseModelOperation, CourseModelPreview, CourseModelValidationIssue, ImpactPreview, LessonPlanDecisionDraft, OutcomeDecisionDraft, OutcomeValidationIssue, SourceRepairEntry, StageAction, StageActionId, StageSlug, UiStatus, Workspace } from "../../types";
import { StageView, stageData, type BriefEditSection } from "./StageViews";

const stageSlugs: StageSlug[] = ["brief", "outcomes", "research", "course-model", "blueprint", "content", "lesson-plan", "package"];
export function sourceRepairModeAvailability(
  runMode: "deterministic" | "live",
  backendEnabled: boolean,
  liveReady = true,
): { available: boolean; reason?: string } {
  if (!backendEnabled) return { available: false };
  if (runMode === "live" && !liveReady) {
    return { available: false, reason: "Live provider credentials are not configured on the server." };
  }
  return { available: true };
}

function stageName(stage: StageSlug): string {
  return stage === "course-model"
    ? "Course Model"
    : stage === "lesson-plan"
      ? "Lesson Plan"
      : stage === "content"
        ? "Student Content"
        : stage === "package"
          ? "Package"
          : stage.charAt(0).toUpperCase() + stage.slice(1).replaceAll("-", " ");
}

const stageNumbers: Record<StageSlug, string> = {
  brief: "01",
  outcomes: "02",
  research: "03",
  "course-model": "04",
  blueprint: "05",
  content: "06",
  "lesson-plan": "07",
  package: "08",
};

const stageContext: Record<StageSlug, { why: string; evidence: string }> = {
  brief: {
    why: "The Brief translates a sparse subject request into explicit audience, scope, constraints, and assumptions before expensive work begins.",
    evidence: "Intake answers and visible safe defaults. Assumptions remain editable until the Brief is approved.",
  },
  outcomes: {
    why: "Measurable outcomes make downstream coverage and assessment decisions testable instead of relying on a general topic description.",
    evidence: "Approved Brief: audience, purpose, scope, level, and assessment expectations.",
  },
  research: {
    why: "The agent separates curriculum evidence from factual grounding so weak or rejected pages cannot silently enter learner content.",
    evidence: "Bounded competitor outlines, candidate metadata, trust notes, and explicit human source decisions.",
  },
  "course-model": {
    why: "This compact hierarchy is the structural source of truth. Stable IDs let every downstream asset remain referentially auditable.",
    evidence: "Outcomes, competitor synthesis, approved sources, scope rules, and structural rationale.",
  },
  blueprint: {
    why: "The Blueprint makes asset generation an explicit product decision for each subtopic, with defaults and visible exceptions.",
    evidence: "Course Model coverage and source assignments, course-wide depth defaults, and explicit asset decisions.",
  },
  content: {
    why: "Content is generated per asset and checked claim by claim. The operator resolves only material evidence and quality issues.",
    evidence: "Approved source excerpts routed by subtopic, generation claims, verifier verdicts, and durable human reviews.",
  },
  "lesson-plan": {
    why: "The Lesson Plan sequences approved content into feasible sessions while reconciling time, delivery mode, and complete subtopic coverage.",
    evidence: "Course Model sequence, selected assets, delivery constraints, and coverage reconciliation.",
  },
  package: {
    why: "A rendered folder is not automatically learner-ready. The release gate reconciles integrity, evidence, review, and output paths.",
    evidence: "Integrity checks, run summary, verifier blockers, review decisions, and render manifest.",
  },
};

function WorkflowRail({ workspace, activeStage, activeJobStage, runMode, onOpenActivity }: { workspace: Workspace; activeStage: StageSlug; activeJobStage?: StageSlug | null; runMode: "deterministic" | "live"; onOpenActivity: () => void }) {
  return (
    <aside className="workflow-rail">
      <div className="rail-heading"><span>Course workflow</span><small>{workspace.stages.filter((stage) => stage.status === "approved").length} / 8 approved</small></div>
      <nav aria-label="Course stages">
        {workspace.stages.map((stage) => {
          const isActive = activeStage === stage.slug;
          const isLocked = stage.status === "locked";
          const navigationPaused = Boolean(activeJobStage && stage.slug !== activeJobStage);
          return (
            <Link
              key={stage.slug}
              to={`/courses/${workspace.course.courseId}/${stage.slug}?mode=${runMode}`}
              className={`${isActive ? "active" : ""} ${navigationPaused ? "navigation-paused" : ""} rail-status-${stage.status}`}
              aria-current={isActive ? "page" : undefined}
              aria-disabled={navigationPaused || undefined}
              onClick={(event) => { if (navigationPaused) event.preventDefault(); }}
              title={navigationPaused ? "Finish the active stage run before moving elsewhere" : isLocked ? "Inspect this locked stage and its requirements" : undefined}
            >
              <span className="rail-number">{stageNumbers[stage.slug]}</span>
              <span className="rail-stage-copy"><strong>{stage.label}</strong><small>{stage.status.replaceAll("_", " ")}</small></span>
              <span className="rail-stage-state" aria-hidden="true">{stage.status === "approved" ? "✓" : ["needs_input", "requires_attention", "failed"].includes(stage.status) ? stage.count || "!" : stage.status === "locked" ? "·" : "→"}</span>
            </Link>
          );
        })}
      </nav>
      <button className="activity-trigger" onClick={onOpenActivity}><span className="activity-bars" aria-hidden="true"><i /><i /><i /></span><span><strong>Activity & runs</strong><small>{workspace.activity.length} recent events</small></span><span aria-hidden="true">›</span></button>
      <div className="rail-footer"><span className="rail-saved-dot" /><span><strong>Artifacts saved</strong><small>Resume-safe workspace</small></span></div>
    </aside>
  );
}

type InspectorTab = "why" | "evidence" | "dependencies" | "history" | "raw";

function ContextInspector({ workspace, stage, onClose }: { workspace: Workspace; stage: StageSlug; onClose: () => void }) {
  const [tab, setTab] = useState<InspectorTab>("why");
  const context = stageContext[stage];
  const stageSummary = workspace.stages.find((item) => item.slug === stage);
  const tabs: Array<[InspectorTab, string]> = [["why", "Why"], ["evidence", "Evidence"], ["dependencies", "Links"], ["history", "History"], ["raw", "Raw"]];
  return (
    <aside className="context-inspector">
      <header><div><span className="eyebrow">Stage context</span><h2>{stageSummary?.label}</h2></div><div className="inspector-header-actions"><StatusBadge status={stageSummary?.status ?? "ready"} count={stageSummary?.count} /><button onClick={onClose} aria-label="Close stage context">×</button></div></header>
      <div className="inspector-tabs" role="tablist" aria-label="Inspector views">{tabs.map(([id, label]) => <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>{label}</button>)}</div>
      <div className="inspector-body">
        {tab === "why" ? <><span className="inspector-section-label">Why this stage exists</span><p className="inspector-lead">{context.why}</p><div className="inspector-callout"><span aria-hidden="true">◆</span><div><strong>Agent recommendation</strong><p>{stageSummary?.summary ?? "Review the structured artifact before taking the next decision."}</p></div></div><span className="inspector-section-label">Decision rule</span><p>Approval records a human checkpoint. It does not merely acknowledge that generation finished.</p></> : null}
        {tab === "evidence" ? <><span className="inspector-section-label">Evidence used here</span><p className="inspector-lead">{context.evidence}</p><div className="evidence-summary"><div><strong>{workspace.research.sources.filter((source) => source.status === "approved").length}</strong><span>Approved sources</span></div><div><strong>{workspace.content.assets.reduce((total, asset) => total + asset.verification.supported, 0)}</strong><span>Supported claims</span></div></div><div className="boundary-note"><span aria-hidden="true">✓</span><p>Only approved, assigned source excerpts enter generation context.</p></div></> : null}
        {tab === "dependencies" ? <div className="dependency-map"><span className="inspector-section-label">Required artifacts</span>{stageSummary?.dependencies.length ? stageSummary.dependencies.map((item) => <div key={item} className="dependency-item before"><span aria-hidden="true">←</span>{item.replaceAll("_", " ")}</div>) : <p className="muted">No artifact prerequisites.</p>}<div className="current-dependency">{stageSummary?.label}</div><span className="inspector-section-label">Downstream stages</span>{stageSummary?.downstreamStages.length ? stageSummary.downstreamStages.map((item) => <div key={item} className="dependency-item after"><span aria-hidden="true">→</span>{stageName(item)}</div>) : <p className="muted">No downstream stage dependency.</p>}</div> : null}
        {tab === "history" ? <div className="inspector-history"><span className="inspector-section-label">Recent events</span>{workspace.activity.map((event) => <article key={event.id}><span className={`history-dot history-${event.tone ?? "neutral"}`} /><div><strong>{event.title}</strong><p>{event.detail}</p><time>{new Date(event.at).toLocaleString()}</time></div></article>)}</div> : null}
        {tab === "raw" ? <><div className="raw-heading"><span className="inspector-section-label">Canonical data</span><button onClick={() => void navigator.clipboard?.writeText(JSON.stringify(stageData(stage, workspace), null, 2))}>Copy</button></div><pre className="inspector-raw">{JSON.stringify(stageData(stage, workspace), null, 2)}</pre></> : null}
      </div>
    </aside>
  );
}

function ActivityDrawer({ workspace, onClose }: { workspace: Workspace; onClose: () => void }) {
  const failedStage = workspace.stages.find((stage) => stage.status === "failed");
  const activeStage = workspace.activeJob?.stage;
  const dialogRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;
      const focusable = [...dialogRef.current.querySelectorAll<HTMLElement>("button:not([disabled]), a[href], [tabindex]:not([tabindex='-1'])")];
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
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      previous?.focus();
    };
  }, []);
  return (
    <div className="drawer-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose(); }}>
      <aside ref={dialogRef} className="activity-drawer" role="dialog" aria-modal="true" aria-labelledby="activity-title" aria-describedby="activity-boundary">
        <header><div><span className="eyebrow">Audit & diagnostics</span><h2 id="activity-title">Activity</h2></div><button ref={closeRef} onClick={onClose} aria-label="Close activity drawer">×</button></header>
        <div className="run-summary-card"><div><span className="run-glyph" aria-hidden="true">{failedStage ? "!" : activeStage ? "…" : "✓"}</span><span><strong>{failedStage ? `${stageName(failedStage.slug)} run failed` : activeStage ? `${stageName(activeStage)} run in progress` : "Workspace state is current"}</strong><small>{failedStage?.lastFailure ?? workspace.course.nextAction}</small></span></div><code>{workspace.course.courseId}</code></div>
        <div className="activity-list" aria-label="Persisted runtime events">{workspace.activity.length ? workspace.activity.map((event) => <article key={event.id}><time>{new Date(event.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time><span className={`activity-dot activity-${event.tone ?? "neutral"}`} /><div><strong>{event.title}</strong><p>{event.detail}</p>{event.stage ? <small>{stageName(event.stage)}</small> : null}</div></article>) : <p className="activity-empty">No persisted runtime events yet.</p>}</div>
        <section className="model-diagnostics" tabIndex={0} aria-labelledby="diagnostics-title"><header><div><span className="eyebrow">Safe model-call summary</span><h3 id="diagnostics-title">Diagnostics by stage</h3></div><strong>{workspace.diagnostics.totals.calls} call{workspace.diagnostics.totals.calls === 1 ? "" : "s"}</strong></header>{workspace.diagnostics.stages.length ? <div>{workspace.diagnostics.stages.map((diagnostic) => <article key={diagnostic.stage}><div><strong>{stageName(diagnostic.stage as StageSlug)}</strong><small>{diagnostic.providers.join(", ") || "Provider not reported"} · {diagnostic.models.join(", ") || "Model not reported"}</small></div><dl><div><dt>Calls</dt><dd>{diagnostic.calls}</dd></div><div><dt>Tokens</dt><dd>{(diagnostic.inputTokens + diagnostic.outputTokens).toLocaleString()}</dd></div><div><dt>Cost</dt><dd>${diagnostic.estimatedCostUsd.toFixed(4)}</dd></div><div><dt>Cache</dt><dd>{diagnostic.cacheHits}</dd></div><div><dt>Retries</dt><dd>{diagnostic.retries}</dd></div><div><dt>Errors</dt><dd>{diagnostic.errors.length}</dd></div></dl>{diagnostic.errors.map((error, index) => <p className="diagnostic-error" key={`${error.type}:${error.at ?? index}`}><strong>{error.type}</strong> {error.message}</p>)}</article>)}</div> : <p className="activity-empty">No live model calls have been recorded for this course.</p>}</section>
        <footer><p id="activity-boundary">Prompts, source bodies, credentials, learner content, and private reasoning are never shown in activity events.</p></footer>
      </aside>
    </div>
  );
}

function DecisionBar({
  stage,
  status,
  actions,
  busy,
  onAction,
}: {
  stage: StageSlug;
  status: UiStatus;
  actions: StageAction[];
  busy?: boolean;
  onAction: (action: StageAction) => void;
}) {
  const primaryIds: StageActionId[] = ["run", "retry", "edit", "add_source", "source_decision", "source_repair", "content_repair", "review_asset", "revise", "approve", "go_to_blocker", "continue"];
  const inlineActionIds: StageActionId[] = ["add_source", "source_decision", "source_repair", "content_repair", "review_asset", "revise"];
  const visibleActions = actions.filter((action) => !inlineActionIds.includes(action.id));
  const statusCopy: Record<UiStatus, [string, string]> = {
    locked: ["Upstream checkpoint required", "This stage is not ready yet"],
    needs_input: ["Required input missing", `Complete ${stageName(stage)} before continuing`],
    ready: ["Stage action", `${stageName(stage)} is ready to run`],
    running: ["Agent working", `Building ${stageName(stage)}`],
    awaiting_review: ["Human checkpoint", `Review ${stageName(stage)} before continuing`],
    approved: ["Checkpoint recorded", `${stageName(stage)} is approved and current`],
    requires_attention: ["Human decision needed", "Resolve the listed blockers before approval"],
    stale: ["Upstream change detected", `Rerun ${stageName(stage)} after its prerequisites are current`],
    failed: ["Last run failed safely", `Retry ${stageName(stage)} when ready`],
  };
  const [kicker, detail] = statusCopy[status];
  return (
    <div className="decision-bar">
      <div className="decision-context"><span className={`decision-dot decision-${status}`} /><div><small>{kicker}</small><strong>{detail}</strong></div></div>
      <div className="decision-actions">
        {visibleActions.map((action) => {
          const primary = primaryIds.includes(action.id) && action.id !== "revise";
          return <button key={action.id} className={`button ${primary ? "button-primary" : "button-secondary"}`} disabled={busy || !action.enabled} title={action.reason} onClick={() => onAction(action)}>{busy && ["run", "retry", "approve"].includes(action.id) ? "Working…" : action.label}{action.enabled && primary ? <span aria-hidden="true">→</span> : null}</button>;
        })}
        {visibleActions.find((action) => !action.enabled && action.reason)?.reason ? <span className="decision-action-reason">{visibleActions.find((action) => !action.enabled && action.reason)?.reason}</span> : null}
        {!visibleActions.length ? <span className="decision-no-actions">{status === "running" ? "Agent working…" : actions.length ? "Use the controls in this stage to continue." : "No stage changes are available."}</span> : null}
      </div>
    </div>
  );
}

const runMessages: Record<StageSlug, string[]> = {
  brief: ["Reading the subject request", "Structuring the course constraints", "Making assumptions visible"],
  outcomes: ["Reading the approved Brief", "Drafting measurable learner outcomes", "Checking assessment evidence and coverage"],
  research: ["Planning the evidence search", "Evaluating candidate sources", "Separating curriculum signals from grounding evidence"],
  "course-model": ["Organizing modules and subtopics", "Assigning stable structural IDs", "Routing approved sources to the model"],
  blueprint: ["Selecting the right learner assets", "Balancing depth and duration", "Checking coverage against the Course Model"],
  content: ["Preparing bounded generation context", "Writing one learner asset at a time", "Verifying claims against approved evidence"],
  "lesson-plan": ["Sequencing the approved content", "Reconciling timing and delivery mode", "Checking complete subtopic coverage"],
  package: ["Rendering the course folder", "Reconciling artifact references", "Running the final release checks"],
};

function AgentRunScreen({ stage, mode, progress }: { stage: StageSlug; mode: "deterministic" | "live"; progress: { message: string; completed?: number; expected?: number } | null }) {
  const [messageIndex, setMessageIndex] = useState(0);
  const messages = runMessages[stage];
  useEffect(() => {
    setMessageIndex(0);
    const interval = window.setInterval(() => setMessageIndex((current) => (current + 1) % messages.length), 2800);
    return () => window.clearInterval(interval);
  }, [messages]);
  const percent = progress?.completed != null && progress.expected
    ? Math.min(100, Math.round((progress.completed / progress.expected) * 100))
    : undefined;
  return (
    <section className="agent-run-screen" aria-live="polite" aria-busy="true">
      <div className="agent-run-orbit" aria-hidden="true"><span /><i /><b /></div>
      <span className="eyebrow">{mode === "live" ? "Live agent run" : "Deterministic run"}</span>
      <h1>The agent is building {stageName(stage)}</h1>
      <p className="agent-run-lead">You can stay here—the artifact will appear as soon as it is ready for your review.</p>
      <div className="agent-run-status">
        <span className="agent-run-pulse" aria-hidden="true" />
        <div key={messageIndex}><strong>{messages[messageIndex]}</strong><small>{progress?.message ?? "Work is in progress"}</small></div>
        {progress?.completed != null && progress.expected ? <b>{progress.completed}/{progress.expected}</b> : null}
      </div>
      <div className={`agent-run-track ${percent == null ? "indeterminate" : ""}`} role="progressbar" aria-label={`${stageName(stage)} run progress`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}><span style={percent == null ? undefined : { width: `${percent}%` }} /></div>
      <p className="agent-run-note">Live runs may take a few minutes. Approval will only be available after the output is fully saved.</p>
    </section>
  );
}

type RevisionTarget = {
  stage: StageSlug;
  targetType: string;
  id: string;
  label: string;
  categories: string[];
  expectedChecksum: string;
  claim?: Claim;
};

function ScopedRevisionDialog({ target, busy, onCancel, onSubmit }: { target: RevisionTarget; busy: boolean; onCancel: () => void; onSubmit: (category: string, instruction: string) => void }) {
  const [category, setCategory] = useState(target.categories.includes("evidence") && target.claim ? "evidence" : target.categories[0] ?? "clarity");
  const [instruction, setInstruction] = useState(target.claim ? `Correct verifier finding ${target.claim.id}: ${target.claim.note || target.claim.text}` : "");
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") onCancel(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onCancel]);
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onCancel(); }}>
      <div className="feedback-dialog" role="dialog" aria-modal="true" aria-labelledby="revision-title">
        <header><span className="eyebrow">{target.stage === "content" ? "Scoped content revision" : `Scoped ${stageName(target.stage)} revision`}</span><h2 id="revision-title">Revise {target.label}</h2><p>Only the named <code>{target.targetType}</code> record may change. Backend validation preserves every unrelated record.</p></header>
        <label><span>Revision category</span><select value={category} onChange={(event) => setCategory(event.target.value)}>{target.categories.map((item) => <option key={item} value={item}>{item.charAt(0).toUpperCase() + item.slice(1)}</option>)}</select></label>
        <label><span>Revision instruction</span><textarea autoFocus rows={5} value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="Describe the exact bounded change required for this record." /></label>
        <div className="impact-preview"><span className="micro-label">Execution boundary</span><div><span aria-hidden="true">→</span>Target type: {target.targetType}</div><div><span aria-hidden="true">→</span>Target ID: {target.id}</div><div><span aria-hidden="true">→</span>Unrelated records must remain unchanged</div></div>
        <footer><button className="button button-quiet" onClick={onCancel}>Cancel</button><button className="button button-primary" disabled={!instruction.trim() || busy} onClick={() => onSubmit(category, instruction.trim())}>{busy ? "Starting revision…" : "Start scoped revision"}</button></footer>
      </div>
    </div>
  );
}

function ImpactConfirmationDialog({ stage, preview, busy, onCancel, onConfirm }: { stage: StageSlug; preview: ImpactPreview; busy: boolean; onCancel: () => void; onConfirm: (reason?: string) => void }) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [reason, setReason] = useState("");
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") onCancel(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onCancel]);
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onCancel(); }}>
      <div className="feedback-dialog impact-dialog" role="dialog" aria-modal="true" aria-labelledby="impact-title">
        <header><span className="eyebrow">Confirmed lifecycle change</span><h2 id="impact-title">Reopen {stageName(stage)}?</h2><p>The server computed this impact from the current pipeline dependency graph. It will validate the preview again under the course mutation lock.</p></header>
        <div className="impact-summary-grid"><div><strong>{preview.directArtifacts.length}</strong><span>reopened artifacts</span></div><div><strong>{preview.staleArtifacts.length}</strong><span>downstream artifacts made stale</span></div><div><strong>{preview.requiresRerunStages.length}</strong><span>stages requiring rerun</span></div></div>
        <dl className="impact-boundaries"><div><dt>Reopened artifacts</dt><dd>{preview.directArtifacts.map((item) => item.replaceAll("_", " ")).join(", ") || "None"}</dd></div><div><dt>Marked stale</dt><dd>{preview.staleArtifacts.map((item) => item.replaceAll("_", " ")).join(", ") || "None"}</dd></div><div><dt>Targeted assets</dt><dd>{preview.targetedAssets.length ? `${preview.targetedAssets.length} asset${preview.targetedAssets.length === 1 ? "" : "s"}` : "None"}</dd></div><div><dt>Preserved assets</dt><dd>{preview.preservedAssets.length ? `${preview.preservedAssets.length} asset${preview.preservedAssets.length === 1 ? "" : "s"}` : "None"}</dd></div></dl>
        <div className="impact-preview"><span className="micro-label">Downstream stages</span>{preview.requiresRerunStages.length ? preview.requiresRerunStages.map((item) => <div key={item}><span aria-hidden="true">→</span>{stageName(item)}</div>) : <div>No downstream reruns are expected.</div>}</div>
        {preview.warnings.length ? <div className="impact-warnings">{preview.warnings.map((warning) => <p key={warning}><span aria-hidden="true">!</span>{warning}</p>)}</div> : null}
        <label><span>Reason <small>Optional audit note</small></span><textarea rows={3} value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Why does this approved checkpoint need to change?" /></label>
        <label className="impact-ack"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /><span>I understand these downstream artifacts will remain visible but cannot satisfy approved prerequisites until rerun.</span></label>
        <footer><button className="button button-quiet" onClick={onCancel}>Cancel</button><button className="button button-primary" disabled={!acknowledged || busy} onClick={() => onConfirm(reason.trim() || undefined)}>{busy ? "Revalidating impact…" : "Confirm and reopen"}</button></footer>
      </div>
    </div>
  );
}

function RevisionImpactConfirmationDialog({ stage, preview, busy, onCancel, onConfirm }: { stage: StageSlug; preview: ImpactPreview; busy: boolean; onCancel: () => void; onConfirm: () => void }) {
  const [acknowledged, setAcknowledged] = useState(false);
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") onCancel(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onCancel]);
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onCancel(); }}>
      <div className="feedback-dialog impact-dialog" role="dialog" aria-modal="true" aria-labelledby="revision-impact-title">
        <header><span className="eyebrow">Scoped revision impact</span><h2 id="revision-impact-title">Confirm this {stageName(stage)} revision?</h2><p>The server proved the named-record boundary and will revalidate this preview while holding the course mutation lock.</p></header>
        <div className="impact-summary-grid"><div><strong>{preview.directArtifacts.length}</strong><span>stage artifact revised</span></div><div><strong>{preview.staleArtifacts.length}</strong><span>downstream artifacts made stale</span></div><div><strong>{preview.requiresRerunStages.length}</strong><span>stages requiring rerun</span></div></div>
        <dl className="impact-boundaries"><div><dt>Direct artifact</dt><dd>{preview.directArtifacts.map((item) => item.replaceAll("_", " ")).join(", ")}</dd></div><div><dt>Marked stale</dt><dd>{preview.staleArtifacts.map((item) => item.replaceAll("_", " ")).join(", ") || "None"}</dd></div><div><dt>Content assets affected</dt><dd>{preview.targetedAssets.length || "None"}</dd></div><div><dt>Rerun stages</dt><dd>{preview.requiresRerunStages.map(stageName).join(", ") || "None"}</dd></div></dl>
        {preview.warnings.length ? <div className="impact-warnings">{preview.warnings.map((warning) => <p key={warning}><span aria-hidden="true">!</span>{warning}</p>)}</div> : null}
        <label className="impact-ack"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} /><span>I understand the named record will be validated in scope and the listed downstream artifacts will become stale.</span></label>
        <footer><button className="button button-quiet" onClick={onCancel}>Back</button><button className="button button-primary" disabled={!acknowledged || busy} onClick={onConfirm}>{busy ? "Revalidating impact…" : "Confirm and start revision"}</button></footer>
      </div>
    </div>
  );
}

const briefSectionLabels: Record<BriefEditSection, string> = {
  settings: "Course settings",
  learner: "Learner and intent",
  scope: "Scope boundary",
  coverage: "Coverage and constraints",
  requirements: "Additional requirements and materials",
  assumptions: "Starting assumptions",
};

function listFromText(value: string): string[] {
  return value.split("\n").map((item) => item.trim()).filter(Boolean);
}

export function briefSectionUpdates(section: BriefEditSection, draft: BriefData, original: BriefData): BriefUpdates {
  const candidates: BriefUpdates = section === "settings"
    ? { courseTitle: draft.courseTitle, level: draft.level, duration: draft.duration, modality: draft.modality, language: draft.language }
    : section === "learner"
      ? { audience: draft.audience, priorKnowledge: draft.priorKnowledge, purpose: draft.purpose, assessmentExpectations: draft.assessmentExpectations }
      : section === "scope"
        ? { inScope: draft.inScope, outOfScope: draft.outOfScope }
        : section === "coverage"
          ? { mustHaveTopics: draft.mustHaveTopics, constraints: draft.constraints }
          : section === "requirements"
            ? {
                availableMaterials: draft.availableMaterials,
                jurisdiction: draft.jurisdiction,
                accessibilityRequirements: draft.accessibilityRequirements,
                liveTeachingConstraints: draft.liveTeachingConstraints,
                toolsOrEquipment: draft.toolsOrEquipment,
                freshnessRequirement: draft.freshnessRequirement,
              }
            : { courseTitle: draft.courseTitle, audience: draft.audience, level: draft.level, duration: draft.duration, modality: draft.modality, language: draft.language };
  return Object.fromEntries(
    Object.entries(candidates).filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(original[key as keyof BriefData])),
  ) as BriefUpdates;
}

function BriefEditDialog({ section, brief, busy, onCancel, onSubmit }: { section: BriefEditSection; brief: BriefData; busy: boolean; onCancel: () => void; onSubmit: (updates: BriefUpdates) => void }) {
  const [draft, setDraft] = useState<BriefData>(() => ({
    ...brief,
    inScope: [...brief.inScope],
    outOfScope: [...brief.outOfScope],
    mustHaveTopics: [...brief.mustHaveTopics],
    constraints: [...brief.constraints],
    availableMaterials: [...brief.availableMaterials],
    assumptions: [...brief.assumptions],
  }));
  const update = <K extends keyof BriefData>(key: K, value: BriefData[K]) => setDraft((current) => ({ ...current, [key]: value }));
  const updates = briefSectionUpdates(section, draft, brief);
  const canSave = Boolean(draft.courseTitle.trim() && draft.audience.trim() && draft.level && draft.duration.trim() && draft.modality && draft.language.trim());

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") onCancel(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onCancel]);

  const settingsFields = <>
    <label><span>Course title</span><input autoFocus value={draft.courseTitle} onChange={(event) => update("courseTitle", event.target.value)} /></label>
    <div className="brief-editor-grid">
      <label><span>Level</span><select value={draft.level} onChange={(event) => update("level", event.target.value)}><option value="introductory">Introductory</option><option value="beginner">Beginner</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option><option value="mixed">Mixed</option><option value="custom">Custom</option></select></label>
      <label><span>Course length</span><input value={draft.duration} onChange={(event) => update("duration", event.target.value)} /></label>
      <label><span>Delivery</span><select value={draft.modality} onChange={(event) => update("modality", event.target.value)}><option value="self_paced">Self-paced</option><option value="live">Live</option><option value="blended">Blended</option><option value="workshop">Workshop</option><option value="custom">Custom</option></select></label>
      <label><span>Language</span><input value={draft.language} onChange={(event) => update("language", event.target.value)} /></label>
    </div>
  </>;

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onCancel(); }}>
      <div className="feedback-dialog brief-edit-dialog" role="dialog" aria-modal="true" aria-labelledby="brief-edit-title">
        <header><span className="eyebrow">Edit one section</span><h2 id="brief-edit-title">{briefSectionLabels[section]}</h2><p>Change the fields directly. The saved Brief becomes a new draft for review, so there is no need to write an instruction for the agent.</p></header>
        <div className="brief-editor-fields">
          {section === "settings" ? settingsFields : null}
          {section === "learner" ? <>
            <label><span>Audience</span><textarea autoFocus rows={3} value={draft.audience} onChange={(event) => update("audience", event.target.value)} /></label>
            <label><span>Prior knowledge</span><textarea rows={2} value={draft.priorKnowledge} onChange={(event) => update("priorKnowledge", event.target.value)} /></label>
            <label><span>Practical purpose</span><textarea rows={3} value={draft.purpose} onChange={(event) => update("purpose", event.target.value)} /></label>
            <label><span>Assessment expectation</span><textarea rows={2} value={draft.assessmentExpectations ?? ""} onChange={(event) => update("assessmentExpectations", event.target.value)} /></label>
          </> : null}
          {section === "scope" ? <div className="brief-editor-grid">
            <label><span>In scope <small>One item per line</small></span><textarea autoFocus rows={6} value={draft.inScope.join("\n")} onChange={(event) => update("inScope", listFromText(event.target.value))} /></label>
            <label><span>Out of scope <small>One item per line</small></span><textarea rows={6} value={draft.outOfScope.join("\n")} onChange={(event) => update("outOfScope", listFromText(event.target.value))} /></label>
          </div> : null}
          {section === "coverage" ? <div className="brief-editor-grid">
            <label><span>Must-have topics <small>One item per line</small></span><textarea autoFocus rows={6} value={draft.mustHaveTopics.join("\n")} onChange={(event) => update("mustHaveTopics", listFromText(event.target.value))} /></label>
            <label><span>Constraints <small>One item per line</small></span><textarea rows={6} value={draft.constraints.join("\n")} onChange={(event) => update("constraints", listFromText(event.target.value))} /></label>
          </div> : null}
          {section === "requirements" ? <>
            <div className="brief-editor-grid">
              <label><span>Jurisdiction or geography</span><textarea autoFocus rows={2} value={draft.jurisdiction ?? ""} onChange={(event) => update("jurisdiction", event.target.value)} /></label>
              <label><span>Accessibility requirements</span><textarea rows={2} value={draft.accessibilityRequirements ?? ""} onChange={(event) => update("accessibilityRequirements", event.target.value)} /></label>
              <label><span>Live-teaching constraints</span><textarea rows={2} value={draft.liveTeachingConstraints ?? ""} onChange={(event) => update("liveTeachingConstraints", event.target.value)} /></label>
              <label><span>Tools or equipment</span><textarea rows={2} value={draft.toolsOrEquipment ?? ""} onChange={(event) => update("toolsOrEquipment", event.target.value)} /></label>
              <label><span>Freshness requirement</span><textarea rows={2} value={draft.freshnessRequirement ?? ""} onChange={(event) => update("freshnessRequirement", event.target.value)} /></label>
              <label><span>Available materials <small>One item per line</small></span><textarea rows={4} value={draft.availableMaterials.join("\n")} onChange={(event) => update("availableMaterials", listFromText(event.target.value))} /></label>
            </div>
          </> : null}
          {section === "assumptions" ? <>
            <div className="assumption-editor-note"><span aria-hidden="true">i</span><p>These are the most common defaults to correct. Saving them makes your choices explicit in the Brief.</p></div>
            <label><span>Audience</span><textarea autoFocus rows={2} value={draft.audience} onChange={(event) => update("audience", event.target.value)} /></label>
            {settingsFields}
          </> : null}
        </div>
        <footer><button className="button button-quiet" onClick={onCancel}>Cancel</button><button className="button button-primary" disabled={!canSave || !Object.keys(updates).length || busy} onClick={() => onSubmit(updates)}>{busy ? "Saving…" : "Save section"}</button></footer>
      </div>
    </div>
  );
}

function Toast({ message, tone, onClose }: { message: string; tone: "good" | "attention" | "neutral"; onClose: () => void }) {
  useEffect(() => {
    const timeout = window.setTimeout(onClose, 5000);
    return () => window.clearTimeout(timeout);
  }, [onClose]);
  return <div className={`toast toast-${tone}`} role="status"><span aria-hidden="true">{tone === "good" ? "✓" : tone === "attention" ? "!" : "i"}</span><p>{message}</p><button onClick={onClose} aria-label="Dismiss message">×</button></div>;
}

export function WorkspacePage() {
  const { courseId = "coffee-live-main", stage: routeStage } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const stage = stageSlugs.includes(routeStage as StageSlug) ? (routeStage as StageSlug) : "brief";
  const [runMode, setRunMode] = useState<"deterministic" | "live">(() => new URLSearchParams(location.search).get("mode") === "deterministic" ? "deterministic" : "live");
  const [activityOpen, setActivityOpen] = useState(false);
  const [impactPreview, setImpactPreview] = useState<ImpactPreview | null>(null);
  const [revisionTarget, setRevisionTarget] = useState<RevisionTarget | null>(null);
  const [pendingRevision, setPendingRevision] = useState<(RevisionTarget & { category: string; instruction: string }) | null>(null);
  const [revisionImpact, setRevisionImpact] = useState<ImpactPreview | null>(null);
  const [briefEditSection, setBriefEditSection] = useState<BriefEditSection | null>(null);
  const [outcomesEditing, setOutcomesEditing] = useState(false);
  const [outcomesDirty, setOutcomesDirty] = useState(false);
  const [outcomesConflict, setOutcomesConflict] = useState(false);
  const [outcomesServerError, setOutcomesServerError] = useState<string>();
  const [outcomesServerIssues, setOutcomesServerIssues] = useState<OutcomeValidationIssue[]>([]);
  const [courseModelEditing, setCourseModelEditing] = useState(false);
  const [courseModelDirty, setCourseModelDirty] = useState(false);
  const [courseModelConflict, setCourseModelConflict] = useState(false);
  const [courseModelServerError, setCourseModelServerError] = useState<string>();
  const [courseModelServerIssues, setCourseModelServerIssues] = useState<CourseModelValidationIssue[]>([]);
  const [courseModelPreview, setCourseModelPreview] = useState<CourseModelPreview | null>(null);
  const [blueprintEditing, setBlueprintEditing] = useState(false);
  const [blueprintDirty, setBlueprintDirty] = useState(false);
  const [blueprintConflict, setBlueprintConflict] = useState(false);
  const [blueprintServerError, setBlueprintServerError] = useState<string>();
  const [lessonPlanEditing, setLessonPlanEditing] = useState(false);
  const [lessonPlanDirty, setLessonPlanDirty] = useState(false);
  const [lessonPlanConflict, setLessonPlanConflict] = useState(false);
  const [lessonPlanServerError, setLessonPlanServerError] = useState<string>();
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [toast, setToast] = useState<{ message: string; tone: "good" | "attention" | "neutral" } | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeJobStage, setActiveJobStage] = useState<StageSlug | null>(null);
  const completedJobIds = useRef(new Set<string>());
  const [runProgress, setRunProgress] = useState<{ message: string; completed?: number; expected?: number } | null>(null);
  const query = useQuery({
    queryKey: ["workspace", courseId],
    queryFn: () => getWorkspace(courseId),
    refetchInterval: activeJobId ? 1500 : false,
  });
  const workspace = query.data?.workspace;
  const currentSummary = workspace?.stages.find((item) => item.slug === stage);
  const liveReady = workspace?.providerReadiness.ready ?? false;
  const outcomesEditCapability = stage === "outcomes"
    && Boolean(currentSummary?.actions.some((action) => action.id === "edit" && action.enabled));
  const courseModelEditCapability = stage === "course-model"
    && Boolean(currentSummary?.actions.some((action) => action.id === "edit" && action.enabled));
  const blueprintEditCapability = stage === "blueprint"
    && Boolean(currentSummary?.actions.some((action) => action.id === "edit" && action.enabled));
  const lessonPlanEditCapability = stage === "lesson-plan"
    && Boolean(currentSummary?.actions.some((action) => action.id === "edit" && action.enabled));
  const briefQuestionsQuery = useQuery({
    queryKey: ["brief-questions", courseId, runMode],
    queryFn: () => {
      if (runMode === "deterministic") return getBriefQuestions(courseId);
      if (!workspace?.briefChecksum) {
        throw new Error("Live Brief clarification requires the current checksum.");
      }
      return runBriefClarifications(courseId, runMode, workspace.briefChecksum);
    },
    enabled: stage === "brief"
      && Boolean(workspace)
      && !query.data?.demoMode
      && !query.data?.readOnly
      && (runMode !== "live" || liveReady)
      && currentSummary?.status === "needs_input",
  });

  useEffect(() => {
    if (!workspace?.activeJob || activeJobId === workspace.activeJob.jobId || completedJobIds.current.has(workspace.activeJob.jobId)) return;
    setActiveJobId(workspace.activeJob.jobId);
    setActiveJobStage(workspace.activeJob.stage);
    setRunProgress({ message: workspace.activeJob.status === "queued" ? "Run queued" : "Agent run in progress" });
  }, [activeJobId, workspace?.activeJob]);

  useEffect(() => {
    if (!outcomesEditing || stage === "outcomes" && outcomesEditCapability) return;
    setOutcomesEditing(false);
    setOutcomesDirty(false);
    setOutcomesConflict(false);
    setOutcomesServerError(undefined);
    setOutcomesServerIssues([]);
  }, [outcomesEditCapability, outcomesEditing, stage]);

  useEffect(() => {
    if (!courseModelEditing || stage === "course-model") return;
    setCourseModelEditing(false);
    setCourseModelDirty(false);
    setCourseModelConflict(false);
    setCourseModelServerError(undefined);
    setCourseModelServerIssues([]);
    setCourseModelPreview(null);
  }, [courseModelEditing, stage]);

  useEffect(() => {
    if (!blueprintEditing || stage === "blueprint") return;
    setBlueprintEditing(false);
    setBlueprintDirty(false);
    setBlueprintConflict(false);
    setBlueprintServerError(undefined);
  }, [blueprintEditing, stage]);

  useEffect(() => {
    if (!lessonPlanEditing || stage === "lesson-plan") return;
    setLessonPlanEditing(false);
    setLessonPlanDirty(false);
    setLessonPlanConflict(false);
    setLessonPlanServerError(undefined);
  }, [lessonPlanEditing, stage]);

  useEffect(() => {
    if (!outcomesDirty && !courseModelDirty && !blueprintDirty && !lessonPlanDirty) return;
    const message = courseModelDirty
      ? "You have unsaved Course Model changes. Leave this page and discard them?"
      : blueprintDirty
        ? "You have unsaved Blueprint changes. Leave this page and discard them?"
        : lessonPlanDirty
          ? "You have unsaved Lesson Plan changes. Leave this page and discard them?"
          : "You have unsaved Outcomes changes. Leave this page and discard them?";
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = message;
    };
    const onDocumentClick = (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target.closest("a[href]") : null;
      if (!(target instanceof HTMLAnchorElement)) return;
      const destination = new URL(target.href, window.location.href);
      if (destination.origin !== window.location.origin) return;
      if (!window.confirm(message)) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    document.addEventListener("click", onDocumentClick, true);
    return () => {
      window.removeEventListener("beforeunload", onBeforeUnload);
      document.removeEventListener("click", onDocumentClick, true);
    };
  }, [blueprintDirty, courseModelDirty, lessonPlanDirty, outcomesDirty]);

  const briefMutation = useMutation({
    mutationFn: async (updates: BriefUpdates) => {
      if (!workspace || query.data?.demoMode) return { demo: true };
      if (!workspace.briefChecksum) throw new Error("Brief editing requires the current checksum.");
      return saveBriefUpdates(courseId, updates, workspace.briefChecksum);
    },
    onSuccess: (result) => {
      setBriefEditSection(null);
      setToast({ tone: "good", message: result && "demo" in result ? "Preview changes recorded for this section." : "Brief section saved. Review the updated draft before approval." });
      void queryClient.invalidateQueries({ queryKey: ["workspace", courseId] });
      void queryClient.invalidateQueries({ queryKey: ["brief-questions", courseId] });
    },
    onError: (error) => {
      const stale = Boolean(versionConflictChecksum(error));
      setToast({ tone: "attention", message: stale ? "The Brief changed in another session. The latest values are loaded; reopen the section and try again." : error.message });
      if (stale) {
        setBriefEditSection(null);
        void queryClient.invalidateQueries({ queryKey: ["workspace", courseId] });
        void queryClient.invalidateQueries({ queryKey: ["brief-questions", courseId] });
      }
    },
  });

  const briefAnswersMutation = useMutation({
    mutationFn: (answers: BriefQuestionAnswer[]) => {
      const round = briefQuestionsQuery.data;
      if (!round?.checksum) throw new Error("Brief answers require the current checksum.");
      return saveBriefAnswers(courseId, answers, round.checksum, runMode);
    },
    onSuccess: async () => {
      setToast({ tone: "good", message: "Brief answers saved. The next relevant round is ready." });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["workspace", courseId] }),
        queryClient.invalidateQueries({ queryKey: ["brief-questions", courseId] }),
      ]);
    },
    onError: (error) => {
      const stale = Boolean(versionConflictChecksum(error));
      setToast({ tone: "attention", message: stale ? "The Brief changed in another session. Refresh before answering this round." : error instanceof Error ? error.message : "The answers could not be saved." });
      if (stale) {
        void queryClient.invalidateQueries({ queryKey: ["workspace", courseId] });
        void queryClient.invalidateQueries({ queryKey: ["brief-questions", courseId] });
      }
    },
  });

  useEffect(() => {
    if (!routeStage && workspace) navigate(`/courses/${courseId}/${workspace.course.currentStage}?mode=${runMode}`, { replace: true });
  }, [courseId, navigate, routeStage, runMode, workspace]);

  useEffect(() => {
    if (!activeJobId) return;
    return subscribeToJob(activeJobId, (event) => {
      setRunProgress({
        message: event.message || event.event_type.replaceAll(".", " "),
        completed: event.progress?.completed,
        expected: event.progress?.expected,
      });
      if (event.event_type === "stage.output_ready") {
        void queryClient.invalidateQueries({ queryKey: ["workspace", courseId] });
      }
      if (event.event_type === "job.completed" || event.event_type === "job.failed") {
        completedJobIds.current.add(event.job_id);
        setActiveJobId(null);
        setActiveJobStage(null);
        setRunProgress(null);
        setToast({
          tone: event.event_type === "job.completed" ? "good" : "attention",
          message: event.event_type === "job.completed"
            ? "The stage output is ready for review."
            : event.message || "The stage run failed. Open Activity for the recorded error.",
        });
        void queryClient.invalidateQueries({ queryKey: ["workspace", courseId] });
      }
    });
  }, [activeJobId, courseId, queryClient]);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["workspace", courseId] });
  const mutation = useMutation({
    mutationFn: async (action: { type: "run" | "approve" }) => {
      if (!workspace) return;
      if (action.type === "run" && runMode === "live" && !workspace.providerReadiness.ready) {
        throw new Error(workspace.providerReadiness.message);
      }
      if (action.type === "run") return runStage(courseId, stage, { expectedChecksum: currentSummary?.checksum, mode: runMode });
      return approveStage(courseId, stage, { expectedChecksum: currentSummary?.checksum });
    },
    onSuccess: async (result, action) => {
      if (result && "job" in result) {
        setActiveJobId(result.job.job_id);
        setActiveJobStage(stage);
        setRunProgress({ message: "Run queued" });
      }
      if (action.type === "approve") {
        await refresh();
        setToast({ tone: "good", message: `${stageName(stage)} approved. The backend has projected the next available action.` });
        return;
      }
      setToast({
        tone: "good",
        message: `${stageName(stage)} started. The artifact will appear here when it is ready.`,
      });
      void refresh();
    },
    onError: (error) => {
      const stale = Boolean(versionConflictChecksum(error));
      setToast({ tone: "attention", message: stale ? "This artifact changed in another session. Refresh before submitting your decision." : error.message });
    },
  });

  const outcomesMutation = useMutation({
    mutationFn: (decision: OutcomeDecisionDraft) => {
      if (!workspace?.outcomesChecksum) throw new Error("Outcomes editing requires the current artifact checksum.");
      return saveOutcomeDecision(courseId, {
        ...decision,
        expectedChecksum: workspace.outcomesChecksum,
      });
    },
    onSuccess: async (result) => {
      setOutcomesConflict(false);
      setOutcomesServerError(undefined);
      setOutcomesServerIssues([]);
      setOutcomesDirty(false);
      queryClient.setQueryData<{ workspace: Workspace; demoMode: boolean; readOnly: boolean }>(
        ["workspace", courseId],
        (current) => current ? {
          ...current,
          workspace: {
            ...current.workspace,
            outcomes: result.outcomes,
            outcomesChecksum: result.checksum || current.workspace.outcomesChecksum,
            outcomeAdvisories: result.advisories,
          },
        } : current,
      );
      setOutcomesEditing(false);
      await refresh();
      setToast({ tone: "good", message: "Outcomes saved as a draft. Review the canonical result before approval." });
    },
    onError: async (error) => {
      if (versionConflictChecksum(error)) {
        setOutcomesServerError(undefined);
        setOutcomesServerIssues([]);
        await refresh();
        setOutcomesConflict(true);
        setToast({ tone: "attention", message: "The Outcomes changed elsewhere. Your local edits are preserved until you choose how to continue." });
        return;
      }
      const message = error instanceof Error ? error.message : "The Outcomes decision could not be saved.";
      setOutcomesServerError(message);
      setOutcomesServerIssues(outcomeValidationIssues(error));
      setToast({ tone: "attention", message });
    },
  });

  const courseModelPreviewMutation = useMutation({
    mutationFn: (operations: CourseModelOperation[]) => {
      if (!workspace?.courseModelChecksum) throw new Error("Course Model editing requires the current artifact checksum.");
      return previewCourseModelDecision(courseId, operations, workspace.courseModelChecksum);
    },
    onSuccess: (result) => {
      setCourseModelConflict(false);
      setCourseModelServerError(undefined);
      setCourseModelServerIssues([]);
      setCourseModelPreview(result);
      setToast({ tone: "good", message: "The typed Course Model batch passed backend validation. Review and acknowledge its impact before save." });
    },
    onError: async (error) => {
      setCourseModelPreview(null);
      if (error instanceof ApiError && error.status === 409) {
        await refresh();
        setCourseModelConflict(true);
        setCourseModelServerError(undefined);
        setCourseModelServerIssues([]);
        setToast({ tone: "attention", message: "The Course Model changed elsewhere. Your operation batch is preserved, but it needs review and a new preview." });
        return;
      }
      const message = error instanceof Error ? error.message : "The Course Model batch could not be previewed.";
      setCourseModelServerError(message);
      setCourseModelServerIssues(courseModelValidationIssues(error));
      setToast({ tone: "attention", message });
    },
  });

  const courseModelSaveMutation = useMutation({
    mutationFn: ({ operations, impactChecksum }: { operations: CourseModelOperation[]; impactChecksum: string }) => {
      if (!workspace?.courseModelChecksum) throw new Error("Course Model editing requires the current artifact checksum.");
      return saveCourseModelDecision(courseId, operations, workspace.courseModelChecksum, impactChecksum);
    },
    onSuccess: async (result) => {
      setCourseModelDirty(false);
      setCourseModelEditing(false);
      setCourseModelConflict(false);
      setCourseModelServerError(undefined);
      setCourseModelServerIssues([]);
      setCourseModelPreview(null);
      queryClient.setQueryData<{ workspace: Workspace; demoMode: boolean; readOnly: boolean }>(
        ["workspace", courseId],
        (current) => current ? { ...current, workspace: { ...current.workspace, courseModel: result.courseModel, modules: result.courseModel.modules, courseModelChecksum: result.checksum || current.workspace.courseModelChecksum } } : current,
      );
      await refresh();
      setToast({ tone: "good", message: "Course Model saved as a canonical draft. Review it before the separate approval checkpoint." });
    },
    onError: async (error) => {
      setCourseModelPreview(null);
      if (error instanceof ApiError && error.status === 409) {
        await refresh();
        setCourseModelConflict(true);
        setCourseModelServerError(undefined);
        setCourseModelServerIssues([]);
        setToast({ tone: "attention", message: "The Course Model or impact checksum became stale. No changes were saved; review the latest model and preview again." });
        return;
      }
      const message = error instanceof Error ? error.message : "The Course Model draft could not be saved.";
      setCourseModelServerError(message);
      setCourseModelServerIssues(courseModelValidationIssues(error));
      setToast({ tone: "attention", message });
    },
  });

  const blueprintMutation = useMutation({
    mutationFn: (decision: BlueprintDecisionDraft) => {
      if (!workspace?.blueprintChecksum) throw new Error("Blueprint editing requires the current artifact checksum.");
      return saveBlueprintDecision(courseId, decision, workspace.blueprintChecksum);
    },
    onSuccess: async (result) => {
      setBlueprintDirty(false);
      setBlueprintEditing(false);
      setBlueprintConflict(false);
      setBlueprintServerError(undefined);
      queryClient.setQueryData<{ workspace: Workspace; demoMode: boolean; readOnly: boolean }>(
        ["workspace", courseId],
        (current) => current ? { ...current, workspace: { ...current.workspace, blueprint: result.blueprint, blueprintChecksum: result.checksum || current.workspace.blueprintChecksum } } : current,
      );
      await refresh();
      setToast({ tone: "good", message: "Blueprint saved as a canonical draft. Review the exact selections before approval." });
    },
    onError: async (error) => {
      if (versionConflictChecksum(error)) {
        await refresh();
        setBlueprintConflict(true);
        setBlueprintServerError(undefined);
        setToast({ tone: "attention", message: "The Blueprint changed elsewhere. Your local settings remain visible for review against the latest artifact." });
        return;
      }
      const message = error instanceof Error ? error.message : "The Blueprint decision could not be saved.";
      setBlueprintServerError(message);
      setToast({ tone: "attention", message });
    },
  });

  const lessonPlanMutation = useMutation({
    mutationFn: (decision: LessonPlanDecisionDraft) => {
      if (!workspace?.lessonPlanChecksum) throw new Error("Lesson Plan editing requires the current artifact checksum.");
      return saveLessonPlanDecision(courseId, decision, workspace.lessonPlanChecksum);
    },
    onSuccess: async (result) => {
      setLessonPlanDirty(false);
      setLessonPlanEditing(false);
      setLessonPlanConflict(false);
      setLessonPlanServerError(undefined);
      queryClient.setQueryData<{ workspace: Workspace; demoMode: boolean; readOnly: boolean }>(
        ["workspace", courseId],
        (current) => current ? { ...current, workspace: { ...current.workspace, lessonPlan: result.lessonPlan, lessonPlanChecksum: result.checksum || current.workspace.lessonPlanChecksum } } : current,
      );
      await refresh();
      const affected = result.lessonPlan.affectedSessionIds;
      setToast({
        tone: "good",
        message: affected.length
          ? `Lesson Plan saved as a canonical draft. Exact affected sessions: ${affected.join(", ")}.`
          : "Lesson Plan saved as a canonical draft. No session bodies changed.",
      });
    },
    onError: async (error) => {
      if (versionConflictChecksum(error)) {
        await refresh();
        setLessonPlanConflict(true);
        setLessonPlanServerError(undefined);
        setToast({ tone: "attention", message: "The Lesson Plan changed elsewhere. Your local delivery decision remains visible for review." });
        return;
      }
      const message = error instanceof Error ? error.message : "The Lesson Plan decision could not be saved.";
      setLessonPlanServerError(message);
      setToast({ tone: "attention", message });
    },
  });

  const knownSourceMutation = useMutation({
    mutationFn: (source: { locator: string; title?: string; publisher?: string; trustNotes?: string; relevance?: string }) => {
      if (!workspace?.research.dossierChecksum) throw new Error("Adding a known source requires the current Research Dossier checksum.");
      return addKnownSource(courseId, {
        expectedChecksum: workspace.research.dossierChecksum,
        ...source,
      });
    },
    onSuccess: async () => {
      await refresh();
      setToast({ tone: "good", message: "Known URL added as a proposed candidate. It still requires the normal human source decision." });
    },
    onError: async (error) => {
      const stale = Boolean(versionConflictChecksum(error));
      if (stale) await refresh();
      setToast({ tone: "attention", message: stale ? "The Research Dossier changed elsewhere. Review the latest candidates before adding this URL again." : error instanceof Error ? error.message : "The known source could not be added." });
    },
  });

  const sourceRepairRequestMutation = useMutation({
    mutationFn: ({ asset, claim }: { asset: ContentAsset; claim: Claim }) => {
      if (!workspace?.content.packageChecksum) throw new Error("Source repair requires the current Content Package checksum.");
      if (runMode === "live" && !workspace.providerReadiness.ready) throw new Error(workspace.providerReadiness.message);
      return requestSourceRepair(courseId, {
        expectedContentChecksum: workspace.content.packageChecksum,
        subtopicId: asset.subtopicId,
        assetId: asset.id,
        claimId: claim.id,
        findingId: claim.id,
        evidenceGap: claim.note || claim.text,
        mode: runMode,
      });
    },
    onSuccess: (result) => {
      setActiveJobId(result.job.job_id);
      setActiveJobStage("content");
      setRunProgress({ message: "Bounded evidence research queued" });
      setToast({ tone: "good", message: `Source Repair ${result.repairId} started for one finding. Approved routes remain unchanged.` });
      void refresh();
    },
    onError: (error) => {
      setToast({ tone: "attention", message: error instanceof Error ? error.message : "The source repair could not start." });
      void refresh();
    },
  });

  const sourceRepairDecisionMutation = useMutation({
    mutationFn: ({ entry, candidateId }: { entry: SourceRepairEntry; candidateId: string }) => {
      if (!workspace?.sourceRepairChecksum) throw new Error("Source repair decision requires the current ledger checksum.");
      return decideSourceRepair(courseId, entry.id, {
        expectedChecksum: workspace.sourceRepairChecksum,
        candidateId,
        decision: "approved",
        rationale: "Approved after reviewing the advisory score, bounded preview, and stated evidence-gap coverage.",
      });
    },
    onSuccess: async () => {
      await refresh();
      setToast({ tone: "good", message: "Source candidate approved. Confirm the exact subtopic and asset route before any canonical source mapping changes." });
    },
    onError: async (error) => {
      await refresh();
      setToast({ tone: "attention", message: error instanceof Error ? error.message : "The source decision could not be saved." });
    },
  });

  const sourceRepairRouteMutation = useMutation({
    mutationFn: (entry: SourceRepairEntry) => {
      if (!workspace?.sourceRepairChecksum) throw new Error("Route confirmation requires the current source-repair ledger checksum.");
      return confirmSourceRepairRoute(courseId, entry.id, {
        expectedChecksum: workspace.sourceRepairChecksum,
        subtopicIds: [entry.origin.subtopicId],
        assetIds: [entry.origin.assetId],
      });
    },
    onSuccess: async (result) => {
      await refresh();
      setToast({ tone: "good", message: `Source ${result.sourceId} was committed to the confirmed route only. Affected asset: ${result.affectedAssetIds.join(", ")}.` });
    },
    onError: async (error) => {
      await refresh();
      setToast({ tone: "attention", message: error instanceof Error ? error.message : "The source route could not be committed." });
    },
  });

  const contentRepairMutation = useMutation({
    mutationFn: ({
      strategy,
      asset,
      claim,
      entry,
    }: {
      strategy: "existing_evidence" | "better_evidence";
      asset: ContentAsset;
      claim?: Claim;
      entry?: SourceRepairEntry;
    }) => {
      if (!workspace?.content.packageChecksum) {
        throw new Error("Content repair requires the current Content Package checksum.");
      }
      if (strategy === "better_evidence" && !workspace.sourceRepairChecksum) {
        throw new Error("Better-evidence repair requires the current Source Repair checksum.");
      }
      const repairMode = entry?.requestedMode ?? runMode;
      if (repairMode === "live" && !workspace.providerReadiness.ready) {
        throw new Error(workspace.providerReadiness.message);
      }
      return requestContentRepair(courseId, {
        expectedContentChecksum: workspace.content.packageChecksum,
        strategy,
        targets: [{
          assetId: asset.id,
          claimIds: claim ? [claim.id] : [],
          findingIds: claim ? [claim.id] : [],
        }],
        sourceRepairId: entry?.id,
        expectedSourceRepairChecksum: entry ? workspace.sourceRepairChecksum : undefined,
        mode: repairMode,
      });
    },
    onSuccess: (result) => {
      setActiveJobId(result.job.job_id);
      setActiveJobStage("content");
      setRunProgress({ message: "Targeted regeneration and reverification queued" });
      setToast({
        tone: "good",
        message: `${result.strategy === "better_evidence" ? "Better-evidence" : "Existing-evidence"} repair started for ${result.targetAssetIds.join(", ")}.`,
      });
      void refresh();
    },
    onError: async (error) => {
      await refresh();
      setToast({
        tone: "attention",
        message: error instanceof Error ? error.message : "The targeted Content repair could not start.",
      });
    },
  });

  const impactMutation = useMutation({
    mutationFn: () => {
      if (!currentSummary?.checksum) throw new Error("Reopen requires the current stage checksum.");
      return previewStageImpact(courseId, stage, currentSummary.checksum, {
        action: "reopen",
        operationSummary: `Reopen ${stageName(stage)}`,
      });
    },
    onSuccess: setImpactPreview,
    onError: (error) => setToast({ tone: "attention", message: error instanceof Error ? error.message : "The impact preview could not be computed." }),
  });

  const reopenMutation = useMutation({
    mutationFn: (reason?: string) => {
      if (!impactPreview) throw new Error("A current impact preview is required.");
      if (!currentSummary?.checksum) throw new Error("Reopen requires the current stage checksum.");
      return reopenStage(courseId, stage, {
        expectedChecksum: currentSummary.checksum,
        impactChecksum: impactPreview.impactChecksum,
        reason,
      });
    },
    onSuccess: () => {
      setImpactPreview(null);
      setToast({ tone: "good", message: `${stageName(stage)} reopened. Downstream artifacts are preserved and marked stale.` });
      void refresh();
    },
    onError: (error) => {
      setImpactPreview(null);
      setToast({ tone: "attention", message: error instanceof ApiError && error.status === 409 ? "The course changed after this impact preview. Review a fresh preview before reopening." : error instanceof Error ? error.message : "The stage could not be reopened." });
      void refresh();
    },
  });

  const revisionImpactMutation = useMutation({
    mutationFn: ({ category, instruction }: { category: string; instruction: string }) => {
      if (!revisionTarget) throw new Error("Choose a record to revise.");
      return previewStageImpact(courseId, revisionTarget.stage, revisionTarget.expectedChecksum, {
        action: "revise",
        targetType: revisionTarget.targetType,
        targetIds: [revisionTarget.id],
        operationSummary: instruction,
      }).then((preview) => ({
        preview,
        pending: {
          ...revisionTarget,
          category,
          instruction,
        },
      }));
    },
    onSuccess: ({ preview, pending }) => {
      setRevisionTarget(null);
      setPendingRevision(pending);
      setRevisionImpact(preview);
    },
    onError: (error) => setToast({ tone: "attention", message: error instanceof Error ? error.message : "The revision impact could not be computed." }),
  });

  const revisionMutation = useMutation({
    mutationFn: () => {
      if (!pendingRevision || !revisionImpact) throw new Error("A current scoped revision impact preview is required.");
      const revisionMode = pendingRevision.stage === "content" ? runMode : "live";
      if (revisionMode === "live" && !workspace?.providerReadiness.ready) {
        throw new Error(workspace?.providerReadiness.message ?? "Live provider credentials are not configured on the server.");
      }
      return reviseStage(courseId, pendingRevision.stage, {
        targetType: pendingRevision.targetType,
        targetIds: [pendingRevision.id],
        category: pendingRevision.category,
        instruction: pendingRevision.instruction,
        expectedChecksum: pendingRevision.expectedChecksum,
        impactChecksum: revisionImpact.impactChecksum,
        mode: revisionMode,
      });
    },
    onSuccess: (result) => {
      const revisedStage = pendingRevision?.stage ?? stage;
      setPendingRevision(null);
      setRevisionImpact(null);
      setActiveJobId(result.job.job_id);
      setActiveJobStage(revisedStage);
      setRunProgress({ message: "Scoped revision queued" });
      setToast({ tone: "good", message: `Scoped ${stageName(revisedStage)} revision started. Unrelated records must remain unchanged.` });
      void refresh();
    },
    onError: (error) => {
      setRevisionImpact(null);
      setPendingRevision(null);
      setToast({ tone: "attention", message: error instanceof ApiError && error.status === 409 ? "The course changed after this impact preview. Review the record and try again." : error instanceof Error ? error.message : "The scoped revision could not start." });
      void refresh();
    },
  });

  async function contentAction(action: string, asset: ContentAsset, claim?: Claim) {
    if (!workspace) return;
    try {
      if (action === "approved" || action === "changes_requested") {
        if (!currentSummary?.actions.some((candidate) => candidate.id === "review_asset" && candidate.enabled)) throw new Error("Content review is not available in the current stage state.");
        if (!workspace.content.reviewChecksum) throw new Error("Content review requires the current checksum.");
        await reviewContentAsset(courseId, asset.id, action, workspace.content.reviewChecksum, claim?.note);
      } else if (action === "revise") {
        if (!currentSummary?.actions.some((candidate) => candidate.id === "revise" && candidate.enabled)) throw new Error("Scoped revision is not available in the current stage state.");
        if (runMode === "live" && !workspace.providerReadiness.ready) throw new Error(workspace.providerReadiness.message);
        if (!currentSummary.checksum) throw new Error("Revision requires the current Content checksum.");
        const categories = currentSummary.actions.find((candidate) => candidate.id === "revise")?.revisionTargets?.find((target) => target.targetType === "asset")?.categories ?? [];
        setRevisionTarget({ stage: "content", targetType: "asset", id: asset.id, label: asset.title, categories, expectedChecksum: currentSummary.checksum, claim });
        return;
      } else if (action === "repair_existing") {
        if (!currentSummary?.actions.some((candidate) => candidate.id === "content_repair" && candidate.enabled)) throw new Error("Typed Content repair is not available in the current stage state.");
        if (runMode === "live" && !workspace.providerReadiness.ready) throw new Error(workspace.providerReadiness.message);
        contentRepairMutation.mutate({ strategy: "existing_evidence", asset, claim });
        return;
      } else if (action === "source_repair") {
        if (!currentSummary?.actions.some((candidate) => candidate.id === "source_repair" && candidate.enabled)) throw new Error("Source repair is not available in the current stage state.");
        if (runMode === "live" && !workspace.providerReadiness.ready) throw new Error(workspace.providerReadiness.message);
        if (!claim) throw new Error("Source repair requires one named verifier finding.");
        sourceRepairRequestMutation.mutate({ asset, claim });
        return;
      } else {
        throw new Error("This content action is not implemented.");
      }
      setToast({
        tone: "good",
        message: `Review decision saved for ${asset.title}.`,
      });
      void refresh();
    } catch (error) {
      setToast({ tone: "attention", message: error instanceof Error ? error.message : "The content action failed." });
    }
  }

  function requestLiveRevision(targetType: string, id: string, label: string) {
    const action = currentSummary?.actions.find(
      (candidate) => candidate.id === "revise" && candidate.enabled,
    );
    const categories = action?.revisionTargets?.find(
      (target) => target.targetType === targetType,
    )?.categories;
    if (runMode !== "live") {
      setToast({
        tone: "attention",
        message: "Scoped revisions for this stage require explicit Live agent mode.",
      });
      return;
    }
    if (!action || !categories?.length || !currentSummary?.checksum) {
      setToast({
        tone: "attention",
        message: "Scoped revision is unavailable in the current stage state.",
      });
      return;
    }
    setRevisionTarget({
      stage,
      targetType,
      id,
      label,
      categories,
      expectedChecksum: currentSummary.checksum,
    });
  }

  async function sourceDecision(selectedIds: string[]) {
    if (!workspace) return;
    try {
      if (!currentSummary?.actions.some((candidate) => candidate.id === "source_decision" && candidate.enabled)) throw new Error("Source decisions are not available in the current stage state.");
      if (!currentSummary.checksum) throw new Error("Source decisions require the current Research checksum.");
      await saveSourceDecision(courseId, selectedIds, currentSummary.checksum);
      setToast({ tone: "good", message: `${selectedIds.length} grounding source${selectedIds.length === 1 ? "" : "s"} saved for review.` });
      void refresh();
    } catch (error) {
      setToast({ tone: "attention", message: error instanceof Error ? error.message : "The source decision could not be saved." });
    }
  }

  if (query.isLoading) return <LoadingState />;
  if (query.isError || !workspace) return <ErrorState message={query.error?.message ?? "No workspace data was returned."} onRetry={() => void query.refetch()} />;

  const context = stageContext[stage];
  const demoMode = query.data?.demoMode ?? false;
  const readOnly = query.data?.readOnly ?? false;
  const actionEnabled = (id: StageActionId) => Boolean(currentSummary?.actions.some((action) => action.id === id && action.enabled));
  const sourceRepairMode = sourceRepairModeAvailability(runMode, actionEnabled("source_repair"), workspace.providerReadiness.ready);
  const sourceRepairAvailable = sourceRepairMode.available;
  const sourceRepairUnavailableReason = sourceRepairMode.reason;
  const contentRepairAvailable = actionEnabled("content_repair") && (runMode !== "live" || workspace.providerReadiness.ready);
  const contentRevisionAvailable = actionEnabled("revise") && (runMode !== "live" || workspace.providerReadiness.ready);
  const routedContentRepairAvailable = actionEnabled("content_repair") && !workspace.sourceRepairs.some(
    (entry) => entry.status === "awaiting_content_repair" && entry.requestedMode === "live" && !workspace.providerReadiness.ready,
  );
  const briefQuestionsError = briefAnswersMutation.error instanceof Error
    ? briefAnswersMutation.error.message
    : briefQuestionsQuery.error instanceof Error
      ? briefQuestionsQuery.error.message
      : undefined;
  const handleStageAction = (action: StageAction) => {
    if (!action.enabled) return;
    if (action.id === "run" || action.id === "retry") {
      if (runMode === "live" && !workspace.providerReadiness.ready) {
        setToast({ tone: "attention", message: workspace.providerReadiness.message });
        return;
      }
      mutation.mutate({ type: "run" });
      return;
    }
    if (action.id === "approve") {
      mutation.mutate({ type: "approve" });
      return;
    }
    if (action.id === "reopen") {
      impactMutation.mutate();
      return;
    }
    if ((action.id === "continue" || action.id === "go_to_blocker") && action.targetStage) {
      navigate(`/courses/${courseId}/${action.targetStage}?mode=${runMode}`);
      return;
    }
    if (action.id === "edit") {
      if (stage === "outcomes") {
        setOutcomesServerError(undefined);
        setOutcomesServerIssues([]);
        setOutcomesConflict(false);
        setOutcomesEditing(true);
        return;
      }
      if (stage === "course-model") {
        setCourseModelServerError(undefined);
        setCourseModelServerIssues([]);
        setCourseModelConflict(false);
        setCourseModelPreview(null);
        setCourseModelDirty(false);
        setCourseModelEditing(true);
        return;
      }
      if (stage === "blueprint") {
        setBlueprintServerError(undefined);
        setBlueprintConflict(false);
        setBlueprintDirty(false);
        setBlueprintEditing(true);
        return;
      }
      if (stage === "lesson-plan") {
        setLessonPlanServerError(undefined);
        setLessonPlanConflict(false);
        setLessonPlanDirty(false);
        setLessonPlanEditing(true);
        return;
      }
      if (stage === "brief" && currentSummary?.status === "needs_input") {
        const intake = document.querySelector<HTMLElement>(".brief-intake-panel");
        intake?.scrollIntoView({ behavior: "smooth", block: "start" });
        intake?.querySelector<HTMLElement>("input, textarea, button")?.focus();
        return;
      }
      if (stage === "brief") setBriefEditSection("learner");
      return;
    }
    const selector = action.id === "source_decision"
      ? ".decision-tray"
      : action.id === "review_asset"
        ? ".content-status-banner"
        : action.id === "revise"
          ? ".verification-panel"
          : undefined;
    if (selector) document.querySelector(selector)?.scrollIntoView({ behavior: "smooth", block: "center" });
  };
  const changeRunMode = (nextMode: "deterministic" | "live") => {
    if (nextMode === "live" && !workspace.providerReadiness.ready) {
      setToast({ tone: "attention", message: workspace.providerReadiness.message });
      return;
    }
    setRunMode(nextMode);
    const params = new URLSearchParams(location.search);
    params.set("mode", nextMode);
    navigate({ pathname: location.pathname, search: params.toString() }, { replace: true });
  };
  return (
    <div className="workspace-shell">
      <header className="workspace-header">
        <AppBrand compact />
        <div className="workspace-course-title"><Link to="/courses">Courses</Link><span aria-hidden="true">/</span><div><strong>{workspace.course.title}</strong><small>{courseId}</small></div></div>
        <div className="workspace-header-actions">
          {demoMode ? <span className="environment-badge"><i /> Preview data</span> : readOnly ? <span className="environment-badge snapshot"><i /> Archived snapshot</span> : <span className="environment-badge connected"><i /> API connected</span>}
          <label className="run-mode-selector" title="Choose how stage runs execute"><span>Run mode</span><select aria-describedby={!workspace.providerReadiness.ready ? "live-readiness-message" : undefined} value={runMode} onChange={(event) => changeRunMode(event.target.value as "deterministic" | "live")}><option value="live" disabled={!workspace.providerReadiness.ready}>Live agent</option><option value="deterministic">Deterministic</option></select></label>
          {!workspace.providerReadiness.ready ? <span id="live-readiness-message" className="provider-readiness provider-unavailable" role="status"><i aria-hidden="true" /> Live unavailable · {workspace.providerReadiness.message}</span> : <span className="provider-readiness provider-ready" title={`${workspace.providerReadiness.provider} · ${workspace.providerReadiness.model}`}><i aria-hidden="true" /> Live ready</span>}
          {runProgress ? <span className="environment-badge connected run-progress"><i /> {runProgress.completed != null && runProgress.expected ? `${runProgress.completed}/${runProgress.expected} · ` : ""}{runProgress.message}</span> : null}
          {workspace.estimatedCost ? <span className="cost-note">${workspace.estimatedCost.toFixed(2)} est.</span> : null}
          <button className={`context-toggle ${inspectorOpen ? "active" : ""}`} onClick={() => setInspectorOpen((open) => !open)} aria-expanded={inspectorOpen}><span aria-hidden="true">i</span> Context</button>
          <button className="header-icon-button" onClick={() => setActivityOpen(true)} aria-label="Open activity"><span className="activity-bars" aria-hidden="true"><i /><i /><i /></span></button>
        </div>
      </header>
      <div className={`workspace-grid ${inspectorOpen ? "inspector-open" : ""}`}>
        <WorkflowRail workspace={workspace} activeStage={stage} activeJobStage={activeJobStage} runMode={runMode} onOpenActivity={() => setActivityOpen(true)} />
        <main className="stage-canvas" id="main-content">
          {(activeJobId && activeJobStage === stage) || (mutation.isPending && mutation.variables?.type === "run") ? (
            <AgentRunScreen stage={stage} mode={runMode} progress={runProgress} />
          ) : currentSummary?.status === "locked" && !demoMode ? (
            <div className="locked-stage-state"><span className="locked-glyph" aria-hidden="true">·</span><span className="eyebrow">{currentSummary.label}</span><h1>This stage is waiting on an upstream decision.</h1><p>{currentSummary.dependencies.length ? `${currentSummary.dependencies.map((item) => item.replaceAll("_", " ")).join(", ")} must be approved and current before this stage can run.` : "A backend prerequisite must be completed before this stage can run."}</p></div>
          ) : <StageView
            stage={stage}
            workspace={workspace}
            initialAssetId={new URLSearchParams(location.search).get("asset") ?? undefined}
            onNavigate={(targetStage, assetId) => navigate(`/courses/${courseId}/${targetStage}?mode=${runMode}${assetId ? `&asset=${encodeURIComponent(assetId)}` : ""}`)}
            contentCapabilities={{ review: actionEnabled("review_asset"), revise: contentRevisionAvailable, contentRepair: contentRepairAvailable, repair: sourceRepairAvailable, repairUnavailableReason: sourceRepairUnavailableReason }}
            onContentAction={actionEnabled("review_asset") || contentRevisionAvailable || contentRepairAvailable || sourceRepairAvailable ? (action, asset, claim) => void contentAction(action, asset, claim) : undefined}
            onRequestRevision={stage !== "content" && actionEnabled("revise") && workspace.providerReadiness.ready ? requestLiveRevision : undefined}
            onSourceDecision={actionEnabled("source_decision") ? (selectedIds) => void sourceDecision(selectedIds) : undefined}
            onAddKnownSource={actionEnabled("add_source") ? (source) => knownSourceMutation.mutate(source) : undefined}
            sourceMutationBusy={knownSourceMutation.isPending}
            sourceRepairBusy={sourceRepairRequestMutation.isPending || sourceRepairDecisionMutation.isPending || sourceRepairRouteMutation.isPending || contentRepairMutation.isPending || Boolean(activeJobId)}
            onSourceRepairDecision={sourceRepairAvailable ? (entry, candidateId) => sourceRepairDecisionMutation.mutate({ entry, candidateId }) : undefined}
            onSourceRepairRoute={sourceRepairAvailable ? (entry) => sourceRepairRouteMutation.mutate(entry) : undefined}
            onContentRepair={routedContentRepairAvailable ? (entry) => {
              if (entry.requestedMode === "live" && !workspace.providerReadiness.ready) {
                setToast({ tone: "attention", message: workspace.providerReadiness.message });
                return;
              }
              const asset = workspace.content.assets.find((candidate) => candidate.id === entry.origin.assetId);
              const claim = asset?.claims.find((candidate) => candidate.id === entry.origin.claimId);
              if (asset) contentRepairMutation.mutate({ strategy: "better_evidence", asset, claim, entry });
            } : undefined}
            onEditBrief={stage === "brief" && actionEnabled("edit") ? setBriefEditSection : undefined}
            outcomesEditing={outcomesEditing}
            outcomesBusy={outcomesMutation.isPending || mutation.isPending || impactMutation.isPending || reopenMutation.isPending || revisionImpactMutation.isPending || revisionMutation.isPending || briefMutation.isPending || briefAnswersMutation.isPending || Boolean(activeJobId)}
            outcomesConflict={outcomesConflict}
            outcomesServerError={outcomesServerError}
            outcomesServerIssues={outcomesServerIssues}
            onStartOutcomesEdit={outcomesEditCapability ? () => { setOutcomesServerError(undefined); setOutcomesServerIssues([]); setOutcomesConflict(false); setOutcomesDirty(false); setOutcomesEditing(true); } : undefined}
            onCancelOutcomesEdit={() => { setOutcomesEditing(false); setOutcomesDirty(false); setOutcomesConflict(false); setOutcomesServerError(undefined); setOutcomesServerIssues([]); }}
            onSaveOutcomes={(decision) => { setOutcomesServerError(undefined); setOutcomesServerIssues([]); outcomesMutation.mutate(decision); }}
            onResolveOutcomesConflict={() => { setOutcomesConflict(false); setOutcomesServerError(undefined); setOutcomesServerIssues([]); }}
            onOutcomesDirtyChange={setOutcomesDirty}
            courseModelEditing={courseModelEditing}
            courseModelBusy={courseModelPreviewMutation.isPending || courseModelSaveMutation.isPending || mutation.isPending || impactMutation.isPending || reopenMutation.isPending || Boolean(activeJobId)}
            courseModelConflict={courseModelConflict}
            courseModelServerError={courseModelServerError}
            courseModelServerIssues={courseModelServerIssues}
            courseModelPreview={courseModelPreview}
            onStartCourseModelEdit={courseModelEditCapability ? () => { setCourseModelServerError(undefined); setCourseModelServerIssues([]); setCourseModelConflict(false); setCourseModelPreview(null); setCourseModelDirty(false); setCourseModelEditing(true); } : undefined}
            onCancelCourseModelEdit={() => { setCourseModelEditing(false); setCourseModelDirty(false); setCourseModelConflict(false); setCourseModelServerError(undefined); setCourseModelServerIssues([]); setCourseModelPreview(null); }}
            onPreviewCourseModel={(operations) => { setCourseModelServerError(undefined); setCourseModelServerIssues([]); courseModelPreviewMutation.mutate(operations); }}
            onSaveCourseModel={(operations, impactChecksum) => courseModelSaveMutation.mutate({ operations, impactChecksum })}
            onInvalidateCourseModelPreview={() => setCourseModelPreview(null)}
            onRecoverCourseModelConflict={(choice) => { setCourseModelConflict(false); setCourseModelServerError(undefined); setCourseModelServerIssues([]); setCourseModelPreview(null); if (choice === "discard") { setCourseModelEditing(false); setCourseModelDirty(false); } }}
            onCourseModelDirtyChange={setCourseModelDirty}
            blueprintEditing={blueprintEditing}
            blueprintBusy={blueprintMutation.isPending || mutation.isPending || impactMutation.isPending || reopenMutation.isPending || Boolean(activeJobId)}
            blueprintConflict={blueprintConflict}
            blueprintServerError={blueprintServerError}
            onStartBlueprintEdit={blueprintEditCapability ? () => { setBlueprintServerError(undefined); setBlueprintConflict(false); setBlueprintDirty(false); setBlueprintEditing(true); } : undefined}
            onCancelBlueprintEdit={() => { setBlueprintEditing(false); setBlueprintDirty(false); setBlueprintConflict(false); setBlueprintServerError(undefined); }}
            onSaveBlueprint={(decision) => { setBlueprintServerError(undefined); blueprintMutation.mutate(decision); }}
            onRecoverBlueprintConflict={(choice) => { setBlueprintConflict(false); setBlueprintServerError(undefined); if (choice === "discard") { setBlueprintEditing(false); setBlueprintDirty(false); } }}
            onBlueprintDirtyChange={setBlueprintDirty}
            lessonPlanEditing={lessonPlanEditing}
            lessonPlanBusy={lessonPlanMutation.isPending || mutation.isPending || impactMutation.isPending || reopenMutation.isPending || Boolean(activeJobId)}
            lessonPlanConflict={lessonPlanConflict}
            lessonPlanServerError={lessonPlanServerError}
            onStartLessonPlanEdit={lessonPlanEditCapability ? () => { setLessonPlanServerError(undefined); setLessonPlanConflict(false); setLessonPlanDirty(false); setLessonPlanEditing(true); } : undefined}
            onCancelLessonPlanEdit={() => { setLessonPlanEditing(false); setLessonPlanDirty(false); setLessonPlanConflict(false); setLessonPlanServerError(undefined); }}
            onSaveLessonPlan={(decision) => { setLessonPlanServerError(undefined); lessonPlanMutation.mutate(decision); }}
            onRecoverLessonPlanConflict={(choice) => { setLessonPlanConflict(false); setLessonPlanServerError(undefined); if (choice === "discard") { setLessonPlanEditing(false); setLessonPlanDirty(false); } }}
            onLessonPlanDirtyChange={setLessonPlanDirty}
            briefQuestionRound={briefQuestionsQuery.data}
            briefQuestionsLoading={briefQuestionsQuery.isLoading || briefQuestionsQuery.isFetching && !briefQuestionsQuery.data}
            briefQuestionsBusy={briefAnswersMutation.isPending}
            briefQuestionsError={briefQuestionsError}
            onRetryBriefQuestions={() => void briefQuestionsQuery.refetch()}
            onSubmitBriefQuestions={(answers) => briefAnswersMutation.mutate(answers)}
          />}
        </main>
        {inspectorOpen ? <ContextInspector workspace={workspace} stage={stage} onClose={() => setInspectorOpen(false)} /> : null}
        <DecisionBar
          stage={stage}
          status={currentSummary?.status ?? "ready"}
          actions={(currentSummary?.actions ?? []).map((action) => runMode === "live" && !workspace.providerReadiness.ready && ["run", "retry"].includes(action.id) ? { ...action, enabled: false, reason: workspace.providerReadiness.message } : action)}
          busy={mutation.isPending || outcomesMutation.isPending || outcomesEditing || courseModelPreviewMutation.isPending || courseModelSaveMutation.isPending || courseModelEditing || blueprintMutation.isPending || blueprintEditing || lessonPlanMutation.isPending || lessonPlanEditing || impactMutation.isPending || reopenMutation.isPending || revisionImpactMutation.isPending || revisionMutation.isPending || briefMutation.isPending || briefAnswersMutation.isPending || knownSourceMutation.isPending || sourceRepairRequestMutation.isPending || sourceRepairDecisionMutation.isPending || sourceRepairRouteMutation.isPending || Boolean(activeJobId)}
          onAction={handleStageAction}
        />
      </div>
      {activityOpen ? <ActivityDrawer workspace={workspace} onClose={() => setActivityOpen(false)} /> : null}
      {revisionTarget ? <ScopedRevisionDialog target={revisionTarget} busy={revisionImpactMutation.isPending} onCancel={() => setRevisionTarget(null)} onSubmit={(category, instruction) => revisionImpactMutation.mutate({ category, instruction })} /> : null}
      {revisionImpact && pendingRevision ? <RevisionImpactConfirmationDialog stage={pendingRevision.stage} preview={revisionImpact} busy={revisionMutation.isPending} onCancel={() => { setRevisionImpact(null); setPendingRevision(null); }} onConfirm={() => revisionMutation.mutate()} /> : null}
      {impactPreview ? <ImpactConfirmationDialog stage={stage} preview={impactPreview} busy={reopenMutation.isPending} onCancel={() => setImpactPreview(null)} onConfirm={(reason) => reopenMutation.mutate(reason)} /> : null}
      {briefEditSection ? <BriefEditDialog section={briefEditSection} brief={workspace.brief} busy={briefMutation.isPending} onCancel={() => setBriefEditSection(null)} onSubmit={(brief) => briefMutation.mutate(brief)} /> : null}
      {toast ? <Toast message={toast.message} tone={toast.tone} onClose={() => setToast(null)} /> : null}
    </div>
  );
}
