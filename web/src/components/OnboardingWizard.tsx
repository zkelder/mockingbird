import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type { LocalDataStatus, SetupState, StorageSummary } from "../api/types";
import { CameraSetupPage } from "../pages/CameraSetupPage";
import { ObservationControlPanel } from "./ObservationControlPanel";
import { formatBytes, parentDirectory } from "../utils";

type WizardStep = "welcome" | "storage" | "camera" | "observe";

const WIZARD_STEP_ORDER: WizardStep[] = ["welcome", "storage", "camera", "observe"];

function isWizardStep(value: string): value is WizardStep {
  return (WIZARD_STEP_ORDER as string[]).includes(value);
}

/**
 * MockingBird Installable Local Product v1: the guided first-run experience.
 *
 * Gated in App.tsx to the dashboard route only, and only while
 * `SetupState.completed` is false -- see docs/local-product-packaging-design.md.
 * This component is a thin orchestrator: the camera step embeds the existing,
 * unmodified `CameraSetupPage` (which already implements the full choose-type
 * / pair-or-configure / validate / draw-Zone / save flow), and the readiness
 * step embeds the existing, unmodified `ObservationControlPanel`. Progress is
 * persisted after every step so a refresh, a closed tab, or an app restart
 * mid-wizard resumes at the right step instead of starting over.
 */
export function OnboardingWizard({ onFinished }: { onFinished: () => void }) {
  const [step, setStep] = useState<WizardStep>("welcome");
  const [createdStreamId, setCreatedStreamId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void apiClient
      .getSetupState()
      .then((state: SetupState) => {
        if (state.completed) {
          onFinished();
          return;
        }
        setStep(isWizardStep(state.current_step) ? state.current_step : "welcome");
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
      {step === "welcome" ? <WelcomeStep onContinue={() => void advance("storage")} /> : null}
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
        birds and other wildlife. When something worth a look happens, it appears in your Review
        Queue for you to confirm -- MockingBird never claims an identification as certain until
        you say so.
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
        <div className="notice-panel">
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
  return (
    <div className="page-stack">
      <section className="panel page-stack">
        <h2>Your camera is ready</h2>
        <p>
          Start observing when you would like MockingBird to watch this camera. Anything worth a
          look lands in Review Queue; nothing here is permanent, and you can start or stop any
          time from Cameras.
        </p>
      </section>
      <ObservationControlPanel streamId={streamId} />
      <section className="panel-actions">
        <button className="primary-action" onClick={onFinish} type="button">
          Finish setup
        </button>
      </section>
    </div>
  );
}
