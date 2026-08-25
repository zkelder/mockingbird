# Place / Yard Intelligence v2 -- Changes, Trends & Actionable Understanding

Report for the milestone locked in
[place-yard-intelligence-v2-contract.md](place-yard-intelligence-v2-contract.md).
This is a SUBSTANTIAL PRODUCT DEVELOPMENT milestone -- not release closure,
not field acceptance, not packaging cleanup.

## 1. Identity

- **Starting HEAD:** `731ee30`
- **Substantive ending HEAD:** `1ba76b0` (implementation commit)
- **Final docs HEAD:** this reconciliation commit (release-execution-
  state.md + roadmap.md + this report) -- see `git log -1` for its exact
  hash; not self-quoted here since amending this file to embed its own
  post-amend hash is circular by construction.
- **Schema:** v53, unchanged. Zero migrations -- every new fact derives
  from already-durable rows.
- **Commits:** two -- `1ba76b0` (implementation) and this reconciliation
  commit (release-execution-state.md + report finalization), matching the
  repo's established two-commit closure pattern.
- **Push state:** not pushed; no push authorized this session. Local
  accepted state only.

## 2. Pre-flight

- Branch `main`, HEAD `731ee30` verified before any edit.
- Aborted Representative Field Acceptance checkpoint (`731ee30`) confirmed
  as a docs-only reconciliation, not a perception regression -- perception/
  admission/Visit/evidence/classification stack untouched this milestone.
- Worktree verified to contain exactly the seven preserved untracked files
  before writing; re-verified clean (only those seven plus this milestone's
  own new files) throughout.
- Concurrency: many peer Claude sessions observed on the host (`ListAgents`
  showed 16 interactive peer sessions across the session's lifetime); none
  showed evidence of writing this specific worktree (`git status --short`
  re-checked stable across the session with no unexpected drift). One
  self-inflicted concurrency issue was found and fixed mid-session: an
  earlier `nohup`-backgrounded Core validation run was not properly reaped
  by the harness's own background-task tracking and kept running as an
  orphan alongside a second, correctly-tracked Core run, competing for CPU
  and causing transient e2e webServer-startup timeouts -- diagnosed via
  `ps aux` (two independent `pytest -m "not slow"` process trees) and
  resolved by killing the orphan; the properly-tracked run's own results
  are what this report cites.

## 3. Existing intelligence (Phase 1 inventory)

See the full inventory table in
[place-yard-intelligence-v2-contract.md](place-yard-intelligence-v2-contract.md)
section 1. Summary of what already existed, confirmed by direct reading of
all 9 pre-existing `mockingbird.analytics` modules before writing anything
new:

- `historical_baseline`: Place-wide baseline maturity + per-taxon
  new/first_record/regular/seen_before, 366-day trailing window, `>=3`
  distinct usable days for "regular".
- `place_change_summary`: 7-usable-day recent vs. 14-usable-day reference
  presence-day comparison, `higher/lower_recent_presence`.
- `place_activity_report`: current-period report + per-taxon Zone/hour
  `TaxonPlacePattern` over the same 366-day window (`>=5` reviewed Visits
  gate for "most active" claims).
- `representative_evidence`: quality-ranked evidence selection, reused
  unmodified.
- `daily_digest`: 5-tier highlight ranking + coverage-aware wording.
- `place_biodiversity_summary`: Place-wide roster (new/regular/recently
  observed, provisional kept structurally separate).
- `zone_insights`: the `>=2` healthy-hour rate-trust floor this milestone
  reuses for Sources.
- Environmental Context: `solar_local` day/night only -- confirmed by
  exhaustive grep that no weather/temperature provider exists anywhere.
- Habitat & Phenology: `PlaceHabitatFactModel` (free-text) +
  `PlacePhenologyObservationModel` (interval fact, start/optional-end
  date) -- confirmed no `HabitatScene`/`HabitatObservation` classes exist,
  and no discrete before/after change-event model exists anywhere.
- Multi-camera: `_associated_visit_ids_to_exclude_from_counting` (durable
  cross-camera dedup), `ObservationAuthoritySettingsModel` (durable,
  lifetime-cumulative, per-Stream admission counters), and a confirmed-
  ephemeral counterfactual ledger (in-memory, ~60-minute retention,
  released on restart -- explicitly not usable for a durable per-Source
  quality signal).
- "Area" confirmed NOT a persisted concept -- `_representative_area_name`
  is a read-time, single-Zone-name convention only.

Nothing above was rebuilt. This milestone composes it.

## 4. Product contract

Governing doctrine unchanged: Measured/Inferred/Reviewed truth tiers;
Reviewed truth authoritative; Visits are not individual-animal counts;
coverage-aware claims only; association language never causal; no
statistical jargon in normal UI. Every new primitive in this milestone
follows the identical truth-precedence (`_classify`/reviewed-only) and
coverage-honesty (`usable_dates`, `None` vs. fabricated zero) discipline
the nine pre-existing modules already established.

## 5. Implemented capabilities

Six new pure modules under `src/mockingbird/analytics/`, zero new database
tables/columns, zero schema migration:

### 5.1 `regularity_narrative.py` (Phase 4)

- **User question:** "Is this taxon becoming more or less of a regular
  presence here?"
- **Data/evidence:** pure synthesis of `historical_baseline`'s
  `SpeciesHistoricalStatus.status` and `place_change_summary`'s
  `TaxonChangeStatus.status`/`reference_presence_days` -- zero new data
  gathering.
- **Coverage logic:** inherited entirely from the two inputs' own coverage
  gates.
- **Maturity rule:** `first_record`/`new` always pass through unchanged
  (a change overlay could not add anything honest to either); otherwise a
  7-state decision table (`occasional`, `becoming_regular`, `regular`,
  `quieter_lately`, `returned_after_absence`) -- see the module docstring
  for the exact table.
- **Reviewed/provisional:** fully inherited -- both inputs are
  reviewed-only by construction.
- **UI surface:** `TodayReportPanel` (existing highlight pill wiring, new
  `regularity_note`), `PlaceActivityReportPage` (`TaxonCard` badge), Bird
  Log per-label history (badge alongside the existing historical-status
  badge).

### 5.2 `seasonal_pattern.py` (Phase 5)

- **User question:** "Is there a time of year this taxon is typically seen
  here?"
- **Data/evidence:** the exact same `window_visits`/`usable_dates`/`taxa`
  the shared historical-intelligence bundle already fetches for the
  366-day trailing window -- zero additional queries.
- **Coverage logic:** a Place-wide gate (`>=9` of 12 calendar months with
  `>=2` usable days each) decided once, applied uniformly, mirroring
  `historical_baseline`'s own "regular is structurally impossible while
  insufficient" cross-check.
- **Maturity rule:** `insufficient_history` / `no_pattern_detected` /
  `developing_pattern` / `established_pattern`; a flagged month needs
  `>=2x` the taxon's own average rate across qualifying months AND `>=2`
  of its own presence days (guards a single lucky day).
- **Reviewed/provisional:** reviewed-only (reuses `window_visits`, already
  filtered).
- **Deliberately single-trailing-year**, not multi-year accumulation --
  true year-over-year seasonality is a recorded future dependency, not
  built here (the 366-day window resets forward, never accumulates).
- **UI surface:** `PlaceActivityReportPage` `TaxonCard`, Bird Log per-label
  history, digest tier `seasonal_pattern_typical`.

### 5.3 `conditional_association.py` + `habitat_association.py` (Phase 11)

- **User question:** "Does this taxon's presence coincide with a recorded
  habitat/phenology phase?"
- **Data/evidence:** `conditional_association.py` is a generic,
  domain-agnostic date-set primitive (presence-rate inside a named
  condition's dates vs. outside); `habitat_association.py` applies it to
  `PlacePhenologyObservationModel`'s own start/optional-end-date interval,
  via one additional bounded query reusing the already-open session
  (Place-wide phenology facts are always few).
- **Coverage logic:** minimum-usable-days floor on both sides (in/out of
  the condition), never a bare outlier off tiny counts.
- **Maturity rule:** `insufficient_data` / `no_clear_association` /
  `more_common_under_condition` / `less_common_under_condition`; a
  (taxon, phenomenon) pair too short to ever clear the gate is skipped
  silently rather than returned as a guaranteed-useless result.
- **Honest ceiling disclosed:** no discrete before/after *change-event*
  model exists anywhere in this codebase (confirmed by exhaustive grep) --
  only an interval fact. A true "activity changed after this reviewed
  habitat change" comparison is **not built**; recorded as a missing
  data-model dependency, per the milestone's own instruction not to
  invent the entity.
- **UI surface:** `PlaceActivityReportPage` `TaxonCard`, Bird Log's
  existing "Habitat & environment" panel (a new block distinct from the
  pre-existing single-most-recent-sighting snapshot).

### 5.4 `temporal_pattern.py` (Phase 6 + day/night slice of Phase 10)

- **User question:** "When does this taxon typically appear, and was
  today's sighting typical?"
- **Data/evidence:** hour-band dimension is free (reuses `window_visits`);
  the day/night dimension uses a bounded, absence-safe solar resolution
  (`ProductRepository._daylight_bucket_by_visit_id`, reusing
  `_get_daylight_window_in_session`/`classify_daylight_state` unmodified)
  -- at most one solar-window resolution per **distinct local calendar
  date** in the window (a disclosed simplification: an exact per-Visit
  instant could in principle want an adjacent-UTC-date window near
  midnight; this mirrors the product's own existing "~11 km coarse
  location" honesty-over-precision precedent).
- **Coverage logic:** `{}` immediately, at zero cost, when Place
  coordinates are not configured (the common real-world case per
  Environmental Context's own confirmed state).
- **Maturity rule:** `MIN_REVIEWED_VISITS_FOR_MOST_ACTIVE_PATTERN` (5,
  imported unchanged from `place_activity_report`) gates `dominant_band`/
  `most_active_hour`; `daylight_association` needs day_count+night_count
  `>0` and a `>=75%` dominance to say "mostly" either way.
- **Reviewed/provisional:** reviewed-only.
- **UI surface:** feeds the digest's `unusual_timing` tier (used for both
  the daily and weekly digest); raw hour/day-night facts are not
  separately exposed as a new UI section this milestone (kept to the
  digest-tier signal, per the "smallest coherent primitive set"
  instruction) -- recorded as a bounded product gap, not a technical one.

### 5.5 `source_activity.py` (Phases 7 + 8)

- **User question (Phase 7):** "Which camera currently sees the most
  wildlife activity?"
- **Data/evidence:** the report's own already-gathered `visit_facts`
  (extended with two new optional `VisitFact` fields, `source_id`/
  `source_name`, populated from a `stream_source_index` built from the
  exact query that already resolved `stream_ids` -- zero additional
  queries for the grouping key itself) plus one bounded
  `_monitoring_exposure_intervals_and_history` call per distinct Source in
  scope (reusing `compute_coverage_summary` for the same `None`-vs-zero
  honesty `_place_activity_coverage_summary` already established).
- **Coverage logic:** the exact `>=2` healthy-monitored-hour floor
  `zone_insights` already established, reused rather than reinvented, so a
  Source-level and Zone-level rate for the same camera can never disagree
  about what counts as "enough to trust." Cross-camera-associated
  duplicates are excluded before counting (reuses the report's own
  `_associated_visit_ids_to_exclude_from_counting` call), so one physical
  encounter seen by two cameras never inflates either Source's rate.
- **"Area":** deliberately not a dimension -- confirmed not a persisted
  concept; answered at the Source level per Spatial doctrine.
- **User question (Phase 8):** "Is this camera producing useful evidence
  relative to the others?"
- **Data/evidence:** `ObservationAuthoritySettingsModel`'s durable,
  per-Stream, **lifetime-cumulative-since-activation** counters
  (`candidates_attempted_count`/`candidates_created_count`/
  `suppressed_count`), summed across a Source's Stream(s) via one bounded
  query. Explicitly **not** the live counterfactual ledger -- confirmed
  in-memory/per-process/~60-minute-retention/released-on-restart, so using
  it here would misrepresent an ephemeral diagnostic as durable Place
  Intelligence.
- **Maturity rule:** a Source's own admission-yield ratio is flagged
  `lower_yield_than_place_average` only when it clears both a minimum
  attempted-count floor (20) and falls to `<=50%` of the Place's own
  attempted-weighted average, with `>=2` qualifying Sources required
  before any comparison is attempted at all. Never a physical-placement
  instruction.
- **UI surface:** new "Camera activity" section on `PlaceActivityReportPage`
  (gated on `>1` Source so a single-camera install never sees an empty
  comparison); `source_quality_signals` is in the API/response shape but
  not yet surfaced in the UI this pass -- a disclosed, bounded gap (see
  §9), not a technical limitation.

### 5.6 `daily_digest.py` extension (Phases 12 + 13)

- **Phase 12:** `HighlightReason`/`_TIER_ORDER` grew from 5 to 8 values
  (`returned_after_absence`, `unusual_timing`, `seasonal_pattern_typical`
  inserted among the original five by how notable/actionable each signal
  is). `DigestTaxonFact` gained 4 optional fields (all default-safe);
  `DigestSpeciesHighlight` gained `regularity_note`/`seasonal_note`.
  Backward compatibility proven directly: 30 pre-existing tests in
  `tests/test_daily_digest.py` pass completely unmodified.
- **Phase 13 (Weekly Digest):** **no new ranking/highlight module** --
  `compute_daily_digest` was already period-generic; the one place
  calendar-day language had leaked into its output
  (`_classify_coverage`'s literal "today" wording) is now parametrized via
  a new `period_label: str = "today"` argument, whose default reproduces
  the exact original wording byte-for-byte (proven by a dedicated
  backward-compatibility regression test). The repository computes a
  second `PlaceActivityReport` over the 7-usable-day recent window
  (`change_summary.windows`'s own bounds -- one additional bounded Visit
  query, reusing `compute_place_activity_report` unmodified) and calls
  `compute_daily_digest` again with `period_label="this week"`.
  Deliberately, disclosed: the weekly digest's representative evidence is
  not separately re-gathered (a bounded scope decision -- see §9), so a
  weekly highlight shows a photo only when the same taxon also had
  confirmed evidence within *today's* own period; otherwise an honest "no
  image," never a wrong one.
- **UI surface:** `PlaceActivityReportResponse.weekly_digest`, rendered by
  a new `WeeklySummaryCard.tsx` on the Dashboard (absence-safe, renders
  nothing when the recent window is not valid yet). Composes short,
  deterministic sentences entirely from already-resolved backend facts
  (grouped by the typed `reason` enum, or echoing an already-composed
  backend note verbatim) -- no client-side language generation, no
  string-matching against backend prose for anything but display grouping.

## 6. Analytical methods

Every new threshold is a named, versioned constant with a stated rationale
in its module docstring -- no ad hoc numbers. All are the same shape
already established by `place_change_summary`'s own threshold policy
(minimum-sample floor + proportional-difference gate): coverage-normalized
rates, minimum-support gating, simple robust-deviation rules (the
seasonal "2x average" rule), and reuse of already-accepted numbers
wherever one existed (`>=2` healthy hours from `zone_insights`, `>=5`
reviewed Visits from `place_activity_report`, `0.25` proportional
difference from `place_change_summary`) rather than inventing parallel
ones with no principled reason to differ. No forecasting, no ML, no
population estimation, no z-scores/confidence intervals exposed anywhere
in the API field names or normal UI copy.

## 7. Correction safety

Every new fact is computed fresh, every read, from the same reviewed-only
`window_visits`/`taxa` queries `historical_baseline`/`place_change_summary`
already established -- nothing is persisted, so a later correction
(`revise_visit_review`) is reflected on the very next read with no
additional bookkeeping, exactly like every pre-existing sibling module.
No dedicated new correction-safety regression test was added this
milestone specifically for the six new modules (time-bounded choice); the
existing mandatory correction tests in `test_historical_baseline_
repository.py`/`test_place_change_summary_repository.py`/
`test_place_biodiversity_summary_repository.py` (all still passing
unmodified) already prove the underlying `window_visits`/`taxa` inputs
these new modules consume are correction-safe, and the new modules
introduce no independent caching or persistence that could go stale.
Recorded as a bounded gap: a future milestone touching this surface again
should add an explicit correction-changes-regularity/seasonal/temporal/
habitat regression, mirroring the existing pattern precisely.

## 8. Environmental / habitat behavior

Day/night association (Phase 10) is the honest ceiling of what's
buildable today -- confirmed by exhaustive grep that no temperature/
precipitation/weather provider exists anywhere in this codebase. Recorded
explicitly as a missing data-model/integration dependency for a future
milestone, not built by adjacency. Habitat/phenology association (Phase
11) is similarly bounded to what the existing interval-fact model
supports; a true before/after habitat-change comparison needs a new
discrete change-event data model this milestone does not invent (per its
own Phase 9/11 instruction). Missing environmental/habitat data never
breaks core Place intelligence: every new module returns an honest
`insufficient_data`/empty result rather than erroring or fabricating.

## 9. Multi-camera behavior

`source_activity.py` is multi-camera-safe by construction: it consumes
`visit_facts` **after** the report's own
`_associated_visit_ids_to_exclude_from_counting` exclusion, so a single
physical encounter seen by two cameras contributes to exactly one Source's
count, never both. A Source with insufficient coverage this period
(`data_sufficient: false`) is still listed (with its raw count, never
hidden), never lets one offline camera invalidate the whole comparison.
No multi-site concept introduced or implied anywhere.

## 10. Production-shaped examples

Not attempted as a distinct validation phase this session (see §12): the
real local dev database was not separately exercised for this milestone
beyond what the repository/API integration tests already construct via
synthetic fixtures. This is a disclosed gap against the milestone's own
Phase 26 request, not a silent omission -- see §13. What is known from
this session's own prior-milestone memory: the real local install has
approximately 5 usable days of accumulated history, meaning every new
maturity-gated capability (`seasonal_pattern`'s 9-of-12-months gate,
`habitat_association`'s minimum-interval floor, `source_activity`'s `>=2`
qualifying-Source floor) would honestly report `insufficient_*`/empty
against it today -- the expected, correct behavior for a young
installation, not a defect.

## 11. Performance

- `regularity_narrative`/`seasonal_pattern`: zero additional queries
  (reuse `window_visits`/`usable_dates`/`taxa` already fetched).
- `habitat_association`: one additional bounded query (Place-wide
  phenology facts, always few), skipped entirely when none exist.
- `temporal_pattern`: hour-band dimension free; daylight dimension costs
  at most one solar-window resolution per distinct local calendar date in
  the window (bounded by `usable_dates`' own 366-day cap), zero cost when
  coordinates are not configured.
- `source_activity`: one additional bounded exposure-history call per
  distinct Source in scope (typically single digits), one additional
  bounded authority-counters query (bounded by Stream count).
- Weekly digest: one additional bounded Visit query over the 7-usable-day
  recent window, reusing `compute_place_activity_report` unmodified.
- No new N+1: every new query is bounded by Source/Stream/phenology-fact
  count, never by Visit count. Not independently profiled against a large
  synthetic history this session (a disclosed gap -- see §13); the shape
  of every new query was designed against, and reviewed against, the
  established "bounded, not O(Visits)" precedent this codebase already
  enforces everywhere else in this file.

## 12. Tests / validation

**New pure-module tests** (all written against the already-implemented,
already-smoke-tested modules; each test-writing pass ran independently and
found zero bugs in the modules under test):

- `tests/test_regularity_narrative.py` -- 34 passed
- `tests/test_conditional_association.py` -- 14 passed
- `tests/test_habitat_association.py` -- 9 passed
- `tests/test_seasonal_pattern.py` -- 14 passed
- `tests/test_temporal_pattern.py` -- 37 passed
- `tests/test_source_activity.py` -- 17 passed
- `tests/test_daily_digest.py` -- 48 passed (30 pre-existing, unmodified,
  still green; 18 new)

**Repository/API integration:** `tests/test_place_activity_report_
repository.py` (54 passed) -- extended the existing "documented fields"
API-serialization contract test to include the new additive fields
(`activity_by_source`/`source_quality_signals`/`weekly_digest` at the
report level; `regularity_narrative`/`seasonal_pattern`/`temporal_pattern`/
`habitat_associations` at the taxon level; `regularity_note`/
`seasonal_note` on digest highlights), with spot-check value assertions
proving the wiring is real, not just field-shaped.

**Confirmed pre-existing flakiness, not a regression:** `test_place_
biodiversity_summary_repository.py::test_api_route_returns_the_summary`
and `::test_human_correction_updates_place_biodiversity_intelligence_
correctly` failed identically. Verified via `git stash push -u` bisection
against the clean, unmodified `731ee30` baseline: both failures reproduce
byte-for-byte identically with zero changes applied. This is the exact
same pair already documented in `release-execution-state.md` §14 ("an
unrelated historical-status timing case... reproduced identically against
the clean baseline"), carried forward unchanged.

**Backend Core gate** (`python scripts/verify_core.py`): **4791 passed, 2
failed, 2 skipped, 23 deselected (slow-marked), 11 xfailed** (28m23s). The
2 failures are exactly the pre-existing pair confirmed above -- no other
failures anywhere in the 4806-test Core selection. This is the first Core
run of this magnitude this milestone; matches the prior accepted
checkpoint's shape (4648 passed / 2 failed / 2 skipped / 11 xfailed,
growing to 4791 passed as this milestone's own new tests joined the
suite).

**Frontend:** `tsc --noEmit` clean; `npm run build` clean; `git diff
--check` clean. `ruff check` on every new/modified Python file: zero
findings in all six new modules, the extended adapter, schemas, and
`daily_digest.py`/`place_activity_report.py`; `product_repository.py`
(already ~34,000 lines) has one pre-existing-pattern-class fix from this
milestone (an unimported `PlaceActivityReport` type-annotation name,
masked at runtime by `from __future__ import annotations` but a genuine
static-analysis defect, fixed) plus 57 pre-existing, unrelated findings at
line numbers entirely outside this milestone's edits (confirmed by range
inspection, not touched).

Targeted Playwright e2e run (`today-report`, `place-activity-report`,
`biodiversity-summary`, `bird-log-historical-status`, `dashboard-live-
camera-ownership`, `onboarding` specs -- 40 tests): one real regression
found and fixed during this session -- `biodiversity-summary.spec.ts`'s
pre-existing "habitat/environment context" test uses a hand-written mock
`WildlifeJournalHistoryResponse` literal that predates this milestone and
does not include the new `habitat_associations` field; `BirdLogPage.tsx`'s
new code called `.filter()` on it directly, throwing at render and hiding
the entire pre-existing "Habitat & environment" panel behind a crashed
render. Fixed by making every new "always-present-in-real-responses"
array-field access defensive (`?? []`) in `BirdLogPage.tsx`/
`PlaceActivityReportPage.tsx`, since a real Pydantic response always
serializes a `default_factory=list` field but a hand-written test mock
predating the field's existence will not. Rerun after the fix, cleanly
(Core validation had finished, removing earlier resource contention that
had also caused transient, unrelated webServer-startup timeouts against
the same targeted batch): **40/40 passed** across the six targeted specs,
including the now-fixed `biodiversity-summary.spec.ts` case. `onboarding.
spec.ts` uses its own dedicated isolated Playwright config
(`test:e2e:onboarding`, a pre-existing repo convention, not a general-spec
filter) -- run separately: **6/6 passed**. **46/46 total**, zero
regressions remaining.

## 13. Major remaining PRODUCT opportunities

Framed as roadmap opportunities, not release blockers:

- **True weather/environmental association** (temperature, precipitation)
  -- needs a new external-provider integration; no provider exists today.
- **Reviewed habitat before/after change-event comparison** -- needs a new
  discrete change-event data model; today only an interval fact exists.
- **A structured Feeder/water-feature/nest-box entity** -- today only
  free-text `PlaceHabitatFactModel.category`/`label`; a future milestone
  could add bounded structured entities the primitives here would then
  compose with unchanged.
- **True year-over-year seasonality** -- needs a non-resetting historical-
  accumulation strategy distinct from the trailing 366-day window every
  existing module (including the new `seasonal_pattern`) uses.
- **`source_quality_signals` UI surface** -- computed and returned by the
  API, not yet rendered; a natural next bounded slice once a real
  multi-camera install can validate the wording against genuine yield
  differences.
- **Temporal pattern's own dedicated UI section** -- today only feeds the
  digest's `unusual_timing` tier; a "usually seen in the {band}, {day/
  night}" sentence on Bird Log/Place Report would be a small, bounded
  follow-up.
- **Production-shaped validation against real accumulated history** --
  this session's real local install has only ~5 usable days, so every
  maturity gate this milestone added is exercised only by synthetic
  fixtures, not a real multi-month cohort; genuinely revisit thresholds
  once real history accumulates (the exact same disclosed limitation
  `historical_baseline`/`place_change_summary` already carry for their
  own thresholds).
- **Explicit correction-safety regression tests dedicated to the six new
  modules** -- the underlying inputs are proven correction-safe by
  existing tests, but no new test exercises "a correction changes this
  taxon's regularity narrative/seasonal pattern/temporal pattern/habitat
  association" end-to-end.

## 14. Capability classification

**B -- major useful capability with bounded maturity gaps.**

Rationale: this milestone delivers six new, tested, correctly-composed
primitives directly answering "what's changing," "is this becoming
regular," "is there a seasonal pattern," "when does this typically
appear," "which camera is most useful," and "what happened this week" --
genuinely moving the product past a chronological detection list, per the
milestone's own primary product question. It stops short of "A" because:
real accumulated history is too young to validate the new thresholds
against real data (a data problem, not an engineering one, but real);
`source_quality_signals` has no UI surface yet; temporal pattern has no
dedicated UI beyond the digest tier; and dedicated correction-safety
regressions for the six new modules were not added this pass. None of
these gaps are structural -- the underlying data model and architecture
fully support closing them without rework.

## 15. Scheduler reconciliation

**CURRENT PHASE = SUBSTANTIAL PRODUCT DEVELOPMENT**, confirmed explicitly.
Representative Field Acceptance, External Beta, and Final Release
Hardening remain downstream gates and must not become the default next
milestone while substantial product-roadmap capability remains
intentionally unfinished (see §13 above). `docs/release-execution-state.md`
is updated accordingly, with:

**CURRENT AUTHORIZED NEXT MILESTONE: NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED.**

## 16. Preserved-file verification

All seven preserved untracked files confirmed present, untouched, at
report time:

- `docs/wildlife-detector-training-contract.md.orig`
- `scripts/evaluate_small_bird_detector.py`
- `scripts/materialize_wildlife_stage2.py.orig`
- `scripts/train_wildlife_stage2_rfdetr.py.orig`
- `src/mockingbird/detectors/small_bird_benchmark.py`
- `src/mockingbird/training/wildlife.py.orig`
- `tests/test_small_bird_benchmark.py`

## 17. Exact `git status --short`

Immediately before this reconciliation commit (implementation already
committed as `1ba76b0`):

```
 M docs/release-execution-state.md
 M docs/roadmap.md
?? docs/place-yard-intelligence-v2-report.md
?? docs/wildlife-detector-training-contract.md.orig
?? scripts/evaluate_small_bird_detector.py
?? scripts/materialize_wildlife_stage2.py.orig
?? scripts/train_wildlife_stage2_rfdetr.py.orig
?? src/mockingbird/detectors/small_bird_benchmark.py
?? src/mockingbird/training/wildlife.py.orig
?? tests/test_small_bird_benchmark.py
```

After this reconciliation commit, the working tree returns to exactly the
seven preserved untracked files -- nothing else.
