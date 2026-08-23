import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";

// Local Identity, Multi-User & Organization Access v1: the shared e2e
// suite's ~18 spec files all predate real authentication and assume they
// can act on the product directly. Rather than touch every one of them,
// this runs once before the whole suite (Playwright's own documented
// pattern for exactly this) and produces one `storageState` file every
// test in every spec file starts from -- a session cookie for a real,
// freshly-bootstrapped Administrator on this run's own isolated instance.
// The onboarding wizard's own "account" step is covered separately and
// far more thoroughly by e2e/onboarding.spec.ts against its own genuinely
// fresh instance; this setup exists only to unblock the *other* specs,
// which are about product features, not identity itself.

const ADMIN_LOGIN_IDENTITY = "e2e-admin";
const ADMIN_PASSWORD = "e2e-shared-suite-admin-password-1";
const HEALTH_CHECK_TIMEOUT_MS = 30_000;
const HEALTH_CHECK_INTERVAL_MS = 250;

export function storageStatePath(runtimeRoot: string): string {
  return join(runtimeRoot, "storage-state.json");
}

async function waitForServer(baseURL: string): Promise<void> {
  const deadline = Date.now() + HEALTH_CHECK_TIMEOUT_MS;
  let lastError: unknown;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${baseURL}/health`);
      if (response.ok) {
        return;
      }
    } catch (error) {
      lastError = error;
    }
    await new Promise((r) => setTimeout(r, HEALTH_CHECK_INTERVAL_MS));
  }
  throw new Error(`MockingBird did not become healthy before global setup's own deadline: ${String(lastError)}`);
}

function sessionCookieFrom(response: Response): { value: string; maxAgeSeconds: number } {
  // Node's fetch merges multiple Set-Cookie headers into one comma-joined
  // string on older runtimes; `getSetCookie()` (Node >= 18.something/undici)
  // is the reliable way to get them back apart. Fall back defensively.
  const rawCookies =
    typeof (response.headers as { getSetCookie?: () => string[] }).getSetCookie === "function"
      ? (response.headers as unknown as { getSetCookie: () => string[] }).getSetCookie()
      : [response.headers.get("set-cookie") ?? ""];
  const sessionCookie = rawCookies.find((cookie) => cookie.startsWith("mb_session="));
  if (!sessionCookie) {
    throw new Error(`No mb_session cookie in response (status ${response.status}): ${rawCookies.join(" | ")}`);
  }
  const value = sessionCookie.split(";")[0].split("=")[1];
  const maxAgeMatch = sessionCookie.match(/Max-Age=(\d+)/i);
  return { value, maxAgeSeconds: maxAgeMatch ? Number(maxAgeMatch[1]) : 60 * 60 * 24 * 30 };
}

export default async function globalSetup(): Promise<void> {
  const configuredRuntimeRoot = process.env.MOCKINGBIRD_E2E_RUNTIME_ROOT?.trim();
  if (!configuredRuntimeRoot) {
    // Mirrors playwright.config.ts's own guard -- this file is only ever
    // invoked through that config, which already enforces this.
    throw new Error("MOCKINGBIRD_E2E_RUNTIME_ROOT must be set before global setup runs.");
  }
  const runtimeRoot = resolve(configuredRuntimeRoot);
  const port = Number(process.env.MOCKINGBIRD_E2E_PORT ?? "8174");
  const baseURL = `http://127.0.0.1:${port}`;

  await waitForServer(baseURL);

  const bootstrapResponse = await fetch(`${baseURL}/api/setup/administrator`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      display_name: "E2E Administrator",
      login_identity: ADMIN_LOGIN_IDENTITY,
      password: ADMIN_PASSWORD,
    }),
  });
  if (bootstrapResponse.status !== 201) {
    throw new Error(
      `e2e global setup could not bootstrap the first Administrator (status ${bootstrapResponse.status}): ` +
        (await bootstrapResponse.text()),
    );
  }
  const { value: sessionToken, maxAgeSeconds } = sessionCookieFrom(bootstrapResponse);

  // Also mark onboarding itself complete, authenticated as the
  // Administrator just created (see `setup_mutation_allowed` -- once an
  // Administrator exists, only a signed-in Administrator may still change
  // setup state) -- so a spec navigating straight to an arbitrary route
  // sees the normal product shell, not the onboarding wizard.
  const finishSetupResponse = await fetch(`${baseURL}/api/setup/state`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Cookie: `mb_session=${sessionToken}` },
    body: JSON.stringify({ current_step: "done", completed: true }),
  });
  if (!finishSetupResponse.ok) {
    throw new Error(
      `e2e global setup could not mark onboarding complete (status ${finishSetupResponse.status}): ` +
        (await finishSetupResponse.text()),
    );
  }

  const path = storageStatePath(runtimeRoot);
  await mkdir(dirname(path), { recursive: true });
  await writeFile(
    path,
    JSON.stringify({
      cookies: [
        {
          name: "mb_session",
          value: sessionToken,
          domain: "127.0.0.1",
          path: "/",
          expires: Math.floor(Date.now() / 1000) + maxAgeSeconds,
          httpOnly: true,
          secure: false,
          sameSite: "Lax" as const,
        },
      ],
      origins: [],
    }),
    "utf-8",
  );
}
