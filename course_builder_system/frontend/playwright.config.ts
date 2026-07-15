import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.dirname(frontendRoot);
const artifactRoot = path.join(repositoryRoot, "output", "playwright");
const python = path.join(repositoryRoot, ".venv", "bin", "python");

export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.e2e.ts",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [
    ["list"],
    ["html", { outputFolder: path.join(artifactRoot, "report"), open: "never" }],
  ],
  outputDir: path.join(artifactRoot, "test-results"),
  use: {
    baseURL: "http://127.0.0.1:8765",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: {
    command: `${python} -m uvicorn tests.browser_acceptance_server:app --host 127.0.0.1 --port 8765`,
    cwd: repositoryRoot,
    url: "http://127.0.0.1:8765/api/health",
    reuseExistingServer: false,
    timeout: 120_000,
    stdout: "pipe",
    stderr: "pipe",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
