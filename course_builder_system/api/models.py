"""Validated HTTP command bodies.

These models intentionally describe operator decisions, not artifact body schemas.
Canonical artifact validation remains in the existing domain layer.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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
    pass


class ReopenStageCommand(VersionedCommand):
    reason: str | None = Field(default=None, max_length=2000)


class RequestChangesCommand(VersionedCommand):
    feedback: str = Field(min_length=1, max_length=12000)
    mode: Literal["deterministic", "live"] = "deterministic"


class BriefAnswersCommand(VersionedCommand):
    answers: dict[str, Any]


class OutcomeDecisionCommand(VersionedCommand):
    selected_ids: list[str]
    edits: dict[str, dict[str, Any]] = Field(default_factory=dict)
    additions: list[dict[str, Any]] = Field(default_factory=list)
    priority_order: list[str] = Field(default_factory=list)


class SourceDecisionCommand(VersionedCommand):
    selected_ids: list[str] = Field(min_length=1, max_length=50)


class BlueprintDecisionCommand(VersionedCommand):
    selected_asset_types: dict[str, list[str]] = Field(default_factory=dict)
    depth_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    anchor_waivers: set[str] = Field(default_factory=set)
    rationale: str = Field(default="Human Blueprint checkpoint.", max_length=4000)


class ContentReviewCommand(VersionedCommand):
    decision: Literal["pending", "approved", "changes_requested"]
    feedback: str | None = Field(default=None, max_length=12000)
