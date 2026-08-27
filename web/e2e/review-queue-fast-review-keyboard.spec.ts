import { expect, test } from "@playwright/test";

// Whole-Product UI / Accessibility / Performance Closure v1.
//
// Two real, live-verified defects fixed together, exercised end to end
// through the same journey because the second is only reachable through
// the first:
//
// 1. A manually imported Visit (`event_type == "manual_media_import"`,
//    ManualImportPage's default, promoted camera-less acquisition path)
//    never populates MotionEvidence and was silently classified
//    `product_category == "unchecked"` regardless of its subject_label --
//    invisible from Review Queue's default "Animals" tab even though it is
//    genuine, real unreviewed wildlife activity. This is the actual root
//    cause of the long-standing `reviewed-product-loop.spec.ts` failure,
//    previously misattributed as an unrelated pre-existing flake across at
//    least three prior milestones' own acceptance records -- see
//    ProductRepository's `_review_queue_triage_fields`.
// 2. Activating "Start Fast Review" swaps a large new region into the page
//    in place, with no navigation -- confirmed live via keyboard that this
//    left focus stranded on `document.body`, forcing a keyboard/
//    screen-reader user to Tab from the very top of the page to reach the
//    form that had just appeared. Fixed by moving focus to the new
//    region's own heading (`FastReviewPanel`'s `activeItemHeadingRef`),
//    the same WAI-ARIA "focus the new region" pattern already used for the
//    mobile nav drawer.

const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

async function importUnreviewedVisit(
  page: import("@playwright/test").Page,
): Promise<{ visitId: string; sourceId: string }> {
  // A dedicated, real (non-demo) Source/Stream -- `POST /api/sources`
  // mirrors the plain "Add Camera" flow (`kind` defaults to
  // "local_camera"), matching real users, not this suite's shared demo
  // fixture Stream (`kind == "demo"`), which is always `legacy_activity`
  // by design and would never exercise the fix under test.
  const created = await page.request.post("/api/sources", {
    data: { name: `Fast Review Keyboard Fixture ${Date.now()}` },
  });
  expect(created.ok()).toBeTruthy();
  const { source, stream } = await created.json();

  const imported = await page.request.post("/api/media/import", {
    multipart: {
      file: {
        name: "fast-review-keyboard.jpg",
        mimeType: "image/jpeg",
        buffer: Buffer.from(TINY_JPEG_BASE64, "base64"),
      },
      stream_id: stream.id,
      subject_label: "unknown_animal",
    },
  });
  expect(imported.ok()).toBeTruthy();
  const { visit } = await imported.json();
  return { visitId: visit.id as string, sourceId: source.id as string };
}

test("an imported Visit is reviewable from the default Animals tab, and Fast Review is fully keyboard-operable", async ({
  page,
}) => {
  const { visitId, sourceId } = await importUnreviewedVisit(page);

  await page.goto("/review");
  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();

  // Regression 1: the default view is the "Animals" tab (no click needed),
  // and the just-imported Visit must already be visible there -- not
  // hidden under "Unchecked" with no obvious way back to it.
  const animalsTab = page.getByRole("button", { name: /^Animals/ });
  await expect(animalsTab).toBeVisible();
  await expect(page.getByText("No review items match these filters")).toHaveCount(0);
  const cards = page.locator("article.queue-card");
  await expect(cards.first()).toBeVisible();

  // Regression 2: Fast Review is reachable and operable by keyboard alone,
  // and activating it does not strand focus on <body>.
  const startFastReview = page.getByRole("button", { name: /Start Fast Review/ });
  await startFastReview.focus();
  await expect(startFastReview).toBeFocused();
  await page.keyboard.press("Enter");

  const panel = page.locator("section.fast-review-panel");
  await expect(panel).toBeVisible();
  const panelHeading = panel.locator("h2");
  await expect(panelHeading).toBeFocused();
  const focusedTag = await page.evaluate(() => document.activeElement?.tagName);
  expect(focusedTag).not.toBe("BODY");

  // Complete the correction using only the keyboard from this point on.
  const labelInput = page.getByLabel("Confirm species or wildlife label");
  await labelInput.focus();
  await page.keyboard.type("northern_cardinal");
  const saveAndNext = page.getByRole("button", { name: "Save & Next" });
  await expect(saveAndNext).toBeEnabled();
  await saveAndNext.focus();
  await page.keyboard.press("Enter");

  // This fixture creates exactly one matching unresolved Visit, so saving
  // it advances Fast Review straight to "queue complete" rather than a
  // next item -- assert that transition (not a specific processed-count
  // string, which only the mid-queue view renders) as the UI-level
  // confirmation, then confirm the underlying write is real and correct.
  await expect(page.getByRole("heading", { name: "Filtered queue complete" })).toBeVisible();

  const visitResponse = await page.request.get(`/api/visits/${visitId}`);
  const visitPayload = await visitResponse.json();
  expect(visitPayload.review_status).toBe("reviewed");
  expect(visitPayload.reviewed_label).toBe("northern_cardinal");

  // This suite runs every spec against one shared instance/database
  // (`playwright.config.ts`'s own `globalSetup`) -- a real, non-demo,
  // "today"-dated confirmed Visit left behind here was found live to leak
  // into a *different*, later-running spec's "no wildlife activity yet
  // today" empty-state assertion (`today-report.spec.ts`), since Today's
  // real (unmocked) activity excludes only demo/archived Sources by
  // default, not merely "created by another test." Archiving mirrors
  // exactly how this codebase's own accepted default-exclusion behavior
  // (Multi-Camera Place Experience v2) already keeps a Source's history
  // out of every ordinary discovery surface's default view.
  const archived = await page.request.patch(`/api/sources/${sourceId}`, {
    data: { archived: true },
  });
  expect(archived.ok()).toBeTruthy();
});
