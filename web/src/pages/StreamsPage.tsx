import { useEffect, useRef, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type {
  CameraSource,
  FolderImportEvidenceBatchCreateResponse,
  FolderImportEvidenceBatchDryRunResponse,
  FolderImportEvidenceBatchDryRunRequest,
  FolderImportPreviewRequest,
  FolderImportPreviewResponse,
  FolderImportCreatedMediaAsset,
  FolderImportRequest,
  FolderImportResponse,
  DemoDetectionRunCreate,
  DemoDetectionRunResult,
  DetectionProposal,
  DetectionProposalDecisionResult,
  DetectionRun,
  ExternalUrlPreviewResponse,
  ExternalUrlPreviewSaveResponse,
  MediaAsset,
  ModelAdapter,
  ModelAdapterRunResult,
  MotionCropPlan,
  MotionEvidence,
  MotionEvaluateSavedMediaResponse,
  MotionEvidencePromoteResponse,
  ReviewLabel,
  SavedMediaRetentionItem,
  SavedMediaRetentionReportResponse,
  SavedPreviewMotionEvidenceResponse,
  SourceConnectionStatus,
  SourceMonitorStatusResponse,
  SourceProviderConfiguration,
  SourceProviderDefinition,
  SourceSetupReviewResponse,
  Stream,
  Zone,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel } from "../utils";

interface StreamsPageProps {
  streams: Stream[];
  sources: CameraSource[];
  onOpenImport: () => void;
  onOpenStream: (streamId: string) => void;
  onOpenMotionEvidence: (motionEvidenceId: string) => void;
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenDetectionProposals: () => void;
  onOpenReview: () => void;
  onOpenBirdLog: () => void;
  onOpenExports: () => void;
}

function connectionTone(status: SourceConnectionStatus["status"]): "good" | "review" | "quiet" {
  if (status === "demo" || status === "configured") {
    return "good";
  }
  if (status === "not_configured" || status === "unavailable") {
    return "review";
  }
  return "quiet";
}

function readinessTone(
  readinessLevel: SourceSetupReviewResponse["readiness_level"],
): "good" | "review" | "quiet" {
  if (readinessLevel === "demo_ready" || readinessLevel === "metadata_ready") {
    return "good";
  }
  if (readinessLevel === "needs_setup" || readinessLevel === "unavailable") {
    return "review";
  }
  return "quiet";
}

function stepTone(
  status: SourceSetupReviewResponse["steps"][number]["status"],
): "good" | "review" | "quiet" {
  if (status === "complete" || status === "available") {
    return "good";
  }
  if (status === "missing" || status === "warning" || status === "unavailable") {
    return "review";
  }
  return "quiet";
}

function draftFromConfiguration(
  definition: SourceProviderDefinition | undefined,
  configuration: SourceProviderConfiguration | null,
): Record<string, string> {
  if (!definition) {
    return {};
  }
  return Object.fromEntries(
    definition.fields.map((field) => {
      const preview = configuration?.safe_config_preview[field.key];
      const value = !field.secret && preview && preview !== "not_configured" ? preview : "";
      return [field.key, value];
    }),
  );
}

function formatBytes(bytes?: number | null): string {
  if (bytes == null) {
    return "Unknown size";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function parseIntegerAtLeast(value: string, label: string, minimum: number): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed) || parsed < minimum) {
    throw new Error(`${label} must be a whole number of at least ${minimum}.`);
  }
  return parsed;
}

function parseAllowedExtensions(value: string): string[] | null {
  const extensions = value
    .split(",")
    .map((extension) => extension.trim())
    .filter(Boolean);
  return extensions.length > 0 ? extensions : null;
}

function isReviewableZone(zone: Zone): boolean {
  return zone.is_active && zone.zone_type !== "privacy" && zone.zone_type !== "ignore";
}

function isImageMedia(asset: MediaAsset): boolean {
  return asset.media_type === "image" || asset.content_type.startsWith("image/");
}

function mediaProvenanceHint(asset: MediaAsset): string {
  const notes = asset.notes?.toLowerCase() ?? "";
  if (
    notes.includes("external_url") ||
    notes.includes("external url") ||
    notes.includes("preview")
  ) {
    return "external_url saved snapshot";
  }
  if (notes.includes("folder")) {
    return "folder import";
  }
  if (notes.includes("manual") || notes.includes("import")) {
    return "manual import";
  }
  return "local media";
}

interface TimelineMediaActionState {
  proposalResult?: DemoDetectionRunResult | null;
  proposalDecisionResult?: DetectionProposalDecisionResult | null;
  proposalMessage?: string | null;
  proposalError?: string | null;
  evidenceResult?: SavedPreviewMotionEvidenceResponse | null;
  evidenceError?: string | null;
  promotionResult?: MotionEvidencePromoteResponse | null;
  promotionError?: string | null;
  localDetectorResult?: ModelAdapterRunResult | null;
  localDetectorError?: string | null;
  isCreatingProposal?: boolean;
  isConvertingProposal?: boolean;
  isCreatingEvidence?: boolean;
  isPromotingEvidence?: boolean;
  isRunningLocalDetector?: boolean;
}

interface StreamMotionCheckState {
  selectedMediaIds?: string[];
  result?: MotionEvaluateSavedMediaResponse | null;
  error?: string | null;
  isChecking?: boolean;
  isCreatingActivity?: boolean;
  lastCheckedAt?: string;
}

type SourceHealthActionStatus = "success" | "failure";

interface SourceHealthSnapshotState {
  status: SourceHealthActionStatus;
  timestamp: string;
  contentType?: string | null;
  error?: string | null;
}

interface SourceHealthCaptureState {
  status: SourceHealthActionStatus;
  timestamp: string;
  contentType?: string | null;
  mediaAssetId?: string | null;
  fileName?: string | null;
  error?: string | null;
}

interface SourceHealthActionState {
  lastSnapshotTest?: SourceHealthSnapshotState;
  lastCaptureByStreamId?: Record<string, SourceHealthCaptureState>;
}

type StorageGuardrailReadiness =
  | "OK"
  | "Watch accumulation"
  | "Review pending images"
  | "Export/reviewed media protected"
  | "Needs snapshots";

interface StorageGuardrailSummary {
  savedImageCount: number;
  savedImageTotalBytes: number | null;
  recentSavedImageCount: number;
  protectedMediaCount: number | null;
  reviewLinkedCount: number | null;
  unreviewedSavedImageCount: number | null;
  oldestSavedImageAt?: string | null;
  newestSavedImageAt?: string | null;
  readiness: StorageGuardrailReadiness;
  recommendedAction: string;
  retentionCoverage: "available" | "partial" | "unavailable";
}

type SnapshotWatchStatus = "idle" | "watching" | "complete" | "stopped" | "error";

type SnapshotWatchStopReason =
  | "user_stopped"
  | "max_captures_reached"
  | "source_error"
  | "storage_warning"
  | "not_enough_snapshots"
  | "completed";

interface SnapshotWatchState {
  isWatching: boolean;
  status: SnapshotWatchStatus;
  sourceId?: string | null;
  streamId?: string | null;
  watchStartedAt?: string | null;
  lastWatchTickAt?: string | null;
  nextCaptureAt?: string | null;
  intervalSeconds: number;
  maxCaptures: number;
  capturesAttempted: number;
  capturesSucceeded: number;
  motionChecksRun: number;
  lastWatchStatus: string;
  lastWatchError?: string | null;
  stopReason?: SnapshotWatchStopReason | null;
  isTickRunning: boolean;
  lastActivityResult?: string | null;
}

interface MediaLifecycleSummary {
  detectionRuns: DetectionRun[];
  proposals: DetectionProposal[];
  motionEvidence: MotionEvidence[];
  eventIds: string[];
  visitIds: string[];
  reviewLabels: ReviewLabel[];
  truthLabels: string[];
  proposalStatusText: string;
  detectionRunText: string;
  motionEvidenceText: string;
  promotedText: string;
  reviewTruthText: string;
  exportReadinessText: string;
  nextStep: string;
  hasPendingMotionEvidence: boolean;
  hasPromotedMotionEvidence: boolean;
}

const MEDIA_TIMELINE_LIMIT = 10;
const MOTION_SNAPSHOT_LIMIT = 5;
const LOCAL_IMAGE_DETECTOR_ADAPTER_ID = "local_image_detector";
const SNAPSHOT_WATCH_INTERVAL_OPTIONS = [10, 30, 60];
const SNAPSHOT_WATCH_CAPTURE_OPTIONS = [3, 5, 10];
const DEFAULT_SNAPSHOT_WATCH_INTERVAL_SECONDS = 10;
const DEFAULT_SNAPSHOT_WATCH_MAX_CAPTURES = 3;
const MIN_SNAPSHOT_WATCH_INTERVAL_SECONDS = 5;
const SNAPSHOT_WATCH_STORAGE_BLOCK_COUNT = 100;

function uniquePresent(values: Array<string | null | undefined>): string[] {
  return [...new Set(values.filter((value): value is string => Boolean(value)))];
}

function summarizeCounts(values: string[]): string {
  const counts = new Map<string, number>();
  for (const value of values) {
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([value, count]) => `${count} ${formatLabel(value)}`)
    .join(", ");
}

function sortNewestFirst<T extends { created_at: string }>(items: T[]): T[] {
  return [...items].sort(
    (left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
  );
}

function sortOldestFirst<T extends { created_at: string }>(items: T[]): T[] {
  return [...items].sort(
    (left, right) => new Date(left.created_at).getTime() - new Date(right.created_at).getTime(),
  );
}

function defaultMotionSnapshotIds(assets: MediaAsset[]): string[] {
  return sortOldestFirst(assets.filter(isImageMedia).slice(0, MOTION_SNAPSHOT_LIMIT)).map(
    (asset) => asset.id,
  );
}

function activitySessionLabel(status?: string | null): string {
  switch (status) {
    case "new_activity":
      return "New activity detected";
    case "ongoing_activity":
      return "Ongoing activity";
    case "cooldown_suppressed":
      return "Cooldown active";
    case "no_activity":
      return "No activity detected";
    default:
      return "Activity";
  }
}

function activitySessionTone(
  status?: string | null,
): "good" | "review" | "quiet" {
  if (status === "new_activity") {
    return "review";
  }
  if (status === "ongoing_activity" || status === "cooldown_suppressed") {
    return "quiet";
  }
  return "quiet";
}

function motionNextStep(
  result: MotionEvaluateSavedMediaResponse,
  createdEvidence: MotionEvidence | null,
): string {
  if (createdEvidence) {
    return "Review activity";
  }
  if (!result.activity_detected) {
    return "Capture more saved snapshots";
  }
  if (!result.can_create_review_activity) {
    return "Named Zone needed for review activity";
  }
  if (!result.should_create_review_activity) {
    return "Same activity";
  }
  return "Create review activity";
}

function focusedCropStatus(plan?: MotionCropPlan | null): string {
  if (!plan) {
    return "Not available";
  }
  if (plan.derived_crop_media_asset_id) {
    return "Focused crop available";
  }
  if (plan.is_full_frame_fallback) {
    return "Full snapshot fallback";
  }
  return "Focused crop planned";
}

type SourceHealthReadinessLabel =
  | "Ready for manual checks"
  | "Needs snapshot test"
  | "Needs saved images"
  | "Needs 2+ snapshots for motion"
  | "Check source setup"
  | "Motion check ready";

function sourceHealthReadinessTone(
  label: SourceHealthReadinessLabel,
): "good" | "review" | "quiet" {
  if (label === "Ready for manual checks" || label === "Motion check ready") {
    return "good";
  }
  if (label === "Check source setup") {
    return "review";
  }
  return "quiet";
}

function sourceNeedsSetup(
  connection: SourceConnectionStatus | null,
  setupReview: SourceSetupReviewResponse | null,
): boolean {
  return (
    connection?.status === "not_configured" ||
    connection?.status === "unavailable" ||
    connection?.status === "offline" ||
    connection?.status === "unsupported" ||
    setupReview?.readiness_level === "needs_setup" ||
    setupReview?.readiness_level === "unavailable"
  );
}

function sourceHealthReadiness(params: {
  isExternalUrlProvider: boolean;
  connection: SourceConnectionStatus | null;
  setupReview: SourceSetupReviewResponse | null;
  snapshotTest?: SourceHealthSnapshotState;
  savedImageCount: number;
  motionState: StreamMotionCheckState;
}): SourceHealthReadinessLabel {
  if (sourceNeedsSetup(params.connection, params.setupReview)) {
    return "Check source setup";
  }
  if (params.isExternalUrlProvider && !params.snapshotTest) {
    return "Needs snapshot test";
  }
  if (params.isExternalUrlProvider && params.snapshotTest?.status === "failure") {
    return "Check source setup";
  }
  if (params.savedImageCount === 0) {
    return "Needs saved images";
  }
  if (params.savedImageCount < 2) {
    return "Needs 2+ snapshots for motion";
  }
  if (!params.motionState.result) {
    return "Motion check ready";
  }
  return "Ready for manual checks";
}

function sourceHealthNextAction(
  label: SourceHealthReadinessLabel,
  motionResult?: MotionEvaluateSavedMediaResponse | null,
  createdEvidence?: MotionEvidence | null,
): string {
  if (createdEvidence) {
    return "Review activity.";
  }
  if (
    motionResult?.activity_detected &&
    motionResult.can_create_review_activity &&
    motionResult.should_create_review_activity
  ) {
    return "Create review activity.";
  }
  if (motionResult?.activity_detected && !motionResult.should_create_review_activity) {
    return "Ready for manual checks.";
  }
  switch (label) {
    case "Check source setup":
      return "Check source setup.";
    case "Needs snapshot test":
      return "Needs snapshot test - click Test snapshot.";
    case "Needs saved images":
      return "Capture ready - click Capture snapshot after a successful test.";
    case "Needs 2+ snapshots for motion":
      return "Needs 2 snapshots for motion.";
    case "Motion check ready":
      return "Motion ready - click Check motion.";
    case "Ready for manual checks":
      return "Ready for manual checks.";
    default:
      return "Ready for manual checks.";
  }
}

function formatHealthTimestamp(timestamp?: string | null): string {
  return timestamp ? formatDateTime(timestamp) : "time unknown";
}

function snapshotHealthText(snapshotTest?: SourceHealthSnapshotState): string {
  if (!snapshotTest) {
    return "Not tested in this session";
  }
  const when = formatHealthTimestamp(snapshotTest.timestamp);
  if (snapshotTest.status === "success") {
    const content = snapshotTest.contentType ? ` · ${snapshotTest.contentType}` : "";
    return `Succeeded at ${when}${content}`;
  }
  return `Failed at ${when}`;
}

function captureHealthText(
  capture: SourceHealthCaptureState | undefined,
  streamImages: MediaAsset[],
): string {
  if (capture) {
    const when = formatHealthTimestamp(capture.timestamp);
    if (capture.status === "success") {
      const fileName = capture.fileName ? ` · ${capture.fileName}` : "";
      return `Saved at ${when}${fileName}`;
    }
    return `Failed at ${when}`;
  }
  const latestImage = streamImages[0];
  if (latestImage) {
    return `No capture this session. Latest saved image: ${
      latestImage.original_filename || latestImage.filename
    }`;
  }
  return "No saved image yet";
}

function motionHealthText(motionState: StreamMotionCheckState): string {
  if (motionState.isChecking) {
    return "Checking motion...";
  }
  if (motionState.isCreatingActivity) {
    return "Creating review activity...";
  }
  if (motionState.error) {
    return `Failed at ${formatHealthTimestamp(motionState.lastCheckedAt)}`;
  }
  const result = motionState.result;
  if (!result) {
    return "Not checked in this session";
  }
  const checkedAt = ` at ${formatHealthTimestamp(motionState.lastCheckedAt)}`;
  if (!result.activity_detected) {
    return `No activity detected${checkedAt}`;
  }
  const label =
    result.strongest_activity_area_label ?? result.strongest_zone_id ?? "Activity area";
  return `Activity detected in ${label}${checkedAt}`;
}

function lastActivityHealthText(motionState: StreamMotionCheckState): string {
  const result = motionState.result;
  if (!result) {
    return "No activity checked yet";
  }
  if (!result.activity_detected) {
    return "No activity detected";
  }
  const label =
    result.strongest_activity_area_label ?? result.strongest_zone_id ?? "Activity area";
  return `${activitySessionLabel(result.session_status)} in ${label}`;
}

function storageGuardrailTone(
  readiness: StorageGuardrailReadiness,
): "good" | "review" | "quiet" {
  if (readiness === "OK") {
    return "good";
  }
  if (
    readiness === "Watch accumulation" ||
    readiness === "Review pending images" ||
    readiness === "Export/reviewed media protected"
  ) {
    return "review";
  }
  return "quiet";
}

function storageGuardrailSummary(
  streamImages: MediaAsset[],
  retentionItems: SavedMediaRetentionItem[],
  motionState: StreamMotionCheckState,
): StorageGuardrailSummary {
  const retentionByMediaId = new Map(
    retentionItems.map((item) => [item.media_asset_id, item]),
  );
  const coveredItems = streamImages
    .map((asset) => retentionByMediaId.get(asset.id))
    .filter((item): item is SavedMediaRetentionItem => Boolean(item));
  const savedImageTotalBytes = streamImages.reduce((total, asset) => {
    if (asset.file_size_bytes < 0) {
      return total;
    }
    return total + asset.file_size_bytes;
  }, 0);
  const createdTimes = streamImages
    .map((asset) => asset.created_at)
    .filter((value): value is string => Boolean(value))
    .sort((left, right) => new Date(left).getTime() - new Date(right).getTime());
  const protectedMediaCount =
    coveredItems.length > 0
      ? coveredItems.filter((item) => item.risk_level === "protected").length
      : null;
  const reviewLinkedCount =
    coveredItems.length > 0
      ? coveredItems.filter(
          (item) =>
            item.linked_motion_evidence_count > 0 ||
            item.linked_event_count > 0 ||
            item.linked_visit_count > 0 ||
            item.reviewed_truth_count > 0,
        ).length
      : null;
  const unreviewedSavedImageCount =
    coveredItems.length > 0
      ? coveredItems.filter((item) => item.reviewed_truth_count === 0).length
      : null;
  const retentionCoverage =
    streamImages.length === 0
      ? "available"
      : coveredItems.length === streamImages.length
        ? "available"
        : coveredItems.length > 0
          ? "partial"
          : "unavailable";

  let readiness: StorageGuardrailReadiness = "OK";
  if (protectedMediaCount && protectedMediaCount > 0) {
    readiness = "Export/reviewed media protected";
  } else if (reviewLinkedCount && reviewLinkedCount > 0) {
    readiness = "Review pending images";
  } else if (streamImages.length > 100) {
    readiness = "Watch accumulation";
  } else if (streamImages.length > 20) {
    readiness = "Watch accumulation";
  } else if (streamImages.length >= 2 && !motionState.result) {
    readiness = "OK";
  } else {
    readiness = "Needs snapshots";
  }

  let recommendedAction = "Capture another snapshot";
  if (streamImages.length === 0) {
    recommendedAction = "Capture another snapshot";
  } else if (streamImages.length === 1) {
    recommendedAction = "Capture another snapshot";
  } else if (motionState.result?.activity_detected) {
    recommendedAction = "Review activity";
  } else if (streamImages.length > 20 || (reviewLinkedCount && reviewLinkedCount > 0)) {
    recommendedAction = "Review activity";
  } else {
    recommendedAction = "Check motion";
  }
  if (protectedMediaCount && protectedMediaCount > 0) {
    recommendedAction = "Export reviewed data";
  }
  if (streamImages.length > 100 && (!reviewLinkedCount || reviewLinkedCount === 0)) {
    recommendedAction = "Configure cleanup later";
  }

  return {
    savedImageCount: streamImages.length,
    savedImageTotalBytes,
    recentSavedImageCount: streamImages.filter((asset) => {
      const createdAt = new Date(asset.created_at).getTime();
      return Number.isFinite(createdAt) && Date.now() - createdAt <= 24 * 60 * 60 * 1000;
    }).length,
    protectedMediaCount,
    reviewLinkedCount,
    unreviewedSavedImageCount,
    oldestSavedImageAt: createdTimes[0] ?? null,
    newestSavedImageAt: createdTimes[createdTimes.length - 1] ?? null,
    readiness,
    recommendedAction,
    retentionCoverage,
  };
}

function storageGuardrailCopy(summary: StorageGuardrailSummary): string {
  if (summary.savedImageCount < 2) {
    return `${summary.savedImageCount} saved images. Needs snapshots for motion.`;
  }
  if (summary.savedImageCount > 100) {
    return `${summary.savedImageCount} saved images. Storage warning before repeated checks.`;
  }
  if (summary.savedImageCount > 20) {
    return `${summary.savedImageCount} saved images. Watch accumulation before repeated checks.`;
  }
  return `${summary.savedImageCount} saved images. Motion check ready.`;
}

function optionalCountText(count: number | null): string {
  return count === null ? "Not available yet" : String(count);
}

function initialSnapshotWatchState(): SnapshotWatchState {
  return {
    isWatching: false,
    status: "idle",
    sourceId: null,
    streamId: null,
    watchStartedAt: null,
    lastWatchTickAt: null,
    nextCaptureAt: null,
    intervalSeconds: DEFAULT_SNAPSHOT_WATCH_INTERVAL_SECONDS,
    maxCaptures: DEFAULT_SNAPSHOT_WATCH_MAX_CAPTURES,
    capturesAttempted: 0,
    capturesSucceeded: 0,
    motionChecksRun: 0,
    lastWatchStatus: "Not watching.",
    lastWatchError: null,
    stopReason: null,
    isTickRunning: false,
    lastActivityResult: null,
  };
}

function snapshotWatchTone(status: SnapshotWatchStatus): "good" | "review" | "quiet" {
  if (status === "watching") {
    return "good";
  }
  if (status === "error") {
    return "review";
  }
  return "quiet";
}

function snapshotWatchLabel(status: SnapshotWatchStatus): string {
  switch (status) {
    case "watching":
      return "Watching";
    case "complete":
      return "Complete";
    case "stopped":
      return "Stopped";
    case "error":
      return "Error";
    case "idle":
    default:
      return "Not watching";
  }
}

function snapshotWatchStopReasonLabel(reason?: SnapshotWatchStopReason | null): string {
  switch (reason) {
    case "user_stopped":
      return "User stopped";
    case "max_captures_reached":
      return "Max captures reached";
    case "source_error":
      return "Source error";
    case "storage_warning":
      return "Storage warning";
    case "not_enough_snapshots":
      return "Needs more snapshots";
    case "completed":
      return "Completed";
    default:
      return "None";
  }
}

function snapshotWatchActivityText(result?: MotionEvaluateSavedMediaResponse | null): string {
  if (!result) {
    return "No motion check yet";
  }
  if (!result.activity_detected) {
    return "No activity detected";
  }
  return `Activity detected in ${
    result.strongest_activity_area_label ?? result.strongest_zone_id ?? "Activity area"
  }`;
}

function snapshotWatchNextAction(
  state: SnapshotWatchState,
  motionResult?: MotionEvaluateSavedMediaResponse | null,
  createdEvidence?: MotionEvidence | null,
): string {
  if (createdEvidence) {
    return "Review activity";
  }
  if (motionResult?.activity_detected) {
    return motionResult.can_create_review_activity ? "Review activity" : "Check motion";
  }
  if (state.status === "error") {
    return "Check source";
  }
  if (state.status === "complete") {
    return "Export reviewed data";
  }
  return state.capturesSucceeded < 2 ? "Capture another snapshot" : "Check motion";
}

function monitorIsActive(status?: SourceMonitorStatusResponse | null): boolean {
  return status?.status === "starting" || status?.status === "monitoring";
}

function monitorTone(status?: SourceMonitorStatusResponse | null): "good" | "review" | "quiet" {
  if (status?.status === "starting" || status?.status === "monitoring") {
    return "good";
  }
  if (status?.status === "error") {
    return "review";
  }
  return "quiet";
}

function monitorLabel(status?: SourceMonitorStatusResponse | null): string {
  switch (status?.status) {
    case "starting":
      return "Starting";
    case "monitoring":
      return "Monitoring";
    case "completed":
      return "Completed";
    case "stopped_by_user":
      return "Stopped";
    case "error":
      return "Needs attention";
    case "stopped":
    default:
      return "Stopped";
  }
}

function monitorStopReasonLabel(reason?: string | null): string {
  switch (reason) {
    case "user_stopped":
      return "User stopped";
    case "max_runtime_reached":
      return "Max runtime reached";
    case "max_snapshots_reached":
      return "Max snapshots reached";
    case "repeated_failures":
      return "Repeated failures";
    case "storage_guardrail":
      return "Storage guardrail";
    case "source_not_ready":
      return "Source not ready";
    case "error":
      return "Error";
    default:
      return "None";
  }
}

function monitorActivityText(status?: SourceMonitorStatusResponse | null): string {
  if (status?.last_activity_detected === true) {
    return "Activity detected";
  }
  if (status?.last_activity_detected === false) {
    return "No activity detected";
  }
  return status?.last_session_status === "needs_more_snapshots"
    ? "Needs 2 snapshots"
    : "No motion check yet";
}

function monitorActivityAreaText(status?: SourceMonitorStatusResponse | null): string {
  const area = status?.last_activity_area;
  if (!area) {
    return "None yet";
  }
  const label = area.label;
  const areaId = area.area_id;
  if (typeof label === "string" && label.trim()) {
    return label;
  }
  return typeof areaId === "string" && areaId.trim() ? areaId : "Activity area";
}

function buildMediaLifecycleSummary(
  asset: MediaAsset,
  detectionRuns: DetectionRun[],
  detectionProposals: DetectionProposal[],
  motionEvidence: MotionEvidence[],
  reviewLabels: ReviewLabel[],
): MediaLifecycleSummary {
  const proposals = sortNewestFirst(
    detectionProposals.filter((proposal) => proposal.media_asset_id === asset.id),
  );
  const runs = sortNewestFirst(detectionRuns.filter((run) => run.media_asset_id === asset.id));
  const evidence = sortNewestFirst(
    motionEvidence.filter((item) => item.snapshot_media_asset_id === asset.id),
  );
  const eventIds = uniquePresent([
    ...proposals.map((proposal) => proposal.event_id),
    ...evidence.map((item) => item.promoted_event_id),
  ]);
  const visitIds = uniquePresent([
    ...proposals.map((proposal) => proposal.visit_id),
    ...evidence.map((item) => item.promoted_visit_id),
  ]);
  const labels = sortNewestFirst(
    reviewLabels.filter(
      (label) =>
        (label.target_type === "event" && eventIds.includes(label.target_id)) ||
        (label.target_type === "visit" && visitIds.includes(label.target_id)),
    ),
  );
  const truthLabels = uniquePresent(labels.map((label) => label.label));
  const proposalStatusText =
    proposals.length > 0 ? summarizeCounts(proposals.map((proposal) => proposal.status)) : "None";
  const detectionRunText =
    runs.length > 0 ? summarizeCounts(runs.map((run) => run.status)) : "None";
  const motionEvidenceText =
    evidence.length > 0 ? summarizeCounts(evidence.map((item) => item.status)) : "None";
  const promotedText =
    eventIds.length > 0 || visitIds.length > 0
      ? [
          eventIds.length > 0 ? `Event ${eventIds.join(", ")}` : null,
          visitIds.length > 0 ? `Visit ${visitIds.join(", ")}` : null,
        ]
          .filter(Boolean)
          .join(" / ")
      : "Not promoted";
  const reviewTruthText = truthLabels.length > 0 ? truthLabels.join(", ") : "None inferable";
  const hasPendingMotionEvidence = evidence.some((item) => item.status === "pending");
  const hasPromotedMotionEvidence = evidence.some((item) => item.status === "promoted");
  const exportReadinessText =
    truthLabels.length > 0
      ? "Likely export-ready after reviewed-only export"
      : eventIds.length > 0 || visitIds.length > 0
        ? "Needs Review Queue correction"
        : proposals.length > 0 || evidence.length > 0
          ? "Needs review context"
          : "No evidence yet";
  const nextStep =
    truthLabels.length > 0
      ? "Create reviewed-only export"
      : eventIds.length > 0 || visitIds.length > 0
        ? "Correct in Review Queue"
        : hasPendingMotionEvidence
          ? "Review activity evidence"
          : proposals.length > 0
            ? "Send suggestion to Review"
            : isImageMedia(asset)
              ? "Analyze image or create review context"
              : "Use as media context only";

  return {
    detectionRuns: runs,
    proposals,
    motionEvidence: evidence,
    eventIds,
    visitIds,
    reviewLabels: labels,
    truthLabels,
    proposalStatusText,
    detectionRunText,
    motionEvidenceText,
    promotedText,
    reviewTruthText,
    exportReadinessText,
    nextStep,
    hasPendingMotionEvidence,
    hasPromotedMotionEvidence,
  };
}

function savedImageStatusLabel(summary: MediaLifecycleSummary): string {
  if (summary.truthLabels.length > 0) {
    return "Reviewed";
  }
  if (summary.eventIds.length > 0 || summary.visitIds.length > 0) {
    return "Needs review";
  }
  if (
    summary.proposals.length > 0 ||
    summary.detectionRuns.length > 0 ||
    summary.motionEvidence.length > 0
  ) {
    return "Suggestion available";
  }
  return "Not analyzed";
}

function savedImageStatusTone(summary: MediaLifecycleSummary): "good" | "review" | "quiet" {
  if (summary.truthLabels.length > 0) {
    return "good";
  }
  if (
    summary.eventIds.length > 0 ||
    summary.visitIds.length > 0 ||
    summary.proposals.length > 0 ||
    summary.detectionRuns.length > 0 ||
    summary.motionEvidence.length > 0
  ) {
    return "review";
  }
  return "quiet";
}

function savedImageNextAction(summary: MediaLifecycleSummary): string {
  if (summary.truthLabels.length > 0) {
    return "Export reviewed data";
  }
  if (summary.eventIds.length > 0 || summary.visitIds.length > 0) {
    return "Review item";
  }
  if (summary.proposals.length > 0 || summary.detectionRuns.length > 0) {
    return "Review suggestion";
  }
  if (summary.motionEvidence.length > 0) {
    return "Open review context";
  }
  return "Analyze image";
}

function modelAdapterTone(status?: ModelAdapter["status"]): "good" | "review" | "quiet" {
  if (status === "available") {
    return "good";
  }
  if (status === "not_configured" || status === "unavailable") {
    return "review";
  }
  return "quiet";
}

function canRunModelAdapter(adapter: ModelAdapter | null): boolean {
  return Boolean(adapter?.configuration_status?.can_run);
}

function modelAdapterSupportsMedia(adapter: ModelAdapter | null, asset: MediaAsset): boolean {
  const supportedTypes =
    adapter?.configuration_status?.supported_media_types ?? adapter?.supported_media_types ?? [];
  return supportedTypes.includes(asset.content_type) || supportedTypes.includes(asset.media_type);
}

function localDetectorReadinessCopy(adapter: ModelAdapter | null): string {
  if (!adapter) {
    return "Local detector readiness is unavailable. Demo analysis remains available.";
  }
  if (canRunModelAdapter(adapter)) {
    return "Ready for explicit local image analysis. Suggestions still require Review correction.";
  }
  return (
    adapter.configuration_status?.setup_hint ??
    adapter.notes ??
    "Configure a local detector model path before running this adapter."
  );
}

export function StreamsPage({
  streams,
  sources,
  onOpenImport,
  onOpenStream,
  onOpenMotionEvidence,
  onOpenEvent,
  onOpenVisit,
  onOpenDetectionProposals,
  onOpenReview,
  onOpenBirdLog,
  onOpenExports,
}: StreamsPageProps) {
  const [connectionStatuses, setConnectionStatuses] = useState<
    Record<string, SourceConnectionStatus>
  >({});
  const [providerDefinitions, setProviderDefinitions] = useState<SourceProviderDefinition[]>([]);
  const [providerConfigurations, setProviderConfigurations] = useState<
    Record<string, SourceProviderConfiguration>
  >({});
  const [setupReviews, setSetupReviews] = useState<Record<string, SourceSetupReviewResponse>>({});
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(sources[0]?.id ?? null);
  const [providerKey, setProviderKey] = useState("");
  const [configDraft, setConfigDraft] = useState<Record<string, string>>({});
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [setupError, setSetupError] = useState<string | null>(null);
  const [setupMessage, setSetupMessage] = useState<string | null>(null);
  const [previewResult, setPreviewResult] = useState<ExternalUrlPreviewResponse | null>(null);
  const [previewSaveResult, setPreviewSaveResult] =
    useState<ExternalUrlPreviewSaveResponse | null>(null);
  const [previewEvidenceResult, setPreviewEvidenceResult] =
    useState<SavedPreviewMotionEvidenceResponse | null>(null);
  const [previewPromotionResult, setPreviewPromotionResult] =
    useState<MotionEvidencePromoteResponse | null>(null);
  const [snapshotProposalResult, setSnapshotProposalResult] =
    useState<DemoDetectionRunResult | null>(null);
  const [snapshotProposalDecisionResult, setSnapshotProposalDecisionResult] =
    useState<DetectionProposalDecisionResult | null>(null);
  const [mediaAssets, setMediaAssets] = useState<MediaAsset[]>([]);
  const [savedMediaRetentionReport, setSavedMediaRetentionReport] =
    useState<SavedMediaRetentionReportResponse | null>(null);
  const [timelineDetectionRuns, setTimelineDetectionRuns] = useState<DetectionRun[]>([]);
  const [timelineDetectionProposals, setTimelineDetectionProposals] = useState<
    DetectionProposal[]
  >([]);
  const [timelineMotionEvidence, setTimelineMotionEvidence] = useState<MotionEvidence[]>([]);
  const [timelineReviewLabels, setTimelineReviewLabels] = useState<ReviewLabel[]>([]);
  const [localDetectorAdapter, setLocalDetectorAdapter] = useState<ModelAdapter | null>(null);
  const [previewZones, setPreviewZones] = useState<Zone[]>([]);
  const [selectedPreviewZoneId, setSelectedPreviewZoneId] = useState("");
  const [timelineZonesByStream, setTimelineZonesByStream] = useState<Record<string, Zone[]>>({});
  const [timelineSelectedZoneByStream, setTimelineSelectedZoneByStream] = useState<
    Record<string, string>
  >({});
  const [timelineZoneErrors, setTimelineZoneErrors] = useState<Record<string, string>>({});
  const [sourceHealthActions, setSourceHealthActions] = useState<
    Record<string, SourceHealthActionState>
  >({});
  const [timelineActionState, setTimelineActionState] = useState<
    Record<string, TimelineMediaActionState>
  >({});
  const [streamMotionCheckState, setStreamMotionCheckState] = useState<
    Record<string, StreamMotionCheckState>
  >({});
  const [streamMonitorStatuses, setStreamMonitorStatuses] = useState<
    Record<string, SourceMonitorStatusResponse>
  >({});
  const [streamMonitorErrors, setStreamMonitorErrors] = useState<Record<string, string>>({});
  const [streamMonitorLoading, setStreamMonitorLoading] = useState<Record<string, boolean>>({});
  const [folderPreviewResult, setFolderPreviewResult] =
    useState<FolderImportPreviewResponse | null>(null);
  const [folderImportResult, setFolderImportResult] = useState<FolderImportResponse | null>(null);
  const [folderEvidenceDryRunResult, setFolderEvidenceDryRunResult] =
    useState<FolderImportEvidenceBatchDryRunResponse | null>(null);
  const [folderEvidenceDryRunRequest, setFolderEvidenceDryRunRequest] =
    useState<FolderImportEvidenceBatchDryRunRequest | null>(null);
  const [folderEvidenceBatchCreateResult, setFolderEvidenceBatchCreateResult] =
    useState<FolderImportEvidenceBatchCreateResponse | null>(null);
  const [folderEvidenceResults, setFolderEvidenceResults] = useState<
    Record<string, SavedPreviewMotionEvidenceResponse>
  >({});
  const [folderEvidenceErrors, setFolderEvidenceErrors] = useState<Record<string, string>>({});
  const [folderRecursive, setFolderRecursive] = useState(false);
  const [folderAllowedExtensions, setFolderAllowedExtensions] = useState("jpg,jpeg,png,webp");
  const [folderMaxFiles, setFolderMaxFiles] = useState("500");
  const [folderMaxDepth, setFolderMaxDepth] = useState("1");
  const [folderImportNote, setFolderImportNote] = useState("");
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewSaveError, setPreviewSaveError] = useState<string | null>(null);
  const [previewEvidenceError, setPreviewEvidenceError] = useState<string | null>(null);
  const [previewPromotionError, setPreviewPromotionError] = useState<string | null>(null);
  const [snapshotProposalError, setSnapshotProposalError] = useState<string | null>(null);
  const [snapshotProposalMessage, setSnapshotProposalMessage] = useState<string | null>(null);
  const [previewZonesError, setPreviewZonesError] = useState<string | null>(null);
  const [mediaAssetsError, setMediaAssetsError] = useState<string | null>(null);
  const [savedMediaRetentionError, setSavedMediaRetentionError] = useState<string | null>(null);
  const [timelineLifecycleError, setTimelineLifecycleError] = useState<string | null>(null);
  const [localDetectorAdapterError, setLocalDetectorAdapterError] = useState<string | null>(null);
  const [folderPreviewError, setFolderPreviewError] = useState<string | null>(null);
  const [folderImportError, setFolderImportError] = useState<string | null>(null);
  const [folderEvidenceDryRunError, setFolderEvidenceDryRunError] = useState<string | null>(null);
  const [folderEvidenceBatchCreateError, setFolderEvidenceBatchCreateError] = useState<
    string | null
  >(null);
  const [isFetchingPreview, setIsFetchingPreview] = useState(false);
  const [isSavingPreview, setIsSavingPreview] = useState(false);
  const [isCreatingPreviewEvidence, setIsCreatingPreviewEvidence] = useState(false);
  const [isPromotingPreviewEvidence, setIsPromotingPreviewEvidence] = useState(false);
  const [isCreatingSnapshotProposal, setIsCreatingSnapshotProposal] = useState(false);
  const [isConvertingSnapshotProposal, setIsConvertingSnapshotProposal] = useState(false);
  const [isLoadingMediaAssets, setIsLoadingMediaAssets] = useState(false);
  const [isLoadingSavedMediaRetention, setIsLoadingSavedMediaRetention] = useState(false);
  const [isLoadingTimelineLifecycle, setIsLoadingTimelineLifecycle] = useState(false);
  const [isLoadingLocalDetectorAdapter, setIsLoadingLocalDetectorAdapter] = useState(false);
  const [isPreviewingFolderImport, setIsPreviewingFolderImport] = useState(false);
  const [isImportingFolderMedia, setIsImportingFolderMedia] = useState(false);
  const [isDryRunningFolderEvidence, setIsDryRunningFolderEvidence] = useState(false);
  const [isCreatingFolderEvidenceBatch, setIsCreatingFolderEvidenceBatch] = useState(false);
  const [folderEvidenceBatchConfirmed, setFolderEvidenceBatchConfirmed] = useState(false);
  const [folderEvidenceLoadingId, setFolderEvidenceLoadingId] = useState<string | null>(null);
  const [isSavingSetup, setIsSavingSetup] = useState(false);
  const [snapshotWatch, setSnapshotWatch] =
    useState<SnapshotWatchState>(() => initialSnapshotWatchState());
  const [snapshotWatchIntervalSeconds, setSnapshotWatchIntervalSeconds] = useState(
    DEFAULT_SNAPSHOT_WATCH_INTERVAL_SECONDS,
  );
  const [snapshotWatchMaxCaptures, setSnapshotWatchMaxCaptures] = useState(
    DEFAULT_SNAPSHOT_WATCH_MAX_CAPTURES,
  );
  const snapshotWatchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const snapshotWatchStateRef = useRef<SnapshotWatchState>(snapshotWatch);

  useEffect(() => {
    snapshotWatchStateRef.current = snapshotWatch;
  }, [snapshotWatch]);

  function clearSnapshotWatchTimer() {
    if (snapshotWatchTimerRef.current) {
      clearTimeout(snapshotWatchTimerRef.current);
      snapshotWatchTimerRef.current = null;
    }
  }

  function updateSnapshotWatchState(
    updater: SnapshotWatchState | ((current: SnapshotWatchState) => SnapshotWatchState),
  ) {
    setSnapshotWatch((current) => {
      const next = typeof updater === "function" ? updater(current) : updater;
      snapshotWatchStateRef.current = next;
      return next;
    });
  }

  useEffect(() => clearSnapshotWatchTimer, []);

  useEffect(() => {
    let isMounted = true;

    async function loadSourceSetup() {
      if (sources.length === 0) {
        setConnectionStatuses({});
        setProviderConfigurations({});
        setSetupReviews({});
        setConnectionError(null);
        return;
      }

      setConnectionError(null);
      try {
        const [definitions, connectionEntries, configurationEntries, reviewEntries] =
          await Promise.all([
            apiClient.getSourceProviderDefinitions(),
            Promise.all(
              sources.map(async (source) => [
                source.id,
                await apiClient.getSourceConnectionStatus(source.id),
              ] as const),
            ),
            Promise.all(
              sources.map(async (source) => [
                source.id,
                await apiClient.getSourceProviderConfiguration(source.id),
              ] as const),
            ),
            Promise.all(
              sources.map(async (source) => [
                source.id,
                await apiClient.getSourceSetupReview(source.id),
              ] as const),
            ),
          ]);
        if (isMounted) {
          setProviderDefinitions(definitions);
          setConnectionStatuses(Object.fromEntries(connectionEntries));
          setProviderConfigurations(Object.fromEntries(configurationEntries));
          setSetupReviews(Object.fromEntries(reviewEntries));
        }
      } catch (caught) {
        if (isMounted) {
          setConnectionError(
            caught instanceof Error ? caught.message : "Could not load source setup status.",
          );
        }
      }
    }

    void loadSourceSetup();

    return () => {
      isMounted = false;
    };
  }, [sources]);

  useEffect(() => {
    if (sources.length === 0) {
      setSelectedSourceId(null);
      return;
    }
    if (!selectedSourceId || !sources.some((source) => source.id === selectedSourceId)) {
      setSelectedSourceId(sources[0].id);
    }
  }, [sources, selectedSourceId]);

  const selectedSource = sources.find((source) => source.id === selectedSourceId) ?? null;
  const selectedConnection = selectedSourceId ? connectionStatuses[selectedSourceId] : null;
  const selectedConfiguration = selectedSourceId
    ? providerConfigurations[selectedSourceId] ?? null
    : null;
  const selectedSetupReview = selectedSourceId ? setupReviews[selectedSourceId] ?? null : null;
  const selectedSourceStreams = selectedSource
    ? streams.filter((stream) => stream.source_id === selectedSource.id)
    : [];
  const selectedSourceStreamIds = selectedSourceStreams.map((stream) => stream.id).join("|");
  const selectedReviewStreams = new Map(
    (selectedSetupReview?.streams ?? []).map((stream) => [stream.stream_id, stream]),
  );
  const selectedProviderDefinition =
    providerDefinitions.find((definition) => definition.provider_key === providerKey) ??
    providerDefinitions.find(
      (definition) => definition.provider_key === selectedConfiguration?.provider_key,
    );

  async function refreshStreamMonitorStatus(streamId: string): Promise<SourceMonitorStatusResponse | null> {
    try {
      const status = await apiClient.getStreamMonitorStatus(streamId);
      setStreamMonitorStatuses((current) => ({
        ...current,
        [streamId]: status,
      }));
      setStreamMonitorErrors((current) => ({
        ...current,
        [streamId]: "",
      }));
      return status;
    } catch (caught) {
      setStreamMonitorErrors((current) => ({
        ...current,
        [streamId]: caught instanceof Error ? caught.message : "Could not load monitoring status.",
      }));
      return null;
    }
  }

  useEffect(() => {
    let isMounted = true;

    async function loadSelectedMonitorStatuses() {
      if (selectedSourceStreams.length === 0) {
        setStreamMonitorStatuses({});
        setStreamMonitorErrors({});
        return;
      }
      const entries: Array<readonly [string, SourceMonitorStatusResponse]> = [];
      const errors: Array<readonly [string, string]> = [];
      await Promise.all(
        selectedSourceStreams.map(async (stream) => {
          try {
            entries.push([stream.id, await apiClient.getStreamMonitorStatus(stream.id)] as const);
          } catch (caught) {
            errors.push([
              stream.id,
              caught instanceof Error ? caught.message : "Could not load monitoring status.",
            ] as const);
          }
        }),
      );
      if (!isMounted) {
        return;
      }
      setStreamMonitorStatuses(Object.fromEntries(entries));
      setStreamMonitorErrors(Object.fromEntries(errors));
    }

    void loadSelectedMonitorStatuses();
    return () => {
      isMounted = false;
    };
  }, [selectedSourceStreamIds]);

  useEffect(() => {
    const activeStreamIds = selectedSourceStreams
      .filter((stream) => monitorIsActive(streamMonitorStatuses[stream.id]))
      .map((stream) => stream.id);
    if (activeStreamIds.length === 0) {
      return;
    }
    const interval = window.setInterval(() => {
      activeStreamIds.forEach((streamId) => {
        void refreshStreamMonitorStatus(streamId);
      });
    }, 5000);
    return () => window.clearInterval(interval);
  }, [selectedSourceStreamIds, streamMonitorStatuses]);

  useEffect(() => {
    clearSnapshotWatchTimer();
    updateSnapshotWatchState(initialSnapshotWatchState());
    setPreviewResult(null);
    setPreviewSaveResult(null);
    setPreviewEvidenceResult(null);
    setPreviewPromotionResult(null);
    setSnapshotProposalResult(null);
    setSnapshotProposalDecisionResult(null);
    setPreviewZones([]);
    setSelectedPreviewZoneId("");
    setPreviewError(null);
    setPreviewSaveError(null);
    setPreviewEvidenceError(null);
    setPreviewPromotionError(null);
    setSnapshotProposalError(null);
    setSnapshotProposalMessage(null);
    setPreviewZonesError(null);
    setFolderPreviewResult(null);
    setFolderImportResult(null);
    setFolderEvidenceDryRunResult(null);
    setFolderEvidenceDryRunRequest(null);
    setFolderEvidenceBatchCreateResult(null);
    setFolderPreviewError(null);
    setFolderImportError(null);
    setFolderEvidenceDryRunError(null);
    setFolderEvidenceBatchCreateError(null);
    setFolderEvidenceResults({});
    setFolderEvidenceErrors({});
    setStreamMotionCheckState({});
    setIsFetchingPreview(false);
    setIsSavingPreview(false);
    setIsCreatingPreviewEvidence(false);
    setIsPromotingPreviewEvidence(false);
    setIsCreatingSnapshotProposal(false);
    setIsConvertingSnapshotProposal(false);
    setIsPreviewingFolderImport(false);
    setIsImportingFolderMedia(false);
    setIsDryRunningFolderEvidence(false);
    setIsCreatingFolderEvidenceBatch(false);
    setFolderEvidenceBatchConfirmed(false);
    setFolderEvidenceLoadingId(null);
  }, [selectedSourceId, selectedConfiguration?.provider_key]);

  useEffect(() => {
    if (!selectedConfiguration) {
      return;
    }
    const definition = providerDefinitions.find(
      (item) => item.provider_key === selectedConfiguration.provider_key,
    );
    setProviderKey(selectedConfiguration.provider_key);
    setConfigDraft(draftFromConfiguration(definition, selectedConfiguration));
  }, [providerDefinitions, selectedConfiguration]);

  useEffect(() => {
    void loadMediaAssets();
  }, []);

  useEffect(() => {
    void loadSavedMediaRetentionReport();
  }, []);

  useEffect(() => {
    void loadTimelineLifecycleData();
  }, []);

  useEffect(() => {
    void loadLocalDetectorAdapter();
  }, []);

  function handleProviderChange(nextProviderKey: string) {
    const definition = providerDefinitions.find((item) => item.provider_key === nextProviderKey);
    const matchingConfiguration =
      selectedConfiguration?.provider_key === nextProviderKey ? selectedConfiguration : null;
    setProviderKey(nextProviderKey);
    setConfigDraft(draftFromConfiguration(definition, matchingConfiguration));
    setSetupError(null);
    setSetupMessage(null);
  }

  async function handleSaveProviderConfiguration(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSourceId || !selectedProviderDefinition) {
      return;
    }

    const config: Record<string, string | null> = {};
    for (const field of selectedProviderDefinition.fields) {
      const draftValue = configDraft[field.key]?.trim() ?? "";
      const existingPreview = selectedConfiguration?.safe_config_preview[field.key];
      if (field.secret && !draftValue && existingPreview === "configured") {
        config[field.key] = "configured";
      } else {
        config[field.key] = draftValue || null;
      }
    }

    setIsSavingSetup(true);
    setSetupError(null);
    setSetupMessage(null);
    try {
      const configuration = await apiClient.updateSourceProviderConfiguration(selectedSourceId, {
        provider_key: selectedProviderDefinition.provider_key,
        config,
      });
      const [connection, setupReview] = await Promise.all([
        apiClient.getSourceConnectionStatus(selectedSourceId),
        apiClient.getSourceSetupReview(selectedSourceId),
      ]);
      setProviderConfigurations((current) => ({
        ...current,
        [selectedSourceId]: configuration,
      }));
      setConnectionStatuses((current) => ({
        ...current,
        [selectedSourceId]: connection,
      }));
      setSetupReviews((current) => ({
        ...current,
        [selectedSourceId]: setupReview,
      }));
      setSetupMessage("Source setup metadata saved.");
    } catch (caught) {
      setSetupError(caught instanceof Error ? caught.message : "Could not save source setup.");
    } finally {
      setIsSavingSetup(false);
    }
  }

  async function loadMediaAssets(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoadingMediaAssets(true);
    }
    setMediaAssetsError(null);
    try {
      setMediaAssets(await apiClient.getMediaAssets());
    } catch (caught) {
      setMediaAssetsError(
        caught instanceof Error ? caught.message : "Could not load saved Stream media.",
      );
    } finally {
      if (showLoading) {
        setIsLoadingMediaAssets(false);
      }
    }
  }

  async function loadSavedMediaRetentionReport(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoadingSavedMediaRetention(true);
    }
    setSavedMediaRetentionError(null);
    try {
      setSavedMediaRetentionReport(await apiClient.getSavedMediaRetentionReport());
    } catch (caught) {
      setSavedMediaRetentionError(
        caught instanceof Error
          ? caught.message
          : "Could not load storage guardrails.",
      );
    } finally {
      if (showLoading) {
        setIsLoadingSavedMediaRetention(false);
      }
    }
  }

  async function refreshMediaAndStorage(): Promise<{
    nextMediaAssets: MediaAsset[];
    nextRetentionReport: SavedMediaRetentionReportResponse | null;
  }> {
    setMediaAssetsError(null);
    setSavedMediaRetentionError(null);
    try {
      const [nextMediaAssets, nextRetentionReport] = await Promise.all([
        apiClient.getMediaAssets(),
        apiClient.getSavedMediaRetentionReport(),
      ]);
      setMediaAssets(nextMediaAssets);
      setSavedMediaRetentionReport(nextRetentionReport);
      return { nextMediaAssets, nextRetentionReport };
    } catch (caught) {
      const message =
        caught instanceof Error ? caught.message : "Could not refresh saved images.";
      setMediaAssetsError(message);
      setSavedMediaRetentionError(message);
      return { nextMediaAssets: mediaAssets, nextRetentionReport: savedMediaRetentionReport };
    }
  }

  async function loadTimelineLifecycleData(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoadingTimelineLifecycle(true);
    }
    setTimelineLifecycleError(null);
    try {
      const [runs, proposals, evidenceResponse, labels] = await Promise.all([
        apiClient.getDetectionRuns(),
        apiClient.getDetectionProposals(),
        apiClient.listMotionEvidence({ status: "all" }),
        apiClient.getReviewLabels(),
      ]);
      setTimelineDetectionRuns(runs);
      setTimelineDetectionProposals(proposals);
      setTimelineMotionEvidence(evidenceResponse.motion_evidence);
      setTimelineReviewLabels(labels);
    } catch (caught) {
      setTimelineLifecycleError(
        caught instanceof Error ? caught.message : "Could not load saved image status.",
      );
    } finally {
      if (showLoading) {
        setIsLoadingTimelineLifecycle(false);
      }
    }
  }

  async function refreshLifecycleAndStorage() {
    await Promise.all([
      loadTimelineLifecycleData({ showLoading: false }),
      loadSavedMediaRetentionReport({ showLoading: false }),
    ]);
  }

  async function loadLocalDetectorAdapter(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoadingLocalDetectorAdapter(true);
    }
    setLocalDetectorAdapterError(null);
    try {
      setLocalDetectorAdapter(
        await apiClient.getModelAdapter(LOCAL_IMAGE_DETECTOR_ADAPTER_ID),
      );
    } catch (caught) {
      setLocalDetectorAdapter(null);
      setLocalDetectorAdapterError(
        caught instanceof Error
          ? caught.message
          : "Could not load local detector readiness.",
      );
    } finally {
      if (showLoading) {
        setIsLoadingLocalDetectorAdapter(false);
      }
    }
  }

  async function refreshSourceSetupStatuses() {
    try {
      const [connectionEntries, reviewEntries] = await Promise.all([
        Promise.all(
          sources.map(async (source) => [
            source.id,
            await apiClient.getSourceConnectionStatus(source.id),
          ] as const),
        ),
        Promise.all(
          sources.map(async (source) => [
            source.id,
            await apiClient.getSourceSetupReview(source.id),
          ] as const),
        ),
      ]);
      setConnectionStatuses(Object.fromEntries(connectionEntries));
      setSetupReviews(Object.fromEntries(reviewEntries));
    } catch (caught) {
      setConnectionError(
        caught instanceof Error ? caught.message : "Could not load source setup status.",
      );
    }
  }

  function updateSourceHealthAction(sourceId: string, patch: SourceHealthActionState) {
    setSourceHealthActions((current) => {
      const existing = current[sourceId] ?? {};
      return {
        ...current,
        [sourceId]: {
          ...existing,
          ...patch,
          lastCaptureByStreamId: {
            ...(existing.lastCaptureByStreamId ?? {}),
            ...(patch.lastCaptureByStreamId ?? {}),
          },
        },
      };
    });
  }

  async function saveStillImagePreviewForStream(
    sourceId: string,
    streamId: string | null,
  ): Promise<ExternalUrlPreviewSaveResponse> {
    const result = await apiClient.saveExternalUrlPreview(sourceId, {
      stream_id: streamId,
    });
    setPreviewSaveResult(result);
    const captureStreamId = result.stream_id ?? streamId;
    if (captureStreamId) {
      updateSourceHealthAction(sourceId, {
        lastCaptureByStreamId: {
          [captureStreamId]: {
            status: result.status === "saved" ? "success" : "failure",
            timestamp: result.fetched_at ?? new Date().toISOString(),
            contentType: result.content_type,
            mediaAssetId: result.media_asset_id,
            fileName: result.file_name,
            error: result.status === "saved" ? null : result.message,
          },
        },
      });
    }
    return result;
  }

  async function handleFetchStillImagePreview() {
    if (!selectedSourceId) {
      return;
    }

    const sourceId = selectedSourceId;
    setIsFetchingPreview(true);
    setPreviewError(null);
    setPreviewResult(null);
    setPreviewSaveError(null);
    setPreviewSaveResult(null);
    setPreviewEvidenceError(null);
    setPreviewEvidenceResult(null);
    setPreviewPromotionError(null);
    setPreviewPromotionResult(null);
    setSnapshotProposalError(null);
    setSnapshotProposalMessage(null);
    setSnapshotProposalResult(null);
    setSnapshotProposalDecisionResult(null);
    try {
      const result = await apiClient.fetchExternalUrlPreview(sourceId, {});
      setPreviewResult(result);
      updateSourceHealthAction(sourceId, {
        lastSnapshotTest: {
          status: result.status === "available" ? "success" : "failure",
          timestamp: result.fetched_at ?? new Date().toISOString(),
          contentType: result.content_type,
          error: result.status === "available" ? null : result.message,
        },
      });
    } catch (caught) {
      const error = caught instanceof Error ? caught.message : "Could not test snapshot.";
      setPreviewError(error);
      updateSourceHealthAction(sourceId, {
        lastSnapshotTest: {
          status: "failure",
          timestamp: new Date().toISOString(),
          error,
        },
      });
    } finally {
      setIsFetchingPreview(false);
    }
  }

  async function handleSaveStillImagePreview() {
    if (!selectedSourceId) {
      return;
    }

    const sourceId = selectedSourceId;
    const streamId = selectedFirstStream?.id ?? null;
    setIsSavingPreview(true);
    setPreviewSaveError(null);
    setPreviewSaveResult(null);
    setPreviewEvidenceError(null);
    setPreviewEvidenceResult(null);
    setPreviewPromotionError(null);
    setPreviewPromotionResult(null);
    setSnapshotProposalError(null);
    setSnapshotProposalMessage(null);
    setSnapshotProposalResult(null);
    setSnapshotProposalDecisionResult(null);
    try {
      await saveStillImagePreviewForStream(sourceId, streamId);
      await refreshMediaAndStorage();
    } catch (caught) {
      const error = caught instanceof Error ? caught.message : "Could not capture snapshot.";
      setPreviewSaveError(error);
      if (streamId) {
        updateSourceHealthAction(sourceId, {
          lastCaptureByStreamId: {
            [streamId]: {
              status: "failure",
              timestamp: new Date().toISOString(),
              error,
            },
          },
        });
      }
    } finally {
      setIsSavingPreview(false);
    }
  }

  function buildSnapshotProposalPayload(): DemoDetectionRunCreate | null {
    if (!previewSaveResult?.media_asset_id) {
      return null;
    }

    return {
      media_asset_id: previewSaveResult.media_asset_id,
      zone_id: selectedPreviewZoneId || null,
      label: "bird",
      confidence: 0.72,
      suggested_subject_label: "unknown_bird",
      suggested_species: "unknown_bird",
      notes:
        "External URL snapshot smoke path demo detector evidence only. " +
        "No model inspected the media and no reviewed truth was created.",
    };
  }

  async function handleCreateSnapshotProposal() {
    const payload = buildSnapshotProposalPayload();
    if (!payload) {
      setSnapshotProposalError("Capture a snapshot before analyzing the image.");
      return;
    }

    setIsCreatingSnapshotProposal(true);
    setSnapshotProposalError(null);
    setSnapshotProposalMessage(null);
    setSnapshotProposalDecisionResult(null);
    try {
      const result = await apiClient.createDemoDetectionRun(payload);
      setSnapshotProposalResult(result);
      setSnapshotProposalMessage(
        result.proposals.length > 0
          ? "Demo analysis created a suggested label. Review correction still creates reviewed data."
          : "Demo analysis completed without a suggested label.",
      );
      await refreshLifecycleAndStorage();
    } catch (caught) {
      setSnapshotProposalError(
        caught instanceof Error ? caught.message : "Image analysis could not be created.",
      );
    } finally {
      setIsCreatingSnapshotProposal(false);
    }
  }

  async function handleConvertSnapshotProposal() {
    const proposal = snapshotProposalResult?.proposals[0] ?? null;
    if (!proposal) {
      setSnapshotProposalError(
        "Analyze the image before sending a suggestion to Review.",
      );
      return;
    }

    setIsConvertingSnapshotProposal(true);
    setSnapshotProposalError(null);
    setSnapshotProposalMessage(null);
    try {
      const result = await apiClient.decideDetectionProposal(proposal.id, {
        decision: "convert_to_event",
        event_title: "External URL snapshot proposal review",
        subject_label: "unknown_bird",
        species_guess: "unknown_bird",
        notes: "Converted from explicit external URL snapshot proposal action; still needs review/correction.",
      });
      setSnapshotProposalDecisionResult(result);
      setSnapshotProposalMessage(
        "Sent suggestion to Review. No reviewed data was created.",
      );
      await refreshLifecycleAndStorage();
    } catch (caught) {
      setSnapshotProposalError(
        caught instanceof Error
          ? caught.message
          : "Suggestion could not be sent to Review.",
      );
    } finally {
      setIsConvertingSnapshotProposal(false);
    }
  }

  async function handleCreateMotionEvidenceFromSavedPreview() {
    if (!previewSaveResult?.media_asset_id) {
      return;
    }
    if (!selectedPreviewZoneId) {
      setPreviewEvidenceError("Choose an active reviewable Zone before creating evidence.");
      return;
    }

    setIsCreatingPreviewEvidence(true);
    setPreviewEvidenceError(null);
    setPreviewEvidenceResult(null);
    setPreviewPromotionError(null);
    setPreviewPromotionResult(null);
    try {
      const result = await apiClient.createMotionEvidenceFromMedia(
        previewSaveResult.media_asset_id,
        {
          stream_id: previewSaveResult.stream_id ?? selectedFirstStream?.id ?? null,
          zone_id: selectedPreviewZoneId,
          note: "Saved preview review handoff.",
          reason: "User requested pending evidence from saved media.",
          duplicate_policy: "skip_existing",
        },
      );
      setPreviewEvidenceResult(result);
      await refreshLifecycleAndStorage();
    } catch (caught) {
      setPreviewEvidenceError(
        caught instanceof Error ? caught.message : "Could not create pending evidence.",
      );
    } finally {
      setIsCreatingPreviewEvidence(false);
    }
  }

  async function handlePromotePreviewEvidence() {
    if (!previewEvidenceResult?.motion_evidence_id) {
      return;
    }

    setIsPromotingPreviewEvidence(true);
    setPreviewPromotionError(null);
    setPreviewPromotionResult(null);
    try {
      const result = await apiClient.promoteMotionEvidence(
        previewEvidenceResult.motion_evidence_id,
        {
          event_title: "External URL snapshot review",
          visit_label_hint: "unknown_animal",
          notes: "Promoted by explicit external URL snapshot capture-to-review action.",
          create_event: true,
          create_visit: true,
          attach_snapshot_media_asset_id: previewSaveResult?.media_asset_id ?? undefined,
        },
      );
      setPreviewPromotionResult(result);
      setPreviewEvidenceResult((current) =>
        current
          ? {
              ...current,
              status: result.evidence.status,
            }
          : current,
      );
      await refreshLifecycleAndStorage();
    } catch (caught) {
      setPreviewPromotionError(
        caught instanceof Error
          ? caught.message
          : "Could not promote pending evidence to reviewable Event/Visit.",
      );
    } finally {
      setIsPromotingPreviewEvidence(false);
    }
  }

  function updateTimelineActionState(mediaId: string, patch: TimelineMediaActionState) {
    setTimelineActionState((current) => ({
      ...current,
      [mediaId]: {
        ...(current[mediaId] ?? {}),
        ...patch,
      },
    }));
  }

  function updateStreamMotionCheckState(streamId: string, patch: StreamMotionCheckState) {
    setStreamMotionCheckState((current) => ({
      ...current,
      [streamId]: {
        ...(current[streamId] ?? {}),
        ...patch,
      },
    }));
  }

  function selectedMotionMediaIds(streamId: string, assets: MediaAsset[]): string[] {
    const validIds = new Set(assets.map((asset) => asset.id));
    const savedSelection = streamMotionCheckState[streamId]?.selectedMediaIds;
    return savedSelection
      ? savedSelection.filter((id) => validIds.has(id))
      : defaultMotionSnapshotIds(assets);
  }

  function toggleMotionSnapshot(streamId: string, assets: MediaAsset[], mediaId: string) {
    const currentSelection = selectedMotionMediaIds(streamId, assets);
    const selected = new Set(currentSelection);
    if (selected.has(mediaId)) {
      selected.delete(mediaId);
    } else {
      selected.add(mediaId);
    }
    updateStreamMotionCheckState(streamId, {
      selectedMediaIds: sortOldestFirst(
        assets.filter((asset) => selected.has(asset.id)),
      ).map((asset) => asset.id),
      result: null,
      error: null,
    });
  }

  async function handleEvaluateSavedMediaMotion(
    stream: Stream,
    assets: MediaAsset[],
    zones: Zone[],
    options: { createActivity: boolean },
  ): Promise<MotionEvaluateSavedMediaResponse | null> {
    const selectedIds = selectedMotionMediaIds(stream.id, assets);
    const selectedAssets = sortOldestFirst(
      assets.filter((asset) => selectedIds.includes(asset.id)),
    );
    if (selectedAssets.length < 2) {
      updateStreamMotionCheckState(stream.id, {
        error: "Select at least two saved snapshots before checking motion.",
        lastCheckedAt: new Date().toISOString(),
      });
      return null;
    }

    updateStreamMotionCheckState(stream.id, {
      error: null,
      isChecking: options.createActivity ? false : true,
      isCreatingActivity: options.createActivity,
    });
    try {
      const result = await apiClient.evaluateSavedMediaMotion({
        stream_id: stream.id,
        media_asset_ids: selectedAssets.map((asset) => asset.id),
        zone_ids: zones.length > 0 ? zones.map((zone) => zone.id) : null,
        create_motion_evidence: options.createActivity,
        attach_best_snapshot: true,
        notes: options.createActivity
          ? "User created review activity from a saved snapshot motion check."
          : null,
      });
      updateStreamMotionCheckState(stream.id, {
        result,
        error: null,
        lastCheckedAt: new Date().toISOString(),
      });
      if (options.createActivity) {
        await refreshLifecycleAndStorage();
      }
      return result;
    } catch (caught) {
      updateStreamMotionCheckState(stream.id, {
        error: caught instanceof Error ? caught.message : "Could not check motion.",
        lastCheckedAt: new Date().toISOString(),
      });
      return null;
    } finally {
      updateStreamMotionCheckState(stream.id, {
        isChecking: false,
        isCreatingActivity: false,
      });
    }
  }

  function stopSnapshotWatch(
    reason: SnapshotWatchStopReason,
    status: SnapshotWatchStatus,
    message: string,
    error: string | null = null,
  ) {
    clearSnapshotWatchTimer();
    updateSnapshotWatchState((current) => ({
      ...current,
      isWatching: false,
      status,
      nextCaptureAt: null,
      lastWatchStatus: message,
      lastWatchError: error,
      stopReason: reason,
      isTickRunning: false,
    }));
  }

  function scheduleSnapshotWatchTick(
    context: {
      sourceId: string;
      stream: Stream;
      zones: Zone[];
      intervalSeconds: number;
      maxCaptures: number;
    },
    delayMs: number,
  ) {
    clearSnapshotWatchTimer();
    updateSnapshotWatchState((current) => ({
      ...current,
      nextCaptureAt: new Date(Date.now() + delayMs).toISOString(),
    }));
    snapshotWatchTimerRef.current = setTimeout(() => {
      void runSnapshotWatchTick(context);
    }, delayMs);
  }

  async function runSnapshotWatchTick(context: {
    sourceId: string;
    stream: Stream;
    zones: Zone[];
    intervalSeconds: number;
    maxCaptures: number;
  }) {
    const activeWatch = snapshotWatchStateRef.current;
    if (
      !activeWatch.isWatching ||
      activeWatch.sourceId !== context.sourceId ||
      activeWatch.streamId !== context.stream.id ||
      activeWatch.isTickRunning
    ) {
      return;
    }
    if (activeWatch.capturesAttempted >= context.maxCaptures) {
      stopSnapshotWatch(
        "max_captures_reached",
        "complete",
        "Bounded run complete.",
      );
      return;
    }

    updateSnapshotWatchState((current) => ({
      ...current,
      capturesAttempted: current.capturesAttempted + 1,
      isTickRunning: true,
      lastWatchTickAt: new Date().toISOString(),
      nextCaptureAt: null,
      lastWatchStatus: "Capturing snapshot.",
      lastWatchError: null,
    }));

    try {
      const captureResult = await saveStillImagePreviewForStream(
        context.sourceId,
        context.stream.id,
      );
      if (captureResult.status !== "saved" || !captureResult.media_asset_id) {
        stopSnapshotWatch(
          "source_error",
          "error",
          "Snapshot capture failed.",
          captureResult.message,
        );
        return;
      }

      updateSnapshotWatchState((current) => ({
        ...current,
        capturesSucceeded: current.capturesSucceeded + 1,
        lastWatchStatus: "Captured snapshot.",
      }));

      const { nextMediaAssets, nextRetentionReport } = await refreshMediaAndStorage();
      const streamImages = sortNewestFirst(
        nextMediaAssets.filter(
          (asset) => asset.stream_id === context.stream.id && isImageMedia(asset),
        ),
      );
      const streamRetentionItems =
        nextRetentionReport?.items.filter((item) => item.stream_id === context.stream.id) ?? [];
      const nextStorageSummary = storageGuardrailSummary(
        streamImages,
        streamRetentionItems,
        streamMotionCheckState[context.stream.id] ?? {},
      );
      if (nextStorageSummary.savedImageCount >= SNAPSHOT_WATCH_STORAGE_BLOCK_COUNT) {
        stopSnapshotWatch(
          "storage_warning",
          "stopped",
          "Storage warning reached. Review/export or clean up manually before repeated checks.",
        );
        return;
      }

      let motionResult: MotionEvaluateSavedMediaResponse | null = null;
      if (streamImages.length >= 2) {
        updateSnapshotWatchState((current) => ({
          ...current,
          lastWatchStatus: "Checking motion.",
        }));
        motionResult = await handleEvaluateSavedMediaMotion(
          context.stream,
          streamImages,
          context.zones,
          { createActivity: false },
        );
        updateSnapshotWatchState((current) => ({
          ...current,
          motionChecksRun: motionResult
            ? current.motionChecksRun + 1
            : current.motionChecksRun,
          lastActivityResult: snapshotWatchActivityText(motionResult),
          lastWatchStatus: snapshotWatchActivityText(motionResult),
        }));
      } else {
        updateSnapshotWatchState((current) => ({
          ...current,
          lastActivityResult: "Needs 2 snapshots for motion",
          lastWatchStatus: "Captured snapshot. Needs 2 snapshots for motion.",
        }));
      }

      updateSnapshotWatchState((current) => ({
        ...current,
        isTickRunning: false,
      }));

      const latestWatch = snapshotWatchStateRef.current;
      if (latestWatch.capturesAttempted >= context.maxCaptures) {
        stopSnapshotWatch(
          streamImages.length >= 2 ? "max_captures_reached" : "not_enough_snapshots",
          "complete",
          streamImages.length >= 2
            ? "Bounded run complete."
            : "Bounded run complete; capture another snapshot before motion checks.",
        );
        return;
      }

      scheduleSnapshotWatchTick(context, context.intervalSeconds * 1000);
    } catch (caught) {
      const error = caught instanceof Error ? caught.message : "Snapshot watch failed.";
      stopSnapshotWatch("source_error", "error", "Snapshot watch stopped.", error);
    }
  }

  function handleStartSnapshotWatch(
    stream: Stream,
    zones: Zone[],
    storageSummary: StorageGuardrailSummary,
  ) {
    if (!selectedSourceId || snapshotWatchStateRef.current.isWatching) {
      return;
    }
    if (!isExternalUrlProvider) {
      updateSnapshotWatchState((current) => ({
        ...current,
        status: "error",
        lastWatchError: "Snapshot watch is available for external snapshot sources.",
        lastWatchStatus: "Check source setup.",
      }));
      return;
    }
    if (sourceNeedsSetup(selectedConnection, selectedSetupReview)) {
      updateSnapshotWatchState((current) => ({
        ...current,
        status: "error",
        lastWatchError: "Check source setup before starting Snapshot watch.",
        lastWatchStatus: "Check source setup.",
      }));
      return;
    }
    if (storageSummary.savedImageCount >= SNAPSHOT_WATCH_STORAGE_BLOCK_COUNT) {
      updateSnapshotWatchState((current) => ({
        ...current,
        status: "error",
        lastWatchError: "Review/export or clean up manually before starting repeated checks.",
        lastWatchStatus: "Storage warning.",
        stopReason: "storage_warning",
      }));
      return;
    }

    const intervalSeconds = Math.max(
      MIN_SNAPSHOT_WATCH_INTERVAL_SECONDS,
      snapshotWatchIntervalSeconds,
    );
    const maxCaptures = snapshotWatchMaxCaptures;
    const startedAt = new Date().toISOString();
    updateSnapshotWatchState({
      ...initialSnapshotWatchState(),
      isWatching: true,
      status: "watching",
      sourceId: selectedSourceId,
      streamId: stream.id,
      watchStartedAt: startedAt,
      intervalSeconds,
      maxCaptures,
      lastWatchStatus: "Starting Snapshot watch.",
    });
    scheduleSnapshotWatchTick(
      {
        sourceId: selectedSourceId,
        stream,
        zones,
        intervalSeconds,
        maxCaptures,
      },
      0,
    );
  }

  function handleStopSnapshotWatch() {
    stopSnapshotWatch("user_stopped", "stopped", "Snapshot watch stopped.");
  }

  async function handleStartMonitoring(stream: Stream) {
    setStreamMonitorLoading((current) => ({ ...current, [stream.id]: true }));
    setStreamMonitorErrors((current) => ({ ...current, [stream.id]: "" }));
    try {
      const status = await apiClient.startStreamMonitor(stream.id, {
        interval_seconds: 15,
        max_runtime_minutes: 30,
        max_snapshots: 100,
        check_motion: true,
        create_review_activity: false,
      });
      setStreamMonitorStatuses((current) => ({
        ...current,
        [stream.id]: status,
      }));
      await refreshMediaAndStorage();
    } catch (caught) {
      setStreamMonitorErrors((current) => ({
        ...current,
        [stream.id]: caught instanceof Error ? caught.message : "Could not start monitoring.",
      }));
    } finally {
      setStreamMonitorLoading((current) => ({ ...current, [stream.id]: false }));
    }
  }

  async function handleStopMonitoring(stream: Stream) {
    setStreamMonitorLoading((current) => ({ ...current, [stream.id]: true }));
    setStreamMonitorErrors((current) => ({ ...current, [stream.id]: "" }));
    try {
      const status = await apiClient.stopStreamMonitor(stream.id);
      setStreamMonitorStatuses((current) => ({
        ...current,
        [stream.id]: status,
      }));
      await refreshMediaAndStorage();
    } catch (caught) {
      setStreamMonitorErrors((current) => ({
        ...current,
        [stream.id]: caught instanceof Error ? caught.message : "Could not stop monitoring.",
      }));
    } finally {
      setStreamMonitorLoading((current) => ({ ...current, [stream.id]: false }));
    }
  }

  async function handleRefreshMonitoring(stream: Stream) {
    setStreamMonitorLoading((current) => ({ ...current, [stream.id]: true }));
    await refreshStreamMonitorStatus(stream.id);
    await refreshMediaAndStorage();
    setStreamMonitorLoading((current) => ({ ...current, [stream.id]: false }));
  }

  function timelineSelectedZoneId(asset: MediaAsset): string | null {
    return timelineSelectedZoneByStream[asset.stream_id] || null;
  }

  function buildTimelineProposalPayload(asset: MediaAsset): DemoDetectionRunCreate {
    return {
      media_asset_id: asset.id,
      zone_id: timelineSelectedZoneId(asset),
      label: "bird",
      confidence: 0.72,
      suggested_subject_label: "unknown_bird",
      suggested_species: "unknown_bird",
      notes:
        "Stream media timeline demo detector evidence only. " +
        "No model inspected the media and no reviewed truth was created.",
    };
  }

  async function handleCreateTimelineProposal(asset: MediaAsset) {
    if (!isImageMedia(asset)) {
      updateTimelineActionState(asset.id, {
        proposalError: "Only saved images can be analyzed.",
      });
      return;
    }

    updateTimelineActionState(asset.id, {
      isCreatingProposal: true,
      proposalError: null,
      proposalMessage: null,
      proposalDecisionResult: null,
    });
    try {
      const result = await apiClient.createDemoDetectionRun(buildTimelineProposalPayload(asset));
      updateTimelineActionState(asset.id, {
        proposalResult: result,
        proposalMessage:
          result.proposals.length > 0
            ? "Demo analysis created a suggested label. Review correction still creates reviewed data."
            : "Demo analysis completed without a suggested label.",
      });
      await refreshLifecycleAndStorage();
    } catch (caught) {
      updateTimelineActionState(asset.id, {
        proposalError:
          caught instanceof Error ? caught.message : "Image analysis could not be created.",
      });
    } finally {
      updateTimelineActionState(asset.id, { isCreatingProposal: false });
    }
  }

  async function handleConvertTimelineProposal(asset: MediaAsset) {
    const proposal = timelineActionState[asset.id]?.proposalResult?.proposals[0] ?? null;
    if (!proposal) {
      updateTimelineActionState(asset.id, {
        proposalError: "Analyze the image before sending a suggestion to Review.",
      });
      return;
    }

    updateTimelineActionState(asset.id, {
      isConvertingProposal: true,
      proposalError: null,
      proposalMessage: null,
    });
    try {
      const result = await apiClient.decideDetectionProposal(proposal.id, {
        decision: "convert_to_event",
        event_title: "Stream media timeline proposal review",
        subject_label: "unknown_bird",
        species_guess: "unknown_bird",
        notes: "Converted from explicit Stream media timeline proposal action; still needs review/correction.",
      });
      updateTimelineActionState(asset.id, {
        proposalDecisionResult: result,
        proposalMessage:
          "Sent suggestion to Review. No reviewed data was created.",
      });
      await refreshLifecycleAndStorage();
    } catch (caught) {
      updateTimelineActionState(asset.id, {
        proposalError:
          caught instanceof Error ? caught.message : "Suggestion could not be sent to Review.",
      });
    } finally {
      updateTimelineActionState(asset.id, { isConvertingProposal: false });
    }
  }

  async function handleRunLocalDetector(asset: MediaAsset) {
    if (!localDetectorAdapter) {
      updateTimelineActionState(asset.id, {
        localDetectorError:
          "Local detector readiness is unavailable. Use demo proposal for smoke testing.",
      });
      return;
    }
    if (!canRunModelAdapter(localDetectorAdapter)) {
      updateTimelineActionState(asset.id, {
        localDetectorError: localDetectorReadinessCopy(localDetectorAdapter),
      });
      return;
    }
    if (!modelAdapterSupportsMedia(localDetectorAdapter, asset)) {
      updateTimelineActionState(asset.id, {
        localDetectorError: "Local detector supports saved image media only.",
      });
      return;
    }

    updateTimelineActionState(asset.id, {
      isRunningLocalDetector: true,
      localDetectorError: null,
      localDetectorResult: null,
    });
    try {
      const selectedZoneId = timelineSelectedZoneId(asset);
      const result = await apiClient.runModelAdapter(LOCAL_IMAGE_DETECTOR_ADAPTER_ID, {
        adapter_id: LOCAL_IMAGE_DETECTOR_ADAPTER_ID,
        media_asset_id: asset.id,
        zone_ids: selectedZoneId ? [selectedZoneId] : null,
        notes:
          "Explicit local detector run from Stream saved image timeline. " +
          "Outputs are proposal evidence only; no reviewed truth was created.",
      });
      updateTimelineActionState(asset.id, { localDetectorResult: result });
      await refreshLifecycleAndStorage();
    } catch (caught) {
      updateTimelineActionState(asset.id, {
        localDetectorError:
          caught instanceof Error ? caught.message : "Local detector run failed.",
      });
    } finally {
      updateTimelineActionState(asset.id, { isRunningLocalDetector: false });
    }
  }

  async function handleCreateTimelineEvidence(asset: MediaAsset) {
    const zoneId = timelineSelectedZoneId(asset);
    if (!isImageMedia(asset)) {
      updateTimelineActionState(asset.id, {
        evidenceError: "Only saved images can create review context.",
      });
      return;
    }
    if (!zoneId) {
      updateTimelineActionState(asset.id, {
        evidenceError: "Add an active non-privacy/non-ignore Zone before creating review context.",
      });
      return;
    }

    updateTimelineActionState(asset.id, {
      isCreatingEvidence: true,
      evidenceError: null,
      promotionError: null,
      promotionResult: null,
    });
    try {
      const result = await apiClient.createMotionEvidenceFromMedia(asset.id, {
        stream_id: asset.stream_id,
        zone_id: zoneId,
        note: "Stream media timeline evidence handoff.",
        reason: "User requested pending evidence from saved Stream media.",
        duplicate_policy: "skip_existing",
      });
      updateTimelineActionState(asset.id, { evidenceResult: result });
      await refreshLifecycleAndStorage();
    } catch (caught) {
      updateTimelineActionState(asset.id, {
        evidenceError:
          caught instanceof Error ? caught.message : "Review context could not be created.",
      });
    } finally {
      updateTimelineActionState(asset.id, { isCreatingEvidence: false });
    }
  }

  async function handlePromoteTimelineEvidence(asset: MediaAsset, evidenceIdOverride?: string) {
    const currentEvidence = timelineActionState[asset.id]?.evidenceResult ?? null;
    const evidenceId = evidenceIdOverride ?? currentEvidence?.motion_evidence_id;
    if (!evidenceId) {
      return;
    }

    updateTimelineActionState(asset.id, {
      isPromotingEvidence: true,
      promotionError: null,
      promotionResult: null,
    });
    try {
      const result = await apiClient.promoteMotionEvidence(evidenceId, {
        event_title: "Stream media timeline review",
        visit_label_hint: "unknown_animal",
        notes: "Promoted by explicit Stream media timeline action.",
        create_event: true,
        create_visit: true,
        attach_snapshot_media_asset_id: asset.id,
      });
      updateTimelineActionState(asset.id, {
        promotionResult: result,
        evidenceResult: currentEvidence
          ? {
              ...currentEvidence,
              status: result.evidence.status,
            }
          : currentEvidence,
      });
      await refreshLifecycleAndStorage();
    } catch (caught) {
      updateTimelineActionState(asset.id, {
        promotionError:
          caught instanceof Error ? caught.message : "Review item could not be created.",
      });
    } finally {
      updateTimelineActionState(asset.id, { isPromotingEvidence: false });
    }
  }

  function buildFolderPreviewRequest(): FolderImportPreviewRequest {
    return {
      recursive: folderRecursive,
      allowed_extensions: parseAllowedExtensions(folderAllowedExtensions),
      max_files: parseIntegerAtLeast(folderMaxFiles, "Max files", 1),
      max_depth: parseIntegerAtLeast(folderMaxDepth, "Max depth", 0),
    };
  }

  async function handlePreviewFolderImport() {
    if (!selectedSourceId) {
      return;
    }

    let requestPayload: FolderImportPreviewRequest;
    try {
      requestPayload = buildFolderPreviewRequest();
    } catch (caught) {
      setFolderPreviewError(
        caught instanceof Error ? caught.message : "Folder import preview settings are invalid.",
      );
      return;
    }

    setIsPreviewingFolderImport(true);
    setFolderPreviewError(null);
    setFolderImportError(null);
    setFolderPreviewResult(null);
    setFolderImportResult(null);
    setFolderEvidenceDryRunResult(null);
    setFolderEvidenceDryRunRequest(null);
    setFolderEvidenceBatchCreateResult(null);
    setFolderEvidenceDryRunError(null);
    setFolderEvidenceBatchCreateError(null);
    setFolderEvidenceBatchConfirmed(false);
    setFolderEvidenceResults({});
    setFolderEvidenceErrors({});
    setFolderEvidenceLoadingId(null);
    try {
      const result = await apiClient.previewFolderImport(selectedSourceId, requestPayload);
      setFolderPreviewResult(result);
    } catch (caught) {
      setFolderPreviewError(
        caught instanceof Error ? caught.message : "Could not preview folder import.",
      );
    } finally {
      setIsPreviewingFolderImport(false);
    }
  }

  async function handleImportPreviewedFolderFiles() {
    if (!selectedSourceId || !folderPreviewResult) {
      return;
    }
    if (folderPreviewResult.candidates.length === 0) {
      setFolderImportError("Preview has no supported files to import as MediaAssets.");
      return;
    }
    if (!selectedFirstStream) {
      setFolderImportError("Add Stream context before importing previewed files as MediaAssets.");
      return;
    }

    let previewOptions: FolderImportPreviewRequest;
    try {
      previewOptions = buildFolderPreviewRequest();
    } catch (caught) {
      setFolderImportError(
        caught instanceof Error ? caught.message : "Folder import settings are invalid.",
      );
      return;
    }

    const importPayload: FolderImportRequest = {
      ...previewOptions,
      relative_paths: folderPreviewResult.candidates.map((candidate) => candidate.relative_path),
      default_stream_id: selectedFirstStream.id,
      note: folderImportNote.trim() || null,
      copy_mode: "copy_to_media_root",
    };

    setIsImportingFolderMedia(true);
    setFolderImportError(null);
    setFolderImportResult(null);
    setFolderEvidenceDryRunResult(null);
    setFolderEvidenceDryRunRequest(null);
    setFolderEvidenceBatchCreateResult(null);
    setFolderEvidenceDryRunError(null);
    setFolderEvidenceBatchCreateError(null);
    setFolderEvidenceBatchConfirmed(false);
    setFolderEvidenceResults({});
    setFolderEvidenceErrors({});
    setFolderEvidenceLoadingId(null);
    try {
      const result = await apiClient.importFolderMedia(selectedSourceId, importPayload);
      setFolderImportResult(result);
      await loadMediaAssets({ showLoading: false });
    } catch (caught) {
      setFolderImportError(
        caught instanceof Error ? caught.message : "Could not import previewed folder files.",
      );
    } finally {
      setIsImportingFolderMedia(false);
    }
  }

  async function handleDryRunFolderEvidenceHandoff() {
    if (!folderImportResult || folderImportResult.imported.length === 0) {
      setFolderEvidenceDryRunError("Import folder media before dry-running evidence handoff.");
      return;
    }

    setIsDryRunningFolderEvidence(true);
    setFolderEvidenceDryRunError(null);
    setFolderEvidenceDryRunResult(null);
    setFolderEvidenceBatchCreateResult(null);
    setFolderEvidenceBatchCreateError(null);
    setFolderEvidenceBatchConfirmed(false);
    try {
      const requestPayload: FolderImportEvidenceBatchDryRunRequest = {
        media_asset_ids: folderImportResult.imported.map((item) => item.media_asset_id),
        duplicate_policy: "skip_existing",
        max_items: folderImportResult.imported.length,
      };
      const result = await apiClient.dryRunFolderImportEvidence(requestPayload);
      setFolderEvidenceDryRunRequest(requestPayload);
      setFolderEvidenceDryRunResult(result);
    } catch (caught) {
      setFolderEvidenceDryRunRequest(null);
      setFolderEvidenceDryRunError(
        caught instanceof Error ? caught.message : "Could not dry-run evidence handoff.",
      );
    } finally {
      setIsDryRunningFolderEvidence(false);
    }
  }

  async function handleCreateFolderEvidenceBatch() {
    if (!folderEvidenceDryRunResult || !folderEvidenceDryRunRequest) {
      setFolderEvidenceBatchCreateError("Dry-run eligible media before batch creation.");
      return;
    }
    if (!folderEvidenceBatchConfirmed) {
      setFolderEvidenceBatchCreateError("Confirm this batch before creating pending evidence.");
      return;
    }

    const eligibleMediaIds = folderEvidenceDryRunResult.items
      .filter((item) => item.would_create_motion_evidence)
      .map((item) => item.media_asset_id);
    if (eligibleMediaIds.length === 0) {
      setFolderEvidenceBatchCreateError("No eligible MediaAssets are available to create.");
      return;
    }

    setIsCreatingFolderEvidenceBatch(true);
    setFolderEvidenceBatchCreateError(null);
    setFolderEvidenceBatchCreateResult(null);
    try {
      const result = await apiClient.createFolderImportEvidenceBatch({
        ...folderEvidenceDryRunRequest,
        media_asset_ids: eligibleMediaIds,
        max_items: eligibleMediaIds.length,
        confirm: true,
        note: "Folder import batch evidence handoff.",
        reason: "User confirmed eligible folder-imported media from batch dry-run.",
      });
      setFolderEvidenceBatchCreateResult(result);
      setFolderEvidenceBatchConfirmed(false);
      await refreshLifecycleAndStorage();
    } catch (caught) {
      setFolderEvidenceBatchCreateError(
        caught instanceof Error ? caught.message : "Could not create pending evidence batch.",
      );
    } finally {
      setIsCreatingFolderEvidenceBatch(false);
    }
  }

  async function handleCreateMotionEvidenceFromFolderImport(
    item: FolderImportCreatedMediaAsset,
  ) {
    setFolderEvidenceLoadingId(item.media_asset_id);
    setFolderEvidenceDryRunResult(null);
    setFolderEvidenceDryRunRequest(null);
    setFolderEvidenceBatchCreateResult(null);
    setFolderEvidenceDryRunError(null);
    setFolderEvidenceBatchCreateError(null);
    setFolderEvidenceBatchConfirmed(false);
    setFolderEvidenceErrors((current) => {
      const next = { ...current };
      delete next[item.media_asset_id];
      return next;
    });
    try {
      const result = await apiClient.createMotionEvidenceFromMedia(item.media_asset_id, {
        stream_id: item.stream_id ?? selectedFirstStream?.id ?? null,
        note: "Folder import evidence handoff.",
        reason: "User requested pending evidence from folder-imported media.",
        duplicate_policy: "skip_existing",
      });
      setFolderEvidenceResults((current) => ({
        ...current,
        [item.media_asset_id]: result,
      }));
      await refreshLifecycleAndStorage();
    } catch (caught) {
      setFolderEvidenceErrors((current) => ({
        ...current,
        [item.media_asset_id]:
          caught instanceof Error ? caught.message : "Could not create pending evidence.",
      }));
    } finally {
      setFolderEvidenceLoadingId(null);
    }
  }

  const selectedProviderLabel =
    selectedSetupReview?.provider_display_name ??
    selectedProviderDefinition?.display_name ??
    selectedConfiguration?.provider_key ??
    "Loading";
  const selectedLivePlaybackLabel = selectedSetupReview
    ? selectedSetupReview.supports_live_playback
      ? "Available"
      : "Not available"
    : "Loading";
  const selectedZoneEditingLabel = selectedSetupReview
    ? selectedSetupReview.supports_zone_editing
      ? "Available"
      : "Unavailable"
    : "Loading";
  const selectedReadinessLabel = selectedSetupReview
    ? formatLabel(selectedSetupReview.readiness_level)
    : "Loading";
  const isManualMediaReady =
    selectedSetupReview?.provider_key === "manual_media" &&
    selectedSetupReview.readiness_level === "metadata_ready";
  const isExternalUrlProvider = selectedConfiguration?.provider_key === "external_url";
  const isFolderImportProvider =
    selectedSetupReview?.provider_key === "folder_import_future" ||
    selectedConfiguration?.provider_key === "folder_import_future";
  const isWebhookProvider =
    selectedSetupReview?.provider_key === "webhook_future" ||
    selectedConfiguration?.provider_key === "webhook_future";
  const selectedFirstStream = selectedSourceStreams[0] ?? null;

  useEffect(() => {
    let isMounted = true;

    if (selectedSourceStreams.length === 0) {
      setTimelineZonesByStream({});
      setTimelineSelectedZoneByStream({});
      setTimelineZoneErrors({});
      return () => {
        isMounted = false;
      };
    }

    async function loadTimelineZones() {
      const zoneEntries: Array<readonly [string, Zone[]]> = [];
      const errorEntries: Array<readonly [string, string]> = [];

      await Promise.all(
        selectedSourceStreams.map(async (stream) => {
          try {
            const zones = await apiClient.getStreamZones(stream.id);
            zoneEntries.push([stream.id, zones] as const);
          } catch (caught) {
            errorEntries.push([
              stream.id,
              caught instanceof Error ? caught.message : "Could not load Stream Zones.",
            ] as const);
          }
        }),
      );

      if (!isMounted) {
        return;
      }

      const nextZonesByStream = Object.fromEntries(zoneEntries);
      setTimelineZonesByStream(nextZonesByStream);
      setTimelineZoneErrors(Object.fromEntries(errorEntries));
      setTimelineSelectedZoneByStream((current) => {
        const next: Record<string, string> = {};
        for (const stream of selectedSourceStreams) {
          const reviewableZones = (nextZonesByStream[stream.id] ?? []).filter(isReviewableZone);
          const currentZoneId = current[stream.id];
          next[stream.id] =
            currentZoneId && reviewableZones.some((zone) => zone.id === currentZoneId)
              ? currentZoneId
              : reviewableZones[0]?.id ?? "";
        }
        return next;
      });
    }

    void loadTimelineZones();

    return () => {
      isMounted = false;
    };
  }, [selectedSourceStreamIds]);

  useEffect(() => {
    let isMounted = true;

    setPreviewZones([]);
    setSelectedPreviewZoneId("");
    setPreviewZonesError(null);
    if (!isExternalUrlProvider || !selectedFirstStream) {
      return () => {
        isMounted = false;
      };
    }

    async function loadPreviewZones() {
      try {
        const zones = await apiClient.getStreamZones(selectedFirstStream.id);
        if (!isMounted) {
          return;
        }
        setPreviewZones(zones);
        setSelectedPreviewZoneId(zones.find(isReviewableZone)?.id ?? "");
      } catch (caught) {
        if (isMounted) {
          setPreviewZonesError(
            caught instanceof Error ? caught.message : "Could not load Stream Zones.",
          );
        }
      }
    }

    void loadPreviewZones();

    return () => {
      isMounted = false;
    };
  }, [isExternalUrlProvider, selectedFirstStream]);

  const reviewablePreviewZones = previewZones.filter(isReviewableZone);
  const blockedPreviewZoneCount = previewZones.filter(
    (zone) => zone.is_active && !isReviewableZone(zone),
  ).length;
  const canSavePreview =
    previewResult?.status === "available" && Boolean(previewResult.preview_data_url);
  const canCreatePreviewEvidence =
    Boolean(previewSaveResult?.media_asset_id) &&
    Boolean(selectedFirstStream) &&
    Boolean(selectedPreviewZoneId);
  const canPromotePreviewEvidence = previewEvidenceResult?.status === "pending";
  const mediaAssetsByStream = new Map<string, MediaAsset[]>();
  for (const asset of mediaAssets) {
    const streamAssets = mediaAssetsByStream.get(asset.stream_id) ?? [];
    streamAssets.push(asset);
    mediaAssetsByStream.set(asset.stream_id, streamAssets);
  }
  for (const streamAssets of mediaAssetsByStream.values()) {
    streamAssets.sort(
      (left, right) =>
        new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
    );
  }
  const folderEvidenceDryRunEligibleCount =
    folderEvidenceDryRunResult?.items.filter((item) => item.would_create_motion_evidence).length ??
    0;
  const nextActionTitle = selectedSetupReview
    ? selectedSetupReview.readiness_level === "demo_ready"
      ? "Next: open Stream Detail and draw Zones."
      : isManualMediaReady
        ? "Next: import media for this Source/Stream."
        : isFolderImportProvider && selectedSetupReview.readiness_level === "needs_setup"
          ? "Next: complete folder path metadata."
        : isFolderImportProvider &&
            selectedSetupReview.readiness_level === "future_adapter_required"
          ? "Next: preview folder import explicitly."
        : isWebhookProvider && selectedSetupReview.readiness_level === "needs_setup"
          ? "Next: complete webhook shared secret metadata."
        : isWebhookProvider &&
            selectedSetupReview.readiness_level === "future_adapter_required"
          ? "Next: future webhook ingest implementation required."
        : isExternalUrlProvider && selectedSetupReview.readiness_level === "metadata_ready"
          ? "Next: test a snapshot explicitly."
          : selectedSetupReview.readiness_level === "needs_setup"
          ? "Next: complete setup metadata."
          : selectedSetupReview.readiness_level === "future_adapter_required"
            ? "Next: review explicit provider workflow before live playback."
            : "Next: review Source setup status."
    : "Next: load Source setup status.";
  const nextActionDetail =
    isWebhookProvider && selectedSetupReview?.readiness_level === "future_adapter_required"
      ? "Webhook UI ingest is future work."
      : isFolderImportProvider && selectedSetupReview?.readiness_level === "future_adapter_required"
      ? "Preview first, then import as MediaAssets."
      : isExternalUrlProvider && selectedSetupReview?.readiness_level === "metadata_ready"
      ? "Test snapshot, then capture one saved image under this camera/source."
      : selectedSetupReview?.next_step ?? selectedConnection?.setup_hint;

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Stream-first workspace"
        title="Streams"
        description="Connect Sources, inspect Streams, configure setup metadata, then draw Zones and review activity."
      />
      <section className="notice-panel onboarding-provider-note">
        <strong>Provider setup is metadata first</strong>
        <span>
          Use explicit snapshot, import, or review actions below. Live playback is future work.
        </span>
      </section>
      {connectionError ? <div className="error-panel">{connectionError}</div> : null}
      {selectedSource ? (
        <section className="panel source-setup-panel source-workflow-panel">
          <div className="section-heading">
            <div>
              <h2>Source workflow</h2>
              <span className="meta-text">
                Setup metadata, playback status, Streams, Zones, and review stay in one flow
              </span>
            </div>
            {selectedSetupReview ? (
              <StatusPill
                label={selectedReadinessLabel}
                tone={readinessTone(selectedSetupReview.readiness_level)}
              />
            ) : selectedConnection ? (
              <StatusPill
                label={formatLabel(selectedConnection.status)}
                tone={connectionTone(selectedConnection.status)}
              />
            ) : null}
          </div>
          <div className="source-selector-row">
            <label>
              Source
              <select
                value={selectedSource.id}
                onChange={(event) => {
                  setSelectedSourceId(event.target.value);
                  setSetupError(null);
                  setSetupMessage(null);
                }}
              >
                {sources.map((source) => (
                  <option key={source.id} value={source.id}>
                    {source.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="source-summary-line">
              <strong>{selectedProviderLabel}</strong>
              <span>{selectedSetupReview?.summary ?? selectedSource.description}</span>
            </div>
          </div>
          <div className="source-overview-grid">
            <div>
              <span>Readiness</span>
              <strong>{selectedReadinessLabel}</strong>
            </div>
            <div>
              <span>Provider</span>
              <strong>{selectedProviderLabel}</strong>
            </div>
            <div>
              <span>Live playback</span>
              <strong>{selectedLivePlaybackLabel}</strong>
            </div>
            <div>
              <span>Zone editing</span>
              <strong>{selectedZoneEditingLabel}</strong>
            </div>
          </div>
          <div className="source-next-action">
            <div>
              <strong>{nextActionTitle}</strong>
              {nextActionDetail ? <span>{nextActionDetail}</span> : null}
            </div>
            <div className="source-next-action-buttons">
              {isManualMediaReady ? (
                <button className="primary-action" onClick={onOpenImport} type="button">
                  Import media
                </button>
              ) : selectedSetupReview?.readiness_level === "demo_ready" && selectedFirstStream ? (
                <button
                  className="primary-action"
                  onClick={() => onOpenStream(selectedFirstStream.id)}
                  type="button"
                >
                  Open Stream Detail
                </button>
              ) : null}
              {selectedFirstStream && selectedSetupReview?.readiness_level !== "demo_ready" ? (
                <button
                  className="secondary-action"
                  onClick={() => onOpenStream(selectedFirstStream.id)}
                  type="button"
                >
                  Open related Stream
                </button>
              ) : null}
            </div>
          </div>
          <div className="source-setup-layout">
            <div className="source-setup-summary">
              {selectedSetupReview ? (
                <div className="source-review-panel">
                  <div className="item-title-row">
                    <h3>Setup status</h3>
                    <StatusPill
                      label={formatLabel(selectedSetupReview.readiness_level)}
                      tone={readinessTone(selectedSetupReview.readiness_level)}
                    />
                  </div>
                  <div className="source-field-summary">
                    <div>
                      <strong>Configured</strong>
                      <div className="source-field-tags">
                        {selectedSetupReview.configured_fields.length > 0 ? (
                          selectedSetupReview.configured_fields.map((field) => (
                            <span key={field}>{formatLabel(field)}</span>
                          ))
                        ) : (
                          <span>None</span>
                        )}
                      </div>
                    </div>
                    <div>
                      <strong>Missing</strong>
                      <div className="source-field-tags">
                        {selectedSetupReview.missing_fields.length > 0 ? (
                          selectedSetupReview.missing_fields.map((field) => (
                            <span key={field}>{formatLabel(field)}</span>
                          ))
                        ) : (
                          <span>None</span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="source-review-step-list">
                    {selectedSetupReview.steps.map((step) => (
                      <div className="source-review-step" key={step.key}>
                        <div className="item-title-row">
                          <strong>{step.label}</strong>
                          <StatusPill
                            label={formatLabel(step.status)}
                            tone={stepTone(step.status)}
                          />
                        </div>
                        <p>{step.message}</p>
                      </div>
                    ))}
                  </div>
                  {selectedSetupReview.warnings.length > 0 ? (
                    <div className="source-warning-list">
                      {selectedSetupReview.warnings.map((warning) => (
                        <span key={warning}>{warning}</span>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
              {isExternalUrlProvider ? (
                <div className="external-preview-panel">
                  <div className="item-title-row">
                    <h3>Snapshot camera</h3>
                    <StatusPill
                      label={previewResult ? formatLabel(previewResult.status) : "Explicit"}
                      tone={previewResult?.status === "available" ? "good" : "quiet"}
                    />
                  </div>
                  <p>
                    Test the Snapshot URL, capture one saved image, then analyze it when you are
                    ready to review.
                  </p>
                  <div className="source-connection-meta">
                    <span>Snapshot URL</span>
                    <span>Not live video</span>
                    <span>Test creates no records</span>
                    <span>Capture saves one image</span>
                    <span>Correction creates reviewed data</span>
                  </div>
                  <button
                    className="secondary-action"
                    disabled={isFetchingPreview}
                    onClick={handleFetchStillImagePreview}
                    type="button"
                  >
                    {isFetchingPreview ? "Testing snapshot..." : "Test snapshot"}
                  </button>
                  {previewError ? <div className="zone-error">{previewError}</div> : null}
                  {previewResult ? (
                    <div className="external-preview-result">
                      <strong>Snapshot test: {previewResult.message}</strong>
                      {previewResult.warnings.length > 0 ? (
                        <div className="source-warning-list">
                          {previewResult.warnings.map((warning) => (
                            <span key={warning}>{warning}</span>
                          ))}
                        </div>
                      ) : null}
                      {previewResult.preview_data_url ? (
                        <div className="external-preview-image-frame">
                          <img
                            alt="External URL still-image preview"
                            src={previewResult.preview_data_url}
                          />
                        </div>
                      ) : null}
                      <div className="source-connection-meta">
                        {previewResult.fetched_at ? (
                          <span>Tested: {formatDateTime(previewResult.fetched_at)}</span>
                        ) : null}
                        {previewResult.content_type ? (
                          <span>Content: {previewResult.content_type}</span>
                        ) : null}
                        {previewResult.bytes_read !== null &&
                        previewResult.bytes_read !== undefined ? (
                          <span>Size read: {formatBytes(previewResult.bytes_read)}</span>
                        ) : null}
                        <span>Not saved</span>
                        <span>No Events/Visits created</span>
                      </div>
                      {canSavePreview ? (
                        <div className="external-preview-save-actions">
                          <button
                            className="primary-action"
                            disabled={isSavingPreview}
                            onClick={handleSaveStillImagePreview}
                            type="button"
                          >
                            {isSavingPreview
                              ? "Capturing snapshot..."
                              : "Capture snapshot"}
                          </button>
                          <span className="meta-text">
                            Capture saves one local image only. It will not analyze, review, or
                            export automatically.
                          </span>
                        </div>
                      ) : null}
                      {previewSaveError ? <div className="zone-error">{previewSaveError}</div> : null}
                      {previewSaveResult ? (
                        <div className="external-preview-save-status">
                          <strong>Captured snapshot: {previewSaveResult.message}</strong>
                          <div className="source-connection-meta">
                            {previewSaveResult.fetched_at ? (
                              <span>Captured: {formatDateTime(previewSaveResult.fetched_at)}</span>
                            ) : null}
                            {previewSaveResult.content_type ? (
                              <span>Content: {previewSaveResult.content_type}</span>
                            ) : null}
                            {previewSaveResult.file_name ? (
                              <span>Saved image: {previewSaveResult.file_name}</span>
                            ) : null}
                            <span>Size: {formatBytes(previewSaveResult.bytes_written)}</span>
                            <span>Source: {selectedSource?.name ?? previewSaveResult.source_id}</span>
                            <span>
                              Stream:{" "}
                              {selectedFirstStream?.name ??
                                previewSaveResult.stream_id ??
                                "none"}
                            </span>
                          </div>
                          <span className="meta-text">
                            Next: analyze the saved image below. No review truth or export was
                            created.
                          </span>
                          {previewSaveResult.media_asset_id ? (
                            <a
                              className="inline-link"
                              href={apiClient.mediaFileUrl(previewSaveResult.media_asset_id)}
                              rel="noreferrer"
                              target="_blank"
                            >
                              Open saved image
                            </a>
                          ) : null}
                          <details className="advanced-details">
                            <summary>Advanced details</summary>
                            <div className="source-connection-meta">
                              {previewSaveResult.media_asset_id ? (
                                <span>MediaAsset: {previewSaveResult.media_asset_id}</span>
                              ) : null}
                              {previewSaveResult.relative_path ? (
                                <span>Path: {previewSaveResult.relative_path}</span>
                              ) : null}
                              <span>
                                Creates Event: {previewSaveResult.creates_event ? "Yes" : "No"}
                              </span>
                              <span>
                                Creates Visit: {previewSaveResult.creates_visit ? "Yes" : "No"}
                              </span>
                              <span>
                                Creates truth: {previewSaveResult.creates_truth ? "Yes" : "No"}
                              </span>
                            </div>
                          </details>
                          {previewSaveResult.media_asset_id ? (
                            <div className="external-preview-proposal-status">
                              <div className="section-heading">
                                <div>
                                  <span className="meta-text">Saved image</span>
                                  <h3>Analyze captured image</h3>
                                </div>
                                <StatusPill label="Demo suggestion" tone="quiet" />
                              </div>
                              <p>
                                Create a demo suggestion for review from this saved snapshot. No
                                model inspects the image and no reviewed data is created.
                              </p>
                              <div className="import-flow-strip">
                                <span>Saved image</span>
                                <span>Suggested label</span>
                                <span>Review correction</span>
                              </div>
                              {snapshotProposalMessage ? (
                                <div className="notice-panel compact-notice">
                                  {snapshotProposalMessage}
                                </div>
                              ) : null}
                              {snapshotProposalError ? (
                                <div className="zone-error">{snapshotProposalError}</div>
                              ) : null}
                              <div className="detail-actions">
                                <button
                                  className="primary-action"
                                  disabled={
                                    isCreatingSnapshotProposal ||
                                    isConvertingSnapshotProposal
                                  }
                                  onClick={handleCreateSnapshotProposal}
                                  type="button"
                                >
                                  {isCreatingSnapshotProposal
                                    ? "Creating..."
                                    : "Analyze image"}
                                </button>
                                {snapshotProposalResult?.proposals[0] &&
                                !snapshotProposalDecisionResult ? (
                                  <button
                                    className="secondary-action"
                                    disabled={isConvertingSnapshotProposal}
                                    onClick={handleConvertSnapshotProposal}
                                    type="button"
                                  >
                                    {isConvertingSnapshotProposal
                                      ? "Converting..."
                                      : "Send suggestion to Review"}
                                  </button>
                                ) : null}
                                <button
                                  className="secondary-action"
                                  onClick={onOpenDetectionProposals}
                                  type="button"
                                >
                                  Review suggestions
                                </button>
                                <button
                                  className="secondary-action"
                                  onClick={onOpenReview}
                                  type="button"
                                >
                                  Review
                                </button>
                              </div>
                              {snapshotProposalResult ? (
                                <div className="timeline-result-grid">
                                  <div className="data-row">
                                    <span>Suggested labels</span>
                                    <strong>
                                      {snapshotProposalResult.proposals.length > 0
                                        ? snapshotProposalResult.proposals
                                            .map((proposal) => proposal.label)
                                            .join(", ")
                                        : "none"}
                                    </strong>
                                  </div>
                                  <div className="data-row">
                                    <span>Review status</span>
                                    <strong>
                                      {snapshotProposalResult.review_queue_count} items need review
                                    </strong>
                                  </div>
                                  <div className="data-row">
                                    <span>Reviewed data created</span>
                                    <strong>No</strong>
                                  </div>
                                </div>
                              ) : null}
                              {snapshotProposalResult ? (
                                <details className="advanced-details">
                                  <summary>Advanced analysis details</summary>
                                  <div className="import-smoke-result-grid">
                                    <div className="data-row">
                                      <span>DetectionRun ID</span>
                                      <strong>{snapshotProposalResult.detection_run.id}</strong>
                                    </div>
                                    <div className="data-row">
                                      <span>Proposal IDs</span>
                                      <strong>
                                        {snapshotProposalResult.proposals.length > 0
                                          ? snapshotProposalResult.proposals
                                              .map((proposal) => proposal.id)
                                              .join(", ")
                                          : "none"}
                                      </strong>
                                    </div>
                                    <div className="data-row">
                                      <span>Review Queue</span>
                                      <strong>
                                        {snapshotProposalResult.review_queue_count} needs review
                                      </strong>
                                    </div>
                                    {snapshotProposalResult.proposals.map((proposal) => (
                                      <div className="data-row" key={proposal.id}>
                                        <span>{proposal.id}</span>
                                        <strong>
                                          {proposal.label} / {Math.round(proposal.confidence * 100)}
                                          % / {formatLabel(proposal.status)}
                                        </strong>
                                      </div>
                                    ))}
                                  </div>
                                </details>
                              ) : null}
                              {snapshotProposalDecisionResult ? (
                                <div className="timeline-result-grid">
                                  <div className="data-row">
                                    <span>Review item</span>
                                    <strong>
                                      {snapshotProposalDecisionResult.visit
                                        ? "Visit ready for correction"
                                        : snapshotProposalDecisionResult.event
                                          ? "Event ready for correction"
                                          : "Not created"}
                                    </strong>
                                  </div>
                                  <div className="data-row">
                                    <span>Next</span>
                                    <strong>Review item</strong>
                                  </div>
                                  <div className="data-row">
                                    <span>Reviewed data created</span>
                                    <strong>No</strong>
                                  </div>
                                  <button
                                    className="primary-action"
                                    onClick={onOpenReview}
                                    type="button"
                                  >
                                    Review item
                                  </button>
                                </div>
                              ) : null}
                              {snapshotProposalDecisionResult ? (
                                <details className="advanced-details">
                                  <summary>Advanced review item details</summary>
                                  <div className="import-smoke-result-grid">
                                    <div className="data-row">
                                      <span>Converted proposal</span>
                                      <strong>
                                        {snapshotProposalDecisionResult.proposal.id}
                                      </strong>
                                    </div>
                                    <div className="data-row">
                                      <span>Event</span>
                                      {snapshotProposalDecisionResult.event ? (
                                        <button
                                          className="inline-link-button"
                                          onClick={() =>
                                            onOpenEvent(
                                              snapshotProposalDecisionResult.event!.id,
                                            )
                                          }
                                          type="button"
                                        >
                                          {snapshotProposalDecisionResult.event.id}
                                        </button>
                                      ) : (
                                        <strong>not created</strong>
                                      )}
                                    </div>
                                    <div className="data-row">
                                      <span>Visit</span>
                                      {snapshotProposalDecisionResult.visit ? (
                                        <button
                                          className="inline-link-button"
                                          onClick={() =>
                                            onOpenVisit(
                                              snapshotProposalDecisionResult.visit!.id,
                                            )
                                          }
                                          type="button"
                                        >
                                          {snapshotProposalDecisionResult.visit.id}
                                        </button>
                                      ) : (
                                        <strong>not created</strong>
                                      )}
                                    </div>
                                  </div>
                                </details>
                              ) : null}
                              <div className="notice-panel compact-notice import-smoke-boundary">
                                <strong>Truth boundary</strong>
                                <ul>
                                  <li>Demo analysis creates a suggested label only.</li>
                                  <li>No model inspected the snapshot.</li>
                                  <li>No reviewed data was created.</li>
                                  <li>Correction remains explicit in Review.</li>
                                </ul>
                              </div>
                            </div>
                          ) : null}
                          {previewSaveResult.media_asset_id ? (
                            <details className="advanced-details">
                              <summary>Advanced review context actions</summary>
                              <div className="external-preview-evidence-actions">
                              <div className="section-heading">
                                <div>
                                  <span className="meta-text">Evidence workflow</span>
                                  <h3>Create pending review context</h3>
                                </div>
                                <StatusPill label="Pending evidence" tone="quiet" />
                              </div>
                              <p className="meta-text">
                                This keeps the saved snapshot attached to pending internal
                                evidence, with optional explicit Event/Visit review context.
                              </p>
                              <label className="external-preview-zone-select">
                                Review zone
                                <select
                                  disabled={reviewablePreviewZones.length === 0}
                                  onChange={(event) =>
                                    setSelectedPreviewZoneId(event.target.value)
                                  }
                                  value={selectedPreviewZoneId}
                                >
                                  {reviewablePreviewZones.length > 0 ? (
                                    reviewablePreviewZones.map((zone) => (
                                      <option key={zone.id} value={zone.id}>
                                        {zone.name} ({formatLabel(zone.zone_type)})
                                      </option>
                                    ))
                                  ) : (
                                    <option value="">No reviewable Zones</option>
                                  )}
                                </select>
                              </label>
                              {previewZonesError ? (
                                <div className="zone-error">{previewZonesError}</div>
                              ) : null}
                              {!selectedFirstStream ? (
                                <div className="zone-error">
                                  Add Stream context before creating evidence.
                                </div>
                              ) : null}
                              {selectedFirstStream && reviewablePreviewZones.length === 0 ? (
                                <div className="zone-error">
                                  Draw an active reviewable Zone on the related Stream before
                                  creating evidence.
                                </div>
                              ) : null}
                              {blockedPreviewZoneCount > 0 ? (
                                <span className="meta-text">
                                  Privacy and ignore Zones are excluded from evidence creation.
                                </span>
                              ) : null}
                              <button
                                className="secondary-action"
                                disabled={isCreatingPreviewEvidence || !canCreatePreviewEvidence}
                                onClick={handleCreateMotionEvidenceFromSavedPreview}
                                type="button"
                              >
                                {isCreatingPreviewEvidence
                                  ? "Creating pending evidence..."
                                  : "Create pending context from saved image"}
                              </button>
                              <span className="meta-text">
                                This creates pending evidence only. It does not create Events,
                                Visits, labels, or truth.
                              </span>
                              </div>
                            </details>
                          ) : null}
                          {previewEvidenceError ? (
                            <div className="zone-error">{previewEvidenceError}</div>
                          ) : null}
                          {previewEvidenceResult ? (
                            <div className="external-preview-evidence-status">
                              <strong>{previewEvidenceResult.message}</strong>
                              <div className="source-connection-meta">
                                <span>
                                  Review context: {previewEvidenceResult.motion_evidence_id}
                                </span>
                                {previewEvidenceResult.zone_id ? (
                                  <span>Zone: {previewEvidenceResult.zone_id}</span>
                                ) : null}
                                <span>Status: {formatLabel(previewEvidenceResult.status)}</span>
                              </div>
                              <span className="meta-text">
                                Pending context is not reviewed data. Creating a review item is
                                explicit, and Review correction still creates the dataset label.
                              </span>
                              {previewEvidenceResult.warnings.length > 0 ? (
                                <div className="source-warning-list">
                                  {previewEvidenceResult.warnings.map((warning) => (
                                    <span key={warning}>{warning}</span>
                                  ))}
                                </div>
                              ) : null}
                              <div className="detail-actions">
                                <button
                                  className="secondary-action"
                                  onClick={() =>
                                    onOpenMotionEvidence(
                                      previewEvidenceResult.motion_evidence_id,
                                    )
                                  }
                                  type="button"
                                >
                                  Open review context
                                </button>
                                <button
                                  className="primary-action"
                                  disabled={
                                    isPromotingPreviewEvidence || !canPromotePreviewEvidence
                                  }
                                  onClick={handlePromotePreviewEvidence}
                                  type="button"
                                >
                                  {isPromotingPreviewEvidence
                                    ? "Creating review item..."
                                    : "Create review item"}
                                </button>
                              </div>
                              {previewPromotionError ? (
                                <div className="zone-error">{previewPromotionError}</div>
                              ) : null}
                              {previewPromotionResult ? (
                                <div className="external-preview-promotion-status">
                                  <strong>
                                    Review item created.
                                  </strong>
                                  <div className="source-connection-meta">
                                    {previewPromotionResult.event_id ? (
                                      <span>Event: {previewPromotionResult.event_id}</span>
                                    ) : null}
                                    {previewPromotionResult.visit_id ? (
                                      <span>Visit: {previewPromotionResult.visit_id}</span>
                                    ) : null}
                                    <span>
                                      Evidence:{" "}
                                      {formatLabel(previewPromotionResult.evidence.status)}
                                    </span>
                                  </div>
                                  <span className="meta-text">
                                    No reviewed data was created. Correct the item in Review before
                                    using reviewed-only exports.
                                  </span>
                                  <div className="detail-actions">
                                    {previewPromotionResult.event_id ? (
                                      <button
                                        className="secondary-action"
                                        onClick={() =>
                                          onOpenEvent(previewPromotionResult.event_id!)
                                        }
                                        type="button"
                                      >
                                        Open Event detail
                                      </button>
                                    ) : null}
                                    {previewPromotionResult.visit_id ? (
                                      <button
                                        className="secondary-action"
                                        onClick={() =>
                                          onOpenVisit(previewPromotionResult.visit_id!)
                                        }
                                        type="button"
                                      >
                                        Open Visit detail
                                      </button>
                                    ) : null}
                                    <button
                                      className="primary-action"
                                      onClick={onOpenReview}
                                      type="button"
                                    >
                                      Review item
                                    </button>
                                    <button
                                      className="secondary-action"
                                      onClick={onOpenExports}
                                      type="button"
                                    >
                                      Export reviewed data
                                    </button>
                                  </div>
                                </div>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}
              {isFolderImportProvider ? (
                <div className="folder-source-import-panel">
                  <div className="item-title-row">
                    <h3>Folder import</h3>
                    <StatusPill
                      label={folderPreviewResult ? "Preview ready" : "Explicit"}
                      tone={folderPreviewResult ? "good" : "quiet"}
                    />
                  </div>
                  <p>
                    Folder import is explicit. Preview scans the configured folder and creates no
                    records. Import copies supported files into local media and creates MediaAssets
                    only.
                  </p>
                  <p className="meta-text">
                    Evidence handoff stays explicit and review-only. No Events, Visits, labels, or
                    truth are created here.
                  </p>
                  <div className="folder-import-control-grid">
                    <label className="checkbox-row">
                      <input
                        checked={folderRecursive}
                        onChange={(event) => {
                          setFolderRecursive(event.target.checked);
                          setFolderPreviewResult(null);
                          setFolderImportResult(null);
                        }}
                        type="checkbox"
                      />
                      Recursive
                    </label>
                    <label>
                      Allowed extensions
                      <input
                        onChange={(event) => {
                          setFolderAllowedExtensions(event.target.value);
                          setFolderPreviewResult(null);
                          setFolderImportResult(null);
                        }}
                        value={folderAllowedExtensions}
                      />
                    </label>
                    <label>
                      Max files
                      <input
                        min="1"
                        onChange={(event) => {
                          setFolderMaxFiles(event.target.value);
                          setFolderPreviewResult(null);
                          setFolderImportResult(null);
                        }}
                        type="number"
                        value={folderMaxFiles}
                      />
                    </label>
                    <label>
                      Max depth
                      <input
                        min="0"
                        onChange={(event) => {
                          setFolderMaxDepth(event.target.value);
                          setFolderPreviewResult(null);
                          setFolderImportResult(null);
                        }}
                        type="number"
                        value={folderMaxDepth}
                      />
                    </label>
                  </div>
                  <label>
                    Import note
                    <textarea
                      onChange={(event) => setFolderImportNote(event.target.value)}
                      placeholder="optional local media context"
                      value={folderImportNote}
                    />
                  </label>
                  <div className="folder-import-actions">
                    <button
                      className="secondary-action"
                      disabled={isPreviewingFolderImport}
                      onClick={() => void handlePreviewFolderImport()}
                      type="button"
                    >
                      {isPreviewingFolderImport
                        ? "Previewing folder import..."
                        : "Preview folder import"}
                    </button>
                    {folderPreviewResult ? (
                      <button
                        className="primary-action"
                        disabled={
                          isImportingFolderMedia ||
                          folderPreviewResult.candidates.length === 0 ||
                          !selectedFirstStream
                        }
                        onClick={() => void handleImportPreviewedFolderFiles()}
                        type="button"
                      >
                        {isImportingFolderMedia
                          ? "Importing as MediaAssets..."
                          : "Import previewed files as MediaAssets"}
                      </button>
                    ) : null}
                  </div>
                  {selectedFirstStream ? (
                    <span className="meta-text">
                      Stream context: {selectedFirstStream.name}. Local media stays linked to this
                      Source/Stream context.
                    </span>
                  ) : (
                    <span className="meta-text">
                      This Source has no related Stream yet, so import will wait for Stream context.
                    </span>
                  )}
                  {folderPreviewError ? <div className="zone-error">{folderPreviewError}</div> : null}
                  {folderImportError ? <div className="zone-error">{folderImportError}</div> : null}
                  {folderPreviewResult ? (
                    <div className="folder-import-preview-result">
                      <div className="folder-import-summary-grid">
                        <div>
                          <span>Candidates</span>
                          <strong>{folderPreviewResult.total_candidates}</strong>
                        </div>
                        <div>
                          <span>Skipped</span>
                          <strong>{folderPreviewResult.total_skipped}</strong>
                        </div>
                        <div>
                          <span>Known bytes</span>
                          <strong>{formatBytes(folderPreviewResult.total_known_bytes)}</strong>
                        </div>
                        <div>
                          <span>Unknown sizes</span>
                          <strong>{folderPreviewResult.unknown_size_count}</strong>
                        </div>
                      </div>
                      <div className="source-connection-meta">
                        <span>Scanned: {formatDateTime(folderPreviewResult.scanned_at)}</span>
                        <span>Dry run: {folderPreviewResult.dry_run ? "Yes" : "No"}</span>
                        <span>
                          Creates MediaAssets:{" "}
                          {folderPreviewResult.creates_media_assets ? "Yes" : "No"}
                        </span>
                        <span>
                          Creates Events/Visits:{" "}
                          {folderPreviewResult.creates_events ||
                          folderPreviewResult.creates_visits
                            ? "Yes"
                            : "No"}
                        </span>
                        <span>
                          Creates truth: {folderPreviewResult.creates_truth ? "Yes" : "No"}
                        </span>
                      </div>
                      <span className="meta-text">
                        Preview only: no MediaAssets, Events, Visits, labels, or truth were
                        created.
                      </span>
                      {folderPreviewResult.warnings.length > 0 ? (
                        <div className="source-warning-list">
                          {folderPreviewResult.warnings.map((warning) => (
                            <span key={warning}>{warning}</span>
                          ))}
                        </div>
                      ) : null}
                      <div className="folder-import-list-grid">
                        <div className="folder-import-list">
                          <div className="item-title-row">
                            <strong>Candidates</strong>
                            <StatusPill
                              label={`${folderPreviewResult.candidates.length} files`}
                              tone="good"
                            />
                          </div>
                          {folderPreviewResult.candidates.length > 0 ? (
                            folderPreviewResult.candidates.map((candidate) => (
                              <article
                                className="folder-import-file-card"
                                key={candidate.relative_path}
                              >
                                <strong>{candidate.file_name}</strong>
                                <span>{candidate.relative_path}</span>
                                <div className="source-connection-meta">
                                  <span>{candidate.extension}</span>
                                  <span>{candidate.planned_media_kind}</span>
                                  <span>{formatBytes(candidate.size_bytes)}</span>
                                  {candidate.modified_at ? (
                                    <span>{formatDateTime(candidate.modified_at)}</span>
                                  ) : null}
                                </div>
                                {candidate.warnings.length > 0 ? (
                                  <div className="source-warning-list">
                                    {candidate.warnings.map((warning) => (
                                      <span key={warning}>{warning}</span>
                                    ))}
                                  </div>
                                ) : null}
                              </article>
                            ))
                          ) : (
                            <span className="meta-text">No supported files in this preview.</span>
                          )}
                        </div>
                        <div className="folder-import-list">
                          <div className="item-title-row">
                            <strong>Skipped</strong>
                            <StatusPill
                              label={`${folderPreviewResult.skipped.length} skipped`}
                              tone="quiet"
                            />
                          </div>
                          {folderPreviewResult.skipped.length > 0 ? (
                            folderPreviewResult.skipped.map((skipped) => (
                              <article
                                className="folder-import-file-card"
                                key={`${skipped.relative_path ?? skipped.file_name ?? "file"}-${
                                  skipped.reason
                                }-${skipped.message}`}
                              >
                                <strong>
                                  {skipped.file_name ?? skipped.relative_path ?? "Skipped file"}
                                </strong>
                                {skipped.relative_path ? <span>{skipped.relative_path}</span> : null}
                                <div className="source-connection-meta">
                                  <span>{formatLabel(skipped.reason)}</span>
                                  <span>{skipped.message}</span>
                                </div>
                              </article>
                            ))
                          ) : (
                            <span className="meta-text">No skipped files in this preview.</span>
                          )}
                        </div>
                      </div>
                    </div>
                  ) : null}
                  {folderImportResult ? (
                    <div className="folder-import-result-panel">
                      <div className="item-title-row">
                        <strong>Import result</strong>
                        <StatusPill
                          label={`${folderImportResult.total_imported} MediaAssets`}
                          tone={folderImportResult.total_imported > 0 ? "good" : "quiet"}
                        />
                      </div>
                      <div className="folder-import-summary-grid">
                        <div>
                          <span>Imported</span>
                          <strong>{folderImportResult.total_imported}</strong>
                        </div>
                        <div>
                          <span>Skipped</span>
                          <strong>{folderImportResult.total_skipped}</strong>
                        </div>
                        <div>
                          <span>Bytes copied</span>
                          <strong>{formatBytes(folderImportResult.total_bytes_copied)}</strong>
                        </div>
                        <div>
                          <span>Copy mode</span>
                          <strong>{formatLabel(folderImportResult.copy_mode)}</strong>
                        </div>
                      </div>
                      <span className="meta-text">
                        MediaAssets only. No MotionEvidence, Events, Visits, labels, or truth were
                        created.
                      </span>
                      {folderImportResult.warnings.length > 0 ? (
                        <div className="source-warning-list">
                          {folderImportResult.warnings.map((warning) => (
                            <span key={warning}>{warning}</span>
                          ))}
                        </div>
                      ) : null}
                      {folderImportResult.imported.length > 0 ? (
                        <div className="folder-evidence-dry-run-panel">
                          <div className="item-title-row">
                            <strong>Evidence handoff dry-run</strong>
                            {folderEvidenceDryRunResult ? (
                              <StatusPill
                                label={`${folderEvidenceDryRunResult.eligible_count} eligible`}
                                tone={
                                  folderEvidenceDryRunResult.eligible_count > 0
                                    ? "good"
                                    : "quiet"
                                }
                              />
                            ) : null}
                          </div>
                          <div className="folder-evidence-action">
                            <button
                              className="secondary-action"
                              disabled={isDryRunningFolderEvidence}
                              onClick={() => void handleDryRunFolderEvidenceHandoff()}
                              type="button"
                            >
                              {isDryRunningFolderEvidence
                                ? "Dry-running evidence handoff..."
                                : "Dry-run evidence handoff"}
                            </button>
                            <span className="meta-text">
                              Dry run only. No MotionEvidence, Events, Visits, labels, or truth
                              were created.
                            </span>
                          </div>
                          {folderEvidenceDryRunError ? (
                            <div className="zone-error">{folderEvidenceDryRunError}</div>
                          ) : null}
                          {folderEvidenceDryRunResult ? (
                            <>
                              <div className="folder-import-summary-grid">
                                <div>
                                  <span>Items checked</span>
                                  <strong>{folderEvidenceDryRunResult.total_items}</strong>
                                </div>
                                <div>
                                  <span>Would create</span>
                                  <strong>{folderEvidenceDryRunResult.would_create_count}</strong>
                                </div>
                                <div>
                                  <span>Duplicates skipped</span>
                                  <strong>
                                    {folderEvidenceDryRunResult.duplicate_skipped_count}
                                  </strong>
                                </div>
                                <div>
                                  <span>Skipped</span>
                                  <strong>{folderEvidenceDryRunResult.skipped_count}</strong>
                                </div>
                              </div>
                              {folderEvidenceDryRunResult.warnings.length > 0 ? (
                                <div className="source-warning-list">
                                  {folderEvidenceDryRunResult.warnings.map((warning) => (
                                    <span key={warning}>{warning}</span>
                                  ))}
                                </div>
                              ) : null}
                              <div className="folder-evidence-dry-run-list">
                                {folderEvidenceDryRunResult.items.map((item) => (
                                  <article
                                    className="folder-import-file-card"
                                    key={`${item.media_asset_id}-${item.skip_reason ?? "eligible"}`}
                                  >
                                    <div className="item-title-row">
                                      <strong>{item.file_name ?? item.media_asset_id}</strong>
                                      <StatusPill
                                        label={
                                          item.would_create_motion_evidence
                                            ? "Would create"
                                            : formatLabel(item.skip_reason ?? "Skipped")
                                        }
                                        tone={
                                          item.would_create_motion_evidence ? "good" : "quiet"
                                        }
                                      />
                                    </div>
                                    <div className="source-connection-meta">
                                      <span>{item.media_asset_id}</span>
                                      {item.stream_id ? <span>Stream: {item.stream_id}</span> : null}
                                      {item.zone_id ? <span>Zone: {item.zone_id}</span> : null}
                                      {item.existing_motion_evidence_id ? (
                                        <span>
                                          Existing MotionEvidence:{" "}
                                          {item.existing_motion_evidence_id}
                                        </span>
                                      ) : null}
                                    </div>
                                    {item.warnings.length > 0 ? (
                                      <div className="source-warning-list">
                                        {item.warnings.map((warning) => (
                                          <span key={warning}>{warning}</span>
                                        ))}
                                      </div>
                                    ) : null}
                                  </article>
                                ))}
                              </div>
                              <div className="folder-evidence-batch-create-panel">
                                <div className="item-title-row">
                                  <strong>Confirmed batch creation</strong>
                                  <StatusPill
                                    label={`${folderEvidenceDryRunEligibleCount} eligible`}
                                    tone={
                                      folderEvidenceDryRunEligibleCount > 0 ? "good" : "quiet"
                                    }
                                  />
                                </div>
                                <label className="checkbox-row">
                                  <input
                                    checked={folderEvidenceBatchConfirmed}
                                    disabled={folderEvidenceDryRunEligibleCount === 0}
                                    onChange={(event) =>
                                      setFolderEvidenceBatchConfirmed(event.target.checked)
                                    }
                                    type="checkbox"
                                  />
                                  Confirm eligible media
                                </label>
                                <div className="folder-evidence-action">
                                  <button
                                    className="primary-action"
                                    disabled={
                                      isCreatingFolderEvidenceBatch ||
                                      !folderEvidenceBatchConfirmed ||
                                      folderEvidenceDryRunEligibleCount === 0
                                    }
                                    onClick={() => void handleCreateFolderEvidenceBatch()}
                                    type="button"
                                  >
                                    {isCreatingFolderEvidenceBatch
                                      ? "Creating pending evidence..."
                                      : "Create pending evidence for eligible media"}
                                  </button>
                                  <span className="meta-text">
                                    Creates pending MotionEvidence only. No Events, Visits, labels,
                                    or truth are created.
                                  </span>
                                </div>
                                {folderEvidenceBatchCreateError ? (
                                  <div className="zone-error">
                                    {folderEvidenceBatchCreateError}
                                  </div>
                                ) : null}
                                {folderEvidenceBatchCreateResult ? (
                                  <div className="folder-evidence-result">
                                    <strong>{folderEvidenceBatchCreateResult.message}</strong>
                                    <div className="folder-import-summary-grid">
                                      <div>
                                        <span>Created</span>
                                        <strong>
                                          {folderEvidenceBatchCreateResult.created_count}
                                        </strong>
                                      </div>
                                      <div>
                                        <span>Skipped</span>
                                        <strong>
                                          {folderEvidenceBatchCreateResult.skipped_count}
                                        </strong>
                                      </div>
                                      <div>
                                        <span>Duplicates skipped</span>
                                        <strong>
                                          {
                                            folderEvidenceBatchCreateResult.duplicate_skipped_count
                                          }
                                        </strong>
                                      </div>
                                      <div>
                                        <span>Items</span>
                                        <strong>
                                          {folderEvidenceBatchCreateResult.total_items}
                                        </strong>
                                      </div>
                                    </div>
                                    {folderEvidenceBatchCreateResult.warnings.length > 0 ? (
                                      <div className="source-warning-list">
                                        {folderEvidenceBatchCreateResult.warnings.map((warning) => (
                                          <span key={warning}>{warning}</span>
                                        ))}
                                      </div>
                                    ) : null}
                                    <div className="folder-evidence-dry-run-list">
                                      {folderEvidenceBatchCreateResult.items.map((item) => (
                                        <article
                                          className="folder-import-file-card"
                                          key={`${item.media_asset_id}-${
                                            item.motion_evidence_id ?? item.skip_reason ?? "batch"
                                          }`}
                                        >
                                          <div className="item-title-row">
                                            <strong>{item.media_asset_id}</strong>
                                            <StatusPill
                                              label={
                                                item.created
                                                  ? "Created"
                                                  : formatLabel(item.skip_reason ?? "Skipped")
                                              }
                                              tone={item.created ? "good" : "quiet"}
                                            />
                                          </div>
                                          <div className="source-connection-meta">
                                            {item.motion_evidence_id ? (
                                              <span>
                                                MotionEvidence: {item.motion_evidence_id}
                                              </span>
                                            ) : null}
                                            {item.stream_id ? (
                                              <span>Stream: {item.stream_id}</span>
                                            ) : null}
                                            {item.zone_id ? (
                                              <span>Zone: {item.zone_id}</span>
                                            ) : null}
                                            {item.existing_motion_evidence_id ? (
                                              <span>
                                                Existing MotionEvidence:{" "}
                                                {item.existing_motion_evidence_id}
                                              </span>
                                            ) : null}
                                          </div>
                                          {item.warnings.length > 0 ? (
                                            <div className="source-warning-list">
                                              {item.warnings.map((warning) => (
                                                <span key={warning}>{warning}</span>
                                              ))}
                                            </div>
                                          ) : null}
                                        </article>
                                      ))}
                                    </div>
                                    <span className="meta-text">
                                      Open Motion Evidence to review, ignore, or promote pending
                                      evidence. Use the Motion Evidence navigation item for the
                                      review step.
                                    </span>
                                  </div>
                                ) : null}
                              </div>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                      <div className="folder-import-list-grid">
                        <div className="folder-import-list">
                          <div className="item-title-row">
                            <strong>Created MediaAssets</strong>
                            <StatusPill
                              label={`${folderImportResult.imported.length} created`}
                              tone="good"
                            />
                          </div>
                          {folderImportResult.imported.length > 0 ? (
                            folderImportResult.imported.map((item) => (
                              <article
                                className="folder-import-file-card"
                                key={item.media_asset_id}
                              >
                                <strong>{item.media_asset_id}</strong>
                                <span>{item.relative_source_path}</span>
                                <div className="source-connection-meta">
                                  <span>{item.file_name}</span>
                                  {item.content_type ? <span>{item.content_type}</span> : null}
                                  <span>{formatBytes(item.size_bytes)}</span>
                                  {item.stream_id ? <span>Stream: {item.stream_id}</span> : null}
                                  {item.zone_id ? <span>Zone: {item.zone_id}</span> : null}
                                </div>
                                {item.warnings.length > 0 ? (
                                  <div className="source-warning-list">
                                    {item.warnings.map((warning) => (
                                      <span key={warning}>{warning}</span>
                                    ))}
                                  </div>
                                ) : null}
                                <div className="folder-evidence-action">
                                  <button
                                    className="secondary-action"
                                    disabled={folderEvidenceLoadingId === item.media_asset_id}
                                    onClick={() =>
                                      void handleCreateMotionEvidenceFromFolderImport(item)
                                    }
                                    type="button"
                                  >
                                    {folderEvidenceLoadingId === item.media_asset_id
                                      ? "Creating pending evidence..."
                                      : "Create pending evidence"}
                                  </button>
                                  <span className="meta-text">
                                    Pending evidence only. No Events, Visits, labels, or truth were
                                    created.
                                  </span>
                                </div>
                                {folderEvidenceErrors[item.media_asset_id] ? (
                                  <div className="zone-error">
                                    {folderEvidenceErrors[item.media_asset_id]}
                                  </div>
                                ) : null}
                                {folderEvidenceResults[item.media_asset_id] ? (
                                  <div className="folder-evidence-result">
                                    <strong>
                                      MotionEvidence:{" "}
                                      {
                                        folderEvidenceResults[item.media_asset_id]
                                          .motion_evidence_id
                                      }
                                    </strong>
                                    <span>
                                      {folderEvidenceResults[item.media_asset_id]
                                        .duplicate_skipped
                                        ? "Existing evidence reused. Open Motion Evidence to review, ignore, or promote pending evidence."
                                        : "Open Motion Evidence to review, ignore, or promote pending evidence."}
                                    </span>
                                    {folderEvidenceResults[item.media_asset_id].warnings.length >
                                    0 ? (
                                      <div className="source-warning-list">
                                        {folderEvidenceResults[item.media_asset_id].warnings.map(
                                          (warning) => (
                                            <span key={warning}>{warning}</span>
                                          ),
                                        )}
                                      </div>
                                    ) : null}
                                  </div>
                                ) : null}
                              </article>
                            ))
                          ) : (
                            <span className="meta-text">No MediaAssets created.</span>
                          )}
                        </div>
                        <div className="folder-import-list">
                          <div className="item-title-row">
                            <strong>Skipped during import</strong>
                            <StatusPill
                              label={`${folderImportResult.skipped.length} skipped`}
                              tone="quiet"
                            />
                          </div>
                          {folderImportResult.skipped.length > 0 ? (
                            folderImportResult.skipped.map((skipped) => (
                              <article
                                className="folder-import-file-card"
                                key={`${skipped.relative_path ?? skipped.file_name ?? "file"}-${
                                  skipped.reason
                                }-${skipped.message}`}
                              >
                                <strong>
                                  {skipped.file_name ?? skipped.relative_path ?? "Skipped file"}
                                </strong>
                                {skipped.relative_path ? <span>{skipped.relative_path}</span> : null}
                                <div className="source-connection-meta">
                                  <span>{formatLabel(skipped.reason)}</span>
                                  <span>{skipped.message}</span>
                                </div>
                              </article>
                            ))
                          ) : (
                            <span className="meta-text">No files skipped during import.</span>
                          )}
                        </div>
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
            <form className="source-setup-form" onSubmit={handleSaveProviderConfiguration}>
              <div className="item-title-row">
                <h3>Provider setup</h3>
                <StatusPill label="Metadata only" tone="quiet" />
              </div>
              <p className="meta-text">
                Provider setup stores safe metadata for this Source. It does not connect, capture,
                decode, or create truth.
              </p>
              <label>
                Provider
                <select
                  value={providerKey}
                  onChange={(event) => handleProviderChange(event.target.value)}
                >
                  {providerDefinitions.map((definition) => (
                    <option key={definition.provider_key} value={definition.provider_key}>
                      {definition.display_name}
                    </option>
                  ))}
                </select>
              </label>
              {selectedProviderDefinition ? (
                <>
                  <p className="meta-text">{selectedProviderDefinition.description}</p>
                  <div className="provider-field-grid">
                    {selectedProviderDefinition.fields.map((field) => {
                      const existingPreview = selectedConfiguration?.safe_config_preview[field.key];
                      return (
                        <label key={field.key}>
                          {field.label}
                          <input
                            placeholder={
                              field.secret && existingPreview === "configured"
                                ? "Configured marker saved"
                                : field.placeholder ?? ""
                            }
                            type={field.secret ? "password" : "text"}
                            value={configDraft[field.key] ?? ""}
                            onChange={(event) =>
                              setConfigDraft((current) => ({
                                ...current,
                                [field.key]: event.target.value,
                              }))
                            }
                          />
                          <span className="field-meta">
                            {field.required ? "Required" : "Optional"}
                            {field.secret ? " · stored as marker only" : ""}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </>
              ) : null}
              <div className="source-setup-actions">
                <button className="primary-action" disabled={isSavingSetup} type="submit">
                  Save setup
                </button>
                <button
                  className="secondary-action"
                  onClick={refreshSourceSetupStatuses}
                  type="button"
                >
                  Refresh status
                </button>
              </div>
              {selectedConfiguration?.setup_hint ? (
                <span className="meta-text">{selectedConfiguration.setup_hint}</span>
              ) : null}
              {setupMessage ? <div className="zone-message">{setupMessage}</div> : null}
              {setupError ? <div className="zone-error">{setupError}</div> : null}
            </form>
          </div>
          <section className="source-streams-panel">
            <div className="section-heading">
              <div>
                <h3>Source Streams</h3>
                <span className="meta-text">
                  Open Stream Detail to inspect playback status and draw Zones
                </span>
              </div>
              <StatusPill label={`${selectedSourceStreams.length} streams`} tone="quiet" />
            </div>
            <div className="source-stream-grid">
              {selectedSourceStreams.length > 0 ? (
                selectedSourceStreams.map((stream) => {
                  const reviewStream = selectedReviewStreams.get(stream.id);
                  const playbackLabel = reviewStream
                    ? formatLabel(reviewStream.playback_status)
                    : stream.is_live
                      ? "Stream"
                      : "Placeholder";
                  const allStreamMediaAssets = mediaAssetsByStream.get(stream.id) ?? [];
                  const streamMediaAssets = allStreamMediaAssets.slice(0, MEDIA_TIMELINE_LIMIT);
                  const streamTimelineZones = timelineZonesByStream[stream.id] ?? [];
                  const reviewableTimelineZones = streamTimelineZones.filter(isReviewableZone);
                  const selectedTimelineZoneId = timelineSelectedZoneByStream[stream.id] ?? "";
                  const blockedTimelineZoneCount = streamTimelineZones.filter(
                    (zone) => zone.is_active && !isReviewableZone(zone),
                  ).length;
                  const allStreamImageAssets = allStreamMediaAssets.filter(isImageMedia);
                  const streamImageAssets = streamMediaAssets.filter(isImageMedia);
                  const recentMotionAssets = streamImageAssets.slice(0, MOTION_SNAPSHOT_LIMIT);
                  const motionState = streamMotionCheckState[stream.id] ?? {};
                  const motionSelectedIds = selectedMotionMediaIds(stream.id, streamImageAssets);
                  const selectedMotionAssets = sortOldestFirst(
                    streamImageAssets.filter((asset) => motionSelectedIds.includes(asset.id)),
                  );
                  const sourceHealthState = selectedSource
                    ? sourceHealthActions[selectedSource.id]
                    : undefined;
                  const lastSnapshotTest = sourceHealthState?.lastSnapshotTest;
                  const lastCapture =
                    sourceHealthState?.lastCaptureByStreamId?.[stream.id];
                  const sourceHealthLabel = sourceHealthReadiness({
                    isExternalUrlProvider,
                    connection: selectedConnection,
                    setupReview: selectedSetupReview,
                    snapshotTest: lastSnapshotTest,
                    savedImageCount: allStreamImageAssets.length,
                    motionState,
                  });
                  const sourceHealthLastError =
                    motionState.error ??
                    (lastCapture?.status === "failure" ? lastCapture.error : null) ??
                    (lastSnapshotTest?.status === "failure" ? lastSnapshotTest.error : null);
                  const streamRetentionItems =
                    savedMediaRetentionReport?.items.filter(
                      (item) => item.stream_id === stream.id,
                    ) ?? [];
                  const storageSummary = storageGuardrailSummary(
                    allStreamImageAssets,
                    streamRetentionItems,
                    motionState,
                  );
                  const motionResult = motionState.result ?? null;
                  const motionCreatedEvidence = motionResult?.created_evidence[0] ?? null;
                  const canCreateMotionReviewActivity =
                    motionResult?.can_create_review_activity ?? true;
                  const shouldCreateMotionReviewActivity =
                    motionResult?.should_create_review_activity ?? false;
                  const motionActivityAreaLabel =
                    motionResult?.strongest_activity_area_label ??
                    motionResult?.strongest_zone_id ??
                    null;
                  const motionSessionLabel = activitySessionLabel(
                    motionResult?.session_status,
                  );
                  const motionCropPlan = motionResult?.crop_plan ?? null;
                  const usesAutomaticActivityAreas = motionResult?.uses_auto_regions ?? false;
                  const bestMotionAssetId =
                    motionResult?.best_snapshot_media_asset_id ??
                    motionResult?.best_media_asset_id ??
                    null;
                  const bestMotionAsset = bestMotionAssetId
                    ? allStreamImageAssets.find(
                        (asset) => asset.id === bestMotionAssetId,
                      )
                    : null;
                  const isCurrentSnapshotWatch =
                    snapshotWatch.sourceId === selectedSourceId &&
                    snapshotWatch.streamId === stream.id;
                  const streamSnapshotWatch = isCurrentSnapshotWatch
                    ? snapshotWatch
                    : initialSnapshotWatchState();
                  const isAnotherSnapshotWatchActive =
                    snapshotWatch.isWatching && !isCurrentSnapshotWatch;
                  const snapshotWatchStartBlockReason = !isExternalUrlProvider
                    ? "Snapshot watch is available for external snapshot sources."
                    : sourceNeedsSetup(selectedConnection, selectedSetupReview)
                      ? "Check source setup before starting Snapshot watch."
                      : storageSummary.savedImageCount >= SNAPSHOT_WATCH_STORAGE_BLOCK_COUNT
                        ? "Review/export or clean up manually before starting repeated checks."
                        : isAnotherSnapshotWatchActive
                          ? "Stop the current Snapshot watch before starting another."
                          : null;
                  const canStartSnapshotWatch =
                    !snapshotWatch.isWatching &&
                    !snapshotWatchStartBlockReason &&
                    !isSavingPreview;
                  const snapshotWatchNextRecommendation = snapshotWatchNextAction(
                    streamSnapshotWatch,
                    motionResult,
                    motionCreatedEvidence,
                  );
                  const monitorStatus = streamMonitorStatuses[stream.id] ?? null;
                  const monitorError = streamMonitorErrors[stream.id] || null;
                  const isMonitorLoading = Boolean(streamMonitorLoading[stream.id]);
                  const isMonitoring = monitorIsActive(monitorStatus);
                  const monitorStartBlockReason = !isExternalUrlProvider
                    ? "Monitoring is available for external snapshot sources."
                    : sourceNeedsSetup(selectedConnection, selectedSetupReview)
                      ? "Confirm Source health before starting monitoring."
                      : storageSummary.savedImageCount >= SNAPSHOT_WATCH_STORAGE_BLOCK_COUNT
                        ? "Review/export or clean up manually before starting monitoring."
                        : null;
                  const canStartMonitoring =
                    !isMonitorLoading && !isMonitoring && !monitorStartBlockReason;
                  return (
                    <section className="source-stream-card" key={stream.id}>
                      <div className="item-title-row">
                        <h4>{stream.name}</h4>
                        <StatusPill
                          label={playbackLabel}
                          tone={reviewStream?.playback_status === "demo" ? "good" : "quiet"}
                        />
                      </div>
                      <p>{reviewStream?.message ?? stream.description}</p>
                      <div className="source-connection-meta">
                        <span>
                          Playback:{" "}
                          {reviewStream ? formatLabel(reviewStream.playback_kind) : "Placeholder"}
                        </span>
                        <span>
                          Live:{" "}
                          {reviewStream?.supports_live_playback ? "Available" : "Not available"}
                        </span>
                        <span>
                          Zones:{" "}
                          {reviewStream
                            ? reviewStream.supports_zone_editing
                              ? "Available"
                              : "Unavailable"
                            : "Available"}
                        </span>
                      </div>
                      <div className="source-health-panel">
                        <div className="item-title-row">
                          <div>
                            <strong>Source health</strong>
                            <p className="meta-text">
                              Camera status for manual snapshot and motion checks.
                            </p>
                          </div>
                          <StatusPill
                            label={sourceHealthLabel}
                            tone={sourceHealthReadinessTone(sourceHealthLabel)}
                          />
                        </div>
                        <div className="source-health-grid">
                          <div className="data-row">
                            <span>Last snapshot test</span>
                            <strong>{snapshotHealthText(lastSnapshotTest)}</strong>
                          </div>
                          <div className="data-row">
                            <span>Last capture</span>
                            <strong>{captureHealthText(lastCapture, streamImageAssets)}</strong>
                          </div>
                          <div className="data-row">
                            <span>Saved images</span>
                            <strong>{allStreamImageAssets.length}</strong>
                          </div>
                          <div className="data-row">
                            <span>Last motion check</span>
                            <strong>{motionHealthText(motionState)}</strong>
                          </div>
                          <div className="data-row">
                            <span>Last activity</span>
                            <strong>{lastActivityHealthText(motionState)}</strong>
                          </div>
                          <div className="data-row">
                            <span>Next recommended action</span>
                            <strong>
                              {sourceHealthNextAction(
                                sourceHealthLabel,
                                motionResult,
                                motionCreatedEvidence,
                              )}
                            </strong>
                          </div>
                        </div>
                        {sourceHealthLastError ? (
                          <div className="zone-error">Last error: {sourceHealthLastError}</div>
                        ) : null}
                        <details className="advanced-details">
                          <summary>Advanced details</summary>
                          <div className="source-connection-meta">
                            <span>Source ID: {selectedSource?.id ?? "none"}</span>
                            <span>Stream ID: {stream.id}</span>
                            <span>
                              Provider:{" "}
                              {selectedConfiguration?.provider_key ??
                                selectedSetupReview?.provider_key ??
                                "unknown"}
                            </span>
                            {lastSnapshotTest?.contentType ? (
                              <span>Snapshot content: {lastSnapshotTest.contentType}</span>
                            ) : null}
                            {lastCapture?.mediaAssetId ? (
                              <span>Saved image ID: {lastCapture.mediaAssetId}</span>
                            ) : null}
                          </div>
                        </details>
                      </div>
                      <div className="source-storage-guardrails-panel">
                        <div className="item-title-row">
                          <div>
                            <strong>Storage guardrails</strong>
                            <p className="meta-text">
                              Read-only saved image signals before manual Snapshot watch.
                            </p>
                          </div>
                          <StatusPill
                            label={
                              isLoadingSavedMediaRetention
                                ? "Loading"
                                : storageSummary.readiness
                            }
                            tone={storageGuardrailTone(storageSummary.readiness)}
                          />
                        </div>
                        <span className="meta-text">{storageGuardrailCopy(storageSummary)}</span>
                        <div className="source-storage-grid">
                          <div className="data-row">
                            <span>Saved images</span>
                            <strong>{storageSummary.savedImageCount}</strong>
                          </div>
                          <div className="data-row">
                            <span>Storage estimate</span>
                            <strong>{formatBytes(storageSummary.savedImageTotalBytes)}</strong>
                          </div>
                          <div className="data-row">
                            <span>Recent saved images</span>
                            <strong>{storageSummary.recentSavedImageCount}</strong>
                          </div>
                          <div className="data-row">
                            <span>Protected media</span>
                            <strong>{optionalCountText(storageSummary.protectedMediaCount)}</strong>
                          </div>
                          <div className="data-row">
                            <span>Review-linked/pending</span>
                            <strong>{optionalCountText(storageSummary.reviewLinkedCount)}</strong>
                          </div>
                          <div className="data-row">
                            <span>Recommended next action</span>
                            <strong>{storageSummary.recommendedAction}</strong>
                          </div>
                        </div>
                        <span className="meta-text">
                          Reviewed/export-linked media is protected by default. Manual cleanup
                          remains separate.
                        </span>
                        <span className="meta-text">
                          Snapshot watch remains bounded and user-started.
                        </span>
                        {savedMediaRetentionError ? (
                          <div className="zone-error">{savedMediaRetentionError}</div>
                        ) : null}
                        <details className="advanced-details">
                          <summary>Advanced details</summary>
                          <div className="source-connection-meta">
                            <span>
                              Retention coverage: {formatLabel(storageSummary.retentionCoverage)}
                            </span>
                            <span>
                              Unreviewed saved images:{" "}
                              {optionalCountText(storageSummary.unreviewedSavedImageCount)}
                            </span>
                            <span>
                              Oldest saved image:{" "}
                              {storageSummary.oldestSavedImageAt
                                ? formatDateTime(storageSummary.oldestSavedImageAt)
                                : "Not available yet"}
                            </span>
                            <span>
                              Newest saved image:{" "}
                              {storageSummary.newestSavedImageAt
                                ? formatDateTime(storageSummary.newestSavedImageAt)
                                : "Not available yet"}
                            </span>
                          </div>
                        </details>
                      </div>
                      {isExternalUrlProvider ? (
                        <div className="camera-monitor-panel">
                          <div className="item-title-row">
                            <div>
                              <strong>Camera Monitoring</strong>
                              <p className="meta-text">
                                Backend-managed monitoring for this external snapshot stream.
                              </p>
                            </div>
                            <StatusPill
                              label={monitorLabel(monitorStatus)}
                              tone={monitorTone(monitorStatus)}
                            />
                          </div>
                          <div className="camera-monitor-grid">
                            <div className="data-row">
                              <span>Last checked</span>
                              <strong>
                                {monitorStatus?.last_tick_at
                                  ? formatDateTime(monitorStatus.last_tick_at)
                                  : "Not checked"}
                              </strong>
                            </div>
                            <div className="data-row">
                              <span>Last snapshot</span>
                              <strong>
                                {monitorStatus?.last_snapshot_media_asset_id ?? "None yet"}
                              </strong>
                            </div>
                            <div className="data-row">
                              <span>Snapshots saved</span>
                              <strong>
                                {monitorStatus
                                  ? `${monitorStatus.snapshots_saved}/${monitorStatus.max_snapshots}`
                                  : "0/100"}
                              </strong>
                            </div>
                            <div className="data-row">
                              <span>Motion checks run</span>
                              <strong>{monitorStatus?.motion_checks_run ?? 0}</strong>
                            </div>
                            <div className="data-row">
                              <span>Last activity</span>
                              <strong>{monitorActivityText(monitorStatus)}</strong>
                            </div>
                            <div className="data-row">
                              <span>Last activity area</span>
                              <strong>{monitorActivityAreaText(monitorStatus)}</strong>
                            </div>
                            <div className="data-row">
                              <span>Last session status</span>
                              <strong>
                                {monitorStatus?.last_session_status
                                  ? formatLabel(monitorStatus.last_session_status)
                                  : "None yet"}
                              </strong>
                            </div>
                            <div className="data-row">
                              <span>Stop reason</span>
                              <strong>
                                {monitorStopReasonLabel(monitorStatus?.stop_reason)}
                              </strong>
                            </div>
                          </div>
                          <div className="detail-actions">
                            <button
                              className="primary-action"
                              disabled={!canStartMonitoring}
                              onClick={() => void handleStartMonitoring(stream)}
                              type="button"
                            >
                              {isMonitorLoading && !isMonitoring
                                ? "Starting..."
                                : "Start monitoring"}
                            </button>
                            <button
                              className="secondary-action"
                              disabled={isMonitorLoading || !isMonitoring}
                              onClick={() => void handleStopMonitoring(stream)}
                              type="button"
                            >
                              {isMonitorLoading && isMonitoring
                                ? "Stopping..."
                                : "Stop monitoring"}
                            </button>
                            <button
                              className="secondary-action"
                              disabled={isMonitorLoading}
                              onClick={() => void handleRefreshMonitoring(stream)}
                              type="button"
                            >
                              Refresh status
                            </button>
                          </div>
                          <span className="meta-text">
                            Monitoring is in-memory for this API run. Review activity, correction,
                            Bird Log, and Export remain explicit actions.
                          </span>
                          {monitorStartBlockReason ? (
                            <span className="meta-text">{monitorStartBlockReason}</span>
                          ) : null}
                          {monitorStatus?.last_error ? (
                            <div className="zone-error">Last error: {monitorStatus.last_error}</div>
                          ) : null}
                          {monitorError ? <div className="zone-error">{monitorError}</div> : null}
                          <details className="advanced-details">
                            <summary>Advanced details</summary>
                            <div className="source-connection-meta">
                              <span>Monitor ID: {monitorStatus?.monitor_id ?? "none"}</span>
                              <span>
                                Started:{" "}
                                {monitorStatus?.started_at
                                  ? formatDateTime(monitorStatus.started_at)
                                  : "Not started"}
                              </span>
                              <span>
                                Next check:{" "}
                                {monitorStatus?.next_tick_at
                                  ? formatDateTime(monitorStatus.next_tick_at)
                                  : "Not scheduled"}
                              </span>
                              <span>
                                Runtime limit:{" "}
                                {monitorStatus
                                  ? `${Math.round(monitorStatus.max_runtime_seconds / 60)} min`
                                  : "30 min"}
                              </span>
                              <span>
                                Check interval: {monitorStatus?.interval_seconds ?? 15}s
                              </span>
                              <span>
                                Consecutive failures:{" "}
                                {monitorStatus?.consecutive_failures ?? 0}
                              </span>
                            </div>
                          </details>
                        </div>
                      ) : null}
                      {isExternalUrlProvider ? (
                        <details className="snapshot-watch-panel snapshot-watch-harness">
                          <summary>Advanced test harness: Snapshot watch</summary>
                          <div className="snapshot-watch-panel-body">
                          <div className="item-title-row">
                            <div>
                              <strong>Snapshot watch test harness</strong>
                              <p className="meta-text">
                                This is a bounded page-local test harness. The product monitoring
                                path is Camera Monitoring Core. It only runs while this page is
                                open and after you click Start.
                              </p>
                            </div>
                            <StatusPill
                              label={snapshotWatchLabel(streamSnapshotWatch.status)}
                              tone={snapshotWatchTone(streamSnapshotWatch.status)}
                            />
                          </div>
                          <div className="snapshot-watch-controls">
                            <label>
                              Snapshot interval
                              <select
                                disabled={snapshotWatch.isWatching}
                                onChange={(event) =>
                                  setSnapshotWatchIntervalSeconds(Number(event.target.value))
                                }
                                value={snapshotWatchIntervalSeconds}
                              >
                                {SNAPSHOT_WATCH_INTERVAL_OPTIONS.map((seconds) => (
                                  <option key={seconds} value={seconds}>
                                    {seconds}s
                                  </option>
                                ))}
                              </select>
                            </label>
                            <label>
                              Bounded run
                              <select
                                disabled={snapshotWatch.isWatching}
                                onChange={(event) =>
                                  setSnapshotWatchMaxCaptures(Number(event.target.value))
                                }
                                value={snapshotWatchMaxCaptures}
                              >
                                {SNAPSHOT_WATCH_CAPTURE_OPTIONS.map((count) => (
                                  <option key={count} value={count}>
                                    {count} captures
                                  </option>
                                ))}
                              </select>
                            </label>
                          </div>
                          <div className="snapshot-watch-grid">
                            <div className="data-row">
                              <span>Manual watch</span>
                              <strong>{streamSnapshotWatch.lastWatchStatus}</strong>
                            </div>
                            <div className="data-row">
                              <span>Started</span>
                              <strong>
                                {streamSnapshotWatch.watchStartedAt
                                  ? formatDateTime(streamSnapshotWatch.watchStartedAt)
                                  : "Not started"}
                              </strong>
                            </div>
                            <div className="data-row">
                              <span>Next capture</span>
                              <strong>
                                {streamSnapshotWatch.nextCaptureAt
                                  ? formatDateTime(streamSnapshotWatch.nextCaptureAt)
                                  : "Not scheduled"}
                              </strong>
                            </div>
                            <div className="data-row">
                              <span>Captured snapshots</span>
                              <strong>
                                {streamSnapshotWatch.capturesSucceeded}/
                                {streamSnapshotWatch.capturesAttempted}
                              </strong>
                            </div>
                            <div className="data-row">
                              <span>Motion checks</span>
                              <strong>{streamSnapshotWatch.motionChecksRun}</strong>
                            </div>
                            <div className="data-row">
                              <span>Last activity result</span>
                              <strong>
                                {streamSnapshotWatch.lastActivityResult ??
                                  "No motion check yet"}
                              </strong>
                            </div>
                            <div className="data-row">
                              <span>Stop reason</span>
                              <strong>
                                {snapshotWatchStopReasonLabel(streamSnapshotWatch.stopReason)}
                              </strong>
                            </div>
                            <div className="data-row">
                              <span>Next recommended action</span>
                              <strong>{snapshotWatchNextRecommendation}</strong>
                            </div>
                          </div>
                          <div className="detail-actions">
                            <button
                              className="primary-action"
                              disabled={!canStartSnapshotWatch}
                              onClick={() =>
                                handleStartSnapshotWatch(
                                  stream,
                                  reviewableTimelineZones,
                                  storageSummary,
                                )
                              }
                              type="button"
                            >
                              Start watch
                            </button>
                            {isCurrentSnapshotWatch && snapshotWatch.isWatching ? (
                              <button
                                className="secondary-action"
                                onClick={handleStopSnapshotWatch}
                                type="button"
                              >
                                Stop watch
                              </button>
                            ) : null}
                          </div>
                          {snapshotWatchStartBlockReason ? (
                            <span className="meta-text">{snapshotWatchStartBlockReason}</span>
                          ) : null}
                          {isCurrentSnapshotWatch && streamSnapshotWatch.lastWatchError ? (
                            <div className="zone-error">
                              {streamSnapshotWatch.lastWatchError}
                            </div>
                          ) : null}
                          <details className="advanced-details">
                            <summary>Advanced details</summary>
                            <div className="source-connection-meta">
                              <span>Source ID: {selectedSourceId ?? "none"}</span>
                              <span>Stream ID: {stream.id}</span>
                              <span>Interval: {streamSnapshotWatch.intervalSeconds}s</span>
                              <span>Max captures: {streamSnapshotWatch.maxCaptures}</span>
                              <span>
                                Last tick:{" "}
                                {streamSnapshotWatch.lastWatchTickAt
                                  ? formatDateTime(streamSnapshotWatch.lastWatchTickAt)
                                  : "none"}
                              </span>
                              <span>
                                Page-local timer:{" "}
                                {streamSnapshotWatch.isWatching ? "active" : "inactive"}
                              </span>
                            </div>
                          </details>
                          </div>
                        </details>
                      ) : null}
                      <div className="detail-actions">
                        <button
                          className="primary-action"
                          onClick={() => onOpenStream(stream.id)}
                          type="button"
                        >
                          Open Stream Detail
                        </button>
                        {isManualMediaReady ? (
                          <button
                            className="secondary-action"
                            onClick={onOpenImport}
                            type="button"
                          >
                            Import media
                          </button>
                        ) : null}
                      </div>
                      <div className="stream-media-timeline">
                        <div className="item-title-row">
                          <div>
                            <strong>Saved images for this stream</strong>
                            <p className="meta-text">
                              Captured snapshots and imported images stay under this camera/stream.
                              Analyze, review, and export remain explicit.
                            </p>
                          </div>
                          <StatusPill
                            label={
                              isLoadingMediaAssets
                                ? "Loading"
                                : `${streamMediaAssets.length} recent`
                            }
                            tone="quiet"
                          />
                        </div>
                        {mediaAssetsError ? (
                          <div className="zone-error">{mediaAssetsError}</div>
                        ) : null}
                        {timelineZoneErrors[stream.id] ? (
                          <div className="zone-error">{timelineZoneErrors[stream.id]}</div>
                        ) : null}
                        {streamMediaAssets.length > 0 ? (
                          <>
                            <label className="timeline-zone-select">
                              Review zone for evidence actions
                              <select
                                disabled={reviewableTimelineZones.length === 0}
                                onChange={(event) =>
                                  setTimelineSelectedZoneByStream((current) => ({
                                    ...current,
                                    [stream.id]: event.target.value,
                                  }))
                                }
                                value={selectedTimelineZoneId}
                              >
                                {reviewableTimelineZones.length > 0 ? (
                                  reviewableTimelineZones.map((zone) => (
                                    <option key={zone.id} value={zone.id}>
                                      {zone.name} ({formatLabel(zone.zone_type)})
                                    </option>
                                  ))
                                ) : (
                                  <option value="">No reviewable Zones</option>
                                )}
                              </select>
                            </label>
                            {reviewableTimelineZones.length === 0 ? (
                              <div className="zone-error">
                                Add an active non-privacy/non-ignore Zone before creating
                                review context.
                              </div>
                            ) : null}
                            {blockedTimelineZoneCount > 0 ? (
                              <span className="meta-text">
                                Privacy and ignore Zones are omitted from review context actions.
                              </span>
                            ) : null}
                            {streamImageAssets.length >= 2 ? (
                              <div className="stream-motion-check-panel">
                                <div className="item-title-row">
                                  <div>
                                    <strong>Check motion</strong>
                                    <p className="meta-text">
                                      {reviewableTimelineZones.length > 0
                                        ? "Compare saved snapshots inside active Zones before creating a review activity."
                                        : "No zones yet — MockingBird will check motion across automatic activity areas."}
                                    </p>
                                  </div>
                                  <StatusPill
                                    label={`${selectedMotionAssets.length} snapshots`}
                                    tone={selectedMotionAssets.length >= 2 ? "good" : "review"}
                                  />
                                </div>
                                <div className="source-connection-meta">
                                  <span>
                                    Saved snapshots: {streamImageAssets.length}
                                  </span>
                                  <span>
                                    Activity areas:{" "}
                                    {reviewableTimelineZones.length > 0
                                      ? reviewableTimelineZones
                                          .map((zone) => zone.name)
                                          .join(", ")
                                      : "automatic"}
                                  </span>
                                  <span>Manual action</span>
                                  <span>No reviewed data created</span>
                                </div>
                                {reviewableTimelineZones.length === 0 ? (
                                  <span className="meta-text">
                                    You can draw feeder/birdbath/ignore zones later for better
                                    results, but they are not required to check motion.
                                  </span>
                                ) : null}
                                <div className="motion-snapshot-picker">
                                  {recentMotionAssets.map((asset) => (
                                    <label className="checkbox-row" key={asset.id}>
                                      <input
                                        checked={motionSelectedIds.includes(asset.id)}
                                        onChange={() =>
                                          toggleMotionSnapshot(
                                            stream.id,
                                            streamImageAssets,
                                            asset.id,
                                          )
                                        }
                                        type="checkbox"
                                      />
                                      <span>
                                        {asset.original_filename || asset.filename} ·{" "}
                                        {formatDateTime(asset.created_at)}
                                      </span>
                                    </label>
                                  ))}
                                </div>
                                <div className="detail-actions">
                                  <button
                                    className="primary-action"
                                    disabled={
                                      motionState.isChecking ||
                                      motionState.isCreatingActivity ||
                                      selectedMotionAssets.length < 2
                                    }
                                    onClick={() =>
                                      void handleEvaluateSavedMediaMotion(
                                        stream,
                                        streamImageAssets,
                                        reviewableTimelineZones,
                                        { createActivity: false },
                                      )
                                    }
                                    type="button"
                                  >
                                    {motionState.isChecking ? "Checking..." : "Check motion"}
                                  </button>
                                  {motionResult?.activity_detected &&
                                  motionResult.created_evidence.length === 0 &&
                                  canCreateMotionReviewActivity &&
                                  shouldCreateMotionReviewActivity ? (
                                    <button
                                      className="primary-action"
                                      disabled={motionState.isCreatingActivity}
                                      onClick={() =>
                                        void handleEvaluateSavedMediaMotion(
                                          stream,
                                          streamImageAssets,
                                          reviewableTimelineZones,
                                          { createActivity: true },
                                        )
                                      }
                                      type="button"
                                    >
                                      {motionState.isCreatingActivity
                                        ? "Creating..."
                                        : "Create review activity"}
                                    </button>
                                  ) : null}
                                  {motionCreatedEvidence ? (
                                    <button
                                      className="primary-action"
                                      onClick={() => onOpenMotionEvidence(motionCreatedEvidence.id)}
                                      type="button"
                                    >
                                      Review activity
                                    </button>
                                  ) : null}
                                  <button
                                    className="secondary-action"
                                    onClick={onOpenBirdLog}
                                    type="button"
                                  >
                                    Bird Log
                                  </button>
                                  <button
                                    className="secondary-action"
                                    onClick={onOpenExports}
                                    type="button"
                                  >
                                    Export reviewed data
                                  </button>
                                </div>
                                {motionState.error ? (
                                  <div className="zone-error">{motionState.error}</div>
                                ) : null}
                                {motionResult?.activity_detected &&
                                !canCreateMotionReviewActivity ? (
                                  <span className="meta-text">
                                    Automatic activity areas can detect motion now; review activity
                                    creation still requires a named Zone in this build.
                                  </span>
                                ) : null}
                                {motionResult?.activity_detected &&
                                canCreateMotionReviewActivity &&
                                !shouldCreateMotionReviewActivity &&
                                !motionCreatedEvidence ? (
                                  <span className="meta-text">
                                    {motionResult.creation_skipped_reason ===
                                    "activity_session_duplicate_suppressed"
                                      ? "This looks like the same recent activity, so MockingBird did not create another review item."
                                      : "This looks like the same recent activity."}
                                  </span>
                                ) : null}
                                {motionResult ? (
                                  <div className="stream-motion-result">
                                    <div className="item-title-row">
                                      <strong>{motionSessionLabel}</strong>
                                      <StatusPill
                                        label={motionSessionLabel}
                                        tone={activitySessionTone(motionResult.session_status)}
                                      />
                                    </div>
                                    <div className="timeline-result-grid">
                                      <div className="data-row">
                                        <span>Activity session</span>
                                        <strong>{motionSessionLabel}</strong>
                                      </div>
                                      <div className="data-row">
                                        <span>Activity area</span>
                                        <strong>{motionActivityAreaLabel ?? "none"}</strong>
                                      </div>
                                      <div className="data-row">
                                        <span>Best snapshot</span>
                                        {bestMotionAsset ? (
                                          <a
                                            className="inline-link"
                                            href={apiClient.mediaFileUrl(bestMotionAsset.id)}
                                            rel="noreferrer"
                                            target="_blank"
                                          >
                                            {bestMotionAsset.original_filename ||
                                              bestMotionAsset.filename}
                                          </a>
                                        ) : (
                                          <strong>none</strong>
                                        )}
                                      </div>
                                      <div className="data-row">
                                        <span>Focused crop</span>
                                        <strong>{focusedCropStatus(motionCropPlan)}</strong>
                                      </div>
                                      <div className="data-row">
                                        <span>Score</span>
                                        <strong>
                                          {Math.round(
                                            motionResult.strongest_changed_ratio * 1000,
                                          ) / 10}
                                          % changed
                                        </strong>
                                      </div>
                                      <div className="data-row">
                                        <span>Next</span>
                                        <strong>{motionNextStep(motionResult, motionCreatedEvidence)}</strong>
                                      </div>
                                    </div>
                                    {motionResult.session_message ? (
                                      <span className="meta-text">
                                        {motionResult.session_message}
                                      </span>
                                    ) : null}
                                    {motionCropPlan &&
                                    !motionCropPlan.derived_crop_media_asset_id &&
                                    !motionCropPlan.is_full_frame_fallback ? (
                                      <span className="meta-text">
                                        MockingBird identified the area to crop for review/model
                                        input. Full snapshot remains saved.
                                      </span>
                                    ) : null}
                                    {motionCropPlan?.warning ? (
                                      <span className="meta-text">{motionCropPlan.warning}</span>
                                    ) : null}
                                    {motionResult.warnings.length > 0 ? (
                                      <div className="source-warning-list">
                                        {motionResult.warnings.map((warning) => (
                                          <span key={warning}>{warning}</span>
                                        ))}
                                      </div>
                                    ) : null}
                                    <span className="meta-text">
                                      {motionResult.local_first_note}
                                    </span>
                                    <details className="advanced-details">
                                      <summary>Advanced motion details</summary>
                                      <div className="timeline-result-grid">
                                        <div className="data-row">
                                          <span>Area source</span>
                                          <strong>
                                            {usesAutomaticActivityAreas
                                              ? "automatic activity areas"
                                            : "user Zones"}
                                          </strong>
                                        </div>
                                        <div className="data-row">
                                          <span>Session key</span>
                                          <strong>{motionResult.session_key ?? "none"}</strong>
                                        </div>
                                        <div className="data-row">
                                          <span>Quiet period</span>
                                          <strong>
                                            {motionResult.quiet_period_seconds} seconds
                                          </strong>
                                        </div>
                                        <div className="data-row">
                                          <span>Cooldown</span>
                                          <strong>{motionResult.cooldown_seconds} seconds</strong>
                                        </div>
                                        <div className="data-row">
                                          <span>Max snapshots</span>
                                          <strong>
                                            {motionResult.max_snapshots_per_session}
                                          </strong>
                                        </div>
                                        {motionResult.existing_activity_reference ? (
                                          <div className="data-row">
                                            <span>Existing activity</span>
                                            <strong>
                                              {motionResult.existing_activity_reference}
                                            </strong>
                                          </div>
                                        ) : null}
                                        {motionCropPlan ? (
                                          <>
                                            <div className="data-row">
                                              <span>Crop reason</span>
                                              <strong>{formatLabel(motionCropPlan.crop_reason)}</strong>
                                            </div>
                                            <div className="data-row">
                                              <span>Crop pixels</span>
                                              <strong>
                                                {motionCropPlan.crop_box_pixels.left},
                                                {motionCropPlan.crop_box_pixels.top}-
                                                {motionCropPlan.crop_box_pixels.right},
                                                {motionCropPlan.crop_box_pixels.bottom} ·{" "}
                                                {motionCropPlan.crop_box_pixels.width}x
                                                {motionCropPlan.crop_box_pixels.height}
                                              </strong>
                                            </div>
                                            <div className="data-row">
                                              <span>Crop normalized</span>
                                              <strong>
                                                {motionCropPlan.crop_box_normalized.left.toFixed(3)}
                                                ,
                                                {motionCropPlan.crop_box_normalized.top.toFixed(3)}
                                                -
                                                {motionCropPlan.crop_box_normalized.right.toFixed(3)}
                                                ,
                                                {motionCropPlan.crop_box_normalized.bottom.toFixed(3)}
                                              </strong>
                                            </div>
                                            <div className="data-row">
                                              <span>Crop padding</span>
                                              <strong>{motionCropPlan.padding_ratio}</strong>
                                            </div>
                                            <div className="data-row">
                                              <span>Derived crop media</span>
                                              <strong>
                                                {motionCropPlan.derived_crop_media_asset_id ?? "not created"}
                                              </strong>
                                            </div>
                                          </>
                                        ) : null}
                                        <div className="data-row">
                                          <span>MediaAsset IDs</span>
                                          <strong>{motionResult.media_asset_ids.join(", ")}</strong>
                                        </div>
                                        {motionResult.activity_areas.map((area) => (
                                          <div
                                            className="data-row"
                                            key={`motion-area-${stream.id}-${area.area_id}`}
                                          >
                                            <span>{area.label}</span>
                                            <strong>
                                              {area.area_id}
                                              {area.cell_ids.length > 0
                                                ? ` · ${area.cell_ids.length} cells`
                                                : ""}
                                            </strong>
                                          </div>
                                        ))}
                                        {motionResult.debug_cell_zones.length > 0 ? (
                                          <div className="data-row">
                                            <span>Raw cell count</span>
                                            <strong>
                                              {motionResult.debug_cell_zones.length}
                                            </strong>
                                          </div>
                                        ) : null}
                                        <div className="data-row">
                                          <span>Candidate count</span>
                                          <strong>{motionResult.candidates.length}</strong>
                                        </div>
                                        {motionResult.frame_scores.map((score) => (
                                          <div
                                            className="data-row"
                                            key={`motion-frame-${stream.id}-${score.frame_index}`}
                                          >
                                            <span>Frame {score.frame_index}</span>
                                            <strong>
                                              {score.triggered_zone_ids.length > 0
                                                ? score.triggered_zone_ids.join(", ")
                                                : "no triggered zones"}{" "}
                                              ·{" "}
                                              {Math.round(score.strongest_changed_ratio * 1000) /
                                                10}
                                              %
                                            </strong>
                                          </div>
                                        ))}
                                        {motionResult.candidates.map((candidate) => (
                                          <div
                                            className="data-row"
                                            key={`motion-candidate-${stream.id}-${candidate.zone_id}-${candidate.start_frame_index}`}
                                          >
                                            <span>{candidate.zone_id}</span>
                                            <strong>
                                              {candidate.start_frame_index}-
                                              {candidate.end_frame_index}, best{" "}
                                              {candidate.best_frame_index},{" "}
                                              {Math.round(candidate.peak_changed_ratio * 1000) /
                                                10}
                                              %
                                            </strong>
                                          </div>
                                        ))}
                                        {motionResult.created_evidence.map((evidence) => (
                                          <div
                                            className="data-row"
                                            key={`motion-created-${evidence.id}`}
                                          >
                                            <span>MotionEvidence</span>
                                            <strong>
                                              {evidence.id} · {formatLabel(evidence.status)}
                                            </strong>
                                          </div>
                                        ))}
                                      </div>
                                    </details>
                                  </div>
                                ) : null}
                              </div>
                            ) : null}
                            <div className="timeline-media-list">
                              {streamMediaAssets.map((asset) => {
                                const actionState = timelineActionState[asset.id] ?? {};
                                const eligibleImage = isImageMedia(asset);
                                const lifecycleSummary = buildMediaLifecycleSummary(
                                  asset,
                                  timelineDetectionRuns,
                                  timelineDetectionProposals,
                                  timelineMotionEvidence,
                                  timelineReviewLabels,
                                );
                                const proposal =
                                  actionState.proposalResult?.proposals[0] ??
                                  lifecycleSummary.proposals.find(
                                    (item) => item.status === "proposed",
                                  ) ??
                                  null;
                                const canConvertProposal =
                                  Boolean(proposal) && !actionState.proposalDecisionResult;
                                const pendingLifecycleEvidence =
                                  lifecycleSummary.motionEvidence.find(
                                    (item) => item.status === "pending",
                                  ) ?? null;
                                const promotableEvidenceId =
                                  actionState.evidenceResult?.status === "pending"
                                    ? actionState.evidenceResult.motion_evidence_id
                                    : pendingLifecycleEvidence?.id;
                                const canPromoteEvidence = Boolean(promotableEvidenceId);
                                const blocksNewMotionEvidence =
                                  lifecycleSummary.hasPendingMotionEvidence ||
                                  lifecycleSummary.hasPromotedMotionEvidence;
                                const latestProposal = lifecycleSummary.proposals[0] ?? null;
                                const latestRun = lifecycleSummary.detectionRuns[0] ?? null;
                                const latestEvidence = lifecycleSummary.motionEvidence[0] ?? null;
                                const showLocalDetectorPanel =
                                  eligibleImage &&
                                  (Boolean(localDetectorAdapter) ||
                                    Boolean(localDetectorAdapterError) ||
                                    isLoadingLocalDetectorAdapter);
                                const localDetectorCanRun =
                                  canRunModelAdapter(localDetectorAdapter);
                                const localDetectorSupportsAsset =
                                  modelAdapterSupportsMedia(localDetectorAdapter, asset);
                                const savedImageStatus = savedImageStatusLabel(lifecycleSummary);
                                return (
                                  <section className="timeline-media-item" key={asset.id}>
                                    <div className="item-title-row">
                                      <div>
                                        <strong>
                                          {mediaProvenanceHint(asset).includes("external_url")
                                            ? "Snapshot"
                                            : asset.original_filename || asset.filename}
                                        </strong>
                                        <span className="meta-text">
                                          {asset.original_filename || asset.filename}
                                        </span>
                                      </div>
                                      <StatusPill
                                        label={eligibleImage ? savedImageStatus : "Context only"}
                                        tone={
                                          eligibleImage
                                            ? savedImageStatusTone(lifecycleSummary)
                                            : "quiet"
                                        }
                                      />
                                    </div>
                                    <div className="source-connection-meta">
                                      <span>Content: {asset.content_type}</span>
                                      <span>Size: {formatBytes(asset.file_size_bytes)}</span>
                                      <span>Captured: {formatDateTime(asset.created_at)}</span>
                                      <span>
                                        Source:{" "}
                                        {sources.find((source) => source.id === asset.source_id)
                                          ?.name ??
                                          asset.source_id ??
                                          "none"}
                                      </span>
                                      <span>Stream: {stream.name}</span>
                                      <span>Origin: {mediaProvenanceHint(asset)}</span>
                                    </div>
                                    {asset.notes ? (
                                      <p className="meta-text">{asset.notes}</p>
                                    ) : null}
                                    <div className="timeline-lifecycle-panel">
                                      <div className="item-title-row">
                                        <strong>Image status</strong>
                                        <StatusPill
                                          label={
                                            isLoadingTimelineLifecycle
                                              ? "Loading"
                                              : savedImageStatus
                                          }
                                          tone={savedImageStatusTone(lifecycleSummary)}
                                        />
                                      </div>
                                      {timelineLifecycleError ? (
                                        <div className="zone-error">
                                          {timelineLifecycleError}
                                        </div>
                                      ) : null}
                                      <div className="timeline-lifecycle-grid">
                                        <div className="data-row">
                                          <span>Analysis</span>
                                          <strong>{lifecycleSummary.proposalStatusText}</strong>
                                        </div>
                                        <div className="data-row">
                                          <span>Analysis run</span>
                                          <strong>{lifecycleSummary.detectionRunText}</strong>
                                        </div>
                                        <div className="data-row">
                                          <span>Review context</span>
                                          <strong>{lifecycleSummary.motionEvidenceText}</strong>
                                        </div>
                                        <div className="data-row">
                                          <span>Review item</span>
                                          <strong>{lifecycleSummary.promotedText}</strong>
                                        </div>
                                        <div className="data-row">
                                          <span>Correction</span>
                                          <strong>{lifecycleSummary.reviewTruthText}</strong>
                                        </div>
                                        <div className="data-row">
                                          <span>Export</span>
                                          <strong>{lifecycleSummary.exportReadinessText}</strong>
                                        </div>
                                        <div className="data-row">
                                          <span>Next</span>
                                          <strong>{savedImageNextAction(lifecycleSummary)}</strong>
                                        </div>
                                      </div>
                                      {latestProposal || latestRun || latestEvidence ? (
                                        <details className="advanced-details">
                                          <summary>Advanced status details</summary>
                                          <div className="timeline-lifecycle-grid">
                                            {latestProposal ? (
                                              <div className="data-row">
                                                <span>Latest proposal</span>
                                                <strong>
                                                  {latestProposal.id} · {latestProposal.label} ·{" "}
                                                  {Math.round(latestProposal.confidence * 100)}% ·{" "}
                                                  {formatLabel(latestProposal.status)}
                                                </strong>
                                              </div>
                                            ) : null}
                                            {latestRun ? (
                                              <div className="data-row">
                                                <span>Latest run</span>
                                                <strong>
                                                  {latestRun.id} · {formatLabel(latestRun.source)} ·{" "}
                                                  {formatLabel(latestRun.status)}
                                                </strong>
                                              </div>
                                            ) : null}
                                            {latestEvidence ? (
                                              <div className="data-row">
                                                <span>Latest MotionEvidence</span>
                                                <strong>
                                                  {latestEvidence.id} ·{" "}
                                                  {formatLabel(latestEvidence.status)}
                                                </strong>
                                              </div>
                                            ) : null}
                                          </div>
                                        </details>
                                      ) : null}
                                      <div className="detail-actions timeline-lifecycle-actions">
                                        {latestProposal ? (
                                          <button
                                            className="secondary-action"
                                            onClick={onOpenDetectionProposals}
                                            type="button"
                                          >
                                            Review suggestions
                                          </button>
                                        ) : null}
                                        {latestEvidence ? (
                                          <button
                                            className="secondary-action"
                                            onClick={() => onOpenMotionEvidence(latestEvidence.id)}
                                            type="button"
                                          >
                                            Open review context
                                          </button>
                                        ) : null}
                                        {lifecycleSummary.eventIds.slice(0, 2).map((eventId) => (
                                          <button
                                            className="inline-link-button"
                                            key={eventId}
                                            onClick={() => onOpenEvent(eventId)}
                                            type="button"
                                          >
                                            Event {eventId}
                                          </button>
                                        ))}
                                        {lifecycleSummary.visitIds.slice(0, 2).map((visitId) => (
                                          <button
                                            className="inline-link-button"
                                            key={visitId}
                                            onClick={() => onOpenVisit(visitId)}
                                            type="button"
                                          >
                                            Visit {visitId}
                                          </button>
                                        ))}
                                        {lifecycleSummary.eventIds.length > 0 ||
                                        lifecycleSummary.visitIds.length > 0 ? (
                                          <button
                                            className="secondary-action"
                                            onClick={onOpenReview}
                                            type="button"
                                          >
                                            Review item
                                          </button>
                                        ) : null}
                                        {lifecycleSummary.truthLabels.length > 0 ? (
                                          <button
                                            className="secondary-action"
                                            onClick={onOpenExports}
                                            type="button"
                                          >
                                            Export reviewed data
                                          </button>
                                        ) : null}
                                      </div>
                                    </div>
                                    {showLocalDetectorPanel ? (
                                      <div className="timeline-detector-panel">
                                        <div className="item-title-row">
                                          <div>
                                            <strong>Analyze image</strong>
                                            <p className="meta-text">
                                              Run a configured local model explicitly, or use the
                                              demo suggestion fallback for testing.
                                            </p>
                                          </div>
                                          <StatusPill
                                            label={
                                              isLoadingLocalDetectorAdapter
                                                ? "Loading"
                                                : localDetectorAdapter
                                                  ? formatLabel(localDetectorAdapter.status)
                                                  : "Unavailable"
                                            }
                                            tone={modelAdapterTone(localDetectorAdapter?.status)}
                                          />
                                        </div>
                                        {localDetectorAdapterError && !localDetectorAdapter ? (
                                          <div className="zone-error">
                                            Local detector readiness could not be loaded:{" "}
                                            {localDetectorAdapterError}. Demo suggestions remain
                                            available.
                                          </div>
                                        ) : null}
                                        {localDetectorAdapter ? (
                                          <>
                                            <details className="advanced-details">
                                              <summary>Advanced detector details</summary>
                                              <div className="timeline-detector-grid">
                                              <div className="data-row">
                                                <span>Adapter</span>
                                                <strong>
                                                  {localDetectorAdapter.name} (
                                                  {localDetectorAdapter.id})
                                                </strong>
                                              </div>
                                              <div className="data-row">
                                                <span>Can run</span>
                                                <strong>
                                                  {localDetectorCanRun ? "Yes" : "No"}
                                                </strong>
                                              </div>
                                              <div className="data-row">
                                                <span>Local only</span>
                                                <strong>
                                                  {localDetectorAdapter.local_only ? "Yes" : "No"}
                                                </strong>
                                              </div>
                                              <div className="data-row">
                                                <span>Creates truth</span>
                                                <strong>
                                                  {localDetectorAdapter.creates_review_truth
                                                    ? "Yes"
                                                    : "No"}
                                                </strong>
                                              </div>
                                              <div className="data-row">
                                                <span>Model path</span>
                                                <strong>
                                                  {localDetectorAdapter.configuration_status
                                                    ?.model_path_configured
                                                    ? "Configured"
                                                    : "Not configured"}
                                                </strong>
                                              </div>
                                              <div className="data-row">
                                                <span>Runtime</span>
                                                <strong>
                                                  {localDetectorAdapter.configuration_status
                                                    ?.runtime_available
                                                    ? "Available"
                                                    : "Unavailable"}
                                                </strong>
                                              </div>
                                              <div className="data-row">
                                                <span>Media support</span>
                                                <strong>
                                                  {localDetectorSupportsAsset
                                                    ? "This image is supported"
                                                    : "Unsupported media"}
                                                </strong>
                                              </div>
                                              </div>
                                            </details>
                                            <span className="meta-text">
                                              {localDetectorReadinessCopy(localDetectorAdapter)}
                                            </span>
                                            {!localDetectorCanRun ? (
                                              <span className="meta-text">
                                                Use demo analysis for smoke testing, or configure
                                                the local model path to run real local suggestions.
                                              </span>
                                            ) : null}
                                            <div className="detail-actions">
                                              <button
                                                className="primary-action"
                                                disabled={
                                                  actionState.isRunningLocalDetector ||
                                                  !localDetectorCanRun ||
                                                  !localDetectorSupportsAsset
                                                }
                                                onClick={() => void handleRunLocalDetector(asset)}
                                                type="button"
                                              >
                                                {actionState.isRunningLocalDetector
                                                  ? "Analyzing..."
                                                  : "Analyze image"}
                                              </button>
                                              <button
                                                className="secondary-action"
                                                onClick={onOpenDetectionProposals}
                                                type="button"
                                              >
                                                Review suggestion
                                              </button>
                                              <button
                                                className="secondary-action"
                                                onClick={onOpenReview}
                                                type="button"
                                              >
                                                Review
                                              </button>
                                            </div>
                                          </>
                                        ) : null}
                                        {actionState.localDetectorError ? (
                                          <div className="zone-error">
                                            {actionState.localDetectorError}
                                          </div>
                                        ) : null}
                                        {actionState.localDetectorResult ? (
                                          <div className="timeline-result-grid">
                                            <div className="data-row">
                                              <span>Suggested label</span>
                                              <strong>
                                                {actionState.localDetectorResult.proposals.length >
                                                0
                                                  ? actionState.localDetectorResult.proposals
                                                      .map(
                                                        (item) =>
                                                          `${formatLabel(item.label)} (${Math.round(
                                                            item.confidence * 100,
                                                          )}%)`,
                                                      )
                                                      .join(", ")
                                                  : "none"}
                                              </strong>
                                            </div>
                                            <div className="data-row">
                                              <span>Local model</span>
                                              <strong>
                                                {actionState.localDetectorResult.adapter.name}
                                              </strong>
                                            </div>
                                            <div className="data-row">
                                              <span>Review status</span>
                                              <strong>
                                                {
                                                  actionState.localDetectorResult
                                                    .review_queue_count
                                                }{" "}
                                                items need review
                                              </strong>
                                            </div>
                                            <div className="data-row">
                                              <span>Reviewed data created</span>
                                              <strong>No</strong>
                                            </div>
                                          </div>
                                        ) : null}
                                        {actionState.localDetectorResult ? (
                                          <div className="detail-actions">
                                            <button
                                              className="primary-action"
                                              onClick={onOpenDetectionProposals}
                                              type="button"
                                            >
                                              Review suggestion
                                            </button>
                                            <button
                                              className="secondary-action"
                                              onClick={onOpenReview}
                                              type="button"
                                            >
                                              Correct label
                                            </button>
                                            <button
                                              className="secondary-action"
                                              onClick={onOpenBirdLog}
                                              type="button"
                                            >
                                              Bird Log
                                            </button>
                                          </div>
                                        ) : null}
                                        {actionState.localDetectorResult ? (
                                          <details className="advanced-details">
                                            <summary>Advanced analysis details</summary>
                                            <div className="timeline-result-grid">
                                              <div className="data-row">
                                                <span>DetectionRun</span>
                                                <strong>
                                                  {
                                                    actionState.localDetectorResult.detection_run
                                                      .id
                                                  }
                                                </strong>
                                              </div>
                                              <div className="data-row">
                                                <span>Adapter</span>
                                                <strong>
                                                  {actionState.localDetectorResult.adapter.name} (
                                                  {actionState.localDetectorResult.adapter.id})
                                                </strong>
                                              </div>
                                              <div className="data-row">
                                                <span>Proposals</span>
                                                <strong>
                                                  {actionState.localDetectorResult.proposals.length >
                                                  0
                                                    ? actionState.localDetectorResult.proposals
                                                        .map((item) => item.id)
                                                        .join(", ")
                                                    : "none"}
                                                </strong>
                                              </div>
                                              <div className="data-row">
                                                <span>Review Queue</span>
                                                <strong>
                                                  {
                                                    actionState.localDetectorResult
                                                      .review_queue_count
                                                  }{" "}
                                                  needs review
                                                </strong>
                                              </div>
                                              {actionState.localDetectorResult.proposals.map(
                                                (item) => (
                                                  <div className="data-row" key={item.id}>
                                                    <span>{item.id}</span>
                                                    <strong>
                                                      {item.label} /{" "}
                                                      {Math.round(item.confidence * 100)}% /{" "}
                                                      {formatLabel(item.status)}
                                                    </strong>
                                                  </div>
                                                ),
                                              )}
                                              <div className="data-row">
                                                <span>Local note</span>
                                                <strong>
                                                  {
                                                    actionState.localDetectorResult
                                                      .local_first_note
                                                  }
                                                </strong>
                                              </div>
                                            </div>
                                          </details>
                                        ) : null}
                                      </div>
                                    ) : null}
                                    <div className="detail-actions">
                                      <a
                                        className="inline-link"
                                        href={apiClient.mediaFileUrl(asset.id)}
                                        rel="noreferrer"
                                        target="_blank"
                                      >
                                        Open image
                                      </a>
                                      <button
                                        className="secondary-action"
                                        disabled={
                                          !eligibleImage ||
                                          actionState.isCreatingProposal ||
                                          actionState.isConvertingProposal
                                        }
                                        onClick={() => void handleCreateTimelineProposal(asset)}
                                        type="button"
                                      >
                                        {actionState.isCreatingProposal
                                          ? "Analyzing..."
                                          : lifecycleSummary.proposals.length > 0
                                            ? "Analyze again (demo)"
                                            : "Analyze image (demo)"}
                                      </button>
                                      {canConvertProposal ? (
                                        <button
                                          className="secondary-action"
                                          disabled={actionState.isConvertingProposal}
                                          onClick={() => void handleConvertTimelineProposal(asset)}
                                          type="button"
                                        >
                                          {actionState.isConvertingProposal
                                            ? "Sending..."
                                            : "Send suggestion to Review"}
                                        </button>
                                      ) : null}
                                      <button
                                        className="secondary-action"
                                        disabled={
                                          !eligibleImage ||
                                          !selectedTimelineZoneId ||
                                          actionState.isCreatingEvidence ||
                                          blocksNewMotionEvidence
                                        }
                                        onClick={() => void handleCreateTimelineEvidence(asset)}
                                        type="button"
                                      >
                                        {actionState.isCreatingEvidence
                                          ? "Creating..."
                                          : lifecycleSummary.hasPendingMotionEvidence
                                            ? "Pending review context exists"
                                            : lifecycleSummary.hasPromotedMotionEvidence
                                              ? "Review context exists"
                                              : "Create review context"}
                                      </button>
                                      <button
                                        className="secondary-action"
                                        onClick={onOpenDetectionProposals}
                                        type="button"
                                      >
                                        Review suggestion
                                      </button>
                                      <button
                                        className="secondary-action"
                                        onClick={onOpenReview}
                                        type="button"
                                      >
                                        Review
                                      </button>
                                      <button
                                        className="secondary-action"
                                        onClick={onOpenBirdLog}
                                        type="button"
                                      >
                                        Bird Log
                                      </button>
                                      <button
                                        className="secondary-action"
                                        onClick={onOpenExports}
                                        type="button"
                                      >
                                        Export reviewed data
                                      </button>
                                    </div>
                                    {actionState.proposalMessage ? (
                                      <div className="notice-panel compact-notice">
                                        {actionState.proposalMessage}
                                      </div>
                                    ) : null}
                                    {actionState.proposalError ? (
                                      <div className="zone-error">
                                        {actionState.proposalError}
                                      </div>
                                    ) : null}
                                    {actionState.proposalResult ? (
                                      <div className="timeline-result-grid">
                                        <div className="data-row">
                                          <span>Suggested labels</span>
                                          <strong>
                                            {actionState.proposalResult.proposals.length > 0
                                              ? actionState.proposalResult.proposals
                                                  .map((item) => item.label)
                                                  .join(", ")
                                              : "none"}
                                          </strong>
                                        </div>
                                        <div className="data-row">
                                          <span>Review status</span>
                                          <strong>
                                            {actionState.proposalResult.review_queue_count} items
                                            need review
                                          </strong>
                                        </div>
                                        <div className="data-row">
                                          <span>Reviewed data created</span>
                                          <strong>No</strong>
                                        </div>
                                      </div>
                                    ) : null}
                                    {actionState.proposalResult ? (
                                      <details className="advanced-details">
                                        <summary>Advanced analysis details</summary>
                                        <div className="timeline-result-grid">
                                          <div className="data-row">
                                            <span>DetectionRun</span>
                                            <strong>
                                              {actionState.proposalResult.detection_run.id}
                                            </strong>
                                          </div>
                                          <div className="data-row">
                                            <span>Proposals</span>
                                            <strong>
                                              {actionState.proposalResult.proposals.length > 0
                                                ? actionState.proposalResult.proposals
                                                    .map((item) => item.id)
                                                    .join(", ")
                                                : "none"}
                                            </strong>
                                          </div>
                                          <div className="data-row">
                                            <span>Review Queue</span>
                                            <strong>
                                              {actionState.proposalResult.review_queue_count} needs
                                              review
                                            </strong>
                                          </div>
                                          {actionState.proposalResult.proposals.map((item) => (
                                            <div className="data-row" key={item.id}>
                                              <span>{item.id}</span>
                                              <strong>
                                                {item.label} /{" "}
                                                {Math.round(item.confidence * 100)}% /{" "}
                                                {formatLabel(item.status)}
                                              </strong>
                                            </div>
                                          ))}
                                        </div>
                                      </details>
                                    ) : null}
                                    {actionState.proposalDecisionResult ? (
                                      <div className="timeline-result-grid">
                                        <div className="data-row">
                                          <span>Review item</span>
                                          <strong>
                                            {actionState.proposalDecisionResult.visit
                                              ? "Visit ready for correction"
                                              : actionState.proposalDecisionResult.event
                                                ? "Event ready for correction"
                                                : "Not created"}
                                          </strong>
                                        </div>
                                        <div className="data-row">
                                          <span>Next</span>
                                          <strong>Review item</strong>
                                        </div>
                                        <div className="data-row">
                                          <span>Reviewed data created</span>
                                          <strong>No</strong>
                                        </div>
                                      </div>
                                    ) : null}
                                    {actionState.proposalDecisionResult ? (
                                      <details className="advanced-details">
                                        <summary>Advanced review item details</summary>
                                        <div className="timeline-result-grid">
                                          <div className="data-row">
                                            <span>Converted proposal</span>
                                            <strong>
                                              {actionState.proposalDecisionResult.proposal.id}
                                            </strong>
                                          </div>
                                          <div className="data-row">
                                            <span>Event</span>
                                            {actionState.proposalDecisionResult.event ? (
                                              <button
                                                className="inline-link-button"
                                                onClick={() =>
                                                  onOpenEvent(
                                                    actionState.proposalDecisionResult!.event!.id,
                                                  )
                                                }
                                                type="button"
                                              >
                                                {actionState.proposalDecisionResult.event.id}
                                              </button>
                                            ) : (
                                              <strong>not created</strong>
                                            )}
                                          </div>
                                          <div className="data-row">
                                            <span>Visit</span>
                                            {actionState.proposalDecisionResult.visit ? (
                                              <button
                                                className="inline-link-button"
                                                onClick={() =>
                                                  onOpenVisit(
                                                    actionState.proposalDecisionResult!.visit!.id,
                                                  )
                                                }
                                                type="button"
                                              >
                                                {actionState.proposalDecisionResult.visit.id}
                                              </button>
                                            ) : (
                                              <strong>not created</strong>
                                            )}
                                          </div>
                                        </div>
                                      </details>
                                    ) : null}
                                    {actionState.evidenceError ? (
                                      <div className="zone-error">{actionState.evidenceError}</div>
                                    ) : null}
                                    {actionState.evidenceResult ? (
                                      <div className="timeline-result-grid">
                                        <div className="data-row">
                                          <span>Review context</span>
                                          <button
                                            className="inline-link-button"
                                            onClick={() =>
                                              onOpenMotionEvidence(
                                                actionState.evidenceResult!.motion_evidence_id,
                                              )
                                            }
                                            type="button"
                                          >
                                            Open details
                                          </button>
                                        </div>
                                        <div className="data-row">
                                          <span>Status</span>
                                          <strong>
                                            {formatLabel(actionState.evidenceResult.status)}
                                          </strong>
                                        </div>
                                        <div className="data-row">
                                          <span>Zone</span>
                                          <strong>
                                            {actionState.evidenceResult.zone_id ?? "none"}
                                          </strong>
                                        </div>
                                      </div>
                                    ) : null}
                                    {canPromoteEvidence ? (
                                      <div className="detail-actions">
                                        <button
                                          className="primary-action"
                                          disabled={actionState.isPromotingEvidence}
                                          onClick={() =>
                                            void handlePromoteTimelineEvidence(
                                              asset,
                                              promotableEvidenceId,
                                            )
                                          }
                                          type="button"
                                        >
                                          {actionState.isPromotingEvidence
                                            ? "Creating review item..."
                                            : "Create review item"}
                                        </button>
                                      </div>
                                    ) : null}
                                    {actionState.promotionError ? (
                                      <div className="zone-error">
                                        {actionState.promotionError}
                                      </div>
                                    ) : null}
                                    {actionState.promotionResult ? (
                                      <div className="timeline-result-grid">
                                        <div className="data-row">
                                          <span>Review item</span>
                                          {actionState.promotionResult.event_id ? (
                                            <button
                                              className="inline-link-button"
                                              onClick={() =>
                                                onOpenEvent(actionState.promotionResult!.event_id!)
                                              }
                                              type="button"
                                            >
                                              {actionState.promotionResult.event_id}
                                            </button>
                                          ) : (
                                            <strong>not created</strong>
                                          )}
                                        </div>
                                        <div className="data-row">
                                          <span>Visit</span>
                                          {actionState.promotionResult.visit_id ? (
                                            <button
                                              className="inline-link-button"
                                              onClick={() =>
                                                onOpenVisit(actionState.promotionResult!.visit_id!)
                                              }
                                              type="button"
                                            >
                                              {actionState.promotionResult.visit_id}
                                            </button>
                                          ) : (
                                            <strong>not created</strong>
                                          )}
                                        </div>
                                      </div>
                                    ) : null}
                                    <div className="notice-panel compact-notice import-smoke-boundary">
                                      <strong>Truth boundary</strong>
                                      <ul>
                                        <li>Saved images are local review context.</li>
                                        <li>Demo analysis creates test-only suggested labels.</li>
                                        <li>
                                          Local model analysis runs only when you click Analyze
                                          image.
                                        </li>
                                        <li>
                                          Reviewed data only happens through explicit Review
                                          correction.
                                        </li>
                                      </ul>
                                    </div>
                                  </section>
                                );
                              })}
                            </div>
                          </>
                        ) : (
                          <div className="timeline-empty-state">
                            No saved images for this stream yet. Test and capture a snapshot or
                            import an image.
                          </div>
                        )}
                      </div>
                    </section>
                  );
                })
              ) : (
                <EmptyState
                  title="No Streams for this Source"
                  description="Add Stream metadata before drawing Zones or reviewing activity."
                />
              )}
            </div>
          </section>
        </section>
      ) : (
        <EmptyState
          title="No Sources available"
          description="Create a Source before configuring provider actions."
        />
      )}
    </div>
  );
}
