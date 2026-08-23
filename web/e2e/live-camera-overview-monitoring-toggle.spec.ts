import { expect, test } from "@playwright/test";

// LiveCameraOverview's legacy "Enable monitoring"/"Disable monitoring"
// toggle (RUNTIME SIMPLIFICATION / CODE ARCHAEOLOGY + OSS READINESS v1,
// 2026-08-15).
//
// `runtime` (StreamRuntimeStatus) is sourced from the *legacy* durable
// monitoring-policy subsystem via `GET /api/streams/monitoring-status`,
// which has no provider filter -- it resolves to a real (if `desired_mode:
// "off"`) status for *any* Stream, including a paired Camera Node one that
// has never used that subsystem. A paired Camera Node is exclusively
// governed by the accepted Observation Engine's own Start/Stop control and
// its Stage 7 admission gate (unified_status.resolve_observation_runtime);
// this toggle must never be offered for it -- arming the legacy policy
// would durably start an ungated zone-motion session against the same
// camera, including auto-created Visits with none of that gate's quality
// checks, and keep silently resuming every time Observation later stops.
// This spec proves the toggle is hidden for a camera_node tile and remains
// shown, unchanged, for every other tile -- on both surfaces that embed the
// shared `LiveCameraOverview` component (Dashboard and Streams).
//
// Same house pattern as dashboard-live-camera-ownership.spec.ts: `/api/
// dashboard/summary` is intercepted only to force this one Stream's
// `source_kind`/`playback_kind` the way a real, non-demo camera reports
// them (`isProductActiveCamera` would otherwise hide a `source_kind:
// "demo"` tile behind an extra click a real camera tile never needs); every
// other field passes through the real backend unmodified.

const streamId = "stream-backyard-feeder";

async function completeSetup(page: import("@playwright/test").Page) {
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

async function forceStreamPlaybackKind(
  page: import("@playwright/test").Page,
  playbackKind: string,
) {
  // Pre-existing bug found during Camera / Source + Multi-Camera Maturity
  // v1 validation: `dashboard_summary` has carried a `?local_date=...` query
  // parameter since before this milestone, so a glob with no trailing
  // wildcard never matched the real request -- this route silently never
  // intercepted, and the mutated `source_kind`/`playback_kind` both tests
  // below depend on was never applied. `today-report.spec.ts`'s own
  // identical interception already uses the correct trailing `**`.
  await page.route("**/api/dashboard/summary**", async (route) => {
    const real = await page.request.get("/api/dashboard/summary");
    const body = await real.json();
    const stream = body.streams.find((item: { stream_id: string }) => item.stream_id === streamId);
    if (stream) {
      stream.source_kind = "integration";
      stream.playback_kind = playbackKind;
      stream.availability_status = "live_ready";
      // `isProductActiveCamera` (LiveCameraOverview.tsx) only renders a
      // tile without an extra "Show inactive cameras" click when at least
      // one "this camera is active" signal is true; a camera_node tile
      // gets this for free from its own dedicated clause, but a plain
      // rtsp/local_usb/etc. tile needs an explicit signal here too.
      stream.monitoring_active = true;
    }
    await route.fulfill({ status: real.status(), contentType: "application/json", body: JSON.stringify(body) });
  });
}

test("the monitoring toggle is hidden for a camera_node tile on both Dashboard and Streams", async ({ page }) => {
  await completeSetup(page);
  await forceStreamPlaybackKind(page, "camera_node");

  await page.goto("/");
  const dashboardTile = page.locator(".camera-overview-tile", {
    has: page.getByRole("heading", { name: "Backyard feeder stream" }),
  });
  await expect(dashboardTile).toBeVisible();
  await expect(dashboardTile.getByRole("button", { name: /Enable monitoring|Disable monitoring/ })).toHaveCount(0);

  await page.goto("/streams");
  const streamsTile = page.locator(".camera-overview-tile", {
    has: page.getByRole("heading", { name: "Backyard feeder stream" }),
  });
  await expect(streamsTile).toBeVisible();
  await expect(streamsTile.getByRole("button", { name: /Enable monitoring|Disable monitoring/ })).toHaveCount(0);
});

test("the monitoring toggle remains shown for a non-camera_node tile", async ({ page }) => {
  await completeSetup(page);
  await forceStreamPlaybackKind(page, "rtsp");

  await page.goto("/");
  const tile = page.locator(".camera-overview-tile", {
    has: page.getByRole("heading", { name: "Backyard feeder stream" }),
  });
  await expect(tile).toBeVisible();
  await expect(tile.getByRole("button", { name: /Enable monitoring|Disable monitoring/ })).toBeVisible();
});
