# Acoustic Runtime & Quality v1

## Purpose

Acoustic / BirdNET Observation Foundation v1 (2026-08-22) built a
trustworthy but entirely *explicit/manual* acoustic path: a recorded audio
clip only ever got analyzed because an operator called `POST
/api/media/{id}/analyze-audio`, and live microphone capture explicitly did
not import its own segments or trigger analysis (see that milestone's own
"Known bounded gaps"). This milestone turns that foundation into a
bounded, restart-safe, quality-governed *runtime*:

```
bounded audio segment source
-> durable analysis work (a queue admission)
-> BirdNET inference
-> quality/abstention policy
-> candidate Observation/evidence
-> retry/recovery
-> bounded retention
```

No physical microphone exists in this development environment. This
milestone is software-first: the runtime is proven with deterministic
recorded-audio fixtures and a simulated segment stream
(`acoustic_runtime.FixtureSegmentSource`), never a live microphone.

## Phase A archaeology -- what already existed

Confirmed by direct reading, not assumed:

- `AcousticAnalysisRunModel` already had a `status` column whose CHECK
  constraint included `'queued'` -- but nothing ever inserted a row with
  that status; `create_acoustic_analysis_run` always inserted directly as
  `'processing'`, synchronously, inline in the HTTP request handler.
- `MicrophoneCaptureSession.poll_new_finalized_segments` had zero callers
  anywhere outside `audio_capture.py` itself.
- `DurableMonitoringSupervisor` (`monitoring/durable_supervisor.py`) is the
  established durable-retry/backoff/restart-recovery pattern in this
  codebase, but models a *small, mostly-static set of long-lived Streams*
  (reconciled by iterating the whole candidate list every pass) -- the
  wrong shape for a growing/draining backlog of many short-lived acoustic
  segments.
- `LocalStorageRetentionService` (`storage/retention_service.py`) is the
  simplest existing background-loop shape: a bare `threading.Thread` +
  `Event.wait`-based interruptible sleep + single-flight guard + "failure
  must never interrupt the rest of the app."
- `StreamRuntimeCheckpointModel` (schema, `storage/models.py`) already
  carries the exact retry/backoff/ownership column shape a durable queue
  item needs (`consecutive_failure_count`, `next_retry_at`,
  `app_instance_id`-style ownership token), just at per-Stream rather than
  per-item granularity.
- `_BoundedOffsetLedger`/`LedgerEvictionAccounting`
  (`observation/counterfactual_lineage.py`) is the established
  bounded-capacity-with-eviction-diagnostics idiom, reused by the
  evidence-cache "8 -> 32 -> 128" incident history.
- No prior "queue"/"work_queue"/"dead_letter" vocabulary exists anywhere in
  this codebase -- there is no parallel job framework to accidentally
  duplicate.

## Architecture decisions

### 1. Unit of work

One captured audio segment = one `MediaAssetModel` row
(`media_type="audio"`), created **without** an Event/Visit -- unlike the
existing manual `create_media_import`/`import_folder_media` paths, which
always create a needs-review placeholder Visit for a deliberately-uploaded
file. Continuous unattended capture means most segments hold no bird sound
at all; creating a placeholder Visit for every one of them would spam the
Review Queue with silence, directly contradicting "no fabricated wildlife
Observation." A candidate Visit is created later, only if BirdNET actually
finds something (`create_acoustic_candidate_visit`/`extend_acoustic_
candidate_visit`, both unchanged/additive to the existing admission path).

### 2. Durable queue / idempotency

`AcousticAnalysisRunModel` is extended in place (schema v43 -> v44, four
new nullable/defaulted columns: `consecutive_failure_count`,
`next_retry_at`, `claimed_by`, `claimed_at`) rather than adding a parallel
table. It already had the right status vocabulary (`queued`/`processing`/
`completed`/`failed`); this milestone is the first thing that actually
inserts a row as `queued` (`ProductRepository.enqueue_acoustic_analysis`,
via `create_acoustic_analysis_run(..., status="queued")` -- the manual
path's own call site is unchanged, still defaults to `"processing"`). One
row IS both the queue entry and its own attempt-history record -- no
second bookkeeping structure.

Idempotency is unchanged from the prior milestone, reused as-is:
`(media_asset_id, pipeline_version)` for the analysis attempt (now also
doubling as the enqueue-admission guard -- `enqueue_acoustic_analysis`
returns `"already_in_flight"`/`"already_processed"` rather than
duplicating), `(media_asset_id, window_start_ms, window_end_ms,
adapter_id)` for candidate creation. This is what makes "at-most-once
candidate" hold for free across retries and restarts -- re-analyzing the
same clip after a crash produces the same windows, which the existing
check recognizes as already-created.

### 3. Retry / restart recovery

A bounded ladder (5s / 30s / 120s, max 3 attempts before terminal
`failed`) -- deliberately reusing `durable_supervisor.DEFAULT_RETRY_
DELAYS_SECONDS`/`DEFAULT_MAX_CONSECUTIVE_FAILURES`'s exact values rather
than inventing a second bounded-retry convention. One shared decision
function, `_apply_acoustic_retry_decision` (`product_repository.py`), is
called by both:

- `reclaim_stale_acoustic_analysis_work` -- crash/stall recovery. A fresh
  process calls this once at startup with `stale_after=timedelta(0)`,
  which reclaims *every* `processing` row unconditionally (a brand-new
  process cannot have legitimately claimed any of them -- mirrors
  `prepare_for_supervision`'s identical "any nonterminal state is a crash
  leftover" reasoning). The running reconcile loop separately calls it
  with a 10-minute duration as a defensive sweep against a same-process
  worker that hung without crashing.
- `retry_or_fail_acoustic_analysis_run` -- a live, caught failure during
  analysis (not a crash).

Using one shared function means the two paths can never silently disagree
about the retry budget.

### 4. Backpressure (Phase D)

Two bounded layers, defense in depth:

1. **Intake-time per-Stream cap** (`DEFAULT_MAX_IN_FLIGHT_SEGMENTS_PER_
   STREAM = 100`), checked *before* a raw segment is ever imported as a
   MediaAsset -- an over-cap segment's raw file is deleted unimported,
   counted (`segments_dropped_capacity`), never silently accumulated. This
   is the primary bound: it prevents unbounded MediaAsset/file creation in
   the first place, not just unbounded queue rows.
2. **Global queued-depth cap** (`DEFAULT_MAX_GLOBAL_QUEUED = 500`),
   `ProductRepository.enforce_acoustic_queue_capacity` -- a secondary,
   coarser bound catching the case where several Streams are each
   individually under their own cap but collectively large. Evicts the
   *oldest* queued rows first (never the newest) to a terminal `failed`
   state with `error_code="acoustic_queue_capacity_exceeded"` -- never
   deleted outright, so eviction stays diagnosable; the row (and the audio
   it points at) is reclaimed later by the ordinary working-audio
   retention sweep, like any other non-evidence segment.

Bounded-capacity justification (not just asserted -- see
`test_acoustic_runtime.py::TestIngestAndBackpressure` and the acceptance
test's own burst phase): BirdNET analyzes roughly 23x faster than real
time on CPU (a real 35s field recording in ~1.5s, per the prior
milestone's own verification). At the default 15s live-capture segment
length, one segment arrives every 15s and takes well under 1s to analyze
-- under sustained realistic single-Stream load the queue never
approaches either bound; both only matter if analysis is genuinely
wedged/unavailable for an extended period. At capacity, the per-Stream cap
alone bounds unanalyzed backlog to at most ~25 minutes of audio per
Stream.

### 5. Retention (Phase E)

A small, dedicated sweep (`ProductRepository.run_working_audio_retention_
sweep`), deliberately separate from the existing, unmodified
`StorageRetentionSettingsModel`/`_storage_retention_evaluation` system and
**not** gated behind the general `automatic_cleanup_enabled` toggle.
Rationale: staying bounded is this new runtime's own correctness property
(the same category as "queue depth is bounded"), not a user retention
preference -- the existing toggle governs a materially bigger decision
(deleting *reviewed* or *superseded* evidence) that should stay
opt-in. Eligible for this sweep: `media_type == "audio"`, zero
`VisitEvidenceLinkModel` rows reference it (never became evidence -- no
detection, abstained, failed, and capacity-evicted are all the same case
here), no `queued`/`processing` run row still references it (never
deletes something still being worked on), older than
`DEFAULT_WORKING_AUDIO_TTL = 48h`. Anything that ever produced a candidate
has a `VisitEvidenceLinkModel` row and is therefore evidence -- it is left
entirely to the existing, unmodified general storage-retention system,
never touched here.

Deletes the file first (best-effort), only removes the DB rows once the
file is confirmed gone; a file-deletion failure leaves the row in place
(retried next sweep) and is counted (`retention_failures`) rather than
silently advancing past it -- the reverse order would risk a silently
orphaned file on a partial failure, exactly the "no silent unlimited disk
growth" property this sweep exists to guarantee.

### 6. Timestamp discipline (Phase F)

Each live-captured segment gets a real derived `started_at`
(`audio_capture.CapturedSegment`, computed as `session_started_at +
sequence_index * segment_seconds`, with `sequence_index` parsed directly
from ffmpeg's own `segment-%08d.wav` filename -- the muxer's own ground
truth, never a separately tracked counter that could desync). This becomes
`MediaAsset.captured_at` when the segment is imported
(`create_audio_segment_media_asset`), so the *existing, unmodified*
`acoustic_ingest.py` boundary-anchor logic (`boundary_anchor =
media_asset.captured_at or EPOCH_ANCHOR`; `observed_at = boundary_anchor +
timedelta(milliseconds=detection.start_ms)`) needs zero changes to produce
a correct absolute detection time -- proven deterministically end to end
in `test_acoustic_runtime.py::TestTimestampDeterminism`.

**Disclosed clock-provenance gap**: segment start time assumes ffmpeg's
segment muxer produces exactly back-to-back segments with no gap or
drift. This is not verified against real hardware -- no physical
microphone exists in this environment. A future milestone with real
microphone hardware should verify actual segment-boundary timing against a
real, long-running ffmpeg process and check for accumulated drift over
hours, not assume the nominal arithmetic holds indefinitely.

### 7. Analysis-window overlap / consolidation policy (Phase I)

Same-clip merging (`_merge_same_species_detections`, unchanged) already
collapses multiple raw ~3s BirdNET windows of the *same* species within
*one clip* into one detection. This milestone adds the genuinely new
piece: **cross-segment** consolidation, since segments now arrive
continuously and one bird calling across a 15s segment boundary would
otherwise fragment into two candidate Visits.

`ACOUSTIC_CONSOLIDATION_GAP = 3s` -- BirdNET's own fixed analysis window,
confirmed directly against the real bundled model, used as a structurally-
justified deterministic threshold rather than a value tuned from this
milestone's small benchmark corpus. Implementation lives in the runtime
layer (`AcousticRuntimeService._consolidating_admit`), not in `acoustic_
ingest.py` or `create_acoustic_candidate_visit` (both untouched by this
policy): before admitting a new detection, look up the most recent
`needs_review`, non-superseded, acoustic-origin candidate Visit for the
same `(stream_id, species)` whose Event ended within the gap
(`find_extendable_acoustic_candidate`); if found, extend it
(`extend_acoustic_candidate_visit` -- adds a new evidence link + a new
`SpeciesSuggestion` preserving that window's own original provenance,
extends `Event.ended_at`, raises `Visit.confidence` to the peak across the
whole encounter, never touches `review_status`/`reviewed_label`); if the
target turned out to be reviewed/superseded since the lookup (re-verified
*inside* `extend_acoustic_candidate_visit`'s own transaction), or if
nothing matched, fall back to an ordinary new candidate -- a detection is
never silently dropped.

Deliberately **not** applied to the manual on-demand `/analyze-audio`
path: each manual call is typically a deliberately-selected, independently
recorded clip, not a structurally-contiguous stream of segments, so
cross-call consolidation there would be a surprising, less-justified
behavior. Two genuinely distinct species in one clip (or across segments)
correctly remain two separate candidates -- proven with real BirdNET
output on a real overlapping-species fixture, not merged.

### 8. Quality / abstention policy (Phase H) -- benchmark-discovered fix

BirdNET's own confidence floor (default 0.5) and this product's
always-`needs_review` admission already implement "abstention over false
certainty" for genuinely ambiguous bird identifications by construction.
Building the bounded benchmark corpus (below) surfaced a real, concrete
gap this milestone fixes: **BirdNET-Analyzer's bundled `BirdNET_GLOBAL_
6K_V2.4` label set is not exclusively bird species.** Confirmed by direct
inspection of the real, installed labels file
(`birdnetlib/models/analyzer/BirdNET_GLOBAL_6K_V2.4_Labels.txt`), it
includes 13 explicit non-avian "soundscape" classes: `Dog`, `Engine`,
`Environmental`, `Fireworks`, `Gryllus assimilis` and `Miogryllus
saussurei` (both crickets), `Gun`, `Human non-vocal`, `Human vocal`,
`Human whistle`, `Noise`, `Power tools`, `Siren`.

Nothing before this milestone filtered these out: a real, clearly-licensed
lawnmower recording (added to the benchmark corpus specifically for
"mechanical/environmental confusors") scored `Engine` at 0.61 confidence
-- above the *default* 0.5 floor -- meaning the pre-existing `create_
acoustic_candidate_visit` would have created a fabricated needs-review
"bird" candidate Visit for a lawnmower. Fixed via `acoustic_ingest.
NON_AVIAN_SOUNDSCAPE_LABELS` (a denylist of the exact 13 confirmed
strings), applied in the shared `_execute_acoustic_analysis` helper
*before* merge/admission -- so both the manual and automatic pipelines
benefit uniformly. `windows_analyzed`/`detections_above_threshold` on the
run row still honestly report BirdNET's raw, unfiltered output (a real,
diagnostically useful fact, distinct from "N candidates were created") --
this filtering only changes candidate-creation eligibility, never
operational-history honesty.

With that fix in place, the bounded benchmark corpus (8 evaluable clips)
showed **zero false positives and 100% recall** at the existing default
`min_confidence=0.5`. This corpus is too small to derive a new global
threshold with statistical confidence in either direction; the explicit,
evidence-proportionate decision is: **keep `DEFAULT_MIN_CONFIDENCE = 0.5`
unchanged.** See "Acoustic benchmark" in the final milestone report for
the full corpus/results.

### 9. Diagnostics (Phase J)

Reuses existing conventions exactly, no new diagnostics system:

- A new Doctor check (`DoctorCheckCode.ACOUSTIC_RUNTIME`,
  `_gather_acoustic_runtime`/`_interpret_acoustic_runtime`), mirroring
  `_gather_offline_ingest`'s identical "lazy model import, bare read-only
  Core query, `OperationalError` means not-yet-migrated" shape, plus
  queue-depth/oldest-pending-age aggregates and BirdNET runtime
  availability. `INFORMATIONAL` when nothing has run yet or the optional
  BirdNET package is absent; `WARN` (never `BLOCKING` -- acoustic analysis
  is an optional capability, visual observation is unaffected) when the
  queue is genuinely stale (>10 minutes oldest-pending) or recent runs
  failed.
- New `ErrorTaxonomyEntry` registrations under the existing
  `ErrorComponent.MODEL_RUNTIME`, mirroring the RTSP-setup-validation
  block's own "new codes for a new capability, existing component" style:
  `acoustic_queue_capacity_exceeded`, `acoustic_analysis_interrupted`,
  `acoustic_segment_probe_failed`, `acoustic_retention_delete_failed`.
- `AcousticRuntimeService.status()` -- a bounded, process-local counters
  snapshot (`AcousticRuntimeCounters`, resets on restart, exactly like
  `_EngineSession._evidence_harvest_misses`) combined with the
  always-durable-derived `acoustic_analysis_queue_diagnostics` (queue
  depth, processing count, oldest queued age, recent failure/eviction
  counts -- computed fresh from rows every call, never a separately
  maintained counter that could drift from reality).

No raw audio, no per-segment high-cardinality identifiers, in any
diagnostic surface.

## Two real, pre-existing bugs found and fixed during this milestone

Neither is new code from this milestone, but both were found via direct
integration/end-to-end testing while building it, and both are fixed
because they concretely affect this milestone's own diagnostics/quality
surfaces:

1. **Non-avian soundscape classes were never filtered** -- see "Quality /
   abstention policy" above. Pre-existing since Acoustic / BirdNET
   Observation Foundation v1; found via the new benchmark corpus's real
   lawnmower fixture; fixed in `acoustic_ingest.py`.
2. **`get_birdnet_status()` raised an uncaught `ValueError`** if called
   after `_install_tflite_runtime_shim` had already installed its
   spec-less `tflite_runtime` shim module earlier in the same process --
   `importlib.util.find_spec` refuses to guess about a `sys.modules` entry
   with `__spec__ is None`. `_tflite_backend_name` already had the correct
   guard (`"tflite_runtime" in sys.modules or ...find_spec(...)`,
   short-circuiting); `_missing_runtime_packages` did not. Found only by
   the Phase K end-to-end acceptance simulation (a unit test using a fake
   `recording` never exercises the real shim-installation path at all) --
   in a real deployment this meant `GET /api/birdnet/status` (and this
   milestone's own new runtime diagnostics) would 500 after the *first*
   real acoustic analysis in the process, never before. Fixed via one
   shared `_tflite_runtime_importable()` helper, reused by both call
   sites, in `species/birdnet_adapter.py`.

## Files

- `src/mockingbird/observation/acoustic_runtime.py` (new) -- the
  reconcile-loop service: `SegmentSource` protocol,
  `MicrophoneSegmentSource` (production), `FixtureSegmentSource`
  (deterministic test/simulation), `AcousticRuntimeService`.
- `src/mockingbird/observation/acoustic_quality_benchmark.py` (new) --
  Phase G/H corpus manifest + real-adapter evaluation/scoring.
- `scripts/evaluate_acoustic_quality.py` (new) -- CLI wrapper.
- `src/mockingbird/observation/acoustic_ingest.py` -- refactored to share
  `_execute_acoustic_analysis` between the manual and automatic paths;
  `NON_AVIAN_SOUNDSCAPE_LABELS` filter; `execute_queued_acoustic_analysis`
  for the automatic pipeline.
- `src/mockingbird/observation/audio_capture.py` -- `CapturedSegment`,
  `MicrophoneCaptureSession.poll_new_finalized_segments_with_timing`
  (additive; the pre-existing `poll_new_finalized_segments` now delegates
  to it, unchanged behavior), `MicrophoneSessionManager.running_stream_
  ids`/`poll_new_finalized_segments_with_timing`.
- `src/mockingbird/repository/product_repository.py` -- `AcousticAnalysisRunModel`
  retry/claim columns; `enqueue_acoustic_analysis`, `claim_next_queued_
  acoustic_analysis`, `reclaim_stale_acoustic_analysis_work`, `retry_or_
  fail_acoustic_analysis_run`, `enforce_acoustic_queue_capacity`,
  `acoustic_analysis_queue_diagnostics`, `create_audio_segment_media_
  asset`, `find_extendable_acoustic_candidate`, `extend_acoustic_
  candidate_visit`, `run_working_audio_retention_sweep`, `resolve_
  acoustic_species_guess`.
- `src/mockingbird/storage/database.py` -- schema v43 -> v44
  (`_migrate_to_acoustic_runtime_queue`).
- `src/mockingbird/species/birdnet_adapter.py` -- the `get_birdnet_status`
  crash fix (`_tflite_runtime_importable`).
- `src/mockingbird/diagnostics/doctor.py` -- `DoctorCheckCode.ACOUSTIC_
  RUNTIME` check.
- `src/mockingbird/diagnostics/error_taxonomy.py` -- four new codes.
- `src/mockingbird/api/main.py` -- `AcousticRuntimeService` app-owned
  singleton, started/stopped alongside the durable monitoring supervisor.
- `src/mockingbird/api/schemas.py` -- `AcousticAnalysisRun`'s four new
  fields.
- `tests/fixtures/acoustic/` -- two new real, clearly-licensed recordings
  (Black-capped Chickadee, a lawnmower confusor) plus four derived/
  synthetic fixtures; `PROVENANCE.md` fully updated.
- Tests: `tests/test_acoustic_runtime.py` (new), `tests/test_acoustic_
  quality_benchmark.py` (new), `tests/test_acoustic_unattended_
  acceptance.py` (new, real-model/`slow`-marked), plus focused additions
  to `tests/test_acoustic_ingest.py`, `tests/test_audio_capture.py`,
  `tests/test_birdnet_adapter.py`, `tests/test_doctor.py`, `tests/test_
  persistence.py`.

## Known bounded gaps

- **Live microphone hardware field acceptance remains deferred** -- no
  physical microphone exists in this environment (also true of the prior
  milestone). The runtime is proven with a deterministic fixture/simulated
  segment stream, which exercises the real `MediaAsset`/queue/analysis/
  retention machinery identically to a real capture session; only the
  literal `MicrophoneCaptureSession` subprocess-capture layer itself
  (unchanged by this milestone) remains unit-tested-with-an-injected-fake-
  process rather than live-hardware-verified.
- **Segment-boundary clock drift over a real, long-running capture session
  is not measurable without real hardware** -- see "Timestamp discipline"
  above.
- **Cross-segment consolidation is per-Stream, per-species only** -- it
  does not attempt any audiovisual correlation (explicitly out of scope
  for this milestone) and does not consolidate across a Stream restart's
  own live-capture session boundary (a genuinely separate future capture
  session starting fresh is treated as unrelated, which is honest --
  nothing here claims otherwise).
- **The benchmark corpus is deliberately small (8 evaluable clips)** -- see
  "Acoustic benchmark" in the final milestone report. Sufficient to tune/
  validate this milestone's runtime policy; not research-grade, and no
  claim of general BirdNET calibration is made from it.
