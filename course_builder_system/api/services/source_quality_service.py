"""Source-quality projection and known-source mutation service."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from agents.source_quality import known_source_candidate, project_source_quality
from api.services.artifact_repository import ArtifactRepository


class SourceQualityService:
    def __init__(self, repository: ArtifactRepository) -> None:
        self.repository = repository

    def project(self, course_id: str) -> dict[str, Any]:
        dossier = self.repository.require(course_id, "research_dossier")
        needs = self._evidence_needs(dossier)
        sources = []
        for candidate in dossier.get("body", {}).get("source_candidates", []):
            if not isinstance(candidate, dict):
                continue
            content, fetch_reason = self._read_content(course_id, candidate.get("content_ref"))
            sources.append(
                {
                    "id": candidate.get("id"),
                    "quality": project_source_quality(
                        candidate,
                        evidence_needs=needs,
                        content=content,
                        fetch_reason=fetch_reason,
                    ),
                }
            )
        return {"sources": sources, "evidence_needs": needs}

    def add_known_source(
        self,
        course_id: str,
        *,
        expected_checksum: str,
        locator: str,
        title: str | None,
        publisher: str | None,
        trust_notes: str | None,
        relevance: str | None,
    ) -> dict[str, Any]:
        location = self.repository.locate(course_id)
        if location.read_only:
            from api.services.artifact_repository import ReadOnlyCourse

            raise ReadOnlyCourse(f"committed example course is read-only: {course_id}")
        dossier = self.repository.require(course_id, "research_dossier")
        actual_checksum = self.repository.checksum(dossier)
        if actual_checksum != expected_checksum:
            from api.services.artifact_repository import VersionConflict

            raise VersionConflict(actual_checksum)
        candidate = known_source_candidate(
            locator,
            title=title,
            publisher=publisher,
            trust_notes=trust_notes,
            relevance=relevance,
        )
        candidates = dossier.get("body", {}).get("source_candidates")
        if not isinstance(candidates, list):
            raise ValueError("research dossier source_candidates must be a list")
        if any(
            isinstance(existing, dict)
            and (
                existing.get("id") == candidate["id"]
                or existing.get("locator") == candidate["locator"]
            )
            for existing in candidates
        ):
            raise ValueError("that source URL is already present in the research dossier")
        updated = deepcopy(dossier)
        updated["body"]["source_candidates"].append(candidate)
        updated["revision"] = int(dossier.get("revision", 0)) + 1
        updated["revision_note"] = (
            "Added a human-provided source candidate; normal source approval is still required."
        )
        updated["produced_by_step"] = "human"
        return self.repository.save(updated, expected_checksum=expected_checksum)

    def _read_content(
        self,
        course_id: str,
        content_ref: object,
    ) -> tuple[str | None, str | None]:
        if not isinstance(content_ref, str) or not content_ref:
            return None, None
        location = self.repository.locate(course_id)
        raw = Path(content_ref)
        path = raw if raw.is_absolute() else self.repository.repo_root / raw
        try:
            resolved = path.resolve()
            resolved.relative_to(location.artifact_root.resolve())
        except (OSError, ValueError):
            return None, "stored content reference is outside the course artifact root"
        try:
            content = resolved.read_text(encoding="utf-8")
        except OSError as exc:
            return None, f"stored source is unreadable: {exc}"
        if not content.strip():
            return None, "stored source has no extractable content"
        return content, None

    @staticmethod
    def _evidence_needs(dossier: dict[str, Any]) -> list[str]:
        body = dossier.get("body", {})
        needs: list[str] = []
        for observation in body.get("gap_observations", []):
            if isinstance(observation, dict) and isinstance(observation.get("statement"), str):
                needs.append(observation["statement"])
        for topic in body.get("normalized_topics", []):
            if isinstance(topic, dict) and isinstance(topic.get("label"), str):
                needs.append(topic["label"])
        return list(dict.fromkeys(needs))[:12]
