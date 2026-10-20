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

// Foreground delivery needs two attention polls: the first seeds the
// shared attention source's "seen" set with nothing, the second (60s later,
// advanced via `page.clock`) returns `alertAfter` -- a genuinely *new* id,
// exactly the "new since last poll" condition
// `shouldDeliverForegroundNotification` requires (Phase 8: never re-notify
// for something already on screen the first time it was ever seen).
//
// Browser Suite Determinism & Demo-Boundary Closure v1 made every request
// return `[]` until the test has seen the first poll arrive and explicitly
// releases the alert; `expectSecondAttentionPoll` then waits for the Alerts
// badge, which the shared attention source sets in the same step that makes
// the delivery decision.
//
// Attention Integrity & Health Reliability v1: the app shell still mounts
// one `AlertsControl` in the mobile header and one in the sidebar (CSS shows
// one), plus `TodayAttentionSummary` on Today, but all three now read one
// shared `AttentionProvider` -- exactly one `/api/alerts/unread` and one
// preferences read per poll, and exactly one delivery per new alert.
async function mockAlertReleasedAfterFirstPoll(page: Page, alertAfter: Record<string, unknown>) {
  let released = false;
  let unreadResponses = 0;
  let preferenceResponses = 0;
  page.on("response", (response) => {
    if (response.url().includes("/api/alerts/unread")) unreadResponses += 1;
    if (response.url().includes("/api/notification-preferences")) preferenceResponses += 1;
  });
  await page.route("**/api/alerts/unread", (route) => {
    const alerts = released ? [alertAfter] : [];
    return route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({ unread_count: alerts.length, recent: alerts }),
    });
  });
  return {
    /** Opens Today and waits until the shared attention source's first
     * poll (its unread and preferences reads) has reached the page. Returns
     * the number of mounted Alerts controls (each shows the same badge). */
    async gotoTodayAndAwaitFirstPoll(): Promise<number> {
      await page.goto("/");
      await expect(page.getByRole("heading", { name: "Today in Your Yard" })).toBeVisible();
      const controls = await page.locator(".alerts-control").count();
      expect(controls).toBeGreaterThan(0);
      await expect.poll(() => unreadResponses >= 1 && preferenceResponses >= 1).toBe(true);
      return controls;
    },
    release() {
      released = true;
    },
    unreadResponseCount() {
      return unreadResponses;
    },
  };
}

async function expectSecondAttentionPoll(page: Page, controls: number) {
  await expect(page.locator(".alerts-badge")).toHaveText(Array(controls).fill("1"));
}

async function deliveredCount(page: Page): Promise<number> {
  return page.evaluate(
    () => (window as unknown as { __deliveredNotifications: unknown[] }).__deliveredNotifications.length,
  );
}

// A minimal, real `Notification` stand-in -- installed before navigation
// via `addInitScript` so `AlertsControl`'s own `typeof Notification`/
// `Notification.permission`/`new Notification(...)` calls all observe it.
// `window.__deliveredNotifications` is what the tests below assert on.
async function mockGrantedNotificationPermission(page: Page) {
  await page.addInitScript(() => {
    (window as unknown as { __deliveredNotifications: Array<{ title: string; body?: string; tag?: string }> })
      .__deliveredNotifications = [];
    class FakeNotification {
      static permission = "granted";
      static requestPermission() {
        return Promise.resolve("granted" as NotificationPermission);
      }
      onclick: (() => void) | null = null;
      constructor(title: string, options?: NotificationOptions) {
        (window as unknown as { __deliveredNotifications: unknown[] }).__deliveredNotifications.push({
          title, body: options?.body, tag: options?.tag,
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

const EMPTY_PLACE_STORY = {
  generated_at: NOW, period_start_at: NOW, period_end_at: NOW,
  entries: [], has_more: false, next_offset: null, total_matched: 0, is_early_experience: false,
};

async function openOnlyAlertFromToday(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "1 thing worth noticing" }).click();
  await expect(page).toHaveURL(/\/alerts/);
}

// Browser Suite Determinism & Demo-Boundary Closure v1: `openAlertAction`
// has two deliberate `open_place_story` paths. Calm Attention &
// Notifications v1 scoped a category-only insight to its Place Story group;
// Place Story Deep Dives & Representative Evidence v1 then routed an action
// that carries a precise `taxon_label` straight to that taxon's own Story.
// This test's fixture used to carry `taxon_label` while asserting the
// category-group path, so it exercised the newer route and failed. Each
// path is now pinned by its own test.
test("clicking a category-only insight alert opens Place Story already scoped to wildlife", async ({ page }) => {
  await completeSetup(page);
  await mockAlerts(page, [
    alert({ action: { action_type: "open_place_story", story_kind: "regularity_change" } }),
  ]);
  await page.route("**/api/place/story*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(EMPTY_PLACE_STORY) }),
  );

  await openOnlyAlertFromToday(page);

  const requestPromise = page.waitForRequest((request) => request.url().includes("/api/place/story?"));
  await page.getByRole("button", { name: "View in Place Story" }).first().click();
  const request = await requestPromise;
  await expect(page).toHaveURL(/\/place-story$/);
  const url = new URL(request.url());
  // "regularity_change" maps to the "wildlife" group -- see App.tsx's
  // `placeStoryCategoryForKind`.
  expect(url.searchParams.getAll("kind").sort()).toEqual(
    ["diversity_milestone", "first_seen", "noteworthy_activity", "regularity_change", "return"].sort(),
  );
  expect(url.searchParams.get("taxon")).toBeNull();
});

test("clicking a taxon-specific insight alert opens that taxon's own Place Story", async ({ page }) => {
  await completeSetup(page);
  await mockAlerts(page, [alert()]);
  await page.route("**/api/place/story*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(EMPTY_PLACE_STORY) }),
  );

  await openOnlyAlertFromToday(page);

  const requestPromise = page.waitForRequest((request) => request.url().includes("/api/place/story?"));
  await page.getByRole("button", { name: "View in Place Story" }).first().click();
  const request = await requestPromise;
  await expect(page).toHaveURL(/\/place-story\/taxon\/northern_cardinal$/);
  const url = new URL(request.url());
  expect(url.searchParams.get("taxon")).toBe("northern_cardinal");
  expect(url.searchParams.getAll("kind")).toEqual([]);
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
  const alerts = await mockAlertReleasedAfterFirstPoll(page, alert({
    id: "health-e2e-1", category: "monitoring", severity: "high",
    title: "Backyard camera has been offline for 20 minutes",
    message: "This enabled camera is unavailable after bounded local recovery attempts.",
    attention_category: "observatory_health", urgency: "immediate",
    action: { action_type: "open_stream", stream_id: "stream-e2e-1" },
  }));

  const controls = await alerts.gotoTodayAndAwaitFirstPoll();
  expect(await deliveredCount(page)).toBe(0); // nothing delivered for the initial empty state

  alerts.release();
  await page.clock.fastForward(61_000); // advance past the shared attention source's 60s poll interval
  await expectSecondAttentionPoll(page, controls);
  await expect.poll(() => deliveredCount(page)).toBe(1);
  const delivered = await page.evaluate(
    () =>
      (window as unknown as { __deliveredNotifications: Array<{ title: string; tag?: string }> })
        .__deliveredNotifications,
  );
  // Exactly one delivery -- no longer one per mounted Alerts control.
  expect(delivered).toHaveLength(1);
  expect(delivered[0].tag).toBe("health-e2e-1");
  expect(delivered[0].title).toBe("Backyard camera has been offline for 20 minutes");
  // Two polls in total for the whole shell (initial + one interval), not
  // one per consumer.
  expect(alerts.unreadResponseCount()).toBe(2);
});

test("a new insight/discovery alert never delivers a live browser notification", async ({ page }) => {
  // Phase 3/9: even a genuinely new Discovery/Insight fact is `digest`
  // urgency, never `immediate` -- it must reach the badge/Attention Center
  // but never pop a live OS notification.
  await page.clock.install();
  await mockGrantedNotificationPermission(page);
  await completeSetup(page);
  await mockNotificationPreferences(page, defaultPreferences({ browser_notifications_enabled: true }));
  const alerts = await mockAlertReleasedAfterFirstPoll(page, alert()); // urgency: "digest" (see the `alert()` helper's default)

  const controls = await alerts.gotoTodayAndAwaitFirstPoll();
  alerts.release();
  await page.clock.fastForward(61_000);
  // The alert reached the Attention Center badge, so the second poll -- and
  // its delivery decision -- really ran before this check.
  await expectSecondAttentionPoll(page, controls);
  expect(await deliveredCount(page)).toBe(0);
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
  const alerts = await mockAlertReleasedAfterFirstPoll(page, alert({
    id: "health-e2e-2", category: "monitoring", severity: "high",
    attention_category: "observatory_health", urgency: "immediate",
  }));

  const controls = await alerts.gotoTodayAndAwaitFirstPoll();
  alerts.release();
  await page.clock.fastForward(61_000);
  // The alert reached the Attention Center badge, so the second poll -- and
  // its delivery decision -- really ran before this check.
  await expectSecondAttentionPoll(page, controls);
  expect(await deliveredCount(page)).toBe(0);
});

test("browser notifications stay off unless the user explicitly enabled them", async ({ page }) => {
  await page.clock.install();
  await mockGrantedNotificationPermission(page); // permission granted, but the preference itself is off
  await completeSetup(page);
  await mockNotificationPreferences(page, defaultPreferences({ browser_notifications_enabled: false }));
  const alerts = await mockAlertReleasedAfterFirstPoll(page, alert({
    id: "health-e2e-3", category: "monitoring", severity: "high",
    attention_category: "observatory_health", urgency: "immediate",
  }));

  const controls = await alerts.gotoTodayAndAwaitFirstPoll();
  alerts.release();
  await page.clock.fastForward(61_000);
  // The alert reached the Attention Center badge, so the second poll -- and
  // its delivery decision -- really ran before this check.
  await expectSecondAttentionPoll(page, controls);
  expect(await deliveredCount(page)).toBe(0);
});
