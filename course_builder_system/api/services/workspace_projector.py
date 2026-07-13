"""Derive operator-facing state from canonical artifacts and active jobs."""

from __future__ import annotations

from typing import Any

import run_summary
from api.services.artifact_repository import ArtifactNotFound, ArtifactRepository
from api.services.pipeline_catalog import PipelineCatalog, StageDefinition

BLOCKING_VERIFICATION_FIELDS = ("unsupported", "ungrounded", "unattributed")


class WorkspaceProjector:
    def __init__(
        self,
        repository: ArtifactRepository,
        catalog: PipelineCatalog,
        *,
        job_runner: Any | None = None,
    ) -> None:
        self.repository = repository
        self.catalog = catalog
        self.job_runner = job_runner

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
        attention = self._attention(artifacts)
        active = self._active_job(course_id)
        stages = [
            self._project_stage(stage, artifacts, attention, active)
            for stage in self.catalog.stages
        ]
        next_stage = next(
            (
                stage
                for stage in stages
                if stage["state"]
                in {"requires_attention", "failed", "awaiting_review", "ready", "stale"}
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
                artifacts.append(
                    {
                        "artifact_type": artifact_type,
                        "checksum": self.repository.checksum(artifact),
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
        stage: StageDefinition,
        artifacts: dict[str, dict[str, Any]],
        attention: dict[str, Any],
        active_job: dict[str, Any] | None,
    ) -> dict[str, Any]:
        outputs = [artifacts.get(name) for name in stage.artifacts]
        present = [artifact for artifact in outputs if artifact is not None]
        prerequisites_ready = all(
            artifacts.get(name, {}).get("status") == "approved"
            for name in stage.prerequisite_artifacts
        )
        if stage.slug == "package":
            review_summary = (
                artifacts.get("content_review", {}).get("body", {}).get("summary")
            )
            if isinstance(review_summary, dict):
                prerequisites_ready = prerequisites_ready and bool(
                    review_summary.get("ready_for_package")
                )
        if active_job and active_job.get("stage") == stage.slug:
            state = "running"
        elif any(artifact.get("status") == "failed" for artifact in present):
            state = "failed"
        elif not present:
            state = "ready" if prerequisites_ready else "locked"
        elif self._stage_is_stale(stage, artifacts, present):
            state = "stale"
        elif any(artifact.get("status") != "approved" for artifact in present):
            state = "awaiting_review"
        elif len(present) < len(stage.artifacts):
            # Research has a deliberate source-decision checkpoint between its outputs.
            state = "awaiting_review"
        elif stage.slug in {"content", "package"} and attention["blocking_total"]:
            state = "requires_attention"
        elif stage.slug in {"content", "package"} and self._review_state(artifacts):
            state = self._review_state(artifacts) or "approved"
        else:
            state = "approved"
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
            "can_mutate": state not in {"locked", "running"},
        }

    def _stage_is_stale(
        self,
        stage: StageDefinition,
        artifacts: dict[str, dict[str, Any]],
        present: list[dict[str, Any]],
    ) -> bool:
        newest_input = max(
            (
                str(artifacts[name].get("updated_at") or "")
                for name in stage.prerequisite_artifacts
                if name in artifacts
            ),
            default="",
        )
        return any(
            artifact.get("status") == "approved"
            and newest_input
            and str(artifact.get("updated_at") or "") < newest_input
            for artifact in present
        )

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
        for subtopic in package.get("body", {}).get("subtopics", []):
            for asset in subtopic.get("assets", []):
                verification = self._asset_verification(asset)
                blocker_count = sum(
                    verification[field] for field in BLOCKING_VERIFICATION_FIELDS
                )
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
        blocking_total = sum(totals[field] for field in BLOCKING_VERIFICATION_FIELDS)
        return {
            "verification_totals": totals,
            "blocking_total": blocking_total + len(failed_units),
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

    @staticmethod
    def _operator_status(stages: list[dict[str, Any]], attention: dict[str, Any]) -> str:
        if attention["blocking_total"]:
            return "requires_attention"
        states = {stage["state"] for stage in stages}
        if "failed" in states:
            return "requires_attention"
        if "running" in states:
            return "running"
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
