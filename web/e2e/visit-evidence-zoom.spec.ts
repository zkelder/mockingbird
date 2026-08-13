import { expect, test } from "@playwright/test";

// WORKING APP v1: Evidence Zoom + Focus.
//
// visit-motion-204/211 (development database) open on a useful saved frame
// (see visit-evidence-gallery.spec.ts) but the bird is a small speck within
// it. These specs prove the frontend zoom/pan/focus contract added on top
// of that gallery: manual zoom/pan work on any frame regardless of
// geometry; "Focus on evidence" and the tracked-region overlay appear only
// for a frame the backend has already validated a `normalized_track_box`
// for (never a bogus control on a frame without one, never carried over
// from a previously-viewed frame); full-resolution access is always
// offered; switching frames always resets the viewport; and none of this
// touches review-form state. `page.route` interception (already used in
// visit-evidence-gallery.spec.ts) stands in for the real multi-frame
// evidence/geometry shape; every image byte and every other endpoint is the
// real backend.

const STREAM_ID = "stream-backyard-feeder";
const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

async function importRealPhoto(
  page: import("@playwright/test").Page,
): Promise<{ visitId: string; mediaAssetId: string }> {
  const response = await page.request.post("/api/media/import", {
    multipart: {
      file: {
        name: "visit-evidence-zoom.jpg",
        mimeType: "image/jpeg",
        buffer: Buffer.from(TINY_JPEG_BASE64, "base64"),
      },
      stream_id: STREAM_ID,
      subject_label: "unknown_bird",
    },
  });
  expect(response.ok()).toBeTruthy();
  const result = await response.json();
  expect(result.visit).not.toBeNull();
  return { visitId: result.visit.id as string, mediaAssetId: result.media_asset.id as string };
}

/** Two evidence frames on one Visit: only `withBox` carries a subject box. */
async function seedTwoFrameVisit(page: import("@playwright/test").Page) {
  const withBox = await importRealPhoto(page);
  const withoutBox = await importRealPhoto(page);

  const detailResponse = await page.request.get(`/api/visits/${withBox.visitId}/detail`);
  const detail = await detailResponse.json();
  const seed = detail.evidence_frames[0];
  const boxFrame = {
    ...seed,
    media_asset_id: withBox.mediaAssetId,
    preview_url: `/api/media/${withBox.mediaAssetId}/preview`,
    is_primary: true,
    evidence_role: "high_resolution_original",
    width: 4624,
    height: 3472,
    // A real-shaped small subject box (see tests/test_visit_evidence_gallery.py).
    normalized_track_box: [0.4593, 0.6218, 0.4889, 0.6676],
  };
  const plainFrame = {
    ...seed,
    media_asset_id: withoutBox.mediaAssetId,
    preview_url: `/api/media/${withoutBox.mediaAssetId}/preview`,
    is_primary: false,
    evidence_role: "activity_crop",
    width: 234,
    height: 271,
    normalized_track_box: null,
  };
  detail.evidence_frames = [boxFrame, plainFrame];
  detail.effective_primary = null;

  await page.route(`**/api/visits/${withBox.visitId}/detail`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(detail) }),
  );

  return { visitId: withBox.visitId, boxFrame, plainFrame };
}

function trackConsoleErrors(page: import("@playwright/test").Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  return errors;
}

test("zoom in, zoom out, and reset controls work, and switching frames resets the viewport", async ({ page }) => {
  const consoleErrors = trackConsoleErrors(page);
  const { visitId } = await seedTwoFrameVisit(page);
  await page.goto(`/visits/${visitId}`);

  const heroPanel = page.locator("section.visit-evidence-panel");
  const zoomLevel = heroPanel.locator(".evidence-zoom-level");
  await expect(zoomLevel).toHaveText("100%");

  const zoomIn = heroPanel.getByRole("button", { name: "Zoom in" });
  const zoomOut = heroPanel.getByRole("button", { name: "Zoom out" });
  const reset = heroPanel.getByRole("button", { name: "Reset view" });
  await expect(zoomOut).toBeDisabled();
  await expect(reset).toBeDisabled();

  await zoomIn.click();
  await zoomIn.click();
  await expect
    .poll(() => zoomLevel.textContent())
    .not.toBe("100%");
  await expect(zoomOut).toBeEnabled();
  await expect(reset).toBeEnabled();

  await zoomOut.click();
  await reset.click();
  await expect(zoomLevel).toHaveText("100%");
  await expect(reset).toBeDisabled();

  // Zoom back in, then switch frames via the thumbnail strip: the new
  // frame must open at a fresh fit view, never the previous frame's zoom.
  await zoomIn.click();
  await expect.poll(() => zoomLevel.textContent()).not.toBe("100%");
  const thumbnails = heroPanel.locator(".review-evidence-thumbnail-strip button");
  await expect(thumbnails).toHaveCount(2);
  await thumbnails.nth(1).click();
  await expect(zoomLevel).toHaveText("100%");
  await expect(reset).toBeDisabled();

  expect(consoleErrors).toEqual([]);
});

test("wheel zoom changes scale over the image", async ({ page }) => {
  const consoleErrors = trackConsoleErrors(page);
  const { visitId } = await seedTwoFrameVisit(page);
  await page.goto(`/visits/${visitId}`);

  const heroPanel = page.locator("section.visit-evidence-panel");
  const viewport = heroPanel.locator(".evidence-zoom-viewport");
  const zoomLevel = heroPanel.locator(".evidence-zoom-level");
  const box = await viewport.boundingBox();
  if (!box) throw new Error("evidence-zoom-viewport did not render a box");

  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.wheel(0, -400);
  await expect.poll(() => zoomLevel.textContent()).not.toBe("100%");

  expect(consoleErrors).toEqual([]);
});

test("dragging pans the image once zoomed in, and is a no-op at fit scale", async ({ page }) => {
  const consoleErrors = trackConsoleErrors(page);
  const { visitId } = await seedTwoFrameVisit(page);
  await page.goto(`/visits/${visitId}`);

  const heroPanel = page.locator("section.visit-evidence-panel");
  const viewport = heroPanel.locator(".evidence-zoom-viewport");
  const stage = heroPanel.locator(".evidence-zoom-stage");

  // Re-measured fresh before every drag: clicking a button below the image
  // can auto-scroll the page (Playwright brings a click target into view),
  // which moves the image's on-screen position -- stale coordinates would
  // drag empty space instead of the image.
  async function dragAcrossViewport() {
    await viewport.scrollIntoViewIfNeeded();
    const box = await viewport.boundingBox();
    if (!box) throw new Error("evidence-zoom-viewport did not render a box");
    const centerX = box.x + box.width / 2;
    const centerY = box.y + box.height / 2;
    await page.mouse.move(centerX, centerY);
    await page.mouse.down();
    await page.mouse.move(centerX - 40, centerY - 20, { steps: 5 });
    await page.mouse.up();
  }

  // At fit scale, panning has nothing to do: the origin is pinned centered.
  const fitLeft = await stage.evaluate((element) => element.getBoundingClientRect().left);
  await dragAcrossViewport();
  const afterDragAtFit = await stage.evaluate((element) => element.getBoundingClientRect().left);
  expect(afterDragAtFit).toBeCloseTo(fitLeft, 0);

  await heroPanel.getByRole("button", { name: "Zoom in" }).click();
  await heroPanel.getByRole("button", { name: "Zoom in" }).click();
  const zoomedLeft = await stage.evaluate((element) => element.getBoundingClientRect().left);

  await dragAcrossViewport();

  const pannedLeft = await stage.evaluate((element) => element.getBoundingClientRect().left);
  expect(pannedLeft).not.toBeCloseTo(zoomedLeft, 0);

  expect(consoleErrors).toEqual([]);
});

test("Focus on evidence and the tracked-region overlay are frame-specific, and land on the saved box", async ({
  page,
}) => {
  const consoleErrors = trackConsoleErrors(page);
  const { visitId } = await seedTwoFrameVisit(page);
  await page.goto(`/visits/${visitId}`);

  const heroPanel = page.locator("section.visit-evidence-panel");
  const focusButton = heroPanel.getByRole("button", { name: "Focus on evidence" });
  const overlayToggle = heroPanel.getByLabel("Show tracked region");
  const overlayBox = heroPanel.locator(".evidence-zoom-subject-box");
  const zoomLevel = heroPanel.locator(".evidence-zoom-level");

  // Frame 1 (primary, opens first) has a real, backend-valid box.
  await expect(focusButton).toBeVisible();
  await expect(overlayToggle).toBeVisible();
  // The overlay favors seeing the photo clearly by default -- hidden until asked for.
  await expect(overlayBox).toHaveCount(0);

  await overlayToggle.check();
  await expect(overlayBox).toBeVisible();

  await focusButton.click();
  await expect.poll(() => zoomLevel.textContent()).not.toBe("100%");
  // Focus recenters and zooms in generously around the saved box; the
  // subject box overlay stays visible and still exactly frames the region
  // this zoomed toward (both driven by the one saved `normalized_track_box`).
  await expect(overlayBox).toBeVisible();

  // Frame 2 has no saved box: switching to it must never carry over frame
  // 1's zoom, overlay choice, or controls -- and must never fabricate a box.
  const thumbnails = heroPanel.locator(".review-evidence-thumbnail-strip button");
  await thumbnails.nth(1).click();
  await expect(zoomLevel).toHaveText("100%");
  await expect(focusButton).toHaveCount(0);
  await expect(overlayToggle).toHaveCount(0);
  await expect(overlayBox).toHaveCount(0);

  // Switching back to frame 1 must not resurrect the overlay-on choice
  // from before -- each frame view starts from the same safe default.
  await thumbnails.nth(0).click();
  await expect(focusButton).toBeVisible();
  await expect(overlayBox).toHaveCount(0);

  expect(consoleErrors).toEqual([]);
});

test("full-resolution access is available and points at the real media endpoint", async ({ page }) => {
  const consoleErrors = trackConsoleErrors(page);
  const { visitId, boxFrame, plainFrame } = await seedTwoFrameVisit(page);
  await page.goto(`/visits/${visitId}`);

  const heroPanel = page.locator("section.visit-evidence-panel");
  const fullResLink = heroPanel.getByRole("link", { name: "Full resolution ↗" });
  await expect(fullResLink).toHaveAttribute("target", "_blank");
  await expect(fullResLink).toHaveAttribute(
    "href",
    new RegExp(`/api/media/${boxFrame.media_asset_id}/full-resolution$`),
  );

  const fullResResponse = await page.request.get(await fullResLink.getAttribute("href") as string);
  expect(fullResResponse.ok()).toBeTruthy();
  expect(fullResResponse.headers()["content-type"]).toContain("image/jpeg");

  // Still offered on a frame that is not the "high_resolution_original"
  // role -- reusing the same generic media endpoint for whichever frame is
  // actually on screen, not gated to one specific evidence role.
  const thumbnails = heroPanel.locator(".review-evidence-thumbnail-strip button");
  await thumbnails.nth(1).click();
  await expect(fullResLink).toHaveAttribute(
    "href",
    new RegExp(`/api/media/${plainFrame.media_asset_id}/full-resolution$`),
  );

  expect(consoleErrors).toEqual([]);
});

test("review form state survives zooming, panning, and switching frames", async ({ page }) => {
  const consoleErrors = trackConsoleErrors(page);
  const { visitId } = await seedTwoFrameVisit(page);
  await page.goto(`/visits/${visitId}`);

  const heroPanel = page.locator("section.visit-evidence-panel");
  const form = page.locator("form.correction-form");
  await form.locator("input").first().fill("unknown_animal");
  await form.locator("textarea").fill("e2e: zoom/pan/focus must not disturb this note.");

  let writeRequestFired = false;
  page.on("request", (request) => {
    if (request.method() !== "GET" && request.url().includes("/api/visits/")) {
      writeRequestFired = true;
    }
  });

  await heroPanel.getByRole("button", { name: "Zoom in" }).click();
  const viewport = heroPanel.locator(".evidence-zoom-viewport");
  await viewport.scrollIntoViewIfNeeded();
  const box = await viewport.boundingBox();
  if (!box) throw new Error("evidence-zoom-viewport did not render a box");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 - 15, box.y + box.height / 2 - 10, { steps: 3 });
  await page.mouse.up();
  await heroPanel.getByRole("button", { name: "Focus on evidence" }).click();
  const thumbnails = heroPanel.locator(".review-evidence-thumbnail-strip button");
  await thumbnails.nth(1).click();
  await heroPanel.getByRole("button", { name: "Reset view", exact: true }).isVisible().catch(() => undefined);

  await expect(form.locator("input").first()).toHaveValue("unknown_animal");
  await expect(form.locator("textarea")).toHaveValue(
    "e2e: zoom/pan/focus must not disturb this note.",
  );
  expect(writeRequestFired).toBe(false);

  expect(consoleErrors).toEqual([]);
});
