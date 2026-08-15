import { expect, test, type Page } from "@playwright/test";

// Report-first Today Dashboard (Product Experience / UI Cohesion v1 Phase
// 1). `TodayReportPanel` renders only facts already computed by the
// existing, hardened Place Activity Report backend (`POST
// /api/analytics/place-activity-report`, see
// docs/place-activity-report-contract.md) -- this spec proves the
// presentation contract (species/visit counts, activity timing, busiest
// Zone, honest wording, a designed empty state, and a quiet review
// affordance that never dominates the page), not the report's own truth
// computation, which is already covered by the backend's own test suite.
//
// The demo-seeded e2e fixture database has no Visits dated "today" (its
// seed content uses fixed historical timestamps), so every scenario here
// intercepts `/api/analytics/place-activity-report` with a fully synthetic,
// schema-shaped response -- the same house pattern
// dashboard-live-camera-ownership.spec.ts already uses for its own
// backend-shaped fixtures. `/api/dashboard/summary` passes through real
// except where a scenario needs a specific, deterministic
// `headline.configured_stream_count`/`monitored_stream_count` combination.

async function completeSetup(page: Page) {
  await page.route("**/api/setup/state", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        completed: true,
        current_step: "done",
        updated_at: new Date().toISOString(),
      }),
    }),
  );
}

async function mockPlaceActivityReport(page: Page, overrides: Record<string, unknown>) {
  const now = new Date();
  const base = {
    period_start_at: new Date(now.getTime() - 24 * 3600 * 1000).toISOString(),
    period_end_at: now.toISOString(),
    timezone_name: "UTC",
    generated_at: now.toISOString(),
    total_visit_count: 0,
    confirmed_wildlife_visit_count: 0,
    provisional_wildlife_visit_count: 0,
    unresolved_visit_count: 0,
    non_wildlife_visit_count: 0,
    excluded_visit_count: 0,
    confirmed_species_unresolved_visit_count: 0,
    wildlife_visit_count: 0,
    distinct_taxa_count: 0,
    distinct_species_count: 0,
    taxa: [] as unknown[],
    first_activity_at: null,
    last_activity_at: null,
    activity_by_zone: [] as unknown[],
    busiest_zone: null,
    activity_by_hour: Array.from({ length: 24 }, (_, hour) => ({ hour, wildlife_visit_count: 0 })),
    coverage: {
      period_seconds: 86_400,
      monitored_seconds: 86_400,
      coverage_ratio: 1,
      history_available_from: new Date(now.getTime() - 30 * 24 * 3600 * 1000).toISOString(),
      history_is_partial: false,
      gaps: [] as unknown[],
      gaps_truncated: false,
    },
    warnings: [
      "Visits are activity sessions, not estimates of unique animals. The same animal may create more than one Visit if it leaves and returns.",
    ],
  };
  const body = { ...base, ...overrides };
  await page.route("**/api/analytics/place-activity-report", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) }),
  );
}

async function mockDashboardHeadline(
  page: Page,
  headlineOverrides: Record<string, unknown>,
) {
  await page.route("**/api/dashboard/summary", async (route) => {
    const real = await page.request.get("/api/dashboard/summary");
    const body = await real.json();
    Object.assign(body.headline, headlineOverrides);
    await route.fulfill({ status: real.status(), contentType: "application/json", body: JSON.stringify(body) });
  });
}

function activityByHour(counts: Record<number, number>) {
  return Array.from({ length: 24 }, (_, hour) => ({ hour, wildlife_visit_count: counts[hour] ?? 0 }));
}

test("Today's report shows species, visit counts, activity timing, and the busiest area without claiming unique animals", async ({
  page,
}) => {
  await completeSetup(page);
  const lastVisitAt = new Date().toISOString();
  await mockPlaceActivityReport(page, {
    total_visit_count: 15,
    confirmed_wildlife_visit_count: 15,
    wildlife_visit_count: 15,
    distinct_taxa_count: 3,
    distinct_species_count: 3,
    last_activity_at: lastVisitAt,
    first_activity_at: new Date(Date.now() - 5 * 3600 * 1000).toISOString(),
    taxa: [
      {
        label: "northern_cardinal",
        display_name: "Northern Cardinal",
        category: "bird",
        is_species: true,
        confirmed_visit_count: 6,
        provisional_visit_count: 0,
        total_visit_count: 6,
        first_activity_at: lastVisitAt,
        last_activity_at: lastVisitAt,
      },
      {
        label: "carolina_wren",
        display_name: "Carolina Wren",
        category: "bird",
        is_species: true,
        confirmed_visit_count: 5,
        provisional_visit_count: 0,
        total_visit_count: 5,
        first_activity_at: lastVisitAt,
        last_activity_at: lastVisitAt,
      },
      {
        label: "house_finch",
        display_name: "House Finch",
        category: "bird",
        is_species: true,
        confirmed_visit_count: 4,
        provisional_visit_count: 0,
        total_visit_count: 4,
        first_activity_at: lastVisitAt,
        last_activity_at: lastVisitAt,
      },
    ],
    activity_by_zone: [
      { zone_id: "zone-feeder-1", zone_name: "Backyard feeder", wildlife_visit_count: 14 },
      { zone_id: null, zone_name: "No Zone", wildlife_visit_count: 1 },
    ],
    busiest_zone: { zone_id: "zone-feeder-1", zone_name: "Backyard feeder", wildlife_visit_count: 14 },
    activity_by_hour: activityByHour({ 7: 9, 14: 6 }),
  });

  await page.goto("/");
  const reportPanel = page.locator("section.today-report");
  await expect(reportPanel).toBeVisible();

  // Headline: species count and a "wildlife visits" count -- never a claim
  // of unique animals ("34 animals").
  await expect(reportPanel.getByText("3", { exact: true })).toBeVisible();
  await expect(reportPanel.getByText("species", { exact: true })).toBeVisible();
  await expect(reportPanel.getByText("15", { exact: true })).toBeVisible();
  await expect(reportPanel.getByText("wildlife visits", { exact: true })).toBeVisible();
  await expect(page.getByText(/15\s+animals/)).toHaveCount(0);
  await expect(page.getByText("unique animal", { exact: false })).toHaveCount(0);

  // Species / top visitors, ranked by Visit count (already sorted by the
  // backend -- this only renders the given order).
  const speciesList = reportPanel.locator(".today-report-species-list li");
  await expect(speciesList).toHaveCount(3);
  await expect(speciesList.nth(0)).toContainText("Northern Cardinal");
  await expect(speciesList.nth(0)).toContainText("6 visits");
  await expect(speciesList.nth(1)).toContainText("Carolina Wren");
  await expect(speciesList.nth(1)).toContainText("5 visits");
  await expect(speciesList.nth(2)).toContainText("House Finch");
  await expect(speciesList.nth(2)).toContainText("4 visits");
  // No per-row "Likely" nagging on ordinary confirmed species rows.
  await expect(reportPanel.getByText("Likely Northern Cardinal")).toHaveCount(0);

  // Activity timing: the single busiest hour bucket (7:00-7:59 -> "7–8 AM"),
  // never a fabricated multi-hour "peak window."
  await expect(reportPanel.getByText("Most active")).toBeVisible();
  await expect(reportPanel.getByText("7–8 AM")).toBeVisible();

  // Busiest area, in plain human-facing Zone wording -- no internal IDs.
  await expect(reportPanel.getByText("Busiest area")).toBeVisible();
  await expect(reportPanel.getByText("Backyard feeder")).toBeVisible();
  await expect(reportPanel.getByText("14 visits")).toBeVisible();
  await expect(reportPanel.getByText("zone-feeder-1")).toHaveCount(0);

  // Recent context, shown sparingly.
  await expect(reportPanel.getByText("Last visit", { exact: false })).toBeVisible();

  // Healthy coverage stays quiet/secondary -- a small pill, not a warning.
  await expect(reportPanel.getByText("Fully observed today")).toBeVisible();
});

test("unresolved and provisional activity stays a quiet affordance, never the center of the report", async ({
  page,
}) => {
  await completeSetup(page);
  await mockPlaceActivityReport(page, {
    total_visit_count: 9,
    confirmed_wildlife_visit_count: 3,
    provisional_wildlife_visit_count: 5,
    unresolved_visit_count: 1,
    wildlife_visit_count: 8,
    distinct_taxa_count: 1,
    distinct_species_count: 1,
    taxa: [
      {
        label: "northern_cardinal",
        display_name: "Northern Cardinal",
        category: "bird",
        is_species: true,
        confirmed_visit_count: 3,
        provisional_visit_count: 5,
        total_visit_count: 8,
        first_activity_at: new Date().toISOString(),
        last_activity_at: new Date().toISOString(),
      },
    ],
  });

  await page.goto("/");
  const reportPanel = page.locator("section.today-report");
  await expect(reportPanel).toBeVisible();

  // Truthful, but a single small link -- not a dominant warning section.
  const reviewAffordance = reportPanel.getByRole("button", { name: "6 items worth reviewing" });
  await expect(reviewAffordance).toBeVisible();

  // The retired anti-patterns must not reappear anywhere on the page.
  await expect(page.getByRole("heading", { name: "Likely today" })).toHaveCount(0);
  await expect(page.getByText("AI suggestion")).toHaveCount(0);
  await expect(page.locator(".dashboard-likely-today")).toHaveCount(0);
  await expect(page.locator(".dashboard-needs-review")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Needs your help" })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Current animal candidates" })).toHaveCount(0);

  // The affordance still leads to the real Review Queue.
  await reviewAffordance.click();
  await expect(page).toHaveURL(/\/review$/);
  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();
});

test("a quiet, intentional empty state appears when there is no wildlife activity yet today", async ({
  page,
}) => {
  await completeSetup(page);
  await mockDashboardHeadline(page, { monitored_stream_count: 1, configured_stream_count: 1 });
  await mockPlaceActivityReport(page, {});

  await page.goto("/");
  const reportPanel = page.locator("section.today-report");
  await expect(reportPanel).toBeVisible();

  await expect(reportPanel.getByText("No wildlife visits yet today")).toBeVisible();
  await expect(reportPanel.getByText("MockingBird is watching this place", { exact: false })).toBeVisible();
  // Not a blank analytics shell -- the rest of the page still renders.
  await expect(page.getByRole("heading", { name: "Today in Your Yard" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Best moments" })).toBeVisible();
});

test("Dashboard's real request to the Place Activity Report endpoint succeeds against the real backend", async ({
  page,
}) => {
  // No route interception here, unlike every other scenario in this file --
  // this proves the frontend's actual `todayLocalRange()` request body is
  // one the real, unmodified backend contract accepts (catches a malformed
  // ISO string or a timezone edge case none of the mocked scenarios could).
  // The demo-seeded fixture database has no Visits dated "today," so a
  // sparse response is the correct, expected real answer here.
  await completeSetup(page);
  const [response] = await Promise.all([
    page.waitForResponse(
      (candidate) =>
        candidate.url().includes("/api/analytics/place-activity-report") &&
        candidate.request().method() === "POST",
    ),
    page.goto("/"),
  ]);

  expect(response.ok()).toBeTruthy();
  const payload = await response.json();
  expect(typeof payload.wildlife_visit_count).toBe("number");
  expect(Array.isArray(payload.taxa)).toBe(true);
  expect(Array.isArray(payload.activity_by_hour)).toBe(true);
  expect(payload.activity_by_hour).toHaveLength(24);
  expect(payload.coverage).toBeTruthy();

  await expect(page.locator("section.today-report")).toBeVisible();
});

test("Today's report stays readable and free of horizontal overflow at phone width", async ({ page }) => {
  await completeSetup(page);
  await mockPlaceActivityReport(page, {
    total_visit_count: 6,
    confirmed_wildlife_visit_count: 6,
    wildlife_visit_count: 6,
    distinct_taxa_count: 2,
    distinct_species_count: 2,
    last_activity_at: new Date().toISOString(),
    first_activity_at: new Date().toISOString(),
    taxa: [
      {
        label: "northern_cardinal",
        display_name: "Northern Cardinal",
        category: "bird",
        is_species: true,
        confirmed_visit_count: 4,
        provisional_visit_count: 0,
        total_visit_count: 4,
        first_activity_at: new Date().toISOString(),
        last_activity_at: new Date().toISOString(),
      },
      {
        label: "carolina_wren",
        display_name: "Carolina Wren",
        category: "bird",
        is_species: true,
        confirmed_visit_count: 2,
        provisional_visit_count: 0,
        total_visit_count: 2,
        first_activity_at: new Date().toISOString(),
        last_activity_at: new Date().toISOString(),
      },
    ],
    activity_by_zone: [{ zone_id: "zone-feeder-1", zone_name: "Backyard feeder", wildlife_visit_count: 6 }],
    busiest_zone: { zone_id: "zone-feeder-1", zone_name: "Backyard feeder", wildlife_visit_count: 6 },
    activity_by_hour: activityByHour({ 8: 6 }),
  });

  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");

  const reportPanel = page.locator("section.today-report");
  await expect(reportPanel).toBeVisible();
  await expect(reportPanel.locator(".today-report-species-list li").first()).toBeVisible();

  const hasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  expect(hasHorizontalOverflow).toBe(false);

  // The report stays above camera/diagnostic content on a narrow viewport.
  const reportTop = await reportPanel.boundingBox();
  const liveOverview = page.locator(".camera-overview-panel").first();
  if (await liveOverview.count()) {
    const liveTop = await liveOverview.boundingBox();
    if (reportTop && liveTop) {
      expect(reportTop.y).toBeLessThan(liveTop.y);
    }
  }
});
