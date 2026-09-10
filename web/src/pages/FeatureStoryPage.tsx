import { useEffect, useRef, useState } from "react";
import { ApiError, apiClient } from "../api/client";
import type { PlaceFeatureDetail, PlaceStoryEntry } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { PlaceStoryEntryCard } from "../components/PlaceStoryEntryCard";
import { RepresentativeThumbnail } from "../components/RepresentativeThumbnail";
import { StatusPill } from "../components/StatusPill";
import {
  CHANGE_EVENT_TYPE_DISPLAY_NAMES,
  FEATURE_TYPE_DISPLAY_NAMES,
  environmentalComparisonSentence,
  featureAssociationSentence,
} from "./PlaceActivityReportPage";
import { formatDate, formatDateTime } from "../utils";

/**
 * Place Story Deep Dives & Representative Evidence v1 -- see
 * docs/place-story-deep-dives-representative-evidence-v1-report.md. "The
 * story of Bird Bath, here" -- one canonical Feature's own longitudinal
 * view, and this product's first dedicated, URL-addressable Feature detail
 * page (previously only an inline expand on the Place Report page; see
 * that report's own recorded "dedicated Feature detail page" gap). Composed
 * entirely from already-accepted primitives:
 *
 * - current state from `GET /api/place/features/{id}/detail` (the existing
 *   detail bundle -- observation links, recent yield, representative
 *   evidence, and every change event's own before/after comparison);
 * - a chronological timeline from `GET /api/place/story?feature_id=` (the
 *   exact same composition engine Place-wide Story already uses, filtered
 *   server-side -- never a second timeline engine).
 *
 * One canonical Feature regardless of camera-view count: this page never
 * duplicates a Story entry or a change event per camera (Multi-Camera
 * Place Feature Linking v1's own guarantee, unmodified here).
 */
interface FeatureStoryPageProps {
  featureId: string;
  onOpenVisit: (visitId: string) => void;
  onOpenTaxonStory: (label: string) => void;
  onOpenBirdLog: (label?: string) => void;
  onOpenPlaceActivityReport: () => void;
}

const STORY_PAGE_SIZE = 30;

export function FeatureStoryPage({
  featureId,
  onOpenVisit,
  onOpenTaxonStory,
  onOpenBirdLog,
  onOpenPlaceActivityReport,
}: FeatureStoryPageProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [detail, setDetail] = useState<PlaceFeatureDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(true);
  const [entries, setEntries] = useState<PlaceStoryEntry[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [storyLoading, setStoryLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    let active = true;
    setDetailLoading(true);
    setNotFound(false);
    setDetailError(null);
    setDetail(null);
    apiClient
      .getPlaceFeatureDetail(featureId)
      .then((response) => {
        if (active) setDetail(response);
      })
      .catch((caught: unknown) => {
        if (!active) return;
        if (caught instanceof ApiError && caught.status === 404) {
          setNotFound(true);
        } else {
          setDetailError("Could not load this Feature's story right now.");
        }
      })
      .finally(() => {
        if (active) setDetailLoading(false);
      });
    return () => {
      active = false;
    };
  }, [featureId]);

  useEffect(() => {
    let active = true;
    setStoryLoading(true);
    setEntries([]);
    apiClient
      .getPlaceStory({ feature_id: featureId, page_size: STORY_PAGE_SIZE, offset: 0 })
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
  }, [featureId]);

  useEffect(() => {
    if (!detailLoading) {
      headingRef.current?.focus();
    }
  }, [detailLoading, featureId]);

  function loadMore() {
    if (nextOffset == null) return;
    setLoadingMore(true);
    apiClient
      .getPlaceStory({ feature_id: featureId, page_size: STORY_PAGE_SIZE, offset: nextOffset })
      .then((response) => {
        setEntries((prior) => [...prior, ...response.entries]);
        setHasMore(response.has_more);
        setNextOffset(response.next_offset ?? null);
      })
      .finally(() => setLoadingMore(false));
  }

  if (detailLoading) {
    return (
      <div className="page feature-story-page">
        <p role="status">Loading the Feature story…</p>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="page feature-story-page">
        <PageHeader eyebrow="Remember" headingRef={headingRef} title="Not found" />
        <EmptyState
          description="This Place Feature no longer exists, or its link is no longer valid."
          title="No Feature story here"
        />
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="page feature-story-page">
        <PageHeader eyebrow="Remember" headingRef={headingRef} title="Not available" />
        <EmptyState
          description={detailError ?? "Could not load this Feature's story right now. Try refreshing the page."}
          title="Could not load this Feature"
        />
      </div>
    );
  }

  const feature = detail.feature;
  const latestChange = detail.changes[0] ?? null;
  const observedBy =
    feature.observation_links.length > 0
      ? feature.observation_links
          .map(
            (link) =>
              `${link.source_name}${link.source_archived ? " (archived)" : ""}${
                link.zone_name ? ` — ${link.zone_name}` : ""
              }`,
          )
          .join(", ")
      : "no camera linked yet";

  return (
    <div className="page feature-story-page">
      <PageHeader
        actions={!feature.is_active ? <StatusPill label="Inactive" tone="quiet" /> : null}
        description={`${FEATURE_TYPE_DISPLAY_NAMES[feature.feature_type] ?? "Feature"} at this Place.`}
        eyebrow="Remember"
        headingRef={headingRef}
        title={feature.name}
      />

      <section aria-label={`${feature.name} summary`} className="journal-label-card">
        {detail.representative_evidence ? (
          <button
            className="journal-label-image"
            onClick={() => onOpenVisit(detail.representative_evidence!.visit_id)}
            type="button"
          >
            <RepresentativeThumbnail
              alt={`Recent wildlife at ${feature.name}, reviewed observation ${formatDateTime(
                detail.representative_evidence.evidence.captured_at,
              )}`}
              evidence={detail.representative_evidence.evidence}
              fallbackText="No image yet"
            />
          </button>
        ) : (
          <div className="journal-label-image">
            <RepresentativeThumbnail alt={feature.name} evidence={null} fallbackText="No image yet" />
          </div>
        )}
        <div className="journal-label-card-body">
          <p className="meta-text">Observed by: {observedBy}</p>
          {detail.recent_yield ? (
            <p className="meta-text">
              Last {detail.recent_yield.window_days} days: {detail.recent_yield.confirmed_wildlife_visit_count}{" "}
              confirmed {detail.recent_yield.confirmed_wildlife_visit_count === 1 ? "visit" : "visits"},{" "}
              {detail.recent_yield.distinct_taxon_count}{" "}
              {detail.recent_yield.distinct_taxon_count === 1 ? "species" : "distinct species"}
              {detail.recent_yield.data_sufficient && detail.recent_yield.visits_per_monitored_hour != null
                ? ` (${detail.recent_yield.visits_per_monitored_hour} per monitored hour)`
                : ""}
              .
            </p>
          ) : (
            <p className="meta-text">Not enough monitoring linked yet to show recent activity.</p>
          )}
          {latestChange ? (
            <div>
              <p>
                Most recent change: {CHANGE_EVENT_TYPE_DISPLAY_NAMES[latestChange.event.event_type]} on{" "}
                {formatDate(latestChange.event.effective_date)}.
              </p>
              {latestChange.comparison ? (
                <p className="meta-text">{featureAssociationSentence(latestChange.comparison)}</p>
              ) : null}
              {environmentalComparisonSentence(latestChange.environmental_comparison) ? (
                <p className="meta-text feature-environmental-comparison">
                  {environmentalComparisonSentence(latestChange.environmental_comparison)}
                </p>
              ) : null}
            </div>
          ) : (
            <p className="meta-text">No changes recorded for this Feature yet.</p>
          )}
          <div className="today-report-footer">
            <button className="text-action" onClick={onOpenPlaceActivityReport} type="button">
              View in Place Report
            </button>
          </div>
        </div>
      </section>

      {storyLoading ? (
        <p role="status">Loading the timeline…</p>
      ) : entries.length === 0 ? (
        <EmptyState
          description="No Reviewed changes or before/after insights have been recorded yet for this Feature."
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
                onOpenPlaceActivityReport={onOpenPlaceActivityReport}
                onOpenTaxonStory={onOpenTaxonStory}
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
