# Multi-scale detector benchmark contract

Status: Observation Engine v2 Stage 6.4 provider contract.

## Boundary

`mockingbird.observation.multi_scale_strategy` and
`mockingbird.observation.multi_scale_benchmark` characterize whether a
bounded multi-scale inference strategy (an optional additional pass over
overlapping source-frame tiles, alongside the existing full-frame pass)
recovers small or distant subjects that full-frame inference at fixed model
input resolution misses. It is offline, deterministic, and diagnostic only:
no camera, Camera Node, live monitoring, worker, or product database is
opened, and no runtime threshold, Ignore region, tracker, or default-provider
configuration is read or mutated. Every output remains `shadow_only=true`,
`creates_truth=false` evidence with no production proposal authority, and
does not change which detector or strategy MockingBird actually runs.

The module split mirrors Stage 6.2/6.3: `multi_scale_strategy.py` is pure
window geometry and coordinate normalization with no CUDA, ONNX Runtime, or
model-specific type anywhere in its contract; `multi_scale_benchmark.py` is
pure report assembly that reuses the existing Stage 6.2
`detector_benchmark` pipeline (`classify_frame`, `sweep_thresholds`,
`cluster_static_false_positives`, `simulate_temporal_policies`,
`classify_sample_sufficiency`) unchanged over already-merged, already-
cross-window-suppressed detections; `multi_scale_benchmark_io.py` handles
safe report I/O (reusing `detector_benchmark_io.load_calibration_manifest`
unchanged); `multi_scale_cli.py` wires those to the `onnx-cuda` provider,
performing one inference call per window.

## Strategy contract

`MultiScaleStrategyConfig` is the explicit, provider-neutral strategy
contract: `strategy_key`/`strategy_version`, `full_frame_enabled`,
`tile_width`/`tile_height` (pixels), `horizontal_overlap`/`vertical_overlap`,
`max_tiles_per_frame`, `min_source_width`/`min_source_height`,
`tile_selection_method`, `edge_padding_behavior`,
`per_window_preprocessing` (a descriptive fact -- "reuses the configured
detector provider's own preprocessing contract unchanged" -- never a live
provider reference), `per_window_score_threshold`,
`cross_window_iou_threshold`, `duplicate_suppression_rule`,
`max_final_detections`, `resource_bounds`, and `limitations`. Two presets
are implemented: `FULL_FRAME` (today's production baseline, one window) and
`FULL_FRAME_PLUS_UNIFORM_TILES` (the full frame plus a uniform overlapping
tile grid, 640x640 tiles at 20% overlap, capped at 9 tiles, skipped below a
960x960 source). A third strategy is explicitly out of scope for this stage.

## Window generation

`windows_for_frame` computes window geometry from a frame's own
`source_width`/`source_height` only -- no Zone, camera identity, or other
scene-specific coordinate ever enters this function. Below
`min_source_width`/`min_source_height`, tiling degrades gracefully to
full-frame-only rather than upsampling a too-small source. The uniform grid
reuses the exact tiling formula the preserved local small-bird tiling probe
(`mockingbird.detectors.small_bird_benchmark.tiled_coordinate_boxes`, kept
untouched and uncommitted) already validated -- tile size derived from a
column/row count so the grid's union is always exactly the full source area
-- generalized to derive that count from a target pixel tile size instead of
a fixed count, and capped so `columns * rows` can never exceed
`max_tiles_per_frame` (`isqrt(max_tiles_per_frame) ** 2 <= max_tiles_per_frame`
bounds each axis independently, a mathematical guarantee independent of
source aspect ratio). That JPEG-encoding/live-runner-coupled probe's other
functions (`aspect_preserving_zone_jpeg`, `run_strategy`,
`evaluation_metrics`) are not reused: they are coupled to the separate
official-package `megadetector_adapter` byte-input runner and that probe's
own less rigorous truth format, not the `onnx-cuda` ONNX Runtime CUDA
provider or the Stage 6.2 `CalibrationManifest` schema this benchmark uses.

## Detection normalization and cross-window suppression

Every window's detections are decoded by the unmodified existing provider
preprocessing/decode path, then `map_window_box_to_source` maps each box
from that window's own local [0,1] space into the source frame's normalized
space (clipped, quantized to the same four-decimal convention the MDv5 raw
decoder already uses). `suppress_cross_window_duplicates` then performs one
deterministic, input-order-independent, same-broad-class greedy NMS pass
over the whole merged per-frame set: a later (lower- or equal-scored)
detection that overlaps an already-kept one at or above
`cross_window_iou_threshold` is always the one suppressed, so the same
physical animal seen by two windows collapses to one observation regardless
of window or input order, while two distinct nearby animals both survive.
`remap_regions_to_window` intersects and remaps each frame's reviewed
Privacy/Ignore regions into every window's own local space before that
window's own inference call, so masking applies per window, not only to the
full frame. Stable output ordering is frame sequence (by `frame_id`, set by
the caller), descending quantized score, broad class, normalized source-space
box, window identity, then observation id.

Because cross-window suppression always runs before the reused Stage 6.2
pipeline sees the merged detections, a within-frame duplicate across two
overlapping windows can never inflate a multi-frame temporal-confirmation
policy (`two_detections`, `two_distinct_frames`, ...): those policies only
ever see the single surviving detection per frame.

## Report contents

Each per-strategy `multi-scale-benchmark-report.json` reuses the Stage 6.2
report shape (`threshold_sweep` -- a single row at the strategy's own
`per_window_score_threshold`, not a full grid sweep -- `static_false_positive_
clusters`, `temporal_policy_simulation`, `sample_sufficiency`,
`overall_classification`) and adds two Stage 6.4 sections: `visibility_
breakdown` (recall bucketed by the manifest's own reviewed `occlusion`/
`blur`/`clipped` facts, each bucket -- including "unknown" when a cohort
never recorded one -- reported explicitly rather than folded into a
misleading denominator) and `scale_specific_facts` (full-frame-only/
tile-only/both true-appearance counts, tile-recovered true appearances,
tile-introduced false positives, tile-border detection count, cross-window
duplicate-suppression counts before/after, and median source/inferred-window
subject pixel area).

## Semantic / non-semantic boundary

Identical rule to `detector_comparison`: absolute paths, timestamps, output
directories, and every runtime/resource fact -- windows inferred per frame,
total inference calls, latency, RSS, GPU memory, CUDA/CPU node counts, model
artifact byte size -- are excluded from `semantic_fingerprint`, reported only
in the separate non-semantic `execution` section.
`build_multi_scale_semantic_report`'s signature structurally cannot leak
one: it never takes an `execution`/runtime parameter as input at all.
`compare_strategy_reports` (comparing a candidate strategy's report against
`full_frame`'s) reads `execution.max_windows_per_frame` from each input
report only to compute a `resource_cost` classification, which -- like
`detector_comparison`'s `RuntimeComparison.classification` -- is written
only to the comparison's own non-semantic `execution.resource_facts`, never
to the semantic payload, and is never an input to `final_recommendation`. A
constructed regression test proves two otherwise-identical strategy
comparisons that differ only in resource facts (even differences crossing
every acceptable/degraded/unacceptable boundary) produce byte-identical
`semantic_fingerprint` and `final_recommendation`.

`duplicate_behavior` (acceptable/degraded/unacceptable) *is* semantic: it is
derived from `scale_specific_facts.duplicates_before_suppression`/
`duplicates_after_suppression`, which are deterministic detection counts
from a fixed model/cohort/strategy, not a wall-clock or hardware
measurement -- the same category of fact as `precision`/`recall` themselves.

## Decision classifications and final recommendation

Each candidate strategy is classified independently: `recall`,
`precision`, `small_subject_recall` (read from the `far` `subject_size_
breakdown` bucket; `insufficient_truth` when that bucket is empty on either
side), and `static_scene_behavior` (recurring static false-positive cluster
count, lower is better) are `better`/`equivalent`/`worse`/`insufficient_
truth`; `duplicate_behavior` and (non-semantic) `resource_cost` are
`acceptable`/`degraded`/`unacceptable`/`insufficient_evidence`. There is no
aggregate winner score. `final_recommendation` is one of `retain_full_frame_
inference`, `continue_tiled_strategy_offline_evaluation`, `tiled_strategy_
ready_for_bounded_live_shadow_trial`, `tiled_strategy_unsuitable`, or
`insufficient_reviewed_small_subject_data`, each hard-coded
`safe_for_production_authority=false`.

## Report and commands

```sh
python -m mockingbird multi-scale-benchmark \
  --strategy {full_frame,full_frame_plus_uniform_tiles} \
  --provider onnx-cuda --provider-config MODEL_BUNDLE.json \
  --frames FRAMES --manifest MANIFEST.json --output OUTPUT_DIRECTORY

python -m mockingbird multi-scale-comparison \
  --baseline-report FULL_FRAME_REPORT.json \
  --candidate-report CANDIDATE_STRATEGY_REPORT.json --output OUTPUT_DIRECTORY
```

Both write one atomic report file into a new or empty directory, using the
identical safe-output-path rules as
[detector-calibration-benchmark-contract.md](detector-calibration-benchmark-contract.md).
Two runs over the same cohort and strategy from different absolute roots
produce byte-identical semantic reports; comparing those reports' outputs
also reproduces identically.

## Supplemental small-subject cohort

The Stage 6.2 70-frame cohort's own `far` (small/distant) bucket has exactly
one frame -- not a statistically meaningful comparison. A supplemental,
ignored, local-only cohort
(`data/benchmarks/small-subject-cohort/manifest.json`, same
`CalibrationManifest` schema) adds 12 further frames built from real local
product `MediaAsset`s that already carried ReviewLabel truth predating and
disjoint from the 70-frame cohort: small/perched/partially-occluded birds,
a motion-blurred clipped bird, two genuinely small (`far`-bucket, <=96px
longest side) subjects, confirmed empty hard negatives, one frame kept
`ambiguous` where independent review could not corroborate the product's
own label, and one frame marked `yes`-but-unscorable where a plausible
subject could not be boxed with confidence. One frame's whole-frame truth
(`yes`, with a box) explicitly overrides what its Visit-level `false_
positive` product label would naively suggest, for the same documented
reason Stage 6.2 already established: a Visit-level correction is scoped to
one motion track, not a whole-frame claim. This cohort is evaluated
separately from, and never merges into or edits, the unchanged 70-frame
cohort; its own `sample_sufficiency` is reported honestly (well below this
benchmark's minimum bounds on its own) rather than presented as adequate.

## Authority and limitations

The module imports no product repository and cannot create or mutate Event,
Visit, MediaAsset, MotionEvidence, evidence link, primary selection,
ReviewLabel, reviewed Observation, Dashboard/export truth, monitoring
policy, or policy revision. It does not select or apply a threshold, does
not create or apply an Ignore region, does not change the Stage 4/6.1
tracker or Stage 6 evidence scoring, and does not change which provider or
strategy MockingBird actually runs. `tiled_strategy_ready_for_bounded_live_
shadow_trial` characterizes accuracy and static-scene evidence on the
current reviewed cohorts only; it is not a production-readiness claim and
does not by itself authorize a live shadow trial, a tracker change, or
Stage 7.
