# Camera Node live-shadow contract

Status: Observation Engine v2 Stage 5 provider contract.

## Boundary

A paired Camera Node owns camera hardware, capture timestamps, sequence numbers, provider generations, and bounded evidence capture. The PC owns Privacy/Ignore masking, ONNX CUDA inference, tracking, temporary evidence ranking, and shadow-only Visit proposals. Neither side in this path writes product records or reviewed truth.

The provider-neutral media objects are `AnalysisStreamCapability`, `AnalysisFrameEnvelope`, `EvidenceBurstCapability`, `EvidenceBurstRequest`, and `EvidenceBurstResult`. Camera-library and accelerator objects cannot cross those contracts. `SnapshotObservationProvider` remains unchanged and continues to be the compatibility production observer.

## First transport implementation

Stage 5 implements one transport: authenticated bounded multipart JPEG over the existing paired Camera Node API. `/node/v1/cameras/{camera_id}/analysis-stream` requires the existing Bearer pairing credential and emits a fixed boundary with content length, source sequence, stable frame identity, UTC capture time, source monotonic time, dimensions, Node session, provider generation, and SHA-256. Anonymous access is rejected, redirects are rejected, at most two streams may be active, each request is frame-bounded, and disconnect releases capacity. There is no synthetic fallback and streaming alone persists nothing.

The paired `/evidence-burst` endpoint accepts one profile-bound, shadow-only JPEG request. The result preserves request identity, provider generation, parent trigger frame, source capture time, dimensions, content hash, and request-to-capture timing. A result with stale generation or lineage is discarded. This first implementation supports one frame per burst; exposure, focus, and whether analysis continues remain provider-dependent.

## Host behavior and bounds

`CameraNodeAnalysisSource` validates content, dimensions, hashes, sequence order, capture times, and generation. It converts only accepted input to byte-backed `FramePacket` values. Its queue is capped at four frames by default, keeps the newest work, drops stale work, and reports gaps, drops, coalescing, frame age, received FPS, and generation resets. Node-to-host clock offset is recorded as an estimate with explicitly uncertain alignment.

`LiveCameraNodeShadowSession` feeds those packets through the Stage 4 frame-driven provider. The detector has one pending inference, the tracker consumes supplied frames at source cadence, and detector cadence rises while tracks are active. A strong or confirmed animal track requests at most one burst per track generation with a configurable global cooldown and no retry. Burst failure does not stop analysis. Temporary burst bytes are limited to eight items, request history to 256 generations, latency history to 128 values, active tracks to provider configuration, and results to the caller's explicit stream frame bound. Stop/reset closes the connection and clears queues, tracks, burst state, and temporary bytes.

## Authority and timing

All outputs are `DetectionObservation`, `TrackUpdate`, `EvidenceCandidate`, or `VisitProposal` with `creates_truth=false`, `shadow_only=true`, and production proposal authority disabled. There is no import path to product repositories. No Event, Visit, MediaAsset, MotionEvidence, evidence link, primary selection, ReviewLabel, reviewed Observation, Dashboard history, or monitoring-policy row is reachable.

Track decisions use source capture time and source-relative offsets. Analysis capture, PC receipt, detector/tracker support, burst request, and burst capture remain distinct facts. Analysis-to-host clock alignment is uncertain unless externally synchronized; source-relative analysis/burst ordering may be supported when both timestamps originate from the same Node generation. Coordinate correspondence alone never proves temporal alignment.

## Health and limitations

Read-only status starts nothing. It reports source state, received FPS, gaps/drops/coalescing, frame age, current generation, supplied/inferred frames, detector observations and inferred cadence, active tracks, pending inference (bounded at zero or one), burst attempts/success/failure/stale results, median burst latency, and shadow-only authority. CUDA provider health and execution facts remain supplied by the Stage 3 detector adapter.

Limitations: multipart JPEG is bandwidth-heavier than encoded video; the initial Node cadence is 2 FPS; one still is captured per burst; camera-specific concurrent capture behavior is provider-dependent; host and Node clocks are not assumed synchronized; no stable live FPS is claimed until measured; no production handoff exists; and TensorRT, species interpretation, audio, multi-camera orchestration, and rolling encoded buffers are out of scope.
