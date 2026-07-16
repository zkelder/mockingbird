import { expect, test } from "@playwright/test";

test("a ranked species suggestion becomes correction, Bird Log, and export truth", async ({
  page,
}) => {
  const suggestionResponse = await page.request.post("/api/species-suggestions", {
    data: {
      adapter_id: "bioclip_2",
      adapter_name: "BioCLIP 2",
      alternatives: [
        {
          calibrated: false,
          common_name: "Blue Jay",
          label: "blue jay (Cyanocitta cristata)",
          rank: 2,
          scientific_name: "Cyanocitta cristata",
          score: 0.21,
          score_kind: "candidate_relative_softmax",
          suggested_label: "blue_jay",
        },
      ],
      confidence: 0.37,
      evidence_region: {
        calibrated: false,
        coordinate_space: "full_frame_normalized",
        height: 0.2,
        score_semantics: "candidate_relative_softmax",
        source: "activity",
        width: 0.2,
        x: 0.4,
        y: 0.3,
      },
      event_id: "event-bird-feeder-001",
      rank: 1,
      source_id: "source-backyard-demo",
      stream_id: "stream-backyard-feeder",
      suggested_common_name: "Northern Cardinal",
      suggested_label: "northern_cardinal",
      suggested_scientific_name: "Cardinalis cardinalis",
      visit_id: "visit-bird-feeder-001",
    },
  });
  expect(suggestionResponse.ok()).toBeTruthy();
  const suggestion = await suggestionResponse.json();

  await page.goto("/review");

  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();
  const visitCard = page
    .locator("article.queue-card")
    .filter({ has: page.getByRole("heading", { name: "Review bird visit" }) });
  await expect(visitCard).toHaveCount(1);
  await expect(visitCard).toContainText("Backyard feeder stream");
  await expect(visitCard).toContainText("Feeder");

  const identificationSummary = visitCard
    .locator("summary")
    .filter({ hasText: "Optional identification assist" });
  const identification = identificationSummary.locator("..");
  await identificationSummary.click();
  await expect(identification).toContainText("Northern Cardinal");
  await expect(identification).toContainText("Cardinalis cardinalis");
  await expect(identification).toContainText("uncalibrated score");
  await identification
    .getByRole("button", {
      name: "Prefill correction with rank 2, Blue Jay",
    })
    .click();
  await expect(visitCard.getByLabel("Species correction")).toHaveValue("blue_jay");

  await visitCard.getByRole("button", { name: "Resolve species" }).click();

  const successPanel = page.locator(".correction-success-panel");
  await expect(successPanel.getByRole("heading", { name: "Correction saved" })).toBeVisible();
  await expect(successPanel).toContainText("Blue Jay");
  await expect(successPanel).toContainText("visit-bird-feeder-001");

  await expect
    .poll(async () => {
      const response = await page.request.get(
        `/api/species-suggestions/${suggestion.id}`,
      );
      expect(response.ok()).toBeTruthy();
      return (await response.json()).status;
    })
    .toBe("accepted");

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
