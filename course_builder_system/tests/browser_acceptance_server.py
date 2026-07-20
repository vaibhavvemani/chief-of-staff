"""Production-shaped FastAPI server with isolated browser-acceptance storage."""

from __future__ import annotations

import importlib
import json
import os
import shutil
import tempfile
from atexit import register
from pathlib import Path

_acceptance_root = Path(tempfile.mkdtemp(prefix="course-builder-browser-acceptance-"))
register(shutil.rmtree, _acceptance_root, ignore_errors=True)
os.environ["COURSE_BUILDER_COURSES_ROOT"] = str(_acceptance_root / "courses")
os.environ["COURSE_BUILDER_RENDERED_ROOT"] = str(_acceptance_root / "rendered_courses")
os.environ["COURSE_BUILDER_RUNTIME_ROOT"] = str(_acceptance_root / "runtime")
os.environ["COURSE_BUILDER_INCLUDE_EXAMPLES"] = "false"

# Seed a writable, isolated copy of the complete deterministic fixture so browser
# lifecycle tests can reopen an approved mid-pipeline stage without mutating the
# committed example or replaying later work packages through the UI.
SEEDED_LIFECYCLE_COURSE_ID = "studio-course-model-reopen-fixture"
COURSE_MODEL_EDITOR_COURSE_ID = "studio-course-model-editor-fixture"
BLUEPRINT_EDITOR_COURSE_ID = "studio-blueprint-editor-fixture"
LESSON_PLAN_EDITOR_COURSE_ID = "studio-lesson-plan-editor-fixture"
_fixture_root = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "acceptance"
    / "coffee-acceptance"
    / "course_artifacts"
)
_seed_root = _acceptance_root / "courses" / SEEDED_LIFECYCLE_COURSE_ID
_seed_root.mkdir(parents=True)
for _fixture_path in _fixture_root.glob("*.json"):
    _artifact = json.loads(_fixture_path.read_text(encoding="utf-8"))
    _artifact["course_id"] = SEEDED_LIFECYCLE_COURSE_ID
    (_seed_root / _fixture_path.name).write_text(
        json.dumps(_artifact, indent=2) + "\n",
        encoding="utf-8",
    )

# A second bounded fixture stops at the approved Research checkpoint so the browser
# acceptance scenario exercises the real deterministic Course Model run before editing.
_editor_seed_root = _acceptance_root / "courses" / COURSE_MODEL_EDITOR_COURSE_ID
_editor_seed_root.mkdir(parents=True)
for _artifact_type in (
    "subject_request",
    "brief",
    "course_outcomes",
    "research_dossier",
    "approved_source_registry",
):
    _fixture_path = _fixture_root / f"{_artifact_type}.json"
    _artifact = json.loads(_fixture_path.read_text(encoding="utf-8"))
    _artifact["course_id"] = COURSE_MODEL_EDITOR_COURSE_ID
    (_editor_seed_root / _fixture_path.name).write_text(
        json.dumps(_artifact, indent=2) + "\n",
        encoding="utf-8",
    )

# A third bounded fixture stops at the approved Course Model checkpoint so A7
# exercises the real deterministic Blueprint run, typed decision, and approval.
_blueprint_seed_root = _acceptance_root / "courses" / BLUEPRINT_EDITOR_COURSE_ID
_blueprint_seed_root.mkdir(parents=True)
for _artifact_type in (
    "subject_request",
    "brief",
    "course_outcomes",
    "research_dossier",
    "approved_source_registry",
    "course_model",
):
    _fixture_path = _fixture_root / f"{_artifact_type}.json"
    _artifact = json.loads(_fixture_path.read_text(encoding="utf-8"))
    _artifact["course_id"] = BLUEPRINT_EDITOR_COURSE_ID
    (_blueprint_seed_root / _fixture_path.name).write_text(
        json.dumps(_artifact, indent=2) + "\n",
        encoding="utf-8",
    )

# A fourth bounded fixture stops at approved Student Content so A12 exercises
# the real deterministic Lesson Plan run before the typed delivery decision.
_lesson_plan_seed_root = _acceptance_root / "courses" / LESSON_PLAN_EDITOR_COURSE_ID
_lesson_plan_seed_root.mkdir(parents=True)
for _artifact_type in (
    "subject_request",
    "brief",
    "course_outcomes",
    "research_dossier",
    "approved_source_registry",
    "course_model",
    "blueprint",
    "content_package",
    "content_progress",
):
    _fixture_path = _fixture_root / f"{_artifact_type}.json"
    _artifact = json.loads(_fixture_path.read_text(encoding="utf-8"))
    _artifact["course_id"] = LESSON_PLAN_EDITOR_COURSE_ID
    (_lesson_plan_seed_root / _fixture_path.name).write_text(
        json.dumps(_artifact, indent=2) + "\n",
        encoding="utf-8",
    )


# Import only after the environment points api.main's module-level app at the
# isolated roots. This also exercises the production-shaped app entry point.
app = importlib.import_module("api.main").app
