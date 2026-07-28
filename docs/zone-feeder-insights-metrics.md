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

The current durable monitoring store keeps the latest runtime generation,
latest healthy frame, and bounded Camera Health incidents—not a complete uptime
ledger. Healthy monitored time is therefore the selected-range overlap of that
latest generation from its saved start through its fresh-frame/stop/failure
boundary, minus overlapping saved unhealthy incidents. Disabled, failed,
recovering, stale, and unavailable periods are not counted. When those facts do
not support an interval, exposure and normalized rate are null rather than
estimated.

Visits per monitored hour is returned only with at least two supported healthy
hours. Zone ranking by rate is shown only for `sufficient` results. Results warn
for fewer than two healthy hours, fewer than five reviewed Visits, less than
50% review coverage, no confirmed activity, or unavailable exposure. Evidence
success percentage is deliberately unavailable because durable capture-attempt
history is not retained.

Every aggregate links to the existing Activity Library with its time, Source,
Stream, Zone, reviewed-outcome, and confirmed-species filters so it can be
audited without a second Visit browser.
