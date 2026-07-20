from __future__ import annotations

import json
import time
from copy import deepcopy
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import MAX_MARKDOWN_PREVIEW_BYTES, create_app
from api.services.artifact_repository import ArtifactRepository
from api.services.local_job_runner import LocalJobRunner
from api.services.pipeline_catalog import PipelineCatalog
from api.services.stage_runner import StageRunner
from api.services.workspace_projector import WorkspaceProjector

REPO_ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_ARTIFACTS = (
    REPO_ROOT / "examples" / "acceptance" / "coffee-acceptance" / "course_artifacts"
)


def _wait(runner: LocalJobRunner, job_id: str) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = runner.get(job_id)
        if job["status"] in {"completed", "failed", "cancelled"}:
            return job
        time.sleep(0.01)
    raise AssertionError("job did not finish")


def _copy_artifacts(
    repository: ArtifactRepository,
    course_id: str,
    artifact_types: tuple[str, ...],
) -> None:
    for artifact_type in artifact_types:
        artifact = json.loads(
            (ACCEPTANCE_ARTIFACTS / f"{artifact_type}.json").read_text(encoding="utf-8")
        )
        artifact["course_id"] = course_id
        repository.save(artifact)


def test_content_pipeline_emits_started_and_terminal_events_during_unit_work(
    tmp_path: Path,
) -> None:
    course_id = "timely-content-progress"
    repository = ArtifactRepository(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        include_examples=False,
    )
    _copy_artifacts(
        repository,
        course_id,
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
    events: list[dict] = []

    StageRunner(
        repository,
        PipelineCatalog(rendered_root=tmp_path / "rendered"),
    ).run(
        course_id,
        "content",
        emit=lambda event_type, **payload: events.append(
            {"event_type": event_type, **payload}
        ),
    )

    units = [event for event in events if event["event_type"].startswith("unit.")]
    starts = [event for event in units if event["event_type"] == "unit.started"]
    terminals = [event for event in units if event["event_type"] != "unit.started"]
    assert starts
    assert len(starts) == len(terminals)
    assert len({event["asset_id"] for event in starts}) == len(starts)
    for started in starts:
        start_index = units.index(started)
        terminal_index = next(
            index
            for index, event in enumerate(units)
            if index > start_index
            and event["asset_id"] == started["asset_id"]
            and event["event_type"] in {"unit.completed", "unit.failed"}
        )
        assert terminal_index == start_index + 1
        assert units[terminal_index]["progress"]["expected"] == len(starts)
    assert events[-2]["event_type"] == "stage.output_ready"
    assert events[-1]["event_type"] == "checkpoint.awaiting_review"


def test_activity_and_diagnostics_are_persisted_aggregated_and_secret_safe(
    tmp_path: Path,
) -> None:
    runner = LocalJobRunner(tmp_path / "runtime", max_workers=1)
    try:
        def task(emit):
            emit(
                "model.call.completed",
                stage="outcomes",
                provider="anthropic",
                model="claude-opus-4-8",
                input_tokens=120,
                output_tokens=30,
                estimated_cost_usd=0.01,
                retry_count=2,
                cache_hit=True,
                message="Model call completed",
                prompt="this must be dropped",
                source_body="this must also be dropped",
            )
            emit(
                "model.call.failed",
                stage="outcomes",
                provider="anthropic",
                model="claude-opus-4-8",
                retry_count=1,
                cache_hit=False,
                error_type="ProviderError",
                message=(
                    "Authorization=Bearer-secret-value API_KEY=top-secret-value "
                    "provider config {'api_key': 'ultra-sensitive-value'} "
                    '{"authorization": "Basic structured-sensitive-value"}'
                ),
            )
            emit(
                "unit.completed",
                stage="outcomes",
                asset_id="bounded_unit",
                attempts=3,
                message="Unit completed after bounded retries",
            )
            return {"ok": True}

        job = runner.submit(course_id="safe-events", stage="outcomes", task=task)
        assert _wait(runner, job["job_id"])["status"] == "completed"

        activity = runner.activity_for_course("safe-events")
        serialized = json.dumps(activity)
        assert "this must be dropped" not in serialized
        assert "top-secret-value" not in serialized
        assert "Bearer-secret-value" not in serialized
        assert "ultra-sensitive-value" not in serialized
        assert "structured-sensitive-value" not in serialized
        assert serialized.count("[redacted]") >= 2

        diagnostics = runner.diagnostics_for_course("safe-events")
        assert diagnostics["totals"] == {
            "calls": 2,
            "input_tokens": 120,
            "output_tokens": 30,
            "estimated_cost_usd": 0.01,
            "cache_hits": 1,
            "retries": 5,
            "errors": 1,
        }
        assert diagnostics["stages"][0]["providers"] == ["anthropic"]
        assert diagnostics["stages"][0]["errors"][0]["type"] == "ProviderError"
    finally:
        runner.shutdown()


def test_synchronous_live_call_emitter_persists_brief_diagnostics(tmp_path: Path) -> None:
    runner = LocalJobRunner(tmp_path / "runtime", max_workers=1)
    try:
        emit = runner.event_emitter("sync-brief-events", "brief")
        emit(
            "model.call.completed",
            provider="anthropic",
            model="claude-opus-4-8",
            input_tokens=25,
            output_tokens=10,
            estimated_cost_usd=0.002,
            retry_count=0,
            cache_hit=False,
            message="Live Brief clarification completed",
        )

        activity = runner.activity_for_course("sync-brief-events")
        assert len(activity) == 1
        assert activity[0]["stage"] == "brief"
        diagnostics = runner.diagnostics_for_course("sync-brief-events")
        assert diagnostics["totals"]["calls"] == 1
        assert diagnostics["stages"][0]["stage"] == "brief"
        assert diagnostics["stages"][0]["input_tokens"] == 25
    finally:
        runner.shutdown()


def test_workspace_projects_backend_owned_actionable_release_checks(tmp_path: Path) -> None:
    course_id = "actionable-release-checks"
    repository = ArtifactRepository(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        include_examples=False,
    )
    _copy_artifacts(
        repository,
        course_id,
        (
            "subject_request",
            "brief",
            "course_outcomes",
            "research_dossier",
            "approved_source_registry",
            "course_model",
            "blueprint",
            "content_package",
            "content_progress",
            "lesson_plan",
            "render_manifest",
            "run_summary",
        ),
    )
    runner = LocalJobRunner(tmp_path / "runtime", max_workers=1)
    try:
        workspace = WorkspaceProjector(
            repository,
            PipelineCatalog(rendered_root=tmp_path / "rendered"),
            job_runner=runner,
        ).project(course_id)
    finally:
        runner.shutdown()

    checks = {check["id"]: check for check in workspace["release_checks"]}
    assert set(checks) >= {
        "integrity",
        "source_boundary",
        "asset_reconciliation",
        "human_review",
    }
    assert checks["integrity"]["passed"] is True
    assert checks["source_boundary"]["passed"] is True
    assert checks["asset_reconciliation"]["passed"] is True
    assert checks["human_review"]["passed"] is False
    assert checks["human_review"]["target_stage"] == "content"
    assert checks["human_review"]["target_asset_id"] == "m1_s1_cc"


class _NotReadyProvider:
    provider_name = "test-provider"
    model_name = "test-model"

    def ready(self) -> bool:
        return False

    def generate(self, **_kwargs):
        raise AssertionError("an unready provider must never be called")


def test_workspace_projects_readiness_and_api_blocks_unready_live_start(
    tmp_path: Path,
) -> None:
    app = create_app(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        runtime_root=tmp_path / "runtime",
        include_examples=False,
        structured_model_provider=_NotReadyProvider(),
    )
    repository = app.state.repository
    repair_course_id = "unready-live-content"
    _copy_artifacts(
        repository,
        repair_course_id,
        (
            "subject_request",
            "brief",
            "course_outcomes",
            "research_dossier",
            "approved_source_registry",
            "course_model",
            "blueprint",
            "content_package",
            "content_progress",
        ),
    )
    package = deepcopy(repository.require(repair_course_id, "content_package"))
    asset = package["body"]["subtopics"][0]["assets"][0]
    claim = asset["claims"][0]
    claim["support"] = "unsupported"
    claim["supporting_excerpt"] = None
    asset["verification"]["supported"] -= 1
    asset["verification"]["unsupported"] += 1
    package = repository.save(
        package,
        expected_checksum=repository.checksum(
            repository.require(repair_course_id, "content_package")
        ),
    )
    with TestClient(app) as client:
        created = client.post(
            "/api/courses",
            json={
                "course_id": "unready-live",
                "subject": "Indoor herbs",
                "brief": {
                    "audience": "Apartment gardeners",
                    "purpose": "Grow herbs indoors",
                    "prior_knowledge": "None",
                    "level": "beginner",
                    "duration": "3 hours",
                    "modality": "self_paced",
                    "language": "English",
                },
            },
        )
        assert created.status_code == 201
        workspace = client.get("/api/courses/unready-live/workspace").json()
        readiness = workspace["provider_readiness"]
        assert readiness == {
            "ready": False,
            "provider": "test-provider",
            "model": "test-model",
            "message": "Live test-provider credentials are not configured on the server.",
        }

        brief_stage = client.get("/api/courses/unready-live/stages/brief").json()
        assert client.post(
            "/api/courses/unready-live/stages/brief/approve",
            json={"expected_checksum": brief_stage["checksum"]},
        ).status_code == 200
        response = client.post(
            "/api/courses/unready-live/stages/outcomes/run",
            json={"mode": "live"},
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "provider_not_ready"
        assert workspace["active_job"] is None

        content_stage = client.get(
            f"/api/courses/{repair_course_id}/stages/content"
        ).json()
        assert {action["id"] for action in content_stage["actions"]} >= {
            "revise",
            "source_repair",
            "content_repair",
        }
        revision = client.post(
            f"/api/courses/{repair_course_id}/stages/content/revisions",
            json={
                "expected_checksum": content_stage["checksum"],
                "target_type": "asset",
                "target_ids": [asset["id"]],
                "category": "evidence",
                "instruction": "Repair only the named evidence finding.",
                "mode": "live",
            },
        )
        content_repair = client.post(
            f"/api/courses/{repair_course_id}/content/repairs",
            json={
                "expected_content_checksum": repository.checksum(package),
                "strategy": "existing_evidence",
                "targets": [
                    {
                        "asset_id": asset["id"],
                        "claim_ids": [claim["id"]],
                        "finding_ids": [claim["id"]],
                    }
                ],
                "mode": "live",
            },
        )
        source_repair = client.post(
            f"/api/courses/{repair_course_id}/source-repairs",
            json={
                "expected_content_checksum": repository.checksum(package),
                "subtopic_id": package["body"]["subtopics"][0]["subtopic_id"],
                "asset_id": asset["id"],
                "claim_id": claim["id"],
                "finding_id": claim["id"],
                "evidence_gap": "Find evidence for the named claim.",
                "mode": "live",
            },
        )
        for blocked in (revision, content_repair, source_repair):
            assert blocked.status_code == 503, blocked.text
            assert blocked.json()["error"]["code"] == "provider_not_ready"
        jobs_dir = tmp_path / "runtime" / repair_course_id / "jobs"
        assert not jobs_dir.exists() or not list(jobs_dir.glob("*.json"))


def test_rendered_output_endpoint_serves_only_bounded_utf8_markdown_as_text(
    tmp_path: Path,
) -> None:
    rendered_root = tmp_path / "rendered"
    app = create_app(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=rendered_root,
        runtime_root=tmp_path / "runtime",
        include_examples=False,
    )
    with TestClient(app) as client:
        assert client.post(
            "/api/courses",
            json={"course_id": "safe-markdown", "subject": "Safe text"},
        ).status_code == 201
        output = rendered_root / "safe-markdown"
        output.mkdir(parents=True)
        (output / "README.md").write_text(
            "# Safe preview\n\n<script>displayed only as text</script>\n",
            encoding="utf-8",
        )
        (output / "unsafe.html").write_text("<script>unsafe</script>", encoding="utf-8")
        (output / "too-large.md").write_bytes(b"x" * (MAX_MARKDOWN_PREVIEW_BYTES + 1))
        (output / "invalid.md").write_bytes(b"\xff\xfe")

        response = client.get("/api/courses/safe-markdown/outputs/README.md")
        assert response.status_code == 200
        assert response.text.startswith("# Safe preview")
        assert response.headers["content-type"].startswith("text/markdown")
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "sandbox" in response.headers["content-security-policy"]
        assert client.get(
            "/api/courses/safe-markdown/outputs/unsafe.html"
        ).status_code == 415
        assert client.get(
            "/api/courses/safe-markdown/outputs/too-large.md"
        ).status_code == 413
        assert client.get(
            "/api/courses/safe-markdown/outputs/invalid.md"
        ).status_code == 422
