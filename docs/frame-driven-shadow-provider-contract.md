# Frame-driven detector/tracker shadow-provider contract

Observation Engine v2 Stage 4 implements `frame-driven-onnx-cuda` as a
deterministic ordered-frame replay provider. It schedules the existing local
ONNX Runtime CUDA detector from source-relative timestamps, updates a
provider-neutral tracker on every supplied analysis frame, retains bounded
portable evidence references, and emits shadow-only `VisitProposal` facts. It
does not consume a live stream or hold production proposal authority.

## Provider and scheduling boundary

The provider uses one explicit versioned configuration that points to the
existing portable ONNX model bundle by a contained relative path. Its semantic
settings declare source nominal FPS, idle and candidate detector FPS, the
single latest detector-work bound, frame-gap and tracker-expiry bounds,
occlusion tolerance, confirmation policy, active-track cap, and evidence-ring
cap. Source nominal FPS must agree with the replay manifest.

Scheduling uses `FramePacket.source_offset_ms`, never wall-clock time. Idle
replay runs the heavyweight detector at the baseline cadence. A tentative or
confirmed animal track selects the bounded candidate cadence. The tracker still
receives every distinct ordered analysis frame. Work is synchronous and
single-pending in Stage 4, so historical detector frames cannot accumulate
behind newer replay input. When every track terminates, cadence returns to idle
and transient track/evidence state is released.

Privacy/Ignore exclusions are normalized input facts. Their pixels are masked
before ONNX preprocessing, and any returned box centered inside an exclusion is
discarded before tracking.

## Provider-neutral tracking

`ProviderNeutralFrameTracker` exposes only normalized geometry, broad class,
source-relative time, frame identity, confidence/provenance, detector
confirmations, tracker-support count, lifecycle state, and stable generation
identity. ONNX Runtime, NVIDIA, Pillow, NumPy, and future tracker-library types
do not enter Observation Engine product contracts.

The first implementation uses deterministic one-to-one spatial association
with predicted centroid motion and a small portable patch-support adapter on
intervening frames. Association combines class compatibility, normalized box
overlap, predicted centroid displacement, and an ambiguity margin. A later
ByteTrack-class implementation may replace this adapter behind the same
contract.

Tracks are bounded and deterministic:

- `tentative`: initial animal evidence without enough temporal support;
- `confirmed`: one configured strong detection plus coherent tracker support,
  or the configured number of coherent detector confirmations;
- `temporarily_lost`: a bounded miss after tentative or confirmed support;
- `ended`: a confirmed episode closed by loss, duration, reset, or replay end;
- `rejected`: an unconfirmed episode that expired without sufficient support.

Repeated frame identities never add support. Active count, missed frames,
source-time gaps, episode duration, and association ambiguity are bounded.
Terminal reasons are `confirmed_visit`, `insufficient_support`, `tracker_lost`,
`maximum_duration`, `ambiguous_association`, `provider_reset`, or
`end_of_replay` as applicable. A terminated generation is never revived.

## Shadow proposal and evidence boundary

A confirmed generation produces exactly one proposal when its episode closes.
The deterministic proposal key is also its idempotency key. It records Stream,
source-relative start/end, broad class, generation, supporting frame identities,
detector/tracker provenance, provider version, evidence references, terminal
reason, and `shadow_only=true`.

Each active generation owns a bounded evidence-role map rather than the full
replay. Available roles are pretrigger context, first detector-confirmed frame,
tracked best, final supported frame, and one bounded alternative. Candidates
contain only portable frame identity/reference, timestamp, dimensions,
normalized subject geometry, provenance, and deterministic subject-area/score
facts. They are temporary shadow evidence and never create `MediaAsset`.
Stage 6 remains responsible for optimal multi-frame evidence scoring.

## Replay, metrics, and execution facts

The Stage 2 CLI accepts:

```sh
python -m mockingbird replay-benchmark \
  --provider frame-driven-onnx-cuda \
  --provider-config data/models/observation-frame-driven/provider-config.json \
  --frames data/replay/frames \
  --manifest data/replay/benchmark.json \
  --output data/replay/output
```

The semantic report includes settings, tracker version/configuration,
detections, track updates, evidence candidates, proposals, matcher output,
pipeline counts, metric states, thresholds, and limitations. Detector latency,
tracker processing time, process/GPU resources, device/runtime facts, absolute
paths, and wall-clock duration remain non-semantic execution facts.

Snapshot-versus-frame-driven comparison reports each side's state/value for
appearance recall, proposal precision, fragmentation, duplicates, incorrect
merges, evidence coverage, and detector frames. Unsupported Snapshot metrics
remain unavailable rather than being treated as zero.

## Authority and current limitations

The provider imports no product repository and cannot create or mutate Event,
Visit, MediaAsset, MotionEvidence, evidence links, primary selections,
ReviewLabel, reviewed Observation, Dashboard/export truth, monitoring policy,
or policy revision. CUDA-only execution remains mandatory; CPU model fallback
is rejected by the Stage 3 detector boundary.

Stage 4 is replay-first continuous analysis. It does not implement live RTSP,
Camera Node analysis streams, rolling encoded buffers, high-resolution evidence
bursts, species interpretation, TensorRT, audio, monitoring workers, or
production proposal authority. Stage 5 adds the provider-neutral Camera Node
analysis-stream and evidence-burst capability boundary.
