import { expect, test } from "@playwright/test";

// Live-view / monitoring ownership projection.
//
// Real finding (2026-08-14/15 live Camera Node investigation): Observation
// Engine deliberately pauses a Stream's legacy live-camera session before it
// takes exclusive Camera Node ownership (`LiveCameraSessionManager
// .pause_for_observation`) -- a healthy, expected hand-off, proven live on
// real Pi/Windows/CUDA hardware to leave Camera Node capture, Observation
// Engine's own heartbeat, and detector activity all continuously healthy.
// But the *legacy* live-view panel on Stream Detail previously read raw
// `liveSession.status`/frame facts with no awareness of that hand-off, so an
// already-open live view (`CurrentFrameView`, polling the now-409ing
// current-frame endpoint every second) forced `liveViewState` to the more
// alarming "no_frames"/"Failed" signal -- masking the deliberate-pause
// signal the page already had -- and a compact "Camera: Paused" fact read as
// though the whole camera had failed, right next to the Observation panel
// correctly saying "Observing". This spec proves the ownership-aware fix.
//
// `page.route` interception (already used elsewhere, e.g.
// visit-evidence-zoom.spec.ts) stands in for the specific paused-while-
// observing wire-state combination, which requires real Camera Node
// hardware to reach in this environment; every other endpoint (the Stream
// itself, zones, events, recent visits, species packs) is the real backend.
// This spec does not re-prove the ownership *transition* mechanism itself
// (`pause_for_observation`/`resume_after_observation`) -- that is covered
// for real, without mocks, both by tests/test_engine_runtime.py's dedicated
// pause/resume suite and by this investigation's own live hardware run.

const streamId = "stream-backyard-feeder";
const sourceId = "source-backyard-demo";

const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";
const TINY_JPEG_BUFFER = Buffer.from(TINY_JPEG_BASE64, "base64");

/** Every field `LiveCameraSessionStatusResponse` requires, defaulted to a
 * quiet "running" session; override only what one test actually varies. */
function buildLiveSessionStatus(overrides: Record<string, unknown> = {}) {
  return {
    stream_id: streamId,
    source_id: sourceId,
    playback_kind: "camera_node",
    status: "running",
    started_at: new Date().toISOString(),
    last_frame_at: new Date().toISOString(),
    latest_frame_age_ms: 200,
    newest_frame_age_ms: 200,
    frame_count: 5,
    clients_connected: 0,
    monitor_running: false,
    auto_create_review_candidates: false,
    auto_identify_review_candidates: false,
    automatic_identification_status: "off",
    auto_review_quiet_seconds: 30,
    auto_review_min_detections: 1,
    auto_review_created_count: 0,
    open_activity_session_count: 0,
    open_activity_zone_names: [],
    ready_activity_session_count: 0,
    current_activity_session: null,
    current_activity_session_id: null,
    activity_detection_count: 0,
    activity_near_miss_count: 0,
    activity_frames_evaluated_count: 0,
    activity_candidate_frame_count: 0,
    activity_saved_candidate_count: 0,
    activity_session_duration_seconds: 0,
    activity_ready_for_review: false,
    activity_manual_review_needed: false,
    activity_fine_motion_applied: false,
    activity_near_miss: false,
    activity_review_activity_created: false,
    last_activity: null,
    last_motion_result: null,
    max_runtime_seconds: 1800,
    persistent: false,
    camera_settings: {},
    message: "Camera session is running. Live view, capture, and monitoring share these frames.",
    warnings: [],
    ...overrides,
  };
}

/** Every field `ObservationSessionStatusResponse` requires, defaulted to a
 * healthy, actively-observing session (real hardware shape, 2026-08-14/15
 * live run: continuous `camera_connected`/climbing `advanced.counterfactual
 * _ledger.raw_detections` for 13.6 minutes straight). */
function buildObservationStatus(overrides: Record<string, unknown> = {}) {
  return {
    stream_id: streamId,
    state: "observing",
    observing: true,
    message: "MockingBird is watching this camera for wildlife.",
    camera_connected: true,
    camera_message: "Connected to the Camera Node.",
    engine_available: true,
    engine_message: "Observation Engine is running.",
    runtime_available: true,
    started_at: new Date().toISOString(),
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

test("an already-open live view survives Observation Engine taking camera ownership", async ({
  page,
}) => {
  const configurationResponse = await page.request.patch(
    `/api/sources/${sourceId}/provider-configuration`,
    { data: { provider_key: "camera_node", config: {} } },
  );
  expect(configurationResponse.ok()).toBeTruthy();

  const realPlaybackResponse = await page.request.get(`/api/streams/${streamId}/playback`);
  expect(realPlaybackResponse.ok()).toBeTruthy();
  const playback = await realPlaybackResponse.json();
  // Only the two facts `isCameraNodePlayback` actually reads -- a real
  // pairing handshake is not needed to prove the *presentation* contract.
  playback.status = "live_ready";
  playback.playback_kind = "camera_node";
  await page.route(`**/api/streams/${streamId}/playback`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(playback) }),
  );

  // Mutable across the test: the legacy session starts "running" (a normal,
  // healthy live view the user already opened) and flips to "paused" mid-
  // test, standing in for a real Start Observing call pausing it out from
  // under an already-watching user -- the exact sequence the live
  // investigation reproduced on real hardware.
  let paused = false;

  await page.route(`**/api/streams/${streamId}/live-session/status`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        buildLiveSessionStatus(
          paused
            ? {
                status: "paused",
                frame_count: 5,
                message: "Live view is paused while Observation Engine is watching this camera.",
              }
            : {},
        ),
      ),
    }),
  );

  await page.route(`**/api/streams/${streamId}/live-session/current-frame*`, (route) => {
    if (paused) {
      return route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Camera session is not active; viewing never starts monitoring." }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "image/jpeg",
      headers: {
        "X-MockingBird-Frame-Sequence": "5",
        "X-MockingBird-Frame-Captured-At": new Date().toISOString(),
        "X-MockingBird-Frame-Age-Ms": "150",
        "X-MockingBird-Frame-Width": "8",
        "X-MockingBird-Frame-Height": "8",
        "X-MockingBird-Frame-State": "live",
      },
      body: TINY_JPEG_BUFFER,
    });
  });

  await page.route(`**/api/streams/${streamId}/observation/status`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(buildObservationStatus(paused ? {} : { state: "stopped", observing: false, message: "Not observing.", camera_connected: false, engine_available: false, engine_message: "Observation Engine has not started yet.", started_at: null })),
    }),
  );

  await page.goto(`/streams/${streamId}`);

  // A paired Camera Node Stream auto-opens its cached-still live view on
  // load (viewing never starts monitoring -- see the dedicated effect in
  // StreamDetailPage), so it is already open and streaming before
  // Observation ever touches the camera, exactly like the mandated live
  // reproduction sequence (baseline live view, then Start Observing).
  await expect(page.locator(".current-frame-status.is-live")).toBeVisible();
  await expect(page.getByRole("button", { name: "Hide live view" })).toBeVisible();
  await expect(page.getByText("Current camera frame unavailable")).toHaveCount(0);

  // Start Observing (simulated): the legacy session is now paused for
  // exclusive Observation ownership.
  paused = true;

  const observationPanel = page.locator("section.observation-control-panel");
  await expect(observationPanel.getByText("Observing", { exact: true })).toBeVisible({ timeout: 10_000 });

  // The core regression: a healthy hand-off must never read as a camera
  // failure, and the previously-masked "no_frames"/"Current camera frame
  // unavailable" signal must never appear just because an already-open live
  // view kept polling a now-intentionally-paused endpoint.
  await expect(page.getByText("Current camera frame unavailable")).toHaveCount(0);
  await expect(page.getByText("No frames", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Live preview paused")).toBeVisible();
  // Appears twice by design: once in the media placeholder that replaced
  // `CurrentFrameView`, once in the primary-status inline notice.
  await expect(
    page.getByText("Live view is paused while Observation Engine is watching this camera."),
  ).toHaveCount(2);

  const cameraStatus = page.locator('[aria-label="Camera and monitor status"]');
  await expect(cameraStatus).toContainText("Camera Observing");
  await expect(cameraStatus).not.toContainText("Camera Paused");

  const pill = page.locator(".status-pill", { hasText: "Paused (Observation running)" });
  await expect(pill).toBeVisible();
  await expect(pill).toHaveClass(/status-quiet/);
  await expect(pill).not.toHaveClass(/status-review/);

  // The legacy frame counter is explicitly scoped and marked stale, never
  // presented as Observation's own live processing count.
  await expect(page.getByText(/Live preview frames.*5.*\(paused\)/)).toBeVisible();

  // Stop Observing (simulated): ownership returns, live view recovers
  // without any page reload or backend restart.
  paused = false;
  await expect(page.getByText("Live preview paused")).toHaveCount(0, { timeout: 10_000 });
  await expect(page.locator(".current-frame-status.is-live")).toBeVisible();

  // Mandatory second cycle (the live investigation's own brief: "The prior
  // issue may be a re-entry/lifecycle defect"): the same hand-off must
  // behave identically the second time, with no leftover state from the
  // first pause/resume.
  paused = true;
  await expect(observationPanel.getByText("Observing", { exact: true })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText("Current camera frame unavailable")).toHaveCount(0);
  await expect(page.getByText("No frames", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Live preview paused")).toBeVisible();
  await expect(cameraStatus).toContainText("Camera Observing");

  paused = false;
  await expect(page.getByText("Live preview paused")).toHaveCount(0, { timeout: 10_000 });
  await expect(page.locator(".current-frame-status.is-live")).toBeVisible();
  await expect(page.getByText("Current camera frame unavailable")).toHaveCount(0);
});
