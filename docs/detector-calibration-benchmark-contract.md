# Detector precision calibration benchmark contract

Status: Observation Engine v2 Stage 6.2 provider contract.

## Boundary

`mockingbird.observation.detector_benchmark` measures MDv5 animal-class precision
and recall against a reviewed, ignored local image cohort. It is offline,
deterministic, and diagnostic only: no camera, Camera Node, live monitoring,
worker, or product database is opened, and no threshold, Ignore region, or
tracker configuration is read or mutated. Every output remains
`shadow_only=true`, `creates_truth=false` evidence with no production
proposal authority; see [roadmap.md](roadmap.md) for how this sits after
Stage 6.1 and strictly before the still-blocked Stage 7.

The module is split the same way as the Stage 2 replay benchmark:
`detector_benchmark.py` is pure (no filesystem, network, or model-runtime
import; every function operates on already-decoded `DetectionObservation`
facts), `detector_benchmark_io.py` handles safe manifest/frame loading and
atomic report writes, and `detector_benchmark_cli.py` wires those to the
existing `onnx-cuda` provider. It reuses deterministic `FramePacket`
construction, the existing `OnnxCudaObservationProvider` /
`OnnxModelBundle` decode path, and the same box-IoU convention as the Stage 2
replay's detection metrics, but it does not run the frame-driven tracker,
evidence scoring, or Visit-proposal matcher; those remain
[frame-driven-shadow-provider-contract.md](frame-driven-shadow-provider-contract.md)
and
[multi-frame-evidence-scoring-contract.md](multi-frame-evidence-scoring-contract.md)
concerns.

## Reviewed calibration manifest

A versioned JSON manifest (`schema_version`/`version` 1) separate from the
Stage 2 replay `BenchmarkManifest`: it carries reviewed per-frame truth for a
curated still-image cohort, not appearances/Visits for a continuous replay.
Each frame records a stable logical `frame_id`, a relative `image` path,
optional declared `width`/`height`/`content_hash` (cross-checked against the
decoded file the same way `replay_io` does), `animal_present` (`yes`/`no`/
`ambiguous`), zero or more reviewed `boxes` (each an `animal`/`person`/
`vehicle`-style `broad_class` plus a normalized box), `scorable`,
visibility/occlusion/blur/clipping/distance facts, `privacy_ignore_regions`,
`scene_group`, optional `sequence_id`/`sequence_order`/`source_offset_ms`,
and free-text `provenance`/`reviewer_note`. An optional top-level
`scene_static_structures` map lets a reviewer attach a human-identified
static-object label (for example the specific feeder pole) to a scene group
for later cross-referencing against an algorithmic cluster; it is descriptive
only.

A "yes" frame that is `scorable` must carry at least one reviewed box (a
reviewer confident enough to say "yes" but not to draw a box should mark the
frame unscorable instead); a "no"/"ambiguous" frame must carry none. Ambiguous
and unscorable frames are excluded from every precision/recall denominator --
never silently treated as negatives -- and are reported as their own bounded
count. Absolute paths, symlinks, path traversal, duplicate frame ids, and
frame-count/box-count/threshold-count limits are rejected the same way the
Stage 2 replay manifest loader rejects them.

## Threshold sweep without re-running inference

The provider decodes each frame exactly once, at one safe low anchor score
threshold strictly below the lowest requested sweep value
(`anchor_score_threshold`). Because class-aware NMS only ever lets a
higher-scored box suppress a lower-scored one, filtering that one decoded set
by `score >= threshold` for each row of the grid reproduces exactly what a
fresh decode at that threshold would keep; the sweep is therefore pure
post-processing over already-decoded, already-NMS'd observations, with no
additional CUDA or CPU model work per threshold. `effective_threshold_grid`
merges the model bundle's own currently configured `score_threshold` into a
fixed general grid (several lower and higher values, `DEFAULT_THRESHOLD_GRID`),
bounded to `(0, 1]`, deduplicated, and always including the live configured
value; the exact grid is recorded in the semantic report.

For every threshold, `classify_frame` matches predicted animal boxes against
reviewed truth at one explicit IoU (`MATCH_IOU_THRESHOLD = 0.5`, shared with
the Stage 2 replay's own box metrics) and separates outcomes into:

- true positive
- false positive (on a negative frame, or an extra unmatched box on a
  positive frame)
- false negative, further split into **below-threshold** (a raw anchor-level
  detection overlapped the truth box but scored under this row's threshold),
  **privacy-masked** (every overlapping raw detection was centered inside a
  declared Privacy/Ignore region, so no threshold change would recover it),
  and **true miss** (no overlapping detection existed even at the anchor
  floor -- a detector-capability gap, not a threshold problem)
- duplicate (a same-class box at or above the match IoU against an
  already-kept, equal-or-higher-scored box in the same frame; collapsed to
  one counted detection, reported separately)
- privacy-excluded (centered inside a declared Privacy/Ignore region;
  excluded from precision/recall, reported as its own count)

`sweep_thresholds` aggregates this per threshold into scorable positive/
negative frame counts, TP/FP/FN/duplicate/privacy-excluded counts, precision,
recall, F1 (descriptive only -- never a selection input), false positives per
negative frame, positive-frame recall, true/false score distributions, a
scene-group breakdown, and a 95% Wilson-score confidence interval for
precision/recall that is withheld (`None`) below
`MIN_CONFIDENCE_INTERVAL_SAMPLE` rather than reported misleadingly narrow or
wide.

## Static false-positive clustering

`cluster_static_false_positives` groups false-positive detections that
recur across frames sharing the same `scene_group`, using bounded normalized
box IoU (`CLUSTER_IOU_THRESHOLD`), centroid proximity
(`CLUSTER_CENTROID_THRESHOLD`), and a near-identical score band
(`CLUSTER_SCORE_BAND`); different scene groups never cluster together. A
group is only reported as a recurring cluster once it reaches
`CLUSTER_MIN_RECURRENCE` members; smaller groups remain an
`independent_false_positive_count` instead. A cluster whose representative
box overlaps a manifest-declared `scene_static_structures` entry carries that
reviewer-assigned label. Clustering is diagnostic evidence only: it never
creates, updates, or implies an Ignore region.

## Temporal confirmation-policy simulation

`simulate_temporal_policies` re-classifies already-scored detections (no
inference, no tracker) grouped by the manifest's own `sequence_id` (a frame
without one is its own single-frame sequence) against bounded policies:
`single_detection`, `two_detections`, `two_distinct_frames`,
`minimum_temporal_span`, `spatial_coherence`, `score_aggregation`, and
`detector_plus_tracker_confirmation`. A sequence's expected true appearance is
derived from its own frame-level `animal_present` truth (this cohort is a
curated still-image set, not a continuous replay with independently reviewed
Visit boundaries, so appearance grouping is coarser than
[observation-replay-benchmark-contract.md](observation-replay-benchmark-contract.md)'s
matcher). Each policy reports confirmed true appearances, confirmed false
episodes, missed true appearances, fragmentation where scorable (only when
every qualifying frame in a sequence carries `source_offset_ms`), and a
precision/recall tradeoff. `detector_plus_tracker_confirmation` is always
reported unsupported: evaluating it honestly requires real `TrackUpdate`
facts from the Stage 4 frame-driven tracker over a continuous ordered replay,
which this benchmark does not run. This never changes the real shadow
tracker's configuration or behavior.

## Preprocessing comparison

`compare_preprocessing` compares the configured `resize_mode` against the
other value already supported by the `onnx-cuda` bundle contract (`stretch`
vs. `letterbox`) at the configured threshold, using the same fixed model
input dimensions -- the currently exported MDv5 bundle has a fixed 1280x1280
graph, so an alternative *input size* is unsupported and reported as such
rather than changing the model. This reuses the same `.onnx` file for a
second decode pass; no new architecture or model artifact is introduced.

## Recommendation classification

`classify_recommendations` emits one entry per candidate action --
`threshold_increase`, `threshold_decrease`, `temporal_confirmation_change`,
`recurring_static_false_positive_region`, `preprocessing_investigation`,
`detector_replacement_evaluation`, `insufficient_reviewed_data` -- each with
its own verdict, supporting metrics, regressions, sample-size limitations,
`safe_for_shadow_experimentation=true`, and `safe_for_production_authority`
hard-coded `false`. There is no aggregate winner score, and F1 is
structurally excluded from every decision input (only precision, recall,
false-positive rate, and sample size feed a verdict).

## Sample sufficiency

`classify_sample_sufficiency` requires a bounded minimum count of scorable
positive and negative frames and of distinct scene groups, and separately
flags a scene group whose positive boxes collapse onto very few distinct
locations (`MIN_DISTINCT_POSITIVE_LOCATIONS`) as likely repeated captures of
the same visit rather than independent examples. `overall_classification`
reports `DETECTOR_CALIBRATION_INSUFFICIENT_DATA` whenever any bound fails,
and `DETECTOR_CALIBRATION_CHARACTERIZED` otherwise; neither status is a
production-readiness claim.

## Report and command

```sh
python -m mockingbird detector-benchmark \
  --provider onnx-cuda \
  --provider-config MODEL_BUNDLE.json \
  --frames FRAMES \
  --manifest MANIFEST.json \
  --output OUTPUT_DIRECTORY
```

Writes one atomic `detector-benchmark-report.json` into a new or empty
directory, using the same safe-output-path rules as
[observation-replay-benchmark-contract.md](observation-replay-benchmark-contract.md).
The semantic report covers the manifest fingerprint, threshold grid, full
threshold sweep, static clusters, temporal simulation, preprocessing
comparison, sample sufficiency, overall classification, and recommendations.
Absolute paths, host/PID facts, wall-clock timestamps, execution duration,
and selected-execution-provider/latency facts remain outside
`semantic_fingerprint`, in a separate `execution` section, unchanged from the
Stage 2/3 convention. Two runs over the same cohort from two different
absolute roots produce byte-identical semantic reports.

## Authority and limitations

The provider imports no product repository and cannot create or mutate
Event, Visit, MediaAsset, MotionEvidence, evidence link, primary selection,
ReviewLabel, reviewed Observation, Dashboard/export truth, monitoring policy,
or policy revision. CUDA-only execution remains mandatory, verified the same
way as
[onnx-cuda-shadow-provider-contract.md](onnx-cuda-shadow-provider-contract.md).
This benchmark does not select or apply a threshold, create or apply an
Ignore region, replace or retrain a detector, or change the Stage 4/6.1
tracker or Stage 6 evidence scoring; those remain later, separately scoped
decisions gated on this benchmark's evidence plus a materially larger and
more representative reviewed cohort than the one committed alongside this
contract.
