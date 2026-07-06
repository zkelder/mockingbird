import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type {
  Event,
  LocalCameraFrameCaptureResponse,
  LiveMotionEvaluateResponse,
  MediaAsset,
  MotionEvaluateSavedMediaResponse,
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
  onOpenMotionEvidence: (motionEvidenceId: string) => void;
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
type LiveMonitorState =
  | "idle"
  | "waiting"
  | "watching"
  | "activity"
  | "no_activity"
  | "failed"
  | "stopped";

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

function supportsLiveMotionMonitoring(status?: StreamPlaybackStatus | null): boolean {
  return (
    isRtspBridgePlayback(status) ||
    isLocalCameraBridgePlayback(status) ||
    isWindowsDshowBridgePlayback(status)
  );
}

function supportsFrameCapture(status?: StreamPlaybackStatus | null): boolean {
  return isLocalCameraBridgePlayback(status) || isWindowsDshowBridgePlayback(status);
}

function streamImageMediaAssets(mediaAssets: MediaAsset[], streamId: string): MediaAsset[] {
  return mediaAssets
    .filter(
      (asset) =>
        asset.stream_id === streamId &&
        (asset.media_type === "image" || asset.content_type.startsWith("image/")),
    )
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
}

function oldestFirstMediaAssets(mediaAssets: MediaAsset[]): MediaAsset[] {
  return [...mediaAssets].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));
}

function isCapturedCameraFrame(asset: MediaAsset): boolean {
  return asset.notes?.includes("Saved explicit local camera frame capture.") ?? false;
}

function latestMotionPair(mediaAssets: MediaAsset[]): MediaAsset[] {
  const capturedFrames = mediaAssets.filter(isCapturedCameraFrame);
  const sourceAssets = capturedFrames.length >= 2 ? capturedFrames : mediaAssets;
  return oldestFirstMediaAssets(sourceAssets.slice(0, 2));
}

function isReviewableZone(zone: Zone): boolean {
  return zone.is_active && zone.zone_type !== "privacy" && zone.zone_type !== "ignore";
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
  onOpenMotionEvidence,
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
  const [savedImageAssets, setSavedImageAssets] = useState<MediaAsset[]>([]);
  const [savedImageError, setSavedImageError] = useState<string | null>(null);
  const [isLoadingSavedImages, setIsLoadingSavedImages] = useState(false);
  const [motionResult, setMotionResult] = useState<MotionEvaluateSavedMediaResponse | null>(null);
  const [motionError, setMotionError] = useState<string | null>(null);
  const [isCheckingMotion, setIsCheckingMotion] = useState(false);
  const [isCreatingReviewActivity, setIsCreatingReviewActivity] = useState(false);
  const [liveMonitorState, setLiveMonitorState] = useState<LiveMonitorState>("idle");
  const [liveMotionResult, setLiveMotionResult] = useState<LiveMotionEvaluateResponse | null>(null);
  const [liveMotionError, setLiveMotionError] = useState<string | null>(null);
  const [isLiveMonitoring, setIsLiveMonitoring] = useState(false);
  const [isEvaluatingLiveMotion, setIsEvaluatingLiveMotion] = useState(false);
  const [isCreatingLiveReviewActivity, setIsCreatingLiveReviewActivity] = useState(false);
  const liveMonitorIntervalRef = useRef<number | null>(null);
  const liveMotionInFlightRef = useRef(false);

  const selectedZone = detail?.zones.find((zone) => zone.id === selectedZoneId) ?? null;

  function clearLiveMonitorInterval() {
    if (liveMonitorIntervalRef.current !== null) {
      window.clearInterval(liveMonitorIntervalRef.current);
      liveMonitorIntervalRef.current = null;
    }
  }

  useEffect(() => {
    let isMounted = true;

    async function loadStreamDetail() {
      clearLiveMonitorInterval();
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
      setSavedImageAssets([]);
      setSavedImageError(null);
      setIsLoadingSavedImages(false);
      setMotionResult(null);
      setMotionError(null);
      setIsCheckingMotion(false);
      setIsCreatingReviewActivity(false);
      setLiveMonitorState("idle");
      setLiveMotionResult(null);
      setLiveMotionError(null);
      setIsLiveMonitoring(false);
      setIsEvaluatingLiveMotion(false);
      setIsCreatingLiveReviewActivity(false);
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
      clearLiveMonitorInterval();
    };
  }, [streamId]);

  useEffect(() => {
    return () => {
      clearLiveMonitorInterval();
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function loadSavedImages() {
      setIsLoadingSavedImages(true);
      setSavedImageError(null);
      try {
        const mediaAssets = await apiClient.getMediaAssets();
        if (isMounted) {
          setSavedImageAssets(streamImageMediaAssets(mediaAssets, streamId));
        }
      } catch (caught) {
        if (isMounted) {
          setSavedImageError(
            caught instanceof Error ? caught.message : "Could not load saved images.",
          );
        }
      } finally {
        if (isMounted) {
          setIsLoadingSavedImages(false);
        }
      }
    }

    void loadSavedImages();

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
    stopLiveMonitoring();
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

  function liveMonitorStateFor(result: LiveMotionEvaluateResponse): LiveMonitorState {
    if (result.activity_detected) {
      return "activity";
    }
    if (
      result.status === "waiting_for_live_frames" ||
      result.status === "no_recent_frames" ||
      result.status === "not_enough_frames"
    ) {
      return "waiting";
    }
    if (result.status === "no_activity") {
      return "watching";
    }
    return "no_activity";
  }

  async function evaluateLiveMotion(createReviewActivity: boolean) {
    if (!detail) {
      return;
    }
    if (liveMotionInFlightRef.current && !createReviewActivity) {
      return;
    }
    liveMotionInFlightRef.current = true;
    setLiveMotionError(null);
    if (createReviewActivity) {
      setIsCreatingLiveReviewActivity(true);
    } else {
      setIsEvaluatingLiveMotion(true);
    }
    try {
      const result = await apiClient.evaluateLiveMotion(detail.stream.id, {
        save_best_frame: true,
        create_review_activity: createReviewActivity,
        min_triggered_frames: 1,
        notes: createReviewActivity
          ? "User created review activity from live stream motion monitoring."
          : null,
      });
      setLiveMotionResult(result);
      setLiveMonitorState(liveMonitorStateFor(result));
      if (result.best_media_asset_id) {
        await refreshSavedImages();
      }
      if (result.activity_detected && !createReviewActivity) {
        clearLiveMonitorInterval();
        setIsLiveMonitoring(false);
      }
    } catch (caught) {
      setLiveMonitorState("failed");
      setLiveMotionError(
        caught instanceof Error ? caught.message : "Could not monitor live motion.",
      );
    } finally {
      liveMotionInFlightRef.current = false;
      if (createReviewActivity) {
        setIsCreatingLiveReviewActivity(false);
      } else {
        setIsEvaluatingLiveMotion(false);
      }
    }
  }

  function startLiveMonitoring() {
    if (!detail) {
      return;
    }
    if (!supportsLiveMotionMonitoring(detail.playback)) {
      setLiveMonitorState("failed");
      setLiveMotionError("Live monitoring is available when MockingBird serves this live stream.");
      return;
    }
    if (!liveViewOpen || !liveUrl) {
      setLiveMonitorState("failed");
      setLiveMotionError("Open Live view before starting live monitoring.");
      return;
    }
    clearLiveMonitorInterval();
    setLiveMotionResult(null);
    setLiveMotionError(null);
    setLiveMonitorState("waiting");
    setIsLiveMonitoring(true);
    void evaluateLiveMotion(false);
    liveMonitorIntervalRef.current = window.setInterval(() => {
      void evaluateLiveMotion(false);
    }, 2000);
  }

  function stopLiveMonitoring() {
    clearLiveMonitorInterval();
    setIsLiveMonitoring(false);
    liveMotionInFlightRef.current = false;
    setLiveMonitorState((current) =>
      current === "idle" || current === "activity" ? current : "stopped",
    );
  }

  async function refreshSavedImages(): Promise<MediaAsset[]> {
    setSavedImageError(null);
    try {
      const mediaAssets = await apiClient.getMediaAssets();
      const nextSavedImages = streamImageMediaAssets(mediaAssets, streamId);
      setSavedImageAssets(nextSavedImages);
      return nextSavedImages;
    } catch (caught) {
      setSavedImageError(caught instanceof Error ? caught.message : "Could not refresh saved images.");
      return savedImageAssets;
    }
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
      } else {
        setMotionResult(null);
        setMotionError(null);
        await refreshSavedImages();
      }
    } catch (caught) {
      setCaptureError(caught instanceof Error ? caught.message : "Could not capture frame.");
    } finally {
      setIsCapturingFrame(false);
    }
  }

  async function handleCheckMotion(createReviewActivity: boolean) {
    if (!detail) {
      return;
    }
    const selectedAssets = latestMotionPair(savedImageAssets);
    if (selectedAssets.length < 2) {
      setMotionError("Capture another frame to check motion.");
      return;
    }

    const reviewableZones = detail.zones.filter(isReviewableZone);
    setMotionError(null);
    if (createReviewActivity) {
      setIsCreatingReviewActivity(true);
    } else {
      setIsCheckingMotion(true);
    }
    try {
      const result = await apiClient.evaluateSavedMediaMotion({
        stream_id: detail.stream.id,
        media_asset_ids: selectedAssets.map((asset) => asset.id),
        zone_ids: reviewableZones.length > 0 ? reviewableZones.map((zone) => zone.id) : null,
        create_motion_evidence: createReviewActivity,
        attach_best_snapshot: true,
        notes: createReviewActivity
          ? "User created review activity from captured local camera frames."
          : null,
      });
      setMotionResult(result);
    } catch (caught) {
      setMotionError(caught instanceof Error ? caught.message : "Could not check motion.");
    } finally {
      if (createReviewActivity) {
        setIsCreatingReviewActivity(false);
      } else {
        setIsCheckingMotion(false);
      }
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
  const liveMonitorStatusLabel =
    liveMonitorState === "waiting"
      ? "Waiting"
      : liveMonitorState === "watching"
        ? "Watching"
        : liveMonitorState === "activity"
          ? "Activity detected"
          : liveMonitorState === "failed"
            ? "Failed"
            : liveMonitorState === "stopped"
              ? "Stopped"
              : liveMonitorState === "no_activity"
                ? "No activity"
                : "Monitor idle";
  const liveMonitorTone =
    liveMonitorState === "activity"
      ? "review"
      : liveMonitorState === "watching"
        ? "good"
        : liveMonitorState === "failed"
          ? "review"
          : "quiet";
  const sourceDisplay = detail.setupReview?.provider_display_name ?? "Source";
  const liveHelpText = liveTroubleshootingText(detail.playback);
  const canMonitorLiveMotion = supportsLiveMotionMonitoring(detail.playback);
  const canCaptureFrame = supportsFrameCapture(detail.playback);
  const captureSaved = captureResult?.status === "saved";
  const latestSavedImage = savedImageAssets[0] ?? null;
  const savedImageCount = savedImageAssets.length;
  const canCheckMotion = savedImageCount >= 2;
  const motionPair = latestMotionPair(savedImageAssets);
  const motionActionLabel = canCheckMotion
    ? "Compare captured frames"
    : "Capture another frame to check motion";
  const motionCreatedEvidence = motionResult?.created_evidence[0] ?? null;
  const liveMotionCreatedEvidence = liveMotionResult?.created_evidence[0] ?? null;
  const canCreateLiveReviewActivity = Boolean(
    liveMotionResult?.activity_detected &&
      liveMotionResult.review_activity_available &&
      liveMotionResult.created_evidence.length === 0,
  );
  const canCreateReviewActivity = Boolean(
    motionResult?.activity_detected &&
      motionResult.can_create_review_activity &&
      motionResult.should_create_review_activity &&
      motionResult.created_evidence.length === 0,
  );
  const captureSuccessMessage =
    captureResult?.capture_source === "live_frame_cache"
      ? "Saved current live frame. It will not appear in Bird Log until you create/review activity."
      : "Saved one local camera frame. It will not appear in Bird Log until you create/review activity.";
  const captureButtonLabel =
    isCapturingFrame
      ? "Capturing..."
      : liveViewOpen
        ? "Capture current frame"
        : "Capture frame";

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
              <StatusPill label={liveMonitorStatusLabel} tone={liveMonitorTone} />
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
          {liveMotionError ? (
            <div className="stream-live-message is-error">
              <strong>{liveMotionError}</strong>
            </div>
          ) : null}
          {isLiveMonitoring || isEvaluatingLiveMotion || liveMotionResult ? (
            <div className="stream-live-message">
              <strong>
                {liveMotionResult?.activity_detected
                  ? "Activity detected"
                  : isLiveMonitoring
                    ? "Watching live video"
                    : liveMonitorStatusLabel}
              </strong>
              <span>
                {liveMotionResult?.message ??
                  "Monitoring compares recent live frames from this stream."}
              </span>
              <span>
                Captured frames are saved evidence. Bird Log updates after reviewed activity.
              </span>
              {liveMotionResult?.strongest_activity_area_label ? (
                <span>Activity area: {liveMotionResult.strongest_activity_area_label}</span>
              ) : null}
              <div className="detail-actions stream-live-actions">
                {liveMotionResult?.best_media_asset_id ? (
                  <a
                    className="secondary-action"
                    href={apiClient.mediaFileUrl(liveMotionResult.best_media_asset_id)}
                  >
                    Open saved best frame
                  </a>
                ) : null}
                {canCreateLiveReviewActivity ? (
                  <button
                    className="primary-action"
                    disabled={isCreatingLiveReviewActivity}
                    onClick={() => void evaluateLiveMotion(true)}
                    type="button"
                  >
                    {isCreatingLiveReviewActivity ? "Creating..." : "Create review activity"}
                  </button>
                ) : null}
                {liveMotionCreatedEvidence ? (
                  <button
                    className="secondary-action"
                    onClick={() => onOpenMotionEvidence(liveMotionCreatedEvidence.id)}
                    type="button"
                  >
                    Open review activity
                  </button>
                ) : null}
                {streamReviewItems.length > 0 ? (
                  <button className="secondary-action" onClick={onOpenReview} type="button">
                    Open Review Queue
                  </button>
                ) : null}
              </div>
              {liveMotionResult?.warnings.length ? (
                <span>{liveMotionResult.warnings[0]}</span>
              ) : null}
            </div>
          ) : null}
          {captureResult ? (
            <div
              className={`stream-live-message${
                captureResult.status === "saved" ? "" : " is-error"
              }`}
            >
              <strong>
                {captureSaved ? captureSuccessMessage : captureResult.message}
              </strong>
              {captureSaved ? (
                <>
                  <span>
                    Saved images for this stream: {savedImageCount}
                    {latestSavedImage
                      ? ` · Latest ${latestSavedImage.original_filename || latestSavedImage.filename}`
                      : ""}
                  </span>
                  <span>Bird Log shows reviewed activity, not raw captures.</span>
                  <div className="detail-actions stream-live-actions">
                    {captureResult.media_asset_id ? (
                      <a
                        className="secondary-action"
                        href={apiClient.mediaFileUrl(captureResult.media_asset_id)}
                      >
                        Open saved frame
                      </a>
                    ) : null}
                    <button
                      className="secondary-action"
                      disabled={isCapturingFrame}
                      onClick={handleCaptureFrame}
                      type="button"
                    >
                      {isCapturingFrame ? "Capturing..." : "Capture another frame"}
                    </button>
                    <button
                      className="secondary-action"
                      disabled={!canCheckMotion || isCheckingMotion || isCreatingReviewActivity}
                      onClick={() => void handleCheckMotion(false)}
                      type="button"
                    >
                      {isCheckingMotion ? "Comparing..." : motionActionLabel}
                    </button>
                    {streamReviewItems.length > 0 ? (
                      <button className="secondary-action" onClick={onOpenReview} type="button">
                        Open Review Queue
                      </button>
                    ) : null}
                  </div>
                  {!canCheckMotion ? (
                    <span>Motion checks compare two saved frames from this stream.</span>
                  ) : (
                    <span>
                      Fallback comparison uses the two most recent saved frames:{" "}
                      {motionPair
                        .map((asset) => asset.original_filename || asset.filename)
                        .join(" -> ")}
                    </span>
                  )}
                </>
              ) : null}
            </div>
          ) : null}
          {captureSaved && savedImageError ? (
            <div className="stream-live-message is-error">
              <strong>{savedImageError}</strong>
            </div>
          ) : null}
          {captureSaved && isLoadingSavedImages ? (
            <span className="stream-live-hint">Refreshing saved images...</span>
          ) : null}
          {captureSaved && motionError ? (
            <div className="stream-live-message is-error">
              <strong>{motionError}</strong>
            </div>
          ) : null}
          {captureSaved && motionResult ? (
            <div className="stream-live-message">
              <strong>
                {motionResult.activity_detected
                  ? "Motion found candidate activity."
                  : "No motion activity found yet."}
              </strong>
              <span>
                {motionResult.activity_detected
                  ? "Create review activity explicitly, then review/correct before Bird Log or export."
                  : "Captured frames remain saved media until activity is reviewed."}
              </span>
              {motionResult.session_message ? <span>{motionResult.session_message}</span> : null}
              <div className="detail-actions stream-live-actions">
                {canCreateReviewActivity ? (
                  <button
                    className="primary-action"
                    disabled={isCreatingReviewActivity}
                    onClick={() => void handleCheckMotion(true)}
                    type="button"
                  >
                    {isCreatingReviewActivity ? "Creating..." : "Create review activity"}
                  </button>
                ) : null}
                {motionCreatedEvidence ? (
                  <button
                    className="secondary-action"
                    onClick={() => onOpenMotionEvidence(motionCreatedEvidence.id)}
                    type="button"
                  >
                    Open review activity
                  </button>
                ) : null}
                {streamReviewItems.length > 0 ? (
                  <button className="secondary-action" onClick={onOpenReview} type="button">
                    Open Review Queue
                  </button>
                ) : null}
              </div>
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
                disabled={!liveUrl || isCapturingFrame}
                onClick={openLiveView}
                type="button"
              >
                Open Live view
              </button>
            )}
            {isLiveMonitoring ? (
              <button className="secondary-action" onClick={stopLiveMonitoring} type="button">
                Stop monitoring
              </button>
            ) : (
              <button
                className={liveViewOpen ? "primary-action" : "secondary-action"}
                disabled={
                  !liveViewOpen || !liveUrl || !canMonitorLiveMotion || isEvaluatingLiveMotion
                }
                onClick={startLiveMonitoring}
                type="button"
              >
                {isEvaluatingLiveMotion ? "Checking..." : "Start monitoring"}
              </button>
            )}
            {canCaptureFrame ? (
              <button
                className="secondary-action"
                disabled={isCapturingFrame}
                onClick={handleCaptureFrame}
                type="button"
              >
                {captureButtonLabel}
              </button>
            ) : null}
          </div>
          <span className="stream-live-hint">
            {canMonitorLiveMotion
              ? "Monitoring compares recent live frames from this stream. Captured frames are saved evidence for fallback review."
              : "Live monitoring is available when MockingBird serves the live stream through a local bridge."}
          </span>
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
