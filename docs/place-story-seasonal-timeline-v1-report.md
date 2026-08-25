# Place Story & Seasonal Timeline v1 — A Living History of the Place

## Identity

- **Starting HEAD:** `950d5c2` (verified exactly against the milestone brief's expected HEAD before any edit)
- **Implementation HEAD:** `055bd4a` — "Place Story & Seasonal Timeline v1: A Living History of the Place"
- **Docs/reconciliation HEAD:** the commit immediately following this report's own addition (this file + `release-execution-state.md` + `roadmap.md`), matching the established two-commit pattern from every prior milestone
- **Schema:** v55 → v55, **unchanged**. No new table, no migration. Every fact this milestone presents already existed as an authoritative, dated, reviewed record; this milestone adds a pure derived read-model over them (see "Story event model," below).
- **Commits:** `055bd4a` (implementation) + the reconciliation commit containing this file
- **Push state:** local accepted state only; not pushed (no push authorized this session)

## Archaeology (Phase 1)

Bounded archaeology was performed by five parallel research passes before any code was written: (1) doctrine/roadmap cross-references, (2) the three predecessor milestones' reusable primitives (Place/Yard Intelligence v2, Environmental Context v2, Place Features & Habitat Change v2), (3) Today/Bird Log/Wildlife Journal/Place Activity Report inventory, (4) Daily/Weekly Digest/habitat/feature/biodiversity-history inventory, (5) API/schema/frontend conventions. The full findings are preserved in this conversation's transcript; the load-bearing conclusions are recorded throughout this report rather than repeated as a separate appendix.

### Existing history/memory inventory

| User question | Existing source | Existing presentation | Missing Place-story capability | Composition used |
|---|---|---|---|---|
| "What's confirmed today?" | `dashboard_summary` / `_dashboard_today_summary` | Today (day-scoped, bounded lists) | No cross-day narrative | Not reused directly; Place Story is Place-wide, not day-scoped |
| "What's the full history of this species?" | `wildlife_journal_overview`/`_history` | Bird Log (paginated gallery, real offset/cursor) | No cross-species chronological view; no "why does this matter" ranking | Pagination idiom (`page_size`/`offset`/`has_more`/`next_offset`) copied exactly |
| "How is the Place doing over an arbitrary period?" | `place_activity_report` | Place Report (aggregated, one period at a time) | No persistent day-by-day/period-over-period narrative | `_historical_place_baseline_and_species_statuses` reused unmodified (additively extended, see below) |
| "Is this species new/regular?" | `historical_baseline.compute_species_historical_statuses` | Badges on Bird Log/Today rows | No dated "first_seen" *event*; no "became regular" moment | `first_confirmed_at`/`status` reused directly for `first_seen`; `compute_species_historical_statuses` re-applied at checkpoints for `regularity_change` |
| "Has activity changed lately?" | `place_change_summary.compute_place_change_summary` + `regularity_narrative.compute_regularity_narrative` | A single sentence in Today's digest, valid only "as of now" | No dated transition event | Re-applied at usable-date checkpoints (new mechanism, described below) — a genuine gap in the existing composition was found and worked around here, see "Truth / provenance" |
| "What changed around the yard, and when?" | `PlaceFeatureChangeEventModel` (Reviewed, dated) | Inline expand on Place Report only, no chronological cross-Feature view | No unified timeline entry | Direct 1:1 projection, zero new logic |
| "Did the change actually affect wildlife?" | `feature_change_comparison.compute_feature_change_comparison` | `PlaceFeatureAssociation` inside Feature detail only | No separate, dated "insight" entry | Reused unmodified via the *existing* `_compute_feature_change_event_comparison` repository method |
| "What's blooming/nesting/changing seasonally?" | `PlacePhenologyObservationModel` (Reviewed, dated interval) | Only inside habitat-context bundle and Bird Log's per-taxon `place_context` | No unified timeline entry | Direct 1:1 projection, zero new logic |
| "How diverse has this Place become?" | `place_biodiversity_summary` | A snapshot count only — no time series, no "Nth species" milestone anywhere | Missing entirely | Derived for free from `all_time_first_confirmed_at`, ranked by date — no new query |
| "What's noteworthy?" | `daily_digest.HighlightReason` (8-tier, day/week only) | `TodayReportPanel`/`WeeklySummaryCard` | No Place-wide, arbitrary-period, cross-domain importance model | Extended conceptually (two-tier `major`/`notable`), not imported directly — see "Story event model" |

For each existing surface: durable facts exist and are already reviewed-truth-gated; all four wildlife surfaces (Today/Bird Log/Place Report/Digest) are already **live-query-always**, no caching, correction-safe by construction; evidence drill-down exists for Visits everywhere; none of them composed into a single cross-domain chronological "why does this matter" narrative before this milestone.

## Product contract

Preserved exactly as the governing brief requires:

- **Epistemic classes.** Only `measured`/`inferred`/`reviewed` — no fourth class invented. Every wildlife-derived event and every Place Feature/phenology projection is `"reviewed"`. Only `comparison_insight` is `"inferred"`, and it is a structurally separate event from the `feature_change`/`phenology` fact it explains (never a merged causal sentence).
- **Encounter semantics.** No event implies one Visit = one animal. Every wildlife-derived title/summary describes the *taxon's presence at this Place*, mirroring `regularity_narrative.py`'s own existing discipline.
- **Place-centered, not a detector-output log.** No event kind corresponds to a raw detection, a raw frame, or a raw Visit. Ordinary repeated Visits are never surfaced — Bird Log already owns that.
- **Calm product.** No new event kind fires without a real, bounded, meaningful-transition test; see "Selection/suppression rules."
- **Local-first.** No new network dependency, no cloud call. `GET /api/place/story` is a local FastAPI route like every other endpoint in this codebase.

## Story event model (Phase 2/3)

**No new database table.** `mockingbird.analytics.place_story.PlaceStoryEvent` is a pure, frozen dataclass — the read-model *is* the composition, not a persisted materialization of one. This was a deliberate choice made after archaeology showed every fact source is already dated, already reviewed-gated, and already cheap enough to compose at read time (see "Long-history performance," below, for the one place this was actually measured, not assumed).

Fields: `id` (stable, deterministic — e.g. `first-seen:northern_cardinal`, `feature-change:{event_id}`, `regularity:{taxon}:{state}:{date}`), `kind`, `group`, `event_date`/`event_end_date` (intervals for phenology), `title`/`summary` (plain language, server-composed, never a raw enum shown to a user), `information_class`, `importance` (`major`/`notable`), `taxon_label`/`taxon_display_name`, `feature_id`/`feature_name`, `visit_id` (evidence drill-down), `zone_id`/`zone_name`/`source_id`, and a small `detail_refs` map (e.g. `{"change_event_id": ...}`) for provenance — never a duplicate copy of the underlying record's own fields.

**Taxonomy actually shipped** (small, per Phase 3's explicit instruction not to invent 50 kinds):

- **wildlife:** `first_seen`, `return`, `regularity_change`, `noteworthy_activity`, `diversity_milestone`
- **place:** `feature_change`, `phenology`
- **context:** `comparison_insight`
- **summary:** `period_summary` — vocabulary reserved, **not emitted in v1** (see "Remaining major PRODUCT opportunities")

`kind`/`group` are internal filter tags only; the UI never renders them raw (verified by an e2e assertion).

## Selection / suppression rules (Phase 4/6/14)

Suppression is structural, not a post-hoc filter pass:

- No function in `place_story.py` ever iterates per-Visit to emit an event — every wildlife-kind source function emits **at most one event per underlying transition**, never per encounter.
- `"became a regular presence"` fires **at most once ever per taxon** (`ever_reached_regular` tracking) — not once per rolling-window recomputation. This closed a real bug a first implementation had: because `historical_status` can only climb (it is a trailing-366-day cumulative count), a taxon's narrative can genuinely fall back to a plain `"regular"` a second time purely because its *change*-window comparison lost statistical support — that must never re-announce the original milestone. A synthetic-history regression test (`test_becoming_regular_fires_exactly_once_ever`) encodes this.
- Regularity/activity-change detection is a **usable-date checkpoint scan** re-applying the exact, unmodified `compute_place_change_windows`/`compute_place_change_summary`/`compute_species_historical_statuses`/`compute_regularity_narrative` functions at every date the underlying rolling windows could possibly have changed (every *usable* date — a provable, not approximate, sufficient condition; see the module docstring's "Why checkpoints" section) — never a second, invented definition of "quiet period."
- Reviewed Place facts (`feature_change`, `phenology`) are **never suppressed by importance** — every one always appears (Phase 13's explicit instruction: a user's own recorded change never disappears because an algorithm scores it low). Only wildlife-derived candidate events go through the selection logic above.
- `build_place_story`'s merge step asserts (not silently drops) if two sources ever produce the same `id` with divergent content — a defensive invariant, not a normal code path.

## Truth / provenance (Phase 15/16)

- **Live-query-always, zero caching**, matching this codebase's own universal discipline for every other Place read-model (`place_activity_report`, `get_place_feature_detail`, `place_biodiversity_summary`). Proven, not just asserted: `test_correction_is_reflected_on_the_very_next_call`, `test_removed_feature_change_event_disappears_from_the_story`, and `test_corrected_phenology_date_moves_the_story_entry` each mutate a fact via the real repository write path and assert the *very next* `place_story()` call reflects it, with zero invalidation step.
- **Provisional wildlife is never included.** Every wildlife-kind event is built exclusively from `_Classification.CONFIRMED_WILDLIFE` facts, via the same `historical_baseline`/`place_change_summary` inputs that already enforce that boundary. This is a deliberate, conservative reading of Phase 16 ("first-ever/major biodiversity milestones should generally obey existing high-trust semantics") applied to *every* wildlife event kind in v1, not only milestones — a provisional-in-Today-only, reviewed-in-Story split was considered and rejected for v1 as unnecessary complexity given the product's current review cadence; recorded as a future option, not a decision reversal.
- **A genuine, previously-undiscovered latent gap in already-accepted code was found and worked around, not silently patched at its source.** `place_change_summary._presence_status` returns `"no_supported_change"` unconditionally whenever `reference_presence_days == 0` (its own docstring: "a taxon never seen in the reference window has no historical rate to compare against"). That reasoning is correct for a genuinely brand-new taxon (already covered by `historical_baseline`'s own "new"/"first_record"), but the *same* zero-reference-presence condition is also exactly what a real absence-then-return produces for an *already-established* taxon — and `regularity_narrative.compute_regularity_narrative`'s own documented `"returned_after_absence"` branch requires precisely `change_status == "higher_recent_presence"` *and* `reference_presence_days == 0`, a combination `_presence_status` can never actually produce. **This means Today's and Bird Log's own already-shipped `"returned_after_absence"` wording has never been reachable in production, for any taxon, since Place / Yard Intelligence v2 shipped** — confirmed by first reproducing the gap with a synthetic scenario, then reading `place_change_summary.py`'s own source to root-cause it precisely (not inferred). This milestone does **not** modify `place_change_summary.py` — it is frozen, already governs two other live surfaces' wording today, and a threshold-policy change there is explicitly outside this milestone's authority. Instead, `place_story._effective_regularity_state` applies one narrow, clearly-documented supplemental check using only fields `compute_place_change_summary` already computes *correctly* (`reference_presence_days`/`recent_presence_days` — only the derived `.status` collapses them) plus the existing, already-versioned `MIN_ABSOLUTE_PRESENCE_DAY_DIFFERENCE` constant, guarded so a brand-new taxon's clustered first sightings can never be mistaken for a return (`first_confirmed_at` must predate the reference window entirely). **Recommendation:** revisit `place_change_summary.py`'s own threshold policy in a future, dedicated milestone so Today/Bird Log's own wording gains the same capability directly, rather than leaving this fix local to Place Story.
- A second, narrower real bug was found and fixed during implementation, before any commit: an early checkpoint-scan implementation only generated checkpoints inside the *requested* period, so `previous_states` was never seeded with a taxon's true prior state — asking for a *later* period alone (e.g. "this month") would falsely re-announce a transition that had genuinely happened months earlier. Fixed by generating checkpoints across `[period_start_at - 366d, period_end_at]` and only ever *emitting* within the requested bounds; `test_transitions_before_the_requested_period_are_not_emitted` and `test_overall_activity_transitions_before_the_period_are_not_emitted` are the regression tests.

## Wildlife milestones (Phase 5/6/21)

- `first_seen` — direct from `historical_baseline`'s already-computed all-time `first_confirmed_at`; `"new"` (established baseline) → `major`, `"first_record"` (baseline still developing) → `notable`, mirroring `daily_digest.py`'s own identical honest distinction.
- `return` — the discovered-gap fix above; dated at the earliest presence date within the qualifying recent window, not the checkpoint date itself (a more precise, honest "when it actually came back").
- `regularity_change` — `becoming_regular`/`quieter_lately` (repeatable over a taxon's life) and `regular` reached for the first time (one-time milestone).
- `noteworthy_activity` — the same checkpoint mechanism applied to `PlaceChangeSummary.overall` (Place-wide, not per-taxon).
- `diversity_milestone` — 1st/5th/10th/25th/50th/100th species, derived "for free" by ranking taxa on their own already-computed `first_confirmed_at` — no stored counter, no time-series table, no gamification (fixed, small, deterministic tiers only; no streaks, no badges beyond the milestone fact itself).

## Place Feature / habitat integration (Phase 7/8)

`feature_change` is a direct, unmodified projection of `PlaceFeatureChangeEventModel` — `added`/`removed` → `major`, everything else → `notable`. `comparison_insight` reuses the *existing* `_compute_feature_change_event_comparison` repository method (the exact one `get_place_feature_detail` already calls) — zero new before/after computation. It is a separate event, `information_class="inferred"`, dated at the comparison window's own close (`post_end`), never fused into one causal sentence with its parent `feature_change` (verified by an explicit unit test asserting the summary text keeps the "compared with" clause and the caveat clause distinct).

## Environmental / phenology composition (Phase 9/10)

`phenology` is a direct, unmodified projection of `PlacePhenologyObservationModel`, including its interval (`event_end_date`). Routine weather was deliberately **not** put on the timeline (Phase 9's explicit instruction). A `weather_caveat` parameter exists on `comparison_insight_event` and is wired through the repository method — but is always passed `None` in v1: composing a real caveat (classifying the pre/post windows via `condition_bands`, honestly omitting it when weather coverage is too sparse — a real, common case per the accepted Environmental Context v2 report) needs its own scoped implementation and test pass. This is the single largest deliberately-deferred piece, in the same spirit as Place Features & Habitat Change v2's own honest recording of the identical gap — see "Remaining major PRODUCT opportunities."

## Timeline product experience (Phase 18/19/23/27)

`web/src/pages/PlaceStoryPage.tsx` — a calm, newest-first, month-grouped list. Filters: Period (Recent 90 days / This month / This year / All history) and Category (All / Wildlife / Place changes / Insights), both native `<select>` elements (no custom query builder). Cards show a `StatusPill` type indicator, the date, an "Inferred" marker only when applicable, plain-language title/summary, and evidence actions ("View evidence" → Visit Detail, "… in Bird Log" → that species' history, "View in Place Report" for Feature/phenology entries, since no dedicated Feature-detail route exists yet — see below). Early-experience state is honest and distinct from "filter matched nothing." Reachable from the persistent nav and from a new "See the Place Story" link on Today, next to the existing "See the full place report" link. No dedicated image thumbnails are rendered in v1 (Phase 22's "text-only is acceptable" fallback) — see "Remaining major PRODUCT opportunities."

## Taxon / Feature story behavior (Phase 20)

The API already supports `taxon`/`feature_id` filters end-to-end (tested via real HTTP). No dedicated "story of this taxon"/"story of this feature" *page* was built in v1 — a bounded, honestly-recorded gap, not a silent omission. The cheapest real next step (linking a taxon/Feature name elsewhere in the product straight into a pre-filtered Place Story) is recorded below.

## Correction safety (Phase 15/29)

Proven directly, not just asserted by design: species re-classification, a removed Reviewed Feature change event, and a corrected phenology date each change the very next `place_story()` read, with the stale entry gone and (for the phenology case) the corrected entry appearing under its new date/period instead.

## Long-history performance (Phase 24)

Measured, not assumed: a synthetic 3-year, 20-taxa, 1,637-Visit, 1,096-usable-day dataset (adversarially randomized, denser than any real installation this product currently has) ran the full regularity/overall-activity checkpoint scan in **1.85s** total. `_visit_slice` uses a one-time sort plus `bisect` per checkpoint (`O(checkpoints·log(visits))`, not `O(checkpoints·visits)`). Wildlife-derived events are bounded to the same trailing `HISTORICAL_BASELINE_WINDOW_DAYS` (366-day) window every other regularity feature in this codebase already uses — a request spanning further back still sees every in-range Reviewed Feature/phenology fact, but older wildlife milestones are a recorded, bounded v1 gap (see below), not a silent drop. An unbounded "all history" request defaults to a defensive 5-year lookback cap (`PLACE_STORY_DEFAULT_LOOKBACK_DAYS`) — a guard rail, not a real product limit given this installation's actual age. No materialized storage was added; nothing measured here justified it.

## Production-shaped validation (Phase 28)

Synthetic multi-fact scenarios were exercised against a real, isolated SQLite repository (not mocks) via `tests/test_place_story_repository.py` and ad hoc scratchpad scripts during development: a first-ever species observation, an every-other-day presence burst crossing the regularity threshold, a genuine multi-week quiet gap followed by real daily resumption (correctly producing `return`, not a false re-announcement), a Feature added with a `major`-tier entry, a phenology interval, and three independent correction scenarios (species, Feature-change deletion, phenology-date edit). The resulting chronology reads as intended: dated, plain-language, calm (a handful of entries across a multi-month synthetic history, never one per Visit), and every claim traces to a real underlying fact via `detail_refs`/`visit_id`. This is synthetic-data confidence, not field/ecological validation — no claim beyond that is made.

## Tests

- `tests/test_place_story.py` — 24 pure-module tests (zero DB): first-seen/diversity-milestone derivation, the regularity-checkpoint scan (including both discovered-bug regression tests), Feature/phenology/comparison-insight projection, and `build_place_story`'s merge/sort/filter/paginate/date-range-overlap contract.
- `tests/test_place_story_repository.py` — 8 repository/HTTP integration tests against real seeded SQLite data and a real FastAPI `TestClient`: first-seen-from-real-visits, Feature-change projection, phenology projection, three correction-safety proofs, the early-experience contract (accounting for this codebase's own standing `seed_if_empty()` demo-data behavior — a real repository is never literally content-free), and paginated/filtered `GET /api/place/story` over real HTTP.
- `web/e2e/place-story.spec.ts` — 6 Playwright specs: empty/early-experience state, populated month-grouped rendering (with an explicit assertion that no raw `kind` enum value ever leaks into visible text), evidence drill-down to Visit Detail, the category filter's actual outgoing request shape, phone-width layout with no horizontal overflow, and reachability + heading order from Today.

### Validation commands/results

- **Tier 1 (focused):** `tests/test_place_story.py` (24) + `tests/test_place_story_repository.py` (8) = 32/32 passed.
- **Tier 2 (Core):** `python scripts/verify_core.py` — **4958 passed / 2 failed / 3 skipped / 23 deselected / 11 xfailed** (22m29s). The 2 failures (`test_place_biodiversity_summary_repository.py::test_api_route_returns_the_summary` and `::test_human_correction_updates_place_biodiversity_intelligence_correctly`) are the identical, already-documented pair every prior milestone checkpoint in `release-execution-state.md` §14 has re-confirmed pre-existing — re-confirmed *again* this session via `git stash push -u` bisection against the clean `950d5c2` baseline (byte-identical failure, same assertion, same `'seen_before' == 'new'` mismatch, with zero of this milestone's changes applied; `git worktree` is documented elsewhere in this repo's memory as giving invalid baselines here, so `git stash push -u`/`pop` was used instead, then the stash was dropped after a diff-against-stash confirmed zero content loss).
- **Frontend:** `tsc --noEmit` clean; `vite build` clean (`page-PlaceStoryPage-*.js` code-split correctly); 44/44 e2e passed — 6 new (`place-story.spec.ts`) + 38 directly-adjacent re-run clean (`bird-log-historical-status`, `dashboard-live-camera-ownership`, `place-activity-report`, `place-features`, `today-report`).
- `git diff --check`: clean.
- Tier 3 (Full) was not run — no packaging/install behavior changed, matching the brief's own instruction not to run Full without that trigger.

## Remaining major PRODUCT opportunities

Recorded deliberately, not as release blockers (matching this codebase's own established pattern):

1. **Period summaries (Phase 12) were not implemented.** A naive per-month implementation would call the expensive `_historical_place_baseline_and_species_statuses` once per month in range — a real, measured-to-be-relevant performance cost this milestone chose not to pay without first designing a cheaper per-period digest path or an explicit memoization strategy. This is the single largest scoped-out capability from the governing brief.
2. **Environmental-context caveats on `comparison_insight`** (Phase 9) — the parameter exists and is wired; the actual weather-band composition is not implemented.
3. **No dedicated taxon/Feature "story" page** (Phase 20) — the API already supports it; only the UI wrapper is missing. Cheapest next step: link taxon/Feature names elsewhere in the product straight into a pre-filtered Place Story.
4. **No representative imagery on Story cards** (Phase 22) — text + a Visit evidence link only; reusing the existing representative-evidence selector for card thumbnails is a bounded follow-up, not a new mechanism.
5. **`place_change_summary.py`'s own `_presence_status` threshold gap** (documented above) — recommend a dedicated future milestone so Today/Bird Log gain working `"returned_after_absence"` wording directly, rather than only Place Story's own local workaround.
6. **Wildlife-derived events are bounded to a 366-day trailing window** for any one request — a real, if currently theoretical (given this product's real age), ceiling for a multi-year "all history" view.
7. **No dedicated deep-link target for a Feature or phenology observation** exists anywhere in the product yet (a pre-existing gap, not introduced here) — Story cards fall back to "View in Place Report."

None of these were built by adjacency; each is recorded as a real, scoped, future decision.

## Capability classification

**B** — major useful capability, bounded history/story gaps. A coherent, correction-safe, tested, calm cross-domain timeline genuinely exists and materially strengthens "Remember" (firsts, returns, regularity shifts, reviewed Place changes, phenology, and honest before/after insight, all in one dated, filterable, paginated place) — but period summaries (an explicitly-requested capability) were not built, weather context is not yet composed onto insights, and taxon/Feature-specific story views and representative imagery remain UI-layer follow-ups on an already-working API.

## Scheduler reconciliation

Confirmed: **CURRENT PHASE = SUBSTANTIAL PRODUCT DEVELOPMENT**. This milestone does not close that phase; see `docs/release-execution-state.md` for the reconciled record.

## Preserved files

The seven preserved untracked detector files were verified present and untouched at the start of this session and remain so now (never staged, edited, renamed, or deleted): `docs/wildlife-detector-training-contract.md.orig`, `scripts/evaluate_small_bird_detector.py`, `scripts/materialize_wildlife_stage2.py.orig`, `scripts/train_wildlife_stage2_rfdetr.py.orig`, `src/mockingbird/detectors/small_bird_benchmark.py`, `src/mockingbird/training/wildlife.py.orig`, `tests/test_small_bird_benchmark.py`.

## Identity (final)

- **Implementation commit:** `055bd4a` — "Place Story & Seasonal Timeline v1: A Living History of the Place" (16 files changed, 2895 insertions, 0 deletions)
- **Docs/reconciliation commit:** the commit containing this file together with `docs/release-execution-state.md` and `docs/roadmap.md`
- **Schema:** v55 → v55, unchanged
- **Push state:** local accepted state only; not pushed

## Exact git status --short (immediately before the reconciliation commit)

```
 M docs/release-execution-state.md
 M docs/roadmap.md
?? docs/place-story-seasonal-timeline-v1-report.md
?? docs/wildlife-detector-training-contract.md.orig
?? scripts/evaluate_small_bird_detector.py
?? scripts/materialize_wildlife_stage2.py.orig
?? scripts/train_wildlife_stage2_rfdetr.py.orig
?? src/mockingbird/detectors/small_bird_benchmark.py
?? src/mockingbird/training/wildlife.py.orig
?? tests/test_small_bird_benchmark.py
```

The seven `??` entries below the new report are the preserved, intentionally-untracked detector files — untouched, exactly as at session start.
