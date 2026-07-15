"""Project state-specific actions from registered backend capabilities."""

from __future__ import annotations

from typing import Any

from api.services.pipeline_catalog import PipelineCatalog


class UnsupportedStageAction(ValueError):
    pass


class StageCapabilityService:
    """Single backend source of truth for actions the product can perform."""

    def __init__(self, catalog: PipelineCatalog) -> None:
        self.catalog = catalog

    def actions(
        self,
        stage_slug: str,
        state: str,
        *,
        read_only: bool,
        approval_failures: list[dict[str, Any]] | None = None,
        prerequisites_ready: bool = True,
        blocking_stage: str | None = None,
    ) -> list[dict[str, Any]]:
        self.catalog.stage(stage_slug)
        if read_only:
            return []
        registered = self.catalog.registered_capabilities(stage_slug)
        failures = approval_failures or []
        actions: list[dict[str, Any]] = []

        if state == "locked":
            if blocking_stage is not None:
                actions.append(self._blocking_action(blocking_stage))
        elif state == "ready":
            actions.append(self._action("run", f"Run {self._label(stage_slug)}"))
        elif state == "stale":
            if not prerequisites_ready and blocking_stage is not None:
                actions.append(self._blocking_action(blocking_stage))
            actions.append(
                self._action(
                    "run",
                    f"Rerun {self._label(stage_slug)}",
                    enabled=prerequisites_ready,
                    reason=(
                        None
                        if prerequisites_ready
                        else "Approve the changed upstream stage before rerunning this output."
                    ),
                )
            )
        elif state == "failed":
            if not prerequisites_ready and blocking_stage is not None:
                actions.append(self._blocking_action(blocking_stage))
            actions.append(
                self._action(
                    "retry",
                    f"Retry {self._label(stage_slug)}",
                    enabled=prerequisites_ready,
                    reason=(
                        None
                        if prerequisites_ready
                        else "Approve the current upstream inputs before retrying."
                    ),
                )
            )
        elif state == "needs_input":
            for direct in registered.direct_actions:
                actions.append(self._direct_action(direct, needs_input=True))
        elif state in {"awaiting_review", "requires_attention"}:
            for direct in registered.direct_actions:
                actions.append(self._direct_action(direct))
            if registered.revisions:
                actions.append(
                    {
                        **self._action("revise", "Request scoped revision"),
                        "revision_targets": [
                            {
                                "target_type": revision.target_type,
                                "categories": list(revision.categories),
                            }
                            for revision in registered.revisions
                        ],
                    }
                )
            failure_stage = next(
                (
                    str(failure["stage"])
                    for failure in failures
                    if failure.get("stage") not in {None, stage_slug}
                ),
                None,
            )
            if failure_stage is not None:
                actions.append(self._blocking_action(failure_stage))
            actions.append(
                self._action(
                    "approve",
                    f"Approve {self._label(stage_slug)}",
                    enabled=not failures,
                    reason=failures[0]["message"] if failures else None,
                )
            )
        elif state == "approved":
            actions.append(
                self._action(
                    "reopen",
                    f"Reopen {self._label(stage_slug)}",
                    requires_impact_confirmation=True,
                )
            )
            next_stage = self._next_stage(stage_slug)
            if next_stage is not None:
                actions.append(
                    {
                        **self._action(
                            "continue", f"Continue to {self._label(next_stage)}"
                        ),
                        "target_stage": next_stage,
                    }
                )
        return actions

    def assert_revision_supported(
        self, stage_slug: str, target_type: str, category: str
    ) -> None:
        if self.catalog.revision_capability(stage_slug, target_type, category) is None:
            raise UnsupportedStageAction(
                f"{stage_slug!r} has no revision handler for "
                f"target type {target_type!r} and category {category!r}"
            )

    def assert_action_available(
        self,
        stage_slug: str,
        state: str,
        action_id: str,
        *,
        read_only: bool,
        approval_failures: list[dict[str, Any]] | None = None,
        prerequisites_ready: bool = True,
        blocking_stage: str | None = None,
    ) -> None:
        match = next(
            (
                action
                for action in self.actions(
                    stage_slug,
                    state,
                    read_only=read_only,
                    approval_failures=approval_failures,
                    prerequisites_ready=prerequisites_ready,
                    blocking_stage=blocking_stage,
                )
                if action["id"] == action_id
            ),
            None,
        )
        if match is None or not match.get("enabled", True):
            reason = match.get("reason") if match else None
            raise UnsupportedStageAction(
                reason or f"action {action_id!r} is not available while stage is {state!r}"
            )

    @staticmethod
    def _action(
        action_id: str,
        label: str,
        *,
        enabled: bool = True,
        reason: str | None = None,
        requires_impact_confirmation: bool = False,
    ) -> dict[str, Any]:
        return {
            "id": action_id,
            "label": label,
            "enabled": enabled,
            "reason": reason,
            "requires_impact_confirmation": requires_impact_confirmation,
        }

    def _direct_action(self, action_id: str, *, needs_input: bool = False) -> dict[str, Any]:
        labels = {
            "edit": "Provide required input" if needs_input else "Edit stage",
            "source_decision": "Save source decision",
            "review_asset": "Review content assets",
        }
        return self._action(action_id, labels[action_id])

    def _blocking_action(self, stage_slug: str) -> dict[str, Any]:
        self.catalog.stage(stage_slug)
        return {
            **self._action(
                "go_to_blocker", f"Go to {self._label(stage_slug)}"
            ),
            "target_stage": stage_slug,
        }

    def _next_stage(self, stage_slug: str) -> str | None:
        slugs = [stage.slug for stage in self.catalog.stages]
        index = slugs.index(stage_slug)
        return slugs[index + 1] if index < len(slugs) - 1 else None

    def _label(self, stage_slug: str) -> str:
        return self.catalog.stage(stage_slug).label
