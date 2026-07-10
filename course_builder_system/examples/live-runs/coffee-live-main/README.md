# Coffee Live Run Snapshot

This is the recovered full live LLM-backed course run completed on 2026-07-06.
It is the substantive live output, not the small deterministic acceptance fixture.

## Contents

- `course_artifacts/` contains the complete pipeline state, approved source
  captures, Blueprint, 18-asset Content Package, verification results, Lesson
  Plan, render manifest, and run summary.
- `rendered_course/` contains the learner-facing Markdown course, with one file
  per selected asset.

Start review at `rendered_course/README.md`. For the complete generated payload
and claim-level verification, inspect `course_artifacts/content_package.json`.

## Run Evidence

- 37 Claude calls
- 2 approved live sources
- 18 Blueprint-selected assets
- 18 generated assets
- 18 rendered Markdown asset files
- approximately 9,200 words of generated learner content
- approximately 14,600 rendered words including claims and verification detail

The selected Blueprint asset IDs and generated Content Package asset IDs match
exactly.

## Quality Status

This snapshot demonstrates that the live pipeline completed, but it is not
learner-ready without revision. Verification recorded:

- supported: 109
- partial: 14
- unsupported: 5
- ungrounded: 1
- unattributed: 3

The archived `run_summary.json` says `operator_status: complete` because it was
produced immediately before the verifier attention-gate fix. Under the current
policy, these findings mean `requires_attention`. The original status is kept
in the snapshot for provenance.

## Provenance

The run was originally isolated under a macOS temporary artifact root. It was
recovered and promoted here on 2026-07-10 so the generated course can be
reviewed durably. Embedded source and render paths were updated to this
repository location; generated course content and verification findings were
not rewritten.
