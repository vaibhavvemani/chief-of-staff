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
        all_assets = self._content_assets(course_id)
        scoped_revision = action == "revise"
        bounded_content_revision = scoped_revision and stage_slug == "content"
        if scoped_revision:
            registered_targets = {
                revision.target_type
                for revision in self.catalog.registered_capabilities(stage_slug).revisions
            }
            if target_type not in registered_targets or not target_ids:
                raise ValueError(
                    f"a scoped {stage.label} revision impact requires named "
                    f"{sorted(registered_targets)} targets"
                )
            normalized_targets = [
                item.strip() for item in target_ids if isinstance(item, str) and item.strip()
            ]
            if len(normalized_targets) != len(target_ids) or len(set(normalized_targets)) != len(
                normalized_targets
            ):
                raise ValueError("impact target IDs must be non-empty and unique")
            known_targets = self._revision_target_ids(course_id, stage_slug, str(target_type))
            unknown = sorted(set(normalized_targets) - known_targets)
            if unknown:
                raise ValueError(
                    f"unknown impact target {target_type}(s): " + ", ".join(unknown)
                )
            if bounded_content_revision:
                downstream = ("render_manifest", "run_summary")
                targeted_assets = sorted(normalized_targets)
                preserved_assets = sorted(set(all_assets) - set(targeted_assets))
            else:
                downstream = self.catalog.downstream_artifacts(set(stage.artifacts))
                content_is_affected = "content_package" in downstream
                targeted_assets = sorted(all_assets) if content_is_affected else []
                preserved_assets = [] if content_is_affected else sorted(all_assets)
        else:
            general_course_model_edit = action == "edit" and stage_slug == "course-model"
            if action != "reopen" and not general_course_model_edit:
                raise ValueError(
                    f"impact preview is not registered for {action!r} on {stage_slug!r}"
                )
            # Reopen and a typed Course Model edit are general lifecycle operations.
            # Target hints must never make their impact look bounded when the
            # mutation will stale the full graph.
            downstream = self.catalog.downstream_artifacts(set(stage.artifacts))
            content_is_affected = (
                "content_package" in stage.artifacts or "content_package" in downstream
            )
            targeted_assets = sorted(all_assets) if content_is_affected else []
            preserved_assets = [] if content_is_affected else sorted(all_assets)
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
        if (
            bounded_content_revision
            and self.repository.load(course_id, "content_review") is not None
        ):
            direct.append("content_review")
        rerun_stages = self.catalog.stages_for_artifacts(downstream)
        warnings: list[str] = []
        if bounded_content_revision:
            warnings.append("The changed learner asset will require human review again.")
        elif scoped_revision:
            warnings.append(
                f"Only the named {target_type} records may change, but saved downstream "
                "artifacts will still become stale."
            )
        if "content_package" in existing_downstream:
            warnings.append("Approved learner content will require generation and review again.")
        if "render_manifest" in existing_downstream or "run_summary" in existing_downstream:
            warnings.append("The current Package will no longer be releasable until rerun.")
        if not existing_downstream:
            warnings.append("No saved downstream artifact will be changed yet.")
        impact_level = self._impact_level(
            stage_slug,
            targeted_assets,
            preserved_assets,
            bounded=bounded_content_revision,
        )
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

    def _revision_target_ids(
        self,
        course_id: str,
        stage_slug: str,
        target_type: str,
    ) -> set[str]:
        if stage_slug == "content" and target_type == "asset":
            return set(self._content_assets(course_id))
        artifact_type, collection, key = {
            ("outcomes", "outcome"): ("course_outcomes", "outcomes", "id"),
            ("blueprint", "subtopic"): (
                "blueprint",
                "subtopic_plans",
                "subtopic_id",
            ),
        }.get((stage_slug, target_type), (None, None, None))
        if stage_slug == "course-model" and target_type == "subtopic":
            artifact = self.repository.load(course_id, "course_model") or {}
            return {
                str(item["id"])
                for module in artifact.get("body", {}).get("modules", [])
                if isinstance(module, dict)
                for item in module.get("subtopics", [])
                if isinstance(item, dict) and item.get("id")
            }
        if stage_slug == "lesson-plan" and target_type == "subtopic":
            artifact = self.repository.load(course_id, "lesson_plan") or {}
            return {
                str(cover["subtopic_id"])
                for session in artifact.get("body", {}).get("sessions", [])
                if isinstance(session, dict)
                for cover in session.get("covers", [])
                if isinstance(cover, dict) and cover.get("subtopic_id")
            }
        if artifact_type is None or collection is None or key is None:
            return set()
        artifact = self.repository.load(course_id, artifact_type) or {}
        return {
            str(item[key])
            for item in artifact.get("body", {}).get(collection, [])
            if isinstance(item, dict) and item.get(key)
        }

    @staticmethod
    def _impact_level(
        stage_slug: str,
        targeted_assets: list[str],
        preserved_assets: list[str],
        *,
        bounded: bool,
    ) -> str:
        if bounded:
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
        bounded_artifacts: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        plan = self.plan(
            course_id,
            changed_artifacts,
            reason=reason,
            transaction_outputs=transaction_outputs,
            bounded_artifacts=bounded_artifacts,
        )
        if not plan:
            return []
        saved = self.repository.save_batch(plan)
        for artifact in saved:
            planned = next(
                candidate
                for candidate, _expected in plan
                if candidate["artifact_type"] == artifact["artifact_type"]
            )
            if self.repository.checksum(artifact.get("body")) != self.repository.checksum(
                planned.get("body")
            ):
                raise RuntimeError(f"invalidation changed {artifact['artifact_type']} body")
        return saved

    def plan(
        self,
        course_id: str,
        changed_artifacts: list[str] | tuple[str, ...] | set[str],
        *,
        reason: str,
        transaction_outputs: set[str] | None = None,
        bounded_artifacts: set[str] | None = None,
    ) -> list[tuple[dict[str, Any], str]]:
        """Build exact-precondition stale writes without changing repository state."""
        graph_affected = set(self.catalog.downstream_artifacts(set(changed_artifacts)))
        if bounded_artifacts is None:
            affected = graph_affected
        else:
            outside_graph = bounded_artifacts - graph_affected
            if outside_graph:
                raise ValueError(
                    "bounded invalidation contains artifacts outside the dependency graph: "
                    + ", ".join(sorted(outside_graph))
                )
            affected = set(bounded_artifacts)
        # Outputs produced and validated in the same atomic stage transaction are
        # current by construction; they are not a domain-level bounded override.
        affected -= transaction_outputs or set()
        planned: list[tuple[dict[str, Any], str]] = []
        for artifact_type in sorted(affected):
            artifact = self.repository.load(course_id, artifact_type)
            if artifact is None or artifact.get("status") == "stale":
                continue
            before_body = self.repository.checksum(artifact.get("body"))
            expected = self.repository.checksum(artifact)
            stale = deepcopy(artifact)
            stale["status"] = "stale"
            stale["revision_note"] = reason
            if self.repository.checksum(stale.get("body")) != before_body:
                raise RuntimeError(f"invalidation changed {artifact_type} body")
            planned.append((stale, expected))
        return planned
