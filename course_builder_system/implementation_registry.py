"""Provider-neutral deterministic/live callable registry for pipeline factories."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

import acceptance
import llm
import steps
from agents.live_stages import LiveStageImplementations, StructuredModelProvider
from research_adapter import ResearchProvider

StepCallable = Callable[[dict, str | None], dict]

REQUIRED_STEP_NAMES = frozenset(
    {
        "intake",
        "course_outcomes",
        "research",
        "source_selection",
        "structure",
        "blueprint",
        "student_content",
        "lesson_plan",
        "render_course_folder",
        "run_summary",
    }
)
JUDGMENT_HEAVY_STAGES = frozenset(
    {
        "brief",
        "outcomes",
        "research",
        "course-model",
        "blueprint",
        "content",
        "lesson-plan",
    }
)


@dataclass(frozen=True)
class ImplementationSelection:
    mode: str
    steps: Mapping[str, StepCallable]


class StageImplementationRegistry:
    """Resolve every pipeline callable explicitly; never cross-mode fallback."""

    def __init__(
        self,
        *,
        deterministic: Mapping[str, StepCallable],
        live: Mapping[str, StepCallable],
        live_readiness: Callable[[], dict[str, Any]],
    ) -> None:
        self._modes = {
            "deterministic": dict(deterministic),
            "live": dict(live),
        }
        self._live_readiness = live_readiness
        for mode, implementations in self._modes.items():
            missing = sorted(REQUIRED_STEP_NAMES - set(implementations))
            extra = sorted(set(implementations) - REQUIRED_STEP_NAMES)
            if missing or extra:
                raise ValueError(
                    f"{mode} implementation registry mismatch; "
                    f"missing={missing}, extra={extra}"
                )

    def selection(self, mode: str) -> ImplementationSelection:
        try:
            implementations = self._modes[mode]
        except KeyError as exc:
            raise ValueError(f"unknown stage-run mode: {mode!r}") from exc
        return ImplementationSelection(mode=mode, steps=dict(implementations))

    def resolve(self, mode: str, step_name: str) -> StepCallable:
        selection = self.selection(mode)
        try:
            return selection.steps[step_name]
        except KeyError as exc:  # constructor validation makes this defensive only
            raise ValueError(
                f"{mode} has no registered implementation for {step_name!r}"
            ) from exc

    def provider_readiness(self) -> dict[str, Any]:
        result = dict(self._live_readiness())
        result.setdefault("ready", False)
        return result

    def assert_mode_ready(self, mode: str, stage_slug: str) -> None:
        self.selection(mode)
        if mode != "live" or stage_slug not in JUDGMENT_HEAVY_STAGES:
            return
        readiness = self.provider_readiness()
        if readiness.get("ready") is not True:
            provider = readiness.get("provider") or "live provider"
            raise llm.ProviderNotReady(
                f"Live {stage_slug} requires configured {provider} credentials on the "
                "Python server. Configure the provider or explicitly choose deterministic mode."
            )


def build_default_implementation_registry(
    *,
    rendered_root: Path = Path("rendered_courses"),
    model_provider: StructuredModelProvider | None = None,
    research_provider_factory: Callable[[], ResearchProvider] | None = None,
    deterministic_controls: acceptance.DeterministicAcceptanceControls | None = None,
) -> StageImplementationRegistry:
    live = LiveStageImplementations(
        model=model_provider,
        research_provider_factory=research_provider_factory,
    )
    deterministic: dict[str, StepCallable] = {
        "intake": steps.intake_step,
        "course_outcomes": steps.course_outcomes_step,
        "research": steps.sprint2_research_step,
        "source_selection": steps.source_selection_step,
        "structure": steps.structure_step,
        "blueprint": steps.blueprint_step,
        "student_content": steps.make_student_content_step(
            asset_generator=acceptance.deterministic_generate_asset,
            package_verifier=partial(
                acceptance.deterministic_verify_content_package,
                controls=deterministic_controls,
            ),
            asset_verifier=partial(
                acceptance.deterministic_verify_asset,
                controls=deterministic_controls,
            ),
        ),
        "lesson_plan": steps.lesson_plan_step,
        "render_course_folder": steps.make_render_course_folder_step(
            output_root=rendered_root
        ),
        "run_summary": steps.run_summary_step,
    }
    live_steps: dict[str, StepCallable] = {
        "intake": live.intake,
        "course_outcomes": live.course_outcomes,
        "research": live.research,
        # Source selection, rendering, and Package calculation remain typed or
        # deterministic even while the surrounding operator journey is Live.
        "source_selection": steps.source_selection_step,
        "structure": live.structure,
        "blueprint": live.blueprint,
        "student_content": steps.student_content_step,
        "lesson_plan": live.lesson_plan,
        "render_course_folder": steps.make_render_course_folder_step(
            output_root=rendered_root
        ),
        "run_summary": steps.run_summary_step,
    }
    return StageImplementationRegistry(
        deterministic=deterministic,
        live=live_steps,
        live_readiness=live.provider_readiness,
    )
