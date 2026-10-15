import { deflateSync } from "node:zlib";
import { expect, test, type Page } from "@playwright/test";

// EVERYDAY WILDLIFE EXPERIENCE & PRESENTATION REFINEMENT v1.
// Workstream A (visual correctness) regressions. Presentation only: no
// backend facts are changed; epoch-anchored instants are mocked at the
// network edge exactly as unknown-capture-time-offline-evidence.spec.ts does.

test.use({ timezoneId: "America/New_York" });

const STREAM_ID = "stream-backyard-feeder";

// A real, large-natural-size PNG (no dependency): the Today thumbnail
// overlap only reproduces when the image's natural height exceeds the row.
function solidPng(width: number, height: number): Buffer {
  const crcTable = Array.from({ length: 256 }, (_, n) => {
    let c = n;
    for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc = (buf: Buffer) => {
    let c = 0xffffffff;
    for (const byte of buf) c = crcTable[(c ^ byte) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (type: string, data: Buffer) => {
    const body = Buffer.concat([Buffer.from(type), data]);
    const length = Buffer.alloc(4);
    length.writeUInt32BE(data.length);
    const checksum = Buffer.alloc(4);
    checksum.writeUInt32BE(crc(body));
    return Buffer.concat([length, body, checksum]);
  };
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header[8] = 8;
  header[9] = 2;
  const row = Buffer.concat([Buffer.from([0]), Buffer.alloc(width * 3, 120)]);
  const raw = Buffer.concat(Array.from({ length: height }, () => row));
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

async function importLargePhoto(page: Page, name: string): Promise<string> {
  const response = await page.request.post("/api/media/import", {
    multipart: {
      file: { name, mimeType: "image/png", buffer: solidPng(1280, 720) },
      stream_id: STREAM_ID,
      subject_label: "unknown_bird",
    },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).visit.id as string;
}

test("Today's Recent activity thumbnails stay in a fixed box and never overlap neighbouring rows", async ({ page }) => {
  // Real large images, real backend; only the Today summary's recent list is
  // shaped (the shared e2e instance's own Visits are not on Today's list).
  const previews: string[] = [];
  for (const name of ["thumb-a.png", "thumb-b.png", "thumb-c.png"]) {
    const visitId = await importLargePhoto(page, name);
    const detail = await (await page.request.get(`/api/visits/${visitId}/detail`)).json();
    previews.push(detail.evidence_frames[0]);
  }
  await page.route("**/api/dashboard/summary*", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.recent_activity = previews.map((frame, index) => ({
      id: `thumb-visit-${index}`,
      event_id: `thumb-event-${index}`,
      stream_id: STREAM_ID,
      captured_at: new Date(Date.now() - index * 60_000).toISOString(),
      activity_started_at: null,
      activity_ended_at: null,
      duration_seconds: null,
      zone_id: null,
      zone_name: null,
      zone_type: null,
      review_status: "needs_review",
      reviewed_label: null,
      review_outcome: "needs_review",
      suggested_label: null,
      has_suggestion: false,
      evidence_frame_count: 1,
      primary_evidence: { ...frame, is_primary: true },
      evidence_modality: "visual",
      multimodal_partner: null,
      cross_camera_partner: null,
      capture_time_known: true,
      stream_name: "Backyard feeder",
      source_id: null,
      source_name: null,
    }));
    await route.fulfill({ response, json: body });
  });
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto("/");
    const rows = page.locator(".dashboard-recent-activity .dashboard-activity-row");
    await expect(rows).toHaveCount(3);
    await expect.poll(() =>
      page.evaluate(() =>
        Array.from(document.querySelectorAll(".dashboard-recent-activity img")).every(
          (image) => (image as HTMLImageElement).complete && (image as HTMLImageElement).naturalHeight > 0,
        ),
      ),
    ).toBe(true);
    const boxes = await rows.evaluateAll((elements) =>
      elements.map((element) => {
        const row = element.getBoundingClientRect();
        // The <img> itself, not its wrapper: the defect was the image
        // rendering at natural height beyond a correctly-sized wrapper.
        const thumb = element.querySelector("img.dashboard-visit-preview")?.getBoundingClientRect();
        return { top: row.top, bottom: row.bottom, thumbHeight: thumb?.height ?? 0, thumbBottom: thumb?.bottom ?? 0 };
      }),
    );
    for (const [index, box] of boxes.entries()) {
      expect(box.thumbHeight).toBeGreaterThan(0);
      expect(box.thumbHeight).toBeLessThanOrEqual(64);
      expect(box.thumbBottom).toBeLessThanOrEqual(box.bottom + 1);
      if (index > 0) expect(box.top).toBeGreaterThanOrEqual(boxes[index - 1].bottom - 1);
    }
  }
});

test("Alerts and Local Data never render the 1970 epoch placeholder as a date", async ({ page }) => {
  await page.route("**/api/alerts?*", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.items = body.items.map((alert: Record<string, unknown>) => ({
      ...alert,
      created_at: "1970-01-01T00:00:09+00:00",
    }));
    await route.fulfill({ response, json: body });
  });
  await page.route("**/api/settings/storage-retention/summary", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({
      response,
      json: { ...body, oldest_managed_media_at: "1970-01-01T00:00:09+00:00" },
    });
  });
  await importLargePhoto(page, "alert-seed.png");

  await page.goto("/alerts");
  await expect(page.getByRole("heading", { name: "Alerts Inbox" })).toBeVisible();
  const alertsText = await page.locator("main").innerText();
  expect(alertsText).not.toMatch(/Dec 31|1969|1970/);

  await page.goto("/local-data");
  await expect(page.getByRole("heading", { name: "Local Data" })).toBeVisible();
  await expect(page.getByText("Time not recorded").first()).toBeVisible();
  expect(await page.locator("main").innerText()).not.toMatch(/12\/31\/1969|1970/);
});
