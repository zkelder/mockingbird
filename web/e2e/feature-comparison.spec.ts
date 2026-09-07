import { expect, test, type Page } from "@playwright/test";

// Place Feature Comparison & Habitat Outcomes v1 (see docs/place-feature-
// comparison-habitat-outcomes-v1-contract.md). Proves the presentation
// contract for the new bounded, Place-wide comparison page against
// synthetic, schema-shaped responses -- the same house pattern
// feature-story.spec.ts/place-features.spec.ts already use -- not the
// underlying comparison computation itself, which
// tests/test_place_feature_comparison.py and its product-shaped scenario
// already cover with real seeded data and real HTTP.

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

function feature(overrides: Record<string, unknown> = {}) {
  return {
    id: "feature-comparison-e2e-1",
    feature_type: "feeder",
    name: "Sunflower Feeder",
    note: null,
    is_active: true,
    installed_date: "2026-06-01",
    removed_date: null,
    source_id: "source-1",
    zone_id: "zone-1",
    feeder_food_type: null,
    information_class: "reviewed",
    provenance: "user_manual_entry",
    created_at: NOW,
    updated_at: NOW,
    observation_links: [
      {
        id: "link-1", source_id: "source-1", source_name: "Patio Camera", source_archived: false,
        zone_id: "zone-1", zone_name: "Feeder Zone", created_at: NOW,
      },
    ],
    ...overrides,
  };
}

function changeEventWithComparison(overrides: Record<string, unknown> = {}) {
  return {
    event: {
      id: "change-1", feature_id: "feature-comparison-e2e-1", event_type: "added", effective_date: "2026-06-01",
      note: null, prior_value: null, new_value: null, information_class: "reviewed",
      provenance: "user_manual_entry", created_at: NOW, updated_at: NOW,
    },
    comparison: {
      maturity: "comparable", window_days: 7, pre_start: "2026-05-25", post_end: "2026-06-08",
      status: "more_common_under_condition", presence_days_in_condition: 6, usable_days_in_condition: 7,
      presence_days_out_of_condition: 1, usable_days_out_of_condition: 7,
    },
    environmental_comparison: null,
    ...overrides,
  };
}

function featureRow(overrides: Record<string, unknown> = {}) {
  return {
    feature: feature(),
    recent_yield: {
      confirmed_wildlife_visit_count: 12, distinct_taxon_count: 3, monitored_seconds: 36000,
      visits_per_monitored_hour: 1.2, data_sufficient: true, window_days: 7,
    },
    latest_change: changeEventWithComparison(),
    representative_evidence: null,
    ...overrides,
  };
}

function overview(overrides: Record<string, unknown> = {}) {
  return {
    generated_at: NOW,
    features: [featureRow()],
    // Empty by default so most tests exercise only the "Compare Features"
    // section unambiguously; tests covering "Habitat Change Outcomes"
    // populate this explicitly.
    change_outcomes: [],
    ...overrides,
  };
}

async function mockComparisonApi(page: Page, body: Record<string, unknown> = overview()) {
  await page.route("**/api/place/feature-comparison", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) }),
  );
}

test("direct navigation renders the comparison page with a Feature row", async ({ page }) => {
  await completeSetup(page);
  await mockComparisonApi(page);

  await page.goto("/place-report/compare");
  await expect(page.getByRole("heading", { name: "Compare Features", level: 1 })).toBeVisible();
  await expect(page.getByText("Sunflower Feeder", { exact: true })).toBeVisible();
  await expect(page.getByText("Enough evidence to compare")).toBeVisible();
  await expect(
    page.getByText("Confirmed wildlife activity was higher in the 7-day windows after this change than before."),
  ).toBeVisible();
});

test("reload keeps the comparison page reachable", async ({ page }) => {
  await completeSetup(page);
  await mockComparisonApi(page);

  await page.goto("/place-report/compare");
  await expect(page.getByRole("heading", { name: "Compare Features", level: 1 })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Compare Features", level: 1 })).toBeVisible();
});

test("an empty Place shows an honest, calm sparse state -- never an error", async ({ page }) => {
  await completeSetup(page);
  await mockComparisonApi(page, overview({ features: [], change_outcomes: [] }));

  await page.goto("/place-report/compare");
  await expect(page.getByText("Record a Feature", { exact: false })).toBeVisible();
  await expect(page.getByText("No comparable changes yet")).toBeVisible();
  await expect(page.getByText(/something went wrong/i)).toHaveCount(0);
});

test("a Feature with insufficient monitoring stays visible with an honest status", async ({ page }) => {
  await completeSetup(page);
  await mockComparisonApi(
    page,
    overview({
      features: [
        featureRow({
          feature: feature({ id: "sparse-feature", name: "New Nest Box", feature_type: "nest_box" }),
          recent_yield: {
            confirmed_wildlife_visit_count: 0, distinct_taxon_count: 0, monitored_seconds: 1800,
            visits_per_monitored_hour: null, data_sufficient: false, window_days: 7,
          },
          latest_change: changeEventWithComparison({
            comparison: {
              maturity: "too_soon", window_days: null, pre_start: null, post_end: null, status: null,
              presence_days_in_condition: null, usable_days_in_condition: null,
              presence_days_out_of_condition: null, usable_days_out_of_condition: null,
            },
          }),
        }),
      ],
      change_outcomes: [],
    }),
  );

  await page.goto("/place-report/compare");
  await expect(page.getByText("New Nest Box", { exact: true })).toBeVisible();
  await expect(page.getByText("Too soon to tell", { exact: true })).toBeVisible();
  await expect(page.getByText("not enough monitoring yet for a rate", { exact: false })).toBeVisible();
});

test("an unlinked Feature shows no camera linked, never a fabricated rate", async ({ page }) => {
  await completeSetup(page);
  await mockComparisonApi(
    page,
    overview({
      features: [
        featureRow({
          feature: feature({ id: "unlinked-feature", name: "Backyard Patch", observation_links: [] }),
          recent_yield: null,
          latest_change: changeEventWithComparison({ comparison: null, environmental_comparison: null }),
        }),
      ],
      change_outcomes: [],
    }),
  );

  await page.goto("/place-report/compare");
  await expect(page.getByText("No camera linked yet")).toBeVisible();
  await expect(page.getByText("Not enough monitoring linked yet to show recent activity.")).toBeVisible();
});

test("early_signal and comparable maturities are visually distinguished", async ({ page }) => {
  await completeSetup(page);
  await mockComparisonApi(
    page,
    overview({
      features: [
        featureRow({ feature: feature({ id: "f-comparable", name: "Comparable Feature" }) }),
        featureRow({
          feature: feature({ id: "f-early", name: "Early Signal Feature" }),
          latest_change: changeEventWithComparison({
            event: { ...changeEventWithComparison().event, id: "change-early", feature_id: "f-early" },
            comparison: {
              maturity: "early_signal", window_days: 30, pre_start: "2026-05-02", post_end: "2026-07-01",
              status: "more_common_under_condition", presence_days_in_condition: 10, usable_days_in_condition: 12,
              presence_days_out_of_condition: 2, usable_days_out_of_condition: 12,
            },
          }),
        }),
      ],
      change_outcomes: [],
    }),
  );

  await page.goto("/place-report/compare");
  await expect(page.getByText("Enough evidence to compare")).toBeVisible();
  await expect(page.getByText("Early signal, longer window")).toBeVisible();
});

test("environmental context renders as a quiet, non-causal secondary line", async ({ page }) => {
  await completeSetup(page);
  await mockComparisonApi(
    page,
    overview({
      change_outcomes: [
        changeEventWithComparison({
          environmental_comparison: {
            status: "comparable", window_days: 7, pre_start: "2026-05-25", post_end: "2026-06-08",
            information_class: "inferred", provider_key: "open-meteo",
            pre_mean_temperature_c: 15.0, post_mean_temperature_c: 2.0,
            pre_total_precipitation_mm: null, post_total_precipitation_mm: null,
            summary: "The after period was notably cooler.",
          },
        }),
      ],
    }),
  );

  await page.goto("/place-report/compare");
  await expect(page.getByText("The after period was notably cooler.")).toBeVisible();
});

test("sorting by visits per monitored hour reorders the Feature list", async ({ page }) => {
  await completeSetup(page);
  await mockComparisonApi(
    page,
    overview({
      features: [
        featureRow({
          feature: feature({ id: "f-low", name: "Low Rate Feeder" }),
          recent_yield: {
            confirmed_wildlife_visit_count: 1, distinct_taxon_count: 1, monitored_seconds: 36000,
            visits_per_monitored_hour: 0.1, data_sufficient: true, window_days: 7,
          },
        }),
        featureRow({
          feature: feature({ id: "f-high", name: "High Rate Feeder" }),
          recent_yield: {
            confirmed_wildlife_visit_count: 20, distinct_taxon_count: 4, monitored_seconds: 36000,
            visits_per_monitored_hour: 2.0, data_sufficient: true, window_days: 7,
          },
        }),
      ],
    }),
  );

  await page.goto("/place-report/compare");
  const rows = page.locator(".feature-comparison-list").first().locator(".feature-comparison-row");
  await expect(rows).toHaveCount(2);
  await page.getByLabel("Sort by").first().selectOption("rate");
  await expect(rows.first()).toContainText("High Rate Feeder");
});

test("filtering by Feature type narrows the list", async ({ page }) => {
  await completeSetup(page);
  await mockComparisonApi(
    page,
    overview({
      features: [
        featureRow({ feature: feature({ id: "f-feeder", name: "The Feeder", feature_type: "feeder" }) }),
        featureRow({ feature: feature({ id: "f-water", name: "The Bird Bath", feature_type: "water" }) }),
      ],
    }),
  );

  await page.goto("/place-report/compare");
  await expect(page.getByText("The Feeder", { exact: true })).toBeVisible();
  await expect(page.getByText("The Bird Bath", { exact: true })).toBeVisible();
  await page.getByLabel("Feature type").selectOption("water");
  await expect(page.getByText("The Bird Bath", { exact: true })).toBeVisible();
  await expect(page.getByText("The Feeder", { exact: true })).toHaveCount(0);
});

test("a Feature Story link from the comparison page navigates there", async ({ page }) => {
  await completeSetup(page);
  await mockComparisonApi(page);
  await page.route("**/api/place/features/feature-comparison-e2e-1/detail", (route) =>
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({ feature: feature(), changes: [changeEventWithComparison()], recent_yield: null, representative_evidence: null }),
    }),
  );
  await page.route("**/api/place/story*", (route) =>
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({ generated_at: NOW, period_start_at: NOW, period_end_at: NOW, entries: [], has_more: false, next_offset: null, total_matched: 0, is_early_experience: false }),
    }),
  );

  await page.goto("/place-report/compare");
  await page.getByRole("button", { name: "View Sunflower Feeder story" }).first().click();
  await expect(page).toHaveURL(/\/place-story\/feature\/feature-comparison-e2e-1/);
});

test("a Compare Features link on the Place Report opens the comparison page", async ({ page }) => {
  await completeSetup(page);
  await page.route("**/api/place/features", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([feature()]) }),
  );
  await page.route("**/api/place/feature-changes*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) }),
  );
  await mockComparisonApi(page);

  await page.goto("/place-report");
  await expect(page.getByRole("heading", { name: "Features & changes" })).toBeVisible();
  await page.getByRole("button", { name: "Compare Features" }).click();
  await expect(page).toHaveURL(/\/place-report\/compare/);
  await expect(page.getByRole("heading", { name: "Compare Features", level: 1 })).toBeVisible();
});

test("the comparison page stays usable and free of horizontal overflow at phone width", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 700 });
  await completeSetup(page);
  await mockComparisonApi(page);

  await page.goto("/place-report/compare");
  await expect(page.getByRole("heading", { name: "Compare Features", level: 1 })).toBeVisible();
  const bodyScrollWidth = await page.evaluate(() => document.body.scrollWidth);
  const viewportWidth = await page.evaluate(() => window.innerWidth);
  expect(bodyScrollWidth).toBeLessThanOrEqual(viewportWidth + 1); // +1: sub-pixel rounding tolerance
});

test("the page heading receives focus for keyboard/screen-reader users", async ({ page }) => {
  await completeSetup(page);
  await mockComparisonApi(page);

  await page.goto("/place-report/compare");
  await expect(page.getByRole("heading", { name: "Compare Features", level: 1 })).toBeFocused();
});

test("sort and filter controls are reachable by keyboard", async ({ page }) => {
  await completeSetup(page);
  await mockComparisonApi(page);

  await page.goto("/place-report/compare");
  await page.getByLabel("Feature type").focus();
  await expect(page.getByLabel("Feature type")).toBeFocused();
});
