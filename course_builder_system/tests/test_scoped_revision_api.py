from __future__ import annotations

import json
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.services.local_job_runner import CourseBusy

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def revision_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.chdir(tmp_path)
    app = create_app(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        runtime_root=tmp_path / "runtime",
        include_examples=False,
    )
    fixture_root = REPO_ROOT / "examples" / "acceptance" / "coffee-acceptance" / "course_artifacts"
    for path in fixture_root.glob("*.json"):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        artifact["course_id"] = "revision-course"
        if artifact["artifact_type"] in {
            "content_package",
            "content_progress",
            "content_review",
        }:
            artifact["status"] = "draft"
        app.state.repository.save(artifact)
    app.state.decisions.sync_content_review("revision-course")
    with TestClient(app) as client:
        yield client


def _job_count(client: TestClient) -> int:
    return len(list(client.app.state.jobs.runtime_root.glob("*/jobs/*.json")))


def _wait(client: TestClient, job_url: str) -> dict:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get(job_url).json()
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(0.01)
    raise AssertionError("revision job did not finish")


def test_unsupported_and_ambiguous_revisions_never_create_a_job(
    revision_client: TestClient,
) -> None:
    client = revision_client
    course_model = client.get("/api/courses/revision-course/stages/course-model").json()
    unsupported = client.post(
        "/api/courses/revision-course/stages/course-model/revisions",
        json={
            "target_type": "subtopic",
            "target_ids": ["m1_s1"],
            "category": "scope",
            "instruction": "Change the scope",
            "mode": "deterministic",
            "expected_checksum": course_model["checksum"],
        },
    )
    assert unsupported.status_code == 409
    assert _job_count(client) == 0

    content = client.get("/api/courses/revision-course/stages/content").json()
    unknown = client.post(
        "/api/courses/revision-course/stages/content/revisions",
        json={
            "target_type": "asset",
            "target_ids": ["missing_asset"],
            "category": "clarity",
            "instruction": "Make it clearer",
            "mode": "deterministic",
            "expected_checksum": content["checksum"],
        },
    )
    assert unknown.status_code == 400
    assert unknown.json()["error"]["code"] == "ambiguous_revision"
    assert _job_count(client) == 0

    cross_subtopic = client.post(
        "/api/courses/revision-course/stages/content/revisions",
        json={
            "target_type": "asset",
            "target_ids": ["m1_s1_cc", "m1_s2_cc"],
            "category": "depth",
            "instruction": "Add examples",
            "mode": "deterministic",
            "expected_checksum": content["checksum"],
        },
    )
    assert cross_subtopic.status_code == 400
    assert _job_count(client) == 0

    legacy = client.post(
        "/api/courses/revision-course/stages/content/request-changes",
        json={"feedback": "Regenerate it", "mode": "deterministic"},
    )
    assert legacy.status_code in {404, 405}
    assert _job_count(client) == 0

    missing_checksum = client.post(
        "/api/courses/revision-course/stages/content/revisions",
        json={
            "target_type": "asset",
            "target_ids": ["m1_s4_assess"],
            "category": "clarity",
            "instruction": "Make the prompt more direct.",
            "mode": "deterministic",
        },
    )
    assert missing_checksum.status_code == 422
    assert _job_count(client) == 0


def test_scoped_content_revision_changes_only_named_asset(
    revision_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = revision_client
    repository = client.app.state.repository
    before = repository.require("revision-course", "content_package")
    before_assets = {
        asset["id"]: repository.checksum(asset)
        for subtopic in before["body"]["subtopics"]
        for asset in subtopic["assets"]
    }
    stage = client.get("/api/courses/revision-course/stages/content").json()
    impact_response = client.post(
        "/api/courses/revision-course/stages/content/impact",
        json={
            "action": "revise",
            "target_type": "asset",
            "target_ids": ["m1_s4_assess"],
            "operation_summary": "Clarify the diagnostic explanation.",
            "expected_checksum": stage["checksum"],
        },
    )
    assert impact_response.status_code == 200, impact_response.text
    impact = impact_response.json()
    assert impact["impact_level"] == "targeted"
    assert impact["targeted_assets"] == ["m1_s4_assess"]
    assert set(impact["direct_artifacts"]) == {
        "content_package",
        "content_progress",
        "content_review",
    }
    assert set(impact["stale_artifacts"]) == {"render_manifest", "run_summary"}
    assert impact["requires_rerun_stages"] == ["package"]

    without_impact = client.post(
        "/api/courses/revision-course/stages/content/revisions",
        json={
            "target_type": "asset",
            "target_ids": ["m1_s4_assess"],
            "category": "clarity",
            "instruction": "Clarify the diagnostic explanation.",
            "mode": "deterministic",
            "expected_checksum": stage["checksum"],
        },
    )
    assert without_impact.status_code == 409
    assert without_impact.json()["error"]["code"] == "impact_confirmation_required"
    assert _job_count(client) == 0

    review = repository.require("revision-course", "content_review")
    review_checksum = repository.checksum(review)
    review["revision_note"] = "A concurrent human review changed"
    repository.save(review, expected_checksum=review_checksum)
    stale_impact = client.post(
        "/api/courses/revision-course/stages/content/revisions",
        json={
            "target_type": "asset",
            "target_ids": ["m1_s4_assess"],
            "category": "clarity",
            "instruction": "Clarify the diagnostic explanation.",
            "mode": "deterministic",
            "expected_checksum": stage["checksum"],
            "impact_acknowledged": True,
            "expected_impact_checksum": impact["impact_checksum"],
        },
    )
    assert stale_impact.status_code == 409
    assert stale_impact.json()["error"]["code"] == "stale_impact_preview"
    assert _job_count(client) == 0
    impact = client.post(
        "/api/courses/revision-course/stages/content/impact",
        json={
            "action": "revise",
            "target_type": "asset",
            "target_ids": ["m1_s4_assess"],
            "operation_summary": "Clarify the diagnostic explanation.",
            "expected_checksum": stage["checksum"],
        },
    ).json()

    lock_states: list[bool] = []
    original_preview = client.app.state.impact.preview

    def observed_preview(*args, **kwargs):
        try:
            with client.app.state.jobs.locks.acquire("revision-course", blocking=False):
                lock_states.append(False)
        except CourseBusy:
            lock_states.append(True)
        return original_preview(*args, **kwargs)

    monkeypatch.setattr(client.app.state.impact, "preview", observed_preview)

    response = client.post(
        "/api/courses/revision-course/stages/content/revisions",
        json={
            "target_type": "asset",
            "target_ids": ["m1_s4_assess"],
            "category": "clarity",
            "instruction": "Clarify the diagnostic explanation.",
            "mode": "deterministic",
            "expected_checksum": stage["checksum"],
            "impact_acknowledged": True,
            "expected_impact_checksum": impact["impact_checksum"],
        },
    )
    assert response.status_code == 202, response.text
    job = _wait(client, response.json()["job_url"])
    assert job["status"] == "completed", job
    assert lock_states == [False, True]
    assert job["result"]["revision"]["changed_ids"] == ["m1_s4_assess"]

    after = repository.require("revision-course", "content_package")
    after_assets = {
        asset["id"]: repository.checksum(asset)
        for subtopic in after["body"]["subtopics"]
        for asset in subtopic["assets"]
    }
    assert after_assets["m1_s4_assess"] != before_assets["m1_s4_assess"]
    for asset_id in set(before_assets) - {"m1_s4_assess"}:
        assert after_assets[asset_id] == before_assets[asset_id]
    assert repository.require("revision-course", "lesson_plan")["status"] == "approved"
    assert repository.require("revision-course", "render_manifest")["status"] == "stale"
    assert repository.require("revision-course", "run_summary")["status"] == "stale"
