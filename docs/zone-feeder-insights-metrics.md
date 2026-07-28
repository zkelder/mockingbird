# Zone and Feeder Insights Metrics

Zone Insights is a bounded, read-only comparison of active feeder, birdbath,
perch, ground, yard, and driveway Zones. A **Visit** is an activity session,
not a unique individual bird; a bird can create more than one Visit after it
leaves and returns.

## Truth and activity

- A confirmed bird Visit is an active, non-superseded Visit with a current
  reviewed bird correction. Detector output and SpeciesSuggestion evidence do
  not count.
- Confirmed species composition and richness include only reviewed bird taxonomy
  species. Generic bird corrections count as confirmed bird activity but not as
  a confirmed species.
- Blank, false-positive, non-bird, unresolved, ambiguous, rejected, and
  superseded Visits remain outside confirmed bird and species metrics.
- Visit duration is the existing evidence-frame activity window when available,
  otherwise the Event window. Dwell totals and medians are sums/statistics of
  those confirmed Visit durations.

## Monitoring exposure and confidence

Durable exposure history begins only when a Stream receives its first fresh
monitoring frame. It records bounded healthy intervals, updates their
fresh-frame checkpoint no more often than the configured cadence, and closes
them on failure, staleness, disablement, orderly shutdown, or unclean restart.
Zone Insights clips and unions those intervals for the selected range, never
infers uptime from enabled intent, runtime checkpoints, Camera Health, or a
calendar day.

Each metric returns the first durable exposure date, whether the selected range
predates that history, and the number of contributing intervals. When the
selected range starts before durable history, its earlier portion is excluded
and the UI warns explicitly. A Stream with no durable interval has unavailable
exposure; a Stream with history but no overlap has zero exposure. Mixed Stream
selections with missing history withhold the aggregate normalized rate rather
than combining known exposure with assumed uptime.

Visits per monitored hour is returned only with at least two supported healthy
hours. Zone ranking by rate is shown only for `sufficient` results. Results warn
for fewer than two healthy hours, fewer than five reviewed Visits, less than
50% review coverage, no confirmed activity, or unavailable exposure. Evidence
success percentage is deliberately unavailable because durable capture-attempt
history is not retained.

Every aggregate links to the existing Activity Library with its time, Source,
Stream, Zone, reviewed-outcome, and confirmed-species filters so it can be
audited without a second Visit browser.
