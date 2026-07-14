import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  ApiError,
  approveStage,
  getWorkspace,
  requestStageChanges,
  reviewContentAsset,
  runStage,
  saveBriefAnswers,
  saveSourceDecision,
  subscribeToJob,
} from "../../api/client";
import { AppBrand } from "../../components/AppBrand";
import { ErrorState, LoadingState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";
import type { BriefAnswers, BriefData, Claim, ContentAsset, StageSlug, UiStatus, Workspace } from "../../types";
import { StageView, stageData, type BriefEditSection } from "./StageViews";

const stageSlugs: StageSlug[] = ["brief", "outcomes", "research", "course-model", "blueprint", "content", "lesson-plan", "package"];

function nextStageAfter(stage: StageSlug): StageSlug | null {
  const index = stageSlugs.indexOf(stage);
  return index >= 0 && index < stageSlugs.length - 1 ? stageSlugs[index + 1] : null;
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

const stageContext: Record<StageSlug, { why: string; evidence: string; consumes: string[]; affects: string[] }> = {
  brief: {
    why: "The Brief translates a sparse subject request into explicit audience, scope, constraints, and assumptions before expensive work begins.",
    evidence: "Intake answers and visible safe defaults. Assumptions remain editable until the Brief is approved.",
    consumes: ["Subject request"],
    affects: ["Outcomes", "Research", "Every downstream artifact"],
  },
  outcomes: {
    why: "Measurable outcomes make downstream coverage and assessment decisions testable instead of relying on a general topic description.",
    evidence: "Approved Brief: audience, purpose, scope, level, and assessment expectations.",
    consumes: ["Approved Brief"],
    affects: ["Research scope", "Course Model coverage", "Assessments"],
  },
  research: {
    why: "The agent separates curriculum evidence from factual grounding so weak or rejected pages cannot silently enter learner content.",
    evidence: "Bounded competitor outlines, candidate metadata, trust notes, and explicit human source decisions.",
    consumes: ["Approved Brief", "Approved Outcomes"],
    affects: ["Course Model source routes", "Generated claims", "Verification"],
  },
  "course-model": {
    why: "This compact hierarchy is the structural source of truth. Stable IDs let every downstream asset remain referentially auditable.",
    evidence: "Outcomes, competitor synthesis, approved sources, scope rules, and structural rationale.",
    consumes: ["Brief", "Outcomes", "Approved source registry"],
    affects: ["Blueprint rows", "Content coverage", "Lesson Plan", "Rendered paths"],
  },
  blueprint: {
    why: "The Blueprint makes asset generation an explicit product decision for each subtopic, with defaults and visible exceptions.",
    evidence: "Course Model coverage and source assignments, course-wide depth defaults, and explicit asset decisions.",
    consumes: ["Approved Course Model"],
    affects: ["Exact generated assets", "Depth budget", "Verification scope"],
  },
  content: {
    why: "Content is generated per asset and checked claim by claim. The operator resolves only material evidence and quality issues.",
    evidence: "Approved source excerpts routed by subtopic, generation claims, verifier verdicts, and durable human reviews.",
    consumes: ["Course Model", "Blueprint", "Approved source excerpts"],
    affects: ["Lesson Plan readiness", "Package release status"],
  },
  "lesson-plan": {
    why: "The Lesson Plan sequences approved content into feasible sessions while reconciling time, delivery mode, and complete subtopic coverage.",
    evidence: "Course Model sequence, selected assets, delivery constraints, and coverage reconciliation.",
    consumes: ["Approved content", "Brief delivery constraints"],
    affects: ["Rendered lesson plan", "Package coverage gate"],
  },
  package: {
    why: "A rendered folder is not automatically learner-ready. The release gate reconciles integrity, evidence, review, and output paths.",
    evidence: "Integrity checks, run summary, verifier blockers, review decisions, and render manifest.",
    consumes: ["All approved upstream artifacts"],
    affects: ["Course delivery"],
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
              <span className="rail-stage-state" aria-hidden="true">{stage.status === "approved" ? "✓" : stage.status === "requires_attention" ? stage.count || "!" : stage.status === "locked" ? "·" : "→"}</span>
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
        {tab === "dependencies" ? <div className="dependency-map"><span className="inspector-section-label">Consumes</span>{context.consumes.map((item) => <div key={item} className="dependency-item before"><span aria-hidden="true">←</span>{item}</div>)}<div className="current-dependency">{stageSummary?.label}</div><span className="inspector-section-label">Affects</span>{context.affects.map((item) => <div key={item} className="dependency-item after"><span aria-hidden="true">→</span>{item}</div>)}</div> : null}
        {tab === "history" ? <div className="inspector-history"><span className="inspector-section-label">Recent events</span>{workspace.activity.map((event) => <article key={event.id}><span className={`history-dot history-${event.tone ?? "neutral"}`} /><div><strong>{event.title}</strong><p>{event.detail}</p><time>{new Date(event.at).toLocaleString()}</time></div></article>)}</div> : null}
        {tab === "raw" ? <><div className="raw-heading"><span className="inspector-section-label">Canonical data</span><button onClick={() => void navigator.clipboard?.writeText(JSON.stringify(stageData(stage, workspace), null, 2))}>Copy</button></div><pre className="inspector-raw">{JSON.stringify(stageData(stage, workspace), null, 2)}</pre></> : null}
      </div>
    </aside>
  );
}

function ActivityDrawer({ workspace, onClose }: { workspace: Workspace; onClose: () => void }) {
  return (
    <div className="drawer-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onClose(); }}>
      <aside className="activity-drawer" role="dialog" aria-modal="true" aria-labelledby="activity-title">
        <header><div><span className="eyebrow">Audit & diagnostics</span><h2 id="activity-title">Activity</h2></div><button onClick={onClose} aria-label="Close activity drawer">×</button></header>
        <div className="run-summary-card"><div><span className="run-glyph" aria-hidden="true">✓</span><span><strong>Latest pipeline run completed</strong><small>Content still needs operator attention</small></span></div><code>{workspace.course.courseId}</code></div>
        <div className="activity-list">{workspace.activity.map((event) => <article key={event.id}><time>{new Date(event.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time><span className={`activity-dot activity-${event.tone ?? "neutral"}`} /><div><strong>{event.title}</strong><p>{event.detail}</p></div></article>)}</div>
        <footer><button className="button button-secondary full-width">Open model-call diagnostics</button><p>Prompts, source bodies, and private reasoning are never shown in activity events.</p></footer>
      </aside>
    </div>
  );
}

function DecisionBar({
  stage,
  status,
  disabled,
  busy,
  onApprove,
  onRequestChanges,
  onRun,
  nextStage,
  onContinue,
  approvalBlocked,
}: {
  stage: StageSlug;
  status: UiStatus;
  disabled?: boolean;
  busy?: boolean;
  onApprove: () => void;
  onRequestChanges: () => void;
  onRun: () => void;
  nextStage: StageSlug | null;
  onContinue: () => void;
  approvalBlocked?: boolean;
}) {
  const isApproved = status === "approved";
  const isLocked = status === "locked";
  const attention = status === "requires_attention";
  const canRequestChanges = ["awaiting_review", "requires_attention", "failed", "stale"].includes(status);
  return (
    <div className="decision-bar">
      <div className="decision-context"><span className={`decision-dot decision-${status}`} /><div><small>{isApproved ? "Checkpoint recorded" : approvalBlocked ? "Source decision required" : attention ? "Human decision needed" : isLocked ? "Upstream checkpoint required" : status === "running" ? "Agent working" : "Stage action"}</small><strong>{isApproved ? nextStage ? `${stageName(nextStage)} is next` : "Course workflow complete" : approvalBlocked ? "Select and save grounding sources first" : attention ? "Resolve blockers before approval" : isLocked ? "This stage is not ready to run" : status === "ready" ? `Ready to build ${stageName(stage)}` : status === "running" ? `Building ${stageName(stage)}` : "Review before continuing"}</strong></div></div>
      <div className="decision-actions">
        {canRequestChanges ? <button className="button button-secondary" disabled={disabled || busy || isLocked} onClick={onRequestChanges}>{stage === "brief" ? "Other change" : "Request changes"}</button> : null}
        {attention && stage === "content" ? <button className="button button-primary" onClick={() => document.querySelector(".attention-banner")?.scrollIntoView({ behavior: "smooth" })}>Review attention queue <span aria-hidden="true">→</span></button> : isApproved ? <button className="button button-primary" disabled={!nextStage} onClick={onContinue}>{nextStage ? `Continue to ${stageName(nextStage)}` : "Course complete"} {nextStage ? <span aria-hidden="true">→</span> : null}</button> : status === "ready" ? <button className="button button-primary" disabled={disabled || busy || isLocked} onClick={onRun}>{busy ? "Starting agent…" : `Run ${stageName(stage)}`} <span aria-hidden="true">→</span></button> : status === "running" ? <button className="button button-primary" disabled>Agent working…</button> : <button className="button button-primary" disabled={disabled || busy || isLocked || approvalBlocked} onClick={onApprove}>{busy ? "Approving…" : approvalBlocked ? "Save source selection first" : `Approve ${stageName(stage)}`} {!approvalBlocked ? <span aria-hidden="true">→</span> : null}</button>}
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

const revisionSuggestions: Record<StageSlug, string[]> = {
  brief: ["Correct the learner or level", "Narrow or expand the scope", "Add a missing constraint"],
  outcomes: ["Make an outcome measurable", "Add missing learner evidence", "Remove an outcome that is out of scope"],
  research: ["Find a stronger primary source", "Remove an unsuitable source", "Cover a missing evidence area"],
  "course-model": ["Reorganize a module", "Add a missing subtopic", "Correct source routing"],
  blueprint: ["Change the asset mix", "Adjust depth or duration", "Add an assessment asset"],
  content: ["Correct an unsupported claim", "Improve clarity for the learner", "Add a practical example"],
  "lesson-plan": ["Rebalance session timing", "Change the delivery mode", "Improve the teaching sequence"],
  package: ["Resolve a release blocker", "Correct a rendered file", "Repair asset reconciliation"],
};

function FeedbackDialog({ title, impact, suggestions, onCancel, onSubmit }: { title: string; impact: string[]; suggestions: string[]; onCancel: () => void; onSubmit: (feedback: string) => void }) {
  const [feedback, setFeedback] = useState("");
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === "Escape") onCancel(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onCancel]);
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) onCancel(); }}>
      <div className="feedback-dialog" role="dialog" aria-modal="true" aria-labelledby="feedback-title">
        <header><span className="eyebrow">Guided revision</span><h2 id="feedback-title">{title}</h2><p>Choose a common issue to get started, then add the specific detail the agent needs.</p></header>
        <div className="revision-suggestions" aria-label="Suggested revision types">{suggestions.map((suggestion) => <button key={suggestion} className={feedback.startsWith(suggestion) ? "selected" : ""} onClick={() => setFeedback(`${suggestion}: `)}>{suggestion}</button>)}</div>
        <label><span>What should be different?</span><textarea autoFocus rows={5} value={feedback} onChange={(event) => setFeedback(event.target.value)} placeholder="For example: target first-time managers instead of experienced team leads." /></label>
        <div className="impact-preview"><span className="micro-label">Likely downstream impact</span>{impact.map((item) => <div key={item}><span aria-hidden="true">→</span>{item}</div>)}</div>
        <footer><button className="button button-quiet" onClick={onCancel}>Cancel</button><button className="button button-primary" disabled={!feedback.trim()} onClick={() => onSubmit(feedback.trim())}>Request scoped revision</button></footer>
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
  const [feedbackOpen, setFeedbackOpen] = useState(false);
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
    mutationFn: async (action: { type: "run" | "approve" | "changes"; feedback?: string }) => {
      if (!workspace) return;
      if (query.data?.demoMode) return { demo: true };
      if (action.type === "run") return runStage(courseId, stage, { expectedChecksum: currentSummary?.checksum, mode: runMode });
      if (action.type === "approve") return approveStage(courseId, stage, { expectedChecksum: currentSummary?.checksum });
      return requestStageChanges(courseId, stage, { expectedChecksum: currentSummary?.checksum, note: action.feedback, mode: runMode });
    },
    onSuccess: async (result, action) => {
      setFeedbackOpen(false);
      if (result && "job" in result) {
        setActiveJobId(result.job.job_id);
        setActiveJobStage(stage);
        setRunProgress({ message: "Run queued" });
      }
      if (result && "demo" in result) {
        setToast({ tone: "good", message: "Preview action recorded. Connect the API to persist this decision." });
        return;
      }
      if (action.type === "approve") {
        const nextStage = nextStageAfter(stage);
        await refresh();
        if (nextStage) {
          setToast({ tone: "good", message: `${stageName(stage)} approved. ${stageName(nextStage)} is ready to run.` });
          navigate(`/courses/${courseId}/${nextStage}?mode=${runMode}`);
        } else {
          setToast({ tone: "good", message: "Package approved. The course workflow is complete." });
        }
        return;
      }
      setToast({
        tone: "good",
        message: action.type === "changes" ? "Revision started. The updated artifact will appear here when it is ready." : `${stageName(stage)} started. The artifact will appear here when it is ready.`,
      });
      void refresh();
    },
    onError: (error) => {
      const stale = error instanceof ApiError && error.status === 409;
      setToast({ tone: "attention", message: stale ? "This artifact changed in another session. Refresh before submitting your decision." : error.message });
    },
  });

  async function contentAction(action: string, asset: ContentAsset, claim?: Claim) {
    if (!workspace) return;
    if (query.data?.demoMode) {
      setToast({ tone: "neutral", message: `“${action.replaceAll("_", " ")}” is wired for ${asset.id}. Connect the API to run it.` });
      return;
    }
    try {
      if (action === "approved" || action === "changes_requested") {
        await reviewContentAsset(courseId, asset.id, action, workspace.content.reviewChecksum, claim?.note);
      } else if (action === "revise") {
        await requestStageChanges(courseId, "content", {
          expectedChecksum: currentSummary?.checksum,
          mode: runMode,
          note: JSON.stringify({
            assets: [asset.id],
            subtopic_id: asset.subtopicId,
            verifier: true,
            feedback: `Revise only this asset${claim ? ` for verifier finding ${claim.id}` : ""}. Use the existing approved evidence and reverify the affected asset.`,
          }),
        });
      } else if (action === "research") {
        const researchStage = workspace.stages.find((item) => item.slug === "research");
        await requestStageChanges(courseId, "research", {
          expectedChecksum: researchStage?.checksum,
          mode: runMode,
          note: `Find better grounding evidence for asset ${asset.id}${claim ? `, claim ${claim.id}: ${claim.text}` : ""}. Keep the research pass bounded to this gap.`,
        });
      }
      setToast({
        tone: "good",
        message: action === "revise"
          ? `Targeted revision accepted for ${asset.title}; unaffected assets will be preserved.`
          : action === "research"
            ? "A bounded research-stage refresh was accepted for this evidence gap. Review the resulting source registry before continuing."
            : `Review decision saved for ${asset.title}.`,
      });
      void refresh();
    } catch (error) {
      setToast({ tone: "attention", message: error instanceof Error ? error.message : "The content action failed." });
    }
  }

  async function sourceDecision(selectedIds: string[]) {
    if (!workspace) return;
    if (query.data?.demoMode) {
      setToast({ tone: "neutral", message: "Source decisions are interactive in preview mode; start the API to persist them." });
      return;
    }
    try {
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
            <div className="locked-stage-state"><span className="locked-glyph" aria-hidden="true">·</span><span className="eyebrow">{currentSummary.label}</span><h1>This stage is waiting on an upstream decision.</h1><p>{context.consumes.join(", ")} must be approved and current before the agent can run this stage.</p><button className="button button-secondary" onClick={() => navigate(`/courses/${courseId}/${workspace.course.currentStage}?mode=${runMode}`)}>Go to current stage</button></div>
          ) : <StageView stage={stage} workspace={workspace} onContentAction={(action, asset, claim) => void contentAction(action, asset, claim)} onSourceDecision={readOnly ? undefined : (selectedIds) => void sourceDecision(selectedIds)} onEditBrief={readOnly ? undefined : setBriefEditSection} />}
        </main>
        {inspectorOpen ? <ContextInspector workspace={workspace} stage={stage} onClose={() => setInspectorOpen(false)} /> : null}
        <DecisionBar
          stage={stage}
          status={currentSummary?.status ?? "ready"}
          disabled={readOnly}
          busy={mutation.isPending || Boolean(activeJobId)}
          onApprove={() => mutation.mutate({ type: "approve" })}
          onRequestChanges={() => setFeedbackOpen(true)}
          onRun={() => mutation.mutate({ type: "run" })}
          nextStage={nextStageAfter(stage)}
          onContinue={() => {
            const nextStage = nextStageAfter(stage);
            if (nextStage) navigate(`/courses/${courseId}/${nextStage}?mode=${runMode}`);
          }}
          approvalBlocked={stage === "research" && !workspace.research.registrySaved}
        />
      </div>
      {activityOpen ? <ActivityDrawer workspace={workspace} onClose={() => setActivityOpen(false)} /> : null}
      {feedbackOpen ? <FeedbackDialog title={`Revise ${currentSummary?.label}`} impact={context.affects} suggestions={revisionSuggestions[stage]} onCancel={() => setFeedbackOpen(false)} onSubmit={(feedback) => mutation.mutate({ type: "changes", feedback })} /> : null}
      {briefEditSection ? <BriefEditDialog section={briefEditSection} brief={workspace.brief} busy={briefMutation.isPending} onCancel={() => setBriefEditSection(null)} onSubmit={(brief) => briefMutation.mutate(brief)} /> : null}
      {toast ? <Toast message={toast.message} tone={toast.tone} onClose={() => setToast(null)} /> : null}
    </div>
  );
}
