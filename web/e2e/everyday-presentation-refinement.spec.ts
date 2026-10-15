import { deflateSync } from "node:zlib";
import { expect, test, type Page } from "@playwright/test";

// EVERYDAY WILDLIFE EXPERIENCE & PRESENTATION REFINEMENT v1.
// Workstream A (visual correctness) regressions. Presentation only: no
// backend facts are changed; epoch-anchored instants are mocked at the
// network edge exactly as unknown-capture-time-offline-evidence.spec.ts does.

test.use({ timezoneId: "America/New_York" });

const STREAM_ID = "stream-backyard-feeder";

// A real, large-natural-size PNG (no dependency): the Today thumbnail
// overlap only reproduces when the image's natural height exceeds the row.
function solidPng(width: number, height: number): Buffer {
  const crcTable = Array.from({ length: 256 }, (_, n) => {
    let c = n;
    for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    return c >>> 0;
  });
  const crc = (buf: Buffer) => {
    let c = 0xffffffff;
    for (const byte of buf) c = crcTable[(c ^ byte) & 0xff] ^ (c >>> 8);
    return (c ^ 0xffffffff) >>> 0;
  };
  const chunk = (type: string, data: Buffer) => {
    const body = Buffer.concat([Buffer.from(type), data]);
    const length = Buffer.alloc(4);
    length.writeUInt32BE(data.length);
    const checksum = Buffer.alloc(4);
    checksum.writeUInt32BE(crc(body));
    return Buffer.concat([length, body, checksum]);
  };
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header[8] = 8;
  header[9] = 2;
  const row = Buffer.concat([Buffer.from([0]), Buffer.alloc(width * 3, 120)]);
  const raw = Buffer.concat(Array.from({ length: height }, () => row));
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

async function importLargePhoto(page: Page, name: string): Promise<string> {
  const response = await page.request.post("/api/media/import", {
    multipart: {
      file: { name, mimeType: "image/png", buffer: solidPng(1280, 720) },
      stream_id: STREAM_ID,
      subject_label: "unknown_bird",
    },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).visit.id as string;
}

test("Today's Recent activity thumbnails stay in a fixed box and never overlap neighbouring rows", async ({ page }) => {
  // Real large images, real backend; only the Today summary's recent list is
  // shaped (the shared e2e instance's own Visits are not on Today's list).
  const previews: string[] = [];
  for (const name of ["thumb-a.png", "thumb-b.png", "thumb-c.png"]) {
    const visitId = await importLargePhoto(page, name);
    const detail = await (await page.request.get(`/api/visits/${visitId}/detail`)).json();
    previews.push(detail.evidence_frames[0]);
  }
  await page.route("**/api/dashboard/summary*", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.recent_activity = previews.map((frame, index) => ({
      id: `thumb-visit-${index}`,
      event_id: `thumb-event-${index}`,
      stream_id: STREAM_ID,
      captured_at: new Date(Date.now() - index * 60_000).toISOString(),
      activity_started_at: null,
      activity_ended_at: null,
      duration_seconds: null,
      zone_id: null,
      zone_name: null,
      zone_type: null,
      review_status: "needs_review",
      reviewed_label: null,
      review_outcome: "needs_review",
      suggested_label: null,
      has_suggestion: false,
      evidence_frame_count: 1,
      primary_evidence: { ...frame, is_primary: true },
      evidence_modality: "visual",
      multimodal_partner: null,
      cross_camera_partner: null,
      capture_time_known: true,
      stream_name: "Backyard feeder",
      source_id: null,
      source_name: null,
    }));
    await route.fulfill({ response, json: body });
  });
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto("/");
    const rows = page.locator(".dashboard-recent-activity .dashboard-activity-row");
    await expect(rows).toHaveCount(3);
    await expect.poll(() =>
      page.evaluate(() =>
        Array.from(document.querySelectorAll(".dashboard-recent-activity img")).every(
          (image) => (image as HTMLImageElement).complete && (image as HTMLImageElement).naturalHeight > 0,
        ),
      ),
    ).toBe(true);
    const boxes = await rows.evaluateAll((elements) =>
      elements.map((element) => {
        const row = element.getBoundingClientRect();
        // The <img> itself, not its wrapper: the defect was the image
        // rendering at natural height beyond a correctly-sized wrapper.
        const thumb = element.querySelector("img.dashboard-visit-preview")?.getBoundingClientRect();
        return { top: row.top, bottom: row.bottom, thumbHeight: thumb?.height ?? 0, thumbBottom: thumb?.bottom ?? 0 };
      }),
    );
    for (const [index, box] of boxes.entries()) {
      expect(box.thumbHeight).toBeGreaterThan(0);
      expect(box.thumbHeight).toBeLessThanOrEqual(64);
      expect(box.thumbBottom).toBeLessThanOrEqual(box.bottom + 1);
      if (index > 0) expect(box.top).toBeGreaterThanOrEqual(boxes[index - 1].bottom - 1);
    }
  }
});

test("Alerts and Local Data never render the 1970 epoch placeholder as a date", async ({ page }) => {
  await page.route("**/api/alerts?*", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.items = body.items.map((alert: Record<string, unknown>) => ({
      ...alert,
      created_at: "1970-01-01T00:00:09+00:00",
    }));
    await route.fulfill({ response, json: body });
  });
  await page.route("**/api/settings/storage-retention/summary", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({
      response,
      json: { ...body, oldest_managed_media_at: "1970-01-01T00:00:09+00:00" },
    });
  });
  await importLargePhoto(page, "alert-seed.png");

  await page.goto("/alerts");
  await expect(page.getByRole("heading", { name: "Alerts Inbox" })).toBeVisible();
  const alertsText = await page.locator("main").innerText();
  expect(alertsText).not.toMatch(/Dec 31|1969|1970/);

  await page.goto("/local-data");
  await expect(page.getByRole("heading", { name: "Local Data" })).toBeVisible();
  await expect(page.getByText("Time not recorded").first()).toBeVisible();
  expect(await page.locator("main").innerText()).not.toMatch(/12\/31\/1969|1970/);
});


// ---------------------------------------------------------------------------
// Workstream B: Visit detail and Review Queue lead with wildlife + one decision.

// The Visit's own automatic species guess (set by the Observation Engine /
// automatic suggestion path, not by a manual import) is shaped at the network
// edge, as unknown-capture-time-offline-evidence.spec.ts does for its facts.
async function showSpeciesGuess(page: Page, visitId: string, speciesGuess: string): Promise<void> {
  await page.route(`**/api/visits/${visitId}/detail`, async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    body.visit = { ...body.visit, species_guess: speciesGuess };
    await route.fulfill({ response, json: body });
  });
}

async function createSuggestedVisit(page: Page): Promise<{ visitId: string; suggestionId: string }> {
  const created = await page.request.post("/api/sources", { data: { name: `Refinement Feeder ${Date.now()}` } });
  expect(created.ok()).toBeTruthy();
  const { source, stream } = await created.json();
  const imported = await page.request.post("/api/media/import", {
    multipart: {
      file: { name: "refinement.png", mimeType: "image/png", buffer: solidPng(640, 480) },
      stream_id: stream.id,
      subject_label: "bird",
    },
  });
  expect(imported.ok()).toBeTruthy();
  const { visit } = await imported.json();
  const suggestion = await page.request.post("/api/species-suggestions", {
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
      event_id: visit.event_id,
      rank: 1,
      source_id: source.id,
      stream_id: stream.id,
      suggested_common_name: "Northern Cardinal",
      suggested_label: "northern_cardinal",
      suggested_scientific_name: "Cardinalis cardinalis",
      visit_id: visit.id,
    },
  });
  expect(suggestion.ok()).toBeTruthy();
  return { visitId: visit.id as string, suggestionId: (await suggestion.json()).id as string };
}

test("Visit detail puts the wildlife and the one decision in the first desktop viewport, with no raw identifiers", async ({
  page,
}) => {
  const { visitId } = await createSuggestedVisit(page);
  await showSpeciesGuess(page, visitId, "northern_cardinal");
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/visits/${visitId}`);

  const decision = page.getByRole("region", { name: "Your decision" });
  await expect(decision).toBeVisible();
  await expect(decision).toContainText("Is this a Northern Cardinal?");
  // A suggestion stays visibly provisional.
  await expect(decision).toContainText("MockingBird's guess — not confirmed");
  await expect(decision.getByRole("button", { name: "Change" })).toBeVisible();
  await expect(decision.getByRole("button", { name: "Not sure" })).toBeVisible();
  const confirm = decision.getByRole("button", { name: "Confirm species" });
  const box = await confirm.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.y + box!.height).toBeLessThanOrEqual(900);
  // The species field shows the name, not the taxonomy key.
  await expect(page.getByRole("combobox", { name: /^Species correction/ })).toHaveValue("Northern Cardinal");

  // Default view carries no internal identifiers, MIME types or pack names.
  const visible = await page.locator("main").innerText();
  expect(visible).not.toMatch(
    /northern_cardinal|blue_jay|visit-[a-z]+-\d+|media-asset-|event-[a-z]+-\d+|image\/png|MiB|KiB|Candidate pack/,
  );

  // Advanced material is still available on demand, nothing was removed.
  await page.getByText("Visit details, evidence trail & export readiness").click();
  await expect(page.getByRole("button", { name: "Check export eligibility" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Exports", exact: true })).toBeVisible();
  await page.getByText(/More suggestions & help identifying/).click();
  await expect(page.getByRole("region", { name: "Identification Assistant" })).toBeVisible();
  await page.getByText("Notes, collections & tags").click();
  await expect(page.getByText("Observation notes")).toBeVisible();
});

test("Visit detail 'Not sure' saves an honest unknown and never accepts the suggestion", async ({ page }) => {
  const { visitId, suggestionId } = await createSuggestedVisit(page);
  await showSpeciesGuess(page, visitId, "northern_cardinal");
  await page.goto(`/visits/${visitId}`);
  await page.getByRole("region", { name: "Your decision" }).getByRole("button", { name: "Not sure" }).click();
  await expect
    .poll(async () => (await (await page.request.get(`/api/visits/${visitId}`)).json()).reviewed_label)
    .toBe("unknown_bird");
  const suggestions = await (await page.request.get(`/api/species-suggestions?visit_id=${visitId}`)).json();
  const suggestion = suggestions.species_suggestions.find((item: { id: string }) => item.id === suggestionId);
  // An abstention is not acceptance of the guess.
  expect(suggestion.status).not.toBe("accepted");
});

test("Visit detail 'Confirm species' still records the suggested species as reviewed truth", async ({ page }) => {
  const { visitId } = await createSuggestedVisit(page);
  await showSpeciesGuess(page, visitId, "northern_cardinal");
  await page.goto(`/visits/${visitId}`);
  await page.getByRole("button", { name: "Confirm species" }).click();
  await expect
    .poll(async () => (await (await page.request.get(`/api/visits/${visitId}`)).json()).reviewed_label)
    .toBe("northern_cardinal");
});

test("Review Queue cards describe the sighting in words, not file facts or pack names", async ({ page }) => {
  const { visitId } = await createSuggestedVisit(page);
  await page.goto("/review");
  const card = page.locator(`article.queue-card[data-target-id="${visitId}"]`);
  await expect(card).toHaveCount(1);
  await expect(card).toContainText("Likely Northern Cardinal — needs your check");
  await expect(card).toContainText("Evidence only.");
  const text = await card.innerText();
  expect(text).not.toMatch(/image\/|video\/|MiB|KiB|Candidate pack|MockingBird saw|Score \d/);
  // Technical facts remain behind the existing disclosure.
  await card.getByText("Advanced evidence").click();
  await expect(card).toContainText("Queue item:");
});

// ---------------------------------------------------------------------------
// Workstream D: calmer Today / Insights.

test("Today's empty Place shows one setup message, not one per card", async ({ page }) => {
  await page.route("**/api/place/biodiversity-summary*", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({
      response,
      json: { ...body, taxa: [], provisional_taxa: [], distinct_species_count: 0, new_taxa: [], regular_taxa: [], recently_observed_taxa: [] },
    });
  });
  await page.route("**/api/place/year-over-year*", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({ response, json: { ...body, place: { ...body.place, status: "insufficient_prior_history" } } });
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Today in Your Yard" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Biodiversity at this Place" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Compared with last year" })).toHaveCount(0);
  await expect(page.getByText("Long-term patterns will appear here")).toHaveCount(0);
  // The optional Place details are one collapsed line, not three setup prompts.
  await expect(page.getByRole("button", { name: "Set approximate location" })).toBeHidden();
  await page.getByText("About your place").click();
  await expect(page.getByRole("button", { name: "Add a feature" })).toBeVisible();
});

test("Insights with no confirmed wildlife shows one actionable empty state, not a grid of zeros", async ({ page }) => {
  await page.route("**/api/analytics/wildlife-insights*", async (route) => {
    const response = await route.fetch();
    const body = await response.json();
    await route.fulfill({
      response,
      json: {
        ...body,
        headline: {
          ...body.headline,
          active_stream_count: Math.max(1, body.headline.active_stream_count),
          active_visit_count: Math.max(1, body.headline.active_visit_count),
          reviewed_wildlife_observation_count: 0,
          unique_confirmed_label_count: 0,
          reviewed_non_bird_activity_count: 0,
          unresolved_visit_count: 3,
          busiest_stream: null,
          peak_activity_hour: null,
        },
      },
    });
  });
  await page.goto("/analytics");
  await expect(page.getByText("Activity is present, but no confirmed wildlife yet")).toBeVisible();
  await expect(page.getByText("3 Visits are waiting for review.")).toBeVisible();
  await expect(page.locator(".wildlife-insights-metrics")).toHaveCount(0);
  await expect(page.getByText("Busiest Stream")).toHaveCount(0);
  await expect(page.getByText("The same number of reviewed observations")).toHaveCount(0);
});

// ---------------------------------------------------------------------------
// Workstream E: navigation and Bird Log rediscovery.

test("primary navigation has six destinations and every existing page stays reachable", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Product navigation" });
  for (const label of ["Today", "Cameras", "Review Queue", "Bird Log", "Place", "Settings"]) {
    await expect(nav.getByRole("button", { name: label, exact: true })).toBeVisible();
  }
  // Retired top-level entries now live under their destination.
  await expect(nav.getByRole("button", { name: "Place Report", exact: true })).toHaveCount(0);

  const reachable: Array<[string, string, string]> = [
    ["Cameras", "Import Media", "Import Media"],
    ["Bird Log", "Activity Library", "Find captured activity"],
    ["Place", "Place Report", "Place Report"],
    ["Place", "Insights", "Insights"],
    ["Place", "Ecological Destinations", "Ecological Destinations"],
    ["Place", "Place Story", "Place Story"],
    ["Settings", "Local Data", "Local Data"],
  ];
  for (const [primary, secondary, heading] of reachable) {
    await nav.getByRole("button", { name: primary, exact: true }).click();
    await nav.getByRole("button", { name: secondary, exact: true }).click();
    await expect(page.getByRole("heading", { name: heading, exact: true }).first()).toBeVisible();
    // The destination stays highlighted while inside one of its pages.
    await expect(nav.getByRole("button", { name: primary, exact: true }).first()).toHaveClass(/active/);
  }
  await nav.getByRole("button", { name: "Review Queue", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();
});

function journalLabel(index: number, hoursAgo: number, knownTime = true) {
  const names = ["Northern Cardinal", "Blue Jay", "American Robin", "House Finch", "Carolina Wren", "Downy Woodpecker", "Mourning Dove"];
  const name = names[index];
  return {
    label: name.toLowerCase().replace(/ /g, "_"),
    display_name: name,
    observation_count: 3 + index,
    first_observed_at: new Date(Date.now() - 30 * 24 * 3600 * 1000).toISOString(),
    latest_observed_at: knownTime
      ? new Date(Date.now() - hoursAgo * 3600 * 1000).toISOString()
      : "1970-01-01T00:00:09+00:00",
    latest_capture_time_known: knownTime,
    stream_count: 1,
    zone_count: 1,
    recent_activity: [],
    representative: null,
    distinct_confirmed_usable_days: 3,
    is_regular: false,
  };
}

test("Bird Log can be searched by species and shows what was seen most recently", async ({ page }) => {
  await page.route("**/api/bird-log/journal?*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        order: "most_recent",
        // Deliberately not in recency order; one has only the placeholder time.
        labels: [
          journalLabel(0, 70),
          journalLabel(1, 2),
          journalLabel(2, 30),
          journalLabel(3, 5),
          journalLabel(4, 200),
          journalLabel(5, 1),
          journalLabel(6, 0, false),
        ],
        baseline_maturity: "established",
        confirmed_species_unresolved_visit_count: 0,
      }),
    }),
  );
  await page.route("**/api/bird-log/likely", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ species: [] }) }),
  );
  await page.goto("/bird-log");
  const recent = page.getByRole("region", { name: "Recently seen" });
  await expect(recent).toBeVisible();
  const names = await recent.locator(".journal-recent-item strong").allInnerTexts();
  expect(names).toEqual(["Downy Woodpecker", "Blue Jay", "House Finch", "American Robin", "Northern Cardinal"]);
  // A species with no real capture time never claims a recency slot.
  expect(names).not.toContain("Mourning Dove");

  await page.getByLabel("Find a species").fill("jay");
  await expect(page.getByText("Showing 1 of 7 species")).toBeVisible();
  await expect(page.getByRole("region", { name: "Recently seen" })).toHaveCount(0);
  await expect(page.locator("article.journal-label-card")).toHaveCount(1);
  await expect(page.locator("article.journal-label-card")).toContainText("Blue Jay");

  await page.getByLabel("Find a species").fill("zzz");
  await expect(page.getByText("No species match “zzz”")).toBeVisible();
  await page.getByRole("button", { name: "Clear search" }).click();
  await expect(page.locator("article.journal-label-card")).toHaveCount(7);
});

// ---------------------------------------------------------------------------
// Workstream C: representative thumbnail framing (presentation only).

test("representative thumbnails centre a vouched subject, keep crops whole, and never blow up small sources", async ({
  page,
}) => {
  const frame = (overrides: Record<string, unknown>) => ({
    media_asset_id: "media-framing",
    preview_url: "/api/media/none/preview",
    captured_at: new Date().toISOString(),
    relative_position: 0,
    frame_sequence: null,
    is_primary: true,
    content_type: "image/jpeg",
    width: 1920,
    height: 1080,
    evidence_role: "monitoring_frame",
    normalized_crop_box: null,
    normalized_track_box: null,
    resolution_provenance: null,
    ...overrides,
  });
  const cases = [
    { ...journalLabel(0, 1), representative: { primary_evidence: frame({ normalized_track_box: [0.62, 0.55, 0.7, 0.68] }) } },
    // A derived crop is already subject-centred: shown whole.
    { ...journalLabel(1, 2), representative: { primary_evidence: frame({ width: 500, height: 400, normalized_crop_box: [0.4, 0.4, 0.6, 0.6] }) } },
    // A small source is shown whole on a soft backdrop, never stretched.
    { ...journalLabel(2, 3), representative: { primary_evidence: frame({ width: 300, height: 200, normalized_track_box: [0.4, 0.4, 0.6, 0.6] }) } },
    // A malformed box is ignored rather than guessed at.
    { ...journalLabel(3, 4), representative: { primary_evidence: frame({ normalized_track_box: [0.9, 0.9, 0.1, 0.1] }) } },
  ].map((item, index) => ({
    ...item,
    representative: {
      visit_id: `framing-visit-${index}`,
      event_id: `framing-event-${index}`,
      stream_id: "s",
      stream_name: "Feeder",
      observed_at: new Date().toISOString(),
      display_name: item.display_name,
      ...item.representative,
    },
  }));
  await page.route("**/api/bird-log/journal?*", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ order: "most_recent", labels: cases, baseline_maturity: "established", confirmed_species_unresolved_visit_count: 0 }),
    }),
  );
  await page.route("**/api/bird-log/likely", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ species: [] }) }),
  );
  await page.route("**/api/media/none/preview", (route) =>
    route.fulfill({ status: 200, contentType: "image/png", body: solidPng(64, 48) }),
  );
  await page.goto("/bird-log");
  const images = page.locator("article.journal-label-card .journal-label-image img");
  await expect(images).toHaveCount(4);
  const transforms = await images.evaluateAll((elements) =>
    elements.map((element) => ({
      framed: element.classList.contains("journal-thumb-framed"),
      lowRes: element.classList.contains("journal-thumb-low-resolution"),
      transform: (element as HTMLElement).style.transform,
    })),
  );
  expect(transforms[0].framed).toBe(true);
  expect(transforms[0].transform).toMatch(/scale\(/);
  expect(transforms[1]).toEqual({ framed: false, lowRes: false, transform: "" });
  expect(transforms[2].lowRes).toBe(true);
  expect(transforms[2].transform).toBe("");
  expect(transforms[3]).toEqual({ framed: false, lowRes: false, transform: "" });
});
