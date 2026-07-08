# Course Builder - Four-Week Prototype Completion Handoff

> **Status:** Prototype complete, validated locally and with one full live run
> **Updated:** 2026-07-06
> **Branch state at validation:** `main` after live-flow efficiency and verifier attention-gate fixes
> **Purpose:** Record what the prototype now does, what was verified, what does not work well enough yet, and what should be improved next.

## 1. Executive Summary

The four-week Course Builder prototype is complete as a working vertical path.

The system can take a sparse subject request through:

`subject_request -> Course Brief -> Course Outcomes -> Research Dossier -> source approval -> Course Model -> Blueprint -> selected Student Content -> verification -> Lesson Plan -> rendered Markdown course folder -> run summary`

The core product contracts work:

- artifacts are persisted as JSON in a course folder;
- stage approvals and resume behavior work;
- source decisions are deterministic;
- rejected/proposed sources are blocked from downstream use;
- Blueprint asset selections control what is generated;
- generated factual claims are attributed and independently verified;
- selected assets are rendered into an organized Markdown folder;
- run summaries now surface verifier blockers instead of silently marking flagged live output complete.

The prototype should be treated as a successful engineering prototype, not as production-ready courseware automation. A live run proved that the full path executes, but also proved that the first live output may need source repair and targeted revision before it is learner-ready.

## 2. What Was Built

### Interaction and approval foundation

- Sparse `subject_request` boundary.
- Deterministic Course Brief questionnaire and typed question model.
- Structured choice model for source decisions and asset decisions.
- Terminal checkpoint loop with `approve`, `changes`, and `quit`.
- Resume behavior that skips approved, current artifacts and reruns missing, draft, stale, rejected, or revised steps.

### Upstream design path

- Course Brief v0.2 output.
- Course Outcomes v0.2 output.
- Bounded research adapter with mock and live provider implementations.
- Competitor outline extraction and normalized coverage matrix.
- Candidate factual-source proposals with locators, trust notes, relevance notes, and failure records.
- Source capture into a source store under stable course/source IDs.
- Deterministic source approval/rejection reducer.
- Compact Course Model v0.2 with modules, subtopics, coverage requirements, structural rationale, and approved source mappings.
- Course Model integrity checks for IDs, dependencies, outcomes, and approved-source routing.

### Blueprint and content production

- Blueprint v0.2 with course defaults and per-subtopic asset plans.
- Explicit selected/rejected asset status.
- Per-asset source routing.
- Whole-course Student Content generation across arbitrary subtopics.
- Deterministic context slicing by subtopic, asset, Blueprint plan, and assigned approved sources.
- Evidence-gap behavior when selected assets have no routed approved evidence.
- Per-asset generation, depth guardrails, claim attribution, and independent verification.
- Targeted revision for a specific asset without regenerating unaffected assets.

### Lesson plan and output folder

- Domain-neutral Lesson Plan generation.
- Markdown renderer for course overview, source index, lesson plan, and selected assets.
- Renderer cleanup to avoid stale files on rerun.
- Run summary with stage totals, unit totals, output paths, resume guidance, and verifier totals.

## 3. Validation Evidence

### Automated regression

Final validation on `main` after all prototype fixes:

```bash
ruff check .
python3 -m pytest -q
```

Result:

- lint passed;
- full test suite passed: `92 passed`.

### Local deterministic acceptance

The local acceptance path runs without external network/API dependencies:

```bash
python3 run.py --acceptance-demo --course-id coffee-acceptance --auto-approve
python3 integrity.py coffee-acceptance
```

Evidence:

- deterministic `coffee-acceptance` artifacts were generated under `courses/coffee-acceptance/`;
- rendered Markdown was generated under `rendered_courses/coffee-acceptance/`;
- the committed snapshot now lives under `examples/acceptance/coffee-acceptance/`;
- integrity passes;
- resume rerun skips approved current stages;
- local acceptance proves orchestration, source routing, rendering, run summary, resume, targeted revision, and negative gates.

### Domain-neutral smoke

The acceptance test suite includes a second unrelated topic, indoor herb gardening. It runs through the same Brief, Outcomes, Research Dossier, source approval, Course Model, Blueprint, selected content slice, and Lesson Plan contracts without subject-specific code or prompt edits.

### Live end-to-end run

A full live run was executed on 2026-07-06 using live bounded research, live LLM-backed Student Content generation, live verification, Lesson Plan, Markdown rendering, and integrity checks.

Observed live-run result:

- live research passed;
- source selection passed;
- Course Model passed;
- Blueprint passed;
- live generation passed;
- live verification ran;
- Lesson Plan generated;
- Markdown folder rendered;
- run summary written;
- integrity passed.

Observed live-run metrics:

- 37 Claude calls;
- estimated logged cost: about `$2.50`;
- max input tokens per call after source-context fix: `8,990`;
- average input tokens: about `6,835`;
- 8 competitor findings;
- 8 source candidates;
- 2 approved sources;
- 18 selected assets;
- 18 generated assets;
- 18 rendered Markdown files;
- rejected source leakage: none.

The live output was created in a temporary artifact root and intentionally not committed as durable course content.

## 4. What Works

The following capabilities are working well enough for the prototype gate:

1. **End-to-end orchestration.** The full stage sequence can run from sparse request to rendered folder.
2. **Plain-file state.** Course artifacts are persisted in predictable JSON files with stable lifecycle metadata.
3. **Resume.** Approved current stages are skipped on rerun; draft/stale/downstream artifacts rerun.
4. **Explicit source decisions.** Source approval/rejection is deterministic and not reinterpreted by the model.
5. **Rejected-source enforcement.** Rejected/proposed/competitor-only sources are excluded from Course Model and generation context.
6. **Course Model compactness.** Competitor evidence and source text remain outside the Course Model.
7. **Blueprint asset control.** The content path generates exactly selected assets and blocks unselected direct generation.
8. **Context slicing.** Generation receives the current subtopic/asset context and only assigned approved source excerpts.
9. **Whole-course generation.** The content path works across multiple subtopics and asset types.
10. **Verification.** Independent verification surfaces supported, partial, unsupported, ungrounded, and unattributed findings.
11. **Targeted revision.** A single asset can be revised without regenerating unaffected assets.
12. **Markdown rendering.** Generated material is rendered into an organized inspectable folder.
13. **Cost control improvement.** Live source excerpts are now bounded, avoiding the earlier 60k+ input-token calls.
14. **Run-summary attention gate.** Unsupported, ungrounded, or unattributed verifier findings now mark the run as `requires_attention`.

## 5. What Does Not Work Well Enough Yet

These are not prototype blockers, but they are real product gaps.

### 5.1 First live output is not guaranteed learner-ready

The full live run completed, but verifier output found:

- `partial`: 14;
- `unsupported`: 5;
- `ungrounded`: 1;
- `unattributed`: 3.

The issues were concentrated in troubleshooting assessment and activity assets. The generated advice was plausible, but not fully supported by the approved source excerpts.

### 5.2 Source quality is the biggest live weakness

The live auto-approved sources were broad index/overview pages:

- an NCA page pointing to AboutCoffee.org;
- CoffeeResearch.org homepage/index content.

Those sources supported high-level coffee concepts, but they did not support detailed troubleshooting claims such as grind-size extraction effects, French press over-extraction, stale coffee-oil residue, or changing one variable at a time.

The system behaved correctly by surfacing the unsupported claims, but the source-selection path needs better source quality before live output can be trusted quickly.

### 5.3 Auto-approve is not a quality workflow

`--auto-approve` is useful for deterministic tests and unattended live validation, but it is not equivalent to a real operator choosing good sources and reviewing artifacts. In live use, the human should inspect source candidates before approving them.

### 5.4 Live research provider is basic

The current live provider is intentionally simple. It can find and fetch pages, but it does not yet rank source authority or topical fit strongly enough. It may propose broad pages where specific authoritative sources are needed.

### 5.5 Verification is surfaced, not automatically repaired

The system records verifier findings and now marks run summary status correctly, but it does not yet automatically:

- route unsupported findings into a targeted revision;
- reopen research/source approval when the issue is insufficient evidence;
- block rendering of flagged learner assets;
- require operator approval after verifier blockers.

### 5.6 Sequential generation is slow

The live run generated 18 assets sequentially. This is acceptable for the prototype, but larger courses will need tighter asset defaults, better batching, or parallelization.

### 5.7 Terminal UX is still rough

The terminal checkpoint loop works, but the product needs better review ergonomics:

- source preview before approval;
- compact diff/revision display;
- clearer verifier issue summaries by severity;
- easier targeted revision commands;
- eventually a browser UI over the same contracts.

### 5.8 Output format is prototype Markdown

Markdown output is deterministic and inspectable, which is correct for the prototype gate. Native DOCX/PPTX styling and SCORM wiring remain later work.

## 6. Improvements Needed Next

### Priority 1 - Source repair and evidence-gated content

1. Add a source repair loop when verifier blockers are caused by insufficient evidence.
2. Let the operator approve additional sources after a downstream evidence gap.
3. Improve source candidate ranking so broad overview/index pages are not auto-preferred over specific instructional or authoritative references.
4. Add source-preview summaries before approval, including estimated coverage by subtopic.
5. Store excerpts by relevant page sections rather than only taking the first bounded text slice.

### Priority 2 - Targeted verifier-driven revision

1. Convert unsupported/ungrounded/unattributed findings into structured revision feedback.
2. Regenerate only flagged assets.
3. Reverify regenerated assets.
4. Preserve approved unaffected assets.
5. Keep `operator_status: requires_attention` until blockers are resolved.

### Priority 3 - Operator review workflow

1. Present source candidates with title, publisher, locator, trust note, relevance note, and content preview.
2. Present verifier blockers as a short asset-by-asset review queue.
3. Add a clear command for "research more for this subtopic" versus "revise using existing sources".
4. Add a final acceptance checklist before considering a live course complete.

### Priority 4 - Cost and speed controls

1. Keep bounded source excerpts.
2. Add an operator-configurable acceptance asset set for live tests.
3. Reduce rich optional assets during live smoke runs unless explicitly selected.
4. Consider parallel generation only after source repair and verification workflow stabilize.
5. Track live-call cost per stage in the run summary.

### Priority 5 - Delivery polish

1. Improve Markdown folder naming and indexes for easier human review.
2. Add native document rendering only after content quality gates are reliable.
3. Wire approved rendered output into the existing SCORM converter as a later packaging step.

## 7. Current Acceptance Boundary

The prototype may honestly claim:

- the full course-builder workflow is implemented end to end;
- local deterministic acceptance is stable;
- a live end-to-end run completed;
- source enforcement and selected-asset enforcement work;
- verifier findings are visible and now affect final run status;
- the output folder is produced and inspectable.

The prototype should not claim:

- generated live content is automatically learner-ready after one pass;
- live source selection is robust enough without human review;
- unsupported claims are automatically repaired;
- production-scale research, packaging, or deployment is complete;
- high-stakes domains can be used without expert review.

## 8. Recommended Next Work Package

The next engineering package should be:

`source repair + verifier-driven targeted revision`

Definition of done for that package:

1. A live run with verifier blockers produces `requires_attention`.
2. The operator can choose to add better evidence or request targeted revision.
3. Only affected assets regenerate.
4. Reverification clears or preserves the remaining blocker list.
5. Run summary changes to `complete` only when no unsupported, ungrounded, or unattributed findings remain.

This is the highest-leverage next step because the live prototype already runs; the main remaining risk is output trust and review speed.
