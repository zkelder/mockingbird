import { expect, test } from "@playwright/test";

test("a correction becomes Bird Log and reviewed export truth", async ({ page }) => {
  await page.goto("/review");

  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();
  const visitCard = page
    .locator("article.queue-card")
    .filter({ has: page.getByRole("heading", { name: "Review bird visit" }) });
  await expect(visitCard).toHaveCount(1);
  await expect(visitCard).toContainText("Backyard feeder stream");
  await expect(visitCard).toContainText("Feeder");

  await visitCard.getByLabel("Species correction").fill("blue_jay");
  await visitCard.getByRole("button", { name: "Resolve species" }).click();

  const successPanel = page.locator(".correction-success-panel");
  await expect(successPanel.getByRole("heading", { name: "Correction saved" })).toBeVisible();
  await expect(successPanel).toContainText("Blue Jay");
  await expect(successPanel).toContainText("visit-bird-feeder-001");

  await page.getByRole("button", { name: "Bird Log" }).click();
  await expect(page).toHaveURL(/\/bird-log$/);
  await expect(page.getByRole("heading", { name: "Bird Log" })).toBeVisible();

  const birdLogEntry = page.locator("article.bird-log-entry").filter({ hasText: "Blue Jay" });
  await expect(birdLogEntry).toHaveCount(1);
  await expect(birdLogEntry).toContainText("Backyard demo source");
  await expect(birdLogEntry).toContainText("Backyard feeder stream");
  await expect(birdLogEntry).toContainText("Feeder");

  await birdLogEntry.getByRole("button", { name: "Export reviewed data" }).click();
  await expect(page).toHaveURL(/\/exports$/);
  await expect(page.getByRole("heading", { name: "Dataset Exports" })).toBeVisible();

  await page.getByLabel("Export name").fill("Primary product loop proof");
  await page.getByRole("button", { name: "Generate manifest" }).click();

  await expect(page.getByText("Reviewed local dataset manifest generated in memory.")).toBeVisible();
  const exportedVisit = page
    .locator("article.record-card")
    .filter({ hasText: "visit-bird-feeder-001" });
  await expect(exportedVisit).toHaveCount(1);
  await expect(exportedVisit).toContainText("Blue Jay");
  await expect(exportedVisit).toContainText("source-backyard-demo");
  await expect(exportedVisit).toContainText("stream-backyard-feeder");
  await expect(exportedVisit).toContainText("Feeder (Feeder)");
  await expect(exportedVisit).toContainText("Reviewed");
  await expect(exportedVisit).toContainText("Ready for local dataset export");
});
