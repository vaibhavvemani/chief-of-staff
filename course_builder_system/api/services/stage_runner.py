"""Execute one product stage using the existing Step callables."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from dotenv import load_dotenv

from agents import content_review
from api.services.artifact_repository import ArtifactRepository, ReadOnlyCourse
from api.services.pipeline_catalog import PipelineCatalog


class StageRunner:
    def __init__(self, repository: ArtifactRepository, catalog: PipelineCatalog) -> None:
        self.repository = repository
        self.catalog = catalog

    def run(
        self,
        course_id: str,
        stage_slug: str,
        *,
        feedback: str | None = None,
        mode: str = "deterministic",
        emit: Callable[..., dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        location = self.repository.locate(course_id)
        if location.read_only:
            raise ReadOnlyCourse(f"committed example course is read-only: {course_id}")
        emit = emit or (lambda *_args, **_kwargs: {})
        stage = self.catalog.stage(stage_slug)
        if mode == "live" and stage_slug == "content":
            load_dotenv()
        if mode == "live" and stage_slug == "content" and not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "Live Student Content requires ANTHROPIC_API_KEY on the Python server. "
                "Configure it in the environment or use deterministic mode."
            )
        steps = self.catalog.steps_for_stage(stage_slug, mode=mode)
        emit(
            "stage.started",
            stage=stage_slug,
            mode=mode,
            message=f"Running {stage.label} in {mode} mode",
        )
        produced_types: list[str] = []
        for step in steps:
            inputs: dict[str, dict[str, Any]] = {}
            for artifact_type in step.consumes:
                artifact = self.repository.load(course_id, artifact_type)
                if artifact is None:
                    raise RuntimeError(
                        f"step {step.name!r} needs {artifact_type!r}, but it is not on disk"
                    )
                if (
                    artifact.get("status") != "approved"
                    and artifact_type not in produced_types
                ):
                    raise RuntimeError(
                        f"step {step.name!r} needs approved {artifact_type!r}"
                    )
                inputs[artifact_type] = artifact
            # Human prose belongs to the generative/revision step. Source selection
            # has its own typed decision command; passing prose as comma-separated
            # source IDs would corrupt that checkpoint.
            step_feedback = None if step.name == "source_selection" else feedback
            produced = step.run(inputs, step_feedback)
            unexpected = set(produced) - set(step.produces)
            if unexpected:
                raise ValueError(
                    f"step {step.name!r} produced undeclared artifacts: {sorted(unexpected)}"
                )
            for artifact_type, artifact in produced.items():
                existing = self.repository.load(course_id, artifact_type)
                artifact["revision"] = (
                    int(existing.get("revision", 0)) + 1 if existing is not None else 0
                )
                artifact["revision_note"] = feedback
                artifact["status"] = "draft"
                self.repository.save(artifact)
                produced_types.append(artifact_type)
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
        if stage_slug == "content" and "content_package" in produced_types:
            self._sync_content_review(course_id)
            produced_types.append("content_review")
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
        return {"stage": stage_slug, "produced_artifact_types": produced_types}

    def _sync_content_review(self, course_id: str) -> None:
        """Reset human decisions only for assets whose generated content changed."""
        package = self.repository.require(course_id, "content_package")
        existing = self.repository.load(course_id, "content_review")
        review = content_review.build_content_review_artifact(
            package, existing_review=existing
        )
        review["revision"] = int(existing.get("revision", 0)) + 1 if existing else 0
        # The ledger itself is canonical and current; its records remain pending.
        review["status"] = "approved"
        self.repository.save(review)
