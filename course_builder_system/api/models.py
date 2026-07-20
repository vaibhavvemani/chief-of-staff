"""Validated HTTP command bodies.

These models intentionally describe operator decisions, not artifact body schemas.
Canonical artifact validation remains in the existing domain layer.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    field_validator,
    model_validator,
)

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
CourseModelId = Annotated[
    str,
    Field(strict=True, pattern=r"^[a-z0-9][a-z0-9_-]*$"),
]
CourseModelReference = Annotated[
    str,
    Field(strict=True, pattern=r"^[a-z0-9][a-z0-9_-]*$"),
]
ModuleClientReference = Annotated[
    str,
    Field(strict=True, pattern=r"^new_module_[a-z0-9_-]+$"),
]
SubtopicClientReference = Annotated[
    str,
    Field(strict=True, pattern=r"^new_subtopic_[a-z0-9_-]+$"),
]
ConceptClientReference = Annotated[
    str,
    Field(strict=True, pattern=r"^new_concept_[a-z0-9_-]+$"),
]
CoverageClientReference = Annotated[
    str,
    Field(strict=True, pattern=r"^new_coverage_[a-z0-9_-]+$"),
]
CourseModelTitle = Annotated[str, Field(strict=True, min_length=1, max_length=200)]
CourseModelPurpose = Annotated[str, Field(strict=True, min_length=1, max_length=500)]
CourseModelScopeItem = Annotated[
    str,
    Field(strict=True, min_length=1, max_length=180),
]
ConceptName = Annotated[str, Field(strict=True, min_length=1, max_length=150)]
ConceptSummary = Annotated[str, Field(strict=True, min_length=1, max_length=400)]
CoverageStatement = Annotated[str, Field(strict=True, min_length=1, max_length=300)]
CourseModelPosition = Annotated[StrictInt, Field(ge=1, le=10_000)]
BlueprintAssetType = Literal[
    "learning_objectives",
    "course_content",
    "summary",
    "case_study",
    "assessment",
    "activities",
    "resources",
]
BlueprintDepthLevel = Literal["introductory", "intermediate", "advanced", "custom"]
BlueprintCaseDepth = Literal["none", "brief", "detailed"]
BlueprintAssessmentComplexity = Literal["none", "recall", "application", "analysis"]


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


class AddModuleOperation(StrictCommand):
    op: Literal["add_module"]
    client_ref: ModuleClientReference
    position: CourseModelPosition
    title: CourseModelTitle
    purpose: CourseModelPurpose
    in_scope: list[CourseModelScopeItem] = Field(max_length=100)
    out_of_scope: list[CourseModelScopeItem] = Field(max_length=100)
    prerequisite_module_ids: list[CourseModelReference] = Field(max_length=100)


class UpdateModuleOperation(StrictCommand):
    op: Literal["update_module"]
    target_id: CourseModelReference
    title: CourseModelTitle | None = None
    purpose: CourseModelPurpose | None = None
    in_scope: list[CourseModelScopeItem] | None = Field(default=None, max_length=100)
    out_of_scope: list[CourseModelScopeItem] | None = Field(default=None, max_length=100)
    prerequisite_module_ids: list[CourseModelReference] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def at_least_one_module_change(self) -> UpdateModuleOperation:
        return _require_non_null_update(
            self,
            ("title", "purpose", "in_scope", "out_of_scope", "prerequisite_module_ids"),
            "Module update",
        )


class RemoveModuleOperation(StrictCommand):
    op: Literal["remove_module"]
    target_id: CourseModelReference


class MoveModuleOperation(StrictCommand):
    op: Literal["move_module"]
    target_id: CourseModelReference
    position: CourseModelPosition


class ReorderModulesOperation(StrictCommand):
    op: Literal["reorder_modules"]
    module_ids: list[CourseModelReference] = Field(min_length=1, max_length=100)


class AddSubtopicOperation(StrictCommand):
    op: Literal["add_subtopic"]
    client_ref: SubtopicClientReference
    parent_id: CourseModelReference
    position: CourseModelPosition
    title: CourseModelTitle
    purpose: CourseModelPurpose
    in_scope: list[CourseModelScopeItem] = Field(max_length=100)
    out_of_scope: list[CourseModelScopeItem] = Field(max_length=100)
    prerequisite_subtopic_ids: list[CourseModelReference] = Field(max_length=100)


class UpdateSubtopicOperation(StrictCommand):
    op: Literal["update_subtopic"]
    target_id: CourseModelReference
    title: CourseModelTitle | None = None
    purpose: CourseModelPurpose | None = None
    in_scope: list[CourseModelScopeItem] | None = Field(default=None, max_length=100)
    out_of_scope: list[CourseModelScopeItem] | None = Field(default=None, max_length=100)
    prerequisite_subtopic_ids: list[CourseModelReference] | None = Field(
        default=None, max_length=100
    )

    @model_validator(mode="after")
    def at_least_one_subtopic_change(self) -> UpdateSubtopicOperation:
        return _require_non_null_update(
            self,
            (
                "title",
                "purpose",
                "in_scope",
                "out_of_scope",
                "prerequisite_subtopic_ids",
            ),
            "Subtopic update",
        )


class RemoveSubtopicOperation(StrictCommand):
    op: Literal["remove_subtopic"]
    target_id: CourseModelReference


class MoveSubtopicOperation(StrictCommand):
    op: Literal["move_subtopic"]
    target_id: CourseModelReference
    parent_id: CourseModelReference
    position: CourseModelPosition


class ReorderSubtopicsOperation(StrictCommand):
    op: Literal["reorder_subtopics"]
    parent_id: CourseModelReference
    subtopic_ids: list[CourseModelReference] = Field(min_length=1, max_length=200)


class AddConceptOperation(StrictCommand):
    op: Literal["add_concept"]
    client_ref: ConceptClientReference
    parent_id: CourseModelReference
    position: CourseModelPosition
    name: ConceptName
    summary: ConceptSummary
    depends_on: list[CourseModelReference] = Field(max_length=200)


class UpdateConceptOperation(StrictCommand):
    op: Literal["update_concept"]
    target_id: CourseModelReference
    name: ConceptName | None = None
    summary: ConceptSummary | None = None
    depends_on: list[CourseModelReference] | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def at_least_one_concept_change(self) -> UpdateConceptOperation:
        return _require_non_null_update(
            self,
            ("name", "summary", "depends_on"),
            "Concept update",
        )


class RemoveConceptOperation(StrictCommand):
    op: Literal["remove_concept"]
    target_id: CourseModelReference


class AddCoverageOperation(StrictCommand):
    op: Literal["add_coverage"]
    client_ref: CoverageClientReference
    parent_id: CourseModelReference
    position: CourseModelPosition
    statement: CoverageStatement
    concept_ids: list[CourseModelReference] = Field(max_length=200)


class UpdateCoverageOperation(StrictCommand):
    op: Literal["update_coverage"]
    target_id: CourseModelReference
    statement: CoverageStatement | None = None
    concept_ids: list[CourseModelReference] | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def at_least_one_coverage_change(self) -> UpdateCoverageOperation:
        return _require_non_null_update(
            self,
            ("statement", "concept_ids"),
            "Coverage update",
        )


class RemoveCoverageOperation(StrictCommand):
    op: Literal["remove_coverage"]
    target_id: CourseModelReference


class AssignCourseModelSourcesOperation(StrictCommand):
    op: Literal["assign_sources"]
    target_type: Literal["subtopic", "concept", "coverage"]
    target_id: CourseModelReference
    source_ids: list[CourseModelId] = Field(max_length=200)


class SetCourseOutcomeLinksOperation(StrictCommand):
    op: Literal["set_course_outcome_links"]
    outcome_ids: list[OutcomeId] = Field(min_length=1, max_length=200)


class SetRationaleOutcomeLinksOperation(StrictCommand):
    op: Literal["set_rationale_outcome_links"]
    target_id: CourseModelId
    outcome_ids: list[OutcomeId] = Field(max_length=200)


CourseModelOperation = Annotated[
    AddModuleOperation
    | UpdateModuleOperation
    | RemoveModuleOperation
    | MoveModuleOperation
    | ReorderModulesOperation
    | AddSubtopicOperation
    | UpdateSubtopicOperation
    | RemoveSubtopicOperation
    | MoveSubtopicOperation
    | ReorderSubtopicsOperation
    | AddConceptOperation
    | UpdateConceptOperation
    | RemoveConceptOperation
    | AddCoverageOperation
    | UpdateCoverageOperation
    | RemoveCoverageOperation
    | AssignCourseModelSourcesOperation
    | SetCourseOutcomeLinksOperation
    | SetRationaleOutcomeLinksOperation,
    Field(discriminator="op"),
]


class CourseModelDecisionPreviewCommand(VersionedCommand):
    expected_checksum: str = Field(min_length=6, max_length=128)
    operations: list[CourseModelOperation] = Field(min_length=1, max_length=100)


class CourseModelDecisionCommand(CourseModelDecisionPreviewCommand):
    impact_acknowledged: StrictBool = False
    expected_impact_checksum: str | None = Field(default=None, min_length=6, max_length=128)


class SourceDecisionCommand(VersionedCommand):
    expected_checksum: str = Field(min_length=6, max_length=128)
    selected_ids: list[str] = Field(min_length=1, max_length=50)


class KnownSourceCommand(VersionedCommand):
    expected_checksum: str = Field(min_length=6, max_length=128)
    locator: KnownSourceLocator
    title: Annotated[str, Field(strict=True, min_length=1, max_length=300)] | None = None
    publisher: Annotated[str, Field(strict=True, min_length=1, max_length=200)] | None = None
    trust_notes: Annotated[str, Field(strict=True, min_length=1, max_length=500)] | None = None
    relevance: Annotated[str, Field(strict=True, min_length=1, max_length=500)] | None = None


SourceRepairId = Annotated[
    str,
    Field(strict=True, pattern=r"^[a-z0-9][a-z0-9_-]*$"),
]


class SourceRepairRequestCommand(StrictCommand):
    expected_content_checksum: str = Field(min_length=6, max_length=128)
    subtopic_id: SourceRepairId
    asset_id: SourceRepairId
    claim_id: SourceRepairId
    finding_id: SourceRepairId
    evidence_gap: Annotated[str, Field(strict=True, min_length=1, max_length=2000)]
    mode: Literal["deterministic", "live"] = "deterministic"


class SourceRepairDecisionCommand(VersionedCommand):
    expected_checksum: str = Field(min_length=6, max_length=128)
    candidate_id: SourceRepairId
    decision: Literal["approved", "rejected"]
    rationale: Annotated[str, Field(strict=True, min_length=1, max_length=1000)]


class SourceRepairRouteCommand(VersionedCommand):
    expected_checksum: str = Field(min_length=6, max_length=128)
    subtopic_ids: list[SourceRepairId] = Field(min_length=1, max_length=50)
    asset_ids: list[SourceRepairId] = Field(min_length=1, max_length=50)

    @field_validator("subtopic_ids", "asset_ids")
    @classmethod
    def unique_route_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("source repair route IDs must be unique")
        return values


def _require_non_null_update(
    model: BaseModel,
    fields: tuple[str, ...],
    label: str,
):
    explicitly_null = [
        field
        for field in fields
        if field in model.model_fields_set and getattr(model, field) is None
    ]
    if explicitly_null:
        raise ValueError(f"{label} fields cannot be null")
    if not any(getattr(model, field) is not None for field in fields):
        raise ValueError(f"{label} must include at least one supported field")
    return model


class BlueprintWordRange(StrictCommand):
    minimum: Annotated[StrictInt, Field(ge=0)]
    target: Annotated[StrictInt, Field(ge=1)]
    maximum: Annotated[StrictInt, Field(ge=1)]

    @model_validator(mode="after")
    def ordered_range(self) -> BlueprintWordRange:
        if not self.minimum <= self.target <= self.maximum:
            raise ValueError("word range must satisfy minimum <= target <= maximum")
        return self


class BlueprintDepthChanges(StrictCommand):
    level: BlueprintDepthLevel | None = None
    target_learning_minutes: Annotated[StrictInt, Field(ge=1)] | None = None
    target_word_range: BlueprintWordRange | None = None
    required_example_count: Annotated[StrictInt, Field(ge=0)] | None = None
    case_depth: BlueprintCaseDepth | None = None
    assessment_complexity: BlueprintAssessmentComplexity | None = None

    @model_validator(mode="after")
    def at_least_one_depth_change(self) -> BlueprintDepthChanges:
        if not any(getattr(self, field) is not None for field in type(self).model_fields):
            raise ValueError("Blueprint depth changes must include at least one field")
        return self


class BlueprintDecisionCommand(VersionedCommand):
    expected_checksum: str = Field(min_length=6, max_length=128)
    default_asset_types: list[BlueprintAssetType] | None = Field(
        default=None,
        min_length=1,
        max_length=7,
    )
    default_depth: BlueprintDepthChanges | None = None
    selected_asset_types: dict[CourseModelId, list[BlueprintAssetType]] = Field(
        default_factory=dict,
        max_length=100,
    )
    depth_overrides: dict[CourseModelId, BlueprintDepthChanges] = Field(
        default_factory=dict,
        max_length=100,
    )
    anchor_waivers: set[CourseModelId] = Field(default_factory=set, max_length=100)
    rationale: str = Field(
        default="Human Blueprint checkpoint.",
        min_length=1,
        max_length=500,
    )

    @field_validator("default_asset_types")
    @classmethod
    def unique_default_assets(
        cls,
        values: list[BlueprintAssetType] | None,
    ) -> list[BlueprintAssetType] | None:
        if values is not None and len(values) != len(set(values)):
            raise ValueError("default asset types must be unique")
        return values

    @field_validator("selected_asset_types")
    @classmethod
    def valid_selected_assets(
        cls,
        values: dict[str, list[BlueprintAssetType]],
    ) -> dict[str, list[BlueprintAssetType]]:
        for subtopic_id, asset_types in values.items():
            if not asset_types:
                raise ValueError(f"{subtopic_id} must select at least one asset")
            if len(asset_types) != len(set(asset_types)):
                raise ValueError(f"{subtopic_id} asset types must be unique")
        return values

    @field_validator("rationale")
    @classmethod
    def nonblank_rationale(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("rationale cannot be blank")
        return normalized


LessonMode = Literal["live", "self_study"]
LessonPlanTargetId = Annotated[str, Field(strict=True, min_length=1, max_length=100)]


class LessonPlanConstraintChanges(StrictCommand):
    max_session_hours: Annotated[StrictInt | StrictFloat, Field(gt=0, le=24)] | None = None
    default_mode: LessonMode | None = None
    calendar_dates: list[
        Annotated[str, Field(strict=True, min_length=1, max_length=40)]
    ] | None = Field(default=None, max_length=20)
    instructor_count: Annotated[StrictInt, Field(ge=1, le=100)] | None = None
    delivery_platform: Annotated[
        str,
        Field(strict=True, min_length=1, max_length=120),
    ] | None = None

    @model_validator(mode="after")
    def at_least_one_constraint_change(self) -> LessonPlanConstraintChanges:
        if not self.model_fields_set:
            raise ValueError("Lesson Plan constraints must include at least one field")
        return self


class LessonPlanSetModeOperation(StrictCommand):
    op: Literal["set_mode"]
    target_id: CourseModelId
    value: LessonMode


class LessonPlanMoveSegmentOperation(StrictCommand):
    op: Literal["move_segment"]
    target_id: CourseModelId
    value: LessonPlanTargetId
    position: Annotated[StrictInt, Field(ge=1, le=10_000)]


class LessonPlanReorderSessionOperation(StrictCommand):
    op: Literal["reorder_session"]
    session_ids: list[LessonPlanTargetId] = Field(min_length=1, max_length=500)

    @field_validator("session_ids")
    @classmethod
    def unique_session_ids(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("session_ids must be unique")
        return values


LessonPlanOperation = Annotated[
    LessonPlanSetModeOperation
    | LessonPlanMoveSegmentOperation
    | LessonPlanReorderSessionOperation,
    Field(discriminator="op"),
]


class LessonPlanDecisionCommand(VersionedCommand):
    expected_checksum: str = Field(min_length=6, max_length=128)
    constraints: LessonPlanConstraintChanges | None = None
    operations: list[LessonPlanOperation] = Field(default_factory=list, max_length=500)
    rationale: str = Field(
        default="Human Lesson Plan checkpoint.",
        min_length=1,
        max_length=500,
    )

    @model_validator(mode="after")
    def nonempty_decision(self) -> LessonPlanDecisionCommand:
        if self.constraints is None and not self.operations:
            raise ValueError("Lesson Plan decision must change constraints or sessions")
        self.rationale = self.rationale.strip()
        if not self.rationale:
            raise ValueError("rationale cannot be blank")
        return self


class ContentReviewCommand(VersionedCommand):
    expected_checksum: str = Field(min_length=6, max_length=128)
    decision: Literal["pending", "approved", "changes_requested"]
    feedback: str | None = Field(default=None, max_length=12000)
