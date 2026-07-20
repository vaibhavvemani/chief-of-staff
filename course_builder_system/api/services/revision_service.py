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
    known_record_ids: tuple[str, ...]


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
        mode: str = "deterministic",
    ) -> PreparedRevision:
        self.capabilities.assert_revision_supported(
            stage_slug, target_type, category
        )
        normalized_ids = tuple(dict.fromkeys(item.strip() for item in target_ids if item.strip()))
        if len(normalized_ids) != len(target_ids):
            raise AmbiguousRevision("revision target IDs must be non-empty and unique")
        if stage_slug != "content" and mode != "live":
            raise AmbiguousRevision(
                f"{stage_slug} scoped revision requires explicit live mode"
            )
        records, parent_by_id = self._known_records(course_id, stage_slug, target_type)
        unknown = sorted(set(normalized_ids) - set(records))
        if unknown:
            raise AmbiguousRevision(
                "unknown revision target record(s): " + ", ".join(unknown)
            )
        parents = {parent_by_id[item] for item in normalized_ids if parent_by_id.get(item)}
        if stage_slug == "content" and len(parents) != 1:
            raise AmbiguousRevision(
                "one revision command cannot span multiple subtopics"
            )
        normalized_instruction = instruction.strip()
        if not normalized_instruction:
            raise AmbiguousRevision("revision instruction cannot be empty")
        if stage_slug == "content":
            feedback = json.dumps(
                {
                    "assets": list(normalized_ids),
                    "subtopic_id": next(iter(parents)),
                    "verifier": category == "evidence",
                    "feedback": normalized_instruction,
                },
                separators=(",", ":"),
            )
        else:
            feedback = json.dumps(
                {
                    "revision": {
                        "stage": stage_slug,
                        "target_type": target_type,
                        "target_ids": list(normalized_ids),
                        "category": category,
                        "instruction": normalized_instruction,
                    }
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
            known_asset_ids=tuple(sorted(records)) if stage_slug == "content" else (),
            known_record_ids=tuple(sorted(records)),
        )

    def _known_records(
        self,
        course_id: str,
        stage_slug: str,
        target_type: str,
    ) -> tuple[dict[str, dict], dict[str, str]]:
        if stage_slug == "content" and target_type == "asset":
            artifact = self.repository.require(course_id, "content_package")
            records = {
                str(asset["id"]): asset
                for subtopic in artifact.get("body", {}).get("subtopics", [])
                if isinstance(subtopic, dict)
                for asset in subtopic.get("assets", [])
                if isinstance(asset, dict) and asset.get("id")
            }
            parents = {
                str(asset["id"]): str(subtopic.get("subtopic_id") or "")
                for subtopic in artifact.get("body", {}).get("subtopics", [])
                if isinstance(subtopic, dict)
                for asset in subtopic.get("assets", [])
                if isinstance(asset, dict) and asset.get("id")
            }
            return records, parents
        if stage_slug == "outcomes" and target_type == "outcome":
            artifact = self.repository.require(course_id, "course_outcomes")
            records = {
                str(item["id"]): item
                for item in artifact.get("body", {}).get("outcomes", [])
                if isinstance(item, dict) and item.get("id")
            }
            return records, {}
        if stage_slug == "course-model" and target_type == "subtopic":
            artifact = self.repository.require(course_id, "course_model")
            records = {
                str(item["id"]): item
                for module in artifact.get("body", {}).get("modules", [])
                if isinstance(module, dict)
                for item in module.get("subtopics", [])
                if isinstance(item, dict) and item.get("id")
            }
            return records, {}
        if stage_slug == "blueprint" and target_type == "subtopic":
            artifact = self.repository.require(course_id, "blueprint")
            records = {
                str(item["subtopic_id"]): item
                for item in artifact.get("body", {}).get("subtopic_plans", [])
                if isinstance(item, dict) and item.get("subtopic_id")
            }
            return records, {}
        if stage_slug == "lesson-plan" and target_type == "subtopic":
            artifact = self.repository.require(course_id, "lesson_plan")
            records = {
                str(cover["subtopic_id"]): cover
                for session in artifact.get("body", {}).get("sessions", [])
                if isinstance(session, dict)
                for cover in session.get("covers", [])
                if isinstance(cover, dict) and cover.get("subtopic_id")
            }
            return records, {}
        raise AmbiguousRevision("the registered revision handler is unavailable")
