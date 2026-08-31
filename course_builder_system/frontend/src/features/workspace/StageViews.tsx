import { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import { getOutputMarkdown } from "../../api/client";
import { SourceStatus, VerificationBadge } from "../../components/StatusBadge";
import type {
  BriefQuestionAnswer,
  BriefQuestionRound as BriefQuestionRoundData,
  BlueprintDecisionDraft,
  Claim,
  ContentAsset,
  CourseModelOperation,
  CourseModelPreview,
  CourseModelValidationIssue,
  LessonPlanDecisionDraft,
  OutcomeDecisionDraft,
  OutcomeValidationIssue,
  OutputFile,
  ReleaseCheck,
  SourceRepairEntry,
  StageSlug,
  Subtopic,
  Workspace,
} from "../../types";
import { BriefQuestionRound } from "./BriefQuestionRound";
import { OutcomesEditor } from "./OutcomesEditor";
import { CourseModelEditor } from "./CourseModelEditor";
import { BlueprintEditor } from "./BlueprintEditor";
import { LessonPlanEditor } from "./LessonPlanEditor";

function stageIntro(title: string, kicker: string, description: string, aside?: React.ReactNode) {
  return (
    <div className="stage-intro">
      <div>
        <span className="eyebrow">{kicker}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {aside ? <div className="stage-intro-aside">{aside}</div> : null}
    </div>
  );
}

function DefinitionItem({ label, value }: { label: string; value: React.ReactNode }) {
  return <div className="definition-item"><dt>{label}</dt><dd>{value}</dd></div>;
}

function TagList({ values, tone = "neutral" }: { values: string[]; tone?: "neutral" | "out" | "source" }) {
  if (!values.length) return <span className="muted">None recorded</span>;
  return <div className="tag-list">{values.map((value) => <span key={value} className={`tag tag-${tone}`}>{value}</span>)}</div>;
}

type ScopedRevisionRecord = { targetType: string; id: string; label: string };

function LiveRevisionControls({ records, onRequest }: { records: ScopedRevisionRecord[]; onRequest?: (targetType: string, id: string, label: string) => void }) {
  if (!onRequest || !records.length) return null;
  return (
    <section className="live-revision-controls" aria-label="Live scoped revision targets">
      <div><span className="eyebrow">Live scoped revision</span><h2>Ask the agent to revise one named record</h2><p>The backend accepts structured output only and rejects changes outside the selected ID.</p></div>
      <div>{records.map((record) => <button className="button button-secondary" key={`${record.targetType}:${record.id}`} onClick={() => onRequest(record.targetType, record.id, record.label)}><span>{record.label}</span><code>{record.id}</code></button>)}</div>
    </section>
  );
}

function displayCode(value: string): string {
  const normalized = value.replaceAll("_", " ");
  return normalized ? normalized[0].toUpperCase() + normalized.slice(1) : "Not set";
}

/** "3", "4", "5" -> "3, 4 and 5" */
function formatList(values: string[]): string {
  if (values.length <= 1) return values[0] ?? "";
  return `${values.slice(0, -1).join(", ")} and ${values[values.length - 1]}`;
}

function displayAssumptionValue(value: string): string {
  if (value.startsWith("[") && value.endsWith("]")) {
    return value.slice(1, -1).replaceAll("'", "").replaceAll('"', "");
  }
  return value;
}

export type BriefEditSection = "settings" | "learner" | "scope" | "coverage" | "requirements" | "assumptions";

function BriefSectionAction({ section, label, onEdit }: { section: BriefEditSection; label: string; onEdit?: (section: BriefEditSection) => void }) {
  if (!onEdit) return null;
  return <button className="section-edit-button" onClick={() => onEdit(section)} aria-label={`${label} in Course Brief`}><span>Adjust</span><span aria-hidden="true">→</span></button>;
}

function BriefView({
  workspace,
  onEdit,
  questionRound,
  questionsLoading = false,
  questionsBusy = false,
  questionsError,
  onRetryQuestions,
  onSubmitQuestions,
}: {
  workspace: Workspace;
  onEdit?: (section: BriefEditSection) => void;
  questionRound?: BriefQuestionRoundData;
  questionsLoading?: boolean;
  questionsBusy?: boolean;
  questionsError?: string;
  onRetryQuestions?: () => void;
  onSubmitQuestions?: (answers: BriefQuestionAnswer[]) => void;
}) {
  const brief = workspace.brief;
  const summary = workspace.stages.find((stage) => stage.slug === "brief");
  const hasArtifact = Boolean(workspace.briefChecksum);
  const explicitFields = new Set(brief.intakeState.explicitFields);
  const acceptedDefaults = new Set(brief.intakeState.acceptedDefaultFields);
  const artifactStatus = summary?.status === "approved"
    ? "Approved"
    : summary?.status === "needs_input"
      ? "Input required"
      : summary?.status === "requires_attention"
        ? "Needs attention"
        : summary?.status === "stale"
          ? "Stale"
          : summary?.status === "failed"
            ? "Failed"
            : hasArtifact
              ? "Ready for review"
              : "Not saved yet";
  const additionalRequirements = [
    ["Jurisdiction", brief.jurisdiction],
    ["Accessibility", brief.accessibilityRequirements],
    ["Live teaching", brief.liveTeachingConstraints],
    ["Tools or equipment", brief.toolsOrEquipment],
    ["Freshness", brief.freshnessRequirement],
  ].filter((item): item is [string, string] => Boolean(item[1]));
  return (
    <div className="stage-view">
      {stageIntro(
        "Course Brief",
        "01 · Direction",
        summary?.status === "needs_input"
          ? "The draft is saved. Complete the relevant questions before reviewing and approving the working agreement."
          : hasArtifact
          ? "The starting request is now a practical working agreement. Review the details before downstream work begins."
          : "Start with these sensible defaults, then adjust only the details that matter for this course.",
        <div className={`artifact-stamp ${hasArtifact ? "" : "suggested"}`}><span>{hasArtifact ? "Working artifact" : "Suggested starting point"}</span><strong>{artifactStatus}</strong></div>,
      )}
      {questionsLoading && summary?.status === "needs_input" ? (
        <section className="brief-intake-panel brief-intake-loading" aria-live="polite"><span className="loading-orbit" aria-hidden="true" /><div><h2>Loading the next question round…</h2><p>The saved Brief remains the source of truth.</p></div></section>
      ) : null}
      {!questionsLoading && questionsError && summary?.status === "needs_input" && !questionRound ? (
        <section className="brief-intake-panel brief-intake-unavailable" role="alert"><div><span className="eyebrow">Guided Brief intake</span><h2>The question round could not be loaded.</h2><p>{questionsError}</p></div>{onRetryQuestions ? <button className="button button-secondary" onClick={onRetryQuestions}>Try again</button> : null}</section>
      ) : null}
      {summary?.status === "needs_input" && questionRound?.questions.length && onSubmitQuestions ? (
        <BriefQuestionRound
          key={`${questionRound.checksum}:${questionRound.roundKind}`}
          round={questionRound}
          busy={questionsBusy}
          serverError={questionsError}
          onSubmit={onSubmitQuestions}
        />
      ) : null}
      <div className="brief-hero-card">
        <div className="brief-hero-heading">
          <div><span className="card-kicker">Course intent</span><h2>{brief.courseTitle}</h2><p>{brief.purpose}</p></div>
          <BriefSectionAction section="settings" label="Adjust course settings" onEdit={onEdit} />
        </div>
        <dl className="brief-quickfacts">
          <DefinitionItem label="Level" value={displayCode(brief.level)} />
          <DefinitionItem label="Duration" value={brief.duration} />
          <DefinitionItem label="Delivery" value={displayCode(brief.modality)} />
          <DefinitionItem label="Language" value={brief.language} />
        </dl>
      </div>
      <div className="stage-card-grid two-column">
        <section className="stage-card">
          <div className="card-heading"><div><span className="card-index">A</span><h3>Learner and intent</h3></div><BriefSectionAction section="learner" label="Adjust learner and intent" onEdit={onEdit} /></div>
          <dl className="stacked-definitions">
            <DefinitionItem label="Audience" value={brief.audience} />
            <DefinitionItem label="Prior knowledge" value={brief.priorKnowledge} />
            <DefinitionItem label="Assessment expectation" value={brief.assessmentExpectations || "Not specified"} />
          </dl>
        </section>
        <section className="stage-card">
          <div className="card-heading"><div><span className="card-index">B</span><h3>Scope boundary</h3></div><BriefSectionAction section="scope" label="Adjust scope boundary" onEdit={onEdit} /></div>
          <div className="scope-columns">
            <div><span className="micro-label">In scope</span><TagList values={brief.inScope} /></div>
            <div><span className="micro-label">Out of scope</span><TagList values={brief.outOfScope} tone="out" /></div>
          </div>
        </section>
        <section className="stage-card">
          <div className="card-heading"><div><span className="card-index">C</span><h3>Must-have coverage</h3></div><BriefSectionAction section="coverage" label="Adjust must-have coverage" onEdit={onEdit} /></div>
          <TagList values={brief.mustHaveTopics} />
          <div className="card-divider" />
          <span className="micro-label">Constraints</span>
          <ul className="clean-list">{brief.constraints.map((item) => <li key={item}>{item}</li>)}</ul>
        </section>
        <section className="stage-card">
          <div className="card-heading"><div><span className="card-index">D</span><h3>Additional requirements and materials</h3></div><BriefSectionAction section="requirements" label="Adjust additional requirements and materials" onEdit={onEdit} /></div>
          {additionalRequirements.length ? <dl className="stacked-definitions">{additionalRequirements.map(([label, value]) => <DefinitionItem key={label} label={label} value={value} />)}</dl> : <span className="muted">No additional requirements recorded</span>}
          <div className="card-divider" />
          <span className="micro-label">Available materials</span>
          <TagList values={brief.availableMaterials} tone="source" />
        </section>
        <section className="stage-card assumption-card">
          <div className="card-heading"><div><span className="card-index">E</span><h3>Visible assumptions</h3></div><BriefSectionAction section="assumptions" label="Review visible assumptions" onEdit={onEdit} /></div>
          <p className="card-note">Defaults are proposals, not hidden facts. Use Adjust to correct any of them.</p>
          <div className="intake-provenance-summary" aria-label="Brief answer provenance"><span><strong>{explicitFields.size}</strong> provided directly</span><span><strong>{acceptedDefaults.size}</strong> defaults accepted</span></div>
          <div className="assumption-list">
            {brief.assumptions.length ? brief.assumptions.map((assumption) => (
              <div key={assumption.field} className="assumption-row">
                <div><strong>{assumption.field.replaceAll("_", " ")}</strong><span>{displayAssumptionValue(assumption.value)}</span></div>
                <small className={acceptedDefaults.has(assumption.field) ? "accepted" : ""}>{acceptedDefaults.has(assumption.field) ? "Accepted default" : explicitFields.has(assumption.field) ? "Provided by you" : "Suggested default"}</small>
              </div>
            )) : <div className="no-assumptions"><span aria-hidden="true">✓</span><p>All current Brief values have been explicitly confirmed.</p></div>}
          </div>
        </section>
      </div>
    </div>
  );
}

function OutcomesView({
  workspace,
  editing = false,
  busy = false,
  conflict = false,
  serverError,
  serverIssues = [],
  onStartEdit,
  onCancel,
  onSave,
  onResolveConflict,
  onDirtyChange,
  onRequestRevision,
}: {
  workspace: Workspace;
  editing?: boolean;
  busy?: boolean;
  conflict?: boolean;
  serverError?: string;
  serverIssues?: OutcomeValidationIssue[];
  onStartEdit?: () => void;
  onCancel?: () => void;
  onSave?: (decision: OutcomeDecisionDraft) => void;
  onResolveConflict?: (choice: "latest" | "keep") => void;
  onDirtyChange?: (dirty: boolean) => void;
  onRequestRevision?: (targetType: string, id: string, label: string) => void;
}) {
  return (
    <div className="stage-view">
      {stageIntro(
        "Course Outcomes",
        "02 · Learning contract",
        "These outcomes control downstream coverage and assessment. Each one states the observable evidence the learner should produce.",
        <div className="outcome-summary"><strong>{workspace.outcomes.length}</strong><span>measurable outcomes</span></div>,
      )}
      <OutcomesEditor
        outcomes={workspace.outcomes}
        advisories={workspace.outcomeAdvisories ?? []}
        canEdit={Boolean(onStartEdit)}
        editing={editing}
        busy={busy}
        conflict={conflict}
        serverError={serverError}
        serverIssues={serverIssues}
        onStartEdit={onStartEdit ?? (() => undefined)}
        onCancel={onCancel ?? (() => undefined)}
        onSave={onSave ?? (() => undefined)}
        onResolveConflict={onResolveConflict ?? (() => undefined)}
        onDirtyChange={onDirtyChange}
      />
      {!editing ? <LiveRevisionControls records={workspace.outcomes.map((outcome) => ({ targetType: "outcome", id: outcome.id, label: outcome.statement }))} onRequest={onRequestRevision} /> : null}
    </div>
  );
}

function ResearchView({
  workspace,
  onSourceDecision,
  onAddKnownSource,
  sourceMutationBusy = false,
}: {
  workspace: Workspace;
  onSourceDecision?: (selectedIds: string[]) => void;
  onAddKnownSource?: (source: { locator: string; title?: string; publisher?: string; trustNotes?: string; relevance?: string }) => void;
  sourceMutationBusy?: boolean;
}) {
  const [tab, setTab] = useState<"sources" | "landscape">("sources");
  const [sourceFilter, setSourceFilter] = useState("");
  const [addingSource, setAddingSource] = useState(false);
  const [knownSource, setKnownSource] = useState({ locator: "", title: "", publisher: "", trustNotes: "", relevance: "" });
  const persistedSelectedIds = useMemo(
    () => workspace.research.sources.filter((source) => ["approved", "selected"].includes(source.status)).map((source) => source.id),
    [workspace.research.sources],
  );
  const [selectedIds, setSelectedIds] = useState<string[]>(persistedSelectedIds);
  useEffect(() => setSelectedIds(persistedSelectedIds), [persistedSelectedIds]);
  const approved = workspace.research.sources.filter((source) => source.status === "approved").length;
  const candidateCount = workspace.research.sources.filter((source) => source.status === "proposed").length;
  const hasSelectionChanges = selectedIds.length !== persistedSelectedIds.length
    || selectedIds.some((id) => !persistedSelectedIds.includes(id));
  const toggle = (sourceId: string, selected: boolean) => {
    setSelectedIds((current) => selected
      ? [...new Set([...current, sourceId])]
      : current.filter((id) => id !== sourceId));
  };
  const visibleSources = workspace.research.sources.filter((source) =>
    `${source.title} ${source.publisher} ${source.relevance}`.toLowerCase().includes(sourceFilter.toLowerCase()),
  );
  return (
    <div className="stage-view research-stage">
      {stageIntro(
        "Research & Sources",
        "03 · Evidence gate",
        "Competitor pages shape the curriculum. Only separately approved grounding sources may support learner-facing claims.",
        // One honest pair of numbers. This header used to read "3 approved /
        // 0 candidates" beside a tab labelled "Grounding sources 10" and a
        // tray reading "3 selected / 7 excluded" — three counts of the same
        // set that appeared to disagree.
        <div className="research-counts"><span><strong>{selectedIds.length}</strong><small>{approved ? "approved" : "selected"}</small></span><span><strong>{workspace.research.sources.length}</strong><small>found</small></span></div>,
      )}
      <div className="tab-row" role="tablist" aria-label="Research views">
        <button role="tab" aria-selected={tab === "sources"} className={tab === "sources" ? "active" : ""} onClick={() => setTab("sources")}>Grounding sources <span>{workspace.research.sources.length}</span></button>
        <button role="tab" aria-selected={tab === "landscape"} className={tab === "landscape" ? "active" : ""} onClick={() => setTab("landscape")}>Competitor landscape <span>{workspace.research.competitors.length}</span></button>
      </div>
      {tab === "sources" ? (
        <div className="research-layout">
          <div className="source-list-panel">
            <div className="list-tools"><div className="search-field"><span aria-hidden="true">⌕</span><input aria-label="Filter sources" value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)} placeholder="Filter candidates" /></div><button className="button button-secondary" disabled={!onAddKnownSource || sourceMutationBusy} title={!onAddKnownSource ? "Known-source additions are unavailable in this stage state" : undefined} onClick={() => setAddingSource((value) => !value)}>+ Add source</button></div>
            {addingSource ? <form className="known-source-form" onSubmit={(event) => { event.preventDefault(); if (!knownSource.locator.trim()) return; onAddKnownSource?.({ locator: knownSource.locator.trim(), title: knownSource.title.trim() || undefined, publisher: knownSource.publisher.trim() || undefined, trustNotes: knownSource.trustNotes.trim() || undefined, relevance: knownSource.relevance.trim() || undefined }); setKnownSource({ locator: "", title: "", publisher: "", trustNotes: "", relevance: "" }); setAddingSource(false); }}><div><span className="eyebrow">Human-provided candidate</span><h3>Add a known source URL</h3><p>The URL is added as proposed. It cannot enter generation context until the normal source decision is saved.</p></div><label><span>Source URL</span><input required type="url" value={knownSource.locator} onChange={(event) => setKnownSource((current) => ({ ...current, locator: event.target.value }))} placeholder="https://example.org/focused-guidance" /></label><div className="known-source-grid"><label><span>Title <small>optional</small></span><input value={knownSource.title} onChange={(event) => setKnownSource((current) => ({ ...current, title: event.target.value }))} /></label><label><span>Publisher <small>optional</small></span><input value={knownSource.publisher} onChange={(event) => setKnownSource((current) => ({ ...current, publisher: event.target.value }))} /></label></div><label><span>Why it may help <small>optional</small></span><textarea rows={2} value={knownSource.relevance} onChange={(event) => setKnownSource((current) => ({ ...current, relevance: event.target.value }))} /></label><label><span>Trust note <small>optional</small></span><textarea rows={2} value={knownSource.trustNotes} onChange={(event) => setKnownSource((current) => ({ ...current, trustNotes: event.target.value }))} /></label><footer><button type="button" className="button button-quiet" onClick={() => setAddingSource(false)}>Cancel</button><button className="button button-primary" disabled={sourceMutationBusy || !knownSource.locator.trim()}>{sourceMutationBusy ? "Adding…" : "Add proposed source"}</button></footer></form> : null}
            <div className="source-list">
            {visibleSources.map((source) => {
              const isSelected = selectedIds.includes(source.id);
              const effectiveStatus = isSelected
                ? source.status === "approved" ? "approved" : "selected"
                : ["approved", "selected"].includes(source.status) ? "proposed" : source.status;
              return (
              <article className={`source-card source-card-${effectiveStatus}`} key={source.id}>
                {/* The internal source id stays available on hover for support
                    questions but is no longer presented as the card's label —
                    `live_07bed5a664d90615` means nothing to a course director. */}
                <div className="source-card-header" title={`Source reference: ${source.id}`}>
                  <div><SourceStatus status={effectiveStatus} /><span className="source-type">{source.sourceType}</span></div>
                </div>
                <h3>{source.title}</h3>
                <p className="source-publisher">{source.publisher} · <span>{source.locator.replace(/^https?:\/\//, "")}</span></p>
                <div className="source-notes">
                  <div><span>Why it matters</span><p>{source.relevance}</p></div>
                  <div><span>Trust note</span><p>{source.trustNotes}</p></div>
                </div>
                {source.quality ? <div className="source-quality"><div className="source-quality-head"><span><strong>{source.quality.overall.toFixed(1)}</strong><small>/ 5 advisory</small></span><div><span className={`quality-recommendation quality-${source.quality.recommendation}`}>{displayCode(source.quality.recommendation)}</span><small>Recommendation is separate from your decision.</small></div></div>
                {/* The six per-dimension scores are diagnostics, not a decision
                    surface. Rendered open on every candidate they made this
                    page ~6,800px tall and buried the actual Select control. */}
                <details className="source-score-detail"><summary>Why this score?</summary><dl>{Object.entries(source.quality.dimensions).map(([name, dimension]) => <div key={name}><dt>{displayCode(name)}</dt><dd><strong>{dimension.score}/5</strong><span>{dimension.reason}</span></dd></div>)}</dl></details>{source.quality.previewSections.length ? <details><summary>Bounded source preview · {source.quality.previewSections.length} relevant section{source.quality.previewSections.length === 1 ? "" : "s"}</summary><div>{source.quality.previewSections.map((section) => <blockquote key={`${section.order}:${section.text}`}>{section.text}</blockquote>)}</div></details> : <p className="source-preview-empty">No extractable content is available yet. Review the metadata before deciding whether to capture this source.</p>}</div> : null}
                <div className="source-footer">
                  <div>{source.assignedNodeIds.length ? <><span className="micro-label">Assigned to</span><TagList values={source.assignedNodeIds} tone="source" /></> : <span className="muted">{isSelected ? "Available for Course Model routing" : "Outside generation context"}</span>}</div>
                  <div className="source-actions"><a target="_blank" rel="noreferrer" href={source.locator}>Preview</a>{isSelected ? <button className="remove-source" disabled={!onSourceDecision} title={!onSourceDecision ? "Source decisions are not available in the current stage state" : undefined} onClick={() => toggle(source.id, false)}>Remove</button> : <button className="select-source" disabled={!onSourceDecision} title={!onSourceDecision ? "Source decisions are not available in the current stage state" : undefined} onClick={() => toggle(source.id, true)}>Select</button>}</div>
                </div>
              </article>
            );})}
            </div>
          </div>
          <aside className="decision-tray">
            <span className="eyebrow">Human checkpoint</span>
            <h3>Choose grounding sources</h3>
            <p className="tray-intro">Only the sources you select and save can support learner-facing claims.</p>
            <div className="tray-stats"><div className="tray-stat"><strong>{selectedIds.length}</strong><span>Selected</span></div><div className="tray-stat"><strong>{Math.max(0, workspace.research.sources.length - selectedIds.length)}</strong><span>Excluded</span></div></div>
            <ol className="source-decision-flow"><li className="done"><span>1</span><div><strong>Candidates found</strong><small>The agent completed bounded research</small></div></li><li className={workspace.research.registrySaved ? "done" : "current"}><span>2</span><div><strong>Select and save</strong><small>Your explicit source decision</small></div></li><li className={workspace.research.registryApproved ? "done" : ""}><span>3</span><div><strong>Approve Research</strong><small>Unlocks the Course Model</small></div></li></ol>
            <div className="tray-check"><span aria-hidden="true">✓</span><p>Unselected and unavailable sources stay outside generation context.</p></div>
            <button className="button button-primary full-width" disabled={!onSourceDecision || !selectedIds.length || (workspace.research.registrySaved && !hasSelectionChanges)} onClick={() => onSourceDecision?.(selectedIds)}>{workspace.research.registrySaved && !hasSelectionChanges ? workspace.research.registryApproved ? "Selection approved" : "Selection saved" : `Save ${selectedIds.length} selected source${selectedIds.length === 1 ? "" : "s"}`}</button>
            {!workspace.research.registrySaved ? <small className="tray-help">Save a selection before approving this stage.</small> : <small className="tray-help ready">{workspace.research.registryApproved ? "Research checkpoint approved." : "Ready for stage approval."}</small>}
          </aside>
        </div>
      ) : (
        <div className="landscape-layout">
          <div className="curriculum-evidence-note"><span aria-hidden="true">i</span><p><strong>Curriculum evidence only.</strong> These outlines inform structure but cannot ground learner-facing factual claims unless separately approved.</p></div>
          <div className="competitor-grid">
            {workspace.research.competitors.map((competitor) => (
              <article className="competitor-card" key={competitor.id}>
                <div className="competitor-head"><span className={`outline-state outline-${competitor.outlineStatus}`}>{outlineStatusLabel(competitor.outlineStatus)}</span><code>{competitor.id}</code></div>
                <span className="card-kicker">{competitor.provider}</span><h3>{competitor.offering}</h3>
                <ol>{competitor.outlineSections.map((section) => <li key={section}><span>{section}</span></li>)}</ol>
                <p>{competitor.structureSummary}</p>
              </article>
            ))}
          </div>
          <section className="observation-panel"><span className="eyebrow">Agent synthesis</span><h3>Structural observations</h3><div>{workspace.research.observations.map((observation, index) => <article key={observation}><span>{String(index + 1).padStart(2, "0")}</span><p>{observation}</p></article>)}</div></section>
        </div>
      )}
    </div>
  );
}

const OUTLINE_STATUS_LABELS: Record<string, string> = {
  usable: "usable",
  partial: "partial",
  // The page was retrieved; our parser just could not find an outline in it.
  no_outline_found: "no outline parsed",
  inaccessible: "not retrievable",
  behind_login: "behind login",
  stale: "stale",
};

function outlineStatusLabel(status: string): string {
  return OUTLINE_STATUS_LABELS[status] ?? status.replace(/_/g, " ");
}

function ModelDetail({ subtopic }: { subtopic: Subtopic }) {
  return (
    <div className="model-detail">
      <header className="model-detail-head">
        <div className="model-detail-title"><code>{subtopic.id}</code><h2>{subtopic.title}</h2><p>{subtopic.purpose}</p></div>
        <button className="button button-secondary" disabled title="Structured Course Model editing is not implemented in this release">Edit subtopic</button>
      </header>
      <dl className="model-metadata">
        <div><dt>Sequence</dt><dd>{String(subtopic.order).padStart(2, "0")}</dd></div>
        <div><dt>Prerequisite</dt><dd>{subtopic.prerequisiteSubtopicIds.join(", ") || "None"}</dd></div>
        <div><dt>Approved sources</dt><dd>{subtopic.approvedSourceIds.length}</dd></div>
      </dl>
      <section className="detail-section scope-contract-section">
        <div className="detail-section-heading"><div><span className="eyebrow">Generation boundary</span><h3>Scope contract</h3></div><span className="section-state">Controls generation</span></div>
        <div className="model-scope-grid"><div className="scope-block scope-in"><span className="micro-label">In scope</span><TagList values={subtopic.inScope} /></div><div className="scope-block scope-out"><span className="micro-label">Out of scope</span><TagList values={subtopic.outOfScope} tone="out" /></div></div>
      </section>
      <section className="detail-section">
        <div className="detail-section-heading"><div><span className="eyebrow">Knowledge structure</span><h3>Concepts</h3></div><span className="section-count">{subtopic.concepts.length}</span></div>
        <div className="model-record-list">{subtopic.concepts.map((concept) => <article className="concept-row" key={concept.id}><div className="record-copy"><code>{concept.id}</code><strong>{concept.name}</strong><p>{concept.summary}</p></div><div className="record-sources"><span>Grounded by</span><TagList values={concept.sourceIds} tone="source" /></div></article>)}</div>
      </section>
      <section className="detail-section">
        <div className="detail-section-heading"><div><span className="eyebrow">Coverage contract</span><h3>Requirements</h3></div><span className="section-count">{subtopic.coverageRequirements.length}</span></div>
        <div className="model-record-list">{subtopic.coverageRequirements.map((requirement) => <article className="requirement-row" key={requirement.id}><span className="requirement-check" aria-hidden="true">✓</span><div className="record-copy"><code>{requirement.id}</code><p>{requirement.statement}</p><div className="record-sources"><span>Supported by</span><TagList values={requirement.sourceIds} tone="source" /></div></div></article>)}</div>
      </section>
      <div className="model-integrity-note"><span aria-hidden="true">✓</span><div><strong>References are valid</strong><p>Concept, coverage, prerequisite, outcome, and source IDs resolve against current artifacts.</p></div></div>
    </div>
  );
}

function CourseModelView({ workspace, ...props }: { workspace: Workspace; editing?: boolean; busy?: boolean; conflict?: boolean; serverError?: string; serverIssues?: CourseModelValidationIssue[]; preview?: CourseModelPreview | null; onStartEdit?: () => void; onCancel?: () => void; onPreview?: (operations: CourseModelOperation[]) => void; onSave?: (operations: CourseModelOperation[], impactChecksum: string) => void; onInvalidatePreview?: () => void; onRecoverConflict?: (choice: "reapply" | "discard") => void; onDirtyChange?: (dirty: boolean) => void; onRequestRevision?: (targetType: string, id: string, label: string) => void }) {
  return <><CourseModelEditor model={workspace.courseModel} outcomes={workspace.outcomes} canEdit={Boolean(props.onStartEdit)} editing={Boolean(props.editing)} busy={Boolean(props.busy)} conflict={Boolean(props.conflict)} serverError={props.serverError} serverIssues={props.serverIssues} preview={props.preview} onStartEdit={props.onStartEdit ?? (() => undefined)} onCancel={props.onCancel ?? (() => undefined)} onPreview={props.onPreview ?? (() => undefined)} onSave={props.onSave ?? (() => undefined)} onInvalidatePreview={props.onInvalidatePreview ?? (() => undefined)} onRecoverConflict={props.onRecoverConflict ?? (() => undefined)} onDirtyChange={props.onDirtyChange} />{!props.editing ? <LiveRevisionControls records={workspace.modules.flatMap((module) => module.subtopics.map((subtopic) => ({ targetType: "subtopic", id: subtopic.id, label: subtopic.title })))} onRequest={props.onRequestRevision} /> : null}</>;
}

const assetColumns = [
  ["course_content", "Content"], ["learning_objectives", "Objectives"], ["summary", "Summary"],
  ["case_study", "Case"], ["assessment", "Assessment"], ["activities", "Activity"], ["resources", "Resources"],
] as const;

function blueprintOverrides(plan: Workspace["blueprint"]["plans"][number], defaults: Workspace["blueprint"]["defaults"]): string[] {
  const overrides: string[] = [];
  const differs = (value: string | number, baseline: string | number) => String(value).toLowerCase() !== String(baseline).toLowerCase();
  if (differs(plan.depth, defaults.depth)) overrides.push(`Depth: ${displayCode(plan.depth)}`);
  if (differs(plan.minutes, defaults.minutes)) overrides.push(`${plan.minutes} min`);
  if (differs(plan.wordTarget, defaults.wordTarget)) overrides.push(`${plan.wordTarget.toLocaleString()} words`);
  if (differs(plan.examples, defaults.examples)) overrides.push(`${plan.examples} example${plan.examples === 1 ? "" : "s"}`);
  if (differs(plan.caseDepth, defaults.caseDepth)) overrides.push(`Case: ${displayCode(plan.caseDepth)}`);
  if (differs(plan.assessmentComplexity, defaults.assessmentComplexity)) overrides.push(`Assessment: ${displayCode(plan.assessmentComplexity)}`);
  return overrides;
}

function BlueprintView({
  workspace,
  editing = false,
  busy = false,
  conflict = false,
  serverError,
  onStartEdit,
  onCancel,
  onSave,
  onRecoverConflict,
  onDirtyChange,
  onRequestRevision,
}: {
  workspace: Workspace;
  editing?: boolean;
  busy?: boolean;
  conflict?: boolean;
  serverError?: string;
  onStartEdit?: () => void;
  onCancel?: () => void;
  onSave?: (decision: BlueprintDecisionDraft) => void;
  onRecoverConflict?: (choice: "reapply" | "discard") => void;
  onDirtyChange?: (dirty: boolean) => void;
  onRequestRevision?: (targetType: string, id: string, label: string) => void;
}) {
  const [exceptionsOnly, setExceptionsOnly] = useState(false);
  const plans = exceptionsOnly ? workspace.blueprint.plans.filter((plan) => plan.exception) : workspace.blueprint.plans;
  const names = new Map(workspace.modules.flatMap((module) => module.subtopics.map((subtopic) => [subtopic.id, subtopic.title])));
  const nameRecord = Object.fromEntries(names);
  const selectedAssets = workspace.blueprint.plans.flatMap((plan) => plan.assets).filter((asset) => asset.selectionStatus === "selected").length;
  const exceptionCount = workspace.blueprint.plans.filter((plan) => plan.exception).length;
  if (editing) return <BlueprintEditor blueprint={workspace.blueprint} contentAssets={workspace.content.assets} subtopicNames={nameRecord} canEdit={Boolean(onStartEdit)} editing busy={busy} conflict={conflict} serverError={serverError} onStartEdit={onStartEdit ?? (() => undefined)} onCancel={onCancel ?? (() => undefined)} onSave={onSave ?? (() => undefined)} onResolveConflict={onRecoverConflict ?? (() => undefined)} onDirtyChange={onDirtyChange} />;
  return (
    <div className="stage-view blueprint-view">
      {stageIntro("Blueprint", "05 · Generation control", "Review the exact learner assets the agent will generate for each subtopic, along with its depth and effort budget.", <><div className="blueprint-total"><span className="blueprint-total-icon" aria-hidden="true">✓</span><div><strong>{selectedAssets}</strong><span>assets included across {workspace.blueprint.plans.length} subtopics</span></div></div>{onStartEdit ? <button className="button button-secondary" disabled={busy} onClick={onStartEdit}>Edit Blueprint</button> : null}</>)}
      <section className="defaults-panel">
        <div className="defaults-heading"><div><span className="eyebrow">Course-wide baseline</span><h3>Starting budget for every subtopic</h3><p>Rows marked with an override show exactly what changes from this baseline.</p></div><span className="defaults-review-note"><span aria-hidden="true">◇</span> Review before approval</span></div>
        <dl><DefinitionItem label="Depth" value={workspace.blueprint.defaults.depth} /><DefinitionItem label="Learning time" value={`${workspace.blueprint.defaults.minutes} min`} /><DefinitionItem label="Word target" value={workspace.blueprint.defaults.wordTarget.toLocaleString()} /><DefinitionItem label="Examples" value={workspace.blueprint.defaults.examples} /><DefinitionItem label="Case depth" value={workspace.blueprint.defaults.caseDepth} /><DefinitionItem label="Assessment" value={workspace.blueprint.defaults.assessmentComplexity} /></dl>
      </section>
      <div className="blueprint-toolbar">
        <div className="blueprint-filter" role="tablist" aria-label="Filter blueprint rows"><button role="tab" aria-selected={!exceptionsOnly} className={!exceptionsOnly ? "active" : ""} onClick={() => setExceptionsOnly(false)}>All subtopics <span>{workspace.blueprint.plans.length}</span></button><button role="tab" aria-selected={exceptionsOnly} className={exceptionsOnly ? "active" : ""} onClick={() => setExceptionsOnly(true)}>Overrides <span>{exceptionCount}</span></button></div>
        <div className="blueprint-legend" aria-label="Asset plan legend"><span><i className="legend-selected" aria-hidden="true">✓</i> Included</span><span><i className="legend-proposed" aria-hidden="true">–</i> Not selected</span><span><i className="legend-anchor" aria-hidden="true">◆</i> Required anchor</span></div>
      </div>
      <section className="blueprint-matrix" aria-label="Subtopic asset plans">
        {plans.length ? plans.map((plan) => {
          const overrides = blueprintOverrides(plan, workspace.blueprint.defaults);
          return (
            <article className="blueprint-plan-row" key={plan.subtopicId}>
              <header className="blueprint-plan-heading">
                <div className="blueprint-plan-title"><div><code>{plan.subtopicId}</code>{plan.exception ? <span className="exception-badge">{overrides.length || 1} override{overrides.length === 1 ? "" : "s"}</span> : <span className="baseline-badge">Uses baseline</span>}</div><h3>{names.get(plan.subtopicId) ?? "Untitled subtopic"}</h3>{overrides.length ? <p>{overrides.join(" · ")}</p> : <p>Course-wide depth and budget apply.</p>}</div>
                <dl className="plan-budget"><div><dt>Time</dt><dd>{plan.minutes} min</dd></div><div><dt>Words</dt><dd>{plan.wordTarget.toLocaleString()}</dd></div><div><dt>Examples</dt><dd>{plan.examples}</dd></div><div><dt>Assessment</dt><dd>{displayCode(plan.assessmentComplexity)}</dd></div></dl>
              </header>
              <div className="plan-assets">
                <span className="micro-label">Learner asset plan</span>
                <div className="asset-plan-grid">{assetColumns.map(([type, label]) => {
                  const asset = plan.assets.find((candidate) => candidate.assetType === type);
                  const selected = asset?.selectionStatus === "selected";
                  const anchor = type === "course_content";
                  return <div key={type} className={`asset-choice ${selected ? "asset-choice-selected" : "asset-choice-proposed"} ${anchor ? "asset-choice-anchor" : ""}`} aria-label={`${names.get(plan.subtopicId)} ${label}: ${selected ? "included" : "not selected"}`}><span className="asset-choice-mark" aria-hidden="true">{anchor ? "◆" : selected ? "✓" : "–"}</span><div><strong>{label}</strong><small>{anchor ? "Required anchor" : selected ? "Included" : "Not selected"}</small></div></div>;
                })}</div>
              </div>
            </article>
          );
        }) : <div className="blueprint-empty"><span aria-hidden="true">◇</span><h3>No overridden rows</h3><p>Every subtopic currently uses the course-wide baseline.</p></div>}
      </section>
      <div className="matrix-guardrail"><span className="guardrail-symbol" aria-hidden="true">◆</span><div><strong>Course Content remains the anchor.</strong><p>Every subtopic keeps one required Course Content asset. Generation can only use approved sources routed through the Course Model.</p></div></div>
      <LiveRevisionControls records={workspace.blueprint.plans.map((plan) => ({ targetType: "subtopic", id: plan.subtopicId, label: names.get(plan.subtopicId) ?? plan.subtopicId }))} onRequest={onRequestRevision} />
    </div>
  );
}

function claimHasAttribution(claim: Claim): boolean {
  return typeof claim.sourceId === "string" && Boolean(claim.sourceId.trim());
}

function claimNeedsInspection(claim: Claim): boolean {
  return claim.support !== "supported" || !claimHasAttribution(claim);
}

function claimDisplaySupport(claim: Claim): string {
  return claimHasAttribution(claim) ? claim.support : "ungrounded";
}

function verificationBreakdown(asset: ContentAsset): ContentAsset["verification"] {
  if (!asset.claims.length) return asset.verification;
  return asset.claims.reduce<ContentAsset["verification"]>((totals, claim) => {
    if (!claimHasAttribution(claim)) totals.ungrounded += 1;
    else if (claim.support === "supported") totals.supported += 1;
    else if (claim.support === "partial") totals.partial += 1;
    else totals.unsupported += 1;
    return totals;
  }, { supported: 0, partial: 0, unsupported: 0, ungrounded: 0, unattributed: asset.verification.unattributed });
}

function localVerificationTotal(asset: ContentAsset): number {
  const totals = verificationBreakdown(asset);
  return totals.unsupported + totals.ungrounded + totals.unattributed;
}

function evidenceReviewTotal(asset: ContentAsset): number {
  const totals = verificationBreakdown(asset);
  return totals.partial + totals.unsupported + totals.ungrounded + totals.unattributed;
}

function AssetReader({ asset, selectedClaimId, onSelectClaim }: { asset: ContentAsset; selectedClaimId?: string; onSelectClaim: (id: string) => void }) {
  const [tab, setTab] = useState<"reader" | "markdown" | "data">("reader");
  return (
    <section className="asset-reader">
      <header className="reader-header">
        {/* The asset id sits on the title attribute rather than under the
            heading it duplicates: `m1_s1_cc` is a reference for support
            questions, not a label for a course director. */}
        <div className="reader-title" title={`Asset reference: ${asset.id}`}><span className="micro-label">{displayCode(asset.type)} · {asset.format.toUpperCase()}</span><h2>{asset.title}</h2></div>
        <div className="reader-tabs" role="tablist" aria-label="Asset view"><button role="tab" aria-selected={tab === "reader"} className={tab === "reader" ? "active" : ""} onClick={() => setTab("reader")}>Reader</button><button role="tab" aria-selected={tab === "markdown"} className={tab === "markdown" ? "active" : ""} onClick={() => setTab("markdown")}>Markdown</button><button role="tab" aria-selected={tab === "data"} className={tab === "data" ? "active" : ""} onClick={() => setTab("data")}>Data</button></div>
      </header>
      <div className="reader-scroll">
        {tab === "reader" ? <div className="markdown-reader"><ReactMarkdown skipHtml>{asset.content}</ReactMarkdown></div> : null}
        {tab === "markdown" ? <pre className="raw-code">{asset.content}</pre> : null}
        {tab === "data" ? <pre className="raw-code">{JSON.stringify(asset, null, 2)}</pre> : null}
        {asset.claims.length ? <section className="claim-index"><div className="claim-index-heading"><div><span className="micro-label">Evidence claims</span><strong>{asset.claims.length} extracted from this asset</strong></div><span>{asset.claims.filter(claimNeedsInspection).length} to inspect</span></div><div className="claim-list">{asset.claims.map((claim) => <button key={claim.id} className={selectedClaimId === claim.id ? "active" : ""} onClick={() => onSelectClaim(claim.id)}><VerificationBadge support={claimDisplaySupport(claim)} /><span>{claim.text}</span><span className="claim-arrow" aria-hidden="true">›</span></button>)}</div></section> : null}
      </div>
    </section>
  );
}

function VerificationDetail({ asset, claim, blockers, reviewCount, canRevise, canContentRepair, canRepair, repairUnavailableReason, onAction }: { asset: ContentAsset; claim?: Claim; blockers: number; reviewCount: number; canRevise: boolean; canContentRepair: boolean; canRepair: boolean; repairUnavailableReason?: string; onAction?: (action: string, asset: ContentAsset, claim?: Claim) => void }) {
  const finding = claim ?? asset.claims.find(claimNeedsInspection) ?? asset.claims[0];
  const totals = verificationBreakdown(asset);
  const verificationTitle = blockers ? "Blocking evidence issues" : totals.partial ? "Partial evidence to review" : "Evidence checks passed";
  return (
    <aside className="verification-panel">
      <div className="verification-head"><div><span className="eyebrow">Verification</span><h3>{verificationTitle}</h3></div><span className={`verification-score ${blockers ? "score-attention" : reviewCount ? "score-review" : "score-good"}`}>{reviewCount || "✓"}</span></div>
      <div className="verification-metrics"><div><strong>{totals.supported}</strong><span>Supported</span></div><div className={totals.partial ? "review" : ""}><strong>{totals.partial}</strong><span>Partial</span></div><div className="bad"><strong>{totals.unsupported}</strong><span>Unsupported</span></div><div className="bad"><strong>{totals.ungrounded + totals.unattributed}</strong><span>No ground</span></div></div>
      {finding ? <div className={`finding-detail finding-${claimDisplaySupport(finding)}`}>
        <div className="finding-label"><VerificationBadge support={claimDisplaySupport(finding)} /><code>{finding.id}</code></div>
        <blockquote>{finding.text}</blockquote>
        <div className="finding-section"><span>Verifier note</span><p>{finding.note || "No verifier note was recorded."}</p></div>
        <div className="finding-section"><span>Assigned source</span><p>{finding.sourceId ? <><code>{finding.sourceId}</code>{finding.excerpt ? ` — “${finding.excerpt}”` : " — no supporting passage found"}</> : "No approved source attribution"}</p></div>
        {claimNeedsInspection(finding) && (canContentRepair || canRepair) ? <div className="repair-actions"><span className="micro-label">Available repair</span>{canContentRepair ? <button onClick={() => onAction?.("repair_existing", asset, finding)}><span aria-hidden="true">↻</span><div><strong>Revise with approved evidence</strong><small>Regenerate and reverify this asset only</small></div></button> : null}{canRepair ? <button onClick={() => onAction?.("source_repair", asset, finding)}><span aria-hidden="true">⌕</span><div><strong>Find better evidence</strong><small>Research one bounded gap, then review and route a source</small></div></button> : null}{!canRepair && repairUnavailableReason ? <p className="unsupported-action-note">{repairUnavailableReason}</p> : null}</div> : claimNeedsInspection(finding) ? <p className="unsupported-action-note">{repairUnavailableReason || (canRevise ? "Use scoped revision for a directed learner-facing change." : "No automated repair is registered for this stage state. Reopen the appropriate approved checkpoint before changing it.")}</p> : null}
      </div> : <div className="empty-mini">Select a claim to inspect its evidence.</div>}
    </aside>
  );
}

function ContentRepairQueue({ workspace, busy, canContentRepair, canSourceRepair, onAction }: { workspace: Workspace; busy: boolean; canContentRepair: boolean; canSourceRepair: boolean; onAction?: (action: string, asset: ContentAsset, claim?: Claim) => void }) {
  const findings = workspace.contentRepairs.findings;
  if (!findings.length) return null;
  const labels = {
    likely_content_error: "Likely content error",
    missing_attribution: "Missing attribution",
    insufficient_evidence: "Insufficient evidence",
    human_review: "Human review",
  };
  // With nothing blocking, this panel only restated the status banner directly
  // above it ("No blocking verification findings") while pushing the asset
  // workbench — the actual review surface — most of the way off screen. The
  // partial findings it listed are already shown against each asset in the
  // verification pane, and the banner links straight to them.
  const blocking = workspace.contentRepairs.hardBlockerTotal > 0;
  if (!blocking) return null;
  const groups = <div className="content-repair-groups">{Object.entries(labels).map(([classification, label]) => {
    const grouped = findings.filter((finding) => finding.classification === classification);
    if (!grouped.length) return null;
    return <section key={classification} className={`content-repair-group repair-group-${classification}`}><div><strong>{label}</strong><span>{grouped.length}</span></div>{grouped.map((finding) => {
      const asset = workspace.content.assets.find((candidate) => candidate.id === finding.assetId);
      const claim = asset?.claims.find((candidate) => candidate.id === finding.claimId);
      return <article key={finding.id}><div><span className={`repair-state repair-state-${finding.blocking ? "blocking" : "review"}`}>{finding.blocking ? "Blocking" : "Review"}</span><code>{finding.assetId}</code><h3>{finding.text}</h3><p>{finding.classificationReason}</p><small>{displayCode(finding.state)}</small></div>{finding.blocking && asset ? <footer>{canContentRepair ? <button className="button button-secondary" aria-label={`Revise with approved evidence for ${finding.assetId}, finding ${finding.findingId}`} disabled={busy} onClick={() => onAction?.("repair_existing", asset, claim)}>Revise with approved evidence</button> : null}{canSourceRepair && claim ? <button className="button button-quiet" aria-label={`Find better evidence for ${finding.assetId}, finding ${finding.findingId}`} disabled={busy} onClick={() => onAction?.("source_repair", asset, claim)}>Find better evidence</button> : null}</footer> : null}</article>;
    })}</section>;
  })}</div>;
  const counts = <span>{workspace.contentRepairs.hardBlockerTotal} blocking · {workspace.contentRepairs.partialTotal} to review</span>;
  return <section className="content-repair-queue" aria-label="Content repair queue"><header><div><span className="eyebrow">Verifier triage</span><h2>Resolve these before release</h2><p>Cause labels are advisory. Every action stays bounded to the named asset and current finding.</p></div>{counts}</header>{groups}</section>;
}

function SourceRepairQueue({ entries, busy, onDecision, onRoute, onContentRepair }: { entries: SourceRepairEntry[]; busy: boolean; onDecision?: (entry: SourceRepairEntry, candidateId: string) => void; onRoute?: (entry: SourceRepairEntry) => void; onContentRepair?: (entry: SourceRepairEntry) => void }) {
  if (!entries.length) return null;
  return <section className="source-repair-queue" aria-label="Source repair queue"><header><div><span className="eyebrow">Bounded evidence repair</span><h2>Source repair queue</h2><p>Recommendations are advisory. A source remains outside the approved registry until you decide and confirm the exact route.</p></div><span>{entries.length} entr{entries.length === 1 ? "y" : "ies"}</span></header><div>{entries.map((entry) => <article key={entry.id} className={`source-repair-entry repair-${entry.status}`}><div className="source-repair-origin"><span className="repair-state">{displayCode(entry.status)}</span><code>{entry.id}</code><h3>{entry.evidenceGap}</h3><p>Finding <code>{entry.origin.findingId}</code> · asset <code>{entry.origin.assetId}</code> · subtopic <code>{entry.origin.subtopicId}</code></p></div>{entry.status === "requested" || entry.status === "researching" ? <div className="repair-working"><span className="loading-orbit" aria-hidden="true" /><div><strong>Researching one evidence gap</strong><p>The approved source registry has not changed.</p></div></div> : null}{entry.status === "awaiting_source_decision" ? <div className="repair-candidates">{entry.proposedCandidates.map((candidate) => <div className="repair-candidate" key={candidate.id}><header><div><span className={`quality-recommendation quality-${candidate.quality.recommendation}`}>{displayCode(candidate.quality.recommendation)}</span><h4>{candidate.title}</h4><p>{candidate.publisher} · {candidate.sourceType}</p></div><span className="candidate-score"><strong>{candidate.quality.overall.toFixed(1)}</strong><small>/ 5 advisory</small></span></header><p>{candidate.relevance}</p><div className="repair-coverage"><span>Likely gap coverage</span>{candidate.quality.coverage.map((row) => <div key={row.need}><strong>{row.score}/5</strong><p>{row.need}</p></div>)}</div>{candidate.quality.previewSections.map((section) => <blockquote key={`${candidate.id}:${section.order}`}>{section.text}</blockquote>)}<details><summary>Why this score?</summary><dl>{Object.entries(candidate.quality.dimensions).map(([name, dimension]) => <div key={name}><dt>{displayCode(name)}</dt><dd><strong>{dimension.score}/5</strong> {dimension.reason}</dd></div>)}</dl></details><footer><a href={candidate.locator} target="_blank" rel="noreferrer">Open source</a><button className="button button-primary" disabled={busy || candidate.fetchStatus !== "available" || !onDecision} onClick={() => onDecision?.(entry, candidate.id)}>Approve this candidate</button></footer></div>)}</div> : null}{entry.status === "awaiting_route_confirmation" ? <div className="repair-route-confirm"><span className="micro-label">Human route confirmation</span><h4>Confirm the only permitted change</h4><dl><div><dt>Course Model subtopic</dt><dd><code>{entry.origin.subtopicId}</code></dd></div><div><dt>Blueprint asset</dt><dd><code>{entry.origin.assetId}</code></dd></div><div><dt>Structure / selection</dt><dd>Unchanged</dd></div></dl><p>This transaction will merge the approved source into the dossier and registry, add one named Course Model mapping, and add one named Blueprint asset route.</p><button className="button button-primary" disabled={busy || !onRoute} onClick={() => onRoute?.(entry)}>Confirm exact source route</button></div> : null}{entry.status === "awaiting_content_repair" ? <div className="repair-routed"><span aria-hidden="true">✓</span><div><strong>Source approved and route committed atomically</strong><p>Affected asset: {entry.affectedAssetIds.join(", ")}. Content is unchanged until you run the targeted repair.</p><button className="button button-primary" disabled={busy || !onContentRepair} onClick={() => onContentRepair?.(entry)}>Regenerate and reverify</button></div></div> : null}{entry.status === "regenerating" ? <div className="repair-working"><span className="loading-orbit" aria-hidden="true" /><div><strong>Regenerating and reverifying the named asset</strong><p>Unrelated learner assets remain byte-for-byte unchanged.</p></div></div> : null}{entry.status === "awaiting_content_review" ? <div className="repair-routed"><span aria-hidden="true">✓</span><div><strong>Targeted regeneration complete</strong><p>{entry.finalVerifierResult?.hardBlockerTotal ? `${entry.finalVerifierResult.hardBlockerTotal} blocker(s) remain.` : "No hard verifier blockers remain."} Human review is still required.</p></div></div> : null}{entry.status === "resolved" ? <div className="repair-routed"><span aria-hidden="true">✓</span><div><strong>Repair resolved</strong><p>The current regenerated asset passed verification and human review.</p></div></div> : null}{entry.status === "failed" || entry.failureReason ? <p className="unsupported-action-note">{entry.failureReason || "This repair entry failed without changing approved routes."}</p> : null}</article>)}</div></section>;
}

function ContentView({ workspace, initialAssetId, canReview, canRevise, canContentRepair, canRepair, repairUnavailableReason, repairBusy, onContentAction, onRepairDecision, onRepairRoute, onContentRepair }: { workspace: Workspace; initialAssetId?: string; canReview: boolean; canRevise: boolean; canContentRepair: boolean; canRepair: boolean; repairUnavailableReason?: string; repairBusy: boolean; onContentAction?: (action: string, asset: ContentAsset, claim?: Claim) => void; onRepairDecision?: (entry: SourceRepairEntry, candidateId: string) => void; onRepairRoute?: (entry: SourceRepairEntry) => void; onContentRepair?: (entry: SourceRepairEntry) => void }) {
  const assets = workspace.content.assets;
  const findingsForAsset = (assetId: string) => workspace.contentRepairs.findings.filter((finding) => finding.assetId === assetId);
  const hasProjectedFindings = workspace.contentRepairs.findings.length > 0;
  const blockerTotalForAsset = (assetId: string) => {
    const projected = findingsForAsset(assetId).filter((finding) => finding.blocking).length;
    if (hasProjectedFindings) return projected;
    const asset = assets.find((candidate) => candidate.id === assetId);
    return asset ? localVerificationTotal(asset) : 0;
  };
  const attentionTotalForAsset = (assetId: string) => {
    const projected = findingsForAsset(assetId).length;
    if (hasProjectedFindings) return projected;
    const asset = assets.find((candidate) => candidate.id === assetId);
    return asset ? evidenceReviewTotal(asset) : 0;
  };
  const initial = assets.find((asset) => asset.id === initialAssetId)
    ?? assets.find((asset) => attentionTotalForAsset(asset.id) > 0)
    ?? assets[0];
  const [selectedAssetId, setSelectedAssetId] = useState(initial?.id ?? "");
  const [selectedClaimId, setSelectedClaimId] = useState<string | undefined>(initial?.claims.find(claimNeedsInspection)?.id);
  const [filter, setFilter] = useState<"all" | "attention" | "approved">("all");
  useEffect(() => {
    if (!assets.length) {
      setSelectedAssetId("");
      setSelectedClaimId(undefined);
      return;
    }
    if (!assets.some((asset) => asset.id === selectedAssetId)) {
      const next = assets.find((asset) => attentionTotalForAsset(asset.id) > 0) ?? assets[0];
      setSelectedAssetId(next.id);
      setSelectedClaimId(next.claims.find(claimNeedsInspection)?.id ?? next.claims[0]?.id);
    }
  }, [assets, selectedAssetId]);
  useEffect(() => {
    if (!initialAssetId) return;
    const target = assets.find((asset) => asset.id === initialAssetId);
    if (!target) return;
    setFilter("all");
    setSelectedAssetId(target.id);
    setSelectedClaimId(target.claims.find(claimNeedsInspection)?.id ?? target.claims[0]?.id);
  }, [assets, initialAssetId]);
  const selected = assets.find((asset) => asset.id === selectedAssetId) ?? assets[0];
  const visible = assets.filter((asset) => filter === "all" || (filter === "attention" ? attentionTotalForAsset(asset.id) > 0 : asset.reviewStatus === "approved"));
  const selectedClaim = selected?.claims.find((claim) => claim.id === selectedClaimId);
  const blockers = hasProjectedFindings
    ? workspace.contentRepairs.hardBlockerTotal
    : assets.reduce((total, asset) => total + localVerificationTotal(asset), 0);
  const reviewAssets = assets.filter((asset) => attentionTotalForAsset(asset.id) > 0).length;
  const selectedBlockers = selected ? blockerTotalForAsset(selected.id) : 0;
  const selectedReviewCount = selected ? attentionTotalForAsset(selected.id) : 0;
  const plannedAssets = workspace.blueprint.plans.flatMap((plan) => plan.assets).filter((asset) => asset.selectionStatus === "selected").length;
  const progressTotal = Math.max(workspace.content.expected, assets.length);
  const progressPercent = progressTotal ? (workspace.content.completed / progressTotal) * 100 : 0;
  return (
    <div className="stage-view content-stage">
      {stageIntro("Student Content", "06 · Production & verification", assets.length ? "Review generated assets and inspect how each learner-facing claim is supported before approving the course content." : "The approved Blueprint is ready. Run this stage to generate learner assets and verify their claims against approved evidence.", assets.length ? <div className="production-progress"><div><strong>{workspace.content.completed}<span>/ {progressTotal}</span></strong><span>assets generated</span></div><div className="mini-progress"><span style={{ width: `${progressPercent}%` }} /></div></div> : <div className="content-ready-badge"><span aria-hidden="true">◇</span><div><strong>Ready to generate</strong><small>Blueprint approved</small></div></div>)}
      {!assets.length ? <section className="content-empty-state">
        <div className="content-empty-main"><div className="empty-artifact-icon" aria-hidden="true"><span>▤</span><i>◆</i></div><span className="eyebrow">Generation workspace</span><h2>No learner assets have been generated yet</h2><p>This is the expected starting state. The agent will follow the approved Blueprint, generate Course Content anchors first, create the selected supporting assets, and then verify their claims.</p><div className="generation-sequence"><div><span>01</span><div><strong>Generate anchors</strong><small>One Course Content asset per planned subtopic</small></div></div><div><span>02</span><div><strong>Create selected assets</strong><small>Only the asset mix approved in the Blueprint</small></div></div><div><span>03</span><div><strong>Verify evidence</strong><small>Check claims against routed approved sources</small></div></div></div></div>
        <aside className="generation-readiness"><span className="micro-label">Ready inputs</span><h3>The agent has what it needs</h3><dl><div><dt>Planned subtopics</dt><dd>{workspace.blueprint.plans.length}</dd></div><div><dt>Selected assets</dt><dd>{plannedAssets}</dd></div><div><dt>Approved sources</dt><dd>{workspace.research.sources.filter((source) => source.status === "approved").length}</dd></div></dl><div className="generation-ready-note"><span aria-hidden="true">✓</span><p>Use <strong>Run Student Content</strong> in the stage action bar to begin.</p></div></aside>
      </section> : <>
      <div className={`content-status-banner ${blockers ? "status-banner-attention" : "status-banner-good"}`}><div className="attention-symbol" aria-hidden="true">{blockers ? "!" : "✓"}</div><div><strong>{blockers ? `${blockers} blocking verification finding${blockers === 1 ? "" : "s"}` : "No blocking verification findings"}</strong><p>{blockers ? "Resolve unsupported, ungrounded, and unattributed claims before approval." : reviewAssets ? `${reviewAssets} asset${reviewAssets === 1 ? " has" : "s have"} partial evidence to inspect during human review.` : "Evidence checks passed. Complete the human review for each asset before approving this stage."}</p></div>{blockers || reviewAssets ? <button onClick={() => setFilter("attention")}>Review evidence <span aria-hidden="true">→</span></button> : <span className="review-ready-pill">Ready for review</span>}</div>
      <ContentRepairQueue workspace={workspace} busy={repairBusy} canContentRepair={canContentRepair} canSourceRepair={canRepair} onAction={onContentAction} />
      <SourceRepairQueue entries={workspace.sourceRepairs} busy={repairBusy} onDecision={onRepairDecision} onRoute={onRepairRoute} onContentRepair={onContentRepair} />
      <div className="content-toolbar"><div className="content-filter" role="tablist" aria-label="Filter generated assets"><button role="tab" aria-selected={filter === "all"} className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>All assets <span>{assets.length}</span></button><button role="tab" aria-selected={filter === "attention"} className={filter === "attention" ? "active" : ""} onClick={() => setFilter("attention")}>Evidence review <span>{reviewAssets}</span></button><button role="tab" aria-selected={filter === "approved"} className={filter === "approved" ? "active" : ""} onClick={() => setFilter("approved")}>Reviewed <span>{assets.filter((asset) => asset.reviewStatus === "approved").length}</span></button></div><p><span aria-hidden="true">◆</span> Course Content anchors are generated first</p></div>
      <div className="content-workspace">
        <aside className="production-board" aria-label="Production board">
          {workspace.modules.flatMap((module) => module.subtopics).map((subtopic) => {
            const subtopicAssets = visible.filter((asset) => asset.subtopicId === subtopic.id);
            if (!subtopicAssets.length) return null;
            return <div className="production-group" key={subtopic.id}><div className="production-group-head"><span>{String(subtopic.order).padStart(2, "0")}</span><div><strong>{subtopic.title}</strong><small>{subtopicAssets.length} assets</small></div></div><div>{subtopicAssets.map((asset) => {
              const reviewTotal = attentionTotalForAsset(asset.id);
              return <button key={asset.id} className={selected?.id === asset.id ? "active" : ""} onClick={() => { setSelectedAssetId(asset.id); setSelectedClaimId(asset.claims.find(claimNeedsInspection)?.id ?? asset.claims[0]?.id); }}><span className={`asset-kind kind-${asset.type === "course_content" ? "anchor" : "support"}`}>{asset.type === "course_content" ? "C" : asset.type.charAt(0).toUpperCase()}</span><span className="asset-nav-copy"><strong>{asset.title}</strong><small>{displayCode(asset.type)} · {asset.reviewStatus === "approved" ? "Reviewed" : "Awaiting review"}</small></span><span className={reviewTotal ? "asset-alert" : "asset-ok"}>{reviewTotal || "✓"}</span></button>;
            })}</div></div>;
          })}
          {!visible.length ? <div className="filter-empty"><span aria-hidden="true">◇</span><strong>No matching assets</strong><p>Choose another filter to continue reviewing.</p></div> : null}
        </aside>
        {selected ? <AssetReader asset={selected} selectedClaimId={selectedClaimId} onSelectClaim={setSelectedClaimId} /> : <div className="reader-empty"><span aria-hidden="true">▤</span><strong>Select an asset</strong><p>Choose an item from the production board to review its content.</p></div>}
        {selected ? <VerificationDetail asset={selected} claim={selectedClaim} blockers={selectedBlockers} reviewCount={selectedReviewCount} canRevise={canRevise} canContentRepair={canContentRepair} canRepair={canRepair} repairUnavailableReason={repairUnavailableReason} onAction={onContentAction} /> : null}
      </div>
      {selected ? <div className="asset-review-strip"><div><span className={`review-state review-${selected.reviewStatus}`} /> <div><strong>{selected.reviewStatus === "approved" ? "Human review complete" : selectedBlockers ? "Resolve blockers before review" : "Human review required"}</strong><span>{selectedBlockers ? `${selectedBlockers} blocking finding${selectedBlockers === 1 ? "" : "s"} must be repaired first.` : selectedReviewCount ? "Partial evidence remains visible for your judgment." : "Evidence checks passed; confirm the learner-facing content."}</span></div></div>{canReview || canRevise ? <div>{canRevise ? <button className="button button-secondary" onClick={() => onContentAction?.("revise", selected)}>Request scoped revision</button> : null}{canReview ? <button className="button button-primary" disabled={selectedBlockers > 0 || selected.reviewStatus === "approved"} onClick={() => onContentAction?.("approved", selected)}>{selected.reviewStatus === "approved" ? "Reviewed" : "Mark asset reviewed"}</button> : null}</div> : <small className="muted">Review decisions are unavailable; scoped revisions are also unavailable in the current stage state.</small>}</div> : null}
      </>}
    </div>
  );
}

function LessonPlanView({
  workspace,
  editing = false,
  busy = false,
  conflict = false,
  serverError,
  onStartEdit,
  onCancel,
  onSave,
  onRecoverConflict,
  onDirtyChange,
  onRequestRevision,
}: {
  workspace: Workspace;
  editing?: boolean;
  busy?: boolean;
  conflict?: boolean;
  serverError?: string;
  onStartEdit?: () => void;
  onCancel?: () => void;
  onSave?: (decision: LessonPlanDecisionDraft) => void;
  onRecoverConflict?: (choice: "reapply" | "discard") => void;
  onDirtyChange?: (dirty: boolean) => void;
  onRequestRevision?: (targetType: string, id: string, label: string) => void;
}) {
  const names = new Map(workspace.modules.flatMap((module) => module.subtopics.map((subtopic) => [subtopic.id, subtopic.title])));
  const nameRecord = Object.fromEntries(names);
  const expected = workspace.lessonPlan.expectedSubtopicIds.length;
  const sessionCount = workspace.lessonPlan.sessions.length;
  const allCovers = workspace.lessonPlan.sessions.flatMap((session) => session.covers);
  const coverCounts = allCovers.reduce((counts, cover) => counts.set(cover.subtopicId, (counts.get(cover.subtopicId) ?? 0) + 1), new Map<string, number>());
  const covered = workspace.lessonPlan.expectedSubtopicIds.filter((id) => (coverCounts.get(id) ?? 0) > 0).length;
  const exactCoverage = expected > 0 && workspace.lessonPlan.expectedSubtopicIds.every((id) => coverCounts.get(id) === 1) && allCovers.every((cover) => workspace.lessonPlan.expectedSubtopicIds.includes(cover.subtopicId));
  const coveragePercent = Math.min(100, Math.round((covered / Math.max(expected, 1)) * 100));
  const modeLabels = [...new Set(allCovers.map((cover) => cover.mode.replace("_", " ")))].map((mode) => mode.replace(/\b\w/g, (letter) => letter.toUpperCase()));
  if (editing) return <LessonPlanEditor lessonPlan={workspace.lessonPlan} subtopicNames={nameRecord} canEdit={Boolean(onStartEdit)} editing busy={busy} conflict={conflict} serverError={serverError} onStartEdit={onStartEdit ?? (() => undefined)} onCancel={onCancel ?? (() => undefined)} onSave={onSave ?? (() => undefined)} onResolveConflict={onRecoverConflict ?? (() => undefined)} onDirtyChange={onDirtyChange} />;
  return (
    <div className="stage-view lesson-plan-view">
      {stageIntro("Lesson Plan", "07 · Delivery sequence", "Turn approved content into a teachable sequence with explicit duration, mode, coverage, and facilitation cues.", <><div className="lesson-total"><strong>{workspace.lessonPlan.totalDurationMinutes}<small>min</small></strong><span>across {sessionCount} {sessionCount === 1 ? "session" : "sessions"}</span></div>{onStartEdit ? <button className="button button-secondary" disabled={busy} onClick={onStartEdit}>Edit Lesson Plan</button> : null}</>)}
      <div className="lesson-layout">
        <section className="session-timeline">
          <div className="timeline-heading"><div><span className="eyebrow">Session timeline</span><h2>{sessionCount} connected {sessionCount === 1 ? "session" : "sessions"}</h2><p>Review the teaching order, delivery mode, and facilitation cues before approval.</p></div><div className="timeline-status"><span aria-hidden="true">✓</span><div><strong>Sequence connected</strong><small>{allCovers.length} planned {allCovers.length === 1 ? "segment" : "segments"}</small></div></div></div>
          {workspace.lessonPlan.sessions.map((session, index) => (
            <article className="session-card" key={session.id}>
              <div className="session-marker"><span>{String(index + 1).padStart(2, "0")}</span><i /></div>
              <div className="session-content">
                <div className="session-head"><div title={`Session reference: ${session.id}`}><span className="micro-label">Session {index + 1}</span><h3>{session.title}</h3></div><div className="duration-pill"><strong>{session.durationMinutes}</strong><span>minutes</span></div></div>
                <div className="session-meta"><div><span>Segments</span><strong>{session.covers.length}</strong></div><div><span>Delivery</span><strong>{[...new Set(session.covers.map((cover) => cover.mode.replace("_", " ")))].join(" + ")}</strong></div><div><span>Coverage</span><strong>{session.covers.length} of {expected}</strong></div></div>
                <div className="session-covers">{session.covers.map((cover, coverIndex) => <div className="cover-row" key={cover.subtopicId}><div className="cover-sequence">{index + 1}.{coverIndex + 1}</div><div className="cover-body"><div className="cover-title"><div><span className="micro-label">Course Model subtopic</span><strong>{names.get(cover.subtopicId) ?? cover.subtopicId}</strong></div><span className={`mode mode-${cover.mode}`}>{cover.mode.replace("_", " ")}</span></div><ol className="teaching-sequence">{cover.talkingPoints.map((point, pointIndex) => <li key={point}><span>{String(pointIndex + 1).padStart(2, "0")}</span><p>{point}</p></li>)}</ol></div></div>)}</div>
              </div>
            </article>
          ))}
        </section>
        <aside className="lesson-constraints">
          <div className="constraint-heading"><span className="eyebrow">Delivery contract</span><h3>Plan at a glance</h3><p>Constraints carried forward from the approved course artifacts.</p></div>
          <dl><DefinitionItem label="Sessions" value={sessionCount} /><DefinitionItem label="Total time" value={`${workspace.lessonPlan.totalDurationMinutes} minutes`} /><DefinitionItem label="Delivery" value={modeLabels.join(" + ") || "Not specified"} /><DefinitionItem label="Breaks" value="As needed" /></dl>
          <div className="coverage-summary"><div className="coverage-summary-head"><div className={exactCoverage ? "coverage-count complete" : "coverage-count"}><strong>{covered}</strong><span>/ {expected}</span></div><div><span className="micro-label">Course Model coverage</span><strong>{exactCoverage ? "Complete coverage" : "Coverage needs review"}</strong></div></div><div className="coverage-track" role="progressbar" aria-label="Course Model coverage" aria-valuemin={0} aria-valuemax={expected} aria-valuenow={covered}><span style={{ width: `${coveragePercent}%` }} /></div></div>
          <div className={`coverage-check ${exactCoverage ? "" : "coverage-warning"}`}><span aria-hidden="true">{exactCoverage ? "✓" : "!"}</span><p>{exactCoverage ? "Every Course Model subtopic appears exactly once in the delivery sequence." : "At least one Course Model subtopic is missing, duplicated, or outside the approved model."}</p></div>
          {/* Session numbers, not raw ids: "sess3, sess4, sess5" told the
              operator nothing, and the ordinal is what the timeline shows.
              Ids with no current position belong to sessions the change
              retired, which is reported as a count rather than as an id. */}
          {workspace.lessonPlan.affectedSessionIds.length ? (() => {
            const positions: string[] = [];
            let retired = 0;
            for (const sessionId of workspace.lessonPlan.affectedSessionIds) {
              const position = workspace.lessonPlan.sessions.findIndex((session) => session.id === sessionId);
              if (position >= 0) positions.push(String(position + 1));
              else retired += 1;
            }
            const parts: string[] = [];
            if (positions.length) parts.push(`${positions.length === 1 ? "session" : "sessions"} ${formatList(positions)}`);
            if (retired) parts.push(`removed ${retired} session${retired === 1 ? "" : "s"}`);
            return <div className="constraint-revision-note"><span aria-hidden="true">↳</span><p>Your last change affected {formatList(parts)}.</p></div>;
          })() : null}
          <div className="constraint-revision-note"><span aria-hidden="true">↳</span><p>{onStartEdit ? "Use the typed editor to change timing, delivery mode, placement, or sequence." : "Editing is unavailable in the current lifecycle state."}</p></div>
        </aside>
      </div>
      <LiveRevisionControls records={workspace.lessonPlan.expectedSubtopicIds.map((id) => ({ targetType: "subtopic", id, label: names.get(id) ?? id }))} onRequest={onRequestRevision} />
    </div>
  );
}

function flattenOutputFiles(files: OutputFile[]): OutputFile[] {
  return files.flatMap((file) => file.kind === "markdown" ? [file] : flattenOutputFiles(file.children ?? []));
}

function FileTree({ files, selectedPath, depth = 0, onSelect }: { files: OutputFile[]; selectedPath?: string; depth?: number; onSelect: (file: OutputFile) => void }) {
  return <ul className="file-tree">{files.map((file) => <li key={file.path}>{file.kind === "folder" ? <div className="file-tree-folder" style={{ paddingLeft: `${12 + depth * 18}px` }}><span className="file-icon file-folder" aria-hidden="true">⌄</span><span>{file.label}</span></div> : <button className={selectedPath === file.path ? "active" : ""} aria-current={selectedPath === file.path ? "true" : undefined} style={{ paddingLeft: `${12 + depth * 18}px` }} onClick={() => onSelect(file)}><span className="file-icon file-markdown" aria-hidden="true">M</span><span>{file.label}</span></button>}{file.children ? <FileTree files={file.children} selectedPath={selectedPath} depth={depth + 1} onSelect={onSelect} /> : null}</li>)}</ul>;
}

function PackageView({ workspace, onNavigate }: { workspace: Workspace; onNavigate?: (stage: StageSlug, assetId?: string) => void }) {
  const markdownFiles = useMemo(() => flattenOutputFiles(workspace.package.files), [workspace.package.files]);
  const [selectedPath, setSelectedPath] = useState<string>();
  const selected = markdownFiles.find((file) => file.path === selectedPath) ?? markdownFiles[0];
  const [preview, setPreview] = useState<{ path?: string; content?: string; error?: string; loading: boolean }>({ loading: false });
  const packageBuilt = markdownFiles.length > 0;
  useEffect(() => {
    if (!markdownFiles.length) {
      setSelectedPath(undefined);
      return;
    }
    if (!selectedPath || !markdownFiles.some((file) => file.path === selectedPath)) setSelectedPath(markdownFiles[0].path);
  }, [markdownFiles, selectedPath]);
  useEffect(() => {
    if (!selected || selected.kind !== "markdown") {
      setPreview({ loading: false });
      return;
    }
    let cancelled = false;
    setPreview({ path: selected.path, loading: true });
    void getOutputMarkdown(workspace.course.courseId, selected.path)
      .then((content) => {
        if (!cancelled) setPreview({ path: selected.path, content, loading: false });
      })
      .catch((error) => {
        if (!cancelled) setPreview({ path: selected.path, error: error instanceof Error ? error.message : "The Markdown preview could not be loaded.", loading: false });
      });
    return () => { cancelled = true; };
  }, [selected, workspace.course.courseId]);
  const unavailableCheck: ReleaseCheck = {
    id: "release_checks_unavailable",
    label: "Release checks unavailable",
    passed: false,
    detail: "Rerun Package so the backend can project the current release gates.",
    targetStage: "package",
  };
  const checks = workspace.package.releaseChecks.length
    ? workspace.package.releaseChecks
    : [unavailableCheck];
  const ready = checks.every((check) => check.passed);
  return (
    <div className="stage-view package-view">
      {stageIntro("Course Package", "08 · Release gate", packageBuilt ? "Review the rendered Markdown folder and confirm every release gate before delivery." : "Build the final Markdown folder, reconcile the approved artifacts, and surface anything that still blocks delivery.", packageBuilt ? <div className={`release-state ${ready ? "release-ready" : "release-blocked"}`}><span aria-hidden="true">{ready ? "✓" : "!"}</span><div><small>Operator status</small><strong>{ready ? "Ready" : "Requires attention"}</strong></div></div> : <div className="package-ready-state"><span aria-hidden="true">◇</span><div><strong>Ready to build</strong><small>Inputs prepared</small></div></div>)}
      {!packageBuilt ? <section className="package-empty-state"><div className="package-empty-main"><div className="empty-artifact-icon" aria-hidden="true"><span>▤</span><i>◆</i></div><span className="eyebrow">Package workspace</span><h2>No rendered package yet</h2><p>This is the expected state before the final stage runs. The agent will reconcile the approved structure and selected assets, then write the learner-facing Markdown folder.</p><div className="package-build-sequence"><div><span>01</span><div><strong>Validate references</strong><small>Check Course Model and downstream artifact IDs</small></div></div><div><span>02</span><div><strong>Reconcile the release</strong><small>Compare selected, generated, and reviewed assets</small></div></div><div><span>03</span><div><strong>Render Markdown</strong><small>Create the course index, lesson plan, sources, and modules</small></div></div></div></div><aside className="package-readiness"><span className="micro-label">Ready inputs</span><h3>The final build can start</h3><dl><div><dt>Lesson sessions</dt><dd>{workspace.lessonPlan.sessions.length}</dd></div><div><dt>Generated assets</dt><dd>{workspace.content.completed}</dd></div><div><dt>Approved sources</dt><dd>{workspace.package.approvedSourceCount}</dd></div></dl>{workspace.package.unresolvedBlockers ? <div className="package-blocker-note"><span aria-hidden="true">!</span><p><strong>{workspace.package.unresolvedBlockers} content blockers remain.</strong> The package can be rendered for inspection, but it will not be releasable.</p></div> : <div className="generation-ready-note"><span aria-hidden="true">✓</span><p>All known release inputs are ready.</p></div>}<div className="package-run-note"><span aria-hidden="true">→</span><p>Use <strong>Run Package</strong> in the stage action bar to build the folder.</p></div></aside></section> : <>
      <div className="release-checklist"><div className="release-title"><span className="eyebrow">Release checklist</span><h2>{ready ? "All gates passed" : "The package is rendered, but not releasable yet"}</h2><p>{ready ? "This course is ready for operator delivery." : "Mechanical completion does not override unresolved verification blockers."}</p></div><div className="release-checks">{checks.map((check) => check.passed ? <div key={check.id} className="passed"><span aria-hidden="true">✓</span><div><strong>{check.label}</strong><small>{check.detail}</small></div></div> : <button type="button" key={check.id} className="blocked" aria-label={`Go to ${check.label} blocker in ${check.targetStage}${check.targetAssetId ? `, asset ${check.targetAssetId}` : ""}`} onClick={() => onNavigate?.(check.targetStage, check.targetAssetId)}><span aria-hidden="true">!</span><div><strong>{check.label}</strong><small>{check.detail}</small><em>Go to {check.targetAssetId ? "asset" : "stage"} →</em></div></button>)}</div></div>
      <div className="package-browser">
        <aside className="output-tree"><div className="tree-heading"><div><span className="micro-label">Rendered output</span><strong>{markdownFiles.length} Markdown {markdownFiles.length === 1 ? "file" : "files"}</strong></div></div><div className="file-tree-scroll"><FileTree files={workspace.package.files} selectedPath={selected?.path} onSelect={(file) => setSelectedPath(file.path)} /></div><div className="format-note"><strong>{workspace.package.format}</strong><p>Markdown is the canonical learner-facing format for this release.</p></div></aside>
        <section className="output-preview">
          <header><div><span className="micro-label">Preview</span><h3>{selected?.label ?? "Select a file"}</h3><code>{selected?.path}</code></div>{selected?.kind === "markdown" ? <a className="button button-secondary" target="_blank" rel="noreferrer" href={`/api/courses/${encodeURIComponent(workspace.course.courseId)}/outputs/${selected.path.split("/").map(encodeURIComponent).join("/")}`}>Open raw file</a> : null}</header>
          {selected?.kind === "markdown" ? <div className="markdown-reader package-markdown" role="region" aria-label={`Preview of ${selected.label}`} aria-busy={preview.loading}>{preview.loading ? <p role="status">Loading the canonical rendered file…</p> : preview.error ? <div className="preview-error" role="alert"><strong>Preview unavailable</strong><p>{preview.error}</p></div> : preview.path === selected.path && preview.content != null ? <><span className="preview-document-label">Canonical rendered file</span><ReactMarkdown skipHtml>{preview.content}</ReactMarkdown></> : null}</div> : null}
        </section>
      </div>
      </>}
    </div>
  );
}

export function StageView({ stage, workspace, initialAssetId, onNavigate, contentCapabilities, onContentAction, onRequestRevision, onSourceDecision, onAddKnownSource, sourceMutationBusy, sourceRepairBusy, onSourceRepairDecision, onSourceRepairRoute, onContentRepair, onEditBrief, outcomesEditing, outcomesBusy, outcomesConflict, outcomesServerError, outcomesServerIssues, onStartOutcomesEdit, onCancelOutcomesEdit, onSaveOutcomes, onResolveOutcomesConflict, onOutcomesDirtyChange, courseModelEditing, courseModelBusy, courseModelConflict, courseModelServerError, courseModelServerIssues, courseModelPreview, onStartCourseModelEdit, onCancelCourseModelEdit, onPreviewCourseModel, onSaveCourseModel, onInvalidateCourseModelPreview, onRecoverCourseModelConflict, onCourseModelDirtyChange, blueprintEditing, blueprintBusy, blueprintConflict, blueprintServerError, onStartBlueprintEdit, onCancelBlueprintEdit, onSaveBlueprint, onRecoverBlueprintConflict, onBlueprintDirtyChange, lessonPlanEditing, lessonPlanBusy, lessonPlanConflict, lessonPlanServerError, onStartLessonPlanEdit, onCancelLessonPlanEdit, onSaveLessonPlan, onRecoverLessonPlanConflict, onLessonPlanDirtyChange, briefQuestionRound, briefQuestionsLoading, briefQuestionsBusy, briefQuestionsError, onRetryBriefQuestions, onSubmitBriefQuestions }: { stage: StageSlug; workspace: Workspace; initialAssetId?: string; onNavigate?: (stage: StageSlug, assetId?: string) => void; contentCapabilities?: { review: boolean; revise: boolean; contentRepair: boolean; repair: boolean; repairUnavailableReason?: string }; onContentAction?: (action: string, asset: ContentAsset, claim?: Claim) => void; onRequestRevision?: (targetType: string, id: string, label: string) => void; onSourceDecision?: (selectedIds: string[]) => void; onAddKnownSource?: (source: { locator: string; title?: string; publisher?: string; trustNotes?: string; relevance?: string }) => void; sourceMutationBusy?: boolean; sourceRepairBusy?: boolean; onSourceRepairDecision?: (entry: SourceRepairEntry, candidateId: string) => void; onSourceRepairRoute?: (entry: SourceRepairEntry) => void; onContentRepair?: (entry: SourceRepairEntry) => void; onEditBrief?: (section: BriefEditSection) => void; outcomesEditing?: boolean; outcomesBusy?: boolean; outcomesConflict?: boolean; outcomesServerError?: string; outcomesServerIssues?: OutcomeValidationIssue[]; onStartOutcomesEdit?: () => void; onCancelOutcomesEdit?: () => void; onSaveOutcomes?: (decision: OutcomeDecisionDraft) => void; onResolveOutcomesConflict?: (choice: "latest" | "keep") => void; onOutcomesDirtyChange?: (dirty: boolean) => void; courseModelEditing?: boolean; courseModelBusy?: boolean; courseModelConflict?: boolean; courseModelServerError?: string; courseModelServerIssues?: CourseModelValidationIssue[]; courseModelPreview?: CourseModelPreview | null; onStartCourseModelEdit?: () => void; onCancelCourseModelEdit?: () => void; onPreviewCourseModel?: (operations: CourseModelOperation[]) => void; onSaveCourseModel?: (operations: CourseModelOperation[], impactChecksum: string) => void; onInvalidateCourseModelPreview?: () => void; onRecoverCourseModelConflict?: (choice: "reapply" | "discard") => void; onCourseModelDirtyChange?: (dirty: boolean) => void; blueprintEditing?: boolean; blueprintBusy?: boolean; blueprintConflict?: boolean; blueprintServerError?: string; onStartBlueprintEdit?: () => void; onCancelBlueprintEdit?: () => void; onSaveBlueprint?: (decision: BlueprintDecisionDraft) => void; onRecoverBlueprintConflict?: (choice: "reapply" | "discard") => void; onBlueprintDirtyChange?: (dirty: boolean) => void; lessonPlanEditing?: boolean; lessonPlanBusy?: boolean; lessonPlanConflict?: boolean; lessonPlanServerError?: string; onStartLessonPlanEdit?: () => void; onCancelLessonPlanEdit?: () => void; onSaveLessonPlan?: (decision: LessonPlanDecisionDraft) => void; onRecoverLessonPlanConflict?: (choice: "reapply" | "discard") => void; onLessonPlanDirtyChange?: (dirty: boolean) => void; briefQuestionRound?: BriefQuestionRoundData; briefQuestionsLoading?: boolean; briefQuestionsBusy?: boolean; briefQuestionsError?: string; onRetryBriefQuestions?: () => void; onSubmitBriefQuestions?: (answers: BriefQuestionAnswer[]) => void }) {
  switch (stage) {
    case "brief": return <BriefView workspace={workspace} onEdit={onEditBrief} questionRound={briefQuestionRound} questionsLoading={briefQuestionsLoading} questionsBusy={briefQuestionsBusy} questionsError={briefQuestionsError} onRetryQuestions={onRetryBriefQuestions} onSubmitQuestions={onSubmitBriefQuestions} />;
    case "outcomes": return <OutcomesView workspace={workspace} editing={outcomesEditing} busy={outcomesBusy} conflict={outcomesConflict} serverError={outcomesServerError} serverIssues={outcomesServerIssues} onStartEdit={onStartOutcomesEdit} onCancel={onCancelOutcomesEdit} onSave={onSaveOutcomes} onResolveConflict={onResolveOutcomesConflict} onDirtyChange={onOutcomesDirtyChange} onRequestRevision={onRequestRevision} />;
    case "research": return <ResearchView workspace={workspace} onSourceDecision={onSourceDecision} onAddKnownSource={onAddKnownSource} sourceMutationBusy={sourceMutationBusy} />;
    case "course-model": return <CourseModelView workspace={workspace} editing={courseModelEditing} busy={courseModelBusy} conflict={courseModelConflict} serverError={courseModelServerError} serverIssues={courseModelServerIssues} preview={courseModelPreview} onStartEdit={onStartCourseModelEdit} onCancel={onCancelCourseModelEdit} onPreview={onPreviewCourseModel} onSave={onSaveCourseModel} onInvalidatePreview={onInvalidateCourseModelPreview} onRecoverConflict={onRecoverCourseModelConflict} onDirtyChange={onCourseModelDirtyChange} onRequestRevision={onRequestRevision} />;
    case "blueprint": return <BlueprintView workspace={workspace} editing={blueprintEditing} busy={blueprintBusy} conflict={blueprintConflict} serverError={blueprintServerError} onStartEdit={onStartBlueprintEdit} onCancel={onCancelBlueprintEdit} onSave={onSaveBlueprint} onRecoverConflict={onRecoverBlueprintConflict} onDirtyChange={onBlueprintDirtyChange} onRequestRevision={onRequestRevision} />;
    case "content": return <ContentView workspace={workspace} initialAssetId={initialAssetId} canReview={contentCapabilities?.review ?? false} canRevise={contentCapabilities?.revise ?? false} canContentRepair={contentCapabilities?.contentRepair ?? false} canRepair={contentCapabilities?.repair ?? false} repairUnavailableReason={contentCapabilities?.repairUnavailableReason} repairBusy={sourceRepairBusy ?? false} onContentAction={onContentAction} onRepairDecision={onSourceRepairDecision} onRepairRoute={onSourceRepairRoute} onContentRepair={onContentRepair} />;
    case "lesson-plan": return <LessonPlanView workspace={workspace} editing={lessonPlanEditing} busy={lessonPlanBusy} conflict={lessonPlanConflict} serverError={lessonPlanServerError} onStartEdit={onStartLessonPlanEdit} onCancel={onCancelLessonPlanEdit} onSave={onSaveLessonPlan} onRecoverConflict={onRecoverLessonPlanConflict} onDirtyChange={onLessonPlanDirtyChange} onRequestRevision={onRequestRevision} />;
    case "package": return <PackageView workspace={workspace} onNavigate={onNavigate} />;
  }
}

export function stageData(stage: StageSlug, workspace: Workspace): unknown {
  switch (stage) {
    case "brief": return workspace.brief;
    case "outcomes": return workspace.outcomes;
    case "research": return workspace.research;
    case "course-model": return workspace.modules;
    case "blueprint": return workspace.blueprint;
    case "content": return workspace.content;
    case "lesson-plan": return workspace.lessonPlan;
    case "package": return workspace.package;
  }
}
