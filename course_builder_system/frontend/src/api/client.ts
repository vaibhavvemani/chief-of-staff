import { demoCourses, demoWorkspaceFor } from "../data/demo";
import type {
  BlueprintAssetType,
  BlueprintDecisionDraft,
  BlueprintPlan,
  BriefData,
  BriefGap,
  BriefIntakeState,
  BriefQuestionAnswer,
  BriefQuestionRound,
  BriefQuestionSpec,
  BriefUpdates,
  ContentAsset,
  CourseModelData,
  CourseModelChangeRecord,
  CourseModelOperation,
  CourseModelPreview,
  CourseModelValidationIssue,
  CourseModule,
  CourseSummary,
  CreateCourseRequest,
  ImpactPreview,
  JobResponse,
  LessonPlanDecisionDraft,
  LessonSession,
  Outcome,
  OutcomeAdvisory,
  OutcomeCognitiveLevel,
  OutcomeDecisionCommand,
  OutcomeEdit,
  OutcomePriority,
  OutcomeValidationIssue,
  OutputFile,
  SourceCandidate,
  ScopedRevisionCommand,
  StageAction,
  StageActionId,
  StageCommand,
  StageSlug,
  StageSummary,
  UiStatus,
  Workspace,
} from "../types";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const jsonHeaders = { "Content-Type": "application/json", Accept: "application/json" };

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...options,
      headers: { ...jsonHeaders, ...options.headers },
    });
  } catch (error) {
    throw new ApiError(error instanceof Error ? error.message : "The API is unavailable.", 0, error);
  }

  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    let message = `Request failed with ${response.status}`;
    if (isRecord(detail)) {
      if (isRecord(detail.error) && typeof detail.error.message === "string") message = detail.error.message;
      else if (typeof detail.detail === "string") message = detail.detail;
      else if (isRecord(detail.detail) && typeof detail.detail.message === "string") message = detail.detail.message;
      else if (Array.isArray(detail.detail)) {
        const issue = detail.detail.find((item) => isRecord(item) && typeof item.msg === "string");
        if (isRecord(issue) && typeof issue.msg === "string") message = issue.msg;
      }
    }
    throw new ApiError(message, response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function versionConflictChecksum(error: unknown): string | undefined {
  if (!(error instanceof ApiError) || error.status !== 409 || !isRecord(error.detail)) return undefined;
  const detail = error.detail.error;
  if (!isRecord(detail)) return undefined;
  return typeof detail.actual_checksum === "string" ? detail.actual_checksum : undefined;
}

export function outcomeValidationIssues(error: unknown): OutcomeValidationIssue[] {
  if (!(error instanceof ApiError) || !isRecord(error.detail) || !isRecord(error.detail.error)) return [];
  return asArray(error.detail.error.issues).flatMap((issue) => {
    if (!isRecord(issue)) return [];
    const code = asString(issue.code);
    const message = asString(issue.message);
    if (!code || !message) return [];
    return [{
      code,
      message,
      outcomeId: asString(issue.outcome_id ?? issue.outcomeId) || undefined,
      field: asString(issue.field) || undefined,
      index: typeof issue.index === "number" && Number.isInteger(issue.index) ? issue.index : undefined,
    }];
  });
}

export function courseModelValidationIssues(error: unknown): CourseModelValidationIssue[] {
  if (!(error instanceof ApiError) || !isRecord(error.detail) || !isRecord(error.detail.error)) return [];
  return asArray(error.detail.error.issues).flatMap((issue) => {
    if (!isRecord(issue)) return [];
    const code = asString(issue.code);
    const message = asString(issue.message);
    if (!code || !message) return [];
    return [{
      code,
      message,
      operationIndex: Number.isInteger(issue.operation_index) ? Number(issue.operation_index) : undefined,
      recordType: asString(issue.record_type) || undefined,
      recordId: asString(issue.record_id) || undefined,
      field: asString(issue.field) || undefined,
      path: asString(issue.path) || undefined,
    }];
  });
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" ? value : fallback;
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function asStringArray(value: unknown): string[] {
  return asArray(value).filter((item): item is string => typeof item === "string");
}

function asNullableString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function asGapKind(value: unknown): BriefGap["kind"] {
  return value === "conflict" || value === "missing" ? value : "ambiguity";
}

function asGapSeverity(value: unknown): BriefGap["severity"] {
  return value === "high" || value === "low" ? value : "medium";
}

function asRoundKind(value: unknown): BriefQuestionRound["roundKind"] {
  return value === "conditional"
    || value === "clarification"
    || value === "complete"
    ? value
    : "mandatory";
}

function normalizeGapAnalysis(value: unknown): BriefGap[] {
  return asArray(value).flatMap((item) =>
    isRecord(item)
      ? [{
          id: asString(item.id),
          kind: asGapKind(item.kind),
          field: asString(item.field),
          severity: asGapSeverity(item.severity),
          message: asString(item.message),
        }]
      : [],
  );
}

const emptyIntakeState = (): BriefIntakeState => ({
  explicitFields: [],
  acceptedDefaultFields: [],
  unresolvedRequiredFields: [],
  answeredQuestionIds: [],
  lastGapAnalysis: [],
});

function normalizeIntakeState(value: unknown): BriefIntakeState {
  if (!isRecord(value)) return emptyIntakeState();
  return {
    explicitFields: asStringArray(value.explicit_fields),
    acceptedDefaultFields: asStringArray(value.accepted_default_fields),
    unresolvedRequiredFields: asStringArray(value.unresolved_required_fields),
    answeredQuestionIds: asStringArray(value.answered_question_ids),
    lastGapAnalysis: normalizeGapAnalysis(value.last_gap_analysis),
  };
}

function asQuestionValue(value: unknown): BriefQuestionSpec["defaultValue"] {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return value;
  const list = asStringArray(value);
  return Array.isArray(value) && list.length === value.length ? list : undefined;
}

function normalizeQuestion(value: unknown): BriefQuestionSpec | null {
  if (!isRecord(value)) return null;
  const answerType = asString(value.answer_type);
  const validAnswerTypes: BriefQuestionSpec["answerType"][] = [
    "free_text",
    "single_choice",
    "multiple_choice",
    "number",
    "duration",
    "confirmation",
  ];
  return {
    id: asString(value.id),
    field: asString(value.field),
    prompt: asString(value.prompt),
    rationale: asString(value.rationale),
    answerType: validAnswerTypes.includes(answerType as BriefQuestionSpec["answerType"])
      ? answerType as BriefQuestionSpec["answerType"]
      : "free_text",
    options: asStringArray(value.options),
    defaultValue: Object.hasOwn(value, "default") ? asQuestionValue(value.default) : undefined,
    required: value.required !== false,
    allowSkip: value.allow_skip === true,
    visibility: isRecord(value.visibility) ? value.visibility : {},
  };
}

const stageStateMap: Record<string, UiStatus> = {
  completed: "approved",
  pending_review: "awaiting_review",
  attention: "requires_attention",
  requires_attention: "requires_attention",
  not_started: "ready",
};

export function normalizeStatus(value: unknown, fallback: UiStatus = "ready"): UiStatus {
  const raw = asString(value).toLowerCase();
  const valid: UiStatus[] = [
    "locked",
    "needs_input",
    "ready",
    "running",
    "awaiting_review",
    "approved",
    "requires_attention",
    "stale",
    "failed",
  ];
  return valid.includes(raw as UiStatus) ? (raw as UiStatus) : stageStateMap[raw] ?? fallback;
}

function normalizeFailure(value: unknown): string | undefined {
  if (isRecord(value)) return asString(value.message) || undefined;
  return asString(value) || undefined;
}

interface BackendCourse {
  course_id?: string;
  title?: string;
  source?: string;
  read_only?: boolean;
  operator_status?: string;
  next_action?: string;
  last_activity_at?: string;
  attention_count?: number;
  current_stage?: string;
}

function normalizeCourse(raw: BackendCourse): CourseSummary {
  const status = normalizeStatus(raw.operator_status, raw.operator_status === "complete" ? "approved" : "ready");
  return {
    courseId: raw.course_id ?? "untitled-course",
    title: raw.title ?? raw.course_id ?? "Untitled course",
    subject: raw.title ?? "Course",
    status,
    currentStage: allStageSlugs.includes(raw.current_stage as StageSlug)
      ? (raw.current_stage as StageSlug)
      : status === "approved"
        ? "package"
        : status === "requires_attention"
          ? "content"
          : "brief",
    nextAction: raw.next_action ?? "Open workspace",
    updatedAt: raw.last_activity_at ?? new Date().toISOString(),
    progress: status === "approved" ? 100 : status === "requires_attention" ? 70 : 10,
    attentionCount: raw.attention_count ?? 0,
    approvedStages: status === "approved" ? 8 : status === "requires_attention" ? 5 : 0,
    totalStages: 8,
  };
}

export async function getCourses(): Promise<{ courses: CourseSummary[]; demoMode: boolean }> {
  try {
    const data = await apiFetch<{ courses?: BackendCourse[] } | BackendCourse[]>("/api/courses");
    const courses = Array.isArray(data) ? data : data.courses ?? [];
    return { courses: courses.map(normalizeCourse), demoMode: false };
  } catch (error) {
    if (error instanceof ApiError && error.status === 0) {
      return { courses: demoCourses, demoMode: true };
    }
    throw error;
  }
}

interface BackendWorkspace {
  course_id?: string;
  title?: string;
  source?: string;
  read_only?: boolean;
  operator_status?: string;
  next_action?: string;
  last_activity_at?: string;
  current_stage?: string;
  active_job?: {
    job_id?: string;
    status?: string;
    stage?: string;
  } | null;
  attention?: {
    verification_totals?: Record<string, number>;
    blocking_total?: number;
    flagged_assets?: unknown[];
    failed_units?: unknown[];
  };
  stages?: BackendStage[];
  artifact_types?: string[];
}

interface StageArtifact {
  artifact_type?: string;
  checksum?: string;
  envelope?: unknown;
  body?: unknown;
}

interface BackendStage {
  slug?: string;
  label?: string;
  state?: string;
  attention_count?: number;
  checksum?: string;
  can_mutate?: boolean;
  dependencies?: unknown[];
  downstream_stages?: unknown[];
  prerequisites_ready?: boolean;
  approval_failures?: unknown[];
  last_failure?: unknown;
  actions?: unknown[];
  advisories?: unknown[];
  artifacts?: StageArtifact[];
}

const allStageSlugs: StageSlug[] = [
  "brief",
  "outcomes",
  "research",
  "course-model",
  "blueprint",
  "content",
  "lesson-plan",
  "package",
];

const blueprintAssetTypes: BlueprintAssetType[] = [
  "learning_objectives",
  "course_content",
  "summary",
  "case_study",
  "assessment",
  "activities",
  "resources",
];

function isBlueprintAssetType(value: string): value is BlueprintAssetType {
  return blueprintAssetTypes.includes(value as BlueprintAssetType);
}

const stageActionIds: StageActionId[] = [
  "run",
  "retry",
  "edit",
  "source_decision",
  "review_asset",
  "revise",
  "approve",
  "reopen",
  "go_to_blocker",
  "continue",
];

function normalizeStageActions(value: unknown): StageAction[] {
  return asArray(value).flatMap((item) => {
    if (!isRecord(item)) return [];
    const id = asString(item.id) as StageActionId;
    if (!stageActionIds.includes(id)) return [];
    const targetStage = asString(item.target_stage) as StageSlug;
    return [{
      id,
      label: asString(item.label, id.replaceAll("_", " ")),
      enabled: item.enabled !== false,
      reason: asString(item.reason) || undefined,
      requiresImpactConfirmation: item.requires_impact_confirmation === true,
      targetStage: allStageSlugs.includes(targetStage) ? targetStage : undefined,
      revisionTargets: asArray(item.revision_targets).flatMap((target) =>
        isRecord(target)
          ? [{
              targetType: asString(target.target_type),
              categories: asStringArray(target.categories),
            }]
          : [],
      ),
    }];
  });
}

function artifactMap(stages: BackendStage[]): Map<string, { body: unknown; checksum?: string; status?: string }> {
  const map = new Map<string, { body: unknown; checksum?: string; status?: string }>();
  stages.forEach((stage) => {
    stage.artifacts?.forEach((artifact) => {
      if (!artifact.artifact_type) return;
      const envelope = isRecord(artifact.envelope) ? artifact.envelope : null;
      const body = artifact.body ?? envelope?.body;
      map.set(artifact.artifact_type, { body, checksum: artifact.checksum, status: asString(envelope?.status) || undefined });
    });
  });
  return map;
}

function normalizeBrief(value: unknown, fallback: BriefData): BriefData {
  if (!isRecord(value)) return fallback;
  return {
    courseTitle: asString(value.course_title, fallback.courseTitle),
    subject: asString(value.subject, fallback.subject),
    audience: asString(value.audience, fallback.audience),
    priorKnowledge: asString(value.prior_knowledge, fallback.priorKnowledge),
    purpose: asString(value.purpose, fallback.purpose),
    level: asString(value.level, fallback.level),
    duration: asString(value.duration, fallback.duration),
    modality: asString(value.modality, fallback.modality),
    language: asString(value.language, fallback.language),
    inScope: asStringArray(value.in_scope),
    outOfScope: asStringArray(value.out_of_scope),
    mustHaveTopics: asStringArray(value.must_have_topics),
    constraints: asStringArray(value.constraints),
    availableMaterials: asStringArray(value.available_materials),
    jurisdiction: asNullableString(value.jurisdiction),
    accessibilityRequirements: asNullableString(value.accessibility_requirements),
    assessmentExpectations: Object.prototype.hasOwnProperty.call(value, "assessment_expectations")
      ? asNullableString(value.assessment_expectations)
      : fallback.assessmentExpectations,
    liveTeachingConstraints: asNullableString(value.live_teaching_constraints),
    toolsOrEquipment: asNullableString(value.tools_or_equipment),
    freshnessRequirement: asNullableString(value.freshness_requirement),
    assumptions: asArray(value.assumptions).flatMap((item) =>
      isRecord(item)
        ? [
            {
              field: asString(item.field),
              value: asString(item.value),
              rationale: asString(item.rationale),
            },
          ]
        : [],
    ),
    provenance: asArray(value.provenance).flatMap((item) =>
      isRecord(item)
        ? [{
            field: asString(item.field),
            source: item.source === "default" ? "default" as const : "user" as const,
            confidence: item.confidence === "assumed" ? "assumed" as const : "explicit" as const,
          }]
        : [],
    ),
    intakeState: normalizeIntakeState(value.intake_state),
  };
}

const outcomeCognitiveLevels: OutcomeCognitiveLevel[] = [
  "remember",
  "understand",
  "apply",
  "analyze",
  "evaluate",
  "create",
];

const outcomePriorities: OutcomePriority[] = ["core", "supporting", "optional"];

function normalizeOutcomes(value: unknown, fallback: Outcome[]): Outcome[] {
  if (!isRecord(value)) return fallback;
  const outcomes = asArray(value.outcomes).flatMap((item) => {
    if (!isRecord(item)) return [];
    const cognitiveLevel = asString(item.cognitive_level) as OutcomeCognitiveLevel;
    const priority = asString(item.priority) as OutcomePriority;
    if (!outcomeCognitiveLevels.includes(cognitiveLevel) || !outcomePriorities.includes(priority)) return [];
    return [{
      id: asString(item.id),
      statement: asString(item.statement),
      cognitiveLevel,
      evidence: asString(item.evidence),
      priority,
    }];
  });
  return outcomes.length ? outcomes : fallback;
}

function normalizeOutcomeAdvisories(value: unknown): OutcomeAdvisory[] {
  return asArray(value).flatMap((item) => {
    if (!isRecord(item)) return [];
    const code = asString(item.code);
    const outcomeId = asString(item.outcome_id ?? item.outcomeId);
    const reason = asString(item.message ?? item.reason);
    if (!code || !outcomeId || !reason) return [];
    const relatedOutcomeId = asString(item.related_outcome_id ?? item.relatedOutcomeId) || undefined;
    return [{
      code,
      outcomeId,
      relatedOutcomeId,
      field: asString(item.field),
      reason,
      level: "advisory" as const,
    }];
  });
}

function normalizeSources(value: unknown, registry: unknown, registryStatus: string | undefined, fallback: SourceCandidate[]): SourceCandidate[] {
  if (!isRecord(value)) return fallback;
  const approvedIds = new Set<string>();
  const rejectedIds = new Set<string>();
  if (isRecord(registry)) {
    asArray(registry.source_registry).forEach((source) => {
      if (isRecord(source)) approvedIds.add(asString(source.id));
    });
    if (isRecord(registry.decision)) {
      asStringArray(registry.decision.rejected_ids).forEach((id) => rejectedIds.add(id));
    }
  }
  const sources = asArray(value.source_candidates).flatMap((item) =>
    isRecord(item)
      ? [
          {
            id: asString(item.id),
            title: asString(item.title),
            publisher: asString(item.publisher),
            sourceType: asString(item.source_type),
            locator: asString(item.locator),
            status: approvedIds.has(asString(item.id))
              ? registryStatus === "approved" ? "approved" : "selected"
              : rejectedIds.has(asString(item.id))
                ? "rejected"
                : asString(item.status),
            trustNotes: asString(item.trust_notes),
            relevance: asString(item.relevance),
            assignedNodeIds: asStringArray(item.assigned_node_ids),
          },
        ]
      : [],
  );
  return sources.length ? sources : fallback;
}

function normalizeCompetitors(value: unknown, fallback: Workspace["research"]["competitors"]): Workspace["research"]["competitors"] {
  if (!isRecord(value)) return fallback;
  const competitors = asArray(value.competitor_findings).flatMap((item) =>
    isRecord(item)
      ? [
          {
            id: asString(item.id),
            provider: asString(item.provider),
            offering: asString(item.offering),
            locator: asString(item.locator),
            outlineStatus: asString(item.outline_status),
            outlineSections: asArray(item.outline_sections).flatMap((section) =>
              isRecord(section) ? [asString(section.raw_label)] : [],
            ),
            structureSummary: asString(item.structure_summary),
          },
        ]
      : [],
  );
  return competitors.length ? competitors : fallback;
}

export function normalizeCourseModel(value: unknown, fallback: CourseModelData): CourseModelData {
  if (!isRecord(value)) return fallback;
  const modules = asArray(value.modules).flatMap((moduleValue) => {
    if (!isRecord(moduleValue)) return [];
    const moduleContext = isRecord(moduleValue.context) ? moduleValue.context : {};
    return [
      {
        id: asString(moduleValue.id),
        order: asNumber(moduleValue.order),
        title: asString(moduleValue.title),
        purpose: asString(moduleContext.purpose),
        inScope: asStringArray(moduleContext.in_scope),
        outOfScope: asStringArray(moduleContext.out_of_scope),
        prerequisiteModuleIds: asStringArray(moduleValue.prerequisite_module_ids),
        subtopics: asArray(moduleValue.subtopics).flatMap((subtopicValue) => {
          if (!isRecord(subtopicValue)) return [];
          const context = isRecord(subtopicValue.context) ? subtopicValue.context : {};
          return [
            {
              id: asString(subtopicValue.id),
              order: asNumber(subtopicValue.order),
              title: asString(subtopicValue.title),
              purpose: asString(context.purpose),
              inScope: asStringArray(context.in_scope),
              outOfScope: asStringArray(context.out_of_scope),
              prerequisiteSubtopicIds: asStringArray(subtopicValue.prerequisite_subtopic_ids),
              concepts: asArray(subtopicValue.concepts).flatMap((conceptValue) =>
                isRecord(conceptValue)
                  ? [
                      {
                        id: asString(conceptValue.id),
                        name: asString(conceptValue.name),
                        summary: asString(conceptValue.summary),
                        dependsOn: asStringArray(conceptValue.depends_on),
                        sourceIds: asStringArray(conceptValue.source_ids),
                      },
                    ]
                  : [],
              ),
              coverageRequirements: asArray(subtopicValue.coverage_requirements).flatMap((requirement) =>
                isRecord(requirement)
                  ? [
                      {
                        id: asString(requirement.id),
                        statement: asString(requirement.statement),
                        conceptIds: asStringArray(requirement.concept_ids),
                        sourceIds: asStringArray(requirement.source_ids),
                      },
                    ]
                  : [],
              ),
              approvedSourceIds: asStringArray(subtopicValue.approved_source_ids),
            },
          ];
        }),
      },
    ];
  });
  const metadata = isRecord(value.course_metadata) ? value.course_metadata : {};
  return {
    modules: modules.length ? modules : fallback.modules,
    courseOutcomeIds: asStringArray(metadata.course_outcome_ids),
    rationales: asArray(value.structural_rationale).flatMap((rationale) =>
      isRecord(rationale)
        ? [{
            id: asString(rationale.id),
            statement: asString(rationale.statement),
            relatedOutcomeIds: asStringArray(rationale.related_outcome_ids),
          }]
        : [],
    ),
    eligibleSources: asArray(value.source_registry).flatMap((source) =>
      isRecord(source)
        ? [{
            id: asString(source.id),
            title: asString(source.title),
            publisher: asString(source.publisher),
          }]
        : [],
    ),
  };
}

function normalizeBlueprint(value: unknown, fallback: Workspace["blueprint"]): Workspace["blueprint"] {
  if (!isRecord(value)) return fallback;
  const defaultsValue = isRecord(value.course_defaults) ? value.course_defaults : {};
  const depth = isRecord(defaultsValue.depth_budget) ? defaultsValue.depth_budget : {};
  const wordRange = isRecord(depth.target_word_range) ? depth.target_word_range : {};
  const defaults = {
    depth: asString(depth.level, fallback.defaults.depth),
    minutes: asNumber(depth.target_learning_minutes, fallback.defaults.minutes),
    wordMinimum: asNumber(wordRange.minimum, fallback.defaults.wordMinimum),
    wordTarget: asNumber(wordRange.target, fallback.defaults.wordTarget),
    wordMaximum: asNumber(wordRange.maximum, fallback.defaults.wordMaximum),
    examples: asNumber(depth.required_example_count, fallback.defaults.examples),
    caseDepth: asString(depth.case_depth, fallback.defaults.caseDepth),
    assessmentComplexity: asString(depth.assessment_complexity, fallback.defaults.assessmentComplexity),
    assetTypes: asStringArray(defaultsValue.default_asset_types).filter(isBlueprintAssetType),
  };
  const plans: BlueprintPlan[] = asArray(value.subtopic_plans).flatMap((planValue) => {
    if (!isRecord(planValue)) return [];
    const budget = isRecord(planValue.depth_budget) ? planValue.depth_budget : {};
    const range = isRecord(budget.target_word_range) ? budget.target_word_range : {};
    const assets = asArray(planValue.asset_plan).flatMap((asset) => {
      if (!isRecord(asset)) return [];
      const assetType = asString(asset.asset_type);
      if (!isBlueprintAssetType(assetType)) return [];
      return [{
        id: asString(asset.id),
        assetType,
        title: asString(asset.title),
        selectionStatus: asString(asset.selection_status),
        sourceIds: asStringArray(asset.source_ids),
      }];
    });
    const selected = assets.filter((asset) => asset.selectionStatus === "selected").map((asset) => asset.assetType);
    const sameAssets = selected.length === defaults.assetTypes.length
      && selected.every((assetType) => defaults.assetTypes.includes(assetType));
    const planValues = {
      depth: asString(budget.level),
      minutes: asNumber(budget.target_learning_minutes),
      wordMinimum: asNumber(range.minimum),
      wordTarget: asNumber(range.target),
      wordMaximum: asNumber(range.maximum),
      examples: asNumber(budget.required_example_count),
      caseDepth: asString(budget.case_depth),
      assessmentComplexity: asString(budget.assessment_complexity),
    };
    return [
      {
        subtopicId: asString(planValue.subtopic_id),
        ...planValues,
        exception: !sameAssets || Object.entries(planValues).some(
          ([field, fieldValue]) => fieldValue !== defaults[field as keyof typeof planValues],
        ),
        anchorWaiverConfirmed: Boolean(planValue.anchor_asset_waiver_confirmed),
        assets,
      },
    ];
  });
  return {
    defaults,
    plans: plans.length ? plans : fallback.plans,
  };
}

function normalizeContent(
  value: unknown,
  fallback: Workspace["content"],
  reviewArtifact?: unknown,
  reviewChecksum?: string,
): Workspace["content"] {
  if (!isRecord(value)) return fallback;
  const reviewBody = isRecord(reviewArtifact) && isRecord(reviewArtifact.body)
    ? reviewArtifact.body
    : isRecord(reviewArtifact)
      ? reviewArtifact
      : null;
  const reviewRecords = new Map<string, Record<string, unknown>>();
  asArray(reviewBody?.assets).forEach((record) => {
    if (isRecord(record) && asString(record.asset_id)) {
      reviewRecords.set(asString(record.asset_id), record);
    }
  });
  const assets: ContentAsset[] = asArray(value.subtopics).flatMap((subtopic) => {
    if (!isRecord(subtopic)) return [];
    const subtopicId = asString(subtopic.subtopic_id);
    return asArray(subtopic.assets).flatMap((asset) => {
      if (!isRecord(asset)) return [];
      const verification = isRecord(asset.verification) ? asset.verification : {};
      const unattributed = asArray(verification.unattributed_found).length;
      const blockers = asNumber(verification.unsupported) + asNumber(verification.ungrounded) + unattributed;
      const review = reviewRecords.get(asString(asset.id));
      const reviewStatus = asString(review?.decision ?? review?.status, "pending");
      return [
        {
          id: asString(asset.id),
          subtopicId,
          type: asString(asset.type),
          title: asString(asset.title),
          format: asString(asset.format),
          content: asString(asset.content),
          status: blockers ? "requires_attention" : "approved",
          reviewStatus: ["approved", "changes_requested", "pending"].includes(reviewStatus)
            ? (reviewStatus as ContentAsset["reviewStatus"])
            : "pending",
          claims: asArray(asset.claims).flatMap((claim) =>
            isRecord(claim)
              ? [
                  {
                    id: asString(claim.id),
                    text: asString(claim.text),
                    sourceId: typeof claim.source_id === "string" ? claim.source_id : null,
                    support: asString(claim.support),
                    excerpt: typeof claim.supporting_excerpt === "string" ? claim.supporting_excerpt : null,
                    note: asString(claim.note),
                  },
                ]
              : [],
          ),
          verification: {
            supported: asNumber(verification.supported),
            partial: asNumber(verification.partial),
            unsupported: asNumber(verification.unsupported),
            ungrounded: asNumber(verification.ungrounded),
            unattributed,
          },
        },
      ];
    });
  });
  return assets.length
    ? { assets, completed: assets.length, expected: assets.length, reviewChecksum }
    : fallback;
}

function normalizeLessonPlan(value: unknown, fallback: Workspace["lessonPlan"]): Workspace["lessonPlan"] {
  if (!isRecord(value)) return fallback;
  const coverage = isRecord(value.coverage_summary) ? value.coverage_summary : {};
  const constraints = isRecord(value.session_constraints) ? value.session_constraints : {};
  const sessions: LessonSession[] = asArray(value.sessions).flatMap((session) =>
    isRecord(session)
      ? [
          {
            id: asString(session.id),
            order: asNumber(session.order),
            title: asString(session.title),
            durationMinutes: asNumber(session.duration_minutes),
            covers: asArray(session.covers).flatMap((cover) =>
              isRecord(cover)
                ? [
                    {
                      subtopicId: asString(cover.subtopic_id),
                      mode: asString(cover.mode),
                      talkingPoints: asStringArray(cover.talking_points),
                    },
                  ]
                : [],
            ),
          },
        ]
      : [],
  );
  const latestDecision = asArray(value.decision_log).filter(isRecord).at(-1);
  return sessions.length
    ? {
        sessions,
        totalDurationMinutes: asNumber(coverage.total_duration_minutes),
        expectedSubtopicIds: asStringArray(coverage.expected_subtopic_ids),
        coveredSubtopicIds: asStringArray(coverage.covered_subtopic_ids),
        constraints: {
          maxSessionHours: asNumber(constraints.max_session_hours, fallback.constraints.maxSessionHours),
          defaultMode: asString(constraints.default_mode, fallback.constraints.defaultMode) === "self_study" ? "self_study" : "live",
          calendarDates: asStringArray(constraints.calendar_dates),
          instructorCount: typeof constraints.instructor_count === "number" ? constraints.instructor_count : null,
          deliveryPlatform: typeof constraints.delivery_platform === "string" ? constraints.delivery_platform : null,
        },
        unresolvedConstraints: asStringArray(value.unresolved_session_constraints),
        affectedSessionIds: isRecord(latestDecision)
          ? asStringArray(latestDecision.affected_session_ids)
          : [],
      }
    : fallback;
}

function outputRelativePath(value: string, courseId: string): string {
  for (const marker of ["/rendered_course/", `/rendered_courses/${courseId}/`]) {
    if (value.includes(marker)) return value.split(marker).at(-1) ?? value;
  }
  return value.replace(/^\.?\//, "");
}

function normalizeOutputFiles(value: unknown, courseId: string): OutputFile[] {
  if (!isRecord(value) || !isRecord(value.paths)) return [];
  const paths = value.paths;
  const labels: Record<string, string> = {
    index: "Course index",
    course_overview: "Course overview",
    source_index: "Source index",
    lesson_plan: "Lesson plan",
  };
  const files: OutputFile[] = Object.entries(labels).flatMap(([key, label]) => {
    const path = asString(paths[key]);
    return path ? [{ path: outputRelativePath(path, courseId), label, kind: "markdown" as const }] : [];
  });
  const assets = isRecord(paths.assets) ? paths.assets : {};
  const folders = new Map<string, OutputFile[]>();
  Object.entries(assets).forEach(([assetId, rawPath]) => {
    if (typeof rawPath !== "string") return;
    const relative = outputRelativePath(rawPath, courseId);
    const parts = relative.split("/");
    const folder = parts.length > 1 ? parts.slice(0, -1).join("/") : "modules";
    const children = folders.get(folder) ?? [];
    children.push({ path: relative, label: assetId, kind: "markdown" });
    folders.set(folder, children);
  });
  if (folders.size) {
    files.push({
      path: "modules",
      label: "Modules",
      kind: "folder",
      children: [...folders.entries()].map(([path, children]) => ({
        path,
        label: path.split("/").at(-1)?.replace(/^\d+_/, "").replaceAll("-", " ") ?? path,
        kind: "folder" as const,
        children,
      })),
    });
  }
  return files;
}

function normalizeStages(raw: BackendWorkspace, fallback: StageSummary[]): StageSummary[] {
  if (!raw.stages?.length) return fallback;
  return raw.stages.flatMap((stage) => {
    const slug = asString(stage.slug) as StageSlug;
    if (!allStageSlugs.includes(slug)) return [];
    return [
      {
        slug,
        label: stage.label ?? fallback.find((item) => item.slug === slug)?.label ?? slug,
        status: normalizeStatus(stage.state),
        count: stage.attention_count || undefined,
        checksum: stage.checksum,
        dependencies: asStringArray(stage.dependencies),
        downstreamStages: asStringArray(stage.downstream_stages).filter(
          (candidate): candidate is StageSlug => allStageSlugs.includes(candidate as StageSlug),
        ),
        prerequisitesReady: stage.prerequisites_ready !== false,
        approvalFailures: asArray(stage.approval_failures).flatMap((failure) =>
          isRecord(failure)
            ? [{
                code: asString(failure.code, "approval_blocked"),
                message: asString(failure.message, "This stage cannot be approved yet."),
                artifactType: asString(failure.artifact_type) || undefined,
                targetIds: asStringArray(failure.record_ids),
              }]
            : [],
        ),
        lastFailure: normalizeFailure(stage.last_failure),
        actions: normalizeStageActions(stage.actions),
        summary: stage.attention_count
          ? `${stage.attention_count} item${stage.attention_count === 1 ? "" : "s"} need attention.`
          : "Current with its recorded inputs.",
      },
    ];
  });
}

async function getStage(courseId: string, slug: StageSlug): Promise<BackendStage> {
  return apiFetch<BackendStage>(`/api/courses/${encodeURIComponent(courseId)}/stages/${slug}`);
}

export async function getWorkspace(courseId: string): Promise<{ workspace: Workspace; demoMode: boolean; readOnly: boolean }> {
  try {
    const projection = await apiFetch<BackendWorkspace>(`/api/courses/${encodeURIComponent(courseId)}/workspace`);
    const stageResults = await Promise.allSettled(allStageSlugs.map((slug) => getStage(courseId, slug)));
    const backendStages = stageResults.flatMap((result) => (result.status === "fulfilled" ? [result.value] : []));
    const artifacts = artifactMap(backendStages);
    const outcomeStage = backendStages.find((candidate) => candidate.slug === "outcomes")
      ?? projection.stages?.find((candidate) => candidate.slug === "outcomes");
    const demoShape = demoWorkspaceFor(courseId);
    const emptyCourse = normalizeCourse({
      course_id: projection.course_id ?? courseId,
      title: projection.title,
      source: projection.source,
      read_only: projection.read_only,
      operator_status: projection.operator_status,
      next_action: projection.next_action,
      last_activity_at: projection.last_activity_at,
      attention_count: projection.attention?.blocking_total ?? 0,
      current_stage: projection.current_stage,
    });
    const startingSubject = projection.title ?? emptyCourse.subject ?? "this subject";
    const base: Workspace = {
      ...demoShape,
      course: emptyCourse,
      stages: normalizeStages(projection, []),
      artifactVersion: "",
      estimatedCost: undefined,
      brief: {
        courseTitle: projection.title ?? "Untitled course",
        subject: startingSubject,
        audience: "General adult learners who are new to the subject.",
        priorKnowledge: "No prior knowledge assumed.",
        purpose: `Build practical working knowledge of ${startingSubject}.`,
        level: "beginner",
        duration: "3 hours of self-paced learning",
        modality: "self_paced",
        language: "English",
        inScope: [`core concepts in ${startingSubject}`, "practical examples"],
        outOfScope: ["advanced specialist topics"],
        mustHaveTopics: ["practical examples"],
        constraints: [],
        availableMaterials: [],
        jurisdiction: null,
        accessibilityRequirements: null,
        assessmentExpectations: "Short practical checks and scenario questions.",
        liveTeachingConstraints: null,
        toolsOrEquipment: null,
        freshnessRequirement: null,
        assumptions: [],
        provenance: [],
        intakeState: emptyIntakeState(),
      },
      outcomes: [],
      outcomesChecksum: artifacts.get("course_outcomes")?.checksum,
      outcomeAdvisories: normalizeOutcomeAdvisories(outcomeStage?.advisories),
      research: { sources: [], competitors: [], observations: [], registrySaved: false, registryApproved: false },
      modules: [],
      courseModel: { modules: [], courseOutcomeIds: [], rationales: [], eligibleSources: [] },
      courseModelChecksum: artifacts.get("course_model")?.checksum,
      blueprint: {
        defaults: { depth: "", minutes: 0, wordMinimum: 0, wordTarget: 0, wordMaximum: 0, examples: 0, caseDepth: "", assessmentComplexity: "", assetTypes: [] },
        plans: [],
      },
      blueprintChecksum: artifacts.get("blueprint")?.checksum,
      content: { assets: [], completed: 0, expected: 0 },
      lessonPlan: {
        sessions: [],
        totalDurationMinutes: 0,
        expectedSubtopicIds: [],
        coveredSubtopicIds: [],
        constraints: { maxSessionHours: 2, defaultMode: "live", calendarDates: [], instructorCount: null, deliveryPlatform: null },
        unresolvedConstraints: [],
        affectedSessionIds: [],
      },
      lessonPlanChecksum: artifacts.get("lesson_plan")?.checksum,
      package: {
        format: "Markdown folder",
        operatorStatus: projection.operator_status ?? "pending",
        integrityPassed: false,
        approvedSourceCount: 0,
        rejectedSourceLeaks: 0,
        selectedAssets: 0,
        renderedAssets: 0,
        unresolvedBlockers: projection.attention?.blocking_total ?? 0,
        files: [],
      },
      activity: [],
      briefChecksum: artifacts.get("brief")?.checksum,
    };
    const runSummary = artifacts.get("run_summary")?.body;
    const manifest = artifacts.get("render_manifest")?.body;
    const summaryRecord = isRecord(runSummary) ? runSummary : {};
    const manifestRecord = isRecord(manifest) ? manifest : {};
    let reviewArtifact: unknown;
    let reviewChecksum: string | undefined;
    if (artifacts.has("content_package")) {
      try {
        const review = await apiFetch<{ artifact?: unknown; checksum?: string }>(
          `/api/courses/${encodeURIComponent(courseId)}/content/reviews`,
        );
        reviewArtifact = review.artifact;
        reviewChecksum = review.checksum;
      } catch (error) {
        if (!(error instanceof ApiError && error.status === 404)) throw error;
      }
    }
    const content = normalizeContent(
      artifacts.get("content_package")?.body,
      base.content,
      reviewArtifact,
      reviewChecksum,
    );
    const blockingTotal = projection.attention?.blocking_total ?? 0;
    const normalizedCourse = normalizeCourse({
      course_id: projection.course_id ?? courseId,
      title: projection.title,
      source: projection.source,
      read_only: projection.read_only,
      operator_status: projection.operator_status,
      next_action: projection.next_action,
      last_activity_at: projection.last_activity_at,
      attention_count: blockingTotal,
      current_stage: projection.current_stage,
    });
    const normalizedStages = normalizeStages(projection, base.stages);
    normalizedCourse.approvedStages = normalizedStages.filter((stage) => stage.status === "approved").length;
    normalizedCourse.progress = Math.round((normalizedCourse.approvedStages / 8) * 100);
    normalizedCourse.currentStage =
      normalizedStages.find((item) =>
        ["needs_input", "requires_attention", "failed", "awaiting_review", "ready", "stale"].includes(item.status),
      )?.slug ?? "package";

    const workspace: Workspace = {
      ...base,
      course: normalizedCourse,
      stages: normalizedStages,
      activeJob:
        projection.active_job?.job_id && allStageSlugs.includes(projection.active_job.stage as StageSlug)
          ? {
              jobId: projection.active_job.job_id,
              status: projection.active_job.status === "running" ? "running" : "queued",
              stage: projection.active_job.stage as StageSlug,
            }
          : undefined,
      artifactVersion:
        projection.stages?.map((stage) => stage.checksum).filter(Boolean).join(":") || base.artifactVersion,
      brief: normalizeBrief(artifacts.get("brief")?.body, base.brief),
      briefChecksum: artifacts.get("brief")?.checksum,
      outcomes: normalizeOutcomes(artifacts.get("course_outcomes")?.body, base.outcomes),
      outcomesChecksum: artifacts.get("course_outcomes")?.checksum,
      outcomeAdvisories: normalizeOutcomeAdvisories(outcomeStage?.advisories),
      research: {
        sources: normalizeSources(
          artifacts.get("research_dossier")?.body,
          artifacts.get("approved_source_registry")?.body,
          artifacts.get("approved_source_registry")?.status,
          base.research.sources,
        ),
        competitors: normalizeCompetitors(artifacts.get("research_dossier")?.body, base.research.competitors),
        observations: isRecord(artifacts.get("research_dossier")?.body)
          ? [
              ...asStringArray((artifacts.get("research_dossier")?.body as Record<string, unknown>).sequence_observations),
              ...asStringArray((artifacts.get("research_dossier")?.body as Record<string, unknown>).gap_observations),
            ]
          : base.research.observations,
        registrySaved: artifacts.has("approved_source_registry"),
        registryApproved: artifacts.get("approved_source_registry")?.status === "approved",
      },
      courseModel: normalizeCourseModel(artifacts.get("course_model")?.body, base.courseModel),
      courseModelChecksum: artifacts.get("course_model")?.checksum,
      modules: normalizeCourseModel(artifacts.get("course_model")?.body, base.courseModel).modules,
      blueprint: normalizeBlueprint(artifacts.get("blueprint")?.body, base.blueprint),
      blueprintChecksum: artifacts.get("blueprint")?.checksum,
      content,
      lessonPlan: normalizeLessonPlan(artifacts.get("lesson_plan")?.body, base.lessonPlan),
      lessonPlanChecksum: artifacts.get("lesson_plan")?.checksum,
      package: {
        ...base.package,
        operatorStatus: asString(summaryRecord.operator_status, projection.operator_status ?? base.package.operatorStatus),
        integrityPassed: artifacts.has("render_manifest"),
        approvedSourceCount: workspaceSourceCount(
          artifacts.get("approved_source_registry")?.body,
        ),
        unresolvedBlockers: blockingTotal,
        selectedAssets: content.expected,
        renderedAssets: isRecord(manifestRecord.paths) && isRecord(manifestRecord.paths.assets)
          ? Object.keys(manifestRecord.paths.assets).length
          : content.completed,
        files: normalizeOutputFiles(manifestRecord, courseId),
      },
    };
    return { workspace, demoMode: false, readOnly: Boolean(projection.read_only) };
  } catch (error) {
    if (error instanceof ApiError && error.status === 0) {
      return { workspace: demoWorkspaceFor(courseId), demoMode: true, readOnly: true };
    }
    throw error;
  }
}

function workspaceSourceCount(value: unknown): number {
  return isRecord(value) ? asArray(value.source_registry).length : 0;
}

export async function createCourse(request: CreateCourseRequest): Promise<{ courseId: string }> {
  const data = await apiFetch<{ course_id?: string; courseId?: string }>("/api/courses", {
    method: "POST",
    body: JSON.stringify({
      subject: request.subject,
      course_id: request.courseId,
      description: request.description,
      constraints: request.constraints
        ? request.constraints.split("\n").map((value) => value.trim()).filter(Boolean)
        : [],
      known_source_locators: request.sourceUrls ?? [],
      brief: request.brief ? briefUpdatesPayload(request.brief) : undefined,
    }),
  });
  const courseId = data.course_id ?? data.courseId ?? "";
  return { courseId };
}

export async function getBriefQuestions(courseId: string): Promise<BriefQuestionRound> {
  const response = await apiFetch<Record<string, unknown>>(
    `/api/courses/${encodeURIComponent(courseId)}/brief/questions`,
  );
  const questions = asArray(response.questions).flatMap((item) => {
    const question = normalizeQuestion(item);
    return question ? [question] : [];
  });
  return {
    questions,
    roundKind: asRoundKind(response.round_kind),
    gapAnalysis: normalizeGapAnalysis(response.gap_analysis),
    intakeState: normalizeIntakeState(response.intake_state),
    checksum: asString(response.checksum),
  };
}

export async function saveBriefAnswers(
  courseId: string,
  answers: BriefQuestionAnswer[],
  expectedChecksum: string,
): Promise<{ checksum?: string }> {
  return apiFetch<{ checksum?: string }>(`/api/courses/${encodeURIComponent(courseId)}/brief/answers`, {
    method: "PUT",
    body: JSON.stringify({
      answers: answers.map((answer) => ({
        question_id: answer.questionId,
        ...(answer.value !== undefined ? { value: answer.value } : {}),
        ...(answer.acceptDefault ? { accept_default: true } : {}),
        ...(answer.skip ? { skip: true } : {}),
      })),
      expected_checksum: expectedChecksum,
    }),
  });
}

function briefUpdatesPayload(updates: BriefUpdates): Record<string, unknown> {
  return {
    course_title: updates.courseTitle,
    audience: updates.audience,
    prior_knowledge: updates.priorKnowledge,
    purpose: updates.purpose,
    level: updates.level,
    duration: updates.duration,
    modality: updates.modality,
    language: updates.language,
    in_scope: updates.inScope,
    out_of_scope: updates.outOfScope,
    must_have_topics: updates.mustHaveTopics,
    constraints: updates.constraints,
    available_materials: updates.availableMaterials,
    jurisdiction: updates.jurisdiction,
    accessibility_requirements: updates.accessibilityRequirements,
    assessment_expectations: updates.assessmentExpectations,
    live_teaching_constraints: updates.liveTeachingConstraints,
    tools_or_equipment: updates.toolsOrEquipment,
    freshness_requirement: updates.freshnessRequirement,
  };
}

export async function saveBriefUpdates(
  courseId: string,
  updates: BriefUpdates,
  expectedChecksum: string,
): Promise<{ checksum?: string }> {
  return apiFetch<{ checksum?: string }>(`/api/courses/${encodeURIComponent(courseId)}/brief`, {
    method: "PATCH",
    body: JSON.stringify({
      updates: Object.fromEntries(Object.entries(briefUpdatesPayload(updates)).filter(([, value]) => value !== undefined)),
      expected_checksum: expectedChecksum,
    }),
  });
}

export async function runStage(courseId: string, stage: StageSlug, command: StageCommand): Promise<JobResponse> {
  const response = await apiFetch<Partial<JobResponse> & { job: JobResponse["job"] }>(`/api/courses/${encodeURIComponent(courseId)}/stages/${stage}/run`, {
    method: "POST",
    body: JSON.stringify({ expected_checksum: command.expectedChecksum, mode: command.mode ?? "deterministic" }),
  });
  return {
    ...response,
    events_url: response.events_url ?? `/api/jobs/${response.job.job_id}/events`,
  };
}

export async function approveStage(courseId: string, stage: StageSlug, command: StageCommand): Promise<void> {
  if (!command.expectedChecksum) {
    throw new Error("Stage approval requires the current checksum.");
  }
  await apiFetch(`/api/courses/${encodeURIComponent(courseId)}/stages/${stage}/approve`, {
    method: "POST",
    body: JSON.stringify({ expected_checksum: command.expectedChecksum }),
  });
}

function courseModelOperationPayload(operation: CourseModelOperation): Record<string, unknown> {
  switch (operation.op) {
    case "add_module": return { op: operation.op, client_ref: operation.clientRef, position: operation.position, title: operation.title, purpose: operation.purpose, in_scope: operation.inScope, out_of_scope: operation.outOfScope, prerequisite_module_ids: operation.prerequisiteModuleIds };
    case "update_module": return { op: operation.op, target_id: operation.targetId, title: operation.title, purpose: operation.purpose, in_scope: operation.inScope, out_of_scope: operation.outOfScope, prerequisite_module_ids: operation.prerequisiteModuleIds };
    case "remove_module": return { op: operation.op, target_id: operation.targetId };
    case "move_module": return { op: operation.op, target_id: operation.targetId, position: operation.position };
    case "reorder_modules": return { op: operation.op, module_ids: operation.moduleIds };
    case "add_subtopic": return { op: operation.op, client_ref: operation.clientRef, parent_id: operation.parentId, position: operation.position, title: operation.title, purpose: operation.purpose, in_scope: operation.inScope, out_of_scope: operation.outOfScope, prerequisite_subtopic_ids: operation.prerequisiteSubtopicIds };
    case "update_subtopic": return { op: operation.op, target_id: operation.targetId, title: operation.title, purpose: operation.purpose, in_scope: operation.inScope, out_of_scope: operation.outOfScope, prerequisite_subtopic_ids: operation.prerequisiteSubtopicIds };
    case "remove_subtopic": return { op: operation.op, target_id: operation.targetId };
    case "move_subtopic": return { op: operation.op, target_id: operation.targetId, parent_id: operation.parentId, position: operation.position };
    case "reorder_subtopics": return { op: operation.op, parent_id: operation.parentId, subtopic_ids: operation.subtopicIds };
    case "add_concept": return { op: operation.op, client_ref: operation.clientRef, parent_id: operation.parentId, position: operation.position, name: operation.name, summary: operation.summary, depends_on: operation.dependsOn };
    case "update_concept": return { op: operation.op, target_id: operation.targetId, name: operation.name, summary: operation.summary, depends_on: operation.dependsOn };
    case "remove_concept": return { op: operation.op, target_id: operation.targetId };
    case "add_coverage": return { op: operation.op, client_ref: operation.clientRef, parent_id: operation.parentId, position: operation.position, statement: operation.statement, concept_ids: operation.conceptIds };
    case "update_coverage": return { op: operation.op, target_id: operation.targetId, statement: operation.statement, concept_ids: operation.conceptIds };
    case "remove_coverage": return { op: operation.op, target_id: operation.targetId };
    case "assign_sources": return { op: operation.op, target_type: operation.targetType, target_id: operation.targetId, source_ids: operation.sourceIds };
    case "set_course_outcome_links": return { op: operation.op, outcome_ids: operation.outcomeIds };
    case "set_rationale_outcome_links": return { op: operation.op, target_id: operation.targetId, outcome_ids: operation.outcomeIds };
  }
}

function compactPayload(value: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(value).filter(([, item]) => item !== undefined));
}

function normalizeImpactResponse(
  response: Record<string, unknown>,
  stage: StageSlug,
  action: ImpactPreview["action"],
): ImpactPreview {
  return {
    action,
    stage,
    operationSummary: asString(response.operation_summary) || undefined,
    directArtifacts: asStringArray(response.direct_artifacts),
    staleArtifacts: asStringArray(response.stale_artifacts),
    targetedAssets: asStringArray(response.targeted_assets),
    preservedAssets: asStringArray(response.preserved_assets),
    requiresRerunStages: asStringArray(response.requires_rerun_stages).filter(
      (candidate): candidate is StageSlug => allStageSlugs.includes(candidate as StageSlug),
    ),
    warnings: asStringArray(response.warnings),
    impactLevel: ["targeted", "downstream", "full"].includes(asString(response.impact_level))
      ? asString(response.impact_level) as ImpactPreview["impactLevel"]
      : "downstream",
    impactChecksum: asString(response.impact_checksum),
  };
}

function normalizeAffectedRecords(value: unknown): CourseModelPreview["affectedRecords"] {
  if (!isRecord(value)) return {};
  return Object.fromEntries(Object.entries(value).flatMap(([family, record]) =>
    isRecord(record)
      ? (() => {
          const changedIds = asStringArray(record.changed_ids);
          const removedIds = asStringArray(record.removed_ids);
          return changedIds.length || removedIds.length
            ? [[family, { changedIds, removedIds }]]
            : [];
        })()
      : [],
  ));
}

function normalizeCourseModelChangeRecords(value: unknown): CourseModelChangeRecord[] {
  return asArray(value).flatMap((record) => {
    if (!isRecord(record)) return [];
    const operationIndex = asNumber(record.operation_index, -1);
    const op = asString(record.op);
    const action = asString(record.action);
    const recordType = asString(record.record_type);
    if (operationIndex < 0 || !op || !action || !recordType) return [];
    return [{
      operationIndex,
      op,
      action,
      recordType,
      recordId: asString(record.record_id) || undefined,
      recordIds: asStringArray(record.record_ids),
      parentId: asString(record.parent_id) || undefined,
    }];
  });
}

function normalizeCourseModelPreview(response: Record<string, unknown>): CourseModelPreview {
  const candidateArtifact = isRecord(response.candidate_artifact) ? response.candidate_artifact : {};
  const impact = isRecord(response.impact) ? response.impact : {};
  return {
    candidate: normalizeCourseModel(candidateArtifact.body, { modules: [], courseOutcomeIds: [], rationales: [], eligibleSources: [] }),
    allocatedIds: isRecord(response.allocated_ids)
      ? Object.fromEntries(Object.entries(response.allocated_ids).filter((entry): entry is [string, string] => typeof entry[1] === "string"))
      : {},
    changeRecords: normalizeCourseModelChangeRecords(response.change_records),
    affectedRecords: normalizeAffectedRecords(response.affected_records),
    impact: normalizeImpactResponse(impact, "course-model", "edit"),
  };
}

export async function previewCourseModelDecision(
  courseId: string,
  operations: CourseModelOperation[],
  expectedChecksum: string,
): Promise<CourseModelPreview> {
  const response = await apiFetch<Record<string, unknown>>(
    `/api/courses/${encodeURIComponent(courseId)}/course-model/decision/preview`,
    {
      method: "POST",
      body: JSON.stringify({
        expected_checksum: expectedChecksum,
        operations: operations.map((operation) => compactPayload(courseModelOperationPayload(operation))),
      }),
    },
  );
  return normalizeCourseModelPreview(response);
}

export async function saveCourseModelDecision(
  courseId: string,
  operations: CourseModelOperation[],
  expectedChecksum: string,
  expectedImpactChecksum: string,
): Promise<{ courseModel: CourseModelData; checksum: string; allocatedIds: Record<string, string>; impact: ImpactPreview }> {
  const response = await apiFetch<Record<string, unknown>>(
    `/api/courses/${encodeURIComponent(courseId)}/course-model/decision`,
    {
      method: "PUT",
      body: JSON.stringify({
        expected_checksum: expectedChecksum,
        operations: operations.map((operation) => compactPayload(courseModelOperationPayload(operation))),
        impact_acknowledged: true,
        expected_impact_checksum: expectedImpactChecksum,
      }),
    },
  );
  const artifact = isRecord(response.artifact) ? response.artifact : {};
  return {
    courseModel: normalizeCourseModel(artifact.body, { modules: [], courseOutcomeIds: [], rationales: [], eligibleSources: [] }),
    checksum: asString(response.checksum),
    allocatedIds: isRecord(response.allocated_ids)
      ? Object.fromEntries(Object.entries(response.allocated_ids).filter((entry): entry is [string, string] => typeof entry[1] === "string"))
      : {},
    impact: normalizeImpactResponse(isRecord(response.impact) ? response.impact : {}, "course-model", "edit"),
  };
}

export async function saveBlueprintDecision(
  courseId: string,
  decision: BlueprintDecisionDraft,
  expectedChecksum: string,
): Promise<{ blueprint: Workspace["blueprint"]; checksum: string }> {
  const depthPayload = (depth: Partial<BlueprintDecisionDraft["defaultDepth"]>) => ({
    level: depth.depth,
    target_learning_minutes: depth.minutes,
    target_word_range: depth.wordMinimum === undefined && depth.wordTarget === undefined && depth.wordMaximum === undefined
      ? undefined
      : {
          minimum: depth.wordMinimum,
          target: depth.wordTarget,
          maximum: depth.wordMaximum,
        },
    required_example_count: depth.examples,
    case_depth: depth.caseDepth,
    assessment_complexity: depth.assessmentComplexity,
  });
  const response = await apiFetch<Record<string, unknown>>(
    `/api/courses/${encodeURIComponent(courseId)}/blueprint/decision`,
    {
      method: "PUT",
      body: JSON.stringify({
        expected_checksum: expectedChecksum,
        default_asset_types: decision.defaultAssetTypes,
        default_depth: compactPayload(depthPayload(decision.defaultDepth)),
        selected_asset_types: decision.selectedAssetTypes,
        depth_overrides: Object.fromEntries(
          Object.entries(decision.depthOverrides).map(([subtopicId, depth]) => [
            subtopicId,
            compactPayload(depthPayload(depth)),
          ]),
        ),
        anchor_waivers: decision.anchorWaivers,
        rationale: decision.rationale,
      }),
    },
  );
  const artifact = isRecord(response.artifact) ? response.artifact : {};
  const fallback: Workspace["blueprint"] = {
    defaults: { depth: "", minutes: 0, wordMinimum: 0, wordTarget: 0, wordMaximum: 0, examples: 0, caseDepth: "", assessmentComplexity: "", assetTypes: [] },
    plans: [],
  };
  return {
    blueprint: normalizeBlueprint(artifact.body, fallback),
    checksum: asString(response.checksum),
  };
}

export async function saveLessonPlanDecision(
  courseId: string,
  decision: LessonPlanDecisionDraft,
  expectedChecksum: string,
): Promise<{ lessonPlan: Workspace["lessonPlan"]; checksum: string }> {
  const response = await apiFetch<Record<string, unknown>>(
    `/api/courses/${encodeURIComponent(courseId)}/lesson-plan/decision`,
    {
      method: "PUT",
      body: JSON.stringify({
        expected_checksum: expectedChecksum,
        constraints: {
          max_session_hours: decision.constraints.maxSessionHours,
          default_mode: decision.constraints.defaultMode,
          calendar_dates: decision.constraints.calendarDates,
          instructor_count: decision.constraints.instructorCount,
          delivery_platform: decision.constraints.deliveryPlatform,
        },
        operations: decision.operations.map((operation) => operation.op === "reorder_session"
          ? { op: operation.op, session_ids: operation.sessionIds }
          : operation.op === "move_segment"
            ? {
                op: operation.op,
                target_id: operation.targetId,
                value: operation.value,
                position: operation.position,
              }
            : { op: operation.op, target_id: operation.targetId, value: operation.value }),
        rationale: decision.rationale,
      }),
    },
  );
  const artifact = isRecord(response.artifact) ? response.artifact : {};
  const fallback: Workspace["lessonPlan"] = {
    sessions: [],
    totalDurationMinutes: 0,
    expectedSubtopicIds: [],
    coveredSubtopicIds: [],
    constraints: {
      maxSessionHours: 2,
      defaultMode: "live",
      calendarDates: [],
      instructorCount: null,
      deliveryPlatform: null,
    },
    unresolvedConstraints: [],
    affectedSessionIds: [],
  };
  return {
    lessonPlan: normalizeLessonPlan(artifact.body, fallback),
    checksum: asString(response.checksum),
  };
}

export async function previewStageImpact(
  courseId: string,
  stage: StageSlug,
  expectedChecksum: string,
  command: {
    action: "reopen" | "revise";
    operationSummary?: string;
    targetType?: string;
    targetIds?: string[];
  },
): Promise<ImpactPreview> {
  const response = await apiFetch<Record<string, unknown>>(
    `/api/courses/${encodeURIComponent(courseId)}/stages/${stage}/impact`,
    {
      method: "POST",
      body: JSON.stringify({
        action: command.action,
        expected_checksum: expectedChecksum,
        operation_summary: command.operationSummary,
        target_type: command.targetType,
        target_ids: command.targetIds ?? [],
      }),
    },
  );
  return normalizeImpactResponse(response, stage, command.action);
}

export async function reopenStage(
  courseId: string,
  stage: StageSlug,
  command: {
    expectedChecksum: string;
    impactChecksum: string;
    reason?: string;
  },
): Promise<void> {
  await apiFetch(`/api/courses/${encodeURIComponent(courseId)}/stages/${stage}/reopen`, {
    method: "POST",
    body: JSON.stringify({
      expected_checksum: command.expectedChecksum,
      reason: command.reason,
      impact_acknowledged: true,
      expected_impact_checksum: command.impactChecksum,
    }),
  });
}

export async function reviseStage(
  courseId: string,
  stage: StageSlug,
  command: ScopedRevisionCommand,
): Promise<JobResponse> {
  const response = await apiFetch<Partial<JobResponse> & { job: JobResponse["job"] }>(`/api/courses/${encodeURIComponent(courseId)}/stages/${stage}/revisions`, {
    method: "POST",
    body: JSON.stringify({
      target_type: command.targetType,
      target_ids: command.targetIds,
      category: command.category,
      instruction: command.instruction,
      mode: command.mode,
      expected_checksum: command.expectedChecksum,
      impact_acknowledged: true,
      expected_impact_checksum: command.impactChecksum,
    }),
  });
  return {
    ...response,
    events_url: response.events_url ?? `/api/jobs/${response.job.job_id}/events`,
  };
}

export async function reviewContentAsset(
  courseId: string,
  assetId: string,
  status: "approved" | "changes_requested",
  expectedChecksum: string,
  note?: string,
): Promise<void> {
  await apiFetch(`/api/courses/${encodeURIComponent(courseId)}/content/reviews/${encodeURIComponent(assetId)}`, {
    method: "PUT",
    body: JSON.stringify({ decision: status, expected_checksum: expectedChecksum, feedback: note }),
  });
}

function outcomeEditPayload(edit: OutcomeEdit): Record<string, unknown> {
  return Object.fromEntries(Object.entries({
    statement: edit.statement,
    evidence: edit.evidence,
    cognitive_level: edit.cognitiveLevel,
    priority: edit.priority,
  }).filter(([, value]) => value !== undefined));
}

export async function saveOutcomeDecision(
  courseId: string,
  command: OutcomeDecisionCommand,
): Promise<{ outcomes: Outcome[]; checksum: string; advisories: OutcomeAdvisory[] }> {
  const response = await apiFetch<Record<string, unknown>>(
    `/api/courses/${encodeURIComponent(courseId)}/outcomes/decision`,
    {
      method: "PUT",
      body: JSON.stringify({
        expected_checksum: command.expectedChecksum,
        selected_ids: command.selectedIds,
        edits: Object.fromEntries(
          Object.entries(command.edits).map(([outcomeId, edit]) => [outcomeId, outcomeEditPayload(edit)]),
        ),
        additions: command.additions.map((addition) => ({
          client_key: addition.clientKey,
          statement: addition.statement,
          evidence: addition.evidence,
          cognitive_level: addition.cognitiveLevel,
          priority: addition.priority,
        })),
        priority_order: command.priorityOrder,
      }),
    },
  );
  const artifact = isRecord(response.artifact) ? response.artifact : {};
  return {
    outcomes: normalizeOutcomes(artifact.body, []),
    checksum: asString(response.checksum),
    advisories: normalizeOutcomeAdvisories(response.advisories),
  };
}

export async function saveSourceDecision(
  courseId: string,
  selectedIds: string[],
  expectedChecksum: string,
): Promise<void> {
  await apiFetch(`/api/courses/${encodeURIComponent(courseId)}/research/sources/decision`, {
    method: "PUT",
    body: JSON.stringify({
      selected_ids: selectedIds,
      expected_checksum: expectedChecksum,
    }),
  });
}

export interface JobEvent {
  event_id: string;
  job_id: string;
  course_id: string;
  event_type: string;
  timestamp: string;
  stage?: StageSlug;
  message: string;
  progress?: { completed?: number; expected?: number };
}

export function subscribeToJob(jobId: string, onEvent: (event: JobEvent) => void): () => void {
  const stream = new EventSource(`/api/jobs/${encodeURIComponent(jobId)}/events`);
  const eventTypes = [
    "job.queued",
    "job.started",
    "stage.started",
    "unit.started",
    "unit.completed",
    "unit.failed",
    "stage.output_ready",
    "checkpoint.awaiting_review",
    "stage.approved",
    "job.completed",
    "job.failed",
  ];
  const listener = (message: MessageEvent) => {
    try {
      onEvent(JSON.parse(message.data) as JobEvent);
    } catch {
      // Ignore malformed progress events; the next workspace refresh is canonical.
    }
  };
  eventTypes.forEach((eventType) => stream.addEventListener(eventType, listener as EventListener));
  return () => {
    eventTypes.forEach((eventType) => stream.removeEventListener(eventType, listener as EventListener));
    stream.close();
  };
}
