from __future__ import annotations

import json
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def guarded_client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        runtime_root=tmp_path / "runtime",
        include_examples=False,
    )
    fixture_root = (
        REPO_ROOT
        / "examples"
        / "acceptance"
        / "coffee-acceptance"
        / "course_artifacts"
    )
    for path in fixture_root.glob("*.json"):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        artifact["course_id"] = "guard-course"
        app.state.repository.save(artifact)
    with TestClient(app) as client:
        yield client


def test_content_approval_cannot_bypass_required_human_reviews(
    guarded_client: TestClient,
) -> None:
    client = guarded_client
    repository = client.app.state.repository
    package = repository.require("guard-course", "content_package")
    package_checksum = repository.checksum(package)
    package["status"] = "draft"
    repository.save(package, expected_checksum=package_checksum)
    progress = repository.require("guard-course", "content_progress")
    progress_checksum = repository.checksum(progress)
    progress["status"] = "draft"
    repository.save(progress, expected_checksum=progress_checksum)
    synced = client.post("/api/courses/guard-course/content/reviews/sync")
    assert synced.status_code == 200
    stage = client.get("/api/courses/guard-course/stages/content").json()

    response = client.post(
        "/api/courses/guard-course/stages/content/approve",
        json={"expected_checksum": stage["checksum"]},
    )

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "approval_guard_failed"
    assert {failure["code"] for failure in error["failures"]} == {
        "content_review_incomplete"
    }


def test_content_and_package_approval_reject_hard_verifier_blockers(
    guarded_client: TestClient,
) -> None:
    client = guarded_client
    repository = client.app.state.repository
    package = repository.require("guard-course", "content_package")
    checksum = repository.checksum(package)
    blocked_asset = package["body"]["subtopics"][0]["assets"][0]
    blocked_asset["claims"][0]["support"] = "unsupported"
    blocked_asset["claims"][0]["supporting_excerpt"] = None
    # A stale zero summary must not hide the current claim-level blocker.
    blocked_asset["verification"]["unsupported"] = 0
    blocked_asset["verification"]["supported"] = 1
    package["status"] = "draft"
    repository.save(package, expected_checksum=checksum)
    progress = repository.require("guard-course", "content_progress")
    progress_checksum = repository.checksum(progress)
    progress["status"] = "draft"
    repository.save(progress, expected_checksum=progress_checksum)
    client.post("/api/courses/guard-course/content/reviews/sync")

    content_stage = client.get("/api/courses/guard-course/stages/content").json()
    assert content_stage["state"] == "requires_attention"
    assert content_stage["attention_count"] >= 1
    content_approval = client.post(
        "/api/courses/guard-course/stages/content/approve",
        json={"expected_checksum": content_stage["checksum"]},
    )
    assert content_approval.status_code == 409
    assert "hard_verifier_blockers" in {
        item["code"] for item in content_approval.json()["error"]["failures"]
    }

    package = repository.require("guard-course", "content_package")
    checksum = repository.checksum(package)
    package["status"] = "approved"
    repository.save(package, expected_checksum=checksum)
    for artifact_type in ("render_manifest", "run_summary"):
        artifact = repository.require("guard-course", artifact_type)
        artifact_checksum = repository.checksum(artifact)
        artifact["status"] = "draft"
        repository.save(artifact, expected_checksum=artifact_checksum)
    package_stage = client.get("/api/courses/guard-course/stages/package").json()
    assert package_stage["state"] == "requires_attention"

    package_approval = client.post(
        "/api/courses/guard-course/stages/package/approve",
        json={"expected_checksum": package_stage["checksum"]},
    )
    assert package_approval.status_code == 409
    codes = {item["code"] for item in package_approval.json()["error"]["failures"]}
    assert "hard_verifier_blockers" in codes
    assert "content_review_incomplete" in codes


def test_package_approval_rechecks_lesson_plan_integrity(
    guarded_client: TestClient,
) -> None:
    client = guarded_client
    repository = client.app.state.repository
    lesson_plan = repository.require("guard-course", "lesson_plan")
    checksum = repository.checksum(lesson_plan)
    lesson_plan["body"]["sessions"][0]["covers"] = []
    repository.save(lesson_plan, expected_checksum=checksum)
    for artifact_type in ("render_manifest", "run_summary"):
        artifact = repository.require("guard-course", artifact_type)
        artifact_checksum = repository.checksum(artifact)
        artifact["status"] = "draft"
        repository.save(artifact, expected_checksum=artifact_checksum)

    stage = client.get("/api/courses/guard-course/stages/package").json()
    response = client.post(
        "/api/courses/guard-course/stages/package/approve",
        json={"expected_checksum": stage["checksum"]},
    )

    assert response.status_code == 409
    assert any(
        failure["code"] == "referential_integrity_failed"
        and failure["artifact_type"] == "lesson_plan"
        for failure in response.json()["error"]["failures"]
    )


def test_each_stage_guard_rejects_its_invalid_domain_state(
    guarded_client: TestClient,
) -> None:
    repository = guarded_client.app.state.repository
    guards = guarded_client.app.state.approval_guards

    cases = [
        (
            "brief",
            "brief",
            lambda body: body.update({"audience": ""}),
            "brief_input_incomplete",
        ),
        (
            "outcomes",
            "course_outcomes",
            lambda body: body["outcomes"].append(deepcopy(body["outcomes"][0])),
            "outcomes_invalid",
        ),
        (
            "research",
            "approved_source_registry",
            lambda body: body["decision"]["selected_ids"].append("missing-source"),
            "source_decision_invalid",
        ),
        (
            "course-model",
            "course_model",
            lambda body: body["modules"][0]["subtopics"][0]["concepts"][0][
                "source_ids"
            ].append("missing-source"),
            "referential_integrity_failed",
        ),
        (
            "blueprint",
            "blueprint",
            lambda body: [
                asset.update({"selection_status": "proposed"})
                for asset in body["subtopic_plans"][0]["asset_plan"]
            ],
            "referential_integrity_failed",
        ),
        (
            "lesson-plan",
            "lesson_plan",
            lambda body: body["sessions"][0].update({"covers": []}),
            "referential_integrity_failed",
        ),
    ]
    for stage, artifact_type, mutate, expected_code in cases:
        original = repository.require("guard-course", artifact_type)
        changed = deepcopy(original)
        mutate(changed["body"])
        repository.save(changed, expected_checksum=repository.checksum(original))

        codes = {
            failure.code for failure in guards.failures("guard-course", stage)
        }

        assert expected_code in codes, (stage, codes)
        current = repository.require("guard-course", artifact_type)
        repository.save(original, expected_checksum=repository.checksum(current))
