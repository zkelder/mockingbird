import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type { CameraSource, SourceConnectionStatus, Stream } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatLabel } from "../utils";

interface StreamsPageProps {
  streams: Stream[];
  sources: CameraSource[];
  onOpenStream: (streamId: string) => void;
}

function connectionTone(status: SourceConnectionStatus["status"]): "good" | "review" | "quiet" {
  if (status === "demo" || status === "configured") {
    return "good";
  }
  if (status === "not_configured" || status === "unavailable") {
    return "review";
  }
  return "quiet";
}

export function StreamsPage({ streams, sources, onOpenStream }: StreamsPageProps) {
  const sourceNames = new Map(sources.map((source) => [source.id, source.name]));
  const [connectionStatuses, setConnectionStatuses] = useState<Record<string, SourceConnectionStatus>>({});
  const [connectionError, setConnectionError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadConnectionStatuses() {
      if (sources.length === 0) {
        setConnectionStatuses({});
        setConnectionError(null);
        return;
      }

      setConnectionError(null);
      try {
        const entries = await Promise.all(
          sources.map(async (source) => [
            source.id,
            await apiClient.getSourceConnectionStatus(source.id),
          ] as const),
        );
        if (isMounted) {
          setConnectionStatuses(Object.fromEntries(entries));
        }
      } catch (caught) {
        if (isMounted) {
          setConnectionError(
            caught instanceof Error ? caught.message : "Could not load source connection status.",
          );
        }
      }
    }

    void loadConnectionStatuses();

    return () => {
      isMounted = false;
    };
  }, [sources]);

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Stream-first workspace"
        title="Streams"
        description="Open a stream to draw zones, inspect outdoor events, and start the review loop."
      />
      {sources.length > 0 ? (
        <section className="source-connection-section">
          <div className="section-heading">
            <h2>Source connection</h2>
            <span className="meta-text">Provider readiness for stream playback</span>
          </div>
          {connectionError ? <div className="error-panel">{connectionError}</div> : null}
          <div className="source-connection-grid">
            {sources.map((source) => {
              const connection = connectionStatuses[source.id];
              const sourceStreams = streams.filter((stream) => stream.source_id === source.id);
              const livePlaybackLabel = connection
                ? connection.supports_live_playback
                  ? "Supported"
                  : "Not available"
                : "Loading";
              const zoneEditingLabel = connection
                ? connection.supports_zone_editing
                  ? "Available"
                  : "Unavailable"
                : "Loading";
              return (
                <section className="source-connection-card" key={source.id}>
                  <div className="item-title-row">
                    <h3>{source.name}</h3>
                    {connection ? (
                      <StatusPill
                        label={formatLabel(connection.status)}
                        tone={connectionTone(connection.status)}
                      />
                    ) : (
                      <StatusPill label="Loading" tone="quiet" />
                    )}
                  </div>
                  <p>{connection?.message ?? source.description}</p>
                  <div className="source-connection-meta">
                    <span>{connection?.stream_ids.length ?? sourceStreams.length} streams</span>
                    <span>Live playback: {livePlaybackLabel}</span>
                    <span>Zone editing: {zoneEditingLabel}</span>
                  </div>
                  {connection?.setup_hint ? (
                    <span className="meta-text">{connection.setup_hint}</span>
                  ) : null}
                </section>
              );
            })}
          </div>
        </section>
      ) : null}
      <div className="stream-list">
        {streams.length > 0 ? (
          streams.map((stream) => (
            <section className="stream-list-item" key={stream.id}>
              <div>
                <div className="item-title-row">
                  <h2>{stream.name}</h2>
                  <StatusPill
                    label={stream.is_live ? "Demo live" : "Offline"}
                    tone={stream.is_live ? "good" : "quiet"}
                  />
                </div>
                <p>{stream.description}</p>
                <span className="meta-text">
                  Source: {sourceNames.get(stream.source_id) ?? stream.source_id}
                </span>
              </div>
              <button className="primary-action" onClick={() => onOpenStream(stream.id)}>
                Open stream
              </button>
            </section>
          ))
        ) : (
          <EmptyState
            title="No streams available"
            description="Streams will become the center of review once a source is connected."
          />
        )}
      </div>
    </div>
  );
}
