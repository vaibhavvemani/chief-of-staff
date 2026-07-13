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
  | "ready"
  | "running"
  | "awaiting_review"
  | "approved"
  | "requires_attention"
  | "stale"
  | "failed";

export interface StageSummary {
  slug: StageSlug;
  label: string;
  status: UiStatus;
  count?: number;
  summary?: string;
  updatedAt?: string;
  checksum?: string;
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
  assessmentExpectations: string;
  assumptions: Array<{ field: string; value: string; rationale: string }>;
}

export interface Outcome {
  id: string;
  statement: string;
  cognitiveLevel: string;
  evidence: string;
  priority: "core" | "supporting" | string;
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
  coverageRequirements: Array<{ id: string; statement: string; sourceIds: string[] }>;
  approvedSourceIds: string[];
}

export interface CourseModule {
  id: string;
  order: number;
  title: string;
  purpose: string;
  subtopics: Subtopic[];
}

export interface AssetPlan {
  id: string;
  assetType: string;
  title: string;
  selectionStatus: "selected" | "proposed" | "rejected" | string;
  sourceIds: string[];
}

export interface BlueprintPlan {
  subtopicId: string;
  depth: string;
  minutes: number;
  wordTarget: number;
  examples: number;
  caseDepth: string;
  assessmentComplexity: string;
  exception: boolean;
  assets: AssetPlan[];
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
  artifactVersion: string;
  estimatedCost?: number;
  brief: BriefData;
  outcomes: Outcome[];
  research: {
    sources: SourceCandidate[];
    competitors: CompetitorFinding[];
    observations: string[];
  };
  modules: CourseModule[];
  blueprint: {
    defaults: {
      depth: string;
      minutes: number;
      wordTarget: number;
      examples: number;
      caseDepth: string;
      assessmentComplexity: string;
    };
    plans: BlueprintPlan[];
  };
  content: {
    assets: ContentAsset[];
    completed: number;
    expected: number;
    reviewChecksum?: string;
  };
  lessonPlan: {
    sessions: LessonSession[];
    totalDurationMinutes: number;
    expectedSubtopicIds: string[];
    coveredSubtopicIds: string[];
  };
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

export interface BriefAnswers {
  courseTitle?: string;
  audience: string;
  priorKnowledge: string;
  purpose?: string;
  level: string;
  duration: string;
  modality: string;
  language: string;
  inScope?: string[];
  outOfScope?: string[];
  mustHaveTopics?: string[];
  constraints?: string[];
  assessmentExpectations?: string;
}

export interface CreateCourseRequest {
  subject: string;
  description?: string;
  constraints?: string;
  sourceUrls?: string[];
  briefAnswers: BriefAnswers;
}

export interface StageCommand {
  expectedChecksum?: string;
  note?: string;
  mode?: "deterministic" | "live";
}

export interface JobResponse {
  job: {
    job_id: string;
    status: "queued" | "running" | "completed" | "failed";
  };
  job_url?: string;
  events_url: string;
}
