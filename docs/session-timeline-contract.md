# Reconnect-safe session-timeline contract

Status: Observation Engine v2 Stage 6.8 engineering-workflow contract, extending
[temporal-review-capture-contract.md](temporal-review-capture-contract.md).

## Problem

Stage 6.7 daylight collection ran two real Camera Node sessions and found that
the real Node resets its per-connection transport sequence header and this
codebase's source-relative offset bookkeeping on every HTTP reconnection,
while `provider_generation` (the camera/provider identity) stays unchanged.
Reconnecting every few seconds is the *normal* case on this transport
(session-01: 13 resets in 2m37s; session-02: 53 resets in 10m07s), not a rare
failure. That exposed three related defects, all rooted in one assumption:
that connection-local `sequence`/`source_offset_ms` are globally comparable
across a whole capture session.

1. `AppearanceInterval` validation compared raw `source_offset_ms` across
   frames from different connections, so a later frame from a new connection
   (near-zero local offset) could look "reversed" relative to an earlier
   frame from the previous connection (high local offset).
2. `temporal_review_io.build_review_packet`'s contact-sheet/index ordering and
   `temporal_annotation`'s exports sorted by the same raw, connection-local
   fields, scrambling cross-connection order.
3. `replay.ReplayInput` requires strictly increasing `source_offset_ms`
   (`ordered_timestamps`); feeding it raw connection-local offsets across a
   multi-reconnect session fails that check, so only a manually selected,
   connection-safe sub-window could be replayed.

## Three distinct concepts

- **Source-local facts**: `sequence`, `source_offset_ms`, `provider_generation`,
  `source_capture_timestamp` -- exactly what one Camera Node connection
  supplied. Never overwritten, never treated as globally comparable.
- **Connection segment**: one contiguous transport connection/generation, with
  a deterministic identity, an ordinal within the session, first/last frame
  identities, original sequence/offset ranges, a host-receive-time range when
  known, and a timing-quality classification
  (`measured_host_clock`/`reconstructed_sequence_order`).
- **Session timeline**: a deterministic, monotonic, engineering-only
  correlation coordinate (`session_sequence`, `session_offset_ms`) used only
  inside one capture session. It is explicitly *not* a camera monotonic
  timestamp -- it is derived from retained provenance so every retained frame
  gets one stable, comparable position regardless of how many reconnects
  happened in between.

## Module

`mockingbird.observation.session_timeline` is pure (no filesystem, network,
CUDA/ONNX Runtime/OpenCV, or product-repository import) and independent of
every other Stage 6.x module, so it introduces no import cycle:
`session_timeline` <- `temporal_capture` <- `temporal_annotation`.

`SourceFrameFact` is the bounded per-frame input: source-local facts plus two
*native* signals a Stage 6.8 capture records directly -- a real per-connection
identity (`connection_segment_hint`) and a host receive timestamp
(`host_received_at_iso`). Either may be `None` for a pre-Stage-6.8 record.

`derive_session_timeline(facts, *, session_id)` returns a `SessionTimeline`
(`classification`, `frames`, `segments`, `limitations`, `upgrade_provenance`):

- **Native** (every fact carries both native signals): processes facts in the
  *given* order -- the caller's own true chronological/receipt order, per
  "frame order observed by the authenticated analysis source" -- and uses
  each frame's host-receive delta only to measure the *step* to the next
  frame, never as a resort key. This means a genuine host-clock regression
  cannot silently reorder frames relative to true arrival order: the step
  clamps forward (minimum 1ms) and the frame is flagged with elevated
  `temporal_uncertainty_ms` instead. A reconnect (`connection_segment_hint`
  change) is flagged `temporal_discontinuity=True` with a small bounded
  uncertainty (the PC receive clock is not synchronized to the Node's capture
  clock); a measured gap at or beyond `LONG_GAP_THRESHOLD_MS` (5 minutes)
  adds an explicit limitation rather than being silently absorbed.
- **Derived** (any fact is missing a native signal): a pre-Stage-6.8 manifest
  never recorded a per-connection identity or host receive time. Its stored
  frame order groups frames by raw, connection-local `source_sequence`
  ascending (real captures wrote it that way; see `to_semantic_dict()`
  below), which is not chronological once more than one connection
  contributed frames. `derive_session_timeline` reconstructs plausible
  connection segments with a deterministic greedy bin-packing pass: sort by
  ascending `source_sequence` first (so this never depends on an unstated
  input-order precondition), then place each frame into the first still-open
  segment whose last-assigned sequence is lower than this frame's own
  sequence, opening a fresh segment only when none qualifies. Within any
  reconstructed segment this guarantees strictly increasing `source_sequence`
  -- exactly the property a single real connection has. Segment ordinal is
  assigned by creation order, which -- because ties at the same sequence
  value keep the stored array's own (chronologically stable-sorted) relative
  order -- approximates true connection start order without claiming to
  prove it. The true duration of a reconstructed reconnect gap is unknown and
  is never fabricated: the assigned `session_offset_ms` step across it is
  always the minimal 1ms needed for strict ordering, and
  `temporal_uncertainty_ms` is set to the documented, deliberately generous
  `LEGACY_RECONNECT_GAP_UNCERTAINTY_MS` (30s) instead of inventing a
  plausible-looking duration. Validated on both real Stage 6.7 sessions: the
  reconstructed segment count matches each session's own recorded
  `generation_reset_count + 1` exactly (14 and 54).
- **Insufficient**: `derive_session_timeline` itself never returns this
  classification (it always succeeds given well-formed `SourceFrameFact`s or
  raises `SessionTimelineError`); it is a value a caller constructs directly
  when even the minimum required source-local provenance cannot be read from
  raw data at all -- see `temporal_capture.upgrade_capture_manifest_timeline`.

Deterministic, monotonic, reproducible for repeated calls with the same
input, independent of filesystem paths or process identity, and never
recomputes a current-wall-clock value: every fact used is already a stored
record.

## Capture-manifest schema (v2)

`CAPTURE_MANIFEST_SCHEMA_VERSION` is 2. `RetainedFrameRecord` gains, all with
safe defaults so hand-built records (tests, the one-off validation-burst
frame) remain valid without knowing about timeline derivation:

- `host_received_at` (str, `""` = not recorded) and `source_capture_timestamp`
  (str | None): source-local facts a live capture always had available but
  the pre-Stage-6.8 schema never persisted.
- `connection_segment_id` (str), `connection_segment_ordinal` (int),
  `session_sequence` (int), `session_offset_ms` (int),
  `previous_frame_identity` (str | None), `temporal_discontinuity` (bool),
  `temporal_uncertainty_ms` (int): the derived session-timeline coordinate.

`CaptureSessionManifest` gains `session_timeline_classification` (defaults
`native_session_timeline`) and `timeline_upgrade_provenance`
(`dict | None`). `to_semantic_dict()` orders `frames` by `session_sequence`,
not the raw per-connection `sequence` (a manifest whose frames never went
through timeline derivation, every `session_sequence` still at its 0 default,
degrades to the tuple's own construction order via Python's stable sort --
unchanged from single-connection/no-reconnect behavior).

`temporal_capture_cli._CaptureLoop._retain()` now records
`host_received_at`/`source_capture_timestamp` from the live `FramePacket`,
and `connection_segment_id` from `frame.node_session_id` -- the real,
already-flowing-through, per-HTTP-connection Node session id (see
[camera-node-live-shadow-contract.md](camera-node-live-shadow-contract.md)),
just never previously recorded here. `temporal_capture.attach_session_timeline`
runs once, after the whole bounded session finishes, over the complete
retained-frame set -- not incrementally while capture is still running -- and
merges the derived coordinate back onto each record; `_run_capture` uses its
output for the final manifest's frames and top-level classification/
provenance fields.

## Backward-compatible upgrade

`temporal_capture.upgrade_capture_manifest_timeline(manifest: dict) -> dict`
is the one entry point for upgrading a *loaded* capture-manifest dict. An
already-native manifest (every frame already carries
`connection_segment_id`/`host_received_at` and
`session_timeline_classification == "native_session_timeline"`) is returned
completely unchanged -- same object, same fingerprint, no recomputation.
Otherwise it derives the timeline, merges it onto a *new* dict (frames
resorted into session order, matching what a native capture's own
`to_semantic_dict()` guarantees), recomputes `semantic_fingerprint` to cover
the added fields, and never mutates its argument or touches a filesystem.
When even `sequence`/`source_offset_ms` cannot be read as valid data, it
returns a `insufficient_temporal_provenance` manifest with frames completely
unchanged (no fabricated `session_*` fields) rather than raising past the
caller.

`temporal_review_io.build_review_packet` is the one place this runs against a
real file: it loads the *original* capture directory's manifest (read-only,
never opened for writing), upgrades it, and writes the upgraded dict as the
review directory's own `capture-session-manifest.json` -- the review
directory's copy is not always byte-identical to the original, but the
original capture directory's own file is never touched. Crops, the contact
sheet, and the HTML index are ordered by `session_sequence`.
`temporal-review-validate`/`-export` operate only on the (already-upgraded,
self-contained) review-directory copy.

## Operator-marker correlation

`temporal_capture.correlate_markers_to_frames(frames, markers)` is a new,
pure, post-hoc pass distinct from `_CaptureLoop`'s bounded live rescue
buffers: given every retained frame's `host_received_at` and the full marker
set, it recomputes each frame's complete, deterministically deduplicated
`operator_marker_ids` using the same `markers_near` bounded-lookback rule the
live path already uses. Because it is host-time based, it is unaffected by a
connection-local `sequence` reset and freely crosses a reconnect boundary
when timing genuinely supports it -- including onto a frame that already
retained itself for an unrelated trigger, and onto a frame outside the live
capture's bounded rescue window. `_run_capture` runs this once at the end of
every capture as a final honest pass over the whole session. A frame lacking
`host_received_at` (a legacy record) is returned unchanged -- no association
is fabricated where the required timing evidence was never recorded.

## AppearanceInterval validation

`validate_annotations` compares `session_offset_ms` (via the new
`_session_offset`/`_session_bounds` helpers), never raw `source_offset_ms`.
A frame lacking a derived `session_offset_ms`, or a manifest classified
`insufficient_temporal_provenance`, rejects with the new
`appearance_frame_missing_session_timeline` code rather than silently
comparing meaningless values. The reversed/out-of-bounds checks use `0` as
the only independent floor (a valid derived coordinate never starts below
zero); an upper bound re-derived from the same frame set an appearance's own
endpoints necessarily belong to would be tautologically unable to fire, so it
is not attempted -- corrupted data is instead caught by the floor check and
by `V_UNKNOWN_FRAME_REFERENCE`. A new `excessive_discontinuity_requires_
uncertainty` code rejects an appearance that both crosses a connection
segment (`connection_segment_id` differs between its endpoints) *and* spans
more than `MAX_CROSS_SEGMENT_SPAN_MS_WITHOUT_UNCERTAINTY` (10s) unless the
reviewer set `continuity_ambiguous=True` -- crossing one reconnect boundary
alone, or any short span, is fully supported without it.
`classify_episode_boundary_failures`'s generation-range scan uses the same
session-relative offsets.

## Export targets

All three continue to reuse their existing schemas unchanged (no new field
changes truth semantics -- `animal_present`/`boxes`/`scorable` are untouched):

- **Detector calibration**: `sequence_order`/`source_offset_ms` now carry
  session-relative values; the original connection-local values are
  preserved as new, additive `original_source_sequence`/
  `original_source_offset_ms` fields, alongside `connection_segment_id`,
  `connection_segment_ordinal`, `temporal_discontinuity`, and
  `provider_generation`. Verified byte-identical `animal_present`/`boxes`
  truth against the real, human-reviewed session-01 annotation (0
  mismatches across 95 frames).
- **Motion proposal**: ordered by session timeline, so "consecutive in the
  ordered list" now honestly means session-adjacent (including across a
  reconnect) instead of being scrambled by connection-local sequence resets.
  `source_offset_ms_range` is grounded in the retained frames' own
  `session_offset_ms` min/max, not an independently-settable top-level field
  that could (and, before Stage 6.8, silently did) disagree with actual
  frame data. Adds `connection_segment_count` and
  `session_timeline_classification` to `temporal_sequences` for honest
  predecessor/segment-boundary reporting.
- **Replay**: `replay.ReplayFrame` gains optional, additive fields
  (`captured_at_iso`, `source_sequence`, `original_source_offset_ms`,
  `connection_segment_id`, `connection_segment_ordinal`,
  `provider_generation`, `temporal_discontinuity`, `temporal_uncertainty_ms`)
  -- absent on any pre-Stage-6.8 input, which keeps `ReplayInput.fingerprint`
  byte-identical to before for one. `build_replay_export` feeds
  `source_offset_ms` the *session-relative* coordinate (already strictly
  monotonic by construction), so `ReplayInput.__post_init__`'s
  `ordered_timestamps` check -- unmodified -- passes on an ordinary
  multi-reconnect session; the true connection-local offset is preserved
  separately as `original_source_offset_ms`. This normalizes what the export
  feeds replay validation; it does not weaken that validation. Refuses
  (`replay_export_requires_session_timeline`) rather than emitting a
  meaningless export when the manifest is classified
  `insufficient_temporal_provenance`. High-resolution frames remain excluded
  (unchanged rule: one `ReplayInput` is one consistent resolution) and the
  exclusion is now explicitly reported via a new `high_resolution_exclusion`
  block (`excluded_frame_count`, `excluded_frame_ids`, `reason`) instead of
  being silent. `temporal_review_cli.run_export`'s replay target now also
  copies every referenced source frame into `<output>/images/` (via the new
  `temporal_review_io.copy_replay_export_images`) -- the manifest alone
  referenced `images/<frame_id>.jpg` paths that nothing had ever written,
  which meant a real `replay-benchmark --frames` invocation against a
  previous export could not actually load without a separate manual copy
  step.

## Replay/tracker interpretation

`replay.ReplayInput.packets()` carries the new fields onto `FramePacket`:
`captured_at`, `frame_sequence` (from `source_sequence`), `provider_generation`,
and `timing_facts` (`connection_segment_id`, `connection_segment_ordinal`,
`temporal_discontinuity`, `temporal_uncertainty_ms`,
`original_source_offset_ms` -- only the ones actually set). A reconnect-safe
export's session-relative `source_offset_ms` stays monotonic straight through
a reconnect, so the frame-driven tracker's own monotonicity check alone
cannot detect the gap.
`frame_driven_provider.FrameDrivenObservationProvider.replay_frames` now
checks `_replay_frame_is_discontinuous(previous, current)` between every
consecutive pair (a `provider_generation` change, or an explicit
`temporal_discontinuity` timing fact) and, when true, finalizes the current
tracker generation and starts a fresh one via the new
`_reset_tracking_for_replay_discontinuity("provider_reset")` -- reusing the
existing `"provider_reset"` reason `restart_live_generation` already
establishes for the live path, not a new taxonomy. Unlike the live path, the
drained results are kept in the replay report: replay has no other place to
report a generation that ended exactly at a reconnect boundary. This is a
new, purely additive replay-mode behavior gated entirely behind data a
pre-Stage-6.8 replay input never carries, so it never changes behavior for
one (all thirteen replay/frame-driven regression suites pass unmodified). The
tracker and episode-boundary logic themselves are unchanged; `_finalize_
tracking`/`ProviderNeutralFrameTracker` are the same Stage 4/6.1 components
described in
[frame-driven-shadow-provider-contract.md](frame-driven-shadow-provider-contract.md).

## Historical upgrade validation

Both real Stage 6.7 captures were rebuilt end to end (`temporal-review-build`
-> real reviewed `annotation.json` migrated by re-pointing only its
`capture_manifest_fingerprint` at the upgraded manifest, no truth field
touched -> `temporal-review-validate` -> `temporal-review-export --target
replay` -> `python -m mockingbird replay-benchmark --provider snapshot`):

| | session-01 | session-02 |
| --- | --- | --- |
| retained frames | 95 | 393 |
| reconstructed segments | 14 | 54 |
| recorded `generation_reset_count` | 13 | 53 |
| classification | `derived_session_timeline` | `derived_session_timeline` |
| validation | 0 rejects | 0 rejects (2 pre-existing ambiguous-truth flags) |
| full-session replay | loads, 0 errors, 63/95 frames (32 high-resolution excluded and reported) | loads, 0 errors, 270/393 frames (123 high-resolution excluded and reported) |
| repeated export | byte-identical `input_fingerprint` and full payload | byte-identical `input_fingerprint` and full payload |

Neither session required a manually selected connection-safe sub-window.
session-02's four real operator markers did not correlate to any frame even
after upgrade: the legacy manifest never recorded `host_received_at`, so
post-hoc correlation has no timing evidence to work with, and no association
is fabricated to compensate -- an honest data-completeness limit of the
historical capture, not a defect in this stage's correlation logic (proven
working on native, host-timestamped data by the hardware-free suite).

## Authority and limitations

No command in this stage opens the product database, changes the detector,
tracker confirmation policy, evidence scoring, burst policy, Camera Node
configuration, monitoring policy, or product records/reviewed truth, or
grants Stage 7 authority. `session_timeline.py` and every module it touches
remain shadow-only, `creates_truth=false`. Recurring-static-geometry burst
deduplication/cooldown (123 high-resolution frames in session-02; 379 track
generations across 393 retained frames from repeatedly triggering fresh
bursts on the same static structures) is a separate, not-yet-addressed issue
this stage does not fix.
