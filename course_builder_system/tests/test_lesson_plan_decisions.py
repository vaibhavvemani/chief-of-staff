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
    lesson_plan = repository.require(course_id, "lesson_plan")
    checksum = repository.checksum(lesson_plan)
    lesson_plan["status"] = "draft"
    return repository.save(lesson_plan, expected_checksum=checksum)


def _put(client: TestClient, course_id: str, lesson_plan: dict, **decision: object):
    return client.put(
        f"/api/courses/{course_id}/lesson-plan/decision",
        json={
            "expected_checksum": client.app.state.repository.checksum(lesson_plan),
            "rationale": "Adjust delivery while preserving exact coverage.",
            **decision,
        },
    )


def _covered(body: dict) -> list[str]:
    return [cover["subtopic_id"] for session in body["sessions"] for cover in session["covers"]]


def test_lesson_plan_decision_applies_constraints_modes_and_exact_coverage(
    client: TestClient,
) -> None:
    course_id = "lesson-plan-decision"
    lesson_plan = _copy_acceptance_course(client, course_id)
    repository = client.app.state.repository

    response = _put(
        client,
        course_id,
        lesson_plan,
        constraints={
            "max_session_hours": 0.5,
            "default_mode": "live",
            "calendar_dates": ["2026-08-03", "2026-08-10"],
            "instructor_count": 1,
            "delivery_platform": "Studio classroom",
        },
        operations=[
            {"op": "set_mode", "target_id": "m1_s4", "value": "self_study"},
        ],
    )

    assert response.status_code == 200, response.text
    artifact = response.json()["artifact"]
    body = artifact["body"]
    assert artifact["status"] == "draft"
    assert artifact["produced_by_step"] == "human"
    assert body["session_constraints"] == {
        "max_session_hours": 0.5,
        "default_mode": "live",
        "calendar_dates": ["2026-08-03", "2026-08-10"],
        "instructor_count": 1,
        "delivery_platform": "Studio classroom",
    }
    assert body["unresolved_session_constraints"] == []
    assert len(body["sessions"]) == 4
    assert all(session["duration_minutes"] <= 30 for session in body["sessions"])
    assert _covered(body) == ["m1_s1", "m1_s2", "m1_s3", "m1_s4"]
    modes = {
        cover["subtopic_id"]: cover["mode"]
        for session in body["sessions"]
        for cover in session["covers"]
    }
    assert modes == {
        "m1_s1": "live",
        "m1_s2": "live",
        "m1_s3": "live",
        "m1_s4": "self_study",
    }
    assert repository.require(course_id, "render_manifest")["status"] == "stale"
    assert repository.require(course_id, "run_summary")["status"] == "stale"


def test_bounded_mode_change_preserves_every_unaffected_session_body(
    client: TestClient,
) -> None:
    course_id = "lesson-plan-bounded"
    lesson_plan = _copy_acceptance_course(client, course_id)
    first = _put(
        client,
        course_id,
        lesson_plan,
        constraints={"max_session_hours": 0.5},
        operations=[],
    )
    assert first.status_code == 200, first.text
    regrouped = first.json()["artifact"]
    before_sessions = {
        session["id"]: deepcopy(session) for session in regrouped["body"]["sessions"]
    }

    second = _put(
        client,
        course_id,
        regrouped,
        operations=[
            {"op": "set_mode", "target_id": "m1_s2", "value": "self_study"},
        ],
    )

    assert second.status_code == 200, second.text
    decided = second.json()["artifact"]
    target_session = next(
        session
        for session in decided["body"]["sessions"]
        if any(cover["subtopic_id"] == "m1_s2" for cover in session["covers"])
    )
    for session in decided["body"]["sessions"]:
        if session["id"] != target_session["id"]:
            assert session == before_sessions[session["id"]]
    assert decided["body"]["decision_log"][-1]["affected_session_ids"] == [target_session["id"]]


def test_duration_change_reports_only_sessions_whose_bodies_change(
    client: TestClient,
) -> None:
    course_id = "lesson-plan-duration-scope"
    lesson_plan = _copy_acceptance_course(client, course_id)
    original_session = deepcopy(lesson_plan["body"]["sessions"][0])

    response = _put(
        client,
        course_id,
        lesson_plan,
        constraints={"max_session_hours": 1.5},
        operations=[],
    )

    assert response.status_code == 200, response.text
    body = response.json()["artifact"]["body"]
    assert body["sessions"] == [original_session]
    assert body["decision_log"][-1]["affected_session_ids"] == []


def test_move_and_reorder_operations_preserve_exact_once_coverage(
    client: TestClient,
) -> None:
    course_id = "lesson-plan-sequence"
    lesson_plan = _copy_acceptance_course(client, course_id)
    regroup = _put(
        client,
        course_id,
        lesson_plan,
        constraints={"max_session_hours": 1},
        operations=[],
    )
    assert regroup.status_code == 200, regroup.text
    regrouped = regroup.json()["artifact"]
    sessions = regrouped["body"]["sessions"]
    assert len(sessions) == 2

    moved = _put(
        client,
        course_id,
        regrouped,
        operations=[
            {
                "op": "move_segment",
                "target_id": "m1_s3",
                "value": sessions[1]["id"],
                "position": 1,
            }
        ],
    )
    assert moved.status_code == 200, moved.text
    moved_artifact = moved.json()["artifact"]
    assert _covered(moved_artifact["body"]) == [
        "m1_s1",
        "m1_s2",
        "m1_s3",
        "m1_s4",
    ]
    assert moved_artifact["body"]["sequence_policy"] == "operator_defined"

    current_ids = [session["id"] for session in moved_artifact["body"]["sessions"]]
    reordered = _put(
        client,
        course_id,
        moved_artifact,
        operations=[
            {"op": "reorder_session", "session_ids": list(reversed(current_ids))},
        ],
    )
    assert reordered.status_code == 200, reordered.text
    reordered_body = reordered.json()["artifact"]["body"]
    assert [session["id"] for session in reordered_body["sessions"]] == list(reversed(current_ids))
    assert set(_covered(reordered_body)) == {"m1_s1", "m1_s2", "m1_s3", "m1_s4"}
    assert len(_covered(reordered_body)) == 4


def test_retired_session_ids_are_never_reallocated(
    client: TestClient,
) -> None:
    course_id = "lesson-plan-session-ids"
    lesson_plan = _copy_acceptance_course(client, course_id)
    regroup = _put(
        client,
        course_id,
        lesson_plan,
        constraints={"max_session_hours": 0.5},
        operations=[],
    )
    assert regroup.status_code == 200, regroup.text
    regrouped = regroup.json()["artifact"]
    sessions = regrouped["body"]["sessions"]
    assert [session["id"] for session in sessions] == ["sess2", "sess3", "sess4", "sess5"]
    assert regrouped["body"]["session_id_cursor"] == 5

    # Preserve a valid historical layout with spare capacity. The cursor is
    # canonical state and must survive independently of currently active IDs.
    repository = client.app.state.repository
    regrouped_checksum = repository.checksum(regrouped)
    regrouped["body"]["session_constraints"]["max_session_hours"] = 1.0
    regrouped = repository.save(regrouped, expected_checksum=regrouped_checksum)

    moved = _put(
        client,
        course_id,
        regrouped,
        operations=[
            {
                "op": "move_segment",
                "target_id": "m1_s4",
                "value": "sess4",
                "position": 2,
            }
        ],
    )
    assert moved.status_code == 200, moved.text
    moved_artifact = moved.json()["artifact"]
    assert "sess5" not in {session["id"] for session in moved_artifact["body"]["sessions"]}
    assert moved_artifact["body"]["session_id_cursor"] == 5

    regroup_again = _put(
        client,
        course_id,
        moved_artifact,
        constraints={"max_session_hours": 1.5},
        operations=[],
    )
    assert regroup_again.status_code == 200, regroup_again.text
    final_body = regroup_again.json()["artifact"]["body"]
    assert [session["id"] for session in final_body["sessions"]] == ["sess6"]
    assert final_body["session_id_cursor"] == 6


@pytest.mark.parametrize(
    "decision, expected_status",
    [
        (
            {"operations": [{"op": "set_mode", "target_id": "missing", "value": "live"}]},
            400,
        ),
        ({"constraints": {"max_session_hours": 0.1}, "operations": []}, 400),
        (
            {"operations": [{"op": "reorder_session", "session_ids": ["sess1", "missing"]}]},
            400,
        ),
        (
            {"operations": [{"op": "set_mode", "target_id": "m1_s1", "value": "live"}]},
            400,
        ),
        ({"constraints": {}, "operations": []}, 422),
        ({"constraints": {"max_session_hours": 1.0, "unknown": True}}, 422),
    ],
)
def test_invalid_lesson_plan_decisions_do_not_mutate(
    client: TestClient,
    decision: dict,
    expected_status: int,
) -> None:
    course_id = "lesson-plan-invalid"
    lesson_plan = _copy_acceptance_course(client, course_id)
    repository = client.app.state.repository
    before = deepcopy(repository.require(course_id, "lesson_plan"))

    response = _put(client, course_id, lesson_plan, **decision)

    assert response.status_code == expected_status, response.text
    assert repository.require(course_id, "lesson_plan") == before


@pytest.mark.parametrize("upstream_status", ["draft", "stale"])
def test_lesson_plan_decision_requires_current_prerequisites_without_mutation(
    client: TestClient,
    upstream_status: str,
) -> None:
    course_id = f"lesson-plan-prerequisite-{upstream_status}"
    lesson_plan = _copy_acceptance_course(client, course_id)
    repository = client.app.state.repository
    content = repository.require(course_id, "content_package")
    content_checksum = repository.checksum(content)
    content["status"] = upstream_status
    repository.save(content, expected_checksum=content_checksum)
    before = deepcopy(repository.require(course_id, "lesson_plan"))

    response = _put(
        client,
        course_id,
        lesson_plan,
        constraints={"max_session_hours": 1.0},
        operations=[],
    )

    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "prerequisite_not_approved"
    assert repository.require(course_id, "lesson_plan") == before


def test_lesson_plan_decision_requires_current_checksum_and_reopen(
    client: TestClient,
) -> None:
    course_id = "lesson-plan-version"
    _copy_acceptance_course(client, course_id)
    repository = client.app.state.repository
    before = deepcopy(repository.require(course_id, "lesson_plan"))
    payload = {
        "expected_checksum": "stale-checksum",
        "constraints": {"max_session_hours": 1.0},
        "operations": [],
    }

    stale = client.put(f"/api/courses/{course_id}/lesson-plan/decision", json=payload)
    assert stale.status_code == 409
    assert repository.require(course_id, "lesson_plan") == before

    approved = repository.require(course_id, "lesson_plan")
    checksum = repository.checksum(approved)
    approved["status"] = "approved"
    approved = repository.save(approved, expected_checksum=checksum)
    payload["expected_checksum"] = repository.checksum(approved)
    blocked = client.put(f"/api/courses/{course_id}/lesson-plan/decision", json=payload)
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "reopen_required"


def test_lesson_plan_reconciles_exact_coverage_with_course_model_authority(
    client: TestClient,
) -> None:
    course_id = "lesson-plan-authority"
    _copy_acceptance_course(client, course_id)
    repository = client.app.state.repository

    for artifact_type, collection in (
        ("blueprint", "subtopic_plans"),
        ("content_package", "subtopics"),
    ):
        artifact = repository.require(course_id, artifact_type)
        checksum = repository.checksum(artifact)
        artifact["body"][collection] = [
            item for item in artifact["body"][collection] if item["subtopic_id"] != "m1_s4"
        ]
        repository.save(artifact, expected_checksum=checksum)

    lesson_plan = repository.require(course_id, "lesson_plan")
    checksum = repository.checksum(lesson_plan)
    lesson_plan["body"]["sessions"][0]["covers"] = [
        cover
        for cover in lesson_plan["body"]["sessions"][0]["covers"]
        if cover["subtopic_id"] != "m1_s4"
    ]
    lesson_plan["body"]["sessions"][0]["duration_minutes"] = 60
    lesson_plan["body"]["sessions"][0]["duration_hours"] = 1.0
    lesson_plan["body"]["coverage_summary"] = {
        "expected_subtopic_ids": ["m1_s1", "m1_s2", "m1_s3"],
        "covered_subtopic_ids": ["m1_s1", "m1_s2", "m1_s3"],
        "total_duration_minutes": 60,
    }
    lesson_plan = repository.save(lesson_plan, expected_checksum=checksum)
    before = deepcopy(lesson_plan)

    response = _put(
        client,
        course_id,
        lesson_plan,
        operations=[
            {"op": "set_mode", "target_id": "m1_s2", "value": "self_study"},
        ],
    )
    assert response.status_code == 400, response.text
    assert "do not exactly match Course Model order" in response.text
    assert repository.require(course_id, "lesson_plan") == before

    stage = client.get(f"/api/courses/{course_id}/stages/lesson-plan").json()
    approval = client.post(
        f"/api/courses/{course_id}/stages/lesson-plan/approve",
        json={"expected_checksum": stage["checksum"]},
    )
    assert approval.status_code == 409, approval.text
    assert "do not exactly match Course Model order" in approval.text
    assert repository.require(course_id, "lesson_plan") == before
