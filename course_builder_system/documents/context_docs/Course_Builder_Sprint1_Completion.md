# Course Builder — Sprint 1 (Foundations) Completion Note

> **Status:** ✅ COMPLETE — all 9 tasks + the `S1.M` milestone gate satisfied.
> **Verified:** 2026-06-23 (filesystem audit of every deliverable).
> **Purpose:** Hand-off context for Sprint 2 — what got built, where it lives, and the flags to carry forward.
> **Companions:** design SoT → `Course_Builder_Phase1_Plan.md`; task index → `Course_Builder_Phase1_Timeline_ClickUp.csv`; schedule → `Course_Builder_Phase1_Sprint_Sheet.md`.

Sprint 1 built the **quality bar + inputs + plumbing** for the Phase 1 target subtopic **`m1_s1` "Nature of Financial Risk"**. No generation agent yet — that's Sprint 2.

---

## Task completion

| Task | Owner | Deliverable | Evidence (verified on disk) |
|---|---|---|---|
| **S1.1** Acquire manual gold assets | Vaibhav | `benchmark/m1_s1/raw/` | 8 source files (`.docx`/`.pptx`) covering all 9 asset types + `Course Status.xlsx` |
| **S1.2** Extract assets → text | Vaibhav | `benchmark/m1_s1/extracted/` | 8 `.md` text files matching the raw assets |
| **S1.3** Confirm complete / fallback decision | Vaibhav | *(decision — no file)* | Outcome confirmed: full 9-asset extraction is complete and `m1_s1` was retained (no fallback subtopic). No standalone artifact. |
| **S1.4** Hand-built gold `content_package.json` | Vaibhav | `benchmark/m1_s1.gold.content_package.json` | Valid JSON; matches the locked `content_package` shape; `subtopic_id: m1_s1`; **all 9 assets populated** (course_content ≈22K chars; assessment carries a `solution`/answer key) |
| **S1.5** Rubric (7 dims) + review-time threshold | Vaibhav | `evals/rubric.md` | 7 dimensions; 1–10 scale with **6 = "matches manual"**; review-time threshold **≤60 min for the core 5** (per-asset breakdown); hybrid scorer table |
| **S1.6** Curate 3–6 grounding sources | Siddarth | `sources/g1–g5.md` + `README.md` | 5 curated sources with stable ids + id→category mapping |
| **S1.7** Hand-author Domain Model | Siddarth | `domain/m1_s1_domain_model.json` | Deep `m1_s1` (8 concepts + 8 key-points) + 5 thin sibling stubs; all source/dependency refs resolve; subtopics match the TOC |
| **S1.8** `llm.py` wrapper + `.env` | Siddarth | `llm.py`, `.env` | Live Anthropic round-trip verified; token-log + prompt-hash cache fire; SDK retry built in |
| **S1.9** Throwaway end-to-end smoke run | Siddarth | `logs/smoke_s1_9_output.md` (+ `smoke_s1_9.py`) | DM + sources → prompt → `llm.call()` → output; cited all 5 sources inline, stayed in `m1_s1` scope; log + cache incremented |
| **S1.M** Milestone gate | — | (S1.4 + S1.5 + S1.9) | All three dependencies satisfied → gate passed |

---

## Where the Sprint 1 outputs live (input map for Sprint 2)

```
benchmark/
  m1_s1/raw/                          # S1.1 manual assets (.docx/.pptx)
  m1_s1/extracted/                    # S1.2 extracted text (.md)
  m1_s1.gold.content_package.json     # S1.4 gold reference (score against this)
evals/
  rubric.md                           # S1.5 rubric + review-time threshold
sources/
  g1..g5.md, README.md                # S1.6 grounding source texts
domain/
  m1_s1_domain_model.json             # S1.7 hand-authored Domain Model input
llm.py  +  .env                       # S1.8 Anthropic wrapper (call/retry/log/cache)
logs/                                 # token log + S1.9 smoke output (gitignored)
.llm_cache/                           # prompt-hash response cache (gitignored)
```

---

## Notes & flags to carry into Sprint 2

1. **Gold package is `schema_version: 0.1`.** Correct for Sprint 1, but **S2.1 bumps the content_package to v0.2** (`claims[]` + `verification`). When it lands, revisit `m1_s1.gold.content_package.json` so the eval stays apples-to-apples against agent output. *(Not a defect — a Sprint 2 to-do.)*

2. **Domain Model is subtopic-structured (a superset of the flat sample).** The body uses `body.subtopics[]` with `depth: deep|thin`, nesting `concepts[]` + `key_points[]` under the deep `m1_s1` slice, plus body-level `grounding_sources[]`. Implications:
   - Sprint 2 prompts (S2.2) should inject the whole `m1_s1` slice (deep concepts + key_points) + the thin-neighbor stubs (stay-in-lane awareness) + the source registry.
   - When Phase 2 auto-builds the DM, it must emit **this** richer shape (not the original flat sample) for the "swap in with zero contract change" promise to hold. Flag this in the Phase 1 handoff doc (S3.9).

3. **Source ids `g1`–`g5` are canonical and stable.** Generated content (S2) and the verifier (S3) will cite them; the DM and rubric already assume them. **Do not renumber.** Mapping: `g1` foundational (risk vs uncertainty) · `g2`/`g3`/`g4` taxonomy (credit/liquidity/market+operational) · `g5` Lehman case.

4. **`llm.py` usage gotchas.**
   - Reads `ANTHROPIC_API_KEY` via `load_dotenv()` from `.env` (gitignored). The account behind the key must stay funded (a low balance returns a `400`, not an auth error).
   - `call(..., use_cache=True)` by default — while tuning prompts, pass `use_cache=False` or clear `.llm_cache/` so unchanged inputs actually re-call.
   - Default model `claude-opus-4-8`; falls back cleanly with a `sys.exit` message if the key is unset.

5. **`S1.9` is a throwaway.** `smoke_s1_9.py` is a plumbing smoke test, **not** the production generator. Real per-asset generation is **S2.2 → `agents/student_content.py`**, anchored on Course Content. The smoke script can be kept as a re-runnable plumbing check or deleted.

6. **`S1.3` left no artifact** (it was a go/no-go decision). Its outcome is confirmed by the complete asset set; if a paper trail is wanted, drop a one-line note in `benchmark/m1_s1/`.

---

## What went well / watch-outs

- **Plumbing proven before generation.** The S1.9 smoke run confirmed DM + sources → live model call → grounded, in-scope output, so Sprint 2 starts on a known-good pipe.
- **Grounding behaved as designed.** Even the throwaway cited all five sources and stayed inside `m1_s1` — early signal the deep/thin DM split and source registration work.
- **Watch:** the biggest Sprint 2 risk is **S2.3 Course Content depth** (the make-or-break asset) and the v0.2 schema bump touching the sample/stub/`integrity.py` together (S2.1). Keep `integrity.py` green after each change.

---

## Sprint 2 entry point

The S1.M gate is satisfied, so Sprint 2 is unblocked. The chain:

- **S2.1** v0.2 schema bump (schema + sample + stub + `integrity.py`, together) ← was blocked only by S1.M
- **S2.2** Course Content prompt + generation logic (`agents/student_content.py`)
- **S2.3** Generate Course Content + inspect (★ make-or-break)
- **S2.4** Prompts for the rest of the core 5 → **S2.5** thin adapter → **S2.6** end-to-end run → **S2.7** contract tests
- **S2.M** gate: end-to-end run produces real, grounded core-5 content; contract tests green.
