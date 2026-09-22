import { expect, test, type Page } from "@playwright/test";

// Analytics & Local Data Truth Consistency v1: `_analytics_summary` (and
// `_local_data_status`, which reuses its `event_count`/`visit_count`/
// `needs_review_count` directly) previously counted the seeded demo
// Source's own two fabricated Events/Visits toward "Events"/"Visits"/
// "Needs review"/"Reviewed species" on both `/analytics` and
// `/local-data` -- the same defect family Review Queue Count Truth
// Consistency v1 closed for the Review Queue/Dashboard/imports.
//
// This suite runs its ~18+ spec files sequentially against one shared,
// already-populated instance (see `playwright.config.ts`'s own
// `globalSetup`), so a hard "reads exactly zero" assertion here would be
// order-dependent on whatever earlier specs already did to that shared
// instance -- not a meaningful regression proof, and liable to break as
// the suite grows. This spec instead proves the fix the way that shared
// -instance constraint actually allows: a real, distinctive action taken
// through the real UI/API must move these real, rendered numbers by
// exactly the genuine amount, on both pages, regardless of whatever else
// already happened in this instance's history. (The demo-only-install
// "reads exactly zero" contract itself is proven with true fixture
// isolation in `tests/test_demo_source_exclusion.py` -- the correct layer
// for that specific claim, and the one Tier 1 already covers exhaustively.)

const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

function metricValue(page: Page, label: string) {
  // Both `/analytics` and `/local-data` render several independent
  // `.metric-card` grids on one page (this page's own summary,
  // `WildlifeInsightsPanel`, `ZoneInsightsPanel`) whose *other* cards'
  // labels/details can contain this card's label as a substring (e.g.
  // "Visits" inside "Unresolved Visits"/"Confirmed bird Visits") -- a plain
  // `hasText` substring filter on the whole card is a Playwright strict
  // -mode violation once more than one matches. `.metric-label`'s own text
  // is exactly the label, nothing else, so match it exactly instead.
  return page
    .locator(".metric-card")
    .filter({ has: page.getByText(label, { exact: true }).and(page.locator(".metric-label")) })
    .locator("strong");
}

test("a real correction moves Analytics and Local Data's real counts, never the seeded demo Source's own count", async ({
  page,
}) => {
  const before = await page.request.get("/api/analytics/summary");
  expect(before.ok()).toBeTruthy();
  const beforeSummary = await before.json();

  // A dedicated, real (non-demo) Source/Stream -- `POST /api/sources`
  // mirrors the plain "Add Camera" flow, matching real users, not this
  // suite's shared demo fixture Stream (`kind == "demo"`), which is
  // always `legacy_activity`/demo-excluded by design.
  const created = await page.request.post("/api/sources", {
    data: { name: `Analytics Truth Consistency Fixture ${Date.now()}` },
  });
  expect(created.ok()).toBeTruthy();
  const { stream } = await created.json();

  const imported = await page.request.post("/api/media/import", {
    multipart: {
      file: {
        name: "analytics-truth-consistency.jpg",
        mimeType: "image/jpeg",
        buffer: Buffer.from(TINY_JPEG_BASE64, "base64"),
      },
      stream_id: stream.id,
      subject_label: "unknown_animal",
    },
  });
  expect(imported.ok()).toBeTruthy();
  const { visit } = await imported.json();

  // A distinctive, real target-species correction -- both a genuine
  // "Needs review" resolution (import creates it needs-review; this
  // corrects it, so the net `needs_review_count` change is zero) and a
  // genuine new `species_counts`/"Reviewed species" entry.
  const corrected = await page.request.post("/api/review-labels", {
    data: {
      review_origin: "human",
      target_type: "visit",
      target_id: visit.id,
      label: "blue_jay",
    },
  });
  expect(corrected.ok()).toBeTruthy();

  await page.goto("/analytics");
  // `exact: true` -- the page's own `<h1>Insights</h1>` (from its `PageHeader`
  // `title`) shares this page with `WildlifeInsightsPanel`'s `<h2>Wildlife
  // Insights</h2>` and `ZoneInsightsPanel`'s `<h2>Zone & feeder insights</h2>`;
  // a substring match against "Insights" resolves to all three (Playwright
  // strict-mode violation).
  await expect(page.getByRole("heading", { name: "Insights", exact: true })).toBeVisible();

  await expect(metricValue(page, "Events")).toHaveText(String(beforeSummary.event_count + 1));
  await expect(metricValue(page, "Visits")).toHaveText(String(beforeSummary.visit_count + 1));
  await expect(metricValue(page, "Needs review")).toHaveText(String(beforeSummary.needs_review_count));
  // "Blue Jay" alone is another Playwright strict-mode violation here -- it
  // legitimately appears in several unrelated places at once (a "New
  // labels" comparison note, review-history cards, a filter dropdown
  // option). `.bar-row` is this page's own "Reviewed species and labels"
  // list item (driven directly by `species_counts`/`label_display_names`,
  // the fields this milestone corrects) and is the one place this
  // assertion actually means to check.
  await expect(page.locator(".bar-row").filter({ hasText: "Blue Jay" })).toBeVisible();

  await page.goto("/local-data");
  await expect(page.getByRole("heading", { name: "Local Data" })).toBeVisible();
  await expect(metricValue(page, "Events")).toHaveText(String(beforeSummary.event_count + 1));
  await expect(metricValue(page, "Visits")).toHaveText(String(beforeSummary.visit_count + 1));
  await expect(metricValue(page, "Needs review")).toHaveText(String(beforeSummary.needs_review_count));
});
