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
    observation_links: [],
    ...overrides,
  };
}

// Multi-Camera Place Feature Linking & Cross-View Habitat Context v1.
function observationLink(overrides: Record<string, unknown> = {}) {
  return {
    id: "link-e2e-1",
    source_id: "source-e2e-1",
    source_name: "Patio",
    source_archived: false,
    zone_id: "zone-e2e-1",
    zone_name: "Bird Bath Zone",
    created_at: NOW,
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
            environmental_comparison: {
              status: "comparable",
              window_days: 7,
              pre_start: "2026-05-25",
              post_end: "2026-06-08",
              information_class: "inferred",
              provider_key: "open_meteo",
              pre_mean_temperature_c: 15.0,
              post_mean_temperature_c: 4.0,
              summary: "The after period was notably cooler.",
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
  // Environmental context renders as a restrained, secondary line -- never
  // fused into the wildlife sentence above it, never a causal claim.
  await expect(page.getByText("The after period was notably cooler.")).toBeVisible();
  // Never a raw percentage or a causal claim from this small a count.
  await expect(page.getByText("%")).toHaveCount(0);
  await expect(page.getByText(/caused|because of|led to|resulted in|due to|drove/i)).toHaveCount(0);
});

test("a Feature comparison without configured weather shows no broken environmental line", async ({ page }) => {
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
              id: "change-e2e-3",
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
              status: "no_clear_association",
              presence_days_in_condition: 3,
              usable_days_in_condition: 7,
              presence_days_out_of_condition: 3,
              usable_days_out_of_condition: 7,
            },
            environmental_comparison: {
              status: "not_configured",
              window_days: 7,
              pre_start: "2026-05-25",
              post_end: "2026-06-08",
            },
          },
        ],
        recent_yield: null,
      }),
    }),
  );

  await page.goto("/place-report");
  await page.getByRole("button", { name: "See activity insight" }).click();
  await expect(
    page.getByText("Activity looked similar in the 7-day windows before and after this change."),
  ).toBeVisible();
  // "not_configured" stays quietly absent -- no broken/empty card, no raw
  // status leaking into visible text.
  await expect(page.getByText("not_configured")).toHaveCount(0);
  await expect(page.locator(".feature-environmental-comparison")).toHaveCount(0);
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
    page.getByText("Too soon to tell — not enough time has passed since this change yet."),
  ).toBeVisible();
});

test("Manage features shows the Observed by chips for a linked Feature, with an archived suffix", async ({
  page,
}) => {
  await completeSetup(page);
  await mockFeaturesSummary(page, { active_feature_count: 1, recent_change_count: 0, highlight: null });
  await mockFeaturesList(page, [
    feature({
      observation_links: [
        observationLink(),
        observationLink({
          id: "link-e2e-2", source_id: "source-e2e-2", source_name: "Garden",
          source_archived: true, zone_id: "zone-e2e-2", zone_name: "Pond Edge Zone",
        }),
      ],
    }),
  ]);

  await page.goto("/");
  await page.getByRole("button", { name: "Manage features" }).click();
  const card = page.locator(".place-features-card");
  await expect(card.getByText("Observed by:")).toBeVisible();
  await expect(card.getByText("Patio — Bird Bath Zone")).toBeVisible();
  await expect(card.getByText("Garden (archived) — Pond Edge Zone")).toBeVisible();
});

test("Manage features shows an honest 'no camera linked' state for a Place-wide Feature", async ({ page }) => {
  await completeSetup(page);
  await mockFeaturesSummary(page, { active_feature_count: 1, recent_change_count: 0, highlight: null });
  await mockFeaturesList(page, [feature({ observation_links: [] })]);

  await page.goto("/");
  await page.getByRole("button", { name: "Manage features" }).click();
  await expect(page.locator(".place-features-card").getByText("No camera linked — Place knowledge only.")).toBeVisible();
});

test("+ Add another view reveals an accessible camera/Zone picker", async ({ page }) => {
  await completeSetup(page);
  await mockFeaturesSummary(page, { active_feature_count: 1, recent_change_count: 0, highlight: null });
  await mockFeaturesList(page, [feature({ observation_links: [observationLink()] })]);

  await page.goto("/");
  await page.getByRole("button", { name: "Manage features" }).click();
  await page.getByRole("button", { name: "+ Add another view" }).click();

  const card = page.locator(".place-features-card");
  // A `<select>` wrapped in its `<label>` computes its accessible name from
  // the label's full text content, which browsers concatenate with the
  // select's own option text -- `getByText` on the label's own static text
  // is the robust check here, not an exact `getByLabel` match.
  await expect(card.getByText("Camera to add")).toBeVisible();
  await expect(card.getByRole("button", { name: "Add view" })).toBeVisible();
  await expect(card.getByRole("button", { name: "Cancel" })).toBeVisible();
});

test("Place Report shows every linked view for a multi-camera Feature", async ({ page }) => {
  await completeSetup(page);
  await page.route("**/api/place/features", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        feature({
          observation_links: [
            observationLink(),
            observationLink({
              id: "link-e2e-3", source_id: "source-e2e-3", source_name: "Garden",
              source_archived: false, zone_id: null, zone_name: null,
            }),
          ],
        }),
      ]),
    }),
  );
  await page.route("**/api/place/feature-changes*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) }),
  );

  await page.goto("/place-report");
  await expect(page.getByRole("heading", { name: "Features & changes" })).toBeVisible();
  await expect(page.getByText("Observed by: Patio — Bird Bath Zone, Garden")).toBeVisible();
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
