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

`CUDAExecutionProvider` is mandatory. Session creation requests only that provider,
sets bounded thread counts, disables CPU execution-provider fallback, and verifies
the selected provider contract. Missing packages, missing CUDA support, load errors,
and inference errors produce bounded error codes. There is no automatic package
installation, model download, network request, or ONNX CPU fallback.

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

The first decoder contract is `xyxy-score-class-v1`: the first named output is a
bounded `N x 6` tensor containing input-space `x1,y1,x2,y2,score,class_index`.
Coordinates are mapped through the declared resize transform to quantized,
normalized source-space boxes. Non-finite/malformed values, invalid classes, invalid
boxes, and oversized output are rejected. Stable output order is frame sequence,
descending quantized score, broad class, normalized box, then stable observation ID.

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
