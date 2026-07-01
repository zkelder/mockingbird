import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type { ReviewCorrectionResult, ReviewQueueItem, TaxonomyLabel } from "../api/types";
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
} from "../components/taxonomy";
import { formatLabel } from "../utils";

type ReviewFilter = "all" | "bird_species" | "unknown_animals" | "false_positives";

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
  const [drafts, setDrafts] = useState<Record<string, { label: string; notes: string }>>({});
  const [taxonomyLabels, setTaxonomyLabels] = useState<TaxonomyLabel[]>([]);
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>("all");
  const [savingId, setSavingId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const queueCounts = useMemo(
    () =>
      items.reduce<Record<ReviewFilter, number>>(
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
    [items, taxonomyLabels],
  );

  const reviewFilters: ReviewFilterOption<ReviewFilter>[] = [
    { value: "all", label: "All", count: queueCounts.all },
    { value: "bird_species", label: "Bird/species", count: queueCounts.bird_species },
    { value: "unknown_animals", label: "Unknown animals", count: queueCounts.unknown_animals },
    { value: "false_positives", label: "False positives", count: queueCounts.false_positives },
  ];

  const filteredItems = useMemo(
    () =>
      items.filter((item) => {
        if (reviewFilter === "all") {
          return true;
        }
        if (reviewFilter === "bird_species") {
          return isBirdReviewLabel(item.suggested_label, taxonomyLabels);
        }
        if (reviewFilter === "unknown_animals") {
          return isUnknownAnimalLabel(item.suggested_label, taxonomyLabels);
        }
        return isFalsePositiveLabel(item.suggested_label, taxonomyLabels);
      }),
    [items, reviewFilter, taxonomyLabels],
  );

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
      {items.length === 0 ? (
        <EmptyState
          title="All demo visits and events are reviewed."
          description="Corrections are available as local dataset-grade labels for exports and analytics."
          action={
            <button className="primary-action" onClick={onOpenExports}>
              Generate dataset export
            </button>
          }
        />
      ) : null}
      {items.length > 0 ? (
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
        {items.length > 0 && filteredItems.length === 0 ? (
          <EmptyState
            title="No review items in this filter"
            description="Switch filters to resolve species, unknown animals, or false positives."
          />
        ) : null}
      </div>
    </div>
  );
}
