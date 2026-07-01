# Course Model v0.2 Fixtures

These fixtures demonstrate the domain-neutral planning contracts without
replacing the legacy `courses/frm-demo/` artifacts.

- `course_outcomes` records the human-approved course-level outcomes that guide
  research and structure.
- `research_dossier` records competitor findings and every proposed, approved,
  or rejected source. It stores source metadata and content pointers, not source
  bodies.
- `course_model` combines the old TOC and Domain Model roles: ordered modules
  and subtopics plus compact context, concepts, dependencies, coverage
  requirements, and approved source IDs. Its global source registry contains
  only approved source metadata; `content_ref` resolves the body when needed.
- `blueprint` stores production decisions separately from course knowledge.
  Each subtopic has a depth budget and an asset plan whose entries can be
  proposed, selected, or rejected by the human reviewer. Each asset also gets
  an explicit `source_ids` subset drawn from the sources approved for that
  subtopic, so a case study does not receive an unrelated source pack.

Generation should build a subtopic context slice from the Course Model and
Blueprint rather than injecting either complete artifact. Load source bodies
only for the current asset's assigned source IDs. In Phase 1 each `content_ref`
points to a compact curated excerpt/notes file, not the complete original
publication; the original locator remains available for reviewer verification.
