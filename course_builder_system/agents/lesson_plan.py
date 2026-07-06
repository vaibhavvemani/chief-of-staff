"""Domain-neutral Lesson Plan generation for Sprint 3."""

from __future__ import annotations

from typing import Any

from orchestrator import make_artifact

DEFAULT_MAX_SESSION_HOURS = 2.0
VALID_MODES = {"live", "self_study"}


def build_lesson_plan_artifact(
    content_package: dict[str, Any],
    blueprint: dict[str, Any],
    *,
    course_model: dict[str, Any] | None = None,
    session_constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic Lesson Plan from generated whole-course content."""
    course_id = content_package["course_id"]
    body = build_lesson_plan_body(
        content_package,
        blueprint,
        course_model=course_model,
        session_constraints=session_constraints,
    )
    return make_artifact(
        course_id,
        "lesson_plan",
        "lesson_plan",
        body=body,
        inputs=["content_package", "blueprint"]
        + (["course_model"] if course_model is not None else []),
    )


def build_lesson_plan_body(
    content_package: dict[str, Any],
    blueprint: dict[str, Any],
    *,
    course_model: dict[str, Any] | None = None,
    session_constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a validated Lesson Plan body."""
    constraints = _normalise_constraints(session_constraints)
    subtopic_ids = [item["subtopic_id"] for item in _body(content_package).get("subtopics", [])]
    if not subtopic_ids:
        raise ValueError("Lesson Plan requires at least one generated subtopic")

    planned = [
        _subtopic_lesson_item(
            subtopic_id,
            content_package,
            blueprint,
            course_model,
            default_mode=constraints["default_mode"],
        )
        for subtopic_id in subtopic_ids
    ]
    sessions: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    current_minutes = 0
    max_minutes = int(constraints["max_session_hours"] * 60)
    for item in planned:
        minutes = item["duration_minutes"]
        if current and current_minutes + minutes > max_minutes:
            sessions.append(_session(len(sessions) + 1, current))
            current = []
            current_minutes = 0
        current.append(item)
        current_minutes += minutes
    if current:
        sessions.append(_session(len(sessions) + 1, current))

    unresolved = _unresolved_constraints(session_constraints)
    unresolved.extend(
        f"{item['subtopic_id']}:duration_exceeds_max_session_hours"
        for item in planned
        if item["duration_minutes"] > max_minutes
    )
    covered = [item["subtopic_id"] for item in planned]
    body = {
        "session_constraints": constraints,
        "unresolved_session_constraints": unresolved,
        "coverage_summary": {
            "expected_subtopic_ids": list(subtopic_ids),
            "covered_subtopic_ids": covered,
            "total_duration_minutes": sum(item["duration_minutes"] for item in planned),
        },
        "sessions": sessions,
    }
    problems = validate_lesson_plan_body(body, expected_subtopic_ids=subtopic_ids)
    if problems:
        raise ValueError("Invalid Lesson Plan:\n- " + "\n- ".join(problems))
    return body


def validate_lesson_plan_body(
    body: dict[str, Any],
    *,
    expected_subtopic_ids: list[str] | tuple[str, ...],
) -> list[str]:
    """Validate Lesson Plan references and coverage semantics."""
    errors: list[str] = []
    sessions = body.get("sessions")
    if not isinstance(sessions, list) or not sessions:
        return ["Lesson Plan must contain at least one session"]
    covered: list[str] = []
    seen_session_ids: set[str] = set()
    for expected_order, session in enumerate(sessions, start=1):
        session_id = session.get("id")
        if not isinstance(session_id, str) or not session_id:
            errors.append("Lesson Plan session is missing id")
        elif session_id in seen_session_ids:
            errors.append(f"Duplicate Lesson Plan session id {session_id}")
        seen_session_ids.add(session_id)
        if session.get("order") != expected_order:
            errors.append(f"Lesson Plan session {session_id} has non-sequential order")
        duration = session.get("duration_hours")
        if not isinstance(duration, int | float) or duration <= 0:
            errors.append(f"Lesson Plan session {session_id} duration_hours must be positive")
        duration_minutes = session.get("duration_minutes")
        if not isinstance(duration_minutes, int) or duration_minutes <= 0:
            errors.append(f"Lesson Plan session {session_id} duration_minutes must be positive")
        constraints = body.get("session_constraints", {})
        max_hours = constraints.get("max_session_hours")
        if (
            isinstance(max_hours, int | float)
            and isinstance(duration, int | float)
            and duration > max_hours
            and len(session.get("covers", [])) > 1
        ):
            errors.append(f"Lesson Plan session {session_id} exceeds max_session_hours")
        covers = session.get("covers")
        if not isinstance(covers, list) or not covers:
            errors.append(f"Lesson Plan session {session_id} must cover at least one subtopic")
            continue
        for item in covers:
            subtopic_id = item.get("subtopic_id")
            if subtopic_id not in expected_subtopic_ids:
                errors.append(f"Lesson Plan covers unknown subtopic {subtopic_id}")
            else:
                covered.append(subtopic_id)
            if item.get("mode") not in VALID_MODES:
                errors.append(f"Lesson Plan subtopic {subtopic_id} has invalid mode")
            talking_points = item.get("talking_points")
            if not isinstance(talking_points, list) or not all(
                isinstance(point, str) and point.strip() for point in talking_points
            ):
                errors.append(f"Lesson Plan subtopic {subtopic_id} needs talking_points")
    if covered != list(expected_subtopic_ids):
        errors.append(
            "Lesson Plan must cover generated subtopics exactly once in order; "
            f"expected={list(expected_subtopic_ids)}, actual={covered}"
        )
    return errors


def _normalise_constraints(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw or {}
    max_session_hours = raw.get("max_session_hours", DEFAULT_MAX_SESSION_HOURS)
    if not isinstance(max_session_hours, int | float) or max_session_hours <= 0:
        raise ValueError("max_session_hours must be positive")
    default_mode = raw.get("default_mode", "live")
    if default_mode not in VALID_MODES:
        raise ValueError("default_mode must be live or self_study")
    return {
        "max_session_hours": float(max_session_hours),
        "default_mode": default_mode,
    }


def _unresolved_constraints(raw: dict[str, Any] | None) -> list[str]:
    raw = raw or {}
    unresolved = []
    for field in ("calendar_dates", "instructor_count", "delivery_platform"):
        if field not in raw:
            unresolved.append(field)
    return unresolved


def _subtopic_lesson_item(
    subtopic_id: str,
    content_package: dict[str, Any],
    blueprint: dict[str, Any],
    course_model: dict[str, Any] | None,
    *,
    default_mode: str,
) -> dict[str, Any]:
    plan = _blueprint_plan(blueprint, subtopic_id)
    subtopic = _content_subtopic(content_package, subtopic_id)
    title = _subtopic_title(course_model, subtopic_id) or _asset_title(subtopic)
    minutes = plan.get("depth_budget", {}).get("target_learning_minutes", 30)
    if not isinstance(minutes, int) or minutes <= 0:
        minutes = 30
    selected_types = [asset["type"] for asset in subtopic.get("assets", [])]
    mode = (
        "live"
        if {"activities", "case_study", "assessment"} & set(selected_types)
        else default_mode
    )
    return {
        "subtopic_id": subtopic_id,
        "title": title,
        "duration_minutes": minutes,
        "mode": mode,
        "talking_points": _talking_points(title, selected_types),
    }


def _session(order: int, items: list[dict[str, Any]]) -> dict[str, Any]:
    titles = [item["title"] for item in items]
    total_minutes = sum(item["duration_minutes"] for item in items)
    return {
        "id": f"sess{order}",
        "order": order,
        "title": " / ".join(titles)[:120],
        "duration_minutes": total_minutes,
        "duration_hours": round(total_minutes / 60, 2),
        "covers": [
            {
                "subtopic_id": item["subtopic_id"],
                "mode": item["mode"],
                "talking_points": item["talking_points"],
            }
            for item in items
        ],
    }


def _talking_points(title: str, selected_types: list[str]) -> list[str]:
    points = [f"Introduce {title} through the approved Course Content."]
    if "activities" in selected_types:
        points.append("Use the selected activity asset for learner practice.")
    if "case_study" in selected_types:
        points.append("Discuss the selected case study before debriefing concepts.")
    if "assessment" in selected_types:
        points.append("Close with the selected assessment and answer-key review.")
    if len(points) == 1:
        points.append("Use the summary asset for consolidation and self-study follow-up.")
    return points


def _body(artifact: dict[str, Any]) -> dict[str, Any]:
    body = artifact.get("body", artifact)
    if not isinstance(body, dict):
        raise ValueError("expected an artifact envelope or body object")
    return body


def _blueprint_plan(blueprint: dict[str, Any], subtopic_id: str) -> dict[str, Any]:
    for plan in _body(blueprint).get("subtopic_plans", []):
        if plan.get("subtopic_id") == subtopic_id:
            return plan
    return {}


def _content_subtopic(content_package: dict[str, Any], subtopic_id: str) -> dict[str, Any]:
    for subtopic in _body(content_package).get("subtopics", []):
        if subtopic.get("subtopic_id") == subtopic_id:
            return subtopic
    raise ValueError(f"Content Package is missing subtopic {subtopic_id}")


def _subtopic_title(course_model: dict[str, Any] | None, subtopic_id: str) -> str | None:
    if course_model is None:
        return None
    for module in _body(course_model).get("modules", []):
        for subtopic in module.get("subtopics", []):
            if subtopic.get("id") == subtopic_id:
                return subtopic.get("title")
    return None


def _asset_title(subtopic: dict[str, Any]) -> str:
    for asset in subtopic.get("assets", []):
        if asset.get("type") == "course_content":
            return asset.get("title", subtopic["subtopic_id"])
    return subtopic["subtopic_id"]
