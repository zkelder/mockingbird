import { expect, test, type Page } from "@playwright/test";

// Place Story Deep Dives & Representative Evidence v1 (see docs/place-
// story-deep-dives-representative-evidence-v1-report.md). Proves the
// presentation contract for this product's first dedicated, URL-addressable
// Feature detail page against synthetic, schema-shaped responses -- the
// same house pattern place-features.spec.ts/place-story.spec.ts already
// use -- not the underlying comparison/representative-evidence computation
// itself, which tests/test_place_feature.py already covers with real
// seeded data and real HTTP.

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

function feature(overrides: Record<string, unknown> = {}) {
  return {
    id: "feature-story-e2e-1",
    feature_type: "water",
    name: "Bird Bath",
    note: null,
    is_active: true,
    installed_date: "2026-06-01",
    removed_date: null,
    source_id: null,
    zone_id: null,
    feeder_food_type: null,
    information_class: "reviewed",
    provenance: "user_manual_entry",
    created_at: NOW,
    updated_at: NOW,
    observation_links: [
      { id: "link-1", source_id: "source-1", source_name: "Patio Camera", source_archived: false, zone_id: "zone-1", zone_name: "Bird Bath Zone", created_at: NOW },
    ],
    ...overrides,
  };
}

function detail(overrides: Record<string, unknown> = {}) {
  return {
    feature: feature(),
    changes: [
      {
        event: {
          id: "change-1",
          feature_id: "feature-story-e2e-1",
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
        environmental_comparison: null,
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
    representative_evidence: {
      visit_id: "visit-bath-1",
      stream_id: "stream-1",
      stream_name: "Patio Camera",
      evidence: {
        media_asset_id: "media-bath-1",
        preview_url: "/api/media/media-bath-1/preview",
        captured_at: "2026-06-05T09:00:00Z",
        content_type: "image/jpeg",
        is_primary: true,
        evidence_role: "identification",
        relative_position: 0,
      },
    },
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

async function mockFeatureStoryApis(
  page: Page,
  options: { detail?: Record<string, unknown> | null; detailStatus?: number } = {},
) {
  await page.route("**/api/place/features/feature-story-e2e-1/detail", (route) => {
    if (options.detailStatus && options.detailStatus !== 200) {
      return route.fulfill({
        status: options.detailStatus,
        contentType: "application/json",
        body: JSON.stringify({ detail: "not found" }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(options.detail ?? detail()),
    });
  });
  await page.route("**/api/place/story*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(emptyPlaceStory()) }),
  );
}

test("direct navigation to a Feature's story renders its header", async ({ page }) => {
  await completeSetup(page);
  await mockFeatureStoryApis(page);

  await page.goto("/place-story/feature/feature-story-e2e-1");
  await expect(page.getByRole("heading", { name: "Bird Bath", level: 1 })).toBeVisible();
  await expect(page.getByText("Observed by: Patio Camera", { exact: false })).toBeVisible();
  await expect(
    page.getByText("Confirmed wildlife activity was higher in the 7-day windows after this change than before."),
  ).toBeVisible();
});

test("reload keeps the same Feature story reachable", async ({ page }) => {
  await completeSetup(page);
  await mockFeatureStoryApis(page);

  await page.goto("/place-story/feature/feature-story-e2e-1");
  await expect(page.getByRole("heading", { name: "Bird Bath", level: 1 })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Bird Bath", level: 1 })).toBeVisible();
});

test("an invalid Feature id gives an honest not-found state", async ({ page }) => {
  await completeSetup(page);
  await mockFeatureStoryApis(page, { detailStatus: 404 });

  await page.goto("/place-story/feature/does-not-exist");
  await expect(page.getByText("No Feature story here")).toBeVisible();
  await expect(page.getByText(/error/i)).toHaveCount(0);
});

test("a new Feature with no links, changes, or evidence shows a sparse, honest state", async ({ page }) => {
  await completeSetup(page);
  await mockFeatureStoryApis(page, {
    detail: detail({
      feature: feature({ observation_links: [] }),
      changes: [],
      recent_yield: null,
      representative_evidence: null,
    }),
  });

  await page.goto("/place-story/feature/feature-story-e2e-1");
  await expect(page.getByText("no camera linked yet", { exact: false })).toBeVisible();
  await expect(page.getByText("No changes recorded for this Feature yet.")).toBeVisible();
  await expect(page.getByText("Not enough monitoring linked yet", { exact: false })).toBeVisible();
  await expect(page.getByRole("img")).toHaveCount(0);
});

test("an archived observation link is labeled, never hidden", async ({ page }) => {
  await completeSetup(page);
  await mockFeatureStoryApis(page, {
    detail: detail({
      feature: feature({
        observation_links: [
          { id: "link-1", source_id: "source-1", source_name: "Garden Camera", source_archived: true, zone_id: null, zone_name: null, created_at: NOW },
        ],
      }),
    }),
  });

  await page.goto("/place-story/feature/feature-story-e2e-1");
  await expect(page.getByText("Garden Camera (archived)", { exact: false })).toBeVisible();
});

test("the representative image renders with a non-species-overstating alt text", async ({ page }) => {
  await completeSetup(page);
  await mockFeatureStoryApis(page);
  await routeMediaPreview(page, "media-bath-1");

  await page.goto("/place-story/feature/feature-story-e2e-1");
  const image = page.getByRole("img", { name: /Recent wildlife at Bird Bath, reviewed observation/ });
  await expect(image).toBeVisible();
});

test("a Feature link from the Place Report opens that Feature's own story", async ({ page }) => {
  await completeSetup(page);
  await page.route("**/api/place/features", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([feature()]) }),
  );
  await page.route("**/api/place/feature-changes*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) }),
  );
  await mockFeatureStoryApis(page);

  await page.goto("/place-report");
  await expect(page.getByRole("heading", { name: "Features & changes" })).toBeVisible();
  await page.getByRole("button", { name: "View Bird Bath story" }).click();
  await expect(page).toHaveURL(/\/place-story\/feature\/feature-story-e2e-1/);
  await expect(page.getByRole("heading", { name: "Bird Bath", level: 1 })).toBeVisible();
});

test("the Feature Story page stays usable and free of horizontal overflow at phone width", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 700 });
  await completeSetup(page);
  await mockFeatureStoryApis(page);

  await page.goto("/place-story/feature/feature-story-e2e-1");
  await expect(page.getByRole("heading", { name: "Bird Bath", level: 1 })).toBeVisible();
  const bodyScrollWidth = await page.evaluate(() => document.body.scrollWidth);
  const viewportWidth = await page.evaluate(() => window.innerWidth);
  expect(bodyScrollWidth).toBeLessThanOrEqual(viewportWidth + 1); // +1: sub-pixel rounding tolerance
});

test("the page heading receives focus for keyboard/screen-reader users", async ({ page }) => {
  await completeSetup(page);
  await mockFeatureStoryApis(page);

  await page.goto("/place-story/feature/feature-story-e2e-1");
  await expect(page.getByRole("heading", { name: "Bird Bath", level: 1 })).toBeFocused();
});
