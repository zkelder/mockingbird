import { expect, test } from "@playwright/test";

// OWNER-ONLY RELEASE POLISH & ACCEPTANCE v1 (O-1, O-2).
//
// Internal release-candidate acceptance on native Windows found two honest-
// presentation defects on a Visit found by offline analysis of an imported
// recording that has no capture-time metadata:
//   O-1: its 1970 epoch placeholder rendered as a year-less "Dec 31, 7:00 PM"
//        in America/New_York, reading like a real recent date;
//   O-2: its evidence panel said "No detections are attached to this manual
//        media visit", although a detector found it and it is not manual.
// Mirrors visit-classifier-supporting-evidence.spec.ts's `page.route`
// technique: a real imported photo and the real backend supply every image
// and every other endpoint; only the Visit detail JSON is shaped to stand in
// for an offline-ingested candidate Visit, using the backend's own
// `capture_time_known`/`acquisition_type` facts (proven by
// tests/test_offline_ingest.py).

test.use({ timezoneId: "America/New_York" });

const STREAM_ID = "stream-backyard-feeder";
const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

async function importRealPhoto(page: import("@playwright/test").Page): Promise<string> {
  const response = await page.request.post("/api/media/import", {
    multipart: {
      file: {
        name: "offline-capture-time.jpg",
        mimeType: "image/jpeg",
        buffer: Buffer.from(TINY_JPEG_BASE64, "base64"),
      },
      stream_id: STREAM_ID,
      subject_label: "unknown_bird",
    },
  });
  expect(response.ok()).toBeTruthy();
  const result = await response.json();
  return result.visit.id as string;
}

async function seedOfflineUnknownCaptureTimeVisit(page: import("@playwright/test").Page): Promise<string> {
  const visitId = await importRealPhoto(page);
  const detail = await (await page.request.get(`/api/visits/${visitId}/detail`)).json();
  const placeholderStart = "1970-01-01T00:00:08+00:00";
  detail.event = {
    ...detail.event,
    event_type: "observation_engine_candidate",
    title: "Machine-observed animal activity (needs review)",
    started_at: placeholderStart,
    ended_at: "1970-01-01T00:00:11+00:00",
    detections: [],
  };
  detail.detections = [];
  detail.evidence_frames = detail.evidence_frames.map((frame: Record<string, unknown>) => ({
    ...frame,
    captured_at: placeholderStart,
  }));
  detail.capture_time_known = false;
  detail.acquisition_type = "recorded_video";
  await page.route(`**/api/visits/${visitId}/detail`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(detail) }),
  );
  return visitId;
}

function trackConsoleErrors(page: import("@playwright/test").Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  return errors;
}

test("an offline Visit with no capture time says so instead of showing the 1970 placeholder as a date", async ({
  page,
}) => {
  const consoleErrors = trackConsoleErrors(page);
  const visitId = await seedOfflineUnknownCaptureTimeVisit(page);
  await page.goto(`/visits/${visitId}`);

  await expect(page.locator("section.visit-evidence-panel")).toBeVisible();
  await expect(page.getByText("Capture time unknown").first()).toBeVisible();
  // The exact field-observed rendering, and any other rendering of the
  // placeholder instant in this zone, must be gone.
  await expect(page.getByText(/Dec 31/)).toHaveCount(0);
  await expect(page.getByText(/7:00 PM/)).toHaveCount(0);

  expect(consoleErrors).toEqual([]);
});

test("an offline-analysis Visit's evidence panel does not call it manual media", async ({ page }) => {
  const consoleErrors = trackConsoleErrors(page);
  const visitId = await seedOfflineUnknownCaptureTimeVisit(page);
  await page.goto(`/visits/${visitId}`);

  await expect(page.getByText("Found by offline analysis of an imported recording.", { exact: false })).toBeVisible();
  await expect(page.getByText(/No separate detection records are stored for this visit/)).toBeVisible();
  await expect(page.getByText(/manual media visit/)).toHaveCount(0);

  expect(consoleErrors).toEqual([]);
});

test("a real manual import keeps its real date and its manual-media wording", async ({ page }) => {
  const consoleErrors = trackConsoleErrors(page);
  const visitId = await importRealPhoto(page);
  await page.goto(`/visits/${visitId}`);

  await expect(page.locator("section.visit-evidence-panel")).toBeVisible();
  await expect(page.getByText("Capture time unknown")).toHaveCount(0);
  await expect(page.getByText("No detections are attached to this manual media visit.")).toBeVisible();

  expect(consoleErrors).toEqual([]);
});
