"""Competitor outline extraction and normalization helpers."""

from __future__ import annotations

import re
from collections import defaultdict

from research_adapter import CompetitorOutline

SYNONYMS = {
    "grind adjustment": "grind size",
    "water and recipe control": "brew ratio",
    "troubleshooting taste": "tasting and adjustment",
    "extraction basics": "extraction",
}


def normalize_topic_label(label: str) -> tuple[str, str]:
    normalized = re.sub(r"[^a-z0-9]+", " ", label.lower()).strip()
    canonical = SYNONYMS.get(normalized, normalized)
    topic_id = "nt_" + re.sub(r"[^a-z0-9]+", "_", canonical).strip("_")
    return topic_id, canonical.title()


def competitor_finding_from_outline(outline: CompetitorOutline) -> dict:
    sections = []
    normalized_ids: list[str] = []
    for index, label in enumerate(outline.outline_labels, start=1):
        topic_id, _ = normalize_topic_label(label)
        normalized_ids.append(topic_id)
        sections.append(
            {
                "id": f"{outline.id}_sec{index}",
                "order": index,
                "raw_label": label,
                "normalized_topic_id": topic_id,
                "locator": outline.locator,
                "parent_label": outline.offering,
            }
        )
    return {
        "id": outline.id,
        "provider": outline.provider,
        "offering": outline.offering,
        "locator": outline.locator,
        "audience": outline.audience,
        "level": outline.level,
        "duration": outline.duration,
        "delivery_format": outline.delivery_format,
        "assessment_approach": outline.assessment_approach,
        "outline_status": outline.outline_status,
        "outline_sections": sections,
        "normalized_topic_ids": _dedupe(normalized_ids),
        "structure_summary": _structure_summary(outline),
        "notable_topics": list(outline.outline_labels[:5]),
        "differentiation_opportunity": (
            "Use the competitor common core as evidence, then tune scope to the approved brief."
        ),
    }


def build_competitor_analysis(findings: list[dict], outcome_ids: list[str]) -> dict:
    topic_aliases: dict[str, set[str]] = defaultdict(set)
    coverage: dict[str, set[str]] = defaultdict(set)
    usable_competitor_ids = {
        finding["id"]
        for finding in findings
        if finding.get("outline_status") in {"usable", "partial"}
    }
    for finding in findings:
        for section in finding.get("outline_sections", []):
            topic_id = section["normalized_topic_id"]
            _, label = normalize_topic_label(section["raw_label"])
            topic_aliases[topic_id].add(section["raw_label"])
            topic_aliases[topic_id].add(label)
            coverage[topic_id].add(finding["id"])

    normalized_topics = [
        {
            "id": topic_id,
            "label": sorted(aliases, key=len)[0],
            "aliases": sorted(aliases),
        }
        for topic_id, aliases in sorted(topic_aliases.items())
    ]
    coverage_matrix = [
        {
            "normalized_topic_id": topic_id,
            "competitor_course_ids": sorted(course_ids),
        }
        for topic_id, course_ids in sorted(coverage.items())
    ]
    common_core = [
        topic_id
        for topic_id, course_ids in sorted(coverage.items())
        if usable_competitor_ids and usable_competitor_ids.issubset(course_ids)
    ]
    sequence_ids = sorted(usable_competitor_ids)
    return {
        "normalized_topics": normalized_topics,
        "coverage_matrix": coverage_matrix,
        "common_core_topic_ids": common_core,
        "sequence_observations": [
            {
                "statement": (
                    "Usable outlines introduce fundamentals before troubleshooting "
                    "or specialized applications."
                ),
                "evidence_competitor_ids": sequence_ids,
            }
        ]
        if sequence_ids
        else [],
        "gap_observations": [
            {
                "statement": (
                    "Competitor outlines do not by themselves approve factual grounding sources."
                ),
                "evidence_competitor_ids": sequence_ids,
            }
        ]
        if sequence_ids
        else [],
        "structural_implications": [
            {
                "id": "si1",
                "implication": (
                    "Start with the shared common-core topics, then add "
                    "differentiators only when the brief requires them."
                ),
                "rationale": (
                    "Frequency is useful evidence but must remain subordinate "
                    "to approved intent and outcomes."
                ),
                "related_outcome_ids": outcome_ids,
                "related_topic_ids": common_core,
            }
        ],
    }


def _structure_summary(outline: CompetitorOutline) -> str:
    if not outline.outline_labels:
        if outline.outline_status == "no_outline_found":
            return "The page was retrieved, but no course outline could be parsed from it."
        return "The page could not be retrieved."
    first = outline.outline_labels[0]
    last = outline.outline_labels[-1]
    return (
        f"Moves from {first} toward {last} across {len(outline.outline_labels)} visible sections."
    )


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
