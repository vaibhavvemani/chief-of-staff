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
    token_log_path: Path = Path("logs/llm_calls.jsonl"),
) -> dict[str, Any]:
    """Create a deterministic summary of a course-builder run."""
    body = build_run_summary_body(
        stage_records=stage_records,
        output_paths=output_paths or {},
        unit_records=unit_records or [],
        token_log_path=token_log_path,
    )
    return make_artifact(
        course_id,
        "run_summary",
        "run_summary",
        body=body,
        inputs=[],
    )


def build_run_summary_body(
    *,
    stage_records: list[dict[str, Any]],
    output_paths: dict[str, Any],
    unit_records: list[dict[str, Any]],
    token_log_path: Path,
) -> dict[str, Any]:
    """Return the run-summary body without wrapping it as an artifact."""
    return {
        "stages": stage_records,
        "stage_totals": _counts(stage_records),
        "student_content_units": unit_records,
        "student_content_totals": _counts(unit_records),
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
        if status in counts:
            counts[status] += 1
    return counts
