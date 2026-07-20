"""Deterministic server-side approval gates for every product stage."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from agents import content_review, lesson_plan
from agents import outcomes as outcomes_agent
from api.services.artifact_repository import ArtifactRepository
from api.services.brief_intake import BriefIntakeService
from api.services.pipeline_catalog import PipelineCatalog
from course_model_integrity import validate_course_model_semantics
from course_model_operations import (
    CourseModelValidationError,
    validate_course_model_candidate,
)


def hard_verifier_blocker_count(asset: dict[str, Any]) -> int:
    """Count current claim-level blockers and reject stale verifier summaries.

    ``partial`` remains a human-review item. Unsupported attributed claims,
    ungrounded claims, unattributed verifier findings, missing verification, and a
    summary that no longer reconciles to the current claims are hard blockers.
    """
    verification = asset.get("verification")
    claims = asset.get("claims")
    if (
        not isinstance(verification, dict)
        or not verification.get("checked_at")
        or not isinstance(claims, list)
    ):
        return 1

    supported = 0
    partial = 0
    unsupported = 0
    ungrounded = 0
    for claim in claims:
        if not isinstance(claim, dict):
            unsupported += 1
            continue
        source_id = claim.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            ungrounded += 1
            continue
        support = claim.get("support")
        if support == "supported":
            supported += 1
        elif support == "partial":
            partial += 1
        else:
            unsupported += 1

    unattributed = verification.get("unattributed_found")
    if not isinstance(unattributed, list):
        return max(1, unsupported + ungrounded)
    summary_reconciles = all(
        type(verification.get(field)) is int and verification[field] == expected
        for field, expected in {
            "supported": supported,
            "partial": partial,
            "unsupported": unsupported,
            "ungrounded": ungrounded,
        }.items()
    )
    return unsupported + ungrounded + len(unattributed) + (0 if summary_reconciles else 1)


@dataclass(frozen=True)
class GuardFailure:
    code: str
    message: str
    stage: str
    artifact_type: str | None = None
    record_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["record_ids"] = list(self.record_ids)
        return value


class ApprovalGuardFailed(RuntimeError):
    def __init__(self, stage: str, failures: list[GuardFailure]) -> None:
        super().__init__(f"{stage} approval failed {len(failures)} guard(s)")
        self.stage = stage
        self.failures = failures


class ApprovalGuardService:
    def __init__(
        self,
        repository: ArtifactRepository,
        catalog: PipelineCatalog,
        *,
        brief_intake: BriefIntakeService | None = None,
    ) -> None:
        self.repository = repository
        self.catalog = catalog
        self.brief_intake = brief_intake or BriefIntakeService()

    def failures(self, course_id: str, stage_slug: str) -> list[GuardFailure]:
        stage = self.catalog.stage(stage_slug)
        failures: list[GuardFailure] = []
        missing_required_artifact = False
        for artifact_type in stage.artifacts:
            artifact = self.repository.load(course_id, artifact_type)
            if artifact is None:
                missing_required_artifact = True
                failures.append(
                    GuardFailure(
                        "missing_stage_output",
                        f"{stage.label} is missing {artifact_type}.",
                        stage_slug,
                        artifact_type,
                    )
                )
            elif artifact.get("status") == "stale":
                failures.append(
                    GuardFailure(
                        "stale_stage_output",
                        f"{artifact_type} is stale and must be rerun.",
                        stage_slug,
                        artifact_type,
                    )
                )
        for artifact_type in self.catalog.prerequisites_for_stage(stage_slug):
            artifact = self.repository.load(course_id, artifact_type)
            if artifact is None or artifact.get("status") != "approved":
                missing_required_artifact = missing_required_artifact or artifact is None
                failures.append(
                    GuardFailure(
                        "prerequisite_not_approved",
                        f"{artifact_type} must be approved and current.",
                        stage_slug,
                        artifact_type,
                    )
                )
        if self.catalog.stage_depends_on_artifact(stage_slug, "brief"):
            subject = self.repository.load(course_id, "subject_request")
            brief = self.repository.load(course_id, "brief")
            brief_ready = (
                subject is not None
                and brief is not None
                and self.brief_intake.is_approved_and_resolved(subject, brief)
            )
            if not brief_ready and not any(
                failure.code == "prerequisite_not_approved" and failure.artifact_type == "brief"
                for failure in failures
            ):
                failures.append(
                    GuardFailure(
                        "prerequisite_not_approved",
                        "brief must be approved, current, and fully resolved.",
                        stage_slug,
                        "brief",
                    )
                )
        # A preserved stale/draft prerequisite can still be inspected by the
        # stage-specific guard.  Report its substantive blockers alongside the
        # lifecycle failure so an operator knows what must actually be repaired.
        # Missing artifacts are the only case where a body guard cannot run.
        if missing_required_artifact:
            return self._deduplicate(failures)

        guard = getattr(self, f"_guard_{stage_slug.replace('-', '_')}")
        failures.extend(guard(course_id))
        return self._deduplicate(failures)

    def assert_can_approve(self, course_id: str, stage_slug: str) -> None:
        failures = self.failures(course_id, stage_slug)
        if failures:
            raise ApprovalGuardFailed(stage_slug, failures)

    def _guard_brief(self, course_id: str) -> list[GuardFailure]:
        subject = self.repository.require(course_id, "subject_request")
        brief = self.repository.require(course_id, "brief")
        body = self.brief_intake.normalize_artifact(subject, brief).get("body", {})
        required = (
            "subject",
            "audience",
            "purpose",
            "prior_knowledge",
            "level",
            "duration",
            "modality",
            "language",
        )
        missing = [field for field in required if not self._present(body.get(field))]
        intake = body.get("intake_state", {})
        raw_unresolved = (
            intake.get("unresolved_required_fields", []) if isinstance(intake, dict) else []
        )
        unresolved = (
            raw_unresolved if isinstance(raw_unresolved, list) else ["invalid_intake_state"]
        )
        conflicts = intake.get("last_gap_analysis", []) if isinstance(intake, dict) else []
        high_conflicts = [
            str(item.get("id") or item.get("field") or "brief_conflict")
            for item in conflicts
            if isinstance(item, dict) and item.get("severity") == "high"
        ]
        failures: list[GuardFailure] = []
        if isinstance(intake, dict) and intake:
            raw_explicit = intake.get("explicit_fields", [])
            raw_defaults = intake.get("accepted_default_fields", [])
            explicit = set(raw_explicit) if isinstance(raw_explicit, list) else set()
            accepted_defaults = set(raw_defaults) if isinstance(raw_defaults, list) else set()
            if "language" not in explicit | accepted_defaults:
                unresolved = [*unresolved, "language_default_acceptance"]
        if missing or unresolved:
            ids = tuple(sorted({*missing, *(str(item) for item in unresolved)}))
            failures.append(
                GuardFailure(
                    "brief_input_incomplete",
                    "Resolve all mandatory Brief fields before approval.",
                    "brief",
                    "brief",
                    ids,
                )
            )
        if high_conflicts:
            failures.append(
                GuardFailure(
                    "brief_conflict",
                    "Resolve high-severity Brief conflicts before approval.",
                    "brief",
                    "brief",
                    tuple(high_conflicts),
                )
            )
        return failures

    def _guard_outcomes(self, course_id: str) -> list[GuardFailure]:
        body = self.repository.require(course_id, "course_outcomes").get("body", {})
        collection = body.get("outcomes", [])
        try:
            outcomes_agent.validate_outcome_collection(collection)
        except outcomes_agent.OutcomeDecisionValidationError as exc:
            record_ids = tuple(
                sorted(
                    {str(issue["outcome_id"]) for issue in exc.issues if issue.get("outcome_id")}
                )
            )
            if any(issue["code"] == "outcomes_empty" for issue in exc.issues):
                return [
                    GuardFailure(
                        "outcomes_empty",
                        "At least one valid Course Outcome is required.",
                        "outcomes",
                        "course_outcomes",
                    )
                ]
            return [
                GuardFailure(
                    "outcomes_invalid",
                    (
                        "Course Outcomes must have unique valid IDs, statements, evidence, "
                        "cognitive levels, priorities, and ordering."
                    ),
                    "outcomes",
                    "course_outcomes",
                    record_ids,
                )
            ]
        cursor = body.get("next_outcome_id")
        if cursor is not None and (
            type(cursor) is not int or cursor < outcomes_agent.next_outcome_id(collection)
        ):
            return [
                GuardFailure(
                    "outcomes_invalid",
                    "Course Outcomes have an invalid canonical ID allocation cursor.",
                    "outcomes",
                    "course_outcomes",
                )
            ]
        return []

    def _guard_research(self, course_id: str) -> list[GuardFailure]:
        registry = self.repository.require(course_id, "approved_source_registry").get("body", {})
        decision = registry.get("decision", {})
        selected = set(decision.get("selected_ids", [])) if isinstance(decision, dict) else set()
        approved = set(decision.get("approved_ids", [])) if isinstance(decision, dict) else set()
        sources = registry.get("source_registry", [])
        source_ids = {
            item.get("id")
            for item in sources
            if isinstance(item, dict) and self._present(item.get("content_ref"))
        }
        if selected and selected == approved == source_ids:
            return []
        return [
            GuardFailure(
                "source_decision_invalid",
                "Save at least one explicit, available, content-bearing source decision.",
                "research",
                "approved_source_registry",
                tuple(sorted(str(item) for item in selected | approved | source_ids)),
            )
        ]

    def _guard_course_model(self, course_id: str) -> list[GuardFailure]:
        course_model = self.repository.require(course_id, "course_model")
        try:
            validate_course_model_candidate(
                course_model,
                course_outcomes=self.repository.require(course_id, "course_outcomes"),
                research_dossier=self.repository.require(course_id, "research_dossier"),
                approved_source_registry=self.repository.require(
                    course_id, "approved_source_registry"
                ),
            )
        except CourseModelValidationError as exc:
            return [
                GuardFailure(
                    "referential_integrity_failed",
                    (
                        f"{issue['path']}: {issue['message']}"
                        if issue.get("path")
                        else str(issue["message"])
                    ),
                    "course-model",
                    "course_model",
                    tuple([str(issue["record_id"])] if issue.get("record_id") else []),
                )
                for issue in exc.issues
            ]
        return []

    def _guard_blueprint(self, course_id: str) -> list[GuardFailure]:
        course_model = self.repository.require(course_id, "course_model")
        blueprint = self.repository.require(course_id, "blueprint")
        errors = validate_course_model_semantics(
            course_model,
            course_outcomes=self.repository.load(course_id, "course_outcomes"),
            research_dossier=self.repository.load(course_id, "research_dossier"),
            approved_source_registry=self.repository.load(course_id, "approved_source_registry"),
            blueprint=blueprint,
        )
        expected = {
            subtopic.get("id")
            for module in course_model.get("body", {}).get("modules", [])
            for subtopic in module.get("subtopics", [])
            if isinstance(subtopic, dict) and subtopic.get("id")
        }
        actual = {
            plan.get("subtopic_id")
            for plan in blueprint.get("body", {}).get("subtopic_plans", [])
            if isinstance(plan, dict) and plan.get("subtopic_id")
        }
        if expected != actual:
            errors.append("Blueprint must contain exactly one plan for every Course Model subtopic")
        failures = self._integrity_failures("blueprint", "blueprint", errors)
        failures.extend(self._course_model_source_failures(course_id, "blueprint"))
        return failures

    def _guard_content(self, course_id: str) -> list[GuardFailure]:
        package = self.repository.require(course_id, "content_package")
        progress = self.repository.require(course_id, "content_progress")
        blueprint = self.repository.require(course_id, "blueprint")
        selected = {
            asset.get("id")
            for plan in blueprint.get("body", {}).get("subtopic_plans", [])
            for asset in plan.get("asset_plan", [])
            if isinstance(asset, dict)
            and asset.get("selection_status") == "selected"
            and asset.get("id")
        }
        generated = {
            asset.get("id")
            for subtopic in package.get("body", {}).get("subtopics", [])
            for asset in subtopic.get("assets", [])
            if isinstance(asset, dict) and asset.get("id")
        }
        generated_ids = [
            str(asset.get("id"))
            for subtopic in package.get("body", {}).get("subtopics", [])
            for asset in subtopic.get("assets", [])
            if isinstance(asset, dict) and asset.get("id")
        ]
        failures: list[GuardFailure] = []
        if selected != generated:
            failures.append(
                GuardFailure(
                    "content_selection_mismatch",
                    "Selected and generated Content assets do not reconcile.",
                    "content",
                    "content_package",
                    tuple(sorted(str(item) for item in selected ^ generated)),
                )
            )
        duplicate_assets = sorted(
            {asset_id for asset_id in generated_ids if generated_ids.count(asset_id) > 1}
        )
        if duplicate_assets:
            failures.append(
                GuardFailure(
                    "content_asset_ids_invalid",
                    "Generated Content asset IDs must be unique.",
                    "content",
                    "content_package",
                    tuple(duplicate_assets),
                )
            )
        units = progress.get("body", {}).get("units", [])
        incomplete = [
            str(unit.get("asset_id") or unit.get("subtopic_id") or "unknown")
            for unit in units
            if isinstance(unit, dict)
            and unit.get("status") in {"failed", "pending", "evidence_gap"}
        ]
        if not progress.get("body", {}).get("complete", False) or incomplete:
            failures.append(
                GuardFailure(
                    "content_generation_incomplete",
                    "All selected Content units must complete successfully.",
                    "content",
                    "content_progress",
                    tuple(incomplete),
                )
            )
        blockers = self._content_blockers(package)
        if blockers:
            failures.append(
                GuardFailure(
                    "hard_verifier_blockers",
                    "Resolve unsupported, ungrounded, and unattributed claims.",
                    "content",
                    "content_package",
                    tuple(sorted(blockers)),
                )
            )
        review = self.repository.load(course_id, "content_review")
        if review is None:
            failures.append(
                GuardFailure(
                    "content_review_missing",
                    "Synchronize and complete the human Content review.",
                    "content",
                    "content_review",
                )
            )
            return failures
        review_records = {
            item.get("asset_id"): item
            for item in review.get("body", {}).get("assets", [])
            if isinstance(item, dict) and item.get("asset_id")
        }
        current_assets = {
            asset.get("id"): asset
            for subtopic in package.get("body", {}).get("subtopics", [])
            for asset in subtopic.get("assets", [])
            if isinstance(asset, dict) and asset.get("id")
        }
        pending = []
        for asset_id, asset in current_assets.items():
            record = review_records.get(asset_id)
            if (
                record is None
                or record.get("asset_fingerprint") != content_review.asset_fingerprint(asset)
                or record.get("decision") != "approved"
            ):
                pending.append(str(asset_id))
        if set(review_records) != set(current_assets):
            pending.extend(str(item) for item in set(review_records) ^ set(current_assets))
        summary = review.get("body", {}).get("summary", {})
        if pending or not isinstance(summary, dict) or not summary.get("ready_for_package"):
            failures.append(
                GuardFailure(
                    "content_review_incomplete",
                    "Every current Content asset requires an approved human review.",
                    "content",
                    "content_review",
                    tuple(sorted(set(pending))),
                )
            )
        return failures

    def _guard_lesson_plan(self, course_id: str) -> list[GuardFailure]:
        package = self.repository.require(course_id, "content_package")
        blueprint = self.repository.require(course_id, "blueprint")
        course_model = self.repository.require(course_id, "course_model")
        expected = lesson_plan.course_model_subtopic_ids(course_model)
        body = self.repository.require(course_id, "lesson_plan").get("body", {})
        errors = lesson_plan.validate_lesson_plan_inputs(
            course_model=course_model,
            blueprint=blueprint,
            content_package=package,
        )
        errors.extend(
            lesson_plan.validate_lesson_plan_body(
                body,
                expected_subtopic_ids=expected,
            )
        )
        constraints = body.get("session_constraints", {})
        if not isinstance(constraints, dict):
            errors.append("Lesson Plan session constraints must be an object")
        else:
            max_hours = constraints.get("max_session_hours")
            if (
                not isinstance(max_hours, int | float)
                or isinstance(max_hours, bool)
                or max_hours <= 0
            ):
                errors.append("Lesson Plan max_session_hours must be positive")
            if constraints.get("default_mode") not in lesson_plan.VALID_MODES:
                errors.append("Lesson Plan default_mode must be live or self_study")
        unresolved = body.get("unresolved_session_constraints", [])
        if not isinstance(unresolved, list):
            errors.append("Lesson Plan unresolved constraints must be a list")
        return self._integrity_failures("lesson-plan", "lesson_plan", errors)

    def _guard_package(self, course_id: str) -> list[GuardFailure]:
        failures = self._guard_content(course_id)
        package = self.repository.require(course_id, "content_package")
        blueprint = self.repository.require(course_id, "blueprint")
        manifest = self.repository.require(course_id, "render_manifest")
        selected = {
            asset.get("id")
            for plan in blueprint.get("body", {}).get("subtopic_plans", [])
            for asset in plan.get("asset_plan", [])
            if isinstance(asset, dict)
            and asset.get("selection_status") == "selected"
            and asset.get("id")
        }
        generated = {
            asset.get("id")
            for subtopic in package.get("body", {}).get("subtopics", [])
            for asset in subtopic.get("assets", [])
            if isinstance(asset, dict) and asset.get("id")
        }
        paths = manifest.get("body", {}).get("paths", {})
        rendered = set(paths.get("assets", {})) if isinstance(paths, dict) else set()
        if not selected == generated == rendered:
            failures.append(
                GuardFailure(
                    "package_asset_mismatch",
                    "Selected, generated, and rendered assets do not reconcile.",
                    "package",
                    "render_manifest",
                    tuple(sorted(str(item) for item in selected ^ generated ^ rendered)),
                )
            )
        registry = self.repository.require(course_id, "approved_source_registry")
        decision = registry.get("body", {}).get("decision", {})
        explicitly_approved = (
            set(decision.get("approved_ids", [])) if isinstance(decision, dict) else set()
        )
        content_bearing = {
            source.get("id")
            for source in registry.get("body", {}).get("source_registry", [])
            if isinstance(source, dict) and self._present(source.get("content_ref"))
        }
        approved = explicitly_approved & content_bearing
        leaked = {
            source_id
            for subtopic in package.get("body", {}).get("subtopics", [])
            for asset in subtopic.get("assets", [])
            for source_id in asset.get("sources", [])
            if source_id not in approved
        }
        if leaked:
            failures.append(
                GuardFailure(
                    "rejected_source_leakage",
                    "Package content contains a source that is not approved.",
                    "package",
                    "content_package",
                    tuple(sorted(str(item) for item in leaked)),
                )
            )
        integrity_failures = [
            *self._guard_blueprint(course_id),
            *self._guard_lesson_plan(course_id),
        ]
        failures.extend(
            GuardFailure(
                failure.code,
                failure.message,
                "package",
                failure.artifact_type,
                failure.record_ids,
            )
            for failure in integrity_failures
        )
        return failures

    def _course_model_source_failures(self, course_id: str, stage: str) -> list[GuardFailure]:
        registry = self.repository.require(course_id, "approved_source_registry")
        decision = registry.get("body", {}).get("decision", {})
        approved_ids = (
            set(decision.get("approved_ids", [])) if isinstance(decision, dict) else set()
        )
        content_bearing = {
            source.get("id")
            for source in registry.get("body", {}).get("source_registry", [])
            if isinstance(source, dict) and self._present(source.get("content_ref"))
        }
        allowed = approved_ids & content_bearing
        model_sources = {
            source.get("id")
            for source in self.repository.require(course_id, "course_model")
            .get("body", {})
            .get("source_registry", [])
            if isinstance(source, dict) and source.get("id")
        }
        invalid = tuple(sorted(str(item) for item in model_sources - allowed))
        if not invalid:
            return []
        return [
            GuardFailure(
                "source_reference_invalid",
                "Course Model sources must be explicitly approved and content-bearing.",
                stage,
                "course_model",
                invalid,
            )
        ]

    @staticmethod
    def _content_blockers(package: dict[str, Any]) -> set[str]:
        blockers: set[str] = set()
        for subtopic in package.get("body", {}).get("subtopics", []):
            for asset in subtopic.get("assets", []):
                if isinstance(asset, dict) and hard_verifier_blocker_count(asset):
                    blockers.add(str(asset.get("id") or "unknown"))
        return blockers

    @staticmethod
    def _integrity_failures(
        stage: str, artifact_type: str, errors: list[str]
    ) -> list[GuardFailure]:
        return [
            GuardFailure(
                "referential_integrity_failed",
                error,
                stage,
                artifact_type,
            )
            for error in errors
        ]

    @staticmethod
    def _present(value: Any) -> bool:
        return isinstance(value, str) and bool(value.strip())

    @staticmethod
    def _deduplicate(failures: list[GuardFailure]) -> list[GuardFailure]:
        result: list[GuardFailure] = []
        seen: set[tuple[Any, ...]] = set()
        for failure in failures:
            key = (
                failure.code,
                failure.stage,
                failure.artifact_type,
                failure.record_ids,
                failure.message,
            )
            if key not in seen:
                seen.add(key)
                result.append(failure)
        return result
