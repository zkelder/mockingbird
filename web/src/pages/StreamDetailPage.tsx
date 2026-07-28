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
  CameraHealthDetailResponse,
  LocalCameraFrameCaptureResponse,
  LiveCameraSessionStatus,
  LiveMotionEvaluateResponse,
  MediaAsset,
  MotionEvaluateSavedMediaResponse,
  Point,
  ReviewQueueItem,
  SourceProviderConfiguration,
  SourceSetupReviewResponse,
  SpeciesCandidatePack,
  Stream,
  StreamMonitoringPolicy,
  StreamPlaybackStatus,
  StreamRuntimeStatus,
  StreamSpeciesCandidatePackSelection,
  StreamVisitSummary,
  Visit,
  VisitDetail,
  VisitEvidenceFrame,
  Zone,
  ZoneActivitySensitivity,
  ZoneMonitoringPolicy,
  ZoneMonitoringPolicyUpdate,
  ZoneType,
} from "../api/types";
import { CurrentFrameView, type CurrentFrameMetadata } from "../components/CurrentFrameView";
import { EmptyState } from "../components/EmptyState";
import { StatusPill } from "../components/StatusPill";
import { StreamPanel } from "../components/StreamPanel";
import { VisitEvidenceSequence } from "../components/VisitEvidenceSequence";
import { formatDateTime, formatLabel } from "../utils";

interface StreamDetailPageProps {
  streamId: string;
  reviewQueue: ReviewQueueItem[];
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenActivity: () => void;
  onOpenInsights: () => void;
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
  onOpenCameraSetup: () => void;
  onReviewActivityCreated: () => Promise<void>;
}

interface StreamDetailState {
  stream: Stream;
  playback: StreamPlaybackStatus;
  setupReview: SourceSetupReviewResponse | null;
  zones: Zone[];
  events: Event[];
  visitsByEvent: Record<string, Visit[]>;
  recentVisits: StreamVisitSummary[];
}

type RecentVisitFilter = "all" | "needs_review" | "reviewed" | "review_outcomes";

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

interface ZoneMonitoringDraft {
  monitoring_enabled: boolean;
  activity_sensitivity: ZoneActivitySensitivity;
  minimum_sustained_activity_seconds: number;
  quiet_period_seconds: number;
  maximum_visit_duration_seconds: number;
  maximum_evidence_frames: number;
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
  | "input_format";

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
    detector_preset: "high_sensitivity" | "normal" | "low_noise";
    interval_ms: number;
    max_frames: number;
  }
> = {
  low: {
    label: "Low noise",
    detector_preset: "low_noise",
    interval_ms: 2500,
    max_frames: 12,
  },
  normal: {
    label: "Normal",
    detector_preset: "normal",
    interval_ms: 1500,
    max_frames: 20,
  },
  high: {
    label: "High sensitivity",
    detector_preset: "high_sensitivity",
    interval_ms: 750,
    max_frames: 24,
  },
};
const liveMonitorSensitivityOptions: LiveMonitorSensitivity[] = ["low", "normal", "high"];
const zoneMonitoringSensitivityOptions: ZoneActivitySensitivity[] = ["low", "normal", "high"];

function zoneMonitoringDraftFromPolicy(policy: ZoneMonitoringPolicy): ZoneMonitoringDraft {
  return {
    monitoring_enabled: policy.monitoring_enabled,
    activity_sensitivity: policy.activity_sensitivity,
    minimum_sustained_activity_seconds: policy.minimum_sustained_activity_seconds,
    quiet_period_seconds: policy.quiet_period_seconds,
    maximum_visit_duration_seconds: policy.maximum_visit_duration_seconds,
    maximum_evidence_frames: policy.maximum_evidence_frames,
  };
}

function zoneMonitoringSummary(policy: ZoneMonitoringPolicy): string {
  return `${formatLabel(policy.activity_sensitivity)} sensitivity · short coherent track opens activity · finish after ${policy.quiet_period_seconds}s quiet`;
}

function zoneSessionPolicyStatus(activity: Record<string, unknown> | null): string | null {
  if (!activity) return null;
  if (activity.finalized_reason === "maximum_duration") {
    return "Visit finalized at this Zone's maximum length.";
  }
  if (activity.finalized_reason === "brief_activity") {
    return "Very brief activity was ignored.";
  }
  if (activity.ready_for_review) return "Visit is finalized and ready for review.";
  return "Activity is open; waiting through this Zone's quiet period.";
}

function pendingAutoCreateReviewCandidatesStorageKey(streamId: string) {
  return `mockingbird:${streamId}:pending-auto-create-review-candidates`;
}

function readPendingAutoCreateReviewCandidates(streamId: string): boolean | null {
  if (typeof window === "undefined") {
    return null;
  }
  let value: string | null = null;
  try {
    value = window.sessionStorage.getItem(
      pendingAutoCreateReviewCandidatesStorageKey(streamId),
    );
  } catch {
    return null;
  }
  if (value === "true") {
    return true;
  }
  if (value === "false") {
    return false;
  }
  return null;
}

function writePendingAutoCreateReviewCandidates(streamId: string, value: boolean) {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.sessionStorage.setItem(
      pendingAutoCreateReviewCandidatesStorageKey(streamId),
      value ? "true" : "false",
    );
  } catch {
    return;
  }
}

const cameraTuningKeys: CameraTuningKey[] = [
  "video_size",
  "preview_video_size",
  "capture_video_size",
  "framerate",
  "input_format",
];

const emptyCameraTuningDraft: CameraTuningDraft = {
  video_size: "",
  preview_video_size: "",
  capture_video_size: "",
  framerate: "",
  input_format: "",
};

const cameraTuningLabels: Record<CameraTuningKey, string> = {
  video_size: "Fallback size",
  preview_video_size: "Preview size",
  capture_video_size: "Capture size",
  framerate: "Framerate",
  input_format: "Input format",
};

const cameraTuningPlaceholders: Record<CameraTuningKey, string> = {
  video_size: "1280x720",
  preview_video_size: "1280x720",
  capture_video_size: "1920x1080",
  framerate: "15",
  input_format: "mjpeg",
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

function isCameraNodePlayback(status?: StreamPlaybackStatus | null): boolean {
  return status?.status === "live_ready" && status.playback_kind === "camera_node";
}

function hasRealLivePlayback(status?: StreamPlaybackStatus | null): boolean {
  return (
    isBrowserPlayablePlayback(status) ||
    isRtspBridgePlayback(status) ||
    isLocalCameraBridgePlayback(status) ||
    isWindowsDshowBridgePlayback(status) ||
    isCameraNodePlayback(status)
  );
}

function cameraHealthLabel(state: CameraHealthDetailResponse["health"]["state"]): string {
  return {
    healthy: "Healthy",
    starting: "Starting",
    waiting_for_capacity: "Waiting for capacity",
    camera_unavailable: "Camera unavailable",
    no_recent_frame: "No recent frame",
    evidence_storage_degraded: "Evidence storage degraded",
    recovering: "Recovering",
    stopped: "Monitoring stopped",
    setup_incomplete: "Setup incomplete",
  }[state];
}

function cameraHealthTone(
  state: CameraHealthDetailResponse["health"]["state"],
): "good" | "review" | "quiet" {
  if (state === "healthy") return "good";
  if (state === "starting" || state === "stopped") return "quiet";
  return "review";
}

function frameAgeLabel(seconds?: number | null): string {
  if (seconds == null) return "Not available";
  if (seconds < 60) return "Under a minute";
  const minutes = Math.floor(seconds / 60);
  return `${minutes} min${minutes === 1 ? "" : "s"}`;
}

function supportsLiveMotionMonitoring(status?: StreamPlaybackStatus | null): boolean {
  return (
    isRtspBridgePlayback(status) ||
    isLocalCameraBridgePlayback(status) ||
    isWindowsDshowBridgePlayback(status) ||
    isCameraNodePlayback(status)
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

function formatVisitDuration(durationSeconds: number): string {
  if (!Number.isFinite(durationSeconds) || durationSeconds <= 0) {
    return "Instant";
  }
  if (durationSeconds < 60) {
    return `${Math.round(durationSeconds)} sec`;
  }
  const minutes = Math.floor(durationSeconds / 60);
  const seconds = Math.round(durationSeconds % 60);
  return seconds ? `${minutes} min ${seconds} sec` : `${minutes} min`;
}

function reviewOutcomeLabel(visit: StreamVisitSummary): string {
  if (visit.review_status === "needs_review") {
    return "Needs review";
  }
  if (visit.review_outcome === "confirmed_bird" && visit.reviewed_label) {
    return `Confirmed: ${formatLabel(visit.reviewed_label)}`;
  }
  if (visit.reviewed_label) {
    return `Reviewed outcome: ${formatLabel(visit.reviewed_label)}`;
  }
  return formatLabel(visit.review_outcome);
}

function visitEvidenceFrames(detail: VisitDetail, summary: StreamVisitSummary): VisitEvidenceFrame[] {
  return detail.evidence_frames.length > 0
    ? detail.evidence_frames
    : summary.primary_evidence
      ? [summary.primary_evidence]
      : [];
}

function VisitEvidenceThumbnail({ evidence }: { evidence: VisitEvidenceFrame | null | undefined }) {
  const [unavailable, setUnavailable] = useState(false);
  if (!evidence || unavailable) {
    return <div className="stream-visit-thumbnail stream-visit-thumbnail-unavailable">Preview unavailable</div>;
  }
  return (
    <img
      alt="Primary Visit evidence"
      className="stream-visit-thumbnail"
      onError={() => setUnavailable(true)}
      src={`${apiClient.baseUrl}${evidence.preview_url}`}
    />
  );
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
  onOpenActivity,
  onOpenInsights,
  onOpenImport,
  onOpenExports,
  onOpenReview,
  onOpenMotionEvidence,
  onOpenCameraSetup,
  onReviewActivityCreated,
}: StreamDetailPageProps) {
  const [detail, setDetail] = useState<StreamDetailState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [candidatePacks, setCandidatePacks] = useState<SpeciesCandidatePack[]>([]);
  const [candidatePackSelection, setCandidatePackSelection] =
    useState<StreamSpeciesCandidatePackSelection | null>(null);
  const [candidatePackDraftId, setCandidatePackDraftId] = useState("");
  const [candidatePackError, setCandidatePackError] = useState<string | null>(null);
  const [isSavingCandidatePack, setIsSavingCandidatePack] = useState(false);
  const [recentVisitFilter, setRecentVisitFilter] = useState<RecentVisitFilter>("all");
  const [recentVisitZoneId, setRecentVisitZoneId] = useState("all");
  const [recentVisitsRefreshToken, setRecentVisitsRefreshToken] = useState(0);
  const [recentVisitsError, setRecentVisitsError] = useState<string | null>(null);
  const [isLoadingRecentVisits, setIsLoadingRecentVisits] = useState(false);
  const [selectedRecentVisitId, setSelectedRecentVisitId] = useState<string | null>(null);
  const [selectedRecentVisitDetail, setSelectedRecentVisitDetail] =
    useState<VisitDetail | null>(null);
  const [recentVisitDetailError, setRecentVisitDetailError] = useState<string | null>(null);
  const [isLoadingRecentVisitDetail, setIsLoadingRecentVisitDetail] = useState(false);
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);
  const [zoneDraft, setZoneDraft] = useState<ZoneDraft | null>(null);
  const [zoneMonitoringDraft, setZoneMonitoringDraft] = useState<ZoneMonitoringDraft | null>(
    null,
  );
  const [drawMode, setDrawMode] = useState(false);
  const [redrawZoneId, setRedrawZoneId] = useState<string | null>(null);
  const [drawStart, setDrawStart] = useState<Point | null>(null);
  const [draftPolygon, setDraftPolygon] = useState<Point[] | null>(null);
  const [newZoneName, setNewZoneName] = useState("New zone");
  const [newZoneType, setNewZoneType] = useState<ZoneType>("feeder");
  const [zoneMessage, setZoneMessage] = useState<string | null>(null);
  const [zoneError, setZoneError] = useState<string | null>(null);
  const [isSavingZone, setIsSavingZone] = useState(false);
  const [isSavingZoneMonitoring, setIsSavingZoneMonitoring] = useState(false);
  const [deleteZoneConfirmId, setDeleteZoneConfirmId] = useState<string | null>(null);
  const [liveViewOpen, setLiveViewOpen] = useState(false);
  const [liveViewState, setLiveViewState] = useState<LiveViewState>("idle");
  const [liveViewReloadToken, setLiveViewReloadToken] = useState(0);
  const [liveViewError, setLiveViewError] = useState<string | null>(null);
  const [liveMediaSize, setLiveMediaSize] = useState<MediaRenderSize | null>(null);
  const [showLiveZones, setShowLiveZones] = useState(true);
  const [liveSession, setLiveSession] = useState<LiveCameraSessionStatus | null>(null);
  const [liveSessionError, setLiveSessionError] = useState<string | null>(null);
  const [monitoringPolicy, setMonitoringPolicy] =
    useState<StreamMonitoringPolicy | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<StreamRuntimeStatus | null>(null);
  const [cameraHealth, setCameraHealth] = useState<CameraHealthDetailResponse | null>(null);
  const [cameraHealthError, setCameraHealthError] = useState<string | null>(null);
  const [isLoadingCameraHealth, setIsLoadingCameraHealth] = useState(true);
  const [isValidatingCameraHealth, setIsValidatingCameraHealth] = useState(false);
  const [monitoringContinuityError, setMonitoringContinuityError] =
    useState<string | null>(null);
  const [isLoadingMonitoringContinuity, setIsLoadingMonitoringContinuity] =
    useState(true);
  const [isUpdatingMonitoringContinuity, setIsUpdatingMonitoringContinuity] =
    useState(false);
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
  const [
    pendingAutoCreateReviewCandidates,
    setPendingAutoCreateReviewCandidates,
  ] = useState(() => readPendingAutoCreateReviewCandidates(streamId) ?? true);
  const [
    backendAutoCreateReviewCandidates,
    setBackendAutoCreateReviewCandidates,
  ] = useState<boolean | null>(null);
  const [isUpdatingAutoCreate, setIsUpdatingAutoCreate] = useState(false);
  const [pendingAutoIdentifyReviewCandidates, setPendingAutoIdentifyReviewCandidates] =
    useState(false);
  const [backendAutoIdentifyReviewCandidates, setBackendAutoIdentifyReviewCandidates] =
    useState<boolean | null>(null);
  const [isUpdatingAutoIdentify, setIsUpdatingAutoIdentify] = useState(false);
  const [autoReviewQuietSeconds, setAutoReviewQuietSeconds] = useState(30);
  const [autoReviewMinDetections, setAutoReviewMinDetections] = useState(1);
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
  const [isOpeningCameraControls, setIsOpeningCameraControls] = useState(false);
  const [liveMotionFocusZoneId, setLiveMotionFocusZoneId] = useState("");
  const [showLiveMotionDebug, setShowLiveMotionDebug] = useState(false);
  const [showForegroundMask, setShowForegroundMask] = useState(false);
  const [liveStatusNotice, setLiveStatusNotice] = useState<string | null>(null);
  const liveMotionInFlightRef = useRef(false);
  const lastAutoReviewQueueItemRef = useRef<string | null>(null);
  const lastAutoIdentificationSuggestionRef = useRef<string | null>(null);
  const lastActivityNoticeRef = useRef<string | null>(null);
  const lastReviewNoticeRef = useRef<string | null>(null);

  const selectedZone = detail?.zones.find((zone) => zone.id === selectedZoneId) ?? null;

  function clearTransientLiveActivity() {
    setLiveMotionResult(null);
    setLiveMotionError(null);
    setLiveStatusNotice(null);
    setLiveMonitorState("stopped");
    lastActivityNoticeRef.current = null;
    lastReviewNoticeRef.current = null;
  }

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
      setBackendAutoCreateReviewCandidates(status.auto_create_review_candidates);
      setBackendAutoIdentifyReviewCandidates(status.auto_identify_review_candidates);
      if (status.monitor_running) {
        setPendingAutoIdentifyReviewCandidates(status.auto_identify_review_candidates);
      }
      if (
        status.monitor_running ||
        (readPendingAutoCreateReviewCandidates(status.stream_id) == null &&
          status.status !== "stopped")
      ) {
        setPendingAutoCreateReviewCandidates(status.auto_create_review_candidates);
        writePendingAutoCreateReviewCandidates(
          status.stream_id,
          status.auto_create_review_candidates,
        );
      }
      setAutoReviewQuietSeconds(status.auto_review_quiet_seconds);
      setAutoReviewMinDetections(status.auto_review_min_detections);
      if (status.status === "stopped" && !status.monitor_running) {
        clearTransientLiveActivity();
      } else {
        handleLiveStatusNoticeFromStatus(status);
      }
      if (status.status !== "stopped" && status.last_motion_result) {
        setLiveMotionResult(status.last_motion_result);
        setLiveMonitorState(liveMonitorStateFor(status.last_motion_result));
      } else if (status.monitor_running) {
        setLiveMonitorState((current) => (current === "idle" ? "waiting" : current));
      }
      if (
        status.last_auto_review_queue_item_id &&
        status.last_auto_review_queue_item_id !== lastAutoReviewQueueItemRef.current
      ) {
        lastAutoReviewQueueItemRef.current = status.last_auto_review_queue_item_id;
        await onReviewActivityCreated();
      }
      if (
        status.last_auto_identification_suggestion_id &&
        status.last_auto_identification_suggestion_id !==
          lastAutoIdentificationSuggestionRef.current
      ) {
        lastAutoIdentificationSuggestionRef.current =
          status.last_auto_identification_suggestion_id;
        await onReviewActivityCreated();
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

  function handleLiveStatusNoticeFromStatus(status: LiveCameraSessionStatus) {
    const activity = (status.current_activity_session ?? status.last_activity ?? null) as
      | Record<string, unknown>
      | null;
    const activityId =
      status.current_activity_session_id ??
      (typeof activity?.activity_session_id === "string" ? activity.activity_session_id : null);
    const reviewQueueItemId =
      status.activity_review_queue_item_id ??
      status.last_auto_review_queue_item_id ??
      (typeof activity?.review_queue_item_id === "string" ? activity.review_queue_item_id : null);

    if (status.notification_event === "activity_started" && activityId) {
      if (lastActivityNoticeRef.current !== activityId) {
        lastActivityNoticeRef.current = activityId;
        setLiveStatusNotice("Feeder activity started.");
      }
      return;
    }
    if (
      (status.notification_event === "review_candidate_ready" || reviewQueueItemId) &&
      reviewQueueItemId
    ) {
      if (lastReviewNoticeRef.current !== reviewQueueItemId) {
        lastReviewNoticeRef.current = reviewQueueItemId;
        setLiveStatusNotice("Review candidate ready.");
      }
    }
  }

  function handleLiveStatusNoticeFromResult(result: LiveMotionEvaluateResponse) {
    if (result.notification_event === "activity_started" && result.activity_session_id) {
      if (lastActivityNoticeRef.current !== result.activity_session_id) {
        lastActivityNoticeRef.current = result.activity_session_id;
        setLiveStatusNotice("Feeder activity started.");
      }
      return;
    }
    if (
      (result.notification_event === "review_candidate_ready" || result.review_queue_item_id) &&
      result.review_queue_item_id
    ) {
      if (lastReviewNoticeRef.current !== result.review_queue_item_id) {
        lastReviewNoticeRef.current = result.review_queue_item_id;
        setLiveStatusNotice("Review candidate ready.");
      }
    }
  }

  async function handleAutoCreateReviewCandidatesChange(enabled: boolean) {
    setPendingAutoCreateReviewCandidates(enabled);
    writePendingAutoCreateReviewCandidates(streamId, enabled);
    const monitorRunning = Boolean(liveSession?.monitor_running || isLiveMonitoring);
    if (!detail || !supportsBackendLiveSession(detail.playback) || !monitorRunning) {
      setLiveStatusNotice("Auto-create will apply when monitoring starts.");
      return;
    }

    setIsUpdatingAutoCreate(true);
    setLiveMotionError(null);
    try {
      const status = await apiClient.updateLiveMotionMonitorSettings(detail.stream.id, {
        auto_create_review_candidates: enabled,
        auto_identify_review_candidates: pendingAutoIdentifyReviewCandidates,
        auto_review_quiet_seconds: autoReviewQuietSeconds,
        auto_review_min_detections: autoReviewMinDetections,
      });
      setLiveSession(status);
      setIsLiveMonitoring(status.monitor_running);
      setBackendAutoCreateReviewCandidates(status.auto_create_review_candidates);
      if (status.monitor_running) {
        setPendingAutoCreateReviewCandidates(status.auto_create_review_candidates);
        writePendingAutoCreateReviewCandidates(
          status.stream_id,
          status.auto_create_review_candidates,
        );
      }
      setLiveStatusNotice(
        `Auto-create ${status.auto_create_review_candidates ? "enabled" : "disabled"}.`,
      );
    } catch (caught) {
      setLiveMotionError(
        caught instanceof Error
          ? caught.message
          : "Could not update auto-create monitoring settings.",
      );
    } finally {
      setIsUpdatingAutoCreate(false);
    }
  }

  async function handleAutoIdentifyReviewCandidatesChange(enabled: boolean) {
    setPendingAutoIdentifyReviewCandidates(enabled);
    const monitorRunning = Boolean(liveSession?.monitor_running || isLiveMonitoring);
    if (!detail || !supportsBackendLiveSession(detail.playback) || !monitorRunning) {
      return;
    }
    setIsUpdatingAutoIdentify(true);
    setLiveMotionError(null);
    try {
      const status = await apiClient.updateLiveMotionMonitorSettings(detail.stream.id, {
        auto_create_review_candidates: pendingAutoCreateReviewCandidates,
        auto_identify_review_candidates: enabled,
        auto_review_quiet_seconds: autoReviewQuietSeconds,
        auto_review_min_detections: autoReviewMinDetections,
      });
      setLiveSession(status);
      setBackendAutoIdentifyReviewCandidates(status.auto_identify_review_candidates);
      if (status.monitor_running) {
        setPendingAutoIdentifyReviewCandidates(status.auto_identify_review_candidates);
      }
    } catch (caught) {
      setLiveMotionError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setIsUpdatingAutoIdentify(false);
    }
  }


  useEffect(() => {
    let isMounted = true;

    async function loadStreamDetail() {
      setIsLoading(true);
      setError(null);
      setCandidatePacks([]);
      setCandidatePackSelection(null);
      setCandidatePackDraftId("");
      setCandidatePackError(null);
      setIsSavingCandidatePack(false);
      setZoneError(null);
      setZoneMessage(null);
      setDeleteZoneConfirmId(null);
      setDrawMode(false);
      setDraftPolygon(null);
      setDrawStart(null);
      setRecentVisitFilter("all");
      setRecentVisitZoneId("all");
      setRecentVisitsError(null);
      setIsLoadingRecentVisits(false);
      setSelectedRecentVisitId(null);
      setSelectedRecentVisitDetail(null);
      setRecentVisitDetailError(null);
      setIsLoadingRecentVisitDetail(false);
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
      setPendingAutoCreateReviewCandidates(
        readPendingAutoCreateReviewCandidates(streamId) ?? false,
      );
      setPendingAutoIdentifyReviewCandidates(false);
      setBackendAutoIdentifyReviewCandidates(null);
      lastAutoIdentificationSuggestionRef.current = null;
      setBackendAutoCreateReviewCandidates(null);
      setIsUpdatingAutoCreate(false);
      setSourceProviderConfig(null);
      setCameraTuningDraft({ ...emptyCameraTuningDraft });
      setCameraTuningMessage(null);
      setCameraTuningError(null);
      setIsSavingCameraTuning(false);
      setLiveMotionFocusZoneId("");
      setShowLiveMotionDebug(false);
      setLiveStatusNotice(null);
      lastActivityNoticeRef.current = null;
      lastReviewNoticeRef.current = null;
      try {
        const stream = await apiClient.getStream(streamId);
        const [
          playback,
          setupReview,
          providerConfiguration,
          zones,
          events,
          recentVisits,
          nextCandidatePacks,
          nextCandidatePackSelection,
        ] = await Promise.all([
          apiClient.getStreamPlaybackStatus(streamId),
          apiClient.getSourceSetupReview(stream.source_id),
          apiClient.getSourceProviderConfiguration(stream.source_id),
          apiClient.getStreamZones(streamId),
          apiClient.getStreamEvents(streamId),
          apiClient.getStreamRecentVisits(streamId, { limit: 12 }),
          apiClient.listSpeciesCandidatePacks(false),
          apiClient.getStreamSpeciesCandidatePackSelection(streamId),
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
            recentVisits,
          });
          setSourceProviderConfig(providerConfiguration);
          setCameraTuningDraft(cameraTuningDraftFromConfig(providerConfiguration));
          setCandidatePacks(nextCandidatePacks);
          setCandidatePackSelection(nextCandidatePackSelection);
          setCandidatePackDraftId(nextCandidatePackSelection.effective_pack.id);
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

  async function saveSpeciesCandidatePack() {
    if (!candidatePackDraftId || isSavingCandidatePack) {
      return;
    }
    setIsSavingCandidatePack(true);
    setCandidatePackError(null);
    try {
      const selection = await apiClient.setStreamSpeciesCandidatePackSelection(streamId, {
        candidate_pack_id: candidatePackDraftId,
      });
      setCandidatePackSelection(selection);
      setCandidatePackDraftId(selection.effective_pack.id);
    } catch (caught) {
      setCandidatePackError(
        caught instanceof Error ? caught.message : "Could not update the Stream candidate pack.",
      );
    } finally {
      setIsSavingCandidatePack(false);
    }
  }

  async function setDurableMonitoringEnabled(enabled: boolean) {
    setIsUpdatingMonitoringContinuity(true);
    setMonitoringContinuityError(null);
    try {
      const result = await apiClient.updateStreamMonitoringPolicy(streamId, {
        enabled,
        idempotency_key:
          globalThis.crypto?.randomUUID?.() ??
          `monitoring-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      });
      setMonitoringPolicy(result.policy);
      setRuntimeStatus(result.runtime);
      const health = await apiClient.getStreamCameraHealth(streamId).catch(() => null);
      if (health) setCameraHealth(health);
    } catch (caught) {
      setMonitoringContinuityError(
        caught instanceof Error ? caught.message : "Could not update monitoring.",
      );
    } finally {
      setIsUpdatingMonitoringContinuity(false);
    }
  }

  async function retryDurableMonitoring() {
    setIsUpdatingMonitoringContinuity(true);
    setMonitoringContinuityError(null);
    try {
      const result = await apiClient.retryStreamMonitoring(streamId, {
        idempotency_key:
          globalThis.crypto?.randomUUID?.() ??
          `monitoring-retry-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      });
      setMonitoringPolicy(result.policy);
      setRuntimeStatus(result.runtime);
      const health = await apiClient.getStreamCameraHealth(streamId).catch(() => null);
      if (health) setCameraHealth(health);
    } catch (caught) {
      setMonitoringContinuityError(
        caught instanceof Error ? caught.message : "Could not retry monitoring.",
      );
    } finally {
      setIsUpdatingMonitoringContinuity(false);
    }
  }

  async function validateCameraHealthSetup() {
    if (!detail) return;
    setIsValidatingCameraHealth(true);
    setCameraHealthError(null);
    try {
      const [setupReview, playback, health] = await Promise.all([
        apiClient.getSourceSetupReview(detail.stream.source_id),
        apiClient.getStreamPlaybackStatus(detail.stream.id),
        apiClient.getStreamCameraHealth(detail.stream.id),
      ]);
      setDetail((current) => current ? { ...current, setupReview, playback } : current);
      setCameraHealth(health);
    } catch {
      setCameraHealthError(
        "Could not validate saved camera setup. MockingBird did not start a camera or change monitoring.",
      );
    } finally {
      setIsValidatingCameraHealth(false);
    }
  }

  useEffect(() => {
    if (detail?.stream.id !== streamId) {
      return;
    }
    let isCurrent = true;
    const reviewStatus =
      recentVisitFilter === "needs_review"
        ? "needs_review"
        : recentVisitFilter === "reviewed" || recentVisitFilter === "review_outcomes"
          ? "reviewed"
          : undefined;

    async function loadRecentVisits() {
      setIsLoadingRecentVisits(true);
      setRecentVisitsError(null);
      try {
        const visits = await apiClient.getStreamRecentVisits(streamId, {
          limit: 12,
          review_status: reviewStatus,
          zone_id: recentVisitZoneId === "all" ? undefined : recentVisitZoneId,
        });
        const visibleVisits =
          recentVisitFilter === "review_outcomes"
            ? visits.filter((visit) => visit.review_outcome !== "confirmed_bird")
            : visits;
        if (isCurrent) {
          setDetail((current) =>
            current && current.stream.id === streamId
              ? { ...current, recentVisits: visibleVisits }
              : current,
          );
        }
      } catch (caught) {
        if (isCurrent) {
          setRecentVisitsError(
            caught instanceof Error ? caught.message : "Could not load recent Visits.",
          );
        }
      } finally {
        if (isCurrent) {
          setIsLoadingRecentVisits(false);
        }
      }
    }

    void loadRecentVisits();
    return () => {
      isCurrent = false;
    };
  }, [
    detail?.stream.id,
    recentVisitFilter,
    recentVisitZoneId,
    recentVisitsRefreshToken,
    streamId,
  ]);

  useEffect(() => {
    let isMounted = true;
    setMonitoringPolicy(null);
    setRuntimeStatus(null);
    setMonitoringContinuityError(null);
    setIsLoadingMonitoringContinuity(true);

    async function loadMonitoringContinuity() {
      try {
        const [policy, status] = await Promise.all([
          apiClient.getStreamMonitoringPolicy(streamId),
          apiClient.getStreamRuntimeStatus(streamId),
        ]);
        if (isMounted) {
          setMonitoringPolicy(policy);
          setRuntimeStatus(status);
        }
      } catch (caught) {
        if (isMounted) {
          setMonitoringContinuityError(
            caught instanceof Error
              ? caught.message
              : "Could not load monitoring continuity status.",
          );
        }
      } finally {
        if (isMounted) {
          setIsLoadingMonitoringContinuity(false);
        }
      }
    }

    void loadMonitoringContinuity();
    return () => {
      isMounted = false;
    };
  }, [streamId]);

  useEffect(() => {
    let isMounted = true;
    setCameraHealth(null);
    setCameraHealthError(null);
    setIsLoadingCameraHealth(true);

    async function loadCameraHealth() {
      try {
        const health = await apiClient.getStreamCameraHealth(streamId);
        if (isMounted) setCameraHealth(health);
      } catch {
        if (isMounted) {
          setCameraHealthError("Could not refresh saved camera health. Existing camera controls are unchanged.");
        }
      } finally {
        if (isMounted) setIsLoadingCameraHealth(false);
      }
    }

    void loadCameraHealth();
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
    if (!detail || !isCameraNodePlayback(detail.playback)) {
      return;
    }
    // A paired Node can show an already-running session’s cached still without
    // taking ownership of the camera or enabling monitoring.
    setLiveViewOpen(true);
    setLiveViewState("opening");
    setLiveViewError(null);
  }, [detail?.stream.id, detail?.playback.playback_kind, detail?.playback.status]);

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
      setZoneMonitoringDraft(null);
      return;
    }

    setZoneDraft({
      name: selectedZone.name,
      zone_type: selectedZone.zone_type,
      is_active: selectedZone.is_active,
    });
    setZoneMonitoringDraft(
      selectedZone.monitoring_policy
        ? zoneMonitoringDraftFromPolicy(selectedZone.monitoring_policy)
        : null,
    );
  }, [selectedZone]);

  useEffect(() => {
    if (deleteZoneConfirmId !== null) {
      setZoneMessage(null);
    }
    setDeleteZoneConfirmId(null);
  }, [selectedZoneId]);

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

  function replaceZoneMonitoringPolicy(zoneId: string, policy: ZoneMonitoringPolicy) {
    setDetail((current) =>
      current
        ? {
            ...current,
            zones: current.zones.map((zone) =>
              zone.id === zoneId ? { ...zone, monitoring_policy: policy } : zone,
            ),
          }
        : current,
    );
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

  async function handleOpenCameraControls() {
    if (!detail) {
      return;
    }
    setIsOpeningCameraControls(true);
    setCameraTuningError(null);
    setCameraTuningMessage(null);
    try {
      const result = await apiClient.openWindowsCameraControls(detail.stream.id);
      if (result.status === "launched") {
        setCameraTuningMessage([result.message, ...result.warnings].join(" "));
      } else {
        setCameraTuningError(result.message);
      }
    } catch (caught) {
      setCameraTuningError(
        caught instanceof Error ? caught.message : "Could not open camera controls.",
      );
    } finally {
      setIsOpeningCameraControls(false);
    }
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
      if (status.status === "stopped") {
        clearTransientLiveActivity();
      }
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
        detector_preset: sensitivitySettings.detector_preset,
        max_frames: sensitivitySettings.max_frames,
        min_triggered_frames: 1,
        focus_zone_id: liveMotionFocusZoneId || null,
        interval_seconds: sensitivitySettings.interval_ms / 1000,
        auto_create_review_candidates: pendingAutoCreateReviewCandidates,
        auto_identify_review_candidates: pendingAutoIdentifyReviewCandidates,
        auto_review_quiet_seconds: autoReviewQuietSeconds,
        auto_review_min_detections: autoReviewMinDetections,
        notes: null,
      });
      setBackendAutoCreateReviewCandidates(result.auto_create_review_candidates);
      if (result.auto_create_review_candidates === pendingAutoCreateReviewCandidates) {
        writePendingAutoCreateReviewCandidates(
          detail.stream.id,
          result.auto_create_review_candidates,
        );
      }
      if (result.best_media_asset_id) {
        await refreshSavedImages();
      }
      if (supportsBackendLiveSession(detail.playback)) {
        const status = await refreshLiveCameraSessionStatus(detail);
        setIsLiveMonitoring(status?.monitor_running ?? true);
      }
      setLiveMotionResult(result);
      handleLiveStatusNoticeFromResult(result);
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
        if (lastReviewNoticeRef.current !== result.review_queue_item_id) {
          lastReviewNoticeRef.current = result.review_queue_item_id;
          setLiveStatusNotice("Review candidate ready.");
        }
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
        setBackendAutoCreateReviewCandidates(status.auto_create_review_candidates);
        setBackendAutoIdentifyReviewCandidates(status.auto_identify_review_candidates);
        setPendingAutoIdentifyReviewCandidates(status.auto_identify_review_candidates);
        setPendingAutoCreateReviewCandidates(status.auto_create_review_candidates);
        writePendingAutoCreateReviewCandidates(
          status.stream_id,
          status.auto_create_review_candidates,
        );
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

  async function handleSaveZoneMonitoring(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedZone || !selectedZone.monitoring_policy || !zoneMonitoringDraft) {
      return;
    }

    const current = selectedZone.monitoring_policy;
    const changes: ZoneMonitoringPolicyUpdate = {};
    const fields: Array<keyof ZoneMonitoringDraft> = [
      "monitoring_enabled",
      "activity_sensitivity",
      "minimum_sustained_activity_seconds",
      "quiet_period_seconds",
      "maximum_visit_duration_seconds",
      "maximum_evidence_frames",
    ];
    for (const field of fields) {
      if (zoneMonitoringDraft[field] !== current[field]) {
        Object.assign(changes, { [field]: zoneMonitoringDraft[field] });
      }
    }
    if (Object.keys(changes).length === 0) {
      setZoneMessage("Monitoring settings are unchanged.");
      return;
    }

    setIsSavingZoneMonitoring(true);
    setZoneError(null);
    setZoneMessage(null);
    try {
      const policy = await apiClient.updateZoneMonitoringPolicy(selectedZone.id, changes);
      replaceZoneMonitoringPolicy(selectedZone.id, policy);
      setZoneMonitoringDraft(zoneMonitoringDraftFromPolicy(policy));
      setZoneMessage("Monitoring settings saved. They apply to future activity sessions.");
    } catch (caught) {
      setZoneError(
        caught instanceof Error ? caught.message : "Could not save Zone monitoring settings.",
      );
    } finally {
      setIsSavingZoneMonitoring(false);
    }
  }

  async function handleRestoreZoneMonitoringDefaults() {
    if (!selectedZone || !selectedZone.monitoring_policy) {
      return;
    }
    setIsSavingZoneMonitoring(true);
    setZoneError(null);
    setZoneMessage(null);
    try {
      const policy = await apiClient.restoreZoneMonitoringPolicyDefaults(selectedZone.id);
      replaceZoneMonitoringPolicy(selectedZone.id, policy);
      setZoneMonitoringDraft(zoneMonitoringDraftFromPolicy(policy));
      setZoneMessage("Recommended monitoring settings restored for future activity sessions.");
    } catch (caught) {
      setZoneError(
        caught instanceof Error ? caught.message : "Could not restore recommended settings.",
      );
    } finally {
      setIsSavingZoneMonitoring(false);
    }
  }

  async function handleDeleteSelectedZone() {
    if (!selectedZone) {
      return;
    }
    if (isLiveMonitoring || liveSession?.monitor_running) {
      setZoneError("Stop monitoring before removing a Zone.");
      return;
    }
    if (deleteZoneConfirmId !== selectedZone.id) {
      setDeleteZoneConfirmId(selectedZone.id);
      setZoneError(null);
      setZoneMessage(`Confirm removal of ${selectedZone.name}.`);
      return;
    }

    const deletedZone = selectedZone;
    setIsSavingZone(true);
    setZoneError(null);
    setZoneMessage(null);
    try {
      const result = await apiClient.deleteZone(deletedZone.id);
      replaceZones(result.zones);
      setSelectedZoneId(result.zones[0]?.id ?? null);
      setDeleteZoneConfirmId(null);
      setRedrawZoneId(null);
      if (liveMotionFocusZoneId === deletedZone.id) {
        setLiveMotionFocusZoneId("");
      }
      setZoneMessage(`${deletedZone.name} removed.`);
    } catch (caught) {
      setZoneError(caught instanceof Error ? caught.message : "Could not remove Zone.");
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
    setRedrawZoneId(null);
    setDraftPolygon(null);
    setDrawStart(null);
    setZoneError(null);
    setZoneMessage(null);
  }

  function startRedrawMode() {
    if (!selectedZone) {
      return;
    }
    if (detail && hasRealLivePlayback(detail.playback)) {
      if (!liveViewOpen) {
        setZoneError("Open Live view to redraw this zone on the camera stream.");
        return;
      }
      if (liveViewState !== "streaming") {
        setZoneError("Wait for the live stream to start before redrawing this zone.");
        return;
      }
    }
    setDrawMode(true);
    setRedrawZoneId(selectedZone.id);
    setDraftPolygon(null);
    setDrawStart(null);
    setZoneError(null);
    setZoneMessage(null);
  }

  function cancelDrawMode() {
    setDrawMode(false);
    setRedrawZoneId(null);
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
    if (!redrawZoneId && !trimmedName) {
      setZoneError("Zone name is required.");
      return;
    }

    setIsSavingZone(true);
    setZoneError(null);
    setZoneMessage(null);
    try {
      if (redrawZoneId) {
        const result = await apiClient.updateZone(redrawZoneId, {
          polygon: draftPolygon,
        });
        replaceZones(result.zones);
        setSelectedZoneId(result.zone.id);
        setDrawMode(false);
        setRedrawZoneId(null);
        setDraftPolygon(null);
        setDrawStart(null);
        setZoneMessage("Zone shape updated.");
        return;
      }

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
      setRedrawZoneId(null);
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

  async function handleInspectRecentVisit(summary: StreamVisitSummary) {
    setSelectedRecentVisitId(summary.id);
    setSelectedRecentVisitDetail(null);
    setRecentVisitDetailError(null);
    setIsLoadingRecentVisitDetail(true);
    try {
      const visitDetail = await apiClient.getVisitDetail(summary.id);
      if (visitDetail.stream.id !== streamId) {
        throw new Error("This Visit is not part of the open Stream.");
      }
      setSelectedRecentVisitDetail(visitDetail);
    } catch (caught) {
      setRecentVisitDetailError(
        caught instanceof Error ? caught.message : "Could not load Visit evidence.",
      );
    } finally {
      setIsLoadingRecentVisitDetail(false);
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
  const cameraCalibrationVisible =
    sourceProviderConfig?.provider_key === "local_usb" &&
    (backendLiveSessionSupported || detail.playback.live_stream_type === "windows_dshow");
  const liveSessionRunning = liveSession?.status === "running";
  const liveSessionStarting = liveSession?.status === "starting";
  const liveSessionFailed = liveSession?.status === "failed";
  const liveMonitorRunning = Boolean(liveSession?.monitor_running || isLiveMonitoring);
  const nativeCameraControlsBlocked =
    liveMonitorRunning ||
    ["starting", "running", "stopping"].includes(liveSession?.status ?? "");
  const cameraNodePlayback = isCameraNodePlayback(detail.playback);
  const liveUrl = cameraNodePlayback
    ? apiClient.liveCameraCurrentFrameUrl(detail.stream.id)
    : liveStreamUrl(detail.playback, detail.stream.id);
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
    liveMonitorRunning && liveMonitorState === "idle"
      ? "Watching"
      : liveMonitorState === "waiting"
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
      : liveMonitorState === "watching" || liveMonitorRunning
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
  const liveSessionActivity = (liveSession?.current_activity_session ??
    liveSession?.last_activity ??
    null) as Record<string, unknown> | null;
  const liveSessionActivityString = (key: string): string | null => {
    const value = liveSessionActivity?.[key];
    return typeof value === "string" && value ? value : null;
  };
  const liveSessionActivityNumber = (key: string): number | null => {
    const value = liveSessionActivity?.[key];
    return typeof value === "number" ? value : null;
  };
  const liveReviewQueueItemId =
    liveMotionResult?.review_queue_item_id ??
    liveSession?.activity_review_queue_item_id ??
    liveSession?.last_auto_review_queue_item_id ??
    liveSessionActivityString("review_queue_item_id");
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
    liveMonitorRunning
      ? "Captured current frame; camera and monitoring are still running."
      : captureResult?.capture_source === "live_camera_session"
      ? "Saved current session frame. It will not appear in Bird Log until you create/review activity."
      : "Saved one local camera frame. It will not appear in Bird Log until you create/review activity.";
  const showManualSavedFrameComparison = Boolean(
    !liveMonitorRunning &&
      (captureSaved || motionResult || motionError || savedImageError || isLoadingSavedImages),
  );
  const captureButtonLabel =
    isCapturingFrame
      ? "Capturing..."
      : liveViewOpen || liveSessionRunning
        ? "Capture current frame"
        : "Capture frame";
  const liveActivityDetected = Boolean(
    liveMotionResult?.activity_detected ||
      liveSession?.current_activity_session_id ||
      liveSessionActivity?.activity_session_id,
  );
  const liveReviewActivityCreated = Boolean(
    liveMotionResult?.review_activity_created ||
      liveSession?.activity_review_activity_created ||
      liveReviewQueueItemId ||
      liveMotionResult?.created_evidence.length,
  );
  const liveActivityZone = liveMotionResult?.strongest_zone_id
    ? detail.zones.find((zone) => zone.id === liveMotionResult.strongest_zone_id)
    : null;
  const liveStrongestZoneName =
    liveMotionResult?.strongest_zone_name ??
    liveActivityZone?.name ??
    liveSessionActivityString("zone_name");
  const liveStrongestZoneType =
    liveMotionResult?.strongest_zone_type ??
    liveActivityZone?.zone_type ??
    (liveSessionActivityString("zone_type") as ZoneType | null);
  const liveSuppressedZones = liveMotionResult?.suppressed_zone_summaries ?? [];
  const liveSuppressedMessage =
    liveMotionResult?.activity_detected === false
      ? liveMotionResult.activity_summary ?? suppressedZoneMessage(liveSuppressedZones)
      : suppressedZoneMessage(liveSuppressedZones);
  const liveActivityAreaLabel =
    liveStrongestZoneName ??
    liveMotionResult?.strongest_activity_area_label ??
    (liveMotionResult?.uses_auto_regions ? "automatic activity" : "general activity");
  const liveActivityDetectionCount =
    liveMotionResult?.activity_detection_count ??
    liveSession?.activity_detection_count ??
    liveSessionActivityNumber("detection_count") ??
    0;
  const liveActivityNearMissCount =
    liveMotionResult?.activity_near_miss_count ??
    liveSession?.activity_near_miss_count ??
    liveSessionActivityNumber("near_miss_count") ??
    0;
  const liveActivityFramesEvaluatedCount =
    liveMotionResult?.activity_frames_evaluated_count ??
    liveSession?.activity_frames_evaluated_count ??
    liveSessionActivityNumber("frames_evaluated_count") ??
    0;
  const liveActivityCandidateFrameCount =
    liveMotionResult?.activity_candidate_frame_count ??
    liveSession?.activity_candidate_frame_count ??
    liveSessionActivityNumber("candidate_frame_count") ??
    0;
  const liveActivitySavedCandidateCount =
    liveMotionResult?.activity_saved_candidate_count ??
    liveSession?.activity_saved_candidate_count ??
    liveSessionActivityNumber("saved_candidate_count") ??
    0;
  const liveActivityManualReviewNeeded = Boolean(
    liveMotionResult?.activity_manual_review_needed ??
      liveSession?.activity_manual_review_needed ??
      liveSessionActivity?.manual_review_needed,
  );
  const liveActivityTitle =
    liveReviewActivityCreated
      ? `Review activity created for ${liveActivityAreaLabel}`
      : liveActivityDetectionCount === 0 && liveActivityNearMissCount > 0
        ? `Possible activity near ${liveActivityAreaLabel}`
      : `Activity detected in ${liveActivityAreaLabel}`;
  const liveBestMediaAssetId =
    liveMotionResult?.best_media_asset_id ?? liveSessionActivityString("best_media_asset_id");
  const liveBestFrameMessage =
    liveBestMediaAssetId && liveStrongestZoneName
      ? `Best frame saved from ${liveStrongestZoneName}.`
      : liveBestMediaAssetId
        ? "Best frame saved from the strongest live activity area."
        : (liveMotionResult?.activity_session_id ?? liveSession?.current_activity_session_id)
          ? "Best frame selected for this visit session."
          : "Best frame is unavailable.";
  const liveBestFrameUrl = liveBestMediaAssetId
    ? apiClient.mediaFileUrl(liveBestMediaAssetId)
    : null;
  const liveActivityBestChangeLabel = formatPercent(
    liveMotionResult?.activity_best_changed_ratio ??
      liveSession?.activity_best_changed_ratio ??
      liveSessionActivityNumber("best_changed_ratio") ??
      liveMotionResult?.strongest_changed_ratio,
  );
  const liveActivityBestFrameSequence =
    liveMotionResult?.activity_best_frame_sequence ??
    liveSession?.activity_best_frame_sequence ??
    liveSessionActivityNumber("best_frame_sequence") ??
    liveMotionResult?.best_frame_sequence;
  const liveBestFrameCapturedAt =
    liveMotionResult?.best_frame_captured_at ??
    liveSessionActivityString("best_frame_captured_at");
  const liveBestFrameTime = liveBestFrameCapturedAt
    ? formatDateTime(liveBestFrameCapturedAt)
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
      : liveMotionResult?.activity_quiet_remaining_seconds != null
        ? `${liveMotionResult.activity_quiet_remaining_seconds}s remaining`
      : liveSession?.activity_cooldown_remaining_seconds != null
        ? `${liveSession.activity_cooldown_remaining_seconds}s remaining`
        : liveSession?.activity_quiet_remaining_seconds != null
          ? `${liveSession.activity_quiet_remaining_seconds}s remaining`
      : null;
  const liveActivityReviewState =
    liveMotionResult?.activity_review_state ??
    liveSession?.activity_review_state ??
    liveSessionActivityString("review_state");
  const liveActivityReviewStateLabel = liveActivityReviewState
    ? formatLabel(liveActivityReviewState)
    : liveActivityDetected
      ? "Active session"
      : "Watching";
  const liveAutoReviewBackendValue =
    backendAutoCreateReviewCandidates ??
    liveSession?.auto_create_review_candidates ??
    liveMotionResult?.auto_create_review_candidates;
  const liveAutoReviewEnabled = liveMonitorRunning
    ? liveAutoReviewBackendValue ?? pendingAutoCreateReviewCandidates
    : pendingAutoCreateReviewCandidates;
  const liveAutoIdentifyBackendValue =
    backendAutoIdentifyReviewCandidates ??
    liveSession?.auto_identify_review_candidates ??
    liveMotionResult?.auto_identify_review_candidates;
  const liveAutoIdentifyEnabled = liveMonitorRunning
    ? liveAutoIdentifyBackendValue ?? pendingAutoIdentifyReviewCandidates
    : pendingAutoIdentifyReviewCandidates;
  const liveAutoReviewStatusText = isUpdatingAutoCreate
    ? "Updating auto-create..."
    : liveMonitorRunning
      ? `Auto-create ${liveAutoReviewEnabled ? "enabled" : "disabled"}.`
      : "Will apply when monitoring starts.";
  const liveAutoReviewCount =
    liveSession?.auto_review_created_count ?? liveMotionResult?.auto_review_created_count ?? 0;
  const liveAutoReviewLastCreated = liveSession?.last_auto_review_created_at
    ? formatDateTime(liveSession.last_auto_review_created_at)
    : liveMotionResult?.last_auto_review_created_at
      ? formatDateTime(liveMotionResult.last_auto_review_created_at)
      : null;
  const liveAutoReviewError =
    liveSession?.auto_review_last_error ?? liveMotionResult?.auto_review_last_error ?? null;
  const liveOpenActivitySessionCount = liveSession?.open_activity_session_count ?? 0;
  const liveOpenActivityZones = liveSession?.open_activity_zone_names ?? [];
  const liveReadyActivitySessionCount = liveSession?.ready_activity_session_count ?? 0;
  const liveLatestReviewQueueItemId =
    liveSession?.latest_activity_review_queue_item_id ??
    liveSession?.last_auto_review_queue_item_id ??
    liveMotionResult?.review_queue_item_id ??
    null;
  const liveSensitivityLabel = liveMonitorSensitivitySettings[liveMonitorSensitivity].label;
  const liveCadenceLabel =
    liveMotionResult?.evaluation_cadence_seconds != null
      ? `${liveMotionResult.evaluation_cadence_seconds.toFixed(2)}s`
      : `${liveMonitorSensitivitySettings[liveMonitorSensitivity].interval_ms / 1000}s`;
  const liveQualityWarnings = liveMotionResult?.image_quality_warnings ?? [];
  const liveMotionGuidanceWarnings =
    liveMotionResult?.warnings.filter((warning) => !liveQualityWarnings.includes(warning)) ?? [];
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
  ).filter(
    ([key, value]) =>
      cameraTuningKeys.includes(key as CameraTuningKey) &&
      value != null &&
      String(value).trim(),
  );
  const liveLastError =
    liveMotionResult?.last_error ?? liveMotionError ?? liveSessionError ?? null;
  const showLiveMonitorFacts = Boolean(
    showLiveMotionDebug && (liveMonitorRunning || liveMotionResult || liveSession),
  );
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
            : liveMonitorRunning
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
        ? "Activity open — review candidate ready."
        : liveWorkflowState === "cooldown"
          ? "Activity open — waiting for quiet."
        : liveWorkflowState === "activity"
          ? "Motion detected."
          : liveWorkflowState === "ignored"
            ? "Quiet — ignored-zone motion."
          : liveWorkflowState === "monitoring"
            ? "Quiet — monitoring."
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
  const continuityNeedsAttention =
    runtimeStatus?.actual_state === "interrupted" ||
    runtimeStatus?.actual_state === "blocked" ||
    Boolean(monitoringContinuityError);
  const continuityLabel = monitoringContinuityError
    ? "Unavailable"
    : isLoadingMonitoringContinuity
      ? "Loading"
      : monitoringPolicy
        ? monitoringPolicy.mode === "armed"
          ? "Monitoring enabled"
          : "Monitoring disabled"
        : "Unavailable";

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
            {detail.stream.description} Start the camera, monitor activity, review candidates, and
            turn corrections into local dataset records.
          </p>
        </div>
        <div className="detail-actions">
          {streamReviewCount > 0 ? (
            <button className="secondary-action" onClick={() => onOpenReview()}>
              Review Queue {streamReviewCount}
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

      <details className="panel stream-secondary-details" aria-label="Species candidate pack">
        <summary className="source-setup-summary">
          <strong>Species candidate pack</strong>
          <span>Optional reviewer-assistance scope; it does not run automatically.</span>
        </summary>
        <div className="stream-secondary-details-body">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Evidence-only identification</span>
            <h2>Species candidate pack</h2>
            <span className="meta-text">
              Future explicit species suggestions for this Stream use this ordered bird scope.
            </span>
          </div>
          {candidatePackSelection ? (
            <StatusPill
              label={`${candidatePackSelection.effective_pack.candidate_count} species`}
              tone="quiet"
            />
          ) : null}
        </div>
        {candidatePackSelection ? (
          <div className="review-identification-grid">
            <div className="data-row">
              <span>Effective pack</span>
              <strong>
                {candidatePackSelection.effective_pack.display_name} v{candidatePackSelection.effective_pack.version}
              </strong>
              <small>
                Compared against {candidatePackSelection.effective_pack.candidate_count} species. Historical suggestion evidence is unchanged.
              </small>
            </div>
            <label>
              Use active pack
              <select
                value={candidatePackDraftId}
                onChange={(event) => setCandidatePackDraftId(event.target.value)}
              >
                {candidatePacks.filter((pack) => pack.status === "active").map((pack) => (
                  <option key={pack.id} value={pack.id}>
                    {pack.display_name} v{pack.version} ({pack.candidate_count} species)
                  </option>
                ))}
              </select>
            </label>
            <div className="data-row">
              <span>Apply</span>
              <button
                className="secondary-action"
                disabled={
                  !candidatePackDraftId ||
                  candidatePackDraftId === candidatePackSelection.effective_pack.id ||
                  isSavingCandidatePack
                }
                onClick={() => void saveSpeciesCandidatePack()}
                type="button"
              >
                {isSavingCandidatePack ? "Saving..." : "Use this pack"}
              </button>
              <small>Pack management is available in Species Suggestions.</small>
            </div>
          </div>
        ) : (
          <span className="meta-text">Loading the Stream candidate-pack selection...</span>
        )}
        {candidatePackSelection?.warning ? (
          <div className="notice-panel">{candidatePackSelection.warning}</div>
        ) : null}
        {candidatePackError ? <div className="error-panel compact-error">{candidatePackError}</div> : null}
        </div>
      </details>

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

          <div className="stream-live-workflow-strip" aria-label="Camera workflow">
            <span className={liveSessionRunning ? "is-active" : ""}>
              <strong>1</strong> Camera {liveSessionRunning ? "running" : "stopped"}
            </span>
            <span className={liveViewOpen ? "is-active" : ""}>
              <strong>2</strong> Live view {liveViewOpen ? "visible" : "hidden"}
            </span>
            <span className={liveMonitorRunning ? "is-active" : ""}>
              <strong>3</strong> Monitoring {liveMonitorRunning ? "on" : "off"}
            </span>
            <span className={liveAutoReviewEnabled ? "is-active" : ""}>
              <strong>4</strong> Auto-create {liveAutoReviewEnabled ? "on" : "off"}
            </span>
            <span className={streamReviewCount > 0 ? "is-active" : ""}>
              <strong>5</strong> Review Queue {streamReviewCount > 0 ? streamReviewCount : "clear"}
            </span>
          </div>

          <div className="stream-live-primary-panel">
            <div className="detail-actions stream-live-actions stream-live-primary-actions">
              {backendLiveSessionSupported ? (
                <button
                  className={liveSessionRunning ? "secondary-action" : "primary-action"}
                  disabled={
                    !liveUrl ||
                    isStartingLiveSession ||
                    isStoppingLiveSession ||
                    liveSessionStarting
                  }
                  onClick={() =>
                    liveSessionRunning
                      ? void stopLiveCameraSession()
                      : void startLiveCameraSession(false)
                  }
                  type="button"
                >
                  {liveSessionRunning
                    ? isStoppingLiveSession
                      ? "Stopping..."
                      : "Stop camera"
                    : isStartingLiveSession
                      ? "Starting..."
                      : "Start camera"}
                </button>
              ) : null}
              {liveViewOpen ? (
                <button className="secondary-action" onClick={stopLiveView} type="button">
                  Hide live view
                </button>
              ) : (
                <button
                  className={backendLiveSessionSupported ? "secondary-action" : "primary-action"}
                  disabled={!liveUrl || (backendLiveSessionSupported && !liveSessionRunning)}
                  onClick={openLiveView}
                  type="button"
                >
                  Show live view
                </button>
              )}
              {liveViewOpen ? (
                <button className="secondary-action" onClick={refreshLiveView} type="button">
                  Reconnect stream
                </button>
              ) : null}
              {liveMonitorRunning ? (
                <button
                  className="primary-action"
                  onClick={() => void stopLiveMonitoring()}
                  type="button"
                >
                  Stop monitoring
                </button>
              ) : (
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
                  {isEvaluatingLiveMotion ? "Starting..." : "Start monitoring"}
                </button>
              )}
              <label className="stream-live-primary-toggle stream-live-auto-review-toggle">
                <input
                  checked={liveAutoReviewEnabled}
                  disabled={isUpdatingAutoCreate}
                  onChange={(event) =>
                    void handleAutoCreateReviewCandidatesChange(event.target.checked)
                  }
                  type="checkbox"
                />
                <span>
                  <strong>Auto-create Review Queue candidates</strong>
                  <span>
                    Creates Review Queue items from completed activity sessions. Does not
                    update Bird Log.
                  </span>
                  <span>{liveAutoReviewStatusText}</span>
                </span>
              </label>
              <label className="stream-live-primary-toggle stream-live-auto-review-toggle">
                <input
                  checked={liveAutoIdentifyEnabled}
                  disabled={isUpdatingAutoIdentify}
                  onChange={(event) =>
                    void handleAutoIdentifyReviewCandidatesChange(event.target.checked)
                  }
                  type="checkbox"
                />
                <span>
                  <strong>Automatically run species identification on new review items</strong>
                  <span>
                    Runs one bounded local BioCLIP attempt after completed activity.
                    Suggestions remain evidence until you correct the review item.
                  </span>
                  <span>
                    {isUpdatingAutoIdentify
                      ? <>Updating identification setting...</>
                      : liveSession?.automatic_identification_status
                        ? formatLabel(liveSession.automatic_identification_status)
                        : liveAutoIdentifyEnabled
                          ? <>Enabled for new review items.</>
                          : <>Off.</>}
                  </span>
                  {liveSession?.last_auto_identification_message ? (
                    <span>{liveSession.last_auto_identification_message}</span>
                  ) : null}
                </span>
              </label>
              {streamReviewCount > 0 ? (
                <button
                  className="secondary-action"
                  onClick={() => onOpenReview(liveReviewQueueContext ?? undefined)}
                  type="button"
                >
                  Open Review Queue
                </button>
              ) : null}
            </div>
            <div className="stream-live-primary-status" aria-label="Camera and monitor status">
              <span>
                <strong>Camera</strong> {formatLabel(liveSession?.status ?? "stopped")}
              </span>
              <span>
                <strong>Live view</strong> {liveViewOpen ? "visible" : "hidden"}
              </span>
              <span>
                <strong>Monitoring</strong> {liveMonitorRunning ? "running" : "stopped"}
              </span>
              <span>
                <strong>Auto-create</strong> {liveAutoReviewEnabled ? "enabled" : "disabled"}
              </span>
              <span>
                <strong>Review Queue</strong>{" "}
                {streamReviewCount > 0 ? `${streamReviewCount} candidate(s)` : "clear"}
              </span>
              <span>
                <strong>Zone sessions</strong>{" "}
                {liveOpenActivitySessionCount > 0
                  ? `${liveOpenActivitySessionCount} open${
                      liveOpenActivityZones.length > 0
                        ? `: ${liveOpenActivityZones.join(", ")}`
                        : ""
                    }`
                  : "none open"}
              </span>
              {liveReadyActivitySessionCount > 0 ? (
                <span>
                  <strong>Ready for review</strong> {liveReadyActivitySessionCount}
                </span>
              ) : null}
              {liveLatestReviewQueueItemId ? (
                <span>
                  <strong>Latest candidate</strong> ready in Review Queue
                </span>
              ) : null}
              {backendLiveSessionSupported ? (
                <span>
                  <strong>Newest frame</strong> {liveSessionNewestFrameLabel}
                </span>
              ) : null}
            </div>
            {liveStatusNotice ? (
              <div className="stream-live-inline-status">
                <strong>{liveStatusNotice}</strong>
              </div>
            ) : null}
            <div className="stream-live-zone-actions">
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
                {drawMode
                  ? redrawZoneId
                    ? "Cancel redraw"
                    : "Cancel draw"
                  : "Draw new zone"}
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
          </div>

          {cameraCalibrationVisible ? (
            <details className="stream-live-secondary-panel stream-live-collapsible-panel">
              <summary>
                <span className="stream-live-panel-summary-copy">
                  <strong>Camera calibration</strong>
                  <span>Set daylight exposure first, then choose live and capture quality.</span>
                </span>
              </summary>
              <form className="stream-live-collapsible-body" onSubmit={handleSaveCameraTuning}>
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
                  {detail.playback.live_stream_type === "windows_dshow" ? (
                    <button
                      className="secondary-action"
                      disabled={
                        nativeCameraControlsBlocked ||
                        isOpeningCameraControls ||
                        isStartingLiveSession ||
                        isStoppingLiveSession
                      }
                      onClick={() => void handleOpenCameraControls()}
                      type="button"
                    >
                      {isOpeningCameraControls ? "Launching..." : "Open native controls"}
                    </button>
                  ) : null}
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
                Size, framerate, and input format apply when the camera restarts. Windows
                exposure, gain, brightness, focus, and low-light compensation use the camera's
                real driver controls. Stop the camera and monitoring before opening native
                controls. MockingBird cannot read or persist these driver-managed values.
              </span>
              {cameraTuningMessage ? (
                <span className="stream-live-hint">{cameraTuningMessage}</span>
              ) : null}
              {cameraTuningError ? (
                <span className="stream-live-hint is-error">{cameraTuningError}</span>
              ) : null}
              </form>
            </details>
          ) : null}

          {canMonitorLiveMotion ? (
            <details className="stream-live-secondary-panel stream-live-collapsible-panel">
              <summary>
                <span className="stream-live-panel-summary-copy">
                  <strong>Activity monitoring</strong>
                  <span>Whole-stream motion with optional Zone context.</span>
                </span>
              </summary>
              <div className="stream-live-collapsible-body">
              <div className="stream-live-panel-header">
                <div>
                  <strong>Review candidate handoff</strong>
                  <span>
                    Motion opens bounded activity sessions. Zones add context; review still
                    decides Bird Log and export truth.
                  </span>
                </div>
              </div>
              <div className="stream-live-field-guidance">
                <span>Motion watches the usable stream; a Zone adds context after motion is found.</span>
                <span>Use Privacy or Ignore Zones to exclude areas from monitoring.</span>
                <span>Use a Feeder, Ground, or Perch Zone to organize review activity.</span>
              </div>
              <div className="stream-live-sensitivity" aria-label="Monitoring sensitivity">
                {liveMonitorSensitivityOptions.map((option) => (
                  <button
                    className={liveMonitorSensitivity === option ? "selected" : ""}
                    disabled={liveMonitorRunning || isEvaluatingLiveMotion}
                    key={option}
                    onClick={() => setLiveMonitorSensitivity(option)}
                    type="button"
                  >
                    {liveMonitorSensitivitySettings[option].label}
                  </button>
                ))}
              </div>
              <div className="stream-live-monitor-facts">
                <span>
                  <strong>Auto-create</strong> {liveAutoReviewEnabled ? "on" : "off"}
                </span>
                <span>
                  <strong>Created</strong> {liveAutoReviewCount}
                </span>
                <span>
                  <strong>Activity state</strong> {liveActivityReviewStateLabel}
                </span>
                <span>
                  <strong>Quiet</strong>{" "}
                  {liveCooldownLabel ??
                    `${autoReviewQuietSeconds}s window / ${autoReviewMinDetections} min`}
                </span>
              </div>
              {liveAutoReviewLastCreated && liveReviewQueueItemId ? (
                <div className="detail-actions stream-live-actions">
                  <button
                    className="secondary-action"
                    onClick={() =>
                      onOpenReview(
                        liveReviewQueueContext ?? {
                          source: "live-motion",
                          search: liveReviewQueueItemId,
                          status: "unreviewed",
                        },
                      )
                    }
                    type="button"
                  >
                    Open auto-created review
                  </button>
                  {liveAutoReviewLastCreated ? (
                    <span className="stream-live-hint">
                      Last auto-created candidate {liveAutoReviewLastCreated}
                    </span>
                  ) : null}
                </div>
              ) : null}
              {liveAutoReviewError ? (
                <span className="stream-live-hint is-error">{liveAutoReviewError}</span>
              ) : null}
              <details
                className="stream-live-debug-details"
                onToggle={(event) => {
                  if (!event.currentTarget.open) {
                    setShowLiveMotionDebug(false);
                    setShowForegroundMask(false);
                  }
                }}
              >
                <summary>Developer details</summary>
                <div className="stream-live-collapsible-body">
                  <div className="stream-live-panel-header">
                    <label className="stream-live-debug-toggle">
                      <input
                        checked={showLiveMotionDebug}
                        onChange={(event) => {
                          setShowLiveMotionDebug(event.target.checked);
                          if (!event.target.checked) {
                            setShowForegroundMask(false);
                          }
                        }}
                        type="checkbox"
                      />
                      Show detection overlays
                    </label>
                    <label className="stream-live-debug-toggle">
                      <input
                        checked={showForegroundMask}
                        disabled={!liveMotionResult?.foreground_mask_data_url}
                        onChange={(event) => setShowForegroundMask(event.target.checked)}
                        type="checkbox"
                      />
                      Foreground mask
                    </label>
                  </div>
                  <details
                    className="stream-live-debug-details"
                    open={showLiveMotionDebug}
                    onToggle={(event) => setShowLiveMotionDebug(event.currentTarget.open)}
                  >
                    <summary>Detection details</summary>
                <div className="stream-live-calibration-grid">
                  <label>
                    <span>Monitoring focus</span>
                    <select
                      disabled={liveMonitorRunning || isEvaluatingLiveMotion}
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
                  <label>
                    <span>Quiet period</span>
                    <input
                      disabled={liveMonitorRunning || isEvaluatingLiveMotion}
                      min={1}
                      max={300}
                      onChange={(event) =>
                        setAutoReviewQuietSeconds(
                          Math.max(1, Math.min(300, Number(event.target.value) || 30)),
                        )
                      }
                      type="number"
                      value={autoReviewQuietSeconds}
                    />
                  </label>
                  <label>
                    <span>Min detections</span>
                    <input
                      disabled={liveMonitorRunning || isEvaluatingLiveMotion}
                      min={1}
                      max={100}
                      onChange={(event) =>
                        setAutoReviewMinDetections(
                          Math.max(1, Math.min(100, Number(event.target.value) || 1)),
                        )
                      }
                      type="number"
                      value={autoReviewMinDetections}
                    />
                  </label>
                  <div className="detail-actions stream-live-actions">
                    {feederFocusZone ? (
                      <button
                        className="secondary-action"
                        disabled={liveMonitorRunning || isEvaluatingLiveMotion}
                        onClick={() => setLiveMotionFocusZoneId(feederFocusZone.id)}
                        type="button"
                      >
                        Use Feeder Zone
                      </button>
                    ) : null}
                    <button
                      className="secondary-action"
                      disabled={liveMonitorRunning || isEvaluatingLiveMotion || !liveMotionFocusZoneId}
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
                    <strong>Source</strong>{" "}
                    {liveMotionResult?.source_frame_width && liveMotionResult.source_frame_height
                      ? `${liveMotionResult.source_frame_width}×${liveMotionResult.source_frame_height}`
                      : "waiting"}
                  </span>
                  <span>
                    <strong>Analysis</strong>{" "}
                    {liveMotionResult?.analysis_frame_width && liveMotionResult.analysis_frame_height
                      ? `${liveMotionResult.analysis_frame_width}×${liveMotionResult.analysis_frame_height}`
                      : "waiting"}
                  </span>
                  <span>
                    <strong>Foreground</strong>{" "}
                    {liveMotionResult?.foreground_model_state ?? "warming"}
                  </span>
                  <span>
                    <strong>Regions</strong> {liveMotionResult?.motion_regions.length ?? 0}
                  </span>
                  <span>
                    <strong>Tracks</strong> {liveMotionResult?.tracked_objects.length ?? 0}
                  </span>
                  <span>
                    <strong>Objects</strong> {liveMotionResult?.object_detector_boxes.length ?? 0}
                  </span>
                  <span>
                    <strong>Trigger</strong>{" "}
                    {liveMotionResult?.activity_triggers.length ? "qualified" : "watching"}
                  </span>
                  <span>
                    <strong>Freshness</strong> {formatAgeMs(liveMotionResult?.analysis_frame_age_ms)}
                  </span>
                  <span>
                    <strong>Dropped</strong> {liveMotionResult?.dropped_frame_count ?? 0}
                  </span>
                </div>
                <details className="stream-live-debug-details">
                  <summary>Detection view</summary>
                  <div className="stream-live-monitor-facts">
                    <span>
                      <strong>Analysis</strong>{" "}
                      {liveMotionResult?.analysis_frame_width && liveMotionResult.analysis_frame_height
                        ? `${liveMotionResult.analysis_frame_width}×${liveMotionResult.analysis_frame_height}`
                        : "waiting"}
                    </span>
                    <span>
                      <strong>Usable frame</strong>{" "}
                      {liveMotionResult?.zone_source_crop_width && liveMotionResult.zone_source_crop_height
                        ? `${liveMotionResult.zone_source_crop_width}×${liveMotionResult.zone_source_crop_height}`
                        : "waiting"}
                    </span>
                    <span>
                      <strong>Regions</strong> {liveMotionResult?.motion_regions.length ?? 0}
                    </span>
                    <span>
                      <strong>Tracks</strong> {liveMotionResult?.tracked_objects.length ?? 0}
                    </span>
                    <span>
                      <strong>Object boxes</strong> {liveMotionResult?.object_detector_boxes.length ?? 0}
                    </span>
                    <span>
                      <strong>Object tracks</strong> {liveMotionResult?.object_detector_tracks.length ?? 0}
                    </span>
                    <span>
                      <strong>Object trigger</strong>{" "}
                      {liveMotionResult?.activity_trigger_source === "object_verified"
                        ? "object verified"
                        : liveMotionResult?.activity_trigger_source === "motion_fallback"
                          ? "motion fallback"
                          : "watching"}
                    </span>
                    <span>
                      <strong>Detector crop</strong>{" "}
                      {liveMotionResult?.object_detector_zone_source_crop_width && liveMotionResult.object_detector_zone_source_crop_height
                        ? `${liveMotionResult.object_detector_zone_source_crop_width}×${liveMotionResult.object_detector_zone_source_crop_height}`
                        : "waiting"}
                    </span>
                    <span>
                      <strong>Detector input</strong>{" "}
                      {liveMotionResult?.object_detector_input_width && liveMotionResult.object_detector_input_height
                        ? `${liveMotionResult.object_detector_input_width}×${liveMotionResult.object_detector_input_height}`
                        : "waiting"}
                    </span>
                    <span>
                      <strong>Detector cadence</strong>{" "}
                      {liveMotionResult?.object_detector_cadence_seconds != null
                        ? `${liveMotionResult.object_detector_cadence_seconds.toFixed(2)} s`
                        : "waiting"}
                    </span>
                    <span>
                      <strong>Inference</strong>{" "}
                      {liveMotionResult?.object_detector_inference_latency_ms != null
                        ? `${liveMotionResult.object_detector_inference_latency_ms} ms`
                        : liveMotionResult?.object_detector_unavailable_reason
                          ? "unavailable"
                          : "waiting"}
                    </span>
                    <span>
                      <strong>Object queue</strong>{" "}
                      {liveMotionResult
                        ? `${liveMotionResult.object_detector_queue_depth}/${liveMotionResult.object_detector_queue_capacity}`
                        : "waiting"}
                    </span>
                    <span>
                      <strong>Object drops</strong>{" "}
                      {liveMotionResult?.object_detector_dropped_frame_count ?? 0}
                    </span>
                    <span>
                      <strong>Detector runtime</strong>{" "}
                      {formatLabel(liveMotionResult?.object_detector_runtime_state ?? "ready")}
                    </span>
                    <span>
                      <strong>Model</strong>{" "}
                      {liveMotionResult?.object_detector_model_loaded
                        ? "loaded"
                        : liveMotionResult?.object_detector_model_configuration_state ?? "waiting"}
                    </span>
                    <span>
                      <strong>Worker</strong>{" "}
                      {liveMotionResult?.object_detector_worker_alive ? "alive" : "not running"}
                    </span>
                    <span>
                      <strong>Active crop</strong>{" "}
                      {liveMotionResult?.object_detector_in_flight_job_identity
                        ? `${liveMotionResult.object_detector_in_flight_job_identity} · ${formatAgeMs(liveMotionResult.object_detector_in_flight_age_ms)}`
                        : "none"}
                    </span>
                    <span>
                      <strong>Latest success</strong>{" "}
                      {liveMotionResult?.object_detector_latest_successful_inference_latency_ms != null
                        ? `${liveMotionResult.object_detector_latest_successful_inference_latency_ms} ms · ${formatAgeMs(liveMotionResult.object_detector_last_completed_age_ms)} ago`
                        : "waiting"}
                    </span>
                    <span>
                      <strong>Timeouts</strong> {liveMotionResult?.object_detector_timed_out_count ?? 0}
                    </span>
                    <span>
                      <strong>Recovery</strong>{" "}
                      {liveMotionResult
                        ? `${liveMotionResult.object_detector_recovery_count} recoveries · ${liveMotionResult.object_detector_worker_reset_count} resets · ${liveMotionResult.object_detector_queue_replacement_count} replacements`
                        : "waiting"}
                    </span>
                    <span>
                      <strong>Device</strong>{" "}
                      {liveMotionResult?.object_detector_execution_device ?? "not selected"}
                    </span>
                    <span>
                      <strong>Runtime note</strong>{" "}
                      {liveMotionResult?.object_detector_last_safe_error_category
                        ? formatLabel(liveMotionResult.object_detector_last_safe_error_category)
                        : "none"}
                    </span>
                    <span>
                      <strong>Trigger</strong>{" "}
                      {liveMotionResult?.activity_triggers.length ? "qualified" : "watching"}
                    </span>
                    <span>
                      <strong>Foreground</strong>{" "}
                      {liveMotionResult?.foreground_model_state ?? "warming"}
                    </span>
                    <span>
                      <strong>Duplicates</strong> {liveMotionResult?.duplicate_frame_count ?? 0}
                    </span>
                    <span>
                      <strong>Dropped</strong> {liveMotionResult?.dropped_frame_count ?? 0}
                    </span>
                    <span>
                      <strong>Freshness</strong> {formatAgeMs(liveMotionResult?.analysis_frame_age_ms)}
                    </span>
                    <span>
                      <strong>Evidence profile</strong>{" "}
                      {liveMotionResult?.selected_evidence_profile_id ?? "not selected"}
                    </span>
                    <span>
                      <strong>High-res still</strong>{" "}
                      {liveMotionResult?.high_resolution_frame_width && liveMotionResult.high_resolution_frame_height
                        ? `${liveMotionResult.high_resolution_frame_width}×${liveMotionResult.high_resolution_frame_height}`
                        : liveMotionResult?.high_resolution_capture_failure_code
                          ? "not captured"
                          : "waiting"}
                    </span>
                    <span>
                      <strong>Activity crop</strong>{" "}
                      {liveMotionResult?.high_resolution_crop_width && liveMotionResult.high_resolution_crop_height
                        ? `${liveMotionResult.high_resolution_crop_width}×${liveMotionResult.high_resolution_crop_height}`
                        : liveMotionResult?.high_resolution_alignment_failure_code
                          ? "full still retained"
                          : "waiting"}
                    </span>
                    <span>
                      <strong>Capture latency</strong>{" "}
                      {liveMotionResult?.high_resolution_capture_latency_ms != null
                        ? `${liveMotionResult.high_resolution_capture_latency_ms} ms`
                        : "waiting"}
                    </span>
                    <span>
                      <strong>Track to capture</strong>{" "}
                      {liveMotionResult?.high_resolution_track_to_capture_delay_ms != null
                        ? `${liveMotionResult.high_resolution_track_to_capture_delay_ms} ms`
                        : "waiting"}
                    </span>
                  </div>
                  {liveMotionResult?.global_illumination_suppressed ? (
                    <span className="stream-live-hint">
                      Global illumination change was ignored for this frame.
                    </span>
                  ) : null}
                  {liveMotionResult?.latest_ignored_frame_reason ? (
                    <span className="stream-live-hint">
                      Latest ignored frame: {formatLabel(liveMotionResult.latest_ignored_frame_reason)}.
                    </span>
                  ) : null}
                  {liveMotionResult?.object_detector_unavailable_reason ? (
                    <span className="stream-live-hint">
                      Object detector: {formatLabel(liveMotionResult.object_detector_unavailable_reason)}.
                    </span>
                  ) : null}
                  {liveMotionResult?.high_resolution_capture_failure_code ? (
                    <span className="stream-live-hint">
                      High-resolution capture: {formatLabel(liveMotionResult.high_resolution_capture_failure_code)}.
                    </span>
                  ) : null}
                  {liveMotionResult?.high_resolution_alignment_failure_code ? (
                    <span className="stream-live-hint">
                      Crop alignment: {formatLabel(liveMotionResult.high_resolution_alignment_failure_code)}; full still remains the evidence context.
                    </span>
                  ) : null}
                </details>
                {liveQualityWarnings.length > 0 ? (
                  <div className="stream-live-suppressed-list">
                    <strong>Image quality</strong>
                    {liveQualityWarnings.map((warning) => (
                      <span key={warning}>{warning}</span>
                    ))}
                  </div>
                ) : null}
                {liveMotionGuidanceWarnings.length ? (
                  <div className="stream-live-suppressed-list">
                    <strong>Motion guidance</strong>
                    {liveMotionGuidanceWarnings.map((warning) => (
                      <span key={warning}>{warning}</span>
                    ))}
                  </div>
                ) : null}
              </details>
                </div>
              </details>
              </div>
            </details>
          ) : null}

          <div className={`stream-live-frame${drawMode ? " draw-mode" : ""}`}>
            <div className="stream-live-media-layer">
              {cameraNodePlayback ? (
                <CurrentFrameView
                  active={liveViewOpen}
                  alt={`${detail.stream.name} current camera frame`}
                  streamId={detail.stream.id}
                  onFrameChange={(frame: CurrentFrameMetadata) => {
                    if (frame.state === "unavailable") {
                      setLiveViewState("no_frames");
                      setLiveViewError("No current camera frame is available.");
                      return;
                    }
                    setLiveViewState("streaming");
                    setLiveViewError(null);
                    if (frame.width && frame.height) {
                      setLiveMediaSize({ width: frame.width, height: frame.height });
                    }
                  }}
                />
              ) : liveViewOpen && liveUrl ? (
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
              {showForegroundMask && liveMotionResult?.foreground_mask_data_url ? (
                <img
                  alt="Foreground mask for current analysis frame"
                  src={liveMotionResult.foreground_mask_data_url}
                  style={{
                    height: "100%",
                    imageRendering: "pixelated",
                    left: 0,
                    opacity: 0.48,
                    pointerEvents: "none",
                    position: "absolute",
                    top: 0,
                    width: "100%",
                  }}
                />
              ) : null}
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
              {showLiveMotionDebug
                ? liveMotionResult?.motion_regions.map((region, index) => {
                    const left = region.left;
                    const top = region.top;
                    const right = region.right;
                    const bottom = region.bottom;
                    if (
                      typeof left !== "number" ||
                      typeof top !== "number" ||
                      typeof right !== "number" ||
                      typeof bottom !== "number"
                    ) {
                      return null;
                    }
                    return (
                      <span
                        aria-label="Current motion region"
                        key={`motion-region-${index}`}
                        style={{
                          border: "2px solid #f8c85b",
                          boxSizing: "border-box",
                          height: `${Math.max(0, bottom - top) * 100}%`,
                          left: `${left * 100}%`,
                          pointerEvents: "none",
                          position: "absolute",
                          top: `${top * 100}%`,
                          width: `${Math.max(0, right - left) * 100}%`,
                        }}
                      />
                    );
                  })
                : null}
              {showLiveMotionDebug
                ? liveMotionResult?.tracked_objects.map((track, index) => {
                    const left = track.left;
                    const top = track.top;
                    const right = track.right;
                    const bottom = track.bottom;
                    if (
                      typeof left !== "number" ||
                      typeof top !== "number" ||
                      typeof right !== "number" ||
                      typeof bottom !== "number"
                    ) {
                      return null;
                    }
                    return (
                      <span
                        aria-label="Tracked object"
                        key={`tracked-object-${index}`}
                        style={{
                          border: "2px solid #54d6a8",
                          borderRadius: 3,
                          boxSizing: "border-box",
                          height: `${Math.max(0, bottom - top) * 100}%`,
                          left: `${left * 100}%`,
                          pointerEvents: "none",
                          position: "absolute",
                          top: `${top * 100}%`,
                          width: `${Math.max(0, right - left) * 100}%`,
                        }}
                      />
                    );
                  })
                : null}
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
              <details className="stream-live-debug-details stream-live-state-debug">
                <summary>Frame cache diagnostics</summary>
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
                  <strong>Activity frames</strong> {liveActivityFramesEvaluatedCount}
                </span>
                <span>
                  <strong>Candidates</strong> {liveActivityCandidateFrameCount}
                </span>
                <span>
                  <strong>Near misses</strong> {liveActivityNearMissCount}
                </span>
                <span>
                  <strong>Newest frame</strong>{" "}
                  {formatAgeMs(liveMotionResult?.newest_frame_age_ms)}
                </span>
                <span>
                  <strong>Last checked</strong> {liveLastChecked ?? "not yet"}
                </span>
                <span>
                  <strong>Monitor</strong> {liveMonitorRunning ? "running" : "not running"}
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
                  <strong>Tracks</strong> {liveMotionResult?.tracked_objects.length ?? 0}
                </span>
                <span>
                  <strong>Trigger</strong>{" "}
                  {liveMotionResult?.activity_triggers.length ? "qualified" : "watching"}
                </span>
                <span>
                  <strong>Freshness</strong> {formatAgeMs(liveMotionResult?.analysis_frame_age_ms)}
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
              </details>
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
                      label={liveReviewActivityCreated ? "Review candidate" : "Activity session"}
                      tone="review"
                    />
                  </div>
                </div>
                <p>
                  {liveReviewActivityCreated
                    ? `Open Review Queue to confirm or correct the activity in ${liveActivityAreaLabel}.`
                    : liveMotionResult?.uses_auto_regions
                      ? "Automatic activity is ready for review; a named Zone is optional context."
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
                    <strong>Detections</strong> {liveActivityDetectionCount}
                  </span>
                  <span>
                    <strong>Near misses</strong> {liveActivityNearMissCount}
                  </span>
                  <span>
                    <strong>Candidate frames</strong> {liveActivityCandidateFrameCount}
                  </span>
                  <span>
                    <strong>Saved candidates</strong> {liveActivitySavedCandidateCount}
                  </span>
                  <span>
                    <strong>State</strong> {liveActivityReviewStateLabel}
                  </span>
                  {liveCooldownLabel ? (
                    <span>
                      <strong>Quiet</strong> {liveCooldownLabel}
                    </span>
                  ) : null}
                  {liveActivityManualReviewNeeded ? (
                    <span>
                      <strong>Review</strong> manual review needed
                    </span>
                  ) : null}
                  <span>
                    <strong>Best frame</strong>{" "}
                    {liveBestMediaAssetId
                      ? "saved"
                      : (liveMotionResult?.activity_session_id ?? liveSession?.current_activity_session_id)
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
                  {liveMonitorRunning ? (
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
            <details className="stream-live-secondary-panel stream-live-collapsible-panel">
              <summary>
                <span className="stream-live-panel-summary-copy">
                  <strong>Manual tools</strong>
                  <span>Capture a frame, compare saved frames, or manually create review activity.</span>
                </span>
              </summary>
              <div className="stream-live-collapsible-body">
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
                    <strong>Saved-frame comparison</strong>
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
                            Open advanced evidence
                          </button>
                        ) : null}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
              </div>
            </details>
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

      <section className="panel stream-camera-health" aria-label="Camera health">
        <div className="section-heading">
          <div>
            <h2>Camera health</h2>
            <span className="meta-text">Saved operational state, separate from wildlife activity and review truth</span>
          </div>
          {cameraHealth ? (
            <StatusPill
              label={cameraHealthLabel(cameraHealth.health.state)}
              tone={cameraHealthTone(cameraHealth.health.state)}
            />
          ) : null}
        </div>
        {isLoadingCameraHealth ? (
          <span className="meta-text">Reading saved camera health…</span>
        ) : cameraHealthError ? (
          <div className="continuity-message is-error">
            <strong>Camera health could not be refreshed.</strong>
            <span>{cameraHealthError}</span>
          </div>
        ) : cameraHealth ? (
          <>
            <div className="monitoring-continuity-facts">
              <span><strong>Desired monitoring</strong> {cameraHealth.health.desired_mode === "armed" ? "Enabled" : "Disabled"}</span>
              <span><strong>Actual monitoring</strong> {formatLabel(cameraHealth.health.actual_state)}</span>
              <span><strong>Preview / readiness</strong> {formatLabel(cameraHealth.health.readiness_status)}</span>
              <span><strong>Last successful frame</strong> {cameraHealth.health.last_good_frame_at ? formatDateTime(cameraHealth.health.last_good_frame_at) : "Not yet received"}</span>
              <span><strong>Frame age</strong> {frameAgeLabel(cameraHealth.health.frame_age_seconds)}</span>
              <span><strong>Last evidence write</strong> {cameraHealth.health.last_evidence_persisted_at ? formatDateTime(cameraHealth.health.last_evidence_persisted_at) : "Not available"}</span>
              <span><strong>Open activity sessions</strong> {cameraHealth.health.open_activity_session_count}</span>
              <span><strong>Next retry</strong> {cameraHealth.health.next_retry_at ? formatDateTime(cameraHealth.health.next_retry_at) : "Not scheduled"}</span>
            </div>
            <div className="continuity-message">
              <strong>{cameraHealth.health.failure_reason ?? cameraHealth.health.message}</strong>
              <span>Preview availability, frame health, and wildlife activity are different signals. Health never creates a Visit, evidence, or reviewed label.</span>
            </div>
            <div className="panel-actions">
              {cameraHealth.health.desired_mode === "armed" ? (
                <>
                  <button className="secondary-button" disabled={isUpdatingMonitoringContinuity} onClick={() => void retryDurableMonitoring()} type="button">Retry now</button>
                  <button className="secondary-button" disabled={isUpdatingMonitoringContinuity} onClick={() => void setDurableMonitoringEnabled(false)} type="button">Disable monitoring</button>
                </>
              ) : (
                <button className="primary-button" disabled={isUpdatingMonitoringContinuity} onClick={() => void setDurableMonitoringEnabled(true)} type="button">Enable monitoring</button>
              )}
              <button className="secondary-button" disabled={isValidatingCameraHealth} onClick={() => void validateCameraHealthSetup()} type="button">{isValidatingCameraHealth ? "Validating setup…" : "Validate setup"}</button>
              <button className="text-action" onClick={onOpenCameraSetup} type="button">Edit camera setup</button>
            </div>
            {cameraHealth.incidents.length > 0 ? (
              <div className="continuity-message">
                <strong>Recent health history</strong>
                {cameraHealth.incidents.slice(0, 5).map((incident) => (
                  <span key={incident.id}>{formatLabel(incident.category)} · {incident.resolved_at ? `Resolved ${formatDateTime(incident.resolved_at)}` : `Open since ${formatDateTime(incident.started_at)}`}</span>
                ))}
              </div>
            ) : (
              <span className="meta-text">No recent camera-health incidents.</span>
            )}
          </>
        ) : null}
      </section>

      <section className="panel stream-monitoring-continuity" aria-label="Monitoring continuity">
        <div className="section-heading">
          <div>
            <h2>Monitoring continuity</h2>
            <span className="meta-text">Restart-safe camera monitoring intent</span>
          </div>
          <StatusPill
            label={continuityLabel}
            tone={continuityNeedsAttention ? "review" : "quiet"}
          />
        </div>
        {isLoadingMonitoringContinuity ? (
          <span className="meta-text">Reading saved monitoring intent...</span>
        ) : monitoringContinuityError ? (
          <div className="continuity-message is-error">
            <strong>Continuity status could not be loaded.</strong>
            <span>{monitoringContinuityError} Existing camera controls are unchanged.</span>
          </div>
        ) : monitoringPolicy && runtimeStatus ? (
          <>
            <div className="monitoring-continuity-facts">
              <span>
                <strong>Desired state</strong>{" "}
                {monitoringPolicy.mode === "armed"
                  ? "Monitoring enabled"
                  : "Monitoring disabled"}
              </span>
              <span>
                <strong>Actual runtime</strong> {formatLabel(runtimeStatus.actual_state)}
              </span>
              <span>
                <strong>Active sessions</strong> {runtimeStatus.active_session_count}
              </span>
              <span>
                <strong>Last start</strong>{" "}
                {runtimeStatus.last_start_attempt_at
                  ? formatDateTime(runtimeStatus.last_start_attempt_at)
                  : "Not started yet"}
              </span>
              <span>
                <strong>Next retry</strong>{" "}
                {runtimeStatus.next_retry_at
                  ? formatDateTime(runtimeStatus.next_retry_at)
                  : "Not scheduled"}
              </span>
              <span>
                <strong>Exposure</strong>{" "}
                {runtimeStatus.exposure_interval_active ? "Active" : "Closed"}
              </span>
              <span>
                <strong>Current healthy time</strong>{" "}
                {runtimeStatus.current_healthy_duration_seconds != null
                  ? formatVisitDuration(runtimeStatus.current_healthy_duration_seconds)
                  : "No active interval"}
              </span>
              <span>
                <strong>Exposure today</strong>{" "}
                {formatVisitDuration(runtimeStatus.durable_exposure_today_seconds)}
              </span>
              <span>
                <strong>Exposure history</strong>{" "}
                {runtimeStatus.exposure_history_available_from
                  ? formatDateTime(runtimeStatus.exposure_history_available_from)
                  : "Not collected yet"}
              </span>
              <span>
                <strong>Last fresh frame</strong>{" "}
                {runtimeStatus.latest_confirmed_exposure_at
                  ? formatDateTime(runtimeStatus.latest_confirmed_exposure_at)
                  : "Not confirmed yet"}
              </span>
              {runtimeStatus.most_recent_exposure_close_reason ? (
                <span>
                  <strong>Last exposure close</strong>{" "}
                  {formatLabel(runtimeStatus.most_recent_exposure_close_reason)}
                </span>
              ) : null}
            </div>
            <div className="continuity-message">
              <strong>{runtimeStatus.message}</strong>
              <span>
                {runtimeStatus.failure_code
                  ? "The camera needs attention before the next local start."
                  : "Enablement changes only saved local monitoring intent."}{" "}
                Monitoring never creates reviewed Bird Log truth.
              </span>
            </div>
            <div className="panel-actions">
              <button
                type="button"
                className={monitoringPolicy.mode === "armed" ? "secondary-button" : "primary-button"}
                disabled={isUpdatingMonitoringContinuity}
                onClick={() =>
                  void setDurableMonitoringEnabled(monitoringPolicy.mode !== "armed")
                }
              >
                {isUpdatingMonitoringContinuity
                  ? "Updating monitoring…"
                  : monitoringPolicy.mode === "armed"
                    ? "Disable monitoring"
                    : "Enable monitoring"}
              </button>
              {monitoringPolicy.mode === "armed" && (
                <button
                  type="button"
                  className="secondary-button"
                  disabled={isUpdatingMonitoringContinuity}
                  onClick={() => void retryDurableMonitoring()}
                >
                  Retry now
                </button>
              )}
            </div>
          </>
        ) : null}
      </section>

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
              {drawMode
                ? redrawZoneId
                  ? "Cancel redraw"
                  : "Cancel draw"
                : realLivePlayback
                  ? "Draw on live stream"
                  : "Draw new zone"}
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
                  <small>
                    {zone.monitoring_policy
                      ? zone.monitoring_policy.monitoring_enabled
                        ? "Monitoring on"
                        : "Monitoring off"
                      : "Suppression zone"}
                  </small>
                </button>
              ))}
            </div>

            <div className="zone-workspace">
              {selectedZone && zoneDraft && !drawMode ? (
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
                  <div className="zone-action-row">
                    <button className="primary-action" disabled={isSavingZone} type="submit">
                      Save zone
                    </button>
                    {realLivePlayback ? (
                      <button
                        className="secondary-action"
                        disabled={isSavingZone}
                        onClick={startRedrawMode}
                        type="button"
                      >
                        Redraw area
                      </button>
                    ) : null}
                    <button
                      className={
                        deleteZoneConfirmId === selectedZone.id
                          ? "danger-action"
                          : "text-action"
                      }
                      disabled={isSavingZone}
                      onClick={() => void handleDeleteSelectedZone()}
                      type="button"
                    >
                      {deleteZoneConfirmId === selectedZone.id
                        ? "Confirm remove"
                        : "Remove zone"}
                    </button>
                  </div>
                </form>
              ) : null}

              {selectedZone && selectedZone.monitoring_policy && zoneMonitoringDraft && !drawMode ? (
                <form className="zone-monitoring-form" onSubmit={handleSaveZoneMonitoring}>
                  <div className="item-title-row">
                    <div>
                      <strong>Monitoring</strong>
                      <span className="meta-text">
                        {selectedZone.monitoring_policy.uses_recommended_defaults
                          ? "Recommended settings for this Zone type"
                          : "Custom settings for this Zone"}
                      </span>
                    </div>
                    <StatusPill
                      label={
                        zoneMonitoringDraft.monitoring_enabled ? "Monitoring on" : "Monitoring off"
                      }
                      tone={zoneMonitoringDraft.monitoring_enabled ? "good" : "quiet"}
                    />
                  </div>
                  <label className="checkbox-row">
                    <input
                      checked={zoneMonitoringDraft.monitoring_enabled}
                      onChange={(event) =>
                        setZoneMonitoringDraft((current) =>
                          current ? { ...current, monitoring_enabled: event.target.checked } : current,
                        )
                      }
                      type="checkbox"
                    />
                    Monitor activity in this Zone
                  </label>
                  <label>
                    Activity sensitivity
                    <select
                      value={zoneMonitoringDraft.activity_sensitivity}
                      onChange={(event) =>
                        setZoneMonitoringDraft((current) =>
                          current
                            ? {
                                ...current,
                                activity_sensitivity: event.target.value as ZoneActivitySensitivity,
                              }
                            : current,
                        )
                      }
                    >
                      {zoneMonitoringSensitivityOptions.map((sensitivity) => (
                        <option key={sensitivity} value={sensitivity}>
                          {formatLabel(sensitivity)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <span className="meta-text">{zoneMonitoringSummary(selectedZone.monitoring_policy)}</span>
                  <details className="zone-monitoring-advanced">
                    <summary>Advanced timing and evidence</summary>
                    <div className="zone-monitoring-grid">
                      <span className="meta-text">
                        A short coherent track qualifies activity. The saved legacy sustained
                        duration is retained for compatibility and does not gate tracking.
                      </span>
                      <label>
                        Finish Visit after quiet (seconds)
                        <input
                          min="5"
                          max="300"
                          onChange={(event) =>
                            setZoneMonitoringDraft((current) =>
                              current
                                ? { ...current, quiet_period_seconds: Number(event.target.value) }
                                : current,
                            )
                          }
                          type="number"
                          value={zoneMonitoringDraft.quiet_period_seconds}
                        />
                      </label>
                      <label>
                        Maximum Visit length (seconds)
                        <input
                          min="30"
                          max="900"
                          onChange={(event) =>
                            setZoneMonitoringDraft((current) =>
                              current
                                ? {
                                    ...current,
                                    maximum_visit_duration_seconds: Number(event.target.value),
                                  }
                                : current,
                            )
                          }
                          type="number"
                          value={zoneMonitoringDraft.maximum_visit_duration_seconds}
                        />
                      </label>
                      <label>
                        Evidence frames
                        <input
                          min="1"
                          max="4"
                          onChange={(event) =>
                            setZoneMonitoringDraft((current) =>
                              current
                                ? { ...current, maximum_evidence_frames: Number(event.target.value) }
                                : current,
                            )
                          }
                          type="number"
                          value={zoneMonitoringDraft.maximum_evidence_frames}
                        />
                      </label>
                    </div>
                  </details>
                  {(() => {
                    const activity = (liveSession?.current_activity_session ??
                      liveSession?.last_activity ?? null) as Record<string, unknown> | null;
                    const status = activity?.zone_id === selectedZone.id
                      ? zoneSessionPolicyStatus(activity)
                      : null;
                    return status ? <span className="meta-text">{status}</span> : null;
                  })()}
                  <div className="zone-action-row">
                    <button
                      className="primary-action"
                      disabled={isSavingZoneMonitoring}
                      type="submit"
                    >
                      Save monitoring
                    </button>
                    <button
                      className="secondary-action"
                      disabled={isSavingZoneMonitoring}
                      onClick={() => void handleRestoreZoneMonitoringDefaults()}
                      type="button"
                    >
                      Restore recommended settings
                    </button>
                  </div>
                  <span className="meta-text">Changes affect future activity sessions.</span>
                </form>
              ) : selectedZone && !drawMode ? (
                <div className="zone-monitoring-restricted">
                  <strong>Suppression only</strong>
                  <span>
                    Privacy and Ignore Zones do not capture activity or expose monitoring controls.
                  </span>
                </div>
              ) : !drawMode ? (
                <span className="meta-text">No zone selected.</span>
              ) : null}

              {(drawMode || draftPolygon) && (
                <form className="draw-zone-panel" onSubmit={handleCreateZone}>
                  <div className="item-title-row">
                    <strong>
                      {redrawZoneId
                        ? draftPolygon
                          ? "Replacement shape"
                          : `Redrawing ${selectedZone?.name ?? "zone"}`
                        : draftPolygon
                          ? "New zone shape"
                          : "Drawing zone"}
                    </strong>
                    <StatusPill label={draftPolygon ? "Ready" : "Draw"} tone="quiet" />
                  </div>
                  {realLivePlayback ? (
                    <span className="meta-text">
                      {redrawZoneId
                        ? "Drag a replacement rectangle over the live camera surface, then save the new shape."
                        : "Drag a rectangle over the live camera surface, then name and save it here."}
                    </span>
                  ) : null}
                  {!redrawZoneId ? (
                    <>
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
                    </>
                  ) : null}
                  <div className="zone-action-row">
                    <button
                      className="primary-action"
                      disabled={isSavingZone || !draftPolygon}
                      type="submit"
                    >
                      {redrawZoneId ? "Save new shape" : "Save new zone"}
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
            <h2>Review Queue</h2>
          </div>
          <div className="list-stack">
            {streamReviewCount > 0 ? (
              <>
                {hasLocalLiveReviewQueueItem ? (
                  <div className="queue-mini">
                    <strong>Live activity candidate</strong>
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
          <div className="detail-actions">
            <button className="text-action" onClick={onOpenActivity} type="button">Open Activity</button>
            <button className="text-action" onClick={onOpenInsights} type="button">Open Zone & Feeder Insights</button>
          </div>
        </div>
      </section>

      <section className="panel stream-recent-visits">
        <div className="section-heading">
          <div>
            <h2>Recent Visits</h2>
            <p className="meta-text">The newest 12 Visits on this Stream. Review corrections remain the source of truth.</p>
          </div>
          <span className="meta-text">Stream history</span>
        </div>
        <div className="stream-visit-filter-row">
          <label>
            Show
            <select
              aria-label="Filter recent Visits by review status"
              onChange={(event) => setRecentVisitFilter(event.target.value as RecentVisitFilter)}
              value={recentVisitFilter}
            >
              <option value="all">All Visits</option>
              <option value="needs_review">Needs review</option>
              <option value="reviewed">Reviewed</option>
              <option value="review_outcomes">Dismissed, false, or blank outcomes</option>
            </select>
          </label>
          <label>
            Zone
            <select
              aria-label="Filter recent Visits by Zone"
              onChange={(event) => setRecentVisitZoneId(event.target.value)}
              value={recentVisitZoneId}
            >
              <option value="all">All configured zones</option>
              {detail.zones.map((zone) => (
                <option key={zone.id} value={zone.id}>
                  {zone.name} ({formatLabel(zone.zone_type)})
                </option>
              ))}
            </select>
          </label>
          {detail.zones.length === 0 ? (
            <span className="meta-text">No configured zones yet; unzoned Visits remain visible.</span>
          ) : null}
        </div>

        {recentVisitsError ? (
          <div className="stream-visit-history-error" role="alert">
            <span>{recentVisitsError}</span>
            <button
              className="secondary-action"
              onClick={() => setRecentVisitsRefreshToken((token) => token + 1)}
              type="button"
            >
              Retry
            </button>
          </div>
        ) : null}
        {isLoadingRecentVisits ? <span className="meta-text">Loading recent Visits…</span> : null}
        {!isLoadingRecentVisits && !recentVisitsError && detail.recentVisits.length === 0 ? (
          <EmptyState
            description={
              recentVisitFilter === "all" && recentVisitZoneId === "all"
                ? "No Visits have been captured for this Stream yet."
                : "No Visits match these review and Zone filters."
            }
            title="No recent Visits"
          />
        ) : null}
        <div className="stream-visit-list">
          {detail.recentVisits.map((visit) => {
            const isSelected = selectedRecentVisitId === visit.id;
            const reviewNeedsAttention = visit.review_status === "needs_review";
            return (
              <article className="stream-visit-card" key={visit.id}>
                <VisitEvidenceThumbnail evidence={visit.primary_evidence} />
                <div className="stream-visit-card-body">
                  <div className="item-title-row">
                    <div>
                      <h3>{formatDateTime(visit.captured_at)}</h3>
                      <span className="meta-text">
                        {visit.zone_name
                          ? visit.zone_type
                            ? `${visit.zone_name} (${formatLabel(visit.zone_type)})`
                            : visit.zone_name
                          : "No Zone assigned"}
                      </span>
                    </div>
                    <StatusPill
                      label={formatLabel(visit.review_status)}
                      tone={reviewNeedsAttention ? "review" : "good"}
                    />
                  </div>
                  <div className="stream-visit-facts">
                    <span>
                      Activity: {formatDateTime(visit.activity_started_at)}
                      {visit.activity_ended_at ? ` – ${formatDateTime(visit.activity_ended_at)}` : ""}
                    </span>
                    <span>Duration: {formatVisitDuration(visit.duration_seconds)}</span>
                    <span>
                      {visit.evidence_frame_count > 1
                        ? `${visit.evidence_frame_count} evidence frames`
                        : visit.evidence_frame_count === 1
                          ? "1 evidence frame"
                          : "No saved evidence"}
                    </span>
                  </div>
                  <div className="stream-visit-outcomes">
                    <strong>{reviewOutcomeLabel(visit)}</strong>
                    {visit.has_suggestion ? (
                      <span className="tag">
                        Suggestion: {visit.suggested_label ? formatLabel(visit.suggested_label) : "available"}
                      </span>
                    ) : null}
                  </div>
                  <div className="detail-actions">
                    <button
                      className="secondary-action"
                      onClick={() => void handleInspectRecentVisit(visit)}
                      type="button"
                    >
                      {isSelected ? "Reload evidence" : "Inspect"}
                    </button>
                    {reviewNeedsAttention ? (
                      <button
                        className="primary-action"
                        onClick={() =>
                          onOpenReview({
                            source: "live-motion",
                            search: visit.id,
                            status: "unreviewed",
                          })
                        }
                        type="button"
                      >
                        Review in Queue
                      </button>
                    ) : (
                      <button
                        className="text-action"
                        onClick={() => onOpenVisit(visit.id)}
                        type="button"
                      >
                        Open Visit detail
                      </button>
                    )}
                    <button
                      className="text-action"
                      onClick={() => onOpenVisit(visit.id)}
                      type="button"
                    >
                      Merge nearby
                    </button>
                  </div>
                </div>
                {isSelected ? (
                  <div className="stream-visit-inspection">
                    <div className="item-title-row">
                      <h3>Visit evidence</h3>
                      <button
                        className="text-action"
                        onClick={() => {
                          setSelectedRecentVisitId(null);
                          setSelectedRecentVisitDetail(null);
                          setRecentVisitDetailError(null);
                        }}
                        type="button"
                      >
                        Close
                      </button>
                    </div>
                    {isLoadingRecentVisitDetail ? <span className="meta-text">Loading evidence…</span> : null}
                    {recentVisitDetailError ? (
                      <div className="stream-visit-history-error" role="alert">
                        <span>{recentVisitDetailError}</span>
                        <button
                          className="secondary-action"
                          onClick={() => void handleInspectRecentVisit(visit)}
                          type="button"
                        >
                          Retry
                        </button>
                      </div>
                    ) : null}
                    {selectedRecentVisitDetail && !isLoadingRecentVisitDetail ? (
                      <>
                        {visitEvidenceFrames(selectedRecentVisitDetail, visit).length > 0 ? (
                          <VisitEvidenceSequence
                            frames={visitEvidenceFrames(selectedRecentVisitDetail, visit)}
                            surfaceOverlay={<StatusPill label={formatLabel(visit.review_status)} tone={reviewNeedsAttention ? "review" : "good"} />}
                          />
                        ) : (
                          <div className="stream-visit-thumbnail-unavailable">
                            No saved evidence is available for this Visit.
                          </div>
                        )}
                        <div className="stream-visit-inspection-facts">
                          <span>Captured: {formatDateTime(visit.captured_at)}</span>
                          <span>
                            Activity: {formatDateTime(visit.activity_started_at)}
                            {visit.activity_ended_at ? ` – ${formatDateTime(visit.activity_ended_at)}` : ""}
                          </span>
                          <span>Current review: {reviewOutcomeLabel(visit)}</span>
                        </div>
                      </>
                    ) : null}
                  </div>
                ) : null}
              </article>
            );
          })}
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
