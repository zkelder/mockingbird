import { expect, test } from "@playwright/test";

// Broader Wildlife Maturity v1 (see docs/broader-wildlife-maturity-v1-
// contract.md). Two real, interactive UI journeys that a repository-level
// test cannot exercise: the Fast Review "Unknown animal" one-click action
// (previously only "Unknown bird" had a one-click/keyboard path), and the
// ordinary correction toast now saying something honest for a non-bird
// taxon instead of always "Added to Bird Log." Both against the real
// running backend (page.request), matching review-queue-reviewed-tab.
// spec.ts's own established convention -- not route-mocked. Each test owns
// a real Source and Visit, scopes the queue to that Visit, and checks the
// truth it saved there (Browser Suite Determinism & Demo-Boundary Closure
// v1: the old version imported onto the demo Stream and acted on "the
// first card", so it could not reach its subject at all).

const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

const DEMO_STREAM_ID = "stream-backyard-feeder";
const DEMO_VISIT_ID = "visit-bird-feeder-001";

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

/** A real (non-demo) Source/Stream, uniquely named so the Review Queue's
 * search can scope to it. The seeded demo Stream's Visits never reach the
 * Review Queue (demo exclusion, by contract), so importing onto it -- as
 * this spec used to -- left nothing to review. */
async function createRealSource(page: import("@playwright/test").Page, label: string) {
  const name = `Broader Wildlife ${label} ${Date.now()}`;
  const created = await page.request.post("/api/sources", { data: { name } });
  expect(created.ok()).toBeTruthy();
  const { source, stream } = await created.json();
  return { name, sourceId: source.id as string, streamId: stream.id as string };
}

/** One unreviewed "animal" Visit; a real imported animal Visit lands on the
 * default Animals tab. */
async function importUnreviewedAnimalVisit(
  page: import("@playwright/test").Page,
  streamId: string,
  name: string,
): Promise<string> {
  const imported = await page.request.post("/api/media/import", {
    multipart: {
      file: { name, mimeType: "image/jpeg", buffer: Buffer.from(TINY_JPEG_BASE64, "base64") },
      stream_id: streamId,
      subject_label: "animal",
    },
  });
  expect(imported.ok()).toBeTruthy();
  const { visit } = await imported.json();
  return visit.id as string;
}

/** Demo control: the seeded demo Visit is still unresolved, yet the visible
 * queue counts nothing on the demo Stream. */
async function expectDemoActivityExcluded(page: import("@playwright/test").Page) {
  await useSeededSourceAsDemo(page);
  const demoVisit = await (await page.request.get(`/api/visits/${DEMO_VISIT_ID}`)).json();
  expect(demoVisit.review_status).toBe("needs_review");
  const summary = await (await page.request.get("/api/review-queue/summary")).json();
  expect(summary.needs_review_by_stream[DEMO_STREAM_ID]).toBeUndefined();
}

/** Opens the Review Queue searched down to this spec's own data (the suite
 * shares one instance, so "the first card" could belong to another spec). */
async function openReviewQueueSearchedFor(
  page: import("@playwright/test").Page,
  search: string,
  expectedCards: number,
) {
  await page.goto("/review");
  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();
  await page.getByText("Filter review items", { exact: true }).click();
  await page.getByPlaceholder("label, stream, source, zone, suggestion").fill(search);
  const cards = page.locator("article.queue-card");
  await expect(cards).toHaveCount(expectedCards);
  return cards;
}

async function archiveSource(page: import("@playwright/test").Page, sourceId: string) {
  const archived = await page.request.patch(`/api/sources/${sourceId}`, { data: { archived: true } });
  expect(archived.ok()).toBeTruthy();
}

test("Fast Review's one-click Unknown animal action saves real reviewed truth", async ({ page }) => {
  // Two Visits: Fast Review shows "Saved <label>." (with Undo) on the panel
  // of the *next* item. After the last item it switches to "Filtered queue
  // complete", which does not repeat it, so with one Visit the confirmation
  // was only visible while the post-save refresh was in flight -- a timing
  // race on a busy shared instance.
  const source = await createRealSource(page, "Fast Review");
  const firstVisitId = await importUnreviewedAnimalVisit(page, source.streamId, "broader-wildlife-fast-review-1.jpg");
  const secondVisitId = await importUnreviewedAnimalVisit(page, source.streamId, "broader-wildlife-fast-review-2.jpg");
  await expectDemoActivityExcluded(page);

  // Both cards are this spec's own; either may be opened first.
  const cards = await openReviewQueueSearchedFor(page, source.name, 2);
  await cards.first().getByRole("button", { name: "Fast review" }).click();

  const fastReview = page.getByRole("region", { name: "Fast Review" });
  await expect(fastReview).toBeVisible();
  const unknownAnimalButton = fastReview.getByRole("button", { name: "Unknown animal", exact: true });
  await expect(unknownAnimalButton).toBeVisible();
  await fastReview.getByText("Keyboard shortcuts").click();
  await expect(fastReview.getByText("A: unknown animal", { exact: false })).toBeVisible();
  await unknownAnimalButton.click();

  await expect(fastReview.getByText("Saved Unknown Animal.", { exact: false })).toBeVisible();
  // Exactly one of this spec's two Visits now holds the saved truth; the
  // other is still waiting (Fast Review advanced to it).
  const visits = await Promise.all(
    [firstVisitId, secondVisitId].map(async (id) => (await page.request.get(`/api/visits/${id}`)).json()),
  );
  expect(visits.map((visit) => visit.review_status).sort()).toEqual(["needs_review", "reviewed"]);
  const saved = visits.find((visit) => visit.review_status === "reviewed");
  expect(saved.reviewed_label).toBe("unknown_animal");

  await archiveSource(page, source.sourceId);
});

test("marking false positive shows an honest toast, not Added to Bird Log", async ({ page }) => {
  // The live review queue always renders in "Product Mode"
  // (`const productMode = true`, ReviewQueuePage.tsx -- a pre-existing,
  // unrelated condition, not something this milestone changed); its one
  // reachable saveCorrectionWithLabel call site is the False Positive
  // button. This is also one of the two concrete cases the contract doc
  // cites as previously wrong ("Marking a Visit false_positive -- explicitly
  // not an animal -- also said 'Added to Bird Log'").
  const source = await createRealSource(page, "False Positive");
  const visitId = await importUnreviewedAnimalVisit(page, source.streamId, "broader-wildlife-toast.jpg");
  await expectDemoActivityExcluded(page);

  const cards = await openReviewQueueSearchedFor(page, visitId, 1);
  await cards.first().getByRole("button", { name: "False positive" }).click();

  await expect(page.getByText("Marked as false positive. Correction saved as local dataset truth.", { exact: false })).toBeVisible();
  await expect(page.getByText("Added to Bird Log", { exact: false })).toHaveCount(0);
  const visit = await (await page.request.get(`/api/visits/${visitId}`)).json();
  expect(visit.reviewed_label).toBe("false_positive");

  await archiveSource(page, source.sourceId);
});
