"""Deterministic Markdown course-folder renderer."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def render_course_folder(
    *,
    course_id: str,
    course_model: dict[str, Any],
    blueprint: dict[str, Any],
    content_package: dict[str, Any],
    lesson_plan: dict[str, Any],
    output_root: Path = Path("rendered_courses"),
) -> dict[str, str]:
    """Render course deliverables as Markdown files and return path metadata."""
    course_dir = output_root / course_id
    paths: dict[str, str] = {}
    course_dir.mkdir(parents=True, exist_ok=True)

    paths["index"] = _write(course_dir / "README.md", _index(course_model, content_package))
    paths["course_overview"] = _write(
        course_dir / "course_overview.md",
        _course_overview(course_model, blueprint, content_package),
    )
    paths["source_index"] = _write(
        course_dir / "source_index.md",
        _source_index(course_model),
    )
    paths["lesson_plan"] = _write(
        course_dir / "lesson_plan.md",
        _lesson_plan(lesson_plan),
    )

    asset_paths: dict[str, str] = {}
    subtopic_order = _subtopic_order(course_model)
    for subtopic in _body(content_package).get("subtopics", []):
        subtopic_id = subtopic["subtopic_id"]
        order = subtopic_order.get(subtopic_id, len(subtopic_order) + 1)
        title = _subtopic_title(course_model, subtopic_id)
        subtopic_dir = course_dir / "modules" / f"{order:02d}_{_slug(subtopic_id)}_{_slug(title)}"
        for asset_order, asset in enumerate(subtopic.get("assets", []), start=1):
            path = (
                subtopic_dir / f"{asset_order:02d}_{_slug(asset['id'])}_{_slug(asset['type'])}.md"
            )
            asset_paths[asset["id"]] = _write(path, _asset_markdown(subtopic_id, title, asset))
    paths["assets"] = asset_paths
    return paths


def _write(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    return str(path)


def _index(course_model: dict[str, Any], content_package: dict[str, Any]) -> str:
    metadata = _body(course_model).get("course_metadata", {})
    lines = [
        f"# {metadata.get('course_title', course_model.get('course_id', 'Course'))}",
        "",
        "## Deliverables",
        "",
        "- [Course Overview](course_overview.md)",
        "- [Source Index](source_index.md)",
        "- [Lesson Plan](lesson_plan.md)",
        "",
        "## Generated Assets",
        "",
    ]
    for subtopic in _body(content_package).get("subtopics", []):
        lines.append(
            f"- {subtopic['subtopic_id']}: {len(subtopic.get('assets', []))} Markdown assets"
        )
    return "\n".join(lines)


def _course_overview(
    course_model: dict[str, Any],
    blueprint: dict[str, Any],
    content_package: dict[str, Any],
) -> str:
    body = _body(course_model)
    metadata = body.get("course_metadata", {})
    lines = [
        f"# {metadata.get('course_title', course_model.get('course_id', 'Course'))}",
        "",
        f"- Subject: {metadata.get('subject')}",
        f"- Audience: {metadata.get('audience_summary')}",
        f"- Level: {metadata.get('level')}",
        f"- Language: {metadata.get('language')}",
        "",
        "## Modules",
        "",
    ]
    rendered_subtopics = {
        subtopic["subtopic_id"] for subtopic in _body(content_package).get("subtopics", [])
    }
    planned = {plan["subtopic_id"]: plan for plan in _body(blueprint).get("subtopic_plans", [])}
    for module in body.get("modules", []):
        lines.append(f"### {module.get('title', module.get('id'))}")
        for subtopic in module.get("subtopics", []):
            marker = "generated" if subtopic.get("id") in rendered_subtopics else "not generated"
            selected = [
                asset["asset_type"]
                for asset in planned.get(subtopic.get("id"), {}).get("asset_plan", [])
                if asset.get("selection_status") == "selected"
            ]
            lines.append(
                f"- {subtopic.get('id')}: {subtopic.get('title')} "
                f"({marker}; selected assets: {', '.join(selected)})"
            )
        lines.append("")
    return "\n".join(lines)


def _source_index(course_model: dict[str, Any]) -> str:
    lines = ["# Source Index", ""]
    for source in _body(course_model).get("source_registry", []):
        lines.extend(
            [
                f"## {source.get('id')}: {source.get('title')}",
                "",
                f"- Publisher: {source.get('publisher')}",
                f"- Type: {source.get('source_type')}",
                f"- Locator: {source.get('locator')}",
                f"- Content reference: {source.get('content_ref')}",
                "",
            ]
        )
    return "\n".join(lines)


def _lesson_plan(lesson_plan: dict[str, Any]) -> str:
    lines = ["# Lesson Plan", ""]
    unresolved = _body(lesson_plan).get("unresolved_session_constraints", [])
    if unresolved:
        lines.extend(["## Unresolved Session Constraints", ""])
        lines.extend(f"- {field}" for field in unresolved)
        lines.append("")
    for session in _body(lesson_plan).get("sessions", []):
        lines.extend(
            [
                f"## {session.get('order')}. {session.get('title')}",
                "",
                f"- Duration: {session.get('duration_hours')} hours",
                "",
            ]
        )
        for cover in session.get("covers", []):
            lines.append(f"### {cover.get('subtopic_id')} ({cover.get('mode')})")
            for point in cover.get("talking_points", []):
                lines.append(f"- {point}")
            lines.append("")
    return "\n".join(lines)


def _asset_markdown(subtopic_id: str, subtopic_title: str, asset: dict[str, Any]) -> str:
    lines = [
        f"# {asset.get('title')}",
        "",
        f"- Subtopic: {subtopic_id} - {subtopic_title}",
        f"- Asset type: {asset.get('type')}",
        f"- Planned source format: {asset.get('format')}",
        "- Rendered file: Markdown",
        f"- Status: {asset.get('status')}",
        "",
        "## Content",
        "",
        asset.get("content", ""),
        "",
    ]
    if asset.get("solution"):
        lines.extend(["## Solution", "", asset["solution"], ""])
    if asset.get("claims"):
        lines.extend(["## Claims", ""])
        for claim in asset["claims"]:
            lines.append(
                f"- {claim.get('id')}: {claim.get('text')} "
                f"[source: {claim.get('source_id')}; support: {claim.get('support')}]"
            )
        lines.append("")
    verification = asset.get("verification", {})
    lines.extend(
        [
            "## Verification",
            "",
            f"- Supported: {verification.get('supported', 0)}",
            f"- Partial: {verification.get('partial', 0)}",
            f"- Unsupported: {verification.get('unsupported', 0)}",
            f"- Ungrounded: {verification.get('ungrounded', 0)}",
            "",
        ]
    )
    return "\n".join(lines)


def _subtopic_order(course_model: dict[str, Any]) -> dict[str, int]:
    order: dict[str, int] = {}
    index = 1
    for module in _body(course_model).get("modules", []):
        for subtopic in module.get("subtopics", []):
            order[subtopic["id"]] = index
            index += 1
    return order


def _subtopic_title(course_model: dict[str, Any], subtopic_id: str) -> str:
    for module in _body(course_model).get("modules", []):
        for subtopic in module.get("subtopics", []):
            if subtopic.get("id") == subtopic_id:
                return subtopic.get("title", subtopic_id)
    return subtopic_id


def _body(artifact: dict[str, Any]) -> dict[str, Any]:
    body = artifact.get("body", artifact)
    if not isinstance(body, dict):
        raise ValueError("expected an artifact envelope or body object")
    return body


def _slug(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return text or "item"
