import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type {
  ReviewCorrectionResult,
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
import { formatLabel } from "../utils";

type ReviewFilter = "all" | "bird_species" | "unknown_animals" | "false_positives";
type ReviewTargetFilter = "all" | "event" | "visit";
type ReviewStatusFilter = "unreviewed" | "reviewed" | "all";

interface LabelHelperGroup {
  title: string;
  labels: string[];
}

function reviewQueueTargetType(item: ReviewQueueItem): ReviewQueueBulkCorrectionTargetType {
  return item.visit_id ? "visit" : "event";
}

function reviewQueueTargetId(item: ReviewQueueItem): string {
  return item.visit_id ?? item.event_id ?? item.id.replace(/^review-queue-/, "");
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

  return [
    item.id,
    item.item_type,
    item.title,
    item.stream_id,
    item.event_id ?? "",
    item.visit_id ?? "",
    item.primary_zone_id ?? "",
    suggestedLabel,
    displayTaxonomyLabel(suggestedLabel || "unknown", taxonomyLabels),
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

interface ReviewQueuePageProps {
  items: ReviewQueueItem[];
  onCreateCorrection: (
    item: ReviewQueueItem,
    label: string,
    notes: string,
  ) => Promise<ReviewCorrectionResult>;
  onOpenEvent: (eventId: string) => void;
  onOpenExports: () => void;
  onOpenVisit: (visitId: string) => void;
}

export function ReviewQueuePage({
  items,
  onCreateCorrection,
  onOpenEvent,
  onOpenExports,
  onOpenVisit,
}: ReviewQueuePageProps) {
  const [queueItems, setQueueItems] = useState<ReviewQueueItem[]>(items);
  const [drafts, setDrafts] = useState<Record<string, { label: string; notes: string }>>({});
  const [bulkDraft, setBulkDraft] = useState({ label: "", notes: "" });
  const [bulkResult, setBulkResult] = useState<ReviewQueueBulkCorrectionResponse | null>(null);
  const [selectedTargetIds, setSelectedTargetIds] = useState<string[]>([]);
  const [taxonomyLabels, setTaxonomyLabels] = useState<TaxonomyLabel[]>([]);
  const [reviewLabels, setReviewLabels] = useState<ReviewLabel[]>([]);
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>("all");
  const [textSearch, setTextSearch] = useState("");
  const [targetTypeFilter, setTargetTypeFilter] = useState<ReviewTargetFilter>("all");
  const [reviewStatusFilter, setReviewStatusFilter] =
    useState<ReviewStatusFilter>("unreviewed");
  const [savingId, setSavingId] = useState<string | null>(null);
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

  const filteredItems = useMemo(
    () => {
      const normalizedSearch = textSearch.trim().toLowerCase();

      return queueItems.filter((item) => {
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
        if (
          normalizedSearch &&
          !reviewQueueSearchText(item, taxonomyLabels).includes(normalizedSearch)
        ) {
          return false;
        }

        return true;
      });
    },
    [queueItems, reviewFilter, reviewStatusFilter, targetTypeFilter, textSearch, taxonomyLabels],
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

  const recentLabelValues = useMemo(
    () => recentReviewLabelValues(reviewLabels),
    [reviewLabels],
  );

  const taxonomyLabelValues = useMemo(
    () => taxonomyHelperValues(taxonomyLabels),
    [taxonomyLabels],
  );

  const visibleSuggestedLabelValues = useMemo(
    () => uniqueLabelValues(filteredItems.map((item) => item.suggested_label)),
    [filteredItems],
  );

  const bulkSuggestedLabelValues = useMemo(
    () =>
      uniqueLabelValues([
        ...selectedItems.map((item) => item.suggested_label),
        ...visibleEligibleItems.map((item) => item.suggested_label),
      ]),
    [selectedItems, visibleEligibleItems],
  );

  const bulkLabelHelperGroups = useMemo(
    () => labelHelperGroups(bulkSuggestedLabelValues, recentLabelValues, taxonomyLabelValues),
    [bulkSuggestedLabelValues, recentLabelValues, taxonomyLabelValues],
  );

  useEffect(() => {
    setQueueItems(items);
  }, [items]);

  useEffect(() => {
    setSelectedTargetIds([]);
    setBulkResult(null);
  }, [reviewFilter, reviewStatusFilter, targetTypeFilter, textSearch]);

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

  async function saveCorrection(item: ReviewQueueItem) {
    const draft = drafts[item.id] ?? { label: item.suggested_label ?? "", notes: "" };
    if (!draft.label.trim()) {
      setMessage("Add a label before saving a correction.");
      return;
    }

    setSavingId(item.id);
    setMessage(null);
    try {
      const result = await onCreateCorrection(item, draft.label.trim(), draft.notes.trim());
      await refreshReviewLabels();
      setMessage(
        `Correction saved as local dataset truth. ${result.review_queue_count} item${
          result.review_queue_count === 1 ? "" : "s"
        } still need review.`,
      );
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Correction could not be saved.");
    } finally {
      setSavingId(null);
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
      {queueItems.length === 0 ? (
        <EmptyState
          title="No Visits need correction"
          description="The Review Queue contains Visits that need user correction. Promote MotionEvidence or import media to create reviewable Visits; corrections create analytics, export, and classifier truth."
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
              <h2>Species review work</h2>
              <span className="meta-text">
                Detection evidence is only a suggestion. Corrected species is local dataset truth.
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
                placeholder="label, id, stream, note"
                type="search"
                value={textSearch}
              />
            </label>
            <label>
              Target
              <select
                onChange={(event) =>
                  setTargetTypeFilter(event.target.value as ReviewTargetFilter)
                }
                value={targetTypeFilter}
              >
                <option value="all">All targets</option>
                <option value="visit">Visits</option>
                <option value="event">Events</option>
              </select>
            </label>
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
          </div>
          <div className="review-filter-summary">
            <span>{filteredItems.length} visible</span>
            <span>{visibleEligibleItems.length} visible eligible</span>
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
          const itemHelperGroups = labelHelperGroups(
            uniqueLabelValues([item.suggested_label, ...visibleSuggestedLabelValues]),
            recentLabelValues,
            taxonomyLabelValues,
          );
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
                {item.reason} Detection evidence is only a suggestion; your correction becomes local
                dataset truth.
              </p>
              <div className="queue-meta">
                <EvidenceBadge
                  label={fromDetectionEvidence ? "Converted proposal evidence" : "Review evidence"}
                />
                {isSpeciesReview ? <EvidenceBadge label="Resolve species" tone="review" /> : null}
                {isUnknownBirdLabel(item.suggested_label, taxonomyLabels) ? (
                  <EvidenceBadge label="Unknown bird" tone="review" />
                ) : null}
                <TaxonomyBadge label={suggestedTaxonomy} value={item.suggested_label} />
                <span>
                  Suggested: {displayTaxonomyLabel(item.suggested_label ?? "unknown", taxonomyLabels)}
                </span>
                <span>Event: {item.event_id ?? "n/a"}</span>
                <span>Visit: {item.visit_id ?? "n/a"}</span>
                {item.visit_id ? <span>Species suggestions: Visit detail</span> : null}
                {item.media_asset ? <span>Imported media attached</span> : null}
              </div>
              {item.media_asset ? (
                <div className="queue-media-block">
                  <MediaAssetPreview asset={item.media_asset} compact />
                </div>
              ) : null}
              <div className="correction-form">
                <TaxonomyLabelInput
                  label={isSpeciesReview ? "Species correction" : "Corrected label"}
                  labels={taxonomyLabels}
                  value={draft.label}
                  placeholder={
                    isSpeciesReview ? "reviewed species, unknown_bird, or false_positive" : "reviewed label"
                  }
                  onChange={(nextLabel) =>
                    setDrafts((current) => ({
                      ...current,
                      [item.id]: { ...draft, label: nextLabel },
                    }))
                  }
                />
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
                <button
                  className="primary-action"
                  disabled={savingId === item.id}
                  onClick={() => void saveCorrection(item)}
                >
                  {savingId === item.id ? "Saving..." : isSpeciesReview ? "Resolve species" : "Save correction"}
                </button>
              </div>
            </article>
          );
        })}
        {queueItems.length > 0 && filteredItems.length === 0 ? (
          <EmptyState
            title="No review items in this filter"
            description="Switch filters to resolve species, unknown animals, or false positives."
          />
        ) : null}
      </div>
    </div>
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
