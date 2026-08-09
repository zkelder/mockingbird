import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "../api/client";
import type { ObservationSessionStatus } from "../api/types";
import { StatusPill } from "./StatusPill";
import { formatDateTime, formatLabel } from "../utils";

const POLL_INTERVAL_MS = 3000;

function stateLabel(status: ObservationSessionStatus | null): string {
  if (!status) return "Not observing";
  switch (status.state) {
    case "observing":
      return "Observing";
    case "starting":
      return "Starting…";
    case "stopping":
      return "Stopping…";
    case "error":
      return "Needs attention";
    default:
      return "Not observing";
  }
}

function statusTone(status: ObservationSessionStatus | null): "good" | "review" | "quiet" {
  if (!status) return "quiet";
  if (status.state === "observing") return "good";
  if (status.state === "error") return "review";
  return "quiet";
}

/**
 * The simple observation control (Product requirement 1): Start/Stop the
 * accepted Observation Engine for one Stream, plus compact camera and
 * engine health. Deliberately does not mention Stage numbers, CUDA, or
 * ONNX -- that vocabulary stays inside the collapsed advanced-diagnostics
 * disclosure, which a basic user never needs to open.
 */
export function ObservationControlPanel({ streamId }: { streamId: string }) {
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

  const observing = status?.observing ?? false;
  const busy = status?.state === "starting" || status?.state === "stopping";

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
          <p className="observation-status-message">{status.message}</p>
          <div className="monitoring-continuity-facts">
            <span>
              <strong>Camera</strong> {status.camera_connected ? "Connected" : status.camera_message}
            </span>
            <span>
              <strong>Observation Engine</strong>{" "}
              {status.engine_available ? "Ready" : status.state === "observing" ? "Ready" : "Not available yet"}
            </span>
            {status.started_at ? (
              <span>
                <strong>Started</strong> {formatDateTime(status.started_at)}
              </span>
            ) : null}
          </div>
          {!status.observing && status.state !== "stopped" && !status.camera_connected ? (
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
          <div className="panel-actions">
            {observing || busy ? (
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
            ) : (
              <button className="primary-button" disabled={isToggling} onClick={() => void start()} type="button">
                Start observing
              </button>
            )}
          </div>
          <details className="review-diagnostic-details">
            <summary>Advanced diagnostics</summary>
            <div className="review-diagnostic-grid">
              <span>Wildlife moments found: {status.counts.candidates_created}</span>
              <span>Activity seen: {status.counts.proposals_observed}</span>
              <span>Not clear enough to review: {status.counts.candidates_suppressed}</span>
              {status.advanced.provider_key ? <span>Provider: {String(status.advanced.provider_key)}</span> : null}
              {status.advanced.detector_provider_key ? (
                <span>Detector: {String(status.advanced.detector_provider_key)}</span>
              ) : null}
              {status.stopped_reason ? <span>Last stop reason: {formatLabel(status.stopped_reason)}</span> : null}
            </div>
            {status.counts.suppressed_reasons.length > 0 ? (
              <div className="review-diagnostic-grid">
                {status.counts.suppressed_reasons.map(([reason, count]) => (
                  <span key={reason}>
                    {formatLabel(reason)}: {count}
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
