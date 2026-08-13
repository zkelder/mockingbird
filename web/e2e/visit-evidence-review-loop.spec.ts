import { expect, test } from "@playwright/test";

// Working App v1: real regression found live against the real development
// database. Visit Detail's evidence-image sections were each gated on a
// provenance fact tied to one specific Visit-creation path (a legacy
// MotionEvidence promotion, or a `representative_media_path` resolving to
// an attached MediaAsset) -- never on the one thing every Visit actually
// has, `evidence_frames`. A Visit created through a path that sets neither
// (the Observation Engine v2 Stage 7 candidate path exercised by
// `tests/test_candidate_visit_review_workflow.py` on the backend) rendered
// no image anywhere on the page, even though the backend already served the
// real evidence bytes correctly. Stage 7 candidates need a real hardware-
// backed detector/tracker pipeline to create, which this hardware-free e2e
// suite cannot stand up -- so this spec proves the actual fix (Visit
// Detail's unconditional `evidence_frames`-first hero panel) the
// provenance-agnostic way it was written: against a real imported photo,
// through the exact same rendering path a Stage 7 candidate now also uses.

const STREAM_ID = "stream-backyard-feeder";
// A tiny, genuinely valid, decodable JPEG (a real encoded 8x8 image, not a
// synthetic byte soup) -- `create_media_import` writes these bytes to a real
// managed-media file, and `/api/media/{id}/preview` really cv2-decodes them,
// exactly like a real saved camera frame.
const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

async function importRealPhoto(
  page: import("@playwright/test").Page,
  subjectLabel: string,
): Promise<string> {
  const response = await page.request.post("/api/media/import", {
    multipart: {
      file: {
        name: "visit-evidence-review-loop.jpg",
        mimeType: "image/jpeg",
        buffer: Buffer.from(TINY_JPEG_BASE64, "base64"),
      },
      stream_id: STREAM_ID,
      subject_label: subjectLabel,
    },
  });
  expect(response.ok()).toBeTruthy();
  const result = await response.json();
  expect(result.visit).not.toBeNull();
  return result.visit.id as string;
}

test("a real saved evidence image actually renders on Visit Detail, and Animal can be confirmed with species left Unknown", async ({
  page,
}) => {
  const visitId = await importRealPhoto(page, "animal");

  await page.goto(`/visits/${visitId}`);

  // The primary-evidence contract this milestone's fix depends on: one real
  // `<img>` element, actually requested and actually decoded by the browser
  // -- not just a truthful-sounding text claim next to a blank space.
  const heroImage = page.locator("section.visit-evidence-panel img").first();
  await expect(heroImage).toBeVisible();
  await expect
    .poll(() => heroImage.evaluate((element: HTMLImageElement) => element.naturalWidth))
    .toBeGreaterThan(0);

  const form = page.locator("form.correction-form");
  await form.locator("input").first().fill("unknown_animal");
  await form.locator("textarea").fill("e2e: animal confirmed, species intentionally left unknown.");
  await form.getByRole("button", { name: /Save correction|Resolve species/ }).click();

  await expect(page.getByRole("heading", { level: 1 })).toContainText("Unknown Animal", {
    ignoreCase: true,
  });

  const visitResponse = await page.request.get(`/api/visits/${visitId}`);
  const visit = await visitResponse.json();
  expect(visit.review_status).toBe("reviewed");
  expect(visit.reviewed_label).toBe("unknown_animal");

  // The frontend client -- not this test -- is the one thing allowed to
  // assert human provenance (docs/review-decision-provenance-contract.md);
  // confirm it actually did.
  const labelsResponse = await page.request.get("/api/review-labels");
  const labels = await labelsResponse.json();
  const ownLabel = labels.find(
    (label: { target_id: string; target_type: string }) =>
      label.target_id === visitId && label.target_type === "visit",
  );
  expect(ownLabel.review_origin).toBe("human");
  expect(ownLabel.is_authoritative).toBe(true);
});

test("Not Animal is authoritative but creates no wildlife Bird Log entry", async ({ page }) => {
  const visitId = await importRealPhoto(page, "animal");

  await page.goto(`/visits/${visitId}`);
  const heroImage = page.locator("section.visit-evidence-panel img").first();
  await expect(heroImage).toBeVisible();

  const form = page.locator("form.correction-form");
  await form.locator("input").first().fill("false_positive");
  await form.locator("textarea").fill("e2e: no animal present in the saved evidence.");
  await form.getByRole("button", { name: /Save correction|Resolve species/ }).click();

  await expect(page.getByRole("heading", { level: 1 })).toContainText("False Positive", {
    ignoreCase: true,
  });

  const visitResponse = await page.request.get(`/api/visits/${visitId}`);
  const visit = await visitResponse.json();
  // Authoritative, reviewed truth -- just never a wildlife Observation.
  expect(visit.review_status).toBe("reviewed");
  expect(visit.reviewed_label).toBe("false_positive");

  const journalResponse = await page.request.get("/api/bird-log/journal");
  const journal = await journalResponse.json();
  const labels = journal.labels.map((entry: { label: string }) => entry.label);
  expect(labels).not.toContain("false_positive");

  const reviewQueueResponse = await page.request.get("/api/review-queue");
  const reviewQueue = await reviewQueueResponse.json();
  expect(reviewQueue.some((item: { visit_id: string }) => item.visit_id === visitId)).toBe(false);
});
