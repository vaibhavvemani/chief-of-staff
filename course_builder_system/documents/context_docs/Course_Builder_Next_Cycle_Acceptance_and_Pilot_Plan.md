# Course Builder — Next Cycle Acceptance and Pilot Plan

> **Status:** Acceptance baseline for implementation and release  
> **Updated:** 2026-07-15  
> **Target user:** One internal, nontechnical course director  
> **Parent plan:** `Course_Builder_Next_Development_Cycle_Plan.md`  
> **Backlog:** `Course_Builder_Next_Cycle_Implementation_Backlog.md`  
> **Technical contracts:** `Course_Builder_Next_Cycle_Technical_Contract_Plan.md`

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

### 3.2 Live acceptance subject

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
- Edit one outcome to make evidence more observable.
- Reorder two outcomes.
- Approve.

**Expected result**

- The deterministic proposal is structured.
- Stable IDs remain unique.
- The saved decision matches the visible order.
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

**Operator action**

- Run Course Model.
- Rename one subtopic.
- Add one coverage requirement to the troubleshooting subtopic.
- Reorder two subtopics or move one within its module.
- Review impact and commit.
- Approve.

**Expected result**

- Backend generates/maintains stable IDs.
- Integrity passes after the operation batch.
- Source and outcome references resolve.
- The impact preview identifies Blueprint and later artifacts.
- Blueprint becomes ready.

### A7 — Generate and edit Blueprint

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
