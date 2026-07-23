import { expect, test, type APIRequestContext, type Locator, type Page } from "@playwright/test";
import { createHash } from "node:crypto";
import { execFile as execFileCallback } from "node:child_process";
import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const execFile = promisify(execFileCallback);
const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const courseId = "studio-live-pilot";
const runMode = "live";
const resume = process.env.COURSE_BUILDER_LIVE_ACCEPTANCE_RESUME === "1";

const subtopicTitles = [
  "Assess an Indoor Growing Site",
  "Select Herbs, Containers, and Growing Medium",
  "Plant Herb Starters or Seeds",
  "Manage Light, Water, Feeding, and Rotation",
  "Harvest Herbs and Troubleshoot Common Problems",
] as const;

const curatedSources = [
  {
    locator: "https://extension.psu.edu/growing-herbs-indoors",
    title: "Growing Herbs Indoors",
    publisher: "Penn State Extension",
  },
  {
    locator: "https://extension.umd.edu/resource/growing-herbs-containers-and-indoors",
    title: "Growing Herbs in Containers and Indoors",
    publisher: "University of Maryland Extension",
  },
  {
    locator: "https://www.rhs.org.uk/herbs/containers",
    title: "Growing herbs in containers",
    publisher: "Royal Horticultural Society",
  },
] as const;

const competitorCourseSources = [
  "https://www.reork.com/tech-course/indoor-herb-cultivation/",
  "https://www.reork.com/tech-course/herb-gardening-fundamentals/",
  "https://workspace.oregonstate.edu/course/master-gardener-series-container-and-small-space-gardening",
] as const;

const assetLabels = [
  "Course Content",
  "Learning Objectives",
  "Summary",
  "Case Study",
  "Assessment",
  "Activity",
  "Resources",
] as const;

const desiredAssetLabels = [
  ["Course Content", "Activity"],
  ["Course Content", "Activity"],
  ["Course Content", "Case Study"],
  ["Course Content", "Assessment"],
  ["Course Content", "Resources"],
] as const;

interface StageProjection {
  state: string;
  checksum?: string;
}

interface JobProjection {
  job_id: string;
  status: string;
  error?: { type?: string } | null;
}

interface ArtifactEnvelope<TBody> {
  artifact: {
    status: string;
    body: TBody;
  };
  checksum: string;
}

interface CourseModelBody {
  modules: Array<{
    id: string;
    title: string;
    subtopics: Array<{
      id: string;
      title: string;
      approved_source_ids: string[];
      concepts: Array<{ source_ids: string[] }>;
      coverage_requirements: Array<{ source_ids: string[] }>;
    }>;
  }>;
  source_registry: Array<{ id: string }>;
}

interface BlueprintBody {
  subtopic_plans: Array<{
    subtopic_id: string;
    asset_plan: Array<{
      id: string;
      asset_type: string;
      selection_status: string;
      source_ids: string[];
    }>;
  }>;
}

interface VerificationSummary {
  supported: number;
  partial: number;
  unsupported: number;
  ungrounded: number;
  unattributed_found: unknown[];
}

interface ContentAsset {
  id: string;
  type: string;
  title: string;
  content: string;
  sources: string[];
  claims: Array<{ id: string; source_id?: string | null }>;
  verification: VerificationSummary;
}

interface ContentPackageBody {
  subtopics: Array<{
    subtopic_id: string;
    assets: ContentAsset[];
  }>;
}

interface ContentReviewBody {
  assets: Array<{
    asset_id: string;
    decision: string;
    asset_fingerprint: string;
  }>;
  summary: {
    approved: number;
    pending: number;
    verification_blockers: {
      unsupported: number;
      ungrounded: number;
      unattributed: number;
    };
    ready_for_package: boolean;
  };
}

interface ContentRepairProjection {
  findings: Array<{
    finding_id: string;
    asset_id: string;
    blocking: boolean;
    state: string;
    recommended_strategy?: string | null;
  }>;
}

interface ResearchBody {
  source_candidates: Array<{
    id: string;
    title: string;
    locator: string;
    status: string;
    content_ref?: string | null;
  }>;
}

interface SourceRegistryBody {
  decision: {
    selected_ids: string[];
    approved_ids: string[];
    rejected_ids: string[];
  };
  source_registry: Array<{ id: string; content_ref: string }>;
}

interface RunSummaryBody {
  operator_status: string;
  student_content_units: Array<{ asset_id: string; status: string }>;
}

interface BriefBody {
  intake_state: {
    answered_question_ids: string[];
  };
  live_teaching_constraints?: string | null;
}

interface RenderManifestBody {
  paths: {
    assets: Record<string, string>;
  };
}

interface WorkspaceProjection {
  operator_status: string;
  active_job?: { job_id: string; stage: string; status: string } | null;
  diagnostics: {
    stages: Array<Record<string, unknown>>;
    totals: Record<string, unknown>;
  };
  provider_readiness: {
    ready: boolean;
    provider: string;
    model: string;
    message: string;
  };
}

test.skip(
  process.env.COURSE_BUILDER_LIVE_ACCEPTANCE !== "1",
  "Set COURSE_BUILDER_LIVE_ACCEPTANCE=1 to authorize the credentialed NC-1104 run.",
);

async function stage(
  request: APIRequestContext,
  stageSlug: string,
): Promise<StageProjection> {
  const response = await request.get(`/api/courses/${courseId}/stages/${stageSlug}`);
  expect(response.ok(), `${stageSlug} projection`).toBe(true);
  return response.json() as Promise<StageProjection>;
}

async function artifact<TBody>(
  request: APIRequestContext,
  artifactType: string,
): Promise<ArtifactEnvelope<TBody>> {
  const response = await request.get(`/api/courses/${courseId}/artifacts/${artifactType}`);
  expect(response.ok(), `${artifactType} artifact`).toBe(true);
  return response.json() as Promise<ArtifactEnvelope<TBody>>;
}

async function workspace(request: APIRequestContext): Promise<WorkspaceProjection> {
  const response = await request.get(`/api/courses/${courseId}/workspace`);
  expect(response.ok(), "workspace projection").toBe(true);
  return response.json() as Promise<WorkspaceProjection>;
}

async function waitForStage(
  request: APIRequestContext,
  stageSlug: string,
  expected: string | string[],
  timeout = 10 * 60_000,
) {
  const states = Array.isArray(expected) ? expected : [expected];
  let observedState = "";
  await expect.poll(
    async () => {
      observedState = (await stage(request, stageSlug)).state;
      return states.includes(observedState) || observedState === "failed";
    },
    { timeout, intervals: [500, 1_000, 2_000, 5_000] },
  ).toBe(true);
  if (observedState === "failed") {
    throw new Error(
      `${stageSlug} entered a retryable failed state; inspect persisted job/activity evidence`,
    );
  }
}

async function waitForNoActiveJob(
  request: APIRequestContext,
  timeout = 15 * 60_000,
) {
  await expect.poll(
    async () => (await workspace(request)).active_job ?? null,
    { timeout, intervals: [1_000, 2_000, 5_000] },
  ).toBeNull();
}

async function waitForJob(
  request: APIRequestContext,
  jobId: string,
  timeout: number,
) {
  let job: JobProjection | undefined;
  await expect.poll(
    async () => {
      const response = await request.get(`/api/jobs/${jobId}`).catch(() => null);
      if (response === null) return false;
      expect(response.ok(), `job ${jobId}`).toBe(true);
      job = await response.json() as JobProjection;
      return ["completed", "failed", "cancelled"].includes(job.status);
    },
    { timeout, intervals: [500, 1_000, 2_000, 5_000] },
  ).toBe(true);
  if (job?.status !== "completed") {
    throw new Error(
      `${job?.job_id ?? jobId} ended ${job?.status ?? "unknown"}`
      + `${job?.error?.type ? ` (${job.error.type})` : ""}; inspect persisted activity evidence`,
    );
  }
}

async function runStage(
  page: Page,
  request: APIRequestContext,
  stageSlug: string,
  buttonName: string,
  expected: string | string[],
  timeout = 10 * 60_000,
) {
  const current = await stage(request, stageSlug);
  const expectedStates = Array.isArray(expected) ? expected : [expected];
  if (current.state === "approved" || expectedStates.includes(current.state)) {
    await page.goto(`/courses/${courseId}/${stageSlug}?mode=${runMode}`);
    return;
  }
  await page.goto(`/courses/${courseId}/${stageSlug}?mode=${runMode}`);
  if (current.state !== "running") {
    const name = current.state === "failed"
      ? buttonName.replace(/^Run /, "Retry ")
      : current.state === "stale"
        ? buttonName.replace(/^Run /, "Rerun ")
        : buttonName;
    const button = page.getByRole("button", { name });
    await expect(button, `${name} control`).toBeEnabled();
    const acceptedResponse = page.waitForResponse((response) =>
      response.request().method() === "POST"
      && response.url().includes(`/api/courses/${courseId}/stages/${stageSlug}/run`),
    );
    await button.click();
    const response = await acceptedResponse;
    expect(response.ok(), `${stageSlug} job acceptance`).toBe(true);
    const accepted = await response.json() as { job: JobProjection };
    await waitForJob(request, accepted.job.job_id, timeout);
  } else {
    const active = (await workspace(request)).active_job;
    expect(active?.job_id, `${stageSlug} active job`).toBeTruthy();
    await waitForJob(request, active!.job_id, timeout);
  }
  await waitForStage(request, stageSlug, expected, timeout);
  await waitForNoActiveJob(request, timeout);
  await page.reload();
}

async function approveStage(
  page: Page,
  request: APIRequestContext,
  stageSlug: string,
  buttonName: string,
) {
  if ((await stage(request, stageSlug)).state === "approved") return;
  await page.goto(`/courses/${courseId}/${stageSlug}?mode=${runMode}`);
  const button = page.getByRole("button", { name: buttonName });
  await expect(button).toBeEnabled();
  await button.click();
  await waitForStage(request, stageSlug, "approved", 60_000);
}

function questionAnswer(questionId: string, prompt: string): string | undefined {
  const normalized = `${questionId} ${prompt}`.toLowerCase();
  if (normalized.includes("audience") || normalized.includes("who is this course for")) {
    return "Apartment beginners with no outdoor growing space and no prior herb-growing experience.";
  }
  if (normalized.includes("purpose") || normalized.includes("able to do")) {
    return "Set up and maintain three container-grown culinary herbs, keep a simple care and troubleshooting log, and complete a first routine harvest.";
  }
  if (normalized.includes("live_teaching") || normalized.includes("live-teaching")) {
    return "Use two 45-minute instructor-led practice blocks with accessible self-paced setup and care-log work between them.";
  }
  if (normalized.includes("scope") || normalized.includes("coverage")) {
    return "Focus on indoor site assessment, container herb selection, planting, routine care, harvesting, and common-problem troubleshooting.";
  }
  if (normalized.includes("prior") || normalized.includes("experience")) {
    return "No gardening experience is assumed; learners can follow basic household instructions.";
  }
  return undefined;
}

async function answerQuestionCard(card: Locator) {
  const questionId = await card.getAttribute("data-question-id") ?? "unknown";
  const prompt = (await card.locator("legend").innerText()).replace(/^\d+/, "").trim();
  const explicitAnswer = questionAnswer(questionId, prompt);
  const radios = card.locator('input[type="radio"]');
  const checks = card.locator('input[type="checkbox"]');
  const text = card.locator('textarea, input[type="text"], input[type="number"]');
  const defaultButton = card.getByRole("button", { name: /Accept suggested default/i });

  if (questionId === "brief_modality" || prompt.toLowerCase().includes("delivery")) {
    await card.getByRole("radio", { name: /blended/i }).check();
  } else if (explicitAnswer && await text.count()) {
    await text.first().fill(explicitAnswer);
  } else if (await defaultButton.count()) {
    await defaultButton.click();
  } else if (await text.count()) {
    await text.first().fill(
      "Keep the course beginner-safe, practical, bounded to culinary herb care, and explicit about excluded high-stakes claims.",
    );
  } else if (await radios.count()) {
    await radios.first().check();
  } else if (await checks.count()) {
    await checks.first().check();
  } else {
    throw new Error(`Unsupported Brief question control: ${questionId}`);
  }
}

async function completeLiveBrief(page: Page, request: APIRequestContext) {
  if ((await stage(request, "brief")).state === "approved") return;
  await page.goto(`/courses/${courseId}/brief?mode=${runMode}`);
  await expect(page.getByText("Live ready", { exact: true })).toBeVisible();
  const startingBrief = await artifact<Record<string, unknown>>(request, "brief");
  let observedConditionalClarification = Boolean(
    startingBrief.artifact.body.live_teaching_constraints,
  );
  for (let round = 0; round < 8; round += 1) {
    const current = await stage(request, "brief");
    if (current.state === "awaiting_review") break;
    expect(current.state).toBe("needs_input");
    const cards = page.locator("fieldset.question-card");
    await expect(cards.first()).toBeVisible({ timeout: 3 * 60_000 });
    const count = await cards.count();
    expect(count).toBeGreaterThan(0);
    expect(count).toBeLessThanOrEqual(5);
    for (let index = 0; index < count; index += 1) {
      const card = cards.nth(index);
      if (await card.getAttribute("data-question-id") === "brief_live_teaching_constraints") {
        observedConditionalClarification = true;
      }
      await answerQuestionCard(card);
    }
    const submittedQuestionIds = await cards.evaluateAll((nodes) =>
      nodes.map((node) => node.getAttribute("data-question-id") ?? ""),
    );
    await page.getByRole("button", { name: "Save answers and continue" }).click();
    await expect.poll(
      async () => {
        const state = (await stage(request, "brief")).state;
        if (state === "awaiting_review") return "awaiting_review";
        if (state !== "needs_input") return state;
        const nextQuestionIds = await page.locator("fieldset.question-card").evaluateAll((nodes) =>
          nodes.map((node) => node.getAttribute("data-question-id") ?? ""),
        );
        return nextQuestionIds.length > 0
          && nextQuestionIds.join(",") !== submittedQuestionIds.join(",")
          ? "next_round"
          : "waiting";
      },
      { timeout: 3 * 60_000, intervals: [500, 1_000, 2_000] },
    ).not.toBe("waiting");
  }
  await waitForStage(request, "brief", "awaiting_review", 3 * 60_000);
  expect(observedConditionalClarification).toBe(true);
  const brief = await artifact<Record<string, unknown>>(request, "brief");
  expect(brief.artifact.body).toMatchObject({
    modality: "blended",
    in_scope: [...subtopicTitles],
    out_of_scope: expect.arrayContaining([
      "Medicinal or therapeutic use",
      "Commercial cultivation",
      "Pesticide prescriptions",
      "Electrical grow-light installation",
    ]),
  });
  await approveStage(page, request, "brief", "Approve Brief");
}

async function ensureCompetitorMaterials(page: Page, request: APIRequestContext) {
  const currentBrief = await artifact<{ available_materials?: string[] }>(request, "brief");
  const existing = currentBrief.artifact.body.available_materials ?? [];
  if (competitorCourseSources.every((locator) => existing.includes(locator))) return;

  await page.goto(`/courses/${courseId}/brief?mode=${runMode}`);
  if ((await stage(request, "brief")).state === "approved") {
    await page.getByRole("button", { name: "Reopen Brief" }).click();
    await expect(page.getByRole("heading", { name: "Reopen Brief" })).toBeVisible();
    await page.getByRole("checkbox", { name: /I understand/ }).check();
    await page.getByRole("button", { name: "Confirm and reopen" }).click();
    await waitForStage(request, "brief", "awaiting_review", 60_000);
  }
  await page.getByRole("button", {
    name: "Adjust additional requirements and materials in Course Brief",
  }).click();
  await page.getByLabel("Available materials").fill(
    [...new Set([...existing, ...competitorCourseSources])].join("\n"),
  );
  await page.getByRole("button", { name: "Save section" }).click();
  await expect.poll(async () => {
    const brief = await artifact<{ available_materials?: string[] }>(request, "brief");
    const materials = brief.artifact.body.available_materials ?? [];
    return competitorCourseSources.every((locator) => materials.includes(locator));
  }).toBe(true);
  await approveStage(page, request, "brief", "Approve Brief");
}

async function ensureKnownSources(page: Page, request: APIRequestContext) {
  let dossier = await artifact<ResearchBody>(request, "research_dossier");
  for (const source of curatedSources) {
    if (dossier.artifact.body.source_candidates.some((candidate) => candidate.locator === source.locator)) {
      continue;
    }
    await page.getByRole("button", { name: "+ Add source" }).click();
    await page.getByLabel("Source URL").fill(source.locator);
    await page.getByLabel(/^Title/).fill(source.title);
    await page.getByLabel(/^Publisher/).fill(source.publisher);
    await page.getByLabel(/Why it may help/).fill(
      "Authoritative practical guidance for beginner indoor culinary-herb setup and care.",
    );
    await page.getByLabel(/Trust note/).fill(
      "Public horticultural extension or professional horticultural authority selected by the operator.",
    );
    await page.getByRole("button", { name: "Add proposed source" }).click();
    await expect(
      page.getByRole("heading", { name: source.title, exact: true }),
    ).toBeVisible();
    dossier = await artifact<ResearchBody>(request, "research_dossier");
  }
  return dossier;
}

async function decideResearchSources(page: Page, request: APIRequestContext) {
  const existingRegistry = await request.get(
    `/api/courses/${courseId}/artifacts/approved_source_registry`,
  );
  if (existingRegistry.ok()) return;

  await page.goto(`/courses/${courseId}/research?mode=${runMode}`);
  const dossier = await ensureKnownSources(page, request);
  const selected = curatedSources.map((source) => {
    const candidate = dossier.artifact.body.source_candidates.find(
      (item) => item.locator === source.locator,
    );
    expect(candidate, source.locator).toBeTruthy();
    return candidate!;
  });
  for (const source of selected) {
    const card = page.locator("article.source-card").filter({ hasText: source.id });
    const select = card.getByRole("button", { name: "Select" });
    if (await select.count()) await select.click();
  }
  await page.getByRole("button", { name: `Save ${selected.length} selected sources` }).click();
  await expect(page.getByText("Ready for stage approval.")).toBeVisible({ timeout: 2 * 60_000 });
  const registry = await artifact<SourceRegistryBody>(request, "approved_source_registry");
  expect(registry.artifact.body.decision.approved_ids.sort()).toEqual(
    selected.map((source) => source.id).sort(),
  );
  expect(registry.artifact.body.decision.rejected_ids.length).toBeGreaterThan(0);
}

async function editOutcomes(page: Page, request: APIRequestContext) {
  if ((await stage(request, "outcomes")).state === "approved") return;
  const outcomes = await artifact<{
    outcomes: Array<{ id: string; evidence: string }>;
  }>(request, "course_outcomes");
  const first = outcomes.artifact.body.outcomes[0];
  expect(first).toBeTruthy();
  if (!first.evidence.includes("care log")) {
    await page.getByRole("button", { name: "Edit Outcomes" }).click();
    await page.getByLabel(`Evidence of learning for ${first.id}`).fill(
      "Learner completes a seven-day care log, diagnoses one common herb problem, and justifies a safe corrective action.",
    );
    await page.getByRole("button", { name: "Save Outcomes draft" }).click();
    await expect.poll(async () => {
      const current = await artifact<{ outcomes: Array<{ id: string; evidence: string }> }>(
        request,
        "course_outcomes",
      );
      return current.artifact.body.outcomes[0]?.evidence;
    }).toContain("care log");
  }
  await approveStage(page, request, "outcomes", "Approve Outcomes");
}

async function editCourseModel(page: Page, request: APIRequestContext) {
  if ((await stage(request, "course-model")).state === "approved") return;
  const model = await artifact<CourseModelBody>(request, "course_model");
  const baseline = model.artifact.body.modules.flatMap((module) => module.subtopics);
  expect(baseline.length).toBeGreaterThanOrEqual(5);
  await page.locator(".decision-bar").getByRole("button", { name: "Edit Course Model" }).click();

  for (let index = 0; index < 5; index += 1) {
    const subtopic = baseline[index];
    const row = page.locator(".editable-subtopic-list > div").filter({ hasText: subtopic.id });
    await row.locator("button.subtopic-select").click();
    await page.getByLabel(`Subtopic title for ${subtopic.id}`).fill(subtopicTitles[index]);
    await page.getByLabel(`Subtopic purpose for ${subtopic.id}`).fill(
      `Enable apartment beginners to make safe, practical decisions for ${subtopicTitles[index].toLowerCase()}.`,
    );
  }
  for (const extra of baseline.slice(5).reverse()) {
    const row = page.locator(".editable-subtopic-list > div").filter({ hasText: extra.id });
    await row.getByRole("button", { name: /^Remove subtopic / }).click();
    await page.getByRole("button", { name: "Remove record" }).click();
  }
  await page.getByRole("button", { name: "Preview impact" }).click();
  await expect(page.getByText("Backend validation passed")).toBeVisible();
  await page.getByRole("checkbox", { name: /reviewed the detailed structural diff/i }).check();
  await page.getByRole("button", { name: "Save Course Model draft" }).click();
  await expect.poll(async () => {
    const current = await artifact<CourseModelBody>(request, "course_model");
    return current.artifact.body.modules.flatMap((module) =>
      module.subtopics.map((subtopic) => subtopic.title),
    );
  }, { timeout: 60_000 }).toEqual([...subtopicTitles]);
  await approveStage(page, request, "course-model", "Approve Course Model");
}

async function editBlueprint(page: Page, request: APIRequestContext) {
  if ((await stage(request, "blueprint")).state === "approved") return;
  await page.locator(".decision-bar").getByRole("button", { name: "Edit Blueprint" }).click();
  for (let index = 0; index < subtopicTitles.length; index += 1) {
    const group = page.getByRole("group", { name: `Assets for ${subtopicTitles[index]}` });
    for (const label of assetLabels) {
      const button = group.getByRole("button", { name: label, exact: true });
      const desired = (desiredAssetLabels[index] as readonly string[]).includes(label);
      const selected = await button.getAttribute("aria-pressed") === "true";
      if (selected !== desired) await button.click();
    }
  }
  const firstMinutes = page.getByLabel(`${subtopicTitles[0]} learning time`);
  const currentMinutes = Number(await firstMinutes.inputValue());
  await firstMinutes.fill(String(currentMinutes === 25 ? 30 : 25));
  await page.getByRole("checkbox", { name: /reviewed the exact asset additions/i }).check();
  await page.getByRole("button", { name: "Save Blueprint draft" }).click();
  await expect.poll(async () => {
    const blueprint = await artifact<BlueprintBody>(request, "blueprint");
    return blueprint.artifact.body.subtopic_plans.flatMap((plan) =>
      plan.asset_plan.filter((asset) => asset.selection_status === "selected"),
    ).length;
  }).toBe(10);
  await approveStage(page, request, "blueprint", "Approve Blueprint");
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

function assetHashes(body: ContentPackageBody): Record<string, string> {
  return Object.fromEntries(body.subtopics.flatMap((subtopic) =>
    subtopic.assets.map((asset) => [
      asset.id,
      createHash("sha256").update(canonicalJson(asset)).digest("hex"),
    ]),
  ));
}

function hardBlockerTotal(body: ContentPackageBody): number {
  return body.subtopics.reduce((total, subtopic) => total + subtopic.assets.reduce(
    (assetTotal, asset) => assetTotal
      + asset.verification.unsupported
      + asset.verification.ungrounded
      + asset.verification.unattributed_found.length,
    0,
  ), 0);
}

async function runControlledContentRevision(
  page: Page,
  request: APIRequestContext,
  targetAssetId: string,
) {
  await page.goto(
    `/courses/${courseId}/content?mode=${runMode}&asset=${encodeURIComponent(targetAssetId)}`,
  );
  if ((await stage(request, "content")).state === "approved") {
    await page.locator(".decision-bar").getByRole("button", {
      name: "Reopen Student Content",
    }).click();
    await expect(page.getByRole("heading", { name: "Reopen Student Content?" })).toBeVisible();
    await page.getByLabel(
      /downstream artifacts will remain visible but cannot satisfy approved prerequisites/i,
    ).check();
    await page.getByRole("button", { name: "Confirm and reopen" }).click();
    await waitForStage(request, "content", ["awaiting_review", "requires_attention"], 60_000);
  }
  const beforeRevision = await artifact<ContentPackageBody>(request, "content_package");
  const revisionButton = page.getByRole("button", { name: "Request scoped revision" });
  await expect(revisionButton).toBeVisible({ timeout: 60_000 });
  await revisionButton.click();
  await page.getByText("Only the named").waitFor();
  await page.getByLabel("Revision instruction").fill(
    "Improve the opening learner guidance with one concrete apartment-safe action. Preserve approved evidence, do not add new factual claims, and keep every unrelated asset unchanged.",
  );
  await page.getByRole("button", { name: "Start scoped revision" }).click();
  await expect(page.getByRole("heading", { name: "Confirm this Student Content revision?" })).toBeVisible();
  await page.getByRole("checkbox", { name: /named record will be validated in scope/i }).check();
  const acceptedResponse = page.waitForResponse((response) =>
    response.request().method() === "POST"
    && response.url().includes(`/api/courses/${courseId}/stages/content/revisions`),
  );
  await page.getByRole("button", { name: "Confirm and start revision" }).click();
  const accepted = await acceptedResponse;
  expect(accepted.ok(), "content revision job acceptance").toBe(true);
  const payload = await accepted.json() as { job: JobProjection };
  await waitForJob(request, payload.job.job_id, 15 * 60_000);
  await expect.poll(
    async () => (await artifact<ContentPackageBody>(request, "content_package")).checksum,
    { timeout: 15 * 60_000, intervals: [1_000, 2_000, 5_000] },
  ).not.toBe(beforeRevision.checksum);
  await waitForNoActiveJob(request, 15 * 60_000);
}

async function resolveContentBlockers(
  page: Page,
  request: APIRequestContext,
  targetedAssetIds: Set<string>,
) {
  for (let attempt = 0; attempt < 12; attempt += 1) {
    const content = await artifact<ContentPackageBody>(request, "content_package");
    if (hardBlockerTotal(content.artifact.body) === 0) return;
    const response = await request.get(`/api/courses/${courseId}/content/repairs`);
    expect(response.ok()).toBe(true);
    const projection = await response.json() as ContentRepairProjection;
    const ready = projection.findings.filter((item) => item.blocking && item.state === "ready");
    const finding = ready.find((item) => item.recommended_strategy === "existing_evidence")
      ?? ready[0];
    expect(finding, "repairable hard verifier finding").toBeTruthy();
    expect(finding!.recommended_strategy, "live repair strategy").toBe("existing_evidence");
    targetedAssetIds.add(finding!.asset_id);
    await page.goto(
      `/courses/${courseId}/content?mode=${runMode}&asset=${encodeURIComponent(finding!.asset_id)}`,
    );
    const beforeChecksum = content.checksum;
    const acceptedResponse = page.waitForResponse((response) =>
      response.request().method() === "POST"
      && response.url().includes(`/api/courses/${courseId}/content/repairs`),
    );
    await page.getByRole("button", {
      name: `Revise with approved evidence for ${finding!.asset_id}, finding ${finding!.finding_id}`,
    }).click();
    const accepted = await acceptedResponse;
    if (!accepted.ok()) {
      throw new Error(`Content repair request failed: ${await accepted.text()}`);
    }
    const payload = await accepted.json() as { job: JobProjection };
    await waitForJob(request, payload.job.job_id, 15 * 60_000);
    await expect.poll(
      async () => (await artifact<ContentPackageBody>(request, "content_package")).checksum,
      { timeout: 15 * 60_000, intervals: [1_000, 2_000, 5_000] },
    ).not.toBe(beforeChecksum);
    await waitForNoActiveJob(request, 15 * 60_000);
  }
  throw new Error("Content hard blockers remained after twelve bounded repair attempts.");
}

async function reviewAllContent(page: Page, request: APIRequestContext) {
  const content = await artifact<ContentPackageBody>(request, "content_package");
  const assetIds = content.artifact.body.subtopics.flatMap((subtopic) =>
    subtopic.assets.map((asset) => asset.id),
  );
  for (const assetId of assetIds) {
    const review = await artifact<ContentReviewBody>(request, "content_review");
    if (review.artifact.body.assets.find((item) => item.asset_id === assetId)?.decision === "approved") {
      continue;
    }
    await page.goto(
      `/courses/${courseId}/content?mode=${runMode}&asset=${encodeURIComponent(assetId)}`,
    );
    const button = page.getByRole("button", { name: "Mark asset reviewed" });
    await expect(button, assetId).toBeEnabled();
    await button.click();
    await expect.poll(async () => {
      const current = await artifact<ContentReviewBody>(request, "content_review");
      return current.artifact.body.assets.find((item) => item.asset_id === assetId)?.decision;
    }).toBe("approved");
  }
}

async function editLessonPlan(page: Page, request: APIRequestContext) {
  if ((await stage(request, "lesson-plan")).state === "approved") return;
  await page.locator(".decision-bar").getByRole("button", { name: "Edit Lesson Plan" }).click();
  const maximum = page.getByLabel("Maximum session hours");
  const current = Number(await maximum.inputValue());
  await maximum.fill(String(current === 0.75 ? 1 : 0.75));
  await page.getByRole("checkbox", { name: /reviewed the changed constraints/i }).check();
  await page.getByRole("button", { name: "Save Lesson Plan draft" }).click();
  await waitForStage(request, "lesson-plan", "awaiting_review", 60_000);
  await approveStage(page, request, "lesson-plan", "Approve Lesson Plan");
}

async function completedScopedRevisionAssetIds(): Promise<string[]> {
  const jobRoot = path.join(repositoryRoot, "runtime", courseId, "jobs");
  const files = await fs.readdir(jobRoot);
  const jobs = await Promise.all(files.filter((name) => name.endsWith(".json")).map(async (name) =>
    JSON.parse(await fs.readFile(path.join(jobRoot, name), "utf8")) as {
      operation?: string;
      status?: string;
      created_at?: string;
      result?: { revision?: { outcome?: string; changed_ids?: string[] } };
    },
  ));
  const completed = jobs.filter((job) =>
    job.operation === "revision"
    && job.status === "completed"
    && job.result?.revision?.outcome === "changed"
    && job.result.revision.changed_ids?.length,
  ).sort((left, right) => String(right.created_at).localeCompare(String(left.created_at)));
  return completed[0]?.result?.revision?.changed_ids ?? [];
}

async function reopenLessonPlanForSummaryRefresh(
  page: Page,
  request: APIRequestContext,
): Promise<boolean> {
  const [content, summary] = await Promise.all([
    artifact<ContentPackageBody>(request, "content_package"),
    artifact<RunSummaryBody>(request, "run_summary"),
  ]);
  const contentIds = content.artifact.body.subtopics.flatMap((subtopic) =>
    subtopic.assets.map((asset) => asset.id),
  ).sort();
  const summaryIds = summary.artifact.body.student_content_units.map((unit) => unit.asset_id).sort();
  if (canonicalJson(contentIds) === canonicalJson(summaryIds)) return false;

  await page.goto(`/courses/${courseId}/lesson-plan?mode=${runMode}`);
  await page.locator(".decision-bar").getByRole("button", {
    name: "Reopen Lesson Plan",
  }).click();
  await expect(page.getByRole("heading", { name: "Reopen Lesson Plan?" })).toBeVisible();
  await page.getByLabel(
    /downstream artifacts will remain visible but cannot satisfy approved prerequisites/i,
  ).check();
  await page.getByRole("button", { name: "Confirm and reopen" }).click();
  await waitForStage(request, "lesson-plan", ["awaiting_review", "requires_attention"], 60_000);
  return true;
}

async function readRuntimeEvents(): Promise<Array<Record<string, unknown>>> {
  const eventRoot = path.join(repositoryRoot, "runtime", courseId, "events");
  const files = await fs.readdir(eventRoot);
  const events: Array<Record<string, unknown>> = [];
  for (const file of files.filter((name) => name.endsWith(".jsonl")).sort()) {
    const content = await fs.readFile(path.join(eventRoot, file), "utf8");
    for (const line of content.split("\n").filter(Boolean)) {
      events.push(JSON.parse(line) as Record<string, unknown>);
    }
  }
  return events;
}

function maximumInputCharsByStage(events: Array<Record<string, unknown>>) {
  const result: Record<string, number> = {};
  for (const event of events) {
    if (event.event_type !== "model.call.started") continue;
    const stageName = String(event.stage ?? "unknown");
    const inputChars = typeof event.input_chars === "number" ? event.input_chars : 0;
    result[stageName] = Math.max(result[stageName] ?? 0, inputChars);
  }
  return result;
}

test("NC-1104 completes the bounded credentialed live browser journey", async ({
  page,
  request,
}, testInfo) => {
  test.setTimeout(30 * 60_000);

  const healthResponse = await request.get("/api/health");
  expect(healthResponse.ok()).toBe(true);
  const health = await healthResponse.json() as {
    provider_readiness: {
      live: { ready: boolean; provider: string; model: string };
    };
  };
  expect(health.provider_readiness.live).toMatchObject({
    ready: true,
    provider: "anthropic",
    model: "claude-opus-4-8",
  });
  const cacheEntriesAtStart = await fs.readdir(path.join(repositoryRoot, ".llm_cache"))
    .then((entries) => entries.filter((name) => name.endsWith(".json")).length)
    .catch((error: NodeJS.ErrnoException) => {
      if (error.code === "ENOENT") return 0;
      throw error;
    });

  const coursesResponse = await request.get("/api/courses");
  expect(coursesResponse.ok()).toBe(true);
  const listed = await coursesResponse.json() as { courses: Array<{ course_id: string }> };
  const exists = listed.courses.some((course) => course.course_id === courseId);
  if (exists && !resume) {
    throw new Error(
      `${courseId} already exists. Preserve it and rerun only with COURSE_BUILDER_LIVE_ACCEPTANCE_RESUME=1.`,
    );
  }
  if (!exists) {
    const created = await request.post("/api/courses", {
      data: {
        course_id: courseId,
        subject: "Indoor herb gardening for apartment beginners",
        description: "Help apartment beginners set up and maintain three container-grown culinary herbs, use a simple care and troubleshooting log, and make a first routine harvest.",
        constraints: [
          "Non-high-stakes practical instruction only",
          "Five subtopics and exactly ten selected learner assets",
          "No medicinal, therapeutic, commercial, pesticide-prescription, or electrical-installation guidance",
        ],
        known_source_locators: [
          ...curatedSources.map((source) => source.locator),
          ...competitorCourseSources,
        ],
        brief: {
          in_scope: [...subtopicTitles],
          must_have_topics: [...subtopicTitles],
          out_of_scope: [
            "Medicinal or therapeutic use",
            "Commercial cultivation",
            "Pesticide prescriptions",
            "Electrical grow-light installation",
            "Claims requiring expert sign-off",
          ],
          accessibility_requirements: "Use plain language, descriptive headings, and instructions that do not rely on color alone.",
          assessment_expectations: "A practical setup check, a seven-day care log, and one troubleshooting decision.",
        },
      },
    });
    expect(created.ok(), await created.text()).toBe(true);
  }

  await page.goto(`/courses/${courseId}/brief?mode=${runMode}`);
  await expect(page.getByText("Live ready", { exact: true })).toBeVisible();
  await completeLiveBrief(page, request);
  await ensureCompetitorMaterials(page, request);

  await runStage(page, request, "outcomes", "Run Outcomes", "awaiting_review");
  await editOutcomes(page, request);

  await runStage(page, request, "research", "Run Research", "awaiting_review", 8 * 60_000);
  await decideResearchSources(page, request);
  await approveStage(page, request, "research", "Approve Research");

  await runStage(page, request, "course-model", "Run Course Model", "awaiting_review");
  await editCourseModel(page, request);

  await runStage(page, request, "blueprint", "Run Blueprint", "awaiting_review");
  await editBlueprint(page, request);

  await runStage(
    page,
    request,
    "content",
    "Run Student Content",
    ["awaiting_review", "requires_attention"],
    20 * 60_000,
  );
  const contentBeforeRepair = await artifact<ContentPackageBody>(request, "content_package");
  const hashesBeforeRepair = assetHashes(contentBeforeRepair.artifact.body);
  expect(Object.keys(hashesBeforeRepair)).toHaveLength(10);
  const targetedAssetIds = new Set<string>();
  let reusedTargetedRevision = false;
  if (hardBlockerTotal(contentBeforeRepair.artifact.body) === 0) {
    const reusableTargets = resume ? await completedScopedRevisionAssetIds() : [];
    if (reusableTargets.length) {
      reusableTargets.forEach((assetId) => targetedAssetIds.add(assetId));
      reusedTargetedRevision = true;
    } else {
      const controlledTarget = Object.keys(hashesBeforeRepair)[0];
      targetedAssetIds.add(controlledTarget);
      await runControlledContentRevision(page, request, controlledTarget);
    }
  }
  await resolveContentBlockers(page, request, targetedAssetIds);
  const contentAfterRepair = await artifact<ContentPackageBody>(request, "content_package");
  const hashesAfterRepair = assetHashes(contentAfterRepair.artifact.body);
  expect(hardBlockerTotal(contentAfterRepair.artifact.body)).toBe(0);
  for (const [assetId, beforeHash] of Object.entries(hashesBeforeRepair)) {
    if (!targetedAssetIds.has(assetId)) expect(hashesAfterRepair[assetId], assetId).toBe(beforeHash);
  }
  expect(targetedAssetIds.size).toBeGreaterThan(0);
  if (!reusedTargetedRevision) {
    expect([...targetedAssetIds].some((assetId) =>
      hashesAfterRepair[assetId] !== hashesBeforeRepair[assetId],
    )).toBe(true);
  }
  await reviewAllContent(page, request);
  const finalReview = await artifact<ContentReviewBody>(request, "content_review");
  expect(finalReview.artifact.body.summary).toMatchObject({
    approved: 10,
    pending: 0,
    ready_for_package: true,
    verification_blockers: { unsupported: 0, ungrounded: 0, unattributed: 0 },
  });
  await approveStage(page, request, "content", "Approve Student Content");

  const refreshedSummaryViaLessonPlan = await reopenLessonPlanForSummaryRefresh(page, request);
  await runStage(page, request, "lesson-plan", "Run Lesson Plan", "awaiting_review");
  await editLessonPlan(page, request);

  await runStage(page, request, "package", "Run Package", "awaiting_review");
  const packagePreview = page.getByRole("region", { name: "Preview of Course index" });
  await expect(packagePreview.getByRole("heading").first()).toBeVisible();
  const raw = await request.get(`/api/courses/${courseId}/outputs/README.md`);
  expect(raw.ok()).toBe(true);
  expect(await raw.text()).toContain(
    `# ${await packagePreview.getByRole("heading").first().innerText()}`,
  );
  await approveStage(page, request, "package", "Approve Package");
  await expect.poll(async () => (await workspace(request)).operator_status).toBe("complete");

  const [brief, model, blueprint, content, registry, manifest, summary] = await Promise.all([
    artifact<BriefBody>(request, "brief"),
    artifact<CourseModelBody>(request, "course_model"),
    artifact<BlueprintBody>(request, "blueprint"),
    artifact<ContentPackageBody>(request, "content_package"),
    artifact<SourceRegistryBody>(request, "approved_source_registry"),
    artifact<RenderManifestBody>(request, "render_manifest"),
    artifact<RunSummaryBody>(request, "run_summary"),
  ]);
  const approvedSourceIds = new Set(registry.artifact.body.source_registry.map((source) => source.id));
  const rejectedSourceIds = new Set(registry.artifact.body.decision.rejected_ids);
  const routedSourceIds = new Set<string>();
  for (const module of model.artifact.body.modules) {
    for (const subtopic of module.subtopics) {
      subtopic.approved_source_ids.forEach((id) => routedSourceIds.add(id));
      subtopic.concepts.flatMap((item) => item.source_ids).forEach((id) => routedSourceIds.add(id));
      subtopic.coverage_requirements.flatMap((item) => item.source_ids).forEach((id) => routedSourceIds.add(id));
    }
  }
  for (const plan of blueprint.artifact.body.subtopic_plans) {
    plan.asset_plan.flatMap((item) => item.source_ids).forEach((id) => routedSourceIds.add(id));
  }
  for (const subtopic of content.artifact.body.subtopics) {
    for (const asset of subtopic.assets) {
      asset.sources.forEach((id) => routedSourceIds.add(id));
      asset.claims.flatMap((claim) => claim.source_id ? [claim.source_id] : []).forEach((id) => routedSourceIds.add(id));
    }
  }
  expect([...routedSourceIds].every((id) => approvedSourceIds.has(id))).toBe(true);
  expect([...routedSourceIds].some((id) => rejectedSourceIds.has(id))).toBe(false);

  const selectedAssetIds = blueprint.artifact.body.subtopic_plans.flatMap((plan) =>
    plan.asset_plan.filter((asset) => asset.selection_status === "selected").map((asset) => asset.id),
  ).sort();
  const generatedAssetIds = content.artifact.body.subtopics.flatMap((subtopic) =>
    subtopic.assets.map((asset) => asset.id),
  ).sort();
  const renderedAssetIds = Object.keys(manifest.artifact.body.paths.assets).sort();
  const summarizedAssetIds = summary.artifact.body.student_content_units.map((unit) => unit.asset_id).sort();
  expect(selectedAssetIds).toHaveLength(10);
  expect(generatedAssetIds).toEqual(selectedAssetIds);
  expect(renderedAssetIds).toEqual(selectedAssetIds);
  expect(summarizedAssetIds).toEqual(selectedAssetIds);
  expect(summary.artifact.body.operator_status).toBe("complete");

  const { stdout: integrityOutput } = await execFile(
    path.join(repositoryRoot, ".venv", "bin", "python"),
    ["integrity.py", courseId],
    { cwd: repositoryRoot },
  );
  expect(integrityOutput).toContain("[integrity] OK");

  const finalWorkspace = await workspace(request);
  const runtimeEvents = await readRuntimeEvents();
  const requiredLiveStages = [
    "outcomes",
    "research",
    "course-model",
    "blueprint",
    "content",
    "lesson-plan",
  ];
  expect(brief.artifact.body.intake_state.answered_question_ids).toContain(
    "brief_live_teaching_constraints",
  );
  expect(brief.artifact.body.live_teaching_constraints).toBeTruthy();
  const observedLiveStages = new Set(
    runtimeEvents
      .filter((event) => event.event_type === "model.call.completed")
      .map((event) => String(event.stage)),
  );
  for (const required of requiredLiveStages) expect(observedLiveStages.has(required), required).toBe(true);
  const contentCallRoles = new Set(
    runtimeEvents
      .filter((event) => event.event_type === "model.call.completed" && event.stage === "content")
      .map((event) => String(event.call_role ?? "")),
  );
  expect(contentCallRoles).toEqual(new Set(["content_generation", "verification"]));

  const evidence = {
    accepted_at: new Date().toISOString(),
    course_id: courseId,
    subject: "Indoor herb gardening for apartment beginners",
    provider_readiness: finalWorkspace.provider_readiness,
    brief_clarification: {
      conditional_question_id: "brief_live_teaching_constraints",
      answered: true,
      implementation: "typed_conditional",
      live_model_call_required: false,
      reason: "No agent-generated follow-up or Brief synthesis was requested.",
    },
    cache_entries_at_start: cacheEntriesAtStart,
    diagnostics: finalWorkspace.diagnostics,
    maximum_input_chars_by_stage: maximumInputCharsByStage(runtimeEvents),
    content_call_roles: [...contentCallRoles].sort(),
    selected_asset_ids: selectedAssetIds,
    generated_asset_ids: generatedAssetIds,
    rendered_asset_ids: renderedAssetIds,
    asset_type_counts: Object.fromEntries(
      content.artifact.body.subtopics.flatMap((subtopic) => subtopic.assets).reduce(
        (counts, asset) => counts.set(asset.type, (counts.get(asset.type) ?? 0) + 1),
        new Map<string, number>(),
      ),
    ),
    approved_source_ids: [...approvedSourceIds].sort(),
    rejected_source_ids: [...rejectedSourceIds].sort(),
    verifier_before_repair: {
      hard_blockers: hardBlockerTotal(contentBeforeRepair.artifact.body),
    },
    verifier_after_repair: {
      hard_blockers: hardBlockerTotal(contentAfterRepair.artifact.body),
    },
    targeted_asset_ids: [...targetedAssetIds].sort(),
    reused_targeted_revision: reusedTargetedRevision,
    refreshed_summary_via_lesson_plan: refreshedSummaryViaLessonPlan,
    asset_hashes_before_repair: hashesBeforeRepair,
    asset_hashes_after_repair: hashesAfterRepair,
    content_review_summary: finalReview.artifact.body.summary,
    integrity_output: integrityOutput.trim(),
    operator_status: summary.artifact.body.operator_status,
    package_implementation: "deterministic",
    resumed: resume,
    playwright_project: testInfo.project.name,
  };
  const evidenceRoot = path.join(repositoryRoot, "output", "playwright", "live");
  await fs.mkdir(evidenceRoot, { recursive: true });
  await fs.writeFile(
    path.join(evidenceRoot, "nc110-live-acceptance-evidence.json"),
    `${JSON.stringify(evidence, null, 2)}\n`,
    "utf8",
  );
  await page.screenshot({
    path: path.join(evidenceRoot, "nc110-live-package-approved.png"),
    fullPage: true,
  });
});
