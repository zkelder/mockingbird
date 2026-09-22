# Analytics & Local Data Truth Consistency v1 -- closure report

## A. Starting baseline

Branch `main`; accepted HEAD `993d3ef094a5f9f0d7ba2941b25476f1172b9c8b` ("Add
Review Queue Count Truth Consistency v1 closure report, link from
release-execution-state.md"); schema `v59` unchanged; version `0.1.0`.
Working tree clean except the seven preserved untracked detector files
(§13 of `release-execution-state.md`), confirmed present, untouched, and
byte-identical (mtime-verified) at both this milestone's own start and
close, plus `uv.lock` (pre-existing untracked, not one of the seven
protected files, not touched). No active writer session found sharing this
working tree: HEAD verified stable across a 3-second drift check, no
`.git/index.lock`, no open file handles under `.git`, no working-tree
changes beyond the seven protected files at session start. **Correction,
mid-session (see §R):** this finding held only at the moment it was taken
-- a second, peer session sharing this exact milestone and working tree
was found active partway through this session's own Tier 3 work. §R
records the complete, unredacted account; not corrected in place here so
this section remains an accurate record of what was true at session start.
Governing docs
read before any edit: `release-execution-state.md` (top matter and the
complete §3 stacked log through the current entries), `product-doctrine.md`
(full read -- Measured/Inferred/Reviewed, Product objects, Two scorecards,
Place Intelligence), `roadmap.md` (grepped for demo/analytics-truth/dataset
-coverage/local-data topics -- confirmed no relevant mention, matching the
prior milestone's own identical finding),
`review-queue-count-truth-consistency-v1-report.md` (complete read --
this milestone's own direct predecessor and the source of its authorization
brief's own P/Q sections), `native-windows-packaging-acceptance-v1-report.md`
(N.2 and the post-`039ce7d` addendum establishing the canonical
`_real_source_condition()`/repurposed-Source contract), and the directly
affected Analytics/Local Data/Yard Map/Dataset Coverage/Dataset Quality
code (`src/mockingbird/repository/product_repository.py`,
`src/mockingbird/api/schemas.py`) and tests (`tests/test_demo_source_
exclusion.py` and every test file found to touch the five affected producer
functions).

## B. Analytical truth contract

Applying the governing brief's own A/B/C test to every field in the five
affected summary types:

- **Category A (genuine ecosystem/history truth -- demo must never
  contribute):** `AnalyticsSummary.event_count`/`visit_count`/`needs_review_
  count`/`species_counts`/`species_label_ids`/`zone_activity_counts`;
  `LocalDataStatus.event_count`/`visit_count`/`needs_review_count` (reused
  directly from `AnalyticsSummary`); every field of `DatasetCoverageSummary`
  except `target_species_count` (`reviewed_record_count`, `export_ready_
  count`, `needs_review_count`, `unknown_bird_count`, `unknown_animal_
  count`, `false_positive_count`, `reviewed_species_count`, `covered_
  target_species_count`, `missing_target_species_count`, `species`,
  `gaps`); every field of `DatasetQualitySummary` (`issue_count`, `high_
  count`/`medium_count`/`low_count`, `freeform_label_count`, `unknown_
  label_count`, `missing_zone_count`, `missing_media_count`, `conflicting_
  correction_count`, `false_positive_count`, `export_ready_count`, `needs_
  review_count`, `issues`); every Visit-derived field of
  `YardMapActivitySummary` (`open_activity_session`, `needs_review_count`,
  `needs_review_visit_ids`, `latest_visit_id`, `latest_visit_at`, `latest_
  confirmed_label`, `latest_preview_url`). All of these are framed to the
  user, in the actual rendered frontend copy (verified by direct read, not
  assumed from field names), as the user's own real observed activity,
  reviewed-dataset export readiness, or export-cleanup signal --
  `AnalyticsPage.tsx`'s "outdoor activity"/"animal visits"/"corrected bird
  truth", `DatasetCoveragePanel.tsx`'s "Export-ready reviewed records"/
  "Reviewed species coverage", `DatasetQualityPanel.tsx`'s "Records needing
  cleanup before export", `YardMapPage.tsx`'s clickable per-camera "N needs
  review" button and "Latest"/"Confirmed" labels.
- **Category B (explicit demo/sample mode):** none of the fields in scope
  qualify -- confirmed directly against the frontend (§ frontend audit,
  below) that no Analytics/Local Data/Dataset Coverage/Dataset Quality/Yard
  Map surface has, or needs, an explicit "you are viewing sample data" mode
  distinct from its normal rendering. `LocalDataPage.tsx`'s own "Reset Demo
  Data" section is the one place demo/sample content is explicitly named to
  the user, and it is an action, not a metric.
- **Category C (internal/diagnostic -- demo inclusion legitimate, must not
  feed ordinary product truth):** `LocalDataStatus.source_count`/`stream_
  count`/`zone_count`/`media_asset_count`/`detection_run_count`/`detection_
  proposal_count`/`motion_evidence_count`/`review_label_count`/`dataset_
  export_count`, and `DatasetCoverageSummary.target_species_count`. A
  direct frontend read of `LocalDataPage.tsx` (its own `PageHeader`
  description: "MockingBird keeps product metadata, imported media
  references, drawn zones, review corrections, analytics inputs, and
  dataset export manifests locally") confirms this entire field family is
  presented as local-storage inventory ("local source records", "local
  import references"), not ecosystem-history truth, sitting beside the
  page's own `database_ready`/`database_integrity_check`/`seed_data_
  present` diagnostic rows -- the same framing this repository's own
  `AdapterEvaluationSummary.unreviewed_count` was already judged to have
  (Review Queue Count Truth Consistency v1's own P section) and correctly
  left alone. `target_species_count` is simply the taxonomy's own
  bird-target-species list size, never activity-derived, so demo status
  cannot affect it either way. Critically, the demo seed's raw storage
  contribution here is itself the *intended purpose* of first-run seed
  data -- `_seed_session` deliberately populates one representative row in
  most of these tables so a first-run walkthrough is not empty -- and this
  is already honestly disclosed via `seed_data_present`, never silently
  presented as the user's own history.

This contract prevents exactly the contradiction the brief opens with: a
demo-only install can no longer show "0 real observations" (via the
now-corrected `needs_review_count`) alongside "N species observed" (via the
now-corrected `species_counts`) or "N reviewed species ready for export"
(via the now-corrected `DatasetCoverageSummary`), while a genuinely
demo-only Local Data panel still honestly discloses that one seeded Source/
Stream/Zone set/ReviewLabel/DatasetExport exists locally.

## C. Complete affected summary-field inventory

| Field | Meaning | Producer | User-facing consumer(s) | Old demo behavior | Final demo behavior |
| --- | --- | --- | --- | --- | --- |
| `AnalyticsSummary.event_count` | Count of Activity Sessions (Events) | `_analytics_summary` | `AnalyticsPage.tsx` ("Events") | Included | Excluded |
| `AnalyticsSummary.visit_count` | Count of animal-centered Visits | `_analytics_summary` | `AnalyticsPage.tsx` ("Visits") | Included | Excluded |
| `AnalyticsSummary.needs_review_count` | Outstanding reviewable items | `_analytics_summary` | `AnalyticsPage.tsx` ("Needs review" + header action button) | Included | Excluded |
| `AnalyticsSummary.species_counts`/`species_label_ids`/`label_display_names`/`label_categories` | Reviewed label/species breakdown | `_analytics_summary` | `AnalyticsPage.tsx` ("Reviewed species and labels", "Reviewed species" tile); `SpeciesCoverageCard.tsx` (currently unmounted) | Included | Excluded |
| `AnalyticsSummary.zone_activity_counts` | Per-zone activity tally | `_analytics_summary` | `AnalyticsPage.tsx` ("Zone activity", "Active zones") | Included | Excluded |
| `LocalDataStatus.event_count`/`visit_count`/`needs_review_count` | Same as above, reused | `_local_data_status` (calls `_analytics_summary`) | `LocalDataPage.tsx` ("Events"/"Visits"/"Needs review") | Included | Excluded (automatic, via reuse) |
| `LocalDataStatus.source_count`/`stream_count`/`zone_count`/`media_asset_count`/`detection_run_count`/`detection_proposal_count`/`motion_evidence_count`/`review_label_count`/`dataset_export_count` | Raw local-storage row counts | `_local_data_status` (`self._count(session, Model)`) | `LocalDataPage.tsx` (inventory metric grid + "Database" panel) | Included | **Unchanged -- Category C, see §B** |
| `LocalDataStatus.seed_data_present` | Whether the seeded demo Source still exists | `_local_data_status` | `LocalDataPage.tsx` ("Database" panel, "Seed data") | N/A (a presence flag, already honest) | Unchanged |
| `DatasetCoverageSummary.reviewed_record_count`/`export_ready_count`/`needs_review_count`/`unknown_bird_count`/`unknown_animal_count`/`false_positive_count`/`reviewed_species_count`/`covered_target_species_count`/`missing_target_species_count`/`species`/`gaps` | Reviewed-dataset export-readiness coverage | `_dataset_coverage_summary` | `DatasetCoveragePanel.tsx` | Included | Excluded |
| `DatasetCoverageSummary.target_species_count` | Size of the bird-target-species taxonomy list | `_dataset_coverage_summary` | `DatasetCoveragePanel.tsx` | N/A (taxonomy size, not activity) | Unchanged |
| `DatasetQualitySummary.issue_count`/`high_count`/`medium_count`/`low_count`/`freeform_label_count`/`unknown_label_count`/`missing_zone_count`/`missing_media_count`/`conflicting_correction_count`/`false_positive_count`/`export_ready_count`/`needs_review_count`/`issues` | Export-cleanup QA signal | `_dataset_quality_summary` | `DatasetQualityPanel.tsx` | Included | Excluded |
| `YardMapActivitySummary.needs_review_count`/`needs_review_visit_ids`/`open_activity_session`/`latest_visit_id`/`latest_visit_at`/`latest_confirmed_label`/`latest_preview_url` | Per-Stream tile activity | `_yard_map_activity_summary` | `YardMapPage.tsx` (per-camera tile: clickable "N needs review" button, "Latest"/"Confirmed" labels, preview photo, "Open activity" pill) | Included | Excluded (zeroed/`None` for a demo-sourced Stream) |
| `YardMapActivitySummary.monitoring_desired_state`/`monitoring_actual_state`/`camera_health_state` | Stream runtime/health state | `_yard_map_activity_summary` | `YardMapPage.tsx` (health indicator) | N/A (no real camera process exists for the demo Stream either way) | Unchanged |
| `ModelReadinessSummary.reviewed_record_count`/`export_ready_count`/`dataset_quality_issue_count`/`high_quality_issue_count`/`reviewed_species_count`/`covered_target_species_count`/`missing_target_species_count` | Pre-model readiness checklist, built from Dataset Coverage/Quality | `_classifier_readiness_report`-adjacent `model_readiness_summary` (reads `_dataset_coverage_summary`/`_dataset_quality_summary`) | `ModelAdaptersPage.tsx`-adjacent readiness surfaces | Included (inherited) | Excluded (inherited automatically, not independently touched) |
| `AdapterEvaluationSummary.unreviewed_count` | Adapter-proposal outcome QA metric | (unrelated producer) | `ModelAdaptersPage.tsx` | Included | **Unchanged -- Category B/QA metric, correctly out of scope (re-confirmed, matching Review Queue Count Truth Consistency v1's own prior determination)** |

## D. Implementation architecture

One new module-level helper, `_real_stream_ids(session) -> set[str]`
(`product_repository.py`, immediately after `_real_source_condition()`
itself, matching where `_visible_review_queue_items`/`_visible_review_
queue_count` were added immediately after `_review_queue_items` for the
prior milestone): a single bulk query joining `StreamModel` ->
`CameraSourceModel` -> outer-joined `SourceProviderConfigurationModel`,
filtered by the unmodified, canonical `_real_source_condition()`. This is
the one seam all four affected Python-side aggregations (`_analytics_
summary`, `_dataset_coverage_summary`, `_dataset_quality_summary`,
`_yard_map_activity_summary`/`yard_map`) now filter through -- no new
demo-detection logic, no ad hoc `provider_key != "demo"` conditional
anywhere in the diff. These four functions each aggregate Events/Visits in
Python (not via a single filterable SQL query the way the Review Queue
family could reuse `_real_source_condition()` inline), so a bulk id-set
computed once per call and checked in Python
(`event.stream_id in real_stream_ids`) is the natural equivalent of that
seam for this shape of code.

- `_analytics_summary`: `real_stream_ids` and a bulk `stream_id_by_event_id`
  map are computed once; the `events` list comprehension and a new `visits`
  list comprehension both filter on stream membership; the `review_labels`
  loop's `event`-target branch gets the identical check added to its
  existing skip condition. `zone_activity_counts`/`species_counts`/
  `species_label_ids` need no independent change -- they are already
  derived exclusively from the now-filtered `events`/`visits`.
- `_dataset_coverage_summary`/`_dataset_quality_summary`: both share an
  identical two-loop shape (a Visit loop, then a genuinely-eventless-Event
  loop). Each loop's existing "does this Event's Stream exist"
  `session.get(StreamModel, ...) is None` check is replaced with
  `event_model.stream_id not in real_stream_ids` -- a strict tightening
  (a nonexistent stream_id can never appear in `real_stream_ids` either,
  since it requires an inner join through `StreamModel`), not two
  independent conditions.
- `_yard_map_activity_summary`: gained a new required keyword parameter,
  `is_real_source: bool`, computed once in `yard_map()` via the same
  `_real_stream_ids` call and passed per-Stream. When `False`, the three
  Visit-derived queries (latest/confirmed, `needs_review_count`, `needs_
  review_visit_ids`, `open_activity`) are skipped entirely rather than
  queried and discarded, and the corresponding fields resolve to `None`/
  `0`/`[]`/`False`. Monitoring/health computation is unchanged -- it
  already has no real camera process to report on for the demo Stream.
- `_local_data_status`: unchanged in its own body; its `event_count`/
  `visit_count`/`needs_review_count` fields are corrected automatically
  because it already calls `self._analytics_summary(session)` directly and
  reuses those three fields verbatim.
- Four brief doctrine comments were added directly to the affected
  `AnalyticsSummary`/`LocalDataStatus`/`DatasetCoverageSummary`/
  `DatasetQualitySummary`/`YardMapActivitySummary` class definitions in
  `schemas.py`, recording which field family is demo-excluded and why, so
  a future field addition inherits the contract instead of silently
  reintroducing this defect family a third time.
- **Incidental bug fix, disclosed rather than silently folded in:**
  `_dataset_quality_summary` referenced `event_ids_with_any_visits`
  (the all-time, including-superseded complement to `event_ids_with_
  visits`) in its second loop's skip condition without ever defining it in
  this function's own scope -- unlike its two siblings (`_analytics_
  summary`, `_dataset_coverage_summary`), which both define it identically
  before the same loop shape. Empirically reproduced: any genuinely
  eventless real Event (no Visit ever -- product-doctrine.md's own
  "Motion ignored in privacy zone" Activity Session example) raised
  `NameError`, crashing `GET /api/dataset-quality/summary`. Not a
  demo-truth defect (it would crash identically for real data, and no
  demo Event is ever genuinely eventless), but found directly inside, and
  fixed alongside, code this milestone was already required to touch to
  add its own demo-filtering to the identical lines. Fixed by adding the
  missing definition, matching the sibling functions' own established
  shape exactly. Confirmed independently by `ruff`'s own static analysis
  (an `F821 Undefined name` finding that disappears after the fix -- see
  §L).

## E. Analytics result

`_analytics_summary`/`GET /api/analytics/summary` now excludes the seeded
demo Source's own two fabricated Events/Visits from every field. A
demo-only install reads `event_count=0`, `visit_count=0`, `needs_review_
count=0`, `species_counts={}`, `species_label_ids=[]`, `zone_activity_
counts={}`. Real activity alongside demo counts correctly and grows as
expected (proven 1, then 2, in Tier 1). A repurposed demo Source's own
pre-existing two Visits count as genuine activity, matching the canonical
`_real_source_condition()` contract exactly.

## F. Species Coverage result

`SpeciesCoverageCard.tsx` (the dedicated Species Coverage component) reads
`AnalyticsSummary` fields directly and is fixed automatically as a
consequence of §E -- no independent code change was needed or made. One
frontend-audit finding, disclosed for completeness: this component is
currently not mounted anywhere in the running app (`grep -rn
"SpeciesCoverageCard" web/` matches only its own file) -- its data-layer
correctness is still fixed by this milestone, but it has no live UI surface
today to visually verify against. Not a defect this milestone introduces or
is authorized to fix (mounting it would be a UI change, out of this
milestone's explicit non-goals); disclosed in §S as advisory context only.

## G. Local Data result

`LocalDataStatus.event_count`/`visit_count`/`needs_review_count` now read
correctly (excluded), fixed via direct reuse of the already-fixed
`_analytics_summary`. `LocalDataStatus`'s nine raw storage-inventory counts
(`source_count`, `stream_count`, `zone_count`, `media_asset_count`,
`detection_run_count`, `detection_proposal_count`, `motion_evidence_count`,
`review_label_count`, `dataset_export_count`) are deliberately left
demo-inclusive per the Category C determination in §B -- confirmed by
direct frontend read that this page frames them as local-storage inventory,
not ecosystem history, and that the demo seed's own contribution to these
tables is its intended illustrative purpose, already disclosed via `seed_
data_present`.

## H. Dataset Coverage / Quality result

Both `_dataset_coverage_summary` and `_dataset_quality_summary` now exclude
the seeded demo Source's own activity from every field, including the
derived `covered_target_species_count`/`reviewed_species_count` numerators
and each individual `species` entry's own per-label counts -- not only the
headline totals. Directly proven with a dedicated test that inserts a
*reviewed*, real-target-species Visit under the seeded demo Stream itself
and confirms it does not count as covered (§L). The incidental `_dataset_
quality_summary` crash bug (§D) is fixed and covered by a dedicated
regression test.

## I. Yard Map/activity result

`_yard_map_activity_summary` now shows "no activity yet" for a demo-sourced
Stream's tile on the Yard Map: `needs_review_count=0`, `needs_review_visit_
ids=[]`, `latest_visit_id=None`, `latest_visit_at=None`, `latest_confirmed_
label=None`, `latest_preview_url=None`, `open_activity_session=False`.
`YardMapPage.tsx` renders every Stream identically with no demo indicator
of its own (confirmed directly: `YardMapActivitySummary`/`YardMapStreamItem`
carry no `is_demo` field, and no `.filter()` on the stream list excludes
anything by demo status) -- before this fix, the seeded demo Stream's tile
could show a clickable "N needs review" button and a fabricated "Latest"/
preview photo indistinguishable from a real camera's own tile. A real
Stream's own tile is proven unaffected, showing its genuine activity
normally alongside an untouched demo tile. A repurposed demo Source's own
pre-existing needs-review Visit is proven to count correctly on its Yard
Map tile too.

## J. Derived-metric consistency result

Every derived percentage/denominator this milestone's own scope touches is
now internally consistent with its own numerator: `DatasetCoverageSummary.
covered_target_species_count`/`missing_target_species_count` (numerator
`covered_target_species_count` no longer counts a demo-only reviewed
species as covered, proven directly, §H); `DatasetCoverageSummary.reviewed_
species_count` (same). No surface in this milestone's scope was found where
a headline count excludes demo data but a derived metric built from the
same underlying records still includes it -- the shared `real_stream_ids`
seam and the two-loop-filtering pattern make this structurally true rather
than something that had to be separately re-verified per field.

## K. Repurposed-demo-source result

`de_demo_seeded_source` (the established test helper: a real, non-"demo"
`SourceProviderConfigurationModel` row for the seeded demo Source) makes
its own pre-existing two Visits count as genuine, real activity across
every affected surface -- `AnalyticsSummary`, `LocalDataStatus`,
`DatasetCoverageSummary`, and `YardMapActivitySummary` all correctly flip
from "excluded" to "included" the moment the Source is repurposed, with no
additional code change required, because every fix in this milestone
reuses the same canonical `_real_source_condition()` a repurposed Source
already satisfies. Proven directly (§L) rather than assumed.

## Frontend audit (Phase 6 bounded consumer search)

A dedicated read of every named consumer file (`AnalyticsPage.tsx`,
`SpeciesCoverageCard.tsx`, `LocalDataPage.tsx`, `DatasetCoveragePanel.tsx`,
`DatasetQualityPanel.tsx`, `YardMapPage.tsx`, and `ModelAdaptersPage.tsx`
for contrast) confirmed: every field's actual rendered label/copy (not
assumed from its name), the exact API call site backing each page
(`GET /api/analytics/summary`, `GET /api/dataset-coverage/summary`,
`GET /api/dataset-quality/summary`, `GET /api/settings/local-data`,
`GET /api/yard-map`), and that no frontend file reads or filters on
`is_demo_source` anywhere (a per-Visit field that exists in the frontend's
own TypeScript types but is never consumed) -- confirming this milestone's
fix belongs entirely at the backend aggregation layer, with zero frontend
source changes required or made. A backend-side producer/constructor audit
(`grep` for every `AnalyticsSummary(`/`YardMapActivitySummary(`/
`DatasetCoverageSummary(`/`DatasetQualitySummary(`/`LocalDataStatus(`
construction site) confirmed exactly one real producer per summary type;
`demo_data.py`'s own same-named `build_analytics_summary`/`review_queue_
items` functions are legacy, pre-SQL-migration code with zero live callers,
confirmed dead and out of scope.

## L. Tier 1 results

11 new tests added to the existing `tests/test_demo_source_exclusion.py`
(29 total in that file, all passing), matching this file's own established
convention (extended by Review Queue Count Truth Consistency v1, itself
extending Pre-Release Trust & Correctness Correction v1's original UI-01
tests):

1. Demo-only analytical state -- 5 tests, one per affected summary type
   (`AnalyticsSummary`, `LocalDataStatus`, `DatasetCoverageSummary`,
   `DatasetQualitySummary`, `YardMapActivitySummary` via a pinned `now`
   just after the seeded demo Events' fixed 2026-01-15 dates) -- every
   genuine-activity field resolves to zero/empty/`None`, while `LocalData
   Status`'s raw storage-inventory fields (`source_count=1`, `stream_
   count=1`, `zone_count=3`, `review_label_count=1`, `dataset_export_
   count=1`) correctly stay inclusive per the Category C contract (§B),
   proven in the same test as a single coherent assertion, not asserted
   separately in a way that could hide an inconsistency.
2. Real + demo -- one combined test proving `AnalyticsSummary`/`Dataset
   CoverageSummary`/`LocalDataStatus` all count exactly the one real,
   reviewed, target-species Visit added alongside the untouched demo
   Source, then grows correctly to 2 as a second real Visit is added
   (never hardcoded) -- plus a dedicated Yard Map test proving a real
   Stream's own tile shows its genuine activity normally alongside an
   unaffected demo tile.
3. Real-only -- proven within the same real+demo tests above: the exact
   real count (1, then 2) appears correctly, which is the real-only
   contract in the presence of demo data that must not perturb it.
4. Repurposed seeded demo Source -- 2 tests (`de_demo_seeded_source`),
   proving the Source's own pre-existing two Visits now count as genuine
   activity across `AnalyticsSummary`/`DatasetCoverageSummary`/`LocalData
   Status` and, separately, on its Yard Map tile.
5. `AnalyticsSummary.needs_review_count` -- covered directly in tests 1, 2,
   and 4.
6. `YardMapActivitySummary.needs_review_count` -- covered directly in
   tests 1, 2, and 4's own dedicated Yard Map tests.
7. Sibling fields -- `event_count`/`visit_count`/`species_counts`/`species_
   label_ids`/`zone_activity_counts` (Analytics); `reviewed_record_count`/
   `export_ready_count`/`reviewed_species_count`/`covered_target_species_
   count` (Dataset Coverage); `issue_count`/`export_ready_count`/`needs_
   review_count`/`issues` (Dataset Quality) -- all directly asserted in
   tests 1 and 2.
8. Derived percentages/denominators -- a dedicated test inserts a
   *reviewed* real-target-species Visit directly under the seeded demo
   Stream itself (not a separate real Stream) and proves `covered_target_
   species_count`/`reviewed_species_count` and that species' own `species`
   entry all correctly exclude it -- the strongest possible proof that the
   numerator, not only the headline count, is fixed.
9. Incidental bug-fix regression -- a dedicated test constructs a
   genuinely eventless real Event (no Visit ever) and proves `_dataset_
   quality_summary` no longer raises `NameError`, correctly classifying it
   as one QA issue instead of crashing.

**RED -> GREEN proof (Phase 7's explicit requirement).** All 11 new tests
were run against the unmodified accepted-baseline source
(`git stash push -- src/mockingbird/repository/product_repository.py`,
keeping the new tests in place): **8 of 11 failed** against baseline (the
3 repurposed-Source tests pass trivially on baseline too, since baseline's
total absence of filtering happens to coincide with "repurposed counts as
real" -- disclosed here rather than silently claimed as a demo-exclusion
proof; their real purpose is regression protection against this
milestone's own fix being too aggressive, proven not to be). After
`git stash pop`, all 29 tests in the file pass. This exceeds the brief's
"at least one representative summary" bar across five.

`ruff check` on both changed source files: `product_repository.py`'s own
established 56-finding baseline is now 55 -- confirmed, via the identical
`git stash` bisection, to be exactly one finding narrower and not
otherwise different: every one of the other 55 findings is byte-identical
(same rule, same column, same message, shifted only by this milestone's
own inserted line count), and the one finding that disappeared is
`F821 Undefined name 'event_ids_with_any_visits'` at the exact line the
incidental bug fix (§D) corrects -- ruff's own static analysis
independently corroborates the fix. `test_demo_source_exclusion.py`: 0
findings. All seven other changed test files: 0 findings (the 2 pre-
existing `F401` findings in `test_api.py` -- unused `asyncio`/`httpx`
imports -- confirmed byte-identical before/after via bisection, unrelated
to this milestone).

## M. Tier 2 results

30 directly-adjacent test files run together, twice (once mid-fix, once
as a final clean re-run after all fixture corrections below): **419
passed, 0 failed.** Files: `test_demo_source_exclusion.py`, `test_api.py`,
`test_persistence.py`, `test_research_export_repository.py`, `test_
dataset_coverage.py`, `test_dataset_quality.py`, `test_yard_map.py`,
`test_dashboard_today.py`, `test_dashboard_detector_health_honesty.py`,
`test_dashboard_observation_engine_truth.py`, `test_camera_health_cross_
surface_honesty.py`, `test_camera_source_creation.py`, `test_detection_
interface.py`, `test_first_run_onboarding.py`, `test_folder_import.py`,
`test_identification_assistant.py`, `test_local_backup_recovery.py`,
`test_local_detector_adapter.py`, `test_local_only_privacy.py`, `test_
media_import.py`, `test_megadetector_adapter.py`, `test_model_readiness.
py`, `test_repository_isolation.py`, `test_review_identification.py`,
`test_review_queue_species_suggestion_batch.py`, `test_review_queue_bulk_
corrections.py`, `test_review_queue_bioclip_status_performance.py`,
`test_fast_review.py`, `test_model_adapter_contract.py`, `test_visit_
curation.py`, `test_review_queue_product_mode.py`.

**20 pre-existing tests initially failed** when `_analytics_summary`/
`_dataset_coverage_summary`/`_dataset_quality_summary`/`yard_map`'s demo
exclusion became load-bearing for the first time -- the identical class of
blast radius this repository's own history already documents twice
(Native-Windows & Packaging Acceptance v1's ~35 fixture conversions;
Review Queue Count Truth Consistency v1's own bounded scope avoided it
only by not touching these functions yet). Each was read and classified
individually, per the governing brief's explicit instruction, not
mechanically forced green:

- **`test_api.py` (2 tests, `test_reset_demo_data_restores_seed_state_
  after_mutations`/`test_reset_demo_data_does_not_duplicate_seed_rows`):**
  both intend to verify "Reset Demo Data" restores/does not duplicate the
  seeded rows -- an internal-inclusive-behavior test, not a demo-exclusion
  test. Their `event_count`/`visit_count` assertions (`== 2`) and one
  `needs_review_count >= 1` assertion assumed the old demo-inclusive
  values; corrected to `== 0` (non-duplication itself remains fully proven
  by the untouched `zone_count`/`review_label_count`/`dataset_export_
  count` assertions alongside them, none of which are demo-filtered). The
  Visit's own raw `review_status` being genuinely restored to `needs_
  review` is independently, separately proven by an existing, unmodified
  assertion two lines below (`GET /api/visits/{id}`) -- the fix is
  precise to the aggregate-metric layer, not the underlying truth.
- **`test_persistence.py` (2 tests, `test_analytics_summary_reflects_
  persisted_correction_state`/`test_analytics_needs_review_count_matches_
  review_queue_on_seed_data`):** both intend to verify a rollup-mirror/
  cross-surface-consistency invariant (an Event's `review_status` mirroring
  its own Visit's, not double-counted) using the seeded Visit as convenient
  fixture data with a known shape -- not testing demo status. Fixed by
  calling `de_demo_seeded_source` right after repository creation in each,
  preserving each test's actual invariant unchanged. (A third, sibling test
  in the same file, `test_analytics_needs_review_count_tracks_review_queue_
  after_correction`, already asserted only the *post-correction* state
  (both 0), which holds regardless of demo status -- correctly needed no
  change, confirmed by reading it rather than assuming.)
- **`test_dataset_coverage.py` (5 tests)/`test_dataset_quality.py` (6
  tests):** every test in both files builds its scenario on the seeded
  Visit/Stream/Zone as convenient plumbing to test dataset coverage/QA's
  own internal correction/freeform-label/conflicting-correction/missing-
  zone/false-positive/proposal-vs-truth logic -- never demo-exclusion
  itself. Fixed once per file, at the shared `autouse` `isolated_
  repository` fixture, by calling `de_demo_seeded_source` immediately
  after repository creation -- covering all tests in each file with one
  change rather than five/six separate ones. Two tests in `test_dataset_
  quality.py` already used delta-based (`before`/`after`) assertions
  robust to demo status either way and correctly needed no change,
  confirmed by reading them rather than assuming.
- **`test_yard_map.py` (1 test, `test_yard_map_activity_is_stream_scoped_
  and_uses_reviewed_truth_only`):** intends to verify per-Stream scoping
  and reviewed-truth-only display using the seeded Stream's two Visits --
  not demo-exclusion (already covered by this milestone's own dedicated
  Yard Map tests in `test_demo_source_exclusion.py`). Fixed by calling
  `de_demo_seeded_source` at the start of this one test only (the file's
  other 3 tests did not touch the affected fields and correctly needed no
  change).
- **`test_model_readiness.py` (3 tests):** `ModelReadinessSummary` is built
  from `_dataset_coverage_summary`/`_dataset_quality_summary`, so this
  file's own failures are the same class, one layer up. All three intend
  to verify pre-model readiness's own signal/checklist logic (QA-issues-
  block-first-spike, corrected records improve readiness) using the seeded
  Visit as convenient plumbing. Fixed once, at the shared fixture, exactly
  as the two Dataset Coverage/Quality files above. The file's other 2
  tests already used delta-based assertions and correctly needed no
  change.

No test was rewritten to weaken or remove an assertion; every fix either
repurposed the seeded demo Source (matching each test's own already-
established, real intent) or corrected an assertion's *expected value* to
match the newly-correct contract while leaving the underlying invariant it
tests unchanged (`test_api.py`'s two tests). `ruff check` on all seven
modified test files: 0 new findings (the 2 pre-existing `test_api.py`
findings noted in §L are unrelated and unchanged).

## N. Tier 3 (full Core) results

This milestone's acceptance pass was worked by two sessions concurrently in
this same working tree for roughly two hours around Tier 3 -- disclosed in
full here and in §R rather than narrated as if one session did it all; HEAD
never moved and nothing was lost, but strict single-writer discipline (§13)
was not maintained. Both sessions carried the identical implementation
(§A-§M, already complete before either session's own Tier 3 work began) and
coordinated live once discovered; this report is written by, and the
`release-execution-state.md` update and commit are made by, the session
whose transcript this is.

**First full Core run** (this session; 2826.99s/47m6s): **6079 passed, 8
failed, 4 skipped, 35 deselected, 11 xfailed.** Four of the eight are
byte-identical to the already-established pre-existing set this file has
recorded across ten-plus prior checkpoints -- `test_doctor_camera_node_
transport.py::test_interpret_no_transport_configured_anywhere_is_pass`/
`test_interpret_ignores_sources_without_transport_configured`, `test_
environmental_context.py::test_temperature_band_established_once_enough_
days_are_cached`, `test_place_change_summary_repository.py::test_api_
round_trip_exposes_change_detection_fields`. `test_place_biodiversity_
summary_repository.py`'s own pair, also part of that established set, did
not reproduce on this run -- consistent with its long-documented (9+
consecutive prior checkpoints) flaky-by-nature behavior (§14), not
concerning on its own.

The remaining four were new: `tests/test_source_provider_smoke_flows.py::
test_external_url_provider_smoke_flow_preserves_truth_boundaries`/`test_
folder_import_provider_smoke_flow_preserves_truth_boundaries` and `tests/
test_taxonomy.py::test_review_correction_normalizes_taxonomy_display_
name`/`test_review_correction_allows_freeform_labels`. Root cause,
confirmed by direct reproduction rather than assumed: both files use the
seeded demo Source/Stream (`source-backyard-demo`/`stream-backyard-
feeder`) as convenient fixture plumbing -- the identical "convenient
plumbing, not demo-exclusion itself" class already fixed in the seven
files in §M -- and neither file was in Tier 2's own 30-file sweep, so
Tier 3 was the first pass wide enough to reach them (exactly the case
Tier 3 exists for). `test_taxonomy.py`'s `VISIT_ID` corrections trigger
`_analytics_summary` (embedded as `analytics` in `POST /api/review-
labels`'s own response) without first repurposing the now-demo-excluded
seeded Stream; fixed identically to the other five fixture-level files,
adding `de_demo_seeded_source(repository)` to the file's `isolated_
repository` fixture. `test_source_provider_smoke_flows.py`'s two
"preserves truth boundaries" tests captured their `before_truth` baseline
*before* `configure_external_url`/`configure_folder_source` repurposed
that same seeded Source -- correct before this milestone (repurposing
never changed dataset truth, since it was already demo-inclusive),
incorrect after (repurposing now correctly makes the Source's own
pre-existing reviewed squirrel Visit start counting, exactly per the
established repurposed-Source contract, §K) -- fixed by moving the
`before_truth` snapshot to after the repurposing step, so each test keeps
proving what it always meant to prove (that the *preview* actions below
it, not the repurposing step itself, preserve truth boundaries).

Both fixes were authored by the peer session (§R); independently verified
here rather than accepted on report alone. Reproduced `test_review_
correction_normalizes_taxonomy_display_name`'s original failure directly
with a full traceback and locals (`pytest --tb=long -l`), by temporarily
reverting just the one added fixture line: confirmed the `KeyError:
'northern_cardinal'` originates in the *test's own* assertion
(`result["analytics"]["species_counts"]["northern_cardinal"]`, a
bracket-index into a dict `_analytics_summary` now correctly leaves empty
for a still-demo-sourced correction), not any server-side crash --
`POST /api/review-labels` itself returns a clean `201` either way. This is
a fixture-classification fix, not a production-code robustness gap,
matching the class of fix already established for the other files; no
additional production-code change was needed or made. Restored the file
and re-ran both files standalone: **9/9 passed** (6 in `test_taxonomy.py`,
3 in `test_source_provider_smoke_flows.py`). `ruff check` on both: 0
findings.

**Second, confirming Core run, from the fully-fixed tree (peer session,
solo -- see §R for why this session's own attempted second run was
stopped instead of run to completion): 4 failed, 6083 passed, 4 skipped,
35 deselected, 11 xfailed (42m38s).** All four failures are the identical,
already-established pre-existing set named above, independently
re-confirmed via direct `git stash` bisection (source files only) against
unmodified HEAD. **Zero Core failures attributable to this milestone.**

## O. Targeted e2e results

`web/e2e/analytics-local-data-truth-consistency.spec.ts` (written before
this session's own acceptance pass began) drives a dedicated real
(non-demo) Source/Stream through `POST /api/sources` -> media import ->
a real species correction, then asserts on the actual rendered `/analytics`
and `/local-data` pages that `Events`/`Visits`/`Needs review` move by
exactly the genuine amount and the corrected species appears in "Reviewed
species and labels" -- deliberately delta-based rather than a hard "reads
zero," disclosed in the spec's own header comment: this suite runs ~18+
spec files sequentially against one shared, already-populated instance, so
an absolute-zero assertion would be order-dependent and not a meaningful
regression proof. The demo-only-install "reads exactly zero" contract
itself is proven with true fixture isolation in `test_demo_source_
exclusion.py` (§L) -- the correct, and only practical, layer for that
specific claim in this suite's own shared-instance design; this e2e spec's
real job, and the one it actually does, is proving the fixed aggregation
code still renders correctly end-to-end in a real browser for real data.

Running it as first found (before this session's own e2e pass) surfaced
three Playwright strict-mode violations -- all real bugs in the untracked
spec file itself, not in application or product-repository code, found
and fixed here:

1. `page.getByRole("heading", { name: "Insights" })` substring-matched
   three headings at once (`/analytics`'s own `<h1>Insights</h1>`, plus
   `WildlifeInsightsPanel`'s `<h2>Wildlife Insights</h2>` and `Zone
   InsightsPanel`'s `<h2>Zone & feeder insights</h2>`, both mounted on the
   same page). Fixed with `exact: true`.
2. The `metricValue()` helper's `.locator(".metric-card", { hasText: label
   })` substring-matched across all three metric grids on the page (this
   page's own summary plus the two panels above) -- e.g. `"Visits"`
   matched `"Unresolved Visits"` (Wildlife) and `"Confirmed bird Visits"`/
   `"Visits / monitored hour"` (Zone) too, five elements total. Fixed by
   matching `.metric-card .metric-label`'s own text *exactly* (that span
   holds only the label, confirmed by reading `MetricCard.tsx` directly),
   which is unaffected by any other card's label/detail text.
3. `page.getByText("Blue Jay")` matched seven elements (a "New labels"
   comparison note, review-history cards, a filter dropdown option, and
   the actual "Reviewed species and labels" row). Fixed by scoping to
   `.bar-row` -- that section's own list-item class, driven directly by
   `species_counts`/`label_display_names`, the fields this milestone
   corrects -- rather than matching the bare species name anywhere on the
   page.

After all three fixes: **1 passed.** `tsc --noEmit` on the web project:
clean. Confirmed the fix was verified, not merely exercised: with `src/
mockingbird/api/schemas.py` and `src/mockingbird/repository/product_
repository.py` isolated via `git stash` (test/spec files, including this
one, left in place) against unmodified HEAD, the spec **still passed** --
expected and correct given the spec's own documented, deliberately
delta-based scope (§ above): creating and correcting a *real, non-demo*
Visit was never the defect this milestone fixes, so this spec does not,
and was never intended to, distinguish old code from new. This is
disclosed rather than presented as a RED->GREEN proof it is not; the
actual RED->GREEN proof for the "demo-only wildlife does not appear as
genuine analytical truth" claim is Tier 1's fixture-isolated tests (§L,
8-of-11 RED against baseline, 29/29 GREEN after), which is the correct
layer per the spec's own design. Restored the stash; re-ran once more on
the fully-restored tree to confirm: **1 passed.** No other existing e2e
spec asserts on any of the five affected surfaces' own numeric fields
(`grep` confirmed only `notification-preferences.spec.ts` and `mobile-
viewport-audit.spec.ts` also visit `/local-data`, and both exercise
unrelated sections -- Notifications settings and horizontal-overflow/
screenshot audit, respectively, neither reading a `.metric-card` value) --
so no other spec needed a standalone regression re-run.

## P. Truth/data-integrity impact

None. This milestone changes only which already-computed Events/Visits/
review labels contribute to displayed aggregate counts and derived
metrics; it never touches `review_status`, `reviewed_label`, `is_
authoritative`, `is_superseded`, or any other Measured/Inferred/Reviewed
truth-tier field (confirmed against `product-doctrine.md`'s "The truth
boundary"/"Measured, Inferred, and Reviewed" sections before any edit, and
directly demonstrated by `test_reset_demo_data_restores_seed_state_after_
mutations`'s own unchanged assertion that the seeded Visit's raw `review_
status` genuinely is `needs_review` even though it no longer contributes to
`needs_review_count`). No detector, classifier, threshold, tracker,
admission, or Visit-assembly logic was touched anywhere in this diff. No
record was deleted, hidden, or mutated -- demo and real records alike
remain exactly as they were; only which of them are *counted* into a
displayed summary changed. Local Only: no network or cloud call is
involved anywhere in this fix; not applicable.

## Q. Schema impact

None. Schema unchanged at `v59` (`CURRENT_DATABASE_SCHEMA_VERSION` in
`storage/database.py`, confirmed both before and after this milestone's own
edits). No migration, no new table, no new column.

## R. Bounded self-review

One implementation/self-review pass (this report, §A-§O) plus this
dedicated acceptance-closure review, per §13's own audit budget --
findings below, each checked directly against code rather than assumed.

- **Contradictory analytics:** none found. Every field family within this
  milestone's own bounded scope (§B) is now internally consistent with its
  siblings on the same page (§J); the one place a genuine numerator/
  denominator pairing exists (`covered_target_species_count`/`reviewed_
  species_count`) is directly proven, not just headline counts (§H, §L
  item 8). Surfaces outside this milestone's bounded scope (Place
  Biodiversity, Place Change/Habitat) were not examined and may or may not
  share an analogous gap -- already disclosed as genuinely unknown in §S,
  not newly found here.
- **Demo leakage:** none found. Read the complete body of all four touched
  functions (not only the diff hunks) directly: `_analytics_summary`'s
  `zone_activity_counts`/`species_counts`/`species_label_ids`/`label_
  display_names`/`label_categories` all derive exclusively from the
  already-filtered `events`/`visits` lists, and the one place a second,
  independent source feeds `species_counts` (the `review_labels` loop, for
  `target_type == "event"`) carries its own explicit `stream_id_by_event_
  id.get(label.target_id) not in real_stream_ids` exclusion. `_dataset_
  coverage_summary`/`_dataset_quality_summary`'s two-loop shape and `_yard_
  map_activity_summary`'s `is_real_source` gate were each confirmed to
  cover every code path that constructs their own return value.
- **Legitimate real data accidentally excluded:** the one real instance
  found is the two Tier-2-blind-spot files in §N, already fixed and
  independently re-verified there. Investigated the mechanism itself
  directly for any broader risk: `_real_stream_ids`'s inner join from
  `StreamModel` to `CameraSourceModel` could in principle silently drop a
  legitimate real Stream if `source_id` were ever absent -- confirmed via
  `storage/models.py` that `StreamModel.source_id` is a `nullable=False`
  foreign key, so this cannot happen. A dangling `event`-type review label
  (referencing a since-removed Event) would now read as excluded rather
  than included by the new third condition in `_analytics_summary`'s
  `review_labels` loop -- confirmed unreachable in practice (`grep` found
  no `session.delete` of `EventModel` anywhere in the repository; Events
  are append-only, per `product-doctrine.md`'s own truth model), so not a
  live risk.
- **Derived numerator/denominator consistency:** reconfirmed by reading
  `model_readiness_summary`'s own inherited computation chain directly
  (`self.dataset_coverage_summary()`/`self.dataset_quality_summary()`,
  both trivial passthroughs to the now-fixed private functions) -- no
  independent, unfixed copy of either computation exists anywhere else in
  the repository (`grep` for every `AnalyticsSummary(`/`DatasetCoverage
  Summary(`/`DatasetQualitySummary(`/`YardMapActivitySummary(`/`LocalData
  Status(` construction site found exactly one live producer each, plus
  `demo_data.py`'s already-confirmed-dead legacy pair).
- **Dashboard/Bird Log/Review Queue regressions:** none, confirmed by
  direct call-site audit rather than inferred from the diff's own shape.
  Read the complete bodies of `dashboard_summary`, `_dashboard_today_
  summary`, `wildlife_journal_overview`, `wildlife_journal_history` (Bird
  Log's actual internal names), and `_review_queue_items`: zero calls to
  any of `_analytics_summary`/`_dataset_coverage_summary`/`_dataset_
  quality_summary`/`_yard_map_activity_summary`/`yard_map` in any of them.
  These surfaces already carry their own, separate, pre-existing `is_demo_
  source`/`_real_source_condition()` filtering from Review Queue Count
  Truth Consistency v1 and Native-Windows & Packaging Acceptance v1,
  untouched by this diff.
- **Truth-state mutation:** none, reconfirmed directly against the diff
  (§P's own claim, independently checked here rather than taken on faith):
  every change is a read-side filter addition (`_real_stream_ids`,
  `is_real_source`, the `real_stream_ids`/`stream_id_by_event_id` lookups
  and their use in list comprehensions/loop conditions); no `INSERT`/
  `UPDATE`/`DELETE`, no `session.add`/`session.delete`, no write to
  `review_status`/`reviewed_label`/`is_authoritative`/`is_superseded`
  anywhere in either changed source file.
- **Working-tree/protected-file state, including a disclosed concurrent
  -session incident:** the seven preserved untracked detector files (§13)
  and `uv.lock` were re-confirmed present and untouched (unchanged mtimes)
  at multiple points across this session. Unlike every prior milestone's
  identical check, this session's own peer-session inventory did *not*
  stay clean throughout: a second session sharing this exact milestone and
  working tree (`Analytics & Local Data Truth Consistency`, no "v1", a
  separate live Claude Desktop session on this machine) was found mid-
  session to have edited `tests/test_taxonomy.py` and `tests/test_source_
  provider_smoke_flows.py` directly in this working tree while idle-
  status was last confirmed clean moments earlier -- a real violation of
  §13's "never allow multiple Claude writer sessions in the same working
  tree" rule, not prevented, only detected after the fact. Handled rather
  than ignored: verified both edits' correctness directly (§N) before
  relying on them; coordinated live via cross-session messaging for the
  remainder of the session (shared Tier 3/e2e responsibility explicitly,
  to avoid duplicating or contending); one near-collision (both sessions
  independently started a full Core run within the same minute, real
  simultaneous CPU/IO contention observed directly via `ps`) caught within
  about a minute and resolved by stopping this session's own redundant run
  rather than the peer's. HEAD never moved during any of this (verified
  repeatedly); no commit, push, or destructive operation occurred from
  either session before this report's own commit, below. Full, unredacted
  disclosure rather than a narrative that omits it: this reduces confidence
  in the "no active writer session" claim's usual strength for this one
  milestone specifically, even though the outcome was verified correct.

## S. Remaining concrete v0.1 blockers

None release-blocking; disclosed rather than silently left:

- `SpeciesCoverageCard.tsx` is not mounted anywhere in the running app
  (§F) -- its data-layer correctness is fixed by this milestone regardless,
  but it has no live UI surface today. Mounting it is a UI-composition
  change, explicitly out of this milestone's own non-goals (no redesign);
  a reasonable candidate for whichever future session next touches
  Analytics/Species Coverage UI composition.
- This milestone's own Phase 6 consumer search was deliberately bounded to
  producers/consumers of the five named summary types
  (`AnalyticsSummary`, `YardMapActivitySummary`, `DatasetCoverageSummary`,
  `DatasetQualitySummary`, `LocalDataStatus`) and `AdapterEvaluationSummary`
  for contrast, per the governing brief's own explicit instruction not to
  expand into a general code audit. Separate, unrelated summary surfaces
  that do not consume any of these five objects (Place Biodiversity
  Summary, Place Change/Habitat summaries, and others) were not examined
  and may or may not have an analogous defect -- genuinely unknown, not
  silently assumed clean, and out of this milestone's own bounded
  authorization to investigate.
- The one incomplete live Camera Node fresh-pairing proof carried forward
  from Native-Windows & Packaging Acceptance v1 (`release-execution-
  state.md` §3/§6.G) remains open and untouched by this milestone.

## T. Advisory next step only

Per the governing brief, this report does not authorize the next
milestone. Advisory only: the expected next global phase remains UI/UX &
First-Run Adoption v1, per this milestone's own authorizing brief. The two
items in §S (mounting `SpeciesCoverageCard`, and whether Place Intelligence
-family summaries share an analogous demo-inclusion gap) are reasonable
candidates for a future session to fold into that phase's own scoping pass
or a dedicated follow-up, not urgent on their own.
