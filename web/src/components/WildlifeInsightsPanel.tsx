import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type {
  ActivityLibraryFilters,
  WildlifeInsightsBreakdown,
  WildlifeInsightsDrilldown,
  WildlifeInsightsRepresentative,
  WildlifeInsightsRequest,
  WildlifeInsightsSummary,
} from "../api/types";
import { EmptyState } from "./EmptyState";
import { MetricCard } from "./MetricCard";
import { formatDateTime } from "../utils";

interface WildlifeInsightsPanelProps {
  onOpenActivityLibrary: (filters: ActivityLibraryFilters) => void;
  onOpenBirdLog: () => void;
  onOpenReview: () => void;
  onOpenStream: (streamId?: string) => void;
  onOpenStreams: () => void;
  onOpenVisit: (visitId: string) => void;
}

const rangeOptions: Array<{ value: WildlifeInsightsRequest["preset"]; label: string }> = [
  { value: "today", label: "Today" },
  { value: "last_7_days", label: "Last 7 days" },
  { value: "last_30_days", label: "Last 30 days" },
  { value: "custom", label: "Custom range" },
];

function localDateInputValue(value = new Date()): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function filtersForDrilldown(drilldown: WildlifeInsightsDrilldown): ActivityLibraryFilters {
  return {
    review_filter: drilldown.review_filter,
    stream_id: drilldown.stream_id ?? null,
    zone_id: drilldown.zone_id ?? null,
    confirmed_label: drilldown.confirmed_label ?? null,
    start_at: drilldown.start_date,
    end_at: drilldown.end_date,
  };
}

function openJournalHistory(label: string): void {
  const path = `/bird-log/${encodeURIComponent(label)}`;
  if (`${window.location.pathname}${window.location.search}` !== path) {
    window.history.pushState({}, "", path);
  }
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function comparisonCopy(summary: WildlifeInsightsSummary): string {
  const change = summary.comparison.reviewed_wildlife_observation_change;
  const period = summary.period.start_date === summary.period.end_date ? "day" : "period";
  if (change === 0) {
    return `The same number of reviewed observations as the previous ${period}.`;
  }
  const count = Math.abs(change);
  return `${count} ${change > 0 ? "more" : "fewer"} reviewed observation${count === 1 ? "" : "s"} than the previous ${period}.`;
}

function activityHourLabel(hour: number): string {
  const suffix = hour < 12 ? "AM" : "PM";
  const display = hour % 12 || 12;
  return `${display} ${suffix}`;
}

function RepresentativeLink({
  observation,
  onOpenVisit,
}: {
  observation: WildlifeInsightsRepresentative | null | undefined;
  onOpenVisit: (visitId: string) => void;
}) {
  const [imageUnavailable, setImageUnavailable] = useState(false);
  if (!observation) return null;
  return (
    <button
      className="wildlife-insights-representative"
      onClick={() => onOpenVisit(observation.visit_id)}
      type="button"
    >
      {observation.primary_evidence && !imageUnavailable ? (
        <img
          alt={`Reviewed ${observation.display_name}`}
          onError={() => setImageUnavailable(true)}
          src={`${apiClient.baseUrl}${observation.primary_evidence.preview_url}`}
        />
      ) : (
        <span className="wildlife-insights-preview-fallback">No saved thumbnail</span>
      )}
      <span>
        <strong>{observation.display_name}</strong>
        <small>{observation.stream_name} · {formatDateTime(observation.observed_at)}</small>
      </span>
    </button>
  );
}

function BreakdownList({
  items,
  onOpenActivityLibrary,
  onOpenStream,
  onOpenVisit,
  title,
}: {
  items: WildlifeInsightsBreakdown[];
  onOpenActivityLibrary: (filters: ActivityLibraryFilters) => void;
  onOpenStream?: (streamId: string) => void;
  onOpenVisit: (visitId: string) => void;
  title: string;
}) {
  if (!items.length) {
    return <span className="meta-text">No confirmed wildlife matches this range.</span>;
  }
  const maximum = Math.max(...items.map((item) => item.count), 1);
  return (
    <div className="wildlife-insights-breakdown" aria-label={title}>
      {items.map((item) => (
        <div className="wildlife-insights-breakdown-row" key={item.id}>
          <button onClick={() => onOpenActivityLibrary(filtersForDrilldown(item.drilldown))} type="button">
            <span>{item.name}</span>
            <strong>{item.count}</strong>
          </button>
          <span aria-hidden="true" className="wildlife-insights-bar"><i style={{ width: `${(item.count / maximum) * 100}%` }} /></span>
          <small>
            {item.change === 0 ? "No change" : `${item.change > 0 ? "+" : ""}${item.change} vs prior`}
          </small>
          <div className="wildlife-insights-row-actions">
            {onOpenStream && item.drilldown.stream_id ? (
              <button className="text-action" onClick={() => onOpenStream(item.drilldown.stream_id!)} type="button">Stream</button>
            ) : null}
            {item.drilldown.confirmed_label ? (
              <button className="text-action" onClick={() => openJournalHistory(item.drilldown.confirmed_label!)} type="button">Journal</button>
            ) : null}
            {item.representative ? (
              <button className="text-action" onClick={() => onOpenVisit(item.representative!.visit_id)} type="button">Visit</button>
            ) : null}
          </div>
        </div>
      ))}
    </div>
  );
}

export function WildlifeInsightsPanel({
  onOpenActivityLibrary,
  onOpenBirdLog,
  onOpenReview,
  onOpenStream,
  onOpenStreams,
  onOpenVisit,
}: WildlifeInsightsPanelProps) {
  const [preset, setPreset] = useState<WildlifeInsightsRequest["preset"]>("last_7_days");
  const [customStartDate, setCustomStartDate] = useState(localDateInputValue());
  const [customEndDate, setCustomEndDate] = useState(localDateInputValue());
  const [appliedCustomRange, setAppliedCustomRange] = useState<Pick<WildlifeInsightsRequest, "start_date" | "end_date"> | null>(null);
  const [summary, setSummary] = useState<WildlifeInsightsSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const request = useMemo<WildlifeInsightsRequest | null>(() => {
    if (preset !== "custom") return { preset };
    return appliedCustomRange
      ? { preset, start_date: appliedCustomRange.start_date, end_date: appliedCustomRange.end_date }
      : null;
  }, [appliedCustomRange, preset]);

  useEffect(() => {
    if (!request) return;
    let active = true;
    setIsLoading(true);
    setError(null);
    void apiClient
      .getWildlifeInsights(request)
      .then((next) => {
        if (active) setSummary(next);
      })
      .catch(() => {
        if (active) setError("Could not load Wildlife Insights. Your activity remains available in the Activity Library.");
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [request]);

  const applyCustomRange = () => {
    if (!customStartDate || !customEndDate || customEndDate < customStartDate) return;
    setAppliedCustomRange({ start_date: customStartDate, end_date: customEndDate });
  };

  const selectPreset = (nextPreset: WildlifeInsightsRequest["preset"]) => {
    setPreset(nextPreset);
    setError(null);
    setSummary(null);
    if (nextPreset === "custom") {
      setAppliedCustomRange(null);
      setIsLoading(false);
    } else {
      setIsLoading(true);
    }
  };

  return (
    <section className="panel wildlife-insights-panel">
      <div className="section-heading">
        <div>
          <h2>Wildlife Insights</h2>
          <span className="meta-text">Confirmed observations come only from current reviewed corrections. Suggestions remain evidence for review.</span>
        </div>
        <button className="secondary-action" onClick={onOpenBirdLog} type="button">Open Bird Log</button>
      </div>

      <div className="wildlife-insights-range" aria-label="Wildlife Insights date range">
        {rangeOptions.map((option) => (
          <button
            className={preset === option.value ? "primary-action" : "secondary-action"}
            key={option.value}
            onClick={() => selectPreset(option.value)}
            type="button"
          >
            {option.label}
          </button>
        ))}
        {preset === "custom" ? (
          <>
            <label>From <input max={customEndDate} onChange={(event) => setCustomStartDate(event.target.value)} type="date" value={customStartDate} /></label>
            <label>To <input min={customStartDate} onChange={(event) => setCustomEndDate(event.target.value)} type="date" value={customEndDate} /></label>
            <button className="primary-action" disabled={!customStartDate || !customEndDate || customEndDate < customStartDate} onClick={applyCustomRange} type="button">Apply</button>
          </>
        ) : null}
      </div>

      {isLoading && !summary ? <span className="meta-text">Loading reviewed wildlife activity…</span> : null}
      {error ? <div className="error-panel">{error}</div> : null}
      {!request && preset === "custom" ? <span className="meta-text">Choose a valid custom date range, then apply it.</span> : null}
      {summary ? (
        <div className="wildlife-insights-content">
          <div className="wildlife-insights-period">
            {summary.period.start_date} to {summary.period.end_date} · local time ({summary.period.timezone_name})
          </div>
          {summary.headline.active_stream_count === 0 ? (
            <EmptyState
              title="No active cameras to summarize"
              description="Add or restore a camera, then review captured activity to build local wildlife insights."
              action={<button className="secondary-action" onClick={onOpenStreams} type="button">Open Cameras / Streams</button>}
            />
          ) : summary.headline.active_visit_count === 0 ? (
            <EmptyState
              title="No activity in this range"
              description="Try a wider range, or open the Activity Library to inspect captured Visits."
              action={<button className="secondary-action" onClick={() => onOpenActivityLibrary(filtersForDrilldown(summary.confirmed_activity_drilldown))} type="button">Open Activity Library</button>}
            />
          ) : (
            <>
              <section className="metric-grid wildlife-insights-metrics">
                <MetricCard label="Reviewed wildlife" value={summary.headline.reviewed_wildlife_observation_count} detail="confirmed observations" />
                <MetricCard label="Confirmed labels" value={summary.headline.unique_confirmed_label_count} detail="in this range" />
                <MetricCard label="Unresolved Visits" value={summary.headline.unresolved_visit_count} detail="need review" />
                <MetricCard label="Reviewed non-bird" value={summary.headline.reviewed_non_bird_activity_count} detail="kept separate" />
                <MetricCard label="Busiest Stream" value={summary.headline.busiest_stream?.name ?? "—"} detail={summary.headline.busiest_stream ? `${summary.headline.busiest_stream.count} confirmed observations` : "No confirmed activity"} />
                <MetricCard label="Peak hour" value={summary.headline.peak_activity_hour == null ? "—" : activityHourLabel(summary.headline.peak_activity_hour)} detail="confirmed activity" />
              </section>

              <section className="notice-panel wildlife-insights-comparison">
                <strong>{comparisonCopy(summary)}</strong>
                <span>
                  {summary.comparison.new_labels.length ? `New labels: ${summary.comparison.new_labels.join(", ")}. ` : ""}
                  {summary.comparison.labels_not_seen.length ? `Not seen this range: ${summary.comparison.labels_not_seen.join(", ")}.` : ""}
                </span>
              </section>

              {summary.headline.reviewed_wildlife_observation_count === 0 ? (
                <EmptyState
                  title="Activity is present, but no confirmed wildlife yet"
                  description="Review Visits to create corrected observation truth. Blank, false, ambiguous, and unknown outcomes stay out of wildlife counts."
                  action={<button className="secondary-action" onClick={onOpenReview} type="button">Open Review Queue</button>}
                />
              ) : (
                <>
                  <section className="wildlife-insights-grid">
                    <div className="panel">
                      <div className="section-heading"><div><h3>Leading confirmed wildlife</h3><span className="meta-text">Open a label for its reviewed Visits.</span></div></div>
                      <BreakdownList items={summary.leading_labels} onOpenActivityLibrary={onOpenActivityLibrary} onOpenVisit={onOpenVisit} title="Leading confirmed wildlife" />
                    </div>
                    <div className="panel">
                      <div className="section-heading"><div><h3>First and latest observations</h3><span className="meta-text">Representative thumbnails are optional evidence, not the count.</span></div></div>
                      <div className="wildlife-insights-representatives">
                        <RepresentativeLink observation={summary.headline.first_observation} onOpenVisit={onOpenVisit} />
                        <RepresentativeLink observation={summary.headline.latest_observation} onOpenVisit={onOpenVisit} />
                      </div>
                    </div>
                  </section>

                  <section className="wildlife-insights-grid">
                    <div className="panel">
                      <div className="section-heading"><div><h3>Observations by day</h3><span className="meta-text">Each bar also states its reviewed count.</span></div></div>
                      <div className="wildlife-insights-day-chart" role="img" aria-label="Confirmed wildlife observations by day">
                        {summary.daily_trend.map((bucket) => (
                          <span key={bucket.local_date} style={{ height: `${Math.max(8, bucket.count * 20)}px` }} title={`${bucket.local_date}: ${bucket.count}`}>{bucket.count}</span>
                        ))}
                      </div>
                      <div className="wildlife-insights-value-table">
                        {summary.daily_trend.map((bucket) => <span key={bucket.local_date}>{bucket.local_date}: <strong>{bucket.count}</strong></span>)}
                      </div>
                    </div>
                    <div className="panel">
                      <div className="section-heading"><div><h3>Activity by hour</h3><span className="meta-text">Local time, confirmed wildlife only.</span></div></div>
                      <div className="wildlife-insights-hour-grid" aria-label="Confirmed wildlife observations by hour">
                        {summary.activity_by_hour.map((bucket) => <span key={bucket.hour}>{activityHourLabel(bucket.hour)} <strong>{bucket.count}</strong></span>)}
                      </div>
                    </div>
                  </section>

                  <section className="wildlife-insights-grid">
                    <div className="panel"><div className="section-heading"><div><h3>Camera / Stream activity</h3><span className="meta-text">Confirmed wildlife by current Stream.</span></div></div><BreakdownList items={summary.stream_breakdown} onOpenActivityLibrary={onOpenActivityLibrary} onOpenStream={onOpenStream} onOpenVisit={onOpenVisit} title="Camera and Stream activity" /></div>
                    <div className="panel"><div className="section-heading"><div><h3>Zone activity</h3><span className="meta-text">Visits without a current Zone remain counted, but are not assigned to a Zone.</span></div></div><BreakdownList items={summary.zone_breakdown} onOpenActivityLibrary={onOpenActivityLibrary} onOpenVisit={onOpenVisit} title="Zone activity" /></div>
                  </section>
                </>
              )}

              <section className="wildlife-insights-context">
                <div><strong>Confirmed wildlife</strong><span>{summary.headline.reviewed_wildlife_observation_count} latest reviewed bird observations.</span></div>
                <div><strong>Reviewed non-bird activity</strong><span>{summary.headline.reviewed_non_bird_activity_count} people, pets, vehicles, squirrels, or similar activity under existing semantics.</span></div>
                <div><strong>Unresolved activity</strong><button className="text-action" onClick={() => onOpenActivityLibrary(filtersForDrilldown(summary.unresolved_activity_drilldown))} type="button">{summary.headline.unresolved_visit_count} needs-review Visits</button></div>
                <div><strong>Review-quality outcomes</strong><span>{summary.review_context.blank_or_false_count} blank/false · {summary.review_context.ambiguous_or_unknown_count} ambiguous/unknown · {summary.review_context.pending_suggestion_evidence_count} pending suggestion evidence</span></div>
              </section>
            </>
          )}
        </div>
      ) : null}
    </section>
  );
}
