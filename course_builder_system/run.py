"""Course Builder entry point for the domain-agnostic walking path."""

from __future__ import annotations

import integrity
import steps
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


def main() -> None:
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
