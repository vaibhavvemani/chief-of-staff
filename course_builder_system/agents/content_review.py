"""Durable, per-asset human review decisions for generated course content."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Literal

from orchestrator import make_artifact

ReviewDecision = Literal["pending", "approved", "changes_requested"]
ALLOWED_DECISIONS = {"pending", "approved", "changes_requested"}


def build_content_review_artifact(
    content_package: dict[str, Any],
    *,
    existing_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create or synchronize the human-review ledger for a Content Package.

    Review decisions survive a synchronization only while the corresponding
    generated asset is byte-for-byte equivalent for review purposes. A revised
    asset receives a new fingerprint and returns to ``pending``.
    """
    course_id = _required_string(content_package, "course_id")
    package_body = _body(content_package, "content_package")
    previous = _review_records(existing_review)
    records: list[dict[str, Any]] = []

    for subtopic in package_body.get("subtopics", []):
        subtopic_id = _required_string(subtopic, "subtopic_id")
        for asset in subtopic.get("assets", []):
            asset_id = _required_string(asset, "id")
            fingerprint = asset_fingerprint(asset)
            prior = previous.get(asset_id)
            if prior and prior.get("asset_fingerprint") == fingerprint:
                decision = prior.get("decision", "pending")
                feedback = prior.get("feedback")
                reviewed_at = prior.get("reviewed_at")
            else:
                decision = "pending"
                feedback = None
                reviewed_at = None
            records.append(
                {
                    "asset_id": asset_id,
                    "subtopic_id": subtopic_id,
                    "asset_type": _required_string(asset, "type"),
                    "title": _required_string(asset, "title"),
                    "asset_fingerprint": fingerprint,
                    "decision": decision,
                    "feedback": feedback,
                    "reviewed_at": reviewed_at,
                    "verification_blockers": _verification_blockers(asset),
                }
            )

    body = {"assets": records}
    body["summary"] = review_summary(body)
    return make_artifact(
        course_id,
        "content_review",
        "content_review",
        body=body,
        inputs=["content_package"],
        schema_version="0.1",
    )


def apply_content_review_decision(
    content_review: dict[str, Any],
    *,
    asset_id: str,
    decision: ReviewDecision,
    feedback: str | None = None,
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    """Apply one explicit human decision without mutating the input artifact."""
    if decision not in ALLOWED_DECISIONS:
        raise ValueError(f"invalid content review decision {decision!r}")
    if decision == "changes_requested" and not (feedback or "").strip():
        raise ValueError("changes_requested requires non-empty feedback")

    decided = deepcopy(content_review)
    body = _body(decided, "content_review")
    match = next(
        (record for record in body.get("assets", []) if record.get("asset_id") == asset_id),
        None,
    )
    if match is None:
        raise ValueError(f"content review contains no asset {asset_id!r}")

    match["decision"] = decision
    match["feedback"] = (feedback or "").strip() or None
    match["reviewed_at"] = None if decision == "pending" else reviewed_at or _now()
    body["summary"] = review_summary(body)
    return decided


def review_summary(review_body: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic review and blocker totals for the workspace gate."""
    records = review_body.get("assets", [])
    counts = {decision: 0 for decision in sorted(ALLOWED_DECISIONS)}
    blocker_totals = {"unsupported": 0, "ungrounded": 0, "unattributed": 0}
    for record in records:
        decision = record.get("decision", "pending")
        if decision in counts:
            counts[decision] += 1
        blockers = record.get("verification_blockers", {})
        for key in blocker_totals:
            value = blockers.get(key, 0) if isinstance(blockers, dict) else 0
            if isinstance(value, int):
                blocker_totals[key] += value
    total_blockers = sum(blocker_totals.values())
    return {
        "total": len(records),
        "pending": counts["pending"],
        "approved": counts["approved"],
        "changes_requested": counts["changes_requested"],
        "verification_blockers": blocker_totals,
        "ready_for_package": bool(records)
        and counts["pending"] == 0
        and counts["changes_requested"] == 0
        and total_blockers == 0,
    }


def asset_fingerprint(asset: dict[str, Any]) -> str:
    """Hash only generated/review-relevant fields using canonical JSON."""
    payload = {
        "id": asset.get("id"),
        "type": asset.get("type"),
        "title": asset.get("title"),
        "content": asset.get("content"),
        "solution": asset.get("solution"),
        "claims": asset.get("claims", []),
        "sources": asset.get("sources", []),
        "verification": asset.get("verification", {}),
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _verification_blockers(asset: dict[str, Any]) -> dict[str, int]:
    verification = asset.get("verification", {})
    if not isinstance(verification, dict):
        verification = {}
    unattributed = verification.get("unattributed_found", [])
    return {
        "unsupported": _nonnegative_int(verification.get("unsupported")),
        "ungrounded": _nonnegative_int(verification.get("ungrounded")),
        "unattributed": len(unattributed) if isinstance(unattributed, list) else 0,
    }


def _review_records(content_review: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not content_review:
        return {}
    body = content_review.get("body", content_review)
    if not isinstance(body, dict):
        return {}
    return {
        record["asset_id"]: record
        for record in body.get("assets", [])
        if isinstance(record, dict) and isinstance(record.get("asset_id"), str)
    }


def _body(artifact: dict[str, Any], name: str) -> dict[str, Any]:
    body = artifact.get("body", artifact)
    if not isinstance(body, dict):
        raise ValueError(f"{name} must contain an object body")
    return body


def _required_string(value: dict[str, Any], field: str) -> str:
    result = value.get(field)
    if not isinstance(result, str) or not result:
        raise ValueError(f"{field} must be a non-empty string")
    return result


def _nonnegative_int(value: Any) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
