import { useEffect, useState } from "react";
import type {
  PlaceActivityReportHourActivity,
  PlaceActivityReportResponse,
  PlaceActivityReportTaxonEntry,
} from "../api/types";
import { apiClient } from "../api/client";
import { EmptyState } from "./EmptyState";
import { StatusPill } from "./StatusPill";
import { changeStatusBadge, formatDateTime } from "../utils";

/**
 * Product Experience / UI Cohesion v1 Phase 1 (Gate C: Daily Place Report
 * v1 hardened this further): the report-first "Today in Your Yard" summary.
 * Renders only facts already computed by the existing read-only Place
 * Activity Report backend (`POST /api/analytics/place-activity-report`, see
 * docs/place-activity-report-contract.md) -- this component never re-derives
 * truth precedence, wildlife eligibility, or Visit counts itself. Every
 * count here is a Visit count, never a unique-animal count.
 *
 * Confirmed vs. provisional: the backend deliberately keeps `confirmed_
 * visit_count`/`provisional_visit_count` separate on every `taxa` entry
 * precisely so a consumer does not blend them into one number (see "Report
 * truth precedence" in docs/place-activity-report-contract.md). The
 * headline species count, "Top visitors" list, and its ranking below are
 * all confirmed-only for exactly that reason -- a species with only
 * provisional (AI-suggested, never human-reviewed) Visits never appears
 * there by name; it is only ever represented, in aggregate and without a
 * species name attached, by the quiet "N items worth reviewing" footer
 * link. A taxon that *is* confirmed but also has additional provisional
 * sightings shows its confirmed count as the primary figure and the extra
 * provisional ones as a small "+N likely" annotation, never folded into one
 * blended total.
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

// Time-only (no date) for a per-species row -- the report is always exactly
// one calendar day, so repeating that day on every row would only add
// noise; the report-level "First visit"/"Last visit" lines below already
// carry the fuller formatDateTime treatment once for the whole page.
function formatTimeOnly(value: string): string {
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

function speciesTimeRange(taxon: PlaceActivityReportTaxonEntry): string {
  const first = formatTimeOnly(taxon.first_activity_at);
  if (taxon.first_activity_at === taxon.last_activity_at) {
    return `Seen ${first}`;
  }
  return `First ${first} · Last ${formatTimeOnly(taxon.last_activity_at)}`;
}

// Historical Baseline Maturity + New/Regular Species v1 (see
// docs/historical-baseline-maturity-contract.md): the backend already
// picked the maturity-appropriate wording (`historical_status.status`
// itself distinguishes "new" from "first_record" using `historical_
// baseline.maturity` -- this component never re-derives that judgment). A
// taxon with no historical_status (purely provisional today, never
// authoritatively confirmed) or "seen_before" status gets no badge at all
// -- keep the row calm rather than annotating every species every day.
function historicalStatusBadge(
  taxon: PlaceActivityReportTaxonEntry,
): { label: string; tone: "good" | "quiet" } | null {
  switch (taxon.historical_status?.status) {
    case "new":
      return { label: "New to your reviewed history", tone: "quiet" };
    case "first_record":
      return { label: "First confirmed record so far", tone: "quiet" };
    case "regular":
      return { label: "Regular here", tone: "good" };
    default:
      return null;
  }
}

// The single Place-level line Today may show about recent-vs-reference
// change -- see "Today integration" in docs/meaningful-change-detection-
// contract.md. `no_supported_change` deliberately renders nothing (the
// calm, ordinary case -- silence is the message), matching how a plain
// "seen_before" species row above also renders no badge at all. This next
// says only what MockingBird recorded under comparable monitoring -- never
// a population/ecological claim.
function overallChangeMessage(status: PlaceActivityReportResponse["overall_change_status"]): string | null {
  switch (status.status) {
    case "building_baseline":
      return "MockingBird is still building a baseline for this Place.";
    case "insufficient_recent_coverage":
      return "There wasn't enough recent monitoring to compare with history.";
    case "more_activity_recorded":
      return "Wildlife activity was recorded on more monitored days recently than in the preceding weeks.";
    case "less_activity_recorded":
      return "Wildlife activity was recorded on fewer monitored days recently than in the preceding weeks.";
    default:
      return null;
  }
}

// Gate C -- Per-Species Zone + Time Pattern Intelligence v1: one concise,
// observational secondary fact about where/when this taxon is usually
// recorded, from the same bounded historical window `historical_status`/
// `change_status` above already use -- never a behavioral or ecological
// claim ("prefers the feeder," "feeds at 7 AM"), only what MockingBird's
// own reviewed history shows. `null` below this milestone's minimum-support
// floor (see "Minimum support" in docs/place-activity-report-contract.md)
// -- the row simply omits this line rather than manufacturing a pattern
// from too little evidence. With no Zones configured, `most_active_zone`
// is always null for every species and this naturally degrades to
// time-only wording -- no separate "no Zones" handling needed here (see
// "Critical invariant: Zones are optional").
function speciesPlacePattern(taxon: PlaceActivityReportTaxonEntry): string | null {
  const zone = taxon.most_active_zone;
  const hour = taxon.most_active_hour;
  if (zone && hour) {
    return `${zone.display_name} · ${formatHourRange(hour.local_hour)}`;
  }
  if (zone) {
    return `Mostly recorded at ${zone.display_name}`;
  }
  if (hour) {
    return `Most active ${formatHourRange(hour.local_hour)}`;
  }
  return null;
}

// Gate C -- Representative Species Evidence v1 (see docs/representative-
// species-evidence-contract.md). Alt text is built from the reviewed taxon
// name and real capture context this component already has -- never model
// speculation, and never information a screen-reader user could not get
// any other way (the species name and visit count are already plain text
// on this same row).
function representativeAlt(taxon: PlaceActivityReportTaxonEntry): string {
  const capturedAt = taxon.representative_evidence?.evidence.captured_at;
  return capturedAt
    ? `${taxon.display_name}, reviewed observation ${formatDateTime(capturedAt)}`
    : `${taxon.display_name}, reviewed observation`;
}

// Compact, non-interactive thumbnail for one species row. Deliberately no
// click-through: Today stays report-first and calm (see "Today UI" in the
// milestone brief), not a photo grid. Renders nothing at all -- no
// placeholder box -- when this taxon has no representative evidence; a
// missing/failed image degrades the same way, never an error state.
function SpeciesThumbnail({ taxon }: { taxon: PlaceActivityReportTaxonEntry }) {
  const [failed, setFailed] = useState(false);
  const evidence = taxon.representative_evidence?.evidence;
  useEffect(() => setFailed(false), [evidence?.media_asset_id]);
  if (!evidence || failed) return null;
  return (
    <img
      alt={representativeAlt(taxon)}
      className="today-report-species-thumb"
      loading="lazy"
      onError={() => setFailed(true)}
      src={`${apiClient.baseUrl}${evidence.preview_url}`}
    />
  );
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

// Reviewed truth first: rank and keep only taxa a human has actually
// confirmed at least once. A taxon backed solely by an AI suggestion never
// appears here by name (see the module doc comment above); it is still
// visible, just not as a named species claim.
function confirmedTaxaByCount(taxa: PlaceActivityReportTaxonEntry[]): PlaceActivityReportTaxonEntry[] {
  return taxa
    .filter((taxon) => taxon.confirmed_visit_count > 0)
    .slice()
    .sort((a, b) => {
      if (b.confirmed_visit_count !== a.confirmed_visit_count) {
        return b.confirmed_visit_count - a.confirmed_visit_count;
      }
      return a.display_name.localeCompare(b.display_name);
    });
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

  // "Did anything happen" stays broad (confirmed + provisional + unresolved
  // wildlife) -- a day is never flattened to "nothing happened" merely
  // because nothing has been reviewed yet (see "Unresolved wildlife" in
  // docs/place-activity-report-contract.md). Once inside this branch, the
  // headline numbers and species list narrow to confirmed truth only.
  const hasWildlife = report.wildlife_visit_count > 0;
  const hasConfirmedWildlife = report.confirmed_wildlife_visit_count > 0;
  const confirmedTaxa = confirmedTaxaByCount(report.taxa);
  const hasConfirmedTaxa = confirmedTaxa.length > 0;
  const topTaxa = confirmedTaxa.slice(0, TOP_SPECIES_LIMIT);
  const extraTaxaCount = confirmedTaxa.length - topTaxa.length;
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
  // Report maturity (see compute_report_maturity in place_activity_report.py)
  // -- purely a coverage judgment, never a wildlife-count one. Used only to
  // decide how confidently a *silence* ("no wildlife yet") can be claimed;
  // it never gates or discounts an actually-recorded Visit.
  const coverageInsufficientForConclusions = report.maturity !== "usable";
  // A confirmed Visit whose taxon never resolved to species level (a coarse
  // "Bird"/"Squirrel" group) still counts as wildlife; fall back to the
  // taxon count so the headline never reads "0 species" while confirmed
  // wildlife plainly appeared today.
  const confirmedSpeciesCount = confirmedTaxa.filter((taxon) => taxon.is_species).length;
  const speciesHeadlineCount = confirmedSpeciesCount > 0 ? confirmedSpeciesCount : confirmedTaxa.length;
  const speciesHeadlineLabel = confirmedSpeciesCount > 0 ? "species" : "kinds of wildlife";
  const changeMessage = overallChangeMessage(report.overall_change_status);

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
      {changeMessage ? <p className="meta-text today-report-change-note">{changeMessage}</p> : null}

      {hasWildlife ? (
        <>
          {hasConfirmedTaxa ? (
            <>
              <div className="today-report-headline">
                <div className="today-report-stat">
                  <strong>{speciesHeadlineCount}</strong>
                  <span>{speciesHeadlineLabel}</span>
                </div>
                <div className="today-report-stat">
                  <strong>{report.confirmed_wildlife_visit_count}</strong>
                  <span>{report.confirmed_wildlife_visit_count === 1 ? "wildlife visit" : "wildlife visits"}</span>
                </div>
              </div>
              {report.first_activity_at ? (
                <p className="meta-text">First visit {formatDateTime(report.first_activity_at)}</p>
              ) : null}
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
                    {topTaxa.map((taxon) => {
                      const historicalBadge = historicalStatusBadge(taxon);
                      const changeBadge = changeStatusBadge(taxon.change_status);
                      const placePattern = speciesPlacePattern(taxon);
                      return (
                        <li key={taxon.label}>
                          <SpeciesThumbnail taxon={taxon} />
                          <div className="today-report-species-name">
                            <span>{taxon.display_name}</span>
                            <span className="today-report-species-meta">{speciesTimeRange(taxon)}</span>
                            {placePattern ? (
                              <span className="today-report-species-meta">{placePattern}</span>
                            ) : null}
                            {historicalBadge ? (
                              <StatusPill label={historicalBadge.label} tone={historicalBadge.tone} />
                            ) : null}
                            {changeBadge ? <StatusPill label={changeBadge.label} tone={changeBadge.tone} /> : null}
                          </div>
                          <div className="today-report-species-count">
                            <strong>{plural(taxon.confirmed_visit_count, "visit")}</strong>
                            {taxon.provisional_visit_count > 0 ? (
                              <span className="today-report-species-likely">
                                +{taxon.provisional_visit_count} likely
                              </span>
                            ) : null}
                          </div>
                        </li>
                      );
                    })}
                  </ol>
                  {extraTaxaCount > 0 ? (
                    <span className="meta-text">+{extraTaxaCount} more species</span>
                  ) : null}
                </div>
              ) : null}
            </>
          ) : (
            // Confirmed wildlife exists (a human confirmed presence, at
            // least via an "unknown_bird"/"unknown_animal" abstention) but
            // no *named* species has been confirmed yet -- distinct from
            // "nothing confirmed at all," and never silently promoted into
            // a fabricated species entry (see "Unknown / unresolved" in
            // docs/place-activity-report-contract.md).
            <EmptyState
              description={
                hasConfirmedWildlife
                  ? `${plural(report.confirmed_wildlife_visit_count, "visit")} confirmed today, but the species hasn’t been identified yet.`
                  : "MockingBird noticed possible wildlife today. Review it to build today’s confirmed history."
              }
              title={hasConfirmedWildlife ? "Confirmed wildlife — species not yet identified" : "Wildlife activity recorded — nothing confirmed yet"}
            />
          )}

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
        coverageInsufficientForConclusions ? (
          // Distinct from "no wildlife" below: too little of today has been
          // monitored yet to honestly say wildlife did or didn't appear.
          // See "Coverage / effort accounting" -- never imply "no birds
          // visited" when there simply isn't enough monitoring behind that
          // claim yet.
          <EmptyState
            description="MockingBird hasn’t monitored enough of today yet to summarize it with confidence. Check back once more of the day has been observed."
            title="Not enough monitoring yet to say"
          />
        ) : (
          <EmptyState
            description="MockingBird is watching this place. Your frequent visitors, busiest times, and most active areas will show up here as activity builds."
            title="No wildlife visits yet today"
          />
        )
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
