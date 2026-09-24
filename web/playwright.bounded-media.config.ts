import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { storageStatePath } from "./e2e/global-setup";

// Remaining Performance P1 Closure v1: a separate, isolated Playwright
// project for the bounded-product-reads spec, on exactly the same principle
// (and copied from the same shape) as playwright.review-queue.config.ts.
//
// That spec's whole subject is a MediaAsset library *larger than the
// windows the pages read*, so it has to import well over a hundred assets.
// The shared suite runs every spec against one database, and several of its
// specs legitimately assert on a near-empty library and a near-empty queue.
// A spec whose job is to build a library cannot share a database with specs
// whose job is to observe an empty one -- so it gets its own, with its own
// port and runtime root, and playwright.config.ts excludes it by name.
//
// It keeps the shared suite's `globalSetup`, because it needs a signed-in
// Administrator on a normal, already-onboarded instance -- unlike
// onboarding.spec.ts, which needs the opposite.
const webRoot = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(webRoot, "..");
const configuredRuntimeRoot = process.env.MOCKINGBIRD_E2E_RUNTIME_ROOT?.trim();
if (!configuredRuntimeRoot) {
  throw new Error("Run browser checks through npm run test:e2e:bounded-media so temporary data is isolated.");
}
const runtimeRoot = resolve(configuredRuntimeRoot);
const port = Number(process.env.MOCKINGBIRD_E2E_PORT ?? "8182");
const baseURL = `http://127.0.0.1:${port}`;
const databasePath = join(runtimeRoot, "mockingbird-bounded-media-e2e.sqlite3").replace(/\\/g, "/");
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
  testMatch: "bounded-product-reads.spec.ts",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  outputDir: join(runtimeRoot, "artifacts"),
  timeout: 90_000,
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
