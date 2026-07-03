# Course Builder — Phase 1 Completion & Phase 2 Handoff

> **Status:** ✅ COMPLETE
> **Final human acceptance:** 2026-07-01
> **Scope:** Phase 1 Student Content benchmark for `m1_s1` “Nature of Financial Risk”
> **Next phase:** Phase 2 — intent, research, source approval, and compact Course Model

## Outcome

Phase 1 retired the project’s largest product risk: the generic Student Content path can produce a complete nine-asset package using scoped approved sources, claim-level attribution, separate adversarial verification, dynamic coverage/depth controls, and targeted revision. The final outputs were fully reviewed and accepted by the project owner on 2026-07-01.

The FRM material is benchmark data only. Reusable prompts and contracts receive subject-specific facts through approved artifacts and deterministic context slices; they do not encode FRM logic.

## Delivered

- A compact Course Model and Blueprint contract with per-subtopic scope, depth, coverage, source assignments, and asset selection.
- Nine generated Student Content asset types, anchored on Course Content and emitted as a schema-valid Content Package v0.2.
- Claim-level source attribution with `sources[]` derived from claims.
- A separate verifier that records supported, partial, unsupported, ungrounded, and unattributed findings.
- Coverage/depth checks and bounded targeted regeneration that preserve unaffected content.
- A rubric, provisional scorecard, blind-review packet, and human acceptance gate.
- Domain-agnostic contract checks, including a non-FRM context-slicing fixture.

## Acceptance evidence

- Final generated package: `courses/frm-demo/content_package.json`
- Final provisional scorecard: `evals/run_2026-06-30_generic_final.provisional.json`
- Blind review packet and committed mapping: `evals/phase1_final_blind_review.json` and `evals/phase1_final_blind_review.mapping.json`
- Gold comparison package: `benchmark/m1_s1.gold.content_package.json`
- Evaluation contract: `evals/rubric.md`
- Automated regression check at close: **54 tests passed** on 2026-07-01.
- Final authority: the project owner completed the review, confirmed the outputs looked good, and authorized Phase 1 closure on 2026-07-01.

The scorecard filename retains `provisional` because its structured human-score fields were not backfilled with invented values. The explicit owner acceptance above is the authoritative completion record.

## Durable lessons

1. **Trust is a pipeline property.** Scoped evidence, writer attribution, independent verification, and a visible human checkpoint work together; no single prompt supplies trust by itself.
2. **Claim-level attribution is the useful granularity.** Asset-level source lists are too coarse. Keeping citations parallel to clean learner-facing prose makes support inspectable without polluting the content.
3. **Context slicing beats context dumping.** Selecting only the current subtopic, depth/coverage requirements, and assigned source excerpts keeps the path understandable and gives Phase 2 a clear source-routing contract.
4. **Depth must come from approved intent.** Blueprint budgets and named coverage gaps create useful expansion; universal word-count pressure creates padding.
5. **The orchestrator can stay opaque.** Artifact bodies and intelligence evolved without putting course-domain rules into orchestration.
6. **FRM proves quality, not generality.** Phase 2 must prove the upstream path on a non-FRM subject before the system can claim end-to-end domain independence.

## Phase 2 entry contract

Phase 2 should preserve the approved downstream interfaces and replace only the fixture-backed upstream intelligence:

1. Conversationally turn a sparse subject request into an approved Course Brief.
2. Produce and approve measurable course-level outcomes.
3. Research competitors and candidate sources, keeping evidence and full source content outside the Course Model.
4. Require an explicit human source-approval decision.
5. Build one compact Course Model containing the approved hierarchy, scope, concepts, dependencies, coverage requirements, and source IDs.
6. Hand that Course Model to the existing Blueprint and Student Content contracts without FRM-specific adaptation.

## Immediate next steps

1. Execute P2.1 in `Course_Builder_Phase2_Plan.md`: add the missing Course Brief v0.2 contract and sparse subject-request boundary.
2. Confirm the non-FRM acceptance course and sparse starting prompt; “coffee making” remains the default example from the Master Context.
3. Add the mocked non-FRM contract fixture, then implement in approval-gate order: intake → outcomes → research/source approval → Course Model.
4. Run the non-FRM path into the existing Blueprint/Student Content boundary and verify that no domain-specific prompt changes are needed.

Phase 1 is closed. Any later tuning of its benchmark is regression work, not a reopening of the phase.
