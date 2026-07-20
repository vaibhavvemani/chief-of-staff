from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import api.services.artifact_repository as repository_module
from agents import content_review
from api.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_ARTIFACTS = (
    REPO_ROOT / "examples" / "acceptance" / "coffee-acceptance" / "course_artifacts"
)
EDIT_SUBTOPIC = [
    {
        "op": "update_subtopic",
        "target_id": "m1_s1",
        "title": "Grind size and extraction control",
    }
]


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        runtime_root=tmp_path / "runtime",
        include_examples=False,
    )
    with TestClient(app) as value:
        yield value


def _copy_acceptance_course(
    client: TestClient,
    course_id: str,
    *,
    draft_course_model: bool = True,
) -> dict[str, Any]:
    repository = client.app.state.repository
    for path in ACCEPTANCE_ARTIFACTS.glob("*.json"):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        artifact["course_id"] = course_id
        repository.save(artifact)
    package = repository.require(course_id, "content_package")
    review = content_review.build_content_review_artifact(package)
    review["status"] = "approved"
    repository.save(review)
    model = repository.require(course_id, "course_model")
    if draft_course_model:
        checksum = repository.checksum(model)
        model["status"] = "draft"
        model = repository.save(model, expected_checksum=checksum)
    return model


def _snapshot_course(client: TestClient, course_id: str) -> dict[str, bytes]:
    root = client.app.state.repository.courses_root / course_id
    return {path.name: path.read_bytes() for path in sorted(root.glob("*.json"))}


def _preview(
    client: TestClient,
    course_id: str,
    checksum: str,
    operations: list[dict[str, Any]] | None = None,
):
    return client.post(
        f"/api/courses/{course_id}/course-model/decision/preview",
        json={
            "expected_checksum": checksum,
            "operations": operations or EDIT_SUBTOPIC,
        },
    )


def _save(
    client: TestClient,
    course_id: str,
    checksum: str,
    impact_checksum: str,
    operations: list[dict[str, Any]] | None = None,
):
    return client.put(
        f"/api/courses/{course_id}/course-model/decision",
        json={
            "expected_checksum": checksum,
            "operations": operations or EDIT_SUBTOPIC,
            "impact_acknowledged": True,
            "expected_impact_checksum": impact_checksum,
        },
    )


def test_preview_is_read_only_and_save_atomically_invalidates_exact_descendants(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    course_id = "course-model-decision"
    model = _copy_acceptance_course(client, course_id)
    repository = client.app.state.repository
    checksum = repository.checksum(model)
    before_preview = _snapshot_course(client, course_id)
    descendants = {
        artifact_type
        for artifact_type in client.app.state.catalog.downstream_artifacts({"course_model"})
        if repository.load(course_id, artifact_type) is not None
    }
    body_checksums = {
        artifact_type: repository.checksum(repository.require(course_id, artifact_type)["body"])
        for artifact_type in descendants
    }
    impact_targets: list[str] = []
    real_impact_preview = client.app.state.decisions.impact.preview

    def capture_impact_targets(*args, **kwargs):
        impact_targets.extend(kwargs["target_ids"])
        return real_impact_preview(*args, **kwargs)

    monkeypatch.setattr(
        client.app.state.decisions.impact,
        "preview",
        capture_impact_targets,
    )

    preview = _preview(client, course_id, checksum)

    assert preview.status_code == 200, preview.text
    preview_body = preview.json()
    assert _snapshot_course(client, course_id) == before_preview
    assert preview_body["candidate_artifact"]["status"] == "draft"
    assert (
        preview_body["candidate_artifact"]["body"]["modules"][0]["subtopics"][0]["title"]
        == "Grind size and extraction control"
    )
    assert preview_body["candidate_artifact"]["body"]["id_allocation"]
    assert preview_body["impact"]["stale_artifacts"] == sorted(descendants)
    assert preview_body["affected_records"]["subtopic"]["changed_ids"] == ["m1_s1"]
    assert "m1_s1" in impact_targets

    missing_acknowledgement = client.put(
        f"/api/courses/{course_id}/course-model/decision",
        json={"expected_checksum": checksum, "operations": EDIT_SUBTOPIC},
    )
    assert missing_acknowledgement.status_code == 409
    assert missing_acknowledgement.json()["error"]["code"] == ("impact_confirmation_required")
    assert _snapshot_course(client, course_id) == before_preview

    saved = _save(
        client,
        course_id,
        checksum,
        preview_body["impact"]["impact_checksum"],
    )

    assert saved.status_code == 200, saved.text
    result = saved.json()
    assert result["artifact"]["status"] == "draft"
    assert result["artifact"]["body"] == preview_body["candidate_artifact"]["body"]
    assert result["artifact"]["revision"] == model["revision"] + 1
    assert set(result["stale_artifact_types"]) == descendants
    for artifact_type in descendants:
        current = repository.require(course_id, artifact_type)
        assert current["status"] == "stale"
        assert repository.checksum(current["body"]) == body_checksums[artifact_type]
    for artifact_type in (
        "subject_request",
        "brief",
        "course_outcomes",
        "research_dossier",
        "approved_source_registry",
    ):
        filename = f"{artifact_type}.json"
        assert _snapshot_course(client, course_id)[filename] == before_preview[filename]

    stage = client.get(f"/api/courses/{course_id}/stages/course-model").json()
    action_ids = {action["id"] for action in stage["actions"]}
    assert "edit" not in action_ids
    assert "revise" not in action_ids

    approved = client.post(
        f"/api/courses/{course_id}/stages/course-model/approve",
        json={"expected_checksum": stage["checksum"]},
    )
    assert approved.status_code == 200, approved.text
    assert client.get(f"/api/courses/{course_id}/stages/course-model").json()["state"] == "approved"


def test_strict_payload_domain_failure_and_noop_preserve_every_file(
    client: TestClient,
) -> None:
    course_id = "strict-course-model"
    model = _copy_acceptance_course(client, course_id)
    repository = client.app.state.repository
    checksum = repository.checksum(model)
    before = _snapshot_course(client, course_id)

    invalid_payloads = [
        {
            "expected_checksum": checksum,
            "operations": [{"op": "replace", "body": {}}],
        },
        {
            "expected_checksum": checksum,
            "operations": [
                {
                    "op": "update_subtopic",
                    "target_id": "m1_s1",
                    "title": "Changed title",
                    "id": "client-controlled-id",
                }
            ],
        },
        {
            "expected_checksum": checksum,
            "operations": [
                {
                    "op": "add_module",
                    "client_ref": "new_module_test",
                    "position": True,
                    "title": "Invalid",
                    "purpose": "Invalid boolean position",
                    "in_scope": [],
                    "out_of_scope": [],
                    "prerequisite_module_ids": [],
                }
            ],
        },
    ]
    for payload in invalid_payloads:
        response = client.post(
            f"/api/courses/{course_id}/course-model/decision/preview",
            json=payload,
        )
        assert response.status_code == 422

    invalid_source = _preview(
        client,
        course_id,
        checksum,
        [
            {
                "op": "assign_sources",
                "target_type": "subtopic",
                "target_id": "m1_s1",
                "source_ids": ["coffee_g4"],
            }
        ],
    )
    assert invalid_source.status_code == 400
    error = invalid_source.json()["error"]
    assert error["code"] == "invalid_course_model_decision"
    assert error["issues"]
    assert any(
        "source" in f"{issue.get('code', '')} {issue.get('message', '')}".lower()
        for issue in error["issues"]
    )

    no_op = _preview(
        client,
        course_id,
        checksum,
        [{"op": "move_module", "target_id": "m1", "position": 1}],
    )
    assert no_op.status_code == 400
    assert any("noop" in issue["code"] for issue in no_op.json()["error"]["issues"])
    assert _snapshot_course(client, course_id) == before


def test_structure_rerun_preserves_deleted_id_high_water_mark(
    client: TestClient,
) -> None:
    course_id = "course-model-rerun-allocation"
    model = _copy_acceptance_course(client, course_id)
    repository = client.app.state.repository
    checksum = repository.checksum(model)
    allocate_then_delete = [
        {
            "op": "add_concept",
            "client_ref": "new_concept_ephemeral",
            "parent_id": "m1_s1",
            "position": 2,
            "name": "Ephemeral concept",
            "summary": "Allocate this ID before deliberately deleting the record.",
            "depends_on": [],
        },
        {"op": "remove_concept", "target_id": "new_concept_ephemeral"},
        {
            "op": "update_module",
            "target_id": "m1",
            "title": "Coffee Making Foundations",
        },
    ]
    preview = _preview(client, course_id, checksum, allocate_then_delete)
    assert preview.status_code == 200, preview.text
    saved = _save(
        client,
        course_id,
        checksum,
        preview.json()["impact"]["impact_checksum"],
        allocate_then_delete,
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["artifact"]["body"]["id_allocation"]["next_concept_id"] == 6

    client.app.state.stages.run(course_id, "course-model")
    rerun_model = repository.require(course_id, "course_model")
    assert rerun_model["body"]["id_allocation"]["next_concept_id"] == 6

    next_add = _preview(
        client,
        course_id,
        repository.checksum(rerun_model),
        [
            {
                "op": "add_concept",
                "client_ref": "new_concept_after_rerun",
                "parent_id": "m1_s1",
                "position": 2,
                "name": "Post-rerun concept",
                "summary": "This concept must not reuse the deleted identifier.",
                "depends_on": [],
            }
        ],
    )

    assert next_add.status_code == 200, next_add.text
    assert next_add.json()["allocated_ids"]["new_concept_after_rerun"] == "c6"


@pytest.mark.parametrize(
    "artifact_type",
    ["brief", "course_outcomes", "research_dossier", "approved_source_registry"],
)
def test_every_catalog_prerequisite_must_be_current_and_approved(
    client: TestClient,
    artifact_type: str,
) -> None:
    course_id = f"blocked-model-{artifact_type.replace('_', '-')}"
    model = _copy_acceptance_course(client, course_id)
    repository = client.app.state.repository
    prerequisite = repository.require(course_id, artifact_type)
    prerequisite_checksum = repository.checksum(prerequisite)
    prerequisite["status"] = "draft"
    repository.save(prerequisite, expected_checksum=prerequisite_checksum)
    before = _snapshot_course(client, course_id)

    response = _preview(client, course_id, repository.checksum(model))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "prerequisite_not_approved"
    assert response.json()["error"]["artifact_type"] == artifact_type
    assert _snapshot_course(client, course_id) == before


def test_approved_model_stale_checksum_lock_and_read_only_protection(
    client: TestClient,
    tmp_path: Path,
) -> None:
    approved_id = "approved-course-model"
    approved_model = _copy_acceptance_course(client, approved_id, draft_course_model=False)
    blocked = _preview(
        client,
        approved_id,
        client.app.state.repository.checksum(approved_model),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "reopen_required"

    course_id = "versioned-course-model"
    model = _copy_acceptance_course(client, course_id)
    repository = client.app.state.repository
    checksum = repository.checksum(model)
    before = _snapshot_course(client, course_id)
    stale = _preview(client, course_id, "0" * 64)
    assert stale.status_code == 409
    assert stale.json()["error"]["actual_checksum"] == checksum
    assert _snapshot_course(client, course_id) == before

    preview = _preview(client, course_id, checksum)
    assert preview.status_code == 200
    with client.app.state.jobs.locks.acquire(course_id):
        busy = _save(
            client,
            course_id,
            checksum,
            preview.json()["impact"]["impact_checksum"],
        )
    assert busy.status_code == 409
    assert _snapshot_course(client, course_id) == before

    example_app = create_app(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "example-courses",
        rendered_root=tmp_path / "example-rendered",
        runtime_root=tmp_path / "example-runtime",
        include_examples=True,
    )
    with TestClient(example_app) as example_client:
        artifact = example_client.get(
            "/api/courses/coffee-acceptance/artifacts/course_model"
        ).json()
        read_only = _preview(
            example_client,
            "coffee-acceptance",
            artifact["checksum"],
        )
    assert read_only.status_code == 403


def test_stale_impact_and_absent_artifact_race_do_not_touch_downstream(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    course_id = "course-model-races"
    model = _copy_acceptance_course(client, course_id)
    repository = client.app.state.repository
    checksum = repository.checksum(model)
    preview = _preview(client, course_id, checksum)
    assert preview.status_code == 200

    blueprint = repository.require(course_id, "blueprint")
    blueprint_checksum = repository.checksum(blueprint)
    blueprint["revision_note"] = "Concurrent downstream update."
    concurrent_blueprint = repository.save(blueprint, expected_checksum=blueprint_checksum)
    before_stale_save = _snapshot_course(client, course_id)
    stale_impact = _save(
        client,
        course_id,
        checksum,
        preview.json()["impact"]["impact_checksum"],
    )
    assert stale_impact.status_code == 409
    assert stale_impact.json()["error"]["code"] == "stale_impact_preview"
    assert repository.require(course_id, "blueprint") == concurrent_blueprint
    assert _snapshot_course(client, course_id) == before_stale_save

    fresh = _preview(client, course_id, checksum)
    assert fresh.status_code == 200
    before_race = _snapshot_course(client, course_id)
    model_path = repository.courses_root / course_id / "course_model.json"
    original_save_batch = repository.save_batch

    def disappear_during_exact_precondition(writes):
        original_bytes = model_path.read_bytes()
        model_path.unlink()
        try:
            return original_save_batch(writes)
        finally:
            model_path.write_bytes(original_bytes)

    monkeypatch.setattr(repository, "save_batch", disappear_during_exact_precondition)
    absent = _save(
        client,
        course_id,
        checksum,
        fresh.json()["impact"]["impact_checksum"],
    )
    assert absent.status_code == 409
    assert absent.json()["error"]["actual_checksum"] == "missing"
    assert _snapshot_course(client, course_id) == before_race


def test_mid_transaction_failure_restores_course_model_and_all_descendants(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    course_id = "course-model-rollback"
    model = _copy_acceptance_course(client, course_id)
    repository = client.app.state.repository
    checksum = repository.checksum(model)
    preview = _preview(client, course_id, checksum)
    assert preview.status_code == 200
    before = _snapshot_course(client, course_id)
    real_replace = repository_module.os.replace
    failed = False

    def fail_blueprint_replacement(source: str | Path, target: str | Path) -> None:
        nonlocal failed
        source_path = Path(source)
        target_path = Path(target)
        if (
            not failed
            and target_path.name == "blueprint.json"
            and source_path.name.startswith(".blueprint.")
            and ".rollback." not in source_path.name
        ):
            failed = True
            raise OSError("injected Course Model transaction failure")
        real_replace(source, target)

    monkeypatch.setattr(repository_module.os, "replace", fail_blueprint_replacement)
    with pytest.raises(OSError, match="injected Course Model transaction failure"):
        _save(
            client,
            course_id,
            checksum,
            preview.json()["impact"]["impact_checksum"],
        )

    assert failed is True
    assert _snapshot_course(client, course_id) == before


def test_course_model_approval_uses_shared_schema_and_cursor_validator(
    client: TestClient,
) -> None:
    course_id = "invalid-course-model-approval"
    _copy_acceptance_course(client, course_id)
    repository = client.app.state.repository
    invalid = repository.require(course_id, "course_model")
    checksum = repository.checksum(invalid)
    invalid["body"]["id_allocation"] = {
        "next_module_id": True,
        "next_subtopic_id": 5,
        "next_concept_id": 5,
        "next_coverage_id": 5,
    }
    invalid = repository.save(invalid, expected_checksum=checksum)
    stage = client.get(f"/api/courses/{course_id}/stages/course-model").json()

    rejected = client.post(
        f"/api/courses/{course_id}/stages/course-model/approve",
        json={"expected_checksum": stage["checksum"]},
    )

    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "approval_guard_failed"
    assert any(
        failure["code"] == "referential_integrity_failed"
        and "allocation" in failure["message"].lower()
        for failure in rejected.json()["error"]["failures"]
    )
    assert repository.require(course_id, "course_model") == invalid
