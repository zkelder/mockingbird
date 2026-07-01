import type { CameraSource, Stream } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";

interface StreamsPageProps {
  streams: Stream[];
  sources: CameraSource[];
  onOpenStream: (streamId: string) => void;
}

export function StreamsPage({ streams, sources, onOpenStream }: StreamsPageProps) {
  const sourceNames = new Map(sources.map((source) => [source.id, source.name]));

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Stream-first workspace"
        title="Streams"
        description="Open a stream to draw zones, inspect outdoor events, and start the review loop."
      />
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
