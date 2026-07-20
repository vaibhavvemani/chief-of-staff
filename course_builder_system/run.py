"""Course Builder entry point for the domain-agnostic walking path."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from functools import partial
from pathlib import Path

import acceptance
import integrity
import steps
from agents import intake
from course_model_operations import carry_forward_course_model_allocation
from orchestrator import (
    Decision,
    PipelineCancelled,
    Step,
    console_approver,
    make_artifact,
    run_pipeline,
)

OUTPUT_TRANSFORMS = {"course_model": carry_forward_course_model_allocation}
StepCallable = Callable[[dict, str | None], dict]


def _implementation(
    implementations: Mapping[str, StepCallable] | None,
    name: str,
    default: StepCallable,
) -> StepCallable:
    if implementations is None:
        return default
    try:
        return implementations[name]
    except KeyError as exc:
        raise ValueError(f"pipeline implementation registry is missing {name!r}") from exc


def build_pipeline(
    *, implementations: Mapping[str, StepCallable] | None = None
) -> list[Step]:
    """The pipeline is just data: an ordered list of steps, each declaring
    what it consumes and produces. This is the spine. Phase 1+ only swaps the
    `run=` stubs for real agents. Phase 2 replaces the remaining upstream
    fixtures while preserving this ordered contract."""
    return [
        Step(
            name="course_outcomes",
            consumes=["brief"],
            produces=["course_outcomes"],
            run=_implementation(implementations, "course_outcomes", steps.course_outcomes_step),
        ),
        Step(
            name="research",
            consumes=["brief", "course_outcomes"],
            produces=["research_dossier"],
            run=_implementation(implementations, "research", steps.research_step),
        ),
        Step(
            name="structure",
            consumes=["brief", "course_outcomes", "research_dossier"],
            produces=["course_model"],
            run=_implementation(implementations, "structure", steps.structure_step),
        ),
        Step(
            name="blueprint",
            consumes=["course_model"],
            produces=["blueprint"],
            run=_implementation(implementations, "blueprint", steps.blueprint_step),
        ),
        Step(
            name="student_content",
            consumes=["course_model", "blueprint", "course_outcomes"],
            produces=["content_package"],
            run=_implementation(
                implementations, "student_content", steps.student_content_step
            ),
        ),
        Step(
            name="lesson_plan",
            consumes=["content_package", "blueprint", "course_model"],
            produces=["lesson_plan"],
            run=_implementation(implementations, "lesson_plan", steps.lesson_plan_step),
        ),
    ]


def build_sprint1_pipeline(
    *, implementations: Mapping[str, StepCallable] | None = None
) -> list[Step]:
    """Sparse request -> Brief -> Outcomes -> mocked source-selection gate."""
    return [
        Step(
            name="intake",
            consumes=["subject_request"],
            produces=["brief"],
            run=_implementation(implementations, "intake", steps.intake_step),
        ),
        Step(
            name="course_outcomes",
            consumes=["brief"],
            produces=["course_outcomes"],
            run=_implementation(implementations, "course_outcomes", steps.course_outcomes_step),
        ),
        Step(
            name="research",
            consumes=["brief", "course_outcomes"],
            produces=["research_dossier"],
            run=_implementation(implementations, "research", steps.research_step),
        ),
        Step(
            name="source_selection",
            consumes=["research_dossier"],
            produces=["approved_source_registry"],
            run=_implementation(
                implementations, "source_selection", steps.source_selection_step
            ),
        ),
    ]


def build_sprint2_pipeline(
    *,
    live_research: bool = False,
    implementations: Mapping[str, StepCallable] | None = None,
) -> list[Step]:
    """Sparse request -> approved sources -> generated Course Model/Blueprint."""
    research_run = steps.live_research_step if live_research else steps.sprint2_research_step
    return [
        Step(
            name="intake",
            consumes=["subject_request"],
            produces=["brief"],
            run=_implementation(implementations, "intake", steps.intake_step),
        ),
        Step(
            name="course_outcomes",
            consumes=["brief"],
            produces=["course_outcomes"],
            run=_implementation(implementations, "course_outcomes", steps.course_outcomes_step),
        ),
        Step(
            name="research",
            consumes=["brief", "course_outcomes"],
            produces=["research_dossier"],
            run=_implementation(implementations, "research", research_run),
        ),
        Step(
            name="source_selection",
            consumes=["research_dossier"],
            produces=["approved_source_registry"],
            run=_implementation(
                implementations, "source_selection", steps.source_selection_step
            ),
        ),
        Step(
            name="structure",
            consumes=[
                "brief",
                "course_outcomes",
                "research_dossier",
                "approved_source_registry",
            ],
            produces=["course_model"],
            run=_implementation(implementations, "structure", steps.structure_step),
        ),
        Step(
            name="blueprint",
            consumes=["course_model"],
            produces=["blueprint"],
            run=_implementation(implementations, "blueprint", steps.blueprint_step),
        ),
    ]


def build_sprint3_pipeline(
    *,
    live_research: bool = False,
    implementations: Mapping[str, StepCallable] | None = None,
) -> list[Step]:
    """Sparse request -> Markdown course folder and resumable run summary."""
    return [
        *build_sprint2_pipeline(
            live_research=live_research,
            implementations=implementations,
        ),
        Step(
            name="student_content",
            consumes=["course_model", "blueprint", "course_outcomes"],
            produces=["content_package", "content_progress"],
            run=_implementation(
                implementations, "student_content", steps.student_content_step
            ),
        ),
        Step(
            name="lesson_plan",
            consumes=["content_package", "blueprint", "course_model"],
            produces=["lesson_plan"],
            run=_implementation(implementations, "lesson_plan", steps.lesson_plan_step),
        ),
        Step(
            name="render_course_folder",
            consumes=["course_model", "blueprint", "content_package", "lesson_plan"],
            produces=["render_manifest"],
            run=_implementation(
                implementations,
                "render_course_folder",
                steps.render_course_folder_step,
            ),
        ),
        Step(
            name="run_summary",
            consumes=[
                "brief",
                "course_outcomes",
                "research_dossier",
                "approved_source_registry",
                "course_model",
                "blueprint",
                "content_package",
                "content_progress",
                "lesson_plan",
                "render_manifest",
            ],
            produces=["run_summary"],
            run=_implementation(implementations, "run_summary", steps.run_summary_step),
        ),
    ]


def build_sprint4_acceptance_pipeline(
    *,
    live_research: bool = False,
    output_root: Path = Path("rendered_courses"),
    controls: acceptance.DeterministicAcceptanceControls | None = None,
    implementations: Mapping[str, StepCallable] | None = None,
) -> list[Step]:
    """Acceptance pipeline with deterministic local content and verification."""
    return [
        *build_sprint2_pipeline(
            live_research=live_research,
            implementations=implementations,
        ),
        Step(
            name="student_content",
            consumes=["course_model", "blueprint", "course_outcomes"],
            produces=["content_package", "content_progress"],
            run=_implementation(
                implementations,
                "student_content",
                steps.make_student_content_step(
                    asset_generator=acceptance.deterministic_generate_asset,
                    package_verifier=partial(
                        acceptance.deterministic_verify_content_package,
                        controls=controls,
                    ),
                    asset_verifier=partial(
                        acceptance.deterministic_verify_asset,
                        controls=controls,
                    ),
                ),
            ),
        ),
        Step(
            name="lesson_plan",
            consumes=["content_package", "blueprint", "course_model"],
            produces=["lesson_plan"],
            run=_implementation(implementations, "lesson_plan", steps.lesson_plan_step),
        ),
        Step(
            name="render_course_folder",
            consumes=["course_model", "blueprint", "content_package", "lesson_plan"],
            produces=["render_manifest"],
            run=_implementation(
                implementations,
                "render_course_folder",
                steps.make_render_course_folder_step(output_root=output_root),
            ),
        ),
        Step(
            name="run_summary",
            consumes=[
                "brief",
                "course_outcomes",
                "research_dossier",
                "approved_source_registry",
                "course_model",
                "blueprint",
                "content_package",
                "content_progress",
                "lesson_plan",
                "render_manifest",
            ],
            produces=["run_summary"],
            run=_implementation(implementations, "run_summary", steps.run_summary_step),
        ),
    ]


def auto_approver(step_name: str, produced: dict) -> Decision:
    """Approve every checkpoint for non-interactive acceptance and smoke runs."""
    return Decision(approved=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Course Builder pipelines.")
    parser.add_argument(
        "--sprint1-demo",
        action="store_true",
        help="Run the Sprint 1 sparse-request to source-selection checkpoint.",
    )
    parser.add_argument(
        "--sprint2-demo",
        action="store_true",
        help="Run the Sprint 2 sparse-request to generated Blueprint checkpoint.",
    )
    parser.add_argument(
        "--sprint3-demo",
        action="store_true",
        help="Run the Sprint 3 sparse-request to Markdown course-folder checkpoint.",
    )
    parser.add_argument(
        "--acceptance-demo",
        action="store_true",
        help=(
            "Run the Sprint 4 local acceptance path with deterministic content and verification."
        ),
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Approve every checkpoint without prompting. Intended for tests and demos.",
    )
    parser.add_argument(
        "--live-research",
        action="store_true",
        help="Use the live bounded research provider instead of the mock provider.",
    )
    parser.add_argument("--subject", default="Coffee making")
    parser.add_argument("--course-id", default=None)
    args = parser.parse_args()
    approver = auto_approver if args.auto_approve else console_approver

    try:
        if args.acceptance_demo:
            subject_request = intake.subject_request_artifact(
                subject=args.subject,
                description=(
                    "A practical beginner course for people who want better results quickly."
                ),
                constraints=["Keep the course compact for the prototype run."],
                course_id=args.course_id or intake.slugify_course_id(args.subject),
            )
            run_pipeline(
                course_id=subject_request["course_id"],
                pipeline=build_sprint4_acceptance_pipeline(
                    live_research=args.live_research,
                ),
                seed_artifacts={"subject_request": subject_request},
                approver=approver,
                output_transforms=OUTPUT_TRANSFORMS,
            )
            if not integrity.report(subject_request["course_id"]):
                raise SystemExit(1)
            return

        if args.sprint1_demo:
            subject_request = intake.subject_request_artifact(
                subject=args.subject,
                description=(
                    "A practical beginner course for people who want better results quickly."
                ),
                constraints=["Keep the course compact for the prototype run."],
                course_id=args.course_id or intake.slugify_course_id(args.subject),
            )
            run_pipeline(
                course_id=subject_request["course_id"],
                pipeline=build_sprint1_pipeline(),
                seed_artifacts={"subject_request": subject_request},
                approver=approver,
                output_transforms=OUTPUT_TRANSFORMS,
            )
            return

        if args.sprint2_demo or args.sprint3_demo:
            subject_request = intake.subject_request_artifact(
                subject=args.subject,
                description=(
                    "A practical beginner course for people who want better results quickly."
                ),
                constraints=["Keep the course compact for the prototype run."],
                course_id=args.course_id or intake.slugify_course_id(args.subject),
            )
            run_pipeline(
                course_id=subject_request["course_id"],
                pipeline=build_sprint3_pipeline(live_research=args.live_research)
                if args.sprint3_demo
                else build_sprint2_pipeline(live_research=args.live_research),
                seed_artifacts={"subject_request": subject_request},
                approver=approver,
                output_transforms=OUTPUT_TRANSFORMS,
            )
            integrity.report(subject_request["course_id"])
            return

        course_id = "frm-demo"

        # This approved seed stands in for the conversational intake agent that will
        # ask only unresolved, high-impact clarifying questions in the full product.
        brief = make_artifact(
            course_id,
            artifact_type="brief",
            produced_by_step="human",
            body={
                "subject": "Financial Risk Management",
                "audience": "Postgraduate learners with foundational finance knowledge",
                "prior_knowledge": "Foundational finance and accounting",
                "level": "intermediate",
                "goals": "Understand, distinguish, and apply foundational financial-risk concepts",
                "scope": "Foundations of financial risk; quantitative implementation is excluded",
                "duration": "30 minutes for the Phase 1 benchmark subtopic",
                "modality": "blended",
                "language": "English",
                "jurisdiction": None,
            },
            inputs=[],
        )

        run_pipeline(
            course_id=course_id,
            pipeline=build_pipeline(),
            seed_artifacts={"brief": brief},
            approver=approver,
            output_transforms=OUTPUT_TRANSFORMS,
        )

        # Cheap guard that Course Model hierarchy/source references remain sound.
        integrity.report(course_id)
    except PipelineCancelled as exc:
        print(
            f"\n[cancelled] Stopped at '{exc.step_name}'. "
            "Rerun the same command to resume from approved checkpoints."
        )
        return


if __name__ == "__main__":
    main()
