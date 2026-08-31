"""Research assembly for Sprint 2 Course Builder planning."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from competitor_analysis import build_competitor_analysis, competitor_finding_from_outline
from orchestrator import make_artifact
from research_adapter import ResearchProvider, SearchResult

DESIGN_SCHEMA_VERSION = "0.2"
DEFAULT_COMPETITOR_LIMIT = 8
DEFAULT_SOURCE_LIMIT = 8
MIN_USABLE_OUTLINES = 3


@dataclass(frozen=True)
class ManualSource:
    """Human-supplied factual source candidate metadata."""

    id: str
    title: str
    publisher: str
    locator: str
    trust_notes: str
    relevance: str
    source_type: str = "manual web source"


@dataclass(frozen=True)
class ResearchConfig:
    competitor_limit: int = DEFAULT_COMPETITOR_LIMIT
    source_limit: int = DEFAULT_SOURCE_LIMIT
    min_usable_outlines: int = MIN_USABLE_OUTLINES


DEFAULT_RESEARCH_CONFIG = ResearchConfig()


def build_research_dossier_artifact(
    brief: dict,
    course_outcomes: dict,
    *,
    provider: ResearchProvider,
    manual_sources: Iterable[ManualSource | dict[str, Any]] = (),
    config: ResearchConfig = DEFAULT_RESEARCH_CONFIG,
) -> dict:
    body = build_research_dossier_body(
        brief,
        course_outcomes,
        provider=provider,
        manual_sources=manual_sources,
        config=config,
    )
    return make_artifact(
        brief["course_id"],
        "research_dossier",
        "research",
        body=body,
        inputs=["brief", "course_outcomes"],
        schema_version=DESIGN_SCHEMA_VERSION,
    )


def build_research_dossier_body(
    brief: dict,
    course_outcomes: dict,
    *,
    provider: ResearchProvider,
    manual_sources: Iterable[ManualSource | dict[str, Any]] = (),
    config: ResearchConfig = DEFAULT_RESEARCH_CONFIG,
) -> dict:
    """Build a research dossier without embedding factual source bodies."""
    subject = brief["body"]["subject"]
    outcome_ids = [outcome["id"] for outcome in course_outcomes["body"]["outcomes"]]

    competitor_findings, source_failures = scan_competitors(
        subject,
        provider=provider,
        config=config,
    )
    usable_count = sum(
        1
        for finding in competitor_findings
        if finding.get("outline_status") in {"usable", "partial"}
        and finding.get("outline_sections")
    )
    if usable_count < config.min_usable_outlines:
        raise ValueError(
            "competitor scan requires at least "
            f"{config.min_usable_outlines} usable outlines; found {usable_count}"
        )

    analysis = build_competitor_analysis(competitor_findings, outcome_ids)
    source_candidates, source_gaps = propose_source_candidates(
        subject,
        provider=provider,
        manual_sources=manual_sources,
        limit=config.source_limit,
    )

    return {
        "research_scope": (
            f"Bounded competitor and factual-source research for {subject}; "
            "competitor outlines inform structure, while only approved factual "
            "sources may ground learner content."
        ),
        "competitor_findings": competitor_findings,
        **analysis,
        "source_candidates": source_candidates,
        "source_failures": source_failures + source_gaps,
    }


def scan_competitors(
    subject: str,
    *,
    provider: ResearchProvider,
    config: ResearchConfig = DEFAULT_RESEARCH_CONFIG,
) -> tuple[list[dict], list[dict]]:
    query = f"{subject} course outline beginner curriculum"
    results = provider.search(query, limit=config.competitor_limit)
    findings: list[dict] = []
    failures: list[dict] = []
    for result in results:
        outline = provider.extract_competitor_outline(result)
        finding = competitor_finding_from_outline(outline)
        findings.append(finding)
        if outline.outline_status not in {"usable", "partial"}:
            failures.append(
                {
                    "id": f"sf_{_stable_id(result.id)}",
                    "title": result.title,
                    "locator": result.locator,
                    "reason": "The page did not expose a usable public course outline.",
                }
            )
    return findings, failures


def propose_source_candidates(
    subject: str,
    *,
    provider: ResearchProvider,
    manual_sources: Iterable[ManualSource | dict[str, Any]] = (),
    limit: int = DEFAULT_SOURCE_LIMIT,
) -> tuple[list[dict], list[dict]]:
    """Propose auditable source metadata; do not fetch or persist bodies yet."""
    query = f"{subject} factual guide reference evidence"
    results = provider.search(query, limit=limit)
    candidates: list[dict] = []
    seen: set[str] = set()
    for result in results:
        if _looks_like_competitor(result):
            continue
        source_id = _stable_id(result.id, prefix="src")
        if source_id in seen:
            continue
        seen.add(source_id)
        candidates.append(_candidate_from_result(result, source_id=source_id))

    for manual in manual_sources:
        candidate = _candidate_from_manual(manual)
        if candidate["id"] in seen:
            continue
        seen.add(candidate["id"])
        candidates.append(candidate)

    failures: list[dict] = []
    if not candidates:
        failures.append(
            {
                "id": "sf_no_candidate_sources",
                "title": "Candidate factual-source search",
                "locator": None,
                "reason": (
                    "No auditable candidate factual sources were found in the bounded search."
                ),
            }
        )
    return candidates, failures


def _candidate_from_result(result: SearchResult, *, source_id: str) -> dict:
    status = "rejected" if _looks_untrustworthy(result) else "proposed"
    rationale = (
        "Rejected before ingestion because authorship or scope looked weak."
        if status == "rejected"
        else None
    )
    return {
        "id": source_id,
        "title": result.title,
        "publisher": _publisher_from_locator(result.locator),
        "source_type": "web page",
        "locator": result.locator,
        "content_ref": None,
        "status": status,
        "trust_notes": _trust_notes(result),
        "relevance": _relevance_notes(result),
        "assigned_node_ids": [],
        "decision_rationale": rationale,
    }


def _candidate_from_manual(source: ManualSource | dict[str, Any]) -> dict:
    if isinstance(source, ManualSource):
        raw = source.__dict__
    else:
        raw = source
    required = {"id", "title", "publisher", "locator", "trust_notes", "relevance"}
    missing = sorted(required - raw.keys())
    if missing:
        raise ValueError(f"manual source is missing required fields: {missing}")
    return {
        "id": _stable_id(str(raw["id"]), prefix="manual"),
        "title": str(raw["title"]),
        "publisher": str(raw["publisher"]),
        "source_type": str(raw.get("source_type", "manual web source")),
        "locator": str(raw["locator"]),
        "content_ref": None,
        "status": "proposed",
        "trust_notes": str(raw["trust_notes"]),
        "relevance": str(raw["relevance"]),
        "assigned_node_ids": [],
        "decision_rationale": None,
    }


def _looks_like_competitor(result: SearchResult) -> bool:
    haystack = f"{result.id} {result.title} {result.snippet}".lower()
    return result.id.startswith("comp_") or any(
        marker in haystack for marker in ("course outline", "curriculum", "class", "workshop")
    )


def _looks_untrustworthy(result: SearchResult) -> bool:
    haystack = f"{result.title} {result.snippet} {result.locator}".lower()
    return any(marker in haystack for marker in ("anonymous", "hack", "unknown", "unattributed"))


def _trust_notes(result: SearchResult) -> str:
    if _looks_untrustworthy(result):
        return "Authorship, publication quality, or evidence trail is unclear."
    return (
        "Candidate discovered through bounded search; human approval is required "
        "before fetching and storing source text."
    )


def _relevance_notes(result: SearchResult) -> str:
    """Report what the search page said about this candidate.

    The Brief's own scope is deliberately not echoed here. Relevance is scored
    against stated evidence needs, so interpolating those needs into the text
    being scored would make every candidate confirm itself.
    """
    if result.snippet:
        return f"Search snippet: {result.snippet}"
    return "No search snippet was available; relevance is unverified until the source is fetched."


def _publisher_from_locator(locator: str) -> str:
    host = re.sub(r"^www\.", "", locator.split("//", 1)[-1].split("/", 1)[0])
    return host or "Unknown publisher"


def _stable_id(value: str, *, prefix: str = "id") -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    slug = re.sub(r"_+", "_", slug)
    if not slug:
        slug = prefix
    if not re.match(r"^[a-z0-9]", slug):
        slug = f"{prefix}_{slug}"
    return slug
