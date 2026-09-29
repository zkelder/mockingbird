import { expect, test, type Page } from "@playwright/test";

// Owner-Only Final Release Hardening -- Fast Review Queue-End Undo v1.
//
// Saving the final Visit of a filtered Fast Review session switches the
// panel to "Filtered queue complete". That screen used to drop the "Saved
// <label>." confirmation and the "Undo last correction" control (and the
// `Z` shortcut) even though the session still held a valid undo token, so
// the one correction most likely to need undoing -- the last one -- could
// not be undone from Fast Review at all. Each test uses one Visit on its
// own real (non-demo) Source, so the final save always lands on the
// completion screen, and archives the Source afterwards so the confirmed
// Visit never leaks into another spec's empty-state assertions.

const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

interface VisitFixture {
  visitId: string;
  sourceId: string;
}

interface ReviewLabelRow {
  id: string;
  target_id: string;
  label: string;
  notes: string | null;
  is_authoritative: boolean;
}

async function importVisitOnRealSource(page: Page, name: string): Promise<VisitFixture> {
  // `POST /api/sources` mirrors the plain "Add Camera" flow (a real,
  // non-demo Source); the shared demo Stream never reaches the Review Queue.
  const created = await page.request.post("/api/sources", {
    data: { name: `${name} ${Date.now()}` },
  });
  expect(created.ok()).toBeTruthy();
  const { source, stream } = await created.json();
  const imported = await page.request.post("/api/media/import", {
    multipart: {
      file: {
        name: "fast-review-queue-end-undo.jpg",
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

async function archiveSource(page: Page, sourceId: string): Promise<void> {
  const archived = await page.request.patch(`/api/sources/${sourceId}`, {
    data: { archived: true },
  });
  expect(archived.ok()).toBeTruthy();
}

async function visitState(page: Page, visitId: string) {
  const response = await page.request.get(`/api/visits/${visitId}`);
  expect(response.ok()).toBeTruthy();
  const payload = await response.json();
  return {
    review_status: payload.review_status as string,
    reviewed_label: (payload.reviewed_label ?? null) as string | null,
  };
}

// Effective ReviewLabels only: a reversed Fast Review correction and its
// reversal row both drop out of this read, so an undone Visit has none.
async function labelsFor(page: Page, visitId: string): Promise<ReviewLabelRow[]> {
  const response = await page.request.get("/api/review-labels");
  expect(response.ok()).toBeTruthy();
  const rows = (await response.json()) as ReviewLabelRow[];
  return rows.filter((row) => row.target_id === visitId);
}

// Scopes the Review Queue to this test's own Visit (the suite shares one
// instance) and opens Fast Review on it.
async function openFastReviewOn(page: Page, visitId: string): Promise<void> {
  await page.goto("/review");
  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();
  await page.getByText("Filter review items", { exact: true }).click();
  await page.getByPlaceholder("label, stream, source, zone, suggestion").fill(visitId);
  await expect(page.locator("article.queue-card")).toHaveCount(1);
  await page.getByRole("button", { name: "Start Fast Review (1)" }).click();
  await expect(page.locator("section.fast-review-panel h2")).toBeFocused();
  await expect(page.locator("section.fast-review-panel")).toContainText(
    "0 reviewed this session · 1 matching unresolved Visit",
  );
}

test("undo stays available on the queue-complete screen, by click and by Z, and restores the Visit", async ({
  page,
}) => {
  const { visitId, sourceId } = await importVisitOnRealSource(page, "Fast Review Queue-End Undo");
  const before = await visitState(page, visitId);
  expect(before.review_status).not.toBe("reviewed");

  await openFastReviewOn(page, visitId);
  const undoRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/review-queue/fast/undo")) undoRequests.push(request.url());
  });

  // --- Round 1: save the final item by click, undo by click. ---
  await page.getByRole("button", { name: "Blank / no activity" }).click();
  const completeHeading = page.getByRole("heading", { name: "Filtered queue complete" });
  await expect(completeHeading).toBeVisible();
  await expect(completeHeading).toBeFocused();
  const complete = page.locator("section.fast-review-complete");
  await expect(complete).toContainText(/Saved [^.]+\./);
  const undoButton = complete.getByRole("button", { name: "Undo last correction" });
  await expect(undoButton).toBeVisible();
  await expect(undoButton).toBeEnabled();

  // The correction is real, authoritative truth before it is undone.
  expect(await visitState(page, visitId)).toEqual({ review_status: "reviewed", reviewed_label: "blank" });
  const afterSave = await labelsFor(page, visitId);
  expect(afterSave).toHaveLength(1);
  expect(afterSave[0]).toMatchObject({ label: "blank", is_authoritative: true });

  // Correction shortcuts have nothing to act on here, so they must not run.
  await page.keyboard.press("c");
  await page.keyboard.press("b");
  // Typing-target protection: `z` typed into a text field is text, never undo.
  const filter = page.getByPlaceholder("label, stream, source, zone, suggestion");
  await filter.focus();
  await page.keyboard.press("End");
  await page.keyboard.press("z");
  await expect(filter).toHaveValue(visitId + "z");
  await page.keyboard.press("Backspace");
  await expect(filter).toHaveValue(visitId);
  await page.waitForTimeout(750);
  expect(undoRequests).toHaveLength(0);
  expect(await labelsFor(page, visitId)).toHaveLength(1);
  expect(await visitState(page, visitId)).toEqual({ review_status: "reviewed", reviewed_label: "blank" });

  await expect(undoButton).toBeVisible();
  const firstUndo = page.waitForResponse((response) => response.url().includes("/api/review-queue/fast/undo"));
  await undoButton.click();
  const firstUndoResponse = await firstUndo;
  expect(firstUndoResponse.status()).toBe(200);
  const firstReversal = await firstUndoResponse.json();
  expect(firstReversal.target_id).toBe(visitId);
  expect(firstReversal.reversal_review_label_id).toBeTruthy();

  // The exact Visit returns as the active Fast Review item, focused, with
  // the session and queue counts restored.
  const panel = page.locator("section.fast-review-panel");
  await expect(panel).toBeVisible();
  await expect(panel.locator("h2")).toBeFocused();
  await expect(panel).toContainText("0 reviewed this session · 1 matching unresolved Visit");
  await expect(panel).toContainText("Correction undone. The Visit is back in its prior review state.");
  await expect(panel.getByRole("button", { name: "Undo last correction" })).toHaveCount(0);
  expect(await visitState(page, visitId)).toEqual(before);
  expect(await labelsFor(page, visitId)).toHaveLength(0);
  expect(undoRequests).toHaveLength(1);

  // --- Round 2: save the final item by keyboard, undo with `Z`. ---
  await page.keyboard.press("k");
  await expect(completeHeading).toBeVisible();
  await expect(completeHeading).toBeFocused();
  await expect(complete).toContainText(/Saved [^.]+\./);
  expect(await visitState(page, visitId)).toEqual({ review_status: "reviewed", reviewed_label: "unknown_bird" });
  const afterSecondSave = await labelsFor(page, visitId);
  expect(afterSecondSave).toHaveLength(1);
  expect(afterSecondSave[0]).toMatchObject({ label: "unknown_bird", is_authoritative: true });

  const secondUndo = page.waitForResponse((response) => response.url().includes("/api/review-queue/fast/undo"));
  await page.keyboard.press("z");
  const secondUndoResponse = await secondUndo;
  expect(secondUndoResponse.status()).toBe(200);
  const secondReversal = await secondUndoResponse.json();
  expect(secondReversal.target_id).toBe(visitId);
  expect(secondReversal.reversal_review_label_id).not.toBe(firstReversal.reversal_review_label_id);
  await expect(panel).toBeVisible();
  await expect(panel.locator("h2")).toBeFocused();
  await expect(panel).toContainText("0 reviewed this session · 1 matching unresolved Visit");
  expect(await visitState(page, visitId)).toEqual(before);
  expect(await labelsFor(page, visitId)).toHaveLength(0);
  expect(undoRequests).toHaveLength(2);

  // Back on the Review Queue, the restored Visit is counted as unresolved again.
  await panel.getByRole("button", { name: "Exit" }).click();
  await expect(page.getByRole("button", { name: "Start Fast Review (1)" })).toBeVisible();

  await archiveSource(page, sourceId);
});

test("a superseded undo token on the queue-complete screen shows the honest error and changes nothing", async ({
  page,
}) => {
  const { visitId, sourceId } = await importVisitOnRealSource(page, "Fast Review Superseded Undo");
  await openFastReviewOn(page, visitId);

  await page.getByRole("button", { name: "Blank / no activity" }).click();
  const complete = page.locator("section.fast-review-complete");
  await expect(page.getByRole("heading", { name: "Filtered queue complete" })).toBeVisible();
  await expect(complete).toContainText(/Saved [^.]+\./);

  // A newer, human correction elsewhere supersedes the Fast Review one.
  const newer = await page.request.post("/api/review-labels", {
    data: {
      target_type: "visit",
      target_id: visitId,
      label: "northern_cardinal",
      notes: "Corrected outside Fast Review.",
      review_origin: "human",
    },
  });
  expect(newer.ok()).toBeTruthy();

  const rejectedUndo = page.waitForResponse((response) => response.url().includes("/api/review-queue/fast/undo"));
  await complete.getByRole("button", { name: "Undo last correction" }).click();
  expect((await rejectedUndo).status()).toBe(409);
  await expect(complete).toContainText("Fast Review undo is no longer available.");
  await expect(complete).not.toContainText("Correction undone");
  await expect(page.locator("section.fast-review-panel")).toHaveCount(0);
  expect(await visitState(page, visitId)).toEqual({
    review_status: "reviewed",
    reviewed_label: "northern_cardinal",
  });
  const labels = await labelsFor(page, visitId);
  expect(labels.map((row) => row.label)).toContain("northern_cardinal");

  await archiveSource(page, sourceId);
});
