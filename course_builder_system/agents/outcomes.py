"""Course-level outcome drafting and structured human selection."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from interaction import ChoiceOption, ChoicePrompt, ScriptedResponder
from orchestrator import make_artifact

DESIGN_SCHEMA_VERSION = "0.2"


def draft_outcomes_from_brief(brief: dict) -> list[dict]:
    """Draft domain-neutral measurable outcomes from an approved brief."""
    body = brief["body"]
    subject = body["subject"]
    purpose = body.get("purpose") or body.get("goals") or f"Build working knowledge of {subject}."
    in_scope = body.get("in_scope", [])
    practical_focus = in_scope[0] if in_scope else subject
    return [
        {
            "id": "co1",
            "statement": f"Explain the core concepts and vocabulary needed to work with {subject}.",
            "cognitive_level": "understand",
            "evidence": "Learner accurately explains key terms in their own words.",
            "priority": "core",
        },
        {
            "id": "co2",
            "statement": f"Apply a repeatable process for {practical_focus}.",
            "cognitive_level": "apply",
            "evidence": "Learner completes a realistic task using the process.",
            "priority": "core",
        },
        {
            "id": "co3",
            "statement": (
                f"Analyze common problems or tradeoffs encountered while pursuing: {purpose}"
            ),
            "cognitive_level": "analyze",
            "evidence": "Learner diagnoses a scenario and justifies a next step.",
            "priority": "core",
        },
        {
            "id": "co4",
            "statement": (
                f"Evaluate whether a chosen approach fits the learner's constraints for {subject}."
            ),
            "cognitive_level": "evaluate",
            "evidence": "Learner compares options against explicit criteria.",
            "priority": "supporting",
        },
    ]


def build_outcome_choice_prompt(outcomes: list[dict]) -> ChoicePrompt:
    return ChoicePrompt(
        id="outcomes_select",
        stage="course_outcomes",
        target_artifact="course_outcomes",
        question="Select the course-level outcomes to approve for research and structure.",
        mode="multi",
        min_selections=1,
        allow_custom=True,
        options=tuple(
            ChoiceOption(
                id=outcome["id"],
                label=outcome["statement"],
                description=(
                    f"{outcome['cognitive_level']} outcome; evidence: {outcome['evidence']}"
                ),
                recommendation_rationale=(
                    "Recommended because it follows directly from the approved brief."
                ),
                selected_by_default=outcome["priority"] in {"core", "supporting"},
            )
            for outcome in outcomes
        ),
    )


def apply_outcome_decision(
    outcomes: list[dict],
    selected_ids: list[str] | tuple[str, ...],
    *,
    edits: dict[str, dict[str, Any]] | None = None,
    additions: list[dict[str, Any]] | None = None,
    priority_order: list[str] | None = None,
) -> list[dict]:
    """Apply explicit select/reject/edit/add/reprioritize decisions."""
    by_id = {outcome["id"]: deepcopy(outcome) for outcome in outcomes}
    for outcome_id, patch in (edits or {}).items():
        if outcome_id not in by_id:
            raise ValueError(f"cannot edit unknown outcome {outcome_id!r}")
        by_id[outcome_id].update(patch)

    approved: list[dict] = []
    for outcome_id in selected_ids:
        if outcome_id not in by_id:
            raise ValueError(f"cannot select unknown outcome {outcome_id!r}")
        approved.append(by_id[outcome_id])

    for addition in additions or []:
        if "id" not in addition:
            addition = {**addition, "id": _next_outcome_id([*by_id, *[o["id"] for o in approved]])}
        approved.append(_normalize_added_outcome(addition))

    if priority_order:
        order = {outcome_id: index for index, outcome_id in enumerate(priority_order)}
        approved.sort(key=lambda outcome: order.get(outcome["id"], len(order)))

    if not _has_meaningful_outcome(approved):
        raise ValueError("research cannot start until at least one meaningful outcome is approved")
    return approved


def run_scripted_outcomes(
    brief: dict,
    responder: ScriptedResponder,
    *,
    edits: dict[str, dict[str, Any]] | None = None,
    additions: list[dict[str, Any]] | None = None,
    priority_order: list[str] | None = None,
) -> dict:
    candidates = draft_outcomes_from_brief(brief)
    prompt = build_outcome_choice_prompt(candidates)
    decision = responder.choose(prompt)
    approved = apply_outcome_decision(
        candidates,
        decision.selected_ids,
        edits=edits,
        additions=[*decision.custom_items, *(additions or [])],
        priority_order=priority_order,
    )
    return build_course_outcomes_artifact(brief, approved)


def build_course_outcomes_artifact(brief: dict, outcomes: list[dict]) -> dict:
    body = brief["body"]
    return make_artifact(
        brief["course_id"],
        "course_outcomes",
        "outcomes",
        body={
            "course_title": body.get("course_title") or body["subject"],
            "audience_summary": body.get("audience", "Learners"),
            "outcomes": outcomes,
        },
        inputs=["brief"],
        schema_version=DESIGN_SCHEMA_VERSION,
    )


def _normalize_added_outcome(outcome: dict[str, Any]) -> dict:
    normalized = {
        "id": outcome["id"],
        "statement": outcome["statement"],
        "cognitive_level": outcome.get("cognitive_level", "apply"),
        "evidence": outcome.get("evidence", "Learner demonstrates the outcome in a task."),
        "priority": outcome.get("priority", "supporting"),
    }
    if not _has_meaningful_outcome([normalized]):
        raise ValueError("added outcome must have a meaningful statement")
    return normalized


def _has_meaningful_outcome(outcomes: list[dict]) -> bool:
    return any(len(outcome.get("statement", "").split()) >= 4 for outcome in outcomes)


def _next_outcome_id(existing_ids: list[str]) -> str:
    used = set(existing_ids)
    index = 1
    while f"co{index}" in used:
        index += 1
    return f"co{index}"
