"""Transparent advisory scoring and bounded previews for research sources."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse, urlunparse

from source_store import prepare_source_excerpt

MAX_PREVIEW_CHARS = 4_000
MAX_PREVIEW_SECTIONS = 4
MAX_SECTION_CHARS = 1_200

_STOPWORDS = frozenset(
    {
        "about",
        "after",
        "against",
        "also",
        "and",
        "are",
        "before",
        "between",
        "course",
        "evidence",
        "for",
        "from",
        "guide",
        "into",
        "missing",
        "page",
        "source",
        "that",
        "the",
        "their",
        "this",
        "through",
        "using",
        "with",
    }
)


def normalize_known_source_locator(locator: str) -> str:
    """Return a safe normalized HTTP(S) locator for a human-supplied source."""
    raw = locator.strip()
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("known sources require an absolute http or https URL")
    if parsed.username or parsed.password:
        raise ValueError("known source URLs must not contain credentials")
    if len(raw) > 1_000:
        raise ValueError("known source URL is too long")
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path or "/",
            parsed.params,
            parsed.query,
            "",
        )
    )


def known_source_candidate(
    locator: str,
    *,
    title: str | None = None,
    publisher: str | None = None,
    trust_notes: str | None = None,
    relevance: str | None = None,
) -> dict[str, Any]:
    """Build one proposed candidate without fetching or approving its body."""
    normalized = normalize_known_source_locator(locator)
    parsed = urlparse(normalized)
    path_label = parsed.path.strip("/").split("/")[-1].replace("-", " ").replace("_", " ")
    source_id = f"known_{hashlib.sha256(normalized.encode()).hexdigest()[:12]}"
    return {
        "id": source_id,
        "title": _required_or_default(title, (path_label or parsed.netloc).title(), "title", 300),
        "publisher": _required_or_default(
            publisher,
            parsed.netloc.removeprefix("www."),
            "publisher",
            200,
        ),
        "source_type": "known web source",
        "locator": normalized,
        "content_ref": None,
        "status": "proposed",
        "trust_notes": _required_or_default(
            trust_notes,
            "Human-provided URL; authority and content remain advisory until reviewed.",
            "trust notes",
            500,
        ),
        "relevance": _required_or_default(
            relevance,
            "Added by the course director for consideration at the normal source checkpoint.",
            "relevance",
            500,
        ),
        "assigned_node_ids": [],
        "decision_rationale": None,
    }


def project_source_quality(
    candidate: dict[str, Any],
    *,
    evidence_needs: list[str] | tuple[str, ...] = (),
    content: str | None = None,
    fetch_reason: str | None = None,
) -> dict[str, Any]:
    """Return advisory scoring, bounded preview sections, and need coverage."""
    text = " ".join(
        str(candidate.get(key) or "")
        for key in ("title", "publisher", "source_type", "locator", "trust_notes", "relevance")
    )
    sections = capture_relevant_sections(content or "", evidence_needs=evidence_needs)
    preview_text = " ".join(section["text"] for section in sections)
    combined = f"{text} {preview_text}".strip()
    dimensions = {
        "authority": _authority_score(candidate),
        "fit": _fit_score(combined, evidence_needs),
        "specificity": _specificity_score(candidate, preview_text),
        "freshness": _freshness_score(combined),
        "fetch_status": _fetch_score(content, fetch_reason),
        "content_availability": _availability_score(content),
    }
    overall = round(
        sum(item["score"] for item in dimensions.values()) / len(dimensions),
        1,
    )
    coverage = [_coverage_row(need, combined) for need in evidence_needs if need.strip()]
    recommendation = (
        "strong_candidate"
        if overall >= 4
        else "review_candidate"
        if overall >= 2.5
        else "weak_candidate"
    )
    return {
        "overall": overall,
        "recommendation": recommendation,
        "advisory_only": True,
        "dimensions": {
            key: {"score": value["score"], "reason": value["reason"]}
            for key, value in dimensions.items()
        },
        "preview_sections": sections,
        "coverage": coverage,
        "fetch_reason": fetch_reason,
    }


def capture_relevant_sections(
    content: str,
    *,
    evidence_needs: list[str] | tuple[str, ...] = (),
    max_sections: int = MAX_PREVIEW_SECTIONS,
    max_chars: int = MAX_PREVIEW_CHARS,
) -> list[dict[str, Any]]:
    """Select relevant bounded passages while preserving excerpt-size guardrails."""
    if max_sections < 1 or max_chars < 1:
        raise ValueError("preview bounds must be positive")
    normalized = prepare_source_excerpt(content, max_chars=max(max_chars * 4, max_chars))
    if not normalized:
        return []
    needs_tokens = _tokens(" ".join(evidence_needs))
    raw_sections = [item.strip() for item in re.split(r"\n\s*\n+", normalized) if item.strip()]
    if len(raw_sections) == 1:
        raw_sections = [
            item.strip()
            for item in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9#])", normalized)
            if item.strip()
        ]
    ranked: list[tuple[int, int, str, list[str]]] = []
    for index, raw in enumerate(raw_sections):
        section = raw[:MAX_SECTION_CHARS].rstrip()
        matched = sorted(_tokens(section) & needs_tokens)
        score = len(matched)
        ranked.append((score, -index, section, matched))
    ranked.sort(reverse=True)
    selected = ranked[:max_sections]
    if not needs_tokens:
        selected = sorted(ranked, key=lambda item: -item[1])[:max_sections]
    result: list[dict[str, Any]] = []
    remaining = max_chars
    for score, negative_index, section, matched in selected:
        if remaining <= 0:
            break
        bounded = section[:remaining].rstrip()
        if not bounded:
            continue
        result.append(
            {
                "order": -negative_index + 1,
                "text": bounded,
                "matched_terms": matched,
                "relevance_score": score,
            }
        )
        remaining -= len(bounded)
    return result


def _authority_score(candidate: dict[str, Any]) -> dict[str, Any]:
    text = " ".join(
        str(candidate.get(key) or "").lower()
        for key in ("publisher", "source_type", "locator", "trust_notes")
    )
    if any(marker in text for marker in ("anonymous", "unknown", "unattributed")):
        return {"score": 1, "reason": "Authorship or institutional responsibility is unclear."}
    if any(
        marker in text
        for marker in (
            ".gov",
            ".edu",
            "government",
            "university",
            "standards body",
            "official",
            "association",
            "institute",
        )
    ):
        return {"score": 5, "reason": "Institutional or primary-source signals are present."}
    return {"score": 3, "reason": "Authority is plausible but requires human verification."}


def _fit_score(text: str, evidence_needs: list[str] | tuple[str, ...]) -> dict[str, Any]:
    if not evidence_needs:
        return {"score": 3, "reason": "No explicit evidence gap was supplied for fit scoring."}
    rows = [_coverage_row(need, text) for need in evidence_needs if need.strip()]
    score = round(sum(row["score"] for row in rows) / len(rows)) if rows else 0
    return {
        "score": score,
        "reason": (
            "Matched terms across "
            f"{sum(bool(row['matched_terms']) for row in rows)} of {len(rows)} "
            "stated evidence needs."
        ),
    }


def _specificity_score(candidate: dict[str, Any], preview_text: str) -> dict[str, Any]:
    text = f"{candidate.get('title', '')} {candidate.get('source_type', '')}".lower()
    if any(marker in text for marker in ("index", "overview", "home page", "portal")):
        return {"score": 2, "reason": "The candidate appears broad or index-like."}
    if len(preview_text) >= 500:
        return {"score": 5, "reason": "The captured text contains a substantive focused passage."}
    if preview_text:
        return {"score": 4, "reason": "A focused extractable passage is available."}
    return {"score": 3, "reason": "Specificity is based on metadata until content is captured."}


def _freshness_score(text: str) -> dict[str, Any]:
    years = [int(value) for value in re.findall(r"\b(?:19|20)\d{2}\b", text)]
    if not years:
        return {"score": 3, "reason": "No publication or update year is visible."}
    age = datetime.now(UTC).year - max(years)
    if age <= 2:
        return {"score": 5, "reason": "A date within the last two years is visible."}
    if age <= 5:
        return {"score": 4, "reason": "A date within the last five years is visible."}
    if age <= 10:
        return {"score": 3, "reason": "The newest visible date is six to ten years old."}
    return {"score": 1, "reason": "The visible date is more than ten years old."}


def _fetch_score(content: str | None, fetch_reason: str | None) -> dict[str, Any]:
    if content and content.strip():
        return {"score": 5, "reason": "The source was fetched successfully."}
    if fetch_reason:
        return {"score": 0, "reason": f"Fetch failed: {fetch_reason}"}
    return {"score": 2, "reason": "The source has not been fetched yet."}


def _availability_score(content: str | None) -> dict[str, Any]:
    if content and content.strip():
        return {"score": 5, "reason": "Extractable content is available for bounded preview."}
    return {"score": 0, "reason": "No extractable source content is currently available."}


def _coverage_row(need: str, text: str) -> dict[str, Any]:
    need_tokens = _tokens(need)
    matched = sorted(need_tokens & _tokens(text))
    ratio = len(matched) / max(1, len(need_tokens))
    score = (
        5 if ratio >= 0.75 else 4 if ratio >= 0.5 else 3 if ratio >= 0.3 else 1 if matched else 0
    )
    return {"need": need.strip(), "score": score, "matched_terms": matched}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) > 2 and token not in _STOPWORDS
    }


def _required_or_default(
    value: str | None,
    default: str,
    label: str,
    max_length: int,
) -> str:
    normalized = value.strip() if value is not None else default.strip()
    if not normalized:
        raise ValueError(f"known source {label} cannot be blank")
    if len(normalized) > max_length:
        raise ValueError(f"known source {label} is too long")
    return normalized
