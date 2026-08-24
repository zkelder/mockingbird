import { expect, test } from "@playwright/test";

// Broader Wildlife Maturity v1 (see docs/broader-wildlife-maturity-v1-
// contract.md). Two real, interactive UI journeys that a repository-level
// test cannot exercise: the Fast Review "Unknown animal" one-click action
// (previously only "Unknown bird" had a one-click/keyboard path), and the
// ordinary correction toast now saying something honest for a non-bird
// taxon instead of always "Added to Bird Log." Both against the real
// running backend (page.request), matching review-queue-reviewed-tab.
// spec.ts's own established convention -- not route-mocked. Neither test
// needs to track which specific Visit ends up open: each import guarantees
// at least one real unreviewed "animal" queue item exists, and the
// assertion is about the UI behavior itself, not about which item it
// acted on.

const STREAM_ID = "stream-backyard-feeder";
const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

async function importUnreviewedAnimalVisit(page: import("@playwright/test").Page, name: string): Promise<string> {
  const imported = await page.request.post("/api/media/import", {
    multipart: {
      file: { name, mimeType: "image/jpeg", buffer: Buffer.from(TINY_JPEG_BASE64, "base64") },
      stream_id: STREAM_ID,
      subject_label: "animal",
    },
  });
  expect(imported.ok()).toBeTruthy();
  const { visit } = await imported.json();
  return visit.id as string;
}

/** Manually-imported media lands in the "Legacy activity" product tab,
 * hidden by default behind the "Show legacy and test activity" toggle --
 * unrelated to this milestone (a pre-existing triage distinction between
 * imported/legacy content and live-camera detections), just a fixture
 * detail this spec needs to navigate past to reach the review form at
 * all. */
async function openLegacyActivityTab(page: import("@playwright/test").Page) {
  await page.getByLabel("Show legacy and test activity").check();
  await page.getByRole("button", { name: "Legacy activity" }).click();
}

test("Fast Review's one-click Unknown animal action saves real reviewed truth", async ({ page }) => {
  await importUnreviewedAnimalVisit(page, "broader-wildlife-fast-review.jpg");

  await page.goto("/review");
  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();
  await openLegacyActivityTab(page);

  const cards = page.locator("article.queue-card");
  await expect(cards.first()).toBeVisible();
  await cards.first().getByRole("button", { name: "Fast review" }).click();

  const fastReview = page.getByRole("region", { name: "Fast Review" });
  await expect(fastReview).toBeVisible();
  const unknownAnimalButton = fastReview.getByRole("button", { name: "Unknown animal", exact: true });
  await expect(unknownAnimalButton).toBeVisible();
  await fastReview.getByText("Keyboard shortcuts").click();
  await expect(fastReview.getByText("A: unknown animal", { exact: false })).toBeVisible();
  await unknownAnimalButton.click();

  await expect(page.getByText("Saved Unknown Animal.", { exact: false })).toBeVisible();
});

test("marking false positive shows an honest toast, not Added to Bird Log", async ({ page }) => {
  // The live review queue always renders in "Product Mode"
  // (`const productMode = true`, ReviewQueuePage.tsx -- a pre-existing,
  // unrelated condition, not something this milestone changed); its one
  // reachable saveCorrectionWithLabel call site is the False Positive
  // button. This is also one of the two concrete cases the contract doc
  // cites as previously wrong ("Marking a Visit false_positive -- explicitly
  // not an animal -- also said 'Added to Bird Log'").
  await importUnreviewedAnimalVisit(page, "broader-wildlife-toast.jpg");

  await page.goto("/review");
  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();
  await openLegacyActivityTab(page);

  const cards = page.locator("article.queue-card");
  await expect(cards.first()).toBeVisible();
  await cards.first().getByRole("button", { name: "False positive" }).click();

  await expect(page.getByText("Marked as false positive. Correction saved as local dataset truth.", { exact: false })).toBeVisible();
  await expect(page.getByText("Added to Bird Log", { exact: false })).toHaveCount(0);
});
