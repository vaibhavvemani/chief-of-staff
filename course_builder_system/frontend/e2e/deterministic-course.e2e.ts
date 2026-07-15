import { expect, test } from "@playwright/test";

const ACCEPTANCE_COURSE_ID = "studio-cycle-acceptance";

test("creates a course and reopens approved Brief and Course Model stages", async ({ page, request }) => {
  const initialCourses = await request.get("/api/courses");
  expect(initialCourses.ok()).toBe(true);
  const initialBody = await initialCourses.json();
  expect(initialBody.courses).toEqual([
    expect.objectContaining({
      course_id: ACCEPTANCE_COURSE_ID,
      read_only: false,
    }),
  ]);

  await page.goto("/courses");
  await expect(page.getByRole("button", { name: "Settings" })).toBeDisabled();
  await page.goto("/courses/new");
  await expect(page.getByRole("heading", { name: "Give the agent a clear starting point." })).toBeVisible();

  await page.getByLabel(/What should this course teach/).fill("Coffee making for home beginners");
  await page.getByRole("radio", { name: /Deterministic preview/ }).check();
  await page.getByRole("button", { name: /Create Brief/ }).click();

  await expect(page).toHaveURL(/\/courses\/[^/]+\/brief\?mode=deterministic$/);
  await expect(page.getByText("API connected", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Course Brief" })).toBeVisible();

  const createdCourses = await request.get("/api/courses");
  expect(createdCourses.ok()).toBe(true);
  const body = await createdCourses.json();
  expect(body.courses).toHaveLength(2);

  const courseId = body.courses.find(
    (course: { course_id: string }) => course.course_id !== ACCEPTANCE_COURSE_ID,
  )?.course_id as string;
  expect(courseId).toBeTruthy();
  const briefBeforeApproval = await request.get(`/api/courses/${courseId}/stages/brief`);
  expect(briefBeforeApproval.ok()).toBe(true);
  const brief = await briefBeforeApproval.json();

  const approval = await request.post(`/api/courses/${courseId}/stages/brief/approve`, {
    data: { expected_checksum: brief.checksum },
  });
  expect(approval.ok()).toBe(true);

  await page.reload();
  const reopenButton = page.getByRole("button", { name: "Reopen Brief" });
  await expect(reopenButton).toBeVisible();
  await reopenButton.click();

  await expect(page.getByRole("heading", { name: "Reopen Brief" })).toBeVisible();
  await expect(page.getByText(/server computed this impact from the current pipeline dependency graph/i)).toBeVisible();
  await page.getByRole("checkbox", { name: /I understand/ }).check();
  await page.getByRole("button", { name: "Confirm and reopen" }).click();

  await expect.poll(async () => {
    const response = await request.get(`/api/courses/${courseId}/stages/brief`);
    return (await response.json()).state;
  }).toBe("awaiting_review");

  await page.goto(`/courses/${ACCEPTANCE_COURSE_ID}/course-model?mode=deterministic`);
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
    const response = await request.get(
      `/api/courses/${ACCEPTANCE_COURSE_ID}/stages/course-model`,
    );
    return (await response.json()).state;
  }).toBe("awaiting_review");
  await expect.poll(async () => {
    const response = await request.get(
      `/api/courses/${ACCEPTANCE_COURSE_ID}/stages/blueprint`,
    );
    return (await response.json()).state;
  }).toBe("stale");
  await expect(page.getByText("Grind Size", { exact: true }).first()).toBeVisible();
});
