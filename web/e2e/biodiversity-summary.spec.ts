import { expect, test, type Page } from "@playwright/test";

// Biodiversity & Place Intelligence v1 (see docs/biodiversity-place-
// intelligence-v1-contract.md). `BiodiversitySummaryCard` renders only
// facts the backend already computed (`GET /api/place/biodiversity-
// summary`) -- this spec proves the presentation contract (headline
// counts, New here/Regular visitors/Recently observed wording, the
// provisional-vs-authoritative visual separation, honest empty/sparse
// states), not the summary's own truth computation, which is already
// covered by tests/test_place_biodiversity_summary.py and tests/
// test_place_biodiversity_summary_repository.py. Every scenario
// intercepts `/api/place/biodiversity-summary` with a fully synthetic,
// schema-shaped response -- the same house pattern today-report.spec.ts
// and bird-log-historical-status.spec.ts already use.

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

const EMPTY_HISTORICAL_BASELINE = {
  window_start_at: new Date(Date.now() - 366 * 24 * 3600 * 1000).toISOString(),
  window_end_at: new Date().toISOString(),
  usable_day_count: 0,
  total_monitored_seconds: null,
  maturity: "insufficient",
  distinct_taxa_count: 0,
  earliest_authoritative_record_at: null,
  latest_authoritative_record_at: null,
};

function taxonEntry(label: string, displayName: string, status: string) {
  const now = new Date().toISOString();
  return {
    label,
    display_name: displayName,
    category: "bird",
    is_species: true,
    historical_status: {
      first_confirmed_at: now,
      last_confirmed_at: now,
      distinct_confirmed_days: 1,
      distinct_confirmed_usable_days: 1,
      total_confirmed_count: 1,
      status,
    },
  };
}

async function mockBiodiversitySummary(page: Page, overrides: Record<string, unknown>) {
  const base = {
    generated_at: new Date().toISOString(),
    historical_baseline: EMPTY_HISTORICAL_BASELINE,
    distinct_species_count: 0,
    taxa: [],
    new_taxa: [],
    regular_taxa: [],
    recently_observed_taxa: [],
    provisional_taxa: [],
    habitat_context: { habitat_facts: [], current_phenology: [], recent_phenology: [] },
    environmental_context: { available: false, for_date: new Date().toISOString().slice(0, 10) },
    warnings: [],
  };
  const body = { ...base, ...overrides };
  await page.route("**/api/place/biodiversity-summary", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) }),
  );
}

test("a brand-new Place shows an honest empty state, not a bare zero", async ({ page }) => {
  await completeSetup(page);
  await mockBiodiversitySummary(page, {
    warnings: ["No monitoring history recorded yet -- biodiversity facts here will fill in once a Stream has been observing."],
  });

  await page.goto("/");
  const card = page.locator(".biodiversity-summary-card");
  await expect(card).toBeVisible();
  await expect(card.getByText("Nothing recorded yet.")).toBeVisible();
  await expect(card.getByText("No monitoring history recorded yet", { exact: false })).toBeVisible();
});

test("Dashboard shows New here, Regular visitors, and Recently observed from the same summary", async ({
  page,
}) => {
  await completeSetup(page);
  const cardinal = taxonEntry("northern_cardinal", "Northern Cardinal", "regular");
  const finch = taxonEntry("house_finch", "House Finch", "new");
  await mockBiodiversitySummary(page, {
    historical_baseline: { ...EMPTY_HISTORICAL_BASELINE, maturity: "established", distinct_taxa_count: 2 },
    distinct_species_count: 2,
    taxa: [cardinal, finch],
    new_taxa: [finch],
    regular_taxa: [cardinal],
    recently_observed_taxa: [cardinal, finch],
  });

  await page.goto("/");
  const card = page.locator(".biodiversity-summary-card");
  await expect(card).toBeVisible();
  await expect(card.getByText("2", { exact: true })).toBeVisible();
  const newLine = card.locator("p", { hasText: "New here:" });
  await expect(newLine).toContainText("House Finch");
  const regularLine = card.locator("p", { hasText: "Regular visitors:" });
  await expect(regularLine).toContainText("Northern Cardinal");
  const recentLine = card.locator("p", { hasText: "Recently observed:" });
  await expect(recentLine).toContainText("Northern Cardinal");
  await expect(recentLine).toContainText("House Finch");
});

test("a regular taxon not seen in the last two weeks is never described as absent", async ({ page }) => {
  await completeSetup(page);
  const cardinal = taxonEntry("northern_cardinal", "Northern Cardinal", "regular");
  await mockBiodiversitySummary(page, {
    historical_baseline: { ...EMPTY_HISTORICAL_BASELINE, maturity: "established", distinct_taxa_count: 1 },
    distinct_species_count: 1,
    taxa: [cardinal],
    regular_taxa: [cardinal],
    recently_observed_taxa: [],
  });

  await page.goto("/");
  const card = page.locator(".biodiversity-summary-card");
  await expect(card.getByText("Regular visitors:", { exact: false })).toBeVisible();
  await expect(card.getByText("Nothing recorded in the last two weeks", { exact: false })).toBeVisible();
  await expect(card.getByText(/absent/i)).toHaveCount(0);
  await expect(card.getByText(/gone/i)).toHaveCount(0);
});

test("provisional taxa are shown separately, never folded into the confirmed species count", async ({
  page,
}) => {
  await completeSetup(page);
  await mockBiodiversitySummary(page, {
    provisional_taxa: [
      {
        label: "carolina_wren",
        display_name: "Carolina Wren",
        distinct_days_seen: 1,
        is_confirmed: false,
        latest_visit: {
          id: "visit-wren",
          activity_started_at: new Date().toISOString(),
          duration_seconds: 10,
        },
      },
    ],
  });

  await page.goto("/");
  const card = page.locator(".biodiversity-summary-card");
  await expect(card).toBeVisible();
  await expect(card.getByText("Species known here")).toBeVisible();
  await expect(card.getByText("0", { exact: true })).toBeVisible();
  await expect(card.getByText("Awaiting review")).toBeVisible();
  await expect(card.getByText("1", { exact: true })).toBeVisible();
});

test("the Place Report page shows the same biodiversity card", async ({ page }) => {
  await completeSetup(page);
  const cardinal = taxonEntry("northern_cardinal", "Northern Cardinal", "new");
  await mockBiodiversitySummary(page, {
    historical_baseline: { ...EMPTY_HISTORICAL_BASELINE, maturity: "established", distinct_taxa_count: 1 },
    distinct_species_count: 1,
    taxa: [cardinal],
    new_taxa: [cardinal],
  });

  await page.goto("/place-report");
  const card = page.locator(".biodiversity-summary-card");
  await expect(card).toBeVisible();
  await expect(card.getByText("New here:", { exact: false })).toBeVisible();
  await expect(card.getByText("Northern Cardinal")).toBeVisible();
});

// Taxon Place History (habitat/environment connection on Bird Log).

async function mockJournalOverview(page: Page) {
  await page.route("**/api/bird-log/journal*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ order: "most_recent", labels: [], baseline_maturity: "insufficient" }),
    }),
  );
  await page.route("**/api/bird-log/likely", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ species: [] }) }),
  );
}

async function mockJournalHistory(page: Page, label: string, overrides: Record<string, unknown>) {
  const now = new Date().toISOString();
  const base = {
    label,
    display_name: "Northern Cardinal",
    scope: {
      preset: "all_time",
      start_date: null,
      end_date: null,
      stream_id: null,
      zone_id: null,
      favorites_only: false,
      tag_id: null,
      timezone_name: "UTC",
    },
    observation_count: 1,
    first_observation: null,
    latest_observation: null,
    representative: null,
    busiest_stream: null,
    busiest_zone: null,
    peak_activity_hour: null,
    stream_breakdown: [],
    zone_breakdown: [],
    activity_by_hour: Array.from({ length: 24 }, (_, hour) => ({ hour, count: 0 })),
    is_new_label_in_range: false,
    distinct_confirmed_usable_days: 1,
    is_regular: false,
    baseline_maturity: "insufficient",
    place_context: null,
    activity_library_drilldown: {
      review_filter: "confirmed_wildlife",
      confirmed_label: label,
      start_date: null,
      end_date: null,
      stream_id: null,
      zone_id: null,
    },
    gallery: { order: "newest", observations: [], has_more: false, next_offset: null },
  };
  const body = { ...base, ...overrides };
  await page.route(`**/api/bird-log/journal/${encodeURIComponent(label)}*`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) }),
  );
}

test("a taxon's history shows habitat/environment context for its most recent sighting", async ({ page }) => {
  await completeSetup(page);
  await mockJournalOverview(page);
  const observedAt = new Date().toISOString();
  await mockJournalHistory(page, "northern_cardinal", {
    place_context: {
      observed_at: observedAt,
      environmental_context: { available: true, daylight_state: "day", reason: "computed" },
      phenology_context: [
        { id: "phen-1", subject_label: "Deciduous canopy", phenomenon: "leafed out", status: "current" },
      ],
    },
  });

  await page.goto("/bird-log/northern_cardinal");
  await expect(page.getByText("Habitat & environment")).toBeVisible();
  await expect(page.getByText("Recorded during daylight")).toBeVisible();
  await expect(page.getByText("Deciduous canopy")).toBeVisible();
  await expect(page.getByText("leafed out", { exact: false })).toBeVisible();
});

test("a taxon's history with no place context omits the habitat/environment section entirely", async ({
  page,
}) => {
  await completeSetup(page);
  await mockJournalOverview(page);
  await mockJournalHistory(page, "northern_cardinal", { place_context: null });

  await page.goto("/bird-log/northern_cardinal");
  await expect(page.getByText("Habitat & environment")).toHaveCount(0);
});
