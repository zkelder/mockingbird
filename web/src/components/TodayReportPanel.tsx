import { useEffect, useState } from "react";
import type {
  PlaceActivityReportDigestSpeciesHighlight,
  PlaceActivityReportHourActivity,
  PlaceActivityReportResponse,
} from "../api/types";
import { apiClient } from "../api/client";
import { EmptyState } from "./EmptyState";
import { SourceActivityList } from "./SourceActivityList";
import { StatusPill } from "./StatusPill";
import { formatDateTime } from "../utils";

/**
 * Product Experience / UI Cohesion v1 Phase 1 (Gate C: Daily Place Report
 * v1, then Calm Daily Digest v1, hardened this further): the report-first
 * "Today in Your Yard" summary. Renders only facts already computed by the
 * existing read-only Place Activity Report backend (`POST /api/analytics/
 * place-activity-report`, see docs/place-activity-report-contract.md) --
 * this component never re-derives truth precedence, wildlife eligibility,
 * Visit counts, or highlight wording/ranking itself. Every count here is a
 * Visit count, never a unique-animal count.
 *
 * Calm Daily Digest v1 (see `mockingbird.analytics.daily_digest`) is the
 * single source of the highlighted-species list, its bounded priority
 * ranking, and every badge/pattern sentence below -- this component is a
 * presentation layer only; it does not rank, caption, or blend counts
 * itself. Confirmed vs. provisional: the backend deliberately keeps
 * `confirmed_visit_count`/`provisional_visit_count` separate on every
 * highlight precisely so a consumer does not blend them into one number
 * (see "Report truth precedence" in docs/place-activity-report-contract.md).
 * A species with only provisional (AI-suggested, never human-reviewed)
 * Visits never appears by name; it is only ever represented, in aggregate
 * and without a species name attached, by `digest.other_activity` and the
 * quiet "N items worth reviewing" footer link. A taxon that *is* confirmed
 * but also has additional provisional sightings shows its confirmed count
 * as the primary figure and the extra provisional ones as a small "+N
 * likely" annotation, never folded into one blended total.
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
  // UI/UX & First-Run Adoption v1: the all-time waiting count (Dashboard
  // headline `needs_review_visit_count`, demo-excluded) -- `reviewCount`
  // below is today-only, so on its own it said "All caught up" while older
  // visits were still waiting in the Review Queue.
  waitingReviewCount?: number;
}

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

function speciesTimeRange(highlight: PlaceActivityReportDigestSpeciesHighlight): string {
  const first = formatTimeOnly(highlight.first_activity_at);
  if (highlight.first_activity_at === highlight.last_activity_at) {
    return `Seen ${first}`;
  }
  return `First ${first} · Last ${formatTimeOnly(highlight.last_activity_at)}`;
}

// Calm Daily Digest v1 already resolved every badge/pattern sentence below
// server-side (`mockingbird.analytics.daily_digest`) -- this component only
// renders already-composed, already-truth-checked text, exactly the same
// "backend resolves facts and wording, this component only presents them"
// boundary the rest of this file follows. `null` is always a calm, valid
// outcome (the ordinary "seen_before" species, "no_supported_change", or a
// pattern below the minimum-support floor) -- never an error state.
function historicalTone(reason: PlaceActivityReportDigestSpeciesHighlight["reason"]): "good" | "quiet" {
  return reason === "regular_activity" ? "good" : "quiet";
}

// Gate C -- Representative Species Evidence v1 (see docs/representative-
// species-evidence-contract.md). Alt text is built from the reviewed
// species name and real capture context this component already has --
// never model speculation, and never information a screen-reader user
// could not get any other way (the species name and visit count are
// already plain text on this same row).
function representativeAlt(highlight: PlaceActivityReportDigestSpeciesHighlight): string {
  const capturedAt = highlight.representative_evidence?.evidence.captured_at;
  return capturedAt
    ? `${highlight.display_name}, reviewed observation ${formatDateTime(capturedAt)}`
    : `${highlight.display_name}, reviewed observation`;
}

// Compact, non-interactive thumbnail for one species row. Deliberately no
// click-through: Today stays report-first and calm (see "Today UI" in the
// milestone brief), not a photo grid. Renders nothing at all -- no
// placeholder box -- when this highlight has no representative evidence; a
// missing/failed image degrades the same way, never an error state (see
// "I.8 Representative evidence" / "image absent still produces highlight").
function SpeciesThumbnail({ highlight }: { highlight: PlaceActivityReportDigestSpeciesHighlight }) {
  const [failed, setFailed] = useState(false);
  const evidence = highlight.representative_evidence?.evidence;
  useEffect(() => setFailed(false), [evidence?.media_asset_id]);
  if (!evidence || failed) return null;
  return (
    <img
      alt={representativeAlt(highlight)}
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

export function TodayReportPanel({
  report,
  isLoading,
  configuredStreamCount,
  monitoredStreamCount,
  onAddCamera,
  onOpenStreams,
  onOpenReview,
  onOpenBirdLog,
  waitingReviewCount = 0,
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
  // Calm Daily Digest v1 already ranked, bounded, and worded this list
  // server-side (see mockingbird.analytics.daily_digest) -- this component
  // never re-derives ranking or truth precedence, it only presents the
  // result.
  const digest = report.digest;
  const primaryHighlights = digest.primary_highlights;
  const hasConfirmedTaxa = primaryHighlights.length > 0 || digest.other_species.length > 0;
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
  // taxon count so the headline never reads "0 species" while confirmed
  // wildlife plainly appeared today. Spans the full confirmed set (primary
  // highlights plus the compact "also recorded" continuation), not only
  // the bounded highlight list.
  const confirmedTaxaCount = primaryHighlights.length + digest.other_species.length;
  const confirmedSpeciesCount =
    primaryHighlights.filter((entry) => entry.is_species).length +
    digest.other_species.filter((entry) => entry.is_species).length;
  const speciesHeadlineCount = confirmedSpeciesCount > 0 ? confirmedSpeciesCount : confirmedTaxaCount;
  const speciesHeadlineLabel = confirmedSpeciesCount > 0 ? "species" : "kinds of wildlife";
  // Calm Daily Digest v1 already resolved this identical sentence
  // server-side (see "I.11 Developing installation" -- one calm,
  // already-accepted baseline sentence, not a second one invented here).
  const changeMessage = digest.place_change_note;
  // Everyday Discovery / Product Experience v2 (Phase F): the evidence
  // behind that one sentence -- previously computed every request but never
  // rendered anywhere (`report.overall_change_status` was dead payload) --
  // shown only when the backend itself reports a directional, supported
  // change; the sentence alone already covers every other (baseline-
  // building/insufficient-coverage/no-change) case honestly. Mirrors Bird
  // Log's own identical "Recent: N of M usable monitored days" wording
  // (`BirdLogPage.tsx`) so the same underlying fact never reads differently
  // on the two surfaces.
  const changeEvidence =
    report.overall_change_status.status === "more_activity_recorded" ||
    report.overall_change_status.status === "less_activity_recorded"
      ? `Recent: ${report.overall_change_status.recent_presence_days} of ${report.overall_change_status.recent_usable_day_count} usable monitored days · Reference: ${report.overall_change_status.reference_presence_days} of ${report.overall_change_status.reference_usable_day_count} usable monitored days`
      : null;

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
      {changeMessage ? (
        <p className="meta-text today-report-change-note">
          {changeMessage}
          {changeEvidence ? <span className="today-report-change-evidence"> · {changeEvidence}</span> : null}
        </p>
      ) : null}

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

              {primaryHighlights.length > 0 ? (
                <div className="today-report-species">
                  <div className="section-heading">
                    <h3>Today’s highlights</h3>
                    <button className="text-action" onClick={onOpenBirdLog} type="button">
                      Bird Log
                    </button>
                  </div>
                  <ol className="today-report-species-list">
                    {primaryHighlights.map((highlight) => (
                      <li key={highlight.label}>
                        <SpeciesThumbnail highlight={highlight} />
                        <div className="today-report-species-name">
                          <span>{highlight.display_name}</span>
                          <span className="today-report-species-meta">{speciesTimeRange(highlight)}</span>
                          {/* Multi-Camera Place Experience v2: which camera
                              produced this highlight's evidence — only
                              worth naming once there is more than one
                              camera to distinguish (see "Do not turn Today
                              into a camera-monitoring dashboard"). */}
                          {monitoredStreamCount > 1 && highlight.representative_evidence?.stream_name ? (
                            <span className="today-report-species-meta">
                              via {highlight.representative_evidence.stream_name}
                            </span>
                          ) : null}
                          {highlight.pattern_note ? (
                            <span className="today-report-species-meta">{highlight.pattern_note}</span>
                          ) : null}
                          {highlight.historical_note ? (
                            <StatusPill label={highlight.historical_note} tone={historicalTone(highlight.reason)} />
                          ) : null}
                          {highlight.change_note ? (
                            <StatusPill label={highlight.change_note} tone="quiet" />
                          ) : null}
                          {/* Place / Yard Intelligence v2: same "only when earned" discipline
                              as the two pills above — most highlights show neither. */}
                          {highlight.regularity_note ? (
                            <StatusPill label={highlight.regularity_note} tone="quiet" />
                          ) : null}
                          {highlight.seasonal_note ? (
                            <StatusPill label={highlight.seasonal_note} tone="quiet" />
                          ) : null}
                        </div>
                        <div className="today-report-species-count">
                          <strong>{plural(highlight.confirmed_visit_count, "visit")}</strong>
                          {highlight.provisional_visit_count > 0 ? (
                            <span className="today-report-species-likely">
                              +{highlight.provisional_visit_count} likely
                            </span>
                          ) : null}
                        </div>
                      </li>
                    ))}
                  </ol>
                  {digest.other_species.length > 0 ? (
                    <p className="meta-text today-report-also-recorded">
                      Also recorded:{" "}
                      {digest.other_species.map((entry) => entry.display_name).join(" · ")}
                    </p>
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

          {/* Multi-Camera Place Experience v2: a compact, coverage-normalized
              per-camera comparison — reuses the exact same SourceActivityList
              presentation as the full Place Activity Report page, never a
              second bar-list. Only worth showing once there is more than one
              camera to compare (matching that page's own gating); Today stays
              a report, not a camera-monitoring dashboard. */}
          {monitoredStreamCount > 1 && (report.activity_by_source ?? []).length > 1 ? (
            <div className="today-report-species">
              <div className="section-heading">
                <h3>By camera</h3>
              </div>
              <SourceActivityList sources={report.activity_by_source} />
            </div>
          ) : null}
        </>
      ) : monitoredStreamCount > 0 ? (
        digest.coverage.state !== "no_confirmed_activity" ? (
          // sparse_monitoring or no_monitoring (see "I.10 Coverage
          // semantics"): too little of today has been monitored yet to
          // honestly say wildlife did or didn't appear -- never "no
          // wildlife visited" when there simply isn't enough monitoring
          // behind that claim yet. Wording is Calm Daily Digest v1's own
          // (mockingbird.analytics.daily_digest), not re-authored here.
          <EmptyState description={digest.coverage.message} title="Not enough monitoring yet to say" />
        ) : (
          // Genuinely usable coverage, genuinely zero wildlife activity of
          // any kind -- an honest, calm observation, not a database dump.
          <EmptyState description={digest.coverage.message} title="No wildlife visits yet today" />
        )
      ) : (
        <EmptyState
          action={
            <button
              className="secondary-action"
              onClick={configuredStreamCount > 0 ? onOpenStreams : onAddCamera}
              type="button"
            >
              {configuredStreamCount > 0 ? "Go to Cameras" : "Add Camera"}
            </button>
          }
          description={
            configuredStreamCount > 0
              ? `Start observing on your ${configuredStreamCount > 1 ? "cameras" : "camera"} to begin building your wildlife report.`
              : "Add a camera to start building your wildlife report. Frequent visitors, busiest times, and most active areas will appear here."
          }
          title={configuredStreamCount > 0 ? "Monitoring hasn’t started yet" : "MockingBird is ready to watch this place"}
        />
      )}

      <div className="today-report-footer">
        {/* Everyday Discovery / Product Experience v2 (Phase I): considered
            breaking this flat count down by unresolved-vs-provisional, but
            `e2e/today-report.spec.ts`'s "unresolved and provisional
            activity stays a quiet affordance" test encodes a deliberate
            existing decision to keep this link calm and jargon-free (it
            explicitly asserts no "AI suggestion" wording ever appears here)
            — review prominence already reads as adequate per this
            milestone's own archaeology; left unchanged rather than
            reopening an already-settled call. */}
        {reviewCount > 0 ? (
          <button className="text-action" onClick={onOpenReview} type="button">
            {plural(reviewCount, "item")} worth reviewing
          </button>
        ) : waitingReviewCount > 0 ? (
          <button className="text-action" onClick={onOpenReview} type="button">
            Nothing new today · {plural(waitingReviewCount, "earlier visit")} still worth reviewing
          </button>
        ) : (
          <span className="meta-text">All caught up — nothing waiting on you</span>
        )}
      </div>
    </section>
  );
}
