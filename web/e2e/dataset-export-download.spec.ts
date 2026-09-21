import { expect, test } from "@playwright/test";

// Pre-Release Trust & Correctness Correction v1 (FLOW-5): Dataset Export
// produced/showed its manifest as inline JSON only, with no way to actually
// save it -- confirmed live. Proves a real browser download now completes,
// with a sensible filename and the same JSON content already shown inline.

test("Dataset Export manifest can be downloaded as a real file", async ({ page }) => {
  await page.goto("/exports");
  await expect(page.getByRole("heading", { name: "Dataset Exports" })).toBeVisible();

  const exportName = `E2E download proof ${Date.now()}`;
  await page.getByLabel("Export name").fill(exportName);
  await page.getByRole("button", { name: "Generate manifest" }).click();

  await expect(page.getByRole("heading", { name: "Manifest preview" })).toBeVisible();
  const downloadButton = page.getByRole("button", { name: "Download manifest JSON" });
  await expect(downloadButton).toBeVisible();

  const [download] = await Promise.all([page.waitForEvent("download"), downloadButton.click()]);

  const filename = download.suggestedFilename();
  expect(filename.startsWith("e2e-download-proof-")).toBe(true);
  expect(filename.endsWith(".json")).toBe(true);
  expect(filename).toMatch(/\d{4}-\d{2}-\d{2}/); // the export's created-at date, somewhere in the name

  const downloadPath = await download.path();
  expect(downloadPath).not.toBeNull();
  const fs = await import("node:fs/promises");
  const savedContent = JSON.parse(await fs.readFile(downloadPath as string, "utf-8"));
  expect(savedContent.export.name).toBe(exportName);
  expect(Array.isArray(savedContent.records)).toBe(true);

  await expect(page.getByText("Manifest download started.")).toBeVisible();
});
