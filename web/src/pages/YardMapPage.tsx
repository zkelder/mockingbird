import {
  useEffect,
  useMemo,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { apiClient } from "../api/client";
import type {
  ActivityLibraryFilters,
  YardMapAreaPoint,
  YardMapRange,
  YardMapResponse,
  YardMapStreamItem,
  YardMapZoneItem,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime } from "../utils";

interface YardMapPageProps {
  onOpenStream: (streamId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenFastReview: (visitIds: string[]) => void;
  onOpenActivityLibrary: (filters: ActivityLibraryFilters) => void;
  onOpenBirdLog: (label: string) => void;
}

function idempotencyKey(): string {
  return `yard-map-${crypto.randomUUID()}`;
}

function wedgePath(heading: number, fieldOfView: number, scale = 1): string {
  const radius = 23 * scale;
  const radians = (degrees: number) => ((degrees - 90) * Math.PI) / 180;
  const point = (degrees: number) =>
    `${(Math.cos(radians(degrees)) * radius).toFixed(2)} ${(Math.sin(radians(degrees)) * radius).toFixed(2)}`;
  const start = heading - fieldOfView / 2;
  const end = heading + fieldOfView / 2;
  return `M 0 0 L ${point(start)} A ${radius} ${radius} 0 ${fieldOfView > 180 ? 1 : 0} 1 ${point(end)} Z`;
}

function zoneTone(zone: YardMapZoneItem): "good" | "review" | "quiet" {
  if (zone.zone_type === "privacy") return "review";
  if (zone.zone_type === "ignore") return "quiet";
  return "good";
}

function cameraHealthLabel(stream: YardMapStreamItem): string {
  return {
    healthy: "Healthy",
    recovering: "Recovering",
    camera_unavailable: "Unavailable",
    no_recent_frame: "Unavailable",
    evidence_storage_degraded: "Unavailable",
    waiting_for_capacity: "Waiting",
    stopped: "Stopped",
    starting: "Starting",
    setup_incomplete: "Unavailable",
  }[stream.activity.camera_health_state];
}

function cameraHealthTone(stream: YardMapStreamItem): "good" | "review" | "quiet" {
  if (stream.activity.camera_health_state === "healthy") return "good";
  if (["stopped", "starting"].includes(stream.activity.camera_health_state)) return "quiet";
  return "review";
}

function normalizedPoint(event: ReactPointerEvent<HTMLElement>): YardMapAreaPoint {
  const bounds = event.currentTarget.getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)),
    y: Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height)),
  };
}

export function YardMapPage({
  onOpenStream,
  onOpenVisit,
  onOpenFastReview,
  onOpenActivityLibrary,
  onOpenBirdLog,
}: YardMapPageProps) {
  const [data, setData] = useState<YardMapResponse | null>(null);
  const [range, setRange] = useState<YardMapRange>("today");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [editing, setEditing] = useState(true);
  const [showCameras, setShowCameras] = useState(true);
  const [showZones, setShowZones] = useState(true);
  const [showRecentActivity, setShowRecentActivity] = useState(true);
  const [showNeedsReview, setShowNeedsReview] = useState(true);
  const [showConfirmed, setShowConfirmed] = useState(true);
  const [showNonBird, setShowNonBird] = useState(true);
  const [selectedStreamId, setSelectedStreamId] = useState<string | null>(null);
  const [dragging, setDragging] = useState<{ kind: "stream" | "zone"; id: string } | null>(null);
  const [drawingZoneId, setDrawingZoneId] = useState<string | null>(null);
  const [areaDraft, setAreaDraft] = useState<YardMapAreaPoint[]>([]);

  const selectedStream = useMemo(
    () => data?.streams.find((stream) => stream.id === selectedStreamId) ?? null,
    [data, selectedStreamId],
  );
  const drawingZone = useMemo(
    () => data?.zones.find((zone) => zone.id === drawingZoneId) ?? null,
    [data, drawingZoneId],
  );

  async function refresh(nextRange = range) {
    setIsLoading(true);
    setError(null);
    try {
      setData(await apiClient.getYardMap(nextRange));
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Could not refresh the Yard Map. The last successful view is still shown.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void refresh(range);
  }, [range]);

  function apply(next: YardMapResponse, notice: string) {
    setData(next);
    setMessage(notice);
    setError(null);
  }

  async function createBlank() {
    try {
      apply(
        await apiClient.createBlankYardMap({ idempotency_key: idempotencyKey() }),
        "Blank local canvas created. Camera positions remain approximate context.",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create the blank Yard Map.");
    }
  }

  async function uploadBackground(file: File | undefined) {
    if (!file) return;
    try {
      apply(
        await apiClient.uploadYardMapBackground(
          file,
          data?.map?.state_token ?? null,
          idempotencyKey(),
        ),
        "Local yard image saved. It is protected configuration media, not Visit evidence.",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save that local yard image.");
    }
  }

  async function removeBackground() {
    if (
      !data?.map ||
      !window.confirm("Remove the local yard image? Camera and Zone placements stay on the blank canvas.")
    ) {
      return;
    }
    try {
      apply(
        await apiClient.removeYardMapBackground({
          expected_state_token: data.map.state_token,
          idempotency_key: idempotencyKey(),
        }),
        "Background removed. Placements remain on the blank canvas.",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not remove the yard image.");
    }
  }

  async function saveStream(
    stream: YardMapStreamItem,
    patch: Partial<NonNullable<YardMapStreamItem["placement"]>>,
  ) {
    const placement = stream.placement;
    if (!placement) return;
    try {
      apply(
        await apiClient.updateYardMapStreamPlacement(stream.id, {
          x: patch.x ?? placement.x,
          y: patch.y ?? placement.y,
          heading_degrees: patch.heading_degrees ?? placement.heading_degrees,
          field_of_view_degrees: patch.field_of_view_degrees ?? placement.field_of_view_degrees,
          display_scale: patch.display_scale ?? placement.display_scale ?? null,
          expected_state_token: placement.state_token,
          idempotency_key: idempotencyKey(),
        }),
        `Saved approximate position for ${stream.name}.`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save this camera placement.");
    }
  }

  async function placeStream(stream: YardMapStreamItem) {
    try {
      apply(
        await apiClient.updateYardMapStreamPlacement(stream.id, {
          x: 0.5,
          y: 0.5,
          heading_degrees: 0,
          field_of_view_degrees: 70,
          display_scale: 1,
          idempotency_key: idempotencyKey(),
        }),
        `Placed ${stream.name} at the canvas center. Drag or use the controls to refine it.`,
      );
      setSelectedStreamId(stream.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not place this camera.");
    }
  }

  async function removeStream(stream: YardMapStreamItem) {
    if (
      !stream.placement ||
      !window.confirm(`Remove ${stream.name} from this map? The Stream is unchanged.`)
    ) {
      return;
    }
    try {
      apply(
        await apiClient.removeYardMapStreamPlacement(stream.id, {
          expected_state_token: stream.placement.state_token,
          idempotency_key: idempotencyKey(),
        }),
        `Removed ${stream.name} from the map. The Stream remains configured.`,
      );
      setSelectedStreamId(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not remove this camera from the map.");
    }
  }

  async function placeZone(zone: YardMapZoneItem) {
    try {
      apply(
        await apiClient.updateYardMapZonePlacement(zone.id, {
          x: 0.5,
          y: 0.5,
          idempotency_key: idempotencyKey(),
        }),
        `Placed ${zone.name} as map context. Its Stream image-space Zone is unchanged.`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not place this Zone.");
    }
  }

  async function saveZone(
    zone: YardMapZoneItem,
    x: number,
    y: number,
    area: YardMapAreaPoint[] | null | undefined = undefined,
  ) {
    if (!zone.placement) return;
    try {
      apply(
        await apiClient.updateYardMapZonePlacement(zone.id, {
          x,
          y,
          area: area === undefined ? zone.placement.area ?? null : area,
          expected_state_token: zone.placement.state_token,
          idempotency_key: idempotencyKey(),
        }),
        `Saved map context for ${zone.name}.`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save this Zone anchor.");
    }
  }

  async function removeZone(zone: YardMapZoneItem) {
    if (
      !zone.placement ||
      !window.confirm(`Remove ${zone.name} from this map? Its Stream image-space Zone is unchanged.`)
    ) {
      return;
    }
    try {
      apply(
        await apiClient.removeYardMapZonePlacement(zone.id, {
          expected_state_token: zone.placement.state_token,
          idempotency_key: idempotencyKey(),
        }),
        `Removed ${zone.name} from the map. Its image-space Zone is unchanged.`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not remove this Zone anchor.");
    }
  }

  function finishDrag(event: ReactPointerEvent<HTMLDivElement>) {
    if (!dragging || !data || drawingZoneId) return;
    const point = normalizedPoint(event);
    setDragging(null);
    if (dragging.kind === "stream") {
      const stream = data.streams.find((item) => item.id === dragging.id);
      if (stream) void saveStream(stream, point);
      return;
    }
    const zone = data.zones.find((item) => item.id === dragging.id);
    if (zone) void saveZone(zone, point.x, point.y);
  }

  function addAreaPoint(event: ReactPointerEvent<HTMLDivElement>) {
    if (!drawingZoneId) return;
    const point = normalizedPoint(event);
    setAreaDraft((draft) => (draft.length >= 12 ? draft : [...draft, point]));
  }

  function startAreaDrawing(zone: YardMapZoneItem) {
    if (!zone.placement) return;
    setDrawingZoneId(zone.id);
    setAreaDraft(zone.placement.area ?? []);
    setMessage(`Click at least three points on the map to draw approximate context for ${zone.name}.`);
  }

  function cancelAreaDrawing() {
    setDrawingZoneId(null);
    setAreaDraft([]);
  }

  function saveAreaDrawing() {
    if (!drawingZone?.placement || areaDraft.length < 3) return;
    void saveZone(drawingZone, drawingZone.placement.x, drawingZone.placement.y, areaDraft);
    cancelAreaDrawing();
  }

  if (!data) {
    return (
      <div className="page-stack">
        <PageHeader
          eyebrow="Yard & Camera Map"
          title="Yard & Camera Map"
          description="Loading local camera context without using an address, GPS, cloud upload, or automatic calibration."
        />
        <section className="panel yard-map-load-state">
          <span>{error ?? (isLoading ? "Loading the local Yard Map…" : "The Yard Map is currently unavailable.")}</span>
          {error ? <button className="secondary-action" onClick={() => void refresh()} type="button">Retry</button> : null}
        </section>
      </div>
    );
  }

  if (!data.map) {
    return (
      <div className="page-stack">
        <PageHeader
          eyebrow="Yard & Camera Map"
          title="Set up a local yard map"
          description="Place approximate camera and Zone context without an address, GPS, cloud upload, or automatic calibration."
        />
        {error ? <div className="error-panel"><strong>Could not refresh the Yard Map.</strong><span>{error}</span></div> : null}
        <section className="panel yard-map-setup">
          <EmptyState
            title="No Yard Map yet"
            description="Start with a blank local canvas or upload one bounded JPEG, PNG, or WebP yard image. It stays on this device."
            action={
              <div className="yard-map-setup-actions">
                <button className="primary-action" onClick={() => void createBlank()} type="button">
                  Start with blank canvas
                </button>
                <label className="secondary-action">
                  Upload yard image
                  <input
                    accept="image/jpeg,image/png,image/webp"
                    aria-label="Upload local yard image"
                    hidden
                    onChange={(event) => void uploadBackground(event.target.files?.[0])}
                    type="file"
                  />
                </label>
              </div>
            }
          />
        </section>
      </div>
    );
  }

  const map = data.map;
  const placedStreamCount = data.streams.filter((stream) => stream.placement).length;

  return (
    <div className="page-stack yard-map-page">
      <PageHeader
        eyebrow="Yard & Camera Map"
        title="Yard & Camera Map"
        description="Approximate local context only. It does not calibrate cameras, infer coverage, change Zones, or create reviewed truth."
        actions={
          <>
            <button className="secondary-action" onClick={() => setEditing((value) => !value)} type="button">
              {editing ? "View map" : "Edit map"}
            </button>
            <button className="secondary-action" onClick={() => void refresh()} type="button">
              Refresh
            </button>
          </>
        }
      />

      <section className="panel yard-map-toolbar" aria-label="Yard Map filters">
        <label>
          Recent activity
          <select value={range} onChange={(event) => setRange(event.target.value as YardMapRange)}>
            <option value="today">Today</option>
            <option value="last_24_hours">Last 24 hours</option>
            <option value="last_7_days">Last 7 days</option>
          </select>
        </label>
        <label><input checked={showCameras} onChange={(event) => setShowCameras(event.target.checked)} type="checkbox" /> Cameras</label>
        <label><input checked={showZones} onChange={(event) => setShowZones(event.target.checked)} type="checkbox" /> Zones</label>
        <label><input checked={showRecentActivity} onChange={(event) => setShowRecentActivity(event.target.checked)} type="checkbox" /> Recent activity</label>
        <label><input checked={showNeedsReview} onChange={(event) => setShowNeedsReview(event.target.checked)} type="checkbox" /> Needs review</label>
        <label><input checked={showConfirmed} onChange={(event) => setShowConfirmed(event.target.checked)} type="checkbox" /> Confirmed wildlife</label>
        <label><input checked={showNonBird} onChange={(event) => setShowNonBird(event.target.checked)} type="checkbox" /> Non-bird activity</label>
      </section>

      {error ? <div className="error-panel"><strong>Yard Map refresh or save failed.</strong><span>{error}</span></div> : null}
      {message ? <div className="notice-panel" role="status">{message}</div> : null}
      {data.warnings.map((warning) => <div className="notice-panel" key={warning}>{warning}</div>)}

      <div className="yard-map-layout">
        <section className="panel yard-map-stage-panel">
          <div
            aria-label={drawingZoneId ? "Draw approximate Zone context" : "Yard Map canvas"}
            className={drawingZoneId ? "yard-map-stage is-drawing" : "yard-map-stage"}
            onClick={addAreaPoint}
            onPointerUp={finishDrag}
            style={{ aspectRatio: `${map.canvas_width} / ${map.canvas_height}` }}
          >
            {map.background ? (
              <img
                alt="Local yard map background"
                className="yard-map-background"
                onError={() => setError("The local yard image could not be loaded. Placements remain available on the blank canvas.")}
                src={`${apiClient.baseUrl}${map.background.preview_url}`}
              />
            ) : <div aria-label="Blank local Yard Map canvas" className="yard-map-blank" />}

            {showZones ? (
              <svg aria-hidden="true" className="yard-map-zone-areas" viewBox="0 0 100 100" preserveAspectRatio="none">
                {data.zones.filter((zone) => zone.placement?.area).map((zone) => (
                  <polygon
                    className={`yard-map-zone-area zone-${zone.zone_type}`}
                    key={zone.id}
                    points={(zone.placement?.area ?? []).map((point) => `${point.x * 100},${point.y * 100}`).join(" ")}
                  />
                ))}
                {drawingZoneId && areaDraft.length > 0 ? (
                  <polyline className="yard-map-zone-area-draft" points={areaDraft.map((point) => `${point.x * 100},${point.y * 100}`).join(" ")} />
                ) : null}
              </svg>
            ) : null}

            {showCameras ? data.streams.filter((stream) => stream.placement).map((stream) => (
              <div
                className="yard-map-camera"
                key={stream.id}
                style={{ left: `${stream.placement!.x * 100}%`, top: `${stream.placement!.y * 100}%` }}
              >
                <svg aria-hidden="true" className="yard-map-wedge" viewBox="-28 -28 56 56">
                  <path d={wedgePath(stream.placement!.heading_degrees, stream.placement!.field_of_view_degrees, stream.placement!.display_scale ?? 1)} />
                </svg>
                <button
                  aria-label={`${stream.name} camera marker`}
                  className="yard-map-marker"
                  onClick={() => editing ? setSelectedStreamId(stream.id) : onOpenStream(stream.id)}
                  onKeyDown={(event) => {
                    if (!editing || !stream.placement) return;
                    const delta = 0.02;
                    if (event.key === "ArrowLeft") { event.preventDefault(); void saveStream(stream, { x: Math.max(0, stream.placement.x - delta) }); }
                    if (event.key === "ArrowRight") { event.preventDefault(); void saveStream(stream, { x: Math.min(1, stream.placement.x + delta) }); }
                    if (event.key === "ArrowUp") { event.preventDefault(); void saveStream(stream, { y: Math.max(0, stream.placement.y - delta) }); }
                    if (event.key === "ArrowDown") { event.preventDefault(); void saveStream(stream, { y: Math.min(1, stream.placement.y + delta) }); }
                  }}
                  onPointerDown={(event) => {
                    if (editing && !drawingZoneId) {
                      event.stopPropagation();
                      event.currentTarget.setPointerCapture(event.pointerId);
                      setDragging({ kind: "stream", id: stream.id });
                    }
                  }}
                  type="button"
                >
                  Camera
                </button>
                <button
                  aria-label={`Open ${stream.name} camera health`}
                  className="text-action yard-map-health-indicator"
                  onClick={() => onOpenStream(stream.id)}
                  onPointerDown={(event) => event.stopPropagation()}
                  type="button"
                >
                  {cameraHealthLabel(stream)}
                </button>
                {showRecentActivity && stream.activity.latest_preview_url ? (
                  <img
                    alt={`Latest safe Visit preview for ${stream.name}`}
                    className="yard-map-visit-preview"
                    onClick={() => stream.activity.latest_visit_id && onOpenVisit(stream.activity.latest_visit_id)}
                    onError={(event) => {
                      event.currentTarget.hidden = true;
                      setMessage(`The latest Visit preview for ${stream.name} is unavailable. The Visit link remains available.`);
                    }}
                    src={`${apiClient.baseUrl}${stream.activity.latest_preview_url}`}
                  />
                ) : null}
              </div>
            )) : null}

            {showZones ? data.zones.filter((zone) => zone.placement).map((zone) => (
              <button
                aria-label={`${zone.name} ${zone.zone_type} map anchor`}
                className={`yard-map-zone zone-${zone.zone_type}`}
                key={zone.id}
                onClick={() => {
                  if (!editing && !drawingZoneId) onOpenStream(zone.stream_id);
                }}
                onPointerDown={(event) => {
                  if (editing && !drawingZoneId) {
                    event.stopPropagation();
                    event.currentTarget.setPointerCapture(event.pointerId);
                    setDragging({ kind: "zone", id: zone.id });
                  }
                }}
                style={{ left: `${zone.placement!.x * 100}%`, top: `${zone.placement!.y * 100}%` }}
                type="button"
              >
                <span>{zone.zone_type}</span>
                <strong>{zone.name}</strong>
              </button>
            )) : null}

            {placedStreamCount === 0 && data.streams.length > 0 ? (
              <div className="yard-map-stage-message">Place a configured camera from the side panel to add it here.</div>
            ) : null}
          </div>
          <p className="meta-text">
            Camera wedges and Zone anchors are user-authored approximate context. They do not alter image-space detection Zones.
          </p>
        </section>

        <aside className="yard-map-side-panel">
          {drawingZone ? (
            <section className="panel yard-map-draw-panel">
              <h2>Draw approximate area</h2>
              <p className="meta-text">Click three to twelve points on the map for {drawingZone.name}. This is user-authored context, not image-space detection geometry.</p>
              <span>{areaDraft.length} points selected</span>
              <div className="action-row">
                <button className="primary-action" disabled={areaDraft.length < 3} onClick={saveAreaDrawing} type="button">Save approximate area</button>
                <button className="secondary-action" onClick={cancelAreaDrawing} type="button">Cancel</button>
              </div>
            </section>
          ) : null}

          <section className="panel">
            <h2>Cameras</h2>
            {data.streams.length === 0 ? <p className="meta-text">No active configured Streams yet.</p> : data.streams.map((stream) => (
              <div className="yard-map-list-item" key={stream.id}>
                <strong>{stream.name}</strong>
                <span>{stream.source_name}</span>
                <StatusPill label={cameraHealthLabel(stream)} tone={cameraHealthTone(stream)} />
                <span className="meta-text">{stream.activity.monitoring_desired_state} / {stream.activity.monitoring_actual_state}</span>
                {stream.activity.open_activity_session ? <StatusPill label="Open activity" tone="review" /> : null}
                {editing && !stream.placement ? <button className="secondary-action" onClick={() => void placeStream(stream)} type="button">Place on map</button> : null}
                <button className="text-action" onClick={() => onOpenStream(stream.id)} type="button">Open Stream</button>
                {showNeedsReview && stream.activity.needs_review_count > 0 ? <button className="text-action" onClick={() => onOpenFastReview(stream.activity.needs_review_visit_ids)} type="button">{stream.activity.needs_review_count} needs review</button> : null}
                {showRecentActivity && stream.activity.latest_visit_at ? <button className="text-action" onClick={() => stream.activity.latest_visit_id && onOpenVisit(stream.activity.latest_visit_id)} type="button">Latest: {formatDateTime(stream.activity.latest_visit_at)}</button> : null}
                {showConfirmed && stream.activity.latest_confirmed_label ? <button className="text-action" onClick={() => onOpenBirdLog(stream.activity.latest_confirmed_label!)} type="button">Confirmed: {stream.activity.latest_confirmed_label}</button> : null}
                {showNonBird ? <button className="text-action" onClick={() => onOpenActivityLibrary({ stream_id: stream.id, review_filter: "non_bird" })} type="button">Non-bird activity</button> : null}
              </div>
            ))}
          </section>

          {editing && selectedStream?.placement ? (
            <section className="panel yard-map-edit-panel">
              <h2>Edit {selectedStream.name}</h2>
              <label>Direction
                <input max="359" min="0" onChange={(event) => void saveStream(selectedStream, { heading_degrees: Number(event.target.value) })} type="range" value={selectedStream.placement.heading_degrees} />
                <span>{Math.round(selectedStream.placement.heading_degrees)}°</span>
              </label>
              <label>Approximate field of view
                <input max="180" min="10" onChange={(event) => void saveStream(selectedStream, { field_of_view_degrees: Number(event.target.value) })} type="range" value={selectedStream.placement.field_of_view_degrees} />
                <span>{Math.round(selectedStream.placement.field_of_view_degrees)}°</span>
              </label>
              <p className="meta-text">This wedge is not a physical measurement, calibration, visibility guarantee, or species-identification range.</p>
              <button className="text-action destructive-action" onClick={() => void removeStream(selectedStream)} type="button">Remove from map</button>
            </section>
          ) : null}

          <section className="panel">
            <h2>Zone context</h2>
            <p className="meta-text">Anchors and drawn areas are separate from each Stream’s image-space Zone geometry.</p>
            {data.zones.length === 0 ? <p className="meta-text">No active Zones are configured.</p> : data.zones.map((zone) => (
              <div className="yard-map-list-item" key={zone.id}>
                <StatusPill label={zone.zone_type} tone={zoneTone(zone)} />
                <strong>{zone.name}</strong>
                {editing && !zone.placement ? <button className="text-action" onClick={() => void placeZone(zone)} type="button">Place anchor</button> : null}
                {editing && zone.placement ? <button className="text-action" onClick={() => startAreaDrawing(zone)} type="button">{zone.placement.area ? "Edit approximate area" : "Draw approximate area"}</button> : null}
                <button className="text-action" onClick={() => onOpenStream(zone.stream_id)} type="button">Open Stream Zone</button>
                {editing && zone.placement ? <button className="text-action destructive-action" onClick={() => void removeZone(zone)} type="button">Remove from map</button> : null}
              </div>
            ))}
          </section>

          {map.background ? (
            <section className="panel">
              <h2>Background</h2>
              <p className="meta-text">Local protected configuration media; it is included in backup and never selected by Visit-media retention.</p>
              {editing ? <button className="text-action destructive-action" onClick={() => void removeBackground()} type="button">Remove background</button> : null}
            </section>
          ) : editing ? (
            <section className="panel">
              <label className="secondary-action">
                Replace blank canvas with yard image
                <input accept="image/jpeg,image/png,image/webp" aria-label="Upload local yard image" hidden onChange={(event) => void uploadBackground(event.target.files?.[0])} type="file" />
              </label>
            </section>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
