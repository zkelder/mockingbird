import { useEffect, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type { Event, Point, ReviewQueueItem, Stream, Visit, Zone, ZoneType } from "../api/types";
import { StatusPill } from "../components/StatusPill";
import { StreamPanel } from "../components/StreamPanel";
import { formatDateTime, formatLabel } from "../utils";

interface StreamDetailPageProps {
  streamId: string;
  reviewQueue: ReviewQueueItem[];
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenExports: () => void;
  onOpenReview: () => void;
}

interface StreamDetailState {
  stream: Stream;
  zones: Zone[];
  events: Event[];
  visitsByEvent: Record<string, Visit[]>;
}

const zoneTypeOptions: ZoneType[] = [
  "feeder",
  "birdbath",
  "ground",
  "perch",
  "yard",
  "driveway",
  "privacy",
  "ignore",
];

interface ZoneDraft {
  name: string;
  zone_type: ZoneType;
  is_active: boolean;
}

function rectanglePolygon(start: Point, end: Point): Point[] {
  const left = Math.min(start.x, end.x);
  const right = Math.max(start.x, end.x);
  const top = Math.min(start.y, end.y);
  const bottom = Math.max(start.y, end.y);

  // Rectangular draw is the first foundation for future polygon editing.
  return [
    { x: left, y: top },
    { x: right, y: top },
    { x: right, y: bottom },
    { x: left, y: bottom },
  ];
}

export function StreamDetailPage({
  streamId,
  reviewQueue,
  onOpenEvent,
  onOpenVisit,
  onOpenExports,
  onOpenReview,
}: StreamDetailPageProps) {
  const [detail, setDetail] = useState<StreamDetailState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);
  const [zoneDraft, setZoneDraft] = useState<ZoneDraft | null>(null);
  const [drawMode, setDrawMode] = useState(false);
  const [drawStart, setDrawStart] = useState<Point | null>(null);
  const [draftPolygon, setDraftPolygon] = useState<Point[] | null>(null);
  const [newZoneName, setNewZoneName] = useState("New zone");
  const [newZoneType, setNewZoneType] = useState<ZoneType>("feeder");
  const [zoneMessage, setZoneMessage] = useState<string | null>(null);
  const [zoneError, setZoneError] = useState<string | null>(null);
  const [isSavingZone, setIsSavingZone] = useState(false);

  const selectedZone = detail?.zones.find((zone) => zone.id === selectedZoneId) ?? null;

  useEffect(() => {
    let isMounted = true;

    async function loadStreamDetail() {
      setIsLoading(true);
      setError(null);
      setZoneError(null);
      setZoneMessage(null);
      setDrawMode(false);
      setDraftPolygon(null);
      setDrawStart(null);
      try {
        const [stream, zones, events] = await Promise.all([
          apiClient.getStream(streamId),
          apiClient.getStreamZones(streamId),
          apiClient.getStreamEvents(streamId),
        ]);
        const visitPairs = await Promise.all(
          events.map(async (event) => [event.id, await apiClient.getEventVisits(event.id)] as const),
        );
        if (isMounted) {
          setDetail({
            stream,
            zones,
            events,
            visitsByEvent: Object.fromEntries(visitPairs),
          });
        }
      } catch (caught) {
        if (isMounted) {
          setError(caught instanceof Error ? caught.message : "Could not load stream.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadStreamDetail();

    return () => {
      isMounted = false;
    };
  }, [streamId]);

  useEffect(() => {
    if (!detail) {
      return;
    }

    if (detail.zones.length === 0) {
      setSelectedZoneId(null);
      return;
    }

    if (!selectedZoneId || !detail.zones.some((zone) => zone.id === selectedZoneId)) {
      setSelectedZoneId(detail.zones[0].id);
    }
  }, [detail, selectedZoneId]);

  useEffect(() => {
    if (!selectedZone) {
      setZoneDraft(null);
      return;
    }

    setZoneDraft({
      name: selectedZone.name,
      zone_type: selectedZone.zone_type,
      is_active: selectedZone.is_active,
    });
  }, [selectedZone]);

  function replaceZones(zones: Zone[]) {
    setDetail((current) => (current ? { ...current, zones } : current));
  }

  async function handleSaveSelectedZone(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedZone || !zoneDraft) {
      return;
    }

    const trimmedName = zoneDraft.name.trim();
    if (!trimmedName) {
      setZoneError("Zone name is required.");
      return;
    }

    setIsSavingZone(true);
    setZoneError(null);
    setZoneMessage(null);
    try {
      const result = await apiClient.updateZone(selectedZone.id, {
        ...zoneDraft,
        name: trimmedName,
      });
      replaceZones(result.zones);
      setSelectedZoneId(result.zone.id);
      setZoneMessage("Zone saved.");
    } catch (caught) {
      setZoneError(caught instanceof Error ? caught.message : "Could not save zone.");
    } finally {
      setIsSavingZone(false);
    }
  }

  function startDrawMode() {
    setDrawMode(true);
    setDraftPolygon(null);
    setDrawStart(null);
    setZoneError(null);
    setZoneMessage(null);
  }

  function cancelDrawMode() {
    setDrawMode(false);
    setDraftPolygon(null);
    setDrawStart(null);
    setZoneError(null);
  }

  function handleDrawStart(point: Point) {
    setDrawStart(point);
    setDraftPolygon(rectanglePolygon(point, point));
    setZoneError(null);
    setZoneMessage(null);
  }

  function handleDrawMove(point: Point) {
    if (!drawStart) {
      return;
    }
    setDraftPolygon(rectanglePolygon(drawStart, point));
  }

  function handleDrawEnd(point: Point) {
    if (!drawStart) {
      return;
    }

    const width = Math.abs(drawStart.x - point.x);
    const height = Math.abs(drawStart.y - point.y);
    setDrawStart(null);

    if (width < 0.015 || height < 0.015) {
      setDraftPolygon(null);
      setZoneError("Zone rectangle is too small.");
      return;
    }

    setDraftPolygon(rectanglePolygon(drawStart, point));
    setZoneMessage("Zone shape ready.");
  }

  async function handleCreateZone(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!draftPolygon) {
      setZoneError("Create a zone shape before saving.");
      return;
    }

    const trimmedName = newZoneName.trim();
    if (!trimmedName) {
      setZoneError("Zone name is required.");
      return;
    }

    setIsSavingZone(true);
    setZoneError(null);
    setZoneMessage(null);
    try {
      const result = await apiClient.createZone({
        stream_id: streamId,
        name: trimmedName,
        zone_type: newZoneType,
        polygon: draftPolygon,
        is_active: true,
      });
      replaceZones(result.zones);
      setSelectedZoneId(result.zone.id);
      setDrawMode(false);
      setDraftPolygon(null);
      setDrawStart(null);
      setNewZoneName("New zone");
      setNewZoneType("feeder");
      setZoneMessage("Zone created.");
    } catch (caught) {
      setZoneError(caught instanceof Error ? caught.message : "Could not create zone.");
    } finally {
      setIsSavingZone(false);
    }
  }

  if (isLoading) {
    return <div className="panel">Loading stream...</div>;
  }

  if (error || !detail) {
    return <div className="error-panel">{error ?? "Stream detail is unavailable."}</div>;
  }

  const streamReviewItems = reviewQueue.filter((item) => item.stream_id === detail.stream.id);

  return (
    <div className="page-stack">
      <div className="stream-detail-heading">
        <div>
          <StatusPill label={detail.stream.is_live ? "Demo live" : "Offline"} tone="good" />
          <h1>{detail.stream.name}</h1>
          <p>
            {detail.stream.description} Draw zones, inspect events, and turn corrections into local
            dataset records.
          </p>
        </div>
        <div className="detail-actions">
          {streamReviewItems.length > 0 ? (
            <button className="secondary-action" onClick={onOpenReview}>
              Review {streamReviewItems.length}
            </button>
          ) : null}
          <button className="secondary-action" onClick={onOpenExports}>
            Dataset Exports
          </button>
          {streamReviewItems.length > 0 ? (
            <StatusPill label={`${streamReviewItems.length} needs review`} tone="review" />
          ) : (
            <StatusPill label="Review clear" tone="good" />
          )}
        </div>
      </div>

      <StreamPanel
        stream={detail.stream}
        zones={detail.zones}
        events={detail.events}
        selectedZoneId={selectedZoneId}
        drawMode={drawMode}
        draftPolygon={draftPolygon}
        onSelectZone={setSelectedZoneId}
        onDrawStart={handleDrawStart}
        onDrawMove={handleDrawMove}
        onDrawEnd={handleDrawEnd}
      />

      <section className="split-grid">
        <div className="panel">
          <div className="section-heading">
            <h2>Zones</h2>
            <span className="meta-text">User-authored context for outdoor activity</span>
            <button className="secondary-action" onClick={drawMode ? cancelDrawMode : startDrawMode}>
              {drawMode ? "Cancel draw" : "Draw new zone"}
            </button>
          </div>
          <div className="zone-editor-grid">
            <div className="zone-list" aria-label="Stream zones">
              {detail.zones.map((zone) => (
                <button
                  className={`zone-list-button${selectedZoneId === zone.id ? " selected" : ""}${
                    zone.is_active ? "" : " inactive"
                  }`}
                  key={zone.id}
                  onClick={() => setSelectedZoneId(zone.id)}
                  type="button"
                >
                  <span>{zone.name}</span>
                  <strong>{formatLabel(zone.zone_type)}</strong>
                </button>
              ))}
            </div>

            <div className="zone-workspace">
              {selectedZone && zoneDraft ? (
                <form className="zone-edit-form" onSubmit={handleSaveSelectedZone}>
                  <label>
                    Name
                    <input
                      value={zoneDraft.name}
                      onChange={(event) =>
                        setZoneDraft((current) =>
                          current ? { ...current, name: event.target.value } : current,
                        )
                      }
                    />
                  </label>
                  <label>
                    Type
                    <select
                      value={zoneDraft.zone_type}
                      onChange={(event) =>
                        setZoneDraft((current) =>
                          current
                            ? { ...current, zone_type: event.target.value as ZoneType }
                            : current,
                        )
                      }
                    >
                      {zoneTypeOptions.map((zoneType) => (
                        <option key={zoneType} value={zoneType}>
                          {formatLabel(zoneType)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="checkbox-row">
                    <input
                      checked={zoneDraft.is_active}
                      onChange={(event) =>
                        setZoneDraft((current) =>
                          current ? { ...current, is_active: event.target.checked } : current,
                        )
                      }
                      type="checkbox"
                    />
                    Active
                  </label>
                  <button className="primary-action" disabled={isSavingZone} type="submit">
                    Save zone
                  </button>
                </form>
              ) : (
                <span className="meta-text">No zone selected.</span>
              )}

              {(drawMode || draftPolygon) && (
                <form className="draw-zone-panel" onSubmit={handleCreateZone}>
                  <div className="item-title-row">
                    <strong>{draftPolygon ? "New zone shape" : "Drawing zone"}</strong>
                    <StatusPill label={draftPolygon ? "Ready" : "Draw"} tone="quiet" />
                  </div>
                  <label>
                    Name
                    <input
                      value={newZoneName}
                      onChange={(event) => setNewZoneName(event.target.value)}
                    />
                  </label>
                  <label>
                    Type
                    <select
                      value={newZoneType}
                      onChange={(event) => setNewZoneType(event.target.value as ZoneType)}
                    >
                      {zoneTypeOptions.map((zoneType) => (
                        <option key={zoneType} value={zoneType}>
                          {formatLabel(zoneType)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="zone-action-row">
                    <button
                      className="primary-action"
                      disabled={isSavingZone || !draftPolygon}
                      type="submit"
                    >
                      Save new zone
                    </button>
                    <button className="secondary-action" onClick={cancelDrawMode} type="button">
                      Cancel
                    </button>
                  </div>
                </form>
              )}

              <div className="zone-meaning">
                <span>
                  <strong>Privacy zone</strong> restricts future detection, storage, and review
                  behavior.
                </span>
                <span>
                  <strong>Ignore zone</strong> keeps routine activity out of normal review events.
                </span>
              </div>

              {zoneMessage ? <div className="zone-message">{zoneMessage}</div> : null}
              {zoneError ? <div className="zone-error">{zoneError}</div> : null}
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="section-heading">
            <h2>Review hints</h2>
          </div>
          <div className="list-stack">
            {streamReviewItems.length > 0 ? (
              <>
                {streamReviewItems.map((item) => (
                  <div className="queue-mini" key={item.id}>
                    <strong>{item.title}</strong>
                    <span>{item.reason}</span>
                  </div>
                ))}
                <button className="secondary-action" onClick={onOpenReview}>
                  Open Review Queue
                </button>
              </>
            ) : (
              <>
                <span className="meta-text">No stream items need review.</span>
                <button className="secondary-action" onClick={onOpenExports}>
                  Open Dataset Exports
                </button>
              </>
            )}
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <h2>Stream events</h2>
        </div>
        <div className="event-list">
          {detail.events.map((event) => {
            const visits = detail.visitsByEvent[event.id] ?? [];
            const primaryZone =
              detail.zones.find((zone) => zone.id === event.primary_zone_id) ?? null;
            return (
              <article className="event-card" key={event.id}>
                <div className="item-title-row">
                  <h3>{event.title}</h3>
                  <div className="detail-actions">
                    <button className="text-action" onClick={() => onOpenEvent(event.id)}>
                      Event detail
                    </button>
                    <StatusPill
                      label={formatLabel(event.review_status)}
                      tone={event.review_status === "needs_review" ? "review" : "good"}
                    />
                  </div>
                </div>
                <span className="meta-text">{formatDateTime(event.started_at)}</span>
                <span className="meta-text">
                  Zone:{" "}
                  {primaryZone
                    ? `${primaryZone.name} (${formatLabel(primaryZone.zone_type)})`
                    : "Unzoned"}
                </span>
                <div className="tag-row">
                  {event.detections.map((detection) => (
                    <span className="tag" key={detection.id}>
                      {formatLabel(detection.label)} {Math.round(detection.confidence * 100)}%
                    </span>
                  ))}
                </div>
                {visits.length > 0 ? (
                  <div className="visit-strip">
                    {visits.map((visit) => (
                      <button key={visit.id} onClick={() => onOpenVisit(visit.id)}>
                        {formatLabel(visit.reviewed_label ?? visit.species_guess ?? visit.subject_label)}
                      </button>
                    ))}
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
