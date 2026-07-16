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

No completed phase changes the central truth rule: generated or external output
is evidence; explicit user correction creates reviewed dataset truth.
