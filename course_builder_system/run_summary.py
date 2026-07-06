"""Run-summary artifact helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from orchestrator import make_artifact


def build_run_summary_artifact(
    *,
    course_id: str,
    stage_records: list[dict[str, Any]],
    output_paths: dict[str, Any] | None = None,
    unit_records: list[dict[str, Any]] | None = None,
    content_package: dict[str, Any] | None = None,
    token_log_path: Path = Path("logs/llm_calls.jsonl"),
    inputs: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Create a deterministic summary of a course-builder run."""
    body = build_run_summary_body(
        course_id=course_id,
        stage_records=stage_records,
        output_paths=output_paths or {},
        unit_records=unit_records or [],
        verification_totals=_verification_totals(content_package or {}),
        token_log_path=token_log_path,
    )
    return make_artifact(
        course_id,
        "run_summary",
        "run_summary",
        body=body,
        inputs=list(inputs or []),
    )


def build_run_summary_body(
    *,
    course_id: str,
    stage_records: list[dict[str, Any]],
    output_paths: dict[str, Any],
    unit_records: list[dict[str, Any]],
    token_log_path: Path,
    verification_totals: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Return the run-summary body without wrapping it as an artifact."""
    stage_totals = _counts(stage_records)
    unit_totals = _counts(unit_records)
    verification_totals = verification_totals or _empty_verification_totals()
    return {
        "course_id": course_id,
        "operator_status": _operator_status(stage_totals, unit_totals, verification_totals),
        "stages": stage_records,
        "stage_totals": stage_totals,
        "student_content_units": unit_records,
        "student_content_totals": unit_totals,
        "verification_totals": verification_totals,
        "resume": {
            "safe_to_rerun": True,
            "behavior": (
                "Rerunning the same command skips approved current artifacts and "
                "regenerates only missing, stale, rejected, or revised steps."
            ),
            "checkpoint_directory": f"courses/{course_id}",
        },
        "token_and_cost_references": {
            "llm_log_path": str(token_log_path),
            "pricing_reference": "llm.py::_MODEL_PRICING_PER_MTOK",
        },
        "output_paths": output_paths,
    }


def stage_record(
    name: str,
    status: str,
    *,
    artifact_types: list[str] | tuple[str, ...] | None = None,
    output_path: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Build one run-summary stage record."""
    if status not in {"completed", "skipped", "failed", "pending_review"}:
        raise ValueError(f"invalid run-summary status {status!r}")
    return {
        "name": name,
        "status": status,
        "artifact_types": list(artifact_types or []),
        "output_path": output_path,
        "error": error,
    }


def _counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"completed": 0, "skipped": 0, "failed": 0, "pending_review": 0}
    for record in records:
        status = record.get("status")
        if isinstance(status, str):
            counts[status] = counts.get(status, 0) + 1
    return counts


def _operator_status(
    stage_totals: dict[str, int],
    unit_totals: dict[str, int],
    verification_totals: dict[str, int] | None = None,
) -> str:
    if stage_totals.get("failed", 0) or unit_totals.get("failed", 0):
        return "requires_attention"
    if unit_totals.get("evidence_gap", 0) or unit_totals.get("pending", 0):
        return "requires_attention"
    verification_totals = verification_totals or {}
    if (
        verification_totals.get("unsupported", 0)
        or verification_totals.get("ungrounded", 0)
        or verification_totals.get("unattributed", 0)
    ):
        return "requires_attention"
    if stage_totals.get("pending_review", 0):
        return "pending_review"
    return "complete"


def _empty_verification_totals() -> dict[str, int]:
    return {
        "supported": 0,
        "partial": 0,
        "unsupported": 0,
        "ungrounded": 0,
        "unattributed": 0,
    }


def _verification_totals(content_package: dict[str, Any]) -> dict[str, int]:
    totals = _empty_verification_totals()
    body = content_package.get("body", content_package)
    if not isinstance(body, dict):
        return totals
    for subtopic in body.get("subtopics", []):
        for asset in subtopic.get("assets", []):
            verification = asset.get("verification", {})
            if not isinstance(verification, dict):
                continue
            for field in ("supported", "partial", "unsupported", "ungrounded"):
                value = verification.get(field, 0)
                if isinstance(value, int):
                    totals[field] += value
            unattributed = verification.get("unattributed_found", [])
            if isinstance(unattributed, list):
                totals["unattributed"] += len(unattributed)
    return totals
