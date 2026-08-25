import { expect, test, type Page } from "@playwright/test";

// Place Features & Habitat Change v2 (see docs/place-features-habitat-
// change-v2-contract.md). `PlaceFeaturesCard` (Dashboard) and the "Features
// & changes" section (Place Report) render only facts the backend already
// computed -- this spec proves the presentation contract (empty state,
// highlight/tag rendering, the add-feature form's accessible structure, and
// the honest before/after wording for each maturity outcome), not the
// underlying comparison computation itself, which is already covered by
// tests/test_place_feature.py. Empty-state scenarios exercise the real,
// unmocked backend (the demo-seeded e2e database genuinely has no Place
// Features yet); populated scenarios intercept the relevant endpoint with a
// synthetic, schema-shaped response, the same house pattern biodiversity-
// summary.spec.ts and today-report.spec.ts already use.

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

const NOW = new Date().toISOString();

function feature(overrides: Record<string, unknown> = {}) {
  return {
    id: "feature-e2e-1",
    feature_type: "feeder",
    name: "Sunflower feeder",
    note: null,
    is_active: true,
    installed_date: null,
    removed_date: null,
    source_id: null,
    zone_id: null,
    feeder_food_type: null,
    information_class: "reviewed",
    provenance: "user_manual_entry",
    created_at: NOW,
    updated_at: NOW,
    ...overrides,
  };
}

async function mockFeaturesSummary(page: Page, body: Record<string, unknown>) {
  await page.route("**/api/place/features-summary", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) }),
  );
}

async function mockFeaturesList(page: Page, features: unknown[]) {
  await page.route("**/api/place/features", (route) => {
    if (route.request().method() !== "GET") {
      return route.continue();
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(features) });
  });
}

test("a brand-new Place shows an honest empty state, not a bare zero", async ({ page }) => {
  await completeSetup(page);
  await page.goto("/");

  const card = page.locator(".place-features-card");
  await expect(card).toBeVisible();
  await expect(card.getByText("No feeders, water features, or other Place features recorded yet.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Add a feature" })).toBeVisible();
});

test("the Place Report has no Features & changes section when nothing is recorded", async ({ page }) => {
  await completeSetup(page);
  await page.goto("/place-report");
  await expect(page.getByRole("heading", { name: "Place Report" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Features & changes" })).toHaveCount(0);
});

test("Dashboard shows the highlight sentence and active feature tags", async ({ page }) => {
  await completeSetup(page);
  await mockFeaturesSummary(page, {
    active_feature_count: 1,
    recent_change_count: 1,
    highlight: "Sunflower feeder has been especially active this week.",
  });
  await mockFeaturesList(page, [feature()]);

  await page.goto("/");
  const card = page.locator(".place-features-card");
  await expect(card).toBeVisible();
  await expect(card.getByText("Sunflower feeder has been especially active this week.")).toBeVisible();
  await expect(card.getByText("Sunflower feeder", { exact: true })).toBeVisible();
});

test("Manage features reveals an accessible add-feature form", async ({ page }) => {
  await completeSetup(page);
  await mockFeaturesSummary(page, { active_feature_count: 0, recent_change_count: 0, highlight: null });
  await mockFeaturesList(page, []);

  await page.goto("/");
  await page.getByRole("button", { name: "Add a feature" }).click();

  const card = page.locator(".place-features-card");
  await expect(card.getByLabel("Type")).toBeVisible();
  await expect(card.getByLabel("Name")).toBeVisible();
  await expect(card.getByRole("button", { name: "Add" })).toBeVisible();
  // The "Record a change" fieldset is present in the same edit view.
  await expect(card.getByLabel("Feature")).toBeVisible();
  await expect(card.getByLabel("What changed")).toBeVisible();
  await expect(card.getByRole("button", { name: "Record change" })).toBeVisible();
});

test("Place Report shows a higher-after before/after insight, association language only", async ({ page }) => {
  await completeSetup(page);
  await page.route("**/api/place/features", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([feature()]) }),
  );
  await page.route("**/api/place/feature-changes*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) }),
  );
  await page.route("**/api/place/features/feature-e2e-1/detail", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        feature: feature(),
        changes: [
          {
            event: {
              id: "change-e2e-1",
              feature_id: "feature-e2e-1",
              event_type: "added",
              effective_date: "2026-06-01",
              note: null,
              prior_value: null,
              new_value: null,
              information_class: "reviewed",
              provenance: "user_manual_entry",
              created_at: NOW,
              updated_at: NOW,
            },
            comparison: {
              maturity: "comparable",
              window_days: 7,
              pre_start: "2026-05-25",
              post_end: "2026-06-08",
              status: "more_common_under_condition",
              presence_days_in_condition: 6,
              usable_days_in_condition: 7,
              presence_days_out_of_condition: 1,
              usable_days_out_of_condition: 7,
            },
          },
        ],
        recent_yield: {
          confirmed_wildlife_visit_count: 12,
          distinct_taxon_count: 3,
          monitored_seconds: 36000,
          visits_per_monitored_hour: 1.2,
          data_sufficient: true,
          window_days: 7,
        },
      }),
    }),
  );

  await page.goto("/place-report");
  await expect(page.getByRole("heading", { name: "Features & changes" })).toBeVisible();
  await page.getByRole("button", { name: "See activity insight" }).click();
  await expect(
    page.getByText("Confirmed wildlife activity was higher in the 7-day windows after this change than before."),
  ).toBeVisible();
  // Never a raw percentage or a causal claim from this small a count.
  await expect(page.getByText("%")).toHaveCount(0);
  await expect(page.getByText(/caused|because of/i)).toHaveCount(0);
});

test("an insufficiently-monitored change reads as an honest restrained state, not a guess", async ({ page }) => {
  await completeSetup(page);
  await page.route("**/api/place/features", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([feature()]) }),
  );
  await page.route("**/api/place/feature-changes*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) }),
  );
  await page.route("**/api/place/features/feature-e2e-1/detail", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        feature: feature(),
        changes: [
          {
            event: {
              id: "change-e2e-2",
              feature_id: "feature-e2e-1",
              event_type: "added",
              effective_date: "2026-06-01",
              note: null,
              prior_value: null,
              new_value: null,
              information_class: "reviewed",
              provenance: "user_manual_entry",
              created_at: NOW,
              updated_at: NOW,
            },
            comparison: { maturity: "too_soon" },
          },
        ],
        recent_yield: null,
      }),
    }),
  );

  await page.goto("/place-report");
  await page.getByRole("button", { name: "See activity insight" }).click();
  await expect(
    page.getByText("Too soon to tell -- not enough time has passed since this change yet."),
  ).toBeVisible();
});

test("the Place Features card stays usable at a narrow (mobile) viewport", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 700 });
  await completeSetup(page);
  await mockFeaturesSummary(page, {
    active_feature_count: 1,
    recent_change_count: 0,
    highlight: "Sunflower feeder has been especially active this week.",
  });
  await mockFeaturesList(page, [feature()]);

  await page.goto("/");
  const card = page.locator(".place-features-card");
  await expect(card).toBeVisible();
  await expect(page.getByRole("button", { name: "Manage features" })).toBeVisible();
});
