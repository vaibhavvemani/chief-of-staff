from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.main import create_app  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        runtime_root=tmp_path / "runtime",
        include_examples=True,
    )
    with TestClient(app) as test_client:
        yield test_client


def test_http_workspace_uses_current_attention_gate_and_targeted_asset_read(
    client: TestClient,
) -> None:
    workspace = client.get("/api/courses/coffee-live-main/workspace")

    assert workspace.status_code == 200
    body = workspace.json()
    assert body["operator_status"] == "requires_attention"
    assert body["attention"]["verification_totals"]["unsupported"] == 5
    assert body["attention"]["verification_totals"]["ungrounded"] == 1
    assert body["attention"]["verification_totals"]["unattributed"] == 3
    assert body["attention"]["blocking_total"] == 9

    asset = client.get(
        "/api/courses/coffee-live-main/content/assets/m1_s4_assess"
    )
    assert asset.status_code == 200
    assert asset.json()["id"] == "m1_s4_assess"
    assert asset.json()["asset"]["id"] == "m1_s4_assess"


def test_http_create_and_stage_commands_are_confined_and_versioned(
    client: TestClient, tmp_path: Path
) -> None:
    unsafe = client.post(
        "/api/courses",
        json={"subject": "Unsafe", "course_id": "../escape"},
    )
    assert unsafe.status_code == 400
    assert not (tmp_path / "escape").exists()

    created = client.post(
        "/api/courses",
        json={
            "subject": "Indoor herb gardening",
            "description": "A practical course for apartment renters.",
            "constraints": ["No outdoor garden beds."],
            "course_id": "herb-course",
        },
    )
    assert created.status_code == 201
    assert created.json()["workspace"]["course_id"] == "herb-course"

    answers = client.put(
        "/api/courses/herb-course/brief/answers",
        json={
            "answers": {
                "audience": "Apartment renters",
                "prior_knowledge": "No gardening experience",
                "purpose": "Grow useful herbs indoors",
                "in_scope": "light, watering, containers",
                "out_of_scope": "outdoor beds",
                "must_have_topics": "basil and mint",
            }
        },
    )
    assert answers.status_code == 200
    assert answers.json()["artifact"]["status"] == "draft"

    draft_stage = client.get("/api/courses/herb-course/stages/brief").json()
    approved = client.post(
        "/api/courses/herb-course/stages/brief/approve",
        json={"expected_checksum": draft_stage["checksum"]},
    )
    assert approved.status_code == 200
    assert approved.json()["stage"]["state"] == "approved"

    stale_reopen = client.post(
        "/api/courses/herb-course/stages/brief/reopen",
        json={"expected_checksum": draft_stage["checksum"]},
    )
    assert stale_reopen.status_code == 409

    approved_stage = client.get("/api/courses/herb-course/stages/brief").json()
    impact = client.post(
        "/api/courses/herb-course/stages/brief/impact",
        json={
            "action": "reopen",
            "expected_checksum": approved_stage["checksum"],
        },
    )
    assert impact.status_code == 200
    reopened = client.post(
        "/api/courses/herb-course/stages/brief/reopen",
        json={
            "expected_checksum": approved_stage["checksum"],
            "impact_acknowledged": True,
            "expected_impact_checksum": impact.json()["impact_checksum"],
        },
    )
    assert reopened.status_code == 200
    assert reopened.json()["stage"]["state"] == "awaiting_review"


def test_http_rejects_course_and_output_path_traversal(client: TestClient) -> None:
    unsafe_course = client.get(
        "/api/courses/%2E%2E%2Fcoffee-live-main/workspace"
    )
    unsafe_output = client.get(
        "/api/courses/coffee-live-main/outputs/%2E%2E%2FREADME.md"
    )

    assert unsafe_course.status_code in {400, 404}
    assert unsafe_output.status_code == 400
    assert unsafe_output.headers.get("content-type", "").startswith("application/json")


def test_http_stage_commands_cannot_mutate_committed_examples(client: TestClient) -> None:
    stage = client.get("/api/courses/coffee-live-main/stages/brief").json()
    response = client.post(
        "/api/courses/coffee-live-main/stages/brief/reopen",
        json={"expected_checksum": stage["checksum"]},
    )

    assert response.status_code == 403


def test_content_review_api_holds_package_until_every_asset_is_reviewed(
    client: TestClient,
) -> None:
    course_id = "review-course"
    repository = client.app.state.repository
    fixture_root = (
        REPO_ROOT
        / "examples"
        / "acceptance"
        / "coffee-acceptance"
        / "course_artifacts"
    )
    for path in fixture_root.glob("*.json"):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        artifact["course_id"] = course_id
        repository.save(artifact)

    synced = client.post(f"/api/courses/{course_id}/content/reviews/sync")

    assert synced.status_code == 200
    review = synced.json()["artifact"]
    assert review["body"]["summary"]["pending"] == review["body"]["summary"]["total"]
    assert review["body"]["summary"]["ready_for_package"] is False
    stage_states = {
        stage["slug"]: stage["state"]
        for stage in client.get(f"/api/courses/{course_id}/workspace").json()["stages"]
    }
    assert stage_states["content"] == "awaiting_review"
    assert stage_states["package"] == "stale"

    checksum = synced.json()["checksum"]
    for record in review["body"]["assets"]:
        decided = client.put(
            f"/api/courses/{course_id}/content/reviews/{record['asset_id']}",
            json={"expected_checksum": checksum, "decision": "approved"},
        )
        assert decided.status_code == 200
        checksum = decided.json()["checksum"]

    final_review = client.get(f"/api/courses/{course_id}/content/reviews").json()[
        "artifact"
    ]
    assert final_review["body"]["summary"]["pending"] == 0
    assert final_review["body"]["summary"]["ready_for_package"] is True
    final_workspace = client.get(f"/api/courses/{course_id}/workspace").json()
    assert final_workspace["operator_status"] == "pending_review"
    assert next(
        stage for stage in final_workspace["stages"] if stage["slug"] == "package"
    )["state"] == "stale"
