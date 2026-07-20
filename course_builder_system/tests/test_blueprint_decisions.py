from __future__ import annotations

import json
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_ARTIFACTS = (
    REPO_ROOT / "examples" / "acceptance" / "coffee-acceptance" / "course_artifacts"
)


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


def _copy_acceptance_course(client: TestClient, course_id: str) -> dict:
    repository = client.app.state.repository
    for path in ACCEPTANCE_ARTIFACTS.glob("*.json"):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        artifact["course_id"] = course_id
        repository.save(artifact)
    blueprint = repository.require(course_id, "blueprint")
    blueprint["status"] = "draft"
    return repository.save(
        blueprint,
        expected_checksum=repository.checksum(repository.require(course_id, "blueprint")),
    )


def test_blueprint_decision_saves_exact_defaults_exceptions_and_invalidates_content(
    client: TestClient,
) -> None:
    course_id = "blueprint-decision"
    blueprint = _copy_acceptance_course(client, course_id)
    repository = client.app.state.repository
    plans = blueprint["body"]["subtopic_plans"]
    first_id = plans[0]["subtopic_id"]
    second_id = plans[1]["subtopic_id"]
    course_model = repository.require(course_id, "course_model")
    approved_sources = {
        subtopic["id"]: subtopic["approved_source_ids"]
        for module in course_model["body"]["modules"]
        for subtopic in module["subtopics"]
    }

    response = client.put(
        f"/api/courses/{course_id}/blueprint/decision",
        json={
            "expected_checksum": repository.checksum(blueprint),
            "default_asset_types": ["course_content", "summary", "activities"],
            "default_depth": {
                "target_learning_minutes": 30,
                "target_word_range": {"minimum": 900, "target": 1300, "maximum": 1700},
                "required_example_count": 2,
            },
            "selected_asset_types": {
                first_id: ["course_content", "assessment"],
            },
            "depth_overrides": {second_id: {"required_example_count": 4}},
            "anchor_waivers": [],
            "rationale": "Use a practice-led baseline with one focused exception.",
        },
    )

    assert response.status_code == 200, response.text
    artifact = response.json()["artifact"]
    assert artifact["status"] == "draft"
    assert artifact["produced_by_step"] == "human"
    assert artifact["body"]["course_defaults"]["default_asset_types"] == [
        "course_content",
        "summary",
        "activities",
    ]
    first = next(
        plan for plan in artifact["body"]["subtopic_plans"] if plan["subtopic_id"] == first_id
    )
    second = next(
        plan for plan in artifact["body"]["subtopic_plans"] if plan["subtopic_id"] == second_id
    )
    assert {
        asset["asset_type"]
        for asset in first["asset_plan"]
        if asset["selection_status"] == "selected"
    } == {"course_content", "assessment"}
    assert second["depth_budget"]["required_example_count"] == 4
    for plan in artifact["body"]["subtopic_plans"]:
        for asset in plan["asset_plan"]:
            expected = (
                approved_sources[plan["subtopic_id"]]
                if asset["selection_status"] == "selected"
                else []
            )
            assert asset["source_ids"] == expected
    assert repository.require(course_id, "content_package")["status"] == "stale"
    assert repository.require(course_id, "lesson_plan")["status"] == "stale"


@pytest.mark.parametrize(
    "changes, expected_status",
    [
        ({"selected_asset_types": {"missing": ["course_content"]}}, 400),
        ({"selected_asset_types": {"m1_s1": []}}, 422),
        ({"default_asset_types": ["course_content", "video"]}, 422),
        (
            {
                "selected_asset_types": {"m1_s1": ["assessment"]},
                "anchor_waivers": [],
            },
            400,
        ),
        (
            {
                "depth_overrides": {
                    "m1_s1": {
                        "target_word_range": {
                            "minimum": 1200,
                            "target": 1000,
                            "maximum": 1100,
                        }
                    }
                }
            },
            422,
        ),
    ],
)
def test_blueprint_decision_rejects_invalid_contracts_without_mutation(
    client: TestClient,
    changes: dict,
    expected_status: int,
) -> None:
    course_id = "blueprint-invalid"
    blueprint = _copy_acceptance_course(client, course_id)
    repository = client.app.state.repository
    checksum = repository.checksum(blueprint)

    response = client.put(
        f"/api/courses/{course_id}/blueprint/decision",
        json={
            "expected_checksum": checksum,
            "rationale": "Test a rejected Blueprint decision.",
            **changes,
        },
    )

    assert response.status_code == expected_status, response.text
    assert repository.checksum(repository.require(course_id, "blueprint")) == checksum


def test_blueprint_decision_requires_current_checksum_and_reopen(client: TestClient) -> None:
    course_id = "blueprint-version"
    blueprint = _copy_acceptance_course(client, course_id)
    repository = client.app.state.repository
    current_checksum = repository.checksum(blueprint)
    command = {
        "expected_checksum": "stale-checksum",
        "selected_asset_types": {"m1_s1": ["course_content", "activities"]},
    }

    stale = client.put(f"/api/courses/{course_id}/blueprint/decision", json=command)
    assert stale.status_code == 409
    assert repository.checksum(repository.require(course_id, "blueprint")) == current_checksum

    approved = repository.require(course_id, "blueprint")
    approved["status"] = "approved"
    approved = repository.save(approved, expected_checksum=current_checksum)
    command["expected_checksum"] = repository.checksum(approved)
    blocked = client.put(f"/api/courses/{course_id}/blueprint/decision", json=command)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "reopen_required"


@pytest.mark.parametrize("course_model_status", ["draft", "stale"])
def test_blueprint_decision_rejects_noncurrent_course_model_without_mutation(
    client: TestClient,
    course_model_status: str,
) -> None:
    course_id = f"blueprint-prerequisite-{course_model_status}"
    blueprint = _copy_acceptance_course(client, course_id)
    repository = client.app.state.repository
    course_model = repository.require(course_id, "course_model")
    course_model["status"] = course_model_status
    repository.save(
        course_model,
        expected_checksum=repository.checksum(
            repository.require(course_id, "course_model")
        ),
    )
    before = deepcopy(repository.require(course_id, "blueprint"))

    response = client.put(
        f"/api/courses/{course_id}/blueprint/decision",
        json={
            "expected_checksum": repository.checksum(blueprint),
            "selected_asset_types": {
                "m1_s1": ["course_content", "activities"],
            },
        },
    )

    assert response.status_code == 409, response.text
    assert response.json()["error"] == {
        "message": "course_model must be approved and current before changing blueprint",
        "code": "prerequisite_not_approved",
        "stage": "blueprint",
        "artifact_type": "course_model",
    }
    assert repository.require(course_id, "blueprint") == before


def test_blueprint_decision_rejects_non_authoritative_source_route_without_mutation(
    client: TestClient,
) -> None:
    course_id = "blueprint-source-authority"
    blueprint = _copy_acceptance_course(client, course_id)
    repository = client.app.state.repository
    registry = repository.require(course_id, "approved_source_registry")
    registry["body"]["decision"]["selected_ids"] = ["coffee_g1"]
    registry["body"]["decision"]["approved_ids"] = ["coffee_g1"]
    registry["body"]["decision"]["rejected_ids"] = ["coffee_g2", "coffee_g4"]
    repository.save(
        registry,
        expected_checksum=repository.checksum(
            repository.require(course_id, "approved_source_registry")
        ),
    )
    before = deepcopy(repository.require(course_id, "blueprint"))

    response = client.put(
        f"/api/courses/{course_id}/blueprint/decision",
        json={
            "expected_checksum": repository.checksum(blueprint),
            "selected_asset_types": {
                "m1_s1": ["course_content", "activities"],
            },
        },
    )

    assert response.status_code == 400, response.text
    error = response.json()["error"]
    assert error["code"] == "invalid_course_model_decision"
    assert {issue["code"] for issue in error["issues"]} >= {
        "approved_source_registry_decision_mismatch",
        "source_not_assignable",
    }
    assert repository.require(course_id, "blueprint") == before


def test_blueprint_decision_rejects_contentless_approved_source_without_mutation(
    client: TestClient,
) -> None:
    course_id = "blueprint-contentless-source"
    blueprint = _copy_acceptance_course(client, course_id)
    repository = client.app.state.repository
    registry = repository.require(course_id, "approved_source_registry")
    next(
        source
        for source in registry["body"]["source_registry"]
        if source["id"] == "coffee_g2"
    )["content_ref"] = ""
    repository.save(
        registry,
        expected_checksum=repository.checksum(
            repository.require(course_id, "approved_source_registry")
        ),
    )
    before = deepcopy(repository.require(course_id, "blueprint"))

    response = client.put(
        f"/api/courses/{course_id}/blueprint/decision",
        json={
            "expected_checksum": repository.checksum(blueprint),
            "depth_overrides": {
                "m1_s4": {"required_example_count": 5},
            },
        },
    )

    assert response.status_code == 400, response.text
    error = response.json()["error"]
    assert error["code"] == "invalid_course_model_decision"
    assert {issue["code"] for issue in error["issues"]} >= {
        "approved_source_registry_record_invalid",
        "source_not_assignable",
    }
    assert repository.require(course_id, "blueprint") == before
