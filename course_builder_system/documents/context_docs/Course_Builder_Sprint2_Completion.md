# Course Builder — Sprint 2 (Generator) Completion Note

> **Status:** ✅ COMPLETE — all 7 tasks + the `S2.M` milestone gate satisfied.
> **Verified:** 2026-06-25 (live end-to-end run + schema/integrity/contract checks on disk).
> **Purpose:** Hand-off context for Sprint 3 — what got built, where it lives, and the flags to carry forward.
> **Companions:** design SoT → `Course_Builder_Phase1_Plan.md`; task index → `Course_Builder_Phase1_Timeline_ClickUp.csv`; schedule → `Course_Builder_Phase1_Sprint_Sheet.md`; prior → `Course_Builder_Sprint1_Completion.md`.

Sprint 2 built the **content generator**: a real, source-grounded, claim-attributed Student Content agent that runs through the pipeline to produce the **core-5** assets for **`m1_s1` "Nature of Financial Risk"** as one schema-valid **v0.2 Content Package**. No verification or scoring yet — that's Sprint 3.

---

## Task completion

| Task | Owner | Deliverable | Evidence (verified on disk) |
|---|---|---|---|
| **S2.1** v0.2 schema bump | Siddarth | `schemas/content_package.v0.2.schema.json` + gold migration + stub + `integrity.py` | Formal v0.2 schema (claims[] + verification); gold `m1_s1.gold.content_package.json` migrated to v0.2; `integrity.py` checks claim `source_id`s + `sources[]`==claim-union *(landed on `main` before this sprint branch)* |
| **S2.2** Course Content prompt + generation logic | Vaibhav | `prompts/course_content.md`, `agents/student_content.py` | Per-asset generation anchored on Course Content; grounding rules + claim attribution *(on `main`)* |
| **S2.3** Generate Course Content + inspect ★ | Vaibhav | `outputs/phase1/m1_s1/s2_3_course_content_asset.json` | Real make-or-break asset generated and inspected *(on `main`)* |
| **S2.4** Prompts + logic for rest of core 5 | Vaibhav | `prompts/{learning_objectives,summary,case_study,assessment}.md`; `agents/student_content.py` refactor | Generic `AssetSpec` registry (5 specs); `generate_asset()`; each non-anchor asset conditioned on the finished Course Content; assessment carries `solution`. Commit `fa959ad` |
| **S2.5** `student_content_step` thin adapter | Siddarth | `steps.py` | Stub replaced with adapter: generate CC anchor → 4 conditioned assets → assemble v0.2 package via `make_artifact(schema_version="0.2")`. Orchestrator untouched. Commit `b9d3b7f` |
| **S2.7** Contract/skeleton tests (LLM mocked) | Siddarth | `tests/`, `conftest.py` | Dependency-free JSON-Schema-subset validator + 6 contract tests (schema-valid v0.2, all core-5 present, claims resolve, integrity passes, full pipeline dry-run with `llm.call` patched to raise). 6 passed. Commit `1445845` |
| **S2.6** Generate core 5 end-to-end ⚌ | Vaibhav + Siddarth | `courses/frm-demo/content_package.json` (+ `lesson_plan.json`) | Live pipeline run: 5 core assets, **schema-valid v0.2**, **integrity green**, 90 grounded claims; two integration fixes. Commit `cbf2171` |
| **S2.M** Milestone gate | — | (S2.6 + S2.7) | End-to-end run produces **real, grounded core-5 content**; contract tests green → gate passed |

---

## The generated baseline (S2.M deliverable)

`courses/frm-demo/content_package.json` — one v0.2 package, `subtopics[m1_s1].assets`:

| Asset | type | format | chars | claims (ungrounded) | sources | solution |
|---|---|---|---|---|---|---|
| `m1_s1_cc` | course_content | pptx | 10,748 | 27 (0) | g1–g5 | — |
| `m1_s1_lo` | learning_objectives | docx | 1,571 | 3 (0) | g1, g5 | — |
| `m1_s1_summary` | summary | docx | 5,163 | 17 (2) | g1–g5 | — |
| `m1_s1_case` | case_study | pptx | 7,916 | 25 (0) | g2–g5 | — |
| `m1_s1_assess` | assessment | pptx | 2,383 | 18 (2) | g1–g5 | ✅ answer key |

- **Grounding worked as designed.** 90 claims total, ~86 carrying a `source_id`; the 4 ungrounded (`source_id: null`) are the *allowed-but-flagged* kind the S3 verifier scrutinizes hardest.
- **Cross-asset coherence is visible** (the conditioning design): the Summary recaps the Course Content, the Case Study develops the Lehman example the CC references, and the Assessment's teacher-only answer key cites claim ids (e.g. `(cl1)`).

---

## Where the Sprint 2 outputs live (input map for Sprint 3)

```
agents/student_content.py            # S2.4 AssetSpec registry + generate_asset() (anchored generation)
prompts/
  course_content.md                  # S2.2 anchor prompt
  learning_objectives.md, summary.md, case_study.md, assessment.md   # S2.4 (conditioned on CC)
steps.py                             # S2.5 student_content_step thin adapter (assembles v0.2 package)
tests/
  schema_check.py                    # dependency-free v0.2 schema validator
  test_content_package_v02.py        # S2.7 contract tests (LLM mocked)
conftest.py                          # puts repo dir on sys.path for pytest
courses/frm-demo/content_package.json  # S2.M baseline core-5 package (score against gold in S3)
logs/llm_calls.jsonl                 # token log (cumulative)
.llm_cache/                          # prompt-hash response cache (gitignored)
```

---

## Integration fixes & key decisions (carry into Sprint 3)

1. **`sources[]` is derived authoritatively, not validated against the writer's echo.** The live run surfaced models routinely over-listing `sources` (naming every available source) even when their claims only cite a subset. Per Plan §E `sources` *is* the derived non-null claim source-id union, so `_validate_and_normalize_asset` now derives it and drops the brittle equality check rather than crashing a 5-asset run. The S3 verifier — not this field — is what scrutinizes attribution integrity.
2. **Assessment `max_tokens` 5,000 → 9,000.** It uniquely emits both `content` (questions) and a full `solution` answer key, which truncated at 5,000. Other assets had headroom.
3. **Contract tests are dependency-free.** `jsonschema` is **not** installed and could not be added: the dev machine's Homebrew Python is **PEP 668 externally-managed** (plain and `--user` pip installs are blocked; only `--break-system-packages` would work, which we avoided). `tests/schema_check.py` is a small validator covering exactly the keyword subset the v0.2 schema uses (`$ref`/`anyOf`/`const`/`enum`/`pattern`/`additionalProperties`/`uniqueItems`/`contains`), proven against the real schema with positive (gold benchmark) + 5 negative cases so it is not vacuously passing. **Decision for S3:** if real `jsonschema` is wanted, add a `requirements-dev.txt` + a venv.
4. **Feedback-driven revision is still deferred (Plan §D).** `student_content_step` keeps the `(inputs, feedback)` signature but ignores `feedback` in the baseline; targeted per-asset regeneration from verifier flags is **S3.6**.

---

## Token / cost data (feeds Phase 4 depth-vs-cost trade-off)

The cumulative token log (`logs/llm_calls.jsonl`, includes earlier smoke/S2.3 runs) shows **8 live calls, ~80.5K input + ~27.8K output tokens, ≈$3 ballpark** at Opus rates. Confirms the Plan's "one-subtopic volume → cost trivial" assumption; the prompt-hash cache made re-runs after each integration fix near-free (only the changed asset re-called).

---

## What went well / watch-outs

- **Plumbing held end-to-end.** The S2.7 full-pipeline dry-run (LLM mocked, `llm.call` patched to raise) proved the `run_pipeline` path *before* spending API budget, so the only live-run surprises were content-shaped (the two fixes above), not structural.
- **Grounding + conditioning behaved as designed** — dense claim attribution and visible cross-asset coherence on the first real run.
- **⚠️ Watch — Course Content depth.** The agent's CC is ~10.7K chars vs the manual gold's ~22.2K (≈48%), while the other four meet or exceed the manual length. Char count ≠ quality, but the make-or-break asset reads shorter than the manual. Per Plan §D, **CC depth-escalation (outline→draft) is an S3, eval-measured lever** — flagged here as the top quality risk for the Sprint 3 improve-and-re-measure loop, not an S2 blocker.
- **Housekeeping:** `ruff check .` reports one pre-existing `I001` import-sort nit in `run.py` (on `main`, one-line `--fix`); the repo's files are not uniformly `ruff format`-conformant. Sprint 2 diffs were kept `ruff check`-clean and avoided repo-wide reformat churn.

---

## Sprint 3 entry point

The S2.M gate is satisfied, so Sprint 3 (Verify, measure & ship) is unblocked. The chain:

- **S3.1** verification agent (adversarial, per-claim verdicts written into `claims[]`) — consumes the baseline package's claims + the ungrounded flags.
- **S3.2** eval/scoring + two-tier compare + scorecard — scores the baseline vs `m1_s1.gold.content_package.json` on the 7-dim rubric (`evals/rubric.md`).
- **S3.3 → S3.4** first baseline scorecard → improve-and-re-measure loop (the main quality-risk task; **Course Content depth is the first lever**).
- **S3.5** light 4 assets (important_person, did_you_know, activities, resources) — extend the `AssetSpec` registry + add 4 prompts.
- **S3.6** wire the deferred feedback-driven targeted regeneration.
