"""Course-level outcome drafting and structured human selection."""

from __future__ import annotations

import re
from copy import deepcopy
from difflib import SequenceMatcher
from typing import Any

from interaction import ChoiceOption, ChoicePrompt, ScriptedResponder
from orchestrator import make_artifact

DESIGN_SCHEMA_VERSION = "0.2"
OUTCOME_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
CLIENT_KEY_PATTERN = re.compile(r"^new_[a-z0-9_-]+$")
CANONICAL_OUTCOME_ID_PATTERN = re.compile(r"^co([1-9][0-9]*)$")
OUTCOME_TEXT_MAX_LENGTH = 300
COGNITIVE_LEVELS = frozenset(
    {"remember", "understand", "apply", "analyze", "evaluate", "create"}
)
OUTCOME_PRIORITIES = frozenset({"core", "supporting", "optional"})
OUTCOME_FIELDS = frozenset(
    {"id", "statement", "cognitive_level", "evidence", "priority"}
)
EDITABLE_OUTCOME_FIELDS = frozenset(
    {"statement", "cognitive_level", "evidence", "priority"}
)
ADDITION_FIELDS = EDITABLE_OUTCOME_FIELDS | {"client_key"}


class OutcomeDecisionValidationError(ValueError):
    """A deterministic Outcomes decision failed one or more domain checks."""

    def __init__(self, issues: list[dict[str, Any]]) -> None:
        if not issues:
            raise ValueError("Outcome decision validation requires at least one issue")
        self.issues = issues
        super().__init__(str(issues[0]["message"]))


def draft_outcomes_from_brief(brief: dict) -> list[dict]:
    """Draft domain-neutral measurable outcomes from an approved brief."""
    body = brief["body"]
    subject = body["subject"]
    purpose = body.get("purpose") or body.get("goals") or f"Build working knowledge of {subject}."
    in_scope = body.get("in_scope", [])
    practical_focus = in_scope[0] if in_scope else subject
    return [
        {
            "id": "co1",
            "statement": f"Explain the core concepts and vocabulary needed to work with {subject}.",
            "cognitive_level": "understand",
            "evidence": "Learner accurately explains key terms in their own words.",
            "priority": "core",
        },
        {
            "id": "co2",
            "statement": f"Apply a repeatable process for {practical_focus}.",
            "cognitive_level": "apply",
            "evidence": "Learner completes a realistic task using the process.",
            "priority": "core",
        },
        {
            "id": "co3",
            "statement": (
                f"Analyze common problems or tradeoffs encountered while pursuing: {purpose}"
            ),
            "cognitive_level": "analyze",
            "evidence": "Learner diagnoses a scenario and justifies a next step.",
            "priority": "core",
        },
        {
            "id": "co4",
            "statement": (
                f"Evaluate whether a chosen approach fits the learner's constraints for {subject}."
            ),
            "cognitive_level": "evaluate",
            "evidence": "Learner compares options against explicit criteria.",
            "priority": "supporting",
        },
    ]


def build_outcome_choice_prompt(outcomes: list[dict]) -> ChoicePrompt:
    return ChoicePrompt(
        id="outcomes_select",
        stage="course_outcomes",
        target_artifact="course_outcomes",
        question="Select the course-level outcomes to approve for research and structure.",
        mode="multi",
        min_selections=1,
        allow_custom=True,
        options=tuple(
            ChoiceOption(
                id=outcome["id"],
                label=outcome["statement"],
                description=(
                    f"{outcome['cognitive_level']} outcome; evidence: {outcome['evidence']}"
                ),
                recommendation_rationale=(
                    "Recommended because it follows directly from the approved brief."
                ),
                selected_by_default=outcome["priority"] in {"core", "supporting"},
            )
            for outcome in outcomes
        ),
    )


def apply_outcome_decision(
    outcomes: list[dict],
    selected_ids: list[str] | tuple[str, ...],
    *,
    edits: dict[str, dict[str, Any]] | None = None,
    additions: list[dict[str, Any]] | None = None,
    priority_order: list[str] | None = None,
    allocation_start: int | None = None,
    reject_noop: bool = False,
) -> list[dict]:
    """Apply one complete, deterministic select/edit/add/order decision.

    An omitted or empty ``priority_order`` retains the historical fallback: selected
    outcomes remain in ``selected_ids`` order and additions follow in request order. A
    non-empty order is complete. ID-less additions use their temporary ``client_key``
    in that order and receive canonical IDs only inside this reducer.
    """
    candidates = _normalize_outcome_collection(
        outcomes,
        allow_empty=True,
        require_meaningful=False,
    )
    by_id = {outcome["id"]: outcome for outcome in candidates}
    issues: list[dict[str, Any]] = []

    selected = _validate_selected_ids(selected_ids, by_id, issues)
    normalized_edits = _validate_edits(edits, by_id, set(selected), issues)
    normalized_additions = _validate_additions(additions, set(by_id), issues)
    order = _validate_priority_order(
        priority_order,
        selected,
        normalized_additions,
        set(by_id),
        issues,
    )
    if issues:
        raise OutcomeDecisionValidationError(issues)

    resolved_allocation_start = (
        next_outcome_id(candidates) if allocation_start is None else allocation_start
    )
    if type(resolved_allocation_start) is not int or resolved_allocation_start < 1:
        raise ValueError("allocation_start must be a positive integer")
    allocated_ids = iter(
        _allocate_outcome_ids(
            set(by_id),
            len(normalized_additions),
            start_at=resolved_allocation_start,
        )
    )
    for record in normalized_additions:
        record["outcome"]["id"] = next(allocated_ids)

    retained: list[dict[str, Any]] = []
    for outcome_id in selected:
        outcome = deepcopy(by_id[outcome_id])
        outcome.update(normalized_edits.get(outcome_id, {}))
        retained.append(outcome)
    added = [deepcopy(record["outcome"]) for record in normalized_additions]

    if order:
        by_reference = {outcome["id"]: outcome for outcome in retained}
        for record, outcome in zip(normalized_additions, added, strict=True):
            by_reference[str(record["client_key"])] = outcome
        decided = [by_reference[reference] for reference in order]
    else:
        decided = [*retained, *added]

    decided = validate_outcome_collection(decided)
    if reject_noop and decided == outcomes:
        raise OutcomeDecisionValidationError(
            [
                _issue(
                    "outcome_decision_noop",
                    "Outcome decision does not change the current Outcomes collection.",
                )
            ]
        )
    return decided


def run_scripted_outcomes(
    brief: dict,
    responder: ScriptedResponder,
    *,
    edits: dict[str, dict[str, Any]] | None = None,
    additions: list[dict[str, Any]] | None = None,
    priority_order: list[str] | None = None,
) -> dict:
    candidates = draft_outcomes_from_brief(brief)
    prompt = build_outcome_choice_prompt(candidates)
    decision = responder.choose(prompt)
    approved = apply_outcome_decision(
        candidates,
        decision.selected_ids,
        edits=edits,
        additions=[*decision.custom_items, *(additions or [])],
        priority_order=priority_order,
    )
    return build_course_outcomes_artifact(brief, approved)


def build_course_outcomes_artifact(
    brief: dict,
    outcomes: list[dict],
    *,
    next_canonical_id: int | None = None,
) -> dict:
    body = brief["body"]
    validated = validate_outcome_collection(outcomes)
    artifact_body = {
        "course_title": body.get("course_title") or body["subject"],
        "audience_summary": body.get("audience", "Learners"),
        "outcomes": validated,
    }
    if next_canonical_id is not None:
        if type(next_canonical_id) is not int or next_canonical_id < 1:
            raise ValueError("next_canonical_id must be a positive integer")
        artifact_body["next_outcome_id"] = next_canonical_id
    return make_artifact(
        brief["course_id"],
        "course_outcomes",
        "outcomes",
        body=artifact_body,
        inputs=["brief"],
        schema_version=DESIGN_SCHEMA_VERSION,
    )


def validate_outcome_collection(outcomes: Any) -> list[dict[str, Any]]:
    """Return a normalized schema-compatible collection or structured hard errors."""
    return _normalize_outcome_collection(
        outcomes,
        allow_empty=False,
        require_meaningful=True,
    )


def outcome_advisories(outcomes: Any) -> list[dict[str, Any]]:
    """Return deterministic, non-blocking quality hints for operator attention."""
    if not isinstance(outcomes, list):
        return []
    records = [item for item in outcomes if isinstance(item, dict)]
    advisories: list[dict[str, Any]] = []
    vague_starts = (
        "know ",
        "learn ",
        "understand ",
        "appreciate ",
        "be aware ",
        "be familiar ",
        "gain knowledge ",
        "develop awareness ",
        "explore ",
    )
    weak_evidence_phrases = {
        "learner demonstrates the outcome in a task",
        "learner demonstrates understanding",
        "learner shows understanding",
        "learner understands the outcome",
        "learner knows the material",
    }
    for item in records:
        outcome_id = item.get("id")
        statement = item.get("statement")
        evidence = item.get("evidence")
        if isinstance(outcome_id, str) and isinstance(statement, str):
            normalized_statement = " ".join(statement.strip().casefold().split())
            if any(f"{normalized_statement} ".startswith(prefix) for prefix in vague_starts):
                advisories.append(
                    _advisory(
                        "vague_or_non_observable_verb",
                        outcome_id,
                        "statement",
                        (
                            "The opening verb may be difficult to observe directly; "
                            "consider a measurable action."
                        ),
                    )
                )
        if isinstance(outcome_id, str) and isinstance(evidence, str):
            normalized_evidence = " ".join(evidence.strip().casefold().split()).rstrip(".")
            if (
                len(_words(normalized_evidence)) < 5
                or normalized_evidence in weak_evidence_phrases
                or normalized_evidence.startswith(("learner understands ", "learner knows "))
            ):
                advisories.append(
                    _advisory(
                        "mechanically_weak_evidence",
                        outcome_id,
                        "evidence",
                        (
                            "The evidence description may not name a concrete observable "
                            "performance or product."
                        ),
                    )
                )

    for index, left in enumerate(records):
        left_id = left.get("id")
        left_statement = left.get("statement")
        if not isinstance(left_id, str) or not isinstance(left_statement, str):
            continue
        left_normalized = " ".join(_words(left_statement))
        if not left_normalized:
            continue
        for right in records[index + 1 :]:
            right_id = right.get("id")
            right_statement = right.get("statement")
            if not isinstance(right_id, str) or not isinstance(right_statement, str):
                continue
            right_normalized = " ".join(_words(right_statement))
            if not right_normalized:
                continue
            if left_normalized == right_normalized:
                advisories.append(
                    _advisory(
                        "duplicate_outcome_statement",
                        right_id,
                        "statement",
                        f"This statement duplicates Outcome {left_id}.",
                        related_outcome_id=left_id,
                    )
                )
            elif (
                min(len(left_normalized.split()), len(right_normalized.split())) >= 4
                and SequenceMatcher(None, left_normalized, right_normalized).ratio() >= 0.86
            ):
                advisories.append(
                    _advisory(
                        "near_duplicate_outcome_statement",
                        right_id,
                        "statement",
                        (
                            f"This statement is very similar to Outcome {left_id}; "
                            "confirm both are distinct."
                        ),
                        related_outcome_id=left_id,
                    )
                )
    return advisories


def _normalize_outcome_collection(
    outcomes: Any,
    *,
    allow_empty: bool,
    require_meaningful: bool,
) -> list[dict[str, Any]]:
    if not isinstance(outcomes, list):
        raise OutcomeDecisionValidationError(
            [_issue("outcomes_type", "Outcomes collection must be a list.", field="outcomes")]
        )
    issues: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []
    ids: list[str] = []
    for index, item in enumerate(outcomes):
        if not isinstance(item, dict):
            issues.append(
                _issue(
                    "outcome_type",
                    "Each Outcome must be an object.",
                    field="outcomes",
                    index=index,
                )
            )
            continue
        outcome_id = item.get("id") if isinstance(item.get("id"), str) else None
        missing = sorted(OUTCOME_FIELDS - set(item))
        unsupported = sorted(set(item) - OUTCOME_FIELDS)
        for field in missing:
            issues.append(
                _issue(
                    "outcome_field_missing",
                    f"Outcome is missing required field {field!r}.",
                    outcome_id=outcome_id,
                    field=field,
                    index=index,
                )
            )
        for field in unsupported:
            issues.append(
                _issue(
                    "unsupported_outcome_field",
                    f"Outcome field {field!r} is not supported.",
                    outcome_id=outcome_id,
                    field=field,
                    index=index,
                )
            )
        normalized_id = _normalize_outcome_id(item.get("id"), issues, index=index)
        statement = _normalize_outcome_field(
            "statement", item.get("statement"), issues, outcome_id=normalized_id, index=index
        )
        cognitive_level = _normalize_outcome_field(
            "cognitive_level",
            item.get("cognitive_level"),
            issues,
            outcome_id=normalized_id,
            index=index,
        )
        evidence = _normalize_outcome_field(
            "evidence", item.get("evidence"), issues, outcome_id=normalized_id, index=index
        )
        priority = _normalize_outcome_field(
            "priority", item.get("priority"), issues, outcome_id=normalized_id, index=index
        )
        if normalized_id is not None:
            ids.append(normalized_id)
        if all(
            value is not None
            for value in (normalized_id, statement, cognitive_level, evidence, priority)
        ):
            normalized.append(
                {
                    "id": normalized_id,
                    "statement": statement,
                    "cognitive_level": cognitive_level,
                    "evidence": evidence,
                    "priority": priority,
                }
            )
    duplicate_ids = sorted({outcome_id for outcome_id in ids if ids.count(outcome_id) > 1})
    for outcome_id in duplicate_ids:
        issues.append(
            _issue(
                "duplicate_outcome_id",
                f"Outcome ID {outcome_id!r} appears more than once.",
                outcome_id=outcome_id,
                field="id",
            )
        )
    if not outcomes and not allow_empty:
        issues.append(
            _issue(
                "outcomes_empty",
                "research cannot start until at least one meaningful outcome is approved",
                field="outcomes",
            )
        )
    if require_meaningful and outcomes and not _has_meaningful_outcome(normalized):
        issues.append(
            _issue(
                "outcomes_not_meaningful",
                "At least one retained or added Outcome must contain a meaningful statement.",
                field="statement",
            )
        )
    if issues:
        raise OutcomeDecisionValidationError(issues)
    return normalized


def _validate_selected_ids(
    selected_ids: Any,
    by_id: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> list[str]:
    if not isinstance(selected_ids, (list, tuple)):
        issues.append(
            _issue("selected_ids_type", "selected_ids must be a list.", field="selected_ids")
        )
        return []
    selected: list[str] = []
    for index, outcome_id in enumerate(selected_ids):
        if not isinstance(outcome_id, str):
            issues.append(
                _issue(
                    "selected_id_type",
                    "Selected Outcome IDs must be strings.",
                    field="selected_ids",
                    index=index,
                )
            )
            continue
        if not OUTCOME_ID_PATTERN.fullmatch(outcome_id):
            issues.append(
                _issue(
                    "invalid_selected_id",
                    f"Selected Outcome ID {outcome_id!r} has invalid syntax.",
                    outcome_id=outcome_id,
                    field="selected_ids",
                    index=index,
                )
            )
            continue
        selected.append(outcome_id)
    duplicate_ids = sorted(
        {outcome_id for outcome_id in selected if selected.count(outcome_id) > 1}
    )
    for outcome_id in duplicate_ids:
        issues.append(
            _issue(
                "duplicate_selected_id",
                f"Outcome ID {outcome_id!r} is selected more than once.",
                outcome_id=outcome_id,
                field="selected_ids",
            )
        )
    for outcome_id in sorted(set(selected) - set(by_id)):
        issues.append(
            _issue(
                "unknown_selected_id",
                f"Cannot select unknown Outcome {outcome_id!r}.",
                outcome_id=outcome_id,
                field="selected_ids",
            )
        )
    return selected


def _validate_edits(
    edits: Any,
    by_id: dict[str, dict[str, Any]],
    selected_ids: set[str],
    issues: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if edits is None:
        return {}
    if not isinstance(edits, dict):
        issues.append(_issue("edits_type", "edits must be an object.", field="edits"))
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for outcome_id, patch in edits.items():
        if not isinstance(outcome_id, str) or not OUTCOME_ID_PATTERN.fullmatch(outcome_id):
            issues.append(
                _issue(
                    "invalid_edit_target",
                    f"Edit target {outcome_id!r} is not a valid Outcome ID.",
                    field="edits",
                )
            )
            continue
        if outcome_id not in by_id:
            issues.append(
                _issue(
                    "unknown_edit_target",
                    f"Cannot edit unknown Outcome {outcome_id!r}.",
                    outcome_id=outcome_id,
                    field="edits",
                )
            )
            continue
        if outcome_id not in selected_ids:
            issues.append(
                _issue(
                    "edit_target_not_retained",
                    f"Outcome {outcome_id!r} is edited but not retained.",
                    outcome_id=outcome_id,
                    field="edits",
                )
            )
        if not isinstance(patch, dict):
            issues.append(
                _issue(
                    "outcome_edit_type",
                    f"Edit for Outcome {outcome_id!r} must be an object.",
                    outcome_id=outcome_id,
                    field="edits",
                )
            )
            continue
        if "id" in patch:
            issues.append(
                _issue(
                    "outcome_id_mutation",
                    "Outcome IDs cannot be changed through an edit patch.",
                    outcome_id=outcome_id,
                    field="id",
                )
            )
        unsupported = sorted(set(patch) - EDITABLE_OUTCOME_FIELDS - {"id"})
        for field in unsupported:
            issues.append(
                _issue(
                    "unsupported_outcome_edit_field",
                    f"Outcome field {field!r} cannot be edited.",
                    outcome_id=outcome_id,
                    field=field,
                )
            )
        present = [field for field in EDITABLE_OUTCOME_FIELDS if field in patch]
        if not present:
            issues.append(
                _issue(
                    "outcome_edit_empty",
                    f"Edit for Outcome {outcome_id!r} must change at least one supported field.",
                    outcome_id=outcome_id,
                    field="edits",
                )
            )
            continue
        normalized_patch: dict[str, Any] = {}
        for field in present:
            value = _normalize_outcome_field(
                field,
                patch[field],
                issues,
                outcome_id=outcome_id,
            )
            if value is not None:
                normalized_patch[field] = value
        normalized[outcome_id] = normalized_patch
    return normalized


def _validate_additions(
    additions: Any,
    existing_ids: set[str],
    issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if additions is None:
        return []
    if not isinstance(additions, (list, tuple)):
        issues.append(
            _issue("additions_type", "additions must be a list.", field="additions")
        )
        return []
    normalized: list[dict[str, Any]] = []
    for index, addition in enumerate(additions):
        start = len(issues)
        if not isinstance(addition, dict):
            issues.append(
                _issue(
                    "outcome_addition_type",
                    "Each added Outcome must be an object.",
                    field="additions",
                    index=index,
                )
            )
            continue
        if "id" in addition:
            issues.append(
                _issue(
                    "addition_id_not_allowed",
                    "Added Outcome IDs are allocated only by the backend.",
                    field="id",
                    index=index,
                )
            )
        unsupported = sorted(set(addition) - ADDITION_FIELDS)
        for field in unsupported:
            issues.append(
                _issue(
                    "unsupported_outcome_addition_field",
                    f"Added Outcome field {field!r} is not supported.",
                    field=field,
                    index=index,
                )
            )
        required = EDITABLE_OUTCOME_FIELDS
        for field in sorted(required - set(addition)):
            issues.append(
                _issue(
                    "outcome_addition_field_missing",
                    f"Added Outcome is missing required field {field!r}.",
                    field=field,
                    index=index,
                )
            )
        outcome_id = None
        client_key = addition.get("client_key")
        if client_key is not None:
            if not isinstance(client_key, str):
                issues.append(
                    _issue(
                        "client_key_type",
                        "Addition client_key must be a string.",
                        field="client_key",
                        index=index,
                    )
                )
            elif not CLIENT_KEY_PATTERN.fullmatch(client_key):
                issues.append(
                    _issue(
                        "invalid_client_key",
                        "Addition client_key must match new_[a-z0-9_-]+.",
                        field="client_key",
                        index=index,
                    )
                )
        values = {
            field: _normalize_outcome_field(
                field,
                addition.get(field),
                issues,
                outcome_id=outcome_id,
                index=index,
            )
            for field in EDITABLE_OUTCOME_FIELDS
        }
        if len(issues) == start:
            normalized.append(
                {
                    "outcome": {"id": outcome_id, **values},
                    "client_key": client_key,
                    "index": index,
                }
            )

    client_keys: set[str] = set()
    for record in normalized:
        client_key = record.get("client_key")
        if client_key:
            if client_key in client_keys:
                issues.append(
                    _issue(
                        "duplicate_client_key",
                        f"Addition client_key {client_key!r} appears more than once.",
                        field="client_key",
                        index=record["index"],
                    )
                )
            client_keys.add(client_key)
    for record in normalized:
        client_key = record.get("client_key")
        if client_key and client_key in existing_ids:
            issues.append(
                _issue(
                    "client_key_collision",
                    f"Addition client_key {client_key!r} is ambiguous with a canonical Outcome ID.",
                    field="client_key",
                    index=record["index"],
                )
            )
    return normalized


def _validate_priority_order(
    priority_order: Any,
    selected_ids: list[str],
    additions: list[dict[str, Any]],
    existing_ids: set[str],
    issues: list[dict[str, Any]],
) -> list[str]:
    if priority_order is None or priority_order == []:
        return []
    if not isinstance(priority_order, (list, tuple)):
        issues.append(
            _issue(
                "priority_order_type",
                "priority_order must be a list.",
                field="priority_order",
            )
        )
        return []
    expected = list(selected_ids)
    for record in additions:
        if record.get("client_key"):
            expected.append(str(record["client_key"]))
        else:
            issues.append(
                _issue(
                    "addition_client_key_required",
                    (
                        "An ID-less addition needs a unique client_key when "
                        "priority_order is explicit."
                    ),
                    field="client_key",
                    index=record["index"],
                )
            )
    order: list[str] = []
    for index, reference in enumerate(priority_order):
        if not isinstance(reference, str):
            issues.append(
                _issue(
                    "priority_order_id_type",
                    "priority_order entries must be strings.",
                    field="priority_order",
                    index=index,
                )
            )
            continue
        if not OUTCOME_ID_PATTERN.fullmatch(reference):
            issues.append(
                _issue(
                    "invalid_priority_order_id",
                    f"Priority-order reference {reference!r} has invalid syntax.",
                    field="priority_order",
                    index=index,
                )
            )
            continue
        order.append(reference)
    duplicates = sorted({reference for reference in order if order.count(reference) > 1})
    for reference in duplicates:
        issues.append(
            _issue(
                "duplicate_priority_order_id",
                f"Priority-order reference {reference!r} appears more than once.",
                outcome_id=reference,
                field="priority_order",
            )
        )
    expected_set = set(expected)
    for reference in sorted(set(order) - expected_set):
        if reference in existing_ids and reference not in selected_ids:
            code = "removed_outcome_in_priority_order"
            message = f"Removed Outcome {reference!r} cannot appear in priority_order."
        else:
            code = "unknown_priority_order_id"
            message = f"Priority-order reference {reference!r} is not in the final collection."
        issues.append(
            _issue(code, message, outcome_id=reference, field="priority_order")
        )
    for reference in sorted(expected_set - set(order)):
        issues.append(
            _issue(
                "missing_priority_order_id",
                f"Final Outcome reference {reference!r} is missing from priority_order.",
                outcome_id=reference,
                field="priority_order",
            )
        )
    return order


def _normalize_outcome_id(
    value: Any,
    issues: list[dict[str, Any]],
    *,
    index: int | None = None,
) -> str | None:
    if not isinstance(value, str):
        issues.append(
            _issue(
                "outcome_id_type",
                "Outcome ID must be a string.",
                field="id",
                index=index,
            )
        )
        return None
    if not OUTCOME_ID_PATTERN.fullmatch(value):
        issues.append(
            _issue(
                "invalid_outcome_id",
                f"Outcome ID {value!r} has invalid syntax.",
                outcome_id=value,
                field="id",
                index=index,
            )
        )
        return None
    return value


def _normalize_outcome_field(
    field: str,
    value: Any,
    issues: list[dict[str, Any]],
    *,
    outcome_id: str | None,
    index: int | None = None,
) -> str | None:
    if not isinstance(value, str):
        issues.append(
            _issue(
                "outcome_field_type",
                f"Outcome {field} must be a string.",
                outcome_id=outcome_id,
                field=field,
                index=index,
            )
        )
        return None
    normalized = value.strip() if field in {"statement", "evidence"} else value
    if field in {"statement", "evidence"}:
        if not normalized:
            issues.append(
                _issue(
                    f"outcome_{field}_empty",
                    f"Outcome {field} cannot be empty or whitespace-only.",
                    outcome_id=outcome_id,
                    field=field,
                    index=index,
                )
            )
            return None
        if len(normalized) > OUTCOME_TEXT_MAX_LENGTH:
            issues.append(
                _issue(
                    f"outcome_{field}_too_long",
                    f"Outcome {field} cannot exceed {OUTCOME_TEXT_MAX_LENGTH} characters.",
                    outcome_id=outcome_id,
                    field=field,
                    index=index,
                )
            )
            return None
    elif field == "cognitive_level" and normalized not in COGNITIVE_LEVELS:
        issues.append(
            _issue(
                "invalid_cognitive_level",
                f"Cognitive level {normalized!r} is not supported.",
                outcome_id=outcome_id,
                field=field,
                index=index,
            )
        )
        return None
    elif field == "priority" and normalized not in OUTCOME_PRIORITIES:
        issues.append(
            _issue(
                "invalid_outcome_priority",
                f"Outcome priority {normalized!r} is not supported.",
                outcome_id=outcome_id,
                field=field,
                index=index,
            )
        )
        return None
    return normalized


def next_outcome_id(outcomes: list[dict[str, Any]], *, minimum: int = 1) -> int:
    """Return the next numeric canonical ID without consulting client references."""
    numeric_ids = [
        int(match.group(1))
        for outcome in outcomes
        if isinstance(outcome, dict)
        and isinstance(outcome.get("id"), str)
        and (match := CANONICAL_OUTCOME_ID_PATTERN.fullmatch(outcome["id"])) is not None
    ]
    return max([minimum - 1, *numeric_ids], default=minimum - 1) + 1


def _allocate_outcome_ids(
    existing_ids: set[str],
    count: int,
    *,
    start_at: int,
) -> list[str]:
    used = set(existing_ids)
    index = start_at
    allocated: list[str] = []
    while len(allocated) < count:
        candidate = f"co{index}"
        index += 1
        if candidate in used:
            continue
        used.add(candidate)
        allocated.append(candidate)
    return allocated


def _has_meaningful_outcome(outcomes: list[dict[str, Any]]) -> bool:
    return any(len(str(outcome.get("statement", "")).split()) >= 4 for outcome in outcomes)


def _words(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.casefold())


def _advisory(
    code: str,
    outcome_id: str,
    field: str,
    message: str,
    *,
    related_outcome_id: str | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "severity": "advisory",
        "code": code,
        "outcome_id": outcome_id,
        "field": field,
        "message": message,
    }
    if related_outcome_id is not None:
        value["related_outcome_id"] = related_outcome_id
    return value


def _issue(
    code: str,
    message: str,
    *,
    outcome_id: str | None = None,
    field: str | None = None,
    index: int | None = None,
) -> dict[str, Any]:
    issue: dict[str, Any] = {"code": code, "message": message}
    if outcome_id is not None:
        issue["outcome_id"] = outcome_id
    if field is not None:
        issue["field"] = field
    if index is not None:
        issue["index"] = index
    return issue
