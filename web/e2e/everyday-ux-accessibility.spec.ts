import { expect, test } from "@playwright/test";
import { userFacingErrorMessage } from "../src/utils";

// Everyday UX & Accessibility Closure v1. Covers the keyboard-operable Zone
// area editor on guided camera setup, the progressive-disclosure changes on
// the Visit / Stream / Local Data pages, and the raw-exception copy seam.

const STREAM_ID = "stream-backyard-feeder";

// A tiny, valid JPEG (same fixture other specs use) so a real Visit exists.
const TINY_JPEG_BASE64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAIAAgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDyuiiivxM/ns//2Q==";

async function seedUnreviewedVisit(page: import("@playwright/test").Page): Promise<string> {
  const response = await page.request.post("/api/media/import", {
    multipart: {
      file: { name: "everyday-ux.jpg", mimeType: "image/jpeg", buffer: Buffer.from(TINY_JPEG_BASE64, "base64") },
      stream_id: STREAM_ID,
      subject_label: "unknown_bird",
    },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).visit.id as string;
}

test.describe("Zone area editor is keyboard-operable", () => {
  test("arrow keys move, Shift+arrows resize, typed values commit, focus is visible", async ({ page }) => {
    await page.goto("/cameras/setup");
    const canvas = page.getByRole("group", { name: "Area to watch" });
    const left = page.getByLabel("Left edge");
    const top = page.getByLabel("Top edge");
    const width = page.getByLabel("Width", { exact: true });
    const height = page.getByLabel("Height", { exact: true });

    // Default rectangle: 20%..80% on both axes.
    await expect(left).toHaveValue("20");
    await expect(width).toHaveValue("60");

    // Reach the canvas by keyboard (Shift+Tab from the first field) so
    // :focus-visible applies, and prove the focus ring is actually drawn.
    await left.focus();
    await page.keyboard.press("Shift+Tab");
    await expect(canvas).toBeFocused();
    const outlineWidth = await canvas.evaluate((el) => getComputedStyle(el).outlineWidth);
    expect(outlineWidth).toBe("3px");

    // Move: 2% per press.
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("ArrowDown");
    await expect(left).toHaveValue("24");
    await expect(top).toHaveValue("22");

    // Resize with Shift; fine step with Alt.
    await page.keyboard.press("Shift+ArrowLeft");
    await expect(width).toHaveValue("58");
    await page.keyboard.press("Alt+Shift+ArrowDown");
    await expect(height).toHaveValue("60.5");

    // The visible rectangle follows the same state.
    const rect = page.locator(".zone-drawing-rectangle");
    await expect(rect).toHaveCSS("left", /./);
    expect(await rect.evaluate((el) => (el as HTMLElement).style.left)).toMatch(/^24(\.0+)?%$/);

    // The move is clamped to the picture: the rectangle can never leave it.
    for (let i = 0; i < 60; i += 1) await page.keyboard.press("ArrowRight");
    await expect(left).toHaveValue("42"); // 100 - 58 width

    // Typed values are held until the field is left, so "10" is not clamped
    // at the "1" keystroke; out-of-range values clamp on commit.
    await width.fill("10");
    await expect(width).toHaveValue("10");
    await width.press("Tab");
    await expect(width).toHaveValue("10");
    await height.fill("500");
    await height.press("Enter");
    await expect(height).toHaveValue("78"); // stops at the picture edge: top (22) + height <= 100
    await expect(top).toHaveValue("22");

    // Instructions are programmatically associated with the control.
    await expect(canvas).toHaveAttribute("aria-describedby", "zone-drawing-instructions");
    await expect(page.locator("#zone-drawing-instructions")).toContainText("arrow keys");
  });
});

test.describe("Progressive disclosure keeps access", () => {
  test("Visit curation is collapsed by default, opens in place, and review stays first", async ({ page }) => {
    const visitId = await seedUnreviewedVisit(page);
    await page.goto(`/visits/${visitId}`);
    const curation = page.locator("details.visit-curation-details");
    await expect(curation).toBeVisible();
    await expect(curation).not.toHaveAttribute("open", "");
    await expect(page.getByRole("heading", { name: "Merge nearby Visits" })).toBeHidden();
    // The correction path is never behind a disclosure.
    await expect(page.getByRole("button", { name: "Confirm species" })).toBeVisible();

    await curation.locator("summary").click();
    await expect(page.getByRole("heading", { name: "Merge nearby Visits" })).toBeVisible();

    // Keyboard: summary is reachable and toggles with Enter.
    await curation.locator("summary").focus();
    await page.keyboard.press("Enter");
    await expect(page.getByRole("heading", { name: "Merge nearby Visits" })).toBeHidden();
  });

  test("Stream Recent Visits no longer repeats a mislabeled Merge nearby action", async ({ page }) => {
    await seedUnreviewedVisit(page);
    await page.goto(`/streams/${STREAM_ID}`);
    await expect(page.getByRole("heading", { name: "Recent Visits" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Merge nearby" })).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Open Visit detail" }).first()).toBeVisible();
  });

  test("Local Data keeps reset and remote-access reference secondary but reachable", async ({ page }) => {
    await page.goto("/local-data");
    await expect(page.getByRole("heading", { name: "Local Data" })).toBeVisible();
    const reset = page.locator("details.local-data-secondary");
    await expect(reset).not.toHaveAttribute("open", "");
    await expect(page.getByRole("button", { name: "Reset demo data" })).toBeHidden();
    await reset.locator("summary").click();
    await expect(page.getByRole("button", { name: "Reset demo data" })).toBeVisible();

    // Sign-in reassurance stays visible; the how-to is one disclosure away.
    await expect(page.getByText("Signing in is always required, on any device.")).toBeVisible();
    const howTo = page.locator("details", { hasText: "How phone and remote access works" });
    await expect(page.getByText("Tailscale")).toBeHidden();
    await howTo.locator("summary").click();
    await expect(page.getByText(/Tailscale/)).toBeVisible();
  });
});

test.describe("Raw exception text never reaches the user", () => {
  test("userFacingErrorMessage passes product text through and replaces runtime errors", () => {
    expect(userFacingErrorMessage(new Error("That tag already exists."), "Could not add this tag.")).toBe(
      "That tag already exists.",
    );
    expect(userFacingErrorMessage(new SyntaxError("Unexpected token '<'"), "Could not load visit detail.")).toBe(
      "Could not load visit detail.",
    );
    expect(
      userFacingErrorMessage(new TypeError("Cannot read properties of undefined"), "Could not save."),
    ).toBe("Could not save.");
    expect(userFacingErrorMessage("boom", "Could not save.")).toBe("Could not save.");
    expect(userFacingErrorMessage(new Error("   "), "Could not save.")).toBe("Could not save.");
  });

  test("a non-JSON success response shows a product message, not a JSON parse error", async ({ page }) => {
    const visitId = await seedUnreviewedVisit(page);
    await page.route(`**/api/visits/${visitId}/detail`, (route) =>
      route.fulfill({ status: 200, contentType: "text/html", body: "<html>gateway page</html>" }),
    );
    await page.goto(`/visits/${visitId}`);
    await expect(page.getByText(/could not read/i).first()).toBeVisible();
    await expect(page.getByText(/Unexpected token|is not valid JSON/i)).toHaveCount(0);
  });
});
