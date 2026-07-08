# Course Builder Prototype

Course Builder is a terminal-operated prototype that turns a sparse subject
request into structured course artifacts and a rendered Markdown course folder.

The current prototype flow is:

`subject_request -> brief -> course_outcomes -> research_dossier -> source approval -> course_model -> blueprint -> student_content -> verification -> lesson_plan -> rendered course folder -> run_summary`

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

## Directory Map

- `agents/` - domain agents for intake, research, Course Model, Blueprint, content, verification, revision, and Lesson Plan.
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

