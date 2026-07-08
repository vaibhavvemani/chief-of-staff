# Course Builder Prototype Operator Guide

## Purpose

This guide covers the final four-week prototype path:

`sparse subject request -> brief -> outcomes -> research/source selection -> Course Model -> Blueprint -> selected content -> Lesson Plan -> Markdown course folder -> run summary`

The prototype is terminal-operated. The interaction contracts are structured so a later UI can render the same checkpoints without changing the underlying pipeline.

## Setup

From `course_builder_system/`:

```bash
python3 -m pytest -q
ruff check .
```

Live LLM-backed content generation requires `ANTHROPIC_API_KEY` in the environment or `.env`. The local acceptance path below does not require an API key.

## Local Acceptance Run

Use this for repeatable prototype acceptance:

```bash
python3 run.py --acceptance-demo --course-id coffee-acceptance --auto-approve
python3 integrity.py coffee-acceptance
```

Expected primary outputs:

- `courses/coffee-acceptance/`
- `rendered_courses/coffee-acceptance/README.md`
- `rendered_courses/coffee-acceptance/course_overview.md`
- `rendered_courses/coffee-acceptance/source_index.md`
- `rendered_courses/coffee-acceptance/lesson_plan.md`
- `rendered_courses/coffee-acceptance/modules/`

Those runtime folders are ignored by git. The committed deterministic acceptance
snapshot lives under `examples/acceptance/coffee-acceptance/`.

## Interactive Operation

Run without `--auto-approve` to review each checkpoint:

```bash
python3 run.py --acceptance-demo --course-id coffee-acceptance
```

At each checkpoint:

- `approve` or `a` accepts the artifact.
- `changes` or `c` reruns only that step with the supplied feedback.
- `quit` or `q` stops the run. Rerun the same command to resume from approved checkpoints.

Targeted content revision syntax:

```text
<asset id or asset type>: <feedback>
```

Examples:

```text
m1_s1_summary: tighten the summary and remove repetition
summary: make the recap more action-oriented
verifier: resolve unsupported claims
{"subtopic_id":"m1_s2","assets":["m1_s2_summary"],"feedback":"make this shorter"}
```

## Resume Behavior

Rerunning the same command is safe. Approved artifacts whose inputs did not change are skipped. Draft, rejected, missing, stale, or revised downstream steps rerun.

If the run stops during a checkpoint, the last produced artifact may remain as `draft`; the next run regenerates that step and continues.

## Review Checklist

Before accepting a prototype run:

- `integrity.py <course_id>` returns OK.
- `run_summary.json` has `operator_status: complete`.
- `approved_source_registry.json` lists only approved sources.
- `course_model.json` source registry contains no rejected or competitor-only sources.
- `blueprint.json` selects only intended assets and keeps `course_content` as each subtopic anchor.
- `content_package.json` contains exactly the selected Blueprint assets.
- `lesson_plan.json` covers generated subtopics exactly once and in order.
- The rendered Markdown folder has no stale files after rerun.

## Scope Boundary

The local acceptance run uses deterministic content and verification to prove orchestration, routing, recovery, rendering, and integrity. Full-quality learner prose still requires the live LLM-backed generation path and human review.
