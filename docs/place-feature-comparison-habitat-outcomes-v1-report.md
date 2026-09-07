# Place Feature Comparison & Habitat Outcomes v1 — Report

Classification: **A**. See "Decision" at the end.

## Authorization and starting state

This milestone's own governing brief is an explicit, deliberately-authorized,
bounded product-development reopening picking up a specific, previously-named
backlog item ("a ranked Feature-comparison view") during the current
`FEATURE FREEZE` phase — the identical mechanism already used for
Environmental Context × Place Story composition, Year-over-Year Seasonality,
Multi-Camera Feature Linking, and Place Story Deep Dives, each of which was
also a bounded reopening of a non-release-blocking opportunity during the
same freeze.

Transparency note, verified directly against the repository rather than
assumed: the same-day Global Remaining Product-Development & Release-Queue
Reconciliation v1 classified "Ranked Feature comparison view" as `D --
enrichment` in its own five-question Product Opportunity Review
(`docs/global-remaining-product-development-release-queue-reconciliation-v1-report.md`
line 257) — not release-blocking, not automatically the next milestone "by
adjacency." `docs/roadmap.md` and `docs/release-execution-state.md` both
list it as an explicit non-goal across at least five prior accepted
milestone reports, each paired with "do NOT automatically authorize... by
adjacency." That is exactly the situation this milestone's own explicit,
separate governing brief resolves: a deliberate decision to build a
previously-deferred, well-scoped, non-release-blocking opportunity now, not
a self-authorized continuation. It does not reopen Lane R, Lane P, BirdNET
legal posture, or External Pre-Release Acceptance, and returns to feature
freeze on completion (see "Scheduler / roadmap update," below).

Baseline verified before any change:

- branch `main`, HEAD `594d65b` (the *report* commit for Place Story Deep
  Dives & Representative Evidence v1 — `release-execution-state.md`'s own
  "Accepted HEAD: `33d9f5f`" self-citation names the *implementation*
  commit immediately before it; a normal one-commit offset, not a
  discrepancy);
- schema v59, unchanged by this milestone;
- worktree clean except the seven preserved untracked detector files
  (confirmed present, untouched, unmodified throughout);
- no active writer (no running product processes; no uncommitted tracked
  changes; no lock files beyond the pre-existing venv/scheduler locks);
- Lane P `CLOSED`; Lane R `OPEN — RELEASE-CRITICAL — TRUE LATENCY TAIL
  EVIDENCE REMAINS` (both untouched by this milestone);
- current authorization prior to this milestone: `NONE — GLOBAL
  PRODUCT-ROADMAP RECONCILIATION REQUIRED`.

## Contract and architecture reused

Full contract:
[place-feature-comparison-habitat-outcomes-v1-contract.md](place-feature-comparison-habitat-outcomes-v1-contract.md).
Investigated directly (governing docs, five prior milestone reports/
contracts, the actual backend/frontend code) before writing any code —
see that document for the full nine-question analysis.

**Zero new analytics/statistics modules.** The entire deliverable is one
new, thin repository-layer composition method,
`ProductRepository.get_place_feature_comparison_overview`, plus one pure,
behavior-preserving extraction, `_feature_change_event_with_comparison`
(the identical per-event comparison/environmental-composition logic
`get_place_feature_detail`'s own loop body already contained, pulled into
a shared helper both methods now call — proven behavior-preserving by
every one of `test_place_feature.py`'s 97 pre-existing tests passing
unchanged). Every comparable figure is reused, unmodified, from an
already-accepted primitive:

- `feature_change_comparison.compute_feature_change_comparison` (the
  7/14/30-day window escalation and four-state maturity vocabulary);
- `feature_yield.compute_feature_yield` (the coverage-normalized
  activity rate, `MIN_MONITORED_HOURS_FOR_RATE` sufficiency floor);
- `environmental_period_comparison.compute_environmental_period_comparison`
  (weather-band composition over the identical wildlife windows);
- `_associated_visit_ids_to_exclude_from_counting` (cross-camera dedup);
- `_place_activity_coverage_summary` (elapsed-time coverage union);
- `representative_evidence.select_representative_evidence` (via
  `_feature_representative_evidence`, all-time, bounded, cross-camera).

Two new Pydantic response types (`PlaceFeatureComparisonRow`,
`PlaceFeatureComparisonOverview`) compose these existing types
(`PlaceFeature`, `PlaceFeatureYieldSummary`,
`PlaceFeatureChangeEventWithComparison`, `RepresentativeEvidence`)
unmodified — no new field carries independently-computed truth.

## Comparison dimensions delivered

**Deliverable A — Comparable Feature Overview** (`features`, one row per
Feature): feature identity/type, observation scope (linked cameras/Zones,
with archived-camera labeling), a coverage-normalized recent-activity rate
gated on `data_sufficient`, the single most-recent Reviewed change with
its own before/after maturity+direction, environmental context when that
comparison reached a real window, and a bounded representative evidence
thumbnail.

**Deliverable B — Habitat Change Outcomes** (`change_outcomes`, one entry
per Reviewed change event that had an observation link at request time —
i.e. a comparison was at least attempted): what changed, when, the
wildlife-activity association (direction + maturity + `window_days`, never
a bare number), environmental context over the identical windows, and a
link back to the owning Feature's Story.

Two dimensions are always shown together, never collapsed: `maturity`
(how much trustworthy comparison exists) and `status` (the direction, if
any) — reused from `PlaceFeatureAssociation` unchanged. `window_days` is
always surfaced so two events landing on different escalated windows are
never silently treated as directly comparable magnitudes.

## Materiality / abstention

Every non-comparable state is shown, never hidden: `too_soon`,
`insufficient_coverage`, "no camera/Zone linked" (comparison entirely
`None`, distinct from an attempted-but-immature comparison), and
`data_sufficient: false` yield. A new label/tone/detail badge helper,
`maturityInfo()` (mirroring `baselineMaturityInfo`/`periodMaturityInfo`'s
established pattern), is the first place in this product that visually
distinguishes `early_signal` from `comparable` — the underlying
`featureAssociationSentence` prose renders identical wording for both,
a separately-disclosed, pre-existing gap this milestone does not touch;
the new badge is an additive improvement layered beside it, not a fix to
that sentence. Tone conveys evidence quality only (`good` = enough
evidence to say something; never `good`/`alert` for the *direction* of a
wildlife change) — the fairness requirement against red/green wildlife
value judgments is satisfied structurally, not by convention alone.

## Coverage / deduplication

Reused, unmodified, proven directly against the new Place-wide overview
(not merely re-asserted from the single-Feature primitives):
`test_overview_yield_dedupes_confirmed_cross_camera_pair` (one real
encounter across two linked cameras counts once) and
`test_overview_coverage_is_union_not_sum` (fully-overlapping camera
coverage reports the union, not the sum). The product-shaped scenario
below exercises both simultaneously inside one realistic multi-Feature
overview response, not in isolation.

## Correction / archival safety

`get_place_feature_comparison_overview` computes everything fresh from
current rows on every call, exactly like `get_place_feature_detail` — no
cache, no persisted derived state, no invalidation step. Proven directly:
correcting a change event's date collapses a mature comparison back to
`too_soon` on the very next call
(`test_overview_reflects_change_event_date_correction_on_next_read`);
removing a change event drops it from `latest_change`
(`test_overview_reflects_change_event_removal_on_next_read`); correcting a
species label changes yield/dedup/representative-evidence on the very next
call (`test_overview_reflects_species_correction_on_next_read`); archiving
a Feature's only linked camera leaves its history fully reachable, labeled
`(archived)`, never dropped
(`test_overview_archived_camera_feature_still_shows_comparison`). All four
are also exercised together, end to end, in the product-shaped scenario.

## Environmental and evidence composition

Environmental context is composed exactly once per change event, over the
identical before/after windows the wildlife comparison already
established, reusing `comparison_window_dates` — never a second window
computation. Every producible sentence was audited against the existing
forbidden-causal-word list (`caused`, `led to`, `resulted in`, `because
of`, `drove`, `due to`, `improved`, `population`) in both the unit tests
and the product-shaped scenario; none appear. Representative evidence
reuses the canonical Gate C selector unmodified; a missing/expired media
file produces an honest `None`
(`test_overview_representative_evidence_none_when_media_file_missing`),
never a broken thumbnail, and the underlying before/after outcome is
completely unaffected by the missing image (proven in the scenario's own
Act 7).

## UI

One new page, `FeatureComparisonPage.tsx`, at route `/place-report/compare`
— a static path (no id parameter, since it compares the whole Place),
registered in `pagePaths` alongside `place-activity-report`/`place-story`,
**not** added to `productNavItems`/`advancedNavItems` (no new top-level nav
destination, matching Feature/Taxon Story's own precedent). Reachable via
one new "Compare Features" link inside the existing "Features & changes"
panel on the Place Report page.

Two sections, "Compare Features" and "Habitat Change Outcomes," each a
calm, card-per-row list (never an HTML `<table>`, so it stacks cleanly on
narrow viewports) with a filter (Feature type) and a sort control reusing
`ZoneInsightsPanel`'s own `.zone-insights-sort` idiom — every sort option
label states a fact ("Visits per monitored hour," "Most recently changed")
never a quality judgment ("Most active," "Best feature"). A Feature with
insufficient data sorts into an honest, visible state rather than
disappearing or defaulting to zero. Representative evidence reuses
`RepresentativeThumbnail` unmodified, sized down via a new, narrowly-scoped
CSS wrapper (`.feature-comparison-thumb`) rather than a new thumbnail
component.

## Local Only

No new external call anywhere in this milestone's own code — every field
is a pure composition of already-persisted rows. Proven directly, not
assumed: `test_overview_never_calls_the_network` (an always-fails weather
requester's `call_count` stays `0` through a full comparable-with-a-real-
temperature-delta read) and the product-shaped scenario (patches
`socket.socket.connect` to raise for its entire run, including every Act).

## Performance

The regression named explicitly in the governing brief — calling the
equivalent of `get_place_feature_detail` independently once per Feature —
was measured, not assumed, against the alternative this milestone
actually ships:

| Scenario | Batched overview | N independent `get_place_feature_detail` calls | Savings |
|---|---|---|---|
| 5 Features, 1 change event each, 7 confirmed Visits each | 541 queries | 685 queries | 21.0% fewer |
| 8 Features, 2 change events each (16 total), 7 confirmed Visits each | 886 queries | 1,128 queries | 21.5% fewer |
| 8-Feature scenario, wall-clock (median of 5, warm cache) | 278 ms | 345 ms | ~19% faster |

The batching removes: the per-Feature observation-link/Source/Zone
re-fetch (three queries per Feature otherwise, now three queries total);
the per-Feature taxonomy-index re-fetch; and, for Deliverable A
specifically, computing every one of a Feature's change events instead of
only its latest one. The remaining query cost is inherent, per-Visit
`StreamVisitSummary` construction (review-label, evidence, and
species-suggestion lookups per Visit) — the same cost `get_place_feature_
detail` itself already pays per Feature, unrelated to this milestone's own
batching and out of its reuse-only scope; batching that construction
across many Visits at once would be a real, larger, separately-scoped
optimization, named here as a future opportunity, not attempted.

`test_comparison_overview_query_count_beats_independent_per_feature_detail_calls`
keeps the 5-Feature comparison as a standing regression test (asserts
strictly fewer queries, not a specific count, so it does not become
brittle against unrelated future query-shape changes elsewhere in the
codebase).

No pagination was added to either list: Features and their manually-
recorded change events are both realistically small-N per Place (a person
must deliberately record each one, unlike Visits) — the measurement above,
at a realistic 8-Feature/16-event scale, found no case for one.

## Product-shaped proof

`tests/test_place_feature_comparison_product_shaped_scenario.py`: a Back
Yard Place with three Features (Sunflower Feeder — Patio Camera only;
Bird Bath — linked to *both* Patio and Garden cameras; Wildflower Patch —
Garden Camera only, added two days before `now`), two cameras with
genuinely different monitoring effort (Patio fully covers the whole
window; Garden covers only the last 4 of the trailing 7 days), a confirmed
cross-camera duplicate encounter at Bird Bath (counts once), a genuinely
independent simultaneous pair at Bird Bath (counts twice), three Reviewed
"added" change events (two mature — one `more_common_under_condition` for
the Feeder, one for Bird Bath — one honestly `too_soon` for the Patch),
persisted environmental context around Bird Bath's own change (a real
temperature delta, non-causal wording verified), one corrected species
label (chickadee → blue jay, propagating on the very next read with no
invalidation step), one archived camera (Garden, after the historical
window closes — both its linked Features stay fully reachable), and one
expired media file (the Feeder's own representative-evidence asset,
deleted mid-scenario — an honest `None`, the before/after outcome
unaffected). One comprehensive, passing test, mirroring this codebase's
own established capstone-scenario convention.

## Validation

- **Tier 1 (focused, during implementation):** every new/changed file run
  repeatedly while writing it; see file-by-file counts below.
- **Fast gate** (`scripts/verify_fast.py`): **1,801 passed, 0 failed**
  (180.11s) — confirms this change introduced no regression in the
  curated pure-contract suite.
- **Backend, Feature/Place/Story/evidence subsystem (Tier 2):**
  `test_place_feature.py` (97, unchanged, all pass — proves the
  `_feature_change_event_with_comparison` extraction is behavior-
  preserving), `test_place_feature_comparison.py` (24 new),
  `test_place_feature_comparison_product_shaped_scenario.py` (1 new),
  `test_multi_camera_place_feature_linking_scenario.py` (1),
  `test_place_story_deep_dives_product_shaped_scenario.py` (1),
  `test_conditional_association.py` (14), `test_environmental_period_
  comparison.py` (24), `test_representative_evidence.py` (10) — **172
  passed, 0 failed** together (counts independently verified via
  `pytest --collect-only`).
- **Backend lint:** `ruff check` on every touched/new backend file. Zero
  new findings in the three touched files (`schemas.py`: 0 before and
  after; `main.py`/`product_repository.py`: findings present both before
  and after are byte-identical in rule/message, differing only by the
  constant line-number shift my own insertions cause — proven by a
  message-level diff against each file's exact pre-change content via
  `git show HEAD:<path>`, not merely a matching count). The two new test
  files were cleaned to zero findings (one unused import, two unused
  local variables, fixed).
- **Frontend:** `tsc --noEmit` clean; `vite build` clean, the new page
  code-splits into its own chunk (`page-FeatureComparisonPage-*.js`,
  11.18 kB / 3.37 kB gzip).
- **e2e:** 14 new tests in `feature-comparison.spec.ts`, plus the full
  directly-adjacent matrix re-run (`place-features`, `feature-story`,
  `taxon-story`, `place-story`, `place-activity-report`, `year-over-year`,
  `mobile-viewport-audit`) — **84 passed, 0 failed**, zero regressions.
- **Runtime/startup:** `python -m mockingbird --check` after the
  production build — passed, integrity confirmed. Incidentally migrated
  this sandbox's own local dev database from schema 57 to 59 (it had not
  been opened in a while); an automatic pre-migration safety backup was
  taken and integrity was confirmed afterward — this is the tool's normal,
  designed behavior, not a side effect of this milestone's own code.
- **Tier 3 (Core gate, `scripts/verify_core.py`):** run given this
  change crosses the analytics/repository/API/frontend boundary and
  refactors a shared method an existing endpoint depends on — **5,897
  passed / 4 failed / 3 skipped / 23 deselected / 11 xfailed** (45m18s).
  All 4 failures independently confirmed pre-existing and unrelated, not
  merely assumed: `test_place_biodiversity_summary_repository.py::test_
  api_route_returns_the_summary` and `::test_human_correction_updates_
  place_biodiversity_intelligence_correctly`, plus `test_place_change_
  summary_repository.py::test_api_round_trip_exposes_change_detection_
  fields`, all reproduce byte-identically (same `AssertionError:
  'insufficient_recent_coverage' == 'higher_recent_presence'` for the
  third one) against the exact pre-change baseline via `git stash push
  -u` isolation — the identical, already-documented flake this file's
  own §14 and a prior milestone's checkpoint both name. `test_camera_
  node_capture_contention.py::test_analysis_stream_disconnect_during_
  inflight_capture_releases_camera_lock` (unrelated Camera Node
  capture-contention code, never touched by this milestone) passes
  cleanly in isolation — a timing-sensitive flake under full-suite
  concurrent load, not a deterministic failure.

## Concrete defects found/fixed

None. This milestone is purely additive/compositional: one new repository
method, one pure (behavior-preserving, test-proven) extraction, two new
response schemas, one new route, one new frontend page, and one new nav
link. No pre-existing defect was found in the reused primitives during
this milestone's own investigation or testing.

## Deferred opportunities (explicitly not built)

- Batching `StreamVisitSummary` construction across many Visits at once
  (the remaining, larger share of the measured query/time cost) — a real,
  separately-scoped optimization with no confirmed real-scale need yet
  (see "Performance," above).
- Fixing `featureAssociationSentence`'s own pre-existing `early_signal`/
  `comparable` wording gap — disclosed by a prior milestone, out of this
  one's bounded scope; this milestone's new badge distinguishes the two
  states additively instead.
- Wiring a comparison entry point into `PlaceFeaturesCard` (Dashboard) —
  one clear entry point (the Place Report page) was judged sufficient;
  a second one is a small, easy follow-on if real usage ever asks for it.
- Every item explicitly named as a non-goal in the governing brief
  (causal attribution, a universal habitat score, broad multi-site
  comparison, new weather providers/backfill, Place Story period
  summaries, Feature-specific year-over-year, automatic Feature identity
  inference, new camera/Zone topology, a Story source-attribution
  rewrite, notifications, provider integrations, a new media pipeline,
  release hardening/Gate A field work) — none attempted, none promoted.

## Decision

**A.** Both named core deliverables (Comparable Feature Overview, Habitat
Change Outcomes) are delivered, fully reusing accepted primitives with
zero new statistical engine; fairness, correction/archival safety,
non-causal composition, and Local Only are each proven directly against
the new surface, not merely inherited by assumption; a real, measured
performance improvement is recorded against the exact regression the
brief named; a comprehensive, realistic product-shaped scenario passes
end to end; validation is green across Fast, the full directly-affected
subsystem, frontend typecheck/build, e2e, and the Core gate. No material
gap is disclosed beyond the two named, genuinely out-of-scope future
opportunities above.

## Scheduler / roadmap update

Per this milestone's own governing brief, the following delta-only
updates are applied to `docs/release-execution-state.md` and
`docs/roadmap.md`:

- accepted HEAD/schema (schema unchanged at v59);
- latest accepted milestone: Place Feature Comparison & Habitat Outcomes
  v1, classification A;
- the "Biodiversity & Place Intelligence" lane's own "substantial
  product-roadmap opportunity still remains" note: "a ranked
  feature-comparison view" is removed from that list (closed by this
  milestone); the rest of that list (Place Story period summaries, a
  year/month picker over the year-over-year card, week-level/named-
  seasonal-period comparison, deeper environmental historical backfill)
  is preserved unchanged;
- Lane F's own "remaining, not closed" list: unaffected (this milestone
  did not touch multi-camera linking itself, only reused it);
- current authorized milestone returns to `NONE — GLOBAL
  PRODUCT-ROADMAP RECONCILIATION REQUIRED`;
- Lane P, Lane R, BirdNET legal posture, and External Pre-Release
  Acceptance are explicitly unchanged by this milestone.
