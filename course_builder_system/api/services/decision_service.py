"""Typed human decisions kept separate from long-running stage execution."""

from __future__ import annotations

from typing import Any

from agents import blueprint as blueprint_agent
from agents import content_review, intake, outcomes
from api.services.approval_guard import ApprovalGuardService
from api.services.artifact_repository import (
    ArtifactNotFound,
    ArtifactRepository,
    ReadOnlyCourse,
)
from api.services.brief_intake import BriefIntakeService
from api.services.lifecycle import (
    ImpactConfirmationRequired,
    ImpactPreviewService,
    InvalidationService,
    StaleImpactPreview,
)
from api.services.pipeline_catalog import PipelineCatalog


class StageNotReopened(RuntimeError):
    pass


class PrerequisiteNotApproved(RuntimeError):
    def __init__(self, stage: str, artifact_type: str) -> None:
        super().__init__(
            f"{artifact_type} must be approved and current before changing {stage}"
        )
        self.stage = stage
        self.artifact_type = artifact_type


class DecisionService:
    def __init__(
        self,
        repository: ArtifactRepository,
        catalog: PipelineCatalog,
        *,
        approval_guards: ApprovalGuardService | None = None,
        invalidation: InvalidationService | None = None,
        impact: ImpactPreviewService | None = None,
        brief_intake: BriefIntakeService | None = None,
    ) -> None:
        self.repository = repository
        self.catalog = catalog
        self.brief_intake = brief_intake or BriefIntakeService()
        self.approval_guards = approval_guards or ApprovalGuardService(
            repository,
            catalog,
            brief_intake=self.brief_intake,
        )
        self.invalidation = invalidation or InvalidationService(repository, catalog)
        self.impact = impact or ImpactPreviewService(repository, catalog)

    def create_course(
        self,
        *,
        subject: str,
        description: str | None,
        constraints: list[str],
        known_source_locators: list[str],
        brief_details: dict[str, Any] | None = None,
        course_id: str | None = None,
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
        brief = intake.build_initial_brief_artifact(artifact)
        if brief_details:
            body = self.brief_intake.merge_updates(
                artifact,
                brief.get("body", {}),
                brief_details,
            )
            brief = intake.brief_artifact_from_body(artifact, body)
        saved_subject = self.repository.save(artifact)
        self.repository.save(brief)
        return saved_subject

    def approve_stage(self, course_id: str, stage_slug: str) -> list[dict[str, Any]]:
        self._writable(course_id)
        self.approval_guards.assert_can_approve(course_id, stage_slug)
        definition = self.catalog.stage(stage_slug)
        missing = [
            artifact_type
            for artifact_type in definition.artifacts
            if self.repository.load(course_id, artifact_type) is None
        ]
        if missing:
            raise ArtifactNotFound(
                f"stage {stage_slug!r} is missing required decision output(s): {', '.join(missing)}"
            )
        artifacts = []
        for artifact_type in definition.artifacts:
            artifact = self.repository.load(course_id, artifact_type)
            if artifact is None:
                continue
            checksum = self.repository.checksum(artifact)
            artifact["status"] = "approved"
            artifacts.append(self.repository.save(artifact, expected_checksum=checksum))
        if not artifacts:
            raise ArtifactNotFound(f"stage has no output to approve: {stage_slug}")
        return artifacts

    def reopen_stage(
        self,
        course_id: str,
        stage_slug: str,
        *,
        reason: str | None = None,
        impact_acknowledged: bool = False,
        expected_impact_checksum: str | None = None,
    ) -> dict[str, Any]:
        self._writable(course_id)
        definition = self.catalog.stage(stage_slug)
        current = [
            artifact
            for artifact_type in definition.artifacts
            if (artifact := self.repository.load(course_id, artifact_type)) is not None
        ]
        if not current:
            raise ArtifactNotFound(f"stage has no output to reopen: {stage_slug}")
        if any(artifact.get("status") != "approved" for artifact in current):
            raise StageNotReopened(f"stage {stage_slug!r} can only be reopened while approved")
        preview = self.impact.preview(
            course_id,
            stage_slug,
            action="reopen",
            operation_summary=reason or f"Reopen {definition.label}",
        )
        if not impact_acknowledged or expected_impact_checksum is None:
            raise ImpactConfirmationRequired(
                "Confirm the current downstream impact before reopening this stage."
            )
        if preview["impact_checksum"] != expected_impact_checksum:
            raise StaleImpactPreview(
                "Downstream state changed after the impact preview; review it again."
            )
        artifacts = []
        for artifact_type in definition.artifacts:
            artifact = self.repository.load(course_id, artifact_type)
            if artifact is None:
                continue
            checksum = self.repository.checksum(artifact)
            artifact["status"] = "draft"
            artifact["revision_note"] = (
                reason.strip()
                if isinstance(reason, str) and reason.strip()
                else "Reopened by the course director."
            )
            artifacts.append(self.repository.save(artifact, expected_checksum=checksum))
        invalidated = self.invalidation.invalidate(
            course_id,
            set(definition.artifacts),
            reason=f"Stale because {definition.label} was reopened.",
        )
        return {
            "artifacts": artifacts,
            "invalidated": invalidated,
            "impact": preview,
        }

    def save_brief_answers(
        self,
        course_id: str,
        answers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self._writable(course_id)
        subject = self.repository.require(course_id, "subject_request")
        existing = self.repository.require(course_id, "brief")
        self._ensure_editable(existing, "brief")
        normalized = self.brief_intake.normalize_artifact(subject, existing)
        body = self.brief_intake.merge_answers(
            subject, normalized.get("body", {}), answers
        )
        artifact = intake.brief_artifact_from_body(subject, body)
        artifact["revision"] = int(existing.get("revision", 0)) + 1
        artifact["status"] = "draft"
        saved = self.repository.save(
            artifact,
            expected_checksum=self.repository.checksum(existing),
        )
        self._invalidate_if_changed(course_id, existing, saved, {"brief"})
        return saved

    def save_brief_updates(
        self,
        course_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        self._writable(course_id)
        subject = self.repository.require(course_id, "subject_request")
        existing = self.repository.require(course_id, "brief")
        self._ensure_editable(existing, "brief")
        normalized = self.brief_intake.normalize_artifact(subject, existing)
        body = self.brief_intake.merge_updates(
            subject, normalized.get("body", {}), updates
        )
        if self.repository.checksum(existing.get("body")) == self.repository.checksum(
            body
        ):
            raise ValueError("Brief update does not change the durable intake state")
        artifact = intake.brief_artifact_from_body(subject, body)
        artifact["revision"] = int(existing.get("revision", 0)) + 1
        artifact["status"] = "draft"
        saved = self.repository.save(
            artifact,
            expected_checksum=self.repository.checksum(existing),
        )
        self._invalidate_if_changed(course_id, existing, saved, {"brief"})
        return saved

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
        brief = self._require_ready_brief(course_id, "outcomes")
        existing = self.repository.load(course_id, "course_outcomes")
        self._ensure_editable(existing, "course_outcomes")
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
        saved = self.repository.save(
            artifact,
            expected_checksum=self.repository.checksum(existing) if existing else None,
        )
        self._invalidate_if_changed(course_id, existing, saved, {"course_outcomes"})
        return saved

    def save_source_decision(self, course_id: str, *, selected_ids: list[str]) -> dict[str, Any]:
        """Capture an explicit grounding-source selection as its own checkpoint."""
        import steps as pipeline_steps

        self._writable(course_id)
        self._require_ready_brief(course_id, "research")
        dossier = self.repository.require(course_id, "research_dossier")
        existing = self.repository.load(course_id, "approved_source_registry")
        self._ensure_editable(dossier, "research_dossier")
        self._ensure_editable(existing, "approved_source_registry")
        produced = pipeline_steps.source_selection_step(
            {"research_dossier": dossier}, ",".join(selected_ids)
        )["approved_source_registry"]
        produced["revision"] = int(existing.get("revision", 0)) + 1 if existing else 0
        produced["revision_note"] = "Explicit source decision from the course workspace."
        produced["status"] = "draft"
        saved = self.repository.save(
            produced,
            expected_checksum=self.repository.checksum(existing) if existing else None,
        )
        self._invalidate_if_changed(course_id, existing, saved, {"approved_source_registry"})
        return saved

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
        self._require_ready_brief(course_id, "blueprint")
        blueprint = self.repository.require(course_id, "blueprint")
        self._ensure_editable(blueprint, "blueprint")
        decided = blueprint_agent.apply_blueprint_decision(
            blueprint,
            selected_asset_types=selected_asset_types,
            depth_overrides=depth_overrides,
            anchor_waivers=anchor_waivers,
            rationale=rationale,
        )
        decided["revision"] = int(blueprint.get("revision", 0)) + 1
        decided["status"] = "draft"
        saved = self.repository.save(decided, expected_checksum=self.repository.checksum(blueprint))
        self._invalidate_if_changed(course_id, blueprint, saved, {"blueprint"})
        return saved

    def save_content_review(
        self,
        course_id: str,
        asset_id: str,
        *,
        decision: str,
        note: str | None,
    ) -> dict[str, Any]:
        self._writable(course_id)
        self._require_ready_brief(course_id, "content")
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
        saved = self.repository.save(artifact, expected_checksum=self.repository.checksum(existing))
        self._invalidate_if_changed(course_id, existing, saved, {"content_review"})
        return saved

    def sync_content_review(self, course_id: str) -> dict[str, Any]:
        """Create or synchronize review records with the current Content Package."""
        self._writable(course_id)
        self._require_ready_brief(course_id, "content")
        package = self.repository.require(course_id, "content_package")
        existing = self.repository.load(course_id, "content_review")
        artifact = content_review.build_content_review_artifact(package, existing_review=existing)
        artifact["revision"] = int(existing.get("revision", 0)) + 1 if existing else 0
        artifact["status"] = "approved"
        saved = self.repository.save(
            artifact,
            expected_checksum=self.repository.checksum(existing) if existing else None,
        )
        self._invalidate_if_changed(course_id, existing, saved, {"content_review"})
        return saved

    def _writable(self, course_id: str) -> None:
        if self.repository.locate(course_id).read_only:
            raise ReadOnlyCourse(f"committed example course is read-only: {course_id}")

    def _require_ready_brief(self, course_id: str, stage_slug: str) -> dict[str, Any]:
        """Enforce the transitive Brief gate for every later typed decision."""
        if not self.catalog.stage_depends_on_artifact(stage_slug, "brief"):
            raise ValueError(f"stage {stage_slug!r} is not downstream of the Brief")
        subject = self.repository.require(course_id, "subject_request")
        brief = self.repository.require(course_id, "brief")
        if not self.brief_intake.is_approved_and_resolved(subject, brief):
            raise PrerequisiteNotApproved(stage_slug, "brief")
        return self.brief_intake.normalize_artifact(subject, brief)

    @staticmethod
    def _ensure_editable(artifact: dict[str, Any] | None, artifact_type: str) -> None:
        if artifact is not None and artifact.get("status") == "approved":
            raise StageNotReopened(
                f"approved {artifact_type} must be reopened before it can change"
            )
        if artifact is not None and artifact.get("status") == "stale":
            raise StageNotReopened(f"stale {artifact_type} must be rerun before a direct decision")

    def _invalidate_if_changed(
        self,
        course_id: str,
        existing: dict[str, Any] | None,
        saved: dict[str, Any],
        changed_artifacts: set[str],
    ) -> None:
        if existing is not None and self.repository.checksum(
            existing.get("body")
        ) == self.repository.checksum(saved.get("body")):
            return
        label = self.catalog.stage_for_artifact(next(iter(changed_artifacts)))
        reason = f"Stale because {label or 'an upstream artifact'} changed."
        self.invalidation.invalidate(
            course_id,
            changed_artifacts,
            reason=reason,
        )
