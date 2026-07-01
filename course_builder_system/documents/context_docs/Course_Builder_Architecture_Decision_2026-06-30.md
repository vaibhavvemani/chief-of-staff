# Course Builder — Architecture Decision: Domain-Agnostic Workflow and Compact Course Model

> **Status:** Approved
> **Date:** 2026-06-30
> **Scope:** Target architecture and migration boundary. FRM Phase 1 remains a benchmark, not the product domain.

## Decision

The Course Builder must support course creation on any subject from a sparse initial request. The target workflow is:

`conversational brief → approved course outcomes → research dossier + source approval → Course Model → Blueprint → content → lesson plan → package`

The former Table of Contents and Domain Model become one compact **Course Model** with two logical views:

- hierarchy: modules, subtopics, order, titles, and scope;
- scoped knowledge: concepts, dependencies, coverage requirements, and approved source IDs.

Competitor findings, candidate-source reasoning, and full source texts do not belong in the Course Model. They remain in a separate Research Dossier and source store.

## Human decisions

The system must pause for approval of:

1. the clarified Course Brief;
2. course-level outcomes before research;
3. competitor/research findings and which sources are trusted;
4. the combined Course Model;
5. each subtopic's Blueprint, including depth and selected asset types;
6. generated content and lesson plans.

Course-level outcomes guide research and structure. They are distinct from subtopic learning-objective documents delivered to learners.

## Context and generation policy

Full-course prompt injection is not the target architecture. A deterministic context builder selects, by stable ID:

- course/audience constraints and relevant approved outcomes;
- the current subtopic and its parent module;
- minimal neighbouring titles/scopes needed to avoid duplication;
- the current subtopic's Blueprint requirements;
- only approved source excerpts assigned to that subtopic/asset.

This is explicit context routing, not RAG. Add semantic retrieval only after measured source/context scale makes deterministic mappings inadequate.

Reusable prompts contain no subject facts. Subject-specific requirements—including named concepts, cases, people, events, and minimum coverage—come from the Course Model and Blueprint.

Long-form content uses:

`approved coverage plan → draft → coverage/depth check → bounded targeted regeneration → factual verification`

There is no universal minimum word count. Each Blueprint may define a target range alongside required concepts, examples, case depth, assessment complexity, and learning-time/depth targets. Revision closes named gaps rather than padding prose.

## Migration rules

1. Treat existing FRM Domain Model, TOC, source, Blueprint, and nine-asset files as fixtures for the Phase 1 quality benchmark.
2. Introduce the Course Model contract and migrate stable TOC/Domain Model IDs into it without duplicating the hierarchy.
3. Add Course Outcome and Research Dossier/source-decision contracts now as
   approved Phase 1 fixtures; replace their fixture-backed steps with
   conversational and research agents in Phase 2.
4. Extend the Blueprint with per-subtopic depth budgets, explicit asset
   selection, and an asset-level subset of the sources already approved for the
   subtopic.
5. Add deterministic context assembly and verify unrelated source text is excluded.
6. Remove FRM coverage facts from generic prompt templates; encode them in the FRM fixture.
7. Preserve claim-level attribution, independent verification, scorecards, checkpoint revision, resumability, and referential-integrity checks.
8. Add a small non-FRM fixture as a generality smoke test; whole-course scaling remains Phase 4.

## Consequences

- Human approval becomes more granular where trust and direction matter, without requiring continuous supervision.
- One Course Model reduces document and approval duplication while remaining readable and correctable.
- Prompt cost scales with the active subtopic rather than the total source corpus.
- Phase 1's FRM result remains useful evidence, but it cannot by itself prove domain generality.
- Existing v0.1 contracts are migration inputs, not permanent locked architecture.
