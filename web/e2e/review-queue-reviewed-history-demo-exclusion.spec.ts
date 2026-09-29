import { expect, test } from "@playwright/test";

// Owner-Only Final Release Hardening -- Browser Suite Determinism &
// Demo-Boundary Closure v1. Review Queue's collapsed "Reviewed history"
// panel (`CorrectionAuditPanel`) titles every entry "Correction truth". It
// used to read the raw, demo-inclusive `GET /api/review-labels`, so a fresh
// install listed the seeded demo squirrel label (`review-label-squirrel-001`
// on `event-squirrel-ground-001`) as the user's own reviewed history, while
// the Reviewed tab, Bird Log and exports already excluded demo activity.
// The page now reads `?real_sources_only=true`; the raw read stays
// demo-inclusive for diagnostic/audit use.

const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

const DEMO_SEED_LABEL_ID = "review-label-squirrel-001";
const DEMO_SEED_EVENT_ID = "event-squirrel-ground-001";

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

test("Reviewed history lists a real human correction and never the seeded demo label", async ({ page }) => {
  // Negative-control precondition: the demo seed label really exists in
  // raw storage, so its absence below is the filter, not an empty fixture.
  await useSeededSourceAsDemo(page);
  const raw = await page.request.get("/api/review-labels");
  expect(raw.ok()).toBeTruthy();
  const rawLabels = (await raw.json()) as Array<{ id: string }>;
  expect(rawLabels.map((label) => label.id)).toContain(DEMO_SEED_LABEL_ID);

  // Positive control: a genuine human correction on a real Source's Visit.
  const created = await page.request.post("/api/sources", {
    data: { name: `Reviewed History Fixture ${Date.now()}` },
  });
  expect(created.ok()).toBeTruthy();
  const { source, stream } = await created.json();
  const imported = await page.request.post("/api/media/import", {
    multipart: {
      file: {
        name: "reviewed-history-demo-exclusion.jpg",
        mimeType: "image/jpeg",
        buffer: Buffer.from(TINY_JPEG_BASE64, "base64"),
      },
      stream_id: stream.id,
      subject_label: "unknown_animal",
    },
  });
  expect(imported.ok()).toBeTruthy();
  const { visit } = await imported.json();
  const corrected = await page.request.post("/api/review-labels", {
    data: {
      review_origin: "human",
      target_type: "visit",
      target_id: visit.id,
      label: "northern_cardinal",
    },
  });
  expect(corrected.status()).toBe(201);

  await page.goto("/review");
  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();
  const history = page.locator("details.correction-audit-panel");
  await history.locator("summary").click();

  // This spec's own entry, scoped by its own Visit id (the shared instance
  // accumulates other specs' corrections).
  const ownEntry = history.locator("article.correction-audit-item", {
    has: page.getByText(`Record: ${visit.id}`, { exact: true }),
  });
  await expect(ownEntry).toHaveCount(1);
  await expect(ownEntry.getByText("Correction truth")).toBeVisible();
  await expect(ownEntry.getByText("Northern Cardinal")).toBeVisible();

  // The demo seed label is absent from the product surface.
  await expect(history.getByText(`Record: ${DEMO_SEED_EVENT_ID}`)).toHaveCount(0);

  // Leave no real, today-dated reviewed Visit visible to later specs'
  // default views (same convention as review-queue-fast-review-keyboard).
  const archived = await page.request.patch(`/api/sources/${source.id}`, { data: { archived: true } });
  expect(archived.ok()).toBeTruthy();
});
