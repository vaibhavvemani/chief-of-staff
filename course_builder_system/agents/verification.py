"""Adversarial claim verification for Phase 1 student-content assets.

The verifier is deliberately separate from the writer.  It checks each asset
against the source text registered by the Domain Model, annotates the existing
claims, and surfaces significant factual statements that the writer did not
put in ``claims[]``.  It never rewrites learner-facing content.
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import llm

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = REPO_ROOT / "prompts" / "verification.md"

VERIFICATION_SYSTEM = (
    "You are the Course Builder adversarial fact-checker. You did not write the "
    "asset. Judge every citation only against the supplied source text and return "
    "only schema-valid JSON."
)

SUPPORT_VALUES = {"supported", "partial", "unsupported"}
UNGROUNDED_NOTE = "Ungrounded claim: no source_id was supplied; human review is required."


def verify_asset(
    asset: dict[str, Any],
    domain_model: dict[str, Any],
    *,
    model: str = llm.DEFAULT_MODEL,
    use_cache: bool = True,
    checked_at: str | datetime | None = None,
) -> dict[str, Any]:
    """Verify one asset and return an annotated deep copy.

    One independent LLM call is made for the asset.  Learner-facing ``content``
    and the claim-derived ``sources`` union are preserved byte-for-byte.
    """
    source_registry = _load_registered_sources(domain_model)
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
    domain_model: dict[str, Any],
    *,
    model: str = llm.DEFAULT_MODEL,
    use_cache: bool = True,
    checked_at: str | datetime | None = None,
) -> dict[str, Any]:
    """Verify every asset in a Content Package envelope or body.

    Assets are checked sequentially and independently.  A single UTC timestamp
    is shared by the package so a run is easy to identify and compare.
    The returned object has the same shape (envelope or body) as the input.
    """
    verified_package = deepcopy(content_package)
    body = _content_package_body(verified_package)
    source_registry = _load_registered_sources(domain_model)
    timestamp = _normalise_checked_at(checked_at)

    subtopics = body.get("subtopics")
    if not isinstance(subtopics, list):
        raise ValueError("content package body must contain a subtopics list")

    for subtopic_index, subtopic in enumerate(subtopics):
        if not isinstance(subtopic, dict) or not isinstance(subtopic.get("assets"), list):
            raise ValueError(
                f"content package subtopics[{subtopic_index}] must contain an assets list"
            )
        subtopic["assets"] = [
            _verify_asset_with_sources(
                asset,
                source_registry,
                model=model,
                use_cache=use_cache,
                checked_at=timestamp,
            )
            for asset in subtopic["assets"]
        ]

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

    result = llm.call(
        [{"role": "user", "content": prompt}],
        system=VERIFICATION_SYSTEM,
        model=model,
        max_tokens=8_000,
        schema=_verification_response_schema(),
        use_cache=use_cache,
    )
    response = result.parsed
    if response is None:
        try:
            response = json.loads(result.text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"verifier returned invalid JSON: {exc}") from exc
    if not isinstance(response, dict):
        raise ValueError("verifier response must be a JSON object")

    verdicts, unattributed = _validate_response(
        response,
        claims=claims,
        attributed_ids=attributed_ids,
        source_registry=source_registry,
    )

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
        source_text = source_registry[source_id]["text"]
        if support in {"supported", "partial"}:
            if not isinstance(excerpt, str) or not excerpt.strip():
                raise ValueError(
                    f"claim {claim_id!r} marked {support} must include an evidence excerpt"
                )
            if excerpt not in source_text:
                raise ValueError(
                    f"claim {claim_id!r} evidence excerpt is not an exact substring "
                    f"of source {source_id!r}"
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
                        "support": {"enum": ["supported", "partial", "unsupported"]},
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
    domain_model: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    body = domain_model.get("body", domain_model)
    if not isinstance(body, dict):
        raise ValueError("domain_model must be an artifact envelope or object body")

    sources: dict[str, dict[str, Any]] = {}
    for category in body.get("grounding_sources", []):
        for item in category.get("items", []):
            source_id = item.get("id")
            if not isinstance(source_id, str) or not source_id:
                raise ValueError("encountered a grounding source without an id")
            if source_id in sources:
                raise ValueError(f"duplicate grounding source id {source_id!r}")
            source_file = item.get("file")
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
                "category": category.get("category"),
                "text": source_path.read_text(encoding="utf-8"),
            }
    if not sources:
        raise ValueError("domain_model has no registered grounding sources")
    return sources


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
    parser.add_argument("--domain-model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=llm.DEFAULT_MODEL)
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args(argv)

    package = json.loads(args.package.read_text(encoding="utf-8"))
    domain_model = json.loads(args.domain_model.read_text(encoding="utf-8"))
    verified = verify_content_package(
        package,
        domain_model,
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
