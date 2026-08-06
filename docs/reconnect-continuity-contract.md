# Reconnect-safe tracker continuity contract

Status: Observation Engine v2 Stage 6.11 engineering-workflow contract, extending
[session-timeline-contract.md](session-timeline-contract.md) and
[frame-driven-shadow-provider-contract.md](frame-driven-shadow-provider-contract.md).

## Problem

Stage 6.10's representative shadow campaign ran two full-length real Camera Node
daylight sessions (session-03: 9m17s, 57 reconnects; session-04: 9m17s, 55
reconnects -- roughly one reconnect every ten seconds, consistent with the
already-documented session-01/02 rate) and found that full-session frame-driven
replay measured `appearance_recall = 0.0` and `proposal_precision = 0.0` in
*both* sessions: 129 tracks / 67 confirmed VisitProposals for 2 reviewed genuine
appearances in session-03 (roughly 33:1); 78 tracks / 27 confirmed for 3 in
session-04 (9:1). `boundary_reason_distribution` showed `provider_reset` as the
terminal reason for essentially every confirmed proposal (67 of 67 in
session-03; 29 of 78 terminations in session-04). The root cause: Stage 6.8's
session timeline correctly flags every reconnect boundary with
`temporal_discontinuity=True` regardless of `provider_generation` (a benign
Camera Node HTTP reconnect never changes it), but
`frame_driven_provider.replay_frames` treated *any* discontinuity signal --
benign reconnect or genuine source change alike -- as an unconditional
`"provider_reset"`, finalizing the current tracker generation and starting a
fresh one at every single reconnect. A genuine multi-second bird visit spanning
several reconnects was mechanically shredded into many short, independently
"confirmed" episodes.

Real reconnect gaps measured directly from session-03/04's own reconnect-safe
replay exports (`source_offset_ms` delta at each `temporal_discontinuity`
frame): 940-6868ms, mean ~2.5-2.9s, median ~2.4-2.5s -- routinely larger than
the tracker's own ordinary `maximum_frame_gap_ms` (1500ms default) and
`tracker_expiry_ms` (1200ms default), so even removing the blanket reset alone
would not have been sufficient; a dedicated, separately bounded bridge window
is required.

## Architectural rule: three separate concepts

A transport connection segment is **not** automatically an observation
generation, and an observation generation is not automatically a track
generation. Collapsing these into one number is exactly what produced the
Stage 6.10 failure.

- **Transport connection segment**: one HTTP analysis-stream connection. May
  reset transport sequence, connection-local source offset
  (`original_source_offset_ms`), and request/session identifier. Does not by
  itself prove the camera changed, the observation source changed, the animal
  disappeared, or that tracker generation must terminate.
- **Observation source generation**: a durable identity for the logical
  analysis source (`provider_generation` in this codebase -- already
  documented in session-timeline-contract.md as "the camera/provider
  identity"). Changes only when evidence indicates tracker continuity is
  unsafe: Stream identity change, Camera Node provider generation change,
  camera identity change, incompatible analysis profile change, an explicit
  provider reset, an unrecoverable source error, or excessive/uncertain
  temporal discontinuity.
- **Track generation** (`ProviderNeutralFrameTracker`'s existing concept, see
  frame-driven-shadow-provider-contract.md): one coherent subject episode. May
  now span more than one benign transport connection segment when continuity
  remains supported. Segment boundaries are never hidden -- they remain
  visible as provenance on every supporting frame and as new replay metrics
  (see below).

## Reconnect continuity decision contract

`mockingbird.observation.reconnect_continuity` is pure: no filesystem,
network, CUDA/ONNX Runtime/OpenCV, camera-provider, or product-repository
import, mirroring every other Stage 6.x decision module
(`session_timeline`, `burst_scheduler`). It never reads species/class
identity.

`is_reconnect_boundary_signal(previous, current)` is the *outer* gate,
unchanged from the Stage 6.8-era check it replaces: a real
`provider_generation` change, or an explicit `temporal_discontinuity` timing
fact. Returns `False` for every pre-Stage-6.8 input (neither fact ever set),
so behavior is completely unaffected for one -- the classifier below is never
even invoked.

Once a signal is present, `classify_frame_reconnect_boundary(previous,
current, config)` returns one of four stable, provider-neutral decisions:

- `continue_across_transport_reconnect`: full bridge eligibility confirmed;
  the tracker marks active tracks pending bounded reacquisition rather than
  terminating them.
- `temporarily_lost_across_reconnect`: not a boundary-level decision -- the
  bounded *per-track* status `ProviderNeutralFrameTracker.
  note_reconnect_boundary` applies to every currently active track once a
  bridge is granted, reusing the existing `lifecycle_state="temporarily_lost"`
  vocabulary rather than adding a new externally-visible lifecycle value.
- `reset_source_generation`: confidently evidenced discontinuity (a fact is
  *known* and disqualifying) -- Stream/camera/Camera Node identity change,
  incompatible analysis profile/dimensions, an explicit discontinuity reason,
  a shutdown/start boundary, or a known gap/uncertainty that exceeds its
  bound. Reuses the existing `"provider_reset"` terminal reason.
- `reject_continuity_insufficient_provenance`: the *minimum* provenance this
  stage needs to prove a boundary is benign is missing or self-contradictory
  (no connection-segment identity on one or both sides, no computable
  source-relative gap, no temporal-uncertainty fact, no provider-generation
  fact on one side, or a discontinuity signal fired without the connection
  segment actually advancing). A distinct `"insufficient_reconnect_
  provenance"` terminal reason keeps this honestly distinguishable from a
  confidently evidenced reset in `boundary_reason_distribution` -- both reset
  the same way, but only one of them means "we know the source changed."

The decision never uses species identity. Inputs are read only from already-
supplied `FramePacket` facts: `stream_id`, `provider_generation`, `width`/
`height`, and additive `timing_facts` keys established by Stage 6.8
(`connection_segment_id`, `temporal_discontinuity`, `temporal_uncertainty_ms`,
`original_source_offset_ms`) plus optional, forward-compatible keys a future
producer may set (`camera_id`, `camera_node_id`, `analysis_profile_id`,
`explicit_discontinuity_reason`, `shutdown_boundary`) -- present today in
tests only, since the current wire protocol does not yet transmit them
per-frame; when absent on either side they are simply not used as a signal,
never as a silent "assume unchanged."

## Benign reconnect eligibility

Continuity is only granted when *all* of the following hold:

- Stream identity matches (`stream_id`).
- `provider_generation` is known on both frames and matches.
- Analysis dimensions match when known on both sides (width/height), and no
  known `analysis_profile_id`/`camera_id`/`camera_node_id` differs.
- Both frames carry a known, non-empty `connection_segment_id`, and it
  actually changed (the segment genuinely advanced).
- The source/session-relative gap (`current.source_offset_ms -
  previous.source_offset_ms`) is known, non-negative, and at or below
  `maximum_reconnect_gap_ms`.
- `temporal_uncertainty_ms` is known and at or below
  `maximum_temporal_uncertainty_ms`.
- No explicit discontinuity reason or shutdown/start boundary fact is set.

A benign reconnect always remains visible in provenance -- the connection
segment transition is never rewritten as though no reconnect happened (see
"Replay metrics" below).

Explicitly *not* eligibility signals by themselves: transport sequence
resetting, connection-local `original_source_offset_ms` resetting to near
zero, or `connection_segment_ordinal` simply advancing -- all three are the
*expected*, benign shape of an ordinary reconnect, not evidence against one.

## Reconnect bridge configuration

`ReconnectBridgeConfig` (all fields bounded and validated in
`__post_init__`), general defaults sanity-checked against but not tuned to
the real session-03/04 gap measurements above:

| Field | Default | Meaning |
| --- | --- | --- |
| `maximum_reconnect_gap_ms` | 15000 | Eligibility bound on the boundary's own source-relative gap (>2x the real observed max of 6868ms) |
| `maximum_temporal_uncertainty_ms` | 2000 | Eligibility bound on known `temporal_uncertainty_ms` |
| `maximum_reconnect_bridge_duration_ms` | 8000 | Bounded session-relative-time patience budget for post-reconnect reacquisition |
| `maximum_reconnect_bridge_frames` | 8 | Bounded frame-count patience budget, independent of duration |
| `maximum_reconnect_geometry_displacement` | 0.18 | Max normalized centroid displacement for reacquisition (tighter than the tracker's own ordinary `maximum_centroid_distance` of 0.22 -- position uncertainty across an unknown-duration gap warrants more caution) |
| `maximum_reconnect_size_change_ratio` | 0.5 | Max fractional box-area change tolerated for reacquisition |
| `minimum_post_reconnect_support` | 1 | Bounded count of genuine post-reconnect matches required to consider a track reacquired |
| `ambiguity_policy` | `"reject"` | The only implemented policy: an ambiguous post-reconnect association is rejected, never guessed |

## Tracker bridge behavior

`ProviderNeutralFrameTracker.note_reconnect_boundary(boundary_offset_ms,
captured_at)` is called once per recognized benign boundary, before the first
post-reconnect frame is observed. It marks every currently active track
`reconnect_pending=True`, transitions `lifecycle_state` to
`"temporarily_lost"` (the existing vocabulary, not a new externally-visible
state), and grants each a bounded, independent reacquisition budget
(`reconnect_bridge_deadline_offset_ms`, `reconnect_bridge_frames_remaining`).
It never terminates anything and never adds detector/tracker support.

`observe()`'s ordinary per-track termination checks
(`negative_interval_reentry`, `maximum_unsupported_duration`,
`tracker_lost`) are *skipped* for a pending track -- a real reconnect gap
routinely exceeds those bounds by design, which is exactly the case this
bridge exists to cover. The absolute `maximum_track_duration_ms` cap still
applies unconditionally: a chain of reconnects can never keep a track alive
past its own maximum episode length.

On each subsequent frame, a pending track may be reacquired exactly like an
ordinary frame-to-frame association -- a matching detector observation or
bounded tracker-support match -- except reacquisition additionally requires
`_reconnect_reacquisition_compatible`: the candidate's geometry must be
within `maximum_reconnect_geometry_displacement`/
`maximum_reconnect_size_change_ratio` of the track's *last known* (not
velocity-extrapolated -- extrapolating across an unknown-duration gap is not
well-founded) bounding box. A track that is not reacquired decrements its
bounded frame budget every observed frame; once the budget or duration
deadline is exhausted, the track terminates with the new
`"reconnect_bridge_expired"` terminal reason (treated the same as
`tracker_lost` for confirmation/ambiguous-reentry purposes -- a bounded-
tolerance exhaustion, not positive evidence of discontinuity, so an
unconfirmed track still relabels to `insufficient_support` and a later
plausible reentry can still be honestly reported as ambiguous).

Simultaneous tracks bridge independently: each has its own budget, and one
may reacquire while another expires in the very same frame. An ambiguous
post-reconnect association (more than one active subject plausibly
compatible with one incoming detection) reuses the tracker's existing
ambiguity-margin mechanism unchanged -- neither candidate is assigned, and the
occurrence is additionally reported as `reconnect_ambiguous_associations` so
it stays distinguishable from ordinary tracking ambiguity. A terminated
(bridge-expired or reset) generation is never revived; the track/generation id
space is never reused.

## Support/confirmation safety

Reconnect survival never creates support by itself. `note_reconnect_boundary`
never calls `_observe_detection`/`_observe_tracker_support` -- the only two
places `detector_confirmation_count`/`tracker_support_count` change -- so
merely surviving one or many reconnects cannot promote a tentative track to
confirmed. Only genuine post-reconnect detector/tracker-support evidence
(observed on a real frame, through the same association path as any ordinary
frame) adds support, exactly as before this stage.

## Evidence and burst lineage

Evidence-candidate/burst-role bookkeeping is unchanged and remains keyed by
`generation_id` (`FrameDrivenObservationProvider._evidence`, popped and
finalized exactly once per generation). Because a benign reconnect never
finalizes the current generation, its evidence ring simply keeps accumulating
across the bridge like any other brief gap; because a `reset_source_
generation`/`reject_continuity_insufficient_provenance` reset *does* finalize
it (unchanged from the pre-Stage-6.11 reset path), evidence for the
terminated generation is popped and cannot leak into whatever generation
starts next. `_update_evidence` already no-ops while
`lifecycle_state == "temporarily_lost"`, so a reconnect-pending track records
no new "evidence" purely from being marked pending.

## Replay integration

`FrameDrivenObservationProvider.replay_frames` computes
`is_reconnect_boundary_signal`/`classify_frame_reconnect_boundary` between
every consecutive frame pair (previously: an unconditional reset on any
signal). A `continue_across_transport_reconnect` decision calls
`note_reconnect_boundary` and folds its "temporarily lost" transition updates
into that same first post-reconnect frame's own `ObservationResult` --
preserving "one `ObservationResult` per supplied frame" exactly as before
this stage. The other two decisions reuse the existing finalize/drain/fresh-
generation reset shape (`_reset_tracking_for_replay_discontinuity`), tagged
with the reason that produced them. Global replay ordering validation
(`ReplayInput`'s strict `ordered_timestamps` check) is unmodified. Live
wiring (`LiveCameraNodeShadowSession`/`_CaptureLoop`) is unchanged in this
stage -- see "Scope boundary" below.

## Replay metrics

Extends the Stage 6.1 episode-boundary metrics with a separate, non-
overlapping set, all read from already-emitted `TrackUpdate`/`VisitProposal`
facts plus each frame's own `connection_segment_id` -- no new provider
contract field required:

- `reconnect_boundary_count`, `reconnect_bridges_attempted`,
  `reconnect_bridges_continued`, `reconnect_bridges_expired`,
  `reconnect_resets_true_source_change`,
  `reconnect_resets_insufficient_provenance`,
  `reconnect_ambiguous_association_count` -- read directly from
  `FrameDrivenObservationProvider`'s semantic facts.
- `tracks_spanning_multiple_connection_segments`,
  `proposals_spanning_multiple_connection_segments` -- derived by cross-
  referencing each generation's `supporting_frame_ids` against the frames'
  own `connection_segment_id`; proves segment provenance remains visible
  after a successful bridge rather than being silently rewritten away.
- `reconnect_fragmentation_avoided` -- an exact count (every continued bridge
  is one episode a pre-Stage-6.11 tracker would have fragmented at that
  boundary), not an estimate.
- `reconnect_related_incorrect_merge_count` -- the subset of the existing
  `incorrectly_merged` match outcomes whose proposal's generation spans more
  than one connection segment, kept separate from ordinary detector-miss
  fragmentation/merge metrics.

## Historical acceptance

Full-session frame-driven replay (`replay-benchmark --provider
frame-driven-onnx-cuda`) against the unchanged human-reviewed truth, same
tracker settings used for the original Stage 6.10 acceptance run
(`data/models/observation-onnx-cuda/frame-driven-provider-config.json`;
session-01/02 use an otherwise-identical config with `source_nominal_fps=2.0`
matching their own real capture cadence):

| | session-01 | session-02 | session-03 (before → after) | session-04 (before → after) |
| --- | --- | --- | --- | --- |
| Capture-level reconnects | 13 | 53 | 57 | 55 |
| Actionable replay boundaries\* | 13 | 53 | 56 | 55 |
| Session timeline quality | `derived` (legacy) | `derived` (legacy) | `native` | `native` |
| Tracks started | 22 | 18 | 129 → 81 | 78 → 57 |
| Tracks confirmed | 1 | 0 | 67 → 46 | 27 → 28 |
| `provider_reset` terminations | 6 (unchanged) | 4 (unchanged) | 67 → 0 | 29 → 0 |
| `reconnect_bridges_attempted` | 0 | 0 | 0 → 56 | 0 → 55 |
| `reconnect_bridges_continued` | 0 | 0 | 0 → 67 | 0 → 29 |
| `reconnect_bridges_expired` | 0 | 0 | 0 → 0 | 0 → 0 |
| `reconnect_resets_true_source_change` | 13 | 53 | -- → 0 | -- → 0 |
| Tracks spanning >1 connection segment | 0 | 0 | 0 → 50 | 0 → 29 |
| Proposals spanning >1 connection segment | 0 | 0 | 0 → 38 | 0 → 23 |
| Incorrect merges | 0 | 0 | 0 → 0 | 0 → 0 |
| `appearance_recall` / `proposal_precision` | n/a\*\* | n/a\*\* | 0.0 → 0.0\*\* | 0.0 → 0.0\*\* |

\* The replay export's own first frame is itself flagged
`temporal_discontinuity=True` (it followed a reconnect earlier in the full
capture, before high-resolution-frame exclusion trimmed the replay window),
but a boundary check inherently needs a predecessor *within the replay
sequence itself* -- there is nothing before array index 0 to compare
against, so that one leading flag can never become an actionable decision.
This is a correct property of processing an ordered sequence, not a data
loss: session-01/02's own capture-level and actionable counts already
matched exactly, and the one-count gap for session-03/04 is this same,
harmless edge case, not introduced by this stage.

\*\* Structurally unmeasurable through this specific benchmark path
independent of tracker quality: the temporal-review-capture replay export
always emits an empty `ExpectedVisit` list by its own prior, documented
design (see
[temporal-review-capture-contract.md](temporal-review-capture-contract.md)),
so the visit-matcher has nothing to match against regardless of how the
tracker behaves. This was already true, and already disclosed as such, in
the Stage 6.10 campaign's own report -- not a new limitation.

Session-01/02 predate Stage 6.8 and carry only reconstructed
(`derived_session_timeline`) provenance, whose true segment-boundary gap is
unknown and is therefore assigned a fixed, deliberately conservative
`LEGACY_RECONNECT_GAP_UNCERTAINTY_MS = 30_000` (30s) `temporal_uncertainty_ms`
-- far above the default `maximum_temporal_uncertainty_ms` (2000ms) bridge
eligibility bound. Every one of their reconnects therefore still classifies
`reset_source_generation` (`REASON_EXCESSIVE_TEMPORAL_UNCERTAINTY`) and
resets exactly as before this stage: real-data confirmation, not just a
synthetic test, that the new bridging capability activates only where native,
Stage-6.8-quality timeline provenance genuinely supports it.

## Scope boundary

This stage's functional fix is scoped to the shared tracker/provider layer
(`frame_tracker.py`, `frame_driven_provider.py`, `reconnect_continuity.py`)
and the offline replay path that both the deterministic acceptance benchmark
and this exact real-session failure exercise. `CameraNodeAnalysisSource`,
`LiveCameraNodeShadowSession`, and `temporal_capture_cli._CaptureLoop` are
unchanged: the live capture loop still rebuilds its transport source and
restarts the live tracker generation on every reconnect exactly as the
Stage 6.6 fix established, because live per-connection `source_offset_ms`
rebasing (the live-side equivalent of Stage 6.8's session timeline, which is
explicitly computed only *after* a capture session finishes, never
incrementally while live) is a materially separate, larger problem than this
stage's scope. The bridge primitives added here (`is_reconnect_boundary_
signal`, `classify_frame_reconnect_boundary`, `note_reconnect_boundary`) are
provider-neutral and live-path-ready; wiring them into the live orchestration
loop is deliberately left as a distinct, not-yet-scoped follow-up, since the
measured failure and this stage's required acceptance are both about offline
replay of an already-captured session, not live recapture.

A separate, already-documented issue -- session-04's richest late appearance
(`appearance-C`, 457-551s) received zero live high-resolution bursts, all 17
bursts landing in the first ~110 seconds -- is explicitly **not** addressed by
this stage. It is a burst-scheduler recurrence/novelty-floor bookkeeping
question, independent of tracker continuity, and remains the next issue after
this one.

## Authority and limitations

No command in this stage opens the product database, changes the detector,
detector threshold, burst scheduler, saved Ignore regions, evidence-scoring
policy, Camera Node configuration, or monitoring policy, or grants Stage 7
authority. Every module touched remains shadow-only, `creates_truth=false`.
`reconnect_continuity.py` and every module it touches import no product
repository, SQLAlchemy, or `mockingbird.api.main` (structurally enforced by a
hardware-free source-grep test, the same convention every earlier Stage 6.x
pure module uses).
