# Coffee Acceptance Snapshot

This is the committed deterministic acceptance-course snapshot moved out of the
runtime folders during repository cleanup.

- `course_artifacts/` contains the generated JSON artifacts.
- `rendered_course/` contains the Markdown course deliverables.

To regenerate the runtime version:

```bash
python3 run.py --acceptance-demo --course-id coffee-acceptance --auto-approve
python3 integrity.py coffee-acceptance
```

That command writes fresh ignored outputs under:

- `courses/coffee-acceptance/`
- `rendered_courses/coffee-acceptance/`

