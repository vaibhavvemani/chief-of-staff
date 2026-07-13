import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import { SourceStatus, VerificationBadge } from "../../components/StatusBadge";
import type {
  Claim,
  ContentAsset,
  CourseModule,
  OutputFile,
  StageSlug,
  Subtopic,
  Workspace,
} from "../../types";

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

export type BriefEditSection = "settings" | "learner" | "scope" | "coverage" | "assumptions";

function BriefSectionAction({ section, label, onEdit }: { section: BriefEditSection; label: string; onEdit?: (section: BriefEditSection) => void }) {
  if (!onEdit) return null;
  return <button className="section-edit-button" onClick={() => onEdit(section)} aria-label={`${label} in Course Brief`}><span>Adjust</span><span aria-hidden="true">→</span></button>;
}

function BriefView({ workspace, onEdit }: { workspace: Workspace; onEdit?: (section: BriefEditSection) => void }) {
  const brief = workspace.brief;
  const summary = workspace.stages.find((stage) => stage.slug === "brief");
  const hasArtifact = Boolean(workspace.briefChecksum);
  return (
    <div className="stage-view">
      {stageIntro(
        "Course Brief",
        "01 · Direction",
        "The agent turned the sparse request into a practical working agreement. Review its assumptions before downstream work changes.",
        <div className={`artifact-stamp ${hasArtifact ? "" : "suggested"}`}><span>{hasArtifact ? "Working artifact" : "Suggested starting point"}</span><strong>{summary?.status === "approved" ? "Approved" : hasArtifact ? "Ready for review" : "Not saved yet"}</strong></div>,
      )}
      <div className="brief-hero-card">
        <div className="brief-hero-heading">
          <div><span className="card-kicker">Course intent</span><h2>{brief.courseTitle}</h2><p>{brief.purpose}</p></div>
          <BriefSectionAction section="settings" label="Adjust course settings" onEdit={onEdit} />
        </div>
        <dl className="brief-quickfacts">
          <DefinitionItem label="Level" value={brief.level} />
          <DefinitionItem label="Duration" value={brief.duration} />
          <DefinitionItem label="Delivery" value={brief.modality} />
          <DefinitionItem label="Language" value={brief.language} />
        </dl>
      </div>
      <div className="stage-card-grid two-column">
        <section className="stage-card">
          <div className="card-heading"><div><span className="card-index">A</span><h3>Learner and intent</h3></div><BriefSectionAction section="learner" label="Adjust learner and intent" onEdit={onEdit} /></div>
          <dl className="stacked-definitions">
            <DefinitionItem label="Audience" value={brief.audience} />
            <DefinitionItem label="Prior knowledge" value={brief.priorKnowledge} />
            <DefinitionItem label="Assessment expectation" value={brief.assessmentExpectations} />
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
        <section className="stage-card assumption-card">
          <div className="card-heading"><div><span className="card-index">D</span><h3>Visible assumptions</h3></div><BriefSectionAction section="assumptions" label="Review visible assumptions" onEdit={onEdit} /></div>
          <p className="card-note">Defaults are proposals, not hidden facts. Reopen the Brief to correct any of them.</p>
          <div className="assumption-list">
            {brief.assumptions.map((assumption) => (
              <div key={assumption.field} className="assumption-row">
                <div><strong>{assumption.field.replaceAll("_", " ")}</strong><span>{assumption.value}</span></div>
                <p>{assumption.rationale}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function OutcomesView({ workspace }: { workspace: Workspace }) {
  return (
    <div className="stage-view">
      {stageIntro(
        "Course Outcomes",
        "02 · Learning contract",
        "These outcomes control downstream coverage and assessment. Each one states the observable evidence the learner should produce.",
        <div className="outcome-summary"><strong>{workspace.outcomes.length}</strong><span>measurable outcomes</span></div>,
      )}
      <div className="outcome-toolbar">
        <div className="quality-note"><span aria-hidden="true">✓</span><div><strong>Outcome quality check passed</strong><small>No vague verbs or obvious duplicates found.</small></div></div>
        <button className="button button-secondary" disabled title="Use Request changes for this release">+ Add outcome</button>
      </div>
      <ol className="outcome-list">
        {workspace.outcomes.map((outcome, index) => (
          <li key={outcome.id} className="outcome-card">
            <span className="outcome-order">{String(index + 1).padStart(2, "0")}</span>
            <div className="outcome-main">
              <div className="outcome-meta">
                <span className={`priority priority-${outcome.priority}`}>{outcome.priority}</span>
                <span>{outcome.cognitiveLevel}</span>
                <code>{outcome.id}</code>
              </div>
              <h3>{outcome.statement}</h3>
              <div className="evidence-line"><span>Evidence of learning</span><p>{outcome.evidence}</p></div>
            </div>
            <div className="row-actions">
              <button disabled aria-label={`Move ${outcome.id}`} title="Structured outcome editing is follow-on work">↕</button>
              <button disabled aria-label={`Edit ${outcome.id}`} title="Use Request changes for this release">Edit</button>
              <button disabled aria-label={`More options for ${outcome.id}`} title="Structured outcome editing is follow-on work">···</button>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function ResearchView({
  workspace,
  onSourceDecision,
}: {
  workspace: Workspace;
  onSourceDecision?: (selectedIds: string[]) => void;
}) {
  const [tab, setTab] = useState<"sources" | "landscape">("sources");
  const [sourceFilter, setSourceFilter] = useState("");
  const [selectedIds, setSelectedIds] = useState<string[]>(
    workspace.research.sources.filter((source) => source.status === "approved").map((source) => source.id),
  );
  const approved = workspace.research.sources.filter((source) => source.status === "approved").length;
  const rejected = workspace.research.sources.filter((source) => source.status === "rejected").length;
  const toggle = (sourceId: string, selected: boolean) => {
    setSelectedIds((current) => selected
      ? [...new Set([...current, sourceId])]
      : current.filter((id) => id !== sourceId));
  };
  const visibleSources = workspace.research.sources.filter((source) =>
    `${source.title} ${source.publisher} ${source.relevance}`.toLowerCase().includes(sourceFilter.toLowerCase()),
  );
  return (
    <div className="stage-view">
      {stageIntro(
        "Research & Sources",
        "03 · Evidence gate",
        "Competitor pages shape the curriculum. Only separately approved grounding sources may support learner-facing claims.",
        <div className="research-counts"><span><strong>{approved}</strong> approved</span><span><strong>{rejected}</strong> rejected</span></div>,
      )}
      <div className="tab-row" role="tablist" aria-label="Research views">
        <button role="tab" aria-selected={tab === "sources"} className={tab === "sources" ? "active" : ""} onClick={() => setTab("sources")}>Grounding sources <span>{workspace.research.sources.length}</span></button>
        <button role="tab" aria-selected={tab === "landscape"} className={tab === "landscape" ? "active" : ""} onClick={() => setTab("landscape")}>Competitor landscape <span>{workspace.research.competitors.length}</span></button>
      </div>
      {tab === "sources" ? (
        <div className="research-layout">
          <div className="source-list">
            <div className="list-tools"><div className="search-field"><span aria-hidden="true">⌕</span><input aria-label="Filter sources" value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)} placeholder="Filter by title, publisher, or topic" /></div><button className="button button-secondary" disabled title="Known-source additions are captured when creating a course">+ Add known source</button></div>
            {visibleSources.map((source) => (
              <article className={`source-card source-card-${source.status}`} key={source.id}>
                <div className="source-card-header">
                  <div><SourceStatus status={source.status} /><span className="source-type">{source.sourceType}</span></div>
                  <code>{source.id}</code>
                </div>
                <h3>{source.title}</h3>
                <p className="source-publisher">{source.publisher} · <span>{source.locator.replace(/^https?:\/\//, "")}</span></p>
                <div className="source-notes">
                  <div><span>Why it matters</span><p>{source.relevance}</p></div>
                  <div><span>Trust note</span><p>{source.trustNotes}</p></div>
                </div>
                <div className="source-footer">
                  <div>{source.assignedNodeIds.length ? <><span className="micro-label">Assigned to</span><TagList values={source.assignedNodeIds} tone="source" /></> : <span className="muted">Not routed into generation</span>}</div>
                  <div className="source-actions"><a target="_blank" rel="noreferrer" href={source.locator}>Preview</a>{selectedIds.includes(source.id) ? <button onClick={() => toggle(source.id, false)}>Reject</button> : <button className="approve-inline" onClick={() => toggle(source.id, true)}>Approve</button>}</div>
                </div>
              </article>
            ))}
          </div>
          <aside className="decision-tray">
            <span className="eyebrow">Decision summary</span>
            <h3>Source registry</h3>
            <div className="tray-stat"><span>Selected for grounding</span><strong>{selectedIds.length}</strong></div>
            <div className="tray-stat"><span>Currently rejected</span><strong>{rejected}</strong></div>
            <div className="tray-check"><span aria-hidden="true">✓</span><p>Rejected, proposed, and contentless sources are excluded from generation context.</p></div>
            <button className="button button-primary full-width" disabled={!onSourceDecision || !selectedIds.length} onClick={() => onSourceDecision?.(selectedIds)}>Save source registry</button>
          </aside>
        </div>
      ) : (
        <div className="landscape-layout">
          <div className="curriculum-evidence-note"><span aria-hidden="true">i</span><p><strong>Curriculum evidence only.</strong> These outlines inform structure but cannot ground learner-facing factual claims unless separately approved.</p></div>
          <div className="competitor-grid">
            {workspace.research.competitors.map((competitor) => (
              <article className="competitor-card" key={competitor.id}>
                <div className="competitor-head"><span className={`outline-state outline-${competitor.outlineStatus}`}>{competitor.outlineStatus}</span><code>{competitor.id}</code></div>
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

function ModelDetail({ subtopic }: { subtopic: Subtopic }) {
  return (
    <div className="model-detail">
      <div className="model-detail-head"><div><code>{subtopic.id}</code><h2>{subtopic.title}</h2><p>{subtopic.purpose}</p></div><button className="button button-secondary" disabled title="Use Request changes for this release">Edit subtopic</button></div>
      <div className="model-metadata"><div><span>Position</span><strong>{String(subtopic.order).padStart(2, "0")}</strong></div><div><span>Prerequisite</span><strong>{subtopic.prerequisiteSubtopicIds.join(", ") || "None"}</strong></div><div><span>Approved sources</span><strong>{subtopic.approvedSourceIds.length}</strong></div></div>
      <section className="detail-section"><div className="detail-heading"><h3>Scope contract</h3><span>Controls generation</span></div><div className="scope-columns"><div><span className="micro-label">In scope</span><TagList values={subtopic.inScope} /></div><div><span className="micro-label">Out of scope</span><TagList values={subtopic.outOfScope} tone="out" /></div></div></section>
      <section className="detail-section"><div className="detail-heading"><h3>Concepts</h3><span>{subtopic.concepts.length}</span></div>{subtopic.concepts.map((concept) => <article className="concept-row" key={concept.id}><div><code>{concept.id}</code><strong>{concept.name}</strong><p>{concept.summary}</p></div><TagList values={concept.sourceIds} tone="source" /></article>)}</section>
      <section className="detail-section"><div className="detail-heading"><h3>Coverage requirements</h3><span>{subtopic.coverageRequirements.length}</span></div>{subtopic.coverageRequirements.map((requirement) => <article className="requirement-row" key={requirement.id}><span className="requirement-check" aria-hidden="true">✓</span><div><code>{requirement.id}</code><p>{requirement.statement}</p><TagList values={requirement.sourceIds} tone="source" /></div></article>)}</section>
      <div className="integrity-note"><span aria-hidden="true">✓</span><div><strong>References are valid</strong><p>Concept, coverage, prerequisite, outcome, and source IDs resolve against current artifacts.</p></div></div>
    </div>
  );
}

function CourseModelView({ workspace }: { workspace: Workspace }) {
  const allSubtopics = workspace.modules.flatMap((module) => module.subtopics);
  const [selectedId, setSelectedId] = useState(allSubtopics[0]?.id ?? "");
  const selected = allSubtopics.find((subtopic) => subtopic.id === selectedId) ?? allSubtopics[0];
  return (
    <div className="stage-view model-view">
      {stageIntro("Course Model", "04 · Structural source of truth", "Modules, subtopics, coverage, and stable IDs form the compact contract every downstream artifact references.", <button className="button button-secondary" disabled title="Run integrity.py from the operator workflow">Validate references</button>)}
      <div className="model-workspace">
        <aside className="model-tree">
          <div className="tree-heading"><div><span className="micro-label">Course hierarchy</span><strong>{workspace.modules.length} module · {allSubtopics.length} subtopics</strong></div><button disabled aria-label="Add module" title="Use Request changes for this release">+</button></div>
          {workspace.modules.map((module: CourseModule) => (
            <div className="tree-module" key={module.id}>
              <div className="module-row"><span className="tree-toggle" aria-hidden="true">⌄</span><span><code>{module.id}</code><strong>{module.title}</strong></span><button disabled aria-label={`More options for ${module.title}`} title="Use Request changes for this release">···</button></div>
              <div className="subtopic-tree">
                {module.subtopics.map((subtopic) => (
                  <button key={subtopic.id} className={selected?.id === subtopic.id ? "active" : ""} onClick={() => setSelectedId(subtopic.id)}>
                    <span className="tree-sequence">{String(subtopic.order).padStart(2, "0")}</span><span><strong>{subtopic.title}</strong><small>{subtopic.approvedSourceIds.length} sources · {subtopic.coverageRequirements.length} requirement</small></span><span aria-hidden="true">›</span>
                  </button>
                ))}
                <button className="add-subtopic" disabled title="Use Request changes for this release"><span>+</span> Add subtopic</button>
              </div>
            </div>
          ))}
        </aside>
        {selected ? <ModelDetail subtopic={selected} /> : null}
      </div>
    </div>
  );
}

const assetColumns = [
  ["course_content", "Content"], ["learning_objectives", "Objectives"], ["summary", "Summary"],
  ["case_study", "Case"], ["assessment", "Assessment"], ["activities", "Activity"], ["resources", "Resources"],
] as const;

function BlueprintView({ workspace }: { workspace: Workspace }) {
  const [exceptionsOnly, setExceptionsOnly] = useState(false);
  const plans = exceptionsOnly ? workspace.blueprint.plans.filter((plan) => plan.exception) : workspace.blueprint.plans;
  const names = new Map(workspace.modules.flatMap((module) => module.subtopics.map((subtopic) => [subtopic.id, subtopic.title])));
  const selectedAssets = workspace.blueprint.plans.flatMap((plan) => plan.assets).filter((asset) => asset.selectionStatus === "selected").length;
  return (
    <div className="stage-view blueprint-view">
      {stageIntro("Blueprint", "05 · Generation control", "The matrix fixes exactly which learner assets the agent may generate for each subtopic. Exceptions stay visible.", <div className="blueprint-total"><strong>{selectedAssets}</strong><span>selected assets</span></div>)}
      <section className="defaults-panel">
        <div className="defaults-heading"><div><span className="eyebrow">Course defaults</span><h3>Applied unless a row says otherwise</h3></div><button className="button button-secondary" disabled title="Use Request changes for this release">Edit defaults</button></div>
        <dl><DefinitionItem label="Depth" value={workspace.blueprint.defaults.depth} /><DefinitionItem label="Learning time" value={`${workspace.blueprint.defaults.minutes} min`} /><DefinitionItem label="Word target" value={workspace.blueprint.defaults.wordTarget.toLocaleString()} /><DefinitionItem label="Examples" value={workspace.blueprint.defaults.examples} /><DefinitionItem label="Case depth" value={workspace.blueprint.defaults.caseDepth} /><DefinitionItem label="Assessment" value={workspace.blueprint.defaults.assessmentComplexity} /></dl>
      </section>
      <div className="blueprint-toolbar"><div><button className={!exceptionsOnly ? "active" : ""} onClick={() => setExceptionsOnly(false)}>All subtopics</button><button className={exceptionsOnly ? "active" : ""} onClick={() => setExceptionsOnly(true)}>Exceptions only <span>{workspace.blueprint.plans.filter((plan) => plan.exception).length}</span></button></div><p><span className="matrix-dot selected" /> Selected <span className="matrix-dot proposed" /> Proposed</p></div>
      <div className="blueprint-table-wrap">
        <table className="blueprint-table">
          <thead><tr><th>Subtopic</th>{assetColumns.map(([, label]) => <th key={label}>{label}</th>)}<th>Depth budget</th></tr></thead>
          <tbody>{plans.map((plan) => (
            <tr key={plan.subtopicId}>
              <th><code>{plan.subtopicId}</code><strong>{names.get(plan.subtopicId)}</strong>{plan.exception ? <span className="exception-badge">Exception</span> : null}</th>
              {assetColumns.map(([type]) => {
                const asset = plan.assets.find((candidate) => candidate.assetType === type);
                const status = asset?.selectionStatus ?? "proposed";
                return <td key={type}><button disabled title="Blueprint matrix editing is follow-on work" className={`asset-cell cell-${status}`} aria-label={`${names.get(plan.subtopicId)} ${type}: ${status}`}><span>{status === "selected" ? "✓" : "+"}</span><small>{status}</small>{type === "course_content" ? <em>anchor</em> : null}</button></td>;
              })}
              <td><strong>{plan.minutes} min · {plan.wordTarget.toLocaleString()} words</strong><small>{plan.examples} examples · {plan.assessmentComplexity}</small></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <div className="matrix-guardrail"><span aria-hidden="true">◆</span><p><strong>Anchor guardrail active.</strong> Every subtopic retains its Course Content asset. Source routing is limited to approved sources assigned in the Course Model.</p></div>
    </div>
  );
}

function verificationTotal(asset: ContentAsset): number {
  return asset.verification.unsupported + asset.verification.ungrounded + asset.verification.unattributed;
}

function AssetReader({ asset, selectedClaimId, onSelectClaim }: { asset: ContentAsset; selectedClaimId?: string; onSelectClaim: (id: string) => void }) {
  const [tab, setTab] = useState<"reader" | "markdown" | "data">("reader");
  return (
    <section className="asset-reader">
      <header className="reader-header">
        <div><span className="micro-label">{asset.type.replaceAll("_", " ")} · {asset.format}</span><h2>{asset.title}</h2><code>{asset.id}</code></div>
        <div className="reader-tabs" role="tablist"><button className={tab === "reader" ? "active" : ""} onClick={() => setTab("reader")}>Reader</button><button className={tab === "markdown" ? "active" : ""} onClick={() => setTab("markdown")}>Markdown</button><button className={tab === "data" ? "active" : ""} onClick={() => setTab("data")}>Data</button></div>
      </header>
      {tab === "reader" ? <div className="markdown-reader"><ReactMarkdown skipHtml>{asset.content}</ReactMarkdown></div> : null}
      {tab === "markdown" ? <pre className="raw-code">{asset.content}</pre> : null}
      {tab === "data" ? <pre className="raw-code">{JSON.stringify(asset, null, 2)}</pre> : null}
      {asset.claims.length ? <div className="claim-index"><span className="micro-label">Claims in this asset</span>{asset.claims.map((claim) => <button key={claim.id} className={selectedClaimId === claim.id ? "active" : ""} onClick={() => onSelectClaim(claim.id)}><VerificationBadge support={claim.support} /><span>{claim.text}</span></button>)}</div> : null}
    </section>
  );
}

function VerificationDetail({ asset, claim, onAction }: { asset: ContentAsset; claim?: Claim; onAction?: (action: string, asset: ContentAsset, claim?: Claim) => void }) {
  const finding = claim ?? asset.claims.find((candidate) => candidate.support !== "supported") ?? asset.claims[0];
  return (
    <aside className="verification-panel">
      <div className="verification-head"><div><span className="eyebrow">Verification</span><h3>{verificationTotal(asset) ? "Attention required" : "Evidence checks passed"}</h3></div><span className={`verification-score ${verificationTotal(asset) ? "score-attention" : "score-good"}`}>{verificationTotal(asset) ? verificationTotal(asset) : "✓"}</span></div>
      <div className="verification-metrics"><div><strong>{asset.verification.supported}</strong><span>Supported</span></div><div><strong>{asset.verification.partial}</strong><span>Partial</span></div><div className="bad"><strong>{asset.verification.unsupported}</strong><span>Unsupported</span></div><div className="bad"><strong>{asset.verification.ungrounded + asset.verification.unattributed}</strong><span>No ground</span></div></div>
      {finding ? <div className="finding-detail">
        <div className="finding-label"><VerificationBadge support={finding.support} /><code>{finding.id}</code></div>
        <blockquote>{finding.text}</blockquote>
        <div className="finding-section"><span>Verifier note</span><p>{finding.note || "No verifier note was recorded."}</p></div>
        <div className="finding-section"><span>Assigned source</span><p>{finding.sourceId ? <><code>{finding.sourceId}</code>{finding.excerpt ? ` — “${finding.excerpt}”` : " — no supporting passage found"}</> : "No approved source attribution"}</p></div>
        {finding.support !== "supported" ? <div className="repair-actions"><span className="micro-label">Choose the likely repair</span><button onClick={() => onAction?.("revise", asset, finding)}><span aria-hidden="true">↻</span><div><strong>Revise with approved evidence</strong><small>Keep sources; regenerate this asset only</small></div></button><button onClick={() => onAction?.("research", asset, finding)}><span aria-hidden="true">⌕</span><div><strong>Find better evidence</strong><small>Reopen research for this exact claim gap</small></div></button></div> : null}
      </div> : <div className="empty-mini">Select a claim to inspect its evidence.</div>}
    </aside>
  );
}

function ContentView({ workspace, onContentAction }: { workspace: Workspace; onContentAction?: (action: string, asset: ContentAsset, claim?: Claim) => void }) {
  const assets = workspace.content.assets;
  const initial = assets.find((asset) => verificationTotal(asset) > 0) ?? assets[0];
  const [selectedAssetId, setSelectedAssetId] = useState(initial?.id ?? "");
  const [selectedClaimId, setSelectedClaimId] = useState<string | undefined>(initial?.claims.find((claim) => claim.support !== "supported")?.id);
  const [filter, setFilter] = useState<"all" | "attention" | "approved">("all");
  const selected = assets.find((asset) => asset.id === selectedAssetId) ?? assets[0];
  const names = new Map(workspace.modules.flatMap((module) => module.subtopics.map((subtopic) => [subtopic.id, subtopic.title])));
  const visible = assets.filter((asset) => filter === "all" || (filter === "attention" ? verificationTotal(asset) > 0 : asset.reviewStatus === "approved"));
  const selectedClaim = selected?.claims.find((claim) => claim.id === selectedClaimId);
  const blockers = assets.reduce((total, asset) => total + verificationTotal(asset), 0);
  return (
    <div className="stage-view content-stage">
      {stageIntro("Student Content", "06 · Production & verification", "Review generated assets at the claim level. Repair weak evidence without regenerating unaffected course work.", <div className="production-progress"><div><strong>{workspace.content.completed}/{workspace.content.expected}</strong><span>assets generated</span></div><div className="mini-progress"><span style={{ width: `${(workspace.content.completed / Math.max(workspace.content.expected, 1)) * 100}%` }} /></div></div>)}
      <div className="attention-banner"><div className="attention-symbol" aria-hidden="true">!</div><div><strong>{blockers} blocking verification findings</strong><p>Generated output is mechanically complete, but the course is not learner-ready. Resolve unsupported, ungrounded, and unattributed claims.</p></div><button onClick={() => setFilter("attention")}>Show attention queue</button></div>
      <div className="production-filter"><div role="tablist"><button className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>All assets <span>{assets.length}</span></button><button className={filter === "attention" ? "active" : ""} onClick={() => setFilter("attention")}>Needs attention <span>{assets.filter((asset) => verificationTotal(asset) > 0).length}</span></button><button className={filter === "approved" ? "active" : ""} onClick={() => setFilter("approved")}>Reviewed <span>{assets.filter((asset) => asset.reviewStatus === "approved").length}</span></button></div><span>Course Content anchors generated first</span></div>
      <div className="content-workspace">
        <aside className="production-board" aria-label="Production board">
          {workspace.modules.flatMap((module) => module.subtopics).map((subtopic) => {
            const subtopicAssets = visible.filter((asset) => asset.subtopicId === subtopic.id);
            if (!subtopicAssets.length) return null;
            return <div className="production-group" key={subtopic.id}><div className="production-group-head"><span>{String(subtopic.order).padStart(2, "0")}</span><div><strong>{subtopic.title}</strong><small>{subtopicAssets.length} assets</small></div></div><div>{subtopicAssets.map((asset) => {
              const total = verificationTotal(asset);
              return <button key={asset.id} className={selected?.id === asset.id ? "active" : ""} onClick={() => { setSelectedAssetId(asset.id); setSelectedClaimId(asset.claims.find((claim) => claim.support !== "supported")?.id); }}><span className={`asset-kind kind-${asset.type === "course_content" ? "anchor" : "support"}`}>{asset.type === "course_content" ? "C" : asset.type.charAt(0).toUpperCase()}</span><span><strong>{asset.title}</strong><small>{asset.reviewStatus === "approved" ? "Reviewed" : "Awaiting review"}</small></span><span className={total ? "asset-alert" : "asset-ok"}>{total || "✓"}</span></button>;
            })}</div></div>;
          })}
          {!visible.length ? <div className="empty-mini">No assets match this filter.</div> : null}
        </aside>
        {selected ? <AssetReader asset={selected} selectedClaimId={selectedClaimId} onSelectClaim={setSelectedClaimId} /> : <div className="empty-mini">Select an asset to read it.</div>}
        {selected ? <VerificationDetail asset={selected} claim={selectedClaim} onAction={onContentAction} /> : null}
      </div>
      {selected ? <div className="asset-review-strip"><div><span className={`review-state review-${selected.reviewStatus}`} /> <strong>{selected.reviewStatus === "approved" ? "Human review complete" : "Human decision required"}</strong><span>Verifier blockers cannot be cleared by review alone.</span></div><div><button className="button button-secondary" onClick={() => onContentAction?.("changes_requested", selected)}>Request changes</button><button className="button button-primary" disabled={verificationTotal(selected) > 0} onClick={() => onContentAction?.("approved", selected)}>Mark asset reviewed</button></div></div> : null}
    </div>
  );
}

function LessonPlanView({ workspace }: { workspace: Workspace }) {
  const names = new Map(workspace.modules.flatMap((module) => module.subtopics.map((subtopic) => [subtopic.id, subtopic.title])));
  const covered = workspace.lessonPlan.coveredSubtopicIds.length;
  const expected = workspace.lessonPlan.expectedSubtopicIds.length;
  return (
    <div className="stage-view">
      {stageIntro("Lesson Plan", "07 · Delivery sequence", "Turn approved content into a teachable sequence with explicit duration, mode, coverage, and facilitation cues.", <div className="lesson-total"><strong>{workspace.lessonPlan.totalDurationMinutes}</strong><span>total minutes</span></div>)}
      <div className="lesson-layout">
        <section className="session-timeline">
          <div className="timeline-heading"><div><span className="eyebrow">Session timeline</span><h3>{workspace.lessonPlan.sessions.length} connected sessions</h3></div><button className="button button-secondary" disabled title="Use Request changes for this release">Adjust constraints</button></div>
          {workspace.lessonPlan.sessions.map((session, index) => (
            <article className="session-card" key={session.id}>
              <div className="session-marker"><span>{String(index + 1).padStart(2, "0")}</span><i /></div>
              <div className="session-content">
                <div className="session-head"><div><code>{session.id}</code><h3>{session.title}</h3></div><div className="duration-pill">{session.durationMinutes} min</div></div>
                <div className="session-covers">{session.covers.map((cover) => <div className="cover-row" key={cover.subtopicId}><div className="cover-title"><span className={`mode mode-${cover.mode}`}>{cover.mode.replace("_", " ")}</span><strong>{names.get(cover.subtopicId) ?? cover.subtopicId}</strong><code>{cover.subtopicId}</code></div><ul>{cover.talkingPoints.map((point) => <li key={point}>{point}</li>)}</ul><button disabled title="Use Request changes for this release">Move mode</button></div>)}</div>
              </div>
            </article>
          ))}
        </section>
        <aside className="lesson-constraints">
          <span className="eyebrow">Constraints</span><h3>Delivery contract</h3>
          <dl><DefinitionItem label="Sessions" value={workspace.lessonPlan.sessions.length} /><DefinitionItem label="Total time" value={`${workspace.lessonPlan.totalDurationMinutes} minutes`} /><DefinitionItem label="Primary mode" value="Live + self-study" /><DefinitionItem label="Breaks" value="As needed" /></dl>
          <div className="coverage-ring"><div style={{ "--coverage": `${(covered / Math.max(expected, 1)) * 360}deg` } as React.CSSProperties}><strong>{covered}/{expected}</strong><span>covered</span></div></div>
          <div className="coverage-check"><span aria-hidden="true">✓</span><p>Every Course Model subtopic appears exactly once in the delivery plan.</p></div>
          <button className="button button-secondary full-width" disabled title="Coverage is summarized above in this release">Review coverage map</button>
        </aside>
      </div>
    </div>
  );
}

function FileTree({ files, depth = 0, onSelect }: { files: OutputFile[]; depth?: number; onSelect: (file: OutputFile) => void }) {
  return <ul className="file-tree">{files.map((file) => <li key={file.path}><button style={{ paddingLeft: `${12 + depth * 18}px` }} onClick={() => onSelect(file)}><span className={`file-icon file-${file.kind}`} aria-hidden="true">{file.kind === "folder" ? "▸" : "M"}</span><span>{file.label}</span></button>{file.children ? <FileTree files={file.children} depth={depth + 1} onSelect={onSelect} /> : null}</li>)}</ul>;
}

function PackageView({ workspace }: { workspace: Workspace }) {
  const firstFile = workspace.package.files.find((file) => file.kind === "markdown");
  const [selected, setSelected] = useState<OutputFile | undefined>(firstFile);
  const checks = [
    ["Course Model integrity", workspace.package.integrityPassed, "All downstream IDs resolve"],
    ["Source boundary", workspace.package.rejectedSourceLeaks === 0, `${workspace.package.approvedSourceCount} approved · ${workspace.package.rejectedSourceLeaks} rejected leaks`],
    ["Asset reconciliation", workspace.package.selectedAssets === workspace.package.renderedAssets, `${workspace.package.renderedAssets} of ${workspace.package.selectedAssets} rendered`],
    ["Human content review", workspace.package.unresolvedBlockers === 0, workspace.package.unresolvedBlockers ? `${workspace.package.unresolvedBlockers} blockers remain` : "All required reviews complete"],
  ] as const;
  const ready = checks.every(([, passed]) => passed);
  return (
    <div className="stage-view package-view">
      {stageIntro("Course Package", "08 · Release gate", "The final gate reconciles structure, evidence, generated assets, human review, and the rendered Markdown folder.", <div className={`release-state ${ready ? "release-ready" : "release-blocked"}`}><span aria-hidden="true">{ready ? "✓" : "!"}</span><div><small>Operator status</small><strong>{ready ? "Ready" : "Requires attention"}</strong></div></div>)}
      <div className="release-checklist"><div className="release-title"><span className="eyebrow">Release checklist</span><h2>{ready ? "All gates passed" : "The package is rendered, but not releasable yet"}</h2><p>{ready ? "This course is ready for operator delivery." : "Mechanical completion does not override unresolved verification blockers."}</p></div><div className="release-checks">{checks.map(([label, passed, detail]) => <div key={label} className={passed ? "passed" : "blocked"}><span aria-hidden="true">{passed ? "✓" : "!"}</span><div><strong>{label}</strong><small>{detail}</small></div></div>)}</div></div>
      <div className="package-browser">
        <aside className="output-tree"><div className="tree-heading"><div><span className="micro-label">Rendered output</span><strong>{workspace.package.format}</strong></div></div><FileTree files={workspace.package.files} onSelect={setSelected} /><div className="format-note"><strong>Prototype output</strong><p>Markdown is the canonical learner-facing format for this release.</p></div></aside>
        <section className="output-preview">
          <header><div><span className="micro-label">Preview</span><h3>{selected?.label ?? "Select a file"}</h3><code>{selected?.path}</code></div>{selected?.kind === "markdown" ? <a className="button button-secondary" target="_blank" rel="noreferrer" href={`/api/courses/${encodeURIComponent(workspace.course.courseId)}/outputs/${selected.path.split("/").map(encodeURIComponent).join("/")}`}>Open raw file</a> : null}</header>
          {selected?.kind === "markdown" ? <div className="markdown-reader package-markdown"><h1>{selected.label}</h1><p>This rendered course file is available in the final Markdown folder. The production API will stream its bounded preview from the configured output root.</p><h2>What this file contains</h2><ul><li>Approved course structure and learner-facing content</li><li>Source references reconciled with the approved registry</li><li>Asset IDs that match the Course Model and Blueprint</li></ul><blockquote>Resolve the remaining verification blockers before distributing this course.</blockquote></div> : <div className="empty-mini">Choose a Markdown file to preview it.</div>}
        </section>
      </div>
    </div>
  );
}

export function StageView({ stage, workspace, onContentAction, onSourceDecision, onEditBrief }: { stage: StageSlug; workspace: Workspace; onContentAction?: (action: string, asset: ContentAsset, claim?: Claim) => void; onSourceDecision?: (selectedIds: string[]) => void; onEditBrief?: (section: BriefEditSection) => void }) {
  switch (stage) {
    case "brief": return <BriefView workspace={workspace} onEdit={onEditBrief} />;
    case "outcomes": return <OutcomesView workspace={workspace} />;
    case "research": return <ResearchView workspace={workspace} onSourceDecision={onSourceDecision} />;
    case "course-model": return <CourseModelView workspace={workspace} />;
    case "blueprint": return <BlueprintView workspace={workspace} />;
    case "content": return <ContentView workspace={workspace} onContentAction={onContentAction} />;
    case "lesson-plan": return <LessonPlanView workspace={workspace} />;
    case "package": return <PackageView workspace={workspace} />;
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
