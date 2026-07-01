# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

The Course Builder turns a subject brief into a complete course folder by running an ordered pipeline of steps, pausing for human approval after each. See `documents/context_docs/` for the full spec and handoff (Master Context, Phase 1 Plan, Sprint Sheet, Source Files Reference).

## Commands

Run from this directory (`course_builder_system/`):

- `python run.py` — run the full pipeline for `frm-demo`. Pauses after each step: `a`pprove / `c`hanges (re-runs only that step with feedback) / `q`uit.
- `python3 integrity.py [course_id]` — check Course Model and downstream references. Exits 0 if clean, 1 if any reference dangles. Defaults to `frm-demo`.
- `python3 -m pytest -q` — run contract, context-slicing, generation, verification, revision, and pipeline tests.
- `ruff check .` / `ruff format .` — lint and format (config in `ruff.toml`).

The local plumbing and contract tests have no service dependency. `anthropic` is needed for live generation and verification calls.

## Architecture invariants — do not break these

- **The orchestrator is an opaque engine.** `orchestrator.py` only ever touches the fixed metadata *envelope* built by `make_artifact` (course_id, artifact_type, status, revision, inputs, …) — never the artifact `body`. Changing an artifact's *body* shape must NOT require editing `orchestrator.py`; schema/content work happens in `steps.py`. The *envelope* may still gain orchestrator-owned fields — e.g. `make_artifact`'s optional `schema_version` override, which lets one artifact pin a newer schema (Content Package v0.2) while the rest stay v0.1. That is an envelope-contract change, not a body change.
- **The pipeline is data.** Steps are an ordered list of `Step(name, consumes, produces, run)` in `run.py:build_pipeline()`. Intake/outcomes/research/structure are fixture-backed in Phase 1; Student Content and verification make real LLM calls outside tests.
- **The Course Model is the structural and compact knowledge source of truth.** Blueprint, Content Package, and Lesson Plan reference its IDs. Full research/source bodies stay separate. `integrity.py` enforces this; run it after changing a contract or step.
- **Generation context is sliced.** A call receives the current Course Model node, its Blueprint depth/asset plan, and only that asset's routed subset of human-approved source excerpts. Do not dump the full model or corpus into prompts.
- **Reusable prompts are domain-neutral.** Course-specific coverage belongs in Course Outcomes, Course Model, Blueprint, and sources—not in prompt prose.
- **Steps don't own lifecycle fields.** A step's `run(inputs, feedback)` returns `{artifact_type: artifact}` and sets only identity + `body` + `inputs`. The orchestrator owns `status`, `revision`, `revision_note`, `updated_at`.

## Gotchas

- **Resume skips compatible approved steps.** `run_pipeline` skips an approved output only when its recorded inputs match the current step contract. Old TOC/Domain Model runs therefore do not silently bypass the Course Model migration.
- **LLM calls use the Anthropic API.** SDK `anthropic`, default model `claude-opus-4-8`; the client reads `ANTHROPIC_API_KEY` from the environment / `.env` (gitignored — fill it in locally). See `learning_scripts/` for the request/response, grounding, and tool-use patterns.

## Repo etiquette

- Work on a feature branch — don't commit directly to `main`. The repo owner merges to `main` (no PR required).
