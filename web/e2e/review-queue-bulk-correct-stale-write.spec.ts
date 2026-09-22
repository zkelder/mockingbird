import { expect, test } from "@playwright/test";

// Local Identity, Multi-User & Organization Access v1 (bulk-correct
// concurrency closure, frontend wiring): proves the REAL ReviewQueuePage
// request-construction code path -- not the repository/API-level
// mechanism (already covered directly by
// tests/test_local_identity_multi_user.py::test_two_reviewers_bulk_
// correction_stale_write_is_rejected_not_silently_overwritten in the
// Python suite) -- actually sends the per-item token a real browser
// session is holding, and that the product visibly refuses to report a
// stale item as saved.
//
// Reviewer B's concurrent change is represented here as a real Zone
// reassignment (`POST /api/visits/{id}/zone`), not a second review
// correction: `bulk_correct_review_queue_items`'s own pre-existing
// eligibility rule already refuses anything that isn't still
// `needs_review` (see `_review_queue_bulk_correction_skip_reason`), so a
// second *authoritative* correction would make the Visit ineligible and
// get caught by that unrelated, pre-existing rule before the new
// `expected_state_tokens` check this test exists to prove is ever
// consulted -- exactly the same reasoning the Python test's own docstring
// gives for its own choice of scenario. A Zone move changes the review-
// state token (`_visit_curation_state`) without touching `review_status`,
// so the Visit stays fully bulk-correction-eligible throughout.

const STREAM_ID = "stream-backyard-feeder";
const FEEDER_ZONE_ID = "zone-feeder";
const GROUND_ZONE_ID = "zone-ground";
const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

test("a bulk correction submitted with a stale review_state_token is rejected, not silently applied, while a concurrent Zone move remains authoritative", async ({
  page,
}) => {
  // Seed a reviewable Visit -- same real product path as
  // review-queue-reviewed-tab.spec.ts's own fixture helper.
  const imported = await page.request.post("/api/media/import", {
    multipart: {
      file: {
        name: "bulk-correct-stale-write.jpg",
        mimeType: "image/jpeg",
        buffer: Buffer.from(TINY_JPEG_BASE64, "base64"),
      },
      stream_id: STREAM_ID,
      subject_label: "animal",
    },
  });
  expect(imported.ok()).toBeTruthy();
  const { visit } = await imported.json();

  // Reviewer A opens the Review Queue: this loads the item's current
  // review_state_token (T1) into the page's own React state, exactly
  // like a real signed-in reviewer with this page open.
  await page.goto("/review");
  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();
  // Media-imported fixtures land in the "Legacy activity" Product Mode
  // group (confirmed by direct execution, not assumed) -- both the
  // group's own tab and its "show legacy and test activity" gate must be
  // active for the seeded item to appear at all, independent of search.
  await page.getByRole("checkbox", { name: "Show sample and older activity" }).check();
  await page.getByRole("button", { name: /^Sample and older activity/ }).click();
  await page.getByText("Filter review items", { exact: true }).click();
  await page.getByPlaceholder("label, stream, source, zone, suggestion").fill(visit.id);

  const cards = page.locator("article.queue-card");
  await expect(cards).toHaveCount(1);

  // Product Mode's card (ProductReviewCard) has no per-item selection
  // control of its own -- "Select visible eligible" (scoped by the
  // search filter above to this one item) is the real product's actual
  // way to populate a bulk-correction selection.
  await page.getByText("Bulk correction", { exact: true }).click();
  await page.getByRole("button", { name: "Select visible eligible" }).click();
  await expect(page.getByText("1 selected / 1 eligible")).toBeVisible();

  // Reviewer B, concurrently, moves this same Visit to a different Zone
  // -- a real Reviewer-tier curation action that advances the
  // review-state token (T1 -> T2) without touching review_status.
  const beforeMove = await page.request.get(`/api/visits/${visit.id}/detail`);
  expect(beforeMove.ok()).toBeTruthy();
  const beforeMovePayload = await beforeMove.json();
  const staleToken: string = beforeMovePayload.review_state_token;
  const currentZoneId: string | null = beforeMovePayload.visit.zone_id;
  const destinationZoneId = currentZoneId === GROUND_ZONE_ID ? FEEDER_ZONE_ID : GROUND_ZONE_ID;

  const moved = await page.request.post(`/api/visits/${visit.id}/zone`, {
    data: {
      zone_id: destinationZoneId,
      expected_state_token: staleToken,
      idempotency_key: `e2e-stale-bulk-correct-zone-move-${visit.id}`,
    },
  });
  expect(moved.ok()).toBeTruthy();
  const movedPayload = await moved.json();
  const authoritativeToken: string = movedPayload.review_state_token;
  expect(authoritativeToken).not.toBe(staleToken);

  // Reviewer A, still holding the page from before that move, fills in a
  // correction and applies it -- driving the real ReviewQueuePage
  // request-construction code path, not a hand-built request.
  await page
    .getByPlaceholder("reviewed species, label, unknown, or false_positive")
    .fill("blue_jay");
  page.once("dialog", (dialog) => void dialog.accept());

  const [bulkCorrectRequest] = await Promise.all([
    page.waitForRequest(
      (request) =>
        request.url().includes("/api/review-queue/bulk-correct") && request.method() === "POST",
    ),
    page.getByRole("button", { name: "Apply correction" }).click(),
  ]);

  // The real frontend request must actually carry the stale token this
  // page loaded, not the (now-different) authoritative one.
  const requestBody = bulkCorrectRequest.postDataJSON() as {
    expected_state_tokens?: Record<string, string>;
  };
  expect(requestBody.expected_state_tokens?.[visit.id]).toBe(staleToken);
  expect(requestBody.expected_state_tokens?.[visit.id]).not.toBe(authoritativeToken);

  // Rejected, not silently applied -- the product does not claim success.
  await expect(page.getByText("0 saved, 0 skipped, 1 failed.")).toBeVisible();
  await expect(
    page.getByText(
      "1 item changed since this page last loaded it and was not saved -- refresh and review it again below.",
    ),
  ).toBeVisible();
  await page.getByText("Per-item batch results").click();
  await expect(
    page.getByText(`${visit.id}: Failed. This item changed. Refresh it before saving a correction.`),
  ).toBeVisible();

  // Reviewer B's newer truth remains authoritative: the Zone move
  // persisted, and Alice's stale correction never became reviewed truth.
  const afterAttempt = await page.request.get(`/api/visits/${visit.id}/detail`);
  const afterAttemptPayload = await afterAttempt.json();
  expect(afterAttemptPayload.visit.zone_id).toBe(destinationZoneId);
  expect(afterAttemptPayload.visit.review_status).toBe("needs_review");
  expect(afterAttemptPayload.visit.reviewed_label).toBeFalsy();
});
