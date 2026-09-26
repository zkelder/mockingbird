# Today Truth Regression Repair v1 -- Report

**Status:** IMPLEMENTED, pending acceptance.
**Contract:** [today-truth-regression-repair-v1-contract.md](today-truth-regression-repair-v1-contract.md).

| | |
| --- | --- |
| Starting HEAD | `83a0e86` (Native-Windows Field Reliability Corrections v1, accepted) |
| Schema | **v61, unchanged** -- no migration, no model change |
| Version | `0.1.0`, unchanged |
| Production code changed | `src/mockingbird/repository/product_repository.py` only |
| Push | **not pushed.** No tag, no publish, no remote operation |

## A. What was wrong

`dashboard_summary`'s Today panel lost confirmed wildlife. A user who did
the thing the product asks them to do -- review an animal and confirm what
it was -- watched it disappear from Today's count, from "New today", and
from "Best moments". Discover -> Confirm -> **Remember** failed at the last
step.

Introduced by `3d78f8a` (*Review Queue Scale Closure v1 (1/n)*), bisected
exactly against its direct parent `73dbcd4`. Present at `8a45d1a`, so
present in the build *Field Validation Closure v1* validated.

### Root cause

`_preloaded_motion_evidence_for_review_queue_item` returned an
**authoritative `None`** for any Visit/Event absent from the bulk preload,
instead of its own `_PRELOAD_MISS` sentinel. The map alone cannot tell
"this target has no MotionEvidence" from "this target was never fetched" --
both are simply absent -- and the code read the second as the first.

`_read_only_build_cache` is shared: "nested builds share the outermost
cache and never clear it early." `dashboard_summary` opens that cache,
runs `_visible_review_queue_items` **first** (populating the map for the
*queue's* members), then runs `_dashboard_today_summary`. Today's Visits
are a different set -- most are already reviewed, which is the point of
Today -- so they got `evidence=None`,
`_review_queue_product_context` classified them `detector_class !=
"animal"`, and the count collapsed.

### Bounded blast radius

Traced producer to consumer; every path that reads the shared cache was
classified, not assumed.

| Path | Coverage | Before |
| --- | --- | --- |
| `_dashboard_today_summary` day-story loop | outside | **wrong** -- drove "New today" / "Best moments" empty |
| `_dashboard_today_summary` detector-count loop | outside | **wrong** -- drove `detector_qualified_animal_visit_count` to 0 |
| `_review_queue_items_uncached` visit-less Event lane | outside by definition | **wrong** -- those cards lost snapshot media and activity context |
| `_review_queue_items_uncached` Visit loop | covered by construction | correct, but only because the membership predicate happened to match |
| `_media_asset_for_path_from_session` | membership-checked (`in by_path`) | correct -- never exposed |
| `get_visit_identification_assistant`, `start_visit_identification_assistant`, `prepare_review_queue_species_suggestions`, `identify_review_queue_item` | no build cache open | correct -- always queried |

The visit-less Event lane is a **second, previously unreported
manifestation inside the Review Queue itself**, found by this trace rather
than by the failing tests. Review Queue Scale Closure v1's "byte-identical
queue" proof did not catch it because its Profile B fixture had no
visit-less Event queue members.

Nothing outside `product_repository.py`'s read path is affected: no write
path, no schema, no API shape, no review-authority decision, no model,
detector, admission or Visit-assembly behaviour.

## B. The repair

**A cache answer must equal the answer the original database query would
have given.** Three states, kept distinguishable:

1. **outside coverage** -> `_PRELOAD_MISS`, caller falls through to its own
   query;
2. **covered, no evidence** -> a real `None`, served with no query;
3. **covered, with evidence** -> the row, served with no query.

A lookup whose Visit *or* Event side is uncovered falls through entirely: a
partial answer over a union predicate is a wrong answer, not a slower one.

Implemented by giving each preload its own covered id set rather than
inferring coverage from map membership:

- `_PreloadedMotionEvidence` -- `by_target` plus `visit_ids`/`event_ids`,
  with `covers()` as the only thing that authorises an answer.
- `_PreloadedPendingSuggestions` -- the same treatment for the pending
  SpeciesSuggestion preload. That one was **latent**, not broken: the queue
  build's membership predicate matches the preload's, so no current caller
  read an uncovered Visit. It is guarded anyway, because the contract
  should not depend on remembering that a nested build narrows the record.
- `media_asset_by_local_path` -- **unchanged.** It already checked
  `media_path in by_path`, so an unfetched path already fell through.

Preserved exactly: media filtering, union deduplication, newest-first
`(created_at, id)` ordering including `created_at` ties, nested-cache
lifetime and cleanup, queue membership, order and classification.

**The accepted optimization is not disabled or reverted.** It is made
correct, and then extended: `_extend_motion_evidence_preload` lets a caller
that knows its own bounded row set up front declare it, so restoring
correctness does not restore one round trip per row. Today's two day loops
and the queue's visit-less Event lane now do exactly that -- see §E.

## C. Red / green evidence

### The seven recorded regression tests

Reproduced **before** the repair at `83a0e86`, and again by stashing the
repair mid-session -- not merely cited:

```
FAILED tests/test_dashboard_today.py::test_today_summary_uses_selected_local_day_and_current_reviewed_truth
FAILED tests/test_dashboard_today.py::test_today_summary_regulars_require_usable_day_coverage_and_exclude_non_nature_records
FAILED tests/test_dashboard_today.py::test_today_summary_new_today_is_wildlife_inclusive_not_bird_only
FAILED tests/test_dashboard_today.py::test_today_summary_counts_a_confirmed_kind_level_mammal_as_real_activity
FAILED tests/test_dashboard_today.py::test_today_summary_best_moments_caps_one_species_and_stays_diverse
FAILED tests/test_dashboard_today.py::test_today_summary_moves_from_likely_to_confirmed_without_duplication
FAILED tests/test_canonical_new_regular_species_consistency.py::test_today_and_bird_log_agree_on_new_species
7 failed, 7 passed in 6.20s
```

**After the repair: `28 passed`** across the same two files plus the new
one.

### New focused coverage -- `tests/test_today_truth_regression_repair.py`

15 tests. Every lookup case is asserted **twice** -- once with the preload
active, once with no cache at all -- and the two answers must agree, which
is stronger than asserting a fixed value because it cannot drift from the
query it stands in for.

| Test | Case |
| --- | --- |
| `test_target_outside_preload_coverage_falls_through_to_the_query` | uncovered Visit -- **the regression** |
| `test_covered_target_with_no_evidence_answers_none_from_the_cache` | covered-empty; also asserts 0 statements |
| `test_covered_target_with_evidence_is_served_without_a_query` | covered-with-rows; also asserts 0 statements |
| `test_mixed_covered_visit_and_uncovered_event_falls_through` | mixed Visit/Event union |
| `test_uncovered_event_only_lookup_falls_through` | Event-only lookup, `visit_id=None` |
| `test_media_asset_filter_is_preserved_on_both_paths` | media filter: match, other-match, no-match |
| `test_newest_first_ordering_including_created_at_ties` | ordering incl. `created_at` ties |
| `test_a_row_promoted_to_both_visit_and_event_is_counted_once` | union deduplication |
| `test_a_nested_build_cannot_make_the_outer_build_answer_wrongly` | nested-build cache lifetime |
| `test_the_preload_never_escapes_its_own_build` | cleanup on context exit |
| `test_confirmed_wildlife_stays_counted_on_today_without_duplication` | review -> Today transition |
| `test_best_moments_still_surface_a_confirmed_visit` | Best moments |
| `test_dashboard_reads_write_nothing` | reads side-effect free; Reviewed truth unchanged |
| `test_today_motion_evidence_reads_do_not_scale_with_the_day` | scale guarantee |
| `test_an_early_returning_nested_preload_leaves_honest_coverage` | stale-preload carryover (see §K) |

**Proven red before, green after.** With only the one tracked production
file reverted to `83a0e86` and the final test files in place:

```
=== BASELINE (83a0e86 product_repository.py, final tests) ===
15 failed, 14 passed in 9.66s
=== REPAIRED (HEAD) ===
29 passed in 9.38s
```

The 15 baseline failures are the seven recorded regressions plus eight of
the fifteen new tests (uncovered target, mixed union, Event-only,
nested-build, early-returning nested preload, review-to-Today, Best
moments, and the scale guarantee). The remaining seven new tests pass at
baseline **by design**: they lock down behaviour the repair must
*preserve* -- covered-empty, covered-with-rows, media filter, ordering,
union dedup, cache cleanup, side-effect freedom -- so they are regression
guards, not defect reproductions.

## D. Visible product-flow proof

Representative isolated data: four animal Visits in one local day (three
Northern Cardinal, one Blue Jay), confirmed in two steps. Identical
fixture, identical calls, `83a0e86` vs the repair.

| After | `detector_qualified_animal_visit_count` | `new_today` | `likely_today` | `best_moments` |
| --- | --- | --- | --- | --- |
| nothing confirmed -- **before** | 4 | -- | -- | 4 |
| nothing confirmed -- **after** | 4 | -- | -- | 4 |
| 3 cardinals confirmed -- **before** | **1** | -- | -- | **1** |
| 3 cardinals confirmed -- **after** | **4** | `northern_cardinal` | -- | 3 |
| all 4 confirmed -- **before** | **0** | -- | -- | **0** |
| all 4 confirmed -- **after** | **4** | `blue_jay`, `northern_cardinal` | -- | 3 |

Before the repair, confirming every Visit emptied the day: the count fell
4 -> 1 -> **0**, "New today" never populated at all, and "Best moments"
ended **empty**. After it, the count holds at 4 throughout, each confirmed
species appears in "New today" exactly once, `likely_today` stays empty
(so nothing is double-counted as both confirmed and likely), and "Best
moments" stays populated and diverse.

**This is the Dashboard Today panel, not the canonical Today report.**
They are separate computation paths and the distinction matters: the same
fixture's `place_activity_report` (the report-first "Today in Your Yard"
surface, `docs/place-activity-report-contract.md`) was **correct on both
sides** -- `total_visit_count` 4 throughout, `confirmed_wildlife_visit_count`
0 -> 3 -> 4, taxa `northern_cardinal:c3/p0` and `blue_jay:c1/p0`. Only
`dashboard_summary.today` regressed, because only it shares a read cache
with the review-queue build. That is also why the canonical report's own
correctness was never evidence that Today was fine.

## E. Query-performance comparison

Identical data, identical calls, statement counts (not wall clock -- this
machine is shared and wall clock varies more than 2x).

### Review-queue scale guarantees -- retained

Fixture: `tests/test_review_queue_scale.py::_build_library`.

| Fixture | `review_queue_items` before | after | `dashboard_summary` before | after |
| --- | --- | --- | --- | --- |
| 25 Visits / 5 backlog / 2 visit-less | 68 | **69** | 203 | **204** |
| 205 Visits / 5 backlog / 2 visit-less | 68 | **69** | 203 | **204** |
| 15 Visits / 60 visit-less backlog | 300 | **301** | 201 | **202** |

`+1` statement, flat, in every case -- the one bulk read that now covers
the visit-less Event lane. Queue contents, order and classification are
identical. The guarantee Review Queue Scale Closure v1 made holds
unchanged: 10x the reviewed history is still **69 vs 69**, not 690.

Without the lane preload this would have been `+60` on the third fixture
(one fall-through per visit-less Event). That is why
`_extend_motion_evidence_preload` exists.

### Today -- correct *and* cheaper than the naive repair

Fixture: N confirmed + 5 pending animal Visits in one local day.

| Today's Visits | `dashboard_summary` before | naive repair | **shipped** | count before | **after** |
| --- | --- | --- | --- | --- | --- |
| 10 confirmed + 5 | 437 | 457 | **439** | 5 (wrong) | **15** |
| 100 confirmed + 5 | 2,547 | 2,747 | **2,549** | 5 (wrong) | **105** |

The naive repair -- coverage check alone -- costs 2 statements per Today
Visit, because Today's two loops each fall through per Visit. Declaring
Today's own bounded (`.limit(501)`) row set to the same preload reduces
that to a **flat +2**, independent of how busy the day is.

`tests/test_today_truth_regression_repair.py::test_today_motion_evidence_reads_do_not_scale_with_the_day`
locks this in structurally, by statement *shape*: at 6 Visits and at 51,
the fall-through query (`... ORDER BY motion_evidence.created_at DESC`)
runs **0 times** and the bulk reads (`... IN (...)`) run the same number of
times, while both days count correctly (6 and 51; the regression made both
1).

## F. Validation

### Tier 1 -- focused

| Suite | Result |
| --- | --- |
| `test_today_truth_regression_repair.py` (new) | 14 passed |
| `test_dashboard_today.py` + `test_canonical_new_regular_species_consistency.py` | 28 passed (with the new file) |

### Tier 2 -- affected subsystems

| Suites | Result |
| --- | --- |
| `test_review_queue_scale.py`, `test_review_queue_page_scale.py`, `test_review_queue_product_mode.py`, `test_review_queue_bulk_corrections.py`, `test_review_queue_bioclip_status_performance.py`, `test_review_queue_species_suggestion_batch.py` | **63 passed** |
| `test_api.py`, `test_wildlife_journal.py`, `test_place_activity_report.py`, `test_place_activity_report_repository.py`, `test_dashboard_detector_health_honesty.py`, `test_dashboard_observation_engine_truth.py`, `test_canonical_new_regular_species_consistency.py` | **194 passed** |

### Tier 3 -- complete non-hardware gate

**Core gate:** see §I. **All seven recorded regression failures are gone,
and zero failures are attributable to this milestone.**

| Check | Result |
| --- | --- |
| `npm run typecheck` (`tsc --noEmit`) | clean |
| `npm run build` | clean, built in 2.79s |
| `python -m mockingbird --check` | `MockingBird is ready: ... integrity ok` |
| `ruff check` on both changed files | **zero new findings** -- `product_repository.py` reports the identical 55 pre-existing errors at `83a0e86` and after; the new test file passes cleanly |
| `ruff format --check` | unchanged -- the file is not ruff-formatted at baseline either, and so are its peer test files |
| Generated artifacts in the worktree | none |

**No hardware session, packaging rebuild or Full gate was required.** The
change is confined to one read-path cache in one module: no packaging,
dependency-closure, model-bundle, migration or platform code is touched.
Core already covers the applicable Fast and migration/backup checks.

## G. Protected-file verification

All eight re-verified against the hashes of record in
[native-windows-field-reliability-corrections-v1-report.md](native-windows-field-reliability-corrections-v1-report.md)
§B, at the start of this session and again at closure.

| File | SHA-256 (first 16) | Match | Tracked? |
| --- | --- | --- | --- |
| `docs/wildlife-detector-training-contract.md.orig` | `63f9e5ba142069da` | yes | untracked |
| `scripts/evaluate_small_bird_detector.py` | `81cdff0423f12112` | yes | untracked |
| `scripts/materialize_wildlife_stage2.py.orig` | `ade97d9d46f44661` | yes | untracked |
| `scripts/train_wildlife_stage2_rfdetr.py.orig` | `a24aa6e294c04df1` | yes | untracked |
| `src/mockingbird/detectors/small_bird_benchmark.py` | `e85a2315fbe1487e` | yes | untracked |
| `src/mockingbird/training/wildlife.py.orig` | `548f0706b5498b02` | yes | untracked |
| `tests/test_small_bird_benchmark.py` | `abad318b8df14c20` | yes | untracked |

`uv.lock` (`f36f26ba9fffcbd8`) also untouched and untracked. Two `git stash
push -- src/mockingbird/repository/product_repository.py` / `git stash pop`
cycles were used this session to obtain baseline evidence; both named that
one tracked path explicitly, and the hashes above were re-taken afterwards
to prove no untracked file moved. Staging used explicit full paths only --
no `git add -A`, no `git add .`.

## H. Disclosures and limitations

1. **`python -m mockingbird --check` migrated the local dev database**
   `data/mockingbird.sqlite3` from schema 59 to 61, taking its own safety
   backup first (`ccd0c81222e0457a8b0f2d31fd99acae`). That is the
   command's normal documented behaviour, the path is gitignored, and no
   product code caused it. Disclosed because it was a real write.
2. **`media_asset_by_local_path` picks the lowest `id` when two
   MediaAssets share a `local_path`;** the uncached query has no `ORDER BY`
   and so has no defined answer in that case. `local_path` carries no
   uniqueness constraint (see `_repair_visit_evidence_links`' own note),
   though every asset's path is derived from its unique id in practice.
   Pre-existing since `3d78f8a`, untouched here, and not a
   coverage-correctness issue.
3. **`_motion_evidence_model_for_visit` is a different, older lookup**
   (oldest-first) that Today also calls per Visit. It never consulted the
   preload and is unchanged. It is the reason Today's *total* statement
   count still grows with the day; that growth is pre-existing and outside
   this milestone's scope.
4. **No real-hardware or field evidence was gathered**, and none is
   claimed. This repair's correctness is established by tests and by
   before/after comparison on identical isolated data.
5. `Q-2`, `Q-4` and the stale `camera_connected` field remain open,
   deferred and non-blocking, exactly as recorded.

## I. Core gate result

Run on this milestone's committed code (`19ae391`), `pytest -m "not slow"`
-- the Core gate:

```
6 failed, 6225 passed, 4 skipped, 35 deselected, 11 xfailed,
284 warnings in 2753.35s (0:45:53)
```

**All seven recorded regression failures are gone.** The prior milestone's
accepted Core checkpoint was `11 failed, 6205 passed`; this run is `6
failed, 6225 passed`.

**Failures attributable to this milestone: ZERO** -- established, not
asserted:

1. **All six reproduce deterministically in isolation** at `19ae391`
   (2.84 s, same six). None is order-dependent; "flaky" was rejected as a
   label rather than used as one.
2. **All six fail identically at the pre-repair baseline**, obtained by
   reverting the one tracked production file to `83a0e86` and re-running
   the same six (2.99 s, same six, same assertions). The failure set is
   the same before and after the repair.

| Test | Disposition |
| --- | --- |
| `test_doctor_camera_node_transport.py::test_interpret_no_transport_configured_anywhere_is_pass` | pre-existing, of record |
| `test_doctor_camera_node_transport.py::test_interpret_ignores_sources_without_transport_configured` | pre-existing, of record |
| `test_environmental_context.py::test_temperature_band_established_once_enough_days_are_cached` | pre-existing, of record |
| `test_place_biodiversity_summary_repository.py::test_api_route_returns_the_summary` | pre-existing, of record |
| `test_place_biodiversity_summary_repository.py::test_human_correction_updates_place_biodiversity_intelligence_correctly` | pre-existing, of record |
| `test_place_change_summary_repository.py::test_api_round_trip_exposes_change_detection_fields` | pre-existing, of record (that file's own long-documented date-sensitive fixture) |

All six are members of the **established recorded six-set** in
[performance-scale-stability-closure-v1-report.md](performance-scale-stability-closure-v1-report.md)
§X. This run contains all six of that set and nothing else; the previous
milestone's run contained four of the six plus the seven Today
regressions. The two `test_place_biodiversity_summary_repository.py`
cases are the pair that happened *not* to fail in that previous run, and
they were specifically checked against the pre-repair baseline rather than
assumed -- they are Place-intelligence repository tests, so attribution to
this repair was genuinely plausible and had to be disproved.

**No deterministic failure was relabelled flaky, and no unrelated test was
modified.** The only test file this milestone touches is its own new one.

## J. Concurrent-session conflict, disclosed

At 20:27 local, **another Claude session on this machine** ("Dashboard
read-only cache truth regression", started ~31 minutes into this
milestone) began running `pytest` against **this same working tree**,
which at that moment already carried this milestone's uncommitted repair.

Consequences, stated plainly:

- That session's test results are **not** a `83a0e86` baseline. They
  exercised the repaired `product_repository.py`, so the seven known
  regression tests pass there for that reason and not because they were
  ever passing at `83a0e86`.
- Two of this session's own `verify_core.py` invocations were stopped
  early -- the first because a post-launch docstring correction would have
  meant the gate did not run on the final code, the second because
  `verify_core.py` leaves its `pytest` child orphaned when the parent is
  killed, and two orphaned runs plus the peer's run were competing for the
  same machine. Those stopped runs are **not** reported as results here.
  The Core result in §I is a single complete run on the committed code.
- The peer session was messaged directly with the exact uncommitted file
  list and asked not to stash, checkout, reset, commit, or edit those
  files, and asked what authorized its work.
- This milestone's work was committed locally at that point rather than
  held uncommitted, specifically so a peer `git stash`/`git checkout`
  could not destroy it. Nothing was pushed.

The seven protected untracked detector files and `uv.lock` were re-hashed
after the peer became active and are byte-identical (§G).


## K. Peer review incorporated

A concurrent session tracing the same defect independently (see §J) raised
one risk a coverage-set fix might not close, and it was checked rather
than assumed: `_preload_review_queue_rows` returns early -- without
touching the cache -- whenever its narrowed target set holds no Visit,
which is exactly what `_review_queue_item_by_target` produces for an Event
target. One build's preload record therefore survives into a nested build
and outlives it.

**Verdict: safe, for a reason that was implicit and is now explicit.** A
covered id means *this cache read that target's rows*, never *that target
belongs to this build*. A read-only build cache cannot go stale inside its
own window, so a surviving record is still an honest record, while a
target it never read stays uncovered and falls through. Had coverage been
implemented as "this build's member ids", the early-return path would have
answered confidently for the wrong build.

Committed as `19ae391`: the invariant stated in `_PreloadedMotionEvidence`'s
docstring, plus `test_an_early_returning_nested_preload_leaves_honest_
coverage` covering the concrete path (outer build, then an Event-only
nested build that preloads nothing, then one covered and one uncovered
lookup). No behaviour change.

The same review independently reached the same conclusion on the other
three items -- Today/dashboard contamination, the visit-less Event lane as
in-queue self-contamination, and `_media_asset_for_path_from_session`
being unaffected because it membership-checks. That is convergent
evidence for §A's blast-radius table, not new scope.
