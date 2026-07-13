import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  ApiError,
  approveStage,
  getWorkspace,
  requestStageChanges,
  reviewContentAsset,
  runStage,
  saveSourceDecision,
  subscribeToJob,
} from "../../api/client";
import { AppBrand } from "../../components/AppBrand";
import { ErrorState, LoadingState } from "../../components/States";
import { StatusBadge } from "../../components/StatusBadge";
import type { Claim, ContentAsset, StageSlug, UiStatus, Workspace } from "../../types";
import { StageView, stageData } from "./StageViews";

const stageSlugs: StageSlug[] = ["brief", "outcomes", "research", "course-model", "blueprint", "content", "lesson-plan", "package"];

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

function WorkflowRail({ workspace, activeStage }: { workspace: Workspace; activeStage: StageSlug }) {
  return (
    <aside className="workflow-rail">
      <div className="rail-heading"><span>Course workflow</span><small>{workspace.stages.filter((stage) => stage.status === "approved").length} / 8 approved</small></div>
      <nav aria-label="Course stages">
        {workspace.stages.map((stage) => {
          const isActive = activeStage === stage.slug;
          const isLocked = stage.status === "locked";
          return (
            <Link
              key={stage.slug}
              to={`/courses/${workspace.course.courseId}/${stage.slug}`}
              className={`${isActive ? "active" : ""} rail-status-${stage.status}`}
              aria-current={isActive ? "page" : undefined}
              title={isLocked ? "Inspect this locked stage and its requirements" : undefined}
            >
              <span className="rail-number">{stageNumbers[stage.slug]}</span>
              <span className="rail-stage-copy"><strong>{stage.label}</strong><small>{stage.status.replaceAll("_", " ")}</small></span>
              <span className="rail-stage-state" aria-hidden="true">{stage.status === "approved" ? "✓" : stage.status === "requires_attention" ? stage.count || "!" : stage.status === "locked" ? "·" : "→"}</span>
            </Link>
          );
        })}
      </nav>
      <button className="activity-trigger"><span className="activity-bars" aria-hidden="true"><i /><i /><i /></span><span><strong>Activity & runs</strong><small>{workspace.activity.length} recent events</small></span><span aria-hidden="true">›</span></button>
      <div className="rail-footer"><span className="rail-saved-dot" /><span><strong>Artifacts saved</strong><small>Resume-safe workspace</small></span></div>
    </aside>
  );
}

type InspectorTab = "why" | "evidence" | "dependencies" | "history" | "raw";

function ContextInspector({ workspace, stage }: { workspace: Workspace; stage: StageSlug }) {
  const [tab, setTab] = useState<InspectorTab>("why");
  const context = stageContext[stage];
  const stageSummary = workspace.stages.find((item) => item.slug === stage);
  const tabs: Array<[InspectorTab, string]> = [["why", "Why"], ["evidence", "Evidence"], ["dependencies", "Links"], ["history", "History"], ["raw", "Raw"]];
  return (
    <aside className="context-inspector">
      <header><div><span className="eyebrow">Context inspector</span><h2>{stageSummary?.label}</h2></div><StatusBadge status={stageSummary?.status ?? "ready"} count={stageSummary?.count} /></header>
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
}: {
  stage: StageSlug;
  status: UiStatus;
  disabled?: boolean;
  busy?: boolean;
  onApprove: () => void;
  onRequestChanges: () => void;
  onRun: () => void;
}) {
  const isApproved = status === "approved";
  const isLocked = status === "locked";
  const attention = status === "requires_attention";
  return (
    <div className="decision-bar">
      <div className="decision-context"><span className={`decision-dot decision-${status}`} /><div><small>{isApproved ? "Checkpoint recorded" : attention ? "Human decision needed" : isLocked ? "Upstream checkpoint required" : "Stage action"}</small><strong>{isApproved ? "Approved and current" : attention ? "Resolve blockers before approval" : isLocked ? "This stage is not ready to run" : "Review before continuing"}</strong></div></div>
      <div className="decision-actions">
        {isApproved ? <button className="button button-secondary" disabled={disabled || busy} onClick={onRequestChanges}>Reopen stage</button> : <button className="button button-secondary" disabled={disabled || busy || isLocked} onClick={onRequestChanges}>Request changes</button>}
        {attention && stage === "content" ? <button className="button button-primary" onClick={() => document.querySelector(".attention-banner")?.scrollIntoView({ behavior: "smooth" })}>Review attention queue <span aria-hidden="true">→</span></button> : status === "ready" ? <button className="button button-primary" disabled={disabled || busy || isLocked} onClick={onRun}>{busy ? "Starting…" : "Run stage"} <span aria-hidden="true">→</span></button> : <button className="button button-primary" disabled={disabled || busy || isLocked || isApproved} onClick={onApprove}>{busy ? "Saving…" : `Approve ${stage === "course-model" ? "Course Model" : stage.replaceAll("-", " ")}`} <span aria-hidden="true">→</span></button>}
      </div>
    </div>
  );
}

function FeedbackDialog({ title, impact, onCancel, onSubmit }: { title: string; impact: string[]; onCancel: () => void; onSubmit: (feedback: string) => void }) {
  const [feedback, setFeedback] = useState("");
  return (
    <div className="modal-backdrop" role="presentation">
      <div className="feedback-dialog" role="dialog" aria-modal="true" aria-labelledby="feedback-title">
        <header><span className="eyebrow">Scoped revision</span><h2 id="feedback-title">{title}</h2><p>Tell the agent exactly what should change in this artifact. The instruction stays attached to this stage.</p></header>
        <label><span>Revision instruction</span><textarea autoFocus rows={5} value={feedback} onChange={(event) => setFeedback(event.target.value)} placeholder="Describe the specific correction, missing coverage, or constraint…" /></label>
        <div className="impact-preview"><span className="micro-label">Likely downstream impact</span>{impact.map((item) => <div key={item}><span aria-hidden="true">→</span>{item}</div>)}</div>
        <footer><button className="button button-quiet" onClick={onCancel}>Cancel</button><button className="button button-primary" disabled={!feedback.trim()} onClick={() => onSubmit(feedback.trim())}>Request scoped revision</button></footer>
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
  const [runMode, setRunMode] = useState<"deterministic" | "live">(() => new URLSearchParams(location.search).get("mode") === "live" ? "live" : "deterministic");
  const [activityOpen, setActivityOpen] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [toast, setToast] = useState<{ message: string; tone: "good" | "attention" | "neutral" } | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [runProgress, setRunProgress] = useState<{ message: string; completed?: number; expected?: number } | null>(null);
  const query = useQuery({ queryKey: ["workspace", courseId], queryFn: () => getWorkspace(courseId) });
  const workspace = query.data?.workspace;
  const currentSummary = workspace?.stages.find((item) => item.slug === stage);

  useEffect(() => {
    if (!routeStage && workspace) navigate(`/courses/${courseId}/${workspace.course.currentStage}`, { replace: true });
  }, [courseId, navigate, routeStage, workspace]);

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
        setActiveJobId(null);
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
    onSuccess: (result) => {
      setFeedbackOpen(false);
      if (result && "job" in result) {
        setActiveJobId(result.job.job_id);
        setRunProgress({ message: "Run queued" });
      }
      setToast({
        tone: "good",
        message: result && "demo" in result ? "Preview action recorded. Connect the API to persist this decision." : "Action accepted. The workspace will refresh as artifacts change.",
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
  return (
    <div className="workspace-shell">
      <header className="workspace-header">
        <AppBrand compact />
        <div className="workspace-course-title"><Link to="/courses">Courses</Link><span aria-hidden="true">/</span><div><strong>{workspace.course.title}</strong><small>{courseId}</small></div></div>
        <div className="workspace-header-actions">
          {demoMode ? <span className="environment-badge"><i /> Preview data</span> : readOnly ? <span className="environment-badge snapshot"><i /> Archived snapshot</span> : <span className="environment-badge connected"><i /> API connected</span>}
          <label className="run-mode-selector" title="Choose how stage runs execute"><span>Run mode</span><select value={runMode} onChange={(event) => setRunMode(event.target.value as "deterministic" | "live")}><option value="deterministic">Deterministic</option><option value="live">Live agent</option></select></label>
          {runProgress ? <span className="environment-badge connected run-progress"><i /> {runProgress.completed != null && runProgress.expected ? `${runProgress.completed}/${runProgress.expected} · ` : ""}{runProgress.message}</span> : null}
          {workspace.estimatedCost ? <span className="cost-note">${workspace.estimatedCost.toFixed(2)} est.</span> : null}
          <button className="header-icon-button" onClick={() => setActivityOpen(true)} aria-label="Open activity"><span className="activity-bars" aria-hidden="true"><i /><i /><i /></span></button>
        </div>
      </header>
      <div className="workspace-grid">
        <WorkflowRail workspace={workspace} activeStage={stage} />
        <main className="stage-canvas" id="main-content">
          {currentSummary?.status === "locked" && !demoMode ? (
            <div className="locked-stage-state"><span className="locked-glyph" aria-hidden="true">·</span><span className="eyebrow">{currentSummary.label}</span><h1>This stage is waiting on an upstream decision.</h1><p>{context.consumes.join(", ")} must be approved and current before the agent can run this stage.</p><button className="button button-secondary" onClick={() => navigate(`/courses/${courseId}/${workspace.course.currentStage}`)}>Go to current stage</button></div>
          ) : <StageView stage={stage} workspace={workspace} onContentAction={(action, asset, claim) => void contentAction(action, asset, claim)} onSourceDecision={readOnly ? undefined : (selectedIds) => void sourceDecision(selectedIds)} />}
        </main>
        <ContextInspector workspace={workspace} stage={stage} />
        <DecisionBar
          stage={stage}
          status={currentSummary?.status ?? "ready"}
          disabled={readOnly}
          busy={mutation.isPending || Boolean(activeJobId)}
          onApprove={() => mutation.mutate({ type: "approve" })}
          onRequestChanges={() => setFeedbackOpen(true)}
          onRun={() => mutation.mutate({ type: "run" })}
        />
      </div>
      <button className="activity-hotspot" aria-hidden="true" tabIndex={-1} onClick={() => setActivityOpen(true)} />
      {activityOpen ? <ActivityDrawer workspace={workspace} onClose={() => setActivityOpen(false)} /> : null}
      {feedbackOpen ? <FeedbackDialog title={`${currentSummary?.status === "approved" ? "Reopen" : "Revise"} ${currentSummary?.label}`} impact={context.affects} onCancel={() => setFeedbackOpen(false)} onSubmit={(feedback) => mutation.mutate({ type: "changes", feedback })} /> : null}
      {toast ? <Toast message={toast.message} tone={toast.tone} onClose={() => setToast(null)} /> : null}
    </div>
  );
}
