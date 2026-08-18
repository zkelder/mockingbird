# v0.1 Product Flow Gap Pass v1 -- audit findings and fixes

Status: bounded product-completion pass (not an architecture milestone).
Starting HEAD `79be29e`. Audited the working product from a new/ordinary
home-wildlife-observer's perspective across the seven required journeys in
the milestone brief, using real persisted field-session data (a read-only
copy of the WSL checkout's own `data/mockingbird.sqlite3`: 3 Streams, 235
Events/Visits, 59 ReviewLabels, 830 MediaAssets, spanning real Jul-Aug 2026
sessions) plus a genuinely fresh/empty database for first-run states, at
desktop (1440px) and narrow (375px) widths, against the actual current
frontend build. See [roadmap.md](roadmap.md) "Current status" for the
one-paragraph summary this document backs.

## Methodology note: a stale packaged build shadowed the dev checkout

Early in this audit, `src/mockingbird/web_dist/` -- a leftover packaged
snapshot from an earlier (2026-08-12) packaging session, gitignored and
disposable -- was silently shadowing every rebuild of the dev checkout's own
`web/dist`, because `mockingbird.web_app.resolve_frontend_dist()` checks the
packaged location first. Roughly the first hour of screenshots in this audit
were unknowingly auditing week-old UI. Discovered via DOM-level forensics
(a "Bird Log" nav-placement discrepancy that traced, through bundle-content
grepping and directly diffing served bytes against disk, to two different
builds entirely) and corrected by deleting the stale directory and
re-verifying the served asset hash matched the current `web/dist` before
re-shooting the full screenshot set. Recorded for future sessions in project
memory (`packaged-web-dist-shadows-dev-build`).

## P0 findings (fixed)

### Dashboard/product-health never reflect an observing Camera Node Stream

- **Journey:** Monitoring / Camera / System Health (also surfaced on Today).
- **Observed:** `_dashboard_runtime_by_stream` (`api/main.py`, feeding both
  `GET /api/dashboard/summary` and `GET /api/product/health`) consulted only
  `LiveCameraSessionManager`/`SourceMonitorManager`, never
  `ObservationEngineSessionManager`. A paired Camera Node Stream's legacy
  live-view session is *deliberately* paused for the entire time Observation
  Engine owns the camera (`architecture.md` "Live camera ownership"), so
  `monitoring_active` was structurally always `False` for a genuinely,
  successfully observing Camera Node Stream -- the accepted, primary
  Observation path. `ProductHealthPanel`'s always-visible "Observing X of Y
  cameras" Dashboard line undercounted real observation, and
  `TodayReportPanel`'s empty-state branch showed "Monitoring hasn't started
  yet / Start observing on your camera..." -- actively telling the user to
  do something they had already done -- while Stream Detail's own
  Observation panel, and the Dashboard's own `LiveCameraOverview` tile
  (independently fixed for a related gap in an earlier session via
  `liveSessionPausedForObservation`), correctly showed "Observing" on the
  very same page.
- **Expected:** the Dashboard's own summary of "is this monitoring" must
  agree with itself and with Stream Detail.
- **Why it matters for v0.1:** this is exactly the milestone's journey-6
  question #1 ("Is MockingBird monitoring?") answered wrongly, on the
  primary landing page, for the accepted primary product path, with a
  message that directly contradicts a successful user action.
- **Evidence:** code-traced (not live-hardware-verified; no real Camera Node
  is reachable from this sandbox) through `architecture.md`'s own documented
  pause/resume contract, `LiveCameraOverview.tsx`'s existing code comment
  describing the identical gap it already worked around for its own tile,
  and confirmed by zero existing test coverage for this interaction
  (`grep` for `camera_node` in `tests/test_dashboard_today.py`: 0 hits).
- **Fix:** `_dashboard_runtime_by_stream` now also reads the same
  side-effect-free `ObservationEngineSessionManager.status()` Stream Detail
  already uses, for `camera_node`-provider Streams only, folding `observing`
  into `monitoring_active`/`monitor_control`. No new detector/tracker/
  threshold. `can_start_monitor`/`can_stop_monitor` stay scoped to the
  legacy subsystem (Camera Node never uses that toggle; already hidden for
  it in `LiveCameraOverview.tsx`).
- **Tests:** `tests/test_dashboard_observation_engine_truth.py` (new, 4
  tests: observing-Camera-Node-Stream positive case, idle-Camera-Node
  negative control, non-Camera-Node negative control, `/api/product/health`
  case). RED confirmed before the fix. Verified zero regression: the 21
  pre-existing failures in `tests/test_stream_playback_contract.py` are
  byte-identical (same test names) with and without this change, confirmed
  by running against pristine clean HEAD in isolation.
- **Commit:** `e52e13e`.

## P1 findings (fixed)

### Stream Detail's "Stream events" list: unbounded and oldest-first

- **Journey:** Bird Log / Species / History (also Today / current activity).
- **Observed:** `ProductRepository.events_for_stream` had no `limit` at any
  layer (repository query, API route, or frontend render) and ordered
  ascending (oldest first) -- unlike the sibling "Recent Visits" section on
  the same page, already correctly bounded (`limit`, default 12, max 50) and
  `.desc()`-ordered. A real Pi Camera Node Stream's history (235 events over
  ~3 weeks of real use) rendered a 55,131px-tall Stream Detail page with
  200+ fully-rendered event cards, oldest first -- a user would have to
  scroll past weeks of old motion events before reaching anything recent.
- **Expected:** bounded, newest-first, matching the neighboring section's
  own already-correct convention.
- **Why it matters for v0.1:** directly undermines "history... easy to
  rediscover" and "a record of wildlife... not a stream of detection
  events" (this milestone's own explicit framing for the Bird Log/History
  journey); would only worsen as any real installation's history grows over
  months.
- **Evidence:** measured directly (55,131px page, `document.body.scrollHeight`;
  200+ `"Live motion activity..."` headings enumerated via DOM query) against
  real field data.
- **Fix:** `events_for_stream`/`GET /api/streams/{id}/events` take a bounded
  `limit` (default 50, matching the existing `MAX_ALERT_PAGE_SIZE`
  convention; capped at 100) and order `started_at.desc()`. One added
  frontend caption ("Newest activity for this Stream"). `StreamPanel.tsx`'s
  small footer event/needs-review counts (fed by this same now-bounded list)
  relabeled "recent events"/"recent needs review" so they no longer silently
  imply a lifetime total; the page's own prominent, accurate "N needs
  review" pill is sourced separately (`streamReviewCount`, from the Review
  Queue's own stream-scoped read) and is unaffected.
- **Tests:** `tests/test_api.py::test_stream_events_are_bounded_and_newest_first`
  (new; 60 synthetic events prove both the bound and the order; RED before
  the fix showed 62 events, oldest first). Full `tests/test_api.py`: 54/54
  passed.
- **Commit:** `5e1dd5f`.

### Analytics/Insights page's Dataset QA panel: unbounded issue list

- **Journey:** Bird Log / Species / History (Insights is the primary-nav
  "Analytics" page).
- **Observed:** `DatasetQualityPanel`'s non-compact variant rendered
  `quality.issues` with no cap -- the identical unbounded-list pattern as
  the Stream events finding above, independently discovered on a different
  primary-nav page. A real 420-issue history rendered 51,213px from this one
  section alone (of a 55,789px total page).
- **Expected:** bounded detail list; the aggregate stat tiles (already
  correct) stay exactly as accurate.
- **Why it matters for v0.1:** same class of defect as the Stream events
  finding -- confirms this was a recurring pattern-class, not an isolated
  incident, worth fixing at both sites found rather than declaring done
  after one.
- **Evidence:** measured directly (51,213px section height; `GET
  /api/dataset-quality/summary` returned `issue_count: 420`, `issues` array
  length 420).
- **Fix:** every `DatasetQualitySummary` aggregate count (`issue_count`,
  `high_count`, `medium_count`, `unknown_label_count`, ...) is computed from
  the complete, untruncated `issues` list earlier in
  `_dataset_quality_summary` (`severity_counts`/`type_counts` are both
  `Counter(... for issue in issues)` over the full list) -- only the
  `issues` list actually returned is sliced to `MAX_DATASET_QUALITY_ISSUES`
  (50) *after* that accounting, so the accurate "420 issues, 177 high" stat
  tiles are provably unaffected. One added frontend caption: "Showing the 50
  highest-priority issues of 420 total" (exact numbers), shown only when the
  list is actually truncated.
- **Tests:** `tests/test_dataset_quality.py::test_dataset_quality_issue_list_is_bounded_but_counts_stay_exact`
  (new; 30 real API-created issues via the existing `import_unknown_bird`
  helper prove the bound while every count-delta stays exact; RED before the
  fix showed 61 issues returned, no cap). Full
  `tests/test_dataset_quality.py`: 7/8 passed; the 8th
  (`test_conflicting_corrections_are_reported`) is a genuine pre-existing
  failure, independently reproduced against pristine clean HEAD with zero of
  this milestone's changes present (confirmed twice: once with only
  `product_repository.py` reverted, once with both `product_repository.py`
  and `api/main.py` reverted) -- unrelated, left untouched per this
  milestone's explicit test-baseline-cleanup boundary.
- **Commit:** `00b3a4b`.

### Narrow-width overflow on Stream Detail's camera view/placeholder

- **Journey:** Responsive and accessibility blockers (also Monitoring/Camera,
  since this is the surface every Stream type shows whenever not actively
  streaming a decoded frame).
- **Observed:** at the existing 640px narrow-width breakpoint,
  `.stream-scene`/`.stream-live-frame`'s base-rule `aspect-ratio: 16 / 9`
  computed a width from the (correctly reduced) 260px `min-height` that
  exceeds the actual narrow viewport -- no `max-width` safety net existed to
  make `aspect-ratio` yield to `min-height` instead of the reverse.
- **Expected:** no visible content cut off at a real narrow/phone width.
- **Why it matters for v0.1:** a real, visible instance of exactly the
  milestone's own "overflow/cutoff... unusable narrow-width layouts" check,
  on the product's central visual surface, reached from Dashboard, Cameras,
  and every camera tile.
- **Evidence:** measured directly (462px wide inside a 375px viewport via
  `getBoundingClientRect()`) and confirmed visually (a cropped screenshot
  showing the "Camera session stopped" heading and panel border clipped on
  the right edge).
- **Fix:** `max-width: 100%` added to both narrow-width rules (2 lines).
- **Verification:** measured width dropped from 462px to 331.5px (fits with
  room for padding); a fresh screenshot shows the heading and panel border
  fully visible. A separate, much smaller (~20px) residual overflow from
  `.stream-ground`'s intentional `-5%` decorative background-bleed inset
  remains and was deliberately left alone -- affects no text or interactive
  content, disproportionate to chase per this milestone's "not a visual
  redesign" scope. No new automated test added (pure 2-rule CSS change,
  verified directly via automated DOM measurement + visual screenshot,
  proportionate to the change's size).
- **Commit:** `8fe2c81`.

## P2 findings (documented, intentionally not fixed)

Kept out of this pass per the milestone's own "prefer a small coherent set
of fixes" and "be skeptical of promoting cosmetic concerns to P1" guidance.

- **Redundant species-name display** on Visit Detail's species-suggestion
  cards: `<h4>{displayName}</h4>` followed by a separate `<span>` repeating
  the common name when no scientific name exists to pair it with
  (`VisitDetailPage.tsx` ~line 1414-1424). Real (DOM-confirmed), but purely
  visual redundancy, not confusing about truth.
- **"Source evidence trace" panel** on Visit Detail is always fully expanded
  (raw IDs: `motion-evidence-XXX`, `event-motion-XXX`) rather than tucked
  into a collapsed "Advanced" disclosure the way the Observation panel's own
  convention does. Real, moderate; doesn't mislead, just denser than ideal
  for a fully-polished v0.1.
- **Cameras/Streams page's primary "Add Camera" entry** lives inside a
  collapsed-by-default "Camera setup and repair" `<details>`, not visible at
  a glance on that specific page. Mitigated by the prominent, always-visible
  "Add Camera" button on the Dashboard hero -- the actual first-landing page
  for both first-run and ordinary use.
- **"Bird Log" (nav) vs. "Wildlife Journal" (page heading)** naming
  inconsistency. Low confusion risk given unambiguous context.
- **Species Suggestions / Advanced Evidence pages'** narrow-width overflow
  (measured via the same automated DOM check used for the Stream Detail
  finding above). Real, but both are explicit developer-only surfaces gated
  behind "Developer Mode," held to a lower narrow-width polish bar per
  doctrine's "advanced diagnostics" framing.
- **Review Queue's filter-panel** labels/inputs ~20px narrow-width overflow.
  Minor, low visual impact, not investigated further.

## Later / roadmap items (explicitly out of scope, left untouched)

- **Zone-drawing keyboard accessibility.** `StreamPanel.tsx`'s zone-drawing
  SVG surface is pointer-event-only; no keyboard-equivalent path to draw or
  adjust a Zone polygon exists. Real, but a substantial feature addition
  (keyboard-driven polygon editing), not a bounded fix -- belongs to a
  dedicated accessibility milestone.
- **Broader "unbounded list" sweep.** This pass fixed the two clearest,
  highest-visibility instances found (Stream events, Dataset QA) of what
  turned out to be a recurring pattern-class. It did not perform an
  exhaustive repository-wide audit for every other possible unbounded list
  render, which would have expanded this pass beyond "bounded." Worth a
  dedicated pass later if further instances surface in real use.
- Full first-run onboarding polish, Place Intelligence, Camera Node
  productization, and every other roadmap item the milestone brief listed as
  explicitly preserved-but-not-implemented here.

## Files changed

- `src/mockingbird/api/main.py` -- Camera Node engine-status read in
  `_dashboard_runtime_by_stream`; bounded `limit` query param on
  `GET /api/streams/{id}/events`.
- `src/mockingbird/repository/product_repository.py` -- `events_for_stream`
  bound + `.desc()` order; `_dataset_quality_summary`'s returned `issues`
  list bounded (counts unaffected); two new module constants
  (`MAX_DATASET_QUALITY_ISSUES`; existing `MAX_ALERT_PAGE_SIZE` reused as the
  events-list default).
- `web/src/pages/StreamDetailPage.tsx` -- "Newest activity for this Stream"
  caption.
- `web/src/components/StreamPanel.tsx` -- "recent events"/"recent needs
  review" footer relabel.
- `web/src/components/DatasetQualityPanel.tsx` -- "Showing the N highest-
  priority issues of M total" caption.
- `web/src/styles.css` -- `max-width: 100%` on `.stream-scene`/
  `.stream-live-frame` at the existing narrow-width breakpoint.
- `tests/test_dashboard_observation_engine_truth.py` (new),
  `tests/test_api.py`, `tests/test_dataset_quality.py` -- focused regression
  coverage for the three backend fixes.

## Pre-existing, unrelated failures encountered (not touched)

All independently reproduced against pristine clean HEAD (`79be29e`) with
zero of this milestone's changes present, via a temporary isolated `git
worktree` (frontend) and direct file-content restoration (backend) -- never
by assuming absence of evidence:

- `tests/test_stream_playback_contract.py`: the identical 21 test names
  fail with and without this milestone's changes (live-motion/burst/zone-
  policy tests, unrelated to this milestone's surfaces).
- `tests/test_dataset_quality.py::test_conflicting_corrections_are_reported`:
  fails identically on clean HEAD.
- `web/e2e/reviewed-product-loop.spec.ts` ("a ranked species suggestion
  becomes correction, Bird Log, and export truth"): fails identically on
  clean HEAD in an isolated worktree (own venv/node_modules symlinked in,
  zero shared mutable state with the main checkout).

These are consistent with the milestone brief's own disclosed "~29
pre-existing/order-dependent" backend baseline and are recorded here, not
fixed, per the milestone's explicit test-baseline-cleanup boundary.
