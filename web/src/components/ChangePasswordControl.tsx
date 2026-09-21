import { useState } from "react";
import { apiClient, ApiError } from "../api/client";

/**
 * Self-service password change, in the account menu -- Pre-Release Trust &
 * Correctness Correction v1 (FLOW-3). The Users page has always told an
 * administrator "see the account menu to change your own password," but no
 * such control existed even though the backend endpoint
 * (`POST /api/auth/change-password`) already did. Mirrors `UsersPage.tsx`'s
 * `ResetPasswordControl` disclosure pattern, with the addition of the
 * current-password proof that endpoint's own contract requires.
 */
export function ChangePasswordControl() {
  const [isOpen, setIsOpen] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function close() {
    setIsOpen(false);
    setCurrentPassword("");
    setNewPassword("");
    setError(null);
    setMessage(null);
  }

  if (!isOpen) {
    return (
      <button className="text-action" onClick={() => setIsOpen(true)} type="button">
        Change password
      </button>
    );
  }

  async function handleChange() {
    setError(null);
    setIsSubmitting(true);
    try {
      await apiClient.changeOwnPassword({ current_password: currentPassword, new_password: newPassword });
      // Deliberately stays open with the form replaced by the success
      // message -- closing immediately (setIsOpen(false) in the same
      // update as setMessage) would collapse back to the toggle button
      // before the message ever painted a frame.
      setMessage("Password changed. You're still signed in here; other sessions were signed out.");
      setCurrentPassword("");
      setNewPassword("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not change the password.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (message) {
    return (
      <div className="account-menu-password-form inline-reset-password">
        <div className="notice-panel">{message}</div>
        <button className="text-action" onClick={close} type="button">
          Close
        </button>
      </div>
    );
  }

  return (
    <div className="account-menu-password-form auth-form inline-reset-password">
      {error ? <div className="error-panel">{error}</div> : null}
      <label>
        Current password
        <input
          autoComplete="current-password"
          onChange={(event) => setCurrentPassword(event.target.value)}
          type="password"
          value={currentPassword}
        />
      </label>
      <label>
        New password
        <input
          autoComplete="new-password"
          minLength={10}
          onChange={(event) => setNewPassword(event.target.value)}
          type="password"
          value={newPassword}
        />
        <span className="meta-text">At least 10 characters.</span>
      </label>
      <div className="button-row">
        <button
          className="primary-action"
          disabled={isSubmitting || !currentPassword || newPassword.length < 10}
          onClick={() => void handleChange()}
          type="button"
        >
          {isSubmitting ? "Saving…" : "Save new password"}
        </button>
        <button className="secondary-action" onClick={close} type="button">
          Cancel
        </button>
      </div>
    </div>
  );
}
