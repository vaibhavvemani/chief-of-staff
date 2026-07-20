# AGENTS.md

This file gives Codex and other coding agents the operating context for this
repository. It replaces the older Claude-specific guidance as the canonical
agent instruction file.

## Project Status

The Course Builder four-week prototype is complete as of 2026-07-06. The first
local Course Builder Studio frontend and FastAPI adapter are implemented as of
2026-07-14. The next milestone-gated development cycle is planned as of
2026-07-15. Its NC-10 lifecycle/command foundation and NC-20 Guided Brief Intake
package have passed independent review. NC-301 and NC-302 have now also passed their
independent NC-30 checkpoint review. NC-303 remains deferred to NC-90 behind NC-902,
and NC-401 through NC-403 passed independent NC-40 backend checkpoint review on
2026-07-20 after corrective hardening of stable IDs, ordered references, source
authority, shared schema validation, and rollback cleanup. NC-40 is not complete.
NC-404 through NC-406 and all later packages remain unstarted; Course Model browser
editing remains disabled.

The system turns a sparse subject request into a rendered course folder through:

`subject_request -> brief -> course_outcomes -> research_dossier -> source approval -> course_model -> blueprint -> selected student_content -> verification -> lesson_plan -> rendered Markdown folder -> run_summary`

Treat the prototype as a successful engineering prototype, not production-ready
courseware automation. A full live run completed, but first-pass live content
can still require source repair and targeted revision before it is learner-ready.

Primary context docs:

- `documents/context_docs/Course_Builder_Master_Context.md` - current north star and status.
- `documents/context_docs/Course_Builder_Four_Week_Prototype_Completion_Handoff.md` - delivered prototype, validation evidence, known gaps, and recommended next work.
- `documents/context_docs/Course_Builder_Frontend_Implementation_Handoff.md` - implemented browser product, API adapter, stage behavior, state flow, extension rules, and known limitations.
- `documents/context_docs/Course_Builder_Next_Development_Cycle_Plan.md` - active next-cycle product outcome, milestones, risks, definition of done, and deferrals.
- `documents/context_docs/Course_Builder_Next_Cycle_Technical_Contract_Plan.md` - target lifecycle, invalidation, typed command, repair, execution, and observability contracts.
- `documents/context_docs/Course_Builder_Next_Cycle_Implementation_Backlog.md` - task-sized work packages, dependencies, priorities, ownership split, and exit gates.
- `documents/context_docs/Course_Builder_Next_Cycle_Acceptance_and_Pilot_Plan.md` - deterministic, recovery, negative, live-agent, and internal operator acceptance protocol.
- `documents/context_docs/Course_Builder_Frontend_Product_and_Implementation_Plan.md` - original frontend product and architecture plan; use the implementation handoff for current behavior.
- `documents/context_docs/Course_Builder_Four_Week_Prototype_Plan.md` - intended prototype scope and definition of done.
- `documents/context_docs/Course_Builder_Four_Week_Sprint_Plan.md` - completed sprint plan and acceptance framing.
- `documents/Prototype_Operator_Guide.md` - how to run and review the prototype.

The active next-cycle program makes the browser dependable for a nontechnical
internal course director and then proves the same workflow with live agent-backed
stages. NC-002, NC-004, NC-005, and NC-101 through NC-109 are implemented and
independently verified. NC-201 through NC-207 are also independently verified. NC-30
Outcomes reducer validation and browser editing are independently verified through
NC-301 and NC-302. NC-303 remains deferred to NC-90 behind NC-902. NC-401 through
NC-403 are independently verified; this does not complete NC-40. NC-404, NC-405,
NC-406, and all later packages remain unstarted, and Course Model editing stays
unavailable in the browser. The next safe implementation action is NC-404. NC-405
remains dependent on NC-404; do not skip ahead to source repair or live-agent parity.
Source repair plus verifier-driven targeted revision remains the central trust milestone
after the intervening stage contracts.

## Commands

Run commands from this directory:

```bash
cd /Users/vaibhavvemani/Developer/chief_of_staff/course_builder_system
```

Useful commands:

- `python3 run.py --help` - show available prototype pipeline modes.
- `python3 run.py --acceptance-demo --course-id coffee-acceptance --auto-approve` - deterministic local end-to-end acceptance run.
- `python3 integrity.py coffee-acceptance` - verify Course Model and downstream references for the acceptance course.
- `python3 run.py --sprint3-demo --live-research --subject "Coffee making" --course-id coffee-live` - live LLM-backed end-to-end path with live research, generation, verification, lesson plan, render, and summary.
- `python3 -m pytest -q` - run the full test suite.
- `ruff check .` - lint the repo.
- `ruff format .` - format Python files when appropriate.
- `cd frontend && npm run build` - type-check and build Course Builder Studio.
- `cd frontend && npm test` - run frontend unit tests.

Local deterministic tests and acceptance do not require external services.
Live generation and verification use Anthropic via `anthropic`; set
`ANTHROPIC_API_KEY` in the environment or `.env`.

## Architecture Invariants

- The orchestrator is an opaque engine. `orchestrator.py` only owns the fixed artifact envelope: `course_id`, `artifact_type`, `status`, `revision`, `revision_note`, `inputs`, `updated_at`, and `body`. Artifact body-shape changes belong in steps, agents, schemas, and integrity checks, not in the orchestrator.
- The pipeline is data. Steps are ordered `Step(name, consumes, produces, run)` objects in `run.py`. Keep new behavior behind step functions or injected callables instead of hardcoding stage logic into the runner.
- The Course Model is the compact structural source of truth. Blueprint, Content Package, Lesson Plan, and rendered output reference its IDs. Full research/source bodies stay outside the Course Model.
- The Blueprint controls generation. Asset selection is per subtopic, and generated content must match selected Blueprint assets exactly.
- Generation context is sliced. Each LLM call should receive the current subtopic, the target asset plan, relevant depth/coverage requirements, and only routed approved source excerpts. Do not dump the full model or source corpus into prompts.
- Reusable prompts are domain-neutral. Course-specific coverage belongs in Course Outcomes, Course Model, Blueprint, and sources, not in prompt prose.
- Steps do not own lifecycle fields. A step returns artifact envelopes with identity, `body`, and `inputs`; the orchestrator sets status, revision, revision note, and timestamps.
- Source decisions are deterministic. Rejected, proposed, unavailable, competitor-only, or contentless sources must not leak into Course Model approved mappings or generation context.
- Verification is an attention gate. Unsupported, ungrounded, or unattributed findings should make `run_summary.operator_status` require attention.
- Markdown rendering is the prototype output format. Native DOCX/PPTX styling and SCORM wiring are later work unless the user explicitly asks for them.

## Operational Gotchas

- Resume skips approved outputs only when their recorded inputs are current and match the step contract. Rerunning the same command is normally safe.
- Content generation is per asset, not one monolithic model call. For each subtopic, `course_content` is generated first; dependent assets then use it for coherence.
- The canonical generated content artifact is `courses/<course_id>/content_package.json`. Learner-facing inspection output is rendered as separate Markdown files under `rendered_courses/<course_id>/modules/`.
- Committed generated snapshots live under `examples/`; runtime-generated course folders should stay out of git unless they are intentionally promoted to fixtures.
- The substantive 2026-07-06 live coffee run is archived under `examples/live-runs/coffee-live-main/`; do not confuse it with the compact deterministic `examples/acceptance/coffee-acceptance/` fixture.
- `--auto-approve` is for deterministic acceptance and unattended plumbing checks. It is not a quality workflow for live courseware.
- Live runs can make many Claude calls. Check `logs/llm_calls.jsonl` for token and estimated cost records. Cache hits are stored under `.llm_cache/`.
- Source excerpts are intentionally bounded before generation and verification. Do not remove that guardrail.
- If a live run completes with verifier blockers, the pipeline worked mechanically but the course is not learner-ready.

## Repo Etiquette

- Work on a feature branch. Do not commit directly to `main` unless the user explicitly asks.
- Branch names should be short and descriptive. Do not include `codex` or sprint names in new branch names.
- The git repository root is the parent `chief_of_staff` repo, but most project commands should run from `course_builder_system/`.
- Use `rg`/`rg --files` for search.
- Use `apply_patch` for manual file edits.
- Respect dirty worktrees. Never revert changes you did not make unless the user explicitly asks.
- Keep changes scoped to the task and aligned with existing contracts.
- Use subagents only when the work is meaningfully parallel or specialized. The main agent remains responsible for integration and verification.
- Run tests proportionate to the change. For docs-only edits, `git diff --check` is usually enough; for code changes, prefer `ruff check .` plus focused tests or the full suite depending on risk.

## Collaboration Preferences

- Communicate directly and pragmatically. Keep updates factual and concise.
- The user is comfortable with Python; skip basic Python explanations.
- The user is still calibrating on LLM API patterns, grounding, tool use, caching, and cost controls. Explain those design choices and tradeoffs more deeply when they matter.
- For non-trivial, risky, or scope-changing work, state a short plan before editing. For straightforward implementation, proceed and verify.
- Ask for review when human judgment is materially needed. Otherwise self-verify and move forward.
