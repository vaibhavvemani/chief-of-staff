"""Targeted Student Content revision driven by human or verifier feedback."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import llm
from agents import student_content, verification


@dataclass(frozen=True)
class RevisionRequest:
    """Normalized asset selection and optional human direction."""

    asset_keys: tuple[str, ...]
    feedback: str | None
    include_verifier_flags: bool


def parse_revision_request(
    raw_feedback: str,
    assets: list[dict[str, Any]],
) -> RevisionRequest:
    """Parse JSON or compact console syntax into a targeted request.

    Accepted forms are ``course_content: make the example deeper``,
    ``verifier`` / ``verifier: extra direction``, or a JSON object such as
    ``{"assets": ["m1_s1_cc"], "feedback": "...", "verifier": true}``.
    """
    if not isinstance(raw_feedback, str) or not raw_feedback.strip():
        raise ValueError("revision feedback must be a non-empty string")
    raw_feedback = raw_feedback.strip()
    aliases = _asset_aliases()

    if raw_feedback.startswith("{"):
        try:
            payload = json.loads(raw_feedback)
        except json.JSONDecodeError as exc:
            raise ValueError(f"revision feedback JSON is invalid: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("revision feedback JSON must be an object")
        allowed = {"asset", "assets", "feedback", "verifier"}
        unknown = sorted(set(payload) - allowed)
        if unknown:
            raise ValueError(f"unknown revision feedback fields: {', '.join(unknown)}")
        selectors = payload.get("assets", payload.get("asset"))
        include_flags = payload.get("verifier", False)
        if type(include_flags) is not bool:
            raise ValueError("revision feedback field 'verifier' must be boolean")
        human_feedback = payload.get("feedback")
        if human_feedback is not None and (
            not isinstance(human_feedback, str) or not human_feedback.strip()
        ):
            raise ValueError("revision feedback field 'feedback' must be a non-empty string")
        keys = _resolve_selectors(selectors, aliases) if selectors is not None else ()
        if include_flags:
            keys = _ordered_union(keys, _flagged_asset_keys(assets))
        if not keys:
            raise ValueError("revision request selected no assets")
        return RevisionRequest(
            keys,
            human_feedback.strip() if human_feedback else None,
            include_flags,
        )

    selector, separator, instruction = raw_feedback.partition(":")
    if selector.strip().lower() == "verifier":
        keys = _flagged_asset_keys(assets)
        if not keys:
            raise ValueError("no assets contain verifier flags requiring revision")
        return RevisionRequest(keys, instruction.strip() or None, True)

    if separator:
        keys = _resolve_selectors(
            [part.strip() for part in selector.split(",") if part.strip()],
            aliases,
        )
        if keys:
            if not instruction.strip():
                raise ValueError("targeted revision instruction cannot be empty")
            return RevisionRequest(keys, instruction.strip(), False)

    raise ValueError(
        "target the revision as '<asset id or type>: <feedback>', use 'verifier', "
        "or pass a JSON object with assets/feedback/verifier fields"
    )


def revise_content_package(
    content_package: dict[str, Any],
    generation_inputs: dict[str, Any],
    domain_model: dict[str, Any],
    raw_feedback: str,
    *,
    subtopic_id: str = "m1_s1",
    model: str = llm.DEFAULT_MODEL,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Regenerate and reverify only the assets selected by *raw_feedback*."""
    revised_package = deepcopy(content_package)
    body = revised_package.get("body", revised_package)
    if not isinstance(body, dict):
        raise ValueError("content package must be an envelope or object body")

    target_subtopic = next(
        (
            item
            for item in body.get("subtopics", [])
            if isinstance(item, dict) and item.get("subtopic_id") == subtopic_id
        ),
        None,
    )
    if target_subtopic is None or not isinstance(target_subtopic.get("assets"), list):
        raise ValueError(f"content package has no assets for subtopic {subtopic_id!r}")

    assets = target_subtopic["assets"]
    request = parse_revision_request(raw_feedback, assets)
    by_id = {asset.get("id"): asset for asset in assets}
    if len(by_id) != len(assets):
        raise ValueError("content package contains duplicate or missing asset ids")

    # Revise the anchor first so any other selected assets condition on the new
    # Course Content. Unselected assets remain byte-for-byte unchanged.
    ordered_keys = sorted(
        request.asset_keys,
        key=lambda key: key != "course_content",
    )
    cc_id = student_content.COURSE_CONTENT_SPEC.asset_id
    course_content = by_id.get(cc_id)
    if course_content is None:
        raise ValueError("content package is missing the Course Content anchor")

    for key in ordered_keys:
        spec = student_content.ASSET_SPECS[key]
        current = by_id.get(spec.asset_id)
        if current is None:
            raise ValueError(f"content package is missing selected asset {spec.asset_id!r}")
        feedback = _build_asset_feedback(current, request.feedback, request.include_verifier_flags)
        generated = student_content.generate_asset(
            spec,
            generation_inputs,
            course_content=course_content if spec.conditioned_on_course_content else None,
            feedback=feedback,
            model=model,
            use_cache=use_cache,
        )
        verified = verification.verify_asset(
            generated,
            domain_model,
            model=model,
            use_cache=use_cache,
        )
        by_id[spec.asset_id] = verified
        if key == "course_content":
            course_content = verified

    target_subtopic["assets"] = [by_id[asset["id"]] for asset in assets]
    return revised_package


def _asset_aliases() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for key, spec in student_content.ASSET_SPECS.items():
        for alias in (key, spec.asset_type, spec.asset_id):
            aliases[alias.lower()] = key
    return aliases


def _resolve_selectors(selectors: Any, aliases: dict[str, str]) -> tuple[str, ...]:
    if isinstance(selectors, str):
        selectors = [selectors]
    if not isinstance(selectors, list) or not all(isinstance(item, str) for item in selectors):
        raise ValueError("revision assets must be a string or list of strings")
    keys: tuple[str, ...] = ()
    for selector in selectors:
        key = aliases.get(selector.strip().lower())
        if key is None:
            raise ValueError(f"unknown revision asset selector {selector!r}")
        keys = _ordered_union(keys, (key,))
    return keys


def _ordered_union(left: tuple[str, ...], right: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*left, *right)))


def _flagged_asset_keys(assets: list[dict[str, Any]]) -> tuple[str, ...]:
    aliases = _asset_aliases()
    flagged = []
    for asset in assets:
        claims = asset.get("claims", [])
        summary = asset.get("verification", {})
        has_claim_flags = any(
            claim.get("source_id") is None
            or claim.get("support") in {"partial", "unsupported"}
            for claim in claims
            if isinstance(claim, dict)
        )
        if has_claim_flags or summary.get("unattributed_found"):
            key = aliases.get(str(asset.get("id", "")).lower())
            if key is not None:
                flagged.append(key)
    return tuple(flagged)


def _build_asset_feedback(
    asset: dict[str, Any],
    human_feedback: str | None,
    include_verifier_flags: bool,
) -> str:
    sections = []
    if human_feedback:
        sections.append(f"Human direction:\n{human_feedback}")
    if include_verifier_flags:
        issues = []
        for claim in asset.get("claims", []):
            source_id = claim.get("source_id")
            support = claim.get("support")
            if source_id is not None and support not in {"partial", "unsupported"}:
                continue
            if source_id is None or support in {"partial", "unsupported"}:
                issues.append(
                    f"- {claim.get('id')}: {claim.get('text')} "
                    f"[verdict={support or 'ungrounded'}; note={claim.get('note')}]"
                )
        for claim_text in asset.get("verification", {}).get("unattributed_found", []):
            issues.append(f"- unattributed factual claim: {claim_text}")
        sections.append(
            "Verifier findings to resolve:\n"
            + "\n".join(issues[:30])
            + "\nRewrite, narrow, remove, or correctly attribute each finding "
            "using only the supplied sources."
        )
    return "\n\n".join(sections)
