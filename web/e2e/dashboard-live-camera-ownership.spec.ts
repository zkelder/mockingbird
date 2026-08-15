import { expect, test } from "@playwright/test";

// Dashboard's Live Camera Overview / ownership projection (WORKING APP v1:
// CAMERA NODE RECOVERY + DASHBOARD OWNERSHIP CONSISTENCY, 2026-08-15).
//
// live-preview-ownership.spec.ts already proved and fixed this exact
// masking bug on Stream Detail: Observation Engine deliberately pauses a
// Stream's legacy live-camera session before taking exclusive Camera Node
// ownership (`LiveCameraSessionManager.pause_for_observation`) -- a
// healthy, expected hand-off, not a camera failure. `LiveCameraOverview`'s
// tile for a `camera_node` Stream mounts `CurrentFrameView` unconditionally
// (no "Show live view" click needed, unlike Stream Detail), so it polled
// the now-409ing current-frame endpoint every second and showed "Current
// camera frame unavailable" -- and the tile's top status pill, sourced
// entirely from the *legacy* monitoring-policy subsystem that Observation
// Engine never touches, kept reading "Monitoring stopped" throughout. This
// spec proves the ownership-aware fix, and that a genuine Camera Node
// failure still reads as a failure (never masked by the same fix).
//
// `page.route` interception (same house pattern as live-preview-ownership
// .spec.ts) stands in for the specific paused-while-observing wire-state
// combination, which requires real Camera Node hardware to reach in this
// environment. `/api/dashboard/summary` is intercepted only to force this
// one Stream's `playback_kind`/`availability_status`/`source_kind` the way
// a real paired, non-demo Camera Node reports them (its real provider
// configuration is intentionally left empty, exactly like the Stream
// Detail spec, since a real pairing handshake is not needed to prove the
// *presentation* contract) -- every other field in the real response
// (visits, species, storage, headline) passes through unmodified.

const streamId = "stream-backyard-feeder";
const sourceId = "source-backyard-demo";

const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";
const TINY_JPEG_BUFFER = Buffer.from(TINY_JPEG_BASE64, "base64");

/** Every field `LiveCameraSessionStatusResponse` requires, defaulted to a
 * quiet "running" session; override only what one test actually varies.
 * (Same defaults as live-preview-ownership.spec.ts.) */
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

test("Dashboard's Live Camera Overview survives Observation Engine taking camera ownership, and still shows a genuine failure", async ({
  page,
}) => {
  const configurationResponse = await page.request.patch(
    `/api/sources/${sourceId}/provider-configuration`,
    { data: { provider_key: "camera_node", config: {} } },
  );
  expect(configurationResponse.ok()).toBeTruthy();

  // The dashboard route (only) gates on setup completion (App.tsx); the
  // shared e2e fixture's demo-seeded database was never driven through the
  // real onboarding wizard, so `/` would otherwise render "Welcome to
  // MockingBird" instead of the Dashboard this spec needs. Overridden here,
  // not mutated on the real backend, so no other spec in this shared,
  // single-worker suite is affected.
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

  // Force this one Stream's dashboard-summary entry to read like a real,
  // non-demo, paired Camera Node -- `_dashboard_live_preview`/
  // `get_stream_playback_status` would otherwise report "not configured"
  // for this fixture's intentionally empty provider config (see the
  // top-of-file comment), and `isProductActiveCamera` hides any
  // `source_kind: "demo"` tile behind an extra "Show demo data" click that
  // a real Camera Node tile never needs. Every other field (visits,
  // species, storage, headline, other Streams) is the real backend,
  // re-fetched fresh on every poll.
  await page.route("**/api/dashboard/summary", async (route) => {
    const real = await page.request.get("/api/dashboard/summary");
    const body = await real.json();
    const stream = body.streams.find((item: { stream_id: string }) => item.stream_id === streamId);
    if (stream) {
      stream.source_kind = "integration";
      stream.playback_kind = "camera_node";
      stream.availability_status = "live_ready";
      stream.availability_message = "Paired Camera Node is ready for an authenticated bounded snapshot preview.";
      stream.live_preview = {
        kind: "backend_session",
        available: true,
        media_kind: "image",
        preview_url: null,
        message: "Select Show live view to open this local preview.",
      };
    }
    await route.fulfill({ status: real.status(), contentType: "application/json", body: JSON.stringify(body) });
  });

  // Mutable across the test: starts a normal healthy "running" session,
  // moves through "paused" (Observation ownership) and "failed" (a genuine,
  // persistent Camera Node outage independently confirmed live against the
  // real Pi on 2026-08-15 -- see the Working App v1 Camera Node Recovery +
  // Dashboard Ownership Consistency milestone) in turn.
  let sessionState: "running" | "paused" | "failed" = "running";

  await page.route(`**/api/streams/${streamId}/live-session/status`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        buildLiveSessionStatus(
          sessionState === "paused"
            ? {
                status: "paused",
                frame_count: 5,
                message: "Live view is paused while Observation Engine is watching this camera.",
              }
            : sessionState === "failed"
              ? {
                  status: "failed",
                  frame_count: 0,
                  last_error: "node_unavailable",
                  message: "node_unavailable",
                }
              : {},
        ),
      ),
    }),
  );

  await page.route(`**/api/streams/${streamId}/live-session/current-frame*`, (route) => {
    if (sessionState !== "running") {
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

  await page.goto("/");

  const tile = page.locator(".camera-overview-tile", { has: page.getByRole("heading", { name: "Backyard feeder stream" }) });
  await expect(tile).toBeVisible();

  // Baseline: a normal healthy camera_node tile shows a live snapshot, not
  // the paused placeholder, and its pill is not the ownership-aware label.
  await expect(tile.locator(".current-frame-status.is-live")).toBeVisible();
  await expect(tile.getByText("Live preview paused")).toHaveCount(0);
  await expect(tile.getByText("Current camera frame unavailable")).toHaveCount(0);
  await expect(tile.locator(".status-pill", { hasText: "Observing" })).toHaveCount(0);

  // Start Observing (simulated): the legacy session is now paused for
  // exclusive Observation ownership. The tile must read as actively
  // healthy, never as a failed or globally-paused camera.
  sessionState = "paused";

  const pill = tile.locator(".status-pill", { hasText: "Observing" });
  await expect(pill).toBeVisible({ timeout: 10_000 });
  await expect(pill).toHaveClass(/status-good/);
  await expect(pill).not.toHaveClass(/status-review/);

  await expect(tile.getByText("Current camera frame unavailable")).toHaveCount(0);
  await expect(tile.getByText("Live preview paused")).toBeVisible();
  await expect(
    tile.getByText("Live view is paused while Observation Engine is watching this camera."),
  ).toBeVisible();
  await expect(tile.getByText(/^Actual:/)).toContainText("Observing");

  // Stop Observing (simulated): ownership returns, the tile recovers to a
  // normal live snapshot without a page reload or backend restart.
  sessionState = "running";
  await expect(tile.getByText("Live preview paused")).toHaveCount(0, { timeout: 10_000 });
  await expect(tile.locator(".current-frame-status.is-live")).toBeVisible();

  // Mandatory second cycle: the same hand-off behaves identically the
  // second time, with no leftover state from the first pause/resume.
  sessionState = "paused";
  await expect(pill).toBeVisible({ timeout: 10_000 });
  await expect(tile.getByText("Current camera frame unavailable")).toHaveCount(0);
  await expect(tile.getByText("Live preview paused")).toBeVisible();

  sessionState = "running";
  await expect(tile.getByText("Live preview paused")).toHaveCount(0, { timeout: 10_000 });
  await expect(tile.locator(".current-frame-status.is-live")).toBeVisible();

  // The core guardrail: a *genuine* Camera Node failure (real, persistent,
  // independently reproduced live against the real Pi this same milestone)
  // is never swallowed by the same ownership-aware fix. `status ===
  // "failed"` is not `"paused"`, so the tile must fall straight back
  // through to the original, honestly alarming presentation.
  sessionState = "failed";
  await expect(tile.getByText("Current camera frame unavailable")).toBeVisible({ timeout: 10_000 });
  await expect(tile.getByText("Live preview paused")).toHaveCount(0);
  await expect(pill).toHaveCount(0);
});
