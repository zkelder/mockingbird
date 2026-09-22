import { expect, test, type Page } from "@playwright/test";

// Historical Baseline Maturity + New/Regular Species v1 (see
// docs/historical-baseline-maturity-contract.md). Bird Log's job is the
// richer, always-available historical detail (distinct confirmed usable
// days, regularity, Place-wide baseline maturity), complementing Today's
// concise per-species status badges (see today-report.spec.ts). Every
// scenario here intercepts `/api/bird-log/journal` and `/api/bird-log/
// journal/{label}` with a fully synthetic, schema-shaped response -- the
// same house pattern today-report.spec.ts already uses for the Place
// Activity Report endpoint -- since driving real accumulated multi-day
// history through the product's own write paths is a backend integration
// concern already covered by tests/test_historical_baseline_repository.py.

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

async function mockJournalOverview(page: Page, overrides: Record<string, unknown>) {
  const now = new Date().toISOString();
  const base = {
    order: "most_recent",
    labels: [
      {
        label: "northern_cardinal",
        display_name: "Northern Cardinal",
        observation_count: 11,
        first_observed_at: new Date(Date.now() - 20 * 24 * 3600 * 1000).toISOString(),
        latest_observed_at: now,
        stream_count: 1,
        zone_count: 1,
        recent_activity: [],
        representative: null,
        distinct_confirmed_usable_days: 3,
        is_regular: true,
      },
    ],
    baseline_maturity: "established",
  };
  const body = { ...base, ...overrides };
  // `getWildlifeJournal` requests `/api/bird-log/journal?order=...` -- the
  // trailing `*` is required so the glob still matches with a query string
  // (unlike the history route below, whose own pattern already needed one
  // for the same reason).
  await page.route("**/api/bird-log/journal*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) }),
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
    observation_count: 11,
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
    distinct_confirmed_usable_days: 3,
    is_regular: true,
    baseline_maturity: "established",
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

test("a regular label's overview card shows Regular here", async ({ page }) => {
  await completeSetup(page);
  await mockJournalOverview(page, {});

  await page.goto("/bird-log");
  const card = page.locator(".journal-label-card").filter({ hasText: "Northern Cardinal" });
  await expect(card).toBeVisible();
  await expect(card.getByText("Regular here")).toBeVisible();
});

test("a not-yet-regular label's overview card shows no regularity badge", async ({ page }) => {
  await completeSetup(page);
  await mockJournalOverview(page, {
    labels: [
      {
        label: "house_finch",
        display_name: "House Finch",
        observation_count: 4,
        first_observed_at: new Date().toISOString(),
        latest_observed_at: new Date().toISOString(),
        stream_count: 1,
        zone_count: 1,
        recent_activity: [],
        representative: null,
        distinct_confirmed_usable_days: 1,
        is_regular: false,
      },
    ],
  });

  await page.goto("/bird-log");
  const card = page.locator(".journal-label-card").filter({ hasText: "House Finch" });
  await expect(card).toBeVisible();
  await expect(card.getByText("Regular here")).toHaveCount(0);
});

test("a label's history detail honestly distinguishes New from First confirmed record, by baseline maturity", async ({
  page,
}) => {
  await completeSetup(page);
  await mockJournalOverview(page, {});
  await mockJournalHistory(page, "northern_cardinal", {
    is_new_label_in_range: true,
    baseline_maturity: "established",
  });

  await page.goto("/bird-log/northern_cardinal");
  await expect(page.getByText("New to your reviewed history in this range")).toBeVisible();
  await expect(page.getByText("First confirmed record so far in this range")).toHaveCount(0);
  await expect(page.getByText("Regular here")).toBeVisible();
});

test("an immature baseline never implies ecological novelty in the history detail notice", async ({ page }) => {
  await completeSetup(page);
  await mockJournalOverview(page, {});
  await mockJournalHistory(page, "northern_cardinal", {
    is_new_label_in_range: true,
    baseline_maturity: "developing",
    is_regular: false,
    distinct_confirmed_usable_days: 1,
  });

  await page.goto("/bird-log/northern_cardinal");
  await expect(page.getByText("First confirmed record so far in this range")).toBeVisible();
  await expect(page.getByText("New to your reviewed history in this range")).toHaveCount(0);
  await expect(page.getByText("hasn't accumulated enough monitored history", { exact: false })).toBeVisible();
});

// Gate C -- Meaningful Change Detection / Baseline Comparison v1 (see
// docs/meaningful-change-detection-contract.md).

test("an overview card with higher recent presence shows the More often recently badge", async ({ page }) => {
  await completeSetup(page);
  await mockJournalOverview(page, {
    labels: [
      {
        label: "northern_cardinal",
        display_name: "Northern Cardinal",
        observation_count: 11,
        first_observed_at: new Date(Date.now() - 20 * 24 * 3600 * 1000).toISOString(),
        latest_observed_at: new Date().toISOString(),
        stream_count: 1,
        zone_count: 1,
        recent_activity: [],
        representative: null,
        distinct_confirmed_usable_days: 3,
        is_regular: true,
        change_status: {
          recent_presence_days: 5,
          recent_usable_day_count: 7,
          reference_presence_days: 3,
          reference_usable_day_count: 14,
          status: "higher_recent_presence",
        },
      },
    ],
  });

  await page.goto("/bird-log");
  const card = page.locator(".journal-label-card").filter({ hasText: "Northern Cardinal" });
  await expect(card.getByText("Regular here")).toBeVisible();
  await expect(card.getByText("More often recently")).toBeVisible();
});

test("a card with no supported change shows no change badge at all", async ({ page }) => {
  await completeSetup(page);
  await mockJournalOverview(page, {
    labels: [
      {
        label: "northern_cardinal",
        display_name: "Northern Cardinal",
        observation_count: 11,
        first_observed_at: new Date(Date.now() - 20 * 24 * 3600 * 1000).toISOString(),
        latest_observed_at: new Date().toISOString(),
        stream_count: 1,
        zone_count: 1,
        recent_activity: [],
        representative: null,
        distinct_confirmed_usable_days: 3,
        is_regular: true,
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

  await page.goto("/bird-log");
  const card = page.locator(".journal-label-card").filter({ hasText: "Northern Cardinal" });
  await expect(card.getByText("More often recently")).toHaveCount(0);
  await expect(card.getByText("Fewer recent visits")).toHaveCount(0);
});

test("a label's history detail shows the recent/reference presence facts and a change badge", async ({ page }) => {
  await completeSetup(page);
  await mockJournalOverview(page, {});
  await mockJournalHistory(page, "northern_cardinal", {
    change_status: {
      recent_presence_days: 1,
      recent_usable_day_count: 7,
      reference_presence_days: 10,
      reference_usable_day_count: 14,
      status: "lower_recent_presence",
    },
  });

  await page.goto("/bird-log/northern_cardinal");
  await expect(page.getByText("Recent: 1 of 7 usable monitored days", { exact: false })).toBeVisible();
  await expect(page.getByText("Reference: 10 of 14 usable monitored days", { exact: false })).toBeVisible();
  await expect(page.getByText("Fewer recent visits")).toBeVisible();
});

test("a label's history detail omits change facts entirely when no change_status is supported", async ({ page }) => {
  await completeSetup(page);
  await mockJournalOverview(page, {});
  await mockJournalHistory(page, "northern_cardinal", { change_status: null });

  await page.goto("/bird-log/northern_cardinal");
  await expect(page.getByText("Recent:", { exact: false })).toHaveCount(0);
  await expect(page.getByText("More often recently")).toHaveCount(0);
  await expect(page.getByText("Fewer recent visits")).toHaveCount(0);
});

// Gate C -- Representative Species Evidence v1 (see docs/representative-
// species-evidence-contract.md). `BirdLogPage`'s label cards render
// whatever `labels[].representative` the backend already computed --
// unchanged frontend code, since this milestone only upgraded the
// backend's *selection* (now the same canonical, quality-aware ranking
// Today uses, not merely "most recent Visit with any evidence") and added
// `resolution_provenance` to the existing evidence shape. No existing e2e
// spec previously exercised a non-null `representative` here (every prior
// scenario used the base fixture's `representative: null`); this closes
// that real, pre-existing coverage gap for the presentation contract these
// scenarios matter for: image present, image absent, each card showing
// only its own evidence (the frontend-observable shape of "a corrected
// review's evidence follows the corrected taxon"), and a zero-Zone label
// unaffected by the thumbnail.

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

function representative(visitId: string, mediaAssetId: string, observedAt: string) {
  return {
    visit_id: visitId,
    event_id: `event-${visitId}`,
    stream_id: "stream-journal",
    stream_name: "Backyard stream",
    source_name: "Backyard camera",
    zone_id: null,
    zone_name: null,
    label: "placeholder",
    display_name: "Placeholder",
    observed_at: observedAt,
    primary_evidence: {
      media_asset_id: mediaAssetId,
      preview_url: `/api/media/${mediaAssetId}/preview`,
      captured_at: observedAt,
      relative_position: 0,
      frame_sequence: 0,
      is_primary: true,
      content_type: "image/jpeg",
      width: 1920,
      height: 1080,
      evidence_role: "identification",
      normalized_crop_box: null,
      normalized_track_box: null,
      resolution_provenance: "synchronized",
    },
  };
}

test("Bird Log shows each label's own representative image, omits the thumbnail honestly when there is none, and a Zone-less label is unaffected", async ({
  page,
}) => {
  await completeSetup(page);
  const now = new Date().toISOString();
  await routeMediaPreview(page, "media-cardinal-journal");
  await routeMediaPreview(page, "media-finch-journal");

  await mockJournalOverview(page, {
    labels: [
      {
        label: "northern_cardinal",
        display_name: "Northern Cardinal",
        observation_count: 6,
        first_observed_at: new Date(Date.now() - 20 * 24 * 3600 * 1000).toISOString(),
        latest_observed_at: now,
        stream_count: 1,
        zone_count: 1,
        recent_activity: [],
        representative: representative("visit-cardinal-journal", "media-cardinal-journal", now),
        distinct_confirmed_usable_days: 3,
        is_regular: true,
      },
      {
        // No confirmed Visit for this label has safe, present evidence --
        // a completely normal state; the fallback placeholder renders,
        // never an error.
        label: "carolina_wren",
        display_name: "Carolina Wren",
        observation_count: 2,
        first_observed_at: new Date(Date.now() - 5 * 24 * 3600 * 1000).toISOString(),
        latest_observed_at: now,
        stream_count: 1,
        zone_count: 1,
        recent_activity: [],
        representative: null,
        distinct_confirmed_usable_days: 1,
        is_regular: false,
      },
      {
        // No-Zone fixture: zero Zones recorded for this label, but it has
        // its own distinct representative image -- proves the thumbnail is
        // unaffected by Zone configuration.
        label: "house_finch",
        display_name: "House Finch",
        observation_count: 1,
        first_observed_at: now,
        latest_observed_at: now,
        stream_count: 1,
        zone_count: 0,
        recent_activity: [],
        representative: representative("visit-finch-journal", "media-finch-journal", now),
        distinct_confirmed_usable_days: 1,
        is_regular: false,
      },
    ],
  });

  await page.goto("/bird-log");
  const cardinalCard = page.locator(".journal-label-card", { hasText: "Northern Cardinal" });
  const wrenCard = page.locator(".journal-label-card", { hasText: "Carolina Wren" });
  const finchCard = page.locator(".journal-label-card", { hasText: "House Finch" });

  const cardinalImage = cardinalCard.locator(".journal-label-image img");
  await expect(cardinalImage).toBeVisible();
  await expect(cardinalImage).toHaveAttribute("src", new RegExp("media-cardinal-journal"));
  await expect(cardinalImage).toHaveAttribute("alt", /Northern Cardinal, reviewed observation/);

  await expect(wrenCard.locator(".journal-label-image img")).toHaveCount(0);
  await expect(wrenCard.locator(".journal-thumbnail-fallback")).toBeVisible();
  await expect(wrenCard.locator(".journal-thumbnail-fallback")).toContainText("No saved thumbnail");

  const finchImage = finchCard.locator(".journal-label-image img");
  await expect(finchImage).toBeVisible();
  await expect(finchImage).toHaveAttribute("src", new RegExp("media-finch-journal"));
  await expect(finchImage).not.toHaveAttribute("src", new RegExp("media-cardinal-journal"));
  await expect(finchCard).toContainText("0 areas");
});
