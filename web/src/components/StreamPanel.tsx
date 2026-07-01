import type { Event, Stream, Zone } from "../api/types";
import { formatLabel } from "../utils";

interface StreamPanelProps {
  stream: Stream;
  zones: Zone[];
  events: Event[];
}

function polygonPoints(zone: Zone): string {
  return zone.polygon.map((point) => `${point.x * 100},${point.y * 100}`).join(" ");
}

function zoneCenter(zone: Zone): { x: number; y: number } {
  const total = zone.polygon.reduce(
    (sum, point) => ({ x: sum.x + point.x, y: sum.y + point.y }),
    { x: 0, y: 0 },
  );
  return {
    x: (total.x / zone.polygon.length) * 100,
    y: (total.y / zone.polygon.length) * 100,
  };
}

export function StreamPanel({ stream, zones, events }: StreamPanelProps) {
  const needsReview = events.filter((event) => event.review_status === "needs_review").length;

  return (
    <section className="stream-panel" aria-label={`${stream.name} stream`}>
      <div className="stream-scene">
        <div className="stream-sky" />
        <div className="stream-tree stream-tree-left" />
        <div className="stream-tree stream-tree-right" />
        <div className="stream-feeder" />
        <div className="stream-ground" />
        <svg className="zone-overlay" viewBox="0 0 100 100" preserveAspectRatio="none">
          {/* Normalized points keep zones aligned as future stream sizes change. */}
          {zones.map((zone) => (
            <polygon
              key={zone.id}
              className={`zone-shape zone-${zone.zone_type}`}
              points={polygonPoints(zone)}
            />
          ))}
        </svg>
        {zones.map((zone) => {
          const center = zoneCenter(zone);
          return (
            <span
              className={`zone-label zone-label-${zone.zone_type}`}
              key={zone.id}
              style={{ left: `${center.x}%`, top: `${center.y}%` }}
            >
              {formatLabel(zone.zone_type)}
            </span>
          );
        })}
      </div>
      <div className="stream-panel-footer">
        <div>
          <strong>{stream.name}</strong>
          <span>{stream.is_live ? "Demo live stream" : "Stream offline"}</span>
        </div>
        <div>
          <strong>{zones.length}</strong>
          <span>zones</span>
        </div>
        <div>
          <strong>{events.length}</strong>
          <span>events</span>
        </div>
        <div>
          <strong>{needsReview}</strong>
          <span>needs review</span>
        </div>
      </div>
    </section>
  );
}
