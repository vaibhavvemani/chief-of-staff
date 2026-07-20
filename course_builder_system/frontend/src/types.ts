export type StageSlug =
  | "brief"
  | "outcomes"
  | "research"
  | "course-model"
  | "blueprint"
  | "content"
  | "lesson-plan"
  | "package";

export type UiStatus =
  | "locked"
  | "needs_input"
  | "ready"
  | "running"
  | "awaiting_review"
  | "approved"
  | "requires_attention"
  | "stale"
  | "failed";

export type StageActionId =
  | "run"
  | "retry"
  | "edit"
  | "add_source"
  | "source_decision"
  | "source_repair"
  | "content_repair"
  | "review_asset"
  | "revise"
  | "approve"
  | "reopen"
  | "go_to_blocker"
  | "continue";

export interface StageAction {
  id: StageActionId;
  label: string;
  enabled: boolean;
  reason?: string;
  requiresImpactConfirmation: boolean;
  targetStage?: StageSlug;
  revisionTargets?: Array<{
    targetType: string;
    categories: string[];
  }>;
}

export interface ApprovalFailure {
  code: string;
  message: string;
  artifactType?: string;
  targetIds?: string[];
}

export interface StageSummary {
  slug: StageSlug;
  label: string;
  status: UiStatus;
  count?: number;
  summary?: string;
  updatedAt?: string;
  checksum?: string;
  dependencies: string[];
  downstreamStages: StageSlug[];
  prerequisitesReady: boolean;
  approvalFailures: ApprovalFailure[];
  lastFailure?: string;
  actions: StageAction[];
}

export interface CourseSummary {
  courseId: string;
  title: string;
  subject: string;
  status: UiStatus;
  currentStage: StageSlug;
  nextAction: string;
  updatedAt: string;
  progress: number;
  attentionCount: number;
  approvedStages: number;
  totalStages: number;
  demo?: boolean;
}

export type QuestionAnswerType =
  | "free_text"
  | "single_choice"
  | "multiple_choice"
  | "number"
  | "duration"
  | "confirmation";

export type QuestionAnswerValue = string | string[] | number | boolean | null;

export type BriefGapKind = "missing" | "ambiguity" | "conflict";
export type BriefGapSeverity = "low" | "medium" | "high";
export type BriefQuestionRoundKind =
  | "mandatory"
  | "conditional"
  | "clarification"
  | "complete";

export interface BriefGap {
  id: string;
  kind: BriefGapKind;
  field: string;
  severity: BriefGapSeverity;
  message: string;
}

export interface BriefIntakeState {
  explicitFields: string[];
  acceptedDefaultFields: string[];
  unresolvedRequiredFields: string[];
  answeredQuestionIds: string[];
  lastGapAnalysis: BriefGap[];
}

export interface BriefProvenance {
  field: string;
  source: "user" | "default";
  confidence: "explicit" | "assumed";
}

export interface BriefQuestionSpec {
  id: string;
  field: string;
  prompt: string;
  rationale: string;
  answerType: QuestionAnswerType;
  options: string[];
  defaultValue?: QuestionAnswerValue;
  required: boolean;
  allowSkip: boolean;
  visibility: Record<string, unknown>;
}

export interface BriefQuestionRound {
  questions: BriefQuestionSpec[];
  roundKind: BriefQuestionRoundKind;
  gapAnalysis: BriefGap[];
  intakeState: BriefIntakeState;
  checksum: string;
}

export interface BriefQuestionAnswer {
  questionId: string;
  value?: QuestionAnswerValue;
  acceptDefault?: boolean;
  skip?: boolean;
}

export interface BriefData {
  courseTitle: string;
  subject: string;
  audience: string;
  priorKnowledge: string;
  purpose: string;
  level: string;
  duration: string;
  modality: string;
  language: string;
  inScope: string[];
  outOfScope: string[];
  mustHaveTopics: string[];
  constraints: string[];
  availableMaterials: string[];
  jurisdiction: string | null;
  accessibilityRequirements: string | null;
  assessmentExpectations: string | null;
  liveTeachingConstraints: string | null;
  toolsOrEquipment: string | null;
  freshnessRequirement: string | null;
  assumptions: Array<{ field: string; value: string; rationale: string }>;
  provenance: BriefProvenance[];
  intakeState: BriefIntakeState;
}

export type OutcomeCognitiveLevel =
  | "remember"
  | "understand"
  | "apply"
  | "analyze"
  | "evaluate"
  | "create";

export type OutcomePriority = "core" | "supporting" | "optional";

export interface Outcome {
  id: string;
  statement: string;
  cognitiveLevel: OutcomeCognitiveLevel;
  evidence: string;
  priority: OutcomePriority;
}

export type OutcomeEditableField =
  | "statement"
  | "evidence"
  | "cognitiveLevel"
  | "priority";

export interface OutcomeEdit {
  statement?: string;
  evidence?: string;
  cognitiveLevel?: OutcomeCognitiveLevel;
  priority?: OutcomePriority;
}

export interface OutcomeAddition {
  clientKey: string;
  statement: string;
  evidence: string;
  cognitiveLevel: OutcomeCognitiveLevel;
  priority: OutcomePriority;
}

export interface OutcomeDecisionDraft {
  selectedIds: string[];
  edits: Record<string, OutcomeEdit>;
  additions: OutcomeAddition[];
  priorityOrder: string[];
}

export interface OutcomeDecisionCommand extends OutcomeDecisionDraft {
  expectedChecksum: string;
}

export interface OutcomeAdvisory {
  code: string;
  outcomeId: string;
  relatedOutcomeId?: string;
  field: string;
  reason: string;
  level: "advisory";
}

export interface OutcomeValidationIssue {
  code: string;
  message: string;
  outcomeId?: string;
  field?: string;
  index?: number;
}

export interface SourceCandidate {
  id: string;
  title: string;
  publisher: string;
  sourceType: string;
  locator: string;
  status: "approved" | "proposed" | "rejected" | "unavailable" | string;
  trustNotes: string;
  relevance: string;
  assignedNodeIds: string[];
  quality?: SourceQuality;
}

export interface SourceQuality {
  overall: number;
  recommendation: "strong_candidate" | "review_candidate" | "weak_candidate" | string;
  advisoryOnly: boolean;
  dimensions: Record<string, { score: number; reason: string }>;
  previewSections: Array<{
    order: number;
    text: string;
    matchedTerms: string[];
    relevanceScore: number;
  }>;
  coverage: Array<{ need: string; score: number; matchedTerms: string[] }>;
  fetchReason?: string | null;
}

export interface SourceRepairCandidate {
  id: string;
  title: string;
  publisher: string;
  sourceType: string;
  locator: string;
  trustNotes: string;
  relevance: string;
  fetchStatus: "available" | "unavailable" | string;
  fetchReason?: string | null;
  quality: SourceQuality;
}

export interface SourceRepairEntry {
  id: string;
  origin: {
    subtopicId: string;
    assetId: string;
    claimId: string;
    findingId: string;
    contentChecksum: string;
  };
  evidenceGap: string;
  requestedMode: "deterministic" | "live";
  proposedCandidates: SourceRepairCandidate[];
  humanSourceDecision?: {
    candidateId: string;
    decision: "approved" | "rejected";
    rationale: string;
  } | null;
  approvedSourceRoute?: {
    sourceId: string;
    subtopicIds: string[];
    assetIds: string[];
  } | null;
  affectedAssetIds: string[];
  status: "requested" | "researching" | "awaiting_source_decision" | "awaiting_route_confirmation" | "awaiting_content_repair" | "regenerating" | "awaiting_content_review" | "resolved" | "failed";
  failureReason?: string | null;
  finalVerifierResult?: {
    hardBlockerTotal: number;
    partialTotal: number;
    reviewStatus: string;
  } | null;
}

export type ContentRepairClassification =
  | "likely_content_error"
  | "missing_attribution"
  | "insufficient_evidence"
  | "human_review";

export interface ContentRepairFinding {
  id: string;
  subtopicId: string;
  assetId: string;
  claimId?: string | null;
  findingId: string;
  text: string;
  note: string;
  classification: ContentRepairClassification;
  classificationReason: string;
  recommendedStrategy?: "existing_evidence" | "better_evidence" | null;
  blocking: boolean;
  state: SourceRepairEntry["status"] | "ready";
  sourceRepairId?: string | null;
}

export interface ContentRepairProjection {
  findings: ContentRepairFinding[];
  groups: Record<ContentRepairClassification, number>;
  hardBlockerTotal: number;
  partialTotal: number;
  readyForPackage: boolean;
}

export interface CompetitorFinding {
  id: string;
  provider: string;
  offering: string;
  locator: string;
  outlineStatus: string;
  outlineSections: string[];
  structureSummary: string;
}

export interface Concept {
  id: string;
  name: string;
  summary: string;
  dependsOn: string[];
  sourceIds: string[];
}

export interface CoverageRequirement {
  id: string;
  statement: string;
  conceptIds: string[];
  sourceIds: string[];
}

export interface Subtopic {
  id: string;
  order: number;
  title: string;
  purpose: string;
  inScope: string[];
  outOfScope: string[];
  prerequisiteSubtopicIds: string[];
  concepts: Concept[];
  coverageRequirements: CoverageRequirement[];
  approvedSourceIds: string[];
}

export interface CourseModule {
  id: string;
  order: number;
  title: string;
  purpose: string;
  inScope: string[];
  outOfScope: string[];
  prerequisiteModuleIds: string[];
  subtopics: Subtopic[];
}

export interface CourseModelRationale {
  id: string;
  statement: string;
  relatedOutcomeIds: string[];
}

export interface CourseModelSource {
  id: string;
  title: string;
  publisher: string;
}

export interface CourseModelData {
  modules: CourseModule[];
  courseOutcomeIds: string[];
  rationales: CourseModelRationale[];
  eligibleSources: CourseModelSource[];
}

export type CourseModelOperation =
  | { op: "add_module"; clientRef: string; position: number; title: string; purpose: string; inScope: string[]; outOfScope: string[]; prerequisiteModuleIds: string[] }
  | { op: "update_module"; targetId: string; title?: string; purpose?: string; inScope?: string[]; outOfScope?: string[]; prerequisiteModuleIds?: string[] }
  | { op: "remove_module"; targetId: string }
  | { op: "move_module"; targetId: string; position: number }
  | { op: "reorder_modules"; moduleIds: string[] }
  | { op: "add_subtopic"; clientRef: string; parentId: string; position: number; title: string; purpose: string; inScope: string[]; outOfScope: string[]; prerequisiteSubtopicIds: string[] }
  | { op: "update_subtopic"; targetId: string; title?: string; purpose?: string; inScope?: string[]; outOfScope?: string[]; prerequisiteSubtopicIds?: string[] }
  | { op: "remove_subtopic"; targetId: string }
  | { op: "move_subtopic"; targetId: string; parentId: string; position: number }
  | { op: "reorder_subtopics"; parentId: string; subtopicIds: string[] }
  | { op: "add_concept"; clientRef: string; parentId: string; position: number; name: string; summary: string; dependsOn: string[] }
  | { op: "update_concept"; targetId: string; name?: string; summary?: string; dependsOn?: string[] }
  | { op: "remove_concept"; targetId: string }
  | { op: "add_coverage"; clientRef: string; parentId: string; position: number; statement: string; conceptIds: string[] }
  | { op: "update_coverage"; targetId: string; statement?: string; conceptIds?: string[] }
  | { op: "remove_coverage"; targetId: string }
  | { op: "assign_sources"; targetType: "subtopic" | "concept" | "coverage"; targetId: string; sourceIds: string[] }
  | { op: "set_course_outcome_links"; outcomeIds: string[] }
  | { op: "set_rationale_outcome_links"; targetId: string; outcomeIds: string[] };

export interface CourseModelValidationIssue {
  code: string;
  message: string;
  operationIndex?: number;
  recordType?: string;
  recordId?: string;
  field?: string;
  path?: string;
}

export interface CourseModelChangeRecord {
  operationIndex: number;
  op: string;
  action: string;
  recordType: string;
  recordId?: string;
  recordIds: string[];
  parentId?: string;
}

export interface CourseModelPreview {
  candidate: CourseModelData;
  allocatedIds: Record<string, string>;
  changeRecords: CourseModelChangeRecord[];
  affectedRecords: Record<string, { changedIds: string[]; removedIds: string[] }>;
  impact: ImpactPreview;
}

export interface AssetPlan {
  id: string;
  assetType: BlueprintAssetType;
  title: string;
  selectionStatus: "selected" | "proposed" | "rejected" | string;
  sourceIds: string[];
}

export type BlueprintAssetType =
  | "learning_objectives"
  | "course_content"
  | "summary"
  | "case_study"
  | "assessment"
  | "activities"
  | "resources";

export interface BlueprintDepthValues {
  depth: string;
  minutes: number;
  wordMinimum: number;
  wordTarget: number;
  wordMaximum: number;
  examples: number;
  caseDepth: string;
  assessmentComplexity: string;
}

export interface BlueprintPlan {
  subtopicId: string;
  depth: string;
  minutes: number;
  wordMinimum: number;
  wordTarget: number;
  wordMaximum: number;
  examples: number;
  caseDepth: string;
  assessmentComplexity: string;
  exception: boolean;
  anchorWaiverConfirmed: boolean;
  assets: AssetPlan[];
}

export interface BlueprintDecisionDraft {
  defaultAssetTypes: BlueprintAssetType[];
  defaultDepth: BlueprintDepthValues;
  selectedAssetTypes: Record<string, BlueprintAssetType[]>;
  depthOverrides: Record<string, Partial<BlueprintDepthValues>>;
  anchorWaivers: string[];
  rationale: string;
}

export interface Claim {
  id: string;
  text: string;
  sourceId?: string | null;
  support: "supported" | "partial" | "unsupported" | "ungrounded" | string;
  excerpt?: string | null;
  note?: string;
}

export interface ContentAsset {
  id: string;
  subtopicId: string;
  type: string;
  title: string;
  format: string;
  content: string;
  status: UiStatus | "done";
  reviewStatus: "approved" | "pending" | "changes_requested";
  claims: Claim[];
  verification: {
    supported: number;
    partial: number;
    unsupported: number;
    ungrounded: number;
    unattributed: number;
  };
}

export interface LessonSession {
  id: string;
  order: number;
  title: string;
  durationMinutes: number;
  covers: Array<{
    subtopicId: string;
    mode: "live" | "self_study" | "blended" | string;
    talkingPoints: string[];
  }>;
}

export type LessonMode = "live" | "self_study";

export interface LessonPlanConstraints {
  maxSessionHours: number;
  defaultMode: LessonMode;
  calendarDates: string[];
  instructorCount: number | null;
  deliveryPlatform: string | null;
}

export type LessonPlanOperation =
  | { op: "set_mode"; targetId: string; value: LessonMode }
  | { op: "move_segment"; targetId: string; value: string; position: number }
  | { op: "reorder_session"; sessionIds: string[] };

export interface LessonPlanDecisionDraft {
  constraints: LessonPlanConstraints;
  operations: LessonPlanOperation[];
  rationale: string;
}

export interface OutputFile {
  path: string;
  label: string;
  kind: "folder" | "markdown";
  children?: OutputFile[];
}

export interface ActivityEvent {
  id: string;
  at: string;
  title: string;
  detail: string;
  tone?: "neutral" | "good" | "attention";
}

export interface Workspace {
  course: CourseSummary;
  stages: StageSummary[];
  activeJob?: {
    jobId: string;
    status: "queued" | "running";
    stage: StageSlug;
  };
  artifactVersion: string;
  estimatedCost?: number;
  brief: BriefData;
  outcomes: Outcome[];
  outcomesChecksum?: string;
  outcomeAdvisories?: OutcomeAdvisory[];
  research: {
    sources: SourceCandidate[];
    competitors: CompetitorFinding[];
    observations: string[];
    registrySaved?: boolean;
    registryApproved?: boolean;
    dossierChecksum?: string;
  };
  sourceRepairs: SourceRepairEntry[];
  sourceRepairChecksum?: string;
  contentRepairs: ContentRepairProjection;
  modules: CourseModule[];
  courseModel: CourseModelData;
  courseModelChecksum?: string;
  blueprint: {
    defaults: BlueprintDepthValues & { assetTypes: BlueprintAssetType[] };
    plans: BlueprintPlan[];
  };
  blueprintChecksum?: string;
  content: {
    assets: ContentAsset[];
    completed: number;
    expected: number;
    reviewChecksum?: string;
    packageChecksum?: string;
  };
  lessonPlan: {
    sessions: LessonSession[];
    totalDurationMinutes: number;
    expectedSubtopicIds: string[];
    coveredSubtopicIds: string[];
    constraints: LessonPlanConstraints;
    unresolvedConstraints: string[];
    affectedSessionIds: string[];
  };
  lessonPlanChecksum?: string;
  package: {
    format: string;
    operatorStatus: string;
    integrityPassed: boolean;
    approvedSourceCount: number;
    rejectedSourceLeaks: number;
    selectedAssets: number;
    renderedAssets: number;
    unresolvedBlockers: number;
    files: OutputFile[];
  };
  activity: ActivityEvent[];
  briefChecksum?: string;
}

export interface BriefUpdates {
  courseTitle?: string;
  audience?: string;
  priorKnowledge?: string;
  purpose?: string;
  level?: string;
  duration?: string;
  modality?: string;
  language?: string;
  inScope?: string[];
  outOfScope?: string[];
  mustHaveTopics?: string[];
  constraints?: string[];
  availableMaterials?: string[];
  jurisdiction?: string | null;
  accessibilityRequirements?: string | null;
  assessmentExpectations?: string | null;
  liveTeachingConstraints?: string | null;
  toolsOrEquipment?: string | null;
  freshnessRequirement?: string | null;
}

export interface CreateCourseRequest {
  courseId?: string;
  subject: string;
  description?: string;
  constraints?: string;
  sourceUrls?: string[];
  brief?: BriefUpdates;
}

export interface StageCommand {
  expectedChecksum?: string;
  note?: string;
  mode?: "deterministic" | "live";
}

export interface ImpactPreview {
  action: "reopen" | "edit" | "revise" | "repair";
  stage: StageSlug;
  operationSummary?: string;
  directArtifacts: string[];
  staleArtifacts: string[];
  targetedAssets: string[];
  preservedAssets: string[];
  requiresRerunStages: StageSlug[];
  warnings: string[];
  impactLevel: "targeted" | "downstream" | "full";
  impactChecksum: string;
}

export interface ScopedRevisionCommand {
  targetType: string;
  targetIds: string[];
  category: string;
  instruction: string;
  expectedChecksum: string;
  impactChecksum: string;
  mode: "deterministic" | "live";
}

export interface ContentRepairCommand {
  strategy: "existing_evidence" | "better_evidence";
  targets: Array<{
    assetId: string;
    claimIds?: string[];
    findingIds?: string[];
  }>;
  expectedContentChecksum: string;
  sourceRepairId?: string;
  expectedSourceRepairChecksum?: string;
  mode: "deterministic" | "live";
}

export interface JobResponse {
  job: {
    job_id: string;
    status: "queued" | "running" | "completed" | "failed";
  };
  job_url?: string;
  events_url: string;
}
