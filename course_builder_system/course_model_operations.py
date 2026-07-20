"""Strict deterministic Course Model operation reduction and validation.

This module is the pure domain boundary for NC-401 through NC-403.  It owns
request-local references, durable ID allocation, ordered structural mutation, and
the authoritative schema-plus-semantic candidate check.  Persistence, locking, and
pipeline invalidation remain API service concerns.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from schema_validation import validate_json_schema

SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "course_model.v0.2.schema.json"
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
UNRESOLVED_REF_PATTERN = re.compile(r"^new_(module|subtopic|concept|coverage)_[a-z0-9_-]+$")

FAMILIES = ("module", "subtopic", "concept", "coverage")
CURSOR_FIELDS = {
    "module": "next_module_id",
    "subtopic": "next_subtopic_id",
    "concept": "next_concept_id",
    "coverage": "next_coverage_id",
}
CANONICAL_PATTERNS = {
    "module": re.compile(r"^m([1-9][0-9]*)$"),
    "subtopic": re.compile(r"^s([1-9][0-9]*)$"),
    "concept": re.compile(r"^c([1-9][0-9]*)$"),
    "coverage": re.compile(r"^cr([1-9][0-9]*)$"),
}
CANONICAL_PREFIXES = {
    "module": "m",
    "subtopic": "s",
    "concept": "c",
    "coverage": "cr",
}
CLIENT_REF_PATTERNS = {family: re.compile(rf"^new_{family}_[a-z0-9_-]+$") for family in FAMILIES}


class CourseModelValidationError(ValueError):
    """A deterministic Course Model operation or candidate check failed."""

    def __init__(self, issues: list[dict[str, Any]]) -> None:
        if not issues:
            raise ValueError("Course Model validation requires at least one issue")
        self.issues = issues
        super().__init__(str(issues[0]["message"]))


@dataclass(frozen=True)
class CourseModelReduction:
    """Pure result used by both preview and persistence paths."""

    candidate_artifact: dict[str, Any]
    candidate_body: dict[str, Any]
    allocated_ids: dict[str, str]
    change_records: list[dict[str, Any]]
    affected_records: dict[str, dict[str, list[str]]]


_OPERATION_FIELDS: dict[str, tuple[set[str], set[str]]] = {
    "add_module": (
        {
            "op",
            "client_ref",
            "position",
            "title",
            "purpose",
            "in_scope",
            "out_of_scope",
            "prerequisite_module_ids",
        },
        set(),
    ),
    "update_module": (
        {"op", "target_id"},
        {
            "title",
            "purpose",
            "in_scope",
            "out_of_scope",
            "prerequisite_module_ids",
        },
    ),
    "remove_module": ({"op", "target_id"}, set()),
    "move_module": ({"op", "target_id", "position"}, set()),
    "reorder_modules": ({"op", "module_ids"}, set()),
    "add_subtopic": (
        {
            "op",
            "client_ref",
            "parent_id",
            "position",
            "title",
            "purpose",
            "in_scope",
            "out_of_scope",
            "prerequisite_subtopic_ids",
        },
        set(),
    ),
    "update_subtopic": (
        {"op", "target_id"},
        {
            "title",
            "purpose",
            "in_scope",
            "out_of_scope",
            "prerequisite_subtopic_ids",
        },
    ),
    "remove_subtopic": ({"op", "target_id"}, set()),
    "move_subtopic": ({"op", "target_id", "parent_id", "position"}, set()),
    "reorder_subtopics": ({"op", "parent_id", "subtopic_ids"}, set()),
    "add_concept": (
        {"op", "client_ref", "parent_id", "position", "name", "summary", "depends_on"},
        set(),
    ),
    "update_concept": ({"op", "target_id"}, {"name", "summary", "depends_on"}),
    "remove_concept": ({"op", "target_id"}, set()),
    "add_coverage": (
        {"op", "client_ref", "parent_id", "position", "statement", "concept_ids"},
        set(),
    ),
    "update_coverage": ({"op", "target_id"}, {"statement", "concept_ids"}),
    "remove_coverage": ({"op", "target_id"}, set()),
    "assign_sources": ({"op", "target_type", "target_id", "source_ids"}, set()),
    "set_course_outcome_links": ({"op", "outcome_ids"}, set()),
    "set_rationale_outcome_links": ({"op", "target_id", "outcome_ids"}, set()),
}

_UPDATE_OPERATIONS = {
    "update_module",
    "update_subtopic",
    "update_concept",
    "update_coverage",
}


def normalize_course_model_allocation(
    course_model_or_body: dict[str, Any],
    *,
    previous_id_allocation: dict[str, Any] | None = None,
) -> dict[str, int]:
    """Return complete collision-safe cursors without mutating the supplied model.

    Historical models derive their first cursor from both family cardinality and
    recognized numeric IDs.  A present state is treated as durable history and may
    never fall below that derived floor or a separately supplied previous state.
    """
    body = _artifact_body(course_model_or_body)
    floors = _allocation_floors(body)
    state = body.get("id_allocation")
    issues: list[dict[str, Any]] = []
    if state is None:
        normalized = dict(floors)
    elif not isinstance(state, dict):
        raise CourseModelValidationError(
            [
                _issue(
                    "allocation_state_type",
                    "id_allocation must be an object.",
                    path="$.body.id_allocation",
                )
            ]
        )
    else:
        expected = set(CURSOR_FIELDS.values())
        missing = sorted(expected - set(state))
        extra = sorted(set(state) - expected)
        for field in missing:
            issues.append(
                _issue(
                    "allocation_cursor_missing",
                    f"Allocation state is missing {field!r}.",
                    field=field,
                    path=f"$.body.id_allocation.{field}",
                )
            )
        for field in extra:
            issues.append(
                _issue(
                    "allocation_cursor_unsupported",
                    f"Allocation state field {field!r} is not supported.",
                    field=field,
                    path=f"$.body.id_allocation.{field}",
                )
            )
        normalized = {}
        for family, field in CURSOR_FIELDS.items():
            value = state.get(field)
            if type(value) is not int or value < 1:
                issues.append(
                    _issue(
                        "allocation_cursor_invalid",
                        f"{field} must be a positive, non-boolean integer.",
                        record_type=family,
                        field=field,
                        path=f"$.body.id_allocation.{field}",
                    )
                )
                continue
            normalized[field] = value
            if value < floors[field]:
                issues.append(
                    _issue(
                        "allocation_cursor_below_floor",
                        f"{field} cannot be lower than the current ID floor {floors[field]}.",
                        record_type=family,
                        field=field,
                        path=f"$.body.id_allocation.{field}",
                    )
                )

    if previous_id_allocation is not None:
        for family, field in CURSOR_FIELDS.items():
            previous = previous_id_allocation.get(field)
            if type(previous) is not int or previous < 1:
                issues.append(
                    _issue(
                        "previous_allocation_cursor_invalid",
                        f"Previous {field} must be a positive, non-boolean integer.",
                        record_type=family,
                        field=field,
                    )
                )
            elif field in normalized and normalized[field] < previous:
                issues.append(
                    _issue(
                        "allocation_cursor_decreased",
                        f"{field} cannot decrease below its persisted value {previous}.",
                        record_type=family,
                        field=field,
                        path=f"$.body.id_allocation.{field}",
                    )
                )

    if issues:
        raise CourseModelValidationError(issues)
    return normalized


def carry_forward_course_model_allocation(
    course_model: dict[str, Any],
    previous_course_model: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return a generated model with prior allocation high-water marks preserved.

    A normal structure-stage rerun replaces the Course Model body.  Without this
    merge, its freshly derived cursors could reuse IDs that a prior typed decision
    allocated and later deleted.  The candidate's own floors still win when the
    regenerated structure contains a higher recognized numeric ID.
    """
    candidate = deepcopy(course_model)
    allocation = normalize_course_model_allocation(candidate)
    if previous_course_model is not None:
        previous = normalize_course_model_allocation(previous_course_model)
        previous_ids = {
            family: {record["id"] for record in records}
            for family, records in _records_by_family(_artifact_body(previous_course_model)).items()
        }
        reuse_issues: list[dict[str, Any]] = []
        for family, records in _records_by_family(candidate["body"]).items():
            cursor = previous[CURSOR_FIELDS[family]]
            for record in records:
                record_id = record["id"]
                match = CANONICAL_PATTERNS[family].fullmatch(record_id)
                if (
                    match is not None
                    and int(match.group(1)) < cursor
                    and record_id not in previous_ids[family]
                ):
                    reuse_issues.append(
                        _issue(
                            "course_model_id_reused",
                            f"Generated {family} ID {record_id!r} is below the prior "
                            "allocation cursor and was not retained from the prior model.",
                            record_type=family,
                            record_id=record_id,
                            field="id",
                        )
                    )
        if reuse_issues:
            raise CourseModelValidationError(reuse_issues)
        allocation = {
            field: max(allocation[field], previous[field]) for field in CURSOR_FIELDS.values()
        }
    candidate["body"]["id_allocation"] = allocation
    return candidate


def validate_course_model_candidate(
    course_model: dict[str, Any],
    *,
    course_outcomes: dict[str, Any],
    research_dossier: dict[str, Any],
    approved_source_registry: dict[str, Any],
    previous_id_allocation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one full candidate artifact and return it unchanged on success."""
    schema_issues = [
        _issue(
            "course_model_schema_invalid",
            item["message"],
            path=item["path"],
        )
        for item in validate_json_schema(course_model, _course_model_schema())
    ]
    if schema_issues:
        raise CourseModelValidationError(schema_issues)

    issues = _semantic_issues(
        course_model,
        course_outcomes=course_outcomes,
        research_dossier=research_dossier,
        approved_source_registry=approved_source_registry,
    )
    try:
        normalize_course_model_allocation(
            course_model,
            previous_id_allocation=previous_id_allocation,
        )
    except CourseModelValidationError as exc:
        issues.extend(exc.issues)
    if issues:
        raise CourseModelValidationError(issues)
    return course_model


def reduce_course_model_operations(
    course_model: dict[str, Any],
    operations: list[dict[str, Any]],
    *,
    course_outcomes: dict[str, Any],
    research_dossier: dict[str, Any],
    approved_source_registry: dict[str, Any],
    reject_noop: bool = True,
) -> CourseModelReduction:
    """Apply one ordered atomic operation batch and return a validated candidate."""
    if not isinstance(operations, list) or not operations:
        raise CourseModelValidationError(
            [
                _issue(
                    "operations_required",
                    "operations must be a non-empty list.",
                    field="operations",
                )
            ]
        )

    validate_course_model_candidate(
        course_model,
        course_outcomes=course_outcomes,
        research_dossier=research_dossier,
        approved_source_registry=approved_source_registry,
    )
    original_body = deepcopy(course_model["body"])
    candidate_body = deepcopy(original_body)
    allocation = normalize_course_model_allocation(candidate_body)
    candidate_body["id_allocation"] = allocation
    local_refs: dict[str, tuple[str, str]] = {}
    allocated_ids: dict[str, str] = {}
    change_records: list[dict[str, Any]] = []

    for index, raw_operation in enumerate(operations):
        operation = _normalize_operation(raw_operation, index=index)
        before = deepcopy(candidate_body)
        change = _apply_operation(
            candidate_body,
            operation,
            index=index,
            local_refs=local_refs,
            allocated_ids=allocated_ids,
        )
        _derive_orders(candidate_body)
        if reject_noop and candidate_body == before:
            raise CourseModelValidationError(
                [
                    _issue(
                        "course_model_operation_noop",
                        f"Operation {operation['op']!r} does not change the candidate.",
                        operation_index=index,
                        record_type=change.get("record_type"),
                        record_id=change.get("record_id"),
                    )
                ]
            )
        change_records.append(change)

    if reject_noop and _substantive_body(candidate_body) == _substantive_body(original_body):
        raise CourseModelValidationError(
            [
                _issue(
                    "course_model_batch_noop",
                    "Course Model operation batch has no final substantive effect.",
                    field="operations",
                )
            ]
        )

    candidate_artifact = deepcopy(course_model)
    candidate_artifact["body"] = candidate_body
    candidate_artifact["status"] = "draft"
    candidate_artifact["produced_by_step"] = "human"
    candidate_artifact["revision"] = int(course_model.get("revision", 0)) + 1
    candidate_artifact["revision_note"] = "Applied structured Course Model operations."
    validate_course_model_candidate(
        candidate_artifact,
        course_outcomes=course_outcomes,
        research_dossier=research_dossier,
        approved_source_registry=approved_source_registry,
        previous_id_allocation=course_model.get("body", {}).get("id_allocation"),
    )

    return CourseModelReduction(
        candidate_artifact=candidate_artifact,
        candidate_body=candidate_body,
        allocated_ids=allocated_ids,
        change_records=change_records,
        affected_records=_affected_records(
            original_body, candidate_body, course_model["course_id"]
        ),
    )


def _apply_operation(
    body: dict[str, Any],
    operation: dict[str, Any],
    *,
    index: int,
    local_refs: dict[str, tuple[str, str]],
    allocated_ids: dict[str, str],
) -> dict[str, Any]:
    name = operation["op"]
    if name == "add_module":
        prerequisites = _resolve_refs(
            operation["prerequisite_module_ids"],
            "module",
            local_refs,
            index,
            "prerequisite_module_ids",
        )
        record_id = _declare_and_allocate(
            body, operation["client_ref"], "module", local_refs, allocated_ids, index
        )
        _insert(
            body["modules"],
            operation["position"],
            {
                "id": record_id,
                "order": 1,
                "title": operation["title"],
                "context": _context_from_operation(operation),
                "prerequisite_module_ids": prerequisites,
                "subtopics": [],
            },
            index=index,
            field="position",
        )
        return _change(index, name, "module", record_id, "added")
    if name == "update_module":
        record_id = _resolve_ref(operation["target_id"], "module", local_refs, index, "target_id")
        module = _require_module(body, record_id, index)
        _update_context_record(module, operation)
        if "prerequisite_module_ids" in operation:
            module["prerequisite_module_ids"] = _resolve_refs(
                operation["prerequisite_module_ids"],
                "module",
                local_refs,
                index,
                "prerequisite_module_ids",
            )
        return _change(index, name, "module", record_id, "updated")
    if name == "remove_module":
        record_id = _resolve_ref(operation["target_id"], "module", local_refs, index, "target_id")
        _remove_record(body["modules"], record_id, "module", index)
        return _change(index, name, "module", record_id, "removed")
    if name == "move_module":
        record_id = _resolve_ref(operation["target_id"], "module", local_refs, index, "target_id")
        _move_record(body["modules"], record_id, operation["position"], "module", index)
        return _change(index, name, "module", record_id, "moved")
    if name == "reorder_modules":
        ids = _resolve_refs(operation["module_ids"], "module", local_refs, index, "module_ids")
        body["modules"] = _reorder_complete(body["modules"], ids, "module", index)
        return _change(index, name, "module", None, "reordered", record_ids=ids)

    if name == "add_subtopic":
        parent_id = _resolve_ref(operation["parent_id"], "module", local_refs, index, "parent_id")
        parent = _require_module(body, parent_id, index)
        prerequisites = _resolve_refs(
            operation["prerequisite_subtopic_ids"],
            "subtopic",
            local_refs,
            index,
            "prerequisite_subtopic_ids",
        )
        record_id = _declare_and_allocate(
            body, operation["client_ref"], "subtopic", local_refs, allocated_ids, index
        )
        _insert(
            parent["subtopics"],
            operation["position"],
            {
                "id": record_id,
                "order": 1,
                "title": operation["title"],
                "context": _context_from_operation(operation),
                "prerequisite_subtopic_ids": prerequisites,
                "concepts": [],
                "coverage_requirements": [],
                "approved_source_ids": [],
            },
            index=index,
            field="position",
        )
        return _change(index, name, "subtopic", record_id, "added", parent_id=parent_id)
    if name == "update_subtopic":
        record_id = _resolve_ref(operation["target_id"], "subtopic", local_refs, index, "target_id")
        _, subtopic = _require_subtopic(body, record_id, index)
        _update_context_record(subtopic, operation)
        if "prerequisite_subtopic_ids" in operation:
            subtopic["prerequisite_subtopic_ids"] = _resolve_refs(
                operation["prerequisite_subtopic_ids"],
                "subtopic",
                local_refs,
                index,
                "prerequisite_subtopic_ids",
            )
        return _change(index, name, "subtopic", record_id, "updated")
    if name == "remove_subtopic":
        record_id = _resolve_ref(operation["target_id"], "subtopic", local_refs, index, "target_id")
        parent, _ = _require_subtopic(body, record_id, index)
        _remove_record(parent["subtopics"], record_id, "subtopic", index)
        return _change(index, name, "subtopic", record_id, "removed", parent_id=parent["id"])
    if name == "move_subtopic":
        record_id = _resolve_ref(operation["target_id"], "subtopic", local_refs, index, "target_id")
        source_parent, subtopic = _require_subtopic(body, record_id, index)
        target_id = _resolve_ref(operation["parent_id"], "module", local_refs, index, "parent_id")
        target_parent = _require_module(body, target_id, index)
        source_parent["subtopics"].remove(subtopic)
        _insert(
            target_parent["subtopics"],
            operation["position"],
            subtopic,
            index=index,
            field="position",
        )
        return _change(index, name, "subtopic", record_id, "moved", parent_id=target_id)
    if name == "reorder_subtopics":
        parent_id = _resolve_ref(operation["parent_id"], "module", local_refs, index, "parent_id")
        parent = _require_module(body, parent_id, index)
        ids = _resolve_refs(
            operation["subtopic_ids"], "subtopic", local_refs, index, "subtopic_ids"
        )
        parent["subtopics"] = _reorder_complete(parent["subtopics"], ids, "subtopic", index)
        return _change(
            index, name, "subtopic", None, "reordered", parent_id=parent_id, record_ids=ids
        )

    if name == "add_concept":
        parent_id = _resolve_ref(operation["parent_id"], "subtopic", local_refs, index, "parent_id")
        _, parent = _require_subtopic(body, parent_id, index)
        dependencies = _resolve_refs(
            operation["depends_on"], "concept", local_refs, index, "depends_on"
        )
        record_id = _declare_and_allocate(
            body, operation["client_ref"], "concept", local_refs, allocated_ids, index
        )
        _insert(
            parent["concepts"],
            operation["position"],
            {
                "id": record_id,
                "name": operation["name"],
                "summary": operation["summary"],
                "depends_on": dependencies,
                "source_ids": [],
            },
            index=index,
            field="position",
        )
        return _change(index, name, "concept", record_id, "added", parent_id=parent_id)
    if name == "update_concept":
        record_id = _resolve_ref(operation["target_id"], "concept", local_refs, index, "target_id")
        _, concept = _require_concept(body, record_id, index)
        for field in ("name", "summary"):
            if field in operation:
                concept[field] = operation[field]
        if "depends_on" in operation:
            concept["depends_on"] = _resolve_refs(
                operation["depends_on"], "concept", local_refs, index, "depends_on"
            )
        return _change(index, name, "concept", record_id, "updated")
    if name == "remove_concept":
        record_id = _resolve_ref(operation["target_id"], "concept", local_refs, index, "target_id")
        parent, _ = _require_concept(body, record_id, index)
        _remove_record(parent["concepts"], record_id, "concept", index)
        return _change(index, name, "concept", record_id, "removed", parent_id=parent["id"])

    if name == "add_coverage":
        parent_id = _resolve_ref(operation["parent_id"], "subtopic", local_refs, index, "parent_id")
        _, parent = _require_subtopic(body, parent_id, index)
        concept_ids = _resolve_refs(
            operation["concept_ids"], "concept", local_refs, index, "concept_ids"
        )
        record_id = _declare_and_allocate(
            body, operation["client_ref"], "coverage", local_refs, allocated_ids, index
        )
        _insert(
            parent["coverage_requirements"],
            operation["position"],
            {
                "id": record_id,
                "statement": operation["statement"],
                "concept_ids": concept_ids,
                "source_ids": [],
            },
            index=index,
            field="position",
        )
        return _change(index, name, "coverage", record_id, "added", parent_id=parent_id)
    if name == "update_coverage":
        record_id = _resolve_ref(operation["target_id"], "coverage", local_refs, index, "target_id")
        _, coverage = _require_coverage(body, record_id, index)
        if "statement" in operation:
            coverage["statement"] = operation["statement"]
        if "concept_ids" in operation:
            coverage["concept_ids"] = _resolve_refs(
                operation["concept_ids"], "concept", local_refs, index, "concept_ids"
            )
        return _change(index, name, "coverage", record_id, "updated")
    if name == "remove_coverage":
        record_id = _resolve_ref(operation["target_id"], "coverage", local_refs, index, "target_id")
        parent, _ = _require_coverage(body, record_id, index)
        _remove_record(parent["coverage_requirements"], record_id, "coverage", index)
        return _change(index, name, "coverage", record_id, "removed", parent_id=parent["id"])

    if name == "assign_sources":
        family = operation["target_type"]
        record_id = _resolve_ref(operation["target_id"], family, local_refs, index, "target_id")
        if family == "subtopic":
            _, target = _require_subtopic(body, record_id, index)
            target["approved_source_ids"] = operation["source_ids"]
        elif family == "concept":
            _, target = _require_concept(body, record_id, index)
            target["source_ids"] = operation["source_ids"]
        else:
            _, target = _require_coverage(body, record_id, index)
            target["source_ids"] = operation["source_ids"]
        return _change(index, name, family, record_id, "sources_assigned")
    if name == "set_course_outcome_links":
        body["course_metadata"]["course_outcome_ids"] = operation["outcome_ids"]
        return _change(index, name, "course", None, "outcome_links_set")
    if name == "set_rationale_outcome_links":
        target_id = operation["target_id"]
        rationale = next(
            (item for item in body["structural_rationale"] if item["id"] == target_id),
            None,
        )
        if rationale is None:
            raise CourseModelValidationError([_unknown_record_issue("rationale", target_id, index)])
        rationale["related_outcome_ids"] = operation["outcome_ids"]
        return _change(index, name, "rationale", target_id, "outcome_links_set")
    raise AssertionError(f"Unhandled Course Model operation: {name}")


def _normalize_operation(raw: Any, *, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise CourseModelValidationError(
            [_issue("operation_type", "Each operation must be an object.", operation_index=index)]
        )
    name = raw.get("op")
    if not isinstance(name, str) or name not in _OPERATION_FIELDS:
        raise CourseModelValidationError(
            [
                _issue(
                    "unsupported_course_model_operation",
                    f"Unsupported Course Model operation {name!r}.",
                    operation_index=index,
                    field="op",
                )
            ]
        )
    required, optional = _OPERATION_FIELDS[name]
    issues: list[dict[str, Any]] = []
    for field in sorted(required - set(raw)):
        issues.append(
            _issue(
                "operation_field_missing",
                f"Operation {name!r} is missing required field {field!r}.",
                operation_index=index,
                field=field,
            )
        )
    for field in sorted(set(raw) - required - optional):
        issues.append(
            _issue(
                "unsupported_operation_field",
                f"Operation {name!r} does not support field {field!r}.",
                operation_index=index,
                field=field,
            )
        )
    if name in _UPDATE_OPERATIONS and not (set(raw) & optional):
        issues.append(
            _issue(
                "update_fields_required",
                f"Operation {name!r} must change at least one editable field.",
                operation_index=index,
            )
        )
    if issues:
        raise CourseModelValidationError(issues)

    operation = dict(raw)
    for field in ("position",):
        if field in operation and (type(operation[field]) is not int or operation[field] < 1):
            issues.append(
                _issue(
                    "operation_position_invalid",
                    "position must be a positive, non-boolean integer.",
                    operation_index=index,
                    field=field,
                )
            )

    text_limits = {
        "title": 200,
        "purpose": 500,
        "name": 150,
        "summary": 400,
        "statement": 300,
    }
    for field, maximum in text_limits.items():
        if field in operation:
            operation[field] = _normalize_text(
                operation[field], maximum, field=field, index=index, issues=issues
            )
    for field in ("in_scope", "out_of_scope"):
        if field in operation:
            operation[field] = _normalize_string_list(
                operation[field],
                field=field,
                index=index,
                issues=issues,
                maximum=180,
                allow_local_refs=False,
            )

    id_list_families = {
        "prerequisite_module_ids": "module",
        "module_ids": "module",
        "prerequisite_subtopic_ids": "subtopic",
        "subtopic_ids": "subtopic",
        "depends_on": "concept",
        "concept_ids": "concept",
    }
    for field, family in id_list_families.items():
        if field in operation:
            operation[field] = _normalize_id_list(
                operation[field], field=field, index=index, issues=issues, family=family
            )
    for field in ("source_ids", "outcome_ids"):
        if field in operation:
            operation[field] = _normalize_id_list(
                operation[field], field=field, index=index, issues=issues, family=None
            )

    add_family = {
        "add_module": "module",
        "add_subtopic": "subtopic",
        "add_concept": "concept",
        "add_coverage": "coverage",
    }.get(name)
    if add_family is not None:
        client_ref = operation.get("client_ref")
        if (
            not isinstance(client_ref, str)
            or CLIENT_REF_PATTERNS[add_family].fullmatch(client_ref) is None
        ):
            issues.append(
                _issue(
                    "client_ref_invalid",
                    f"client_ref must begin with new_{add_family}_ and contain "
                    "lowercase ID characters.",
                    operation_index=index,
                    field="client_ref",
                    record_type=add_family,
                )
            )

    for field in ("target_id", "parent_id"):
        if field in operation:
            value = operation[field]
            if not isinstance(value, str) or ID_PATTERN.fullmatch(value) is None:
                issues.append(
                    _issue(
                        "operation_id_invalid",
                        f"{field} must be a valid lowercase identifier.",
                        operation_index=index,
                        field=field,
                    )
                )
    target_type = operation.get("target_type")
    if name == "assign_sources" and (
        not isinstance(target_type, str) or target_type not in {"subtopic", "concept", "coverage"}
    ):
        issues.append(
            _issue(
                "source_target_type_invalid",
                "assign_sources target_type must be subtopic, concept, or coverage.",
                operation_index=index,
                field="target_type",
            )
        )
    if issues:
        raise CourseModelValidationError(issues)
    return operation


def _semantic_issues(
    course_model: dict[str, Any],
    *,
    course_outcomes: dict[str, Any],
    research_dossier: dict[str, Any],
    approved_source_registry: dict[str, Any],
) -> list[dict[str, Any]]:
    body = course_model["body"]
    issues: list[dict[str, Any]] = []
    course_id = course_model["course_id"]
    for artifact, label in (
        (course_outcomes, "course_outcomes"),
        (research_dossier, "research_dossier"),
        (approved_source_registry, "approved_source_registry"),
    ):
        if artifact.get("course_id") != course_id:
            issues.append(
                _issue(
                    "course_id_mismatch",
                    f"{label} and Course Model course_id values differ.",
                    record_type=label,
                    field="course_id",
                )
            )

    outcomes_body = _authority_body(course_outcomes, "course_outcomes", issues)
    outcome_records = _authority_object_list(
        outcomes_body,
        "outcomes",
        "course_outcomes",
        issues,
    )
    research_body = _authority_body(research_dossier, "research_dossier", issues)
    research_candidates = _authority_object_list(
        research_body,
        "source_candidates",
        "research_dossier",
        issues,
    )
    normalized_topics = _authority_object_list(
        research_body,
        "normalized_topics",
        "research_dossier",
        issues,
    )

    modules = body["modules"]
    subtopics = [subtopic for module in modules for subtopic in module["subtopics"]]
    concepts = [concept for subtopic in subtopics for concept in subtopic["concepts"]]
    coverage = [
        requirement for subtopic in subtopics for requirement in subtopic["coverage_requirements"]
    ]
    rationales = body["structural_rationale"]
    sources = body["source_registry"]
    collections = {
        "module": modules,
        "subtopic": subtopics,
        "concept": concepts,
        "coverage": coverage,
        "rationale": rationales,
        "source": sources,
    }
    for family, records in collections.items():
        seen: set[str] = set()
        for record in records:
            record_id = record["id"]
            if record_id in seen:
                issues.append(
                    _issue(
                        f"duplicate_{family}_id",
                        f"Duplicate {family} ID {record_id!r}.",
                        record_type=family,
                        record_id=record_id,
                        field="id",
                    )
                )
            seen.add(record_id)

    module_ids = {module["id"] for module in modules}
    subtopic_ids = {subtopic["id"] for subtopic in subtopics}
    concept_ids = {concept["id"] for concept in concepts}
    source_ids = {source["id"] for source in sources}

    module_dependencies: dict[str, list[str]] = {}
    for expected_order, module in enumerate(modules, start=1):
        module_id = module["id"]
        if module["order"] != expected_order:
            issues.append(
                _issue(
                    "module_order_invalid",
                    f"Module {module_id} must have order {expected_order}.",
                    record_type="module",
                    record_id=module_id,
                    field="order",
                )
            )
        module_dependencies[module_id] = module["prerequisite_module_ids"]
        issues.extend(
            _reference_issues(
                module["prerequisite_module_ids"],
                module_ids,
                owner_type="module",
                owner_id=module_id,
                field="prerequisite_module_ids",
                self_id=module_id,
            )
        )
        for expected_subtopic_order, subtopic in enumerate(module["subtopics"], start=1):
            if subtopic["order"] != expected_subtopic_order:
                issues.append(
                    _issue(
                        "subtopic_order_invalid",
                        f"Subtopic {subtopic['id']} must have order {expected_subtopic_order}.",
                        record_type="subtopic",
                        record_id=subtopic["id"],
                        field="order",
                    )
                )

    subtopic_dependencies: dict[str, list[str]] = {}
    concept_dependencies: dict[str, list[str]] = {}
    for subtopic in subtopics:
        subtopic_id = subtopic["id"]
        subtopic_dependencies[subtopic_id] = subtopic["prerequisite_subtopic_ids"]
        issues.extend(
            _reference_issues(
                subtopic["prerequisite_subtopic_ids"],
                subtopic_ids,
                owner_type="subtopic",
                owner_id=subtopic_id,
                field="prerequisite_subtopic_ids",
                self_id=subtopic_id,
            )
        )
        approved_ids = set(subtopic["approved_source_ids"])
        issues.extend(
            _reference_issues(
                subtopic["approved_source_ids"],
                source_ids,
                owner_type="subtopic",
                owner_id=subtopic_id,
                field="approved_source_ids",
            )
        )
        local_concept_ids = {concept["id"] for concept in subtopic["concepts"]}
        for concept in subtopic["concepts"]:
            concept_id = concept["id"]
            concept_dependencies[concept_id] = concept["depends_on"]
            issues.extend(
                _reference_issues(
                    concept["depends_on"],
                    concept_ids,
                    owner_type="concept",
                    owner_id=concept_id,
                    field="depends_on",
                    self_id=concept_id,
                )
            )
            for source_id in concept["source_ids"]:
                if source_id not in approved_ids:
                    issues.append(
                        _issue(
                            "concept_source_not_assigned_to_subtopic",
                            f"Concept {concept_id} source {source_id} is not assigned "
                            f"to {subtopic_id}.",
                            record_type="concept",
                            record_id=concept_id,
                            field="source_ids",
                        )
                    )
        for requirement in subtopic["coverage_requirements"]:
            requirement_id = requirement["id"]
            issues.extend(
                _reference_issues(
                    requirement["concept_ids"],
                    local_concept_ids,
                    owner_type="coverage",
                    owner_id=requirement_id,
                    field="concept_ids",
                )
            )
            for source_id in requirement["source_ids"]:
                if source_id not in approved_ids:
                    issues.append(
                        _issue(
                            "coverage_source_not_assigned_to_subtopic",
                            f"Coverage {requirement_id} source {source_id} is not "
                            f"assigned to {subtopic_id}.",
                            record_type="coverage",
                            record_id=requirement_id,
                            field="source_ids",
                        )
                    )

    for family, dependencies in (
        ("module", module_dependencies),
        ("subtopic", subtopic_dependencies),
        ("concept", concept_dependencies),
    ):
        cycle = _find_cycle(dependencies)
        if cycle:
            issues.append(
                _issue(
                    f"{family}_dependency_cycle",
                    f"{family.title()} dependency cycle: {' -> '.join(cycle)}.",
                    record_type=family,
                )
            )

    outcome_ids = [item.get("id") for item in outcome_records]
    for index, outcome_id in enumerate(outcome_ids):
        if not isinstance(outcome_id, str) or ID_PATTERN.fullmatch(outcome_id) is None:
            issues.append(
                _issue(
                    "course_outcomes_record_invalid",
                    "Every current Outcome must have a valid string ID.",
                    record_type="course_outcome",
                    path=f"$.course_outcomes.body.outcomes[{index}].id",
                )
            )
    valid_outcomes = {item for item in outcome_ids if isinstance(item, str)}
    linked_outcomes = body["course_metadata"]["course_outcome_ids"]
    if set(linked_outcomes) != valid_outcomes:
        issues.append(
            _issue(
                "course_outcome_links_incomplete",
                "Course Model-wide Outcome links must contain every current Outcome exactly once.",
                record_type="course",
                record_id=course_id,
                field="course_outcome_ids",
            )
        )
    for rationale in rationales:
        issues.extend(
            _reference_issues(
                rationale["related_outcome_ids"],
                valid_outcomes,
                owner_type="rationale",
                owner_id=rationale["id"],
                field="related_outcome_ids",
            )
        )

    authoritative_sources, allowed_source_ids, source_authority_issues = _source_authority(
        approved_source_registry
    )
    issues.extend(source_authority_issues)
    for source in sources:
        source_id = source["id"]
        if source_id not in allowed_source_ids:
            issues.append(
                _issue(
                    "source_not_assignable",
                    f"Course Model source {source_id!r} is not explicitly approved with content.",
                    record_type="source",
                    record_id=source_id,
                    field="id",
                )
            )
        elif any(
            source.get(field) != authoritative_sources[source_id].get(field)
            for field in ("id", "title", "publisher", "source_type", "locator", "content_ref")
        ):
            issues.append(
                _issue(
                    "source_metadata_mismatch",
                    f"Course Model source metadata for {source_id!r} differs from "
                    "the approved registry.",
                    record_type="source",
                    record_id=source_id,
                )
            )
    for family, records, field in (
        ("subtopic", subtopics, "approved_source_ids"),
        ("concept", concepts, "source_ids"),
        ("coverage", coverage, "source_ids"),
    ):
        for record in records:
            for source_id in record[field]:
                if source_id not in allowed_source_ids:
                    issues.append(
                        _issue(
                            "source_not_assignable",
                            f"{family.title()} {record['id']} uses ineligible "
                            f"source {source_id!r}.",
                            record_type=family,
                            record_id=record["id"],
                            field=field,
                        )
                    )

    valid_nodes = module_ids | subtopic_ids
    for candidate_index, candidate in enumerate(research_candidates):
        assigned_node_ids = candidate.get("assigned_node_ids", [])
        if not isinstance(assigned_node_ids, list):
            issues.append(
                _issue(
                    "research_dossier_record_invalid",
                    "Research assigned_node_ids must be a list.",
                    record_type="research_source",
                    record_id=candidate.get("id"),
                    path=(
                        "$.research_dossier.body.source_candidates"
                        f"[{candidate_index}].assigned_node_ids"
                    ),
                )
            )
            continue
        for node_index, node_id in enumerate(assigned_node_ids):
            if not isinstance(node_id, str):
                issues.append(
                    _issue(
                        "research_dossier_record_invalid",
                        "Every assigned node ID must be a string.",
                        record_type="research_source",
                        record_id=candidate.get("id"),
                        path=(
                            "$.research_dossier.body.source_candidates"
                            f"[{candidate_index}].assigned_node_ids[{node_index}]"
                        ),
                    )
                )
                continue
            if node_id not in valid_nodes:
                issues.append(
                    _issue(
                        "research_assignment_unknown_node",
                        f"Research source {candidate.get('id')} is assigned to "
                        f"unknown node {node_id!r}.",
                        record_type="research_source",
                        record_id=candidate.get("id"),
                        field="assigned_node_ids",
                    )
                )
    topic_ids: set[str] = set()
    for index, item in enumerate(normalized_topics):
        topic_id = item.get("id")
        if not isinstance(topic_id, str) or ID_PATTERN.fullmatch(topic_id) is None:
            issues.append(
                _issue(
                    "research_dossier_record_invalid",
                    "Every normalized research topic must have a valid string ID.",
                    record_type="research_topic",
                    path=f"$.research_dossier.body.normalized_topics[{index}].id",
                )
            )
        else:
            topic_ids.add(topic_id)
    for rationale in rationales:
        issues.extend(
            _reference_issues(
                rationale["related_topic_ids"],
                topic_ids,
                owner_type="rationale",
                owner_id=rationale["id"],
                field="related_topic_ids",
            )
        )

    for path, value in _request_local_reference_values(body):
        if UNRESOLVED_REF_PATTERN.fullmatch(value):
            issues.append(
                _issue(
                    "unresolved_request_local_reference",
                    f"Request-local reference {value!r} must not be persisted.",
                    path=path,
                )
            )
    for path in _banned_source_text_paths(body):
        issues.append(
            _issue(
                "embedded_source_text_forbidden",
                "Course Model stores source pointers, not embedded source text.",
                path=path,
            )
        )
    return issues


def _source_authority(
    approved_source_registry: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], set[str], list[dict[str, Any]]]:
    body = approved_source_registry.get("body", {})
    issues: list[dict[str, Any]] = []
    if not isinstance(body, dict):
        return (
            {},
            set(),
            [
                _issue(
                    "approved_source_registry_invalid",
                    "Approved source registry body must be an object.",
                    record_type="approved_source_registry",
                    path="$.approved_source_registry.body",
                )
            ],
        )
    decision = body.get("decision", {})
    if not isinstance(decision, dict):
        issues.append(
            _issue(
                "approved_source_registry_invalid",
                "Approved source registry decision must be an object.",
                record_type="approved_source_registry",
                path="$.approved_source_registry.body.decision",
            )
        )
        decision = {}
    records = body.get("source_registry", [])
    approved = decision.get("approved_ids", [])
    rejected = decision.get("rejected_ids", [])
    if (
        not isinstance(records, list)
        or not isinstance(approved, list)
        or not isinstance(rejected, list)
    ):
        issues.append(
            _issue(
                "approved_source_registry_invalid",
                "Approved source registry must expose decision.approved_ids, "
                "decision.rejected_ids, and source_registry lists.",
                record_type="approved_source_registry",
            )
        )
        return {}, set(), issues
    by_id: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            issues.append(
                _issue(
                    "approved_source_registry_record_invalid",
                    "Every approved source registry record must be an object with a string ID.",
                    record_type="approved_source_registry",
                    path=f"$.approved_source_registry.body.source_registry[{index}]",
                )
            )
            continue
        if record["id"] in by_id:
            issues.append(
                _issue(
                    "approved_source_registry_duplicate_id",
                    f"Approved source registry repeats source {record['id']!r}.",
                    record_type="approved_source_registry",
                    record_id=record["id"],
                )
            )
        by_id[record["id"]] = record
    for index, source_id in enumerate(approved):
        if not isinstance(source_id, str):
            issues.append(
                _issue(
                    "approved_source_registry_record_invalid",
                    "Every approved source ID must be a string.",
                    record_type="approved_source_registry",
                    path=(f"$.approved_source_registry.body.decision.approved_ids[{index}]"),
                )
            )
    rejected_ids: set[str] = set()
    for index, source_id in enumerate(rejected):
        if not isinstance(source_id, str):
            issues.append(
                _issue(
                    "approved_source_registry_record_invalid",
                    "Every rejected source ID must be a string.",
                    record_type="approved_source_registry",
                    path=(f"$.approved_source_registry.body.decision.rejected_ids[{index}]"),
                )
            )
        else:
            rejected_ids.add(source_id)
    allowed = {
        source_id
        for source_id in approved
        if isinstance(source_id, str)
        and source_id in by_id
        and source_id not in rejected_ids
        and isinstance(by_id[source_id].get("content_ref"), str)
        and bool(by_id[source_id]["content_ref"].strip())
    }
    return by_id, allowed, issues


def _authority_body(
    artifact: dict[str, Any],
    artifact_type: str,
    issues: list[dict[str, Any]],
) -> dict[str, Any]:
    body = artifact.get("body")
    if isinstance(body, dict):
        return body
    issues.append(
        _issue(
            f"{artifact_type}_invalid",
            f"{artifact_type} body must be an object.",
            record_type=artifact_type,
            path=f"$.{artifact_type}.body",
        )
    )
    return {}


def _authority_object_list(
    body: dict[str, Any],
    field: str,
    artifact_type: str,
    issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    values = body.get(field)
    if not isinstance(values, list):
        issues.append(
            _issue(
                f"{artifact_type}_invalid",
                f"{artifact_type}.{field} must be a list.",
                record_type=artifact_type,
                field=field,
                path=f"$.{artifact_type}.body.{field}",
            )
        )
        return []
    records: list[dict[str, Any]] = []
    for index, value in enumerate(values):
        if not isinstance(value, dict):
            issues.append(
                _issue(
                    f"{artifact_type}_record_invalid",
                    f"Every {artifact_type}.{field} item must be an object.",
                    record_type=artifact_type,
                    field=field,
                    path=f"$.{artifact_type}.body.{field}[{index}]",
                )
            )
        else:
            records.append(value)
    return records


def _allocation_floors(body: dict[str, Any]) -> dict[str, int]:
    records = _records_by_family(body)
    floors: dict[str, int] = {}
    for family in FAMILIES:
        numeric = [
            int(match.group(1))
            for record in records[family]
            if isinstance(record.get("id"), str)
            and (match := CANONICAL_PATTERNS[family].fullmatch(record["id"])) is not None
        ]
        floors[CURSOR_FIELDS[family]] = max(len(records[family]), max(numeric, default=0)) + 1
    return floors


def _declare_and_allocate(
    body: dict[str, Any],
    client_ref: str,
    family: str,
    local_refs: dict[str, tuple[str, str]],
    allocated_ids: dict[str, str],
    index: int,
) -> str:
    if client_ref in local_refs:
        raise CourseModelValidationError(
            [
                _issue(
                    "duplicate_client_ref",
                    f"client_ref {client_ref!r} was already declared.",
                    operation_index=index,
                    record_type=family,
                    field="client_ref",
                )
            ]
        )
    cursor = body["id_allocation"]
    field = CURSOR_FIELDS[family]
    existing = {record["id"] for record in _records_by_family(body)[family]}
    number = cursor[field]
    while f"{CANONICAL_PREFIXES[family]}{number}" in existing:
        number += 1
    canonical_id = f"{CANONICAL_PREFIXES[family]}{number}"
    cursor[field] = number + 1
    local_refs[client_ref] = (family, canonical_id)
    allocated_ids[client_ref] = canonical_id
    return canonical_id


def _resolve_ref(
    value: str,
    family: str,
    local_refs: dict[str, tuple[str, str]],
    index: int,
    field: str,
) -> str:
    if value in local_refs:
        declared_family, canonical = local_refs[value]
        if declared_family != family:
            raise CourseModelValidationError(
                [
                    _issue(
                        "request_local_reference_wrong_type",
                        f"{value!r} declares a {declared_family}, not a {family}.",
                        operation_index=index,
                        record_type=family,
                        field=field,
                    )
                ]
            )
        return canonical
    if value.startswith("new_"):
        raise CourseModelValidationError(
            [
                _issue(
                    "request_local_reference_unresolved",
                    f"Request-local reference {value!r} must be declared by an "
                    "earlier add operation.",
                    operation_index=index,
                    record_type=family,
                    field=field,
                )
            ]
        )
    return value


def _resolve_refs(
    values: list[str],
    family: str,
    local_refs: dict[str, tuple[str, str]],
    index: int,
    field: str,
) -> list[str]:
    resolved = [_resolve_ref(value, family, local_refs, index, field) for value in values]
    if len(resolved) != len(set(resolved)):
        raise CourseModelValidationError(
            [
                _issue(
                    "resolved_reference_duplicate",
                    f"{field} resolves to duplicate IDs.",
                    operation_index=index,
                    record_type=family,
                    field=field,
                )
            ]
        )
    return resolved


def _normalize_text(
    value: Any,
    maximum: int,
    *,
    field: str,
    index: int,
    issues: list[dict[str, Any]],
) -> Any:
    if not isinstance(value, str):
        issues.append(
            _issue(
                "operation_text_type",
                f"{field} must be a string.",
                operation_index=index,
                field=field,
            )
        )
        return value
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        issues.append(
            _issue(
                "operation_text_bounds",
                f"{field} must contain 1 to {maximum} characters.",
                operation_index=index,
                field=field,
            )
        )
    return normalized


def _normalize_string_list(
    value: Any,
    *,
    field: str,
    index: int,
    issues: list[dict[str, Any]],
    maximum: int,
    allow_local_refs: bool,
) -> Any:
    if not isinstance(value, list):
        issues.append(
            _issue(
                "operation_list_type",
                f"{field} must be a list.",
                operation_index=index,
                field=field,
            )
        )
        return value
    result: list[str] = []
    for item_index, item in enumerate(value):
        if not isinstance(item, str):
            issues.append(
                _issue(
                    "operation_list_item_type",
                    f"{field} items must be strings.",
                    operation_index=index,
                    field=field,
                    path=f"$.operations[{index}].{field}[{item_index}]",
                )
            )
            continue
        normalized = item.strip()
        if not normalized or len(normalized) > maximum:
            issues.append(
                _issue(
                    "operation_list_item_bounds",
                    f"{field} items must contain 1 to {maximum} characters.",
                    operation_index=index,
                    field=field,
                    path=f"$.operations[{index}].{field}[{item_index}]",
                )
            )
        if not allow_local_refs and normalized.startswith("new_"):
            issues.append(
                _issue(
                    "request_local_reference_not_allowed",
                    f"{field} does not accept request-local references.",
                    operation_index=index,
                    field=field,
                )
            )
        result.append(normalized)
    if len(result) != len(set(result)):
        issues.append(
            _issue(
                "operation_list_duplicate",
                f"{field} items must be unique.",
                operation_index=index,
                field=field,
            )
        )
    return result


def _normalize_id_list(
    value: Any,
    *,
    field: str,
    index: int,
    issues: list[dict[str, Any]],
    family: str | None,
) -> Any:
    result = _normalize_string_list(
        value,
        field=field,
        index=index,
        issues=issues,
        maximum=500,
        allow_local_refs=family is not None,
    )
    if not isinstance(result, list):
        return result
    for item_index, item in enumerate(result):
        if ID_PATTERN.fullmatch(item) is None:
            issues.append(
                _issue(
                    "operation_id_invalid",
                    f"{field} contains invalid identifier {item!r}.",
                    operation_index=index,
                    field=field,
                    path=f"$.operations[{index}].{field}[{item_index}]",
                )
            )
    return result


def _update_context_record(record: dict[str, Any], operation: dict[str, Any]) -> None:
    if "title" in operation:
        record["title"] = operation["title"]
    if "purpose" in operation:
        record["context"]["purpose"] = operation["purpose"]
    if "in_scope" in operation:
        record["context"]["in_scope"] = operation["in_scope"]
    if "out_of_scope" in operation:
        record["context"]["out_of_scope"] = operation["out_of_scope"]


def _context_from_operation(operation: dict[str, Any]) -> dict[str, Any]:
    return {
        "purpose": operation["purpose"],
        "in_scope": operation["in_scope"],
        "out_of_scope": operation["out_of_scope"],
    }


def _insert(
    records: list[dict[str, Any]],
    position: int,
    record: dict[str, Any],
    *,
    index: int,
    field: str,
) -> None:
    if position > len(records) + 1:
        raise CourseModelValidationError(
            [
                _issue(
                    "operation_position_out_of_range",
                    f"{field} must be between 1 and {len(records) + 1}.",
                    operation_index=index,
                    field=field,
                )
            ]
        )
    records.insert(position - 1, record)


def _move_record(
    records: list[dict[str, Any]], record_id: str, position: int, family: str, index: int
) -> None:
    record = next((item for item in records if item["id"] == record_id), None)
    if record is None:
        raise CourseModelValidationError([_unknown_record_issue(family, record_id, index)])
    records.remove(record)
    _insert(records, position, record, index=index, field="position")


def _remove_record(records: list[dict[str, Any]], record_id: str, family: str, index: int) -> None:
    record = next((item for item in records if item["id"] == record_id), None)
    if record is None:
        raise CourseModelValidationError([_unknown_record_issue(family, record_id, index)])
    records.remove(record)


def _reorder_complete(
    records: list[dict[str, Any]], ids: list[str], family: str, index: int
) -> list[dict[str, Any]]:
    current_ids = [record["id"] for record in records]
    if len(ids) != len(current_ids) or set(ids) != set(current_ids):
        raise CourseModelValidationError(
            [
                _issue(
                    "incomplete_reorder",
                    f"{family.title()} reorder must contain every current ID exactly once.",
                    operation_index=index,
                    record_type=family,
                )
            ]
        )
    by_id = {record["id"]: record for record in records}
    return [by_id[record_id] for record_id in ids]


def _require_module(body: dict[str, Any], record_id: str, index: int) -> dict[str, Any]:
    module = next((item for item in body["modules"] if item["id"] == record_id), None)
    if module is None:
        raise CourseModelValidationError([_unknown_record_issue("module", record_id, index)])
    return module


def _require_subtopic(
    body: dict[str, Any], record_id: str, index: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    for module in body["modules"]:
        for subtopic in module["subtopics"]:
            if subtopic["id"] == record_id:
                return module, subtopic
    raise CourseModelValidationError([_unknown_record_issue("subtopic", record_id, index)])


def _require_concept(
    body: dict[str, Any], record_id: str, index: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    for subtopic in _records_by_family(body)["subtopic"]:
        for concept in subtopic["concepts"]:
            if concept["id"] == record_id:
                return subtopic, concept
    raise CourseModelValidationError([_unknown_record_issue("concept", record_id, index)])


def _require_coverage(
    body: dict[str, Any], record_id: str, index: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    for subtopic in _records_by_family(body)["subtopic"]:
        for requirement in subtopic["coverage_requirements"]:
            if requirement["id"] == record_id:
                return subtopic, requirement
    raise CourseModelValidationError([_unknown_record_issue("coverage", record_id, index)])


def _derive_orders(body: dict[str, Any]) -> None:
    for module_order, module in enumerate(body["modules"], start=1):
        module["order"] = module_order
        for subtopic_order, subtopic in enumerate(module["subtopics"], start=1):
            subtopic["order"] = subtopic_order


def _records_by_family(body: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    modules = body.get("modules", []) if isinstance(body.get("modules", []), list) else []
    subtopics = [
        subtopic
        for module in modules
        if isinstance(module, dict) and isinstance(module.get("subtopics", []), list)
        for subtopic in module["subtopics"]
        if isinstance(subtopic, dict)
    ]
    return {
        "module": [item for item in modules if isinstance(item, dict)],
        "subtopic": subtopics,
        "concept": [
            concept
            for subtopic in subtopics
            if isinstance(subtopic.get("concepts", []), list)
            for concept in subtopic["concepts"]
            if isinstance(concept, dict)
        ],
        "coverage": [
            requirement
            for subtopic in subtopics
            if isinstance(subtopic.get("coverage_requirements", []), list)
            for requirement in subtopic["coverage_requirements"]
            if isinstance(requirement, dict)
        ],
    }


def _affected_records(
    original: dict[str, Any], candidate: dict[str, Any], course_id: str
) -> dict[str, dict[str, list[str]]]:
    before = _record_snapshots(original, course_id)
    after = _record_snapshots(candidate, course_id)
    result: dict[str, dict[str, list[str]]] = {}
    for family in ("course", "module", "subtopic", "concept", "coverage", "rationale", "source"):
        old = before.get(family, {})
        new = after.get(family, {})
        candidate_order = list(new)
        original_order = list(old)
        result[family] = {
            "changed_ids": [
                record_id for record_id in candidate_order if old.get(record_id) != new[record_id]
            ],
            "removed_ids": [record_id for record_id in original_order if record_id not in new],
            "preserved_ids": [
                record_id
                for record_id in candidate_order
                if record_id in old and old[record_id] == new[record_id]
            ],
        }
    return result


def _record_snapshots(body: dict[str, Any], course_id: str) -> dict[str, dict[str, Any]]:
    snapshots: dict[str, dict[str, Any]] = {
        "course": {course_id: deepcopy(body.get("course_metadata"))},
        "module": {},
        "subtopic": {},
        "concept": {},
        "coverage": {},
        "rationale": {item["id"]: deepcopy(item) for item in body.get("structural_rationale", [])},
        "source": {item["id"]: deepcopy(item) for item in body.get("source_registry", [])},
    }
    for module in body.get("modules", []):
        module_value = {key: deepcopy(value) for key, value in module.items() if key != "subtopics"}
        snapshots["module"][module["id"]] = module_value
        for subtopic in module.get("subtopics", []):
            subtopic_value = {
                key: deepcopy(value)
                for key, value in subtopic.items()
                if key not in {"concepts", "coverage_requirements"}
            }
            subtopic_value["parent_id"] = module["id"]
            snapshots["subtopic"][subtopic["id"]] = subtopic_value
            for concept in subtopic.get("concepts", []):
                snapshots["concept"][concept["id"]] = {
                    **deepcopy(concept),
                    "parent_id": subtopic["id"],
                }
            for requirement in subtopic.get("coverage_requirements", []):
                snapshots["coverage"][requirement["id"]] = {
                    **deepcopy(requirement),
                    "parent_id": subtopic["id"],
                }
    return snapshots


def _reference_issues(
    values: list[str],
    valid: set[str],
    *,
    owner_type: str,
    owner_id: str,
    field: str,
    self_id: str | None = None,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for value in values:
        if value not in valid:
            issues.append(
                _issue(
                    "unknown_reference",
                    f"{owner_type.title()} {owner_id} references unknown ID {value!r}.",
                    record_type=owner_type,
                    record_id=owner_id,
                    field=field,
                )
            )
        if self_id is not None and value == self_id:
            issues.append(
                _issue(
                    "self_reference",
                    f"{owner_type.title()} {owner_id} cannot reference itself.",
                    record_type=owner_type,
                    record_id=owner_id,
                    field=field,
                )
            )
    return issues


def _find_cycle(dependencies: dict[str, list[str]]) -> list[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str, path: list[str]) -> list[str] | None:
        if node in visiting:
            return path[path.index(node) :] + [node]
        if node in visited:
            return None
        visiting.add(node)
        for dependency in dependencies.get(node, []):
            if dependency in dependencies:
                cycle = visit(dependency, [*path, dependency])
                if cycle:
                    return cycle
        visiting.remove(node)
        visited.add(node)
        return None

    for node in dependencies:
        cycle = visit(node, [node])
        if cycle:
            return cycle
    return None


def _substantive_body(body: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(body)
    value.pop("id_allocation", None)
    return value


def _artifact_body(value: dict[str, Any]) -> dict[str, Any]:
    body = value.get("body") if isinstance(value, dict) else None
    return body if isinstance(body, dict) else value


@lru_cache(maxsize=1)
def _course_model_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _request_local_reference_values(body: dict[str, Any]) -> list[tuple[str, str]]:
    """Return only ID/reference fields that could accidentally persist local refs."""
    found: list[tuple[str, str]] = []

    def add(path: str, value: Any) -> None:
        if isinstance(value, str):
            found.append((path, value))

    def add_list(path: str, values: Any) -> None:
        if isinstance(values, list):
            for index, value in enumerate(values):
                add(f"{path}[{index}]", value)

    add_list(
        "$.body.course_metadata.course_outcome_ids",
        body.get("course_metadata", {}).get("course_outcome_ids", []),
    )
    for rationale_index, rationale in enumerate(body.get("structural_rationale", [])):
        base = f"$.body.structural_rationale[{rationale_index}]"
        add(f"{base}.id", rationale.get("id"))
        for field in (
            "evidence_artifact_refs",
            "related_outcome_ids",
            "related_topic_ids",
        ):
            add_list(f"{base}.{field}", rationale.get(field, []))
    for module_index, module in enumerate(body.get("modules", [])):
        module_path = f"$.body.modules[{module_index}]"
        add(f"{module_path}.id", module.get("id"))
        add_list(
            f"{module_path}.prerequisite_module_ids",
            module.get("prerequisite_module_ids", []),
        )
        for subtopic_index, subtopic in enumerate(module.get("subtopics", [])):
            subtopic_path = f"{module_path}.subtopics[{subtopic_index}]"
            add(f"{subtopic_path}.id", subtopic.get("id"))
            add_list(
                f"{subtopic_path}.prerequisite_subtopic_ids",
                subtopic.get("prerequisite_subtopic_ids", []),
            )
            add_list(
                f"{subtopic_path}.approved_source_ids",
                subtopic.get("approved_source_ids", []),
            )
            for concept_index, concept in enumerate(subtopic.get("concepts", [])):
                concept_path = f"{subtopic_path}.concepts[{concept_index}]"
                add(f"{concept_path}.id", concept.get("id"))
                add_list(f"{concept_path}.depends_on", concept.get("depends_on", []))
                add_list(f"{concept_path}.source_ids", concept.get("source_ids", []))
            for coverage_index, coverage in enumerate(subtopic.get("coverage_requirements", [])):
                coverage_path = f"{subtopic_path}.coverage_requirements[{coverage_index}]"
                add(f"{coverage_path}.id", coverage.get("id"))
                add_list(f"{coverage_path}.concept_ids", coverage.get("concept_ids", []))
                add_list(f"{coverage_path}.source_ids", coverage.get("source_ids", []))
    for source_index, source in enumerate(body.get("source_registry", [])):
        add(f"$.body.source_registry[{source_index}].id", source.get("id"))
    return found


def _banned_source_text_paths(value: Any, path: str = "$.body") -> list[str]:
    banned = {"content", "excerpt", "full_text", "raw_text", "source_text"}
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in banned:
                found.append(child_path)
            found.extend(_banned_source_text_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_banned_source_text_paths(child, f"{path}[{index}]"))
    return found


def _change(
    index: int,
    operation: str,
    record_type: str,
    record_id: str | None,
    action: str,
    **details: Any,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "operation_index": index,
        "op": operation,
        "action": action,
        "record_type": record_type,
    }
    if record_id is not None:
        value["record_id"] = record_id
    value.update(details)
    return value


def _unknown_record_issue(family: str, record_id: str, index: int) -> dict[str, Any]:
    return _issue(
        "course_model_record_not_found",
        f"Unknown {family} ID {record_id!r}.",
        operation_index=index,
        record_type=family,
        record_id=record_id,
        field="target_id",
    )


def _issue(
    code: str,
    message: str,
    *,
    operation_index: int | None = None,
    record_type: str | None = None,
    record_id: str | None = None,
    field: str | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    issue: dict[str, Any] = {"code": code, "message": message}
    if operation_index is not None:
        issue["operation_index"] = operation_index
    if record_type is not None:
        issue["record_type"] = record_type
    if record_id is not None:
        issue["record_id"] = record_id
    if field is not None:
        issue["field"] = field
    if path is not None:
        issue["path"] = path
    return issue
