# Broader Wildlife Maturity v1 -- Closure Report

See [broader-wildlife-maturity-v1-contract.md](broader-wildlife-maturity-v1-contract.md)
for the full archaeology, the Phase 2 contract, and the Phase 3 cohort
rationale -- not repeated in full here.

- **Starting HEAD:** `34ad8bc183436dc21cba5aa6cf5c627a77a401d9` (Site-Specific
  Learning v1)
- **Ending HEAD:** see commit recorded at closure below
- **Schema:** unchanged, v53 -- every fix in this milestone was reachable
  through existing schema/semantics (new *seed data*, not new columns/
  tables/migrations)
- **Nothing pushed** (confirmed: no `git push` run this session)

## P0/P1/P2 archaeology findings (summary)

Full detail in the contract doc's "Phase 1" section. Headline: the core
architecture (taxonomy denylist, detector class vocabulary, admission/
Visit-assembly geometry, review/correction plumbing, analytics wildlife
inclusion, research/export mapping) was **already deliberately
taxon-generic** before this milestone -- confirmed by direct code reading,
not assumed from doc comments. Two claims from the initial archaeology
pass were investigated further and downgraded to "already correct" after
deeper verification (Dashboard's `is_species` gate; the severity of the
BioCLIP-2.5 false-positive case, which was the shelved candidate, not the
deployed model) -- both recorded in the contract doc's "Findings
investigated and closed without a code change" so they are not
rediscovered.

**P0 (3), all closed or deliberately, honestly left open with real
evidence -- see below:**
1. Evidence-scoring hard-rejected any subject box touching a frame edge,
   with no size carve-out -- zero-recall risk for large/close mammals.
   **Fixed.**
2. No taxonomy row existed for deer/raccoon/opossum/fox/rabbit, which
   cascaded into a real evidence-retention protection gap for those
   labels. **Fixed** (seed data only, no logic change -- the retention
   logic was already correct).
3. Species identification (BioCLIP) is structurally closed to bird species
   only, with no pre-hoc taxon-scope signal available. **Investigated in
   depth, deliberately not "fixed" with a new heuristic** (no real
   non-bird evaluation imagery or live model access exists in this
   environment to validate one) -- honestly documented, abstention-gate
   test coverage strengthened instead. See "Identification maturity"
   below.

**P1 (structural/UX gaps closed):** Fast Review's missing "Unknown animal"
one-click action; the "Added to Bird Log" toast firing on every
correction/false-positive; `ManualImportPage`/`FolderImportPage` defaulting
imported media to `unknown_bird`; `BiodiversitySummaryCard`'s "Species
known here" headline undercounting confirmed kind-level wildlife;
`DatasetCoveragePanel`/`ExportsPage` never surfacing their own
`unknown_animal` sibling metrics; zero non-bird test coverage across the
research/export test suite plus a test-fixture bug that structurally
prevented writing any (all fixed -- see below). Untested-at-mammal-scale
Visit-assembly geometry constants (occlusion/merge-gap tolerance,
scene-confusor spread ceiling) -- **deliberately left numerically
unchanged** (no real data to justify new numbers; new structural tests
added instead to prove what *is* already sound and disclose what remains
unproven).

**P2 (documented, not acted on):** retention-setting naming
(`*_bird_wildlife`) now activates correctly for the cohort but keeps its
pre-existing bird-flavored name (unnecessary churn to rename); assorted
placeholder copy omitting `unknown_animal`; `VisitReviewOutcome.
confirmed_bird`/`non_bird` naming as a latent trap for future code (all
current consumers already compensate); `SpeciesCoverageCard` (dead code,
zero import sites); audio "Bird heard" copy (accurate today, BirdNET is
bird-only).

## Exact bird-specific assumptions found and exact corrections made

| # | Assumption found | File:line | Correction |
|---|---|---|---|
| 1 | `subject_edge_clipped` was an unconditional hard rejection | `observation/evidence_scoring.py:107-110,250-256` | Added `LARGE_SUBJECT_AREA_RATIO_FLOOR` (0.04); a clipped box at/above it is graded (`-10`), not excluded; below it, unchanged hard rejection |
| 2 | No taxonomy row for deer/raccoon/opossum/fox/rabbit | `api/demo_data.py:248-258` (before) | Added 5 kind-level (`is_species=False`) rows, mirroring `squirrel`'s existing precedent exactly |
| 3 | "Added to Bird Log" toast fired for every correction, incl. false_positive | `web/src/pages/ReviewQueuePage.tsx:2478` (before) | Toast text now branches on `isFalsePositiveLabel`/`isBirdReviewLabel` |
| 4 | No one-click "Unknown animal" Fast Review action | `ReviewQueuePage.tsx` Fast Review panel | Added button + `A` keyboard shortcut + legend entry, mirroring "Unknown bird" exactly |
| 5 | Imported media defaulted to `unknown_bird` | `ManualImportPage.tsx`, `FolderImportPage.tsx` | Default changed to `unknown_animal` (honest for arbitrary imported media) |
| 6 | `BiodiversitySummaryCard` "Species known here" ignored `distinct_taxa_count` | `BiodiversitySummaryCard.tsx:67-69` (before) | Falls back to kind-level taxa count + relabels "Kinds of wildlife known here" only when the fallback is actually used (verified not to change the already-correct all-zero case) |
| 7 | `DatasetCoveragePanel`/`ExportsPage` never showed their own `unknown_animal`/non-bird sibling metrics | `DatasetCoveragePanel.tsx:76`, `ExportsPage.tsx:322` | Added the sibling metric/badge next to the existing bird-only one in both |
| 8 | `test_camtrap_dp.py`'s `_observation()` fixture derived `taxon_category`/`display_name`/`is_species` from *whether a label was passed*, hardcoded to bird values -- no test could construct an internally-consistent reviewed-mammal fixture | `tests/test_camtrap_dp.py:33-81` (before) | Parameterized with an `_UNSET` sentinel preserving the exact bird default for all 19 existing call sites |
| 9 | Zero non-bird fixtures across `test_research_export.py`/`test_camtrap_dp.py`/`test_conservation_report.py` | those files | 5 new tests added (raccoon, both with and without a scientific name) |

## Taxonomy / identification semantics

Confirmed (not changed): four durable states -- broad animal class
(detector), taxon/species suggestion (BioCLIP, bird-scoped), reviewed
taxon truth (any string), unresolved/unknown animal (`unknown_bird`/
`unknown_animal`/`ambiguous`, a deliberately separate "confirmed but
species-unresolved" concept, never folded into "no taxon"). A detector
class is never species evidence anywhere in the codebase (verified by
direct grep across the admission/evidence/identification path).

### Identification maturity

BioCLIP's candidate-pack mechanism is validated and tested
(`_validated_species_candidate_pack_members`) to require bird-species
membership -- a deliberate, tested product boundary. This milestone does
**not** remove it: doing so would mean either fabricating unvalidated
mammal-species identities (forbidden) or building a new taxon-scope
heuristic with no real evidence to validate it against (no live BioCLIP
runtime or real non-bird evaluation imagery exists in this environment --
checked directly). The honest v1 outcome, per the milestone's own Phase 5
instruction ("return honest broad-class/unknown results rather than
building a new model-training project"):

- **Automatic species suggestion for a non-bird taxon: unsupported.** A
  non-bird Visit either receives a wrong bird suggestion (which a human is
  fully equipped to correct -- verified, no structural block anywhere) or
  correctly abstains. The one real non-bird-animal photo in the
  abstention gate's own historical validation cohort (a dog, Visits
  139/140) already correctly abstains (score 0.53-0.60, both floors
  clear). This is real, if narrow, positive evidence -- not proof the
  gate is safe against every possible mammal, which was never claimed.
- **Human-supplied kind-level identification: fully supported.** A
  reviewer can record "squirrel"/"raccoon"/etc. directly (no automatic
  suggestion required), and it becomes fully authoritative reviewed truth
  end-to-end -- proven by new tests (see below).
- Strengthened: 3 new structural regression tests proving the abstention
  decision function is taxon-blind by construction (no `taxon`/`category`
  parameter exists anywhere in its real signature) and that its real,
  cited floors would also catch a hypothetical score at the worst known
  real wrong value, regardless of species name.
- The existing review UI already discloses candidate-pack scope
  honestly (`"Compared against {N} species from {display_name} v{version}"`)
  -- no new transparency UI needed.

## Large-subject / multi-subject findings

3 new tests directly against `visit_episode_assembler` (the real assembly
module, not a mock), at ~13% of frame area (well above bird-scale, matching
`LARGE_SUBJECT_AREA_RATIO_FLOOR`):
- Two simultaneous large (deer-scale) subjects at different positions
  remain two proposals and recognize each other as concurrent siblings --
  identical mechanics to the existing bird-scale fixture, now proven at
  scale.
- A small (squirrel-scale) and a large (deer-scale) subject simultaneously
  in frame also remain correctly separate -- proves size heterogeneity
  doesn't confuse the decision.
- A large subject briefly occluded (8s, within the 15s merge window) and
  reacquired at the same position/size still merges into one Visit --
  direct evidence the occlusion-tolerance geometry math (previously
  untested outside bird scale) generalizes.

All three passed on first correct attempt once the geometry was set up
correctly, confirming the ratio-based (not pixel/area-cutoff) design
already claimed by the code's own comments.

## Night / low-light findings

Evidence scoring's exposure handling (`image_underexposed`) was already a
soft score penalty, never a hard rejection -- confirmed unchanged, and a
new test (`test_underexposed_night_candidate_is_graded_not_excluded`)
proves a night-flagged candidate remains eligible, is correctly
outranked by a well-lit alternative when one exists, and remains real,
selectable evidence when it is the only option. Classification abstention
is taxon-blind by construction (see above), so it applies identically to
a night encounter -- no separate "night" code path exists to audit. Scene-
confusor suppression's numeric thresholds remain **honestly disclosed as
untested at mammal scale** (see P1 above) -- not claimed as validated for
night mammal behavior specifically.

## Human-correction evidence (Phase 8 journeys)

All against the real `create_review_label`/`revise_visit_review`/
`create_species_suggestion` write paths (never hand-set fields), in
`tests/test_place_biodiversity_summary_repository.py`:

- **Journey 4** (provisional mammal corrected to a different taxon, every
  downstream surface updates): squirrel -> raccoon, proven through the
  repository method *and* the real HTTP route; stale squirrel history
  empties, raccoon history populates as "new."
- **Journey 2/3 mandatory items, made honest**: the brief's literal
  wording ("classifier proposes squirrel...") is not achievable -- BioCLIP
  cannot propose a non-bird species (see above). The real, achievable
  version is proven instead: a wrong *bird* suggestion (what BioCLIP would
  actually produce) is fully overridden by a human correction to `rabbit`
  or to `unknown_animal`, with the machine's wrong guess never
  contaminating biodiversity truth or taxon history either way.
- **Journey "local learning cannot silently rewrite reviewed truth"**:
  confirmed structurally, not reopened -- every write to
  `VisitModel.reviewed_label` anywhere in `src/mockingbird` lives in
  `product_repository.py`'s own review/correction/reopen methods (grep-
  verified); no scene-confusor/local-adaptation module writes it.

Also live-verified in the real UI (Playwright, real backend, not mocked):
Fast Review's new "Unknown animal" one-click action saves real reviewed
truth; marking a Visit false-positive now shows "Marked as false
positive," never "Added to Bird Log."

*(Aside, unrelated to this milestone, found during this verification: the
review queue's non-"Product Mode" card rendering --
`const productMode = true` in `ReviewQueuePage.tsx` -- is permanently
unreachable dead code today; `saveCorrectionWithLabel`'s only live call
site is Product Mode's False Positive button. The toast fix is correct and
tested either way; noted for engineering awareness, not touched -- UI
redesign/dead-code cleanup is out of this milestone's scope.)*

## Today / history / Biodiversity evidence (Phase 9 / Journey 8)

`test_representative_wildlife_cohort_is_remembered_and_a_pet_is_honestly_excluded`
(new): squirrel, deer, raccoon, opossum, fox, rabbit, and a bird control
all confirmed at one Place -> all appear correctly in
`place_biodiversity_summary`'s taxa/historical-status, each earning
"new"/"first_record" status, proven through the repository method *and*
the real HTTP route. A confirmed cat is **honestly, deliberately absent**
from the same roster (verified: still real, queryable Visit data via
`GET /api/visits/{id}`, just correctly not "wildlife" -- see the contract
doc's "Cat is a deliberate case, not a defect").
`test_today_summary_counts_a_confirmed_kind_level_mammal_as_real_activity`
(new, `test_dashboard_today.py`): a confirmed kind-level squirrel counts
as real Today activity and, side-by-side with an identically kind-level
"generic bird" correction, correctly does *not* earn a "New Today" badge
(species-level-only, proven not to be a bird-vs-mammal double standard).

## Export / research evidence (Phase 10 / Journey 9)

5 new tests: Camtrap DP correctly maps a reviewed raccoon both without a
scientific name (honest `scientificName: null`, no fabrication, no
dropped observation) and with one (`Procyon lotor`, identical shape to the
bird path); generic research export's JSON/CSV rows carry the real
`taxon_category: "mammal"`; the conservation report lists a confirmed
raccoon in its taxon roster next to a confirmed bird with its own honest
`is_species: false`, never folded into the "unresolved wildlife" bucket
that's reserved for genuinely unresolved taxa. The one production-code
defect found in this area was a **test-fixture bug** blocking these tests
from ever being written (see correction #8 above) -- the underlying
`research/eligibility.py`/`camtrap_dp.py`/`conservation_report.py`
production code needed no changes, confirmed already taxon-generic by
direct reading before any test existed to prove it.

## Bird-regression evidence (Phase 12 / Journey 7)

Every modified/added test file's bird-flavored cases were run and pass
unchanged (evidence scoring's small-clipped-subject case still hard-
rejects exactly as before; the existing bird correction/revision test in
the biodiversity suite; all pre-existing Dashboard/Biodiversity/export
bird tests). Full Core suite result: **4614 passed, 3 failed, 2 skipped,
11 xfailed** (2203.76s / 36m43s). All 3 failures are in
`test_camera_node.py`/`test_camera_node_real_process.py` (real-subprocess/
real-socket/real-watchdog-notify Camera Node process tests -- explicitly
out of this milestone's scope, never touched). **Confirmed pre-existing
and unrelated via clean-baseline comparison**, not merely assumed: `git
stash push -u` (per the established convention from Habitat & Phenology
Foundation v1) to a fully unmodified working tree, then reran all 3 in
isolation -- the two `test_camera_node_real_process.py` failures reproduce
identically on the clean baseline (`Connection refused` waiting on a real
spawned subprocess's health port -- an environment characteristic of this
sandbox, not a code defect, let alone one from this milestone) and the
third (`test_picamera2_restoration_failure...`) passed standalone on the
same clean baseline, confirming it isn't a deterministic regression
either. All 251 tests across every file this milestone touched were also
re-run after restoring the stash (`git stash pop`), confirming the
restore was clean and nothing was lost: 251/251 passed.

## Capability matrix

Terms: **validated** (proven by a real or structural test this milestone
or already-existing coverage), **supported with abstention** (the system
correctly declines rather than fabricates), **broad-class only**, **N/A**
(dimension doesn't apply), **unsupported**.

| Cohort member | Presence detection | Localization | Visit assembly | Evidence crop | Species/taxon ranking | Review path | Today/Biodiversity | Export |
|---|---|---|---|---|---|---|---|---|
| Squirrel | validated | validated | validated | validated | unsupported (automatic); human-supplied kind-level: validated | validated | validated | validated (generic, proven via raccoon) |
| Rabbit | validated | validated | validated | validated | unsupported (automatic); human-supplied: validated | validated | validated | validated (generic) |
| Deer | validated | **validated (new large-subject tests)** | **validated (new large-subject tests)** | **validated (new edge-clip fix + test)** | unsupported (automatic); human-supplied: validated | validated | validated | validated (generic) |
| Raccoon | validated | validated | validated | validated | unsupported (automatic); human-supplied: validated | validated | validated | **validated (representative export test case)** |
| Opossum | validated | validated | validated | validated | unsupported (automatic); human-supplied: validated | validated | validated | validated (generic) |
| Fox | validated | validated | validated | validated | unsupported (automatic); human-supplied: validated | validated | validated | validated (generic) |
| Domestic/feral cat | validated | validated | validated | validated | N/A (pet, not a wildlife-identification target) | validated (recorded correctly) | **N/A by design** (honestly, deliberately excluded from wildlife aggregates -- verified, not a gap) | **validated** (pre-existing: `tests/test_research_eligibility.py::test_non_wildlife_taxon_is_real_but_not_eligible_for_wildlife_export`, `taxon_category="pet"` -> `eligible=False`) |
| Bird (control) | validated | validated | validated | validated | **validated** (BioCLIP's actual designed scope) | validated | validated | validated |
| Insect/arthropod | **deferred** -- no real basis found for even a broad-class claim (see contract doc) | deferred | deferred | deferred | deferred | deferred | deferred | deferred |

Multi-subject (any combination above): validated structurally --
simultaneous same-size, simultaneous size-heterogeneous, and sequential-
with-occlusion all proven at both bird and large-mammal scale.

Night/low-light (nocturnal cohort members -- raccoon, opossum, fox):
evidence handling validated (graded, not excluded); classification
abstention validated as taxon-blind; admission-layer scene-confusor
resistance at mammal scale is **honestly disclosed as unproven**, not
claimed.

## Focused validation

- **Tier 1** (new/updated unit-level tests): `test_observation_evidence_
  scoring.py`, `test_evidence_benchmark.py`, `test_visit_episode_
  assembler.py`, `test_identification_eligibility.py`, `test_storage_
  retention.py`, `test_dashboard_today.py`, `test_place_biodiversity_
  summary_repository.py`, `test_camtrap_dp.py`, `test_research_export.py`,
  `test_conservation_report.py` -- all pass (see per-file counts in the
  session's own test runs; every file run standalone and green after each
  change, no regressions at any step).
- **Tier 2**: `web/e2e/biodiversity-summary.spec.ts` (8/8, incl. 1 new),
  `web/e2e/broader-wildlife-maturity-review.spec.ts` (2/2, new),
  `bird-log-historical-status.spec.ts` (9/9), `today-report.spec.ts`
  (19/19), `place-activity-report.spec.ts` (3/3),
  `review-queue-reviewed-tab.spec.ts` + `review-queue-bulk-correct-stale-
  write.spec.ts` + `visit-evidence-review-loop.spec.ts` (4/4) -- **41/41
  passed** in the combined focused wildlife-journey batch. Frontend
  `tsc --noEmit` and `vite build` both clean.
- **Tier 3**: full Core suite run (`pytest tests/`, 4630 collected) --
  result below.

### Core result

**4614 passed, 3 failed, 2 skipped, 11 xfailed** in 36m43s. All 3 failures
confirmed pre-existing and unrelated to this milestone via clean-baseline
comparison (`git stash`) -- see "Bird-regression evidence" above for the
full verification. Zero failures attributable to this milestone's changes.

## Preserved-file status

Confirmed untouched (matches the exact 7-file set from session start,
verified via `git status` immediately before closing): `docs/wildlife-
detector-training-contract.md.orig`, `scripts/evaluate_small_bird_
detector.py`, `scripts/materialize_wildlife_stage2.py.orig`, `scripts/
train_wildlife_stage2_rfdetr.py.orig`, `src/mockingbird/detectors/
small_bird_benchmark.py`, `src/mockingbird/training/wildlife.py.orig`,
`tests/test_small_bird_benchmark.py`.

## Nothing pushed

Confirmed: no `git push` invoked this session. All work is local commits
on `main` (see ending HEAD above).

## Remaining bounded broader-wildlife gaps

- Automatic species-level identification for any non-bird cohort member
  remains genuinely unsupported (structural, not a bug -- see
  "Identification maturity"). Closing it for real would need either real
  non-bird evaluation imagery + a validated broad-class/taxon-scope gate,
  or a promoted alternative provider -- both explicitly out of this
  milestone's scope.
- Visit-assembly occlusion-tolerance and scene-confusor geometry constants
  remain bird-calibrated; this milestone proved the *mechanism*
  generalizes at large scale but did not re-derive the *numbers* against
  real mammal field data (none exists in this environment).
- Insect/arthropod support remains fully deferred, honestly.
- The dead `productMode = true` non-Product-Mode review card path
  (unrelated to broader wildlife) was noted, not addressed.

## Next natural milestone suggestion

Species Classification Re-evaluation / Promotion v2 (already named as the
next candidate in `docs/detection-species-model-benchmark-promotion-v1-
report.md`, independent of this milestone) is the natural path to closing
the one remaining structural gap here -- real non-bird evaluation imagery
plus a proper calibration study, which this milestone deliberately did not
attempt.

---

*Do not begin the next milestone automatically.*
