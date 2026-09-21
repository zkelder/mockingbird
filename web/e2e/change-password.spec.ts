import { expect, test } from "@playwright/test";

// Pre-Release Trust & Correctness Correction v1 (FLOW-3): the Users page
// has always told administrators "see the account menu to change your own
// password," but no such control existed anywhere, even though the backend
// endpoint (POST /api/auth/change-password) already worked (see
// tests/test_local_identity_multi_user.py for its own coverage). This
// proves the new ChangePasswordControl end to end, against a throwaway
// user created for this test -- never the shared suite's own e2e-admin
// account, since a change to that account's password would affect every
// other spec sharing its storage state.

// Runs in its own unauthenticated context (bypassing the shared admin
// storageState every other spec starts from) so it can perform a real
// sign-in as the throwaway user it creates.
test.use({ storageState: { cookies: [], origins: [] } });

const ADMIN_LOGIN_IDENTITY = "e2e-admin";
const ADMIN_PASSWORD = "e2e-shared-suite-admin-password-1";

async function signIn(page: import("@playwright/test").Page, loginIdentity: string, password: string) {
  await page.goto("/");
  await page.getByLabel("Login identity").fill(loginIdentity);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "MockingBird status" })).toBeVisible();
}

test("a signed-in user can change their own password from the account menu", async ({ page }) => {
  const loginIdentity = `e2e-password-change-${Date.now()}`;
  const originalPassword = "throwaway-original-password-1";
  const newPassword = "throwaway-changed-password-2";

  await signIn(page, ADMIN_LOGIN_IDENTITY, ADMIN_PASSWORD);

  // Create a throwaway user as the admin, then hand off entirely to it.
  await page.goto("/users");
  await page.getByLabel("Display name").fill("E2E Password Change");
  await page.getByLabel("Login identity").fill(loginIdentity);
  await page.getByLabel("Temporary password").fill(originalPassword);
  await page.getByRole("button", { name: "Add user" }).click();
  await expect(page.getByText(loginIdentity)).toBeVisible();

  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();

  await signIn(page, loginIdentity, originalPassword);

  const accountMenu = page.locator(".account-menu");
  await accountMenu.getByRole("button", { name: "Change password" }).click();
  await accountMenu.getByLabel("Current password").fill(originalPassword);
  await accountMenu.getByLabel("New password").fill(newPassword);
  await accountMenu.getByRole("button", { name: "Save new password" }).click();

  await expect(accountMenu.getByText("Password changed.")).toBeVisible();
  // No password value, old or new, is ever echoed back into the DOM.
  await expect(page.locator("body")).not.toContainText(originalPassword);
  await expect(page.locator("body")).not.toContainText(newPassword);

  // The current session survives a self-service change (only *other*
  // sessions are revoked) -- still signed in, no forced sign-out.
  await expect(page.getByRole("heading", { name: "MockingBird status" })).toBeVisible();

  // Prove the new password actually took effect and the old one no longer
  // works, with a real fresh sign-in.
  await accountMenu.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();

  await page.getByLabel("Login identity").fill(loginIdentity);
  await page.getByLabel("Password").fill(originalPassword);
  await page.getByRole("button", { name: "Sign in" }).click();
  // The old password is genuinely rejected -- proves the change took effect
  // server-side, not only that the UI showed a success message.
  await expect(page.locator(".error-panel")).toBeVisible();

  await signIn(page, loginIdentity, newPassword);
});

test("an incorrect current password is rejected with a clear error, never silently accepted", async ({
  page,
}) => {
  const loginIdentity = `e2e-password-change-wrong-${Date.now()}`;
  const originalPassword = "throwaway-original-password-3";

  await signIn(page, ADMIN_LOGIN_IDENTITY, ADMIN_PASSWORD);
  await page.goto("/users");
  await page.getByLabel("Display name").fill("E2E Wrong Current Password");
  await page.getByLabel("Login identity").fill(loginIdentity);
  await page.getByLabel("Temporary password").fill(originalPassword);
  await page.getByRole("button", { name: "Add user" }).click();
  await expect(page.getByText(loginIdentity)).toBeVisible();
  await page.getByRole("button", { name: "Sign out" }).click();

  await signIn(page, loginIdentity, originalPassword);

  const accountMenu = page.locator(".account-menu");
  await accountMenu.getByRole("button", { name: "Change password" }).click();
  await accountMenu.getByLabel("Current password").fill("definitely-the-wrong-password");
  await accountMenu.getByLabel("New password").fill("some-new-password-4");
  await accountMenu.getByRole("button", { name: "Save new password" }).click();

  await expect(accountMenu.locator(".error-panel")).toBeVisible();
  await expect(accountMenu.getByText("Password changed.")).not.toBeVisible();
});
