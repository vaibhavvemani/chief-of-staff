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
    fixture_root = REPO_ROOT / "examples" / "acceptance" / "coffee-acceptance" / "course_artifacts"
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
    record_id = synced.json()["artifact"]["body"]["assets"][0]["asset_id"]
    missing_checksum = client.put(
        f"/api/courses/guard-course/content/reviews/{record_id}",
        json={"decision": "approved"},
    )
    assert missing_checksum.status_code == 422
    stage = client.get("/api/courses/guard-course/stages/content").json()

    response = client.post(
        "/api/courses/guard-course/stages/content/approve",
        json={"expected_checksum": stage["checksum"]},
    )

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "approval_guard_failed"
    assert {failure["code"] for failure in error["failures"]} == {"content_review_incomplete"}


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


def test_package_approval_rejects_selected_rendered_asset_mismatch_without_mutation(
    guarded_client: TestClient,
) -> None:
    client = guarded_client
    repository = client.app.state.repository
    manifest = repository.require("guard-course", "render_manifest")
    manifest_checksum = repository.checksum(manifest)
    rendered_assets = manifest["body"]["paths"]["assets"]
    omitted_asset_id = next(iter(rendered_assets))
    del rendered_assets[omitted_asset_id]
    manifest["status"] = "draft"
    manifest = repository.save(manifest, expected_checksum=manifest_checksum)
    summary = repository.require("guard-course", "run_summary")
    summary_checksum = repository.checksum(summary)
    summary["status"] = "draft"
    repository.save(summary, expected_checksum=summary_checksum)
    before = repository.checksum(manifest)

    package_stage = client.get("/api/courses/guard-course/stages/package").json()
    # A pure render reconciliation failure has no verifier attention count, so the
    # lifecycle remains at its human checkpoint while the projected approval action
    # is disabled by the backend-owned package guard.
    assert package_stage["state"] == "awaiting_review"
    assert "package_asset_mismatch" in {
        failure["code"] for failure in package_stage["approval_failures"]
    }
    approve_action = next(
        action for action in package_stage["actions"] if action["id"] == "approve"
    )
    assert approve_action["enabled"] is False
    response = client.post(
        "/api/courses/guard-course/stages/package/approve",
        json={"expected_checksum": package_stage["checksum"]},
    )

    assert response.status_code == 409
    failures = response.json()["error"]["failures"]
    mismatch = next(
        failure for failure in failures if failure["code"] == "package_asset_mismatch"
    )
    assert mismatch["artifact_type"] == "render_manifest"
    assert omitted_asset_id in mismatch["record_ids"]
    assert (
        repository.checksum(repository.require("guard-course", "render_manifest"))
        == before
    )
    assert repository.require("guard-course", "render_manifest")["status"] == "draft"


def test_synchronizing_changed_content_review_stales_package_without_body_loss(
    guarded_client: TestClient,
) -> None:
    client = guarded_client
    repository = client.app.state.repository
    before = {
        artifact_type: repository.require("guard-course", artifact_type)
        for artifact_type in ("render_manifest", "run_summary")
    }
    body_checksums = {
        artifact_type: repository.checksum(artifact["body"])
        for artifact_type, artifact in before.items()
    }
    for artifact_type in ("content_package", "content_progress"):
        artifact = repository.require("guard-course", artifact_type)
        checksum = repository.checksum(artifact)
        artifact["status"] = "draft"
        repository.save(artifact, expected_checksum=checksum)

    response = client.post("/api/courses/guard-course/content/reviews/sync")

    assert response.status_code == 200, response.text
    for artifact_type in ("render_manifest", "run_summary"):
        artifact = repository.require("guard-course", artifact_type)
        assert artifact["status"] == "stale"
        assert repository.checksum(artifact["body"]) == body_checksums[artifact_type]


def test_approved_content_review_cannot_change_without_reopen(
    guarded_client: TestClient,
) -> None:
    client = guarded_client
    stage = client.get("/api/courses/guard-course/stages/content").json()
    assert stage["state"] == "approved"

    response = client.post("/api/courses/guard-course/content/reviews/sync")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "unsupported_action"


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
            lambda body: body["modules"][0]["subtopics"][0]["concepts"][0]["source_ids"].append(
                "missing-source"
            ),
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

        codes = {failure.code for failure in guards.failures("guard-course", stage)}

        assert expected_code in codes, (stage, codes)
        current = repository.require("guard-course", artifact_type)
        repository.save(original, expected_checksum=repository.checksum(current))
