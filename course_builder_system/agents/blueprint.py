"""Blueprint generation and decision reduction for Sprint 2."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from orchestrator import make_artifact

DESIGN_SCHEMA_VERSION = "0.2"

ASSET_CATALOG = {
    "learning_objectives": ("Learning Objectives", "docx", "State measurable learner targets."),
    "course_content": ("Course Content", "pptx", "Teach the approved coverage at depth."),
    "summary": ("Summary", "docx", "Reinforce the lesson without adding new claims."),
    "case_study": ("Case Study", "pptx", "Apply the subtopic to a grounded scenario."),
    "assessment": ("Assessment", "pptx", "Check learner understanding and transfer."),
    "activities": ("Activities", "docx", "Give learners participatory practice."),
    "resources": ("Additional Resources", "docx", "Point learners to approved source paths."),
}

ASSET_SUFFIX = {
    "learning_objectives": "lo",
    "course_content": "cc",
    "summary": "summary",
    "case_study": "case",
    "assessment": "assess",
    "activities": "activities",
    "resources": "resources",
}


def build_blueprint_artifact(course_model: dict) -> dict:
    return make_artifact(
        course_model["course_id"],
        "blueprint",
        "blueprint",
        body=build_blueprint_body(course_model),
        inputs=["course_model"],
        schema_version=DESIGN_SCHEMA_VERSION,
    )


def build_blueprint_body(course_model: dict) -> dict:
    defaults = _course_defaults(course_model)
    plans = []
    for index, subtopic in enumerate(_iter_subtopics(course_model), start=1):
        plans.append(_subtopic_plan(subtopic, defaults, index=index))
    return {
        "course_defaults": defaults,
        "subtopic_plans": plans,
        "decision_log": [
            {
                "id": "bd1",
                "scope": "course_defaults",
                "decision": "accepted_generated_defaults",
                "rationale": (
                    "Initial Blueprint uses course-level defaults and only varies "
                    "subtopic assets where the Course Model suggests practice or diagnosis."
                ),
            }
        ],
    }


def apply_blueprint_decision(
    blueprint: dict,
    *,
    default_asset_types: list[str] | tuple[str, ...] | None = None,
    default_depth: dict[str, Any] | None = None,
    selected_asset_types: dict[str, list[str] | tuple[str, ...]] | None = None,
    depth_overrides: dict[str, dict[str, Any]] | None = None,
    anchor_waivers: set[str] | None = None,
    approved_source_ids_by_subtopic: dict[str, list[str] | tuple[str, ...]] | None = None,
    rationale: str = "Human Blueprint checkpoint.",
) -> dict:
    """Apply course defaults and per-subtopic exceptions to a Blueprint."""
    selected_asset_types = selected_asset_types or {}
    depth_overrides = depth_overrides or {}
    anchor_waivers = anchor_waivers or set()
    approved_source_ids_by_subtopic = approved_source_ids_by_subtopic or {}
    rationale = str(rationale).strip()
    if not rationale:
        raise ValueError("Blueprint decision rationale cannot be blank")
    if len(rationale) > 500:
        raise ValueError("Blueprint decision rationale cannot exceed 500 characters")
    decided = deepcopy(blueprint)
    body = decided.get("body", {})
    plans = body.get("subtopic_plans", [])
    plan_ids = {plan["subtopic_id"] for plan in plans}
    unknown = (
        set(selected_asset_types)
        | set(depth_overrides)
        | set(anchor_waivers)
        | set(approved_source_ids_by_subtopic)
    ) - plan_ids
    if unknown:
        raise ValueError(f"Blueprint decision references unknown subtopics: {sorted(unknown)}")

    if default_asset_types is not None:
        _validate_asset_selection("course defaults", default_asset_types)
        body["course_defaults"]["default_asset_types"] = list(default_asset_types)
    if default_depth is not None:
        _apply_depth_override(body["course_defaults"]["depth_budget"], default_depth)

    original_contract = {
        "course_defaults": deepcopy(blueprint.get("body", {}).get("course_defaults", {})),
        "subtopic_plans": deepcopy(blueprint.get("body", {}).get("subtopic_plans", [])),
    }
    log_entries: list[tuple[str, str]] = []
    if default_asset_types is not None:
        log_entries.append(("course_defaults", "asset_defaults"))
    if default_depth is not None:
        log_entries.append(("course_defaults", "depth_defaults"))

    for plan in plans:
        subtopic_id = plan["subtopic_id"]
        existing_selected = [
            asset["asset_type"]
            for asset in plan["asset_plan"]
            if asset.get("selection_status") == "selected"
        ]
        requested = selected_asset_types.get(subtopic_id)
        has_asset_decision = requested is not None or default_asset_types is not None
        selected_values = (
            requested
            if requested is not None
            else default_asset_types
            if default_asset_types is not None
            else existing_selected
        )
        _validate_asset_selection(subtopic_id, selected_values)
        selected = set(selected_values)
        waiver = (
            subtopic_id in anchor_waivers
            if has_asset_decision
            else subtopic_id in anchor_waivers
            or bool(plan.get("anchor_asset_waiver_confirmed"))
        )
        if "course_content" not in selected and not waiver:
            raise ValueError(
                f"Blueprint decision for {subtopic_id} omits course_content "
                "without an explicit anchor waiver"
            )
        if "course_content" in selected and waiver:
            raise ValueError(
                f"Blueprint decision for {subtopic_id} confirms an anchor waiver "
                "while course_content remains selected"
            )
        if has_asset_decision:
            routed_sources = list(
                approved_source_ids_by_subtopic.get(
                    subtopic_id,
                    _existing_routed_sources(plan),
                )
            )
            for asset in plan["asset_plan"]:
                included = asset["asset_type"] in selected
                asset["selection_status"] = "selected" if included else "rejected"
                asset["source_ids"] = list(routed_sources) if included else []
        if has_asset_decision or subtopic_id in anchor_waivers:
            plan["anchor_asset_waiver_confirmed"] = waiver
        if requested is not None:
            log_entries.append((subtopic_id, "asset_exception"))

        if default_depth is not None:
            _apply_depth_override(plan["depth_budget"], default_depth)
        if subtopic_id in depth_overrides:
            _apply_depth_override(plan["depth_budget"], depth_overrides[subtopic_id])
            log_entries.append((subtopic_id, "depth_exception"))

    final_contract = {
        "course_defaults": body.get("course_defaults", {}),
        "subtopic_plans": plans,
    }
    if final_contract == original_contract:
        raise ValueError("Blueprint decision does not change the current artifact")

    log_index = len(body.get("decision_log", [])) + 1
    for scope, decision in log_entries:
        body["decision_log"].append(
            {
                "id": f"bd{log_index}",
                "scope": scope,
                "decision": decision,
                "rationale": rationale,
            }
        )
        log_index += 1
    return decided


def _course_defaults(course_model: dict) -> dict:
    level = course_model["body"]["course_metadata"].get("level", "beginner")
    depth_level = _depth_level(level)
    minutes = 20 if depth_level == "introductory" else 30 if depth_level == "intermediate" else 40
    word_target = minutes * 55
    return {
        "depth_budget": {
            "level": depth_level,
            "target_learning_minutes": minutes,
            "target_word_range": {
                "minimum": max(300, word_target - 350),
                "target": word_target,
                "maximum": word_target + 450,
            },
            "required_concept_ids": [],
            "required_example_count": 2,
            "case_depth": "brief",
            "assessment_complexity": "application",
            "expansion_policy": "targeted_by_coverage_gap",
        },
        "default_asset_types": [
            "learning_objectives",
            "course_content",
            "summary",
            "assessment",
        ],
        "source_routing_policy": (
            "Route only sources approved for the subtopic; do not route rejected, "
            "proposed, unavailable, or contentless sources."
        ),
    }


def _subtopic_plan(subtopic: dict, defaults: dict, *, index: int) -> dict:
    concept_ids = [concept["id"] for concept in subtopic.get("concepts", [])]
    depth_budget = deepcopy(defaults["depth_budget"])
    depth_budget["required_concept_ids"] = concept_ids
    depth_budget["required_example_count"] = _example_count(subtopic, index)
    depth_budget["case_depth"] = _case_depth(subtopic)
    depth_budget["assessment_complexity"] = _assessment_complexity(index)

    selected_types = _selected_asset_types(subtopic, index)
    assets = [
        _asset(subtopic, asset_type, selected=asset_type in selected_types)
        for asset_type in ASSET_CATALOG
    ]
    return {
        "subtopic_id": subtopic["id"],
        "depth_budget": depth_budget,
        "asset_plan": assets,
        "source_routing_notes": (
            "Selected assets cite only this subtopic's approved source ids: "
            + ", ".join(subtopic.get("approved_source_ids", []))
        ),
        "anchor_asset_waiver_confirmed": False,
    }


def _asset(subtopic: dict, asset_type: str, *, selected: bool) -> dict:
    title, file_format, purpose = ASSET_CATALOG[asset_type]
    source_ids = list(subtopic.get("approved_source_ids", [])) if selected else []
    return {
        "id": f"{subtopic['id']}_{ASSET_SUFFIX[asset_type]}",
        "asset_type": asset_type,
        "title": title if asset_type != "course_content" else subtopic["title"],
        "format": file_format,
        "selection_status": "selected" if selected else "proposed",
        "purpose": purpose,
        "source_ids": source_ids,
    }


def _selected_asset_types(subtopic: dict, index: int) -> set[str]:
    title = subtopic.get("title", "").lower()
    selected = {"learning_objectives", "course_content", "summary"}
    if index % 2 == 0:
        selected.add("activities")
    if any(marker in title for marker in ("practice", "workflow", "ratio", "recipe")):
        selected.add("assessment")
    if any(marker in title for marker in ("diagnosis", "troubleshooting", "taste", "case")):
        selected.update({"case_study", "assessment"})
    if index == 1:
        selected.add("resources")
    return selected


def _apply_depth_override(depth_budget: dict, override: dict[str, Any]) -> None:
    allowed = {
        "level",
        "target_learning_minutes",
        "target_word_range",
        "required_example_count",
        "case_depth",
        "assessment_complexity",
    }
    unknown = sorted(set(override) - allowed)
    if unknown:
        raise ValueError(f"unknown Blueprint depth override fields: {unknown}")
    if not override:
        raise ValueError("Blueprint depth override must include at least one field")
    if "level" in override and override["level"] not in {
        "introductory",
        "intermediate",
        "advanced",
        "custom",
    }:
        raise ValueError("Blueprint depth level is invalid")
    if "target_learning_minutes" in override:
        value = override["target_learning_minutes"]
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise ValueError("Blueprint target learning minutes must be a positive integer")
    if "target_word_range" in override:
        word_range = override["target_word_range"]
        if not isinstance(word_range, dict) or set(word_range) != {
            "minimum",
            "target",
            "maximum",
        }:
            raise ValueError(
                "Blueprint target word range requires minimum, target, and maximum"
            )
        values = [word_range[key] for key in ("minimum", "target", "maximum")]
        if any(not isinstance(value, int) or isinstance(value, bool) for value in values):
            raise ValueError("Blueprint target word range values must be integers")
        invalid_bounds = values[0] < 0 or values[1] < 1 or values[2] < 1
        if invalid_bounds or not values[0] <= values[1] <= values[2]:
            raise ValueError(
                "Blueprint target word range must satisfy minimum <= target <= maximum"
            )
    if "required_example_count" in override:
        value = override["required_example_count"]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError("Blueprint example count must be a non-negative integer")
    if "case_depth" in override and override["case_depth"] not in {
        "none",
        "brief",
        "detailed",
    }:
        raise ValueError("Blueprint case depth is invalid")
    if "assessment_complexity" in override and override["assessment_complexity"] not in {
        "none",
        "recall",
        "application",
        "analysis",
    }:
        raise ValueError("Blueprint assessment complexity is invalid")
    for key, value in override.items():
        depth_budget[key] = deepcopy(value)


def _validate_asset_selection(scope: str, asset_types: list[str] | tuple[str, ...]) -> None:
    if not asset_types:
        raise ValueError(f"Blueprint decision for {scope} selects no assets")
    duplicates = sorted(
        {asset_type for asset_type in asset_types if asset_types.count(asset_type) > 1}
    )
    if duplicates:
        raise ValueError(
            f"Blueprint decision for {scope} contains duplicate asset types: {duplicates}"
        )
    unknown = sorted(set(asset_types) - set(ASSET_CATALOG))
    if unknown:
        raise ValueError(
            f"Blueprint decision for {scope} references unknown asset types: {unknown}"
        )


def _existing_routed_sources(plan: dict[str, Any]) -> list[str]:
    routed: list[str] = []
    for asset in plan.get("asset_plan", []):
        for source_id in asset.get("source_ids", []):
            if source_id not in routed:
                routed.append(source_id)
    return routed


def _iter_subtopics(course_model: dict) -> list[dict]:
    return [
        subtopic
        for module in course_model.get("body", {}).get("modules", [])
        for subtopic in module.get("subtopics", [])
    ]


def _depth_level(level: str) -> str:
    normalized = str(level).lower()
    if normalized in {"beginner", "introductory"}:
        return "introductory"
    if normalized in {"intermediate", "advanced"}:
        return normalized
    return "custom"


def _example_count(subtopic: dict, index: int) -> int:
    base = max(1, len(subtopic.get("coverage_requirements", [])))
    return base + (1 if index % 2 == 0 else 0)


def _case_depth(subtopic: dict) -> str:
    title = subtopic.get("title", "").lower()
    if any(marker in title for marker in ("diagnosis", "troubleshooting", "taste", "case")):
        return "detailed"
    if any(marker in title for marker in ("practice", "workflow", "ratio", "recipe")):
        return "brief"
    return "none"


def _assessment_complexity(index: int) -> str:
    return "application" if index % 2 else "analysis"
