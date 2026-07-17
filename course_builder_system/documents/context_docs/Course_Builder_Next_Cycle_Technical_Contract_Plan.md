# Course Builder — Next Cycle Technical Contract Plan

> **Status:** Implementation contract baseline  
> **Updated:** 2026-07-17
> **Purpose:** Lock the state, command, invalidation, repair, execution, and
> observability boundaries needed to implement the next development cycle  
> **Parent plan:** `Course_Builder_Next_Development_Cycle_Plan.md`

> **NC-30 contract update — 2026-07-17:** NC-301 and NC-302 have passed independent
> checkpoint review. NC-303 remains deferred to NC-90 behind NC-902. NC-40 has not
> started, and the next safe implementation action is NC-401. This does not complete
> Milestone 3 or the cycle.

## 1. How to use this document

The parent plan defines the product outcome and milestone order. This document defines
the technical behavior those milestones must share.

Use it before implementing:

- stage lifecycle changes;
- stage edit or revision commands;
- Brief question rounds;
- downstream-impact previews;
- source repair;
- targeted content repair;
- deterministic/live implementation selection;
- progress, activity, or cost diagnostics.

The contracts here are intentionally narrower than final request/response schemas. The
implementation may refine field names, but it must preserve the decisions and behavior
described here. If a change would alter a boundary in this document, update and review
the document before changing code.

## 2. Decisions locked for the cycle

1. Deterministic and live modes use the same product workflow and artifact contracts.
2. Stage state is derived by the backend projector, never inferred by React.
3. Approved artifacts require an explicit reopen before general editing.
4. Consequential changes receive an impact preview before mutation.
5. General upstream changes explicitly invalidate affected downstream artifacts.
6. Bounded evidence repair uses a dedicated repair workflow rather than broadly
   reopening Research.
7. Typed decisions are preferred over free-text revision.
8. A free-text revision must have a known stage, target, category, and implementation.
9. The backend enforces approval gates even if the UI is bypassed.
10. Human source approval, artifact approval, and content review remain authoritative.
11. Live model output is validated and reduced through deterministic domain logic.
12. Package rendering and integrity remain deterministic.
13. Safe diagnostics may expose provider/model/cost summaries, but never credentials,
    hidden reasoning, full prompts, or full source bodies.
14. No database, distributed queue, agent framework, or generic chat is introduced in
    this cycle.

## 3. Target stage state model

The target operator-facing states are:

| State | Meaning | Primary valid action |
|---|---|---|
| `locked` | Required upstream artifacts are not approved/current. | Go to the blocking stage. |
| `needs_input` | Human answers or a typed decision are required before an agent/proposal can run. | Answer questions or save the required decision. |
| `ready` | Inputs are approved/current and the stage can run. | Run stage. |
| `running` | A persisted job owns the course mutation lock. | Watch progress or wait. |
| `awaiting_review` | A complete draft exists and needs a human checkpoint. | Edit, request a supported revision, or approve. |
| `requires_attention` | A draft/current output has blockers or requested changes. | Resolve the specific attention items. |
| `approved` | The human checkpoint is recorded and the artifact is current. | Continue or explicitly reopen. |
| `stale` | The saved output is inspectable but one or more consumed inputs changed. | Rerun or perform an allowed targeted repair. |
| `failed` | The last stage job failed safely. | Inspect the safe error and retry. |

### 3.1 State-transition rules

```text
locked
  -> needs_input or ready

needs_input
  -> needs_input             while required answers remain
  -> ready or awaiting_review when required input is complete

ready
  -> running
  -> failed

running
  -> awaiting_review
  -> requires_attention
  -> failed

awaiting_review
  -> running                 supported revision
  -> approved                approval guards pass
  -> requires_attention      validation or review finds a blocker

requires_attention
  -> running                 revision or repair
  -> awaiting_review         blockers cleared but human approval remains

approved
  -> awaiting_review         explicit reopen, preserving the current body
  -> stale                   upstream consequential change

stale
  -> running
  -> failed

failed
  -> running                 safe retry
```

The implementation may project an explicitly reopened artifact as `awaiting_review`
even though its envelope status is `draft`. Reopen must not delete the current body.

### 3.2 Artifact lifecycle values

The artifact envelope remains owned by the orchestration/lifecycle layer. The cycle may
use these lifecycle status values:

- `draft`;
- `approved`;
- `stale`;
- `failed` only when a persisted artifact itself is invalid, not merely because its job
  failed.

Job failure normally remains runtime state. A failed job must not overwrite the last
valid artifact with an empty or failed body.

## 4. Explicit invalidation contract

Timestamp comparison alone is not sufficient for consequential browser mutations. The
Decision Service must use the `PipelineCatalog` dependency graph to mark affected
approved outputs stale when a general upstream change is committed.

### 4.1 General invalidation

Examples:

| Changed artifact | Normally affected |
|---|---|
| Brief | Outcomes, Research, Course Model, Blueprint, Content, Lesson Plan, Package |
| Outcomes | Research, Course Model, Blueprint where outcome-linked, Content, Lesson Plan, Package |
| Research source decision | Course Model, Blueprint, affected Content, Package |
| Course Model structure/scope | Blueprint, affected Content, Lesson Plan, Package |
| Blueprint asset/depth decision | affected Content, Lesson Plan where delivery changes, Package |
| Content asset | content review for that asset, Package; Lesson Plan only if its inputs/coverage changed |
| Lesson Plan | Package |

The dependency walker must derive actual downstream artifacts from the catalog and
declared step contracts rather than duplicating a second hardcoded pipeline order in
React.

### 4.2 Targeted invalidation

A bounded operation may produce a smaller impact than normal graph invalidation only
when a dedicated domain command proves that scope.

Allowed examples:

- revise one generated asset using unchanged approved evidence;
- add and route a source to one subtopic, then revise named assets;
- change a Lesson Plan constraint and regenerate named sessions;
- rerender Package files after content changed without changing course structure.

The command must return the exact impacted artifact types and record IDs. If the domain
cannot prove bounded impact, use normal downstream invalidation.

### 4.3 Stale artifacts

- Preserve stale artifact bodies for comparison and recovery.
- Do not allow a stale artifact to satisfy an approved prerequisite.
- Do not silently approve a regenerated stale artifact.
- Reapproval remains a human checkpoint.
- Activity should record why the artifact became stale.

## 5. Impact-preview contract

Every consequential command that may invalidate approved work should support a dry-run
impact preview.

### 5.1 Request

The conceptual request contains:

```json
{
  "action": "reopen | edit | revise | repair",
  "stage": "course-model",
  "target_type": "subtopic",
  "target_ids": ["m1_s2"],
  "operation_summary": "Change scope and source assignments",
  "expected_checksum": "..."
}
```

### 5.2 Response

The conceptual response contains:

```json
{
  "direct_artifacts": ["course_model"],
  "stale_artifacts": ["blueprint", "content_package", "lesson_plan", "render_manifest", "run_summary"],
  "targeted_assets": ["m1_s2_cc", "m1_s2_assess"],
  "preserved_assets": ["..."],
  "requires_rerun_stages": ["blueprint", "content", "lesson-plan", "package"],
  "warnings": ["Approved learner content will require review again."],
  "impact_level": "targeted | downstream | full"
}
```

The preview is advisory until the mutation is submitted. The mutation still checks the
expected checksum, recomputes impact under the course lock, and rejects stale previews.

## 6. Common command envelope

Every consequential mutation should include:

| Field | Purpose |
|---|---|
| `expected_checksum` | Prevent stale browser overwrites. |
| `reason` or `rationale` | Human-readable audit context where relevant. |
| `mode` | Required for commands that start work: `deterministic` or `live`. |
| `target_ids` | Bounded record scope where applicable. |
| `impact_acknowledged` | Confirms that the current impact preview was shown for destructive/downstream changes. |

Do not put UI tabs, dialog state, or local selections in canonical artifacts.

## 7. Stage capability matrix

The following matrix is the target capability boundary for this cycle.

| Stage | Human input | Direct edit | Typed decision | Scoped agent revision | Reopen | Dedicated repair | Approval gate |
|---|---:|---:|---:|---:|---:|---:|---:|
| Brief | Yes | Yes | Yes | Yes | Yes | No | Required answers resolved |
| Outcomes | No | Yes | Yes | Yes | Yes | No | At least one valid outcome |
| Research & Sources | Source decision | Add known URL | Yes | Bounded research | Yes | Source repair | Approved content-bearing source registry |
| Course Model | No | Yes | Yes | Yes | Yes | Source-route update | Integrity and approved-source references |
| Blueprint | Asset/depth decision | Yes | Yes | Yes | Yes | Targeted source/asset reroute | Exact valid per-subtopic plans |
| Student Content | Human review | No raw edit | Review decision | Yes | Yes | Content/evidence repair | No hard blockers; all reviews approved |
| Lesson Plan | Delivery constraints | Yes | Yes | Yes | Yes | Affected-session regeneration | Exact Course Model coverage |
| Package | Release decision | No | Retry/rerender | No | Yes | Return to blocking stage | All release checks pass |

Package should not present a generic “request changes” action. A Package problem must
route to the responsible stage or retry deterministic rendering.

The matrix is the target boundary for the full cycle, not a claim that every capability
is currently projected. Outcomes direct edit and typed decision are implemented through
NC-302. Outcomes scoped agent revision remains NC-303 and must not be projected before
its NC-90 implementation behind NC-902.

## 8. Brief intake contract

### 8.1 Draft representation

The Brief remains the canonical stage artifact. Its body should gain an intake section
that records completion without introducing browser-owned state.

Conceptual addition:

```json
{
  "intake_state": {
    "explicit_fields": ["audience", "purpose"],
    "accepted_default_fields": ["language"],
    "unresolved_required_fields": ["duration"],
    "answered_question_ids": ["brief_audience"],
    "last_gap_analysis": []
  }
}
```

The existing readable Brief fields remain the downstream contract. `intake_state` is
stage-specific body data, not an orchestrator field.

All Brief reads and mutations use one pure normalization boundary. It does not rewrite
stored historical artifacts: explicitly accepted historical defaults remain accepted,
assumed defaults on a historical draft remain unresolved, and approved pre-NC-20
snapshots are grandfathered for compatibility. API checksums continue to identify the
persisted artifact even when the returned read view is normalized.

### 8.2 Required fields

- subject, provided by the Subject Request;
- audience;
- desired practical result/purpose;
- prior knowledge;
- target level;
- duration;
- modality.

Language defaults visibly to English and must be explicitly accepted or changed.

### 8.3 Question API behavior

The API serializes the existing `QuestionSpec` fields. It returns only visible,
unresolved questions for the current draft and never lets the frontend duplicate
conditional logic.

Recommended command surface:

```text
GET  /api/courses/{course_id}/brief/questions
PUT  /api/courses/{course_id}/brief/answers
POST /api/courses/{course_id}/brief/clarifications/run
```

- Saving answers is synchronous and durable.
- A detailed creation request may atomically populate already-known Brief fields; a
  complete input set returns no redundant questions.
- Gap analysis is deterministic first.
- Live clarification may propose at most three additional validated questions.
- A live clarifier cannot invent artifact fields outside the allowed question set.
- The Brief projects `needs_input` while required fields remain unresolved.
- When required fields are resolved, it projects `awaiting_review`.
- Every later stage and typed decision derives its transitive dependency from the
  `PipelineCatalog` graph and requires the normalized Brief to be resolved and approved,
  including at the locked execution boundary.

## 9. Typed stage-decision contracts

### 9.1 Outcomes decision

The deterministic Outcomes reducer is the authoritative decision boundary used by the
API and React. The command supports selected IDs, bounded field edits, additions,
removals by omission after browser confirmation, and priority order. Strict request
models reject unknown command, edit, and addition fields.

The reducer validates the complete resulting collection atomically, not only individual
patches. It must reject:

- an empty or meaningless final collection;
- duplicate selected IDs, unknown selected IDs, duplicate final IDs, or any
  client-supplied canonical ID for an addition;
- edits to unknown IDs, unsupported editable fields, or any attempt to mutate an ID;
- invalid ID syntax outside `^[a-z0-9][a-z0-9_-]*$`;
- non-string, empty, whitespace-only, or longer-than-300-character statements or
  evidence;
- cognitive levels outside `remember`, `understand`, `apply`, `analyze`, `evaluate`, or
  `create`;
- priorities outside `core`, `supporting`, or `optional`;
- a malformed, ambiguous, scope-escaping, or no-op decision;
- a duplicate, unknown, removed, or incomplete nonempty priority order.

Statement and evidence whitespace is normalized before comparison and persistence.
Retained and edited Outcomes preserve their stable canonical IDs, and display reordering
never renumbers them. Clients cannot choose canonical IDs for additions. The backend
allocates deterministic collision-free canonical IDs and persists a monotonic
`next_outcome_id` cursor, so removing the highest-numbered Outcome does not permit that
ID to be reused later. React may assign a request-local client reference so a new row can
appear in the order before it has a canonical ID; the reducer resolves that reference
during the same atomic decision, and the reference never persists as an Outcome ID.

A nonempty `priority_order` claims to be the complete final order. It must contain each
retained canonical ID and each request-local addition reference exactly once. For
backward compatibility, an omitted or empty `priority_order` falls back deterministically
to `selected_ids` order followed by additions in request order. Removal remains omission
from `selected_ids`, with confirmation owned by the browser.

A valid meaningful decision saves a new draft; it never auto-approves. The canonical
response replaces local editor state and persists across refresh. Approval remains a
separate command guarded against an empty collection, duplicate IDs, invalid statements
or evidence, invalid cognitive levels or priorities, and invalid ordering. Failed
decision or approval validation leaves the previous valid artifact unchanged.

On a checksum conflict, the browser refetches the canonical artifact and performs a
three-way rebase. Nonoverlapping local edits, additions, and confirmed removals are
preserved; server additions are incorporated and server removals are not resurrected.
Overlapping field or order changes require an explicit operator choice before another
save. Unsaved Outcomes edits warn before browser unload or internal stage navigation.

Every Outcomes creation, edit, approval, and run remains behind the normalized Brief
readiness gate. Changing an existing artifact requires its expected checksum and occurs
under the per-course mutation lock. Read-only examples cannot be changed. An approved
Outcomes artifact exposes edit only after explicit Reopen and current impact
acknowledgement. The backend projector and capability service own those decisions;
React must not infer them. A meaningful saved change derives downstream invalidation
from `PipelineCatalog` and preserves stale artifact bodies.

The backend also returns structured nonblocking advisories tied to Outcome IDs for vague
or non-observable verbs, duplicate or near-duplicate statements, and missing or
mechanically weak evidence. These checks guide operator attention and do not claim to
judge final pedagogical quality.

### 9.2 Source decision

The human selects approved grounding sources. The reducer determines rejected IDs and
persists captured content. Candidate discovery never counts as approval.

Add separate commands for:

```text
POST /api/courses/{course_id}/research/known-sources
POST /api/courses/{course_id}/research/repairs
PUT  /api/courses/{course_id}/research/repairs/{repair_id}/decision
```

Known-source submission creates a proposed candidate until the human approves it.

### 9.3 Course Model decision

Use a batch of validated operations:

```json
{
  "operations": [
    {
      "op": "add | update | remove | move | reorder | assign_sources",
      "target_type": "module | subtopic | concept | coverage_requirement",
      "target_id": "m1_s2",
      "parent_id": "m1",
      "position": 2,
      "changes": {}
    }
  ],
  "expected_checksum": "...",
  "impact_acknowledged": true
}
```

The backend owns ID generation, operation order, integrity validation, and rollback on
failure. The whole batch succeeds or nothing is saved.

### 9.4 Blueprint decision

Keep the current reducer fields and add UI coverage for:

- selected asset types per subtopic;
- depth overrides;
- anchor waivers;
- rationale.

The reducer continues to reject unknown subtopics/assets, empty selections, and missing
anchor waivers.

### 9.5 Lesson Plan decision

Recommended shape:

```json
{
  "constraints": {
    "max_session_hours": 2,
    "default_mode": "live",
    "calendar_dates": [],
    "instructor_count": 1,
    "delivery_platform": null
  },
  "operations": [
    {
      "op": "set_mode | move_segment | reorder_session",
      "target_id": "m1_s2",
      "value": "self_study"
    }
  ],
  "expected_checksum": "..."
}
```

The backend regenerates/validates the affected plan and preserves exact subtopic
coverage.

## 10. Scoped revision contract

Free-text revision is a job command, not a generic message.

Conceptual shape:

```json
{
  "target_type": "outcome | subtopic | asset | session",
  "target_ids": ["m1_s2"],
  "category": "scope | structure | depth | clarity | evidence | sequence",
  "instruction": "...",
  "mode": "deterministic | live",
  "expected_checksum": "..."
}
```

Rules:

1. The stage must register a revision handler for the target type/category.
2. Unknown or ambiguous targets are rejected before starting a job.
3. The handler receives only the bounded target context and relevant constraints.
4. Output passes the same deterministic validator as a direct edit.
5. The job response identifies changed and preserved records.
6. A no-op revision is reported as a no-op, not presented as a successful change.
7. The revised artifact returns to human review.

## 11. Source-repair contract

### 11.1 Why this is separate from general Research reopening

Reopening Research broadly can stale the entire downstream course. A verifier evidence
gap usually needs a much smaller operation: find evidence for named claims, approve one
source, route it to named assets, and regenerate those assets.

### 11.2 Canonical support artifact

Add a `source_repair` canonical support artifact containing a repair ledger. It does not
replace the Research Dossier or approved source registry.

Each entry records:

- repair ID;
- originating subtopic, asset, claim, and finding IDs;
- evidence-gap description;
- requested mode;
- proposed candidate metadata and bounded previews;
- human source decision;
- approved source route;
- affected asset IDs;
- repair status;
- final verifier result.

Recommended entry states:

```text
requested
  -> researching
  -> awaiting_source_decision
  -> awaiting_route_confirmation
  -> regenerating
  -> awaiting_content_review
  -> resolved or failed
```

The ledger artifact is current canonical audit data. Individual entry state belongs in
its body; it is not an orchestrator stage status.

### 11.3 Repair transaction

After the human approves a candidate and confirms its route, one locked domain mutation
must:

1. capture/store the approved source body;
2. merge the approved source into the Research Dossier and registry;
3. assign the source to named Course Model subtopics/requirements;
4. assign the source to named Blueprint assets;
5. record exact targeted content impact;
6. leave unrelated structure and assets unchanged;
7. start or make ready the targeted content-repair job.

This human-confirmed transaction may keep the updated Research, Course Model, and
Blueprint artifacts approved because it applies an explicit typed source decision and
does not change structure or asset selection. It increments their revisions and records
the repair rationale.

If the requested repair requires scope, structure, outcome, or asset-selection changes,
the dedicated repair flow must stop and route the operator to normal stage reopening.

## 12. Content-repair contract

Two strategies are supported:

### 12.1 Revise with existing approved evidence

- target named assets and optional finding IDs;
- use only currently routed approved excerpts;
- regenerate named assets;
- reverify named assets;
- preserve all other assets byte-for-byte;
- reset review only for changed assets.

### 12.2 Find better evidence

- create a Source Repair entry;
- complete the source decision/route transaction;
- regenerate named assets with the new routed evidence;
- reverify and return to human review.

### 12.3 Completion rules

- Hard blocker counts come from current claim-level results.
- `partial` remains a human-review item, not a hard blocker.
- A changed asset cannot inherit its prior approved review decision.
- An unchanged asset preserves its review decision.
- Content and Package remain `requires_attention` while hard blockers remain.

## 13. Server-side approval guards

| Stage | Required guard |
|---|---|
| Brief | Mandatory fields resolved; accepted defaults recorded; no high-severity intake conflict. |
| Outcomes | At least one meaningful outcome; unique valid IDs; nonempty schema-bounded statements and evidence; valid cognitive levels and priorities; complete duplicate-free order. |
| Research | Dossier present; explicit source decision; at least one approved content-bearing source; no invalid selected IDs. |
| Course Model | Referential integrity passes; all source IDs are approved/content-bearing; outcome links resolve. |
| Blueprint | Every Course Model subtopic has one plan; selected assets are valid; anchor rule passes; source routes are approved. |
| Student Content | Selected/generated reconciliation passes; no failed/evidence-gap units; no hard verifier blockers; every asset review is approved. |
| Lesson Plan | Every generated subtopic appears exactly once in order unless an approved typed operation defines otherwise; constraints valid. |
| Package | Integrity passes; rejected-source leakage is zero; selected/generated/rendered assets reconcile; Content review complete; hard blockers zero. |

Approval failure returns structured guard failures so the UI can link to the exact
blocking stage, asset, source, or decision.

## 14. Deterministic/live execution contract

### 14.1 Stage implementation boundary

Keep `Step(name, consumes, produces, run)` as the pipeline contract. Pipeline factories
inject deterministic or live callables behind the same step definitions.

The existing `(inputs, feedback) -> produced artifacts` signature remains valid.
Provider/model services and progress callbacks should be captured by injected closures
or factories rather than added to artifact bodies.

Conceptual construction:

```text
build_pipeline(
    implementations=deterministic_implementations,
    progress_callback=event_adapter,
)

build_pipeline(
    implementations=live_implementations,
    progress_callback=event_adapter,
)
```

The API `StageRunner` passes its safe event adapter when resolving stage steps. The CLI
may pass a console/no-op adapter.

### 14.2 Required live implementations

| Stage | Live responsibility |
|---|---|
| Brief | Bounded gap proposal and optional structured Brief synthesis. |
| Outcomes | Structured measurable outcome proposal/revision. |
| Research | Search planning, bounded tool use, extraction, authority/fit evaluation. |
| Course Model | Structured hierarchy/coverage proposal and scoped revision. |
| Blueprint | Structured depth/asset proposal and scoped revision. |
| Student Content | Grounded per-asset generation and depth repair. |
| Verification | Independent claim/evidence checking. |
| Lesson Plan | Structured delivery proposal/revision under deterministic constraints. |
| Package | No live model call; deterministic reconciliation and rendering. |

### 14.3 Failure behavior

- Live failure does not silently substitute deterministic output.
- The last valid artifact remains on disk.
- The job records a safe error.
- The stage projects `failed` with a retry action.
- Switching to deterministic mode is an explicit operator choice.

## 15. Progress and activity contract

### 15.1 Safe event fields

Events may contain:

- event ID;
- job ID;
- course ID;
- stage;
- event type;
- timestamp;
- safe human-readable message;
- subtopic/asset/record ID;
- completed and expected counts;
- mode;
- provider and model identifier;
- input/output token totals;
- estimated cost;
- retry/attempt count;
- cache-hit flag;
- safe error type/message.

Events must not contain:

- API keys or credentials;
- hidden chain-of-thought/private reasoning;
- full prompts;
- full source bodies;
- learner content bodies unless the artifact endpoint already authorizes them.

### 15.2 Required event sequence

```text
job.queued
job.started
stage.started
unit.started       repeated where applicable
unit.completed     or unit.failed
stage.output_ready
checkpoint.awaiting_review
job.completed      or job.failed
```

Unit events must be emitted while generation is occurring, not reconstructed only after
the complete stage returns.

### 15.3 Activity projection

Activity reads persisted jobs/events and safe LLM-call summaries. It remains diagnostic
runtime state and does not become canonical course truth.

## 16. Backend/frontend ownership

### Backend owns

- stage state;
- prerequisite and approval guards;
- question visibility and validation;
- typed decision validation/reduction;
- stable IDs;
- impact calculation;
- invalidation;
- source enforcement;
- revision/repair scope;
- job execution and safe events;
- integrity and release readiness.

### Frontend owns

- which artifact/record is selected;
- open dialogs, tabs, filters, and reading modes;
- rendering typed questions and commands;
- showing impact and asking for confirmation;
- displaying canonical status and safe progress;
- navigation after successful decisions.

The frontend must not duplicate the dependency graph, question visibility rules,
approval rules, or source eligibility rules.

## 17. Contract test requirements

Before a command is considered implemented, add tests for:

1. successful valid mutation;
2. invalid target/field rejection;
3. expected-checksum conflict;
4. read-only example rejection;
5. course mutation lock conflict;
6. correct direct and downstream impact;
7. preservation of unrelated artifact bodies;
8. resulting stage projection;
9. approval-guard behavior;
10. deterministic/live parity of artifact shape;
11. safe event payloads for jobs;
12. browser interaction where the command is exposed.

Source and content repair additionally require byte-for-byte preservation assertions for
unaffected assets.

The Outcomes command additionally requires focused coverage of complete-collection
reduction, deterministic ID allocation and temporary-reference ordering, strict payloads,
normalization and no-op rejection, advisory results, Brief-readiness gates, draft
persistence, approval/reopen capability gates, and canonical refresh behavior.

## 18. Technical start gate

Implementation may begin when:

- the state model is accepted;
- the capability matrix is accepted;
- explicit invalidation replaces ambiguous timestamp-only browser behavior in the
  implementation backlog;
- each enabled revision action maps to a named handler;
- Brief intake persistence uses the Brief artifact and `intake_state`;
- Source Repair is accepted as a dedicated support-artifact workflow;
- Package is confirmed as deterministic;
- deterministic/live implementations are confirmed to share the same step contracts;
- the acceptance plan has concrete deterministic and live scenarios;
- the initial lifecycle tests are identified in the backlog.

These decisions are now the baseline for the companion implementation backlog and
acceptance plan.
