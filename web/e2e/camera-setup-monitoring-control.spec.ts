import { expect, test } from "@playwright/test";

// Camera Setup Camera Node monitoring-control fix (Product Experience / UI
// Cohesion v1 Phase 1). CameraSetupPage.tsx's guided "3. Start watching"
// step used to render the legacy durable-monitoring checkbox unconditionally
// for every provider, including a paired Camera Node -- a combination the
// backend already rejects (`_reject_camera_node_legacy_monitoring_enable`,
// see "Camera Node monitoring-ownership rule" in docs/runtime-map.md). This
// proves the checkbox is gone for camera_node, so the guided flow can never
// even offer an option the backend would reject, and unchanged for a
// provider that legitimately uses legacy durable monitoring.

test("camera setup defaults the Camera type dropdown to MockingBird Camera Node, the golden path", async ({
  page,
}) => {
  // First-Hour Onboarding + Whole-Product Observability Closure v1 ("A4
  // golden path priority"): before this fix, a genuinely first-time user
  // (no prior selection) landed on "Manual media" by default -- an
  // incidental consequence of provider definition order on the backend,
  // not the documented reference/golden path. See "Native Camera Node
  // remains the reference/golden path" in product-doctrine.md.
  await page.goto("/cameras/setup");
  await expect(page.getByRole("heading", { name: "Add Camera" })).toBeVisible();

  await expect(page.getByLabel("Camera type")).toHaveValue("camera_node");
});

test("camera setup hides the legacy Start watching checkbox for a Camera Node camera", async ({
  page,
}) => {
  await page.goto("/cameras/setup");
  await expect(page.getByRole("heading", { name: "Add Camera" })).toBeVisible();

  await page.getByLabel("Camera type").selectOption("camera_node");

  await expect(page.getByRole("heading", { name: "3. Start watching" })).toBeVisible();
  await expect(page.getByLabel("Start watching once setup finishes")).toHaveCount(0);
  await expect(page.locator('input[type="checkbox"]')).toHaveCount(0);
  await expect(
    page.getByText("Finishing setup never starts watching by itself", { exact: false }),
  ).toBeVisible();
  await expect(page.getByText("Start observing", { exact: false })).toBeVisible();

  await expect(page.getByRole("button", { name: "Finish setup" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Finish and start watching" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Finish without watching yet" })).toHaveCount(0);
});

test("camera setup keeps the legacy Start watching checkbox for a non-Camera-Node camera", async ({
  page,
}) => {
  await page.goto("/cameras/setup");
  await expect(page.getByRole("heading", { name: "Add Camera" })).toBeVisible();

  await page.getByLabel("Camera type").selectOption("manual_media");

  await expect(page.getByRole("heading", { name: "3. Start watching" })).toBeVisible();
  const checkbox = page.getByLabel("Start watching once setup finishes");
  await expect(checkbox).toBeVisible();
  await expect(checkbox).not.toBeChecked();
  await expect(page.getByRole("button", { name: "Finish without watching yet" })).toBeVisible();

  await checkbox.check();
  await expect(page.getByRole("button", { name: "Finish and start watching" })).toBeVisible();
});
