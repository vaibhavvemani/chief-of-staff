"""Research adapter interfaces, live provider, and mock providers."""

from __future__ import annotations

import hashlib
import html
import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from io import BytesIO
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, quote_plus, urljoin, urlparse
from urllib.request import Request, urlopen


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
    content_type: str | None = None
    status_code: int | None = None


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


class BoundedLiveResearchProvider:
    """Small live web provider with bounded search/fetch behavior.

    The provider intentionally stays behind the Sprint 1 adapter protocol. It
    can use a DuckDuckGo HTML search page by default, or a custom
    ``search_url_template`` in environments that proxy search. Tests can inject
    ``fetch_bytes`` to avoid network access while still exercising retry and
    parsing behavior.
    """

    def __init__(
        self,
        *,
        search_url_template: str = "https://lite.duckduckgo.com/lite/?q={query}",
        user_agent: str = "CourseBuilderPrototype/0.2",
        timeout_s: float = 8.0,
        max_retries: int = 2,
        retry_backoff_s: float = 0.25,
        max_bytes: int = 2_000_000,
        fetch_bytes: FetchBytes | None = None,
    ) -> None:
        self.search_url_template = search_url_template
        self.user_agent = user_agent
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.retry_backoff_s = retry_backoff_s
        self.max_bytes = max_bytes
        self._fetch_bytes = fetch_bytes or self._urlopen_fetch

    def search(self, query: str, *, limit: int) -> list[SearchResult]:
        if limit < 1:
            return []
        locator = self.search_url_template.format(query=quote_plus(query))
        for attempt in range(self.max_retries + 1):
            try:
                status_code, headers, payload = self._fetch_bytes(locator)
                if status_code == 429 or status_code >= 500:
                    if attempt == self.max_retries:
                        return []
                    time.sleep(self.retry_backoff_s * (attempt + 1))
                    continue
                break
            except (HTTPError, URLError, TimeoutError, OSError):
                if attempt == self.max_retries:
                    return []
                time.sleep(self.retry_backoff_s * (attempt + 1))
        if status_code >= 400:
            return []
        content_type = headers.get("content-type", headers.get("Content-Type", ""))
        raw_html = _decode_bytes(payload, content_type)

        links = _extract_links(raw_html, base_url=locator)
        results: list[SearchResult] = []
        seen: set[str] = set()
        for href, label in links:
            normalized = _normalize_http_locator(_unwrap_result_href(href))
            if normalized is None or normalized in seen:
                continue
            if _is_search_engine_url(normalized):
                continue
            seen.add(normalized)
            title = _squash_ws(label)
            if not title:
                continue
            results.append(
                SearchResult(
                    id=_live_result_id(normalized),
                    title=title[:180],
                    locator=normalized,
                    snippet=f"Live search result for: {query}",
                )
            )
            if len(results) >= limit:
                break
        return results

    def fetch(self, locator: str) -> FetchResult:
        return self._fetch(locator)

    def extract_competitor_outline(self, result: SearchResult) -> CompetitorOutline:
        fetched = self.fetch(result.locator)
        if not fetched.ok or not fetched.content:
            return CompetitorOutline(
                id=result.id,
                provider=_provider_from_locator(result.locator),
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

        labels = tuple(
            _filter_outline_labels_for_offering(
                _extract_outline_labels(fetched.content),
                result.title,
            )
        )
        status = "usable" if len(labels) >= 3 else "partial" if labels else "inaccessible"
        return CompetitorOutline(
            id=result.id,
            provider=_provider_from_locator(result.locator),
            offering=result.title,
            locator=result.locator,
            audience="Unknown from accessible page.",
            level="unknown",
            duration=None,
            delivery_format=None,
            assessment_approach=None,
            outline_status=status,
            outline_labels=labels,
        )

    def _fetch(self, locator: str) -> FetchResult:
        normalized = _normalize_http_locator(locator)
        if normalized is None:
            return FetchResult(
                locator=locator,
                ok=False,
                reason="invalid HTTP URL",
            )
        locator = normalized
        last_reason = "request did not complete"
        for attempt in range(self.max_retries + 1):
            try:
                status_code, headers, payload = self._fetch_bytes(locator)
                content_type = headers.get("content-type", headers.get("Content-Type", ""))
                if status_code == 429 or status_code >= 500:
                    last_reason = f"HTTP {status_code}"
                    if attempt < self.max_retries:
                        time.sleep(self.retry_backoff_s * (attempt + 1))
                        continue
                    return FetchResult(
                        locator=locator,
                        ok=False,
                        reason=last_reason,
                        content_type=content_type,
                        status_code=status_code,
                    )
                if status_code >= 400:
                    return FetchResult(
                        locator=locator,
                        ok=False,
                        reason=f"HTTP {status_code}",
                        content_type=content_type,
                        status_code=status_code,
                    )
                text, reason = _extract_text(payload, locator, content_type)
                if not text.strip():
                    return FetchResult(
                        locator=locator,
                        ok=False,
                        reason=reason or "no extractable text",
                        content_type=content_type,
                        status_code=status_code,
                    )
                return FetchResult(
                    locator=locator,
                    ok=True,
                    content=text,
                    content_type=content_type,
                    status_code=status_code,
                )
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                last_reason = str(exc)
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_s * (attempt + 1))
        return FetchResult(locator=locator, ok=False, reason=last_reason)

    def _urlopen_fetch(self, locator: str) -> tuple[int, dict[str, str], bytes]:
        request = Request(locator, headers={"User-Agent": self.user_agent})
        with urlopen(request, timeout=self.timeout_s) as response:  # noqa: S310
            payload = response.read(self.max_bytes + 1)
            if len(payload) > self.max_bytes:
                raise OSError(f"response exceeded max_bytes={self.max_bytes}")
            return response.status, dict(response.headers.items()), payload


def _live_result_id(locator: str) -> str:
    """Return a stable reference even when search ranking order changes."""
    digest = hashlib.sha256(locator.encode("utf-8")).hexdigest()[:16]
    return f"live_{digest}"


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
    """A small non-FRM provider used by Sprint 1/2 tests and demos."""
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
            id="comp_brewlab",
            title="Brew Better Coffee at Home",
            locator="https://example.test/brewlab",
            snippet=(
                "Beginner home course outline for fresh beans, recipes, water, and taste fixes."
            ),
        ),
        SearchResult(
            id="comp_locked",
            title="Professional Cafe Course",
            locator="https://example.test/locked",
            snippet="Outline is behind a login.",
        ),
        SearchResult(
            id="coffee_g1",
            title="Coffee Brewing Basics Notes",
            locator="https://example.test/coffee-brewing",
            snippet=(
                "Auditable source for extraction variables, grind size, water "
                "temperature, and ratio."
            ),
        ),
        SearchResult(
            id="coffee_g2",
            title="Water Quality for Coffee",
            locator="https://example.test/water-quality",
            snippet="Auditable source for water quality, temperature, and extraction control.",
        ),
        SearchResult(
            id="coffee_g4",
            title="Coffee Brewing Troubleshooting Chart",
            locator="https://example.test/troubleshooting-chart",
            snippet="Auditable source for diagnosing sour, bitter, weak, and muddy coffee.",
        ),
        SearchResult(
            id="coffee_g3",
            title="Anonymous Espresso Hack List",
            locator="https://example.test/espresso-hacks",
            snippet="Unattributed coffee and espresso advice outside beginner home brewing scope.",
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
        "comp_brewlab": CompetitorOutline(
            id="comp_brewlab",
            provider="Example Brew Lab",
            offering="Brew Better Coffee at Home",
            locator="https://example.test/brewlab",
            audience="Home coffee beginners.",
            level="beginner",
            duration="3 hours",
            delivery_format="self-paced",
            assessment_approach="brew log and short quiz",
            outline_status="usable",
            outline_labels=(
                "Fresh beans and storage",
                "Recipe basics",
                "Grind size",
                "Water quality",
                "Taste correction loop",
            ),
        ),
    }
    pages = {
        "https://example.test/home-coffee": (
            "Course outline\nBeans and freshness\nGrind size\nWater temperature\n"
            "Brew ratio\nTasting and adjustment"
        ),
        "https://example.test/barista": (
            "Course outline\nExtraction basics\nGrind adjustment\n"
            "Water and recipe control\nMilk texture\nTroubleshooting taste"
        ),
        "https://example.test/brewlab": (
            "Course outline\nFresh beans and storage\nRecipe basics\n"
            "Grind size\nWater quality\nTaste correction loop"
        ),
        "https://example.test/coffee-brewing": (
            "Extraction is shaped by grind size, water temperature, brew ratio, "
            "and contact time. A repeatable recipe makes adjustments easier."
        ),
        "https://example.test/water-quality": (
            "Water quality affects extraction and flavor clarity. Beginner courses "
            "can treat it as a useful adjustment after recipe basics are stable."
        ),
        "https://example.test/troubleshooting-chart": (
            "Sour coffee can point to under-extraction, while bitter coffee can "
            "point to over-extraction. Adjust grind, ratio, and contact time one "
            "variable at a time."
        ),
        "https://example.test/espresso-hacks": (
            "Anonymous espresso tips without sourcing or beginner context."
        ),
    }
    return MockResearchProvider(search_results=results, pages=pages, outlines=outlines)


def _tokens(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", value.lower()) if token}


class FetchBytes(Protocol):
    def __call__(self, locator: str) -> tuple[int, dict[str, str], bytes]: ...


class _TextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0
        self._line_tags = {"h1", "h2", "h3", "h4", "li", "p", "title"}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
        if tag in self._line_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in self._line_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = _squash_ws(data)
        if text:
            self.parts.append(text)


class _LinkHTMLParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self._href_stack: list[str | None] = []
        self._text_stack: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href")
        self._href_stack.append(urljoin(self.base_url, href) if href else None)
        self._text_stack.append([])

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._href_stack:
            return
        href = self._href_stack.pop()
        text_parts = self._text_stack.pop()
        label = _squash_ws(" ".join(text_parts))
        if href and label:
            self.links.append((href, label))

    def handle_data(self, data: str) -> None:
        if self._text_stack:
            self._text_stack[-1].append(data)


def _extract_text(payload: bytes, locator: str, content_type: str) -> tuple[str, str | None]:
    content_type = content_type.lower()
    if "pdf" in content_type or urlparse(locator).path.lower().endswith(".pdf"):
        text = _extract_pdf_text(payload)
        return text, None if text else "PDF did not expose extractable text"
    decoded = _decode_bytes(payload, content_type)
    if "<html" in decoded[:1000].lower() or "text/html" in content_type:
        return _extract_visible_html_text(decoded), None
    return _squash_multiline(decoded), None


def _extract_visible_html_text(raw_html: str) -> str:
    parser = _TextHTMLParser()
    parser.feed(raw_html)
    parser.close()
    return _squash_multiline(html.unescape(" ".join(parser.parts)))


def _extract_links(raw_html: str, *, base_url: str) -> list[tuple[str, str]]:
    parser = _LinkHTMLParser(base_url)
    parser.feed(raw_html)
    parser.close()
    return parser.links


def _extract_pdf_text(payload: bytes) -> str:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError:
        return _pdf_ascii_fallback(payload)

    try:
        reader = PdfReader(BytesIO(payload))
        pages = [page.extract_text() or "" for page in reader.pages[:20]]
    except Exception:
        return _pdf_ascii_fallback(payload)
    return _squash_multiline("\n".join(pages))


def _pdf_ascii_fallback(payload: bytes) -> str:
    decoded = payload.decode("latin-1", errors="ignore")
    visible = re.findall(r"[A-Za-z0-9][A-Za-z0-9 ,.;:()/%-]{20,}", decoded)
    return _squash_multiline("\n".join(visible[:200]))


def _extract_outline_labels(text: str) -> list[str]:
    labels: list[str] = []
    lines = [_clean_outline_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]

    marker_indexes = [
        index
        for index, line in enumerate(lines)
        if any(marker in line.lower() for marker in OUTLINE_START_MARKERS)
    ]
    for index in marker_indexes:
        labels.extend(_outline_labels_from_window(lines[index + 1 : index + 40]))
        if len(labels) >= 12:
            break
    return _dedupe(labels)


def _outline_labels_from_window(lines: list[str]) -> list[str]:
    labels: list[str] = []
    for line in lines:
        lowered = line.lower()
        if labels and any(marker in lowered for marker in OUTLINE_STOP_MARKERS):
            break
        if _looks_like_outline_label(line):
            labels.append(line)
        if len(labels) >= 12:
            break
    return labels


def _looks_like_outline_label(label: str) -> bool:
    if not label or len(label) > 140 or _is_outline_chrome(label):
        return False
    words = label.split()
    if not 2 <= len(words) <= 14:
        return False
    lower = label.lower()
    return any(marker in lower for marker in OUTLINE_TOPIC_MARKERS) or _looks_like_title(label)


def _clean_outline_line(line: str) -> str:
    label = re.sub(r"^\s*(?:\d+[\.)]|[-*•])\s*", "", line).strip()
    label = _squash_ws(label)
    if ":" in label:
        before_colon, after_colon = label.split(":", 1)
        if 1 <= len(before_colon.split()) <= 7 and len(after_colon.split()) >= 3:
            label = before_colon.strip()
    return label.strip(" .")


def _looks_like_title(label: str) -> bool:
    words = label.split()
    if not words:
        return False
    titleish = sum(1 for word in words if word[:1].isupper())
    return titleish >= max(1, len(words) // 2)


def _is_outline_chrome(label: str) -> bool:
    lower = label.lower().strip()
    if lower in OUTLINE_SKIP_EXACT:
        return True
    return any(marker in lower for marker in OUTLINE_SKIP_CONTAINS)


GENERIC_OFFERING_TOKENS = {
    "basic",
    "beginner",
    "beginners",
    "complete",
    "course",
    "fundamentals",
    "guide",
    "handbook",
    "introduction",
    "module",
    "overview",
    "pdf",
    "program",
    "skills",
    "training",
}


def _filter_outline_labels_for_offering(labels: list[str], offering_title: str) -> list[str]:
    offering_tokens = _tokens(offering_title) - GENERIC_OFFERING_TOKENS
    if not offering_tokens:
        return labels
    if any(_tokens(label) & offering_tokens for label in labels):
        return labels
    topicish = [
        label
        for label in labels
        if any(marker in label.lower() for marker in OUTLINE_TOPIC_MARKERS)
    ]
    return labels if len(topicish) >= 3 else []


OUTLINE_START_MARKERS = (
    "course outline",
    "course overview",
    "course content",
    "topics covered",
    "program of the course",
    "curriculum",
    "syllabus",
    "your day includes",
    "what you will learn",
    "what you'll learn",
    "modules include",
    "learning outcomes",
    "course objectives",
    "by the end of the course",
    "by the end of this course",
    "upon completion of the course",
    "upon completion of this course",
)

OUTLINE_STOP_MARKERS = (
    "who should attend",
    "course details",
    "after training",
    "reviews",
    "related courses",
    "booking",
    "payment",
    "faq",
    "contact",
    "address",
    "social networks",
    "footer",
)

OUTLINE_TOPIC_MARKERS = (
    "module",
    "lesson",
    "topic",
    "introduction",
    "overview",
    "basics",
    "fundamentals",
    "assessment",
    "practice",
    "workflow",
    "troubleshooting",
    "recipe",
    "methods",
    "tools",
    "skills",
    "history",
    "origin",
    "species",
    "processing",
    "coffee",
    "barista",
    "espresso",
    "sensory",
    "roasting",
    "brewing",
    "milk",
    "grind",
    "water",
    "apply",
    "create",
    "demonstrate",
    "describe",
    "evaluate",
    "explain",
    "identify",
    "recognize",
    "select",
    "understand",
)

OUTLINE_SKIP_EXACT = {
    "about us",
    "account",
    "ask ai",
    "back to top",
    "blog",
    "cart",
    "checkout",
    "close suggestions",
    "consulting",
    "contact us",
    "copy link",
    "course media",
    "course calendar",
    "courses",
    "download",
    "events catering",
    "faq",
    "footer menu",
    "fullscreen",
    "go to next items",
    "go to previous items",
    "home",
    "links",
    "location",
    "login",
    "menu",
    "my account",
    "program of the course",
    "print",
    "privacy",
    "refund policy",
    "register",
    "report",
    "save",
    "search",
    "share",
    "share this document",
    "sign in",
    "skip to content",
    "uploaded by",
    "upload",
    "you'll leave with",
}

OUTLINE_SKIP_CONTAINS = (
    "cookie",
    "copyright",
    "email",
    "log in",
    "mobile:",
    "privacy",
    "review marketplace",
    "quick links",
    "save save",
    "scribd",
    "sign in",
    "share this",
    "telephone",
    "training calendar",
    "training centers",
    "view more",
    "www.",
)


def _decode_bytes(payload: bytes, content_type: str) -> str:
    charset_match = re.search(r"charset=([^;\s]+)", content_type, re.I)
    charset = charset_match.group(1) if charset_match else "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def _unwrap_result_href(href: str) -> str:
    parsed = urlparse(href)
    params = parse_qs(parsed.query)
    for key in ("uddg", "url", "u"):
        if params.get(key):
            # parse_qs already removes the redirect wrapper's percent encoding.
            # A second unquote would corrupt valid target escapes such as %20.
            return params[key][0]
    return href


def _normalize_http_locator(value: str) -> str | None:
    """Return a request-safe HTTP(S) URL without double-decoding target escapes."""
    candidate = html.unescape(value).strip()
    if not candidate or any(
        ord(character) < 0x20 or ord(character) == 0x7F
        for character in candidate
    ):
        return None
    parsed = urlparse(candidate)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or any(character.isspace() for character in parsed.netloc)
    ):
        return None
    return parsed._replace(
        path=quote(parsed.path, safe="/%:@!$&'()*+,;=-._~"),
        params=quote(parsed.params, safe="/%:@!$&'()*+,;=-._~"),
        query=quote(parsed.query, safe="=&%/:;+,.?@!$'()*-_[]~"),
        fragment=quote(parsed.fragment, safe="%/:;+,.?@!$&'()*=-_[]~"),
    ).geturl()


def _provider_from_locator(locator: str) -> str:
    host = urlparse(locator).netloc
    return host or "Unknown"


def _is_search_engine_url(value: str) -> bool:
    host = urlparse(value).netloc.lower()
    return host in {"duckduckgo.com", "lite.duckduckgo.com", "www.duckduckgo.com"}


def _squash_ws(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def _squash_multiline(value: str) -> str:
    lines = [_squash_ws(line) for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
