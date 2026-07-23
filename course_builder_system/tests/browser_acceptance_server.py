"""Production-shaped FastAPI server with isolated browser-acceptance storage."""

from __future__ import annotations

import importlib
import json
import os
import shutil
import tempfile
import threading
import time
from atexit import register
from pathlib import Path

import acceptance
import steps
from agents import content_review as content_review_agent

_configured_acceptance_root = os.getenv("COURSE_BUILDER_BROWSER_ACCEPTANCE_ROOT")
if _configured_acceptance_root:
    _acceptance_root = Path(_configured_acceptance_root)
    _acceptance_root.mkdir(parents=True, exist_ok=True)
else:
    _acceptance_root = Path(tempfile.mkdtemp(prefix="course-builder-browser-acceptance-"))
    register(shutil.rmtree, _acceptance_root, ignore_errors=True)
os.environ["COURSE_BUILDER_COURSES_ROOT"] = str(_acceptance_root / "courses")
os.environ["COURSE_BUILDER_RENDERED_ROOT"] = str(_acceptance_root / "rendered_courses")
os.environ["COURSE_BUILDER_RUNTIME_ROOT"] = str(_acceptance_root / "runtime")
os.environ["COURSE_BUILDER_INCLUDE_EXAMPLES"] = "true"

# Seed a writable, isolated copy of the complete deterministic fixture so browser
# lifecycle tests can reopen an approved mid-pipeline stage without mutating the
# committed example or replaying later work packages through the UI.
SEEDED_LIFECYCLE_COURSE_ID = "studio-course-model-reopen-fixture"
PACKAGE_PREVIEW_COURSE_ID = "studio-package-preview-fixture"
COURSE_MODEL_EDITOR_COURSE_ID = "studio-course-model-editor-fixture"
BLUEPRINT_EDITOR_COURSE_ID = "studio-blueprint-editor-fixture"
LESSON_PLAN_EDITOR_COURSE_ID = "studio-lesson-plan-editor-fixture"
SOURCE_REPAIR_COURSE_ID = "studio-source-repair-fixture"
CONTENT_REPAIR_COURSE_ID = "studio-content-repair-fixture"
CONTENT_BLOCKER_TRUTH_COURSE_ID = "studio-content-blocker-truth-fixture"
REOPEN_RERUN_COURSE_ID = "studio-reopen-rerun-fixture"
FAILURE_RECOVERY_COURSE_ID = "studio-failure-recovery-fixture"
ACTIVE_REFRESH_COURSE_ID = "studio-active-refresh-fixture"
RESTART_RECOVERY_COURSE_ID = "studio-restart-recovery-fixture"
NEGATIVE_SOURCE_COURSE_ID = "studio-negative-source-fixture"
_fixture_root = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "acceptance"
    / "coffee-acceptance"
    / "course_artifacts"
)
_seed_root = _acceptance_root / "courses" / SEEDED_LIFECYCLE_COURSE_ID
_seed_root.mkdir(parents=True, exist_ok=True)
for _fixture_path in _fixture_root.glob("*.json"):
    _artifact = json.loads(_fixture_path.read_text(encoding="utf-8"))
    _artifact["course_id"] = SEEDED_LIFECYCLE_COURSE_ID
    (_seed_root / _fixture_path.name).write_text(
        json.dumps(_artifact, indent=2) + "\n",
        encoding="utf-8",
    )
_rendered_fixture_root = _fixture_root.parent / "rendered_course"
shutil.copytree(
    _rendered_fixture_root,
    _acceptance_root / "rendered_courses" / SEEDED_LIFECYCLE_COURSE_ID,
    dirs_exist_ok=True,
)


def _seed_artifacts(course_id: str, artifact_types: tuple[str, ...]) -> Path:
    """Copy one bounded mutable fixture slice into isolated acceptance storage."""
    course_root = _acceptance_root / "courses" / course_id
    course_root.mkdir(parents=True, exist_ok=True)
    for artifact_type in artifact_types:
        artifact = json.loads(
            (_fixture_root / f"{artifact_type}.json").read_text(encoding="utf-8")
        )
        artifact["course_id"] = course_id
        (course_root / f"{artifact_type}.json").write_text(
            json.dumps(artifact, indent=2) + "\n",
            encoding="utf-8",
        )
    return course_root


# NC-110 recovery fixtures are isolated from the earlier package checkpoints. One
# starts complete for reopen/rerun; two stop at Blueprint for failure/refresh tests;
# one runs long enough for the acceptance supervisor to restart the API process.
_seed_artifacts(
    REOPEN_RERUN_COURSE_ID,
    tuple(path.stem for path in sorted(_fixture_root.glob("*.json"))),
)
shutil.copytree(
    _rendered_fixture_root,
    _acceptance_root / "rendered_courses" / REOPEN_RERUN_COURSE_ID,
    dirs_exist_ok=True,
)
for _course_id in (FAILURE_RECOVERY_COURSE_ID, ACTIVE_REFRESH_COURSE_ID):
    _seed_artifacts(
        _course_id,
        (
            "subject_request",
            "brief",
            "course_outcomes",
            "research_dossier",
            "approved_source_registry",
            "course_model",
            "blueprint",
        ),
    )
_seed_artifacts(
    RESTART_RECOVERY_COURSE_ID,
    ("subject_request", "brief"),
)
_negative_source_root = _seed_artifacts(
    NEGATIVE_SOURCE_COURSE_ID,
    (
        "subject_request",
        "brief",
        "course_outcomes",
        "research_dossier",
        "approved_source_registry",
        "course_model",
    ),
)
_negative_model_path = _negative_source_root / "course_model.json"
_negative_model = json.loads(_negative_model_path.read_text(encoding="utf-8"))
_negative_model["status"] = "draft"
_negative_model_path.write_text(
    json.dumps(_negative_model, indent=2) + "\n",
    encoding="utf-8",
)
# Exercise real asynchronous failure/retry and refresh/concurrency behavior without
# introducing test-only routes into the product API. The default deterministic asset
# implementation is wrapped only in this dedicated acceptance process.
_deterministic_generate_asset = acceptance.deterministic_generate_asset


def _controlled_generate_asset(*args, **kwargs):
    inputs = kwargs.get("inputs")
    if inputs is None and len(args) > 1:
        inputs = args[1]
    course_model = inputs.get("course_model", {}) if isinstance(inputs, dict) else {}
    course_id = course_model.get("course_id") if isinstance(course_model, dict) else None
    if course_id is None and isinstance(inputs, dict):
        course_id = next(
            (
                value.get("course_id")
                for value in inputs.values()
                if isinstance(value, dict) and value.get("course_id")
            ),
            None,
        )
    if course_id == ACTIVE_REFRESH_COURSE_ID:
        time.sleep(0.30)
    return _deterministic_generate_asset(*args, **kwargs)


acceptance.deterministic_generate_asset = _controlled_generate_asset

_make_student_content_step = steps.make_student_content_step
_controlled_stage_failure_seen = False


def _controlled_make_student_content_step(*args, **kwargs):
    implementation = _make_student_content_step(*args, **kwargs)

    def run(inputs, feedback=None):
        global _controlled_stage_failure_seen
        course_model = inputs.get("course_model", {}) if isinstance(inputs, dict) else {}
        course_id = course_model.get("course_id") if isinstance(course_model, dict) else None
        if (
            course_id == FAILURE_RECOVERY_COURSE_ID
            and not _controlled_stage_failure_seen
        ):
            _controlled_stage_failure_seen = True
            raise RuntimeError("controlled NC-110 deterministic generation failure")
        return implementation(inputs, feedback)

    return run


steps.make_student_content_step = _controlled_make_student_content_step

_course_outcomes_step = steps.course_outcomes_step
_restart_marker = _acceptance_root / ".nc110-restart-started"


def _controlled_course_outcomes_step(inputs, feedback=None):
    brief = inputs.get("brief", {}) if isinstance(inputs, dict) else {}
    course_id = brief.get("course_id") if isinstance(brief, dict) else None
    if course_id == RESTART_RECOVERY_COURSE_ID and not _restart_marker.exists():
        _restart_marker.write_text("started\n", encoding="utf-8")
        time.sleep(60)
    return _course_outcomes_step(inputs, feedback)


steps.course_outcomes_step = _controlled_course_outcomes_step

# Keep Package rendering independent from the lifecycle fixture, which another
# scenario intentionally reopens and invalidates.
_package_seed_root = _acceptance_root / "courses" / PACKAGE_PREVIEW_COURSE_ID
_package_seed_root.mkdir(parents=True, exist_ok=True)
for _fixture_path in _fixture_root.glob("*.json"):
    _artifact = json.loads(_fixture_path.read_text(encoding="utf-8"))
    _artifact["course_id"] = PACKAGE_PREVIEW_COURSE_ID
    (_package_seed_root / _fixture_path.name).write_text(
        json.dumps(_artifact, indent=2) + "\n",
        encoding="utf-8",
    )
shutil.copytree(
    _rendered_fixture_root,
    _acceptance_root / "rendered_courses" / PACKAGE_PREVIEW_COURSE_ID,
    dirs_exist_ok=True,
)

# A second bounded fixture stops at the approved Research checkpoint so the browser
# acceptance scenario exercises the real deterministic Course Model run before editing.
_editor_seed_root = _acceptance_root / "courses" / COURSE_MODEL_EDITOR_COURSE_ID
_editor_seed_root.mkdir(parents=True, exist_ok=True)
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
_source_repair_seed_root.mkdir(parents=True, exist_ok=True)
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
_content_repair_seed_root.mkdir(parents=True, exist_ok=True)
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
_content_truth_seed_root.mkdir(parents=True, exist_ok=True)
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
_blueprint_seed_root.mkdir(parents=True, exist_ok=True)
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
_lesson_plan_seed_root.mkdir(parents=True, exist_ok=True)
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


@app.post("/__acceptance__/terminate-api")
def terminate_api_process() -> dict[str, bool]:
    """Terminate this acceptance-only API child after returning the response."""

    threading.Timer(0.10, lambda: os._exit(73)).start()
    return {"terminating": True}
