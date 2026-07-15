from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def _client_with_complete_course(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        runtime_root=tmp_path / "runtime",
        include_examples=False,
    )
    repository = app.state.repository
    fixture_root = REPO_ROOT / "examples" / "acceptance" / "coffee-acceptance" / "course_artifacts"
    for path in fixture_root.glob("*.json"):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        artifact["course_id"] = "impact-course"
        repository.save(artifact)
    with TestClient(app) as client:
        yield client


def test_reopen_requires_fresh_typed_impact_and_preserves_stale_bodies(
    tmp_path: Path,
) -> None:
    with _client_with_complete_course(tmp_path) as client:
        repository = client.app.state.repository
        stage = client.get("/api/courses/impact-course/stages/course-model").json()
        preview = client.post(
            "/api/courses/impact-course/stages/course-model/impact",
            json={
                "action": "reopen",
                "expected_checksum": stage["checksum"],
                "target_type": "subtopic",
                "target_ids": ["m1_s4"],
                "operation_summary": "Rescope troubleshooting",
            },
        )
        assert preview.status_code == 200, preview.text
        impact = preview.json()
        assert impact["direct_artifacts"] == ["course_model"]
        assert "blueprint" in impact["stale_artifacts"]
        assert "content_package" in impact["stale_artifacts"]
        assert impact["requires_rerun_stages"] == [
            "blueprint",
            "content",
            "lesson-plan",
            "package",
        ]
        package = repository.require("impact-course", "content_package")
        all_asset_ids = {
            asset["id"] for subtopic in package["body"]["subtopics"] for asset in subtopic["assets"]
        }
        # A target hint cannot make a general reopen look bounded. The actual
        # mutation stales the whole downstream graph, so every saved Content asset
        # is affected and none is promised as preserved.
        assert set(impact["targeted_assets"]) == all_asset_ids
        assert impact["preserved_assets"] == []
        assert impact["impact_level"] == "downstream"

        without_confirmation = client.post(
            "/api/courses/impact-course/stages/course-model/reopen",
            json={"expected_checksum": stage["checksum"]},
        )
        assert without_confirmation.status_code == 409
        assert without_confirmation.json()["error"]["code"] == "impact_confirmation_required"

        blueprint = repository.require("impact-course", "blueprint")
        blueprint_checksum = repository.checksum(blueprint)
        blueprint["revision_note"] = "Concurrent downstream decision"
        repository.save(blueprint, expected_checksum=blueprint_checksum)
        stale_preview = client.post(
            "/api/courses/impact-course/stages/course-model/reopen",
            json={
                "expected_checksum": stage["checksum"],
                "impact_acknowledged": True,
                "expected_impact_checksum": impact["impact_checksum"],
            },
        )
        assert stale_preview.status_code == 409
        assert stale_preview.json()["error"]["code"] == "stale_impact_preview"

        fresh = client.post(
            "/api/courses/impact-course/stages/course-model/impact",
            json={"action": "reopen", "expected_checksum": stage["checksum"]},
        ).json()
        stale_types = fresh["stale_artifacts"]
        body_checksums = {
            artifact_type: repository.checksum(
                repository.require("impact-course", artifact_type)["body"]
            )
            for artifact_type in stale_types
        }
        reopened = client.post(
            "/api/courses/impact-course/stages/course-model/reopen",
            json={
                "expected_checksum": stage["checksum"],
                "impact_acknowledged": True,
                "expected_impact_checksum": fresh["impact_checksum"],
                "reason": "Rescope troubleshooting",
            },
        )
        assert reopened.status_code == 200, reopened.text
        assert reopened.json()["stage"]["state"] == "awaiting_review"
        assert set(reopened.json()["stale_artifact_types"]) == set(stale_types)
        for artifact_type in stale_types:
            artifact = repository.require("impact-course", artifact_type)
            assert artifact["status"] == "stale"
            assert repository.checksum(artifact["body"]) == body_checksums[artifact_type]

        blueprint_stage = client.get("/api/courses/impact-course/stages/blueprint").json()
        assert blueprint_stage["state"] == "stale"
        rerun = next(action for action in blueprint_stage["actions"] if action["id"] == "run")
        assert rerun["enabled"] is False
        blocked_run = client.post(
            "/api/courses/impact-course/stages/blueprint/run",
            json={
                "mode": "deterministic",
                "expected_checksum": blueprint_stage["checksum"],
            },
        )
        assert blocked_run.status_code == 409


def test_content_reopen_reports_direct_content_as_affected(tmp_path: Path) -> None:
    with _client_with_complete_course(tmp_path) as client:
        stage = client.get("/api/courses/impact-course/stages/content").json()
        preview = client.post(
            "/api/courses/impact-course/stages/content/impact",
            json={"action": "reopen", "expected_checksum": stage["checksum"]},
        )

        assert preview.status_code == 200, preview.text
        impact = preview.json()
        assert impact["targeted_assets"]
        assert impact["preserved_assets"] == []
        assert set(impact["stale_artifacts"]) >= {
            "lesson_plan",
            "render_manifest",
            "run_summary",
        }
