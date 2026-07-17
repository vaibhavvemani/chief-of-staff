import { expect, test, type APIRequestContext, type Page } from "@playwright/test";

const SEEDED_LIFECYCLE_COURSE_ID = "studio-course-model-reopen-fixture";

interface StageProjection {
  state: string;
  checksum?: string;
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
});

test("keeps the seeded Course Model reopen lifecycle scenario", async ({ page, request }) => {
  await page.goto(
    `/courses/${SEEDED_LIFECYCLE_COURSE_ID}/course-model?mode=deterministic`,
  );
  await expect(page.getByRole("heading", { name: "Course Model" })).toBeVisible();
  await expect(page.getByText("Grind Size", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Edit subtopic" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Add module" })).toBeDisabled();
  await expect(page.getByRole("button", { name: /Add subtopic/ })).toBeDisabled();
  await page.getByRole("button", { name: "Open activity" }).click();
  await expect(
    page.getByRole("button", { name: "Model-call diagnostics unavailable" }),
  ).toBeDisabled();
  await page.getByRole("button", { name: "Close activity drawer" }).click();

  const reopenCourseModel = page.getByRole("button", { name: "Reopen Course Model" });
  await expect(reopenCourseModel).toBeVisible();
  await reopenCourseModel.click();
  await expect(page.getByRole("heading", { name: "Reopen Course Model" })).toBeVisible();
  await expect(page.getByText(/downstream artifacts made stale/i)).toBeVisible();
  await page.getByRole("checkbox", { name: /I understand/ }).check();
  await page.getByRole("button", { name: "Confirm and reopen" }).click();

  await expect.poll(async () => {
    return (await stage(request, SEEDED_LIFECYCLE_COURSE_ID, "course-model")).state;
  }).toBe("awaiting_review");
  await expect.poll(async () => {
    return (await stage(request, SEEDED_LIFECYCLE_COURSE_ID, "blueprint")).state;
  }).toBe("stale");
  await expect(page.getByText("Grind Size", { exact: true }).first()).toBeVisible();
});
