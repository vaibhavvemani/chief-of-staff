# Runtime Course Artifacts

Pipeline runs write checkpoint artifacts here:

`courses/<course_id>/<artifact_type>.json`

Examples include `brief.json`, `course_model.json`, `blueprint.json`,
`content_package.json`, `lesson_plan.json`, and `run_summary.json`.

Most course folders are generated runtime state and are ignored by git. The
exception is `courses/frm-demo/`, which remains tracked as a legacy FRM fixture
because tests and backward-compatible loading paths still use it.

The committed deterministic coffee acceptance snapshot lives under:

`examples/acceptance/coffee-acceptance/`

