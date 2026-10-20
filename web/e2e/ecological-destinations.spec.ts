import { expect, test, type Page } from "@playwright/test";

// Ecological Interoperability & Submission Workflows v1 (see docs/
// ecological-interoperability-submission-v1-contract.md). Mirrors
// `place-features.spec.ts`'s established pattern: this spec proves the
// presentation contract (destination availability honesty, eligibility
// preview rendering, the explicit location/media consent step, the
// confirmation-before-export flow) against synthetic, schema-shaped
// responses -- the underlying eligibility/preparation/export computation
// itself is already covered thoroughly by tests/test_ecological_
// interoperability_repository.py and tests/test_ecological_
// interoperability_api.py.

async function completeSetup(page: Page) {
  await page.route("**/api/setup/state", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ completed: true, current_step: "done", updated_at: new Date().toISOString() }),
    }),
  );
}

const NOW = new Date().toISOString();

const DESTINATIONS = [
  { key: "inaturalist", display_name: "iNaturalist", offered: true, offered_reason: null },
  {
    key: "ebird", display_name: "eBird", offered: false,
    offered_reason:
      "eBird's own Rules and Best Practices exclude nest/feeder/trail-camera observations "
      + '("eBird is designed to collect in-person observations of living wild birds").',
  },
];

function previewItem(overrides: Record<string, unknown> = {}) {
  return {
    visit_id: "visit-bird-feeder-001",
    classification: "confirmed_taxon",
    taxon_label: "northern_cardinal",
    taxon_display_name: "Northern Cardinal",
    captured_at: NOW,
    status: "eligible",
    needs_input_reasons: [],
    excluded_reasons: [],
    ...overrides,
  };
}

function submissionRecord(overrides: Record<string, unknown> = {}) {
  return {
    id: "ecological-submission-001",
    visit_id: "visit-bird-feeder-001",
    destination: "inaturalist",
    status: "prepared",
    is_stale: false,
    content_fingerprint: "abc123",
    taxon_label: "northern_cardinal",
    taxon_scientific_name: null,
    destination_taxon_id: "9083",
    destination_taxon_match_status: "matched",
    taxonomy_mapping_version: "inaturalist-v1-taxa-api",
    location_choice: "none",
    location_latitude: null,
    location_longitude: null,
    location_place_name: null,
    media_policy: "none",
    media_selection_asset_id: null,
    needs_input_reasons: [],
    excluded_reasons: [],
    prepared_at: NOW,
    prepared_by_user_id: null,
    exported_at: null,
    external_id: null,
    external_url: null,
    result_recorded_at: null,
    result_notes: null,
    updated_at: NOW,
    ...overrides,
  };
}

async function mockDestinations(page: Page) {
  await page.route("**/api/ecological/destinations", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(DESTINATIONS) }),
  );
}

test("eBird is shown as not offered with its cited reason, never silently hidden", async ({ page }) => {
  await completeSetup(page);
  await mockDestinations(page);
  await page.goto("/ecological-destinations");

  // The destination button is correctly disabled (it can never be selected),
  // so the reason must be visible WITHOUT clicking it -- a hover-only title
  // tooltip on an unclickable button is not an adequate answer to "why
  // can't I use eBird" (Phase 23).
  const ebirdButton = page.getByRole("button", { name: /eBird \(not offered\)/i });
  await expect(ebirdButton).toBeVisible();
  await expect(ebirdButton).toBeDisabled();
  await expect(page.getByText(/eBird is not offered/i)).toBeVisible();
  await expect(page.getByText(/feeder cameras|in-person observations/i)).toBeVisible();
});

test("previewing eligibility shows honest per-record status, not just a bare count", async ({ page }) => {
  await completeSetup(page);
  await mockDestinations(page);
  await page.route("**/api/ecological/eligibility-preview", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        destination: DESTINATIONS[0],
        items: [
          previewItem(),
          previewItem({
            visit_id: "visit-squirrel-ground-001", taxon_label: "squirrel", taxon_display_name: "Squirrel",
            status: "needs_input", needs_input_reasons: ["taxonomy_mapping_ambiguous"],
          }),
        ],
        eligible_count: 1, needs_input_count: 1, excluded_count: 0,
      }),
    }),
  );
  await page.route("**/api/ecological/submissions?*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );

  await page.goto("/ecological-destinations");
  await page.getByRole("button", { name: "Preview eligibility" }).click();

  // Scoped to the preview table: the Species filter's own <option> list
  // legitimately repeats taxon names.
  const previewTable = page.getByRole("table", { name: "Ecological eligibility preview" });
  await expect(previewTable.getByText("Northern Cardinal")).toBeVisible();
  await expect(previewTable.getByText("Squirrel")).toBeVisible();
  await expect(page.getByText(/taxonomy mapping ambiguous/i)).toBeVisible();
});

test("preparing and exporting requires an explicit confirmation naming what will happen", async ({ page }) => {
  await completeSetup(page);
  await mockDestinations(page);
  await page.route("**/api/ecological/eligibility-preview", (route) =>
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({
        destination: DESTINATIONS[0], items: [previewItem()],
        eligible_count: 1, needs_input_count: 0, excluded_count: 0,
      }),
    }),
  );
  let prepareCalled = false;
  await page.route("**/api/ecological/submissions", (route) => {
    if (route.request().method() === "POST") {
      prepareCalled = true;
      return route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify([submissionRecord()]) });
    }
    return route.continue();
  });
  // Empty until prepare has actually happened -- realistic sequencing, and
  // disambiguates the "Northern Cardinal" text from the preview list above.
  await page.route("**/api/ecological/submissions?*", (route) =>
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify(prepareCalled ? [submissionRecord()] : []),
    }),
  );
  let exportCalled = false;
  await page.route("**/api/ecological/submissions/export", (route) => {
    exportCalled = true;
    return route.fulfill({
      status: 201, contentType: "application/json",
      body: JSON.stringify({
        destination: "inaturalist", output_directory: "/data/ecological_exports/export-1",
        files: [{ name: "inaturalist_import.csv", relative_path: "inaturalist_import.csv", content_type: "text/csv", size_bytes: 120 }],
        included_count: 1, skipped: [],
      }),
    });
  });

  await page.goto("/ecological-destinations");
  await page.getByRole("button", { name: "Preview eligibility" }).click();
  const previewList = page.getByRole("table", { name: "Ecological eligibility preview" });
  await expect(previewList.getByText("Northern Cardinal")).toBeVisible();

  await page.getByRole("button", { name: /Prepare 1 selected/ }).click();
  await expect.poll(() => prepareCalled).toBe(true);
  await expect(page.getByText(/Prepared 1 record/)).toBeVisible();

  // Selecting the now-prepared record and exporting must show a real
  // confirmation dialog naming the destination/location/media before
  // anything is written (Phase 24) -- and declining it must not export.
  const preparedList = page.getByRole("table", { name: "Prepared ecological submissions" });
  await expect(preparedList.getByText("Northern Cardinal")).toBeVisible();
  const checkbox = preparedList.locator('[role="row"]').filter({ hasText: "Northern Cardinal" }).locator('input[type="checkbox"]');
  await checkbox.check();

  page.once("dialog", (dialog) => {
    expect(dialog.message()).toContain("iNaturalist");
    void dialog.dismiss();
  });
  await page.getByRole("button", { name: /Export 1 selected/ }).click();
  await expect.poll(() => exportCalled).toBe(false);

  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: /Export 1 selected/ }).click();
  await expect.poll(() => exportCalled).toBe(true);
  await expect(page.getByText(/1 record\(s\) written/)).toBeVisible();
});

test("preparing with an exact location choice but no coordinate typed in is refused, not silently zero", async ({ page }) => {
  await completeSetup(page);
  await mockDestinations(page);
  await page.route("**/api/ecological/eligibility-preview", (route) =>
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({
        destination: DESTINATIONS[0], items: [previewItem()],
        eligible_count: 1, needs_input_count: 0, excluded_count: 0,
      }),
    }),
  );
  await page.route("**/api/ecological/submissions?*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
  let prepareCalled = false;
  await page.route("**/api/ecological/submissions", (route) => {
    if (route.request().method() === "POST") {
      prepareCalled = true;
    }
    return route.continue();
  });

  await page.goto("/ecological-destinations");
  await page.getByRole("button", { name: "Preview eligibility" }).click();
  await expect(
    page.getByRole("table", { name: "Ecological eligibility preview" }).getByText("Northern Cardinal"),
  ).toBeVisible();
  await page.getByLabel("Location").selectOption("exact");

  await page.getByRole("button", { name: /Prepare 1 selected/ }).click();
  await expect(page.getByText(/enter a real latitude and longitude/i)).toBeVisible();
  expect(prepareCalled).toBe(false);
});

test("choosing an approximate location shows the obscured-is-display-only warning", async ({ page }) => {
  await completeSetup(page);
  await mockDestinations(page);
  await page.route("**/api/ecological/submissions?*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );

  await page.goto("/ecological-destinations");
  await page.getByLabel("Location").selectOption("coarse");
  await expect(page.getByText(/not a transmission setting/i)).toBeVisible();
  await expect(page.getByText(/still receives and stores the exact coordinate/i)).toBeVisible();
});
