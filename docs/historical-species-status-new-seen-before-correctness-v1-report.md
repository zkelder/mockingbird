# Historical Species-Status ("New" vs. "Seen Before") Correctness v1

A release-correctness milestone closing two reproduced `tests/
test_place_biodiversity_summary_repository.py` failures that had recurred,
unfixed, across at least nine consecutive prior full-Core checkpoints (see
`docs/release-execution-state.md` §14) without ever being assigned their own
dedicated investigation.

## Starting state

- Branch `main`, HEAD `98f1138c63ebf648e1c6b864a4d326b32f9861a9`, confirmed
  unpushed (`+244 -0` ahead of `origin/main`).
- Schema: v58 (`CURRENT_DATABASE_SCHEMA_VERSION`), unchanged by this
  milestone.
- The seven preserved untracked detector-training files (`docs/wildlife-
  detector-training-contract.md.orig`, `scripts/evaluate_small_bird_
  detector.py`, `scripts/materialize_wildlife_stage2.py.orig`, `scripts/
  train_wildlife_stage2_rfdetr.py.orig`, `src/mockingbird/detectors/
  small_bird_benchmark.py`, `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`) confirmed present and untouched at
  both start and close, byte-identical, alongside this milestone's own one
  committed change. No active writer was found modifying this worktree
  before starting (no relevant `pytest`/product `python` process, no git
  lock files). An untracked root `uv.lock` (mtime predating this session's
  first command) was observed, matching this file's own repeatedly-recorded
  "ordinary `uv run` side effect in an actively-shared worktree" precedent;
  left untouched rather than spending this milestone's own scope on it,
  since it is not one of the seven protected files and this milestone
  neither ran nor needed any `uv` command.
- Reproduced failures, confirmed RED against the unmodified pre-fix code
  (see "RED," below): `tests/test_place_biodiversity_summary_repository.py::
  test_api_route_returns_the_summary` and `::test_human_correction_updates_
  place_biodiversity_intelligence_correctly`.

## Contract

The canonical semantics (`mockingbird.analytics.historical_baseline.
compute_species_historical_statuses`, see `docs/canonical-new-regular-
species-contract.md` and `docs/historical-baseline-maturity-contract.md`)
are unchanged by this milestone and were not violated by either implicated
call site:

- **`"new"` / `"first_record"`** -- a taxon's all-time-earliest reviewed
  confirmation falls within `[period_start_at, period_end_at)`. Both are the
  same underlying fact ("this is genuinely the first-ever confirmed record
  of this taxon at this Place"); `"new"` is worded only once Place-wide
  baseline maturity is `"established"` (>= 7 usable monitored days),
  `"first_record"` otherwise -- never both, never neither.
- **`"regular"`** -- confirmed on >= `MIN_DISTINCT_USABLE_DAYS_FOR_REGULAR`
  (3) distinct *usable* (>= 2h durably monitored) days within the trailing
  366-day window, and structurally impossible while baseline maturity is
  `"insufficient"`.
- **`"seen_before"`** -- confirmed previously, neither new this period nor
  yet regular.
- Priority order is fixed and single-sourced: `"new"`/`"first_record"` is
  checked first (an all-time, unbounded fact), then `"regular"`, then
  `"seen_before"` as the residual case. Every consumer reaches this through
  the one shared `ProductRepository._historical_place_baseline_and_species_
  statuses` adapter -- never a second, independently-drifting computation.

**`ProductRepository.place_biodiversity_summary`** (`GET /api/place/
biodiversity-summary`) and **`ProductRepository.wildlife_journal_history`**
(`GET /api/bird-log/journal/{label}`) are both, explicitly and by product
design, **"live view" endpoints** -- not fixed report periods. Both call the
shared helper with `period_start_at=`today's Place-local midnight,
`period_end_at=`the real instant the request is handled (`datetime.now()`,
un-overridable through either HTTP route). This is documented, deliberate
behavior in three independent places: `place_biodiversity_summary`'s own
docstring ("mirrors `wildlife_journal_overview`'s exact session/anchoring
convention... a live view, not a fixed report period"); `docs/biodiversity-
place-intelligence-v1-contract.md` ("a live view, not a fixed report
period... `generated_at` -- when this read was produced; re-requesting
later can honestly change the answer"); and `docs/canonical-new-regular-
species-contract.md` ("Bird Log is a live view rather than a fixed report
period, so 'today' (as of the moment of the request) is its equivalent
narrow window"). A confirmation reads `"new"`/`"first_record"` through
these two endpoints only on the Place-local calendar day it was actually
first confirmed; a day later, the identical underlying fact correctly reads
`"seen_before"` (or `"regular"` once it recurs enough). This is not a gap
this milestone had license to redefine (see "Root cause," below, for why it
is also not the cause of the two reproduced failures).

## Root cause

**Both reproduced failures are a test-fixture defect, not a product-code
defect: a hardcoded past calendar-date constant used as data for two
assertions made through un-overridable, real-wall-clock-anchored "live
view" HTTP routes.**

`tests/test_place_biodiversity_summary_repository.py` defined `NOW =
datetime(2026, 8, 24, 12, 0, tzinfo=UTC)` -- a fixed instant -- and used it
both to build fixture data (Visit timestamps, monitoring-exposure days) and,
in most tests, as an explicit `now=NOW` argument to the repository methods
under test. Passing `now=NOW` explicitly makes those calls fully
self-consistent regardless of what `NOW` equals, and every such assertion
was, and remains, correct. But two assertions -- `test_api_route_returns_
the_summary`'s `new_taxa` check and `test_human_correction_updates_place_
biodiversity_intelligence_correctly`'s final `journal_b["historical_
status"] == "new"` check -- go through the real HTTP routes
(`LegacyAuthenticatedSyncTestClient(app).get(...)`), which construct
`ProductRepository` calls with **no** `now` override, so they always resolve
`period_start_at`/`period_end_at` from the real system clock
(`datetime.now().astimezone()`). Every run on any calendar day other than
2026-08-24 therefore evaluated `is_first_in_period` against `period_start_at
=` the *real* execution day's local midnight while the fixture's own
confirmation timestamp stayed fixed at 2026-08-24 -- correctly, per the
contract above, producing `"seen_before"` instead of `"new"`/`"first_
record"`, and an empty `new_taxa` list. This environment's real clock is
2026-08-30 (confirmed via `date`/`datetime.now(UTC)`), six days after the
fixture's hardcoded instant, which is exactly why both assertions failed
here.

Answering the ten root-cause questions the governing brief posed, from
direct code reading (`ProductRepository._historical_place_baseline_and_
species_statuses`, `mockingbird.analytics.historical_baseline.compute_
species_historical_statuses`) and from the passing/failing pattern of the
existing test suite:

1. **What counts toward "seen before"?** Every non-superseded, `reviewed`
   Visit with a non-null `reviewed_label` (`VisitModel.is_superseded ==
   False`, `review_status == "reviewed"`), resolved through the current
   taxonomy to a wildlife taxon. A provisional `SpeciesSuggestion` never
   contributes (`_classify` returns `PROVISIONAL_WILDLIFE`, excluded).
2. **At what timestamp boundary?** `is_first_in_period = period_start_at <=
   first_confirmed_at < period_end_at` -- a single half-open-interval
   comparison, one call site, reused by every caller. For the two live-view
   endpoints, that boundary is today's Place-local midnight through "now,"
   real-wall-clock, by design (see "Contract," above).
3. **Does the current Visit count itself in its own baseline?** Yes, and
   this is required, correct behavior, not a self-pollution bug: a
   genuinely first-ever confirmation's own timestamp *is* what makes
   `first_confirmed_at` fall inside the period. The priority order
   (`"new"`/`"first_record"` checked before `"regular"`/`"seen_before"`)
   means this can never demote a real first-ever confirmation to
   `"seen_before"` -- proved directly by every currently- and now-passing
   "first occurrence" test in this file and in `tests/test_historical_
   baseline_repository.py`.
4. **Does a Reviewed correction mutate the same row read for history?**
   Yes: `revise_visit_review` writes a new authoritative `ReviewLabelModel`
   revision row and updates `VisitModel.reviewed_label` (the single field
   the all-time aggregate reads) to the corrected label in the same
   transaction; the all-time `GROUP BY reviewed_label` aggregate is
   re-read fresh on every call, with no caching layer to invalidate.
5. **Current-vs-history boundary distinction?** Structural, not
   time-window-based: the all-time first/last-confirmed aggregate has no
   Visit-count cap and is deliberately unbounded (a `GROUP BY`, not a
   per-row scan -- see `historical_baseline.py`'s own module docstring),
   while `distinct_confirmed_usable_days`/regularity is bounded to the
   trailing 366-day `window_visits` query. Both share one `usable_dates`
   set so neither can silently disagree with the other.
6. **Are old inferred values retained after correction?** No: the query
   reads only the current `VisitModel.reviewed_label`; there is no join to
   suggestion/inference history for this computation, and a corrected
   label's old identity is proven, not just asserted, to carry zero
   observations afterward (`observation_count == 0`,
   `historical_status is None` for the stale label, in both the existing
   mandatory-correction test and this milestone's new one).
7. **Are reviewed/corrected rows joined incorrectly?** No irregularity
   found; the join is a plain `VisitModel ⋈ EventModel` on `event_id`/
   `stream_id`, identical in shape across all call sites.
8. **Place scope / taxon identity / label normalization?** Consistent:
   both endpoints scope to the same non-archived-Source `stream_ids`
   set, and taxon identity is resolved once through the shared
   `taxonomy_index`, with same-taxon label variants merged honestly (not
   picked arbitrarily) -- unchanged by, and irrelevant to, this defect.
9. **Why do both endpoints fail through the shared path?** Because they
   are not actually two independent defects: both `place_biodiversity_
   summary` and `wildlife_journal_history` call the identical `_historical_
   place_baseline_and_species_statuses` helper with the identical "today's
   local midnight -> now" live-view convention (by design, reused, not
   duplicated), and their HTTP routes share the identical absence of a
   test-clock override. One stale test fixture therefore broke both
   identically -- which is exactly why the shared-helper contract (see
   below) was never actually violated: the same correct convention,
   applied consistently, produced the same test-visible symptom at both
   call sites.
10. **Why didn't the canonical new/regular work already fix this?** Because
    it never was a canonical-logic defect. `docs/canonical-new-regular-
    species-contract.md` reconciled three *independently-computed*
    "new/regular" implementations into one; `place_biodiversity_summary`/
    `wildlife_journal_history` were never among them -- they already,
    correctly, call the one canonical helper (confirmed directly in
    `docs/biodiversity-place-intelligence-v1-contract.md`: "unchanged,
    reused verbatim... This milestone adds no new status value and no new
    eligibility rule"). The defect is a test-fixture staleness issue
    introduced with `test_place_biodiversity_summary_repository.py` itself
    (Biodiversity & Place Intelligence v1, 2026-08-24) -- the sibling,
    earlier-accepted `test_historical_baseline_repository.py` avoided the
    identical trap in its own comparable HTTP-route test
    (`test_api_round_trip_exposes_historical_baseline_and_bird_log_
    regularity`) by asserting `historical_status` only through
    `place-activity-report`'s explicit `start_at`/`end_at` POST body (a
    fixed-period route, immune to wall-clock drift), and deliberately not
    asserting `historical_status`'s *value* through the two live-view Bird
    Log HTTP calls in that same test. `test_place_biodiversity_summary_
    repository.py` did assert it there, with a hardcoded date, and nothing
    caught the mismatch until a day after 2026-08-24 arrived.

A genuine, but unreproduced and out-of-scope, adjacent observation surfaced
during root-causing and was investigated to a firm conclusion rather than
left speculative: the all-time first/last-confirmed aggregate inside the
shared helper is deliberately unbounded (no upper time filter), so in
principle a *past-period* report (`place_activity_report`/`place_story`,
neither of which this milestone's two reproduced failures touch) re-viewed
after new confirmations accumulate could compute all-time facts that
include confirmations after that past period's own `period_end_at`. Traced
this to its actual consumption point (`place_activity_report_response`,
`mockingbird/analytics/place_activity_report_adapter.py:646`): the response
is built by iterating `report.taxa` -- itself constructed only from
`visit_facts` correctly bounded to `[period_start_at, period_end_at)` -- and
merely *looking up* `species_historical_statuses.get(label)` to attach a
fact, never iterating the unbounded dict independently. A taxon with no
confirmed presence inside the report's own bounded period therefore can
never appear in `report.taxa` regardless of what the unbounded all-time
aggregate separately contains, so this does not reach any user-visible
surface for `place_activity_report`. Not re-verified for `place_story`
(out of scope, unreproduced, no adjacency to the two defects this milestone
closes); recorded here rather than silently dropped, per the governing
brief's own adversarial-review requirement.

## RED

Both reproduced tests run against the unmodified pre-fix code, exactly as
found:

```
tests/test_place_biodiversity_summary_repository.py::test_api_route_returns_the_summary FAILED
AssertionError: assert [] == ['northern_cardinal']
  (body["new_taxa"] was empty)

tests/test_place_biodiversity_summary_repository.py::test_human_correction_updates_place_biodiversity_intelligence_correctly FAILED
AssertionError: assert 'seen_before' == 'new'
  (journal_b["historical_status"], the final HTTP assertion in the test)
```

Byte-identical in shape to the `'seen_before' == 'new'` mismatch
independently re-confirmed as pre-existing across nine-plus prior full-Core
checkpoints in `docs/release-execution-state.md` §14 (the earliest,
"Camera / Source Experience & First-Hour Setup Closure v1," already
diagnosed it in passing as "an unrelated historical-status timing case" --
correctly, but never assigned its own fix until this milestone).

## Implementation

**One file changed, zero production code touched:** `tests/test_place_
biodiversity_summary_repository.py`.

1. **The fix.** `NOW` is now computed from the real wall clock at test
   -collection time (`datetime.now(UTC).replace(hour=12, minute=0,
   second=0, microsecond=0)`) instead of a hardcoded past date. Pinned to
   noon UTC (not the literal collection instant) so it stays safely inside
   one Place-local calendar day regardless of host timezone, preserving
   the original constant's own "stay exact, avoid boundary edge cases"
   discipline while tracking whatever day the suite actually runs on. This
   is a one-constant change: the ~50 other usages of `NOW` across the
   file's 21 (now 23) tests are all either passed explicitly as `now=NOW`
   (self-consistent regardless of its absolute value) or used only to
   compute relative offsets for fixture data -- none depend on its
   specific value beyond "the same instant throughout," which is
   unchanged.
2. **Two new tests**, closing the two required semantic cases this file
   had no coverage for (the pure-domain/repository-report-period coverage
   for both already existed elsewhere -- see "Validation," Tier 1 -- but
   not specifically proven through `place_biodiversity_summary`/
   `wildlife_journal_history` and their real HTTP routes, the exact pair
   the two reproduced defects were found through):
   - `test_subsequent_confirmation_of_an_already_confirmed_species_reads_
     seen_before` -- a second, later confirmation of an already-once
     -confirmed (not-yet-regular) species reads `"seen_before"`, not
     `"new"`, through both repository methods and both real HTTP routes.
   - `test_human_correction_to_a_previously_confirmed_species_reads_seen_
     before` -- correcting a Visit to a species that already has a real,
     earlier confirmed record reads `"seen_before"` for the corrected
     label (not `"new"` merely because the row was just reviewed), with
     both real records intact (`observation_count == 2`, no duplication,
     no loss) and the stale label carrying zero observations.

No change to `mockingbird.analytics.historical_baseline`, `ProductRepository
._historical_place_baseline_and_species_statuses`, `place_biodiversity_
summary`, `wildlife_journal_history`, or any route in `mockingbird.api.
main` -- per root-cause finding, none was defective. Schema unchanged
(v58); no `CURRENT_DATABASE_SCHEMA_VERSION` guard-rail assertions needed
touching.

## Reviewed truth

Correction propagation was independently re-confirmed, not merely assumed,
through both the pre-existing mandatory-correction test (correction to a
*genuinely new* species: `after_history_b.historical_status == "new"`,
proven through both the repository call and, now, the real HTTP route) and
this milestone's new test (correction to an *already-seen* species:
`historical_status == "seen_before"`, `observation_count == 2`, stale label
`observation_count == 0`/`historical_status is None`). Both directions
correctly recompute status from the single current `VisitModel.reviewed_
label` value; the corrected identity carries no phantom duplicate history,
and the superseded identity carries no residual authoritative history.

## Temporal correctness

Self-exclusion and future-non-retroactivity are proven structurally (the
priority-ordered `is_first_in_period` check, evaluated before regularity,
independent of Visit count; the all-time-first aggregate is a `MIN`, which
a later Visit can never move earlier) and empirically, through the
existing, currently-passing `place_activity_report`-anchored tests in
`tests/test_historical_baseline_repository.py`/`tests/test_historical_
baseline.py` (period-explicit, immune to wall-clock drift, exercising the
identical shared helper this milestone's two endpoints also call). No
regression introduced; no product code changed.

## Place isolation

MockingBird is a single-Place product (one property per installation,
multiple *Cameras/Streams* within it -- see `docs/product-doctrine.md`);
there is no multi-Place concept for "seen at Place A" to leak into "seen at
Place B." The closest real analog -- history from an archived (no longer
part of the active Place) Source/Stream must not count -- is already
covered and passing (`tests/test_historical_baseline_repository.py::
test_archived_stream_confirmations_are_excluded_from_historical_facts`),
using the identical non-archived-`stream_ids` scoping both implicated
endpoints already share.

## Validation

**Tier 1** (focused historical-status/new-regular; 23 tests in the directly
implicated file plus its closest pure-domain/repository siblings):

```
tests/test_place_biodiversity_summary_repository.py .......................  [23 passed]
```
including both originally-RED tests, now green, plus the two new semantic
-case tests above.

**Tier 2** (broader affected repository/API/product-intelligence coverage,
run together with Tier 1 in one pass):

```
tests/test_place_biodiversity_summary_repository.py
tests/test_historical_baseline.py
tests/test_historical_baseline_repository.py
tests/test_canonical_new_regular_species_consistency.py
tests/test_place_biodiversity_summary.py
tests/test_wildlife_journal.py
tests/test_place_activity_report_repository.py
tests/test_place_change_summary_repository.py
tests/test_place_change_summary.py
tests/test_place_story.py
tests/test_place_story_repository.py
tests/test_place_feature.py
tests/test_regularity_narrative.py
tests/test_seasonal_pattern.py
tests/test_temporal_pattern.py
tests/test_source_activity.py
tests/test_dashboard_today.py
tests/test_environmental_context.py
tests/test_ecological_interoperability_repository.py

498 passed in 114.92s
```

Zero failures, zero regressions across every surface that consumes
`_historical_place_baseline_and_species_statuses`/`compute_species_
historical_statuses` either directly or through a composed fact
(regularity narratives, seasonal/temporal patterns, change summary, place
story, place features, dashboard Today, environmental-context
associations, ecological export eligibility).

**Tier 3** (one full Core run, per the governing brief's "one Tier-3 run
only" -- run bare, `python3 -m pytest -q`, with no `slow`-marker
deselection, so this run is a strict superset of every prior "Core"
checkpoint cited in §14 of `docs/release-execution-state.md`):

```
5277 passed, 3 skipped, 11 xfailed, 231 warnings in 2229.99s (0:37:09)
```

**Zero failures** -- both previously-recurring `test_place_biodiversity_
summary_repository.py` failures are gone (their two tests are now inside
the 5277 passed), and nothing else regressed. This is the first full Core
run in at least nine consecutive checkpoints (see §14 of `docs/release-
execution-state.md`) to report zero failures at all; every previously-cited
"2 failed, both pre-existing" checkpoint was exactly this pair. The 231
warnings are pre-existing, unrelated deprecation notices (`audioop`/`aifc`/
`sunau` stdlib removal, SQLAlchemy's default datetime adapter, FastAPI
`on_event`), not new findings. No unrelated failure required baseline
-bisection, since none occurred.

`ruff check` on the one touched file (`tests/test_place_biodiversity_
summary_repository.py`): clean -- "All checks passed!" No other file was
touched, so no other file's finding-count could have changed. `tsc --noEmit`
/`vite build` not run: this milestone touched zero frontend code (test
-file-only, backend), so a frontend build has no reachable path to a
regression here -- matching the proportionality several prior narrow
correctness/evidence milestones in this same file already established
(e.g., Platform / Runtime Portability & Support Truth Closure v1 likewise
skipped a full Core run for a comparably scoped change; this milestone runs
Tier 3 instead specifically because the governing brief required it, given
this defect's own multi-checkpoint recurrence history).

## Remaining risks

- The unbounded all-time aggregate's interaction with a *re-viewed past
  -period* report (`place_activity_report`/`place_story`) was investigated
  (see "Root cause," above) and confirmed **not reachable** for
  `place_activity_report` specifically (its response builder only looks up
  into the unbounded dict for taxa already present in its own
  period-bounded `visit_facts`). `place_story`'s own consumption of the
  same unbounded `all_time_first_confirmed_at`/`taxa` fields
  (`compute_diversity_milestone_events`) was not separately re-verified --
  out of scope, unreproduced, no adjacency to either defect this milestone
  closes. Concrete, bounded, worth a future glance if `place_story` is ever
  itself the subject of a correctness milestone; not a reason to withhold
  accepting this one.
- This milestone's fix makes `NOW` track the real wall clock at test
  -collection time rather than a fixed instant. The residual risk this
  reintroduces -- a pytest session whose collection phase and this file's
  own execution straddle a local midnight -- is real in principle but
  negligible in practice (collection for the full suite completes in
  seconds, not the ~20+ minutes Tier-3 execution takes) and is the same
  risk profile every other `datetime.now(UTC)`-anchored test in this suite
  (dozens, by direct grep) already carries; not a new category of
  flakiness introduced by this fix.
- The untracked root `uv.lock` observed at this milestone's start (an
  ordinary side effect of some `uv` invocation elsewhere in this
  actively-shared worktree, matching a pattern recorded at least four
  times previously in `docs/release-execution-state.md`) was left
  untouched -- not this milestone's own artifact, not one of the seven
  protected files, no risk to this milestone's own correctness claim.

## Decision

**A.**

Both reproduced failures were independently confirmed RED against the real,
unmodified pre-fix code and GREEN after; the root cause was traced to a
concrete, single, precisely-identified defect (a stale hardcoded test-clock
constant colliding with two intentionally real-wall-clock-anchored "live
view" HTTP routes) rather than assumed; every one of the required semantic
guarantees -- first occurrence, subsequent occurrence, correction to a new
species, correction to a previously-seen species, current-Visit
self-exclusion, future-Visit non-retroactivity, Place/archived-Stream
isolation, unresolved-label exclusion, and agreement between both product
endpoints -- was independently proven, either by a test newly added this
milestone or by an existing, currently-passing test through the identical
shared computation path; the fix is the smallest correct one (one test
file, zero production code, zero schema change); Tier 1/2 are fully clean
(498 tests, run together as one pass covering the implicated file plus
every other consumer of the shared historical-status path, zero failures);
and Tier 3 -- one full Core run, 5277 passed, **zero failed** -- confirms no
wider regression and is itself the first zero-failure full Core checkpoint
in at least nine consecutive prior attempts.
