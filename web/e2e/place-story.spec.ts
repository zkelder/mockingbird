import { expect, test, type Page } from "@playwright/test";

// Place Story & Seasonal Timeline v1 (see docs/place-story-seasonal-
// timeline-v1-report.md). This spec proves the presentation contract
// (empty/early-experience state, month grouping, filters, card content,
// evidence drill-down, basic accessibility) against a synthetic,
// schema-shaped response -- the same house pattern place-features.spec.ts/
// today-report.spec.ts already use -- not the underlying derivation logic
// itself, which tests/test_place_story.py and tests/test_place_story_
// repository.py already cover with real seeded data and real HTTP.
//
// The empty-state case is deliberately mocked too (unlike place-features.
// spec.ts's real-backend empty state): unlike Place Features, the
// e2e demo-seeded backend's own bounded demo Visit data can itself
// populate wildlife-derived Place Story entries, so relying on the real
// backend for "nothing recorded yet" would be nondeterministic.

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

function emptyResponse() {
  return {
    generated_at: NOW,
    period_start_at: NOW,
    period_end_at: NOW,
    entries: [],
    has_more: false,
    next_offset: null,
    total_matched: 0,
    is_early_experience: true,
  };
}

function entry(overrides: Record<string, unknown> = {}) {
  return {
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
    visit_id: "visit-e2e-1",
    zone_id: null,
    zone_name: null,
    source_id: null,
    detail_refs: {},
    ...overrides,
  };
}

async function mockPlaceStory(page: Page, body: Record<string, unknown>) {
  await page.route("**/api/place/story*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) }),
  );
}

test("a brand-new Place shows a calm, honest early-experience state", async ({ page }) => {
  await completeSetup(page);
  await mockPlaceStory(page, emptyResponse());

  await page.goto("/place-story");
  await expect(page.getByRole("heading", { name: "Place Story" })).toBeVisible();
  await expect(page.getByText("Your Place Story is just beginning")).toBeVisible();
  await expect(page.getByRole("button", { name: "See the full Place Report" })).toBeVisible();
});

test("populated Story groups entries by month and renders plain-language cards", async ({ page }) => {
  await completeSetup(page);
  await mockPlaceStory(page, {
    generated_at: NOW,
    period_start_at: NOW,
    period_end_at: NOW,
    entries: [
      entry(),
      entry({
        id: "feature-change:evt-1",
        kind: "feature_change",
        group: "place",
        event_date: "2025-04-02",
        title: "Sunflower Feeder added",
        summary: "Sunflower Feeder added.",
        importance: "major",
        taxon_label: null,
        taxon_display_name: null,
        feature_id: "feature-1",
        feature_name: "Sunflower Feeder",
        visit_id: null,
        detail_refs: { change_event_id: "evt-1" },
      }),
    ],
    has_more: false,
    next_offset: null,
    total_matched: 2,
    is_early_experience: false,
  });

  await page.goto("/place-story");
  await expect(page.getByText("2 moments in this period")).toBeVisible();
  // Two distinct month headings, newest first.
  await expect(page.getByRole("heading", { name: "April 2025" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "March 2025" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "First Northern Cardinal observation" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Sunflower Feeder added" })).toBeVisible();
  // The internal `kind` enum never leaks as raw text -- only the mapped label.
  await expect(page.getByText("first_seen", { exact: true })).toHaveCount(0);
});

test("a wildlife entry's evidence link opens the underlying Visit", async ({ page }) => {
  await completeSetup(page);
  await mockPlaceStory(page, {
    generated_at: NOW, period_start_at: NOW, period_end_at: NOW,
    entries: [entry()], has_more: false, next_offset: null, total_matched: 1, is_early_experience: false,
  });
  await page.route("**/api/visits/visit-e2e-1*", (route) => route.continue());

  await page.goto("/place-story");
  await page.getByRole("button", { name: "View evidence" }).click();
  await expect(page).toHaveURL(/\/visits\/visit-e2e-1/);
});

test("category filter re-requests the backend with the mapped kind list", async ({ page }) => {
  await completeSetup(page);
  await mockPlaceStory(page, {
    generated_at: NOW, period_start_at: NOW, period_end_at: NOW,
    entries: [entry()], has_more: false, next_offset: null, total_matched: 1, is_early_experience: false,
  });

  await page.goto("/place-story");
  await expect(page.getByRole("heading", { name: "First Northern Cardinal observation" })).toBeVisible();

  const requestPromise = page.waitForRequest((request) => request.url().includes("/api/place/story?"));
  await page.getByLabel("Category").selectOption("place");
  const request = await requestPromise;
  const url = new URL(request.url());
  expect(url.searchParams.getAll("kind").sort()).toEqual(["feature_change", "phenology"]);
});

test("the Place Story stays usable and free of horizontal overflow at phone width", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 700 });
  await completeSetup(page);
  await mockPlaceStory(page, {
    generated_at: NOW, period_start_at: NOW, period_end_at: NOW,
    entries: [entry()], has_more: false, next_offset: null, total_matched: 1, is_early_experience: false,
  });

  await page.goto("/place-story");
  await expect(page.getByRole("heading", { name: "First Northern Cardinal observation" })).toBeVisible();
  await expect(page.getByLabel("Period")).toBeVisible();
  await expect(page.getByLabel("Category")).toBeVisible();
  const bodyScrollWidth = await page.evaluate(() => document.body.scrollWidth);
  const viewportWidth = await page.evaluate(() => window.innerWidth);
  expect(bodyScrollWidth).toBeLessThanOrEqual(viewportWidth + 1); // +1: sub-pixel rounding tolerance
});

test("Place Story is reachable from Today and keeps accessible heading order", async ({ page }) => {
  await completeSetup(page);
  await mockPlaceStory(page, emptyResponse());

  await page.goto("/");
  await page.getByRole("button", { name: "See the Place Story" }).click();
  await expect(page).toHaveURL(/\/place-story/);

  // h1 (page title) precedes any h2 (month headings / section headings) --
  // logical heading order even when the list is empty and no h2 exists yet.
  const h1 = page.getByRole("heading", { level: 1 });
  await expect(h1).toHaveText("Place Story");
});
