from __future__ import annotations

import time
from pathlib import Path

import pytest

from api.services.artifact_repository import ArtifactRepository
from api.services.decision_service import DecisionService
from api.services.local_job_runner import CourseBusy, LocalJobRunner
from api.services.pipeline_catalog import PipelineCatalog
from orchestrator import make_artifact

REPO_ROOT = Path(__file__).resolve().parents[1]


def _wait_for_terminal(runner: LocalJobRunner, job_id: str) -> dict:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        job = runner.get(job_id)
        if job["status"] in {"completed", "failed", "cancelled"}:
            return job
        time.sleep(0.01)
    raise AssertionError("job did not reach a terminal state")


def _create_with_approved_brief(
    decisions: DecisionService,
    *,
    subject: str,
    course_id: str,
) -> None:
    decisions.create_course(
        subject=subject,
        description=None,
        constraints=[],
        known_source_locators=[],
        brief_details={
            "audience": "Adult learners new to the subject",
            "purpose": f"Apply {subject.lower()} safely and reliably.",
            "prior_knowledge": "No prior knowledge required.",
            "level": "beginner",
            "duration": "3 hours",
            "modality": "self_paced",
            "language": "English",
        },
        course_id=course_id,
    )
    decisions.approve_stage(course_id, "brief")


def test_local_job_runner_persists_job_and_versioned_events(tmp_path: Path) -> None:
    runner = LocalJobRunner(tmp_path / "runtime", max_workers=1)
    try:
        def task(emit):
            emit("stage.output_ready", stage="brief", message="Ready")
            return {"artifact_type": "brief"}

        job = runner.submit(
            course_id="safe-course",
            stage="brief",
            task=task,
        )
        completed = _wait_for_terminal(runner, job["job_id"])
        events = runner.events(job["job_id"])

        assert completed["status"] == "completed"
        assert completed["result"] == {"artifact_type": "brief"}
        assert [event["event_type"] for event in events] == [
            "job.queued",
            "job.started",
            "stage.output_ready",
            "job.completed",
        ]
        assert len({event["event_id"] for event in events}) == len(events)
        assert all(event["course_id"] == "safe-course" for event in events)
    finally:
        runner.shutdown()


def test_course_mutation_lock_rejects_a_second_mutation(tmp_path: Path) -> None:
    runner = LocalJobRunner(tmp_path / "runtime", max_workers=1)
    try:
        with runner.locks.acquire("locked-course"):
            with pytest.raises(CourseBusy):
                with runner.locks.acquire("locked-course"):
                    pass
    finally:
        runner.shutdown()


def test_content_review_endpoint_service_uses_canonical_review_ledger(tmp_path: Path) -> None:
    repository = ArtifactRepository(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        include_examples=False,
    )
    decisions = DecisionService(repository, PipelineCatalog(rendered_root=tmp_path / "rendered"))
    _create_with_approved_brief(
        decisions,
        subject="Safe lifting",
        course_id="review-course",
    )
    package = make_artifact(
        "review-course",
        "content_package",
        "student_content",
        body={
            "subtopics": [
                {
                    "subtopic_id": "m1_s1",
                    "assets": [
                        {
                            "id": "m1_s1_cc",
                            "type": "course_content",
                            "title": "Safe lifting basics",
                            "content": "Keep the load close.",
                            "solution": None,
                            "claims": [],
                            "sources": [],
                            "verification": {
                                "supported": 0,
                                "partial": 0,
                                "unsupported": 0,
                                "ungrounded": 0,
                                "unattributed_found": [],
                            },
                        }
                    ],
                }
            ]
        },
        inputs=["course_model", "blueprint", "course_outcomes"],
        schema_version="0.2",
    )
    package["status"] = "approved"
    repository.save(package)

    ledger = decisions.sync_content_review("review-course")
    decided = decisions.save_content_review(
        "review-course",
        "m1_s1_cc",
        decision="approved",
        note="Checked against the source pack.",
    )

    assert ledger["body"]["summary"]["pending"] == 1
    assert decided["body"]["assets"][0]["decision"] == "approved"
    assert decided["body"]["assets"][0]["feedback"] == "Checked against the source pack."
    assert decided["body"]["summary"]["ready_for_package"] is True
    assert decided["status"] == "approved"


def test_source_decision_service_persists_explicit_registry(tmp_path: Path) -> None:
    repository = ArtifactRepository(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        include_examples=False,
    )
    decisions = DecisionService(repository, PipelineCatalog(rendered_root=tmp_path / "rendered"))
    _create_with_approved_brief(
        decisions,
        subject="Indoor gardening",
        course_id="source-course",
    )
    dossier = make_artifact(
        "source-course",
        "research_dossier",
        "research",
        body={
            "source_candidates": [
                {
                    "id": "source_1",
                    "title": "University growing guide",
                    "publisher": "Example University",
                    "source_type": "web page",
                    "locator": "https://example.edu/growing",
                    "content_ref": "sources/source_1.txt",
                    "status": "proposed",
                    "trust_notes": "University extension guidance.",
                    "relevance": "Supports the growing sequence.",
                    "assigned_node_ids": [],
                }
            ]
        },
        inputs=["brief", "course_outcomes"],
        schema_version="0.2",
    )
    dossier["status"] = "draft"
    repository.save(dossier)

    registry = decisions.save_source_decision(
        "source-course", selected_ids=["source_1"]
    )

    assert registry["body"]["decision"]["selected_ids"] == ["source_1"]
    assert registry["body"]["decision"]["approved_ids"] == ["source_1"]
    assert registry["body"]["source_registry"][0]["id"] == "source_1"
    assert registry["status"] == "draft"
