import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { storageStatePath } from "./e2e/global-setup";

const webRoot = dirname(fileURLToPath(import.meta.url));
const repositoryRoot = resolve(webRoot, "..");
const configuredRuntimeRoot = process.env.MOCKINGBIRD_E2E_RUNTIME_ROOT?.trim();
if (!configuredRuntimeRoot) {
  throw new Error("Run browser checks through npm run test:e2e so temporary data is isolated.");
}
const runtimeRoot = resolve(configuredRuntimeRoot);
const port = Number(process.env.MOCKINGBIRD_E2E_PORT ?? "8174");
const baseURL = `http://127.0.0.1:${port}`;
const databasePath = join(runtimeRoot, "mockingbird-e2e.sqlite3").replace(/\\/g, "/");
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
  // onboarding.spec.ts already runs -- exhaustively -- against its own
  // genuinely fresh instance via playwright.onboarding.config.ts (see
  // that spec file's own header comment: "separate from the shared
  // suite's already-configured instance"). This suite's new `globalSetup`
  // below pre-authenticates its shared instance for the other ~18 spec
  // files, which is directly incompatible with onboarding.spec.ts's own
  // "genuinely fresh, no administrator yet" premise -- exclude it here
  // rather than have the two configs silently fight over one file.
  // review-queue-bounded-page.spec.ts is excluded for the same reason, from
  // the other direction: it deliberately builds a review backlog larger than
  // one page, and several specs here assert on a near-empty queue. It runs
  // against its own instance via playwright.review-queue.config.ts. Review
  // Queue Scale Closure v1.
  // bounded-product-reads.spec.ts is excluded for the same reason again
  // (Remaining Performance P1 Closure v1): its subject is a MediaAsset
  // library larger than the windows the product pages read, and several
  // specs here assert on a near-empty one.
  testIgnore: [
    "**/onboarding.spec.ts",
    "**/review-queue-bounded-page.spec.ts",
    "**/bounded-product-reads.spec.ts",
  ],
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  outputDir: join(runtimeRoot, "artifacts"),
  timeout: 45_000,
  expect: {
    timeout: 10_000,
  },
  // Local Identity, Multi-User & Organization Access v1: this suite's
  // ~18 pre-existing spec files predate real authentication. `globalSetup`
  // bootstraps a real Administrator on this run's own isolated instance
  // once and marks onboarding complete; every test in every spec file
  // then starts already signed in via this shared `storageState`, with no
  // change needed to any of those files. See e2e/global-setup.ts.
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
