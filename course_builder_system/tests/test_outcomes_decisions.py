from __future__ import annotations

import json
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agents import outcomes
from api.main import create_app
from api.models import OutcomeDecisionCommand
from orchestrator import make_artifact

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


def _outcome(
    outcome_id: str,
    *,
    statement: str | None = None,
    evidence: str | None = None,
    cognitive_level: str = "apply",
    priority: str = "core",
) -> dict[str, Any]:
    return {
        "id": outcome_id,
        "statement": statement or f"Apply a reliable workflow for Outcome {outcome_id}.",
        "cognitive_level": cognitive_level,
        "evidence": evidence or f"Learner completes an observable task for Outcome {outcome_id}.",
        "priority": priority,
    }


def _candidates() -> list[dict[str, Any]]:
    return [_outcome("co1"), _outcome("co2"), _outcome("co3")]


def _addition(**overrides: Any) -> dict[str, Any]:
    value = {
        "statement": "Create a diagnostic plan for a realistic scenario.",
        "cognitive_level": "create",
        "evidence": "Learner produces and explains a usable diagnostic plan.",
        "priority": "supporting",
    }
    value.update(overrides)
    return value


def _issue_codes(exc: pytest.ExceptionInfo[outcomes.OutcomeDecisionValidationError]) -> set[str]:
    return {issue["code"] for issue in exc.value.issues}


def _complete_and_approve_brief(client: TestClient, course_id: str) -> None:
    created = client.post(
        "/api/courses",
        json={"subject": "Coffee making", "course_id": course_id},
    )
    assert created.status_code == 201, created.text
    brief = client.get(f"/api/courses/{course_id}/artifacts/brief").json()
    completed = client.patch(
        f"/api/courses/{course_id}/brief",
        json={
            "expected_checksum": brief["checksum"],
            "updates": {
                "audience": "Adults learning to brew coffee at home.",
                "purpose": "Brew balanced coffee and diagnose common problems.",
                "prior_knowledge": "No prior knowledge assumed.",
                "level": "beginner",
                "duration": "3 hours",
                "modality": "self_paced",
                "language": "English",
            },
        },
    )
    assert completed.status_code == 200, completed.text
    stage = client.get(f"/api/courses/{course_id}/stages/brief").json()
    approved = client.post(
        f"/api/courses/{course_id}/stages/brief/approve",
        json={"expected_checksum": stage["checksum"]},
    )
    assert approved.status_code == 200, approved.text


def _initial_decision(
    client: TestClient,
    course_id: str,
    *,
    selected_ids: list[str] | None = None,
    edits: dict[str, dict[str, Any]] | None = None,
    additions: list[dict[str, Any]] | None = None,
    priority_order: list[str] | None = None,
) -> dict[str, Any]:
    response = client.put(
        f"/api/courses/{course_id}/outcomes/decision",
        json={
            "expected_checksum": "missing",
            "selected_ids": selected_ids or ["co1", "co2", "co3"],
            "edits": edits or {},
            "additions": additions or [],
            "priority_order": priority_order or [],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _copy_acceptance_course(client: TestClient, course_id: str) -> None:
    repository = client.app.state.repository
    for path in ACCEPTANCE_ARTIFACTS.glob("*.json"):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        artifact["course_id"] = course_id
        repository.save(artifact)


def test_reducer_supports_simultaneous_add_edit_remove_and_complete_reorder() -> None:
    decided = outcomes.apply_outcome_decision(
        _candidates(),
        ["co3", "co1"],
        edits={
            "co1": {
                "statement": "  Evaluate a repeatable brewing workflow against clear criteria.  ",
                "evidence": "  Learner compares two workflows using a written rubric.  ",
                "cognitive_level": "evaluate",
                "priority": "optional",
            }
        },
        additions=[
            _addition(client_key="new_capstone"),
            _addition(
                client_key="new_plan",
                statement="Create a personal improvement plan from brewing evidence.",
            ),
        ],
        priority_order=["new_capstone", "co1", "new_plan", "co3"],
    )

    assert [item["id"] for item in decided] == ["co4", "co1", "co5", "co3"]
    assert "co2" not in {item["id"] for item in decided}
    edited = decided[1]
    assert edited == {
        "id": "co1",
        "statement": "Evaluate a repeatable brewing workflow against clear criteria.",
        "cognitive_level": "evaluate",
        "evidence": "Learner compares two workflows using a written rubric.",
        "priority": "optional",
    }


def test_idless_additions_use_deterministic_monotonic_ids_and_fallback_order() -> None:
    candidates = [_outcome("co1"), _outcome("co4")]
    kwargs = {
        "selected_ids": ["co1"],
        "additions": [
            _addition(statement="Create a first new observable learner product."),
            _addition(statement="Create a second new observable learner product."),
            _addition(statement="Create a third new observable learner product."),
        ],
        "priority_order": [],
    }

    first = outcomes.apply_outcome_decision(candidates, **kwargs)
    second = outcomes.apply_outcome_decision(candidates, **kwargs)

    assert first == second
    assert [item["id"] for item in first] == ["co1", "co5", "co6", "co7"]


def test_backend_allocation_cursor_rejects_boolean_values() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        outcomes.apply_outcome_decision(
            _candidates(),
            ["co1"],
            additions=[_addition()],
            allocation_start=True,
        )


@pytest.mark.parametrize(
    ("candidate_factory", "kwargs", "expected_code"),
    [
        (_candidates, {"selected_ids": []}, "outcomes_empty"),
        (
            _candidates,
            {"selected_ids": ["co1", "co1"]},
            "duplicate_selected_id",
        ),
        (
            lambda: [_outcome("co1"), _outcome("co1")],
            {"selected_ids": ["co1"]},
            "duplicate_outcome_id",
        ),
        (
            _candidates,
            {"selected_ids": ["missing"]},
            "unknown_selected_id",
        ),
        (
            _candidates,
            {"selected_ids": ["co1"], "edits": {"missing": {"priority": "core"}}},
            "unknown_edit_target",
        ),
        (
            _candidates,
            {"selected_ids": ["co1"], "edits": {"co1": {"invented": True}}},
            "unsupported_outcome_edit_field",
        ),
        (
            _candidates,
            {"selected_ids": ["co1"], "edits": {"co1": {"id": "co9"}}},
            "outcome_id_mutation",
        ),
        (
            _candidates,
            {"selected_ids": ["co1"], "edits": {"co2": {"priority": "optional"}}},
            "edit_target_not_retained",
        ),
        (
            _candidates,
            {"selected_ids": ["co1"], "edits": {"co1": {"cognitive_level": "judge"}}},
            "invalid_cognitive_level",
        ),
        (
            _candidates,
            {"selected_ids": ["co1"], "edits": {"co1": {"priority": "urgent"}}},
            "invalid_outcome_priority",
        ),
        (
            _candidates,
            {"selected_ids": ["co1"], "edits": {"co1": {"statement": "   "}}},
            "outcome_statement_empty",
        ),
        (
            _candidates,
            {"selected_ids": ["co1"], "edits": {"co1": {"evidence": "   "}}},
            "outcome_evidence_empty",
        ),
        (
            _candidates,
            {"selected_ids": ["co1"], "edits": {"co1": {"statement": 42}}},
            "outcome_field_type",
        ),
        (
            _candidates,
            {"selected_ids": ["co1"], "edits": {"co1": {"evidence": "x" * 301}}},
            "outcome_evidence_too_long",
        ),
        (
            _candidates,
            {"selected_ids": ["../co1"]},
            "invalid_selected_id",
        ),
        (
            _candidates,
            {"selected_ids": ["co1"], "additions": [_addition(id="co2")]},
            "addition_id_not_allowed",
        ),
        (
            _candidates,
            {
                "selected_ids": ["co1"],
                "additions": [_addition(client_key="new_same"), _addition(client_key="new_same")],
            },
            "duplicate_client_key",
        ),
        (
            _candidates,
            {
                "selected_ids": ["co1"],
                "additions": [_addition()],
                "priority_order": ["co1"],
            },
            "addition_client_key_required",
        ),
        (
            _candidates,
            {"selected_ids": ["co1", "co2"], "priority_order": ["co1", "co1"]},
            "duplicate_priority_order_id",
        ),
        (
            _candidates,
            {"selected_ids": ["co1"], "priority_order": ["co1", "missing"]},
            "unknown_priority_order_id",
        ),
        (
            _candidates,
            {"selected_ids": ["co1"], "priority_order": ["co2", "co1"]},
            "removed_outcome_in_priority_order",
        ),
        (
            _candidates,
            {"selected_ids": ["co1", "co2"], "priority_order": ["co1"]},
            "missing_priority_order_id",
        ),
        (
            _candidates,
            {"selected_ids": ["co1"], "priority_order": "co1"},
            "priority_order_type",
        ),
        (
            _candidates,
            {"selected_ids": ["co1"], "priority_order": ["co1", 42]},
            "priority_order_id_type",
        ),
        (
            _candidates,
            {"selected_ids": ["co1"], "priority_order": ["CO1"]},
            "invalid_priority_order_id",
        ),
    ],
)
def test_reducer_rejects_invalid_decisions_with_structured_issues(
    candidate_factory,
    kwargs: dict[str, Any],
    expected_code: str,
) -> None:
    with pytest.raises(outcomes.OutcomeDecisionValidationError) as exc_info:
        outcomes.apply_outcome_decision(candidate_factory(), **kwargs)

    assert expected_code in _issue_codes(exc_info)
    assert all({"code", "message"} <= set(issue) for issue in exc_info.value.issues)


def test_existing_collection_rejects_noop_after_normalization() -> None:
    with pytest.raises(outcomes.OutcomeDecisionValidationError) as exc_info:
        outcomes.apply_outcome_decision(
            _candidates(),
            ["co1", "co2", "co3"],
            priority_order=["co1", "co2", "co3"],
            reject_noop=True,
        )

    assert _issue_codes(exc_info) == {"outcome_decision_noop"}


def test_advisories_are_structured_nonblocking_and_identify_affected_outcomes() -> None:
    collection = [
        _outcome(
            "co1",
            statement="Understand the core brewing workflow and its variables.",
            evidence="Learner knows it.",
        ),
        _outcome(
            "co2",
            statement="Understand the core brewing workflow and its variables.",
        ),
        _outcome(
            "co3",
            statement="Understand the core brewing workflow and all its variables.",
        ),
    ]

    assert outcomes.validate_outcome_collection(collection)
    advisories = outcomes.outcome_advisories(collection)
    codes = {item["code"] for item in advisories}

    assert {
        "vague_or_non_observable_verb",
        "mechanically_weak_evidence",
        "duplicate_outcome_statement",
        "near_duplicate_outcome_statement",
    } <= codes
    assert all(item["severity"] == "advisory" for item in advisories)
    assert all(item["outcome_id"] in {"co1", "co2", "co3"} for item in advisories)


def test_nested_outcome_command_models_are_strict() -> None:
    base = {
        "expected_checksum": "missing",
        "selected_ids": ["co1"],
        "edits": {},
        "additions": [],
        "priority_order": [],
    }
    invalid_commands = [
        {**base, "invented": True},
        {**base, "edits": {"co1": {"id": "co9"}}},
        {**base, "edits": {"co1": {}}},
        {**base, "edits": {"co1": {"statement": 42}}},
        {**base, "additions": [{**_addition(), "invented": True}]},
        {**base, "additions": [_addition(id="co9")]},
        {**base, "additions": [{"statement": "Missing required fields"}]},
        {**base, "additions": [_addition(client_key="temporary-1")]},
    ]

    for command in invalid_commands:
        with pytest.raises(ValueError):
            OutcomeDecisionCommand.model_validate(command)


def test_initial_decision_with_missing_checksum_saves_draft_and_survives_refresh(
    client: TestClient,
) -> None:
    _complete_and_approve_brief(client, "initial-outcomes")

    decided = _initial_decision(
        client,
        "initial-outcomes",
        selected_ids=["co2", "co1"],
        edits={
            "co1": {
                "statement": "  Explain core brewing variables using precise language.  ",
                "evidence": "Learner explains each variable with a concrete example.",
                "cognitive_level": "understand",
                "priority": "supporting",
            }
        },
        additions=[_addition(client_key="new_diagnosis")],
        priority_order=["new_diagnosis", "co1", "co2"],
    )

    assert decided["artifact"]["status"] == "draft"
    assert [item["id"] for item in decided["artifact"]["body"]["outcomes"]] == [
        "co5",
        "co1",
        "co2",
    ]
    refreshed = client.get(
        "/api/courses/initial-outcomes/artifacts/course_outcomes"
    ).json()
    assert refreshed["artifact"] == decided["artifact"]
    assert refreshed["checksum"] == decided["checksum"]
    assert refreshed["artifact"]["body"]["next_outcome_id"] == 6
    stage = client.get("/api/courses/initial-outcomes/stages/outcomes").json()
    assert {action["id"] for action in stage["actions"]} == {"edit", "approve"}
    assert stage["advisories"] == decided["advisories"]


def test_decision_requires_current_checksum_and_rejections_preserve_artifact(
    client: TestClient,
) -> None:
    _complete_and_approve_brief(client, "versioned-outcomes")
    initial = _initial_decision(client, "versioned-outcomes")
    artifact_before = deepcopy(initial["artifact"])

    missing = client.put(
        "/api/courses/versioned-outcomes/outcomes/decision",
        json={
            "selected_ids": ["co1", "co2", "co3"],
            "edits": {"co1": {"priority": "supporting"}},
            "additions": [],
            "priority_order": [],
        },
    )
    assert missing.status_code == 422

    changed = client.put(
        "/api/courses/versioned-outcomes/outcomes/decision",
        json={
            "expected_checksum": initial["checksum"],
            "selected_ids": ["co1", "co2", "co3"],
            "edits": {"co1": {"priority": "supporting"}},
            "additions": [],
            "priority_order": [],
        },
    )
    assert changed.status_code == 200, changed.text
    stale = client.put(
        "/api/courses/versioned-outcomes/outcomes/decision",
        json={
            "expected_checksum": initial["checksum"],
            "selected_ids": ["co1", "co2", "co3"],
            "edits": {"co2": {"priority": "optional"}},
            "additions": [],
            "priority_order": [],
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["actual_checksum"] == changed.json()["checksum"]

    current = changed.json()
    artifact_path = (
        client.app.state.repository.courses_root
        / "versioned-outcomes"
        / "course_outcomes.json"
    )
    bytes_before_rejection = artifact_path.read_bytes()
    invalid = client.put(
        "/api/courses/versioned-outcomes/outcomes/decision",
        json={
            "expected_checksum": current["checksum"],
            "selected_ids": ["co1", "co1"],
            "edits": {},
            "additions": [],
            "priority_order": [],
        },
    )
    assert invalid.status_code == 400
    error = invalid.json()["error"]
    assert error["code"] == "invalid_outcome_decision"
    assert "duplicate_selected_id" in {item["code"] for item in error["issues"]}
    after = client.get(
        "/api/courses/versioned-outcomes/artifacts/course_outcomes"
    ).json()
    assert after["artifact"] == current["artifact"]
    assert artifact_path.read_bytes() == bytes_before_rejection
    assert artifact_before["revision"] + 1 == current["artifact"]["revision"]


def test_api_rejects_unknown_nested_fields_without_mutation(client: TestClient) -> None:
    _complete_and_approve_brief(client, "strict-outcomes")
    initial = _initial_decision(client, "strict-outcomes")

    for edits, additions in (
        ({"co1": {"id": "co9"}}, []),
        ({"co1": {"invented": True}}, []),
        ({"co1": {}}, []),
        ({}, [_addition(id="co9")]),
        ({}, [{**_addition(), "invented": True}]),
    ):
        response = client.put(
            "/api/courses/strict-outcomes/outcomes/decision",
            json={
                "expected_checksum": initial["checksum"],
                "selected_ids": ["co1", "co2", "co3"],
                "edits": edits,
                "additions": additions,
                "priority_order": [],
            },
        )
        assert response.status_code == 422

    after = client.get("/api/courses/strict-outcomes/artifacts/course_outcomes").json()
    assert after["checksum"] == initial["checksum"]


def test_deleted_outcome_ids_are_not_reused_across_later_decisions(
    client: TestClient,
) -> None:
    course_id = "monotonic-outcome-ids"
    _complete_and_approve_brief(client, course_id)
    initial = _initial_decision(
        client,
        course_id,
        additions=[_addition(client_key="new_first")],
        priority_order=["co1", "co2", "co3", "new_first"],
    )
    assert [item["id"] for item in initial["artifact"]["body"]["outcomes"]] == [
        "co1",
        "co2",
        "co3",
        "co5",
    ]
    assert initial["artifact"]["body"]["next_outcome_id"] == 6

    deleted = client.put(
        f"/api/courses/{course_id}/outcomes/decision",
        json={
            "expected_checksum": initial["checksum"],
            "selected_ids": ["co1", "co2", "co3"],
            "edits": {},
            "additions": [],
            "priority_order": ["co1", "co2", "co3"],
        },
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["artifact"]["body"]["next_outcome_id"] == 6

    added_again = client.put(
        f"/api/courses/{course_id}/outcomes/decision",
        json={
            "expected_checksum": deleted.json()["checksum"],
            "selected_ids": ["co1", "co2", "co3"],
            "edits": {},
            "additions": [_addition(client_key="new_second")],
            "priority_order": ["co1", "co2", "co3", "new_second"],
        },
    )
    assert added_again.status_code == 200, added_again.text
    assert [
        item["id"] for item in added_again.json()["artifact"]["body"]["outcomes"]
    ] == ["co1", "co2", "co3", "co6"]
    assert added_again.json()["artifact"]["body"]["next_outcome_id"] == 7


def test_missing_checksum_cannot_overwrite_an_artifact_that_appears_during_mutation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    course_id = "missing-sentinel-race"
    _complete_and_approve_brief(client, course_id)
    repository = client.app.state.repository
    decisions = client.app.state.decisions
    original = decisions.save_outcome_decision
    appeared: dict[str, Any] = {}

    def race_save(*args: Any, **kwargs: Any) -> dict[str, Any]:
        brief = repository.require(course_id, "brief")
        concurrent = outcomes.build_course_outcomes_artifact(
            brief,
            [_outcome("co9")],
            next_canonical_id=10,
        )
        concurrent["status"] = "draft"
        saved = repository.save(concurrent)
        appeared["artifact"] = saved
        appeared["bytes"] = (
            repository.courses_root / course_id / "course_outcomes.json"
        ).read_bytes()
        return original(*args, **kwargs)

    monkeypatch.setattr(decisions, "save_outcome_decision", race_save)
    response = client.put(
        f"/api/courses/{course_id}/outcomes/decision",
        json={
            "expected_checksum": "missing",
            "selected_ids": ["co9"],
            "edits": {"co9": {"priority": "supporting"}},
            "additions": [],
            "priority_order": [],
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["actual_checksum"] == repository.checksum(
        appeared["artifact"]
    )
    assert repository.require(course_id, "course_outcomes") == appeared["artifact"]
    assert (
        repository.courses_root / course_id / "course_outcomes.json"
    ).read_bytes() == appeared["bytes"]


def test_unresolved_unapproved_and_stale_briefs_block_outcomes_decisions(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/courses",
        json={"subject": "Coffee making", "course_id": "unresolved-outcomes"},
    )
    assert created.status_code == 201
    unresolved = client.put(
        "/api/courses/unresolved-outcomes/outcomes/decision",
        json={
            "expected_checksum": "missing",
            "selected_ids": ["co1"],
            "edits": {},
            "additions": [],
            "priority_order": [],
        },
    )
    assert unresolved.status_code == 409
    assert unresolved.json()["error"]["code"] == "prerequisite_not_approved"

    created = client.post(
        "/api/courses",
        json={"subject": "Coffee making", "course_id": "unapproved-outcomes"},
    )
    assert created.status_code == 201
    brief = client.get("/api/courses/unapproved-outcomes/artifacts/brief").json()
    completed = client.patch(
        "/api/courses/unapproved-outcomes/brief",
        json={
            "expected_checksum": brief["checksum"],
            "updates": {
                "audience": "Home brewers",
                "purpose": "Brew balanced coffee",
                "prior_knowledge": "None",
                "level": "beginner",
                "duration": "3 hours",
                "modality": "self_paced",
                "language": "English",
            },
        },
    )
    assert completed.status_code == 200
    unapproved = client.put(
        "/api/courses/unapproved-outcomes/outcomes/decision",
        json={
            "expected_checksum": "missing",
            "selected_ids": ["co1"],
            "edits": {},
            "additions": [],
            "priority_order": [],
        },
    )
    assert unapproved.status_code == 409

    _complete_and_approve_brief(client, "stale-brief-outcomes")
    repository = client.app.state.repository
    stale_brief = repository.require("stale-brief-outcomes", "brief")
    stale_checksum = repository.checksum(stale_brief)
    stale_brief["status"] = "stale"
    repository.save(stale_brief, expected_checksum=stale_checksum)
    stale = client.put(
        "/api/courses/stale-brief-outcomes/outcomes/decision",
        json={
            "expected_checksum": "missing",
            "selected_ids": ["co1"],
            "edits": {},
            "additions": [],
            "priority_order": [],
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "prerequisite_not_approved"

    _complete_and_approve_brief(client, "invalid-approved-brief-outcomes")
    invalid_brief = repository.require("invalid-approved-brief-outcomes", "brief")
    invalid_checksum = repository.checksum(invalid_brief)
    invalid_brief["body"]["audience"] = ""
    repository.save(invalid_brief, expected_checksum=invalid_checksum)
    invalid_approved = client.put(
        "/api/courses/invalid-approved-brief-outcomes/outcomes/decision",
        json={
            "expected_checksum": "missing",
            "selected_ids": ["co1"],
            "edits": {},
            "additions": [],
            "priority_order": [],
        },
    )
    assert invalid_approved.status_code == 409
    assert invalid_approved.json()["error"]["code"] == "prerequisite_not_approved"


def test_approved_outcomes_require_impact_confirmed_reopen_before_edit(
    client: TestClient,
) -> None:
    course_id = "reopen-outcomes"
    _complete_and_approve_brief(client, course_id)
    initial = _initial_decision(client, course_id)
    stage = client.get(f"/api/courses/{course_id}/stages/outcomes").json()
    approved = client.post(
        f"/api/courses/{course_id}/stages/outcomes/approve",
        json={"expected_checksum": stage["checksum"]},
    )
    assert approved.status_code == 200, approved.text
    artifact = client.get(f"/api/courses/{course_id}/artifacts/course_outcomes").json()

    blocked = client.put(
        f"/api/courses/{course_id}/outcomes/decision",
        json={
            "expected_checksum": artifact["checksum"],
            "selected_ids": ["co1", "co2", "co3"],
            "edits": {"co1": {"priority": "supporting"}},
            "additions": [],
            "priority_order": [],
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "reopen_required"

    approved_stage = client.get(f"/api/courses/{course_id}/stages/outcomes").json()
    preview = client.post(
        f"/api/courses/{course_id}/stages/outcomes/impact",
        json={"expected_checksum": approved_stage["checksum"], "action": "reopen"},
    ).json()
    missing_impact = client.post(
        f"/api/courses/{course_id}/stages/outcomes/reopen",
        json={"expected_checksum": approved_stage["checksum"]},
    )
    assert missing_impact.status_code == 409
    assert missing_impact.json()["error"]["code"] == "impact_confirmation_required"

    repository = client.app.state.repository
    downstream = make_artifact(
        course_id,
        "research_dossier",
        "research",
        body={"marker": "concurrent downstream state"},
        inputs=["brief", "course_outcomes"],
    )
    repository.save(downstream)
    stale_impact = client.post(
        f"/api/courses/{course_id}/stages/outcomes/reopen",
        json={
            "expected_checksum": approved_stage["checksum"],
            "impact_acknowledged": True,
            "expected_impact_checksum": preview["impact_checksum"],
        },
    )
    assert stale_impact.status_code == 409
    assert stale_impact.json()["error"]["code"] == "stale_impact_preview"

    fresh = client.post(
        f"/api/courses/{course_id}/stages/outcomes/impact",
        json={"expected_checksum": approved_stage["checksum"], "action": "reopen"},
    ).json()
    reopened = client.post(
        f"/api/courses/{course_id}/stages/outcomes/reopen",
        json={
            "expected_checksum": approved_stage["checksum"],
            "impact_acknowledged": True,
            "expected_impact_checksum": fresh["impact_checksum"],
            "reason": "Edit the approved Outcomes.",
        },
    )
    assert reopened.status_code == 200, reopened.text
    current = client.get(f"/api/courses/{course_id}/artifacts/course_outcomes").json()
    edited = client.put(
        f"/api/courses/{course_id}/outcomes/decision",
        json={
            "expected_checksum": current["checksum"],
            "selected_ids": ["co1", "co2", "co3"],
            "edits": {"co1": {"priority": "supporting"}},
            "additions": [],
            "priority_order": [],
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["artifact"]["status"] == "draft"
    assert initial["artifact"]["body"] != edited.json()["artifact"]["body"]


def test_outcome_change_invalidates_exact_descendants_without_body_loss(
    client: TestClient,
) -> None:
    course_id = "outcome-invalidation"
    _copy_acceptance_course(client, course_id)
    repository = client.app.state.repository
    artifact = repository.require(course_id, "course_outcomes")
    artifact_checksum = repository.checksum(artifact)
    artifact["status"] = "draft"
    artifact = repository.save(artifact, expected_checksum=artifact_checksum)
    descendants = {
        artifact_type
        for artifact_type in client.app.state.catalog.downstream_artifacts(
            {"course_outcomes"}
        )
        if repository.load(course_id, artifact_type) is not None
    }
    body_checksums = {
        artifact_type: repository.checksum(repository.require(course_id, artifact_type)["body"])
        for artifact_type in descendants
    }
    selected_ids = [item["id"] for item in artifact["body"]["outcomes"]]

    response = client.put(
        f"/api/courses/{course_id}/outcomes/decision",
        json={
            "expected_checksum": repository.checksum(artifact),
            "selected_ids": selected_ids,
            "edits": {
                "co1": {
                    "statement": "Explain core brewing variables and connect each to taste.",
                }
            },
            "additions": [],
            "priority_order": selected_ids,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["artifact"]["status"] == "draft"
    for artifact_type in descendants:
        current = repository.require(course_id, artifact_type)
        assert current["status"] == "stale"
        assert repository.checksum(current["body"]) == body_checksums[artifact_type]


def test_invalid_approval_is_structured_and_successful_approval_is_explicit(
    client: TestClient,
) -> None:
    _complete_and_approve_brief(client, "invalid-approval")
    _initial_decision(client, "invalid-approval")
    repository = client.app.state.repository
    invalid = repository.require("invalid-approval", "course_outcomes")
    checksum = repository.checksum(invalid)
    invalid["body"]["outcomes"][0]["cognitive_level"] = "judge"
    invalid = repository.save(invalid, expected_checksum=checksum)
    invalid_stage = client.get("/api/courses/invalid-approval/stages/outcomes").json()
    rejected = client.post(
        "/api/courses/invalid-approval/stages/outcomes/approve",
        json={"expected_checksum": invalid_stage["checksum"]},
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "approval_guard_failed"
    assert "outcomes_invalid" in {
        item["code"] for item in rejected.json()["error"]["failures"]
    }
    assert repository.require("invalid-approval", "course_outcomes") == invalid

    _complete_and_approve_brief(client, "invalid-cursor-approval")
    _initial_decision(client, "invalid-cursor-approval")
    invalid_cursor = repository.require(
        "invalid-cursor-approval", "course_outcomes"
    )
    checksum = repository.checksum(invalid_cursor)
    invalid_cursor["body"]["next_outcome_id"] = 1
    invalid_cursor = repository.save(invalid_cursor, expected_checksum=checksum)
    invalid_cursor_stage = client.get(
        "/api/courses/invalid-cursor-approval/stages/outcomes"
    ).json()
    rejected_cursor = client.post(
        "/api/courses/invalid-cursor-approval/stages/outcomes/approve",
        json={"expected_checksum": invalid_cursor_stage["checksum"]},
    )
    assert rejected_cursor.status_code == 409
    assert "outcomes_invalid" in {
        item["code"] for item in rejected_cursor.json()["error"]["failures"]
    }
    assert (
        repository.require("invalid-cursor-approval", "course_outcomes")
        == invalid_cursor
    )

    _complete_and_approve_brief(client, "valid-approval")
    _initial_decision(client, "valid-approval")
    valid_stage = client.get("/api/courses/valid-approval/stages/outcomes").json()
    approved = client.post(
        "/api/courses/valid-approval/stages/outcomes/approve",
        json={"expected_checksum": valid_stage["checksum"]},
    )
    assert approved.status_code == 200, approved.text
    assert client.get("/api/courses/valid-approval/stages/outcomes").json()["state"] == (
        "approved"
    )


def test_outcome_decision_rejects_concurrent_mutation_without_change(
    client: TestClient,
) -> None:
    _complete_and_approve_brief(client, "busy-outcomes")
    initial = _initial_decision(client, "busy-outcomes")

    with client.app.state.jobs.locks.acquire("busy-outcomes"):
        response = client.put(
            "/api/courses/busy-outcomes/outcomes/decision",
            json={
                "expected_checksum": initial["checksum"],
                "selected_ids": ["co1", "co2", "co3"],
                "edits": {"co1": {"priority": "supporting"}},
                "additions": [],
                "priority_order": [],
            },
        )

    assert response.status_code == 409
    after = client.get("/api/courses/busy-outcomes/artifacts/course_outcomes").json()
    assert after["checksum"] == initial["checksum"]


def test_active_course_job_suppresses_outcome_mutation_capabilities(
    client: TestClient,
) -> None:
    _complete_and_approve_brief(client, "active-job-outcomes")
    _initial_decision(client, "active-job-outcomes")
    projector = client.app.state.projector
    original_runner = projector.job_runner

    class ActiveJobRunner:
        @staticmethod
        def active_for_course(_course_id: str) -> dict[str, Any]:
            return {"job_id": "active", "stage": "research", "status": "running"}

        @staticmethod
        def latest_for_stage(_course_id: str, _stage_slug: str) -> None:
            return None

    projector.job_runner = ActiveJobRunner()
    try:
        stage = projector.stage("active-job-outcomes", "outcomes")
    finally:
        projector.job_runner = original_runner

    assert stage["state"] == "awaiting_review"
    assert stage["actions"] == []
    assert stage["can_mutate"] is False


def test_committed_example_outcomes_are_read_only(tmp_path: Path) -> None:
    app = create_app(
        repo_root=REPO_ROOT,
        courses_root=tmp_path / "courses",
        rendered_root=tmp_path / "rendered",
        runtime_root=tmp_path / "runtime",
        include_examples=True,
    )
    with TestClient(app) as example_client:
        artifact = example_client.get(
            "/api/courses/coffee-acceptance/artifacts/course_outcomes"
        ).json()
        selected_ids = [item["id"] for item in artifact["artifact"]["body"]["outcomes"]]
        response = example_client.put(
            "/api/courses/coffee-acceptance/outcomes/decision",
            json={
                "expected_checksum": artifact["checksum"],
                "selected_ids": selected_ids,
                "edits": {"co1": {"priority": "optional"}},
                "additions": [],
                "priority_order": selected_ids,
            },
        )

    assert response.status_code == 403
