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
    selected_asset_types: dict[str, list[str] | tuple[str, ...]] | None = None,
    depth_overrides: dict[str, dict[str, Any]] | None = None,
    anchor_waivers: set[str] | None = None,
    rationale: str = "Human Blueprint checkpoint.",
) -> dict:
    """Apply per-subtopic exceptions to a generated Blueprint."""
    selected_asset_types = selected_asset_types or {}
    depth_overrides = depth_overrides or {}
    anchor_waivers = anchor_waivers or set()
    decided = deepcopy(blueprint)
    plan_ids = {plan["subtopic_id"] for plan in decided.get("body", {}).get("subtopic_plans", [])}
    unknown = (set(selected_asset_types) | set(depth_overrides) | set(anchor_waivers)) - plan_ids
    if unknown:
        raise ValueError(f"Blueprint decision references unknown subtopics: {sorted(unknown)}")

    log_index = len(decided["body"].get("decision_log", [])) + 1
    for plan in decided["body"]["subtopic_plans"]:
        subtopic_id = plan["subtopic_id"]
        if subtopic_id in selected_asset_types:
            selected = set(selected_asset_types[subtopic_id])
            available = {asset["asset_type"] for asset in plan["asset_plan"]}
            missing = selected - available
            if missing:
                raise ValueError(
                    f"Blueprint decision for {subtopic_id} references unknown asset types: "
                    f"{sorted(missing)}"
                )
            if not selected:
                raise ValueError(f"Blueprint decision for {subtopic_id} selects no assets")
            if "course_content" not in selected and subtopic_id not in anchor_waivers:
                raise ValueError(
                    f"Blueprint decision for {subtopic_id} omits course_content "
                    "without an explicit anchor waiver"
                )
            for asset in plan["asset_plan"]:
                asset["selection_status"] = (
                    "selected" if asset["asset_type"] in selected else "rejected"
                )
            plan["anchor_asset_waiver_confirmed"] = subtopic_id in anchor_waivers
            decided["body"]["decision_log"].append(
                {
                    "id": f"bd{log_index}",
                    "scope": subtopic_id,
                    "decision": "asset_exception",
                    "rationale": rationale,
                }
            )
            log_index += 1
        if subtopic_id in depth_overrides:
            _apply_depth_override(plan["depth_budget"], depth_overrides[subtopic_id])
            decided["body"]["decision_log"].append(
                {
                    "id": f"bd{log_index}",
                    "scope": subtopic_id,
                    "decision": "depth_exception",
                    "rationale": rationale,
                }
            )
            log_index += 1
        if subtopic_id in anchor_waivers:
            plan["anchor_asset_waiver_confirmed"] = True
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
    for key, value in override.items():
        depth_budget[key] = value


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
