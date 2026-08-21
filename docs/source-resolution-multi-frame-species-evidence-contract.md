# Source-Resolution + Multi-Frame Species Evidence v1

Status: implemented (Decision B — see "Decision" below). Commit: see roadmap.md's Gate B entry for this milestone.

## Why this exists

Same-Frame Species Evidence v1 and Subject-Centric Classifier Input proved
exact-frame identity and subject-centric cropping, but left one gap open
(documented explicitly in both their own reports): the automatic species-
assist path could only ever safely crop the analysis-stream-resolution
frame (`classifier_same_frame`, proven `same_frame=True`) or fall back to a
full frame. The Camera Node's separately-captured, genuinely higher-
resolution `high_resolution_burst` evidence was — and had to be, by
construction — `same_frame=False`, so `classifier_input.py`'s "proof, not
proximity" safety rule correctly refused to crop against it. The product
requirement this milestone closes:

> detect/track efficiently at analysis resolution, then use the highest
> genuinely available source-resolution subject evidence for species
> identification, preferably across multiple quality-ranked frames, without
> lying about resolution or temporal provenance.

## Resolution/provenance vocabulary

- **analysis_frame**: the frame used for continuous detector/tracker work
  (the Camera Node's `monitoring`-purpose capture profile).
- **source_frame**: the highest-resolution frame actually acquired and
  retained for that exposure/path (the Camera Node's `evidence`-purpose
  capture profile, when a burst succeeds).
- **native_resolution**: pixels directly produced by the camera/provider,
  never synthetically enlarged. This codebase never upscales/interpolates
  anywhere in the species-evidence path — a hard invariant, not merely a
  benchmark rule.
- **derived_crop**: a crop taken from a source frame.
- **exact_same_frame**: `GeometryAttribution.same_frame is True` — the
  evidence image and the geometry's own source observation are provably
  the identical captured frame (byte-identical, sha256-verified for the
  live analysis stream).
- **synchronized**: `GeometryAttribution.resolution_provenance ==
  "synchronized"` — a genuinely separate, later real capture, but one whose
  Camera Node capture-profile metadata *proves* it shares the analysis
  frame's field of view (`fov_alignment_proven`), with a real, measured gap
  inside the existing bounded misalignment threshold
  (`localization_attribution.DEFAULT_MISALIGNMENT_GAP_THRESHOLD_MS`, 5000ms
  — reused, not reinvented).
- **near_time_capture**: `resolution_provenance == "near_time_capture"` — a
  real, bounded-gap capture without a *proven* field-of-view match. Honestly
  retained as evidence; never safe to crop a reused subject box against.
- **fallback**: `resolution_provenance == "fallback"` — gap unknown or
  exceeds the bounded threshold, or no usable native evidence at all.

These four `resolution_provenance` values, plus the pre-existing `same_frame`
boolean and the new `fov_alignment_proven`/`geometry_transform_id` facts,
live on `GeometryAttribution`
(`src/mockingbird/observation/contracts.py`) — additive fields, `None` for
every pre-existing record, computed by
`localization_attribution.geometry_attribution_for_update`/
`geometry_attribution_for_burst`
(`src/mockingbird/observation/localization_attribution.py`).

Never collapsed: a high-resolution frame captured 300ms later is
`synchronized` or `near_time_capture`, never mislabeled `exact_same_frame`.

## Acquisition strategy actually available (Phase A findings)

Reconstructed from the real reference implementation, not assumed:

- **Reference camera/provider**: `PiCamera2Provider`
  (`src/mockingbird_node/providers.py`) — the Raspberry Pi/picamera2-backed
  Camera Node provider. No sensor part number is hardcoded anywhere in the
  repository (confirmed by exhaustive grep); every capture profile is
  discovered at runtime from the real `Picamera2.global_camera_info()`/
  `camera.sensor_modes`.
- **Deployed analysis resolution**: 1920×1080, ≤1.5MB JPEG
  (`MOCKINGBIRD_NODE_MAX_IMAGE_WIDTH`/`_HEIGHT`/`_MAX_IMAGE_BYTES`, identical
  in `scripts/install_camera_node.py` and
  `scripts/build_camera_node_artifact.py` — what a real deployed Camera Node
  actually runs with, not just the library default).
- **Deployed evidence ceiling**: up to 10000×8000px / 16MB JPEG
  (`MOCKINGBIRD_NODE_EVIDENCE_MAX_IMAGE_WIDTH/HEIGHT/BYTES`) — bounded well
  above any real sensor mode, so the ceiling never artificially caps real
  capability.
- **Real field-proven burst resolution**: **4624×3472** — documented from
  real prior live Camera Node sessions in
  `docs/sustained-visit-continuity-contract.md` ("three real 4624x3472
  high-resolution bursts"), `docs/candidate-visit-authority-contract.md`
  ("real 4624x3472 burst evidence of a backyard feeder tree"), and present
  as real files in this checkout's own `data/media/imports/` (98 real,
  independently-verified 4624×3472 JPEGs, see "Benchmark" below). This is
  ~8x the analysis resolution's pixel count (2.07MP vs 16.06MP), not a
  marketing number — `PiCamera2Provider._is_required_warm_pair` explicitly
  retries this exact pair once after a larger candidate is rejected for
  resource exhaustion (`tests/test_camera_node.py::
  test_picamera2_warm_required_pair_retries_once_after_resource_rejections`),
  so 4624×3472 is the largest mode that reliably fits real Pi memory
  headroom today, not an arbitrary choice.
- **Acquisition mechanism — Strategy A/C available today**: `PiCamera2Provider`
  configures `main` (evidence, RGB888) and `lores` (monitoring, YUV420)
  simultaneously via one `create_still_configuration(main=..., lores=...)`
  call (`_initialize_warm_camera`), then reads both from the *same live
  session* (`capture_array("lores")` / `capture_array("main")`). This is
  real, exercised production code (`capture_class == "warm_concurrent"`),
  not dead scaffolding. A cold single-stream "reconfiguration_required"
  fallback exists for hardware/driver combinations where the warm pair
  cannot be proven (Strategy D territory — see below).
- **FOV-alignment proof already existed, but only in a different pipeline**:
  `mockingbird.motion.high_resolution_evidence.resolve_alignment`/
  `CaptureProfileGeometry`/`NormalizedGeometryTransform` (tested,
  `tests/test_high_resolution_evidence.py`) already compares real
  `geometry_group` fingerprints (from real `sensor_modes()` `crop_limits`)
  before trusting a cross-profile box — but this machinery was wired only
  into the legacy, human-initiated "save best frame during live view"
  path (`api/main.py::_capture_high_resolution_activity_evidence`,
  `mockingbird.playback.live_camera_session`), never into the Observation
  Engine's automatic `camera_node_live.py` burst path. Before this
  milestone, `geometry_attribution_for_burst` reused the analysis frame's
  raw normalized box on the burst image with **zero** FOV/aspect-ratio
  proof — only a temporal-gap heuristic. This milestone closes that gap by
  reusing (not duplicating) `resolve_alignment` inside the Observation
  Engine path — see "Coordinate mapping" below.

Given this, the selected strategy is **A (exact dual-resolution/same-
exposure retrieval) when `capture_class == "warm_concurrent"` and alignment
is proven**, degrading honestly to **near_time_capture** when a burst
succeeds without proven alignment, and **fallback** when neither applies.
Strategy E (honest analysis-resolution-only fallback) remains fully intact
and unchanged — provider capability was never forced.

## Coordinate mapping

`engine_runtime._default_capture_profile_alignment` fetches this Stream's
real monitoring/evidence `CaptureProfileGeometry` pair once, at session
start (never per-frame — a single bounded `CameraNodeClient.cameras()` call,
mirroring the pairing/health checks this same startup path already makes),
and calls the existing, tested `resolve_alignment`. The resulting
`AlignmentDecision` is threaded into `LiveCameraNodeShadowSession` and
consulted inside `_process_frame`'s burst-evidence construction
(`camera_node_live.py`):

- When alignment is proven (`status == "aligned"`), the analysis-frame
  subject box is mapped onto the evidence image via the real
  `NormalizedGeometryTransform.map_box` (handles rotation/mirror; a pure
  identity for this reference hardware's normal orientation, but not
  hardcoded as one — a provider that *does* report a rotation/mirror
  difference between profiles is handled correctly without new code).
  `geometry_transform_id` is persisted so the mapping is reproducible.
- When alignment cannot be proven, or the mapped box is structurally
  invalid, the box is dropped (`subject_geometry=None`) rather than
  persisting an unproven or wrong-space box under a "synchronized" claim.
- Any failure fetching alignment (Camera Node unreachable at session start,
  incomplete Stream configuration) degrades to `None` — never blocks
  Observation Engine startup, never raises. Confirmed by
  `tests/test_engine_runtime.py::
  test_capture_profile_alignment_none_on_client_error_never_raises`.

Mandatory invariant upheld: a mapped source crop bbox refers to the same
physical subject region as the detector bbox, or no bbox is claimed at all.
Never an ad hoc multiplication.

## Native/source-resolution classifier-input tier

`species/classifier_input.py` gains one new tier,
`native_resolution_subject_box`
(`resolve_native_resolution_subject_crop`), ranked in
`resolve_classifier_input`'s decision order as:

1. `persisted_subject_crop` — an already-curated derived crop (unchanged;
   respecting prior deliberate curation outranks automated resolution
   choice).
2. **`native_resolution_subject_box` (new)** — the first of
   `native_resolution_candidates` (caller-ordered, best-first) whose
   `GeometryAttribution.resolution_provenance == "synchronized"` — the
   same "proof, not proximity" bar `exact_frame_subject_box` already
   enforces, applied identically to higher-resolution evidence so it never
   gets a *weaker* safety bar than same-resolution evidence.
3. `exact_frame_subject_box` — unchanged (byte-identical analysis frame).
4. `full_frame` — unchanged, always available.

Resolution is ranked ahead of same-resolution same-frame identity once
correspondence is equally proven, because the entire product requirement
this milestone exists to satisfy is genuinely more subject-relevant pixels
before BioCLIP's own internal resize (see "Why resolution helps" below).

`ProductRepository._classifier_input_override` (the single seam feeding
every automatic BioCLIP run,
`product_repository._review_species_crop_context`) now also fetches this
Visit's `_native_resolution_subject_frames_for_visit` and passes them
through — additive, and provably backward-compatible (`test_classifier_
input.py`'s 30 pre-existing tests pass completely unchanged; the new tier is
only ever reached when `resolution_provenance == "synchronized"` data
exists, which no pre-milestone record ever has).

### Finding genuinely-native candidates without a role check

A winning `high_resolution_burst`-origin `EvidenceCandidate` is persisted
under whichever role `evidence_scoring.score_proposal_evidence` assigned it
(`identification`/`context`/`alternate`), never the origin role string
itself (`candidate_visit_adapter._build_evidence_items`). So
`ProductRepository._native_resolution_candidate_assets_for_visit` does not
filter by `evidence_role` at all — it decodes every Visit-linked asset's
`geometry_attribution_json` and keeps the ones whose `resolution_provenance
== "synchronized"`, which only a genuine burst-origin candidate can ever
carry. Ordered by `VisitEvidenceLinkModel.created_at`/id — the exact order
`_build_evidence_items` inserted them in (identification pick first, by the
scorer's own already-computed quality rank), so no second ranking system is
invented.

## Bounded multi-frame candidate selection

`ProductRepository.species_multi_frame_candidate_plans(visit_id,
max_candidates=MAX_LIVE_VISIT_EVIDENCE_FRAMES)` — read-only, side-effect-
free (never runs a model, never persists, never mutates a Visit). Returns
the same-frame plan (if eligible) followed by native-resolution plans, each
independently resolved via the exact tiers above, capped at 4 —
`MAX_LIVE_VISIT_EVIDENCE_FRAMES`, the existing, already-measured ceiling on
how many evidence frames a Visit ever retains at all, not an invented
number (a real Visit supplies at most one same-frame asset plus up to
`MAX_LIVE_VISIT_EVIDENCE_FRAMES - 1` distinct native alternates today).

## Quality ranking

Reused, not reinvented: candidate order comes from
`evidence_scoring.score_proposal_evidence`'s own already-computed,
already-tested, species-blind (structurally checked — "Species identity and
species-model inference are never used") ranking over track/detector
support, subject containment/edge-clipping, subject pixel area, temporal
alignment, sharpness (deterministic edge-response RMS), and exposure —
computed once at capture time and preserved via persisted evidence-link
order. This milestone adds no second quality-ranking subsystem.

## Multi-frame consensus / abstention integration

`species/identification_eligibility.py` adds
`evaluate_multi_frame_consensus` (pure, `FrameClassificationResult` in,
`MultiFrameConsensusDecision` out), reusing (never replacing)
`evaluate_classification_abstention` per frame:

1. Each frame independently scored via its own tier's existing floor.
2. One frame degenerates to exactly today's single-frame behavior
   (`consensus_basis="single_frame"`).
3. No confident frame at all → abstain (`no_confident_frame_result`).
4. All confident frames agree → suggest (`unanimous_agreement`), reporting
   the best-quality agreeing frame's own real score — never an average.
5. A strict majority (> half) of confident frames agree → suggest
   (`majority_agreement`) — "one anomalous frame cannot overpower several
   strong contradictory frames," but a real majority, never a plurality.
6. A genuine no-majority split → abstain (`cross_frame_disagreement`) —
   disagreement is positive evidence for abstention, never discarded.

Separation preserved: evidence quality eligibility (`evaluate_
identification_eligibility`) ≠ classification support/abstention
(`evaluate_classification_abstention`/`evaluate_multi_frame_consensus`) ≠
reviewed truth (unaffected; human correction remains authoritative
regardless of any of the above).

`native_resolution_crop` is mapped to the `subject_focused` abstention tier
(`classifier_input_tier`) — the same floor as any other subject-focused
crop, never a softer or stricter one for being higher-resolution.

**Not wired into the live, mutating `identify_review_queue_item`
orchestration** — see "Decision" below for why.

## Capability contract

`ObservationProviderCapabilitiesResponse`
(`src/mockingbird/api/schemas.py`) now exposes `high_resolution_burst:
bool` — previously computed on `ObservationProviderCapabilities` but
silently dropped by the response model's field list (a real, disclosed gap
this milestone closes with a one-line addition; the existing
`**provider.capabilities.__dict__` spread in `api/main.py` needed no
change). `FrameDrivenObservationProvider.capabilities.high_resolution_burst
is True` was already correct at the dataclass level
(`tests/test_observation_frame_driven.py`); it now reaches the wire.

Per-evidence-item provenance (`resolution_provenance`, `fov_alignment_
proven`, `geometry_transform_id` on `GeometryAttribution`) is the richer,
more honest mechanism actually used for "can this evidence be trusted as
native-resolution" — a single static per-provider-kind capability flag
would be a coarser, less honest signal than what already exists per-item.

## No fake resolution

Upheld throughout, never violated:

- Original source dimensions are always retained (`ResolutionEvidencePair`/
  `ClassifierInputPlan.original_width/height`) — never lost.
- No interpolation/upscaling exists anywhere in this path. `resolve_
  native_resolution_subject_crop` crops real pixels via the existing
  `plan_activity_crop` padding convention; it never resizes upward.
- `resolution_provenance="fallback"` is always explicit, never hidden —
  `_classifier_input_override` falls through to the pre-existing megadetector/
  activity/full_frame tiers exactly as before whenever the new tier does not
  apply.
- The benchmark (below) never compares an analysis crop against an upscaled
  copy of that same crop — its "analysis-resolution equivalent" arm is
  built by *downscaling* real native pixels' geometry before cropping (see
  "Benchmark methodology").

## Benchmark

See `src/mockingbird/observation/source_resolution_species_benchmark.py`
(pure comparison logic) and `..._io.py` (real-cohort loading, always via a
disposable copy of the source database — never opens a real product
database directly, see `copy_database_for_read_only_analysis`).

### Methodology

No live BioCLIP model was available in this development sandbox (no
packaged model weights present locally — confirmed via `bioclip_runtime`'s
own resolvers all returning `None`). Species top-1 correctness, named-
suggestion precision, cross-arm disagreement rate, and false-confident-
suggestion rate could therefore not be measured live in this session; the
benchmark honestly reports `live_model_inference_available=False` plus an
explicit `limitations` entry rather than fabricating a score, and instead
measures the model-independent facts this milestone's product requirement
actually turns on:

- **Arm A (analysis-resolution equivalent)**: for each real subject box,
  compute the pixel dimensions that exact same real, already-measured
  normalized box would have at the real deployed analysis resolution
  (1920×1080) — pure arithmetic on a resolution-independent normalized
  box, never a resized image. This *removes* detail relative to the real
  native capture (an honest simulation of a lower-resolution capture),
  never adds fabricated detail — the opposite of the forbidden "upscale and
  call it native" comparison.
- **Arm B (native/source-resolution single-best frame)**: the real,
  already-persisted derived crop's own real pixel dimensions.
- **Arm C (multi-frame availability)**: how many genuinely distinct native
  candidate frames each real Visit actually has.

### Real cohort

98 real, paired (native-resolution parent, derived-crop child) evidence
records, loaded from this checkout's own real product database
(`data/mockingbird.sqlite3`, 235 real Visits total) via a safe read-only
copy. This pairing comes from the pre-existing `high_resolution_original`/
`activity_crop` evidence relationship (the "best-frame media attachment"
feature predating this milestone, see `mockingbird.motion.
high_resolution_evidence`) — real photographed bird/animal encounters, real
4624×3472 native captures (100% `alignment_status="aligned"`), real derived
crops as small as 87×124px (genuinely small/far subjects), with 58 real
human-reviewed Visits overall (35 `unknown_bird`, 18 `false_positive`, 3
`house_finch`, 1 `squirrel`, 1 `northern_cardinal`) providing partial real
ground truth. This is real historical data from the *legacy* capture
pathway (predates this milestone's own schema fields), used honestly as a
source of genuine paired native/derived-crop imagery — never claimed to
carry this milestone's own `resolution_provenance="synchronized"` schema.

### Real results

- **Median native-to-analysis-equivalent subject pixel area ratio: 22.7x**
  across all 98 real pairs.
- **34/98 (35%) real subjects cross the 32px eligibility floor
  (`identification_eligibility.MINIMUM_CLASSIFIER_INPUT_DIMENSION_PX`) only
  at native resolution** — un-attemptable at the analysis-resolution
  equivalent (median simulated size 51×46px), attemptable at real native
  resolution (median real crop size 206×253px, 98/98 eligible).
- 10 real `false_positive`-reviewed pairs exist; native resolution does not
  introduce a *new* eligibility-crossing risk specific to them (all 10 were
  already eligible at native resolution — no shift observed either way,
  since eligibility is a resolution floor, not a confidence judgment).
- **0/98 real Visits in this specific (legacy-pathway) cohort have more
  than one genuinely distinct native-resolution candidate frame** — a real,
  structural fact about *this data source* (the legacy manual "save best
  frame" path made at most one capture per Visit by construction), not
  evidence that the new Observation-Engine burst pathway (which retains up
  to `MAX_LIVE_VISIT_EVIDENCE_FRAMES - 1` = 3 native alternates per Visit
  when available) rarely produces multiple candidates in the field — that
  pathway has not yet accumulated enough real field history in this
  sandbox to measure directly.

Full report: `data/benchmarks/source-resolution-species-evidence/
source-resolution-species-benchmark-report.json` (generated by
`scripts/benchmark_source_resolution_species_evidence.py`).

## Nuthatch/difficult-case regression

The real, previously-documented nuthatch→Tufted-Titmouse/Red-bellied-
Woodpecker misidentification (2026-08-19, cited in
`docs/person-background-false-positive-attribution-v1-report.md` and
`docs/end-to-end-bird-encounter-recall-closure-v1-report.md`, explicitly
deferred by two subsequent milestones as "a concrete, real input this
milestone should use") remains an open, never-directly-re-tested species-
level question. This milestone could not re-run that exact historical
encounter through the new native-resolution/multi-frame path: no live
BioCLIP model was available in this sandbox, and the specific original raw
evidence for that exact encounter was not readily extractable from the
available field-acceptance artifacts (the underlying fragmented Visits have
since been superseded by the Ambiguous-Boundary Transitive Fragmentation
Closure this same historical cohort's duplicate-Visit symptom motivated).
Recommended as the natural next bounded validation step once a live model
is available (see "Remaining limitations" in the milestone final report) —
not fabricated here.

## Privacy

Unchanged and re-verified: `_classifier_input_override`'s new native-
resolution branch produces a `_ReviewSpeciesCropContext` with `source=
"activity"` (the same value the existing same-frame/persisted-crop tiers
already use) and a real geometric `box_normalized` — so the existing
`_review_species_crop_intersects_restricted_zone` check (keyed on
`crop.source`, real-polygon-aware for anything other than `"full_frame"`)
applies to it exactly as it does to every other subject-focused crop,
without any new special-casing. No hidden full-resolution privacy bypass
was introduced. Confirmed by the full existing privacy regression suite
passing unchanged (`tests/test_review_identification.py`).

## Performance / resource impact

- Capability-alignment fetch: one bounded `CameraNodeClient.cameras()` call
  per Observation Engine session start (not per-frame), the same class of
  call this startup path already makes for pairing/health.
- No new per-frame CPU/GPU cost: coordinate mapping is pure arithmetic
  inside the existing burst-construction path.
- No cache-size change anywhere (explicit non-goal, honored).
- `species_multi_frame_candidate_plans` is read-only and bounded (≤4
  plans); never invoked from the continuous detection/tracking hot path.
- No new BioCLIP calls were added to any live, mutating code path — the
  multi-frame consensus function exists as tested, invokable infrastructure
  and a benchmark primitive, not as an unconditional new per-Visit cost.

## Decision

**B — SOURCE-RESOLUTION ACQUISITION IMPLEMENTED, MULTI-FRAME POLICY NOT YET
JUSTIFIED.**

The pixel path is fixed and proven: genuine native/source-resolution
acquisition already existed in the reference hardware/provider, honest
FOV-alignment proof already existed in a sibling pipeline, and this
milestone correctly wires the two together into the Observation Engine's
automatic species-evidence path, with correct coordinate mapping, honest
provenance vocabulary, and a real, measured 22.7x median pixel-detail
improvement that changes eligibility outcomes for over a third of a real
98-encounter cohort. Multi-frame consensus is genuinely implemented as
pure, tested, invokable infrastructure (`evaluate_multi_frame_consensus`,
`species_multi_frame_candidate_plans`) and used by the governed benchmark —
but two things needed to responsibly promote it into the live, mutating
`identify_review_queue_item` orchestration are not yet available in this
environment: (1) real field evidence that multiple genuinely distinct
native candidate frames actually accumulate often enough, under the new
Observation-Engine burst pathway specifically, to make consensus
meaningful rather than a no-op; and (2) any live species-classifier
inference to measure whether combining frames changes real accuracy versus
the now-improved single-best-frame path. Per this repository's own
governing doctrine ("A candidate detector/classifier does not gain
production authority merely because it is newer or appears better
informally; require reproducible incumbent comparison first" —
AGENTS.md), promoting an always-on multi-frame consensus into the
unconditional production path without that evidence would be exactly the
kind of ungoverned promotion this codebase's own precedent explicitly
guards against.

## Recommended smallest follow-up

Once real field history accumulates on the new Observation-Engine burst
pathway (no code change required to start collecting it — this milestone's
own capture-time wiring already produces it), re-run this benchmark against
that fresh cohort; if it shows real multi-candidate availability and (once
a live model is reachable) real accuracy benefit from consensus over
single-best-frame, wire `species_multi_frame_candidate_plans` +
`evaluate_multi_frame_consensus` into `identify_review_queue_item` as an
additive extension of the existing single-frame path — the infrastructure
already exists and is already tested end-to-end.
