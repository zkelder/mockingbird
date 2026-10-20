import type { ReactNode } from "react";
import type { PlaceYearOverYearResponse, PlaceYearOverYearSpeciesEntry } from "../api/types";
import { StatusPill } from "./StatusPill";
import { formatMonthYear } from "../utils";

interface YearOverYearCardProps {
  comparison: PlaceYearOverYearResponse | null;
  onOpenBirdLog?: (label?: string) => void;
  // Place Story Deep Dives & Representative Evidence v1: an additive deep
  // link to that species' own Taxon Story -- kept alongside, not instead
  // of, the existing Bird Log link (Bird Log remains the detailed
  // occurrence log; Taxon Story is the calmer longitudinal view this
  // year-over-year fact itself is drawn from).
  onOpenTaxonStory?: (label: string) => void;
  // Everyday Wildlife Experience & Presentation Refinement v1: on Today, the
  // "long-term patterns will appear once there is a year of history"
  // placeholder is just another empty state; Today opts out of showing it
  // (the Place report keeps it). Real comparisons and the other honest
  // abstentions (partial month, thin coverage) still appear.
  hideWhenNoYearOfHistory?: boolean;
}

/**
 * Year-over-Year Seasonality & Long-Term Place Memory v1 -- see
 * docs/year-over-year-seasonality-long-term-place-memory-v1-report.md. A
 * calm "compared with this time last year" summary: overall Place activity
 * plus a small, backend-ranked set of notable species-level changes, never
 * every species (`GET /api/place/year-over-year`). A sibling of
 * `BiodiversitySummaryCard`/`PlaceFeaturesCard`, not nested inside either --
 * a genuinely separate, period-independent fetch that must keep working, or
 * stay quietly absent, regardless of whether those (or the report) loaded.
 *
 * Renders nothing while the fetch is still in flight or failed
 * (`comparison === null`) -- same absence-safety discipline as its sibling
 * cards. Every abstention status renders a calm, honest sentence, never an
 * error banner or an empty chart -- MockingBird should frequently and
 * comfortably say "not enough comparable history yet." No red/green value
 * judgment and no bare trend arrow for wildlife increase/decrease -- every
 * direction is paired with plain-language text, and `StatusPill` always
 * uses the same non-judgmental "quiet" tone for both "higher" and "lower".
 */
export function YearOverYearCard({
  comparison,
  onOpenBirdLog,
  onOpenTaxonStory,
  hideWhenNoYearOfHistory = false,
}: YearOverYearCardProps) {
  if (!comparison) {
    return null;
  }
  if (hideWhenNoYearOfHistory && comparison.place.status === "insufficient_prior_history") {
    return null;
  }

  const { place, notable_species_changes: notableSpeciesChanges } = comparison;
  const currentLabel = formatMonthYear(place.current_period.start_date);
  const priorLabel = formatMonthYear(place.prior_period.start_date);
  const showSpeciesChanges =
    (place.status === "comparable" || place.status === "no_material_difference") &&
    notableSpeciesChanges.length > 0;

  return (
    <section aria-label="Compared with last year" className="panel year-over-year-card">
      <div className="section-heading">
        <h3>Compared with last year</h3>
      </div>
      <p className="meta-text">
        {currentLabel} vs. {priorLabel}
      </p>

      {placeSummary(place, currentLabel, priorLabel)}

      {showSpeciesChanges ? (
        <ul className="habitat-phenology-list">
          {notableSpeciesChanges.map((entry) => (
            <li key={entry.label}>
              <button
                className="text-action"
                disabled={!onOpenTaxonStory}
                onClick={() => onOpenTaxonStory?.(entry.label)}
                type="button"
              >
                {entry.display_name}
              </button>
              <span className="meta-text">{speciesChangeSentence(entry)}</span>
              {onOpenBirdLog ? (
                <button className="text-action" onClick={() => onOpenBirdLog(entry.label)} type="button">
                  Bird Log
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function placeSummary(
  place: PlaceYearOverYearResponse["place"],
  currentLabel: string,
  priorLabel: string,
): ReactNode {
  switch (place.status) {
    case "comparable":
      return (
        <p>
          <StatusPill
            label={place.overall_activity === "higher" ? "More activity recorded" : "Less activity recorded"}
            tone="quiet"
          />{" "}
          Confirmed wildlife activity at this Place was {place.overall_activity} in {currentLabel} than in{" "}
          {priorLabel}, under comparable monitoring.
        </p>
      );
    case "no_material_difference":
      return <p className="meta-text">Activity is similar to {priorLabel}, under comparable monitoring.</p>;
    case "partial_period":
      return (
        <p className="meta-text">
          {currentLabel} is still in progress — check back once it's complete for a full comparison with{" "}
          {priorLabel}.
        </p>
      );
    case "insufficient_current_coverage":
      return <p className="meta-text">Not enough monitoring this period yet to compare with {priorLabel}.</p>;
    case "insufficient_prior_coverage":
      return (
        <p className="meta-text">
          Not enough monitoring around {priorLabel} to compare confidently with this period.
        </p>
      );
    case "insufficient_prior_history":
    default:
      return (
        <p className="meta-text">
          Long-term patterns will appear here once MockingBird has a full comparable year of history.
        </p>
      );
  }
}

/** Plain-language, association-only wording composed from raw status
 * fields (never a backend-provided sentence -- mirrors PlaceActivityReportPage's
 * `featureAssociationSentence`'s identical frontend-composition convention
 * for this surface). Never "arrived" -- detection is not proof of arrival.
 * Exported (Place Story Deep Dives & Representative Evidence v1) so a Taxon
 * Story header composes the identical sentence for its own single taxon's
 * comparison, rather than a second, potentially-drifting wording. */
export function speciesChangeSentence(entry: PlaceYearOverYearSpeciesEntry): string {
  const parts: string[] = [];
  if (entry.status === "comparable" && entry.activity_direction) {
    parts.push(`observed ${entry.activity_direction} often this period`);
  }
  if (entry.first_observed_is_material && entry.first_observed_day_difference != null) {
    const days = Math.abs(entry.first_observed_day_difference);
    const word = entry.first_observed_day_difference < 0 ? "earlier" : "later";
    parts.push(`first observed here about ${days} day${days === 1 ? "" : "s"} ${word} than last year`);
  }
  return parts.join(" · ");
}
