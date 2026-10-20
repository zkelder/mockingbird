# Offline / Recorded Observation Ingest v1

## Purpose

Before this milestone, recorded video could be imported as a MediaAsset
(with EXIF/`creation_time`/content-hash/duration provenance -- see "v0.1
Acquisition/Ingest Interoperability Closure v1" in
[roadmap.md](roadmap.md)), but it never flowed through the wildlife-
observation pipeline: no frame decode, no detection, no tracking, no Visit
assembly, no evidence, no review. This milestone closes that gap. A user can
now give MockingBird a recorded wildlife video (or a folder-imported
camera-trap clip) and have it processed by the **same** subject-level
wildlife Observation pipeline a live Camera Node uses -- producing ordinary
needs-review candidate Visits, Events, and Evidence, never a second,
parallel pipeline.

Desired path:

```
recorded media -> import (existing folder-import path, unchanged)
               -> explicit "Analyze imported media" action
               -> bounded decode into source frames
               -> the ordinary Observation Engine seam
               -> Event / subject Visits (multi-subject correct)
               -> persisted Evidence (source-resolution)
               -> provisional species assistance (unchanged, still provisional)
               -> review (unchanged)
               -> durable Observation / Bird Log / export (unchanged)
```

This must never pretend recorded media was live continuous monitoring.

## Common seam: reuse, never a second pipeline

The single most important architectural fact this milestone rests on:
**`FrameDrivenObservationProvider.replay_frames(frames: tuple[FramePacket,
...]) -> tuple[ObservationResult, ...]` is already a peer, already-tested,
already-production entry point** for feeding an arbitrary ordered frame
sequence through the real detector/tracker -- the exact same method the
existing Perception Replay Regression Harness (`replay.ReplayRunner`,
`perception_regression.run_perception_regression`) already drives for
offline frame sources. `mockingbird.observation.offline_ingest` supplies a
**new frame source** (`recorded_video_source`, decoding one recorded video
into that same `FramePacket` shape) into that **existing** seam -- it adds
no new detector, tracker, assembler, evidence scorer, admission gate, or
multi-subject mechanism of any kind.

```
recorded video file
    -> recorded_video_source.sample_recorded_video_frames  (NEW: bounded ffmpeg decode)
    -> recorded_video_source.frame_packets_from_recorded_video  (NEW: FramePacket projection)
    -> FrameDrivenObservationProvider.replay_frames  (EXISTING, unmodified, one call per video)
    -> visit_episode_assembler.build_tracklets / assemble_visit_episodes  (EXISTING, unmodified)
    -> candidate_visit_authority.resolve_ambiguous_boundary_arbitration  (EXISTING, unmodified)
    -> candidate_visit_adapter.CandidateVisitAuthorityAdapter.attempt_candidate  (EXISTING, unmodified)
    -> ProductRepository.create_candidate_visit_from_proposal  (EXISTING, unmodified)
```

The only genuinely new *engine-adjacent* code is `recorded_video_source.py`
(decode) and `offline_ingest.py` (orchestration: resolve the MediaAsset/
Stream, activate/revert authority, harvest evidence bytes, run the admission
loop, record progress). Every admission check a live Camera Node candidate
gets -- authority mode/activation boundary, lineage validity, ambiguity/
continuation-pending policy, session/hourly rate budgets, Privacy/Ignore
Zone exclusion, evidence-quality admission, scene-confusor suspicion,
concurrent-sibling Event reuse -- applies identically and unmodified,
because it is the same code, not a re-implementation.

`FrameDrivenObservationProvider.replay_frames` resets tracker state and
finalizes (drains every still-open track generation) on **every call** --
confirmed directly from its own implementation (`self.reset()` at entry,
`self.finalize_replay()`/`drain_final_results()` at exit). This is why one
recorded video is always decoded into one complete, ordered `FramePacket`
tuple and fed through **exactly one** `replay_frames` call: splitting one
recording across multiple calls would treat each artificial chunk boundary
as "the recording ended here," fragmenting one continuous encounter purely
because of how this module happened to batch its own frames. Bounded memory
is achieved at the *decode* layer instead (see "Frame sampling policy"),
never by chunking the engine call itself.

## Acquisition-session semantics

Offline analysis of one recorded video is its own bounded acquisition
session, explicitly distinct from live monitoring:

- Authority (`ObservationAuthorityMode`) is activated `candidate_visit` for
  the MediaAsset's own Stream with `fresh_session=True` -- mirroring exactly
  what a real "Start observing" action does for a live Stream (see
  [candidate-visit-authority-contract.md](candidate-visit-authority-contract.md)
  "Fresh-session activation") -- for the duration of one bounded call, and
  reverted to `shadow` unconditionally afterward (success, failure, or
  exception), matching the same kill-switch discipline
  `engine_runtime._EngineSession.stop` already uses. It is never left
  standing active; a Stream that was never live-observing is never made to
  look live-observing.
- `provider_key="recorded-media-offline-ingest-v1"` (a durable, diagnostic-
  only fact on `ObservationCandidateVisitModel`, never product-facing truth)
  distinguishes an offline-ingest-produced candidate from a live session's
  `"frame-driven-onnx-cuda"` or the perception-replay harness's
  `"perception-replay-regression-v1"` -- the same established convention,
  not a new one. `detector_provenance`/`tracker_provenance` stay the real
  underlying engine identity (`detector.provider_id`/`provider.provider_id`)
  -- honest about which detector/tracker actually ran, exactly like the
  live construction site in `engine_runtime.py`.
- The Stream itself is never claimed to be "currently live": a
  `folder_import_future`-provider Stream already reports
  `supports_live_playback=false`/`is_live=False` (see
  [folder-trailcam-provider-boundary-design.md](folder-trailcam-provider-boundary-design.md)),
  unaffected by this milestone. Nothing about offline ingest changes that
  honesty; a Visit produced this way lives under a Stream that never implied
  live connectivity in the first place.

## Frame sampling policy

Default: **2.0 fps** (one sampled frame every 500ms), fixed via ffmpeg's own
deterministic `fps` video filter -- never frame-by-frame Python throttling,
so re-decoding the same file at the same `sample_fps` always yields the same
frame count at the same offsets (required for `FrameDrivenObservationProvider`'s
own `deterministic_replay` capability to hold for this frame source too).

Justification, not "1fps because it's simple":

- This product's own empirically-observed live analysis cadence is
  materially *sparser* -- roughly 0.85fps / ~1.17s per analyzed frame,
  measured directly in the 2026-08-19 End-to-End Bird Encounter Recall
  Closure v1 field campaign -- and that cadence is already the accepted
  production baseline. Recorded media has no live bandwidth/hardware
  constraint forcing a slower rate, so sampling *denser* than the
  already-accepted live cadence is cheap for a bounded clip and can only
  reduce (never increase) the risk of missing a brief encounter.
- 500ms gaps between consecutive sampled frames sit comfortably below every
  temporal tolerance the shared tracker/assembler already use to decide
  "same encounter": `maximum_unsupported_detector_ms` (~5000ms,
  `frame_tracker.TrackerConfiguration`) and `merge_gap_ms` (15000ms,
  `visit_episode_assembler.VisitAssemblyConfiguration`). Uniform, fixed-
  interval sampling therefore cannot itself manufacture an artificial gap
  large enough to fragment or falsely separate one continuous encounter --
  see "Visit/event temporal boundaries" below.

Bounded by `max_frames` (default 3600, i.e. 30 minutes of sampled coverage
at the default rate) -- comfortably beyond "a normal short trail-camera
clip" while keeping the worst-case memory footprint (every sampled frame is
a real, source-resolution JPEG that might later be selected as evidence and
is held in memory for the one `replay_frames` call -- see "Bounded memory,
not bounded duration" below) from growing unbounded for an unusually long
recording. Truncation is always disclosed (`RecordedFrameSamplingResult.
truncated`/`OfflineIngestResult.truncated`), never silent. Both `sample_fps`
and `max_frames` are explicit, caller-overridable parameters (API request
body, CLI flags).

### Bounded memory, not bounded duration

`recorded_video_source.sample_recorded_video_frames` never buffers the
source file or the raw decoded stream: ffmpeg's own stdout pipe is read
incrementally, one JPEG frame at a time, reusing
`mockingbird.playback.rtsp_bridge.iter_multipart_mjpeg` -- the exact same
bounded buffer-scan the live RTSP bridge already uses, supplied with a new
local-file ffmpeg command instead of an RTSP one. Only the bounded,
already-downsampled, JPEG-compressed *output* frames (capped at
`max_frames`) are ever accumulated as a Python sequence at once -- never the
source video's own raw/native-rate frame sequence.

## Frame-time semantics

For a frame decoded at source offset `T`:

- `source_offset_ms = round(index * 1000 / sample_fps)` -- deterministic by
  construction of the `fps` filter, never approximated or read back from
  ffmpeg's own re-encoded output timestamps (not reliably recoverable once
  frames are piped as a bare MJPEG byte stream).
- `frame_observed_at = capture_start + T` **only** when `capture_start` is a
  trustworthy fact already recorded on the MediaAsset (`MediaAssetModel.
  captured_at`, populated at import time from EXIF `DateTimeOriginal` for an
  image or the container's own `creation_time` tag for a video -- see
  "Video `creation_time` extraction" below). This governs two independent
  places:
  - `FramePacket.captured_at`, per sampled frame (fed into the detector/
    tracker, and onward into persisted evidence `MediaAssetModel.
    captured_at`).
  - `observed_at` passed to `CandidateVisitAuthorityAdapter.attempt_candidate`
    per assembled proposal (`capture_start + proposal.start_offset_ms`),
    which becomes `EventModel.started_at`/`ended_at` and the persisted
    candidate evidence's own `created_at` -- see "Today/history timestamp
    behavior" below for why this matters.
- When `capture_start` is unknown, `FramePacket.captured_at` is left `None`
  and the existing, already-reviewed `frame_driven_provider._with_fallback_
  captured_at` convention applies unmodified: `datetime(1970, 1, 1, tzinfo=
  UTC) + offset` -- deliberately an obviously-not-real date, never a
  recomputed "now". `offline_ingest.EPOCH_ANCHOR` reuses the identical
  anchor for the `observed_at` value the orchestrator itself must supply
  (a mandatory keyword argument with no default), so an Event/Visit from a
  timestamp-unknown recording reads as honestly pre-1970, never as "today."
  **Never a fabricated absolute UTC timestamp either way.**

This is a real, deliberate design fork from the live path, where
`observed_at` (real processing wall-clock "now") and the frame's own actual
capture moment are always approximately equal (off by seconds of processing
latency) -- for a historical recorded video they can differ by years, so
this milestone cannot reuse live's implicit "processing time ≈ capture time"
assumption; it must derive `observed_at` from the video's own timeline
instead. See `run_offline_video_ingest`'s own docstring for the exact
mechanism, and "Today/history timestamp behavior" below for the regression
this protects.

### Video `creation_time` extraction

`media_provenance.VideoProbeResult` gained a `captured_at: datetime | None`
field, parsed from ffprobe's own `format.tags.creation_time` (a `Z`-suffixed
ISO-8601 UTC instant on every container this module has observed emit one --
verified directly against a real ffmpeg-generated clip, not assumed). `None`
-- never a fabricated fallback to filesystem mtime or import time -- when
the tag is absent, malformed, or lacks a timezone offset entirely (a naive
`creation_time` is honestly discarded, mirroring `extract_image_captured_at`'s
identical EXIF discipline). The existing folder-import creation path
(`ProductRepository.import_source_folder_media_assets`) now populates
`MediaAssetModel.captured_at` for a video exactly as it already did for an
image -- a small, additive, backward-compatible extension of an existing,
already-tested function; no schema change (the `captured_at` column already
existed, simply unpopulated for video until now).

### Capture-time presentation (Owner-Only Release Polish & Acceptance v1)

The epoch anchor above is a storage and ordering convention, never a date
to show. Two facts matter here:

- **Persisted evidence carries the anchor, not `None`.** The frame-driven
  provider's `_with_fallback_captured_at` replaces a `None`
  `FramePacket.captured_at` with `1970-01-01 + offset` *before* evidence is
  built, so an offline Visit's persisted evidence `MediaAssetModel.
  captured_at` is `1970 + offset`. "Evidence `captured_at` is present" does
  not, on its own, mean a real capture time is known.
- **The placeholder is identified by provenance, never by age.**
  `ProductRepository._visit_capture_time_known` reports `False` only when
  the candidate ledger's `provider_key` maps to `recorded_video` and the
  source recording's own `MediaAssetModel.captured_at` is `None` (the
  source id comes from the ledger's frame lineage, `"<source
  media_asset_id>:<index>"`). An acoustic candidate uses its source audio
  asset the same way. A recording that genuinely states a 1970 capture
  time stays known. An Event starting on or after 1971-01-01 skips the
  check, which only avoids queries for ordinary Visits.

The resulting `capture_time_known` flag is exposed on `StreamVisitSummary`
(and so Today/Dashboard, Activity Library and Bird Log rows), Bird Log
label summaries and representatives, `ReviewQueueItem`, `VisitDetail`
(with `acquisition_type`) and `EventDetail`. The frontend's
`formatCaptureDateTime` shows "Capture time unknown" when it is `false`.
Research export requires the same fact before calling a capture time
`recorded`. Raw timestamps, ordering, evidence and reviewed truth are
unchanged.

## Source-resolution evidence

The decoded sampled frame **is** the source frame -- there is no separate
"low-resolution live analysis stream plus on-demand high-resolution burst"
split for offline video (a live Camera Node's own architecture, driven by
network/hardware constraints that do not apply to a file already on disk).
The same bytes handed to the detector are the same bytes available as
persisted evidence, so `same_frame=True`/`resolution_provenance=
"exact_same_frame"` holds by construction for every offline-ingest
identification/context candidate -- reusing the exact, unmodified
`localization_attribution.geometry_attribution_for_update` call site
`FrameDrivenProvider._candidate` already makes for a live "same analysis
frame" evidence candidate. No new alignment/crop mechanism was added or is
needed; `mockingbird.motion.high_resolution_evidence.resolve_alignment`/
`NormalizedGeometryTransform`/`crop_jpeg` remain entirely unused by this
path because there is no cross-resolution transform to prove here.

## Multi-subject correctness

Mandatory, and satisfied for free by reusing the existing seam unmodified.
`visit_episode_assembler.classify_boundary` already buckets tracklets by
`(stream_id, broad_class)` and marks two temporally-overlapping tracklets
`incompatible`/`temporal_overlap`, recording each in the other's
`concurrent_sibling_proposal_ids` (Multi-Subject Visit Assembly & Review v1,
Phase 1); `ProductRepository._create_candidate_visit_locked`'s existing
`_event_id_for_concurrent_siblings` helper (Phase 2) then reuses a sibling's
already-persisted `event_id` instead of minting a new one. A recorded clip
containing two simultaneous, distinct subjects therefore already produces
one shared Event with two independent sibling Visits, each admitted through
its own full, independent admission pass (one sibling's rejection never
blocks or degrades the other's), with zero new code for this milestone to
add -- proven directly by
`test_offline_ingest.py::test_offline_ingest_produces_sibling_visits_for_two_simultaneous_subjects`
(a real ffmpeg-decoded clip, two simultaneous fake-detector subjects, one
Event, two Visits, no shared/borrowed evidence).

## Visit/event temporal boundaries

`assemble_visit_episodes` is called **without** `known_horizon_ms`. Per its
own "Episode finality" contract (see
[tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md)),
omitting this parameter means every resulting proposal reports
`continuation_pending=False` -- "preserving the exact prior behavior for
every existing caller (`replay.py`, every offline/already-complete
recording...)". A recorded video is, by construction, already wholly
observed the moment the whole file has been decoded (there is no "more of
the stream might still arrive" concern a live/still-running session has),
so this is the *correct* default, not a workaround -- it also means the
offline admission loop needs no retry/timer mechanism at all: every
proposal is attempted exactly once, in one deterministic pass, immediately
after `resolve_ambiguous_boundary_arbitration` runs once over the complete
proposal set (mirroring `admission_replay.evaluate_shadow_admission`'s
identical "arbitrate once over everything, then attempt every proposal in
order" discipline -- without adopting that module's isolated-repository-only
scope, which is deliberately test/regression-only; see [Idempotency and
concurrency](#idempotency-and-concurrency) below for why this milestone
could not simply import that module).

Genuine same-encounter ambiguity that survives full information (two
fragments whose gap is neither clearly "merge" nor clearly "separate" even
with the whole recording available) is still handled by the existing,
unmodified ambiguous-boundary arbitration mechanism -- conservatively
blocked unless arbitration names a single resolved winner, exactly as a live
session would.

## Evidence persistence

Unmodified. `CandidateVisitAuthorityAdapter.attempt_candidate` scores
already-retained evidence via the existing, unmodified `evidence_scoring.
score_proposal_evidence`, and `ProductRepository._create_candidate_visit_
locked` persists only the bounded, already-selected identification/context/
alternate picks (`max_evidence_items_per_candidate`, default 4;
`max_evidence_bytes_per_candidate`, default 8MB) -- never every sampled
frame. Because `offline_ingest.py` decodes one bounded, complete frame
sequence before calling `replay_frames` once, it already holds every
sampled frame's own JPEG bytes in memory for the whole call; evidence
lookup is therefore a direct dict lookup by `EvidenceCandidate.
media_asset_id` rather than the live path's bounded eviction-based harvest
cache (`_MAX_CACHED_BURST_BYTES`) -- a live session needs that cache because
its own frame history is unbounded/indefinite, which a single bounded
recorded video is not.

Every persisted evidence `MediaAssetModel` row carries the same lineage a
live candidate's does: `trigger_id` (= `proposal_id`), `derivation_source=
"observation_engine_candidate"`, `normalized_track_box_json` (raw subject
geometry), `geometry_attribution_json` (`resolution_provenance=
"exact_same_frame"` -- see above), `evidence_role`
(`identification`/`context`/`alternate`). Which imported file/decoded frame
offset produced it is answerable via the `ObservationCandidateVisitModel`
ledger row (`source_capture_frame_ids`/`supporting_frame_ids`, both derived
from this module's own deterministic `frame_id = "{media_asset_id}:
{index:08d}"` scheme) plus the originating `RecordedMediaAnalysisRunModel`
row (`media_asset_id`, `sample_fps`, `pipeline_version`).

## Species assistance

Untouched. Offline-ingest Visits are ordinary `needs_review` Visits with
`species_guess=None`/`reviewed_label=None` on creation, reaching the exact
same production species-suggestion path (BioCLIP adapter, abstention
policy, `classifier_same_frame` evidence handling) any other Visit does --
no separate "offline classifier" was added, and none is needed. Reviewed
truth remains exclusively the existing, unmodified `create_review_label`
path.

## Multi-frame species opportunity

Offline video naturally produces more than one retained evidence candidate
per Visit when the scorer selects an alternate alongside identification/
context -- `species_multi_frame_candidate_plans` (the existing, tested-but-
not-production-wired multi-frame consensus infrastructure) already reads
whatever evidence a Visit happens to have, so an offline-ingest Visit with
multiple retained frames is automatically visible to it with zero new
plumbing. This milestone does **not** wire `evaluate_multi_frame_consensus`
into the live identification path, does not add a policy-promotion
decision, and does not treat this as evidence toward that separate,
explicitly-deferred milestone (see [source-resolution-multi-frame-species-evidence-contract.md](source-resolution-multi-frame-species-evidence-contract.md)) --
only that the same legitimate candidate structure is populated, unchanged.

## Still-image and camera-trap batch behavior

Deliberately unimplemented by this milestone, and correctly so: the
existing folder-import path already turns a still image into one MediaAsset
with real EXIF `captured_at`, and the existing single/batch MotionEvidence
handoff (Phase 13G/13I) already lets an operator explicitly promote it to
one bounded evidence-review opportunity -- a still image has exactly one
frame, so there is no "decode more frames" gap to close for it. Camera-trap
batch ordering/timestamp-honesty/duplicate-detection are likewise already
handled by the existing folder-import provenance work (content-hash
duplicate detection, per-file `captured_at`, no continuous-monitoring
implication). This milestone's scope is specifically the recorded-*video*
decode gap the previous milestone's own report named as the sole remaining
defect; it does not reopen or re-validate the already-accepted image/batch
path.

## Coverage / effort

Critical invariant, verified directly (not merely asserted): offline ingest
creates **zero** `MonitoringExposureIntervalModel` rows. That table has
exactly one constructor call site in the entire codebase
(`ProductRepository._checkpoint_monitoring_exposure_interval`), reached only
through two call paths -- the legacy durable-monitoring-supervisor's
`mark_monitoring_running` and the live Observation Engine's
`record_observation_exposure_frame` (called once per live-session healthy-
frame batch from `engine_runtime._EngineSession`). `offline_ingest.py` calls
neither. `test_offline_ingest_creates_no_monitoring_exposure_intervals`
locks this in directly against the real table. A 4-second (or 40-minute)
recorded clip therefore never implies a live continuous-monitoring window
of any duration, matching `MediaAssetModel.duration_seconds`'s own existing,
pre-this-milestone honesty guarantee ("never wired into
`MonitoringExposureIntervalModel`/coverage math").

## Today/history timestamp behavior

Import time is never observation time. A historical camera-trap video
imported (and analyzed) today displays under its own real historical
capture date -- derived from `capture_start + proposal.start_offset_ms`, see
"Frame-time semantics" above -- never under today's date merely because
analysis happened today. `test_offline_ingest_historical_capture_imported_
today_is_not_reported_as_today` proves this directly against
`dashboard_summary`'s own "today" computation using a real 2020-dated
synthetic clip. See also "Known Core failure cleanup" below: a related,
pre-existing test-fixture bug in this same "today" computation's own test
coverage was found and fixed as part of this milestone.

## Privacy

Unmodified, and inherited automatically. `ProductRepository.
stream_privacy_ignore_regions(stream_id)` (side-effect-free, keyed only by
`stream_id` + `ZoneModel.zone_type`/`is_active`/`polygon_json` -- no live-
only assumption anywhere in it) is called once per offline-ingest run and
threaded into every constructed `FramePacket.analysis_excluded_regions`,
giving the same three enforcement layers a live Stream gets: pixel-level
masking before detector inference (`onnx_provider._preprocess`), detection-
level filtering before a track can form (`frame_driven_provider._excluded`),
and the persistence-level defense-in-depth check
(`_create_candidate_visit_locked`'s `blocked_privacy_zone`). Source-
resolution recorded evidence therefore cannot bypass a restricted Zone any
more than a live candidate can -- proven directly by
`test_offline_ingest_respects_privacy_zone`.

## Source association

An imported video MediaAsset's own already-recorded `stream_id` (set by the
existing, unmodified folder-import path at import time, where an operator
already explicitly selected a Stream) is the *only* Stream an offline-
ingest run ever attaches candidates to -- `run_offline_video_ingest` never
accepts a caller-supplied Stream override and never defaults to "the active
backyard camera." This is "explicit operator-selected association," reusing
the existing import-time Stream choice rather than adding a second
selection step; no new UI/API concept was needed. A MediaAsset with no
Stream (structurally impossible today -- `MediaAssetModel.stream_id` is
non-nullable) or whose Stream row has been deleted since import fails
closed (`missing_stream`).

## Idempotency and concurrency

Two independent layers, deliberately not one:

1. **Content-addressed, always-on.** `AssembledVisitProposal.proposal_id` is
   already a deterministic sha256 of the assembler version plus sorted
   constituent generation ids (unchanged from the live path).
   `FrameDrivenObservationProvider`'s own `deterministic_replay` capability
   plus this module's own deterministic `frame_id`/`source_offset_ms`
   construction mean re-decoding the *same* file at the *same* `sample_fps`
   reproduces the identical tracker generation ids and therefore the
   identical `proposal_id` -- so `ObservationCandidateVisitModel`'s existing
   primary-key idempotency check (`"idempotent_repeat"` outcome) already
   prevents a duplicate Visit for genuinely identical decoded content,
   *regardless* of what `pipeline_version` label a caller used. This is
   depended on, not merely tolerated -- see
   `test_offline_ingest_reprocessing_identical_content_under_a_new_pipeline_version_stays_idempotent`.
2. **Run-level, orchestration-scoped.** `RecordedMediaAnalysisRunModel`
   (schema 41) records one row per `(media_asset_id, pipeline_version)`
   attempt with a bounded `queued`/`processing`/`completed`/`failed`
   lifecycle. `run_offline_video_ingest` checks for an existing row first:
   a `completed` row short-circuits (`status="already_processed"`, no new
   engine work at all) unless the caller passes `force_reprocess=True`; a
   `queued`/`processing` row refuses a concurrent duplicate attempt
   (`status="in_progress"`, raised as `ValueError("analysis_already_in_
   progress")` from `ProductRepository.create_recorded_media_analysis_run`
   if the race is only caught at insert time, translated back to the same
   honest `"in_progress"` outcome rather than an unhandled 500). This is a
   bounded, single-process-adequate guard -- not a distributed lock -- which
   is proportionate: analysis is synchronous within one bounded call, not a
   background job a queue would otherwise need to de-duplicate.

Explicitly distinguished: *same file, same pipeline* (short-circuited by
layer 2, cheap) versus *explicit reprocessing under a materially different
pipeline* (layer 2 lets the attempt proceed; layer 1 still correctly
refuses to duplicate a Visit if the underlying detection is, despite the
new pipeline label, actually unchanged -- proven by the same test above --
while a genuinely different detection result, e.g. a real upgraded model,
legitimately produces a new, additional Visit, proven by
`test_offline_ingest_reprocessing_with_genuinely_different_detection_creates_a_new_visit`).
Neither layer ever touches or overwrites already-reviewed historical truth
from an earlier run; only the unmodified `create_review_label` path can.

This milestone's admission-loop shape deliberately does **not** reuse
`mockingbird.observation.admission_replay` (the Perception Replay Regression
Harness's own admission bridge) despite the near-identical control flow,
because that module's whole contract is "isolated, disposable database and
`replay:`-namespaced synthetic Stream only" (`require_replay_stream_id`,
`IsolatedAdmissionRepository`) -- reusing it for real product ingest against
the real database and a real Stream would blur a deliberately-drawn
architectural boundary (see
[perception-replay-regression-harness-contract.md](perception-replay-regression-harness-contract.md)).
`offline_ingest.py`'s own admission loop (~20 lines: sort, arbitrate once,
attempt each via the same `CandidateVisitAuthorityAdapter`) is a small,
independently-written mirror of that harness's orchestration shape, not an
import of it -- the actual admission *logic* it calls into remains 100%
shared with zero duplication.

## Failure/resume behavior

Bounded, never a distributed job queue:

- A pre-flight `media_provenance.probe_video_metadata` check (cheap,
  already-existing) classifies an unreadable container as
  `media_file_invalid` and a readable container with no video stream as
  `unsupported_codec` *before* attempting the more expensive full decode.
  A container that probes fine but genuinely fails to decode raises
  `decode_failed`.
- ffmpeg's own hard `-frames:v <max_frames>` cap plus a bounded overall
  decode timeout (`DEFAULT_DECODE_TIMEOUT_SECONDS=900s`) bound worst-case
  wall time; the decode subprocess is always terminated deterministically
  (`rtsp_bridge`'s existing terminate-then-kill discipline, reused via
  `iter_multipart_mjpeg`'s own `finally`) even when a caller stops consuming
  frames early.
- Every genuine failure (decode error, no configured model bundle/CUDA
  runtime, or any other unexpected exception) is caught, recorded on the
  `RecordedMediaAnalysisRunModel` row (`status="failed"`, a stable
  `error_code` plus a sanitized `error_message` -- never a raw filesystem
  path or third-party exception string reaching the API/CLI), and returned
  as an honest `OfflineIngestResult` -- never a partial Visit/Event/
  MediaAsset, because nothing above the repository's own existing
  transactional `create_candidate_visit_from_proposal` writes anything, and
  that method already rolls back completely on any genuine storage failure.
- Rerun is deterministic/idempotent (see above); there is no partial-
  progress checkpoint/resume within one decode pass -- a failed attempt is
  retried from the beginning by calling the route/CLI again (cheap for a
  bounded clip; explicitly out of scope: a distributed job queue or
  frame-level checkpointing).

## Progress and diagnostics

`RecordedMediaAnalysisRunModel` (schema 41) is bounded operational history,
mirroring `MonitoringExposureIntervalModel`'s own "operational history,
never evidence" framing -- it never itself gates or creates a Visit/Event;
it only records that one bounded attempt happened. Exposed read-only via
`GET /api/media/{media_id}/analysis-runs` (and `ProductRepository.
get_recorded_media_analysis_run`/`list_recorded_media_analysis_runs_for_
media_asset`): `status` (`queued`/`processing`/`completed`/`failed`),
`frames_considered`, `frames_analyzed` (frames the detector actually ran
inference on -- `ObservationResult.detector_ran`, an already-existing
field), `events_created`, `visits_created`, `source_duration_seconds`,
`error_code`/`error_message`, `started_at`/`completed_at`. No per-frame log
spam -- diagnostics are one row per attempt, not one row per frame.

## Error taxonomy

Stable, bounded, lowercase-snake-case codes -- matching this codebase's
*actual* established convention (`SavedMediaFrameDecodeError`'s
`"image_decode_failed"`, `OnvifClientError`'s `"onvif_host_invalid"`, etc.),
not a new `SCREAMING_SNAKE_CASE` vocabulary:

- `media_file_invalid` -- unreadable/missing/empty file.
- `unsupported_codec` -- readable container, no usable video stream.
- `decode_failed` -- a container ffmpeg cannot actually decode despite
  probing successfully.
- `ffmpeg_unavailable` -- no ffmpeg/ffprobe binary on this installation.
- `engine_unavailable` -- no configured Observation Engine model bundle/
  CUDA runtime (the exact same condition, and the exact same
  `_engine_failure_message` classifier, the live `/observation/start` route
  already reports honestly).
- `media_asset_not_found` / `media_asset_not_video` / `missing_stream` --
  orchestration-level request validation.
- `analysis_already_in_progress` -- the bounded concurrency guard (see
  above); maps to HTTP 409.
- `processing_failed` -- generic, sanitized catch-all for any other
  unexpected exception.

Never leaked to a normal UI: local filesystem paths never appear in an API
response (`test_analyze_recorded_media_response_never_leaks_a_local_
filesystem_path`); raw ffmpeg stderr is never attached to a persisted
`error_message`.

## API / CLI / UI surface

The smallest practical operator path -- no new job-management UI:

- `POST /api/media/{media_id}/analyze-recorded` (`RecordedMediaAnalysisRequest`
  -> `RecordedMediaAnalysisResponse`): bounded and **synchronous** -- runs
  the full decode/detect/track/assemble/admit pass before responding. This
  is a deliberate, disclosed v0.1 limitation: a real short trail-camera clip
  completes in seconds, so a background job queue was judged disproportionate
  scope (see "Scope exclusions"); a materially longer recording would need a
  future async/background variant, not built here.
- `GET /api/media/{media_id}/analysis-runs` (-> `list[RecordedMediaAnalysisRun]`):
  side-effect-free history/diagnostics read.
- `python -m mockingbird analyze-recorded-media <media_asset_id> [--sample-fps]
  [--max-frames] [--pipeline-version] [--force-reprocess] [--json]`: the
  same orchestrator, for local/scripted use, mirroring the existing
  `__main__.py` lazy-import dispatch convention exactly.
- **Frontend:** one new "Analyze imported media" action on the Streams
  page's existing folder-import results panel (`StreamsPage.tsx`), shown
  only for a video MediaAsset (`content_type.startsWith("video/")`),
  alongside the existing "Create pending evidence" action for stills --
  reusing the exact same per-item loading/error/result state pattern that
  action already established, not a new page or a large job-management
  surface. No camera pairing, no Zone requirement -- consistent with
  "Onboarding relationship" below.

## Onboarding relationship

Recorded media is an alternative acquisition source, not a camera. Analyzing
an imported video never requires Camera Node pairing, and Zones remain
entirely optional (a Zone-less Stream analyzes exactly like a Zone-less live
Stream already does -- `zone_id` stays `None` throughout, proven directly by
`test_offline_ingest_works_with_no_zones_configured`). "Add camera" and
"Import recorded wildlife media" remain the existing, already-distinct UI
entry points (Camera setup vs. Streams-page folder import); this milestone
does not merge or restructure them.

## Schema changes

Schema v40 -> v41, one additive migration
(`_migrate_to_recorded_media_analysis_runs`): a new, empty
`recorded_media_analysis_runs` table (see `RecordedMediaAnalysisRunModel`
above), mirroring `_migrate_to_scene_confusor_regions`'s own "additive
table, no seeded row" pattern exactly. Upgrade-path-tested against a real
rolled-back-to-v40 snapshot database
(`test_schema_40_upgrades_to_current_with_recorded_media_analysis_runs`),
not just fresh-install `create_all`.

## Known Core failure cleanup

The previous milestone's own report named one pre-existing failure,
`test_dashboard_summary_uses_reviewed_truth_and_bounded_safe_visits`,
suspected as a midnight/local-day-boundary sensitivity. Root-caused this
milestone: **not** a production bug in `ProductRepository.dashboard_summary`
(its own UTC-normalization of the local-day boundary via `_as_utc`/
`normalize_utc` is already correct), but a **test-fixture** bug --
`add_dashboard_today_visits` (`tests/test_stream_playback_contract.py`)
persisted a raw local-timezone-aware `datetime.now().astimezone()` value
directly into `DateTime(timezone=True)` columns, while every real
production write path always normalizes to UTC first
(`datetime.now(UTC)`). SQLite's generic `DateTime(timezone=True)` binding
silently discards tzinfo and encodes only the raw wall-clock digit string,
so the fixture's un-normalized local digits only coincidentally compared
correctly against `dashboard_summary`'s own correctly-UTC-normalized day
boundary whenever the real local hour happened to be `>=` the host's UTC
offset magnitude -- and would silently exclude a genuinely-today row
whenever a test happened to run between local midnight and (local midnight
+ |UTC offset|). Confirmed empirically both ways: reproduced the failure by
constructing a row the old (unconverted) way, and confirmed the fix
(`normalize_utc(...)` before every persisted timestamp in that fixture)
resolves it. Fixed at the test-fixture layer (the actually-buggy layer);
added `test_dashboard_midnight_boundary_uses_local_day_not_utc_digits`, a
deterministic, host-timezone-independent regression using a fixed, explicit
UTC-4 offset (never the real system clock/timezone) so it can never depend
on what hour it happens to run or what timezone the host is in.

## Scope exclusions (explicitly not built here)

- Model benchmark/promotion, multi-frame production promotion (see "Multi-
  frame species opportunity" above).
- Camtrap DP export, research collaboration, conservation reporting --
  deferred to the next Research/Conservation/Export milestone.
- Scheduled/background/distributed processing of any kind -- this route is
  synchronous by design (see "API / CLI / UI surface").
- GPU transcoding architecture, video editing, automatic cloud backup.
- A second offline classifier (species assistance is entirely unmodified).
- RTSPS workaround, ONVIF/RTSP/Camera Node changes of any kind -- untouched.
- A distinct "acquisition effort" ledger for research-grade coverage
  accounting -- deferred; this milestone's only coverage-adjacent
  requirement (never creating live monitoring exposure) is satisfied by
  omission, not a new ledger.

## Files

- `src/mockingbird/observation/recorded_video_source.py` (new) -- bounded
  ffmpeg decode + deterministic `FramePacket` construction.
- `src/mockingbird/observation/offline_ingest.py` (new) -- the acquisition-
  session orchestrator.
- `src/mockingbird/observation/offline_ingest_cli.py` (new) -- CLI wrapper.
- `src/mockingbird/repository/product_repository.py` -- new
  `RecordedMediaAnalysisRunModel` + five small repository methods; the
  video branch of `import_source_folder_media_assets` now also populates
  `captured_at` from the container's own `creation_time`.
- `src/mockingbird/source_providers/media_provenance.py` -- `VideoProbeResult.
  captured_at` (additive).
- `src/mockingbird/storage/database.py` -- schema v40 -> v41.
- `src/mockingbird/api/main.py` / `src/mockingbird/api/schemas.py` -- two
  new routes + three new schemas.
- `src/mockingbird/__main__.py` -- one new CLI subcommand.
- `web/src/pages/StreamsPage.tsx` / `web/src/api/client.ts` /
  `web/src/api/types.ts` -- the "Analyze imported media" action.
- `tests/test_recorded_video_source.py`, `tests/test_offline_ingest.py`,
  `tests/test_recorded_media_analysis_api.py`,
  `tests/test_offline_ingest_cli.py`, `tests/test_media_provenance.py`
  (extended), `tests/test_persistence.py` (extended),
  `tests/test_stream_playback_contract.py` (fixed + extended).

## Testing expectations

See the test files above for the full, current regression set. Highlights:
real ffmpeg-decoded synthetic clips throughout (skipped, never faked, when
genuinely unavailable); an injected fake detector for the tracker/assembly/
admission path (this codebase's established hardware-adjacent convention --
no real CUDA/model bundle is available in this environment, mirroring
`tests/test_observation_frame_driven.py::FakeDetector` and `tests/test_
observation_session_api.py`'s identical precedent for the live
`/observation/start` route); zero monkeypatching of the actual admission
gates.
