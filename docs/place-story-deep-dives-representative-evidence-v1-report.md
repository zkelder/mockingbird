# Place Story Deep Dives & Representative Evidence v1

A deliberately-authorized, one-time, bounded product-development reopening
(see `docs/release-execution-state.md` for the full governing brief). Builds
MockingBird's first dedicated, URL-addressable "story of one thing at this
Place" surfaces -- a Taxon Story (the story of one species here) and a
Feature Story (the story of one Place Feature here, and this product's
first dedicated Feature detail page) -- plus a representative-evidence
contract that both surfaces, and Place Feature detail generally, now share.

## Starting state

- Branch `main`, accepted HEAD `973cb5e` (the report commit for Multi-Camera
  Place Feature Linking & Cross-View Habitat Context v1).
- Schema `v59`, unchanged by this milestone (stays `v59` -- no migration).
- `CURRENT PHASE`: `FEATURE FREEZE -- EVIDENCE, RELEASE READINESS &
  HOUSEKEEPING`. Lane P `CLOSED`. Lane R `OPEN -- RELEASE-CRITICAL -- TRUE
  LATENCY TAIL EVIDENCE REMAINS` (untouched by this milestone, per its own
  explicit instruction not to touch it).
- Authorization before this milestone: `NONE -- GLOBAL PRODUCT-ROADMAP
  RECONCILIATION REQUIRED`.
- Worktree verified safe at start and throughout: all seven preserved
  untracked detector files (`docs/wildlife-detector-training-contract.md.orig`,
  `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`) present and untouched; re-confirmed
  immediately before implementation began (`git rev-parse HEAD` matched
  `973cb5e`, `git status --short` matched exactly the seven files, no
  recently-modified files under `src/`/`tests/`/`docs/`/`web/`).

## Why product development was reopened

This milestone's own governing brief is an explicit, one-time, owner-issued
reopening naming exactly two capabilities the immediately-prior
reconciliation (`global-remaining-product-development-release-queue-
reconciliation-v1-report.md`) had already examined under its own
five-question product-opportunity test and classified **D -- enrichment,
not required before release**: "a dedicated taxon/Feature story page" and
"representative imagery on Story cards." The owner's explicit choice
tonight overrides that specific conclusion for these two named items only
-- matching the identical pattern of the two immediately-preceding
milestones (Environmental Context x Place Story composition; Year-over-Year
Seasonality), each also a one-time reopening of a named "D" item. This does
not reopen the roadmap generally, does not authorize a further milestone,
and does not change Lane R or Lane P.

## Existing architecture (archaeology, before any code change)

Five parallel research agents plus direct reads answered the governing
brief's own twelve archaeology questions (section 5) before any
implementation:

1. **`PlaceStoryEvent` fields** (`mockingbird.analytics.place_story.py`):
   `id`, `kind`, `group`, `event_date`, `event_end_date`, `title`,
   `summary`, `information_class`, `importance`, `taxon_label`,
   `taxon_display_name`, `feature_id`, `feature_name`, `visit_id`,
   `zone_id`, `zone_name`, `source_id`, `detail_refs`.
2. **Taxon filtering**: `GET /api/place/story?taxon=` already worked
   end-to-end (`build_place_story(taxon_label=...)`), keyed on the
   canonical `TaxonFact.label`, since Place Story & Seasonal Timeline v1
   shipped -- confirmed by an existing test
   (`test_filters_by_kind_taxon_and_feature`) and by the Calm Attention
   system already carrying `taxon_label` on `open_place_story` actions.
3. **Feature filtering**: `?feature_id=` likewise already worked
   end-to-end (`feature_change`/`comparison_insight` kinds).
4. **Representative imagery**: `RepresentativeEvidence` (visit id +
   `VisitEvidenceFrame` + stream context), always attached to a *Visit*,
   never to a taxon or Feature directly -- recomputed fresh on every read.
5. **Canonical best-evidence primitive**: yes --
   `mockingbird.analytics.representative_evidence.select_representative_
   evidence` (Gate C), already reused unmodified by Today and Bird Log.
6. Bird Log links to Visit detail via the existing `visit_id`/evidence
   plumbing, unchanged.
7. **Reviewed corrections in Story**: already proven live -- a correction
   changes taxon grouping and Story entries on the very next read, with no
   invalidation step
   (`test_reviewed_correction_moves_representative_eligibility_to_the_
   corrected_taxon`, `test_revision_keeps_one_effective_truth_for_bird_
   log_dashboard_analytics_and_exports`).
8. **Routing**: this codebase has no `react-router` -- a hand-rolled
   `Page` union + `AppRoute`/`readAppRoute`/`writeAppRoute` in
   `web/src/navigation.ts` parses/builds every URL by hand.
9. **Reusing Place Story's own filtering rather than a second timeline
   engine**: fully possible, and done -- zero changes to `place_story.py`'s
   own event-selection/suppression logic were needed.
10. **The deferred-period-summaries performance concern** (calling the
    expensive `_historical_place_baseline_and_species_statuses` once per
    period in a range) does not apply here: a Taxon/Feature Story makes
    exactly one bounded call each, the same shape Bird Log/Feature-detail
    already make today.
11. **Representative evidence without loading every image**: yes -- the
    canonical selector ranks on already-persisted metadata only (widths,
    boxes, resolution provenance), with one `Path.is_file()` stat per
    bounded candidate, never an image decode.
12. **Missing fields for clean deep-linking**: none. `taxon_label`
    (already used for Bird Log navigation) and `feature_id` (FK-quality,
    on `feature_change`/`comparison_insight`) were already sufficient.

**The single most consequential archaeology finding**: `GET /api/bird-log/
journal/{label}` (`wildlife_journal_history`, Bird Log's existing per-species
drill-down) already returns essentially the entire Taxon Story header for
free -- `regularity_narrative`, `historical_status`, `change_status`,
`seasonal_pattern`, first/latest observation with representative evidence,
busiest Zone/Stream, all keyed by canonical label and already correction-
safe. Likewise `GET /api/place/features/{id}/detail` (`get_place_feature_
detail`, already accepted, already exercised by the Place Report's inline
expand) already returns a Feature's current state, every change event with
its own before/after and environmental comparison, and recent yield. This
meant the deep dives' *backend* delta could be genuinely small: one
additive Year-over-Year parameter, and one additive Feature-detail field --
never a second timeline engine, a second regularity engine, or a second
evidence engine.

## Shared Story composition contract

No second timeline engine was built, at either layer:

- **Backend**: `place_story.py`'s own event selection/suppression/kind
  taxonomy is completely unmodified. A Taxon Story's timeline is
  `GET /api/place/story?taxon=<label>`; a Feature Story's timeline is
  `GET /api/place/story?feature_id=<id>`. The Place-wide Story page's own
  request shape is unchanged.
- **Frontend**: `PlaceStoryPage.tsx`'s own private card renderer was
  extracted into a shared, exported component,
  `web/src/components/PlaceStoryEntryCard.tsx` (`KIND_LABEL`/`GROUP_TONE`
  moved with it), reused unmodified by `PlaceStoryPage`, `TaxonStoryPage`,
  and `FeatureStoryPage`. This is the "smallest shared composition
  boundary" the governing brief's section 16 explicitly permits when a
  literal refactor is warranted -- a rendering extraction, not a new
  engine, and behavior-preserving (the existing `place-story.spec.ts` suite
  passes unmodified).

## Taxon deep dive

`web/src/pages/TaxonStoryPage.tsx`, route `/place-story/taxon/:label`
(canonical taxonomy label, never a display string). Composes three already-
existing endpoints, each fetched independently so one's failure never blanks
the others:

- **Header**: `GET /api/bird-log/journal/{label}?preset=all_time` (Bird
  Log's own existing per-species bundle) -- regularity/historical-status
  badges (`historicalStatusBadge`/`regularityNarrativeBadge`/
  `changeStatusBadge`, the exact shared helpers Today/Bird Log already use,
  reused unmodified), a seasonal-pattern note, first-observed date
  ("First observed here on August 28."), busiest Zone
  ("Frequently recorded near the Bird Bath Zone."), and the representative
  image -- zero new backend computation.
- **Year-over-year line**: `GET /api/place/year-over-year?taxon=<label>`
  (see "Year-over-year, taxon-scoped" below) -- reuses `YearOverYearCard`'s
  own exported `speciesChangeSentence` composer verbatim, so the wording
  ("observed higher often this period", "first observed here about N days
  earlier than last year") never drifts from the Dashboard/Place Report
  card's own phrasing for the identical fact.
- **Timeline**: `GET /api/place/story?taxon=<label>`, rendered via the
  shared `PlaceStoryEntryCard`.

A 404 from the header endpoint (an unrecognized or non-wildlife label) is
an honest **not-found** state ("No taxon story here"), not an error banner
and not a fake narrative; a *known* taxon with zero confirmed observations
renders a distinct **sparse** state ("No confirmed observations yet") --
these are two different backend outcomes (404 vs. 200 with
`observation_count: 0`) and the page tells them apart correctly.

## Year-over-year, taxon-scoped

The only genuinely new backend computation this milestone adds. Before this
milestone, `compute_species_year_over_year_comparisons`'s full, unranked,
per-taxon result was computed inside `_year_over_year_comparison_facts_in_
session` and then immediately discarded after `select_notable_species_
changes` bounded it to the top 5 -- explicitly recorded as a future
opportunity in the Year-over-Year Seasonality v1 report's own "remaining
opportunities" ("a future milestone wanting the complete per-taxon list...
has `compute_species_year_over_year_comparisons`'s own unranked, unbounded
return value already available at the repository layer"). This milestone:

- widens `_year_over_year_comparison_facts_in_session`'s return to a
  3-tuple, adding the already-computed `species_comparisons` list (its
  two existing call sites -- `place_year_over_year_comparison` and
  `place_story`'s own year-over-year gate -- updated to unpack it,
  behavior-unchanged for the second);
- adds an optional `taxon` parameter to `place_year_over_year_comparison`
  (and the `GET /api/place/year-over-year` route), which resolves the
  input via the existing `_taxonomy_label_model_for_input` resolver
  (accepting a label, display name, or alias, exactly like Bird Log's own
  drill-down) and looks the taxon up in the already-computed list;
- adds one additive response field, `PlaceYearOverYearResponse.taxon_
  comparison`, reusing the existing `_year_over_year_species_entry_
  response` reshaping function verbatim -- no second response type.

Proven directly, not merely asserted: `test_taxon_param_returns_comparison_
even_when_not_notable` seeds six other real species changes so the
requested taxon is genuinely crowded out of the bounded top-5 list, then
confirms `taxon_comparison` still returns its own real comparison;
`test_taxon_param_accepts_display_name_input` proves alias resolution;
`test_taxon_with_no_data_in_either_period_abstains_honestly` and
`test_unknown_taxon_input_abstains_rather_than_erroring` both return `None`,
never a fabricated result or a 500; `test_omitting_taxon_leaves_taxon_
comparison_none` proves zero behavior change for every existing caller.

## Feature deep dive

`web/src/pages/FeatureStoryPage.tsx`, route `/place-story/feature/:id`.
This is also this product's **first dedicated, URL-addressable Feature
detail page** -- Place Features & Habitat Change v2 and Multi-Camera Place
Feature Linking v1 had both explicitly recorded "a dedicated Feature detail
page/route" as a real, named, deliberately-deferred gap ("today folded into
an inline expand on the Place Report page... a real standalone page... is a
natural, small follow-up"). Closing that gap and building the Feature Story
deep dive turned out to be the same piece of work, since `GET /api/place/
features/{id}/detail` already carried everything a dedicated page needed
except a representative image.

- **Header**: `GET /api/place/features/{id}/detail` -- Feature name/type,
  an "Inactive" pill when applicable, "Observed by: {camera}{ (archived)}{
  — Zone}, ..." (the identical rendering convention `PlaceActivityReportPage
  .tsx`'s existing inline expand already established, reused verbatim),
  recent yield ("Last 7 days: 12 confirmed visits, 3 distinct species (1.2
  per monitored hour)."), the most recent Reviewed change with its own
  before/after sentence (`featureAssociationSentence`, exported and reused
  unmodified) and environmental-context line (`environmentalComparisonSentence`,
  same), and the representative image.
- **Timeline**: `GET /api/place/story?feature_id=<id>`, rendered via the
  same shared `PlaceStoryEntryCard` -- `feature_change`/`comparison_insight`
  entries only, never every Visit (Bird Log remains the occurrence log; a
  Feature Story is not a second one).

The header shows only the Feature's *current state* (latest change, current
yield); the full historical change list lives in the timeline below, which
Place Story's own existing engine already composes one entry per change
event (never per camera) -- so this milestone never renders the same fact
twice in two different, potentially-drifting shapes.

A 404 (invalid/deleted Feature id) renders an honest not-found state; a
Feature with zero observation links, zero changes, and zero evidence
renders a fully sparse-but-honest header ("no camera linked yet", "No
changes recorded for this Feature yet.", "Not enough monitoring linked yet
to show recent activity.").

## Representative evidence contract

One canonical selector, reused, never duplicated:
`mockingbird.analytics.representative_evidence.select_representative_
evidence` (Gate C) is completely unmodified by this milestone. What changed
is *who gathers candidates for it*:

- **Taxon Story** needs no new gathering code at all -- it reads Bird Log's
  own already-computed `representative` field.
- **Feature Story** needed a new candidate-gathering path, since no caller
  had ever asked "the best image across this Feature's own linked camera
  views" before. `ProductRepository._feature_representative_evidence`
  (new) reuses the exact multi-view-aware, cross-camera-deduplicated query
  core (`_feature_scoped_visit_rows`, extracted from `_feature_scoped_
  visit_facts` as a pure, behavior-preserving refactor -- see "Multi-camera
  behavior" below), filters to confirmed wildlife via a newly-extracted
  shared predicate (`_is_confirmed_wildlife_summary`, lifted verbatim out of
  `_wildlife_journal_confirmed_records`'s own inline logic so both callers
  share one truth boundary), and hands the result to `_representative_
  evidence_response` -- the *same* function Today and Bird Log already call.
  `PlaceFeatureDetail.representative_evidence` is the one new, additive
  response field.

Scope is **all of the Feature's own history**, not `recent_yield`'s bounded
7-day window (mirroring Bird Log's own unbounded-history precedent for the
identical reason: "what did MockingBird actually see here" should not go
blank the moment a feeder's recent week happens to be quiet).

## Evidence selection / abstention

Every abstention path required by the governing brief is real and tested,
not merely designed:

- **No observation links** -> `representative_evidence: null`
  (`test_feature_representative_evidence_none_without_observation_links`).
- **No confirmed wildlife Visit in scope** -> `null`, even with a real,
  otherwise-eligible image attached to an unreviewed Visit
  (`test_feature_representative_evidence_none_when_no_confirmed_wildlife_
  visit`).
- **Visits outside the Feature's own scope never leak in** -- a confirmed,
  fully-eligible Visit on an *unlinked* Zone of the same camera is
  correctly excluded
  (`test_feature_representative_evidence_ignores_visits_outside_feature_
  scope`).
- **A missing media file abstains cleanly** -- the winning candidate's own
  file was deleted from disk -> `null`, never a broken thumbnail
  (`test_feature_representative_evidence_abstains_when_media_file_missing`,
  and the product-shaped scenario's own deliberately-deleted frame).
- **Every linked camera view is considered**, not only the first
  (`test_feature_representative_evidence_spans_every_linked_camera_view`).
- Frontend: `RepresentativeThumbnail` (new shared component, mirrors Bird
  Log's own established `JournalThumbnail` fallback/`onError`/audio-aware
  convention without duplicating that already-accepted component's
  internals) renders a calm "No image yet" placeholder on any load failure
  or absent evidence -- never a broken `<img>`.

## Truth / correction safety

Proven directly at both the representative-evidence layer and (already, by
inheritance) the Story-timeline layer:

- `test_feature_representative_evidence_reflects_correction_on_next_read`:
  correcting the winning Visit to `false_positive` removes it from
  representative-evidence eligibility on the very next `get_place_feature_
  detail` call, no invalidation step.
- The product-shaped scenario proves the identical property live: after
  revising the winning Cardinal Visit away, `representative_evidence` is
  either `None` or points at a different Visit -- never the corrected-away
  one.
- Taxon Story's and Feature Story's own *timelines* inherit Place Story's
  already-proven correction-safety unmodified (`test_correction_is_
  reflected_on_the_very_next_call` and siblings, pre-existing, unaffected)
  -- filtering by `taxon=`/`feature_id=` happens after the identical
  correction-aware composition, not before it.
- Year-over-year's `taxon_comparison` inherits the exact same correction-
  safety property `TestCorrectionSafety::test_reviewed_species_correction_
  changes_the_very_next_call` already proves for the underlying `species_
  comparisons` list this milestone's own code merely filters.
- No second truth system was created anywhere: every sentence a deep dive
  shows is either a direct Reviewed fact, or an already-governed Inferred
  composition (year-over-year, before/after, environmental caveat) reusing
  its own pre-existing, already-audited wording -- nothing is persisted as
  a new authoritative record.

## Multi-camera behavior

Reuses v59 observation-link authority unmodified; no singular-compatibility
field is treated as canonical anywhere in this milestone's own new code.
Concretely:

- `_feature_scoped_visit_rows` (new, extracted from `_feature_scoped_
  visit_facts` as a pure, behavior-preserving refactor -- `start_at`
  becomes optional so representative-evidence gathering can request "all
  time" while the two pre-existing bounded-window callers are completely
  unaffected) is the one shared query+dedup core behind *both* Feature
  yield/before-after (existing) and Feature representative evidence (new).
  It already applies `_associated_visit_ids_to_exclude_from_counting` --
  one real cross-camera encounter never produces two representative-
  evidence candidates for the same real bird.
- `test_feature_representative_evidence_spans_every_linked_camera_view`
  proves representative evidence considers a Feature's *second* linked
  camera, not only its first.
- The product-shaped scenario proves one canonical Feature, two camera
  views, one Reviewed change event, one Story `feature_change` entry
  (never one per camera), and cross-camera-deduplicated activity, all
  composed through the identical, unmodified v59 mechanism.

## Archived / expired evidence

- **Archived camera, valid history**: `test_feature_representative_
  evidence_survives_camera_archival` and the product-shaped scenario's own
  Act 9 both archive a linked camera *after* its historical window closed
  and confirm representative evidence, `get_place_feature_detail`, and both
  Story timelines remain fully reachable and numerically unchanged --
  `_feature_scoped_visit_rows` never excludes an archived Source, matching
  the accepted "archiving preserves history" doctrine this exact mechanism
  already established for yield/before-after.
- **Expired/deleted media**: a retained Story event or change event whose
  own representative candidate has lost its backing file abstains cleanly
  (see "Evidence selection / abstention" above) -- the *history* (the
  change event, the Story entry) remains; only the *image* honestly
  disappears. No UI path conflates the two: a sparse-evidence Feature/Taxon
  still shows its full text-based history, just without a photo.

## Deep linking / routes

- `web/src/navigation.ts`: `Page` gains `"taxon-story"`/`"feature-story"`;
  `AppRoute` gains `taxonLabel`/`featureId`; `readAppRoute`/`pathForAppRoute`
  parse and build `/place-story/taxon/:label` and `/place-story/feature/:id`
  -- a 3-segment special case mirroring the existing `/cameras/:id/edit`
  convention, not a mechanical copy of the governing brief's own literal
  `/place/story/taxon/{id}` suggestion (this codebase's actual routing
  architecture nests deep-dive routes under the existing `/place-story`
  path instead).
- **Bookmarkable/reload-safe**: both routes parse identically on first load
  and on reload (`test-e2e` "reload keeps the same ... story reachable",
  ×2). **Invalid identity**: a well-formed-but-nonexistent label/id parses
  the route correctly and lets the *page* render an honest not-found state
  (matching every other detail page's `error-panel`-family convention) --
  the router itself only recovers to Dashboard for a genuinely unrecognized
  path shape, unchanged.
- **Deep links wired at every location the governing brief named**:
  - **Place Story** (`PlaceStoryEntryCard`): a taxon-linked entry gains a
    "{name}'s story" action (additive, alongside the existing "{name} in
    Bird Log" link, not replacing it); a Feature-linked entry's action
    becomes "{name} story" (replacing the previous "View in Place Report"
    fallback, which remains only for `phenology` entries, which carry no
    `feature_id`).
  - **Bird Log**: a new "See {name}'s story" link on the per-label detail
    header.
  - **Place Feature cards/detail**: `PlaceFeaturesCard`'s calm-view feature
    tags become clickable (`onOpenFeatureStory`, optional prop, backward
    compatible); `PlaceActivityReportPage`'s inline Feature expand gains a
    "View {name} story" action alongside its existing "See activity
    insight" toggle.
  - **Year-over-Year card**: gains `onOpenTaxonStory`, wired as the primary
    per-species action (its existing Bird Log link is kept as a second,
    explicit "Bird Log" action, not removed).
  - **Calm Attention**: `App.tsx`'s `openAlertAction` now checks
    `action.taxon_label`/`action.feature_id` first (already flowing to the
    frontend, previously unused there) and routes directly to that taxon's/
    Feature's own Story, falling back to the pre-existing category-group
    Place Story scoping only when neither is present -- a small, trivial,
    well-tested change matching the governing brief's own explicit
    allowance (section 14), not a Web Push/attention-persistence/read-state
    reopening.

## Place-wide Story impact

No degradation. `PlaceStoryPage.tsx`'s own fetch, filters, pagination, and
early-experience/empty-state logic are completely unchanged; only its
per-entry action rendering was extracted into the shared `PlaceStoryEntryCard`
and given two new optional props. The full existing `place-story.spec.ts`
suite (6 specs) passes unmodified. No new representative imagery was added
to Place-wide Story cards themselves -- section 17's "do not turn Place-wide
Story into a dense wall of images" is honored by construction: images live
only on the two new deep-dive pages.

## Local Only

No new network dependency anywhere. Proven directly, not assumed: the
product-shaped scenario patches `socket.socket.connect` to raise for its
entire duration (the same technique Multi-Camera Place Feature Linking v1's
and Year-over-Year Seasonality's own scenarios already established) and
completes successfully end to end, including representative-evidence
gathering, the taxon-scoped year-over-year comparison, and both Story
timelines.

## Accessibility / mobile

- **Focus management**: `PageHeader` gained an optional `headingRef` prop
  (additive, unused by every pre-existing caller) so a Taxon/Feature Story
  page's own `<h1>` receives focus on load/subject-change -- the identical
  WAI-ARIA "focus the new region's own heading" pattern Fast Review's
  `activeItemHeadingRef` and the mobile nav drawer already established in
  this codebase, applied here to the one case those precedents did not yet
  cover (a top-level page swap in this router's own architecture). Proven
  by two e2e specs (`toBeFocused()` on the `<h1>`).
- **Alt text**: representative images use the exact "{name}, reviewed
  observation {date}" pattern (`RepresentativeThumbnail`) this codebase's
  own convention already reserves for Reviewed-truth-gated images (`Today
  ReportPanel.representativeAlt`, `BirdLogPage.thumbnailAlt`) -- safe here
  because representative evidence is *always* drawn from confirmed
  Visits by construction. A Feature's representative image (which has no
  single associated species) uses a deliberately neutral "Recent wildlife
  at {Feature name}, reviewed observation {date}" -- honest about
  provenance, never a fabricated species claim.
- **Keyboard**: every new interactive element is a real `<button type=
  "button">` (feature tags, "Load more", Story-entry actions, the
  representative-image button that opens its own Visit) -- none are
  `<div onClick>` affordances.
- **Mobile width**: zero new CSS was written. Both new pages reuse
  `.journal-label-card`/`.journal-label-image`/`.journal-label-card-body`
  (Bird Log's own existing two-column-collapsing-to-one-column grid,
  already responsive at ≤620px) for their header, and the existing
  `.place-story-entries`/`.place-story-card` classes for their timeline --
  inheriting mobile-safety for free rather than re-deriving it. Proven
  directly by two e2e specs asserting zero horizontal overflow at 375px.

## Performance

Measured with this codebase's own established `before_cursor_execute`
SQLAlchemy event-listener harness (`_count_queries`, mirroring `tests/
test_year_over_year_comparison_repository.py`'s identical pattern), not
assumed:

- **`taxon=` on year-over-year adds zero extra queries**
  (`test_taxon_param_adds_zero_extra_queries`) -- it is a pure Python
  filter over `compute_species_year_over_year_comparisons`'s already-
  computed, already-in-memory result; the one real lookup it does perform
  (`_taxonomy_label_model_for_input`) reuses the caller's already-fetched
  `taxonomy_index` rather than a second full-table scan.
- **Representative-evidence query count does not grow with unrelated Place
  history** (`test_representative_evidence_query_count_does_not_grow_with_
  unrelated_history`): 100 confirmed Visits seeded on a completely
  different, unlinked camera/Zone produce an identical query count to a
  minimal fixture -- the Feature's own SQL-level scoping (`_feature_
  observation_scopes`) is what bounds the cost, not a post-hoc filter.
- **A genuine, self-caught N+1-shaped inefficiency was found and fixed
  before shipping**: the first implementation pass built a full
  `StreamVisitSummary` (several of its own queries: evidence frames,
  suggestion lookup, Zone lookup) for *every* row `_feature_scoped_visit_
  rows` returned, before bounding to the last `MAX_REPRESENTATIVE_
  EVIDENCE_CANDIDATES` (20) -- for a Feature with a long, busy history,
  cost grew with that Feature's own total Visit count well past the point
  the bound would ever use it. Fixed by scanning most-recent-first and
  stopping as soon as 20 confirmed-wildlife candidates are found --
  behaviorally identical final selection (same most-recent-20-confirmed
  contract `_representative_evidence_response` already enforced), proven
  directly by `test_representative_evidence_query_count_does_not_grow_
  with_own_visit_count` (25 vs. 50 of the Feature's own confirmed Visits
  produce an identical query count) and by every pre-existing
  representative-evidence/scenario test continuing to pass unchanged after
  the fix.
- No image bytes are ever decoded during any of this -- selection ranks on
  already-persisted metadata only, matching the pre-existing Gate C
  contract exactly.
- Compared against the Place-wide Story baseline: a Taxon/Feature Story
  page issues three (Taxon) or two (Feature) independent, already-bounded
  fetches -- none reintroduce the "expensive baseline call per period"
  anti-pattern Place Story's own period-summaries gap warned against, and
  none query image bytes for a list of many items (the failure mode
  section 21 specifically forbids) -- each deep dive resolves exactly one
  representative image, for one subject, per page load.

## Product-shaped proof

`tests/test_place_story_deep_dives_product_shaped_scenario.py` -- one
continuous, real, executable scenario (real seeded SQLite, no mocking of
product logic), matching the governing brief's own section 34 worked
example: Place "Back Yard," Feature "Bird Bath" linked to Patio Camera/Bird
Bath Zone and Garden Camera/Pond Edge Zone (the identical naming Multi-
Camera Place Feature Linking v1's own scenario already established, for
continuity), Northern Cardinal and Carolina Wren as the two taxa, two years
of history. In one continuous run, proves: Cardinal activity materially
higher this September than last (a real year-over-year change, `activity_
direction == "higher"`); a real cross-camera Cardinal pair collapsing to one
counted encounter; several real evidence frames including one with an
already-deleted backing file (representative selection skips it honestly);
a Taxon Story for Cardinal that never includes a Wren-labeled event, and
vice versa; a Feature Story for Bird Bath containing exactly one
`feature_change` entry despite two linked cameras, with zero taxon-labeled
(per-Visit) entries; Patio Camera renamed and Garden Camera archived with
representative evidence, Feature detail, and the Cardinal Taxon Story all
remaining fully reachable and unchanged; a Reviewed correction removing the
winning representative-evidence Visit from eligibility on the very next
read; and Local Only operation throughout (any network-socket attempt fails
the test immediately).

## Validation

**Tier 1 (focused, backend)**:
- `tests/test_place_feature.py`: grew by 11 new tests (8 representative-
  evidence correctness/abstention + 1 HTTP round-trip + 2 performance), all
  passing; full file (86 -> 97 tests) passing.
- `tests/test_year_over_year_comparison_repository.py`: grew by 8 new
  tests (5 `TestTaxonComparison` + 2 HTTP round-trip + 1 performance), all
  passing; full file (25 -> 33 tests) passing.
- `tests/test_place_story_deep_dives_product_shaped_scenario.py`: 1 new
  comprehensive scenario test, passing.
- Directly-affected re-run: `test_place_story.py`, `test_place_story_
  repository.py`, `test_year_over_year_comparison.py`, `test_year_over_
  year_product_shaped_scenario.py`, `test_multi_camera_place_feature_
  linking_scenario.py` -- 221 passed, 0 failed (89.3s combined).
- `ruff check` on every touched Python file: zero new findings, confirmed
  by a message-level (rule + text) diff against a `git stash push -u`
  -isolated clean baseline (83 pre-existing findings, byte-identical
  before and after).

**Tier 2 (Core gate)**: `python scripts/verify_core.py` -- run given this
milestone's genuinely cross-cutting surface (`product_repository.py`,
`schemas.py`, `main.py`, `place_activity_report_adapter.py`, spanning
Place Story + Feature + Year-over-Year + representative-evidence
subsystems), matching development-workflow.md's own escalation rule
("anything crossing more than one subsystem"). **5875 passed / 1 failed
/ 3 skipped / 23 deselected (`slow`-marked) / 11 xfailed (2576.58s /
42m57s).** The one failure,
`tests/test_place_change_summary_repository.py::test_api_round_trip_
exposes_change_detection_fields` (`AssertionError: assert
'insufficient_recent_coverage' == 'higher_recent_presence'`), is
independently re-confirmed pre-existing and unrelated, not merely
assumed: a `git stash push -u` bisection ran this exact test against the
clean, unmodified `973cb5e` starting commit and reproduced the
byte-identical failure and assertion text -- conclusive proof this
milestone introduces no regression here. This is the same already-
documented, real-wall-clock-date-dependent flakiness class this
codebase's own validation baselines have recorded across numerous prior
milestones for this exact test/its sibling
(`test_place_biodiversity_summary_repository.py`) -- Multi-Camera Place
Feature Linking v1's own Core run, on this identical starting commit,
independently hit the same test with the same symptom. No code this
milestone touches (`place_change_summary.py`, `historical_baseline.py`)
was changed. Tier 3/Full was not run -- no schema/packaging/migration/
Camera-Node/BioCLIP code was touched, matching this milestone's own
governing brief section 36 and this codebase's own Tier-3-escalation
rules.

**Frontend**:
- `tsc --noEmit`: clean.
- `vite build`: clean (109 modules; `page-TaxonStoryPage`/`page-
  FeatureStoryPage` correctly code-split into their own chunks, matching
  every other page's lazy-loading convention).
- New e2e: `web/e2e/taxon-story.spec.ts` (8 specs) + `web/e2e/feature-
  story.spec.ts` (9 specs) -- 17/17 passing, covering direct route, reload,
  invalid id, sparse state, representative image + alt text, deep-link
  click-through, phone width, and focus management for both pages.
- Directly-adjacent re-run: `place-story.spec.ts`, `place-features.spec.ts`,
  `year-over-year.spec.ts`, `bird-log-historical-status.spec.ts`,
  `mobile-viewport-audit.spec.ts`, `today-report.spec.ts` -- 78/78 passing,
  zero regressions from the `PlaceStoryEntryCard` extraction, the
  `PlaceFeaturesCard`/`YearOverYearCard`/`PageHeader` prop additions, or the
  new `representative_evidence`/`taxon_comparison` response fields.

## New defects found/fixed

Two genuine, previously-nonexistent-until-this-milestone defects were found
by this milestone's own test-writing and measurement discipline, and fixed
before shipping (neither was ever in an accepted, released state):

1. **A real N+1-shaped inefficiency in this milestone's own first
   representative-evidence implementation** -- see "Performance," above.
   Found by writing the exact query-count regression test the governing
   brief's own section 21/32 requires, not assumed acceptable; fixed by
   scanning most-recent-first with an early exit, with zero change to the
   final selection outcome (proven by the full existing test suite passing
   unchanged after the fix).
2. **A redundant taxonomy-table re-scan in this milestone's own first
   `taxon=` year-over-year implementation** -- `_taxonomy_label_model_for_
   input` was called without the caller's own already-fetched `taxonomy_
   index`, triggering a second full-table scan `place_year_over_year_
   comparison` had already paid the cost of avoiding for its main
   computation. Found by the same query-count measurement discipline;
   fixed by threading the existing index through (`_taxonomy_label_model_
   for_input`'s own pre-existing, documented "performance escape hatch"
   parameter), proven by `test_taxon_param_adds_zero_extra_queries`.

No pre-existing defect in code this milestone read closely was found.

## Explicit deferred opportunities

Recorded deliberately, matching this codebase's own established pattern of
naming real future work rather than silently dropping it:

- **A year/month picker on the Taxon Story's year-over-year line** -- it
  always shows only the current month vs. a year ago, matching `Year
  OverYearCard`'s own identical, already-accepted scope boundary.
  Browsing other months is a natural, bounded follow-on.
- **`select_notable_species_changes`'s bounded top-5 list still has no
  general "see all" drill-down** on the Place-wide Year-over-Year card
  itself -- this milestone's `taxon=` parameter answers "one specific
  taxon's own comparison," not "show me the full ranked list," which
  remains a distinct, not-yet-built capability.
- **`RepresentativeThumbnail` was deliberately not backported into
  `BirdLogPage.tsx`'s own existing, already-accepted `JournalThumbnail`** --
  the two are behaviorally identical by design, but consolidating them was
  judged real, but out of this milestone's bounded scope (a working,
  tested, accepted component should not be touched merely for aesthetic
  de-duplication) and a genuine, small future opportunity.
- **A general Feature-comparison / "which Feature is more active" ranked
  view** remains unbuilt, as explicitly required (non-goal): a Feature
  Story tells the story of *one* Feature, never a leaderboard.
- **Place Story period summaries** remain unbuilt, as explicitly required
  (non-goal): a deep-dive header is a small, bounded, already-loaded-facts
  summary, never a general period-summary engine.
- **A Feature-specific year-over-year comparison** remains unbuilt, as
  explicitly required (non-goal) -- year-over-year stays species-scoped
  only.
- **Wildlife-kind Story events' own `source_id`/`visit_id` remain
  unpopulated** -- a separate, larger, previously-disclosed data-modeling
  exercise (Place Story's own report, Multi-Camera Place Feature Linking
  v1's own report), correctly out of this milestone's bounded scope; this
  milestone's own representative-evidence contract answers "what did
  MockingBird see" a different, already-sufficient way (via Bird Log's/
  the Feature's own representative-evidence gathering, not via the Story
  event's own fields), so this gap did not block anything here.
- **No real field/production proof of a live Taxon/Feature Story on real
  accumulated multi-year history** exists yet -- this product does not yet
  have a full multi-year real deployment anywhere (the identical,
  unavoidable "blocked on elapsed real history, not engineering"
  constraint Year-over-Year Seasonality v1 already disclosed). Every
  positive-outcome proof in this report is real-mechanism-and-synthetic-
  data (real repository, real SQLite, zero mocking of product logic), not
  a substitute for eventual real-field depth.

## Feature-freeze impact

This milestone closes exactly the two named product opportunities it was
authorized for (a dedicated taxon/Feature story page; representative Story
imagery), plus, as a direct consequence of building the Feature Story page,
the separately-long-named "dedicated Feature detail page" gap two prior
milestones had each recorded as their own explicit future dependency. It
does not touch, weaken, or reopen: Lane P (License, `CLOSED`, untouched);
Lane R (Complete Field Acceptance / true-latency-tail evidence, `OPEN --
RELEASE-CRITICAL`, completely untouched -- no code in this milestone's
scope intersects the Observation Engine's admission/timing path at all);
BirdNET's commercial-adjacent legal posture (untouched, unrelated); Web
Push, attention persistence, per-user read/dismiss state, or attention
diagnostics (none reopened -- the one Calm Attention change is a precise-
routing improvement using data the system already computed and already
sent to the frontend); External Pre-Release Acceptance or Final Release
Hardening (not authorized by this milestone, not self-authorized here).

`CURRENT PHASE` returns, unchanged in substance, to `FEATURE FREEZE --
EVIDENCE, RELEASE READINESS & HOUSEKEEPING` at this milestone's close.

## Decision

**A**

A complete, cleanly-scoped, fully-proven closure of both named product
opportunities, achieved almost entirely through composition of already-
accepted primitives rather than new engines -- the archaeology phase
correctly identified that the two backend deep-dive surfaces needed
strikingly little genuinely new code (one additive year-over-year
parameter; one additive Feature-detail field; one shared query-core
extraction), which let the bulk of the real engineering effort go into
correctness, abstention, correction-safety, and performance proofs rather
than into inventing new computation. Every hard requirement the governing
brief demanded is proven directly with real seeded data, not merely
designed or asserted: representative-evidence abstention (5 distinct honest-
`null` paths, each with its own regression test), correction safety (both
targeted tests and the live product-shaped scenario), multi-camera
correctness (reusing v59's own unmodified mechanism), archived-camera
reachability, Local Only operation, and bounded, measured performance. Two
genuine defects in this milestone's *own* new code (a real N+1-shaped
inefficiency; a redundant taxonomy re-scan) were found by its own
measurement discipline and fixed before shipping, with the fixes themselves
proven behavior-preserving. Validation is honest and layered: 19 new
focused backend tests plus one full product-shaped scenario, zero new lint
findings (verified by baseline bisection), a clean frontend build, 17/17
new e2e plus 78/78 directly-adjacent e2e with zero regressions, and Tier 2
(Core) run given the genuinely cross-cutting surface touched. Deferred
items are each a genuine, explicitly-scoped non-goal or a real future
opportunity, not a gap glossed over.

## Scheduler reconciliation

`CURRENT PHASE` confirmed unchanged: `FEATURE FREEZE -- EVIDENCE, RELEASE
READINESS & HOUSEKEEPING`. This milestone does not authorize External
Pre-Release Acceptance, Final Release Hardening, the next Lane R daylight
tranche, or any further product-development milestone. Lane R (`OPEN --
RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE REMAINS`) is completely
untouched, exactly as the governing brief required. See
`docs/release-execution-state.md` for the reconciled record.

## Preserved files

Confirmed present, untouched, and byte-identical at both the start and the
close of this milestone (`git status --short`, both times, matched
exactly):

- `docs/wildlife-detector-training-contract.md.orig`
- `scripts/evaluate_small_bird_detector.py`
- `scripts/materialize_wildlife_stage2.py.orig`
- `scripts/train_wildlife_stage2_rfdetr.py.orig`
- `src/mockingbird/detectors/small_bird_benchmark.py`
- `src/mockingbird/training/wildlife.py.orig`
- `tests/test_small_bird_benchmark.py`
