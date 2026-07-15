from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.services.artifact_repository import ArtifactRepository
from api.services.local_job_runner import LocalJobRunner, _safe_error_message
from api.services.pipeline_catalog import PipelineCatalog
from api.services.revision_service import NoOpRevision
from api.services.stage_runner import StageRunner
from api.services.workspace_projector import WorkspaceProjector
from orchestrator import Step, make_artifact

REPO_ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_ARTIFACTS = (
    REPO_ROOT / "examples" / "acceptance" / "coffee-acceptance" / "course_artifacts"
)


def _repository(tmp_path: Path) -> ArtifactRepository:
    return ArtifactRepository(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        include_examples=False,
    )


def _copy_acceptance_course(repository: ArtifactRepository, *, course_id: str) -> None:
    for path in ACCEPTANCE_ARTIFACTS.glob("*.json"):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        artifact["course_id"] = course_id
        repository.save(artifact)


def _wait_for_terminal(runner: LocalJobRunner, job_id: str) -> dict:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        job = runner.get(job_id)
        if job["status"] in {"completed", "failed", "cancelled"}:
            return job
        time.sleep(0.01)
    raise AssertionError("job did not reach a terminal state")


def test_safe_job_errors_redact_common_credential_shapes() -> None:
    message = _safe_error_message(
        RuntimeError(
            "provider failed: ANTHROPIC_API_KEY=top-secret-value; "
            "Authorization: Bearer-token-value Bearer direct-token-value"
        )
    )

    assert "top-secret-value" not in message
    assert "Bearer-token-value" not in message
    assert "direct-token-value" not in message
    assert message.count("[redacted]") == 3


def test_failed_multistep_package_run_preserves_canonical_outputs_and_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    course_id = "atomic-package-course"
    repository = _repository(tmp_path)
    _copy_acceptance_course(repository, course_id=course_id)
    before_manifest = repository.require(course_id, "render_manifest")
    before_summary = repository.require(course_id, "run_summary")
    before_checksums = {
        "render_manifest": repository.checksum(before_manifest),
        "run_summary": repository.checksum(before_summary),
    }

    fail_summary = True

    def render_step(_inputs: dict, _feedback: str | None) -> dict:
        return {
            "render_manifest": make_artifact(
                course_id,
                "render_manifest",
                "render_course_folder",
                body={"files": ["new-output.md"]},
                inputs=[],
            )
        }

    def summary_step(_inputs: dict, _feedback: str | None) -> dict:
        if fail_summary:
            raise RuntimeError("summary generation failed after render")
        return {
            "run_summary": make_artifact(
                course_id,
                "run_summary",
                "run_summary",
                body={"operator_status": "complete", "retry_marker": True},
                inputs=["render_manifest"],
            )
        }

    package_steps = [
        Step("render_course_folder", [], ["render_manifest"], render_step),
        Step("run_summary", ["render_manifest"], ["run_summary"], summary_step),
    ]
    catalog = PipelineCatalog(rendered_root=tmp_path / "rendered")
    monkeypatch.setattr(
        catalog,
        "steps_for_stage",
        lambda slug, mode="deterministic": (
            package_steps
            if slug == "package"
            else PipelineCatalog.steps_for_stage(catalog, slug, mode=mode)
        ),
    )
    stage_runner = StageRunner(repository, catalog)
    jobs = LocalJobRunner(tmp_path / "runtime", max_workers=1)
    try:
        failed_job = jobs.submit(
            course_id=course_id,
            stage="package",
            task=lambda emit: stage_runner.run(course_id, "package", emit=emit),
        )
        failed = _wait_for_terminal(jobs, failed_job["job_id"])

        assert failed["status"] == "failed"
        assert failed["error"] == {
            "type": "RuntimeError",
            "message": "summary generation failed after render",
        }
        assert (
            repository.checksum(repository.require(course_id, "render_manifest"))
            == before_checksums["render_manifest"]
        )
        assert (
            repository.checksum(repository.require(course_id, "run_summary"))
            == before_checksums["run_summary"]
        )
        assert "stage.output_ready" not in {
            event["event_type"] for event in jobs.events(failed_job["job_id"])
        }

        fail_summary = False
        retry_job = jobs.submit(
            course_id=course_id,
            stage="package",
            task=lambda emit: stage_runner.run(course_id, "package", emit=emit),
        )
        retried = _wait_for_terminal(jobs, retry_job["job_id"])

        assert retried["status"] == "completed"
        assert repository.require(course_id, "render_manifest")["body"] == {
            "files": ["new-output.md"]
        }
        assert repository.require(course_id, "run_summary")["body"] == {
            "operator_status": "complete",
            "retry_marker": True,
        }
        assert jobs.latest_for_stage(course_id, "package")["job_id"] == retry_job["job_id"]
    finally:
        jobs.shutdown()


def test_noop_revision_fails_truthfully_without_overwriting_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    course_id = "noop-revision-course"
    repository = _repository(tmp_path)
    _copy_acceptance_course(repository, course_id=course_id)
    package = repository.require(course_id, "content_package")
    progress = repository.require(course_id, "content_progress")
    before_checksums = {
        "content_package": repository.checksum(package),
        "content_progress": repository.checksum(progress),
    }

    def unchanged_content_step(_inputs: dict, _feedback: str | None) -> dict:
        return {
            "content_package": deepcopy(package),
            "content_progress": deepcopy(progress),
        }

    catalog = PipelineCatalog(rendered_root=tmp_path / "rendered")
    monkeypatch.setattr(
        catalog,
        "steps_for_stage",
        lambda slug, mode="deterministic": (
            [
                Step(
                    "student_content",
                    [],
                    ["content_package", "content_progress"],
                    unchanged_content_step,
                )
            ]
            if slug == "content"
            else PipelineCatalog.steps_for_stage(catalog, slug, mode=mode)
        ),
    )
    stage_runner = StageRunner(repository, catalog)
    jobs = LocalJobRunner(tmp_path / "runtime", max_workers=1)
    try:
        job = jobs.submit(
            course_id=course_id,
            stage="content",
            task=lambda emit: stage_runner.run(
                course_id,
                "content",
                revision={
                    "target_type": "asset",
                    "target_ids": ["m1_s1_cc"],
                    "category": "clarity",
                    "instruction": "Use clearer language.",
                },
                emit=emit,
            ),
        )
        failed = _wait_for_terminal(jobs, job["job_id"])

        assert failed["status"] == "failed"
        assert failed["result"] is None
        assert failed["error"]["type"] == NoOpRevision.__name__
        assert "prior artifact was preserved" in failed["error"]["message"]
        assert (
            repository.checksum(repository.require(course_id, "content_package"))
            == before_checksums["content_package"]
        )
        assert (
            repository.checksum(repository.require(course_id, "content_progress"))
            == before_checksums["content_progress"]
        )
        assert repository.load(course_id, "content_review") is None
        event_types = [event["event_type"] for event in jobs.events(job["job_id"])]
        assert "stage.output_ready" not in event_types
        assert "checkpoint.awaiting_review" not in event_types
        assert event_types[-1] == "job.failed"
    finally:
        jobs.shutdown()


def test_revision_that_changes_an_undeclared_asset_is_rejected_atomically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    course_id = "scope-escape-course"
    repository = _repository(tmp_path)
    _copy_acceptance_course(repository, course_id=course_id)
    package = repository.require(course_id, "content_package")
    progress = repository.require(course_id, "content_progress")
    before = repository.checksum(package)

    def escaped_content_step(_inputs: dict, _feedback: str | None) -> dict:
        changed = deepcopy(package)
        changed["body"]["subtopics"][0]["assets"][1]["content"] += " Out of scope."
        return {
            "content_package": changed,
            "content_progress": deepcopy(progress),
        }

    catalog = PipelineCatalog(rendered_root=tmp_path / "rendered")
    monkeypatch.setattr(
        catalog,
        "steps_for_stage",
        lambda slug, mode="deterministic": (
            [
                Step(
                    "student_content",
                    [],
                    ["content_package", "content_progress"],
                    escaped_content_step,
                )
            ]
            if slug == "content"
            else PipelineCatalog.steps_for_stage(catalog, slug, mode=mode)
        ),
    )
    runner = StageRunner(repository, catalog)

    with pytest.raises(ValueError, match="outside its declared scope"):
        runner.run(
            course_id,
            "content",
            revision={
                "target_type": "asset",
                "target_ids": ["m1_s1_cc"],
                "category": "clarity",
                "instruction": "Clarify only the named asset.",
            },
        )

    assert repository.checksum(repository.require(course_id, "content_package")) == before


def test_interrupted_job_is_projected_as_retryable_after_restart(
    tmp_path: Path,
) -> None:
    course_id = "restart-retry-course"
    repository = _repository(tmp_path)
    subject = make_artifact(
        course_id,
        "subject_request",
        "seed",
        body={"subject": "Safe lifting"},
        inputs=[],
    )
    subject["status"] = "approved"
    repository.save(subject)

    runtime_root = tmp_path / "runtime"
    jobs_dir = runtime_root / course_id / "jobs"
    jobs_dir.mkdir(parents=True)
    interrupted_id = "interruptedjob"
    (jobs_dir / f"{interrupted_id}.json").write_text(
        json.dumps(
            {
                "job_id": interrupted_id,
                "course_id": course_id,
                "stage": "brief",
                "status": "running",
                "created_at": "2020-01-01T00:00:00.000+00:00",
                "started_at": "2020-01-01T00:00:01.000+00:00",
                "completed_at": None,
                "result": None,
                "error": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    jobs = LocalJobRunner(runtime_root, max_workers=1)
    try:
        recovered = jobs.get(interrupted_id)
        projected = WorkspaceProjector(
            repository,
            PipelineCatalog(rendered_root=tmp_path / "rendered"),
            job_runner=jobs,
        ).stage(course_id, "brief")

        assert recovered["status"] == "failed"
        assert recovered["error"] == {
            "type": "InterruptedJob",
            "message": "The API process stopped before this job completed; rerun is safe.",
        }
        assert projected["state"] == "failed"
        assert projected["last_failure"] == recovered["error"]
        assert [action["id"] for action in projected["actions"]] == ["retry"]

        retry = jobs.submit(
            course_id=course_id,
            stage="brief",
            task=lambda _emit: {"retried": True},
        )
        completed = _wait_for_terminal(jobs, retry["job_id"])

        assert completed["status"] == "completed"
        assert completed["result"] == {"retried": True}
        assert jobs.latest_for_stage(course_id, "brief")["job_id"] == retry["job_id"]
    finally:
        jobs.shutdown()


def test_interrupted_job_can_be_retried_through_api_after_restart(
    tmp_path: Path,
) -> None:
    course_id = "api-restart-retry-course"
    courses_root = tmp_path / "courses"
    rendered_root = tmp_path / "rendered"
    runtime_root = tmp_path / "runtime"
    repository = ArtifactRepository(
        repo_root=REPO_ROOT,
        courses_root=courses_root,
        rendered_root=rendered_root,
        include_examples=False,
    )
    subject = make_artifact(
        course_id,
        "subject_request",
        "seed",
        body={"subject": "Safe lifting"},
        inputs=[],
    )
    subject["status"] = "approved"
    repository.save(subject)

    jobs_dir = runtime_root / course_id / "jobs"
    jobs_dir.mkdir(parents=True)
    interrupted_id = "apiinterruptedjob"
    (jobs_dir / f"{interrupted_id}.json").write_text(
        json.dumps(
            {
                "job_id": interrupted_id,
                "course_id": course_id,
                "stage": "brief",
                "status": "running",
                "created_at": "2020-01-01T00:00:00.000+00:00",
                "started_at": "2020-01-01T00:00:01.000+00:00",
                "completed_at": None,
                "result": None,
                "error": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    app = create_app(
        repo_root=REPO_ROOT,
        courses_root=courses_root,
        rendered_root=rendered_root,
        runtime_root=runtime_root,
        include_examples=False,
    )
    with TestClient(app) as client:
        recovered_stage = client.get(f"/api/courses/{course_id}/stages/brief").json()
        assert recovered_stage["state"] == "failed"
        assert [action["id"] for action in recovered_stage["actions"]] == ["retry"]

        response = client.post(
            f"/api/courses/{course_id}/stages/brief/run",
            json={
                "mode": "deterministic",
                "expected_checksum": recovered_stage["checksum"],
            },
        )
        assert response.status_code == 202, response.text
        retried = _wait_for_terminal(app.state.jobs, response.json()["job"]["job_id"])

        assert retried["status"] == "completed", retried
        brief = app.state.repository.require(course_id, "brief")
        assert brief["status"] == "draft"
        assert (
            client.get(f"/api/courses/{course_id}/stages/brief").json()["state"]
            == "awaiting_review"
        )
