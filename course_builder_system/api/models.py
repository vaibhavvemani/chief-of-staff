"""Validated HTTP command bodies.

These models intentionally describe operator decisions, not artifact body schemas.
Canonical artifact validation remains in the existing domain layer.
"""

from __future__ import annotations

from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field

type StageState = Literal[
    "locked",
    "needs_input",
    "ready",
    "running",
    "awaiting_review",
    "requires_attention",
    "approved",
    "stale",
    "failed",
]
STAGE_STATES = frozenset(get_args(StageState.__value__))


class StrictCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateCourseRequest(StrictCommand):
    subject: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=4000)
    constraints: list[str] = Field(default_factory=list, max_length=50)
    known_source_locators: list[str] = Field(default_factory=list, max_length=50)
    course_id: str | None = None


class VersionedCommand(StrictCommand):
    expected_checksum: str | None = Field(default=None, min_length=6, max_length=128)


class RunStageCommand(VersionedCommand):
    mode: Literal["deterministic", "live"] = "deterministic"


class ApproveStageCommand(VersionedCommand):
    expected_checksum: str = Field(min_length=6, max_length=128)


class ReopenStageCommand(VersionedCommand):
    expected_checksum: str = Field(min_length=6, max_length=128)
    reason: str | None = Field(default=None, max_length=2000)
    impact_acknowledged: bool = False
    expected_impact_checksum: str | None = Field(default=None, min_length=6, max_length=128)


class ScopedRevisionCommand(VersionedCommand):
    expected_checksum: str = Field(min_length=6, max_length=128)
    target_type: str = Field(min_length=1, max_length=64)
    target_ids: list[str] = Field(min_length=1, max_length=50)
    category: str = Field(min_length=1, max_length=64)
    instruction: str = Field(min_length=1, max_length=12000)
    mode: Literal["deterministic", "live"] = "deterministic"
    impact_acknowledged: bool = False
    expected_impact_checksum: str | None = Field(default=None, min_length=6, max_length=128)


class ImpactPreviewCommand(VersionedCommand):
    expected_checksum: str = Field(min_length=6, max_length=128)
    action: Literal["reopen", "edit", "revise", "repair"]
    target_type: str | None = Field(default=None, max_length=64)
    target_ids: list[str] = Field(default_factory=list, max_length=50)
    operation_summary: str | None = Field(default=None, max_length=2000)


class ImpactPreviewResponse(BaseModel):
    action: str
    stage: str
    operation_summary: str | None = None
    direct_artifacts: list[str]
    stale_artifacts: list[str]
    targeted_assets: list[str]
    preserved_assets: list[str]
    requires_rerun_stages: list[str]
    warnings: list[str]
    impact_level: Literal["targeted", "downstream", "full"]
    impact_checksum: str


class BriefAnswersCommand(VersionedCommand):
    answers: dict[str, Any]


class OutcomeDecisionCommand(VersionedCommand):
    expected_checksum: str = Field(min_length=6, max_length=128)
    selected_ids: list[str]
    edits: dict[str, dict[str, Any]] = Field(default_factory=dict)
    additions: list[dict[str, Any]] = Field(default_factory=list)
    priority_order: list[str] = Field(default_factory=list)


class SourceDecisionCommand(VersionedCommand):
    expected_checksum: str = Field(min_length=6, max_length=128)
    selected_ids: list[str] = Field(min_length=1, max_length=50)


class BlueprintDecisionCommand(VersionedCommand):
    expected_checksum: str = Field(min_length=6, max_length=128)
    selected_asset_types: dict[str, list[str]] = Field(default_factory=dict)
    depth_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    anchor_waivers: set[str] = Field(default_factory=set)
    rationale: str = Field(default="Human Blueprint checkpoint.", max_length=4000)


class ContentReviewCommand(VersionedCommand):
    expected_checksum: str = Field(min_length=6, max_length=128)
    decision: Literal["pending", "approved", "changes_requested"]
    feedback: str | None = Field(default=None, max_length=12000)
