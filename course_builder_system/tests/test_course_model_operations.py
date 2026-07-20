from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

import orchestrator
from agents.course_model import build_course_model_artifact
from api.models import CourseModelDecisionPreviewCommand
from course_model_operations import (
    CourseModelReduction,
    CourseModelValidationError,
    carry_forward_course_model_allocation,
    reduce_course_model_operations,
    validate_course_model_candidate,
)
from orchestrator import Decision, Step
from run import OUTPUT_TRANSFORMS

REPO_ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_ARTIFACTS = (
    REPO_ROOT / "examples" / "acceptance" / "coffee-acceptance" / "course_artifacts"
)
MODEL_DIR = REPO_ROOT / "course_models"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _acceptance_inputs() -> dict[str, dict[str, Any]]:
    return {
        artifact_type: _load(ACCEPTANCE_ARTIFACTS / f"{artifact_type}.json")
        for artifact_type in (
            "course_model",
            "course_outcomes",
            "research_dossier",
            "approved_source_registry",
        )
    }


def _frm_inputs() -> dict[str, dict[str, Any]]:
    model = _load(MODEL_DIR / "frm_demo.course_model.json")
    outcomes = _load(MODEL_DIR / "frm_demo.course_outcomes.json")
    dossier = _load(MODEL_DIR / "frm_demo.research_dossier.json")
    source_ids = [source["id"] for source in model["body"]["source_registry"]]
    registry = {
        "course_id": model["course_id"],
        "artifact_type": "approved_source_registry",
        "status": "approved",
        "body": {
            "decision": {
                "selected_ids": source_ids,
                "approved_ids": source_ids,
                "rejected_ids": [],
            },
            "source_registry": deepcopy(model["body"]["source_registry"]),
        },
    }
    return {
        "course_model": model,
        "course_outcomes": outcomes,
        "research_dossier": dossier,
        "approved_source_registry": registry,
    }


def _reduce(
    inputs: dict[str, dict[str, Any]],
    operations: list[dict[str, Any]],
    *,
    reject_noop: bool = True,
) -> CourseModelReduction:
    return reduce_course_model_operations(
        deepcopy(inputs["course_model"]),
        deepcopy(operations),
        course_outcomes=deepcopy(inputs["course_outcomes"]),
        research_dossier=deepcopy(inputs["research_dossier"]),
        approved_source_registry=deepcopy(inputs["approved_source_registry"]),
        reject_noop=reject_noop,
    )


def _module(body: dict[str, Any], module_id: str) -> dict[str, Any]:
    return next(module for module in body["modules"] if module["id"] == module_id)


def _subtopic(body: dict[str, Any], subtopic_id: str) -> dict[str, Any]:
    return next(
        subtopic
        for module in body["modules"]
        for subtopic in module["subtopics"]
        if subtopic["id"] == subtopic_id
    )


def _concept(body: dict[str, Any], concept_id: str) -> dict[str, Any]:
    return next(
        concept
        for module in body["modules"]
        for subtopic in module["subtopics"]
        for concept in subtopic["concepts"]
        if concept["id"] == concept_id
    )


def _coverage(body: dict[str, Any], coverage_id: str) -> dict[str, Any]:
    return next(
        coverage
        for module in body["modules"]
        for subtopic in module["subtopics"]
        for coverage in subtopic["coverage_requirements"]
        if coverage["id"] == coverage_id
    )


def _all_ids(body: dict[str, Any]) -> set[str]:
    return {
        str(record["id"])
        for record in body.get("modules", [])
        for record in (
            record,
            *record.get("subtopics", []),
            *[
                nested
                for subtopic in record.get("subtopics", [])
                for nested in (
                    *subtopic.get("concepts", []),
                    *subtopic.get("coverage_requirements", []),
                )
            ],
        )
    }


def _strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [item for child in value.values() for item in _strings(child)]
    if isinstance(value, list):
        return [item for child in value for item in _strings(child)]
    return [value] if isinstance(value, str) else []


def _add_second_module_operations() -> list[dict[str, Any]]:
    return [
        {
            "op": "add_module",
            "client_ref": "new_module_second",
            "position": 2,
            "title": "Applied Coffee Practice",
            "purpose": "Turn the foundations into a repeatable practice workflow.",
            "in_scope": ["Practice"],
            "out_of_scope": ["Commercial production"],
            "prerequisite_module_ids": ["m1"],
        },
        {
            "op": "add_subtopic",
            "client_ref": "new_subtopic_transfer",
            "parent_id": "new_module_second",
            "position": 1,
            "title": "Transfer to a New Brewer",
            "purpose": "Apply the workflow with unfamiliar equipment.",
            "in_scope": ["Transfer"],
            "out_of_scope": ["Machine repair"],
            "prerequisite_subtopic_ids": ["m1_s4"],
        },
    ]


def _add_complete_second_module_operations() -> list[dict[str, Any]]:
    return [
        *_add_second_module_operations(),
        {
            "op": "add_concept",
            "client_ref": "new_concept_transfer",
            "parent_id": "new_subtopic_transfer",
            "position": 1,
            "name": "Transfer variables",
            "summary": "Variables that must be reconsidered when equipment changes.",
            "depends_on": ["c_m1_s4_1"],
        },
        {
            "op": "add_coverage",
            "client_ref": "new_coverage_transfer",
            "parent_id": "new_subtopic_transfer",
            "position": 1,
            "statement": "Adapt one known recipe to unfamiliar brewing equipment.",
            "concept_ids": ["new_concept_transfer"],
        },
        {
            "op": "assign_sources",
            "target_type": "subtopic",
            "target_id": "new_subtopic_transfer",
            "source_ids": ["coffee_g1"],
        },
        {
            "op": "assign_sources",
            "target_type": "concept",
            "target_id": "new_concept_transfer",
            "source_ids": ["coffee_g1"],
        },
        {
            "op": "assign_sources",
            "target_type": "coverage",
            "target_id": "new_coverage_transfer",
            "source_ids": ["coffee_g1"],
        },
    ]


def test_strict_command_union_accepts_every_operation_family() -> None:
    operations = [
        *_add_second_module_operations(),
        {"op": "update_module", "target_id": "m1", "title": "Revised"},
        {"op": "remove_module", "target_id": "m2"},
        {"op": "move_module", "target_id": "m1", "position": 1},
        {"op": "reorder_modules", "module_ids": ["m1"]},
        {"op": "update_subtopic", "target_id": "m1_s1", "title": "Revised"},
        {"op": "remove_subtopic", "target_id": "m1_s4"},
        {
            "op": "move_subtopic",
            "target_id": "m1_s4",
            "parent_id": "m1",
            "position": 1,
        },
        {
            "op": "reorder_subtopics",
            "parent_id": "m1",
            "subtopic_ids": ["m1_s1", "m1_s2", "m1_s3", "m1_s4"],
        },
        {
            "op": "add_concept",
            "client_ref": "new_concept_extra",
            "parent_id": "m1_s1",
            "position": 1,
            "name": "A concept",
            "summary": "A compact concept summary.",
            "depends_on": [],
        },
        {"op": "update_concept", "target_id": "c1", "name": "Revised"},
        {"op": "remove_concept", "target_id": "c1"},
        {
            "op": "add_coverage",
            "client_ref": "new_coverage_extra",
            "parent_id": "m1_s1",
            "position": 1,
            "statement": "Cover a concept.",
            "concept_ids": ["c1"],
        },
        {"op": "update_coverage", "target_id": "cr1", "statement": "Revised"},
        {"op": "remove_coverage", "target_id": "cr1"},
        {
            "op": "assign_sources",
            "target_type": "subtopic",
            "target_id": "m1_s1",
            "source_ids": ["g1"],
        },
        {"op": "set_course_outcome_links", "outcome_ids": ["co1"]},
        {
            "op": "set_rationale_outcome_links",
            "target_id": "sr1",
            "outcome_ids": ["co1"],
        },
    ]

    command = CourseModelDecisionPreviewCommand.model_validate(
        {"expected_checksum": "abcdef", "operations": operations}
    )

    assert [operation.op for operation in command.operations] == [
        operation["op"] for operation in operations
    ]


@pytest.mark.parametrize(
    "operation",
    [
        {"op": "replace", "path": "/body", "value": {}},
        {
            "op": "add_module",
            "client_ref": "new_module_extra",
            "position": 1,
            "title": "Title",
            "purpose": "Purpose",
            "in_scope": [],
            "out_of_scope": [],
            "prerequisite_module_ids": [],
            "id": "m99",
        },
        {
            "op": "add_module",
            "client_ref": "new_module_extra",
            "position": True,
            "title": "Title",
            "purpose": "Purpose",
            "in_scope": [],
            "out_of_scope": [],
            "prerequisite_module_ids": [],
        },
        {
            "op": "add_concept",
            "client_ref": "new_subtopic_wrong_kind",
            "parent_id": "m1_s1",
            "position": 1,
            "name": "Concept",
            "summary": "Summary",
            "depends_on": [],
        },
        {"op": "update_module", "target_id": "m1"},
        {"op": "update_subtopic", "target_id": "m1_s1", "title": None},
        {
            "op": "assign_sources",
            "target_type": "module",
            "target_id": "m1",
            "source_ids": [],
        },
    ],
)
def test_strict_command_union_rejects_generic_extra_and_mistyped_payloads(
    operation: dict[str, Any],
) -> None:
    with pytest.raises(ValueError):
        CourseModelDecisionPreviewCommand.model_validate(
            {"expected_checksum": "abcdef", "operations": [operation]}
        )


def test_mixed_batch_resolves_local_references_and_all_mutable_record_fields() -> None:
    inputs = _acceptance_inputs()
    operations = [
        *_add_complete_second_module_operations(),
        {
            "op": "update_module",
            "target_id": "new_module_second",
            "title": "Applied Coffee Transfer",
            "purpose": "Transfer reliable decisions to unfamiliar equipment.",
            "in_scope": ["Practice", "Transfer"],
            "out_of_scope": ["Commercial production", "Machine repair"],
            "prerequisite_module_ids": ["m1"],
        },
        {
            "op": "update_subtopic",
            "target_id": "new_subtopic_transfer",
            "title": "Equipment Transfer",
            "purpose": "Adapt a known process without losing control of variables.",
            "in_scope": ["Transfer", "Diagnosis"],
            "out_of_scope": ["Machine repair"],
            "prerequisite_subtopic_ids": ["m1_s4"],
        },
        {
            "op": "update_concept",
            "target_id": "new_concept_transfer",
            "name": "Transferable variables",
            "summary": "Variables to hold constant or deliberately retune.",
            "depends_on": ["c_m1_s4_1"],
        },
        {
            "op": "update_coverage",
            "target_id": "new_coverage_transfer",
            "statement": "Adapt and justify one recipe for unfamiliar equipment.",
            "concept_ids": ["new_concept_transfer"],
        },
        {
            "op": "set_course_outcome_links",
            "outcome_ids": ["co4", "co3", "co2", "co1"],
        },
        {
            "op": "set_rationale_outcome_links",
            "target_id": "sr1",
            "outcome_ids": ["co1", "co4"],
        },
    ]

    reduction = _reduce(inputs, operations)
    body = reduction.candidate_body

    assert reduction.allocated_ids == {
        "new_module_second": "m2",
        "new_subtopic_transfer": "s5",
        "new_concept_transfer": "c5",
        "new_coverage_transfer": "cr5",
    }
    module = _module(body, "m2")
    assert module["title"] == "Applied Coffee Transfer"
    assert module["context"] == {
        "purpose": "Transfer reliable decisions to unfamiliar equipment.",
        "in_scope": ["Practice", "Transfer"],
        "out_of_scope": ["Commercial production", "Machine repair"],
    }
    subtopic = _subtopic(body, "s5")
    assert subtopic["title"] == "Equipment Transfer"
    assert subtopic["prerequisite_subtopic_ids"] == ["m1_s4"]
    assert subtopic["approved_source_ids"] == ["coffee_g1"]
    assert _concept(body, "c5") == {
        "id": "c5",
        "name": "Transferable variables",
        "summary": "Variables to hold constant or deliberately retune.",
        "depends_on": ["c_m1_s4_1"],
        "source_ids": ["coffee_g1"],
    }
    assert _coverage(body, "cr5") == {
        "id": "cr5",
        "statement": "Adapt and justify one recipe for unfamiliar equipment.",
        "concept_ids": ["c5"],
        "source_ids": ["coffee_g1"],
    }
    assert body["course_metadata"]["course_outcome_ids"] == [
        "co4",
        "co3",
        "co2",
        "co1",
    ]
    assert body["structural_rationale"][0]["related_outcome_ids"] == ["co1", "co4"]
    assert not any(value.startswith("new_") for value in _strings(body))


def test_move_and_reorder_preserve_ids_nested_records_and_contiguous_order() -> None:
    inputs = _acceptance_inputs()
    original_nested = deepcopy(_subtopic(inputs["course_model"]["body"], "m1_s4"))
    operations = [
        *_add_second_module_operations(),
        {"op": "move_module", "target_id": "new_module_second", "position": 1},
        {
            "op": "reorder_modules",
            "module_ids": ["m1", "new_module_second"],
        },
        {
            "op": "move_subtopic",
            "target_id": "m1_s4",
            "parent_id": "new_module_second",
            "position": 2,
        },
        {
            "op": "reorder_subtopics",
            "parent_id": "new_module_second",
            "subtopic_ids": ["m1_s4", "new_subtopic_transfer"],
        },
    ]

    body = _reduce(inputs, operations).candidate_body

    assert [module["id"] for module in body["modules"]] == ["m1", "m2"]
    assert [module["order"] for module in body["modules"]] == [1, 2]
    assert [item["id"] for item in _module(body, "m1")["subtopics"]] == [
        "m1_s1",
        "m1_s2",
        "m1_s3",
    ]
    assert [item["id"] for item in _module(body, "m2")["subtopics"]] == [
        "m1_s4",
        "s5",
    ]
    assert [item["order"] for item in _module(body, "m2")["subtopics"]] == [1, 2]
    moved = _subtopic(body, "m1_s4")
    assert {key: moved[key] for key in moved if key != "order"} == {
        key: original_nested[key] for key in original_nested if key != "order"
    }


def test_remove_concept_and_coverage_only_removes_named_records() -> None:
    inputs = _acceptance_inputs()

    body = _reduce(
        inputs,
        [
            {"op": "remove_coverage", "target_id": "cr_m1_s4_1"},
            {"op": "remove_concept", "target_id": "c_m1_s4_1"},
        ],
    ).candidate_body

    retained = _subtopic(body, "m1_s4")
    assert retained["concepts"] == []
    assert retained["coverage_requirements"] == []
    assert retained["approved_source_ids"] == ["coffee_g1", "coffee_g2"]


def test_remove_subtopic_cascades_its_concepts_and_coverage() -> None:
    inputs = _acceptance_inputs()

    body = _reduce(
        inputs,
        [{"op": "remove_subtopic", "target_id": "m1_s4"}],
    ).candidate_body

    assert "m1_s4" not in _all_ids(body)
    assert "c_m1_s4_1" not in _all_ids(body)
    assert "cr_m1_s4_1" not in _all_ids(body)
    assert [item["order"] for item in _module(body, "m1")["subtopics"]] == [1, 2, 3]


def test_remove_module_cascades_all_nested_records_but_keeps_one_valid_module() -> None:
    inputs = _acceptance_inputs()

    reduction = _reduce(
        inputs,
        [
            {
                **_add_second_module_operations()[0],
                "prerequisite_module_ids": [],
            },
            {
                **_add_second_module_operations()[1],
                "prerequisite_subtopic_ids": [],
            },
            {"op": "remove_module", "target_id": "m1"},
        ],
    )
    body = reduction.candidate_body

    assert [module["id"] for module in body["modules"]] == ["m2"]
    assert body["modules"][0]["order"] == 1
    assert [item["id"] for item in body["modules"][0]["subtopics"]] == ["s5"]
    assert not (_all_ids(inputs["course_model"]["body"]) & _all_ids(body))


def test_assign_sources_supports_each_target_and_enforces_parent_assignment() -> None:
    inputs = _acceptance_inputs()
    valid = _reduce(
        inputs,
        [
            {
                "op": "assign_sources",
                "target_type": "subtopic",
                "target_id": "m1_s1",
                "source_ids": ["coffee_g1", "coffee_g2"],
            },
            {
                "op": "assign_sources",
                "target_type": "concept",
                "target_id": "c_m1_s1_1",
                "source_ids": ["coffee_g2"],
            },
            {
                "op": "assign_sources",
                "target_type": "coverage",
                "target_id": "cr_m1_s1_1",
                "source_ids": ["coffee_g2"],
            },
        ],
    ).candidate_body

    assert _subtopic(valid, "m1_s1")["approved_source_ids"] == [
        "coffee_g1",
        "coffee_g2",
    ]
    assert _concept(valid, "c_m1_s1_1")["source_ids"] == ["coffee_g2"]
    assert _coverage(valid, "cr_m1_s1_1")["source_ids"] == ["coffee_g2"]

    with pytest.raises(CourseModelValidationError):
        _reduce(
            inputs,
            [
                {
                    "op": "assign_sources",
                    "target_type": "concept",
                    "target_id": "c_m1_s1_1",
                    "source_ids": ["coffee_g2"],
                }
            ],
        )


def test_deleted_ids_are_not_reused_across_later_batches() -> None:
    inputs = _acceptance_inputs()
    first = _reduce(inputs, _add_complete_second_module_operations())
    after_first = {**inputs, "course_model": first.candidate_artifact}

    deleted = _reduce(
        after_first,
        [{"op": "remove_module", "target_id": "m2"}],
    )
    after_delete = {**inputs, "course_model": deleted.candidate_artifact}
    second_operations = [
        *deepcopy(_add_complete_second_module_operations()),
    ]
    second = _reduce(after_delete, second_operations)

    assert first.allocated_ids == {
        "new_module_second": "m2",
        "new_subtopic_transfer": "s5",
        "new_concept_transfer": "c5",
        "new_coverage_transfer": "cr5",
    }
    assert deleted.candidate_body["id_allocation"] == {
        "next_module_id": 3,
        "next_subtopic_id": 6,
        "next_concept_id": 6,
        "next_coverage_id": 6,
        "retired_module_ids": ["m2"],
        "retired_subtopic_ids": ["s5"],
        "retired_concept_ids": ["c5"],
        "retired_coverage_ids": ["cr5"],
    }
    assert second.allocated_ids == {
        "new_module_second": "m3",
        "new_subtopic_transfer": "s6",
        "new_concept_transfer": "c6",
        "new_coverage_transfer": "cr6",
    }


def test_generated_model_cannot_reintroduce_an_id_below_the_prior_cursor() -> None:
    inputs = _acceptance_inputs()
    previous = deepcopy(inputs["course_model"])
    previous["body"]["id_allocation"] = {
        "next_module_id": 2,
        "next_subtopic_id": 5,
        "next_concept_id": 6,
        "next_coverage_id": 5,
    }
    regenerated = deepcopy(previous)
    regenerated["body"].pop("id_allocation")
    regenerated["body"]["modules"][0]["subtopics"][0]["concepts"][0]["id"] = "c5"

    with pytest.raises(CourseModelValidationError) as exc_info:
        carry_forward_course_model_allocation(regenerated, previous)

    assert exc_info.value.issues[0]["code"] == "course_model_id_reused"


def test_generation_rerun_rejects_retired_ids_from_every_structural_family() -> None:
    inputs = _acceptance_inputs()
    operations = deepcopy(_add_complete_second_module_operations())
    operations[0]["prerequisite_module_ids"] = []
    operations[1]["prerequisite_subtopic_ids"] = []
    operations[2]["depends_on"] = []
    operations.append({"op": "remove_module", "target_id": "m1"})

    deleted = _reduce(inputs, operations)
    allocation = deleted.candidate_body["id_allocation"]
    assert allocation["retired_module_ids"] == ["m1"]
    assert allocation["retired_subtopic_ids"] == [
        "m1_s1",
        "m1_s2",
        "m1_s3",
        "m1_s4",
    ]
    assert allocation["retired_concept_ids"] == [
        "c_m1_s1_1",
        "c_m1_s2_1",
        "c_m1_s3_1",
        "c_m1_s4_1",
    ]
    assert allocation["retired_coverage_ids"] == [
        "cr_m1_s1_1",
        "cr_m1_s2_1",
        "cr_m1_s3_1",
        "cr_m1_s4_1",
    ]

    with pytest.raises(CourseModelValidationError) as exc_info:
        carry_forward_course_model_allocation(
            deepcopy(inputs["course_model"]),
            deleted.candidate_artifact,
        )

    assert {issue["record_type"] for issue in exc_info.value.issues} == {
        "module",
        "subtopic",
        "concept",
        "coverage",
    }
    assert {issue["code"] for issue in exc_info.value.issues} == {
        "course_model_id_reused"
    }


def test_cli_pipeline_injects_course_model_allocation_preservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _acceptance_inputs()
    existing = deepcopy(inputs["course_model"])
    existing["course_id"] = "cli-allocation"
    existing["status"] = "stale"
    existing["body"]["id_allocation"] = {
        "next_module_id": 2,
        "next_subtopic_id": 5,
        "next_concept_id": 6,
        "next_coverage_id": 5,
    }
    regenerated = deepcopy(existing)
    regenerated["body"].pop("id_allocation")
    monkeypatch.setattr(orchestrator, "COURSES_DIR", tmp_path / "courses")
    orchestrator.save_artifact(existing)

    orchestrator.run_pipeline(
        "cli-allocation",
        [
            Step(
                name="structure",
                consumes=[],
                produces=["course_model"],
                run=lambda _inputs, _feedback: {"course_model": deepcopy(regenerated)},
            )
        ],
        {},
        approver=lambda _step, _produced: Decision(approved=True),
        output_transforms=OUTPUT_TRANSFORMS,
    )

    saved = orchestrator.load_artifact("cli-allocation", "course_model")
    assert saved is not None
    assert saved["body"]["id_allocation"]["next_concept_id"] == 6


def test_cli_pipeline_fails_closed_before_reusing_retired_legacy_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inputs = _acceptance_inputs()
    deleted = _reduce(
        inputs,
        [{"op": "remove_subtopic", "target_id": "m1_s4"}],
    ).candidate_artifact
    deleted["course_id"] = "cli-retired-legacy"
    deleted["status"] = "stale"
    regenerated = deepcopy(inputs["course_model"])
    regenerated["course_id"] = "cli-retired-legacy"
    monkeypatch.setattr(orchestrator, "COURSES_DIR", tmp_path / "courses")
    orchestrator.save_artifact(deleted)

    with pytest.raises(CourseModelValidationError) as exc_info:
        orchestrator.run_pipeline(
            "cli-retired-legacy",
            [
                Step(
                    name="structure",
                    consumes=[],
                    produces=["course_model"],
                    run=lambda _inputs, _feedback: {
                        "course_model": deepcopy(regenerated)
                    },
                )
            ],
            {},
            approver=lambda _step, _produced: Decision(approved=True),
            output_transforms=OUTPUT_TRANSFORMS,
        )

    assert any(
        issue["code"] == "course_model_id_reused"
        and issue["record_id"] == "m1_s4"
        for issue in exc_info.value.issues
    )
    assert orchestrator.load_artifact("cli-retired-legacy", "course_model") == deleted


def test_allocation_precedes_later_deletion_and_advances_on_success() -> None:
    inputs = _acceptance_inputs()

    reduction = _reduce(
        inputs,
        [
            {
                "op": "add_concept",
                "client_ref": "new_concept_ephemeral",
                "parent_id": "m1_s1",
                "position": 2,
                "name": "Ephemeral concept",
                "summary": "Allocated and deliberately removed in this batch.",
                "depends_on": [],
            },
            {"op": "remove_concept", "target_id": "new_concept_ephemeral"},
            {
                "op": "update_module",
                "target_id": "m1",
                "title": "Coffee Making Foundations",
            },
        ],
    )

    assert reduction.allocated_ids["new_concept_ephemeral"] == "c5"
    assert "c5" not in _all_ids(reduction.candidate_body)
    assert reduction.candidate_body["id_allocation"]["next_concept_id"] == 6
    assert reduction.candidate_body["id_allocation"]["retired_concept_ids"] == ["c5"]

    corrupted = {**inputs, "course_model": deepcopy(reduction.candidate_artifact)}
    corrupted["course_model"]["body"]["id_allocation"]["next_concept_id"] = 5
    with pytest.raises(CourseModelValidationError) as exc_info:
        _reduce(
            corrupted,
            [{"op": "update_module", "target_id": "m1", "title": "Another title"}],
        )

    assert any(
        issue["code"] == "allocation_cursor_below_floor"
        for issue in exc_info.value.issues
    )


@pytest.mark.parametrize(
    ("inputs_factory", "expected"),
    [
        (
            _acceptance_inputs,
            {
                "next_module_id": 2,
                "next_subtopic_id": 5,
                "next_concept_id": 5,
                "next_coverage_id": 5,
            },
        ),
        (
            _frm_inputs,
            {
                "next_module_id": 3,
                "next_subtopic_id": 8,
                "next_concept_id": 9,
                "next_coverage_id": 7,
            },
        ),
    ],
)
def test_historical_models_derive_complete_collision_safe_allocation_state(
    inputs_factory,
    expected: dict[str, int],
) -> None:
    inputs = inputs_factory()
    original = deepcopy(inputs["course_model"])

    reduction = _reduce(
        inputs,
        [
            {
                "op": "update_module",
                "target_id": "m1",
                "title": f"{_module(original['body'], 'm1')['title']} revised",
            }
        ],
    )

    assert "id_allocation" not in original["body"]
    assert reduction.candidate_body["id_allocation"] == expected
    assert inputs["course_model"] == original


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("next_module_id", True),
        ("next_module_id", False),
        ("next_module_id", 0),
        ("next_module_id", -1),
        ("next_module_id", 1.0),
        ("next_module_id", "2"),
        ("next_module_id", 1),
        ("next_subtopic_id", 4),
        ("next_concept_id", 4),
        ("next_coverage_id", 4),
    ],
)
def test_invalid_boolean_and_decreasing_allocation_cursors_are_rejected(
    field: str,
    invalid: Any,
) -> None:
    inputs = _acceptance_inputs()
    inputs["course_model"]["body"]["id_allocation"] = {
        "next_module_id": 2,
        "next_subtopic_id": 5,
        "next_concept_id": 5,
        "next_coverage_id": 5,
        field: invalid,
    }

    with pytest.raises(CourseModelValidationError):
        _reduce(
            inputs,
            [
                {
                    "op": "update_module",
                    "target_id": "m1",
                    "title": "Revised title",
                }
            ],
        )


def test_partial_allocation_state_is_rejected_and_valid_high_cursors_are_preserved() -> None:
    inputs = _acceptance_inputs()
    inputs["course_model"]["body"]["id_allocation"] = {
        "next_module_id": 20,
        "next_subtopic_id": 30,
        "next_concept_id": 40,
    }
    with pytest.raises(CourseModelValidationError):
        _reduce(
            inputs,
            [{"op": "update_module", "target_id": "m1", "title": "Revised title"}],
        )

    inputs["course_model"]["body"]["id_allocation"] = {
        "next_module_id": 20,
        "next_subtopic_id": 30,
        "next_concept_id": 40,
        "next_coverage_id": 50,
    }
    body = _reduce(
        inputs,
        [{"op": "update_module", "target_id": "m1", "title": "Revised title"}],
    ).candidate_body
    assert body["id_allocation"] == {
        "next_module_id": 20,
        "next_subtopic_id": 30,
        "next_concept_id": 40,
        "next_coverage_id": 50,
    }


@pytest.mark.parametrize(
    "operations",
    [
        [
            {
                "op": "add_concept",
                "client_ref": "new_concept_same",
                "parent_id": "m1_s1",
                "position": 2,
                "name": "First",
                "summary": "First summary.",
                "depends_on": [],
            },
            {
                "op": "add_concept",
                "client_ref": "new_concept_same",
                "parent_id": "m1_s1",
                "position": 3,
                "name": "Second",
                "summary": "Second summary.",
                "depends_on": [],
            },
        ],
        [
            {
                "op": "add_coverage",
                "client_ref": "new_coverage_forward",
                "parent_id": "m1_s1",
                "position": 2,
                "statement": "Forward reference is forbidden.",
                "concept_ids": ["new_concept_later"],
            },
            {
                "op": "add_concept",
                "client_ref": "new_concept_later",
                "parent_id": "m1_s1",
                "position": 2,
                "name": "Later concept",
                "summary": "Declared too late for the earlier reference.",
                "depends_on": [],
            },
        ],
        [
            {
                "op": "add_subtopic",
                "client_ref": "new_subtopic_wrong_type",
                "parent_id": "m1",
                "position": 5,
                "title": "Wrong type target",
                "purpose": "Exercise typed local references.",
                "in_scope": [],
                "out_of_scope": [],
                "prerequisite_subtopic_ids": [],
            },
            {
                "op": "add_concept",
                "client_ref": "new_concept_uses_wrong_type",
                "parent_id": "m1_s1",
                "position": 2,
                "name": "Wrong dependency",
                "summary": "A subtopic reference cannot be a concept dependency.",
                "depends_on": ["new_subtopic_wrong_type"],
            },
        ],
    ],
)
def test_duplicate_forward_and_wrong_type_local_references_are_rejected(
    operations: list[dict[str, Any]],
) -> None:
    with pytest.raises(CourseModelValidationError) as exc_info:
        _reduce(_acceptance_inputs(), operations)

    assert exc_info.value.issues
    assert all({"code", "message"} <= set(issue) for issue in exc_info.value.issues)


@pytest.mark.parametrize(
    "operations",
    [
        [
            {
                "op": "add_coverage",
                "client_ref": "new_coverage_guessed",
                "parent_id": "m1_s1",
                "position": 2,
                "statement": "A guessed future concept must not resolve.",
                "concept_ids": ["c5"],
            },
            {
                "op": "add_concept",
                "client_ref": "new_concept_later",
                "parent_id": "m1_s1",
                "position": 2,
                "name": "Later concept",
                "summary": "This would receive c5 if the earlier guess were accepted.",
                "depends_on": [],
            },
        ],
        [
            {
                "op": "add_concept",
                "client_ref": "new_concept_guessed_dependency",
                "parent_id": "m1_s1",
                "position": 2,
                "name": "Guessed dependency",
                "summary": "A direct canonical guess is still a forward reference.",
                "depends_on": ["c5"],
            },
            {
                "op": "add_concept",
                "client_ref": "new_concept_dependency_target",
                "parent_id": "m1_s1",
                "position": 3,
                "name": "Dependency target",
                "summary": "This record has not been declared at the first operation.",
                "depends_on": [],
            },
        ],
        [
            {
                "op": "add_module",
                "client_ref": "new_module_guessed_prerequisite",
                "position": 2,
                "title": "Guessed prerequisite",
                "purpose": "A future canonical module is not currently referenceable.",
                "in_scope": [],
                "out_of_scope": [],
                "prerequisite_module_ids": ["m2"],
            },
            {
                "op": "add_module",
                "client_ref": "new_module_later",
                "position": 3,
                "title": "Later module",
                "purpose": "This module has not been declared at the first operation.",
                "in_scope": [],
                "out_of_scope": [],
                "prerequisite_module_ids": [],
            },
        ],
    ],
)
def test_guessed_future_canonical_ids_do_not_bypass_ordered_references(
    operations: list[dict[str, Any]],
) -> None:
    with pytest.raises(CourseModelValidationError) as exc_info:
        _reduce(_acceptance_inputs(), operations)

    assert exc_info.value.issues[0]["code"] == "operation_reference_not_found"


def test_unresolved_request_local_reference_in_existing_model_is_rejected() -> None:
    inputs = _acceptance_inputs()
    inputs["course_model"]["body"]["modules"][0]["prerequisite_module_ids"] = ["new_module_ghost"]

    with pytest.raises(CourseModelValidationError):
        _reduce(
            inputs,
            [{"op": "update_module", "target_id": "m1", "title": "Revised title"}],
        )


def test_request_local_looking_prose_is_not_treated_as_a_reference() -> None:
    reduction = _reduce(
        _acceptance_inputs(),
        [
            {
                "op": "update_module",
                "target_id": "m1",
                "title": "new_module_example",
            }
        ],
    )

    assert _module(reduction.candidate_body, "m1")["title"] == "new_module_example"


def test_only_typed_client_ref_patterns_are_reserved_in_reference_fields() -> None:
    inputs = _acceptance_inputs()
    inputs["course_model"]["body"]["modules"][0]["id"] = "new_curriculum"

    reduction = _reduce(
        inputs,
        [
            {
                "op": "update_module",
                "target_id": "new_curriculum",
                "title": "Historical identifier retained",
                "in_scope": ["new_product_launch", "new_module_scope"],
            }
        ],
    )

    module = _module(reduction.candidate_body, "new_curriculum")
    assert module["title"] == "Historical identifier retained"
    assert module["context"]["in_scope"] == [
        "new_product_launch",
        "new_module_scope",
    ]


@pytest.mark.parametrize(
    "operations",
    [
        [
            *_add_second_module_operations(),
            {
                "op": "update_module",
                "target_id": "m1",
                "prerequisite_module_ids": ["new_module_second"],
            },
        ],
        [
            {
                "op": "update_subtopic",
                "target_id": "m1_s1",
                "prerequisite_subtopic_ids": ["m1_s4"],
            }
        ],
        [
            {
                "op": "update_concept",
                "target_id": "c_m1_s1_1",
                "depends_on": ["c_m1_s2_1"],
            },
            {
                "op": "update_concept",
                "target_id": "c_m1_s2_1",
                "depends_on": ["c_m1_s1_1"],
            },
        ],
        [{"op": "remove_subtopic", "target_id": "m1_s1"}],
        [
            {
                "op": "update_coverage",
                "target_id": "cr_m1_s1_1",
                "concept_ids": ["missing_concept"],
            }
        ],
        [
            {
                "op": "update_module",
                "target_id": "m1",
                "prerequisite_module_ids": ["missing_module"],
            }
        ],
    ],
)
def test_cycles_and_dangling_references_reject_the_complete_candidate(
    operations: list[dict[str, Any]],
) -> None:
    with pytest.raises(CourseModelValidationError):
        _reduce(_acceptance_inputs(), operations)


@pytest.mark.parametrize(
    "operations",
    [
        [{"op": "remove_module", "target_id": "m1"}],
        [
            {"op": "remove_subtopic", "target_id": "m1_s4"},
            {"op": "remove_subtopic", "target_id": "m1_s3"},
            {"op": "remove_subtopic", "target_id": "m1_s2"},
            {"op": "remove_subtopic", "target_id": "m1_s1"},
        ],
    ],
)
def test_final_candidate_requires_a_module_and_a_subtopic_in_every_module(
    operations: list[dict[str, Any]],
) -> None:
    with pytest.raises(CourseModelValidationError):
        _reduce(_acceptance_inputs(), operations)


@pytest.mark.parametrize(
    "corrupt",
    [
        "duplicate_subtopic_order",
        "duplicate_coverage_id",
        "duplicate_rationale_id",
        "duplicate_source_id",
        "ambiguous_structural_id",
        "whitespace_module_title",
    ],
)
def test_authoritative_validator_rejects_duplicate_ids_and_order(corrupt: str) -> None:
    inputs = _acceptance_inputs()
    body = inputs["course_model"]["body"]
    if corrupt == "duplicate_subtopic_order":
        body["modules"][0]["subtopics"][1]["order"] = 1
    elif corrupt == "duplicate_coverage_id":
        body["modules"][0]["subtopics"][1]["coverage_requirements"][0]["id"] = "cr_m1_s1_1"
    elif corrupt == "duplicate_rationale_id":
        body["structural_rationale"].append(deepcopy(body["structural_rationale"][0]))
    elif corrupt == "duplicate_source_id":
        body["source_registry"].append(deepcopy(body["source_registry"][0]))
    elif corrupt == "ambiguous_structural_id":
        body["modules"][0]["subtopics"][0]["concepts"][0]["id"] = "m1"
        body["modules"][0]["subtopics"][0]["coverage_requirements"][0][
            "concept_ids"
        ] = ["m1"]
    else:
        body["modules"][0]["title"] = "   "

    with pytest.raises(CourseModelValidationError):
        _reduce(
            inputs,
            [{"op": "update_module", "target_id": "m1", "title": "Revised title"}],
        )


def test_transient_dangling_references_are_allowed_when_final_batch_repairs_them() -> None:
    inputs = _acceptance_inputs()

    body = _reduce(
        inputs,
        [
            {"op": "remove_subtopic", "target_id": "m1_s1"},
            {
                "op": "update_subtopic",
                "target_id": "m1_s2",
                "prerequisite_subtopic_ids": [],
            },
        ],
    ).candidate_body

    assert "m1_s1" not in _all_ids(body)
    assert _subtopic(body, "m1_s2")["prerequisite_subtopic_ids"] == []


@pytest.mark.parametrize(
    "source_id",
    ["coffee_g4", "coffee_g3", "comp_homebrew", "missing_source"],
)
def test_ineligible_source_assignments_are_rejected(source_id: str) -> None:
    with pytest.raises(CourseModelValidationError):
        _reduce(
            _acceptance_inputs(),
            [
                {
                    "op": "assign_sources",
                    "target_type": "subtopic",
                    "target_id": "m1_s1",
                    "source_ids": [source_id],
                }
            ],
        )


def test_explicitly_approved_but_contentless_source_is_ineligible() -> None:
    inputs = _acceptance_inputs()
    registry = inputs["approved_source_registry"]["body"]
    candidate = next(
        item
        for item in inputs["research_dossier"]["body"]["source_candidates"]
        if item["id"] == "coffee_g4"
    )
    registry["decision"]["selected_ids"].append(candidate["id"])
    registry["decision"]["approved_ids"].append(candidate["id"])
    registry["decision"]["rejected_ids"].remove(candidate["id"])
    registry["source_registry"].append(
        {
            key: candidate[key]
            for key in (
                "id",
                "title",
                "publisher",
                "source_type",
                "locator",
                "content_ref",
            )
        }
    )

    with pytest.raises(CourseModelValidationError) as exc_info:
        _reduce(
            inputs,
            [
                {
                    "op": "assign_sources",
                    "target_type": "subtopic",
                    "target_id": "m1_s1",
                    "source_ids": [candidate["id"]],
                }
            ],
        )

    assert any(
        issue["code"] == "approved_source_registry_record_invalid"
        for issue in exc_info.value.issues
    )


@pytest.mark.parametrize("source_kind", ["rejected", "absent", "competitor_only"])
def test_registry_cannot_forge_source_eligibility_outside_research_candidates(
    source_kind: str,
) -> None:
    inputs = _acceptance_inputs()
    dossier = inputs["research_dossier"]["body"]
    registry = inputs["approved_source_registry"]["body"]
    if source_kind == "rejected":
        candidate = next(
            item for item in dossier["source_candidates"] if item["id"] == "coffee_g3"
        )
        source_id = candidate["id"]
        forged = {
            key: candidate[key]
            for key in ("id", "title", "publisher", "source_type", "locator")
        }
        registry["decision"]["rejected_ids"].remove(source_id)
    elif source_kind == "competitor_only":
        competitor = next(
            item
            for item in dossier["competitor_findings"]
            if item["id"] == "comp_homebrew"
        )
        source_id = competitor["id"]
        forged = {
            "id": source_id,
            "title": competitor["offering"],
            "publisher": competitor["provider"],
            "source_type": "competitor outline",
            "locator": competitor["locator"],
        }
    else:
        source_id = "missing_source"
        forged = {
            "id": source_id,
            "title": "Untracked source",
            "publisher": "example.test",
            "source_type": "web page",
            "locator": "https://example.test/untracked",
        }
    forged["content_ref"] = f"sources/{source_id}.md"
    registry["decision"]["selected_ids"].append(source_id)
    registry["decision"]["approved_ids"].append(source_id)
    registry["source_registry"].append(forged)

    with pytest.raises(CourseModelValidationError) as exc_info:
        _reduce(
            inputs,
            [{"op": "update_module", "target_id": "m1", "title": "Revised title"}],
        )

    assert any(
        issue["code"]
        in {
            "approved_source_rejected_by_research",
            "approved_source_missing_from_research",
        }
        for issue in exc_info.value.issues
    )


def test_explicit_registry_approval_can_promote_a_proposed_research_candidate() -> None:
    inputs = _acceptance_inputs()
    candidate = next(
        item
        for item in inputs["research_dossier"]["body"]["source_candidates"]
        if item["id"] == "coffee_g1"
    )
    assert candidate["status"] == "proposed"

    reduction = _reduce(
        inputs,
        [{"op": "update_module", "target_id": "m1", "title": "Revised title"}],
    )

    assert "coffee_g1" in {
        source["id"] for source in reduction.candidate_body["source_registry"]
    }


def test_registry_cannot_replace_an_existing_research_content_pointer() -> None:
    inputs = _frm_inputs()
    for artifact_type in ("course_model", "approved_source_registry"):
        source = next(
            item
            for item in inputs[artifact_type]["body"]["source_registry"]
            if item["id"] == "g1"
        )
        source["content_ref"] = "sources/forged-g1.md"

    with pytest.raises(CourseModelValidationError) as exc_info:
        _reduce(
            inputs,
            [{"op": "update_module", "target_id": "m1", "title": "Revised title"}],
        )

    assert any(
        issue["code"] == "approved_source_research_metadata_mismatch"
        for issue in exc_info.value.issues
    )


@pytest.mark.parametrize(
    "operations",
    [
        [{"op": "set_course_outcome_links", "outcome_ids": ["co1"]}],
        [
            {
                "op": "set_course_outcome_links",
                "outcome_ids": ["co1", "co2", "co3", "missing_outcome"],
            }
        ],
        [
            {
                "op": "set_rationale_outcome_links",
                "target_id": "sr1",
                "outcome_ids": ["missing_outcome"],
            }
        ],
    ],
)
def test_incomplete_and_unknown_course_outcome_links_are_rejected(
    operations: list[dict[str, Any]],
) -> None:
    with pytest.raises(CourseModelValidationError):
        _reduce(_acceptance_inputs(), operations)


@pytest.mark.parametrize(
    "corruption",
    [
        "outcome_item",
        "outcome_statement",
        "outcome_whitespace",
        "duplicate_outcome_id",
        "source_candidate_item",
        "source_candidate_id",
        "assigned_node_id",
        "normalized_topic_item",
        "normalized_topic_label",
        "normalized_topic_whitespace",
        "registry_decision",
        "registry_selected_ids",
        "registry_approved_id",
    ],
)
def test_malformed_authority_artifacts_return_structured_issues(corruption: str) -> None:
    inputs = _acceptance_inputs()
    if corruption == "outcome_item":
        inputs["course_outcomes"]["body"]["outcomes"] = [None]
    elif corruption == "outcome_statement":
        del inputs["course_outcomes"]["body"]["outcomes"][0]["statement"]
    elif corruption == "outcome_whitespace":
        inputs["course_outcomes"]["body"]["outcomes"][0]["statement"] = "   "
    elif corruption == "duplicate_outcome_id":
        inputs["course_outcomes"]["body"]["outcomes"][1]["id"] = "co1"
    elif corruption == "source_candidate_item":
        inputs["research_dossier"]["body"]["source_candidates"] = [None]
    elif corruption == "source_candidate_id":
        del inputs["research_dossier"]["body"]["source_candidates"][0]["id"]
    elif corruption == "assigned_node_id":
        inputs["research_dossier"]["body"]["source_candidates"][0]["assigned_node_ids"] = [{}]
    elif corruption == "normalized_topic_item":
        inputs["research_dossier"]["body"]["normalized_topics"] = [None]
    elif corruption == "normalized_topic_label":
        del inputs["research_dossier"]["body"]["normalized_topics"][0]["label"]
    elif corruption == "normalized_topic_whitespace":
        inputs["research_dossier"]["body"]["normalized_topics"][0]["label"] = "   "
    elif corruption == "registry_decision":
        inputs["approved_source_registry"]["body"]["decision"] = []
    elif corruption == "registry_selected_ids":
        del inputs["approved_source_registry"]["body"]["decision"]["selected_ids"]
    else:
        inputs["approved_source_registry"]["body"]["decision"]["approved_ids"] = [{}]

    with pytest.raises(CourseModelValidationError) as exc_info:
        _reduce(
            inputs,
            [{"op": "update_module", "target_id": "m1", "title": "Revised title"}],
        )

    assert exc_info.value.issues
    assert any(
        any(marker in issue["code"] for marker in ("invalid", "duplicate", "blank"))
        for issue in exc_info.value.issues
    )


def test_generator_deduplicates_scope_values_before_shared_validation() -> None:
    inputs = _acceptance_inputs()
    brief = _load(ACCEPTANCE_ARTIFACTS / "brief.json")
    brief["body"]["in_scope"] = ["Practical Examples"]
    brief["body"]["must_have_topics"] = ["Practical Examples"]

    generated = build_course_model_artifact(
        brief,
        inputs["course_outcomes"],
        inputs["research_dossier"],
        approved_source_registry=inputs["approved_source_registry"],
    )

    validate_course_model_candidate(
        generated,
        course_outcomes=inputs["course_outcomes"],
        research_dossier=inputs["research_dossier"],
        approved_source_registry=inputs["approved_source_registry"],
    )
    for module in generated["body"]["modules"]:
        assert len(module["context"]["in_scope"]) == len(
            set(module["context"]["in_scope"])
        )
        for subtopic in module["subtopics"]:
            assert len(subtopic["context"]["in_scope"]) == len(
                set(subtopic["context"]["in_scope"])
            )


@pytest.mark.parametrize(
    "operation",
    [
        {"op": "update_module", "target_id": "m1", "title": "Coffee making Foundations"},
        {"op": "move_module", "target_id": "m1", "position": 1},
        {"op": "reorder_modules", "module_ids": ["m1"]},
        {
            "op": "reorder_subtopics",
            "parent_id": "m1",
            "subtopic_ids": ["m1_s1", "m1_s2", "m1_s3", "m1_s4"],
        },
        {
            "op": "assign_sources",
            "target_type": "subtopic",
            "target_id": "m1_s1",
            "source_ids": ["coffee_g1"],
        },
        {
            "op": "set_course_outcome_links",
            "outcome_ids": ["co1", "co2", "co3", "co4"],
        },
    ],
)
def test_each_operation_rejects_a_normalized_noop(operation: dict[str, Any]) -> None:
    with pytest.raises(CourseModelValidationError) as exc_info:
        _reduce(_acceptance_inputs(), [operation])

    assert exc_info.value.issues


def test_final_reversal_and_allocation_normalization_alone_are_rejected_as_noop() -> None:
    with pytest.raises(CourseModelValidationError):
        _reduce(
            _acceptance_inputs(),
            [
                {"op": "move_subtopic", "target_id": "m1_s4", "parent_id": "m1", "position": 1},
                {"op": "move_subtopic", "target_id": "m1_s4", "parent_id": "m1", "position": 4},
            ],
        )


@pytest.mark.parametrize(
    "operation",
    [
        {"op": "replace", "path": "/body/modules", "value": []},
        {"op": "update_module", "target_id": "m1", "title": "Changed", "invented": True},
        {
            "op": "assign_sources",
            "target_type": [],
            "target_id": "m1_s1",
            "source_ids": [],
        },
        {
            "op": "assign_sources",
            "target_type": {},
            "target_id": "m1_s1",
            "source_ids": [],
        },
        {
            "op": "assign_sources",
            "target_type": True,
            "target_id": "m1_s1",
            "source_ids": [],
        },
        {
            "op": "add_module",
            "client_ref": "new_module_client_id",
            "position": 2,
            "title": "Client-controlled ID",
            "purpose": "This must be rejected.",
            "in_scope": [],
            "out_of_scope": [],
            "prerequisite_module_ids": [],
            "id": "m99",
        },
    ],
)
def test_domain_reducer_rejects_arbitrary_or_non_strict_operations(
    operation: dict[str, Any],
) -> None:
    with pytest.raises(CourseModelValidationError) as exc_info:
        _reduce(_acceptance_inputs(), [operation])

    assert exc_info.value.issues
    assert all({"code", "message"} <= set(issue) for issue in exc_info.value.issues)
