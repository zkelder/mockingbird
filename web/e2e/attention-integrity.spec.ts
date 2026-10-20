import { expect, test, type APIRequestContext, type Browser, type Page } from "@playwright/test";

// Attention Integrity & Health Reliability v1.
//
// Alert read/dismiss is per signed-in user (schema 62): one person's "Mark
// read" or "Dismiss" must never change what another person sees, while the
// alert condition itself stays shared. The app shell has exactly one
// attention source, shared by both Alerts controls (mobile header and
// sidebar) and Today's "things worth noticing" line, so they can never
// disagree. Every real-backend test creates its own real (non-demo) Source
// and archives it afterwards, like the other real-Source specs.

const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

interface AlertRow {
  id: string;
  status: string;
  visit_id?: string | null;
}

async function importVisitOnRealSource(page: Page, name: string): Promise<{ visitId: string; sourceId: string }> {
  const created = await page.request.post("/api/sources", { data: { name: `${name} ${Date.now()}` } });
  expect(created.ok()).toBeTruthy();
  const { source, stream } = await created.json();
  const imported = await page.request.post("/api/media/import", {
    multipart: {
      file: { name: "attention-integrity.jpg", mimeType: "image/jpeg", buffer: Buffer.from(TINY_JPEG_BASE64, "base64") },
      stream_id: stream.id,
      subject_label: "unknown_animal",
    },
  });
  expect(imported.ok()).toBeTruthy();
  const { visit } = await imported.json();
  return { visitId: visit.id as string, sourceId: source.id as string };
}

async function archiveSource(page: Page, sourceId: string): Promise<void> {
  const archived = await page.request.patch(`/api/sources/${sourceId}`, { data: { archived: true } });
  expect(archived.ok()).toBeTruthy();
}

async function reviewAlertFor(request: APIRequestContext, visitId: string): Promise<AlertRow> {
  const response = await request.get("/api/alerts?category=review&page_size=50");
  expect(response.ok()).toBeTruthy();
  const items = (await response.json()).items as AlertRow[];
  const match = items.find((item) => item.visit_id === visitId);
  expect(match, `review alert for ${visitId}`).toBeTruthy();
  return match as AlertRow;
}

async function unreadCount(request: APIRequestContext): Promise<number> {
  const response = await request.get("/api/alerts/unread");
  expect(response.ok()).toBeTruthy();
  return (await response.json()).unread_count as number;
}

async function createUser(page: Page, role: "viewer" | "reviewer"): Promise<{ login: string; password: string }> {
  const login = `attention-${role}-${Date.now()}`;
  const password = `${role}-attention-password-1`;
  const created = await page.request.post("/api/admin/users", {
    data: { display_name: `Attention ${role}`, login_identity: login, password, role },
  });
  expect(created.status(), await created.text()).toBe(201);
  return { login, password };
}

async function signedInPage(browser: Browser, baseURL: string, login: string, password: string): Promise<Page> {
  const context = await browser.newContext({ baseURL, storageState: { cookies: [], origins: [] } });
  const page = await context.newPage();
  await page.goto("/");
  await page.getByLabel("Username").fill(login);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Today in Your Yard" })).toBeVisible();
  return page;
}

function badgeText(count: number): string {
  return count > 99 ? "99+" : String(count);
}

test("one user's read and dismiss never change another signed-in user's attention", async ({ page, browser, baseURL }) => {
  const { visitId, sourceId } = await importVisitOnRealSource(page, "Attention isolation");
  const reviewer = await createUser(page, "reviewer");
  const reviewerPage = await signedInPage(browser, baseURL as string, reviewer.login, reviewer.password);
  try {
    const alert = await reviewAlertFor(page.request, visitId);
    expect(alert.status).toBe("unread");
    expect((await reviewAlertFor(reviewerPage.request, visitId)).status).toBe("unread");
    const reviewerUnreadBefore = await unreadCount(reviewerPage.request);

    // The administrator marks it read through the real UI: Today's line and
    // the badge move together, from the one shared source.
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Today in Your Yard" })).toBeVisible();
    const adminUnreadBefore = await unreadCount(page.request);
    await expect(page.locator(".alerts-badge:visible")).toHaveText(badgeText(adminUnreadBefore));
    await page.goto("/alerts");
    await expect(page.getByRole("heading", { name: "Alerts Inbox" })).toBeVisible();
    await page.getByRole("button", { name: "Review", exact: true }).click();
    // Newest first: this test's own Visit alert is the top Review row.
    const row = page.locator(".alerts-inbox-list .alert-row").first();
    await expect(row.getByText("unread", { exact: true })).toBeVisible();
    await row.getByRole("button", { name: "Mark read" }).click();
    await expect(row.getByText("read", { exact: true })).toBeVisible();
    expect((await reviewAlertFor(page.request, visitId)).status).toBe("read");
    const adminUnreadAfter = await unreadCount(page.request);
    expect(adminUnreadAfter).toBe(adminUnreadBefore - 1);
    // The header badge picked up the mutation's own response -- no reload.
    if (adminUnreadAfter > 0) {
      await expect(page.locator(".alerts-badge:visible")).toHaveText(badgeText(adminUnreadAfter));
    } else {
      await expect(page.locator(".alerts-badge:visible")).toHaveCount(0);
    }

    // The reviewer's view is untouched by the administrator's read.
    expect((await reviewAlertFor(reviewerPage.request, visitId)).status).toBe("unread");
    expect(await unreadCount(reviewerPage.request)).toBe(reviewerUnreadBefore);
    await reviewerPage.reload();
    await expect(reviewerPage.locator(".alerts-badge:visible")).toHaveText(badgeText(reviewerUnreadBefore));
    await expect(reviewerPage.locator(".today-attention-summary")).toHaveText(
      reviewerUnreadBefore === 1 ? "1 thing worth noticing" : `${reviewerUnreadBefore} things worth noticing`,
    );

    // The reviewer dismisses it; the administrator's own "read" stands.
    const dismissed = await reviewerPage.request.post(`/api/alerts/${alert.id}/dismiss`);
    expect(dismissed.ok()).toBeTruthy();
    expect((await reviewAlertFor(reviewerPage.request, visitId)).status).toBe("dismissed");
    expect((await reviewAlertFor(page.request, visitId)).status).toBe("read");
  } finally {
    await reviewerPage.context().close();
    await archiveSource(page, sourceId);
  }
});

test("signing in as a different user never inherits the previous user's attention state", async ({ page, browser, baseURL }) => {
  const { sourceId } = await importVisitOnRealSource(page, "Attention account switch");
  const reviewer = await createUser(page, "reviewer");
  const viewer = await createUser(page, "viewer");
  const shared = await signedInPage(browser, baseURL as string, reviewer.login, reviewer.password);
  try {
    const reviewerUnread = await unreadCount(shared.request);
    expect(reviewerUnread).toBeGreaterThan(0);
    await expect(shared.locator(".alerts-badge:visible")).toHaveText(badgeText(reviewerUnread));

    await shared.getByRole("button", { name: "Sign out" }).click();
    await shared.getByLabel("Username").fill(viewer.login);
    await shared.getByLabel("Password").fill(viewer.password);
    await shared.getByRole("button", { name: "Sign in" }).click();
    await expect(shared.getByRole("heading", { name: "Today in Your Yard" })).toBeVisible();

    // A Viewer never sees Needs Help review work, so their count differs;
    // the shell must show theirs, not the reviewer's leftover state.
    const viewerUnread = await unreadCount(shared.request);
    expect(viewerUnread).toBeLessThan(reviewerUnread);
    if (viewerUnread > 0) {
      await expect(shared.locator(".alerts-badge:visible")).toHaveText(badgeText(viewerUnread));
    } else {
      await expect(shared.locator(".alerts-badge:visible")).toHaveCount(0);
      await expect(shared.locator(".today-attention-summary")).toHaveCount(0);
    }
  } finally {
    await shared.context().close();
    await archiveSource(page, sourceId);
  }
});

test("the app shell reads attention once per poll for both Alerts controls and Today", async ({ page }) => {
  await page.clock.install();
  let unreadRequests = 0;
  page.on("request", (request) => {
    if (new URL(request.url()).pathname === "/api/alerts/unread") unreadRequests += 1;
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Today in Your Yard" })).toBeVisible();
  expect(await page.locator(".alerts-control").count()).toBe(2);
  await expect.poll(() => unreadRequests).toBe(1);
  // Give any stray independent fetch a chance to show up before asserting
  // there was none.
  await page.waitForLoadState("networkidle");
  expect(unreadRequests).toBe(1);

  await page.clock.fastForward(61_000);
  await expect.poll(() => unreadRequests).toBe(2);
  await page.waitForLoadState("networkidle");
  expect(unreadRequests).toBe(2);
});

test("a model/runtime Observatory Health alert opens Doctor for an Administrator", async ({ page }) => {
  const healthAlert = {
    id: "model-runtime-e2e-1",
    category: "monitoring",
    severity: "warning",
    title: "Wildlife detection is unavailable",
    message: "No detector model bundle is installed. A Camera Node is configured, but the Observation Engine cannot start without a detector model bundle.",
    created_at: "2026-09-30T12:00:00Z",
    updated_at: "2026-09-30T12:00:00Z",
    status: "unread",
    action: { action_type: "open_doctor" },
    attention_category: "observatory_health",
    urgency: "in_app_only",
  };
  await page.route("**/api/alerts/unread", (route) =>
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({ unread_count: 1, recent: [healthAlert] }),
    }),
  );
  await page.route("**/api/alerts/model-runtime-e2e-1/read", (route) =>
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({ unread_count: 0, recent: [{ ...healthAlert, status: "read" }] }),
    }),
  );
  await page.goto("/");
  await page.locator(".alerts-button:visible").click();
  const drawer = page.getByRole("region", { name: "Recent alerts" });
  await expect(drawer.getByText("Observatory Health", { exact: false })).toBeVisible();
  await drawer.getByRole("button", { name: "Open Doctor" }).click();
  await expect(page).toHaveURL(/\/doctor$/);
  await expect(page.locator(".alerts-badge:visible")).toHaveCount(0);
});

test("MockingBird status says when alert reconciliation is failing", async ({ page }) => {
  await page.route("**/api/product/health", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.attention_sync = {
      status: "failing",
      running: true,
      poll_interval_seconds: 900,
      last_attempt_at: "2026-09-30T12:15:00Z",
      last_success_at: "2026-09-30T11:45:00Z",
      last_failure_at: "2026-09-30T12:15:00Z",
      last_error_code: "attention_sync_database_error",
      last_error_message: "Alert reconciliation could not read or write the local database, so alerts may be out of date.",
      consecutive_failure_count: 2,
      success_count: 4,
      failure_count: 2,
    };
    await route.fulfill({ response, json: body });
  });
  await page.goto("/");
  const panel = page.getByRole("region", { name: "MockingBird status" });
  await expect(panel.getByText(/Alert reconciliation could not read or write the local database/)).toBeVisible();
  await expect(panel.getByText(/Alerts were last reconciled/)).toBeVisible();
});
