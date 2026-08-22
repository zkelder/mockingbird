# Acoustic / BirdNET Observation Foundation v1

## Purpose

Before this milestone, MockingBird's Observation/review architecture only
ever produced evidence from video: a Camera Node, RTSP/USB/DirectShow
Stream, or recorded-video import. Audio was a deliberately deferred,
named-but-unbuilt capability -- see "Audio-aware boundary" in
[durable-camera-monitor-lifecycle-design.md](durable-camera-monitor-lifecycle-design.md)
(Roadmap phase 24C) and the "Audio." entry in
[roadmap.md](roadmap.md). This milestone closes that gap: a microphone or
recorded-audio clip can now produce an evidence-backed, reviewable
wildlife Observation through BirdNET-class provisional identification,
without weakening the existing reviewed-truth architecture.

```
microphone/audio source -> captured audio evidence -> BirdNET-class
provisional identification -> review/correction -> authoritative
Observation -> Today/Bird Log/history
```

Audiovisual fusion (associating an acoustic detection with a simultaneous
visual one) is explicitly **not** attempted here -- see "Scope exclusions."

## Architecture decision

### 1. Is audio another Source capability/type, or a bounded extension?

A bounded extension of the existing Source/Stream/Evidence/SpeciesSuggestion/
ReviewLabel chain, not a parallel truth system. `Source` was already
defined broadly enough ("An adapter-backed input that can provide video,
images, clips, or stream data" -- glossary.md); this milestone adds one new
concrete provider (`microphone`, `SOURCE_PROVIDER_DEFINITIONS`) and reuses
the existing generic file-import path (`SUPPORTED_MEDIA_CONTENT_TYPES`/
`SUPPORTED_MEDIA_EXTENSIONS`, now audio-aware) for recorded clips -- no new
Source provider type for the file path, mirroring how recorded-video
analysis is an *action* on an already-imported MediaAsset, not its own
provider.

### 2. What durable entity owns an audio clip?

The existing, generalized `MediaAssetModel` (Evidence) -- `media_type` was
already an unconstrained, application-level-only discriminator with two
values (`"image"`, `"video"`); adding `"audio"` required zero schema
migration. Two new nullable columns (`audio_sample_rate_hz`,
`audio_channel_count`) are the audio analog of `image_width`/`image_height`.

### 3. How does an audio-only detection become a provisional Observation
   candidate without pretending there was visual evidence?

BirdNET collapses what the visual pipeline does in two stages (a spatial
`DetectionProposal` locating *something*, then a `SpeciesSuggestion`
naming it) into one: a positive species score on a bounded ~3s window *is*
both the activity signal and the candidate identification. There is no
bounding box to report, so every geometry-shaped field
(`normalized_track_box_json`, `geometry_attribution_json`, `zone_id`) on an
audio-original Visit/MediaAsset stays genuinely `None` -- never fabricated.

`mockingbird.observation.acoustic_ingest.run_acoustic_analysis` is a small,
independently-written orchestrator, **not** a reuse of
`offline_ingest.run_offline_video_ingest`'s tracker/assembler/authority
machinery: `evaluate_evidence_admission` hard-requires a valid, non-
degenerate `normalized_box` (`reject_subject_geometry_invalid`) and
`evaluate_scene_confusor_suspicion` hard-requires a `candidate_box:
BoundingBox` parameter -- both genuinely geometry-coupled, confirmed by
direct reading, not assumed. Routing audio through them would mean
fabricating a box that was never observed, exactly the "pretending there
was visual evidence" trap this question warns against. Instead,
`ProductRepository.create_acoustic_candidate_visit` is a new, small, bounded
sibling to `create_candidate_visit_from_proposal`: it creates
`EventModel`/`VisitModel`/`VisitEvidenceLinkModel`/`SpeciesSuggestionModel`
rows directly, with `subject_label="bird"` (always correct and honest --
BirdNET's whole domain is birds), `zone_id=None` (Zones are geometric
regions on a frame; they do not apply to audio), and no scene-confusor/
evidence-quality geometry gate.

### 4. Which existing reviewed-truth machinery is reused unchanged?

Everything at and above the `SpeciesSuggestion` layer -- verified directly,
not assumed:

- `ReviewLabel`/`_create_review_label_in_session`/`review_provenance.
  is_authority_eligible`: completely unmodified. A BirdNET suggestion is
  confirmed/corrected/rejected through the exact same `POST /api/review-
  labels` (and Fast Review/bulk) endpoints a visual correction uses --
  these request/response schemas were already fully evidence-agnostic (no
  image field anywhere), confirmed by direct reading before any code was
  written.
- `SpeciesSuggestion` status lifecycle (pending/accepted/rejected/
  superseded) and `POST /api/species-suggestions/{id}/status`: unmodified.
- Today/Bird Log/Dashboard consumption (`dashboard_summary`,
  `wildlife_journal_overview`): **zero backend changes needed** -- proven
  directly (`tests/test_acoustic_ingest.py::test_full_review_flow_
  reaches_bird_log_and_today_unmodified`, and the equivalent real-model
  test): an audio-original reviewed Visit already appears in both
  correctly, because both already key off `review_status`/`reviewed_label`
  generically.
- Frontend confirm/correct/reject (`FastReviewPanel`, `VisitDetailPage.
  saveCorrection`, `IdentificationAssistPanel`): already tolerate zero
  image evidence at every call site (multiple pre-existing no-media
  fallback branches).

### 5. What minimal schema change was actually required?

One migration, v42 -> v43 (`_migrate_to_acoustic_observation_foundation`):

- `media_assets` gains nullable `audio_sample_rate_hz`, `audio_channel_count`.
- `species_suggestions` gains nullable `window_start_ms`, `window_end_ms`
  (the temporal analog of `evidence_region_json`) and
  `model_provenance_json` (adapter-neutral model/runtime provenance --
  reusable by any future adapter, not audio-specific by construction).
- One new, empty, bounded operational-history table,
  `acoustic_analysis_runs` (`AcousticAnalysisRunModel`), mirroring
  `RecordedMediaAnalysisRunModel`'s exact "one row per bounded attempt,
  never gates a Visit, honest no-detection outcome" role.

No new "Observation" table -- doctrine and the Research/Export contract are
both explicit that a reviewed Visit already *is* the Observation in this
schema; inventing a second persisted Observation object would be exactly
the broad Observation-semantics refactor this milestone was told not to do.

### 6. Timestamp representation for later audiovisual alignment

Reuses the *exact* convention `offline_ingest.py` established for recorded
video, not a second scheme: a clip has a `capture_start` (real UTC instant
when known); each BirdNET window carries `start_ms`/`end_ms` relative to
that clip; `observed_at = capture_start + offset` when known, otherwise the
*same* `EPOCH_ANCHOR` (`datetime(1970,1,1,tzinfo=UTC) + offset`) the video
path already uses -- an honestly-not-real date, never a fabricated "now."
Reusing the identical anchor (not a different one) is what would let a
future audiovisual-fusion milestone join a video frame and an audio window
on one timeline without a translation layer.

### 7. BirdNET runtime/package decision

See "BirdNET runtime decision," below -- the full, empirically-verified
answer.

## BirdNET runtime decision

**Chosen**: [`birdnetlib`](https://github.com/joeweiss/birdnetlib)
(Apache-2.0 wrapper) running the bundled **BirdNET-Analyzer
`GLOBAL_6K_V2.4`** TFLite model (Cornell K. Lisa Yang Center for
Conservation Bioacoustics / kahst BirdNET-Analyzer), on a lightweight
**`ai-edge-litert`** TFLite interpreter backend -- not full TensorFlow, not
`tflite-runtime`.

Every claim below was verified directly in this milestone's own working
session, not assumed from documentation:

- `pip index versions tflite-runtime` -> "No matching distribution found"
  for this project's supported Python versions. `birdnetlib` 0.18.1 only
  ever does `import tflite_runtime.interpreter as tflite`, falling back to
  a full `tensorflow` install otherwise (confirmed by reading its source).
  Rather than pull in full TensorFlow for a lightweight CPU interpreter,
  `mockingbird.species.birdnet_adapter._install_tflite_runtime_shim`
  resolves `ai-edge-litert` (Google's maintained successor, identical
  `Interpreter` API) and registers it under the `tflite_runtime` name
  *before* `birdnetlib` is imported -- a no-op if a real `tflite_runtime`
  genuinely is installed.
- Real transitive dependency closure beyond `birdnetlib`'s own declared
  deps (`pydub`, `matplotlib`, `requests`, `watchdog`): `librosa`,
  `resampy`, `audioread` -- none of these three are declared in
  `birdnetlib`'s own package metadata despite being hard imports;
  discovered by running real code in a scratch venv, not by reading its
  README. All five are pinned in the new `classifier-birdnet` optional
  extra (pyproject.toml).
- The model itself ships as real package data inside the `birdnetlib`
  wheel (confirmed by inspecting the installed wheel directly, 61MB) --
  installing the optional extra is the one explicit action that obtains
  it; no runtime download ever occurs, matching this product's existing
  "must not automatically download weights" rule for MDv5/BioCLIP.
- CPU-only by explicit design choice, mirroring the existing BioCLIP
  precedent (`BioClipAdapterConfig.device` hard-enforced to `"cpu"`):
  BirdNET-Analyzer's TFLite model is CPU-cheap by construction (a real
  35-second field recording analyzed in ~1.5s on CPU during verification).
- Real positive test: a real, clearly-licensed (CC BY-SA 3.0, attributed)
  Northern Cardinal recording (xeno-canto #75501 via Wikimedia Commons --
  see `tests/fixtures/acoustic/PROVENANCE.md`) correctly identified at
  0.78-0.999 confidence across every window. Real negative test: synthetic
  pink noise produced 0 detections at both a low (0.1) and realistic (0.5)
  confidence floor.

### Licensing, disclosed explicitly

The BirdNET-Analyzer model *weights* bundled inside `birdnetlib` are
licensed **CC BY-NC-SA 4.0** -- NonCommercial. Compatible with MockingBird's
current local, personal-use, non-commercial posture, structured as an
optional, removable extra (never required for core startup, weights never
committed to git, exactly like every other optional model dependency this
product already has) -- but a real constraint for any future commercial-
release decision, recorded here plainly per this codebase's existing
provenance rigor for MDv5/BioCLIP licensing, not glossed over.
`birdnetlib`'s own wrapper code is Apache-2.0 (no constraint).

### Alternatives considered and rejected

- Full `tensorflow` CPU backend: works (birdnetlib's built-in fallback) but
  a much heavier, redundant footprint for a lightweight inference-only
  need; `ai-edge-litert` does the same job at a fraction of the size,
  matching the "prefer a small runtime over a full framework" precedent
  already set by ONNX Runtime over full PyTorch for MDv5.
- A hand-rolled direct-TFLite integration against BirdNET-Analyzer's raw
  released model files, bypassing `birdnetlib` entirely: rejected as
  reinventing already-correct, maintained windowing/species-range/label
  logic for no real benefit -- "make one evidence-backed implementation
  decision rather than building multiple providers," and `birdnetlib` is
  exactly that one decision.
- A hosted/cloud BirdNET API: rejected outright per doctrine ("Do not use
  an external hosted API as the core production path"; "Do not make the
  product cloud-dependent").

### Configuration

Env-var-driven, mirroring the existing `MOCKINGBIRD_MEGADETECTOR_*`/
`MOCKINGBIRD_BIOCLIP_*` convention (`mockingbird.species.birdnet_adapter`):

| Variable | Purpose | Default |
| --- | --- | --- |
| `MOCKINGBIRD_BIRDNET_MIN_CONFIDENCE` | Confidence floor | `0.5` |
| `MOCKINGBIRD_BIRDNET_MODEL_PATH` | Optional override model path | unset (uses the bundled model) |
| `MOCKINGBIRD_BIRDNET_LABELS_PATH` | Optional override labels path | unset |
| `MOCKINGBIRD_BIRDNET_LATITUDE` / `..._LONGITUDE` | Optional species-range filter | unset (full global species list) |

Unlike MDv5/BioCLIP, no configuration is *required* for the common case --
the model ships inside the optional pip package itself.

## Implemented

### Phase B -- audio provider/capture foundation

- **Deterministic file provider**: recorded-audio import reuses the
  existing generic manual-upload (`create_media_import`) and folder-import
  (`import_folder_media`) paths, now audio-content-type-aware
  (`audio/wav`, `audio/x-wav`, `audio/mpeg`; `.wav`/`.mp3`).
  `mockingbird.source_providers.media_provenance.probe_audio_metadata`
  extracts duration/sample-rate/channel-count/`captured_at` via ffprobe,
  mirroring `probe_video_metadata` exactly.
- **Canonical clip format**: `mockingbird.observation.audio_capture.
  decode_audio_to_canonical_wav` bounded-transcodes any supported source
  format to 48kHz mono 16-bit PCM WAV (BirdNET's native rate) via ffmpeg
  (already a hard runtime dependency -- no new native audio library).
  Bounded by `max_duration_seconds` (default 900s); ffmpeg writes directly
  to disk, never buffered fully in memory.
- **Live microphone capture**: `audio_capture.MicrophoneCaptureSession`/
  `MicrophoneSessionManager` -- ffmpeg's own `segment` muxer produces
  bounded, finalized rolling WAV segments (default 15s), reusing the exact
  architectural choice this product already made for every other capture
  path (RTSP, Windows DirectShow) rather than adding a native PortAudio-
  backed dependency (`sounddevice`/`pyaudio`). Platform-aware command
  construction (`-f pulse`/`-f alsa` on Linux, `-f dshow` on Windows),
  injectable `platform_name` for hardware-free testing, mirroring
  `windows_camera_bridge.py`'s identical convention.
- **New Source provider**: `microphone` (`SOURCE_PROVIDER_DEFINITIONS`),
  `supports_live_playback=False`/`supports_zone_editing=False` (Zones are
  geometric; audio has no video privacy polygons to reuse -- see the
  "Audio-aware boundary" doc). Two config fields: `device`, `capture_consent`.
- **Explicit, separate consent**: reuses the existing, generic
  `SourceProviderConfigurationModel`/`update_source_provider_configuration`
  mechanism -- no new consent-specific persistence path. `capture_consent`
  must be the literal string `"true"`; never inherited from a Stream's
  video `armed`/monitoring-policy state, satisfying the Audio-aware
  boundary doc's explicit requirement.
- **API**: `POST/GET /api/streams/{id}/audio-capture/{start,stop,status}` --
  `start` refuses (403) without explicit consent and (400) without a
  configured device; a process-local `MicrophoneSessionManager` singleton
  (mirrors `get_live_camera_session_manager`'s identical lazy-singleton
  pattern), stopped on application shutdown. Deliberately does not itself
  import captured segments or trigger analysis -- capture and analysis
  remain two separate, explicit actions (mirrors the file-import path's
  own "explicit Analyze imported media action" discipline); a caller
  drains `poll_new_finalized_segments()`.

### Phase C -- BirdNET-class analysis

`mockingbird.species.birdnet_adapter`: `run_birdnet_on_clip` -- local
inference only, explicit model/version/license/runtime provenance
(`BirdNetProvenance`), deterministic configuration (env-var-resolved,
never silently varying), confidence/probability preserved exactly as
BirdNET reports it, candidate common/scientific name preserved, time-window
offsets preserved in milliseconds. No automatic authority: this function
returns detections, never writes anything. No-detection is a legitimate,
honestly-recorded outcome, never conflated with an error. Two independent
test-injection seams (`analyzer`, `recording`) let ordinary tests avoid
the real ~700MB optional dependency stack entirely.

### Phase D -- acoustic evidence

The audio clip persists as an ordinary `MediaAssetModel`
(`media_type="audio"`), linked to its Visit via the existing
`VisitEvidenceLinkModel` (`evidence_role="identification"`) -- bounded,
already suitable for playback (`GET /api/media/{id}/file`) and export. No
waveform/spectrogram generation was added in this v1 (see "Known bounded
gaps") -- the milestone brief treats this as optional derived
presentation, never observational authority, and the clip itself is
already real, playable evidence without it.

### Phase E -- acoustic Observation/review integration

Covered in architecture-decision point 4, above. `create_acoustic_
candidate_visit`'s idempotency key is `(media_asset_id, window_start_ms,
window_end_ms, adapter_id)` -- the audio-native analog of the visual
path's content-addressed `proposal_id`. Consecutive/overlapping same-
species BirdNET windows within one clip are merged into one candidate
Visit before persistence (`acoustic_ingest._merge_same_species_
detections`) -- never one Visit per raw ~3s window, which would fragment
one continuous vocalization into near-duplicate Review Queue items exactly
the way this product's own Visit Continuity work (2026-08-17) already
fixed for the visual path. Two *different* species detected in one clip
correctly become two independent candidate Visits (each its own Event --
see "Known bounded gaps" for the deliberately-deferred Event-sharing case).

### Phase F -- Today / Bird Log / place history minimum integration

Backend needed zero changes (proven directly, see point 4 above). Frontend,
deliberately minimal:

- `MediaAssetPreview.tsx`: a real `<audio controls>` playback branch for
  `media_type === "audio"` (Review Queue, Visit Detail).
- `VisitEvidenceSequence.tsx`: the single-frame case (every audio Visit
  today) renders a plain audio player instead of the image zoom viewer for
  that frame; multi-frame playback/thumbnail-strip chrome is unaffected
  (harmless no-op for a 1-item sequence, per direct reading of that logic).
- Ordinary-language copy: `"Bird heard — species not confirmed"` (vs.
  `"Animal detected — species not confirmed"`) in Dashboard/Review Queue
  where the evidence kind is directly known per-item; Bird Log's
  `JournalThumbnail` shows `"🔊 Heard"` instead of the genuinely-missing-
  evidence `"No saved thumbnail"` copy, so the two states read distinctly.
  Multi-day/multi-visit aggregate copy ("Seen on N of the last 14 days")
  was deliberately left unchanged -- see "Known bounded gaps."
- `StreamsPage.tsx`: an "Analyze imported audio" action mirroring the
  existing "Analyze imported media" (video) action exactly, shown only for
  `content_type.startsWith("audio/")`.
- `ModelAdapterKind.audio_classifier` (previously an unused reserved
  placeholder) is now the real kind BirdNET's status reporting corresponds
  to conceptually, though (per architecture-decision point 3's finding)
  the generic `run_model_adapter` dispatcher deliberately still excludes
  species/audio classifiers -- BirdNET has its own bespoke route
  (`/api/media/{id}/analyze-audio`), matching the existing precedent that
  `species_classifier` also bypasses that dispatcher.

### Phase G -- export/interoperability foundation

Two narrow, disclosed gaps found during archaeology and fixed (not a
redesign):

- `mockingbird.research.camtrap_dp`'s media `filePath` mapping hardcoded a
  `.jpg` extension regardless of the evidence's real content type
  (already silently wrong for recorded-video evidence, predating this
  milestone) -- fixed via a small, bounded `content_type -> extension` map
  covering every format this product's import path already supports.
- `_offline_acquisition_effort_for_scope` only recognized `media_type ==
  "image"`/video analysis runs; a completed `AcousticAnalysisRunModel` row
  had no corresponding fact type, which would have silently undercounted
  (never crashed) offline acquisition effort once audio existed. Fixed
  additively: `RecordedAudioAcquisitionFact` mirrors `RecordedVideo
  AcquisitionFact` exactly, threaded through `compute_offline_acquisition_
  effort`, `effort.csv`, and `ConservationReportResponse`
  (`offline_recorded_audio_*` fields, all defaulted so this is backward
  compatible).

Camtrap DP's `fileMediatype` field was *already* generic (a real MIME
string reused verbatim, not a closed image/video/audio enum) -- no fix
needed there. The generic CSV/JSON research export
(`ResearchEvidenceRecord`) was already fully format-agnostic (`width`/
`height` already nullable, `content_type` already a free string) -- no fix
needed there either.

## Files

- `src/mockingbird/observation/audio_capture.py` (new) -- bounded ffmpeg
  decode/transcode, live-microphone capture session/manager.
- `src/mockingbird/observation/acoustic_ingest.py` (new) -- the acquisition
  -session orchestrator (decode -> analyze -> merge -> admit).
- `src/mockingbird/species/birdnet_adapter.py` (new) -- BirdNET inference,
  provenance, status/config resolution.
- `src/mockingbird/storage/models.py` -- `MediaAssetModel.audio_sample_
  rate_hz`/`.audio_channel_count`.
- `src/mockingbird/storage/database.py` -- schema v42 -> v43.
- `src/mockingbird/repository/product_repository.py` -- `AcousticAnalysis
  RunModel`, `SpeciesSuggestionModel` additive columns, `create_acoustic_
  candidate_visit` + acoustic-analysis-run CRUD, `microphone`
  `SourceProviderDefinition`, audio content-type/extension registration,
  audio branch in folder-import provenance extraction, `SUPPORTED_MEDIA_
  CONTENT_TYPES`/`SUPPORTED_MEDIA_EXTENSIONS` audio entries, offline-
  acquisition-effort audio fact wiring.
- `src/mockingbird/source_providers/media_provenance.py` -- `AudioProbe
  Result`/`probe_audio_metadata`, `AUDIO_EXTENSIONS`, generalized
  `MediaKind`/`media_kind_for_extension`.
- `src/mockingbird/source_providers/folder_import_preview.py` -- audio
  extensions included in `SUPPORTED_EXTENSIONS` (opt-in only, mirrors the
  existing video precedent exactly).
- `src/mockingbird/research/acquisition_effort.py` -- `RecordedAudio
  AcquisitionFact`, `OfflineAcquisitionEffort` audio fields.
- `src/mockingbird/research/camtrap_dp.py` -- content-type-aware media file
  extension (bug fix, not audio-specific).
- `src/mockingbird/api/schemas.py` / `src/mockingbird/api/main.py` --
  `AcousticAnalysisRun`, `RecordedAudioAnalysisRequest/Response`,
  `BirdNetStatusResponse`, `AudioCaptureStatusResponse`,
  `SpeciesSuggestion*` window/provenance fields, `MediaAsset` audio
  fields, `ConservationReportResponse` audio fields, and the new routes.
- `pyproject.toml` -- `classifier-birdnet` optional extra.
- `.gitignore` -- `tests/fixtures/acoustic/*.wav`/`*.mp3` (real/synthetic
  local-only fixtures, mirrors the existing model-artifact convention).
- Frontend: `web/src/api/types.ts`, `web/src/api/client.ts`,
  `web/src/components/MediaAssetPreview.tsx`,
  `web/src/components/VisitEvidenceSequence.tsx`,
  `web/src/pages/DashboardPage.tsx`, `web/src/pages/BirdLogPage.tsx`,
  `web/src/pages/ReviewQueuePage.tsx`, `web/src/pages/StreamsPage.tsx`,
  `web/src/utils.ts`, `web/src/styles.css`.
- Tests: `tests/test_audio_capture.py`, `tests/test_birdnet_adapter.py`,
  `tests/test_acoustic_ingest.py`, `tests/test_acoustic_analysis_api.py`,
  `tests/test_acoustic_ingest_real_model.py` (real-model, `slow`-marked,
  `skipif`-gated), `tests/test_persistence.py` (extended),
  `tests/fixtures/acoustic/PROVENANCE.md`.

## Known bounded gaps

- **Live microphone capture is implemented and unit-tested (injected fake
  subprocess) but not live-hardware-verified** -- no microphone/audio
  input device exists in this development sandbox. The file-based
  recorded-audio path (the milestone's required deliverable) is fully,
  independently, real-model-verified end to end and proves the
  architecture; per this milestone's own validation doctrine, missing
  specialty microphone hardware is not treated as a blocker.
- **No automatic capture-to-analysis pipeline for live microphone
  segments.** A captured segment becomes an ordinary imported MediaAsset;
  analyzing it is a separate, explicit action (`analyze-audio`), mirroring
  the file-import precedent exactly. A future milestone could add a small,
  explicitly-scoped bounded poller if continuous unattended listening
  proves valuable -- deliberately not built here (see "Do not build a
  large generic audio framework").
- **No Event-sharing for two simultaneous distinct species in one clip**
  (each gets its own Event, unlike the visual path's `concurrent_sibling_
  proposal_ids` mechanism). Correct and honest as built (two independent
  candidate Visits), just not "tidy" -- a small, cheap follow-up, not a
  defect.
- **No waveform/spectrogram derived-evidence generation.** Explicitly
  optional per this milestone's own brief ("if useful and can be generated
  cheaply... never observational authority"); deferred as a presentation-
  only enhancement, not required for the core evidence-backed review loop.
- **Species-level daily/aggregate copy ("Seen on N of the last 14 days")
  was left unchanged** -- deliberately, since a multi-day species-level
  stat can legitimately mix heard-only and seen occurrences; only
  single-Visit-level copy (where the evidence kind is directly known) was
  made precise. A full "was every occurrence in this aggregate audio-only"
  treatment is future UI-polish scope, not attempted here.
- **`ModelAdapterKind.audio_classifier`** is now conceptually associated
  with BirdNET via this contract doc, but is not wired into the generic
  `ModelAdapter`/`run_model_adapter` status/dispatch surface (consistent
  with `species_classifier`'s own existing exclusion from that same
  dispatcher) -- `GET /api/birdnet/status` is BirdNET's own dedicated
  status route instead, mirroring the existing BioCLIP status precedent.

## Validation

See the final milestone report for exact commands/results by tier. Summary:
83 new focused tests across 6 files (5 hermetic + 1 real-model/`slow`-
marked/`skipif`-gated), zero regressions across every adjacent existing
test file exercised, `tsc --noEmit` and `vite build` both clean.
