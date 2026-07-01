import type { CameraSource, Stream } from "../api/types";
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
      <div className="section-heading">
        <h1>Streams</h1>
      </div>
      <div className="stream-list">
        {streams.map((stream) => (
          <section className="stream-list-item" key={stream.id}>
            <div>
              <div className="item-title-row">
                <h2>{stream.name}</h2>
                <StatusPill label={stream.is_live ? "Demo live" : "Offline"} tone={stream.is_live ? "good" : "quiet"} />
              </div>
              <p>{stream.description}</p>
              <span className="meta-text">{sourceNames.get(stream.source_id) ?? stream.source_id}</span>
            </div>
            <button className="secondary-action" onClick={() => onOpenStream(stream.id)}>
              Open stream
            </button>
          </section>
        ))}
      </div>
    </div>
  );
}
