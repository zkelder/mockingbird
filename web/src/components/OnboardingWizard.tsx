import { useCallback, useEffect, useState } from "react";
import { apiClient, ApiError } from "../api/client";
import type { CurrentUser, LocalDataStatus, ObservationSessionStatus, SetupState, StorageSummary } from "../api/types";
import { CameraSetupPage } from "../pages/CameraSetupPage";
import { ObservationControlPanel } from "./ObservationControlPanel";
import { formatBytes, parentDirectory } from "../utils";

type WizardStep = "welcome" | "account" | "storage" | "camera" | "observe";

const WIZARD_STEP_ORDER: WizardStep[] = ["welcome", "account", "storage", "camera", "observe"];

function isWizardStep(value: string): value is WizardStep {
  return (WIZARD_STEP_ORDER as string[]).includes(value);
}

/**
 * MockingBird Installable Local Product v1: the guided first-run experience.
 *
 * Gated in App.tsx globally while `SetupState.completed` is false -- see
 * docs/local-product-packaging-design.md. This component is a thin
 * orchestrator: the camera step embeds the existing, unmodified
 * `CameraSetupPage` (which already implements the full choose-type /
 * pair-or-configure / validate / draw-Zone / save flow), and the readiness
 * step embeds the existing, unmodified `ObservationControlPanel`. Progress is
 * persisted after every step so a refresh, a closed tab, or an app restart
 * mid-wizard resumes at the right step instead of starting over.
 *
 * `"account"` (Local Identity, Multi-User & Organization Access v1) is the
 * new second step: it creates this Host's first Administrator and, on
 * success, signs the browser in via `onAccountCreated` -- every later step
 * needs an authenticated session (see `mockingbird.api.auth.ROUTE_POLICY`'s
 * safe `authenticated`-floor default), which is exactly why account
 * creation comes right after the purely-informational "welcome" step and
 * before anything that reads real data.
 */
export function OnboardingWizard({
  onAccountCreated,
  onFinished,
}: {
  onAccountCreated: (user: CurrentUser) => void;
  onFinished: () => void;
}) {
  const [step, setStep] = useState<WizardStep>("welcome");
  const [createdStreamId, setCreatedStreamId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void apiClient
      .getSetupState()
      .then(async (state: SetupState) => {
        if (state.completed) {
          onFinished();
          return;
        }
        let resumedStep = isWizardStep(state.current_step) ? state.current_step : "welcome";
        // A rare edge case: an installation caught mid-wizard (already past
        // "welcome") by an app upgrade to this exact milestone, from a
        // build old enough to predate the "account" step entirely. Later
        // steps all need a real session; resuming one without ever having
        // created an account would otherwise just look like a broken load.
        if (resumedStep !== "welcome" && resumedStep !== "account") {
          try {
            await apiClient.getCurrentUser();
          } catch {
            resumedStep = "account";
          }
        }
        setStep(resumedStep);
        setCreatedStreamId(state.last_created_stream_id ?? null);
      })
      .catch(() => {
        // Fresh installs always start at "welcome" server-side; a read
        // failure here just means progress cannot resume precisely, not
        // that setup should be skipped.
        setError("Setup progress could not be read. Starting from the beginning.");
      })
      .finally(() => setIsLoading(false));
  }, [onFinished]);

  async function advance(nextStep: WizardStep, streamId?: string) {
    setError(null);
    try {
      await apiClient.updateSetupState({
        current_step: nextStep,
        completed: false,
        last_created_stream_id: streamId ?? createdStreamId ?? undefined,
      });
      if (streamId) {
        setCreatedStreamId(streamId);
      }
      setStep(nextStep);
    } catch {
      setError("Could not save setup progress. Check your connection and try again.");
    }
  }

  async function finish() {
    setError(null);
    try {
      await apiClient.updateSetupState({
        current_step: "done",
        completed: true,
        last_created_stream_id: createdStreamId ?? undefined,
      });
      onFinished();
    } catch {
      setError("Could not finish setup. Try again in a moment.");
    }
  }

  async function handleCameraComplete(streamId: string) {
    try {
      // A fresh install starts with an illustrative sample camera so a brand
      // new Dashboard is never blank; once a real camera exists, replace it
      // instead of confusingly mixing the two. This is the same action
      // already available from Local Data -- see `removeSampleData` -- so
      // this adds no new backend behavior. Best-effort: never blocks setup.
      await apiClient.removeSampleData();
    } catch {
      // Non-fatal -- the sample walkthrough staying visible is not an error.
    }
    void advance("observe", streamId);
  }

  if (isLoading) {
    return <div className="panel">Loading setup…</div>;
  }

  return (
    <div className="onboarding-wizard page-stack">
      <section className="page-header">
        <div>
          <span className="eyebrow">
            Setup step {WIZARD_STEP_ORDER.indexOf(step) + 1} of {WIZARD_STEP_ORDER.length}
          </span>
          <h1>Welcome to MockingBird</h1>
          <p>A few quick steps get MockingBird watching your yard.</p>
        </div>
      </section>
      {error ? <div className="error-panel">{error}</div> : null}
      {step === "welcome" ? <WelcomeStep onContinue={() => void advance("account")} /> : null}
      {step === "account" ? (
        <AccountStep
          onCreated={(user) => {
            onAccountCreated(user);
            void advance("storage");
          }}
        />
      ) : null}
      {step === "storage" ? <StorageStep onContinue={() => void advance("camera")} /> : null}
      {step === "camera" ? (
        <CameraSetupPage
          onCancel={() => void finish()}
          onComplete={(streamId) => void handleCameraComplete(streamId)}
          onSourcesChanged={() => {}}
        />
      ) : null}
      {step === "observe" ? (
        createdStreamId ? (
          <ObserveStep streamId={createdStreamId} onFinish={() => void finish()} />
        ) : (
          // Progress said "observe" but no camera is on record (for example
          // an interrupted session) -- an honest recovery, not a dead end.
          <section className="panel page-stack">
            <h2>No camera on record yet</h2>
            <p>Add a camera to start observing, or finish setup and add one later from Cameras.</p>
            <div className="panel-actions">
              <button className="secondary-action" onClick={() => void advance("camera")} type="button">
                Add a camera
              </button>
              <button className="primary-action" onClick={() => void finish()} type="button">
                Finish setup
              </button>
            </div>
          </section>
        )
      ) : null}
    </div>
  );
}

function WelcomeStep({ onContinue }: { onContinue: () => void }) {
  return (
    <section className="panel page-stack">
      <h2>What MockingBird does</h2>
      <p>
        MockingBird watches outdoor cameras you choose and quietly notices meaningful visits from
        birds and other wildlife. Sightings show up right away in Today and Bird Log, often with a
        likely species guess -- MockingBird never claims an identification as certain until you
        confirm or correct it, whenever you'd like.
      </p>
      <ul className="onboarding-promise-list">
        <li>Your video and data stay on this device.</li>
        <li>Nothing is uploaded or shared automatically.</li>
        <li>You choose when observing starts and stops.</li>
      </ul>
      <div className="panel-actions">
        <button className="primary-action" onClick={onContinue} type="button">
          Get started
        </button>
      </div>
    </section>
  );
}

function AccountStep({ onCreated }: { onCreated: (user: CurrentUser) => void }) {
  const [displayName, setDisplayName] = useState("");
  const [loginIdentity, setLoginIdentity] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const user = await apiClient.createFirstAdministrator({
        display_name: displayName,
        login_identity: loginIdentity,
        password,
      });
      onCreated(user);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Could not create your administrator account.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form className="panel page-stack auth-form" onSubmit={(event) => void handleSubmit(event)}>
      <h2>Create your administrator account</h2>
      <p>
        This is the first account on this Host, with full access to cameras, users, and system
        settings. You can add Viewer and Reviewer accounts for others later from Users.
      </p>
      {error ? <div className="error-panel">{error}</div> : null}
      <label>
        Your name
        <input
          autoFocus
          onChange={(event) => setDisplayName(event.target.value)}
          type="text"
          value={displayName}
        />
      </label>
      <label>
        Login identity
        <input
          autoComplete="username"
          onChange={(event) => setLoginIdentity(event.target.value)}
          type="text"
          value={loginIdentity}
        />
      </label>
      <label>
        Password
        <input
          autoComplete="new-password"
          minLength={10}
          onChange={(event) => setPassword(event.target.value)}
          type="password"
          value={password}
        />
        <span className="meta-text">At least 10 characters.</span>
      </label>
      <div className="panel-actions">
        <button
          className="primary-action"
          disabled={isSubmitting || !displayName || !loginIdentity || password.length < 10}
          type="submit"
        >
          {isSubmitting ? "Creating…" : "Create account"}
        </button>
      </div>
    </form>
  );
}

function StorageStep({ onContinue }: { onContinue: () => void }) {
  const [status, setStatus] = useState<LocalDataStatus | null>(null);
  const [storage, setStorage] = useState<StorageSummary | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([apiClient.getLocalDataStatus(), apiClient.getStorageRetentionSummary()])
      .then(([nextStatus, nextStorage]) => {
        setStatus(nextStatus);
        setStorage(nextStorage);
      })
      .catch(() => setLoadError("Local storage details could not be read."));
  }, []);

  const usedBytes = storage
    ? (storage.approximate_database_bytes ?? 0) + storage.total_managed_media_bytes
    : null;

  return (
    <section className="panel page-stack">
      <h2>Where MockingBird keeps your data</h2>
      <p>
        Cameras, Zones, reviewed visits, exports, and backups all stay in one local folder on this
        device. MockingBird created it automatically; there is nothing to set up.
      </p>
      {status?.database_path ? (
        <code className="onboarding-storage-path">{parentDirectory(status.database_path)}</code>
      ) : null}
      {storage ? (
        <div className="monitoring-continuity-facts">
          <span>
            <strong>Currently used</strong> {usedBytes !== null ? formatBytes(usedBytes) : "Unknown"}
          </span>
          <span>
            <strong>Free space</strong> {formatBytes(storage.disk_free_bytes)}
          </span>
          <span>
            <strong>Writable</strong> {storage.is_writable ? "Yes" : "No"}
          </span>
        </div>
      ) : null}
      {storage && !storage.is_writable ? (
        <div className="error-panel">
          MockingBird cannot write to its data folder. Fix folder permissions, then continue.
        </div>
      ) : storage?.storage_warning ? (
        // Storage/Privacy/Recovery v1 Phase C's `critical` tier means new
        // evidence may soon fail to save -- distinct from, and more urgent
        // than, an early `getting_low`/`action_recommended` heads-up, so it
        // reuses the same `error-panel` treatment as the not-writable case
        // above instead of the calm `notice-panel` every tier previously
        // shared.
        <div className={storage.storage_health_tier === "critical" ? "error-panel" : "notice-panel"}>
          <span>{storage.storage_warning}</span>
        </div>
      ) : null}
      {loadError ? <div className="error-panel">{loadError}</div> : null}
      <div className="panel-actions">
        <button
          className="primary-action"
          disabled={Boolean(storage && !storage.is_writable)}
          onClick={onContinue}
          type="button"
        >
          Continue
        </button>
      </div>
    </section>
  );
}

function ObserveStep({ streamId, onFinish }: { streamId: string; onFinish: () => void }) {
  // `null` = not yet known (first poll still in flight) -- deliberately
  // defaults to the live-observing copy below rather than flashing the
  // no-runtime copy first, since most Sources do support observing.
  const [runtimeAvailable, setRuntimeAvailable] = useState<boolean | null>(null);
  const handleStatus = useCallback((status: ObservationSessionStatus | null) => {
    setRuntimeAvailable(status?.runtime_available ?? null);
  }, []);

  return (
    <div className="page-stack">
      <section className="panel page-stack">
        <h2>Your camera is ready</h2>
        {runtimeAvailable === false ? (
          <p>
            This camera type doesn&rsquo;t watch for activity on its own here, so there is no
            Start observing step for it. If this is a recorded/imported Source, use{" "}
            <strong>Import Media</strong> (in the main menu) whenever you&rsquo;re ready to add
            video or image files -- MockingBird analyzes them the same way a live camera&rsquo;s
            activity is analyzed. Sightings will show up in Today and Bird Log; open Review Queue
            any time you want to work through suggestions in one place. Nothing here is
            permanent, and you can add or adjust Sources any time from Cameras.
          </p>
        ) : (
          <p>
            Start observing when you would like MockingBird to watch this camera. Sightings will
            show up in Today and Bird Log as they happen; open Review Queue any time you want to
            work through suggestions in one place. Nothing here is permanent, and you can start or
            stop observing any time from Cameras.
          </p>
        )}
      </section>
      <ObservationControlPanel streamId={streamId} onStatus={handleStatus} />
      <section className="panel-actions">
        <button className="primary-action" onClick={onFinish} type="button">
          Finish setup
        </button>
      </section>
    </div>
  );
}
