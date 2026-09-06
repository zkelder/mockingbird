import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type { PlaceStoryEntry, PlaceStoryEventGroup, PlaceStoryEventKind } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatDate, formatMonthYear } from "../utils";

/**
 * Place Story & Seasonal Timeline v1 -- see docs/place-story-seasonal-
 * timeline-v1-report.md. A calm, longitudinal "what happened here, and
 * why does MockingBird think it mattered" surface, deliberately distinct
 * from Bird Log (granular per-observation wildlife history): this page
 * reads `GET /api/place/story`, a derived read-model composed entirely
 * from already-authoritative facts, and never re-derives truth or ranking
 * itself -- every `title`/`summary` string already carries the full
 * plain-language copy the backend composed; this component only groups,
 * filters, and paginates what it is given (mirrors PlaceActivityReportPage's
 * identical "present, never re-derive" discipline).
 */

type PeriodPreset = "recent" | "this_month" | "this_year" | "all_history";
type CategoryFilter = "all" | PlaceStoryEventGroup;

interface PlaceStoryPageProps {
  onOpenVisit: (visitId: string) => void;
  onOpenBirdLog: (label?: string) => void;
  onOpenPlaceActivityReport: () => void;
  // Calm Attention & Notifications v1: an attention item's deep link opens
  // Place Story already scoped to the category group its own underlying
  // event belongs to (see `App.tsx`'s `openAlertAction`) -- more precise
  // than always landing on the unfiltered page, without needing a new
  // taxon/feature filter control this page does not otherwise have.
  // `undefined` (every pre-existing caller) keeps today's default ("all").
  initialCategory?: CategoryFilter;
}

const PERIOD_OPTIONS: Array<{ value: PeriodPreset; label: string }> = [
  { value: "recent", label: "Recent (last 90 days)" },
  { value: "this_month", label: "This month" },
  { value: "this_year", label: "This year" },
  { value: "all_history", label: "All history" },
];

const CATEGORY_OPTIONS: Array<{ value: CategoryFilter; label: string }> = [
  { value: "all", label: "All" },
  { value: "wildlife", label: "Wildlife" },
  { value: "place", label: "Place changes" },
  { value: "context", label: "Insights" },
];

const KINDS_BY_GROUP: Record<PlaceStoryEventGroup, PlaceStoryEventKind[]> = {
  wildlife: ["first_seen", "return", "regularity_change", "noteworthy_activity", "diversity_milestone"],
  place: ["feature_change", "phenology"],
  context: ["comparison_insight", "year_over_year"],
  summary: ["period_summary"],
};

const GROUP_TONE: Record<PlaceStoryEventGroup, "good" | "review" | "alert" | "quiet"> = {
  wildlife: "good",
  place: "review",
  context: "quiet",
  summary: "quiet",
};

const KIND_LABEL: Record<PlaceStoryEventKind, string> = {
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

function periodRange(preset: PeriodPreset): { start_at?: string; end_at?: string } {
  const now = new Date();
  const endAt = now.toISOString();
  if (preset === "recent") {
    const start = new Date(now);
    start.setUTCDate(start.getUTCDate() - 90);
    return { start_at: start.toISOString(), end_at: endAt };
  }
  if (preset === "this_month") {
    const start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1));
    return { start_at: start.toISOString(), end_at: endAt };
  }
  if (preset === "this_year") {
    const start = new Date(Date.UTC(now.getUTCFullYear(), 0, 1));
    return { start_at: start.toISOString(), end_at: endAt };
  }
  return { end_at: endAt }; // "all_history": let the backend apply its own bounded default
}

const PAGE_SIZE = 20;

export function PlaceStoryPage({
  onOpenVisit,
  onOpenBirdLog,
  onOpenPlaceActivityReport,
  initialCategory,
}: PlaceStoryPageProps) {
  const [period, setPeriod] = useState<PeriodPreset>("recent");
  const [category, setCategory] = useState<CategoryFilter>(initialCategory ?? "all");
  const [entries, setEntries] = useState<PlaceStoryEntry[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [totalMatched, setTotalMatched] = useState(0);
  const [isEarlyExperience, setIsEarlyExperience] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const range = useMemo(() => periodRange(period), [period]);
  const kinds = category === "all" ? undefined : KINDS_BY_GROUP[category];

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    apiClient
      .getPlaceStory({ ...range, kind: kinds, page_size: PAGE_SIZE, offset: 0 })
      .then((response) => {
        if (!active) return;
        setEntries(response.entries);
        setHasMore(response.has_more);
        setNextOffset(response.next_offset ?? null);
        setTotalMatched(response.total_matched);
        setIsEarlyExperience(response.is_early_experience);
      })
      .catch(() => {
        if (active) setError("Could not load the Place Story right now.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period, category]);

  function loadMore() {
    if (nextOffset == null) return;
    setLoadingMore(true);
    apiClient
      .getPlaceStory({ ...range, kind: kinds, page_size: PAGE_SIZE, offset: nextOffset })
      .then((response) => {
        setEntries((prior) => [...prior, ...response.entries]);
        setHasMore(response.has_more);
        setNextOffset(response.next_offset ?? null);
      })
      .catch(() => setError("Could not load more of the Place Story."))
      .finally(() => setLoadingMore(false));
  }

  const groupedByMonth = useMemo(() => {
    const groups: Array<{ heading: string; items: PlaceStoryEntry[] }> = [];
    for (const entry of entries) {
      const heading = formatMonthYear(entry.event_date);
      const last = groups[groups.length - 1];
      if (last && last.heading === heading) {
        last.items.push(entry);
      } else {
        groups.push({ heading, items: [entry] });
      }
    }
    return groups;
  }, [entries]);

  return (
    <div className="page place-story-page">
      <PageHeader
        eyebrow="Remember"
        title="Place Story"
        description="A living history of this Place -- firsts, meaningful changes, and noteworthy moments, gathered from your reviewed wildlife history and recorded Place changes."
      />

      <section className="panel journal-filter-panel" aria-label="Filter the Place Story">
        <label>
          Period
          <select onChange={(event) => setPeriod(event.target.value as PeriodPreset)} value={period}>
            {PERIOD_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Category
          <select onChange={(event) => setCategory(event.target.value as CategoryFilter)} value={category}>
            {CATEGORY_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </section>

      {loading ? (
        <p role="status">Loading the Place Story…</p>
      ) : error ? (
        <EmptyState title="Something went wrong" description={error} />
      ) : entries.length === 0 && isEarlyExperience ? (
        <EmptyState
          title="Your Place Story is just beginning"
          description="As MockingBird observes more wildlife and you record changes around the yard -- a new feeder, a planting, a phenology note -- this timeline will grow."
          action={
            <button className="secondary-action" onClick={onOpenPlaceActivityReport} type="button">
              See the full Place Report
            </button>
          }
        />
      ) : entries.length === 0 ? (
        <EmptyState
          title="Nothing here yet for this period"
          description="Try a longer period or a different category."
        />
      ) : (
        <>
          <p className="place-story-count">
            {totalMatched} {totalMatched === 1 ? "moment" : "moments"} in this period
          </p>
          {groupedByMonth.map((group) => (
            <section aria-label={group.heading} className="place-story-month" key={group.heading}>
              <h2>{group.heading}</h2>
              <ul className="place-story-entries">
                {group.items.map((entry) => (
                  <PlaceStoryCard
                    entry={entry}
                    key={entry.id}
                    onOpenBirdLog={onOpenBirdLog}
                    onOpenPlaceActivityReport={onOpenPlaceActivityReport}
                    onOpenVisit={onOpenVisit}
                  />
                ))}
              </ul>
            </section>
          ))}
          {hasMore ? (
            <button
              className="secondary-action"
              disabled={loadingMore}
              onClick={loadMore}
              type="button"
            >
              {loadingMore ? "Loading…" : "Load more"}
            </button>
          ) : null}
        </>
      )}
    </div>
  );
}

interface PlaceStoryCardProps {
  entry: PlaceStoryEntry;
  onOpenVisit: (visitId: string) => void;
  onOpenBirdLog: (label?: string) => void;
  onOpenPlaceActivityReport: () => void;
}

function PlaceStoryCard({ entry, onOpenVisit, onOpenBirdLog, onOpenPlaceActivityReport }: PlaceStoryCardProps) {
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
        {entry.taxon_label ? (
          <button className="text-action" onClick={() => onOpenBirdLog(entry.taxon_label!)} type="button">
            {entry.taxon_display_name ?? "View"} in Bird Log
          </button>
        ) : null}
        {entry.feature_id || entry.kind === "phenology" ? (
          <button className="text-action" onClick={onOpenPlaceActivityReport} type="button">
            View in Place Report
          </button>
        ) : null}
      </div>
    </li>
  );
}
