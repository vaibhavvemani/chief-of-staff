"""Research adapter interfaces and mock provider for Sprint 1."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SearchResult:
    id: str
    title: str
    locator: str
    snippet: str


@dataclass(frozen=True)
class FetchResult:
    locator: str
    ok: bool
    content: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class CompetitorOutline:
    id: str
    provider: str
    offering: str
    locator: str | None
    audience: str
    level: str
    duration: str | None
    delivery_format: str | None
    assessment_approach: str | None
    outline_status: str
    outline_labels: tuple[str, ...]


class ResearchProvider(Protocol):
    def search(self, query: str, *, limit: int) -> list[SearchResult]: ...

    def fetch(self, locator: str) -> FetchResult: ...

    def extract_competitor_outline(self, result: SearchResult) -> CompetitorOutline: ...


class MockResearchProvider:
    """Fixture-backed provider with explicit success and failure results."""

    def __init__(
        self,
        *,
        search_results: list[SearchResult],
        pages: dict[str, str],
        outlines: dict[str, CompetitorOutline],
    ) -> None:
        self._search_results = search_results
        self._pages = pages
        self._outlines = outlines

    def search(self, query: str, *, limit: int) -> list[SearchResult]:
        terms = _tokens(query)
        ranked = [
            result
            for result in self._search_results
            if terms & (_tokens(result.title) | _tokens(result.snippet))
        ]
        if not ranked:
            ranked = list(self._search_results)
        return ranked[:limit]

    def fetch(self, locator: str) -> FetchResult:
        if locator not in self._pages:
            return FetchResult(
                locator=locator,
                ok=False,
                reason="mock provider has no accessible content for this locator",
            )
        return FetchResult(locator=locator, ok=True, content=self._pages[locator])

    def extract_competitor_outline(self, result: SearchResult) -> CompetitorOutline:
        if result.id not in self._outlines:
            return CompetitorOutline(
                id=result.id,
                provider="Unknown",
                offering=result.title,
                locator=result.locator,
                audience="Unknown from accessible page.",
                level="unknown",
                duration=None,
                delivery_format=None,
                assessment_approach=None,
                outline_status="inaccessible",
                outline_labels=(),
            )
        return self._outlines[result.id]


def coffee_mock_provider() -> MockResearchProvider:
    """A small non-FRM provider used by Sprint 1 tests and demos."""
    results = [
        SearchResult(
            id="comp_homebrew",
            title="Home Coffee Brewing Basics",
            locator="https://example.test/home-coffee",
            snippet="Beginner course covering beans, grind, water, ratio, and brewing.",
        ),
        SearchResult(
            id="comp_barista",
            title="Barista Fundamentals",
            locator="https://example.test/barista",
            snippet="Coffee beginner outline for extraction, milk texture, workflow, and tasting.",
        ),
        SearchResult(
            id="comp_locked",
            title="Professional Cafe Course",
            locator="https://example.test/locked",
            snippet="Outline is behind a login.",
        ),
    ]
    outlines = {
        "comp_homebrew": CompetitorOutline(
            id="comp_homebrew",
            provider="Example Learning",
            offering="Home Coffee Brewing Basics",
            locator="https://example.test/home-coffee",
            audience="Home brewers and beginners.",
            level="beginner",
            duration="2 hours",
            delivery_format="self-paced",
            assessment_approach="short quizzes",
            outline_status="usable",
            outline_labels=(
                "Coffee beans and freshness",
                "Grind size",
                "Water temperature",
                "Brew ratio",
                "Tasting and adjustment",
            ),
        ),
        "comp_barista": CompetitorOutline(
            id="comp_barista",
            provider="Example Academy",
            offering="Barista Fundamentals",
            locator="https://example.test/barista",
            audience="New baristas and serious home brewers.",
            level="beginner to intermediate",
            duration="1 day",
            delivery_format="workshop",
            assessment_approach="practical demonstration",
            outline_status="usable",
            outline_labels=(
                "Extraction basics",
                "Grind adjustment",
                "Water and recipe control",
                "Milk texture",
                "Troubleshooting taste",
            ),
        ),
    }
    pages = {
        "https://example.test/home-coffee": "Beans, grind, water temperature, ratio, tasting.",
        "https://example.test/barista": "Extraction, milk, workflow, troubleshooting.",
    }
    return MockResearchProvider(search_results=results, pages=pages, outlines=outlines)


def _tokens(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", value.lower()) if token}
