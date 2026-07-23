# Course Builder — Next Cycle Acceptance and Pilot Plan

> **Status:** Acceptance baseline for implementation and release  
> **Updated:** 2026-07-20
> **Target user:** One internal, nontechnical course director  
> **Parent plan:** `Course_Builder_Next_Development_Cycle_Plan.md`  
> **Backlog:** `Course_Builder_Next_Cycle_Implementation_Backlog.md`  
> **Technical contracts:** `Course_Builder_Next_Cycle_Technical_Contract_Plan.md`

> **NC-20 checkpoint — 2026-07-17:** Guided Brief Intake passed independent
> deterministic review. Evidence covers bounded relevant rounds, durable refresh and
> multi-round merges, status-aware historical normalization without fixture writes,
> stale/concurrent mutation rejection, unresolved approval and transitive execution
> gates, impact-confirmed reopen, and browser conflict recovery.

> **NC-30 independent checkpoint — 2026-07-17:** NC-301 and NC-302 passed independent
> deterministic review. Evidence covers strict complete-collection reduction, stable
> monotonic backend-owned IDs, canonical ordering, typed browser editing, unsaved-work
> protection, explicit stale-conflict resolution, durable draft refresh, explicit
> approval, capability/reopen gates, and downstream invalidation. NC-303 remains
> deferred to NC-90 behind NC-902.

> **NC-40 backend checkpoint — 2026-07-20:** NC-401 through NC-403 passed independent
> deterministic review after corrective hardening of stable ID history, ordered typed
> references, source provenance, shared schema enforcement, and rollback cleanup.
> NC-404 and NC-405 passed independent review with deterministic browser Scenario A6
> evidence, including the exact-preview structural diff. NC-40 is not complete because
> NC-406 remains deferred to NC-90. This does not mark Milestone 3 or the whole cycle
> complete.

> **NC-50 checkpoint — 2026-07-20:** NC-501 through NC-503 passed independent
> deterministic review with browser Scenario A7 evidence. Evidence covers typed
> defaults and per-subtopic exceptions, exact asset/depth contracts, word/time/example/
> case/assessment controls, explicit anchor waivers, reconciliation and stale-content
> preview, refresh and checksum-conflict recovery, approved-source-only routing, and
> rejection without mutation for noncurrent Course Models or rejected/contentless
> sources. NC-504 remains deferred to NC-90 behind NC-905.

> **NC-60 checkpoint — 2026-07-20:** NC-601 through NC-603 passed independent
> deterministic review with browser Scenario A12 evidence. Evidence covers typed
> constraints, modes, moves, and ordering; exact ordered Course Model coverage across
> Blueprint and Content; monotonic session IDs; intent-aware checksum-conflict rebasing;
> bounded preservation and exact affected-session reporting; refresh; explicit approval;
> and Package readiness. NC-604 remains deferred to NC-90 behind NC-908.

> **NC-70 checkpoint — 2026-07-20:** NC-701 through NC-709 passed independent
> deterministic review with browser evidence for Scenario A10's source-decision and
> route phase. Evidence covers advisory source quality, bounded previews, known-source
> proposal without premature approval, exact Content-origin repair scope, bounded
> candidate research, human approval, atomic dossier/registry/Course Model/Blueprint
> routing, unrelated-record preservation, rollback, and the truthful
> `awaiting_content_repair` boundary. At that checkpoint, targeted Content regeneration,
> reverification, and review closure remained NC-80 work; the following checkpoint
> records its completion.

> **NC-80 checkpoint — 2026-07-20:** NC-801 through NC-808 passed independent
> deterministic review with browser Scenarios A8 through A11 evidence. Evidence covers
> advisory finding classification, truthful source-less and unattributed hard-blocker
> gating, existing-evidence and better-evidence repair, exact target-only regeneration
> and reverification, unchanged-asset preservation, Source Repair lifecycle closure,
> fingerprint-based review reset/preservation, visible nonblocking partial findings,
> and Content approval releasing Lesson Plan only after review closure. Negative and
> recovery evidence covers pre-job validation, atomic scope rejection, secret-safe
> typed failure/retry, and process-restart recovery. This does not mark Milestone 3 or
> the whole cycle complete.

> **NC-003 live-subject checkpoint — 2026-07-20:** The documented fallback is selected
> for live validation: `Indoor herb gardening for apartment beginners`, course ID
> `studio-live-pilot`. The boundary is five subtopics and ten representative learner
> assets, with a practical three-container setup/care/harvest outcome, accessible public
> horticultural sources, and no medicinal, commercial, pesticide-prescription,
> electrical-installation, or other expert-sign-off scope.

> **NC-90 checkpoint — 2026-07-20:** NC-901 through NC-912 and scoped live revisions
> NC-303, NC-406, NC-504, and NC-604 passed independent review. Contract evidence
> covers explicit deterministic/live registry
> ownership, original-schema validation for paid and cached structured output, bounded
> research retries and stable result IDs, reducer-owned live proposals/revisions,
> truthful live Brief provenance and repeat clarification, bounded live evidence repair,
> atomic stage-plus-invalidation writes, unknown-target rejection, and explicit
> no-fallback failures. Stage evals use an injected structured provider across indoor
> herb gardening and bicycle maintenance and prove grounding, coverage, source routing,
> generation/verification separation, revision scope, and repair categories. They are
> not a credentialed Anthropic end-to-end run; that remains NC-1104.

> **NC-100 checkpoint — 2026-07-20:** NC-1001 through NC-1007 passed independent
> review. Evidence covers timely generation and targeted-repair progress, persisted
> secret-safe activity and stage call summaries, readiness gates on every live start
> path, actual bounded Markdown rendering with raw HTML disabled, exact backend-owned
> release-blocker navigation, and keyboard/focus/status/contrast coverage. The full
> Python suite passes 458 tests, the frontend suite passes 92 tests, and the corrected
> Chromium acceptance suite passes all 9 scenarios. NC-110 is next; neither Milestone 3
> nor the cycle is complete.

> **NC-110 implementation evidence — 2026-07-23:** NC-1101 through NC-1105 are
> implemented and independently verified. The full Python suite passes 468 tests,
> Ruff passes, the frontend suite passes 92 tests, the
> corrected deterministic Chromium suite passes 13 scenarios, and the credentialed
> `studio-live-pilot` Chromium journey reaches an approved Package with ten reconciled
> assets, zero hard verifier blockers, current human reviews, enforced approved-source
> routing, and successful integrity. Known recorded Anthropic cost is $5.930895; two
> interrupted calls have unknown billing outside that estimate. The two-topic injected
> live regression passes on indoor herb gardening and unrelated bicycle maintenance.
> Recovery evidence now induces an actual post-start stage failure and an actual
> Uvicorn child-process restart; verifier metadata is deterministically restricted to
> explicit title, publisher, type, or URL relationships.
> NC-120 and the real course-director pilot remain unstarted.

## 1. Purpose

This document defines how the next development cycle will be proven complete.

It separates four forms of evidence:

1. deterministic browser acceptance for product and state contracts;
2. negative and recovery acceptance for trustworthiness;
3. bounded live-agent acceptance for real model/research execution;
4. an unaided internal course-director pilot for usability and workflow fit.

Passing API tests alone is not sufficient. Passing a live generation run alone is also
not sufficient. The release gate requires all four forms of evidence.

## 2. Acceptance principles

1. Test the browser journey, not only individual endpoints.
2. Keep deterministic and live flows structurally identical.
3. Make expected stage state explicit after every consequential action.
4. Deliberately exercise revision, reopening, staleness, repair, and recovery.
5. Prove negative gates by attempting invalid actions.
6. Prove targeted repair by hashing and comparing unaffected assets.
7. Never use `--auto-approve` as evidence of human workflow quality.
8. Never claim success while hard verifier blockers or required reviews remain.
9. The internal pilot must not depend on terminal or JSON manipulation.
10. Record live call/cost evidence without exposing credentials or private reasoning.

## 3. Test subjects and course boundaries

### 3.1 Deterministic acceptance subject

Use:

`Coffee making for home beginners`

Recommended course ID in isolated tests:

`studio-cycle-acceptance`

Why:

- existing deterministic research/content fixtures already support the domain;
- prior live evidence identifies realistic troubleshooting source gaps;
- the subject is safe for non-expert acceptance;
- the content is understandable enough for UI and verification review;
- it can exercise examples, activities, assessments, and evidence repair.

The acceptance course must be created under temporary artifact/runtime/render roots. Do
not mutate the committed `coffee-acceptance` or `coffee-live-main` snapshots.

### 3.2 Live acceptance subject — selected

The internal director should select the final live subject before Milestone 6 closes.
Selection criteria:

- non-high-stakes;
- clearly bounded practical result;
- accessible public grounding sources;
- no required legal, medical, or financial expert sign-off;
- approximately four to six subtopics;
- approximately eight to twelve selected learner assets;
- enough factual content to exercise grounding and verification;
- unrelated enough to coffee to test domain neutrality.

Fallback subject:

`Indoor herb gardening for apartment beginners`

Recommended fallback course ID:

`studio-live-pilot`

**Recorded selection (2026-07-20):** use the fallback subject and course ID above for
NC-90 and NC-110 live validation.

- Audience: apartment beginners with no outdoor growing space assumed.
- Practical result: set up and maintain three container-grown culinary herbs, use a
  simple care/troubleshooting log, and make a first routine harvest.
- Five subtopics: indoor site assessment; herb/container/growing-medium selection;
  planting starters or seeds; light/water/feeding/rotation; harvest and common-problem
  troubleshooting.
- Ten-asset envelope: five `course_content` assets, two `activities`, one `case_study`,
  one `assessment`, and one `resources` asset.
- Excluded: medicinal or therapeutic use, commercial cultivation, pesticide
  prescriptions, electrical grow-light installation, and claims requiring expert
  sign-off.
- Verified public grounding examples: Penn State Extension's [Growing Herbs
  Indoors](https://extension.psu.edu/growing-herbs-indoors), University of Minnesota
  Extension's [Growing herbs in home
  gardens](https://extension.umn.edu/gardening-minnesota/growing-herbs), and the Royal
  Horticultural Society's [Growing herbs in
  containers](https://www.rhs.org.uk/herbs/containers).

### 3.3 Pilot course boundary

The pilot may use the same subject as live acceptance if the director has not seen the
generated artifacts. If they helped select or inspect the live acceptance output, use a
new bounded subject to avoid rehearsed behavior.

## 4. Test environment

### 4.1 Deterministic browser environment

- isolated temporary `courses`, `runtime`, and `rendered_courses` roots;
- deterministic pipeline implementations;
- deterministic source-repair provider;
- deterministic content generator/verifier capable of producing named blockers;
- one FastAPI worker;
- production-like React build or controlled Vite test server;
- no external provider credentials required.

### 4.2 Live environment

- normal local course/runtime/render roots dedicated to acceptance;
- server-side Anthropic credentials;
- live research enabled;
- one API worker;
- source and LLM caches enabled but recorded;
- model-call log and job/event persistence enabled;
- no browser-accessible credentials;
- a clean course ID for the first run.

### 4.3 Evidence retained

For each formal acceptance run retain:

- final canonical artifacts;
- rendered course folder;
- run summary;
- integrity report;
- safe job/event history;
- stage implementation/mode summary;
- LLM call/token/cost/cache summary for live runs;
- verifier totals before and after repair;
- content asset hashes before and after targeted repair;
- browser test report/screenshots on failure;
- operator pilot notes and issue classification.

For the NC-30 deterministic checkpoint, retain the results from
`tests/test_outcomes_decisions.py`, `OutcomesEditor.test.tsx`, the Outcomes cases in
`WorkspacePage.test.tsx` and `StageViews.test.tsx`, `client.test.ts`, and the bounded
Playwright Outcomes path in `deterministic-course.e2e.ts`. The checkpoint evidence
identifies the saved canonical draft and explicit approval transition and is supplemented
by the complete Python, frontend, build, and browser regression matrix.

## 5. Scenario A — Deterministic complete operator journey

This scenario is the primary automated browser acceptance path.

### A1 — Create the course

**Operator action**

- Create `studio-cycle-acceptance` from the sparse subject.
- Select Deterministic mode.

**Expected result**

- Subject Request is approved.
- Brief exists as a durable draft.
- Brief state is `needs_input`.
- Outcomes and later stages are locked.
- No default is treated as an explicit human answer.

### A2 — Complete mandatory and conditional intake

Use these test answers:

| Field | Answer |
|---|---|
| Audience | Adults making coffee at home with little technical knowledge |
| Purpose | Consistently brew balanced coffee and diagnose common taste problems |
| Prior knowledge | None assumed |
| Level | Beginner |
| Duration | Three hours |
| Modality | Blended |
| Language | Explicitly accept English default |

Because the modality is blended, answer one conditional live-teaching constraint.
Also trigger one deterministic gap/clarification case, such as an initially generic
audience, and resolve it.

**Expected result**

- Question visibility comes from the backend.
- Earlier answers survive subsequent rounds and refresh.
- No more than the bounded question count appears in one round.
- Required/default-acceptance state is recorded in the Brief.
- Brief changes to `awaiting_review` when resolved.

### A3 — Edit and approve Brief

**Operator action**

- Add “troubleshooting sour and bitter coffee” as a must-have.
- Exclude commercial espresso-machine maintenance.
- Approve Brief.

**Expected result**

- The edit changes only the intended fields.
- The approved Brief reflects human answers and accepted assumptions.
- Outcomes becomes ready.

### A4 — Generate and edit Outcomes

**Operator action**

- Run Outcomes.
- Open the typed Outcomes editor.
- Edit one existing Outcome statement and its evidence to make the result more
  observable.
- Add one Outcome.
- Change a cognitive level and a priority.
- Reorder Outcomes using the keyboard-operable controls.
- Remove a different existing Outcome and confirm the removal.
- Save the complete structural decision as a draft.
- Confirm the canonical server result is still awaiting review rather than approved.
- Refresh the browser and confirm the saved draft, IDs, fields, and order persist.
- Approve the Outcomes explicitly.
- Confirm Research becomes available as the next stage.

**Expected result**

- The deterministic proposal is structured.
- Retained and edited canonical IDs remain stable and unique; reordering does not
  renumber them.
- Backend domain logic assigns a deterministic collision-free canonical ID to the added
  Outcome; clients cannot supply it, request-local client order references do not
  persist, and a removed canonical ID is never reused by a later addition.
- The removed Outcome is absent only after confirmation.
- The saved decision contains one unambiguous complete order matching the visible order.
- An omitted or empty order remains backward compatible by using selected Outcome order
  followed by addition order, while any supplied nonempty order must be complete.
- The save returns a canonical draft, survives refresh, and does not auto-approve.
- Advisory vague-verb, duplicate/near-duplicate, and weak-evidence findings are
  structured and nonblocking when hard validation passes.
- Editing availability comes from backend capabilities. An approved artifact does not
  become directly editable without impact-confirmed Reopen.
- Unsaved edits warn before navigation. A stale save rebases nonoverlapping work onto the
  latest canonical artifact and requires explicit resolution for overlapping field or
  order changes before resubmission.
- Explicit approval succeeds only after the server revalidates the complete collection.
- Research becomes ready.

### A5 — Research and explicit source decision

**Operator action**

- Run Research.
- Inspect candidate preview/trust/coverage.
- Select at least two sources.
- Reject at least one source.
- Add one known deterministic test URL as a proposed source, then decide whether to
  approve or reject it.
- Save source decision and approve Research.

**Expected result**

- Competitor evidence is labelled separately.
- Candidate discovery does not count as approval.
- Only selected, available, content-bearing sources enter the registry.
- Rejected/competitor/contentless sources remain downstream-ineligible.
- Course Model becomes ready.

### A6 — Generate and edit Course Model

**Current checkpoint status:** The NC-401 through NC-403 backend portion is independently
verified. NC-404 and NC-405 passed independent review with deterministic browser evidence
for the operator actions below, including allocated request-local IDs and the added,
renamed, and moved/reordered diff before save. NC-406 is independently verified behind
NC-904.

**Operator action**

- Run Course Model.
- Rename one subtopic.
- Add one coverage requirement to the troubleshooting subtopic.
- Reorder two subtopics or move one within its module.
- Preview and acknowledge downstream impact, then save the canonical draft.
- Refresh and verify the edited structure persists.
- Approve.

**Expected result**

- Backend generates/maintains stable IDs.
- Integrity passes after the operation batch.
- Source and outcome references resolve.
- The impact preview identifies Blueprint and later artifacts.
- Blueprint becomes ready.

### A7 — Generate and edit Blueprint

**Current checkpoint status:** Passed under independently reviewed NC-501 through
NC-503. The deterministic browser scenario persists and refreshes the exact 17-unit
selection, verifies authoritative source routes, approves Blueprint, and observes
Student Content become ready. NC-504 live revision remains deferred.

**Operator action**

- Run Blueprint.
- Select an Activity for one subtopic.
- Remove an optional asset from another.
- Change depth/time or example count for the troubleshooting subtopic.
- Keep Course Content selected.
- Approve.

**Expected result**

- Visible selections exactly match the saved Blueprint.
- Every subtopic has a valid plan.
- Source routes use approved sources only.
- Selected asset count becomes the expected Student Content unit count.

### A8 — Generate content with deliberate findings

**Current checkpoint status:** Passed under independently reviewed NC-801 through
NC-808. Browser evidence projects source-less and unattributed findings as hard
blockers, keeps the exact asset review control disabled, exposes a target-specific
repair action, and refreshes from canonical backend state after repair.

The deterministic verifier should produce at least:

1. one missing-attribution or content-error blocker repairable with existing evidence;
2. one unsupported/evidence-gap blocker requiring better evidence;
3. one partial finding that requires human review but is not a hard blocker.

**Operator action**

- Run Student Content.
- Observe real per-unit progress.
- Inspect the asset, claims, sources, and findings.

**Expected result**

- Generated assets exactly match selected Blueprint assets.
- Rejected sources do not appear.
- Content state is `requires_attention`.
- Mark-reviewed is disabled for assets with hard blockers.
- Partial evidence remains visible.

### A9 — Repair with existing evidence

**Current checkpoint status:** Passed under independently reviewed NC-801 through
NC-808. Browser and backend evidence prove exact target-only regeneration and
reverification, changed-fingerprint review reset, unchanged asset hashes, and truthful
remaining blocker state.

**Operator action**

- Choose “Revise with approved evidence” for the first blocker.
- Confirm the targeted asset and finding.

**Expected result**

- Only the named asset regenerates.
- The asset is reverified.
- Its prior review decision resets.
- Unaffected asset hashes remain identical.
- Remaining blockers continue to hold `requires_attention`.

### A10 — Repair with better evidence

**Current checkpoint status:** Passed across independently reviewed NC-701 through
NC-709 and NC-801 through NC-808. NC-70 proves candidate review, human source decision,
and the exact atomic route through `awaiting_content_repair`; NC-80 proves the dependent
targeted regeneration, reverification, blocker outcome, review synchronization,
Source Repair lifecycle closure, and unchanged-asset hashes.

**Operator action**

- Choose “Find better evidence” for the evidence-gap blocker.
- Review deterministic repair candidates.
- Approve one source.
- Confirm its subtopic/asset route.
- Run targeted regeneration and reverification.

**Expected result**

- A Source Repair entry records the complete flow.
- The source is not approved before the human decision.
- Dossier, registry, Course Model route, and Blueprint route update atomically.
- No structure or unrelated asset selection changes.
- Only named assets regenerate.
- The blocker clears if the new evidence supports it.
- Unaffected asset hashes remain identical.

### A11 — Complete content review and approval

**Current checkpoint status:** Passed under independently reviewed NC-801 through
NC-808. Browser evidence keeps partial findings visible but nonblocking, requires every
blocker-free changed review to become current, approves Content only at zero hard
blockers with current reviews, and then exposes Lesson Plan as ready.

**Operator action**

- Inspect the partial finding.
- Mark every blocker-free asset reviewed.
- Approve Student Content.

**Expected result**

- Hard blocker total is zero.
- Every review record is approved/current.
- Content becomes approved.
- Lesson Plan becomes ready.

### A12 — Generate and edit Lesson Plan

**Current checkpoint status:** Passed under independently reviewed NC-601 through
NC-603. The deterministic browser scenario runs the real Lesson Plan stage, changes the
duration and one delivery mode, persists delivery details, refreshes, verifies exact
Course Model coverage and exact affected-session IDs, approves, and observes Package
become ready. NC-604 live revision remains deferred.

**Operator action**

- Run Lesson Plan.
- Change maximum session duration.
- Move one segment between live and self-study.
- Approve.

**Expected result**

- Affected sessions update.
- Every generated Course Model subtopic appears exactly once.
- Duration and mode constraints are valid.
- Package becomes ready.

### A13 — Render and inspect Package

**Operator action**

- Run Package.
- Select several files in the tree.
- Inspect their actual Markdown inline.
- Approve Package.

**Expected result**

- Integrity passes.
- Source leakage is zero.
- Selected/generated/rendered assets reconcile.
- Human-review and hard-blocker counts are zero.
- Inline preview matches raw file contents.
- Operator status becomes `complete`.

## 6. Scenario B — Reopen, impact, and stale recovery

Run this as a separate deterministic browser scenario so it does not make Scenario A
unnecessarily long.

### B1 — Reopen an approved upstream stage

- Start from a fully approved deterministic course.
- Open approved Course Model.
- Click Reopen.
- Inspect and confirm impact.

**Expected:** Course Model becomes editable; affected downstream artifacts become stale;
their bodies remain inspectable.

### B2 — Make a bounded structural change

- Rename or rescope one subtopic.
- Save and reapprove Course Model.

**Expected:** Blueprint is stale/ready to rerun; unrelated prior bodies remain available;
later stages cannot falsely remain complete.

### B3 — Rerun downstream stages

- Rerun/reapprove Blueprint, affected Content, Lesson Plan where required, and Package.

**Expected:** Resume skips unaffected approved work where the contract permits; final
status returns to complete only after all checkpoints pass.

### B4 — Stale browser conflict

- Open the same artifact in two browser contexts.
- Save in the first.
- Attempt save in the second with the old checksum.

**Expected:** The second save receives a conflict, does not overwrite data, and offers a
refresh/review path.

## 7. Scenario C — Failure, restart, and retry

### C1 — Provider/step failure

- Force a deterministic stage implementation to fail after job start.

**Expected:** Job becomes failed; last valid artifact remains unchanged; safe error and
retry appear; no empty artifact is approved.

### C2 — API restart during a job

- Start a controlled long-running job.
- restart the API process.

**Expected:** Interrupted job is marked failed; the workspace recovers from persisted
state; rerun is safe.

### C3 — Refresh/navigation during work

- Start Student Content.
- Refresh the browser.

**Expected:** Active job is rediscovered, progress resumes, and navigation does not start
a competing mutation.

### C4 — Concurrent mutation

- Attempt two mutating commands for the same course.

**Expected:** One owns the mutation lock; the other receives a clear conflict without
partial writes.

## 8. Scenario D — Negative trust and security gates

Automate these API/browser checks:

1. Approve Research without a saved source decision — rejected.
2. Select an unknown/unavailable/contentless source — rejected.
3. Force a rejected source ID into a Course Model command — rejected.
4. Remove Course Content without an anchor waiver — rejected.
5. Generate an unselected asset directly — rejected.
6. Approve Content with a hard verifier blocker — rejected.
7. Approve Content with a pending human review — rejected.
8. Approve Package with selected/rendered mismatch — rejected.
9. Mutate a committed example course — rejected.
10. Use a stale expected checksum — rejected.
11. Attempt output path traversal — rejected.
12. Send unknown fields in strict command bodies — rejected.
13. Submit an unsupported generic revision — rejected before job creation.
14. Submit a revision with an ambiguous target — rejected before job creation.
15. Attempt to run a locked stage — rejected with blocking prerequisites.
16. Submit an Outcomes decision while the Brief is unresolved, unapproved, stale, or
    invalid — rejected without changing Outcomes.
17. Submit a malformed, incomplete-order, scope-escaping, or no-op Outcomes decision —
    rejected without changing the previous valid artifact.
18. Attempt to approve structurally invalid Outcomes — rejected without recording
    approval.

## 9. Scenario E — Bounded live-agent acceptance

This is a formal manual/semi-automated run using the real provider and research path.

### E1 — Preflight

- Confirm provider readiness through the UI.
- Confirm a clean course ID and bounded subject.
- Confirm expected selected-asset range.
- Record model/provider configuration and cache state.

### E2 — Run the same operator journey

Follow the same stages and decisions as Scenario A. At minimum, exercise:

- one conditional Brief clarification;
- one Outcomes edit or live scoped revision;
- explicit source approval/rejection;
- one Course Model edit or live scoped revision;
- one Blueprint asset/depth change;
- live content generation and independent verification;
- repair of any hard blocker, or a controlled repair demonstration if none appears;
- Lesson Plan constraint change;
- actual Package inspection.

### E3 — Confirm live implementation coverage

The activity/diagnostic record must show real live execution for:

- bounded Brief clarification or synthesis where requested;
- Outcomes;
- Research;
- Course Model;
- Blueprint;
- Student Content;
- Verification;
- Lesson Plan.

Package remains deterministic and should be reported as such.

### E4 — Live quality and safety checks

- Every output validates against its artifact schema.
- Course Model integrity passes.
- Selected assets match generated assets.
- Approved-source routing is enforced.
- Rejected-source leakage is zero.
- Unaffected assets survive targeted revision.
- Hard verifier blockers are zero at final approval.
- All human review records are approved/current.
- Final Package integrity and reconciliation pass.

### E5 — Cost/call evidence

Record by stage:

- call count;
- input/output tokens;
- estimated cost;
- cache hits;
- retry count;
- maximum input size;
- selected/generated asset count.

The first accepted live run establishes the baseline rather than an arbitrary permanent
budget. The run fails the operational gate if calls are unbounded, unexplained, or lack
stage attribution.

## 10. Automated coverage matrix

| Capability | Unit/domain | API contract | React component | Browser E2E | Live/manual |
|---|---:|---:|---:|---:|---:|
| Stage state/capability | Required | Required | Required | Required | Observe |
| Impact/invalidation | Required | Required | Required | Required | Observe |
| Brief questions | Required | Required | Required | Required | Required |
| Outcomes decision | Required | Required | Required | Required | Required |
| Source decision | Required | Required | Required | Required | Required |
| Course Model operations | Required | Required | Required | Required | Required |
| Blueprint decision | Required | Required | Required | Required | Required |
| Content generation | Required | Required | Status/UI | Required | Required |
| Verification | Required | Required | Required | Required | Required |
| Source repair | Required | Required | Required | Required | Required |
| Content review | Required | Required | Required | Required | Required |
| Lesson Plan decision | Required | Required | Required | Required | Required |
| Package preview/gate | Required | Required | Required | Required | Required |
| Failure/recovery | Required | Required | Required | Required | Controlled smoke |
| Security/path/read-only | Required | Required | N/A | Selected cases | N/A |
| Progress/activity | Event tests | Required | Required | Required | Required |
| Accessibility | N/A | N/A | Required | Required | Pilot observation |

## 11. Internal course-director pilot

### 11.1 Pilot objective

Determine whether the product matches how a nontechnical internal course director wants
to work, not merely whether engineering can demonstrate it.

### 11.2 Operator setup

Provide only:

- normal application startup instructions;
- the application URL;
- confirmation that provider readiness is green;
- a short statement of the course-building goal.

Do not provide:

- terminal artifact commands;
- JSON editing instructions;
- hidden source IDs;
- scripted click-by-click coaching;
- explanations of internal stage implementation unless requested after the task.

### 11.3 Pilot task brief

Ask the director to:

> Build a sample course that you would be comfortable handing to another internal
> reviewer. Correct the system whenever its proposal does not match your intent. Use the
> available evidence and verification tools to resolve problems, and finish only when
> you believe the Package is ready for review.

The observer may remind them of the overall goal but should not tell them which control
to click.

### 11.4 Required pilot behaviors

The course director must naturally complete or be prompted by the task to complete:

- bounded intake;
- one upstream edit;
- explicit source decisions;
- one structure or Blueprint change;
- content review;
- one repair path;
- Lesson Plan review/change;
- Package inspection and final decision.

### 11.5 Observation scorecard

Record each item as pass, friction, or failure.

| Area | Question |
|---|---|
| Orientation | Can the director identify the current stage and next action? |
| Intake | Are required and conditional questions understandable and proportionate? |
| Trust | Can they distinguish an agent recommendation from their decision? |
| Editing | Can they find and complete the correction they expect? |
| Impact | Do they understand what a change will invalidate? |
| Sources | Can they judge and approve/reject evidence confidently? |
| Verification | Can they understand why a claim is blocked or partial? |
| Repair | Can they choose between revising content and finding evidence? |
| Progress | Can they tell whether the system is working, waiting, or failed? |
| Recovery | Can they recover from an induced safe failure? |
| Package | Can they inspect actual deliverables and understand readiness? |
| Independence | Did they finish without terminal, JSON, or engineering intervention? |

Also record:

- time spent per stage, for observation rather than a hard target;
- repeated backtracking;
- controls they expected but could not find;
- terminology they misunderstood;
- ignored or surprising actions;
- revisions that changed too much or too little;
- content-quality concerns;
- desired workflow changes.

## 12. Issue classification

### Release blocker

Any of the following:

- data loss or silent overwrite;
- false `complete` or false approval;
- rejected-source leakage;
- an enabled action that is ignored or does something materially different;
- inability to complete a required checkpoint;
- repair regenerates unrelated assets without warning;
- terminal or raw JSON required;
- engineering intervention required to recover a normal failure;
- live mode silently uses deterministic output;
- credentials or unsafe private data exposed.

### Major workflow defect

- the director can finish only after coaching;
- impact or blocker information is materially unclear;
- an expected consequential edit is unavailable;
- recovery is possible but confusing;
- actual output cannot be inspected in the product.

### Minor usability defect

- wording, spacing, discoverability, or navigation friction that does not require
  coaching and does not threaten trust.

### Product preference

- a reasonable alternative workflow or presentation preference that does not break the
  agreed acceptance journey.

## 13. Pilot pass/fail rule

The pilot passes when:

- there are zero release blockers;
- the director completes without terminal, JSON, or engineering intervention;
- stage and release statuses remain truthful;
- source and verifier gates work;
- the repair path completes with bounded impact;
- the actual Package is inspectable;
- remaining findings are minor defects or prioritized product preferences.

If a release blocker or major workflow defect is fixed, the director repeats the
affected path without coaching before the pilot is considered passed.

## 14. Final release evidence checklist

- [ ] Deterministic Scenario A passes.
- [ ] Reopen/stale Scenario B passes.
- [ ] Failure/recovery Scenario C passes.
- [ ] Negative gate Scenario D passes.
- [ ] Bounded live Scenario E passes.
- [ ] Python regression suite passes.
- [ ] Frontend unit/component suite passes.
- [ ] Browser acceptance suite passes.
- [ ] Accessibility checks pass on the primary path.
- [ ] Integrity passes for deterministic and live courses.
- [ ] Rejected-source leakage is zero.
- [ ] Selected/generated/rendered assets reconcile.
- [ ] Hard verifier blockers are zero at final status.
- [ ] Required content reviews are approved/current.
- [ ] Live call/cost evidence is retained.
- [ ] Internal course-director pilot passes.
- [ ] Master Context and implementation handoff are updated.

The cycle closes only when the evidence above supports the product claim, not when all
planned code has merely been merged.
