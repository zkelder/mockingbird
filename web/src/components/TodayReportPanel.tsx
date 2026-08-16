import type { PlaceActivityReportHourActivity, PlaceActivityReportResponse } from "../api/types";
import { EmptyState } from "./EmptyState";
import { StatusPill } from "./StatusPill";
import { formatDateTime } from "../utils";

/**
 * Product Experience / UI Cohesion v1 Phase 1: the report-first "Today in
 * Your Yard" summary. Renders only facts already computed by the existing
 * read-only Place Activity Report backend (`POST
 * /api/analytics/place-activity-report`, see
 * docs/place-activity-report-contract.md) -- this component never re-derives
 * truth precedence, wildlife eligibility, or Visit counts itself. Every
 * count here is a Visit count, never a unique-animal count.
 */

interface TodayReportPanelProps {
  report: PlaceActivityReportResponse | null;
  isLoading: boolean;
  configuredStreamCount: number;
  monitoredStreamCount: number;
  onAddCamera: () => void;
  onOpenStreams: () => void;
  onOpenReview: () => void;
  onOpenBirdLog: () => void;
}

const TOP_SPECIES_LIMIT = 5;

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

function formatHour12(hour: number): { label: string; period: "AM" | "PM" } {
  const period = hour < 12 ? "AM" : "PM";
  const twelveHour = hour % 12 === 0 ? 12 : hour % 12;
  return { label: String(twelveHour), period };
}

// One hour bucket shown as its own honest span (the 7:00-7:59 bucket reads
// "7–8 AM") -- never a fabricated multi-hour "peak window." The backend
// only exposes a per-hour distribution, so this is the most a deterministic,
// obvious presentation can claim; see "Baselines / trends" in
// docs/place-activity-report-contract.md.
function formatHourRange(hour: number): string {
  const start = formatHour12(hour);
  const end = formatHour12((hour + 1) % 24);
  if (start.period === end.period) {
    return `${start.label}–${end.label} ${end.period}`;
  }
  return `${start.label} ${start.period}–${end.label} ${end.period}`;
}

// The single busiest hour; the earliest hour wins a tie so the result is
// deterministic across otherwise-equal buckets.
function busiestHour(
  activityByHour: PlaceActivityReportHourActivity[],
): PlaceActivityReportHourActivity | null {
  let best: PlaceActivityReportHourActivity | null = null;
  for (const entry of activityByHour) {
    if (entry.wildlife_visit_count > 0 && (!best || entry.wildlife_visit_count > best.wildlife_visit_count)) {
      best = entry;
    }
  }
  return best;
}

export function TodayReportPanel({
  report,
  isLoading,
  configuredStreamCount,
  monitoredStreamCount,
  onAddCamera,
  onOpenStreams,
  onOpenReview,
  onOpenBirdLog,
}: TodayReportPanelProps) {
  if (!report && isLoading) {
    return (
      <section aria-label="Today's wildlife report" className="panel today-report">
        <p className="meta-text">Loading today’s report…</p>
      </section>
    );
  }

  if (!report) {
    return (
      <section aria-label="Today's wildlife report" className="panel today-report">
        <EmptyState
          description="MockingBird could not load today's wildlife summary right now. Your camera data and history are unaffected."
          title="Today's report is temporarily unavailable"
        />
      </section>
    );
  }

  const hasWildlife = report.wildlife_visit_count > 0;
  const topTaxa = report.taxa.slice(0, TOP_SPECIES_LIMIT);
  const extraTaxaCount = report.taxa.length - topTaxa.length;
  const busiest = busiestHour(report.activity_by_hour);
  // Everything that is not yet confirmed truth but is not excluded either --
  // a truthful, backend-derived total, never a re-derivation of per-Visit
  // truth precedence (see docs/review-decision-provenance-contract.md).
  const reviewCount = report.provisional_wildlife_visit_count + report.unresolved_visit_count;
  const coverageKnown = report.coverage.monitored_seconds != null;
  // The backend's own disclosure sentences already state exactly what a
  // union-of-cameras coverage figure does and does not mean (see
  // "Place-wide coverage policy" in docs/place-activity-report-contract.md);
  // this only selects which already-written sentences are about coverage,
  // it never authors new coverage wording.
  const coverageNotes = report.warnings.filter((warning) =>
    /coverage|monitoring exposure/i.test(warning),
  );
  // The cross-Stream warning above only ever fires for the multi-Stream
  // "some but not all Streams have history" case (see "Place-wide coverage
  // policy" in docs/place-activity-report-contract.md); it says nothing
  // about *this period's own* measured coverage_ratio. A Stream can have
  // durable exposure history from an earlier period yet zero coverage
  // during the requested one (for example: monitored yesterday, not yet
  // started today) -- the backend correctly reports that as a real
  // coverage_ratio near/at 0, but deriving coveragePartial from warnings
  // alone missed it entirely, showing the "good"-toned "Fully observed
  // today" pill for a literal 0% ratio. The backend deliberately leaves
  // "how much gap counts as partial" to the UI (it "does not invent a
  // materiality threshold"); a small tolerance (99%) absorbs sub-minute
  // restart/rollover gaps without diluting the pill's honesty for a
  // materially incomplete day.
  const coverageRatio = report.coverage.coverage_ratio;
  const coverageRatioLow = coverageRatio != null && coverageRatio < 0.99;
  const coveragePartial = coverageNotes.length > 0 || coverageRatioLow;
  // Prefer the backend's own richer cross-Stream sentence when both signals
  // fire; otherwise fall back to an honest sentence built only from the
  // real, already-returned coverage_ratio -- never a fabricated claim.
  const coverageNote =
    coverageNotes[0] ??
    (coverageRatioLow
      ? `MockingBird was actively monitoring about ${Math.round(coverageRatio! * 100)}% of today so far.`
      : null);
  // A confirmed Visit whose taxon never resolved to species level (a coarse
  // "Bird"/"Squirrel" group) still counts as wildlife; fall back to the
  // taxon count so the headline never reads "0 species" while wildlife
  // plainly appeared today.
  const speciesHeadlineCount =
    report.distinct_species_count > 0 ? report.distinct_species_count : report.distinct_taxa_count;
  const speciesHeadlineLabel = report.distinct_species_count > 0 ? "species" : "kinds of wildlife";

  return (
    <section aria-label="Today's wildlife report" className="panel today-report">
      <div className="section-heading">
        <div>
          <h2>Today’s activity</h2>
        </div>
        {coverageKnown ? (
          <StatusPill
            label={coveragePartial ? "Partial coverage today" : "Fully observed today"}
            tone={coveragePartial ? "quiet" : "good"}
          />
        ) : null}
      </div>
      {coveragePartial && coverageNote ? (
        <p className="meta-text today-report-coverage-note">{coverageNote}</p>
      ) : null}

      {hasWildlife ? (
        <>
          <div className="today-report-headline">
            <div className="today-report-stat">
              <strong>{speciesHeadlineCount}</strong>
              <span>{speciesHeadlineLabel}</span>
            </div>
            <div className="today-report-stat">
              <strong>{report.wildlife_visit_count}</strong>
              <span>{report.wildlife_visit_count === 1 ? "wildlife visit" : "wildlife visits"}</span>
            </div>
          </div>
          {report.last_activity_at ? (
            <p className="meta-text">Last visit {formatDateTime(report.last_activity_at)}</p>
          ) : null}

          {topTaxa.length > 0 ? (
            <div className="today-report-species">
              <div className="section-heading">
                <h3>Top visitors</h3>
                <button className="text-action" onClick={onOpenBirdLog} type="button">
                  Bird Log
                </button>
              </div>
              <ol className="today-report-species-list">
                {topTaxa.map((taxon) => (
                  <li key={taxon.label}>
                    <span>{taxon.display_name}</span>
                    <strong>{plural(taxon.total_visit_count, "visit")}</strong>
                  </li>
                ))}
              </ol>
              {extraTaxaCount > 0 ? (
                <span className="meta-text">+{extraTaxaCount} more species</span>
              ) : null}
            </div>
          ) : null}

          {busiest || report.busiest_zone ? (
            <div className="today-report-facts">
              {busiest ? (
                <div className="today-report-fact">
                  <span>Most active</span>
                  <strong>{formatHourRange(busiest.hour)}</strong>
                </div>
              ) : null}
              {report.busiest_zone ? (
                <div className="today-report-fact">
                  <span>Busiest area</span>
                  <strong>{report.busiest_zone.zone_name}</strong>
                  <span className="meta-text">{plural(report.busiest_zone.wildlife_visit_count, "visit")}</span>
                </div>
              ) : null}
            </div>
          ) : null}
        </>
      ) : monitoredStreamCount > 0 ? (
        <EmptyState
          description="MockingBird is watching this place. Your frequent visitors, busiest times, and most active areas will show up here as activity builds."
          title="No wildlife visits yet today"
        />
      ) : (
        <EmptyState
          action={
            <button
              className="secondary-action"
              onClick={configuredStreamCount > 0 ? onOpenStreams : onAddCamera}
              type="button"
            >
              {configuredStreamCount > 0 ? "Open Cameras / Streams" : "Add Camera"}
            </button>
          }
          description={
            configuredStreamCount > 0
              ? "Start observing on your camera to begin building your wildlife report."
              : "Add a camera to start building your wildlife report. Frequent visitors, busiest times, and most active areas will appear here."
          }
          title={configuredStreamCount > 0 ? "Monitoring hasn’t started yet" : "MockingBird is ready to watch this place"}
        />
      )}

      <div className="today-report-footer">
        {reviewCount > 0 ? (
          <button className="text-action" onClick={onOpenReview} type="button">
            {plural(reviewCount, "item")} worth reviewing
          </button>
        ) : (
          <span className="meta-text">All caught up — nothing waiting on you</span>
        )}
      </div>
    </section>
  );
}
