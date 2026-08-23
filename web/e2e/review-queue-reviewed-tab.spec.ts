import { expect, test } from "@playwright/test";

// Everyday Product / Discovery UX Closure v1: found via live hands-on
// verification, not a unit test. The Review Queue's "Reviewed" tab
// (product_category === "reviewed") and a separate, collapsed "Status"
// filter (defaulting to "Unreviewed") were two independently-applied,
// silently conflicting filters -- opening the Reviewed tab always showed
// "No review items match these filters" even when reviewed items existed,
// because the hidden default Status filter required review_status ===
// "needs_review", which no reviewed item can ever satisfy. This also
// exercises the companion fix: the card title now says what a Visit was
// actually reviewed as ("Reviewed: <species>") instead of an undifferentiated
// "Reviewed activity" for every card.

const STREAM_ID = "stream-backyard-feeder";
const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

async function importAndConfirmVisit(page: import("@playwright/test").Page): Promise<string> {
  const imported = await page.request.post("/api/media/import", {
    multipart: {
      file: {
        name: "review-queue-reviewed-tab.jpg",
        mimeType: "image/jpeg",
        buffer: Buffer.from(TINY_JPEG_BASE64, "base64"),
      },
      stream_id: STREAM_ID,
      subject_label: "animal",
    },
  });
  expect(imported.ok()).toBeTruthy();
  const { visit } = await imported.json();

  const reviewed = await page.request.post("/api/review-labels", {
    data: { review_origin: "human", target_type: "visit", target_id: visit.id, label: "blue_jay" },
  });
  expect(reviewed.ok()).toBeTruthy();
  return visit.id as string;
}

test("the Reviewed tab shows reviewed items, each labeled with what it was actually reviewed as", async ({
  page,
}) => {
  const visitId = await importAndConfirmVisit(page);

  await page.goto("/review");
  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();

  const reviewedTab = page.getByRole("button", { name: /^Reviewed/ });
  await expect(reviewedTab).toBeVisible();
  await reviewedTab.click();

  // The regression: this used to always be empty regardless of how many
  // reviewed items existed.
  const cards = page.locator("article.queue-card");
  await expect(cards.first()).toBeVisible();
  await expect(page.getByText("No review items match these filters")).toHaveCount(0);

  const ownCard = cards.filter({ hasText: "Reviewed: Blue Jay" });
  await expect(ownCard).toHaveCount(1);

  // Confirm the underlying data really is this Visit, not a coincidence.
  const visitResponse = await page.request.get(`/api/visits/${visitId}`);
  const visitPayload = await visitResponse.json();
  expect(visitPayload.review_status).toBe("reviewed");
  expect(visitPayload.reviewed_label).toBe("blue_jay");
});
