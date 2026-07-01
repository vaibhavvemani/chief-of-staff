# Course Builder — Phase 1 Implementation Plan

> **Status:** Implementation in progress; Sprints 1–2 are complete and Sprint 3 engineering is ready for the live quality run. Created 2026-06-08; architecture amended 2026-06-30.
> **Phase 1 goal:** Prove a *domain-agnostic* Student Content path using one FRM subtopic as a benchmark fixture, with grounding, separate verification, claim-level attribution, dynamic depth/coverage controls, and a review rubric.
> **Done when:** for **m1_s1 "Nature of Financial Risk"**, the agent's output scores ≥ the manual version on the rubric and a human review takes **minutes (light touch-ups), not a rewrite**.
> **Timeline & ownership:** the sprint breakdown, schedule, and who-does-what live in the companion boss-facing **Sprint Sheet** → `Course_Builder_Phase1_Sprint_Sheet.md`. (Summary: ~3-week target, 4-week ceiling; 2 peer interns paired.)

This doc is the single source of truth for **building** Phase 1. Sections A–H are the **locked design decisions** (the "what + why"); Sections K–N are **Done / risks / scope / lessons**. The 2026-06-30 decisions supersede any earlier statement that reusable prompts may contain FRM coverage rules, that all source text should be injected into every call, or that separate TOC and Domain Model artifacts remain the target architecture. The cross-phase migration record is `Course_Builder_Architecture_Decision_2026-06-30.md`.

---

## A. Target & scope (Cluster 1)

| Decision | Why |
|---|---|
| **Subtopic = `m1_s1` "Nature of Financial Risk"** | Flagship benchmark with a strong manual comparison; mixes definitions (factual accuracy) and the Lehman case (grounding/verification). It is test data, never a product-domain assumption. |
| **Generate all 9 assets for this benchmark** | Phase 1 deliberately selects all 9 in its Blueprint fixture to exercise the complete path. In the product, the human selects the appropriate asset list independently for each subtopic. |
| **"Done" = one benchmark subtopic; a non-FRM smoke test protects generality** | Scaling to many subtopics is Phase 4. Reusable prompts receive subject, coverage, depth, concepts, and source context only through approved artifacts. A cheap non-FRM fixture/test should fail if FRM facts leak into generic logic. |

## B. Benchmark / gold standard (Cluster 2)

| Decision | Why |
|---|---|
| **Manual m1_s1 benchmark is acquired and extracted** | Raw `.docx`/`.pptx` files, extracted text, and the gold Content Package are present under `benchmark/m1_s1/`; they remain the comparison fixture rather than prompt input to copy. |
| **Gold standard = a hand-built reference `content_package.json`** | Same shape as agent output → apples-to-apples per-asset, per-dimension scoring in the eval. |
| **Manual = floor + structural/house-style reference; the rubric judges "≥ manual"** | The manual is itself uneven. **Never optimize for textual similarity** to it — that would cap the agent at the manual's quality, when the point is to be able to exceed it. |

## C. Inputs the agent consumes (Cluster 3)

| Decision | Why |
|---|---|
| **Hand-author one compact Course Model fixture** | The Course Model combines the TOC hierarchy with the useful Domain Model fields: subtopic scope, concepts, dependencies, dynamic `coverage_requirements`, and approved source IDs. Thin neighbour summaries maintain course awareness without injecting the whole course. |
| **Hand-author a minimal Blueprint fixture** | For m1_s1 it selects all 9 assets and defines depth, target learning minutes, a target word range, required concepts/examples/case depth, and assessment complexity. These values are inputs, not hardcoded prompt rules. |
| **A "grounding source" = approved real source material stored separately** | A URL with no content is not grounding. Phase 1 stores compact curated evidence excerpts/notes in `sources/` plus the original locator; the Course Model stores only IDs/metadata. Later research may retain the full approved corpus outside prompts while routing bounded excerpts into each call. |
| **3–6 strong approved sources for this benchmark** | This is a benchmark-specific source selection, not a product cap. Later courses may have many more sources; source-to-subtopic assignments and excerpt selection keep prompts bounded. |
| **Deterministic context builder** | For an asset call, select the Course Brief/outcome essentials, current subtopic, parent module, minimal neighbour titles/scopes, its Blueprint depth/asset requirements, and only assigned approved source excerpts. This is ID-based selection, not RAG. |

## D. Generation agent (Cluster 4)

| Decision | Why |
|---|---|
| **Per-selected-asset generation, anchored on Course Content** | Generate only assets selected in the Blueprint. Generate Course Content first, then condition dependent assets on its approved content plus their smaller context slice for cross-asset coherence without a monolith. |
| **Long-form loop = coverage plan → draft → check → bounded targeted regeneration** | The Course Model coverage requirements and Blueprint depth budget define the plan. A deterministic check retries a clearly short/incomplete draft with named gaps and a hard attempt cap. Section-by-section drafting is deferred until whole-course scale shows it is worth the extra calls. The writer does not self-verify factual support; that remains the verifier's job. |
| **No universal minimum length** | `target_word_range` is a subtopic-specific guardrail. Passing requires required-concept coverage, appropriate depth, examples/cases/assessment complexity, and pedagogical coherence—not padding to a global word count. |
| **Inject only the deterministic context slice** | Even though the FRM benchmark corpus is small, the reusable path must work when a course has many large sources. Assigned excerpts are supplied per subtopic/asset; the complete source corpus is not pasted into every prompt. |
| **One generic prompt template per asset type, versioned in `prompts/`** | Prompts define the asset task and consume artifact values. FRM facts such as required concepts, people, events, or cases belong in Course Model `coverage_requirements` and Blueprint fields, never in the reusable template. |
| **Opus (latest) for generation and verification; log tokens/cost per run** | One-subtopic volume → cost trivial; depth-first now, optimize model mix in Phase 4 using the logged data. |
| **Targeted feedback revision closes the loop** | Verification, coverage/depth findings, and human feedback identify the asset/section to revise. Preserve unaffected content and re-run verification on changed factual claims. |

## E. Source attribution (Cluster 5)

| Decision | Why |
|---|---|
| **Claim-level attribution** | Each *significant factual claim* (dates, figures, named events, regulatory facts — not framing) carries a `source_id`. The **writer attributes**; the **verifier confirms + locates the passage**. Asset-level was too coarse for real verification. |
| **Clean content + a parallel `claims[]` array** | `content` stays clean prose; `claims[]` carries the attribution + verifier verdicts. `sources[]` becomes the *derived union* of non-null claim `source_id`s (keeps `integrity.py` working). |
| **Ungrounded claims allowed but flagged (`source_id: null`)** | Implements "an unsupported claim is visible, not hidden." Keeps content comprehensive while keeping trust honest; verifier scrutinizes flagged claims hardest. |

**v0.2 asset shape (per asset):**
```jsonc
{
  "id": "m1_s1_cc", "type": "course_content", "title": "...", "format": "docx",
  "content": "<clean prose>",
  "claims": [
    { "id": "c1", "text": "<the claim>", "source_id": "g3",   // or null = ungrounded
      "support": null,            // verifier fills: supported | partial | unsupported
      "supporting_excerpt": null, // verifier fills
      "note": null }
  ],
  "sources": ["g3"],              // derived union of non-null claim source_ids
  "verification": {               // verifier fills (per asset)
    "supported": 0, "partial": 0, "unsupported": 0, "ungrounded": 0,
    "unattributed_found": [], "checked_at": null },
  "solution": "...",              // teacher-only, assessments
  "file": null, "status": "done"
}
```

## F. Verification pass (Cluster 6)

| Decision | Why |
|---|---|
| **Checks factual support + attribution integrity ONLY** | (1) each attributed claim — does the cited source support it? (2) flag ungrounded claims; (3) catch significant claims the writer left un-attributed. **Not** pedagogy/coverage/style (the rubric's job; pedagogy can't be auto-judged). |
| **Separate adversarial prompt, same model (Opus), run asset-by-asset** | "You did NOT write this; find claims the source doesn't support." One call per asset → per-claim verdicts, with full asset context. |
| **Output: per-claim verdicts written back into `claims[]` + a per-asset verification summary** | The summary is exactly what the human sees at the checkpoint. |
| **Annotate, surface, and support targeted revision** | Verification findings are visible to the human and become scoped revision inputs. The system revises only affected sections/assets and does not let the writer silently bless its own factual changes. |

## G. Eval & scoring (Cluster 7)

- **Rubric = 7 dimensions** (master doc §11): factual accuracy, coverage, source attribution, pedagogical clarity, asset completeness, house style, review time.
- **Scale: 1–10 per dimension, 6 anchored to "matches the manual version."** "≥ manual" = ≥6 on every comparative dimension; review-time has its own target. Scores 1–5 are below the manual bar, 6 means manual-equivalent, 7–8 means better than manual, and 9–10 means substantially better than manual.
- **Scoring is hybrid, human is the final arbiter:** auto for mechanical (asset completeness; attribution + factual accuracy come from the verifier's verdicts); **LLM-as-judge proposes** coverage + house style; **human is final scorer** for pedagogical clarity + review time and **ratifies** everything. A model is never the *sole* arbiter of the bar.
- **Two-tier comparison:** LLM-judge head-to-head (agent vs manual) each iteration for a fast directional signal; **blind side-by-side human scoring (A/B anonymized)** at the "done" gate for the real call.
- **Scorecard:** one JSON per run in `evals/` (rubric scores + verifier stats + review-time + prompt git SHA) + a tiny trend script. File-based.
- **Review-time:** timed human review at the milestone (wall-clock + edit-extent) against the locked rubric threshold: **≤60 minutes for the full core 5 package, with light edits only**. This *is* the done-condition.

## H. Engineering & integration (Cluster 8)

- **Orchestrator remains generic.** `student_content_step` stays a thin adapter: build an asset-specific context slice → generate/expand → verify → assemble the Content Package → return `{"content_package": artifact}`. Contract wiring may change; course-domain logic must not enter orchestration.
- **Migrate contracts together:** replace separate TOC/Domain Model consumption with the compact Course Model; add Blueprint depth and per-subtopic asset-selection fields; update samples, fixtures, and `integrity.py` so claim and assignment `source_id`s resolve to approved sources.
- **`llm.py`:** thin Anthropic SDK wrapper — call, retry, **token/cost logging**, and a **local response cache** keyed on (model + prompt-hash) so unchanged assets don't re-call the API while tuning.
- **Prompts versioned by git**; scorecards record the SHA. Secrets via gitignored `.env` → `os.environ`.
- **Tests on the contract, not quality:** selected assets are present (all 9 for m1_s1), unselected assets are not required, claims resolve to approved sources, context slices exclude unrelated sources, integrity passes, and generic prompts contain no FRM coverage facts. LLM calls are mocked for plumbing tests; quality lives in the eval harness.

**Module layout:**
```
llm.py                       # Anthropic wrapper: call, retry, token log, prompt-hash cache
schemas/
  content_package.v0.2.schema.json  # formal Content Package contract
agents/
  student_content.py         # per-asset generation, anchored on Course Content
  verification.py            # separate asset-by-asset verifier
prompts/                     # one template per asset type + verification.md (git-versioned)
sources/                     # g1.md, g3.md … curated source texts (one per id)
course_models/
  m1_s1.course_model.json    # combined hierarchy + scoped domain fixture
blueprints/
  m1_s1.blueprint.json       # depth budget + all-9 benchmark asset selection
benchmark/
  m1_s1/                     # manual gold assets dropped in + extracted text
  m1_s1.gold.content_package.json   # the reference package
evals/
  rubric.md                  # rubric + review-time threshold
  run_*.json                 # per-run scorecards
  compare.py                 # trend / two-tier comparison helper
```

---

## K. Definition of Done (the exit checklist)

For **m1_s1**:
- [ ] All 9 assets generated, grounded, claim-level attributed, and verified.
- [ ] Output is schema-valid **v0.2**, passes `integrity.py`, runs end-to-end via `run.py` with the checkpoint.
- [ ] **Core 5 score ≥6** ("matches manual") on every comparative rubric dimension at the **blind human gate**; **light 4 present & decent**.
- [ ] **Timed human review ≤ threshold**, edits are touch-ups not a rewrite.
- [ ] Verification pass runs; its summary is surfaced at the checkpoint.
- [x] Gold reference package + rubric + approved sources + hand-authored Course Model and Blueprint fixtures all live in the repo.
- [x] Generic prompts contain no FRM-specific required coverage; a non-FRM fixture can traverse the reusable path.
- [x] Context construction injects only the current subtopic slice and assigned approved source excerpts.
- [ ] Phase 1 handoff doc written; master context updated.

## L. Risks & de-risking

| Risk | Mitigation |
|---|---|
| **Manual benchmark does not represent the desired product quality** | Use it as the comparison floor and house-style reference, never as a textual-similarity target; the rubric can reward better output. |
| **Iteration runs forever** (open-ended) | Timeboxed to ~3 wks; the buffer sprint is the release valve; treat as the most-justified overrun. |
| **Thin / noisy sources cap quality** | Human approves 3–6 strong sources for the benchmark; allow-but-flag unsupported gaps. The number is not a product limit. |
| **Verifier itself unreliable** (same-model blind spot) | Manual spot-checks during iteration; **diverse-model verifier is the fallback** if spot-checks show misses. |
| **Prompt overfitting to m1_s1** | Put coverage in artifacts, add static checks for leaked FRM facts, and run a small non-FRM fixture through the generic path. |
| **Context becomes too large as research scales** | Keep source text separate, assign sources/excerpts by subtopic ID, log context size, and consider RAG only after deterministic slicing hits a measured limit. |
| **Length checks create padded prose** | Use Blueprint-specific ranges plus coverage/depth/example checks; targeted expansion repairs named gaps rather than appending generic text. |
| **Contract migration breaks the skeleton** | Course Model, Blueprint, Content Package fixtures, references, and `integrity.py` update together behind contract tests. |

## M. Reusable lessons to capture (the POC double-payoff → handoff doc)

- How an agent builds *trustworthy* content (generation + grounding + claim-attribution pattern).
- Where *separate* verification earns its keep — what it catches, its false-positive rate.
- The right **citation granularity** in practice (claim-level findings).
- The **eval pattern** (rubric + two-tier comparison + scorecard trend) as reusable measurement.
- What the human actually needed to review / redirect at the checkpoint.
- **Token/cost data** for context-slice size and the depth-vs-cost trade-off (feeds Phase 4).
- Whether coverage/depth checks produce useful targeted expansion without word-count padding.

## N. Out of scope for Phase 1 (YAGNI — deferred to their proper phases)

No RAG / vector DB · no live competitor-research agent or conversational intake agent (Phase 2; Phase 1 uses approved fixtures) · no parallelization · no whole-course scaling (Phase 4) · no LMS / file packaging *in the pipeline* — `file: null`, text only (Phase 5; the standalone SCORM 1.2 converter is already built but not yet wired into the pipeline — see `scorm_converter.md`) · no agent framework (direct SDK) · console checkpoint only, no UI (Phase 6) · no model-mix cost optimization (Phase 4).

---

## Resolved Sprint 1 inputs

The original Sprint 1 inputs—manual benchmark, rubric threshold, and benchmark grounding sources—are no longer architecture questions. Any missing operational input is tracked as execution status, not reopened as a design decision.
