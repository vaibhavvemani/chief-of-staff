# Examples

This folder stores committed generated snapshots and historical phase artifacts
that are useful for review but should not live in runtime output folders.

## Contents

- `acceptance/coffee-acceptance/` - deterministic Sprint 4 acceptance snapshot:
  - `course_artifacts/` contains the JSON pipeline artifacts.
  - `rendered_course/` contains the rendered Markdown course folder.
- `phase1/domain/` - legacy hand-authored Phase 1 domain model.
- `phase1/generated_assets/` - legacy single-asset generation outputs.

Fresh runs still write to the runtime folders:

- `courses/<course_id>/`
- `rendered_courses/<course_id>/`
- `outputs/`

