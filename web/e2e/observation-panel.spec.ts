import { expect, test } from "@playwright/test";

const streamId = "stream-backyard-feeder";
const sourceId = "source-backyard-demo";

const FORBIDDEN_BASIC_VOCABULARY = [
  "SnapshotObservationProvider",
  "frame-driven-onnx-cuda",
  "provider_generation",
  "ONNX Runtime",
  "ONNX",
  "CUDA",
  "policy_revision",
  "camera_node_engine",
  "live_monitoring",
  "snapshot_monitor",
];

test("Stream Detail renders one basic Observation experience for a Stream with no runtime yet", async ({
  page,
}) => {
  // Explicit, order-independent precondition: a Source with no live camera
  // to observe, regardless of what an earlier spec file already configured
  // on this shared demo Source.
  const configurationResponse = await page.request.patch(
    `/api/sources/${sourceId}/provider-configuration`,
    { data: { provider_key: "manual_media", config: {} } },
  );
  expect(configurationResponse.ok()).toBeTruthy();

  await page.goto(`/streams/${streamId}`);

  const observationHeadings = page.getByRole("heading", { name: "Observation", exact: true });
  await expect(observationHeadings).toHaveCount(1);
  // The old competing panels are gone -- one basic Observation experience only.
  await expect(page.getByRole("heading", { name: "Camera health", exact: true })).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Monitoring continuity", exact: true })).toHaveCount(0);

  const panel = page.locator("section.observation-control-panel");
  await expect(panel).toBeVisible();
  await expect(panel.getByRole("button", { name: "Start observing" })).toHaveCount(0);

  const visibleText = await panel.innerText();
  for (const forbidden of FORBIDDEN_BASIC_VOCABULARY) {
    expect(visibleText).not.toContain(forbidden);
  }

  // Advanced diagnostics is present but collapsed by default.
  const details = panel.locator("details.review-diagnostic-details");
  await expect(details).toBeVisible();
  await expect(details).not.toHaveAttribute("open", "");
});

test("unified Start/Stop routes an external_url Stream to the existing Snapshot monitor", async ({
  page,
}) => {
  const configurationResponse = await page.request.patch(
    `/api/sources/${sourceId}/provider-configuration`,
    {
      data: {
        provider_key: "external_url",
        // Loopback with nothing listening: capture attempts fail fast and
        // deterministically (connection refused) instead of risking a slow
        // hang against an unreachable LAN address that could stall the
        // shared single-process dev server for other tests in this run.
        config: { url: "http://127.0.0.1:9/still.jpg" },
      },
    },
  );
  expect(configurationResponse.ok()).toBeTruthy();

  await page.goto(`/streams/${streamId}`);
  const panel = page.locator("section.observation-control-panel");
  await expect(panel).toBeVisible();

  const startButton = panel.getByRole("button", { name: "Start observing" });
  await expect(startButton).toBeVisible();
  await startButton.click();

  await expect(panel.getByText("Observing", { exact: true })).toBeVisible({ timeout: 10_000 });
  const stopButton = panel.getByRole("button", { name: "Stop observing" });
  await expect(stopButton).toBeVisible();

  const visibleText = await panel.innerText();
  for (const forbidden of FORBIDDEN_BASIC_VOCABULARY) {
    expect(visibleText).not.toContain(forbidden);
  }

  await stopButton.click();
  await expect(panel.getByRole("button", { name: "Start observing" })).toBeVisible({ timeout: 10_000 });

  // Advanced diagnostics stays collapsed even after Start/Stop; opening it
  // is where runtime/provider vocabulary is allowed to appear.
  const details = panel.locator("details.review-diagnostic-details");
  await expect(details).not.toHaveAttribute("open", "");
  await details.locator("summary").click();
  await expect(details).toHaveAttribute("open", "");
  await expect(details.getByText(/Runtime: Snapshot Monitor/i)).toBeVisible();
});

test("Site-Specific Learning & Local Adaptation: advanced diagnostics shows restrained local-learning status and controls", async ({
  page,
}) => {
  const configurationResponse = await page.request.patch(
    `/api/sources/${sourceId}/provider-configuration`,
    { data: { provider_key: "manual_media", config: {} } },
  );
  expect(configurationResponse.ok()).toBeTruthy();

  await page.goto(`/streams/${streamId}`);
  const panel = page.locator("section.observation-control-panel");
  await expect(panel).toBeVisible();

  const details = panel.locator("details.review-diagnostic-details");
  await details.locator("summary").click();
  await expect(details).toHaveAttribute("open", "");

  // A brand-new Stream, honestly: enabled by default, nothing to act on yet.
  await expect(details.getByText("Local learning: Not enough reviewed history yet")).toBeVisible();

  const visibleText = await panel.innerText();
  for (const forbidden of FORBIDDEN_BASIC_VOCABULARY) {
    expect(visibleText).not.toContain(forbidden);
  }
  // Never model-training/ML-engineering jargon (see the governing milestone
  // brief's Phase 6) -- even inside the advanced/support view.
  for (const jargon of ["tensor", "embedding", "optimizer", "gradient", "epoch", "region_id", "occurrence_count"]) {
    expect(visibleText.toLowerCase()).not.toContain(jargon);
  }

  await details.getByRole("button", { name: "Disable local adjustment" }).click();
  await expect(details.getByText("Local learning: Local adjustment disabled")).toBeVisible();
  await expect(details.getByRole("button", { name: "Enable local adjustment" })).toBeVisible();

  await details.getByRole("button", { name: "Reset local learning" }).click();
  // Reset is a clean no-op with no accumulated history yet -- the enabled
  // toggle it does not touch stays exactly where the operator left it.
  await expect(details.getByText("Local learning: Local adjustment disabled")).toBeVisible();
});
