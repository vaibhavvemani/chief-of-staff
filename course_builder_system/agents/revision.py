"""Targeted Student Content revision driven by human or verifier feedback."""

from __future__ import annotations

import json
from collections.abc import Callable
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
    aliases = _asset_aliases(assets)

    if raw_feedback.startswith("{"):
        try:
            payload = json.loads(raw_feedback)
        except json.JSONDecodeError as exc:
            raise ValueError(f"revision feedback JSON is invalid: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("revision feedback JSON must be an object")
        allowed = {"asset", "assets", "feedback", "verifier", "subtopic_id"}
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


def infer_revision_subtopic_id(content_package_body: dict[str, Any], raw_feedback: str) -> str:
    """Infer a single revision subtopic from compact feedback.

    The whole-course path requires revisions to stay targeted. If feedback
    cannot be mapped to exactly one generated subtopic, the caller must pass an
    explicit ``subtopic_id``.
    """
    subtopics = content_package_body.get("subtopics", [])
    if not isinstance(subtopics, list) or not subtopics:
        raise ValueError("content package contains no subtopics to revise")

    if raw_feedback.strip().startswith("{"):
        try:
            payload = json.loads(raw_feedback)
        except json.JSONDecodeError as exc:
            raise ValueError(f"revision feedback JSON is invalid: {exc}") from exc
        subtopic_id = payload.get("subtopic_id") if isinstance(payload, dict) else None
        if isinstance(subtopic_id, str) and subtopic_id:
            _ensure_subtopic_exists(subtopics, subtopic_id)
            return subtopic_id

    selector = raw_feedback.partition(":")[0].strip().lower()
    if selector == "verifier":
        flagged = [
            subtopic["subtopic_id"]
            for subtopic in subtopics
            if _flagged_asset_keys(subtopic.get("assets", []))
        ]
        unique = tuple(dict.fromkeys(flagged))
        if len(unique) == 1:
            return unique[0]
        raise ValueError(
            "verifier revision spans zero or multiple subtopics; pass an explicit subtopic_id"
        )

    selectors = [part.strip().lower() for part in selector.split(",") if part.strip()]
    matches = {
        subtopic["subtopic_id"]
        for subtopic in subtopics
        for asset in subtopic.get("assets", [])
        if str(asset.get("id", "")).lower() in selectors
    }
    if len(matches) == 1:
        return next(iter(matches))
    if len(subtopics) == 1:
        return subtopics[0]["subtopic_id"]
    raise ValueError("revision feedback must identify exactly one subtopic or asset id")


def revise_content_package(
    content_package: dict[str, Any],
    generation_inputs: dict[str, Any],
    course_model: dict[str, Any],
    raw_feedback: str,
    *,
    subtopic_id: str = "m1_s1",
    model: str = llm.DEFAULT_MODEL,
    use_cache: bool = True,
    asset_generator: Callable[..., dict[str, Any]] | None = None,
    asset_verifier: Callable[..., dict[str, Any]] | None = None,
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
    resolved_specs = {
        key: student_content.resolve_asset_spec(spec, generation_inputs)
        for key, spec in student_content.ASSET_SPECS.items()
    }
    cc_id = resolved_specs["course_content"].asset_id
    course_content = by_id.get(cc_id)
    if course_content is None:
        raise ValueError("content package is missing the Course Content anchor")

    for key in ordered_keys:
        spec = resolved_specs[key]
        current = by_id.get(spec.asset_id)
        if current is None:
            raise ValueError(f"content package is missing selected asset {spec.asset_id!r}")
        feedback = _build_asset_feedback(current, request.feedback, request.include_verifier_flags)
        generate_asset = asset_generator or student_content.generate_asset_to_depth
        verify_asset = asset_verifier or verification.verify_asset
        generated = generate_asset(
            spec,
            generation_inputs,
            course_content=course_content if spec.conditioned_on_course_content else None,
            feedback=feedback,
            model=model,
            use_cache=use_cache,
        )
        verified = verify_asset(
            generated,
            course_model,
            model=model,
            use_cache=use_cache,
            source_ids=student_content.routed_source_ids(spec, generation_inputs),
        )
        by_id[spec.asset_id] = verified
        if key == "course_content":
            course_content = verified

    target_subtopic["assets"] = [by_id[asset["id"]] for asset in assets]
    return revised_package


def _asset_aliases(assets: list[dict[str, Any]] | None = None) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for key, spec in student_content.ASSET_SPECS.items():
        for alias in (key, spec.asset_type):
            aliases[alias.lower()] = key
    for asset in assets or []:
        asset_type = asset.get("type")
        asset_id = asset.get("id")
        if asset_type in ASSET_KEYS_BY_TYPE and isinstance(asset_id, str):
            aliases[asset_id.lower()] = ASSET_KEYS_BY_TYPE[asset_type]
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


ASSET_KEYS_BY_TYPE = {spec.asset_type: key for key, spec in student_content.ASSET_SPECS.items()}


def _ensure_subtopic_exists(subtopics: list[dict[str, Any]], subtopic_id: str) -> None:
    if not any(subtopic.get("subtopic_id") == subtopic_id for subtopic in subtopics):
        raise ValueError(f"content package has no subtopic {subtopic_id!r}")


def _flagged_asset_keys(assets: list[dict[str, Any]]) -> tuple[str, ...]:
    aliases = _asset_aliases(assets)
    flagged = []
    for asset in assets:
        claims = asset.get("claims", [])
        summary = asset.get("verification", {})
        has_claim_flags = any(
            claim.get("source_id") is None or claim.get("support") in {"partial", "unsupported"}
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
