import { expect, test, type Page } from "@playwright/test";

// v0.1 Acquisition/Ingest Interoperability Closure v1 ("II.4 ONVIF",
// "II.18 Onboarding"). CameraSetupPage.tsx's guided "Add Camera" flow
// gains a bounded ONVIF discovery sub-flow, following the same "discover
// -> select -> normal name/zone/finish flow" shape camera_node's pairing
// sub-flow already establishes. `POST /api/onvif/discover-profiles` is
// mocked with a synthetic, schema-shaped response -- the same house
// pattern today-report.spec.ts already uses -- since no real ONVIF
// camera is available in this environment; the real backend contract
// (SOAP parsing, LAN-only host validation, credential redaction) is
// already covered by tests/test_onvif_client.py and the ONVIF scenarios
// in tests/test_stream_playback_contract.py.

async function mockOnvifDiscovery(page: Page) {
  await page.route("**/api/onvif/discover-profiles", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "available",
        message: "Found 2 media profile(s).",
        device_manufacturer: "Acme",
        device_model: "CamPro 4K",
        device_firmware_version: "1.0",
        profiles: [
          {
            profile_token: "main",
            profile_name: "Main stream",
            advertised_width: 1920,
            advertised_height: 1080,
            encoding: "H264",
            stream_uri: "rtsp://192.168.50.10:554/onvif1",
          },
          {
            profile_token: "sub",
            profile_name: "Sub stream",
            advertised_width: 640,
            advertised_height: 360,
            encoding: "H264",
            stream_uri: "rtsp://192.168.50.10:554/onvif2",
          },
        ],
      }),
    }),
  );
}

test("ONVIF network camera is selectable and offers discovery before the generic field form", async ({
  page,
}) => {
  await page.goto("/cameras/setup");
  await expect(page.getByRole("heading", { name: "Add Camera" })).toBeVisible();

  const cameraType = page.getByLabel("Camera type");
  await expect(cameraType.locator('option[value="onvif"]')).toHaveText("ONVIF network camera");
  await cameraType.selectOption("onvif");

  await expect(page.locator("strong", { hasText: "ONVIF network camera" })).toBeVisible();
  await expect(page.getByLabel("Camera host")).toBeVisible();
  await expect(page.getByLabel("Username")).toBeVisible();
  await expect(page.getByLabel("Password")).toBeVisible();
  await expect(page.getByRole("button", { name: "Discover this camera" })).toBeDisabled();
});

test("discovering an ONVIF camera lists its profiles, and selecting one enables Finish through the ordinary RTSP path", async ({
  page,
}) => {
  await mockOnvifDiscovery(page);
  await page.route("**/api/camera-setup/validate", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ready",
        message: "Ready.",
        can_continue: true,
        preview_available: false,
        creates_events: false,
        creates_visits: false,
        creates_media_assets: false,
        creates_truth: false,
      }),
    }),
  );

  await page.goto("/cameras/setup");
  await page.getByLabel("Camera type").selectOption("onvif");
  await page.getByLabel("Camera host").fill("192.168.50.10");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("hunter2");

  const discoverButton = page.getByRole("button", { name: "Discover this camera" });
  await expect(discoverButton).toBeEnabled();
  await discoverButton.click();

  await expect(page.getByText("Acme CamPro 4K — 2 video profiles")).toBeVisible();
  const profileSelect = page.getByLabel("Video profile");
  await expect(profileSelect.locator("option")).toHaveCount(3); // placeholder + 2 profiles
  await expect(profileSelect.locator('option[value="main"]')).toHaveText("Main stream — 1920×1080");

  await profileSelect.selectOption("main");
  await expect(
    page.getByText("Profile selected. This camera will play through MockingBird's RTSP bridge", {
      exact: false,
    }),
  ).toBeVisible();

  // The credential the user typed never leaks into the page itself.
  await expect(page.locator("body")).not.toContainText("hunter2");

  await page.getByLabel("Camera name").fill("Backyard ONVIF camera");
  await page.getByRole("button", { name: "Check camera settings" }).click();
  await expect(page.getByText("Ready.")).toBeVisible();

  const finishButton = page.getByRole("button", { name: /Finish/ });
  await expect(finishButton).toBeEnabled();
});

test("an ONVIF camera that rejects authentication shows an honest, actionable message", async ({
  page,
}) => {
  await page.route("**/api/onvif/discover-profiles", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "authentication_rejected",
        message: "The camera rejected this username/password.",
        profiles: [],
      }),
    }),
  );

  await page.goto("/cameras/setup");
  await page.getByLabel("Camera type").selectOption("onvif");
  await page.getByLabel("Camera host").fill("192.168.50.10");
  await page.getByLabel("Username").fill("admin");
  await page.getByLabel("Password").fill("wrong");
  await page.getByRole("button", { name: "Discover this camera" }).click();

  await expect(page.getByText("The camera rejected this username/password.")).toBeVisible();
  await expect(page.getByLabel("Video profile")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Finish/ })).toBeDisabled();
  await expect(page.getByText("Discover this camera and choose a video profile.")).toBeVisible();
});
