# Sustained-visit tracker-continuity contract

Status: Observation Engine v2 Stage 6.16 engineering-workflow contract, extending
[frame-driven-shadow-provider-contract.md](frame-driven-shadow-provider-contract.md)'s
Stage 6.1 episode boundary. Independent of, and composes unchanged with,
[reconnect-continuity-contract.md](reconnect-continuity-contract.md).

## Problem

The Stage 6.10/6.15 representative shadow-acceptance campaign's real attempt-3 session
(9m24s-10m04s, real Camera Node, real CUDA MDv5 inference) directly confirmed one
genuine, continuous small-bird appearance at a feeder perch lasting approximately five
minutes (three real 4624x3472 high-resolution bursts spanning the start, middle, and
near-end of the visit). The Stage 6.11 reconnect-bridging fix was independently
confirmed intact (zero `provider_reset` terminations; 40 of 63 reconnect boundaries
bridged). Despite that, full-session frame-driven replay still fragmented this single
appearance into approximately 37 confirmed track generations (47 when counting
temporally- and spatially-adjacent unconfirmed fragments too).

A deterministic, frame-by-frame characterization (see the campaign's own
`fragmentation-characterization.md`, ignored/local) proved the dominant mechanism
directly, not by inference:

- **83% (39/47)** of fragment terminations were ordinary bounded-tolerance
  tracker-support-loss expiry (`tracker_lost` and its unconfirmed-track twin
  `insufficient_support`) -- `ProviderNeutralFrameTracker.observe()`'s existing
  `maximum_frame_gap_ms`/`tracker_expiry_ms` bound (1200-1500ms) is tighter than this
  sustained visit's own real, uneven analysis-frame cadence (average ~1.18s, with real
  transport jitter) and its intermittent detector-confidence dips below the model
  bundle's own hard decode floor.
- **13% (6/47)** were the existing `maximum_unsupported_detector_ms` (5000ms) cap.
- **4% (2/47)** were the absolute `maximum_track_duration_ms` cap.
- **0%** were explicit negative-detector intervals (`negative_interval_reentry`),
  reconnect/reset, ambiguous association, or true visual departure -- the reviewed
  appearance is present start to end.

A concrete, verbatim trace (three fragments in the visit's first 20 seconds alone) showed
the structural shape precisely: `observe()`'s ordinary per-track termination check runs
*before* the current frame's own detections are matched, so a track is torn down by
stale elapsed-time bookkeeping on the exact frame that would otherwise have matched and
continued it, and that detection instead starts a brand-new generation on the identical
frame.

## Bounded evidence hierarchy

Three kinds of evidence, expressed through `TrackUpdate.support_state` (additive; reuses
the existing `lifecycle_state="temporarily_lost"` vocabulary rather than adding a fourth
externally-visible value, matching the Stage 6.11 convention):

- **`strong_detector_supported`**: a matched detection at or above
  `TrackerConfiguration.strong_detection_threshold` (unchanged, pre-existing field).
  Normal behavior: increments `detector_confirmation_count`, refreshes every timestamp,
  and is the only kind of evidence that advances `last_strong_detector_offset_ms`.
- **`weak_detector_supported`**: a matched, spatially/class-coherent detection at or
  above `TrackerConfiguration.weak_detector_support_floor` (new; default `0.05`, reusing
  this product's existing calibrated `review_floor` concept and default from
  `temporal_capture_cli`'s `--review-floor`, not a scene-specific number) and below
  `strong_detection_threshold`. Refreshes ordinary continuity bookkeeping (missed-frame
  count, negative-frame streak, both offset timestamps, geometry) and its own separate
  `weak_detector_support_count`, exactly like a strong observation, but never advances
  `last_strong_detector_offset_ms`.
- **`tracker_supported`**: an unmatched frame resolved by the existing bounded
  tracker-support adapter (`TrackerSupportResolver`, unchanged). Refreshes ordinary
  continuity bookkeeping the same way, governed by the same bounded tolerance described
  below.

`detector_confirmation_count`/`minimum_detector_confirmations` keep their exact
pre-existing meaning and behavior: every genuine matched detector observation counts,
strong or weak, unconditionally, exactly as before this stage. This is deliberate, not
an oversight -- real attempt-3 evidence proved a genuinely continuous subject's own
*confirming* pair of observations is routinely both individually below
`strong_detection_threshold` (a real bird's natural confidence swings, e.g. one
observation at 0.37 and the next at 0.45, while still clearly the same coherent,
repeated, spatially-matched subject). Gating confirmation itself on strength -- an
earlier design considered and rejected during this stage's own validation -- would have
made *initial* confirmation harder, not just continuity more forgiving, directly hurting
the appearance recall this stage exists to improve. `minimum_detector_confirmations` was
always a repeated-evidence bar, never a strength bar.

## Widened confirmed-track gap tolerance

`ProviderNeutralFrameTracker._gap_bound(track, offset, tight_bound)` replaces the
ordinary tight bound (`maximum_frame_gap_ms` in the pre-assignment check,
`tracker_expiry_ms` in the post-assignment miss check) with
`max(tight_bound, maximum_unsupported_detector_ms)` -- reusing the existing,
already-configured `maximum_unsupported_detector_ms` (5000ms) rather than inventing a
new ceiling -- whenever `_widening_eligible(track, offset)` holds. The ordinary
frame-count-based `maximum_missed_frames` check is also skipped while eligible, relying
on the time-based bound alone: a coarse or jittery real analysis cadence naturally
produces more "missed" frames without that meaning the subject left.

`_widening_eligible` is confirmed-track-only (an already-confirmed track's own
`minimum_detector_confirmations` bar already filters one-off noise) and has two bounded
tiers:

- **Graduated**: the track has shown at least one genuinely strong detector hit at any
  point in its life (`last_strong_detector_offset_ms is not None`). Real attempt-3
  evidence shows a genuinely continuous subject's own detector confidence can swing for
  minutes with only rare peaks above `strong_detection_threshold` (only 4 raw detections
  across the whole ~600s session ever reached the deployed 0.7 threshold); once *any*
  such peak has occurred, the widened tolerance applies unconditionally for the rest of
  the track's life (still bounded below by `maximum_unsupported_detector_ms` and
  unconditionally by `maximum_track_duration_ms`).
- **Provisional**: the track has *never* shown a strong hit. It still gets the widened
  tolerance, but only for a bounded, one-time, non-renewable window measured from its
  own start (`maximum_weak_support_span_ms`, new; default `15000`ms, an explicitly
  derived 3x multiple of the existing `maximum_unsupported_detector_ms` default rather
  than an unrelated new number). Once that window elapses with no strong proof ever
  appearing, the track permanently falls back to the ordinary tight bound -- a
  persistent weak-only artifact (which can still *confirm* from repeated coherent
  evidence exactly like a real subject can) cannot ride an indefinite string of
  weak/tracker-only refreshes.

`maximum_unsupported_detector_ms` itself is deliberately **left unchanged at 5000ms**.
Raising it was considered, to bridge more of the real attempt-3 gaps (observed up to
~10.4s), but the existing
`test_ghost_tracker_support_does_not_absorb_a_later_distinct_appearance` regression (a
previously-fixed reviewed-replay incorrect-merge pattern: a loose/background-echoing
tracker-support resolver sustaining a track on pure tracker-support alone) proved a
materially larger value measurably weakens exactly the incorrect-merge/ghost-track
protection this stage must not trade away. This stage's fragmentation improvement comes
from the widened per-frame gap tolerance and weak-evidence continuity refresh alone,
which do not touch that ceiling's protective role.

## Weak-detector-support visibility

If a future provider's own detector decode floor sits below
`weak_detector_support_floor`, `ProviderNeutralFrameTracker.observe()` filters
`DetectionObservation`s below the floor out of its own candidate pool before
association -- the tracker's own explicit floor, independent of whatever a specific
provider's decode threshold happens to be. In the current real deployment
(`model-bundle.json`'s own `score_threshold=0.1`, already above the `0.05` default
floor) this is an inert safety margin, not an active filter -- consistent with the task
framing "if the existing provider currently discards below-operating-point detections
before the tracker can see them" being conditional: at the tracker/provider boundary
nothing was being discarded that the tracker needed added visibility into: the ONNX
decode's own `score_threshold` is the only pre-existing discard point, and it already
sits below `strong_detection_threshold`.

## No-immortal-track bounds

Every bound remains explicit and enforced:

- `maximum_weak_support_span_ms`: caps a never-strong ("provisional") track's widened
  eligibility window, one-time, non-renewable, from its own start.
- `maximum_unsupported_detector_ms` (unchanged, 5000ms): caps total elapsed time since
  *any* genuine detector evidence (strong or weak) regardless of confirmed/widening
  status -- unaffected by tracker-support-only refreshes, which never touch
  `last_detector_offset_ms`.
- `maximum_track_duration_ms` (unchanged): absolute cap regardless of confirmed status,
  evidence type, or widening eligibility.
- `negative_detector_frames_to_end`/`negative_interval_reentry` (unchanged): explicit,
  visually meaningful negative detector frames still count against the episode exactly
  as before -- the widened tolerance only relaxes *no-evidence* gaps, never explicit
  negative evidence.
- Geometry/class association (unchanged `_assign()` IoU/centroid/class gates): a weak
  detection is bound by the identical spatial-coherence test a strong one is: a
  spatially or class-incompatible weak detection cannot associate to an existing track
  and instead starts its own, independently-tentative generation.
- Reconnect bridging (Stage 6.11, unchanged): composes independently; a benign
  reconnect still marks tracks `temporarily_lost` pending bounded reacquisition and
  never itself adds detector or tracker support.

## Replay metrics

New pipeline facts, read directly from already-emitted `FrameDrivenObservationProvider`
semantic facts or derived from already-emitted `TrackUpdate.support_state`/generation
grouping -- no new provider contract field beyond `TrackUpdate.weak_detector_support_
count`/`support_state` themselves:

- `strong_detector_support_frame_count`, `weak_detector_support_frame_count`,
  `tracker_only_support_frame_count`: per-update `support_state` tallies.
- `confidence_dip_bridge_count`: frames where the widened tolerance -- not the ordinary
  tight bound -- is why a track was not terminated.
- `terminations_after_weak_support_count`: generations whose terminal `support_state`
  was weak or tracker-only rather than strong or a live `temporarily_lost` snapshot.
- `maximum_weak_support_span_ms`/`maximum_tracker_only_support_span_ms`: the longest
  observed contiguous run (by replay order, not frame count) of one generation's own
  updates carrying exactly that `support_state`.

These extend, and never duplicate, the existing Stage 6.1
`episode_temporary_loss_count`/`episode_confirmed_split_count`/
`boundary_reason_distribution` and Stage 6.11 `reconnect_*` metrics.

## Real replay validation

Re-run via a hardware-free recorded-detection playback harness (reuses each session's
own already-produced real-CUDA `replay-report.json` detections, replayed by frame
identity through the current tracker/provider code -- isolates exactly the tracker
continuity change this stage is scoped to, since the detector itself is provably
unchanged and deterministic; see the final acceptance report for the full method and its
one disclosed fidelity limitation).

| | attempt-3 (before -> after) | attempt-2 (before -> after) |
| --- | --- | --- |
| Tracks started | 63 -> 47 | 77 -> 65 |
| Tracks confirmed | 37 -> 25 | 38 -> 28 |
| Generations relevant to the reviewed appearance (time+geometry) | 47 -> 36 | n/a (no genuine appearance) |
| ...of those, confirmed | 29 -> 20 | n/a |
| `confidence_dip_bridge_count` | n/a -> 25 | n/a -> 28 |
| `strong_detector_support_frame_count` | n/a -> 5 | n/a -> 0 |
| `incorrect_merge_count` / `duplicate_count` | 0 -> 0 | 0 -> 0 |
| `proposal_precision` | 0.0 -> 0.0 (all-clutter session; n/a) | 0.0 -> 0.0 |

`appearance_recall`/`proposal_precision` measure literally `0.0` before *and* after for
attempt-3 -- proven, not assumed, to be the exact same structural limitation Stage 6.11
already disclosed for sessions 01-04: attempt-3's own temporal-review-capture export
carries `expected_visit_count=0` (an empty `ExpectedVisit` list) even though two real
`ExpectedAppearance` entries exist, so the visit-level matcher this metric depends on has
nothing to match against regardless of tracker quality. The honest evidence of
improvement is the generation-count and boundary-reason movement above, exactly as Stage
6.11 established for this same benchmark path's known limitation.

attempt-2 (hard negative, no genuine wildlife, real red-glass-feeder clutter whose
measured maximum score across its whole real session, 0.417, never once reached the
deployed `strong_detection_threshold` of 0.7): `strong_detector_support_frame_count=0`
confirms every one of its confirmed generations stayed in the bounded "provisional"
tier for its entire life. Proposal count *decreased* (38 to 28); precision stayed exactly
0.0 (no new false positives); zero incorrect merges or duplicates either side.

## Authority and limitations

No command in this stage opens the product database, changes the detector, detector
threshold, detector calibration, burst scheduler, reconnect continuity policy, Camera
Node transport, evidence scorer, session timeline, Privacy/Ignore configuration,
monitoring policy, or product Visit/reviewed-truth authority. Every module touched
remains shadow-only, `creates_truth=false`. `frame_tracker.py`, `frame_driven_
provider.py`, `contracts.py`, and `replay.py` import no product repository, SQLAlchemy,
or `mockingbird.api.main` (structurally enforced by hardware-free source-grep tests,
the same convention every earlier Stage 6.x pure module uses).
