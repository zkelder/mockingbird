import { expect, test } from "@playwright/test";

const streamId = "stream-backyard-feeder";
const sourceId = "source-backyard-demo";

test("native camera controls report launch and monitor conflicts without hardware", async ({
  page,
}) => {
  const configurationResponse = await page.request.patch(
    `/api/sources/${sourceId}/provider-configuration`,
    {
      data: {
        provider_key: "local_usb",
        config: {
          live_stream_type: "windows_dshow",
          windows_camera_name: "EMEET SmartCam S600",
          ffmpeg_binary_path: "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
        },
      },
    },
  );
  expect(configurationResponse.ok()).toBeTruthy();

  let controlsRequestCount = 0;
  let releaseLaunchResponse: (() => void) | undefined;
  let markLaunchRequested: (() => void) | undefined;
  const launchRequested = new Promise<void>((resolve) => {
    markLaunchRequested = resolve;
  });

  await page.route(`**/api/streams/${streamId}/camera-controls/open`, async (route) => {
    controlsRequestCount += 1;
    if (controlsRequestCount === 1) {
      await new Promise<void>((resolve) => {
        releaseLaunchResponse = resolve;
        markLaunchRequested?.();
      });
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          stream_id: streamId,
          source_id: sourceId,
          status: "launched",
          message:
            "Native Windows camera controls were launched. Adjust exposure, gain, or low-light settings in the camera driver, close the native window, then restart the camera and capture a test frame. MockingBird cannot read or persist these driver-managed values.",
          creates_media: false,
          creates_evidence: false,
          creates_event: false,
          creates_visit: false,
          creates_truth: false,
          warnings: [],
        }),
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        stream_id: streamId,
        source_id: sourceId,
        status: "monitor_running",
        message: "Stop monitoring before opening native controls.",
        creates_media: false,
        creates_evidence: false,
        creates_event: false,
        creates_visit: false,
        creates_truth: false,
        warnings: [],
      }),
    });
  });

  await page.goto(`/streams/${streamId}`);

  const calibration = page.locator("details").filter({
    has: page.getByText("Camera calibration", { exact: true }),
  });
  await expect(calibration).toBeVisible();
  await calibration.locator("summary").click();
  await expect(calibration).toContainText(
    "Stop the camera and monitoring before opening native controls.",
  );
  await expect(calibration).toContainText(
    "MockingBird cannot read or persist these driver-managed values.",
  );

  const controlsButton = calibration.getByRole("button", {
    name: /^(Open native controls|Launching\.\.\.)$/,
  });
  await controlsButton.click();
  await launchRequested;
  await expect(controlsButton).toHaveText("Launching...");
  releaseLaunchResponse?.();

  await expect(calibration).toContainText(
    "Native Windows camera controls were launched. Adjust exposure, gain, or low-light settings",
  );
  await expect(calibration).toContainText(
    "MockingBird cannot read or persist these driver-managed values.",
  );

  await controlsButton.click();
  await expect(calibration.locator(".stream-live-hint.is-error")).toHaveText(
    "Stop monitoring before opening native controls.",
  );
  expect(controlsRequestCount).toBe(2);
});
