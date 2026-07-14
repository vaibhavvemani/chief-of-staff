import { demoCourses, demoWorkspaceFor } from "../data/demo";
import type {
  BlueprintPlan,
  BriefAnswers,
  BriefData,
  ContentAsset,
  CourseModule,
  CourseSummary,
  CreateCourseRequest,
  JobResponse,
  LessonSession,
  Outcome,
  OutputFile,
  SourceCandidate,
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
    }
    throw new ApiError(message, response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
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

const stageStateMap: Record<string, UiStatus> = {
  completed: "approved",
  pending_review: "awaiting_review",
  attention: "requires_attention",
  requires_attention: "requires_attention",
  not_started: "ready",
};

function normalizeStatus(value: unknown, fallback: UiStatus = "ready"): UiStatus {
  const raw = asString(value).toLowerCase();
  const valid: UiStatus[] = [
    "locked",
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
  stages?: Array<{
    slug?: string;
    label?: string;
    state?: string;
    attention_count?: number;
    checksum?: string;
    can_mutate?: boolean;
  }>;
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
    assessmentExpectations: asString(value.assessment_expectations, fallback.assessmentExpectations),
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
  };
}

function normalizeOutcomes(value: unknown, fallback: Outcome[]): Outcome[] {
  if (!isRecord(value)) return fallback;
  const outcomes = asArray(value.outcomes).flatMap((item) =>
    isRecord(item)
      ? [
          {
            id: asString(item.id),
            statement: asString(item.statement),
            cognitiveLevel: asString(item.cognitive_level),
            evidence: asString(item.evidence),
            priority: asString(item.priority),
          },
        ]
      : [],
  );
  return outcomes.length ? outcomes : fallback;
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

function normalizeModules(value: unknown, fallback: CourseModule[]): CourseModule[] {
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
  return modules.length ? modules : fallback;
}

function normalizeBlueprint(value: unknown, fallback: Workspace["blueprint"]): Workspace["blueprint"] {
  if (!isRecord(value)) return fallback;
  const defaultsValue = isRecord(value.course_defaults) ? value.course_defaults : {};
  const depth = isRecord(defaultsValue.depth_budget) ? defaultsValue.depth_budget : {};
  const wordRange = isRecord(depth.target_word_range) ? depth.target_word_range : {};
  const plans: BlueprintPlan[] = asArray(value.subtopic_plans).flatMap((planValue) => {
    if (!isRecord(planValue)) return [];
    const budget = isRecord(planValue.depth_budget) ? planValue.depth_budget : {};
    const range = isRecord(budget.target_word_range) ? budget.target_word_range : {};
    return [
      {
        subtopicId: asString(planValue.subtopic_id),
        depth: asString(budget.level),
        minutes: asNumber(budget.target_learning_minutes),
        wordTarget: asNumber(range.target),
        examples: asNumber(budget.required_example_count),
        caseDepth: asString(budget.case_depth),
        assessmentComplexity: asString(budget.assessment_complexity),
        exception: asString(budget.case_depth) !== asString(depth.case_depth),
        assets: asArray(planValue.asset_plan).flatMap((asset) =>
          isRecord(asset)
            ? [
                {
                  id: asString(asset.id),
                  assetType: asString(asset.asset_type),
                  title: asString(asset.title),
                  selectionStatus: asString(asset.selection_status),
                  sourceIds: asStringArray(asset.source_ids),
                },
              ]
            : [],
        ),
      },
    ];
  });
  return {
    defaults: {
      depth: asString(depth.level, fallback.defaults.depth),
      minutes: asNumber(depth.target_learning_minutes, fallback.defaults.minutes),
      wordTarget: asNumber(wordRange.target, fallback.defaults.wordTarget),
      examples: asNumber(depth.required_example_count, fallback.defaults.examples),
      caseDepth: asString(depth.case_depth, fallback.defaults.caseDepth),
      assessmentComplexity: asString(depth.assessment_complexity, fallback.defaults.assessmentComplexity),
    },
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
  return sessions.length
    ? {
        sessions,
        totalDurationMinutes: asNumber(coverage.total_duration_minutes),
        expectedSubtopicIds: asStringArray(coverage.expected_subtopic_ids),
        coveredSubtopicIds: asStringArray(coverage.covered_subtopic_ids),
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
        assessmentExpectations: "Short practical checks and scenario questions.",
        assumptions: [],
      },
      outcomes: [],
      research: { sources: [], competitors: [], observations: [], registrySaved: false, registryApproved: false },
      modules: [],
      blueprint: {
        defaults: { depth: "", minutes: 0, wordTarget: 0, examples: 0, caseDepth: "", assessmentComplexity: "" },
        plans: [],
      },
      content: { assets: [], completed: 0, expected: 0 },
      lessonPlan: { sessions: [], totalDurationMinutes: 0, expectedSubtopicIds: [], coveredSubtopicIds: [] },
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
        ["requires_attention", "failed", "awaiting_review", "ready", "stale"].includes(item.status),
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
      modules: normalizeModules(artifacts.get("course_model")?.body, base.modules),
      blueprint: normalizeBlueprint(artifacts.get("blueprint")?.body, base.blueprint),
      content,
      lessonPlan: normalizeLessonPlan(artifacts.get("lesson_plan")?.body, base.lessonPlan),
      package: {
        ...base.package,
        operatorStatus: asString(summaryRecord.operator_status, projection.operator_status ?? base.package.operatorStatus),
        integrityPassed:
          normalizedStages.find((item) => item.slug === "package")?.status === "approved" && blockingTotal === 0,
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
      return { workspace: demoWorkspaceFor(courseId), demoMode: true, readOnly: false };
    }
    throw error;
  }
}

function workspaceSourceCount(value: unknown): number {
  return isRecord(value) ? asArray(value.source_registry).length : 0;
}

export async function createCourse(request: CreateCourseRequest): Promise<{ courseId: string; briefInitialized: boolean }> {
  const data = await apiFetch<{ course_id?: string; courseId?: string }>("/api/courses", {
    method: "POST",
    body: JSON.stringify({
      subject: request.subject,
      description: request.description,
      constraints: request.constraints
        ? request.constraints.split("\n").map((value) => value.trim()).filter(Boolean)
        : [],
      known_source_locators: request.sourceUrls ?? [],
    }),
  });
  const courseId = data.course_id ?? data.courseId ?? "";
  try {
    await saveBriefAnswers(courseId, request.briefAnswers);
    return { courseId, briefInitialized: true };
  } catch (error) {
    // The subject request already exists. Preserve that successful creation so a
    // transient connection loss does not lead the user into a duplicate-course retry.
    if (error instanceof ApiError && error.status === 0) return { courseId, briefInitialized: false };
    throw error;
  }
}

function briefAnswersPayload(answers: BriefAnswers): Record<string, unknown> {
  return {
    course_title: answers.courseTitle,
    audience: answers.audience,
    prior_knowledge: answers.priorKnowledge,
    purpose: answers.purpose,
    level: answers.level,
    duration: answers.duration,
    modality: answers.modality,
    language: answers.language,
    in_scope: answers.inScope,
    out_of_scope: answers.outOfScope,
    must_have_topics: answers.mustHaveTopics,
    constraints: answers.constraints,
    assessment_expectations: answers.assessmentExpectations,
  };
}

export async function saveBriefAnswers(
  courseId: string,
  answers: BriefAnswers,
  expectedChecksum?: string,
): Promise<{ checksum?: string }> {
  return apiFetch<{ checksum?: string }>(`/api/courses/${encodeURIComponent(courseId)}/brief/answers`, {
    method: "PUT",
    body: JSON.stringify({
      answers: Object.fromEntries(Object.entries(briefAnswersPayload(answers)).filter(([, value]) => value !== undefined)),
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
  await apiFetch(`/api/courses/${encodeURIComponent(courseId)}/stages/${stage}/approve`, {
    method: "POST",
    body: JSON.stringify({ expected_checksum: command.expectedChecksum }),
  });
}

export async function requestStageChanges(courseId: string, stage: StageSlug, command: StageCommand): Promise<JobResponse> {
  const response = await apiFetch<Partial<JobResponse> & { job: JobResponse["job"] }>(`/api/courses/${encodeURIComponent(courseId)}/stages/${stage}/request-changes`, {
    method: "POST",
    body: JSON.stringify({ expected_checksum: command.expectedChecksum, feedback: command.note ?? "Please revise this stage.", mode: command.mode ?? "deterministic" }),
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
  expectedChecksum: string | undefined,
  note?: string,
): Promise<void> {
  await apiFetch(`/api/courses/${encodeURIComponent(courseId)}/content/reviews/${encodeURIComponent(assetId)}`, {
    method: "PUT",
    body: JSON.stringify({ decision: status, expected_checksum: expectedChecksum, feedback: note }),
  });
}

export async function saveSourceDecision(
  courseId: string,
  selectedIds: string[],
  expectedChecksum?: string,
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
