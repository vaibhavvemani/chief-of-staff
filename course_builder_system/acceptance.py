"""Sprint 4 local acceptance helpers.

These helpers are deliberately domain-neutral and deterministic. They let the
prototype exercise the complete orchestration, source-routing, content-package,
verification, Lesson Plan, renderer, resume, and revision path without relying
on external network or model credentials during acceptance tests.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from agents import student_content


def deterministic_generate_asset(
    spec: student_content.AssetSpec,
    inputs: dict[str, Any],
    course_content: dict[str, Any] | None = None,
    feedback: str | None = None,
    model: str = "local-acceptance",
    use_cache: bool = True,
) -> dict[str, Any]:
    """Generate a small grounded asset for local acceptance runs.

    The function intentionally goes through the same Blueprint asset resolution
    and source-routing guards as live generation. It is not a quality substitute
    for LLM-authored course material; it is a deterministic acceptance driver.
    """
    resolved = student_content.resolve_asset_spec(spec, inputs)
    source_ids = student_content.routed_source_ids(resolved, inputs)
    if not source_ids:
        raise ValueError(f"selected asset {resolved.asset_type!r} has no routed sources")

    subtopic_id = inputs["subtopic_id"]
    subtopic_title = _subtopic_title(inputs["course_model"], subtopic_id)
    source_id = source_ids[0]
    source_title = _source_title(inputs["course_model"], source_id)
    course_title = _course_title(inputs["course_model"])

    paragraphs = [
        f"# {resolved.title}",
        (
            f"This {resolved.asset_type.replace('_', ' ')} supports {subtopic_title} "
            f"inside {course_title}."
        ),
        (
            f"It is grounded in approved source {source_id} ({source_title}) and "
            "uses only sources routed through the approved Blueprint asset plan."
        ),
        (
            "Learners should connect the approved concepts to a practical decision, "
            "then check that decision against the stated source evidence."
        ),
    ]
    if resolved.conditioned_on_course_content and course_content is not None:
        paragraphs.append(f"This asset is conditioned on anchor asset {course_content['id']}.")
    if feedback:
        paragraphs.append(f"Revision applied: {feedback}")

    asset = {
        "id": resolved.asset_id,
        "type": resolved.asset_type,
        "title": resolved.title,
        "format": resolved.format,
        "content": "\n\n".join(paragraphs),
        "claims": [
            {
                "id": f"{resolved.asset_id}_c1",
                "text": f"{resolved.title} is grounded in approved source {source_id}.",
                "source_id": source_id,
                "support": None,
                "supporting_excerpt": None,
                "note": None,
            }
        ],
        "sources": [source_id],
        "verification": deepcopy(student_content.EMPTY_VERIFICATION),
        "file": None,
        "status": "done",
    }
    if resolved.has_solution:
        asset["solution"] = (
            "Acceptance answer key: compare the learner response to the approved "
            "source evidence."
        )
    return asset


def deterministic_verify_content_package(
    content_package: dict[str, Any],
    course_model: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    """Annotate every generated claim as supported for local acceptance."""
    verified = deepcopy(content_package)
    body = verified.get("body", verified)
    for subtopic in body.get("subtopics", []):
        for index, asset in enumerate(subtopic.get("assets", [])):
            subtopic["assets"][index] = deterministic_verify_asset(asset, course_model, **kwargs)
    return verified


def deterministic_verify_asset(
    asset: dict[str, Any],
    course_model: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    """Annotate one asset as deterministically verified."""
    verified = deepcopy(asset)
    for claim in verified.get("claims", []):
        if claim.get("source_id") is None:
            claim["support"] = None
            claim["supporting_excerpt"] = None
            claim["note"] = "Acceptance verifier: ungrounded claim retained for review."
            continue
        claim["support"] = "supported"
        claim["supporting_excerpt"] = "Deterministic acceptance evidence."
        claim["note"] = "Supported by the local acceptance verifier."
    verified["verification"] = {
        "supported": sum(
            claim.get("support") == "supported" for claim in verified.get("claims", [])
        ),
        "partial": 0,
        "unsupported": 0,
        "ungrounded": sum(
            claim.get("source_id") is None for claim in verified.get("claims", [])
        ),
        "unattributed_found": [],
        "checked_at": "2026-07-06T00:00:00+00:00",
    }
    return verified


def _course_title(course_model: dict[str, Any]) -> str:
    body = _body(course_model)
    return body.get("course_metadata", {}).get("course_title") or course_model.get(
        "course_id",
        "Course",
    )


def _subtopic_title(course_model: dict[str, Any], subtopic_id: str) -> str:
    for module in _body(course_model).get("modules", []):
        for subtopic in module.get("subtopics", []):
            if subtopic.get("id") == subtopic_id:
                return subtopic.get("title", subtopic_id)
    return subtopic_id


def _source_title(course_model: dict[str, Any], source_id: str) -> str:
    for source in _body(course_model).get("source_registry", []):
        if source.get("id") == source_id:
            return source.get("title", source_id)
    return source_id


def _body(artifact: dict[str, Any]) -> dict[str, Any]:
    body = artifact.get("body", artifact)
    if not isinstance(body, dict):
        raise ValueError("expected an artifact envelope or body object")
    return body
