"""FastAPI transport for Course Builder Studio."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from agents.outcomes import OutcomeDecisionValidationError, outcome_advisories
from agents.source_repair import SourceRepairProvider
from api.models import (
    ApproveStageCommand,
    BlueprintDecisionCommand,
    BriefAnswersCommand,
    BriefClarificationCommand,
    BriefQuestionRoundResponse,
    BriefUpdatesCommand,
    ContentReviewCommand,
    CourseModelDecisionCommand,
    CourseModelDecisionPreviewCommand,
    CreateCourseRequest,
    ImpactPreviewCommand,
    ImpactPreviewResponse,
    KnownSourceCommand,
    LessonPlanDecisionCommand,
    OutcomeDecisionCommand,
    ReopenStageCommand,
    RunStageCommand,
    ScopedRevisionCommand,
    SourceDecisionCommand,
    SourceRepairDecisionCommand,
    SourceRepairRequestCommand,
    SourceRepairRouteCommand,
)
from api.services.approval_guard import ApprovalGuardFailed, ApprovalGuardService
from api.services.artifact_repository import (
    ArtifactNotFound,
    ArtifactRepository,
    ReadOnlyCourse,
    VersionConflict,
)
from api.services.brief_intake import BriefIntakeService, serialize_round
from api.services.capability_service import (
    StageCapabilityService,
    UnsupportedStageAction,
)
from api.services.decision_service import (
    DecisionService,
    PrerequisiteNotApproved,
    StageNotReopened,
)
from api.services.lifecycle import (
    ImpactConfirmationRequired,
    ImpactPreviewService,
    InvalidationService,
    StaleImpactPreview,
)
from api.services.local_job_runner import CourseBusy, JobNotFound, LocalJobRunner
from api.services.pipeline_catalog import PipelineCatalog
from api.services.revision_service import AmbiguousRevision, RevisionService
from api.services.source_quality_service import SourceQualityService
from api.services.source_repair_service import SourceRepairService
from api.services.stage_runner import StageRunner
from api.services.workspace_projector import WorkspaceProjector
from course_model_operations import (
    CourseModelValidationError,
    carry_forward_course_model_allocation,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def create_app(
    *,
    repo_root: Path = REPO_ROOT,
    courses_root: Path | None = None,
    rendered_root: Path | None = None,
    runtime_root: Path | None = None,
    include_examples: bool = True,
    deterministic_source_repair_provider: SourceRepairProvider | None = None,
    live_source_repair_provider: SourceRepairProvider | None = None,
) -> FastAPI:
    repo_root = repo_root.resolve()
    repository = ArtifactRepository(
        repo_root=repo_root,
        courses_root=courses_root,
        rendered_root=rendered_root,
        include_examples=include_examples,
    )
    catalog = PipelineCatalog(rendered_root=repository.rendered_root)
    jobs = LocalJobRunner(runtime_root or repo_root / "runtime")
    brief_intake = BriefIntakeService()
    guards = ApprovalGuardService(repository, catalog, brief_intake=brief_intake)
    capabilities = StageCapabilityService(catalog)
    impact = ImpactPreviewService(repository, catalog)
    invalidation = InvalidationService(repository, catalog)
    revisions = RevisionService(repository, capabilities)
    projector = WorkspaceProjector(
        repository,
        catalog,
        job_runner=jobs,
        approval_guards=guards,
        capabilities=capabilities,
        brief_intake=brief_intake,
    )
    decisions = DecisionService(
        repository,
        catalog,
        approval_guards=guards,
        invalidation=invalidation,
        impact=impact,
        brief_intake=brief_intake,
    )
    source_quality = SourceQualityService(repository)
    source_repairs = SourceRepairService(
        repository,
        deterministic_provider=deterministic_source_repair_provider,
        live_provider=live_source_repair_provider,
    )
    stages = StageRunner(
        repository,
        catalog,
        revisions=revisions,
        invalidation=invalidation,
        brief_intake=brief_intake,
        output_transforms={"course_model": carry_forward_course_model_allocation},
    )
    frontend_dist = repo_root / "frontend" / "dist"

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        jobs.shutdown(wait=True)

    app = FastAPI(
        title="Course Builder Studio API",
        version="0.1.0",
        description="Local artifact-first adapter around the Course Builder prototype.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Last-Event-ID"],
    )
    app.state.repository = repository
    app.state.catalog = catalog
    app.state.jobs = jobs
    app.state.projector = projector
    app.state.decisions = decisions
    app.state.stages = stages
    app.state.approval_guards = guards
    app.state.capabilities = capabilities
    app.state.impact = impact
    app.state.brief_intake = brief_intake
    app.state.revisions = revisions

    @app.exception_handler(ArtifactNotFound)
    async def _not_found(_request: Request, exc: ArtifactNotFound):
        return _error_response(404, str(exc))

    @app.exception_handler(JobNotFound)
    async def _job_not_found(_request: Request, exc: JobNotFound):
        return _error_response(404, str(exc))

    @app.exception_handler(ReadOnlyCourse)
    async def _read_only(_request: Request, exc: ReadOnlyCourse):
        return _error_response(403, str(exc))

    @app.exception_handler(VersionConflict)
    async def _conflict(_request: Request, exc: VersionConflict):
        return _error_response(
            409,
            str(exc),
            extra={"actual_checksum": exc.actual_checksum},
        )

    @app.exception_handler(CourseBusy)
    async def _busy(_request: Request, exc: CourseBusy):
        return _error_response(409, str(exc))

    @app.exception_handler(FileExistsError)
    async def _exists(_request: Request, exc: FileExistsError):
        return _error_response(409, str(exc))

    @app.exception_handler(ApprovalGuardFailed)
    async def _approval_rejected(_request: Request, exc: ApprovalGuardFailed):
        return _error_response(
            409,
            str(exc),
            extra={
                "code": "approval_guard_failed",
                "stage": exc.stage,
                "failures": [failure.to_dict() for failure in exc.failures],
            },
        )

    @app.exception_handler(ImpactConfirmationRequired)
    async def _impact_confirmation(_request: Request, exc: ImpactConfirmationRequired):
        return _error_response(409, str(exc), extra={"code": "impact_confirmation_required"})

    @app.exception_handler(StaleImpactPreview)
    async def _stale_impact(_request: Request, exc: StaleImpactPreview):
        return _error_response(409, str(exc), extra={"code": "stale_impact_preview"})

    @app.exception_handler(StageNotReopened)
    async def _stage_not_reopened(_request: Request, exc: StageNotReopened):
        return _error_response(409, str(exc), extra={"code": "reopen_required"})

    @app.exception_handler(PrerequisiteNotApproved)
    async def _prerequisite_not_approved(_request: Request, exc: PrerequisiteNotApproved):
        return _error_response(
            409,
            str(exc),
            extra={
                "code": "prerequisite_not_approved",
                "stage": exc.stage,
                "artifact_type": exc.artifact_type,
            },
        )

    @app.exception_handler(UnsupportedStageAction)
    async def _unsupported_action(_request: Request, exc: UnsupportedStageAction):
        return _error_response(409, str(exc), extra={"code": "unsupported_action"})

    @app.exception_handler(AmbiguousRevision)
    async def _ambiguous_revision(_request: Request, exc: AmbiguousRevision):
        return _error_response(400, str(exc), extra={"code": "ambiguous_revision"})

    @app.exception_handler(OutcomeDecisionValidationError)
    async def _invalid_outcome_decision(_request: Request, exc: OutcomeDecisionValidationError):
        return _error_response(
            400,
            str(exc),
            extra={"code": "invalid_outcome_decision", "issues": exc.issues},
        )

    @app.exception_handler(CourseModelValidationError)
    async def _invalid_course_model_decision(_request: Request, exc: CourseModelValidationError):
        return _error_response(
            400,
            str(exc),
            extra={"code": "invalid_course_model_decision", "issues": exc.issues},
        )

    @app.exception_handler(ValueError)
    async def _bad_request(_request: Request, exc: ValueError):
        return _error_response(400, str(exc))

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        load_dotenv()
        return {
            "status": "ok",
            "provider_readiness": {
                "deterministic": True,
                "live_anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
            },
            "frontend_built": (frontend_dist / "index.html").is_file(),
        }

    @app.get("/api/courses")
    def list_courses() -> dict[str, Any]:
        return {"courses": projector.list_courses()}

    @app.post("/api/courses", status_code=201)
    def create_course(command: CreateCourseRequest) -> dict[str, Any]:
        artifact = decisions.create_course(
            subject=command.subject,
            description=command.description,
            constraints=command.constraints,
            known_source_locators=command.known_source_locators,
            brief_details=command.brief,
            course_id=command.course_id,
        )
        return {
            "course_id": artifact["course_id"],
            "workspace": projector.project(artifact["course_id"]),
        }

    @app.get("/api/courses/{course_id}/workspace")
    def workspace(course_id: str) -> dict[str, Any]:
        return projector.project(course_id)

    @app.get("/api/courses/{course_id}/stages/{stage_slug}")
    def stage(course_id: str, stage_slug: str) -> dict[str, Any]:
        return projector.stage(course_id, stage_slug)

    @app.get("/api/courses/{course_id}/artifacts/{artifact_type}")
    def artifact(course_id: str, artifact_type: str) -> dict[str, Any]:
        value = repository.require(course_id, artifact_type)
        persisted = value
        if artifact_type == "brief":
            subject = repository.require(course_id, "subject_request")
            value = brief_intake.normalize_artifact(subject, value)
        return {
            "artifact": value,
            "checksum": repository.checksum(persisted),
            "read_only": repository.locate(course_id).read_only,
        }

    @app.post("/api/courses/{course_id}/stages/{stage_slug}/run", status_code=202)
    def run_stage(course_id: str, stage_slug: str, command: RunStageCommand) -> dict[str, Any]:
        catalog.stage(stage_slug)
        if repository.locate(course_id).read_only:
            raise ReadOnlyCourse(f"committed example course is read-only: {course_id}")
        _check_stage_version(projector, course_id, stage_slug, command.expected_checksum)
        state = projector.stage(course_id, stage_slug)["state"]
        action_id = "retry" if state == "failed" else "run"
        capabilities.assert_action_available(
            stage_slug,
            state,
            action_id,
            read_only=False,
            prerequisites_ready=projector.stage(course_id, stage_slug).get(
                "prerequisites_ready", False
            ),
        )
        job = jobs.submit(
            course_id=course_id,
            stage=stage_slug,
            task=lambda emit: (
                _check_stage_version(projector, course_id, stage_slug, command.expected_checksum)
                or stages.run(course_id, stage_slug, mode=command.mode, emit=emit)
            ),
        )
        return _job_accepted(job)

    @app.post("/api/courses/{course_id}/stages/{stage_slug}/approve")
    def approve_stage(
        course_id: str, stage_slug: str, command: ApproveStageCommand
    ) -> dict[str, Any]:
        with jobs.mutate_now(course_id):
            _check_stage_version(projector, course_id, stage_slug, command.expected_checksum)
            _ensure_stage_state(
                projector,
                course_id,
                stage_slug,
                allowed={"awaiting_review", "requires_attention"},
            )
            artifacts = decisions.approve_stage(course_id, stage_slug)
        return {
            "stage": projector.stage(course_id, stage_slug),
            "approved_artifact_types": [item["artifact_type"] for item in artifacts],
        }

    @app.post("/api/courses/{course_id}/stages/{stage_slug}/reopen")
    def reopen_stage(
        course_id: str, stage_slug: str, command: ReopenStageCommand
    ) -> dict[str, Any]:
        if repository.locate(course_id).read_only:
            raise ReadOnlyCourse(f"committed example course is read-only: {course_id}")
        with jobs.mutate_now(course_id):
            _check_stage_version(projector, course_id, stage_slug, command.expected_checksum)
            state = projector.stage(course_id, stage_slug)["state"]
            capabilities.assert_action_available(
                stage_slug,
                state,
                "reopen",
                read_only=repository.locate(course_id).read_only,
                prerequisites_ready=projector.stage(course_id, stage_slug).get(
                    "prerequisites_ready", False
                ),
                requires_reopen=projector.stage(course_id, stage_slug).get(
                    "requires_reopen", False
                ),
            )
            result = decisions.reopen_stage(
                course_id,
                stage_slug,
                reason=command.reason,
                impact_acknowledged=command.impact_acknowledged,
                expected_impact_checksum=command.expected_impact_checksum,
            )
        return {
            "stage": projector.stage(course_id, stage_slug),
            "reopened_artifact_types": [item["artifact_type"] for item in result["artifacts"]],
            "stale_artifact_types": [item["artifact_type"] for item in result["invalidated"]],
            "impact": result["impact"],
        }

    @app.post(
        "/api/courses/{course_id}/stages/{stage_slug}/impact",
        response_model=ImpactPreviewResponse,
    )
    def preview_impact(
        course_id: str, stage_slug: str, command: ImpactPreviewCommand
    ) -> dict[str, Any]:
        _check_stage_version(projector, course_id, stage_slug, command.expected_checksum)
        if repository.locate(course_id).read_only:
            raise ReadOnlyCourse(f"committed example course is read-only: {course_id}")
        return impact.preview(
            course_id,
            stage_slug,
            action=command.action,
            target_type=command.target_type,
            target_ids=command.target_ids,
            operation_summary=command.operation_summary,
        )

    @app.post(
        "/api/courses/{course_id}/stages/{stage_slug}/revisions",
        status_code=202,
    )
    def revise_stage(
        course_id: str, stage_slug: str, command: ScopedRevisionCommand
    ) -> dict[str, Any]:
        _check_stage_version(projector, course_id, stage_slug, command.expected_checksum)
        catalog.stage(stage_slug)
        if repository.locate(course_id).read_only:
            raise ReadOnlyCourse(f"committed example course is read-only: {course_id}")
        state = projector.stage(course_id, stage_slug)["state"]
        capabilities.assert_action_available(
            stage_slug,
            state,
            "revise",
            read_only=False,
            prerequisites_ready=projector.stage(course_id, stage_slug).get(
                "prerequisites_ready", False
            ),
        )
        _ensure_stage_state(
            projector,
            course_id,
            stage_slug,
            allowed={"awaiting_review", "requires_attention"},
        )
        revision_payload = {
            "target_type": command.target_type,
            "target_ids": command.target_ids,
            "category": command.category,
            "instruction": command.instruction,
        }
        # Reject unsupported, unknown, or cross-subtopic targets before a job exists.
        revisions.prepare(course_id, stage_slug, **revision_payload)
        current_impact = impact.preview(
            course_id,
            stage_slug,
            action="revise",
            target_type=command.target_type,
            target_ids=command.target_ids,
            operation_summary=command.instruction,
        )
        _assert_impact_acknowledged(
            current_impact,
            impact_acknowledged=command.impact_acknowledged,
            expected_impact_checksum=command.expected_impact_checksum,
        )

        def execute_revision(emit):
            _check_stage_version(projector, course_id, stage_slug, command.expected_checksum)
            # LocalJobRunner holds the course mutation lock while this task runs.
            # Recompute the exact impact here so the advisory browser preview cannot
            # authorize a mutation against changed downstream state.
            locked_impact = impact.preview(
                course_id,
                stage_slug,
                action="revise",
                target_type=command.target_type,
                target_ids=command.target_ids,
                operation_summary=command.instruction,
            )
            _assert_impact_acknowledged(
                locked_impact,
                impact_acknowledged=command.impact_acknowledged,
                expected_impact_checksum=command.expected_impact_checksum,
            )
            return stages.run(
                course_id,
                stage_slug,
                revision=revision_payload,
                mode=command.mode,
                emit=emit,
            )

        job = jobs.submit(
            course_id=course_id,
            stage=stage_slug,
            task=execute_revision,
        )
        return _job_accepted(job)

    @app.get(
        "/api/courses/{course_id}/brief/questions",
        response_model=BriefQuestionRoundResponse,
    )
    def brief_questions(course_id: str) -> dict[str, Any]:
        subject = repository.require(course_id, "subject_request")
        brief = repository.require(course_id, "brief")
        normalized = brief_intake.normalize_artifact(subject, brief)
        return serialize_round(
            brief_intake.question_round(subject, normalized.get("body", {})),
            checksum=repository.checksum(brief),
        )

    @app.post(
        "/api/courses/{course_id}/brief/clarifications/run",
        response_model=BriefQuestionRoundResponse,
    )
    def brief_clarifications(
        course_id: str,
        command: BriefClarificationCommand,
    ) -> dict[str, Any]:
        # NC-20 always runs deterministic gap detection. ``mode`` reserves the
        # provider-neutral command shape for NC-909 without invoking a model here.
        brief = repository.require(course_id, "brief")
        checksum = repository.checksum(brief)
        if checksum != command.expected_checksum:
            raise VersionConflict(checksum)
        subject = repository.require(course_id, "subject_request")
        normalized = brief_intake.normalize_artifact(subject, brief)
        return serialize_round(
            brief_intake.question_round(subject, normalized.get("body", {})),
            checksum=checksum,
        )

    @app.put("/api/courses/{course_id}/brief/answers")
    def brief_answers(course_id: str, command: BriefAnswersCommand) -> dict[str, Any]:
        with jobs.mutate_now(course_id):
            _check_artifact_version(repository, course_id, "brief", command.expected_checksum)
            value = decisions.save_brief_answers(
                course_id,
                [answer.model_dump(exclude_unset=True) for answer in command.answers],
            )
        return {"artifact": value, "checksum": repository.checksum(value)}

    @app.patch("/api/courses/{course_id}/brief")
    def brief_updates(course_id: str, command: BriefUpdatesCommand) -> dict[str, Any]:
        with jobs.mutate_now(course_id):
            _check_artifact_version(repository, course_id, "brief", command.expected_checksum)
            value = decisions.save_brief_updates(course_id, command.updates)
        return {"artifact": value, "checksum": repository.checksum(value)}

    @app.put("/api/courses/{course_id}/outcomes/decision")
    def outcome_decision(course_id: str, command: OutcomeDecisionCommand) -> dict[str, Any]:
        with jobs.mutate_now(course_id):
            _check_artifact_version(
                repository, course_id, "course_outcomes", command.expected_checksum
            )
            value = decisions.save_outcome_decision(
                course_id,
                selected_ids=list(command.selected_ids),
                edits={
                    outcome_id: patch.model_dump(exclude_none=True)
                    for outcome_id, patch in command.edits.items()
                },
                additions=[
                    addition.model_dump(exclude_none=True) for addition in command.additions
                ],
                priority_order=list(command.priority_order),
                expected_checksum=command.expected_checksum,
            )
        return {
            "artifact": value,
            "checksum": repository.checksum(value),
            "advisories": outcome_advisories(value.get("body", {}).get("outcomes", [])),
        }

    @app.post("/api/courses/{course_id}/course-model/decision/preview")
    def course_model_decision_preview(
        course_id: str, command: CourseModelDecisionPreviewCommand
    ) -> dict[str, Any]:
        _check_artifact_version(repository, course_id, "course_model", command.expected_checksum)
        return decisions.preview_course_model_decision(
            course_id,
            operations=[
                operation.model_dump(exclude_none=True) for operation in command.operations
            ],
            expected_checksum=command.expected_checksum,
        )

    @app.put("/api/courses/{course_id}/course-model/decision")
    def course_model_decision(
        course_id: str, command: CourseModelDecisionCommand
    ) -> dict[str, Any]:
        with jobs.mutate_now(course_id):
            _check_artifact_version(
                repository, course_id, "course_model", command.expected_checksum
            )
            return decisions.save_course_model_decision(
                course_id,
                operations=[
                    operation.model_dump(exclude_none=True) for operation in command.operations
                ],
                expected_checksum=command.expected_checksum,
                impact_acknowledged=command.impact_acknowledged,
                expected_impact_checksum=command.expected_impact_checksum,
            )

    @app.put("/api/courses/{course_id}/research/sources/decision")
    def source_decision(course_id: str, command: SourceDecisionCommand) -> dict[str, Any]:
        with jobs.mutate_now(course_id):
            _check_stage_version(projector, course_id, "research", command.expected_checksum)
            value = decisions.save_source_decision(course_id, selected_ids=command.selected_ids)
        return {
            "artifact": value,
            "checksum": repository.checksum(value),
            "stage": projector.stage(course_id, "research"),
        }

    def assert_projected_action(course_id: str, stage_slug: str, action_id: str) -> None:
        projected = projector.stage(course_id, stage_slug)
        capabilities.assert_action_available(
            stage_slug,
            projected["state"],
            action_id,
            read_only=repository.locate(course_id).read_only,
            approval_failures=projected.get("approval_failures"),
            prerequisites_ready=projected.get("prerequisites_ready", False),
            blocking_stage=projected.get("blocking_stage"),
            requires_reopen=projected.get("requires_reopen", False),
        )

    @app.get("/api/courses/{course_id}/research/sources/quality")
    def source_quality_projection(course_id: str) -> dict[str, Any]:
        return source_quality.project(course_id)

    @app.post("/api/courses/{course_id}/research/sources", status_code=201)
    def add_known_source(course_id: str, command: KnownSourceCommand) -> dict[str, Any]:
        with jobs.mutate_now(course_id):
            assert_projected_action(course_id, "research", "add_source")
            value = source_quality.add_known_source(
                course_id,
                expected_checksum=command.expected_checksum,
                locator=command.locator,
                title=command.title,
                publisher=command.publisher,
                trust_notes=command.trust_notes,
                relevance=command.relevance,
            )
        return {
            "artifact": value,
            "checksum": repository.checksum(value),
            "quality": source_quality.project(course_id),
        }

    @app.get("/api/courses/{course_id}/source-repairs")
    def source_repair_ledger(course_id: str) -> dict[str, Any]:
        return source_repairs.view(course_id)

    @app.post("/api/courses/{course_id}/source-repairs", status_code=202)
    def request_source_repair(
        course_id: str,
        command: SourceRepairRequestCommand,
    ) -> dict[str, Any]:
        with jobs.mutate_now(course_id):
            assert_projected_action(course_id, "content", "source_repair")
            requested = source_repairs.request(
                course_id,
                expected_content_checksum=command.expected_content_checksum,
                subtopic_id=command.subtopic_id,
                asset_id=command.asset_id,
                claim_id=command.claim_id,
                finding_id=command.finding_id,
                evidence_gap=command.evidence_gap,
                mode=command.mode,
            )
        repair_id = requested["repair_id"]
        job = jobs.submit(
            course_id=course_id,
            stage="content",
            task=lambda emit: source_repairs.research(
                course_id,
                repair_id,
                emit=emit,
            ),
        )
        return {**_job_accepted(job), "repair_id": repair_id}

    @app.post(
        "/api/courses/{course_id}/source-repairs/{repair_id}/research",
        status_code=202,
    )
    def restart_source_repair_research(course_id: str, repair_id: str) -> dict[str, Any]:
        assert_projected_action(course_id, "content", "source_repair")
        job = jobs.submit(
            course_id=course_id,
            stage="content",
            task=lambda emit: source_repairs.research(
                course_id,
                repair_id,
                emit=emit,
            ),
        )
        return {**_job_accepted(job), "repair_id": repair_id}

    @app.put("/api/courses/{course_id}/source-repairs/{repair_id}/decision")
    def decide_source_repair(
        course_id: str,
        repair_id: str,
        command: SourceRepairDecisionCommand,
    ) -> dict[str, Any]:
        with jobs.mutate_now(course_id):
            assert_projected_action(course_id, "content", "source_repair")
            return source_repairs.decide_candidate(
                course_id,
                repair_id,
                expected_checksum=command.expected_checksum,
                candidate_id=command.candidate_id,
                decision=command.decision,
                rationale=command.rationale,
            )

    @app.put("/api/courses/{course_id}/source-repairs/{repair_id}/route")
    def confirm_source_repair_route(
        course_id: str,
        repair_id: str,
        command: SourceRepairRouteCommand,
    ) -> dict[str, Any]:
        with jobs.mutate_now(course_id):
            assert_projected_action(course_id, "content", "source_repair")
            return source_repairs.confirm_route(
                course_id,
                repair_id,
                expected_checksum=command.expected_checksum,
                subtopic_ids=command.subtopic_ids,
                asset_ids=command.asset_ids,
            )

    @app.put("/api/courses/{course_id}/blueprint/decision")
    def blueprint_decision(course_id: str, command: BlueprintDecisionCommand) -> dict[str, Any]:
        with jobs.mutate_now(course_id):
            _check_artifact_version(repository, course_id, "blueprint", command.expected_checksum)
            value = decisions.save_blueprint_decision(
                course_id,
                default_asset_types=command.default_asset_types,
                default_depth=(
                    command.default_depth.model_dump(exclude_none=True)
                    if command.default_depth is not None
                    else None
                ),
                selected_asset_types=command.selected_asset_types,
                depth_overrides={
                    subtopic_id: override.model_dump(exclude_none=True)
                    for subtopic_id, override in command.depth_overrides.items()
                },
                anchor_waivers=command.anchor_waivers,
                rationale=command.rationale,
            )
        return {"artifact": value, "checksum": repository.checksum(value)}

    @app.put("/api/courses/{course_id}/lesson-plan/decision")
    def lesson_plan_decision(
        course_id: str,
        command: LessonPlanDecisionCommand,
    ) -> dict[str, Any]:
        with jobs.mutate_now(course_id):
            _check_artifact_version(
                repository,
                course_id,
                "lesson_plan",
                command.expected_checksum,
            )
            value = decisions.save_lesson_plan_decision(
                course_id,
                constraints=(
                    command.constraints.model_dump(exclude_unset=True)
                    if command.constraints is not None
                    else None
                ),
                operations=[
                    operation.model_dump(exclude_none=True) for operation in command.operations
                ],
                rationale=command.rationale,
            )
        return {"artifact": value, "checksum": repository.checksum(value)}

    @app.get("/api/courses/{course_id}/content/assets")
    def content_assets(course_id: str) -> dict[str, Any]:
        return {"assets": projector.list_assets(course_id)}

    @app.get("/api/courses/{course_id}/content/assets/{asset_id}")
    def content_asset(course_id: str, asset_id: str) -> dict[str, Any]:
        return projector.asset(course_id, asset_id)

    @app.get("/api/courses/{course_id}/content/reviews")
    def content_reviews(course_id: str) -> dict[str, Any]:
        value = repository.require(course_id, "content_review")
        return {"artifact": value, "checksum": repository.checksum(value)}

    @app.post("/api/courses/{course_id}/content/reviews/sync")
    def sync_content_reviews(course_id: str) -> dict[str, Any]:
        with jobs.mutate_now(course_id):
            content_stage = projector.stage(course_id, "content")
            capabilities.assert_action_available(
                "content",
                content_stage["state"],
                "review_asset",
                read_only=repository.locate(course_id).read_only,
                approval_failures=content_stage.get("approval_failures"),
                prerequisites_ready=content_stage.get("prerequisites_ready", False),
            )
            value = decisions.sync_content_review(course_id)
        return {"artifact": value, "checksum": repository.checksum(value)}

    @app.put("/api/courses/{course_id}/content/reviews/{asset_id}")
    def content_review(
        course_id: str, asset_id: str, command: ContentReviewCommand
    ) -> dict[str, Any]:
        with jobs.mutate_now(course_id):
            content_stage = projector.stage(course_id, "content")
            capabilities.assert_action_available(
                "content",
                content_stage["state"],
                "review_asset",
                read_only=repository.locate(course_id).read_only,
                approval_failures=content_stage.get("approval_failures"),
                prerequisites_ready=content_stage.get("prerequisites_ready", False),
            )
            _check_artifact_version(
                repository, course_id, "content_review", command.expected_checksum
            )
            value = decisions.save_content_review(
                course_id,
                asset_id,
                decision=command.decision,
                note=command.feedback,
            )
        return {"artifact": value, "checksum": repository.checksum(value)}

    @app.get("/api/courses/{course_id}/outputs/{relative_path:path}")
    def output(course_id: str, relative_path: str) -> FileResponse:
        return FileResponse(repository.output_path(course_id, relative_path))

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str) -> dict[str, Any]:
        return jobs.get(job_id)

    @app.get("/api/jobs/{job_id}/events")
    def job_events(
        job_id: str,
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    ) -> StreamingResponse:
        jobs.get(job_id)
        return StreamingResponse(
            _event_stream(jobs, job_id, after=last_event_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/api/jobs/{job_id}/events/snapshot")
    def job_event_snapshot(job_id: str) -> dict[str, Any]:
        return {"events": jobs.events(job_id)}

    # A production Vite build can be served by the same local process. During
    # development, the Vite server remains preferable for hot module reload.
    if (frontend_dist / "index.html").is_file():
        assets = frontend_dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

        @app.get("/{spa_path:path}", include_in_schema=False)
        def frontend_spa(spa_path: str) -> FileResponse:
            if spa_path == "api" or spa_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="API route not found")
            return FileResponse(frontend_dist / "index.html")

    return app


def _check_stage_version(
    projector: WorkspaceProjector,
    course_id: str,
    stage_slug: str,
    expected: str | None,
) -> None:
    if expected is None:
        return
    actual = projector.stage(course_id, stage_slug).get("checksum") or "missing"
    if actual != expected:
        raise VersionConflict(actual)


def _ensure_stage_state(
    projector: WorkspaceProjector,
    course_id: str,
    stage_slug: str,
    *,
    allowed: set[str],
) -> None:
    state = projector.stage(course_id, stage_slug)["state"]
    if state not in allowed:
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"stage {stage_slug!r} cannot run while {state!r}",
                "state": state,
                "allowed_states": sorted(allowed),
            },
        )


def _check_artifact_version(
    repository: ArtifactRepository,
    course_id: str,
    artifact_type: str,
    expected: str | None,
) -> None:
    if expected is None:
        return
    value = repository.load(course_id, artifact_type)
    actual = repository.checksum(value) if value is not None else "missing"
    if actual != expected:
        raise VersionConflict(actual)


def _job_accepted(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "job": job,
        "job_url": f"/api/jobs/{job['job_id']}",
        "events_url": f"/api/jobs/{job['job_id']}/events",
    }


def _assert_impact_acknowledged(
    preview: dict[str, Any],
    *,
    impact_acknowledged: bool,
    expected_impact_checksum: str | None,
) -> None:
    if not impact_acknowledged or expected_impact_checksum is None:
        raise ImpactConfirmationRequired(
            "Confirm the current downstream impact before starting this revision."
        )
    if preview["impact_checksum"] != expected_impact_checksum:
        raise StaleImpactPreview(
            "Downstream state changed after the impact preview; review it again."
        )


def _event_stream(jobs: LocalJobRunner, job_id: str, *, after: str | None) -> Iterator[str]:
    cursor = after
    idle_ticks = 0
    while True:
        events = jobs.events(job_id, after=cursor)
        for event in events:
            cursor = event["event_id"]
            yield (
                f"id: {cursor}\n"
                f"event: {event['event_type']}\n"
                f"data: {json.dumps(event, separators=(',', ':'))}\n\n"
            )
            idle_ticks = 0
        job = jobs.get(job_id)
        if job["status"] in {"completed", "failed", "cancelled"} and not events:
            break
        time.sleep(0.25)
        idle_ticks += 1
        if idle_ticks >= 60:
            yield ": keep-alive\n\n"
            idle_ticks = 0


def _error_response(status_code: int, message: str, *, extra: dict[str, Any] | None = None):
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status_code,
        content={"error": {"message": message, **(extra or {})}},
    )


app = create_app(
    courses_root=Path(os.environ["COURSE_BUILDER_COURSES_ROOT"])
    if os.getenv("COURSE_BUILDER_COURSES_ROOT")
    else None,
    rendered_root=Path(os.environ["COURSE_BUILDER_RENDERED_ROOT"])
    if os.getenv("COURSE_BUILDER_RENDERED_ROOT")
    else None,
    runtime_root=Path(os.environ["COURSE_BUILDER_RUNTIME_ROOT"])
    if os.getenv("COURSE_BUILDER_RUNTIME_ROOT")
    else None,
    include_examples=os.getenv("COURSE_BUILDER_INCLUDE_EXAMPLES", "true").lower()
    not in {"0", "false", "no"},
)
