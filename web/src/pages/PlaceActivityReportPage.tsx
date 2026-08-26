import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type {
  CameraSource,
  PlaceActivityReportCoverageGap,
  PlaceActivityReportHourActivity,
  PlaceActivityReportOverallChangeStatus,
  PlaceActivityReportRequest,
  PlaceActivityReportResponse,
  PlaceActivityReportTaxonEntry,
  PlaceActivityReportZoneActivity,
  PlaceBiodiversitySummaryResponse,
  PlaceFeature,
  PlaceFeatureChangeEvent,
  PlaceFeatureDetail,
  PlaceHabitatFact,
  PlacePhenologyObservation,
} from "../api/types";
import { BiodiversitySummaryCard } from "../components/BiodiversitySummaryCard";
import { EmptyState } from "../components/EmptyState";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { SourceActivityList } from "../components/SourceActivityList";
import { StatusPill } from "../components/StatusPill";
import {
  changeStatusBadge,
  formatDateTime,
  historicalStatusBadge,
  phenologyDateRange,
  regularityNarrativeBadge,
  seasonalPatternNote,
} from "../utils";

/**
 * Everyday Discovery / Product Experience v2 (Phase G): the secondary
 * "explore the full picture" surface over the existing, already-complete
 * Place Activity Report backend (`POST /api/analytics/place-activity-
 * report`, see docs/place-activity-report-contract.md). Today's dashboard
 * (`TodayReportPanel`) reads a bounded sliver of this same response --
 * today only, one `busiest_zone` winner, `digest`'s top-5 highlights. This
 * page reads the fuller underlying facts (`taxa`, `activity_by_zone`,
 * `activity_by_hour`, `coverage`, `historical_baseline`) directly, over a
 * period the reviewer chooses, instead of `digest` -- `digest`'s own
 * composed sentences ("...yet today") are correct only for a literal
 * today-scoped request, so reusing them here for an arbitrary period (for
 * example "last 30 days") would misrepresent the period. This component
 * never re-derives truth precedence, wildlife eligibility, or Visit
 * counts itself; it only presents facts the backend already resolved.
 */

interface PlaceActivityReportPageProps {
  sources: CameraSource[];
  onOpenVisit: (visitId: string) => void;
  /** With no `label`, opens Bird Log's overview; with one, deep-links
   * straight to that species' own Bird Log history (mirrors the identical
   * pattern App.tsx already wires for Yard & Camera Map). */
  onOpenBirdLog: (label?: string) => void;
}

type PlaceReportPreset = "today" | "last_7_days" | "last_30_days" | "this_year" | "custom";
type BoundedPreset = Exclude<PlaceReportPreset, "custom">;

const PRESET_OPTIONS: Array<{ value: PlaceReportPreset; label: string }> = [
  { value: "today", label: "Today" },
  { value: "last_7_days", label: "Last 7 days" },
  { value: "last_30_days", label: "Last 30 days" },
  { value: "this_year", label: "This year" },
  { value: "custom", label: "Custom range" },
];

// Matches the request contract's own cap ("span capped at 366 days" --
// docs/place-activity-report-contract.md's "Integration" section).
const MAX_PERIOD_DAYS = 366;

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

// Mirrors DashboardPage.tsx's own todayLocalRange()/local-day-boundary
// pattern (see that file's comment): a real local Date, mutated via
// setHours/setDate, never millisecond arithmetic that could drift across a
// DST transition.
function localMidnight(base: Date, dayOffset = 0): Date {
  const value = new Date(base);
  value.setHours(0, 0, 0, 0);
  value.setDate(value.getDate() + dayOffset);
  return value;
}

function localDateInputValue(value = new Date()): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

// `new Date("YYYY-MM-DD")` parses the bare date as UTC midnight, not local
// midnight -- exactly the drift the local-midnight helpers above exist to
// avoid. Parses the <input type="date"> value's own calendar components
// directly instead of handing the string to the Date constructor.
function parseLocalDateInput(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  const [, year, month, day] = match;
  return new Date(Number(year), Number(month) - 1, Number(day));
}

function presetRange(preset: BoundedPreset, now: Date): PlaceActivityReportRequest {
  const end_at = localMidnight(now, 1).toISOString();
  switch (preset) {
    case "today":
      return { start_at: localMidnight(now).toISOString(), end_at };
    case "last_7_days":
      return { start_at: localMidnight(now, -6).toISOString(), end_at };
    case "last_30_days":
      return { start_at: localMidnight(now, -29).toISOString(), end_at };
    case "this_year":
      return { start_at: localMidnight(new Date(now.getFullYear(), 0, 1)).toISOString(), end_at };
    default:
      return { start_at: localMidnight(now).toISOString(), end_at };
  }
}

function resolveCustomRange(startDate: string, endDate: string): PlaceActivityReportRequest | null {
  const start = parseLocalDateInput(startDate);
  const end = parseLocalDateInput(endDate);
  if (!start || !end || end < start) return null;
  return {
    start_at: localMidnight(start).toISOString(),
    // Exclusive upper bound (the request contract is "[start_at, end_at)"),
    // so the chosen end date's own full local day is included.
    end_at: localMidnight(end, 1).toISOString(),
  };
}

function customRangeSpanDays(startDate: string, endDate: string): number | null {
  const range = resolveCustomRange(startDate, endDate);
  if (!range) return null;
  return Math.round((new Date(range.end_at).getTime() - new Date(range.start_at).getTime()) / 86_400_000);
}

function formatHour12(hour: number): { label: string; period: "AM" | "PM" } {
  const period = hour < 12 ? "AM" : "PM";
  const twelveHour = hour % 12 === 0 ? 12 : hour % 12;
  return { label: String(twelveHour), period };
}

// Mirrors TodayReportPanel.tsx's identical helper -- a single hour bucket
// shown as its own honest span ("7-8 AM"), never a fabricated wider "peak
// window."
function formatHourRange(hour: number): string {
  const start = formatHour12(hour);
  const end = formatHour12((hour + 1) % 24);
  if (start.period === end.period) {
    return `${start.label}–${end.label} ${end.period}`;
  }
  return `${start.label} ${start.period}–${end.label} ${end.period}`;
}

function formatHourShort(hour: number): string {
  const { label, period } = formatHour12(hour);
  return `${label}${period}`;
}

function formatMonitoredHours(seconds: number): string {
  const hoursValue = seconds / 3600;
  return `${hoursValue < 10 ? hoursValue.toFixed(1) : Math.round(hoursValue)} h`;
}

function formatGapRange(gap: PlaceActivityReportCoverageGap): string {
  return `${formatDateTime(gap.start_at)} – ${formatDateTime(gap.end_at)}`;
}

// The single busiest hour, matching TodayReportPanel.tsx's identical rule:
// the earliest hour wins a tie, so the result is deterministic.
function busiestHour(activity: PlaceActivityReportHourActivity[]): PlaceActivityReportHourActivity | null {
  let best: PlaceActivityReportHourActivity | null = null;
  for (const entry of activity) {
    if (entry.wildlife_visit_count > 0 && (!best || entry.wildlife_visit_count > best.wildlife_visit_count)) {
      best = entry;
    }
  }
  return best;
}

function isSameZone(
  zone: PlaceActivityReportZoneActivity,
  other: PlaceActivityReportZoneActivity | null | undefined,
): boolean {
  if (!other) return false;
  if (zone.zone_id != null || other.zone_id != null) return zone.zone_id === other.zone_id;
  return zone.zone_name === other.zone_name;
}

function sortedTaxa(taxa: PlaceActivityReportTaxonEntry[]): PlaceActivityReportTaxonEntry[] {
  return [...taxa].sort(
    (a, b) =>
      b.confirmed_visit_count - a.confirmed_visit_count ||
      b.provisional_visit_count - a.provisional_visit_count ||
      b.total_visit_count - a.total_visit_count ||
      a.display_name.localeCompare(b.display_name),
  );
}

// Composes the identical "Backyard feeder · 7-8 AM" wording convention
// documented for the digest's own `pattern_note` (see "Today integration"
// in docs/place-activity-report-contract.md), but over every taxon in the
// full report, not just the digest's bounded top-5 -- and, per this
// milestone's own brief, discloses the honest "not enough support" case
// rather than silently omitting the row when `most_active_zone`/`most_
// active_hour` are null but this taxon does have some reviewed history.
function taxonPatternNote(taxon: PlaceActivityReportTaxonEntry): string | null {
  const zone = taxon.most_active_zone;
  const hour = taxon.most_active_hour;
  if (zone && hour) {
    return `Usually at ${zone.display_name} · around ${formatHourRange(hour.local_hour)}`;
  }
  if (zone) {
    return `Usually recorded at ${zone.display_name}`;
  }
  if (hour) {
    return `Usually recorded around ${formatHourRange(hour.local_hour)}`;
  }
  if (taxon.zone_activity.length > 0 || taxon.hour_activity.length > 0) {
    return "Not enough reviewed activity yet to show a usual time or place";
  }
  return null;
}

// Place-wide counterpart of utils.ts's `changeStatusBadge` -- same
// deliberately non-judgmental "quiet" tone for both directions, but over
// `PlaceActivityReportOverallChangeStatus`'s own distinct status values
// (an aggregate across all confirmed wildlife, not one taxon).
function overallChangeBadge(
  status: PlaceActivityReportOverallChangeStatus,
): { label: string; tone: "good" | "quiet" } | null {
  switch (status.status) {
    case "more_activity_recorded":
      return { label: "More activity recorded recently", tone: "quiet" };
    case "less_activity_recorded":
      return { label: "Less activity recorded recently", tone: "quiet" };
    default:
      return null;
  }
}

function periodMaturityInfo(
  maturity: PlaceActivityReportResponse["maturity"],
): { label: string; tone: "good" | "quiet"; detail: string } {
  switch (maturity) {
    case "usable":
      return {
        label: "Enough monitoring to trust this period",
        tone: "good",
        detail: "There was enough active monitoring in this period to treat the pattern below as reasonably reliable.",
      };
    case "sparse":
      return {
        label: "Limited monitoring this period",
        tone: "quiet",
        detail: "Only a small part of this period was actively monitored, so this pattern may not be reliable yet.",
      };
    case "no_data":
    default:
      return {
        label: "Not enough monitoring yet",
        tone: "quiet",
        detail: "MockingBird hasn't recorded any monitoring for this period yet, so there isn't enough here to show a pattern.",
      };
  }
}

function baselineMaturityInfo(
  maturity: PlaceActivityReportResponse["historical_baseline"]["maturity"],
): { label: string; tone: "good" | "quiet"; detail: string } {
  switch (maturity) {
    case "established":
      return {
        label: "Enough history built up",
        tone: "good",
        detail: "MockingBird has enough history to reliably tell new visitors from regulars.",
      };
    case "developing":
      return {
        label: "Still building history",
        tone: "quiet",
        detail: "MockingBird is still building up enough history to confidently say what's new or regular here.",
      };
    case "insufficient":
    default:
      return {
        label: "Not enough history yet",
        tone: "quiet",
        detail: "Not enough monitoring history yet to say what's new or regular here.",
      };
  }
}

function HourActivityChart({ activity }: { activity: PlaceActivityReportHourActivity[] }) {
  const maxCount = activity.reduce((max, entry) => Math.max(max, entry.wildlife_visit_count), 0);
  const busiest = busiestHour(activity);
  return (
    <div>
      <div className="place-report-hour-chart" aria-label="Wildlife activity by local hour">
        {activity.map((entry) => {
          const heightPct =
            maxCount > 0
              ? Math.max((entry.wildlife_visit_count / maxCount) * 100, entry.wildlife_visit_count > 0 ? 8 : 3)
              : 3;
          const isBusiest = busiest != null && entry.hour === busiest.hour && entry.wildlife_visit_count > 0;
          return (
            <div
              className={isBusiest ? "place-report-hour-bar place-report-hour-bar-busiest" : "place-report-hour-bar"}
              key={entry.hour}
              title={`${formatHourRange(entry.hour)}: ${plural(entry.wildlife_visit_count, "visit")}`}
            >
              <i style={{ height: `${heightPct}%` }} />
            </div>
          );
        })}
      </div>
      <div className="place-report-hour-labels" aria-hidden="true">
        {activity.map((entry) => (
          <span key={entry.hour}>{entry.hour % 6 === 0 ? formatHourShort(entry.hour) : ""}</span>
        ))}
      </div>
      {busiest ? (
        <p className="meta-text">
          Most active around {formatHourRange(busiest.hour)} ({plural(busiest.wildlife_visit_count, "visit")}).
        </p>
      ) : (
        <p className="meta-text">Not enough activity yet to show a most-active time.</p>
      )}
    </div>
  );
}

function ZoneActivityList({
  zones,
  busiestZone,
}: {
  zones: PlaceActivityReportZoneActivity[];
  busiestZone: PlaceActivityReportZoneActivity | null | undefined;
}) {
  const sorted = [...zones].sort((a, b) => b.wildlife_visit_count - a.wildlife_visit_count);
  const maxCount = sorted.reduce((max, zone) => Math.max(max, zone.wildlife_visit_count), 0);
  return (
    <div className="bar-list" aria-label="Wildlife activity by area">
      {sorted.map((zone) => (
        <div className="bar-row" key={zone.zone_id ?? zone.zone_name}>
          <span>
            {zone.zone_name}
            {isSameZone(zone, busiestZone) ? <StatusPill label="Busiest" tone="good" /> : null}
          </span>
          <div>
            <i style={{ width: `${maxCount > 0 ? Math.max((zone.wildlife_visit_count / maxCount) * 100, 4) : 4}%` }} />
            <strong>{plural(zone.wildlife_visit_count, "visit")}</strong>
          </div>
        </div>
      ))}
    </div>
  );
}

// Multi-Camera Place Experience v2: `SourceActivityList` moved to
// `../components/SourceActivityList.tsx` (imported above) so
// TodayReportPanel.tsx can reuse the identical presentation instead of a
// second, drifting per-camera bar list.

// Mirrors BirdLogPage.tsx's private JournalThumbnail fallback behavior
// (an honest "no image"/"heard" state, reusing its exact `.journal-
// thumbnail-fallback`/`.journal-thumbnail-audio` styling) over this
// report's own `representative_evidence` field instead of Bird Log's.
function TaxonThumbnail({ taxon }: { taxon: PlaceActivityReportTaxonEntry }) {
  const [failed, setFailed] = useState(false);
  const evidence = taxon.representative_evidence?.evidence;
  useEffect(() => setFailed(false), [evidence?.media_asset_id]);
  if (!evidence || failed) {
    return <div className="journal-thumbnail-fallback">No image yet</div>;
  }
  if (evidence.content_type.startsWith("audio/")) {
    return (
      <div className="journal-thumbnail-fallback journal-thumbnail-audio" aria-label={`${taxon.display_name}, heard`}>
        🔊 Heard
      </div>
    );
  }
  return (
    <img
      alt={`${taxon.display_name}, reviewed observation`}
      loading="lazy"
      onError={() => setFailed(true)}
      src={`${apiClient.baseUrl}${evidence.preview_url}`}
    />
  );
}

function TaxonCard({
  taxon,
  onOpenVisit,
  onOpenBirdLog,
}: {
  taxon: PlaceActivityReportTaxonEntry;
  onOpenVisit: (visitId: string) => void;
  onOpenBirdLog: (label?: string) => void;
}) {
  const isConfirmed = taxon.confirmed_visit_count > 0;
  const historicalBadge = historicalStatusBadge(taxon.historical_status?.status);
  const changeBadge = changeStatusBadge(taxon.change_status);
  const regularityBadge = regularityNarrativeBadge(taxon.regularity_narrative);
  const seasonalNote = seasonalPatternNote(taxon.seasonal_pattern);
  const patternNote = taxonPatternNote(taxon);
  // Place / Yard Intelligence v2, Phase 11: association language only,
  // shown compactly (one line, first match) -- never a chart wall of every
  // recorded phenomenon.
  const habitatAssociation = (taxon.habitat_associations ?? []).find(
    (association) => association.status !== "no_clear_association",
  );
  // Environmental Context v2: identical compact, first-match convention as
  // habitatAssociation above -- see docs/environmental-context-v2-
  // contract.md "Phase 6/16".
  const weatherAssociation = (taxon.weather_associations ?? []).find(
    (association) => association.status !== "no_clear_association",
  );
  const visitId = taxon.representative_evidence?.visit_id;
  return (
    <article className="journal-label-card">
      {visitId ? (
        <button className="journal-label-image" onClick={() => onOpenVisit(visitId)} type="button">
          <TaxonThumbnail taxon={taxon} />
        </button>
      ) : (
        <div className="journal-label-image">
          <TaxonThumbnail taxon={taxon} />
        </div>
      )}
      <div className="journal-label-card-body">
        <div className="section-heading">
          <div>
            <h2>{taxon.display_name}</h2>
            {isConfirmed ? (
              <span className="meta-text">
                {plural(taxon.confirmed_visit_count, "confirmed visit")}
                {taxon.provisional_visit_count > 0 ? ` · +${taxon.provisional_visit_count} likely` : ""}
              </span>
            ) : (
              <span className="meta-text">{plural(taxon.provisional_visit_count, "likely visit")} · not yet confirmed</span>
            )}
            {historicalBadge ? <StatusPill label={historicalBadge.label} tone={historicalBadge.tone} /> : null}
            {changeBadge ? <StatusPill label={changeBadge.label} tone={changeBadge.tone} /> : null}
            {regularityBadge ? <StatusPill label={regularityBadge.label} tone={regularityBadge.tone} /> : null}
          </div>
        </div>
        <div className="journal-label-facts">
          <span>First: <strong>{formatDateTime(taxon.first_activity_at)}</strong></span>
          <span>Latest: <strong>{formatDateTime(taxon.last_activity_at)}</strong></span>
        </div>
        {patternNote ? <span className="meta-text">{patternNote}</span> : null}
        {seasonalNote ? <span className="meta-text">{seasonalNote}</span> : null}
        {habitatAssociation ? (
          <span className="meta-text">
            {habitatAssociation.status === "more_common_under_condition" ? "Observed more often" : "Observed less often"}
            {" while "}
            {habitatAssociation.phenomenon} was current ({habitatAssociation.subject_label})
          </span>
        ) : null}
        {weatherAssociation ? (
          <span className="meta-text">
            {weatherAssociation.status === "more_common_under_condition" ? "Observed more often" : "Observed less often"}
            {" during "}
            {weatherAssociation.condition_label}
          </span>
        ) : null}
        {isConfirmed ? (
          <button className="text-action" onClick={() => onOpenBirdLog(taxon.label)} type="button">
            View in Bird Log
          </button>
        ) : null}
      </div>
    </article>
  );
}

const FEATURE_TYPE_DISPLAY_NAMES: Record<string, string> = {
  feeder: "Feeder",
  water: "Water",
  nest_box: "Nest box",
  vegetation_patch: "Vegetation patch",
  structure: "Structure",
  habitat_area: "Habitat area",
  other: "Feature",
};

const CHANGE_EVENT_TYPE_DISPLAY_NAMES: Record<string, string> = {
  added: "Added",
  removed: "Removed",
  moved: "Moved",
  modified: "Modified",
  replenished: "Replenished",
  food_changed: "Food changed",
  vegetation_changed: "Vegetation changed",
  other: "Changed",
};

/** Plain-language, association-only wording for one change event's
 * before/after comparison -- never a causal claim, and never a raw
 * percentage from a small count (see docs/place-features-habitat-change-
 * v2-contract.md "Before/after analysis"). */
function featureAssociationSentence(association: {
  maturity: string;
  status?: string | null;
  window_days?: number | null;
}): string {
  if (association.maturity === "too_soon") {
    return "Too soon to tell -- not enough time has passed since this change yet.";
  }
  if (association.maturity === "insufficient_coverage") {
    return "Not enough comparable monitoring yet to evaluate this change.";
  }
  const windowText = association.window_days ? `the ${association.window_days}-day windows` : "the monitored windows";
  if (association.status === "more_common_under_condition") {
    return `Confirmed wildlife activity was higher in ${windowText} after this change than before.`;
  }
  if (association.status === "less_common_under_condition") {
    return `Confirmed wildlife activity was lower in ${windowText} after this change than before.`;
  }
  return `Activity looked similar in ${windowText} before and after this change.`;
}

export function PlaceActivityReportPage({ sources, onOpenVisit, onOpenBirdLog }: PlaceActivityReportPageProps) {
  const [preset, setPreset] = useState<PlaceReportPreset>("last_30_days");
  const [customStartDate, setCustomStartDate] = useState(localDateInputValue(localMidnight(new Date(), -29)));
  const [customEndDate, setCustomEndDate] = useState(localDateInputValue());
  const [appliedCustomRange, setAppliedCustomRange] = useState<PlaceActivityReportRequest | null>(null);
  // Camera / Source + Multi-Camera Maturity v1, Phase N: an empty selection
  // means the unfiltered whole-Place report -- mirrors the backend's own
  // "omitted/empty means every Source" contract for `source_ids`.
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [report, setReport] = useState<PlaceActivityReportResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Habitat & Phenology Foundation v1: a read-only, deliberately period-
  // independent fetch -- habitat facts are durable, and the *full*
  // phenology history (not just this period's slice) is shown so history
  // stays honestly historical rather than silently reappearing/
  // disappearing as the period picker changes. See docs/habitat-phenology-
  // foundation-v1-contract.md "Frontend surface". Editing lives on the
  // Dashboard (Today) card; this page only displays.
  const [habitatFacts, setHabitatFacts] = useState<PlaceHabitatFact[]>([]);
  const [phenologyObservations, setPhenologyObservations] = useState<PlacePhenologyObservation[]>([]);

  useEffect(() => {
    let active = true;
    void Promise.all([
      apiClient.getPlaceHabitatFacts().catch(() => []),
      apiClient.getPlacePhenologyObservations().catch(() => []),
    ]).then(([facts, observations]) => {
      if (active) {
        setHabitatFacts(facts);
        setPhenologyObservations(observations);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  // Place Features & Habitat Change v2: another read-only, period-
  // independent fetch, same reasoning as habitat/phenology above -- see
  // docs/place-features-habitat-change-v2-contract.md "Product surfaces".
  // Editing lives on the Dashboard (Today) card; this page only displays,
  // plus lets a reviewer expand one Feature at a time to lazily load its
  // own before/after insight (a heavier per-Feature computation, never
  // fetched for every Feature up front).
  const [placeFeatures, setPlaceFeatures] = useState<PlaceFeature[]>([]);
  const [featureChangeEvents, setFeatureChangeEvents] = useState<PlaceFeatureChangeEvent[]>([]);
  const [expandedFeatureId, setExpandedFeatureId] = useState<string | null>(null);
  const [expandedFeatureDetail, setExpandedFeatureDetail] = useState<PlaceFeatureDetail | null>(null);
  const [isLoadingFeatureDetail, setIsLoadingFeatureDetail] = useState(false);

  useEffect(() => {
    let active = true;
    void Promise.all([
      apiClient.getPlaceFeatures().catch(() => []),
      apiClient.getPlaceFeatureChangeEvents().catch(() => []),
    ]).then(([features, events]) => {
      if (active) {
        setPlaceFeatures(features);
        setFeatureChangeEvents(events);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const toggleFeatureDetail = (featureId: string) => {
    if (expandedFeatureId === featureId) {
      setExpandedFeatureId(null);
      setExpandedFeatureDetail(null);
      return;
    }
    setExpandedFeatureId(featureId);
    setExpandedFeatureDetail(null);
    setIsLoadingFeatureDetail(true);
    void apiClient
      .getPlaceFeatureDetail(featureId)
      .catch(() => null)
      .then((detail) => {
        setExpandedFeatureDetail(detail);
        setIsLoadingFeatureDetail(false);
      });
  };

  // Biodiversity & Place Intelligence v1: another read-only, period-
  // independent fetch, same reasoning as habitat/phenology above -- an
  // all-time Place roster, not scoped to whatever period is selected
  // above. See docs/biodiversity-place-intelligence-v1-contract.md.
  const [biodiversitySummary, setBiodiversitySummary] = useState<PlaceBiodiversitySummaryResponse | null>(
    null,
  );

  useEffect(() => {
    let active = true;
    void apiClient
      .getPlaceBiodiversitySummary()
      .catch(() => null)
      .then((next) => {
        if (active) setBiodiversitySummary(next);
      });
    return () => {
      active = false;
    };
  }, []);

  function toggleSourceId(sourceId: string) {
    setSelectedSourceIds((current) =>
      current.includes(sourceId)
        ? current.filter((selected) => selected !== sourceId)
        : [...current, sourceId],
    );
  }

  const range = useMemo<PlaceActivityReportRequest | null>(() => {
    const period = preset === "custom" ? appliedCustomRange : presetRange(preset, new Date());
    if (!period) return null;
    return selectedSourceIds.length > 0 ? { ...period, source_ids: selectedSourceIds } : period;
  }, [preset, appliedCustomRange, selectedSourceIds]);

  useEffect(() => {
    if (!range) return;
    let active = true;
    setIsLoading(true);
    setError(null);
    void apiClient
      .getPlaceActivityReport(range)
      .then((next) => {
        if (active) setReport(next);
      })
      .catch(() => {
        if (active) {
          setError("Could not load the place report right now. Your camera data and history are unaffected.");
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [range]);

  const customSpanDays = customRangeSpanDays(customStartDate, customEndDate);
  const customSpanTooLong = customSpanDays != null && customSpanDays > MAX_PERIOD_DAYS;
  const customRangeIsValid = customSpanDays != null && customSpanDays > 0 && !customSpanTooLong;

  const hasWildlife = (report?.wildlife_visit_count ?? 0) > 0;
  const taxaList = report ? sortedTaxa(report.taxa) : [];
  const overallBadge = report ? overallChangeBadge(report.overall_change_status) : null;

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Explore the full picture"
        title="Place Report"
        description="The same wildlife report Today uses, over a period you choose -- when it's most active, which areas see the most activity, what's been seen where, and whether there's enough monitoring to trust the pattern."
        actions={
          <button className="secondary-action" onClick={() => onOpenBirdLog()} type="button">
            Open Bird Log
          </button>
        }
      />

      <section className="panel journal-filter-panel" aria-label="Choose a period">
        <label>
          Period
          <select
            onChange={(event) => {
              const next = event.target.value as PlaceReportPreset;
              setPreset(next);
              if (next === "custom") {
                setAppliedCustomRange(null);
              }
            }}
            value={preset}
          >
            {PRESET_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        {preset === "custom" ? (
          <>
            <label>
              From
              <input max={customEndDate} onChange={(event) => setCustomStartDate(event.target.value)} type="date" value={customStartDate} />
            </label>
            <label>
              To
              <input min={customStartDate} onChange={(event) => setCustomEndDate(event.target.value)} type="date" value={customEndDate} />
            </label>
            <button
              className="primary-action"
              disabled={!customRangeIsValid}
              onClick={() => setAppliedCustomRange(resolveCustomRange(customStartDate, customEndDate))}
              type="button"
            >
              Apply
            </button>
            {customSpanTooLong ? <span className="meta-text">Choose a range of 366 days or less.</span> : null}
          </>
        ) : null}
        {report ? (
          <span className="meta-text">
            {new Date(report.period_start_at).toLocaleDateString()} – {new Date(report.period_end_at).toLocaleDateString()}
            {" · "}Updated {formatDateTime(report.generated_at)}
          </span>
        ) : null}
      </section>

      {/* A separate panel, not nested inside .journal-filter-panel above --
          that section's own `input`/`select` styling (sized/bordered for
          its text-style period controls) would otherwise visually distort
          these ordinary checkboxes (`.checkbox-row`'s own reset loses that
          specific cascade). Still directly beneath the period picker, so it
          reads as the same "choose what this report covers" filter area. */}
      {sources.length > 0 ? (
        <section className="panel place-report-source-filter" aria-label="Filter by camera">
          <fieldset>
            <legend>Cameras / Sources</legend>
            <div className="retention-checkbox-grid">
              {sources.map((source) => (
                <label className="checkbox-row" key={source.id}>
                  <input
                    checked={selectedSourceIds.includes(source.id)}
                    onChange={() => toggleSourceId(source.id)}
                    type="checkbox"
                  />
                  {source.name}
                </label>
              ))}
            </div>
            <span className="meta-text">
              {selectedSourceIds.length === 0
                ? "No cameras selected -- every camera is included."
                : `Limited to ${selectedSourceIds.length} of ${sources.length} camera${sources.length === 1 ? "" : "s"}.`}
            </span>
          </fieldset>
        </section>
      ) : null}

      {error ? (
        report ? (
          <div className="dashboard-refresh-notice" role="status">
            <span>{error}</span>
          </div>
        ) : (
          <div className="error-panel">
            <strong>Could not load the place report.</strong>
            <span>{error}</span>
          </div>
        )
      ) : null}

      {isLoading && !report ? <div className="panel">Loading the place report…</div> : null}

      {report ? (
        <>
          {report.warnings.length > 0 ? (
            <div className="notice-panel" role="status">
              <strong>{report.warnings[0]}</strong>
              {report.warnings.length > 1 ? <span>+{report.warnings.length - 1} more note{report.warnings.length - 1 === 1 ? "" : "s"}</span> : null}
            </div>
          ) : null}

          <section className="metric-grid">
            <MetricCard label="Wildlife visits" value={report.wildlife_visit_count} detail="confirmed + likely" />
            <MetricCard label="Confirmed" value={report.confirmed_wildlife_visit_count} detail="reviewed truth" />
            <MetricCard
              label={report.distinct_species_count > 0 ? "Species seen" : "Kinds of wildlife seen"}
              value={report.distinct_species_count > 0 ? report.distinct_species_count : report.distinct_taxa_count}
            />
            <MetricCard
              label="Worth reviewing"
              value={report.provisional_wildlife_visit_count + report.unresolved_visit_count}
              detail="not yet confirmed"
            />
          </section>
          {report.first_activity_at ? <p className="meta-text">First activity {formatDateTime(report.first_activity_at)}</p> : null}
          {report.last_activity_at ? <p className="meta-text">Last activity {formatDateTime(report.last_activity_at)}</p> : null}

          <div className="split-grid">
            <section className="panel" aria-label="Monitoring coverage for this period">
              <div className="section-heading">
                <div>
                  <h2>How much of this period was monitored</h2>
                </div>
                <StatusPill label={periodMaturityInfo(report.maturity).label} tone={periodMaturityInfo(report.maturity).tone} />
              </div>
              <p className="meta-text">{periodMaturityInfo(report.maturity).detail}</p>
              {report.coverage.coverage_ratio != null ? (
                <p className="meta-text">
                  About {Math.round(report.coverage.coverage_ratio * 100)}% of this period was actively monitored
                  {report.coverage.monitored_seconds != null ? ` (roughly ${formatMonitoredHours(report.coverage.monitored_seconds)}).` : "."}
                </p>
              ) : null}
              {report.coverage.gaps.length > 0 ? (
                <div className="place-report-gap-list">
                  <span className="meta-text">
                    {plural(report.coverage.gaps.length, "monitoring gap")} recorded{report.coverage.gaps_truncated ? " (showing the earliest)" : ""}:
                  </span>
                  {report.coverage.gaps.slice(0, 3).map((gap) => (
                    <span className="meta-text" key={gap.start_at}>{formatGapRange(gap)}</span>
                  ))}
                  {report.coverage.gaps.length > 3 ? (
                    <span className="meta-text">+{report.coverage.gaps.length - 3} more gap{report.coverage.gaps.length - 3 === 1 ? "" : "s"}</span>
                  ) : null}
                </div>
              ) : null}
            </section>

            <section className="panel" aria-label="Historical depth for new/regular comparisons">
              <div className="section-heading">
                <div>
                  <h2>How much history MockingBird has</h2>
                  <span className="meta-text">A separate, longer-running measure from the coverage above</span>
                </div>
                <StatusPill
                  label={baselineMaturityInfo(report.historical_baseline.maturity).label}
                  tone={baselineMaturityInfo(report.historical_baseline.maturity).tone}
                />
              </div>
              <p className="meta-text">{baselineMaturityInfo(report.historical_baseline.maturity).detail}</p>
              <p className="meta-text">
                Built from {plural(report.historical_baseline.usable_day_count, "well-monitored day")} of history
                {report.historical_baseline.distinct_taxa_count > 0
                  ? ` across ${plural(report.historical_baseline.distinct_taxa_count, "kind of wildlife")}`
                  : ""}.
              </p>
              {overallBadge ? (
                <div className="section-heading">
                  <span className="meta-text">
                    Recent: {report.overall_change_status.recent_presence_days} of {report.overall_change_status.recent_usable_day_count} usable monitored days
                    {" · "}
                    Reference: {report.overall_change_status.reference_presence_days} of {report.overall_change_status.reference_usable_day_count} usable monitored days
                  </span>
                  <StatusPill label={overallBadge.label} tone={overallBadge.tone} />
                </div>
              ) : null}
            </section>
          </div>

          {hasWildlife ? (
            <>
              <section className="panel" aria-label="Wildlife activity by hour of day">
                <div className="section-heading">
                  <div>
                    <h2>When wildlife is most active</h2>
                    <span className="meta-text">Local hours, this period</span>
                  </div>
                </div>
                <HourActivityChart activity={report.activity_by_hour} />
              </section>

              <section className="panel" aria-label="Wildlife activity by area">
                <div className="section-heading">
                  <div>
                    <h2>Where wildlife is most active</h2>
                    <span className="meta-text">Every area with recorded activity, ranked</span>
                  </div>
                </div>
                {report.activity_by_zone.length > 0 ? (
                  <ZoneActivityList busiestZone={report.busiest_zone} zones={report.activity_by_zone} />
                ) : (
                  <EmptyState title="No area activity recorded yet" description="Draw Zones on a Stream to break activity down by area." />
                )}
              </section>

              {/* Place / Yard Intelligence v2, Phase 7: which camera currently
                  sees the most wildlife activity, normalized for how long each
                  one was actually monitored -- never a raw side-by-side count. */}
              {(report.activity_by_source ?? []).length > 1 ? (
                <section className="panel" aria-label="Wildlife activity by camera">
                  <div className="section-heading">
                    <div>
                      <h2>Camera activity</h2>
                      <span className="meta-text">Confirmed wildlife visits per monitored hour, this period</span>
                    </div>
                  </div>
                  <SourceActivityList sources={report.activity_by_source} />
                </section>
              ) : null}

              <section className="panel" aria-label="Species seen in this period">
                <div className="section-heading">
                  <div>
                    <h2>Species seen in this period</h2>
                    <span className="meta-text">Confirmed and likely sightings, with their usual time or place when there's enough history to say</span>
                  </div>
                </div>
                {taxaList.length > 0 ? (
                  <div className="journal-label-grid">
                    {taxaList.map((taxon) => (
                      <TaxonCard key={taxon.label} onOpenBirdLog={onOpenBirdLog} onOpenVisit={onOpenVisit} taxon={taxon} />
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    description="Wildlife activity was recorded in this period, but nothing has resolved to a named species or kind yet."
                    title="No specific species identified yet"
                  />
                )}
              </section>
            </>
          ) : (
            <section className="panel">
              <EmptyState
                description={
                  report.maturity === "usable"
                    ? "MockingBird actively monitored this period and didn't record any wildlife activity."
                    : "MockingBird hasn't monitored enough of this period yet to show a reliable pattern. Patterns will appear here as more of this period is actively watched."
                }
                title={report.maturity === "usable" ? "No wildlife activity recorded in this period" : "Not enough monitoring yet to see a pattern"}
              />
            </section>
          )}
        </>
      ) : null}

      {/* Biodiversity & Place Intelligence v1: deliberately outside the
          `report` conditional above -- an all-time Place roster, not
          scoped to the period picker. Same component the Dashboard's own
          sibling card uses, so the two can never disagree. */}
      <BiodiversitySummaryCard onOpenBirdLog={onOpenBirdLog} summary={biodiversitySummary} />

      {/* Habitat & Phenology Foundation v1: deliberately outside the `report`
          conditional above -- a genuinely independent, period-agnostic
          fetch that must keep working (or stay quietly absent) regardless
          of whether the wildlife report loaded. Read-only: editing lives on
          the Dashboard (Today) card. */}
      {habitatFacts.length > 0 || phenologyObservations.length > 0 ? (
        <section aria-label="Habitat and season history" className="panel">
          <div className="section-heading">
            <div>
              <h2>Habitat &amp; season</h2>
              <span className="meta-text">
                Durable details about this Place, and the full history of recorded season/phenology
                notes -- not limited to the period above.
              </span>
            </div>
          </div>
          {habitatFacts.length > 0 ? (
            <div className="tag-row">
              {habitatFacts.map((fact) => (
                <span className="tag" key={fact.id}>
                  {fact.label}
                </span>
              ))}
            </div>
          ) : null}
          {phenologyObservations.length > 0 ? (
            <ul className="habitat-phenology-list">
              {phenologyObservations.map((observation) => (
                <li key={observation.id}>
                  <strong>{observation.subject_label}</strong> &middot; {observation.phenomenon}
                  {observation.status === "current" ? <StatusPill label="Current" tone="good" /> : null}
                  {observation.status === "recent" ? <StatusPill label="Recently" tone="quiet" /> : null}
                  <span className="meta-text">
                    {phenologyDateRange(observation.observed_start_date, observation.observed_end_date)}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      {/* Place Features & Habitat Change v2: deliberately outside the
          `report` conditional above, same reasoning as Habitat & Season
          just above -- a genuinely independent, period-agnostic fetch.
          Read-only: editing lives on the Dashboard (Today) card. Each
          Feature's own before/after insight is lazily loaded only when
          expanded, never computed for every Feature up front. */}
      {placeFeatures.length > 0 || featureChangeEvents.length > 0 ? (
        <section aria-label="Place features and changes" className="panel">
          <div className="section-heading">
            <div>
              <h2>Features &amp; changes</h2>
              <span className="meta-text">
                Feeders, water features, and other things around this Place, and the full history of
                recorded changes -- not limited to the period above.
              </span>
            </div>
          </div>
          {placeFeatures.length > 0 ? (
            <ul className="habitat-phenology-list">
              {placeFeatures.map((feature) => (
                <li key={feature.id}>
                  <strong>{feature.name}</strong> &middot; {FEATURE_TYPE_DISPLAY_NAMES[feature.feature_type]}
                  {!feature.is_active ? <StatusPill label="Inactive" tone="quiet" /> : null}
                  <button
                    className="text-action"
                    onClick={() => toggleFeatureDetail(feature.id)}
                    type="button"
                  >
                    {expandedFeatureId === feature.id ? "Hide activity insight" : "See activity insight"}
                  </button>
                  {expandedFeatureId === feature.id ? (
                    <div className="detail-actions">
                      {isLoadingFeatureDetail ? (
                        <span className="meta-text">Loading…</span>
                      ) : expandedFeatureDetail ? (
                        expandedFeatureDetail.changes.length > 0 ? (
                          <ul className="habitat-phenology-list">
                            {expandedFeatureDetail.changes.map((change) => (
                              <li key={change.event.id}>
                                <span className="meta-text">
                                  {CHANGE_EVENT_TYPE_DISPLAY_NAMES[change.event.event_type]} &middot;{" "}
                                  {change.event.effective_date}
                                </span>
                                <p className="meta-text">
                                  {change.comparison
                                    ? featureAssociationSentence(change.comparison)
                                    : "No camera or Zone is linked to this feature yet, so activity can't be compared."}
                                </p>
                              </li>
                            ))}
                          </ul>
                        ) : (
                          <span className="meta-text">No changes recorded for this feature yet.</span>
                        )
                      ) : (
                        <span className="meta-text">Could not load this feature's activity insight.</span>
                      )}
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
          {featureChangeEvents.filter((event) => !event.feature_id).length > 0 ? (
            <ul className="habitat-phenology-list">
              {featureChangeEvents
                .filter((event) => !event.feature_id)
                .map((event) => (
                  <li key={event.id}>
                    {CHANGE_EVENT_TYPE_DISPLAY_NAMES[event.event_type]}
                    <span className="meta-text">
                      {event.effective_date}
                      {event.note ? ` · ${event.note}` : ""}
                    </span>
                  </li>
                ))}
            </ul>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
