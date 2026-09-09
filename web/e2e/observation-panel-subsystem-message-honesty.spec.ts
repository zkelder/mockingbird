import { expect, test } from "@playwright/test";

// Product Operations & First-Observation Completion v1: `ObservationControlPanel`'s
// own needs-attention detail box was hardcoded to `status.camera_message`
// regardless of which subsystem actually failed. For a Camera Node Stream
// whose camera is connected but whose Observation Engine detector/GPU/model
// failed to load, this showed the reassuring "Camera Node is paired and
// configured." directly below the panel's own top-line `status.message`,
// which already, correctly, displays the real engine failure text (see
// `_EngineSession.snapshot`'s "headline whichever subsystem is actually
// blocking" precedence, engine_runtime.py) -- an internally inconsistent
// panel: an alarming pill and a correct headline, immediately followed by a
// reassuring detail line about a subsystem that was never the problem.
//
// `page.route` interception for `observation/status` stands in for a real
// detector/GPU load failure (mirroring `live-preview-ownership.spec.ts`'s
// own established `buildObservationStatus` pattern) -- every other endpoint
// is the real backend.

const streamId = "stream-backyard-feeder";
const sourceId = "source-backyard-demo";

const GPU_FAILURE_MESSAGE =
  "This PC's GPU/graphics driver does not meet Observation Engine requirements " +
  "(a compatible NVIDIA GPU and driver are required). (onnx_cuda_unavailable)";
const STALE_CAMERA_SUCCESS_TEXT = "Camera Node is paired and configured.";

function buildObservationStatus(overrides: Record<string, unknown> = {}) {
  return {
    stream_id: streamId,
    state: "needs_attention",
    observing: false,
    message: GPU_FAILURE_MESSAGE,
    camera_connected: true,
    camera_message: STALE_CAMERA_SUCCESS_TEXT,
    engine_available: false,
    engine_message: GPU_FAILURE_MESSAGE,
    runtime_available: true,
    started_at: null,
    retry_action: false,
    counts: {
      track_updates_observed: 0,
      evidence_candidates_observed: 0,
      proposals_observed: 0,
      candidates_created: 0,
      candidates_suppressed: 0,
      suppressed_reasons: [],
    },
    advanced: { runtime_kind: "camera_node_engine" },
    ...overrides,
  };
}

test("the needs-attention detail box shows the real engine failure, not a stale camera success message", async ({
  page,
}) => {
  const configurationResponse = await page.request.patch(
    `/api/sources/${sourceId}/provider-configuration`,
    { data: { provider_key: "camera_node", config: {} } },
  );
  expect(configurationResponse.ok()).toBeTruthy();

  await page.route(`**/api/streams/${streamId}/observation/status`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(buildObservationStatus()),
    }),
  );

  await page.goto(`/streams/${streamId}`);

  const observationPanel = page.locator("section.observation-control-panel");
  await expect(observationPanel).toBeVisible();

  // Camera and Observation are still reported separately (unaffected by
  // this fix) -- the camera itself stayed healthy.
  await expect(observationPanel.getByText("Camera Healthy")).toBeVisible();
  await expect(observationPanel.getByText("Observation Needs attention")).toBeVisible();

  // The core regression: the detail box must show the real engine failure,
  // never the stale "paired and configured" success text for a subsystem
  // that was never the problem.
  const detailBox = observationPanel.locator(".continuity-message").first();
  await expect(detailBox).toContainText("GPU/graphics driver");
  await expect(observationPanel.getByText(STALE_CAMERA_SUCCESS_TEXT)).toHaveCount(0);
});

test("the needs-attention detail box still shows the real camera failure when the camera itself is the problem", async ({
  page,
}) => {
  const configurationResponse = await page.request.patch(
    `/api/sources/${sourceId}/provider-configuration`,
    { data: { provider_key: "camera_node", config: {} } },
  );
  expect(configurationResponse.ok()).toBeTruthy();

  const cameraFailureMessage = "Camera Node connection stopped: repeated failures.";
  await page.route(`**/api/streams/${streamId}/observation/status`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        buildObservationStatus({
          message: cameraFailureMessage,
          camera_connected: false,
          camera_message: cameraFailureMessage,
          engine_available: true,
          engine_message: "Ready",
        }),
      ),
    }),
  );

  await page.goto(`/streams/${streamId}`);

  const observationPanel = page.locator("section.observation-control-panel");
  const detailBox = observationPanel.locator(".continuity-message").first();
  await expect(detailBox).toContainText("repeated failures");
  await expect(detailBox).not.toContainText("GPU");
});
