# Reviewed temporal capture and active-learning dataset contract

Status: Observation Engine v2 Stage 6.6 engineering-workflow contract.

## Boundary

`mockingbird.observation.temporal_capture`/`temporal_annotation` and their
`_io`/`_cli` counterparts are an engineering-only acquisition and review
workflow, not a product feature. They capture bounded live temporal
sequences from a paired Camera Node, produce an auditable local review
packet, record human-reviewed whole-frame/box/appearance/usefulness truth,
validate that truth against stable rules, and export deterministic
manifests into the three existing benchmark schemas (Stage 6.2 detector
calibration, the Stage 6.5 motion-proposal temporal cohort shape, and the
Stage 2 replay benchmark shape) -- inventing no new schema for any of them.
Every output remains `shadow_only=true`, `creates_truth=false` with no
production proposal authority. The module imports no product repository and
opens no product database; it cannot create or mutate Event, Visit,
MediaAsset, MotionEvidence, evidence link, primary selection, ReviewLabel,
reviewed Observation, monitoring policy, or policy revision. This stage
implements no new detector or proposal strategy: `temporal-capture` reuses
the Stage 5 `LiveCameraNodeShadowSession`/`CameraNodeHttpTransport` and the
Stage 6.5 `motion_proposal_strategy.generate_proposals` unchanged.

## Module split

- `temporal_capture.py` -- pure: `CaptureBounds`, `CaptureSessionConfig`,
  `OperatorMarker`/`markers_near`, `RecurringGeometryTracker`,
  `PeriodicNegativeScheduler`, per-frame trigger classification, and
  `CaptureSessionManifest` assembly/fingerprinting. No CUDA, ONNX Runtime,
  OpenCV, or camera-provider type anywhere in its contract.
- `temporal_capture_io.py` -- safe filesystem I/O only: the same
  new-or-empty/symlink-free output-directory bound every earlier benchmark
  IO module uses, atomic frame/manifest writes, and operator-marker file
  read/write. `CameraNodeConnectionConfig` (host/credential/camera/stream/
  evidence-profile) is deliberately a separate type from every semantic
  manifest type -- nothing in `temporal_capture.py` can carry it.
- `temporal_capture_cli.py` -- the one place that opens a real network
  connection: `temporal-capture` and `temporal-capture-mark`. `_CaptureLoop`
  drives bounded, checkpointed batches of `LiveCameraNodeShadowSession.run()`
  and applies the pure trigger/bounds contract to decide retention; it never
  reimplements the Node transport, detector, or tracker.
- `temporal_annotation.py` -- pure: the human-annotation schema
  (`BoxAnnotation`, `AppearanceInterval`, `EvidenceUsefulness`,
  `Provenance`, `FrameAnnotation`, `AnnotationSet`), `validate_annotations`,
  active-learning classification, dataset statistics/sufficiency, and the
  three export transforms.
- `temporal_review_io.py` -- the one place that touches PIL for pixel
  rendering (box overlays, contact sheet, HTML index), mirroring
  `multi_scale_cli`/`build_overlays.py`'s existing convention of keeping
  box-drawing out of every pure module. Also owns annotation-file
  read/write and makes a review directory fully self-contained (it copies
  the capture manifest and every original source frame in, so
  `temporal-review-validate`/`-export` need only `--review`).
- `temporal_review_cli.py` -- `temporal-review-build`,
  `temporal-review-validate`, `temporal-review-export`.

## Capture-session manifest

`CaptureSessionManifest.to_semantic_dict()`/`.fingerprint` cover every
bullet of the required capture contract: schema version, session/Node
identity, transport/provider keys, analysis dimensions/FPS, host/source
start-end times, sequence range, per-frame identities/offsets, sequence
gaps/dropped/coalesced/stale counts (read from the reused
`CameraNodeAnalysisSource.status()`), Privacy/Ignore regions, model
fingerprint, a combined tracker+motion-proposal-strategy configuration
fingerprint, evidence-profile id, the full `CaptureBounds`, the actual stop
condition, and limitations. `CaptureSessionConfig`/`CameraNodeConnectionConfig`
are structurally separate types (see above), so an absolute path, hostname,
credential, or bearer token cannot enter the semantic manifest -- proven by
a hardware-free test that greps the serialized manifest for the fixture
credential value and the tmp-path prefix.

## Bounded capture behavior

`CaptureBounds` carries all thirteen required hard ceilings (duration,
analysis frames, bytes stored, high-resolution frames, detector
observations/frame, active tracks, operator markers, pretrigger frames,
post-trigger frames, periodic-negative interval and count, adjacent-context
frames, pending burst requests, output files). `_CaptureLoop.run()` checks
every bound between bounded `session.run()` batches and returns the exact
`STOP_*` reason that fired; no in-memory buffer (retained-frame list,
decoded-motion-plane cache, marker set) grows past its bound -- the plane
cache in particular uses an explicit evict-from-both-structures-together
loop rather than a `maxlen` deque, because a `maxlen` deque would silently
drop the oldest id from the order list without ever freeing the
correspondingly larger cached plane, which a hardware-free test catches
directly.

## Triggers

All ten documented triggers are stable reason codes
(`TRIGGER_ANIMAL_ABOVE_OPERATING_POINT` /
`_BELOW_OPERATING_POINT_ABOVE_REVIEW_FLOOR`, `_SHADOW_TRACK_EVENT`,
`_MOTION_PROPOSAL_GENERATED`, `_HIGH_RESOLUTION_BURST`, `_OPERATOR_MARKER`,
`_PERIODIC_NEGATIVE_SAMPLE`, `_RECURRING_STATIC_GEOMETRY`,
`_PRIVACY_IGNORE_INTERACTION`, `_GENERATION_OR_SEQUENCE_DISCONTINUITY`),
plus `_PRETRIGGER_CONTEXT`/`_POST_TRIGGER_CONTEXT` for the bounded context
window a genuine trigger pulls in around itself. An operator marker never
requires a detector event: `markers_near` correlates purely on host time
within the marker's own bounded lookback, so a frame with zero detections
is still retained when a marker covers it. Motion-proposal generation
reuses `motion_proposal_strategy.generate_proposals` unchanged against a
small in-memory plane cache; a provider-generation change clears that cache
and the pretrigger buffer and is itself a trigger, so a proposal is never
computed across a generation boundary. Recurring static geometry reuses the
same IoU/centroid clustering rule `detector_benchmark.cluster_static_false_
positives` already established, applied live and bounded to 64 tracked
clusters.

## Operator marker

`OperatorMarker` supports the five required kinds (wildlife visible now /
recently visible / uncertain possible / known empty / noteworthy
environmental change) with a bounded lookback, a stable marker id, and no
species claim. `temporal-capture-mark` is a small separate CLI process that
writes one timestamped JSON file into the running capture directory's
`markers/` subdirectory; `_CaptureLoop` polls that directory once per
checkpoint. This keeps marking decoupled from the capture process's own
event loop (a repository-consistent local mechanism, per the task's own
allowed options) and makes it trivially testable without any real keyboard
interaction. A marker is engineering evidence only until a human transcribes
it into `annotation.json`; it never creates a product ReviewLabel or
Observation.

## Review packet

`temporal-review-build` produces, per retained frame: one overlay crop
(detector boxes in red, motion-proposal boxes in blue, a title bar with
trigger reasons -- the same box-drawing technique
`data/field-acceptance/.../build_overlays.py` already validated) and an
entry in one chronological HTML index (sorted by `sequence`, independent of
on-disk write order). One bounded grid contact sheet covers all retained
frames at a glance. Track episodes and adjacent negative context are not
separate artifact types: they fall out of the same per-frame overlay
sequence, grouped by `provider_generation`/`active_track_count` and by the
pretrigger/post-trigger trigger reasons already on each record. A fresh
`annotation.json` skeleton (every frame `unreviewed`) is written only if one
does not already exist, so re-running review-build never discards
in-progress human review. No OCR, remote service, or new UI framework is
used -- everything is local PIL rendering plus static HTML.

## Human annotation contract

`FrameAnnotation`/`BoxAnnotation`/`AppearanceInterval`/`EvidenceUsefulness`/
`Provenance` implement every required field group: whole-frame truth
(`yes`/`no`/`ambiguous`/`unreviewed`, plus `yes_but_unscorable`); box truth
(class, partial-visibility, occlusion, edge-clipping, blur, distance
proxy, box confidence, review limitation); temporal appearance (start/end
frame identity, instantaneous, entry/exit uncertainty, continuity
ambiguity); evidence usefulness (broad confirmation / identification /
context usefulness, subject absence, undecodable, ambiguous); and
provenance (reviewer, timestamp, source session, truth source -- including
`product_review_record` with an explicit `product_review_label` and
`whole_frame_independently_confirmed` flag, so a product Visit-level label
can never silently become whole-frame negative truth).

## Annotation validation

`validate_annotations` reads a capture-manifest dict and an `AnnotationSet`
and returns every required check as a stable `ValidationIssue` code:
`scorable_yes_requires_box_or_unscorable`,
`negative_frame_has_positive_boxes`, `box_outside_image_bounds` (enforced at
construction by `BoxAnnotation.__post_init__`),
`temporal_interval_outside_sequence_bounds`, `appearance_interval_reversed`,
`duplicate_logical_identity`, `missing_source_media`,
`content_hash_mismatch` (both via a caller-supplied, pure-preserving
`actual_content_hash` lookup), `product_false_positive_treated_as_frame_
negative`, `stale_generation_evidence` (an appearance spanning a
`provider_generation` change), `privacy_masked_content_marked_usable_
without_override`, and `capture_manifest_fingerprint_mismatch`. Ambiguous
truth and unmarked overlapping-appearance continuity are `flag` severity
(surfaced, does not fail validation) rather than `reject`, because
ambiguous frames are legitimately reviewed truth excluded from scoring
*downstream* by the reused Stage 6.2 pipeline, not by the validator itself.

## Export targets

All three reuse an existing schema unchanged:

- **Detector calibration**: the Stage 6.2 `CalibrationManifest`/
  `CalibrationFrame`/`ReviewedBox` shape.
- **Motion proposal**: the identical schema, with real `sequence_id`/
  `sequence_order`/`source_offset_ms` from the live capture session's own
  order (the same reuse Stage 6.5 established for temporal cohorts) plus a
  descriptive `temporal_sequences` block (ordered frame ids, offset range,
  derived animal-present intervals, sequence-gap/generation-reset counts).
- **Replay**: the Stage 2 `ReplayInput`/`BenchmarkManifest` shape
  (`ExpectedAppearance`/`ExpectedDetection`/`ExpectedEvidence`).
  `EvidenceUsefulness`'s fields were deliberately chosen to mirror
  `ExpectedEvidence`'s fields one-to-one. `visits` is always empty: this
  annotation contract records appearance intervals, not reviewed Visit
  boundaries, and inventing a one-appearance-per-Visit mapping would claim a
  review judgment nobody made.

`temporal-review-export` refuses to write anything when
`validate_annotations` reports any `reject`-severity issue.

## Active-learning classifications

`classify_active_learning` reads one retained-frame record and its
annotation and returns a bounded tuple drawn from the required fourteen
categories (`true_positive`, `false_positive`, `false_negative`,
`below_threshold_true_positive`, `hard_negative_static`,
`hard_negative_motion`, `duplicate_detection`, `ambiguous_truth`,
`privacy_excluded`, `tracking_failure`, `episode_boundary_failure`,
`useful_training_positive`, `useful_training_negative`, `hold_for_review`),
using the same `MATCH_IOU_THRESHOLD = 0.5` convention as
`detector_benchmark`. These are engineering dataset-curation labels only,
never product truth, and classification never mutates a model, a runtime
threshold, or any retained record.

## Dataset statistics

`compute_dataset_statistics` aggregates every required count across one or
more (capture-session, annotation-set) pairs -- sessions/frames,
reviewed/unreviewed, positive/negative/ambiguous, reviewed-box count,
sequence/appearance counts, small-subject/blur/clip/occlusion counts, scene
diversity, hard-negative cluster count, false negatives, below-threshold
positives, Privacy/Ignore examples, provider fingerprints, content-hash
duplicates -- and a per-benchmark-target `benchmark_sufficiency` using the
same general, not-fit-to-one-session bounds
(`classify_export_sufficiency`, mirroring
`detector_benchmark.classify_sample_sufficiency`'s own bound philosophy):
at least 20 reviewed positive and 20 reviewed negative frames, at least 2
distinct scene/camera groups, and at least 3 distinct capture sessions. A
single feeder or a single day's capture cannot satisfy this by
construction.

## Privacy and artifact safety

Every capture/review/export output directory goes through the identical
new-or-empty, symlink-free, `data/`-contained safe-output-directory check
every earlier benchmark IO module already uses; `data/` remains fully
`.gitignore`d. No command opens the product database, and a source-grep
hardware-free test asserts none of the six Stage 6.6 modules references the
product repository, SQLAlchemy, `mockingbird.api.main`, or a product truth
table constructor.

## Commands

```sh
python -m mockingbird temporal-capture \
  --camera-node-config <ignored-config.json> \
  --provider frame-driven-onnx-cuda --provider-config <ignored-model-config.json> \
  --output <ignored-output-directory> --duration <bounded-seconds>

python -m mockingbird temporal-capture-mark \
  --capture <capture-directory> --kind wildlife_visible_now [--note "..."]

python -m mockingbird temporal-review-build --capture <capture-directory> --output <review-directory>
python -m mockingbird temporal-review-validate --review <review-directory>
python -m mockingbird temporal-review-export --review <review-directory> \
  --target detector-calibration|motion-proposal|replay --output <output-directory>
```

## Daylight collection

The bounded real mechanics smoke (nighttime, no wildlife present) verified
transport mechanics only -- authentication, bounded retention, manifest
correctness, reconnect recovery, periodic sampling, and operator-marker
rescue. It is not a substitute for daytime collection with genuine wildlife
activity and must never be reported as one. Daylight collection is a
separate, not-yet-run, human-supervised step using the identical commands:

```sh
cd /home/zkelder/projects/mockingbird-active
source data/runtime/venvs/observation-onnx-cuda/bin/activate
export PYTHONPATH="$PWD/src"
NVIDIA_PY_LIBS="$PWD/.venv/lib/python3.12/site-packages/nvidia"
export LD_LIBRARY_PATH="$NVIDIA_PY_LIBS/cu13/lib:$NVIDIA_PY_LIBS/cudnn/lib:$NVIDIA_PY_LIBS/cusparselt/lib:$NVIDIA_PY_LIBS/nccl/lib:$NVIDIA_PY_LIBS/nvshmem/lib"

python -m mockingbird temporal-capture \
  --camera-node-config <path-to-real-camera-node-config.json> \
  --provider frame-driven-onnx-cuda \
  --provider-config <path-to-real-provider-config.json> \
  --output <new-empty-daylight-capture-directory> \
  --duration 600 --max-analysis-frames 1500 --validation-burst

# In a second terminal, whenever wildlife is directly observed, whether or
# not the automated detector reacted:
python -m mockingbird temporal-capture-mark \
  --capture <same-daylight-capture-directory> \
  --kind wildlife_visible_now \
  --note "<what was actually seen, engineering description only>" \
  --lookback-seconds 20

python -m mockingbird temporal-review-build \
  --capture <same-daylight-capture-directory> --output <new-empty-review-directory>
# Edit <review-directory>/annotation.json by hand against contact-sheet.jpg
# and the per-frame crops/frames before continuing.
python -m mockingbird temporal-review-validate --review <review-directory>
python -m mockingbird temporal-review-export --review <review-directory> \
  --target detector-calibration --output <new-empty-export-directory>
```

Checklist:

- [ ] Confirm the Camera Node is reachable (`/node/v1/health`) and daylight
      conditions are actually present before starting -- this step exists to
      collect real wildlife activity, not another empty scene.
- [ ] Use `--duration 600` (the ten-minute hard ceiling) rather than a short
      smoke-length run; real feeder activity is sparse and bursty.
- [ ] Keep a human present and attentive for the full session. Fire
      `temporal-capture-mark --kind wildlife_visible_now` (or
      `uncertain_possible_wildlife` if unsure) immediately on any sighting,
      especially ones the operator suspects the detector missed --
      marker-triggered retention is designed for exactly that case, and one
      marker per genuinely distinct sighting is more useful than one marker
      covering several.
- [ ] After the run, read `capture-session-manifest.json`'s `stop_condition`
      and bound counters honestly before assuming the session went as
      planned (a `transport_error`/`byte_limit`/`frame_limit` stop is a real
      operational fact to record, not to silently retry away).
- [ ] Run `temporal-review-build`, then genuinely inspect
      `contact-sheet.jpg` and the per-frame crops/frames -- do not
      auto-approve. Annotate `whole_frame_truth` (`yes`/`no`/`ambiguous`)
      and box truth by hand for every frame; leaving frames `unreviewed`
      keeps them out of the scorable denominator rather than silently
      counting them as negative.
- [ ] If a frame corresponds to a product Visit, record `product_review_label`
      and `whole_frame_independently_confirmed` truthfully -- a Visit-level
      `false_positive` label alone is never sufficient to mark a frame
      `whole_frame_truth: "no"`.
- [ ] Run `temporal-review-validate` and resolve every rejection before
      exporting; flags (e.g. ambiguous-in-denominator,
      continuity-unmarked) do not block export but should be looked at.
- [ ] Export to whichever of the three targets the next benchmarking task
      actually needs, and read the printed `benchmark_sufficiency` line
      rather than assuming one day's session is enough -- report the
      dataset's real size and limitations (single feeder, single session,
      time-of-day, weather) alongside any benchmark that later consumes it.
- [ ] Confirm `git status`/`git check-ignore -v` show every new capture,
      review, and export path under `data/` before considering the session
      complete -- none of it belongs in version control.

Daylight collection completed with two real Camera Node sessions (session-01:
95 retained frames, 13 reconnects in 2m37s; session-02: 393 retained frames,
53 reconnects in 10m07s -- approximately 5-6 reconnects per minute). This
exposed that the real Node resets its per-connection transport sequence and
this codebase's source-relative offset bookkeeping on every HTTP
reconnection while `provider_generation` stays unchanged, which broke
cross-connection `AppearanceInterval` validation, review/export ordering, and
full-session replay export (only a manually selected, connection-safe
sub-window could be replayed). Stage 6.8 adds a reconnect-safe session
timeline that fixes all three while preserving original source-local
provenance unchanged -- see
[session-timeline-contract.md](session-timeline-contract.md), which both
real sessions' captures now upgrade and replay through end to end.

## Authority and limitations

No command selects or applies a runtime threshold, creates or applies an
Ignore region, changes the Stage 4/6.1 tracker or Stage 6 evidence scoring,
implements a new detector or proposal strategy, or changes which provider
MockingBird actually runs. `active_track_count`/`track_generation_ids` on a
pretrigger/post-trigger context record are not independently recomputed
(they reuse the triggering frame's own facts where available and are
otherwise empty), a documented simplification since context frames exist
for visual continuity, not as independent detection evidence. Broad scene
displacement, camera-generation reset mid-burst, and privacy-boundary
interaction detection inherit the same honestly-documented limitations as
the Stage 6.5 adaptive-proposal contract. No outcome of this stage
authorizes production Visit proposals or Stage 7.
