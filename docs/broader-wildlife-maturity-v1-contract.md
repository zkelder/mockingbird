# Broader Wildlife Maturity v1

Closes bird-specific assumptions in the end-to-end observatory loop --
Source -> activity -> animal presence -> localization/tracking -> Visit ->
evidence -> classification/suggestion -> interpretation -> review ->
Observation -> Today/history/Place intelligence -> export -- so it behaves
credibly for ordinary non-bird wildlife (squirrel, rabbit, deer, raccoon,
opossum, fox, domestic/feral cat), with birds retained as the regression
control. This is not a mandate to train a new detector, and not permission
to lower truth standards for mammals: human-reviewed truth remains
authoritative throughout.

## Phase 1 -- Archaeology headline

MockingBird's core architecture is **already deliberately taxon-generic** --
this predates this milestone and is not an accident:

- `src/mockingbird/wildlife_taxonomy.py` -- `is_wildlife_category` is a
  **denylist** (`{pet, person, vehicle, object, false_positive, unknown}`),
  not a bird/mammal allowlist. A brand-new wildlife category is wildlife
  automatically, with zero caller changes. Its own docstring already states
  the product is "bird-first but wildlife-native."
- `api/schemas.py:381-389` `LabelCategory` already has `mammal` as a
  first-class member alongside `bird`.
- The production detector (MegaDetector v5 ONNX,
  `detectors/megadetector_adapter.py:55`) has only ever output generic
  `animal`/`person`/`vehicle`/`unknown_animal` -- it has never been
  bird-specific, and never claims species.
- The custom wildlife-detector training pipeline
  (`training/wildlife.py:815,867`) deliberately trains one generic `animal`
  class; taxon is metadata only, never a class label -- and its real
  Stage-2 training sources already span squirrels, chipmunks, deer,
  opossums, rabbits, foxes, raccoons, cats, coyotes, and bobcats
  (`training/wildlife_source_registry_v0_2.json:86`; none of that imagery
  is wired into product tests -- see Phase 3).
- Admission/candidate-quality/multi-subject Visit assembly
  (`observation/candidate_visit_authority.py`, `candidate_quality_gate.py`,
  `visit_episode_assembler.py`, `scene_confusor.py`) never reads a
  species/bird literal anywhere -- confirmed by direct grep, not just docs.
  Simultaneous-subject disambiguation is geometry/overlap based, not
  species based, and already keeps two overlapping animals (mammal+mammal,
  mammal+bird) structurally separate.
- The review/correction write path (`api/schemas.py`'s `label` fields,
  `product_repository._normalize_label_from_session`) is free text
  end-to-end; the real picker (`web/src/components/TaxonomyLabelInput.tsx`)
  already mixes `unknown_animal`/`squirrel` with birds and accepts any
  custom label. No backend or frontend structural block exists on
  submitting a correct non-bird taxon.
- Research/export (`research/eligibility.py`, `research/camtrap_dp.py`,
  `research/conservation_report.py`) resolve taxon identity generically
  from the reviewed `TaxonomyLabel` row; none contain a `"bird"` literal.
  `demo_data.py` already ships one reviewed mammal record
  (`visit-squirrel-ground-001`) proving this path works today.

Given that, the real gaps are narrower and cluster around a few concrete
root causes, not a systemic bird-only design. Severities below reflect
direct code verification, not just the initial fan-out read (two claims
from the initial pass were downgraded after deeper reading -- see "Findings
investigated and closed without a code change").

### P0 -- would produce actively wrong or lost non-bird truth

1. **Evidence scoring hard-rejects any subject box touching a frame edge**,
   with no size carve-out --
   [`observation/evidence_scoring.py:250,107-110,347`](../src/mockingbird/observation/evidence_scoring.py).
   `subject_edge_clipped` sits in `_HARD_REJECTIONS`; a candidate with
   `min(box) <= 0.01` or `box[2]/box[3] >= 0.99` is **structurally
   ineligible** for `identification`/`context` selection, not merely
   penalized (the existing -30 containment score never gets a chance to
   compete). Calibrated for a small bird fully inside a wide feeder scene.
   A deer/raccoon/fox at ordinary camera-trap range routinely fills or
   exceeds the frame -- edge contact is the *normal* framing reality for a
   large, close animal, not a sign of a bad detection. If every retained
   frame of a real encounter is edge-touching, `identification`/`context`
   both resolve `None` (`no_useful_evidence`) and the encounter can be
   silently starved of admissible evidence and never surface as reviewable
   Visit content -- a zero-recall failure for exactly the "larger subject"
   scenario this milestone targets. Fixed below.
2. **Non-bird mammal taxonomy content gap cascades into real protection
   loss.** `api/demo_data.py:201-448` seeds 14 bird species plus exactly
   one non-bird entry (`squirrel`, kind-level). No taxonomy row exists at
   all for deer/raccoon/opossum/fox/rabbit. This is not just an
   autocomplete inconvenience: `product_repository._storage_visit_is_
   wildlife` (`:18170-18190`) first tries to match a reviewed label against
   a real `TaxonomyLabelModel` row and, when found, correctly applies the
   generic wildlife denylist -- but when **no row exists** (true today for
   a freeform "deer"/"raccoon"/... correction), it falls back to a literal
   `{"bird", "unknown_bird", "wildlife"}` set that does not include them.
   A confirmed deer/raccoon/opossum/fox/rabbit Visit today is **not**
   protected by "keep reviewed wildlife evidence" retention the way a
   confirmed bird or squirrel is, and instead ages out on the shorter
   "reviewed other evidence" schedule (default as low as 30 days) alongside
   blank/ambiguous junk -- real risk of silently deleting the evidence
   behind a correctly-reviewed mammal encounter. Root cause is a taxonomy
   **content** gap (already self-diagnosed this way, for a different
   symptom, in `docs/canonical-new-regular-species-contract.md:122-137`);
   fixed below by adding the missing rows, which activates the *already
   correct* generic logic -- no logic change needed.
3. **Species identification (BioCLIP) is structurally closed to bird
   species only, with no taxon-scope signal available before it runs** --
   see "Identification maturity" below for the full investigation and the
   deliberately conservative conclusion (no new heuristic, no new model;
   documented + tested, not silently patched over).

### P1 -- non-bird use incomplete or awkward, not wrong

- Absolute geometry-gap/occlusion-timing constants in Visit assembly
  (`visit_episode_assembler.py:396-402` gap tolerance/size-change ratio,
  `frame_tracker.py:64` `maximum_unsupported_detector_ms=5000`,
  `scene_confusor.py:92,142` `min_occurrences_to_suspect`/`geometry_spread_
  ceiling`) were derived and field-validated exclusively against small-bird
  feeder sessions. Structurally taxon-agnostic (ratio/relative math, not
  species-keyed), but untested at mammal scale/dwell-time -- plausible
  fragmentation (occlusion outlasting the merge window) or, for a mammal
  that reuses one exact physical feature (a den, a porch chair) with less
  pose-driven position spread than a hopping bird, false scene-confusor
  suppression. The `reviewed_real` permanent-protection escape is a real
  backstop once a human reviews once, so this is recall risk, not
  corrupted truth. No real mammal-scale fixtures existed anywhere in the
  suite to prove or disprove this either way (confirmed by grep across
  `tests/test_visit_episode_assembler.py`, `test_scene_confusor.py`,
  `test_frame_tracker.py`, `tests/fixtures/observation_stage*/` -- zero
  non-`"animal"`-generic scenarios). Addressed via new structural fixtures
  in Phase 6/7, not a numeric-constant change (no real evidence yet
  justifies picking new numbers).
- Fast Review has a one-key "Unknown bird" action
  (`web/src/pages/ReviewQueuePage.tsx:4529-4536`, shortcut `K`) with no
  sibling for "Unknown animal" -- reachable only by dropping into the text
  picker. Fixed below.
- `"Added to Bird Log. Correction saved as local dataset truth."`
  (`ReviewQueuePage.tsx:2478`) fires unconditionally, including for a
  squirrel correction or a `false_positive` mark. Fixed below.
- `ManualImportPage.tsx:58,657` / `FolderImportPage.tsx:56,287` pre-fill
  (not placeholder -- a real submitted value if untouched) the initial
  subject label with literal `"unknown_bird"` for arbitrary imported media.
  Fixed below.
- `web/src/components/BiodiversitySummaryCard.tsx:67-69` headlines
  `"Species known here"` from `distinct_species_count` alone, with no
  fallback to `distinct_taxa_count` the way `TodayReportPanel.tsx:232-243`
  and `PlaceActivityReportPage.tsx:717-720` already do -- self-contradicts
  the same card's own taxa-name lists just below it (a confirmed squirrel
  is named in "Regular visitors" but not counted in the headline). Fixed
  below.
- `web/src/components/DatasetCoveragePanel.tsx:76-77,106-108` headlines
  "Unknown birds needing review" and never surfaces the sibling
  `unknown_animal_count` field it already receives, unlike
  `AnalyticsPage.tsx:124-125` which correctly pairs both. Fixed below.
- `web/src/pages/ExportsPage.tsx:324-325,382-383` "Unknown bird records"
  metric/badge checks only `label === "unknown_bird"`, no equivalent for
  `unknown_animal`. Fixed below.
- No real or fixture non-bird-mammal test coverage exists beyond
  "squirrel" (kind-level, always a synthetic string label, never real
  pixels, reused across ~20 files). Rabbit, coyote, bobcat, deer, fox,
  chipmunk, and opossum have **zero** committed test presence. Real
  species-tagged camera-trap imagery for exactly these species already
  sits locally under `data/training/wildlife-stage{1,2}/` but is
  `.gitignore`d, unwired to any test, and was collected to train a
  single-class localization detector, not to validate product behavior.
  Closed in Phase 3/6/7/11 via a bounded representative cohort.
- Research/export test suite (`tests/test_research_export.py`,
  `test_camtrap_dp.py`, `test_conservation_report.py`, etc.) is
  bird-fixture-only even though the code under test is already
  taxon-generic (confirmed directly) -- a real regression blind spot, plus
  two test-only fixture helpers that hardcode bird identity with no
  override (`test_camtrap_dp.py:33-81`'s `_observation()` derives
  `category="bird"` from *whether a label was passed at all*, not from a
  real category -- would silently build an internally-inconsistent
  "mammal labeled bird" fixture today). Closed in Phase 10.

### P2 -- later / cosmetic, not acted on this milestone

- Retention setting names (`retain_reviewed_bird_wildlife_evidence`,
  `reviewed_non_bird_age_days`) are misleadingly bird-flavored given the
  underlying logic is already taxon-generic (finding #2 above fixes the
  *content* gap that made this visible; the names themselves are cosmetic
  and a rename is unnecessary churn per this milestone's own scope
  boundary).
- `VisitReviewOutcome.confirmed_bird`/`non_bird` naming
  (`api/schemas.py:234,238`) is a latent trap for future code that treats
  `confirmed_bird` as "is this confirmed wildlife" -- every current
  consumer already compensates correctly (verified directly), so this is a
  naming hazard, not a live bug.
- Assorted placeholder/guidance copy that mentions only `unknown_bird`
  omitting `unknown_animal` (`VisitDetailPage.tsx:1511,1684,1542`,
  `ReviewQueuePage.tsx:3602`); a badge fallback defaulting to
  `"unknown_bird"` (`VisitDetailPage.tsx:1315`) when no guess exists at all
  (the adjacent primary text is already correct).
- Species-suggestion **configuration** tooling (`StreamDetailPage.tsx:2512`,
  `SpeciesSuggestionsPage.tsx`, `DetectionProposalsPage.tsx:99-104`,
  `ClassifierManifestPage.tsx`) is scoped to "bird taxonomy" -- investigated
  and confirmed **honest, not a gap**: BioCLIP's candidate pack really is
  bird-species-only by design (see "Identification maturity" below), so
  this copy accurately reflects real capability rather than
  under-selling it.
- `SpeciesCoverageCard.tsx` is entirely bird-scoped but has zero import
  sites anywhere in the app today (dead code) -- noted, not wired up, so
  not acted on.
- Audio review cards are titled "Bird heard" unconditionally
  (`ReviewQueuePage.tsx:97`) -- accurate today because the only acoustic
  classifier is BirdNET (bird-only); forward-looking only, no live defect.
- `glossary.md` has no dedicated entry for taxon-rank vocabulary
  (`LabelCategory`/kind vs. species) -- a documentation nit, not a product
  defect.

### Findings investigated and closed without a code change

Two claims from the initial fan-out read did not survive direct
verification, and are recorded here so they are not silently
rediscovered:

- **Dashboard "New Today"/"Recent Regulars" panels
  (`product_repository._dashboard_today_is_confirmed_species`,
  `:16805-16829`) requiring `taxonomy.is_species == True`.** Initially
  flagged as a bird-only exclusion. Direct reading shows the gate already
  went through a real bird-only -> wildlife-inclusive fix (its own comment
  names this: "previously bird-only, one of the two disagreeing
  New/Regular implementations the contract closes") and today requires
  species-level truth **uniformly** -- the generic `"bird"` kind-level
  taxonomy row (`is_species=False`) is excluded by the identical rule a
  kind-level `"squirrel"` row is. `docs/canonical-new-regular-species-
  contract.md`'s own "known, separate, currently-latent gap" section
  already names this precisely as "a taxonomy-content gap, not a logic
  gap." Requiring species-level truth for a "New/Regular *species*" badge
  is the doctrinally correct behavior (see Phase 4's "Preserve hierarchy":
  a kind-level "mammal" identification is not automatically species
  evidence) -- the canonical, more-visible surfaces (`historical_baseline.
  compute_species_historical_statuses`, feeding Today's digest, Bird Log,
  and the Biodiversity card) already track kind-level new/regular status
  correctly with no `is_species` gate. No change made.
- **The BioCLIP-2.5 case scoring 99.75%/96% margin on a real no-bird
  photo**, cited as proof the forced-choice failure mode is live. Direct
  reading of `docs/detection-species-model-benchmark-promotion-v1-
  report.md:352-367` shows this was the **shelved, not-promoted**
  BioCLIP-2.5 candidate, explicitly rejected for exactly this
  under-calibration. The **production** BioCLIP-2's worst known real wrong
  full-frame answer topped out at 0.817 -- "comfortably separated" from
  where a genuine positive lands, and safely below the shipped 0.85
  full-frame floor. Further, production's own historical hard-negative
  validation cohort includes one real photo of an actual non-bird animal
  (a dog, Visits 139/140) and it correctly abstained (score 0.53-0.60,
  below both floors). This materially de-risks (without eliminating) the
  concern -- see "Identification maturity."

## Phase 2 -- The broader-wildlife contract for v1

**1. Taxon truth.** Four durable states, all already representable without
schema change: broad animal class (detector's generic `animal`), taxon/
species suggestion (BioCLIP, bird-scoped only -- see below), reviewed taxon
truth (any string, resolved against `TaxonomyLabel` when one exists),
unresolved/unknown animal (`unknown_bird`/`unknown_animal`/`ambiguous`,
tracked as their own honest "confirmed but species-unresolved" concept via
`is_wildlife_category`'s deliberate exclusion of `LabelCategory.unknown`
plus `place_activity_report`'s `confirmed_species_unresolved_visit_count`
-- verified correct, not a gap). A detector class is never treated as
species evidence anywhere in the admission/evidence path (verified).

**2. Product language.** Fixing the concrete instances found above
(toast, Fast Review parity, import defaults, two undercount panels). Not
a rename of `BirdLogPage`/`bird-log` route/`getBirdNetStatus` and similar
internal identifiers -- those are internal naming that render taxon-correct
copy already (verified per-file), and renaming them is unnecessary churn
this milestone explicitly avoids.

**3. Visit/evidence.** One architecture for all taxa (already true -- no
"mammal Visit" concept exists or is introduced). The one real size-driven
defect (edge-clip hard rejection) is fixed narrowly: large subjects get
graded, not excluded; the existing bird-scale behavior (small/typical
clipped subjects still hard-rejected) is untouched and covered by a
regression test.

**4. Identification.** BioCLIP's candidate-pack mechanism is validated and
tested to require bird-species membership
(`product_repository._validated_species_candidate_pack_members:8715-8719`,
`ValueError("candidate_pack_members_must_be_bird_species")`) -- this is a
deliberate, tested product boundary, not an oversight, and this milestone
does not remove it (doing so risks fabricating unvalidated mammal-species
identities, exactly what the milestone forbids). No live BioCLIP model
runtime or real non-bird evaluation imagery is available in this
environment (checked directly: no `BIOCLIP_MODEL_PATH`/embedding cache
present; the two local evaluation reports that looked promising on first
read contain only bird/blank/person-dog cases, no real mammal case, on
direct inspection). Building a new taxon-scope heuristic without any way
to validate it against real evidence would itself violate "do not lower
truth standards" and risks becoming the kind of new-classifier project
this milestone explicitly excludes. The contract for v1 is therefore:
identification stays honestly scoped to birds (already transparently
disclosed in review UI: `"Compared against {N} species from {display_name}
v{version}"`); non-bird Visits either receive a wrong bird suggestion that
a human is fully equipped to correct (verified: no structural block
anywhere in the correction path) or -- per the one real non-bird hard
negative in the validation history -- correctly abstain. New structural
regression tests are added (Phase 5) to keep the abstention gate honest;
no new model, no new heuristic gate.

**5. Place intelligence.** Reviewed non-bird wildlife already flows
correctly through Today/Biodiversity/history (verified directly in code,
not just docs, across `place_activity_report.py`, `historical_baseline.py`,
`daily_digest.py`, `place_biodiversity_summary.py`). Zone & Feeder Insights
is the one surface that is genuinely, deliberately bird-only by product
design (`docs/zone-feeder-insights-metrics.md`: "confirmed **bird** Visit,"
"confirmed **bird** species") -- and it already labels itself as such in
its own UI heading ("Compare confirmed bird Visits..."). Per this
milestone's own instruction to "label and isolate" an intentionally
bird-specific surface rather than silently mixing semantics, this is left
alone and documented as such, not treated as a defect.

**6. Export.** Already taxon-generic in the code that matters
(`research/eligibility.py`, `camtrap_dp.py`, `conservation_report.py` --
verified, zero `"bird"` literals). The gap is test-coverage-only (Phase
10), not a production defect.

**Cat is a deliberate case, not a defect.** `LabelCategory.pet` (covering
`cat`/`dog`) is intentionally excluded from `is_wildlife_category` by
product design -- `wildlife_taxonomy.py`'s own docstring uses cat/dog as
its canonical "a real animal, but not wildlife activity at this Place"
example. This milestone validates that a cat encounter flows correctly
through detection -> Visit -> evidence -> review (it does -- `pet` is a
first-class `LabelCategory` used throughout) and is honestly, consistently
excluded from "confirmed wildlife" Biodiversity/species-richness
aggregates -- not "fixed" into counting as wildlife.

## Phase 3 -- Representative acceptance cohort

| Cohort member | Morphology/behavior slot | Taxonomy status after this milestone | Fixture basis |
|---|---|---|---|
| Squirrel | Small mammal (existing) | Kind-level, already seeded | Existing demo record + new synthetic fixtures |
| Rabbit | Small mammal | Kind-level, **newly seeded** | New synthetic fixtures |
| Deer | Large mammal | Kind-level, **newly seeded** | New synthetic fixtures |
| Raccoon | Medium mammal, nocturnal | Kind-level, **newly seeded** | New synthetic fixtures |
| Opossum | Medium mammal, nocturnal | Kind-level, **newly seeded** | New synthetic fixtures |
| Fox | Medium mammal | Kind-level, **newly seeded** | New synthetic fixtures |
| Domestic/feral cat | Domestic animal (deliberately non-wildlife) | Unchanged (`pet`) | Existing seed row |
| Bird (multiple species) | Regression control | Unchanged | Existing extensive coverage |

Multi-subject case: two deer (same taxon) and squirrel+bird (cross-taxon)
sharing an encounter window, exercised against the existing multi-subject
Visit assembly (Phase 6) -- no new "mammal Visit" path.

Insect/arthropod: **explicitly deferred**, per this milestone's own
allowance. Archaeology found no real, honest basis for even a broad-class
insect capability today -- `"insect"` appears exactly once anywhere in
`src/mockingbird`/`tests`, as one of five *hypothetical future category*
strings in a parametrized taxonomy test
(`tests/test_wildlife_taxonomy.py:24`), with zero detector, evidence, or
review-path exercise of any kind. Fabricating cohort inclusion here would
mean fabricating support that does not exist; deferred honestly instead.

Real local footage is insufficient for any cohort member except birds (no
real MockingBird-camera mammal photos exist in this repository or
environment). Per this milestone's own instruction, acceptance uses
deterministic synthetic/structural fixtures -- built in the same JSON
scenario shape already established by `tests/fixtures/observation_stage*/`
-- for structural Visit-assembly/evidence/review/Today/export journeys, and
the real (gitignored, locally-present) `data/training/wildlife-stage{1,2}/`
camera-trap imagery is used only where a real decoded image is genuinely
useful (e.g., proving evidence-scoring/crop-selection code paths against
real pixels), never as a claim of validated species-level identification
accuracy (identification is not being benchmarked on new imagery this
milestone -- see the identification contract above).
