import { devices, expect, test, type Locator, type Page } from "@playwright/test";
import { join } from "node:path";

// Mobile Viewport Audit v1 (draft). A lightweight, cross-cutting layout
// sweep -- not a feature/contract test like every other file in this suite
// -- that visits the product's key surfaces at a realistic phone viewport
// and proves two cheap, high-value facts about each: (1) nothing forces the
// page wider than the viewport (a `document.documentElement.scrollWidth`
// horizontal-overflow check -- the same check today-report.spec.ts and
// place-story.spec.ts already each run once, for their own single page,
// generalized here across the whole product), and (2) a full-page
// screenshot exists for a human to actually look at. One `test()` per
// surface so a failure names exactly which page regressed.
//
// Device emulation: `devices["Pixel 7"]` (412x839 viewport, isMobile/
// hasTouch true, 2.625x device scale factor) via a file-level `test.use()`.
// This is the first file in this suite to call `test.use()`/
// `test.describe()`/`devices` -- none of the ~18 existing spec files need
// per-file option overrides -- but it is Playwright's own documented
// pattern (see https://playwright.dev/docs/emulation#devices) and composes
// safely with this suite's shared playwright.config.ts: `test.use()`
// shallow-merges onto the config's own `use` block (baseURL, storageState,
// trace, headless, ...), so only the keys this preset actually sets
// (viewport/userAgent/deviceScaleFactor/isMobile/hasTouch/screen) are
// touched here -- there is no need to re-spread the base config's `use`
// block. The shared authenticated `storageState` from global-setup.ts still
// applies to every test below except the Sign-in test, which explicitly
// opts back out. Picked an Android/Chromium preset over an iPhone one on
// purpose: this repo's playwright.config.ts declares no `projects` array,
// so every test here actually runs on Chromium regardless of which device
// is emulated -- `devices["Pixel 7"]`'s own `defaultBrowserType: "chromium"`
// genuinely matches that, where an iPhone preset would nominally claim
// WebKit while still silently executing on Chromium.
test.use({ ...devices["Pixel 7"] });

const STREAM_ID = "stream-backyard-feeder";

// A tiny, genuinely valid, decodable JPEG -- the same fixture
// visit-evidence-gallery.spec.ts and visit-evidence-review-loop.spec.ts
// already use. `/api/media/import` writes these bytes to a real managed
// media file, and `/api/media/{id}/preview` really cv2-decodes them.
const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

// Session-scratch output directory for this draft's screenshots (per the
// task that produced this file -- not a repo convention). Playwright
// creates missing parent directories automatically when writing a
// screenshot. Worth repointing at something durable (e.g. `testInfo.
// outputDir`, which already resolves under this suite's own per-run
// `runtimeRoot/artifacts` -- see playwright.config.ts's `outputDir`) once
// this file graduates from a one-off draft.
const SCREENSHOT_DIR =
  "/tmp/claude-1000/-home-zkelder-projects-mockingbird-active/4f16a706-388f-4bca-9944-5ba6107e202e/scratchpad/mobile-audit-screenshots";

function screenshotPath(name: string): string {
  return join(SCREENSHOT_DIR, `${name}.png`);
}

async function assertNoHorizontalOverflow(page: Page, surfaceName: string): Promise<void> {
  const { scrollWidth, clientWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
  }));
  expect(
    scrollWidth,
    `${surfaceName}: horizontal overflow at phone width -- document.documentElement.scrollWidth ` +
      `(${scrollWidth}px) exceeds clientWidth (${clientWidth}px) + 1px subpixel-rounding tolerance`,
  ).toBeLessThanOrEqual(clientWidth + 1);
}

async function assertMeetsTapTargetMinimum(
  locator: Locator,
  label: string,
  minSizePx = 40,
): Promise<void> {
  const box = await locator.boundingBox();
  expect(box, `${label}: expected a visible, measurable tap target`).not.toBeNull();
  if (!box) return;
  expect(
    box.width,
    `${label}: tap target width ${box.width}px is below the ${minSizePx}px minimum`,
  ).toBeGreaterThanOrEqual(minSizePx);
  expect(
    box.height,
    `${label}: tap target height ${box.height}px is below the ${minSizePx}px minimum`,
  ).toBeGreaterThanOrEqual(minSizePx);
}

// Imports a real photo onto the existing demo Stream, then drives the real
// correction form on Visit Detail to confirm it as `speciesLabel` -- the
// same two-step real-UI pattern visit-evidence-review-loop.spec.ts and
// visit-evidence-gallery.spec.ts already use for their own seeding. A raw
// POST to /api/review-labels would never earn `review_origin: "human"`
// (Review Decision Provenance / Truth Boundary v1 stamps that only inside
// apiClient.createReviewLabel, the frontend's own interactive submit
// handler -- see src/api/client.ts) -- driving the actual form is what
// makes this Visit's reviewed truth real rather than simulated, so Today,
// Bird Log, and Visit Detail all treat it exactly like a Visit a real
// reviewer confirmed.
async function seedConfirmedBirdVisit(
  page: Page,
  speciesLabel: string,
): Promise<{ visitId: string; mediaAssetId: string }> {
  const importResponse = await page.request.post("/api/media/import", {
    multipart: {
      file: {
        name: "mobile-viewport-audit.jpg",
        mimeType: "image/jpeg",
        buffer: Buffer.from(TINY_JPEG_BASE64, "base64"),
      },
      stream_id: STREAM_ID,
      subject_label: "unknown_bird",
    },
  });
  expect(
    importResponse.ok(),
    `seeding: POST /api/media/import failed (${importResponse.status()})`,
  ).toBeTruthy();
  const imported = await importResponse.json();
  expect(imported.visit).not.toBeNull();
  const visitId = imported.visit.id as string;
  const mediaAssetId = imported.media_asset.id as string;

  await page.goto(`/visits/${visitId}`);
  const form = page.locator("form.correction-form");
  await form.locator("input").first().fill(speciesLabel);
  await form
    .locator("textarea")
    .fill("e2e: seeded by mobile-viewport-audit.spec.ts for a phone-width layout screenshot.");
  await form.getByRole("button", { name: /Save correction|Resolve species/ }).click();

  // Poll the real record rather than the rendered heading text -- avoids
  // coupling this seeding helper to displayTaxonomyLabel()'s exact
  // formatting, and mirrors the same confirmation convention reviewed-
  // product-loop.spec.ts already uses after its own correction.
  await expect
    .poll(async () => {
      const visitResponse = await page.request.get(`/api/visits/${visitId}`);
      const visit = await visitResponse.json();
      return visit.review_status as string;
    })
    .toBe("reviewed");

  return { visitId, mediaAssetId };
}

// Same real import as seedConfirmedBirdVisit, left needs_review -- for
// Review Queue's own layout, which does not need a confirmed Visit.
async function seedUnreviewedVisit(page: Page): Promise<{ visitId: string }> {
  const importResponse = await page.request.post("/api/media/import", {
    multipart: {
      file: {
        name: "mobile-viewport-audit-unreviewed.jpg",
        mimeType: "image/jpeg",
        buffer: Buffer.from(TINY_JPEG_BASE64, "base64"),
      },
      stream_id: STREAM_ID,
      subject_label: "unknown_bird",
    },
  });
  expect(
    importResponse.ok(),
    `seeding: POST /api/media/import failed (${importResponse.status()})`,
  ).toBeTruthy();
  const imported = await importResponse.json();
  expect(imported.visit).not.toBeNull();
  return { visitId: imported.visit.id as string };
}

test("Today / Dashboard stays free of horizontal overflow at phone width", async ({ page }) => {
  await seedConfirmedBirdVisit(page, "northern_cardinal");

  await page.goto("/");
  await expect(page.locator("section.today-report")).toBeVisible();

  await assertNoHorizontalOverflow(page, "Today / Dashboard (/)");
  await page.screenshot({ path: screenshotPath("today"), fullPage: true });

  // Cheap tap-target sanity check on the always-present phone-width bottom
  // nav (see App.tsx's `mobile-bottom-nav`, shown below the 760px mobile
  // breakpoint) -- 2 of its buttons, not an exhaustive audit of every item.
  const primaryNav = page.getByRole("navigation", { name: "Primary" });
  await assertMeetsTapTargetMinimum(
    primaryNav.getByRole("button", { name: "Today", exact: true }),
    "Bottom nav: Today",
  );
  await assertMeetsTapTargetMinimum(
    primaryNav.getByRole("button", { name: "Cameras", exact: true }),
    "Bottom nav: Cameras",
  );
});

test("Bird Log stays free of horizontal overflow at phone width", async ({ page }) => {
  await seedConfirmedBirdVisit(page, "northern_cardinal");

  await page.goto("/bird-log");
  await expect(page.getByRole("heading", { name: "Bird Log" })).toBeVisible();
  // At least one reviewed species card exists (this run's own seeded
  // Visit, and/or the pre-existing demo data). `article.journal-label-card`
  // is the current species-grid card (styles.css also still carries an
  // unrelated, unreferenced-by-any-.tsx `.bird-log-entry` rule -- dead CSS
  // from an earlier layout, confirmed by a repo-wide grep; left alone as
  // out of this milestone's bounded scope, recorded in the report).
  await expect(page.locator("article.journal-label-card").first()).toBeVisible({ timeout: 20_000 });

  await assertNoHorizontalOverflow(page, "Bird Log (/bird-log)");
  await page.screenshot({ path: screenshotPath("bird-log"), fullPage: true });
});

test("Place Story stays free of horizontal overflow at phone width", async ({ page }) => {
  // Deliberately not mocked, unlike place-story.spec.ts's own scenarios --
  // this is a real render of whatever this run's real backend state
  // actually is (the pre-existing demo Visit data may or may not be enough
  // to leave "early experience" state; either is a legitimate state to
  // audit for layout purposes).
  await page.goto("/place-story");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Place Story");

  await assertNoHorizontalOverflow(page, "Place Story (/place-story)");
  await page.screenshot({ path: screenshotPath("place-story"), fullPage: true });
});

test("Cameras / Streams list stays free of horizontal overflow at phone width", async ({ page }) => {
  await page.goto("/cameras");
  await expect(page.getByRole("heading", { name: "Cameras / Streams" })).toBeVisible();
  // The pre-existing demo Stream's own card heading is real but sits
  // inside a collapsed-by-default disclosure on this page (confirmed via
  // Playwright's own "hidden" accessibility-tree report, not a timing
  // flake), so this intentionally does not assert on it -- StreamsPage's
  // own content-disclosure shape is that page's concern, not this layout
  // audit's. The page heading above plus the overflow/screenshot below
  // are this test's actual point.

  await assertNoHorizontalOverflow(page, "Cameras / Streams list (/cameras)");
  await page.screenshot({ path: screenshotPath("cameras"), fullPage: true });
});

test("Stream detail stays free of horizontal overflow at phone width", async ({ page }) => {
  await page.goto(`/streams/${STREAM_ID}`);
  await expect(page.getByRole("heading", { name: "Backyard feeder stream" })).toBeVisible();

  await assertNoHorizontalOverflow(page, `Stream detail (/streams/${STREAM_ID})`);
  await page.screenshot({ path: screenshotPath("stream-detail"), fullPage: true });
});

test("Visit detail stays free of horizontal overflow at phone width", async ({ page }) => {
  const { visitId } = await seedConfirmedBirdVisit(page, "northern_cardinal");

  await page.goto(`/visits/${visitId}`);
  await expect(page.locator("section.visit-evidence-panel")).toBeVisible();

  await assertNoHorizontalOverflow(page, `Visit detail (/visits/${visitId})`);
  await page.screenshot({ path: screenshotPath("visit-detail"), fullPage: true });
});

test("Review Queue stays free of horizontal overflow at phone width", async ({ page }) => {
  // Neither the pre-existing demo needs_review Visit (visit-bird-feeder-001,
  // seeded by demo_data.py) nor a freshly real-imported one (via the same
  // /api/media/import path production Add Camera/import flows use) appears
  // under Review Queue's default "animals" tab in this run -- confirmed
  // both ways, and independently reproduced by e2e/reviewed-product-loop.
  // spec.ts (an existing, unmodified spec) failing identically when run
  // alone. This points at a genuine pre-existing gap in how `product_
  // category` gets set for a needs_review item (`matchesProductReviewTab`'s
  // default "animals" tab requires `item.product_category === "animal"`),
  // unrelated to this milestone's changes -- recorded in
  // docs/mobile-remote-experience-v1-report.md as found-but-out-of-scope,
  // not fixed here. Auditing whatever this page's real, honest state
  // actually is (populated or not) is this test's actual point, mirroring
  // the Place Story test's identical "either state is legitimate" stance.
  await seedUnreviewedVisit(page);

  await page.goto("/review");
  await expect(page.getByRole("heading", { name: "Review Queue" })).toBeVisible();

  await assertNoHorizontalOverflow(page, "Review Queue (/review)");
  await page.screenshot({ path: screenshotPath("review-queue"), fullPage: true });

  const confirmButton = page
    .locator("article.queue-card")
    .first()
    .getByRole("button", { name: /Save correction|Resolve species/ });
  if (await confirmButton.count()) {
    await assertMeetsTapTargetMinimum(confirmButton, "Review Queue: confirm/save-correction button");
  }
});

test("Place Activity Report stays free of horizontal overflow at phone width", async ({ page }) => {
  // Deliberately not mocked -- see place-activity-report.spec.ts's own
  // real-backend convention for this exact page.
  await page.goto("/place-report");
  await expect(page.getByRole("heading", { name: "Place Report" })).toBeVisible();

  await assertNoHorizontalOverflow(page, "Place Activity Report (/place-report)");
  await page.screenshot({ path: screenshotPath("place-report"), fullPage: true });
});

test("Local Data / Settings stays free of horizontal overflow at phone width", async ({ page }) => {
  await page.goto("/local-data");
  await expect(page.getByRole("heading", { name: "Local Data" })).toBeVisible();

  await assertNoHorizontalOverflow(page, "Local Data / Settings (/local-data)");
  await page.screenshot({ path: screenshotPath("local-data"), fullPage: true });
});

// Sign-in needs a genuinely unauthenticated context -- every test above
// relies on the shared authenticated `storageState` from global-setup.ts
// (see playwright.config.ts), so this is the one test in this file that
// must opt back out of it. Nesting it in its own `test.describe` merges
// this override onto the file-level `test.use({ ...devices["Pixel 7"] })`
// above rather than replacing it, so the phone emulation still applies.
test.describe("Sign-in (unauthenticated)", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("Sign-in stays free of horizontal overflow at phone width", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();

    await assertNoHorizontalOverflow(page, "Sign-in");
    await page.screenshot({ path: screenshotPath("sign-in"), fullPage: true });
  });
});

// Phase 25's own explicit instruction: test at least ~360px, ~390px, and a
// tablet/narrow-desktop width, not just one phone size -- `devices["Pixel
// 7"]` above (412px) is a real, common Android width, but the narrowest
// mainstream Android phones (360px) are where an overlooked fixed-width
// element is most likely to actually overflow. Each width below re-checks
// the two highest-content-density, highest-risk surfaces (Today, Visit
// detail) plus the new nav drawer itself, rather than the full 10-surface
// sweep again -- proportionate additional coverage, not a 3x-longer suite
// for marginal extra evidence.
//
// Whole-Product UI / Accessibility / Performance Closure v1: added 1024px
// (laptop) and 1440px (desktop) -- until now this matrix only ever
// exercised mobile/tablet widths, so the two representative desktop widths
// the milestone brief itself names had no automated regression coverage at
// all (only manually verified, ad hoc, each prior pass). Both reuse the
// identical assertions below; `isMobileNavWidth` already branches to the
// always-visible desktop sidebar for anything >= 760px, so no separate
// desktop-specific test shape is needed.
for (const { label, width, height } of [
  { label: "360px (narrow Android)", width: 360, height: 740 },
  { label: "390px (iPhone-class)", width: 390, height: 844 },
  { label: "768px (tablet/narrow desktop)", width: 768, height: 1024 },
  { label: "1024px (laptop)", width: 1024, height: 800 },
  { label: "1440px (desktop)", width: 1440, height: 900 },
]) {
  test.describe(`Viewport matrix -- ${label}`, () => {
    test.use({ viewport: { width, height } });

    test(`Today stays free of horizontal overflow at ${label}`, async ({ page }) => {
      await seedConfirmedBirdVisit(page, "northern_cardinal");
      await page.goto("/");
      await expect(page.locator("section.today-report")).toBeVisible();
      await assertNoHorizontalOverflow(page, `Today (${label})`);
    });

    test(`Visit detail stays free of horizontal overflow at ${label}`, async ({ page }) => {
      const { visitId } = await seedConfirmedBirdVisit(page, "northern_cardinal");
      await page.goto(`/visits/${visitId}`);
      await expect(page.locator("section.visit-evidence-panel")).toBeVisible();
      await assertNoHorizontalOverflow(page, `Visit detail (${label})`);
    });

    test(`the nav drawer opens, navigates, and closes cleanly at ${label}`, async ({ page }) => {
      await page.goto("/");
      await expect(page.locator("section.today-report")).toBeVisible();

      // Below the 760px mobile-nav breakpoint (see styles.css), the
      // hamburger/drawer/bottom-nav apply; at 768px this exercises the
      // ordinary always-visible desktop-width sidebar instead -- both are
      // legitimate, intentionally different behavior at that width, so
      // this test adapts rather than asserting one fixed shape.
      const isMobileNavWidth = width < 760;
      if (isMobileNavWidth) {
        const toggle = page.getByRole("button", { name: "Open navigation" });
        await expect(toggle).toBeVisible();
        await assertMeetsTapTargetMinimum(toggle, `Nav toggle (${label})`);
        await toggle.click();
        const drawer = page.locator("#primary-navigation");
        await expect(drawer).toHaveClass(/sidebar-open/);
        await drawer.getByRole("button", { name: "Bird Log", exact: true }).click();
        await expect(page).toHaveURL(/\/bird-log$/);
        // Navigating closes the drawer (see App.tsx's page-keyed useEffect).
        await expect(drawer).not.toHaveClass(/sidebar-open/);
      } else {
        await expect(page.locator("aside.sidebar")).toBeVisible();
        await page.locator("aside.sidebar").getByRole("button", { name: "Bird Log", exact: true }).click();
        await expect(page).toHaveURL(/\/bird-log$/);
      }
      await assertNoHorizontalOverflow(page, `Bird Log after nav (${label})`);
    });
  });
}
