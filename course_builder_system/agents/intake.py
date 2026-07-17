"""Course Brief intake for sparse subject requests."""

from __future__ import annotations

import re
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from interaction import QuestionSpec, ScriptedResponder
from orchestrator import make_artifact

DESIGN_SCHEMA_VERSION = "0.2"
INTAKE_FOLLOWUP_MODEL = "claude-haiku-4-5"

BRIEF_FIELD_ORDER = (
    "subject",
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

MANDATORY_BRIEF_FIELDS = (
    "subject",
    "audience",
    "purpose",
    "prior_knowledge",
    "level",
    "duration",
    "modality",
    "language",
)

MANDATORY_QUESTION_FIELDS = MANDATORY_BRIEF_FIELDS[1:]
CONDITIONAL_QUESTION_IDS = ("brief_live_teaching_constraints",)
LIST_BRIEF_FIELDS = {
    "in_scope",
    "out_of_scope",
    "must_have_topics",
    "constraints",
    "available_materials",
}
NULLABLE_BRIEF_FIELDS = {
    "jurisdiction",
    "accessibility_requirements",
    "assessment_expectations",
    "live_teaching_constraints",
    "tools_or_equipment",
    "freshness_requirement",
}
DIRECT_EDIT_FIELDS = {
    "course_title",
    *BRIEF_FIELD_ORDER[1:],
    "constraints",
    "available_materials",
    "accessibility_requirements",
}
TEXT_FIELD_LIMITS = {
    "subject": 200,
    "course_title": 200,
    "audience": 500,
    "prior_knowledge": 500,
    "purpose": 700,
    "duration": 200,
    "language": 100,
    "jurisdiction": 500,
    "accessibility_requirements": 500,
    "assessment_expectations": 500,
    "live_teaching_constraints": 500,
    "tools_or_equipment": 500,
    "freshness_requirement": 500,
}
LIST_ITEM_LIMITS = {
    "available_materials": 1000,
}

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
        allow_agent_followup=True,
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


@dataclass(frozen=True)
class IntakeGap:
    id: str
    kind: str
    field: str
    severity: str
    message: str


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
    if not isinstance(subject, str):
        raise ValueError("subject must be text")
    normalized_subject = subject.strip()
    if not normalized_subject:
        raise ValueError("subject cannot be empty")
    _validate_field_length("subject", normalized_subject)
    normalized_description: str | None = None
    if description is not None:
        if not isinstance(description, str):
            raise ValueError("description must be text")
        normalized_description = description.strip() or None
        if normalized_description is not None:
            _validate_field_length("purpose", normalized_description)
    normalized_constraints = _validated_seed_list("constraints", constraints or [])
    normalized_locators = _validated_seed_list(
        "available_materials", known_source_locators or []
    )
    resolved_course_id = course_id or slugify_course_id(normalized_subject)
    return make_artifact(
        resolved_course_id,
        "subject_request",
        "human",
        body={
            "subject": normalized_subject,
            "description": normalized_description,
            "known_source_locators": normalized_locators,
            "constraints": normalized_constraints,
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
    allowed_resolved_fields: set[str] | None = None,
    answered_question_ids: set[str] | None = None,
) -> list[QuestionSpec]:
    """Validate bounded agent follow-up candidates for the brief stage."""
    max_questions = min(max_questions, 3)
    allowed_resolved_fields = allowed_resolved_fields or set()
    answered_question_ids = answered_question_ids or set()
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
        if question.id in answered_question_ids:
            continue
        if question.id in seen_ids or question.field in seen_fields:
            continue
        if question.field not in allowed_fields:
            continue
        if (
            question.answer_type != "free_text"
            or question.options
            or question.default is not None
            or not question.required
            or question.allow_skip
            or not question.allow_agent_followup
            or not question.prompt.strip()
            or not question.why.strip()
            or not question.visible_for(existing_answers)
        ):
            continue
        if (
            question.field not in allowed_resolved_fields
            and question.field in existing_answers
            and existing_answers[question.field]
            not in (
                None,
                "",
                [],
            )
        ):
            continue
        accepted.append(question)
        seen_ids.add(question.id)
        seen_fields.add(question.field)
    return accepted


def analyze_intake_gaps(subject_request: dict, answers: dict[str, Any]) -> list[IntakeGap]:
    """Detect ambiguity/conflicts before asking any agent follow-up questions."""
    body = subject_request.get("body", subject_request)
    gaps: list[IntakeGap] = []
    subject = str(body.get("subject", "")).strip()
    seeded = _seed_answers(subject_request if "body" in subject_request else {"body": body})
    merged = {**seeded, **answers}

    purpose = str(merged.get("purpose", "")).strip()
    if (
        len(_tokens(subject)) < 2
        and not body.get("description")
        and purpose in {"", _brief_defaults(subject)["purpose"]}
    ):
        gaps.append(
            IntakeGap(
                id="gap_subject_context",
                kind="ambiguity",
                field="purpose",
                severity="medium",
                message="The subject is too sparse to infer a useful course purpose.",
            )
        )
    audience = str(merged.get("audience", "")).strip().lower()
    if audience in {"", "everyone", "anyone", "general"}:
        gaps.append(
            IntakeGap(
                id="gap_audience_generic",
                kind="ambiguity",
                field="audience",
                severity="medium",
                message="The audience is generic, which makes depth and examples ambiguous.",
            )
        )
    if _scope_overlap(merged.get("in_scope"), merged.get("out_of_scope")):
        gaps.append(
            IntakeGap(
                id="gap_scope_overlap",
                kind="conflict",
                field="out_of_scope",
                severity="high",
                message="At least one topic appears in both in-scope and out-of-scope inputs.",
            )
        )
    prior = str(merged.get("prior_knowledge", "")).lower()
    level = str(merged.get("level", "")).lower()
    if level in {"beginner", "introductory"} and any(
        marker in prior for marker in ("advanced", "expert", "professional")
    ):
        gaps.append(
            IntakeGap(
                id="gap_level_prior_conflict",
                kind="conflict",
                field="prior_knowledge",
                severity="medium",
                message="The requested beginner level conflicts with advanced prior knowledge.",
            )
        )
    return gaps


def gap_followups(
    subject_request: dict,
    answers: dict[str, Any],
    *,
    max_questions: int = 3,
    answered_question_ids: Iterable[str] = (),
) -> list[QuestionSpec]:
    """Turn detected gaps into validated, stage-safe follow-up questions."""
    proposed = []
    gaps = analyze_intake_gaps(subject_request, answers)
    for gap in gaps:
        proposed.append(
            QuestionSpec(
                id=f"brief_followup_{gap.field}_{gap.id}",
                field=gap.field,
                prompt=gap.message,
                why="Resolving this improves the Course Brief before research starts.",
                answer_type="free_text",
                allow_agent_followup=True,
            )
        )
    return validated_followups(
        answers,
        proposed,
        max_questions=max_questions,
        allowed_resolved_fields={gap.field for gap in gaps},
        answered_question_ids=set(answered_question_ids),
    )


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


def build_initial_brief_artifact(subject_request: dict) -> dict:
    """Create the canonical durable intake draft for a newly created course."""
    return build_brief_artifact(subject_request, _seed_answers(subject_request))


def brief_artifact_from_body(subject_request: dict, body: dict[str, Any]) -> dict:
    """Wrap a validated Brief body without moving lifecycle ownership into intake."""
    return make_artifact(
        subject_request["course_id"],
        "brief",
        "intake",
        body=body,
        inputs=["subject_request"],
        schema_version=DESIGN_SCHEMA_VERSION,
    )


def build_brief_body(subject_request_body: dict, answers: dict[str, Any]) -> dict:
    """Build a new Brief while leaving untouched defaults explicitly unresolved."""
    raw_subject = subject_request_body["subject"]
    if not isinstance(raw_subject, str) or not raw_subject.strip():
        raise ValueError("subject cannot be empty")
    subject = raw_subject.strip()
    _validate_field_length("subject", subject)
    defaults = _brief_defaults(subject)
    supplied: dict[str, Any] = {}
    for key, value in answers.items():
        if key not in DIRECT_EDIT_FIELDS:
            raise ValueError(f"unknown Brief field: {key}")
        if not _present(value):
            continue
        normalized = _validate_direct_update(key, value)
        if _present(normalized):
            supplied[key] = normalized
    values = {**defaults, **supplied}
    values["subject"] = subject
    values["course_title"] = supplied.get("course_title") or _title_from_subject(subject)
    values["constraints"] = _dedupe(
        _as_list(supplied.get("constraints")) + _as_list(subject_request_body.get("constraints"))
    )
    values["available_materials"] = _dedupe(
        _as_list(supplied.get("available_materials"))
        + _as_list(subject_request_body.get("known_source_locators"))
    )
    explicit = {"subject", *supplied}
    answered = {
        question.id
        for question in COURSE_BRIEF_QUESTIONS
        if question.field in explicit and _present(values.get(question.field))
    }
    state = _make_intake_state(
        subject_request_body,
        values,
        explicit_fields=explicit,
        accepted_default_fields=set(),
        answered_question_ids=answered,
    )
    return _build_readable_body(subject_request_body, values, state)


def normalize_brief_body(
    subject_request: dict,
    brief_body: dict[str, Any],
    *,
    grandfather_assumed_defaults: bool = False,
) -> dict[str, Any]:
    """Project current and historical Briefs through one normalized intake contract.

    Historical artifacts are grandfathered from their readable fields and provenance.
    This keeps committed snapshots byte-for-byte unchanged while giving API consumers a
    valid intake view. Every newly created Brief already carries an explicit state.
    """
    subject_body = _subject_body(subject_request)
    normalized = deepcopy(brief_body)
    raw_state = normalized.get("intake_state")
    if isinstance(raw_state, dict):
        explicit = _valid_field_set(raw_state.get("explicit_fields"))
        accepted = _valid_field_set(raw_state.get("accepted_default_fields"))
        answered = {
            str(item)
            for item in raw_state.get("answered_question_ids", [])
            if isinstance(item, str) and item
        }
    else:
        explicit = {"subject"}
        accepted: set[str] = set()
        provenance = {
            str(item.get("field")): item
            for item in normalized.get("provenance", [])
            if isinstance(item, dict) and isinstance(item.get("field"), str)
        }
        for field_name in BRIEF_FIELD_ORDER[1:]:
            if not _present(normalized.get(field_name)):
                continue
            item = provenance.get(field_name, {})
            if item.get("source") == "default":
                if (
                    item.get("confidence") == "explicit"
                    or grandfather_assumed_defaults
                ):
                    accepted.add(field_name)
            else:
                explicit.add(field_name)
        answered = {
            question.id
            for question in COURSE_BRIEF_QUESTIONS
            if question.field in explicit | accepted
        }
        # Historical Briefs predate explicit skip tracking. Grandfather the optional
        # conditional decision instead of making an approved snapshot newly incomplete.
        answered.update(CONDITIONAL_QUESTION_IDS)
    explicit.add("subject")
    values = _brief_values(normalized, subject_body)
    state = _make_intake_state(
        subject_body,
        values,
        explicit_fields=explicit,
        accepted_default_fields=accepted,
        answered_question_ids=answered,
    )
    normalized["intake_state"] = state
    return normalized


def brief_question_round(
    subject_request: dict,
    brief_body: dict[str, Any],
    *,
    clarification_provider: Any | None = None,
) -> dict[str, Any]:
    """Return one backend-owned visible question round for the current draft."""
    normalized = normalize_brief_body(subject_request, brief_body)
    state = normalized["intake_state"]
    unresolved = set(state["unresolved_required_fields"])
    answered_ids = set(state["answered_question_ids"])
    mandatory = [
        question
        for question in COURSE_BRIEF_QUESTIONS
        if question.field in MANDATORY_QUESTION_FIELDS
        and question.field in unresolved
        and question.visible_for(normalized)
        and question.id not in answered_ids
    ][:5]
    if mandatory:
        return {
            "questions": mandatory,
            "round_kind": "mandatory",
            "gap_analysis": state["last_gap_analysis"],
            "intake_state": state,
        }

    conditional = [
        question
        for question in COURSE_BRIEF_QUESTIONS
        if question.id in CONDITIONAL_QUESTION_IDS
        and question.visible_for(normalized)
        and question.id not in answered_ids
    ]
    if clarification_provider is None:
        followups = gap_followups(
            subject_request,
            normalized,
            answered_question_ids=answered_ids,
        )
    else:
        followups = list(
            clarification_provider.propose(
                subject_request,
                normalized,
                tuple(_gap_from_dict(item) for item in state["last_gap_analysis"]),
                max_questions=3,
            )
        )
        followups = validated_followups(
            normalized,
            followups,
            max_questions=3,
            allowed_resolved_fields={item["field"] for item in state["last_gap_analysis"]},
            answered_question_ids=answered_ids,
        )
    additional = [*conditional, *followups][:3]
    return {
        "questions": additional,
        "round_kind": "clarification"
        if followups
        else "conditional"
        if conditional
        else "complete",
        "gap_analysis": state["last_gap_analysis"],
        "intake_state": state,
    }


def merge_answer_round(
    subject_request: dict,
    brief_body: dict[str, Any],
    submissions: list[dict[str, Any]],
    *,
    clarification_provider: Any | None = None,
) -> dict[str, Any]:
    """Validate and merge one displayed answer round into the canonical Brief."""
    if not submissions or len(submissions) > 5:
        raise ValueError("a Brief answer round must contain between one and five answers")
    normalized = normalize_brief_body(subject_request, brief_body)
    current_round = brief_question_round(
        subject_request,
        normalized,
        clarification_provider=clarification_provider,
    )
    available = {question.id: question for question in current_round["questions"]}
    question_ids = [str(item.get("question_id", "")) for item in submissions]
    if len(question_ids) != len(set(question_ids)):
        raise ValueError("question IDs in one answer round must be unique")

    state = normalized["intake_state"]
    explicit = set(state["explicit_fields"])
    accepted = set(state["accepted_default_fields"])
    answered = set(state["answered_question_ids"])
    values = _brief_values(normalized, _subject_body(subject_request))
    for submission in submissions:
        question_id = submission.get("question_id")
        question = available.get(question_id)
        if question is None:
            raise ValueError(
                f"question {question_id!r} is unknown, resolved, or not visible in this round"
            )
        has_value = "value" in submission
        accept_default = submission.get("accept_default") is True
        skip = submission.get("skip") is True
        if sum((has_value, accept_default, skip)) != 1:
            raise ValueError(f"{question.id}: choose exactly one of value, accept_default, or skip")
        if accept_default:
            if question.default is None:
                raise ValueError(f"{question.id}: no default is available to accept")
            value = question.default
            accepted.add(question.field)
            explicit.discard(question.field)
        elif skip:
            if not question.allow_skip:
                raise ValueError(f"{question.id}: this question cannot be skipped")
            value = None
            accepted.discard(question.field)
            explicit.discard(question.field)
        else:
            raw = submission.get("value")
            if question.answer_type in {"free_text", "duration"} and isinstance(
                raw, str
            ):
                raw = raw.strip()
            if raw in (None, "", []):
                raise ValueError(
                    f"{question.id}: blank values do not implicitly accept a default or skip"
                )
            errors = question.validate_answer(raw)
            if errors:
                raise ValueError("; ".join(errors))
            value = question.coerce_answer(raw)
            _validate_field_length(question.field, value)
            explicit.add(question.field)
            accepted.discard(question.field)
        values[question.field] = _as_list(value) if question.field in LIST_BRIEF_FIELDS else value
        answered.add(question.id)

    next_state = _make_intake_state(
        _subject_body(subject_request),
        values,
        explicit_fields=explicit,
        accepted_default_fields=accepted,
        answered_question_ids=answered,
    )
    return _build_readable_body(_subject_body(subject_request), values, next_state)


def merge_brief_updates(
    subject_request: dict,
    brief_body: dict[str, Any],
    updates: dict[str, Any],
) -> dict[str, Any]:
    """Apply partial direct edits through the same provenance and gap reducer."""
    if not updates:
        raise ValueError("at least one Brief field update is required")
    unknown = sorted(set(updates) - DIRECT_EDIT_FIELDS)
    if unknown:
        raise ValueError(f"unknown Brief fields: {unknown}")
    normalized = normalize_brief_body(subject_request, brief_body)
    state = normalized["intake_state"]
    explicit = set(state["explicit_fields"])
    accepted = set(state["accepted_default_fields"])
    answered = set(state["answered_question_ids"])
    subject_body = _subject_body(subject_request)
    values = _brief_values(normalized, subject_body)
    defaults = _brief_defaults(subject_body["subject"])
    for field_name, raw_value in updates.items():
        value = _validate_direct_update(field_name, raw_value)
        question = _question_for_field(field_name)
        if field_name in MANDATORY_QUESTION_FIELDS and not _present(value):
            values[field_name] = defaults[field_name]
            explicit.discard(field_name)
            accepted.discard(field_name)
            if question:
                answered.discard(question.id)
            continue
        values[field_name] = value
        explicit.add(field_name)
        accepted.discard(field_name)
        if question:
            answered.add(question.id)
    next_state = _make_intake_state(
        subject_body,
        values,
        explicit_fields=explicit,
        accepted_default_fields=accepted,
        answered_question_ids=answered,
    )
    return _build_readable_body(subject_body, values, next_state)


def _make_intake_state(
    subject_request_body: dict[str, Any],
    values: dict[str, Any],
    *,
    explicit_fields: set[str],
    accepted_default_fields: set[str],
    answered_question_ids: set[str],
) -> dict[str, Any]:
    explicit = _valid_field_set(explicit_fields)
    accepted = _valid_field_set(accepted_default_fields) - explicit
    subject_envelope = {"body": subject_request_body}
    gaps = analyze_intake_gaps(subject_envelope, values)
    active_gap_question_ids = {f"brief_followup_{gap.field}_{gap.id}" for gap in gaps}
    # A clarification is answered only when the revised value actually closes its
    # deterministic gap. An inadequate answer remains visible rather than becoming a
    # permanently resolved-but-blocking question.
    answered_question_ids = set(answered_question_ids) - active_gap_question_ids
    unresolved = [
        field_name
        for field_name in MANDATORY_BRIEF_FIELDS
        if field_name not in explicit | accepted or not _present(values.get(field_name))
    ]
    for question in COURSE_BRIEF_QUESTIONS:
        if (
            question.id in CONDITIONAL_QUESTION_IDS
            and question.visible_for(values)
            and question.id not in answered_question_ids
            and question.field not in unresolved
        ):
            unresolved.append(question.field)
    for gap in gaps:
        if gap.field not in unresolved:
            unresolved.append(gap.field)
    return {
        "explicit_fields": _ordered_fields(explicit),
        "accepted_default_fields": _ordered_fields(accepted),
        "unresolved_required_fields": unresolved,
        "answered_question_ids": sorted(answered_question_ids),
        "last_gap_analysis": [_gap_to_dict(gap) for gap in gaps],
    }


def _build_readable_body(
    subject_request_body: dict[str, Any],
    values: dict[str, Any],
    intake_state: dict[str, Any],
) -> dict[str, Any]:
    subject = subject_request_body["subject"]
    defaults = _brief_defaults(subject)
    merged = {**defaults, **values, "subject": subject}
    explicit = set(intake_state["explicit_fields"])
    accepted = set(intake_state["accepted_default_fields"])
    body: dict[str, Any] = {
        "course_title": merged.get("course_title") or _title_from_subject(subject),
        "subject": subject,
        "audience": str(merged["audience"]),
        "prior_knowledge": str(merged["prior_knowledge"]),
        "purpose": str(merged["purpose"]),
        "level": str(merged["level"]),
        "duration": str(merged["duration"]),
        "modality": str(merged["modality"]),
        "language": str(merged["language"]),
        "in_scope": _dedupe(_as_list(merged.get("in_scope"))),
        "out_of_scope": _dedupe(_as_list(merged.get("out_of_scope"))),
        "must_have_topics": _dedupe(_as_list(merged.get("must_have_topics"))),
        "constraints": _dedupe(_as_list(merged.get("constraints"))),
        "available_materials": _dedupe(_as_list(merged.get("available_materials"))),
        "jurisdiction": _nullable(merged.get("jurisdiction")),
        "accessibility_requirements": _nullable(merged.get("accessibility_requirements")),
        "assessment_expectations": _nullable(merged.get("assessment_expectations")),
        "live_teaching_constraints": _nullable(merged.get("live_teaching_constraints")),
        "tools_or_equipment": _nullable(merged.get("tools_or_equipment")),
        "freshness_requirement": _nullable(merged.get("freshness_requirement")),
        "assumptions": [],
        "provenance": [],
        "unresolved_decisions": [
            {
                "field": field_name,
                "reason": "A required answer or explicit default acceptance is still needed.",
                "blocking": True,
            }
            for field_name in intake_state["unresolved_required_fields"]
        ],
        "intake_state": intake_state,
    }
    provenance_fields = (
        *BRIEF_FIELD_ORDER,
        "constraints",
        "available_materials",
        "accessibility_requirements",
    )
    for field_name in provenance_fields:
        if field_name in explicit:
            body["provenance"].append(
                {"field": field_name, "source": "user", "confidence": "explicit"}
            )
        elif field_name in accepted:
            body["provenance"].append(
                {"field": field_name, "source": "default", "confidence": "explicit"}
            )
            body["assumptions"].append(
                {
                    "field": field_name,
                    "value": str(merged.get(field_name)),
                    "rationale": "The course director explicitly accepted this visible default.",
                }
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
                        "This visible default has not yet been explicitly accepted "
                        "or changed."
                    ),
                }
            )
    return body


def _brief_values(body: dict[str, Any], subject_request_body: dict[str, Any]) -> dict[str, Any]:
    defaults = _brief_defaults(subject_request_body["subject"])
    values = {**defaults}
    for field_name in DIRECT_EDIT_FIELDS | {"subject"}:
        if field_name in body:
            values[field_name] = deepcopy(body[field_name])
    values["subject"] = subject_request_body["subject"]
    return values


def _subject_body(subject_request: dict[str, Any]) -> dict[str, Any]:
    body = subject_request.get("body", subject_request)
    if not isinstance(body, dict) or not _present(body.get("subject")):
        raise ValueError("a valid Subject Request is required for Brief intake")
    return body


def _valid_field_set(value: Any) -> set[str]:
    if not isinstance(value, (list, tuple, set)):
        return set()
    allowed = DIRECT_EDIT_FIELDS | {"subject"}
    return {str(item) for item in value if isinstance(item, str) and item in allowed}


def _ordered_fields(fields: set[str]) -> list[str]:
    order = (
        *BRIEF_FIELD_ORDER,
        "constraints",
        "available_materials",
        "accessibility_requirements",
        "course_title",
    )
    return [field_name for field_name in order if field_name in fields]


def _question_for_field(field_name: str) -> QuestionSpec | None:
    return next(
        (question for question in COURSE_BRIEF_QUESTIONS if question.field == field_name),
        None,
    )


def _validate_direct_update(field_name: str, value: Any) -> Any:
    if field_name in LIST_BRIEF_FIELDS:
        if not isinstance(value, (list, tuple, str)):
            raise ValueError(f"{field_name}: expected text or a list of text values")
        if isinstance(value, (list, tuple)) and any(
            not isinstance(item, str) for item in value
        ):
            raise ValueError(f"{field_name}: list items must be text")
        items = _dedupe(_as_list(value))
        _validate_field_length(field_name, items)
        return items
    if field_name in NULLABLE_BRIEF_FIELDS and value is None:
        return None
    if value is None and field_name in MANDATORY_QUESTION_FIELDS:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name}: expected text")
    stripped = value.strip()
    if field_name == "course_title" and not stripped:
        raise ValueError("course_title cannot be empty")
    question = _question_for_field(field_name)
    if question and stripped:
        errors = question.validate_answer(stripped)
        if errors:
            raise ValueError("; ".join(errors))
    _validate_field_length(field_name, stripped)
    return stripped or None


def _validate_field_length(field_name: str, value: Any) -> None:
    if field_name in LIST_BRIEF_FIELDS:
        limit = LIST_ITEM_LIMITS.get(field_name, 300)
        for item in _as_list(value):
            if len(item) > limit:
                raise ValueError(
                    f"{field_name}: list items must be at most {limit} characters"
                )
        return
    limit = TEXT_FIELD_LIMITS.get(field_name)
    if limit is not None and isinstance(value, str) and len(value) > limit:
        raise ValueError(f"{field_name}: must be at most {limit} characters")


def _gap_to_dict(gap: IntakeGap) -> dict[str, str]:
    return {
        "id": gap.id,
        "kind": gap.kind,
        "field": gap.field,
        "severity": gap.severity,
        "message": gap.message,
    }


def _gap_from_dict(value: dict[str, Any]) -> IntakeGap:
    return IntakeGap(
        id=str(value.get("id", "")),
        kind=str(value.get("kind", "")),
        field=str(value.get("field", "")),
        severity=str(value.get("severity", "")),
        message=str(value.get("message", "")),
    )


def _present(value: Any) -> bool:
    return value not in (None, "", [])


def _seed_answers(subject_request: dict) -> dict[str, Any]:
    body = subject_request["body"]
    answers: dict[str, Any] = {}
    description = body.get("description")
    if description is not None and not isinstance(description, str):
        raise ValueError("description must be text")
    normalized_description = description.strip() if isinstance(description, str) else ""
    if normalized_description:
        _validate_field_length("purpose", normalized_description)
        answers["purpose"] = normalized_description
    constraints = _dedupe(_as_list(body.get("constraints")))
    if constraints:
        _validate_field_length("constraints", constraints)
        answers["constraints"] = constraints
    locators = _dedupe(_as_list(body.get("known_source_locators")))
    if locators:
        _validate_field_length("available_materials", locators)
        answers["available_materials"] = locators
    return answers


def _validated_seed_list(field_name: str, values: list[str]) -> list[str]:
    if not isinstance(values, list):
        raise ValueError(f"{field_name}: expected a list of text values")
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError(f"{field_name}: list items must be text")
        item = value.strip()
        if not item:
            raise ValueError(f"{field_name}: list items cannot be blank")
        normalized.append(item)
    result = _dedupe(normalized)
    _validate_field_length(field_name, result)
    return result


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


def _scope_overlap(in_scope: Any, out_of_scope: Any) -> bool:
    in_items = {_normalize_scope_item(item) for item in _as_list(in_scope)}
    out_items = {_normalize_scope_item(item) for item in _as_list(out_of_scope)}
    return bool((in_items - {""}) & (out_items - {""}))


def _normalize_scope_item(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _tokens(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", value.lower()) if token}
