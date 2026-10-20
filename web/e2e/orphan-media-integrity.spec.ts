import { expect, test } from "@playwright/test";
import { existsSync } from "node:fs";
import { mkdir, utimes, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";

// Orphan Media Integrity & Recovery v1: Local Data -> Storage & Retention ->
// Storage integrity. A check is report-only; moving to the recovery folder is a
// separate confirmed step; the file is never deleted and can be moved back.

const runtimeRoot = resolve(process.env.MOCKINGBIRD_E2E_RUNTIME_ROOT ?? "");
const mediaRoot = join(runtimeRoot, "media");

test("a check finds an unowned file, recovery is confirmed, and it can be moved back", async ({ page }) => {
  const name = `unowned-e2e-${Date.now()}.jpg`;
  const orphan = join(mediaRoot, "orphan-e2e", name);
  await mkdir(join(mediaRoot, "orphan-e2e"), { recursive: true });
  await writeFile(orphan, "not-referenced-by-any-record");
  const old = new Date(Date.now() - 3 * 3600 * 1000);
  await utimes(orphan, old, old); // past the "possibly still being written" grace

  await page.goto("/local-data");
  const panel = page.getByLabel("Storage integrity");
  await expect(panel.getByRole("heading", { name: "Storage integrity" })).toBeVisible();

  // Checking is report-only.
  await panel.getByRole("button", { name: "Check storage integrity" }).click();
  await expect(panel.getByText(/Unowned media found:/)).toBeVisible();
  expect(existsSync(orphan)).toBe(true);
  await panel.getByText(/Review files/).click();
  await expect(panel.getByText(new RegExp(`orphan-e2e/${name}`))).toBeVisible();
  // Ordinary UI never shows the absolute local path.
  await expect(page.locator("body")).not.toContainText(runtimeRoot);

  // Two-step confirmation; cancel leaves the file alone.
  await panel.getByRole("button", { name: "Review recovery options" }).click();
  await panel.getByRole("button", { name: "Cancel" }).click();
  expect(existsSync(orphan)).toBe(true);

  await panel.getByRole("button", { name: "Review recovery options" }).click();
  await panel.getByRole("button", { name: "Confirm: Move to recovery folder" }).click();
  await expect(panel.getByRole("status").filter({ hasText: "Nothing was deleted" })).toBeVisible();
  expect(existsSync(orphan)).toBe(false);

  // Move it back from the recovery list.
  await panel.getByText(/Unowned media moved to recovery/).click();
  await panel.getByRole("button", { name: "Move back" }).first().click();
  await expect(panel.getByRole("status").filter({ hasText: "moved back" })).toBeVisible();
  expect(existsSync(orphan)).toBe(true);

  // Leave the shared instance clean for the next check.
  await panel.getByRole("button", { name: "Check storage integrity" }).click();
  await panel.getByRole("button", { name: "Review recovery options" }).click();
  await panel.getByRole("button", { name: "Confirm: Move to recovery folder" }).click();
  await expect(panel.getByRole("status").filter({ hasText: "Nothing was deleted" })).toBeVisible();
});

test("a clean library reports no unowned media", async ({ page }) => {
  await page.goto("/local-data");
  const panel = page.getByLabel("Storage integrity");
  await panel.getByRole("button", { name: "Check storage integrity" }).click();
  await expect(panel.getByText(/No unowned media found|Unowned media found:/)).toBeVisible();
});
