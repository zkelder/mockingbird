import type { PlaceActivityReportSourceActivity } from "../api/types";

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

/**
 * Place / Yard Intelligence v2, Phase 7: coverage-normalized cross-Source
 * activity comparison, mirroring ZoneActivityList's own bar-list style. A
 * Source below the minimum-monitored-hours floor (`data_sufficient: false`)
 * still shows its raw confirmed count but never a fabricated rate, and
 * sorts after every sufficient Source (matching `compute_source_activity`'s
 * own ranking, which this list preserves rather than re-sorting).
 *
 * Multi-Camera Place Experience v2: extracted out of PlaceActivityReportPage.tsx
 * into its own shared component so TodayReportPanel.tsx can reuse this exact
 * presentation for its own compact "By camera" section -- one canonical
 * per-camera activity comparison, never a second, drifting bar list.
 */
export function SourceActivityList({ sources }: { sources: PlaceActivityReportSourceActivity[] }) {
  const maxRate = sources.reduce((max, source) => Math.max(max, source.visits_per_monitored_hour ?? 0), 0);
  return (
    <div className="bar-list" aria-label="Wildlife activity by camera">
      {sources.map((source) => (
        <div className="bar-row" key={source.source_id}>
          <span>{source.source_name}</span>
          <div>
            {source.data_sufficient && source.visits_per_monitored_hour !== null && source.visits_per_monitored_hour !== undefined ? (
              <>
                <i
                  style={{
                    width: `${maxRate > 0 ? Math.max((source.visits_per_monitored_hour / maxRate) * 100, 4) : 4}%`,
                  }}
                />
                <strong>{source.visits_per_monitored_hour.toFixed(2)} / hour</strong>
              </>
            ) : (
              <span className="meta-text">
                {plural(source.confirmed_wildlife_visit_count, "visit")} · not enough monitoring to compare
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
