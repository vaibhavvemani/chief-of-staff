from __future__ import annotations

from pathlib import Path

import pytest

from api.services.artifact_repository import ArtifactRepository, ReadOnlyCourse
from api.services.decision_service import DecisionService
from api.services.pipeline_catalog import PipelineCatalog
from api.services.stage_runner import StageRunner
from orchestrator import make_artifact

REPO_ROOT = Path(__file__).resolve().parents[1]


def _services(tmp_path: Path) -> tuple[ArtifactRepository, DecisionService]:
    repository = ArtifactRepository(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        include_examples=False,
    )
    catalog = PipelineCatalog(rendered_root=tmp_path / "rendered")
    return repository, DecisionService(repository, catalog)


def test_create_course_writes_only_a_valid_approved_subject_request(tmp_path: Path) -> None:
    repository, decisions = _services(tmp_path)

    artifact = decisions.create_course(
        subject="Indoor herb gardening",
        description="A compact course for apartment renters.",
        constraints=["No outdoor garden beds."],
        known_source_locators=["https://example.test/herbs"],
        course_id="herb-gardening",
    )

    assert artifact["course_id"] == "herb-gardening"
    assert artifact["artifact_type"] == "subject_request"
    assert artifact["status"] == "approved"
    assert repository.list_artifact_types("herb-gardening") == ["subject_request"]
    assert (
        tmp_path / "courses" / "herb-gardening" / "subject_request.json"
    ).is_file()


def test_create_course_rejects_unsafe_duplicate_and_empty_requests(tmp_path: Path) -> None:
    repository, decisions = _services(tmp_path)
    command = {
        "subject": "Coffee making",
        "description": None,
        "constraints": [],
        "known_source_locators": [],
    }

    with pytest.raises(ValueError):
        decisions.create_course(**command, course_id="../outside")
    with pytest.raises(ValueError, match="subject cannot be empty"):
        decisions.create_course(**{**command, "subject": "   "}, course_id="empty")

    decisions.create_course(**command, course_id="coffee-course")
    with pytest.raises(FileExistsError):
        decisions.create_course(**command, course_id="coffee-course")

    assert not (tmp_path / "outside").exists()
    assert repository.list_locations()[0].course_id == "coffee-course"


def test_stage_approve_and_reopen_commands_preserve_body_and_revision(tmp_path: Path) -> None:
    repository, decisions = _services(tmp_path)
    decisions.create_course(
        subject="Coffee making",
        description=None,
        constraints=[],
        known_source_locators=[],
        course_id="stage-course",
    )
    brief = make_artifact(
        "stage-course",
        "brief",
        "intake",
        body={"audience": "Home brewers"},
        inputs=["subject_request"],
    )
    repository.save(brief)
    original_body = brief["body"]
    original_revision = brief["revision"]

    approved = decisions.approve_stage("stage-course", "brief")
    reopened = decisions.reopen_stage("stage-course", "brief")

    assert approved[0]["status"] == "approved"
    assert reopened[0]["status"] == "draft"
    assert reopened[0]["body"] == original_body
    assert reopened[0]["revision"] == original_revision
    assert reopened[0]["revision_note"] == "Reopened by the course director."


def test_stage_commands_reject_unknown_stages_and_read_only_snapshots(tmp_path: Path) -> None:
    runtime_repository, runtime_decisions = _services(tmp_path)
    runtime_decisions.create_course(
        subject="Coffee making",
        description=None,
        constraints=[],
        known_source_locators=[],
        course_id="command-course",
    )
    with pytest.raises(ValueError, match="unknown product stage"):
        runtime_decisions.approve_stage("command-course", "not-a-stage")

    repository = ArtifactRepository(repo_root=REPO_ROOT)
    catalog = PipelineCatalog(rendered_root=tmp_path / "rendered")
    decisions = DecisionService(repository, catalog)
    runner = StageRunner(repository, catalog)

    with pytest.raises(ReadOnlyCourse):
        decisions.reopen_stage("coffee-live-main", "brief")
    with pytest.raises(ReadOnlyCourse):
        runner.run("coffee-live-main", "brief")
