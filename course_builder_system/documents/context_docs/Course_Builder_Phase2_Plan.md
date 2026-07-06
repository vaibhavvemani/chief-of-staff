# Course Builder — Phase 2 Implementation Plan

> **Status:** COMPLETE WITHIN THE FOUR-WEEK PROTOTYPE — retained as detailed upstream design context
> **Goal:** Replace the fixture-backed upstream path with real, domain-agnostic intent, outcomes, research/source-approval, and Course Model agents.
> **Acceptance course:** A non-FRM course beginning from a sparse request; “coffee making” is the default unless the project owner selects another subject before the live run.
> **Downstream boundary:** Produce an approved Course Model that the existing Blueprint and Student Content contracts can consume without domain-specific changes.

> **Completion note:** The upstream path is now implemented in the prototype and has been exercised in deterministic and live runs. Remaining work is not "Phase 2 completion"; it is source-quality hardening, verifier-driven repair, operator UX, and productionization. See `Course_Builder_Four_Week_Prototype_Completion_Handoff.md`.

## Definition of Done

Phase 2 is complete when one sparse non-FRM request can travel through:

`subject request → clarified and approved Course Brief → approved course outcomes → Research Dossier + explicit source decisions → approved compact Course Model`

The gate requires:

- The intake dialogue asks only unresolved, high-impact questions and preserves explicit inclusions, exclusions, and constraints.
- Course outcomes are measurable, traceable to the approved brief, and approved before research begins.
- Competitor findings and candidate sources are gathered with locators, trust notes, relevance, and topic assignments.
- The human explicitly approves or rejects candidate sources; only approved sources enter the Course Model registry.
- Full source content and research evidence remain outside the compact Course Model.
- The Course Model contains stable IDs, hierarchy, scope, concepts, dependencies, coverage requirements, and source assignments.
- Schema, referential-integrity, resume/revision, and domain-leakage tests pass.
- The approved non-FRM Course Model reaches the existing Blueprint boundary without changing generic downstream prompts for that subject.

## Locked boundaries

1. **Preserve the orchestrator contract.** Lifecycle fields and checkpoint behavior remain orchestrator-owned. Agent steps return artifact bodies and declared inputs.
2. **Keep conversation at the intake boundary.** The clarifier may conduct several short turns, but it emits one Course Brief into the normal approval checkpoint once the required intent is sufficiently resolved.
3. **Approve intent before spending on research.** Research cannot start from an unapproved brief or outcomes artifact.
4. **Research evidence is not Course Model content.** The Research Dossier holds findings and source decisions; full approved content lives in the external source store referenced by `content_ref`.
5. **No hidden source approval.** The model may recommend a status, but a human decision determines which candidates are approved.
6. **No FRM assumptions.** FRM fixtures remain regression inputs only. The acceptance path is non-FRM.
7. **No RAG yet.** Use deterministic source capture and node assignment until measured scale demonstrates a retrieval need.

## Work sequence

### P2.1 — Lock contracts and acceptance fixtures

- Add a formal Course Brief v0.2 schema; the repository currently has v0.2 schemas for outcomes, Research Dossier, Course Model, Blueprint, and Content Package but not the brief.
- Decide the minimal subject-request input shape and retain the existing artifact envelope.
- Confirm the existing v0.2 upstream schemas express the live-agent needs; make only evidence-backed contract amendments.
- Add a sparse non-FRM acceptance request and mocked expected-shape fixtures.
- Extend schema and integrity tests before replacing any fixture step.

**Gate:** all upstream contracts validate independently and their references form one coherent chain.

### P2.2 — Conversational intake

- Implement the clarifier and a versioned prompt.
- Detect missing high-impact fields: audience, prior knowledge, level/depth, goals, scope, duration, modality, language, jurisdiction, constraints, must-haves, and exclusions.
- Avoid re-asking resolved fields; summarize assumptions separately from user-stated facts.
- Emit a draft Course Brief for the existing approve/reject/revise checkpoint.

**Gate:** a sparse subject becomes an approved, schema-valid brief in a short dialogue; rejection revises only the brief.

### P2.3 — Course outcomes

- Replace `course_outcomes_step` fixture loading with a real agent.
- Generate measurable whole-course outcomes with cognitive level, observable evidence, and priority.
- Add brief-alignment checks and feedback-driven revision.

**Gate:** approved outcomes are traceable to the brief and contain no subtopic-delivery artifacts.

### P2.4 — Research and source approval

- Replace `research_step` fixture loading with a bounded research workflow.
- Capture competitor offerings, audience/structure/topic findings, differentiation opportunities, and candidate authoritative sources.
- Store source content outside artifacts and retain locators plus `content_ref` paths.
- Present proposed source decisions for explicit human approval/rejection and preserve all decisions in the dossier.
- Add provenance, failed-fetch, duplicate-source, and stale/insufficient-evidence handling.

**Gate:** the approved Research Dossier is reproducible enough to audit and every approved source resolves to stored content.

### P2.5 — Compact Course Model

- Replace `structure_step` fixture loading with a real structure agent.
- Build ordered modules/subtopics, purpose and scope, prerequisites, concepts, coverage requirements, and approved source assignments.
- Enforce stable IDs and validate every outcome, dependency, concept, node, and source reference.
- Support targeted human revision without rebuilding approved research.

**Gate:** one approved Course Model passes schema/integrity checks and preserves both TOC and domain-model use cases without embedding source text.

### P2.6 — Non-FRM end-to-end gate and handoff

- Run the sparse acceptance request through all four real upstream capabilities.
- Exercise rejection/resume at least once to prove checkpoint behavior.
- Hand the resulting Course Model to the existing Blueprint boundary.
- Run the full regression suite, inspect domain-leakage checks, record model/token/cost data, and write the Phase 2 handoff.

**Gate:** the non-FRM path meets the Definition of Done with no subject-specific edits to reusable downstream prompts.

## Test strategy

- Mock model and research calls for deterministic contract, revision, and failure-path tests.
- Keep one live non-FRM acceptance run as product evidence, not as a unit-test dependency.
- Test that rejected sources cannot enter `source_registry`, concepts, coverage requirements, or downstream context slices.
- Test that full source text cannot appear inside the Course Model artifact.
- Test that resumed runs skip already approved upstream artifacts.
- Keep all Phase 1 tests green throughout the replacement work.

## Main risks

| Risk | Control |
|---|---|
| Intake becomes an exhausting questionnaire | Ask only unresolved, high-impact questions; allow explicit assumptions for low-impact gaps. |
| Research returns impressive-looking but weak sources | Require locators, captured content, trust notes, relevance, and explicit human decisions. |
| Course Model becomes a research dump | Enforce compact schema limits and keep evidence/source content in separate stores. |
| Source IDs are assigned before the hierarchy exists | Let research use provisional assignments, then reconcile and validate final node IDs during structure creation. |
| Live web variability makes tests flaky | Mock external research in tests and reserve live access for the acceptance run. |
| Upstream agents overfit to the acceptance subject | Static prompt checks plus FRM and a second tiny subject fixture for contract-only traversal. |

## First executable slice

This section is retained as historical implementation guidance. It is not the current next action after prototype completion.

Begin with **P2.1**: add the Course Brief v0.2 contract, define the sparse subject-request boundary, and create the non-FRM mocked contract test. Do not call live research APIs until that chain is green.
