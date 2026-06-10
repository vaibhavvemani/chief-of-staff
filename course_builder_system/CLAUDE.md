# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

The Course Builder turns a subject brief into a complete course folder by running an ordered pipeline of steps, pausing for human approval after each. See `documents/context_docs/` for the full spec and handoff (Master Context, Phase 1 Plan, Sprint Sheet, Source Files Reference).

## Commands

Run from this directory (`course_builder_system/`):

- `python run.py` — run the full pipeline for `frm-demo`. Pauses after each step: `a`pprove / `c`hanges (re-runs only that step with feedback) / `q`uit.
- `python integrity.py [course_id]` — check that every cross-artifact reference resolves to a TOC id. Exits 0 if clean, 1 if any reference dangles. Defaults to `frm-demo`.
- `ruff check .` / `ruff format .` — lint and format (config in `ruff.toml`).

The skeleton has **no dependencies**. `anthropic` is only needed once steps make real LLM calls (Phase 1+) and for `learning_scripts/`.

## Architecture invariants — do not break these

- **The orchestrator is an opaque engine.** `orchestrator.py` only ever touches the fixed metadata *envelope* built by `make_artifact` (course_id, artifact_type, status, revision, inputs, …) — never the artifact `body`. Changing an artifact's shape must NOT require editing `orchestrator.py`. Schema/content work happens in `steps.py`.
- **The pipeline is data.** Steps are an ordered list of `Step(name, consumes, produces, run)` in `run.py:build_pipeline()`. The current `run=` functions in `steps.py` are hardcoded stubs (no LLM calls); Phase 1+ replaces each stub with a real agent and nothing else in the pipeline changes. Stub bodies are the locked v0.1 shapes copied from `documents/artifact_samples/*.frm.example.json` — keep them mutually consistent.
- **The TOC is the single source of truth for structure.** Every other artifact (blueprint, content_package, lesson_plan) references TOC ids and never re-encodes the module/subtopic tree. `integrity.py` enforces this; run it after changing any step.
- **Steps don't own lifecycle fields.** A step's `run(inputs, feedback)` returns `{artifact_type: artifact}` and sets only identity + `body` + `inputs`. The orchestrator owns `status`, `revision`, `revision_note`, `updated_at`.

## Gotchas

- **Resume skips approved steps.** `run_pipeline` skips any step whose outputs are already `approved` on disk under `courses/<course_id>/`. After editing a step, delete that step's `courses/<course_id>/<artifact_type>.json` file(s) and re-run, or the change won't take effect.
- **LLM calls use the Anthropic API.** SDK `anthropic`, default model `claude-opus-4-8`; the client reads `ANTHROPIC_API_KEY` from the environment / `.env` (gitignored — fill it in locally). See `learning_scripts/` for the request/response, grounding, and tool-use patterns.

## Repo etiquette

- Work on a feature branch — don't commit directly to `main`. The repo owner merges to `main` (no PR required).
