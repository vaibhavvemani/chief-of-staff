from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from agents import content_review
from tests.schema_check import validate

ROOT = Path(__file__).resolve().parents[1]
LIVE_PACKAGE = (
    ROOT
    / "examples"
    / "live-runs"
    / "coffee-live-main"
    / "course_artifacts"
    / "content_package.json"
)
SCHEMA = ROOT / "schemas" / "content_review.v0.1.schema.json"


def _package() -> dict:
    return json.loads(LIVE_PACKAGE.read_text(encoding="utf-8"))


def test_content_review_tracks_every_asset_and_verifier_blocker() -> None:
    review = content_review.build_content_review_artifact(_package())

    assert len(review["body"]["assets"]) == 18
    assert review["body"]["summary"] == {
        "total": 18,
        "pending": 18,
        "approved": 0,
        "changes_requested": 0,
        "verification_blockers": {
            "unsupported": 5,
            "ungrounded": 1,
            "unattributed": 3,
        },
        "ready_for_package": False,
    }
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert validate(review, schema) == []


def test_content_review_decision_is_explicit_and_non_mutating() -> None:
    original = content_review.build_content_review_artifact(_package())
    decided = content_review.apply_content_review_decision(
        original,
        asset_id="m1_s1_lo",
        decision="approved",
        reviewed_at="2026-07-13T00:00:00+00:00",
    )

    assert original["body"]["summary"]["pending"] == 18
    assert decided["body"]["summary"]["approved"] == 1
    assert decided["body"]["summary"]["pending"] == 17


def test_content_review_resets_only_a_changed_asset() -> None:
    package = _package()
    existing = content_review.build_content_review_artifact(package)
    existing = content_review.apply_content_review_decision(
        existing,
        asset_id="m1_s1_lo",
        decision="approved",
    )
    existing = content_review.apply_content_review_decision(
        existing,
        asset_id="m1_s1_summary",
        decision="approved",
    )

    revised_package = deepcopy(package)
    revised_package["body"]["subtopics"][0]["assets"][1]["content"] += " Revised."
    synced = content_review.build_content_review_artifact(
        revised_package,
        existing_review=existing,
    )
    by_id = {record["asset_id"]: record for record in synced["body"]["assets"]}

    assert by_id["m1_s1_lo"]["decision"] == "pending"
    assert by_id["m1_s1_summary"]["decision"] == "approved"


def test_changes_requested_requires_feedback() -> None:
    review = content_review.build_content_review_artifact(_package())

    with pytest.raises(ValueError, match="requires non-empty feedback"):
        content_review.apply_content_review_decision(
            review,
            asset_id="m1_s1_lo",
            decision="changes_requested",
        )
