"""Typed human decisions kept separate from long-running stage execution."""

from __future__ import annotations

from typing import Any

from agents import blueprint as blueprint_agent
from agents import content_review, intake, outcomes
from api.services.artifact_repository import (
    ArtifactNotFound,
    ArtifactRepository,
    ReadOnlyCourse,
)
from api.services.pipeline_catalog import PipelineCatalog


class DecisionService:
    def __init__(self, repository: ArtifactRepository, catalog: PipelineCatalog) -> None:
        self.repository = repository
        self.catalog = catalog

    def create_course(
        self,
        *,
        subject: str,
        description: str | None,
        constraints: list[str],
        known_source_locators: list[str],
        course_id: str | None,
    ) -> dict[str, Any]:
        if not subject.strip():
            raise ValueError("subject cannot be empty")
        resolved_id = course_id or intake.slugify_course_id(subject, suffix="course")
        self.repository.validate_course_id(resolved_id)
        try:
            self.repository.locate(resolved_id)
        except ArtifactNotFound:
            pass
        else:
            raise FileExistsError(f"course already exists: {resolved_id}")
        artifact = intake.subject_request_artifact(
            subject=subject.strip(),
            description=description,
            constraints=constraints,
            known_source_locators=known_source_locators,
            course_id=resolved_id,
        )
        # Subject Request is a human-supplied seed, matching save_seed_artifact.
        artifact["status"] = "approved"
        return self.repository.save(artifact)

    def approve_stage(self, course_id: str, stage_slug: str) -> list[dict[str, Any]]:
        self._writable(course_id)
        definition = self.catalog.stage(stage_slug)
        missing = [
            artifact_type
            for artifact_type in definition.artifacts
            if self.repository.load(course_id, artifact_type) is None
        ]
        if missing:
            raise ArtifactNotFound(
                f"stage {stage_slug!r} is missing required decision output(s): "
                f"{', '.join(missing)}"
            )
        artifacts = []
        for artifact_type in definition.artifacts:
            artifact = self.repository.load(course_id, artifact_type)
            if artifact is None:
                continue
            checksum = self.repository.checksum(artifact)
            artifact["status"] = "approved"
            artifacts.append(
                self.repository.save(artifact, expected_checksum=checksum)
            )
        if not artifacts:
            raise ArtifactNotFound(f"stage has no output to approve: {stage_slug}")
        return artifacts

    def reopen_stage(self, course_id: str, stage_slug: str) -> list[dict[str, Any]]:
        self._writable(course_id)
        definition = self.catalog.stage(stage_slug)
        artifacts = []
        for artifact_type in definition.artifacts:
            artifact = self.repository.load(course_id, artifact_type)
            if artifact is None:
                continue
            checksum = self.repository.checksum(artifact)
            artifact["status"] = "draft"
            artifact["revision_note"] = "Reopened by the course director."
            artifacts.append(
                self.repository.save(artifact, expected_checksum=checksum)
            )
        if not artifacts:
            raise ArtifactNotFound(f"stage has no output to reopen: {stage_slug}")
        return artifacts

    def save_brief_answers(
        self, course_id: str, answers: dict[str, Any]
    ) -> dict[str, Any]:
        self._writable(course_id)
        subject = self.repository.require(course_id, "subject_request")
        artifact = intake.build_brief_artifact(subject, answers)
        existing = self.repository.load(course_id, "brief")
        artifact["revision"] = int(existing.get("revision", 0)) + 1 if existing else 0
        artifact["status"] = "draft"
        return self.repository.save(artifact)

    def save_outcome_decision(
        self,
        course_id: str,
        *,
        selected_ids: list[str],
        edits: dict[str, dict[str, Any]],
        additions: list[dict[str, Any]],
        priority_order: list[str],
    ) -> dict[str, Any]:
        self._writable(course_id)
        brief = self.repository.require(course_id, "brief")
        existing = self.repository.load(course_id, "course_outcomes")
        candidates = (
            existing.get("body", {}).get("outcomes", [])
            if existing
            else outcomes.draft_outcomes_from_brief(brief)
        )
        decided = outcomes.apply_outcome_decision(
            candidates,
            selected_ids,
            edits=edits,
            additions=additions,
            priority_order=priority_order,
        )
        artifact = outcomes.build_course_outcomes_artifact(brief, decided)
        artifact["revision"] = int(existing.get("revision", 0)) + 1 if existing else 0
        artifact["status"] = "draft"
        return self.repository.save(artifact)

    def save_source_decision(
        self, course_id: str, *, selected_ids: list[str]
    ) -> dict[str, Any]:
        """Capture an explicit grounding-source selection as its own checkpoint."""
        import steps as pipeline_steps

        self._writable(course_id)
        dossier = self.repository.require(course_id, "research_dossier")
        existing = self.repository.load(course_id, "approved_source_registry")
        produced = pipeline_steps.source_selection_step(
            {"research_dossier": dossier}, ",".join(selected_ids)
        )["approved_source_registry"]
        produced["revision"] = int(existing.get("revision", 0)) + 1 if existing else 0
        produced["revision_note"] = "Explicit source decision from the course workspace."
        produced["status"] = "draft"
        return self.repository.save(
            produced,
            expected_checksum=self.repository.checksum(existing) if existing else None,
        )

    def save_blueprint_decision(
        self,
        course_id: str,
        *,
        selected_asset_types: dict[str, list[str]],
        depth_overrides: dict[str, dict[str, Any]],
        anchor_waivers: set[str],
        rationale: str,
    ) -> dict[str, Any]:
        self._writable(course_id)
        blueprint = self.repository.require(course_id, "blueprint")
        decided = blueprint_agent.apply_blueprint_decision(
            blueprint,
            selected_asset_types=selected_asset_types,
            depth_overrides=depth_overrides,
            anchor_waivers=anchor_waivers,
            rationale=rationale,
        )
        decided["revision"] = int(blueprint.get("revision", 0)) + 1
        decided["status"] = "draft"
        return self.repository.save(
            decided, expected_checksum=self.repository.checksum(blueprint)
        )

    def save_content_review(
        self,
        course_id: str,
        asset_id: str,
        *,
        decision: str,
        note: str | None,
    ) -> dict[str, Any]:
        self._writable(course_id)
        existing = self.repository.load(course_id, "content_review")
        if existing is None:
            existing = self.sync_content_review(course_id)
        artifact = content_review.apply_content_review_decision(
            existing,
            asset_id=asset_id,
            decision=decision,
            feedback=note,
        )
        artifact["revision"] = int(existing.get("revision", 0)) + 1 if existing else 0
        artifact["status"] = "approved"
        return self.repository.save(
            artifact, expected_checksum=self.repository.checksum(existing)
        )

    def sync_content_review(self, course_id: str) -> dict[str, Any]:
        """Create or synchronize review records with the current Content Package."""
        self._writable(course_id)
        package = self.repository.require(course_id, "content_package")
        existing = self.repository.load(course_id, "content_review")
        artifact = content_review.build_content_review_artifact(
            package, existing_review=existing
        )
        artifact["revision"] = int(existing.get("revision", 0)) + 1 if existing else 0
        artifact["status"] = "approved"
        return self.repository.save(
            artifact,
            expected_checksum=self.repository.checksum(existing) if existing else None,
        )

    def _writable(self, course_id: str) -> None:
        if self.repository.locate(course_id).read_only:
            raise ReadOnlyCourse(f"committed example course is read-only: {course_id}")
