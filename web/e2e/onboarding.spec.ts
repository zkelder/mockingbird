import { expect, test } from "@playwright/test";

// MockingBird Installable Local Product v1: first-run onboarding
// (docs/local-product-packaging-design.md). Runs against its own isolated,
// genuinely fresh MockingBird instance (see playwright.onboarding.config.ts)
// -- separate from the shared suite's already-configured instance, and
// separate from the heavier real-camera/real-observation validation this
// milestone performs directly against the API and a real paired Camera
// Node (browser automation cannot supply real camera hardware).

// Runs before the completion test below, in file order (this config uses
// one worker against one shared fresh instance): a direct deep link must
// bypass the wizard specifically while setup is still genuinely incomplete.
test("a direct deep link during a fresh install renders the normal app, not the wizard", async ({
  page,
}) => {
  // The onboarding gate applies to the dashboard route only (see
  // docs/local-product-packaging-design.md) -- a bookmarked or shared link
  // must not be hijacked into a setup wizard.
  await page.goto("/review");

  await expect(page.getByRole("heading", { name: "Welcome to MockingBird" })).toHaveCount(0);
});

test("a fresh install shows guided setup, persists progress across a reload, and finishing reaches the normal Dashboard", async ({
  page,
}) => {
  await page.goto("/");

  // Welcome: what MockingBird does, no developer vocabulary.
  await expect(page.getByRole("heading", { name: "Welcome to MockingBird" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "What MockingBird does" })).toBeVisible();
  const bodyText = await page.locator("body").innerText();
  for (const forbidden of ["uvicorn", "venv", "pip install", "npm run", "WSL"]) {
    expect(bodyText).not.toContain(forbidden);
  }
  await page.getByRole("button", { name: "Get started" }).click();

  // Storage: local data location/usage/writability, no SQLite internals --
  // a folder to look at, never the database filename/engine itself.
  await expect(page.getByRole("heading", { name: "Where MockingBird keeps your data" })).toBeVisible();
  await expect(page.getByText("Writable")).toBeVisible();
  const storageBodyText = await page.locator("body").innerText();
  expect(storageBodyText.toLowerCase()).not.toContain(".sqlite3");
  expect(storageBodyText.toLowerCase()).not.toContain("sqlite3");
  await page.getByRole("button", { name: "Continue" }).click();

  // Camera: the existing, unmodified guided Add Camera flow is embedded
  // directly -- proving composition, not a second implementation of it.
  await expect(page.getByRole("heading", { name: "Add Camera" })).toBeVisible();

  // A reload mid-wizard must resume at the saved step, not restart --
  // "close/reopen without losing configuration."
  await page.reload();
  await expect(page.getByRole("heading", { name: "Add Camera" })).toBeVisible();

  // Finishing without a camera is an explicit, honest escape hatch (the
  // milestone does not require every step during first run); the app then
  // shows the normal product shell instead of the wizard.
  await page.getByRole("button", { name: "Discard setup" }).click();
  await expect(page.getByRole("heading", { name: "Today in Your Yard" })).toBeVisible();

  // Onboarding must never reappear after completion, including on reload.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Today in Your Yard" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Welcome to MockingBird" })).toHaveCount(0);
});
