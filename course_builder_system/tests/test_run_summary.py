from __future__ import annotations

from pathlib import Path

import run_summary


def test_run_summary_requires_attention_for_blocking_verifier_findings() -> None:
    summary = run_summary.build_run_summary_body(
        course_id="coffee-live",
        stage_records=[run_summary.stage_record("content_package", "completed")],
        output_paths={},
        unit_records=[{"status": "completed"}],
        token_log_path=Path("logs/llm_calls.jsonl"),
        verification_totals={
            "supported": 4,
            "partial": 1,
            "unsupported": 1,
            "ungrounded": 0,
            "unattributed": 0,
        },
    )

    assert summary["operator_status"] == "requires_attention"
    assert summary["verification_totals"]["unsupported"] == 1


def test_run_summary_records_non_blocking_partial_verifier_findings() -> None:
    summary = run_summary.build_run_summary_body(
        course_id="coffee-live",
        stage_records=[run_summary.stage_record("content_package", "completed")],
        output_paths={},
        unit_records=[{"status": "completed"}],
        token_log_path=Path("logs/llm_calls.jsonl"),
        verification_totals={
            "supported": 4,
            "partial": 2,
            "unsupported": 0,
            "ungrounded": 0,
            "unattributed": 0,
        },
    )

    assert summary["operator_status"] == "complete"
    assert summary["verification_totals"]["partial"] == 2
