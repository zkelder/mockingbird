import { expect, test } from "@playwright/test";

// Whole-Product UI / Accessibility / Performance Closure v1: closes the
// bounded gap docs/acoustic-productization-licensing-field-acceptance-v1
// -report.md disclosed -- "the two status endpoints that could tell a user
// 'microphone/model unavailable' have zero frontend callers anywhere."
// `GET /api/product/health`'s new `acoustic` field is exercised by focused
// backend tests (tests/test_product_health.py); this proves the frontend
// actually renders it on the one page every user sees first.

test("MockingBird status shows a calm 'Not configured' acoustic row by default, never blocking readiness", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "MockingBird status" })).toBeVisible();

  const healthPanel = page.locator("section.product-health-panel");
  await expect(healthPanel).toContainText("Acoustic");
  await expect(healthPanel).toContainText("Not configured");

  // Acoustic is optional -- its status must never read as a failure or
  // block the overall "Ready" state.
  await expect(healthPanel.getByText("Ready", { exact: true })).toBeVisible();

  const health = await page.request.get("/api/product/health");
  expect(health.ok()).toBeTruthy();
  const body = await health.json();
  expect(body.acoustic).toEqual({
    configured: false,
    status: "not_configured",
    detail:
      "No microphone is configured for any camera. Acoustic identification is optional -- visual observation is unaffected.",
  });
  expect(body.ready).toBe(true);
});
