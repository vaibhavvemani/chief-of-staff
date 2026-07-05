"""Course Builder entry point for the domain-agnostic walking path."""

from __future__ import annotations

import argparse

import integrity
import steps
from agents import intake
from orchestrator import Step, console_approver, make_artifact, run_pipeline


def build_pipeline() -> list[Step]:
    """The pipeline is just data: an ordered list of steps, each declaring
    what it consumes and produces. This is the spine. Phase 1+ only swaps the
    `run=` stubs for real agents. Phase 2 replaces the remaining upstream
    fixtures while preserving this ordered contract."""
    return [
        Step(
            name="course_outcomes",
            consumes=["brief"],
            produces=["course_outcomes"],
            run=steps.course_outcomes_step,
        ),
        Step(
            name="research",
            consumes=["brief", "course_outcomes"],
            produces=["research_dossier"],
            run=steps.research_step,
        ),
        Step(
            name="structure",
            consumes=["brief", "course_outcomes", "research_dossier"],
            produces=["course_model"],
            run=steps.structure_step,
        ),
        Step(
            name="blueprint",
            consumes=["course_model"],
            produces=["blueprint"],
            run=steps.blueprint_step,
        ),
        Step(
            name="student_content",
            consumes=["course_model", "blueprint", "course_outcomes"],
            produces=["content_package"],
            run=steps.student_content_step,
        ),
        Step(
            name="lesson_plan",
            consumes=["content_package", "blueprint"],
            produces=["lesson_plan"],
            run=steps.lesson_plan_step,
        ),
    ]


def build_sprint1_pipeline() -> list[Step]:
    """Sparse request -> Brief -> Outcomes -> mocked source-selection gate."""
    return [
        Step(
            name="intake",
            consumes=["subject_request"],
            produces=["brief"],
            run=steps.intake_step,
        ),
        Step(
            name="course_outcomes",
            consumes=["brief"],
            produces=["course_outcomes"],
            run=steps.course_outcomes_step,
        ),
        Step(
            name="research",
            consumes=["brief", "course_outcomes"],
            produces=["research_dossier"],
            run=steps.research_step,
        ),
        Step(
            name="source_selection",
            consumes=["research_dossier"],
            produces=["approved_source_registry"],
            run=steps.source_selection_step,
        ),
    ]


def build_sprint2_pipeline(*, live_research: bool = False) -> list[Step]:
    """Sparse request -> approved sources -> generated Course Model/Blueprint."""
    research_run = steps.live_research_step if live_research else steps.sprint2_research_step
    return [
        Step(
            name="intake",
            consumes=["subject_request"],
            produces=["brief"],
            run=steps.intake_step,
        ),
        Step(
            name="course_outcomes",
            consumes=["brief"],
            produces=["course_outcomes"],
            run=steps.course_outcomes_step,
        ),
        Step(
            name="research",
            consumes=["brief", "course_outcomes"],
            produces=["research_dossier"],
            run=research_run,
        ),
        Step(
            name="source_selection",
            consumes=["research_dossier"],
            produces=["approved_source_registry"],
            run=steps.source_selection_step,
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
            run=steps.structure_step,
        ),
        Step(
            name="blueprint",
            consumes=["course_model"],
            produces=["blueprint"],
            run=steps.blueprint_step,
        ),
    ]


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
        "--live-research",
        action="store_true",
        help="Use the live bounded research provider for Sprint 2 instead of the mock provider.",
    )
    parser.add_argument("--subject", default="Coffee making")
    parser.add_argument("--course-id", default=None)
    args = parser.parse_args()

    if args.sprint1_demo:
        subject_request = intake.subject_request_artifact(
            subject=args.subject,
            description=("A practical beginner course for people who want better results quickly."),
            constraints=["Keep the course compact for the prototype run."],
            course_id=args.course_id or intake.slugify_course_id(args.subject),
        )
        run_pipeline(
            course_id=subject_request["course_id"],
            pipeline=build_sprint1_pipeline(),
            seed_artifacts={"subject_request": subject_request},
            approver=console_approver,
        )
        return

    if args.sprint2_demo:
        subject_request = intake.subject_request_artifact(
            subject=args.subject,
            description=("A practical beginner course for people who want better results quickly."),
            constraints=["Keep the course compact for the prototype run."],
            course_id=args.course_id or intake.slugify_course_id(args.subject),
        )
        run_pipeline(
            course_id=subject_request["course_id"],
            pipeline=build_sprint2_pipeline(live_research=args.live_research),
            seed_artifacts={"subject_request": subject_request},
            approver=console_approver,
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
        approver=console_approver,
    )

    # Cheap guard that Course Model hierarchy/source references remain sound.
    integrity.report(course_id)


if __name__ == "__main__":
    main()
