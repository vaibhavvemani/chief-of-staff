import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  ApiError,
  approveStage,
  getWorkspace,
  previewStageImpact,
  reopenStage,
  reviseStage,
  reviewContentAsset,
  runStage,
  saveBriefAnswers,
  saveSourceDecision,
  subscribeToJob,
} from "../../api/client";
import { AppBrand } from "../../components/AppBrand";
import { ErrorState, LoadingState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";
import type { BriefAnswers, BriefData, Claim, ContentAsset, ImpactPreview, StageAction, StageActionId, StageSlug, UiStatus, Workspace } from "../../types";
import { StageView, stageData, type BriefEditSection } from "./StageViews";

const stageSlugs: StageSlug[] = ["brief", "outcomes", "research", "course-model", "blueprint", "content", "lesson-plan", "package"];

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
  return (
    <div className="drawer-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose(); }}>
      <aside className="activity-drawer" role="dialog" aria-modal="true" aria-labelledby="activity-title">
        <header><div><span className="eyebrow">Audit & diagnostics</span><h2 id="activity-title">Activity</h2></div><button onClick={onClose} aria-label="Close activity drawer">×</button></header>
        <div className="run-summary-card"><div><span className="run-glyph" aria-hidden="true">{failedStage ? "!" : activeStage ? "…" : "✓"}</span><span><strong>{failedStage ? `${stageName(failedStage.slug)} run failed` : activeStage ? `${stageName(activeStage)} run in progress` : "Workspace state is current"}</strong><small>{failedStage?.lastFailure ?? workspace.course.nextAction}</small></span></div><code>{workspace.course.courseId}</code></div>
        <div className="activity-list">{workspace.activity.map((event) => <article key={event.id}><time>{new Date(event.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time><span className={`activity-dot activity-${event.tone ?? "neutral"}`} /><div><strong>{event.title}</strong><p>{event.detail}</p></div></article>)}</div>
        <footer><button className="button button-secondary full-width" disabled title="Model-call diagnostics are not exposed in this release">Model-call diagnostics unavailable</button><p>Prompts, source bodies, and private reasoning are never shown in activity events.</p></footer>
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
  const primaryIds: StageActionId[] = ["run", "retry", "edit", "source_decision", "review_asset", "revise", "approve", "go_to_blocker", "continue"];
  const inlineActionIds: StageActionId[] = ["source_decision", "review_asset", "revise"];
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
      <div className={`agent-run-track ${percent == null ? "indeterminate" : ""}`} aria-hidden="true"><span style={percent == null ? undefined : { width: `${percent}%` }} /></div>
      <p className="agent-run-note">Live runs may take a few minutes. Approval will only be available after the output is fully saved.</p>
    </section>
  );
}

function ScopedRevisionDialog({ asset, claim, categories, busy, onCancel, onSubmit }: { asset: ContentAsset; claim?: Claim; categories: string[]; busy: boolean; onCancel: () => void; onSubmit: (category: string, instruction: string) => void }) {
  const [category, setCategory] = useState(categories.includes("evidence") && claim ? "evidence" : categories[0] ?? "clarity");
  const [instruction, setInstruction] = useState(claim ? `Correct verifier finding ${claim.id}: ${claim.note || claim.text}` : "");
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") onCancel(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onCancel]);
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onCancel(); }}>
      <div className="feedback-dialog" role="dialog" aria-modal="true" aria-labelledby="revision-title">
        <header><span className="eyebrow">Scoped content revision</span><h2 id="revision-title">Revise {asset.title}</h2><p>Only <code>{asset.id}</code> will be regenerated. Other content assets remain unchanged.</p></header>
        <label><span>Revision category</span><select value={category} onChange={(event) => setCategory(event.target.value)}>{categories.map((item) => <option key={item} value={item}>{item.charAt(0).toUpperCase() + item.slice(1)}</option>)}</select></label>
        <label><span>Revision instruction</span><textarea autoFocus rows={5} value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="Describe the exact learner-facing change required for this asset." /></label>
        <div className="impact-preview"><span className="micro-label">Execution boundary</span><div><span aria-hidden="true">→</span>Target type: asset</div><div><span aria-hidden="true">→</span>Target ID: {asset.id}</div><div><span aria-hidden="true">→</span>Execution mode preserves unaffected assets</div></div>
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

const briefSectionLabels: Record<BriefEditSection, string> = {
  settings: "Course settings",
  learner: "Learner and intent",
  scope: "Scope boundary",
  coverage: "Coverage and constraints",
  assumptions: "Starting assumptions",
};

function listFromText(value: string): string[] {
  return value.split("\n").map((item) => item.trim()).filter(Boolean);
}

function BriefEditDialog({ section, brief, busy, onCancel, onSubmit }: { section: BriefEditSection; brief: BriefData; busy: boolean; onCancel: () => void; onSubmit: (brief: BriefData) => void }) {
  const [draft, setDraft] = useState<BriefData>(() => ({
    ...brief,
    inScope: [...brief.inScope],
    outOfScope: [...brief.outOfScope],
    mustHaveTopics: [...brief.mustHaveTopics],
    constraints: [...brief.constraints],
    assumptions: [...brief.assumptions],
  }));
  const update = <K extends keyof BriefData>(key: K, value: BriefData[K]) => setDraft((current) => ({ ...current, [key]: value }));
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
            <label><span>Assessment expectation</span><textarea rows={2} value={draft.assessmentExpectations} onChange={(event) => update("assessmentExpectations", event.target.value)} /></label>
          </> : null}
          {section === "scope" ? <div className="brief-editor-grid">
            <label><span>In scope <small>One item per line</small></span><textarea autoFocus rows={6} value={draft.inScope.join("\n")} onChange={(event) => update("inScope", listFromText(event.target.value))} /></label>
            <label><span>Out of scope <small>One item per line</small></span><textarea rows={6} value={draft.outOfScope.join("\n")} onChange={(event) => update("outOfScope", listFromText(event.target.value))} /></label>
          </div> : null}
          {section === "coverage" ? <div className="brief-editor-grid">
            <label><span>Must-have topics <small>One item per line</small></span><textarea autoFocus rows={6} value={draft.mustHaveTopics.join("\n")} onChange={(event) => update("mustHaveTopics", listFromText(event.target.value))} /></label>
            <label><span>Constraints <small>One item per line</small></span><textarea rows={6} value={draft.constraints.join("\n")} onChange={(event) => update("constraints", listFromText(event.target.value))} /></label>
          </div> : null}
          {section === "assumptions" ? <>
            <div className="assumption-editor-note"><span aria-hidden="true">i</span><p>These are the most common defaults to correct. Saving them makes your choices explicit in the Brief.</p></div>
            <label><span>Audience</span><textarea autoFocus rows={2} value={draft.audience} onChange={(event) => update("audience", event.target.value)} /></label>
            {settingsFields}
          </> : null}
        </div>
        <footer><button className="button button-quiet" onClick={onCancel}>Cancel</button><button className="button button-primary" disabled={!canSave || busy} onClick={() => onSubmit(draft)}>{busy ? "Saving…" : "Save section"}</button></footer>
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
  const [revisionTarget, setRevisionTarget] = useState<{ asset: ContentAsset; claim?: Claim; expectedChecksum?: string } | null>(null);
  const [briefEditSection, setBriefEditSection] = useState<BriefEditSection | null>(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [toast, setToast] = useState<{ message: string; tone: "good" | "attention" | "neutral" } | null>(() => new URLSearchParams(location.search).get("setup") === "incomplete" ? {
    tone: "attention",
    message: "The course was created, but its starting Brief could not be saved. Review the suggested defaults and use Adjust to save them.",
  } : null);
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

  useEffect(() => {
    if (!workspace?.activeJob || activeJobId === workspace.activeJob.jobId || completedJobIds.current.has(workspace.activeJob.jobId)) return;
    setActiveJobId(workspace.activeJob.jobId);
    setActiveJobStage(workspace.activeJob.stage);
    setRunProgress({ message: workspace.activeJob.status === "queued" ? "Run queued" : "Agent run in progress" });
  }, [activeJobId, workspace?.activeJob]);

  const briefMutation = useMutation({
    mutationFn: async (edited: BriefData) => {
      if (!workspace || query.data?.demoMode) return { demo: true };
      const answers: BriefAnswers = {
        courseTitle: edited.courseTitle,
        audience: edited.audience,
        priorKnowledge: edited.priorKnowledge,
        purpose: edited.purpose,
        level: edited.level,
        duration: edited.duration,
        modality: edited.modality,
        language: edited.language,
        inScope: edited.inScope,
        outOfScope: edited.outOfScope,
        mustHaveTopics: edited.mustHaveTopics,
        constraints: edited.constraints,
        assessmentExpectations: edited.assessmentExpectations,
      };
      return saveBriefAnswers(courseId, answers, workspace.briefChecksum);
    },
    onSuccess: (result) => {
      setBriefEditSection(null);
      setToast({ tone: "good", message: result && "demo" in result ? "Preview changes recorded for this section." : "Brief section saved. Review the updated draft before approval." });
      const params = new URLSearchParams(location.search);
      if (params.has("setup")) {
        params.delete("setup");
        navigate({ pathname: location.pathname, search: params.toString() }, { replace: true });
      }
      void queryClient.invalidateQueries({ queryKey: ["workspace", courseId] });
    },
    onError: (error) => {
      const stale = error instanceof ApiError && error.status === 409;
      setToast({ tone: "attention", message: stale ? "The Brief changed in another session. Refresh and try again." : error.message });
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
      const stale = error instanceof ApiError && error.status === 409;
      setToast({ tone: "attention", message: stale ? "This artifact changed in another session. Refresh before submitting your decision." : error.message });
    },
  });

  const impactMutation = useMutation({
    mutationFn: () => {
      if (!currentSummary?.checksum) throw new Error("Reopen requires the current stage checksum.");
      return previewStageImpact(courseId, stage, currentSummary.checksum, `Reopen ${stageName(stage)}`);
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

  const revisionMutation = useMutation({
    mutationFn: ({ category, instruction }: { category: string; instruction: string }) => {
      if (!revisionTarget) throw new Error("Choose a content asset to revise.");
      if (!revisionTarget.expectedChecksum) throw new Error("Revision requires the current Content checksum.");
      return reviseStage(courseId, "content", {
        targetType: "asset",
        targetIds: [revisionTarget.asset.id],
        category,
        instruction,
        expectedChecksum: revisionTarget.expectedChecksum,
        mode: runMode,
      });
    },
    onSuccess: (result) => {
      setRevisionTarget(null);
      setActiveJobId(result.job.job_id);
      setActiveJobStage("content");
      setRunProgress({ message: "Scoped revision queued" });
      setToast({ tone: "good", message: "Scoped revision started. Unaffected content assets will be preserved." });
      void refresh();
    },
    onError: (error) => setToast({ tone: "attention", message: error instanceof Error ? error.message : "The scoped revision could not start." }),
  });

  async function contentAction(action: string, asset: ContentAsset, claim?: Claim) {
    if (!workspace) return;
    try {
      if (action === "approved" || action === "changes_requested") {
        if (!currentSummary?.actions.some((candidate) => candidate.id === "review_asset" && candidate.enabled)) throw new Error("Content review is not available in the current stage state.");
        await reviewContentAsset(courseId, asset.id, action, workspace.content.reviewChecksum, claim?.note);
      } else if (action === "revise") {
        if (!currentSummary?.actions.some((candidate) => candidate.id === "revise" && candidate.enabled)) throw new Error("Scoped revision is not available in the current stage state.");
        setRevisionTarget({ asset, claim, expectedChecksum: currentSummary.checksum });
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

  async function sourceDecision(selectedIds: string[]) {
    if (!workspace) return;
    try {
      if (!currentSummary?.actions.some((candidate) => candidate.id === "source_decision" && candidate.enabled)) throw new Error("Source decisions are not available in the current stage state.");
      await saveSourceDecision(courseId, selectedIds, currentSummary?.checksum);
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
  const handleStageAction = (action: StageAction) => {
    if (!action.enabled) return;
    if (action.id === "run" || action.id === "retry") {
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
      setBriefEditSection("learner");
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
          <label className="run-mode-selector" title="Choose how stage runs execute"><span>Run mode</span><select value={runMode} onChange={(event) => changeRunMode(event.target.value as "deterministic" | "live")}><option value="live">Live agent</option><option value="deterministic">Deterministic</option></select></label>
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
          ) : <StageView stage={stage} workspace={workspace} contentCapabilities={{ review: actionEnabled("review_asset"), revise: actionEnabled("revise") }} onContentAction={actionEnabled("review_asset") || actionEnabled("revise") ? (action, asset, claim) => void contentAction(action, asset, claim) : undefined} onSourceDecision={actionEnabled("source_decision") ? (selectedIds) => void sourceDecision(selectedIds) : undefined} onEditBrief={actionEnabled("edit") ? setBriefEditSection : undefined} />}
        </main>
        {inspectorOpen ? <ContextInspector workspace={workspace} stage={stage} onClose={() => setInspectorOpen(false)} /> : null}
        <DecisionBar
          stage={stage}
          status={currentSummary?.status ?? "ready"}
          actions={currentSummary?.actions ?? []}
          busy={mutation.isPending || impactMutation.isPending || reopenMutation.isPending || revisionMutation.isPending || Boolean(activeJobId)}
          onAction={handleStageAction}
        />
      </div>
      {activityOpen ? <ActivityDrawer workspace={workspace} onClose={() => setActivityOpen(false)} /> : null}
      {revisionTarget ? <ScopedRevisionDialog asset={revisionTarget.asset} claim={revisionTarget.claim} categories={currentSummary?.actions.find((action) => action.id === "revise")?.revisionTargets?.find((target) => target.targetType === "asset")?.categories ?? []} busy={revisionMutation.isPending} onCancel={() => setRevisionTarget(null)} onSubmit={(category, instruction) => revisionMutation.mutate({ category, instruction })} /> : null}
      {impactPreview ? <ImpactConfirmationDialog stage={stage} preview={impactPreview} busy={reopenMutation.isPending} onCancel={() => setImpactPreview(null)} onConfirm={(reason) => reopenMutation.mutate(reason)} /> : null}
      {briefEditSection ? <BriefEditDialog section={briefEditSection} brief={workspace.brief} busy={briefMutation.isPending} onCancel={() => setBriefEditSection(null)} onSubmit={(brief) => briefMutation.mutate(brief)} /> : null}
      {toast ? <Toast message={toast.message} tone={toast.tone} onClose={() => setToast(null)} /> : null}
    </div>
  );
}
