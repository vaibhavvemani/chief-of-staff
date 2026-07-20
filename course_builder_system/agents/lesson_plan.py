"""Domain-neutral Lesson Plan generation for Sprint 3."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from orchestrator import make_artifact

DEFAULT_MAX_SESSION_HOURS = 2.0
VALID_MODES = {"live", "self_study"}
LESSON_PLAN_OPERATIONS = {"set_mode", "move_segment", "reorder_session"}


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
    expected = list(expected_subtopic_ids)
    if len(covered) != len(set(covered)) or set(covered) != set(expected):
        errors.append(
            "Lesson Plan must cover generated subtopics exactly once; "
            f"expected={expected}, actual={covered}"
        )
    elif covered != expected and body.get("sequence_policy") != "operator_defined":
        errors.append(
            "Lesson Plan subtopic order differs from the Course Model without an "
            "approved typed sequence operation"
        )
    coverage = body.get("coverage_summary")
    if not isinstance(coverage, dict):
        errors.append("Lesson Plan coverage_summary must be an object")
    else:
        if coverage.get("expected_subtopic_ids") != expected:
            errors.append("Lesson Plan expected_subtopic_ids do not match generated content")
        if coverage.get("covered_subtopic_ids") != covered:
            errors.append("Lesson Plan covered_subtopic_ids do not match session coverage")
        total = sum(
            session.get("duration_minutes", 0)
            for session in sessions
            if isinstance(session.get("duration_minutes"), int)
        )
        if coverage.get("total_duration_minutes") != total:
            errors.append("Lesson Plan total duration does not match its sessions")
    return errors


def course_model_subtopic_ids(course_model: dict[str, Any]) -> list[str]:
    """Return the Course Model's authoritative ordered subtopic IDs."""
    return [
        str(subtopic["id"])
        for module in _body(course_model).get("modules", [])
        if isinstance(module, dict)
        for subtopic in module.get("subtopics", [])
        if isinstance(subtopic, dict) and subtopic.get("id")
    ]


def validate_lesson_plan_inputs(
    *,
    course_model: dict[str, Any],
    blueprint: dict[str, Any],
    content_package: dict[str, Any],
) -> list[str]:
    """Reconcile Lesson Plan inputs against the Course Model authority boundary."""
    errors: list[str] = []
    expected = course_model_subtopic_ids(course_model)
    if not expected:
        errors.append("Course Model must contain at least one subtopic")
    if len(expected) != len(set(expected)):
        errors.append("Course Model contains duplicate subtopic IDs")
    candidates = {
        "Blueprint": [
            str(item["subtopic_id"])
            for item in _body(blueprint).get("subtopic_plans", [])
            if isinstance(item, dict) and item.get("subtopic_id")
        ],
        "Content Package": [
            str(item["subtopic_id"])
            for item in _body(content_package).get("subtopics", [])
            if isinstance(item, dict) and item.get("subtopic_id")
        ],
    }
    for label, actual in candidates.items():
        if len(actual) != len(set(actual)):
            errors.append(f"{label} contains duplicate subtopic IDs")
        if actual != expected:
            errors.append(
                f"{label} subtopics do not exactly match Course Model order; "
                f"expected={expected}, actual={actual}"
            )
    return errors


def apply_lesson_plan_decision(
    lesson_plan: dict[str, Any],
    *,
    constraints: dict[str, Any] | None,
    operations: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    content_package: dict[str, Any],
    blueprint: dict[str, Any],
    course_model: dict[str, Any],
    rationale: str = "Human Lesson Plan checkpoint.",
) -> dict[str, Any]:
    """Reduce one typed delivery decision while preserving untouched sessions."""
    rationale = str(rationale).strip()
    if not rationale:
        raise ValueError("Lesson Plan decision rationale cannot be blank")
    if len(rationale) > 500:
        raise ValueError("Lesson Plan decision rationale cannot exceed 500 characters")
    if constraints is None and not operations:
        raise ValueError("Lesson Plan decision must change constraints or sessions")

    decided = deepcopy(lesson_plan)
    body = decided.get("body")
    if not isinstance(body, dict):
        raise ValueError("Lesson Plan artifact body must be an object")
    input_errors = validate_lesson_plan_inputs(
        course_model=course_model,
        blueprint=blueprint,
        content_package=content_package,
    )
    if input_errors:
        raise ValueError("Lesson Plan inputs are inconsistent:\n- " + "\n- ".join(input_errors))
    expected_ids = course_model_subtopic_ids(course_model)
    existing_errors = validate_lesson_plan_body(body, expected_subtopic_ids=expected_ids)
    if existing_errors:
        raise ValueError("Current Lesson Plan is invalid:\n- " + "\n- ".join(existing_errors))

    planned = {
        subtopic_id: _subtopic_lesson_item(
            subtopic_id,
            content_package,
            blueprint,
            course_model,
            default_mode=body.get("session_constraints", {}).get(
                "default_mode",
                "live",
            ),
        )
        for subtopic_id in expected_ids
    }
    original_contract = _lesson_plan_contract(body)
    original_sessions = {
        str(session.get("id")): deepcopy(session)
        for session in body["sessions"]
        if isinstance(session, dict) and session.get("id")
    }
    session_id_cursor = _session_id_cursor(body)
    existing_constraints = dict(body.get("session_constraints", {}))
    merged_constraints = _normalise_constraints({**existing_constraints, **(constraints or {})})
    changed_constraint_fields = sorted(
        field
        for field in (constraints or {})
        if merged_constraints.get(field) != existing_constraints.get(field)
    )
    body["session_constraints"] = merged_constraints
    sessions = body["sessions"]

    if "max_session_hours" in changed_constraint_fields:
        sessions, session_id_cursor = _regroup_sessions(
            sessions,
            planned,
            max_minutes=int(merged_constraints["max_session_hours"] * 60),
            session_id_cursor=session_id_cursor,
        )
    if "default_mode" in changed_constraint_fields:
        for session in sessions:
            for cover in session["covers"]:
                cover["mode"] = merged_constraints["default_mode"]

    seen_operation_targets: set[tuple[str, str]] = set()
    for operation in operations:
        op = operation.get("op")
        if op not in LESSON_PLAN_OPERATIONS:
            raise ValueError(f"unknown Lesson Plan operation: {op!r}")
        if op == "set_mode":
            target_id = str(operation.get("target_id", ""))
            _reject_duplicate_lesson_operation(seen_operation_targets, op, target_id)
            _, cover = _find_cover(sessions, target_id)
            value = operation.get("value")
            if value not in VALID_MODES:
                raise ValueError("Lesson Plan mode must be live or self_study")
            if cover["mode"] == value:
                raise ValueError(f"Lesson Plan mode for {target_id} is unchanged")
            cover["mode"] = value
        elif op == "move_segment":
            target_id = str(operation.get("target_id", ""))
            _reject_duplicate_lesson_operation(seen_operation_targets, op, target_id)
            source, cover = _find_cover(sessions, target_id)
            target_session_id = str(operation.get("value", ""))
            target = _find_session(sessions, target_session_id)
            position = operation.get("position")
            if not isinstance(position, int) or isinstance(position, bool) or position < 1:
                raise ValueError("Lesson Plan segment position must be a positive integer")
            current_index = source["covers"].index(cover)
            if source is target and current_index == position - 1:
                raise ValueError(f"Lesson Plan segment {target_id} is already at that position")
            source["covers"].remove(cover)
            target_index = min(position - 1, len(target["covers"]))
            target["covers"].insert(target_index, cover)
            if not source["covers"]:
                sessions.remove(source)
        else:
            session_ids = operation.get("session_ids")
            if not isinstance(session_ids, list) or not session_ids:
                raise ValueError("Lesson Plan session order must be a nonempty list")
            if len(session_ids) != len(set(session_ids)):
                raise ValueError("Lesson Plan session order contains duplicates")
            current_ids = [session["id"] for session in sessions]
            if set(session_ids) != set(current_ids) or len(session_ids) != len(current_ids):
                raise ValueError(
                    "Lesson Plan session order must include every session exactly once"
                )
            if session_ids == current_ids:
                raise ValueError("Lesson Plan session order is unchanged")
            by_id = {session["id"]: session for session in sessions}
            sessions = [by_id[session_id] for session_id in session_ids]
            body["sequence_policy"] = "operator_defined"

    if any(operation.get("op") == "move_segment" for operation in operations):
        body["sequence_policy"] = "operator_defined"
    _refresh_sessions(sessions, planned)
    max_minutes = int(merged_constraints["max_session_hours"] * 60)
    oversized = [session["id"] for session in sessions if session["duration_minutes"] > max_minutes]
    if oversized:
        raise ValueError("Lesson Plan sessions exceed max_session_hours: " + ", ".join(oversized))
    covered = [cover["subtopic_id"] for session in sessions for cover in session["covers"]]
    body["sessions"] = sessions
    body["unresolved_session_constraints"] = _unresolved_constraints(merged_constraints)
    body["coverage_summary"] = {
        "expected_subtopic_ids": expected_ids,
        "covered_subtopic_ids": covered,
        "total_duration_minutes": sum(session["duration_minutes"] for session in sessions),
    }
    problems = validate_lesson_plan_body(body, expected_subtopic_ids=expected_ids)
    if problems:
        raise ValueError("Invalid Lesson Plan decision:\n- " + "\n- ".join(problems))
    if _lesson_plan_contract(body) == original_contract:
        raise ValueError("Lesson Plan decision does not change the current artifact")
    next_sessions = {str(session["id"]): session for session in sessions}
    affected = {
        session_id
        for session_id in original_sessions.keys() | next_sessions.keys()
        if original_sessions.get(session_id) != next_sessions.get(session_id)
    }
    body["session_id_cursor"] = session_id_cursor
    log = body.setdefault("decision_log", [])
    log.append(
        {
            "id": f"lpd{len(log) + 1}",
            "constraint_fields": changed_constraint_fields,
            "operations": [deepcopy(operation) for operation in operations],
            "affected_session_ids": sorted(affected),
            "rationale": rationale,
        }
    )
    return decided


def _normalise_constraints(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw or {}
    max_session_hours = raw.get("max_session_hours", DEFAULT_MAX_SESSION_HOURS)
    if (
        not isinstance(max_session_hours, int | float)
        or isinstance(max_session_hours, bool)
        or max_session_hours <= 0
    ):
        raise ValueError("max_session_hours must be positive")
    default_mode = raw.get("default_mode", "live")
    if default_mode not in VALID_MODES:
        raise ValueError("default_mode must be live or self_study")
    result: dict[str, Any] = {
        "max_session_hours": float(max_session_hours),
        "default_mode": default_mode,
    }
    if "calendar_dates" in raw:
        calendar_dates = raw["calendar_dates"]
        if not isinstance(calendar_dates, list) or not all(
            isinstance(value, str) and value.strip() for value in calendar_dates
        ):
            raise ValueError("calendar_dates must be a list of nonblank strings")
        result["calendar_dates"] = list(calendar_dates)
    if "instructor_count" in raw:
        instructor_count = raw["instructor_count"]
        if instructor_count is not None and (
            not isinstance(instructor_count, int)
            or isinstance(instructor_count, bool)
            or instructor_count < 1
        ):
            raise ValueError("instructor_count must be a positive integer or null")
        result["instructor_count"] = instructor_count
    if "delivery_platform" in raw:
        platform = raw["delivery_platform"]
        if platform is not None and (not isinstance(platform, str) or not platform.strip()):
            raise ValueError("delivery_platform must be nonblank text or null")
        result["delivery_platform"] = platform.strip() if isinstance(platform, str) else None
    return result


def _unresolved_constraints(raw: dict[str, Any] | None) -> list[str]:
    raw = raw or {}
    unresolved = []
    if not raw.get("calendar_dates"):
        unresolved.append("calendar_dates")
    if raw.get("instructor_count") is None:
        unresolved.append("instructor_count")
    if not raw.get("delivery_platform"):
        unresolved.append("delivery_platform")
    return unresolved


def _lesson_plan_contract(body: dict[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in body.items() if key != "decision_log"}


def _reject_duplicate_lesson_operation(
    seen: set[tuple[str, str]],
    op: str,
    target_id: str,
) -> None:
    key = (op, target_id)
    if key in seen:
        raise ValueError(f"duplicate Lesson Plan {op} operation for {target_id}")
    seen.add(key)


def _find_cover(
    sessions: list[dict[str, Any]],
    subtopic_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    matches = [
        (session, cover)
        for session in sessions
        for cover in session.get("covers", [])
        if cover.get("subtopic_id") == subtopic_id
    ]
    if len(matches) != 1:
        raise ValueError(f"unknown or ambiguous Lesson Plan subtopic: {subtopic_id!r}")
    return matches[0]


def _find_session(
    sessions: list[dict[str, Any]],
    session_id: str,
) -> dict[str, Any]:
    matches = [session for session in sessions if session.get("id") == session_id]
    if len(matches) != 1:
        raise ValueError(f"unknown or ambiguous Lesson Plan session: {session_id!r}")
    return matches[0]


def _regroup_sessions(
    sessions: list[dict[str, Any]],
    planned: dict[str, dict[str, Any]],
    *,
    max_minutes: int,
    session_id_cursor: int,
) -> tuple[list[dict[str, Any]], int]:
    covers = [deepcopy(cover) for session in sessions for cover in session["covers"]]
    groups: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_minutes = 0
    for cover in covers:
        minutes = planned[cover["subtopic_id"]]["duration_minutes"]
        if minutes > max_minutes:
            raise ValueError(
                f"Lesson Plan segment {cover['subtopic_id']} exceeds max_session_hours"
            )
        if current and current_minutes + minutes > max_minutes:
            groups.append(current)
            current = []
            current_minutes = 0
        current.append(cover)
        current_minutes += minutes
    if current:
        groups.append(current)

    existing_by_coverage = {
        tuple(cover["subtopic_id"] for cover in session["covers"]): session for session in sessions
    }
    used_ids: set[str] = set()
    cursor = session_id_cursor + 1
    result: list[dict[str, Any]] = []
    for group in groups:
        coverage = tuple(cover["subtopic_id"] for cover in group)
        existing = existing_by_coverage.get(coverage)
        if existing is not None and existing["id"] not in used_ids:
            session = deepcopy(existing)
            session["covers"] = group
        else:
            while f"sess{cursor}" in used_ids:
                cursor += 1
            session = {"id": f"sess{cursor}", "covers": group}
            cursor += 1
        used_ids.add(session["id"])
        result.append(session)
    _refresh_sessions(result, planned)
    return result, max(session_id_cursor, cursor - 1)


def _session_id_cursor(body: dict[str, Any]) -> int:
    """Recover the highest allocated session ID, including retired history."""
    stored = body.get("session_id_cursor")
    cursor = stored if isinstance(stored, int) and not isinstance(stored, bool) else 0
    candidates: list[Any] = [
        session.get("id") for session in body.get("sessions", []) if isinstance(session, dict)
    ]
    for record in body.get("decision_log", []):
        if not isinstance(record, dict):
            continue
        candidates.extend(record.get("affected_session_ids", []))
        for operation in record.get("operations", []):
            if not isinstance(operation, dict):
                continue
            candidates.append(operation.get("value"))
            candidates.extend(operation.get("session_ids", []))
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.startswith("sess") and candidate[4:].isdigit():
            cursor = max(cursor, int(candidate[4:]))
    return cursor


def _refresh_sessions(
    sessions: list[dict[str, Any]],
    planned: dict[str, dict[str, Any]],
) -> None:
    for order, session in enumerate(sessions, start=1):
        if not session.get("covers"):
            raise ValueError(f"Lesson Plan session {session.get('id')} cannot be empty")
        titles = [planned[cover["subtopic_id"]]["title"] for cover in session["covers"]]
        total_minutes = sum(
            planned[cover["subtopic_id"]]["duration_minutes"] for cover in session["covers"]
        )
        session.update(
            {
                "order": order,
                "title": " / ".join(titles)[:120],
                "duration_minutes": total_minutes,
                "duration_hours": round(total_minutes / 60, 2),
            }
        )


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
        "live" if {"activities", "case_study", "assessment"} & set(selected_types) else default_mode
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
