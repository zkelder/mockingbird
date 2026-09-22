import type { DatasetCoverageSummary } from "../api/types";
import { formatLabel } from "../utils";
import { EmptyState } from "./EmptyState";
import { EvidenceBadge } from "./EvidenceBadge";

interface DatasetCoveragePanelProps {
  coverage: DatasetCoverageSummary | null;
  onOpenExports?: () => void;
  onOpenReview: () => void;
  variant?: "full" | "compact";
}

function gapReasonLabel(reason: string): string {
  if (reason === "missing_reviewed_examples") {
    return "Missing target species";
  }
  if (reason === "unknown_birds_need_review") {
    return "Unknown birds needing review";
  }
  if (reason === "unknown_animals_need_review") {
    return "Unknown animals needing review";
  }
  return formatLabel(reason);
}

export function DatasetCoveragePanel({
  coverage,
  onOpenExports,
  onOpenReview,
  variant = "full",
}: DatasetCoveragePanelProps) {
  if (!coverage) {
    return (
      <section className="panel dataset-coverage-panel">
        <div className="section-heading">
          <h2>Dataset Coverage</h2>
        </div>
        <span className="meta-text">Dataset coverage is unavailable.</span>
      </section>
    );
  }

  const isCompact = variant === "compact";
  const reviewedSpecies = coverage.species.filter(
    (species) => species.is_species && species.reviewed_record_count > 0,
  );
  const missingTargetSpecies = coverage.gaps.filter(
    (gap) => gap.reason === "missing_reviewed_examples",
  );
  const nextReviewGaps = coverage.gaps.filter((gap) => gap.reason !== "missing_reviewed_examples");

  return (
    <section className={`panel dataset-coverage-panel ${isCompact ? "compact" : ""}`}>
      <div className="section-heading">
        <div>
          <h2>Dataset Coverage</h2>
          <span className="meta-text">
            Corrected labels are local dataset truth. Detection and proposal labels are evidence only.
          </span>
        </div>
        <EvidenceBadge label="Coverage for future model work" tone="review" />
      </div>

      <div className="coverage-metric-grid">
        <div>
          <span className="meta-text">Export-ready reviewed records</span>
          <strong>{coverage.export_ready_count}</strong>
        </div>
        <div>
          <span className="meta-text">Reviewed species coverage</span>
          <strong>
            {coverage.covered_target_species_count}/{coverage.target_species_count}
          </strong>
        </div>
        <div>
          <span className="meta-text">Unknown birds needing review</span>
          <strong>{coverage.unknown_bird_count}</strong>
        </div>
        {/* Broader Wildlife Maturity v1: the panel already received this
            field and already distinguishes the two reasons in its gap list
            (gapReasonLabel above) — it just never surfaced this sibling
            metric, unlike AnalyticsPage's matching "Unknown animals" card.
            See docs/broader-wildlife-maturity-v1-contract.md. */}
        <div>
          <span className="meta-text">Unknown animals needing review</span>
          <strong>{coverage.unknown_animal_count}</strong>
        </div>
        <div>
          <span className="meta-text">Missing target species</span>
          <strong>{coverage.missing_target_species_count}</strong>
        </div>
      </div>

      {!isCompact ? (
        <div className="coverage-columns">
          <div>
            <div className="section-heading">
              <h3>Reviewed species labels</h3>
              <span className="meta-text">{coverage.reviewed_species_count} reviewed species records</span>
            </div>
            <div className="coverage-list">
              {reviewedSpecies.length > 0 ? (
                reviewedSpecies.map((species) => (
                  <div className="summary-row" key={species.label}>
                    <span>
                      {species.display_name}
                      {species.media_asset_count > 0 ? (
                        <EvidenceBadge label={`${species.media_asset_count} local media`} tone="quiet" />
                      ) : null}
                    </span>
                    <strong>{species.reviewed_record_count}</strong>
                  </div>
                ))
              ) : (
                <EmptyState
                  title="No reviewed species yet"
                  description="Resolve visits to start reviewed species coverage."
                  action={
                    <button className="secondary-action" onClick={onOpenReview}>
                      Resolve species
                    </button>
                  }
                />
              )}
            </div>
          </div>

          <div>
            <div className="section-heading">
              <h3>Gaps to review next</h3>
              <span className="meta-text">Training-readiness signal, not model training</span>
            </div>
            <div className="coverage-list">
              {[...nextReviewGaps, ...missingTargetSpecies.slice(0, 8)].map((gap) => (
                <div className="summary-row" key={`${gap.reason}-${gap.label}`}>
                  <span>{gap.display_name}</span>
                  <strong>{gapReasonLabel(gap.reason)}</strong>
                </div>
              ))}
              {coverage.gaps.length === 0 ? (
                <span className="meta-text">No dataset coverage gaps are visible right now.</span>
              ) : null}
            </div>
          </div>
        </div>
      ) : (
        <span className="meta-text">
          {coverage.needs_review_count} record{coverage.needs_review_count === 1 ? "" : "s"} still need
          review before export coverage is complete.
        </span>
      )}

      <div className="detail-actions">
        {coverage.needs_review_count > 0 ? (
          <button className="secondary-action" onClick={onOpenReview}>
            Review unknowns and gaps
          </button>
        ) : null}
        {onOpenExports ? (
          <button className="secondary-action" onClick={onOpenExports}>
            Open Dataset Exports
          </button>
        ) : null}
      </div>
    </section>
  );
}
