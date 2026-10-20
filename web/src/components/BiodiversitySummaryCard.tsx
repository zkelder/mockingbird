import type { PlaceBiodiversitySummaryResponse, PlaceBiodiversityTaxonEntry } from "../api/types";

interface BiodiversitySummaryCardProps {
  summary: PlaceBiodiversitySummaryResponse | null;
  onOpenBirdLog?: () => void;
  // Everyday Wildlife Experience & Presentation Refinement v1: Today already
  // says "nothing observed yet" once (the report panel) and points at Review
  // for awaiting items; a second empty "Biodiversity here" card repeating it
  // is noise. Today opts in; other surfaces keep the explicit empty state.
  hideWhenNothingConfirmed?: boolean;
}

const MAX_NAMES_SHOWN = 6;

function namesLine(entries: PlaceBiodiversityTaxonEntry[]): string {
  const names = entries.map((entry) => entry.display_name);
  if (names.length <= MAX_NAMES_SHOWN) {
    return names.join(" · ");
  }
  const shown = names.slice(0, MAX_NAMES_SHOWN);
  return `${shown.join(" · ")} · +${names.length - MAX_NAMES_SHOWN} more`;
}

/**
 * Biodiversity & Place Intelligence v1 (see docs/biodiversity-place-
 * intelligence-v1-contract.md "Place Biodiversity Summary"). A calm,
 * read-only Place-wide roster: how many taxa are authoritatively known
 * here, and which are new/regular/recently observed -- reusing the exact
 * same `historical_status` values Today and Bird Log already show, so
 * this card can never disagree with them (see docs/canonical-new-regular-
 * species-contract.md). A sibling of `EnvironmentalContextCard`/
 * `HabitatPhenologyCard`, not nested inside either: a genuinely separate
 * fetch that must keep working, or stay quietly absent, regardless of
 * whether those (or the report) loaded.
 *
 * Renders nothing while the fetch is still in flight or failed
 * (`summary === null`) -- same absence-safety discipline as its two
 * sibling cards. `provisional_taxa` is shown only as a separate, clearly
 * distinct "awaiting review" count -- never blended into the confirmed
 * species count above it (see the contract doc's truth-boundary
 * discussion). Absence from "Recently observed" is never phrased as
 * "gone"/"absent" -- see product-doctrine.md and the milestone's own
 * "not observed recently must never mean absent" instruction.
 */
export function BiodiversitySummaryCard({ summary, onOpenBirdLog, hideWhenNothingConfirmed = false }: BiodiversitySummaryCardProps) {
  if (!summary) {
    return null;
  }

  const hasAnyConfirmed = summary.taxa.length > 0;
  const hasProvisional = summary.provisional_taxa.length > 0;
  if (hideWhenNothingConfirmed && !hasAnyConfirmed && !hasProvisional) {
    return null;
  }
  // Broader Wildlife Maturity v1: mirrors TodayReportPanel's own species/
  // kinds-of-wildlife fallback (see docs/broader-wildlife-maturity-v1-
  // contract.md). distinct_species_count only counts species-level truth
  // (bird-only today in practice -- see the contract's identification
  // section), so a Place with only confirmed kind-level wildlife (a
  // reviewed squirrel, deer, ...) previously headlined "0" here while
  // naming them by name in "Regular visitors"/"New here" just below --
  // a visible, self-contradicting undercount on the same card.
  const usingTaxaFallback =
    summary.distinct_species_count === 0 && summary.historical_baseline.distinct_taxa_count > 0;
  const speciesHeadlineCount = usingTaxaFallback
    ? summary.historical_baseline.distinct_taxa_count
    : summary.distinct_species_count;
  const speciesHeadlineLabel = usingTaxaFallback ? "Kinds of wildlife known here" : "Species known here";

  return (
    <section aria-label="Biodiversity at this Place" className="panel biodiversity-summary-card">
      <div className="section-heading">
        <h3>Biodiversity here</h3>
        {onOpenBirdLog ? (
          <button className="text-action" onClick={onOpenBirdLog} type="button">
            View in Bird Log
          </button>
        ) : null}
      </div>

      {summary.warnings.length > 0 ? <p className="meta-text">{summary.warnings[0]}</p> : null}

      {!hasAnyConfirmed && !hasProvisional ? (
        <p className="meta-text">Nothing recorded yet.</p>
      ) : (
        <>
          <div className="today-report-facts">
            <div className="today-report-fact">
              <span>{speciesHeadlineLabel}</span>
              <strong>{speciesHeadlineCount}</strong>
            </div>
            {hasProvisional ? (
              <div className="today-report-fact">
                <span>Awaiting review</span>
                <strong>{summary.provisional_taxa.length}</strong>
              </div>
            ) : null}
          </div>

          {summary.new_taxa.length > 0 ? (
            <p className="meta-text">
              <strong>New here: </strong>
              {namesLine(summary.new_taxa)}
            </p>
          ) : null}

          {summary.regular_taxa.length > 0 ? (
            <p className="meta-text">
              <strong>Regular visitors: </strong>
              {namesLine(summary.regular_taxa)}
            </p>
          ) : null}

          {summary.recently_observed_taxa.length > 0 ? (
            <p className="meta-text">
              <strong>Recently observed: </strong>
              {namesLine(summary.recently_observed_taxa)}
            </p>
          ) : hasAnyConfirmed ? (
            <p className="meta-text">
              Nothing recorded in the last two weeks — {summary.taxa.length} known here overall.
            </p>
          ) : null}
        </>
      )}
    </section>
  );
}
