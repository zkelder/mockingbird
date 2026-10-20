import { expect, test, type Page } from "@playwright/test";

// Year-over-Year Seasonality & Long-Term Place Memory v1 (see docs/
// year-over-year-seasonality-long-term-place-memory-v1-report.md).
// `YearOverYearCard` renders only facts the backend already computed
// (`GET /api/place/year-over-year`) -- this spec proves the presentation
// contract (calm phrasing, sparse-state honesty, no red/green judgment, no
// bare trend arrow), not the comparison's own truth computation, which is
// already covered by tests/test_year_over_year_comparison.py and tests/
// test_year_over_year_comparison_repository.py. Every scenario intercepts
// `/api/place/year-over-year` with a fully synthetic, schema-shaped
// response -- the same house pattern biodiversity-summary.spec.ts already
// uses.

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

function period(overrides: Record<string, unknown> = {}) {
  return {
    start_date: "2026-09-01",
    end_date: "2026-10-01",
    is_complete: true,
    usable_day_count: 20,
    monitored_seconds: 200_000,
    confirmed_wildlife_visit_count: 10,
    ...overrides,
  };
}

async function mockYearOverYear(page: Page, overrides: Record<string, unknown>) {
  const base = {
    generated_at: new Date().toISOString(),
    place: {
      policy_version: 1,
      current_period: period(),
      prior_period: period({ start_date: "2025-09-01", end_date: "2025-10-01" }),
      status: "insufficient_prior_history",
      overall_activity: null,
      association: null,
      information_class: "inferred",
    },
    notable_species_changes: [],
  };
  const body = { ...base, ...overrides };
  await page.route("**/api/place/year-over-year*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) }),
  );
}

test("a brand-new Place shows an honest, calm first-year message on the Place Report, and Today stays quiet", async ({ page }) => {
  await completeSetup(page);
  await mockYearOverYear(page, {});

  // Today omits the "long-term patterns will appear" placeholder (it is just
  // another empty state there); the Place Report keeps the honest sentence.
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Today in Your Yard" })).toBeVisible();
  await expect(page.locator(".year-over-year-card")).toHaveCount(0);

  await page.goto("/place-report");
  const card = page.locator(".year-over-year-card");
  await expect(card).toBeVisible();
  await expect(card.getByText("Compared with last year")).toBeVisible();
  await expect(card.getByText("Long-term patterns will appear here", { exact: false })).toBeVisible();
  await expect(card.getByText(/error/i)).toHaveCount(0);
});

test("a real, material increase renders calmly with the notable species below it", async ({ page }) => {
  await completeSetup(page);
  await mockYearOverYear(page, {
    place: {
      policy_version: 1,
      current_period: period(),
      prior_period: period({ start_date: "2025-09-01", end_date: "2025-10-01" }),
      status: "comparable",
      overall_activity: "higher",
      association: null,
      information_class: "inferred",
    },
    notable_species_changes: [
      {
        label: "northern_cardinal",
        display_name: "Northern Cardinal",
        category: "bird",
        is_species: true,
        status: "comparable",
        activity_direction: "higher",
        association: null,
        current_first_observed_date: null,
        prior_first_observed_date: null,
        first_observed_timing_status: "insufficient_data",
        first_observed_day_difference: null,
        first_observed_is_material: false,
      },
    ],
  });

  await page.goto("/");
  const card = page.locator(".year-over-year-card");
  await expect(card).toBeVisible();
  // "September 2026"/"September 2025" each appear twice on this card (the
  // meta-text period line, and again inside the composed prose sentence) --
  // .first() confirms presence without over-specifying which occurrence.
  await expect(card.getByText("September 2026", { exact: false }).first()).toBeVisible();
  await expect(card.getByText("September 2025", { exact: false }).first()).toBeVisible();
  await expect(card.getByText("More activity recorded")).toBeVisible();
  await expect(card.getByText("Northern Cardinal")).toBeVisible();
  await expect(card.getByText("observed higher often", { exact: false })).toBeVisible();
});

test("a genuinely similar period reads as similar, not as no data", async ({ page }) => {
  await completeSetup(page);
  await mockYearOverYear(page, {
    place: {
      policy_version: 1,
      current_period: period(),
      prior_period: period({ start_date: "2025-09-01", end_date: "2025-10-01" }),
      status: "no_material_difference",
      overall_activity: "similar",
      association: null,
      information_class: "inferred",
    },
  });

  await page.goto("/");
  const card = page.locator(".year-over-year-card");
  await expect(card).toBeVisible();
  await expect(card.getByText("Activity is similar to", { exact: false })).toBeVisible();
});

test("an in-progress current month reads as partial, not as a completed comparison", async ({ page }) => {
  await completeSetup(page);
  await mockYearOverYear(page, {
    place: {
      policy_version: 1,
      current_period: period({ is_complete: false }),
      prior_period: period({ start_date: "2025-09-01", end_date: "2025-10-01" }),
      status: "partial_period",
      overall_activity: null,
      association: null,
      information_class: "inferred",
    },
  });

  await page.goto("/");
  const card = page.locator(".year-over-year-card");
  await expect(card).toBeVisible();
  await expect(card.getByText("still in progress", { exact: false })).toBeVisible();
});

test("never shows a red/green judgment or a bare trend arrow", async ({ page }) => {
  await completeSetup(page);
  await mockYearOverYear(page, {
    place: {
      policy_version: 1,
      current_period: period(),
      prior_period: period({ start_date: "2025-09-01", end_date: "2025-10-01" }),
      status: "comparable",
      overall_activity: "lower",
      association: null,
      information_class: "inferred",
    },
  });

  await page.goto("/");
  const card = page.locator(".year-over-year-card");
  await expect(card).toBeVisible();
  await expect(card.getByText("Less activity recorded")).toBeVisible();
  // No bare arrow glyphs, no "declined"/"population" framing.
  await expect(card.getByText(/[↑↓▲▼]/)).toHaveCount(0);
  await expect(card.getByText(/declined|population/i)).toHaveCount(0);
});

test("the Place Report page shows the same year-over-year card", async ({ page }) => {
  await completeSetup(page);
  await mockYearOverYear(page, {
    place: {
      policy_version: 1,
      current_period: period(),
      prior_period: period({ start_date: "2025-09-01", end_date: "2025-10-01" }),
      status: "comparable",
      overall_activity: "higher",
      association: null,
      information_class: "inferred",
    },
  });

  await page.goto("/place-report");
  const card = page.locator(".year-over-year-card");
  await expect(card).toBeVisible();
  await expect(card.getByText("More activity recorded")).toBeVisible();
});

test("stays legible at a phone-width viewport", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await completeSetup(page);
  await mockYearOverYear(page, {
    place: {
      policy_version: 1,
      current_period: period(),
      prior_period: period({ start_date: "2025-09-01", end_date: "2025-10-01" }),
      status: "comparable",
      overall_activity: "higher",
      association: null,
      information_class: "inferred",
    },
    notable_species_changes: [
      {
        label: "northern_cardinal",
        display_name: "Northern Cardinal",
        category: "bird",
        is_species: true,
        status: "comparable",
        activity_direction: "higher",
        association: null,
        current_first_observed_date: null,
        prior_first_observed_date: null,
        first_observed_timing_status: "insufficient_data",
        first_observed_day_difference: null,
        first_observed_is_material: false,
      },
    ],
  });

  await page.goto("/");
  const card = page.locator(".year-over-year-card");
  await expect(card).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
