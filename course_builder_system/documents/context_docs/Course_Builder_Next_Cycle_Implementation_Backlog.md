# Course Builder — Next Cycle Implementation Backlog

> **Status:** NC-100 independently verified; NC-110 next
> **Updated:** 2026-07-20
> **Planning model:** Dependency and exit-gate driven; no fixed calendar estimate  
> **Parent plan:** `Course_Builder_Next_Development_Cycle_Plan.md`  
> **Technical contracts:** `Course_Builder_Next_Cycle_Technical_Contract_Plan.md`  
> **Acceptance:** `Course_Builder_Next_Cycle_Acceptance_and_Pilot_Plan.md`

## 1. Purpose

This backlog turns the next-cycle milestones into implementation-sized work packages.
It is intended to be the source for issue tracker tasks, engineering handoffs, and
implementation sequencing.

The backlog deliberately avoids week estimates. Work begins with lifecycle correctness,
then unlocks stage interaction work, source/content repair, live-agent parity, and the
operator pilot.

## 2. Priority definitions

| Priority | Meaning |
|---|---|
| `P0-D` | Required for the deterministic operator-ready gate. |
| `P0-L` | Required for the live-agent gate. |
| `P0-P` | Required for the internal operator pilot/release gate. |
| `P1` | Valuable within the cycle, but may not delay the release gate unless pilot evidence promotes it. |
| `Deferred` | Explicitly outside the cycle. |

Most tasks are release tasks. The labels distinguish which gate they first block, not
whether they matter.

## 3. Common task definition of done

Unless a task says otherwise, it is complete only when:

1. the backend/domain contract is implemented;
2. the frontend exposes the action truthfully when applicable;
3. expected-checksum concurrency is preserved;
4. read-only examples remain protected;
5. course mutation locking remains correct;
6. affected and preserved artifacts are verified;
7. focused unit/contract tests pass;
8. relevant component/browser coverage is added;
9. existing Python and frontend regression suites pass;
10. context documents are updated if the implemented behavior differs from the plan.

## 4. Dependency overview

Implementation checkpoint (2026-07-20): NC-002 through NC-005, NC-101 through
NC-109, NC-201 through NC-207, NC-301, and NC-302 are independently verified. NC-401
through NC-403 passed independent NC-40
backend checkpoint review on 2026-07-20 after corrective hardening. NC-40 is not
complete. NC-404 is independently verified with deterministic browser Scenario A6
evidence. NC-405 is independently verified with deterministic browser Scenario A6 diff
evidence. NC-501 through NC-503 are independently verified with deterministic browser
Scenario A7 evidence after corrective lifecycle/source-authority hardening. NC-601
through NC-603 are independently verified with
deterministic browser Scenario A12 evidence after corrective conflict-rebase, stable-ID,
Course Model-authority, and affected-session hardening. NC-701 through NC-709 are
independently verified with deterministic
browser evidence for Scenario A10's source-decision and route phase. NC-801 through
NC-808 are independently verified with deterministic browser Scenarios A8 through A11
evidence, including both repair strategies, target-only regeneration, truthful blocker
and review state, and typed failure/restart recovery. NC-901 through NC-912 and scoped
live revisions NC-303, NC-406, NC-504, and NC-604 passed independent NC-90 checkpoint
review. NC-1001 through NC-1007 passed independent NC-100 checkpoint review with real
progress, safe persisted activity and call diagnostics, readiness gates across all live
starts, actual safe Markdown rendering, actionable backend-owned Package blockers, and
acceptance-path accessibility evidence. NC-110 and later packages remain unstarted. This
status note does not mark Milestone 3 or the cycle complete.

```text
NC-00 acceptance foundation
  -> NC-10 lifecycle and command foundation
      -> NC-20 guided Brief intake
      -> NC-30 Outcomes decisions
      -> NC-40 Course Model decisions
      -> NC-50 Blueprint decisions
      -> NC-60 Lesson Plan decisions
          -> NC-70 source quality and source repair
              -> NC-80 content repair and review closure
                  -> NC-90 live-agent parity
                      -> NC-100 progress, diagnostics, and Package completion
                          -> NC-110 deterministic/live browser acceptance
                              -> NC-120 internal pilot and release decision
```

After NC-10 is stable, NC-20, NC-30, NC-40, NC-50, and the command-contract portion of
NC-60 may proceed in parallel. Source repair and live parity remain integration-heavy
and should converge through the main agent responsible for shared contracts.

## 5. Work package NC-00 — Acceptance foundation

### Goal

Create executable acceptance boundaries before changing lifecycle code.

### Tasks

#### NC-001 — Approve planning package

- **Priority:** P0-D
- **Dependencies:** None
- Review the next-cycle plan, technical contract plan, backlog, and acceptance plan.
- Record any changed decision in the documents before implementation.

**Acceptance:** The planning start gate in the technical contract plan has no unresolved
blocker.

#### NC-002 — Establish deterministic acceptance course

- **Priority:** P0-D
- **Dependencies:** NC-001
- Use a dedicated runtime/test ID rather than modifying committed fixtures in place.
- Base the deterministic subject on the existing coffee fixture path.
- Add deterministic controls for a known verifier blocker and its repair.
- Define expected source, Course Model, Blueprint, content, review, and Package outputs.

**Acceptance:** The scenario can be reset and rerun without network or model access.

#### NC-003 — Establish live pilot subject boundary

- **Priority:** P0-L
- **Dependencies:** NC-001
- **Status:** Resolved on 2026-07-20 with the documented fallback subject.
- The internal director selects a non-high-stakes subject before live parity validation.
- The fallback subject is indoor herb gardening for apartment beginners.
- Keep the live pilot to approximately four to six subtopics and a representative asset
  set so quality and repair remain reviewable.

Recorded boundary:

- **Course ID:** `studio-live-pilot`.
- **Audience:** apartment beginners with no outdoor growing space assumed.
- **Practical result:** set up and maintain three container-grown culinary herbs, use a
  simple care/troubleshooting log, and make a first routine harvest.
- **Five subtopics:** assess the indoor site; select herbs/containers/growing medium;
  plant starters or seeds; manage light/water/feeding/rotation; harvest and troubleshoot
  common problems.
- **Ten-asset review envelope:** five `course_content` assets, two `activities`, one
  `case_study`, one `assessment`, and one `resources` asset.
- **Exclusions:** medicinal or therapeutic use, commercial production, pesticide
  prescriptions, electrical grow-light installation, and any claim requiring legal,
  medical, financial, or other expert sign-off.
- **Public grounding examples:** Penn State Extension's [Growing Herbs
  Indoors](https://extension.psu.edu/growing-herbs-indoors), University of Minnesota
  Extension's [Growing herbs in home
  gardens](https://extension.umn.edu/gardening-minnesota/growing-herbs), and the Royal
  Horticultural Society's [Growing herbs in
  containers](https://www.rhs.org.uk/herbs/containers).

**Acceptance:** The subject has accessible public sources, no mandatory high-stakes
expert sign-off, and a clearly bounded practical result.

#### NC-004 — Create capability-map regression test

- **Priority:** P0-D
- **Dependencies:** NC-001
- Encode which stage states/actions are valid.
- Protect the absence of generic/fake actions.
- Make the test behavior-based where possible; do not rely only on source-string checks.

**Acceptance:** A stage cannot expose an action without a registered backend capability.

#### NC-005 — Scaffold browser acceptance

- **Priority:** P0-D
- **Dependencies:** NC-002
- Add Playwright configuration and a deterministic API/server test harness.
- Implement course creation and workspace load as the first smoke path.
- Provide isolated temporary artifact, runtime, and render roots.

**Acceptance:** CI/local execution can launch the app, create an isolated course, and
inspect the Brief route in a real browser.

### Deterministic package exit gate

- Deterministic and live subject boundaries are defined.
- Browser acceptance can run in isolation.
- The target capability map is executable.

## 6. Work package NC-10 — Lifecycle and command foundation

### Goal

Make stage state, reopening, impact, invalidation, approval, and revisions reliable.

### Tasks

#### NC-101 — Add target stage-state vocabulary

- **Priority:** P0-D
- **Dependencies:** NC-004
- Add `needs_input` to backend and frontend state contracts.
- Preserve locked, ready, running, awaiting review, attention, approved, stale, and
  failed semantics.
- Add exhaustive state normalization tests.

**Acceptance:** Every stage state returned by the API has one documented UI treatment
and primary action.

#### NC-102 — Implement dependency-graph invalidation service

- **Priority:** P0-D
- **Dependencies:** NC-101
- Use `PipelineCatalog` consumes/produces relationships.
- Mark affected approved outputs stale after consequential upstream changes.
- Preserve stale bodies.
- Support explicit bounded-impact overrides only for registered domain operations.

**Acceptance:** Brief, Outcomes, source, Course Model, Blueprint, content, and Lesson Plan
changes produce the expected stale artifact set in contract tests.

#### NC-103 — Implement impact preview

- **Priority:** P0-D
- **Dependencies:** NC-102
- Add a typed dry-run impact service/endpoint.
- Return direct artifacts, stale artifacts, targeted/preserved assets, rerun stages, and
  warnings.
- Recompute impact under the mutation lock before committing.

**Acceptance:** A stale preview/checksum cannot authorize a mutation; a fresh preview
matches the committed impact.

#### NC-104 — Harden server-side approval guards

- **Priority:** P0-D
- **Dependencies:** NC-101
- Implement the per-stage guard matrix from the technical contract plan.
- Return structured failures with stage/record IDs.
- Prevent Content and Package approval with blockers or pending reviews.

**Acceptance:** Direct API requests cannot bypass any release gate.

#### NC-105 — Wire explicit reopen in the API client and UI

- **Priority:** P0-D
- **Dependencies:** NC-102, NC-103
- Add frontend transport for reopen.
- Show impact before confirmation.
- Preserve and display the current body after reopening.
- Navigate to the newly editable review state.

**Acceptance:** An approved Brief and an approved Course Model can be reopened from the
browser and cause the correct downstream stale state.

#### NC-106 — Register stage capabilities and revision handlers

- **Priority:** P0-D
- **Dependencies:** NC-101
- Create one backend source of truth for supported direct decisions, revisions, repairs,
  retries, and reopen.
- Project valid actions with stage state.
- Remove frontend guesses based only on status.

**Acceptance:** The frontend action bar renders only actions returned as valid by the
backend capability projection.

#### NC-107 — Replace generic revision payload

- **Priority:** P0-D
- **Dependencies:** NC-106
- Add target type, target IDs, category, instruction, mode, and checksum.
- Reject ambiguous/unsupported revisions before queuing.
- Detect/report no-op revisions.

**Acceptance:** Course Model, Blueprint, or Lesson Plan feedback cannot be accepted and
then ignored.

#### NC-108 — Preserve last valid artifact on job failure

- **Priority:** P0-D
- **Dependencies:** NC-101
- Verify stage runs write new artifacts only after valid output is available.
- Persist safe failure state in jobs/events.
- Add retry from failed/stale states.

**Acceptance:** A forced provider or step failure leaves the previous artifact body
unchanged and exposes a safe retry.

#### NC-109 — Remove placeholder and fake enabled controls

- **Priority:** P0-D
- **Dependencies:** NC-106
- Audit Settings, diagnostics, add/edit buttons, revision actions, and Package actions.
- Implement, disable with a truthful explanation, or remove each one.

**Acceptance:** The capability-map browser test finds no enabled control without an
observable result.

### Package exit gate

- Reopen and impact work end to end.
- Downstream stale state is deterministic.
- Approval cannot be bypassed.
- Unsupported revisions cannot start.
- Failure preserves the last valid artifact.

## 7. Work package NC-20 — Guided Brief intake

**Implementation status (2026-07-17): independently checkpointed.** NC-201 through
NC-207 pass the deterministic package exit gate, including historical normalization,
negative API gates, concurrency conflicts, and the isolated Playwright intake/reopen
path.

### Goal

Implement required and conditional question rounds without turning intake into chat.

### Tasks

#### NC-201 — Extend Brief body with intake state

- **Priority:** P0-D
- **Dependencies:** NC-101
- Add explicit fields, accepted defaults, unresolved required fields, answered question
  IDs, and gap-analysis summary.
- Migrate/normalize historical Briefs without breaking snapshots.

**Acceptance:** Current fixtures project a valid intake state; new courses distinguish
human answers from accepted defaults.

#### NC-202 — Serialize QuestionSpec through API models

- **Priority:** P0-D
- **Dependencies:** NC-201
- Expose prompt, rationale, type, options, default, required/skip rules, and visibility.
- Keep conditional logic in Python.

**Acceptance:** API tests prove conditional live-teaching questions appear only for
applicable modalities.

#### NC-203 — Merge and persist answer rounds

- **Priority:** P0-D
- **Dependencies:** NC-202
- Merge answers with the current draft instead of rebuilding from subject defaults.
- Preserve previously explicit answers.
- Recompute unresolved required fields and gap analysis.

**Acceptance:** Refresh and multiple answer rounds do not lose or reset earlier answers.

#### NC-204 — Project Brief needs-input state

- **Priority:** P0-D
- **Dependencies:** NC-201, NC-203
- Return `needs_input` while mandatory fields/default acceptance remain unresolved.
- Return review state when complete.

**Acceptance:** The user cannot approve an unresolved Brief or run later stages.

#### NC-205 — Build typed question-round UI

- **Priority:** P0-D
- **Dependencies:** NC-202, NC-204
- Render no more than five deterministic questions in a round.
- Show why each question matters.
- Support visible default acceptance and optional skips.
- Maintain accessible validation/focus.

**Acceptance:** The deterministic browser scenario completes required intake without raw
JSON or generic free text.

#### NC-206 — Add bounded clarification contract and deterministic gap pass

- **Priority:** P0-D
- **Dependencies:** NC-203, NC-205
- Run deterministic gap detection in both modes.
- Define the injectable boundary used later by the live clarifier.
- Enforce at most three additional questions over eligible fields.
- Reject invented fields and repeated resolved questions in the deterministic validator.

**Acceptance:** Sparse/conflicting inputs receive relevant deterministic questions;
complete inputs do not receive unnecessary questions; the contract is ready for NC-909.

#### NC-207 — Preserve direct Brief editing and explicit reopen

- **Priority:** P0-D
- **Dependencies:** NC-105, NC-203
- Use the same merge/validation path for section edits.
- Require reopening an approved Brief before saving.

**Acceptance:** Direct edits do not bypass impact confirmation or reset unrelated fields.

### Deterministic package exit gate

- Mandatory intake is enforced.
- Conditional questions are bounded.
- Answers survive refresh.
- Approved Brief editing uses reopen and impact.

## 8. Work package NC-30 — Outcomes decisions

**Implementation status (2026-07-20):** NC-301 and NC-302 have passed independent
checkpoint review. NC-303 is independently verified behind NC-902.
NC-401 through NC-403 are independently verified after the NC-40 backend checkpoint.
NC-404 is independently verified with deterministic browser Scenario A6 evidence.
NC-405 is independently verified with deterministic browser evidence. NC-40 is not
complete. NC-501 through NC-503 and NC-601 through NC-603 are independently verified.
NC-406, NC-504, and NC-604 are independently verified behind their NC-90 dependencies. NC-701
through NC-709, NC-801 through NC-808, NC-901 through NC-912, and NC-1001 through
NC-1007 are independently verified. NC-110 is the next package.

### Tasks

#### NC-301 — Complete Outcomes reducer validation

- **Priority:** P0-D
- **Dependencies:** NC-104
- **Status:** Independently verified.
- Validate the complete resulting collection across additions, edits, removal, stable
  IDs, deterministic backend ID allocation, priority order, and minimum selection.
- Reject strict-payload, type, enum, length, target, collision, ambiguity, and no-op
  failures without changing the previous valid artifact.
- Resolve request-local addition references into canonical IDs. A supplied nonempty
  priority order is complete; omitted or empty order falls back to selected-ID order
  followed by addition order.
- Reject client-supplied canonical IDs for additions and persist a monotonic backend
  allocation cursor so removed IDs are never reused.
- Return structured nonblocking advisories for vague verbs, duplicate or near-duplicate
  statements, and mechanically weak evidence.

#### NC-302 — Build Outcomes editor

- **Priority:** P0-D
- **Dependencies:** NC-301, NC-105
- **Status:** Independently verified.
- Add, edit, confirm removal, and keyboard-reorder Outcomes and evidence; change
  cognitive level and priority without renumbering canonical IDs.
- Use backend-projected edit, approve, and reopen capabilities; do not recreate Brief or
  lifecycle gates in React.
- Show structured advisory quality checks and field-level validation accessibly.
- Warn on unsaved navigation and rebase nonoverlapping stale changes while requiring an
  explicit choice for overlapping field or order conflicts.
- Save the canonical result as a draft, preserve it across refresh, and require separate
  explicit approval.

#### NC-303 — Add scoped Outcomes revision

- **Priority:** P0-L
- **Dependencies:** NC-107, NC-902
- **Status:** Independently verified behind NC-902.
- Target named outcomes/categories.
- Reduce live output through the Outcomes validator.

### Deterministic package exit gate

- Deterministic evidence shows that the operator can make a complete structural Outcomes
  change in the browser, save it as a durable draft, refresh, and approve it explicitly.
- Backend validation, stable IDs, capability/reopen gates, and catalog-driven downstream
  invalidation remain authoritative.

The live revision requirement closes with NC-303 during NC-90. It must change only named
Outcomes and preserve stable IDs where possible.

## 9. Work package NC-40 — Course Model decisions

**Implementation status (2026-07-20):** NC-401 through NC-403 passed independent NC-40
backend checkpoint review after corrective hardening. This does not complete NC-40.
NC-404 is independently verified with deterministic browser Scenario A6 evidence.
NC-405 is independently verified with deterministic browser Scenario A6 diff evidence.
NC-501 through NC-503 are independently verified with deterministic browser Scenario A7
evidence. NC-406, NC-504, and NC-604 are implemented behind their NC-90 dependencies
and independently verified. NC-601 through NC-603 are independently verified with
deterministic browser Scenario A12 evidence. NC-701 through NC-709 and NC-801 through
NC-808, NC-901 through NC-912, and NC-1001 through NC-1007 are independently verified;
NC-110 is the next package.

### Tasks

#### NC-401 — Define typed Course Model operations

- **Priority:** P0-D
- **Dependencies:** NC-103, NC-107
- **Status:** Independently verified.
- Implement add, update, remove, move, reorder, and assign-source operations.
- Make operation batches atomic.
- Resolve only earlier typed request-local references; reject guessed future canonical
  IDs even when a later allocation would otherwise produce the guessed value.

#### NC-402 — Implement stable ID allocation

- **Priority:** P0-D
- **Dependencies:** NC-401
- **Status:** Independently verified.
- Generate new module, subtopic, concept, and coverage IDs through domain logic.
- Never reuse an ID within a course.
- Persist per-family retired-ID history so legacy generated IDs, canonical IDs, and
  cascaded descendants remain retired across API and CLI generation reruns.

#### NC-403 — Validate operation batches

- **Priority:** P0-D
- **Dependencies:** NC-401, NC-402
- **Status:** Independently verified.
- Run Course Model integrity and source-eligibility checks before save.
- Reject unresolved dependency/outcome/source references.
- Fail closed on unsupported checked-in schema keywords, validate Outcome and Research
  authority shapes, and reconcile approved source metadata/status to research candidates.

#### NC-404 — Build Course Model edit UI

- **Priority:** P0-D
- **Dependencies:** NC-403, NC-105
- **Status:** Independently verified with deterministic browser Scenario A6 evidence.
- Support consequential controls listed in the technical capability matrix.
- Show impact before commit.

#### NC-405 — Add Course Model diff summary

- **Priority:** P0-P
- **Dependencies:** NC-404
- **Status:** Independently verified with deterministic browser Scenario A6 evidence.
- Show added, removed, renamed, moved, scope-changed, and source-changed records.

#### NC-406 — Add scoped live Course Model revision

- **Priority:** P0-L
- **Dependencies:** NC-403, NC-904
- **Status:** Independently verified behind NC-904.
- Ask the model for structured operations, not a replacement artifact.
- Validate/reduce through the same batch service.

### Deterministic package exit gate

- The operator can change structure without hand-editing JSON.
- Invalid references cannot be saved.
- Downstream impact is correct.

The live proposal/revision requirement closes with NC-406 during NC-90 and must pass
through the same typed operations.

## 10. Work package NC-50 — Blueprint decisions

**Implementation status (2026-07-20):** NC-501 through NC-503 passed independent
checkpoint review with deterministic browser Scenario A7 evidence. Corrective review
closed draft/stale Course Model mutation and rejected/contentless source-route leaks
with exact no-mutation regressions. NC-504 is independently verified behind NC-905.

### Tasks

#### NC-501 — Finalize Blueprint decision contract tests

- **Priority:** P0-D
- **Dependencies:** NC-104
- **Status:** Independently verified.
- Cover defaults, selected assets, overrides, unknown IDs, empty selections, and anchor
  waivers.

#### NC-502 — Build Blueprint editing UI

- **Priority:** P0-D
- **Dependencies:** NC-501, NC-105
- **Status:** Independently verified.
- Add course default editing and per-subtopic exceptions.
- Make asset cells interactive.
- Confirm anchor waivers explicitly.

#### NC-503 — Add Blueprint reconciliation preview

- **Priority:** P0-D
- **Dependencies:** NC-502
- **Status:** Independently verified.
- Show added/removed assets and which existing content will become stale.

#### NC-504 — Add scoped live Blueprint revision

- **Priority:** P0-L
- **Dependencies:** NC-107, NC-905
- **Status:** Independently verified behind NC-905.
- Request structured selected-asset/depth changes.
- Validate through the deterministic reducer.

### Deterministic package exit gate

- The operator can control exact assets/depth per subtopic.
- Generated content selection remains exact.

The live proposal/revision requirement closes with NC-504 during NC-90 and cannot bypass
anchor or source rules.

## 11. Work package NC-60 — Lesson Plan decisions

**Implementation status (2026-07-20):** NC-601 through NC-603 passed independent
review with deterministic browser Scenario A12 evidence. The reviewed contract covers
typed constraints and session operations, ordered Course Model-authoritative coverage,
monotonic session IDs, intent-aware checksum-conflict rebasing, bounded preservation,
and exact affected-session reporting. NC-604 is independently verified behind NC-908.

### Tasks

#### NC-601 — Define Lesson Plan decision reducer

- **Priority:** P0-D
- **Dependencies:** NC-107
- Support constraints, mode changes, moves, and ordering.
- Preserve exact Course Model coverage.

#### NC-602 — Build Lesson Plan controls

- **Priority:** P0-D
- **Dependencies:** NC-601, NC-105
- Edit max session length, default mode, delivery details, and segment placement.
- Show affected sessions.

#### NC-603 — Implement affected-session regeneration

- **Priority:** P0-D
- **Dependencies:** NC-601
- Preserve unaffected session bodies where the operation is bounded.

#### NC-604 — Add scoped live Lesson Plan revision

- **Priority:** P0-L
- **Dependencies:** NC-601, NC-908
- **Status:** Independently verified behind NC-908.
- Request structured constraint/operation proposals.
- Validate exact coverage deterministically.

### Deterministic package exit gate

- The director can adjust delivery without generic feedback.
- Coverage and constraints remain valid.
- Bounded changes preserve unaffected sessions.

The live proposal/revision requirement closes with NC-604 during NC-90 and must use the
same Lesson Plan reducer.

## 12. Work package NC-70 — Research quality and source repair

**Implementation status (2026-07-20):** NC-701 through NC-709 passed independent
checkpoint review. Deterministic browser evidence covers Scenario A10's source-decision
and route phase: reviewable source quality, known-source proposal, bounded evidence
research, human approval, exact atomic routing, and preservation of unrelated state.
At the NC-70 boundary Content remained unchanged at `awaiting_content_repair`; NC-80
now supplies the targeted regeneration and reverification that closes that boundary.

### Tasks

#### NC-701 — Add source candidate scoring

- **Priority:** P0-D
- **Dependencies:** NC-106
- **Status:** Independently verified.
- Score authority, fit, specificity, freshness, fetch status, and content availability.
- Keep scoring transparent and advisory.

#### NC-702 — Capture relevant source sections

- **Priority:** P0-D
- **Dependencies:** NC-701
- **Status:** Independently verified.
- Extract bounded sections relevant to candidate topics/evidence gaps.
- Preserve existing excerpt-size guardrails.

#### NC-703 — Project bounded source previews and coverage

- **Priority:** P0-D
- **Dependencies:** NC-702
- **Status:** Independently verified.
- Return safe preview, trust/relevance notes, and topic/gap coverage.

#### NC-704 — Add known-source command and UI

- **Priority:** P0-D
- **Dependencies:** NC-106
- **Status:** Independently verified.
- Create proposed candidates from user-provided URLs.
- Require normal source approval.

#### NC-705 — Add source_repair artifact contract

- **Priority:** P0-D
- **Dependencies:** NC-102
- **Status:** Independently verified.
- Add schema/validation/repository support for the repair ledger.
- Synchronize entry state under course mutation locks.

#### NC-706 — Implement bounded evidence research job

- **Priority:** P0-D
- **Dependencies:** NC-705
- **Status:** Independently verified.
- Consume subtopic/asset/claim/finding scope.
- Produce proposed candidates without changing the approved registry.
- Use an injected research provider so deterministic repair works before live parity.

#### NC-707 — Build repair candidate review UI

- **Priority:** P0-P
- **Dependencies:** NC-703, NC-706
- **Status:** Independently verified.
- Show the originating finding, candidate previews, coverage, and approval decision.

#### NC-708 — Implement source approval and route transaction

- **Priority:** P0-D
- **Dependencies:** NC-403, NC-501, NC-705
- **Status:** Independently verified.
- Atomically update source store, dossier, registry, named Course Model source mappings,
  Blueprint routes, and repair ledger.
- Stop and require normal reopen when scope/structure/asset selection would change.

#### NC-709 — Add source-repair impact and preservation tests

- **Priority:** P0-D
- **Dependencies:** NC-708
- **Status:** Independently verified.
- Assert unrelated Course Model/Blueprint records and content assets remain unchanged.

### Package exit gate

- Source quality is reviewable before approval.
- A known source can be added after creation.
- One evidence gap can produce and approve a bounded candidate.
- Source routing updates only the confirmed scope.
- Deterministic browser evidence proves the source-decision and route portion of A10;
  NC-80 proves the dependent targeted regeneration, reverification, and review closure.

## 13. Work package NC-80 — Content repair and review closure

**Implementation status (2026-07-20):** NC-801 through NC-808 passed independent
checkpoint review. Deterministic browser Scenarios A8 through A11 prove truthful
source-less and unattributed blocker gating, both repair strategies, exact target-only
regeneration and reverification, unchanged-asset preservation, Source Repair lifecycle
closure, fingerprint-synchronized review reset/preservation, visible nonblocking
partial findings, and Content approval releasing Lesson Plan only after review closure.
Negative and recovery coverage proves pre-job validation, atomic scope rejection,
secret-safe typed failure/retry, and process-restart recovery.

### Tasks

#### NC-801 — Define typed ContentRepairCommand

- **Priority:** P0-D
- **Dependencies:** NC-107
- **Status:** Independently verified.
- Require asset IDs and optional finding/claim IDs.
- Distinguish existing-evidence and better-evidence strategies.

#### NC-802 — Classify verifier findings for repair

- **Priority:** P0-D
- **Dependencies:** NC-801
- **Status:** Independently verified.
- Classify likely content error, missing attribution, insufficient evidence, or human
  review case.
- Keep classification advisory.

#### NC-803 — Repair using existing approved evidence

- **Priority:** P0-D
- **Dependencies:** NC-801
- **Status:** Independently verified.
- Regenerate and reverify named assets only.
- Preserve unaffected assets byte-for-byte.

#### NC-804 — Connect better-evidence repair

- **Priority:** P0-D
- **Dependencies:** NC-708, NC-801
- **Status:** Independently verified.
- Create/advance Source Repair entries and start targeted content regeneration after the
  approved route transaction.

#### NC-805 — Correct content-review synchronization

- **Priority:** P0-D
- **Dependencies:** NC-803
- **Status:** Independently verified.
- Reset decisions only for changed asset fingerprints.
- Preserve unchanged approvals.

#### NC-806 — Recalculate attention and release state after repair

- **Priority:** P0-D
- **Dependencies:** NC-803, NC-804, NC-805
- **Status:** Independently verified.
- Derive current blockers from claim-level results.
- Keep partial findings visible but nonblocking.

#### NC-807 — Build repair queue and progress UI

- **Priority:** P0-P
- **Dependencies:** NC-802, NC-804
- **Status:** Independently verified.
- Group findings by likely cause.
- Show repair state from request to re-review.

#### NC-808 — Add deterministic blocker-repair acceptance

- **Priority:** P0-D
- **Dependencies:** NC-806, NC-807
- **Status:** Independently verified.
- Inject one unsupported/unattributed/evidence-gap path.
- Clear it through the real browser workflow.

### Package exit gate

- Both repair strategies work.
- Unaffected assets are preserved.
- Reviews and blocker totals are truthful.
- Package readiness updates only after repair and review complete.

## 14. Work package NC-90 — Live-agent parity

**Implementation status (2026-07-20):** NC-901 through NC-912 and the dependency-gated
scoped live revisions NC-303, NC-406, NC-504, and NC-604 passed independent checkpoint
review. Evidence uses injected structured providers on indoor
herb gardening and bicycle maintenance; it is not a credentialed Anthropic end-to-end
run, which remains NC-1104.

### Goal

Replace deterministic proposals behind stable contracts, one stage at a time.

### Tasks

#### NC-901 — Add provider-neutral implementation registry

- **Status:** Independently verified.
- **Priority:** P0-L
- **Dependencies:** NC-10 package exit
- Resolve deterministic/live callables for each stage through pipeline factories.
- Keep Step contracts and CLI behavior stable.

#### NC-902 — Live Outcomes implementation

- **Status:** Independently verified.
- **Priority:** P0-L
- **Dependencies:** NC-301, NC-901
- Add structured output, validation, cache/cost logs, and eval fixtures.

#### NC-903 — Live Research implementation hardening

- **Status:** Independently verified.
- **Priority:** P0-L
- **Dependencies:** NC-901
- Add bounded search planning/tool use, ranking inputs, retries, and safe failures.

#### NC-904 — Live Course Model implementation

- **Status:** Independently verified.
- **Priority:** P0-L
- **Dependencies:** NC-403, NC-901
- Generate validated structure or operations from approved inputs only.

#### NC-905 — Live Blueprint implementation

- **Status:** Independently verified.
- **Priority:** P0-L
- **Dependencies:** NC-501, NC-901
- Generate selected assets/depth proposals through the deterministic reducer.

#### NC-906 — Live Student Content regression hardening

- **Status:** Independently verified.
- **Priority:** P0-L
- **Dependencies:** NC-901
- Preserve current context slicing, source bounds, cache, verification, and targeted
  revision behavior under the shared registry.

#### NC-907 — Live Verification regression hardening

- **Status:** Independently verified.
- **Priority:** P0-L
- **Dependencies:** NC-906
- Verify separation from generation, result parsing, attribution, and repair categories.

#### NC-908 — Live Lesson Plan implementation

- **Status:** Independently verified.
- **Priority:** P0-L
- **Dependencies:** NC-601, NC-901
- Generate validated sessions/operations under deterministic coverage constraints.

#### NC-909 — Live Brief clarification/synthesis

- **Status:** Independently verified.
- **Priority:** P0-L
- **Dependencies:** NC-206, NC-901
- Propose bounded validated questions and optional structured Brief revisions.

#### NC-912 — Live bounded evidence-repair provider

- **Status:** Independently verified.
- **Priority:** P0-L
- **Dependencies:** NC-706, NC-903
- Connect the Source Repair job to live bounded search/extraction.
- Preserve the same proposed-candidate and human-decision contracts used by the
  deterministic repair provider.

#### NC-910 — Stage-level live eval suite

- **Status:** Independently verified.
- **Priority:** P0-L
- **Dependencies:** NC-902 through NC-909 and NC-912 as applicable
- Cover schema validity, instruction adherence, domain neutrality, grounding, coverage,
  stable references, revision scope, and failure behavior.

#### NC-911 — Prevent silent live fallback

- **Status:** Independently verified.
- **Priority:** P0-L
- **Dependencies:** NC-901
- Make provider failure explicit.
- Require an operator decision to change mode.

### Package exit gate

- Every judgment-heavy stage has a live implementation or an explicitly documented
  deterministic responsibility.
- Live artifacts match deterministic contract shapes.
- No live failure silently becomes deterministic output.
- Stage evals pass on at least two unrelated topics.

## 15. Work package NC-100 — Progress, diagnostics, and Package completion

**Implementation status (2026-07-20): independently checkpointed.** NC-1001 through
NC-1007 passed fresh read-only review. Evidence covers timely generation and repair
unit progress, persisted secret-safe activity, stage diagnostics with provider, model,
calls, tokens, cost, cache, real retry attempts, and safe errors, provider readiness on
every live start path, bounded canonical Markdown fetch and raw-HTML-disabled rendering,
backend-owned release-check navigation to exact stages/assets, and keyboard, focus,
status, and contrast coverage. The corrected Chromium suite passes all 9 scenarios.

### Tasks

#### NC-1001 — Connect live unit progress callback

- **Status:** Independently verified.
- **Priority:** P0-P
- **Dependencies:** NC-901
- Pass an event adapter through pipeline factories.
- Emit unit events during generation.

#### NC-1002 — Project real activity history

- **Status:** Independently verified.
- **Priority:** P0-P
- **Dependencies:** NC-1001
- Read persisted jobs/events and safe call summaries.
- Remove hardcoded activity claims.

#### NC-1003 — Add safe call/cost diagnostics

- **Status:** Independently verified.
- **Priority:** P0-P
- **Dependencies:** NC-901
- Show provider, model, calls, tokens, estimated cost, cache hits, retries, and safe errors
  by stage.

#### NC-1004 — Add provider-readiness UI

- **Status:** Independently verified.
- **Priority:** P0-L
- **Dependencies:** NC-901
- Block live start when required provider credentials are unavailable.
- Explain the problem without exposing credentials.

#### NC-1005 — Fetch and render selected Markdown

- **Status:** Independently verified.
- **Priority:** P0-D
- **Dependencies:** NC-104
- Add safe text response/fetch handling.
- Render the actual selected file with raw HTML disabled.

#### NC-1006 — Add Package blocker navigation

- **Status:** Independently verified.
- **Priority:** P0-P
- **Dependencies:** NC-806, NC-1005
- Link each failed release check to the responsible stage/asset.

#### NC-1007 — Add accessibility coverage

- **Status:** Independently verified.
- **Priority:** P0-P
- **Dependencies:** Major UI tasks complete
- Cover keyboard flow, focus, labels, dialogs, status announcements, and contrast issues
  on the acceptance path.

### Package exit gate

- Progress is real and timely.
- Activity and diagnostics are populated and safe.
- Live readiness is clear.
- Package displays actual content and actionable blockers.

## 16. Work package NC-110 — Automated release validation

### Tasks

#### NC-1101 — Full deterministic browser acceptance

- **Priority:** P0-D
- **Dependencies:** NC-20 through NC-80 deterministic exits, NC-1005
- Automate the complete scenario in the acceptance plan.

#### NC-1102 — Lifecycle/recovery browser scenarios

- **Priority:** P0-P
- **Dependencies:** NC-108, NC-1002
- Cover refresh during run, API restart, retry, stale conflict, reopen, and navigation.

#### NC-1103 — Negative source and approval scenarios

- **Priority:** P0-P
- **Dependencies:** NC-104, NC-708
- Attempt rejected source leakage, blocker approval, read-only mutation, path traversal, and
  concurrent mutation.

#### NC-1104 — Bounded live end-to-end acceptance

- **Priority:** P0-L
- **Dependencies:** NC-90 and NC-100 exits
- Run the selected live subject through Package.
- Record calls, tokens, cost, cache, retries, verifier results, and repairs.

#### NC-1105 — Domain-neutral second-topic regression

- **Priority:** P0-L
- **Dependencies:** NC-1104
- Confirm no subject-specific prompt or code assumption was introduced.

### Package exit gate

- Deterministic, negative, recovery, and live scenarios pass.
- The live run has no hard verifier blockers after repair/review.
- Integrity and source enforcement pass.

## 17. Work package NC-120 — Internal pilot and release decision

### Tasks

#### NC-1201 — Prepare operator-only start instructions

- **Priority:** P0-P
- **Dependencies:** NC-110 exits
- Provide normal local startup and provider-readiness guidance.
- Do not include JSON editing or artifact repair instructions.

#### NC-1202 — Run internal course-director pilot

- **Priority:** P0-P
- **Dependencies:** NC-1201
- Observe without directing unless safety/data integrity requires intervention.
- Use the acceptance-plan scorecard.

#### NC-1203 — Triage pilot findings

- **Priority:** P0-P
- **Dependencies:** NC-1202
- Classify release blockers, workflow defects, quality defects, and preferences.
- Add accepted blockers to this backlog with dependencies and tests.

#### NC-1204 — Rerun pilot blocker path

- **Priority:** P0-P
- **Dependencies:** NC-1203 blocker fixes
- Have the director repeat affected tasks without coaching.

#### NC-1205 — Close cycle and update context

- **Priority:** P0-P
- **Dependencies:** NC-1204
- Record validation evidence, remaining limitations, cost, and recommended next package.
- Update Master Context and implementation handoff.

### Package exit gate

- The director completes without terminal, raw JSON, or engineering intervention.
- No false-ready state or ignored action occurs.
- Remaining feedback is prioritized follow-on work rather than a core workflow blocker.

## 18. Recommended ownership split

This plan retains the existing two-person “bones versus intelligence” split.

### Platform/API owner

- lifecycle and invalidation;
- capability/impact projection;
- typed reducers and command endpoints;
- source repair transaction;
- job/progress/activity services;
- server-side approval gates;
- backend contract and security tests.

### Frontend/product owner

- question rounds;
- typed stage editors;
- impact/reopen interaction;
- repair queue;
- activity/diagnostics/Package views;
- accessibility and browser acceptance.

### Pair closely

- command/view contracts before implementation;
- Course Model operations;
- source repair;
- deterministic acceptance fixture;
- live-stage evals;
- internal pilot triage.

## 19. Initial ready queue

The first development work should be pulled in this order:

1. NC-001 planning approval;
2. NC-002 deterministic fixture definition;
3. NC-004 capability regression;
4. NC-005 browser harness;
5. NC-101 state vocabulary;
6. NC-102 invalidation service;
7. NC-103 impact preview;
8. NC-104 approval guards;
9. NC-106 capability registry;
10. NC-105 reopen UI;
11. NC-107 scoped revision command;
12. NC-109 placeholder-control cleanup.

Do not begin broad live-agent replacement before the NC-10 lifecycle exit gate. Do not
begin the final pilot before both deterministic and bounded live browser acceptance pass.

## 20. Deferred backlog boundary

Do not add tasks for authentication, multi-user collaboration, hosting, distributed
queues, DOCX/PPTX, SCORM, RAG, generic chat, mobile authoring, or broad parallelization
to this active backlog unless the user explicitly reopens cycle scope.
