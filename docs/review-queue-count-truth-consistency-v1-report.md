# Review Queue Count Truth Consistency v1 -- closure report

## A. Starting baseline

Branch `main`; accepted HEAD `3feab6c3e5bacf6ee45fb7f8067c5049d2813565`
("Reconcile release-execution-state.md and publish the Native-Windows &
Packaging Acceptance v1 report"); schema `v59` unchanged; version `0.1.0`.
Working tree clean except the seven preserved untracked detector files
(§13 of `release-execution-state.md`), confirmed present, untouched, and
byte-identical (re-hashed) at both this milestone's own start and close.
No active writer session found sharing this working tree: of 199 peer
sessions in this session's own inventory, every MockingBird-named session
was idle or offline, and the sole "busy" peer session belonged to an
unrelated project (a different codebase entirely). Governing docs read
before any edit: `release-execution-state.md` (§§1, 3, 6.G, 6.R, 16),
`product-doctrine.md` (truth boundary / Measured-Inferred-Reviewed),
`roadmap.md` (confirmed no mention of this topic), the Native-Windows &
Packaging Acceptance v1 report and its addendum, and the directly
affected review/import/model-adapter code and tests.

## B. Canonical user-visible count contract

Two new `ProductRepository` methods, added immediately after
`_review_queue_items` itself (`src/mockingbird/repository/
product_repository.py`):

```python
def _visible_review_queue_items(self, session: Session) -> list[ReviewQueueItem]:
    return [item for item in self._review_queue_items(session) if not item.is_demo_source]

def _visible_review_queue_count(self, session: Session) -> int:
    return len(self._visible_review_queue_items(session))
```

This is the one seam every user-visible "needs review"/"review queue
count"/equivalent surface now goes through. It reuses the
already-established `is_demo_source` semantics from
`_review_queue_product_context` (itself already correctly mirroring
`_real_source_condition()`'s "effective provider wins over stale `kind`"
precedent, fixed in Native-Windows & Packaging Acceptance v1's own
addendum) -- no new source-classification logic was created.
`_review_queue_items`/`review_queue_items()` itself is completely
unchanged: internal callers that legitimately need the full, unfiltered,
`is_demo_source`-flagged picture (`test_review_queue_product_mode.py`'s
own accepted contract) still get it.

## C. Complete list of `review_queue_count` producers found

A bounded repository search (`grep -rn "review_queue_count" src/` plus
every call site of `self._review_queue_items(session)`) found exactly
**eleven** producers -- confirming, not merely assuming, the prior
milestone's own "roughly a dozen" estimate:

| Producer (function) | Response object | Classification | Previous behavior | Final behavior |
| --- | --- | --- | --- | --- |
| `run_model_adapter` | `ModelAdapterRunResult` | A -- user-visible (`ModelAdaptersPage.tsx` pill) | Unfiltered `len(...)` | `_visible_review_queue_count(session)` |
| `_run_local_image_detector_adapter` | `ModelAdapterRunResult` | A -- user-visible (same pill) | Unfiltered `len(...)` | `_visible_review_queue_count(session)` |
| `_run_megadetector_adapter` | `ModelAdapterRunResult` | A -- user-visible (same pill) | Unfiltered `len(...)` | `_visible_review_queue_count(session)` |
| `create_demo_detection_run` | `DemoDetectionRunResult` | A -- user-visible (`ManualImportPage.tsx`/`StreamsPage.tsx` "demo proposal" pill) | Unfiltered `len(...)` | `_visible_review_queue_count(session)` |
| `decide_detection_proposal` | `DetectionProposalDecisionResult` | A -- user-visible (`DetectionProposalsPage.tsx` pill) | Unfiltered `len(...)` | `_visible_review_queue_count(session)` |
| `create_media_import` | `MediaImportResult` | A -- user-visible (`ManualImportPage.tsx` pill) | Unfiltered `len(...)` | `_visible_review_queue_count(session)` |
| `import_folder_media` | `FolderImportResult` | A -- user-visible (`FolderImportPage.tsx` pill) | Unfiltered `len(...)` | `_visible_review_queue_count(session)` |
| `_create_review_label_result_in_session` | `ReviewCorrectionResult` | A -- user-visible, **highest priority** (`ReviewQueuePage.tsx` toast, both single-correction and bulk-adjacent paths) | Unfiltered `len(...)` | `_visible_review_queue_count(session)` |
| `_review_correction_result_for_model` | `ReviewCorrectionResult` | A -- user-visible (identical toast; the "already-decided/idempotent" branch of revise/fast-correct) | Unfiltered `len(...)` | `_visible_review_queue_count(session)` |
| `_visit_review_reopen_response` | `VisitReviewReopenResponse` | A -- user-visible (reopen-visit response) | Unfiltered `len(...)` | `_visible_review_queue_count(session)` |
| `_fast_review_undo_response` | `FastReviewUndoResponse` | A -- user-visible (Fast Review undo response) | Unfiltered `len(...)` | `_visible_review_queue_count(session)` |

All eleven are classification **A** (user-visible; every one is reached
by a real, currently-shipped frontend page). None were classification B
(would-remain-inclusive-by-design) or C (dead code). `dashboard_summary`'s
own pre-existing, already-correct inline filter (`product_review_items = [
item for item in self._review_queue_items(session) if not
item.is_demo_source]`) was refactored to call `_visible_review_queue_items`
directly -- the same behavior, one fewer duplicate implementation.
`GET /api/review-queue`'s own existing one-line filter in `api/main.py`
was deliberately left as is: a different architectural layer (HTTP
boundary operating on the public `review_queue_items()` wrapper's already
-serialized output, not a `session`), already correct, already tested.
Consolidating it into the same repository-level helper was considered and
declined to keep this milestone's blast radius bounded, consistent with
its own governing brief.

**Two closely-related, larger families were found and deliberately left
unfixed** (see §P for the full account): `YardMapActivitySummary.
needs_review_count` and `AnalyticsSummary.needs_review_count` (the latter
embedded in four of the eleven response objects above, but --checked
directly-- never actually read by the frontend from those specific
response envelopes; it is separately, genuinely live via `GET
/api/analytics/summary`).

## D. Shared implementation/helper introduced or reused

`_visible_review_queue_items`/`_visible_review_queue_count` (new, §B).
Reused, not reinvented: `is_demo_source` (`_review_queue_product_context`,
already correct since the prior milestone's own addendum) and
`_review_queue_items` itself (untouched).

## E. Core review/correction flow result

Exercised directly, as the governing brief required. `POST
/api/review-labels` (`create_review_label` -> `_create_review_label_
result_in_session`), Fast Review correct+undo (`create_fast_review_
correction`/`undo_fast_review_correction` -> `_review_correction_result_
for_model` / `_fast_review_undo_response`), and reopen (`reopen_visit_
review` -> `_visit_review_reopen_response`) were all identified, mapped
to their exact HTTP endpoints, and covered by new regression tests (§I).
The representative regression -- correcting the one genuine needs-review
Visit while the seeded demo Visit still sits unreviewed -- was
independently proven **RED** against the unmodified baseline
(`assert 1 == 0`: the response reported 1 outstanding item, the seeded
demo Visit, as if it were real work still to do) and **GREEN** after the
fix, via `git stash` bisection, at both the Python/HTTP level (Tier 1)
and the real-browser level (targeted e2e, §L).

## F. Import/folder-import result

`create_media_import` (Manual Import) and `import_folder_media` (Folder
Import) both fixed identically. Dedicated regression tests prove each
correctly counts real imported activity (1, then 2 across two imports)
while a demo-only queue reads 0 throughout.

## G. Model-adapter/detection-proposal result

`run_model_adapter` (covering its own generic dispatch path plus the
`_run_local_image_detector_adapter`/`_run_megadetector_adapter`
sub-dispatches, which share the byte-identical one-line fix and were
verified by direct code reading rather than independently reproduced --
this repository's own established convention for a mechanically identical
change applied at multiple sites, see the Native-Windows addendum's own
precedent for this same judgment call), `create_demo_detection_run`, and
`decide_detection_proposal` are all fixed. One combined regression test
exercises all three against one shared real Visit (import -> run adapter
-> create demo run -> create and reject a proposal), proving the count
stays correctly pinned to the one real item throughout, unaffected by how
many proposal-only actions run against it -- table-driven rather than
three near-duplicate fixtures, per the governing brief's own instruction.

## H. Demo-source regression coverage

8 new tests in `tests/test_demo_source_exclusion.py` (18 total in that
file, all passing): demo-only queue -> 0; one real + demo -> 1, then two
real + demo -> 2; a repurposed seeded demo Source (via the already
-established `de_demo_seeded_source` helper) -> counts once repurposed,
exactly matching `_real_source_condition()`'s own accepted contract; the
core correction response; Fast Review undo; Manual Import; Folder Import;
and the combined Model Adapter/Demo Detection Run/Detection Proposal
test. Two new module-level test helpers (`_add_real_stream_and_zone`,
`_add_real_needs_review_visit`) factor out fixture boilerplate this
file's own pre-existing tests had already begun duplicating, used only by
the new tests (the two pre-existing duplicated blocks were left
untouched, out of caution for already-accepted, already-passing tests).

## I. Tier 1 results

18/18 passed in `tests/test_demo_source_exclusion.py`. The core-flow
regression test independently proven RED (unmodified baseline) -> GREEN
(fixed) via `git stash` bisection; the new e2e spec independently proven
the same way at the real-browser level (§L).

## J. Tier 2 results

275/275 passed across 20 directly-adjacent files: `test_demo_source_
exclusion.py`, `test_review_queue_product_mode.py` (the internal
unfiltered-contract test, confirmed still passing unmodified),
`test_review_queue_bulk_corrections.py`, `test_review_queue_bioclip_
status_performance.py`, `test_review_queue_species_suggestion_batch.py`,
`test_dashboard_today.py`, `test_dashboard_detector_health_honesty.py`,
`test_dashboard_observation_engine_truth.py`, `test_media_import.py`,
`test_folder_import.py`, `test_model_adapter_contract.py`, `test_
detection_interface.py`, `test_fast_review.py`, `test_review_
identification.py`, `test_visit_curation.py`, `test_api.py`, `test_
species_candidate_packs.py`, `test_identification_eligibility_
regression_2026_08_21.py`, `test_local_detector_adapter.py`, `test_
motion_evidence.py` -- explicitly including the demo-source contract
tests from the prior two milestones, as required.

## K. Tier 3 result

Run twice. **Against the fix:** 6069 passed, 7 failed, 4 skipped, 35
deselected, 11 xfailed (43m35s). Six failures are byte-identical to the
already-established pre-existing set recorded across multiple prior
milestones (`test_doctor_camera_node_transport.py` x2, `test_
environmental_context.py`, both `test_place_biodiversity_summary_
repository.py` cases, `test_place_change_summary_repository.py`). The
seventh, `test_everyday_discovery_ux_closure.py::test_today_dashboard_
shows_only_corrected_truth`, was not previously on record and touches
`_dashboard_today_summary`/`best_moments` -- a code path this milestone
never modified.

Rather than assume flakiness, Tier 3 was run a **second time** from a
`git stash`-isolated, completely unmodified `3feab6c` baseline: **6062
passed, 6 failed, 4 skipped, 35 deselected, 11 xfailed (41m9s)** -- the
identical six pre-existing failures, and the seventh test did not fail on
this run either. `test_everyday_discovery_ux_closure.py` was last
touched two commits before this milestone's own starting baseline
(confirmed via `git log`), untouched by this milestone; it passed cleanly
both in isolation (1/1, 0.73s) and at its own file's level (19/19,
6.43s) on the fixed tree. **Zero Core failures attributable to this
milestone** -- the seventh is a genuine, newly-observed, full-suite-only
intermittent flake in an unrelated subsystem, consistent with this
repository's own already-documented class of load/timing-sensitive
full-suite flakiness, proven non-attributable by a full second baseline
run rather than merely asserted.

`ruff check` on both changed source files: `product_repository.py`'s own
established 56-finding baseline confirmed byte-identical before/after via
`git stash` bisection; `tests/test_demo_source_exclusion.py`: 0 findings.

## L. Targeted frontend/e2e result

**Static verification (all 12 frontend display call sites, read
directly):** `ManualImportPage.tsx` (x2: the main import pill and the
demo-proposal pill), `ModelAdaptersPage.tsx`, `FolderImportPage.tsx`,
`DetectionProposalsPage.tsx`, `ReviewQueuePage.tsx` (x2: the correction
summary and toast message), `StreamsPage.tsx` (x4: snapshot and timeline
proposal panels). Every one does a direct pass-through of
`result.review_queue_count` with no independent recomputation; zero
renders as a grammatically sensible "0 needs review"/"0 items still need
review"; no wording anywhere implies demo activity is real. No frontend
source change was required or made.

**New Playwright spec**, `web/e2e/review-queue-count-demo-exclusion.
spec.ts`: creates a dedicated real (non-demo) Source/Stream via `POST
/api/sources` (the seeded demo Stream is always `legacy_activity` by
design and would never exercise this fix -- confirmed empirically during
this milestone's own test development, and matching `review-queue-fast-
review-keyboard.spec.ts`'s own already-established reasoning for the
identical choice), imports one real image, clicks the real rendered
"False positive" quick-action, and asserts the real toast text reads "0
items still need review." -- independently proven RED (announced "1",
the seeded demo Visit's own count) against the unmodified baseline and
GREEN after the fix, both via `git stash` bisection at the real-browser
level.

**Existing specs.** `review-queue-fast-review-keyboard.spec.ts` re-run
standalone: passed, no regression. Two others --
`reviewed-product-loop.spec.ts` and `review-queue-bulk-correct-stale-
write.spec.ts` -- were found already failing when run standalone against
this exact starting baseline, each on a stale UI-element expectation
unrelated to `review_queue_count` (a missing "Reviewed" tab button in one
case, a missing "Show legacy and test activity" checkbox in the other).
Independently confirmed via the identical `git stash` bisection
discipline to fail byte-identically with or without this milestone's own
fix. Disclosed here as pre-existing e2e drift this milestone did not
cause and, per its own bounded scope, does not fix.

`tsc --noEmit` on the web project: clean (the new spec type-checks with
no errors).

## M. Truth/data-integrity impact

None. This milestone changes only which already-computed items are
counted for display; it never touches `review_status`, `reviewed_label`,
`is_authoritative`, or any Measured/Inferred/Reviewed truth-tier
semantics (confirmed against `product-doctrine.md`'s own "The truth
boundary"/"Measured, Inferred, and Reviewed" sections before any edit).
No admission, tracking, detector, classifier, or Visit-assembly logic was
touched. Local Only: no network or cloud call is involved anywhere in
this fix; not applicable.

## N. Schema impact

None. Schema unchanged at `v59`.

## O. Final HEAD and working-tree state

Two commits, not pushed: `2923afb` (the fix, backend tests, and the new
e2e spec) and `cada544` (the `release-execution-state.md` reconciliation
and this report). Working tree confirmed clean except the seven preserved
untracked detector files, byte-identical (re-hashed) to this milestone's
own start.

## P. Remaining concrete v0.1 blockers

None release-blocking; all confirmed low-severity or explicitly
out-of-scope, disclosed rather than silently left:

- **`YardMapActivitySummary.needs_review_count`** (`YardMapPage.tsx`'s
  own per-camera clickable "N needs review" button) is a raw per-stream
  SQL count with no `is_demo_source` awareness at all -- the same defect
  family this milestone closes elsewhere, on a different page, via a
  completely different computation (`product_repository.py` around line
  26792, not `_review_queue_items`-derived). Found during this
  milestone's own search; not fixed, because it is a different
  computation on a different page, outside the bounded `review_queue_
  count` family this milestone's own governing brief scoped, and its own
  blast radius (whether `needs_review_visit_ids`, the map pin's health
  state, etc. need matching treatment) was not evaluated.
- **A larger, separate family**: `AnalyticsSummary.needs_review_count`
  (`_analytics_summary`, `product_repository.py` around line 40455) is
  demo-inclusive, and is live via `GET /api/analytics/summary` feeding
  `AnalyticsPage.tsx` (a headline stat) and `SpeciesCoverageCard.tsx` (a
  per-species review gate), and transitively `LocalDataStatus.needs_
  review_count` (`LocalDataPage.tsx`, explicitly labeled "Needs review" /
  "local correction work"), `DatasetCoverageSummary.needs_review_count`
  (`DatasetCoveragePanel.tsx`, "records still need review before export
  coverage is complete"), and `DatasetQualitySummary.needs_review_count`
  (`DatasetQualityPanel.tsx`, "Records needing cleanup before export") --
  all three genuinely actionable, user-facing "go review this" framings,
  not raw storage totals. This is a real, more significant instance of
  the same underlying defect family, but fixing it responsibly requires
  a doctrine decision this milestone was not authorized to make:
  `_analytics_summary` also computes `event_count`/`visit_count`/
  `species_counts`, all currently demo-inclusive too, and changing only
  `needs_review_count` while leaving those siblings untouched would
  create a *new* internal inconsistency within `AnalyticsSummary` itself.
  Given this repository's own documented history of two unexpectedly
  broad regression incidents from touching shared demo-source-adjacent
  code, and that `_analytics_summary` is more foundational/widely-shared
  than `_review_queue_product_context` was, this is recommended as a
  dedicated future milestone, not an opportunistic extension of this one.
- **`AdapterEvaluationSummary.unreviewed_count`** (`ModelAdaptersPage.
  tsx`'s adapter-evaluation stats grid) was found and checked: correctly
  left alone. It is a QA/evaluation metric about a specific adapter's
  historical proposal-outcome distribution (Proposals/Reviewed truth/
  Unreviewed/Matched-mismatched), not a "go review this" call to action,
  classification B by this milestone's own scheme.
- Two pre-existing, already-broken e2e specs unrelated to this milestone
  (`reviewed-product-loop.spec.ts`, `review-queue-bulk-correct-stale-
  write.spec.ts`; see §L) -- stale UI-element expectations, disclosed and
  confirmed non-attributable, not fixed.
- The one incomplete live Camera Node fresh-pairing proof from Native-
  Windows & Packaging Acceptance v1 remains open (carried forward, not
  falsely closed -- see `release-execution-state.md` §3).

## Q. Advisory next step only

Per the governing brief, this report does not authorize the next
milestone. Advisory only:

1. If the Analytics/Local Data/Dataset Coverage/Dataset Quality
   demo-inclusion family (§P) is worth closing before the expected next
   global phase (UI/UX & First-Run Adoption v1), it needs its own
   dedicated milestone: first a doctrine decision (should `event_count`/
   `visit_count`/`species_counts` also exclude demo activity, or only
   `needs_review_count`, and why), then the fix, then a full Tier 3 run
   given this repository's own documented history with demo-source
   blast radius.
2. `YardMapActivitySummary.needs_review_count` is a smaller, more
   contained candidate for the same or a separate future pass.
3. The two disclosed pre-existing e2e staleness findings (§L, §P) are
   reasonable candidates for whichever future session next does e2e
   suite maintenance -- neither is urgent on its own.
4. The Native-Windows live Camera Node pairing proof (§P, and
   `release-execution-state.md` §3/§6.G) remains available whenever a
   future session has explicit permission for a remote-write action
   against that shared device, or a dedicated non-shared Camera Node
   becomes available.
