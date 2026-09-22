import { useEffect, useRef, useState } from "react";
import { ApiError, apiClient } from "../api/client";
import type { PlaceStoryEntry, PlaceYearOverYearResponse, WildlifeJournalHistoryResponse } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { PlaceStoryEntryCard } from "../components/PlaceStoryEntryCard";
import { RepresentativeThumbnail } from "../components/RepresentativeThumbnail";
import { StatusPill } from "../components/StatusPill";
import { speciesChangeSentence } from "../components/YearOverYearCard";
import {
  changeStatusBadge,
  formatDateFromInstant,
  formatDateTime,
  historicalStatusBadge,
  regularityNarrativeBadge,
  seasonalPatternNote,
} from "../utils";

/**
 * Place Story Deep Dives & Representative Evidence v1 -- see
 * docs/place-story-deep-dives-representative-evidence-v1-report.md. "The
 * story of Northern Cardinal, here" -- a calm, longitudinal view of one
 * taxon composed entirely from already-accepted primitives:
 *
 * - header facts from `GET /api/bird-log/journal/{label}` (the existing
 *   Bird Log per-species drill-down bundle -- regularity, first/latest
 *   observation, representative evidence, busiest Zone/Stream);
 * - a year-over-year line from `GET /api/place/year-over-year?taxon=`;
 * - a chronological timeline from `GET /api/place/story?taxon=` (the exact
 *   same composition engine/event selection Place-wide Story already uses,
 *   filtered server-side -- never a second timeline engine).
 *
 * This page never re-derives truth, regularity, or ranking of its own --
 * it only fetches and presents. Bird Log remains the detailed, complete
 * occurrence log; this page is the calmer "why does this matter" summary.
 */
interface TaxonStoryPageProps {
  taxonLabel: string;
  onOpenVisit: (visitId: string) => void;
  onOpenBirdLog: (label?: string) => void;
  onOpenFeatureStory: (featureId: string) => void;
  onOpenPlaceActivityReport: () => void;
}

const STORY_PAGE_SIZE = 30;

function formatLabelGuess(label: string): string {
  return label
    .split("_")
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

export function TaxonStoryPage({
  taxonLabel,
  onOpenVisit,
  onOpenBirdLog,
  onOpenFeatureStory,
  onOpenPlaceActivityReport,
}: TaxonStoryPageProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [history, setHistory] = useState<WildlifeJournalHistoryResponse | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [headerError, setHeaderError] = useState<string | null>(null);
  const [headerLoading, setHeaderLoading] = useState(true);
  const [yearOverYear, setYearOverYear] = useState<PlaceYearOverYearResponse | null>(null);
  const [entries, setEntries] = useState<PlaceStoryEntry[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [storyLoading, setStoryLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    let active = true;
    setHeaderLoading(true);
    setNotFound(false);
    setHeaderError(null);
    setHistory(null);
    apiClient
      .getWildlifeJournalHistory(taxonLabel, { preset: "all_time" })
      .then((response) => {
        if (active) setHistory(response);
      })
      .catch((caught: unknown) => {
        if (!active) return;
        if (caught instanceof ApiError && caught.status === 404) {
          setNotFound(true);
        } else {
          setHeaderError("Could not load this taxon's story right now.");
        }
      })
      .finally(() => {
        if (active) setHeaderLoading(false);
      });
    return () => {
      active = false;
    };
  }, [taxonLabel]);

  useEffect(() => {
    let active = true;
    setYearOverYear(null);
    apiClient
      .getPlaceYearOverYear({ taxon: taxonLabel })
      .then((response) => {
        if (active) setYearOverYear(response);
      })
      .catch(() => {
        // Absence-safe: a Taxon Story remains fully useful with no
        // year-over-year line at all, mirroring YearOverYearCard's own
        // "render nothing on failure" discipline -- never a second error
        // banner alongside the header's own.
      });
    return () => {
      active = false;
    };
  }, [taxonLabel]);

  useEffect(() => {
    let active = true;
    setStoryLoading(true);
    setEntries([]);
    apiClient
      .getPlaceStory({ taxon: taxonLabel, page_size: STORY_PAGE_SIZE, offset: 0 })
      .then((response) => {
        if (!active) return;
        setEntries(response.entries);
        setHasMore(response.has_more);
        setNextOffset(response.next_offset ?? null);
      })
      .catch(() => undefined)
      .finally(() => {
        if (active) setStoryLoading(false);
      });
    return () => {
      active = false;
    };
  }, [taxonLabel]);

  // WAI-ARIA "focus the new region's own heading" pattern (see Fast
  // Review's `activeItemHeadingRef`/the mobile nav drawer's identical
  // convention) -- this page can be reused for a different taxon without a
  // full remount (a Story-card link from one Taxon Story to another, were
  // that ever added), so focus follows the *label*, not only mount.
  useEffect(() => {
    if (!headerLoading) {
      headingRef.current?.focus();
    }
  }, [headerLoading, taxonLabel]);

  function loadMore() {
    if (nextOffset == null) return;
    setLoadingMore(true);
    apiClient
      .getPlaceStory({ taxon: taxonLabel, page_size: STORY_PAGE_SIZE, offset: nextOffset })
      .then((response) => {
        setEntries((prior) => [...prior, ...response.entries]);
        setHasMore(response.has_more);
        setNextOffset(response.next_offset ?? null);
      })
      .finally(() => setLoadingMore(false));
  }

  const fallbackTitle = formatLabelGuess(taxonLabel);

  if (headerLoading) {
    return (
      <div className="page taxon-story-page">
        <p role="status">Loading the story of {fallbackTitle}…</p>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="page taxon-story-page">
        <PageHeader eyebrow="Remember" headingRef={headingRef} title="Not found" />
        <EmptyState
          description={`"${taxonLabel}" is not a species or animal MockingBird recognizes at this Place.`}
          title="No taxon story here"
        />
      </div>
    );
  }

  const displayName = history?.display_name ?? fallbackTitle;
  const badges = [
    historicalStatusBadge(history?.historical_status),
    regularityNarrativeBadge(history?.regularity_narrative),
    changeStatusBadge(history?.change_status),
  ].filter((badge): badge is { label: string; tone: "good" | "quiet" } => badge !== null);
  const seasonalNote = seasonalPatternNote(history?.seasonal_pattern);
  const hasAnyHistory = (history?.observation_count ?? 0) > 0;

  return (
    <div className="page taxon-story-page">
      <PageHeader
        description={`The story of ${displayName} at this Place.`}
        eyebrow="Remember"
        headingRef={headingRef}
        title={displayName}
      />

      {headerError ? <EmptyState description={headerError} title="Something went wrong" /> : null}

      {!hasAnyHistory ? (
        <EmptyState
          description={`MockingBird has not yet confirmed ${displayName} at this Place — once a sighting is reviewed, its story will start here.`}
          title="No confirmed observations yet"
        />
      ) : (
        <section aria-label={`${displayName} summary`} className="journal-label-card">
          {history?.representative ? (
            <button
              className="journal-label-image"
              onClick={() => onOpenVisit(history.representative!.visit_id)}
              type="button"
            >
              <RepresentativeThumbnail
                alt={`${displayName}, reviewed observation ${formatDateTime(history.representative.observed_at)}`}
                evidence={history.representative.primary_evidence}
                fallbackText="No image yet"
              />
            </button>
          ) : (
            <div className="journal-label-image">
              <RepresentativeThumbnail alt={displayName} evidence={null} fallbackText="No image yet" />
            </div>
          )}
          <div className="journal-label-card-body">
            {badges.length > 0 ? (
              <div className="tag-row">
                {badges.map((badge) => (
                  <StatusPill key={badge.label} label={badge.label} tone={badge.tone} />
                ))}
              </div>
            ) : null}
            {seasonalNote ? <p className="meta-text">{seasonalNote}</p> : null}
            {yearOverYear?.taxon_comparison ? <p>{speciesChangeSentence(yearOverYear.taxon_comparison)}.</p> : null}
            {history?.first_observation ? (
              <p className="meta-text">
                First observed here on {formatDateFromInstant(history.first_observation.observed_at)}.
              </p>
            ) : null}
            {history?.busiest_zone ? (
              <p className="meta-text">Frequently recorded near the {history.busiest_zone.name}.</p>
            ) : null}
            <div className="today-report-footer">
              <button className="text-action" onClick={() => onOpenBirdLog(taxonLabel)} type="button">
                See every observation in Bird Log
              </button>
            </div>
          </div>
        </section>
      )}

      {storyLoading ? (
        <p role="status">Loading the timeline…</p>
      ) : entries.length === 0 ? (
        <EmptyState
          description="No dated, longitudinally meaningful moments (firsts, regularity changes, year-over-year shifts) have been recorded yet for this taxon."
          title="No story events yet"
        />
      ) : (
        <>
          <ul className="place-story-entries">
            {entries.map((entry) => (
              <PlaceStoryEntryCard
                entry={entry}
                key={entry.id}
                onOpenBirdLog={onOpenBirdLog}
                onOpenFeatureStory={onOpenFeatureStory}
                onOpenPlaceActivityReport={onOpenPlaceActivityReport}
                onOpenVisit={onOpenVisit}
              />
            ))}
          </ul>
          {hasMore ? (
            <button className="secondary-action" disabled={loadingMore} onClick={loadMore} type="button">
              {loadingMore ? "Loading…" : "Load more"}
            </button>
          ) : null}
        </>
      )}
    </div>
  );
}
