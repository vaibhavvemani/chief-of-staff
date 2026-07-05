"""Deterministic Course Model generation for Sprint 2."""

from __future__ import annotations

import re
from typing import Any

from competitor_analysis import normalize_topic_label
from orchestrator import make_artifact
from source_selection import approved_source_registry as registry_from_research

DESIGN_SCHEMA_VERSION = "0.2"
TARGET_SUBTOPIC_MIN = 4
TARGET_SUBTOPIC_MAX = 8


def build_course_model_artifact(
    brief: dict,
    course_outcomes: dict,
    research_dossier: dict,
    approved_source_registry: dict | None = None,
) -> dict:
    body = build_course_model_body(
        brief,
        course_outcomes,
        research_dossier,
        approved_source_registry=approved_source_registry,
    )
    inputs = ["brief", "course_outcomes", "research_dossier"]
    if approved_source_registry is not None:
        inputs.append("approved_source_registry")
    return make_artifact(
        brief["course_id"],
        "course_model",
        "structure",
        body=body,
        inputs=inputs,
        schema_version=DESIGN_SCHEMA_VERSION,
    )


def build_course_model_body(
    brief: dict,
    course_outcomes: dict,
    research_dossier: dict,
    *,
    approved_source_registry: dict | None = None,
) -> dict:
    sources = _resolve_source_registry(research_dossier, approved_source_registry)
    if not sources:
        raise ValueError("Course Model generation requires at least one approved source")

    body = brief["body"]
    outcomes = course_outcomes["body"]["outcomes"]
    topics = _select_topics(body, research_dossier["body"])
    modules = _build_modules(body, topics, sources)
    topic_ids = [topic["id"] for topic in topics]
    research_topic_ids = {
        topic["id"] for topic in research_dossier["body"].get("normalized_topics", [])
    }
    rationale_topic_ids = [topic_id for topic_id in topic_ids if topic_id in research_topic_ids]
    outcome_ids = [outcome["id"] for outcome in outcomes]

    return {
        "course_metadata": {
            "course_title": body["course_title"],
            "subject": body["subject"],
            "audience_summary": body["audience"],
            "level": _normalize_level(body.get("level")),
            "language": body["language"],
            "jurisdiction": body.get("jurisdiction"),
            "course_outcome_ids": outcome_ids,
        },
        "structural_rationale": [
            {
                "id": "sr1",
                "statement": (
                    "The first structure pass follows the common competitor core, "
                    "then adds brief-specific practice and troubleshooting scope."
                ),
                "evidence_artifact_refs": [
                    "research_dossier.common_core_topic_ids",
                    "brief.in_scope",
                    "brief.must_have_topics",
                ],
                "related_outcome_ids": outcome_ids,
                "related_topic_ids": rationale_topic_ids,
            }
        ],
        "modules": modules,
        "source_registry": sources,
    }


def _resolve_source_registry(
    research_dossier: dict,
    approved_source_registry: dict | None,
) -> list[dict]:
    if approved_source_registry is not None:
        registry = approved_source_registry.get("body", {}).get("source_registry", [])
    else:
        registry = registry_from_research(research_dossier)
    result = []
    for source in registry:
        if not source.get("content_ref"):
            continue
        result.append(
            {
                "id": source["id"],
                "title": source["title"],
                "publisher": source["publisher"],
                "source_type": source["source_type"],
                "locator": source.get("locator"),
                "content_ref": source["content_ref"],
            }
        )
    return result


def _select_topics(brief_body: dict, research_body: dict) -> list[dict]:
    topic_lookup = {
        topic["id"]: topic["label"] for topic in research_body.get("normalized_topics", [])
    }
    selected: list[tuple[str, str]] = []

    for topic_id in research_body.get("common_core_topic_ids", []):
        if topic_id in topic_lookup:
            selected.append((topic_id, topic_lookup[topic_id]))
    for implication in research_body.get("structural_implications", []):
        for topic_id in implication.get("related_topic_ids", []):
            if topic_id in topic_lookup:
                selected.append((topic_id, topic_lookup[topic_id]))

    brief_topics = list(brief_body.get("in_scope", [])) + list(
        brief_body.get("must_have_topics", [])
    )
    for label in brief_topics:
        topic_id, normalized_label = normalize_topic_label(label)
        selected.append((topic_id, normalized_label))

    out_of_scope = " ".join(brief_body.get("out_of_scope", [])).lower()
    filtered: list[dict] = []
    seen: set[str] = set()
    for topic_id, label in selected:
        if topic_id in seen:
            continue
        if _topic_excluded(label, out_of_scope):
            continue
        seen.add(topic_id)
        filtered.append({"id": topic_id, "label": _humanize_topic(label)})

    while len(filtered) < TARGET_SUBTOPIC_MIN:
        index = len(filtered) + 1
        fallback_label = _fallback_topic_label(index, brief_body["subject"])
        topic_id, label = normalize_topic_label(fallback_label)
        if topic_id not in seen:
            seen.add(topic_id)
            filtered.append({"id": topic_id, "label": label})
    return filtered[:TARGET_SUBTOPIC_MAX]


def _build_modules(brief_body: dict, topics: list[dict], sources: list[dict]) -> list[dict]:
    modules: list[dict] = []
    chunks = [topics[:4]]
    if len(topics) > 4:
        chunks.append(topics[4:])

    previous_module_id: str | None = None
    previous_subtopic_id: str | None = None
    for module_index, chunk in enumerate(chunks, start=1):
        module_id = f"m{module_index}"
        module_title = (
            f"{brief_body['subject']} Foundations"
            if module_index == 1
            else f"{brief_body['subject']} Practice and Extension"
        )
        subtopics = []
        for subtopic_index, topic in enumerate(chunk, start=1):
            subtopic_id = f"{module_id}_s{subtopic_index}"
            assigned_sources = _sources_for_topic(topic["label"], sources)
            concept_id = f"c_{subtopic_id}_1"
            coverage_id = f"cr_{subtopic_id}_1"
            subtopics.append(
                {
                    "id": subtopic_id,
                    "order": subtopic_index,
                    "title": topic["label"],
                    "context": {
                        "purpose": _purpose_for_topic(topic["label"], brief_body),
                        "in_scope": [topic["label"], *brief_body.get("must_have_topics", [])[:2]],
                        "out_of_scope": brief_body.get("out_of_scope", [])[:3],
                    },
                    "prerequisite_subtopic_ids": [previous_subtopic_id]
                    if previous_subtopic_id
                    else [],
                    "concepts": [
                        {
                            "id": concept_id,
                            "name": topic["label"],
                            "summary": (
                                f"Core decisions and vocabulary learners need for "
                                f"{topic['label'].lower()}."
                            ),
                            "depends_on": [],
                            "source_ids": [source["id"] for source in assigned_sources],
                        }
                    ],
                    "coverage_requirements": [
                        {
                            "id": coverage_id,
                            "statement": (
                                f"Explain {topic['label'].lower()} and connect it to "
                                "a practical learner decision."
                            ),
                            "concept_ids": [concept_id],
                            "source_ids": [source["id"] for source in assigned_sources],
                        }
                    ],
                    "approved_source_ids": [source["id"] for source in assigned_sources],
                }
            )
            previous_subtopic_id = subtopic_id
        modules.append(
            {
                "id": module_id,
                "order": module_index,
                "title": module_title,
                "context": {
                    "purpose": _module_purpose(module_index, brief_body),
                    "in_scope": brief_body.get("in_scope", [])[:4],
                    "out_of_scope": brief_body.get("out_of_scope", [])[:3],
                },
                "prerequisite_module_ids": [previous_module_id] if previous_module_id else [],
                "subtopics": subtopics,
            }
        )
        previous_module_id = module_id
    return modules


def _sources_for_topic(topic_label: str, sources: list[dict]) -> list[dict]:
    topic_tokens = _tokens(topic_label)
    matched = [
        source
        for source in sources
        if topic_tokens
        & _tokens(
            f"{source.get('title', '')} "
            f"{source.get('publisher', '')} "
            f"{source.get('source_type', '')}"
        )
    ]
    if matched:
        return matched
    return sources[:1]


def _topic_excluded(label: str, out_of_scope: str) -> bool:
    label_tokens = _tokens(label)
    excluded_tokens = _tokens(out_of_scope)
    return bool(label_tokens and label_tokens <= excluded_tokens)


def _module_purpose(module_index: int, brief_body: dict) -> str:
    if module_index == 1:
        return (
            f"Build the shared foundations needed to achieve: "
            f"{brief_body.get('purpose', brief_body['subject'])}"
        )[:500]
    return "Extend the foundations into practice, diagnosis, and learner transfer."


def _purpose_for_topic(topic_label: str, brief_body: dict) -> str:
    return (f"Teach {topic_label.lower()} within the approved scope for {brief_body['audience']}.")[
        :500
    ]


def _fallback_topic_label(index: int, subject: str) -> str:
    labels = [
        f"{subject} foundations",
        f"{subject} workflow",
        f"{subject} practice",
        f"{subject} troubleshooting",
    ]
    return labels[(index - 1) % len(labels)]


def _normalize_level(level: Any) -> str:
    if not level:
        return "beginner"
    text = str(level).strip().lower()
    if text == "introductory":
        return "beginner"
    return text


def _humanize_topic(label: str) -> str:
    text = str(label).strip()
    if not text:
        return "Foundations"
    return text[:1].upper() + text[1:]


def _tokens(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", value.lower()) if token}
