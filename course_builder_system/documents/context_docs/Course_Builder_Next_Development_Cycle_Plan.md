# Course Builder — Next Development Cycle Plan

> **Status:** Approved planning baseline for the next development cycle  
> **Updated:** 2026-07-20
> **Planning model:** Milestone-gated; no fixed time constraint  
> **Target user:** One internal, nontechnical course director  
> **Scope:** Finish the eight-stage browser product, close the content-trust loop,
> and prove the same workflow with live agent-backed stages  
> **Read with:** `Course_Builder_Master_Context.md`,
> `Course_Builder_Four_Week_Prototype_Completion_Handoff.md`, and
> `Course_Builder_Frontend_Implementation_Handoff.md`

> **Implementation update — 2026-07-20:** NC-10 and NC-20 have passed independent
> review. The post-frontend audit below records the gaps that led to those packages;
> current Guided Brief behavior is documented in the frontend implementation handoff.
> NC-301 and NC-302 have passed independent NC-30 checkpoint review. NC-303 remains
> deferred to NC-90 behind NC-902. NC-401 through NC-403 passed independent NC-40
> backend checkpoint review on 2026-07-20 after corrective hardening. NC-40 is not
> complete: NC-404 through NC-406 and all later packages remain unstarted, Course Model
> browser editing stays disabled, and the next safe implementation action is NC-404.
> NC-405 remains dependent on NC-404. This does not complete Milestone 3 or the cycle.

## 1. Purpose of this document

This document is the active plan for the development cycle after the first Course
Builder Studio implementation.

The pipeline and browser workspace now complete the full mechanical path from a sparse
subject request to a rendered Markdown course. The next cycle is not primarily about
adding more output formats or expanding infrastructure. It is about making the existing
product dependable, truthful, editable, and usable by a nontechnical internal course
director.

The target outcome is:

> A nontechnical internal course director can create, revise, repair, approve, and
> package a trustworthy sample course entirely in Course Builder Studio—first through
> the deterministic implementation, then through the live agent-backed workflow.

This plan is milestone-driven rather than calendar-driven. A milestone is complete only
when its exit gate passes. Later functionality should not be layered on top of an
unfinished interaction or trust contract.

The implementation handoff remains authoritative for what exists today. This document
is authoritative for what the next development cycle is intended to achieve.

### Planning package

Use this plan with three implementation companions:

- `Course_Builder_Next_Cycle_Technical_Contract_Plan.md` — target lifecycle,
  invalidation, typed command, repair, live execution, and observability contracts;
- `Course_Builder_Next_Cycle_Implementation_Backlog.md` — task-sized work packages,
  dependencies, priorities, ownership split, and package exit gates;
- `Course_Builder_Next_Cycle_Acceptance_and_Pilot_Plan.md` — deterministic, negative,
  recovery, live-agent, and internal course-director release scenarios.

This document answers **what outcome and milestones are required**. The technical plan
answers **what shared behavior must be preserved**. The backlog answers **what work to
pull and in what dependency order**. The acceptance plan answers **how completion is
proven**.

## 2. Executive direction

The theme of the next cycle is:

`close the operator loop`

The planning direction confirmed for this cycle is:

- the release user is one internal, nontechnical course director;
- work is milestone-gated rather than constrained to an arbitrary schedule;
- intake uses a small mandatory question set plus bounded questions for missing or
  conflicting information;
- deterministic implementations prove the complete workflow first;
- the final product demonstration must build a full course with real live agent/research
  calls behind the same contracts;
- authentication, collaboration, hosting, native document output, SCORM, RAG, and other
  expansion features remain deferred.

The product already runs all eight stages. The next work must ensure that the course
director can:

- provide the minimum necessary intent without completing a long questionnaire;
- receive bounded follow-up questions only when information is missing or conflicting;
- inspect and correct consequential fields at every checkpoint;
- reopen an approved stage safely;
- understand downstream impact before committing a change;
- distinguish a real revision from a generic regeneration;
- select, reject, add, and repair grounding evidence;
- resolve verifier blockers without regenerating unaffected content;
- see real progress, failures, and safe recovery actions;
- inspect the actual rendered course files;
- run the same product journey in deterministic and live modes;
- finish only when the course is genuinely releasable.

Major expansion features are deliberately deferred until this outcome is proven.

## 3. Product and technical baseline

### 3.1 What already works

The current product provides a strong base:

- an eight-stage React workspace over the existing artifact pipeline;
- a FastAPI adapter that keeps the domain layer separate from HTTP concerns;
- persisted JSON artifacts and resumable stage execution;
- explicit approval checkpoints;
- deterministic and live run-mode selection;
- persisted local jobs and Server-Sent Event transport;
- optimistic concurrency through expected checksums;
- explicit source selection and approved-source enforcement;
- Course Model, Blueprint, Student Content, Lesson Plan, and Package review views;
- durable Guided Brief intake and a typed Outcomes structural decision editor;
- live Student Content generation and independent verification;
- durable per-asset human content review;
- targeted Student Content revision;
- Markdown rendering and package reconciliation;
- read-only inspection of committed acceptance and live-run snapshots.

As of this plan, the regression baseline is:

- `133` Python tests passing in the project virtual environment;
- `6` frontend API-client tests passing;
- a deterministic API workflow test that reaches a rendered Package.

### 3.2 Gaps found during the post-frontend audit

The most important gaps are not cosmetic.

| Area | Current behavior | Required direction |
|---|---|---|
| Brief questions | Typed question and gap-detection primitives exist in Python, but the browser immediately creates a default Brief. | Expose the question contract through the API and implement bounded question rounds. |
| Outcomes editing | NC-301 and NC-302 now provide independently verified strict deterministic reduction and a typed React editor. | Preserve the typed contract and keep NC-303 live scoped revision deferred to NC-90 behind NC-902. |
| Blueprint editing | The backend has a typed decision command, but React is read-only. | Wire asset selection, defaults, exceptions, and depth controls. |
| Course Model editing | NC-401 through NC-403 provide an independently verified deterministic typed backend mutation contract; the browser controls remain disabled. | Start NC-404 UI work, then NC-405 diff work only after its NC-404 dependency is complete. |
| Lesson Plan editing | The view shows constraints, but changes rely on generic feedback. | Add typed constraint and sequence commands. |
| Generic revision | Several stage steps accept feedback at the API boundary but ignore it in the step implementation. | Show revision actions only when a real scoped handler exists. |
| Reopening | The API has a reopen command, but React does not expose it consistently. | Add explicit reopen and downstream-impact confirmation. |
| Source repair | “Find better evidence” targets an approved Research stage that the API requires to be reopened first. | Build a dedicated bounded repair workflow rather than a generic stage rerun. |
| Live mode | Research and Student Content/verification are live; several upstream proposal stages remain deterministic. | Add live implementations behind the same stage contracts. |
| Progress | The browser receives stage events, but content unit events are not emitted continuously during generation. | Connect generation callbacks to persisted progress events. |
| Activity | The visual surface exists, but activity, diagnostics, and cost data are incomplete or placeholder-like. | Project real safe events and stage-level call summaries. |
| Package preview | Raw Markdown can be opened, but the inline preview is representative content. | Fetch and render the actual selected file. |
| Browser assurance | API coverage is strong, but there is no true browser end-to-end acceptance suite. | Add component, accessibility, and Playwright coverage. |

### 3.3 Important product truth

The interface must not imply that a feature works when only its visual control exists.
An enabled action must have a complete command, domain implementation, persistence path,
projection rule, and test. Otherwise it should remain visibly unavailable.

## 4. Planning principles

The following principles govern this cycle.

### 4.1 One workflow, two implementations

Deterministic and live modes must exercise the same:

- routes and views;
- typed commands;
- artifact contracts;
- approval checkpoints;
- stale and reopen behavior;
- verifier and review gates;
- rendering path.

Only the proposal or generation implementation changes.

```text
operator action
    -> typed stage command
        -> shared validation and persistence contract
            -> deterministic implementation for repeatable acceptance
            -> live implementation for real model/research execution
```

There must not be a separate simplified product flow for deterministic testing.

### 4.2 Typed decisions before generic prose

Use direct fields and structured commands for bounded decisions. Free text may add
nuance, but it must be attached to a known stage, record, asset, claim, or operation.

A revision request should identify at least:

- the stage;
- the target type;
- the target ID or bounded scope;
- the revision category;
- the operator instruction;
- the expected checksum;
- the requested execution mode.

### 4.3 Approval remains human-controlled

Agents may propose artifacts and revisions. They must not approve sources, approve stage
outputs, clear human-review decisions, or declare the final course ready.

### 4.4 Repair the smallest valid scope

Revisions should invalidate and regenerate only the scope affected by the change.
Unrelated, approved assets should be preserved.

### 4.5 Verification remains the release gate

Unsupported, ungrounded, and unattributed findings remain hard blockers. Partial
evidence remains visible for human judgment. Mechanical rendering never overrides the
content gate.

### 4.6 Use agents where judgment helps

Live agent implementations are appropriate for clarification, outcomes, research,
structure, Blueprint proposals, content, verification, and Lesson Plan proposals.

Source approval, typed reducers, referential integrity, stage state, downstream
invalidation, rendering, and release-state calculation should remain deterministic.

### 4.7 Preserve current architecture boundaries

- The orchestrator remains an opaque artifact engine.
- Pipeline stages remain data-driven `Step` objects or injected stage callables.
- React and browser storage do not become authoritative.
- The Course Model remains the structural source of truth.
- The Blueprint continues to control exact asset generation.
- Full source bodies remain outside the Course Model.
- Generation context remains bounded and routed by approved IDs.
- Reusable prompts remain domain-neutral.

## 5. Target operator acceptance journey

Before feature implementation begins, the team should turn the following journey into
the canonical deterministic and live acceptance scenario.

The internal course director must be able to:

1. create a course from a sparse subject;
2. answer the mandatory Brief questions;
3. answer at least one conditional clarification;
4. correct and approve the Brief;
5. edit at least one Course Outcome;
6. review competitor evidence and source candidates;
7. approve at least one source and reject at least one source;
8. add or repair a source when an evidence gap appears;
9. change one Course Model module or subtopic;
10. change one Blueprint asset selection or depth setting;
11. generate Student Content;
12. resolve a deliberately introduced verifier blocker;
13. review and approve every changed content asset;
14. change one Lesson Plan constraint;
15. render and inspect the actual Package files;
16. complete the workflow with a truthful `complete` status.

The deterministic scenario proves the product and state contracts. The live scenario
proves the agent-backed implementations behind those contracts.

## 6. Milestone 0 — Acceptance contract and capability map

### Objective

Define the release boundary before writing more feature code.

### Work

1. Select the sample-course subject for deterministic acceptance.
2. Select a second subject for the final live-agent pilot.
3. Write the operator acceptance script using the journey in Section 5.
4. Define the exact expected artifact and stage state after every action.
5. Create a stage capability matrix covering:
   - view;
   - run;
   - direct edit;
   - scoped revision;
   - reopen;
   - approve;
   - repair;
   - retry;
   - downstream impact.
6. Mark every current control as implemented, incomplete, or deliberately unavailable.
7. Turn the most important missing behavior into failing contract or browser tests before
   implementation.

### Exit gate

- The team agrees that completing the acceptance journey means the cycle succeeded.
- Every intended stage action has a named command and acceptance behavior.
- No feature is included only because a visual control already exists.

## 7. Milestone 1 — Workflow and lifecycle correctness

### Objective

Make stage state, approval, reopening, revision, and invalidation consistent before
adding richer stage editing.

### Work

1. Wire the existing reopen API into the frontend.
2. Require an explicit reopen before changing an approved artifact, except for a
   dedicated bounded repair operation whose impact is already known.
3. Add a downstream-impact preview before consequential changes.
4. Show affected stages and affected assets separately.
5. Make stale state reliable when inputs change, including rapid consecutive changes.
6. Preserve optimistic concurrency checks for every consequential mutation.
7. Add an explicit `needs_input` state, or an equivalent truthful projection, for a
   stage that is waiting on user answers rather than ready to run an agent.
8. Enforce allowed stage states on the server for run, approve, reopen, revise, retry,
   and repair commands.
9. Enforce Content and Package approval gates on the server.
10. Prevent approval when:
    - required stage artifacts are missing;
    - a required source decision is missing;
    - hard verifier blockers remain;
    - required content reviews are pending or changes are requested;
    - referential integrity fails;
    - selected/generated/rendered assets do not reconcile.
11. Remove or disable fake enabled controls.
12. Show `Request changes` only where the current stage has a real revision handler.
13. Ensure job failure and API restart recovery lead to a clear, safe retry state.

### Exit gate

- An approved stage can be safely reopened from the browser.
- The user sees downstream impact before committing a change.
- A stage never silently accepts unsupported feedback.
- The backend prevents an invalid approval even if the UI is bypassed.
- Resume and stale behavior remain correct after revision and restart.

## 8. Milestone 2 — Guided Brief intake

### Objective

Collect the smallest useful amount of human intent while asking additional questions
only when they materially improve the Brief.

### 8.1 Mandatory starting information

The recommended mandatory information is:

1. subject;
2. intended audience;
3. desired practical result;
4. prior knowledge;
5. target level;
6. available learning time;
7. delivery mode.

Language may default to English, but the default must be visible and editable before
approval.

### 8.2 Conditional information

Ask only when applicable or unresolved:

- jurisdiction, regulation, or geography;
- freshness or currentness requirements;
- required tools, software, or equipment;
- must-have topics or examples;
- excluded topics;
- accessibility requirements;
- live-teaching constraints;
- conflicts between level and prior knowledge;
- ambiguous audience or purpose;
- overlap between in-scope and out-of-scope material.

The normal additional round should contain no more than three high-impact questions.

### 8.3 Work

1. Expose the existing `QuestionSpec` model through validated API view models.
2. Return question ID, field, prompt, rationale, answer type, options, default, required
   state, skip behavior, and visibility conditions.
3. Persist answers after every round.
4. Use the draft Brief as canonical durable progress rather than browser-only form state.
5. Render question rounds as typed form controls.
6. Explain why each question matters.
7. Allow visible defaults to be accepted explicitly.
8. Run deterministic gap detection first.
9. In live mode, allow the intake implementation to propose additional questions only
   within the validated fields and maximum-question limit.
10. Synthesize a readable Brief from the accepted answers.
11. Preserve direct section editing after synthesis.
12. Prevent Brief approval until mandatory information is resolved.

### Exit gate

- A sparse request receives a short, relevant clarification flow.
- A detailed request is not forced through redundant questions.
- Refreshing the browser does not lose answers.
- The approved Brief visibly distinguishes human answers from accepted assumptions.

## 9. Milestone 3 — Meaningful editing for every stage

### Objective

Let the course director correct the decisions that materially shape the course without
opening JSON or using the terminal.

The goal is not a generic editor for every raw field. The goal is a complete set of
operator-relevant decisions.

### 9.1 Minimum stage controls

| Stage | Minimum operator controls |
|---|---|
| Brief | Direct field and section editing; question answers; assumptions |
| Outcomes | Add, edit, remove, reorder, change evidence, change priority |
| Research | Preview, select, reject, add URL, research a specific gap |
| Course Model | Add/remove/reorder modules and subtopics; edit title, purpose, scope, coverage, prerequisites, and source assignments |
| Blueprint | Apply defaults, select assets, set per-subtopic exceptions, adjust depth/time/examples/case/assessment settings, control anchor waiver |
| Student Content | Review asset, select claim/finding, request scoped revision, repair evidence, record human decision |
| Lesson Plan | Change session limits, delivery mode, live/self-study split, order, and affected-session regeneration |
| Package | Inspect actual output, retry deterministic rendering, return to the blocking stage |

### 9.2 Outcomes

**Implementation status (2026-07-20):** NC-301 and NC-302 have passed independent
checkpoint review. This does not complete the Milestone 3 exit gate. NC-303 remains
deferred to NC-90 behind NC-902. NC-401 through NC-403 are implemented with
deterministic backend evidence and have passed independent NC-40 backend checkpoint
review. NC-40 is not complete; NC-404 through NC-406 and all later packages remain
unstarted, and Course Model browser editing remains disabled. The next safe action is
NC-404; NC-405 remains dependent on NC-404.

1. Wire the existing typed Outcomes API command into React.
2. Support add, edit, remove, reorder, evidence, cognitive level, and priority.
3. Validate the complete resulting collection on the backend, preserve stable retained
   IDs, and allocate deterministic collision-free IDs for additions.
4. Require a complete nonempty priority order when supplied; for compatibility, an
   omitted or empty order resolves to selected Outcome order followed by addition order.
5. Provide structured advisory checks for vague verbs, duplicate or near-duplicate
   statements, and mechanically weak evidence without pretending to judge pedagogy.
6. Save the changed Outcomes as a new draft, survive refresh, and require separate
   explicit approval.

### 9.3 Course Model

1. Define typed structural operations rather than accepting arbitrary body replacement.
2. Support module and subtopic add, remove, rename, reorder, and move.
3. Support scoped edits to purpose, in/out scope, prerequisites, concepts, coverage
   requirements, outcome links, and source assignments.
4. Generate stable IDs through backend domain logic.
5. Run referential-integrity validation after every command.
6. Reject destructive operations that leave unresolved references.
7. Show whether the change affects only Blueprint, or Blueprint plus generated content
   and Lesson Plan.

### 9.4 Blueprint

1. Wire the existing typed Blueprint decision API into React.
2. Support applying course-wide defaults.
3. Support per-subtopic asset selection.
4. Support depth, time, word-range, example, case, and assessment overrides.
5. Require an explicit anchor waiver when Course Content is removed.
6. Show exceptions separately from the baseline.
7. Reconcile selected assets before approval.

### 9.5 Lesson Plan

1. Add a typed Lesson Plan constraints command.
2. Support maximum session length, default delivery mode, and relevant live constraints.
3. Support moving a subtopic between live and self-study delivery.
4. Support sequence changes through validated operations.
5. Regenerate only affected sessions when possible.
6. Preserve complete, exact Course Model coverage.

### 9.6 Scoped free-text revisions

Free text remains useful for changes that are hard to represent as direct fields. The
request must identify a stage and bounded target. The stage implementation must return a
changed artifact or a clear failure explaining why it could not apply the request.

Where practical, show a concise before/after summary before approval.

### Exit gate

- The director can make at least one meaningful correction at every checkpoint.
- Structured decisions use typed commands.
- Free-text revision is always scoped and implemented.
- Stable IDs, source boundaries, and downstream references remain valid.

## 10. Milestone 4 — Research and source-quality improvement

### Objective

Improve the evidence presented for approval before attempting to compensate through
content revision.

### Work

1. Rank source candidates by:
   - authority;
   - topical fit;
   - specificity;
   - freshness when relevant;
   - fetch and content availability;
   - likely coverage of the current evidence need.
2. Distinguish primary or authoritative material from broad overview/index pages.
3. Show a bounded source-content preview inside the workspace.
4. Show estimated coverage by topic or evidence gap.
5. Let the operator add a known URL after course creation.
6. Capture relevant page sections rather than only an initial bounded slice.
7. Let a research job receive an explicit subtopic, asset, claim, and evidence-gap scope.
8. Preserve competitor pages as curriculum evidence unless separately approved as
   grounding sources.
9. Keep the recommendation visually separate from the human source decision.
10. Record fetch failures and contentless sources without allowing them downstream.

### Exit gate

- The director can tell what a source is likely to support before approving it.
- A bounded research request can target one missing evidence area.
- Broad pages are not silently preferred over more specific authoritative material.
- Rejected and contentless sources remain excluded downstream.

## 11. Milestone 5 — Closed verifier-driven repair loop

### Objective

Turn verifier findings into a complete, observable repair workflow that preserves
unaffected work.

### 11.1 Required flow

```text
verifier finding
    -> classify likely cause
        -> revise using existing approved evidence
        OR
        -> find better evidence
            -> run bounded research
            -> review candidate
            -> approve source
            -> assign source to affected subtopic/assets
    -> regenerate affected assets only
    -> reverify changed assets
    -> update human-review state
    -> recalculate release status
```

### 11.2 Work

1. Classify a finding as likely:
   - content/generation error;
   - missing attribution;
   - insufficient approved evidence;
   - ambiguous human-review case.
2. Define a repair request containing asset IDs, claim IDs, subtopic IDs, finding type,
   and selected repair strategy.
3. Add a dedicated repair service or bounded workflow rather than routing every gap
   through generic Research-stage feedback.
4. Append newly discovered source candidates to the Research Dossier without marking
   them approved.
5. Require an explicit human decision before adding a source to the approved registry.
6. Add typed source assignment to the affected Course Model subtopic and Blueprint
   assets.
7. Preview the exact artifacts and assets affected by the assignment.
8. Regenerate only the selected assets.
9. Reverify every changed asset automatically.
10. Preserve unaffected assets byte-for-byte.
11. Reset human review only for assets whose review-relevant content changed.
12. Keep hard blockers until the new verifier result actually clears them.
13. Keep partial evidence visible for human judgment.
14. Update the run summary and Package readiness after every repair.
15. Add a deterministic acceptance fixture that deliberately produces and then clears a
   blocker.

### Exit gate

- A blocker can be resolved from the browser using existing or newly approved evidence.
- Only affected assets regenerate.
- Unaffected assets remain byte-for-byte unchanged.
- Reverification and human-review state are correct.
- `complete` remains impossible until all hard blockers are cleared.

## 12. Milestone 6 — Live-agent parity

### Objective

Replace deterministic proposal implementations with live implementations behind the
same validated contracts, then prove a live end-to-end course.

### 12.1 Live implementations required

- Brief synthesis and bounded clarification;
- Course Outcomes proposal and scoped revision;
- research planning, search, source evaluation, and evidence-gap repair;
- Course Model proposal and scoped structural revision;
- Blueprint proposal and scoped revision;
- Student Content generation;
- independent verification;
- Lesson Plan proposal and scoped revision.

### 12.2 Operations that remain deterministic or human-controlled

- source approval and rejection;
- typed decision reducers;
- stable ID generation and structural validation;
- referential-integrity checks;
- stage-state projection;
- downstream invalidation;
- approval gates;
- human content-review decisions;
- rendering and packaging;
- final release-state calculation.

### 12.3 Implementation rules

1. Use direct model SDK calls and injected implementations; do not introduce an agent
   framework without a demonstrated need.
2. Validate structured model output before persistence.
3. Run deterministic integrity and source-boundary checks after model output.
4. Keep prompts domain-neutral.
5. Route only bounded artifact slices and approved source excerpts.
6. Give live revision calls only the target record, relevant constraints, and affected
   evidence.
7. Do not silently fall back to deterministic output when a live call fails.
8. Show a safe retry path after a live failure.
9. Record stage, provider, model, token, cost, retry, and cache information in safe
   diagnostics rather than the artifact body or browser-local state.
10. Preserve existing source-excerpt bounds.
11. Add stage-specific cost and call limits.
12. Add stage evals for schema validity, instruction adherence, domain neutrality,
   grounding, coverage, and revision scope.

### Exit gate

- The acceptance journey passes in Live mode.
- Judgment-heavy stages use real model or research calls.
- Human decisions and deterministic gates remain authoritative.
- The operator can see which stages ran live and their safe call/cost summaries.
- The live course passes integrity, source-boundary, verification, review, and Package
  gates.

## 13. Milestone 7 — Operator experience and observability

### Objective

Ensure a nontechnical director can understand work, failures, and next actions without
terminal or JSON access.

### Work

1. Connect content generation callbacks to persisted unit events while work is running.
2. Show real completed/expected unit progress.
3. Populate Activity from persisted jobs and safe events.
4. Show stage-level model-call counts, token summaries, estimated cost, cache hits,
   retries, and failures.
5. Never expose hidden reasoning, full private prompts, credentials, or full source
   bodies through diagnostics.
6. Check provider readiness before allowing a live stage to start.
7. Explain configuration problems without asking the operator to debug Python.
8. Add clear retry and recovery actions after provider errors or API restarts.
9. Fetch and render the actual selected Markdown file in the Package preview.
10. Add a final acceptance checklist with links back to blocking work.
11. Make empty, needs-input, ready, running, awaiting-review, approved, attention,
    stale, failed, and locked states visually and semantically distinct.
12. Make deterministic and live execution unmistakable.
13. Improve keyboard navigation, focus restoration, labels, modal behavior, and status
    announcements.

### Exit gate

- The director can determine what the system is doing and what to do next.
- Long-running content work shows real progress.
- Failures provide a safe browser action.
- The selected Package document is the actual rendered file.
- No enabled diagnostic or navigation control is a placeholder.

## 14. Milestone 8 — Browser validation and internal pilot

### Objective

Prove the complete product through automation and an unaided internal course-director
pilot.

### 14.1 Automated validation

Add:

- React interaction tests for every typed editor;
- question-round and default-acceptance tests;
- reopen and downstream-impact tests;
- revision-scope tests;
- source preview, approval, addition, and repair tests;
- content-review and verifier-repair tests;
- actual Package-preview tests;
- accessibility checks for the primary journey;
- a Playwright deterministic end-to-end acceptance scenario;
- refresh and navigation recovery during an active job;
- API restart recovery;
- optimistic-concurrency conflict handling;
- a deterministic blocker-repair scenario;
- a bounded live-agent smoke scenario;
- stage-level live-call and cost assertions.

Existing schema, integrity, source leakage, selected-asset, resume, and negative-gate
tests remain required.

### 14.2 Internal pilot protocol

The internal course director receives only the normal local start instructions and the
product URL. They should not receive terminal commands for manipulating a course or
instructions to edit JSON.

During the pilot they must:

1. create the chosen sample course;
2. complete the bounded intake;
3. revise at least one major design artifact;
4. make explicit source decisions;
5. change the generated asset plan;
6. review generated learner content;
7. repair one verifier blocker;
8. approve the Lesson Plan;
9. inspect the actual rendered Package;
10. explain why the course is or is not ready.

Record:

- points where engineering help was required;
- actions the director expected but could not find;
- incorrect or misleading status;
- revisions that changed too much or too little;
- unclear source or verification information;
- acceptable and unacceptable waiting time;
- product preferences that are not functional blockers.

Any need for terminal access, raw JSON editing, or manual artifact repair is a release
blocker.

### Exit gate

- Deterministic browser acceptance passes.
- The bounded live-agent acceptance passes.
- The internal course director completes the pilot without engineering intervention.
- Remaining feedback consists of prioritized usability or quality improvements rather
  than broken core workflow.

## 15. Definition of done for the cycle

The next development cycle is complete only when all of the following are true:

1. Every enabled control performs the action it promises.
2. Mandatory Brief information is resolved before approval.
3. Conditional questions are bounded and relevant.
4. The operator can correct every consequential stage through the UI.
5. Approved stages can be safely reopened.
6. Downstream impact is shown before a consequential change.
7. Stale and resume behavior remain correct after revisions.
8. Source approval and rejection remain explicit and enforced.
9. Rejected, proposed, unavailable, competitor-only, and contentless sources do not leak
   into generation.
10. A verifier blocker can be repaired end to end from the browser.
11. Targeted repair preserves unaffected assets.
12. Reverification and per-asset human review are durable and truthful.
13. Deterministic and live modes use the same operator workflow and contracts.
14. Live mode uses real model or research calls for judgment-heavy stages.
15. The operator can see safe progress and call/cost diagnostics.
16. The Package preview shows the actual rendered documents.
17. `complete` is impossible while hard blockers or required reviews remain.
18. The internal nontechnical course director completes the sample-course pilot without
   engineering intervention.

## 16. Recommended dependency order

The milestones should be implemented in this order:

```text
acceptance contract
    -> lifecycle correctness
        -> guided intake
            -> typed stage editing
                -> source quality
                    -> closed verifier repair
                        -> live-agent parity
                            -> observability and operator polish
                                -> browser acceptance and internal pilot
```

Some frontend and backend tasks within a milestone can proceed in parallel after their
shared command and view contracts are agreed. Milestone exit gates should remain
sequential.

The first implementation package should contain:

1. the acceptance capability map;
2. failing tests for reopen, downstream impact, and the currently broken source-repair
   action;
3. consistent server-side approval gates;
4. the frontend reopen and impact-confirmation workflow;
5. removal or disabling of unsupported revision actions;
6. the serialized Brief question contract and first question-round UI.

## 17. Risk register

### 17.1 Full editing becomes an unbounded WYSIWYG project

**Risk:** Attempting to expose every artifact field delays the trust and repair work.

**Control:** Implement the minimum consequential decisions in Section 9. Use bounded
agent revision for complex prose changes and retain raw data only as a diagnostic view.

### 17.2 Source repair accidentally regenerates the whole course

**Risk:** Updating Research, Course Model, and Blueprint evidence routes can cause broad
staleness.

**Control:** Design a dedicated repair workflow with explicit impact, typed source
assignment, targeted asset regeneration, and byte-for-byte preservation tests.

### 17.3 Live mode overstates agent coverage

**Risk:** The UI says “Live agent” while a stage still uses deterministic proposal code.

**Control:** Record the implementation used by each job and show it in Activity. Do not
claim live parity until the stage has a real live implementation and eval coverage.

### 17.4 Agent output weakens deterministic guarantees

**Risk:** Structured outputs contain invalid IDs, source routes, or asset selections.

**Control:** Validate and reduce all live outputs through deterministic domain logic.
Never let the model own approval or integrity state.

### 17.5 Better UI hides unresolved content risk

**Risk:** Polished screens make a mechanically complete course appear learner-ready.

**Control:** Keep verifier and human-review gates server-enforced and visible through the
final Package.

### 17.6 Browser testing arrives too late

**Risk:** API contracts pass while real navigation, focus, refresh, or async selection
breaks.

**Control:** Establish the browser acceptance scenario in Milestone 0 and grow it with
each milestone.

### 17.7 Cost or latency makes the live pilot impractical

**Risk:** Agent parity introduces too many calls before quality is established.

**Control:** Preserve bounded context, use stage budgets, cache unchanged calls, keep the
pilot asset plan intentionally representative, and record cost per stage before
optimizing through parallelism.

## 18. Deliberate deferrals

The following are out of scope until this plan's release gate passes:

- authentication and authorization;
- multi-user collaboration, comments, and real-time editing;
- hosted production deployment;
- distributed queues or multiple API workers;
- native DOCX/PPTX generation and styling;
- SCORM wiring;
- generic agent chat;
- a generic workflow-builder interface;
- RAG, embeddings, or vector search;
- mobile authoring;
- organization-wide dashboards;
- automatic pedagogical-quality judgment;
- broad generation parallelization;
- nonessential bundle optimization;
- additional export formats.

These deferrals are not statements that the features have no value. They preserve focus
on a complete, trustworthy single-director workflow.

## 19. Final planning summary

The first Course Builder Studio release proved that the existing pipeline can be
operated through a browser. The next cycle must prove that the browser product is a
complete course-director workspace rather than a review layer over a CLI-oriented
prototype.

The work should proceed from workflow truth to interaction completeness, then from
deterministic acceptance to live-agent parity. The final gate is not an engineering
demo. It is an internal nontechnical course director completing a real sample course,
making corrections, repairing evidence, and reaching a trustworthy Package without
terminal or artifact-level intervention.
