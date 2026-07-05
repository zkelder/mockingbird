import { useEffect, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type {
  Event,
  LocalCameraFrameCaptureResponse,
  Point,
  ReviewQueueItem,
  SourceSetupReviewResponse,
  Stream,
  StreamPlaybackStatus,
  Visit,
  Zone,
  ZoneType,
} from "../api/types";
import { StatusPill } from "../components/StatusPill";
import { StreamPanel } from "../components/StreamPanel";
import { formatDateTime, formatLabel } from "../utils";

interface StreamDetailPageProps {
  streamId: string;
  reviewQueue: ReviewQueueItem[];
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenImport: () => void;
  onOpenExports: () => void;
  onOpenReview: () => void;
}

interface StreamDetailState {
  stream: Stream;
  playback: StreamPlaybackStatus;
  setupReview: SourceSetupReviewResponse | null;
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

type LiveViewState = "idle" | "opening" | "streaming" | "failed" | "no_frames";

function playbackTone(status: StreamPlaybackStatus["status"]): "good" | "review" | "quiet" {
  if (status === "demo" || status === "live_ready") {
    return "good";
  }
  if (
    status === "not_configured" ||
    status === "unavailable" ||
    status === "playback_error" ||
    status === "unsupported_rtsp_bridge_required" ||
    status === "unsupported_stream_type"
  ) {
    return "review";
  }
  return "quiet";
}

function isBrowserPlayablePlayback(status?: StreamPlaybackStatus | null): boolean {
  return (
    status?.status === "live_ready" &&
    Boolean(status.preview_url) &&
    ["mjpeg", "browser_video", "hls"].includes(status.playback_kind)
  );
}

function isRtspBridgePlayback(status?: StreamPlaybackStatus | null): boolean {
  return (
    status?.status === "live_ready" &&
    status.playback_kind === "rtsp" &&
    Boolean(status.rtsp_bridge_available)
  );
}

function isLocalCameraBridgePlayback(status?: StreamPlaybackStatus | null): boolean {
  return (
    status?.status === "live_ready" &&
    status.playback_kind === "local_usb" &&
    Boolean(status.local_camera_bridge_available)
  );
}

function isWindowsDshowBridgePlayback(status?: StreamPlaybackStatus | null): boolean {
  return (
    status?.status === "live_ready" &&
    status.playback_kind === "windows_dshow" &&
    Boolean(status.windows_camera_bridge_available)
  );
}

function hasRealLivePlayback(status?: StreamPlaybackStatus | null): boolean {
  return (
    isBrowserPlayablePlayback(status) ||
    isRtspBridgePlayback(status) ||
    isLocalCameraBridgePlayback(status) ||
    isWindowsDshowBridgePlayback(status)
  );
}

function supportsFrameCapture(status?: StreamPlaybackStatus | null): boolean {
  return isLocalCameraBridgePlayback(status) || isWindowsDshowBridgePlayback(status);
}

function liveStreamUrl(playback: StreamPlaybackStatus, streamId: string): string | null {
  if (isWindowsDshowBridgePlayback(playback)) {
    return apiClient.windowsDshowMjpegBridgeUrl(streamId);
  }
  if (isLocalCameraBridgePlayback(playback)) {
    return apiClient.localCameraMjpegBridgeUrl(streamId);
  }
  if (isRtspBridgePlayback(playback)) {
    return apiClient.rtspMjpegBridgeUrl(streamId);
  }
  if (isBrowserPlayablePlayback(playback)) {
    return playback.preview_url ?? null;
  }
  return null;
}

function liveTroubleshootingText(playback: StreamPlaybackStatus): string | null {
  if (playback.playback_kind === "windows_dshow") {
    return (
      "Close Windows Camera or meeting apps, check the DirectShow camera name, " +
      "check the ffmpeg.exe path, and allow Windows camera privacy permissions."
    );
  }
  if (playback.playback_kind !== "local_usb") {
    return null;
  }
  const device = playback.local_camera_device_display ?? "/dev/video0";
  return (
    `Stop other camera apps, check ${device}, try /dev/video1 in Source setup if needed, ` +
    "and stop Live view before direct ffmpeg tests."
  );
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
  onOpenImport,
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
  const [liveViewOpen, setLiveViewOpen] = useState(false);
  const [liveViewState, setLiveViewState] = useState<LiveViewState>("idle");
  const [liveViewReloadToken, setLiveViewReloadToken] = useState(0);
  const [liveViewError, setLiveViewError] = useState<string | null>(null);
  const [captureResult, setCaptureResult] = useState<LocalCameraFrameCaptureResponse | null>(null);
  const [captureError, setCaptureError] = useState<string | null>(null);
  const [isCapturingFrame, setIsCapturingFrame] = useState(false);

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
      setLiveViewOpen(false);
      setLiveViewState("idle");
      setLiveViewReloadToken(0);
      setLiveViewError(null);
      setCaptureResult(null);
      setCaptureError(null);
      setIsCapturingFrame(false);
      try {
        const stream = await apiClient.getStream(streamId);
        const [playback, setupReview, zones, events] = await Promise.all([
          apiClient.getStreamPlaybackStatus(streamId),
          apiClient.getSourceSetupReview(stream.source_id),
          apiClient.getStreamZones(streamId),
          apiClient.getStreamEvents(streamId),
        ]);
        const visitPairs = await Promise.all(
          events.map(async (event) => [event.id, await apiClient.getEventVisits(event.id)] as const),
        );
        if (isMounted) {
          setDetail({
            stream,
            playback,
            setupReview,
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
    if (!detail || hasRealLivePlayback(detail.playback)) {
      return;
    }
    setLiveViewOpen(false);
    setLiveViewState("idle");
    setLiveViewError(null);
  }, [detail]);

  useEffect(() => {
    if (!liveViewOpen || liveViewState !== "opening") {
      return;
    }
    const timeout = window.setTimeout(() => {
      setLiveViewState((current) => (current === "opening" ? "no_frames" : current));
      setLiveViewError("Camera opened but no frames received.");
    }, 7000);
    return () => window.clearTimeout(timeout);
  }, [liveViewOpen, liveViewReloadToken, liveViewState]);

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

  function openLiveView() {
    setLiveViewOpen(true);
    setLiveViewState("opening");
    setLiveViewError(null);
    setLiveViewReloadToken((current) => current + 1);
  }

  function stopLiveView() {
    setLiveViewOpen(false);
    setLiveViewState("idle");
    setLiveViewError(null);
  }

  function refreshLiveView() {
    if (!liveViewOpen) {
      openLiveView();
      return;
    }
    setLiveViewState("opening");
    setLiveViewError(null);
    setLiveViewReloadToken((current) => current + 1);
  }

  async function handleCaptureFrame() {
    if (!detail || !supportsFrameCapture(detail.playback)) {
      return;
    }
    setIsCapturingFrame(true);
    setCaptureError(null);
    setCaptureResult(null);
    try {
      const result = await apiClient.captureLocalCameraFrame(detail.stream.id);
      setCaptureResult(result);
      if (result.status !== "saved") {
        setCaptureError(result.message);
      }
    } catch (caught) {
      setCaptureError(caught instanceof Error ? caught.message : "Could not capture frame.");
    } finally {
      setIsCapturingFrame(false);
    }
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
  const isManualMediaStream =
    detail.setupReview?.provider_key === "manual_media" &&
    detail.setupReview.readiness_level === "metadata_ready";
  const realLivePlayback = hasRealLivePlayback(detail.playback);
  const liveUrl = liveStreamUrl(detail.playback, detail.stream.id);
  const liveElementKey = `${liveUrl ?? "no-live-url"}-${liveViewReloadToken}`;
  const liveViewStatusLabel =
    liveViewState === "streaming"
      ? "Streaming"
      : liveViewState === "opening"
        ? "Opening"
        : liveViewState === "failed"
          ? "Failed"
          : liveViewState === "no_frames"
            ? "No frames"
            : "Ready";
  const liveViewTone =
    liveViewState === "failed" || liveViewState === "no_frames"
      ? "review"
      : liveViewState === "streaming"
        ? "good"
        : "quiet";
  const sourceDisplay = detail.setupReview?.provider_display_name ?? "Source";
  const liveHelpText = liveTroubleshootingText(detail.playback);
  const canCaptureFrame = supportsFrameCapture(detail.playback);

  return (
    <div className="page-stack">
      <div className="stream-detail-heading">
        <div>
          <StatusPill
            label={formatLabel(detail.playback.status)}
            tone={playbackTone(detail.playback.status)}
          />
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

      {realLivePlayback ? (
        <section className="stream-live-hero" aria-label={`${detail.stream.name} live stream`}>
          <div className="stream-live-toolbar">
            <div>
              <strong>Live camera stream</strong>
              <span>
                {detail.playback.message} Zones remain below until real-video overlay alignment is
                implemented.
              </span>
            </div>
            <div className="stream-live-badges">
              <StatusPill label={formatLabel(detail.playback.status)} tone="good" />
              <StatusPill label={formatLabel(detail.playback.playback_kind)} tone="quiet" />
              {detail.playback.local_camera_device_display ? (
                <StatusPill label={detail.playback.local_camera_device_display} tone="quiet" />
              ) : null}
              {detail.playback.windows_camera_name_display ? (
                <StatusPill label={detail.playback.windows_camera_name_display} tone="quiet" />
              ) : null}
              {detail.playback.windows_ffmpeg_binary_display ? (
                <StatusPill label={detail.playback.windows_ffmpeg_binary_display} tone="quiet" />
              ) : null}
              <StatusPill label={liveViewStatusLabel} tone={liveViewTone} />
            </div>
          </div>
          <div className="stream-live-frame">
            {liveViewOpen && liveUrl ? (
              detail.playback.playback_kind === "browser_video" ||
              detail.playback.playback_kind === "hls" ? (
                <video
                  controls
                  key={liveElementKey}
                  muted
                  onCanPlay={() => {
                    setLiveViewState("streaming");
                    setLiveViewError(null);
                  }}
                  onError={() => {
                    setLiveViewState("failed");
                    setLiveViewError("Live camera failed to load.");
                  }}
                  playsInline
                  src={liveUrl}
                />
              ) : (
                <img
                  alt={`${detail.stream.name} live camera stream`}
                  key={liveElementKey}
                  onError={() => {
                    setLiveViewState("failed");
                    setLiveViewError("Live camera failed to load.");
                  }}
                  onLoad={() => {
                    setLiveViewState("streaming");
                    setLiveViewError(null);
                  }}
                  src={
                    detail.playback.playback_kind === "local_usb" ||
                    detail.playback.playback_kind === "rtsp" ||
                    detail.playback.playback_kind === "windows_dshow"
                      ? `${liveUrl}${liveUrl.includes("?") ? "&" : "?"}reload=${liveViewReloadToken}`
                      : liveUrl
                  }
                />
              )
            ) : (
              <div className="stream-live-placeholder">
                <strong>{liveUrl ? "Live camera ready" : "Live camera unavailable"}</strong>
                <span>
                  {liveUrl
                    ? "Open Live view to start the stream request."
                    : detail.playback.setup_hint ?? detail.playback.message}
                </span>
              </div>
            )}
          </div>
          {liveViewState === "opening" ? (
            <div className="stream-live-message">Opening camera...</div>
          ) : null}
          {liveViewError ? (
            <div className="stream-live-message is-error">
              <strong>{liveViewError}</strong>
              {liveHelpText ? <span>{liveHelpText}</span> : null}
            </div>
          ) : liveHelpText ? (
            <span className="stream-live-hint">{liveHelpText}</span>
          ) : null}
          {captureResult ? (
            <div
              className={`stream-live-message${
                captureResult.status === "saved" ? "" : " is-error"
              }`}
            >
              <strong>{captureResult.message}</strong>
              {captureResult.status === "saved" && captureResult.media_asset_id ? (
                <a href={apiClient.mediaFileUrl(captureResult.media_asset_id)}>
                  Open saved frame
                </a>
              ) : null}
            </div>
          ) : null}
          {captureError && !captureResult ? (
            <div className="stream-live-message is-error">
              <strong>{captureError}</strong>
            </div>
          ) : null}
          <div className="detail-actions stream-live-actions">
            {liveViewOpen ? (
              <>
                <button className="secondary-action" onClick={stopLiveView} type="button">
                  Stop Live view
                </button>
                <button className="secondary-action" onClick={refreshLiveView} type="button">
                  Refresh stream
                </button>
              </>
            ) : (
              <button
                className="primary-action"
                disabled={!liveUrl}
                onClick={openLiveView}
                type="button"
              >
                Open Live view
              </button>
            )}
            {canCaptureFrame ? (
              <button
                className="secondary-action"
                disabled={isCapturingFrame}
                onClick={handleCaptureFrame}
                type="button"
              >
                {isCapturingFrame ? "Capturing..." : "Capture frame"}
              </button>
            ) : null}
          </div>
          {canCaptureFrame ? (
            <span className="stream-live-hint">
              Save one frame from this live camera for motion/review.
            </span>
          ) : null}
        </section>
      ) : (
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
      )}

      <div className="stream-context-strip">
        <span>
          <strong>Playback</strong> {formatLabel(detail.playback.playback_kind)}
        </span>
        <span>
          <strong>Status</strong> {formatLabel(detail.playback.status)}
        </span>
        <span>
          <strong>Source</strong> {sourceDisplay}
        </span>
        <span>
          <strong>Zones</strong>{" "}
          {detail.playback.supports_zone_editing ? "Available nearby" : "Unavailable"}
        </span>
        {detail.playback.live_stream_url_display ? (
          <span>
            <strong>Stream URL</strong> {detail.playback.live_stream_url_display}
          </span>
        ) : null}
        {detail.playback.windows_camera_name_display ? (
          <span>
            <strong>Windows camera</strong> {detail.playback.windows_camera_name_display}
          </span>
        ) : null}
        {isManualMediaStream ? (
          <button className="secondary-action" onClick={onOpenImport} type="button">
            Import media
          </button>
        ) : null}
      </div>
      <span className="meta-text">{detail.setupReview?.next_step ?? detail.playback.setup_hint}</span>

      <section className="split-grid">
        <div className="panel">
          <div className="section-heading">
            <h2>Zones</h2>
            <span className="meta-text">
              {realLivePlayback
                ? "Zone controls stay with this Stream; drawing over real video is not aligned yet."
                : "User-authored context for outdoor activity"}
            </span>
            <button
              className="secondary-action"
              disabled={realLivePlayback}
              onClick={drawMode ? cancelDrawMode : startDrawMode}
            >
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
