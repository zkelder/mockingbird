# Independent biological-encounter denominator design

Status: Visit Authority Budget + Ambiguous-Boundary Recall Closure v1
(2026-08-19), diagnostic/field-validation tooling. Not a Stage number, not
a new Observation Engine v2 pipeline stage, and not a normal product
capability -- see [candidate-visit-authority-contract.md](candidate-visit-authority-contract.md)
for the fresh-session/budget-scoping and evidence-cache-capacity fixes this
milestone also made, and [scene-confusor-suppression-v1-report.md](scene-confusor-suppression-v1-report.md)
for the field session that first surfaced this gap.

## Problem

Every prior field-acceptance session measured recall against a denominator
that was itself downstream of the pipeline being evaluated: created Visits,
detector tracks, assembled proposals, or (even the more careful
counterfactual-ledger reconstruction) raw detections -- all of them only
exist because the detector/tracker already looked at the scene. None of
them can prove the pipeline's *recall* against reality, only its own
internal consistency. The immediately preceding field session tried to
compare admitted Visits against continuous independent human observation of
the same live scene and found it structurally impossible: the Observation
Engine holds exclusive capture ownership of a paired Camera Node stream
while running (the legacy live-view "current frame" endpoint returns 409
during an active session), so there was no way to look at the same moment
through a second, independent channel without either competing for the
physical camera or trusting the very pipeline under test.

## Chosen approach: option A, a capability-safe tee

Of the milestone's own preferred options (A: capability-safe tee from the
same source; B: a bounded pre-admission recording path; C: another passive
capture path; D: a second camera or human log), this implementation is A: a
tee of the exact bytes the Observation Engine already decodes for
inference, not a second capture connection. `_EngineSession._run_async`
(`engine_runtime.py`) already holds a real, already-decoded `FramePacket`
(including its raw JPEG `payload`) for every analysis frame it processes,
in its own existing per-batch loop (`for result in results: ... for packet
in result.frame_packets: ...`). `mockingbird.observation.acceptance_
recorder.BoundedFrameSampleRecorder.maybe_record(packet)` is called there,
directly -- no new Camera Node connection, no new capture lock, no risk of
contending with the Node's own single-consumer analysis-stream endpoint,
and structurally no way to influence detection, tracking, evidence scoring,
or admission (the recorder module imports nothing from `candidate_visit_
authority`/`candidate_quality_gate`/`visit_episode_assembler`/
`mockingbird.repository` -- enforced directly by
`test_module_has_no_product_repository_or_admission_pipeline_import` in
`tests/test_acceptance_recorder.py`).

## Bounded, not a recording subsystem

`AcceptanceRecorderConfig` is explicit and bounded on three axes:
`sample_interval_ms` (default 3000ms -- dense enough to catch a multi-
minute encounter's own start/end, sparse enough to stay a genuinely bounded
diagnostic artifact, not a re-implementation of continuous recording),
`max_frames` (default 2400, i.e. a full 120-minute session at the default
interval), and `max_total_bytes` (default 2.5GB). Every bound is enforced
directly (`BoundedFrameSampleRecorder.maybe_record` returns `False` and
records a `stopped_reason` once a cap is reached, verified directly by
`test_stops_accepting_once_max_frames_reached`/
`test_stops_accepting_once_max_total_bytes_reached`) -- never a silent
truncation. Each saved frame is written as a plain JPEG file plus one JSONL
manifest line (sequence index, source-relative offset, wall-clock capture
time, filename, sha256 content hash, byte count) -- enough identity for a
human reviewer to independently mark encounter start/end and species/taxon
against real timestamps, without needing anything else from the product.

`max_total_bytes`'s default was revised from an initial 750MB after the
first real field use of this recorder (2026-08-19): analysis-resolution
JPEGs measured ~801KB on average (max ~841KB), not the "well under 200KB"
originally assumed, so the byte bound silently bound first -- at 936 of an
intended ~2400 frames -- ending recording ~30 minutes before the session's
actual Stop and losing independent coverage of that session's last three
admitted Visits. 2.5GB gives `max_frames`'s own default real headroom over
the worst frame size actually observed
(`test_default_byte_bound_has_real_headroom_over_the_old_undersized_default`),
so the frame-count/duration bound is the one that binds in ordinary
operation.

## Off by default; explicit opt-in only

`ObservationEngineSessionManager` accepts an optional `acceptance_recording_
root: Path | None = None` (default `None` -- every existing test and every
ordinary product process is completely unaffected, verified directly by
`test_acceptance_recording_is_off_by_default_and_never_touches_admission`).
The one process-level wiring point,
`main.get_observation_engine_session_manager()`, reads it from
`MOCKINGBIRD_ACCEPTANCE_RECORDING_DIR` -- an environment variable, not a
product setting, UI control, or API route, matching "do not create a large
recording subsystem" and "keep it clearly diagnostic/evaluation-only." When
set, every real "Start observing" for every Stream writes to its own fresh,
stream- and start-time-scoped subdirectory
(`{root}/{stream_id}/{YYYYMMDDTHHMMSSZ}/`), so repeated or concurrent
sessions never collide.

## Never evidence, never truth

Recorded frames are never referenced by any `MediaAsset`, `Visit`, `Event`,
`DetectionProposal`, or `ReviewLabel` -- there is no code path from this
module into the product repository at all. They exist solely so a human can
build an independently-adjudicated encounter log (start/end, species/taxon,
subject size/scene region) *after* a field session, which the field
session's own report then compares against the pipeline's own funnel
(noticed -> localized -> viable episode -> viable proposal -> Visit) -- the
comparison is the deliverable; the recording itself is disclosed,
diagnostic-only local storage under a gitignored path, never redistributed
or treated as a product capability. Broadening this into a supported
recording feature (continuous, product-configurable, or UI-surfaced) is
explicitly out of this milestone's scope and would require its own product
doctrine decision -- see "Do not center the product on... snapshot loops"
and the NVR/continuous-recording deprioritization in
[roadmap.md](roadmap.md).
