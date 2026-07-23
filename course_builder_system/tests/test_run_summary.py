from __future__ import annotations

from pathlib import Path

import run_summary
import steps


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


def test_run_summary_reconciles_targeted_progress_to_current_package() -> None:
    content_package = {
        "course_id": "targeted-repair",
        "artifact_type": "content_package",
        "status": "approved",
        "body": {
            "subtopics": [
                {
                    "subtopic_id": "m1_s1",
                    "assets": [
                        {
                            "id": "m1_s1_cc",
                            "type": "course_content",
                            "title": "Core content",
                            "format": "markdown",
                            "status": "done",
                            "verification": {},
                        },
                        {
                            "id": "m1_s1_resources",
                            "type": "resources",
                            "title": "Resources",
                            "format": "markdown",
                            "status": "done",
                            "verification": {},
                        },
                    ],
                }
            ]
        },
    }
    result = steps.run_summary_step(
        {
            "content_package": content_package,
            "content_progress": {
                "body": {
                    "units": [
                        {
                            "stage": "student_content",
                            "subtopic_id": "m1_s1",
                            "asset_type": "targeted_repair",
                            "asset_id": "targeted_revision",
                            "status": "completed",
                            "attempts": 1,
                            "error": None,
                        }
                    ]
                }
            },
            "render_manifest": {
                "status": "draft",
                "body": {"paths": {"assets": {}}},
            },
        },
        None,
    )["run_summary"]["body"]

    assert [unit["asset_id"] for unit in result["student_content_units"]] == [
        "m1_s1_cc",
        "m1_s1_resources",
    ]
    assert result["student_content_totals"]["completed"] == 2
    assert result["operator_status"] == "complete"
