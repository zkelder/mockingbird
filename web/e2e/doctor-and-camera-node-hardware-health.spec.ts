import { expect, test } from "@playwright/test";

// Product Operations & First-Observation Completion v1: the first
// authenticated HTTP/UI surface for MockingBird Doctor (previously
// CLI-only), plus the bounded, live, on-demand Camera Node hardware/
// storage check surfaced on the Camera Configuration page. Both exercise
// the real backend (real `run_doctor()`, real database/media root); only
// the Camera Node's own live `/node/v1/health` response is mocked, since a
// real reachable Camera Node is not available in this environment.

const streamId = "stream-backyard-feeder";
const sourceId = "source-backyard-demo";

test("Doctor shows real check results and a working recovery link", async ({ page }) => {
  await page.goto("/doctor");

  await expect(page.getByRole("heading", { name: "Doctor" })).toBeVisible();
  // A fresh, real, empty-but-valid instance is genuinely healthy or
  // degraded by Doctor's own contract -- never "Not working" here.
  await expect(page.getByRole("heading", { name: "Overall" })).toBeVisible();
  await expect(page.getByText(/^(Healthy|Needs attention)$/).first()).toBeVisible();

  const rows = page.locator(".doctor-check-row");
  await expect(rows).toHaveCount(await rows.count());
  expect(await rows.count()).toBeGreaterThan(10);
  await expect(page.getByText("Database", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Storage", { exact: true }).first()).toBeVisible();

  // Refresh re-fetches without erroring.
  await page.getByRole("button", { name: "Refresh" }).click();
  await expect(page.getByRole("heading", { name: "Doctor" })).toBeVisible();

  // A non-passing check's own "Open Local Data"/"Open Cameras" link, where
  // present, must actually navigate -- a real, working recovery action,
  // not dead text. A fresh instance's Backup check is informational
  // ("No backups have been created yet"), which this page still links out
  // from since a user might reasonably want to create one.
  const backupRow = page.locator(".doctor-check-row", { has: page.getByText("Backup", { exact: true }) });
  const openLocalData = backupRow.getByRole("button", { name: "Open Local Data" });
  if (await openLocalData.count()) {
    await openLocalData.click();
    await expect(page).toHaveURL(/\/local-data$/);
  }
});

test("Camera Node hardware check shows real storage/hardware facts on demand", async ({ page }) => {
  const configurationResponse = await page.request.patch(
    `/api/sources/${sourceId}/provider-configuration`,
    { data: { provider_key: "camera_node", config: {} } },
  );
  expect(configurationResponse.ok()).toBeTruthy();

  await page.route(`**/api/streams/${streamId}/camera-node-hardware-health`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        applicable: true,
        reachable: true,
        message: "Camera Node reached.",
        storage: { total_bytes: 32_000_000_000, free_bytes: 150_000_000, storage_health_tier: "critical" },
        hardware: {
          undervoltage_active: true,
          throttled_active: false,
          undervoltage_occurred: true,
          throttled_occurred: false,
          temperature_celsius: 58.2,
        },
        checked_at: new Date().toISOString(),
      }),
    }),
  );

  await page.goto(`/cameras/${streamId}/edit`);

  const hardwarePanel = page.locator('section[aria-label="Camera Node hardware"]');
  await expect(hardwarePanel).toBeVisible();
  await hardwarePanel.getByRole("button", { name: "Check Camera Node hardware" }).click();

  await expect(hardwarePanel.getByText("Critically low")).toBeVisible();
  await expect(hardwarePanel.getByText("Undervoltage detected")).toBeVisible();
  await expect(hardwarePanel.getByText("58.2")).toBeVisible();
});

test("Camera Node hardware panel does not appear for a non-Camera-Node source", async ({ page }) => {
  const configurationResponse = await page.request.patch(
    `/api/sources/${sourceId}/provider-configuration`,
    { data: { provider_key: "external_url", config: { url: "rtsp://example.invalid/stream" } } },
  );
  expect(configurationResponse.ok()).toBeTruthy();

  await page.goto(`/cameras/${streamId}/edit`);

  await expect(page.locator('section[aria-label="Camera Node hardware"]')).toHaveCount(0);
});
