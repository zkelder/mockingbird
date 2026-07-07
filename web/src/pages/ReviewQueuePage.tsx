import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { apiClient } from "../api/client";
import type {
  BoundingBox,
  DetectionProposal,
  DetectionRun,
  MotionEvidence,
  ReviewCorrectionResult,
  ReviewIdentificationSummary,
  ReviewLabel,
  ReviewQueueBulkCorrectionResponse,
  ReviewQueueBulkCorrectionTargetType,
  ReviewQueueItem,
  TaxonomyLabel,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { EvidenceBadge } from "../components/EvidenceBadge";
import { MediaAssetPreview } from "../components/MediaAssetPreview";
import { PageHeader } from "../components/PageHeader";
import { ReviewFilterTabs, type ReviewFilterOption } from "../components/ReviewFilterTabs";
import { StatusPill } from "../components/StatusPill";
import { TaxonomyLabelInput } from "../components/TaxonomyLabelInput";
import { TaxonomyBadge } from "../components/TaxonomyBadge";
import {
  displayTaxonomyLabel,
  findTaxonomyLabel,
  isBirdReviewLabel,
  isFalsePositiveLabel,
  isUnknownAnimalLabel,
  isUnknownBirdLabel,
  taxonomyKey,
} from "../components/taxonomy";
import { formatDateTime, formatLabel } from "../utils";

type ReviewFilter = "all" | "bird_species" | "unknown_animals" | "false_positives";
type ReviewTargetFilter = "all" | "event" | "visit";
type ReviewEvidenceFilter =
  | "all"
  | "has_media"
  | "has_detection_proposal"
  | "has_motion_evidence"
  | "no_proposal_evidence";
export type ReviewStatusFilter = "unreviewed" | "reviewed" | "all";
type LabelValidationStatus = "empty" | "suggested" | "recent" | "taxonomy" | "custom";

export interface ReviewQueueInitialContext {
  source?: "classifier-readiness" | "live-motion";
  sourceLabel?: string | null;
  search?: string | null;
  correctionLabel?: string | null;
  status?: ReviewStatusFilter | null;
}

interface LabelHelperGroup {
  title: string;
  labels: string[];
}

interface CorrectionHistoryGroup {
  key: string;
  targetType: string;
  targetId: string;
  latest: ReviewLabel;
  older: ReviewLabel[];
}

interface ReviewEvidenceProposal {
  proposal: DetectionProposal;
  relation: "linked" | "same_media";
}

interface ReviewItemFilterMetadata {
  detectionProposalCount: number;
  hasDetectionProposal: boolean;
  hasMedia: boolean;
  hasMotionEvidence: boolean;
  motionEvidenceCount: number;
  searchText: string;
  sourceId: string | null;
  sourceName: string | null;
  streamId: string | null;
  streamName: string | null;
}

interface SourceStreamFilterOption {
  value: string;
  label: string;
  count: number;
}

interface ActiveFilterChip {
  key: string;
  label: string;
  onClear: () => void;
}

type LastCorrectionSummary =
  | {
      mode: "single";
      targetType: string;
      targetId: string;
      label: string;
      reviewLabelId: string;
      remaining: number;
    }
  | {
      mode: "bulk";
      targetType: ReviewQueueBulkCorrectionTargetType;
      requestedCount: number;
      succeededCount: number;
      skippedCount: number;
      failedCount: number;
      label: string;
      reviewLabelIds: string[];
      correctedTargetIds: string[];
      remaining: number;
    };

function reviewQueueTargetType(item: ReviewQueueItem): ReviewQueueBulkCorrectionTargetType {
  if (item.target_type === "visit" || item.target_type === "event") {
    return item.target_type;
  }
  return item.visit_id ? "visit" : "event";
}

function reviewQueueTargetId(item: ReviewQueueItem): string {
  return item.target_id || item.visit_id || item.event_id || item.id.replace(/^review-queue-/, "");
}

function reviewItemZoneName(item: ReviewQueueItem): string {
  return item.zone_name ?? item.primary_zone_name ?? item.zone_id ?? item.primary_zone_id ?? "No zone";
}

function reviewItemZoneLabel(item: ReviewQueueItem): string {
  const zoneName = reviewItemZoneName(item);
  const zoneType = item.zone_type ?? item.primary_zone_type;
  if (zoneType) {
    return `${zoneName} (${formatLabel(zoneType)})`;
  }
  return zoneName;
}

function reviewQueueSourceLabel(
  item: ReviewQueueItem,
  metadata?: Pick<ReviewItemFilterMetadata, "sourceId" | "sourceName">,
): string {
  return item.source_name ?? metadata?.sourceName ?? item.source_id ?? metadata?.sourceId ?? "Unknown source";
}

function reviewQueueStreamLabel(
  item: ReviewQueueItem,
  metadata?: Pick<ReviewItemFilterMetadata, "streamId" | "streamName">,
): string {
  return item.stream_name ?? metadata?.streamName ?? item.stream_id ?? metadata?.streamId ?? "Unknown stream";
}

function isLiveActivityReviewItem(item: ReviewQueueItem): boolean {
  return Boolean(item.activity_session_id);
}

function detectionCountLabel(count: number): string {
  return `${count} detection${count === 1 ? "" : "s"}`;
}

function formatPercent(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) {
    return "n/a";
  }
  const percent = value * 100;
  if (percent === 0) {
    return "0%";
  }
  if (Math.abs(percent) < 0.1) {
    return `${percent.toFixed(2)}%`;
  }
  if (Math.abs(percent) < 10) {
    return `${percent.toFixed(2).replace(/\.?0+$/, "")}%`;
  }
  return `${Math.round(percent)}%`;
}

function liveActivitySummary(item: ReviewQueueItem): string {
  const detectionCount = item.detection_count || 1;
  return `${reviewItemZoneName(item)} visit - ${detectionCountLabel(detectionCount)} - best change ${formatPercent(
    item.best_changed_ratio,
  )}`;
}

function formatQualityWarning(warning: string): string {
  return warning.includes(" ") ? warning : formatLabel(warning);
}

function focusCropOverlayStyle(box: BoundingBox | null | undefined): CSSProperties | undefined {
  if (!box) {
    return undefined;
  }
  return {
    left: `${box.x * 100}%`,
    top: `${box.y * 100}%`,
    width: `${box.width * 100}%`,
    height: `${box.height * 100}%`,
  };
}

function focusCropPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function focusCropBoxLabel(box: BoundingBox | null | undefined): string {
  if (!box) {
    return "No crop box";
  }
  return `Box ${focusCropPercent(box.x)}, ${focusCropPercent(box.y)} / ${focusCropPercent(
    box.width,
  )} x ${focusCropPercent(box.height)}`;
}

function focusCropPixelLabel(item: ReviewQueueItem): string {
  const box = item.focus_crop_box_pixels;
  if (!box) {
    return "Pixel box unavailable";
  }
  return `Pixels ${box.x}, ${box.y} / ${box.width} x ${box.height}`;
}

function focusCropSummary(item: ReviewQueueItem): string {
  if (!item.focus_crop_available) {
    return "Full best frame";
  }
  return item.focus_crop_label ?? "Activity focus";
}

function reviewIdentificationLabel(item: ReviewQueueItem): string | null {
  const identification = item.identification;
  if (!identification) {
    return null;
  }
  return (
    identification.suggestion?.suggested_label ??
    identification.proposal?.suggested_species ??
    identification.proposal?.suggested_subject_label ??
    identification.proposal?.label ??
    null
  );
}

function reviewIdentificationConfidence(
  identification: ReviewIdentificationSummary | null | undefined,
): number | null {
  if (!identification) {
    return null;
  }
  return identification.suggestion?.confidence ?? identification.proposal?.confidence ?? null;
}

function reviewIdentificationStatusTone(
  identification: ReviewIdentificationSummary | null | undefined,
): "good" | "review" | "quiet" {
  if (!identification) {
    return "quiet";
  }
  if (
    identification.status === "suggestion_present" ||
    identification.status === "proposal_present" ||
    identification.status === "suggestion_created" ||
    identification.status === "proposal_created"
  ) {
    return "review";
  }
  if (identification.status === "configured_available" || identification.status === "ready") {
    return "good";
  }
  return "quiet";
}

function reviewIdentificationStatusLabel(identification: ReviewIdentificationSummary): string {
  if (identification.status === "configured_available") {
    return "Configured available";
  }
  if (identification.status === "unavailable_no_adapter") {
    return "No analyzer";
  }
  if (identification.status === "unsupported_media") {
    return "Unsupported media";
  }
  return formatLabel(identification.status);
}

function reviewIdentificationCanRun(identification: ReviewIdentificationSummary): boolean {
  return identification.can_run_on_best_frame || identification.can_run;
}

function reviewIdentificationLabelValues(items: ReviewQueueItem[]): string[] {
  return uniqueLabelValues(items.map(reviewIdentificationLabel));
}

function isBulkCorrectionEligible(item: ReviewQueueItem): boolean {
  return item.review_status === "needs_review";
}

function matchesTargetFilter(item: ReviewQueueItem, targetFilter: ReviewTargetFilter): boolean {
  return targetFilter === "all" || reviewQueueTargetType(item) === targetFilter;
}

function matchesStatusFilter(item: ReviewQueueItem, statusFilter: ReviewStatusFilter): boolean {
  if (statusFilter === "all") {
    return true;
  }
  if (statusFilter === "reviewed") {
    return item.review_status === "reviewed";
  }
  return item.review_status === "needs_review";
}

function reviewQueueSearchText(item: ReviewQueueItem, taxonomyLabels: TaxonomyLabel[]): string {
  const suggestedLabel = item.suggested_label ?? "";
  const media = item.media_asset;
  const identification = item.identification;
  const identificationLabel = reviewIdentificationLabel(item) ?? "";

  return [
    item.id,
    item.item_type,
    item.target_type,
    item.target_id,
    item.title,
    item.stream_id,
    item.stream_name ?? "",
    item.source_id ?? "",
    item.source_name ?? "",
    item.event_id ?? "",
    item.visit_id ?? "",
    item.primary_zone_id ?? "",
    item.primary_zone_name ?? "",
    item.primary_zone_type ?? "",
    item.zone_id ?? "",
    item.zone_name ?? "",
    item.zone_type ?? "",
    item.best_media_asset_id ?? "",
    item.activity_session_id ?? "",
    item.activity_started_at ?? "",
    item.activity_last_seen_at ?? "",
    item.detection_count.toString(),
    item.best_frame_sequence?.toString() ?? "",
    item.best_changed_ratio?.toString() ?? "",
    item.best_changed_pixels?.toString() ?? "",
    item.best_total_scored_pixels?.toString() ?? "",
    item.effective_threshold_used?.toString() ?? "",
    item.threshold_source ?? "",
    item.fine_motion_applied ? "fine motion applied" : "",
    ...item.image_quality_warnings,
    suggestedLabel,
    item.suggestion_id ?? "",
    item.suggestion_confidence?.toString() ?? "",
    item.suggestion_reason ?? "",
    item.focus_crop_available ? "activity focus crop" : "full best frame",
    item.focus_crop_source ?? "",
    item.focus_crop_label ?? "",
    item.focus_crop_box_normalized
      ? `${item.focus_crop_box_normalized.x} ${item.focus_crop_box_normalized.y} ${item.focus_crop_box_normalized.width} ${item.focus_crop_box_normalized.height}`
      : "",
    item.focus_crop_box_pixels
      ? `${item.focus_crop_box_pixels.x} ${item.focus_crop_box_pixels.y} ${item.focus_crop_box_pixels.width} ${item.focus_crop_box_pixels.height}`
      : "",
    ...item.focus_crop_warnings,
    displayTaxonomyLabel(suggestedLabel || "unknown", taxonomyLabels),
    identification?.status ?? "",
    identification?.message ?? "",
    identification?.adapter_id ?? "",
    identification?.adapter_name ?? "",
    identification?.adapter_kind ?? "",
    identification?.adapter_status ?? "",
    identification?.setup_hint ?? "",
    identification?.focus_crop_label ?? "",
    identification?.focus_crop_source ?? "",
    ...(identification?.focus_crop_warnings ?? []),
    identificationLabel,
    displayTaxonomyLabel(identificationLabel || "unknown", taxonomyLabels),
    identification?.suggestion?.id ?? "",
    identification?.suggestion?.adapter_name ?? "",
    identification?.proposal?.id ?? "",
    identification?.proposal?.label ?? "",
    identification?.proposal?.suggested_subject_label ?? "",
    identification?.proposal?.suggested_species ?? "",
    item.reason,
    media?.id ?? "",
    media?.filename ?? "",
    media?.original_filename ?? "",
    media?.notes ?? "",
  ]
    .join(" ")
    .toLowerCase();
}

function uniqueLabelValues(values: Array<string | null | undefined>): string[] {
  const seenKeys = new Set<string>();
  const uniqueValues: string[] = [];

  for (const value of values) {
    const cleaned = value?.trim();
    if (!cleaned) {
      continue;
    }
    const key = taxonomyKey(cleaned);
    if (!key || seenKeys.has(key)) {
      continue;
    }
    seenKeys.add(key);
    uniqueValues.push(cleaned);
  }

  return uniqueValues;
}

function recentReviewLabelValues(reviewLabels: ReviewLabel[]): string[] {
  return uniqueLabelValues(
    [...reviewLabels]
      .sort(
        (first, second) =>
          new Date(second.created_at).getTime() - new Date(first.created_at).getTime(),
      )
      .map((label) => label.label),
  );
}

function taxonomyHelperValues(taxonomyLabels: TaxonomyLabel[]): string[] {
  return uniqueLabelValues(
    taxonomyLabels
      .filter((label) => label.is_reviewable)
      .sort((first, second) => {
        const firstOrder = first.sort_order ?? Number.MAX_SAFE_INTEGER;
        const secondOrder = second.sort_order ?? Number.MAX_SAFE_INTEGER;
        return firstOrder === secondOrder
          ? first.display_name.localeCompare(second.display_name)
          : firstOrder - secondOrder;
      })
      .map((label) => label.label),
  );
}

function labelHelperGroups(
  suggestedLabels: string[],
  recentLabels: string[],
  taxonomyLabels: string[],
): LabelHelperGroup[] {
  const usedKeys = new Set<string>();
  const takeUnique = (values: string[], limit: number) => {
    const selected: string[] = [];
    for (const value of values) {
      const key = taxonomyKey(value);
      if (!key || usedKeys.has(key)) {
        continue;
      }
      usedKeys.add(key);
      selected.push(value);
      if (selected.length >= limit) {
        break;
      }
    }
    return selected;
  };

  return [
    { title: "Suggested", labels: takeUnique(suggestedLabels, 3) },
    { title: "Recent", labels: takeUnique(recentLabels, 4) },
    { title: "Taxonomy", labels: takeUnique(taxonomyLabels, 5) },
  ].filter((group) => group.labels.length > 0);
}

function labelMatchesHelperValue(value: string, helperLabels: string[]): boolean {
  const key = taxonomyKey(value);
  return helperLabels.some((label) => taxonomyKey(label) === key);
}

function classifyCorrectionLabel(
  value: string,
  {
    recentLabels,
    suggestedLabels,
    taxonomyLabelValues,
    taxonomyLabels,
  }: {
    recentLabels: string[];
    suggestedLabels: string[];
    taxonomyLabelValues: string[];
    taxonomyLabels: TaxonomyLabel[];
  },
): LabelValidationStatus {
  const cleaned = value.trim();
  if (!cleaned) {
    return "empty";
  }
  if (labelMatchesHelperValue(cleaned, suggestedLabels)) {
    return "suggested";
  }
  if (labelMatchesHelperValue(cleaned, recentLabels)) {
    return "recent";
  }
  if (
    labelMatchesHelperValue(cleaned, taxonomyLabelValues) ||
    findTaxonomyLabel(cleaned, taxonomyLabels)
  ) {
    return "taxonomy";
  }
  return "custom";
}

function compareReviewLabelsNewestFirst(first: ReviewLabel, second: ReviewLabel): number {
  const timeDelta =
    new Date(second.created_at).getTime() - new Date(first.created_at).getTime();
  return timeDelta !== 0 ? timeDelta : second.id.localeCompare(first.id);
}

function sortReviewLabelsNewestFirst(labels: ReviewLabel[]): ReviewLabel[] {
  return [...labels].sort(compareReviewLabelsNewestFirst);
}

function reviewTargetKey(targetType: string, targetId: string): string {
  return `${targetType}:${targetId}`;
}

function proposalRelationForReviewItem(
  item: ReviewQueueItem,
  proposal: DetectionProposal,
): ReviewEvidenceProposal["relation"] | null {
  if (
    (item.visit_id && proposal.visit_id === item.visit_id) ||
    (item.event_id && proposal.event_id === item.event_id)
  ) {
    return "linked";
  }

  if (
    item.media_asset?.id &&
    proposal.media_asset_id === item.media_asset.id &&
    !proposal.event_id &&
    !proposal.visit_id
  ) {
    return "same_media";
  }

  return null;
}

function reviewEvidenceProposals(
  item: ReviewQueueItem,
  proposals: DetectionProposal[],
): ReviewEvidenceProposal[] {
  return proposals
    .map((proposal) => {
      const relation = proposalRelationForReviewItem(item, proposal);
      return relation ? { proposal, relation } : null;
    })
    .filter((value): value is ReviewEvidenceProposal => value !== null)
    .sort((first, second) => {
      if (first.relation !== second.relation) {
        return first.relation === "linked" ? -1 : 1;
      }
      return (
        new Date(second.proposal.created_at).getTime() -
        new Date(first.proposal.created_at).getTime()
      );
    });
}

function reviewMotionEvidenceForQueueItem(
  item: ReviewQueueItem,
  motionEvidence: MotionEvidence[],
): MotionEvidence[] {
  return motionEvidence
    .filter(
      (evidence) =>
        (item.visit_id && evidence.promoted_visit_id === item.visit_id) ||
        (item.event_id && evidence.promoted_event_id === item.event_id) ||
        (item.media_asset?.id && evidence.snapshot_media_asset_id === item.media_asset.id),
    )
    .sort(
      (first, second) =>
        new Date(second.created_at).getTime() - new Date(first.created_at).getTime(),
    );
}

function reviewItemFilterMetadata(
  item: ReviewQueueItem,
  proposals: DetectionProposal[],
  motionEvidence: MotionEvidence[],
  taxonomyLabels: TaxonomyLabel[],
  detectionRunsById: Map<string, DetectionRun>,
): ReviewItemFilterMetadata {
  const proposalEvidence = reviewEvidenceProposals(item, proposals);
  const motionEvidenceItems = reviewMotionEvidenceForQueueItem(item, motionEvidence);
  const sourceId =
    item.source_id ??
    item.media_asset?.source_id ??
    motionEvidenceItems.find((evidence) => evidence.source_id)?.source_id ??
    null;
  const sourceName = item.source_name ?? null;
  const streamId =
    item.stream_id ||
    item.media_asset?.stream_id ||
    motionEvidenceItems.find((evidence) => evidence.stream_id)?.stream_id ||
    null;
  const streamName = item.stream_name ?? null;
  const proposalSearch = proposalEvidence.flatMap(({ proposal }) => {
    const run = detectionRunsById.get(proposal.run_id);
    return [
      proposal.id,
      proposal.label,
      proposal.suggested_subject_label,
      proposal.suggested_species ?? "",
      proposal.status,
      proposal.run_id,
      run?.source ?? "",
      run?.summary ?? "",
    ];
  });
  const motionSearch = motionEvidenceItems.flatMap((evidence) => [
    evidence.id,
    evidence.status,
    evidence.source_id ?? "",
    evidence.stream_id ?? "",
    evidence.zone_id,
    evidence.snapshot_media_asset_id ?? "",
    evidence.notes ?? "",
  ]);
  const hasMedia =
    Boolean(item.media_asset) ||
    proposalEvidence.some(({ proposal }) => Boolean(proposal.media_asset_id)) ||
    motionEvidenceItems.some((evidence) => Boolean(evidence.snapshot_media_asset_id));

  return {
    detectionProposalCount: proposalEvidence.length,
    hasDetectionProposal: proposalEvidence.length > 0,
    hasMedia,
    hasMotionEvidence: motionEvidenceItems.length > 0,
    motionEvidenceCount: motionEvidenceItems.length,
    searchText: [
      reviewQueueSearchText(item, taxonomyLabels),
      sourceId ?? "",
      sourceName ?? "",
      streamId ?? "",
      streamName ?? "",
      item.media_asset?.source_id ?? "",
      item.media_asset?.stream_id ?? "",
      ...proposalSearch,
      ...motionSearch,
    ]
      .join(" ")
      .toLowerCase(),
    sourceId,
    sourceName,
    streamId,
    streamName,
  };
}

function matchesEvidenceFilter(
  metadata: ReviewItemFilterMetadata,
  evidenceFilter: ReviewEvidenceFilter,
): boolean {
  if (evidenceFilter === "has_media") {
    return metadata.hasMedia;
  }
  if (evidenceFilter === "has_detection_proposal") {
    return metadata.hasDetectionProposal;
  }
  if (evidenceFilter === "has_motion_evidence") {
    return metadata.hasMotionEvidence;
  }
  if (evidenceFilter === "no_proposal_evidence") {
    return !metadata.hasDetectionProposal;
  }
  return true;
}

function matchesSourceStreamFilter(
  metadata: ReviewItemFilterMetadata,
  sourceStreamFilter: string,
): boolean {
  if (sourceStreamFilter === "all") {
    return true;
  }
  if (sourceStreamFilter.startsWith("stream:")) {
    return metadata.streamId === sourceStreamFilter.slice("stream:".length);
  }
  if (sourceStreamFilter.startsWith("source:")) {
    return metadata.sourceId === sourceStreamFilter.slice("source:".length);
  }
  return true;
}

function sourceStreamFilterOptions(
  metadataById: Map<string, ReviewItemFilterMetadata>,
): SourceStreamFilterOption[] {
  const streamCounts = new Map<string, { count: number; label: string }>();
  const sourceCounts = new Map<string, { count: number; label: string }>();

  for (const metadata of metadataById.values()) {
    if (metadata.streamId) {
      const existing = streamCounts.get(metadata.streamId);
      streamCounts.set(metadata.streamId, {
        count: (existing?.count ?? 0) + 1,
        label: metadata.streamName ?? existing?.label ?? metadata.streamId,
      });
    }
    if (metadata.sourceId) {
      const existing = sourceCounts.get(metadata.sourceId);
      sourceCounts.set(metadata.sourceId, {
        count: (existing?.count ?? 0) + 1,
        label: metadata.sourceName ?? existing?.label ?? metadata.sourceId,
      });
    }
  }

  return [
    {
      count: metadataById.size,
      label: "All streams/sources",
      value: "all",
    },
    ...[...streamCounts.entries()]
      .sort(([first], [second]) => first.localeCompare(second))
      .map(([streamId, { count, label }]) => ({
        count,
        label: `Stream ${label}`,
        value: `stream:${streamId}`,
      })),
    ...[...sourceCounts.entries()]
      .sort(([first], [second]) => first.localeCompare(second))
      .map(([sourceId, { count, label }]) => ({
        count,
        label: `Source ${label}`,
        value: `source:${sourceId}`,
      })),
  ];
}

function reviewEvidenceFilterLabel(evidenceFilter: ReviewEvidenceFilter): string {
  const labels: Record<ReviewEvidenceFilter, string> = {
    all: "All evidence",
    has_media: "Has best frame",
    has_detection_proposal: "Has suggestion evidence",
    has_motion_evidence: "Has activity evidence",
    no_proposal_evidence: "No suggestion evidence",
  };
  return labels[evidenceFilter];
}

function sourceStreamFilterLabel(
  sourceStreamFilter: string,
  options: SourceStreamFilterOption[],
): string {
  return options.find((option) => option.value === sourceStreamFilter)?.label ?? sourceStreamFilter;
}

function formatConfidence(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function compactIdList(ids: string[], emptyLabel: string): string {
  if (ids.length === 0) {
    return emptyLabel;
  }
  if (ids.length <= 3) {
    return ids.join(", ");
  }
  return `${ids.slice(0, 3).join(", ")} +${ids.length - 3} more`;
}

function reviewLabelsForQueueItem(
  item: ReviewQueueItem,
  reviewLabels: ReviewLabel[],
): ReviewLabel[] {
  const targetType = reviewQueueTargetType(item);
  const targetId = reviewQueueTargetId(item);
  return sortReviewLabelsNewestFirst(
    reviewLabels.filter(
      (label) => label.target_type === targetType && label.target_id === targetId,
    ),
  );
}

function correctionHistoryGroups(reviewLabels: ReviewLabel[]): CorrectionHistoryGroup[] {
  const groups = new Map<string, ReviewLabel[]>();

  for (const reviewLabel of sortReviewLabelsNewestFirst(reviewLabels)) {
    const key = reviewTargetKey(reviewLabel.target_type, reviewLabel.target_id);
    groups.set(key, [...(groups.get(key) ?? []), reviewLabel]);
  }

  return Array.from(groups.entries()).map(([key, labels]) => ({
    key,
    targetType: labels[0]?.target_type ?? "target",
    targetId: labels[0]?.target_id ?? key,
    latest: labels[0],
    older: labels.slice(1),
  }));
}

interface ReviewQueuePageProps {
  items: ReviewQueueItem[];
  initialContext?: ReviewQueueInitialContext | null;
  onCreateCorrection: (
    item: ReviewQueueItem,
    label: string,
    notes: string,
  ) => Promise<ReviewCorrectionResult>;
  onInitialContextConsumed?: () => void;
  onOpenEvent: (eventId: string) => void;
  onOpenAnalytics: () => void;
  onOpenClassifierReadiness: () => void;
  onOpenExports: () => void;
  onOpenVisit: (visitId: string) => void;
}

export function ReviewQueuePage({
  items,
  initialContext,
  onCreateCorrection,
  onInitialContextConsumed,
  onOpenEvent,
  onOpenAnalytics,
  onOpenClassifierReadiness,
  onOpenExports,
  onOpenVisit,
}: ReviewQueuePageProps) {
  const [queueItems, setQueueItems] = useState<ReviewQueueItem[]>(items);
  const [drafts, setDrafts] = useState<Record<string, { label: string; notes: string }>>({});
  const [bulkDraft, setBulkDraft] = useState({ label: "", notes: "" });
  const [bulkResult, setBulkResult] = useState<ReviewQueueBulkCorrectionResponse | null>(null);
  const [lastCorrectionSummary, setLastCorrectionSummary] =
    useState<LastCorrectionSummary | null>(null);
  const [selectedTargetIds, setSelectedTargetIds] = useState<string[]>([]);
  const [detectionProposals, setDetectionProposals] = useState<DetectionProposal[]>([]);
  const [detectionRuns, setDetectionRuns] = useState<DetectionRun[]>([]);
  const [motionEvidence, setMotionEvidence] = useState<MotionEvidence[]>([]);
  const [taxonomyLabels, setTaxonomyLabels] = useState<TaxonomyLabel[]>([]);
  const [reviewLabels, setReviewLabels] = useState<ReviewLabel[]>([]);
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>("all");
  const [textSearch, setTextSearch] = useState("");
  const [targetTypeFilter, setTargetTypeFilter] = useState<ReviewTargetFilter>("all");
  const [evidenceFilter, setEvidenceFilter] = useState<ReviewEvidenceFilter>("all");
  const [sourceStreamFilter, setSourceStreamFilter] = useState("all");
  const [reviewStatusFilter, setReviewStatusFilter] =
    useState<ReviewStatusFilter>("unreviewed");
  const [readinessHandoffLabel, setReadinessHandoffLabel] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [identifyingId, setIdentifyingId] = useState<string | null>(null);
  const [isBulkSaving, setIsBulkSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const queueCounts = useMemo(
    () =>
      queueItems.reduce<Record<ReviewFilter, number>>(
        (counts, item) => {
          counts.all += 1;
          if (isBirdReviewLabel(item.suggested_label, taxonomyLabels)) {
            counts.bird_species += 1;
          } else if (isUnknownAnimalLabel(item.suggested_label, taxonomyLabels)) {
            counts.unknown_animals += 1;
          } else if (isFalsePositiveLabel(item.suggested_label, taxonomyLabels)) {
            counts.false_positives += 1;
          }
          return counts;
        },
        { all: 0, bird_species: 0, unknown_animals: 0, false_positives: 0 },
      ),
    [queueItems, taxonomyLabels],
  );

  const reviewFilters: ReviewFilterOption<ReviewFilter>[] = [
    { value: "all", label: "All", count: queueCounts.all },
    { value: "bird_species", label: "Bird/species", count: queueCounts.bird_species },
    { value: "unknown_animals", label: "Unknown animals", count: queueCounts.unknown_animals },
    { value: "false_positives", label: "False positives", count: queueCounts.false_positives },
  ];

  const detectionRunsById = useMemo(
    () => new Map(detectionRuns.map((run) => [run.id, run])),
    [detectionRuns],
  );

  const filterMetadataByItemId = useMemo(
    () =>
      new Map(
        queueItems.map((item) => [
          item.id,
          reviewItemFilterMetadata(
            item,
            detectionProposals,
            motionEvidence,
            taxonomyLabels,
            detectionRunsById,
          ),
        ]),
      ),
    [detectionProposals, detectionRunsById, motionEvidence, queueItems, taxonomyLabels],
  );

  const sourceStreamOptions = useMemo(
    () => sourceStreamFilterOptions(filterMetadataByItemId),
    [filterMetadataByItemId],
  );

  const filteredItems = useMemo(
    () => {
      const normalizedSearch = textSearch.trim().toLowerCase();

      return queueItems.filter((item) => {
        const metadata = filterMetadataByItemId.get(item.id);
        if (!metadata) {
          return false;
        }
        if (
          reviewFilter === "bird_species" &&
          !isBirdReviewLabel(item.suggested_label, taxonomyLabels)
        ) {
          return false;
        }
        if (
          reviewFilter === "unknown_animals" &&
          !isUnknownAnimalLabel(item.suggested_label, taxonomyLabels)
        ) {
          return false;
        }
        if (
          reviewFilter === "false_positives" &&
          !isFalsePositiveLabel(item.suggested_label, taxonomyLabels)
        ) {
          return false;
        }

        if (!matchesTargetFilter(item, targetTypeFilter)) {
          return false;
        }
        if (!matchesStatusFilter(item, reviewStatusFilter)) {
          return false;
        }
        if (!matchesEvidenceFilter(metadata, evidenceFilter)) {
          return false;
        }
        if (!matchesSourceStreamFilter(metadata, sourceStreamFilter)) {
          return false;
        }
        if (
          normalizedSearch &&
          !metadata.searchText.includes(normalizedSearch)
        ) {
          return false;
        }

        return true;
      });
    },
    [
      evidenceFilter,
      filterMetadataByItemId,
      queueItems,
      reviewFilter,
      reviewStatusFilter,
      sourceStreamFilter,
      targetTypeFilter,
      textSearch,
      taxonomyLabels,
    ],
  );

  const selectedItems = useMemo(
    () =>
      queueItems.filter((item) => selectedTargetIds.includes(reviewQueueTargetId(item))),
    [queueItems, selectedTargetIds],
  );

  const selectedEligibleItems = useMemo(
    () => selectedItems.filter(isBulkCorrectionEligible),
    [selectedItems],
  );

  const hasEligibleBulkSelection =
    selectedTargetIds.length > 0 && selectedEligibleItems.length === selectedTargetIds.length;

  const selectedTargetType = selectedItems[0]
    ? reviewQueueTargetType(selectedItems[0])
    : null;

  const visibleEligibleItems = useMemo(
    () => filteredItems.filter(isBulkCorrectionEligible),
    [filteredItems],
  );

  const activeFilterChips = useMemo<ActiveFilterChip[]>(() => {
    const chips: ActiveFilterChip[] = [];
    if (textSearch.trim()) {
      chips.push({
        key: "search",
        label: `Search: ${textSearch.trim()}`,
        onClear: () => {
          setTextSearch("");
          setReadinessHandoffLabel(null);
        },
      });
    }
    if (reviewFilter !== "all") {
      chips.push({
        key: "category",
        label: `Group: ${reviewFilters.find((filter) => filter.value === reviewFilter)?.label ?? reviewFilter}`,
        onClear: () => setReviewFilter("all"),
      });
    }
    if (targetTypeFilter !== "all") {
      chips.push({
        key: "target",
        label: `Type: ${formatLabel(targetTypeFilter)}`,
        onClear: () => setTargetTypeFilter("all"),
      });
    }
    if (evidenceFilter !== "all") {
      chips.push({
        key: "evidence",
        label: `Evidence: ${reviewEvidenceFilterLabel(evidenceFilter)}`,
        onClear: () => setEvidenceFilter("all"),
      });
    }
    if (sourceStreamFilter !== "all") {
      chips.push({
        key: "source-stream",
        label: sourceStreamFilterLabel(sourceStreamFilter, sourceStreamOptions),
        onClear: () => setSourceStreamFilter("all"),
      });
    }
    if (reviewStatusFilter !== "all") {
      chips.push({
        key: "status",
        label: `Status: ${formatLabel(reviewStatusFilter)}`,
        onClear: () => setReviewStatusFilter("all"),
      });
    }
    return chips;
  }, [
    evidenceFilter,
    reviewFilter,
    reviewFilters,
    reviewStatusFilter,
    sourceStreamFilter,
    sourceStreamOptions,
    targetTypeFilter,
    textSearch,
  ]);

  const recentLabelValues = useMemo(
    () => recentReviewLabelValues(reviewLabels),
    [reviewLabels],
  );

  const taxonomyLabelValues = useMemo(
    () => taxonomyHelperValues(taxonomyLabels),
    [taxonomyLabels],
  );

  const visibleSuggestedLabelValues = useMemo(
    () =>
      uniqueLabelValues([
        ...filteredItems.map((item) => item.suggested_label),
        ...reviewIdentificationLabelValues(filteredItems),
      ]),
    [filteredItems],
  );

  const bulkSuggestedLabelValues = useMemo(
    () =>
      uniqueLabelValues([
        ...selectedItems.map((item) => item.suggested_label),
        ...visibleEligibleItems.map((item) => item.suggested_label),
        ...reviewIdentificationLabelValues(selectedItems),
        ...reviewIdentificationLabelValues(visibleEligibleItems),
      ]),
    [selectedItems, visibleEligibleItems],
  );

  const bulkLabelHelperGroups = useMemo(
    () => labelHelperGroups(bulkSuggestedLabelValues, recentLabelValues, taxonomyLabelValues),
    [bulkSuggestedLabelValues, recentLabelValues, taxonomyLabelValues],
  );

  const bulkLabelValidation = useMemo(
    () =>
      classifyCorrectionLabel(bulkDraft.label, {
        recentLabels: recentLabelValues,
        suggestedLabels: bulkSuggestedLabelValues,
        taxonomyLabelValues,
        taxonomyLabels,
      }),
    [bulkDraft.label, bulkSuggestedLabelValues, recentLabelValues, taxonomyLabelValues, taxonomyLabels],
  );

  const correctionAuditGroups = useMemo(
    () => correctionHistoryGroups(reviewLabels),
    [reviewLabels],
  );

  useEffect(() => {
    if (!initialContext) {
      return;
    }

    const nextSearch = initialContext.search?.trim() ?? "";
    const nextCorrectionLabel = initialContext.correctionLabel?.trim() ?? "";
    const nextSourceLabel =
      initialContext.sourceLabel?.trim() || nextSearch || nextCorrectionLabel || null;

    if (nextSearch) {
      setTextSearch(nextSearch);
    }
    if (initialContext.source === "live-motion") {
      setReviewFilter("all");
      setTargetTypeFilter("all");
      setEvidenceFilter("all");
      setSourceStreamFilter("all");
    }
    if (initialContext.status) {
      setReviewStatusFilter(initialContext.status);
    }
    if (nextCorrectionLabel) {
      setBulkDraft((current) =>
        current.label.trim() ? current : { ...current, label: nextCorrectionLabel },
      );
    }
    setSelectedTargetIds([]);
    setBulkResult(null);
    setReadinessHandoffLabel(
      initialContext.source === "classifier-readiness" ? nextSourceLabel : null,
    );
    onInitialContextConsumed?.();
  }, [initialContext, onInitialContextConsumed]);

  useEffect(() => {
    setQueueItems(items);
  }, [items]);

  useEffect(() => {
    setSelectedTargetIds([]);
    setBulkResult(null);
  }, [
    evidenceFilter,
    reviewFilter,
    reviewStatusFilter,
    sourceStreamFilter,
    targetTypeFilter,
    textSearch,
  ]);

  useEffect(() => {
    if (!sourceStreamOptions.some((option) => option.value === sourceStreamFilter)) {
      setSourceStreamFilter("all");
    }
  }, [sourceStreamFilter, sourceStreamOptions]);

  useEffect(() => {
    const availableTargetIds = new Set(
      queueItems.filter(isBulkCorrectionEligible).map(reviewQueueTargetId),
    );
    setSelectedTargetIds((current) =>
      current.filter((targetId) => availableTargetIds.has(targetId)),
    );
  }, [queueItems]);

  useEffect(() => {
    const visibleEligibleTargetIds = new Set(visibleEligibleItems.map(reviewQueueTargetId));
    setSelectedTargetIds((current) =>
      current.filter((targetId) => visibleEligibleTargetIds.has(targetId)),
    );
  }, [visibleEligibleItems]);

  useEffect(() => {
    let isMounted = true;

    async function loadTaxonomy() {
      try {
        const labels = await apiClient.getTaxonomyLabels();
        if (isMounted) {
          setTaxonomyLabels(labels);
        }
      } catch (caught) {
        if (isMounted) {
          setMessage(caught instanceof Error ? caught.message : "Could not load taxonomy labels.");
        }
      }
    }

    void loadTaxonomy();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function loadDetectionEvidence() {
      try {
        const [nextProposals, nextRuns, nextMotionEvidence] = await Promise.all([
          apiClient.getDetectionProposals(),
          apiClient.getDetectionRuns(),
          apiClient.listMotionEvidence({ status: "all" }),
        ]);
        if (isMounted) {
          setDetectionProposals(nextProposals);
          setDetectionRuns(nextRuns);
          setMotionEvidence(nextMotionEvidence.motion_evidence);
        }
      } catch {
        if (isMounted) {
          setDetectionProposals([]);
          setDetectionRuns([]);
          setMotionEvidence([]);
        }
      }
    }

    void loadDetectionEvidence();

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function loadReviewLabels() {
      try {
        const labels = await apiClient.getReviewLabels();
        if (isMounted) {
          setReviewLabels(labels);
        }
      } catch {
        if (isMounted) {
          setReviewLabels([]);
        }
      }
    }

    void loadReviewLabels();

    return () => {
      isMounted = false;
    };
  }, []);

  async function refreshReviewLabels() {
    try {
      setReviewLabels(await apiClient.getReviewLabels());
    } catch {
      // Recent helpers are convenience only; correction truth is handled by submit.
    }
  }

  async function refreshDetectionEvidence() {
    const [nextProposals, nextRuns, nextMotionEvidence] = await Promise.all([
      apiClient.getDetectionProposals(),
      apiClient.getDetectionRuns(),
      apiClient.listMotionEvidence({ status: "all" }),
    ]);
    setDetectionProposals(nextProposals);
    setDetectionRuns(nextRuns);
    setMotionEvidence(nextMotionEvidence.motion_evidence);
  }

  function canSelectForBulk(item: ReviewQueueItem): boolean {
    return (
      isBulkCorrectionEligible(item) &&
      (!selectedTargetType || reviewQueueTargetType(item) === selectedTargetType)
    );
  }

  function toggleBulkSelection(item: ReviewQueueItem, selected: boolean) {
    const targetId = reviewQueueTargetId(item);
    setSelectedTargetIds((current) => {
      if (selected) {
        return current.includes(targetId) ? current : [...current, targetId];
      }
      return current.filter((selectedTargetId) => selectedTargetId !== targetId);
    });
  }

  function selectVisibleBulkItems() {
    const targetType =
      selectedTargetType ??
      (targetTypeFilter === "event" || targetTypeFilter === "visit"
        ? targetTypeFilter
        : visibleEligibleItems[0]
          ? reviewQueueTargetType(visibleEligibleItems[0])
          : null);
    if (!targetType) {
      return;
    }
    setSelectedTargetIds(
      visibleEligibleItems
        .filter((item) => reviewQueueTargetType(item) === targetType)
        .map(reviewQueueTargetId),
    );
  }

  function clearBulkSelection() {
    setSelectedTargetIds([]);
    setBulkResult(null);
  }

  function clearReadinessSearch() {
    setTextSearch("");
    setReadinessHandoffLabel(null);
    setSelectedTargetIds([]);
    setBulkResult(null);
  }

  function resetReviewFilters() {
    setReviewFilter("all");
    setTextSearch("");
    setTargetTypeFilter("all");
    setEvidenceFilter("all");
    setSourceStreamFilter("all");
    setReviewStatusFilter("all");
    setReadinessHandoffLabel(null);
    setSelectedTargetIds([]);
    setBulkResult(null);
  }

  async function saveBulkCorrection() {
    const trimmedLabel = bulkDraft.label.trim();
    if (!trimmedLabel) {
      setMessage("Add a label before saving a bulk correction.");
      return;
    }
    if (!selectedTargetType || !hasEligibleBulkSelection) {
      setMessage("Select review items before saving a bulk correction.");
      return;
    }

    const confirmed = window.confirm(
      "Apply this correction to selected review items?\n\n" +
        "Corrections are truth for analytics and exports.",
    );
    if (!confirmed) {
      return;
    }

    setIsBulkSaving(true);
    setMessage(null);
    setBulkResult(null);
    setLastCorrectionSummary(null);
    try {
      const result = await apiClient.bulkCorrectReviewQueueItems({
        target_type: selectedTargetType,
        target_ids: selectedTargetIds,
        label: trimmedLabel,
        notes: bulkDraft.notes.trim() || undefined,
      });
      const refreshedQueue = await apiClient.getReviewQueue();
      setQueueItems(refreshedQueue);
      if (result.succeeded_count > 0) {
        setSelectedTargetIds([]);
        setLastCorrectionSummary({
          correctedTargetIds: result.results
            .filter((item) => item.status === "succeeded")
            .map((item) => item.target_id),
          failedCount: result.failed_count,
          label: trimmedLabel,
          mode: "bulk",
          requestedCount: result.requested_count,
          reviewLabelIds: result.results
            .map((item) => item.created_review_label_id)
            .filter((id): id is string => Boolean(id)),
          remaining: refreshedQueue.filter(isBulkCorrectionEligible).length,
          skippedCount: result.skipped_count,
          succeededCount: result.succeeded_count,
          targetType: selectedTargetType,
        });
      }
      await refreshReviewLabels();
      setBulkResult(result);
      setMessage(
        `${result.succeeded_count} correction${
          result.succeeded_count === 1 ? "" : "s"
        } saved as local dataset truth.`,
      );
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Bulk correction could not be saved.");
    } finally {
      setIsBulkSaving(false);
    }
  }

  async function saveCorrectionWithLabel(
    item: ReviewQueueItem,
    label: string,
    notes: string,
    acceptedSuggestionId?: string | null,
  ) {
    const trimmedLabel = label.trim();
    if (!trimmedLabel) {
      setMessage("Add a label before saving a correction.");
      return;
    }

    setSavingId(item.id);
    setMessage(null);
    setLastCorrectionSummary(null);
    try {
      const result = await onCreateCorrection(item, trimmedLabel, notes.trim());
      if (acceptedSuggestionId) {
        try {
          await apiClient.updateSpeciesSuggestionStatus(acceptedSuggestionId, "accepted");
        } catch {
          // The ReviewLabel is truth; suggestion status is evidence polish only.
        }
      }
      await refreshReviewLabels();
      setLastCorrectionSummary({
        label: result.review_label.label,
        mode: "single",
        remaining: result.review_queue_count,
        reviewLabelId: result.review_label.id,
        targetId: result.review_label.target_id,
        targetType: result.review_label.target_type,
      });
      setMessage(
        `Added to Bird Log. Correction saved as local dataset truth. ${result.review_queue_count} item${
          result.review_queue_count === 1 ? "" : "s"
        } still need review.`,
      );
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Correction could not be saved.");
    } finally {
      setSavingId(null);
    }
  }

  async function saveCorrection(item: ReviewQueueItem) {
    const draft = drafts[item.id] ?? { label: item.suggested_label ?? "", notes: "" };
    await saveCorrectionWithLabel(item, draft.label, draft.notes);
  }

  async function runIdentificationAssist(item: ReviewQueueItem) {
    const targetType = reviewQueueTargetType(item);
    const targetId = reviewQueueTargetId(item);
    const identification = item.identification;
    const mediaAssetId = item.best_media_asset_id ?? item.media_asset?.id ?? null;

    setIdentifyingId(item.id);
    setMessage(null);
    try {
      const result = await apiClient.identifyReviewQueueItem(targetType, targetId, {
        adapter_id: identification?.adapter_id ?? undefined,
        media_asset_id: mediaAssetId ?? undefined,
      });
      const refreshedQueue = await apiClient.getReviewQueue();
      setQueueItems(refreshedQueue);
      await refreshDetectionEvidence();
      setMessage(result.identification.message);
    } catch (caught) {
      setMessage(
        caught instanceof Error ? caught.message : "Identification assist could not run.",
      );
    } finally {
      setIdentifyingId(null);
    }
  }

  async function rejectIdentificationSuggestion(item: ReviewQueueItem) {
    const suggestionId = item.identification?.suggestion?.id;
    if (!suggestionId) {
      return;
    }
    setIdentifyingId(item.id);
    setMessage(null);
    try {
      await apiClient.updateSpeciesSuggestionStatus(suggestionId, "rejected");
      const refreshedQueue = await apiClient.getReviewQueue();
      setQueueItems(refreshedQueue);
      setMessage("Suggestion rejected as evidence. No review truth was created.");
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Suggestion could not be rejected.");
    } finally {
      setIdentifyingId(null);
    }
  }

  async function rejectIdentificationProposal(item: ReviewQueueItem) {
    const proposalId = item.identification?.proposal?.id;
    if (!proposalId) {
      return;
    }
    setIdentifyingId(item.id);
    setMessage(null);
    try {
      await apiClient.decideDetectionProposal(proposalId, {
        decision: "reject",
        notes: "Rejected from Review Queue identification assist.",
      });
      const refreshedQueue = await apiClient.getReviewQueue();
      setQueueItems(refreshedQueue);
      await refreshDetectionEvidence();
      setMessage("Suggestion evidence rejected. No review truth was created.");
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Suggestion evidence could not be rejected.");
    } finally {
      setIdentifyingId(null);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Dataset-grade truth"
        title="Review Queue"
        description="Confirm or correct outdoor activity before it becomes analytics and local export data."
        actions={
          <button className="secondary-action" onClick={onOpenExports}>
            Open Dataset Exports
          </button>
        }
      />
      {message ? <div className="notice-panel">{message}</div> : null}
      {lastCorrectionSummary ? (
        <CorrectionSuccessPanel
          onContinueReview={() => setLastCorrectionSummary(null)}
          onOpenAnalytics={onOpenAnalytics}
          onOpenClassifierReadiness={onOpenClassifierReadiness}
          onOpenExports={onOpenExports}
          summary={lastCorrectionSummary}
          taxonomyLabels={taxonomyLabels}
        />
      ) : null}
      {readinessHandoffLabel ? (
        <section className="notice-panel review-handoff-notice">
          <div>
            <strong>Classifier readiness gap: {formatLabel(readinessHandoffLabel)}</strong>
            <span>
              Search and bulk label were prefilled. Select review items and apply a correction
              explicitly to create truth.
            </span>
          </div>
          <button className="text-action" onClick={clearReadinessSearch} type="button">
            Clear search
          </button>
        </section>
      ) : null}
      {queueItems.length === 0 ? (
        <EmptyState
          title="No review items need correction"
          description="Review Queue contains Events and Visits that need user correction. Live candidates appear here only after explicit handoff, and Bird Log updates only after correction."
          action={
            <button className="primary-action" onClick={onOpenExports}>
              Open Dataset Exports
            </button>
          }
        />
      ) : null}
      {queueItems.length > 0 ? (
        <section className="panel species-review-panel">
          <div className="section-heading">
            <div>
              <h2>Review candidates</h2>
              <span className="meta-text">
                Suggestions are evidence only. Corrected labels are local dataset truth.
              </span>
            </div>
            <EvidenceBadge label={`${queueCounts.bird_species} bird/species`} tone="review" />
          </div>
          <ReviewFilterTabs
            activeFilter={reviewFilter}
            filters={reviewFilters}
            label="Review queue filters"
            onChange={setReviewFilter}
          />
          <div className="review-narrow-controls">
            <label>
              Search
              <input
                onChange={(event) => setTextSearch(event.target.value)}
                placeholder="label, stream, source, zone, suggestion"
                type="search"
                value={textSearch}
              />
            </label>
            <label>
              Item type
              <select
                onChange={(event) =>
                  setTargetTypeFilter(event.target.value as ReviewTargetFilter)
                }
                value={targetTypeFilter}
              >
                <option value="all">All item types</option>
                <option value="visit">Visits</option>
                <option value="event">Events</option>
              </select>
            </label>
            <label>
              Evidence
              <select
                onChange={(event) =>
                  setEvidenceFilter(event.target.value as ReviewEvidenceFilter)
                }
                value={evidenceFilter}
              >
                <option value="all">All evidence states</option>
                <option value="has_media">Has best frame</option>
                <option value="has_detection_proposal">Has suggestion evidence</option>
                <option value="has_motion_evidence">Has activity evidence</option>
                <option value="no_proposal_evidence">No suggestion evidence</option>
              </select>
            </label>
            {sourceStreamOptions.length > 1 ? (
              <label>
                Source / Stream
                <select
                  onChange={(event) => setSourceStreamFilter(event.target.value)}
                  value={sourceStreamFilter}
                >
                  {sourceStreamOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label} ({option.count})
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <label>
              Status
              <select
                onChange={(event) =>
                  setReviewStatusFilter(event.target.value as ReviewStatusFilter)
                }
                value={reviewStatusFilter}
              >
                <option value="unreviewed">Unreviewed</option>
                <option value="reviewed">Reviewed</option>
                <option value="all">All statuses</option>
              </select>
            </label>
            <button className="secondary-action" onClick={resetReviewFilters} type="button">
              Reset filters
            </button>
          </div>
          <div className="review-filter-summary">
            <strong>
              Showing {filteredItems.length} of {queueItems.length} review items
            </strong>
            <span>{visibleEligibleItems.length} visible eligible</span>
            <span>{selectedTargetIds.length} selected</span>
          </div>
          <div className="review-active-filter-row">
            {activeFilterChips.length > 0 ? (
              activeFilterChips.map((chip) => (
                <button
                  className="review-filter-chip"
                  key={chip.key}
                  onClick={chip.onClear}
                  type="button"
                >
                  {chip.label}
                </button>
              ))
            ) : (
              <span className="meta-text">No extra filters active.</span>
            )}
          </div>
        </section>
      ) : null}
      {queueItems.length > 0 ? (
        <section className="panel review-bulk-panel">
          <div className="section-heading">
            <div>
              <h2>Bulk correction</h2>
              <span className="meta-text">
                Applies your correction to selected items. Corrections are truth for analytics and exports.
              </span>
            </div>
            <EvidenceBadge
              label={`${selectedTargetIds.length} selected / ${visibleEligibleItems.length} visible eligible`}
              tone={selectedTargetIds.length > 0 ? "review" : "quiet"}
            />
          </div>
          <span className="meta-text">
            Bulk correction applies only to selected unreviewed items.
          </span>
          <div className="review-bulk-form">
            <TaxonomyLabelInput
              label="Bulk corrected label"
              labels={taxonomyLabels}
              value={bulkDraft.label}
              placeholder="reviewed species, label, unknown, or false_positive"
              onChange={(nextLabel) =>
                setBulkDraft((current) => ({ ...current, label: nextLabel }))
              }
            />
            <LabelValidationLine status={bulkLabelValidation} />
            <LabelHelperChips
              groups={bulkLabelHelperGroups}
              onSelect={(nextLabel) =>
                setBulkDraft((current) => ({ ...current, label: nextLabel }))
              }
              taxonomyLabels={taxonomyLabels}
            />
            <label>
              Notes
              <textarea
                value={bulkDraft.notes}
                onChange={(event) =>
                  setBulkDraft((current) => ({ ...current, notes: event.target.value }))
                }
                placeholder="optional shared review note"
              />
            </label>
            <div className="review-bulk-actions">
              <button
                className="secondary-action"
                disabled={visibleEligibleItems.length === 0 || isBulkSaving}
                onClick={selectVisibleBulkItems}
                type="button"
              >
                Select visible eligible
              </button>
              <button
                className="secondary-action"
                disabled={selectedTargetIds.length === 0 || isBulkSaving}
                onClick={clearBulkSelection}
                type="button"
              >
                Clear selection
              </button>
              <button
                className="primary-action"
                disabled={
                  !hasEligibleBulkSelection || !bulkDraft.label.trim() || isBulkSaving
                }
                onClick={() => void saveBulkCorrection()}
                type="button"
              >
                {isBulkSaving ? "Applying..." : "Apply correction"}
              </button>
            </div>
          </div>
          {selectedTargetType ? (
            <span className="meta-text">
              Bulk action is limited to selected {selectedTargetType} items.
            </span>
          ) : null}
          {bulkResult ? (
            <div className="notice-panel review-bulk-result">
              <strong>Bulk correction result</strong>
              <span>
                {bulkResult.succeeded_count} saved, {bulkResult.skipped_count} skipped,{" "}
                {bulkResult.failed_count} failed.
              </span>
            </div>
          ) : null}
        </section>
      ) : null}
      <CorrectionAuditPanel
        groups={correctionAuditGroups}
        onOpenEvent={onOpenEvent}
        onOpenVisit={onOpenVisit}
        taxonomyLabels={taxonomyLabels}
      />
      <div className="queue-list">
        {filteredItems.map((item) => {
          const fromDetectionEvidence =
            item.event_id?.startsWith("event-detection") || item.visit_id?.startsWith("visit-detection");
          const draft = drafts[item.id] ?? {
            label: item.suggested_label ?? "",
            notes: "",
          };
          const suggestedTaxonomy = findTaxonomyLabel(item.suggested_label, taxonomyLabels);
          const isSpeciesReview = isBirdReviewLabel(item.suggested_label, taxonomyLabels);
          const targetId = reviewQueueTargetId(item);
          const isSelected = selectedTargetIds.includes(targetId);
          const isSelectable = canSelectForBulk(item);
          const identification = item.identification ?? null;
          const identificationLabel = reviewIdentificationLabel(item);
          const itemHelperGroups = labelHelperGroups(
            uniqueLabelValues([
              item.suggested_label,
              identificationLabel,
              ...visibleSuggestedLabelValues,
            ]),
            recentLabelValues,
            taxonomyLabelValues,
          );
          const itemSuggestedLabelValues = uniqueLabelValues([
            item.suggested_label,
            identificationLabel,
            ...visibleSuggestedLabelValues,
          ]);
          const itemLabelValidation = classifyCorrectionLabel(draft.label, {
            recentLabels: recentLabelValues,
            suggestedLabels: itemSuggestedLabelValues,
            taxonomyLabelValues,
            taxonomyLabels,
          });
          const itemReviewLabels = reviewLabelsForQueueItem(item, reviewLabels);
          const latestItemCorrection = itemReviewLabels[0] ?? null;
          const previousItemCorrections = itemReviewLabels.slice(1);
          const itemEvidenceProposals = reviewEvidenceProposals(item, detectionProposals);
          const itemSourceStreamMetadata = filterMetadataByItemId.get(item.id);
          const sourceLabel = reviewQueueSourceLabel(item, itemSourceStreamMetadata);
          const streamLabel = reviewQueueStreamLabel(item, itemSourceStreamMetadata);
          const zoneLabel = reviewItemZoneLabel(item);
          const isLiveActivity = isLiveActivityReviewItem(item);
          const hasActivityDiagnostics =
            isLiveActivity ||
            item.focus_crop_available ||
            item.best_frame_sequence != null ||
            item.best_changed_ratio != null ||
            item.effective_threshold_used != null ||
            item.threshold_source != null;
          const focusCropOverlay =
            item.focus_crop_available && item.focus_crop_box_normalized ? (
              <span
                className="review-focus-crop-overlay"
                style={focusCropOverlayStyle(item.focus_crop_box_normalized)}
              >
                <span>Activity focus</span>
              </span>
            ) : null;
          return (
            <article className="queue-card" key={item.id}>
              <div className="item-title-row">
                <div>
                  <span className="meta-text">{formatLabel(item.item_type)}</span>
                  <h2>{item.title}</h2>
                </div>
                <div className="detail-actions">
                  {item.visit_id ? (
                    <button className="text-action" onClick={() => onOpenVisit(item.visit_id!)}>
                      Visit detail
                    </button>
                  ) : item.event_id ? (
                    <button className="text-action" onClick={() => onOpenEvent(item.event_id!)}>
                      Event detail
                    </button>
                  ) : null}
                  <StatusPill label={formatLabel(item.review_status)} tone="review" />
                </div>
              </div>
              <label className="checkbox-row review-bulk-select">
                <input
                  checked={isSelected}
                  disabled={!isSelectable || isBulkSaving}
                  onChange={(event) => toggleBulkSelection(item, event.target.checked)}
                  type="checkbox"
                />
                {isSelectable
                  ? "Select for bulk correction"
                  : !isBulkCorrectionEligible(item)
                    ? "Only unreviewed items are eligible for bulk correction"
                    : selectedTargetType
                      ? `Bulk selection currently expects ${selectedTargetType} items`
                      : "Bulk selection is unavailable for this item"}
              </label>
              <p>
                {item.reason} Suggestion evidence is not truth; your correction becomes local
                dataset truth.
              </p>
              <div
                className={`review-candidate-context${
                  item.media_asset ? "" : " review-candidate-context-no-media"
                }`}
              >
                {item.media_asset ? (
                  <div className="review-candidate-media">
                    <MediaAssetPreview
                      asset={item.media_asset}
                      compact
                      surfaceOverlay={focusCropOverlay}
                    />
                  </div>
                ) : null}
                <div className="review-candidate-body">
                  <div className="review-candidate-summary-row">
                    <EvidenceBadge
                      label={isLiveActivity ? "Live monitor candidate" : "Review candidate"}
                      tone={isLiveActivity ? "review" : "quiet"}
                    />
                    <strong>
                      {isLiveActivity
                        ? liveActivitySummary(item)
                        : `${reviewItemZoneName(item)} ${formatLabel(item.item_type)}`}
                    </strong>
                  </div>
                  <div className="review-candidate-path">
                    <span>Source: {sourceLabel}</span>
                    <span>Stream: {streamLabel}</span>
                    <span>Zone: {zoneLabel}</span>
                  </div>
                  <div className="review-candidate-metrics">
                    {item.detection_count > 0 ? (
                      <span>{detectionCountLabel(item.detection_count)}</span>
                    ) : null}
                    {item.near_miss_count > 0 ? (
                      <span>{item.near_miss_count} near miss{item.near_miss_count === 1 ? "" : "es"}</span>
                    ) : null}
                    {item.candidate_frame_count > 0 ? (
                      <span>{item.candidate_frame_count} candidate frame{item.candidate_frame_count === 1 ? "" : "s"}</span>
                    ) : null}
                    {item.best_changed_ratio != null ? (
                      <span>Best change {formatPercent(item.best_changed_ratio)}</span>
                    ) : null}
                    {item.best_frame_sequence != null ? (
                      <span>Best frame {item.best_frame_sequence}</span>
                    ) : null}
                    {item.best_media_asset_id ? (
                      <span>Best frame saved</span>
                    ) : null}
                  </div>
                  <div
                    className={`review-focus-context${
                      item.focus_crop_available ? "" : " review-focus-context-muted"
                    }`}
                  >
                    <strong>{focusCropSummary(item)}</strong>
                    {item.focus_crop_available ? (
                      <>
                        <span>{formatLabel(item.focus_crop_source)} context</span>
                        <span>Focus overlay on best frame</span>
                        <span>Full frame stays available</span>
                      </>
                    ) : (
                      <span>
                        {item.focus_crop_warnings.length > 0
                          ? item.focus_crop_warnings.map(formatQualityWarning).join(", ")
                          : "No focus crop"}
                      </span>
                    )}
                  </div>
                  {item.image_quality_warnings.length > 0 ? (
                    <div className="review-quality-warnings">
                      <strong>Quality warnings</strong>
                      {item.image_quality_warnings.map((warning) => (
                        <span key={warning}>{formatQualityWarning(warning)}</span>
                      ))}
                    </div>
                  ) : null}
                  {hasActivityDiagnostics ? (
                    <details className="review-diagnostic-details">
                      <summary>Activity diagnostics</summary>
                      <div className="review-diagnostic-grid">
                        <span>Session: {item.activity_session_id ?? "n/a"}</span>
                        <span>
                          Window:{" "}
                          {item.activity_started_at ? formatDateTime(item.activity_started_at) : "n/a"} -{" "}
                          {item.activity_last_seen_at
                            ? formatDateTime(item.activity_last_seen_at)
                            : "n/a"}
                        </span>
                        <span>
                          Changed pixels: {item.best_changed_pixels ?? "n/a"} /{" "}
                          {item.best_total_scored_pixels ?? "n/a"}
                        </span>
                        <span>Frames evaluated: {item.frames_evaluated_count}</span>
                        <span>Saved candidates: {item.saved_candidate_count}</span>
                        <span>Threshold: {item.effective_threshold_used ?? "n/a"}</span>
                        <span>Threshold source: {item.threshold_source ?? "n/a"}</span>
                        <span>Fine motion: {item.fine_motion_applied ? "Applied" : "Not applied"}</span>
                        {item.focus_crop_available ? (
                          <>
                            <span>{focusCropBoxLabel(item.focus_crop_box_normalized)}</span>
                            <span>{focusCropPixelLabel(item)}</span>
                          </>
                        ) : null}
                      </div>
                    </details>
                  ) : null}
                </div>
              </div>
              <div className="queue-meta">
                <EvidenceBadge
                  label={fromDetectionEvidence ? "Converted suggestion evidence" : "Review candidate"}
                />
                {isLiveActivity ? <EvidenceBadge label="Live activity session" tone="review" /> : null}
                {isSpeciesReview ? <EvidenceBadge label="Resolve species" tone="review" /> : null}
                {isUnknownBirdLabel(item.suggested_label, taxonomyLabels) ? (
                  <EvidenceBadge label="Unknown bird" tone="review" />
                ) : null}
                {item.suggestion_confidence != null ? (
                  <EvidenceBadge label="Low-confidence suggestion" tone="quiet" />
                ) : null}
                {identification ? (
                  <EvidenceBadge
                    label={`Identification ${reviewIdentificationStatusLabel(identification)}`}
                    tone={
                      identification.status === "configured_available" ||
                      identification.status === "ready" ||
                      identification.status === "proposal_present" ||
                      identification.status === "suggestion_present"
                        ? "review"
                        : "quiet"
                    }
                  />
                ) : null}
                {identification?.adapter_is_demo ? (
                  <EvidenceBadge label="Demo placeholder" tone="quiet" />
                ) : null}
                <TaxonomyBadge label={suggestedTaxonomy} value={item.suggested_label} />
                <span>
                  Suggestion: {displayTaxonomyLabel(item.suggested_label ?? "unknown", taxonomyLabels)}
                </span>
                {item.suggestion_confidence != null ? (
                  <span>Confidence: {formatConfidence(item.suggestion_confidence)}</span>
                ) : null}
                <span>Source: {sourceLabel}</span>
                <span>Stream: {streamLabel}</span>
                <span>Zone: {zoneLabel}</span>
                {item.visit_id ? <span>Species suggestions: Visit detail</span> : null}
                {item.media_asset ? <span>Best frame attached</span> : null}
              </div>
              <details className="review-diagnostic-details">
                <summary>Record details</summary>
                <div className="review-diagnostic-grid">
                  <span>Review item: {item.id}</span>
                  <span>Target: {reviewQueueTargetType(item)} / {reviewQueueTargetId(item)}</span>
                  <span>Event: {item.event_id ?? "n/a"}</span>
                  <span>Visit: {item.visit_id ?? "n/a"}</span>
                  <span>Best frame ID: {item.best_media_asset_id ?? "n/a"}</span>
                  <span>Suggestion ID: {item.suggestion_id ?? "n/a"}</span>
                </div>
              </details>
              <div className="review-evidence-context">
                <div className="section-heading">
                  <div>
                    <h3>Review candidate context</h3>
                    <span className="meta-text">
                      Review source, best frame, and suggestion evidence before saving correction truth.
                    </span>
                  </div>
                  <StatusPill label={formatLabel(item.review_status)} tone="review" />
                </div>
                <div className="review-evidence-grid">
                  <div className="data-row">
                    <span>Best frame</span>
                    <strong>
                      {item.media_asset?.original_filename ?? item.media_asset?.filename ?? "No best frame attached"}
                    </strong>
                    {item.media_asset ? (
                      <small>{formatLabel(item.media_asset.media_type)} / {item.media_asset.content_type}</small>
                    ) : null}
                  </div>
                  <div className="data-row">
                    <span>Stream / Zone</span>
                    <strong>{streamLabel}</strong>
                    <small>{sourceLabel} / {zoneLabel}</small>
                  </div>
                  <div className="data-row">
                    <span>Suggestion</span>
                    <strong>{displayTaxonomyLabel(item.suggested_label ?? "unknown", taxonomyLabels)}</strong>
                    <small>
                      {item.suggestion_confidence != null
                        ? `Low-confidence ${formatConfidence(item.suggestion_confidence)}. `
                        : ""}
                      Suggestion only - confirm or correct.
                    </small>
                  </div>
                  <div className="data-row">
                    <span>Truth boundary</span>
                    <strong>{item.suggestion_creates_truth ? "Creates truth" : "Evidence only"}</strong>
                    <small>
                      {item.suggestion_reason ?? "ReviewLabel truth is created by correction submit."}
                    </small>
                  </div>
                </div>
                {itemEvidenceProposals.length > 0 ? (
                  <div className="review-proposal-evidence-list">
                    {itemEvidenceProposals.slice(0, 3).map(({ proposal, relation }) => {
                      const run = detectionRunsById.get(proposal.run_id) ?? null;
                      return (
                        <article className="review-proposal-evidence-card" key={proposal.id}>
                          <div className="item-title-row">
                            <div>
                              <span className="meta-text">
                                {relation === "linked" ? "Linked suggestion" : "Same-frame suggestion"} -{" "}
                                {run ? formatLabel(run.source) : "analyzer"} source
                              </span>
                              <h4>{displayTaxonomyLabel(proposal.label, taxonomyLabels)}</h4>
                            </div>
                            <StatusPill label={formatLabel(proposal.status)} tone="quiet" />
                          </div>
                          <div className="review-proposal-facts">
                            <span>Confidence: {formatConfidence(proposal.confidence)}</span>
                            <span>
                              Suggestion:{" "}
                              {displayTaxonomyLabel(
                                proposal.suggested_species ?? proposal.suggested_subject_label,
                                taxonomyLabels,
                              )}
                            </span>
                          </div>
                          <details className="review-diagnostic-details">
                            <summary>Suggestion record</summary>
                            <div className="review-diagnostic-grid">
                              <span>Proposal ID: {proposal.id}</span>
                              <span>Run ID: {proposal.run_id}</span>
                              <span>Status: {formatLabel(proposal.status)}</span>
                            </div>
                          </details>
                          <p>Suggestions remain evidence. The correction form creates truth.</p>
                        </article>
                      );
                    })}
                    {itemEvidenceProposals.length > 3 ? (
                      <span className="meta-text">
                        {itemEvidenceProposals.length - 3} more suggestion evidence item
                        {itemEvidenceProposals.length - 3 === 1 ? "" : "s"} available in advanced tools.
                      </span>
                    ) : null}
                  </div>
                ) : (
                  <span className="meta-text">
                    No suggestion evidence is linked to this review item yet.
                  </span>
                )}
              </div>
              <IdentificationAssistPanel
                identification={identification}
                isBusy={identifyingId === item.id || savingId === item.id}
                onAcceptLabel={(label, suggestionId) =>
                  void saveCorrectionWithLabel(
                    item,
                    label,
                    `Accepted identification assist evidence${
                      suggestionId ? ` (${suggestionId})` : ""
                    }.`,
                    suggestionId,
                  )
                }
                onFillLabel={(label) =>
                  setDrafts((current) => ({
                    ...current,
                    [item.id]: { ...draft, label },
                  }))
                }
                onRejectSuggestion={() => void rejectIdentificationSuggestion(item)}
                onRejectProposal={() => void rejectIdentificationProposal(item)}
                onRun={() => void runIdentificationAssist(item)}
                taxonomyLabels={taxonomyLabels}
              />
              {item.review_status === "reviewed" && latestItemCorrection ? (
                <CorrectionTruthSummary
                  latest={latestItemCorrection}
                  older={previousItemCorrections}
                  taxonomyLabels={taxonomyLabels}
                />
              ) : (
                <div className="correction-form">
                  <TaxonomyLabelInput
                    label={isSpeciesReview ? "Species correction" : "Corrected label"}
                    labels={taxonomyLabels}
                    value={draft.label}
                    placeholder={
                      isSpeciesReview
                        ? "reviewed species, unknown_bird, or false_positive"
                        : "reviewed label"
                    }
                    onChange={(nextLabel) =>
                      setDrafts((current) => ({
                        ...current,
                        [item.id]: { ...draft, label: nextLabel },
                      }))
                    }
                  />
                  <LabelValidationLine status={itemLabelValidation} />
                  <LabelHelperChips
                    groups={itemHelperGroups}
                    onSelect={(nextLabel) =>
                      setDrafts((current) => ({
                        ...current,
                        [item.id]: { ...draft, label: nextLabel },
                      }))
                    }
                    taxonomyLabels={taxonomyLabels}
                  />
                  <span className="review-correction-boundary">
                    Corrections create local dataset truth. Suggestions remain evidence.
                  </span>
                  <label>
                    Notes
                    <textarea
                      value={draft.notes}
                      onChange={(event) =>
                        setDrafts((current) => ({
                          ...current,
                          [item.id]: { ...draft, notes: event.target.value },
                        }))
                      }
                      placeholder="optional review note"
                    />
                  </label>
                  <div className="detail-actions">
                    <button
                      className="secondary-action"
                      disabled={savingId === item.id}
                      onClick={() =>
                        void saveCorrectionWithLabel(
                          item,
                          "false_positive",
                          draft.notes || "Marked false positive from Review Queue.",
                        )
                      }
                      type="button"
                    >
                      Mark false positive
                    </button>
                    <button
                      className="primary-action"
                      disabled={savingId === item.id}
                      onClick={() => void saveCorrection(item)}
                      type="button"
                    >
                      {savingId === item.id
                        ? "Saving..."
                        : isSpeciesReview
                          ? "Resolve species"
                          : "Save correction"}
                    </button>
                  </div>
                </div>
              )}
            </article>
          );
        })}
        {queueItems.length > 0 && filteredItems.length === 0 ? (
          <EmptyState
            title={
              readinessHandoffLabel ? "No matching review items found" : "No review items match these filters"
            }
            description={
              readinessHandoffLabel
                ? "No matching review items found. Clear search to review other items."
                : "There is still review work outside this filtered view. Reset filters to see the full queue."
            }
            action={
              readinessHandoffLabel ? (
                <button className="secondary-action" onClick={clearReadinessSearch} type="button">
                  Clear search
                </button>
              ) : (
                <button className="secondary-action" onClick={resetReviewFilters} type="button">
                  Reset filters
                </button>
              )
            }
          />
        ) : null}
      </div>
    </div>
  );
}

function IdentificationAssistPanel({
  identification,
  isBusy,
  onAcceptLabel,
  onFillLabel,
  onRejectProposal,
  onRejectSuggestion,
  onRun,
  taxonomyLabels,
}: {
  identification: ReviewIdentificationSummary | null;
  isBusy: boolean;
  onAcceptLabel: (label: string, suggestionId?: string | null) => void;
  onFillLabel: (label: string) => void;
  onRejectProposal: () => void;
  onRejectSuggestion: () => void;
  onRun: () => void;
  taxonomyLabels: TaxonomyLabel[];
}) {
  if (!identification) {
    return null;
  }

  const proposalIsRejected = identification.proposal?.status === "rejected";
  const suggestedLabel =
    identification.suggestion?.suggested_label ??
    (!proposalIsRejected
      ? identification.proposal?.suggested_species ??
        identification.proposal?.suggested_subject_label ??
        identification.proposal?.label
      : null) ??
    null;
  const confidence = reviewIdentificationConfidence(identification);
  const suggestionId = identification.suggestion?.id ?? null;
  const proposalId =
    identification.proposal && identification.proposal.status === "proposed"
      ? identification.proposal.id
      : null;
  const canRun = reviewIdentificationCanRun(identification);
  const supportedMediaCopy =
    identification.supported_media_types.length > 0
      ? identification.supported_media_types.join(", ")
      : "n/a";
  const setupStatusLabel = identification.setup_status
    ? formatLabel(identification.setup_status)
    : identification.adapter_status
      ? formatLabel(identification.adapter_status)
      : "Unavailable";
  const setupDetailsOpen =
    identification.status === "setup_required" ||
    identification.status === "unavailable" ||
    identification.status === "unsupported_media" ||
    identification.status === "failed";
  const focusPixelLabel = identification.focus_crop_box_pixels
    ? `Pixels ${identification.focus_crop_box_pixels.x}, ${identification.focus_crop_box_pixels.y} / ${identification.focus_crop_box_pixels.width} x ${identification.focus_crop_box_pixels.height}`
    : "Pixel box unavailable";

  return (
    <div className="review-identification-assist">
      <div className="section-heading">
        <div>
          <h3>Identification assist</h3>
          <span className="meta-text">
            Suggestions stay evidence until correction.
          </span>
        </div>
        <StatusPill
          label={reviewIdentificationStatusLabel(identification)}
          tone={reviewIdentificationStatusTone(identification)}
        />
      </div>
      <div className="review-identification-grid">
        <div className="data-row">
          <span>Analyzer</span>
          <strong>
            {identification.adapter_name ??
              (identification.status === "setup_required"
                ? "Identification setup required"
                : "No analyzer")}
          </strong>
          <small>
            {identification.adapter_is_demo
              ? "Placeholder analyzer"
              : identification.setup_status
                ? `${setupStatusLabel}${identification.local_only ? " / local" : ""}`
                : "Unavailable"}
          </small>
        </div>
        <div className="data-row">
          <span>Best frame</span>
          <strong>{identification.media_asset_id ?? "No best frame"}</strong>
          <small>
            {identification.can_run_on_best_frame
              ? "Runnable media"
              : identification.unavailable_reason ?? `Supports ${supportedMediaCopy}`}
          </small>
        </div>
        <div className="data-row">
          <span>Focus context</span>
          <strong>
            {identification.focus_crop_available
              ? identification.focus_crop_label ?? "Activity focus"
              : "Full best frame"}
          </strong>
          <small>
            {identification.focus_crop_available
              ? `Best frame with ${formatLabel(
                  identification.focus_crop_source,
                )} crop context. ${focusCropBoxLabel(
                  identification.focus_crop_box_normalized,
                )}. ${focusPixelLabel}.`
              : identification.focus_crop_warnings.length > 0
                ? identification.focus_crop_warnings.map(formatQualityWarning).join(", ")
                : "No focus crop metadata"}
          </small>
        </div>
        <div className="data-row">
          <span>Suggestion</span>
          <strong>
            {suggestedLabel ? displayTaxonomyLabel(suggestedLabel, taxonomyLabels) : "No suggestion"}
          </strong>
          <small>
            {identification.adapter_is_demo
              ? "Placeholder evidence; no species confidence. "
              : confidence != null
                ? `${formatConfidence(confidence)} confidence. `
                : ""}
            {identification.suggestion_count + identification.proposal_count} suggestion evidence item
            {identification.suggestion_count + identification.proposal_count === 1 ? "" : "s"}
          </small>
        </div>
        <div className="data-row">
          <span>Status</span>
          <strong>{reviewIdentificationStatusLabel(identification)}</strong>
          <small>{identification.message}</small>
        </div>
        <div className="data-row">
          <span>Truth boundary</span>
          <strong>{identification.creates_truth ? "Creates truth" : "Evidence only"}</strong>
          <small>
            {identification.status === "failed"
              ? identification.unavailable_reason ?? "Failed cleanly"
              : identification.setup_hint ??
                "Accepting still creates a ReviewLabel through correction."}
          </small>
        </div>
      </div>
      <details className="review-identification-setup-details" open={setupDetailsOpen}>
        <summary>Analyzer setup</summary>
        <div className="review-identification-setup-grid">
          <div className="data-row">
            <span>Status</span>
            <strong>{setupStatusLabel}</strong>
            <small>
              {identification.adapter_is_demo
                ? "Demo output is placeholder evidence."
                : identification.can_run_on_best_frame
                  ? "Ready for this best frame."
                  : "No local analyzer configured for this best frame."}
            </small>
          </div>
          <div className="data-row">
            <span>Required env</span>
            <strong>
              {identification.required_env_var ? (
                <code>{identification.required_env_var}</code>
              ) : (
                "None"
              )}
            </strong>
            <small>{identification.model_path_hint ?? "Demo analyzer requires no model file."}</small>
          </div>
          <div className="data-row">
            <span>Best frame media</span>
            <strong>{supportedMediaCopy}</strong>
            <small>{identification.media_asset_id ? "Best-frame compatibility is checked here." : "Readiness only."}</small>
          </div>
          <div className="data-row">
            <span>Truth boundary</span>
            <strong>{identification.creates_truth ? "Creates truth" : "Suggestions are not truth"}</strong>
            <small>No model files are bundled or downloaded.</small>
          </div>
        </div>
        {identification.setup_hint ? (
          <span className="meta-text">{identification.setup_hint}</span>
        ) : null}
      </details>
      <div className="review-identification-actions">
        {canRun ? (
          <button
            className="secondary-action"
            disabled={isBusy}
            onClick={onRun}
            type="button"
          >
            {isBusy
              ? "Running..."
              : identification.adapter_is_demo
                ? "Run demo placeholder"
                : "Run identification"}
          </button>
        ) : null}
        {suggestedLabel ? (
          <>
            <button
              className="secondary-action"
              disabled={isBusy}
              onClick={() => onFillLabel(suggestedLabel)}
              type="button"
            >
              Use label
            </button>
            <button
              className="primary-action"
              disabled={isBusy}
              onClick={() => onAcceptLabel(suggestedLabel, suggestionId)}
              type="button"
            >
              Accept as correction
            </button>
          </>
        ) : null}
        {suggestionId ? (
          <button
            className="secondary-action"
            disabled={isBusy}
            onClick={onRejectSuggestion}
            type="button"
          >
            Reject suggestion
          </button>
        ) : null}
        {proposalId ? (
          <button
            className="secondary-action"
            disabled={isBusy}
            onClick={onRejectProposal}
            type="button"
          >
            Reject suggestion evidence
          </button>
        ) : null}
      </div>
    </div>
  );
}

function CorrectionSuccessPanel({
  onContinueReview,
  onOpenAnalytics,
  onOpenClassifierReadiness,
  onOpenExports,
  summary,
  taxonomyLabels,
}: {
  onContinueReview: () => void;
  onOpenAnalytics: () => void;
  onOpenClassifierReadiness: () => void;
  onOpenExports: () => void;
  summary: LastCorrectionSummary;
  taxonomyLabels: TaxonomyLabel[];
}) {
  const isBulk = summary.mode === "bulk";
  const appliedLabel = displayTaxonomyLabel(summary.label, taxonomyLabels);
  const reviewLabelIds =
    summary.mode === "single" ? [summary.reviewLabelId] : summary.reviewLabelIds;

  return (
    <section className="notice-panel correction-success-panel">
      <div className="correction-success-header">
        <div>
          <EvidenceBadge label="Correction truth" tone="truth" />
          <h2>{isBulk ? "Bulk correction saved" : "Correction saved"}</h2>
          <p>
            {isBulk
              ? `${summary.succeededCount} correction${
                  summary.succeededCount === 1 ? "" : "s"
                } created explicitly for ${appliedLabel}.`
              : `Correction ${summary.reviewLabelId} created explicitly for ${appliedLabel}.`}
          </p>
        </div>
        <StatusPill
          label={`${summary.remaining} still need review`}
          tone={summary.remaining > 0 ? "review" : "good"}
        />
      </div>
      <div className="correction-success-grid">
        {summary.mode === "single" ? (
          <>
            <div className="data-row">
              <span>Corrected target</span>
              <strong>{formatLabel(summary.targetType)}</strong>
              <small>{summary.targetId}</small>
            </div>
            <div className="data-row">
              <span>Applied label</span>
              <strong>{appliedLabel}</strong>
              <small>{summary.label}</small>
            </div>
            <div className="data-row">
              <span>Correction ID</span>
              <strong>{summary.reviewLabelId}</strong>
            </div>
          </>
        ) : (
          <>
            <div className="data-row">
              <span>Bulk target</span>
              <strong>{formatLabel(summary.targetType)}</strong>
              <small>{compactIdList(summary.correctedTargetIds, "No corrected targets")}</small>
            </div>
            <div className="data-row">
              <span>Applied label</span>
              <strong>{appliedLabel}</strong>
              <small>{summary.label}</small>
            </div>
            <div className="data-row">
              <span>Requested / saved / skipped / failed</span>
              <strong>
                {summary.requestedCount} / {summary.succeededCount} / {summary.skippedCount} /{" "}
                {summary.failedCount}
              </strong>
            </div>
            <div className="data-row">
              <span>Correction IDs</span>
              <strong>{compactIdList(reviewLabelIds, "No correction IDs returned")}</strong>
              <small>{reviewLabelIds.length} created</small>
            </div>
          </>
        )}
      </div>
      <div className="correction-success-boundary">
        <strong>This correction is local dataset truth.</strong>
        <span>
          Suggestion evidence and best frames stay evidence. This correction now counts toward dataset
          coverage, classifier readiness, exports, and analytics.
        </span>
      </div>
      <div className="detail-actions correction-success-actions">
        <button className="secondary-action" onClick={onOpenClassifierReadiness} type="button">
          Advanced Classifier Readiness
        </button>
        <button className="secondary-action" onClick={onOpenExports} type="button">
          Dataset Exports
        </button>
        <button className="secondary-action" onClick={onOpenAnalytics} type="button">
          Analytics
        </button>
        <button className="secondary-action" onClick={onContinueReview} type="button">
          Continue Review Queue
        </button>
      </div>
    </section>
  );
}

function CorrectionAuditPanel({
  groups,
  onOpenEvent,
  onOpenVisit,
  taxonomyLabels,
}: {
  groups: CorrectionHistoryGroup[];
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
  taxonomyLabels: TaxonomyLabel[];
}) {
  if (groups.length === 0) {
    return null;
  }

  return (
    <section className="panel correction-audit-panel">
      <div className="section-heading">
        <div>
          <h2>Reviewed correction audit</h2>
          <span className="meta-text">
            Latest correction truth stays visible after items leave the active queue.
          </span>
        </div>
        <EvidenceBadge
          label={`${groups.length} reviewed target${groups.length === 1 ? "" : "s"}`}
          tone="truth"
        />
      </div>
      <div className="correction-audit-list">
        {groups.map((group) => (
          <article className="history-item correction-audit-item" key={group.key}>
            <div className="item-title-row">
              <div>
                <span className="meta-text">Correction truth</span>
                <strong>{displayTaxonomyLabel(group.latest.label, taxonomyLabels)}</strong>
              </div>
              {group.targetType === "visit" ? (
                <button
                  className="text-action"
                  onClick={() => onOpenVisit(group.targetId)}
                  type="button"
                >
                  Visit detail
                </button>
              ) : group.targetType === "event" ? (
                <button
                  className="text-action"
                  onClick={() => onOpenEvent(group.targetId)}
                  type="button"
                >
                  Event detail
                </button>
              ) : null}
            </div>
            <span>
              Latest {formatLabel(group.targetType)} correction -{" "}
              {formatDateTime(group.latest.created_at)}
            </span>
            <span className="meta-text">Record: {group.targetId}</span>
            {group.latest.notes ? <p>{group.latest.notes}</p> : null}
            {group.older.length > 0 ? (
              <details className="correction-history-details">
                <summary>
                  {group.older.length} older correction{group.older.length === 1 ? "" : "s"}
                </summary>
                <div className="history-list">
                  {group.older.map((label) => (
                    <ReviewLabelHistoryItem
                      key={label.id}
                      reviewLabel={label}
                      taxonomyLabels={taxonomyLabels}
                    />
                  ))}
                </div>
              </details>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function CorrectionTruthSummary({
  latest,
  older,
  taxonomyLabels,
}: {
  latest: ReviewLabel;
  older: ReviewLabel[];
  taxonomyLabels: TaxonomyLabel[];
}) {
  return (
    <div className="correction-truth-summary">
      <EvidenceBadge label="Correction truth" tone="truth" />
      <strong>{displayTaxonomyLabel(latest.label, taxonomyLabels)}</strong>
      <span>Latest correction - {formatDateTime(latest.created_at)}</span>
      {latest.notes ? <p>{latest.notes}</p> : null}
      {older.length > 0 ? (
        <details className="correction-history-details">
          <summary>{older.length} older correction{older.length === 1 ? "" : "s"}</summary>
          <div className="history-list">
            {older.map((label) => (
              <ReviewLabelHistoryItem
                key={label.id}
                reviewLabel={label}
                taxonomyLabels={taxonomyLabels}
              />
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
}

function ReviewLabelHistoryItem({
  reviewLabel,
  taxonomyLabels,
}: {
  reviewLabel: ReviewLabel;
  taxonomyLabels: TaxonomyLabel[];
}) {
  return (
    <div className="history-item">
      <strong>{displayTaxonomyLabel(reviewLabel.label, taxonomyLabels)}</strong>
      <span>
        {formatLabel(reviewLabel.target_type)} correction -{" "}
        {formatDateTime(reviewLabel.created_at)}
      </span>
      {reviewLabel.notes ? <p>{reviewLabel.notes}</p> : null}
    </div>
  );
}

function LabelValidationLine({ status }: { status: LabelValidationStatus }) {
  const validationCopy: Record<LabelValidationStatus, string> = {
    empty: "Choose or type a label.",
    suggested: "Matches suggested label.",
    recent: "Matches recent correction.",
    taxonomy: "Matches taxonomy.",
    custom: "Custom label. Saved only after you apply it.",
  };

  return (
    <span className={`label-validation-line label-validation-${status}`}>
      {validationCopy[status]}
    </span>
  );
}

function LabelHelperChips({
  groups,
  onSelect,
  taxonomyLabels,
}: {
  groups: LabelHelperGroup[];
  onSelect: (label: string) => void;
  taxonomyLabels: TaxonomyLabel[];
}) {
  if (groups.length === 0) {
    return null;
  }

  return (
    <div className="label-helper-panel">
      <div className="label-helper-heading">
        <strong>Label helpers</strong>
        <span>Click to fill; submit still required.</span>
      </div>
      {groups.map((group) => (
        <div className="label-helper-group" key={group.title}>
          <span>{group.title}</span>
          <div className="label-helper-chips">
            {group.labels.map((label) => (
              <button
                key={`${group.title}-${taxonomyKey(label)}`}
                onClick={() => onSelect(label)}
                type="button"
              >
                {displayTaxonomyLabel(label, taxonomyLabels)}
              </button>
            ))}
          </div>
        </div>
      ))}
      <span className="field-helper">Corrections are truth after you apply them.</span>
    </div>
  );
}
