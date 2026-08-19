import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "../api/client";
import type { ObservationSessionStatus } from "../api/types";
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
}: {
  streamId: string;
  onOpenCameraSetup?: () => void;
}) {
  const [status, setStatus] = useState<ObservationSessionStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isToggling, setIsToggling] = useState(false);
  const mountedRef = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const next = await apiClient.getStreamObservationStatus(streamId);
      if (mountedRef.current) {
        setStatus(next);
        setError(null);
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
  }, [streamId]);

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
                <div className="continuity-message">
                  <span>{status.camera_message}</span>
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
          </details>
        </>
      ) : null}
    </section>
  );
}
