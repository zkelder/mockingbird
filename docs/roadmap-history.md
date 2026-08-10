# MockingBird Roadmap History

This file is a concise record of completed roadmap work. It is not required
reading for normal implementation tasks. Current priorities and sequencing live
in [roadmap.md](roadmap.md); detailed contracts live in the applicable design
documents.

## Phases 0-6 - product foundation

- Phase 0 established product doctrine, vocabulary, architecture framing, and
  local-first/stream-first boundaries.
- Phase 1 established Sources, Streams, Zones, Events, Visits, Detections,
  ReviewLabels, exports, demo data, and the product API.
- Phase 2 established the stream-first frontend and review/correction surfaces.
- Phase 3 established demo/manual/local media paths underneath the shared
  product model.
- Phase 4 established detections as reviewable evidence.
- Phase 5 established the bird-feeder species review vertical and reviewed
  dataset/export loop.
- Phase 6 extended the vocabulary toward broader yard activity while retaining
  local review truth.

## Phases 7-9 - local intelligence and reviewed datasets

- Phase 7 established optional model-adapter guardrails, MegaDetector decision
  and runtime investigation, and the pivot to lightweight motion triggering.
- Phase 8 established deterministic zone-aware motion, MotionEvidence,
  evidence promotion, frame sampling boundaries, and optional best-frame media
  context.
- Phase 9 established SpeciesSuggestion evidence, explicit correction flow,
  classifier readiness, metadata-only manifests, and external training/export
  boundaries based on reviewed truth.

## Phases 10-14 - Source/provider product contracts

- Phase 10 established Stream playback, Source connection, provider
  configuration, and Source setup review contracts.
- Phase 11 established the external URL still-image boundary: explicit fetch,
  explicit MediaAsset save, explicit pending MotionEvidence handoff, explicit
  promotion, and correction truth.
- Phase 12 established source/stream smoke coverage and saved-preview retention,
  dry-run, and low-risk file-only cleanup boundaries.
- Phase 13 established folder/trail-cam configuration, dry-run preview,
  MediaAsset import, explicit single/batch pending-evidence handoff, and review
  provenance.
- Phase 14 consolidated provider smoke flows and established metadata-only
  generic webhook validation and pending MotionEvidence.

## Phases 15-18 - MVP clarity and review efficiency

- Phase 15 added MVP readiness, the demo script, onboarding/empty states, a
  readiness checklist, and UI-copy reduction.
- Phase 16 designed default-off worker boundaries and added read-only disabled
  worker status/dry-run planning.
- Phase 17 added bulk MotionEvidence/review actions, correction helpers/history,
  and evidence traceability.
- Phase 18 added classifier-readiness example drill-down and Review Queue gap
  actions.

## Phases 19-22 - live camera product loop

- Phase 19 added explicit in-memory monitoring for configured Streams and an
  explicit monitoring-to-review handoff.
- Phase 20 added browser-playable Live view metadata and frontend playback.
- Phase 21 added an optional request-scoped system-FFmpeg RTSP-to-MJPEG bridge.
- Phase 22 added local USB/Windows DirectShow playback, one backend-owned
  in-memory session per Stream, explicit capture, live monitoring, Zone overlay,
  bounded best-frame evidence, review handoff, and optional identification
  assistance. Correction remained truth throughout.

## Phase 23 - field validation

Phase 23 added bounded camera transition diagnostics, camera discovery and
creation, simplified setup, real Windows webcam field checks, live Zone redraw,
motion calibration and image-quality warnings, camera/Zone/sample lifecycle
safety, and an optional local MDv5 proposal verifier. Field findings showed the
need for representative bird-arrival data and repeatable recall/nuisance
measurement rather than one-frame threshold tuning.

## Phase 24A-24D - runtime, recovery, and inert continuity state

- Phase 24A created one same-origin local application runtime with startup
  validation, route recovery, and graceful process-owned camera shutdown.
- Phase 24B added verified database-and-managed-media backup, import, download,
  rollback-safe restore, and pre-restore safety backups.
- Phase 24C designed durable camera/monitor lifecycle with separate desired
  policy, runtime checkpoints, safety holds, and future-audio separation.
- Phase 24D added schema version 2, default-off policy/stopped checkpoints for
  every Stream, read-only lifecycle APIs/status, and side-effect-free polling.

## Phase 24E-24G - durable live continuity and bounded review handoff

- Phase 24E added a bounded `DurableStreamSupervisor` foundation with
  fake-adapter lifecycle, app-instance/checkpoint reconciliation, one-Stream
  leases, deterministic backoff, and stop ordering.
- Phase 24F added explicit Stream-scoped enabling for supported backend-owned
  RTSP/local USB/Windows DirectShow live video, reusing the existing
  camera/session path with bounded recovery.
- Phase 24G allowed explicitly enabled durable monitoring to create or reuse
  at most one needs-review candidate per completed activity session, never
  writing ReviewLabels or Bird Log truth automatically.

## Phase 25 - dependable field loop

Phase 25 hardened restart recovery, bounded storage, retention controls,
camera/source health, and long-run observability, and ran the first
representative field-acceptance campaigns. The first bounded field acceptance
closed as a measured failure at detector-qualified animal Visit admission
precision (10 of 23 reviewed Visits were false positives); a later Admission
Rejection Observability cohort passed admission precision (10/10 promoted
Visits were real birds) while recall remained insufficient. This phase's
goal -- sustained, trustworthy, unattended real-camera operation -- is
carried forward as the Phase 1 (Trustworthy Single-Site Observatory) exit
gate in [roadmap.md](roadmap.md).

## Phase 26A-26B - identification evidence

- Phase 26A added the optional local BioCLIP 2 species-suggestion adapter and
  durable manual-attempt instrumentation (candidate bank, scores,
  provenance); it creates `SpeciesSuggestion` evidence only.
- Phase 26B added a default-off automatic post-activity assist that schedules
  exactly one bounded BioCLIP attempt for each newly completed eligible
  Visit, never retries an existing attempt, and never blocks the monitor on
  model execution.
- Representative species-level correction truth (30-100 examples) sufficient
  to validate BioCLIP's accuracy has not yet been collected; Phase 26C (audio
  evidence) and Phase 26D (multi-signal ranking) remain future work. This gap
  carries forward into Phase 2 (Detection Quality & Model Lifecycle) in
  [roadmap.md](roadmap.md).

## Phase 27A - installable local product v1

Phase 27A delivered first-run detection and a guided setup wizard composing
the existing Add Camera and Observation panel, host-disk storage
writable/low-space status, a consolidated basic product-health view, a
previous-shutdown marker and fixed log location, and a self-contained Windows
"unpack and run" bundle with an embedded Python runtime (no Python/pip/npm
knowledge required to use it). Native Windows CUDA/DLL loading defects
(site-packages path resolution, `AddDllDirectory`/PATH interaction,
`WinError32` masking) and packaged CUDA dependency-closure gaps were found
through real hardware deployment and fixed. See
[local-product-packaging-design.md](local-product-packaging-design.md).
Native Windows hardware acceptance of the produced bundle, accessibility,
update policy, and further dependency-reproducibility/performance work remain
open; see Phase 4 in [roadmap.md](roadmap.md).

## Observation Engine v2 - Stages 1-7, Product Vertical Slice v1, Unified Observation Experience v1

A strangler migration replaced the timer-driven snapshot observer with a
provider-neutral, evidence-only Observation Engine while keeping
`SnapshotObservationProvider` as a compatibility/fallback path. In sequence:
provider-neutral frame/detection/track/evidence/Visit-proposal contracts
(Stage 1); deterministic recorded-media replay benchmarks (Stage 2); an
optional ONNX Runtime CUDA detector provider verified on a local RTX 4060 Ti
with CUDA-only execution (Stage 3); a replay-first frame-driven
detector/tracker shadow pipeline (Stage 4); provider-neutral Camera Node
analysis-stream and evidence-burst capabilities (Stage 5); bounded
multi-frame evidence scoring and old/new shadow comparison (Stage 6).

Stages 6.1-6.19 hardened that shadow pipeline against real Camera Node field
data: an episode-boundary fix separated genuine detector support from
tracker-support so episodes close on positive evidence of discontinuity; a
detector precision/recall calibration benchmark and a shadow-only
candidate-comparison tool were built and used to evaluate a MegaDetector
`spruce` candidate (rejected: worse precision/recall than MDv5 at its
starting threshold, and restricted GPL-3.0 licensing) and a tiling/
adaptive-motion recall strategy (rejected for production: real precision
cost outweighed recovered recall); a reviewed temporal-capture and
active-learning dataset pipeline was built and used across real daylight
Camera Node sessions, which found and fixed three live-transport defects
(per-connection sequence resets, periodic-sampling starvation, marker-
correlation timing); a reconnect-safe session timeline, reconnect-continuity
tracker bridging, and a recurrence-aware burst scheduler were added after
representative shadow-acceptance campaigns found severe tracker fragmentation
(up to 129 track generations for 2-3 real appearances) caused by treating
every benign ~10-second HTTP reconnect as a source reset, plus a
burst-placement/fairness gap that starved late-session appearances of
high-resolution evidence; a burst-storm defect (a recurring static object
reading as "stronger support" on every re-detection) and a sustained-visit
fragmentation defect (natural confidence dips exceeding the tracker's
tolerance during a real multi-minute visit) were found and fixed via a
strong/weak/tracker-only evidence hierarchy; a shadow `VisitEpisodeAssembler`
separated track lifetime from Visit lifetime; and a reviewed-replay lineage
fix let reviewed truth join to replay-produced evidence candidates. Real
Camera Node replays of these fixes together materially reduced tracker
fragmentation and raised measured `appearance_recall` from a
structurally-zero 0.0 (an empty-`ExpectedVisit`-list measurement defect,
itself fixed in Stage 6.17) to a real 0.5-1.0 across sessions.

Stage 7 added one explicit, bounded, default-off `ObservationAuthorityMode`
(`shadow` or `candidate_visit`) that may turn one accepted, assembled Visit
proposal into at most one bounded, needs-review candidate Visit through the
existing `VisitModel`/`EventModel` schema, with a durable activation boundary
and idempotency ledger; it can never write `ReviewLabel`, Bird Log, or export
truth. Product Vertical Slice v1 made this reachable as a Stream-scoped
Start/Stop Observation control with a conservative candidate-quality
admission gate. Unified Observation Experience v1 made that same
Start/Stop/Health control consistent across every supported Stream type
(Camera Node, RTSP/local USB/Windows DirectShow, external-URL snapshot, or an
honest "no runtime" state), replacing the earlier Camera-Node-only panel.

Full per-stage numbers and defect analyses remain in the linked design/
contract documents under `docs/` (routed from
[architecture.md](architecture.md)) and in the dated reports under
`data/field-acceptance/`.

## Camera Node pairing repair and Observation capture-ownership fixes (August 2026)

Real-hardware use after the above milestones surfaced and fixed two defects:
repairing an existing Camera Node's pairing could be told a valid, unconsumed
one-time code was "rejected" because the client conflated "code does not
match" (HTTP 401) with "code already consumed by an earlier successful
attempt" (HTTP 409); and starting Observation for a paired Camera Node Stream
could collide with an already-running legacy live-view/monitoring session for
the same physical camera, since both independently polled the Node's single
per-camera capture lock. Both are fixed: repair now distinguishes the two
rejection reasons and can resume an already-succeeded-but-unsaved pairing,
and an explicit, revocable capture-ownership hand-off
(`LiveCameraSessionManager.pause_for_observation`/`resume_after_observation`)
lets Observation and legacy live view share one camera without contention.
See "Camera ownership vs. the legacy live-view/monitoring session" in
[observation-engine-product-control-contract.md](observation-engine-product-control-contract.md)
and "Live camera ownership" in [architecture.md](architecture.md).

No completed phase changes the central truth rule: generated or external output
is evidence; explicit user correction creates reviewed dataset truth. Unknown
and abstained outcomes remain valid, never a defect to eliminate.
