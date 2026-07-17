"""Execute one product stage using the existing Step callables."""

from __future__ import annotations

import os
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from dotenv import load_dotenv

from agents import content_review
from api.services.artifact_repository import ArtifactRepository, ReadOnlyCourse
from api.services.brief_intake import BriefIntakeService
from api.services.capability_service import StageCapabilityService
from api.services.lifecycle import InvalidationService
from api.services.pipeline_catalog import PipelineCatalog
from api.services.revision_service import (
    NoOpRevision,
    PreparedRevision,
    RevisionService,
)


class StageRunner:
    def __init__(
        self,
        repository: ArtifactRepository,
        catalog: PipelineCatalog,
        *,
        revisions: RevisionService | None = None,
        invalidation: InvalidationService | None = None,
        brief_intake: BriefIntakeService | None = None,
    ) -> None:
        self.repository = repository
        self.catalog = catalog
        self.revisions = revisions or RevisionService(repository, StageCapabilityService(catalog))
        self.invalidation = invalidation or InvalidationService(repository, catalog)
        self.brief_intake = brief_intake or BriefIntakeService()

    def run(
        self,
        course_id: str,
        stage_slug: str,
        *,
        revision: dict[str, Any] | None = None,
        mode: str = "deterministic",
        emit: Callable[..., dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        location = self.repository.locate(course_id)
        if location.read_only:
            raise ReadOnlyCourse(f"committed example course is read-only: {course_id}")
        emit = emit or (lambda *_args, **_kwargs: {})
        stage = self.catalog.stage(stage_slug)
        if self.catalog.stage_depends_on_artifact(stage_slug, "brief"):
            subject = self.repository.require(course_id, "subject_request")
            brief = self.repository.require(course_id, "brief")
            if not self.brief_intake.is_approved_and_resolved(subject, brief):
                raise RuntimeError(
                    "a fully resolved and approved Brief is required before "
                    f"running {stage_slug}"
                )
        if mode == "live" and stage_slug == "content":
            load_dotenv()
        if mode == "live" and stage_slug == "content" and not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "Live Student Content requires ANTHROPIC_API_KEY on the Python server. "
                "Configure it in the environment or use deterministic mode."
            )
        steps = self.catalog.steps_for_stage(stage_slug, mode=mode)
        prepared_revision = self._prepare_revision(course_id, stage_slug, revision)
        emit(
            "stage.started",
            stage=stage_slug,
            mode=mode,
            message=f"Running {stage.label} in {mode} mode",
        )
        staged: dict[str, dict[str, Any]] = {}
        previous: dict[str, dict[str, Any] | None] = {}
        for step in steps:
            inputs: dict[str, dict[str, Any]] = {}
            for artifact_type in step.consumes:
                artifact = staged.get(artifact_type) or self.repository.load(
                    course_id, artifact_type
                )
                if artifact is None:
                    raise RuntimeError(
                        f"step {step.name!r} needs {artifact_type!r}, but it is not on disk"
                    )
                if artifact.get("status") != "approved" and artifact_type not in staged:
                    raise RuntimeError(f"step {step.name!r} needs approved {artifact_type!r}")
                inputs[artifact_type] = artifact
            if step.name == "student_content":
                existing_package = self.repository.load(course_id, "content_package")
                if existing_package is not None:
                    inputs["existing_content_package"] = existing_package
            # Human prose belongs to the generative/revision step. Source selection
            # has its own typed decision command; passing prose as comma-separated
            # source IDs would corrupt that checkpoint.
            step_feedback = prepared_revision.feedback if prepared_revision is not None else None
            if step.name == "source_selection":
                step_feedback = None
            produced = step.run(inputs, step_feedback)
            unexpected = set(produced) - set(step.produces)
            if unexpected:
                raise ValueError(
                    f"step {step.name!r} produced undeclared artifacts: {sorted(unexpected)}"
                )
            for artifact_type, artifact in produced.items():
                self._validate_output(course_id, artifact_type, artifact)
                previous.setdefault(artifact_type, self.repository.load(course_id, artifact_type))
                staged[artifact_type] = deepcopy(artifact)
            progress = produced.get("content_progress", {}).get("body", {})
            for unit in progress.get("units", []):
                event_type = (
                    "unit.failed"
                    if unit.get("status") in {"failed", "evidence_gap"}
                    else "unit.completed"
                )
                emit(
                    event_type,
                    stage=stage_slug,
                    subtopic_id=unit.get("subtopic_id"),
                    asset_id=unit.get("asset_id"),
                    progress={
                        "completed": progress.get("completed_asset_count"),
                        "expected": progress.get("expected_asset_count"),
                    },
                    message=f"{unit.get('asset_id') or 'Content unit'} {unit.get('status')}",
                )
        if stage_slug == "content" and "content_package" in staged:
            previous_review = self.repository.load(course_id, "content_review")
            review = content_review.build_content_review_artifact(
                staged["content_package"], existing_review=previous_review
            )
            previous["content_review"] = previous_review
            staged["content_review"] = review
        revision_outcome = None
        if prepared_revision is not None:
            revision_outcome = self._validate_revision_outcome(prepared_revision, previous, staged)
        self._commit(course_id, staged, previous, prepared_revision)
        changed_types = {
            artifact_type
            for artifact_type, artifact in staged.items()
            if previous.get(artifact_type) is None
            or self.repository.checksum(previous[artifact_type].get("body"))
            != self.repository.checksum(artifact.get("body"))
        }
        invalidated: list[dict[str, Any]] = []
        if changed_types:
            bounded_artifacts = (
                {"render_manifest", "run_summary"}
                if prepared_revision is not None
                and prepared_revision.stage == "content"
                and prepared_revision.target_type == "asset"
                else None
            )
            invalidated = self.invalidation.invalidate(
                course_id,
                changed_types,
                reason=f"Stale because {stage.label} changed.",
                transaction_outputs=set(staged),
                bounded_artifacts=bounded_artifacts,
            )
        emit(
            "stage.output_ready",
            stage=stage_slug,
            message=f"{stage.label} is ready for review",
        )
        emit(
            "checkpoint.awaiting_review",
            stage=stage_slug,
            message=f"Review {stage.label} before continuing",
        )
        result: dict[str, Any] = {
            "stage": stage_slug,
            "produced_artifact_types": list(staged),
            "stale_artifact_types": [artifact["artifact_type"] for artifact in invalidated],
        }
        if revision_outcome is not None:
            result["revision"] = revision_outcome
        return result

    def _prepare_revision(
        self,
        course_id: str,
        stage_slug: str,
        revision: dict[str, Any] | None,
    ) -> PreparedRevision | None:
        if revision is None:
            return None
        return self.revisions.prepare(
            course_id,
            stage_slug,
            target_type=str(revision["target_type"]),
            target_ids=list(revision["target_ids"]),
            category=str(revision["category"]),
            instruction=str(revision["instruction"]),
        )

    @staticmethod
    def _validate_output(course_id: str, artifact_type: str, artifact: dict[str, Any]) -> None:
        if artifact.get("course_id") != course_id:
            raise ValueError(f"{artifact_type} output has the wrong course_id")
        if artifact.get("artifact_type") != artifact_type:
            raise ValueError(f"{artifact_type} output has the wrong artifact_type")
        if not isinstance(artifact.get("body"), dict):
            raise ValueError(f"{artifact_type} output body must be an object")

    def _validate_revision_outcome(
        self,
        revision: PreparedRevision,
        previous: dict[str, dict[str, Any] | None],
        staged: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        old = previous.get("content_package")
        new = staged.get("content_package")
        if old is None or new is None:
            raise NoOpRevision("revision did not produce a Content Package")
        old_assets = self._assets_by_id(old)
        new_assets = self._assets_by_id(new)
        if set(old_assets) != set(new_assets):
            raise ValueError("revision changed the Content Package asset identity set")
        if self.repository.checksum(self._package_skeleton(old)) != self.repository.checksum(
            self._package_skeleton(new)
        ):
            raise ValueError("revision changed Content Package data outside asset bodies")
        changed_ids = tuple(
            sorted(
                asset_id
                for asset_id in old_assets
                if self.repository.checksum(old_assets[asset_id])
                != self.repository.checksum(new_assets[asset_id])
            )
        )
        if not changed_ids:
            raise NoOpRevision(
                "revision produced no content change; the prior artifact was preserved"
            )
        outside_scope = sorted(set(changed_ids) - set(revision.target_ids))
        if outside_scope:
            raise ValueError(
                "revision changed assets outside its declared scope: " + ", ".join(outside_scope)
            )
        return {
            "outcome": "changed",
            "changed_ids": list(changed_ids),
            "preserved_ids": sorted(set(revision.known_asset_ids) - set(changed_ids)),
        }

    @staticmethod
    def _assets_by_id(package: dict[str, Any]) -> dict[str, dict[str, Any]]:
        assets = {
            str(asset["id"]): asset
            for subtopic in package.get("body", {}).get("subtopics", [])
            if isinstance(subtopic, dict)
            for asset in subtopic.get("assets", [])
            if isinstance(asset, dict) and asset.get("id")
        }
        count = sum(
            1
            for subtopic in package.get("body", {}).get("subtopics", [])
            if isinstance(subtopic, dict)
            for asset in subtopic.get("assets", [])
            if isinstance(asset, dict)
        )
        if len(assets) != count:
            raise ValueError("Content Package revision contains duplicate or missing asset IDs")
        return assets

    @staticmethod
    def _package_skeleton(package: dict[str, Any]) -> dict[str, Any]:
        skeleton = deepcopy(package.get("body", {}))
        for subtopic in skeleton.get("subtopics", []):
            if isinstance(subtopic, dict):
                subtopic["assets"] = [
                    asset.get("id")
                    for asset in subtopic.get("assets", [])
                    if isinstance(asset, dict)
                ]
        return skeleton

    def _commit(
        self,
        course_id: str,
        staged: dict[str, dict[str, Any]],
        previous: dict[str, dict[str, Any] | None],
        revision: PreparedRevision | None,
    ) -> None:
        for artifact_type, artifact in staged.items():
            existing = previous.get(artifact_type)
            artifact["revision"] = (
                int(existing.get("revision", 0)) + 1 if existing is not None else 0
            )
            artifact["revision_note"] = revision.instruction if revision is not None else None
            # The review ledger is canonical support state; its records, rather than
            # its envelope, carry pending/approved human decisions.
            artifact["status"] = "approved" if artifact_type == "content_review" else "draft"
            self.repository.save(
                artifact,
                expected_checksum=(
                    self.repository.checksum(existing) if existing is not None else None
                ),
            )
