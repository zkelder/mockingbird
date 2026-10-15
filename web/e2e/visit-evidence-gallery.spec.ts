import { expect, test } from "@playwright/test";

// Working App v1: Visit evidence gallery.
//
// Real field evidence (visit-motion-204, visit-motion-211 in the
// development database) showed a reviewer an auto-selected primary crop
// that was an empty, off-target close-up, while another already-saved frame
// on the exact same Visit (a `tracked_best_frame`) plainly showed the bird.
// The backend's `effective_primary` recommendation for that exact real
// shape is pinned by tests/test_visit_evidence_gallery.py; a hardware-free
// e2e suite cannot stand up the real live-activity multi-frame write path
// (see visit-evidence-review-loop.spec.ts for the same constraint), so
// these specs prove the frontend side of the same contract: given a
// realistic multi-frame `evidence_frames`/`effective_primary` API response,
// Visit Detail's gallery actually renders every frame, defaults to the
// recommended one, lets a reviewer switch freely, and never lets switching
// touch review state. `page.route` interception (already used elsewhere in
// this suite, e.g. camera-controls.spec.ts) stands in for that one API
// response; every image byte and every other endpoint is the real backend.

const STREAM_ID = "stream-backyard-feeder";
const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

async function importRealPhoto(
  page: import("@playwright/test").Page,
): Promise<{ visitId: string; mediaAssetId: string }> {
  const response = await page.request.post("/api/media/import", {
    multipart: {
      file: {
        name: "visit-evidence-gallery.jpg",
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

test("gallery defaults to the recommended frame, exposes every saved frame, and switching never touches review state", async ({
  page,
}) => {
  const persisted = await importRealPhoto(page);
  const alternate = await importRealPhoto(page);

  const detailResponse = await page.request.get(`/api/visits/${persisted.visitId}/detail`);
  const detail = await detailResponse.json();
  const seed = detail.evidence_frames[0];
  const primaryFrame = { ...seed, media_asset_id: persisted.mediaAssetId, preview_url: `/api/media/${persisted.mediaAssetId}/preview`, is_primary: true, evidence_role: "activity_crop" };
  const recommendedFrame = { ...seed, media_asset_id: alternate.mediaAssetId, preview_url: `/api/media/${alternate.mediaAssetId}/preview`, is_primary: false, evidence_role: "tracked_best_frame" };
  detail.evidence_frames = [primaryFrame, recommendedFrame];
  // Mirrors the real API contract pinned by
  // tests/test_visit_evidence_gallery.py::test_off_target_primary_crop_yields_a_useful_different_recommendation.
  detail.effective_primary = {
    selected_media_asset_id: alternate.mediaAssetId,
    persisted_primary_media_asset_id: persisted.mediaAssetId,
    recommended_effective_primary_media_asset_id: alternate.mediaAssetId,
    evidence_role: "tracked_best_frame",
    selection_reason: "tracked_best_frame_preferred",
    is_useful: true,
    is_user_controlled: false,
    temporally_supported: true,
    temporal_status: "supported",
    containment_status: null,
    edge_clipped: null,
    width: null,
    height: null,
    candidate_count: 2,
    historical_preview_only: true,
    would_change_automatically: true,
  };

  await page.route(`**/api/visits/${persisted.visitId}/detail`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(detail) }),
  );

  const consoleErrors: string[] = [];
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.goto(`/visits/${persisted.visitId}`);

  const heroPanel = page.locator("section.visit-evidence-panel");
  const heroImage = heroPanel.locator(".review-evidence-sequence-image img");

  // The recommended frame -- not the persisted primary -- is what a
  // reviewer actually sees first, and it is real, decoded image bytes.
  await expect(heroImage).toBeVisible();
  await expect
    .poll(() => heroImage.evaluate((element: HTMLImageElement) => element.naturalWidth))
    .toBeGreaterThan(0);
  await expect(heroImage).toHaveAttribute("src", new RegExp(alternate.mediaAssetId));
  await expect(heroPanel.locator(".review-evidence-recommendation")).toContainText("Recommended view");
  await expect(heroPanel.locator(".review-evidence-sequence-meta")).toContainText(
    "Recommended view (supporting evidence)",
  );

  // Every saved frame is discoverable as an actual thumbnail, no debug panel
  // required -- both roles are visible in the filmstrip.
  const thumbnails = heroPanel.locator(".review-evidence-thumbnail-strip button");
  await expect(thumbnails).toHaveCount(2);

  const form = page.locator("form.correction-form");
  await form.locator("input").first().fill("unknown_animal");
  await form.locator("textarea").fill("e2e: switching evidence frames must not disturb this note.");

  let writeRequestFired = false;
  page.on("request", (request) => {
    if (request.method() !== "GET" && request.url().includes("/api/visits/")) {
      writeRequestFired = true;
    }
  });

  // Switch to the persisted primary via its thumbnail.
  await thumbnails.filter({ hasText: "Primary" }).click();
  await expect(heroImage).toHaveAttribute("src", new RegExp(persisted.mediaAssetId));
  await expect(heroPanel.locator(".review-evidence-sequence-meta")).toContainText("Primary evidence");
  // The recommendation is still offered, now as an explicit jump back.
  await expect(heroPanel.getByRole("button", { name: "View recommended frame" })).toBeVisible();

  // The correction form -- Visit-level review state -- is completely
  // unaffected by which evidence image happens to be on screen.
  await expect(form.locator("input").first()).toHaveValue("Unknown Animal");
  await expect(form.locator("textarea")).toHaveValue(
    "e2e: switching evidence frames must not disturb this note.",
  );
  expect(writeRequestFired).toBe(false);

  // Jump back to the recommended frame using the explicit affordance.
  await heroPanel.getByRole("button", { name: "View recommended frame" }).click();
  await expect(heroImage).toHaveAttribute("src", new RegExp(alternate.mediaAssetId));
  await expect(heroPanel.getByRole("button", { name: "View recommended frame" })).toHaveCount(0);

  expect(consoleErrors).toEqual([]);
});

test("a single-evidence-frame Visit keeps the gallery simple", async ({ page }) => {
  const { visitId } = await importRealPhoto(page);

  const consoleErrors: string[] = [];
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });

  await page.goto(`/visits/${visitId}`);

  const heroPanel = page.locator("section.visit-evidence-panel");
  const heroImage = heroPanel.locator(".review-evidence-sequence-image img");
  await expect(heroImage).toBeVisible();
  await expect
    .poll(() => heroImage.evaluate((element: HTMLImageElement) => element.naturalWidth))
    .toBeGreaterThan(0);
  await expect(heroPanel.locator(".review-evidence-sequence-meta")).toContainText("Primary evidence");

  // No filmstrip and no recommendation banner clutter a Visit with nothing
  // to switch between.
  await expect(heroPanel.locator(".review-evidence-thumbnail-strip")).toHaveCount(0);
  await expect(heroPanel.locator(".review-evidence-recommendation")).toHaveCount(0);

  expect(consoleErrors).toEqual([]);
});

test("a missing individual evidence asset is shown as unavailable without breaking the rest of the gallery", async ({
  page,
}) => {
  const broken = await importRealPhoto(page);
  const working = await importRealPhoto(page);

  const detailResponse = await page.request.get(`/api/visits/${broken.visitId}/detail`);
  const detail = await detailResponse.json();
  const seed = detail.evidence_frames[0];
  const brokenFrame = { ...seed, media_asset_id: broken.mediaAssetId, preview_url: `/api/media/${broken.mediaAssetId}/preview`, is_primary: true, evidence_role: "activity_crop" };
  const workingFrame = { ...seed, media_asset_id: working.mediaAssetId, preview_url: `/api/media/${working.mediaAssetId}/preview`, is_primary: false, evidence_role: "tracked_best_frame" };
  detail.evidence_frames = [brokenFrame, workingFrame];
  detail.effective_primary = null;

  await page.route(`**/api/visits/${broken.visitId}/detail`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(detail) }),
  );
  // The real backend returns 404 for a media file that no longer exists on
  // disk (see get_media_preview in mockingbird/api/main.py); reproduce that
  // exact contract for one specific saved asset without touching the other.
  await page.route(`**/api/media/${broken.mediaAssetId}/preview`, (route) =>
    route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Media file not found." }),
    }),
  );

  await page.goto(`/visits/${broken.visitId}`);

  const heroPanel = page.locator("section.visit-evidence-panel");
  await expect(heroPanel.locator(".review-evidence-preview-unavailable")).toHaveText(
    "Saved preview is unavailable.",
  );
  // The rest of the page, including the other saved frame, is intact.
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const thumbnails = heroPanel.locator(".review-evidence-thumbnail-strip button");
  await expect(thumbnails).toHaveCount(2);

  await thumbnails.filter({ hasNotText: "Primary" }).click();
  const heroImage = heroPanel.locator(".review-evidence-sequence-image img");
  await expect(heroImage).toBeVisible();
  await expect
    .poll(() => heroImage.evaluate((element: HTMLImageElement) => element.naturalWidth))
    .toBeGreaterThan(0);
  await expect(heroPanel.locator(".review-evidence-preview-unavailable")).toHaveCount(0);
});
