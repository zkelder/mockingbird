import { spawn } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const webRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const runtimeRoot = await mkdtemp(join(tmpdir(), "mockingbird-e2e-"));
const playwrightCli = join(webRoot, "node_modules", "playwright", "cli.js");

let exitCode = 1;
try {
  const runner = spawn(process.execPath, [playwrightCli, "test"], {
    cwd: webRoot,
    env: {
      ...process.env,
      MOCKINGBIRD_E2E_RUNTIME_ROOT: runtimeRoot,
    },
    stdio: "inherit",
  });

  exitCode = await new Promise((resolve, reject) => {
    runner.once("error", reject);
    runner.once("exit", (code) => resolve(code ?? 1));
  });
} finally {
  // The Playwright process has stopped its app server, so Windows can release the SQLite file.
  await rm(runtimeRoot, { force: true, recursive: true, maxRetries: 4, retryDelay: 100 });
}

process.exitCode = exitCode;
