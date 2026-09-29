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

// The seeded demo Stream's Visits never reach the Review Queue (demo
// exclusion, by contract), so this spec owns a real Source, Stream and two
// Zones -- the same `POST /api/sources` fixture shape as
// review-queue-count-demo-exclusion.spec.ts.
const DEMO_STREAM_ID = "stream-backyard-feeder";
const DEMO_VISIT_ID = "visit-bird-feeder-001";
const SQUARE = [
  { x: 0.1, y: 0.1 },
  { x: 0.9, y: 0.1 },
  { x: 0.9, y: 0.9 },
  { x: 0.1, y: 0.9 },
];
const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

/** Other specs in this shared suite deliberately repurpose the seeded demo
 * Source into a real camera (Guided Camera Editing), after which its seeded
 * activity is real history by contract (`_real_source_condition`). A demo
 * control therefore owns that state: it first returns the seeded Source to
 * its demo provider through the ordinary provider-configuration API. */
async function useSeededSourceAsDemo(page: import("@playwright/test").Page) {
  const restored = await page.request.patch("/api/sources/source-backyard-demo/provider-configuration", {
    data: { provider_key: "demo", config: {} },
  });
  expect(restored.ok()).toBeTruthy();
}

test("a bulk correction submitted with a stale review_state_token is rejected, not silently applied, while a concurrent Zone move remains authoritative", async ({
  page,
}) => {
  const created = await page.request.post("/api/sources", {
    data: { name: `Bulk Correct Stale Write Fixture ${Date.now()}` },
  });
  expect(created.ok()).toBeTruthy();
  const { source, stream } = await created.json();
  const zoneIds: string[] = [];
  for (const [name, zoneType] of [
    ["Feeder", "feeder"],
    ["Ground", "ground"],
  ]) {
    const zoneResponse = await page.request.post("/api/zones", {
      data: { stream_id: stream.id, name, zone_type: zoneType, polygon: SQUARE },
    });
    expect(zoneResponse.ok()).toBeTruthy();
    zoneIds.push((await zoneResponse.json()).zone.id as string);
  }
  const [feederZoneId, groundZoneId] = zoneIds;

  // Seed a reviewable Visit -- same real product path as
  // review-queue-reviewed-tab.spec.ts's own fixture helper.
  const imported = await page.request.post("/api/media/import", {
    multipart: {
      file: {
        name: "bulk-correct-stale-write.jpg",
        mimeType: "image/jpeg",
        buffer: Buffer.from(TINY_JPEG_BASE64, "base64"),
      },
      stream_id: stream.id,
      subject_label: "animal",
    },
  });
  expect(imported.ok()).toBeTruthy();
  const { visit } = await imported.json();

  // Demo control: the seeded demo Visit is still unresolved, yet the
  // visible queue counts nothing on the demo Stream.
  await useSeededSourceAsDemo(page);
  const demoVisit = await (await page.request.get(`/api/visits/${DEMO_VISIT_ID}`)).json();
  expect(demoVisit.review_status).toBe("needs_review");
  const summary = await (await page.request.get("/api/review-queue/summary")).json();
  expect(summary.needs_review_by_stream[DEMO_STREAM_ID]).toBeUndefined();

  // Reviewer A opens the Review Queue: this loads the item's current
  // review_state_token (T1) into the page's own React state, exactly
  // like a real signed-in reviewer with this page open. A real imported
  // animal Visit lands on the default Animals tab; the search filter scopes
  // the list to this spec's own Visit on the shared instance.
  await page.goto("/review");
  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();
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
  const destinationZoneId = currentZoneId === groundZoneId ? feederZoneId : groundZoneId;

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
      "1 item changed since this page last loaded it and was not saved — refresh and review it again below.",
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

  // Hygiene for the shared instance (same convention as
  // review-queue-fast-review-keyboard.spec.ts): keep this spec's still-
  // unresolved Visit out of later specs' default views.
  const archived = await page.request.patch(`/api/sources/${source.id}`, { data: { archived: true } });
  expect(archived.ok()).toBeTruthy();
});
