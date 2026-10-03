import { expect, test, type Page } from "@playwright/test";

// Research Export & Ecological Workflow Completion v1 (see docs/research-
// export-ecological-workflow-completion-v1-contract.md). Presentation
// contract against schema-shaped synthetic responses -- the export/bundle
// computation itself is covered by tests/test_research_media_bundle.py.

const NOW = new Date().toISOString();
const DESTINATIONS = [
  { key: "inaturalist", display_name: "iNaturalist", offered: true, offered_reason: null },
];

async function prepare(page: Page) {
  await page.route("**/api/setup/state", (route) =>
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({ completed: true, current_step: "done", updated_at: NOW }),
    }),
  );
  await page.route("**/api/ecological/destinations", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(DESTINATIONS) }),
  );
  await page.route("**/api/ecological/submissions?*", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );
}

function item(overrides: Record<string, unknown> = {}) {
  return {
    visit_id: "visit-1", classification: "confirmed_taxon", taxon_label: "northern_cardinal",
    taxon_display_name: "Northern Cardinal", captured_at: NOW, status: "eligible",
    needs_input_reasons: [], excluded_reasons: [], ...overrides,
  };
}

function previewBody(items: unknown[]) {
  return JSON.stringify({
    destination: DESTINATIONS[0], items,
    eligible_count: items.length, needs_input_count: 0, excluded_count: 0,
  });
}

test("a Visit deep link scopes the preview to that Visit and preselects it when eligible", async ({ page }) => {
  await prepare(page);
  let requestFilters: Record<string, unknown> | null = null;
  await page.route("**/api/ecological/eligibility-preview", (route) => {
    requestFilters = route.request().postDataJSON().filters;
    return route.fulfill({ status: 200, contentType: "application/json", body: previewBody([item()]) });
  });

  await page.goto("/ecological-destinations?visit=visit-1");
  await expect(page.getByText("Showing one Visit")).toBeVisible();
  await expect(page.getByText("This Visit is ready to prepare")).toBeVisible();
  expect(requestFilters).toMatchObject({ visit_ids: ["visit-1"], acquisition_scope: "both" });
  await expect(page.getByRole("button", { name: /Prepare 1 selected/ })).toBeEnabled();
});

test("a deep-linked Visit that is not eligible is explained, never silently exported", async ({ page }) => {
  await prepare(page);
  await page.route("**/api/ecological/eligibility-preview", (route) =>
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify({
        destination: DESTINATIONS[0],
        items: [item({
          classification: "provisional_suggestion", taxon_label: null, taxon_display_name: null,
          status: "excluded", excluded_reasons: ["not_reviewed"],
        })],
        eligible_count: 0, needs_input_count: 0, excluded_count: 1,
      }),
    }),
  );

  await page.goto("/ecological-destinations?visit=visit-1");
  await expect(page.getByText("This Visit cannot be exported")).toBeVisible();
  await expect(page.getByText(/not reviewed/i).first()).toBeVisible();
  await expect(page.getByText(/never exported as confirmed truth/i)).toBeVisible();
  await expect(page.getByRole("button", { name: /Prepare 0 selected/ })).toBeDisabled();
});

test("filters map to server filters and round-trip through the URL", async ({ page }) => {
  await prepare(page);
  await page.route("**/api/streams", (route) =>
    route.fulfill({
      status: 200, contentType: "application/json",
      body: JSON.stringify([{ id: "stream-a", source_id: "src", name: "Feeder", description: "", is_live: true }]),
    }),
  );
  let requestFilters: Record<string, unknown> | null = null;
  await page.route("**/api/ecological/eligibility-preview", (route) => {
    requestFilters = route.request().postDataJSON().filters;
    return route.fulfill({ status: 200, contentType: "application/json", body: previewBody([]) });
  });

  await page.goto("/ecological-destinations?stream=stream-a&scope=offline&from=2026-08-01");
  await expect(page.getByLabel("Camera / Stream")).toHaveValue("stream-a");
  await expect(page.getByLabel("Captured")).toHaveValue("offline");
  await expect(page.getByLabel("From")).toHaveValue("2026-08-01");

  await page.getByLabel("Captured").selectOption("live");
  await expect(page).toHaveURL(/scope=live/);
  await page.getByRole("button", { name: "Preview eligibility" }).click();
  await expect(page.getByText("Nothing in range")).toBeVisible();
  expect(requestFilters).toMatchObject({ stream_ids: ["stream-a"], acquisition_scope: "live" });
  expect((requestFilters as unknown as { start_at: string }).start_at).toContain("2026-08-01");

  // Defaults preserve current behavior: no filter keys in the URL.
  await page.getByLabel("Camera / Stream").selectOption("");
  await page.getByLabel("Captured").selectOption("both");
  await page.getByLabel("From").fill("");
  await expect(page).not.toHaveURL(/[?]/);
});

test("research bundle preview and write report included photos, omissions and warnings honestly", async ({ page }) => {
  await prepare(page);
  const bodies: Record<string, unknown>[] = [];
  await page.route("**/api/research/export", (route) => {
    const body = route.request().postDataJSON();
    bodies.push(body);
    return route.fulfill({
      status: 201, contentType: "application/json",
      body: JSON.stringify({
        export_id: "research-export-1",
        output_directory: body.dry_run ? null : "/data/research_exports/research-export-1",
        files: [], observation_count: 2, media_count: 3, excluded_count: 1,
        excluded_reasons: { not_reviewed: 1 },
        media_bundle: {
          requested: 3, bundled: 2, omitted: 1, omitted_reasons: { omitted_missing: 1 },
          total_bytes: 2048, warnings: ["media-3: not bundled (omitted_missing)"],
        },
        manifest: {}, dry_run: body.dry_run,
      }),
    });
  });

  await page.goto("/ecological-destinations");
  await page.getByLabel("Include evidence photos in the bundle").check();
  await expect(page.getByText(/Privacy Zones do not redact pixels/).first()).toBeVisible();

  await page.getByRole("button", { name: "Preview bundle" }).click();
  await expect(page.getByText(/Preview: 2 observation\(s\), 1 excluded as not research-eligible/)).toBeVisible();
  await expect(page.getByText(/Photos: 2 of 3 would be included/)).toBeVisible();
  await expect(page.getByText("media-3: not bundled (omitted_missing)")).toBeVisible();
  expect(bodies[0]).toMatchObject({ include_media: true, dry_run: true });

  page.once("dialog", (dialog) => {
    expect(dialog.message()).toContain("copied into the bundle");
    expect(dialog.message()).toContain("never uploads");
    void dialog.accept();
  });
  await page.getByRole("button", { name: "Write bundle" }).click();
  await expect(page.getByText(/ready to download/)).toBeVisible();
  expect(bodies[1]).toMatchObject({ include_media: true, dry_run: false });
  // Ordinary UI never shows where the Host stored the bundle.
  await expect(page.locator("body")).not.toContainText("/data/research_exports");
  await expect(page.locator("body")).not.toContainText("research_exports");

  // The completed export is retrieved through the product, by id only.
  let downloadUrl = "";
  await page.route("**/api/research/exports/*/download", (route) => {
    downloadUrl = route.request().url();
    return route.fulfill({
      status: 200, contentType: "application/zip",
      headers: { "content-disposition": 'attachment; filename="research-export-1.zip"' },
      body: Buffer.from("PK\u0005\u0006" + "\0".repeat(18), "binary"),
    });
  });
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download export" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("research-export-1.zip");
  expect(new URL(downloadUrl).pathname).toBe("/api/research/exports/research-export-1/download");
  expect(new URL(downloadUrl).search).toBe("");
  await expect(page.locator("body")).not.toContainText("/data/research_exports");
});

test("an empty bundle explains why instead of a silent zero", async ({ page }) => {
  await prepare(page);
  await page.route("**/api/research/export", (route) =>
    route.fulfill({
      status: 201, contentType: "application/json",
      body: JSON.stringify({
        export_id: "e", output_directory: null, files: [], observation_count: 0, media_count: 0,
        excluded_count: 4, excluded_reasons: { not_reviewed: 4 }, media_bundle: null, manifest: {}, dry_run: true,
      }),
    }),
  );
  await page.goto("/ecological-destinations");
  await page.getByRole("button", { name: "Preview bundle" }).click();
  await expect(page.getByText("Nothing eligible to bundle")).toBeVisible();
  await expect(page.getByText(/4 observation\(s\) matched your filters but are not research-eligible/)).toBeVisible();
});

test("the media-limit refusal is shown as a plain error", async ({ page }) => {
  await prepare(page);
  await page.route("**/api/research/export", (route) =>
    route.fulfill({
      status: 400, contentType: "application/json",
      body: JSON.stringify({ detail: "research_export_media_limit_exceeded: narrow the export filters." }),
    }),
  );
  await page.goto("/ecological-destinations");
  await page.getByRole("button", { name: "Preview bundle" }).click();
  await expect(page.locator(".error-panel")).toBeVisible();
});
