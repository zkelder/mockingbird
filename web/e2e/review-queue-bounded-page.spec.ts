import { expect, test } from "@playwright/test";

// Review Queue Scale Closure v1. Performance / Scale / Stability Closure v1
// left one release-blocking P0 open: the Review Queue page downloaded the
// entire queue -- reviewed history included -- on mount and again after every
// saved correction (2,058 items / 14.9 MB at its burst profile), and computed
// every tab count, filter count and "showing N of M" disclosure client-side
// over that download.
//
// This spec drives the real page in a real browser and proves both halves of
// the fix at once: the requests it makes are bounded, and the numbers it shows
// still describe the whole queue. It watches the network directly, because
// "no full-history payload is fetched" is a statement about requests, not
// about rendering.
//
// Every expectation is stated against the server's own answer for the same
// view rather than against a fixture count, for two reasons: this suite
// shares one database across specs, so no spec may assume a pristine queue;
// and "the rendered page agrees with server truth" is the stronger claim
// anyway.

const PAGE_SIZE = 25;
const IMPORTED_VISITS = 32;
const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

interface QueueRequest {
  url: string;
  bounded: boolean;
  unbounded: boolean;
}

/** Every `/api/review-queue...` request the page makes, classified. */
function watchQueueRequests(page: import("@playwright/test").Page): QueueRequest[] {
  const seen: QueueRequest[] = [];
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith("/api/review-queue")) {
      return;
    }
    seen.push({
      url: url.pathname + url.search,
      bounded:
        url.pathname === "/api/review-queue/page" ||
        url.pathname === "/api/review-queue/summary",
      // The whole-queue shape: `/api/review-queue` exactly, with or without
      // `include_reviewed`. Its sub-routes (`/page`, `/summary`, `/fast/*`,
      // `/bulk-correct`) are not it.
      unbounded: url.pathname === "/api/review-queue",
    });
  });
  return seen;
}

/** The server's own answer for the Animals tab, as the page requests it. */
async function animalsTruth(
  page: import("@playwright/test").Page,
  { page: pageIndex = 0 }: { page?: number } = {},
) {
  const response = await page.request.get("/api/review-queue/page", {
    params: {
      tab: "animals",
      status: "unreviewed",
      page_size: PAGE_SIZE,
      page: pageIndex,
    },
  });
  expect(response.ok()).toBeTruthy();
  return { body: await response.json(), bytes: (await response.body()).length };
}

async function importVisits(
  page: import("@playwright/test").Page,
  count: number,
): Promise<{ visitIds: string[]; streamId: string }> {
  // A dedicated, real (non-demo) Source/Stream -- `POST /api/sources`
  // mirrors the plain "Add Camera" flow, matching real users, not this
  // suite's shared demo fixture Stream (`kind == "demo"`), whose activity is
  // demo-excluded from the visible queue by design and would never exercise
  // what is under test here. Same reasoning as
  // `review-queue-fast-review-keyboard.spec.ts` and
  // `review-queue-count-demo-exclusion.spec.ts`.
  const created = await page.request.post("/api/sources", {
    data: { name: `Review Queue Bounded Page Fixture ${Date.now()}` },
  });
  expect(created.ok()).toBeTruthy();
  const { stream } = await created.json();

  const visitIds: string[] = [];
  for (let index = 0; index < count; index += 1) {
    const imported = await page.request.post("/api/media/import", {
      multipart: {
        file: {
          name: `review-queue-bounded-${index}.jpg`,
          mimeType: "image/jpeg",
          buffer: Buffer.from(TINY_JPEG_BASE64, "base64"),
        },
        stream_id: stream.id,
        subject_label: "animal",
      },
    });
    expect(imported.ok()).toBeTruthy();
    const { visit } = await imported.json();
    visitIds.push(visit.id as string);
  }
  return { visitIds, streamId: stream.id as string };
}

test("the Review Queue renders one bounded page whose counts still describe the whole queue", async ({
  page,
}) => {
  await importVisits(page, IMPORTED_VISITS);
  const { body: truth, bytes: boundedBytes } = await animalsTruth(page);
  expect(truth.matching_items).toBeGreaterThanOrEqual(IMPORTED_VISITS);
  expect(truth.items).toHaveLength(PAGE_SIZE);

  const requests = watchQueueRequests(page);
  await page.goto("/review");
  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();

  // One page of review cards, never the backlog.
  const cards = page.locator("article.queue-card");
  await expect(cards).toHaveCount(PAGE_SIZE);

  // The tab chip, the disclosure and the pager all report whole-queue
  // numbers, not the 25 on screen.
  await expect(page.getByRole("button", { name: /^Animals/ })).toContainText(
    String(truth.tab_counts.animals),
  );
  await expect(
    page.getByText(`${truth.matching_items} showing / ${truth.total_items} total`),
  ).toBeVisible();
  await expect(
    page.getByText(
      `Page 1 of ${truth.page_count} · ${truth.matching_items} matching Visits`,
    ),
  ).toBeVisible();

  // The mount itself never asked for the whole queue.
  expect(requests.filter((entry) => entry.unbounded)).toHaveLength(0);
  expect(requests.filter((entry) => entry.bounded).length).toBeGreaterThan(0);

  // The window really is bounded: fewer items than match, and fewer bytes
  // than the unbounded shape of the same queue. (How payload scales with
  // *history* is asserted structurally in `tests/test_review_queue_page_
  // scale.py`, where the library size can be controlled; this suite shares
  // one database across specs.)
  expect(truth.items.length).toBeLessThan(truth.matching_items);
  const unbounded = await page.request.get("/api/review-queue?include_reviewed=true");
  expect(unbounded.ok()).toBeTruthy();
  expect(boundedBytes).toBeLessThan((await unbounded.body()).length);
});

test("the next page can be reached, and asks only for that page", async ({ page }) => {
  await importVisits(page, IMPORTED_VISITS);
  const { body: firstTruth } = await animalsTruth(page);
  const { body: secondTruth } = await animalsTruth(page, { page: 1 });
  expect(firstTruth.page_count).toBeGreaterThan(1);

  const requests = watchQueueRequests(page);
  await page.goto("/review");
  const cards = page.locator("article.queue-card");
  await expect(cards).toHaveCount(PAGE_SIZE);
  const firstPageIds = await cards.evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute("data-target-id")),
  );

  await page.getByRole("button", { name: "Next", exact: true }).click();

  await expect(
    page.getByText(
      `Page 2 of ${firstTruth.page_count} · ${firstTruth.matching_items} matching Visits`,
    ),
  ).toBeVisible();
  // Paging is a real request now, so wait for the list to settle on the new
  // page rather than reading it while the previous one is still shown.
  await expect(page.locator("div.queue-list")).toHaveAttribute("aria-busy", "false");
  await expect(cards.first()).toHaveAttribute(
    "data-target-id",
    secondTruth.items[0].target_id,
  );
  await expect(cards).toHaveCount(secondTruth.items.length);

  // Distinct work: no item repeats between the pages, and nothing between
  // them is skipped -- the second page is exactly what the server's own
  // page 1 holds, in its order.
  const secondPageIds = await cards.evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute("data-target-id")),
  );
  expect(new Set(secondPageIds).size).toBe(secondPageIds.length);
  expect(
    secondPageIds.filter((targetId) => firstPageIds.includes(targetId)),
  ).toHaveLength(0);
  expect(secondPageIds).toEqual(
    secondTruth.items.map((item: { target_id: string }) => item.target_id),
  );

  // Paging is one more bounded request for `page=1`, never a re-download.
  expect(requests.filter((entry) => entry.unbounded)).toHaveLength(0);
  expect(requests.some((entry) => entry.url.includes("page=1"))).toBeTruthy();
});

test("correcting an item keeps the page coherent and never reloads history", async ({
  page,
}) => {
  await importVisits(page, IMPORTED_VISITS);
  const { body: before } = await animalsTruth(page);

  await page.goto("/review");
  const cards = page.locator("article.queue-card");
  await expect(cards).toHaveCount(PAGE_SIZE);

  // Start watching only now, so what is asserted is what the *correction*
  // triggers rather than what the mount did.
  const requests = watchQueueRequests(page);

  const firstCard = cards.first();
  const correctedTargetId = await firstCard.getAttribute("data-target-id");
  await firstCard.getByRole("button", { name: "False positive" }).click();

  // One item left the Animals group and arrived in Reviewed, and the counts
  // say so -- these are whole-queue numbers, refreshed from the server.
  await expect(page.getByRole("button", { name: /^Animals/ })).toContainText(
    String(before.tab_counts.animals - 1),
  );
  await expect(
    page.getByText(
      `Page 1 of ${before.page_count} · ${before.matching_items - 1} matching Visits`,
    ),
  ).toBeVisible();
  // The page refilled from the next item rather than leaving a hole, and the
  // corrected item is gone from it.
  await expect(cards).toHaveCount(PAGE_SIZE);
  await expect(
    page.locator(`article.queue-card[data-target-id="${correctedTargetId}"]`),
  ).toHaveCount(0);

  // The refetch after the correction was bounded.
  expect(requests.filter((entry) => entry.unbounded)).toHaveLength(0);
  expect(requests.filter((entry) => entry.bounded).length).toBeGreaterThan(0);

  const after = await page.request.get("/api/review-queue/summary");
  expect(after.ok()).toBeTruthy();
  const summary = await after.json();
  expect(summary.tab_counts.animals).toBe(before.tab_counts.animals - 1);
  expect(summary.tab_counts.reviewed).toBeGreaterThan(0);
});

test("the Reviewed tab and the filters work against the server, not a download", async ({
  page,
}) => {
  const { visitIds } = await importVisits(page, 6);
  const reviewed = await page.request.post("/api/review-labels", {
    data: {
      review_origin: "human",
      target_type: "visit",
      target_id: visitIds[0],
      label: "blue_jay",
    },
  });
  expect(reviewed.ok()).toBeTruthy();

  const { body: truth } = await animalsTruth(page);
  const reviewedResponse = await page.request.get("/api/review-queue/page", {
    params: { tab: "reviewed", page_size: PAGE_SIZE },
  });
  expect(reviewedResponse.ok()).toBeTruthy();
  const reviewedTruth = await reviewedResponse.json();
  expect(reviewedTruth.matching_items).toBeGreaterThan(0);

  const requests = watchQueueRequests(page);
  await page.goto("/review");
  await expect(page.locator("article.queue-card")).toHaveCount(
    Math.min(PAGE_SIZE, truth.matching_items),
  );

  // Reviewed history is not on the initial load at all; opening the tab
  // fetches it, and the card says what it was reviewed as.
  await page.getByRole("button", { name: /^Reviewed/ }).click();
  const reviewedCards = page.locator("article.queue-card");
  await expect(reviewedCards).toHaveCount(
    Math.min(PAGE_SIZE, reviewedTruth.matching_items),
  );
  await expect(reviewedCards.filter({ hasText: "Reviewed: Blue Jay" })).toHaveCount(1);
  expect(requests.some((entry) => entry.url.includes("tab=reviewed"))).toBeTruthy();

  // A filter narrows the result set server-side and the disclosure follows.
  await page.getByRole("button", { name: /^Animals/ }).click();
  await page.getByText("Filter review items").click();
  await page.getByLabel("Search").fill("no-such-species-anywhere");
  await expect(page.getByText(`0 showing / ${truth.total_items} total`)).toBeVisible();
  expect(
    requests.some((entry) => entry.url.includes("search=no-such-species-anywhere")),
  ).toBeTruthy();

  await page.getByLabel("Search").fill("");
  await expect(page.locator("article.queue-card")).toHaveCount(
    Math.min(PAGE_SIZE, truth.matching_items),
  );

  // Nothing in this whole session asked for the unbounded queue.
  expect(requests.filter((entry) => entry.unbounded)).toHaveLength(0);
});
