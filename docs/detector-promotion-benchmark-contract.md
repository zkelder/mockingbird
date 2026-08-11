# Detection and localization model benchmark / promotion v1

Status: completed offline/shadow benchmark; terminal state A, MDv5 native
retained. This contract extends the existing detector calibration, candidate
comparison, multi-scale, Detection Quality Accounting, geometry-lineage, and
counterfactual-lineage contracts. It does not replace them.

## Question and authority boundary

This benchmark asks whether the exact production MDv5 detector remains the
strongest supported choice, whether MockingBird's accepted bounded tiling
strategy repairs its observed small-bird failures, or whether a permissively
licensed modern challenger warrants promotion validation.

The benchmark is filesystem-only and offline:

- it never opens the product database or a Camera Node;
- it never creates Event, Visit, DetectionProposal, ReviewLabel, Observation,
  export, analytics, or training truth;
- it never changes detector configuration, production threshold, provider
  authority, tracking, admission, evidence selection, or Visit semantics;
- a candidate failure is isolated at the adapter boundary;
- benchmark results are evidence for a separate promotion decision, not a
  deployment mechanism.

Production remains the checksum-verified MDv5 ONNX/CUDA provider at threshold
0.1. Only terminal state D, after the existing representative reviewed-truth,
calibration, resource, integration, shadow, monitoring, and rollback gates are
satisfied, could justify a separate production-change milestone.

## Reused infrastructure

The implementation deliberately reuses:

- CalibrationManifest, sweep_thresholds, and the existing IoU matching rules
  for reviewed precision/recall accounting;
- classify_license for the existing permissive/restricted/unacceptable
  license classification;
- FULL_FRAME and FULL_FRAME_PLUS_UNIFORM_TILES from multi_scale_strategy.py,
  including the capped uniform 3x3 tiling, 20-percent overlap, minimum
  960-pixel source dimensions, per-window score floor 0.1, cross-window NMS
  at IoU 0.5, and at most ten windows;
- EvaluationExample governance so reviewed_truth requires a human reviewer
  identity and diagnostic_only can never enter a population denominator;
- the production MDv5 OnnxCudaObservationProvider and accepted model bundle,
  decoder, preprocessing, threshold behavior, and CUDA-only provider check.

mockingbird.observation.detector_promotion adds only provider-neutral model
provenance, normalized candidate detections, governed diagnostic summaries,
failure isolation, and deterministic report composition.
scripts/run_detector_candidate_benchmark.py supplies the benchmark-only
runtime adapters.

## Corpus v1

The ignored local manifest
data/evaluations/detector-promotion-v1/corpus-manifest.json contains 75
checksum-pinned source images and has semantic fingerprint
24bef2dabb37cff8dd4ae984135721aa90647294e2bded0a6e7f83fbdf6bacec.
It is evaluation/holdout material and is prohibited from training use.

| Provenance category | Count | Permitted use |
| --- | ---: | --- |
| Human-reviewed detector-calibration truth | 70 frames: 28 positive, 36 negative, 6 ambiguous; 28 reviewed boxes; 4 scene groups | Reviewed precision, recall, false positives, localization, threshold sweeps, and scene/distance breakdowns |
| Latest combined-attribution identification images | 4 diagnostic-only frames with agent-measured bird ROIs | Per-case engineering diagnostics only; never a population metric or training truth |
| Extra latest-session context control | 1 diagnostic-only image with a visually confirmed production on-bird box | Detection-control diagnostic only; its detector-derived box is not independent IoU truth |
| Detection Quality Accounting truth | 51 reviewed Visit examples referenced, not duplicated | Corroborating Visit/admission presence outcomes only; no localization metric |

The latest live analysis-frame bytes were not retained. The available native
3840x2160 burst images preserve the relevant real source content, but offline
inference on them is not a byte-identical replay of the lower-resolution live
analysis calls. The live counterfactual findings remain proof-complete for the
original calls; the offline runs neither erase nor pretend to reproduce them.

Reviewed negatives include the surviving feeder-scene clutter,
branches/bark/vegetation, grass/foliage, and recurring static shepherd-hook
confusors. The exact source images for the earlier approximately 0.935
pavement/dappled-shadow, 0.795 clutter, and 0.544 feeder-hardware detections
were not retained and are not replaced by merely related images. The latest
session's failure to reproduce a new high-confidence environmental false
positive is retained as a non-finding.

## Candidate and input contract

Every candidate records model and architecture identity, exact weights SHA-256
and source, model and weights license, redistribution status, runtime/package
identity and package checksum when available, backend, native input,
preprocessing, postprocessing, score floor, taxonomy, and input strategy.

Every normalized detection records:

- broad class (animal, person, vehicle, or other);
- native label and confidence;
- source-relative xyxy box, validated inside [0, 1];
- model key/version, backend, and input-strategy identity;
- source frame identity.

All models receive identical decoded source pixels for a given full-frame run.
The bounded tile experiment derives tiles from those same pixels through the
accepted strategy. Each model's official preprocessing then maps a full frame
or tile to its native fixed input. MDv5 uses its exact 1280x1280 letterbox;
MDV6 Apache uses its official 640x640 transform; RF-DETR Small uses its
official 512-pixel path. None of these verified runtimes exposes a separate
higher-native-resolution switch, so the accepted tile path is the explicit
real-pixel small-object experiment. No generative upscaling is used.

Full-frame and tile outputs are projected back to source coordinates and
merged with the accepted cross-window IoU rule. Native taxonomy is preserved
alongside the broad class. Raw confidence values are not treated as calibrated
across models; each model is evaluated at its documented operating point and
over its own bounded threshold sweep.

## Tested models and exact artifacts

| Candidate | Weights SHA-256 | Runtime/package | License status |
| --- | --- | --- | --- |
| Production MDv5a ONNX | b03ef7968a54be1ae15e6987d520be0fa3cd71d8d229ec3aeb0bf0faa710abbc (source PT fe3e90e4b1955821ab7c1f88b446dc0c8cb25e109fdd1872916a55305294a5ef) | ONNX Runtime GPU 1.28.0; accepted raw YOLOv5 decoder | MIT; eligible |
| MDV6-apa-rtdetr-c | 4814cdbc9a0dbf20e4b04495f060176d8340b00d182fc98ce808a4d14a2a6fce (official MD5 3992888e26f627ee5a4ff9f116be97c3) | PyTorchWildlife 1.3.0 wheel SHA-256 3215c1041ae52481a96d25dbe3fa509a3db5a814395a08bb2e0ab259a260d57d | Apache-2.0 model/weights; eligible |
| MDV6-apa-rtdetr-e | 8017129225455be75998195453282f1984aa1c46ebb77b05dd7db97f1bf79117 (official MD5 6f8855d147ef17dc123c2f21fcb554b7) | Same verified PyTorchWildlife package | Apache-2.0 model/weights; eligible |
| RF-DETR Small | d81979a9213a2109345158ce9232668df4c1ae52e9b8db3f2ec0a8cbad959b33 (registry MD5 fb37061c1af7bace359c91b723a8d5c1) | RF-DETR 1.8.3 wheel SHA-256 345e55b897ce590464e64ae4750e60b668436cbc6bf58d87f438895a93c3e9a4 | Apache-2.0 designated Small weights/package; eligible |

MDV6 Compact and Expanded are the permissive wildlife-specific successors
most likely to address the observed failure. RF-DETR Small is one bounded,
modern general-detector challenger sized for the actual 8-GB GPU. A second
general model was not added after these covered both missing roles. YOLO26 was
not run: its AGPL/Enterprise implications prevent promotion eligibility
without a separate licensing decision, and it did not fill an uncovered
benchmark role.

The MDV6 adapter uses the official PyTorchWildlife model and YAML, but injects
PResNet.pretrained=False before constructing the model because the complete
verified checkpoint overwrites every backbone weight and upstream otherwise
performs a redundant network download. The candidate checkpoint is unchanged.
Official MDV6 postprocessing may exceed source bounds by fractions of a pixel;
the adapter explicitly clamps those coordinates before normalization.

RF-DETR loads the verified official Small artifact, but runtime 1.8.3 reports
one absent randomly initialized _kp_active_mask parameter and that the model
has not been optimized for inference. Those warnings are deployment evidence,
not silently suppressed. The parameter is associated with a keypoint mask, but
the partial-load warning still prevents treating this adapter as integration-
ready without upstream/runtime reconciliation.

## Metric and determinism rules

Only the 70 reviewed calibration frames contribute reviewed metrics. The
accepted scorer reports true/false detections, precision, animal recall,
positive-frame recall, false positives per negative frame, confidence
distributions, scene and subject-distance breakdowns, and duplicate counts.
Localization adds the best IoU per reviewed box plus recall at IoU 0.25, 0.50,
and 0.75.

Diagnostic-only rows report hit/miss at IoU 0.50, best on-bird confidence,
maximum overlap, highest-confidence off-ROI detection, off-ROI count, and
latency. They always state creates_population_metric=false.

Semantic output contains model/corpus/strategy identity and sorted normalized
detections. Startup, host/platform, timing, throughput, GPU allocation, and
artifact byte size live only under execution; changing those facts cannot
change the semantic fingerprint. Report construction also recursively removes
execution/resource/timing fields before hashing and sorts candidates by key.

## Reproduction

The local model/runtime/config and result artifacts follow existing ignored
evaluation-data retention:

    data/models/detector-promotion-v1/
    data/runtime/detector-promotion-v1/
    data/evaluations/detector-promotion-v1/

One run is invoked as:

    .venv/bin/python scripts/run_detector_candidate_benchmark.py \
      --candidate-config data/evaluations/detector-promotion-v1/mdv6-c-config.json \
      --manifest data/evaluations/detector-promotion-v1/corpus-manifest.json \
      --strategy full_frame \
      --output data/evaluations/detector-promotion-v1/runs/mdv6-c-full-frame.json

Before inference, the runner verifies the configured weights checksum, every
manifest image checksum, and every source dimension. A mismatch fails closed.
Candidate adapters run independently, so an unavailable third-party runtime
does not authorize fallback or contaminate another result.

## Promotion states

- A — MDv5 native retained: incumbent remains strongest on valid evidence.
- B — MDv5 multi-scale candidate: accepted tiling materially repairs the
  failure at acceptable precision/resource cost.
- C — MDV6/other challenger ready for promotion validation: clearly stronger,
  but reviewed holdout/shadow evidence is incomplete.
- D — new detector promotion justified: the formal promotion contract is
  genuinely satisfied.
- E — insufficient benchmark truth: mechanism works but evidence cannot select
  an engineering winner responsibly.

The v1 evidence selects A. The detailed measurements and next gate are in
[detector-promotion-benchmark-report.md](detector-promotion-benchmark-report.md).
