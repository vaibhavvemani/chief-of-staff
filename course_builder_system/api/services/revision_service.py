"""Validate scoped revision commands before a job is allowed to start."""

from __future__ import annotations

import json
from dataclasses import dataclass

from api.services.artifact_repository import ArtifactRepository
from api.services.capability_service import StageCapabilityService


class AmbiguousRevision(ValueError):
    pass


class NoOpRevision(RuntimeError):
    pass


@dataclass(frozen=True)
class PreparedRevision:
    stage: str
    target_type: str
    target_ids: tuple[str, ...]
    category: str
    instruction: str
    feedback: str
    known_asset_ids: tuple[str, ...]


class RevisionService:
    def __init__(
        self,
        repository: ArtifactRepository,
        capabilities: StageCapabilityService,
    ) -> None:
        self.repository = repository
        self.capabilities = capabilities

    def prepare(
        self,
        course_id: str,
        stage_slug: str,
        *,
        target_type: str,
        target_ids: list[str] | tuple[str, ...],
        category: str,
        instruction: str,
    ) -> PreparedRevision:
        self.capabilities.assert_revision_supported(
            stage_slug, target_type, category
        )
        normalized_ids = tuple(dict.fromkeys(item.strip() for item in target_ids if item.strip()))
        if len(normalized_ids) != len(target_ids):
            raise AmbiguousRevision("revision target IDs must be non-empty and unique")
        if stage_slug != "content" or target_type != "asset":
            raise AmbiguousRevision("the registered revision handler is unavailable")
        package = self.repository.require(course_id, "content_package")
        assets: dict[str, str] = {
            str(asset["id"]): str(subtopic.get("subtopic_id") or "")
            for subtopic in package.get("body", {}).get("subtopics", [])
            if isinstance(subtopic, dict)
            for asset in subtopic.get("assets", [])
            if isinstance(asset, dict) and asset.get("id")
        }
        unknown = sorted(set(normalized_ids) - set(assets))
        if unknown:
            raise AmbiguousRevision(
                "unknown revision target asset(s): " + ", ".join(unknown)
            )
        subtopics = {assets[item] for item in normalized_ids}
        if len(subtopics) != 1:
            raise AmbiguousRevision(
                "one revision command cannot span multiple subtopics"
            )
        normalized_instruction = instruction.strip()
        if not normalized_instruction:
            raise AmbiguousRevision("revision instruction cannot be empty")
        feedback = json.dumps(
            {
                "assets": list(normalized_ids),
                "subtopic_id": next(iter(subtopics)),
                "verifier": category == "evidence",
                "feedback": normalized_instruction,
            },
            separators=(",", ":"),
        )
        return PreparedRevision(
            stage=stage_slug,
            target_type=target_type,
            target_ids=normalized_ids,
            category=category,
            instruction=normalized_instruction,
            feedback=feedback,
            known_asset_ids=tuple(sorted(assets)),
        )
