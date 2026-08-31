# Course Builder — Backend Architecture Assessment

> **Date:** 2026-08-06
> **Purpose:** An independent read of the backend as it actually stands, written
> before any optimization or frontend redesign work. It records what the
> architecture gets right (and must be preserved), what should be refactored, and
> what is a cost/observability opportunity rather than a structural one.
> This is an assessment, not a plan. Nothing here is committed work.

---

## 1. Verified current state

Everything checked on 2026-08-06 from a clean `main` at `1f08b74`:

| Check | Result |
| --- | --- |
| `python -m pytest -q` (in `.venv`) | **470 passed**, 7.1s |
| `ruff check .` | **All checks passed** |
| `cd frontend && npm test` | **92 passed** (10 files), 2.8s |
| Milestone status | NC-10 → NC-110 independently checkpointed; **NC-120 unstarted** |

**Environment gotcha worth recording:** the system `python3` (Homebrew 3.14) has no
`fastapi` installed, so a bare `python3 -m pytest` fails collection on 14 API test
modules with `ModuleNotFoundError: No module named 'fastapi'`. This is not a code
defect. Use `.venv/bin/python -m pytest`. `AGENTS.md` documents `python3 -m pytest -q`
and should be corrected to name the venv.

### Size

| Area | Lines |
| --- | --- |
| Python source (excl. tests) | ~26,500 |
| Python tests | ~16,800 (46 files) |
| Frontend `src/` | ~15,000 (incl. 2,554 CSS) |

The test-to-source ratio is **0.63 : 1**. Tests do *not* outnumber source. That is a
normal-to-healthy ratio for a system with this many cross-artifact invariants — the
volume is not the problem (see §4 for what actually is).

---

## 2. What the architecture gets right — preserve these

These are load-bearing decisions. Refactoring must not weaken them.

### 2.1 One execution path, two front doors

The most important structural property in the repo, and it is correct:

```
api/services/pipeline_catalog.PipelineCatalog.pipeline_steps()
    -> run.build_sprint4_acceptance_pipeline()   (deterministic)
    -> run.build_sprint3_pipeline()              (live)
    -> list[orchestrator.Step]
```

The browser does **not** reimplement the pipeline. `StageRunner` executes the same
`Step(name, consumes, produces, run)` objects the CLI executes; it just runs the
slice belonging to one product stage instead of the whole list. There is no drift
risk between `run.py --acceptance-demo` and clicking "Run" in Studio, because there
is only one definition of what a stage does.

Any refactor that introduces a second, API-specific step list would be a serious
regression. Do not do it.

### 2.2 Explicit deterministic/live registry with no fallback

`implementation_registry.py` is a genuinely good piece of design for an LLM system:

- Every step name must have a registered callable in **both** modes. The constructor
  computes `missing` and `extra` against `REQUIRED_STEP_NAMES` and raises — so you
  cannot half-add a live stage.
- `assert_mode_ready()` raises `ProviderNotReady` for judgment-heavy stages when
  credentials are absent, rather than silently degrading to deterministic output.
- Live mode deliberately keeps `source_selection`, `render_course_folder`, and
  `run_summary` deterministic. Those are typed decisions and calculations, not
  judgment — correctly excluded from the model.

The no-fallback property is what makes the evidence trustworthy: a green live run
cannot secretly be a deterministic run.

### 2.3 Bounded, audited model calls

`llm.py` centralizes everything that matters for cost and trust:

- `LiveCallContext` enforces a per-stage ceiling on **both** call count and input
  characters (`StageRunner.LIVE_CALL_LIMITS`), raising `LiveCallLimitExceeded`
  rather than running up a bill.
- Structured output is validated against the local schema validator on the fresh
  path **and on the cache-hit path**. Revalidating cached results is a subtle,
  correct touch — a schema change invalidates stale cached responses instead of
  silently feeding them downstream.
- `_raise_on_bad_stop()` turns truncation/refusal into a loud `LLMError` instead of
  a short artifact that passes shape checks.
- Every call is logged to `logs/llm_calls.jsonl` with token counts, latency,
  `pricing_as_of`, and an estimated cost — and `_estimate_cost_usd` returns `None`
  for an unknown model rather than applying the wrong tier.

### 2.4 Clean service decomposition

14 services under `api/services/`, each single-purpose, with an import graph that is
a **DAG — no cycles, no god object**. Helper function names are globally unique
across the codebase (no `_normalize_x` copy-pasted into four modules), which means
the previous agent was disciplined about extraction rather than duplication.

`orchestrator.py` stays a genuinely opaque engine at 285 lines: it owns the artifact
envelope and nothing about artifact bodies. That invariant has held.

---

## 3. Refactoring candidates — ranked

### R1. Split `course_model_operations.py` (2,568 lines / 94 KB) — **highest value**

One module currently does five separable jobs:

| Concern | Approx. span |
| --- | --- |
| Allocation normalization / carry-forward | 156–395 |
| Candidate validation | 395–454 |
| The operation reducer + `_apply_operation` | 454–836 |
| Semantic issue detection | 990–1483 (~490 lines) |
| Source authority checks | 1483–1731 |
| Reference / cycle integrity | 2348–2410 |

This is the riskiest file in the repo to touch and the one most likely to be touched,
since it is the Course Model reducer. Proposal: convert to a `course_model/` package
(`normalize.py`, `reduce.py`, `semantics.py`, `authority.py`, `refs.py`) and
re-export the existing public names from `__init__.py`. **Zero call-site churn**,
the 1,608-line test file keeps passing unchanged, and future edits touch a 400-line
file instead of a 2,568-line one.

### R2. Make schema enforcement symmetric — **highest correctness value**

Today there are two disconnected schema systems and neither covers everything.

**System A — `schemas/*.json` (9 files).** Only **3** are loaded by production code
(`course_model`, `course_outcomes`, `research_dossier`, all via
`course_model_operations`). `blueprint`, `brief`, `subject_request`, and
`content_package` schemas exist but are exercised **only by tests**. And five
artifact types that get written to disk have **no schema at all**:
`lesson_plan`, `run_summary`, `render_manifest`, `content_progress`,
`approved_source_registry`.

**System B — hand-written inline schemas in `agents/live_stages.py`** (~450 lines:
`_brief_schema`, `_outcomes_schema`, `_blueprint_schema`, `_course_model_update_schema`,
`_lesson_mode_schema`, `_lesson_sequence_schema`) that constrain the model's
structured output.

Two observations, and they pull in different directions:

- The **overlap is real duplication.** `_brief_schema`'s `updates` object enumerates
  the same fields and enums as `schemas/brief.v0.2.schema.json`. Adding a Brief field
  means editing both, and nothing fails if you forget.
- The **divergence is intentional and correct.** The live schemas describe *proposal*
  shapes (target IDs, bounded `maxItems`, tight `maxLength`) — deliberately narrower
  than the artifact schema. That narrowness is a cost and quality control, not an
  oversight. Do not collapse them into one schema.

Recommendation: keep both layers but give each one job. Enforce artifact schemas at a
single write-time choke point (`ArtifactRepository.save` / `orchestrator.save_artifact`),
covering all 13 artifact types; and derive the *field/enum* vocabulary of the live
proposal schemas from the artifact schemas so the two cannot drift, while keeping the
bounds hand-authored.

### R3. Break up `api/main.py` (1,187 lines)

Every route is a closure inside `create_app`. It works, and it is how the dependency
wiring got done, but no route can be read or tested in isolation and the file only
grows. Since `app.state` already holds every service, moving to `APIRouter` modules
per domain (`courses`, `stages`, `decisions`, `repairs`, `jobs`, `outputs`) with
`Depends` resolving from `app.state` is mechanical and low-risk.

Note `create_app` also contains an ~25-line inline recovery loop for interrupted
content repairs; that belongs in `SourceRepairService`.

### R4. Small cleanups (each < 30 minutes)

- **Leaky private import.** `content_repair_service.py` and `source_repair_service.py`
  both `from api.services.local_job_runner import _safe_error_message`. A redaction
  helper used by three modules should be public — move to `api/services/redaction.py`.
- **Dead defensive branch.** `StageRunner.run` computes
  `supports_progress = "progress_callback" in signature(self.catalog.steps_for_stage).parameters`
  — introspecting a collaborator it imports directly and controls. Delete the branch.
- **No config module.** Policy constants are scattered: `DEFAULT_MODEL` and
  `_STREAM_THRESHOLD` in `llm.py`, `LIVE_CALL_LIMITS` in `StageRunner`,
  `MAX_SOURCE_EXCERPT_CHARS` in `source_store.py`, CORS origins in `api/main.py`.
  These are cost/policy knobs that change together when the model tier changes.
  A single `config.py` makes the cost posture reviewable in one place.

---

## 4. Tests — the issue is organization, not volume

46 test files, 470 tests, 7.1 seconds. The suite is fast and it passes. Volume is
fine (§1). Two real problems:

1. **Named by work package, not by subject.** `test_nc100_observability.py`,
   `test_sprint4_acceptance_stabilization.py`, `test_sprint3_whole_course_production.py`,
   `test_next_cycle_acceptance_profile.py` are named after the *sprint that created
   them*. When you change `stage_runner.py` you cannot tell which files cover it, so
   the safe move is always "run everything" — which works now at 7s, but the naming
   also means nobody can find the right place to add a test. Regrouping by subject is
   cheap and mostly `git mv` plus renames.
2. **Five overlapping `test_frontend_integration_*.py` modules** testing the API from
   the frontend's perspective, alongside `test_api_*.py` modules testing the same
   endpoints. Worth a consolidation pass.

Neither is urgent. Do them opportunistically, not as a project.

---

## 5. Cost & observability — quantified, and the biggest single lever

From `logs/llm_calls.jsonl` (255 records, 195 real calls, 60 local-cache hits):

| Metric | Value |
| --- | --- |
| Input tokens | **3,222,646** |
| Output tokens | 389,284 |
| Anthropic cache-read tokens | **0** |
| Anthropic cache-write tokens | **0** |
| Estimated cost | $24.75 (all `claude-opus-4-8`) |

Three findings:

**5.1 Input is ~8× output, and server-side prompt caching is not used at all.**
`grep cache_control` returns nothing. The `.llm_cache/` directory is a *local disk
cache keyed on an exact prompt hash* — it only helps on a byte-identical replay, which
is why it hit 60/255 times. It does nothing for the real pattern: 54 content calls
that share a large, stable prefix (system prompt, asset spec, course model slice) and
vary only in the subtopic tail. Anthropic prompt caching bills a cached prefix at
**0.1×** the input rate on read (the pricing table in `llm.py` already knows this — it
just never gets a chance to apply it). At ~16.5k input tokens per call with a
substantial shared prefix, this is the largest available cost reduction and it
requires no change to output quality. Worth a careful look before any other
optimization.

**5.2 Everything runs on Opus.** All 255 calls are `claude-opus-4-8`. Some stages are
plausibly Sonnet- or Haiku-shaped (research query shaping, lesson sequencing) — but
this must be decided per stage against the eval harness (`evals/compare.py`), not
assumed. Also note `DEFAULT_MODEL` predates the Claude 5 family; a model-tier review
is due on its own.

**5.3 66% of live spend is unattributed.** 128 of 195 calls logged no `stage` —
2.51M input tokens, ~$18.78, in the `?` bucket. Stage attribution only happens inside
the API's `LiveCallContext`, so CLI runs record no stage. That undercuts the whole
point of the cost log. Setting a `LiveCallContext` (or at least a `call_role`) on the
CLI path is a small change with a large payoff for the next optimization pass.

---

## 6. Bottom line

The backend does **not** need an architectural redesign. The core decisions — one
step contract shared by CLI and browser, an explicit no-fallback implementation
registry, bounded and audited model calls, a service DAG — are sound and should be
defended, not rewritten.

What it needs is **consolidation**, in this order:

1. Split `course_model_operations.py` (R1) — reduces the risk of every future change.
2. Close the schema enforcement gap (R2) — the only finding with a correctness edge.
3. Investigate Anthropic prompt caching + fix stage attribution (§5.1, §5.3) — the
   largest cost lever, independent of the refactors.
4. Break up `api/main.py` (R3) and the small cleanups (R4) — quality of life.

Separately, the remaining *program* work is NC-120: the internal pilot with a real
nontechnical course director, which by its own definition must not be simulated by an
agent. Refactoring does not advance it, and destabilizing the backend would set it
back — so refactors should land behind the existing green suite, one at a time.

---

## 7. Frontend note (for the later redesign pass)

Recorded here only so it is not lost; a proper frontend assessment is separate work.

- `styles/refinement.css` (1,890 lines) was added in `1f08b74` as an override layer
  loaded *after* `global.css` (664 lines), redeclaring `:root` and the full token set.
  Two stylesheets where the second exists to defeat the first is a design-debt
  pattern; the redesign should collapse them into one token system rather than adding
  a third layer.
- `api/client.ts` (2,218 lines) mixes transport, error decoding, and ~700 lines of
  hand-written defensive normalizers (`normalizeCourseModel`, `normalizeStatus`, …)
  that restate `types.ts`. Worth generating from the API's OpenAPI schema — FastAPI
  already publishes it.
- `WorkspacePage.tsx` at 1,447 lines is the frontend's `main.py`.
