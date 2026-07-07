import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type FormEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { apiClient } from "../api/client";
import type {
  Event,
  LocalCameraFrameCaptureResponse,
  LiveCameraSessionStatus,
  LiveMotionEvaluateResponse,
  MediaAsset,
  MotionEvaluateSavedMediaResponse,
  Point,
  ReviewQueueItem,
  SourceProviderConfiguration,
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
  onOpenReview: (
    context?: {
      source?: "live-motion";
      search?: string | null;
      status?: "unreviewed" | "reviewed" | "all" | null;
    } | null,
  ) => void;
  onOpenMotionEvidence: (motionEvidenceId: string) => void;
  onReviewActivityCreated: () => Promise<void>;
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

interface MediaRenderSize {
  width: number;
  height: number;
}

type CameraTuningKey =
  | "video_size"
  | "preview_video_size"
  | "capture_video_size"
  | "framerate"
  | "input_format"
  | "brightness"
  | "contrast"
  | "exposure"
  | "zoom_mode";

type CameraTuningDraft = Record<CameraTuningKey, string>;

type LiveViewState = "idle" | "opening" | "streaming" | "failed" | "no_frames";
type LiveMonitorState =
  | "idle"
  | "waiting"
  | "watching"
  | "cooldown"
  | "activity"
  | "no_activity"
  | "failed"
  | "stopped";
type LiveMonitorSensitivity = "low" | "normal" | "high";

const liveMonitorSensitivitySettings: Record<
  LiveMonitorSensitivity,
  {
    label: string;
    min_changed_ratio: number;
    pixel_delta_threshold: number;
    interval_ms: number;
    max_frames: number;
  }
> = {
  low: {
    label: "Low",
    min_changed_ratio: 0.035,
    pixel_delta_threshold: 35,
    interval_ms: 2500,
    max_frames: 12,
  },
  normal: {
    label: "Normal",
    min_changed_ratio: 0.012,
    pixel_delta_threshold: 18,
    interval_ms: 1500,
    max_frames: 20,
  },
  high: {
    label: "High",
    min_changed_ratio: 0.003,
    pixel_delta_threshold: 10,
    interval_ms: 750,
    max_frames: 24,
  },
};
const liveMonitorSensitivityOptions: LiveMonitorSensitivity[] = ["low", "normal", "high"];

const cameraTuningKeys: CameraTuningKey[] = [
  "video_size",
  "preview_video_size",
  "capture_video_size",
  "framerate",
  "input_format",
  "brightness",
  "contrast",
  "exposure",
  "zoom_mode",
];

const emptyCameraTuningDraft: CameraTuningDraft = {
  video_size: "",
  preview_video_size: "",
  capture_video_size: "",
  framerate: "",
  input_format: "",
  brightness: "",
  contrast: "",
  exposure: "",
  zoom_mode: "",
};

const cameraTuningLabels: Record<CameraTuningKey, string> = {
  video_size: "Fallback size",
  preview_video_size: "Preview size",
  capture_video_size: "Capture size",
  framerate: "Framerate",
  input_format: "Input format",
  brightness: "Brightness note",
  contrast: "Contrast note",
  exposure: "Exposure note",
  zoom_mode: "Zoom/crop note",
};

const cameraTuningPlaceholders: Record<CameraTuningKey, string> = {
  video_size: "1280x720",
  preview_video_size: "1280x720",
  capture_video_size: "1920x1080",
  framerate: "15",
  input_format: "mjpeg",
  brightness: "driver setting",
  contrast: "driver setting",
  exposure: "driver setting",
  zoom_mode: "feeder framed tight",
};

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

function supportsBackendLiveSession(status?: StreamPlaybackStatus | null): boolean {
  return supportsLiveMotionMonitoring(status);
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

function safeConfigValue(
  config: SourceProviderConfiguration | null,
  key: string,
): string {
  const value = config?.safe_config_preview[key];
  if (!value || value === "not_configured" || value === "configured") {
    return "";
  }
  return value;
}

function cameraTuningDraftFromConfig(
  config: SourceProviderConfiguration | null,
): CameraTuningDraft {
  return {
    ...emptyCameraTuningDraft,
    ...Object.fromEntries(
      cameraTuningKeys.map((key) => [key, safeConfigValue(config, key)]),
    ),
  };
}

function providerConfigPayload(
  config: SourceProviderConfiguration | null,
  draft: CameraTuningDraft,
): Record<string, string | null> {
  const payload: Record<string, string | null> = {};
  for (const [key, value] of Object.entries(config?.safe_config_preview ?? {})) {
    if (value && value !== "not_configured" && value !== "configured") {
      payload[key] = value;
    }
  }
  for (const key of cameraTuningKeys) {
    const value = draft[key].trim();
    if (value) {
      payload[key] = value;
    } else {
      delete payload[key];
    }
  }
  return payload;
}

function isReviewableZone(zone: Zone): boolean {
  return zone.is_active && zone.zone_type !== "privacy" && zone.zone_type !== "ignore";
}

function polygonPoints(points: Point[]): string {
  return points.map((point) => `${point.x * 100},${point.y * 100}`).join(" ");
}

function zoneLabelAnchor(zone: Zone): Point {
  if (!zone.polygon.length) {
    return { x: 0.5, y: 0.5 };
  }

  const minX = Math.min(...zone.polygon.map((point) => point.x));
  const maxX = Math.max(...zone.polygon.map((point) => point.x));
  const minY = Math.min(...zone.polygon.map((point) => point.y));
  const labelX = minX + (maxX - minX) / 2;

  return {
    x: Math.min(0.78, Math.max(0.22, labelX)),
    y: Math.min(0.92, Math.max(0.03, minY + 0.02)),
  };
}

function liveZoneLabel(zone: Zone, expanded: boolean): string {
  return expanded ? zone.name : formatLabel(zone.zone_type);
}

function suppressedZoneDisplay(
  summary: LiveMotionEvaluateResponse["suppressed_zone_summaries"][number],
): string {
  return `${summary.zone_name} (${formatLabel(summary.zone_type)})`;
}

function suppressedZoneMessage(
  summaries: LiveMotionEvaluateResponse["suppressed_zone_summaries"],
): string | null {
  if (!summaries.length) {
    return null;
  }
  if (summaries.length === 1) {
    return `Motion ignored in ${summaries[0].zone_name}.`;
  }
  return `Motion ignored in ${summaries[0].zone_name} and ${
    summaries.length - 1
  } other ignore/privacy zone${summaries.length === 2 ? "" : "s"}.`;
}

function formatAgeMs(ageMs: number | null | undefined): string {
  if (ageMs == null) {
    return "n/a";
  }
  if (ageMs < 1000) {
    return `${ageMs} ms`;
  }
  return `${Math.round(ageMs / 1000)}s ago`;
}

function formatPercent(value: number | null | undefined): string {
  if (value == null) {
    return "n/a";
  }
  const percent = value * 100;
  return `${percent < 1 ? percent.toFixed(2) : percent.toFixed(1)}%`;
}

function pointFromPointer(event: ReactPointerEvent<HTMLElement>): Point {
  const rect = event.currentTarget.getBoundingClientRect();
  const x = (event.clientX - rect.left) / rect.width;
  const y = (event.clientY - rect.top) / rect.height;

  return {
    x: Math.min(1, Math.max(0, x)),
    y: Math.min(1, Math.max(0, y)),
  };
}

function containedMediaRectStyle(size: MediaRenderSize | null): CSSProperties {
  if (!size?.width || !size.height) {
    return { inset: 0 };
  }

  const containerAspect = 16 / 9;
  const mediaAspect = size.width / size.height;

  if (mediaAspect > containerAspect) {
    const heightPercent = (containerAspect / mediaAspect) * 100;
    return {
      left: "0%",
      top: `${(100 - heightPercent) / 2}%`,
      width: "100%",
      height: `${heightPercent}%`,
    };
  }

  const widthPercent = (mediaAspect / containerAspect) * 100;
  return {
    left: `${(100 - widthPercent) / 2}%`,
    top: "0%",
    width: `${widthPercent}%`,
    height: "100%",
  };
}

function liveStreamUrl(playback: StreamPlaybackStatus, streamId: string): string | null {
  if (isWindowsDshowBridgePlayback(playback)) {
    return apiClient.liveCameraSessionMjpegUrl(streamId);
  }
  if (isLocalCameraBridgePlayback(playback)) {
    return apiClient.liveCameraSessionMjpegUrl(streamId);
  }
  if (isRtspBridgePlayback(playback)) {
    return apiClient.liveCameraSessionMjpegUrl(streamId);
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
  onReviewActivityCreated,
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
  const [liveMediaSize, setLiveMediaSize] = useState<MediaRenderSize | null>(null);
  const [showLiveZones, setShowLiveZones] = useState(true);
  const [liveSession, setLiveSession] = useState<LiveCameraSessionStatus | null>(null);
  const [liveSessionError, setLiveSessionError] = useState<string | null>(null);
  const [isStartingLiveSession, setIsStartingLiveSession] = useState(false);
  const [isStoppingLiveSession, setIsStoppingLiveSession] = useState(false);
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
  const [liveMonitorSensitivity, setLiveMonitorSensitivity] =
    useState<LiveMonitorSensitivity>("normal");
  const [sourceProviderConfig, setSourceProviderConfig] =
    useState<SourceProviderConfiguration | null>(null);
  const [cameraTuningDraft, setCameraTuningDraft] = useState<CameraTuningDraft>({
    ...emptyCameraTuningDraft,
  });
  const [cameraTuningMessage, setCameraTuningMessage] = useState<string | null>(null);
  const [cameraTuningError, setCameraTuningError] = useState<string | null>(null);
  const [isSavingCameraTuning, setIsSavingCameraTuning] = useState(false);
  const [liveMotionFocusZoneId, setLiveMotionFocusZoneId] = useState("");
  const [showLiveMotionDebug, setShowLiveMotionDebug] = useState(false);
  const liveMotionInFlightRef = useRef(false);

  const selectedZone = detail?.zones.find((zone) => zone.id === selectedZoneId) ?? null;

  async function refreshLiveCameraSessionStatus(
    currentDetail: StreamDetailState | null = detail,
  ): Promise<LiveCameraSessionStatus | null> {
    if (!currentDetail || !supportsBackendLiveSession(currentDetail.playback)) {
      setLiveSession(null);
      return null;
    }
    try {
      const status = await apiClient.getLiveCameraSessionStatus(currentDetail.stream.id);
      setLiveSession(status);
      setIsLiveMonitoring(status.monitor_running);
      if (status.last_motion_result) {
        setLiveMotionResult(status.last_motion_result);
        setLiveMonitorState(liveMonitorStateFor(status.last_motion_result));
      } else if (status.monitor_running) {
        setLiveMonitorState((current) => (current === "idle" ? "waiting" : current));
      }
      setLiveSessionError(null);
      return status;
    } catch (caught) {
      setLiveSessionError(
        caught instanceof Error ? caught.message : "Could not read camera session status.",
      );
      return null;
    }
  }

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
      setLiveMediaSize(null);
      setShowLiveZones(true);
      setLiveSession(null);
      setLiveSessionError(null);
      setIsStartingLiveSession(false);
      setIsStoppingLiveSession(false);
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
      setSourceProviderConfig(null);
      setCameraTuningDraft({ ...emptyCameraTuningDraft });
      setCameraTuningMessage(null);
      setCameraTuningError(null);
      setIsSavingCameraTuning(false);
      setLiveMotionFocusZoneId("");
      setShowLiveMotionDebug(false);
      try {
        const stream = await apiClient.getStream(streamId);
        const [playback, setupReview, providerConfiguration, zones, events] = await Promise.all([
          apiClient.getStreamPlaybackStatus(streamId),
          apiClient.getSourceSetupReview(stream.source_id),
          apiClient.getSourceProviderConfiguration(stream.source_id),
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
          setSourceProviderConfig(providerConfiguration);
          setCameraTuningDraft(cameraTuningDraftFromConfig(providerConfiguration));
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
    if (!detail || !supportsBackendLiveSession(detail.playback)) {
      return;
    }
    let isMounted = true;

    async function pollStatus() {
      if (!isMounted) {
        return;
      }
      await refreshLiveCameraSessionStatus(detail);
    }

    void pollStatus();
    const interval = window.setInterval(() => {
      void pollStatus();
    }, 3000);
    return () => {
      isMounted = false;
      window.clearInterval(interval);
    };
  }, [detail?.stream.id, detail?.playback.playback_kind, detail?.playback.status]);

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

  useEffect(() => {
    if (!detail || !liveMotionFocusZoneId) {
      return;
    }
    if (!detail.zones.some((zone) => zone.id === liveMotionFocusZoneId && isReviewableZone(zone))) {
      setLiveMotionFocusZoneId("");
    }
  }, [detail, liveMotionFocusZoneId]);

  function replaceZones(zones: Zone[]) {
    setDetail((current) => (current ? { ...current, zones } : current));
  }

  function updateCameraTuningDraft(key: CameraTuningKey, value: string) {
    setCameraTuningDraft((current) => ({ ...current, [key]: value }));
    setCameraTuningMessage(null);
    setCameraTuningError(null);
  }

  async function handleSaveCameraTuning(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!detail || !sourceProviderConfig) {
      return;
    }
    setIsSavingCameraTuning(true);
    setCameraTuningError(null);
    setCameraTuningMessage(null);
    try {
      const updatedConfig = await apiClient.updateSourceProviderConfiguration(
        detail.stream.source_id,
        {
          provider_key: sourceProviderConfig.provider_key,
          config: providerConfigPayload(sourceProviderConfig, cameraTuningDraft),
        },
      );
      const [playback, setupReview] = await Promise.all([
        apiClient.getStreamPlaybackStatus(detail.stream.id),
        apiClient.getSourceSetupReview(detail.stream.source_id),
      ]);
      setSourceProviderConfig(updatedConfig);
      setCameraTuningDraft(cameraTuningDraftFromConfig(updatedConfig));
      setDetail((current) =>
        current ? { ...current, playback, setupReview } : current,
      );
      setCameraTuningMessage(
        liveSessionRunning
          ? "Saved. Restart camera to apply session settings."
          : "Saved. Settings apply next time the camera starts.",
      );
    } catch (caught) {
      setCameraTuningError(
        caught instanceof Error ? caught.message : "Could not save camera tuning.",
      );
    } finally {
      setIsSavingCameraTuning(false);
    }
  }

  async function restartLiveCameraSession() {
    if (!detail || !supportsBackendLiveSession(detail.playback)) {
      return;
    }
    setCameraTuningError(null);
    setCameraTuningMessage(null);
    await stopLiveMonitoring();
    await stopLiveCameraSession();
    await startLiveCameraSession(true);
    setCameraTuningMessage("Camera restarted with saved settings.");
  }

  async function startLiveCameraSession(openViewAfterStart = false) {
    if (!detail || !supportsBackendLiveSession(detail.playback)) {
      return;
    }
    setIsStartingLiveSession(true);
    setLiveSessionError(null);
    setLiveViewError(null);
    try {
      const status = await apiClient.startLiveCameraSession(detail.stream.id);
      setLiveSession(status);
      if (openViewAfterStart) {
        setLiveViewOpen(true);
        setLiveViewState("opening");
        setLiveMediaSize(null);
        setLiveViewReloadToken((current) => current + 1);
      }
    } catch (caught) {
      setLiveSessionError(
        caught instanceof Error ? caught.message : "Could not start camera session.",
      );
    } finally {
      setIsStartingLiveSession(false);
    }
  }

  async function stopLiveCameraSession() {
    if (!detail || !supportsBackendLiveSession(detail.playback)) {
      return;
    }
    setIsStoppingLiveSession(true);
    setLiveSessionError(null);
    await stopLiveMonitoring();
    setDrawMode(false);
    setDraftPolygon(null);
    setDrawStart(null);
    setLiveViewOpen(false);
    setLiveViewState("idle");
    setLiveViewError(null);
    try {
      const status = await apiClient.stopLiveCameraSession(detail.stream.id);
      setLiveSession(status);
    } catch (caught) {
      setLiveSessionError(
        caught instanceof Error ? caught.message : "Could not stop camera session.",
      );
    } finally {
      setIsStoppingLiveSession(false);
    }
  }

  function openLiveView() {
    if (detail && supportsBackendLiveSession(detail.playback) && liveSession?.status !== "running") {
      setLiveViewError("Start camera session before opening live view.");
      return;
    }
    setLiveViewOpen(true);
    setLiveViewState("opening");
    setLiveViewError(null);
    setLiveMediaSize(null);
    setLiveViewReloadToken((current) => current + 1);
  }

  function stopLiveView() {
    setDrawMode(false);
    setDraftPolygon(null);
    setDrawStart(null);
    setLiveViewOpen(false);
    setLiveViewState("idle");
    setLiveViewError(null);
  }

  function refreshLiveView() {
    if (detail && supportsBackendLiveSession(detail.playback) && liveSession?.status !== "running") {
      setLiveViewError("Start camera session before reconnecting live view.");
      return;
    }
    if (!liveViewOpen) {
      openLiveView();
      return;
    }
    setLiveViewState("opening");
    setLiveViewError(null);
    setLiveMediaSize(null);
    setLiveViewReloadToken((current) => current + 1);
  }

  function liveMonitorStateFor(result: LiveMotionEvaluateResponse): LiveMonitorState {
    if (result.status === "decode_failed" || result.session_status === "error") {
      return "failed";
    }
    if (result.session_status === "cooldown") {
      return "cooldown";
    }
    if (result.activity_detected) {
      return "activity";
    }
    if (
      result.status === "start_session_required" ||
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

  async function startBackendLiveMonitoring() {
    if (!detail) {
      return;
    }
    if (liveMotionInFlightRef.current) {
      return;
    }
    liveMotionInFlightRef.current = true;
    setLiveMotionError(null);
    setIsEvaluatingLiveMotion(true);
    try {
      const sensitivitySettings = liveMonitorSensitivitySettings[liveMonitorSensitivity];
      const result = await apiClient.startLiveMotionMonitor(detail.stream.id, {
        save_best_frame: true,
        create_review_activity: false,
        min_changed_ratio: sensitivitySettings.min_changed_ratio,
        pixel_delta_threshold: sensitivitySettings.pixel_delta_threshold,
        max_frames: sensitivitySettings.max_frames,
        min_triggered_frames: 1,
        focus_zone_id: liveMotionFocusZoneId || null,
        interval_seconds: sensitivitySettings.interval_ms / 1000,
        notes: null,
      });
      if (result.best_media_asset_id) {
        await refreshSavedImages();
      }
      if (supportsBackendLiveSession(detail.playback)) {
        const status = await refreshLiveCameraSessionStatus(detail);
        setIsLiveMonitoring(status?.monitor_running ?? true);
      }
      setLiveMotionResult(result);
      setLiveMonitorState(liveMonitorStateFor(result));
    } catch (caught) {
      setLiveMonitorState("failed");
      setLiveMotionError(
        caught instanceof Error ? caught.message : "Could not monitor live motion.",
      );
    } finally {
      liveMotionInFlightRef.current = false;
      setIsEvaluatingLiveMotion(false);
    }
  }

  async function createLiveReviewActivity() {
    if (!detail) {
      return;
    }
    setIsCreatingLiveReviewActivity(true);
    setLiveMotionError(null);
    try {
      const result = await apiClient.createLiveMotionReviewActivity(detail.stream.id);
      if (result.review_queue_item_id) {
        setLiveMotionResult((current) =>
          current
            ? {
                ...current,
                review_activity_created: result.review_activity_created,
                review_activity_reused: result.review_activity_reused,
                review_activity_already_exists: result.review_activity_already_exists,
                review_activity_available: false,
                motion_evidence_id: result.motion_evidence_id,
                event_id: result.event_id,
                visit_id: result.visit_id,
                review_queue_item_id: result.review_queue_item_id,
                review_status: result.review_status,
                suggested_label: result.suggested_label,
                suggestion_id: result.suggestion_id,
                suggestion_confidence: result.suggestion_confidence,
                best_media_asset_id: result.media_asset_id ?? current.best_media_asset_id,
                media_asset_id: result.media_asset_id ?? current.media_asset_id,
                activity_session_id: result.activity_session_id ?? current.activity_session_id,
                activity_detection_count:
                  result.activity_detection_count || current.activity_detection_count,
                activity_started_at: result.activity_started_at ?? current.activity_started_at,
                activity_last_seen_at: result.activity_last_seen_at ?? current.activity_last_seen_at,
                message: result.message,
                last_evaluation_message: result.message,
              }
            : current,
        );
        await onReviewActivityCreated();
      } else {
        setLiveMotionError(result.message);
      }
      await refreshLiveCameraSessionStatus(detail);
    } catch (caught) {
      setLiveMotionError(
        caught instanceof Error ? caught.message : "Could not create review activity.",
      );
    } finally {
      setIsCreatingLiveReviewActivity(false);
    }
  }

  async function startLiveMonitoring() {
    if (!detail) {
      return;
    }
    if (!supportsLiveMotionMonitoring(detail.playback)) {
      setLiveMonitorState("failed");
      setLiveMotionError("Live monitoring is available when MockingBird serves this live stream.");
      return;
    }
    if (supportsBackendLiveSession(detail.playback) && liveSession?.status !== "running") {
      setLiveMonitorState("failed");
      setLiveMotionError("Start camera session before monitoring.");
      return;
    }
    if (!supportsBackendLiveSession(detail.playback)) {
      setLiveMonitorState("failed");
      setLiveMotionError("Live monitoring requires a backend camera session.");
      return;
    }
    setLiveMotionResult(null);
    setLiveMotionError(null);
    setLiveMonitorState("waiting");
    setIsLiveMonitoring(true);
    await startBackendLiveMonitoring();
  }

  async function stopLiveMonitoring() {
    if (detail && supportsBackendLiveSession(detail.playback)) {
      try {
        const status = await apiClient.stopLiveMotionMonitor(detail.stream.id);
        setLiveSession(status);
      } catch (caught) {
        setLiveMotionError(
          caught instanceof Error ? caught.message : "Could not stop live monitoring.",
        );
      }
    }
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
    const wasLiveMonitoring = isLiveMonitoring || Boolean(liveSession?.monitor_running);
    setIsCapturingFrame(true);
    setCaptureError(null);
    setCaptureResult(null);
    try {
      const result = await apiClient.captureLocalCameraFrame(detail.stream.id);
      setCaptureResult(result);
      if (supportsBackendLiveSession(detail.playback)) {
        const status = await refreshLiveCameraSessionStatus(detail);
        if (wasLiveMonitoring && status?.monitor_running) {
          setIsLiveMonitoring(true);
        }
      }
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
    if (detail && hasRealLivePlayback(detail.playback)) {
      if (!liveViewOpen) {
        setZoneError("Open Live view to draw zones on the camera stream.");
        return;
      }
      if (liveViewState !== "streaming") {
        setZoneError("Wait for the live stream to start before drawing zones.");
        return;
      }
    }
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

  function handleLiveDrawStart(event: ReactPointerEvent<HTMLElement>) {
    if (!drawMode) {
      return;
    }
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    handleDrawStart(pointFromPointer(event));
  }

  function handleLiveDrawMove(event: ReactPointerEvent<HTMLElement>) {
    if (!drawMode || event.buttons !== 1) {
      return;
    }
    handleDrawMove(pointFromPointer(event));
  }

  function handleLiveDrawEnd(event: ReactPointerEvent<HTMLElement>) {
    if (!drawMode) {
      return;
    }
    event.preventDefault();
    handleDrawEnd(pointFromPointer(event));
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
  const backendLiveSessionSupported = supportsBackendLiveSession(detail.playback);
  const liveSessionRunning = liveSession?.status === "running";
  const liveSessionStarting = liveSession?.status === "starting";
  const liveSessionFailed = liveSession?.status === "failed";
  const liveUrl = liveStreamUrl(detail.playback, detail.stream.id);
  const liveElementKey = `${liveUrl ?? "no-live-url"}-${liveViewReloadToken}`;
  const liveViewStatusLabel =
    backendLiveSessionSupported && liveSessionRunning && !liveViewOpen
      ? "Session running"
      : liveViewState === "streaming"
      ? "Streaming"
      : liveViewState === "opening"
        ? "Opening"
        : liveViewState === "failed"
          ? "Failed"
          : liveViewState === "no_frames"
            ? "No frames"
            : "Ready";
  const liveViewTone =
    liveSessionFailed || liveViewState === "failed" || liveViewState === "no_frames"
      ? "review"
      : liveViewState === "streaming" || liveSessionRunning
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
  const liveSessionRuntimeLimit =
    liveSession?.max_runtime_seconds != null
      ? `${Math.round(liveSession.max_runtime_seconds / 60)}m max`
      : "30m max";
  const liveSessionNewestFrameLabel = formatAgeMs(liveSession?.latest_frame_age_ms);
  const liveSessionFrameCount = liveSession?.frame_count ?? 0;
  const captureSaved = captureResult?.status === "saved";
  const latestSavedImage = savedImageAssets[0] ?? null;
  const savedImageCount = savedImageAssets.length;
  const canCheckMotion = savedImageCount >= 2;
  const motionPair = latestMotionPair(savedImageAssets);
  const motionActionLabel = canCheckMotion
    ? "Compare captured frames"
    : "Capture another frame to check motion";
  const motionCreatedEvidence = motionResult?.created_evidence[0] ?? null;
  const liveReviewQueueItemId = liveMotionResult?.review_queue_item_id ?? null;
  const liveReviewQueueContext = liveReviewQueueItemId
    ? {
        source: "live-motion" as const,
        search: liveReviewQueueItemId,
        status: "unreviewed" as const,
      }
    : null;
  const hasLocalLiveReviewQueueItem = Boolean(
    liveReviewQueueItemId && !streamReviewItems.some((item) => item.id === liveReviewQueueItemId),
  );
  const streamReviewCount = streamReviewItems.length + (hasLocalLiveReviewQueueItem ? 1 : 0);
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
    captureResult?.capture_source === "live_camera_session" &&
    (isLiveMonitoring || liveSession?.monitor_running)
      ? "Captured current frame; camera and monitoring are still running."
      : captureResult?.capture_source === "live_camera_session"
      ? "Saved current session frame. It will not appear in Bird Log until you create/review activity."
      : "Saved one local camera frame. It will not appear in Bird Log until you create/review activity.";
  const showManualSavedFrameComparison = Boolean(
    !isLiveMonitoring &&
      (captureSaved || motionResult || motionError || savedImageError || isLoadingSavedImages),
  );
  const captureButtonLabel =
    isCapturingFrame
      ? "Capturing..."
      : liveViewOpen || liveSessionRunning
        ? "Capture current frame"
        : "Capture frame";
  const liveActivityDetected = Boolean(liveMotionResult?.activity_detected);
  const liveReviewActivityCreated = Boolean(
    liveMotionResult?.review_activity_created ||
      liveReviewQueueItemId ||
      liveMotionResult?.created_evidence.length,
  );
  const liveActivityZone = liveMotionResult?.strongest_zone_id
    ? detail.zones.find((zone) => zone.id === liveMotionResult.strongest_zone_id)
    : null;
  const liveStrongestZoneName =
    liveMotionResult?.strongest_zone_name ?? liveActivityZone?.name ?? null;
  const liveStrongestZoneType =
    liveMotionResult?.strongest_zone_type ?? liveActivityZone?.zone_type ?? null;
  const liveSuppressedZones = liveMotionResult?.suppressed_zone_summaries ?? [];
  const liveSuppressedMessage =
    liveMotionResult?.activity_detected === false
      ? liveMotionResult.activity_summary ?? suppressedZoneMessage(liveSuppressedZones)
      : suppressedZoneMessage(liveSuppressedZones);
  const liveActivityAreaLabel =
    liveStrongestZoneName ??
    liveMotionResult?.strongest_activity_area_label ??
    (liveMotionResult?.uses_auto_regions ? "auto area" : "unzoned activity");
  const liveActivityTitle =
    liveReviewActivityCreated
      ? `Review activity created for ${liveActivityAreaLabel}`
      : `Activity detected in ${liveActivityAreaLabel}`;
  const liveBestFrameMessage =
    liveMotionResult?.best_media_asset_id && liveStrongestZoneName
      ? `Best frame saved from ${liveStrongestZoneName}.`
      : liveMotionResult?.best_media_asset_id
        ? "Best frame saved from the strongest live activity area."
        : liveMotionResult?.activity_session_id
          ? "Best frame selected for this visit session."
          : "Best frame is unavailable.";
  const liveBestFrameUrl = liveMotionResult?.best_media_asset_id
    ? apiClient.mediaFileUrl(liveMotionResult.best_media_asset_id)
    : null;
  const liveActivityDetectionCount = liveMotionResult?.activity_detection_count ?? 0;
  const liveActivityBestChangeLabel = formatPercent(
    liveMotionResult?.activity_best_changed_ratio ?? liveMotionResult?.strongest_changed_ratio,
  );
  const liveActivityBestFrameSequence =
    liveMotionResult?.activity_best_frame_sequence ?? liveMotionResult?.best_frame_sequence;
  const liveBestFrameTime = liveMotionResult?.best_frame_captured_at
    ? formatDateTime(liveMotionResult.best_frame_captured_at)
    : null;
  const liveLastChecked = liveMotionResult?.evaluated_at
    ? formatDateTime(liveMotionResult.evaluated_at)
    : null;
  const liveLastActivity = liveMotionResult?.activity_detected
    ? `${liveBestFrameTime ?? liveLastChecked ?? "Recent check"} / ${liveActivityAreaLabel}`
    : null;
  const liveCooldownLabel =
    liveMotionResult?.session_status === "cooldown"
      ? liveMotionResult.cooldown_remaining_seconds != null
        ? `${liveMotionResult.cooldown_remaining_seconds}s remaining`
        : "waiting for quiet period"
      : null;
  const liveSensitivityLabel = liveMonitorSensitivitySettings[liveMonitorSensitivity].label;
  const liveStrongestChangeLabel = formatPercent(liveMotionResult?.strongest_changed_ratio);
  const liveStrongestThresholdLabel = formatPercent(
    liveMotionResult?.effective_threshold_used ??
    liveMotionResult?.threshold_used ??
      liveMotionResult?.strongest_zone_min_changed_ratio ??
      liveMotionResult?.min_changed_ratio,
  );
  const liveThresholdSourceLabel = liveMotionResult?.threshold_source
    ? formatLabel(liveMotionResult.threshold_source)
    : "Requested";
  const liveStrongestPairLabel =
    liveMotionResult?.frame_pair_sequences?.length === 2
      ? `${liveMotionResult.frame_pair_sequences[0]}->${liveMotionResult.frame_pair_sequences[1]}`
      : liveMotionResult?.strongest_frame_start_sequence &&
          liveMotionResult?.strongest_frame_end_sequence
        ? `${liveMotionResult.strongest_frame_start_sequence}->${liveMotionResult.strongest_frame_end_sequence}`
        : "n/a";
  const liveChangedPixelsLabel =
    liveMotionResult?.changed_pixels != null &&
    (liveMotionResult.total_scored_pixels ?? liveMotionResult.total_pixels) != null
      ? `${liveMotionResult.changed_pixels}/${
          liveMotionResult.total_scored_pixels ?? liveMotionResult.total_pixels
        }`
      : "n/a";
  const liveFineMotionLabel = liveMotionResult?.fine_motion_applied ? "applied" : "standard";
  const liveMarginLabel = formatPercent(liveMotionResult?.margin_to_threshold);
  const liveMeanDeltaLabel =
    liveMotionResult?.mean_delta != null ? liveMotionResult.mean_delta.toFixed(1) : "n/a";
  const liveCadenceLabel =
    liveMotionResult?.evaluation_cadence_seconds != null
      ? `${liveMotionResult.evaluation_cadence_seconds.toFixed(2)}s`
      : `${liveMonitorSensitivitySettings[liveMonitorSensitivity].interval_ms / 1000}s`;
  const liveQualityWarnings = liveMotionResult?.image_quality_warnings ?? [];
  const reviewableLiveZones = detail.zones.filter(isReviewableZone);
  const feederFocusZone = reviewableLiveZones.find((zone) => zone.zone_type === "feeder");
  const liveFocusZone =
    reviewableLiveZones.find((zone) => zone.id === liveMotionFocusZoneId) ?? null;
  const liveFocusLabel =
    liveMotionResult?.focus_zone_name ??
    liveFocusZone?.name ??
    (liveMotionFocusZoneId ? "Selected Zone" : "All Zones");
  const cameraSettingRows = Object.entries(
    (liveSession?.camera_settings ?? detail.playback.camera_settings ?? {}) as Record<
      string,
      unknown
    >,
  ).filter(([, value]) => value != null && String(value).trim());
  const liveLastError =
    liveMotionResult?.last_error ?? liveMotionError ?? liveSessionError ?? null;
  const showLiveMonitorFacts = Boolean(isLiveMonitoring || liveMotionResult || liveSession);
  const liveWorkflowState =
    liveViewError || liveMotionError || liveSessionError || liveMotionResult?.last_error
      ? "error"
      : liveReviewActivityCreated
        ? "review_created"
        : liveMotionResult?.session_status === "cooldown"
          ? "cooldown"
        : liveActivityDetected
          ? "activity"
          : liveSuppressedZones.length > 0
            ? "ignored"
          : isLiveMonitoring
            ? "monitoring"
            : liveViewOpen && liveViewState === "streaming"
              ? "streaming"
              : liveSessionRunning
                ? "streaming"
              : liveViewState === "opening" || liveSessionStarting
                ? "opening"
                : "ready";
  const liveWorkflowMessage =
    liveWorkflowState === "error"
      ? liveViewError ??
        liveMotionError ??
        liveSessionError ??
        liveMotionResult?.last_error ??
        "Live camera needs attention."
      : liveWorkflowState === "review_created"
        ? "Review activity created. Open Review to confirm/correct."
        : liveWorkflowState === "cooldown"
          ? liveMotionResult?.last_evaluation_message ?? "Cooldown active."
        : liveWorkflowState === "activity"
          ? liveMotionResult?.activity_summary ?? "Activity detected."
          : liveWorkflowState === "ignored"
            ? liveSuppressedMessage ?? "Motion ignored in privacy/ignore zone."
          : liveWorkflowState === "monitoring"
            ? "Watching recent live frames for activity."
            : liveWorkflowState === "streaming"
              ? backendLiveSessionSupported
                ? "Camera session is running."
                : "Live camera is running."
              : liveWorkflowState === "opening"
                ? backendLiveSessionSupported
                  ? "Starting camera session..."
                  : "Opening live view..."
                : backendLiveSessionSupported
                  ? "Start camera session to draw zones and monitor activity."
                  : "Open Live view to draw zones on the camera stream.";
  const liveOverlayStyle = containedMediaRectStyle(liveMediaSize);
  const livePlaybackNeedsAttention =
    liveViewOpen &&
    (liveViewState === "opening" ||
      liveViewState === "failed" ||
      liveViewState === "no_frames" ||
      Boolean(liveViewError));
  const liveZonesVisible = (showLiveZones || drawMode) && !livePlaybackNeedsAttention;
  const activeZoneCount = detail.zones.filter((zone) => zone.is_active).length;

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
          {streamReviewCount > 0 ? (
            <button className="secondary-action" onClick={() => onOpenReview()}>
              Review {streamReviewCount}
            </button>
          ) : null}
          <button className="secondary-action" onClick={onOpenExports}>
            Dataset Exports
          </button>
          {streamReviewCount > 0 ? (
            <StatusPill label={`${streamReviewCount} needs review`} tone="review" />
          ) : (
            <StatusPill label="Review clear" tone="good" />
          )}
        </div>
      </div>

      {realLivePlayback ? (
        <section className="stream-live-hero" aria-label={`${detail.stream.name} live stream`}>
          <div className="stream-live-toolbar">
            <div className="stream-live-title">
              <span className="stream-live-eyebrow">{sourceDisplay}</span>
              <strong>Live camera</strong>
              <span>{detail.stream.name}</span>
            </div>
            <div className="stream-live-badges">
              <StatusPill label={liveViewStatusLabel} tone={liveViewTone} />
              <StatusPill label={liveMonitorStatusLabel} tone={liveMonitorTone} />
              {streamReviewCount > 0 ? (
                <StatusPill label={`${streamReviewCount} needs review`} tone="review" />
              ) : (
                <StatusPill label="Review clear" tone="good" />
              )}
            </div>
          </div>

          <div className="stream-live-meta-grid">
            <span>
              <strong>Playback</strong> {formatLabel(detail.playback.playback_kind)}
            </span>
            <span>
              <strong>Zones</strong> {activeZoneCount} active / {detail.zones.length} total
            </span>
            {detail.playback.local_camera_device_display ? (
              <span>
                <strong>Camera</strong> {detail.playback.local_camera_device_display}
              </span>
            ) : null}
            {detail.playback.windows_camera_name_display ? (
              <span>
                <strong>Camera</strong> {detail.playback.windows_camera_name_display}
              </span>
            ) : null}
            {detail.playback.live_stream_url_display ? (
              <span>
                <strong>Stream URL</strong> {detail.playback.live_stream_url_display}
              </span>
            ) : null}
            {detail.playback.windows_ffmpeg_binary_display ? (
              <span>
                <strong>Bridge</strong> {detail.playback.windows_ffmpeg_binary_display}
              </span>
            ) : null}
            {backendLiveSessionSupported ? (
              <>
                <span>
                  <strong>Session</strong> {formatLabel(liveSession?.status ?? "stopped")}
                </span>
                <span>
                  <strong>Frames</strong> {liveSessionFrameCount}
                </span>
                <span>
                  <strong>Runtime</strong> {liveSessionRuntimeLimit}
                </span>
              </>
            ) : null}
          </div>

          {liveActivityDetected || liveReviewActivityCreated ? null : (
            <div className="detail-actions stream-live-actions stream-live-primary-actions">
              {backendLiveSessionSupported && !liveSessionRunning ? (
                <button
                  className="primary-action"
                  disabled={!liveUrl || isStartingLiveSession || isStoppingLiveSession}
                  onClick={() => void startLiveCameraSession(true)}
                  type="button"
                >
                  {isStartingLiveSession ? "Starting..." : "Start camera"}
                </button>
              ) : !backendLiveSessionSupported && !liveViewOpen ? (
                <button
                  className="primary-action"
                  disabled={!liveUrl || isCapturingFrame}
                  onClick={openLiveView}
                  type="button"
                >
                  Open Live view
                </button>
              ) : isLiveMonitoring ? (
                <>
                  <button
                    className="primary-action"
                    onClick={() => void stopLiveMonitoring()}
                    type="button"
                  >
                    Stop monitoring
                  </button>
                  {liveViewOpen ? (
                    <button className="secondary-action" onClick={stopLiveView} type="button">
                      Hide live view
                    </button>
                  ) : (
                    <button className="secondary-action" onClick={openLiveView} type="button">
                      Open live view
                    </button>
                  )}
                  {backendLiveSessionSupported ? (
                    <button
                      className="secondary-action"
                      disabled={isStoppingLiveSession}
                      onClick={() => void stopLiveCameraSession()}
                      type="button"
                    >
                      {isStoppingLiveSession ? "Stopping..." : "Stop camera"}
                    </button>
                  ) : null}
                </>
              ) : (
                <>
                  <button
                    className="primary-action"
                    disabled={
                      !liveUrl ||
                      !canMonitorLiveMotion ||
                      isEvaluatingLiveMotion ||
                      (backendLiveSessionSupported && !liveSessionRunning) ||
                      (!backendLiveSessionSupported && !liveViewOpen)
                    }
                    onClick={() => void startLiveMonitoring()}
                    type="button"
                  >
                    {isEvaluatingLiveMotion ? "Checking..." : "Start monitoring"}
                  </button>
                  {liveViewOpen ? (
                    <button className="secondary-action" onClick={stopLiveView} type="button">
                      Hide live view
                    </button>
                  ) : (
                    <button
                      className="secondary-action"
                      disabled={backendLiveSessionSupported && !liveSessionRunning}
                      onClick={openLiveView}
                      type="button"
                    >
                      Open live view
                    </button>
                  )}
                  {liveViewOpen ? (
                    <button className="secondary-action" onClick={refreshLiveView} type="button">
                      Reconnect stream
                    </button>
                  ) : null}
                  {backendLiveSessionSupported ? (
                    <button
                      className="secondary-action"
                      disabled={isStoppingLiveSession}
                      onClick={() => void stopLiveCameraSession()}
                      type="button"
                    >
                      {isStoppingLiveSession ? "Stopping..." : "Stop camera"}
                    </button>
                  ) : null}
                </>
              )}
              {liveViewOpen || liveSessionRunning ? (
                <div className="stream-live-sensitivity" aria-label="Monitoring sensitivity">
                  {liveMonitorSensitivityOptions.map((option) => (
                    <button
                      className={liveMonitorSensitivity === option ? "selected" : ""}
                      disabled={isLiveMonitoring || isEvaluatingLiveMotion}
                      key={option}
                      onClick={() => setLiveMonitorSensitivity(option)}
                      type="button"
                    >
                      {liveMonitorSensitivitySettings[option].label}
                    </button>
                  ))}
                </div>
              ) : null}
              <button
                className={drawMode ? "primary-action" : "secondary-action"}
                disabled={
                  drawMode
                    ? isSavingZone
                    : !liveViewOpen || liveViewState !== "streaming" || isSavingZone
                }
                onClick={drawMode ? cancelDrawMode : startDrawMode}
                type="button"
              >
                {drawMode ? "Cancel draw" : "Draw new zone"}
              </button>
              <button
                aria-pressed={showLiveZones}
                className="secondary-action"
                disabled={drawMode || !detail.zones.length}
                onClick={() => setShowLiveZones((current) => !current)}
                type="button"
              >
                {showLiveZones ? "Hide zones" : "Show zones"}
              </button>
            </div>
          )}

          {backendLiveSessionSupported && sourceProviderConfig?.provider_key === "local_usb" ? (
            <form className="stream-live-secondary-panel" onSubmit={handleSaveCameraTuning}>
              <div className="stream-live-panel-header">
                <div>
                  <strong>Camera tuning</strong>
                  <span>Preview 1280x720 at 10-15fps is a good feeder starting point.</span>
                </div>
                <div className="detail-actions stream-live-actions">
                  <button
                    className="secondary-action"
                    disabled={isSavingCameraTuning}
                    type="submit"
                  >
                    {isSavingCameraTuning ? "Saving..." : "Save settings"}
                  </button>
                  {backendLiveSessionSupported ? (
                    <button
                      className="secondary-action"
                      disabled={isSavingCameraTuning || isStartingLiveSession || isStoppingLiveSession}
                      onClick={() => void restartLiveCameraSession()}
                      type="button"
                    >
                      Restart camera
                    </button>
                  ) : null}
                </div>
              </div>
              <div className="stream-live-tuning-grid">
                {cameraTuningKeys.map((key) => (
                  <label key={key}>
                    <span>{cameraTuningLabels[key]}</span>
                    <input
                      value={cameraTuningDraft[key]}
                      onChange={(event) => updateCameraTuningDraft(key, event.target.value)}
                      placeholder={cameraTuningPlaceholders[key]}
                    />
                  </label>
                ))}
              </div>
              {cameraSettingRows.length > 0 ? (
                <div className="stream-live-monitor-facts">
                  {cameraSettingRows.map(([key, value]) => (
                    <span key={key}>
                      <strong>{formatLabel(key)}</strong> {String(value)}
                    </span>
                  ))}
                </div>
              ) : null}
              <span className="stream-live-hint">
                Size, framerate, and input format are passed to ffmpeg when supported.
                Brightness, contrast, exposure, and zoom notes may need the camera driver app.
              </span>
              {cameraTuningMessage ? (
                <span className="stream-live-hint">{cameraTuningMessage}</span>
              ) : null}
              {cameraTuningError ? (
                <span className="stream-live-hint is-error">{cameraTuningError}</span>
              ) : null}
            </form>
          ) : null}

          {canMonitorLiveMotion ? (
            <div className="stream-live-secondary-panel">
              <div className="stream-live-panel-header">
                <div>
                  <strong>Motion calibration</strong>
                  <span>
                    Strongest {liveStrongestZoneName ?? "area"} change {liveStrongestChangeLabel},
                    threshold {liveStrongestThresholdLabel}.
                  </span>
                </div>
                <label className="stream-live-debug-toggle">
                  <input
                    checked={showLiveMotionDebug}
                    onChange={(event) => setShowLiveMotionDebug(event.target.checked)}
                    type="checkbox"
                  />
                  Show motion debug
                </label>
              </div>
              <div className="stream-live-calibration-grid">
                <label>
                  <span>Monitoring focus</span>
                  <select
                    disabled={isLiveMonitoring || isEvaluatingLiveMotion}
                    value={liveMotionFocusZoneId}
                    onChange={(event) => setLiveMotionFocusZoneId(event.target.value)}
                  >
                    <option value="">All reviewable Zones</option>
                    {reviewableLiveZones.map((zone) => (
                      <option key={zone.id} value={zone.id}>
                        {zone.name} ({formatLabel(zone.zone_type)})
                      </option>
                    ))}
                  </select>
                </label>
                <div className="detail-actions stream-live-actions">
                  {feederFocusZone ? (
                    <button
                      className="secondary-action"
                      disabled={isLiveMonitoring || isEvaluatingLiveMotion}
                      onClick={() => setLiveMotionFocusZoneId(feederFocusZone.id)}
                      type="button"
                    >
                      Use Feeder Zone
                    </button>
                  ) : null}
                  <button
                    className="secondary-action"
                    disabled={isLiveMonitoring || isEvaluatingLiveMotion || !liveMotionFocusZoneId}
                    onClick={() => setLiveMotionFocusZoneId("")}
                    type="button"
                  >
                    Clear focus
                  </button>
                </div>
              </div>
              <div className="stream-live-monitor-facts">
                <span>
                  <strong>Focus</strong> {liveFocusLabel}
                </span>
                <span>
                  <strong>Sensitivity</strong> {liveSensitivityLabel}
                </span>
                <span>
                  <strong>Cadence</strong> {liveCadenceLabel}
                </span>
                <span>
                  <strong>Changed pixels</strong> {liveChangedPixelsLabel}
                </span>
                <span>
                  <strong>Fine motion</strong> {liveFineMotionLabel}
                </span>
                <span>
                  <strong>Threshold source</strong> {liveThresholdSourceLabel}
                </span>
                <span>
                  <strong>Margin</strong> {liveMarginLabel}
                </span>
                <span>
                  <strong>Mean delta</strong> {liveMeanDeltaLabel}
                </span>
                <span>
                  <strong>Frame pair</strong> {liveStrongestPairLabel}
                </span>
              </div>
              {liveMotionResult?.near_miss ? (
                <span className="stream-live-hint">
                  Near miss: tighten the feeder Zone, use feeder focus, or move the camera closer.
                </span>
              ) : null}
              {liveQualityWarnings.length > 0 ? (
                <div className="stream-live-suppressed-list">
                  <strong>Image quality</strong>
                  {liveQualityWarnings.map((warning) => (
                    <span key={warning}>{warning}</span>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}

          <div className={`stream-live-frame${drawMode ? " draw-mode" : ""}`}>
            <div className="stream-live-media-layer">
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
                    onLoadedMetadata={(event) => {
                      const video = event.currentTarget;
                      setLiveMediaSize({
                        width: video.videoWidth || 16,
                        height: video.videoHeight || 9,
                      });
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
                    onLoad={(event) => {
                      const image = event.currentTarget;
                      setLiveViewState("streaming");
                      setLiveViewError(null);
                      setLiveMediaSize({
                        width: image.naturalWidth || 16,
                        height: image.naturalHeight || 9,
                      });
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
                  <strong>
                    {liveUrl
                      ? backendLiveSessionSupported && !liveSessionRunning
                        ? "Camera session stopped"
                        : "Live camera ready"
                      : "Live camera unavailable"}
                  </strong>
                  <span>
                    {liveUrl
                      ? backendLiveSessionSupported && !liveSessionRunning
                        ? "Start camera session to feed live view, capture, and monitoring."
                        : "Open Live view to draw zones on the camera stream."
                      : detail.playback.setup_hint ?? detail.playback.message}
                  </span>
                </div>
              )}
            </div>
            <div
              className={`stream-live-zone-surface${drawMode ? " draw-mode" : ""}${
                liveZonesVisible ? "" : " is-hidden"
              }`}
              style={liveOverlayStyle}
              onPointerDown={handleLiveDrawStart}
              onPointerMove={handleLiveDrawMove}
              onPointerUp={handleLiveDrawEnd}
            >
              <svg
                aria-label="Live stream zones"
                className="zone-overlay"
                viewBox="0 0 100 100"
                preserveAspectRatio="none"
              >
                {detail.zones.map((zone) => (
                  <polygon
                    key={zone.id}
                    className={`zone-shape zone-${zone.zone_type}${
                      selectedZoneId === zone.id ? " zone-selected" : ""
                    }${zone.is_active ? "" : " zone-inactive"}${
                      showLiveMotionDebug && liveMotionResult?.strongest_zone_id === zone.id
                        ? " zone-motion-strongest"
                        : ""
                    }${
                      showLiveMotionDebug && liveMotionFocusZoneId === zone.id
                        ? " zone-motion-focus"
                        : ""
                    }`}
                    points={polygonPoints(zone.polygon)}
                    aria-label={`Select ${zone.name}`}
                    role="button"
                    tabIndex={0}
                    onClick={(event) => {
                      event.stopPropagation();
                      if (!drawMode) {
                        setSelectedZoneId(zone.id);
                      }
                    }}
                    onKeyDown={(event) => {
                      if (!drawMode && (event.key === "Enter" || event.key === " ")) {
                        event.preventDefault();
                        setSelectedZoneId(zone.id);
                      }
                    }}
                  />
                ))}
                {draftPolygon ? (
                  <polygon className="zone-shape zone-draft" points={polygonPoints(draftPolygon)} />
                ) : null}
              </svg>
              {detail.zones.map((zone) => {
                const anchor = zoneLabelAnchor(zone);
                const expandedLabel = drawMode || selectedZoneId === zone.id;
                return (
                  <button
                    className={`zone-label live-zone-label zone-label-${zone.zone_type}${
                      selectedZoneId === zone.id ? " zone-label-selected" : ""
                    }${zone.is_active ? "" : " zone-label-inactive"}`}
                    key={zone.id}
                    type="button"
                    style={{ left: `${anchor.x * 100}%`, top: `${anchor.y * 100}%` }}
                    title={`${zone.name} (${formatLabel(zone.zone_type)})`}
                    onClick={() => {
                      if (!drawMode) {
                        setSelectedZoneId(zone.id);
                      }
                    }}
                  >
                    {liveZoneLabel(zone, expandedLabel)}
                  </button>
                );
              })}
            </div>
          </div>

          <div
            className={`stream-live-state-card${
              liveWorkflowState === "error" ? " is-error" : ""
            }`}
          >
            <strong>{liveWorkflowMessage}</strong>
            {liveWorkflowState === "error" && liveHelpText ? <span>{liveHelpText}</span> : null}
            {liveWorkflowState !== "error" && !liveActivityDetected ? (
              <span>
                {canMonitorLiveMotion
                  ? "Zones are drawn over this live stream and used by monitoring."
                  : "Zones are drawn over this live stream. Live monitoring is available when MockingBird serves the stream through a local bridge."}
              </span>
            ) : null}
            {showLiveMonitorFacts ? (
              <div className="stream-live-monitor-facts">
                {backendLiveSessionSupported ? (
                  <>
                    <span>
                      <strong>Camera session</strong>{" "}
                      {formatLabel(liveSession?.status ?? "stopped")}
                    </span>
                    <span>
                      <strong>Session frames</strong> {liveSessionFrameCount}
                    </span>
                    <span>
                      <strong>Session newest</strong> {liveSessionNewestFrameLabel}
                    </span>
                  </>
                ) : null}
                <span>
                  <strong>Recent frames</strong>{" "}
                  {liveMotionResult
                    ? `${liveMotionResult.recent_frame_count}/${liveMotionResult.buffer_capacity}`
                    : "waiting"}
                </span>
                <span>
                  <strong>Newest frame</strong>{" "}
                  {formatAgeMs(liveMotionResult?.newest_frame_age_ms)}
                </span>
                <span>
                  <strong>Last checked</strong> {liveLastChecked ?? "not yet"}
                </span>
                <span>
                  <strong>Monitor</strong> {isLiveMonitoring ? "running" : "not running"}
                </span>
                <span>
                  <strong>Sensitivity</strong> {liveSensitivityLabel}
                </span>
                <span>
                  <strong>Last activity</strong> {liveLastActivity ?? "none yet"}
                </span>
                <span>
                  <strong>Strongest zone</strong> {liveStrongestZoneName ?? "none yet"}
                </span>
                <span>
                  <strong>Strongest change</strong> {liveStrongestChangeLabel}
                </span>
                <span>
                  <strong>Threshold</strong> {liveStrongestThresholdLabel}
                </span>
                <span>
                  <strong>Frame pair</strong> {liveStrongestPairLabel}
                </span>
                {liveCooldownLabel ? (
                  <span>
                    <strong>Cooldown</strong> {liveCooldownLabel}
                  </span>
                ) : null}
                {liveLastError ? (
                  <span>
                    <strong>Last error</strong> {liveLastError}
                  </span>
                ) : null}
              </div>
            ) : null}
          </div>

          {liveActivityDetected ? (
            <div className="stream-live-activity-card">
              <div className="stream-live-activity-media">
                {liveBestFrameUrl ? (
                  <img alt="Best activity frame" src={liveBestFrameUrl} />
                ) : (
                  <div>
                    <strong>Best frame</strong>
                    <span>
                      {liveMotionResult?.activity_session_id ? "Selected in session" : "Unavailable"}
                    </span>
                  </div>
                )}
              </div>
              <div className="stream-live-activity-body">
                <div className="item-title-row">
                  <strong>
                    {liveActivityTitle}
                  </strong>
                  <div className="stream-live-activity-pills">
                    {liveStrongestZoneType ? (
                      <StatusPill label={formatLabel(liveStrongestZoneType)} tone="quiet" />
                    ) : null}
                    <StatusPill
                      label={liveReviewActivityCreated ? "Needs review" : "Visit session"}
                      tone="review"
                    />
                  </div>
                </div>
                <p>
                  {liveReviewActivityCreated
                    ? `Open Review to confirm or correct the activity in ${liveActivityAreaLabel}.`
                    : liveMotionResult?.uses_auto_regions
                      ? "Automatic activity areas are evidence only; add or select a named Zone before review activity."
                      : `${liveBestFrameMessage} Create a review activity to send it into the correction flow.`}
                </p>
                <div className="stream-live-activity-facts">
                  <span>
                    <strong>Area</strong> {liveActivityAreaLabel}
                  </span>
                  {liveStrongestZoneType ? (
                    <span>
                      <strong>Zone type</strong> {formatLabel(liveStrongestZoneType)}
                    </span>
                  ) : null}
                  <span>
                    <strong>Detected</strong> {liveBestFrameTime ?? "Recent live frame"}
                  </span>
                  <span>
                    <strong>Detections</strong> {liveActivityDetectionCount || 1}
                  </span>
                  <span>
                    <strong>Best frame</strong>{" "}
                    {liveMotionResult?.best_media_asset_id
                      ? "saved"
                      : liveMotionResult?.activity_session_id
                        ? "selected"
                        : "unavailable"}
                  </span>
                  <span>
                    <strong>Frame</strong> {liveActivityBestFrameSequence ?? "n/a"}
                  </span>
                  <span>
                    <strong>Change</strong> {liveActivityBestChangeLabel}
                  </span>
                  <span>
                    <strong>Bird Log</strong> after review
                  </span>
                </div>
                {liveSuppressedZones.length > 0 ? (
                  <div className="stream-live-suppressed-list">
                    <strong>Suppressed motion</strong>
                    {liveSuppressedZones.map((summary) => (
                      <span key={summary.zone_id}>
                        Ignored motion in {suppressedZoneDisplay(summary)}
                      </span>
                    ))}
                  </div>
                ) : null}
                <div className="detail-actions stream-live-actions">
                  {liveReviewActivityCreated ? (
                    <button
                      className="primary-action"
                      onClick={() => onOpenReview(liveReviewQueueContext)}
                      type="button"
                    >
                      Open Review Queue
                    </button>
                  ) : null}
                  {!liveReviewActivityCreated && canCreateLiveReviewActivity ? (
                    <button
                      className="primary-action"
                      disabled={isCreatingLiveReviewActivity}
                      onClick={() => void createLiveReviewActivity()}
                      type="button"
                    >
                      {isCreatingLiveReviewActivity ? "Creating..." : "Create review activity"}
                    </button>
                  ) : null}
                  {liveBestFrameUrl ? (
                    <a className="secondary-action" href={liveBestFrameUrl}>
                      Open saved best frame
                    </a>
                  ) : null}
                  {isLiveMonitoring ? (
                    <button
                      className="secondary-action"
                      onClick={() => void stopLiveMonitoring()}
                      type="button"
                    >
                      Stop monitoring
                    </button>
                  ) : !liveReviewActivityCreated ? (
                    <button
                      className="secondary-action"
                      disabled={
                        !liveUrl ||
                        !canMonitorLiveMotion ||
                        (backendLiveSessionSupported && !liveSessionRunning) ||
                        (!backendLiveSessionSupported && !liveViewOpen)
                      }
                      onClick={() => void startLiveMonitoring()}
                      type="button"
                    >
                      Continue monitoring
                    </button>
                  ) : null}
                  {!liveReviewActivityCreated && streamReviewCount > 0 ? (
                    <button className="text-action" onClick={() => onOpenReview()} type="button">
                      Open Review Queue
                    </button>
                  ) : null}
                </div>
                {liveMotionResult?.warnings.length ? (
                  <span className="stream-live-hint">{liveMotionResult.warnings[0]}</span>
                ) : null}
              </div>
            </div>
          ) : null}

          {canCaptureFrame ? (
            <div className="stream-live-secondary-panel">
              <div className="stream-live-secondary-copy">
                <strong>Manual capture</strong>
                <span>
                  Manual snapshot for evidence/debug. Monitoring saves best frames automatically
                  when activity is detected.
                </span>
              </div>
              <div className="detail-actions stream-live-actions">
                <button
                  className="secondary-action"
                  disabled={isCapturingFrame}
                  onClick={handleCaptureFrame}
                  type="button"
                >
                  {captureButtonLabel}
                </button>
                {captureResult?.media_asset_id ? (
                  <a
                    className="secondary-action"
                    href={apiClient.mediaFileUrl(captureResult.media_asset_id)}
                  >
                    Open saved frame
                  </a>
                ) : null}
              </div>
              {captureResult ? (
                <div
                  className={`stream-live-inline-status${
                    captureResult.status === "saved" ? "" : " is-error"
                  }`}
                >
                  <strong>{captureSaved ? captureSuccessMessage : captureResult.message}</strong>
                  {captureSaved ? (
                    <span>
                      Saved images for this stream: {savedImageCount}
                      {latestSavedImage
                        ? ` · Latest ${latestSavedImage.original_filename || latestSavedImage.filename}`
                        : ""}
                    </span>
                  ) : null}
                </div>
              ) : null}
              {captureError && !captureResult ? (
                <div className="stream-live-inline-status is-error">
                  <strong>{captureError}</strong>
                </div>
              ) : null}
              {showManualSavedFrameComparison ? (
                <div className="stream-live-fallback-panel">
                  <div>
                    <strong>Manual saved-frame comparison</strong>
                    <span>
                      Fallback comparison stays secondary to live monitoring and still requires
                      review before Bird Log or export.
                    </span>
                  </div>
                  {savedImageError ? (
                    <div className="stream-live-inline-status is-error">
                      <strong>{savedImageError}</strong>
                    </div>
                  ) : null}
                  {isLoadingSavedImages ? (
                    <span className="stream-live-hint">Refreshing saved images...</span>
                  ) : null}
                  {motionError ? (
                    <div className="stream-live-inline-status is-error">
                      <strong>{motionError}</strong>
                    </div>
                  ) : null}
                  <div className="detail-actions stream-live-actions">
                    <button
                      className="secondary-action"
                      disabled={!canCheckMotion || isCheckingMotion || isCreatingReviewActivity}
                      onClick={() => void handleCheckMotion(false)}
                      type="button"
                    >
                      {isCheckingMotion ? "Comparing..." : motionActionLabel}
                    </button>
                    {streamReviewCount > 0 ? (
                      <button
                        className="secondary-action"
                        onClick={() => onOpenReview()}
                        type="button"
                      >
                        Open Review Queue
                      </button>
                    ) : null}
                  </div>
                  {!canCheckMotion ? (
                    <span className="stream-live-hint">
                      Motion checks compare two saved frames from this stream.
                    </span>
                  ) : (
                    <span className="stream-live-hint">
                      Comparing:{" "}
                      {motionPair
                        .map((asset) => asset.original_filename || asset.filename)
                        .join(" -> ")}
                    </span>
                  )}
                  {motionResult ? (
                    <div className="stream-live-inline-status">
                      <strong>
                        {motionResult.activity_detected
                          ? "Manual comparison found candidate activity."
                          : "Manual comparison found no activity yet."}
                      </strong>
                      <span>
                        {motionResult.activity_detected
                          ? "Create review activity explicitly before correction, Bird Log, or export."
                          : "Captured frames remain saved media until activity is reviewed."}
                      </span>
                      {motionResult.session_message ? (
                        <span>{motionResult.session_message}</span>
                      ) : null}
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
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
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
                ? "Zones are drawn over this live stream and used by monitoring."
                : "User-authored context for outdoor activity"}
            </span>
            <button
              className="secondary-action"
              disabled={isSavingZone}
              onClick={drawMode ? cancelDrawMode : startDrawMode}
            >
              {drawMode ? "Cancel draw" : realLivePlayback ? "Draw on live stream" : "Draw new zone"}
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
                  {realLivePlayback ? (
                    <span className="meta-text">
                      Drag a rectangle over the live camera surface, then name and save it here.
                    </span>
                  ) : null}
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
            {streamReviewCount > 0 ? (
              <>
                {hasLocalLiveReviewQueueItem ? (
                  <div className="queue-mini">
                    <strong>Live motion activity</strong>
                    <span>Needs review. Bird Log updates after correction.</span>
                  </div>
                ) : null}
                {streamReviewItems.map((item) => (
                  <div className="queue-mini" key={item.id}>
                    <strong>{item.title}</strong>
                    <span>{item.reason}</span>
                  </div>
                ))}
                <button className="secondary-action" onClick={() => onOpenReview()}>
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
