"""Explicit downstream impact and lifecycle invalidation services."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.services.artifact_repository import ArtifactRepository
from api.services.pipeline_catalog import PipelineCatalog


class ImpactConfirmationRequired(RuntimeError):
    pass


class StaleImpactPreview(RuntimeError):
    pass


class ImpactPreviewService:
    def __init__(self, repository: ArtifactRepository, catalog: PipelineCatalog) -> None:
        self.repository = repository
        self.catalog = catalog

    def preview(
        self,
        course_id: str,
        stage_slug: str,
        *,
        action: str,
        target_type: str | None = None,
        target_ids: list[str] | tuple[str, ...] = (),
        operation_summary: str | None = None,
    ) -> dict[str, Any]:
        stage = self.catalog.stage(stage_slug)
        downstream = self.catalog.downstream_artifacts(set(stage.artifacts))
        existing_downstream = [
            artifact_type
            for artifact_type in downstream
            if self.repository.load(course_id, artifact_type) is not None
        ]
        direct = [
            artifact_type
            for artifact_type in stage.artifacts
            if self.repository.load(course_id, artifact_type) is not None
        ]
        all_assets = self._content_assets(course_id)
        targeted_assets = self._targeted_assets(
            all_assets,
            target_type=target_type,
            target_ids=target_ids,
            content_is_affected="content_package" in downstream,
        )
        preserved_assets = sorted(set(all_assets) - set(targeted_assets))
        rerun_stages = self.catalog.stages_for_artifacts(downstream)
        warnings: list[str] = []
        if "content_package" in existing_downstream:
            warnings.append("Approved learner content will require generation and review again.")
        if "render_manifest" in existing_downstream or "run_summary" in existing_downstream:
            warnings.append("The current Package will no longer be releasable until rerun.")
        if not existing_downstream:
            warnings.append("No saved downstream artifact will be changed yet.")
        impact_level = self._impact_level(stage_slug, targeted_assets, preserved_assets)
        fingerprint_payload = {
            "action": action,
            "stage": stage_slug,
            "target_type": target_type,
            "target_ids": sorted(set(target_ids)),
            "direct": self._checksums(course_id, direct),
            "downstream": self._checksums(course_id, existing_downstream),
        }
        return {
            "action": action,
            "stage": stage_slug,
            "operation_summary": operation_summary,
            "direct_artifacts": direct,
            "stale_artifacts": existing_downstream,
            "targeted_assets": targeted_assets,
            "preserved_assets": preserved_assets,
            "requires_rerun_stages": list(rerun_stages),
            "warnings": warnings,
            "impact_level": impact_level,
            "impact_checksum": self.repository.checksum(fingerprint_payload),
        }

    def _checksums(self, course_id: str, artifact_types: list[str]) -> dict[str, str]:
        values: dict[str, str] = {}
        for artifact_type in artifact_types:
            artifact = self.repository.load(course_id, artifact_type)
            if artifact is not None:
                values[artifact_type] = self.repository.checksum(artifact)
        return values

    def _content_assets(self, course_id: str) -> dict[str, str]:
        package = self.repository.load(course_id, "content_package") or {}
        return {
            str(asset["id"]): str(subtopic.get("subtopic_id") or "")
            for subtopic in package.get("body", {}).get("subtopics", [])
            if isinstance(subtopic, dict)
            for asset in subtopic.get("assets", [])
            if isinstance(asset, dict) and asset.get("id")
        }

    @staticmethod
    def _targeted_assets(
        assets: dict[str, str],
        *,
        target_type: str | None,
        target_ids: list[str] | tuple[str, ...],
        content_is_affected: bool,
    ) -> list[str]:
        targets = set(target_ids)
        if target_type == "asset":
            return sorted(set(assets) & targets)
        if target_type == "subtopic":
            return sorted(
                asset_id
                for asset_id, subtopic_id in assets.items()
                if subtopic_id in targets
            )
        return sorted(assets) if content_is_affected else []

    @staticmethod
    def _impact_level(
        stage_slug: str, targeted_assets: list[str], preserved_assets: list[str]
    ) -> str:
        if targeted_assets and preserved_assets:
            return "targeted"
        if stage_slug in {"brief", "outcomes", "research"}:
            return "full"
        return "downstream"


class InvalidationService:
    def __init__(self, repository: ArtifactRepository, catalog: PipelineCatalog) -> None:
        self.repository = repository
        self.catalog = catalog

    def invalidate(
        self,
        course_id: str,
        changed_artifacts: list[str] | tuple[str, ...] | set[str],
        *,
        reason: str,
        transaction_outputs: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        affected = set(self.catalog.downstream_artifacts(set(changed_artifacts)))
        # Outputs produced and validated in the same atomic stage transaction are
        # current by construction; they are not a domain-level bounded override.
        affected -= transaction_outputs or set()
        saved: list[dict[str, Any]] = []
        for artifact_type in sorted(affected):
            artifact = self.repository.load(course_id, artifact_type)
            if artifact is None or artifact.get("status") == "stale":
                continue
            before_body = self.repository.checksum(artifact.get("body"))
            expected = self.repository.checksum(artifact)
            stale = deepcopy(artifact)
            stale["status"] = "stale"
            stale["revision_note"] = reason
            persisted = self.repository.save(stale, expected_checksum=expected)
            if self.repository.checksum(persisted.get("body")) != before_body:
                raise RuntimeError(f"invalidation changed {artifact_type} body")
            saved.append(persisted)
        return saved
