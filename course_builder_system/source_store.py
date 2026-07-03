"""Source content storage foundation for approved research sources."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredSource:
    course_id: str
    source_id: str
    content_ref: str
    locator: str | None
    status: str
    reason: str | None = None


class SourceStore:
    """Persist source excerpts under a stable course/source identity."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def persist(
        self,
        *,
        course_id: str,
        source_id: str,
        content: str,
        locator: str | None = None,
    ) -> StoredSource:
        _validate_id(course_id, "course_id")
        _validate_id(source_id, "source_id")
        if not content.strip():
            raise ValueError("source content must not be empty")
        path = self.root / course_id / f"{source_id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return StoredSource(
            course_id=course_id,
            source_id=source_id,
            content_ref=str(path),
            locator=locator,
            status="available",
        )

    def unavailable(
        self,
        *,
        course_id: str,
        source_id: str,
        reason: str,
        locator: str | None = None,
    ) -> StoredSource:
        _validate_id(course_id, "course_id")
        _validate_id(source_id, "source_id")
        if not reason.strip():
            raise ValueError("unavailable sources require a reason")
        return StoredSource(
            course_id=course_id,
            source_id=source_id,
            content_ref="",
            locator=locator,
            status="unavailable",
            reason=reason,
        )

    def validate_content_ref(self, content_ref: str | None) -> bool:
        if not content_ref:
            return False
        path = Path(content_ref)
        return path.is_file() and path.read_text(encoding="utf-8").strip() != ""


def _validate_id(value: str, label: str) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", value):
        raise ValueError(f"{label} must be a stable lowercase id, got {value!r}")
