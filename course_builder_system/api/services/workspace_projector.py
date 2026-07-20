"""Derive operator-facing state from canonical artifacts and active jobs."""

from __future__ import annotations

from typing import Any

import run_summary
from agents.outcomes import outcome_advisories
from api.services.approval_guard import (
    ApprovalGuardService,
    hard_verifier_blocker_count,
)
from api.services.artifact_repository import ArtifactNotFound, ArtifactRepository
from api.services.brief_intake import BriefIntakeService
from api.services.capability_service import StageCapabilityService
from api.services.pipeline_catalog import PipelineCatalog, StageDefinition

BLOCKING_VERIFICATION_FIELDS = ("unsupported", "ungrounded", "unattributed")


class WorkspaceProjector:
    def __init__(
        self,
        repository: ArtifactRepository,
        catalog: PipelineCatalog,
        *,
        job_runner: Any | None = None,
        approval_guards: ApprovalGuardService | None = None,
        capabilities: StageCapabilityService | None = None,
        brief_intake: BriefIntakeService | None = None,
    ) -> None:
        self.repository = repository
        self.catalog = catalog
        self.job_runner = job_runner
        self.brief_intake = brief_intake or BriefIntakeService()
        self.approval_guards = approval_guards or ApprovalGuardService(
            repository,
            catalog,
            brief_intake=self.brief_intake,
        )
        self.capabilities = capabilities or StageCapabilityService(catalog)

    def list_courses(self) -> list[dict[str, Any]]:
        courses = []
        for location in self.repository.list_locations():
            workspace = self.project(location.course_id)
            courses.append(
                {
                    "course_id": location.course_id,
                    "title": workspace["title"],
                    "source": location.source,
                    "read_only": location.read_only,
                    "operator_status": workspace["operator_status"],
                    "current_stage": workspace["current_stage"],
                    "next_action": workspace["next_action"],
                    "last_activity_at": workspace["last_activity_at"],
                    "attention_count": workspace["attention"]["blocking_total"],
                }
            )
        return sorted(
            courses,
            key=lambda item: (item["last_activity_at"] or "", item["course_id"]),
            reverse=True,
        )

    def project(self, course_id: str) -> dict[str, Any]:
        location = self.repository.locate(course_id)
        artifacts = {
            artifact_type: self.repository.load(course_id, artifact_type)
            for artifact_type in self.repository.list_artifact_types(course_id)
        }
        artifacts = {name: value for name, value in artifacts.items() if value is not None}
        if "brief" in artifacts and "subject_request" in artifacts:
            artifacts["brief"] = self.brief_intake.normalize_artifact(
                artifacts["subject_request"], artifacts["brief"]
            )
        attention = self._attention(artifacts)
        active = self._active_job(course_id)
        stages = [
            self._project_stage(
                course_id,
                stage,
                artifacts,
                attention,
                active,
                read_only=location.read_only,
            )
            for stage in self.catalog.stages
        ]
        next_stage = next(
            (
                stage
                for stage in stages
                if stage["state"]
                in {
                    "requires_attention",
                    "failed",
                    "needs_input",
                    "awaiting_review",
                    "ready",
                    "stale",
                }
            ),
            None,
        )
        updated = max(
            (
                str(artifact.get("updated_at") or "")
                for artifact in artifacts.values()
                if artifact.get("updated_at")
            ),
            default=None,
        )
        return {
            "course_id": course_id,
            "title": self._title(course_id, artifacts),
            "source": location.source,
            "read_only": location.read_only,
            "operator_status": self._operator_status(stages, attention),
            "current_stage": next_stage["slug"] if next_stage else "package",
            "next_action": self._next_action(next_stage),
            "last_activity_at": updated,
            "active_job": active,
            "attention": attention,
            "stages": stages,
            "artifact_types": sorted(artifacts),
        }

    def stage(self, course_id: str, stage_slug: str) -> dict[str, Any]:
        definition = self.catalog.stage(stage_slug)
        workspace = self.project(course_id)
        stage = next(item for item in workspace["stages"] if item["slug"] == stage_slug)
        artifacts = []
        for artifact_type in definition.artifacts:
            artifact = self.repository.load(course_id, artifact_type)
            if artifact is not None:
                persisted = artifact
                if artifact_type == "brief":
                    subject = self.repository.require(course_id, "subject_request")
                    artifact = self.brief_intake.normalize_artifact(subject, artifact)
                artifacts.append(
                    {
                        "artifact_type": artifact_type,
                        "checksum": self.repository.checksum(persisted),
                        "envelope": {
                            key: value for key, value in artifact.items() if key != "body"
                        },
                        "body": artifact.get("body"),
                    }
                )
        return {**stage, "artifacts": artifacts}

    def list_assets(self, course_id: str) -> list[dict[str, Any]]:
        package = self.repository.require(course_id, "content_package")
        review = self.repository.load(course_id, "content_review") or {}
        decisions = {
            record.get("asset_id"): record
            for record in review.get("body", {}).get("assets", [])
            if isinstance(record, dict) and record.get("asset_id")
        }
        assets: list[dict[str, Any]] = []
        for subtopic in package.get("body", {}).get("subtopics", []):
            subtopic_id = subtopic.get("subtopic_id")
            for asset in subtopic.get("assets", []):
                verification = self._asset_verification(asset)
                assets.append(
                    {
                        "id": asset.get("id"),
                        "subtopic_id": subtopic_id,
                        "type": asset.get("type"),
                        "title": asset.get("title"),
                        "status": asset.get("status"),
                        "verification": verification,
                        "review": decisions.get(asset.get("id")),
                        "requires_attention": any(
                            verification[field] for field in BLOCKING_VERIFICATION_FIELDS
                        ),
                    }
                )
        return assets

    def asset(self, course_id: str, asset_id: str) -> dict[str, Any]:
        for summary in self.list_assets(course_id):
            if summary["id"] != asset_id:
                continue
            package = self.repository.require(course_id, "content_package")
            for subtopic in package.get("body", {}).get("subtopics", []):
                for asset in subtopic.get("assets", []):
                    if asset.get("id") == asset_id:
                        return {**summary, "asset": asset}
        raise ArtifactNotFound(f"content asset not found: {asset_id}")

    def _project_stage(
        self,
        course_id: str,
        stage: StageDefinition,
        artifacts: dict[str, dict[str, Any]],
        attention: dict[str, Any],
        active_job: dict[str, Any] | None,
        *,
        read_only: bool,
    ) -> dict[str, Any]:
        outputs = [artifacts.get(name) for name in stage.artifacts]
        present = [artifact for artifact in outputs if artifact is not None]
        prerequisite_artifacts = self.catalog.prerequisites_for_stage(stage.slug)
        prerequisites_ready = all(
            artifacts.get(name, {}).get("status") == "approved"
            for name in prerequisite_artifacts
        )
        blocking_stage = next(
            (
                self.catalog.stage_for_artifact(name)
                for name in prerequisite_artifacts
                if artifacts.get(name, {}).get("status") != "approved"
                and self.catalog.stage_for_artifact(name) is not None
            ),
            None,
        )
        brief_ready = True
        if self.catalog.stage_depends_on_artifact(stage.slug, "brief"):
            subject = artifacts.get("subject_request")
            brief = artifacts.get("brief")
            brief_ready = (
                subject is not None
                and brief is not None
                and self.brief_intake.is_approved_and_resolved(subject, brief)
            )
            if not brief_ready:
                prerequisites_ready = False
                blocking_stage = "brief"
        if stage.slug == "package":
            review_summary = (
                artifacts.get("content_review", {}).get("body", {}).get("summary")
            )
            if isinstance(review_summary, dict):
                prerequisites_ready = prerequisites_ready and bool(
                    review_summary.get("ready_for_package")
                )
                if not review_summary.get("ready_for_package"):
                    blocking_stage = "content"
        latest_job = self._latest_stage_job(course_id, stage.slug)
        failed_job_controls_stage = bool(
            latest_job
            and latest_job.get("status") == "failed"
            and latest_job.get("operation", "run") != "content_repair"
        )
        needs_input = self._needs_input(stage, artifacts)
        requires_reopen = bool(
            stage.slug == "brief"
            and needs_input
            and present
            and all(artifact.get("status") == "approved" for artifact in present)
        )
        if active_job and active_job.get("stage") == stage.slug:
            state = "running"
        elif failed_job_controls_stage:
            state = "failed"
        elif any(artifact.get("status") == "failed" for artifact in present):
            state = "failed"
        elif requires_reopen:
            state = "requires_attention"
        elif not present:
            if needs_input:
                state = "needs_input"
            else:
                state = "ready" if prerequisites_ready else "locked"
        elif any(artifact.get("status") == "stale" for artifact in present):
            state = "stale"
        elif not brief_ready:
            state = "stale"
        elif stage.slug in {"content", "package"} and attention["blocking_total"]:
            state = "requires_attention"
        elif not prerequisites_ready:
            state = "stale"
        elif stage.slug in {"content", "package"} and self._review_state(artifacts):
            state = self._review_state(artifacts) or "approved"
        elif needs_input:
            state = "needs_input"
        elif any(artifact.get("status") != "approved" for artifact in present):
            state = "awaiting_review"
        elif len(present) < len(stage.artifacts):
            # Research has a deliberate source-decision checkpoint between its outputs.
            state = "awaiting_review"
        else:
            state = "approved"
        approval_failures = (
            [
                failure.to_dict()
                for failure in self.approval_guards.failures(course_id, stage.slug)
            ]
            if state in {"awaiting_review", "requires_attention"}
            else []
        )
        actions = self.capabilities.actions(
            stage.slug,
            state,
            read_only=read_only,
            approval_failures=approval_failures,
            prerequisites_ready=prerequisites_ready,
            blocking_stage=blocking_stage,
            requires_reopen=requires_reopen,
        )
        if active_job is not None:
            actions = [
                action
                for action in actions
                if action.get("id") in {"continue", "go_to_blocker"}
            ]
        advisories = (
            outcome_advisories(
                artifacts.get("course_outcomes", {}).get("body", {}).get("outcomes", [])
            )
            if stage.slug == "outcomes"
            else []
        )
        downstream_artifacts = self.catalog.downstream_artifacts(set(stage.artifacts))
        return {
            "slug": stage.slug,
            "label": stage.label,
            "state": state,
            "artifact_types": list(stage.artifacts),
            "present_artifact_types": [
                artifact_type
                for artifact_type, artifact in zip(stage.artifacts, outputs, strict=True)
                if artifact is not None
            ],
            "attention_count": (
                attention["blocking_total"] if stage.slug in {"content", "package"} else 0
            ),
            "checksum": self.repository.checksum(present) if present else None,
            "dependencies": list(prerequisite_artifacts),
            "prerequisites_ready": prerequisites_ready,
            "requires_reopen": requires_reopen,
            "downstream_stages": list(
                self.catalog.stages_for_artifacts(downstream_artifacts)
            ),
            "approval_failures": approval_failures,
            "advisories": advisories,
            "last_failure": (
                latest_job.get("error")
                if latest_job and latest_job.get("status") == "failed"
                else None
            ),
            "actions": actions,
            "can_mutate": any(
                action.get("enabled", True)
                and action.get("id")
                not in {"continue", "go_to_blocker", "wait"}
                for action in actions
            ),
        }

    @staticmethod
    def _review_state(artifacts: dict[str, dict[str, Any]]) -> str | None:
        """Apply the durable human-review gate when a ledger exists.

        Historical snapshots predate the ledger and remain inspectable under their
        existing status. Newly synchronized courses cannot package pending decisions.
        """
        summary = artifacts.get("content_review", {}).get("body", {}).get("summary")
        if not isinstance(summary, dict):
            return None
        if summary.get("changes_requested", 0):
            return "requires_attention"
        if summary.get("pending", 0):
            return "awaiting_review"
        if not summary.get("ready_for_package", False):
            return "requires_attention"
        return None

    def _attention(self, artifacts: dict[str, dict[str, Any]]) -> dict[str, Any]:
        package = artifacts.get("content_package") or {}
        totals = run_summary._verification_totals(package)
        assets = []
        claim_level_blocking_total = 0
        for subtopic in package.get("body", {}).get("subtopics", []):
            for asset in subtopic.get("assets", []):
                verification = self._asset_verification(asset)
                blocker_count = hard_verifier_blocker_count(asset)
                claim_level_blocking_total += blocker_count
                if blocker_count:
                    assets.append(
                        {
                            "asset_id": asset.get("id"),
                            "subtopic_id": subtopic.get("subtopic_id"),
                            "verification": verification,
                            "blocker_count": blocker_count,
                        }
                    )
        progress = artifacts.get("content_progress", {}).get("body", {})
        failed_units = [
            unit
            for unit in progress.get("units", [])
            if unit.get("status") in {"failed", "pending", "evidence_gap"}
        ]
        return {
            "verification_totals": totals,
            "blocking_total": claim_level_blocking_total + len(failed_units),
            "flagged_assets": assets,
            "failed_units": failed_units,
        }

    @staticmethod
    def _asset_verification(asset: dict[str, Any]) -> dict[str, int]:
        value = asset.get("verification") if isinstance(asset.get("verification"), dict) else {}
        unattributed = value.get("unattributed_found", [])
        return {
            "supported": (
                value.get("supported", 0)
                if isinstance(value.get("supported", 0), int)
                else 0
            ),
            "partial": value.get("partial", 0) if isinstance(value.get("partial", 0), int) else 0,
            "unsupported": value.get("unsupported", 0)
            if isinstance(value.get("unsupported", 0), int)
            else 0,
            "ungrounded": value.get("ungrounded", 0)
            if isinstance(value.get("ungrounded", 0), int)
            else 0,
            "unattributed": len(unattributed) if isinstance(unattributed, list) else 0,
        }

    def _active_job(self, course_id: str) -> dict[str, Any] | None:
        if self.job_runner is None:
            return None
        return self.job_runner.active_for_course(course_id)

    def _latest_stage_job(self, course_id: str, stage_slug: str) -> dict[str, Any] | None:
        if self.job_runner is None or not hasattr(self.job_runner, "latest_for_stage"):
            return None
        return self.job_runner.latest_for_stage(course_id, stage_slug)

    @staticmethod
    def _needs_input(
        stage: StageDefinition, artifacts: dict[str, dict[str, Any]]
    ) -> bool:
        if stage.slug != "brief":
            return False
        intake_state = artifacts.get("brief", {}).get("body", {}).get("intake_state")
        return isinstance(intake_state, dict) and bool(
            intake_state.get("unresolved_required_fields")
        )

    @staticmethod
    def _operator_status(stages: list[dict[str, Any]], attention: dict[str, Any]) -> str:
        if attention["blocking_total"]:
            return "requires_attention"
        states = {stage["state"] for stage in stages}
        if "failed" in states:
            return "requires_attention"
        if "running" in states:
            return "running"
        if "needs_input" in states:
            return "needs_input"
        if "awaiting_review" in states or "stale" in states:
            return "pending_review"
        if all(stage["state"] == "approved" for stage in stages):
            return "complete"
        return "in_progress"

    @staticmethod
    def _next_action(stage: dict[str, Any] | None) -> str | None:
        if stage is None:
            return None
        return {
            "requires_attention": (
                f"Resolve {stage['attention_count']} blocker(s) in {stage['label']}"
            ),
            "failed": f"Retry {stage['label']}",
            "needs_input": f"Complete input for {stage['label']}",
            "awaiting_review": f"Review {stage['label']}",
            "ready": f"Run {stage['label']}",
            "stale": f"Refresh {stage['label']}",
        }.get(stage["state"])

    @staticmethod
    def _title(course_id: str, artifacts: dict[str, dict[str, Any]]) -> str:
        model = artifacts.get("course_model", {}).get("body", {})
        title = model.get("course_metadata", {}).get("course_title")
        if title:
            return str(title)
        brief = artifacts.get("brief", {}).get("body", {})
        if brief.get("course_title"):
            return str(brief["course_title"])
        subject = artifacts.get("subject_request", {}).get("body", {}).get("subject")
        return str(subject or course_id)
