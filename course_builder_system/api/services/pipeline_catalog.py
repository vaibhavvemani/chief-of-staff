"""Map the existing executable pipeline to the eight product stages."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from orchestrator import Step


@dataclass(frozen=True)
class StageDefinition:
    slug: str
    label: str
    step_names: tuple[str, ...]
    artifacts: tuple[str, ...]
    prerequisite_artifacts: tuple[str, ...]


STAGES: tuple[StageDefinition, ...] = (
    StageDefinition("brief", "Brief", ("intake",), ("brief",), ("subject_request",)),
    StageDefinition(
        "outcomes",
        "Outcomes",
        ("course_outcomes",),
        ("course_outcomes",),
        ("brief",),
    ),
    StageDefinition(
        "research",
        "Research & Sources",
        ("research", "source_selection"),
        ("research_dossier", "approved_source_registry"),
        ("brief", "course_outcomes"),
    ),
    StageDefinition(
        "course-model",
        "Course Model",
        ("structure",),
        ("course_model",),
        ("brief", "course_outcomes", "research_dossier", "approved_source_registry"),
    ),
    StageDefinition(
        "blueprint", "Blueprint", ("blueprint",), ("blueprint",), ("course_model",)
    ),
    StageDefinition(
        "content",
        "Student Content",
        ("student_content",),
        ("content_package", "content_progress"),
        ("course_model", "blueprint", "course_outcomes"),
    ),
    StageDefinition(
        "lesson-plan",
        "Lesson Plan",
        ("lesson_plan",),
        ("lesson_plan",),
        ("content_package", "blueprint", "course_model"),
    ),
    StageDefinition(
        "package",
        "Package",
        ("render_course_folder", "run_summary"),
        ("render_manifest", "run_summary"),
        ("course_model", "blueprint", "content_package", "content_progress", "lesson_plan"),
    ),
)


class PipelineCatalog:
    """A read-only view over the pipeline data already assembled by ``run.py``."""

    def __init__(self, *, rendered_root: Path | None = None) -> None:
        self.rendered_root = rendered_root or Path("rendered_courses")
        self._by_slug = {stage.slug: stage for stage in STAGES}

    @property
    def stages(self) -> tuple[StageDefinition, ...]:
        return STAGES

    def stage(self, slug: str) -> StageDefinition:
        try:
            return self._by_slug[slug]
        except KeyError as exc:
            raise ValueError(f"unknown product stage: {slug!r}") from exc

    def executable_steps(self, *, mode: str = "deterministic") -> dict[str, Step]:
        # Import lazily so read-only projection does not initialize agent clients.
        import run

        if mode == "deterministic":
            pipeline = run.build_sprint4_acceptance_pipeline(output_root=self.rendered_root)
        elif mode == "live":
            pipeline = run.build_sprint3_pipeline(live_research=True)
        else:
            raise ValueError(f"unknown stage-run mode: {mode!r}")
        return {step.name: step for step in pipeline}

    def steps_for_stage(self, slug: str, *, mode: str = "deterministic") -> list[Step]:
        stage = self.stage(slug)
        by_name = self.executable_steps(mode=mode)
        return [by_name[name] for name in stage.step_names]
