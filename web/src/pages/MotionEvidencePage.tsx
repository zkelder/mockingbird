import { useEffect, useMemo, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type {
  CameraSource,
  MediaAsset,
  MotionEvidence,
  MotionEvidenceBulkAction,
  MotionEvidenceBulkActionResponse,
  MotionEvidenceCreateRequest,
  MotionEvidencePromoteResponse,
  MotionEvidenceStatus,
  MotionEvaluateSequenceRequest,
  MotionEvaluateSequenceResponse,
  Stream,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { EvidenceBadge } from "../components/EvidenceBadge";
import { MediaAssetPreview } from "../components/MediaAssetPreview";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel, mergeMediaAssets } from "../utils";

type MotionEvidenceFilter = "all" | MotionEvidenceStatus;

const statusFilters: Array<{ value: MotionEvidenceFilter; label: string }> = [
  { value: "pending", label: "Pending" },
  { value: "promoted", label: "Promoted" },
  { value: "ignored", label: "Ignored" },
  { value: "all", label: "All" },
];

const motionSampleFrames = `[
  [
    [0, 0, 0],
    [0, 0, 0],
    [0, 0, 0]
  ],
  [
    [0, 0, 0],
    [0, 255, 0],
    [0, 0, 0]
  ],
  [
    [0, 0, 0],
    [0, 255, 0],
    [0, 0, 0]
  ]
]`;

const noMotionSampleFrames = `[
  [
    [0, 0, 0],
    [0, 0, 0],
    [0, 0, 0]
  ],
  [
    [0, 0, 0],
    [0, 0, 0],
    [0, 0, 0]
  ],
  [
    [0, 0, 0],
    [0, 0, 0],
    [0, 0, 0]
  ]
]`;

const motionWorkflowSteps = [
  "Create or evaluate motion evidence",
  "Attach existing local media",
  "Promote useful evidence",
  "Review/correct for truth",
];

const pendingEvidenceBoundaryCopy =
  "This is pending evidence. It is not an Event, Visit, label, or truth.";
const pendingWebhookEvidenceBoundaryCopy =
  "This is pending evidence from webhook metadata. It is not an Event, Visit, label, or truth.";
const pendingFolderEvidenceBoundaryCopy =
  "This is pending evidence from imported local media. It is not an Event, Visit, label, or truth.";
const promotedEvidenceBoundaryCopy =
  "Promoted evidence created a reviewable Event/Visit. Correction remains the truth boundary.";

interface WebhookEvidenceProvenance {
  isWebhook: boolean;
  providerKey: string | null;
  candidateType: string | null;
  externalEventId: string | null;
  externalLabel: string | null;
  externalConfidence: string | null;
  externalTimestamp: string | null;
}

/**
 * Remaining Performance P1 Closure v1 (P1-7): how many recent MediaAssets
 * the "attach existing media" pickers offer. Assets this page's evidence
 * actually references are hydrated separately and merged in, so nothing
 * the page needs to resolve depends on falling inside this window.
 */
const MEDIA_PICKER_WINDOW = 100;

interface MotionEvidencePageProps {
  streams: Stream[];
  sources: CameraSource[];
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenMotionEvidence: (motionEvidenceId: string) => void;
  onOpenReview: () => void;
  onEvidenceChanged: () => Promise<void>;
}

export function MotionEvidencePage({
  streams,
  sources,
  onOpenEvent,
  onOpenVisit,
  onOpenMotionEvidence,
  onOpenReview,
  onEvidenceChanged,
}: MotionEvidencePageProps) {
  const [evidence, setEvidence] = useState<MotionEvidence[]>([]);
  const [mediaAssets, setMediaAssets] = useState<MediaAsset[]>([]);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [selectedBulkEvidenceIds, setSelectedBulkEvidenceIds] = useState<string[]>([]);
  const [statusFilter, setStatusFilter] = useState<MotionEvidenceFilter>("pending");
  const [zoneFilter, setZoneFilter] = useState("");
  const [manualZoneId, setManualZoneId] = useState("zone-feeder");
  const [manualSourceId, setManualSourceId] = useState("");
  const [manualStreamId, setManualStreamId] = useState("");
  const [manualPeakChangedRatio, setManualPeakChangedRatio] = useState("42%");
  const [manualTriggeredFrameCount, setManualTriggeredFrameCount] = useState("2");
  const [manualStartFrameIndex, setManualStartFrameIndex] = useState("10");
  const [manualEndFrameIndex, setManualEndFrameIndex] = useState("12");
  const [manualBestFrameIndex, setManualBestFrameIndex] = useState("11");
  const [manualSnapshotMediaAssetId, setManualSnapshotMediaAssetId] = useState("");
  const [manualNotes, setManualNotes] = useState("Manual evidence candidate before stream sampling.");
  const [manualScoringConfig, setManualScoringConfig] = useState(
    '{\n  "source": "manual-ui",\n  "phase": "8H"\n}',
  );
  const [sampleSourceId, setSampleSourceId] = useState("");
  const [sampleStreamId, setSampleStreamId] = useState("");
  const [sampleZoneId, setSampleZoneId] = useState("zone-feeder");
  const [sampleZoneLeft, setSampleZoneLeft] = useState("0.34");
  const [sampleZoneTop, setSampleZoneTop] = useState("0.34");
  const [sampleZoneRight, setSampleZoneRight] = useState("0.67");
  const [sampleZoneBottom, setSampleZoneBottom] = useState("0.67");
  const [samplePixelDeltaThreshold, setSamplePixelDeltaThreshold] = useState("25");
  const [sampleMinChangedRatio, setSampleMinChangedRatio] = useState("0.2");
  const [sampleMinTriggeredFrames, setSampleMinTriggeredFrames] = useState("1");
  const [sampleMaxGapFrames, setSampleMaxGapFrames] = useState("1");
  const [sampleFrameIndexStart, setSampleFrameIndexStart] = useState("0");
  const [sampleCreateMotionEvidence, setSampleCreateMotionEvidence] = useState(false);
  const [sampleNotes, setSampleNotes] = useState(
    "Sampled frame harness candidate before real stream sampling.",
  );
  const [sampleFramesJson, setSampleFramesJson] = useState(motionSampleFrames);
  const [sampleResult, setSampleResult] = useState<MotionEvaluateSequenceResponse | null>(null);
  const [eventTitle, setEventTitle] = useState("");
  const [visitLabelHint, setVisitLabelHint] = useState("unknown_animal");
  const [promotionNotes, setPromotionNotes] = useState("");
  const [attachMediaAssetId, setAttachMediaAssetId] = useState("");
  const [lastPromotion, setLastPromotion] = useState<MotionEvidencePromoteResponse | null>(null);
  const [lastBulkPromotion, setLastBulkPromotion] =
    useState<MotionEvidenceBulkActionResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [isEvaluatingSample, setIsEvaluatingSample] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Advanced/developer surface, but `motion_evidence` rows also accumulate
  // from ordinary live-camera monitoring (see `_evaluate_live_stream_motion`),
  // so this list is not bounded by developer-tool usage alone. Render cap
  // only, mirroring StreamDetailPage's "Show more events" convention -- all
  // evidence is already fetched either way, and bulk selection below still
  // operates over the full filtered set, not just what's rendered.
  const [visibleEvidenceCount, setVisibleEvidenceCount] = useState(15);

  const sourceById = useMemo(() => new Map(sources.map((source) => [source.id, source])), [sources]);
  const streamById = useMemo(() => new Map(streams.map((stream) => [stream.id, stream])), [streams]);
  const evidenceById = useMemo(() => new Map(evidence.map((item) => [item.id, item])), [evidence]);
  const mediaById = useMemo(
    () => new Map(mediaAssets.map((asset) => [asset.id, asset])),
    [mediaAssets],
  );
  const zoneFilteredEvidence = useMemo(
    () =>
      evidence.filter((item) =>
        zoneFilter.trim()
          ? (item.zone_id ?? "automatic activity area")
              .toLowerCase()
              .includes(zoneFilter.trim().toLowerCase())
          : true,
      ),
    [evidence, zoneFilter],
  );
  const sortedEvidence = useMemo(() => {
    const statusFiltered =
      statusFilter === "all"
        ? zoneFilteredEvidence
        : zoneFilteredEvidence.filter((item) => item.status === statusFilter);
    return [...statusFiltered].sort(
      (left, right) =>
        new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
    );
  }, [statusFilter, zoneFilteredEvidence]);
  const selectablePendingEvidence = useMemo(
    () => sortedEvidence.filter((item) => item.status === "pending"),
    [sortedEvidence],
  );
  const selectedPendingEvidenceIds = useMemo(
    () =>
      selectedBulkEvidenceIds.filter(
        (id) => evidenceById.get(id)?.status === "pending",
      ),
    [evidenceById, selectedBulkEvidenceIds],
  );
  const selectedPendingCount = selectedPendingEvidenceIds.length;
  const selectedEvidence =
    sortedEvidence.find((item) => item.id === selectedEvidenceId) ?? sortedEvidence[0] ?? null;
  const selectedMediaAsset = selectedEvidence?.snapshot_media_asset_id
    ? mediaById.get(selectedEvidence.snapshot_media_asset_id) ?? null
    : null;
  const selectedSource = selectedEvidence?.source_id
    ? sourceById.get(selectedEvidence.source_id) ?? null
    : null;
  const selectedStream = selectedEvidence?.stream_id
    ? streamById.get(selectedEvidence.stream_id) ?? null
    : null;
  const selectedHasSavedPreviewMedia = selectedEvidence
    ? isSavedPreviewMediaEvidence(selectedEvidence, selectedMediaAsset)
    : false;
  const selectedHasFolderImportMedia = selectedEvidence
    ? isFolderImportMediaEvidence(selectedEvidence, selectedMediaAsset)
    : false;
  const selectedWebhookProvenance = selectedEvidence
    ? getWebhookEvidenceProvenance(selectedEvidence)
    : null;
  const attachedMediaTitle = selectedHasFolderImportMedia
    ? "Folder-imported media"
    : selectedHasSavedPreviewMedia
      ? "Saved preview media"
      : "Attached media";
  const attachedMediaProvenance = selectedEvidence
    ? formatAttachedMediaProvenance(selectedEvidence, selectedMediaAsset)
    : "";
  const selectedFolderRelativePath = extractSafeRelativePath(
    selectedMediaAsset?.notes ?? "",
    "relative_source_path",
  );
  const selectedFolderCopyMode = extractSafeNoteValue(selectedMediaAsset?.notes ?? "", "copy_mode");
  const manualMediaAsset = manualSnapshotMediaAssetId
    ? mediaById.get(manualSnapshotMediaAssetId) ?? null
    : null;
  const evidenceCounts = useMemo(() => {
    const counts: Record<MotionEvidenceFilter, number> = {
      all: zoneFilteredEvidence.length,
      pending: 0,
      promoted: 0,
      ignored: 0,
    };
    zoneFilteredEvidence.forEach((item) => {
      counts[item.status] += 1;
    });
    return counts;
  }, [zoneFilteredEvidence]);

  async function loadEvidence(
    options: { showLoading?: boolean; selectEvidenceId?: string } = {},
  ) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoading(true);
    }
    setError(null);
    try {
      // Remaining Performance P1 Closure v1 (P1-7): two bounded reads in
      // place of the whole MediaAsset library. The picker offers a recent
      // window; the lookup map is hydrated with exactly the snapshots this
      // evidence list references, which is what it was ever used for.
      const [response, pickerPage] = await Promise.all([
        apiClient.listMotionEvidence({ status: "all" }),
        apiClient.getMediaAssetPage({ limit: MEDIA_PICKER_WINDOW, newest_first: true }),
      ]);
      const referenced = await apiClient.getMediaAssetsByIds(
        response.motion_evidence
          .map((item) => item.snapshot_media_asset_id)
          .filter((id): id is string => Boolean(id)),
      );
      const nextMediaAssets = mergeMediaAssets(pickerPage.items, referenced);
      setEvidence(response.motion_evidence);
      setMediaAssets(nextMediaAssets);
      setSelectedEvidenceId((current) =>
        options.selectEvidenceId &&
        response.motion_evidence.some((item) => item.id === options.selectEvidenceId)
          ? options.selectEvidenceId
          : current && response.motion_evidence.some((item) => item.id === current)
            ? current
            : response.motion_evidence[0]?.id ?? null,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load Motion Evidence.");
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  }

  useEffect(() => {
    void loadEvidence();
  }, []);

  useEffect(() => {
    setSelectedBulkEvidenceIds((current) =>
      current.filter((id) => evidenceById.get(id)?.status === "pending"),
    );
  }, [evidenceById]);

  useEffect(() => {
    setVisibleEvidenceCount(15);
  }, [statusFilter, zoneFilter]);

  useEffect(() => {
    setEventTitle(
      selectedEvidence
        ? selectedEvidence.zone_id
          ? `Motion evidence in ${selectedEvidence.zone_id}`
          : "Outdoor motion activity"
        : "",
    );
    setVisitLabelHint("unknown_animal");
    setPromotionNotes("");
    setAttachMediaAssetId(selectedEvidence?.snapshot_media_asset_id ?? "");
    setLastPromotion(null);
  }, [selectedEvidence?.id, selectedEvidence?.snapshot_media_asset_id]);

  async function applyZoneFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await loadEvidence({ showLoading: false });
  }

  async function createManualEvidence(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    const zoneId = manualZoneId.trim();
    if (!zoneId) {
      setError("Add a zone_id before creating Motion Evidence.");
      return;
    }

    let peakChangedRatio: number;
    let triggeredFrameCount: number;
    let startFrameIndex: number | null;
    let endFrameIndex: number | null;
    let bestFrameIndex: number | null;
    let scoringConfig: Record<string, string | number | boolean>;
    try {
      peakChangedRatio = parsePeakChangedRatio(manualPeakChangedRatio);
      triggeredFrameCount = parsePositiveInteger(
        manualTriggeredFrameCount,
        "Triggered frame count",
      );
      startFrameIndex = parseOptionalFrameIndex(manualStartFrameIndex, "Start frame index");
      endFrameIndex = parseOptionalFrameIndex(manualEndFrameIndex, "End frame index");
      bestFrameIndex = parseOptionalFrameIndex(manualBestFrameIndex, "Best frame index");
      scoringConfig = parseScoringConfig(manualScoringConfig);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Manual evidence fields are invalid.");
      return;
    }

    const payload: MotionEvidenceCreateRequest = {
      zone_id: zoneId,
      source_id: manualSourceId || undefined,
      stream_id: manualStreamId || undefined,
      start_frame_index: startFrameIndex,
      end_frame_index: endFrameIndex,
      best_frame_index: bestFrameIndex,
      peak_changed_ratio: peakChangedRatio,
      triggered_frame_count: triggeredFrameCount,
      scoring_config: scoringConfig,
      snapshot_media_asset_id: manualSnapshotMediaAssetId.trim() || undefined,
      notes: manualNotes.trim() || undefined,
    };

    setIsCreating(true);
    setLastPromotion(null);
    setLastBulkPromotion(null);
    try {
      const created = await apiClient.createMotionEvidence(payload);
      setStatusFilter("pending");
      setZoneFilter(created.zone_id ?? "");
      setSelectedEvidenceId(created.id);
      setMessage(
        created.snapshot_media_asset_id
          ? `${created.id} created as pending Motion Evidence with media ${created.snapshot_media_asset_id}. Review it before promotion.`
          : `${created.id} created as pending Motion Evidence. Review it before promotion.`,
      );
      await loadEvidence({ showLoading: false, selectEvidenceId: created.id });
      await onEvidenceChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Manual Motion Evidence could not be created.");
    } finally {
      setIsCreating(false);
    }
  }

  async function evaluateSampledFrames(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    const zoneId = sampleZoneId.trim();
    if (!zoneId) {
      setError("Add a zone_id before evaluating sampled frames.");
      return;
    }

    let payload: MotionEvaluateSequenceRequest;
    try {
      const left = parseNormalizedBound(sampleZoneLeft, "Zone left");
      const top = parseNormalizedBound(sampleZoneTop, "Zone top");
      const right = parseNormalizedBound(sampleZoneRight, "Zone right");
      const bottom = parseNormalizedBound(sampleZoneBottom, "Zone bottom");
      validateZoneBounds(left, top, right, bottom);

      payload = {
        frames: parseFrameSequence(sampleFramesJson),
        zones: [
          {
            zone_id: zoneId,
            left,
            top,
            right,
            bottom,
          },
        ],
        source_id: sampleSourceId || undefined,
        stream_id: sampleStreamId || undefined,
        frame_index_start: parseNonNegativeInteger(sampleFrameIndexStart, "Frame index start"),
        pixel_delta_threshold: parseNonNegativeNumber(
          samplePixelDeltaThreshold,
          "Pixel delta threshold",
        ),
        min_changed_ratio: parseRatio(sampleMinChangedRatio, "Minimum changed ratio"),
        min_triggered_frames: parsePositiveInteger(
          sampleMinTriggeredFrames,
          "Minimum triggered frames",
        ),
        max_gap_frames: parseNonNegativeInteger(sampleMaxGapFrames, "Maximum gap frames"),
        create_motion_evidence: sampleCreateMotionEvidence,
        notes: sampleNotes.trim() || undefined,
      };
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sampled frame fields are invalid.");
      return;
    }

    setIsEvaluatingSample(true);
    try {
      const result = await apiClient.evaluateMotionSequence(payload);
      setSampleResult(result);
      if (result.created_evidence.length > 0) {
        const firstCreated = result.created_evidence[0];
        setStatusFilter("pending");
        setZoneFilter(firstCreated.zone_id ?? "");
        setSelectedEvidenceId(firstCreated.id);
        setMessage(
          `${firstCreated.id} created as pending Motion Evidence from sampled frame evaluation.`,
        );
        await loadEvidence({ showLoading: false, selectEvidenceId: firstCreated.id });
        await onEvidenceChanged();
      } else {
        setMessage(
          `Sampled frame evaluation returned ${result.candidates.length} candidate${
            result.candidates.length === 1 ? "" : "s"
          } and created no Motion Evidence.`,
        );
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sampled frames could not be evaluated.");
    } finally {
      setIsEvaluatingSample(false);
    }
  }

  async function ignoreEvidence(item: MotionEvidence) {
    setActionId(`${item.id}:ignore`);
    setError(null);
    setMessage(null);
    setLastPromotion(null);
    setLastBulkPromotion(null);
    try {
      const ignored = await apiClient.ignoreMotionEvidence(item.id);
      setSelectedEvidenceId(ignored.id);
      setMessage(`${ignored.id} ignored as motion noise. No Event, Visit, or truth was created.`);
      await loadEvidence({ showLoading: false });
      await onEvidenceChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Motion Evidence could not be ignored.");
    } finally {
      setActionId(null);
    }
  }

  async function attachMediaEvidence(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedEvidence || selectedEvidence.status !== "pending") {
      return;
    }

    await updateMediaAttachment(selectedEvidence, attachMediaAssetId.trim() || null);
  }

  async function clearMediaAttachment(item: MotionEvidence) {
    if (item.status !== "pending") {
      return;
    }

    await updateMediaAttachment(item, null);
  }

  async function updateMediaAttachment(item: MotionEvidence, mediaAssetId: string | null) {
    setActionId(`${item.id}:attach-media`);
    setError(null);
    setMessage(null);
    setLastPromotion(null);
    setLastBulkPromotion(null);
    try {
      const updated = await apiClient.attachMotionEvidenceMedia(item.id, {
        snapshot_media_asset_id: mediaAssetId,
      });
      setSelectedEvidenceId(updated.id);
      setAttachMediaAssetId(updated.snapshot_media_asset_id ?? "");
      setMessage(
        updated.snapshot_media_asset_id
          ? `${updated.id} now references existing media ${updated.snapshot_media_asset_id}. No labels or truth were created.`
          : `${updated.id} no longer has a media reference. No labels or truth were changed.`,
      );
      await loadEvidence({ showLoading: false, selectEvidenceId: updated.id });
      await onEvidenceChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Media could not be attached.");
    } finally {
      setActionId(null);
    }
  }

  async function promoteEvidence(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedEvidence || selectedEvidence.status !== "pending") {
      return;
    }

    setActionId(`${selectedEvidence.id}:promote`);
    setError(null);
    setMessage(null);
    setLastPromotion(null);
    setLastBulkPromotion(null);
    try {
      const result = await apiClient.promoteMotionEvidence(selectedEvidence.id, {
        event_title: eventTitle.trim() || undefined,
        visit_label_hint: visitLabelHint.trim() || undefined,
        notes: promotionNotes.trim() || undefined,
        create_event: true,
        create_visit: true,
      });
      setLastPromotion(result);
      setSelectedEvidenceId(result.evidence.id);
      setMessage(
        `${result.evidence.id} promoted to reviewable Event/Visit evidence. Correction still creates truth.`,
      );
      await loadEvidence({ showLoading: false });
      await onEvidenceChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Motion Evidence could not be promoted.");
    } finally {
      setActionId(null);
    }
  }

  function toggleBulkSelection(item: MotionEvidence, checked: boolean) {
    if (item.status !== "pending") {
      return;
    }
    setSelectedBulkEvidenceIds((current) => {
      const next = new Set(current);
      if (checked) {
        next.add(item.id);
      } else {
        next.delete(item.id);
      }
      return [...next];
    });
  }

  function selectAllPendingInView() {
    setSelectedBulkEvidenceIds((current) => {
      const next = new Set(current);
      selectablePendingEvidence.forEach((item) => next.add(item.id));
      return [...next];
    });
  }

  async function applyBulkAction(action: MotionEvidenceBulkAction) {
    if (selectedPendingEvidenceIds.length === 0) {
      return;
    }

    const actionLabel = action === "promote" ? "promote" : "ignore";
    const noun = selectedPendingEvidenceIds.length === 1 ? "item" : "items";
    const confirmation =
      action === "promote"
        ? `Promote ${selectedPendingEvidenceIds.length} pending Motion Evidence ${noun}? Promotion creates reviewable visits/events, not truth.`
        : `Ignore ${selectedPendingEvidenceIds.length} pending Motion Evidence ${noun}? Ignored evidence creates no Event, Visit, label, or truth.`;
    if (!window.confirm(confirmation)) {
      return;
    }

    setActionId(`bulk:${action}`);
    setError(null);
    setMessage(null);
    setLastPromotion(null);
    setLastBulkPromotion(null);
    try {
      const result = await apiClient.bulkMotionEvidenceAction({
        motion_evidence_ids: selectedPendingEvidenceIds,
        action,
      });
      setSelectedBulkEvidenceIds([]);
      setLastBulkPromotion(action === "promote" ? result : null);
      const summary = `${formatLabel(actionLabel)} bulk action: ${result.succeeded_count} succeeded, ${result.skipped_count} skipped, ${result.failed_count} failed.`;
      const boundary =
        action === "promote"
          ? "Promote creates reviewable visits/events, not truth. Corrections still drive analytics and exports."
          : "Ignored Motion Evidence remains non-truth evidence history.";
      setMessage(`${summary} ${boundary}`);
      const firstSucceeded = result.results.find((item) => item.status === "succeeded");
      await loadEvidence({
        showLoading: false,
        selectEvidenceId: firstSucceeded?.motion_evidence_id,
      });
      await onEvidenceChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Bulk Motion Evidence action failed.");
    } finally {
      setActionId(null);
    }
  }

  const hasFilters = statusFilter !== "all" || zoneFilter.trim().length > 0;
  const isBulkActionRunning = actionId === "bulk:ignore" || actionId === "bulk:promote";

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Advanced evidence"
        title="Advanced Evidence"
        description="Used for debugging activity detection and review handoff. The normal product loop is Cameras/Streams → Review Queue → Bird Log → Export."
        actions={
          <button className="secondary-action" onClick={onOpenReview}>
            Review Queue
          </button>
        }
      />

      <section className="notice-panel">
        <strong>Advanced evidence before truth</strong>
        <span>
          Promote useful evidence only when validating the internal flow; correct Review Queue items for
          dataset truth.
        </span>
      </section>

      <section className="panel motion-workflow-panel">
        <div>
          <h2>Workflow</h2>
          <p>Create, attach best frame, promote, then correct in Review Queue.</p>
        </div>
        <div className="motion-workflow-steps" aria-label="Motion Evidence workflow">
          {motionWorkflowSteps.map((step) => (
            <span key={step}>{step}</span>
          ))}
        </div>
      </section>

      {message ? <div className="notice-panel">{message}</div> : null}
      {error ? <div className="error-panel">{error}</div> : null}
      {lastPromotion ? (
        <PromotionResultPanel
          promotion={lastPromotion}
          onOpenMotionEvidence={onOpenMotionEvidence}
          onOpenEvent={onOpenEvent}
          onOpenVisit={onOpenVisit}
        />
      ) : null}
      {lastBulkPromotion ? (
        <BulkPromotionResultPanel
          result={lastBulkPromotion}
          onOpenMotionEvidence={onOpenMotionEvidence}
          onOpenEvent={onOpenEvent}
          onOpenVisit={onOpenVisit}
        />
      ) : null}

      <section className="panel motion-create-panel">
        <div className="section-heading">
          <div>
            <h2>Create manual activity evidence</h2>
            <span className="meta-text">
              Manual evidence creation is for local testing before stream sampling is wired in.
              It creates pending MotionEvidence only; it does not create labels, reviewed
              observations, or export-ready truth.
            </span>
          </div>
          <EvidenceBadge label="Pending evidence only" tone="review" />
        </div>
        <form className="motion-create-form" onSubmit={createManualEvidence}>
          <div className="motion-create-grid">
            <label>
              Zone ID
              <input
                required
                value={manualZoneId}
                onChange={(event) => setManualZoneId(event.target.value)}
                placeholder="zone-feeder"
              />
            </label>
            <label>
              Source
              <select
                value={manualSourceId}
                onChange={(event) => setManualSourceId(event.target.value)}
              >
                <option value="">Infer from zone</option>
                {sources.map((source) => (
                  <option key={source.id} value={source.id}>
                    {source.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Stream
              <select
                value={manualStreamId}
                onChange={(event) => setManualStreamId(event.target.value)}
              >
                <option value="">Infer from zone</option>
                {streams.map((stream) => (
                  <option key={stream.id} value={stream.id}>
                    {stream.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Peak change
              <input
                required
                value={manualPeakChangedRatio}
                onChange={(event) => setManualPeakChangedRatio(event.target.value)}
                placeholder="42% or 0.42"
              />
            </label>
            <label>
              Triggered frames
              <input
                required
                inputMode="numeric"
                value={manualTriggeredFrameCount}
                onChange={(event) => setManualTriggeredFrameCount(event.target.value)}
                placeholder="2"
              />
            </label>
            <label className="motion-wide-field">
              Attach existing media asset
              <select
                disabled={mediaAssets.length === 0}
                value={manualSnapshotMediaAssetId}
                onChange={(event) => setManualSnapshotMediaAssetId(event.target.value)}
              >
                <option value="">No attached media</option>
                {mediaAssets.map((asset) => (
                  <option key={asset.id} value={asset.id}>
                    {asset.original_filename} - {asset.id}
                  </option>
                ))}
              </select>
              <span className="field-helper">
                Optional: attach an existing local media asset as visual evidence. Import media
                first on the Import Media page, then select it here. This creates pending evidence
                only; it does not create labels, reviewed observations, or export-ready truth.
              </span>
            </label>
            {manualSnapshotMediaAssetId ? (
              <div className="manual-media-preview motion-wide-field">
                <div className="section-heading">
                  <div>
                    <h3>Creation media context</h3>
                    <span className="meta-text">
                      The selected MediaAsset must belong to the same stream as this evidence.
                    </span>
                  </div>
                  <EvidenceBadge label="Evidence context" tone="evidence" />
                </div>
                {manualMediaAsset ? (
                  <>
                    <MediaAssetPreview asset={manualMediaAsset} compact />
                    <div className="detail-actions">
                      <a
                        className="text-action"
                        href={apiClient.mediaFileUrl(manualMediaAsset.id)}
                        rel="noreferrer"
                        target="_blank"
                      >
                        Open media file
                      </a>
                    </div>
                  </>
                ) : (
                  <span className="meta-text">
                    Media details are not loaded yet. The backend will validate this ID on create.
                  </span>
                )}
              </div>
            ) : null}
            <label>
              Start frame
              <input
                inputMode="numeric"
                value={manualStartFrameIndex}
                onChange={(event) => setManualStartFrameIndex(event.target.value)}
                placeholder="optional"
              />
            </label>
            <label>
              End frame
              <input
                inputMode="numeric"
                value={manualEndFrameIndex}
                onChange={(event) => setManualEndFrameIndex(event.target.value)}
                placeholder="optional"
              />
            </label>
            <label>
              Best frame
              <input
                inputMode="numeric"
                value={manualBestFrameIndex}
                onChange={(event) => setManualBestFrameIndex(event.target.value)}
                placeholder="optional"
              />
            </label>
            <label className="motion-wide-field">
              Scoring config JSON
              <textarea
                value={manualScoringConfig}
                onChange={(event) => setManualScoringConfig(event.target.value)}
              />
            </label>
            <label className="motion-wide-field">
              Notes
              <textarea
                value={manualNotes}
                onChange={(event) => setManualNotes(event.target.value)}
                placeholder="Manual evidence note"
              />
            </label>
          </div>
          <div className="motion-create-actions">
            <button className="primary-action" disabled={isCreating} type="submit">
              {isCreating ? "Creating..." : "Create pending evidence"}
            </button>
            <span className="field-helper">
              Leave source and stream blank to let the backend use the selected zone. Imported
              media can be attached now or later from the detail panel.
            </span>
          </div>
        </form>
      </section>

      <section className="panel motion-create-panel sampled-frame-panel">
        <div className="section-heading">
          <div>
            <h2>Sampled Frame Evaluation</h2>
            <span className="meta-text">
              Use tiny sampled frame planes to exercise motion scoring before real stream sampling
              is wired in. This can create pending MotionEvidence only; it does not create labels,
              reviewed observations, or export-ready truth.
            </span>
          </div>
          <EvidenceBadge label="Frame-plane harness" tone="evidence" />
        </div>
        <form className="motion-create-form" onSubmit={evaluateSampledFrames}>
          <div className="motion-create-grid">
            <label>
              Source
              <select
                value={sampleSourceId}
                onChange={(event) => setSampleSourceId(event.target.value)}
              >
                <option value="">Infer from zone</option>
                {sources.map((source) => (
                  <option key={source.id} value={source.id}>
                    {source.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Stream
              <select
                value={sampleStreamId}
                onChange={(event) => setSampleStreamId(event.target.value)}
              >
                <option value="">Infer from zone</option>
                {streams.map((stream) => (
                  <option key={stream.id} value={stream.id}>
                    {stream.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Zone ID
              <input
                required
                value={sampleZoneId}
                onChange={(event) => setSampleZoneId(event.target.value)}
                placeholder="zone-feeder"
              />
            </label>
            <label>
              Left
              <input
                required
                inputMode="decimal"
                value={sampleZoneLeft}
                onChange={(event) => setSampleZoneLeft(event.target.value)}
                placeholder="0"
              />
            </label>
            <label>
              Top
              <input
                required
                inputMode="decimal"
                value={sampleZoneTop}
                onChange={(event) => setSampleZoneTop(event.target.value)}
                placeholder="0"
              />
            </label>
            <label>
              Right
              <input
                required
                inputMode="decimal"
                value={sampleZoneRight}
                onChange={(event) => setSampleZoneRight(event.target.value)}
                placeholder="1"
              />
            </label>
            <label>
              Bottom
              <input
                required
                inputMode="decimal"
                value={sampleZoneBottom}
                onChange={(event) => setSampleZoneBottom(event.target.value)}
                placeholder="1"
              />
            </label>
            <label>
              Pixel delta threshold
              <input
                required
                inputMode="decimal"
                value={samplePixelDeltaThreshold}
                onChange={(event) => setSamplePixelDeltaThreshold(event.target.value)}
                placeholder="25"
              />
            </label>
            <label>
              Minimum changed ratio
              <input
                required
                inputMode="decimal"
                value={sampleMinChangedRatio}
                onChange={(event) => setSampleMinChangedRatio(event.target.value)}
                placeholder="0.02"
              />
            </label>
            <label>
              Minimum triggered frames
              <input
                required
                inputMode="numeric"
                value={sampleMinTriggeredFrames}
                onChange={(event) => setSampleMinTriggeredFrames(event.target.value)}
                placeholder="1"
              />
            </label>
            <label>
              Maximum gap frames
              <input
                required
                inputMode="numeric"
                value={sampleMaxGapFrames}
                onChange={(event) => setSampleMaxGapFrames(event.target.value)}
                placeholder="1"
              />
            </label>
            <label>
              Frame index start
              <input
                required
                inputMode="numeric"
                value={sampleFrameIndexStart}
                onChange={(event) => setSampleFrameIndexStart(event.target.value)}
                placeholder="0"
              />
            </label>
            <label className="motion-checkbox-field">
              <input
                checked={sampleCreateMotionEvidence}
                onChange={(event) => setSampleCreateMotionEvidence(event.target.checked)}
                type="checkbox"
              />
              Create pending MotionEvidence
            </label>
            <label className="motion-wide-field">
              Frame planes JSON
              <textarea
                className="sampled-frame-textarea"
                value={sampleFramesJson}
                onChange={(event) => setSampleFramesJson(event.target.value)}
              />
            </label>
            <label className="motion-wide-field">
              Notes
              <textarea
                value={sampleNotes}
                onChange={(event) => setSampleNotes(event.target.value)}
                placeholder="Evidence note for created records"
              />
            </label>
          </div>
          <div className="motion-create-actions sampled-frame-actions">
            <button
              className="secondary-action"
              onClick={() => setSampleFramesJson(motionSampleFrames)}
              type="button"
            >
              Use motion sample
            </button>
            <button
              className="secondary-action"
              onClick={() => setSampleFramesJson(noMotionSampleFrames)}
              type="button"
            >
              Use no motion sample
            </button>
            <button className="primary-action" disabled={isEvaluatingSample} type="submit">
              {isEvaluatingSample ? "Evaluating..." : "Evaluate sampled frames"}
            </button>
            <span className="field-helper">
              Leave source and stream blank to let the backend use the selected zone.
            </span>
          </div>
        </form>

        {sampleResult ? (
          <section className="sampled-frame-results">
            <div className="motion-evidence-detail-grid">
              <DetailItem label="Frame scores" value={`${sampleResult.frame_scores.length}`} />
              <DetailItem label="Candidates" value={`${sampleResult.candidates.length}`} />
              <DetailItem
                label="Created evidence"
                value={`${sampleResult.created_evidence.length}`}
              />
              <DetailItem
                label="Requested creation"
                value={sampleCreateMotionEvidence ? "yes" : "no"}
              />
            </div>

            <div className="motion-evidence-subsection">
              <h3>Candidates</h3>
              {sampleResult.candidates.length > 0 ? (
                <div className="sampled-frame-result-list">
                  {sampleResult.candidates.map((candidate) => (
                    <div
                      className="sampled-frame-result-card"
                      key={`${candidate.zone_id}:${candidate.start_frame_index}:${candidate.end_frame_index}`}
                    >
                      <strong>{candidate.zone_id}</strong>
                      <span>
                        Frames {candidate.start_frame_index}-{candidate.end_frame_index}
                      </span>
                      <span>Best frame {candidate.best_frame_index}</span>
                      <span>{formatPercent(candidate.peak_changed_ratio)} peak change</span>
                      <span>{candidate.triggered_frame_count} triggered frames</span>
                    </div>
                  ))}
                </div>
              ) : (
                <span className="meta-text">No motion candidates returned.</span>
              )}
            </div>

            <div className="motion-evidence-subsection">
              <h3>Created MotionEvidence</h3>
              {sampleResult.created_evidence.length > 0 ? (
                <div className="sampled-frame-result-list">
                  {sampleResult.created_evidence.map((created) => (
                    <button
                      className="sampled-frame-result-card selectable"
                      key={created.id}
                      onClick={() => {
                        setStatusFilter("pending");
                        setZoneFilter(created.zone_id ?? "");
                        setSelectedEvidenceId(created.id);
                      }}
                      type="button"
                    >
                      <strong>{created.id}</strong>
                      <span>{formatLabel(created.status)}</span>
                      <span>{created.zone_id ?? "Automatic activity area"}</span>
                      <span>{formatPercent(created.peak_changed_ratio)} peak change</span>
                      <span>{created.triggered_frame_count} triggered frames</span>
                    </button>
                  ))}
                </div>
              ) : (
                <span className="meta-text">No MotionEvidence records created.</span>
              )}
            </div>

            <section className="notice-panel">
              <strong>Truth boundary</strong>
              <span>
                Created evidence is pending only. Promotion creates unreviewed Event/Visit
                evidence; correction remains truth.
              </span>
            </section>
          </section>
        ) : null}
      </section>

      <section className="panel motion-evidence-filters">
        <div className="section-heading">
          <div>
            <h2>Evidence filters</h2>
            <span className="meta-text">Review pending activity, promoted evidence, or ignored noise.</span>
          </div>
          <EvidenceBadge label={`${evidenceCounts.pending} pending`} tone="review" />
        </div>
        <div className="proposal-status-tabs" role="tablist" aria-label="Motion Evidence status filters">
          {statusFilters.map((filter) => (
            <button
              className={statusFilter === filter.value ? "selected" : ""}
              key={filter.value}
              onClick={() => setStatusFilter(filter.value)}
              type="button"
            >
              {filter.label}
              <span>{evidenceCounts[filter.value]}</span>
            </button>
          ))}
        </div>
        <form className="motion-zone-filter" onSubmit={applyZoneFilter}>
          <label>
            Zone ID
            <input
              placeholder="zone-feeder"
              value={zoneFilter}
              onChange={(event) => setZoneFilter(event.target.value)}
            />
          </label>
          <button className="secondary-action" type="submit">
            Apply
          </button>
          {zoneFilter ? (
            <button
              className="text-action"
              type="button"
              onClick={() => {
                setZoneFilter("");
              }}
            >
              Clear
            </button>
          ) : null}
        </form>
        <div className="motion-bulk-actions">
          <div>
            <strong>{selectedPendingCount} pending selected</strong>
            <span>Promote creates reviewable visits/events, not truth.</span>
            <span>Corrections still drive analytics and exports.</span>
          </div>
          <div className="detail-actions">
            <button
              className="secondary-action"
              disabled={selectablePendingEvidence.length === 0 || isBulkActionRunning}
              onClick={selectAllPendingInView}
              type="button"
            >
              Select pending in view
            </button>
            <button
              className="text-action"
              disabled={selectedPendingCount === 0 || isBulkActionRunning}
              onClick={() => setSelectedBulkEvidenceIds([])}
              type="button"
            >
              Clear
            </button>
            <button
              className="secondary-action"
              disabled={selectedPendingCount === 0 || isBulkActionRunning}
              onClick={() => void applyBulkAction("ignore")}
              type="button"
            >
              {actionId === "bulk:ignore" ? "Ignoring..." : "Bulk ignore"}
            </button>
            <button
              className="primary-action"
              disabled={selectedPendingCount === 0 || isBulkActionRunning}
              onClick={() => void applyBulkAction("promote")}
              type="button"
            >
              {actionId === "bulk:promote" ? "Promoting..." : "Bulk promote"}
            </button>
          </div>
        </div>
      </section>

      {isLoading ? <div className="panel">Loading advanced evidence...</div> : null}

      {!isLoading && sortedEvidence.length === 0 ? (
        <EmptyState
                title={hasFilters ? "No advanced evidence matches this filter." : "No advanced evidence yet."}
          description={
            hasFilters
              ? "Try another status or zone, or review explicit media handoff results."
              : "Create evidence from saved media, folder imports, manual/dev tools, or sampled frames."
          }
        />
      ) : null}

      {!isLoading && sortedEvidence.length > 0 ? (
        <div className="motion-evidence-layout">
          <section className="motion-evidence-list" aria-label="Advanced evidence list">
            <span className="meta-text">
              Showing {Math.min(visibleEvidenceCount, sortedEvidence.length)} of {sortedEvidence.length}
            </span>
            {sortedEvidence.slice(0, visibleEvidenceCount).map((item) => (
              <article
                className={
                  selectedEvidence?.id === item.id
                    ? "motion-evidence-row selected"
                    : "motion-evidence-row"
                }
                key={item.id}
              >
                <div className="motion-evidence-row-top">
                  <label className="motion-evidence-select">
                    <input
                      checked={selectedPendingEvidenceIds.includes(item.id)}
                      disabled={item.status !== "pending" || isBulkActionRunning}
                      onChange={(event) => toggleBulkSelection(item, event.target.checked)}
                      type="checkbox"
                    />
                    <span>{item.status === "pending" ? "Select" : "Locked"}</span>
                  </label>
                  <button
                    className="motion-evidence-row-main"
                    onClick={() => setSelectedEvidenceId(item.id)}
                    type="button"
                  >
                    <div className="item-title-row">
                      <div>
                        <span className="meta-text">
                          {item.zone_id ?? "Automatic activity area"}
                        </span>
                        <h2>{item.id}</h2>
                      </div>
                      <div className="record-status-stack">
                        {getWebhookEvidenceProvenance(item).isWebhook ? (
                          <EvidenceBadge label="Webhook metadata evidence" tone="evidence" />
                        ) : null}
                        {item.snapshot_media_asset_id ? (
                          <EvidenceBadge
                            label={
                              formatMotionEvidenceMediaBadge(
                                item,
                                mediaById.get(item.snapshot_media_asset_id) ?? null,
                              )
                            }
                            tone="evidence"
                          />
                        ) : null}
                        <MotionEvidenceStatusPill status={item.status} />
                      </div>
                    </div>
                    <div className="motion-evidence-meta">
                      <span>{formatPercent(item.peak_changed_ratio)} peak change</span>
                      <span>{item.triggered_frame_count} triggered frames</span>
                      <span>{formatRange(item)}</span>
                      <span>{formatDateTime(item.created_at)}</span>
                    </div>
                    {item.notes ? <p>{item.notes}</p> : null}
                  </button>
                </div>
                {item.status === "promoted" &&
                (item.promoted_event_id || item.promoted_visit_id) ? (
                  <div className="motion-evidence-row-links">
                    <span>Promoted to review</span>
                    <button
                      className="text-action"
                      onClick={() => onOpenMotionEvidence(item.id)}
                      type="button"
                    >
                      Open evidence
                    </button>
                    {item.promoted_event_id ? (
                      <button
                        className="text-action"
                        onClick={() => onOpenEvent(item.promoted_event_id!)}
                        type="button"
                      >
                        Open Event
                      </button>
                    ) : null}
                    {item.promoted_visit_id ? (
                      <button
                        className="text-action"
                        onClick={() => onOpenVisit(item.promoted_visit_id!)}
                        type="button"
                      >
                        Open Visit
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </article>
            ))}
            {sortedEvidence.length > visibleEvidenceCount ? (
              <div className="panel-actions">
                <button
                  className="secondary-action"
                  onClick={() => setVisibleEvidenceCount((current) => current + 20)}
                  type="button"
                >
                  Show more evidence ({sortedEvidence.length - visibleEvidenceCount} more)
                </button>
              </div>
            ) : null}
          </section>

          <section className="panel motion-evidence-detail">
            {selectedEvidence ? (
              <>
                <div className="section-heading">
                  <div>
                    <span className="meta-text">Selected evidence</span>
                    <h2>{selectedEvidence.id}</h2>
                  </div>
                  <MotionEvidenceStatusPill status={selectedEvidence.status} />
                </div>

                <section className="notice-panel motion-status-note">
                  <strong>{formatLabel(selectedEvidence.status)} status</strong>
                  <span>{formatEvidenceStatusCopy(selectedEvidence, selectedMediaAsset)}</span>
                </section>

                {selectedWebhookProvenance?.isWebhook ? (
                  <section className="motion-evidence-subsection webhook-evidence-panel">
                    <div className="section-heading">
                      <div>
                        <h3>Webhook metadata evidence</h3>
                        <span className="meta-text">
                          Generic webhook ingest provenance is evidence metadata only.
                        </span>
                      </div>
                      <EvidenceBadge label="Generic webhook ingest" tone="evidence" />
                    </div>
                    <p className="evidence-panel-copy">
                      {selectedEvidence.status === "promoted"
                        ? "Promoted evidence created a reviewable Event/Visit. Correction remains the truth boundary."
                        : selectedEvidence.status === "ignored"
                          ? "This webhook-origin evidence was ignored and remains non-truth evidence history."
                          : pendingWebhookEvidenceBoundaryCopy}{" "}
                      No label has been confirmed yet by webhook metadata.
                    </p>
                    <div className="motion-review-context-grid">
                      <ContextItem
                        label="Provider"
                        value={selectedWebhookProvenance.providerKey ?? "webhook_future"}
                      />
                      <ContextItem
                        label="Candidate type"
                        value={formatWebhookValue(selectedWebhookProvenance.candidateType)}
                      />
                      <ContextItem
                        label="External event ID"
                        value={formatWebhookValue(selectedWebhookProvenance.externalEventId)}
                      />
                      <ContextItem
                        label="Untrusted external label"
                        value={formatWebhookValue(selectedWebhookProvenance.externalLabel)}
                        detail="Evidence metadata only"
                      />
                      <ContextItem
                        label="Untrusted external confidence"
                        value={formatWebhookValue(selectedWebhookProvenance.externalConfidence)}
                        detail="Not a reviewed confidence"
                      />
                      <ContextItem
                        label="Webhook timestamp"
                        value={formatWebhookValue(selectedWebhookProvenance.externalTimestamp)}
                      />
                    </div>
                  </section>
                ) : null}

                <div className="motion-evidence-detail-grid">
                  <DetailItem
                    label="Activity context"
                    value={selectedEvidence.zone_id ?? "Automatic activity area"}
                  />
                  <DetailItem label="Status" value={formatLabel(selectedEvidence.status)} />
                  <DetailItem label="Peak change" value={formatPercent(selectedEvidence.peak_changed_ratio)} />
                  <DetailItem label="Triggered frames" value={`${selectedEvidence.triggered_frame_count}`} />
                  <DetailItem label="Frame/time range" value={formatRange(selectedEvidence)} />
                  <DetailItem label="Best frame/time" value={formatBestMoment(selectedEvidence)} />
                  <DetailItem
                    label="Source"
                    value={formatSource(selectedEvidence.source_id, sourceById)}
                  />
                  <DetailItem
                    label="Stream"
                    value={formatStream(selectedEvidence.stream_id, streamById)}
                  />
                  <DetailItem label="Created" value={formatDateTime(selectedEvidence.created_at)} />
                </div>

                <section className="motion-evidence-subsection">
                  <div className="section-heading">
                    <div>
                      <h3>Source/Stream/Zone context</h3>
                      <span className="meta-text">
                        Context helps decide whether pending evidence should be ignored or promoted.
                      </span>
                    </div>
                    <EvidenceBadge label="Review context" tone="evidence" />
                  </div>
                  <div className="motion-review-context-grid">
                    <ContextItem
                      label="Source"
                      value={selectedSource?.name ?? selectedEvidence.source_id ?? "none"}
                      detail={selectedEvidence.source_id}
                    />
                    <ContextItem
                      label="Stream"
                      value={selectedStream?.name ?? selectedEvidence.stream_id ?? "none"}
                      detail={selectedEvidence.stream_id}
                    />
                    <ContextItem
                      label="Activity area"
                      value={selectedEvidence.zone_id ?? "Automatic activity area"}
                    />
                    <ContextItem
                      label="Evidence state"
                      value={formatLabel(selectedEvidence.status)}
                      detail={
                        selectedEvidence.status === "pending"
                          ? "Review before promoting"
                          : selectedEvidence.status === "promoted"
                            ? "Event/Visit review remains"
                            : "Preserved as ignored evidence"
                      }
                    />
                  </div>
                </section>

                <section className="motion-evidence-subsection">
                  <h3>Scoring context</h3>
                  <div className="motion-config-list">
                    {Object.entries(selectedEvidence.scoring_config).length > 0 ? (
                      Object.entries(selectedEvidence.scoring_config).map(([key, value]) => (
                        <span key={key}>
                          {formatLabel(key)}: {String(value)}
                        </span>
                      ))
                    ) : (
                      <span>No scoring configuration attached.</span>
                    )}
                  </div>
                </section>

                <section className="motion-evidence-subsection">
                  <h3>Evidence links</h3>
                  <div className="motion-evidence-links">
                    <span>Attached media: {selectedEvidence.snapshot_media_asset_id ?? "none"}</span>
                    <span>Promoted Event: {selectedEvidence.promoted_event_id ?? "none"}</span>
                    <span>Promoted Visit: {selectedEvidence.promoted_visit_id ?? "none"}</span>
                  </div>
                  <div className="detail-actions">
                    <button
                      className="text-action"
                      onClick={() => onOpenMotionEvidence(selectedEvidence.id)}
                      type="button"
                    >
                      Open evidence detail
                    </button>
                    {selectedEvidence.snapshot_media_asset_id ? (
                      <a
                        className="text-action"
                        href={apiClient.mediaFileUrl(selectedEvidence.snapshot_media_asset_id)}
                        rel="noreferrer"
                        target="_blank"
                      >
                        Open media asset
                      </a>
                    ) : null}
                    {selectedEvidence.promoted_event_id ? (
                      <button
                        className="text-action"
                        onClick={() => onOpenEvent(selectedEvidence.promoted_event_id!)}
                      >
                        Open promoted Event
                      </button>
                    ) : null}
                    {selectedEvidence.promoted_visit_id ? (
                      <button
                        className="text-action"
                        onClick={() => onOpenVisit(selectedEvidence.promoted_visit_id!)}
                      >
                        Open promoted Visit
                      </button>
                    ) : null}
                  </div>
                </section>

                <section className="motion-evidence-subsection attached-media-section">
                  <div className="section-heading">
                    <div>
                      <h3>{attachedMediaTitle}</h3>
                      <span className="meta-text">
                        {selectedEvidence.snapshot_media_asset_id
                          ? attachedMediaProvenance
                          : "No media is attached to this evidence."}
                      </span>
                    </div>
                    {selectedEvidence.snapshot_media_asset_id ? (
                      <EvidenceBadge
                        label={
                          selectedHasFolderImportMedia
                            ? "Folder-imported media"
                            : selectedHasSavedPreviewMedia
                              ? "Saved local media"
                              : "Evidence context"
                        }
                        tone="evidence"
                      />
                    ) : (
                      <EvidenceBadge label="No media" tone="quiet" />
                    )}
                  </div>
                  {selectedEvidence.snapshot_media_asset_id ? (
                    <div className="attached-media-context">
                      <div className="attached-media-id-row">
                        <span>MediaAsset ID</span>
                        <strong>{selectedEvidence.snapshot_media_asset_id}</strong>
                      </div>
                      {selectedMediaAsset ? (
                        <MediaAssetPreview asset={selectedMediaAsset} compact />
                      ) : (
                        <div className="notice-panel">
                          <strong>Media details not loaded</strong>
                          <span>
                            The evidence stores this MediaAsset reference. Use the existing media
                            file route to open it.
                          </span>
                        </div>
                      )}
                      <div className="attached-media-provenance">
                        <strong>Review boundary</strong>
                        <span>{attachedMediaProvenance}</span>
                        <span>
                          Media is evidence context only. It does not create Events, Visits,
                          labels, reviewed observations, export-ready truth, or dataset truth.
                        </span>
                        <span>No label has been confirmed yet by Motion Evidence itself.</span>
                      </div>
                      {selectedHasFolderImportMedia ? (
                        <div className="motion-review-context-grid">
                          <ContextItem label="Provider" value="folder_import_future" />
                          <ContextItem
                            label="Original relative path"
                            value={selectedFolderRelativePath ?? "not available"}
                          />
                          <ContextItem
                            label="Import context"
                            value={
                              selectedFolderCopyMode
                                ? formatLabel(selectedFolderCopyMode)
                                : "Imported local media"
                            }
                          />
                          <ContextItem
                            label="Evidence state"
                            value={formatLabel(selectedEvidence.status)}
                            detail="Folder media remains evidence until explicit promotion and correction."
                          />
                        </div>
                      ) : null}
                      <div className="detail-actions">
                        <a
                          className="secondary-action"
                          href={apiClient.mediaFileUrl(selectedEvidence.snapshot_media_asset_id)}
                          rel="noreferrer"
                          target="_blank"
                        >
                          Open media file
                        </a>
                      </div>
                    </div>
                  ) : (
                    <p className="media-empty-note">
                      No media is attached yet. MotionEvidence can still be reviewed, ignored, or
                      promoted without media.
                    </p>
                  )}
                  {selectedEvidence.status === "promoted" ? (
                    <p className="media-readonly-note">
                      Media attachment is locked after promotion so Event/Visit review context stays
                      stable. Correct labels on the promoted review records before export.
                    </p>
                  ) : null}
                  {selectedEvidence.status === "pending" ? (
                    <p className="media-readonly-note">
                      {formatPendingEvidenceBoundaryCopy(selectedEvidence, selectedMediaAsset)}
                    </p>
                  ) : null}
                  {selectedEvidence.status === "ignored" ? (
                    <p className="media-readonly-note">
                      Media attachment is read-only because this evidence was ignored as noise.
                    </p>
                  ) : null}
                </section>

                <section className="notice-panel">
                  <strong>Truth boundary</strong>
                  <span>
                    Motion Evidence can explain why a moment was captured. It does not create
                    reviewed labels, species truth, exports, or dataset coverage truth.
                  </span>
                </section>

                {selectedEvidence.status === "pending" ? (
                  <section className="motion-action-panel">
                    <div className="notice-panel">
                      <strong>Pending evidence</strong>
                      <span>
                        {formatPendingEvidenceBoundaryCopy(selectedEvidence, selectedMediaAsset)}{" "}
                        Ignore noisy evidence or promote explicitly when this should become a
                        reviewable Event/Visit.
                      </span>
                    </div>
                    <form className="motion-attachment-form" onSubmit={attachMediaEvidence}>
                      <div>
                        <strong>Attach existing media</strong>
                        <p>
                          The ID must refer to an existing imported/local media asset for the same
                          stream. This does not create labels, reviewed observations, or export-ready
                          truth.
                        </p>
                        <span className="field-helper">
                          Current attached ID: {selectedEvidence.snapshot_media_asset_id ?? "none"}
                        </span>
                      </div>
                      <label>
                        MediaAsset ID
                        <input
                          list="motion-media-assets"
                          value={attachMediaAssetId}
                          onChange={(event) => setAttachMediaAssetId(event.target.value)}
                          placeholder="media_best_frame_001"
                        />
                        <datalist id="motion-media-assets">
                          {mediaAssets.map((asset) => (
                            <option key={asset.id} value={asset.id}>
                              {asset.original_filename}
                            </option>
                          ))}
                        </datalist>
                      </label>
                      <div className="detail-actions">
                        <button
                          className="secondary-action"
                          disabled={actionId === `${selectedEvidence.id}:attach-media`}
                          type="submit"
                        >
                          {actionId === `${selectedEvidence.id}:attach-media`
                            ? "Updating..."
                            : selectedEvidence.snapshot_media_asset_id
                              ? "Update media"
                              : "Attach media"}
                        </button>
                        {selectedEvidence.snapshot_media_asset_id ? (
                          <button
                            className="text-action"
                            disabled={actionId === `${selectedEvidence.id}:attach-media`}
                            onClick={() => void clearMediaAttachment(selectedEvidence)}
                            type="button"
                          >
                            Clear
                          </button>
                        ) : null}
                      </div>
                    </form>
                    <div className="detail-actions">
                      <button
                        className="secondary-action"
                        disabled={actionId === `${selectedEvidence.id}:ignore`}
                        onClick={() => void ignoreEvidence(selectedEvidence)}
                        type="button"
                      >
                        {actionId === `${selectedEvidence.id}:ignore` ? "Ignoring..." : "Ignore"}
                      </button>
                    </div>
                    <form className="motion-promote-form" onSubmit={promoteEvidence}>
                      <div>
                        <strong>Promote to review</strong>
                        <p>
                          Promotion creates unreviewed Event/Visit evidence only. Correct labels in
                          Review or Visit Detail before export.
                        </p>
                      </div>
                      <label>
                        Event title
                        <input
                          value={eventTitle}
                          onChange={(event) => setEventTitle(event.target.value)}
                          placeholder="Motion evidence in feeder"
                        />
                      </label>
                      <label>
                        Visit label hint
                        <input
                          value={visitLabelHint}
                          onChange={(event) => setVisitLabelHint(event.target.value)}
                          placeholder="unknown_animal"
                        />
                      </label>
                      <label>
                        Notes
                        <textarea
                          value={promotionNotes}
                          onChange={(event) => setPromotionNotes(event.target.value)}
                          placeholder="Why this should become reviewable evidence"
                        />
                      </label>
                      <button
                        className="primary-action"
                        disabled={actionId === `${selectedEvidence.id}:promote`}
                        type="submit"
                      >
                        {actionId === `${selectedEvidence.id}:promote` ? "Promoting..." : "Promote"}
                      </button>
                    </form>
                  </section>
                ) : null}

                {selectedEvidence.status === "promoted" ? (
                  <div className="notice-panel">
                    <strong>Promoted evidence</strong>
                    <span>
                      {promotedEvidenceBoundaryCopy} No label is truth until review/correction.
                      Open the detail pages and correct labels before export.
                      {selectedEvidence.snapshot_media_asset_id
                        ? ` Attached media ${selectedEvidence.snapshot_media_asset_id} remains evidence context.`
                        : ""}
                    </span>
                    <div className="detail-actions">
                      <button
                        className="secondary-action"
                        onClick={() => onOpenMotionEvidence(selectedEvidence.id)}
                        type="button"
                      >
                        Open evidence detail
                      </button>
                      {selectedEvidence.promoted_event_id ? (
                        <button
                          className="secondary-action"
                          onClick={() => onOpenEvent(selectedEvidence.promoted_event_id!)}
                          type="button"
                        >
                          Open promoted Event
                        </button>
                      ) : null}
                      {selectedEvidence.promoted_visit_id ? (
                        <button
                          className="secondary-action"
                          onClick={() => onOpenVisit(selectedEvidence.promoted_visit_id!)}
                          type="button"
                        >
                          Open promoted Visit
                        </button>
                      ) : null}
                    </div>
                  </div>
                ) : null}

                {selectedEvidence.status === "ignored" ? (
                  <div className="notice-panel">
                    <strong>Ignored evidence</strong>
                    <span>
                      This evidence is preserved as noise/evidence history and cannot be promoted.
                    </span>
                  </div>
                ) : null}

                {lastPromotion ? (
                  <div className="notice-panel">
                    <strong>Created reviewable evidence</strong>
                    <span>
                      Promoted to reviewable Event/Visit evidence. Correction still creates truth.
                    </span>
                    <div className="detail-actions">
                      <button
                        className="secondary-action"
                        onClick={() => onOpenMotionEvidence(lastPromotion.evidence.id)}
                        type="button"
                      >
                        Open evidence
                      </button>
                      {lastPromotion.event_id ? (
                        <button
                          className="secondary-action"
                          onClick={() => onOpenEvent(lastPromotion.event_id!)}
                          type="button"
                        >
                          Open Event
                        </button>
                      ) : null}
                      {lastPromotion.visit_id ? (
                        <button
                          className="secondary-action"
                          onClick={() => onOpenVisit(lastPromotion.visit_id!)}
                          type="button"
                        >
                          Open Visit
                        </button>
                      ) : null}
                    </div>
                  </div>
                ) : null}
              </>
            ) : null}
          </section>
        </div>
      ) : null}
    </div>
  );
}

function PromotionResultPanel({
  promotion,
  onOpenMotionEvidence,
  onOpenEvent,
  onOpenVisit,
}: {
  promotion: MotionEvidencePromoteResponse;
  onOpenMotionEvidence: (motionEvidenceId: string) => void;
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
}) {
  return (
    <section className="notice-panel promotion-result-panel">
      <div>
        <strong>Promoted to reviewable Event/Visit</strong>
        <span>Correction still creates truth.</span>
      </div>
      <div className="detail-actions">
        <button
          className="secondary-action"
          onClick={() => onOpenMotionEvidence(promotion.evidence.id)}
          type="button"
        >
          Open evidence
        </button>
        {promotion.event_id ? (
          <button
            className="secondary-action"
            onClick={() => onOpenEvent(promotion.event_id!)}
            type="button"
          >
            Open Event
          </button>
        ) : null}
        {promotion.visit_id ? (
          <button
            className="secondary-action"
            onClick={() => onOpenVisit(promotion.visit_id!)}
            type="button"
          >
            Open Visit
          </button>
        ) : null}
      </div>
    </section>
  );
}

function BulkPromotionResultPanel({
  result,
  onOpenMotionEvidence,
  onOpenEvent,
  onOpenVisit,
}: {
  result: MotionEvidenceBulkActionResponse;
  onOpenMotionEvidence: (motionEvidenceId: string) => void;
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
}) {
  const linkedResults = result.results.filter(
    (item) => item.created_event_id || item.created_visit_id,
  );
  const otherResults = result.results.filter(
    (item) => !item.created_event_id && !item.created_visit_id,
  );

  return (
    <section className="notice-panel promotion-result-panel">
      <div>
        <strong>Bulk promote result</strong>
        <span>
          {result.succeeded_count} promoted, {result.skipped_count} skipped,{" "}
          {result.failed_count} failed. Correction still creates truth.
        </span>
      </div>
      {linkedResults.length > 0 ? (
        <div className="promotion-result-list">
          {linkedResults.map((item) => (
            <div className="promotion-result-item" key={item.motion_evidence_id}>
              <span>{item.motion_evidence_id}</span>
              <div className="detail-actions">
                <button
                  className="text-action"
                  onClick={() => onOpenMotionEvidence(item.motion_evidence_id)}
                  type="button"
                >
                  Open evidence
                </button>
                {item.created_event_id ? (
                  <button
                    className="text-action"
                    onClick={() => onOpenEvent(item.created_event_id!)}
                    type="button"
                  >
                    Open Event
                  </button>
                ) : null}
                {item.created_visit_id ? (
                  <button
                    className="text-action"
                    onClick={() => onOpenVisit(item.created_visit_id!)}
                    type="button"
                  >
                    Open Visit
                  </button>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      ) : null}
      {otherResults.length > 0 ? (
        <details className="promotion-result-details">
          <summary>{otherResults.length} skipped or failed item{otherResults.length === 1 ? "" : "s"}</summary>
          <div className="promotion-result-list">
            {otherResults.map((item) => (
              <div className="promotion-result-item" key={item.motion_evidence_id}>
                <span>
                  {item.motion_evidence_id}: {item.message}
                </span>
                <button
                  className="text-action"
                  onClick={() => onOpenMotionEvidence(item.motion_evidence_id)}
                  type="button"
                >
                  Open evidence
                </button>
              </div>
            ))}
          </div>
        </details>
      ) : null}
    </section>
  );
}

function MotionEvidenceStatusPill({ status }: { status: MotionEvidenceStatus }) {
  const tone = status === "pending" ? "review" : status === "promoted" ? "good" : "quiet";
  return <StatusPill label={formatLabel(status)} tone={tone} />;
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ContextItem({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string | null;
}) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && detail !== value ? <small>{detail}</small> : null}
    </div>
  );
}

function formatEvidenceStatusCopy(evidence: MotionEvidence, asset: MediaAsset | null): string {
  const webhookProvenance = getWebhookEvidenceProvenance(evidence);
  if (evidence.status === "pending") {
    if (webhookProvenance.isWebhook) {
      return pendingWebhookEvidenceBoundaryCopy;
    }
    return formatPendingEvidenceBoundaryCopy(evidence, asset);
  }
  if (evidence.status === "promoted") {
    return `${promotedEvidenceBoundaryCopy} No label has been confirmed yet unless review/correction has been saved.`;
  }
  return "This evidence was ignored and remains preserved as non-truth evidence history.";
}

function formatPendingEvidenceBoundaryCopy(
  evidence: MotionEvidence,
  asset: MediaAsset | null,
): string {
  if (getWebhookEvidenceProvenance(evidence).isWebhook) {
    return pendingWebhookEvidenceBoundaryCopy;
  }
  return isFolderImportMediaEvidence(evidence, asset)
    ? pendingFolderEvidenceBoundaryCopy
    : pendingEvidenceBoundaryCopy;
}

function formatMotionEvidenceMediaBadge(
  evidence: MotionEvidence,
  asset: MediaAsset | null,
): string {
  if (getWebhookEvidenceProvenance(evidence).isWebhook) {
    return "Webhook metadata evidence";
  }
  if (isFolderImportMediaEvidence(evidence, asset)) {
    return "Folder-imported media";
  }
  if (isSavedPreviewMediaEvidence(evidence, asset)) {
    return "Saved preview media";
  }
  return "Media attached";
}

function getWebhookEvidenceProvenance(evidence: MotionEvidence): WebhookEvidenceProvenance {
  const providerKey = formatOptionalConfigValue(evidence.scoring_config.provider_key);
  const source = formatOptionalConfigValue(evidence.scoring_config.source);
  const isWebhook =
    providerKey === "webhook_future" || source === "webhook_metadata_motion_event";

  return {
    isWebhook,
    providerKey,
    candidateType: formatOptionalConfigValue(evidence.scoring_config.candidate_type),
    externalEventId: formatOptionalConfigValue(evidence.scoring_config.external_event_id),
    externalLabel: formatOptionalConfigValue(evidence.scoring_config.external_label_untrusted),
    externalConfidence: formatOptionalConfigValue(
      evidence.scoring_config.external_confidence_untrusted,
    ),
    externalTimestamp: formatOptionalConfigValue(evidence.scoring_config.external_timestamp),
  };
}

function formatOptionalConfigValue(
  value: string | number | boolean | string[] | null | undefined,
): string | null {
  if (value === undefined || value === null) {
    return null;
  }
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  return String(value);
}

function formatWebhookValue(value: string | null): string {
  return value && value.trim() ? value : "not provided";
}

function isSavedPreviewMediaEvidence(evidence: MotionEvidence, asset: MediaAsset | null): boolean {
  if (!evidence.snapshot_media_asset_id) {
    return false;
  }

  const source = String(evidence.scoring_config.source ?? "").toLowerCase();
  const notes = `${evidence.notes ?? ""}\n${asset?.notes ?? ""}`.toLowerCase();
  return (
    source === "saved_preview_media_asset" ||
    notes.includes("created from saved mediaasset") ||
    notes.includes("saved explicit external_url still-image preview") ||
    notes.includes("provider_key=external_url")
  );
}

function isFolderImportMediaEvidence(evidence: MotionEvidence, asset: MediaAsset | null): boolean {
  if (!evidence.snapshot_media_asset_id) {
    return false;
  }

  const source = String(evidence.scoring_config.source ?? "").toLowerCase();
  const notes = `${evidence.notes ?? ""}\n${asset?.notes ?? ""}`.toLowerCase();
  return (
    source === "folder_import_media_asset" ||
    notes.includes("folder-imported mediaasset") ||
    notes.includes("provider_key=folder_import_future")
  );
}

function formatAttachedMediaProvenance(
  evidence: MotionEvidence,
  asset: MediaAsset | null,
): string {
  if (!evidence.snapshot_media_asset_id) {
    return "No media is attached to this evidence.";
  }

  if (isSavedPreviewMediaEvidence(evidence, asset)) {
    const host = extractSafeNoteValue(asset?.notes ?? "", "url_host");
    if (host) {
      return `This evidence is linked to saved local media from external URL host ${host}.`;
    }
    if ((asset?.notes ?? "").toLowerCase().includes("provider_key=external_url")) {
      return "This evidence is linked to saved local media from an external URL preview.";
    }
  }

  if (isFolderImportMediaEvidence(evidence, asset)) {
    const relativePath = extractSafeRelativePath(asset?.notes ?? "", "relative_source_path");
    if (relativePath) {
      return `This evidence is linked to folder-imported local media from ${relativePath}.`;
    }
    return "This evidence is linked to folder-imported local media.";
  }

  return "This evidence is linked to saved local media.";
}

function extractSafeNoteValue(notes: string, key: string): string | null {
  const prefixes = [`${key}=`, `${key}:`];
  const line = notes
    .split(/\r?\n/)
    .find((entry) => prefixes.some((prefix) => entry.trim().startsWith(prefix)));
  if (!line) {
    return null;
  }

  const rawValue = prefixes.reduce<string | null>((current, prefix) => {
    if (current !== null) {
      return current;
    }
    const trimmed = line.trim();
    return trimmed.startsWith(prefix) ? trimmed.slice(prefix.length).trim() : null;
  }, null);
  if (!rawValue) {
    return null;
  }

  const safeValue = rawValue.replace(/[^A-Za-z0-9.:\[\]-]/g, "").slice(0, 120);
  return safeValue || null;
}

function extractSafeRelativePath(notes: string, key: string): string | null {
  const rawValue = extractRawNoteValue(notes, key);
  if (!rawValue) {
    return null;
  }

  const normalized = rawValue.trim().replace(/\\/g, "/");
  if (
    !normalized ||
    normalized.startsWith("/") ||
    normalized.startsWith("~/") ||
    /^[A-Za-z]:/.test(normalized)
  ) {
    return null;
  }

  const segments = normalized.split("/").filter(Boolean);
  if (segments.length === 0 || segments.some((segment) => segment === "..")) {
    return null;
  }

  return segments
    .map((segment) => segment.replace(/[^A-Za-z0-9._ -]/g, "-").slice(0, 80))
    .join("/")
    .slice(0, 180);
}

function extractRawNoteValue(notes: string, key: string): string | null {
  const prefixes = [`${key}=`, `${key}:`];
  const line = notes
    .split(/\r?\n/)
    .find((entry) => prefixes.some((prefix) => entry.trim().startsWith(prefix)));
  if (!line) {
    return null;
  }

  const trimmed = line.trim();
  const prefix = prefixes.find((entry) => trimmed.startsWith(entry));
  return prefix ? trimmed.slice(prefix.length).trim() : null;
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatRange(evidence: MotionEvidence): string {
  if (evidence.start_time || evidence.end_time) {
    return `${evidence.start_time ?? "unknown"} to ${evidence.end_time ?? "unknown"}`;
  }
  if (
    evidence.start_frame_index !== null &&
    evidence.start_frame_index !== undefined ||
    evidence.end_frame_index !== null &&
    evidence.end_frame_index !== undefined
  ) {
    return `frames ${evidence.start_frame_index ?? "?"}-${evidence.end_frame_index ?? "?"}`;
  }
  return "range unknown";
}

function parsePeakChangedRatio(value: string): number {
  const trimmed = value.trim();
  const numeric = trimmed.endsWith("%") ? Number(trimmed.slice(0, -1)) / 100 : Number(trimmed);
  const ratio = !trimmed.endsWith("%") && numeric > 1 ? numeric / 100 : numeric;
  if (!Number.isFinite(ratio) || ratio < 0 || ratio > 1) {
    throw new Error("Peak change must be a percentage from 0% to 100% or a decimal from 0 to 1.");
  }
  return ratio;
}

function parsePositiveInteger(value: string, label: string): number {
  const parsed = Number(value.trim());
  if (!Number.isInteger(parsed) || parsed < 1) {
    throw new Error(`${label} must be a whole number of at least 1.`);
  }
  return parsed;
}

function parseOptionalFrameIndex(value: string, label: string): number | null {
  if (!value.trim()) {
    return null;
  }
  const parsed = Number(value.trim());
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new Error(`${label} must be a whole number of at least 0.`);
  }
  return parsed;
}

function parseNonNegativeInteger(value: string, label: string): number {
  const parsed = Number(value.trim());
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new Error(`${label} must be a whole number of at least 0.`);
  }
  return parsed;
}

function parseNonNegativeNumber(value: string, label: string): number {
  const parsed = Number(value.trim());
  if (!Number.isFinite(parsed) || parsed < 0) {
    throw new Error(`${label} must be a number of at least 0.`);
  }
  return parsed;
}

function parseRatio(value: string, label: string): number {
  const parsed = Number(value.trim());
  if (!Number.isFinite(parsed) || parsed < 0 || parsed > 1) {
    throw new Error(`${label} must be a number from 0 to 1.`);
  }
  return parsed;
}

function parseNormalizedBound(value: string, label: string): number {
  const parsed = Number(value.trim());
  if (!Number.isFinite(parsed) || parsed < 0 || parsed > 1) {
    throw new Error(`${label} must be a normalized number from 0 to 1.`);
  }
  return parsed;
}

function validateZoneBounds(left: number, top: number, right: number, bottom: number) {
  if (right <= left) {
    throw new Error("Zone right must be greater than zone left.");
  }
  if (bottom <= top) {
    throw new Error("Zone bottom must be greater than zone top.");
  }
}

function parseFrameSequence(rawValue: string): number[][][] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(rawValue);
  } catch {
    throw new Error("Frame planes must be valid JSON.");
  }

  if (!Array.isArray(parsed) || parsed.length < 2) {
    throw new Error("Frame planes must be an array with at least 2 frame planes.");
  }

  let expectedWidth: number | null = null;
  let expectedHeight: number | null = null;
  return parsed.map((plane, planeIndex) => {
    if (!Array.isArray(plane) || plane.length === 0) {
      throw new Error(`Frame plane ${planeIndex + 1} must be a non-empty 2D array.`);
    }

    const height = plane.length;
    const rows = plane.map((row, rowIndex) => {
      if (!Array.isArray(row) || row.length === 0) {
        throw new Error(`Frame plane ${planeIndex + 1}, row ${rowIndex + 1} must be non-empty.`);
      }
      return row.map((value, columnIndex) => {
        if (typeof value !== "number" || !Number.isFinite(value)) {
          throw new Error(
            `Frame plane ${planeIndex + 1}, row ${rowIndex + 1}, column ${
              columnIndex + 1
            } must be a finite number.`,
          );
        }
        return value;
      });
    });

    const width = rows[0].length;
    if (rows.some((row) => row.length !== width)) {
      throw new Error(`Frame plane ${planeIndex + 1} must be rectangular.`);
    }
    if (expectedWidth === null) {
      expectedWidth = width;
      expectedHeight = height;
    } else if (width !== expectedWidth || height !== expectedHeight) {
      throw new Error("All frame planes must have matching dimensions.");
    }

    return rows;
  });
}

function parseScoringConfig(rawValue: string): Record<string, string | number | boolean> {
  if (!rawValue.trim()) {
    return {};
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(rawValue);
  } catch {
    throw new Error("Scoring config must be valid JSON.");
  }

  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Scoring config must be a JSON object.");
  }

  const config: Record<string, string | number | boolean> = {};
  Object.entries(parsed).forEach(([key, value]) => {
    if (
      typeof value !== "string" &&
      typeof value !== "number" &&
      typeof value !== "boolean"
    ) {
      throw new Error("Scoring config values must be strings, numbers, or booleans.");
    }
    if (typeof value === "number" && !Number.isFinite(value)) {
      throw new Error("Scoring config number values must be finite.");
    }
    config[key] = value;
  });

  return config;
}

function formatBestMoment(evidence: MotionEvidence): string {
  if (evidence.best_frame_time) {
    return evidence.best_frame_time;
  }
  if (evidence.best_frame_index !== null && evidence.best_frame_index !== undefined) {
    return `frame ${evidence.best_frame_index}`;
  }
  return "not selected";
}

function formatSource(
  sourceId: string | null | undefined,
  sourceById: Map<string, CameraSource>,
): string {
  if (!sourceId) {
    return "none";
  }
  return sourceById.get(sourceId)?.name ?? sourceId;
}

function formatStream(
  streamId: string | null | undefined,
  streamById: Map<string, Stream>,
): string {
  if (!streamId) {
    return "none";
  }
  return streamById.get(streamId)?.name ?? streamId;
}
