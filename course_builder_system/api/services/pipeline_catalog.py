"""Map the existing executable pipeline to the eight product stages."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

from orchestrator import Step


@dataclass(frozen=True)
class StageDefinition:
    slug: str
    label: str
    step_names: tuple[str, ...]
    artifacts: tuple[str, ...]


@dataclass(frozen=True)
class RevisionCapability:
    """One bounded revision handler that is actually implemented."""

    target_type: str
    categories: tuple[str, ...]


@dataclass(frozen=True)
class StageCapabilities:
    """Registered domain operations for one product stage.

    State-specific availability is calculated by ``StageCapabilityService``.  This
    registry only answers whether a command has a real backend implementation.
    """

    direct_actions: tuple[str, ...] = ()
    revisions: tuple[RevisionCapability, ...] = ()


STAGES: tuple[StageDefinition, ...] = (
    StageDefinition("brief", "Brief", ("intake",), ("brief",)),
    StageDefinition(
        "outcomes",
        "Outcomes",
        ("course_outcomes",),
        ("course_outcomes",),
    ),
    StageDefinition(
        "research",
        "Research & Sources",
        # Source selection is a typed human decision in the workspace. The CLI
        # pipelines may still use their deterministic fallback for unattended
        # acceptance runs, but an interactive stage run must stop at candidates.
        ("research",),
        ("research_dossier", "approved_source_registry"),
    ),
    StageDefinition(
        "course-model",
        "Course Model",
        ("structure",),
        ("course_model",),
    ),
    StageDefinition("blueprint", "Blueprint", ("blueprint",), ("blueprint",)),
    StageDefinition(
        "content",
        "Student Content",
        ("student_content",),
        ("content_package", "content_progress"),
    ),
    StageDefinition(
        "lesson-plan",
        "Lesson Plan",
        ("lesson_plan",),
        ("lesson_plan",),
    ),
    StageDefinition(
        "package",
        "Package",
        ("render_course_folder", "run_summary"),
        ("render_manifest", "run_summary"),
    ),
)


# Support artifacts are canonical domain state even though they are not produced by
# the CLI Step list.  Keeping these edges in the catalog gives the backend one graph
# while leaving the orchestrator and React unaware of artifact bodies.
SUPPORT_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "content_package": ("content_review",),
    "content_review": ("render_manifest", "run_summary"),
}

SUPPORT_ARTIFACT_STAGES: dict[str, str] = {
    "content_review": "content",
    "source_repair": "content",
}

STAGE_CAPABILITIES: dict[str, StageCapabilities] = {
    "brief": StageCapabilities(direct_actions=("edit",)),
    "outcomes": StageCapabilities(direct_actions=("edit",)),
    "research": StageCapabilities(direct_actions=("source_decision", "add_source")),
    "course-model": StageCapabilities(direct_actions=("edit",)),
    "blueprint": StageCapabilities(direct_actions=("edit",)),
    "content": StageCapabilities(
        direct_actions=("review_asset", "source_repair"),
        revisions=(
            RevisionCapability(
                target_type="asset",
                categories=("clarity", "depth", "evidence"),
            ),
        ),
    ),
    "lesson-plan": StageCapabilities(direct_actions=("edit",)),
    "package": StageCapabilities(),
}


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

    def pipeline_steps(self, *, mode: str = "deterministic") -> list[Step]:
        """Return the ordered executable contract used to derive dependencies."""
        # Import lazily so projection and tests do not initialize live clients.
        import run

        if mode == "deterministic":
            return run.build_sprint4_acceptance_pipeline(output_root=self.rendered_root)
        if mode == "live":
            return run.build_sprint3_pipeline(live_research=True)
        raise ValueError(f"unknown stage-run mode: {mode!r}")

    def steps_for_stage(self, slug: str, *, mode: str = "deterministic") -> list[Step]:
        stage = self.stage(slug)
        by_name = self.executable_steps(mode=mode)
        return [by_name[name] for name in stage.step_names]

    def prerequisites_for_stage(
        self, slug: str, *, mode: str = "deterministic"
    ) -> tuple[str, ...]:
        """Derive external stage inputs from its declared ``Step`` contracts."""
        steps = self.steps_for_stage(slug, mode=mode)
        produced = {artifact for step in steps for artifact in step.produces}
        consumed = {
            artifact
            for step in steps
            for artifact in step.consumes
            if artifact not in produced
        }
        return tuple(sorted(consumed))

    def artifact_dependencies(
        self, *, mode: str = "deterministic"
    ) -> dict[str, tuple[str, ...]]:
        """Return the authoritative artifact dependency graph.

        Edges are derived from the pipeline's ``consumes``/``produces`` values.
        Explicit support-artifact edges live alongside the catalog rather than in a
        decision service or client component.
        """
        graph: dict[str, set[str]] = defaultdict(set)
        for step in self.pipeline_steps(mode=mode):
            for consumed in step.consumes:
                graph[consumed].update(step.produces)
            for produced in step.produces:
                graph.setdefault(produced, set())
        for consumed, produced_values in SUPPORT_DEPENDENCIES.items():
            graph[consumed].update(produced_values)
            for produced in produced_values:
                graph.setdefault(produced, set())
        return {
            artifact: tuple(sorted(dependents))
            for artifact, dependents in sorted(graph.items())
        }

    def downstream_artifacts(
        self,
        changed_artifacts: tuple[str, ...] | list[str] | set[str],
        *,
        mode: str = "deterministic",
    ) -> tuple[str, ...]:
        """Walk the catalog graph and return transitive descendants only."""
        changed = set(changed_artifacts)
        graph = self.artifact_dependencies(mode=mode)
        queue = deque(sorted(changed))
        downstream: set[str] = set()
        while queue:
            current = queue.popleft()
            for dependent in graph.get(current, ()):
                if dependent in changed or dependent in downstream:
                    continue
                downstream.add(dependent)
                queue.append(dependent)
        return tuple(sorted(downstream))

    def stage_depends_on_artifact(
        self,
        stage_slug: str,
        artifact_type: str,
        *,
        mode: str = "deterministic",
    ) -> bool:
        """Answer transitive stage dependency questions from the canonical graph."""
        stage = self.stage(stage_slug)
        downstream = set(self.downstream_artifacts({artifact_type}, mode=mode))
        return any(output in downstream for output in stage.artifacts)

    def stage_for_artifact(self, artifact_type: str) -> str | None:
        if artifact_type in SUPPORT_ARTIFACT_STAGES:
            return SUPPORT_ARTIFACT_STAGES[artifact_type]
        for stage in self.stages:
            if artifact_type in stage.artifacts:
                return stage.slug
        return None

    def stages_for_artifacts(self, artifact_types: list[str] | tuple[str, ...]) -> tuple[str, ...]:
        wanted = {
            stage
            for artifact_type in artifact_types
            if (stage := self.stage_for_artifact(artifact_type)) is not None
        }
        return tuple(stage.slug for stage in self.stages if stage.slug in wanted)

    def registered_capabilities(self, slug: str) -> StageCapabilities:
        self.stage(slug)
        return STAGE_CAPABILITIES[slug]

    def revision_capability(
        self, slug: str, target_type: str, category: str
    ) -> RevisionCapability | None:
        for capability in self.registered_capabilities(slug).revisions:
            if capability.target_type == target_type and category in capability.categories:
                return capability
        return None
