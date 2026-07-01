"""Phase 1 evaluation, blind-review, ratification, and trend tooling.

The module deliberately separates three kinds of evidence:

* deterministic mechanical evidence from the generated package;
* optional LLM head-to-head proposals (never final judgments); and
* blind human scores, which are the only evidence that can close the gate.

Run ``python3 evals/compare.py --help`` for the file-based CLI.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import llm  # noqa: E402

SCORECARD_VERSION = "1.0"
BLIND_PACKET_VERSION = "1.0"
CORE_ASSET_TYPES = (
    "course_content",
    "learning_objectives",
    "summary",
    "case_study",
    "assessment",
)
LIGHT_ASSET_TYPES = ("important_person", "did_you_know", "activities", "resources")
ASSET_ORDER = CORE_ASSET_TYPES + LIGHT_ASSET_TYPES
DIMENSIONS = (
    "factual_accuracy",
    "coverage",
    "source_attribution",
    "pedagogical_clarity",
    "asset_completeness",
    "house_style",
    "review_time",
)
LLM_DIMENSIONS = ("coverage", "house_style")
HUMAN_ONLY_DIMENSIONS = ("pedagogical_clarity", "review_time")
ALLOWED_EDIT_EXTENTS = {"none", "light", "moderate", "heavy", "rewrite"}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_json(value: Any) -> str:
    return _sha256_bytes(_canonical_json(value).encode("utf-8"))


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_package(path: Path) -> dict[str, Any]:
    package = _load_json(path)
    if package.get("artifact_type") != "content_package":
        raise ValueError(f"{path} is not a content_package artifact")
    if package.get("schema_version") != "0.2":
        raise ValueError(f"{path} must use Content Package schema_version '0.2'")
    body = package.get("body")
    if not isinstance(body, dict) or not isinstance(body.get("subtopics"), list):
        raise ValueError(f"{path} has no valid body.subtopics array")
    return package


def _subtopic_assets(package: dict[str, Any], subtopic_id: str) -> dict[str, dict[str, Any]]:
    for subtopic in package["body"]["subtopics"]:
        if subtopic.get("subtopic_id") != subtopic_id:
            continue
        assets = subtopic.get("assets")
        if not isinstance(assets, list):
            raise ValueError(f"Subtopic {subtopic_id!r} has no valid assets array")
        by_type: dict[str, dict[str, Any]] = {}
        for asset in assets:
            if not isinstance(asset, dict) or not isinstance(asset.get("type"), str):
                raise ValueError(f"Subtopic {subtopic_id!r} contains an invalid asset")
            asset_type = asset["type"]
            if asset_type in by_type:
                raise ValueError(
                    f"Subtopic {subtopic_id!r} contains duplicate {asset_type!r} assets"
                )
            by_type[asset_type] = asset
        return by_type
    raise ValueError(f"Subtopic {subtopic_id!r} not found in package")


def _evaluation_context(
    course_model_path: Path | None,
    subtopic_id: str,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Load the approved scope contract without exposing source bodies."""
    if course_model_path is None:
        return None, {"course_model_path": None, "course_model_sha256": None}
    path = course_model_path.resolve()
    artifact = _load_json(path)
    body = artifact.get("body", artifact)
    metadata = body.get("course_metadata", {})
    for module in body.get("modules", []):
        for subtopic in module.get("subtopics", []):
            if subtopic.get("id") != subtopic_id:
                continue
            context = {
                "course_title": metadata.get("course_title"),
                "subject": metadata.get("subject"),
                "audience_summary": metadata.get("audience_summary"),
                "level": metadata.get("level"),
                "module": {
                    "id": module.get("id"),
                    "title": module.get("title"),
                    "context": module.get("context"),
                },
                "subtopic": {
                    "id": subtopic.get("id"),
                    "title": subtopic.get("title"),
                    "context": subtopic.get("context"),
                    "concepts": subtopic.get("concepts", []),
                    "coverage_requirements": subtopic.get("coverage_requirements", []),
                },
            }
            return context, {
                "course_model_path": str(path),
                "course_model_sha256": _sha256_bytes(path.read_bytes()),
            }
    raise ValueError(f"Subtopic {subtopic_id!r} not found in Course Model {path}")


def _git_sha() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip()
    return value or None


def _ratio_score(ratio: float) -> int:
    """Map a 0..1 evidence ratio onto the rubric's 1..10 scale."""
    thresholds = (
        (0.99, 10),
        (0.97, 9),
        (0.95, 8),
        (0.90, 7),
        (0.80, 6),
        (0.70, 5),
        (0.55, 4),
        (0.40, 3),
        (0.20, 2),
    )
    for threshold, score in thresholds:
        if ratio >= threshold:
            return score
    return 1


def _verifier_evidence(asset: dict[str, Any] | None) -> dict[str, Any]:
    if asset is None:
        return {
            "checked_at": None,
            "claim_count": 0,
            "supported": 0,
            "partial": 0,
            "unsupported": 0,
            "ungrounded": 0,
            "unattributed_found": [],
            "pending_verdicts": 0,
            "summary_consistent": False,
            "summary_mismatches": ["asset is missing"],
        }

    claims = asset.get("claims") if isinstance(asset.get("claims"), list) else []
    verification = asset.get("verification") if isinstance(asset.get("verification"), dict) else {}
    derived = {
        "supported": sum(claim.get("support") == "supported" for claim in claims),
        "partial": sum(claim.get("support") == "partial" for claim in claims),
        "unsupported": sum(claim.get("support") == "unsupported" for claim in claims),
        "ungrounded": sum(claim.get("source_id") is None for claim in claims),
    }
    # Ungrounded claims intentionally keep support=None: the verifier cannot
    # issue a source-support verdict when there is no source. Only attributed
    # claims without a verdict make verification incomplete.
    pending = sum(
        claim.get("source_id") is not None and claim.get("support") is None for claim in claims
    )
    unattributed = verification.get("unattributed_found", [])
    if not isinstance(unattributed, list):
        unattributed = []

    mismatches = []
    for field, derived_value in derived.items():
        if verification.get(field) != derived_value:
            mismatches.append(
                f"verification.{field}={verification.get(field)!r}, derived={derived_value}"
            )

    return {
        "checked_at": verification.get("checked_at"),
        "claim_count": len(claims),
        **derived,
        "unattributed_found": [str(item) for item in unattributed],
        "pending_verdicts": pending,
        "summary_consistent": not mismatches,
        "summary_mismatches": mismatches,
    }


def _verification_ready(evidence: dict[str, Any]) -> bool:
    return bool(
        evidence["checked_at"]
        and evidence["pending_verdicts"] == 0
        and evidence["summary_consistent"]
    )


def _factual_accuracy(asset: dict[str, Any] | None) -> dict[str, Any]:
    evidence = _verifier_evidence(asset)
    if not _verification_ready(evidence):
        return {
            "score": 1,
            "status": "mechanical_provisional",
            "method": "verifier verdict quality; incomplete/inconsistent verification scores 1",
            "evidence": evidence,
        }

    total = evidence["claim_count"] + len(evidence["unattributed_found"])
    if total == 0:
        score = 6
        ratio = None
        note = "No significant claims were declared or found; neutral manual-equivalent proposal."
    else:
        ratio = (evidence["supported"] + 0.5 * evidence["partial"]) / total
        score = _ratio_score(ratio)
        note = "Unsupported, ungrounded, pending, and unattributed claims receive no credit."
    evidence = {**evidence, "weighted_support_ratio": ratio, "note": note}
    return {
        "score": score,
        "status": "mechanical_provisional",
        "method": "supported=1, partial=0.5, all other significant claims=0",
        "evidence": evidence,
    }


def _source_attribution(asset: dict[str, Any] | None) -> dict[str, Any]:
    evidence = _verifier_evidence(asset)
    if not _verification_ready(evidence):
        return {
            "score": 1,
            "status": "mechanical_provisional",
            "method": "traceable supported claims; incomplete/inconsistent verification scores 1",
            "evidence": evidence,
        }

    total = evidence["claim_count"] + len(evidence["unattributed_found"])
    if total == 0:
        score = 6
        ratio = None
        note = "No significant claims were declared or found; neutral manual-equivalent proposal."
    else:
        ratio = (evidence["supported"] + 0.5 * evidence["partial"]) / total
        score = _ratio_score(ratio)
        note = "A citation receives credit only when the verifier confirms its support."
    evidence = {**evidence, "traceable_support_ratio": ratio, "note": note}
    return {
        "score": score,
        "status": "mechanical_provisional",
        "method": (
            "supported citation=1, partial citation=0.5, unsupported/ungrounded/unattributed=0"
        ),
        "evidence": evidence,
    }


def _asset_completeness(asset: dict[str, Any] | None, asset_type: str) -> dict[str, Any]:
    checks: dict[str, bool] = {
        "asset_present": asset is not None,
        "type_matches": bool(asset and asset.get("type") == asset_type),
        "id_present": bool(asset and isinstance(asset.get("id"), str) and asset["id"].strip()),
        "title_present": bool(
            asset and isinstance(asset.get("title"), str) and asset["title"].strip()
        ),
        "format_present": bool(
            asset and isinstance(asset.get("format"), str) and asset["format"].strip()
        ),
        "content_nonempty": bool(
            asset
            and isinstance(asset.get("content"), str)
            and asset["content"].strip()
            and "<" not in asset["content"][:2]
        ),
        "claims_array": bool(asset and isinstance(asset.get("claims"), list)),
        "sources_array": bool(asset and isinstance(asset.get("sources"), list)),
        "verification_object": bool(asset and isinstance(asset.get("verification"), dict)),
        "status_present": bool(
            asset and isinstance(asset.get("status"), str) and asset["status"].strip()
        ),
    }
    if asset_type == "assessment":
        checks["solution_nonempty"] = bool(
            asset and isinstance(asset.get("solution"), str) and asset["solution"].strip()
        )
    ratio = sum(checks.values()) / len(checks)
    return {
        "score": _ratio_score(ratio),
        "status": "mechanical_provisional",
        "method": "required asset/field checks; content depth is scored under coverage",
        "evidence": {
            "checks": checks,
            "passed": sum(checks.values()),
            "total": len(checks),
            "completion_ratio": ratio,
            "failed_checks": [name for name, passed in checks.items() if not passed],
        },
    }


def _pending_dimension(reason: str, status: str = "pending_human") -> dict[str, Any]:
    return {"score": None, "status": status, "method": None, "evidence": {"reason": reason}}


def _judge_schema() -> dict[str, Any]:
    dimension = {
        "type": "object",
        "additionalProperties": False,
        "required": ["score", "comparison", "evidence"],
        "properties": {
            "score": {"type": "integer"},
            "comparison": {"type": "string", "enum": ["below", "matches", "exceeds"]},
            "evidence": {"type": "string"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["assessments"],
        "properties": {
            "assessments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["asset_type", "coverage", "house_style"],
                    "properties": {
                        "asset_type": {"type": "string"},
                        "coverage": dimension,
                        "house_style": dimension,
                    },
                },
            }
        },
    }


def _judge_prompt(
    agent_assets: dict[str, dict[str, Any]],
    gold_assets: dict[str, dict[str, Any]],
    asset_types: Iterable[str],
    evaluation_context: dict[str, Any] | None = None,
) -> str:
    comparisons = []
    for asset_type in asset_types:
        if asset_type not in agent_assets or asset_type not in gold_assets:
            continue
        comparisons.append(
            {
                "asset_type": asset_type,
                "agent": {
                    "title": agent_assets[asset_type].get("title"),
                    "content": agent_assets[asset_type].get("content"),
                    "solution": agent_assets[asset_type].get("solution"),
                },
                "manual": {
                    "title": gold_assets[asset_type].get("title"),
                    "content": gold_assets[asset_type].get("content"),
                    "solution": gold_assets[asset_type].get("solution"),
                },
            }
        )
    payload = {
        "approved_scope_contract": evaluation_context,
        "comparisons": comparisons,
    }
    return (
        "You are proposing two rubric scores by comparing generated course assets "
        "head-to-head with their manual references. The manual reference anchors score 6. "
        "Use 1-5 when the agent is worse, 6 when it matches, and 7-10 when it is better. "
        "Coverage means essential scope and useful depth. House style means tone, headings, "
        "bullet density, seriousness, and structure. Return every supplied asset exactly once. "
        "When an approved scope contract is supplied, score coverage against that contract: "
        "do not penalize either candidate for omitting manual material explicitly out of scope. "
        "The manual still anchors style and quality. Your result is advisory and will be "
        "ratified by a human.\n\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _llm_judge(
    agent_assets: dict[str, dict[str, Any]],
    gold_assets: dict[str, dict[str, Any]],
    asset_types: Iterable[str],
    model: str,
    evaluation_context: dict[str, Any] | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    expected = [
        asset_type
        for asset_type in asset_types
        if asset_type in agent_assets and asset_type in gold_assets
    ]
    result = llm.call(
        [
            {
                "role": "user",
                "content": _judge_prompt(
                    agent_assets,
                    gold_assets,
                    expected,
                    evaluation_context,
                ),
            }
        ],
        system=(
            "You are an independent course-quality evaluator. Compare the supplied pairs; "
            "do not infer human approval and do not score dimensions you were not asked to score."
        ),
        model=model,
        max_tokens=6000,
        schema=_judge_schema(),
    )
    parsed = result.parsed if result.parsed is not None else json.loads(result.text)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("assessments"), list):
        raise ValueError("LLM judge returned an invalid assessments object")

    proposals: dict[str, dict[str, Any]] = {}
    for item in parsed["assessments"]:
        if not isinstance(item, dict) or item.get("asset_type") not in expected:
            raise ValueError("LLM judge returned an unknown or invalid asset_type")
        asset_type = item["asset_type"]
        if asset_type in proposals:
            raise ValueError(f"LLM judge returned duplicate assessment for {asset_type}")
        proposals[asset_type] = {}
        for dimension in LLM_DIMENSIONS:
            proposal = item.get(dimension)
            if not isinstance(proposal, dict):
                raise ValueError(f"LLM judge omitted {dimension} for {asset_type}")
            score = proposal.get("score")
            if not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 10:
                raise ValueError(f"LLM judge score must be 1..10 for {asset_type}.{dimension}")
            proposals[asset_type][dimension] = {
                "score": score,
                "status": "llm_proposal_pending_human_ratification",
                "method": "LLM head-to-head proposal; manual asset anchors score 6",
                "evidence": {
                    "comparison": proposal.get("comparison"),
                    "rationale": proposal.get("evidence"),
                },
            }
    missing = sorted(set(expected) - set(proposals))
    if missing:
        raise ValueError(f"LLM judge omitted assets: {', '.join(missing)}")
    metadata = {
        "enabled": True,
        "model": result.model,
        "prompt_hash": result.prompt_hash,
        "cache_hit": result.cache_hit,
    }
    return proposals, metadata


def _aggregate_verifier_stats(asset_rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_fields = ("claim_count", "supported", "partial", "unsupported", "ungrounded")
    aggregate = {field: 0 for field in total_fields}
    aggregate["unattributed_found"] = 0
    aggregate["assets_checked"] = 0
    aggregate["assets_consistent"] = 0
    for row in asset_rows:
        evidence = row["dimensions"]["factual_accuracy"]["evidence"]
        for field in total_fields:
            aggregate[field] += int(evidence.get(field, 0))
        aggregate["unattributed_found"] += len(evidence.get("unattributed_found", []))
        aggregate["assets_checked"] += int(bool(evidence.get("checked_at")))
        aggregate["assets_consistent"] += int(bool(evidence.get("summary_consistent")))
    return aggregate


def build_scorecard(
    agent_path: Path,
    gold_path: Path,
    *,
    subtopic_id: str = "m1_s1",
    use_llm_judge: bool = False,
    model: str = llm.DEFAULT_MODEL,
    course_model_path: Path | None = None,
) -> dict[str, Any]:
    """Build a provisional scorecard. This function can never pass the human gate."""
    agent_path = agent_path.resolve()
    gold_path = gold_path.resolve()
    agent_package = _load_package(agent_path)
    gold_package = _load_package(gold_path)
    agent_assets = _subtopic_assets(agent_package, subtopic_id)
    gold_assets = _subtopic_assets(gold_package, subtopic_id)
    evaluation_context, context_inputs = _evaluation_context(course_model_path, subtopic_id)

    present_types = [
        asset_type
        for asset_type in ASSET_ORDER
        if asset_type in agent_assets or asset_type in gold_assets
    ]
    extra_types = sorted((set(agent_assets) | set(gold_assets)) - set(ASSET_ORDER))
    present_types.extend(extra_types)

    proposals: dict[str, dict[str, Any]] = {}
    judge_metadata: dict[str, Any] = {
        "enabled": False,
        "model": None,
        "prompt_hash": None,
        "cache_hit": None,
    }
    if use_llm_judge:
        proposals, judge_metadata = _llm_judge(
            agent_assets,
            gold_assets,
            present_types,
            model=model,
            evaluation_context=evaluation_context,
        )

    rows = []
    for asset_type in present_types:
        asset = agent_assets.get(asset_type)
        dimensions = {
            "factual_accuracy": _factual_accuracy(asset),
            "coverage": proposals.get(asset_type, {}).get(
                "coverage",
                _pending_dimension(
                    "Run score with --llm-judge for a proposal; a human still decides.",
                    status="pending_optional_llm_proposal_and_human",
                ),
            ),
            "source_attribution": _source_attribution(asset),
            "pedagogical_clarity": _pending_dimension(
                "Human judgment is required; this dimension is never auto-scored."
            ),
            "asset_completeness": _asset_completeness(asset, asset_type),
            "house_style": proposals.get(asset_type, {}).get(
                "house_style",
                _pending_dimension(
                    "Run score with --llm-judge for a proposal; a human still decides.",
                    status="pending_optional_llm_proposal_and_human",
                ),
            ),
            "review_time": _pending_dimension(
                "A human must record wall-clock minutes and edit extent."
            ),
        }
        rows.append(
            {
                "asset_id": asset.get("id") if asset else None,
                "asset_type": asset_type,
                "required_for_gate": asset_type in CORE_ASSET_TYPES,
                "manual_asset_present": asset_type in gold_assets,
                "dimensions": dimensions,
            }
        )

    mechanical_blockers = []
    for row in rows:
        if not row["required_for_gate"]:
            continue
        for dimension in ("factual_accuracy", "source_attribution", "asset_completeness"):
            score = row["dimensions"][dimension]["score"]
            if score is None or score < 6:
                mechanical_blockers.append(
                    f"{row['asset_type']}.{dimension} provisional score is {score!r} (<6)"
                )

    agent_hash = _sha256_bytes(agent_path.read_bytes())
    gold_hash = _sha256_bytes(gold_path.read_bytes())
    timestamp = _now()
    run_id = _sha256_json(
        {
            "agent_sha256": agent_hash,
            "gold_sha256": gold_hash,
            "subtopic_id": subtopic_id,
            "timestamp": timestamp,
            "judge_prompt_hash": judge_metadata["prompt_hash"],
        }
    )[:16]
    scorecard = {
        "scorecard_version": SCORECARD_VERSION,
        "run_id": run_id,
        "timestamp": timestamp,
        "subtopic_id": subtopic_id,
        "inputs": {
            "agent_path": str(agent_path),
            "agent_sha256": agent_hash,
            "gold_path": str(gold_path),
            "gold_sha256": gold_hash,
            **context_inputs,
        },
        "evaluation_context": evaluation_context,
        "prompt_git_sha": _git_sha(),
        "llm_judge": judge_metadata,
        "verifier_stats": _aggregate_verifier_stats(rows),
        "assets": rows,
        "pending_human_dimensions": list(HUMAN_ONLY_DIMENSIONS),
        "human_ratification": {
            "status": "pending",
            "note": "Automated scores and LLM judgments are proposals until blind human review.",
        },
        "human_review": None,
        "gate": {
            "status": "pending_human_review",
            "passed": False,
            "core_minimum_score": 6,
            "core_review_minutes_limit": 60,
            "provisional_mechanical_blockers": mechanical_blockers,
            "reasons": [
                "Blind human A/B scores, timed review, edit extent, and ratification are pending."
            ],
        },
    }
    return scorecard


def _candidate_asset(asset: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "type",
        "title",
        "format",
        "content",
        "claims",
        "sources",
        "verification",
        "solution",
    )
    return {key: copy.deepcopy(asset[key]) for key in allowed if key in asset}


def _rating_template() -> dict[str, Any]:
    return {
        "scores": {dimension: None for dimension in DIMENSIONS},
        "review_minutes": None,
        "edit_extent": None,
        "notes": "",
        "ratified": False,
    }


def build_blind_packet(
    agent_path: Path,
    gold_path: Path,
    *,
    subtopic_id: str = "m1_s1",
    course_model_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return an anonymized packet and its separate, hidden deterministic mapping."""
    agent_path = agent_path.resolve()
    gold_path = gold_path.resolve()
    agent_package = _load_package(agent_path)
    gold_package = _load_package(gold_path)
    agent_assets = _subtopic_assets(agent_package, subtopic_id)
    gold_assets = _subtopic_assets(gold_package, subtopic_id)
    evaluation_context, context_inputs = _evaluation_context(course_model_path, subtopic_id)
    shared_types = [
        asset_type
        for asset_type in ASSET_ORDER
        if asset_type in agent_assets and asset_type in gold_assets
    ]
    missing_core = sorted(
        set(CORE_ASSET_TYPES) - set(agent_assets) | set(CORE_ASSET_TYPES) - set(gold_assets)
    )
    if missing_core:
        raise ValueError(
            "Blind done-gate packet requires both versions of every core asset; missing: "
            + ", ".join(missing_core)
        )

    agent_hash = _sha256_bytes(agent_path.read_bytes())
    gold_hash = _sha256_bytes(gold_path.read_bytes())
    basis = _sha256_json(
        {
            "agent_sha256": agent_hash,
            "gold_sha256": gold_hash,
            "course_model_sha256": context_inputs["course_model_sha256"],
            "subtopic_id": subtopic_id,
        }
    )
    packet_id = basis[:16]
    assignments: dict[str, dict[str, str]] = {}
    packet_assets = []
    for asset_type in shared_types:
        agent_is_a = int(hashlib.sha256(f"{basis}:{asset_type}".encode()).hexdigest(), 16) % 2 == 0
        assignments[asset_type] = {
            "A": "agent" if agent_is_a else "gold",
            "B": "gold" if agent_is_a else "agent",
        }
        candidates = {
            "A": _candidate_asset(
                agent_assets[asset_type] if agent_is_a else gold_assets[asset_type]
            ),
            "B": _candidate_asset(
                gold_assets[asset_type] if agent_is_a else agent_assets[asset_type]
            ),
        }
        packet_assets.append(
            {
                "asset_type": asset_type,
                "required_for_gate": asset_type in CORE_ASSET_TYPES,
                "candidates": {
                    label: {"asset": candidate, "rating": _rating_template()}
                    for label, candidate in candidates.items()
                },
            }
        )

    commitment = _sha256_json(assignments)
    packet = {
        "blind_packet_version": BLIND_PACKET_VERSION,
        "packet_id": packet_id,
        "created_at": _now(),
        "subtopic_id": subtopic_id,
        "mapping_commitment": commitment,
        "instructions": {
            "score_scale": "1-10; 6 means manual-equivalent",
            "dimensions": list(DIMENSIONS),
            "edit_extent_values": sorted(ALLOWED_EDIT_EXTENTS),
            "completion": (
                "Score and ratify both candidates for every core asset. Record wall-clock "
                "minutes and edit extent separately for each candidate, then ratify the review. "
                "Score coverage against evaluation_context; do not reward out-of-scope breadth."
            ),
        },
        "evaluation_context": evaluation_context,
        "human_review": {
            "reviewer": None,
            "started_at": None,
            "completed_at": None,
            "ratified": False,
            "notes": "",
        },
        "assets": packet_assets,
    }
    mapping = {
        "blind_mapping_version": BLIND_PACKET_VERSION,
        "packet_id": packet_id,
        "subtopic_id": subtopic_id,
        "mapping_commitment": commitment,
        "inputs": {
            "agent_path": str(agent_path),
            "agent_sha256": agent_hash,
            "gold_path": str(gold_path),
            "gold_sha256": gold_hash,
            **context_inputs,
        },
        "assignments": assignments,
    }
    return packet, mapping


def _validate_rating(rating: Any, context: str) -> None:
    if not isinstance(rating, dict):
        raise ValueError(f"{context} rating is missing")
    scores = rating.get("scores")
    if not isinstance(scores, dict):
        raise ValueError(f"{context}.scores is missing")
    for dimension in DIMENSIONS:
        score = scores.get(dimension)
        if not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 10:
            raise ValueError(f"{context}.scores.{dimension} must be an integer from 1 to 10")
    minutes = rating.get("review_minutes")
    if not isinstance(minutes, (int, float)) or isinstance(minutes, bool) or minutes < 0:
        raise ValueError(f"{context}.review_minutes must be a non-negative number")
    if rating.get("edit_extent") not in ALLOWED_EDIT_EXTENTS:
        raise ValueError(f"{context}.edit_extent must be one of {sorted(ALLOWED_EDIT_EXTENTS)}")
    if rating.get("ratified") is not True:
        raise ValueError(f"{context}.ratified must be true")


def ratify_scorecard(
    scorecard: dict[str, Any],
    completed_packet: dict[str, Any],
    mapping: dict[str, Any],
) -> dict[str, Any]:
    """Ingest a completed blind review and produce the final pass/fail scorecard."""
    if scorecard.get("scorecard_version") != SCORECARD_VERSION:
        raise ValueError("Unsupported scorecard version")
    if completed_packet.get("packet_id") != mapping.get("packet_id"):
        raise ValueError("Blind packet and mapping packet_id do not match")
    expected_subtopic = scorecard.get("subtopic_id")
    if (
        completed_packet.get("subtopic_id") != expected_subtopic
        or mapping.get("subtopic_id") != expected_subtopic
    ):
        raise ValueError("Scorecard, blind packet, and mapping subtopic_id do not match")
    assignments = mapping.get("assignments")
    if not isinstance(assignments, dict):
        raise ValueError("Blind mapping has no assignments")
    commitment = _sha256_json(assignments)
    if commitment != mapping.get("mapping_commitment") or commitment != completed_packet.get(
        "mapping_commitment"
    ):
        raise ValueError("Blind mapping commitment does not match the packet")
    score_inputs = scorecard.get("inputs", {})
    map_inputs = mapping.get("inputs", {})
    for field in ("agent_sha256", "gold_sha256", "course_model_sha256"):
        if score_inputs.get(field) != map_inputs.get(field):
            raise ValueError(f"Scorecard and blind mapping disagree on {field}")

    review_meta = completed_packet.get("human_review")
    if not isinstance(review_meta, dict) or review_meta.get("ratified") is not True:
        raise ValueError("completed_packet.human_review.ratified must be true")
    if not review_meta.get("reviewer") or not review_meta.get("completed_at"):
        raise ValueError("Completed review must include reviewer and completed_at")

    packet_assets = {
        row.get("asset_type"): row
        for row in completed_packet.get("assets", [])
        if isinstance(row, dict)
    }
    unblinded = []
    reasons = []
    total_agent_minutes = 0.0
    for asset_type in CORE_ASSET_TYPES:
        row = packet_assets.get(asset_type)
        if not isinstance(row, dict):
            raise ValueError(f"Completed review is missing core asset {asset_type}")
        candidates = row.get("candidates")
        assignment = assignments.get(asset_type)
        if not isinstance(candidates, dict) or not isinstance(assignment, dict):
            raise ValueError(f"Completed review/mapping is malformed for {asset_type}")
        for label in ("A", "B"):
            candidate = candidates.get(label)
            if not isinstance(candidate, dict):
                raise ValueError(f"Completed review is missing {asset_type}.{label}")
            _validate_rating(candidate.get("rating"), f"{asset_type}.{label}")
        agent_label = next(
            (label for label in ("A", "B") if assignment.get(label) == "agent"), None
        )
        gold_label = next((label for label in ("A", "B") if assignment.get(label) == "gold"), None)
        if agent_label is None or gold_label is None:
            raise ValueError(f"Blind mapping must assign one agent and one gold for {asset_type}")
        agent_rating = candidates[agent_label]["rating"]
        gold_rating = candidates[gold_label]["rating"]
        total_agent_minutes += float(agent_rating["review_minutes"])
        below = [dimension for dimension, score in agent_rating["scores"].items() if score < 6]
        if below:
            reasons.append(f"{asset_type} is below 6 on: {', '.join(sorted(below))}")
        if agent_rating["edit_extent"] not in {"none", "light"}:
            reasons.append(
                f"{asset_type} edit extent is {agent_rating['edit_extent']!r}, not light-touch"
            )
        unblinded.append(
            {
                "asset_type": asset_type,
                "agent_candidate": agent_label,
                "gold_candidate": gold_label,
                "agent_rating": copy.deepcopy(agent_rating),
                "gold_rating": copy.deepcopy(gold_rating),
                "score_deltas_agent_minus_gold": {
                    dimension: agent_rating["scores"][dimension] - gold_rating["scores"][dimension]
                    for dimension in DIMENSIONS
                },
            }
        )

    if total_agent_minutes > 60:
        reasons.append(f"Core-5 agent review took {total_agent_minutes:g} minutes (>60)")
    passed = not reasons

    final = copy.deepcopy(scorecard)
    by_type = {row["asset_type"]: row for row in final.get("assets", [])}
    for reviewed in unblinded:
        row = by_type.get(reviewed["asset_type"])
        if row is None:
            continue
        for dimension, score in reviewed["agent_rating"]["scores"].items():
            prior = row["dimensions"].get(dimension)
            row["dimensions"][dimension] = {
                "score": score,
                "status": "human_ratified",
                "method": "blind A/B human review",
                "evidence": {
                    "agent_candidate": reviewed["agent_candidate"],
                    "manual_candidate": reviewed["gold_candidate"],
                    "manual_score": reviewed["gold_rating"]["scores"][dimension],
                    "prior_automated_assessment": prior,
                },
            }

    final["human_review"] = {
        "packet_id": completed_packet["packet_id"],
        "reviewer": review_meta["reviewer"],
        "started_at": review_meta.get("started_at"),
        "completed_at": review_meta["completed_at"],
        "ratified": True,
        "notes": review_meta.get("notes", ""),
        "core_agent_review_minutes": total_agent_minutes,
        "assets": unblinded,
    }
    final["human_ratification"] = {
        "status": "ratified",
        "reviewer": review_meta["reviewer"],
        "completed_at": review_meta["completed_at"],
    }
    final["gate"] = {
        "status": "passed" if passed else "failed",
        "passed": passed,
        "core_minimum_score": 6,
        "core_review_minutes_limit": 60,
        "reasons": reasons
        or [
            "All core-5 human scores are >=6, review time is <=60 minutes, "
            "edit extent is light-touch, and the blind review is ratified."
        ],
    }
    final["ratified_at"] = _now()
    return final


def trend_scorecards(scorecards: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for scorecard in scorecards:
        mechanical_scores = []
        for asset in scorecard.get("assets", []):
            if not asset.get("required_for_gate"):
                continue
            for dimension in ("factual_accuracy", "source_attribution", "asset_completeness"):
                score = asset.get("dimensions", {}).get(dimension, {}).get("score")
                if isinstance(score, (int, float)) and not isinstance(score, bool):
                    mechanical_scores.append(float(score))
        rows.append(
            {
                "run_id": scorecard.get("run_id"),
                "timestamp": scorecard.get("timestamp"),
                "prompt_git_sha": scorecard.get("prompt_git_sha"),
                "gate_status": scorecard.get("gate", {}).get("status"),
                "gate_passed": scorecard.get("gate", {}).get("passed", False),
                "core_mechanical_average": (
                    round(sum(mechanical_scores) / len(mechanical_scores), 3)
                    if mechanical_scores
                    else None
                ),
                "core_agent_review_minutes": (scorecard.get("human_review") or {}).get(
                    "core_agent_review_minutes"
                ),
            }
        )
    rows.sort(key=lambda row: (row.get("timestamp") or "", row.get("run_id") or ""))
    return {"trend_version": "1.0", "generated_at": _now(), "runs": rows}


def _default_mapping_path(packet_path: Path) -> Path:
    return packet_path.with_name(f"{packet_path.stem}.mapping.json")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    score = subparsers.add_parser("score", help="Build a provisional scorecard")
    score.add_argument("--agent", type=Path, required=True)
    score.add_argument("--gold", type=Path, required=True)
    score.add_argument("--output", type=Path, required=True)
    score.add_argument("--subtopic-id", default="m1_s1")
    score.add_argument("--llm-judge", action="store_true")
    score.add_argument("--model", default=llm.DEFAULT_MODEL)
    score.add_argument("--course-model", type=Path)

    blind = subparsers.add_parser("blind", help="Create blind packet + hidden mapping")
    blind.add_argument("--agent", type=Path, required=True)
    blind.add_argument("--gold", type=Path, required=True)
    blind.add_argument("--output", type=Path, required=True)
    blind.add_argument("--mapping-output", type=Path)
    blind.add_argument("--subtopic-id", default="m1_s1")
    blind.add_argument("--course-model", type=Path)

    ratify = subparsers.add_parser("ratify", help="Ingest a completed blind human review")
    ratify.add_argument("--scorecard", type=Path, required=True)
    ratify.add_argument("--review", type=Path, required=True)
    ratify.add_argument("--mapping", type=Path, required=True)
    ratify.add_argument("--output", type=Path, required=True)

    trend = subparsers.add_parser("trend", help="Summarize scorecard progression")
    trend.add_argument("scorecards", nargs="+", type=Path)
    trend.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "score":
        result = build_scorecard(
            args.agent,
            args.gold,
            subtopic_id=args.subtopic_id,
            use_llm_judge=args.llm_judge,
            model=args.model,
            course_model_path=args.course_model,
        )
        _write_json(args.output, result)
        print(f"Wrote provisional scorecard: {args.output}")
        return 0
    if args.command == "blind":
        packet, mapping = build_blind_packet(
            args.agent,
            args.gold,
            subtopic_id=args.subtopic_id,
            course_model_path=args.course_model,
        )
        mapping_path = args.mapping_output or _default_mapping_path(args.output)
        _write_json(args.output, packet)
        _write_json(mapping_path, mapping)
        print(f"Wrote blind review packet: {args.output}")
        print(f"Wrote hidden mapping (do not give to reviewer): {mapping_path}")
        return 0
    if args.command == "ratify":
        result = ratify_scorecard(
            _load_json(args.scorecard), _load_json(args.review), _load_json(args.mapping)
        )
        _write_json(args.output, result)
        print(f"Wrote ratified scorecard: {args.output}")
        return 0
    if args.command == "trend":
        result = trend_scorecards(_load_json(path) for path in args.scorecards)
        if args.output:
            _write_json(args.output, result)
            print(f"Wrote scorecard trend: {args.output}")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
