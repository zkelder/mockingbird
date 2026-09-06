import type { PlaceStoryEntry, PlaceStoryEventGroup, PlaceStoryEventKind } from "../api/types";
import { StatusPill } from "./StatusPill";
import { formatDate } from "../utils";

/**
 * Place Story Deep Dives & Representative Evidence v1 -- extracted from
 * PlaceStoryPage.tsx's own private `PlaceStoryCard` (Place Story &
 * Seasonal Timeline v1) so the Place-wide Story, Taxon Story, and Feature
 * Story pages all render one identical event card, rather than each
 * inventing its own "how do I phrase a Place Story entry" presentation
 * (see docs/place-story-deep-dives-representative-evidence-v1-report.md
 * "Shared Story composition contract"). This is the smallest shared
 * composition boundary the governing brief permits -- no second timeline
 * engine, only one shared rendering of the one existing engine's output.
 *
 * Every `title`/`summary` string already carries the full plain-language
 * copy the backend composed; this component never re-derives truth or
 * ranking, only renders what it is given.
 */

export const KIND_LABEL: Record<PlaceStoryEventKind, string> = {
  first_seen: "First observation",
  return: "Returned",
  regularity_change: "Regularity change",
  noteworthy_activity: "Notable activity",
  diversity_milestone: "Biodiversity milestone",
  feature_change: "Place change",
  phenology: "Phenology",
  comparison_insight: "Before/after insight",
  year_over_year: "Compared with last year",
  period_summary: "Recap",
};

export const GROUP_TONE: Record<PlaceStoryEventGroup, "good" | "review" | "alert" | "quiet"> = {
  wildlife: "good",
  place: "review",
  context: "quiet",
  summary: "quiet",
};

interface PlaceStoryEntryCardProps {
  entry: PlaceStoryEntry;
  onOpenVisit: (visitId: string) => void;
  // Omitted on a page that already *is* that taxon's/Feature's own Story --
  // linking to yourself from your own timeline would be a dead-end loop.
  onOpenTaxonStory?: (label: string) => void;
  onOpenFeatureStory?: (featureId: string) => void;
  onOpenBirdLog?: (label?: string) => void;
  onOpenPlaceActivityReport?: () => void;
}

export function PlaceStoryEntryCard({
  entry,
  onOpenVisit,
  onOpenTaxonStory,
  onOpenFeatureStory,
  onOpenBirdLog,
  onOpenPlaceActivityReport,
}: PlaceStoryEntryCardProps) {
  return (
    <li className="place-story-card">
      <div className="place-story-card-heading">
        <StatusPill label={KIND_LABEL[entry.kind]} tone={GROUP_TONE[entry.group]} />
        <span className="place-story-card-date">
          {formatDate(entry.event_date)}
          {entry.event_end_date && entry.event_end_date !== entry.event_date
            ? ` – ${formatDate(entry.event_end_date)}`
            : ""}
        </span>
        {entry.information_class === "inferred" ? (
          <span className="place-story-card-basis" title="An inferred insight, not a directly reviewed fact">
            Inferred
          </span>
        ) : null}
      </div>
      <h3>{entry.title}</h3>
      <p>{entry.summary}</p>
      <div className="place-story-card-actions">
        {entry.visit_id ? (
          <button className="text-action" onClick={() => onOpenVisit(entry.visit_id!)} type="button">
            View evidence
          </button>
        ) : null}
        {entry.taxon_label && onOpenTaxonStory ? (
          <button className="text-action" onClick={() => onOpenTaxonStory(entry.taxon_label!)} type="button">
            {entry.taxon_display_name ?? "View"}&rsquo;s story
          </button>
        ) : null}
        {entry.taxon_label && onOpenBirdLog ? (
          <button className="text-action" onClick={() => onOpenBirdLog(entry.taxon_label!)} type="button">
            {entry.taxon_display_name ?? "View"} in Bird Log
          </button>
        ) : null}
        {entry.feature_id && onOpenFeatureStory ? (
          <button className="text-action" onClick={() => onOpenFeatureStory(entry.feature_id!)} type="button">
            {entry.feature_name ?? "View"} story
          </button>
        ) : (entry.feature_id || entry.kind === "phenology") && onOpenPlaceActivityReport ? (
          <button className="text-action" onClick={onOpenPlaceActivityReport} type="button">
            View in Place Report
          </button>
        ) : null}
      </div>
    </li>
  );
}
