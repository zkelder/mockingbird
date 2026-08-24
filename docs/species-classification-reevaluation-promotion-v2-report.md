# Species Classification Re-evaluation & Promotion v2 — Report

Date: 2026-08-24. Starting HEAD: `9114f9e09f8eced72239c8beccaeaa5b3179a0bb`
("Broader Wildlife Maturity v1"). Starting schema: 53 (unchanged by this
milestone). This is an evaluation/architecture-decision/calibration/
promotion milestone, explicitly not a detector-training campaign, per the
milestone's own instructions.

## Decision

**RETAIN BASELINE.** BioCLIP-2 (ViT-L/14, closed 14-species "Backyard Core
v1" pack, with the accepted Identification Eligibility + Abstention v1
policy) remains MockingBird's production species identifier. Neither real
candidate clears the predeclared promotion gate (Phase 12, below).

- **BioCLIP 2.5 (ViT-H/14) is explicitly rejected**, not merely
  "not-yet-promoted." The 2026-08-22 session found a calibration concern on
  an 8-case sample; this session built a real, individually visually-verified
  36-case cohort (3× larger, mostly new evidence) and found the concern is
  severe and reproducible: BioCLIP 2.5 is **confidently wrong on 14/19
  (73.7%) of real hard-negative cases**, vs. the incumbent's 1/19 (5.3%). Its
  real top-1 accuracy gain on genuine birds (8/13 vs. incumbent's 5/13) does
  not come close to offsetting a hard-negative safety regression of this
  size, against this milestone's own named most-important release metric
  ("how often does the product confidently tell the user the wrong thing").
- **SpeciesNet v4.0.3a is reconfirmed unsuitable as a primary bird
  identifier** (0/13 correct on MockingBird's real 14-species set — it never
  resolves closer than a generic "bird"), but this session found real,
  positive, previously-untested evidence that its broader taxonomy has
  genuine mammal-species-level capability (correctly named "domestic cat"
  and "virginia opossum" at 0.93-0.96 confidence on clear external camera-
  trap photos) alongside excellent hard-negative safety matching the
  incumbent (18/19 correct abstention on the same real MockingBird hard-
  negative cohort, 0/19 confidently wrong). This is recorded as a genuine,
  unpromoted lead for a future, explicitly-scoped broader-wildlife
  integration milestone — not wired into production this session (see Phase
  9/12 for why).
- **One real P0 defect found during archaeology and fixed**: the species
  identification eligibility/abstention policy (accepted 2026-08-21) was
  silently bypassable via three suggestion-reuse ("Identify again")
  short-circuits that never checked policy version — a suggestion computed
  before the abstention policy existed, or under an older version of it,
  could be served back indefinitely, bypassing every abstention improvement
  made since. Fixed; regression test added; full suite green (below).

---

## Phase 1 — Bounded archaeology

Four parallel research passes (code contract, real-DB/fixture evidence
inventory, truth-boundary/provenance wiring, runtime/platform/licensing),
plus this session's own direct reading of the 2026-08-22 promotion report and
its two real JSON benchmark artifacts, which turned out to already contain
the load-bearing prior evidence for this exact milestone (the report's own
closing section explicitly named "Species Classification Re-evaluation /
Promotion v2" as its recommended next milestone).

### P0 — correctness/blocker findings

1. **Abstention-policy bypass via suggestion reuse** (fixed this session,
   see "Fixes made," below).
2. **The species "adapter framework" is hardcoded to one provider.**
   `identify_review_queue_item` explicitly rejects any `species_classifier`-
   kind adapter other than BioCLIP with `species_classifier_not_supported`;
   `_model_adapters()` is a flat hardcoded tuple, not a registry;
   `automatic_identification.py` hardcodes `adapter_id=BIOCLIP_ADAPTER_ID` in
   the request it builds. This is not a bug (nothing is currently broken by
   it) but it is a real, load-bearing architectural fact for Phase 12/13: a
   second production provider is not a config change, it is new plumbing.
   Not built this session, because no candidate earned it (see Decision).

### P1 — real candidate architectures that actually exist and are runnable here

- **BioCLIP-2** (production incumbent): real, packaged, Windows-validated,
  CPU-only-enforced by config (`bioclip_adapter.py`'s
  `_validate_config_files`), weights cached locally
  (`data/models/bioclip-2/`, 1.6GB).
- **BioCLIP 2.5 (ViT-H/14)**: real code exists only as a benchmark script
  (`scripts/benchmark_bioclip25_candidate.py`); no production adapter module,
  no packaging, no status reporting. Weights cached locally
  (`data/models/bioclip-2.5-vith14/`, 3.7GB) — no re-download needed.
- **SpeciesNet v4.0.3a**: real code exists as a benchmark-only module
  (`src/mockingbird/species/speciesnet_candidate.py`) with a structurally
  enforced import boundary (a test parses its own AST to prove it can never
  import `mockingbird.repository`/`storage`/`api` or any model runtime) —
  confirmed never called by production code. `speciesnet` 5.0.5 and its
  heavy transitive stack (`torch`, `yolov5`, `onnx2torch`, `kagglehub`) are
  installed in `.venv` for research only; **absent from `pyproject.toml`
  entirely** — zero packaging exists. Weights cached locally
  (`~/.cache/kagglehub/.../v4.0.3a/1`, 489MB).
- **Custom backyard classifier**: still does not exist (no trained
  artifact). Confirmed unchanged from 2026-08-22; not evaluated.

All three real, instantiable candidates were actually run this session (not
merely discussed) — see Phase 4-6.

### P2 — minor/future notes

- `BioClipIdentificationAttemptModel.crop_source` is DB-`CHECK`-constrained
  to exactly `megadetector|activity|full_frame`; the finer same-frame/
  native-resolution/persisted-crop distinction only exists in the
  unconstrained `crop_provenance_json` blob. A benchmark or promotion
  analysis reading only the constrained column cannot tell those tiers
  apart.
- BioCLIP's payload builder never populates the schema-43 top-level
  `SpeciesSuggestionModel.model_provenance_json` column for image-backed
  suggestions — full provenance is nested inside `evidence_region_json`
  instead. Not a correctness bug (nothing is lost), but any future tooling
  expecting the top-level column will get `None`. Left alone — out of this
  milestone's scope to reconcile two adapters' provenance storage
  conventions.
- Multi-frame consensus (`evaluate_multi_frame_consensus`) is unwired more
  narrowly than its own docstring claims: the benchmark script the docstring
  names as its real consumer does not actually call it either. Corrected
  understanding only; not acted on (multi-frame consensus stays out of
  scope — Same-Frame Species Evidence v1's single-frame architectural cap is
  unchanged and not this milestone's to revisit).
- `docs/speciesnet-adapter-boundary-plan.md`'s proposed env vars/route shape
  were never implemented; what actually shipped (the `ModelAdapter`/
  `identify_review_queue_item` machinery) is materially different. The plan
  doc is stale design history, not a current contract.

---

## Phase 2 — The classification contract (locked)

The production pipeline already keeps these stages distinct in code (see
Phase 1 P1-2 code map, not repeated here); this milestone changes none of
the stage boundaries, only reconfirms them as the contract to evaluate
against:

1. **Detector/broad animal evidence** — MDv5 proposal (`_credible_
   megadetector_animal_proposal`). Unchanged, out of scope.
2. **Subject localization/evidence selection** — `classifier_input.py`'s
   4-tier resolver (persisted crop → native-resolution box → same-frame
   crop → full-frame fallback), plus two legacy crop_source tiers
   (`megadetector`, `activity`) the production caller also consults before
   ever reaching a true full-frame fallback — 6 real tiers end-to-end, not
   4. Confirmed via code + confirmed the chosen tier is persisted
   (`classifier_input.input_type` / `identification_policy.tier`).
3. **Identification eligibility** — `evaluate_identification_eligibility`
   (32px minimum classifier-input dimension floor). Model-agnostic at the
   pure-function level.
4. **Candidate taxon/species ranking** — closed-set softmax over a fixed
   candidate pack (BioCLIP family) or open-taxonomy ensemble argmax
   (SpeciesNet).
5. **Calibration/confidence interpretation** — `candidate_relative_softmax`,
   explicitly `calibrated=False` everywhere it is structurally recorded (see
   Phase 7).
6. **Abstention** — `evaluate_classification_abstention`
   (`identification-eligibility-v1`, per-tier score/margin floors). Reused
   as-is by the pure scoring math for any closed-set model on the same 0-1
   relative-softmax scale; the *production plumbing* that calls it is
   BioCLIP-specific only (Phase 1 P0-2).
7. **Provisional suggestion** — `SpeciesSuggestionModel(status="pending")`.
   Never created for an abstained result.
8. **Human-reviewed truth** — `ReviewLabelModel`, gated by
   `review_provenance.is_authority_eligible`. See Phase 14.

These eight stages were never collapsed into one opaque "species
confidence" by any candidate evaluated this session, and this milestone
does not collapse them either.

---

## Phase 3 — Candidate architectures evaluated

- **Candidate A — current production stack.** BioCLIP-2, unmodified before
  measurement (confirmed: no config/threshold change was made until *after*
  the promotion-gate decision below, and the only change made anywhere —
  the P0-1 abstention-bypass fix — is a reuse-idempotency correctness fix,
  not a threshold or model change).
- **Candidate B — SpeciesNet.** Evaluated on real MockingBird evidence as a
  primary bird identifier (rejected, unchanged verdict, now on 13 cases
  instead of 5) and, newly this session, as a **candidate generator/
  complementary evidence source specifically for the broader-wildlife
  (mammal) domain** — the role this milestone's Phase 9 asks to be
  considered separately from "does it beat BioCLIP-2 on birds." Real,
  positive signal found (Phase 9); not promoted (Phase 12).
- **Candidate C — BioCLIP 2.5.** The only other genuine existing candidate
  with real artifacts. Evaluated at 3x the prior sample size; the prior
  session's "genuinely strong lead, calibration measurably unresolved"
  finding is now sharpened to "resolved, and it fails."
- **Candidate D — staged architecture.** Not built. The evidence does not
  support it: BioCLIP 2.5's failure mode (confidently wrong exactly where a
  detector-level "there might not be a credible subject here" signal would
  help most) is a genuine, real argument *for* a future staged
  eligibility-then-classifier design, but no viable classifier stage exists
  to stage today (2.5 fails outright; SpeciesNet has no bird capability to
  contribute), so there is nothing to compose. Recorded as a real,
  evidence-backed future direction, not built speculatively.

No ensemble was built, per the milestone's own instruction and because
runtime/packaging cost was never justified by a passing gate.

---

## Phase 4 — The evaluation cohort (built and run for real)

**This is the most consequential finding of the archaeology phase.** The
milestone brief's aspirational cohort (rich, evenly stratified subgroups)
cannot be honestly built from real MockingBird evidence at anywhere near
that scale. Exact, verified counts from the live product database
(`data/mockingbird.sqlite3`, schema 49 — 4 migrations behind the checked-out
code's schema 53; not touched, see caveat below) and every fixture directory
in the repository:

- 235 total Visits; **58 human-reviewed**. Of those: 35 `unknown_bird`
  (no species resolved), 18 `false_positive`, 3 `house_finch`, 1
  `northern_cardinal`, 1 fabricated `squirrel` demo row (`demo://` path,
  zero evidence links, zero `ReviewLabel` audit row — confirmed fake, not
  real evidence).
- **Zero genuine real MockingBird mammal photos exist anywhere in this
  repository or environment** — independently reconfirmed from scratch this
  session (DB sweep + filesystem sweep), and independently corroborated by
  Broader Wildlife Maturity v1's own contract doc, written hours earlier:
  *"no real MockingBird-camera mammal photos exist in this repository or
  environment... Rabbit, coyote, bobcat, deer, fox, chipmunk, and opossum
  have zero committed test presence."*
- Multi-subject Visits: 0 (no `event_id` is ever shared by >1 Visit; the
  diagnostic sibling-candidate column is `NULL` on every row).
- No persisted day/night or geolocation signal exists in this DB (schema
  migration 51, Environmental Context Foundation, has never run against it).

Given this, the cohort actually built and run is the **largest real,
individually visually-verified evaluation ever assembled for this
comparison** — not the aspirational full stratification, but a real,
honest, 3x expansion of the prior session's n=15/23:

**36 cases total, 32 scored** (`scripts/benchmark_species_promotion_v2_
cohort.py`, output at `data/evaluations/species-promotion-v2/unified-cohort-
report.json`):

| Subgroup | n (scored) | Source |
|---|---:|---|
| Ordinary/common birds | 13 | 5 reused from the archived 2026-08-11 cohort (Visits 011-019) + **4 new** real reviewed Visits (230/231/235 house_finch, motion-005 cardinal) from the live DB, a materially different, well-exposed capture session |
| Small/far | 1 (subset of above) | motion-005 cardinal: real, in-flight, motion-blurred, clipped at frame edge — cross-confirmed against `data/benchmarks/small-subject-cohort/manifest.json`'s independent annotation |
| Multi-subject | **0** | Structurally zero in this DB; disclosed, not fabricated |
| Hard negatives | 19 | 2 reused (archived) + **17 new real reviewed `false_positive` Visits**, spanning 3 distinct real scenes (shepherd's-hook static-scene cluster ×6, a second tube-feeder scene ×8, 2 genuine night/IR captures, 1 well-exposed daytime scene) |
| Poor evidence | 9 (subset, tagged) | motion-blur/clipped cardinal + 8 tight `activity_crop` hard negatives |
| Night/low-light | 2 (subset, tagged) | The only genuine night evidence found anywhere in this environment — 2 real reviewed `false_positive` Visits, IR flash artifacts |
| Broader wildlife (squirrel/rabbit/deer/raccoon/opossum/fox/cat) | **0 real** | Genuinely zero; see Phase 9 for the informal external-domain supplement |
| New/open-set | 4 unscored (disclosure only) | 2 archived ambiguous/sliver Visits (011/012) + Visits 139/140 (person+dog) — run and reported, never scored against an assumed ground truth this session cannot independently confirm |

**Data-quality correction made before scoring, not after**: one real
`false_positive` Visit (`visit-motion-015`) was **excluded** from the
hard-negative set after this session's own direct visual inspection (and
independent confirmation from `data/benchmarks/small-subject-cohort/
manifest.json`, written by an earlier session) showed a real bird is
visible in that exact frame — the Visit-level correction was scoped to an
unrelated passing vehicle, not a whole-frame claim. Using it as a clean
negative would have been dishonest; it is listed in the cohort file but
excluded from every tally.

Every case's exact image path, tier, tags, and provenance note is recorded
in the benchmark script itself (`build_cases()`) and the JSON output — not
just asserted in this document.

**Honest limitation, stated plainly**: n=32 scored cases is a real,
meaningful improvement over the prior n=15/23, but it is still a small
sample. Every percentage in this report should be read as "on the largest
real cohort available in this environment," not as a statistically
authoritative population estimate. Where a single scene cluster dominates a
subgroup (6 of 19 hard negatives share one recurring background), that is
disclosed via the `tags`/`provenance` fields, not hidden.

---

## Phase 5 — Input strategy

Every case above was run through the exact evidence representation
MockingBird's real resolver would actually select for it — not idealized
crops. Tiers actually exercised:

- **`subject_focused`** (persisted/native/same-frame crop, or a real
  `activity_crop`): the 5 diagnostic crops, 1 same-frame crop, and 10 of the
  19 hard negatives (2 night `activity_crop`, 8 tight `activity_crop`).
- **`full_frame`** (true uncropped fallback): the 8 archived full-frame
  Visits, all 4 new species Visits, and 9 of the 19 hard negatives.

Findings:

- SpeciesNet's `always_crop` architecture, run consistently in its own
  honest "no external bbox" mode (matching how BioCLIP is evaluated — same
  evidence, same case, both models), calls `blank` on nearly every
  full-frame input regardless of whether a bird is present — reconfirmed,
  unchanged from 2026-08-22. On genuine `subject_focused` crops it commits
  to a specific label far more often but only ever reaches the generic
  `bird`, never a MockingBird-taxonomy species name, on real evidence.
- BioCLIP-2.5's calibration failure is **not confined to `full_frame`** as
  the prior session's smaller sample suggested: 6 of its 14 hard-negative
  failures are on real `subject_focused`/`activity_crop` evidence (the
  *looser* floor, 0.70/0.20 vs. full_frame's 0.85/0.40) — a materially
  different and previously untested finding, since the prior cohort's hard
  negatives were entirely `full_frame`.
- The winning input representation, confirmed again: MockingBird's own real
  resolver output, used as-is. No candidate was benchmarked on artificially
  perfect crops.

---

## Phase 6 — Metrics (the core result)

All three real, cached models were run fresh this session
(`scripts/benchmark_species_promotion_v2_cohort.py`) — not a patchwork of
old JSON. Device: CUDA available in this sandbox for the benchmark run
itself (production BioCLIP-2 is CPU-only *by current config*, see Phase 10);
GPU was used here only to get a fast, reproducible relative comparison, with
real CPU latency cited from the 2026-08-22 session where a same-host
CPU-vs-CPU comparison exists.

| Metric | BioCLIP-2 (incumbent) | BioCLIP 2.5 | SpeciesNet |
|---|---:|---:|---:|
| Positive cases scored | 13 | 13 | 13 |
| Positive correct (top-1) | 5 (38.5%) | **8 (61.5%)** | 0 (0%) |
| Positive confidently wrong | 1 (7.7%) | 3 (23.1%) | 0 (abstained on all 4 misses) |
| Positive abstained | 7 (53.8%) | 2 (15.4%) | 9 (69.2%) |
| Hard-negative cases scored | 19 | 19 | 19 |
| **Hard-negative correct abstention** | **18 (94.7%)** | 5 (26.3%) | **18 (94.7%)** |
| **Hard-negative confidently wrong** | **1 (5.3%)** | **14 (73.7%)** | **0 (0%)** |
| Median inference (this session, CUDA) | 67ms | 80ms | 108ms |
| Real CPU latency (2026-08-22 session, same host) | ~0.70-0.74s/image | ~1.11-1.17s/image | not benchmarked CPU-only |
| Model load time (this session) | 18.5s | 31.7s | 0.7s |
| On-disk weight size | 1.71GB | 3.94GB | 489MB (classifier only) |

**Reading this table honestly**: BioCLIP 2.5 has a real, reproduced,
material top-1 accuracy advantage on genuine birds. It also has a
reproduced, *severe* hard-negative safety regression — nearly 3 out of 4
real empty/false-positive scenes get a confident, specific, wrong bird name
instead of the incumbent's near-universal correct abstention. Per this
milestone's own framing, this is exactly the "slightly lower top-1 but much
better abstention may be the superior product" test, run in the opposite
direction: BioCLIP 2.5 has *higher* top-1 and *much worse* abstention, and
the milestone's own doctrine (`docs/roadmap.md` Gate B: "a sufficiently low
confidently-wrong rate" is a release requirement, not top-1) says that
loses.

A genuinely interesting, disclosed pattern in BioCLIP 2.5's failures: 7 of
its 14 hard-negative misses (the overexposed shepherd's-hook scene cluster)
all say `carolina_chickadee` at 0.94-0.99 confidence; both night-scene
misses say `american_robin` (0.81 and 0.998); the incumbent's own single
miss is the *same* night scene, also `american_robin` (0.91 confidence).
This looks like scene/background pattern-matching rather than genuine
subject-absence detection in both models on this specific real capture —
a real, reproducible, cross-model hard case worth naming for a future
session, not something this milestone's scope extends to fixing (no model
was retrained or fine-tuned).

---

## Phase 7 — Calibration

- **BioCLIP-2 and BioCLIP-2.5 scores remain honestly `calibrated=False`.**
  `BioClipProvenance.calibrated` is hardcoded `False` at every layer,
  including the worker-boundary decoder, which structurally rejects any
  other value. This session did not change that.
- **Is formal calibration (temperature scaling, isotonic, Platt) justified
  by this session's evidence?** No. n=32 scored real cases is too small to
  fit a stable calibration curve without real overfitting risk, per the
  milestone's own instruction ("Do not build a complex learned calibrator
  unless evidence requires it" / "If data is insufficient... preserve score
  semantics honestly... set `calibrated=false`"). This session does exactly
  that: no new calibrator was built for either model.
- **Do the existing empirical thresholds still hold up?** For BioCLIP-2 —
  yes, strongly: 18/19 real hard negatives correctly abstain under the
  existing accepted floors, reconfirming (on 2.4x more real evidence) the
  same policy accepted 2026-08-21. For BioCLIP-2.5 — no: the same floors
  (applied here as an explicit *diagnostic reference only*, per the
  inherited Part E4 rule from the 2026-08-22 report — never a real
  calibration for a different model) let through 73.7% of real hard
  negatives at high confidence. This is not a "threshold needs tuning"
  finding — full-frame scores cluster at 0.94-0.99 for both true and false
  positives, the same saturation problem the prior session diagnosed as
  "likely softmax numerical saturation from a much higher-dimensional
  embedding space," which a simple threshold move cannot reliably fix
  without also losing real positive coverage. Moot for this milestone since
  2.5 is not promoted; recorded honestly as an open question for any future
  revisit, not investigated further (would require real per-model
  calibration study this milestone did not need to justify a decision).
- **SpeciesNet's `blank` mechanism** is a competing class inside its own
  softmax, not a threshold decision — functionally it behaved excellently
  on real evidence (94.7% correct abstention, matching the incumbent) but
  it is not a calibrated probability either, and is not claimed to be one.

No model in production or under evaluation this session is claimed to
output a calibrated probability. This is unchanged, honestly, from every
prior session.

---

## Phase 8 — Abstention/open-set behavior

Tested directly, on real evidence, per the milestone's mandatory list:

| Test case | BioCLIP-2 | BioCLIP 2.5 | SpeciesNet |
|---|---|---|---|
| Empty images (19 real hard negatives) | Abstains 94.7% | Abstains 26.3% | Abstains (`blank`) 94.7% |
| Mammal presented to bird-oriented model (external spot-check, Phase 9) | Abstains (structurally cannot answer) | Not tested (not promoted) | Correctly identifies species (not abstention — genuine capability) |
| Unfamiliar species / open-set (external chickens, Phase 9) | Abstains | Not tested | Correctly abstains (`blank`) |
| Poor crop / tiny subject / blur (motion-005 cardinal, 8 tight-crop poor-evidence hard negatives) | Abstains on the cardinal itself (real limitation, matches known small/far gap); correctly abstains on 8/8 tight-crop poor-evidence hard negatives | Fails 4/8 tight-crop poor-evidence hard negatives | 7/8 correct abstention — 1 miss (`motion-148-crop`: low-confidence generic `"bird"` at 0.313 instead of `blank`, not a specific wrong species claim, but not a clean abstention either) |
| Low light (2 real night hard negatives) | 1/2 correct, 1/2 confidently wrong (`american_robin`) | 0/2 correct, both confidently wrong | 2/2 correct |
| High-confidence wrong historical failure cases (013/014/016/017 full-frame — the documented "RBW-bias" cohort) | Reproduces the known wrong answers this session (unchanged since 2026-08-21 acceptance) | Correctly identifies 3/4 (the real, reproduced improvement) | Calls `blank` on all 4 (safe but non-actionable) |

**No candidate is promoted on the strength of guessing constantly.**
SpeciesNet's high abstention rate (69.2% on positives) is a real, disclosed
cost of its unsuitability as MockingBird's bird identifier, not evidence in
its favor there — it is only evidence in its favor on the *mammal* question
(Phase 9), where it commits to specific, correct, high-confidence answers
rather than hiding behind abstention.

---

## Phase 9 — Broader wildlife decision

Broader Wildlife Maturity v1 (this milestone's immediate predecessor,
accepted hours earlier) deliberately left species-level mammal
identification unsupported, explicitly because no way existed to validate a
new heuristic locally. This milestone asked whether that can honestly
change now. Real answer: **partially, with real positive signal, but not
enough to promote.**

Since zero real MockingBird mammal photos exist (Phase 4), this session ran
a **separate, clearly-labeled, informal, external-domain spot-check**
(`scripts/spotcheck_speciesnet_external_wildlife.py`, output at
`data/evaluations/species-promotion-v2/external-broader-wildlife-
spotcheck.json`) against 6 real third-party camera-trap photos (Channel
Islands Camera Traps / ENA24 corpora, already present in the repository's
gitignored `data/training/wildlife-stage2/` detector-training corpus — read
only, never touching the 7 preserved detector files or the training
pipeline itself). Ground truth is this session's own direct visual
identification of clear photos, disclosed as such — these images carry no
per-image species label in the local manifest (it is a detector corpus:
animal-or-not, not species-labeled).

| Photo | SpeciesNet | BioCLIP-2 |
|---|---|---|
| Squirrel (daylight, forest floor) | `blank` (missed — small/distant subject, matches its known always_crop weakness on non-cropped subjects) | Abstains (structural) |
| Cat (tabby, suburban yard) | **`domestic cat`, 0.926** | Abstains (structural) |
| Opossum (night IR) | **`virginia opossum`, 0.964** | Abstains (structural) |
| Chickens x2 (domestic, off-target) | `blank` (safe) | Abstains (structural) |
| Empty scene (daylight) | `blank`, 1.000 | Abstains (structural) |
| Empty scene (night IR) | `blank`, 1.000 | Abstains (structural) |

BioCLIP-2 behaves exactly as its architecture predicts on every case: a
closed 14-species bird-only candidate pack cannot name a mammal, and its
abstention policy correctly declines rather than forcing a bird label onto
any of them — a real, working safety property, not a gap.

**Per-species classification against the milestone's own Phase 16 list**,
disclosed honestly per candidate:

| Species | SpeciesNet | BioCLIP-2 |
|---|---|---|
| Cat | Useful taxon/species-level (real, external-domain evidence only) | Unsupported (structural) |
| Opossum | Useful taxon/species-level (real, external-domain evidence only) | Unsupported (structural) |
| Squirrel | Abstain (missed on this one real external sample; genus-level rows exist in its taxonomy) | Unsupported (structural) |
| Rabbit, deer, raccoon, fox | Unsupported (not tested — no real or external evidence obtained this session) | Unsupported (structural) |

**Why this is not promoted or wired into production this session**, even
though the signal is real and positive:

1. **Zero real MockingBird-domain validation.** Clear, well-lit, well-framed
   external photos are not evidence that SpeciesNet will perform as well on
   MockingBird's actual motion-triggered, often distant, sometimes-night
   camera captures — the exact domain gap the 2026-08-22 report already
   demonstrated matters (SpeciesNet's `always_crop` design underperforms on
   MockingBird's own un-boxed full frames for birds; there is no reason to
   assume the mammal case is immune to the same gap).
2. **Real, non-trivial engineering cost.** Phase 1's P0-2 finding stands:
   the current adapter framework is hardcoded to one `species_classifier`
   provider. A second provider requires a new adapter module, generalizing
   a hardcoded rejection, new packaging/distribution work (SpeciesNet has
   *zero* packaging today — not in `pyproject.toml`, not in
   `build_local_product.py`), and new status reporting to reach parity with
   BioCLIP-2's existing `get_bioclip_status()` pattern.
3. **The milestone's own instruction**: "do not add a second classifier
   merely to make the architecture look wildlife-native... measured value
   must justify runtime complexity." A promising external-domain result on
   n=6 informal cases is a lead, not a measured value.
4. Broader Wildlife Maturity v1's decision (species ID deliberately stays
   bird-only) was made hours before this milestone with the same
   information this session had about local validation limits, and remains
   the more defensible position until real MockingBird mammal evidence
   exists to validate against.

**Recommendation, not executed this session**: a future, explicitly-scoped
"Broader Wildlife SpeciesNet Integration" milestone should (a) collect real
MockingBird mammal field evidence first (this is the actual blocker, not
model capability), (b) build the second-provider adapter plumbing Phase 1
found missing, and (c) evaluate SpeciesNet specifically as a mammal-only
complementary/candidate-generator source, never as a bird-domain
replacement.

---

## Phase 10 — Platform/runtime matrix

| Component | CPU | NVIDIA CUDA | Windows | Linux | Apple Silicon | AMD |
|---|---|---|---|---|---|---|
| BioCLIP-2 | **Validated** (production, real field history) | Structural-only — config explicitly refuses non-CPU today (`_validate_config_files`); not a hard technical wall, a current-scope limit reinforced by a CPU-only pinned Windows torch closure | **Validated** (real packaged deployment, Species Suggestion v1.2) | Validated (this repo's own dev environment) | Deferred — no hardware available to test | Deferred — no hardware available to test |
| BioCLIP 2.5 | Structurally supported (same `open_clip` stack as the incumbent) but never packaged/validated | Validated for this session's benchmark only (real GPU, real inference) | Unsupported (no packaging exists) | Structural-only (ran in this repo's `.venv`, never packaged) | Deferred | Deferred |
| SpeciesNet | README-documented as feasible; not benchmarked CPU-only this session (real CUDA numbers only) | Validated for this session's benchmark only | Unsupported (zero packaging; heavy PyTorch/YOLOv5-era dependency tree explicitly kept out of core per the original 2026-08 boundary review) | Structural-only (`.venv`-only, research use) | Deferred | Deferred |

No hardware-unverified claim is upgraded to "validated" anywhere in this
table. Apple Silicon and AMD remain genuinely untested — this session had
no such hardware, and per the milestone's own instruction, that does not
block the milestone; it is disclosed as deferred, not assumed to work
because PyTorch theoretically supports it.

---

## Phase 11 — Packaging/licensing/distribution

| | BioCLIP-2 | BioCLIP 2.5 | SpeciesNet |
|---|---|---|---|
| Code license | **MIT — independently re-verified this session by live fetch of the real `huggingface.co/imageomics/bioclip-2` model card** (metadata tag `license: mit`, description "License: MIT", BibTeX `license = {MIT}`). Not verifiable from anything cached *on this disk* (no model card/README/LICENSE is cached alongside the raw weights+config), so the live fetch was the correct way to close that gap rather than merely re-asserting the prior report's claim. | **MIT — independently re-verified the same way**, live fetch of `huggingface.co/imageomics/bioclip-2.5-vith14` (identical metadata/description/BibTeX confirmation). | **Apache-2.0, independently re-confirmed this session** directly from the cached artifact's own `README.md` frontmatter (`~/.cache/kagglehub/.../README.md`: `license: apache-2.0`) — the one license claim checkable from a real local artifact *and* independently re-confirmed live. |
| In `pyproject.toml` | Yes — `classifier-bioclip` extra | Not separately declared; its runtime dependency (`open_clip_torch`) is the same already-declared package | **Absent entirely** — zero declaration anywhere |
| In `build_local_product.py` Windows closure | Yes — full pinned/SHA-256-verified bundle | **No** — no `ACCEPTED_BIOCLIP25_*` constants exist | **No** — zero mentions |
| Model size (cached) | 1.71GB | 3.94GB | 489MB (classifier component only) |
| Download mechanism | Explicit, pinned, checksum-verified, no silent large download | Manual, one-time (`huggingface_hub`), not automated into any product path | Official upstream scripts auto-download; MockingBird's boundary doctrine (`speciesnet-adapter-boundary-plan.md`) explicitly forbids inheriting that behavior — never implemented here |
| Offline/first-run/failure behavior | `get_bioclip_status()` reports `available`/`unavailable`/`not_configured` cleanly; core monitoring continues without it | No adapter exists, so no status/failure path exists yet | Same — no adapter exists |

**Core monitoring continues if species identification is unavailable** —
unchanged, structural, confirmed by the existing `get_bioclip_status`
pattern and by the fact that neither challenger has any production wiring
to fail in the first place. No enormous weights are silently downloaded by
any code path this session touched or added.

---

## Phase 12 — Promotion gate (predeclared before the extended-cohort run)

Before running the extended real cohort, the gate criteria were fixed as:
no unacceptable regression on ordinary birds; meaningful improvement on the
named weakness (RBW-bias sibling-taxa full-frame errors); **better or
equivalent confidently-wrong rate — non-negotiable, this milestone's own
named most-important metric**; acceptable small/far and hard-negative
behavior; abstention preserved or improved; honest score semantics;
complete provenance; wildlife-breadth improvement valued but not mandatory,
and never at bird-first performance's expense; acceptable runtime/
dependency footprint; acceptable licensing; complexity justified by
measurable benefit.

**Applying it to the real results (Phase 6):**

| Candidate | Correctness | Truthfulness | Wildlife breadth | Runtime | Distribution | Architecture | **Gate result** |
|---|---|---|---|---|---|---|---|
| BioCLIP 2.5 | Real improvement on RBW-bias cohort (3/3 fixed) **but fails the non-negotiable confidently-wrong bar by a wide margin** (73.7% vs. incumbent's 5.3%) | Score semantics honest (`calibrated=False` preserved); abstention **regressed**, not preserved | N/A (bird-only model) | Real, non-prohibitive cost (~1.5x incumbent CPU latency, 2.3x size) | Same MIT family, no new blocker | Would require a full new adapter + packaging build-out | **FAILS — confidently-wrong regression alone is disqualifying, independent of every other factor** |
| SpeciesNet | 0/13 real bird accuracy; real mammal capability but external-domain-only | Score semantics honest; abstention excellent | Real, unvalidated-in-domain mammal lead | Heavy dependency tree, deliberately kept out of core per original 2026 boundary review; real CUDA-benchmarked latency here, CPU unbenchmarked | Apache-2.0 confirmed clean; zero packaging built | Would require new adapter + hardcoded-rejection removal + packaging + status reporting — a real, undischarged cost | **FAILS as bird identifier (correctness); NOT YET EARNED as mammal complement (unvalidated in domain + undischarged architecture cost)** |
| BioCLIP-2 (baseline) | — | — | — | — | — | — | **Retained** |

**No candidate clears the gate.** Per the milestone's own framing, this is
recorded as a successful result, not a failure to find a winner.

---

## Phase 13 — Promotion implementation

**Not applicable.** No candidate passed the gate. No production wiring,
adapter registration, packaging change, or threshold change was made to any
candidate model this session. The only production code change this session
made is the P0-1 abstention-bypass fix (below), which touches the existing
BioCLIP-2 path's reuse/idempotency logic, not model selection, thresholds,
or architecture.

### Fix made: abstention-policy reuse bypass (P0-1)

`_reusable_bioclip_suggestion` and `_reusable_legacy_bioclip_suggestion`
(`src/mockingbird/repository/product_repository.py`) matched a candidate
pending suggestion for reuse on exact input/model/candidate-pack identity,
but never checked whether the suggestion's recorded
`identification_policy.policy_version` matched the current
`IDENTIFICATION_ELIGIBILITY_POLICY_VERSION`. A suggestion computed before
the abstention policy existed (pre-2026-08-21), or under an older version of
it, could be served back indefinitely by the ordinary, expected "Identify
again" UI action — never re-entering the abstention gate at all. Fixed: both
reuse paths now additionally require an exact current-policy-version match;
a stale or absent policy stamp now correctly falls through to fresh
inference. New regression test:
`test_review_identification_does_not_reuse_suggestion_from_a_stale_
eligibility_policy_version` (`tests/test_review_identification.py`) —
proves reuse is refused and fresh inference genuinely re-runs (2 real
attempts recorded, a new suggestion id, `created_suggestion_ids != []`).
The 4 pre-existing reuse tests (proving *legitimate* same-policy reuse still
works) remain green, unmodified.

---

## Phase 14 — Human-correction regression

Answered from direct code archaeology this session (not assumed), with
file:line citations retained in the research record:

1. **Candidate suggests correct species, human confirms** — real, exercised
   continuously in production; unaffected by this session.
2. **Candidate suggests wrong species, human corrects** — same path;
   `test_review_identification_bioclip_never_overwrites_a_confirmed_visit`
   already proves a later suggestion can never touch a confirmed Visit's
   truth.
3. **Human correction becomes durable Observation truth** — enforced by
   exactly one choke point, `_create_review_label_in_session`, gated by
   `review_provenance.is_authority_eligible` (only `human`/
   `imported_curated`/legacy-unattributed origins can ever set
   `VisitModel.reviewed_label`/`review_status`).
4. **New inference cannot overwrite that reviewed truth** — confirmed
   structurally: `SpeciesSuggestionModel` content (`suggested_label`,
   `confidence`, `adapter_id`, provenance) is immutable after creation
   (exhaustive grep: zero `UPDATE`/`.field =` sites touching those columns
   anywhere in the codebase); the only mutable field is `.status`
   (pending→accepted/rejected/superseded).
5. **Species correction updates Today/history/Biodiversity** — all three
   read through one canonical resolver,
   `_historical_place_baseline_and_species_statuses`, itself keyed only on
   `VisitModel.review_status`/`reviewed_label` — never on
   `SpeciesSuggestion` for confirmed truth.
6. **Local-learning state still treats human review as upstream authority**
   — Scene Confusor Suppression's reviewed-negative path and Site-Specific
   Learning's conservative-by-default correction are both unaffected by
   this milestone (not touched); both already sit downstream of the same
   review-provenance gate.
7. **Changing classifier provider/model does not rewrite historical
   reviewed truth** — structurally guaranteed, not merely tested:
   `ReviewLabelModel` carries **no classifier-identity field at all** — model
   identity lives only on `SpeciesSuggestionModel`, which reviewed truth
   never references. There is nothing for a provider change to rewrite.
8. **Old observations preserve their original classifier provenance** —
   yes: `SpeciesSuggestionModel.evidence_region_json.model_provenance` is
   written once at creation and never mutated (same exhaustive-grep proof as
   #4).

**Zero P0s found in the truth-boundary/provenance investigation.** This is
a real, independently re-derived confirmation (not a repeat of a prior
session's claim) that a future classifier promotion, whenever one actually
clears the gate, can proceed without any historical-truth migration or
rewrite concern.

---

## Phase 15 — Field/real-evidence check

Every number in Phase 6-9 above **is** the field/real-evidence check for
this milestone — there was no separate synthetic-fixture-only run to
contrast it against. Concrete, named real examples:

- **Improvement**: BioCLIP 2.5 correctly names `house_finch` at 0.98-0.999
  confidence on 3 real full-frame photos (Visits 013/014/016) where the
  incumbent scores wrong (`red_bellied_woodpecker`/`tufted_titmouse`,
  0.37-0.65) — the exact documented RBW-bias cohort, real improvement,
  reproduced.
- **Regression**: BioCLIP 2.5 confidently says `carolina_chickadee`
  (0.94-0.998) on 7 real empty shepherd's-hook frames and `american_robin`
  (0.81-0.998) on both real night frames — a severe, real, newly-quantified
  safety regression.
- **Confident wrongs**: 14 real BioCLIP-2.5 cases (listed in full in the
  JSON artifact); 4 real SpeciesNet cases (all the same failure mode — a
  generic `bird` instead of the real species, never a wrong specific
  species name); 1 real BioCLIP-2 case (the night scene both challengers
  also missed).
- **Correct abstentions**: 18/19 real BioCLIP-2 hard negatives; 18/19 real
  SpeciesNet hard negatives.
- **Unexpected behavior**: both BioCLIP-2 and BioCLIP-2.5 independently
  converge on `american_robin` for the exact same real night capture — a
  genuine, reproducible, cross-model hard case (Phase 6).
- **Sparse-subgroup disclosure, not manufactured conclusions**: multi-subject
  (n=0), night/low-light (n=2), and broader wildlife (n=0 real,
  n=6 informal external) are explicitly reported as too sparse for any
  authoritative conclusion, per the subgroup table in Phase 4 — no
  statistic is derived from them beyond what 2 or 6 cases can honestly
  support.

---

## Phase 16 — Capability matrix (promoted architecture = unchanged production BioCLIP-2 + MDv5)

| Capability | Status |
|---|---|
| Common backyard bird species | validated (real production field history + this session's 38.5% top-1 / 94.7% correct-abstention reconfirmation) |
| Small/far birds | abstention expected (real limitation, unchanged; the one real small/far case this session tested was correctly abstained on, not identified) |
| Multi-subject birds | structural-only (Multi-Subject Visit Assembly exists; zero real classification cases to validate against) |
| Poor evidence (blur/occlusion/edge) | validated for abstention (8/8 real tight-crop poor-evidence hard negatives correctly abstained); the one poor-evidence *positive* case (the motion-blurred, clipped cardinal) was also abstained rather than identified — a real, disclosed small/far accuracy gap, not a safety issue; species-level accuracy under poor evidence not separately measurable at this sample size |
| Night visual identification | abstention expected (1/2 real night hard negatives correctly abstained, 1/2 confidently wrong — a real, disclosed, unresolved gap, unchanged by this milestone) |
| Squirrel | unsupported (structural — closed bird-only candidate pack) |
| Rabbit | unsupported (structural; also zero evidence of any kind) |
| Deer | unsupported (structural; also zero evidence of any kind) |
| Raccoon | unsupported (structural; also zero evidence of any kind) |
| Opossum | unsupported (structural; SpeciesNet showed real external-domain capability here, but SpeciesNet is not promoted) |
| Fox | unsupported (structural; also zero evidence of any kind) |
| Cat | unsupported (structural; SpeciesNet showed real external-domain capability here, but SpeciesNet is not promoted) |
| Unknown/open-set abstention | validated (94.7% real hard-negative correct-abstention rate, reconfirmed on 2.4x more evidence than 2026-08-21's acceptance) |
| CPU | validated (production-shipped, Windows-verified history) |
| NVIDIA CUDA | structural-only (config currently refuses it; not hardware-unverified, deliberately unused) |
| Apple Silicon | deferred (no hardware available) |
| AMD | deferred (no hardware available) |

---

## Validation

**Tier 1** (candidate adapters/runtime, input/crop handling, benchmark
evaluator, score/calibration semantics, abstention, hard negatives,
broader-wildlife cases, provenance, provider-unavailable behavior):

```
pytest tests/test_speciesnet_candidate.py tests/test_identification_eligibility.py \
       tests/test_native_resolution_species_evidence.py tests/test_same_frame_species_evidence.py \
       tests/test_bioclip_adapter.py tests/test_review_provenance.py \
       tests/test_review_identification.py -q
```
→ **218 passed** (183 + 35, both runs green; includes the new P0-1
regression test).

**Tier 2** (Observation Engine classifier path, evidence resolver, Visit
detail/review/correction, Today/history/Biodiversity, broader-wildlife
regressions, local-learning regressions, packaging/runtime tests):
`test_dashboard_today.py`, `test_place_biodiversity_summary.py`,
`test_place_biodiversity_summary_repository.py`, `test_scene_confusor.py`,
`test_scene_confusor_repository.py`, `test_wildlife_journal.py`,
`test_wildlife_insights.py`, `test_wildlife_taxonomy.py`,
`test_species_candidate_packs.py`, `test_observation_evidence_scoring.py`,
`test_evidence_benchmark.py`, `test_local_product_packaging.py`,
`test_visit_episode_assembler.py`,
`test_canonical_new_regular_species_consistency.py`,
`test_representative_evidence.py`, `test_historical_baseline.py`,
`test_historical_baseline_repository.py` → **402 passed**. Plus
`test_engine_runtime.py` (Observation Engine tick loop, where automatic
identification is scheduled) → **82 passed** in isolation; one test
(`test_user_stop_during_reconnect_backoff_is_prompt`, a wall-clock timing
assertion, `elapsed < 3.0`) failed once at 4.17s when run concurrently
with the Tier-3 Core gate below (CPU contention, unrelated to any change
this session made — the species identification reuse-path fix touches
nothing in the reconnect/backoff path) and was independently re-run alone
immediately after, passing cleanly at 2.92s. Confirmed pre-existing
timing flakiness under load, not a regression, matching this repository's
own established pattern for this exact class of finding.

**Tier 3**: this session's one production code change (the P0-1
reuse-bypass fix) genuinely changes classifier/runtime behavior (it changes
when a suggestion is reused vs. freshly re-inferred), so the full Core
suite (`scripts/verify_core.py`, `pytest -m "not slow"`) is run before
closure regardless of the no-promotion outcome, per this milestone's own
validation-tier instruction → **4595 passed, 2 skipped, 23 deselected, 11
xfailed, 0 failed** (18m19s). `test_engine_runtime.py`'s one
CPU-contention-induced timing flake from the Tier-2 run (above) did not
recur here, consistent with it being contention, not a regression.

---

## Seven preserved detector files

Confirmed untouched this session (checked before and after every edit):
`docs/wildlife-detector-training-contract.md.orig`,
`scripts/evaluate_small_bird_detector.py`,
`scripts/materialize_wildlife_stage2.py.orig`,
`scripts/train_wildlife_stage2_rfdetr.py.orig`,
`src/mockingbird/detectors/small_bird_benchmark.py`,
`src/mockingbird/training/wildlife.py.orig`,
`tests/test_small_bird_benchmark.py`. The Phase 9 external-domain spot-check
read raw images from `data/training/wildlife-stage2/dataset/train/` (an
adjacent, already-existing, gitignored data directory) but never opened,
imported, or modified any of the seven files themselves, and never touched
the training/materialization pipeline they belong to.

## Nothing pushed

Confirmed: no `git push` invoked this session. Local `main` remains ahead of
`origin/main` (177+ commits before this session's own commit(s) are added).

---

## Required closure questions

1. **Baseline architecture**: BioCLIP-2 (ViT-L/14, closed 14-species
   "Backyard Core v1" pack, CPU-only-by-config, with the accepted
   Identification Eligibility + Abstention v1 policy) + MDv5a detection —
   unchanged.
2. **Real candidates evaluated**: SpeciesNet v4.0.3a (classifier-only) and
   BioCLIP 2.5 (ViT-H/14) — both real, both actually run this session on a
   fresh, extended cohort, not merely discussed.
3. **Evidence cohort**: 36 real cases (32 scored), individually visually
   verified this session; a 3x real expansion of the prior session's
   cohort, built from the live product DB plus reused archived evidence.
   See Phase 4 for exact subgroup counts.
4. **Subgroup sizes**: ordinary birds 13; small/far 1; multi-subject 0;
   hard negatives 19; poor evidence 9 (tagged subset); night/low-light 2;
   broader wildlife 0 real / 6 informal-external; new/open-set 4
   (unscored, disclosure-only).
5. **What each candidate improved**: BioCLIP 2.5 — real top-1 accuracy gain
   on genuine birds (61.5% vs. 38.5%), including fixing the documented
   RBW-bias sibling-taxa cohort outright. SpeciesNet — nothing on birds;
   real, previously-untested mammal-species-level capability on external
   evidence (cat, opossum).
6. **What each candidate regressed**: BioCLIP 2.5 — hard-negative safety,
   severely (73.7% confidently wrong vs. 5.3%). SpeciesNet — nothing
   relative to itself (it was never a bird candidate to begin with); as a
   bird candidate it remains at 0% specific-species accuracy, unchanged.
7. **Lowest dangerous confident-wrong behavior**: SpeciesNet (0% on real
   hard negatives, best of the three, including the incumbent), but this
   is inseparable from its near-total inability to commit to a specific
   bird answer at all — not a like-for-like win on usefulness.
8. **Abstention comparison**: incumbent 94.7% correct hard-negative
   abstention (reconfirmed, +1 new real miss found this session);
   BioCLIP 2.5 26.3% (severe regression); SpeciesNet 94.7% (matches
   incumbent, on real MockingBird evidence).
9. **Genuinely supported broader wildlife**: none, structurally, for the
   promoted (unchanged) architecture. Real, positive, external-domain-only
   signal exists for SpeciesNet on cat and opossum specifically —
   explicitly not validated against MockingBird's own capture domain, and
   not shipped.
10. **Winning input representation**: MockingBird's own real evidence
    resolver output (the 6-tier crop/full-frame chain), used exactly as
    production would select it — confirmed again, no idealized-crop
    benchmarking anywhere in this session.
11. **Genuinely calibrated scores**: none. `calibrated=False` preserved
    honestly for both BioCLIP models; no formal calibration was built
    (evidence volume did not justify one); SpeciesNet's `blank` mechanism
    is not a calibrated probability either, despite performing well
    empirically.
12. **Runtime/platforms actually validated**: CPU (BioCLIP-2, real
    production history); CUDA (all three, this session's own benchmark
    run, real GPU); Windows (BioCLIP-2 only, real packaged deployment
    history). Apple Silicon and AMD remain deferred, not claimed.
13. **Licensing/distribution constraints**: all three real licenses were
    independently re-verified this session, not merely re-asserted from
    prior reports — SpeciesNet's Apache-2.0 from its cached local artifact's
    own `README.md` frontmatter, and both BioCLIP-2 and BioCLIP-2.5's MIT
    license by live fetch of their real HuggingFace model cards (neither
    was checkable from anything cached on this disk, so a live check was
    required rather than optional). Neither challenger has any packaging
    built regardless of the clean license outcome.
14. **Did any candidate pass the predeclared gate?** No.
15. **What was promoted/demoted?** Nothing. The one production code change
    is a correctness fix (P0-1), not a model or threshold change.
16. **Why retaining the baseline is correct**: it is the only architecture
    with a real, extensive, positive field record and a hard-negative
    safety rate (94.7%) neither real challenger matched while also being
    useful; BioCLIP 2.5's real accuracy gain is disqualified by its own
    severe, reproduced safety regression against this milestone's own
    named most-important metric.
17. **When the classifier is unavailable**: unchanged — core
    monitoring/detection continues; `get_bioclip_status()` reports a clean
    `available`/`unavailable`/`not_configured` state; no truth write is
    ever gated on species-model availability.
18. **Does reviewed historical truth remain invariant?** Yes, structurally
    guaranteed (Phase 14) — `ReviewLabelModel` carries no classifier
    identity to rewrite, and `SpeciesSuggestionModel` content is immutable
    after creation.
19. **Remaining classification gaps, exactly**: (a) BioCLIP 2.5's
    full-frame/activity-crop confident-wrong problem is real, severe, and
    unresolved — not a small-tuning gap; (b) SpeciesNet's real mammal
    capability has zero MockingBird-domain validation; (c) genuinely zero
    real MockingBird mammal evidence exists anywhere to close that gap
    with — that is the actual blocker, not model capability; (d) small/far
    and night bird identification remain real, disclosed, unresolved weak
    spots for the retained incumbent itself, unchanged by this milestone;
    (e) the species-classifier adapter framework remains hardcoded to one
    provider (Phase 1 P0-2) — a real, undischarged architectural cost for
    whichever future candidate eventually does clear the gate.

---

## Summary

- **Starting HEAD**: `9114f9e09f8eced72239c8beccaeaa5b3179a0bb`
- **Ending HEAD**: see commit recorded at closure below
- **Schema**: unchanged, v53 (no migration; the live local DB itself is
  separately, pre-existingly at v49 — 4 migrations behind the checked-out
  code — never touched or migrated by this session, per the read-only
  discipline every benchmark script in this family follows)
- **Focused validation**: Tier 1 — 218 passed. Tier 2 — 402 + 82 passed (1
  confirmed CPU-contention flake, re-ran clean in isolation). Tier 3 (Core
  gate) — 4595 passed, 2 skipped, 23 deselected, 11 xfailed, **0 failed**.
- **Seven preserved detector files**: confirmed untouched.
- **Nothing pushed**: confirmed.
- **Next natural milestone** (not started, per this milestone's explicit
  instruction to stop): Gate F (OSS/security/compatibility/packaging
  closure) remains the roadmap's own next open gate. A second, smaller,
  explicitly-optional candidate: a real MockingBird-field mammal-evidence
  collection effort, which is the actual prerequisite for ever honestly
  evaluating SpeciesNet's broader-wildlife lead in-domain — not a model or
  architecture task, a data-collection one.

**STOP. Do not begin the next milestone automatically.**
