import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "../api/client";
import type { ObservationSessionStatus, SceneConfusorLearningStatus } from "../api/types";
import { StatusPill } from "./StatusPill";
import { formatDateTime, formatLabel } from "../utils";

const POLL_INTERVAL_MS = 3000;

function randomIdempotencyKey(prefix: string): string {
  return globalThis.crypto?.randomUUID?.() ?? `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function stateLabel(status: ObservationSessionStatus | null): string {
  if (!status) return "Not observing";
  if (!status.runtime_available) return "Not available here";
  switch (status.state) {
    case "observing":
      return "Observing";
    case "starting":
      return "Starting…";
    case "stopping":
      return "Stopping…";
    case "needs_attention":
      return "Needs attention";
    default:
      return "Not observing";
  }
}

function statusTone(status: ObservationSessionStatus | null): "good" | "review" | "quiet" {
  if (!status || !status.runtime_available) return "quiet";
  if (status.state === "observing") return "good";
  if (status.state === "needs_attention") return "review";
  return "quiet";
}

const ADVANCED_LABELS: Record<string, string> = {
  runtime_kind: "Runtime",
  provider_key: "Provider",
  detector_provider_key: "Detector",
  desired_mode: "Desired mode",
  actual_state: "Actual state",
  failure_code: "Failure code",
  monitor_status: "Monitor status",
  activation_boundary_at: "Activation boundary",
};

// Plain-language override for the one suppression reason that most benefits
// from it (see docs/scene-confusor-suspicion-contract.md "UI" -- diagnostics
// stay here, in the advanced/support view, not the everyday Today
// experience). Every other reason falls back to the existing generic
// `formatLabel` conversion unchanged.
const SUPPRESSED_REASON_LABELS: Record<string, string> = {
  blocked_scene_confusor_suspected: "Repeated background pattern ignored",
};

// Site-Specific Learning & Local Adaptation v1: the smallest honest label a
// non-technical user needs -- never "region", "occurrence count", or any
// other model-internal term (see docs/scene-confusor-suspicion-contract.md,
// "Operator surface").
//
// Acceptance correction (2026-08-24): evidence-based state (is anything
// being learned/evaluated from reviewed activity?) is checked before, and
// independently of, whether production adaptation is currently turned on --
// collecting/evaluating reviewed evidence never stops just because
// production adaptation is off (the default), so this must never say
// "disabled" while that evaluation is still ongoing. The enable/disable
// button below already communicates the operator's own current production
// setting; this line only ever describes what the evidence itself shows.
function learningStatusLabel(status: SceneConfusorLearningStatus | null): string {
  if (!status) return "Reading…";
  if (status.regions_currently_adjusted > 0) {
    return status.reviewed_evidence_enabled ? "Local adjustment active" : "Learning from reviewed activity on this camera";
  }
  if (status.regions_with_reviewed_evidence > 0) return "Learning from reviewed activity on this camera";
  return "Not enough reviewed history yet";
}

/**
 * The unified Observation panel (Unified Observation Experience v1):
 * Start/Stop for one Stream, plus compact camera and observation-capability
 * health, no matter which existing runtime actually backs this Stream
 * (Camera Node's accepted frame-driven engine, existing backend-owned live
 * monitoring for RTSP/local USB/Windows DirectShow, or the existing
 * Snapshot Source monitor). Deliberately does not mention which runtime is
 * underneath, Stage numbers, CUDA, or ONNX in its basic state -- that
 * vocabulary stays inside the collapsed advanced-diagnostics disclosure,
 * which a basic user never needs to open.
 */
export function ObservationControlPanel({
  streamId,
  onOpenCameraSetup,
  onStatus,
}: {
  streamId: string;
  onOpenCameraSetup?: () => void;
  // Lets a caller (e.g. the onboarding wizard's final step) react to
  // `runtime_available` without a second, independently-polled fetch of
  // the same status this panel already owns.
  onStatus?: (status: ObservationSessionStatus | null) => void;
}) {
  const [status, setStatus] = useState<ObservationSessionStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isToggling, setIsToggling] = useState(false);
  const [learningStatus, setLearningStatus] = useState<SceneConfusorLearningStatus | null>(null);
  const [isLearningBusy, setIsLearningBusy] = useState(false);
  // Deliberately its own state, not the primary `error` above: that one
  // replaces this whole panel's body (including the advanced-diagnostics
  // section these two actions live in) when set -- a failed toggle/reset
  // must never hide the very controls a user would retry from.
  const [learningError, setLearningError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const next = await apiClient.getStreamObservationStatus(streamId);
      if (mountedRef.current) {
        setStatus(next);
        setError(null);
        onStatus?.(next);
      }
    } catch {
      if (mountedRef.current) {
        setError("Observation status could not be read. The last known state is still shown.");
      }
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
    // `onStatus` must be a stable (e.g. useCallback-memoized) reference from
    // the caller -- an inline arrow here would retrigger the effect below on
    // every render and restart the poll loop.
  }, [streamId, onStatus]);

  useEffect(() => {
    mountedRef.current = true;
    setStatus(null);
    setIsLoading(true);
    void refresh();
    const interval = window.setInterval(() => void refresh(), POLL_INTERVAL_MS);
    return () => {
      mountedRef.current = false;
      window.clearInterval(interval);
    };
  }, [refresh]);

  const refreshLearningStatus = useCallback(async () => {
    try {
      const next = await apiClient.getSceneConfusorLearningStatus(streamId);
      if (mountedRef.current) setLearningStatus(next);
    } catch {
      // Advanced-diagnostics-only: a failed read here should never disturb
      // the primary Start/Stop control above it.
    }
  }, [streamId]);

  useEffect(() => {
    // Read once per Stream, not on the 3s live-status poll -- this reflects
    // reviewed activity, which changes on a review action, not every frame.
    setLearningStatus(null);
    void refreshLearningStatus();
  }, [refreshLearningStatus]);

  async function toggleLearningEnabled() {
    if (!learningStatus) return;
    setIsLearningBusy(true);
    setLearningError(null);
    try {
      const next = await apiClient.setSceneConfusorLearningEnabled(streamId, !learningStatus.reviewed_evidence_enabled);
      setLearningStatus(next);
    } catch {
      setLearningError("Could not update local adjustment. Try again in a moment.");
    } finally {
      setIsLearningBusy(false);
    }
  }

  async function resetLearning() {
    setIsLearningBusy(true);
    setLearningError(null);
    try {
      const next = await apiClient.resetSceneConfusorLearning(streamId);
      setLearningStatus(next);
    } catch {
      setLearningError("Could not reset local learning. Try again in a moment.");
    } finally {
      setIsLearningBusy(false);
    }
  }

  async function start() {
    setIsToggling(true);
    setError(null);
    try {
      const next = await apiClient.startStreamObservation(streamId);
      setStatus(next);
    } catch {
      setError("Could not start observing. Check the camera and try again.");
    } finally {
      setIsToggling(false);
    }
  }

  async function stop() {
    setIsToggling(true);
    setError(null);
    try {
      const next = await apiClient.stopStreamObservation(streamId);
      setStatus(next);
    } catch {
      setError("Could not stop observing. Try again in a moment.");
    } finally {
      setIsToggling(false);
    }
  }

  async function retryNow() {
    setIsToggling(true);
    setError(null);
    try {
      await apiClient.retryStreamMonitoring(streamId, {
        idempotency_key: randomIdempotencyKey("observation-retry"),
      });
      await refresh();
    } catch {
      setError("Could not retry. Try again in a moment.");
    } finally {
      setIsToggling(false);
    }
  }

  const observing = status?.observing ?? false;
  const busy = status?.state === "starting" || status?.state === "stopping";
  const needsAttention = status?.state === "needs_attention";
  const showStop = Boolean(status?.runtime_available) && (observing || busy || Boolean(status?.retry_action));
  const showStart = Boolean(status?.runtime_available) && !showStop && !needsAttention;

  return (
    <section className="panel observation-control-panel" aria-label="Wildlife observation">
      <div className="section-heading">
        <div>
          <h2>Observation</h2>
          <span className="meta-text">Start or stop MockingBird watching this camera for wildlife</span>
        </div>
        <StatusPill label={stateLabel(status)} tone={statusTone(status)} />
      </div>
      {isLoading ? (
        <span className="meta-text">Reading observation status…</span>
      ) : error ? (
        <div className="continuity-message is-error">
          <strong>{error}</strong>
        </div>
      ) : status ? (
        <>
          {!status.runtime_available ? (
            <div className="continuity-message">
              <span>{status.message}</span>
            </div>
          ) : (
            <>
              <p className="observation-status-message">{status.message}</p>
              <div className="monitoring-continuity-facts">
                {status.state !== "observing" ? (
                  <span>
                    <strong>Camera</strong> {status.camera_connected ? "Healthy" : "Needs attention"}
                  </span>
                ) : null}
                {/* Camera and Observation are reported separately -- a
                    successfully paired, reachable camera must never read
                    "Needs attention" merely because the *Observation*
                    runtime (model bundle, GPU/CUDA) is what actually failed
                    to start, and vice versa. */}
                {status.state !== "observing" ? (
                  <span>
                    <strong>Observation</strong> {status.engine_available ? "Ready" : "Needs attention"}
                  </span>
                ) : null}
                {status.last_useful_frame_at ? (
                  <span>
                    <strong>Last activity</strong> {formatDateTime(status.last_useful_frame_at)}
                  </span>
                ) : null}
                {status.started_at && status.state === "observing" ? (
                  <span>
                    <strong>Started</strong> {formatDateTime(status.started_at)}
                  </span>
                ) : null}
              </div>
              {needsAttention ? (
                // Product Operations & First-Observation Completion v1:
                // this used to always read `status.camera_message`,
                // regardless of which subsystem actually failed -- for a
                // connected camera whose *engine* (detector/GPU/model)
                // failed to load, it showed the reassuring "Camera Node is
                // paired and configured." right below the real failure
                // text this same panel's own top-line `status.message`
                // already, correctly, displays (see `_EngineSession.
                // snapshot`'s "headline whichever subsystem is actually
                // blocking" precedence, engine_runtime.py). Reusing
                // `status.message` here -- already resolved with that
                // exact precedence -- fixes the engine-failure case and
                // leaves the camera-failure case unchanged (there,
                // `status.message` already equals `status.camera_message`).
                <div className="continuity-message">
                  <span>{status.message}</span>
                </div>
              ) : null}
              {status.counts.proposals_observed > 0 && status.counts.candidates_created === 0 ? (
                <div className="continuity-message">
                  <span>
                    MockingBird saw activity but couldn't capture a clear enough moment to bring to
                    Review Queue yet. That's expected on a quiet or distant scene, not an error.
                  </span>
                </div>
              ) : null}
              {status.candidate_authority_exhausted ? (
                <div className="continuity-message">
                  <span>
                    {status.candidate_authority_message ??
                      "This session has reached its automatic Visit-creation limit for the recent " +
                        "activity period. New Visit creation will automatically resume on its own " +
                        "as that period rolls forward -- no restart is needed."}
                  </span>
                </div>
              ) : null}
            </>
          )}
          <div className="panel-actions">
            {showStop ? (
              <button
                className="secondary-button"
                disabled={isToggling || status.state === "stopping"}
                onClick={() => void stop()}
                type="button"
              >
                {status.state === "stopping"
                  ? "Stopping…"
                  : status.state === "starting"
                    ? "Cancel starting"
                    : "Stop observing"}
              </button>
            ) : null}
            {showStart ? (
              <button className="primary-button" disabled={isToggling} onClick={() => void start()} type="button">
                Start observing
              </button>
            ) : null}
            {needsAttention && status.retry_action ? (
              <button className="secondary-button" disabled={isToggling} onClick={() => void retryNow()} type="button">
                Retry now
              </button>
            ) : null}
            {needsAttention && status.setup_action === "edit_camera_setup" && onOpenCameraSetup ? (
              <button className="text-action" onClick={onOpenCameraSetup} type="button">
                Edit camera setup
              </button>
            ) : null}
          </div>
          <details className="review-diagnostic-details">
            <summary>Advanced diagnostics</summary>
            <div className="review-diagnostic-grid">
              <span>Wildlife moments found: {status.counts.candidates_created}</span>
              <span>Activity seen: {status.counts.proposals_observed}</span>
              <span>Not clear enough to review: {status.counts.candidates_suppressed}</span>
              {Object.entries(status.advanced)
                .filter(([, value]) => value !== null && value !== undefined && value !== "")
                .map(([key, value]) => (
                  <span key={key}>
                    {ADVANCED_LABELS[key] ?? formatLabel(key)}: {formatLabel(String(value))}
                  </span>
                ))}
              {status.stopped_reason ? <span>Last stop reason: {formatLabel(status.stopped_reason)}</span> : null}
            </div>
            {status.counts.suppressed_reasons.length > 0 ? (
              <div className="review-diagnostic-grid">
                {status.counts.suppressed_reasons.map(([reason, count]) => (
                  <span key={reason}>
                    {SUPPRESSED_REASON_LABELS[reason] ?? formatLabel(reason)}: {count}
                  </span>
                ))}
              </div>
            ) : null}
            <div className="review-diagnostic-grid">
              <span>Local learning: {learningStatusLabel(learningStatus)}</span>
              {learningStatus && learningStatus.regions_with_reviewed_evidence > 0 ? (
                <span>Reviewed examples supporting it: {learningStatus.regions_with_reviewed_evidence}</span>
              ) : null}
            </div>
            {learningStatus ? (
              <div className="button-row">
                <button className="text-action" type="button" disabled={isLearningBusy} onClick={() => void toggleLearningEnabled()}>
                  {learningStatus.reviewed_evidence_enabled ? "Disable local adjustment" : "Enable local adjustment"}
                </button>
                <button className="text-action" type="button" disabled={isLearningBusy} onClick={() => void resetLearning()}>
                  Reset local learning
                </button>
              </div>
            ) : null}
            {learningError ? <span className="meta-text">{learningError}</span> : null}
          </details>
        </>
      ) : null}
    </section>
  );
}
