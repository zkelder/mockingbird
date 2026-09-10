import { useEffect, useState } from "react";
import { apiClient, ApiError } from "../api/client";
import type { CurrentUser, InstallationSettings } from "../api/types";

interface SignInPageProps {
  onSignedIn: (user: CurrentUser) => void;
}

// Local Identity, Multi-User & Organization Access v1: the normal product
// flow for every returning session on an already-set-up Host -- unlike
// OnboardingWizard's "account" step (first-run only, creates the very
// first Administrator), this page only ever signs in an existing user.
export function SignInPage({ onSignedIn }: SignInPageProps) {
  const [installationName, setInstallationName] = useState<string | null>(null);
  const [loginIdentity, setLoginIdentity] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void apiClient
      .getInstallationSettings()
      .then((settings: InstallationSettings) => {
        if (!cancelled) {
          setInstallationName(settings.installation_name ?? null);
        }
      })
      .catch(() => {
        // Display-only; a calm sign-in screen still works with no name shown.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const user = await apiClient.signIn({ login_identity: loginIdentity, password });
      onSignedIn(user);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not reach MockingBird. Check your connection and try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="sign-in-shell">
      <form className="panel sign-in-card" onSubmit={(event) => void handleSubmit(event)}>
        <div className="brand-block">
          <span className="brand-mark">MB</span>
          <div>
            <strong>MockingBird</strong>
            <span>{installationName ?? "Local wildlife observatory"}</span>
          </div>
        </div>
        <h1>Sign in</h1>
        {error ? (
          <div className="error-panel" role="alert">
            {error}
          </div>
        ) : null}
        <label>
          Login identity
          <input
            autoComplete="username"
            autoFocus
            name="login_identity"
            onChange={(event) => setLoginIdentity(event.target.value)}
            type="text"
            value={loginIdentity}
          />
        </label>
        <label>
          Password
          <input
            autoComplete="current-password"
            name="password"
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            value={password}
          />
        </label>
        <button
          className="primary-action"
          disabled={isSubmitting || !loginIdentity || !password}
          type="submit"
        >
          {isSubmitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
