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

test("correcting one real item reports the real remaining count, never counting the seeded demo Visit", async ({
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
  const { visit } = await imported.json();

  // Explicit demo control: the seeded demo Visit is still unresolved, so a
  // demo-inclusive count would announce one more item than the real count.
  await useSeededSourceAsDemo(page);
  const demoVisit = await page.request.get("/api/visits/visit-bird-feeder-001");
  expect(demoVisit.ok()).toBeTruthy();
  expect((await demoVisit.json()).review_status).toBe("needs_review");

  await page.goto("/review");
  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();

  // Default "Animals" tab, no click needed. The suite shares one instance,
  // so scope the list to this spec's own Visit rather than assume it is the
  // only real item.
  await page.getByText("Filter review items", { exact: true }).click();
  await page.getByPlaceholder("label, stream, source, zone, suggestion").fill(visit.id);
  const cards = page.locator("article.queue-card");
  await expect(cards).toHaveCount(1);

  // Real outstanding work right before the correction (demo-excluded by
  // `/api/review-queue/summary`, the same visible needs-review set that
  // backs the response's `review_queue_count`). A fresh instance has exactly
  // this spec's item, so this is the original "0 items" assertion there.
  const summary = await (await page.request.get("/api/review-queue/summary")).json();
  const realNeedsReview = Object.values(summary.needs_review_by_stream as Record<string, number>).reduce(
    (total, count) => total + count,
    0,
  );
  expect(summary.needs_review_by_stream[stream.id]).toBe(1);
  const remaining = realNeedsReview - 1;

  await cards.first().getByRole("button", { name: "False positive" }).click();

  // The regression: before this fix, this response's `review_queue_count`
  // was an unfiltered `len(_review_queue_items(session))`, which counts the
  // seeded demo Source's own still-needs-review `visit-bird-feeder-001` as
  // if it were outstanding real work -- announcing one more than the real
  // remaining count (on a fresh instance, "1" instead of "0").
  await expect(
    page.getByText(new RegExp(`(^|\\D)${remaining} item${remaining === 1 ? "" : "s"} still need review\\.`)),
  ).toBeVisible();
  const resolved = await (await page.request.get(`/api/visits/${visit.id}`)).json();
  expect(resolved.review_status).not.toBe("needs_review");
});
