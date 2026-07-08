# Sprint 4 Demonstration Script

## Primary Acceptance

1. Start from a clean branch with Sprint 3 merged.
2. Run the local acceptance path:

   ```bash
   python3 run.py --acceptance-demo --course-id coffee-acceptance --auto-approve
   ```

3. Confirm integrity:

   ```bash
   python3 integrity.py coffee-acceptance
   ```

4. Open the rendered folder:

   ```text
   rendered_courses/coffee-acceptance/

   The committed deterministic snapshot is stored under:

   examples/acceptance/coffee-acceptance/
   ```

5. Review:

   - `README.md`
   - `course_overview.md`
   - `source_index.md`
   - `lesson_plan.md`
   - `modules/`

## Resume Drill

1. Start an interactive run:

   ```bash
   python3 run.py --acceptance-demo --course-id coffee-acceptance
   ```

2. Approve early checkpoints.
3. Enter `quit` at a later checkpoint.
4. Rerun the same command.
5. Confirm approved checkpoints are skipped and the run resumes at the incomplete step.

## Targeted Revision Drill

At the `student_content` checkpoint, choose `changes` and enter feedback such as:

```text
m1_s1_summary: tighten the summary and make the learner action clearer
```

Expected behavior:

- Only the targeted asset is regenerated.
- Existing approved upstream artifacts remain unchanged.
- The final integrity check remains green.

## Negative Gate

Run:

```bash
python3 -m pytest tests/test_sprint4_acceptance_stabilization.py -q
```

This proves:

- rejected sources cannot enter the Course Model;
- competitor-only sources cannot masquerade as factual sources;
- invalid source IDs fail schema validation;
- selected assets without routed evidence are blocked;
- unselected Blueprint assets cannot be generated directly;
- a second unrelated topic uses the same contracts.
