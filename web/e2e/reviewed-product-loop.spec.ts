import { expect, test } from "@playwright/test";

// The primary reviewed-truth product loop, end to end in a real browser:
// a ranked, uncalibrated species suggestion stays evidence in Review Queue;
// an explicit human correction (prefilled from the suggestion's rank-2
// alternative, then saved) becomes Reviewed truth; that one correction then
// reads coherently in the Review Queue's Reviewed tab, Bird Log and the
// reviewed-only dataset export.
//
// Owner-Only Final Release Hardening -- Reviewed-Truth Browser Closure v1
// rewrote this spec's fixture, not its claims. It used to attach the
// suggestion to the seeded demo Visit (`visit-bird-feeder-001` on the demo
// Source) and correct it inline from a "Review bird visit" Review Queue card.
// Both premises are gone by accepted contract: demo-Source activity is
// excluded from Review Queue, Bird Log and exports so seed data can never
// read as a user's own record (Native-Windows & Packaging Acceptance v1,
// Review Queue Count Truth Consistency v1, UI/UX & First-Run Adoption v1),
// and Review Queue renders product cards whose "Review" action opens Visit
// Detail, where the correction form and ranked alternatives live. The spec
// therefore could never pass again; it now drives a real (non-demo) Source,
// Stream and Zone -- the same fixture shape
// `review-queue-count-demo-exclusion.spec.ts` uses -- through today's path.

const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

test("a ranked species suggestion becomes correction, Bird Log, and export truth", async ({
  page,
}) => {
  const created = await page.request.post("/api/sources", {
    data: { name: `Reviewed Loop Feeder ${Date.now()}` },
  });
  expect(created.ok()).toBeTruthy();
  const { source, stream } = await created.json();

  const zoneResponse = await page.request.post("/api/zones", {
    data: {
      stream_id: stream.id,
      name: "Feeder",
      zone_type: "feeder",
      polygon: [
        { x: 0.1, y: 0.1 },
        { x: 0.9, y: 0.1 },
        { x: 0.9, y: 0.9 },
        { x: 0.1, y: 0.9 },
      ],
    },
  });
  expect(zoneResponse.ok()).toBeTruthy();
  const { zone } = await zoneResponse.json();

  const imported = await page.request.post("/api/media/import", {
    multipart: {
      file: {
        name: "reviewed-product-loop.jpg",
        mimeType: "image/jpeg",
        buffer: Buffer.from(TINY_JPEG_BASE64, "base64"),
      },
      stream_id: stream.id,
      zone_id: zone.id,
      subject_label: "bird",
    },
  });
  expect(imported.ok()).toBeTruthy();
  const { visit } = await imported.json();
  const visitId = visit.id as string;

  const suggestionResponse = await page.request.post("/api/species-suggestions", {
    data: {
      adapter_id: "bioclip_2",
      adapter_name: "BioCLIP 2",
      alternatives: [
        {
          calibrated: false,
          common_name: "Blue Jay",
          label: "blue jay (Cyanocitta cristata)",
          rank: 2,
          scientific_name: "Cyanocitta cristata",
          score: 0.21,
          score_kind: "candidate_relative_softmax",
          suggested_label: "blue_jay",
        },
      ],
      confidence: 0.37,
      evidence_region: {
        calibrated: false,
        coordinate_space: "full_frame_normalized",
        height: 0.2,
        score_semantics: "candidate_relative_softmax",
        source: "activity",
        width: 0.2,
        x: 0.4,
        y: 0.3,
      },
      event_id: visit.event_id,
      rank: 1,
      source_id: source.id,
      stream_id: stream.id,
      suggested_common_name: "Northern Cardinal",
      suggested_label: "northern_cardinal",
      suggested_scientific_name: "Cardinalis cardinalis",
      visit_id: visitId,
    },
  });
  expect(suggestionResponse.ok()).toBeTruthy();
  const suggestion = await suggestionResponse.json();

  // Review Queue: the suggestion is visible, and visibly only evidence.
  await page.goto("/review");
  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();
  const visitCard = page.locator(`article.queue-card[data-target-id="${visitId}"]`);
  await expect(visitCard).toHaveCount(1);
  await expect(visitCard).toContainText("species not confirmed");
  await expect(visitCard).toContainText(stream.name);
  await expect(visitCard).toContainText("Feeder");
  await expect(visitCard).toContainText("Northern Cardinal");
  await expect(visitCard).toContainText("Evidence only.");

  // Saving the suggestion as evidence created no truth.
  const beforeCorrection = await (await page.request.get(`/api/visits/${visitId}`)).json();
  expect(beforeCorrection.review_status).toBe("needs_review");
  expect(beforeCorrection.reviewed_label ?? null).toBeNull();

  await visitCard.getByRole("button", { name: "Review", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/visits/${visitId}$`));

  // Visit Detail: the ranked alternatives are offered as evidence; choosing
  // rank 2 only prefills the correction form.
  const assistant = page.getByRole("region", { name: "Identification Assistant" });
  await expect(assistant).toContainText("Evidence only");
  const rankTwo = assistant
    .locator("article")
    .filter({ has: page.getByRole("heading", { name: "Suggested label: blue_jay" }) });
  await expect(rankTwo).toContainText("Rank 2");
  await rankTwo.getByRole("button", { name: "Use suggestion" }).click();
  const correctionField = page.getByRole("combobox", { name: /^Species correction/ });
  await expect(correctionField).toHaveValue("blue_jay");

  // Prefilling is not saving.
  const afterPrefill = await (await page.request.get(`/api/visits/${visitId}`)).json();
  expect(afterPrefill.review_status).toBe("needs_review");

  await page.getByRole("button", { name: "Confirm species" }).click();
  await expect(page.getByText("Correction saved and suggestion marked accepted.")).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Blue Jay");

  await expect
    .poll(async () => {
      const response = await page.request.get(`/api/species-suggestions/${suggestion.id}`);
      expect(response.ok()).toBeTruthy();
      return (await response.json()).status;
    })
    .toBe("accepted");

  // The human correction -- not the rank-1 suggestion -- is the truth.
  const reviewedVisit = await (await page.request.get(`/api/visits/${visitId}`)).json();
  expect(reviewedVisit.review_status).toBe("reviewed");
  expect(reviewedVisit.reviewed_label).toBe("blue_jay");
  const labels = await (await page.request.get("/api/review-labels")).json();
  const ownLabel = labels.find(
    (label: { target_id: string; target_type: string }) =>
      label.target_type === "visit" && label.target_id === visitId,
  );
  expect(ownLabel.label).toBe("blue_jay");
  expect(ownLabel.review_origin).toBe("human");
  expect(ownLabel.is_authoritative).toBe(true);

  // Review Queue: the Visit left the waiting groups and reads as reviewed.
  await page.getByRole("button", { name: "Review Queue" }).click();
  await expect(page).toHaveURL(/\/review$/);
  await expect(page.locator(`article.queue-card[data-target-id="${visitId}"]`)).toHaveCount(0);
  await page.getByRole("button", { name: /^Reviewed/ }).click();
  const reviewedCard = page.locator(`article.queue-card[data-target-id="${visitId}"]`);
  await expect(reviewedCard).toHaveCount(1);
  await expect(reviewedCard).toContainText("Reviewed: Blue Jay");
  await expect(reviewedCard).not.toContainText("Northern Cardinal");

  // Bird Log: Blue Jay is a confirmed species, and scoped to this spec's own
  // camera it holds exactly this one observation -- the corrected label,
  // never the rank-1 suggestion. (Scoped because the shared browser-suite
  // instance accumulates other specs' Blue Jay truth.)
  await page.getByRole("button", { name: "Bird Log" }).click();
  await expect(page).toHaveURL(/\/bird-log$/);
  await expect(page.getByRole("heading", { name: "Bird Log" })).toBeVisible();
  const birdLogEntry = page.locator(".journal-label-card").filter({ hasText: "Blue Jay" });
  await expect(birdLogEntry).toHaveCount(1);
  await birdLogEntry.getByRole("button", { name: "Open history" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Blue Jay" })).toBeVisible();
  await page.locator("label.camera-filter select").selectOption(stream.id);
  const galleryCards = page.locator("article.journal-gallery-card");
  await expect(galleryCards).toHaveCount(1);
  await expect(galleryCards).toContainText(`${source.name} · ${stream.name} · Feeder`);
  await expect(galleryCards).toContainText("Confirmed");

  const cameraJournal = await (
    await page.request.get(`/api/bird-log/journal?stream_id=${stream.id}`)
  ).json();
  expect(
    cameraJournal.labels.map((entry: { label: string; observation_count: number }) => [
      entry.label,
      entry.observation_count,
    ]),
  ).toEqual([["blue_jay", 1]]);

  // Reviewed-only export: the corrected label, with its Source, Stream and Zone.
  await page.goto("/exports");
  await expect(page.getByRole("heading", { name: "Dataset Exports" })).toBeVisible();
  await page.getByLabel("Export name").fill("Primary product loop proof");
  await page.getByRole("button", { name: "Generate manifest" }).click();

  await expect(page.getByText("Reviewed local dataset manifest generated in memory.")).toBeVisible();
  const exportedVisit = page.locator("article.record-card").filter({ hasText: visitId });
  await expect(exportedVisit).toHaveCount(1);
  await expect(exportedVisit).toContainText("Blue Jay");
  await expect(exportedVisit).not.toContainText("Northern Cardinal");
  await expect(exportedVisit).toContainText(source.id);
  await expect(exportedVisit).toContainText(stream.id);
  await expect(exportedVisit).toContainText("Feeder (Feeder)");
  await expect(exportedVisit).toContainText("Reviewed");
  await expect(exportedVisit).toContainText("Ready for local dataset export");
});
