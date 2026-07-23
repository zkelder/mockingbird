import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type {
  CameraSource,
  Stream,
  WildlifeJournalGalleryOrder,
  WildlifeJournalHistoryRequest,
  WildlifeJournalHistoryResponse,
  WildlifeJournalLabelSummary,
  WildlifeJournalObservation,
  WildlifeJournalOrder,
  WildlifeJournalRangePreset,
  WildlifeJournalRepresentative,
  WildlifeJournalOverviewResponse,
  Zone,
} from "../api/types";
import { activityLibraryPath } from "./ActivityLibraryPage";
import { EmptyState } from "../components/EmptyState";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime } from "../utils";

interface BirdLogPageProps {
  sources: CameraSource[];
  streams: Stream[];
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenStreams: () => void;
  onOpenImport: () => void;
  onOpenReview: () => void;
  onOpenExports: () => void;
}

interface JournalLocation {
  order: WildlifeJournalOrder;
  preset: WildlifeJournalRangePreset;
  startDate: string;
  endDate: string;
  streamId: string;
  zoneId: string;
  favoritesOnly: boolean;
  galleryOrder: WildlifeJournalGalleryOrder;
  offset: number;
}

const overviewOrders: Array<{ value: WildlifeJournalOrder; label: string }> = [
  { value: "most_recent", label: "Most recently observed" },
  { value: "most_observed", label: "Most observed" },
  { value: "alphabetical", label: "Alphabetical" },
  { value: "first_observed", label: "First observed" },
];

const rangeOptions: Array<{ value: WildlifeJournalRangePreset; label: string }> = [
  { value: "all_time", label: "All time" },
  { value: "today", label: "Today" },
  { value: "last_7_days", label: "Last 7 days" },
  { value: "last_30_days", label: "Last 30 days" },
  { value: "this_year", label: "This year" },
  { value: "custom", label: "Custom range" },
];

function localDateInputValue(value = new Date()): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function validOption<T extends string>(value: string | null, options: readonly T[], fallback: T): T {
  return value && options.includes(value as T) ? (value as T) : fallback;
}

function readJournalLocation(): JournalLocation {
  const params = new URLSearchParams(window.location.search);
  const parsedOffset = Number.parseInt(params.get("offset") ?? "0", 10);
  return {
    order: validOption(
      params.get("order"),
      overviewOrders.map((option) => option.value),
      "most_recent",
    ),
    preset: validOption(
      params.get("range"),
      rangeOptions.map((option) => option.value),
      "all_time",
    ),
    startDate: params.get("from") ?? "",
    endDate: params.get("to") ?? "",
    streamId: params.get("stream") ?? "",
    zoneId: params.get("zone") ?? "",
    favoritesOnly: params.get("favorites") === "1",
    galleryOrder: validOption(params.get("gallery"), ["newest", "oldest"], "newest"),
    offset: Number.isFinite(parsedOffset) && parsedOffset >= 0 ? parsedOffset : 0,
  };
}

function readJournalLabel(pathname = window.location.pathname): string | null {
  const normalizedPath = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  const segments = normalizedPath.split("/").filter(Boolean);
  if (segments.length !== 2 || segments[0] !== "bird-log") return null;
  try {
    return decodeURIComponent(segments[1]).trim() || null;
  } catch {
    return null;
  }
}

function journalPath(label: string | null, location: JournalLocation): string {
  const params = new URLSearchParams();
  if (!label) {
    if (location.order !== "most_recent") params.set("order", location.order);
    return `/bird-log${params.size ? `?${params.toString()}` : ""}`;
  }
  if (location.preset !== "all_time") params.set("range", location.preset);
  if (location.startDate) params.set("from", location.startDate);
  if (location.endDate) params.set("to", location.endDate);
  if (location.streamId) params.set("stream", location.streamId);
  if (location.zoneId) params.set("zone", location.zoneId);
  if (location.favoritesOnly) params.set("favorites", "1");
  if (location.galleryOrder !== "newest") params.set("gallery", location.galleryOrder);
  if (location.offset > 0) params.set("offset", String(location.offset));
  const path = `/bird-log/${encodeURIComponent(label)}`;
  return `${path}${params.size ? `?${params.toString()}` : ""}`;
}

function writeJournalUrl(label: string | null, location: JournalLocation, replace = false): void {
  const path = journalPath(label, location);
  if (replace) {
    window.history.replaceState({}, "", path);
  } else if (`${window.location.pathname}${window.location.search}` !== path) {
    window.history.pushState({}, "", path);
  }
}

function navigatePath(path: string): void {
  if (`${window.location.pathname}${window.location.search}` !== path) {
    window.history.pushState({}, "", path);
  }
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function historyRequest(location: JournalLocation): WildlifeJournalHistoryRequest {
  return {
    preset: location.preset,
    start_date: location.startDate || null,
    end_date: location.endDate || null,
    stream_id: location.streamId || null,
    zone_id: location.zoneId || null,
    favorites_only: location.favoritesOnly,
    gallery_order: location.galleryOrder,
    page_size: 24,
    offset: location.offset,
  };
}

function durationLabel(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)} sec`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} min ${Math.round(seconds % 60)} sec`;
}

function hourLabel(hour: number): string {
  const suffix = hour < 12 ? "AM" : "PM";
  return `${hour % 12 || 12} ${suffix}`;
}

function thumbnailAlt(label: string, observedAt: string): string {
  return `${label}, reviewed observation ${formatDateTime(observedAt)}`;
}

function JournalThumbnail({
  label,
  observedAt,
  representative,
}: {
  label: string;
  observedAt: string;
  representative?: WildlifeJournalRepresentative | WildlifeJournalObservation | null;
}) {
  const [failed, setFailed] = useState(false);
  const evidence = representative?.primary_evidence;
  useEffect(() => setFailed(false), [evidence?.media_asset_id]);
  if (!evidence || failed) {
    return <div className="journal-thumbnail-fallback">No saved thumbnail</div>;
  }
  return (
    <img
      alt={thumbnailAlt(label, observedAt)}
      loading="lazy"
      onError={() => setFailed(true)}
      src={`${apiClient.baseUrl}${evidence.preview_url}`}
    />
  );
}

function Sparkline({ activity }: { activity: WildlifeJournalLabelSummary["recent_activity"] }) {
  const maximum = Math.max(...activity.map((day) => day.count), 1);
  return (
    <div aria-label="Recent reviewed observations" className="journal-sparkline">
      {activity.map((day) => (
        <span
          key={day.local_date}
          style={{ height: `${Math.max(4, Math.round((day.count / maximum) * 30))}px` }}
          title={`${day.local_date}: ${day.count} reviewed observations`}
        />
      ))}
    </div>
  );
}

function BreakdownList({
  items,
  title,
}: {
  items: WildlifeJournalHistoryResponse["stream_breakdown"];
  title: string;
}) {
  if (items.length === 0) return <span className="meta-text">No current {title.toLowerCase()} in this scope.</span>;
  return (
    <div className="journal-breakdown" aria-label={title}>
      {items.map((item) => (
        <div key={item.id}>
          <span>{item.name}</span>
          <strong>{item.count}</strong>
        </div>
      ))}
    </div>
  );
}

export function BirdLogPage({
  streams,
  onOpenVisit,
  onOpenStreams,
  onOpenReview,
}: BirdLogPageProps) {
  const [journalLabel, setJournalLabel] = useState<string | null>(readJournalLabel);
  const [location, setLocation] = useState<JournalLocation>(readJournalLocation);
  const [customStartDate, setCustomStartDate] = useState(location.startDate || localDateInputValue());
  const [customEndDate, setCustomEndDate] = useState(location.endDate || localDateInputValue());
  const [zones, setZones] = useState<Zone[]>([]);
  const [overview, setOverview] = useState<WildlifeJournalOverviewResponse | null>(null);
  const [history, setHistory] = useState<WildlifeJournalHistoryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void apiClient
      .getZones()
      .then((next) => {
        if (active) setZones(next);
      })
      .catch(() => {
        if (active) setZones([]);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    function handlePopState() {
      const next = readJournalLocation();
      const nextLabel = readJournalLabel();
      setJournalLabel(nextLabel);
      setLocation(next);
      setCustomStartDate(next.startDate || localDateInputValue());
      setCustomEndDate(next.endDate || localDateInputValue());
      setError(null);
      if (nextLabel) {
        setHistory(null);
      } else {
        setOverview(null);
      }
    }
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);
    if (!journalLabel) {
      void apiClient
        .getWildlifeJournal(location.order)
        .then((next) => {
          if (active) setOverview(next);
        })
        .catch(() => {
          if (active) setError("Could not load Wildlife Journal. Your reviewed activity remains in the Activity Library.");
        })
        .finally(() => {
          if (active) setIsLoading(false);
        });
    } else {
      void apiClient
        .getWildlifeJournalHistory(journalLabel, historyRequest(location))
        .then((next) => {
          if (active) setHistory(next);
        })
        .catch((caught) => {
          if (active) setError(caught instanceof Error ? caught.message : "Could not load this Journal history.");
        })
        .finally(() => {
          if (active) setIsLoading(false);
        });
    }
    return () => {
      active = false;
    };
  }, [journalLabel, location]);

  const visibleZones = useMemo(
    () => zones.filter((zone) => !location.streamId || zone.stream_id === location.streamId),
    [location.streamId, zones],
  );

  const commitLocation = (next: JournalLocation) => {
    setLocation(next);
    writeJournalUrl(journalLabel, next);
  };

  const navigateJournalLabel = (nextLabel: string | null) => {
    writeJournalUrl(nextLabel, location);
    window.dispatchEvent(new PopStateEvent("popstate"));
  };

  const openActivityLibrary = () => {
    if (!history) return;
    const drilldown = history.activity_library_drilldown;
    navigatePath(activityLibraryPath({
      review_filter: drilldown.review_filter,
      confirmed_label: drilldown.confirmed_label,
      start_at: drilldown.start_date ?? null,
      end_at: drilldown.end_date ?? null,
      stream_id: drilldown.stream_id ?? null,
      zone_id: drilldown.zone_id ?? null,
      favorites_only: location.favoritesOnly,
    }));
  };

  const loadMore = async () => {
    if (!journalLabel || !history?.gallery.next_offset || isLoadingMore) return;
    setIsLoadingMore(true);
    try {
      const next = await apiClient.getWildlifeJournalHistory(journalLabel, {
        ...historyRequest(location),
        offset: history.gallery.next_offset,
      });
      setHistory((current) => {
        if (!current) return next;
        const existing = new Set(current.gallery.observations.map((item) => item.visit_id));
        return {
          ...next,
          gallery: {
            ...next.gallery,
            observations: [
              ...current.gallery.observations,
              ...next.gallery.observations.filter((item) => !existing.has(item.visit_id)),
            ],
          },
        };
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load more reviewed observations.");
    } finally {
      setIsLoadingMore(false);
    }
  };

  if (!journalLabel) {
    return (
      <div className="page-stack">
        <PageHeader
          eyebrow="Reviewed wildlife history"
          title="Wildlife Journal"
          description="Confirmed wildlife from current reviewed corrections. Suggestions and unresolved activity stay in review context."
          actions={
            <>
              <button className="secondary-action" onClick={() => navigatePath("/analytics")} type="button">Wildlife Insights</button>
              <button className="secondary-action" onClick={onOpenReview} type="button">Review Queue</button>
            </>
          }
        />
        <section className="panel journal-controls">
          <label>
            Order labels by
            <select
              onChange={(event) => commitLocation({ ...location, order: event.target.value as WildlifeJournalOrder })}
              value={location.order}
            >
              {overviewOrders.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
        </section>
        {error ? <div className="error-panel">{error}</div> : null}
        {isLoading && !overview ? <div className="panel">Loading Wildlife Journal…</div> : null}
        {overview?.labels.length === 0 && !isLoading ? (
          <EmptyState
            title={streams.length === 0 ? "No cameras to journal yet" : "No confirmed wildlife observations yet"}
            description={streams.length === 0 ? "Add a camera or local media Source, then review outdoor activity." : "Review a Visit to create a confirmed local wildlife observation. Suggestions are not Journal entries."}
            action={<button className="secondary-action" onClick={streams.length === 0 ? onOpenStreams : onOpenReview} type="button">{streams.length === 0 ? "Add Camera" : "Open Review Queue"}</button>}
          />
        ) : null}
        {overview?.labels.length ? (
          <section className="journal-label-grid" aria-label="Confirmed wildlife labels">
            {overview.labels.map((item) => (
              <article className="journal-label-card" key={item.label}>
                <button className="journal-label-image" onClick={() => navigateJournalLabel(item.label)} type="button">
                  <JournalThumbnail label={item.display_name} observedAt={item.latest_observed_at} representative={item.representative} />
                </button>
                <div className="journal-label-card-body">
                  <div className="section-heading">
                    <div><h2>{item.display_name}</h2><span className="meta-text">{item.observation_count} reviewed observation{item.observation_count === 1 ? "" : "s"}</span></div>
                    <Sparkline activity={item.recent_activity} />
                  </div>
                  <div className="journal-label-facts">
                    <span>First: <strong>{formatDateTime(item.first_observed_at)}</strong></span>
                    <span>Latest: <strong>{formatDateTime(item.latest_observed_at)}</strong></span>
                    <span>{item.stream_count} Stream{item.stream_count === 1 ? "" : "s"} · {item.zone_count} Zone{item.zone_count === 1 ? "" : "s"}</span>
                  </div>
                  <button className="secondary-action" onClick={() => navigateJournalLabel(item.label)} type="button">Open history</button>
                </div>
              </article>
            ))}
          </section>
        ) : null}
      </div>
    );
  }

  const activeHistory = history;
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Reviewed wildlife history"
        title={activeHistory ? activeHistory.display_name : "Wildlife Journal"}
        description="One bounded history of current reviewed observations. Open a Visit for full evidence and correction audit context."
        actions={
          <>
            <button className="secondary-action" onClick={() => navigateJournalLabel(null)} type="button">All Journal labels</button>
            <button className="secondary-action" onClick={openActivityLibrary} type="button">Open Activity Library</button>
          </>
        }
      />
      <section className="panel journal-filter-panel">
        <label>
          Date range
          <select
            onChange={(event) => {
              const preset = event.target.value as WildlifeJournalRangePreset;
              commitLocation({
                ...location,
                preset,
                startDate: preset === "custom" ? customStartDate : "",
                endDate: preset === "custom" ? customEndDate : "",
                offset: 0,
              });
            }}
            value={location.preset}
          >
            {rangeOptions.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>
        {location.preset === "custom" ? (
          <>
            <label>From <input max={customEndDate} onChange={(event) => setCustomStartDate(event.target.value)} type="date" value={customStartDate} /></label>
            <label>To <input min={customStartDate} onChange={(event) => setCustomEndDate(event.target.value)} type="date" value={customEndDate} /></label>
            <button
              className="primary-action"
              disabled={!customStartDate || !customEndDate || customEndDate < customStartDate}
              onClick={() => commitLocation({ ...location, startDate: customStartDate, endDate: customEndDate, offset: 0 })}
              type="button"
            >Apply</button>
          </>
        ) : null}
        <label>
          Stream
          <select onChange={(event) => commitLocation({ ...location, streamId: event.target.value, zoneId: "", offset: 0 })} value={location.streamId}>
            <option value="">All Streams</option>
            {streams.map((stream) => <option key={stream.id} value={stream.id}>{stream.name}</option>)}
          </select>
        </label>
        <label>
          Zone
          <select onChange={(event) => commitLocation({ ...location, zoneId: event.target.value, offset: 0 })} value={location.zoneId}>
            <option value="">All Zones</option>
            {visibleZones.map((zone) => <option key={zone.id} value={zone.id}>{zone.name}</option>)}
          </select>
        </label>
        <label>
          Gallery order
          <select onChange={(event) => commitLocation({ ...location, galleryOrder: event.target.value as WildlifeJournalGalleryOrder, offset: 0 })} value={location.galleryOrder}>
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
          </select>
        </label>
        <label>
          Favorites
          <select onChange={(event) => commitLocation({ ...location, favoritesOnly: event.target.value === "yes", offset: 0 })} value={location.favoritesOnly ? "yes" : "all"}>
            <option value="all">All reviewed Visits</option>
            <option value="yes">Favorites only</option>
          </select>
        </label>
      </section>
      {error ? <div className="error-panel">{error}</div> : null}
      {isLoading && !activeHistory ? <div className="panel">Loading reviewed Journal history…</div> : null}
      {activeHistory ? (
        <>
          <div className="journal-scope-note">{activeHistory.scope.start_date ?? "All recorded dates"}{activeHistory.scope.end_date ? ` to ${activeHistory.scope.end_date}` : ""}{activeHistory.scope.favorites_only ? " · favorites only" : ""} · local time ({activeHistory.scope.timezone_name})</div>
          {activeHistory.observation_count === 0 ? (
            <EmptyState
              title="No active confirmed observations in this scope"
              description="This label may have been revised, reopened, superseded, or filtered out. Review history remains available on individual Visits."
              action={<button className="secondary-action" onClick={() => commitLocation({ ...location, preset: "all_time", startDate: "", endDate: "", streamId: "", zoneId: "", favoritesOnly: false, offset: 0 })} type="button">Clear Journal filters</button>}
            />
          ) : (
            <>
              <section className="metric-grid journal-metrics">
                <MetricCard label="Observations" value={activeHistory.observation_count} detail="current reviewed truth" />
                <MetricCard label="Busiest Stream" value={activeHistory.busiest_stream?.name ?? "—"} detail={activeHistory.busiest_stream ? `${activeHistory.busiest_stream.count} observations` : "No activity"} />
                <MetricCard label="Busiest Zone" value={activeHistory.busiest_zone?.name ?? "—"} detail={activeHistory.busiest_zone ? `${activeHistory.busiest_zone.count} observations` : "No Zone context"} />
                <MetricCard label="Peak hour" value={activeHistory.peak_activity_hour == null ? "—" : hourLabel(activeHistory.peak_activity_hour)} detail="local time" />
              </section>
              {activeHistory.is_new_label_in_range ? <div className="notice-panel"><strong>New Journal label in this range</strong><span>This is a local MockingBird record milestone, not an ecological claim.</span></div> : null}
              <section className="journal-history-grid">
                <div className="panel"><h2>First recorded</h2>{activeHistory.first_observation ? <button className="journal-observation-link" onClick={() => onOpenVisit(activeHistory.first_observation!.visit_id)} type="button">{formatDateTime(activeHistory.first_observation.observed_at)} · {activeHistory.first_observation.stream_name}</button> : null}</div>
                <div className="panel"><h2>Most recent</h2>{activeHistory.latest_observation ? <button className="journal-observation-link" onClick={() => onOpenVisit(activeHistory.latest_observation!.visit_id)} type="button">{formatDateTime(activeHistory.latest_observation.observed_at)} · {activeHistory.latest_observation.stream_name}</button> : null}</div>
              </section>
              <section className="journal-history-grid">
                <div className="panel"><h2>Stream activity</h2><BreakdownList items={activeHistory.stream_breakdown} title="Streams" /></div>
                <div className="panel"><h2>Zone activity</h2><BreakdownList items={activeHistory.zone_breakdown} title="Zones" /></div>
              </section>
              <section className="panel">
                <div className="section-heading"><div><h2>Activity by hour</h2><span className="meta-text">Confirmed wildlife only, local time.</span></div></div>
                <div className="journal-hour-grid" aria-label="Confirmed observations by local hour">{activeHistory.activity_by_hour.map((bucket) => <span key={bucket.hour}>{hourLabel(bucket.hour)} <strong>{bucket.count}</strong></span>)}</div>
              </section>
              <section className="journal-gallery" aria-label="Reviewed observation gallery">
                <div className="section-heading"><div><h2>Reviewed observation gallery</h2><span className="meta-text">{activeHistory.gallery.order === "newest" ? "Newest first" : "Oldest first"} · one safe primary preview per Visit.</span></div></div>
                {activeHistory.gallery.observations.map((observation) => (
                  <article className="journal-gallery-card" key={observation.visit_id}>
                    <button className="journal-gallery-image" onClick={() => onOpenVisit(observation.visit_id)} type="button"><JournalThumbnail label={observation.display_name} observedAt={observation.observed_at} representative={observation} /></button>
                    <div className="journal-gallery-body">
                      <div className="section-heading"><div><h3>{formatDateTime(observation.observed_at)}</h3><span className="meta-text">{observation.source_name} · {observation.stream_name}{observation.zone_name ? ` · ${observation.zone_name}` : ""}</span></div><StatusPill label="Reviewed" tone="good" /></div>
                      <div className="journal-gallery-facts"><span>Duration <strong>{durationLabel(observation.duration_seconds)}</strong></span><span>Evidence frames <strong>{observation.evidence_frame_count}</strong></span><span>Correction <strong>{observation.display_name}</strong></span></div>
                      <div className="journal-gallery-milestones">{observation.is_favorite ? <StatusPill label="Favorite" tone="good" /> : null}{observation.has_note ? <StatusPill label="Note" tone="quiet" /> : null}{observation.has_curation_history ? <StatusPill label="Curated" tone="quiet" /> : null}{observation.has_review_revision ? <StatusPill label="Revised" tone="quiet" /> : null}{observation.is_first_on_stream ? <StatusPill label="First on Stream" tone="quiet" /> : null}{observation.is_first_in_zone ? <StatusPill label="First in Zone" tone="quiet" /> : null}</div>
                      <button className="secondary-action" onClick={() => onOpenVisit(observation.visit_id)} type="button">Open Visit Detail</button>
                    </div>
                  </article>
                ))}
                {activeHistory.gallery.has_more ? <button className="secondary-action" disabled={isLoadingMore} onClick={() => void loadMore()} type="button">{isLoadingMore ? "Loading…" : "Load more observations"}</button> : null}
              </section>
            </>
          )}
        </>
      ) : null}
    </div>
  );
}
