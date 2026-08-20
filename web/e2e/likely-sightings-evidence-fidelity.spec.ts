import { expect, test } from "@playwright/test";

// LIKELY SIGHTINGS EVIDENCE FIDELITY & ID HONESTY v1.
//
// Real product report: multiple "Likely sightings" cards on Bird Log showed
// apparently identical/near-identical wide yard images under materially
// different, precise species names, and manual review found the underlying
// image sometimes empty while the Visit's own evidence showed something
// else -- a trust problem, not a detection/classification one. Root cause:
// `GET /api/bird-log/likely` (`ProductRepository.list_likely_species_
// overview` -> `_stream_visit_summary_from_models`) only ever returns a
// Visit's generic, persisted `is_primary` evidence frame, never the frame
// the species classifier actually read. Those already-persisted-but-
// unlinked-here facts live on `SpeciesSuggestion.evidence_region.
// classifier_input` and are already surfaced per-Visit as `VisitDetail.
// classifier_supporting_evidence` (Visit Same-Frame Classifier Evidence
// Visibility v1, docs/visit-classifier-evidence-visibility-contract.md).
//
// These specs prove the frontend fix in BirdLogPage.tsx: each Likely
// Sightings card resolves and prefers its own real classifier evidence when
// the backend has it (labeled "Identification evidence"), falls back to an
// honestly-labeled "Visit preview" when it does not, and never mixes up
// which evidence or which Visit belongs to which card. Mirrors visit-
// classifier-supporting-evidence.spec.ts's own `page.route` interception
// technique -- every image byte is served by the real backend; only the
// shaped list/detail JSON responses stand in for real Observation Engine
// data, since driving a real candidate Visit through detection/tracking/
// classification is out of scope for a frontend presentation fix.

const STREAM_ID = "stream-backyard-feeder";
const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

async function importRealPhoto(
  page: import("@playwright/test").Page,
): Promise<{ visitId: string; mediaAssetId: string }> {
  const response = await page.request.post("/api/media/import", {
    multipart: {
      file: {
        name: `evidence-fidelity-${Math.random().toString(36).slice(2)}.jpg`,
        mimeType: "image/jpeg",
        buffer: Buffer.from(TINY_JPEG_BASE64, "base64"),
      },
      stream_id: STREAM_ID,
      subject_label: "unknown_bird",
    },
  });
  expect(response.ok()).toBeTruthy();
  const result = await response.json();
  expect(result.visit).not.toBeNull();
  return { visitId: result.visit.id as string, mediaAssetId: result.media_asset.id as string };
}

/** A minimal, realistic `VisitEvidenceFrame` for a given real media asset. */
function evidenceFrame(mediaAssetId: string, overrides: Record<string, unknown> = {}) {
  return {
    media_asset_id: mediaAssetId,
    preview_url: `/api/media/${mediaAssetId}/preview`,
    captured_at: new Date().toISOString(),
    relative_position: 0,
    frame_sequence: 0,
    is_primary: true,
    content_type: "image/jpeg",
    width: 3840,
    height: 2160,
    evidence_role: "identification",
    normalized_crop_box: null,
    normalized_track_box: null,
    ...overrides,
  };
}

/** One `DashboardTodaySpecies` entry, the shape `GET /api/bird-log/likely` returns. */
function likelySpeciesEntry({
  label,
  displayName,
  visitId,
  primaryMediaAssetId,
}: {
  label: string;
  displayName: string;
  visitId: string;
  primaryMediaAssetId: string | null;
}) {
  const now = new Date().toISOString();
  return {
    label,
    display_name: displayName,
    distinct_days_seen: 1,
    is_confirmed: false,
    latest_visit: {
      id: visitId,
      event_id: `${visitId}-event`,
      stream_id: STREAM_ID,
      stream_name: "Backyard Feeder",
      source_id: "source-backyard",
      source_name: "Backyard Feeder Camera",
      captured_at: now,
      activity_started_at: now,
      activity_ended_at: now,
      duration_seconds: 4,
      zone_id: null,
      zone_name: null,
      zone_type: null,
      review_status: "needs_review",
      reviewed_label: null,
      review_outcome: "needs_review",
      suggested_label: label,
      has_suggestion: true,
      evidence_frame_count: primaryMediaAssetId ? 1 : 0,
      primary_evidence: primaryMediaAssetId ? evidenceFrame(primaryMediaAssetId) : null,
    },
  };
}

/** Routes `GET /api/bird-log/likely` to a fixed, fully-shaped species list. */
async function routeLikelySpecies(page: import("@playwright/test").Page, species: unknown[]) {
  await page.route("**/api/bird-log/likely", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ species }) }),
  );
}

/**
 * Routes `GET /api/visits/{visitId}/detail` to the real backend's own
 * response for that (really-imported) Visit, with only
 * `classifier_supporting_evidence` overridden -- proving every other real
 * field on the response stays untouched and real, matching visit-
 * classifier-supporting-evidence.spec.ts's own technique.
 */
async function routeVisitDetail(
  page: import("@playwright/test").Page,
  visitId: string,
  classifierSupportingEvidence: unknown,
) {
  const response = await page.request.get(`/api/visits/${visitId}/detail`);
  const detail = await response.json();
  detail.classifier_supporting_evidence = classifierSupportingEvidence;
  await page.route(`**/api/visits/${visitId}/detail`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(detail) }),
  );
}

function likelyCard(page: import("@playwright/test").Page, displayName: string) {
  return page.locator("article.journal-label-card", { hasText: `Likely ${displayName}` });
}

function trackConsoleErrors(page: import("@playwright/test").Page): string[] {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  return errors;
}

test("Test A/B: distinct suggestion evidence renders distinct, preferred URLs over the generic Visit preview", async ({
  page,
}) => {
  const consoleErrors = trackConsoleErrors(page);
  const finch = await importRealPhoto(page);
  const finchPrimary = await importRealPhoto(page);
  const mockingbird = await importRealPhoto(page);

  await routeLikelySpecies(page, [
    likelySpeciesEntry({
      displayName: "House Finch",
      label: "house_finch",
      primaryMediaAssetId: finchPrimary.mediaAssetId,
      visitId: finch.visitId,
    }),
    likelySpeciesEntry({
      displayName: "Northern Mockingbird",
      label: "northern_mockingbird",
      primaryMediaAssetId: mockingbird.mediaAssetId,
      visitId: mockingbird.visitId,
    }),
  ]);
  // House Finch: the classifier's real input differs from the Visit's own
  // generic primary evidence -- the card must prefer the former.
  await routeVisitDetail(page, finch.visitId, {
    frame: evidenceFrame(finch.mediaAssetId, { evidence_role: "classifier_same_frame", is_primary: false }),
    input_type: "same_frame_crop",
    same_frame: true,
    species_suggestion_id: "species-suggestion-finch",
  });
  // Northern Mockingbird: no distinct classifier evidence recorded.
  await routeVisitDetail(page, mockingbird.visitId, null);

  await page.goto("/bird-log");

  const finchCard = likelyCard(page, "House Finch");
  const mockingbirdCard = likelyCard(page, "Northern Mockingbird");
  await expect(finchCard).toBeVisible();
  await expect(mockingbirdCard).toBeVisible();

  const finchSrc = await finchCard.locator("img").getAttribute("src");
  const mockingbirdSrc = await mockingbirdCard.locator("img").getAttribute("src");

  // Test A: different evidence IDs render different evidence URLs.
  expect(finchSrc).not.toBe(mockingbirdSrc);

  // Test B: the House Finch card shows the classifier's real input, not the
  // generic Visit preview it also had available.
  expect(finchSrc).toContain(finch.mediaAssetId);
  expect(finchSrc).not.toContain(finchPrimary.mediaAssetId);
  await expect(finchCard.getByText("Identification evidence")).toBeVisible();

  expect(mockingbirdSrc).toContain(mockingbird.mediaAssetId);

  expect(consoleErrors).toEqual([]);
});

test("Test C: fallback to the Visit preview is explicit and deterministic when suggestion-specific evidence is absent", async ({
  page,
}) => {
  const consoleErrors = trackConsoleErrors(page);
  const wren = await importRealPhoto(page);

  await routeLikelySpecies(page, [
    likelySpeciesEntry({
      displayName: "Carolina Wren",
      label: "carolina_wren",
      primaryMediaAssetId: wren.mediaAssetId,
      visitId: wren.visitId,
    }),
  ]);
  await routeVisitDetail(page, wren.visitId, null);

  await page.goto("/bird-log");

  const card = likelyCard(page, "Carolina Wren");
  await expect(card).toBeVisible();
  await expect(card.getByText("Visit preview")).toBeVisible();
  await expect(card.getByText("Identification evidence")).toHaveCount(0);
  const src = await card.locator("img").getAttribute("src");
  expect(src).toContain(wren.mediaAssetId);

  expect(consoleErrors).toEqual([]);
});

test("Test D: card navigation opens its own Visit, never another card's", async ({ page }) => {
  const consoleErrors = trackConsoleErrors(page);
  const finch = await importRealPhoto(page);
  const thrasher = await importRealPhoto(page);

  await routeLikelySpecies(page, [
    likelySpeciesEntry({
      displayName: "House Finch",
      label: "house_finch",
      primaryMediaAssetId: finch.mediaAssetId,
      visitId: finch.visitId,
    }),
    likelySpeciesEntry({
      displayName: "Brown Thrasher",
      label: "brown_thrasher",
      primaryMediaAssetId: thrasher.mediaAssetId,
      visitId: thrasher.visitId,
    }),
  ]);
  await routeVisitDetail(page, finch.visitId, null);
  await routeVisitDetail(page, thrasher.visitId, null);

  await page.goto("/bird-log");

  await likelyCard(page, "Brown Thrasher").getByRole("button", { name: "Confirm or correct" }).click();
  await expect(page).toHaveURL(new RegExp(`/visits/${thrasher.visitId}$`));
  await expect(page).not.toHaveURL(new RegExp(`/visits/${finch.visitId}$`));

  expect(consoleErrors).toEqual([]);
});

test("Test E: a card with no resolvable image degrades gracefully without destroying the Likely Sightings section", async ({
  page,
}) => {
  const consoleErrors = trackConsoleErrors(page);
  const empty = await importRealPhoto(page);
  const finch = await importRealPhoto(page);

  await routeLikelySpecies(page, [
    likelySpeciesEntry({
      displayName: "American Robin",
      label: "american_robin",
      primaryMediaAssetId: null,
      visitId: empty.visitId,
    }),
    likelySpeciesEntry({
      displayName: "House Finch",
      label: "house_finch",
      primaryMediaAssetId: finch.mediaAssetId,
      visitId: finch.visitId,
    }),
  ]);
  await routeVisitDetail(page, empty.visitId, null);
  await routeVisitDetail(page, finch.visitId, null);

  await page.goto("/bird-log");

  await expect(page.getByText("Likely sightings")).toBeVisible();
  const robinCard = likelyCard(page, "American Robin");
  await expect(robinCard).toBeVisible();
  await expect(robinCard.getByText("No saved thumbnail")).toBeVisible();
  await expect(robinCard.locator("img")).toHaveCount(0);
  // The rest of the section survives the one card with nothing to show.
  await expect(likelyCard(page, "House Finch")).toBeVisible();

  expect(consoleErrors).toEqual([]);
});

test("Test F: the provisional suggestion stays visibly unconfirmed", async ({ page }) => {
  const consoleErrors = trackConsoleErrors(page);
  const titmouse = await importRealPhoto(page);
  await routeLikelySpecies(page, [
    likelySpeciesEntry({
      displayName: "Tufted Titmouse",
      label: "tufted_titmouse",
      primaryMediaAssetId: titmouse.mediaAssetId,
      visitId: titmouse.visitId,
    }),
  ]);
  await routeVisitDetail(page, titmouse.visitId, null);

  await page.goto("/bird-log");

  const card = likelyCard(page, "Tufted Titmouse");
  await expect(card.getByText("Not yet confirmed")).toBeVisible();

  expect(consoleErrors).toEqual([]);
});

test("Test G: no stale card/image reuse when the underlying list order changes", async ({ page }) => {
  const consoleErrors = trackConsoleErrors(page);
  const finch = await importRealPhoto(page);
  const wren = await importRealPhoto(page);
  const dove = await importRealPhoto(page);

  const entries = {
    dove: likelySpeciesEntry({
      displayName: "Mourning Dove",
      label: "mourning_dove",
      primaryMediaAssetId: dove.mediaAssetId,
      visitId: dove.visitId,
    }),
    finch: likelySpeciesEntry({
      displayName: "House Finch",
      label: "house_finch",
      primaryMediaAssetId: finch.mediaAssetId,
      visitId: finch.visitId,
    }),
    wren: likelySpeciesEntry({
      displayName: "Carolina Wren",
      label: "carolina_wren",
      primaryMediaAssetId: wren.mediaAssetId,
      visitId: wren.visitId,
    }),
  };
  for (const visitId of [finch.visitId, wren.visitId, dove.visitId]) {
    await routeVisitDetail(page, visitId, null);
  }

  let order: (keyof typeof entries)[] = ["finch", "wren", "dove"];
  await page.route("**/api/bird-log/likely", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ species: order.map((key) => entries[key]) }),
    }),
  );

  await page.goto("/bird-log");
  const firstPass: Record<string, string | null> = {};
  for (const key of Object.keys(entries) as (keyof typeof entries)[]) {
    firstPass[key] = await likelyCard(page, entries[key].display_name).locator("img").getAttribute("src");
  }

  // Same three Visits, reversed order -- as if newer activity re-sorted the
  // overview between loads. Each species must keep its own image.
  order = ["dove", "wren", "finch"];
  await page.reload();

  for (const key of Object.keys(entries) as (keyof typeof entries)[]) {
    const src = await likelyCard(page, entries[key].display_name).locator("img").getAttribute("src");
    expect(src).toBe(firstPass[key]);
  }

  expect(consoleErrors).toEqual([]);
});

test("Test H: accessible text never presents the AI suggestion as confirmed fact", async ({ page }) => {
  const consoleErrors = trackConsoleErrors(page);
  const chickadee = await importRealPhoto(page);
  const chickadeeCrop = await importRealPhoto(page);
  const woodpecker = await importRealPhoto(page);

  await routeLikelySpecies(page, [
    likelySpeciesEntry({
      displayName: "Carolina Chickadee",
      label: "carolina_chickadee",
      primaryMediaAssetId: chickadee.mediaAssetId,
      visitId: chickadee.visitId,
    }),
    likelySpeciesEntry({
      displayName: "Red-bellied Woodpecker",
      label: "red_bellied_woodpecker",
      primaryMediaAssetId: woodpecker.mediaAssetId,
      visitId: woodpecker.visitId,
    }),
  ]);
  await routeVisitDetail(page, chickadee.visitId, {
    frame: evidenceFrame(chickadeeCrop.mediaAssetId, { evidence_role: "classifier_same_frame", is_primary: false }),
    input_type: "same_frame_crop",
    same_frame: true,
    species_suggestion_id: "species-suggestion-chickadee",
  });
  await routeVisitDetail(page, woodpecker.visitId, null);

  await page.goto("/bird-log");

  const identificationAlt = await likelyCard(page, "Carolina Chickadee").locator("img").getAttribute("alt");
  expect(identificationAlt).not.toBeNull();
  expect(identificationAlt).not.toBe("Carolina Chickadee");
  expect(identificationAlt?.toLowerCase()).toContain("provisional");
  expect(identificationAlt?.toLowerCase()).toContain("evidence for");

  const previewAlt = await likelyCard(page, "Red-bellied Woodpecker").locator("img").getAttribute("alt");
  expect(previewAlt).not.toBeNull();
  expect(previewAlt).not.toBe("Red-bellied Woodpecker");
  expect(previewAlt?.toLowerCase()).toContain("visit preview");
  expect(previewAlt?.toLowerCase()).toContain("not confirmed");

  expect(consoleErrors).toEqual([]);
});
