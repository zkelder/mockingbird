import { expect, Page, test } from "@playwright/test";

// MockingBird Installable Local Product v1: first-run onboarding
// (docs/local-product-packaging-design.md), extended by Local Identity,
// Multi-User & Organization Access v1 with a new "account" step (see
// docs/local-identity-multi-user-contract.md "First-run administrator").
// Runs against its own isolated, genuinely fresh MockingBird instance (see
// playwright.onboarding.config.ts) -- separate from the shared suite's
// already-configured instance, and separate from the heavier real-camera/
// real-observation validation this milestone performs directly against the
// API and a real paired Camera Node (browser automation cannot supply real
// camera hardware).

const ADMIN_LOGIN_IDENTITY = "admin";
const ADMIN_PASSWORD = "correct horse battery staple";

async function signIn(page: Page, loginIdentity = ADMIN_LOGIN_IDENTITY, password = ADMIN_PASSWORD) {
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.getByLabel("Login identity").fill(loginIdentity);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
}

// Runs before the other tests below, in file order (this config uses one
// worker against one shared fresh instance): a fresh install has no
// Administrator account yet, so every route -- not just the dashboard --
// must show the wizard's own "account" step first. This is a deliberate
// behavior change from the wizard's pre-multi-user, dashboard-only gate:
// once routes can require a real signed-in session, a deep link during
// fresh install showing the normal app (with no way to sign in) would be a
// dead end rather than a harmless early look.
test("a direct deep link during a fresh install still reaches guided setup, not a dead end", async ({
  page,
}) => {
  await page.goto("/review");

  await expect(page.getByRole("heading", { name: "Welcome to MockingBird" })).toBeVisible();
});

test("a fresh install creates the first administrator, shows guided setup, persists progress across a reload, and finishing reaches the normal Dashboard", async ({
  page,
}) => {
  await page.goto("/");

  // Welcome: what MockingBird does, no developer vocabulary.
  await expect(page.getByRole("heading", { name: "Welcome to MockingBird" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "What MockingBird does" })).toBeVisible();
  const bodyText = await page.locator("body").innerText();
  for (const forbidden of ["uvicorn", "venv", "pip install", "npm run", "WSL"]) {
    expect(bodyText).not.toContain(forbidden);
  }
  // Lane C Sparse-State Honesty & First-Hour Narrative Closure v1: the
  // review-optional design shipped well before this wizard's own copy was
  // updated to match it -- this paragraph used to say a sighting "appears
  // in your Review Queue for you to confirm," implying Review Queue is the
  // normal destination for ordinary discovery. Today/Bird Log are.
  expect(bodyText).toContain("Today and Bird Log");
  expect(bodyText).not.toContain("appears in your Review Queue");
  await page.getByRole("button", { name: "Get started" }).click();

  // Account: the new first-run administrator step (Local Identity, Multi-
  // User & Organization Access v1) -- no default credentials, a real name/
  // login identity/password must be entered.
  await expect(page.getByRole("heading", { name: "Create your administrator account" })).toBeVisible();
  const createAccountButton = page.getByRole("button", { name: "Create account" });
  await expect(createAccountButton).toBeDisabled();
  await page.getByLabel("Your name").fill("Ada Admin");
  await page.getByLabel("Login identity").fill(ADMIN_LOGIN_IDENTITY);
  await page.getByLabel("Password").fill(ADMIN_PASSWORD);
  await createAccountButton.click();

  // Storage: local data location/usage/writability, no SQLite internals --
  // a folder to look at, never the database filename/engine itself. Only
  // reachable once signed in -- proves account creation left the browser
  // authenticated, not merely "account exists, now sign in again."
  await expect(page.getByRole("heading", { name: "Where MockingBird keeps your data" })).toBeVisible();
  await expect(page.getByText("Writable")).toBeVisible();
  const storageBodyText = await page.locator("body").innerText();
  expect(storageBodyText.toLowerCase()).not.toContain(".sqlite3");
  expect(storageBodyText.toLowerCase()).not.toContain("sqlite3");
  await page.getByRole("button", { name: "Continue" }).click();

  // Camera: the existing, unmodified guided Add Camera flow is embedded
  // directly -- proving composition, not a second implementation of it.
  await expect(page.getByRole("heading", { name: "Add Camera" })).toBeVisible();

  // A reload mid-wizard must resume at the saved step, not restart --
  // "close/reopen without losing configuration." Also proves the signed-in
  // session itself survives a reload (a cookie, not in-memory-only state).
  await page.reload();
  await expect(page.getByRole("heading", { name: "Add Camera" })).toBeVisible();

  // Finishing without a camera is an explicit, honest escape hatch (the
  // milestone does not require every step during first run); the app then
  // shows the normal product shell instead of the wizard. Labeled "Do this
  // later" (not "Discard") because nothing is actually discarded -- see
  // "Pairing recovery UX" in docs/camera-node-pairing-persistence-design.md.
  await page.getByRole("button", { name: "Do this later" }).click();
  await expect(page.getByRole("heading", { name: "Today in Your Yard" })).toBeVisible();

  // Onboarding must never reappear after completion, including on reload,
  // and the account menu now shows the signed-in Administrator.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Today in Your Yard" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Welcome to MockingBird" })).toHaveCount(0);
  await expect(page.getByText("Ada Admin")).toBeVisible();

  // First-run bootstrap must never be replayable once an Administrator
  // exists -- signing out returns to sign-in, never back to account setup.
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Create your administrator account" })).toHaveCount(0);
  await signIn(page);
  await expect(page.getByRole("heading", { name: "Today in Your Yard" })).toBeVisible();
});

// First-Run & Pairing Reliability v1
// (docs/camera-node-pairing-persistence-design.md). These target Add
// Camera directly at its own stable route (`/cameras/setup`, unaffected by
// whether onboarding itself is complete -- see navigation.ts) rather than
// re-walking the wizard above, so they stay independent of the tests'
// shared server/database and of each other's order. By this point in file
// order, setup is already complete (the test above finished it) and each
// test below runs in its own fresh browser context with no session, so it
// must sign in as the Administrator that test already created before
// reaching the camera-setup content. A real Camera Node pairing needs real
// device hardware that browser automation cannot supply (see the file
// header); Camera Node responses are mocked at the browser's own network
// boundary with `page.route`, exercising exactly the part only a real
// browser can prove: reload/resume UI behavior, never re-implementing the
// backend pairing-persistence contract already covered directly in
// tests/test_camera_node_pairing_persistence.py.

const FAKE_CAMERAS = [
  { camera_id: "cam-1", display_name: "Feeder view", status: "available", snapshot_supported: true, setup_hint: null, provider_type: "v4l2" },
];

function fakePairResponse() {
  return {
    pairing_token: "node-pair-fake-token-for-tests",
    node_id: "node-fake",
    display_name: "Backyard Camera Node",
    api_version: "v1",
    cameras: FAKE_CAMERAS,
    message: "Camera Node found and paired. Choose one advertised camera to continue setup.",
  };
}

function fakePendingSetup(overrides: Record<string, unknown> = {}) {
  return {
    pairing_token: "node-pair-fake-token-for-tests",
    status: "active",
    node_id: "node-fake",
    display_name: "Backyard Camera Node",
    api_version: "v1",
    cameras: FAKE_CAMERAS,
    selected_camera_id: "cam-1",
    camera_name: null,
    stream_name: null,
    zone_name: null,
    zone_type: null,
    polygon: null,
    sensitivity: null,
    monitoring_enabled: false,
    message: "Camera Node paired. Continue setup.",
    ...overrides,
  };
}

test("Camera name starts as a real editable default, never an empty field masquerading as filled", async ({ page }) => {
  await page.goto("/cameras/setup");
  await signIn(page);

  const cameraName = page.getByLabel("Camera name");
  // A real value in the box, not merely gray placeholder text sitting over
  // an empty required field -- see "Required-field UX".
  await expect(cameraName).toHaveValue("My camera");
  await expect(cameraName).not.toHaveValue("");
});

test("Finish is never silently disabled -- every missing prerequisite is named nearby", async ({ page }) => {
  await page.goto("/cameras/setup");
  await signIn(page);

  const finishButton = page.getByRole("button", { name: /^Finish/ });
  await expect(finishButton).toBeDisabled();
  const blockers = page.locator(".finish-blockers");
  await expect(blockers).toBeVisible();
  await expect(blockers).toContainText("Check the camera first.");
});

test("a paired Camera Node survives a reload: resumes at camera selection, never asks for another code", async ({ page }) => {
  await page.route("**/api/camera-nodes/pending-setup", (route) => {
    if (route.request().method() !== "GET") return route.continue();
    route.fulfill({ status: 200, json: fakePendingSetup() });
  });
  await page.route("**/api/camera-nodes/pair", (route) => route.fulfill({ status: 200, json: fakePairResponse() }));

  await page.goto("/cameras/setup");
  await signIn(page);

  // The resumable pairing is discovered on load alone -- no address/code
  // entry, no second "Pair Camera Node" click.
  await expect(page.getByText("Camera Node paired")).toBeVisible();
  await expect(page.getByLabel("Node address")).toHaveCount(0);
  await expect(page.getByLabel("Camera view")).toBeVisible();

  await page.reload();

  await expect(page.getByText("Camera Node paired")).toBeVisible();
  await expect(page.getByLabel("One-time pairing code")).toHaveCount(0);
});

test("a pairing that needs renewal explains why and offers one clear recovery action, preserving typed fields", async ({ page }) => {
  await page.route("**/api/camera-nodes/pending-setup", (route) => {
    if (route.request().method() !== "GET") return route.continue();
    route.fulfill({
      status: 200,
      json: fakePendingSetup({
        status: "needs_renewal",
        camera_name: "Backyard feeder camera",
        message: "Pairing needs to be renewed.",
      }),
    });
  });

  await page.goto("/cameras/setup");
  await signIn(page);

  // Shown twice by design: the dedicated banner explains it, and the same
  // fact also appears as a Finish-disabled reason -- exact text tells the
  // banner ("...renewed") apart from the blocker list item ("...renewed.").
  await expect(page.getByText("Pairing needs to be renewed", { exact: true })).toBeVisible();
  await expect(page.locator(".finish-blockers")).toContainText("Pairing needs to be renewed.");
  // Not framed as a first-time ask -- the recovery action is explicit and
  // singular, and already-entered setup (camera name) is not thrown away.
  await expect(page.getByRole("button", { name: "Renew pairing" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Pair Camera Node", exact: true })).toHaveCount(0);
  await expect(page.getByLabel("Camera name")).toHaveValue("Backyard feeder camera");
});
