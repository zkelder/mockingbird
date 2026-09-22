import { useEffect, useMemo, useRef, useState } from "react";
import { apiClient } from "../api/client";
import type {
  FeatureComparisonMaturity,
  PlaceFeature,
  PlaceFeatureComparisonOverview,
  PlaceFeatureComparisonRow,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { RepresentativeThumbnail } from "../components/RepresentativeThumbnail";
import { StatusPill } from "../components/StatusPill";
import {
  CHANGE_EVENT_TYPE_DISPLAY_NAMES,
  FEATURE_TYPE_DISPLAY_NAMES,
  environmentalComparisonSentence,
  featureAssociationSentence,
} from "./PlaceActivityReportPage";
import { formatDate } from "../utils";

/**
 * Place Feature Comparison & Habitat Outcomes v1 -- see docs/place-
 * feature-comparison-habitat-outcomes-v1-contract.md. A calm, honest,
 * bounded comparison surface over every recorded Place Feature and every
 * Reviewed change event with an attempted before/after comparison -- never
 * a leaderboard, never a single "habitat score". Composed entirely from
 * `GET /api/place/feature-comparison`, itself a thin, batched composition
 * of already-accepted primitives (Feature yield, before/after comparison,
 * environmental composition, representative evidence). Sorting/filtering
 * here reflects data availability or plain factual attributes only --
 * never an ecological quality judgment.
 */
interface FeatureComparisonPageProps {
  onOpenFeatureStory: (featureId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenPlaceActivityReport: () => void;
}

type FeatureSortKey = "automatic" | "name" | "type" | "rate" | "recent_change";
type OutcomeSortKey = "recent" | "evidence";

const MATURITY_RANK: Record<FeatureComparisonMaturity, number> = {
  comparable: 0,
  early_signal: 1,
  insufficient_coverage: 2,
  too_soon: 3,
};

/** A label/tone/detail triple for `FeatureComparisonMaturity` (plus the
 * "no monitoring scope at all" case, `maturity: null`) -- mirrors
 * `baselineMaturityInfo`/`periodMaturityInfo`'s own established pattern in
 * PlaceActivityReportPage.tsx. `tone` reflects how much trustworthy
 * evidence exists, never the direction of a wildlife change -- "good" here
 * means "enough evidence to say something," not "activity increased." This
 * is the first place `early_signal` and `comparable` are ever visually
 * distinguished in this product (the underlying `featureAssociationSentence`
 * renders identical wording for both, a separately-disclosed, not-fixed
 * gap -- this badge is a new, additive element, not a fix to that
 * sentence). */
function maturityInfo(
  maturity: FeatureComparisonMaturity | null,
): { label: string; tone: "good" | "review" | "quiet"; detail: string } {
  switch (maturity) {
    case "comparable":
      return {
        label: "Enough evidence to compare",
        tone: "good",
        detail: "The freshest comparison window had enough monitored history on both sides of this change.",
      };
    case "early_signal":
      return {
        label: "Early signal, longer window",
        tone: "review",
        detail:
          "Only a longer, less-fresh comparison window had enough monitored history yet — treat this as provisional.",
      };
    case "insufficient_coverage":
      return {
        label: "Not enough comparable monitoring",
        tone: "quiet",
        detail: "Even the widest comparison window did not have enough monitored history on both sides yet.",
      };
    case "too_soon":
      return {
        label: "Too soon to tell",
        tone: "quiet",
        detail: "Not enough time has passed since this change to compare before and after yet.",
      };
    default:
      return {
        label: "No camera or Zone linked",
        tone: "quiet",
        detail: "Link a camera or Zone to this Feature to compare activity before and after a change.",
      };
  }
}

function observedBySummary(feature: PlaceFeature): string {
  if (feature.observation_links.length === 0) return "No camera linked yet";
  return feature.observation_links
    .map(
      (link) =>
        `${link.source_name}${link.source_archived ? " (archived)" : ""}${
          link.zone_name ? ` — ${link.zone_name}` : ""
        }`,
    )
    .join(", ");
}

export function FeatureComparisonPage({
  onOpenFeatureStory,
  onOpenVisit,
  onOpenPlaceActivityReport,
}: FeatureComparisonPageProps) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [overview, setOverview] = useState<PlaceFeatureComparisonOverview | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [onlySufficientData, setOnlySufficientData] = useState(false);
  const [featureSort, setFeatureSort] = useState<FeatureSortKey>("automatic");
  const [outcomeSort, setOutcomeSort] = useState<OutcomeSortKey>("recent");

  useEffect(() => {
    let active = true;
    setIsLoading(true);
    setError(null);
    apiClient
      .getPlaceFeatureComparison()
      .then((response) => {
        if (active) setOverview(response);
      })
      .catch(() => {
        if (active) setError("Could not load the Feature comparison right now.");
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!isLoading) headingRef.current?.focus();
  }, [isLoading]);

  const featureById = useMemo(() => {
    const map = new Map<string, PlaceFeature>();
    for (const row of overview?.features ?? []) map.set(row.feature.id, row.feature);
    return map;
  }, [overview]);

  const featureRows = useMemo(() => {
    let rows = overview?.features ?? [];
    if (typeFilter !== "all") rows = rows.filter((row) => row.feature.feature_type === typeFilter);
    if (onlySufficientData) rows = rows.filter((row) => row.recent_yield?.data_sufficient === true);
    const sorted = [...rows];
    sorted.sort((a, b) => {
      if (featureSort === "name") return a.feature.name.localeCompare(b.feature.name);
      if (featureSort === "type") {
        const typeCompare = (FEATURE_TYPE_DISPLAY_NAMES[a.feature.feature_type] ?? "").localeCompare(
          FEATURE_TYPE_DISPLAY_NAMES[b.feature.feature_type] ?? "",
        );
        return typeCompare !== 0 ? typeCompare : a.feature.name.localeCompare(b.feature.name);
      }
      if (featureSort === "rate") {
        const rateA = a.recent_yield?.data_sufficient ? a.recent_yield.visits_per_monitored_hour : null;
        const rateB = b.recent_yield?.data_sufficient ? b.recent_yield.visits_per_monitored_hour : null;
        if (rateA == null && rateB == null) return a.feature.name.localeCompare(b.feature.name);
        if (rateA == null) return 1;
        if (rateB == null) return -1;
        return rateB - rateA || a.feature.name.localeCompare(b.feature.name);
      }
      if (featureSort === "recent_change") {
        const dateA = a.latest_change?.event.effective_date ?? null;
        const dateB = b.latest_change?.event.effective_date ?? null;
        if (dateA == null && dateB == null) return a.feature.name.localeCompare(b.feature.name);
        if (dateA == null) return 1;
        if (dateB == null) return -1;
        return dateB.localeCompare(dateA) || a.feature.name.localeCompare(b.feature.name);
      }
      return 0; // "automatic" — preserve the backend's own newest-created-first order.
    });
    return sorted;
  }, [overview, typeFilter, onlySufficientData, featureSort]);

  const outcomeRows = useMemo(() => {
    let rows = overview?.change_outcomes ?? [];
    if (typeFilter !== "all") {
      rows = rows.filter((outcome) => featureById.get(outcome.event.feature_id ?? "")?.feature_type === typeFilter);
    }
    const sorted = [...rows];
    sorted.sort((a, b) => {
      if (outcomeSort === "evidence") {
        const rankA = MATURITY_RANK[a.comparison?.maturity ?? "too_soon"];
        const rankB = MATURITY_RANK[b.comparison?.maturity ?? "too_soon"];
        if (rankA !== rankB) return rankA - rankB;
      }
      return b.event.effective_date.localeCompare(a.event.effective_date);
    });
    return sorted;
  }, [overview, typeFilter, outcomeSort, featureById]);

  if (isLoading) {
    return (
      <div className="page feature-comparison-page">
        <p role="status">Loading Feature comparison…</p>
      </div>
    );
  }

  if (!overview) {
    return (
      <div className="page feature-comparison-page">
        <PageHeader eyebrow="Compare" headingRef={headingRef} title="Compare Features" />
        <EmptyState
          description={error ?? "Could not load Feature comparison right now. Try refreshing the page."}
          title="Could not load Feature comparison"
        />
      </div>
    );
  }

  const typeOptions = Object.entries(FEATURE_TYPE_DISPLAY_NAMES);

  return (
    <div className="page feature-comparison-page">
      <PageHeader
        description="A fair, honest look at your recorded Features and habitat changes — not a leaderboard."
        eyebrow="Compare"
        headingRef={headingRef}
        title="Compare Features"
      />

      {overview.features.length > 0 ? (
        <section aria-label="Filter the comparison" className="panel journal-filter-panel">
          <label>
            Feature type
            <select onChange={(event) => setTypeFilter(event.target.value)} value={typeFilter}>
              <option value="all">All types</option>
              {typeOptions.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <input
              checked={onlySufficientData}
              onChange={(event) => setOnlySufficientData(event.target.checked)}
              type="checkbox"
            />{" "}
            Only Features with enough monitoring to compare
          </label>
        </section>
      ) : null}

      <section aria-label="Compare Features" className="panel feature-comparison-section">
        <h2>Compare Features</h2>
        <p className="meta-text">
          Visits per monitored hour is coverage-normalized and only safe to compare when both Features have enough
          monitoring. Sorting here reflects data available, never an ecological quality judgment.
        </p>
        {overview.features.length > 0 ? (
          <div className="zone-insights-sort">
            <label>
              Sort by
              <select onChange={(event) => setFeatureSort(event.target.value as FeatureSortKey)} value={featureSort}>
                <option value="automatic">Recently added</option>
                <option value="name">Name (A-Z)</option>
                <option value="type">Type</option>
                <option value="rate">Visits per monitored hour</option>
                <option value="recent_change">Most recently changed</option>
              </select>
            </label>
          </div>
        ) : null}
        {featureRows.length === 0 ? (
          <EmptyState
            description={
              overview.features.length === 0
                ? "Record a Feature (a feeder, water source, nest box, or habitat area) on the Place Report page to begin comparing."
                : "No Features match the current filter."
            }
            title="Nothing to compare yet"
          />
        ) : (
          <ul className="feature-comparison-list">
            {featureRows.map((row: PlaceFeatureComparisonRow) => {
              const info = maturityInfo(row.latest_change?.comparison?.maturity ?? null);
              const environmentalSentence = environmentalComparisonSentence(row.latest_change?.environmental_comparison);
              return (
                <li className="feature-comparison-row" key={row.feature.id}>
                  <div className="feature-comparison-thumb">
                    {row.representative_evidence ? (
                      <button
                        className="journal-label-image"
                        onClick={() => onOpenVisit(row.representative_evidence!.visit_id)}
                        type="button"
                      >
                        <RepresentativeThumbnail
                          alt={`Recent wildlife at ${row.feature.name}`}
                          evidence={row.representative_evidence.evidence}
                          fallbackText="No image yet"
                        />
                      </button>
                    ) : (
                      <div className="journal-label-image">
                        <RepresentativeThumbnail alt={row.feature.name} evidence={null} fallbackText="No image yet" />
                      </div>
                    )}
                  </div>
                  <div className="feature-comparison-body">
                    <div className="feature-comparison-heading">
                      <strong>{row.feature.name}</strong>
                      <span className="meta-text">{FEATURE_TYPE_DISPLAY_NAMES[row.feature.feature_type] ?? "Feature"}</span>
                      {!row.feature.is_active ? <StatusPill label="Inactive" tone="quiet" /> : null}
                    </div>
                    <p className="meta-text">Observed by: {observedBySummary(row.feature)}</p>
                    {row.recent_yield ? (
                      <p className="meta-text">
                        Last {row.recent_yield.window_days} days: {row.recent_yield.confirmed_wildlife_visit_count}{" "}
                        confirmed {row.recent_yield.confirmed_wildlife_visit_count === 1 ? "visit" : "visits"},{" "}
                        {row.recent_yield.distinct_taxon_count}{" "}
                        {row.recent_yield.distinct_taxon_count === 1 ? "species" : "distinct species"}
                        {row.recent_yield.data_sufficient && row.recent_yield.visits_per_monitored_hour != null
                          ? ` (${row.recent_yield.visits_per_monitored_hour} per monitored hour)`
                          : " — not enough monitoring yet for a rate"}
                        .
                      </p>
                    ) : (
                      <p className="meta-text">Not enough monitoring linked yet to show recent activity.</p>
                    )}
                    <div className="feature-comparison-latest-change">
                      <StatusPill label={info.label} tone={info.tone} />
                      {row.latest_change ? (
                        <span className="meta-text">
                          {CHANGE_EVENT_TYPE_DISPLAY_NAMES[row.latest_change.event.event_type]} on{" "}
                          {formatDate(row.latest_change.event.effective_date)}
                        </span>
                      ) : (
                        <span className="meta-text">No changes recorded yet</span>
                      )}
                    </div>
                    {row.latest_change?.comparison ? (
                      <p className="meta-text">{featureAssociationSentence(row.latest_change.comparison)}</p>
                    ) : null}
                    {environmentalSentence ? (
                      <p className="meta-text feature-environmental-comparison">{environmentalSentence}</p>
                    ) : null}
                    <div className="today-report-footer">
                      <button className="text-action" onClick={() => onOpenFeatureStory(row.feature.id)} type="button">
                        View {row.feature.name} story
                      </button>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section aria-label="Habitat Change Outcomes" className="panel feature-comparison-section">
        <h2>Habitat Change Outcomes</h2>
        <p className="meta-text">
          Reviewed changes with an attempted before/after comparison. An association describes what was observed
          during the same period — never a cause.
        </p>
        {outcomeRows.length > 0 ? (
          <div className="zone-insights-sort">
            <label>
              Sort by
              <select onChange={(event) => setOutcomeSort(event.target.value as OutcomeSortKey)} value={outcomeSort}>
                <option value="recent">Most recent change</option>
                <option value="evidence">Most evidence available</option>
              </select>
            </label>
          </div>
        ) : null}
        {outcomeRows.length === 0 ? (
          <EmptyState
            description="No Reviewed change has enough monitoring linked yet to attempt a before/after comparison."
            title="No comparable changes yet"
          />
        ) : (
          <ul className="feature-comparison-list">
            {outcomeRows.map((outcome) => {
              const feature = featureById.get(outcome.event.feature_id ?? "");
              const info = maturityInfo(outcome.comparison?.maturity ?? null);
              const environmentalSentence = environmentalComparisonSentence(outcome.environmental_comparison);
              return (
                <li className="feature-comparison-row feature-comparison-outcome-row" key={outcome.event.id}>
                  <div className="feature-comparison-body">
                    <div className="feature-comparison-heading">
                      <strong>{feature?.name ?? "Feature"}</strong>
                      {feature ? (
                        <span className="meta-text">{FEATURE_TYPE_DISPLAY_NAMES[feature.feature_type] ?? "Feature"}</span>
                      ) : null}
                    </div>
                    <p className="meta-text">
                      {CHANGE_EVENT_TYPE_DISPLAY_NAMES[outcome.event.event_type]} on{" "}
                      {formatDate(outcome.event.effective_date)}
                      {outcome.event.note ? ` — ${outcome.event.note}` : ""}
                    </p>
                    <div className="feature-comparison-latest-change">
                      <StatusPill label={info.label} tone={info.tone} />
                    </div>
                    {outcome.comparison ? <p className="meta-text">{featureAssociationSentence(outcome.comparison)}</p> : null}
                    {environmentalSentence ? (
                      <p className="meta-text feature-environmental-comparison">{environmentalSentence}</p>
                    ) : null}
                    {feature ? (
                      <div className="today-report-footer">
                        <button className="text-action" onClick={() => onOpenFeatureStory(feature.id)} type="button">
                          View {feature.name} story
                        </button>
                      </div>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <div className="today-report-footer">
        <button className="secondary-action" onClick={onOpenPlaceActivityReport} type="button">
          Back to Place Report
        </button>
      </div>
    </div>
  );
}
