import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.dirname(frontendRoot);
const artifactRoot = path.join(repositoryRoot, "output", "playwright", "live");
const python = path.join(repositoryRoot, ".venv", "bin", "python");

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/live-course.e2e.ts",
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  workers: 1,
  timeout: 30 * 60_000,
  expect: { timeout: 30_000 },
  reporter: [
    ["list"],
    ["html", { outputFolder: path.join(artifactRoot, "report"), open: "never" }],
  ],
  outputDir: path.join(artifactRoot, "test-results"),
  use: {
    baseURL: "http://127.0.0.1:8766",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: {
    command: `${python} -m uvicorn api.main:app --host 127.0.0.1 --port 8766 --no-access-log`,
    cwd: repositoryRoot,
    url: "http://127.0.0.1:8766/api/health",
    reuseExistingServer: false,
    timeout: 120_000,
    stdout: "pipe",
    stderr: "pipe",
  },
  projects: [
    {
      name: "chromium-live",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
