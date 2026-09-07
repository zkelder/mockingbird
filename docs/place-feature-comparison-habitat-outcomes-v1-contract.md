# Place Feature Comparison & Habitat Outcomes v1 — Contract

## Authorization note (read first)

`docs/release-execution-state.md`'s `CURRENT PHASE: FEATURE FREEZE` header
(corrected 2026-09-06 by Global Remaining Product-Development &
Release-Queue Reconciliation v1) states plainly that the reconciliation
itself "does **not** authorize ... any product-development milestone," and
that same reconciliation's own five-question Product Opportunity Review
classified "Ranked Feature comparison view" as `D -- enrichment`
(`docs/global-remaining-product-development-release-queue-reconciliation-v1-report.md`
line 257) — not release-blocking, not automatically the next milestone by
adjacency. `docs/roadmap.md` and `docs/release-execution-state.md` both
list "a ranked Feature-comparison view" as an explicit non-goal repeated
across at least five prior accepted milestone reports, each time paired
with "do NOT automatically authorize ... by adjacency."

That is exactly the mechanism this milestone uses: a *separate, explicit*
authorization (this milestone's own governing brief) picking up a
previously-deferred, non-release-blocking, well-scoped backlog item —
the identical pattern already used for Environmental Context × Place
Story composition, Year-over-Year Seasonality, Multi-Camera Feature
Linking, and Place Story Deep Dives, each of which was *also* a
deliberately-authorized, one-time, bounded reopening of a Classification
C/D-shaped opportunity during the same feature freeze. It does not
reopen Lane R, Lane P, BirdNET legal posture, or External Pre-Release
Acceptance, and it returns to feature freeze on completion. This is
recorded here for transparency, not as a blocker; see the closure
report's "Starting state" section for the equivalent disclosure at
completion.

Baseline verified before any change: branch `main`, HEAD `594d65b`
(`594d65b` is the *report* commit for Place Story Deep Dives &
Representative Evidence v1; `docs/release-execution-state.md`'s own
"Accepted HEAD: `33d9f5f`" self-citation names the *implementation*
commit immediately before it — not a discrepancy, the normal
one-commit offset between an "implementation" commit and the "report"
commit that updates the scheduler about it), schema v59, worktree clean
except the seven preserved untracked detector files, no active writer,
Lane P `CLOSED`, Lane R `OPEN -- RELEASE-CRITICAL -- TRUE LATENCY TAIL
EVIDENCE REMAINS` (untouched by this milestone), current authorization
`NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED` prior to this
milestone's own authorization arriving.

## 1. What existing Feature-yield / before-after results are genuinely comparable?

**`FeatureYield.visits_per_monitored_hour`** (via `feature_yield.py`,
computed over the fixed `FEATURE_YIELD_WINDOW_DAYS = 7` window every
Feature already uses) is the one number that is fair to compare
*across different Features*, because it is already coverage-normalized
and every Feature's rate is computed over the identical fixed recent
window. It is comparable **only** between rows where both sides have
`data_sufficient = True` (>= `MIN_MONITORED_HOURS_FOR_RATE` = 2.0 hours
of monitored coverage in that window) — exactly the existing
`source_activity`/`zone_insights` sufficiency floor, not a new number.
Raw `confirmed_wildlife_visit_count`/`distinct_taxon_count` are **not**
independently comparable across Features with different monitoring
scope (a 3-camera Feature naturally accumulates more raw Visits than a
1-camera one); they are shown as supporting detail alongside the rate,
never sorted or ranked on their own.

**`FeatureChangeComparison`/`PlaceFeatureAssociation`** (one change
event's before/after outcome) is comparable across different change
events only along two explicit axes shown together, never blended:
`maturity` (how much trustworthy comparison exists at all) and `status`
(the direction, `more_common_under_condition` /
`less_common_under_condition` / `no_clear_association`). The
*magnitude* of a rate difference is not safely comparable between two
events that resolved to different `window_days` (7 vs. 14 vs. 30) —
different events can legitimately land on different window sizes
depending on how much usable coverage existed — so `window_days` is
always shown alongside any comparison, per the fairness requirement
that incompatible periods be labeled, not silently equated.

A Feature can have several change events, each with its own
independent comparison. This milestone never combines multiple events'
comparisons into one verdict for a Feature.

## 2. Which comparisons have different denominators, periods, or scopes?

- Yield's recency window is fixed (7 days) for every Feature, but its
  *denominator* (`monitored_seconds`, from the coverage-union ledger)
  varies enormously by how many camera/Zone views are linked and for
  how long — the rate normalizes for this, but `data_sufficient` must
  always be shown, never silently assumed.
- Before/after `window_days` is chosen independently per change event
  (whichever candidate window first clears
  `conditional_association`'s sample floor) — two events being viewed
  side by side may honestly be comparing 7-day and 30-day periods; both
  are always surfaced.
- A Feature's own overall history length (`installed_date`, when
  recorded) differs Feature to Feature; this is shown as-is (existing
  field, no new "Feature maturity" classification invented) so a
  1-day-old Feature is never visually implied to be as established as a
  6-month one.
- Multi-camera Features have monitoring scope **unioned**, not summed,
  across every linked view (reusing `_place_activity_coverage_summary`
  unmodified) — a Feature watched by two cameras is not double-credited
  for overlapping wall-clock time, but it does have broader raw
  observation breadth than a single-camera Feature; `observation_links`
  is always shown so this is visible, not hidden inside one number.

## 3. Coverage, duplicate, and eligibility semantics reused unmodified

- **Coverage** = elapsed-time union via
  `ProductRepository._place_activity_coverage_summary` /
  `_feature_scoped_monitored_seconds` — never a per-Stream sum. Already
  load-bearing inside `feature_yield`; this milestone calls the exact
  same repository methods, never a second coverage engine.
- **Duplicates** = `_associated_visit_ids_to_exclude_from_counting`,
  applied inside the shared `_feature_scoped_visit_rows` core that both
  yield and before/after already delegate to. Inherited automatically by
  reusing those methods; no new dedup logic anywhere in this milestone.
- **Eligibility** = "confirmed wildlife Visit"
  (`_classify(...) is _Classification.CONFIRMED_WILDLIFE` in
  `feature_yield`; `_is_confirmed_wildlife_summary` for representative
  evidence) — Reviewed-only. Inherited unmodified.

## 4. Zero-, one-, and multi-link Feature behavior

- **Zero links:** `_feature_monitoring_stream_ids` returns `[]`;
  `_feature_yield_summary`/`_compute_feature_change_event_comparison`
  are never even attempted (mirroring `get_place_feature_detail`'s own
  `if stream_ids:` guard). The comparison overview shows such a Feature
  with an honest "not linked to a camera or Zone yet" status — visible,
  sortable into its own "not enough data" state, never hidden and never
  given a fabricated zero rate.
- **One link:** computed normally, scoped to that Stream/Zone.
- **Multi-link:** yield/comparison/representative-evidence are unioned
  and cross-camera-deduplicated exactly as Multi-Camera Place Feature
  Linking v1 already built; `source_id`/`zone_id` stay `NULL`/`NULL`
  (the existing compatibility-mirror rule) and the full
  `observation_links` list is what the comparison overview displays.

## 5. Reusing accepted primitives without a new statistical engine

Confirmed by direct inspection: **zero new analytics/statistics
modules are needed.** This milestone adds exactly one new, thin
repository-layer composition method
(`ProductRepository.get_place_feature_comparison_overview`) that loops
the following four already-accepted primitives across every Feature in
one batched pass, and two new Pydantic response wrappers with no new
computed fields of their own:

- `_place_feature_observation_link_context` (batched link/Source/Zone
  loader — already built for exactly this "many Features at once"
  shape by `list_place_features`/`get_place_features_summary`)
- `_feature_yield_summary` (unmodified)
- `_compute_feature_change_event_comparison` +
  `_feature_environmental_period_comparison` (unmodified)
- `_feature_representative_evidence` (unmodified)

No new `AbstractSet[date]` arithmetic, no new association/statistical
threshold, no new "habitat score" of any kind.

## 6. What existing data can support a useful ranked view now?

Only `visits_per_monitored_hour` (gated on `data_sufficient` for both
sides) is safe to sort by as an "activity rate" — explicitly labeled as
a coverage-normalized rate, never "best" or "healthiest." Additional
safe, factual, non-judgmental sort/filter dimensions, all already
existing fields requiring no new computation:

- `feature_type` (categorical filter)
- most-recent change `effective_date` (recency)
- comparison `maturity` (an "evidence available" ordering — comparable
  → early_signal → insufficient_coverage → too_soon → not linked —
  explicitly labeled as data-availability, not quality)
- `name` (alphabetical; the deterministic tie-break for every other
  sort, matching `ZoneInsightsPanel`'s own
  `|| a.name.localeCompare(b.name)` convention)

No composite score is computed anywhere.

## 7. Smallest user-facing surface that adds real value

One new page, `FeatureComparisonPage.tsx` at route `/place-report/compare`
(a static path added to `pagePaths`, mirroring `place-activity-report`/
`place-story` — **not** added to `productNavItems`/`advancedNavItems`,
so it introduces no new top-level nav destination, exactly like
Feature/Taxon Story before it), reachable via one new "Compare Features"
link inside the existing "Features & changes" panel on
`PlaceActivityReportPage.tsx`. Two sections:

- **Compare Features** (Deliverable A): one row per Feature.
- **Habitat Change Outcomes** (Deliverable B): one row per Reviewed
  change event that has an attempted comparison.

## 8. Performance risk with many Features

The risk named explicitly in the brief — calling the equivalent of
`get_place_feature_detail` independently once per Feature — would
redundantly (a) re-fetch each Feature's own link rows and (b) recompute
a comparison for *every* one of that Feature's change events, not just
the one the overview needs. The new repository method avoids both:
link/Source/Zone context is fetched once for every Feature in scope
(the same three-query batch `list_place_features` already uses); for
Deliverable A's per-Feature row, only the single most-recent change
event's comparison is computed (not the Feature's full history — full
history stays one click away at the Feature Story, which already
exists); for Deliverable B, every change event in scope is fetched in
one `feature_id IN (...)` query and each qualifying event's comparison
is computed once, reusing the pre-fetched per-Feature link/stream-id
context rather than re-resolving it per event (the identical technique
`get_place_feature_detail` already uses inside one Feature, hoisted one
level up across every Feature). Representative evidence per Feature
reuses `_feature_representative_evidence`'s existing bound
(`MAX_REPRESENTATIVE_EVIDENCE_CANDIDATES = 20` candidates scanned,
short-circuited immediately for a zero-link Feature). Measured query
count/timing against a realistic multi-Feature, multi-camera, multi-event
Place is required (§12 of the governing brief) and reported in the
closure report rather than assumed.

## 9. Dimensions that must remain separate, never collapsed

- Reviewed change fact vs. Inferred wildlife association vs. Inferred
  environmental context — three different epistemic tiers, three
  different fields, never blended into one sentence or one number.
- Recent-window yield rate (fixed 7-day, "how active lately") vs.
  event-scoped before/after comparison (variable window, "did activity
  change after this dated change") — two different questions with two
  different denominators; always two separate sections/columns.
- Association `status` (direction) vs. `maturity` (confidence/data
  availability) — both always shown together; a caller must never say
  "activity increased" when `maturity` is `too_soon`.
- Visit count, distinct-taxon count, and rate — three separate columns,
  never weighted into one figure.

## Non-goals reaffirmed for this contract specifically

No new analytics module. No composite/"habitat" score. No causal
language anywhere in new copy (audited against the existing forbidden-word
discipline `environmental_period_comparison`'s own composition already
established). No pagination added to Deliverable A/B unless measurement
in §12 of the closure report actually shows it is needed — Features and
their manually-recorded change events are both realistically small-N per
Place, unlike Visits.
