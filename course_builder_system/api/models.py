"""Validated HTTP command bodies.

These models intentionally describe operator decisions, not artifact body schemas.
Canonical artifact validation remains in the existing domain layer.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

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


SubjectSeed = Annotated[str, Field(strict=True, min_length=1, max_length=200)]
PurposeSeed = Annotated[str, Field(strict=True, max_length=700)]
BriefListItem = Annotated[str, Field(strict=True, min_length=1, max_length=300)]
KnownSourceLocator = Annotated[str, Field(strict=True, min_length=1, max_length=1000)]
OutcomeId = Annotated[
    str,
    Field(strict=True, pattern=r"^[a-z0-9][a-z0-9_-]*$"),
]
OutcomeClientKey = Annotated[
    str,
    Field(strict=True, pattern=r"^new_[a-z0-9_-]+$"),
]
OutcomeText = Annotated[str, Field(strict=True, min_length=1, max_length=300)]
OutcomeCognitiveLevel = Literal[
    "remember",
    "understand",
    "apply",
    "analyze",
    "evaluate",
    "create",
]
OutcomePriority = Literal["core", "supporting", "optional"]


class CreateCourseRequest(StrictCommand):
    subject: SubjectSeed
    description: PurposeSeed | None = None
    constraints: list[BriefListItem] = Field(default_factory=list, max_length=50)
    known_source_locators: list[KnownSourceLocator] = Field(default_factory=list, max_length=50)
    brief: dict[str, Any] = Field(default_factory=dict, max_length=30)
    course_id: str | None = None

    @field_validator("subject")
    @classmethod
    def normalize_subject(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("subject cannot be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("constraints", "known_source_locators")
    @classmethod
    def normalize_seed_lists(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = value.strip()
            if not item:
                raise ValueError("seed list items cannot be blank")
            if item in seen:
                continue
            seen.add(item)
            normalized.append(item)
        return normalized


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


class BriefQuestionAnswer(StrictCommand):
    question_id: str = Field(min_length=1, max_length=200)
    value: Any = None
    accept_default: StrictBool = False
    skip: StrictBool = False

    @model_validator(mode="after")
    def exactly_one_resolution(self) -> BriefQuestionAnswer:
        has_value = "value" in self.model_fields_set
        if sum((has_value, self.accept_default, self.skip)) != 1:
            raise ValueError(
                "choose exactly one of value, accept_default, or skip for each question"
            )
        return self


class BriefAnswersCommand(VersionedCommand):
    expected_checksum: str = Field(min_length=6, max_length=128)
    answers: list[BriefQuestionAnswer] = Field(min_length=1, max_length=5)


class BriefUpdatesCommand(VersionedCommand):
    expected_checksum: str = Field(min_length=6, max_length=128)
    updates: dict[str, Any] = Field(min_length=1, max_length=30)


class BriefClarificationCommand(VersionedCommand):
    expected_checksum: str = Field(min_length=6, max_length=128)
    mode: Literal["deterministic", "live"] = "deterministic"


class BriefGapView(BaseModel):
    id: str
    kind: Literal["missing", "ambiguity", "conflict"]
    field: str
    severity: Literal["low", "medium", "high"]
    message: str


class BriefIntakeStateView(BaseModel):
    explicit_fields: list[str]
    accepted_default_fields: list[str]
    unresolved_required_fields: list[str]
    answered_question_ids: list[str]
    last_gap_analysis: list[BriefGapView]


class QuestionSpecView(BaseModel):
    id: str
    field: str
    prompt: str
    rationale: str
    answer_type: Literal[
        "free_text",
        "single_choice",
        "multiple_choice",
        "number",
        "duration",
        "confirmation",
    ]
    options: list[str]
    default: Any | None = None
    required: bool
    allow_skip: bool
    visibility: dict[str, Any]


class BriefQuestionRoundResponse(BaseModel):
    questions: list[QuestionSpecView] = Field(max_length=5)
    round_kind: Literal["mandatory", "conditional", "clarification", "complete"]
    gap_analysis: list[BriefGapView]
    intake_state: BriefIntakeStateView
    checksum: str


class OutcomeEditCommand(StrictCommand):
    statement: OutcomeText | None = None
    evidence: OutcomeText | None = None
    cognitive_level: OutcomeCognitiveLevel | None = None
    priority: OutcomePriority | None = None

    @model_validator(mode="after")
    def at_least_one_non_null_edit(self) -> OutcomeEditCommand:
        editable = ("statement", "evidence", "cognitive_level", "priority")
        explicitly_null = [
            field
            for field in editable
            if field in self.model_fields_set and getattr(self, field) is None
        ]
        if explicitly_null:
            raise ValueError("Outcome edit fields cannot be null")
        if not any(getattr(self, field) is not None for field in editable):
            raise ValueError("Outcome edit must include at least one supported field")
        return self


class OutcomeAdditionCommand(StrictCommand):
    client_key: OutcomeClientKey | None = None
    statement: OutcomeText
    evidence: OutcomeText
    cognitive_level: OutcomeCognitiveLevel
    priority: OutcomePriority


class OutcomeDecisionCommand(VersionedCommand):
    expected_checksum: str = Field(min_length=6, max_length=128)
    selected_ids: list[OutcomeId]
    edits: dict[OutcomeId, OutcomeEditCommand] = Field(default_factory=dict)
    additions: list[OutcomeAdditionCommand] = Field(default_factory=list)
    priority_order: list[OutcomeId] = Field(default_factory=list)


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
