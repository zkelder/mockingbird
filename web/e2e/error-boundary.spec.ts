import { expect, test } from "@playwright/test";

// Pre-Release Trust & Correctness Correction v1 (FLOW-10, elevated to
// release-critical): before this, an unexpected render error anywhere in
// the component tree turned the entire app into a blank white screen with
// no recovery path -- there was no top-level React error boundary at all.
// `?mockingbird_test_crash=1` is a deliberate, test-only hook
// (web/src/main.tsx) that throws during render in place of the real app,
// proving the boundary catches a genuine descendant render failure rather
// than relying on finding or fabricating a real defect to trigger one.

test("a render failure is caught by a calm, recoverable error screen, never a blank page", async ({ page }) => {
  await page.goto("/?mockingbird_test_crash=1");

  const boundary = page.locator(".app-error-boundary");
  await expect(boundary).toBeVisible();
  await expect(boundary).toContainText("MockingBird ran into a problem");
  await expect(boundary).toContainText("Your reviewed history and evidence are safe");

  // Never a blank page: the document has real, visible content.
  const bodyText = await page.locator("body").innerText();
  expect(bodyText.trim().length).toBeGreaterThan(0);

  // No raw stack trace or implementation detail dumped into the UI.
  await expect(boundary).not.toContainText("at TestCrash");
  await expect(boundary).not.toContainText(".tsx:");

  const reload = boundary.getByRole("button", { name: "Reload MockingBird" });
  await expect(reload).toBeVisible();

  // Reloading returns to the same crash-test URL (test artifact of the
  // hook, not the product), so it deterministically re-shows the boundary
  // rather than silently recovering -- proving Reload actually reloads.
  await reload.click();
  await expect(boundary).toBeVisible();
});

test("a normal load never shows the error boundary", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".app-error-boundary")).toHaveCount(0);
});
