from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agents import intake
from api.main import create_app
from interaction import QuestionSpec
from orchestrator import make_artifact
from tests.schema_check import validate

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def _create(client: TestClient, course_id: str = "guided-intake") -> dict:
    response = client.post(
        "/api/courses",
        json={"subject": "Coffee making", "course_id": course_id},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _questions(client: TestClient, course_id: str = "guided-intake") -> dict:
    response = client.get(f"/api/courses/{course_id}/brief/questions")
    assert response.status_code == 200, response.text
    return response.json()


def _answer(
    client: TestClient, round_data: dict, answers: list[dict], course_id: str = "guided-intake"
) -> dict:
    response = client.put(
        f"/api/courses/{course_id}/brief/answers",
        json={"answers": answers, "expected_checksum": round_data["checksum"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _assert_outcomes_decision_blocked(client: TestClient, course_id: str) -> None:
    response = client.put(
        f"/api/courses/{course_id}/outcomes/decision",
        json={
            "expected_checksum": "missing",
            "selected_ids": [],
            "edits": {},
            "additions": [],
            "priority_order": [],
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "prerequisite_not_approved"
    assert client.get(f"/api/courses/{course_id}/artifacts/course_outcomes").status_code == 404


def _complete_blended_intake(client: TestClient, course_id: str = "guided-intake") -> dict:
    first = _questions(client, course_id)
    _answer(
        client,
        first,
        [
            {"question_id": "brief_audience", "value": "General"},
            {"question_id": "brief_prior_knowledge", "accept_default": True},
            {
                "question_id": "brief_purpose",
                "value": "Brew balanced coffee and diagnose taste problems.",
            },
            {"question_id": "brief_level", "accept_default": True},
            {"question_id": "brief_duration", "accept_default": True},
        ],
        course_id,
    )
    second = _questions(client, course_id)
    _answer(
        client,
        second,
        [
            {"question_id": "brief_modality", "value": "blended"},
            {"question_id": "brief_language", "accept_default": True},
        ],
        course_id,
    )
    additional = _questions(client, course_id)
    assert len(additional["questions"]) <= 3
    assert {item["id"] for item in additional["questions"]} == {
        "brief_live_teaching_constraints",
        "brief_followup_audience_gap_audience_generic",
    }
    return _answer(
        client,
        additional,
        [
            {"question_id": "brief_live_teaching_constraints", "skip": True},
            {
                "question_id": "brief_followup_audience_gap_audience_generic",
                "value": "Adults making coffee at home with little technical knowledge.",
            },
        ],
        course_id,
    )


def test_new_course_persists_normalized_needs_input_brief_and_typed_questions(
    client: TestClient,
) -> None:
    created = _create(client)

    assert created["workspace"]["stages"][0]["state"] == "needs_input"
    assert created["workspace"]["stages"][1]["state"] == "locked"
    round_data = _questions(client)
    assert len(round_data["questions"]) == 5
    assert round_data["round_kind"] == "mandatory"
    question = round_data["questions"][0]
    assert set(question) == {
        "id",
        "field",
        "prompt",
        "rationale",
        "answer_type",
        "options",
        "default",
        "required",
        "allow_skip",
        "visibility",
    }
    assert round_data["intake_state"]["explicit_fields"] == ["subject"]
    assert round_data["intake_state"]["accepted_default_fields"] == []
    assert "language" in round_data["intake_state"]["unresolved_required_fields"]


def test_creation_boundary_normalizes_seed_values_into_schema_valid_artifacts(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/courses",
        json={
            "subject": "  Coffee making  ",
            "description": "  Brew reliably with home equipment.  ",
            "constraints": ["  Use home equipment.  ", "Use home equipment."],
            "known_source_locators": [
                "  https://example.test/coffee-guide  ",
                "https://example.test/coffee-guide",
            ],
            "course_id": "normalized-seed",
        },
    )
    assert response.status_code == 201, response.text

    subject_request = client.get(
        "/api/courses/normalized-seed/artifacts/subject_request"
    ).json()["artifact"]
    brief = client.get("/api/courses/normalized-seed/artifacts/brief").json()["artifact"]
    assert subject_request["body"] == {
        "subject": "Coffee making",
        "description": "Brew reliably with home equipment.",
        "constraints": ["Use home equipment."],
        "known_source_locators": ["https://example.test/coffee-guide"],
    }
    assert brief["body"]["purpose"] == "Brew reliably with home equipment."
    assert brief["body"]["constraints"] == ["Use home equipment."]
    assert brief["body"]["available_materials"] == [
        "https://example.test/coffee-guide"
    ]
    assert "purpose" in brief["body"]["intake_state"]["explicit_fields"]

    subject_schema = json.loads(
        (REPO_ROOT / "schemas" / "subject_request.v0.2.schema.json").read_text(
            encoding="utf-8"
        )
    )
    brief_schema = json.loads(
        (REPO_ROOT / "schemas" / "brief.v0.2.schema.json").read_text(encoding="utf-8")
    )
    assert validate(subject_request, subject_schema) == []
    assert validate(brief, brief_schema) == []


def test_detailed_starting_request_projects_complete_without_redundant_questions(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/courses",
        json={
            "subject": "Coffee making",
            "course_id": "detailed-intake",
            "brief": {
                "audience": "Adults learning to brew coffee at home",
                "purpose": "Brew balanced coffee and diagnose common taste problems.",
                "prior_knowledge": "No prior coffee knowledge required.",
                "level": "beginner",
                "duration": "3 hours",
                "modality": "self_paced",
                "language": "English",
            },
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["workspace"]["stages"][0]["state"] == "awaiting_review"
    round_data = _questions(client, "detailed-intake")
    assert round_data["round_kind"] == "complete"
    assert round_data["questions"] == []
    state = round_data["intake_state"]
    assert state["unresolved_required_fields"] == []
    assert state["accepted_default_fields"] == []
    assert set(state["explicit_fields"]) >= {
        "audience",
        "purpose",
        "prior_knowledge",
        "level",
        "duration",
        "modality",
        "language",
    }


def test_invalid_detailed_request_is_rejected_before_course_creation(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/courses",
        json={
            "subject": "Coffee making",
            "course_id": "invalid-detailed-intake",
            "brief": {"invented_field": ""},
        },
    )

    assert response.status_code == 400
    assert client.get(
        "/api/courses/invalid-detailed-intake/workspace"
    ).status_code == 404


@pytest.mark.parametrize(
    "invalid_seed",
    [
        {"subject": "x" * 201},
        {"description": "x" * 701},
        {"constraints": ["x" * 301]},
        {"known_source_locators": ["x" * 1001]},
        {"constraints": ["   "]},
        {"known_source_locators": ["\n\t"]},
    ],
)
def test_creation_boundary_rejects_seed_values_that_cannot_form_a_valid_brief(
    client: TestClient,
    invalid_seed: dict,
) -> None:
    payload = {"subject": "Coffee making", "course_id": "invalid-seed", **invalid_seed}
    response = client.post("/api/courses", json=payload)

    assert response.status_code == 422, response.text


def test_whitespace_only_description_remains_an_explicitly_unresolved_purpose(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/courses",
        json={
            "subject": "Coffee making",
            "description": " \n\t ",
            "course_id": "blank-description",
        },
    )
    assert response.status_code == 201, response.text

    brief = client.get("/api/courses/blank-description/artifacts/brief").json()["artifact"]
    round_data = _questions(client, "blank-description")
    assert brief["body"]["purpose"] == "Build practical working knowledge of Coffee making."
    assert "purpose" not in brief["body"]["intake_state"]["explicit_fields"]
    assert "brief_purpose" in {question["id"] for question in round_data["questions"]}


def test_answer_rounds_merge_refresh_conditionals_and_defaults_without_reset(
    client: TestClient,
) -> None:
    _create(client)
    first = _questions(client)
    saved_first = _answer(
        client,
        first,
        [
            {"question_id": "brief_audience", "value": "General"},
            {"question_id": "brief_prior_knowledge", "accept_default": True},
            {
                "question_id": "brief_purpose",
                "value": "Brew balanced coffee and diagnose taste problems.",
            },
            {"question_id": "brief_level", "accept_default": True},
            {"question_id": "brief_duration", "accept_default": True},
        ],
    )
    assert saved_first["artifact"]["body"]["audience"] == "General"

    refreshed = client.get("/api/courses/guided-intake/stages/brief").json()
    assert refreshed["artifacts"][0]["body"]["audience"] == "General"
    second = _questions(client)
    assert [item["id"] for item in second["questions"]] == [
        "brief_modality",
        "brief_language",
    ]
    _answer(
        client,
        second,
        [
            {"question_id": "brief_modality", "value": "blended"},
            {"question_id": "brief_language", "accept_default": True},
        ],
    )
    additional = _questions(client)
    ids = {item["id"] for item in additional["questions"]}
    assert "brief_live_teaching_constraints" in ids
    assert "brief_followup_audience_gap_audience_generic" in ids

    completed = _answer(
        client,
        additional,
        [
            {"question_id": "brief_live_teaching_constraints", "skip": True},
            {
                "question_id": "brief_followup_audience_gap_audience_generic",
                "value": "Adults making coffee at home with little technical knowledge.",
            },
        ],
    )["artifact"]["body"]
    assert completed["purpose"] == "Brew balanced coffee and diagnose taste problems."
    assert completed["audience"].startswith("Adults making coffee")
    assert set(completed["intake_state"]["accepted_default_fields"]) == {
        "prior_knowledge",
        "level",
        "duration",
        "language",
    }
    assert completed["intake_state"]["unresolved_required_fields"] == []
    assert (
        client.get("/api/courses/guided-intake/stages/brief").json()["state"] == "awaiting_review"
    )
    _assert_outcomes_decision_blocked(client, "guided-intake")


def test_invalid_stale_repeated_and_bypass_commands_are_rejected(client: TestClient) -> None:
    _create(client)
    first = _questions(client)
    blank = client.put(
        "/api/courses/guided-intake/brief/answers",
        json={
            "expected_checksum": first["checksum"],
            "answers": [{"question_id": "brief_audience", "value": "   \n"}],
        },
    )
    assert blank.status_code == 400
    too_long = client.put(
        "/api/courses/guided-intake/brief/answers",
        json={
            "expected_checksum": first["checksum"],
            "answers": [{"question_id": "brief_audience", "value": "x" * 501}],
        },
    )
    assert too_long.status_code == 400
    assert _questions(client)["checksum"] == first["checksum"]
    invalid = client.put(
        "/api/courses/guided-intake/brief/answers",
        json={
            "expected_checksum": first["checksum"],
            "answers": [{"question_id": "brief_level", "value": "expert"}],
        },
    )
    assert invalid.status_code == 400
    assert "not an allowed option" in invalid.text

    duplicate = client.put(
        "/api/courses/guided-intake/brief/answers",
        json={
            "expected_checksum": first["checksum"],
            "answers": [
                {"question_id": "brief_audience", "value": "Home beginners"},
                {"question_id": "brief_audience", "value": "Other beginners"},
            ],
        },
    )
    assert duplicate.status_code == 400
    hidden = client.put(
        "/api/courses/guided-intake/brief/answers",
        json={
            "expected_checksum": first["checksum"],
            "answers": [
                {
                    "question_id": "brief_live_teaching_constraints",
                    "value": "Not visible yet",
                }
            ],
        },
    )
    assert hidden.status_code == 400
    assert _questions(client)["checksum"] == first["checksum"]

    blocked_approval = client.post(
        "/api/courses/guided-intake/stages/brief/approve",
        json={
            "expected_checksum": client.get("/api/courses/guided-intake/stages/brief").json()[
                "checksum"
            ]
        },
    )
    assert blocked_approval.status_code == 409
    blocked_later = client.post(
        "/api/courses/guided-intake/stages/outcomes/run",
        json={"mode": "deterministic"},
    )
    assert blocked_later.status_code == 409
    _assert_outcomes_decision_blocked(client, "guided-intake")

    _answer(
        client,
        first,
        [
            {"question_id": "brief_audience", "value": "Home beginners"},
            {"question_id": "brief_prior_knowledge", "accept_default": True},
            {"question_id": "brief_purpose", "value": "Brew balanced coffee."},
            {"question_id": "brief_level", "accept_default": True},
            {"question_id": "brief_duration", "accept_default": True},
        ],
    )
    stale = client.put(
        "/api/courses/guided-intake/brief/answers",
        json={
            "expected_checksum": first["checksum"],
            "answers": [{"question_id": "brief_audience", "value": "Overwrite"}],
        },
    )
    assert stale.status_code == 409
    second = _questions(client)
    repeated = client.put(
        "/api/courses/guided-intake/brief/answers",
        json={
            "expected_checksum": second["checksum"],
            "answers": [{"question_id": "brief_audience", "value": "Overwrite"}],
        },
    )
    assert repeated.status_code == 400
    malformed = client.put(
        "/api/courses/guided-intake/brief/answers",
        json={
            "expected_checksum": second["checksum"],
            "answers": [
                {
                    "question_id": "brief_modality",
                    "value": "self_paced",
                    "invented": True,
                }
            ],
        },
    )
    assert malformed.status_code == 422
    for malformed_boolean in (
        {"question_id": "brief_modality", "accept_default": 1},
        {"question_id": "brief_modality", "skip": "true"},
    ):
        coercive = client.put(
            "/api/courses/guided-intake/brief/answers",
            json={
                "expected_checksum": second["checksum"],
                "answers": [malformed_boolean],
            },
        )
        assert coercive.status_code == 422
    assert _questions(client)["checksum"] == second["checksum"]


def test_self_paced_hides_live_question_and_clarification_endpoint_is_bounded(
    client: TestClient,
) -> None:
    _create(client)
    first = _questions(client)
    _answer(
        client,
        first,
        [
            {
                "question_id": "brief_audience",
                "value": "Adults new to home coffee brewing.",
            },
            {"question_id": "brief_prior_knowledge", "accept_default": True},
            {"question_id": "brief_purpose", "value": "Brew balanced coffee."},
            {"question_id": "brief_level", "accept_default": True},
            {"question_id": "brief_duration", "accept_default": True},
        ],
    )
    second = _questions(client)
    _answer(
        client,
        second,
        [
            {"question_id": "brief_modality", "accept_default": True},
            {"question_id": "brief_language", "accept_default": True},
        ],
    )
    complete = _questions(client)
    assert complete["round_kind"] == "complete"
    assert complete["questions"] == []
    response = client.post(
        "/api/courses/guided-intake/brief/clarifications/run",
        json={"expected_checksum": complete["checksum"], "mode": "live"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["questions"] == []

    changed = client.patch(
        "/api/courses/guided-intake/brief",
        json={
            "expected_checksum": complete["checksum"],
            "updates": {"assessment_expectations": "One practical demonstration."},
        },
    )
    assert changed.status_code == 200, changed.text
    stale = client.post(
        "/api/courses/guided-intake/brief/clarifications/run",
        json={"expected_checksum": complete["checksum"], "mode": "deterministic"},
    )
    assert stale.status_code == 409


def test_direct_edit_rejects_non_text_list_members_without_mutation(client: TestClient) -> None:
    _create(client)
    current = client.get("/api/courses/guided-intake/artifacts/brief").json()

    response = client.patch(
        "/api/courses/guided-intake/brief",
        json={
            "expected_checksum": current["checksum"],
            "updates": {"constraints": [{"invented": True}, 42, True]},
        },
    )

    assert response.status_code == 400
    after = client.get("/api/courses/guided-intake/artifacts/brief").json()
    assert after["checksum"] == current["checksum"]
    assert after["artifact"]["body"]["constraints"] == []


def test_outcomes_decision_unlocks_only_after_brief_approval(client: TestClient) -> None:
    _create(client)
    _complete_blended_intake(client)
    stage = client.get("/api/courses/guided-intake/stages/brief").json()
    approved = client.post(
        "/api/courses/guided-intake/stages/brief/approve",
        json={"expected_checksum": stage["checksum"]},
    )
    assert approved.status_code == 200, approved.text

    response = client.put(
        "/api/courses/guided-intake/outcomes/decision",
        json={
            "expected_checksum": "missing",
            "selected_ids": ["co1"],
            "edits": {},
            "additions": [],
            "priority_order": ["co1"],
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["artifact"]["status"] == "draft"
    assert [
        item["id"] for item in response.json()["artifact"]["body"]["outcomes"]
    ] == ["co1"]


def test_approved_direct_edit_requires_reopen_and_preserves_unrelated_intake(
    client: TestClient,
) -> None:
    _create(client)
    completed = _complete_blended_intake(client)["artifact"]
    accepted_before = completed["body"]["intake_state"]["accepted_default_fields"]
    answered_before = completed["body"]["intake_state"]["answered_question_ids"]
    stage = client.get("/api/courses/guided-intake/stages/brief").json()
    approved = client.post(
        "/api/courses/guided-intake/stages/brief/approve",
        json={"expected_checksum": stage["checksum"]},
    )
    assert approved.status_code == 200, approved.text
    artifact = client.get("/api/courses/guided-intake/artifacts/brief").json()
    rejected = client.patch(
        "/api/courses/guided-intake/brief",
        json={
            "expected_checksum": artifact["checksum"],
            "updates": {"must_have_topics": ["Taste diagnosis"]},
        },
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "reopen_required"

    approved_stage = client.get("/api/courses/guided-intake/stages/brief").json()
    preview = client.post(
        "/api/courses/guided-intake/stages/brief/impact",
        json={
            "expected_checksum": approved_stage["checksum"],
            "action": "reopen",
            "operation_summary": "Edit the approved Brief",
        },
    ).json()
    reopened = client.post(
        "/api/courses/guided-intake/stages/brief/reopen",
        json={
            "expected_checksum": approved_stage["checksum"],
            "reason": "Add one must-have topic.",
            "impact_acknowledged": True,
            "expected_impact_checksum": preview["impact_checksum"],
        },
    )
    assert reopened.status_code == 200, reopened.text
    current = client.get("/api/courses/guided-intake/artifacts/brief").json()
    edited = client.patch(
        "/api/courses/guided-intake/brief",
        json={
            "expected_checksum": current["checksum"],
            "updates": {"must_have_topics": ["Taste diagnosis"]},
        },
    )
    assert edited.status_code == 200, edited.text
    body = edited.json()["artifact"]["body"]
    assert body["must_have_topics"] == ["Taste diagnosis"]
    assert body["intake_state"]["accepted_default_fields"] == accepted_before
    assert set(body["intake_state"]["answered_question_ids"]) - {"brief_must_have_topics"} == set(
        answered_before
    )
    assert "must_have_topics" in body["intake_state"]["explicit_fields"]


def test_clearing_mandatory_direct_field_returns_brief_to_needs_input(
    client: TestClient,
) -> None:
    _create(client)
    completed = _complete_blended_intake(client)

    response = client.patch(
        "/api/courses/guided-intake/brief",
        json={
            "expected_checksum": completed["checksum"],
            "updates": {"audience": ""},
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()["artifact"]["body"]
    assert "audience" in body["intake_state"]["unresolved_required_fields"]
    assert "brief_audience" not in body["intake_state"]["answered_question_ids"]
    assert client.get("/api/courses/guided-intake/stages/brief").json()["state"] == (
        "needs_input"
    )


def test_direct_edit_reclassifies_only_the_targeted_accepted_default(
    client: TestClient,
) -> None:
    _create(client)
    completed = _complete_blended_intake(client)
    defaults_before = set(
        completed["artifact"]["body"]["intake_state"]["accepted_default_fields"]
    )

    response = client.patch(
        "/api/courses/guided-intake/brief",
        json={
            "expected_checksum": completed["checksum"],
            "updates": {"language": "French"},
        },
    )

    assert response.status_code == 200, response.text
    state = response.json()["artifact"]["body"]["intake_state"]
    assert "language" in state["explicit_fields"]
    assert set(state["accepted_default_fields"]) == defaults_before - {"language"}


def test_answer_and_direct_edit_endpoints_reject_concurrent_mutation(
    client: TestClient,
) -> None:
    _create(client)
    current = _questions(client)
    jobs = client.app.state.jobs

    with jobs.locks.acquire("guided-intake"):
        answer = client.put(
            "/api/courses/guided-intake/brief/answers",
            json={
                "expected_checksum": current["checksum"],
                "answers": [
                    {"question_id": "brief_audience", "value": "Home beginners"}
                ],
            },
        )
    assert answer.status_code == 409

    with jobs.locks.acquire("guided-intake"):
        edit = client.patch(
            "/api/courses/guided-intake/brief",
            json={
                "expected_checksum": current["checksum"],
                "updates": {"audience": "Home beginners"},
            },
        )
    assert edit.status_code == 409
    assert _questions(client)["checksum"] == current["checksum"]


def test_stale_and_no_op_direct_edits_do_not_create_false_revisions(
    client: TestClient,
) -> None:
    _create(client)
    initial = client.get("/api/courses/guided-intake/artifacts/brief").json()
    changed = client.patch(
        "/api/courses/guided-intake/brief",
        json={
            "expected_checksum": initial["checksum"],
            "updates": {"purpose": "Brew balanced coffee."},
        },
    )
    assert changed.status_code == 200, changed.text

    stale = client.patch(
        "/api/courses/guided-intake/brief",
        json={
            "expected_checksum": initial["checksum"],
            "updates": {"purpose": "Overwrite a newer purpose."},
        },
    )
    assert stale.status_code == 409
    current = client.get("/api/courses/guided-intake/artifacts/brief").json()
    no_op = client.patch(
        "/api/courses/guided-intake/brief",
        json={
            "expected_checksum": current["checksum"],
            "updates": {"purpose": "Brew balanced coffee."},
        },
    )
    assert no_op.status_code == 400
    after = client.get("/api/courses/guided-intake/artifacts/brief").json()
    assert after["checksum"] == current["checksum"]
    assert after["artifact"]["revision"] == current["artifact"]["revision"]


def test_historical_brief_normalization_does_not_rewrite_readable_fields() -> None:
    historical = {
        "subject": "Coffee making",
        "audience": "Home brewers",
        "purpose": "Brew better coffee",
        "prior_knowledge": "None",
        "level": "beginner",
        "duration": "3 hours",
        "modality": "self_paced",
        "language": "English",
        "provenance": [{"field": "level", "source": "default", "confidence": "assumed"}],
    }
    normalized = intake.normalize_brief_body({"body": {"subject": "Coffee making"}}, historical)

    assert {key: normalized[key] for key in historical} == historical
    assert normalized["intake_state"]["unresolved_required_fields"] == ["level"]
    assert "level" not in normalized["intake_state"]["accepted_default_fields"]


def test_historical_draft_is_normalized_on_every_read_and_cannot_bypass_approval(
    client: TestClient,
) -> None:
    _create(client, "historical-draft")
    repository = client.app.state.repository
    brief = repository.require("historical-draft", "brief")
    brief["body"].pop("intake_state")
    saved = repository.save(
        brief,
        expected_checksum=repository.checksum(
            repository.require("historical-draft", "brief")
        ),
    )
    path = repository.runtime_location("historical-draft").artifact_root / "brief.json"
    before = path.read_bytes()

    artifact_view = client.get(
        "/api/courses/historical-draft/artifacts/brief"
    ).json()
    stage_view = client.get("/api/courses/historical-draft/stages/brief").json()
    questions = _questions(client, "historical-draft")
    approval = client.post(
        "/api/courses/historical-draft/stages/brief/approve",
        json={"expected_checksum": stage_view["checksum"]},
    )

    unresolved = artifact_view["artifact"]["body"]["intake_state"][
        "unresolved_required_fields"
    ]
    assert unresolved
    assert "level" in unresolved
    assert stage_view["state"] == "needs_input"
    assert questions["round_kind"] == "mandatory"
    assert len(questions["questions"]) == 5
    assert approval.status_code == 409
    assert artifact_view["checksum"] == repository.checksum(saved)
    assert path.read_bytes() == before


def test_approved_but_unresolved_brief_requires_reopen_and_blocks_all_later_work(
    client: TestClient,
) -> None:
    _create(client, "corrupt-approved")
    _complete_blended_intake(client, "corrupt-approved")
    ready_stage = client.get("/api/courses/corrupt-approved/stages/brief").json()
    approved = client.post(
        "/api/courses/corrupt-approved/stages/brief/approve",
        json={"expected_checksum": ready_stage["checksum"]},
    )
    assert approved.status_code == 200, approved.text

    repository = client.app.state.repository
    brief = repository.require("corrupt-approved", "brief")
    brief_checksum = repository.checksum(brief)
    brief["body"]["in_scope"] = ["grind size"]
    brief["body"]["out_of_scope"] = ["grind size"]
    repository.save(brief, expected_checksum=brief_checksum)
    model = json.loads(
        (
            REPO_ROOT
            / "examples"
            / "acceptance"
            / "coffee-acceptance"
            / "course_artifacts"
            / "course_model.json"
        ).read_text(encoding="utf-8")
    )
    model["course_id"] = "corrupt-approved"
    model["status"] = "approved"
    repository.save(model)

    brief_stage = client.get("/api/courses/corrupt-approved/stages/brief").json()
    assert brief_stage["state"] == "requires_attention"
    assert [action["id"] for action in brief_stage["actions"]] == ["reopen"]
    assert "out_of_scope" in brief_stage["artifacts"][0]["body"]["intake_state"][
        "unresolved_required_fields"
    ]
    assert client.get("/api/courses/corrupt-approved/stages/outcomes").json()[
        "state"
    ] == "locked"
    _assert_outcomes_decision_blocked(client, "corrupt-approved")
    blueprint = client.get("/api/courses/corrupt-approved/stages/blueprint").json()
    assert blueprint["state"] == "locked"
    blocked_run = client.post(
        "/api/courses/corrupt-approved/stages/blueprint/run",
        json={"mode": "deterministic"},
    )
    assert blocked_run.status_code == 409

    for artifact_type, producer, body, inputs in (
        (
            "course_outcomes",
            "course_outcomes",
            {"outcomes": []},
            ["brief"],
        ),
        ("blueprint", "blueprint", {"subtopics": []}, ["course_model"]),
        (
            "content_package",
            "student_content",
            {
                "subtopics": [
                    {
                        "subtopic_id": "m1_s1",
                        "assets": [
                            {
                                "id": "m1_s1_cc",
                                "claims": [
                                    {
                                        "id": "claim_1",
                                        "text": "Unsupported claim",
                                        "source_id": "source_1",
                                        "support": "unsupported",
                                    }
                                ],
                                "verification": {
                                    "checked_at": "2026-07-17T00:00:00Z",
                                    "supported": 0,
                                    "partial": 0,
                                    "unsupported": 1,
                                    "ungrounded": 0,
                                    "unattributed_found": [],
                                },
                            }
                        ],
                    }
                ]
            },
            ["course_model", "blueprint", "course_outcomes"],
        ),
        (
            "content_progress",
            "student_content",
            {"units": []},
            ["course_model", "blueprint", "course_outcomes"],
        ),
    ):
        artifact = make_artifact(
            "corrupt-approved",
            artifact_type,
            producer,
            body=body,
            inputs=inputs,
            schema_version="0.2",
        )
        artifact["status"] = "approved"
        repository.save(artifact)
    content = client.get("/api/courses/corrupt-approved/stages/content").json()
    assert content["state"] == "stale"
    assert "revise" not in {action["id"] for action in content["actions"]}
    blocked_revision = client.post(
        "/api/courses/corrupt-approved/stages/content/revisions",
        json={
            "expected_checksum": content["checksum"],
            "target_type": "asset",
            "target_ids": ["m1_s1_cc"],
            "category": "clarity",
            "instruction": "Rewrite the unsupported claim.",
            "mode": "deterministic",
            "impact_acknowledged": True,
            "expected_impact_checksum": "not-current",
        },
    )
    assert blocked_revision.status_code == 409
    assert client.app.state.jobs.active_for_course("corrupt-approved") is None

    preview = client.post(
        "/api/courses/corrupt-approved/stages/brief/impact",
        json={
            "expected_checksum": brief_stage["checksum"],
            "action": "reopen",
            "operation_summary": "Repair unresolved approved intake",
        },
    ).json()
    reopened = client.post(
        "/api/courses/corrupt-approved/stages/brief/reopen",
        json={
            "expected_checksum": brief_stage["checksum"],
            "reason": "Resolve the conflicting scope.",
            "impact_acknowledged": True,
            "expected_impact_checksum": preview["impact_checksum"],
        },
    )
    assert reopened.status_code == 200, reopened.text
    assert client.get("/api/courses/corrupt-approved/stages/brief").json()[
        "state"
    ] == "needs_input"


def test_committed_fixture_projects_complete_intake_without_rewrite(tmp_path: Path) -> None:
    fixture = (
        REPO_ROOT
        / "examples"
        / "acceptance"
        / "coffee-acceptance"
        / "course_artifacts"
        / "brief.json"
    )
    before = fixture.read_bytes()
    app = create_app(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        runtime_root=tmp_path / "runtime",
        include_examples=True,
    )
    with TestClient(app) as example_client:
        response = example_client.get(
            "/api/courses/coffee-acceptance/stages/brief"
        )
        artifact = example_client.get(
            "/api/courses/coffee-acceptance/artifacts/brief"
        ).json()
        read_only_mutation = example_client.patch(
            "/api/courses/coffee-acceptance/brief",
            json={
                "expected_checksum": artifact["checksum"],
                "updates": {"language": "French"},
            },
        )

    assert response.status_code == 200
    assert read_only_mutation.status_code == 403
    projected = response.json()
    assert projected["state"] == "approved"
    intake_state = projected["artifacts"][0]["body"]["intake_state"]
    assert intake_state["unresolved_required_fields"] == []
    assert artifact["artifact"]["body"]["intake_state"] == intake_state
    assert fixture.read_bytes() == before


def test_clarification_validator_rejects_invented_and_repeated_resolved_questions() -> None:
    invented = QuestionSpec(
        id="brief_followup_secret",
        field="secret_field",
        prompt="Invented?",
        why="Must be rejected.",
        allow_agent_followup=True,
    )
    repeated = QuestionSpec(
        id="brief_followup_audience_gap_audience_generic",
        field="audience",
        prompt="Repeat?",
        why="Must be rejected after resolution.",
        allow_agent_followup=True,
    )

    assert (
        intake.validated_followups(
            {"audience": "Home beginners"},
            [invented, repeated],
            allowed_resolved_fields={"audience"},
            answered_question_ids={repeated.id},
        )
        == []
    )
