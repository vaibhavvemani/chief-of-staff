"""Provider-neutral live stage adapters reduced through deterministic domain logic."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Protocol

import llm
from agents import blueprint as blueprint_agent
from agents import course_model as course_model_agent
from agents import intake, lesson_plan, outcomes, research
from course_model_integrity import validate_course_model_semantics
from course_model_operations import reduce_course_model_operations
from interaction import QuestionSpec
from research_adapter import BoundedLiveResearchProvider, ResearchProvider, SearchResult


class StructuredModelProvider(Protocol):
    """Minimal structured-output boundary used by every judgment-heavy live stage."""

    provider_name: str
    model_name: str

    def ready(self) -> bool: ...

    def generate(
        self,
        *,
        stage: str,
        system: str,
        payload: dict[str, Any],
        schema: dict[str, Any],
        max_tokens: int,
        use_cache: bool = True,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class AnthropicStructuredModelProvider:
    model_name: str = llm.DEFAULT_MODEL
    provider_name: str = "anthropic"

    def ready(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY"))

    def generate(
        self,
        *,
        stage: str,
        system: str,
        payload: dict[str, Any],
        schema: dict[str, Any],
        max_tokens: int,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        result = llm.call(
            [{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            system=system,
            model=self.model_name,
            max_tokens=max_tokens,
            schema=schema,
            use_cache=use_cache,
            call_role=stage,
        )
        if not isinstance(result.parsed, dict):
            raise llm.LLMError(f"{stage} structured output must be an object")
        return result.parsed


class _PlannedResearchProvider:
    """Apply a bounded primary/fallback competitor plan plus one source query."""

    def __init__(
        self,
        provider: ResearchProvider,
        *,
        competitor_query: str,
        competitor_fallback_query: str,
        source_query: str,
        competitor_seed_locators: list[str] | tuple[str, ...] = (),
    ) -> None:
        self.provider = provider
        self.competitor_queries = (competitor_query, competitor_fallback_query)
        self.source_query = source_query
        self.competitor_seed_results = [
            SearchResult(
                id=f"operator_material_{index}",
                title=locator.rstrip("/").rsplit("/", 1)[-1].replace("-", " "),
                locator=locator,
                snippet="Operator-provided available material for competitor review.",
            )
            for index, locator in enumerate(competitor_seed_locators, start=1)
            if locator.startswith(("https://", "http://"))
        ]
        self.search_count = 0
        self.web_search_count = 0

    def search(self, _query: str, *, limit: int):
        if self.search_count >= 2:
            raise ValueError("live Research exceeded its two-query plan")
        if self.search_count == 0:
            results = [
                result
                for query in self.competitor_queries
                for result in self.provider.search(query, limit=limit)
            ]
            results.extend(self.competitor_seed_results)
            self.web_search_count += 2
            selected = _rank_course_results(results, limit=limit)
        else:
            selected = self.provider.search(self.source_query, limit=limit)
            self.web_search_count += 1
        self.search_count += 1
        return selected

    def fetch(self, locator: str):
        return self.provider.fetch(locator)

    def extract_competitor_outline(self, result):
        return self.provider.extract_competitor_outline(result)


def _rank_course_results(results: list[Any], *, limit: int) -> list[Any]:
    """Deduplicate and stably prefer public course/curriculum-shaped results."""
    unique: list[Any] = []
    seen: set[str] = set()
    for result in results:
        locator = str(result.locator)
        if locator in seen:
            continue
        seen.add(locator)
        unique.append(result)

    def score(result: Any) -> int:
        text = f"{result.title} {result.locator}".casefold()
        weighted_markers = {
            "course outline": 8,
            "learning outcomes": 8,
            "curriculum": 7,
            "syllabus": 7,
            "modules": 6,
            "course": 3,
            "class": 2,
            "training": 2,
        }
        operator_priority = 20 if str(result.id).startswith("operator_material_") else 0
        return operator_priority + sum(
            weight for marker, weight in weighted_markers.items() if marker in text
        )

    ranked = sorted(enumerate(unique), key=lambda item: (-score(item[1]), item[0]))
    return [result for _index, result in ranked[:limit]]


class LiveClarificationProvider:
    """Propose at most three field-safe Brief follow-ups through a live model."""

    def __init__(self, model: StructuredModelProvider) -> None:
        self.model = model

    def propose(
        self,
        subject_request: dict,
        brief_body: dict,
        gaps: tuple[intake.IntakeGap, ...],
        *,
        max_questions: int,
    ) -> list[QuestionSpec]:
        allowed_fields = list(
            dict.fromkeys(
                gap.field
                for gap in gaps
                if gap.field
                in {
                    question.field
                    for question in intake.COURSE_BRIEF_QUESTIONS
                    if question.allow_agent_followup
                }
            )
        )
        if not allowed_fields:
            return []
        limit = min(max_questions, 3, len(allowed_fields))
        gap_by_field = {
            field: next(gap for gap in gaps if gap.field == field)
            for field in allowed_fields
        }
        response = self.model.generate(
            stage="brief",
            system=(
                "You propose concise Course Brief clarification questions. Return only "
                "questions for the supplied allowed fields; do not answer them or add fields."
            ),
            payload={
                "subject_request": subject_request.get("body", {}),
                "brief": _brief_slice(brief_body),
                "gaps": [gap.__dict__ for gap in gaps],
                "allowed_fields": allowed_fields,
                "maximum_questions": limit,
            },
            schema={
                "type": "object",
                "additionalProperties": False,
                "required": ["questions"],
                "properties": {
                    "questions": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": limit,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["field", "prompt", "rationale"],
                            "properties": {
                                "field": {"type": "string", "enum": allowed_fields},
                                "prompt": {"type": "string", "minLength": 1, "maxLength": 300},
                                "rationale": {
                                    "type": "string",
                                    "minLength": 1,
                                    "maxLength": 300,
                                },
                            },
                        },
                    }
                },
            },
            max_tokens=1400,
        )
        questions = []
        for item in response["questions"]:
            questions.append(
                QuestionSpec(
                    # Match the canonical gap identity so an inadequate answer is
                    # cleared and the same still-active question can be asked again.
                    id=(
                        f"brief_followup_{item['field']}_"
                        f"{gap_by_field[item['field']].id}"
                    ),
                    field=item["field"],
                    prompt=item["prompt"].strip(),
                    why=item["rationale"].strip(),
                    answer_type="free_text",
                    allow_agent_followup=True,
                )
            )
        return questions


class LiveStageImplementations:
    """Bound live proposal callables to one model and one bounded research factory."""

    def __init__(
        self,
        *,
        model: StructuredModelProvider | None = None,
        research_provider_factory: Callable[[], ResearchProvider] | None = None,
    ) -> None:
        self.model = model or AnthropicStructuredModelProvider()
        self.research_provider_factory = (
            research_provider_factory or BoundedLiveResearchProvider
        )

    def provider_readiness(self) -> dict[str, Any]:
        return {
            "ready": self.model.ready(),
            "provider": self.model.provider_name,
            "model": self.model.model_name,
        }

    def intake(self, inputs: dict, feedback: str | None) -> dict:
        del feedback
        subject = inputs["subject_request"]
        response = self.model.generate(
            stage="brief",
            system=(
                "Synthesize a bounded, domain-neutral Course Brief from the sparse request. "
                "Use only the allowed fields and do not invent expert-sign-off claims."
            ),
            payload={"subject_request": subject.get("body", {})},
            schema=_brief_schema(),
            max_tokens=2400,
        )
        artifact = intake.build_inferred_brief_artifact(subject, response["updates"])
        return {"brief": artifact}

    def course_outcomes(self, inputs: dict, feedback: str | None) -> dict:
        brief = inputs["brief"]
        revision = _revision_feedback(feedback)
        if revision is not None:
            existing = inputs.get("existing_course_outcomes")
            if existing is None:
                raise ValueError("live Outcomes revision requires the current artifact")
            targets = revision["target_ids"]
            by_id = {item["id"]: item for item in existing["body"]["outcomes"]}
            response = self.model.generate(
                stage="outcomes",
                system=(
                    "Revise only the named Course Outcomes. Preserve their IDs and return "
                    "complete replacement fields for each target."
                ),
                payload={
                    "category": revision["category"],
                    "instruction": revision["instruction"],
                    "targets": [by_id[target] for target in targets],
                    "brief": _brief_slice(brief.get("body", {})),
                },
                schema=_outcome_revision_schema(targets),
                max_tokens=2200,
            )
            edits = {item.pop("target_id"): item for item in deepcopy(response["outcomes"])}
            if set(edits) != set(targets):
                raise ValueError("live Outcomes revision must return every named target once")
            revised = outcomes.apply_outcome_decision(
                existing["body"]["outcomes"],
                [item["id"] for item in existing["body"]["outcomes"]],
                edits=edits,
                priority_order=[item["id"] for item in existing["body"]["outcomes"]],
                reject_noop=True,
            )
            artifact = outcomes.build_course_outcomes_artifact(
                brief,
                revised,
                next_canonical_id=existing["body"].get("next_outcome_id"),
            )
            return {"course_outcomes": artifact}

        response = self.model.generate(
            stage="outcomes",
            system=(
                "Propose measurable course-level outcomes grounded only in the approved "
                "Brief. Return observable evidence and no canonical IDs."
            ),
            payload={"brief": _brief_slice(brief.get("body", {}))},
            schema=_outcomes_schema(),
            max_tokens=2600,
        )
        proposed = [
            {"id": f"co{index}", **item}
            for index, item in enumerate(response["outcomes"], start=1)
        ]
        artifact = outcomes.build_course_outcomes_artifact(
            brief,
            proposed,
            next_canonical_id=len(proposed) + 1,
        )
        return {"course_outcomes": artifact}

    def research(self, inputs: dict, feedback: str | None) -> dict:
        del feedback
        brief = inputs["brief"]
        course_outcomes = inputs["course_outcomes"]
        response = self.model.generate(
            stage="research",
            system=(
                "Plan one primary and one fallback bounded competitor query plus one "
                "bounded factual-source query. Keep them specific to the Brief and avoid "
                "high-stakes expansion. Both competitor queries must target public "
                "instructional course pages rather than general how-to articles and must "
                "explicitly seek an outline, curriculum, syllabus, modules, or learning "
                "outcomes. The fallback must use different search terms and may use only a "
                "closely adjacent non-high-stakes instructional domain that preserves every "
                "Brief exclusion."
            ),
            payload={
                "brief": _brief_slice(brief.get("body", {})),
                "outcomes": course_outcomes.get("body", {}).get("outcomes", []),
            },
            schema={
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "competitor_query",
                    "competitor_fallback_query",
                    "source_query",
                ],
                "properties": {
                    "competitor_query": {
                        "type": "string",
                        "minLength": 3,
                        "maxLength": 240,
                        "pattern": (
                            ".*([Oo]utline|[Cc]urriculum|[Ss]yllabus|[Mm]odules?|"
                            "[Ll]earning [Oo]utcomes).*"
                        ),
                    },
                    "competitor_fallback_query": {
                        "type": "string",
                        "minLength": 3,
                        "maxLength": 240,
                        "pattern": (
                            ".*([Oo]utline|[Cc]urriculum|[Ss]yllabus|[Mm]odules?|"
                            "[Ll]earning [Oo]utcomes).*"
                        ),
                    },
                    "source_query": {
                        "type": "string",
                        "minLength": 3,
                        "maxLength": 240,
                    },
                },
            },
            max_tokens=700,
        )
        provider = _PlannedResearchProvider(
            self.research_provider_factory(),
            competitor_query=response["competitor_query"],
            competitor_fallback_query=response["competitor_fallback_query"],
            source_query=response["source_query"],
            competitor_seed_locators=[
                str(locator)
                for locator in brief.get("body", {}).get("available_materials", [])
                if isinstance(locator, str)
            ],
        )
        artifact = research.build_research_dossier_artifact(
            brief,
            course_outcomes,
            provider=provider,
            config=research.ResearchConfig(
                competitor_limit=6,
                source_limit=6,
                min_usable_outlines=3,
            ),
        )
        if provider.search_count != 2:
            raise ValueError("live Research did not execute its exact two-query plan")
        if provider.web_search_count != 3:
            raise ValueError("live Research did not execute its bounded three-search plan")
        return {"research_dossier": artifact}

    def structure(self, inputs: dict, feedback: str | None) -> dict:
        revision = _revision_feedback(feedback)
        if revision is None:
            baseline = course_model_agent.build_course_model_artifact(
                inputs["brief"],
                inputs["course_outcomes"],
                inputs["research_dossier"],
                approved_source_registry=inputs.get("approved_source_registry"),
            )
            targets = _subtopics(baseline)
            instruction = (
                "Refine the generated subtopic titles and purposes so the structure best "
                "serves the approved outcomes and research while preserving scope."
            )
            category = "structure"
        else:
            baseline = inputs.get("existing_course_model")
            if baseline is None:
                raise ValueError("live Course Model revision requires the current artifact")
            target_ids = set(revision["target_ids"])
            targets = [item for item in _subtopics(baseline) if item["id"] in target_ids]
            if {item["id"] for item in targets} != target_ids:
                raise ValueError("live Course Model revision target changed before execution")
            instruction = revision["instruction"]
            category = revision["category"]
        target_ids = [item["id"] for item in targets]
        response = self.model.generate(
            stage="course-model",
            system=(
                "Return structured updates for exactly the named Course Model subtopics. "
                "Do not add IDs, sources, outcomes, modules, concepts, or coverage records."
            ),
            payload={
                "category": category,
                "instruction": instruction,
                "targets": [
                    {
                        "id": item["id"],
                        "title": item["title"],
                        "purpose": item["context"]["purpose"],
                        "in_scope": item["context"]["in_scope"],
                        "out_of_scope": item["context"]["out_of_scope"],
                    }
                    for item in targets
                ],
                "brief": _brief_slice(inputs["brief"].get("body", {})),
                "outcome_ids": [
                    item["id"]
                    for item in inputs["course_outcomes"].get("body", {}).get("outcomes", [])
                ],
            },
            schema=_course_model_update_schema(target_ids),
            max_tokens=4200,
        )
        updates = response["subtopics"]
        if {item["target_id"] for item in updates} != set(target_ids) or len(updates) != len(
            target_ids
        ):
            raise ValueError("live Course Model output must update every named target once")
        operations = [
            {
                "op": "update_subtopic",
                "target_id": item["target_id"],
                "title": item["title"],
                "purpose": item["purpose"],
                "in_scope": item["in_scope"],
                "out_of_scope": item["out_of_scope"],
            }
            for item in updates
        ]
        reduction = reduce_course_model_operations(
            baseline,
            operations,
            course_outcomes=inputs["course_outcomes"],
            research_dossier=inputs["research_dossier"],
            approved_source_registry=inputs["approved_source_registry"],
            reject_noop=True,
        )
        artifact = reduction.candidate_artifact
        artifact["produced_by_step"] = "structure"
        artifact["inputs"] = baseline["inputs"]
        return {"course_model": artifact}

    def blueprint(self, inputs: dict, feedback: str | None) -> dict:
        revision = _revision_feedback(feedback)
        if revision is None:
            baseline = blueprint_agent.build_blueprint_artifact(inputs["course_model"])
            targets = list(baseline["body"]["subtopic_plans"])
            instruction = (
                "Choose a reviewable asset mix and depth for each subtopic while retaining "
                "Course Content as the grounding anchor."
            )
            category = "structure"
        else:
            baseline = inputs.get("existing_blueprint")
            if baseline is None:
                raise ValueError("live Blueprint revision requires the current artifact")
            wanted = set(revision["target_ids"])
            targets = [
                item
                for item in baseline["body"]["subtopic_plans"]
                if item["subtopic_id"] in wanted
            ]
            if {item["subtopic_id"] for item in targets} != wanted:
                raise ValueError("live Blueprint revision target changed before execution")
            instruction = revision["instruction"]
            category = revision["category"]
        target_ids = [item["subtopic_id"] for item in targets]
        response = self.model.generate(
            stage="blueprint",
            system=(
                "Return selected learner-asset types and bounded depth settings for exactly "
                "the named Blueprint subtopics. Course Content must remain selected."
            ),
            payload={
                "category": category,
                "instruction": instruction,
                "targets": targets,
                "course_model_subtopics": _blueprint_target_contexts(
                    inputs["course_model"],
                    target_ids,
                ),
            },
            schema=_blueprint_schema(target_ids),
            max_tokens=3600,
        )
        plans = response["plans"]
        if {item["subtopic_id"] for item in plans} != set(target_ids) or len(plans) != len(
            target_ids
        ):
            raise ValueError("live Blueprint output must return every named target once")
        selected = {item["subtopic_id"]: item["asset_types"] for item in plans}
        overrides = {
            item["subtopic_id"]: item["depth"]
            for item in plans
        }
        try:
            artifact = blueprint_agent.apply_blueprint_decision(
                baseline,
                selected_asset_types=selected,
                depth_overrides=overrides,
                approved_source_ids_by_subtopic={
                    item["id"]: list(item.get("approved_source_ids", []))
                    for item in _subtopics(inputs["course_model"])
                },
                rationale=f"Live {category} proposal: {instruction}"[:500],
            )
        except ValueError as exc:
            if "does not change the current artifact" not in str(exc):
                raise
            artifact = deepcopy(baseline)
            log = artifact["body"].setdefault("decision_log", [])
            log.append(
                {
                    "id": f"bd{len(log) + 1}",
                    "scope": "live_proposal",
                    "decision": "confirmed_current_contract",
                    "rationale": instruction[:500],
                }
            )
        errors = validate_course_model_semantics(
            inputs["course_model"],
            blueprint=artifact,
        )
        if errors:
            raise ValueError("Invalid live Blueprint proposal: " + "; ".join(errors))
        artifact["produced_by_step"] = "blueprint"
        return {"blueprint": artifact}

    def lesson_plan(self, inputs: dict, feedback: str | None) -> dict:
        revision = _revision_feedback(feedback)
        if revision is None:
            baseline = lesson_plan.build_lesson_plan_artifact(
                inputs["content_package"],
                inputs["blueprint"],
                course_model=inputs.get("course_model"),
            )
            target_ids = lesson_plan.course_model_subtopic_ids(inputs["course_model"])
            instruction = (
                "Choose appropriate live or self-study delivery modes without changing "
                "Course Model coverage or learner content."
            )
            category = "delivery"
        else:
            baseline = inputs.get("existing_lesson_plan")
            if baseline is None:
                raise ValueError("live Lesson Plan revision requires the current artifact")
            target_ids = list(revision["target_ids"])
            instruction = revision["instruction"]
            category = revision["category"]
        target_contexts = _lesson_target_contexts(inputs, baseline, target_ids)
        if revision is not None and category == "sequence":
            all_ids = [
                cover["subtopic_id"]
                for session in baseline["body"]["sessions"]
                for cover in session["covers"]
            ]
            if not set(all_ids) - set(target_ids):
                raise ValueError(
                    "a sequence revision requires at least one non-target subtopic anchor"
                )
            response = self.model.generate(
                stage="lesson-plan",
                system=(
                    "Return one bounded placement for exactly each named subtopic. Use "
                    "only supplied subtopic IDs; preserve all coverage and learner content."
                ),
                payload={
                    "category": category,
                    "instruction": instruction,
                    "targets": target_contexts,
                    "current_constraints": baseline["body"].get(
                        "session_constraints", {}
                    ),
                    "sessions": [
                        {
                            "id": session["id"],
                            "order": session["order"],
                            "duration_minutes": session["duration_minutes"],
                            "subtopic_ids": [
                                cover["subtopic_id"] for cover in session["covers"]
                            ],
                        }
                        for session in baseline["body"]["sessions"]
                    ],
                },
                schema=_lesson_sequence_schema(target_ids, all_ids),
                max_tokens=2200,
            )
            placements = response["placements"]
            if {
                item["target_id"] for item in placements
            } != set(target_ids) or len(placements) != len(target_ids):
                raise ValueError(
                    "live Lesson Plan sequence output must return every named target once"
                )
            operations = _lesson_sequence_operations(baseline, placements)
        else:
            response = self.model.generate(
                stage="lesson-plan",
                system=(
                    "Return delivery-mode decisions for exactly the named subtopics. "
                    "Use their bounded Course Model, Blueprint, and current-placement "
                    "context; preserve exact coverage and learner content."
                ),
                payload={
                    "category": category,
                    "instruction": instruction,
                    "targets": target_contexts,
                    "current_constraints": baseline["body"].get(
                        "session_constraints", {}
                    ),
                    "current_modes": {
                        item["id"]: item["current_placement"]["mode"]
                        for item in target_contexts
                    },
                },
                schema=_lesson_mode_schema(target_ids),
                max_tokens=2200,
            )
            modes = response["modes"]
            if {item["subtopic_id"] for item in modes} != set(target_ids) or len(
                modes
            ) != len(target_ids):
                raise ValueError(
                    "live Lesson Plan delivery output must return every named target once"
                )
            current_modes = {
                cover["subtopic_id"]: cover["mode"]
                for session in baseline["body"]["sessions"]
                for cover in session["covers"]
            }
            operations = [
                {
                    "op": "set_mode",
                    "target_id": item["subtopic_id"],
                    "value": item["mode"],
                }
                for item in modes
                if current_modes[item["subtopic_id"]] != item["mode"]
            ]
        if operations:
            artifact = lesson_plan.apply_lesson_plan_decision(
                baseline,
                constraints=None,
                operations=operations,
                content_package=inputs["content_package"],
                blueprint=inputs["blueprint"],
                course_model=inputs["course_model"],
                rationale=f"Live {category} proposal: {instruction}"[:500],
            )
        else:
            artifact = deepcopy(baseline)
            log = artifact["body"].setdefault("decision_log", [])
            log.append(
                {
                    "id": f"lpd{len(log) + 1}",
                    "constraint_fields": [],
                    "operations": [],
                    "affected_session_ids": [],
                    "rationale": f"Live proposal confirmed current modes: {instruction}"[:500],
                }
            )
        artifact["produced_by_step"] = "lesson_plan"
        return {"lesson_plan": artifact}


def _revision_feedback(feedback: str | None) -> dict[str, Any] | None:
    if not feedback:
        return None
    try:
        value = json.loads(feedback)
    except json.JSONDecodeError as exc:
        raise ValueError("live scoped revision feedback must be structured JSON") from exc
    revision = value.get("revision") if isinstance(value, dict) else None
    if not isinstance(revision, dict):
        raise ValueError("live scoped revision feedback is missing its revision object")
    return revision


def _brief_slice(body: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "subject",
        "course_title",
        "purpose",
        "audience",
        "level",
        "prior_knowledge",
        "in_scope",
        "out_of_scope",
        "must_have_topics",
        "duration",
        "modality",
        "language",
        "jurisdiction",
        "constraints",
        "available_materials",
        "accessibility_requirements",
        "assessment_expectations",
        "live_teaching_constraints",
        "tools_or_equipment",
        "freshness_requirement",
    )
    return {key: deepcopy(body[key]) for key in allowed if key in body}


def _subtopics(course_model: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for module in course_model.get("body", {}).get("modules", [])
        if isinstance(module, dict)
        for item in module.get("subtopics", [])
        if isinstance(item, dict)
    ]


def _blueprint_target_contexts(
    course_model: dict[str, Any],
    target_ids: list[str],
) -> list[dict[str, Any]]:
    wanted = set(target_ids)
    source_by_id = {
        item["id"]: item
        for item in course_model.get("body", {}).get("source_registry", [])
        if isinstance(item, dict) and item.get("id")
    }
    return [
        {
            "id": item["id"],
            "title": item["title"],
            "purpose": item["context"]["purpose"],
            "in_scope": item["context"]["in_scope"],
            "out_of_scope": item["context"]["out_of_scope"],
            "concepts": [
                {
                    "id": concept["id"],
                    "name": concept["name"],
                    "summary": concept["summary"],
                }
                for concept in item.get("concepts", [])
            ],
            "coverage_requirements": [
                {
                    "id": coverage["id"],
                    "statement": coverage["statement"],
                    "related_outcome_ids": coverage.get("related_outcome_ids", []),
                }
                for coverage in item.get("coverage_requirements", [])
            ],
            "approved_sources": [
                {
                    "id": source_id,
                    "title": source_by_id[source_id].get("title"),
                    "publisher": source_by_id[source_id].get("publisher"),
                    "source_type": source_by_id[source_id].get("source_type"),
                }
                for source_id in item.get("approved_source_ids", [])
                if source_id in source_by_id
            ],
        }
        for item in _subtopics(course_model)
        if item["id"] in wanted
    ]


def _lesson_target_contexts(
    inputs: dict[str, Any],
    baseline: dict[str, Any],
    target_ids: list[str],
) -> list[dict[str, Any]]:
    model_by_id = {item["id"]: item for item in _subtopics(inputs["course_model"])}
    plan_by_id = {
        item["subtopic_id"]: item
        for item in inputs["blueprint"]["body"].get("subtopic_plans", [])
    }
    content_by_id = {
        item["subtopic_id"]: item
        for item in inputs["content_package"]["body"].get("subtopics", [])
    }
    placement_by_id = {
        cover["subtopic_id"]: {
            "session_id": session["id"],
            "session_order": session["order"],
            "position": position,
            "mode": cover["mode"],
            "talking_point_count": len(cover.get("talking_points", [])),
        }
        for session in baseline["body"]["sessions"]
        for position, cover in enumerate(session["covers"], start=1)
    }
    contexts = []
    for target_id in target_ids:
        model = model_by_id[target_id]
        plan = plan_by_id[target_id]
        content = content_by_id[target_id]
        contexts.append(
            {
                "id": target_id,
                "title": model["title"],
                "purpose": model["context"]["purpose"],
                "coverage_requirements": [
                    item["statement"] for item in model.get("coverage_requirements", [])
                ],
                "selected_asset_types": [
                    item["asset_type"]
                    for item in plan.get("asset_plan", [])
                    if item.get("selection_status") == "selected"
                ],
                "depth_budget": deepcopy(plan.get("depth_budget", {})),
                "generated_asset_types": [
                    item.get("type")
                    for item in content.get("assets", [])
                    if isinstance(item, dict) and item.get("type")
                ],
                "current_placement": {
                    **placement_by_id[target_id],
                    "duration_minutes": plan.get("depth_budget", {}).get(
                        "target_learning_minutes"
                    ),
                },
            }
        )
    return contexts


def _lesson_sequence_operations(
    baseline: dict[str, Any],
    placements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sessions = [
        {
            "id": session["id"],
            "covers": [cover["subtopic_id"] for cover in session["covers"]],
        }
        for session in baseline["body"]["sessions"]
    ]
    operations: list[dict[str, Any]] = []
    for placement in placements:
        target_id = placement["target_id"]
        anchor_id = placement["after_subtopic_id"]
        source = next(session for session in sessions if target_id in session["covers"])
        source["covers"].remove(target_id)
        if not source["covers"]:
            sessions.remove(source)
        if anchor_id is None:
            target_session = sessions[0]
            position = 1
        else:
            target_session = next(
                session for session in sessions if anchor_id in session["covers"]
            )
            position = target_session["covers"].index(anchor_id) + 2
        target_session["covers"].insert(position - 1, target_id)
        operations.append(
            {
                "op": "move_segment",
                "target_id": target_id,
                "value": target_session["id"],
                "position": position,
            }
        )
    return operations


def _brief_schema() -> dict[str, Any]:
    text = {"type": "string", "minLength": 1, "maxLength": 500}
    text_list = {"type": "array", "maxItems": 20, "items": text}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["updates"],
        "properties": {
            "updates": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "purpose",
                    "audience",
                    "level",
                    "prior_knowledge",
                    "in_scope",
                    "out_of_scope",
                    "must_have_topics",
                    "duration",
                    "modality",
                    "language",
                ],
                "properties": {
                    "course_title": text,
                    "purpose": text,
                    "audience": text,
                    "level": text,
                    "prior_knowledge": text,
                    "in_scope": text_list,
                    "out_of_scope": text_list,
                    "must_have_topics": text_list,
                    "duration": text,
                    "modality": {
                        "type": "string",
                        "enum": ["self_paced", "live", "blended", "workshop", "custom"],
                    },
                    "language": text,
                    "jurisdiction": {
                        "anyOf": [
                            {"type": "string", "minLength": 1, "maxLength": 200},
                            {"type": "null"},
                        ]
                    },
                    "assessment_expectations": {
                        "anyOf": [
                            {"type": "string", "minLength": 1, "maxLength": 500},
                            {"type": "null"},
                        ]
                    },
                    "live_teaching_constraints": {
                        "anyOf": [text, {"type": "null"}]
                    },
                    "tools_or_equipment": {"anyOf": [text, {"type": "null"}]},
                    "freshness_requirement": {"anyOf": [text, {"type": "null"}]},
                    "accessibility_requirements": {
                        "anyOf": [text, {"type": "null"}]
                    },
                },
            }
        },
    }


def _outcome_fields() -> dict[str, Any]:
    return {
        "statement": {"type": "string", "minLength": 1, "maxLength": 300},
        "cognitive_level": {
            "type": "string",
            "enum": sorted(outcomes.COGNITIVE_LEVELS),
        },
        "evidence": {"type": "string", "minLength": 1, "maxLength": 300},
        "priority": {"type": "string", "enum": sorted(outcomes.OUTCOME_PRIORITIES)},
    }


def _outcomes_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["outcomes"],
        "properties": {
            "outcomes": {
                "type": "array",
                "minItems": 3,
                "maxItems": 8,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(_outcome_fields()),
                    "properties": _outcome_fields(),
                },
            }
        },
    }


def _outcome_revision_schema(target_ids: list[str]) -> dict[str, Any]:
    fields = {"target_id": {"type": "string", "enum": target_ids}, **_outcome_fields()}
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["outcomes"],
        "properties": {
            "outcomes": {
                "type": "array",
                "minItems": len(target_ids),
                "maxItems": len(target_ids),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(fields),
                    "properties": fields,
                },
            }
        },
    }


def _course_model_update_schema(target_ids: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["subtopics"],
        "properties": {
            "subtopics": {
                "type": "array",
                "minItems": len(target_ids),
                "maxItems": len(target_ids),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "target_id",
                        "title",
                        "purpose",
                        "in_scope",
                        "out_of_scope",
                    ],
                    "properties": {
                        "target_id": {"type": "string", "enum": target_ids},
                        "title": {"type": "string", "minLength": 1, "maxLength": 200},
                        "purpose": {"type": "string", "minLength": 1, "maxLength": 500},
                        "in_scope": {
                            "type": "array",
                            "maxItems": 20,
                            "items": {"type": "string", "minLength": 1, "maxLength": 180},
                        },
                        "out_of_scope": {
                            "type": "array",
                            "maxItems": 20,
                            "items": {"type": "string", "minLength": 1, "maxLength": 180},
                        },
                    },
                },
            }
        },
    }


def _blueprint_schema(target_ids: list[str]) -> dict[str, Any]:
    assets = sorted(blueprint_agent.ASSET_CATALOG)
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["plans"],
        "properties": {
            "plans": {
                "type": "array",
                "minItems": len(target_ids),
                "maxItems": len(target_ids),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["subtopic_id", "asset_types", "depth"],
                    "properties": {
                        "subtopic_id": {"type": "string", "enum": target_ids},
                        "asset_types": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": len(assets),
                            "uniqueItems": True,
                            "contains": {"const": "course_content"},
                            "items": {"type": "string", "enum": assets},
                        },
                        "depth": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": [
                                "level",
                                "target_learning_minutes",
                                "required_example_count",
                                "case_depth",
                                "assessment_complexity",
                            ],
                            "properties": {
                                "level": {
                                    "type": "string",
                                    "enum": [
                                        "introductory",
                                        "intermediate",
                                        "advanced",
                                        "custom",
                                    ],
                                },
                                "target_learning_minutes": {
                                    "type": "integer",
                                    "minimum": 5,
                                    "maximum": 180,
                                },
                                "required_example_count": {
                                    "type": "integer",
                                    "minimum": 0,
                                    "maximum": 12,
                                },
                                "case_depth": {
                                    "type": "string",
                                    "enum": ["none", "brief", "detailed"],
                                },
                                "assessment_complexity": {
                                    "type": "string",
                                    "enum": ["none", "recall", "application", "analysis"],
                                },
                            },
                        },
                    },
                },
            }
        },
    }


def _lesson_mode_schema(target_ids: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["modes"],
        "properties": {
            "modes": {
                "type": "array",
                "minItems": len(target_ids),
                "maxItems": len(target_ids),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["subtopic_id", "mode"],
                    "properties": {
                        "subtopic_id": {"type": "string", "enum": target_ids},
                        "mode": {"type": "string", "enum": ["live", "self_study"]},
                    },
                },
            }
        },
    }


def _lesson_sequence_schema(
    target_ids: list[str],
    all_subtopic_ids: list[str],
) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["placements"],
        "properties": {
            "placements": {
                "type": "array",
                "minItems": len(target_ids),
                "maxItems": len(target_ids),
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["target_id", "after_subtopic_id"],
                    "properties": {
                        "target_id": {"type": "string", "enum": target_ids},
                        "after_subtopic_id": {
                            "anyOf": [
                                {
                                    "type": "string",
                                    "enum": [
                                        item
                                        for item in all_subtopic_ids
                                        if item not in set(target_ids)
                                    ],
                                },
                                {"type": "null"},
                            ]
                        },
                    },
                },
            }
        },
    }
