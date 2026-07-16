import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

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
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  outputDir: join(runtimeRoot, "artifacts"),
  timeout: 45_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL,
    headless: true,
    trace: "retain-on-failure",
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
