"""Execute one product stage using the existing Step callables."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import llm
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
    LIVE_CALL_LIMITS = {
        "brief": (2, 60_000),
        "outcomes": (2, 60_000),
        "research": (2, 80_000),
        "course-model": (2, 120_000),
        "blueprint": (2, 120_000),
        "content": (64, 180_000),
        "lesson-plan": (2, 120_000),
    }

    def __init__(
        self,
        repository: ArtifactRepository,
        catalog: PipelineCatalog,
        *,
        revisions: RevisionService | None = None,
        invalidation: InvalidationService | None = None,
        brief_intake: BriefIntakeService | None = None,
        output_transforms: dict[
            str,
            Callable[[dict[str, Any], dict[str, Any] | None], dict[str, Any]],
        ]
        | None = None,
    ) -> None:
        self.repository = repository
        self.catalog = catalog
        self.revisions = revisions or RevisionService(repository, StageCapabilityService(catalog))
        self.invalidation = invalidation or InvalidationService(repository, catalog)
        self.brief_intake = brief_intake or BriefIntakeService()
        self.output_transforms = output_transforms or {}

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
        self.catalog.assert_mode_ready(mode, stage_slug)
        steps = self.catalog.steps_for_stage(stage_slug, mode=mode)
        prepared_revision = self._prepare_revision(
            course_id,
            stage_slug,
            revision,
            mode=mode,
        )
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
            if prepared_revision is not None:
                for artifact_type in stage.artifacts:
                    existing_stage_artifact = self.repository.load(course_id, artifact_type)
                    if existing_stage_artifact is not None:
                        inputs[f"existing_{artifact_type}"] = existing_stage_artifact
            # Human prose belongs to the generative/revision step. Source selection
            # has its own typed decision command; passing prose as comma-separated
            # source IDs would corrupt that checkpoint.
            step_feedback = prepared_revision.feedback if prepared_revision is not None else None
            if step.name == "source_selection":
                step_feedback = None
            if mode == "live" and stage_slug in self.LIVE_CALL_LIMITS:
                max_calls, max_input_chars = self.LIVE_CALL_LIMITS[stage_slug]
                with llm.live_call_context(
                    stage=stage_slug,
                    course_id=course_id,
                    max_calls=max_calls,
                    max_input_chars=max_input_chars,
                    emit=emit,
                ):
                    produced = step.run(inputs, step_feedback)
            else:
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
        stage_writes = self._prepare_stage_writes(staged, previous, prepared_revision)
        changed_types = {
            artifact_type
            for artifact_type, artifact in staged.items()
            if previous.get(artifact_type) is None
            or self.repository.checksum(previous[artifact_type].get("body"))
            != self.repository.checksum(artifact.get("body"))
        }
        invalidation_plan: list[tuple[dict[str, Any], str]] = []
        if changed_types:
            bounded_artifacts = (
                {"render_manifest", "run_summary"}
                if prepared_revision is not None
                and prepared_revision.stage == "content"
                and prepared_revision.target_type == "asset"
                else None
            )
            invalidation_plan = self.invalidation.plan(
                course_id,
                changed_types,
                reason=f"Stale because {stage.label} changed.",
                transaction_outputs=set(staged),
                bounded_artifacts=bounded_artifacts,
            )
        # A stage output and every stale transition it causes are one lifecycle
        # transaction. A replacement failure must not expose a partly-current graph.
        saved = self.repository.save_batch([*stage_writes, *invalidation_plan])
        stage_count = len(stage_writes)
        staged.update({artifact["artifact_type"]: artifact for artifact in saved[:stage_count]})
        invalidated = saved[stage_count:]
        for artifact, (planned, _expected) in zip(
            invalidated,
            invalidation_plan,
            strict=True,
        ):
            if self.repository.checksum(artifact.get("body")) != self.repository.checksum(
                planned.get("body")
            ):
                raise RuntimeError(f"invalidation changed {artifact['artifact_type']} body")
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
        *,
        mode: str,
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
            mode=mode,
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
        artifact_types = {
            "content": "content_package",
            "outcomes": "course_outcomes",
            "course-model": "course_model",
            "blueprint": "blueprint",
            "lesson-plan": "lesson_plan",
        }
        artifact_type = artifact_types.get(revision.stage)
        if artifact_type is None:
            raise ValueError(f"unsupported revision stage: {revision.stage}")
        old = previous.get(artifact_type)
        new = staged.get(artifact_type)
        if old is None or new is None:
            raise NoOpRevision(f"revision did not produce {artifact_type}")
        old_records = self._revision_records(revision.stage, old)
        new_records = self._revision_records(revision.stage, new)
        if set(old_records) != set(new_records):
            raise ValueError(f"revision changed the {artifact_type} record identity set")
        old_skeleton = self._revision_skeleton(revision.stage, old)
        new_skeleton = self._revision_skeleton(revision.stage, new)
        if self.repository.checksum(old_skeleton) != self.repository.checksum(new_skeleton):
            changed_sections = sorted(
                key
                for key in old_skeleton.keys() | new_skeleton.keys()
                if self.repository.checksum(old_skeleton.get(key))
                != self.repository.checksum(new_skeleton.get(key))
            )
            raise ValueError(
                f"revision changed {artifact_type} data outside target records: "
                + ", ".join(changed_sections)
            )
        if revision.stage == "lesson-plan":
            changed_ids = self._lesson_revision_changed_ids(
                old,
                new,
                old_records,
                new_records,
                set(revision.target_ids),
            )
        else:
            changed_ids = tuple(
                sorted(
                    record_id
                    for record_id in old_records
                    if self.repository.checksum(old_records[record_id])
                    != self.repository.checksum(new_records[record_id])
                )
            )
        if not changed_ids:
            raise NoOpRevision(
                "revision produced no content change; the prior artifact was preserved"
            )
        outside_scope = sorted(set(changed_ids) - set(revision.target_ids))
        if outside_scope:
            raise ValueError(
                "revision changed records outside its declared scope: "
                + ", ".join(outside_scope)
            )
        return {
            "outcome": "changed",
            "changed_ids": list(changed_ids),
            "preserved_ids": sorted(set(revision.known_record_ids) - set(changed_ids)),
        }

    @classmethod
    def _revision_records(
        cls,
        stage: str,
        artifact: dict[str, Any],
    ) -> dict[str, dict[str, Any]]:
        body = artifact.get("body", {})
        if stage == "content":
            return cls._assets_by_id(artifact)
        if stage == "outcomes":
            records = body.get("outcomes", [])
            key = "id"
        elif stage == "course-model":
            records = [
                item
                for module in body.get("modules", [])
                if isinstance(module, dict)
                for item in module.get("subtopics", [])
                if isinstance(item, dict)
            ]
            key = "id"
        elif stage == "blueprint":
            records = body.get("subtopic_plans", [])
            key = "subtopic_id"
        elif stage == "lesson-plan":
            records = [
                cover
                for session in body.get("sessions", [])
                if isinstance(session, dict)
                for cover in session.get("covers", [])
                if isinstance(cover, dict)
            ]
            key = "subtopic_id"
        else:
            raise ValueError(f"unsupported revision stage: {stage}")
        result = {
            str(record[key]): record
            for record in records
            if isinstance(record, dict) and record.get(key)
        }
        if len(result) != len(records):
            raise ValueError(f"{stage} revision contains duplicate or missing record IDs")
        return result

    @staticmethod
    def _revision_skeleton(stage: str, artifact: dict[str, Any]) -> dict[str, Any]:
        if stage == "content":
            return StageRunner._package_skeleton(artifact)
        skeleton = deepcopy(artifact.get("body", {}))
        if stage == "outcomes":
            skeleton["outcomes"] = [
                item.get("id") for item in skeleton.get("outcomes", [])
            ]
        elif stage == "course-model":
            # The typed reducer may canonicalize legacy allocation metadata even
            # when a revision only updates an existing subtopic. Model output
            # cannot control this backend-owned bookkeeping.
            skeleton.pop("id_allocation", None)
            for module in skeleton.get("modules", []):
                module["subtopics"] = [
                    item.get("id") for item in module.get("subtopics", [])
                ]
        elif stage == "blueprint":
            skeleton["subtopic_plans"] = [
                item.get("subtopic_id") for item in skeleton.get("subtopic_plans", [])
            ]
            skeleton["decision_log"] = []
        elif stage == "lesson-plan":
            # Session shape, coverage order, derived totals, and bookkeeping are
            # reducer-owned consequences of a typed target move. Target and
            # non-target coverage safety is checked explicitly below.
            skeleton.pop("session_id_cursor", None)
            skeleton.pop("sessions", None)
            skeleton.pop("coverage_summary", None)
            skeleton.pop("sequence_policy", None)
        if stage in {"outcomes", "course-model", "blueprint", "lesson-plan"}:
            skeleton["decision_log"] = []
        return skeleton

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

    def _lesson_revision_changed_ids(
        self,
        old: dict[str, Any],
        new: dict[str, Any],
        old_records: dict[str, dict[str, Any]],
        new_records: dict[str, dict[str, Any]],
        target_ids: set[str],
    ) -> tuple[str, ...]:
        old_placements = self._lesson_placements(old)
        new_placements = self._lesson_placements(new)
        if set(old_placements) != set(new_placements):
            raise ValueError("revision changed the lesson_plan coverage identity set")

        non_targets = set(old_records) - target_ids
        changed_non_target_records = sorted(
            record_id
            for record_id in non_targets
            if self.repository.checksum(old_records[record_id])
            != self.repository.checksum(new_records[record_id])
        )
        if changed_non_target_records:
            raise ValueError(
                "revision changed records outside its declared scope: "
                + ", ".join(changed_non_target_records)
            )
        old_non_target_order = [
            item
            for item in self._lesson_coverage_order(old)
            if item not in target_ids
        ]
        new_non_target_order = [
            item
            for item in self._lesson_coverage_order(new)
            if item not in target_ids
        ]
        if old_non_target_order != new_non_target_order:
            raise ValueError(
                "revision changed Lesson Plan sequence outside its declared scope"
            )
        return tuple(
            sorted(
                record_id
                for record_id in target_ids
                if self.repository.checksum(old_records[record_id])
                != self.repository.checksum(new_records[record_id])
                or old_placements[record_id] != new_placements[record_id]
            )
        )

    @staticmethod
    def _lesson_coverage_order(artifact: dict[str, Any]) -> list[str]:
        return [
            str(cover["subtopic_id"])
            for session in artifact.get("body", {}).get("sessions", [])
            if isinstance(session, dict)
            for cover in session.get("covers", [])
            if isinstance(cover, dict) and cover.get("subtopic_id")
        ]

    @classmethod
    def _lesson_placements(cls, artifact: dict[str, Any]) -> dict[str, dict[str, Any]]:
        placements: dict[str, dict[str, Any]] = {}
        global_order = 0
        for session in artifact.get("body", {}).get("sessions", []):
            if not isinstance(session, dict):
                continue
            for position, cover in enumerate(session.get("covers", []), start=1):
                if not isinstance(cover, dict) or not cover.get("subtopic_id"):
                    continue
                global_order += 1
                placements[str(cover["subtopic_id"])] = {
                    "session_id": session.get("id"),
                    "position": position,
                    "global_order": global_order,
                }
        return placements

    def _prepare_stage_writes(
        self,
        staged: dict[str, dict[str, Any]],
        previous: dict[str, dict[str, Any] | None],
        revision: PreparedRevision | None,
    ) -> list[tuple[dict[str, Any], str]]:
        writes: list[tuple[dict[str, Any], str]] = []
        for artifact_type, artifact in staged.items():
            existing = previous.get(artifact_type)
            if transform := self.output_transforms.get(artifact_type):
                artifact = transform(artifact, existing)
                staged[artifact_type] = artifact
            artifact["revision"] = (
                int(existing.get("revision", 0)) + 1 if existing is not None else 0
            )
            artifact["revision_note"] = revision.instruction if revision is not None else None
            # The review ledger is canonical support state; its records, rather than
            # its envelope, carry pending/approved human decisions.
            artifact["status"] = "approved" if artifact_type == "content_review" else "draft"
            writes.append(
                (
                    artifact,
                    self.repository.checksum(existing)
                    if existing is not None
                    else "missing",
                )
            )
        return writes
