import { expect, test } from "@playwright/test";

// VISIT SAME-FRAME CLASSIFIER EVIDENCE VISIBILITY v1.
//
// Real field defect (visit-observation-candidate-022, 2026-08-16): BioCLIP
// suggested "House Finch" at 99.1% confidence from a `classifier_same_frame`
// MediaAsset the ordinary evidence gallery never shows, while the Visit's own
// displayed "identification" evidence happened to contain no visible bird --
// making a valid suggestion look unsupported to a human reviewer. These specs
// prove the frontend surface this milestone adds: a clearly-labeled
// "Species suggestion evidence" panel, separate from the primary evidence
// hero, rendered only when the backend has real classifier-supporting
// evidence to show, using the existing evidence-zoom mechanics. Mirrors
// visit-evidence-zoom.spec.ts's own `page.route` interception technique --
// every image byte and every other endpoint is the real backend; only the
// two JSON responses this milestone's own new field/endpoint interaction
// touches are shaped here to stand in for a real Observation Engine
// candidate Visit's evidence lineage.

const STREAM_ID = "stream-backyard-feeder";
const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

async function importRealPhoto(
  page: import("@playwright/test").Page,
): Promise<{ visitId: string; mediaAssetId: string }> {
  const response = await page.request.post("/api/media/import", {
    multipart: {
      file: {
        name: "classifier-supporting-evidence.jpg",
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

/**
 * One Visit whose primary evidence is a real (but, per the real field
 * scenario, effectively "empty of the bird") image, plus a distinct
 * `classifier_supporting_evidence` asset and a matching SpeciesSuggestion --
 * the exact shape `ProductRepository.classifier_supporting_evidence` returns
 * for a real historical Visit like visit-observation-candidate-022.
 */
async function seedVisitWithClassifierSupportingEvidence(page: import("@playwright/test").Page) {
  const primary = await importRealPhoto(page);
  const supporting = await importRealPhoto(page);

  const detailResponse = await page.request.get(`/api/visits/${primary.visitId}/detail`);
  const detail = await detailResponse.json();
  const seed = detail.evidence_frames[0];
  const primaryFrame = {
    ...seed,
    media_asset_id: primary.mediaAssetId,
    preview_url: `/api/media/${primary.mediaAssetId}/preview`,
    is_primary: true,
    evidence_role: "identification",
    width: 3840,
    height: 2160,
    normalized_track_box: null,
  };
  const supportingFrame = {
    ...seed,
    media_asset_id: supporting.mediaAssetId,
    preview_url: `/api/media/${supporting.mediaAssetId}/preview`,
    is_primary: false,
    evidence_role: "classifier_same_frame",
    width: 1920,
    height: 1440,
    normalized_track_box: [0.4859, 0.577, 0.5228, 0.6304],
  };
  detail.evidence_frames = [primaryFrame];
  detail.effective_primary = null;
  detail.classifier_supporting_evidence = {
    frame: supportingFrame,
    species_suggestion_id: "species-suggestion-e2e-1",
    same_frame: true,
    input_type: "same_frame_crop",
  };

  await page.route(`**/api/visits/${primary.visitId}/detail`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(detail) }),
  );
  await page.route(`**/api/species-suggestions**visit_id=${primary.visitId}**`, (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        species_suggestions: [
          {
            id: "species-suggestion-e2e-1",
            source_id: null,
            stream_id: STREAM_ID,
            event_id: detail.event.id,
            visit_id: primary.visitId,
            media_asset_id: primary.mediaAssetId,
            motion_evidence_id: null,
            adapter_id: "bioclip_2",
            adapter_name: "BioCLIP 2",
            suggested_label: "house_finch",
            suggested_common_name: "House Finch",
            suggested_scientific_name: null,
            confidence: 0.991,
            rank: 1,
            alternatives: [],
            evidence_region: {
              source: "activity",
              classifier_input: {
                source_media_asset_id: supporting.mediaAssetId,
                input_type: "same_frame_crop",
                same_frame: true,
              },
            },
            status: "pending",
            created_at: new Date().toISOString(),
            notes: null,
          },
        ],
      }),
    }),
  );

  return { visitId: primary.visitId, primaryFrame, supportingFrame };
}

function trackConsoleErrors(page: import("@playwright/test").Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  return errors;
}

test("classifier supporting evidence renders separately from primary evidence, clearly labeled, and names the suggestion", async ({
  page,
}) => {
  const consoleErrors = trackConsoleErrors(page);
  const { visitId, supportingFrame } = await seedVisitWithClassifierSupportingEvidence(page);
  await page.goto(`/visits/${visitId}`);

  const heroPanel = page.locator("section.visit-evidence-panel");
  await expect(heroPanel).toBeVisible();

  const supportingPanel = page.locator("section.classifier-supporting-evidence-panel");
  await expect(supportingPanel).toBeVisible();
  await expect(supportingPanel.getByText("Species suggestion evidence")).toBeVisible();
  // The dedicated badge, plus the reused evidence-sequence meta strip's own
  // "Supporting evidence" caption (since this frame is not `is_primary`) --
  // both independently agree this is not the Visit's primary evidence.
  await expect(supportingPanel.locator(".evidence-badge").getByText("Supporting evidence")).toBeVisible();
  // Names the actual suggestion it explains, not a generic message.
  await expect(supportingPanel.getByText(/House Finch/i)).toBeVisible();
  await expect(supportingPanel.getByText(/not the Visit evidence image above/i)).toBeVisible();

  // A genuinely separate image element from the primary hero -- proving
  // this is real supporting evidence, not a relabeled duplicate.
  const supportingImage = supportingPanel.locator(".evidence-zoom-viewport img");
  await expect(supportingImage).toBeVisible();
  const supportingSrc = await supportingImage.getAttribute("src");
  expect(supportingSrc).toContain(supportingFrame.media_asset_id);
  const heroImage = heroPanel.locator(".evidence-zoom-viewport img");
  const heroSrc = await heroImage.getAttribute("src");
  expect(heroSrc).not.toBe(supportingSrc);

  expect(consoleErrors).toEqual([]);
});

test("classifier supporting evidence is zoomable using the existing evidence viewer", async ({ page }) => {
  const consoleErrors = trackConsoleErrors(page);
  const { visitId } = await seedVisitWithClassifierSupportingEvidence(page);
  await page.goto(`/visits/${visitId}`);

  const supportingPanel = page.locator("section.classifier-supporting-evidence-panel");
  const zoomLevel = supportingPanel.locator(".evidence-zoom-level");
  await expect(zoomLevel).toHaveText("100%");

  const zoomIn = supportingPanel.getByRole("button", { name: "Zoom in" });
  await zoomIn.click();
  await zoomIn.click();
  await expect.poll(() => zoomLevel.textContent()).not.toBe("100%");

  // The real, backend-proven same-frame subject box: Focus/overlay controls
  // are offered here exactly as they are for any other frame with one.
  await expect(supportingPanel.getByRole("button", { name: "Focus on evidence" })).toBeVisible();
  await expect(supportingPanel.getByLabel("Show tracked region")).toBeVisible();

  expect(consoleErrors).toEqual([]);
});

test("no classifier supporting evidence panel when the backend has nothing distinct to show", async ({
  page,
}) => {
  const consoleErrors = trackConsoleErrors(page);
  const { visitId } = await importRealPhoto(page);
  await page.goto(`/visits/${visitId}`);

  await expect(page.locator("section.visit-evidence-panel")).toBeVisible();
  await expect(page.locator("section.classifier-supporting-evidence-panel")).toHaveCount(0);

  expect(consoleErrors).toEqual([]);
});

test("classifier supporting evidence panel stays usable on a narrow mobile viewport", async ({ page }) => {
  const consoleErrors = trackConsoleErrors(page);
  const { visitId } = await seedVisitWithClassifierSupportingEvidence(page);

  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto(`/visits/${visitId}`);

  const supportingPanel = page.locator("section.classifier-supporting-evidence-panel");
  await expect(supportingPanel).toBeVisible();
  await expect(supportingPanel.locator(".evidence-zoom-viewport img")).toBeVisible();
  await expect(supportingPanel.getByRole("button", { name: "Zoom in" })).toBeVisible();

  const hasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  expect(hasHorizontalOverflow).toBe(false);

  expect(consoleErrors).toEqual([]);
});
