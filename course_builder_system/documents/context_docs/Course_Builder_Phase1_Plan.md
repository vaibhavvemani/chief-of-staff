# Course Builder — Phase 1 Implementation Plan

> **Status:** Design locked, ready to implement. Created 2026-06-08.
> **Phase 1 goal:** Replace the `student_content_step` stub with a *real* Student Content agent for one FRM subtopic, with grounding, separate verification, claim-level attribution, and a review rubric.
> **Done when:** for **m1_s1 "Nature of Financial Risk"**, the agent's output scores ≥ the manual version on the rubric and a human review takes **minutes (light touch-ups), not a rewrite**.
> **Timebox:** ~3 weeks target, 4 weeks ceiling (this is the make-or-break phase and the most justified place in the whole project to spend a buffer week). Part of a ~13.5-week whole-POC budget due ~2026-09-08.
> **Team:** 2 peer interns (P1 = Vaibhav, P2 = peer), ~4–6 focused hrs/day × 5 days, worked fully paired/fluid with a primary lane each sprint.

This doc is the single source of truth for Phase 1. Sections A–H are the **locked design decisions** (the "what + why"); Section J is the **sprint plan**; Sections K–N are **Done / risks / scope / lessons**.

---

## A. Target & scope (Cluster 1)

| Decision | Why |
|---|---|
| **Subtopic = `m1_s1` "Nature of Financial Risk"** | Flagship first subtopic → most complete manual benchmark; mixes definitions (tests factual accuracy) + the Lehman case (tests grounding/verification). Contingent on Section B confirming its manual assets are complete. |
| **Target all 9 asset types, built in waves, risk-first** | Order: (1) **Course Content** first — the make-or-break "full body of knowledge"; (2) rest of the **core 5** — Learning Objectives, Summary, Case Study, Assessment; (3) the **light 4** — Important Person, Did you know, Activities, Resources. Light 4 deferrable to the buffer sprint if tight. |
| **"Done" = one subtopic; a 2nd is an optional buffer stretch** | Matches the master doc; scaling to many subtopics is Phase 4. Prompts stay **parameterized** by (subtopic, concepts, sources) so a 2nd subtopic is a cheap check, not a rewrite. |

## B. Benchmark / gold standard (Cluster 2)

| Decision | Why |
|---|---|
| **Acquire m1_s1's manual assets (P1 drops `.docx`/`.pptx` into `benchmark/m1_s1/`), extract to text once** | The manual assets are **not in the repo today** (`course_content/` is empty). #1 practical blocker. No parsing pipeline — one-off extraction for one subtopic (file I/O is Phase 5). |
| **Gold standard = a hand-built reference `content_package.json`** | Same shape as agent output → apples-to-apples per-asset, per-dimension scoring in the eval. |
| **Manual = floor + structural/house-style reference; the rubric judges "≥ manual"** | The manual is itself uneven. **Never optimize for textual similarity** to it — that would cap the agent at the manual's quality, when the point is to be able to exceed it. |

## C. Inputs the agent consumes (Cluster 3)

| Decision | Why |
|---|---|
| **Hand-author the Domain Model in the locked `domain_model` schema — deep on m1_s1, thin stubs for the other m1 subtopics** | Phase 2 builds the real DM later and swaps in with zero contract change. Thin-neighbor awareness keeps chapters **self-contained with no cross-linkage**. |
| **A "grounding source" = real source TEXT, curated to excerpts** (not URL-only) | Grounding means generating from *supplied verified sources, not model memory*. A URL with no content isn't grounding. |
| **3–6 strong sources, one text file per id in `sources/` (`sources/g1.md` …), DM registers id→metadata** | Quality over quantity for one foundational subtopic; keeps the verification load sane. |

## D. Generation agent (Cluster 4)

| Decision | Why |
|---|---|
| **Per-asset generation, anchored on Course Content** | Generate Course Content first; generate every other asset conditioned on the finished Course Content + DM + sources → cross-asset coherence (Summary summarizes what was taught, Assessment tests it) **without** a separate planning step and **without** the monolith. |
| **Single-shot per asset, escalate only if measured** | Only Course Content escalates to outline→draft if the eval shows it's thin. **No writer self-refinement of facts** — the writer never blesses its own claims (that's verification's job). |
| **Inject the whole m1_s1 DM slice + all source texts into every asset prompt** | No per-asset source *selection* (that edges toward RAG, deferred). Within token budget for a handful of small sources. |
| **Comprehensiveness-first; Blueprint slide/hour counts are a loose guide** | Instruct for "the full body of knowledge" at depth ≈ manual + the 20–50% extra ethos. Exact counts are a Phase 5 packaging concern; `file: null`, text only. |
| **One prompt template per asset type, parameterized by subtopic context, versioned in `prompts/`** | Asset types are genuinely different; composition over monolith. |
| **Opus (latest) for generation and verification; log tokens/cost per run** | One-subtopic volume → cost trivial; depth-first now, optimize model mix in Phase 4 using the logged data. |
| **Feedback-driven revision deferred until baseline works** | Build generate→verify→eval first with `feedback` ignored; wire per-asset regeneration late. Keep the `(inputs, feedback)` signature throughout so it's a clean extension. |

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
| **Phase 1: annotate + surface to human (don't block, don't auto-revise yet)** | Matches the checkpoint model + deferred revision. Once revision is wired late in Phase 1, these flags become the targeted regeneration inputs — closing the loop then. |

## G. Eval & scoring (Cluster 7)

- **Rubric = 7 dimensions** (master doc §11): factual accuracy, coverage, source attribution, pedagogical clarity, asset completeness, house style, review time.
- **Scale: 1–5 per dimension, 3 anchored to "matches the manual version."** "≥ manual" = ≥3 on every comparative dimension; review-time has its own target.
- **Scoring is hybrid, human is the final arbiter:** auto for mechanical (asset completeness; attribution + factual accuracy come from the verifier's verdicts); **LLM-as-judge proposes** coverage + house style; **human is final scorer** for pedagogical clarity + review time and **ratifies** everything. A model is never the *sole* arbiter of the bar.
- **Two-tier comparison:** LLM-judge head-to-head (agent vs manual) each iteration for a fast directional signal; **blind side-by-side human scoring (A/B anonymized)** at the "done" gate for the real call.
- **Scorecard:** one JSON per run in `evals/` (rubric scores + verifier stats + review-time + prompt git SHA) + a tiny trend script. File-based.
- **Review-time:** timed human review at the milestone (wall-clock + edit-extent) against a **threshold set in Sprint 1** (e.g. "≤ ~15 min, touch-ups not a rewrite"). This *is* the done-condition.

## H. Engineering & integration (Cluster 8)

- **Orchestrator never changes.** `student_content_step` becomes a thin adapter: call generation agent → verification → assemble v0.2 Content Package → return `{"content_package": artifact}`.
- **Clean v0.2 schema bump:** update the Content Package schema, the example sample, the stub, and `integrity.py` together (claim `source_id`s must resolve to grounding ids).
- **`llm.py`:** thin Anthropic SDK wrapper — call, retry, **token/cost logging**, and a **local response cache** keyed on (model + prompt-hash) so unchanged assets don't re-call the API while tuning.
- **Prompts versioned by git**; scorecards record the SHA. Secrets via gitignored `.env` → `os.environ`.
- **Tests on the contract, not quality:** schema-valid v0.2, all expected assets present, claims resolve, integrity passes; LLM mocked for plumbing tests. Quality lives in the eval harness.

**Module layout:**
```
llm.py                       # Anthropic wrapper: call, retry, token log, prompt-hash cache
agents/
  student_content.py         # per-asset generation, anchored on Course Content
  verification.py            # separate asset-by-asset verifier
prompts/                     # one template per asset type + verification.md (git-versioned)
sources/                     # g1.md, g3.md … curated source texts (one per id)
domain/
  m1_s1_domain_model.json    # hand-authored DM input (deep m1_s1 + thin m1)
benchmark/
  m1_s1/                     # manual gold assets dropped in + extracted text
  m1_s1.gold.content_package.json   # the reference package
evals/
  rubric.md                  # rubric + review-time threshold
  run_*.json                 # per-run scorecards
  compare.py                 # trend / two-tier comparison helper
```

---

## J. Sprint plan

3 one-week sprints + 1 buffer. Paired/fluid with a primary lane each sprint; pair on the make-or-break pieces. Each sprint ends with a checkpoint demo + decision (mirrors the product's checkpoint model).

### Sprint 1 — Ruler, inputs, wrapper, spike
*Lock what "good" means and assemble every agent input before generating for real; get one throwaway generation on screen.*

| Owner | Tasks |
|---|---|
| **P1** | **Acquire + transcribe** m1_s1 manual assets → `benchmark/m1_s1.gold.content_package.json` (#1 risk — day 1). Write the **rubric** (`evals/rubric.md`, 7 dims, 1–5, 3=manual) + set the **review-time threshold**. |
| **P2** | Hand-author the **DM** (`domain/m1_s1_domain_model.json`, deep m1_s1 + thin m1). Curate **3–6 sources** → `sources/*.md`. Build **`llm.py`** (call, retry, token log, prompt-hash cache). Run the **throwaway spike** (one `course_content` draft) to shake out SDK + grounding. |
| **Pair** | Agree the rubric; confirm m1_s1's manual assets are complete (validates the subtopic choice). |

**DoD:** gold reference package + rubric + review-time threshold + DM + sources in repo; `llm.py` callable with caching; spike output seen. **Checkpoint:** gold + rubric + spike side by side → agree the bar.

### Sprint 2 — Generation pipeline, wired in
*Real grounded + attributed generation for the core 5, running inside the orchestrator on the v0.2 contract.*

| Owner | Tasks |
|---|---|
| **Shared, first** | **v0.2 schema bump:** Content Package schema + example sample + stub + `integrity.py` (claim `source_id`s resolve). |
| **P1** | **Generation agent** — per-asset prompt templates (`prompts/`) for the core 5; Course-Content-first anchored generation; claim-level attribution; allow-but-flag ungrounded. |
| **P2** | Wire **`student_content_step`** (thin adapter) → `run.py` produces a real v0.2 Content Package, integrity passes, checkpoint pauses; source-id plumbing. |
| **Pair** | Meet at the contract; first live end-to-end run. |

**DoD:** `python run.py` generates a real v0.2 Content Package for the core 5, passes integrity, pauses at the checkpoint (quality not yet judged). **Checkpoint:** live run, eyeball the content.

### Sprint 3 — Verification + eval + iterate core-5 to the bar
*The separate verifier, the scoring harness, and the tuning loop that gets the core 5 to ≥ manual.*

| Owner | Tasks |
|---|---|
| **P2** | **Verification agent** (asset-by-asset, adversarial) → verdicts written back into `claims[]` + per-asset summary. |
| **P1** | **Eval harness** — auto mechanical scores + LLM-judge proposes coverage/house-style; JSON scorecard in `evals/` + trend script; blind-gate setup. |
| **Pair** | First scored run → **iterate** core 5 (generate→verify→score vs manual), split by gap type (P1 generation-quality, P2 verification/attribution), until each core asset hits ≥3. |

**DoD:** core 5 hit ≥3 at a blind scoring; verification surfaced; scorecard trend shows the climb. **Checkpoint:** baseline → improved scorecard; top remaining gaps.

### Sprint 4 — BUFFER / finish: light-4 sweep, revision loop, done-gate, handoff
*May land inside 3 weeks if iteration is fast; otherwise this is the justified overrun week.*

- Sweep the **light 4** assets (reuse the machinery; bar = present & decent).
- Wire **feedback-driven per-asset revision** (the deferred 4g loop).
- **Final blind human gate** on all done-conditions + timed review.
- **Phase 1 handoff doc** (Section M lessons) + update the master context; mark Phase 1 done.

**DoD:** see Section K. **Checkpoint:** final agent-vs-manual blind scoring → **Phase 1 done?**

---

## K. Definition of Done (the exit checklist)

For **m1_s1**:
- [ ] All 9 assets generated, grounded, claim-level attributed, and verified.
- [ ] Output is schema-valid **v0.2**, passes `integrity.py`, runs end-to-end via `run.py` with the checkpoint.
- [ ] **Core 5 score ≥3** ("matches manual") on every comparative rubric dimension at the **blind human gate**; **light 4 present & decent**.
- [ ] **Timed human review ≤ threshold**, edits are touch-ups not a rewrite.
- [ ] Verification pass runs; its summary is surfaced at the checkpoint.
- [ ] Gold reference package + rubric + sources + hand-authored DM all live in the repo.
- [ ] Phase 1 handoff doc written; master context updated.

## L. Risks & de-risking

| Risk | Mitigation |
|---|---|
| **Manual gold assets hard to get / incomplete** (#1) | Acquire Sprint 1, day 1. Fall back to another m1 subtopic if blocked. |
| **Iteration runs forever** (open-ended) | Timeboxed to ~3 wks; the buffer sprint is the release valve; treat as the most-justified overrun. |
| **Thin / noisy sources cap quality** | Curate 3–6 strong verified sources; allow-but-flag for gaps. |
| **Verifier itself unreliable** (same-model blind spot) | Manual spot-checks during iteration; **diverse-model verifier is the fallback** if spot-checks show misses. |
| **Prompt overfitting to m1_s1** | Parameterized prompts; optional 2nd subtopic in the buffer to check generalization. |
| **v0.2 schema churn breaks the skeleton** | Contract tests + `integrity.py` update land together with the bump. |

## M. Reusable lessons to capture (the POC double-payoff → handoff doc)

- How an agent builds *trustworthy* content (generation + grounding + claim-attribution pattern).
- Where *separate* verification earns its keep — what it catches, its false-positive rate.
- The right **citation granularity** in practice (claim-level findings).
- The **eval pattern** (rubric + two-tier comparison + scorecard trend) as reusable measurement.
- What the human actually needed to review / redirect at the checkpoint.
- **Token/cost data** for the depth-vs-cost trade-off (feeds Phase 4).

## N. Out of scope for Phase 1 (YAGNI — deferred to their proper phases)

No RAG / vector DB · no parallelization · no multi-subtopic scaling (Phase 4) · no LMS / file packaging — `file: null`, text only (Phase 5) · no agent framework (direct SDK) · Steps 1/2/4 stay stubs · console checkpoint only, no UI (Phase 6) · no model-mix cost optimization (Phase 4).

---

## Open items to settle in Sprint 1 (not blockers to starting)

1. Confirm m1_s1's manual assets are complete once dropped in (else fall back subtopic).
2. Set the concrete **review-time threshold** number when writing the rubric.
3. Choose the specific 3–6 **grounding sources** for m1_s1 (definitional + risk-taxonomy + Lehman-case facts).
