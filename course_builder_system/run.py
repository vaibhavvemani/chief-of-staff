"""
Course Builder - Phase 0 entry point.

Run with:   python run.py

Produces a complete placeholder course folder under courses/<course_id>/,
pausing for your approval after each step.
"""

from __future__ import annotations

import integrity
import steps
from orchestrator import Step, make_artifact, run_pipeline, console_approver


def build_pipeline() -> list[Step]:
    """The pipeline is just data: an ordered list of steps, each declaring
    what it consumes and produces. This is the spine. Phase 1+ only swaps the
    `run=` stubs for real agents."""
    return [
        Step(
            name="structure",
            consumes=["brief"],
            produces=["domain_model", "toc"],
            run=steps.structure_step,
        ),
        Step(
            name="blueprint",
            consumes=["toc", "domain_model"],
            produces=["blueprint"],
            run=steps.blueprint_step,
        ),
        Step(
            name="student_content",
            consumes=["toc", "blueprint", "domain_model"],
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

    # The human's intent is itself an artifact: the seed input to Step 1.
    brief = make_artifact(
        course_id,
        artifact_type="brief",
        produced_by_step="human",
        body={
            "subject": "Financial Risk Management",
            "audience": "PG",
            "level": "intermediate",
            "goals": "<what the course should achieve>",
            "scope": "<in / out of scope>",
        },
        inputs=[],
    )

    run_pipeline(
        course_id=course_id,
        pipeline=build_pipeline(),
        seed_artifacts={"brief": brief},
        approver=console_approver,
    )

    # Cheap guard that the data contracts held: every Blueprint / Content
    # Package / Lesson Plan reference must resolve to a TOC id (Handoff 7.1).
    integrity.report(course_id)


if __name__ == "__main__":
    main()
