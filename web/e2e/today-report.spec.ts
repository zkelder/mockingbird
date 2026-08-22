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
    // Most scenarios below represent a well-monitored day; scenarios that
    // specifically exercise sparse/no-data maturity override this.
    maturity: "usable" as string,
    // Historical Baseline Maturity + New/Regular Species v1: most scenarios
    // below don't care about Place-wide baseline maturity itself (only
    // individual `taxa[].historical_status` entries, overridden per-test);
    // this default is deliberately "established" so a scenario that adds a
    // `historical_status` without also overriding this field still gets the
    // "new" (not "first_record") wording by default.
    historical_baseline: {
      window_start_at: new Date(now.getTime() - 366 * 24 * 3600 * 1000).toISOString(),
      window_end_at: now.toISOString(),
      usable_day_count: 10,
      total_monitored_seconds: 10 * 2 * 3600,
      maturity: "established" as string,
      distinct_taxa_count: 3,
      earliest_authoritative_record_at: new Date(now.getTime() - 300 * 24 * 3600 * 1000).toISOString(),
      latest_authoritative_record_at: now.toISOString(),
    },
    // Gate C -- Meaningful Change Detection / Baseline Comparison v1 (see
    // docs/meaningful-change-detection-contract.md). Deliberately "valid" +
    // "no_supported_change" by default -- the calm, invisible-by-default
    // case (no Place-level note rendered) -- so a scenario that doesn't
    // care about this feature sees no unexpected text; scenarios that do
    // override these fields explicitly.
    change_windows: {
      policy_version: 1,
      recent_window_start_at: new Date(now.getTime() - 7 * 24 * 3600 * 1000).toISOString(),
      recent_window_end_at: now.toISOString(),
      reference_window_start_at: new Date(now.getTime() - 21 * 24 * 3600 * 1000).toISOString(),
      reference_window_end_at: new Date(now.getTime() - 7 * 24 * 3600 * 1000).toISOString(),
      is_valid: true,
      invalid_reason: null,
    },
    overall_change_status: {
      recent_presence_days: 4,
      recent_usable_day_count: 7,
      reference_presence_days: 8,
      reference_usable_day_count: 14,
      status: "no_supported_change" as string,
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
  // No per-row "Likely" nagging on ordinary confirmed species rows, and no
  // blended "+N likely" annotation when a species has zero provisional
  // Visits.
  await expect(reportPanel.getByText("Likely Northern Cardinal")).toHaveCount(0);
  await expect(speciesList.locator(".today-report-species-likely")).toHaveCount(0);
  // Per-species timing (first_activity_at == last_activity_at in this
  // fixture, so each row reads "Seen <time>" rather than a redundant range).
  await expect(speciesList.nth(0)).toContainText("Seen");

  // Report-level first/last activity are both shown, not just the last.
  await expect(reportPanel.getByText("First visit", { exact: false })).toBeVisible();

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

// Gate C -- Per-Species Zone + Time Pattern Intelligence v1: a species row's
// own "where/when it's usually recorded" secondary fact, from
// `taxa[].most_active_zone`/`most_active_hour` (see
// docs/place-activity-report-contract.md). These scenarios are additive to
// the report contract above -- taxa entries omitting these fields (every
// other scenario in this file) simply render no such line, proven
// implicitly by every test above continuing to pass unmodified.

test("a species row shows its usual Zone and time-of-day pattern once there is enough reviewed history", async ({
  page,
}) => {
  await completeSetup(page);
  const lastVisitAt = new Date().toISOString();
  await mockPlaceActivityReport(page, {
    total_visit_count: 6,
    confirmed_wildlife_visit_count: 6,
    wildlife_visit_count: 6,
    distinct_taxa_count: 1,
    distinct_species_count: 1,
    last_activity_at: lastVisitAt,
    first_activity_at: lastVisitAt,
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
        zone_activity: [{ zone_id: "zone-feeder-1", display_name: "Backyard feeder", reviewed_visit_count: 6 }],
        hour_activity: [{ local_hour: 7, reviewed_visit_count: 6 }],
        most_active_zone: { zone_id: "zone-feeder-1", display_name: "Backyard feeder", reviewed_visit_count: 6 },
        most_active_hour: { local_hour: 7, reviewed_visit_count: 6 },
      },
    ],
  });

  await page.goto("/");
  const speciesRow = page.locator(".today-report-species-list li").first();
  await expect(speciesRow).toBeVisible();
  // Combined Zone + time, in plain human-facing wording -- no internal IDs.
  await expect(speciesRow.getByText("Backyard feeder · 7–8 AM")).toBeVisible();
  await expect(speciesRow.getByText("zone-feeder-1")).toHaveCount(0);
});

test("a species row shows time-only pattern wording with no Zones configured, never implying setup is incomplete", async ({
  page,
}) => {
  await completeSetup(page);
  const lastVisitAt = new Date().toISOString();
  await mockPlaceActivityReport(page, {
    total_visit_count: 5,
    confirmed_wildlife_visit_count: 5,
    wildlife_visit_count: 5,
    distinct_taxa_count: 1,
    distinct_species_count: 1,
    last_activity_at: lastVisitAt,
    first_activity_at: lastVisitAt,
    // Place-wide: no Zone was ever recorded either -- the ordinary,
    // fully-supported "no Zones configured" state, not an error state.
    activity_by_zone: [],
    busiest_zone: null,
    taxa: [
      {
        label: "house_finch",
        display_name: "House Finch",
        category: "bird",
        is_species: true,
        confirmed_visit_count: 5,
        provisional_visit_count: 0,
        total_visit_count: 5,
        first_activity_at: lastVisitAt,
        last_activity_at: lastVisitAt,
        zone_activity: [{ zone_id: null, display_name: "No Zone", reviewed_visit_count: 5 }],
        hour_activity: [{ local_hour: 16, reviewed_visit_count: 5 }],
        most_active_zone: null,
        most_active_hour: { local_hour: 16, reviewed_visit_count: 5 },
      },
    ],
  });

  await page.goto("/");
  const reportPanel = page.locator("section.today-report");
  const speciesRow = page.locator(".today-report-species-list li").first();
  await expect(speciesRow).toBeVisible();
  await expect(speciesRow.getByText("Most active 4–5 PM")).toBeVisible();
  // Never a fabricated Zone claim, and never wording that implies Zone
  // setup is missing or incomplete.
  await expect(speciesRow.getByText("No Zone")).toHaveCount(0);
  await expect(reportPanel.getByText("Busiest area")).toHaveCount(0);
  await expect(page.getByText(/set ?up.*incomplete/i)).toHaveCount(0);
  await expect(page.getByText(/no zones? configured/i)).toHaveCount(0);
});

test("a species row omits pattern copy below the minimum-support floor instead of guessing a favorite", async ({
  page,
}) => {
  await completeSetup(page);
  const lastVisitAt = new Date().toISOString();
  await mockPlaceActivityReport(page, {
    total_visit_count: 1,
    confirmed_wildlife_visit_count: 1,
    wildlife_visit_count: 1,
    distinct_taxa_count: 1,
    distinct_species_count: 1,
    last_activity_at: lastVisitAt,
    first_activity_at: lastVisitAt,
    taxa: [
      {
        label: "blue_jay",
        display_name: "Blue Jay",
        category: "bird",
        is_species: true,
        confirmed_visit_count: 1,
        provisional_visit_count: 0,
        total_visit_count: 1,
        first_activity_at: lastVisitAt,
        last_activity_at: lastVisitAt,
        // A single reviewed Visit: the backend reports the honest raw
        // count but withholds any "most active" claim -- see "Minimum
        // support" in docs/place-activity-report-contract.md.
        zone_activity: [{ zone_id: "zone-feeder-1", display_name: "Backyard feeder", reviewed_visit_count: 1 }],
        hour_activity: [{ local_hour: 7, reviewed_visit_count: 1 }],
        most_active_zone: null,
        most_active_hour: null,
      },
    ],
  });

  await page.goto("/");
  const speciesRow = page.locator(".today-report-species-list li").first();
  await expect(speciesRow).toBeVisible();
  await expect(speciesRow.getByText("Blue Jay")).toBeVisible();
  await expect(speciesRow.getByText("Backyard feeder", { exact: false })).toHaveCount(0);
  await expect(speciesRow.getByText("Most active", { exact: false })).toHaveCount(0);
  await expect(speciesRow.getByText("Mostly recorded", { exact: false })).toHaveCount(0);
});

test("historical status badges read New/First confirmed/Regular honestly, and a plain species row stays unbadged", async ({
  page,
}) => {
  // Historical Baseline Maturity + New/Regular Species v1 (see
  // docs/historical-baseline-maturity-contract.md): the backend already
  // resolved the maturity-appropriate wording into `taxon.historical_
  // status.status` -- this only proves the frontend renders exactly what
  // it was given, never re-deriving the new-vs-regular judgment itself.
  await completeSetup(page);
  const now = new Date().toISOString();
  await mockPlaceActivityReport(page, {
    total_visit_count: 4,
    confirmed_wildlife_visit_count: 4,
    wildlife_visit_count: 4,
    distinct_taxa_count: 4,
    distinct_species_count: 4,
    last_activity_at: now,
    first_activity_at: now,
    historical_baseline: {
      window_start_at: new Date(Date.now() - 366 * 24 * 3600 * 1000).toISOString(),
      window_end_at: now,
      usable_day_count: 10,
      total_monitored_seconds: 10 * 2 * 3600,
      maturity: "established",
      distinct_taxa_count: 4,
      earliest_authoritative_record_at: new Date(Date.now() - 300 * 24 * 3600 * 1000).toISOString(),
      latest_authoritative_record_at: now,
    },
    taxa: [
      {
        label: "white_breasted_nuthatch",
        display_name: "White-breasted Nuthatch",
        category: "bird",
        is_species: true,
        confirmed_visit_count: 1,
        provisional_visit_count: 0,
        total_visit_count: 1,
        first_activity_at: now,
        last_activity_at: now,
        historical_status: {
          first_confirmed_at: now,
          last_confirmed_at: now,
          distinct_confirmed_days: 1,
          distinct_confirmed_usable_days: 1,
          total_confirmed_count: 1,
          status: "new",
        },
      },
      {
        label: "carolina_wren",
        display_name: "Carolina Wren",
        category: "bird",
        is_species: true,
        confirmed_visit_count: 1,
        provisional_visit_count: 0,
        total_visit_count: 1,
        first_activity_at: now,
        last_activity_at: now,
        historical_status: {
          first_confirmed_at: now,
          last_confirmed_at: now,
          distinct_confirmed_days: 1,
          distinct_confirmed_usable_days: 1,
          total_confirmed_count: 1,
          status: "first_record",
        },
      },
      {
        label: "northern_cardinal",
        display_name: "Northern Cardinal",
        category: "bird",
        is_species: true,
        confirmed_visit_count: 6,
        provisional_visit_count: 0,
        total_visit_count: 6,
        first_activity_at: now,
        last_activity_at: now,
        historical_status: {
          first_confirmed_at: new Date(Date.now() - 20 * 24 * 3600 * 1000).toISOString(),
          last_confirmed_at: now,
          distinct_confirmed_days: 5,
          distinct_confirmed_usable_days: 3,
          total_confirmed_count: 11,
          status: "regular",
        },
      },
      {
        label: "house_finch",
        display_name: "House Finch",
        category: "bird",
        is_species: true,
        confirmed_visit_count: 1,
        provisional_visit_count: 0,
        total_visit_count: 1,
        first_activity_at: now,
        last_activity_at: now,
        // No historical_status at all: a purely-provisional-until-now
        // species that was JUST confirmed does still get one (backend
        // guarantee); this row instead models the calm, ordinary
        // "seen_before" case by omitting the field, which the frontend
        // must treat identically to an explicit "seen_before" -- no badge.
      },
    ],
  });

  await page.goto("/");
  const reportPanel = page.locator("section.today-report");
  const speciesList = reportPanel.locator(".today-report-species-list li");
  await expect(speciesList).toHaveCount(4);

  const nuthatchRow = speciesList.filter({ hasText: "White-breasted Nuthatch" });
  await expect(nuthatchRow.getByText("New to your reviewed history")).toBeVisible();

  const wrenRow = speciesList.filter({ hasText: "Carolina Wren" });
  await expect(wrenRow.getByText("First confirmed record so far")).toBeVisible();
  // Never implies ecological novelty language when the baseline itself
  // said so via "first_record" rather than "new".
  await expect(wrenRow.getByText("New to your reviewed history")).toHaveCount(0);

  const cardinalRow = speciesList.filter({ hasText: "Northern Cardinal" });
  await expect(cardinalRow.getByText("Regular here")).toBeVisible();

  const finchRow = speciesList.filter({ hasText: "House Finch" });
  await expect(finchRow.getByText("Regular here")).toHaveCount(0);
  await expect(finchRow.getByText("New to your reviewed history")).toHaveCount(0);
  await expect(finchRow.getByText("First confirmed record so far")).toHaveCount(0);
});

test("change-status badges read More/Fewer honestly, and no_supported_change stays unbadged", async ({ page }) => {
  // Gate C -- Meaningful Change Detection / Baseline Comparison v1 (see
  // docs/meaningful-change-detection-contract.md): the backend already
  // resolved the recent-vs-reference comparison into `taxon.change_status.
  // status` -- this only proves the frontend renders exactly what it was
  // given, never re-deriving the comparison itself.
  await completeSetup(page);
  const now = new Date().toISOString();
  const baseTaxon = {
    category: "bird",
    is_species: true,
    confirmed_visit_count: 3,
    provisional_visit_count: 0,
    total_visit_count: 3,
    first_activity_at: now,
    last_activity_at: now,
  };
  await mockPlaceActivityReport(page, {
    total_visit_count: 3,
    confirmed_wildlife_visit_count: 3,
    wildlife_visit_count: 3,
    distinct_taxa_count: 3,
    distinct_species_count: 3,
    last_activity_at: now,
    first_activity_at: now,
    taxa: [
      {
        ...baseTaxon,
        label: "northern_cardinal",
        display_name: "Northern Cardinal",
        change_status: {
          recent_presence_days: 5,
          recent_usable_day_count: 7,
          reference_presence_days: 3,
          reference_usable_day_count: 14,
          status: "higher_recent_presence",
        },
      },
      {
        ...baseTaxon,
        label: "house_finch",
        display_name: "House Finch",
        change_status: {
          recent_presence_days: 1,
          recent_usable_day_count: 7,
          reference_presence_days: 10,
          reference_usable_day_count: 14,
          status: "lower_recent_presence",
        },
      },
      {
        ...baseTaxon,
        label: "carolina_wren",
        display_name: "Carolina Wren",
        change_status: {
          recent_presence_days: 4,
          recent_usable_day_count: 7,
          reference_presence_days: 8,
          reference_usable_day_count: 14,
          status: "no_supported_change",
        },
      },
    ],
  });

  await page.goto("/");
  const reportPanel = page.locator("section.today-report");
  const speciesList = reportPanel.locator(".today-report-species-list li");
  await expect(speciesList).toHaveCount(3);

  const cardinalRow = speciesList.filter({ hasText: "Northern Cardinal" });
  await expect(cardinalRow.getByText("More often recently")).toBeVisible();

  const finchRow = speciesList.filter({ hasText: "House Finch" });
  await expect(finchRow.getByText("Fewer recent visits")).toBeVisible();

  const wrenRow = speciesList.filter({ hasText: "Carolina Wren" });
  await expect(wrenRow.getByText("More often recently")).toHaveCount(0);
  await expect(wrenRow.getByText("Fewer recent visits")).toHaveCount(0);
});

test("the Place-level change message stays calm: shown only when there is something to say", async ({ page }) => {
  await completeSetup(page);

  await mockPlaceActivityReport(page, {
    overall_change_status: {
      recent_presence_days: 0,
      recent_usable_day_count: 0,
      reference_presence_days: 0,
      reference_usable_day_count: 0,
      status: "building_baseline",
    },
  });
  await page.goto("/");
  await expect(page.getByText("MockingBird is still building a baseline for this Place.")).toBeVisible();

  await mockPlaceActivityReport(page, {
    overall_change_status: {
      recent_presence_days: 2,
      recent_usable_day_count: 7,
      reference_presence_days: 12,
      reference_usable_day_count: 14,
      status: "less_activity_recorded",
    },
  });
  await page.goto("/");
  await expect(
    page.getByText("Wildlife activity was recorded on fewer monitored days recently than in the preceding weeks."),
  ).toBeVisible();

  // The calm default -- no Place-level line at all, matching how an
  // ordinary "seen_before" species row also renders no badge.
  await mockPlaceActivityReport(page, {
    overall_change_status: {
      recent_presence_days: 4,
      recent_usable_day_count: 7,
      reference_presence_days: 8,
      reference_usable_day_count: 14,
      status: "no_supported_change",
    },
  });
  await page.goto("/");
  await expect(page.locator(".today-report-change-note")).toHaveCount(0);
});

test("a Stream with older exposure history but zero coverage this period shows Partial, never Fully observed", async ({
  page,
}) => {
  // Regression for a real Working App v1 acceptance finding: a Stream that
  // was monitored on an earlier day (so it has durable exposure history,
  // and the backend's coverage policy correctly *reports* rather than
  // withholds a figure -- see "Place-wide coverage policy" in
  // docs/place-activity-report-contract.md) but was not observed at all
  // during *today's* period. The backend has no cross-Stream warning to
  // emit here (there is only one in-scope Stream, and it does have some
  // history) -- deriving coveragePartial from that warning alone produced
  // the "good"-toned "Fully observed today" pill for a literal 0%
  // coverage_ratio. This must read as Partial, using the real ratio.
  await completeSetup(page);
  await mockPlaceActivityReport(page, {
    coverage: {
      period_seconds: 86_400,
      monitored_seconds: 0,
      coverage_ratio: 0,
      history_available_from: new Date(Date.now() - 2 * 24 * 3600 * 1000).toISOString(),
      history_is_partial: false,
      gaps: [
        {
          start_at: new Date(Date.now() - 24 * 3600 * 1000).toISOString(),
          end_at: new Date().toISOString(),
          duration_seconds: 86_400,
        },
      ],
      gaps_truncated: false,
    },
  });

  await page.goto("/");
  const reportPanel = page.locator("section.today-report");
  await expect(reportPanel).toBeVisible();

  await expect(reportPanel.getByText("Partial coverage today")).toBeVisible();
  await expect(reportPanel.getByText("Fully observed today")).toHaveCount(0);
  await expect(reportPanel.getByText("about 0% of today", { exact: false })).toBeVisible();
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

test("a species' provisional Visits never blend into its confirmed count, and a never-confirmed species never appears by name", async ({
  page,
}) => {
  // Gate C: Daily Place Report v1 regression. The backend keeps confirmed_
  // visit_count/provisional_visit_count separate on every taxon precisely
  // so a UI never blends them (see "Report truth precedence" in
  // docs/place-activity-report-contract.md) -- this proves the frontend
  // actually honors that separation instead of summing total_visit_count.
  await completeSetup(page);
  const seenAt = new Date().toISOString();
  await mockPlaceActivityReport(page, {
    total_visit_count: 12,
    confirmed_wildlife_visit_count: 6,
    provisional_wildlife_visit_count: 6,
    wildlife_visit_count: 12,
    distinct_taxa_count: 2,
    distinct_species_count: 2,
    first_activity_at: seenAt,
    last_activity_at: seenAt,
    taxa: [
      {
        // Confirmed several times, but also has two additional, not-yet-
        // reviewed sightings -- the confirmed count must stay primary.
        label: "northern_cardinal",
        display_name: "Northern Cardinal",
        category: "bird",
        is_species: true,
        confirmed_visit_count: 6,
        provisional_visit_count: 2,
        total_visit_count: 8,
        first_activity_at: seenAt,
        last_activity_at: seenAt,
      },
      {
        // Never human-confirmed at all -- an AI suggestion only.
        label: "house_finch",
        display_name: "House Finch",
        category: "bird",
        is_species: true,
        confirmed_visit_count: 0,
        provisional_visit_count: 4,
        total_visit_count: 4,
        first_activity_at: seenAt,
        last_activity_at: seenAt,
      },
    ],
  });

  await page.goto("/");
  const reportPanel = page.locator("section.today-report");
  await expect(reportPanel).toBeVisible();

  // Headline reflects confirmed truth only: 1 confirmed species, 6
  // confirmed visits -- never the blended 2/12.
  await expect(reportPanel.getByText("1", { exact: true })).toBeVisible();
  await expect(reportPanel.getByText("species", { exact: true })).toBeVisible();
  await expect(reportPanel.getByText("6", { exact: true })).toBeVisible();
  await expect(reportPanel.getByText("wildlife visits", { exact: true })).toBeVisible();

  const speciesList = reportPanel.locator(".today-report-species-list li");
  await expect(speciesList).toHaveCount(1);
  await expect(speciesList.first()).toContainText("Northern Cardinal");
  await expect(speciesList.first()).toContainText("6 visits");
  // The extra, not-yet-reviewed sightings are disclosed quietly, never
  // folded into "8 visits."
  await expect(speciesList.first()).toContainText("+2 likely");
  await expect(speciesList.first()).not.toContainText("8 visits");

  // House Finch has zero confirmed Visits -- never named in Top visitors,
  // anywhere on the page.
  await expect(page.getByText("House Finch")).toHaveCount(0);

  // Its 4 provisional Visits still count toward the quiet review affordance
  // (2 + 4 = 6), without ever naming the species there either.
  await expect(reportPanel.getByRole("button", { name: "6 items worth reviewing" })).toBeVisible();
});

test("insufficient monitoring today says so honestly, instead of a confident 'no wildlife' claim", async ({
  page,
}) => {
  // Gate C: Daily Place Report v1 regression -- report maturity. Distinct
  // from the coverage pill above (which answers "how complete was today"):
  // this answers "is there even enough monitoring behind a claim of
  // silence yet," so a camera that only just started today does not read
  // as a confident "No wildlife visits yet."
  await completeSetup(page);
  await mockDashboardHeadline(page, { monitored_stream_count: 1, configured_stream_count: 1 });
  await mockPlaceActivityReport(page, {
    maturity: "sparse",
    coverage: {
      period_seconds: 86_400,
      monitored_seconds: 1_800,
      coverage_ratio: 1_800 / 86_400,
      history_available_from: new Date().toISOString(),
      history_is_partial: false,
      gaps: [] as unknown[],
      gaps_truncated: false,
    },
  });

  await page.goto("/");
  const reportPanel = page.locator("section.today-report");
  await expect(reportPanel).toBeVisible();

  await expect(reportPanel.getByText("Not enough monitoring yet to say")).toBeVisible();
  await expect(reportPanel.getByText("No wildlife visits yet today")).toHaveCount(0);
});

test("confirmed-but-unidentified wildlife is distinguished from nothing confirmed at all", async ({
  page,
}) => {
  // Gate C: Daily Place Report v1 regression. A human explicitly confirming
  // "an animal was here" while abstaining on species (an "unknown_bird"/
  // "unknown_animal" correction) is real confirmed truth -- it must not
  // read the same as a day with zero human review at all, and it must
  // never be silently promoted into a fabricated species entry. See
  // "Unknown / unresolved" in docs/place-activity-report-contract.md.
  await completeSetup(page);
  await mockPlaceActivityReport(page, {
    total_visit_count: 2,
    confirmed_wildlife_visit_count: 2,
    confirmed_species_unresolved_visit_count: 2,
    wildlife_visit_count: 2,
    distinct_taxa_count: 0,
    distinct_species_count: 0,
    taxa: [] as unknown[],
  });

  await page.goto("/");
  const reportPanel = page.locator("section.today-report");
  await expect(reportPanel).toBeVisible();

  await expect(reportPanel.getByText("Confirmed wildlife — species not yet identified")).toBeVisible();
  await expect(reportPanel.getByText("2 visits confirmed today", { exact: false })).toBeVisible();
  await expect(reportPanel.getByText("Wildlife activity recorded — nothing confirmed yet")).toHaveCount(0);
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
  expect(["no_data", "sparse", "usable"]).toContain(payload.maturity);
  // Historical Baseline Maturity + New/Regular Species v1: a real,
  // demo-seeded database with no Visits "today" still returns an honest
  // (likely "insufficient") baseline, never a missing field.
  expect(payload.historical_baseline).toBeTruthy();
  expect(["insufficient", "developing", "established"]).toContain(
    payload.historical_baseline.maturity,
  );

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

test("Bird Log is reachable from the persistent nav without enabling Developer Mode", async ({
  page,
}) => {
  // Regression for a real Working App v1 acceptance finding: the Today
  // report's own "Top visitors -> Bird Log" link (above) only renders once
  // topTaxa is non-empty, so on any day with no wildlife visits so far
  // today -- most days, for most yards -- it was the *only* path to Bird
  // Log anywhere in the UI, and Bird Log itself lived in advancedNavItems
  // (predating the product/advanced nav split, carried over alongside
  // genuinely technical pages like Analyzers and Classifier Readiness).
  // A nontechnical user had no persistent, reliable way to reach their
  // Wildlife Journal without first discovering and enabling "Developer
  // Mode." Bird Log now lives in the always-visible primary nav.
  await completeSetup(page);
  await mockPlaceActivityReport(page, {}); // sparse: no taxa today, so the report's own link is absent

  await page.goto("/");
  await expect(page.locator("section.today-report")).toBeVisible();
  await expect(page.locator(".today-report-species")).toHaveCount(0);

  // Developer Mode is off by default -- "Developer tools" is not rendered.
  await expect(page.getByRole("button", { name: /Developer Mode/ })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  await expect(page.getByText("Developer tools")).toHaveCount(0);

  const birdLogNavItem = page.getByRole("button", { name: "Bird Log", exact: true });
  await expect(birdLogNavItem).toBeVisible();
  await birdLogNavItem.click();
  await expect(page).toHaveURL(/\/bird-log$/);
  await expect(page.getByRole("heading", { name: "Wildlife Journal" })).toBeVisible();
});


// Gate C -- Representative Species Evidence v1 (see docs/representative-
// species-evidence-contract.md). `TodayReportPanel` never selects an image
// itself -- it only renders whatever `taxa[].representative_evidence` the
// backend already computed -- so these scenarios exercise the frontend
// presentation contract with synthetic, schema-shaped fixtures, the same
// house convention this whole file already uses. Backend selection/truth
// correctness (provisional-suggestion exclusion, multi-subject isolation,
// missing-media handling, corrected-review eligibility, no-Zone
// selection) is covered by tests/test_place_activity_report_repository.py.

const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

async function routeMediaPreview(page: Page, mediaAssetId: string) {
  await page.route(`**/api/media/${mediaAssetId}/preview`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "image/jpeg",
      body: Buffer.from(TINY_JPEG_BASE64, "base64"),
    }),
  );
}

function representativeEvidence(visitId: string, mediaAssetId: string, capturedAt: string) {
  return {
    visit_id: visitId,
    evidence: {
      media_asset_id: mediaAssetId,
      preview_url: `/api/media/${mediaAssetId}/preview`,
      captured_at: capturedAt,
      relative_position: 0,
      frame_sequence: 0,
      is_primary: true,
      content_type: "image/jpeg",
      width: 1920,
      height: 1080,
      evidence_role: "identification",
      normalized_crop_box: null,
      normalized_track_box: null,
      resolution_provenance: null,
    },
  };
}

test("Today shows a representative image only for species that actually have one, each row its own, never a broken placeholder", async ({
  page,
}) => {
  await completeSetup(page);
  const lastVisitAt = new Date().toISOString();
  await routeMediaPreview(page, "media-cardinal-today");
  await routeMediaPreview(page, "media-finch-today");
  // Deliberately never routed -- the real backend 404s for an unknown id,
  // proving the frontend degrades gracefully rather than showing a broken
  // image icon.
  const brokenMediaAssetId = "media-does-not-exist";

  await mockPlaceActivityReport(page, {
    total_visit_count: 12,
    confirmed_wildlife_visit_count: 12,
    wildlife_visit_count: 12,
    distinct_taxa_count: 4,
    distinct_species_count: 4,
    last_activity_at: lastVisitAt,
    first_activity_at: lastVisitAt,
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
        representative_evidence: representativeEvidence("visit-cardinal-today", "media-cardinal-today", lastVisitAt),
      },
      {
        // A taxon with no confirmed Visit this period that has safe,
        // present evidence -- a completely normal state, never an error.
        label: "carolina_wren",
        display_name: "Carolina Wren",
        category: "bird",
        is_species: true,
        confirmed_visit_count: 3,
        provisional_visit_count: 0,
        total_visit_count: 3,
        first_activity_at: lastVisitAt,
        last_activity_at: lastVisitAt,
        representative_evidence: null,
      },
      {
        // Distinct from the Cardinal above -- proves each row renders its
        // own evidence, never a shared/mixed-up image (the frontend-level
        // analog of the backend's multi-subject-isolation regression).
        label: "house_finch",
        display_name: "House Finch",
        category: "bird",
        is_species: true,
        confirmed_visit_count: 2,
        provisional_visit_count: 0,
        total_visit_count: 2,
        first_activity_at: lastVisitAt,
        last_activity_at: lastVisitAt,
        representative_evidence: representativeEvidence("visit-finch-today", "media-finch-today", lastVisitAt),
        // No-Zone fixture: this taxon's own Zone/time pattern has no Zone
        // support at all -- proves the thumbnail renders correctly
        // alongside (and independently of) Zone/time pattern wording.
        most_active_zone: null,
        most_active_hour: { local_hour: 7, reviewed_visit_count: 2 },
      },
      {
        // Evidence metadata references a real-looking id, but the preview
        // route was deliberately never mocked -- proves a failed image
        // load degrades to no thumbnail, never a broken-image icon.
        label: "blue_jay",
        display_name: "Blue Jay",
        category: "bird",
        is_species: true,
        confirmed_visit_count: 1,
        provisional_visit_count: 0,
        total_visit_count: 1,
        first_activity_at: lastVisitAt,
        last_activity_at: lastVisitAt,
        representative_evidence: representativeEvidence("visit-jay-today", brokenMediaAssetId, lastVisitAt),
      },
    ],
    activity_by_zone: [{ zone_id: null, zone_name: "No Zone", wildlife_visit_count: 12 }],
    busiest_zone: null,
    activity_by_hour: activityByHour({ 7: 8, 14: 4 }),
  });

  await page.goto("/");
  const reportPanel = page.locator("section.today-report");
  await expect(reportPanel).toBeVisible();
  const speciesList = reportPanel.locator(".today-report-species-list li");
  await expect(speciesList).toHaveCount(4);

  // Northern Cardinal: image present, with honest alt text naming the
  // reviewed taxon -- never model speculation.
  const cardinalRow = speciesList.filter({ hasText: "Northern Cardinal" });
  const cardinalImage = cardinalRow.locator("img.today-report-species-thumb");
  await expect(cardinalImage).toBeVisible();
  await expect(cardinalImage).toHaveAttribute("src", new RegExp("media-cardinal-today"));
  await expect(cardinalImage).toHaveAttribute("alt", /Northern Cardinal, reviewed observation/);

  // Carolina Wren: image absent -- no thumbnail element at all, species
  // name/count still fully readable, no error shown.
  const wrenRow = speciesList.filter({ hasText: "Carolina Wren" });
  await expect(wrenRow.locator("img.today-report-species-thumb")).toHaveCount(0);
  await expect(wrenRow).toContainText("Carolina Wren");
  await expect(wrenRow).toContainText("3 visits");

  // House Finch: its own distinct image, not the Cardinal's -- and the
  // no-Zone time-only pattern renders alongside it without conflict.
  const finchRow = speciesList.filter({ hasText: "House Finch" });
  const finchImage = finchRow.locator("img.today-report-species-thumb");
  await expect(finchImage).toBeVisible();
  await expect(finchImage).toHaveAttribute("src", new RegExp("media-finch-today"));
  await expect(finchImage).not.toHaveAttribute("src", new RegExp("media-cardinal-today"));
  await expect(finchRow).toContainText("Most active 7");

  // Blue Jay: the backend claimed evidence, but the image genuinely fails
  // to load -- the thumbnail must disappear entirely, never a broken-image
  // icon left in the row.
  const jayRow = speciesList.filter({ hasText: "Blue Jay" });
  await expect(jayRow.locator("img.today-report-species-thumb")).toHaveCount(0);
  await expect(jayRow).toContainText("Blue Jay");
});
