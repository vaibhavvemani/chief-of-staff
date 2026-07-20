"""Production-shaped FastAPI server with isolated browser-acceptance storage."""

from __future__ import annotations

import importlib
import json
import os
import shutil
import tempfile
from atexit import register
from pathlib import Path

from agents import content_review as content_review_agent

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
SOURCE_REPAIR_COURSE_ID = "studio-source-repair-fixture"
CONTENT_REPAIR_COURSE_ID = "studio-content-repair-fixture"
CONTENT_BLOCKER_TRUTH_COURSE_ID = "studio-content-blocker-truth-fixture"
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

# A fifth isolated fixture carries one deterministic verifier blocker so NC-70
# exercises known-source addition, bounded evidence research, human source review,
# and the exact route transaction without starting NC-80 content regeneration.
_source_repair_seed_root = _acceptance_root / "courses" / SOURCE_REPAIR_COURSE_ID
_source_repair_seed_root.mkdir(parents=True)
for _fixture_path in _fixture_root.glob("*.json"):
    _artifact = json.loads(_fixture_path.read_text(encoding="utf-8"))
    _artifact["course_id"] = SOURCE_REPAIR_COURSE_ID
    if _artifact.get("artifact_type") == "content_package":
        _asset = _artifact["body"]["subtopics"][0]["assets"][0]
        _claim = _asset["claims"][0]
        _claim["support"] = "unsupported"
        _claim["supporting_excerpt"] = None
        _claim["note"] = "The approved route does not support this deterministic claim."
        _asset["verification"]["supported"] -= 1
        _asset["verification"]["unsupported"] += 1
    (_source_repair_seed_root / _fixture_path.name).write_text(
        json.dumps(_artifact, indent=2) + "\n",
        encoding="utf-8",
    )

# A sixth isolated fixture proves A9/A10 with two independently repairable hard
# findings plus one visible, nonblocking partial finding. Every baseline asset is
# pre-reviewed so fingerprint preservation and target-only resets are observable.
_content_repair_seed_root = _acceptance_root / "courses" / CONTENT_REPAIR_COURSE_ID
_content_repair_seed_root.mkdir(parents=True)
_content_repair_package = None
for _fixture_path in _fixture_root.glob("*.json"):
    _artifact = json.loads(_fixture_path.read_text(encoding="utf-8"))
    _artifact["course_id"] = CONTENT_REPAIR_COURSE_ID
    if _artifact.get("artifact_type") in {
        "lesson_plan",
        "render_manifest",
        "run_summary",
    }:
        continue
    if _artifact.get("artifact_type") == "content_package":
        _assets = {
            asset["id"]: asset
            for subtopic in _artifact["body"]["subtopics"]
            for asset in subtopic["assets"]
        }
        _better_asset = _assets["m1_s1_cc"]
        _better_claim = _better_asset["claims"][0]
        _better_claim["support"] = "unsupported"
        _better_claim["supporting_excerpt"] = None
        _better_claim["note"] = (
            "The approved route does not support this exact deterministic claim."
        )
        _better_asset["verification"]["supported"] -= 1
        _better_asset["verification"]["unsupported"] += 1

        _existing_asset = _assets["m1_s2_cc"]
        _existing_claim = _existing_asset["claims"][0]
        _existing_claim["support"] = "unsupported"
        _existing_claim["supporting_excerpt"] = None
        _existing_claim["note"] = (
            "This wording is incorrect and should be rewritten from the approved evidence."
        )
        _existing_asset["verification"]["supported"] -= 1
        _existing_asset["verification"]["unsupported"] += 1

        _partial_asset = _assets["m1_s3_cc"]
        _partial_claim = _partial_asset["claims"][0]
        _partial_claim["support"] = "partial"
        _partial_claim["supporting_excerpt"] = "Deterministic partial evidence."
        _partial_claim["note"] = "The source supports only part of the wording."
        _partial_asset["verification"]["supported"] -= 1
        _partial_asset["verification"]["partial"] += 1
        _content_repair_package = _artifact
    (_content_repair_seed_root / _fixture_path.name).write_text(
        json.dumps(_artifact, indent=2) + "\n",
        encoding="utf-8",
    )

if _content_repair_package is None:
    raise RuntimeError("browser Content repair fixture is missing content_package")
_content_review = content_review_agent.build_content_review_artifact(_content_repair_package)
for _review_record in _content_review["body"]["assets"]:
    _review_record["decision"] = "approved"
    _review_record["reviewed_at"] = "2026-07-20T00:00:00+00:00"
_content_review["body"]["summary"] = content_review_agent.review_summary(_content_review["body"])
_content_review["status"] = "approved"
(_content_repair_seed_root / "content_review.json").write_text(
    json.dumps(_content_review, indent=2) + "\n",
    encoding="utf-8",
)

# A seventh isolated fixture protects A8's browser truth for the two blocker shapes
# that are easy to undercount in a claim-only UI: a source-less claim and a standalone
# unattributed verifier finding. Human review starts pending and must remain disabled.
_content_truth_seed_root = _acceptance_root / "courses" / CONTENT_BLOCKER_TRUTH_COURSE_ID
_content_truth_seed_root.mkdir(parents=True)
_content_truth_package = None
for _fixture_path in _fixture_root.glob("*.json"):
    _artifact = json.loads(_fixture_path.read_text(encoding="utf-8"))
    _artifact["course_id"] = CONTENT_BLOCKER_TRUTH_COURSE_ID
    if _artifact.get("artifact_type") in {
        "lesson_plan",
        "render_manifest",
        "run_summary",
    }:
        continue
    if _artifact.get("artifact_type") == "content_package":
        _asset = _artifact["body"]["subtopics"][0]["assets"][0]
        _claim = _asset["claims"][0]
        _claim["source_id"] = None
        _claim["support"] = "supported"
        _claim["supporting_excerpt"] = None
        _claim["note"] = "This factual claim has no approved source attribution."
        _asset["verification"]["supported"] -= 1
        _asset["verification"]["ungrounded"] += 1
        _asset["verification"]["unattributed_found"].append(
            "A second factual statement has no approved source attribution."
        )
        _content_truth_package = _artifact
    (_content_truth_seed_root / _fixture_path.name).write_text(
        json.dumps(_artifact, indent=2) + "\n",
        encoding="utf-8",
    )

if _content_truth_package is None:
    raise RuntimeError("browser Content blocker-truth fixture is missing content_package")
_content_truth_review = content_review_agent.build_content_review_artifact(
    _content_truth_package
)
(_content_truth_seed_root / "content_review.json").write_text(
    json.dumps(_content_truth_review, indent=2) + "\n",
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
