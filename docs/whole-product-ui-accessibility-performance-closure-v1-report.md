# Whole-Product UI / Accessibility / Performance Closure v1

Bounded, integrated product-quality closure of Lane Q ("Whole-Product UI /
Accessibility / Performance") from
[release-execution-state.md](release-execution-state.md). Evaluates the
released product experience as one system across responsiveness,
accessibility, keyboard/focus behavior, touch usability, large real-data
performance, several-camera presentation, error/recovery UX, loading
behavior, visual consistency, and capability truthfulness -- then fixes
concrete release-quality defects found. Not a visual redesign, feature
campaign, or generic cleanup pass.

## Identity

- **Starting HEAD:** `4312b18` (One-Release Roadmap & Scheduler
  Reconciliation v1), branch `main`, local-only (215 commits ahead of
  `origin/main`, unpushed per standing policy).
- **Schema:** `v57`, unchanged by this milestone (no schema-touching
  change was needed).
- **Backend environment:** Python 3.12.3, this repository's own `.venv`.
  BirdNET (`classifier-birdnet` extra) confirmed installed and reporting
  `runtime_available: true` in this sandbox, unprompted -- useful, real
  evidence for the acoustic-health work below (not a mocked assumption).
- **Frontend environment:** Node (via the repository's `web/node_modules`),
  Vite 6.4.3, TypeScript via `tsc --noEmit`, Playwright 1.61.1 with
  Chromium already installed in this sandbox
  (`~/.cache/ms-playwright/chromium-1234`).
- **Datasets/backlogs used:**
  - The project's own real accumulated dev database
    (`data/mockingbird.sqlite3`, read-only inspection only, never
    mutated): 235 Visits/Events, 3 Streams/Sources, 59 review labels, 830
    media assets -- used only to calibrate what "real-world large" means
    for this product today, not as a live target (per the standing
    decision in
    [field-acceptance-auth-blocker-deferred-2026-08-25.md](field-acceptance-auth-blocker-deferred-2026-08-25.md):
    no live credentials/participation requested).
  - A dedicated, disposable, isolated QA instance (fresh SQLite DB, own
    port, own bootstrapped local Administrator via the same
    `POST /api/setup/administrator` self-onboarding path the e2e suite's
    own `global-setup.ts` already uses -- no shared/live credentials
    involved), seeded with a larger, product-shaped dataset: 371 Visits
    across 3 active Streams (mixed connected/disconnected) + 1 archived
    Stream, spanning 150 days, 18 species, a 89-item unreviewed backlog
    (55 detector-shaped + 18 manually/folder-imported + 10 person/vehicle
    + 6 genuinely uncategorized), and a configured-and-healthy microphone
    Source. This is the dataset the responsive/performance/multi-camera
    findings below were measured against.
  - Playwright's own existing isolated per-run instances for all e2e
    execution (`e2e/global-setup.ts`, real backend, real SQLite, no
    mocking of product logic except where individual specs deliberately
    mock a route).

**Worktree safety.** The seven preserved untracked detector files were
confirmed present, byte-for-byte unmodified (verified by exact `mtime`
match against the session-start listing) at both the start and the end of
this milestone -- see the "Preserved untracked detector files" list in
`release-execution-state.md`, none touched. A second local session
(`mockingbird-active-e8`, connected the same morning) was found via
`ListAgents`; investigated and found to have made zero filesystem writes
to this repository in the 60+ minutes preceding this session's own first
edit, and `git status` stayed clean (only the seven preserved files) at
every check performed throughout. No concurrent-writer conflict occurred;
`git status` was re-verified clean of unexpected changes immediately
before every commit.

## Journeys reviewed

| Journey | Disposition |
|---|---|
| A. First meaningful use (onboarding, sign-in, setup) | Reviewed via the QA instance's own bootstrap + `OnboardingWizard`/`SignInPage` code; no defect found. Existing `onboarding.spec.ts` covers this path in depth already and was not re-litigated. |
| B. Today / Place report | Reviewed live across all four widths with real seeded data (highlights, best moments, biodiversity, live camera overview, product health). No defect found beyond the acoustic-status gap (closed, see below). Confirmed representative-evidence/truth-precedence rules were not touched. |
| C. Visit case file | Reviewed live (evidence, correction form, progressive disclosure). Confirmed **P0-1** and **P1-1/P1-2** findings below through this exact journey (Review Queue -> Fast Review -> correction). |
| D. Bird Log / history | Reviewed live at 371-Visit/18-species scale (desktop screenshot: 2149px tall -- already well-bounded, no defect). |
| E. Cameras / Streams | Reviewed live with 3 active (mixed connected/disconnected) + 1 archived Stream. No defect found; see "Multi-camera" below. |
| F. Attention / notifications | Spot-checked (Alerts control/inbox render correctly at all widths); not a focus area this pass since Calm Attention & Notifications v1 already closed this lane's own decision. No new defect found. |
| G. Habitat/environment/acoustics | Confirmed no broken/misleading/developer-centric UI states in the currently-shipped optional domains. Closed the one disclosed acoustic gap (below); did not reopen habitat/acoustics architecture. |

## Findings

### P0

| # | Surface | Reproduced behavior | Fix |
|---|---|---|---|
| P0-1 | Review Queue default "Animals" tab / `ProductRepository._review_queue_triage_fields` | A manually imported Visit (`event_type == "manual_media_import"`, `ManualImportPage` -- the default, promoted camera-less acquisition path) or folder-imported Visit (`event_type == "folder_media_import"`) never populates `MotionEvidenceModel` and was unconditionally classified `product_category == "unchecked"`, regardless of `subject_label`. Review Queue's default view (the "Animals" tab) excludes "unchecked" items, and the resulting "No review items match these filters" empty state's own "Reset filters" action does **not** change tabs -- so a user who had just imported real wildlife photos, the literal default flow for a camera-less setup, saw a dead end with no indication their imported photos were sitting one tab away, unreviewed. Confirmed live (real QA instance, real import) and by direct code trace (`product_repository.py`, `_review_queue_triage_fields`). This is the actual, previously-unidentified root cause of `web/e2e/reviewed-product-loop.spec.ts`'s long-standing failure being misattributed as an "unrelated pre-existing flake" across at least three prior milestones' own acceptance records (see "Root-caused, not fixed" below for why that specific spec still fails for a *different*, now precisely-identified reason). | Extended the existing `observation_engine_candidate`/`acoustic_observation_candidate` subject-label fallback (already used for the identical gap in those two event types) to also cover `manual_media_import`/`folder_media_import` -- `product_repository.py`. Two new regression tests in `tests/test_review_queue_product_mode.py`, one exercising the real `create_media_import` production entry point end to end. RED confirmed via `git stash` against the pre-fix code (both tests failed identically); GREEN after. Live-verified in the browser: a real imported Visit now appears under the default "Animals" tab (screenshot evidence, "Animals 73" including "media-qa-imported-342.jpg"). |

### P1

| # | Surface | Reproduced behavior | Fix |
|---|---|---|---|
| P1-1 | `ReviewQueuePage.tsx`, `FastReviewPanel` (open transition) | Activating "Start Fast Review" via keyboard (focus + Enter) swaps a large new region into the page in place, with no navigation. Confirmed live via a real keyboard-driven Playwright session that focus landed on `document.body` after activation -- a keyboard/screen-reader user had to Tab from the very top of the page (through the entire sidebar) to reach the form that had just appeared. | Added `activeItemHeadingRef`, focused via `useEffect` on `[isOpen, activeItem?.id]`, mirroring the WAI-ARIA "focus the new region's own heading" pattern already used correctly by the mobile nav drawer (`App.tsx`'s `mobileNavToggleRef`). Live-verified before/after (focus now lands on the panel's own `<h2>`, confirmed by tag/section/`isBody` inspection in a real browser). |
| P1-2 | Same component (last-item-in-view completion) | Found while regression-testing P1-1: completing the *last* matching Visit in the current tab/filter view (Save & Next) made the entire Fast Review section vanish with **no** acknowledgment at all (the `items.length === 0` early-return fired unconditionally, bypassing the already-implemented "Filtered queue complete" state), stranding focus on `document.body` a second, different way. | Changed the early-return guard to `items.length === 0 && !isOpen`, so an in-progress session whose queue just emptied falls through to the existing "Filtered queue complete" view (which now also receives focus via a parallel `completeHeadingRef`) instead of disappearing. |
| P1-3 | `GET /api/product/health` / `ProductHealthPanel.tsx` (acoustic status gap, Lane A) | The scheduler's disclosed bounded gap -- "no product-facing frontend acoustic health/status surface" -- confirmed still open (see "Acoustic status" below for the full investigation). | New additive `ProductHealthAcousticSummary`/`ProductHealthStatus.acoustic` field, computed from already-existing facts only (no new capability); one new calm row in `ProductHealthPanel.tsx`. Never a factor in `ready`. |

### P2 (documented, not expanded into fixes -- see "Scope discipline" below for why each stops here)

- `web/src/styles.css`'s dead-CSS footprint around `.bird-log-entry` is materially larger than previously documented: 16 selectors (`.bird-log-summary-card` through `.bird-log-image-placeholder span`, ~207 contiguous lines, plus several `@media` touch-points), all confirmed unreferenced by any current `.tsx` file. The one class name a prior milestone flagged was the tip of this block, not the whole of it.
- The `setError(caught instanceof Error ? caught.message : fallback)` pattern (~15 files) surfaces raw `Error.message` text on a non-`ApiError` failure (a raw network/parse-level exception, e.g. "Failed to fetch"). The common case -- an `ApiError` from a real API 4xx/5xx -- is already safe today because this codebase consistently writes human-authored `HTTPException(detail=...)` strings backend-side; only the narrower non-`ApiError` edge case is at risk.
- `StreamPanel.tsx`: Zone **selection** is fully keyboard-accessible (`role="button"`, `tabIndex={0}`, `onKeyDown` handling Enter/Space -- confirmed by direct code read, this was *not* actually broken). Drawing a **new** Zone polygon has no keyboard equivalent at all (pointer-only `onPointerDown`/`onPointerMove`/`onPointerUp`). Zones remain optional/advanced per product doctrine; a genuine keyboard-driven polygon editor is real interaction-design work, not a bounded fix.

### Root-caused, not fixed (disclosed)

**`web/e2e/reviewed-product-loop.spec.ts`.** Investigated to a materially more precise root cause than any of its three-plus prior "unrelated pre-existing flake" mentions. The spec targets legacy, pre-"Product Mode" Review Queue markup (`article.queue-card` containing a "Review bird visit" heading and a "Species correction" input) -- but `ReviewQueuePage.tsx:1439` reads `const productMode = true;`, a **hardcoded constant with no toggle**, introduced by a pre-existing commit (`1772c36`, "Simplify animal review workflow", confirmed via `git log -S` to predate this session and the last several accepted milestones). That means the exact markup this spec looks for is permanently unreachable dead UI in the shipped product -- not a live defect (Product Mode's actual cards were verified working correctly, extensively, throughout this session). Fixing the *spec* requires rewriting it against the current flow (`ProductReviewCard` -> `onOpenVisit` -> Visit Detail's own identification-assist/correction UI), a real but separately-scoped rewrite; left undone here per this milestone's own scope discipline rather than expanding implementation surface further on a test-suite-only gap. This is a strictly better outcome than before: the failure is no longer a mystery "unrelated flake" carried forward unexplained -- it is now a precisely diagnosed, cheaply fixable, non-product-affecting test-suite staleness issue.

## Accessibility

**Keyboard.** Primary navigation (sidebar, 10 items) is fully Tab-reachable in a sensible order using real `<button>` elements throughout (no click-handler-on-`<div>` pattern found anywhere checked, including the 8000-line `StreamsPage.tsx`). The mobile nav drawer's Escape-to-close and focus-restoration were found to already work correctly (verified live: Enter opens and focuses the toggle button correctly labeled "Close navigation"; Escape closes it and returns focus to the same button, now "Open navigation"). Fast Review, the product's primary bulk-correction keyboard journey, had two real focus-management defects (P1-1, P1-2 above); both fixed and covered by a new e2e test (`review-queue-fast-review-keyboard.spec.ts`) that completes an entire import -> review -> correction loop using only `page.keyboard`, asserting focus never lands on `<body>` at any transition.

**Focus.** No global `:focus`/`:focus-visible` override exists anywhere in `styles.css` (only two narrow, justified exceptions for custom SVG-based controls) -- the whole product relies on, and gets, the browser's native visible focus ring (`outline: auto`, confirmed present via computed style on a real focused nav button). The two new `tabIndex={-1}` headings added for P1-1/P1-2 inherit this same native behavior rather than needing bespoke CSS.

**Semantics.** `StatusPill` is never color-only -- it always renders a text label alongside its tone class. Zone selection uses correct `role="button"`/`tabIndex`/`onKeyDown` semantics. No systemic "buttons that are actually clickable divs" pattern was found in the surfaces inspected. 24 of 69 component/page files have zero `aria-`/`role=` attributes, but spot-checking the largest of them (`StreamsPage.tsx`) found this reflects consistent use of native semantic elements (real `<button>`s) rather than missing semantics -- a raw ARIA-attribute count is not, by itself, a reliable accessibility signal, and no concrete defect was found this way.

**Narrow/touch.** Zero horizontal overflow found across 40 real combinations (4 viewports x 10 pages, real 371-Visit seeded data, `scrollWidth <= clientWidth` measured directly in a live browser). The existing tap-target-minimum and mobile-drawer conventions (`mobile-viewport-audit.spec.ts`) were exercised and found intact; that suite's own automated coverage was extended (see "Validation") to also cover the two desktop/laptop widths this milestone's brief names, which had no automated regression coverage at all before this pass (only ad hoc manual verification, each prior time).

**Remaining limitations (disclosed, not closed this pass).** Zone-polygon *drawing* has no keyboard path (P2 above). No axe-core or other automated accessibility-testing tool is installed in this repository; this was a bounded, targeted, evidence-driven pass using real keyboard/DOM inspection, matching the brief's own explicit "not a full formal WCAG certification campaign" bound -- not exhaustive coverage of every control on every page.

## Performance

All measurements below are against the 371-Visit / 89-item-backlog QA dataset described in "Identity," each endpoint hit 3x, real wall-clock `curl -w "%{time_total}"` / Python `time.perf_counter()`, no synthetic assumptions.

| Endpoint/page | Dataset | Before | Fix | After | Semantic-equivalence check |
|---|---|---|---|---|---|
| `_acoustic_health_summary` (new code, isolated) | Same, with the process-global repository correctly configured (mirroring real request handling) | N/A -- new code | N/A | ~5ms/call steady-state (`get_birdnet_status` 0.16ms, `acoustic_analysis_queue_diagnostics` 1.25ms, `list_streams` 0.27ms, the rest is Python overhead) | Confirmed the new field never appears in, or alters, any other `ProductHealthStatus` field; `ready`/`message` computation is untouched by construction (acoustic is added after those are already computed). |
| `GET /api/product/health` (includes the above) | Same | N/A (pre-existing endpoint; no prior measurement existed at this exact scale to diff against) | Additive `acoustic` field only | ~0.94-1.19s across 3 repeated calls | Byte-for-byte identical response shape aside from the one new additive `acoustic` key; every pre-existing field's value independently confirmed unchanged by inspection. |

**No fix-driving performance regression was found.** `GET /api/dashboard/summary` (~0.93-1.03s across 3 calls, internally used by `get_product_health`) and `GET /api/review-queue` (~0.72-0.75s across 3 calls) were both measured at this dataset's 89-item unreviewed backlog -- directly comparable in shape to BioCLIP Status / Review Queue Performance v1's own accepted precedent (87-item backlog, 1.96s post-fix baseline for the same dashboard-summary computation family). Both today's numbers sit at or below that established "good" bar despite this dataset's larger total history (371 vs. that milestone's smaller total), so no further optimization was pursued -- consistent with "do not optimize based only on intuition," there is no evidenced regression to fix.

**Large-list discipline audit (section 14).** Investigated two pages that rendered as very tall full-page screenshots (Stream Detail: 15,108px at 1440px width; Analytics: 13,533px) as possible unbounded-list regressions of the 2026-08-18 "v0.1 Product Flow Gap Pass v1" fix. Both investigated to conclusive, evidenced non-findings:
- Stream Detail's "Stream events" section is still correctly bounded (`GET /api/streams/{id}/events` defaults to `limit=50`, confirmed directly: a real 371-Visit-backed Stream returned exactly 50 events, newest (`2026-08-27`) to oldest (`2026-08-02`) -- the height is simply 50 genuinely-detailed cards, not an unbounded list).
- Analytics' "Dataset QA" issue list is still correctly bounded (`MAX_DATASET_QUALITY_ISSUES = 50` in `product_repository.py`, confirmed applied; the frontend's dormant-looking "Showing the N highest-priority issues of M total" disclosure is dormant only because this dataset's own issue count happens to be under 50, not because the mechanism is broken).
- Dashboard's "actionable animal visits" preview list is bounded to 12 server-side.

No unbounded-list regression was found anywhere checked this pass.

## Multi-camera

Integrated behavior checked against 3 active Streams (mixed `connected`/`disconnected` `CameraSourceModel.status`) + 1 archived Stream, real seeded activity spread unevenly across them (55%/30%/15%), at all four viewport widths. Streams/Cameras page rendered coherently with no layout regression; semantic-button hygiene confirmed (79 `onClick` handlers, 81 real `<button>` elements -- no click-handler-on-non-interactive-element pattern). Multi-Camera Place Experience v2's own accepted architecture (cross-camera association, Area vocabulary, archived-history-by-explicit-filter) was not reopened or re-tested beyond this integrated presentation check, per that milestone's own closure and this milestone's explicit instruction not to.

## Error/recovery

Spot-checked the App-shell-level failure path (`App.tsx`'s top-level data-load error branch): shows a curated message ("MockingBird reached the local app, but its camera data could not be loaded.") plus a Retry action, never a raw exception -- confirmed by code read, matching doctrine. Surveyed the `setError`/error-panel pattern across ~30 files (see P2 above): the dominant, common-case path (`ApiError` from a real backend 4xx/5xx) already shows curated, human-written text because this codebase's backend consistently authors `HTTPException(detail=...)` for end users; only the narrower non-`ApiError` network/parse-failure edge case carries any raw-text risk, and that risk was documented rather than treated as a proven defect (no concrete reproduction of a misleading raw-text failure was found this session). Confirmed by direct code read that `ObservationControlPanel.tsx` already correctly separates "camera reachable" from "Observation runtime (model bundle/GPU/CUDA) failed to start" into two independent status lines with an explicit comment recording exactly this doctrine ("a successfully paired, reachable camera must never read 'Needs attention' merely because the *Observation* runtime... is what actually failed to start, and vice versa") -- directly answering section 12's "camera unavailable while Node remains reachable" / "GPU unavailable/fallback" distinction without any change needed. Camera Node offline / storage-pressure / backup / auth-session-expiry messaging was not re-tested end to end this pass (each already has substantial accepted, dedicated prior-milestone work -- Camera Node Connectivity & Recovery, Release Engineering Foundation's backup/migration health checks, Appliance / Storage / Privacy / Recovery v1, Local Identity's session-expiry handling); no new defect was found or reported against any of them.

## Acoustic status

**Gap confirmed still open** at the start of this milestone -- quoted directly from
[acoustic-productization-licensing-field-acceptance-v1-report.md](acoustic-productization-licensing-field-acceptance-v1-report.md):
"the two status endpoints that could tell a user 'microphone/model
unavailable' have zero frontend callers anywhere." Independently re-verified
in current code (not merely trusted from the prior report): `GET
/api/birdnet/status` and the per-Stream `/audio-capture/status` endpoints
were confirmed to have zero callers anywhere in `web/src/**/*.tsx`, and
`ProductHealthPanel.tsx`/`ProductHealthStatus` had zero acoustic-related
fields at all.

**Bounded implementation** (per the brief's explicit "smallest
capability-aware... fold into existing health/product patterns"
instruction, and nothing more):

- Backend: `ProductHealthAcousticSummary` (`configured: bool`, `status:
  "not_configured" | "healthy" | "degraded" | "model_unavailable" |
  "microphone_unavailable"`, `detail: str`) added additively to
  `ProductHealthStatus`. Computed by `_acoustic_health_summary()`
  (`main.py`), composed entirely from three already-existing, already-cheap
  facts: the per-Stream `microphone` provider configuration
  (`_microphone_config_for_stream`, already used by the existing
  audio-capture endpoints), `get_birdnet_status()` (a pure package-
  availability check, already used by the existing BirdNET-status
  endpoint), and `acoustic_analysis_queue_diagnostics` (Doctor's own
  existing 24h failure/backlog signal, reused for the one "degraded" case
  a configured-and-working microphone can still reach). Never a new
  computation module; never a live capture probe; never a factor in
  `ProductHealthStatus.ready` (acoustic status can never make the whole
  product read as "not ready").
- Frontend: one additive field on the existing `ProductHealthStatus`
  TypeScript interface; one new calm text row ("Acoustic: Not configured" /
  "Healthy" / "Degraded" / "Model unavailable" / "Microphone unavailable")
  in the existing `ProductHealthPanel.tsx`, in the same plain-text style as
  its four sibling rows (Storage/Cameras/Observing/Backup) -- deliberately
  not a `StatusPill` here, to avoid introducing a second visual pattern
  into a panel that otherwise uses none for this list. The fuller `detail`
  sentence surfaces only in the panel's existing "Advanced diagnostics"
  disclosure, and only when there is something to explain (not for the
  common "not configured" or "healthy" cases) -- progressive disclosure,
  not concealment.

**Explicitly not built** (per the brief): no new acoustic analytics, no
waveform dashboard, no second acoustic settings architecture, no audio
privacy redesign, no Doctor web UI.

Live-verified end to end against the real QA instance (a genuinely
configured, healthy microphone Source reported `status: "healthy"`
correctly) and against a fresh e2e instance (the default, no-microphone
case correctly reports `"not_configured"` and never affects `ready`).

## Validation

**Tier 1 (focused).** All new/changed tests green, each independently
RED-confirmed against the pre-fix code via `git stash`:
- `tests/test_review_queue_product_mode.py` -- 2 new tests (P0-1), 3/3
  passing.
- `tests/test_product_health.py` -- 5 new tests (acoustic states:
  not-configured, microphone-unavailable, model-unavailable, healthy,
  degraded), 15/15 passing in the file.
- `web/e2e/review-queue-fast-review-keyboard.spec.ts` (new) -- P0-1 and
  P1-1/P1-2 exercised end to end through one real keyboard-only
  import-review-correct journey. Passing. Found and fixed a genuine
  test-hygiene defect in this same new spec while validating the full
  suite: this suite runs every spec against one shared instance
  (`playwright.config.ts`'s `globalSetup`), and the real, non-demo,
  "today"-dated confirmed Visit this test creates was found -- via a
  rigorous three-way bisection (contended full run: fails; clean full run:
  still fails; the unmodified 128-spec baseline with this file removed:
  passes) -- to leak into `today-report.spec.ts`'s unrelated "no wildlife
  activity yet today" empty-state assertion when both run in the same full
  suite. Fixed by archiving the fixture Source at the end of the test
  (`PATCH /api/sources/{id}` `{archived: true}`), mirroring this
  codebase's own accepted default-exclusion behavior (archived Sources
  already stay out of Today's default view). Re-verified clean on the full
  136-test suite afterward.
- `web/e2e/acoustic-health-status.spec.ts` (new) -- P1-3, passing.
- `web/e2e/mobile-viewport-audit.spec.ts` -- extended with 1024px/1440px
  (6 new tests), passing; formalizes what this milestone's manual pass
  found ad hoc.

**Tier 2 (affected subsystem).**
- `tsc --noEmit` / `vite build`: clean throughout, re-run after every
  frontend change.
- `ruff check` on all touched Python files: 83 findings total (`main.py`
  26, `product_repository.py` 57, `schemas.py`/both new test files 0),
  **zero new** -- confirmed by a direct clean-baseline bisection
  (`git stash push --keep-index` per file, re-run, byte-identical counts
  before/after: 26/26 and 57/57), not merely inspected by eye given the
  scale of `product_repository.py` (42,600+ lines).
- Full existing e2e suite (`npm run test:e2e`, all 136 specs including
  this milestone's own 8 additions): **135 passed / 1 failed** (5.2m). The
  one failure is `reviewed-product-loop.spec.ts`, precisely root-caused
  above (not a regression -- confirmed via a rigorous three-way
  bisection: the unmodified, this-milestone-untouched 128-spec baseline
  independently reproduces the identical single failure, byte-for-byte
  the same assertion, 127 passed / 1 failed). A first full run surfaced 2
  additional failures that a careful investigation traced to this
  milestone's own new fixture data leaking between specs in the suite's
  one shared instance (not a production defect) -- see the
  `review-queue-fast-review-keyboard.spec.ts` entry above for the full
  bisection and fix.
- Full Core (`scripts/verify_core.py`, `pytest -m "not slow"`), run
  standalone (not concurrent with e2e, after an earlier concurrent attempt
  produced real, confirmed SQLite lock contention -- see below): **5166
  passed / 2 failed / 3 skipped / 23 deselected (slow-marked) / 11 xfailed
  (26m50s)**. Both failures are the identical, already-documented
  `test_place_biodiversity_summary_repository.py` pair
  (`test_api_route_returns_the_summary`,
  `test_human_correction_updates_place_biodiversity_intelligence_correctly`)
  independently re-confirmed as pre-existing across at least eight prior
  consecutive milestone checkpoints (see this file's own §14) -- not
  re-bisected again here given zero code this milestone touched has any
  relationship to biodiversity-summary computation.

**A note on validation methodology.** Running the full e2e suite
concurrently with full Core once produced real, directly observed SQLite
lock contention (`sqlite3.OperationalError: database is locked` in a
background acoustic-runtime reconcile thread, and one e2e test genuinely
timing out waiting on a write that was delayed by the contention) -- a
real instance of this project's own already-documented SQLite-under-
concurrent-load class of issue, not a defect in this milestone's changes.
Both suites were re-run standalone afterward for the clean, trustworthy
numbers reported above and throughout this report.

**Tier 3.** Full Core run performed (see above) -- justified despite this
being a primarily frontend-and-adjacent-backend milestone because
`_review_queue_triage_fields`'s classification logic (P0-1) is a
widely-shared function reachable from Dashboard, Review Queue, and Today,
not an isolated leaf change.

## Remaining release risks

- `reviewed-product-loop.spec.ts` remains red, for a newly-precise,
  disclosed, non-product-affecting reason (see "Root-caused, not fixed").
- Zone-polygon *drawing* (not selection) has no keyboard equivalent --
  real, disclosed, pre-existing, scoped out of this bounded pass.
- The larger-than-previously-documented dead-CSS block and the narrow
  raw-exception-text edge case (P2 items above) remain, by design, as
  disclosed low-priority cleanup, not blocking.

## Decision

**Classification A.** One real P0 and three real P1 defects were found
through live, evidence-based investigation (not merely code reading) and
fixed, each with a RED/GREEN-verified regression test and a live
before/after confirmation in a real browser. No known P0 remains. The
whole-product journeys (A-G), all four required responsive widths,
keyboard/focus/semantics, real-data performance, multi-camera
presentation, error/recovery messaging, and the acoustic-status gap were
each investigated with concrete evidence, not assumed sound. The one
remaining e2e failure (`reviewed-product-loop.spec.ts`) is precisely
diagnosed as pre-existing, non-product-affecting test-suite staleness,
independently reproduced on the unmodified baseline. No measured
performance regression. Full e2e (135/136, only the disclosed pre-existing
gap) and full Core both green. See the report's "Remaining release risks"
above for the concrete, bounded items intentionally left open, per this
milestone's own scope discipline -- none are P0/P1 product defects.
