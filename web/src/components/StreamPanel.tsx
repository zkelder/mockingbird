import type { PointerEvent } from "react";
import type { Event, Point, Stream, Zone } from "../api/types";
import { formatLabel } from "../utils";

interface StreamPanelProps {
  stream: Stream;
  zones: Zone[];
  events: Event[];
  selectedZoneId?: string | null;
  drawMode?: boolean;
  draftPolygon?: Point[] | null;
  onSelectZone?: (zoneId: string) => void;
  onDrawStart?: (point: Point) => void;
  onDrawMove?: (point: Point) => void;
  onDrawEnd?: (point: Point) => void;
}

function polygonPoints(points: Point[]): string {
  return points.map((point) => `${point.x * 100},${point.y * 100}`).join(" ");
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

function pointFromPointer(event: PointerEvent<HTMLElement>): Point {
  const rect = event.currentTarget.getBoundingClientRect();
  const x = (event.clientX - rect.left) / rect.width;
  const y = (event.clientY - rect.top) / rect.height;

  return {
    x: Math.min(1, Math.max(0, x)),
    y: Math.min(1, Math.max(0, y)),
  };
}

export function StreamPanel({
  stream,
  zones,
  events,
  selectedZoneId = null,
  drawMode = false,
  draftPolygon = null,
  onSelectZone,
  onDrawStart,
  onDrawMove,
  onDrawEnd,
}: StreamPanelProps) {
  const needsReview = events.filter((event) => event.review_status === "needs_review").length;

  function handlePointerDown(event: PointerEvent<HTMLElement>) {
    if (!drawMode) {
      return;
    }
    event.currentTarget.setPointerCapture(event.pointerId);
    onDrawStart?.(pointFromPointer(event));
  }

  function handlePointerMove(event: PointerEvent<HTMLElement>) {
    if (!drawMode || event.buttons !== 1) {
      return;
    }
    onDrawMove?.(pointFromPointer(event));
  }

  function handlePointerUp(event: PointerEvent<HTMLElement>) {
    if (!drawMode) {
      return;
    }
    onDrawEnd?.(pointFromPointer(event));
  }

  return (
    <section className="stream-panel" aria-label={`${stream.name} stream`}>
      <div
        className={`stream-scene${drawMode ? " draw-mode" : ""}`}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
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
              className={`zone-shape zone-${zone.zone_type}${
                selectedZoneId === zone.id ? " zone-selected" : ""
              }${zone.is_active ? "" : " zone-inactive"}`}
              points={polygonPoints(zone.polygon)}
              aria-label={`Select ${zone.name}`}
              role="button"
              tabIndex={0}
              onClick={(event) => {
                event.stopPropagation();
                if (!drawMode) {
                  onSelectZone?.(zone.id);
                }
              }}
              onKeyDown={(event) => {
                if (!drawMode && (event.key === "Enter" || event.key === " ")) {
                  event.preventDefault();
                  onSelectZone?.(zone.id);
                }
              }}
            />
          ))}
          {draftPolygon ? (
            <polygon className="zone-shape zone-draft" points={polygonPoints(draftPolygon)} />
          ) : null}
        </svg>
        {zones.map((zone) => {
          const center = zoneCenter(zone);
          return (
            <span
              className={`zone-label zone-label-${zone.zone_type}${
                selectedZoneId === zone.id ? " zone-label-selected" : ""
              }${zone.is_active ? "" : " zone-label-inactive"}`}
              key={zone.id}
              aria-label={`Select ${zone.name}`}
              role="button"
              tabIndex={0}
              style={{ left: `${center.x}%`, top: `${center.y}%` }}
              onClick={() => {
                if (!drawMode) {
                  onSelectZone?.(zone.id);
                }
              }}
              onKeyDown={(event) => {
                if (!drawMode && (event.key === "Enter" || event.key === " ")) {
                  event.preventDefault();
                  onSelectZone?.(zone.id);
                }
              }}
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
          <span>recent events</span>
        </div>
        <div>
          <strong>{needsReview}</strong>
          <span>recent needs review</span>
        </div>
      </div>
    </section>
  );
}
