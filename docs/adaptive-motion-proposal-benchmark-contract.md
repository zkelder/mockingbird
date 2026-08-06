# Adaptive motion-proposal detector benchmark contract

Status: Observation Engine v2 Stage 6.5 provider contract.

## Boundary

`mockingbird.observation.motion_proposal_strategy` and
`mockingbird.observation.motion_proposal_benchmark` characterize whether a
bounded, deterministic, *adaptive* multi-scale strategy -- a small number of
temporal-change-guided high-resolution inference windows, alongside the
existing full-frame pass -- retains some of the Stage 6.4 uniform-tile
strategy's recall benefit without its precision/resource collapse. It is
offline, deterministic, and diagnostic only: no camera, Camera Node, live
monitoring, worker, or product database is opened, and no runtime threshold,
Ignore region, tracker, or default-provider configuration is read or
mutated. Every output remains `shadow_only=true`, `creates_truth=false`
evidence with no production proposal authority, and does not change which
detector or strategy MockingBird actually runs. No outcome of this benchmark
authorizes production Visit proposals; Stage 7 remains blocked.

The module split mirrors Stage 6.2/6.4: `motion_proposal_strategy.py` is
pure temporal-change geometry with no CUDA, ONNX Runtime, OpenCV, or
camera-provider type anywhere in its contract; `motion_proposal_benchmark.py`
is pure report assembly that reuses the existing Stage 6.2
`detector_benchmark` pipeline (`sweep_thresholds`, `cluster_static_false_
positives`, `simulate_temporal_policies`, `classify_sample_sufficiency`) and
the existing Stage 6.4 `multi_scale_benchmark` window machinery
(`merge_frame_windows`, `visibility_breakdown`, `compute_scale_specific_
facts`, and -- unmodified -- `compare_strategy_reports` itself) unchanged;
`motion_proposal_io.py` handles safe manifest/report I/O and the one
genuinely new decode step (image to downsampled grayscale frame plane);
`motion_proposal_cli.py` wires those to the `onnx-cuda` provider, performing
one inference call per window exactly like the Stage 6.4 CLI.

A finalized motion-proposal window is a `multi_scale_strategy.StrategyWindow`
(`window_kind="tile"`): once a proposal has a source-normalized box it is
geometrically identical to a uniform-grid tile, so cross-window duplicate
suppression, Privacy/Ignore remapping, source-coordinate mapping, and the
scale-specific-facts/visibility-breakdown report sections are reused
completely unchanged rather than reimplemented. A motion-proposal report is
therefore shape-compatible with a Stage 6.4 multi-scale report and the
existing, unmodified `multi-scale-comparison` command can already compare it
against either baseline; see "Three-way decision" below for why a further,
adaptive-specific decision layer still exists on top of that reuse.

## Provider-neutral proposal contract

`MotionProposalStrategyConfig` is the explicit, provider-neutral bounded
proposal contract. It carries no OpenCV, CUDA, ONNX Runtime, or
camera-provider object -- every field is a plain string, bool, int, or
float, the same convention `MultiScaleStrategyConfig` already established:

| Contract fact | Field(s) |
| --- | --- |
| strategy key and version | `strategy_key`, `strategy_version` |
| temporal frame requirements | `requires_predecessor_frame`, `temporal_frame_requirement` |
| source-relative maximum frame gap | `max_predecessor_gap_ms` |
| comparison/downsample dimensions | `comparison_width`, `comparison_height` |
| change threshold | `pixel_delta_threshold` |
| minimum/maximum changed-region area | `min_region_area_fraction`, `max_region_area_fraction` |
| morphology/region-merging configuration | `region_connectivity`, `region_merge_gap_fraction` |
| padding around proposed regions | `context_padding_ratio` |
| proposal aspect-ratio normalization | `target_aspect_ratio` |
| maximum proposals per frame | `max_proposals_per_frame` |
| maximum proposal pixel area | `max_proposal_source_area_fraction` (plus `min_window_dimension_fraction`) |
| proposal ranking rule | `ranking_rule` |
| Privacy/Ignore handling | `privacy_ignore_handling` |
| camera-motion rejection behavior | `camera_motion_rejection`, `max_changed_pixel_ratio`, `global_luminance_shift_threshold` |
| limitations | `limitations` |

`per_window_score_threshold`, `cross_window_iou_threshold`,
`duplicate_suppression_rule`, `max_final_detections`, `edge_padding_
behavior`, `per_window_preprocessing`, and `resource_bounds` mirror the
identical Stage 6.4 fields so a proposal window integrates through the exact
same detector-integration contract a uniform tile already uses.

`FULL_FRAME_PLUS_MOTION_PROPOSALS` is the one implemented preset:
`max_proposals_per_frame=3` (the task's own suggested initial bound),
`comparison_width/height=160x120` (fixed, aspect-independent -- see
"Comparison plane" below), `pixel_delta_threshold=25.0` (the identical
default `mockingbird.motion.scoring.score_zone_motion` already uses),
`context_padding_ratio=0.5` (the identical default
`mockingbird.motion.activity_crop.DEFAULT_CROP_PADDING_RATIO` already uses),
`target_aspect_ratio=1.0` (square, matching both the MDv5 model's square
input and the Stage 6.4 uniform tiles' square shape), and
`max_predecessor_gap_ms=90_000`. None of these defaults were fit to the
current feeder scene; they were chosen as general, product-motivated values
(a periodic/motion-triggered snapshot cadence measured in seconds-to-low-
minutes, not any one camera's configured interval) and then exercised
against the real reviewed temporal cohort described below.

## Comparison plane

Motion proposals never run connected-region extraction against a full-
resolution source frame. `motion_proposal_io.decode_frame_plane` decodes an
already-verified local image, converts it to grayscale, and resizes it to a
fixed `comparison_width`x`comparison_height` regardless of source resolution
or aspect ratio -- deliberately reusing the `FramePlane` shape
(`mockingbird.motion.scoring`/`mockingbird.motion.activity_crop`'s existing
rectangular sequence-of-sequences convention) by type only, not by importing
product motion-evidence behavior. Every changed-region box computed from
that plane is immediately expressed in normalized `[0,1]` space before it
ever leaves `motion_proposal_strategy`, so the fixed comparison size
introduces no scene- or camera-specific coordinate and no aspect-ratio
error: a box at normalized `(0.3, 0.7)` in the downsampled plane is exactly
`(0.3, 0.7)` in the source frame, the same principle
`multi_scale_strategy.map_window_box_to_source` already relies on. Pixel
differencing and connected-region extraction stay pure Python (no NumPy,
OpenCV, or CUDA import), mirroring the existing `mockingbird.motion.scoring`
convention; the plane is kept intentionally small precisely so that a pure-
Python 8-connected flood fill stays fast and bounded regardless of source
resolution.

## Temporal predecessor eligibility

`FrameIdentity` bundles the bounded facts needed to decide whether one frame
may be diffed against a candidate predecessor -- `frame_id`, `sequence_id`,
`source_offset_ms`, `content_hash`, and an optional `provider_generation` --
with no pixel data, camera identity, or Zone reference.
`check_predecessor_eligibility` returns one stable reason code instead of
raising, in this order, so every "handle honestly" case in the task packet
maps to exactly one first-match reason:

1. `temporal_evidence_unavailable` -- the current frame carries no
   `sequence_id` at all (a curated still-image cohort with no sequencing
   produces this for every frame; distinct from "first in a real sequence").
2. `first_frame_no_predecessor` -- the current frame is genuinely first in
   its sequence.
3. `sequence_boundary` -- the candidate predecessor belongs to a different
   `sequence_id`, or the declared order is inverted (a negative gap).
4. `provider_generation_changed` -- the predecessor and current frame
   declare different `provider_generation` values (a live provider's
   generation reset must clear temporal state the same way; see
   `frame_driven_provider.restart_live_generation`).
5. `duplicate_frame_identity` -- the predecessor and current frame share
   the same `frame_id`, or the same non-null `content_hash`.
6. `temporal_evidence_unavailable` -- either frame lacks a recorded
   `source_offset_ms`.
7. `excessive_source_time_gap` -- the gap exceeds `max_predecessor_gap_ms`.

Only a pair that clears every check proceeds to pixel differencing. The
CLI's own `_predecessors_by_frame_id` groups the temporal-cohort manifest's
frames by `sequence_id` (a frame with none is its own singleton, the same
convention `detector_benchmark._sequence_groups` already established) and
orders each group by `sequence_order`/`source_offset_ms`/`frame_id`, so this
benchmark's notion of "in order" agrees with the reused temporal-policy
simulation's notion for the same manifest.

## Deterministic frame differencing and connected-region extraction

`detect_changed_regions` computes, from the two already-decoded comparison
planes only:

1. **Privacy/Ignore masking before differencing.** Declared regions are
   converted to a pixel-exclusion mask over the comparison plane; excluded
   pixels never contribute to the changed-pixel ratio, the mean-delta
   statistic, or any connected region. A pair whose excluded area covers the
   entire plane is rejected `fully_privacy_masked` before any comparison.
2. **Whole-plane statistics and camera-motion/lighting safeguards.** A
   mean absolute delta at or above `global_luminance_shift_threshold`
   rejects the pair `global_luminance_shift`; a changed-pixel ratio at or
   above `max_changed_pixel_ratio` rejects it `excessive_changed_pixel_
   ratio`. Both fire before any region is extracted, so a whole-frame
   brightness shift or a broad camera bump cannot itself produce a grid of
   proposal windows -- it produces zero. Broad scene displacement is caught
   only incidentally through the changed-pixel-ratio guard; no independent
   motion-vector/optical-flow displacement estimate is computed (an
   explicit, honestly-reported `limitations` entry).
3. **Bounded 8-connected component extraction** over the surviving changed-
   pixel mask, via a deterministic stack-based flood fill keyed only by the
   mask itself (raster-scan discovery order, no dict/set hash-order
   dependency). A frame that fragments into more than
   `MAX_RAW_REGIONS_BEFORE_MERGE` (64) raw components is itself unstable
   comparison input and is rejected rather than merged.
4. **Morphology/region-merging** without an OpenCV dependency: any two raw
   components whose bounding boxes fall within `region_merge_gap_fraction`
   of each other are unioned, repeated to a fixed point -- an approximate
   "close" (dilate, merge, erode) using only bounding-box distance.
5. **Minimum/maximum changed-region area filtering** (`min_region_area_
   fraction`/`max_region_area_fraction`, a fraction of total comparison-
   plane pixels): a region too small is noise (`region_area_below_
   minimum`); a region covering more than 35% of the frame is unlikely to be
   one bounded local subject (`region_area_above_maximum`) and is far more
   likely a residual global change the two safeguards above did not already
   catch at the whole-plane level.

## Proposal window generation

For every surviving region, `finalize_proposal_window` performs the
documented step order -- pad, normalize aspect ratio, clip, enforce
minimum/maximum size -- defensively re-clipping (`_clip_preserving_size`,
which shifts a box fully inside `[0,1]` before ever shrinking it, so a
proposal near one edge does not lose width/height, and therefore aspect
ratio, only on the clipped side) after each step:

1. pad by `context_padding_ratio` on every side;
2. normalize toward `target_aspect_ratio` by growing the shorter axis,
   centered on the region;
3. clip to source bounds (preserving size where possible);
4. expand any axis below `min_window_dimension_fraction` of the source
   dimension, centered;
5. shrink (preserving aspect ratio, centered) if the box exceeds
   `max_proposal_source_area_fraction` of the source frame's area;
6. round to the same four-decimal box convention
   `multi_scale_strategy.BOX_COORDINATE_DECIMALS` already uses.

Every finalized candidate (region + box) is then ranked by
`ranking_rule` -- descending changed-pixel count on the pre-padding merged
region, tie-broken by normalized box then a stable region index -- and
bounded to `max_proposals_per_frame`; every candidate beyond that bound is
recorded as a `proposal_count_exceeds_maximum` rejection rather than
silently dropped. Each retained proposal receives a deterministic identity
(`motion-proposal-{frame_id}-{rank:02d}`) and becomes a `StrategyWindow`.

## Detector integration

`motion_proposal_cli._run_benchmark` builds one `FramePacket` per window --
the `full_frame` window reuses the original file path unchanged, exactly
like the Stage 6.4 CLI; each proposal window is cropped once from a shared
full-resolution decode of the source image and re-encoded as its own JPEG,
with the frame's Privacy/Ignore regions remapped into that window's own
local space via the unchanged `multi_scale_strategy.remap_regions_to_
window` -- then runs the existing `OnnxCudaObservationProvider`/
`OnnxModelBundle` once per window. `merge_frame_proposal_windows` is a thin
adapter that assembles `(full_frame_window, *proposal_windows)` and calls
`multi_scale_benchmark.merge_frame_windows` unchanged: every window's
detections are mapped into source coordinates and one deterministic,
input-order-independent, same-broad-class cross-window duplicate-
suppression pass runs before the reused Stage 6.2 pipeline ever sees the
merged set. Because that merge always runs first, a within-frame duplicate
across the full-frame pass and a proposal window can never inflate a
multi-frame temporal-confirmation policy -- those policies only ever see the
single surviving detection per frame, identical to the Stage 6.4 guarantee.

## Report contents

Each `motion-proposal-benchmark-report.json` is shape-compatible with a
Stage 6.4 `multi-scale-benchmark-report.json` (`strategy`, `cohort`,
`threshold_sweep`, `static_false_positive_clusters`, `temporal_policy_
simulation`, `visibility_breakdown`, `scale_specific_facts`, `sample_
sufficiency`, `overall_classification`) and adds two Stage 6.5 sections:

- `proposal_behavior`: `frames_eligible_for_temporal_proposals`, `frames_
  with_proposals`, `total_proposal_count`, `total_proposals_rejected`, and
  `rejection_reason_distribution` (every pair-level and region-level reason
  code observed, sorted, deterministic), plus mean/median `proposed_
  source_area_fraction`.
- `proposal_records`: one entry per retained proposal (`frame_id`,
  `predecessor_frame_id`, `proposal_id`, `rank`, `source_box`, `changed_
  pixel_count`, `source_area_fraction`) -- deterministic provenance, never a
  truth source.

`scale_specific_facts` (reused unchanged from `multi_scale_benchmark`)
already answers "proposal-region recall" at the detection level, because a
motion proposal is a `window_kind="tile"`: `tile_recovered_true_
appearances`/`true_appearances_tile_only`/`tile_introduced_false_
positives`/`tile_border_detection_count` describe proposal-window behavior
specifically, with no Stage 6.5 code duplicating that truth-matching logic.

## Semantic / non-semantic boundary

Identical rule to `detector_comparison`/`multi_scale_benchmark`: absolute
paths, timestamps, output directories, and every runtime/resource fact --
windows inferred per frame, total inference calls, proposal-generation
latency, detector latency, total frame-processing latency, RSS, GPU memory,
CUDA/CPU node counts -- are excluded from `semantic_fingerprint`, reported
only in the separate non-semantic `execution` section.
`build_motion_proposal_semantic_report`'s signature structurally cannot leak
one: it never takes an `execution`/runtime parameter as input at all.

## Three-way decision

`build_adaptive_decision_report` compares the adaptive strategy separately
against both baselines by calling the existing, **unmodified**
`multi_scale_benchmark.compare_strategy_reports` twice (`full_frame` vs
`motion_proposals`, `uniform_tiles` vs `motion_proposals`) rather than
reimplementing precision/recall/small-subject-recall/static-scene/
duplicate-behavior/resource-cost comparison -- reuse is possible because the
motion-proposal report is a structural superset of a multi-scale report.
What this layer adds that plain pairwise comparison cannot:

- **`proposal_region_recall`**: of the true positives the adaptive strategy
  actually found, the fraction found *only* through a proposal window
  (`scale_specific_facts.tile_recovered_true_appearances` /
  `threshold_sweep[0].true_positives`), computed strictly from already-
  produced report fields.
- **Temporal-behavior sufficiency**, independent of the reused cohort-level
  `sample_sufficiency`: `MIN_FRAMES_ELIGIBLE_FOR_TEMPORAL_SUFFICIENCY` (10)
  and `MIN_FRAMES_WITH_PROPOSALS_FOR_TEMPORAL_SUFFICIENCY` (5), both general
  bounds, not fit to the current cohort's size. A strategy whose proposal
  mechanism essentially never had an eligible frame to act on cannot be
  honestly judged "ready" no matter how its few frames turned out.
- The adaptive-specific outcome vocabulary the task packet specifies, which
  intentionally differs in wording and in cardinality from the Stage 6.4
  vocabulary (a new `expand_temporal_benchmark_truth` outcome has no Stage
  6.4 analogue): `retain_full_frame_inference`, `continue_adaptive_
  strategy_offline`, `expand_temporal_benchmark_truth`, `adaptive_strategy_
  ready_for_bounded_live_shadow_trial`, `adaptive_strategy_unsuitable`,
  `insufficient_temporal_data`. Every verdict is hard-coded
  `safe_for_shadow_experimentation=true` and `safe_for_production_
  authority=false`; there is no aggregate winner score, and resource cost
  (non-semantic) never enters `_final_recommendation`'s inputs, mirroring
  every earlier stage's semantic/non-semantic exclusion.

## Report and commands

```sh
python -m mockingbird motion-proposal-benchmark \
  --provider onnx-cuda --provider-config MODEL_BUNDLE.json \
  --frames FRAMES --manifest MANIFEST.json --output OUTPUT_DIRECTORY

python -m mockingbird motion-proposal-decision \
  --full-frame-report FULL_FRAME_REPORT.json \
  --uniform-tiles-report UNIFORM_TILES_REPORT.json \
  --motion-proposal-report MOTION_PROPOSAL_REPORT.json \
  --output OUTPUT_DIRECTORY
```

Both write one atomic report file into a new or empty directory, using the
identical safe-output-path rules as
[detector-calibration-benchmark-contract.md](detector-calibration-benchmark-contract.md).
The first command reads the identical reviewed `CalibrationManifest` schema
the Stage 6.2/6.4 benchmarks already use (`detector_benchmark_io.load_
calibration_manifest`, reused unchanged) -- `sequence_id`/`sequence_order`/
`source_offset_ms` are already first-class fields of that schema, so no new
manifest schema was introduced for temporal sequencing. The second command
also accepts a `full_frame`/`full_frame_plus_uniform_tiles` report produced
by the existing `multi-scale-benchmark` command unmodified. Two runs over
the same cohort and strategy from different absolute roots produce
byte-identical semantic reports; the decision report over the same three
input reports also reproduces identically.

## Reviewed temporal cohort

Adaptive motion proposals require real ordered sequences, which the
existing 70-frame and 12-frame Stage 6.2/6.4 cohorts were not built to
provide (they are curated still images; only 10 of the 70 frames carry a
`sequence_id` at all). A separate, ignored, local-only temporal cohort
(`data/benchmarks/motion-temporal-cohort/manifest.json`, the identical
`CalibrationManifest` schema) was constructed from already-reviewed local
material only -- no new capture, no download, no changed truth in either
existing cohort. See the final report for its exact composition and honest
sufficiency classification.

## Authority and limitations

The module imports no product repository and cannot create or mutate Event,
Visit, MediaAsset, MotionEvidence, evidence link, primary selection,
ReviewLabel, reviewed Observation, Dashboard/export truth, monitoring
policy, or policy revision. It does not select or apply a threshold, does
not create or apply an Ignore region, does not change the Stage 4/6.1
tracker or Stage 6 evidence scoring, and does not change which provider or
strategy MockingBird actually runs. `adaptive_strategy_ready_for_bounded_
live_shadow_trial` characterizes accuracy, static-scene, and proposal-
behavior evidence on the current reviewed cohorts only; it is not a
production-readiness claim and does not by itself authorize a live shadow
trial, a tracker change, or Stage 7.
