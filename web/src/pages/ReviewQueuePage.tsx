import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
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
  ReviewQueueSpeciesSuggestionBatchPrepareResponse,
  SpeciesCandidatePackSummary,
  TaxonomyLabel,
  VisitIdentificationAssistantResponse,
  VisitTagSummary,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { EvidenceBadge } from "../components/EvidenceBadge";
import { IdentificationAssistant } from "../components/IdentificationAssistant";
import { MediaAssetPreview } from "../components/MediaAssetPreview";
import { PageHeader } from "../components/PageHeader";
import { ReviewFilterTabs, type ReviewFilterOption } from "../components/ReviewFilterTabs";
import { VisitEvidenceSequence } from "../components/VisitEvidenceSequence";
import { RefinedCropEditor } from "../components/RefinedCropEditor";
import { speciesSuggestionMetricLabel } from "../components/speciesSuggestion";
import { StatusPill } from "../components/StatusPill";
import { TaxonomyLabelInput } from "../components/TaxonomyLabelInput";
import { TaxonomyBadge } from "../components/TaxonomyBadge";
import {
  displayTaxonomyLabel,
  findTaxonomyLabel,
  isBirdReviewLabel,
  isFalsePositiveLabel,
  isUnknownBirdLabel,
  taxonomyKey,
} from "../components/taxonomy";
import { formatDateTime, formatLabel } from "../utils";

type ReviewTriageCategory =
  | "animal_evidence"
  | "vehicle_person_evidence"
  | "no_clear_proposal"
  | "not_analyzed"
  | "false_positives";
type ReviewFilter = "all" | ReviewTriageCategory;
type ReviewSort = "newest" | "animals_first";
type ReviewTargetFilter = "all" | "event" | "visit";
type ReviewEvidenceFilter =
  | "all"
  | "has_media"
  | "has_detection_proposal"
  | "has_motion_evidence"
  | "no_proposal_evidence";
export type ReviewStatusFilter = "unreviewed" | "reviewed" | "all";
type LabelValidationStatus = "empty" | "suggested" | "recent" | "taxonomy" | "custom";
type ProductReviewTab =
  | "animals"
  | "other_activity"
  | "unchecked"
  | "legacy_activity"
  | "reviewed";

const PRODUCT_REVIEW_PAGE_SIZE = 25;

function matchesProductReviewTab(
  item: ReviewQueueItem,
  tab: ProductReviewTab,
  showLegacyAndTestActivity: boolean,
): boolean {
  if (tab === "reviewed") {
    return item.product_category === "reviewed";
  }
  if (tab === "legacy_activity") {
    return showLegacyAndTestActivity && item.product_category === "legacy_activity";
  }
  if (item.review_status !== "needs_review") {
    return false;
  }
  if (tab === "animals") {
    return item.target_type === "visit" && item.product_category === "animal";
  }
  if (tab === "other_activity") {
    return item.product_category === "other_activity";
  }
  return item.product_category === "unchecked";
}

function productReviewTitle(item: ReviewQueueItem, taxonomyLabels: TaxonomyLabel[]): string {
  if (item.product_category === "animal") {
    // Acoustic / BirdNET Observation Foundation v1: honest about whether
    // this candidate's evidence was heard or seen.
    return item.media_asset?.media_type === "audio"
      ? "Bird heard — species not confirmed"
      : "Animal detected — species not confirmed";
  }
  if (item.product_category === "other_activity") {
    return "Other detector-qualified activity";
  }
  if (item.product_category === "unchecked") {
    return "Activity needs evidence review";
  }
  if (item.product_category === "reviewed") {
    // Everyday Product / Discovery UX Closure v1: say what this was actually
    // reviewed as instead of an undifferentiated "Reviewed activity" for
    // every card in this tab.
    return item.reviewed_label
      ? `Reviewed: ${displayTaxonomyLabel(item.reviewed_label, taxonomyLabels)}`
      : "Reviewed activity";
  }
  return "Legacy or test activity";
}

export interface ReviewQueueInitialContext {
  source?: "activity-library" | "classifier-readiness" | "live-motion";
  sourceLabel?: string | null;
  search?: string | null;
  correctionLabel?: string | null;
  status?: ReviewStatusFilter | null;
  visitIds?: string[];
  openFastReview?: boolean;
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

interface RankedSpeciesAlternative {
  confidence: number | null;
  commonName: string | null;
  correctionLabel: string;
  label: string;
  rank: number;
  scientificName: string | null;
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
  triage: ReviewTriageSummary;
}

interface ReviewTriageSummary {
  category: ReviewTriageCategory;
  confidence: number | null;
  hasAnalyzerRun: boolean;
  label: string | null;
  secondaryConfidence: number | null;
  secondaryLabel: string | null;
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


const MAX_SPECIES_SUGGESTION_BATCH_VISITS = 25;

type SpeciesSuggestionBatchOutcomeStatus =
  | "new_evidence"
  | "reused"
  | "skipped"
  | "setup_required"
  | "failed";

type SpeciesSuggestionBatchPhase = "running" | "completed" | "canceled";

interface SpeciesSuggestionBatchOutcome {
  visitId: string;
  title: string;
  status: SpeciesSuggestionBatchOutcomeStatus;
  message: string;
  mediaAssetId: string | null;
  topSuggestion: string | null;
  wasScheduled: boolean;
  candidatePackLabel?: string | null;
  candidatePackWarning?: string | null;
}

interface SpeciesSuggestionBatchState {
  phase: SpeciesSuggestionBatchPhase;
  selectedTotal: number;
  scheduledTotal: number;
  currentVisitId: string | null;
  outcomes: SpeciesSuggestionBatchOutcome[];
}

function isSpeciesSuggestionBatchEligible(
  item: ReviewQueueItem,
  taxonomyLabels: TaxonomyLabel[],
): boolean {
  return (
    item.target_type === "visit" &&
    item.review_status === "needs_review" &&
    isBirdReviewLabel(item.suggested_label, taxonomyLabels)
  );
}

function assistantRunStatus(response: VisitIdentificationAssistantResponse): string | null {
  const status = response.run?.status;
  return typeof status === "string" ? status : null;
}

function candidatePackLabel(pack: SpeciesCandidatePackSummary | null | undefined): string | null {
  return pack
    ? `Compared against ${pack.candidate_count} species from ${pack.display_name} v${pack.version}`
    : null;
}

function batchOutcomeFromAssistant(
  item: ReviewQueueItem,
  response: VisitIdentificationAssistantResponse,
): SpeciesSuggestionBatchOutcome {
  const mediaAssetId = response.selected_evidence_frames[0]?.media_asset_id ?? null;
  const topSuggestion = response.suggestions[0]?.label ?? null;
  const reusedCompletedInput =
    response.message.includes("exact saved input already has identification evidence") ||
    response.message.includes("already recorded") ||
    response.availability.message.includes("reused the completed result");
  const createdEvidence = response.suggestions.some(
    (suggestion) => suggestion.origin === "user_triggered_review_assistance",
  );
  const status = response.availability.status;
  const runStatus = assistantRunStatus(response);
  const base = {
    visitId: reviewQueueTargetId(item),
    title: item.title,
    message: response.message,
    mediaAssetId,
    topSuggestion,
    wasScheduled: true,
    candidatePackLabel: candidatePackLabel(response.availability.candidate_pack),
    candidatePackWarning: response.availability.candidate_pack_warning,
  };
  if (reusedCompletedInput) {
    return { ...base, status: "reused" };
  }
  if (createdEvidence) {
    return { ...base, status: "new_evidence" };
  }
  if (status === "suggestion_present" || response.suggestions.length > 0) {
    return { ...base, status: "reused" };
  }
  if (status === "setup_required") {
    return { ...base, status: "setup_required" };
  }
  if (status === "failed" || runStatus === "failed") {
    return { ...base, status: "failed" };
  }
  return { ...base, status: "skipped" };
}

function speciesSuggestionBatchCounts(state: SpeciesSuggestionBatchState) {
  const count = (status: SpeciesSuggestionBatchOutcomeStatus) =>
    state.outcomes.filter((outcome) => outcome.status === status).length;
  const finishedScheduled = state.outcomes.filter(
    (outcome) => outcome.wasScheduled,
  ).length;
  const queued = Math.max(
    0,
    state.scheduledTotal - finishedScheduled - (state.currentVisitId ? 1 : 0),
  );
  const canceled =
    state.phase === "canceled"
      ? Math.max(0, state.selectedTotal - state.outcomes.length - (state.currentVisitId ? 1 : 0))
      : 0;
  return {
    canceled,
    completedWithNewEvidence: count("new_evidence"),
    failed: count("failed"),
    queued,
    reused: count("reused"),
    setupRequired: count("setup_required"),
    skipped: count("skipped"),
  };
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

function normalizedOverlayStyle(box: BoundingBox | null | undefined): CSSProperties | undefined {
  if (!box) {
    return undefined;
  }
  const left = Math.max(0, Math.min(1, box.x));
  const top = Math.max(0, Math.min(1, box.y));
  const right = Math.max(left, Math.min(1, box.x + box.width));
  const bottom = Math.max(top, Math.min(1, box.y + box.height));
  if (right <= left || bottom <= top) {
    return undefined;
  }
  return {
    left: `${left * 100}%`,
    top: `${top * 100}%`,
    width: `${(right - left) * 100}%`,
    height: `${(bottom - top) * 100}%`,
  };
}

type ProposalOverlayTone = "animal" | "person" | "vehicle" | "other";

function proposalOverlayTone(
  proposal: DetectionProposal,
  taxonomyLabels: TaxonomyLabel[],
): ProposalOverlayTone {
  const value =
    proposal.suggested_species ?? proposal.suggested_subject_label ?? proposal.label;
  const key = taxonomyKey(value ?? "");
  const taxonomy = findTaxonomyLabel(value, taxonomyLabels);
  if (key === "person" || taxonomy?.category === "person") {
    return "person";
  }
  if (key === "vehicle" || taxonomy?.category === "vehicle") {
    return "vehicle";
  }
  if (
    key === "animal" ||
    key === "unknown_animal" ||
    key === "bird" ||
    key === "unknown_bird" ||
    taxonomy?.category === "bird" ||
    taxonomy?.category === "mammal" ||
    taxonomy?.category === "pet"
  ) {
    return "animal";
  }
  return "other";
}

function proposalOverlayLabel(
  proposal: DetectionProposal,
  taxonomyLabels: TaxonomyLabel[],
): string {
  const value =
    proposal.suggested_species ?? proposal.suggested_subject_label ?? proposal.label;
  return `${displayTaxonomyLabel(value, taxonomyLabels)} ${formatConfidence(
    proposal.confidence,
  )}`;
}

function reviewProposalOverlays(
  proposals: ReviewEvidenceProposal[],
  mediaAssetId: string | null,
): ReviewEvidenceProposal[] {
  const candidates = proposals.filter(
    ({ proposal }) =>
      proposal.status !== "rejected" &&
      proposal.bbox &&
      Boolean(mediaAssetId) &&
      proposal.media_asset_id === mediaAssetId,
  );
  const latestRunId = candidates.reduce<ReviewEvidenceProposal | null>((latest, current) => {
    if (!latest) {
      return current;
    }
    return new Date(current.proposal.created_at).getTime() >
      new Date(latest.proposal.created_at).getTime()
      ? current
      : latest;
  }, null)?.proposal.run_id;

  return candidates
    .filter(({ proposal }) => proposal.run_id === latestRunId)
    .sort((first, second) => second.proposal.confidence - first.proposal.confidence)
    .slice(0, 8);
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

function optionalString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function optionalNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function rankedSpeciesAlternatives(
  identification: ReviewIdentificationSummary,
): RankedSpeciesAlternative[] {
  const suggestion = identification.suggestion;
  if (!suggestion) {
    return [];
  }

  return suggestion.alternatives
    .map((alternative, index): RankedSpeciesAlternative | null => {
      const label =
        optionalString(alternative.label) ??
        optionalString(alternative.suggested_label);
      if (!label) {
        return null;
      }

      const explicitRank = optionalNumber(alternative.rank);
      return {
        confidence:
          optionalNumber(alternative.score) ??
          optionalNumber(alternative.confidence),
        commonName: optionalString(alternative.common_name),
        correctionLabel:
          optionalString(alternative.suggested_label) ?? label,
        label,
        rank:
          explicitRank !== null && explicitRank > 0
            ? Math.round(explicitRank)
            : suggestion.rank + index + 1,
        scientificName: optionalString(alternative.scientific_name),
      };
    })
    .filter((alternative): alternative is RankedSpeciesAlternative => alternative !== null)
    .sort((first, second) => first.rank - second.rank);
}

function pendingSuggestionIdForCorrection(
  item: ReviewQueueItem,
  correctionLabel: string,
): string | null {
  const suggestion = item.identification?.suggestion;
  if (!suggestion || suggestion.status !== "pending") {
    return null;
  }
  const correctionKey = taxonomyKey(correctionLabel);
  if (!correctionKey) {
    return null;
  }
  const candidateLabels = [
    suggestion.suggested_label,
    ...suggestion.alternatives
      .map((alternative) => optionalString(alternative.suggested_label))
      .filter((label): label is string => label !== null),
  ];
  return candidateLabels.some((label) => taxonomyKey(label) === correctionKey)
    ? suggestion.id
    : null;
}

function speciesEvidenceRegionSummary(
  evidenceRegion: Record<string, unknown> | null | undefined,
): string | null {
  if (!evidenceRegion) {
    return null;
  }

  const parts: string[] = [];
  const source =
    optionalString(evidenceRegion.source) ??
    optionalString(evidenceRegion.crop_source);
  if (source) {
    parts.push(`${formatLabel(source)} source`);
  }

  const box = {
    x: optionalNumber(evidenceRegion.x),
    y: optionalNumber(evidenceRegion.y),
    width: optionalNumber(evidenceRegion.width),
    height: optionalNumber(evidenceRegion.height),
  };
  if (
    box.x !== null &&
    box.y !== null &&
    box.width !== null &&
    box.height !== null
  ) {
    parts.push(focusCropBoxLabel(box as BoundingBox));
  }

  return parts.length > 0 ? parts.join(" · ") : "Stored classifier crop metadata";
}

function speciesScoreLabel(identification: ReviewIdentificationSummary): string {
  const adapterId =
    identification.suggestion?.adapter_id ?? identification.adapter_id ?? "";
  const scoreSemantics = optionalString(
    identification.suggestion?.evidence_region?.score_semantics,
  );
  const normalizedSemantics = taxonomyKey(scoreSemantics ?? "");
  return taxonomyKey(adapterId) === "bioclip_2" ||
    normalizedSemantics.includes("uncalibrated") ||
    normalizedSemantics.includes("candidate_bank") ||
    normalizedSemantics.includes("candidate_relative")
    ? "uncalibrated score"
    : "confidence";
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

function triageCategoryForLabel(
  value: string | null | undefined,
  taxonomyLabels: TaxonomyLabel[],
): ReviewTriageCategory | null {
  const key = taxonomyKey(value ?? "");
  const taxonomy = findTaxonomyLabel(value, taxonomyLabels);
  if (key === "false_positive" || taxonomy?.category === "false_positive") {
    return "false_positives";
  }
  if (
    key === "person" ||
    key === "vehicle" ||
    taxonomy?.category === "person" ||
    taxonomy?.category === "vehicle"
  ) {
    return "vehicle_person_evidence";
  }
  if (
    key === "animal" ||
    key === "unknown_animal" ||
    key === "bird" ||
    key === "unknown_bird" ||
    taxonomy?.category === "bird" ||
    taxonomy?.category === "mammal" ||
    taxonomy?.category === "pet"
  ) {
    return "animal_evidence";
  }
  return null;
}

function triageProposal(
  proposal: DetectionProposal,
  taxonomyLabels: TaxonomyLabel[],
): { category: ReviewTriageCategory; label: string } | null {
  for (const value of [
    proposal.suggested_species,
    proposal.suggested_subject_label,
    proposal.label,
  ]) {
    const category = triageCategoryForLabel(value, taxonomyLabels);
    const label = value?.trim();
    if (category && label) {
      return { category, label };
    }
  }
  return null;
}

function reviewTriageSummary(
  item: ReviewQueueItem,
  proposalEvidence: ReviewEvidenceProposal[],
  detectionRuns: DetectionRun[],
  taxonomyLabels: TaxonomyLabel[],
): ReviewTriageSummary {
  if (isFalsePositiveLabel(item.suggested_label, taxonomyLabels)) {
    return {
      category: "false_positives",
      confidence: null,
      hasAnalyzerRun: false,
      label: item.suggested_label ?? "false_positive",
      secondaryConfidence: null,
      secondaryLabel: null,
    };
  }

  const activeProposals = proposalEvidence
    .filter(({ proposal }) => proposal.status !== "rejected")
    .map(({ proposal }) => ({ proposal, triage: triageProposal(proposal, taxonomyLabels) }))
    .filter(
      (
        value,
      ): value is {
        proposal: DetectionProposal;
        triage: { category: ReviewTriageCategory; label: string };
      } => value.triage !== null,
    );
  const strongest = (category: ReviewTriageCategory) =>
    activeProposals
      .filter((value) => value.triage.category === category)
      .sort((first, second) => second.proposal.confidence - first.proposal.confidence)[0];
  const animal = strongest("animal_evidence");
  const vehicleOrPerson = strongest("vehicle_person_evidence");
  const selected = animal ?? vehicleOrPerson;
  if (selected) {
    return {
      category: selected.triage.category,
      confidence: selected.proposal.confidence,
      hasAnalyzerRun: true,
      label: selected.triage.label,
      secondaryConfidence: animal && vehicleOrPerson ? vehicleOrPerson.proposal.confidence : null,
      secondaryLabel: animal && vehicleOrPerson ? vehicleOrPerson.triage.label : null,
    };
  }

  const mediaAssetId = item.best_media_asset_id ?? item.media_asset?.id ?? null;
  const hasAnalyzerRun = Boolean(
    mediaAssetId && detectionRuns.some((run) => run.media_asset_id === mediaAssetId),
  );
  return {
    category: hasAnalyzerRun ? "no_clear_proposal" : "not_analyzed",
    confidence: null,
    hasAnalyzerRun,
    label: null,
    secondaryConfidence: null,
    secondaryLabel: null,
  };
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
  detectionRuns: DetectionRun[],
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
    evidence.zone_id ?? "",
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
    triage: reviewTriageSummary(
      item,
      proposalEvidence,
      detectionRuns,
      taxonomyLabels,
    ),
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

function reviewTriageTitle(
  triage: ReviewTriageSummary,
  taxonomyLabels: TaxonomyLabel[],
): string {
  if (triage.category === "animal_evidence") {
    const animalLabel = displayTaxonomyLabel(triage.label ?? "animal", taxonomyLabels);
    if (triage.secondaryLabel) {
      return `${animalLabel} with ${displayTaxonomyLabel(
        triage.secondaryLabel,
        taxonomyLabels,
      )} context`;
    }
    return `Animal evidence: ${animalLabel}`;
  }
  if (triage.category === "vehicle_person_evidence") {
    return `Other activity: ${displayTaxonomyLabel(triage.label ?? "vehicle", taxonomyLabels)}`;
  }
  if (triage.category === "no_clear_proposal") {
    return "Analyzer found no clear object";
  }
  if (triage.category === "false_positives") {
    return "False-positive context";
  }
  return "Saved frame has not been checked";
}

function reviewTriageDescription(
  triage: ReviewTriageSummary,
  identification: ReviewIdentificationSummary | null,
  hasMedia: boolean,
): string {
  if (triage.category === "animal_evidence") {
    if (triage.secondaryLabel) {
      return "Animal evidence appears in a mixed scene with vehicle or person evidence. Inspect the boxes before correcting.";
    }
    return "Review this likely wildlife activity first; the analyzer result remains evidence until correction.";
  }
  if (triage.category === "vehicle_person_evidence") {
    return "Vehicle/person evidence can be reviewed or corrected without entering the Bird Log as a bird.";
  }
  if (triage.category === "no_clear_proposal") {
    return "The saved frame was checked, but the analyzer returned no usable animal, person, or vehicle proposal.";
  }
  if (triage.category === "false_positives") {
    return "This context is already marked as likely noise; correction still decides truth.";
  }
  if (!hasMedia) {
    return "A saved best frame is required before optional identification can run.";
  }
  if (identification && reviewIdentificationCanRun(identification)) {
    return "Check the saved best frame explicitly for animal, person, or vehicle evidence.";
  }
  return "Optional identification is not currently available; review the saved frame manually.";
}

function reviewTriageSortRank(category: ReviewTriageCategory): number {
  const ranks: Record<ReviewTriageCategory, number> = {
    animal_evidence: 0,
    not_analyzed: 1,
    no_clear_proposal: 2,
    vehicle_person_evidence: 3,
    false_positives: 4,
  };
  return ranks[category];
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
  onFastReviewChanged: () => Promise<void>;
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
  onFastReviewChanged,
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
  const [selectedSpeciesSuggestionVisitIds, setSelectedSpeciesSuggestionVisitIds] =
    useState<string[]>([]);
  const [speciesSuggestionBatch, setSpeciesSuggestionBatch] =
    useState<SpeciesSuggestionBatchState | null>(null);
  const speciesSuggestionBatchCancelRef = useRef(false);
  const speciesSuggestionBatchMountedRef = useRef(true);
  const [detectionProposals, setDetectionProposals] = useState<DetectionProposal[]>([]);
  const [detectionRuns, setDetectionRuns] = useState<DetectionRun[]>([]);
  const [motionEvidence, setMotionEvidence] = useState<MotionEvidence[]>([]);
  const [taxonomyLabels, setTaxonomyLabels] = useState<TaxonomyLabel[]>([]);
  const [reviewLabels, setReviewLabels] = useState<ReviewLabel[]>([]);
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>("all");
  const [productTab, setProductTab] = useState<ProductReviewTab>("animals");
  const [showLegacyAndTestActivity, setShowLegacyAndTestActivity] = useState(false);
  const [skippedTargetIds, setSkippedTargetIds] = useState<Set<string>>(() => new Set());
  const [reviewPage, setReviewPage] = useState(0);
  const productMode = true;
  const [reviewSort, setReviewSort] = useState<ReviewSort>("newest");
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
  const [fastReviewRequest, setFastReviewRequest] = useState<ReviewQueueItem | null>(null);
  const [scopedVisitIds, setScopedVisitIds] = useState<Set<string> | null>(null);
  const [shouldOpenFocusedFastReview, setShouldOpenFocusedFastReview] = useState(false);

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
            detectionRuns,
          ),
        ]),
      ),
    [
      detectionProposals,
      detectionRuns,
      detectionRunsById,
      motionEvidence,
      queueItems,
      taxonomyLabels,
    ],
  );

  const queueCounts = useMemo(
    () =>
      queueItems.reduce<Record<ReviewFilter, number>>(
        (counts, item) => {
          counts.all += 1;
          const category = filterMetadataByItemId.get(item.id)?.triage.category;
          if (category) {
            counts[category] += 1;
          }
          return counts;
        },
        {
          all: 0,
          animal_evidence: 0,
          vehicle_person_evidence: 0,
          no_clear_proposal: 0,
          not_analyzed: 0,
          false_positives: 0,
        },
      ),
    [filterMetadataByItemId, queueItems],
  );

  const reviewFilters: ReviewFilterOption<ReviewFilter>[] = [
    { value: "all", label: "All", count: queueCounts.all },
    { value: "animal_evidence", label: "Animal evidence", count: queueCounts.animal_evidence },
    {
      value: "vehicle_person_evidence",
      label: "Vehicle / person",
      count: queueCounts.vehicle_person_evidence,
    },
    { value: "no_clear_proposal", label: "No clear proposal", count: queueCounts.no_clear_proposal },
    { value: "not_analyzed", label: "Not checked", count: queueCounts.not_analyzed },
    { value: "false_positives", label: "False positives", count: queueCounts.false_positives },
  ];
  const productQueueCounts = useMemo(
    () =>
      queueItems.reduce<Record<ProductReviewTab, number>>(
        (counts, item) => {
          if (item.target_type === "visit" && item.product_category === "animal") {
            counts.animals += 1;
          } else if (item.product_category === "other_activity") {
            counts.other_activity += 1;
          } else if (item.product_category === "unchecked") {
            counts.unchecked += 1;
          } else if (item.product_category === "legacy_activity") {
            counts.legacy_activity += 1;
          } else {
            counts.reviewed += 1;
          }
          return counts;
        },
        {
          animals: 0,
          other_activity: 0,
          unchecked: 0,
          legacy_activity: 0,
          reviewed: 0,
        },
      ),
    [queueItems],
  );

  const productReviewFilters: ReviewFilterOption<ProductReviewTab>[] = [
    { value: "animals", label: "Animals", count: productQueueCounts.animals },
    {
      value: "other_activity",
      label: "Other activity",
      count: productQueueCounts.other_activity,
    },
    { value: "unchecked", label: "Unchecked", count: productQueueCounts.unchecked },
    {
      value: "legacy_activity",
      label: "Legacy activity",
      count: productQueueCounts.legacy_activity,
    },
    { value: "reviewed", label: "Reviewed", count: productQueueCounts.reviewed },
  ];

  const sourceStreamOptions = useMemo(
    () => sourceStreamFilterOptions(filterMetadataByItemId),
    [filterMetadataByItemId],
  );

  const filteredItems = useMemo(
    () => {
      const normalizedSearch = textSearch.trim().toLowerCase();

      const matchingItems = queueItems.filter((item) => {
        if (skippedTargetIds.has(reviewQueueTargetId(item))) {
          return false;
        }
        if (!matchesProductReviewTab(item, productTab, showLegacyAndTestActivity)) {
          return false;
        }
        if (scopedVisitIds && !scopedVisitIds.has(reviewQueueTargetId(item))) {
          return false;
        }
        const metadata = filterMetadataByItemId.get(item.id);
        if (!metadata) {
          return false;
        }
        if (reviewFilter !== "all" && metadata.triage.category !== reviewFilter) {
          return false;
        }

        if (!matchesTargetFilter(item, targetTypeFilter)) {
          return false;
        }
        // Everyday Product / Discovery UX Closure v1: the "Reviewed" tab's
        // own definition (product_category === "reviewed") already fully
        // determines review status -- every matching item's review_status
        // is always "reviewed". The separate Status filter below defaults
        // to "unreviewed" (a sensible default for the other tabs), so
        // applying it here too silently ANDed an unsatisfiable condition:
        // opening the Reviewed tab always showed an empty "No review items
        // match these filters" with no indication why, since the
        // conflicting Status control lives in a collapsed panel.
        if (productTab !== "reviewed" && !matchesStatusFilter(item, reviewStatusFilter)) {
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
      if (reviewSort === "newest") {
        return matchingItems;
      }
      return [...matchingItems].sort((first, second) => {
        const firstTriage = filterMetadataByItemId.get(first.id)?.triage;
        const secondTriage = filterMetadataByItemId.get(second.id)?.triage;
        if (!firstTriage || !secondTriage) {
          return 0;
        }
        const rankDelta =
          reviewTriageSortRank(firstTriage.category) -
          reviewTriageSortRank(secondTriage.category);
        if (rankDelta !== 0) {
          return rankDelta;
        }
        return (secondTriage.confidence ?? 0) - (firstTriage.confidence ?? 0);
      });
    },
    [
      evidenceFilter,
      filterMetadataByItemId,
      queueItems,
      productTab,
      showLegacyAndTestActivity,
      skippedTargetIds,
      reviewFilter,
      reviewSort,
      reviewStatusFilter,
      scopedVisitIds,
      sourceStreamFilter,
      targetTypeFilter,
      textSearch,
    ],
  );
  const reviewPageCount = Math.max(
    1,
    Math.ceil(filteredItems.length / PRODUCT_REVIEW_PAGE_SIZE),
  );
  const pagedItems = useMemo(
    () =>
      filteredItems.slice(
        reviewPage * PRODUCT_REVIEW_PAGE_SIZE,
        (reviewPage + 1) * PRODUCT_REVIEW_PAGE_SIZE,
      ),
    [filteredItems, reviewPage],
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



  const visibleSpeciesSuggestionItems = useMemo(
    () =>
      filteredItems.filter((item) => isSpeciesSuggestionBatchEligible(item, taxonomyLabels)),
    [filteredItems, taxonomyLabels],
  );

  const selectedSpeciesSuggestionItems = useMemo(
    () =>
      filteredItems.filter(
        (item) =>
          isSpeciesSuggestionBatchEligible(item, taxonomyLabels) &&
          selectedSpeciesSuggestionVisitIds.includes(reviewQueueTargetId(item)),
      ),
    [filteredItems, selectedSpeciesSuggestionVisitIds, taxonomyLabels],
  );

  const isSpeciesSuggestionBatchRunning = speciesSuggestionBatch?.phase === "running";
  const speciesSuggestionBatchCountsValue = speciesSuggestionBatch
    ? speciesSuggestionBatchCounts(speciesSuggestionBatch)
    : null;


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
    if (reviewSort !== "newest") {
      chips.push({
        key: "order",
        label: "Order: Animals first",
        onClear: () => setReviewSort("newest"),
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
    reviewSort,
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
      setReviewSort("newest");
      setTargetTypeFilter("all");
      setEvidenceFilter("all");
      setSourceStreamFilter("all");
    }
    if (initialContext.source === "activity-library") {
      setReviewFilter("all");
      setReviewSort("newest");
      setTargetTypeFilter("visit");
      setEvidenceFilter("all");
      setSourceStreamFilter("all");
      setScopedVisitIds(new Set((initialContext.visitIds ?? []).slice(0, 50)));
      setShouldOpenFocusedFastReview(Boolean(initialContext.openFastReview));
    } else {
      setScopedVisitIds(null);
      setShouldOpenFocusedFastReview(false);
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
    setSelectedSpeciesSuggestionVisitIds([]);
    setBulkResult(null);
    setSpeciesSuggestionBatch((current) =>
      current?.phase === "running" ? current : null,
    );
    setReadinessHandoffLabel(
      initialContext.source === "classifier-readiness" ? nextSourceLabel : null,
    );
    onInitialContextConsumed?.();
  }, [initialContext, onInitialContextConsumed]);

  useEffect(() => {
    if (!shouldOpenFocusedFastReview) {
      return;
    }
    const firstUnresolved = filteredItems.find(
      (item) => item.target_type === "visit" && item.review_status === "needs_review",
    );
    if (firstUnresolved) {
      setFastReviewRequest(firstUnresolved);
    }
    setShouldOpenFocusedFastReview(false);
  }, [filteredItems, shouldOpenFocusedFastReview]);

  useEffect(() => {
    let isMounted = true;
    void apiClient
      .getReviewQueue({ includeReviewed: true })
      .then((nextItems) => {
        if (isMounted) {
          setQueueItems(nextItems);
        }
      })
      .catch(() => {
        // Keep the initial unresolved snapshot if reviewed-history loading is unavailable.
      });
    return () => {
      isMounted = false;
    };
  }, [items]);

  useEffect(() => {
    setReviewPage(0);
  }, [
    evidenceFilter,
    productTab,
    reviewFilter,
    reviewStatusFilter,
    showLegacyAndTestActivity,
    sourceStreamFilter,
    targetTypeFilter,
    textSearch,
  ]);

  useEffect(() => {
    setSelectedTargetIds([]);
    setSelectedSpeciesSuggestionVisitIds([]);
    setBulkResult(null);
    if (!isSpeciesSuggestionBatchRunning) {
      setSpeciesSuggestionBatch(null);
    }
  }, [
    evidenceFilter,
    isSpeciesSuggestionBatchRunning,
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
    const visibleVisitIds = new Set(
      visibleSpeciesSuggestionItems.map(reviewQueueTargetId),
    );
    setSelectedSpeciesSuggestionVisitIds((current) =>
      current.filter((visitId) => visibleVisitIds.has(visitId)),
    );
  }, [visibleSpeciesSuggestionItems]);

  useEffect(() => {
    speciesSuggestionBatchMountedRef.current = true;
    return () => {
      speciesSuggestionBatchMountedRef.current = false;
      speciesSuggestionBatchCancelRef.current = true;
    };
  }, []);


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



  function toggleSpeciesSuggestionBatchSelection(
    item: ReviewQueueItem,
    selected: boolean,
  ) {
    if (!isSpeciesSuggestionBatchEligible(item, taxonomyLabels)) {
      return;
    }
    const visitId = reviewQueueTargetId(item);
    setSelectedSpeciesSuggestionVisitIds((current) => {
      if (!selected) {
        return current.filter((selectedVisitId) => selectedVisitId !== visitId);
      }
      if (current.includes(visitId) || current.length >= MAX_SPECIES_SUGGESTION_BATCH_VISITS) {
        return current;
      }
      return [...current, visitId];
    });
  }

  function selectVisibleSpeciesSuggestionVisits() {
    setSelectedSpeciesSuggestionVisitIds(
      visibleSpeciesSuggestionItems
        .slice(0, MAX_SPECIES_SUGGESTION_BATCH_VISITS)
        .map(reviewQueueTargetId),
    );
    if (!isSpeciesSuggestionBatchRunning) {
      setSpeciesSuggestionBatch(null);
    }
  }

  function clearSpeciesSuggestionBatchSelection() {
    if (isSpeciesSuggestionBatchRunning) {
      return;
    }
    setSelectedSpeciesSuggestionVisitIds([]);
    setSpeciesSuggestionBatch(null);
  }

  function cancelSpeciesSuggestionBatch() {
    if (!isSpeciesSuggestionBatchRunning) {
      return;
    }
    speciesSuggestionBatchCancelRef.current = true;
    setMessage("Cancellation requested. The current Visit may finish safely.");
  }

  async function runSpeciesSuggestionBatch() {
    if (isSpeciesSuggestionBatchRunning) {
      return;
    }
    const selected = selectedSpeciesSuggestionItems.slice(
      0,
      MAX_SPECIES_SUGGESTION_BATCH_VISITS,
    );
    if (selected.length === 0) {
      setMessage("Select unresolved Visits before running species suggestions.");
      return;
    }

    speciesSuggestionBatchCancelRef.current = false;
    setMessage(null);
    setSpeciesSuggestionBatch({
      phase: "running",
      selectedTotal: selected.length,
      scheduledTotal: 0,
      currentVisitId: null,
      outcomes: [],
    });

    let prepared: ReviewQueueSpeciesSuggestionBatchPrepareResponse;
    try {
      prepared = await apiClient.prepareReviewQueueSpeciesSuggestionBatch({
        visit_ids: selected.map(reviewQueueTargetId),
      });
    } catch {
      if (speciesSuggestionBatchMountedRef.current) {
        setSpeciesSuggestionBatch({
          phase: "completed",
          selectedTotal: selected.length,
          scheduledTotal: 0,
          currentVisitId: null,
          outcomes: selected.map((item) => ({
            visitId: reviewQueueTargetId(item),
            title: item.title,
            status: "failed",
            message: "Selection validation could not be completed safely.",
            mediaAssetId: null,
            topSuggestion: null,
            wasScheduled: false,
          })),
        });
        setMessage("Species suggestion selection validation failed safely.");
      }
      return;
    }

    const itemsByVisitId = new Map(selected.map((item) => [reviewQueueTargetId(item), item]));
    const preflightOutcomes: SpeciesSuggestionBatchOutcome[] = prepared.results
      .filter((result) => result.status !== "queued")
      .map((result) => {
        const item = itemsByVisitId.get(result.visit_id);
        return {
          visitId: result.visit_id,
          title: item?.title ?? "Selected Visit",
          status: result.status === "setup_required" ? "setup_required" : "skipped",
          message: result.message,
          mediaAssetId: result.media_asset_id ?? null,
          topSuggestion: null,
          wasScheduled: false,
          candidatePackLabel: candidatePackLabel(result.candidate_pack),
          candidatePackWarning: result.candidate_pack_warning,
        };
      });
    const queued = prepared.results.filter((result) => result.status === "queued");
    if (!speciesSuggestionBatchMountedRef.current) {
      return;
    }
    setSpeciesSuggestionBatch({
      phase: speciesSuggestionBatchCancelRef.current ? "canceled" : "running",
      selectedTotal: selected.length,
      scheduledTotal: queued.length,
      currentVisitId: null,
      outcomes: preflightOutcomes,
    });

    for (const preparedItem of queued) {
      if (speciesSuggestionBatchCancelRef.current) {
        break;
      }
      const item = itemsByVisitId.get(preparedItem.visit_id);
      if (!item) {
        continue;
      }
      if (!speciesSuggestionBatchMountedRef.current) {
        return;
      }
      setSpeciesSuggestionBatch((current) =>
        current
          ? { ...current, currentVisitId: preparedItem.visit_id }
          : current,
      );

      let outcome: SpeciesSuggestionBatchOutcome;
      try {
        const response = await apiClient.startVisitIdentificationAssistant(
          preparedItem.visit_id,
          {
            evidence_mode: "primary_only",
            idempotency_key: createFastReviewKey("batch-species-suggestion"),
          },
        );
        outcome = batchOutcomeFromAssistant(item, response);
      } catch {
        outcome = {
          visitId: preparedItem.visit_id,
          title: item.title,
          status: "failed",
          message: "Species suggestion failed safely for this Visit.",
          mediaAssetId: preparedItem.media_asset_id ?? null,
          topSuggestion: null,
          wasScheduled: true,
        };
      }
      if (!speciesSuggestionBatchMountedRef.current) {
        return;
      }
      setSpeciesSuggestionBatch((current) =>
        current
          ? {
              ...current,
              currentVisitId: null,
              outcomes: [...current.outcomes, outcome],
            }
          : current,
      );
    }

    if (!speciesSuggestionBatchMountedRef.current) {
      return;
    }
    const canceled = speciesSuggestionBatchCancelRef.current;
    setSpeciesSuggestionBatch((current) =>
      current
        ? { ...current, currentVisitId: null, phase: canceled ? "canceled" : "completed" }
        : current,
    );
    try {
      setQueueItems(await apiClient.getReviewQueue({ includeReviewed: true }));
    } catch {
      // Completed evidence stays durable; a manual refresh can restore this view.
    }
    setSelectedSpeciesSuggestionVisitIds([]);
    setMessage(
      canceled
        ? "Species suggestion batch canceled after the current Visit finished."
        : "Species suggestion batch completed. Suggestions remain evidence only.",
    );
  }


  function clearReadinessSearch() {
    setTextSearch("");
    setReadinessHandoffLabel(null);
    setSelectedTargetIds([]);
    setSelectedSpeciesSuggestionVisitIds([]);
    setBulkResult(null);
    if (!isSpeciesSuggestionBatchRunning) {
      setSpeciesSuggestionBatch(null);
    }
  }

  function resetReviewFilters() {
    setReviewFilter("all");
    setReviewSort("newest");
    setTextSearch("");
    setTargetTypeFilter("all");
    setEvidenceFilter("all");
    setSourceStreamFilter("all");
    setReviewStatusFilter("all");
    setReadinessHandoffLabel(null);
    setSelectedTargetIds([]);
    setSelectedSpeciesSuggestionVisitIds([]);
    setBulkResult(null);
    if (!isSpeciesSuggestionBatchRunning) {
      setSpeciesSuggestionBatch(null);
    }
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
      const refreshedQueue = await apiClient.getReviewQueue({ includeReviewed: true });
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
      let suggestionStatusWarning = "";
      if (acceptedSuggestionId) {
        try {
          await apiClient.updateSpeciesSuggestionStatus(acceptedSuggestionId, "accepted");
        } catch (caught) {
          const detail =
            caught instanceof Error ? caught.message : "status update failed";
          suggestionStatusWarning =
            ` Suggestion evidence status was not updated (${detail});` +
            " the correction is still saved truth.";
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
        } still need review.${suggestionStatusWarning}`,
      );
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Correction could not be saved.");
    } finally {
      setSavingId(null);
    }
  }

  async function saveCorrection(item: ReviewQueueItem) {
    const draft = drafts[item.id] ?? { label: item.suggested_label ?? "", notes: "" };
    await saveCorrectionWithLabel(
      item,
      draft.label,
      draft.notes,
      pendingSuggestionIdForCorrection(item, draft.label),
    );
  }

  async function runIdentificationAssist(item: ReviewQueueItem) {
    if (identifyingId !== null) {
      return;
    }
    const targetType = reviewQueueTargetType(item);
    const targetId = reviewQueueTargetId(item);
    const identification = item.identification;
    const mediaAssetId = item.best_media_asset_id ?? item.media_asset?.id ?? null;

    setIdentifyingId(item.id);
    setMessage(null);
    try {
      const message =
        targetType === "visit"
          ? (
              await apiClient.startVisitIdentificationAssistant(targetId, {
                evidence_mode: "primary_only",
                idempotency_key: createFastReviewKey("identification-assistant"),
              })
            ).message
          : (
              await apiClient.identifyReviewQueueItem(targetType, targetId, {
                adapter_id: identification?.adapter_id ?? undefined,
                media_asset_id: mediaAssetId ?? undefined,
              })
            ).identification.message;
      const refreshedQueue = await apiClient.getReviewQueue({ includeReviewed: true });
      setQueueItems(refreshedQueue);
      await refreshDetectionEvidence();
      setMessage(message);
    } catch (caught) {
      setMessage(
        caught instanceof Error ? caught.message : "Identification assist could not run.",
      );
    } finally {
      setIdentifyingId(null);
    }
  }

  async function rejectIdentificationSuggestion(item: ReviewQueueItem) {
    if (identifyingId !== null) {
      return;
    }
    const suggestionId = item.identification?.suggestion?.id;
    if (!suggestionId) {
      return;
    }
    setIdentifyingId(item.id);
    setMessage(null);
    try {
      await apiClient.updateSpeciesSuggestionStatus(suggestionId, "rejected");
      const refreshedQueue = await apiClient.getReviewQueue({ includeReviewed: true });
      setQueueItems(refreshedQueue);
      setMessage("Suggestion rejected as evidence. No review truth was created.");
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Suggestion could not be rejected.");
    } finally {
      setIdentifyingId(null);
    }
  }

  async function rejectIdentificationProposal(item: ReviewQueueItem) {
    if (identifyingId !== null) {
      return;
    }
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
      const refreshedQueue = await apiClient.getReviewQueue({ includeReviewed: true });
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
          title="No wildlife moments ready for review"
          description="MockingBird only surfaces a candidate here once it has a clear enough moment to actually review. If observation is running but nothing appears, MockingBird saw activity but couldn't capture a clear enough moment yet -- that's expected, not an error."
          action={
            <button className="primary-action" onClick={onOpenExports}>
              Open Dataset Exports
            </button>
          }
        />
      ) : null}
      {queueItems.length > 0 ? (
        <section className="review-triage-bar" aria-label="Product Mode review queue">
          <div className="review-triage-copy">
            <strong>Product Mode</strong>
            <span>
              Current detector-qualified animal Visits are shown first. Detector evidence
              is not a species result; a correction is still the only truth action.
            </span>
          </div>
          <ReviewFilterTabs
            activeFilter={productTab}
            filters={productReviewFilters}
            label="Product review groups"
            onChange={setProductTab}
          />
          <label className="review-triage-order">
            <input
              checked={showLegacyAndTestActivity}
              onChange={(event) => setShowLegacyAndTestActivity(event.target.checked)}
              type="checkbox"
            />
            Show legacy and test activity
          </label>
          <details className="review-diagnostic-details">
            <summary>Developer evidence filters</summary>
            <ReviewFilterTabs
              activeFilter={reviewFilter}
              filters={reviewFilters}
              label="Developer review evidence groups"
              onChange={setReviewFilter}
            />
            <label className="review-triage-order">
              Review order
              <select
                onChange={(event) => setReviewSort(event.target.value as ReviewSort)}
                value={reviewSort}
              >
                <option value="newest">Newest first</option>
                <option value="animals_first">Analyzer evidence first</option>
              </select>
            </label>
          </details>
        </section>
      ) : null}
      {queueItems.length > 0 ? (
        <details
          className="panel species-review-panel review-secondary-details"
          open={Boolean(readinessHandoffLabel)}
        >
          <summary>
            <span>Filter review items</span>
            <strong>
              {filteredItems.length} showing / {queueItems.length} total
            </strong>
          </summary>
          <span className="meta-text">
            Narrow the selected evidence group by subject, camera, or review status.
          </span>
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
        </details>
      ) : null}
      {queueItems.length > 0 ? (
        <details className="panel review-bulk-panel review-secondary-details">
          <summary>
            <span>Bulk correction</span>
            <strong>
              {selectedTargetIds.length} selected / {visibleEligibleItems.length} eligible
            </strong>
          </summary>
          <span className="meta-text">
            Apply one correction to selected unreviewed items.
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
        </details>
      ) : null}

      {queueItems.length > 0 ? (
        <details
          className="panel review-bulk-panel review-secondary-details"
          open={isSpeciesSuggestionBatchRunning}
        >
          <summary>
            <span>Batch species suggestions</span>
            <strong>
              {selectedSpeciesSuggestionVisitIds.length} selected / {visibleSpeciesSuggestionItems.length} visible unresolved Visits
            </strong>
          </summary>
          <span className="meta-text">
            The current filtered result set only. At most {MAX_SPECIES_SUGGESTION_BATCH_VISITS} Visits run sequentially; suggestions stay evidence only.
          </span>
          <div className="review-bulk-actions">
            <button
              className="secondary-action"
              disabled={
                visibleSpeciesSuggestionItems.length === 0 ||
                isSpeciesSuggestionBatchRunning
              }
              onClick={selectVisibleSpeciesSuggestionVisits}
              type="button"
            >
              Select visible Visits (up to {MAX_SPECIES_SUGGESTION_BATCH_VISITS})
            </button>
            <button
              className="secondary-action"
              disabled={
                selectedSpeciesSuggestionVisitIds.length === 0 ||
                isSpeciesSuggestionBatchRunning
              }
              onClick={clearSpeciesSuggestionBatchSelection}
              type="button"
            >
              Clear selection
            </button>
            <button
              className="primary-action"
              disabled={
                selectedSpeciesSuggestionItems.length === 0 ||
                isSpeciesSuggestionBatchRunning
              }
              onClick={() => void runSpeciesSuggestionBatch()}
              type="button"
            >
              Suggest species for selected
            </button>
            {isSpeciesSuggestionBatchRunning ? (
              <button
                className="secondary-action"
                onClick={cancelSpeciesSuggestionBatch}
                type="button"
              >
                Cancel after current Visit
              </button>
            ) : null}
          </div>
          {visibleSpeciesSuggestionItems.length > MAX_SPECIES_SUGGESTION_BATCH_VISITS ? (
            <span className="field-helper">
              Select visible chooses the first {MAX_SPECIES_SUGGESTION_BATCH_VISITS} Visits in this filtered order.
            </span>
          ) : null}
          <span className="field-helper">
            Each Visit independently resolves its Stream's active pack. Scores are uncalibrated and relative; no suggestion is selected automatically.
          </span>
          {speciesSuggestionBatch && speciesSuggestionBatchCountsValue ? (
            <div aria-live="polite" className="notice-panel review-bulk-result">
              <strong>
                {formatLabel(speciesSuggestionBatch.phase)} batch: {speciesSuggestionBatch.selectedTotal} selected
              </strong>
              <span>
                {speciesSuggestionBatchCountsValue.queued} queued · {speciesSuggestionBatch.currentVisitId ? `analyzing ${speciesSuggestionBatch.currentVisitId}` : "no Visit currently analyzing"} · {speciesSuggestionBatchCountsValue.completedWithNewEvidence} new evidence · {speciesSuggestionBatchCountsValue.reused} reused · {speciesSuggestionBatchCountsValue.skipped} skipped · {speciesSuggestionBatchCountsValue.setupRequired} setup required · {speciesSuggestionBatchCountsValue.failed} failed · {speciesSuggestionBatchCountsValue.canceled} canceled
              </span>
              <span>
                Summary: {speciesSuggestionBatchCountsValue.completedWithNewEvidence} analyzed with new evidence, {speciesSuggestionBatchCountsValue.reused} existing result{speciesSuggestionBatchCountsValue.reused === 1 ? "" : "s"} reused, {speciesSuggestionBatchCountsValue.skipped} skipped, {speciesSuggestionBatchCountsValue.failed} failed.
              </span>
              {speciesSuggestionBatch.outcomes.length > 0 ? (
                <details className="review-diagnostic-details">
                  <summary>Per-Visit batch results</summary>
                  <div className="review-diagnostic-grid">
                    {speciesSuggestionBatch.outcomes.map((outcome) => (
                      <span key={outcome.visitId}>
                        {outcome.visitId}: {formatLabel(outcome.status)}
                        {outcome.mediaAssetId ? ` - ${outcome.mediaAssetId}` : ""}
                        {outcome.topSuggestion ? ` - ${displayTaxonomyLabel(outcome.topSuggestion, taxonomyLabels)}` : ""}
                        {outcome.candidatePackLabel ? ` - ${outcome.candidatePackLabel}` : ""}.
                        {" "}{outcome.message}
                        {outcome.candidatePackWarning ? ` Warning: ${outcome.candidatePackWarning}` : ""}
                      </span>
                    ))}
                  </div>
                </details>
              ) : null}
            </div>
          ) : null}
        </details>
      ) : null}

      <FastReviewPanel
        items={filteredItems.filter(
          (item) => item.target_type === "visit" && item.review_status === "needs_review",
        )}
        recentLabelValues={recentLabelValues}
        taxonomyLabelValues={taxonomyLabelValues}
        taxonomyLabels={taxonomyLabels}
        onQueueItemsChange={setQueueItems}
        onReviewChanged={onFastReviewChanged}
        requestedItem={fastReviewRequest}
        onRequestedItemConsumed={() => setFastReviewRequest(null)}
      />
      <CorrectionAuditPanel
        groups={correctionAuditGroups}
        onOpenEvent={onOpenEvent}
        onOpenVisit={onOpenVisit}
        taxonomyLabels={taxonomyLabels}
      />
      <div className="queue-list">
        {pagedItems.map((item) => {
          if (productMode) {
            return (
              <ProductReviewCard
                item={item}
                key={item.id}
                onFalsePositive={() =>
                  void saveCorrectionWithLabel(
                    item,
                    "false_positive",
                    "Marked false positive from Product Mode.",
                  )
                }
                onOpenReview={() =>
                  item.visit_id
                    ? onOpenVisit(item.visit_id)
                    : onOpenEvent(item.event_id ?? reviewQueueTargetId(item))
                }
                onSkip={() => {
                  setSkippedTargetIds(
                    (current) => new Set([...current, reviewQueueTargetId(item)]),
                  );
                  setMessage("Skipped for this browser session. No review state changed.");
                }}
                onStartFastReview={() => setFastReviewRequest(item)}
                taxonomyLabels={taxonomyLabels}
              />
            );
          }
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
          const isSpeciesSuggestionSelected = selectedSpeciesSuggestionVisitIds.includes(targetId);
          const isSpeciesSuggestionEligible = isSpeciesSuggestionBatchEligible(item, taxonomyLabels);
          const speciesSuggestionSelectionAtLimit =
            !isSpeciesSuggestionSelected &&
            selectedSpeciesSuggestionVisitIds.length >= MAX_SPECIES_SUGGESTION_BATCH_VISITS;
          const identification = item.identification ?? null;
          const identificationSuggestion = identification?.suggestion ?? null;
          const linkedSpeciesSuggestion =
            identificationSuggestion?.id === item.suggestion_id
              ? identificationSuggestion
              : null;
          const suggestionMetricLabel = linkedSpeciesSuggestion
            ? speciesSuggestionMetricLabel(linkedSpeciesSuggestion)
            : "confidence";
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
          const itemTriage = itemSourceStreamMetadata?.triage ?? {
            category: "not_analyzed" as const,
            confidence: null,
            hasAnalyzerRun: false,
            label: null,
            secondaryConfidence: null,
            secondaryLabel: null,
          };
          const sourceLabel = reviewQueueSourceLabel(item, itemSourceStreamMetadata);
          const streamLabel = reviewQueueStreamLabel(item, itemSourceStreamMetadata);
          const zoneLabel = reviewItemZoneLabel(item);
          const isLiveActivity = isLiveActivityReviewItem(item);
          const evidenceFrames = item.evidence_frames ?? [];
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
                style={normalizedOverlayStyle(item.focus_crop_box_normalized)}
              >
                <span>Activity focus</span>
              </span>
            ) : null;
          const itemProposalOverlays = reviewProposalOverlays(
            itemEvidenceProposals,
            item.best_media_asset_id ?? item.media_asset?.id ?? null,
          );
          const labeledOverlayTones = new Set<ProposalOverlayTone>();
          const analyzerProposalOverlays = itemProposalOverlays.map(({ proposal }) => {
            const style = normalizedOverlayStyle(proposal.bbox);
            if (!style) {
              return null;
            }
            const tone = proposalOverlayTone(proposal, taxonomyLabels);
            const showLabel = !labeledOverlayTones.has(tone);
            labeledOverlayTones.add(tone);
            return (
              <span
                aria-hidden="true"
                className={`review-proposal-overlay review-proposal-overlay-${tone}`}
                key={proposal.id}
                style={style}
              >
                {showLabel ? <span>{proposalOverlayLabel(proposal, taxonomyLabels)}</span> : null}
              </span>
            );
          });
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
                  {item.target_type === "visit" && item.review_status === "needs_review" ? (
                    <button className="text-action" onClick={() => setFastReviewRequest(item)} type="button">
                      Fast review
                    </button>
                  ) : null}
                  <StatusPill label={formatLabel(item.review_status)} tone="review" />
                </div>
              </div>
              <details className="review-bulk-selection-details">
                <summary>Bulk selection</summary>
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
              </details>
              <details className="review-bulk-selection-details">
                <summary>Batch species selection</summary>
                <label className="checkbox-row review-bulk-select">
                  <input
                    checked={isSpeciesSuggestionSelected}
                    disabled={
                      !isSpeciesSuggestionEligible ||
                      isSpeciesSuggestionBatchRunning ||
                      speciesSuggestionSelectionAtLimit
                    }
                    onChange={(event) =>
                      toggleSpeciesSuggestionBatchSelection(item, event.target.checked)
                    }
                    type="checkbox"
                  />
                  {isSpeciesSuggestionEligible
                    ? isSpeciesSuggestionBatchRunning
                      ? "Batch species suggestion is currently running"
                      : speciesSuggestionSelectionAtLimit
                        ? `Batch limit of ${MAX_SPECIES_SUGGESTION_BATCH_VISITS} Visits reached`
                        : "Select for species suggestions"
                    : "Only unresolved bird Visits are eligible for species suggestions"}
                </label>
              </details>
              <p>
                {item.reason} Suggestion evidence is not truth; your correction becomes local
                dataset truth.
              </p>
              <div className={`review-item-triage review-item-triage-${itemTriage.category}`}>
                <div className="review-item-triage-copy">
                  <div className="review-item-triage-heading">
                    <EvidenceBadge
                      label={
                        itemTriage.confidence != null
                          ? `${formatLabel(itemTriage.category)} ${formatConfidence(
                              itemTriage.confidence,
                            )}`
                          : formatLabel(itemTriage.category)
                      }
                      tone={
                        itemTriage.category === "animal_evidence"
                          ? "review"
                          : itemTriage.category === "vehicle_person_evidence"
                            ? "evidence"
                            : "quiet"
                      }
                    />
                    {itemTriage.secondaryLabel && itemTriage.secondaryConfidence != null ? (
                      <EvidenceBadge
                        label={`${displayTaxonomyLabel(
                          itemTriage.secondaryLabel,
                          taxonomyLabels,
                        )} ${formatConfidence(itemTriage.secondaryConfidence)}`}
                        tone="evidence"
                      />
                    ) : null}
                    <strong>{reviewTriageTitle(itemTriage, taxonomyLabels)}</strong>
                  </div>
                  <span>
                    {reviewTriageDescription(
                      itemTriage,
                      identification,
                      Boolean(item.best_media_asset_id ?? item.media_asset?.id),
                    )}
                  </span>
                </div>
                {(itemTriage.category === "not_analyzed" ||
                  itemTriage.category === "no_clear_proposal") &&
                identification &&
                reviewIdentificationCanRun(identification) ? (
                  <button
                    className="secondary-action"
                    disabled={identifyingId !== null || savingId === item.id}
                    onClick={() => void runIdentificationAssist(item)}
                    type="button"
                  >
                    {identifyingId === item.id
                      ? "Checking..."
                      : itemTriage.category === "no_clear_proposal"
                        ? "Suggest species again"
                        : "Suggest species"}
                  </button>
                ) : null}
              </div>
              <div
                className={`review-candidate-context${
                  item.media_asset ? "" : " review-candidate-context-no-media"
                }`}
              >
                {evidenceFrames.length > 0 ? (
                  <div className="review-candidate-media">
                    <VisitEvidenceSequence
                      frames={evidenceFrames}
                      surfaceOverlay={
                        <>
                          {focusCropOverlay}
                          {analyzerProposalOverlays}
                        </>
                      }
                    />
                  </div>
                ) : item.media_asset ? (
                  <div className="review-candidate-media">
                    <MediaAssetPreview
                      asset={item.media_asset}
                      compact
                      surfaceOverlay={
                        <>
                          {focusCropOverlay}
                          {analyzerProposalOverlays}
                        </>
                      }
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
                    {evidenceFrames.length > 0 ? (
                      <span>{evidenceFrames.length} review frame{evidenceFrames.length === 1 ? "" : "s"}</span>
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
                  {itemProposalOverlays.length > 0 ? (
                    <div className="review-proposal-overlay-legend">
                      <strong>Analyzer boxes</strong>
                      <span className="review-proposal-legend-animal">Animal</span>
                      <span className="review-proposal-legend-person">Person</span>
                      <span className="review-proposal-legend-vehicle">Vehicle</span>
                      <span>
                        {itemProposalOverlays.length} shown - evidence only
                      </span>
                    </div>
                  ) : null}
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
                  <EvidenceBadge
                    label={
                      suggestionMetricLabel === "uncalibrated score"
                        ? "Uncalibrated model score"
                        : "Suggestion evidence"
                    }
                    tone="quiet"
                  />
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
                  <span>
                    {suggestionMetricLabel === "uncalibrated score"
                      ? "Uncalibrated score"
                      : "Confidence"}
                    : {formatConfidence(item.suggestion_confidence)}
                  </span>
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
                        ? `${
                            suggestionMetricLabel === "uncalibrated score"
                              ? "Uncalibrated score"
                              : "Confidence"
                          } ${formatConfidence(item.suggestion_confidence)}. `
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
                isBusy={identifyingId !== null || savingId === item.id}
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
        {filteredItems.length > PRODUCT_REVIEW_PAGE_SIZE ? (
          <div className="detail-actions review-page-controls">
            <span className="meta-text">
              Page {reviewPage + 1} of {reviewPageCount} · {filteredItems.length} matching Visits
            </span>
            <button
              className="secondary-action"
              disabled={reviewPage === 0}
              onClick={() => setReviewPage((current) => Math.max(0, current - 1))}
              type="button"
            >
              Previous
            </button>
            <button
              className="secondary-action"
              disabled={reviewPage + 1 >= reviewPageCount}
              onClick={() =>
                setReviewPage((current) => Math.min(reviewPageCount - 1, current + 1))
              }
              type="button"
            >
              Next
            </button>
          </div>
        ) : null}
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

function ProductReviewCard({
  item,
  onFalsePositive,
  onOpenReview,
  onSkip,
  onStartFastReview,
  taxonomyLabels,
}: {
  item: ReviewQueueItem;
  onFalsePositive: () => void;
  onOpenReview: () => void;
  onSkip: () => void;
  onStartFastReview: () => void;
  taxonomyLabels: TaxonomyLabel[];
}) {
  const explicitSuggestion =
    item.suggestion_id && item.identification?.suggestion?.id === item.suggestion_id
      ? item.identification.suggestion
      : null;
  const capturedAt = item.captured_at ?? item.activity_started_at ?? null;
  const location = [item.stream_name ?? item.stream_id, item.zone_name ?? "No Zone"].join(" · ");
  const evidenceClass = item.detector_class
    ? `${formatLabel(item.detector_class)} detector evidence`
    : item.product_category === "unchecked"
      ? "No detector qualification recorded"
      : "Legacy activity evidence";

  return (
    <article className="queue-card review-product-card">
      {item.media_asset ? (
        <MediaAssetPreview asset={item.media_asset} compact />
      ) : (
        <div className="review-product-image-unavailable">
          Primary evidence unavailable
        </div>
      )}
      <div className="review-product-card-copy">
        <div className="queue-card-heading">
          <div>
            <strong>{productReviewTitle(item, taxonomyLabels)}</strong>
            <span className="meta-text">
              {capturedAt ? formatDateTime(capturedAt) : "Capture time unavailable"} · {location}
            </span>
          </div>
          <EvidenceBadge
            label={item.product_category === "animal" ? "Animal evidence" : formatLabel(item.product_category)}
            tone={item.product_category === "animal" ? "review" : "quiet"}
          />
        </div>
        <div className="review-product-facts">
          <span>{evidenceClass}</span>
          {item.detector_score != null ? <span>Score {item.detector_score.toFixed(3)}</span> : null}
          <span>
            {item.evidence_count === 1 ? "1 evidence item" : `${item.evidence_count} evidence items`}
          </span>
        </div>
        {explicitSuggestion ? (
          <div className="review-product-suggestion">
            <strong>Species suggestions</strong>
            <span>
              {displayTaxonomyLabel(explicitSuggestion.suggested_label, taxonomyLabels)}
              {explicitSuggestion.confidence != null
                ? ` · relative score ${explicitSuggestion.confidence.toFixed(3)}`
                : ""}
              {" · evidence only"}
            </span>
            <span>
              {item.identification?.candidate_pack
                ? `Candidate pack ${item.identification.candidate_pack.display_name} v${item.identification.candidate_pack.version}`
                : "Open the Visit for full suggestion evidence."}
            </span>
            <button className="text-action" onClick={onOpenReview} type="button">
              View all suggestions
            </button>
          </div>
        ) : null}
        <div className="detail-actions">
          <button className="primary-action" onClick={onOpenReview} type="button">
            Review
          </button>
          {item.target_type === "visit" && item.review_status === "needs_review" ? (
            <button className="secondary-action" onClick={onStartFastReview} type="button">
              Fast Review
            </button>
          ) : null}
          {item.review_status === "needs_review" ? (
            <>
              <button className="secondary-action" onClick={onFalsePositive} type="button">
                False positive
              </button>
              <button className="text-action" onClick={onSkip} type="button">
                Skip
              </button>
            </>
          ) : null}
        </div>
        <details className="review-diagnostic-details">
          <summary>Developer evidence</summary>
          <div className="review-diagnostic-grid">
            <span>Queue item: {item.id}</span>
            <span>Track generation: {item.track_generation_id ?? "not recorded"}</span>
            <span>Detector: {item.detector_class ?? "not recorded"}</span>
            <span>
              Evidence IDs: {item.evidence_frames.map((frame) => frame.media_asset_id).join(", ") || item.media_asset?.id || "none"}
            </span>
            <span>Review status: {formatLabel(item.review_status)}</span>
          </div>
          {item.detector_provenance ? (
            <pre className="review-product-provenance">
              {JSON.stringify(item.detector_provenance, null, 2)}
            </pre>
          ) : (
            <span className="meta-text">Raw detector provenance was not recorded.</span>
          )}
        </details>
      </div>
    </article>
  );
}

interface FastReviewUndoState {
  label: string;
  reviewLabelId: string;
  stateToken: string;
  targetId: string;
}

function createFastReviewKey(prefix: string): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return prefix + "-" + crypto.randomUUID();
  }
  return prefix + "-" + Date.now() + "-" + Math.random().toString(36).slice(2);
}

function isFastReviewTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return (
    target.isContentEditable ||
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement ||
    Boolean(target.closest(".identification-assistant"))
  );
}

function fastReviewDuration(item: ReviewQueueItem): string {
  if (!item.activity_started_at || !item.activity_last_seen_at) {
    return "Duration unavailable";
  }
  const seconds = Math.max(
    0,
    Math.round(
      (new Date(item.activity_last_seen_at).getTime() -
        new Date(item.activity_started_at).getTime()) /
        1000,
    ),
  );
  if (seconds < 60) {
    return seconds + "s";
  }
  return Math.floor(seconds / 60) + "m " + (seconds % 60) + "s";
}

function FastReviewPanel({
  items,
  recentLabelValues,
  taxonomyLabelValues,
  taxonomyLabels,
  onQueueItemsChange,
  onReviewChanged,
  requestedItem,
  onRequestedItemConsumed,
}: {
  items: ReviewQueueItem[];
  recentLabelValues: string[];
  taxonomyLabelValues: string[];
  taxonomyLabels: TaxonomyLabel[];
  onQueueItemsChange: (items: ReviewQueueItem[]) => void;
  onReviewChanged: () => Promise<void>;
  requestedItem: ReviewQueueItem | null;
  onRequestedItemConsumed: () => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [activeItem, setActiveItem] = useState<ReviewQueueItem | null>(null);
  const [draftLabel, setDraftLabel] = useState("");
  const [draftNotes, setDraftNotes] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isNavigating, setIsNavigating] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [processedCount, setProcessedCount] = useState(0);
  const [undoState, setUndoState] = useState<FastReviewUndoState | null>(null);
  const [isFavoritingLastCorrection, setIsFavoritingLastCorrection] = useState(false);
  const [lastCorrectionFavorited, setLastCorrectionFavorited] = useState(false);
  const [availableTags, setAvailableTags] = useState<VisitTagSummary[]>([]);
  const [postCorrectionTagId, setPostCorrectionTagId] = useState("");
  const [newPostCorrectionTag, setNewPostCorrectionTag] = useState("");
  const [identificationAssistant, setIdentificationAssistant] = useState<VisitIdentificationAssistantResponse | null>(null);
  const [identificationAssistantError, setIdentificationAssistantError] = useState<string | null>(null);
  const [isLoadingIdentificationAssistant, setIsLoadingIdentificationAssistant] = useState(false);
  const [isRunningIdentificationAssistant, setIsRunningIdentificationAssistant] = useState(false);
  const [assistantPrefillSuggestionId, setAssistantPrefillSuggestionId] = useState<string | null>(null);
  const [reviewSessionId] = useState(() => createFastReviewKey("fast-review-session"));

  useEffect(() => { void apiClient.getVisitTags().then(setAvailableTags).catch(() => setAvailableTags([])); }, []);

  // Navigation accepts a bounded snapshot rather than the full queue. Its order is
  // exactly the active Review Queue order, so filters and Stream scoping are retained.
  const boundedItems = useMemo(() => items.slice(0, 200), [items]);
  const orderedTargets = useMemo(
    () =>
      boundedItems.map((item) => ({
        target_type: "visit" as const,
        target_id: reviewQueueTargetId(item),
      })),
    [boundedItems],
  );
  const scopedStreamId = useMemo(() => {
    const streamIds = new Set(boundedItems.map((item) => item.stream_id));
    return streamIds.size === 1 ? boundedItems[0]?.stream_id ?? null : null;
  }, [boundedItems]);
  const suggestedLabels = useMemo(
    () =>
      uniqueLabelValues(
        activeItem?.suggestion_id ? [activeItem.suggested_label] : [],
      ),
    [activeItem],
  );
  const activeFullResolutionFrame = activeItem?.evidence_frames.find(
    (frame) => frame.evidence_role === "high_resolution_original",
  ) ?? null;
  const activeCropBounds = activeItem?.evidence_frames.find(
    (frame) => frame.is_primary,
  )?.normalized_crop_box ?? null;
  const helperGroups = useMemo(
    () => labelHelperGroups(suggestedLabels, recentLabelValues, taxonomyLabelValues),
    [recentLabelValues, suggestedLabels, taxonomyLabelValues],
  );
  const labelValidation = useMemo(
    () =>
      classifyCorrectionLabel(draftLabel, {
        recentLabels: recentLabelValues,
        suggestedLabels,
        taxonomyLabelValues,
        taxonomyLabels,
      }),
    [draftLabel, recentLabelValues, suggestedLabels, taxonomyLabelValues, taxonomyLabels],
  );

  useEffect(() => {
    if (!activeItem) {
      return;
    }
    const refreshed = items.find(
      (item) => reviewQueueTargetId(item) === reviewQueueTargetId(activeItem),
    );
    if (refreshed) {
      setActiveItem(refreshed);
    } else if (isOpen && !isSaving && !isNavigating) {
      setActiveItem(null);
      setMessage("Filters changed. Reopen Fast Review to continue within the new queue.");
    }
  }, [activeItem, isNavigating, isOpen, isSaving, items]);

  function selectItem(item: ReviewQueueItem) {
    setActiveItem(item);
    setDraftLabel("");
    setDraftNotes("");
    setAssistantPrefillSuggestionId(null);
    setMessage(null);
    setIsOpen(true);
  }

  useEffect(() => {
    if (!requestedItem) {
      return;
    }
    const matchingItem = items.find((item) => item.id === requestedItem.id);
    if (matchingItem) {
      selectItem(matchingItem);
    }
    onRequestedItemConsumed();
  }, [items, onRequestedItemConsumed, requestedItem]);

  async function refreshProductState(): Promise<ReviewQueueItem[]> {
    const refreshed = await apiClient.getReviewQueue({ includeReviewed: true });
    onQueueItemsChange(refreshed);
    await onReviewChanged();
    return refreshed;
  }

  async function navigate(direction: "next" | "previous", current = activeItem) {
    if (!current || orderedTargets.length === 0) {
      return;
    }
    setIsNavigating(true);
    setMessage(null);
    try {
      const response = await apiClient.navigateFastReviewQueue({
        ordered_targets: orderedTargets,
        current_target: {
          target_type: "visit",
          target_id: reviewQueueTargetId(current),
        },
        direction,
        stream_id: scopedStreamId,
      });
      if (!response.item) {
        setActiveItem(null);
        setMessage(response.message);
        return;
      }
      setActiveItem(response.item);
      setDraftLabel("");
      setDraftNotes("");
      setAssistantPrefillSuggestionId(null);
      setMessage(
        String(response.position ?? 1) +
          " of " +
          response.unresolved_count +
          " unresolved Visit" +
          (response.unresolved_count === 1 ? "" : "s") +
          " in this filtered queue.",
      );
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Could not move through Fast Review.");
    } finally {
      setIsNavigating(false);
    }
  }

  async function saveAndNext(label = draftLabel, notes = draftNotes) {
    if (!activeItem || isSaving) {
      return;
    }
    const trimmedLabel = label.trim();
    if (!trimmedLabel) {
      setMessage("Choose or type a correction label before saving.");
      return;
    }

    setIsSaving(true);
    setMessage(null);
    try {
      const response = await apiClient.createFastReviewCorrection({
        target_type: "visit",
        target_id: reviewQueueTargetId(activeItem),
        label: trimmedLabel,
        notes: notes.trim() || null,
        review_session_id: reviewSessionId,
        idempotency_key: createFastReviewKey("fast-review-save"),
        expected_state_token: activeItem.review_state_token,
      });
      setUndoState({
        label: response.result.review_label.label,
        reviewLabelId: response.result.review_label.id,
        stateToken: response.undo_state_token,
        targetId: response.result.review_label.target_id,
      });
      setLastCorrectionFavorited(false);
      setProcessedCount((count) => count + (response.idempotent ? 0 : 1));
      await refreshProductState();
      await navigate("next", activeItem);
    } catch (caught) {
      setMessage(
        caught instanceof Error
          ? caught.message
          : "Correction could not be saved. This Visit may have changed elsewhere.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function undoLastCorrection() {
    if (!undoState || isSaving) {
      return;
    }
    setIsSaving(true);
    setMessage(null);
    try {
      await apiClient.undoFastReviewCorrection({
        review_label_id: undoState.reviewLabelId,
        review_session_id: reviewSessionId,
        idempotency_key: createFastReviewKey("fast-review-undo"),
        expected_state_token: undoState.stateToken,
      });
      const refreshed = await refreshProductState();
      const restored = refreshed.find(
        (item) => item.target_type === "visit" && reviewQueueTargetId(item) === undoState.targetId,
      );
      if (restored) {
        setActiveItem(restored);
        setDraftLabel("");
        setDraftNotes("");
      }
      setUndoState(null);
      setProcessedCount((count) => Math.max(0, count - 1));
      setMessage("Correction undone. The Visit is back in its prior review state.");
    } catch (caught) {
      setMessage(
        caught instanceof Error
          ? caught.message
          : "Undo is no longer available because a newer correction replaced it.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function favoriteLastCorrectedVisit() {
    if (!undoState || isFavoritingLastCorrection || lastCorrectionFavorited) return;
    setIsFavoritingLastCorrection(true);
    try {
      const organization = await apiClient.getVisitOrganization(undoState.targetId);
      await apiClient.updateVisitOrganization(undoState.targetId, {
        is_favorite: true,
        expected_state_token: organization.state_token,
        idempotency_key: createFastReviewKey("fast-review-favorite"),
      });
      setLastCorrectionFavorited(true);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Could not favorite that Visit.");
    } finally {
      setIsFavoritingLastCorrection(false);
    }
  }

  async function tagLastCorrectedVisit() {
    const tag = availableTags.find((item) => item.id === postCorrectionTagId);
    if (!undoState || !tag) return;
    try { await apiClient.addVisitTag(tag.id, undoState.targetId, { expected_state_token: tag.state_token, idempotency_key: createFastReviewKey("fast-review-tag") }); setMessage(`Correction saved; added tag “${tag.name}” independently.`); setPostCorrectionTagId(""); const refreshed = await apiClient.getVisitTags(); setAvailableTags(refreshed); }
    catch (caught) { setMessage(caught instanceof Error ? caught.message : "Correction was saved, but the tag could not be added."); }
  }

  async function createAndTagLastCorrectedVisit() {
    if (!undoState || !newPostCorrectionTag.trim()) return;
    try { const tag = await apiClient.createVisitTag({ name: newPostCorrectionTag, idempotency_key: createFastReviewKey("fast-review-tag-create") }); setNewPostCorrectionTag(""); setAvailableTags((current) => [...current, tag]); await apiClient.addVisitTag(tag.id, undoState.targetId, { expected_state_token: tag.state_token, idempotency_key: createFastReviewKey("fast-review-tag-add") }); setMessage(`Correction saved; created and added tag “${tag.name}” independently.`); }
    catch (caught) { setMessage(caught instanceof Error ? caught.message : "Correction was saved, but the new tag could not be added."); }
  }

  useEffect(() => {
    let isMounted = true;
    if (!activeItem) {
      setIdentificationAssistant(null);
      return () => {
        isMounted = false;
      };
    }
    setAssistantPrefillSuggestionId(null);
    setIsLoadingIdentificationAssistant(true);
    setIdentificationAssistantError(null);
    void apiClient
      .getVisitIdentificationAssistant(reviewQueueTargetId(activeItem))
      .then((response) => {
        if (isMounted) {
          setIdentificationAssistant(response);
        }
      })
      .catch((caught: unknown) => {
        if (isMounted) {
          setIdentificationAssistantError(
            caught instanceof Error ? caught.message : "Could not check Identification Assistant availability.",
          );
        }
      })
      .finally(() => {
        if (isMounted) {
          setIsLoadingIdentificationAssistant(false);
        }
      });
    return () => {
      isMounted = false;
    };
  }, [activeItem?.target_id]);

  async function runIdentificationAssistant() {
    if (!activeItem || isRunningIdentificationAssistant) {
      return;
    }
    setIsRunningIdentificationAssistant(true);
    setIdentificationAssistantError(null);
    try {
      const result = await apiClient.startVisitIdentificationAssistant(
        reviewQueueTargetId(activeItem),
        {
          evidence_mode: "primary_only",
          idempotency_key: createFastReviewKey("identification-assistant"),
        },
      );
      setIdentificationAssistant(result);
      setMessage(result.message);
      const refreshed = await apiClient.getReviewQueue({ includeReviewed: true });
      onQueueItemsChange(refreshed);
      const refreshedActive = refreshed.find(
        (item) => reviewQueueTargetId(item) === reviewQueueTargetId(activeItem),
      );
      if (refreshedActive) {
        setActiveItem(refreshedActive);
      }
    } catch (caught) {
      setIdentificationAssistantError(
        caught instanceof Error ? caught.message : "Identification Assistant could not analyze saved evidence.",
      );
    } finally {
      setIsRunningIdentificationAssistant(false);
    }
  }

  async function dismissIdentificationAssistantSuggestion(suggestionId: string) {
    try {
      const updated = await apiClient.updateSpeciesSuggestionStatus(suggestionId, "rejected");
      setIdentificationAssistant((current) =>
        current
          ? {
              ...current,
              suggestions: current.suggestions.map((suggestion) =>
                suggestion.suggestion_id === updated.id
                  ? { ...suggestion, status: updated.status }
                  : suggestion,
              ),
            }
          : current,
      );
      setMessage("Suggestion dismissed as evidence. No review truth was created.");
    } catch (caught) {
      setIdentificationAssistantError(
        caught instanceof Error ? caught.message : "Suggestion could not be dismissed.",
      );
    }
  }

  function useIdentificationAssistantSuggestion(label: string, suggestionId: string) {
    setDraftLabel(label);
    setAssistantPrefillSuggestionId(suggestionId);
    setMessage("Suggestion prefilled the label. Save & Next remains the explicit truth action.");
  }

  function clearIdentificationAssistantPrefill() {
    setAssistantPrefillSuggestionId(null);
    setDraftLabel("");
    setMessage("Suggestion prefill cleared. Choose a correction before saving.");
  }

  useEffect(() => {
    if (!isOpen || !activeItem) {
      return undefined;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (isFastReviewTypingTarget(event.target)) {
        return;
      }
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        event.preventDefault();
        void saveAndNext();
        return;
      }
      if (event.key.toLowerCase() === "n") {
        event.preventDefault();
        void navigate("next");
      } else if (event.key.toLowerCase() === "p") {
        event.preventDefault();
        void navigate("previous");
      } else if (event.key.toLowerCase() === "c") {
        event.preventDefault();
        void saveAndNext("bird", "Confirmed bird in Fast Review.");
      } else if (event.key.toLowerCase() === "k") {
        event.preventDefault();
        void saveAndNext("unknown_bird", "Marked unknown bird in Fast Review.");
      } else if (event.key.toLowerCase() === "b") {
        event.preventDefault();
        void saveAndNext("blank", "Marked blank or no activity in Fast Review.");
      } else if (event.key.toLowerCase() === "x") {
        event.preventDefault();
        void saveAndNext("non_bird", "Marked non-bird activity in Fast Review.");
      } else if (event.key.toLowerCase() === "u") {
        event.preventDefault();
        void saveAndNext("ambiguous", "Marked ambiguous activity in Fast Review.");
      } else if (event.key.toLowerCase() === "z") {
        event.preventDefault();
        void undoLastCorrection();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeItem, draftLabel, draftNotes, isOpen, isSaving, undoState]);

  if (items.length === 0) {
    return null;
  }

  if (!isOpen) {
    return (
      <section className="panel fast-review-launcher">
        <div>
          <span className="eyebrow">Focused workflow</span>
          <h2>Fast Review</h2>
          <p>
            Review one unresolved Visit at a time with evidence, explicit correction actions,
            and save-and-next. The current queue filters stay in effect.
          </p>
          {items.length > 200 ? (
            <span className="meta-text">Fast Review uses the first 200 matching Visits at a time.</span>
          ) : null}
        </div>
        <button className="primary-action" onClick={() => selectItem(boundedItems[0])} type="button">
          Start Fast Review ({Math.min(items.length, 200)})
        </button>
      </section>
    );
  }

  if (!activeItem) {
    return (
      <section className="panel fast-review-complete">
        <div>
          <span className="eyebrow">Fast Review</span>
          <h2>Filtered queue complete</h2>
          <p>{message ?? "No unresolved Visits remain in this filtered queue."}</p>
        </div>
        <button className="secondary-action" onClick={() => setIsOpen(false)} type="button">
          Return to Review Queue
        </button>
      </section>
    );
  }

  return (
    <section className="panel fast-review-panel" aria-label="Fast Review">
      <div className="fast-review-header">
        <div>
          <span className="eyebrow">Fast Review</span>
          <h2>{activeItem.title}</h2>
          <p>
            {processedCount} reviewed this session · {Math.min(boundedItems.length, 200)} matching
            unresolved Visit{boundedItems.length === 1 ? "" : "s"}
          </p>
        </div>
        <div className="detail-actions">
          <button
            className="secondary-action"
            disabled={isNavigating || isSaving}
            onClick={() => void navigate("previous")}
            type="button"
          >
            Previous Visit
          </button>
          <button
            className="secondary-action"
            disabled={isNavigating || isSaving}
            onClick={() => void navigate("next")}
            type="button"
          >
            Next Visit
          </button>
          <button className="text-action" onClick={() => setIsOpen(false)} type="button">
            Exit
          </button>
        </div>
      </div>
      {message ? <div className="notice-panel fast-review-message">{message}</div> : null}
      {undoState ? (
        <div className="fast-review-post-correction">
          <span>Correction saved independently of your Visit organization.</span>
          <button
            className="secondary-action"
            disabled={isFavoritingLastCorrection || lastCorrectionFavorited}
            onClick={() => void favoriteLastCorrectedVisit()}
            type="button"
          >
            {lastCorrectionFavorited ? "Favorited" : isFavoritingLastCorrection ? "Saving…" : "Favorite this Visit"}
          </button>
          <label>Add tag <select value={postCorrectionTagId} onChange={(event) => setPostCorrectionTagId(event.target.value)}><option value="">Choose tag</option>{availableTags.map((tag) => <option key={tag.id} value={tag.id}>{tag.name}</option>)}</select></label><button className="secondary-action" disabled={!postCorrectionTagId} onClick={() => void tagLastCorrectedVisit()} type="button">Add tag</button>
          <label>New tag <input maxLength={50} value={newPostCorrectionTag} onChange={(event) => setNewPostCorrectionTag(event.target.value)} /></label><button className="text-action" disabled={!newPostCorrectionTag.trim()} onClick={() => void createAndTagLastCorrectedVisit()} type="button">Create and add</button>
        </div>
      ) : null}
      <div className="fast-review-context">
        <div className="data-row">
          <span>Stream</span>
          <strong>{reviewQueueStreamLabel(activeItem)}</strong>
          <small>{reviewQueueSourceLabel(activeItem)}</small>
        </div>
        <div className="data-row">
          <span>Zone</span>
          <strong>{reviewItemZoneLabel(activeItem)}</strong>
          <small>{activeItem.activity_session_id ? "Live activity Visit" : "Review Queue Visit"}</small>
        </div>
        <div className="data-row">
          <span>Visit time</span>
          <strong>
            {activeItem.activity_started_at
              ? formatDateTime(activeItem.activity_started_at)
              : activeItem.media_asset?.created_at
                ? formatDateTime(activeItem.media_asset.created_at)
                : "Unavailable"}
          </strong>
          <small>Duration {fastReviewDuration(activeItem)}</small>
        </div>
        <div className="data-row">
          <span>Queue progress</span>
          <strong>{boundedItems.findIndex((item) => item.id === activeItem.id) + 1} / {boundedItems.length}</strong>
          <small>Current active filters only</small>
        </div>
      </div>
      <div className="fast-review-content">
        <div className="fast-review-evidence">
          {activeItem.evidence_frames.length > 0 ? (
            <VisitEvidenceSequence
              frames={activeItem.evidence_frames}
              keyboardControls
            />
          ) : activeItem.media_asset ? (
            <MediaAssetPreview asset={activeItem.media_asset} compact />
          ) : (
            <div className="fast-review-no-evidence">No saved evidence frame is available for this Visit.</div>
          )}
          {activeItem.visit_id && activeFullResolutionFrame ? (
            <div className="detail-actions">
              <RefinedCropEditor
                fullFrame={activeFullResolutionFrame}
                initialBounds={activeCropBounds}
                onSaved={(response) => {
                  setMessage(response.message);
                  void refreshProductState();
                }}
                visitId={activeItem.visit_id}
              />
            </div>
          ) : null}
          {activeItem.stale_species_suggestions ? (
            <div className="notice-panel compact-notice">Suggestions were generated from an earlier image. Run Suggest species again to analyze the refined crop.</div>
          ) : null}
        </div>
        <div className="fast-review-form">
          <IdentificationAssistant
            assistant={identificationAssistant}
            error={identificationAssistantError}
            isLoading={isLoadingIdentificationAssistant}
            isRunning={isRunningIdentificationAssistant}
            onAnalyze={() => void runIdentificationAssistant()}
            onClearPrefill={clearIdentificationAssistantPrefill}
            onRejectSuggestion={(suggestionId) => void dismissIdentificationAssistantSuggestion(suggestionId)}
            onUseSuggestion={useIdentificationAssistantSuggestion}
            prefilledSuggestionId={assistantPrefillSuggestionId}
          />
          <div className="fast-review-suggestions">
            <strong>Evidence-only suggestions</strong>
            {suggestedLabels.length > 0 ? (
              <div className="label-helper-chips">
                {suggestedLabels.map((label) => (
                  <button key={label} onClick={() => setDraftLabel(label)} type="button">
                    Use suggestion: {displayTaxonomyLabel(label, taxonomyLabels)}
                  </button>
                ))}
              </div>
            ) : (
              <span className="meta-text">No species suggestion is available for this Visit.</span>
            )}
            {activeItem.suggestion_confidence != null ? (
              <span className="meta-text">
                Evidence score: {formatConfidence(activeItem.suggestion_confidence)}. It is not an accepted label.
              </span>
            ) : null}
            <span className="field-helper">Choosing a suggestion only fills the label. Save confirms truth.</span>
          </div>
          <TaxonomyLabelInput
            label="Confirm species or wildlife label"
            labels={taxonomyLabels}
            onChange={setDraftLabel}
            placeholder="Search existing species or label"
            value={draftLabel}
          />
          <LabelValidationLine status={labelValidation} />
          <LabelHelperChips
            groups={helperGroups}
            onSelect={setDraftLabel}
            taxonomyLabels={taxonomyLabels}
          />
          <label>
            Notes
            <textarea
              onChange={(event) => setDraftNotes(event.target.value)}
              placeholder="optional review note"
              value={draftNotes}
            />
          </label>
          <div className="fast-review-actions">
            <button
              className="primary-action"
              disabled={isSaving || !draftLabel.trim()}
              onClick={() => void saveAndNext()}
              type="button"
            >
              {isSaving ? "Saving..." : "Save & Next"}
            </button>
            <button
              className="secondary-action"
              disabled={isSaving}
              onClick={() => void saveAndNext("bird", "Confirmed bird in Fast Review.")}
              type="button"
              title="Records generic 'bird', not whatever species is suggested above. To confirm a specific species, choose a suggestion chip first."
            >
              Generic bird (no species)
            </button>
            <button
              className="secondary-action"
              disabled={isSaving}
              onClick={() => void saveAndNext("unknown_bird", "Marked unknown bird in Fast Review.")}
              type="button"
            >
              Unknown bird
            </button>
            <button
              className="secondary-action"
              disabled={isSaving}
              onClick={() => void saveAndNext("blank", "Marked blank or no activity in Fast Review.")}
              type="button"
            >
              Blank / no activity
            </button>
            <button
              className="secondary-action"
              disabled={isSaving}
              onClick={() => void saveAndNext("false_positive", "Marked false activity in Fast Review.")}
              type="button"
            >
              False positive
            </button>
            <button
              className="secondary-action"
              disabled={isSaving}
              onClick={() => void saveAndNext("non_bird", "Marked non-bird activity in Fast Review.")}
              type="button"
            >
              Non-bird activity
            </button>
            <button
              className="secondary-action"
              disabled={isSaving}
              onClick={() => void saveAndNext("ambiguous", "Marked ambiguous activity in Fast Review.")}
              type="button"
            >
              Ambiguous / unknown
            </button>
          </div>
          {undoState ? (
            <div className="fast-review-undo">
              <span>Saved {displayTaxonomyLabel(undoState.label, taxonomyLabels)}.</span>
              <button className="text-action" disabled={isSaving} onClick={() => void undoLastCorrection()} type="button">
                Undo last correction
              </button>
            </div>
          ) : null}
          <details className="fast-review-shortcuts">
            <summary>Keyboard shortcuts</summary>
            <span>Left / Right: evidence frame · Space: play/pause · Ctrl/Cmd+Enter: save & next</span>
            <span>N / P: next / previous Visit · C: generic bird (no species) · K: unknown bird</span>
            <span>B: blank · X: non-bird · U: ambiguous · Z: undo</span>
            <span>Shortcuts are paused while typing in a search or notes field.</span>
          </details>
        </div>
      </div>
    </section>
  );
}

function IdentificationAssistPanel({
  identification,
  isBusy,
  onFillLabel,
  onRejectProposal,
  onRejectSuggestion,
  onRun,
  taxonomyLabels,
}: {
  identification: ReviewIdentificationSummary | null;
  isBusy: boolean;
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
  const suggestedDisplayLabel =
    optionalString(identification.suggestion?.suggested_common_name) ??
    (suggestedLabel
      ? displayTaxonomyLabel(suggestedLabel, taxonomyLabels)
      : "No suggestion");
  const suggestedScientificName =
    optionalString(identification.suggestion?.suggested_scientific_name);
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
  const rankedAlternatives = rankedSpeciesAlternatives(identification);
  const speciesCropSummary = speciesEvidenceRegionSummary(
    identification.suggestion?.evidence_region,
  );
  const scoreLabel = speciesScoreLabel(identification);

  return (
    <details className="review-identification-assist review-secondary-details">
      <summary>
        <span>Optional identification assist</span>
        <strong>{reviewIdentificationStatusLabel(identification)}</strong>
      </summary>
      <span className="meta-text">Suggestions stay evidence until correction.</span>
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
        {identification.candidate_pack ? (
          <div className="data-row">
            <span>Candidate pack</span>
            <strong>
              Compared against {identification.candidate_pack.candidate_count} species from {identification.candidate_pack.display_name} v{identification.candidate_pack.version}
            </strong>
            <small>
              {identification.candidate_pack_warning ?? "This Stream pack is resolved before each explicit suggestion."}
            </small>
          </div>
        ) : null}
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
          <span>Crop provenance</span>
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
                  )}. ${focusPixelLabel}.${speciesCropSummary ? ` Classifier input: ${speciesCropSummary}.` : ""}`
                : identification.focus_crop_warnings.length > 0
                  ? identification.focus_crop_warnings.map(formatQualityWarning).join(", ")
                  : speciesCropSummary
                    ? `Classifier input: ${speciesCropSummary}.`
                    : "Full best frame; no classifier crop metadata"}
          </small>
        </div>
        <div className="data-row">
          <span>Suggestion</span>
          <strong>{suggestedDisplayLabel}</strong>
          <small>
            {suggestedScientificName ? `${suggestedScientificName}. ` : ""}
            {identification.adapter_is_demo
              ? "Placeholder evidence; no species confidence. "
              : confidence != null
                ? `${formatConfidence(confidence)} ${scoreLabel}. `
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
      {rankedAlternatives.length > 0 ? (
        <div className="data-row">
          <span>Ranked alternatives</span>
          <strong>
            {rankedAlternatives.length} competing model candidate
            {rankedAlternatives.length === 1 ? "" : "s"}
          </strong>
          <div className="review-identification-actions">
            {rankedAlternatives.map((alternative) => (
              <button
                aria-label={`Prefill correction with rank ${alternative.rank}, ${alternative.commonName ?? alternative.label}`}
                className="secondary-action"
                disabled={isBusy}
                key={`${alternative.rank}:${alternative.correctionLabel}`}
                onClick={() => onFillLabel(alternative.correctionLabel)}
                title="Prefill only"
                type="button"
              >
                #{alternative.rank}{" "}
                {alternative.commonName ??
                  displayTaxonomyLabel(alternative.label, taxonomyLabels)}
                {alternative.scientificName
                  ? ` (${alternative.scientificName})`
                  : ""}
                {" · "}
                {alternative.confidence !== null
                  ? `${formatConfidence(alternative.confidence)} ${scoreLabel}`
                  : "score unavailable"}
              </button>
            ))}
          </div>
          <small>
            Choosing an alternative only prefills the correction field. Submit the
            correction separately to create reviewed truth.
          </small>
        </div>
      ) : null}
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
                : "Suggest species"}
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
              Prefill correction
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
    </details>
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
              : `Correction created explicitly for ${appliedLabel}.`}
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
    <details className="panel correction-audit-panel review-secondary-details">
      <summary>
        <span>Reviewed history</span>
        <strong>
          {groups.length} reviewed target{groups.length === 1 ? "" : "s"}
        </strong>
      </summary>
      <span className="meta-text">
        Latest correction truth stays available after items leave the active queue.
      </span>
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
    </details>
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
