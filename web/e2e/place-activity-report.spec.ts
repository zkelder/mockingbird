import { expect, test, type Page } from "@playwright/test";

// Everyday Discovery / Product Experience v2 (Phase G): the Place Report
// secondary exploration surface over the existing Place Activity Report
// backend (see docs/place-activity-report-contract.md). No route mocking --
// unlike today-report.spec.ts's synthetic fixtures, this proves the real
// frontend request/render against the real, unmodified backend contract
// (the demo-seeded e2e database has no Visits "today," but does have
// historical seed content a wide "This year" period picks up).

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

test("Place Report is reachable from the persistent nav and loads a real report", async ({ page }) => {
  await completeSetup(page);
  await page.goto("/");

  // Place Report is a secondary page under the "Place" destination
  // (Everyday Wildlife Experience & Presentation Refinement v1).
  await page.getByRole("navigation", { name: "Product navigation" }).getByRole("button", { name: "Place", exact: true }).click();
  const navItem = page.getByRole("navigation", { name: "Product navigation" }).getByRole("button", { name: "Place Report", exact: true });
  await expect(navItem).toBeVisible();

  const [response] = await Promise.all([
    page.waitForResponse(
      (candidate) =>
        candidate.url().includes("/api/analytics/place-activity-report") &&
        candidate.request().method() === "POST",
    ),
    navItem.click(),
  ]);
  expect(response.ok()).toBeTruthy();

  await expect(page).toHaveURL(/\/place-report$/);
  await expect(page.getByRole("heading", { name: "Place Report" })).toBeVisible();
  // Two distinct adequacy axes, never conflated into one -- see
  // docs/canonical-new-regular-species-contract.md and docs/place-activity-
  // report-contract.md's own coverage-vs-baseline distinction.
  await expect(page.getByRole("heading", { name: "How much of this period was monitored" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "How much history MockingBird has" })).toBeVisible();
  // No raw analytics/developer terminology leaks into ordinary copy.
  await expect(page.getByText("maturity", { exact: false })).toHaveCount(0);
  await expect(page.getByText(/\binsufficient\b/i)).toHaveCount(0);
});

test("Today links into the Place Report, and Bird Log links back to it", async ({ page }) => {
  await completeSetup(page);

  await page.goto("/");
  await expect(page.locator("section.today-report")).toBeVisible();
  const fromToday = page.getByRole("button", { name: "See the full place report" });
  await expect(fromToday).toBeVisible();
  await fromToday.click();
  await expect(page).toHaveURL(/\/place-report$/);
  await expect(page.getByRole("heading", { name: "Place Report" })).toBeVisible();

  await page.goto("/bird-log");
  const fromBirdLog = page.getByRole("button", { name: "Full Place Report" });
  await expect(fromBirdLog).toBeVisible();
  await fromBirdLog.click();
  await expect(page).toHaveURL(/\/place-report$/);
  await expect(page.getByRole("heading", { name: "Place Report" })).toBeVisible();
});

test("choosing This year widens the period and can surface historical seed activity", async ({ page }) => {
  await completeSetup(page);
  await page.goto("/place-report");
  await expect(page.getByRole("heading", { name: "Place Report" })).toBeVisible();

  const [response] = await Promise.all([
    page.waitForResponse(
      (candidate) =>
        candidate.url().includes("/api/analytics/place-activity-report") &&
        candidate.request().method() === "POST",
    ),
    page.locator('section[aria-label="Choose a period"] select').selectOption("this_year"),
  ]);
  expect(response.ok()).toBeTruthy();
  const payload = await response.json();
  expect(typeof payload.wildlife_visit_count).toBe("number");

  // Whichever real state this period resolves to, the page must render one
  // coherent, non-blank outcome -- never both an empty state and content.
  const emptyState = page.getByRole("heading", { name: /No wildlife activity recorded|Not enough monitoring/ });
  const speciesSection = page.getByRole("heading", { name: "Species seen in this period" });
  await expect(emptyState.or(speciesSection)).toBeVisible();
});
