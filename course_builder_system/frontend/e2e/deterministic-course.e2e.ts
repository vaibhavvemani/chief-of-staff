import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { createHash } from "node:crypto";

const SEEDED_LIFECYCLE_COURSE_ID = "studio-course-model-reopen-fixture";
const PACKAGE_PREVIEW_COURSE_ID = "studio-package-preview-fixture";
const COURSE_MODEL_EDITOR_COURSE_ID = "studio-course-model-editor-fixture";
const BLUEPRINT_EDITOR_COURSE_ID = "studio-blueprint-editor-fixture";
const LESSON_PLAN_EDITOR_COURSE_ID = "studio-lesson-plan-editor-fixture";
const SOURCE_REPAIR_COURSE_ID = "studio-source-repair-fixture";
const CONTENT_REPAIR_COURSE_ID = "studio-content-repair-fixture";
const CONTENT_BLOCKER_TRUTH_COURSE_ID = "studio-content-blocker-truth-fixture";
const REOPEN_RERUN_COURSE_ID = "studio-reopen-rerun-fixture";
const FAILURE_RECOVERY_COURSE_ID = "studio-failure-recovery-fixture";
const ACTIVE_REFRESH_COURSE_ID = "studio-active-refresh-fixture";
const RESTART_RECOVERY_COURSE_ID = "studio-restart-recovery-fixture";
const NEGATIVE_SOURCE_COURSE_ID = "studio-negative-source-fixture";
const READ_ONLY_ACCEPTANCE_COURSE_ID = "coffee-acceptance";

interface StageProjection {
  state: string;
  checksum?: string;
  prerequisites_ready?: boolean;
}

interface BriefQuestion {
  id: string;
  field: string;
  prompt: string;
  answer_type: string;
  options: string[];
  default?: string | number | boolean | string[] | null;
  required: boolean;
  allow_skip: boolean;
}

interface BriefRound {
  questions: BriefQuestion[];
  round_kind: "mandatory" | "conditional" | "clarification" | "complete";
  gap_analysis: Array<{ id: string; field: string; severity: string }>;
  intake_state: BriefIntakeState;
  checksum: string;
}

interface BriefIntakeState {
  explicit_fields: string[];
  accepted_default_fields: string[];
  unresolved_required_fields: string[];
  answered_question_ids: string[];
  last_gap_analysis: Array<{ id: string; field: string; severity: string }>;
}

interface BriefArtifact {
  artifact: {
    body: Record<string, unknown> & { intake_state: BriefIntakeState };
  };
  checksum: string;
}

interface OutcomeRecord {
  id: string;
  statement: string;
  evidence: string;
  cognitive_level: string;
  priority: string;
}

interface OutcomesArtifact {
  artifact: {
    body: { outcomes: OutcomeRecord[] };
  };
  checksum: string;
}

interface BlueprintArtifact {
  artifact: {
    body: {
      course_defaults: {
        default_asset_types: string[];
      };
      subtopic_plans: Array<{
        subtopic_id: string;
        anchor_asset_waiver_confirmed: boolean;
        depth_budget: {
          target_learning_minutes: number;
          required_example_count: number;
        };
        asset_plan: Array<{
          id: string;
          asset_type: string;
          selection_status: string;
          source_ids: string[];
        }>;
      }>;
    };
  };
  checksum: string;
}

interface LessonPlanArtifact {
  artifact: {
    body: {
      session_constraints: {
        max_session_hours: number;
        default_mode: string;
        calendar_dates?: string[];
        instructor_count?: number | null;
        delivery_platform?: string | null;
      };
      unresolved_session_constraints: string[];
      sessions: Array<{
        id: string;
        order: number;
        duration_minutes: number;
        covers: Array<{ subtopic_id: string; mode: string }>;
      }>;
      coverage_summary: {
        expected_subtopic_ids: string[];
        covered_subtopic_ids: string[];
        total_duration_minutes: number;
      };
      decision_log: Array<{ affected_session_ids: string[] }>;
    };
  };
  checksum: string;
}

interface CanonicalArtifact<TBody> {
  artifact: {
    body: TBody;
  };
  checksum: string;
}

interface SourceRecord {
  id: string;
  status?: string;
}

interface SourceDossierBody {
  source_candidates: SourceRecord[];
}

interface SourceRegistryBody {
  source_registry: SourceRecord[];
  decision: {
    approved_ids: string[];
  };
}

interface CourseModelSourceBody {
  source_registry: SourceRecord[];
  modules: Array<{
    subtopics: Array<{
      id: string;
      approved_source_ids: string[];
    }>;
  }>;
}

interface BlueprintSourceBody {
  subtopic_plans: Array<{
    subtopic_id: string;
    asset_plan: Array<{
      id: string;
      selection_status: string;
      source_ids: string[];
    }>;
  }>;
}

interface SourceRepairLedger {
  checksum: string;
  entries: Array<{
    id: string;
    status: string;
    approved_source_route: {
      source_id: string;
      subtopic_ids: string[];
      asset_ids: string[];
    } | null;
    affected_asset_ids: string[];
    final_verifier_result?: {
      hard_blocker_total: number;
      review_status: string;
    } | null;
  }>;
}

interface ContentAssetRecord extends Record<string, unknown> {
  id: string;
  title: string;
}

interface ContentPackageBody {
  subtopics: Array<{
    subtopic_id: string;
    assets: ContentAssetRecord[];
  }>;
}

interface ContentReviewLedger {
  artifact: {
    body: {
      assets: Array<{
        asset_id: string;
        decision: string;
        asset_fingerprint: string;
      }>;
      summary: {
        pending: number;
        approved: number;
        ready_for_package: boolean;
      };
    };
  };
  checksum: string;
}

interface ContentRepairProjection {
  hard_blocker_total: number;
  partial_total: number;
  ready_for_package: boolean;
}

interface WorkspaceProjection {
  operator_status: string;
  active_job?: {
    job_id: string;
    status: string;
    stage: string;
  } | null;
  stages: Array<{
    slug: string;
    state: string;
    actions: Array<{ id: string; enabled: boolean }>;
  }>;
}

async function stage(
  request: APIRequestContext,
  courseId: string,
  stageSlug: string,
): Promise<StageProjection> {
  const response = await request.get(`/api/courses/${courseId}/stages/${stageSlug}`);
  expect(response.ok()).toBe(true);
  return response.json() as Promise<StageProjection>;
}

async function briefRound(
  request: APIRequestContext,
  courseId: string,
): Promise<BriefRound> {
  const response = await request.get(`/api/courses/${courseId}/brief/questions`);
  expect(response.ok()).toBe(true);
  return response.json() as Promise<BriefRound>;
}

async function briefArtifact(
  request: APIRequestContext,
  courseId: string,
): Promise<BriefArtifact> {
  const response = await request.get(`/api/courses/${courseId}/artifacts/brief`);
  expect(response.ok()).toBe(true);
  return response.json() as Promise<BriefArtifact>;
}

async function outcomesArtifact(
  request: APIRequestContext,
  courseId: string,
): Promise<OutcomesArtifact> {
  const response = await request.get(
    `/api/courses/${courseId}/artifacts/course_outcomes`,
  );
  expect(response.ok()).toBe(true);
  return response.json() as Promise<OutcomesArtifact>;
}

async function blueprintArtifact(
  request: APIRequestContext,
  courseId: string,
): Promise<BlueprintArtifact> {
  const response = await request.get(`/api/courses/${courseId}/artifacts/blueprint`);
  expect(response.ok()).toBe(true);
  return response.json() as Promise<BlueprintArtifact>;
}

async function lessonPlanArtifact(
  request: APIRequestContext,
  courseId: string,
): Promise<LessonPlanArtifact> {
  const response = await request.get(`/api/courses/${courseId}/artifacts/lesson_plan`);
  expect(response.ok()).toBe(true);
  return response.json() as Promise<LessonPlanArtifact>;
}

async function canonicalArtifact<TBody>(
  request: APIRequestContext,
  courseId: string,
  artifactType: string,
): Promise<CanonicalArtifact<TBody>> {
  const response = await request.get(
    `/api/courses/${courseId}/artifacts/${artifactType}`,
  );
  expect(response.ok()).toBe(true);
  return response.json() as Promise<CanonicalArtifact<TBody>>;
}

async function contentReview(
  request: APIRequestContext,
  courseId: string,
): Promise<ContentReviewLedger> {
  const response = await request.get(`/api/courses/${courseId}/content/reviews`);
  expect(response.ok()).toBe(true);
  return response.json() as Promise<ContentReviewLedger>;
}

async function contentRepairProjection(
  request: APIRequestContext,
  courseId: string,
): Promise<ContentRepairProjection> {
  const response = await request.get(`/api/courses/${courseId}/content/repairs`);
  expect(response.ok()).toBe(true);
  return response.json() as Promise<ContentRepairProjection>;
}

async function workspace(
  request: APIRequestContext,
  courseId: string,
): Promise<WorkspaceProjection> {
  const response = await request.get(`/api/courses/${courseId}/workspace`);
  expect(response.ok()).toBe(true);
  return response.json() as Promise<WorkspaceProjection>;
}

async function waitForStageState(
  request: APIRequestContext,
  courseId: string,
  stageSlug: string,
  expected: string,
  timeout = 30_000,
) {
  await expect.poll(
    async () => (await stage(request, courseId, stageSlug)).state,
    { timeout },
  ).toBe(expected);
}

async function runStageFromBrowser(
  page: Page,
  request: APIRequestContext,
  courseId: string,
  stageSlug: string,
  buttonName: string,
  expected: string,
  timeout = 30_000,
) {
  await page.goto(`/courses/${courseId}/${stageSlug}?mode=deterministic`);
  const button = page.getByRole("button", { name: buttonName });
  await expect(button).toBeEnabled();
  await button.click();
  await waitForStageState(request, courseId, stageSlug, expected, timeout);
}

async function approveStageFromBrowser(
  page: Page,
  request: APIRequestContext,
  courseId: string,
  stageSlug: string,
  buttonName: string,
) {
  const button = page.getByRole("button", { name: buttonName });
  await expect(button).toBeEnabled();
  await button.click();
  await waitForStageState(request, courseId, stageSlug, "approved");
}

async function reviewEveryVisibleContentAsset(
  page: Page,
  request: APIRequestContext,
  courseId: string,
) {
  const content = await canonicalArtifact<ContentPackageBody>(
    request,
    courseId,
    "content_package",
  );
  const assetIds = [...contentAssets(content.artifact.body).keys()];
  expect(assetIds.length).toBeGreaterThan(0);
  for (const assetId of assetIds) {
    await page.goto(
      `/courses/${courseId}/content?mode=deterministic&asset=${encodeURIComponent(assetId)}`,
    );
    const review = page.getByRole("button", { name: "Mark asset reviewed" });
    await expect(review, assetId).toBeEnabled();
    await review.click();
    await expect.poll(async () => {
      const ledger = await contentReview(request, courseId);
      return ledger.artifact.body.assets.find((record) => record.asset_id === assetId)
        ?.decision;
    }).toBe("approved");
  }
}

function contentAssets(body: ContentPackageBody): Map<string, ContentAssetRecord> {
  return new Map(
    body.subtopics.flatMap((subtopic) =>
      subtopic.assets.map((asset) => [asset.id, asset] as const),
    ),
  );
}

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value !== null && typeof value === "object") {
    const record = value as Record<string, unknown>;
    return `{${Object.keys(record).sort().map((key) =>
      `${JSON.stringify(key)}:${canonicalJson(record[key])}`,
    ).join(",")}}`;
  }
  return JSON.stringify(value) ?? "null";
}

function contentHash(value: unknown): string {
  return createHash("sha256").update(canonicalJson(value)).digest("hex");
}

function questionCard(page: Page, questionId: string) {
  return page.locator(`fieldset.question-card[data-question-id="${questionId}"]`);
}

async function expectBoundedDisplayedRound(page: Page, maximum = 5) {
  const cards = page.locator("fieldset.question-card");
  await expect(cards.first()).toBeVisible();
  expect(await cards.count()).toBeLessThanOrEqual(maximum);
  return cards;
}

async function acceptSuggestedDefault(page: Page, questionId: string) {
  const button = questionCard(page, questionId).getByRole("button", {
    name: /Accept suggested default for/i,
  });
  await expect(button).toContainText("Accept suggested default");
  await button.click();
  await expect(button).toHaveAttribute("aria-pressed", "true");
}

async function saveDisplayedRound(page: Page) {
  await page.getByRole("button", { name: "Save answers and continue" }).click();
}

test("completes bounded durable Guided Brief intake and protects approved editing", async ({
  page,
  request,
}, testInfo) => {
  test.setTimeout(180_000);
  const subject = testInfo.retry
    ? `Coffee making for home beginners retry ${testInfo.retry}`
    : "Coffee making for home beginners";

  const initialCourses = await request.get("/api/courses");
  expect(initialCourses.ok()).toBe(true);
  expect((await initialCourses.json()).courses).toEqual(
    expect.arrayContaining([
      expect.objectContaining({
        course_id: SEEDED_LIFECYCLE_COURSE_ID,
        read_only: false,
      }),
    ]),
  );

  await page.goto("/courses");
  await expect(page.getByRole("button", { name: "Settings" })).toBeDisabled();
  await page.goto("/courses/new");
  await expect(
    page.getByRole("heading", { name: "Give the agent a clear starting point." }),
  ).toBeVisible();

  await page.getByLabel(/What should this course teach/).fill(subject);
  await page.getByRole("radio", { name: /Deterministic preview/ }).check();
  await page.getByRole("button", { name: /Create Brief/ }).click();

  await expect(page).toHaveURL(/\/courses\/[^/]+\/brief\?mode=deterministic$/);
  const pathParts = new URL(page.url()).pathname.split("/").filter(Boolean);
  const courseId = pathParts[1];
  expect(courseId).toBeTruthy();
  expect(courseId).not.toBe(SEEDED_LIFECYCLE_COURSE_ID);
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Confirm the course direction" })).toBeVisible();

  await expect.poll(async () => (await stage(request, courseId, "brief")).state).toBe(
    "needs_input",
  );
  expect((await stage(request, courseId, "outcomes")).state).toBe("locked");

  const initialRound = await briefRound(request, courseId);
  expect(initialRound.round_kind).toBe("mandatory");
  expect(initialRound.questions).toHaveLength(5);
  expect(initialRound.questions.map((question) => question.id)).not.toContain(
    "brief_live_teaching_constraints",
  );
  expect(await page.locator("fieldset.question-card").count()).toBe(
    initialRound.questions.length,
  );
  await expectBoundedDisplayedRound(page);
  await expect(questionCard(page, "brief_audience")).toContainText("Why this matters:");

  const invalidChoice = initialRound.questions.find(
    (question) => question.answer_type === "single_choice" && question.options.length,
  );
  expect(invalidChoice).toBeTruthy();
  const invalidAnswer = await request.put(`/api/courses/${courseId}/brief/answers`, {
    data: {
      expected_checksum: initialRound.checksum,
      answers: [{ question_id: invalidChoice?.id, value: "not-a-valid-option" }],
    },
  });
  expect(invalidAnswer.ok()).toBe(false);
  expect(invalidAnswer.status()).toBeGreaterThanOrEqual(400);
  expect(invalidAnswer.status()).toBeLessThan(500);
  const roundAfterInvalidAnswer = await briefRound(request, courseId);
  expect(roundAfterInvalidAnswer.checksum).toBe(initialRound.checksum);
  expect(roundAfterInvalidAnswer.questions.map((question) => question.id)).toContain(
    invalidChoice?.id,
  );

  const unresolvedBrief = await stage(request, courseId, "brief");
  const unresolvedApproval = await request.post(
    `/api/courses/${courseId}/stages/brief/approve`,
    { data: { expected_checksum: unresolvedBrief.checksum } },
  );
  expect(unresolvedApproval.ok()).toBe(false);

  const lockedOutcomes = await stage(request, courseId, "outcomes");
  const prematureOutcomesRun = await request.post(
    `/api/courses/${courseId}/stages/outcomes/run`,
    {
      data: {
        mode: "deterministic",
        ...(lockedOutcomes.checksum
          ? { expected_checksum: lockedOutcomes.checksum }
          : {}),
      },
    },
  );
  expect(prematureOutcomesRun.ok()).toBe(false);
  expect((await stage(request, courseId, "outcomes")).state).toBe("locked");

  await questionCard(page, "brief_audience")
    .getByLabel("Who is this course for?")
    .fill("General");
  await acceptSuggestedDefault(page, "brief_prior_knowledge");
  await questionCard(page, "brief_purpose")
    .getByLabel("What should learners be able to do after the course?")
    .fill("Consistently brew balanced coffee and diagnose common taste problems.");
  await acceptSuggestedDefault(page, "brief_level");
  await acceptSuggestedDefault(page, "brief_duration");
  await saveDisplayedRound(page);

  await expect(questionCard(page, "brief_modality")).toBeVisible();
  const afterFirstRound = await briefArtifact(request, courseId);
  expect(afterFirstRound.artifact.body.audience).toBe("General");
  expect(afterFirstRound.artifact.body.purpose).toBe(
    "Consistently brew balanced coffee and diagnose common taste problems.",
  );
  expect(afterFirstRound.artifact.body.intake_state.explicit_fields).toEqual(
    expect.arrayContaining(["audience", "purpose"]),
  );
  expect(afterFirstRound.artifact.body.intake_state.accepted_default_fields).toEqual(
    expect.arrayContaining(["prior_knowledge", "level", "duration"]),
  );
  expect(afterFirstRound.artifact.body.intake_state.answered_question_ids).toEqual(
    expect.arrayContaining([
      "brief_audience",
      "brief_prior_knowledge",
      "brief_purpose",
      "brief_level",
      "brief_duration",
    ]),
  );

  await page.reload();
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await expect(questionCard(page, "brief_audience")).toHaveCount(0);
  await expect(questionCard(page, "brief_modality")).toBeVisible();
  const secondRound = await briefRound(request, courseId);
  expect(secondRound.round_kind).toBe("mandatory");
  expect(secondRound.questions.map((question) => question.id)).not.toContain(
    "brief_live_teaching_constraints",
  );
  await expectBoundedDisplayedRound(page);

  const concurrentSecondRoundEdit = await request.patch(
    `/api/courses/${courseId}/brief`,
    {
      data: {
        expected_checksum: secondRound.checksum,
        updates: { assessment_expectations: "One practical brewing check." },
      },
    },
  );
  expect(concurrentSecondRoundEdit.ok()).toBe(true);
  await questionCard(page, "brief_modality")
    .getByRole("radio", { name: /blended/i })
    .check();
  await acceptSuggestedDefault(page, "brief_language");
  await saveDisplayedRound(page);

  await expect(page.getByText(/Answers were not saved/)).toBeVisible();
  await expect(page.getByText(/changed in another session/i)).toBeVisible();
  await expect.poll(async () => (await briefRound(request, courseId)).checksum).not.toBe(
    secondRound.checksum,
  );
  const afterStaleAnswer = await briefArtifact(request, courseId);
  expect(afterStaleAnswer.artifact.body.modality).toBe("self_paced");
  expect(
    afterStaleAnswer.artifact.body.intake_state.accepted_default_fields,
  ).not.toContain("language");

  await questionCard(page, "brief_modality")
    .getByRole("radio", { name: /blended/i })
    .check();
  await acceptSuggestedDefault(page, "brief_language");
  await saveDisplayedRound(page);

  await expect(questionCard(page, "brief_live_teaching_constraints")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Resolve the remaining Brief gaps" }),
  ).toBeVisible();
  const clarificationRound = await briefRound(request, courseId);
  expect(clarificationRound.round_kind).toBe("clarification");
  expect(clarificationRound.questions.length).toBeGreaterThan(0);
  expect(clarificationRound.questions.length).toBeLessThanOrEqual(3);
  const audienceClarification = clarificationRound.questions.find(
    (question) => question.field === "audience",
  );
  expect(audienceClarification).toBeTruthy();
  expect(clarificationRound.questions.map((question) => question.id)).toContain(
    "brief_live_teaching_constraints",
  );
  await expectBoundedDisplayedRound(page, 3);
  await expect(
    questionCard(page, "brief_live_teaching_constraints").getByRole("button", {
      name: "Skip Are there any live-teaching constraints?",
    }),
  ).toBeVisible();
  await questionCard(page, "brief_live_teaching_constraints")
    .getByRole("textbox", { name: "Are there any live-teaching constraints?" })
    .fill("Use two instructor-led practice blocks of no more than 45 minutes each.");
  await questionCard(page, audienceClarification?.id ?? "missing-audience-clarification")
    .getByRole("textbox", {
      name: audienceClarification?.prompt ?? "missing audience clarification",
    })
    .fill("Adults making coffee at home with little technical knowledge.");
  await saveDisplayedRound(page);

  await expect.poll(async () => (await stage(request, courseId, "brief")).state).toBe(
    "awaiting_review",
  );
  const completeRound = await briefRound(request, courseId);
  expect(completeRound.round_kind).toBe("complete");
  expect(completeRound.questions).toEqual([]);

  await page.reload();
  await expect(page.getByRole("heading", { name: "Course Brief" })).toBeVisible();
  await expect(page.getByText("Adults making coffee at home with little technical knowledge.")).toBeVisible();
  await expect(page.getByText("Blended", { exact: true })).toBeVisible();
  await expect(page.locator("fieldset.question-card")).toHaveCount(0);

  const completedBrief = await briefArtifact(request, courseId);
  const preservedAnsweredQuestionIds = [
    ...completedBrief.artifact.body.intake_state.answered_question_ids,
  ].sort();
  const preservedAcceptedDefaults = [
    ...completedBrief.artifact.body.intake_state.accepted_default_fields,
  ].sort();
  expect(completedBrief.artifact.body.intake_state.unresolved_required_fields).toEqual([]);
  expect(preservedAcceptedDefaults).toEqual(
    expect.arrayContaining(["prior_knowledge", "level", "duration", "language"]),
  );

  await page.getByRole("button", { name: "Approve Brief" }).click();
  await expect.poll(async () => (await stage(request, courseId, "brief")).state).toBe(
    "approved",
  );
  expect((await stage(request, courseId, "outcomes")).state).toBe("ready");

  await page.goto(`/courses/${courseId}/brief?mode=deterministic`);
  await expect(page.getByRole("button", { name: "Reopen Brief" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Adjust must-have coverage in Course Brief" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", {
      name: "Adjust additional requirements and materials in Course Brief",
    }),
  ).toHaveCount(0);

  const approvedBrief = await briefArtifact(request, courseId);
  const editWithoutReopen = await request.patch(`/api/courses/${courseId}/brief`, {
    data: {
      expected_checksum: approvedBrief.checksum,
      updates: { must_have_topics: ["troubleshooting sour and bitter coffee"] },
    },
  });
  expect(editWithoutReopen.ok()).toBe(false);
  expect(editWithoutReopen.status()).toBe(409);

  await page.getByRole("button", { name: "Reopen Brief" }).click();
  await expect(page.getByRole("heading", { name: "Reopen Brief" })).toBeVisible();
  await expect(
    page.getByText(/server computed this impact from the current pipeline dependency graph/i),
  ).toBeVisible();
  await page.getByRole("checkbox", { name: /I understand/ }).check();
  await page.getByRole("button", { name: "Confirm and reopen" }).click();

  await expect.poll(async () => (await stage(request, courseId, "brief")).state).toBe(
    "awaiting_review",
  );
  await page.getByRole("button", {
    name: "Adjust additional requirements and materials in Course Brief",
  }).click();
  const beforeConcurrentDirectEdit = await briefArtifact(request, courseId);
  const concurrentDirectEdit = await request.patch(`/api/courses/${courseId}/brief`, {
    data: {
      expected_checksum: beforeConcurrentDirectEdit.checksum,
      updates: { freshness_requirement: "Review the course annually." },
    },
  });
  expect(concurrentDirectEdit.ok()).toBe(true);
  const liveTeachingConstraints = page.getByLabel("Live-teaching constraints");
  await liveTeachingConstraints.fill(
    "Use three instructor-led practice blocks of no more than 30 minutes each.",
  );
  await page.getByRole("button", { name: "Save section" }).click();

  await expect(page.locator(".brief-edit-dialog")).toHaveCount(0);
  await expect(page.getByText(/latest values are loaded/i)).toBeVisible();
  const afterStaleDirectEdit = await briefArtifact(request, courseId);
  expect(afterStaleDirectEdit.artifact.body.live_teaching_constraints).toBe(
    "Use two instructor-led practice blocks of no more than 45 minutes each.",
  );
  expect(afterStaleDirectEdit.artifact.body.freshness_requirement).toBe(
    "Review the course annually.",
  );

  await page.getByRole("button", {
    name: "Adjust additional requirements and materials in Course Brief",
  }).click();
  await page.getByLabel("Live-teaching constraints").fill(
    "Use three instructor-led practice blocks of no more than 30 minutes each.",
  );
  await page.getByRole("button", { name: "Save section" }).click();

  await expect.poll(async () => {
    const current = await briefArtifact(request, courseId);
    return current.artifact.body.live_teaching_constraints;
  }).toBe("Use three instructor-led practice blocks of no more than 30 minutes each.");
  const editedBrief = await briefArtifact(request, courseId);
  expect(editedBrief.artifact.body.audience).toBe(
    "Adults making coffee at home with little technical knowledge.",
  );
  expect(editedBrief.artifact.body.purpose).toBe(
    "Consistently brew balanced coffee and diagnose common taste problems.",
  );
  const editedAnsweredQuestionIds = [
    ...editedBrief.artifact.body.intake_state.answered_question_ids,
  ].sort();
  expect(editedAnsweredQuestionIds).toEqual(
    [...preservedAnsweredQuestionIds, "brief_freshness_requirement"].sort(),
  );
  expect(
    [...editedBrief.artifact.body.intake_state.accepted_default_fields].sort(),
  ).toEqual(preservedAcceptedDefaults);

  await page.getByRole("button", { name: "Approve Brief" }).click();
  await expect.poll(async () => (await stage(request, courseId, "brief")).state).toBe(
    "approved",
  );

  await page.goto(`/courses/${courseId}/outcomes?mode=deterministic`);
  await expect(page.getByRole("button", { name: "Run Outcomes" })).toBeVisible();
  await page.getByRole("button", { name: "Run Outcomes" }).click();
  await expect.poll(
    async () => (await stage(request, courseId, "outcomes")).state,
    { timeout: 30_000 },
  ).toBe("awaiting_review");
  await expect(page.getByRole("heading", { name: "Course Outcomes" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Edit Outcomes" })).toBeVisible();

  await page.getByRole("button", { name: "Edit Outcomes" }).click();
  await page
    .getByLabel("Outcome statement for co1")
    .fill("My first unsaved Outcome statement.");
  const navigationDialog = page.waitForEvent("dialog");
  const navigationClick = page.getByRole("link", { name: /Research & Sources/ }).click();
  const dialog = await navigationDialog;
  expect(dialog.message()).toContain("unsaved Outcomes changes");
  await dialog.dismiss();
  await navigationClick;
  await expect(page).toHaveURL(new RegExp(`/courses/${courseId}/outcomes\\?mode=deterministic$`));
  await expect(page.getByLabel("Outcome statement for co1")).toHaveValue(
    "My first unsaved Outcome statement.",
  );

  const beforeUseLatest = await outcomesArtifact(request, courseId);
  const useLatestIds = beforeUseLatest.artifact.body.outcomes.map((outcome) => outcome.id);
  const concurrentUseLatest = await request.put(
    `/api/courses/${courseId}/outcomes/decision`,
    {
      data: {
        expected_checksum: beforeUseLatest.checksum,
        selected_ids: useLatestIds,
        edits: {
          co2: {
            evidence: "The server saved this concurrent evidence description.",
          },
        },
        additions: [],
        priority_order: useLatestIds,
      },
    },
  );
  expect(concurrentUseLatest.ok()).toBe(true);
  await page.getByRole("button", { name: "Save Outcomes draft" }).click();
  await expect(page.getByText("These Outcomes changed elsewhere.")).toBeVisible();
  await page.getByRole("button", { name: "Use latest server version" }).click();
  await expect(page.getByLabel("Outcome statement for co1")).not.toHaveValue(
    "My first unsaved Outcome statement.",
  );
  await expect(page.getByLabel("Evidence of learning for co2")).toHaveValue(
    "The server saved this concurrent evidence description.",
  );
  await page.getByRole("button", { name: "Cancel changes" }).click();

  await page.getByRole("button", { name: "Edit Outcomes" }).click();
  await page
    .getByLabel("Evidence of learning for co1")
    .fill("My nonconflicting local evidence description.");
  const beforeKeepLocal = await outcomesArtifact(request, courseId);
  const keepLocalIds = beforeKeepLocal.artifact.body.outcomes.map((outcome) => outcome.id);
  const concurrentKeepLocal = await request.put(
    `/api/courses/${courseId}/outcomes/decision`,
    {
      data: {
        expected_checksum: beforeKeepLocal.checksum,
        selected_ids: keepLocalIds,
        edits: { co3: { priority: "supporting" } },
        additions: [],
        priority_order: keepLocalIds,
      },
    },
  );
  expect(concurrentKeepLocal.ok()).toBe(true);
  await page.getByRole("button", { name: "Save Outcomes draft" }).click();
  await expect(page.getByText("These Outcomes changed elsewhere.")).toBeVisible();
  await page.getByRole("button", { name: "Keep my edits against latest" }).click();
  await expect(page.getByLabel("Evidence of learning for co1")).toHaveValue(
    "My nonconflicting local evidence description.",
  );
  await expect(page.getByLabel("Priority for co3")).toHaveValue("supporting");
  await page.getByRole("button", { name: "Save Outcomes draft" }).click();
  await expect.poll(async () => {
    const artifact = await outcomesArtifact(request, courseId);
    return artifact.artifact.body.outcomes.find((outcome) => outcome.id === "co1")?.evidence;
  }).toBe("My nonconflicting local evidence description.");

  await page.getByRole("button", { name: "Edit Outcomes" }).click();
  await page
    .getByLabel("Outcome statement for co1")
    .fill("Explain core coffee concepts and use them to choose a sound starting recipe.");
  await page
    .getByLabel("Evidence of learning for co1")
    .fill("Learner explains the key concepts and justifies a starting recipe.");

  await page.getByRole("button", { name: "+ Add Outcome" }).click();
  await page
    .getByLabel("Outcome statement for new Outcome 5")
    .fill("Create a repeatable brew log for controlled improvement.");
  await page
    .getByLabel("Evidence of learning for new Outcome 5")
    .fill("Learner produces a brew log with one justified variable change.");
  await page.getByLabel("Cognitive level for new Outcome 5").selectOption("create");
  await page.getByLabel("Priority for new Outcome 5").selectOption("optional");
  await page.getByRole("button", { name: "Move new Outcome 5 up" }).click();

  await page.getByRole("button", { name: "Remove co2" }).click();
  const removalDialog = page.getByRole("dialog", { name: "Remove this Outcome?" });
  await expect(removalDialog).toContainText("co2");
  await removalDialog.getByRole("button", { name: "Remove Outcome" }).click();
  await page.getByRole("button", { name: "Save Outcomes draft" }).click();

  await expect.poll(
    async () => {
      const artifact = await outcomesArtifact(request, courseId);
      return artifact.artifact.body.outcomes.map((outcome) => outcome.id);
    },
    { timeout: 30_000 },
  ).toEqual(["co1", "co3", "co5", "co4"]);
  expect((await stage(request, courseId, "outcomes")).state).toBe("awaiting_review");

  const savedOutcomes = (await outcomesArtifact(request, courseId)).artifact.body.outcomes;
  expect(savedOutcomes).toEqual([
    expect.objectContaining({
      id: "co1",
      statement:
        "Explain core coffee concepts and use them to choose a sound starting recipe.",
      evidence: "Learner explains the key concepts and justifies a starting recipe.",
    }),
    expect.objectContaining({ id: "co3" }),
    expect.objectContaining({
      id: "co5",
      statement: "Create a repeatable brew log for controlled improvement.",
      evidence: "Learner produces a brew log with one justified variable change.",
      cognitive_level: "create",
      priority: "optional",
    }),
    expect.objectContaining({ id: "co4" }),
  ]);

  await page.reload();
  await expect(
    page.getByRole("heading", {
      name: "Explain core coffee concepts and use them to choose a sound starting recipe.",
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Learner explains the key concepts and justifies a starting recipe."),
  ).toBeVisible();
  await expect(page.locator(".outcome-list > .outcome-card code")).toHaveText([
    "co1",
    "co3",
    "co5",
    "co4",
  ]);
  await expect(page.getByText("Create", { exact: true })).toBeVisible();
  await expect(page.getByText("optional", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Approve Outcomes" }).click();
  await expect.poll(
    async () => (await stage(request, courseId, "outcomes")).state,
  ).toBe("approved");
  await expect.poll(
    async () => (await stage(request, courseId, "research")).state,
  ).toBe("ready");

  await page.goto(`/courses/${courseId}/research?mode=deterministic`);
  await expect(page.getByRole("heading", { name: "Research & Sources" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run Research" })).toBeVisible();

  // NC-1101 continues the same isolated course through every remaining Scenario A
  // checkpoint instead of treating separately seeded editor tests as an end-to-end run.
  await page.getByRole("button", { name: "Run Research" }).click();
  await waitForStageState(request, courseId, "research", "awaiting_review");
  await expect(page.getByRole("button", { name: "+ Add source" })).toBeEnabled();
  await page.getByRole("button", { name: "+ Add source" }).click();
  await page.getByLabel("Source URL").fill("https://example.edu/nc110-known-coffee-source");
  await page.getByLabel(/Title/).fill("NC-110 known coffee candidate");
  await page.getByLabel(/Publisher/).fill("Example University");
  await page.getByRole("button", { name: "Add proposed source" }).click();
  await expect(
    page.getByRole("heading", { name: "NC-110 known coffee candidate" }),
  ).toBeVisible();

  const selectableSources = page.getByRole("button", { name: "Select" });
  expect(await selectableSources.count()).toBeGreaterThanOrEqual(2);
  await selectableSources.nth(0).click();
  await selectableSources.nth(1).click();
  await page.getByRole("button", { name: /Save 2 selected sources/ }).click();
  await expect(page.getByText("Ready for stage approval.")).toBeVisible();
  await approveStageFromBrowser(
    page,
    request,
    courseId,
    "research",
    "Approve Research",
  );
  expect((await stage(request, courseId, "course-model")).state).toBe("ready");

  await runStageFromBrowser(
    page,
    request,
    courseId,
    "course-model",
    "Run Course Model",
    "awaiting_review",
  );
  await page.locator(".decision-bar").getByRole("button", { name: "Edit Course Model" }).click();
  const firstSubtopicTitle = page.getByLabel(/^Subtopic title for /).first();
  const originalSubtopicTitle = await firstSubtopicTitle.inputValue();
  await firstSubtopicTitle.fill(`${originalSubtopicTitle} for Home Brewing`);
  await page.getByRole("button", { name: "Preview impact" }).click();
  await expect(page.getByText("Backend validation passed")).toBeVisible();
  await page.getByRole("checkbox", { name: /reviewed the detailed structural diff/i }).check();
  await page.getByRole("button", { name: "Save Course Model draft" }).click();
  await expect(
    page.getByRole("heading", { name: `${originalSubtopicTitle} for Home Brewing` }),
  ).toBeVisible();
  await approveStageFromBrowser(
    page,
    request,
    courseId,
    "course-model",
    "Approve Course Model",
  );

  await runStageFromBrowser(
    page,
    request,
    courseId,
    "blueprint",
    "Run Blueprint",
    "awaiting_review",
  );
  await page.locator(".decision-bar").getByRole("button", { name: "Edit Blueprint" }).click();
  const firstAssetGroup = page.locator('[aria-label^="Assets for "]').first();
  const activityToggle = firstAssetGroup.getByRole("button", { name: /Activity/ });
  await activityToggle.click();
  await page.getByLabel(/learning time/).first().fill("25");
  await page.getByRole("checkbox", { name: /reviewed the exact asset additions/i }).check();
  await page.getByRole("button", { name: "Save Blueprint draft" }).click();
  await approveStageFromBrowser(
    page,
    request,
    courseId,
    "blueprint",
    "Approve Blueprint",
  );

  await runStageFromBrowser(
    page,
    request,
    courseId,
    "content",
    "Run Student Content",
    "awaiting_review",
    60_000,
  );
  await expect(page.getByText("No blocking verification findings")).toBeVisible();
  await reviewEveryVisibleContentAsset(page, request, courseId);
  await approveStageFromBrowser(
    page,
    request,
    courseId,
    "content",
    "Approve Student Content",
  );

  await runStageFromBrowser(
    page,
    request,
    courseId,
    "lesson-plan",
    "Run Lesson Plan",
    "awaiting_review",
  );
  await page.locator(".decision-bar").getByRole("button", { name: "Edit Lesson Plan" }).click();
  await page.getByLabel("Maximum session hours").fill("0.5");
  await page.getByLabel(/^Delivery mode for /).first().selectOption("self_study");
  await page.getByRole("checkbox", { name: /reviewed the changed constraints/i }).check();
  await page.getByRole("button", { name: "Save Lesson Plan draft" }).click();
  await approveStageFromBrowser(
    page,
    request,
    courseId,
    "lesson-plan",
    "Approve Lesson Plan",
  );

  await runStageFromBrowser(
    page,
    request,
    courseId,
    "package",
    "Run Package",
    "awaiting_review",
  );
  const packagePreview = page.getByRole("region", { name: "Preview of Course index" });
  await expect(packagePreview.getByRole("heading").first()).toBeVisible();
  const rawPackage = await request.get(`/api/courses/${courseId}/outputs/README.md`);
  expect(rawPackage.ok()).toBe(true);
  expect(await rawPackage.text()).toContain(`# ${await packagePreview.getByRole("heading").first().innerText()}`);
  await approveStageFromBrowser(
    page,
    request,
    courseId,
    "package",
    "Approve Package",
  );
  await expect.poll(async () => (await workspace(request, courseId)).operator_status).toBe(
    "complete",
  );
});

test("Scenario B reopens, changes, and reruns downstream stages to completion", async ({ page, request }) => {
  test.setTimeout(180_000);
  await page.goto(
    `/courses/${REOPEN_RERUN_COURSE_ID}/course-model?mode=deterministic`,
  );
  await expect(page.getByRole("heading", { name: "Course Model" })).toBeVisible();
  await expect(page.getByText("Grind Size", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Edit Course Model" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Add module" })).toHaveCount(0);
  const activityTrigger = page.getByRole("button", { name: "Open activity" });
  await activityTrigger.click();
  await expect(page.getByRole("heading", { name: "Diagnostics by stage" })).toBeVisible();
  await expect(page.getByText("No live model calls have been recorded for this course.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Close activity drawer" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Activity" })).toHaveCount(0);
  await expect(activityTrigger).toBeFocused();

  const reopenCourseModel = page.getByRole("button", { name: "Reopen Course Model" });
  await expect(reopenCourseModel).toBeVisible();
  await reopenCourseModel.click();
  await expect(page.getByRole("heading", { name: "Reopen Course Model" })).toBeVisible();
  await expect(page.getByText(/downstream artifacts made stale/i)).toBeVisible();
  await page.getByRole("checkbox", { name: /I understand/ }).check();
  await page.getByRole("button", { name: "Confirm and reopen" }).click();

  await expect.poll(async () => {
    return (await stage(request, REOPEN_RERUN_COURSE_ID, "course-model")).state;
  }).toBe("awaiting_review");
  await expect.poll(async () => {
    return (await stage(request, REOPEN_RERUN_COURSE_ID, "blueprint")).state;
  }).toBe("stale");
  await expect(page.getByText("Grind Size", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Edit Course Model" }).first()).toBeVisible();

  await page.locator(".decision-bar").getByRole("button", { name: "Edit Course Model" }).click();
  await page.getByLabel("Subtopic title for m1_s1").fill("Grind Size After Reopen");
  await page.getByRole("button", { name: "Preview impact" }).click();
  await expect(page.getByText("Backend validation passed")).toBeVisible();
  await page.getByRole("checkbox", { name: /reviewed the detailed structural diff/i }).check();
  await page.getByRole("button", { name: "Save Course Model draft" }).click();
  await expect(page.getByRole("heading", { name: "Grind Size After Reopen" })).toBeVisible();
  await approveStageFromBrowser(
    page,
    request,
    REOPEN_RERUN_COURSE_ID,
    "course-model",
    "Approve Course Model",
  );

  await runStageFromBrowser(
    page,
    request,
    REOPEN_RERUN_COURSE_ID,
    "blueprint",
    "Run Blueprint",
    "awaiting_review",
  );
  await approveStageFromBrowser(
    page,
    request,
    REOPEN_RERUN_COURSE_ID,
    "blueprint",
    "Approve Blueprint",
  );
  await runStageFromBrowser(
    page,
    request,
    REOPEN_RERUN_COURSE_ID,
    "content",
    "Run Student Content",
    "awaiting_review",
    60_000,
  );
  await reviewEveryVisibleContentAsset(page, request, REOPEN_RERUN_COURSE_ID);
  await approveStageFromBrowser(
    page,
    request,
    REOPEN_RERUN_COURSE_ID,
    "content",
    "Approve Student Content",
  );
  await runStageFromBrowser(
    page,
    request,
    REOPEN_RERUN_COURSE_ID,
    "lesson-plan",
    "Run Lesson Plan",
    "awaiting_review",
  );
  await approveStageFromBrowser(
    page,
    request,
    REOPEN_RERUN_COURSE_ID,
    "lesson-plan",
    "Approve Lesson Plan",
  );
  await runStageFromBrowser(
    page,
    request,
    REOPEN_RERUN_COURSE_ID,
    "package",
    "Run Package",
    "awaiting_review",
  );
  await approveStageFromBrowser(
    page,
    request,
    REOPEN_RERUN_COURSE_ID,
    "package",
    "Approve Package",
  );
  await expect.poll(
    async () => (await workspace(request, REOPEN_RERUN_COURSE_ID)).operator_status,
  ).toBe("complete");
});

test("Scenario C1 fails safely and retries through the browser", async ({ page, request }) => {
  test.setTimeout(60_000);
  await page.goto(
    `/courses/${FAILURE_RECOVERY_COURSE_ID}/content?mode=deterministic`,
  );
  expect((await stage(request, FAILURE_RECOVERY_COURSE_ID, "content")).state).toBe("ready");
  const contentBeforeFailure = await request.get(
    `/api/courses/${FAILURE_RECOVERY_COURSE_ID}/artifacts/content_package`,
  );
  expect(contentBeforeFailure.status()).toBe(404);
  await page.getByRole("button", { name: "Run Student Content" }).click();
  await waitForStageState(
    request,
    FAILURE_RECOVERY_COURSE_ID,
    "content",
    "failed",
  );
  const contentAfterFailure = await request.get(
    `/api/courses/${FAILURE_RECOVERY_COURSE_ID}/artifacts/content_package`,
  );
  expect(contentAfterFailure.status()).toBe(404);
  await expect(page.getByText("Last run failed safely")).toBeVisible();
  const retry = page.getByRole("button", { name: "Retry Student Content" });
  await expect(retry).toBeEnabled();

  await page.getByRole("button", { name: "Open activity" }).click();
  await expect(
    page.getByRole("dialog", { name: "Activity" }).getByText(
      "controlled NC-110 deterministic generation failure",
      { exact: true },
    ).first(),
  ).toBeVisible();
  await expect(
    page.getByRole("dialog", { name: "Activity" }).getByText("Job started", {
      exact: true,
    }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await retry.click();
  await waitForStageState(
    request,
    FAILURE_RECOVERY_COURSE_ID,
    "content",
    "awaiting_review",
    60_000,
  );
  await expect(page.getByText("No blocking verification findings")).toBeVisible();
});

test("Scenario C2 recovers an interrupted API job and retries it visibly", async ({
  page,
  request,
}) => {
  test.setTimeout(60_000);
  await page.goto(
    `/courses/${RESTART_RECOVERY_COURSE_ID}/outcomes?mode=deterministic`,
  );
  expect((await stage(request, RESTART_RECOVERY_COURSE_ID, "outcomes")).state).toBe("ready");
  await page.getByRole("button", { name: "Run Outcomes" }).click();
  await expect.poll(async () => {
    const current = await workspace(request, RESTART_RECOVERY_COURSE_ID);
    return current.active_job?.status;
  }).toBe("running");

  const termination = await request.post("/__acceptance__/terminate-api");
  expect(termination.ok()).toBe(true);
  await expect.poll(async () => {
    try {
      return (await request.get("/api/health")).ok();
    } catch {
      return false;
    }
  }, { timeout: 10_000 }).toBe(false);
  await expect.poll(async () => {
    try {
      return (await request.get("/api/health")).ok();
    } catch {
      return false;
    }
  }, { timeout: 30_000 }).toBe(true);

  await page.goto(
    `/courses/${RESTART_RECOVERY_COURSE_ID}/outcomes?mode=deterministic`,
  );
  await waitForStageState(
    request,
    RESTART_RECOVERY_COURSE_ID,
    "outcomes",
    "failed",
  );
  await expect(page.getByText("Last run failed safely")).toBeVisible();
  await page.getByRole("button", { name: "Open activity" }).click();
  await expect(
    page.getByLabel("Persisted runtime events").getByText(
      /API process stopped before this job completed/i,
    ),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  const retry = page.getByRole("button", { name: "Retry Outcomes" });
  await expect(retry).toBeEnabled();
  await retry.click();
  await waitForStageState(
    request,
    RESTART_RECOVERY_COURSE_ID,
    "outcomes",
    "awaiting_review",
  );
  await expect(page.getByRole("heading", { name: "Course Outcomes" })).toBeVisible();
});

test("Scenarios C3 and C4 rediscover active work and reject a competing mutation", async ({
  page,
  request,
}) => {
  test.setTimeout(60_000);
  await page.goto(
    `/courses/${ACTIVE_REFRESH_COURSE_ID}/content?mode=deterministic`,
  );
  await page.getByRole("button", { name: "Run Student Content" }).click();
  await expect.poll(async () => {
    const current = await workspace(request, ACTIVE_REFRESH_COURSE_ID);
    return current.active_job?.stage;
  }).toBe("content");
  await expect(
    page.getByRole("progressbar", { name: "Student Content run progress" }),
  ).toBeVisible();

  const competingRun = await request.post(
    `/api/courses/${ACTIVE_REFRESH_COURSE_ID}/stages/content/run`,
    { data: { mode: "deterministic" } },
  );
  expect(competingRun.ok()).toBe(false);
  expect(competingRun.status()).toBe(409);

  await page.reload();
  await expect(
    page.getByRole("progressbar", { name: "Student Content run progress" }),
  ).toBeVisible();
  await page.goto(
    `/courses/${ACTIVE_REFRESH_COURSE_ID}/blueprint?mode=deterministic`,
  );
  const afterNavigation = await workspace(request, ACTIVE_REFRESH_COURSE_ID);
  expect(
    afterNavigation.stages.find((candidate) => candidate.slug === "content")?.state,
  ).toMatch(/running|awaiting_review/);
  await page.goto(
    `/courses/${ACTIVE_REFRESH_COURSE_ID}/content?mode=deterministic`,
  );
  await waitForStageState(
    request,
    ACTIVE_REFRESH_COURSE_ID,
    "content",
    "awaiting_review",
    60_000,
  );
  expect((await workspace(request, ACTIVE_REFRESH_COURSE_ID)).active_job).toBeFalsy();
});

test("Scenario D rejects source leakage, blocker approval, read-only writes, and traversal", async ({
  page,
  request,
}) => {
  const modelBefore = await canonicalArtifact<CourseModelSourceBody>(
    request,
    NEGATIVE_SOURCE_COURSE_ID,
    "course_model",
  );
  const rejectedSourcePreview = await request.post(
    `/api/courses/${NEGATIVE_SOURCE_COURSE_ID}/course-model/decision/preview`,
    {
      data: {
        expected_checksum: modelBefore.checksum,
        operations: [
          {
            op: "assign_sources",
            target_type: "subtopic",
            target_id: "m1_s1",
            source_ids: ["coffee_g3"],
          },
        ],
      },
    },
  );
  expect(rejectedSourcePreview.ok()).toBe(false);
  expect(rejectedSourcePreview.status()).toBe(400);
  expect(
    await canonicalArtifact<CourseModelSourceBody>(
      request,
      NEGATIVE_SOURCE_COURSE_ID,
      "course_model",
    ),
  ).toEqual(modelBefore);

  await page.goto(
    `/courses/${CONTENT_BLOCKER_TRUTH_COURSE_ID}/content?mode=deterministic`,
  );
  await expect(page.getByRole("button", { name: "Approve Student Content" })).toBeDisabled();
  const blockedContent = await stage(
    request,
    CONTENT_BLOCKER_TRUTH_COURSE_ID,
    "content",
  );
  const blockedApproval = await request.post(
    `/api/courses/${CONTENT_BLOCKER_TRUTH_COURSE_ID}/stages/content/approve`,
    { data: { expected_checksum: blockedContent.checksum } },
  );
  expect(blockedApproval.ok()).toBe(false);
  expect((await stage(request, CONTENT_BLOCKER_TRUTH_COURSE_ID, "content")).state)
    .toBe("requires_attention");

  await page.goto(
    `/courses/${READ_ONLY_ACCEPTANCE_COURSE_ID}/course-model?mode=deterministic`,
  );
  await expect(page.getByText("Archived snapshot")).toBeVisible();
  await expect(page.getByRole("button", { name: /Reopen Course Model/ })).toHaveCount(0);
  const readOnlyWrite = await request.post(
    `/api/courses/${READ_ONLY_ACCEPTANCE_COURSE_ID}/stages/course-model/run`,
    { data: { mode: "deterministic" } },
  );
  expect(readOnlyWrite.status()).toBe(403);

  const traversal = await request.get(
    `/api/courses/${PACKAGE_PREVIEW_COURSE_ID}/outputs/%2e%2e%2F%2e%2e%2FAGENTS.md`,
  );
  expect(traversal.ok()).toBe(false);
  expect(traversal.status()).toBeGreaterThanOrEqual(400);
  expect(traversal.status()).toBeLessThan(500);
});

test("renders canonical Package Markdown and routes its named blocker", async ({ page }) => {
  await page.goto(
    `/courses/${PACKAGE_PREVIEW_COURSE_ID}/package?mode=deterministic`,
  );
  await expect(page.getByRole("heading", { name: "Course Package" })).toBeVisible();
  const preview = page.getByRole("region", { name: "Preview of Course index" });
  await expect(preview.getByRole("heading", { name: "Coffee making" })).toBeVisible();
  await expect(preview.getByRole("heading", { name: "Deliverables" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open raw file" })).toHaveAttribute(
    "href",
    new RegExp(`/api/courses/${PACKAGE_PREVIEW_COURSE_ID}/outputs/README\\.md$`),
  );

  await page.getByRole("button", { name: "Course overview" }).click();
  await expect(
    page.getByRole("region", { name: "Preview of Course overview" })
      .getByText("Audience: General adult learners who are new to the subject."),
  ).toBeVisible();

  const blocker = page.getByRole("button", {
    name: /Go to Human content review blocker in content, asset /,
  });
  await expect(blocker).toBeVisible();
  const label = await blocker.getAttribute("aria-label");
  const targetAsset = label?.split(", asset ").at(-1);
  expect(targetAsset).toBeTruthy();
  await blocker.click();
  await expect(page).toHaveURL(
    new RegExp(`/courses/${PACKAGE_PREVIEW_COURSE_ID}/content\\?mode=deterministic&asset=${targetAsset}$`),
  );
  await expect(page.locator(".production-board button.active")).toBeVisible();
});

test("Scenario A6 edits, previews, persists, and approves the typed Course Model", async ({
  page,
  request,
}) => {
  await page.goto(
    `/courses/${COURSE_MODEL_EDITOR_COURSE_ID}/course-model?mode=deterministic`,
  );
  await expect(page.getByRole("button", { name: "Run Course Model" })).toBeVisible();
  await page.getByRole("button", { name: "Run Course Model" }).click();
  await expect.poll(
    async () => (await stage(request, COURSE_MODEL_EDITOR_COURSE_ID, "course-model")).state,
    { timeout: 30_000 },
  ).toBe("awaiting_review");
  await expect(page.getByRole("heading", { name: "Course Model" })).toBeVisible();

  await page.locator(".decision-bar").getByRole("button", { name: "Edit Course Model" }).click();
  const firstTitle = page.getByLabel("Subtopic title for m1_s1");
  await expect(firstTitle).toBeVisible();
  await firstTitle.fill("Grind Size and Extraction Control");

  await page.getByRole("button", { name: "Add coverage requirement" }).click();
  const newCoverageStatement = page.getByLabel(/^Coverage statement for new_coverage_/);
  await newCoverageStatement.fill(
    "Compare two grind settings and justify the next extraction adjustment.",
  );
  const newCoverageConcepts = page.getByLabel(/^Concept references for coverage new_coverage_/);
  await newCoverageConcepts.selectOption({ index: 0 });

  await page.getByRole("button", {
    name: "Reorder subtopic Grind Size and Extraction Control down",
  }).click();
  await page.getByRole("button", { name: "Preview impact" }).click();
  await expect(page.getByText("Backend validation passed")).toBeVisible();
  const detailedDiff = page.getByRole("region", { name: "What will change" });
  await expect(detailedDiff).toBeVisible();
  const added = detailedDiff.getByRole("region", { name: "Added records: 1" });
  await expect(added.getByText("Compare two grind settings and justify the next extraction adjustment.")).toBeVisible();
  await expect(added.locator(".course-model-diff-ref code").first()).toHaveText(/^new_coverage_/);
  await expect(added.locator(".course-model-diff-ref code").nth(1)).toHaveText(/^cr[0-9]+$/);
  const renamed = detailedDiff.getByRole("region", { name: "Renamed records: 1" });
  await expect(renamed.locator(".diff-before")).toContainText("Grind Size");
  await expect(renamed.locator(".diff-after")).toContainText("Grind Size and Extraction Control");
  await expect(detailedDiff.getByRole("region", { name: /Moved or reordered records:/ })).toBeVisible();
  await expect(page.getByText(/Downstream impact:/)).toBeVisible();
  await page.getByRole("checkbox", { name: /reviewed the detailed structural diff/i }).check();
  await page.getByRole("button", { name: "Save Course Model draft" }).click();

  await expect.poll(
    async () => (await stage(request, COURSE_MODEL_EDITOR_COURSE_ID, "course-model")).state,
  ).toBe("awaiting_review");
  await expect(
    page.getByRole("heading", { name: "Grind Size and Extraction Control" }),
  ).toBeVisible();
  await page.reload();
  await page
    .locator(".model-tree")
    .getByRole("button", { name: /Grind Size and Extraction Control/ })
    .click();
  await expect(
    page.getByRole("heading", { name: "Grind Size and Extraction Control" }),
  ).toBeVisible();
  await expect(
    page.getByText("Compare two grind settings and justify the next extraction adjustment."),
  ).toBeVisible();

  await page.getByRole("button", { name: "Approve Course Model" }).click();
  await expect.poll(
    async () => (await stage(request, COURSE_MODEL_EDITOR_COURSE_ID, "course-model")).state,
  ).toBe("approved");
  await expect.poll(
    async () => (await stage(request, COURSE_MODEL_EDITOR_COURSE_ID, "blueprint")).state,
  ).toBe("ready");
});

test("Scenario A7 reconciles and approves an exact typed Blueprint", async ({
  page,
  request,
}) => {
  await page.goto(
    `/courses/${BLUEPRINT_EDITOR_COURSE_ID}/blueprint?mode=deterministic`,
  );
  await expect(page.getByRole("button", { name: "Run Blueprint" })).toBeVisible();
  await page.getByRole("button", { name: "Run Blueprint" }).click();
  await expect.poll(
    async () => (await stage(request, BLUEPRINT_EDITOR_COURSE_ID, "blueprint")).state,
    { timeout: 30_000 },
  ).toBe("awaiting_review");
  await expect(page.getByRole("heading", { name: "Blueprint" })).toBeVisible();

  await page.locator(".decision-bar").getByRole("button", { name: "Edit Blueprint" }).click();
  await expect(page.getByRole("heading", { name: "Edit Blueprint" })).toBeVisible();

  const grindAssets = page.getByLabel("Assets for Grind Size");
  await grindAssets.getByRole("button", { name: /Activity/ }).click();
  await expect(grindAssets.getByRole("button", { name: /Activity/ })).toHaveAttribute(
    "aria-pressed",
    "true",
  );

  const conceptsAssets = page.getByLabel("Assets for Core Concepts In Coffee Making");
  await conceptsAssets.getByRole("button", { name: /Activity/ }).click();
  await expect(conceptsAssets.getByRole("button", { name: /Activity/ })).toHaveAttribute(
    "aria-pressed",
    "false",
  );

  await page.getByLabel("Coffee Making Troubleshooting learning time").fill("35");
  await page.getByLabel("Coffee Making Troubleshooting required examples").fill("4");
  await expect(
    page.getByLabel("Assets for Coffee Making Troubleshooting")
      .getByRole("button", { name: /Course Content/ }),
  ).toHaveAttribute("aria-pressed", "true");

  const reconciliation = page.getByRole("region", { name: "What generation will change" });
  await expect(reconciliation.getByText("m1_s1_activities")).toBeVisible();
  await expect(reconciliation.getByText("m1_s2_activities")).toBeVisible();
  await page.getByRole("checkbox", { name: /reviewed the exact asset additions/i }).check();
  await page.getByRole("button", { name: "Save Blueprint draft" }).click();

  await expect(page.getByRole("heading", { name: "Blueprint" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Blueprint" })).toBeVisible();

  const saved = await blueprintArtifact(request, BLUEPRINT_EDITOR_COURSE_ID);
  const plans = Object.fromEntries(
    saved.artifact.body.subtopic_plans.map((plan) => [plan.subtopic_id, plan]),
  );
  expect(
    plans.m1_s1.asset_plan.find((asset) => asset.asset_type === "activities")
      ?.selection_status,
  ).toBe("selected");
  expect(
    plans.m1_s2.asset_plan.find((asset) => asset.asset_type === "activities")
      ?.selection_status,
  ).toBe("rejected");
  expect(plans.m1_s4.depth_budget).toMatchObject({
    target_learning_minutes: 35,
    required_example_count: 4,
  });
  expect(
    plans.m1_s4.asset_plan.find((asset) => asset.asset_type === "course_content")
      ?.selection_status,
  ).toBe("selected");
  expect(plans.m1_s4.anchor_asset_waiver_confirmed).toBe(false);

  const selectedAssets = saved.artifact.body.subtopic_plans.flatMap((plan) =>
    plan.asset_plan.filter((asset) => asset.selection_status === "selected"),
  );
  expect(selectedAssets).toHaveLength(17);
  for (const plan of saved.artifact.body.subtopic_plans) {
    const authoritativeIds = plan.subtopic_id === "m1_s2" || plan.subtopic_id === "m1_s4"
      ? ["coffee_g1", "coffee_g2"]
      : ["coffee_g1"];
    for (const asset of plan.asset_plan) {
      if (asset.selection_status === "selected") {
        expect(asset.source_ids).toEqual(authoritativeIds);
      } else {
        expect(asset.source_ids).toEqual([]);
      }
    }
  }

  await page.getByRole("button", { name: "Approve Blueprint" }).click();
  await expect.poll(
    async () => (await stage(request, BLUEPRINT_EDITOR_COURSE_ID, "blueprint")).state,
  ).toBe("approved");
  await expect.poll(
    async () => (await stage(request, BLUEPRINT_EDITOR_COURSE_ID, "content")).state,
  ).toBe("ready");
});

test("Scenario A12 reconciles and approves a typed Lesson Plan", async ({
  page,
  request,
}) => {
  await page.goto(
    `/courses/${LESSON_PLAN_EDITOR_COURSE_ID}/lesson-plan?mode=deterministic`,
  );
  await expect(page.getByRole("button", { name: "Run Lesson Plan" })).toBeVisible();
  await page.getByRole("button", { name: "Run Lesson Plan" }).click();
  await expect.poll(
    async () => (await stage(request, LESSON_PLAN_EDITOR_COURSE_ID, "lesson-plan")).state,
    { timeout: 30_000 },
  ).toBe("awaiting_review");

  await page.locator(".decision-bar").getByRole("button", { name: "Edit Lesson Plan" }).click();
  await expect(page.getByRole("heading", { name: "Edit Lesson Plan" })).toBeVisible();
  await page.getByLabel("Maximum session hours").fill("0.5");
  await page.getByLabel("Delivery mode for Coffee Making Troubleshooting").selectOption("self_study");
  await page.getByLabel("Instructor count").fill("1");
  await page.getByLabel("Delivery platform").fill("Studio classroom");
  await page.getByLabel("Calendar dates").fill("2026-08-03\n2026-08-10");

  await expect(page.getByText("4 subtopics, each exactly once.")).toBeVisible();
  const reconciliation = page.getByRole("region", { name: "What delivery planning will change" });
  await expect(reconciliation.getByText("sess1")).toBeVisible();
  await page.getByRole("checkbox", { name: /reviewed the changed constraints/i }).check();
  await page.getByRole("button", { name: "Save Lesson Plan draft" }).click();

  await expect(page.getByRole("heading", { name: "Lesson Plan" })).toBeVisible();
  await page.reload();
  await expect(page.getByText("Last decision changed exact sessions:", { exact: false })).toBeVisible();
  const saved = await lessonPlanArtifact(request, LESSON_PLAN_EDITOR_COURSE_ID);
  const covered = saved.artifact.body.sessions.flatMap((session) =>
    session.covers.map((cover) => cover.subtopic_id),
  );
  expect(covered).toEqual(saved.artifact.body.coverage_summary.expected_subtopic_ids);
  expect(new Set(covered).size).toBe(covered.length);
  expect(saved.artifact.body.sessions).toHaveLength(4);
  expect(saved.artifact.body.sessions.every((session) => session.duration_minutes <= 30)).toBe(true);
  expect(
    saved.artifact.body.sessions.flatMap((session) => session.covers)
      .find((cover) => cover.subtopic_id === "m1_s4")?.mode,
  ).toBe("self_study");
  expect(saved.artifact.body.session_constraints).toMatchObject({
    max_session_hours: 0.5,
    default_mode: "live",
    calendar_dates: ["2026-08-03", "2026-08-10"],
    instructor_count: 1,
    delivery_platform: "Studio classroom",
  });
  expect(saved.artifact.body.unresolved_session_constraints).toEqual([]);
  expect(saved.artifact.body.decision_log.at(-1)?.affected_session_ids).toEqual([
    "sess1",
    "sess2",
    "sess3",
    "sess4",
    "sess5",
  ]);

  await page.getByRole("button", { name: "Approve Lesson Plan" }).click();
  await expect.poll(
    async () => (await stage(request, LESSON_PLAN_EDITOR_COURSE_ID, "lesson-plan")).state,
  ).toBe("approved");
  await expect.poll(
    async () => (await stage(request, LESSON_PLAN_EDITOR_COURSE_ID, "package")).state,
  ).toBe("ready");
});

test("NC-70 adds a known source and commits one bounded repair route", async ({
  page,
  request,
}) => {
  const dossierBefore = await canonicalArtifact<SourceDossierBody>(
    request,
    SOURCE_REPAIR_COURSE_ID,
    "research_dossier",
  );
  const registryBefore = await canonicalArtifact<SourceRegistryBody>(
    request,
    SOURCE_REPAIR_COURSE_ID,
    "approved_source_registry",
  );
  const modelBefore = await canonicalArtifact<CourseModelSourceBody>(
    request,
    SOURCE_REPAIR_COURSE_ID,
    "course_model",
  );
  const blueprintBefore = await canonicalArtifact<BlueprintSourceBody>(
    request,
    SOURCE_REPAIR_COURSE_ID,
    "blueprint",
  );
  const contentBefore = await canonicalArtifact<Record<string, unknown>>(
    request,
    SOURCE_REPAIR_COURSE_ID,
    "content_package",
  );

  await page.goto(
    `/courses/${SOURCE_REPAIR_COURSE_ID}/research?mode=deterministic`,
  );
  await expect(page.getByRole("button", { name: "+ Add source" })).toBeVisible();
  await expect(
    page.getByText("Recommendation is separate from your decision.").first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "+ Add source" }).click();
  await page.getByLabel("Source URL").fill(
    "https://example.edu/focused-coffee-evidence",
  );
  await page.getByLabel(/Title/).fill("Known focused coffee evidence");
  await page.getByLabel(/Publisher/).fill("Example University");
  await page.getByLabel(/Why it may help/).fill(
    "May address the unsupported coffee claim.",
  );
  await page.getByLabel(/Trust note/).fill(
    "Human-provided URL; authority still requires source review.",
  );
  await page.getByRole("button", { name: "Add proposed source" }).click();
  await expect(
    page.getByRole("heading", { name: "Known focused coffee evidence" }),
  ).toBeVisible();

  const dossierWithKnown = await canonicalArtifact<SourceDossierBody>(
    request,
    SOURCE_REPAIR_COURSE_ID,
    "research_dossier",
  );
  const knownCandidate = dossierWithKnown.artifact.body.source_candidates.find(
    (source) => source.id.startsWith("known_"),
  );
  expect(knownCandidate).toMatchObject({ status: "proposed" });
  expect(dossierWithKnown.artifact.body.source_candidates).toHaveLength(
    dossierBefore.artifact.body.source_candidates.length + 1,
  );
  expect(
    await canonicalArtifact<SourceRegistryBody>(
      request,
      SOURCE_REPAIR_COURSE_ID,
      "approved_source_registry",
    ),
  ).toEqual(registryBefore);

  await page.goto(
    `/courses/${SOURCE_REPAIR_COURSE_ID}/content?mode=deterministic`,
  );
  await expect(page.getByText("1 blocking verification finding")).toBeVisible();
  await page.getByRole("button", {
    name: "Find better evidence for m1_s1_cc, finding m1_s1_cc_c1",
  }).click();
  const repairQueue = page.getByRole("region", { name: "Source repair queue" });
  await expect(repairQueue).toBeVisible();
  await expect(
    repairQueue.getByText(/Recommendations are advisory/),
  ).toBeVisible();
  await expect(
    repairQueue.getByText(/This deterministic passage exists to prove/),
  ).toBeVisible({ timeout: 30_000 });
  await expect(
    repairQueue.getByRole("button", { name: "Approve this candidate" }),
  ).toBeVisible();

  expect(
    await canonicalArtifact<SourceRegistryBody>(
      request,
      SOURCE_REPAIR_COURSE_ID,
      "approved_source_registry",
    ),
  ).toEqual(registryBefore);
  await repairQueue.getByRole("button", { name: "Approve this candidate" }).click();
  await expect(
    repairQueue.getByRole("button", { name: "Confirm exact source route" }),
  ).toBeVisible();
  await expect(
    repairQueue.locator("dl").getByText("m1_s1_cc", { exact: true }),
  ).toBeVisible();
  expect(
    await canonicalArtifact<SourceRegistryBody>(
      request,
      SOURCE_REPAIR_COURSE_ID,
      "approved_source_registry",
    ),
  ).toEqual(registryBefore);
  await repairQueue.getByRole("button", { name: "Confirm exact source route" }).click();

  await expect(
    page.getByText("Source approved and route committed atomically"),
  ).toBeVisible();
  await expect(
    repairQueue.getByRole("button", { name: "Regenerate and reverify" }),
  ).toBeVisible();

  const ledgerResponse = await request.get(
    `/api/courses/${SOURCE_REPAIR_COURSE_ID}/source-repairs`,
  );
  expect(ledgerResponse.ok()).toBe(true);
  const ledger = (await ledgerResponse.json()) as SourceRepairLedger;
  expect(ledger.entries).toHaveLength(1);
  const repair = ledger.entries[0];
  expect(repair.status).toBe("awaiting_content_repair");
  expect(repair.affected_asset_ids).toEqual(["m1_s1_cc"]);
  expect(repair.approved_source_route).toMatchObject({
    subtopic_ids: ["m1_s1"],
    asset_ids: ["m1_s1_cc"],
  });
  const sourceId = repair.approved_source_route?.source_id;
  expect(sourceId).toBeTruthy();

  const dossierAfter = await canonicalArtifact<SourceDossierBody>(
    request,
    SOURCE_REPAIR_COURSE_ID,
    "research_dossier",
  );
  expect(
    dossierAfter.artifact.body.source_candidates.find(
      (source) => source.id === knownCandidate?.id,
    ),
  ).toMatchObject({ status: "proposed" });
  expect(
    dossierAfter.artifact.body.source_candidates.find(
      (source) => source.id === sourceId,
    ),
  ).toMatchObject({ status: "approved" });

  const registryAfter = await canonicalArtifact<SourceRegistryBody>(
    request,
    SOURCE_REPAIR_COURSE_ID,
    "approved_source_registry",
  );
  expect(registryAfter.artifact.body.decision.approved_ids).toContain(sourceId);
  expect(registryAfter.artifact.body.source_registry.map((source) => source.id)).toContain(
    sourceId,
  );

  const modelAfter = await canonicalArtifact<CourseModelSourceBody>(
    request,
    SOURCE_REPAIR_COURSE_ID,
    "course_model",
  );
  expect(modelAfter.artifact.body.source_registry.map((source) => source.id)).toContain(
    sourceId,
  );
  expect(
    modelAfter.artifact.body.modules[0].subtopics[0].approved_source_ids,
  ).toContain(sourceId);
  expect(modelAfter.artifact.body.modules[0].subtopics.slice(1)).toEqual(
    modelBefore.artifact.body.modules[0].subtopics.slice(1),
  );

  const blueprintAfter = await canonicalArtifact<BlueprintSourceBody>(
    request,
    SOURCE_REPAIR_COURSE_ID,
    "blueprint",
  );
  const planBefore = blueprintBefore.artifact.body.subtopic_plans[0];
  const planAfter = blueprintAfter.artifact.body.subtopic_plans[0];
  expect(
    planAfter.asset_plan.find((asset) => asset.id === "m1_s1_cc")?.source_ids,
  ).toContain(sourceId);
  expect(planAfter.asset_plan.filter((asset) => asset.id !== "m1_s1_cc")).toEqual(
    planBefore.asset_plan.filter((asset) => asset.id !== "m1_s1_cc"),
  );
  expect(blueprintAfter.artifact.body.subtopic_plans.slice(1)).toEqual(
    blueprintBefore.artifact.body.subtopic_plans.slice(1),
  );
  expect(
    blueprintAfter.artifact.body.subtopic_plans.flatMap((plan) =>
      plan.asset_plan.map((asset) => [asset.id, asset.selection_status]),
    ),
  ).toEqual(
    blueprintBefore.artifact.body.subtopic_plans.flatMap((plan) =>
      plan.asset_plan.map((asset) => [asset.id, asset.selection_status]),
    ),
  );

  expect(
    await canonicalArtifact<Record<string, unknown>>(
      request,
      SOURCE_REPAIR_COURSE_ID,
      "content_package",
    ),
  ).toEqual(contentBefore);
});

test("Scenario A8 keeps source-less and unattributed findings blocking in the browser", async ({
  page,
  request,
}) => {
  await page.goto(
    `/courses/${CONTENT_BLOCKER_TRUTH_COURSE_ID}/content?mode=deterministic`,
  );

  await expect(page.getByText("2 blocking verification findings")).toBeVisible();
  const repairQueue = page.getByRole("region", { name: "Content repair queue" });
  await expect(repairQueue).toContainText("Missing attribution");
  await expect(repairQueue).toContainText("2 blocking · 0 review");
  await expect(
    repairQueue.locator(".repair-group-missing_attribution article"),
  ).toHaveCount(2);

  const board = page.getByRole("complementary", { name: "Production board" });
  await board.getByRole("button", { name: /Grind Size/ }).click();
  await expect(page.getByText("1 to inspect")).toBeVisible();
  await expect(page.getByText("No ground").locator("..")).toContainText("2");
  await expect(page.getByRole("button", { name: "Mark asset reviewed" })).toBeDisabled();
  await expect(page.getByText("2 blocking findings must be repaired first.")).toBeVisible();

  await repairQueue.getByRole("button", {
    name: "Revise with approved evidence for m1_s1_cc, finding m1_s1_cc_c1",
  }).click();
  await expect.poll(
    async () => (await contentRepairProjection(request, CONTENT_BLOCKER_TRUTH_COURSE_ID)).hard_blocker_total,
    { timeout: 30_000 },
  ).toBe(0);
  await expect(page.getByText("No blocking verification findings")).toBeVisible();
  await expect(page.getByRole("button", { name: "Mark asset reviewed" })).toBeEnabled();
});

test("Scenarios A9 and A10 repair exact assets and close Content review", async ({
  page,
  request,
}) => {
  test.setTimeout(60_000);
  const packageBefore = await canonicalArtifact<ContentPackageBody>(
    request,
    CONTENT_REPAIR_COURSE_ID,
    "content_package",
  );
  const assetsBefore = contentAssets(packageBefore.artifact.body);
  const hashesBefore = new Map(
    [...assetsBefore].map(([assetId, asset]) => [assetId, contentHash(asset)]),
  );
  const reviewBefore = await contentReview(request, CONTENT_REPAIR_COURSE_ID);
  expect(reviewBefore.artifact.body.summary.pending).toBe(0);

  await page.goto(
    `/courses/${CONTENT_REPAIR_COURSE_ID}/content?mode=deterministic`,
  );
  await expect(page.getByText("2 blocking verification findings")).toBeVisible();
  const repairQueue = page.getByRole("region", { name: "Content repair queue" });
  await expect(repairQueue).toContainText("Likely content error");
  await expect(repairQueue).toContainText("Insufficient evidence");
  await expect(repairQueue).toContainText("Human review");
  await expect(repairQueue).toContainText("2 blocking · 1 review");

  const existingEvidenceGroup = repairQueue.locator(
    ".repair-group-likely_content_error",
  );
  await expect(existingEvidenceGroup).toContainText("m1_s2_cc");
  const existingRepairButton = existingEvidenceGroup.getByRole("button", {
    name: "Revise with approved evidence",
  });
  await expect(existingRepairButton).toHaveAttribute(
    "aria-label",
    /m1_s2_cc, finding m1_s2_cc_c1/,
  );
  await existingRepairButton.focus();
  await page.keyboard.press("Enter");
  await expect.poll(
    async () => (await contentRepairProjection(request, CONTENT_REPAIR_COURSE_ID)).hard_blocker_total,
    { timeout: 30_000 },
  ).toBe(1);
  await expect(page.getByText("1 blocking verification finding")).toBeVisible();

  const packageAfterExisting = await canonicalArtifact<ContentPackageBody>(
    request,
    CONTENT_REPAIR_COURSE_ID,
    "content_package",
  );
  const assetsAfterExisting = contentAssets(packageAfterExisting.artifact.body);
  expect(contentHash(assetsAfterExisting.get("m1_s2_cc"))).not.toBe(
    hashesBefore.get("m1_s2_cc"),
  );
  for (const [assetId, expectedHash] of hashesBefore) {
    if (assetId === "m1_s2_cc") continue;
    expect(contentHash(assetsAfterExisting.get(assetId)), assetId).toBe(expectedHash);
  }
  const reviewAfterExisting = await contentReview(request, CONTENT_REPAIR_COURSE_ID);
  const beforeReviewRecords = new Map(
    reviewBefore.artifact.body.assets.map((record) => [record.asset_id, record]),
  );
  const afterExistingReviewRecords = new Map(
    reviewAfterExisting.artifact.body.assets.map((record) => [record.asset_id, record]),
  );
  expect(afterExistingReviewRecords.get("m1_s2_cc")?.decision).toBe("pending");
  for (const [assetId, previous] of beforeReviewRecords) {
    if (assetId === "m1_s2_cc") continue;
    expect(afterExistingReviewRecords.get(assetId), assetId).toMatchObject({
      decision: previous.decision,
      asset_fingerprint: previous.asset_fingerprint,
    });
  }
  expect((await stage(request, CONTENT_REPAIR_COURSE_ID, "package")).prerequisites_ready)
    .toBe(false);

  const evidenceGapGroup = repairQueue.locator(
    ".repair-group-insufficient_evidence",
  );
  await expect(evidenceGapGroup).toContainText("m1_s1_cc");
  await evidenceGapGroup.getByRole("button", { name: "Find better evidence" }).click();
  const sourceQueue = page.getByRole("region", { name: "Source repair queue" });
  await expect(
    sourceQueue.getByText(/This deterministic passage exists to prove/),
  ).toBeVisible({ timeout: 30_000 });
  await sourceQueue.getByRole("button", { name: "Approve this candidate" }).click();
  await expect(
    sourceQueue.getByRole("button", { name: "Confirm exact source route" }),
  ).toBeVisible();
  await sourceQueue.getByRole("button", { name: "Confirm exact source route" }).click();
  await expect(
    sourceQueue.getByRole("button", { name: "Regenerate and reverify" }),
  ).toBeVisible();

  const packageAfterRoute = await canonicalArtifact<ContentPackageBody>(
    request,
    CONTENT_REPAIR_COURSE_ID,
    "content_package",
  );
  expect(packageAfterRoute).toEqual(packageAfterExisting);
  await sourceQueue.getByRole("button", { name: "Regenerate and reverify" }).click();
  await expect.poll(
    async () => (await contentRepairProjection(request, CONTENT_REPAIR_COURSE_ID)).hard_blocker_total,
    { timeout: 30_000 },
  ).toBe(0);
  await expect(page.getByText("No blocking verification findings")).toBeVisible();
  await expect(sourceQueue.getByText("Targeted regeneration complete")).toBeVisible();
  await expect(sourceQueue.getByText("No hard verifier blockers remain.")).toBeVisible();

  const packageAfterBetter = await canonicalArtifact<ContentPackageBody>(
    request,
    CONTENT_REPAIR_COURSE_ID,
    "content_package",
  );
  const assetsAfterBetter = contentAssets(packageAfterBetter.artifact.body);
  expect(contentHash(assetsAfterBetter.get("m1_s1_cc"))).not.toBe(
    contentHash(assetsAfterExisting.get("m1_s1_cc")),
  );
  for (const [assetId, previous] of assetsAfterExisting) {
    if (assetId === "m1_s1_cc") continue;
    expect(contentHash(assetsAfterBetter.get(assetId)), assetId).toBe(contentHash(previous));
  }

  const reviewAfterBetter = await contentReview(request, CONTENT_REPAIR_COURSE_ID);
  const reviewRecordsAfterBetter = new Map(
    reviewAfterBetter.artifact.body.assets.map((record) => [record.asset_id, record]),
  );
  expect(reviewRecordsAfterBetter.get("m1_s1_cc")?.decision).toBe("pending");
  expect(reviewRecordsAfterBetter.get("m1_s2_cc")?.decision).toBe("pending");
  for (const [assetId, previous] of afterExistingReviewRecords) {
    if (assetId === "m1_s1_cc") continue;
    expect(reviewRecordsAfterBetter.get(assetId), assetId).toMatchObject({
      decision: previous.decision,
      asset_fingerprint: previous.asset_fingerprint,
    });
  }

  const board = page.getByRole("complementary", { name: "Production board" });
  await board.getByRole("button", { name: /Grind Size/ }).click();
  await page.getByRole("button", { name: "Mark asset reviewed" }).click();
  await expect.poll(async () => {
    const ledgerResponse = await request.get(
      `/api/courses/${CONTENT_REPAIR_COURSE_ID}/source-repairs`,
    );
    const ledger = (await ledgerResponse.json()) as SourceRepairLedger;
    return ledger.entries[0]?.status;
  }).toBe("resolved");
  await expect(sourceQueue.getByText("Repair resolved")).toBeVisible();

  await board.getByRole("button", { name: /Core Concepts In Coffee Making/ }).click();
  await page.getByRole("button", { name: "Mark asset reviewed" }).click();
  await expect.poll(
    async () => (await contentReview(request, CONTENT_REPAIR_COURSE_ID)).artifact.body.summary.ready_for_package,
  ).toBe(true);
  const finalProjection = await contentRepairProjection(request, CONTENT_REPAIR_COURSE_ID);
  expect(finalProjection).toMatchObject({
    hard_blocker_total: 0,
    partial_total: 1,
    ready_for_package: true,
  });

  const approveContent = page.getByRole("button", { name: "Approve Student Content" });
  await expect(approveContent).toBeEnabled();
  await approveContent.click();
  await expect.poll(
    async () => (await stage(request, CONTENT_REPAIR_COURSE_ID, "content")).state,
  ).toBe("approved");
  const lessonPlanStage = await stage(
    request,
    CONTENT_REPAIR_COURSE_ID,
    "lesson-plan",
  );
  expect(lessonPlanStage.state).toBe("ready");
  expect(lessonPlanStage.prerequisites_ready).toBe(true);
  await page.goto(`/courses/${CONTENT_REPAIR_COURSE_ID}/lesson-plan?mode=deterministic`);
  await expect(page.getByRole("button", { name: "Run Lesson Plan" })).toBeEnabled();
});
