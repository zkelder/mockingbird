import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type {
  ClassifierReadinessReport,
  ClassifierReadinessSpeciesSummary,
  ReviewLabel,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { EvidenceBadge } from "../components/EvidenceBadge";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel, userFacingErrorMessage } from "../utils";

interface ClassifierReadinessPageProps {
  onOpenAnalytics: () => void;
  onOpenClassifierManifest: () => void;
  onOpenExports: () => void;
  onOpenEvent: (eventId: string) => void;
  onOpenReview: () => void;
  onOpenReviewForLabel: (label: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenSpeciesSuggestions: () => void;
}

function compareReviewLabelsNewestFirst(first: ReviewLabel, second: ReviewLabel): number {
  const timeDelta =
    new Date(second.created_at).getTime() - new Date(first.created_at).getTime();
  return timeDelta !== 0 ? timeDelta : second.id.localeCompare(first.id);
}

export function ClassifierReadinessPage({
  onOpenAnalytics,
  onOpenClassifierManifest,
  onOpenExports,
  onOpenEvent,
  onOpenReview,
  onOpenReviewForLabel,
  onOpenVisit,
  onOpenSpeciesSuggestions,
}: ClassifierReadinessPageProps) {
  const [report, setReport] = useState<ClassifierReadinessReport | null>(null);
  const [reviewLabels, setReviewLabels] = useState<ReviewLabel[]>([]);
  const [selectedLabel, setSelectedLabel] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadReport() {
    setIsLoading(true);
    setError(null);
    try {
      const [nextReport, nextReviewLabels] = await Promise.all([
        apiClient.getClassifierReadiness(),
        apiClient.getReviewLabels(),
      ]);
      setReport(nextReport);
      setReviewLabels(nextReviewLabels);
      setSelectedLabel(
        (current) =>
          current ?? nextReport.species[0]?.label ?? nextReport.missing_target_labels[0] ?? null,
      );
    } catch (caught) {
      setError(userFacingErrorMessage(caught, "Could not load classifier readiness."));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadReport();
  }, []);

  const missingTargetPreview = useMemo(
    () => report?.missing_target_labels.slice(0, 24) ?? [],
    [report],
  );
  const missingTargetSet = useMemo(
    () => new Set(report?.missing_target_labels ?? []),
    [report],
  );
  const selectedSpeciesSummary = useMemo(
    () => report?.species.find((species) => species.label === selectedLabel) ?? null,
    [report, selectedLabel],
  );
  const selectedExamples = useMemo(
    () =>
      reviewLabels
        .filter((reviewLabel) => reviewLabel.label === selectedLabel)
        .sort(compareReviewLabelsNewestFirst),
    [reviewLabels, selectedLabel],
  );
  const selectedNeedsMoreExamples =
    selectedLabel !== null &&
    (missingTargetSet.has(selectedLabel) ||
      (selectedSpeciesSummary !== null && selectedSpeciesSummary.warnings.length > 0));

  if (isLoading) {
    return <div className="panel">Loading classifier readiness...</div>;
  }

  if (error) {
    return (
      <div className="error-panel">
        <strong>Could not load classifier readiness.</strong>
        <span>{error}</span>
        <button className="secondary-action" onClick={() => void loadReport()}>
          Retry
        </button>
      </div>
    );
  }

  if (!report) {
    return <div className="panel">Classifier readiness is unavailable.</div>;
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Advanced setup"
        title="Classifier Readiness"
        description="Developer-facing dataset readiness for future classifier work. It does not copy media, train models, or create reviewed truth."
        actions={
          <>
            <button className="secondary-action" onClick={onOpenClassifierManifest}>
              View manifest preview
            </button>
            <button className="secondary-action" onClick={onOpenReview}>
              Review Queue
            </button>
            <button className="secondary-action" onClick={onOpenAnalytics}>
              Analytics
            </button>
          </>
        }
      />

      <section className="notice-panel">
        <strong>Advanced setup — reviewed corrections are training truth</strong>
        <span>
          Evidence and suggestions are not enough. Training remains future work and secondary to
          the review loop.
        </span>
      </section>

      <section className="panel classifier-readiness-status">
        <div>
          <div className="quality-issue-title">
            <h2>Readiness status</h2>
            <StatusPill
              label={report.ready_for_manifest_export ? "Ready for manifest metadata export" : "Not ready"}
              tone={report.ready_for_manifest_export ? "good" : "review"}
            />
          </div>
          <p>{report.recommended_next_step}</p>
        </div>
        <div className="detail-actions">
          <button className="secondary-action" onClick={onOpenExports}>
            Dataset Exports
          </button>
          <button className="secondary-action" onClick={onOpenClassifierManifest}>
            View manifest preview
          </button>
          <button className="secondary-action" onClick={() => void loadReport()}>
            Refresh
          </button>
        </div>
      </section>

      <section className="metric-grid">
        <MetricCard
          label="Reviewed examples"
          value={report.reviewed_examples}
          detail="correction truth"
        />
        <MetricCard
          label="Media-backed"
          value={report.media_backed_reviewed_examples}
          detail="reviewed examples with media"
        />
        <MetricCard
          label="Export-ready"
          value={report.export_ready_examples}
          detail="known taxonomy species"
        />
        <MetricCard
          label="Missing targets"
          value={report.missing_target_labels.length}
          detail="target species without media-backed truth"
        />
      </section>

      <section className="metric-grid">
        <MetricCard
          label="Unknown labels"
          value={report.unknown_label_count}
          detail="not species truth"
        />
        <MetricCard
          label="False positives"
          value={report.false_positive_count}
          detail="excluded from species export"
        />
        <MetricCard
          label="Out of taxonomy"
          value={report.out_of_taxonomy_count}
          detail="needs label cleanup"
        />
        <MetricCard label="Skip reasons" value={report.skipped.length} detail="why records wait" />
      </section>

      <section className="panel classifier-readiness-panel">
        <div className="section-heading">
          <div>
            <h2>Species examples</h2>
            <span className="meta-text">Reviewed taxonomy species that have classifier-ready signal</span>
          </div>
          <EvidenceBadge label="Reviewed correction truth" tone="truth" />
        </div>
        {report.species.length > 0 ? (
          <div className="readiness-table" role="table" aria-label="Classifier species readiness">
            <div className="readiness-table-row readiness-table-head" role="row">
              <span role="columnheader">Label</span>
              <span role="columnheader">Reviewed</span>
              <span role="columnheader">Media-backed</span>
              <span role="columnheader">Export-ready</span>
              <span role="columnheader">Warnings</span>
            </div>
            {report.species.map((species) => (
              <div
                className={
                  selectedLabel === species.label
                    ? "readiness-table-row readiness-table-row-selected"
                    : "readiness-table-row"
                }
                key={species.label}
                role="row"
              >
                <div className="readiness-label-cell" role="cell">
                  <strong>{formatLabel(species.label)}</strong>
                  <button
                    className="text-action"
                    onClick={() => setSelectedLabel(species.label)}
                    type="button"
                  >
                    View examples
                  </button>
                  <button
                    className="text-action"
                    onClick={() => onOpenReviewForLabel(species.label)}
                    type="button"
                  >
                    Find review candidates
                  </button>
                </div>
                <span role="cell">{species.reviewed_examples}</span>
                <span role="cell">{species.media_backed_examples}</span>
                <span role="cell">{species.export_ready_examples}</span>
                <span className="readiness-warning-list" role="cell">
                  {species.warnings.length > 0
                    ? species.warnings.map((warning) => (
                        <EvidenceBadge label={formatLabel(warning)} tone="review" key={warning} />
                      ))
                    : "No warnings"}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No classifier-ready species yet"
            description="Review media-backed Visits before manifest export."
            action={
              <button className="secondary-action" onClick={onOpenReview}>
                Open Review Queue
              </button>
            }
          />
        )}
      </section>

      <section className="panel classifier-readiness-panel">
        <div className="section-heading">
          <div>
            <h2>Reviewed examples</h2>
            <span className="meta-text">
              {selectedLabel ? `${formatLabel(selectedLabel)} · ${selectedExamples.length} shown` : "Select a label"}
            </span>
          </div>
          <div className="detail-actions">
            {selectedLabel ? (
              <button
                className="secondary-action"
                onClick={() => onOpenReviewForLabel(selectedLabel)}
                type="button"
              >
                Find review candidates
              </button>
            ) : null}
            <EvidenceBadge label="ReviewLabel truth" tone="truth" />
          </div>
        </div>
        {selectedLabel ? (
          <>
            <ClassifierExampleSummary
              label={selectedLabel}
              summary={selectedSpeciesSummary}
              exampleCount={selectedExamples.length}
              needsMoreExamples={selectedNeedsMoreExamples}
              onOpenReviewForLabel={onOpenReviewForLabel}
            />
            {selectedExamples.length > 0 ? (
              <div className="classifier-example-list">
                {selectedExamples.map((reviewLabel) => (
                  <ReviewLabelExampleCard
                    key={reviewLabel.id}
                    reviewLabel={reviewLabel}
                    onOpenEvent={onOpenEvent}
                    onOpenVisit={onOpenVisit}
                  />
                ))}
              </div>
            ) : (
              <EmptyState
                title="No reviewed examples yet."
                description="No reviewed examples yet. Find items to correct."
                action={
                  <button
                    className="secondary-action"
                    onClick={() => onOpenReviewForLabel(selectedLabel)}
                    type="button"
                  >
                    Find review candidates
                  </button>
                }
              />
            )}
          </>
        ) : (
          <EmptyState
            title="Select a readiness label"
            description="Choose a species or missing target label to inspect reviewed correction examples."
          />
        )}
      </section>

      <section className="split-grid">
        <div className="panel classifier-readiness-panel">
          <div className="section-heading">
            <div>
              <h2>Missing target labels</h2>
              <span className="meta-text">{report.missing_target_labels.length} missing</span>
            </div>
          </div>
          {report.missing_target_labels.length > 0 ? (
            <>
              <div className="tag-row">
                {missingTargetPreview.map((label) => (
                  <button
                    className={selectedLabel === label ? "tag tag-button selected" : "tag tag-button"}
                    key={label}
                    onClick={() => setSelectedLabel(label)}
                    type="button"
                  >
                    {formatLabel(label)}
                  </button>
                ))}
              </div>
              {report.missing_target_labels.length > missingTargetPreview.length ? (
                <span className="meta-text">
                  {report.missing_target_labels.length - missingTargetPreview.length} more target
                  labels need reviewed media-backed examples.
                </span>
              ) : null}
              {selectedLabel && missingTargetSet.has(selectedLabel) ? (
                <div className="readiness-gap-callout">
                  <span>No reviewed examples yet. Find items to correct.</span>
                  <button
                    className="text-action"
                    onClick={() => onOpenReviewForLabel(selectedLabel)}
                    type="button"
                  >
                    Find review candidates
                  </button>
                </div>
              ) : null}
            </>
          ) : (
            <EmptyState
              title="All target labels have media-backed examples"
              description="The manifest page can still use readiness warnings before metadata export."
            />
          )}
        </div>

        <div className="panel classifier-readiness-panel">
          <div className="section-heading">
            <div>
              <h2>Skipped records</h2>
              <span className="meta-text">Reasons records are not classifier-ready</span>
            </div>
          </div>
          {report.skipped.length > 0 ? (
            <div className="readiness-summary-list">
              {report.skipped.map((item) => (
                <div className="summary-row" key={item.reason}>
                  <span>{formatLabel(item.reason)}</span>
                  <strong>{item.count}</strong>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No skipped records"
              description="Every reviewed candidate currently meets the readiness policy."
            />
          )}
        </div>
      </section>

      <section className="panel classifier-readiness-panel">
        <div className="section-heading">
          <div>
            <h2>Warnings</h2>
            <span className="meta-text">Use these before deciding on future manifest export</span>
          </div>
          <button className="secondary-action" onClick={onOpenSpeciesSuggestions}>
            Species Suggestions
          </button>
        </div>
        {report.warnings.length > 0 ? (
          <div className="readiness-warning-stack">
            {report.warnings.map((warning) => (
              <div className="notice-panel readiness-warning" key={warning}>
                <strong>{warning}</strong>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No report-level warnings"
            description="The readiness report has no current warnings. Metadata export still stays separate from training."
          />
        )}
      </section>
    </div>
  );
}

function ClassifierExampleSummary({
  label,
  summary,
  exampleCount,
  needsMoreExamples,
  onOpenReviewForLabel,
}: {
  label: string;
  summary: ClassifierReadinessSpeciesSummary | null;
  exampleCount: number;
  needsMoreExamples: boolean;
  onOpenReviewForLabel: (label: string) => void;
}) {
  return (
    <div className="classifier-example-summary">
      <div>
        <span>Selected label</span>
        <strong>{formatLabel(label)}</strong>
      </div>
      <div>
        <span>Reviewed</span>
        <strong>{summary?.reviewed_examples ?? exampleCount}</strong>
      </div>
      <div>
        <span>Media-backed</span>
        <strong>{summary?.media_backed_examples ?? 0}</strong>
      </div>
      <div>
        <span>Export-ready</span>
        <strong>{summary?.export_ready_examples ?? 0}</strong>
      </div>
      {needsMoreExamples ? (
        <div className="classifier-example-gap">
          <span>Gap</span>
          <strong>Needs more reviewed corrections.</strong>
          <button
            className="text-action"
            onClick={() => onOpenReviewForLabel(label)}
            type="button"
          >
            Find review candidates
          </button>
        </div>
      ) : null}
    </div>
  );
}

function ReviewLabelExampleCard({
  reviewLabel,
  onOpenEvent,
  onOpenVisit,
}: {
  reviewLabel: ReviewLabel;
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
}) {
  const isVisit = reviewLabel.target_type === "visit";
  const isEvent = reviewLabel.target_type === "event";

  return (
    <article className="classifier-example-card">
      <div className="section-heading">
        <div>
          <span className="meta-text">{formatLabel(reviewLabel.target_type)} correction</span>
          <h3>{formatLabel(reviewLabel.label)}</h3>
        </div>
        <EvidenceBadge label="ReviewLabel truth" tone="truth" />
      </div>
      <div className="classifier-example-meta">
        <span>ID: {reviewLabel.id}</span>
        <span>Target: {reviewLabel.target_id}</span>
        <span>Created: {formatDateTime(reviewLabel.created_at)}</span>
      </div>
      {reviewLabel.notes ? <p>{reviewLabel.notes}</p> : <p>No correction notes.</p>}
      <div className="detail-actions">
        {isEvent ? (
          <button
            className="secondary-action"
            onClick={() => onOpenEvent(reviewLabel.target_id)}
            type="button"
          >
            Open Event
          </button>
        ) : null}
        {isVisit ? (
          <button
            className="secondary-action"
            onClick={() => onOpenVisit(reviewLabel.target_id)}
            type="button"
          >
            Open Visit
          </button>
        ) : null}
      </div>
    </article>
  );
}
