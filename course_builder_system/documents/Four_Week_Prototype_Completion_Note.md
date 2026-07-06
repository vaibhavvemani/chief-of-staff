# Four-Week Prototype Completion Note

## Final Gate

The prototype now covers the approved vertical path:

`sparse request -> guided brief -> outcomes -> bounded research -> explicit source approval -> Course Model -> Blueprint -> selected content -> verification -> Lesson Plan -> Markdown course folder -> run summary`

## Acceptance Evidence

Implemented Sprint 4 acceptance and stabilization includes:

- local primary acceptance run through `python3 run.py --acceptance-demo`;
- deterministic generated course folder for `coffee-acceptance`;
- second-topic domain-neutral smoke for indoor herb gardening;
- resume after operator cancellation;
- targeted Student Content revision;
- deterministic renderer rerun cleanup;
- final negative tests for rejected-source, competitor-source, invalid-ID, evidence-gap, and unselected-asset leakage.

## Commands

```bash
ruff check .
python3 -m pytest -q
python3 run.py --acceptance-demo --course-id coffee-acceptance --auto-approve
python3 integrity.py coffee-acceptance
```

## Remaining Boundary

The prototype proves the product path and enforcement contracts. Production readiness still requires live-source hardening at larger scale, richer UI work, document/PPTX rendering, deployment packaging, and human quality review for specialist or high-stakes domains.
