import { expect, test, type Page } from "@playwright/test";

// Place Story Deep Dives & Representative Evidence v1 (see docs/place-
// story-deep-dives-representative-evidence-v1-report.md). Proves the
// presentation contract (direct route, reload safety, invalid taxon,
// sparse state, representative image, deep links, phone width,
// accessibility) against synthetic, schema-shaped responses -- the same
// house pattern place-story.spec.ts/place-features.spec.ts already use --
// not the underlying derivation logic itself, which the backend test suite
// (test_place_feature.py, test_year_over_year_comparison_repository.py,
// test_place_story.py) already covers with real seeded data and real HTTP.

// A real, tiny, decodable JPEG (mirrors bird-log-historical-status.spec.ts's
// identical fixture) -- the representative-evidence `<img>` must actually
// load in a real browser for `getByRole("img")` to find it; a fake/un-mocked
// `preview_url` fails to load and silently falls back to the "No image yet"
// placeholder instead, which would make an image-rendering assertion
// vacuously pass against a broken thumbnail.
const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

async function routeMediaPreview(page: Page, mediaAssetId: string) {
  await page.route(`**/api/media/${mediaAssetId}/preview`, (route) =>
    route.fulfill({ status: 200, contentType: "image/jpeg", body: Buffer.from(TINY_JPEG_BASE64, "base64") }),
  );
}

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

function history(overrides: Record<string, unknown> = {}) {
  return {
    label: "northern_cardinal",
    display_name: "Northern Cardinal",
    scope: { timezone_name: "UTC" },
    observation_count: 6,
    first_observation: { observed_at: "2025-08-28T14:00:00Z" },
    latest_observation: { observed_at: "2026-09-01T10:00:00Z" },
    representative: {
      visit_id: "visit-cardinal-1",
      observed_at: "2026-09-01T10:00:00Z",
      primary_evidence: {
        media_asset_id: "media-cardinal-1",
        preview_url: "/api/media/media-cardinal-1/preview",
        captured_at: "2026-09-01T10:00:00Z",
        content_type: "image/jpeg",
        is_primary: true,
        evidence_role: "identification",
        relative_position: 0,
      },
    },
    busiest_stream: { id: "stream-1", name: "Back Yard", count: 5 },
    busiest_zone: { id: "zone-1", name: "Bird Bath Zone", count: 4 },
    peak_activity_hour: 8,
    stream_breakdown: [],
    zone_breakdown: [],
    activity_by_hour: [],
    is_new_label_in_range: false,
    distinct_confirmed_usable_days: 6,
    is_regular: true,
    baseline_maturity: "established",
    historical_status: "regular",
    change_status: null,
    activity_library_drilldown: { review_filter: "confirmed_wildlife", confirmed_label: "northern_cardinal" },
    gallery: { order: "newest", observations: [], has_more: false, next_offset: null },
    ...overrides,
  };
}

function emptyPlaceStory() {
  return {
    generated_at: NOW,
    period_start_at: NOW,
    period_end_at: NOW,
    entries: [],
    has_more: false,
    next_offset: null,
    total_matched: 0,
    is_early_experience: false,
  };
}

function emptyYearOverYear() {
  return {
    generated_at: NOW,
    place: {
      policy_version: 1,
      current_period: { start_date: "2026-09-01", end_date: "2026-09-30", is_complete: false },
      prior_period: { start_date: "2025-09-01", end_date: "2025-09-30", is_complete: true },
      status: "insufficient_prior_history",
      information_class: "inferred",
    },
    notable_species_changes: [],
    taxon_comparison: null,
  };
}

async function mockTaxonStoryApis(
  page: Page,
  options: { history?: Record<string, unknown> | null; historyStatus?: number } = {},
) {
  await page.route("**/api/bird-log/journal/*", (route) => {
    if (options.historyStatus && options.historyStatus !== 200) {
      return route.fulfill({
        status: options.historyStatus,
        contentType: "application/json",
        body: JSON.stringify({ detail: "not found" }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(options.history ?? history()),
    });
  });
  await page.route("**/api/place/year-over-year*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(emptyYearOverYear()) }),
  );
  await page.route("**/api/place/story*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(emptyPlaceStory()) }),
  );
}

test("direct navigation to a taxon's story renders its header", async ({ page }) => {
  await completeSetup(page);
  await mockTaxonStoryApis(page);
  await routeMediaPreview(page, "media-cardinal-1");

  await page.goto("/place-story/taxon/northern_cardinal");
  await expect(page.getByRole("heading", { name: "Northern Cardinal", level: 1 })).toBeVisible();
  await expect(page.getByText("Regular here")).toBeVisible();
  await expect(page.getByText("First observed here on Aug", { exact: false })).toBeVisible();
  await expect(page.getByText("Frequently recorded near the Bird Bath Zone", { exact: false })).toBeVisible();
});

test("reload keeps the same taxon story reachable", async ({ page }) => {
  await completeSetup(page);
  await mockTaxonStoryApis(page);

  await page.goto("/place-story/taxon/northern_cardinal");
  await expect(page.getByRole("heading", { name: "Northern Cardinal", level: 1 })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Northern Cardinal", level: 1 })).toBeVisible();
});

test("an invalid taxon label gives an honest not-found state, never a fake narrative", async ({ page }) => {
  await completeSetup(page);
  await mockTaxonStoryApis(page, { historyStatus: 404 });

  await page.goto("/place-story/taxon/not-a-real-taxon");
  await expect(page.getByText("No taxon story here")).toBeVisible();
  await expect(page.getByText(/error/i)).toHaveCount(0);
});

test("a valid taxon with zero confirmed observations shows a sparse, honest state", async ({ page }) => {
  await completeSetup(page);
  await mockTaxonStoryApis(page, {
    history: history({
      observation_count: 0,
      first_observation: null,
      latest_observation: null,
      representative: null,
      busiest_stream: null,
      busiest_zone: null,
      historical_status: null,
      is_regular: false,
    }),
  });

  await page.goto("/place-story/taxon/brown_thrasher");
  await expect(page.getByText("No confirmed observations yet")).toBeVisible();
  await expect(page.getByRole("img")).toHaveCount(0);
});

test("the representative image renders with a reviewed-truth alt text", async ({ page }) => {
  await completeSetup(page);
  await mockTaxonStoryApis(page);
  await routeMediaPreview(page, "media-cardinal-1");

  await page.goto("/place-story/taxon/northern_cardinal");
  const image = page.getByRole("img", { name: /Northern Cardinal, reviewed observation/ });
  await expect(image).toBeVisible();
});

test("a Place Story taxon link opens that taxon's own story", async ({ page }) => {
  await completeSetup(page);
  // One conditional handler for the shared `/api/place/story` pattern: the
  // Place-wide Story page's own unfiltered fetch gets a real entry to click
  // through; the Taxon Story page's own `?taxon=` timeline fetch gets an
  // (irrelevant to this test) empty page. Two separate `page.route` calls
  // for the identical glob would silently shadow each other (Playwright
  // dispatches the most-recently-registered matching handler), so this
  // must be one handler, not two.
  await page.route("**/api/place/story*", (route) => {
    const isTaxonScoped = new URL(route.request().url()).searchParams.has("taxon");
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        generated_at: NOW,
        period_start_at: NOW,
        period_end_at: NOW,
        entries: isTaxonScoped
          ? []
          : [
              {
                id: "first-seen:northern_cardinal",
                kind: "first_seen",
                group: "wildlife",
                event_date: "2025-03-10",
                event_end_date: null,
                title: "First Northern Cardinal observation",
                summary: "First reviewed observation of Northern Cardinal recorded at this Place.",
                information_class: "reviewed",
                importance: "major",
                taxon_label: "northern_cardinal",
                taxon_display_name: "Northern Cardinal",
                feature_id: null,
                feature_name: null,
                visit_id: null,
                zone_id: null,
                zone_name: null,
                source_id: null,
                detail_refs: {},
              },
            ],
        has_more: false,
        next_offset: null,
        total_matched: isTaxonScoped ? 0 : 1,
        is_early_experience: false,
      }),
    });
  });
  await page.route("**/api/bird-log/journal/*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(history()) }),
  );
  await page.route("**/api/place/year-over-year*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(emptyYearOverYear()) }),
  );
  await routeMediaPreview(page, "media-cardinal-1");

  await page.goto("/place-story");
  await page.getByRole("button", { name: "Northern Cardinal’s story" }).click();
  await expect(page).toHaveURL(/\/place-story\/taxon\/northern_cardinal/);
  await expect(page.getByRole("heading", { name: "Northern Cardinal", level: 1 })).toBeVisible();
});

test("the Taxon Story page stays usable and free of horizontal overflow at phone width", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 700 });
  await completeSetup(page);
  await mockTaxonStoryApis(page);

  await page.goto("/place-story/taxon/northern_cardinal");
  await expect(page.getByRole("heading", { name: "Northern Cardinal", level: 1 })).toBeVisible();
  const bodyScrollWidth = await page.evaluate(() => document.body.scrollWidth);
  const viewportWidth = await page.evaluate(() => window.innerWidth);
  expect(bodyScrollWidth).toBeLessThanOrEqual(viewportWidth + 1); // +1: sub-pixel rounding tolerance
});

test("the page heading receives focus so a keyboard/screen-reader user lands on the new subject", async ({
  page,
}) => {
  await completeSetup(page);
  await mockTaxonStoryApis(page);

  await page.goto("/place-story/taxon/northern_cardinal");
  await expect(page.getByRole("heading", { name: "Northern Cardinal", level: 1 })).toBeFocused();
});
