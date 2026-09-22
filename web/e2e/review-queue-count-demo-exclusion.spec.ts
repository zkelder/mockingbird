import { expect, test } from "@playwright/test";

// Review Queue Count Truth Consistency v1: Native-Windows & Packaging
// Acceptance v1 fixed `GET /api/review-queue`/`dashboard_summary` excluding
// the seeded demo Source's own fabricated activity, but disclosed that the
// core review/correction response itself (`POST /api/review-labels`, which
// backs this page's quick-action "False positive"/"Save correction"
// buttons) still reported an unfiltered count -- so correcting the one
// genuine item a user actually cares about still announced "1 item still
// needs review", counting the seeded demo Visit as if it were real
// outstanding work. This proves the real, rendered toast text a user sees
// is now truthful.

const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

test("correcting one real item reports 0 remaining, not the seeded demo Visit's own count", async ({
  page,
}) => {
  // A dedicated, real (non-demo) Source/Stream -- `POST /api/sources`
  // mirrors the plain "Add Camera" flow, matching real users, not this
  // suite's shared demo fixture Stream (`kind == "demo"`), which is always
  // `legacy_activity`/demo-excluded by design and would never exercise the
  // fix under test (see `review-queue-fast-review-keyboard.spec.ts`'s own
  // identical reasoning).
  const created = await page.request.post("/api/sources", {
    data: { name: `Review Queue Count Fixture ${Date.now()}` },
  });
  expect(created.ok()).toBeTruthy();
  const { stream } = await created.json();

  const imported = await page.request.post("/api/media/import", {
    multipart: {
      file: {
        name: "review-queue-count-demo-exclusion.jpg",
        mimeType: "image/jpeg",
        buffer: Buffer.from(TINY_JPEG_BASE64, "base64"),
      },
      stream_id: stream.id,
      subject_label: "unknown_animal",
    },
  });
  expect(imported.ok()).toBeTruthy();

  await page.goto("/review");
  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();

  // Default "Animals" tab, no click needed -- the just-imported real Visit
  // must already be there, and it is the only item this fresh instance has
  // (the seeded demo Visit never reaches this list at all, correctly
  // excluded by the prior milestone's own `GET /api/review-queue` fix).
  const cards = page.locator("article.queue-card");
  await expect(cards).toHaveCount(1);
  await cards.first().getByRole("button", { name: "False positive" }).click();

  // The regression: before this fix, this response's `review_queue_count`
  // was an unfiltered `len(_review_queue_items(session))`, which counts the
  // seeded demo Source's own still-needs-review `visit-bird-feeder-001` as
  // if it were outstanding real work -- announcing "1" here even though the
  // only genuine item in this instance was just resolved.
  await expect(page.getByText(/0 items still need review\./)).toBeVisible();
});
