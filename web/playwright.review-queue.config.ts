import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { storageStatePath } from "./e2e/global-setup";

// Review Queue Scale Closure v1: a separate, isolated Playwright project
// for the bounded-Review-Queue spec, on the same principle (and copied from
// the same shape) as playwright.onboarding.config.ts.
//
// That spec's whole subject is a review backlog *larger than one page*, so
// it has to create ~90 review items. The shared suite runs every spec
// against one database, and several of its Review Queue and Today specs
// legitimately assert on a near-empty queue ("1 card", "0 items still need
// review", "no wildlife activity yet today"). A spec whose job is to build
// a backlog cannot share a database with specs whose job is to observe an
// empty one -- so it gets its own, with its own port and runtime root, and
// playwright.config.ts excludes it by name.
//
// It keeps the shared suite's `globalSetup`, because it needs a signed-in
// Administrator on a normal, already-onboarded instance -- unlike
// onboarding.spec.ts, which needs the opposite.
const webRoot = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(webRoot, "..");
const configuredRuntimeRoot = process.env.MOCKINGBIRD_E2E_RUNTIME_ROOT?.trim();
if (!configuredRuntimeRoot) {
  throw new Error("Run browser checks through npm run test:e2e:review-queue so temporary data is isolated.");
}
const runtimeRoot = resolve(configuredRuntimeRoot);
const port = Number(process.env.MOCKINGBIRD_E2E_PORT ?? "8181");
const baseURL = `http://127.0.0.1:${port}`;
const databasePath = join(runtimeRoot, "mockingbird-review-queue-e2e.sqlite3").replace(/\\/g, "/");
const configuredChannel = process.env.MOCKINGBIRD_E2E_CHANNEL?.trim();
const localPythonCandidates =
  process.platform === "win32"
    ? [
        join(repositoryRoot, ".venv312", "Scripts", "python.exe"),
        join(repositoryRoot, ".venv", "Scripts", "python.exe"),
      ]
    : [
        join(repositoryRoot, ".venv312", "bin", "python"),
        join(repositoryRoot, ".venv", "bin", "python"),
      ];
const pythonExecutable =
  process.env.MOCKINGBIRD_E2E_PYTHON?.trim() ||
  localPythonCandidates.find(existsSync) ||
  "python";
const edgeIsInstalled =
  process.platform === "win32" &&
  [
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  ].some(existsSync);

export default defineConfig({
  testDir: "./e2e",
  testMatch: "review-queue-bounded-page.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  outputDir: join(runtimeRoot, "artifacts"),
  timeout: 45_000,
  expect: {
    timeout: 10_000,
  },
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL,
    headless: true,
    trace: "retain-on-failure",
    storageState: storageStatePath(runtimeRoot),
    ...(configuredChannel || edgeIsInstalled
      ? { channel: configuredChannel || "msedge" }
      : {}),
  },
  webServer: {
    command: `"${pythonExecutable}" -m uvicorn mockingbird.api.main:app --host 127.0.0.1 --port ${port}`,
    cwd: repositoryRoot,
    env: {
      ...process.env,
      MOCKINGBIRD_BACKUP_ROOT: join(runtimeRoot, "backups"),
      MOCKINGBIRD_DB_URL: `sqlite:///${databasePath}`,
      MOCKINGBIRD_MEDIA_ROOT: join(runtimeRoot, "media"),
      MOCKINGBIRD_WEB_DIST: join(webRoot, "dist"),
    },
    reuseExistingServer: false,
    timeout: 30_000,
    url: `${baseURL}/health`,
  },
});
