# ONNX Runtime CUDA Shadow Provider Contract

Observation Engine v2 Stage 3 implements `onnx-cuda` as an optional,
replay-driven detection provider. It consumes the deterministic Stage 2
`FramePacket` sequence and emits provider-neutral `DetectionObservation` evidence.
It is not a live pipeline and has no tracking, evidence-selection, Visit-proposal,
or product-write authority.

## Optional runtime and capability probe

Core imports, Snapshot observation, and replay manifest validation do not import or
initialize ONNX Runtime. The provider imports it lazily only for a probe or explicit
session load. The probe reports provider/runtime versions, available and selected
execution providers, CUDA and model-bundle status, device/accelerator, shadow mode,
and unsupported capabilities. It does not load a model, touch a camera, start a
worker, or write state.

`CUDAExecutionProvider` is mandatory and must be registered first. Session creation
requests CUDA, sets bounded thread counts, and sets
`session.disable_cpu_ep_fallback=1`. A registered `CPUExecutionProvider` is not by
itself evidence of fallback. Bounded ONNX Runtime profiling classifies actual model
node execution as `cuda_only_verified`, `mixed_cuda_cpu_execution`, or
`cuda_execution_verification_insufficient`; activation accepts only the first, with
at least one CUDA node and zero CPU or unattributed model nodes. Raw profile paths and
traces stay temporary and non-semantic. Missing CUDA support, load errors, inference
errors, mixed execution, and insufficient assignment evidence produce bounded error
codes. There is no automatic package installation, model download, network request,
or ONNX CPU fallback.

## Portable model bundle

The developer supplies a JSON manifest next to one ignored local `.onnx` file. The
schema records:

- schema version, model key/version, `ONNX` format, and SHA-256 model fingerprint;
- license, redistribution, taxonomy, provenance, and limitations;
- input tensor name/dimensions, float32 dtype and input scale, NCHW layout,
  RGB/BGR order, channel normalization, and deterministic stretch or letterbox
  behavior including fill color;
- output tensor names, the explicit decoder key, broad classes, the explicit
  animal-class subset, thresholds, result bound, and compatible providers.

Paths must be relative, contained regular files; symlinks, hash mismatches,
unsupported schema/format/decoder values, unsafe dimensions, and malformed fields
are rejected. Model paths never enter the semantic report. Model weights and GPU
caches are not committed.

The compatibility decoder contract remains `xyxy-score-class-v1`: the first named
output is a bounded `N x 6` tensor containing input-space
`x1,y1,x2,y2,score,class_index`.

The model-specific `megadetector_v5_yolov5_raw_v1` decoder consumes one bounded
`[1,N,8]` MDv5/YOLOv5 tensor whose sigmoid probabilities have already been applied.
Columns are center `x,y,width,height`, objectness, and animal/person/vehicle class
probabilities. It uses strict objectness and final-confidence thresholds, computes
`objectness * best_class_probability`, applies class-aware NMS at the bundle's IoU
threshold, and bounds final detections. The bundle fixes raw output shape, source and
ONNX fingerprints, the `animal, person, vehicle` class order, animal subset, score
threshold, NMS threshold, and candidate/detection limits. Coordinates are reversed
through the declared classic letterbox transform, clipped and rounded in source
pixels, then converted to normalized boxes with MDv5's four-decimal coordinate and
three-decimal confidence truncation.

Both decoders reject non-finite or malformed values, invalid classes/boxes, and
oversized output. Stable output order is frame sequence, descending quantized score,
broad class, normalized box, then stable observation ID. Neither decoder emits
species truth or product writes.

## Replay and report boundary

Use the existing command with explicit local configuration:

```sh
python -m mockingbird replay-benchmark \
  --provider onnx-cuda \
  --frames FRAMES \
  --manifest BENCHMARK.json \
  --provider-config MODEL_BUNDLE.json \
  --output OUTPUT_DIRECTORY
```

The semantic report records the provider contract, capabilities/limitations, model
and bundle fingerprints, preprocessing/postprocessing versions, normalized
detections, detection metrics, and absence of truth authority. Latencies, execution
duration, and selected execution providers are non-semantic execution facts. Visit
metrics are `not_evaluated` because Stage 3 emits no Visit proposals. Detection
truth metrics are evaluated only when bounded frame-indexed box annotations exist.

The provider module has no product repository dependency and cannot create Event,
Visit, MediaAsset, MotionEvidence, evidence links, primary selections, Review Queue
items, ReviewLabel, Observation, Dashboard/export truth, or monitoring-policy
revisions. Explicit close releases its one session; no background worker survives
replay.

Hardware-free tests use fake runtimes and sessions. Local RTX validation is a
separate ignored two-run activation check and must not be claimed until a compatible
local bundle is explicitly supplied. TensorRT, live streams, Camera Node analysis,
continuous tracking, and Visit authority are later stages.
