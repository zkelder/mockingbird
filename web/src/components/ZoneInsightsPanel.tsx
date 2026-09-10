import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import { formatLabel } from "../utils";
import type {
  ActivityLibraryFilters,
  CameraSource,
  Stream,
  TaxonomyLabel,
  ZoneInsightsRequest,
  ZoneInsightsSummary,
  ZoneInsightsZone,
  ZoneType,
} from "../api/types";
import { EmptyState } from "./EmptyState";
import { MetricCard } from "./MetricCard";

type RangePreset = "last_7_days" | "last_30_days" | "custom";
type SortKey = "automatic" | "confirmed" | "rate" | "dwell" | "richness" | "review";

const zoneTypes: Array<{ value: ZoneType; label: string }> = [
  { value: "feeder", label: "Feeder" },
  { value: "birdbath", label: "Birdbath" },
  { value: "perch", label: "Perch" },
  { value: "ground", label: "Ground" },
  { value: "yard", label: "Yard" },
  { value: "driveway", label: "Driveway" },
];

function localInputValue(value: Date): string {
  const offset = value.getTimezoneOffset() * 60_000;
  return new Date(value.getTime() - offset).toISOString().slice(0, 16);
}

function activityHourLabel(hour: number): string {
  return String(hour % 12 || 12) + (hour < 12 ? " AM" : " PM");
}

function durationLabel(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  if (seconds < 60) return String(Math.round(seconds)) + " sec";
  return String(Math.floor(seconds / 60)) + " min " + String(Math.round(seconds % 60)) + " sec";
}

function percentage(value: number | null | undefined): string {
  return value == null ? "—" : value.toFixed(value % 1 === 0 ? 0 : 1) + "%";
}

function hours(value: number | null | undefined): string {
  return value == null ? "Unavailable" : value.toFixed(value < 10 ? 1 : 0) + " h";
}

function rate(value: number | null | undefined): string {
  return value == null ? "—" : value.toFixed(value < 10 ? 2 : 1);
}

function qualityLabel(status: ZoneInsightsZone["metrics"]["data_quality_status"]): string {
  return {
    sufficient: "Sufficient",
    limited_monitoring: "Limited monitoring",
    limited_review_coverage: "Limited review coverage",
    no_confirmed_activity: "No confirmed activity",
    unavailable_exposure: "Exposure unavailable",
    unavailable: "Unavailable",
  }[status];
}

function qualitySortValue(zone: ZoneInsightsZone): number {
  return zone.metrics.data_quality_status === "sufficient"
    && zone.metrics.confirmed_bird_visits_per_monitored_hour != null
    ? zone.metrics.confirmed_bird_visits_per_monitored_hour
    : -1;
}

export function ZoneInsightsPanel({
  sources,
  streams,
  onOpenActivityLibrary,
}: {
  sources: CameraSource[];
  streams: Stream[];
  onOpenActivityLibrary: (filters: ActivityLibraryFilters) => void;
}) {
  const [preset, setPreset] = useState<RangePreset>("last_7_days");
  const [customStart, setCustomStart] = useState(localInputValue(new Date(Date.now() - 7 * 86_400_000)));
  const [customEnd, setCustomEnd] = useState(localInputValue(new Date()));
  const [appliedCustom, setAppliedCustom] = useState<Pick<ZoneInsightsRequest, "start_at" | "end_at"> | null>(null);
  const [lastThirtyRange, setLastThirtyRange] = useState<Pick<ZoneInsightsRequest, "start_at" | "end_at"> | null>(null);
  const [streamId, setStreamId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [zoneType, setZoneType] = useState<ZoneType | "">("");
  const [taxonomyId, setTaxonomyId] = useState("");
  const [taxonomy, setTaxonomy] = useState<TaxonomyLabel[]>([]);
  const [summary, setSummary] = useState<ZoneInsightsSummary | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sort, setSort] = useState<SortKey>("automatic");

  useEffect(() => {
    let active = true;
    void apiClient.getTaxonomyLabels().then((labels) => {
      if (active) setTaxonomy(labels.filter((label) => label.category === "bird" && label.is_species));
    });
    return () => { active = false; };
  }, []);

  const request = useMemo<ZoneInsightsRequest | null>(() => {
    const filters: ZoneInsightsRequest = {
      stream_id: streamId || null,
      source_id: sourceId || null,
      zone_type: zoneType || null,
      confirmed_taxonomy_id: taxonomyId || null,
    };
    if (preset === "last_7_days") return filters;
    if (preset === "last_30_days") return lastThirtyRange ? { ...filters, ...lastThirtyRange } : null;
    return appliedCustom ? { ...filters, ...appliedCustom } : null;
  }, [appliedCustom, lastThirtyRange, preset, sourceId, streamId, taxonomyId, zoneType]);

  useEffect(() => {
    if (!request) return;
    let active = true;
    setIsLoading(true);
    setError(null);
    void apiClient.getZoneInsights(request)
      .then((next) => { if (active) setSummary(next); })
      .catch(() => { if (active) setError("Could not load Zone Insights. Existing activity remains available in the Activity Library."); })
      .finally(() => { if (active) setIsLoading(false); });
    return () => { active = false; };
  }, [request]);

  const choosePreset = (next: RangePreset) => {
    setPreset(next);
    setSummary(null);
    setError(null);
    if (next === "last_30_days") {
      const end = new Date();
      setLastThirtyRange({ start_at: new Date(end.getTime() - 30 * 86_400_000).toISOString(), end_at: end.toISOString() });
    }
    if (next === "custom") setAppliedCustom(null);
  };

  const sortedZones = useMemo(() => {
    if (!summary) return [];
    const zones = [...summary.zones];
    if (sort === "automatic") return zones;
    const score = (zone: ZoneInsightsZone): number => {
      if (sort === "confirmed") return zone.metrics.confirmed_bird_visit_count;
      if (sort === "rate") return qualitySortValue(zone);
      if (sort === "dwell") return zone.metrics.total_confirmed_bird_dwell_seconds;
      if (sort === "richness") return zone.metrics.confirmed_species_richness;
      return zone.metrics.review_coverage_percentage ?? -1;
    };
    return zones.sort((left, right) => score(right) - score(left) || left.zone_name.localeCompare(right.zone_name));
  }, [sort, summary]);

  const trustedRateLeader = summary?.zones.find(
    (zone) => zone.metrics.data_quality_status === "sufficient" && zone.metrics.confirmed_bird_visits_per_monitored_hour != null,
  ) ?? null;

  return (
    <section className="panel zone-insights-panel">
      <div className="section-heading"><div><h2>Zone & feeder insights</h2><span className="meta-text">Compare confirmed bird Visits against only supported monitored time. Suggestions never count as confirmed species.</span></div></div>
      <div className="zone-insights-controls">
        <div className="zone-insights-range" aria-label="Zone Insights range">
          {(["last_7_days", "last_30_days", "custom"] as RangePreset[]).map((option) => <button className={preset === option ? "primary-action" : "secondary-action"} key={option} onClick={() => choosePreset(option)} type="button">{option === "last_7_days" ? "Last 7 days" : option === "last_30_days" ? "Last 30 days" : "Custom range"}</button>)}
        </div>
        {preset === "custom" ? <div className="zone-insights-custom-range"><label>From <input max={customEnd} onChange={(event) => setCustomStart(event.target.value)} type="datetime-local" value={customStart} /></label><label>To <input min={customStart} onChange={(event) => setCustomEnd(event.target.value)} type="datetime-local" value={customEnd} /></label><button className="primary-action" disabled={!customStart || !customEnd || customEnd <= customStart} onClick={() => setAppliedCustom({ start_at: new Date(customStart).toISOString(), end_at: new Date(customEnd).toISOString() })} type="button">Apply</button></div> : null}
        <div className="zone-insights-filter-grid">
          <label>Camera / Source<select onChange={(event) => setSourceId(event.target.value)} value={sourceId}><option value="">All cameras</option>{sources.map((source) => <option key={source.id} value={source.id}>{source.name}</option>)}</select></label>
          <label>Stream<select onChange={(event) => setStreamId(event.target.value)} value={streamId}><option value="">All Streams</option>{streams.filter((stream) => !sourceId || stream.source_id === sourceId).map((stream) => <option key={stream.id} value={stream.id}>{stream.name}</option>)}</select></label>
          <label>Zone type<select onChange={(event) => setZoneType(event.target.value as ZoneType | "")} value={zoneType}><option value="">Applicable Zones</option>{zoneTypes.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}</select></label>
          <label>Confirmed species<select onChange={(event) => setTaxonomyId(event.target.value)} value={taxonomyId}><option value="">All confirmed species</option>{taxonomy.map((label) => <option key={label.id} value={label.id}>{label.display_name}</option>)}</select></label>
        </div>
      </div>
      {isLoading && !summary ? <span className="meta-text">Loading read-only Zone comparisons…</span> : null}
      {error ? <div className="error-panel">{error}</div> : null}
      {!request && preset === "custom" ? <span className="meta-text">Choose a valid start and end time, then apply the range.</span> : null}
      {summary ? <div className="zone-insights-content">
        <div className="zone-insights-period">{new Date(summary.applied_filters.start_at).toLocaleString()} to {new Date(summary.applied_filters.end_at).toLocaleString()}</div>
        <section className="metric-grid zone-insights-metrics">
          <MetricCard label="Confirmed bird Visits" value={summary.aggregate.confirmed_bird_visit_count} detail="reviewed bird activity sessions" />
          <MetricCard label="Healthy monitored hours" value={hours(summary.aggregate.healthy_monitored_hours)} detail="durable healthy exposure" />
          <MetricCard label="Visits / monitored hour" value={rate(summary.aggregate.confirmed_bird_visits_per_monitored_hour)} detail="only when exposure is sufficient" />
          <MetricCard label="Confirmed species" value={summary.aggregate.confirmed_species_richness} detail="reviewed species truth" />
          <MetricCard label="Review coverage" value={percentage(summary.aggregate.review_coverage_percentage)} detail={String(summary.aggregate.unresolved_visit_count) + " unresolved Visits"} />
        </section>
        <div className="zone-insights-context">Based on {hours(summary.aggregate.healthy_monitored_hours)} durable healthy monitored hours across {summary.aggregate.exposure_interval_count} interval{summary.aggregate.exposure_interval_count === 1 ? "" : "s"}, and {percentage(summary.aggregate.review_coverage_percentage)} reviewed activity. {trustedRateLeader ? trustedRateLeader.zone_name + " has the strongest supported rate at " + rate(trustedRateLeader.metrics.confirmed_bird_visits_per_monitored_hour) + " Visits/hour." : "Rate ranking is withheld until monitoring and review coverage are sufficient."}</div>
        <div className="notice-panel zone-insights-honesty"><strong>Visits are activity sessions, not estimates of unique birds.</strong><span>A bird may create more than one Visit if it leaves and returns. Visit totals do not represent unique individuals.</span></div>
        {summary.zone_count === 0 ? <EmptyState title="No applicable Zones match this range" description="Choose a wider range or inspect captured activity in the Activity Library." /> : <>
          <div className="zone-insights-sort"><label>Sort comparison<select onChange={(event) => setSort(event.target.value as SortKey)} value={sort}><option value="automatic">Best supported rate, then Visits</option><option value="confirmed">Confirmed Visits</option><option value="rate">Visits per monitored hour</option><option value="dwell">Total dwell time</option><option value="richness">Species richness</option><option value="review">Review coverage</option></select></label></div>
          <section className="zone-insights-table" aria-label="Zone comparison">{sortedZones.map((zone) => <article className="zone-insights-row" key={zone.zone_id}>
            <div className="zone-insights-zone"><strong>{zone.zone_name}</strong><span>{formatLabel(zone.zone_type)} · {zone.stream_name}</span><span className={"zone-insights-quality quality-" + zone.metrics.data_quality_status}>{qualityLabel(zone.metrics.data_quality_status)}</span></div>
            <div><span>Healthy time</span><strong>{hours(zone.metrics.healthy_monitored_hours)}</strong></div>
            <div><span>Confirmed Visits</span><button className="text-action" onClick={() => onOpenActivityLibrary(zone.confirmed_activity_drilldown.filters)} type="button">{zone.metrics.confirmed_bird_visit_count}</button></div>
            <div><span>Visits / hour</span><strong>{rate(zone.metrics.confirmed_bird_visits_per_monitored_hour)}</strong></div>
            <div><span>Total dwell</span><strong>{durationLabel(zone.metrics.total_confirmed_bird_dwell_seconds)}</strong></div>
            <div><span>Median Visit</span><strong>{durationLabel(zone.metrics.median_confirmed_bird_duration_seconds)}</strong></div>
            <div><span>Species richness</span><strong>{zone.metrics.confirmed_species_richness}</strong></div>
            <div><span>Review coverage</span><strong>{percentage(zone.metrics.review_coverage_percentage)}</strong></div>
            <div><span>False-positive</span><strong>{percentage(zone.metrics.reviewed_false_positive_percentage)}</strong></div>
            <div className="zone-insights-row-links"><button className="text-action" onClick={() => onOpenActivityLibrary(zone.unresolved_activity_drilldown.filters)} type="button">{zone.metrics.unresolved_visit_count} unresolved</button><button className="text-action" onClick={() => onOpenActivityLibrary(zone.reviewed_blank_drilldown.filters)} type="button">{zone.metrics.reviewed_blank_count} blank</button><button className="text-action" onClick={() => onOpenActivityLibrary(zone.reviewed_non_bird_drilldown.filters)} type="button">{zone.metrics.reviewed_non_bird_count} non-bird</button></div>
            {zone.species_composition.length ? <div className="zone-insights-species">{zone.species_composition.map((species) => <button className="secondary-action" key={species.taxonomy_id} onClick={() => onOpenActivityLibrary(species.drilldown.filters)} type="button">{species.display_name}: {species.visit_count} ({percentage(species.percentage)})</button>)}</div> : <span className="meta-text">No confirmed reviewed species for this Zone.</span>}
            {zone.metrics.warnings.length ? <ul className="zone-insights-warnings">{zone.metrics.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul> : null}
          </article>)}</section>
        </>}
        <section className="zone-insights-charts">
          <div className="panel"><div className="section-heading"><div><h3>Confirmed Visits by day</h3><span className="meta-text">Open a day to audit its reviewed activity.</span></div></div><div className="zone-insights-daily">{summary.daily_trend.map((bucket) => <button key={bucket.local_date} onClick={() => onOpenActivityLibrary(bucket.drilldown.filters)} type="button"><span>{bucket.local_date}</span><strong>{bucket.confirmed_bird_visit_count}</strong></button>)}</div></div>
          <div className="panel"><div className="section-heading"><div><h3>Confirmed Visits by hour</h3><span className="meta-text">{summary.busiest_supported_hour == null ? "More confirmed activity is needed before naming a busiest time." : "Busiest supported hour: " + activityHourLabel(summary.busiest_supported_hour) + "."}</span></div></div><div className="zone-insights-hours">{summary.activity_by_hour.map((bucket) => <span key={bucket.hour}>{activityHourLabel(bucket.hour)} <strong>{bucket.confirmed_bird_visit_count}</strong></span>)}</div></div>
        </section>
        <ul className="zone-insights-warnings">{summary.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
      </div> : null}
    </section>
  );
}
