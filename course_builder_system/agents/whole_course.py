"""Whole-course Student Content coordination for Sprint 3.

The coordinator is deliberately thin: it derives work units from the approved
Course Model and Blueprint, then calls the existing Student Content agent for
each selected asset. It does not embed domain logic.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import llm
from agents import student_content

ASSET_VOCABULARY = [
    "learning_objectives",
    "course_content",
    "summary",
    "case_study",
    "important_person",
    "did_you_know",
    "assessment",
    "activities",
    "resources",
]


@dataclass(frozen=True)
class WorkUnit:
    """One selected asset generation target."""

    subtopic_id: str
    asset_type: str
    asset_id: str
    title: str
    format: str


ProgressCallback = Callable[[dict[str, Any]], None]


def build_work_units(
    inputs: dict[str, Any],
    *,
    target_subtopic_ids: list[str] | tuple[str, ...] | None = None,
) -> list[WorkUnit]:
    """Return selected Blueprint assets in Course Model order."""
    target_set = set(target_subtopic_ids or [])
    units: list[WorkUnit] = []
    for subtopic_id in planned_subtopic_ids(inputs):
        if target_set and subtopic_id not in target_set:
            continue
        scoped = {**inputs, "subtopic_id": subtopic_id}
        selected_specs = sorted(
            student_content.selected_asset_specs(scoped),
            key=lambda spec: spec.asset_type != "course_content",
        )
        for spec in selected_specs:
            resolved = student_content.resolve_asset_spec(spec, scoped)
            units.append(
                WorkUnit(
                    subtopic_id=subtopic_id,
                    asset_type=resolved.asset_type,
                    asset_id=resolved.asset_id,
                    title=resolved.title,
                    format=resolved.format,
                )
            )
    return units


def planned_subtopic_ids(inputs: dict[str, Any]) -> list[str]:
    """Return Blueprint-planned subtopics in Course Model order."""
    course_body = _body(inputs["course_model"])
    blueprint_body = _body(inputs["blueprint"])
    planned = {
        plan.get("subtopic_id")
        for plan in blueprint_body.get("subtopic_plans", [])
        if isinstance(plan, dict)
    }
    ordered = [
        subtopic["id"]
        for module in course_body.get("modules", [])
        for subtopic in module.get("subtopics", [])
        if subtopic.get("id") in planned
    ]
    unknown = sorted(subtopic_id for subtopic_id in planned if subtopic_id not in ordered)
    if unknown:
        raise ValueError("Blueprint plans unknown Course Model subtopics: " + ", ".join(unknown))
    return ordered


def generate_content_package_body(
    inputs: dict[str, Any],
    *,
    existing_body: dict[str, Any] | None = None,
    target_subtopic_ids: list[str] | tuple[str, ...] | None = None,
    max_retries: int = 1,
    model: str = llm.DEFAULT_MODEL,
    use_cache: bool = True,
    continue_on_error: bool = True,
    progress_callback: ProgressCallback | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generate selected assets and return ``(content_package_body, progress)``.

    Existing completed assets are reused by asset id. Failed assets are omitted
    from the package and reported in progress, allowing a later run to retry
    without deleting unrelated artifacts.
    """
    if type(max_retries) is not int or max_retries < 0:
        raise ValueError("max_retries must be a non-negative integer")
    existing_by_subtopic = _existing_assets(existing_body)
    output_by_subtopic: dict[str, list[dict[str, Any]]] = {}
    progress = _initial_progress()
    target_ids = list(target_subtopic_ids) if target_subtopic_ids is not None else None
    units = build_work_units(inputs, target_subtopic_ids=target_ids)
    current_anchor_by_subtopic: dict[str, dict[str, Any]] = {}

    for unit in units:
        scoped = {**inputs, "subtopic_id": unit.subtopic_id}
        spec = student_content.resolve_asset_spec(
            student_content.ASSET_SPECS[unit.asset_type],
            scoped,
        )
        record = _unit_record(unit, status="running", attempts=0)
        progress["current"] = {
            "stage": "student_content",
            "subtopic_id": unit.subtopic_id,
            "asset_type": unit.asset_type,
            "asset_id": unit.asset_id,
        }
        _emit(progress_callback, record)

        existing = existing_by_subtopic.get(unit.subtopic_id, {}).get(unit.asset_id)
        if _asset_complete(existing):
            output_by_subtopic.setdefault(unit.subtopic_id, []).append(deepcopy(existing))
            if unit.asset_type == "course_content":
                current_anchor_by_subtopic[unit.subtopic_id] = deepcopy(existing)
            _record(progress, {**record, "status": "skipped"})
            continue

        gap = _evidence_gap(spec, scoped)
        if gap:
            _record(progress, {**record, "status": "evidence_gap", "error": gap})
            if not continue_on_error:
                break
            continue

        if (
            spec.conditioned_on_course_content
            and unit.subtopic_id not in current_anchor_by_subtopic
        ):
            _record(
                progress,
                {
                    **record,
                    "status": "pending",
                    "error": "Course Content anchor is not available for this subtopic.",
                },
            )
            if not continue_on_error:
                break
            continue

        generated: dict[str, Any] | None = None
        last_error: Exception | None = None
        attempts = max_retries + 1
        attempt_count = 0
        for attempt in range(1, attempts + 1):
            attempt_count = attempt
            try:
                generated = student_content.generate_asset_to_depth(
                    spec,
                    scoped,
                    course_content=current_anchor_by_subtopic.get(unit.subtopic_id)
                    if spec.conditioned_on_course_content
                    else None,
                    model=model,
                    use_cache=use_cache,
                )
                break
            except Exception as exc:  # noqa: BLE001 - progress must retain recoverable failures
                last_error = exc
                if attempt == attempts:
                    break

        if generated is None:
            _record(
                progress,
                {
                    **record,
                    "status": "failed",
                    "attempts": attempts,
                    "error": str(last_error),
                },
            )
            if not continue_on_error:
                break
            continue

        output_by_subtopic.setdefault(unit.subtopic_id, []).append(generated)
        if unit.asset_type == "course_content":
            current_anchor_by_subtopic[unit.subtopic_id] = generated
        _record(progress, {**record, "status": "completed", "attempts": attempt_count})

    body = {
        "asset_vocabulary": ASSET_VOCABULARY,
        "subtopics": [
            {"subtopic_id": subtopic_id, "assets": output_by_subtopic.get(subtopic_id, [])}
            for subtopic_id in planned_subtopic_ids(inputs)
            if (not target_ids or subtopic_id in set(target_ids))
            and output_by_subtopic.get(subtopic_id)
        ],
    }
    progress["current"] = None
    progress["totals"] = _status_counts(progress["units"])
    progress["expected_asset_count"] = len(units)
    progress["completed_asset_count"] = sum(
        len(subtopic["assets"]) for subtopic in body["subtopics"]
    )
    progress["complete"] = progress["completed_asset_count"] == len(units) and not any(
        unit["status"] in {"failed", "pending", "evidence_gap"} for unit in progress["units"]
    )
    return body, progress


def assert_exact_selected_assets(
    content_package_body: dict[str, Any],
    inputs: dict[str, Any],
    *,
    target_subtopic_ids: list[str] | tuple[str, ...] | None = None,
) -> None:
    """Raise if the package does not contain exactly selected Blueprint assets."""
    expected = {
        (unit.subtopic_id, unit.asset_id): unit
        for unit in build_work_units(inputs, target_subtopic_ids=target_subtopic_ids)
    }
    actual: dict[tuple[str, str], dict[str, Any]] = {}
    for subtopic in content_package_body.get("subtopics", []):
        subtopic_id = subtopic.get("subtopic_id")
        for asset in subtopic.get("assets", []):
            key = (subtopic_id, asset.get("id"))
            if key in actual:
                raise ValueError(f"Duplicate generated asset {key}")
            actual[key] = asset
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    if missing or extra:
        raise ValueError(f"Content Package selection mismatch: missing={missing}, extra={extra}")
    for key, unit in expected.items():
        asset = actual[key]
        if asset.get("type") != unit.asset_type:
            raise ValueError(f"Asset {unit.asset_id} has type {asset.get('type')!r}")


def _body(artifact: dict[str, Any]) -> dict[str, Any]:
    body = artifact.get("body", artifact)
    if not isinstance(body, dict):
        raise ValueError("expected an artifact envelope or body object")
    return body


def _existing_assets(existing_body: dict[str, Any] | None) -> dict[str, dict[str, dict[str, Any]]]:
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for subtopic in (existing_body or {}).get("subtopics", []):
        subtopic_id = subtopic.get("subtopic_id")
        if not isinstance(subtopic_id, str):
            continue
        result[subtopic_id] = {
            asset["id"]: asset
            for asset in subtopic.get("assets", [])
            if isinstance(asset, dict) and isinstance(asset.get("id"), str)
        }
    return result


def _asset_complete(asset: dict[str, Any] | None) -> bool:
    return bool(asset and asset.get("status") == "done" and isinstance(asset.get("content"), str))


def _evidence_gap(spec: student_content.AssetSpec, inputs: dict[str, Any]) -> str | None:
    try:
        source_ids = student_content.routed_source_ids(spec, inputs)
    except ValueError as exc:
        return str(exc)
    if not source_ids:
        return f"Selected asset {spec.asset_type!r} has no approved routed sources."
    return None


def _initial_progress() -> dict[str, Any]:
    return {
        "stage": "student_content",
        "current": None,
        "units": [],
        "totals": {},
        "expected_asset_count": 0,
        "completed_asset_count": 0,
        "complete": False,
    }


def _unit_record(unit: WorkUnit, *, status: str, attempts: int) -> dict[str, Any]:
    return {
        "stage": "student_content",
        "subtopic_id": unit.subtopic_id,
        "asset_type": unit.asset_type,
        "asset_id": unit.asset_id,
        "title": unit.title,
        "format": unit.format,
        "status": status,
        "attempts": attempts,
        "error": None,
    }


def _record(progress: dict[str, Any], record: dict[str, Any]) -> None:
    progress["units"].append(record)


def _status_counts(units: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for unit in units:
        status = unit.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _emit(callback: ProgressCallback | None, record: dict[str, Any]) -> None:
    if callback is not None:
        callback(record)
