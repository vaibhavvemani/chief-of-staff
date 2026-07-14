# Course Builder Prototype

Course Builder is a terminal-operated prototype that turns a sparse subject
request into structured course artifacts and a rendered Markdown course folder.

It now also includes Course Builder Studio: a desktop-first, artifact-oriented
web workspace for running the pipeline, reviewing agent outputs, making source
and content decisions, and inspecting the final Markdown package.

The current prototype flow is:

`subject_request -> brief -> course_outcomes -> research_dossier -> source approval -> course_model -> blueprint -> student_content -> verification -> lesson_plan -> rendered course folder -> run_summary`

For a complete code-level explanation of the architecture, artifact contracts,
stage behavior, prompts, LLM calls, API, frontend, validation, and current
limitations, read
[`documents/Course_Builder_Complete_Technical_Guide.md`](documents/Course_Builder_Complete_Technical_Guide.md).

For the canonical Course Builder Studio product and implementation handoff, read
[`documents/context_docs/Course_Builder_Frontend_Implementation_Handoff.md`](documents/context_docs/Course_Builder_Frontend_Implementation_Handoff.md).

## Run

Deterministic local acceptance:

```bash
python3 run.py --acceptance-demo --course-id coffee-acceptance --auto-approve
python3 integrity.py coffee-acceptance
```

Live LLM-backed path:

```bash
python3 run.py --sprint3-demo --live-research --subject "Coffee making" --course-id coffee-live
python3 integrity.py coffee-live
```

Live generation requires `ANTHROPIC_API_KEY` in the environment or `.env`.

## Course Builder Studio

Install the Python and frontend dependencies once:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
cd frontend
npm install
```

Run the API from the project root:

```bash
.venv/bin/uvicorn api.main:app --reload
```

In a second terminal, run the Vite development server:

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to the local FastAPI server.
The dashboard exposes runtime courses plus the committed acceptance and live-run
snapshots; committed snapshots are deliberately read-only. New stage runs default
to Live agent mode, with deterministic mode available for repeatable local tests.
Live mode uses `ANTHROPIC_API_KEY` only on the Python
server—the browser never receives provider credentials.

For a single-process local build, run `npm run build` in `frontend/` first and
then start Uvicorn; FastAPI will serve the built studio at
`http://127.0.0.1:8000` alongside the API.

Production frontend assets and all checks can be built with:

```bash
cd frontend
npm run build
npm test
cd ..
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
```

The first web release uses one bounded in-process job runner and persisted SSE
events. Run one API worker so the per-course execution lock remains authoritative.

## Directory Map

- `agents/` - domain agents for intake, research, Course Model, Blueprint, content, verification, revision, and Lesson Plan.
- `api/` - FastAPI projection, decision commands, local job runner, and SSE transport for Course Builder Studio.
- `frontend/` - React, TypeScript, and Vite Course Builder Studio interface.
- `prompts/` - reusable domain-neutral LLM prompts.
- `schemas/` - JSON schemas for artifact contracts.
- `tests/` - regression and contract tests.
- `documents/` - operator docs, planning docs, architecture notes, and context handoffs.
- `course_models/` - curated v0.2 fixtures used by tests and legacy FRM loading.
- `courses/` - runtime checkpoint artifacts written by pipeline runs. Only `courses/frm-demo/` is kept as a legacy fixture.
- `rendered_courses/` - runtime Markdown output written by renderer runs.
- `outputs/` - ad hoc/generated single-asset CLI outputs.
- `examples/` - committed generated snapshots and legacy phase artifacts moved out of runtime folders.
- `benchmark/` - FRM manual benchmark source files and gold content package.
- `sources/` - curated source excerpts used by fixtures.
- `evals/` - evaluation helpers, rubrics, and historical score artifacts.
- `learning_scripts/` - small LLM API learning/reference scripts.

Runtime folders such as `courses/<new-id>/`, `rendered_courses/`, `outputs/`,
`logs/`, and `.llm_cache/` are intentionally ignored by git.

## Agent Instructions

Read `AGENTS.md` before non-trivial work. It captures the current prototype
status, architecture invariants, run commands, and collaboration preferences.
