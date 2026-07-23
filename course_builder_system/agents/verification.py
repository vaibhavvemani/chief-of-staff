"""Adversarial claim verification for Phase 1 student-content assets.

The verifier is deliberately separate from the writer. It checks each asset
against the source text approved in the Course Model, annotates the existing
claims, and surfaces significant factual statements that the writer did not
put in ``claims[]``.  It never rewrites learner-facing content.
"""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import llm
from source_store import prepare_source_excerpt

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = REPO_ROOT / "prompts" / "verification.md"

VERIFICATION_SYSTEM = (
    "You are the Course Builder adversarial fact-checker. You did not write the "
    "asset. Judge every citation only against the supplied source text and return "
    "only schema-valid JSON."
)

SUPPORT_VALUES = {"supported", "partial", "unsupported"}
UNGROUNDED_NOTE = "Ungrounded claim: no source_id was supplied; human review is required."
_METADATA_CLAIM_GLUE = {
    "a",
    "an",
    "and",
    "approved",
    "article",
    "as",
    "at",
    "available",
    "be",
    "by",
    "called",
    "can",
    "category",
    "classified",
    "found",
    "from",
    "guide",
    "has",
    "is",
    "its",
    "link",
    "located",
    "maintained",
    "named",
    "of",
    "online",
    "page",
    "provided",
    "published",
    "publisher",
    "registered",
    "resource",
    "source",
    "the",
    "this",
    "title",
    "titled",
    "type",
    "url",
    "was",
    "web",
    "website",
}
_METADATA_RELATIONSHIP_WORDS = {
    "Title": {"called", "named", "title", "titled"},
    "Publisher": {"by", "maintained", "provided", "published", "publisher"},
    "Type": {"as", "category", "classified", "type"},
    "URL": {"available", "found", "link", "located", "online", "url", "website"},
}


def verify_asset(
    asset: dict[str, Any],
    course_model: dict[str, Any],
    *,
    model: str = llm.DEFAULT_MODEL,
    use_cache: bool = True,
    checked_at: str | datetime | None = None,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Verify one asset and return an annotated deep copy.

    One independent LLM call is made for the asset.  Learner-facing ``content``
    and the claim-derived ``sources`` union are preserved byte-for-byte.
    """
    source_registry = _load_registered_sources(course_model)
    if source_ids is not None:
        source_registry = _filter_sources(source_registry, source_ids, "asset")
    timestamp = _normalise_checked_at(checked_at)
    return _verify_asset_with_sources(
        asset,
        source_registry,
        model=model,
        use_cache=use_cache,
        checked_at=timestamp,
    )


def verify_content_package(
    content_package: dict[str, Any],
    course_model: dict[str, Any],
    *,
    model: str = llm.DEFAULT_MODEL,
    use_cache: bool = True,
    checked_at: str | datetime | None = None,
    blueprint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify every asset in a Content Package envelope or body.

    Assets are checked sequentially and independently.  A single UTC timestamp
    is shared by the package so a run is easy to identify and compare.
    The returned object has the same shape (envelope or body) as the input.
    """
    verified_package = deepcopy(content_package)
    body = _content_package_body(verified_package)
    source_registry = _load_registered_sources(course_model)
    timestamp = _normalise_checked_at(checked_at)

    subtopics = body.get("subtopics")
    if not isinstance(subtopics, list):
        raise ValueError("content package body must contain a subtopics list")

    for subtopic_index, subtopic in enumerate(subtopics):
        if not isinstance(subtopic, dict) or not isinstance(subtopic.get("assets"), list):
            raise ValueError(
                f"content package subtopics[{subtopic_index}] must contain an assets list"
            )
        subtopic_sources = _sources_for_subtopic(
            course_model,
            subtopic.get("subtopic_id"),
            source_registry,
        )
        verified_assets = []
        for asset in subtopic["assets"]:
            asset_sources = _sources_for_asset(
                blueprint,
                subtopic.get("subtopic_id"),
                asset,
                subtopic_sources,
            )
            verified_assets.append(
                _verify_asset_with_sources(
                    asset,
                    asset_sources,
                    model=model,
                    use_cache=use_cache,
                    checked_at=timestamp,
                )
            )
        subtopic["assets"] = verified_assets

    return verified_package


def _verify_asset_with_sources(
    asset: dict[str, Any],
    source_registry: dict[str, dict[str, Any]],
    *,
    model: str,
    use_cache: bool,
    checked_at: str,
) -> dict[str, Any]:
    claims, attributed_ids = _validate_asset_for_verification(asset, source_registry)
    prompt = _render_prompt(asset, source_registry)
    validation_error: ValueError | None = None
    for attempt in range(2):
        correction = ""
        if validation_error is not None:
            correction = (
                "\n\n## Required Correction\n\n"
                "Your previous verifier response failed deterministic validation:\n"
                f"{validation_error}\n\n"
                "Re-check every verdict against its claim's cited source_id only. "
                "Return a fresh complete response; do not copy evidence from another source."
            )
        result = llm.call(
            [{"role": "user", "content": prompt + correction}],
            system=VERIFICATION_SYSTEM,
            model=model,
            max_tokens=8_000,
            schema=_verification_response_schema(),
            use_cache=use_cache,
            call_role="verification",
        )
        response: dict[str, Any] | None = None
        try:
            response = _parse_verifier_response(result)
            verdicts, unattributed = _validate_response(
                response,
                claims=claims,
                attributed_ids=attributed_ids,
                source_registry=source_registry,
            )
            break
        except ValueError as exc:
            validation_error = exc
            if attempt == 1:
                if response is None:
                    raise
                response = _conservative_verifier_fallback(
                    response,
                    claims=claims,
                    source_registry=source_registry,
                )
                verdicts, unattributed = _validate_response(
                    response,
                    claims=claims,
                    attributed_ids=attributed_ids,
                    source_registry=source_registry,
                )
                break
    else:  # pragma: no cover - loop either breaks or raises
        raise AssertionError("verifier retry loop ended without a result")

    verified = deepcopy(asset)
    for claim in verified["claims"]:
        source_id = claim["source_id"]
        if source_id is None:
            claim["support"] = None
            claim["supporting_excerpt"] = None
            claim["note"] = UNGROUNDED_NOTE
            continue

        verdict = verdicts[claim["id"]]
        claim["support"] = verdict["support"]
        claim["supporting_excerpt"] = verdict["supporting_excerpt"]
        claim["note"] = verdict["note"]

    counts = _verdict_counts(verdicts)
    verified["verification"] = {
        **counts,
        "ungrounded": sum(claim["source_id"] is None for claim in claims),
        "unattributed_found": unattributed,
        "checked_at": checked_at,
    }

    # The verifier annotates evidence only.  Guard the fields the writer owns.
    if verified.get("content") != asset.get("content"):
        raise AssertionError("verification must not modify asset content")
    if verified.get("sources") != asset.get("sources"):
        raise AssertionError("verification must not modify the asset source union")
    return verified


def _parse_verifier_response(result: llm.LLMResult) -> dict[str, Any]:
    response = result.parsed
    if response is None:
        try:
            response = json.loads(result.text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"verifier returned invalid JSON: {exc}") from exc
    if not isinstance(response, dict):
        raise ValueError("verifier response must be a JSON object")
    return response


def _conservative_verifier_fallback(
    response: dict[str, Any],
    *,
    claims: list[dict[str, Any]],
    source_registry: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Conservatively repair verifier-only defects after retry exhaustion.

    This never upgrades a verdict. Unknown/duplicate verdict ids are discarded;
    attributed claims left without a verdict become unsupported. A
    supported/partial claim whose evidence is absent from its cited source also
    becomes unsupported. Unrelated response defects remain and still fail.
    """
    repaired = deepcopy(response)
    claims_by_id = {claim.get("id"): claim for claim in claims}
    verdicts = repaired.get("claim_verdicts")
    if not isinstance(verdicts, list):
        return repaired

    canonical_verdicts: list[dict[str, Any]] = []
    seen: set[str] = set()
    changed = False
    for verdict in verdicts:
        if not isinstance(verdict, dict):
            continue
        claim_id = verdict.get("claim_id")
        claim = claims_by_id.get(claim_id)
        if (
            not isinstance(claim_id, str)
            or not isinstance(claim, dict)
            or claim.get("source_id") is None
            or claim_id in seen
        ):
            changed = True
            continue
        canonical_verdicts.append(verdict)
        seen.add(claim_id)

    for claim in claims:
        claim_id = claim.get("id")
        if claim.get("source_id") is None or claim_id in seen:
            continue
        canonical_verdicts.append(
            {
                "claim_id": claim_id,
                "support": "unsupported",
                "supporting_excerpt": None,
                "note": (
                    "Deterministic fallback: the verifier returned no valid verdict for "
                    "this attributed claim; treated as unsupported."
                ),
            }
        )
        seen.add(claim_id)
        changed = True

    repaired["claim_verdicts"] = canonical_verdicts
    verdicts = canonical_verdicts
    for verdict in verdicts:
        claim = claims_by_id[verdict["claim_id"]]
        source_id = claim.get("source_id")
        source = source_registry.get(source_id)
        if not isinstance(source, dict):
            continue
        excerpt = verdict.get("supporting_excerpt")
        support = verdict.get("support")
        if support in {"supported", "partial"} and (
            not isinstance(excerpt, str)
            or not excerpt.strip()
            or not _evidence_excerpt_is_valid(claim, excerpt, source)
        ):
            verdict["support"] = "unsupported"
            verdict["supporting_excerpt"] = None
            verdict["note"] = (
                "Deterministic fallback: the verifier could not provide an exact excerpt "
                f"from cited source {source_id}; treated as unsupported."
            )
            changed = True
        elif support == "unsupported" and excerpt is not None:
            verdict["supporting_excerpt"] = None
            verdict["note"] = (
                "Deterministic fallback: unsupported verdict retained and invalid evidence "
                "was discarded."
            )
            changed = True

    summary = repaired.get("verification")
    if changed and isinstance(summary, dict):
        for support in ("supported", "partial", "unsupported"):
            summary[support] = sum(
                isinstance(verdict, dict) and verdict.get("support") == support
                for verdict in verdicts
            )
        summary["ungrounded"] = sum(claim.get("source_id") is None for claim in claims)
    return repaired


def _validate_asset_for_verification(
    asset: dict[str, Any],
    source_registry: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[str]]:
    if not isinstance(asset, dict):
        raise ValueError("asset must be a JSON object")
    if not isinstance(asset.get("content"), str):
        raise ValueError("asset content must be a string")

    claims = asset.get("claims")
    if not isinstance(claims, list):
        raise ValueError("asset claims must be a list")

    seen_ids: set[str] = set()
    attributed_ids: set[str] = set()
    claim_sources: list[str] = []
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict):
            raise ValueError(f"claims[{index}] must be an object")
        claim_id = claim.get("id")
        if not isinstance(claim_id, str) or not claim_id.strip():
            raise ValueError(f"claims[{index}] must have a non-empty string id")
        if claim_id in seen_ids:
            raise ValueError(f"duplicate claim id in asset: {claim_id!r}")
        seen_ids.add(claim_id)

        if not isinstance(claim.get("text"), str) or not claim["text"].strip():
            raise ValueError(f"claim {claim_id!r} must have non-empty text")

        source_id = claim.get("source_id")
        if source_id is None:
            continue
        if not isinstance(source_id, str) or source_id not in source_registry:
            raise ValueError(f"claim {claim_id!r} cites unknown source_id {source_id!r}")
        attributed_ids.add(claim_id)
        if source_id not in claim_sources:
            claim_sources.append(source_id)

    asset_sources = asset.get("sources")
    if not isinstance(asset_sources, list) or not all(
        isinstance(source_id, str) for source_id in asset_sources
    ):
        raise ValueError("asset sources must be a list of source-id strings")
    if len(asset_sources) != len(set(asset_sources)):
        raise ValueError("asset sources must not contain duplicates")
    if set(asset_sources) != set(claim_sources):
        raise ValueError(
            "asset sources must equal the non-null claim source_id union before verification"
        )
    return claims, attributed_ids


def _validate_response(
    response: dict[str, Any],
    *,
    claims: list[dict[str, Any]],
    attributed_ids: set[str],
    source_registry: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    expected_top_keys = {"claim_verdicts", "verification"}
    if set(response) != expected_top_keys:
        raise ValueError(
            f"verifier response keys must be {sorted(expected_top_keys)}; got {sorted(response)}"
        )

    raw_verdicts = response["claim_verdicts"]
    if not isinstance(raw_verdicts, list):
        raise ValueError("verifier claim_verdicts must be a list")

    claims_by_id = {claim["id"]: claim for claim in claims}
    verdicts: dict[str, dict[str, Any]] = {}
    expected_verdict_keys = {"claim_id", "support", "supporting_excerpt", "note"}
    for index, verdict in enumerate(raw_verdicts):
        if not isinstance(verdict, dict) or set(verdict) != expected_verdict_keys:
            raise ValueError(
                f"claim_verdicts[{index}] must have exactly {sorted(expected_verdict_keys)}"
            )
        claim_id = verdict["claim_id"]
        if not isinstance(claim_id, str) or claim_id not in claims_by_id:
            raise ValueError(f"verifier returned unknown claim_id {claim_id!r}")
        if claim_id not in attributed_ids:
            raise ValueError(f"verifier returned a verdict for ungrounded claim {claim_id!r}")
        if claim_id in verdicts:
            raise ValueError(f"verifier returned duplicate verdict for claim {claim_id!r}")

        support = verdict["support"]
        if support not in SUPPORT_VALUES:
            raise ValueError(f"claim {claim_id!r} has invalid support verdict {support!r}")
        note = verdict["note"]
        if not isinstance(note, str) or not note.strip():
            raise ValueError(f"claim {claim_id!r} verdict must include a clear note")

        excerpt = verdict["supporting_excerpt"]
        source_id = claims_by_id[claim_id]["source_id"]
        source = source_registry[source_id]
        if support in {"supported", "partial"}:
            if not isinstance(excerpt, str) or not excerpt.strip():
                raise ValueError(
                    f"claim {claim_id!r} marked {support} must include an evidence excerpt"
                )
            if not _evidence_excerpt_is_valid(claims_by_id[claim_id], excerpt, source):
                raise ValueError(
                    f"claim {claim_id!r} evidence excerpt is not an exact substring "
                    f"of allowed evidence from source {source_id!r}"
                )
        elif excerpt is not None:
            raise ValueError(f"claim {claim_id!r} marked unsupported must use a null excerpt")

        verdicts[claim_id] = {
            "support": support,
            "supporting_excerpt": excerpt,
            "note": note,
        }

    actual_ids = set(verdicts)
    if actual_ids != attributed_ids:
        missing = sorted(attributed_ids - actual_ids)
        extra = sorted(actual_ids - attributed_ids)
        raise ValueError(
            "verifier verdicts must cover every attributed claim exactly once; "
            f"missing={missing}, extra={extra}"
        )

    summary = response["verification"]
    expected_summary_keys = {
        "supported",
        "partial",
        "unsupported",
        "ungrounded",
        "unattributed_found",
    }
    if not isinstance(summary, dict) or set(summary) != expected_summary_keys:
        raise ValueError(
            f"verifier verification summary must have exactly {sorted(expected_summary_keys)}"
        )

    expected_counts = _verdict_counts(verdicts)
    expected_counts["ungrounded"] = sum(claim["source_id"] is None for claim in claims)
    for field, expected in expected_counts.items():
        value = summary[field]
        if type(value) is not int or value != expected:
            raise ValueError(f"verifier summary {field}={value!r} does not reconcile to {expected}")

    unattributed = summary["unattributed_found"]
    if not isinstance(unattributed, list) or not all(
        isinstance(item, str) and item.strip() for item in unattributed
    ):
        raise ValueError("unattributed_found must be a list of non-empty claim strings")
    if len(unattributed) != len(set(unattributed)):
        raise ValueError("unattributed_found must not contain duplicates")
    return verdicts, list(unattributed)


def _verdict_counts(verdicts: dict[str, dict[str, Any]]) -> dict[str, int]:
    return {
        support: sum(verdict["support"] == support for verdict in verdicts.values())
        for support in ("supported", "partial", "unsupported")
    }


def _render_prompt(
    asset: dict[str, Any],
    source_registry: dict[str, dict[str, Any]],
) -> str:
    template = PROMPT_PATH.read_text(encoding="utf-8")
    asset_payload = {
        "id": asset.get("id"),
        "type": asset.get("type"),
        "title": asset.get("title"),
        "content": asset.get("content"),
        "claims": [
            {
                "id": claim.get("id"),
                "text": claim.get("text"),
                "source_id": claim.get("source_id"),
            }
            for claim in asset.get("claims", [])
        ],
    }
    if "solution" in asset:
        asset_payload["solution"] = asset["solution"]

    source_blocks = []
    for source_id, source in source_registry.items():
        source_blocks.append(
            "\n".join(
                [
                    f"### Source {source_id}: {source.get('name', '')}",
                    "<SOURCE_METADATA>",
                    _source_metadata(source),
                    "</SOURCE_METADATA>",
                    "<SOURCE_TEXT>",
                    source["text"],
                    "</SOURCE_TEXT>",
                ]
            )
        )

    return template.replace(
        "{{ASSET_JSON}}",
        json.dumps(asset_payload, ensure_ascii=False, indent=2),
    ).replace("{{SOURCE_TEXTS}}", "\n\n".join(source_blocks))


def _source_metadata(source: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"Title: {source.get('name', '')}",
            f"Publisher: {source.get('publisher', '')}",
            f"Type: {source.get('category', '')}",
            f"URL: {source.get('url', '')}",
        ]
    )


def _evidence_excerpt_is_valid(
    claim: dict[str, Any],
    excerpt: str,
    source: dict[str, Any],
) -> bool:
    if excerpt in source["text"]:
        return True
    return _metadata_excerpt_is_valid(claim, excerpt, source)


def _metadata_excerpt_is_valid(
    claim: dict[str, Any],
    excerpt: str,
    source: dict[str, Any],
) -> bool:
    """Allow metadata evidence only for a narrowly metadata-only claim.

    Prompt guidance is not a trust boundary. The deterministic validator therefore
    requires the claimed metadata value to appear verbatim in the claim and rejects
    any remaining vocabulary outside a small metadata relationship vocabulary.
    Substantive words cannot be justified merely because an excerpt appears beside
    the source title, publisher, type, or URL in the verifier prompt.
    """
    fields = (
        ("Title", source.get("name")),
        ("Publisher", source.get("publisher")),
        ("Type", source.get("category")),
        ("URL", source.get("url")),
    )
    matching_fields = [
        (label, value.strip())
        for label, value in fields
        if isinstance(value, str)
        and value.strip()
        and excerpt in f"{label}: {value}"
    ]
    if not matching_fields:
        return False

    claim_text = claim.get("text")
    if not isinstance(claim_text, str):
        return False
    folded_claim = claim_text.casefold()
    if not any(value.casefold() in folded_claim for _label, value in matching_fields):
        return False

    residual = folded_claim
    metadata_values = sorted(
        {
            value.strip().casefold()
            for _label, value in fields
            if isinstance(value, str) and value.strip()
        },
        key=len,
        reverse=True,
    )
    for value in metadata_values:
        residual = residual.replace(value, " ")
    remaining_words = set(re.findall(r"[a-z0-9]+", residual))
    if not remaining_words <= _METADATA_CLAIM_GLUE:
        return False
    return any(
        remaining_words & _METADATA_RELATIONSHIP_WORDS[label]
        for label, _value in matching_fields
    )


def _verification_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["claim_verdicts", "verification"],
        "properties": {
            "claim_verdicts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "claim_id",
                        "support",
                        "supporting_excerpt",
                        "note",
                    ],
                    "properties": {
                        "claim_id": {"type": "string"},
                        "support": {
                            "type": "string",
                            "enum": ["supported", "partial", "unsupported"],
                        },
                        "supporting_excerpt": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                        "note": {"type": "string"},
                    },
                },
            },
            "verification": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "supported",
                    "partial",
                    "unsupported",
                    "ungrounded",
                    "unattributed_found",
                ],
                "properties": {
                    "supported": {"type": "integer"},
                    "partial": {"type": "integer"},
                    "unsupported": {"type": "integer"},
                    "ungrounded": {"type": "integer"},
                    "unattributed_found": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
    }


def _load_registered_sources(
    course_model: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    body = course_model.get("body", course_model)
    if not isinstance(body, dict):
        raise ValueError("course_model must be an artifact envelope or object body")

    sources: dict[str, dict[str, Any]] = {}
    categories = body.get("grounding_sources", [])
    if not categories and isinstance(body.get("source_registry"), list):
        categories = [{"category": "APPROVED", "items": body["source_registry"]}]
    for category in categories:
        for item in category.get("items", []):
            source_id = item.get("id")
            if not isinstance(source_id, str) or not source_id:
                raise ValueError("encountered a grounding source without an id")
            if source_id in sources:
                raise ValueError(f"duplicate grounding source id {source_id!r}")
            source_file = item.get("file", item.get("content_ref"))
            if not isinstance(source_file, str) or not source_file:
                raise ValueError(f"grounding source {source_id!r} is missing file")
            source_path = Path(source_file)
            if not source_path.is_absolute():
                source_path = REPO_ROOT / source_path
            if not source_path.exists():
                raise FileNotFoundError(
                    f"grounding source {source_id!r} file not found: {source_path}"
                )
            sources[source_id] = {
                **item,
                "name": item.get("name", item.get("title", source_id)),
                "category": category.get("category") or item.get("source_type"),
                "url": item.get("url", item.get("locator")),
                "file": source_file,
                "text": prepare_source_excerpt(source_path.read_text(encoding="utf-8")),
            }
    if not sources:
        raise ValueError("course_model has no registered grounding sources")
    return sources


def _sources_for_subtopic(
    course_model: dict[str, Any],
    subtopic_id: Any,
    source_registry: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Deterministically select the human-approved source pack for a node."""
    body = course_model.get("body", course_model)
    approved = None
    for module in body.get("modules", []):
        for subtopic in module.get("subtopics", []):
            if subtopic.get("id") == subtopic_id:
                approved = subtopic.get("approved_source_ids")
                break
    if approved is None:  # legacy fixture compatibility
        return source_registry
    if not isinstance(approved, list) or not all(isinstance(item, str) for item in approved):
        raise ValueError("Course Model approved_source_ids must be a string list")
    unknown = sorted(set(approved) - set(source_registry))
    if unknown:
        raise ValueError("Course Model approves unknown sources: " + ", ".join(unknown))
    return {source_id: source_registry[source_id] for source_id in approved}


def _filter_sources(
    source_registry: dict[str, dict[str, Any]],
    source_ids: list[str],
    label: str,
) -> dict[str, dict[str, Any]]:
    if not isinstance(source_ids, list) or not all(isinstance(item, str) for item in source_ids):
        raise ValueError(f"{label} source_ids must be a string list")
    unknown = sorted(set(source_ids) - set(source_registry))
    if unknown:
        raise ValueError(f"{label} routes unknown sources: " + ", ".join(unknown))
    return {source_id: source_registry[source_id] for source_id in source_ids}


def _sources_for_asset(
    blueprint: dict[str, Any] | None,
    subtopic_id: Any,
    asset: dict[str, Any],
    subtopic_sources: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Narrow an approved subtopic pack to the Blueprint's asset assignment."""
    if blueprint is None:
        return subtopic_sources
    body = blueprint.get("body", blueprint)
    for plan in body.get("subtopic_plans", []):
        if plan.get("subtopic_id") != subtopic_id:
            continue
        for configured in plan.get("asset_plan", []):
            if configured.get("id") == asset.get("id") or configured.get(
                "asset_type"
            ) == asset.get("type"):
                return _filter_sources(
                    subtopic_sources,
                    configured.get("source_ids", list(subtopic_sources)),
                    f"Blueprint asset {asset.get('id')}",
                )
        raise ValueError(f"Blueprint has no asset plan for {asset.get('id')!r}")
    raise ValueError(f"Blueprint has no subtopic plan for {subtopic_id!r}")


def _content_package_body(content_package: dict[str, Any]) -> dict[str, Any]:
    body = content_package.get("body", content_package)
    if not isinstance(body, dict):
        raise ValueError("content package must be an artifact envelope or object body")
    return body


def _normalise_checked_at(value: str | datetime | None) -> str:
    if value is None:
        return datetime.now(UTC).isoformat(timespec="seconds")
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("checked_at datetime must be timezone-aware")
        return value.astimezone(UTC).isoformat(timespec="seconds")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("checked_at must be an ISO-8601 UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("checked_at must be an ISO-8601 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError("checked_at must use UTC")
    return parsed.astimezone(UTC).isoformat(timespec="seconds")


def main(argv: list[str] | None = None) -> int:
    """Verify a saved v0.2 package and write a separate annotated artifact."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument(
        "--course-model",
        "--domain-model",
        dest="course_model",
        type=Path,
        required=True,
        help="Approved combined Course Model (legacy --domain-model alias supported).",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=llm.DEFAULT_MODEL)
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args(argv)

    package = json.loads(args.package.read_text(encoding="utf-8"))
    course_model = json.loads(args.course_model.read_text(encoding="utf-8"))
    verified = verify_content_package(
        package,
        course_model,
        model=args.model,
        use_cache=not args.no_cache,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(verified, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote verified Content Package to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
