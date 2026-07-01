import type { AnalyticsSummary, TaxonomyLabel } from "../api/types";
import { formatLabel } from "../utils";
import { EvidenceBadge } from "./EvidenceBadge";
import { birdSpeciesLabels } from "./taxonomy";

interface SpeciesCoverageCardProps {
  analytics: AnalyticsSummary;
  taxonomyLabels?: TaxonomyLabel[];
  onOpenReview?: () => void;
}

export function SpeciesCoverageCard({
  analytics,
  taxonomyLabels = [],
  onOpenReview,
}: SpeciesCoverageCardProps) {
  const targets = birdSpeciesLabels(taxonomyLabels);
  const coveredTargets = targets.filter((label) => (analytics.species_counts[label.label] ?? 0) > 0);
  const reviewedSpeciesTotal = Object.entries(analytics.species_counts).reduce(
    (total, [label, count]) => (analytics.species_label_ids.includes(label) ? total + count : total),
    0,
  );

  return (
    <section className="panel species-coverage-card">
      <div className="section-heading">
        <div>
          <h2>Species coverage</h2>
          <span className="meta-text">Reviewed bird species ready for dataset export</span>
        </div>
        <EvidenceBadge label={`${reviewedSpeciesTotal} reviewed species`} tone="truth" />
      </div>
      <div className="species-coverage-summary">
        <strong>
          {coveredTargets.length}/{targets.length || analytics.species_label_ids.length}
        </strong>
        <span>bird species targets have reviewed local truth.</span>
      </div>
      <div className="species-coverage-list">
        {(targets.length > 0 ? targets : analytics.species_label_ids.map((label) => ({ label, display_name: formatLabel(label) }))).map(
          (label) => {
            const count = analytics.species_counts[label.label] ?? 0;
            return (
              <div className="summary-row" key={label.label}>
                <span>{label.display_name}</span>
                <strong>{count > 0 ? `${count} reviewed` : "Needs review"}</strong>
              </div>
            );
          },
        )}
      </div>
      {analytics.needs_review_count > 0 && onOpenReview ? (
        <button className="secondary-action" onClick={onOpenReview}>
          Resolve species
        </button>
      ) : null}
    </section>
  );
}
