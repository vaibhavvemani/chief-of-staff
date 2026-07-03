"""Course Brief intake for sparse subject requests."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from interaction import QuestionSpec, ScriptedResponder
from orchestrator import make_artifact

DESIGN_SCHEMA_VERSION = "0.2"

BRIEF_FIELD_ORDER = (
    "audience",
    "prior_knowledge",
    "purpose",
    "level",
    "duration",
    "modality",
    "language",
    "in_scope",
    "out_of_scope",
    "must_have_topics",
    "jurisdiction",
    "assessment_expectations",
    "live_teaching_constraints",
    "tools_or_equipment",
    "freshness_requirement",
)

COURSE_BRIEF_QUESTIONS: tuple[QuestionSpec, ...] = (
    QuestionSpec(
        id="brief_audience",
        field="audience",
        prompt="Who is this course for?",
        why="Audience determines examples, assumed vocabulary, and practical depth.",
        answer_type="free_text",
        allow_agent_followup=True,
    ),
    QuestionSpec(
        id="brief_prior_knowledge",
        field="prior_knowledge",
        prompt="What should learners already know?",
        why="Prior knowledge prevents the course from overexplaining or skipping foundations.",
        answer_type="free_text",
        default="No prior knowledge assumed.",
        allow_agent_followup=True,
    ),
    QuestionSpec(
        id="brief_purpose",
        field="purpose",
        prompt="What should learners be able to do after the course?",
        why="The purpose anchors outcomes, research, structure, and assessment.",
        answer_type="free_text",
        allow_agent_followup=True,
    ),
    QuestionSpec(
        id="brief_level",
        field="level",
        prompt="What level should the course target?",
        why="Level controls depth and the expected sophistication of explanations.",
        answer_type="single_choice",
        options=("introductory", "beginner", "intermediate", "advanced", "mixed", "custom"),
        default="beginner",
    ),
    QuestionSpec(
        id="brief_duration",
        field="duration",
        prompt="How large should the course be?",
        why="Duration constrains structure, source depth, and content volume.",
        answer_type="duration",
        default="3 hours of self-paced learning",
    ),
    QuestionSpec(
        id="brief_modality",
        field="modality",
        prompt="How will the course be delivered?",
        why="Delivery mode changes asset choices and lesson-plan assumptions.",
        answer_type="single_choice",
        options=("self_paced", "live", "blended", "workshop", "custom"),
        default="self_paced",
    ),
    QuestionSpec(
        id="brief_language",
        field="language",
        prompt="What language should the course use?",
        why="Language must be explicit before generating learner-facing material.",
        answer_type="free_text",
        default="English",
    ),
    QuestionSpec(
        id="brief_in_scope",
        field="in_scope",
        prompt="What must be included?",
        why="In-scope topics prevent research and structure from drifting.",
        answer_type="free_text",
        default="core concepts and practical application",
    ),
    QuestionSpec(
        id="brief_out_of_scope",
        field="out_of_scope",
        prompt="What should be excluded?",
        why="Exclusions are as important as inclusions for a compact Course Model.",
        answer_type="free_text",
        default="advanced specialist topics",
    ),
    QuestionSpec(
        id="brief_must_have_topics",
        field="must_have_topics",
        prompt="Are there any must-have topics or examples?",
        why="Must-haves become explicit structure and coverage inputs.",
        answer_type="free_text",
        default="practical examples",
    ),
    QuestionSpec(
        id="brief_jurisdiction",
        field="jurisdiction",
        prompt="Does the course depend on a jurisdiction, regulation, or geography?",
        why="Some subjects require location-specific sources or exclusions.",
        answer_type="free_text",
        required=False,
        allow_skip=True,
    ),
    QuestionSpec(
        id="brief_assessment_expectations",
        field="assessment_expectations",
        prompt="What kind of assessment should this course include?",
        why="Assessment expectations shape outcomes and Blueprint asset choices.",
        answer_type="free_text",
        default="Short practical checks and scenario questions.",
    ),
    QuestionSpec(
        id="brief_live_teaching_constraints",
        field="live_teaching_constraints",
        prompt="Are there any live-teaching constraints?",
        why="Live constraints matter later for the lesson plan.",
        answer_type="free_text",
        required=False,
        allow_skip=True,
        show_if={"modality": ("live", "blended", "workshop")},
    ),
    QuestionSpec(
        id="brief_tools_or_equipment",
        field="tools_or_equipment",
        prompt="Are specific tools, software, or equipment required?",
        why="Tools and equipment affect examples, activities, and source selection.",
        answer_type="free_text",
        required=False,
        allow_skip=True,
    ),
    QuestionSpec(
        id="brief_freshness_requirement",
        field="freshness_requirement",
        prompt="Does the material need a specific freshness or currentness standard?",
        why="Freshness requirements affect source age and research scope.",
        answer_type="free_text",
        required=False,
        allow_skip=True,
    ),
)


def slugify_course_id(subject: str, suffix: str = "demo") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", subject.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    if not slug:
        slug = "course"
    return f"{slug}-{suffix}"


def subject_request_artifact(
    *,
    subject: str,
    description: str | None = None,
    known_source_locators: list[str] | None = None,
    constraints: list[str] | None = None,
    course_id: str | None = None,
) -> dict:
    """Create a schema-versioned sparse subject request artifact."""
    resolved_course_id = course_id or slugify_course_id(subject)
    return make_artifact(
        resolved_course_id,
        "subject_request",
        "human",
        body={
            "subject": subject,
            "description": description,
            "known_source_locators": known_source_locators or [],
            "constraints": constraints or [],
        },
        inputs=[],
        schema_version=DESIGN_SCHEMA_VERSION,
    )


def visible_unresolved_questions(
    answers: dict[str, Any],
    *,
    limit: int = 5,
) -> list[QuestionSpec]:
    """Return the next deterministic question round."""
    questions: list[QuestionSpec] = []
    for question in COURSE_BRIEF_QUESTIONS:
        if not question.visible_for(answers):
            continue
        if question.resolved_by(answers):
            continue
        questions.append(question)
        if len(questions) >= limit:
            break
    return questions


def validated_followups(
    existing_answers: dict[str, Any],
    proposed_questions: Iterable[QuestionSpec],
    *,
    max_questions: int = 3,
) -> list[QuestionSpec]:
    """Validate bounded agent follow-up candidates for the brief stage."""
    allowed_fields = {
        question.field for question in COURSE_BRIEF_QUESTIONS if question.allow_agent_followup
    }
    accepted: list[QuestionSpec] = []
    seen_ids: set[str] = set()
    seen_fields: set[str] = set()
    for question in proposed_questions:
        if len(accepted) >= max_questions:
            break
        if not question.id.startswith("brief_followup_"):
            continue
        if question.id in seen_ids or question.field in seen_fields:
            continue
        if question.field not in allowed_fields:
            continue
        if question.field in existing_answers and existing_answers[question.field] not in (
            None,
            "",
            [],
        ):
            continue
        accepted.append(question)
        seen_ids.add(question.id)
        seen_fields.add(question.field)
    return accepted


def run_scripted_intake(subject_request: dict, responder: ScriptedResponder) -> dict:
    """Resolve a Course Brief with deterministic questions and a test responder."""
    answers = _seed_answers(subject_request)
    while True:
        questions = visible_unresolved_questions(answers)
        if not questions:
            break
        answers.update(responder.answer_questions(questions))
    return build_brief_artifact(subject_request, answers)


def build_brief_artifact(subject_request: dict, answers: dict[str, Any]) -> dict:
    course_id = subject_request["course_id"]
    return make_artifact(
        course_id,
        "brief",
        "intake",
        body=build_brief_body(subject_request["body"], answers),
        inputs=["subject_request"],
        schema_version=DESIGN_SCHEMA_VERSION,
    )


def build_brief_body(subject_request_body: dict, answers: dict[str, Any]) -> dict:
    """Build a schema-valid brief body while exposing every assumption."""
    subject = subject_request_body["subject"]
    seeded_constraints = subject_request_body.get("constraints", [])
    seeded_materials = subject_request_body.get("known_source_locators", [])
    defaults = _brief_defaults(subject)
    merged = {**defaults, **{k: v for k, v in answers.items() if v not in (None, "", [])}}

    constraints = _as_list(merged.get("constraints")) + list(seeded_constraints)
    available_materials = _as_list(merged.get("available_materials")) + list(seeded_materials)

    body = {
        "course_title": merged.get("course_title") or _title_from_subject(subject),
        "subject": subject,
        "audience": merged["audience"],
        "prior_knowledge": merged["prior_knowledge"],
        "purpose": merged["purpose"],
        "level": merged["level"],
        "duration": merged["duration"],
        "modality": merged["modality"],
        "language": merged["language"],
        "in_scope": _as_list(merged["in_scope"]),
        "out_of_scope": _as_list(merged["out_of_scope"]),
        "must_have_topics": _as_list(merged["must_have_topics"]),
        "constraints": _dedupe([item for item in constraints if item]),
        "available_materials": _dedupe([item for item in available_materials if item]),
        "jurisdiction": _nullable(merged.get("jurisdiction")),
        "accessibility_requirements": _nullable(merged.get("accessibility_requirements")),
        "assessment_expectations": _nullable(merged.get("assessment_expectations")),
        "live_teaching_constraints": _nullable(merged.get("live_teaching_constraints")),
        "tools_or_equipment": _nullable(merged.get("tools_or_equipment")),
        "freshness_requirement": _nullable(merged.get("freshness_requirement")),
        "assumptions": [],
        "provenance": [],
        "unresolved_decisions": [],
    }

    for field_name in BRIEF_FIELD_ORDER:
        if field_name in answers and answers[field_name] not in (None, "", []):
            body["provenance"].append(
                {"field": field_name, "source": "user", "confidence": "explicit"}
            )
        elif field_name in defaults:
            body["provenance"].append(
                {"field": field_name, "source": "default", "confidence": "assumed"}
            )
            body["assumptions"].append(
                {
                    "field": field_name,
                    "value": str(defaults[field_name]),
                    "rationale": (
                        "No explicit answer was supplied; the prototype used a safe default."
                    ),
                }
            )

    return body


def _seed_answers(subject_request: dict) -> dict[str, Any]:
    body = subject_request["body"]
    answers: dict[str, Any] = {}
    description = body.get("description")
    if description:
        answers["purpose"] = description
    if body.get("constraints"):
        answers["constraints"] = list(body["constraints"])
    if body.get("known_source_locators"):
        answers["available_materials"] = list(body["known_source_locators"])
    return answers


def _brief_defaults(subject: str) -> dict[str, Any]:
    return {
        "audience": "General adult learners who are new to the subject.",
        "prior_knowledge": "No prior knowledge assumed.",
        "purpose": f"Build practical working knowledge of {subject}.",
        "level": "beginner",
        "duration": "3 hours of self-paced learning",
        "modality": "self_paced",
        "language": "English",
        "in_scope": [f"core concepts in {subject}", "practical examples"],
        "out_of_scope": ["advanced specialist topics"],
        "must_have_topics": ["practical examples"],
        "constraints": [],
        "available_materials": [],
        "assessment_expectations": "Short practical checks and scenario questions.",
    }


def _title_from_subject(subject: str) -> str:
    return subject[:1].upper() + subject[1:]


def _as_list(value: Any) -> list[str]:
    if value in (None, "", []):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(value)]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _nullable(value: Any) -> str | None:
    if value in (None, "", []):
        return None
    return str(value)
