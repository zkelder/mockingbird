import { expect, test, type Page } from "@playwright/test";

// Calm Attention & Notifications v1 (see docs/calm-attention-
// notifications-v1-report.md). Mirrors place-story.spec.ts's house pattern:
// a synthetic, schema-shaped `/api/*` mock proves the presentation
// contract (toggles load/save, the calm Today summary line, the deep-link
// category mapping, phone-width usability) -- not the underlying selection/
// dedup/sync logic itself, which tests/test_calm_attention.py already
// covers with real seeded data.

async function completeSetup(page: Page) {
  await page.route("**/api/setup/state", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ completed: true, current_step: "done", updated_at: new Date().toISOString() }),
    }),
  );
}

const NOW = new Date().toISOString();

function defaultPreferences(overrides: Record<string, unknown> = {}) {
  return {
    discovery_enabled: true,
    insight_enabled: true,
    needs_help_enabled: true,
    observatory_health_enabled: true,
    browser_notifications_enabled: false,
    quiet_hours_enabled: false,
    quiet_hours_start_minute: 22 * 60,
    quiet_hours_end_minute: 7 * 60,
    updated_at: NOW,
    ...overrides,
  };
}

function alert(overrides: Record<string, unknown> = {}) {
  return {
    id: "alert-e2e-1",
    category: "insight",
    severity: "info",
    title: "Cardinals have been showing up more often lately",
    message: "Northern Cardinal has been appearing more often recently.",
    created_at: NOW,
    updated_at: NOW,
    read_at: null,
    dismissed_at: null,
    resolved_at: null,
    status: "unread",
    stream_id: null,
    stream_name: null,
    zone_id: null,
    zone_name: null,
    visit_id: null,
    source_id: null,
    action: { action_type: "open_place_story", story_kind: "regularity_change", taxon_label: "northern_cardinal" },
    attention_category: "insight",
    urgency: "digest",
    ...overrides,
  };
}

async function mockNotificationPreferences(page: Page, preferences: Record<string, unknown>) {
  await page.route("**/api/notification-preferences", (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(preferences) });
    }
    const updates = route.request().postDataJSON();
    return route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify({ ...preferences, ...updates }),
    });
  });
}

async function mockAlerts(page: Page, alerts: Array<Record<string, unknown>>) {
  await page.route("**/api/alerts/unread", (route) =>
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({ unread_count: alerts.length, recent: alerts }),
    }),
  );
  await page.route("**/api/alerts?*", (route) =>
    route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify({ items: alerts, next_offset: null }),
    }),
  );
}

// The first poll (`AlertsControl` mounts and polls immediately) returns
// nothing, seeding `seenAlertIdsRef`; the second poll (60s later, advanced
// via `page.clock`) returns `alertAfter` -- a genuinely *new* id, exactly
// the "new since last poll" condition `shouldDeliverForegroundNotification`
// requires (Phase 8: never re-notify for something already on screen the
// first time it was ever seen).
async function mockAlertsAppearingOnSecondPoll(page: Page, alertAfter: Record<string, unknown>) {
  let pollCount = 0;
  await page.route("**/api/alerts/unread", (route) => {
    pollCount += 1;
    const alerts = pollCount === 1 ? [] : [alertAfter];
    return route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({ unread_count: alerts.length, recent: alerts }),
    });
  });
}

// A minimal, real `Notification` stand-in -- installed before navigation
// via `addInitScript` so `AlertsControl`'s own `typeof Notification`/
// `Notification.permission`/`new Notification(...)` calls all observe it.
// `window.__deliveredNotifications` is what the tests below assert on.
async function mockGrantedNotificationPermission(page: Page) {
  await page.addInitScript(() => {
    (window as unknown as { __deliveredNotifications: Array<{ title: string; body?: string }> })
      .__deliveredNotifications = [];
    class FakeNotification {
      static permission = "granted";
      static requestPermission() {
        return Promise.resolve("granted" as NotificationPermission);
      }
      onclick: (() => void) | null = null;
      constructor(title: string, options?: NotificationOptions) {
        (window as unknown as { __deliveredNotifications: unknown[] }).__deliveredNotifications.push({
          title, body: options?.body,
        });
      }
      close() {}
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).Notification = FakeNotification;
  });
}

test("Today shows nothing when there is genuinely nothing unread", async ({ page }) => {
  await completeSetup(page);
  await mockAlerts(page, []);
  await page.goto("/");
  await expect(page.getByText("things worth noticing")).toHaveCount(0);
  await expect(page.getByText("1 thing worth noticing")).toHaveCount(0);
});

test("Today surfaces a calm count of unread attention items", async ({ page }) => {
  await completeSetup(page);
  await mockAlerts(page, [alert(), alert({ id: "alert-e2e-2" })]);
  await page.goto("/");
  await expect(page.getByRole("button", { name: "2 things worth noticing" })).toBeVisible();
});

test("clicking an insight alert opens Place Story already scoped to wildlife", async ({ page }) => {
  await completeSetup(page);
  await mockAlerts(page, [alert()]);
  await page.route("**/api/place/story*", (route) =>
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({
        generated_at: NOW, period_start_at: NOW, period_end_at: NOW,
        entries: [], has_more: false, next_offset: null, total_matched: 0, is_early_experience: false,
      }),
    }),
  );

  await page.goto("/");
  await page.getByRole("button", { name: "2 things worth noticing" }).or(
    page.getByRole("button", { name: "1 thing worth noticing" }),
  ).click();
  await expect(page).toHaveURL(/\/alerts/);

  const requestPromise = page.waitForRequest((request) => request.url().includes("/api/place/story?"));
  await page.getByRole("button", { name: "View in Place Story" }).first().click();
  const request = await requestPromise;
  await expect(page).toHaveURL(/\/place-story/);
  const url = new URL(request.url());
  // "regularity_change" maps to the "wildlife" group -- see App.tsx's
  // `placeStoryCategoryForKind`.
  expect(url.searchParams.getAll("kind").sort()).toEqual(
    ["diversity_milestone", "first_seen", "noteworthy_activity", "regularity_change", "return"].sort(),
  );
});

test("notification preferences load, render conservative defaults, and save a toggle change", async ({ page }) => {
  await completeSetup(page);
  await mockNotificationPreferences(page, defaultPreferences());

  await page.goto("/local-data");
  await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
  const insightToggle = page.getByLabel("Insights & summaries");
  await expect(insightToggle).toBeChecked();
  const browserRow = page.getByText("A live interruption on this device");
  await expect(browserRow).toBeVisible();
  // Conservative default (Phase 16): never pre-enabled -- proven regardless
  // of this test browser's own Notification-permission default (a real
  // per-environment/per-browser fact, not product behavior): whichever of
  // the three mutually exclusive states rendered, it must never be the
  // "already on" checkbox state.
  const permission = await page.evaluate(() =>
    typeof Notification === "undefined" ? "unsupported" : Notification.permission,
  );
  if (permission === "default") {
    await expect(page.getByRole("button", { name: "Enable browser notifications" })).toBeVisible();
  } else if (permission === "denied") {
    await expect(page.getByText("Blocked", { exact: false })).toBeVisible();
  } else if (permission === "granted") {
    await expect(page.getByLabel("Enabled")).not.toBeChecked();
  } else {
    await expect(page.getByText("Not supported in this browser")).toBeVisible();
  }

  const putPromise = page.waitForRequest(
    (request) => request.url().includes("/api/notification-preferences") && request.method() === "PUT",
  );
  await insightToggle.uncheck();
  const putRequest = await putPromise;
  expect(putRequest.postDataJSON()).toEqual({ insight_enabled: false });
});

test("quiet hours inputs only appear once quiet hours are enabled", async ({ page }) => {
  await completeSetup(page);
  await mockNotificationPreferences(page, defaultPreferences());

  await page.goto("/local-data");
  await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
  await expect(page.locator('input[type="time"]')).toHaveCount(0);

  const putPromise = page.waitForRequest(
    (request) => request.url().includes("/api/notification-preferences") && request.method() === "PUT",
  );
  await page.getByLabel("Quiet hours").check();
  const putRequest = await putPromise;
  expect(putRequest.postDataJSON()).toEqual({ quiet_hours_enabled: true });
});

test("the Alerts inbox stays usable and overflow-free at phone width", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 700 });
  await completeSetup(page);
  await mockAlerts(page, [alert()]);

  await page.goto("/alerts");
  await expect(page.getByRole("heading", { name: "Alerts Inbox" })).toBeVisible();
  await expect(page.getByText("Insight", { exact: true }).first()).toBeVisible();
  const bodyScrollWidth = await page.evaluate(() => document.body.scrollWidth);
  const viewportWidth = await page.evaluate(() => window.innerWidth);
  expect(bodyScrollWidth).toBeLessThanOrEqual(viewportWidth + 1); // +1: sub-pixel rounding tolerance
});

test("the Notifications settings card stays usable and overflow-free at phone width", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 700 });
  await completeSetup(page);
  await mockNotificationPreferences(page, defaultPreferences({ quiet_hours_enabled: true }));

  await page.goto("/local-data");
  await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible();
  await expect(page.getByLabel("New & unusual wildlife")).toBeVisible();
  await expect(page.locator('input[type="time"]')).toHaveCount(2);
  const bodyScrollWidth = await page.evaluate(() => document.body.scrollWidth);
  const viewportWidth = await page.evaluate(() => window.innerWidth);
  expect(bodyScrollWidth).toBeLessThanOrEqual(viewportWidth + 1); // +1: sub-pixel rounding tolerance
});

// ---------------------------------------------------------------------------
// Foreground browser-notification delivery (Phase 22 Decision B). These
// prove `shouldDeliverForegroundNotification`'s own decision logic end to
// end -- not only that Settings persists a toggle -- by installing a real
// `Notification` stand-in and a fake clock (this repo has no JS unit-test
// harness; a real running page is the most direct way to prove this without
// introducing one for a single module).
// ---------------------------------------------------------------------------

test("a new sustained health alert delivers a live browser notification when enabled", async ({ page }) => {
  await page.clock.install();
  await mockGrantedNotificationPermission(page);
  await completeSetup(page);
  await mockNotificationPreferences(page, defaultPreferences({ browser_notifications_enabled: true }));
  await mockAlertsAppearingOnSecondPoll(page, alert({
    id: "health-e2e-1", category: "monitoring", severity: "high",
    title: "Backyard camera has been offline for 20 minutes",
    message: "This enabled camera is unavailable after bounded local recovery attempts.",
    attention_category: "observatory_health", urgency: "immediate",
    action: { action_type: "open_stream", stream_id: "stream-e2e-1" },
  }));

  await page.goto("/");
  await expect.poll(() =>
    page.evaluate(() => (window as unknown as { __deliveredNotifications: unknown[] }).__deliveredNotifications.length),
  ).toBe(0); // first poll: nothing yet, and nothing delivered for the initial empty state

  await page.clock.fastForward(61_000); // advance past AlertsControl's 60s poll interval
  await expect.poll(() =>
    page.evaluate(() => (window as unknown as { __deliveredNotifications: unknown[] }).__deliveredNotifications.length),
  ).toBe(1);
  const delivered = await page.evaluate(
    () => (window as unknown as { __deliveredNotifications: Array<{ title: string }> }).__deliveredNotifications[0],
  );
  expect(delivered.title).toBe("Backyard camera has been offline for 20 minutes");
});

test("a new insight/discovery alert never delivers a live browser notification", async ({ page }) => {
  // Phase 3/9: even a genuinely new Discovery/Insight fact is `digest`
  // urgency, never `immediate` -- it must reach the badge/Attention Center
  // but never pop a live OS notification.
  await page.clock.install();
  await mockGrantedNotificationPermission(page);
  await completeSetup(page);
  await mockNotificationPreferences(page, defaultPreferences({ browser_notifications_enabled: true }));
  await mockAlertsAppearingOnSecondPoll(page, alert()); // urgency: "digest" (see the `alert()` helper's default)

  await page.goto("/");
  await page.clock.fastForward(61_000);
  await expect(page.getByRole("button", { name: "1 thing worth noticing" })).toBeVisible();
  const delivered = await page.evaluate(
    () => (window as unknown as { __deliveredNotifications: unknown[] }).__deliveredNotifications.length,
  );
  expect(delivered).toBe(0);
});

test("quiet hours suppress a live notification that would otherwise fire", async ({ page }) => {
  await page.clock.install();
  await mockGrantedNotificationPermission(page);
  await completeSetup(page);
  // A full-day quiet-hours window (0 minutes to 1439 minutes) guarantees
  // "now" falls inside it regardless of the real wall-clock time this test
  // happens to run at -- deterministic, not a timing-dependent flake.
  await mockNotificationPreferences(page, defaultPreferences({
    browser_notifications_enabled: true, quiet_hours_enabled: true,
    quiet_hours_start_minute: 0, quiet_hours_end_minute: 1439,
  }));
  await mockAlertsAppearingOnSecondPoll(page, alert({
    id: "health-e2e-2", category: "monitoring", severity: "high",
    attention_category: "observatory_health", urgency: "immediate",
  }));

  await page.goto("/");
  await page.clock.fastForward(61_000);
  await expect(page.getByRole("button", { name: "1 thing worth noticing" })).toBeVisible();
  const delivered = await page.evaluate(
    () => (window as unknown as { __deliveredNotifications: unknown[] }).__deliveredNotifications.length,
  );
  expect(delivered).toBe(0);
});

test("browser notifications stay off unless the user explicitly enabled them", async ({ page }) => {
  await page.clock.install();
  await mockGrantedNotificationPermission(page); // permission granted, but the preference itself is off
  await completeSetup(page);
  await mockNotificationPreferences(page, defaultPreferences({ browser_notifications_enabled: false }));
  await mockAlertsAppearingOnSecondPoll(page, alert({
    id: "health-e2e-3", category: "monitoring", severity: "high",
    attention_category: "observatory_health", urgency: "immediate",
  }));

  await page.goto("/");
  await page.clock.fastForward(61_000);
  await expect(page.getByRole("button", { name: "1 thing worth noticing" })).toBeVisible();
  const delivered = await page.evaluate(
    () => (window as unknown as { __deliveredNotifications: unknown[] }).__deliveredNotifications.length,
  );
  expect(delivered).toBe(0);
});
