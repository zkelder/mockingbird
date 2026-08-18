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

## Clock-drift disposition (v0.1 Release Hardening v1)

Investigated as a release-audit finding: is Node-to-host clock drift
surfaced or acted upon before timestamps participate in persisted Visit/
evidence chronology? Traced precisely, with no code change:

`node_to_host_clock_offset_ms` (`camera_node_live.py`, `_pop_latest`) is
computed once per delivered frame (`host_receive_time - node_capture_time`)
and attached to `FramePacket.timing_facts`, alongside the static
`node_to_host_clock_alignment="uncertain"` fact this document already
describes above. It is not read anywhere else -- not by an API route, a
health check, a log line, or a UI surface. This is a real gap between
"computed" and "surfaced," but it is not a correctness gap: every
consequential ordering/windowing decision already avoids ever comparing a
Node timestamp against a host timestamp, confirmed by tracing each one --

- **Visit/tracklet assembly** sorts and merges exclusively by
  `source_offset_ms` (`VisitEpisodeAssembler`), a Node-session-relative
  offset -- both operands of every comparison are Node-sourced.
- **Cross-reconnect stitching** (`session_timeline.native_reconnect_step`)
  compares two host-side `received_at` reads -- both operands are
  host-sourced. Its own `NATIVE_CLOCK_REGRESSION_UNCERTAINTY_MS` constant
  guards a real *host*-clock regression, a different concern from Node
  drift.
- **Burst latency/alignment** (`request_to_capture_ms`) compares two Node
  timestamps.
- **Coverage/exposure accounting** (`MonitoringExposureIntervalModel`,
  Today Coverage Truth v1) reads only the host's own clock
  (`ObservationEngineSessionManager._clock`) and never a Node timestamp at
  all -- structurally immune, not merely careful.
- **Visit-to-Visit ordering** (every Dashboard/journal/Bird Log query) sorts
  by `EventModel.started_at`, stamped from the host's own `decided_at =
  datetime.now(UTC)` at candidate-creation time -- never a Node timestamp.

This is a deliberate, already-stated design discipline (see "Analysis-to-
host clock alignment is uncertain unless externally synchronized," above),
not an accident this pass discovered. No numeric drift threshold exists
anywhere in the repository, and none is introduced here: inventing one
would not be defensible from evidence, since nothing measured depends on
one. Per this milestone's own instruction ("if current timestamps remain
trustworthy under ordinary drift, document that and do not manufacture a
feature"), no threshold, warning, degraded-health state, or new diagnostic
was added.

**One narrower, disclosed limitation, deliberately left open:** the raw
Node capture timestamp is persisted verbatim onto `MediaAsset.captured_at`
and `VisitEvidenceLink.captured_at` (`ProductRepository.
_create_candidate_visit_locked`) without the "uncertain alignment" caveat
computed two layers upstream. If a Node's own system clock were badly
wrong (for example, no RTC and a lost-power boot to an incorrect time), an
individual evidence image's displayed capture time could read inconsistent
with its own Visit's host-clock-derived window -- a display-trust
annoyance on that one field, not a Visit-ordering, coverage, or evidence-
chronology defect, since (per the tracing above) nothing sorts, merges, or
windows by it. Closing this -- for example, propagating the alignment
caveat as far as the persisted record, or surfacing the already-computed
offset in `ObservationSessionStatusResponse.advanced` for an operator who
suspects a clock problem -- is reasonable future work if a real case is
ever reported, not a v0.1 release blocker.

## Health and limitations

Read-only status starts nothing. It reports source state, received FPS, gaps/drops/coalescing, frame age, current generation, supplied/inferred frames, detector observations and inferred cadence, active tracks, pending inference (bounded at zero or one), burst attempts/success/failure/stale results, median burst latency, and shadow-only authority. CUDA provider health and execution facts remain supplied by the Stage 3 detector adapter.

Limitations: multipart JPEG is bandwidth-heavier than encoded video; the initial Node cadence is 2 FPS; one still is captured per burst; camera-specific concurrent capture behavior is provider-dependent; host and Node clocks are not assumed synchronized; no stable live FPS is claimed until measured; no production handoff exists; and TensorRT, species interpretation, audio, multi-camera orchestration, and rolling encoded buffers are out of scope.
