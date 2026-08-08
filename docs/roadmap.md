# MockingBird Roadmap

This is the current planning authority. It intentionally describes completed
foundations briefly and keeps detailed historical phase narration in
[roadmap-history.md](roadmap-history.md) and the linked design documents.

## Product outcome

MockingBird is a local-first, hardware-agnostic nature observatory that helps
people notice, understand, and remember wildlife around a place.

The current milestone is **Reliable Daily Observatory v1**: Today in Your Yard
makes detector-qualified activity, reviewed discoveries, evidence-backed
moments, Zone/hour context, bounded confirmation work, and observation health
the everyday Dashboard experience. The first bounded field acceptance closed
as a measured failure at detector-qualified animal Visit admission precision:
10 of 23 reviewed Visits were false positives and useful evidence was 56.5%.
Evidence/crop lineage, explicit correction truth, Dashboard/durable-truth
consistency, duplicate and incorrect-merge control, and controlled restart
recovery passed. **Runtime Integrity v1 passed real launcher validation**:
truthful shutdown persistence, loaded-worker inference, stable generation, and
bounded recovery were demonstrated; its 14m27s smoke window was a minor
protocol deviation, not a rerun blocker. The valid July 30 Admission Rejection
Observability cohort passed Animal Visit Admission Precision: 10/10 promoted
Visits were real birds, durable promotion/lineage/useful Visit evidence were
10/10, while primary crop usefulness was 6/10 and recall remains insufficient.

**Temporal Evidence Alignment and Primary Selection v1** is implemented as
conservative temporally proven primary selection. Bounded deterministic review
guidance preserves one primary link and all evidence, distinguishes high-resolution
lineage from subject presence, and never silently rewrites historical selections
or reviewed truth. A delayed high-resolution crop remains retained secondary
evidence unless durable facts affirm subject continuity at capture time. Optimal
multi-frame visual evidence ranking is implemented as Observation Engine v2 Stage 6;
**Observation Engine v2 Stages 1-6** are complete: provider-neutral contracts
wrap the established observer, deterministic shadow-only ordered-frame replay
provides reproducible reports, the optional ONNX Runtime CUDA provider performs
local-model detection with verified no-CPU fallback, and the distinct
`frame-driven-onnx-cuda` provider schedules detection from source time, tracks
intervening analysis frames, retains bounded evidence candidates, and emits
idempotent shadow-only Visit proposals. Stage 3 was activated on the local RTX
4060 Ti with 886 CUDA-executed and zero CPU-executed model nodes. Stage 5 adds one
authenticated bounded Camera Node multipart-JPEG analysis stream, live host
backpressure/generation handling, and immediate one-frame high-resolution burst
evidence. It remains shadow-only with no production proposal authority. Stage 6
adds bounded, deterministic multi-frame evidence scoring described in
[multi-frame-evidence-scoring-contract.md](multi-frame-evidence-scoring-contract.md)
and Snapshot-versus-frame-driven shadow comparison; a two-root native RTX 4060 Ti
replay produced identical semantic fingerprints with CUDA-only model execution.
Stage 6 remains shadow-only with no production proposal authority. Stage 6.1
adds a provider-neutral shadow track episode boundary: genuine detector
support and bounded tracker-support are tracked separately so an episode ends
on positive evidence of discontinuity (elapsed time or explicit
animal-negative detector frames) instead of surviving indefinitely on
tracker-support alone, while brief misses, occlusion, and ordinary cadence
gaps still stay one coherent episode. On the same reviewed-evidence replay
this closes the confirmed episode on principled grounds instead of an
unbounded span, but does not by itself raise appearance recall on that
dataset: the second expected appearance received no positive detector
evidence at all in that image set, which is a detection-recall fact outside
this boundary fix's scope. The first bounded daylight Camera Node hardware
smoke completed and closed as `STAGE_6_DAYLIGHT_INSUFFICIENT_WILDLIFE`:
structural no-write proof, CUDA-only execution, and clean shutdown all
passed, but independent reviewed-crop inspection of every animal-positive
frame and both high-resolution bursts found no genuine wildlife, pointing at
suspected detector false positives on static feeder-scene content rather
than a tracker or evidence-scoring defect. Stage 6.2 adds an offline,
deterministic detector precision/recall calibration benchmark described in
[detector-calibration-benchmark-contract.md](detector-calibration-benchmark-contract.md)
to characterize that finding on a reviewed local cohort before any threshold
or proposal-policy change. Stage 6.3 adds a deterministic, shadow-only
detector-candidate comparison described in
[detector-candidate-comparison-contract.md](detector-candidate-comparison-contract.md)
that scores a replacement candidate against the MDv5 baseline on the
identical reviewed cohort, keeping each model's own threshold grid and an
explicit semantic/non-semantic runtime boundary rather than an opaque
winner score; a two-root real-CUDA rerun produced byte-identical comparison
fingerprints despite genuinely different measured latency between roots,
confirming that boundary holds under real hardware jitter, not only
synthetic fixtures. Its first real evaluation compared the MegaDetector
v1000.0.0-spruce candidate (`spruce`) against MDv5 on the same 70-frame
cohort: at spruce's currently un-tuned starting threshold it scored worse
precision and recall than MDv5, its GPL-3.0 licensing classified
restricted, and the tool's own verdict was `retain_mdv5_baseline` --
`spruce` is not yet suitable for a live shadow trial on this evidence.
Stage 6.4 adds a deterministic, provider-neutral multi-scale inference-
strategy benchmark described in
[multi-scale-detector-benchmark-contract.md](multi-scale-detector-benchmark-contract.md)
to characterize whether tiling recovers small/distant subjects that MDv5's
existing full-frame pass misses. Real CUDA results on the unchanged 70-frame
cohort: adding a bounded uniform tile grid alongside the full-frame pass
raised recall from 0.357 to 0.5 (4 true appearances found only by a tile),
but precision collapsed from 0.270 to 0.035 (149 tile-introduced false
positives) and recurring static false-positive clusters grew from 4 to 66,
including reproducing the same shepherd's-hook hard negative; the one
existing `far`-bucket example remained missed either way. A supplemental,
ignored, local 12-frame small-subject cohort (built from real, previously
unused, already product-reviewed frames -- see the contract doc) showed the
same pattern at smaller scale and surfaced a second confirmed case of a
Visit-level `false_positive` label not describing its own frame's whole-frame
truth. The tool's own verdict on both cohorts was `continue_tiled_strategy_
offline_evaluation` / `insufficient_reviewed_small_subject_data` -- tiling is
not yet suitable for a live shadow trial; it shows genuine recall potential
gated behind an unresolved precision cost that further threshold/NMS work
would need to address before that changes. A representative field comparison
remains a separate, not-yet-completed activation step. Stage 6.5 adds a
deterministic, provider-neutral adaptive motion-proposal strategy described
in
[adaptive-motion-proposal-benchmark-contract.md](adaptive-motion-proposal-benchmark-contract.md)
that derives a small bounded number (at most 3 per frame) of temporal-
change-guided high-resolution windows from ordered source-relative frame
pairs, instead of a fixed uniform tile grid, asking whether selective
proposals can retain some of tiling's recall benefit without its precision
and resource collapse. Because the existing 70-frame cohort carries almost
no real frame sequencing, a separate, ignored, local-only 38-frame reviewed
temporal cohort was built from already-reviewed real local material only
(two real front-yard camera sessions plus the existing daylight-smoke
sequence; no new capture, no download, no changed truth in either existing
cohort). Real CUDA results on both cohorts: `full_frame_plus_motion_
proposals` matched `full_frame` almost exactly -- on the unchanged 70-frame
cohort zero proposal windows ever fired (every raw pixel change on the only
eligible real sequence was noise-sized); on the new temporal cohort exactly
one proposal fired out of 9 temporally eligible real frame pairs, and that
window did not overlap the reviewed animal box in either frame, so it
neither recovered a true positive nor introduced a false positive. Both
cohorts' `motion-proposal-decision` reports reached `insufficient_temporal_
data` reproducibly (byte-identical fingerprints across two real-CUDA roots
outside and inside the checkout) -- there is not yet enough reviewed
temporal evidence to judge the adaptive strategy's recall/precision
tradeoff either way, a materially different and more honest outcome than a
confident negative or positive verdict. This is not yet a live shadow
trial candidate, and no outcome of this stage authorizes production Visit
proposals. Stage 7 controlled proposal-authority migration remains blocked
on measured success across the tiled, adaptive, and field-comparison
evaluations together. Stage 6.6 adds a reviewed temporal capture and
active-learning dataset pipeline described in
[temporal-review-capture-contract.md](temporal-review-capture-contract.md):
`temporal-capture`/`temporal-capture-mark` acquire bounded, triggered live
sequences from the paired Camera Node (reusing Stage 5's session/transport
and Stage 6.5's motion-proposal strategy unchanged -- no new detector
strategy), and `temporal-review-build`/`-validate`/`-export` turn them into
human-reviewed whole-frame/box truth exported into the existing Stage 6.2
calibration, Stage 6.5 motion-proposal, and Stage 2 replay manifest shapes
without inventing new schemas. It creates no product record, truth, or
proposal authority of any kind. A bounded real Camera Node mechanics smoke
found and fixed three genuine live-transport/orchestration defects invisible
to hardware-free tests, all now regression-tested: (1) the Node's
per-connection sequence header restarts at 1 on every fresh HTTP connection
while `provider_generation` stays unchanged, which the existing
single-connection `CameraNodeAnalysisSource` contract correctly rejects --
fixed by rebuilding the source and restarting the provider's live
generation on reconnect, since a batch boundary is the *normal* case on
this transport, not a rare failure; (2) periodic negative sampling was
silently starved because it was keyed on `source_offset_ms`, which that
same reconnect re-zeroes, so elapsed time rarely reached
`periodic_negative_interval_seconds` within one connection's lifetime --
fixed by keying it on the host receive clock instead; (3) operator-marker
correlation could structurally never fire at all: marker discovery only
happens right before fetching new frames, but a marker only ever matches
frames received at-or-before its own timestamp, so a freshly discovered
marker could never match anything still to come -- fixed with a bounded
retroactive rescue buffer that wires up the previously-unused
`adjacent_context_frame_count` bound to re-scan recently-processed,
not-yet-retained frames whenever a new marker appears. With all three fixes
verified together on the real Node (nighttime, no wildlife required or
claimed), a 60-second bounded capture retained 18 frames -- one high-
resolution validation burst, 3 periodic negative samples, 11 frames
rescued by one real operator marker, and 3 post-trigger context frames --
with zero credential/hostname/path leakage into the manifest and an
identical structural no-write proof (product database hash and every
tracked fingerprint unchanged) before and after. All three export targets
correctly reported `sufficient: false` from this single nighttime session
rather than overclaiming. Daylight collection with genuine wildlife
remains a separate, not-yet-run step; this stage authorizes no Stage 7
activity by itself.
Daylight collection completed with two real Camera Node sessions (95 and
393 retained frames, 13 and 53 reconnects) and found that the real Node
resets its per-connection transport sequence and source-relative offset
bookkeeping on every HTTP reconnection -- the normal case on this
transport, roughly every ten seconds, not a rare failure -- while
`provider_generation` stays unchanged. That broke cross-connection
`AppearanceInterval` validation, review/export ordering, and full-session
replay export (only a manually selected, connection-safe sub-window could
be replayed). Stage 6.8 adds a reconnect-safe session timeline described in
[session-timeline-contract.md](session-timeline-contract.md): a
deterministic, monotonic, engineering-only per-frame coordinate, derived
natively from real per-connection identity and host receive time for a
Stage 6.8 capture or reconstructed deterministically from connection-local
sequence numbers for an older manifest (explicitly classified native/
derived/insufficient), while original source-local facts remain unchanged,
separate provenance. Both real Stage 6.7 sessions now upgrade, validate,
and replay end to end with no manually selected sub-window and
byte-identical repeated-export fingerprints; the reconstructed connection-
segment count matched each session's own recorded reconnect count exactly
(14 and 54). It changes no detector, tracker confirmation policy, evidence
scoring, burst policy, or monitoring policy, opens no product database, and
authorizes no Stage 7 activity. Recurring-static-geometry burst
deduplication/cooldown -- session-02 alone produced 123 high-resolution
frames and 379 track generations across 393 retained frames from
recurring static structures repeatedly triggering fresh bursts -- is the
next separate issue, deliberately not addressed by this stage.
Stage 6.9 adds a provider-neutral, bounded, recurrence-aware burst scheduler
described in
[burst-scheduler-contract.md](burst-scheduler-contract.md):
`mockingbird.observation.burst_scheduler` sits between a burst *opportunity*
(a meaningful `TrackUpdate`) and the existing Stage 5 evidence-burst request,
deciding to issue, suppress a duplicate recurrence, defer, reject on a
session/rate budget, or allow an explicit operator/engineering override --
a new track generation alone no longer guarantees a fresh burst. Recurrence
groups use the same bounded IoU/centroid geometry convention as
`RecurringGeometryTracker`/`cluster_static_false_positives`, extended with a
box-size gate; novelty (materially stronger confidence relative to the
group's own historic floor, meaningful motion/change evidence, stronger
temporal support, a genuine time gap, an operator marker, an engineering
request, or a bounded retry) can still issue a fresh burst despite a
recurring match. A deterministic offline replay evaluator
(`burst_scheduler_replay`, `python -m mockingbird burst-schedule-replay`)
reconstructs opportunities from an already-captured Stage 6.6/6.8 manifest
and replays them without opening the product database or rewriting the
source capture. Replayed against the real Stage 6.7 sessions: session-02's
123 historical high-resolution bursts (379 track generations) reduce to 50
proposed bursts (74 explicitly suppressed as recurring static geometry, a
59% reduction) while all 4 reviewed genuine appearances and all 3
reviewer-attributed operator-marked appearances retain burst eligibility,
with zero missed-useful-burst risk; session-01 (a short session the old
system's own `max_high_resolution_frames` cap already truncated at 32) shows
a roughly neutral 32-to-33 change with its 1 reviewed appearance retained
and 44 recurring-geometry suppressions. A bounded 90-second real Camera Node
mechanics smoke on a live daylight feeder scene reproduced the same pattern
live -- 72 real track generations, only 16 real bursts plus one explicitly
labeled engineering-override validation burst -- with an unchanged product
database hash before and after and clean process/GPU shutdown. It changes no
detector, tracker confirmation policy, saved Ignore region, or monitoring
policy, and authorizes no Stage 7 activity.
A representative shadow-operations acceptance campaign (two new full-length
real daylight sessions, session-03 and session-04) closed as a measured
failure specifically at tracker/Visit assembly: full-session frame-driven
replay produced 129 and 78 tracker generations for only 2 and 3 reviewed
genuine appearances, with confirmed episodes cut off by `provider_reset`
almost every time -- this Camera Node reconnects roughly every ten seconds
under real load, and the replay host was treating every reconnect boundary
as an unconditional source reset regardless of whether the underlying
camera/provider identity actually changed. Detector precision/recall,
incorrect-merge safety, burst-volume bounds, and resource stability all
passed or passed with limitation on the same campaign; a separate
burst-placement gap (a session-04 late/sustained appearance received zero
live high-resolution bursts) was also identified. Stage 6.11 adds a
reconnect-safe tracker-continuity decision described in
[reconnect-continuity-contract.md](reconnect-continuity-contract.md):
`mockingbird.observation.reconnect_continuity` distinguishes a benign
transport reconnect -- Stream/provider-generation/analysis-profile
unchanged, a genuine new connection segment, a bounded source-relative gap
and temporal uncertainty -- from a confidently evidenced source-generation
reset or insufficient bridge provenance, using only already-available
Stage 6.8 provenance and never species identity. `ProviderNeutralFrameTracker`
gains a bounded per-track reconnect-bridge budget: active tracks are marked
temporarily lost, pending bounded reacquisition, rather than terminated
outright; reconnect survival by itself never creates detector/tracker-support
evidence, and a track not reacquired within its own bounded window still
terminates. Replayed against the real session-03/04 data with the identical
provider settings and unchanged human-reviewed truth, tracks started dropped
from 129/78 to 81/57, confirmed proposals from 67/27 to 46/28,
`provider_reset` terminations from 67/29 to zero in both, and 50/29 tracks
(38/23 confirmed proposals) now honestly span more than one transport
connection segment (previously always exactly one, by construction), with
zero incorrect merges in either session, before or after. The existing Stage
6.7 session-01/02 sessions predate Stage 6.8 and carry only reconstructed
(`derived_session_timeline`) provenance with a fixed, deliberately
conservative 30-second `temporal_uncertainty_ms` per reconnect boundary; run
through the identical replay unchanged, every reconnect in both correctly
fails the bridge's uncertainty bound and still resets exactly as before this
stage -- real-data confirmation that the new bridging capability activates
only where native, Stage-6.8-quality timeline provenance actually supports
it, not merely because a discontinuity signal is present. `appearance_recall`/`proposal_precision` remain
unmeasurable through this specific benchmark path independent of tracker
quality (the temporal-review-capture replay export always emits an empty
`ExpectedVisit` list by its own existing, documented design -- see
[temporal-review-capture-contract.md](temporal-review-capture-contract.md)
-- so nothing can ever match); the honest evidence of improvement is the
fragmentation, boundary-reason, and cross-segment metrics above. This stage
changes no detector, detector threshold, burst-scheduler, or evidence-scoring
behavior and authorizes no Stage 7 activity; live Camera Node wiring is
unchanged, and the burst-placement gap remains the next separate issue.
Stage 6.11B closes that live-wiring gap: `CameraNodeAnalysisSource` now
distinguishes a benign transport reconnect (new connection segment, unchanged
`provider_generation`) from a genuine source reset -- connection-local
sequence/offset anchors still reset, but the session-relative
`source_offset_ms` the tracker consumes stays continuous, only the
cross-segment step using host receive time (`session_timeline.
native_reconnect_step`, reusing the Stage 6.8 native-timeline constants
rather than a second timeline policy). `FrameDrivenObservationProvider.
observe_live_frame` now runs the identical Stage 6.11 boundary
classification live and calls `note_reconnect_boundary` to bridge the
tracker, instead of `temporal_capture_cli._CaptureLoop` rebuilding the
transport source and restarting the whole live generation on every ordinary
reconnect (the Stage 6.6-era recovery this removes). `LiveCameraNodeShadowSession`
no longer force-clears Stage 6.9 burst-scheduler recurrence state on a
benign reconnect either, closing a related gap where every reconnect used
to reset burst-novelty bookkeeping too. A bounded 180-second real Camera
Node session showed 7 real HTTP reconnects, all correctly classified
benign with zero provider resets, an unchanged product database (hash,
size, and every tracked table row count), and clean shutdown; no genuine
wildlife appeared in that quiet window, so live track-spanning-reconnect
continuity rests on the hardware-free suite and the byte-identical
session-03/04 replay regression rather than a real live track in this
smoke. True resets (provider-generation/camera/stream/profile change,
excessive gap/uncertainty, missing provenance, shutdown boundary) reuse the
unchanged `reconnect_continuity` decision module and still fully reset. It
changes no detector, tracker confirmation policy, burst-scheduler policy,
evidence scoring, or monitoring policy and authorizes no Stage 7 activity;
the burst-placement gap remains the next separate issue.
Stage 6.12 closes that burst-placement gap with late-session evidence-burst
fairness and a bounded novelty reserve, described in
[burst-scheduler-contract.md](burst-scheduler-contract.md). Reconstructing
the complete burst-decision timeline for the real session-04 capture
proved the exact starvation mechanism, correcting Stage 6.10's own
disclosed-as-unverified hypothesis: the Stage 6.9 session-budget gate was
checked before recurrence/novelty evaluation ever ran, so once
early-session activity exhausted the fixed 56-slot budget (at
session-relative 439s) every later opportunity -- all 46 reconstructed for
the session's richest, latest, two-simultaneous-bird reviewed appearance
(`appearance-C`, 457-551s) -- was rejected unconditionally regardless of
novelty; a diagnostic replay with only that gate lifted showed the
existing, unmodified recurrence/novelty logic already correctly recognized
38 of those 46 as materially novel. `burst_scheduler.decide()` now
evaluates recurrence/novelty unconditionally before any budget check
(changing only *when*, never *whether*, a non-novel recurrence is
rejected) and adds one small, bounded, session-relative-time rolling
fairness reserve that only an opportunity already proven not a
suppressible recurrence may draw from once the ordinary or
operator-override budget is exhausted; a recurring, non-novel opportunity
can never consume it, and the existing `max_bursts_per_session`,
`operator_override_reserved_bursts`, `max_concurrent_requests`, and
`max_bursts_per_minute` safety bounds remain exactly as absolute as
before. Replayed against the real session-01-04 sessions: session-01 is
unaffected (never exhausts its ordinary budget), session-02/03 already
retained every reviewed appearance and gain materially better temporal
distribution with recurring-geometry suppression unchanged or higher, and
session-04's `appearance-C` moves from zero issued bursts to
burst-eligible (genuine appearances retained: 2/3 to 3/3) with only a
modest, reserve-attributed issued-burst increase (56 to 64 of 266
reconstructed opportunities) nowhere near the pre-Stage-6.9
123-burst/379-generation volume. It changes no detector, tracker
confirmation policy, reconnect continuity, Camera Node transport, evidence
scoring, saved Ignore region, or monitoring policy, opens no product
database, and authorizes no Stage 7 activity.
Stage 6.13 closes a standalone tooling gap instead of starting new detector/
tracker/burst/reconnect research: Stage 6.7/6.10 acceptance work repeatedly
had to fall back on bounded descriptive analysis because no standalone
evidence-scoring benchmark CLI existed. `python -m mockingbird
evidence-benchmark`/`evidence-comparison` (see
[evidence-benchmark-contract.md](evidence-benchmark-contract.md)) evaluates a
reviewed evidence manifest -- derived directly from an existing Stage 6.6/6.8
review packet with no hand-copying -- by calling the existing Stage 6
evidence scorer unchanged, and compares two such reports metric-by-metric
without an aggregate winner score. Real evaluation against the four
historical reviewed sessions used across Stages 6.7-6.12 found useful
identification evidence only among a minority of episodes (12/41, 6/146,
24/114, 31/129 episodes ever selected an identification candidate at all)
and zero episodes across all four sessions where a high-resolution burst
frame was the selected identification evidence rather than an ordinary
tracked frame -- alongside honestly disclosed reconstruction limitations
(no independently recorded temporal alignment or reviewer-preferred-candidate
truth in this historical corpus). It opens no product database and
authorizes no Stage 7 activity; the next representative shadow-acceptance
rerun can regenerate this artifact directly instead of hand-built descriptive
analysis, but Stage 7 remains blocked pending that rerun.
Stage 6.13's own real evaluation disclosed exactly one remaining integration
gap: a replay produced through `replay-benchmark` assigns each frame a
replay-derived identity distinct from the original reviewed `frame_id`, so
reviewed truth could not link to a replay-sourced `EvidenceCandidate` even
when both referred to the same captured frame. Stage 6.14 closes that
lineage gap, described in
[reviewed-replay-lineage-contract.md](reviewed-replay-lineage-contract.md):
the original reviewed frame identity now propagates, as optional additive
provenance alongside every existing replay-local identity, from
`temporal_annotation.build_replay_export` through `FramePacket`,
`DetectionObservation`, `TrackUpdate`, `EvidenceCandidate`, and
`VisitProposal`, and `evidence_benchmark`'s join now uses that explicit
identity -- never coincidental equality, filename, ordering, timestamp, or
geometry -- refusing rather than guessing on a hash mismatch or unknown
source reference. Real evaluation against session-04's reviewed packet and a
freshly produced real-CUDA replay, run from two independent absolute
filesystem roots, reproduced byte-identical semantic fingerprints at every
layer and the exact pre-existing Stage 6.11/6.12 tracker counts (57 started,
28 confirmed); 25 of 28 replay-sourced episodes' selected evidence joined
directly to reviewed truth, moving `useful_identification_rate` from a
manifest-only 0.143 to a replay-informed 0.176 and
`episodes_with_identification_candidate` from 31 to 56, while
`selected_identification_correctness`/`selected_context_correctness`
honestly remain `not_evaluated` -- this corpus never recorded a reviewer's
preferred-candidate truth, and lineage makes a join possible without
inventing that judgment. Session-01/02 spot-checks confirmed the mechanism
generalizes (100% detection/evidence-candidate lineage propagation in both;
session-02 reproduced zero confirmed proposals byte-identical to its own
existing Stage 6.11 record, an unrelated pre-existing fact). A structural
no-write proof before and after the whole campaign found an unchanged
SQLite hash/size and every tracked table row count. It changes no detector,
tracker, reconnect, burst-scheduler, or evidence-scoring behavior and
authorizes no Stage 7 activity; the representative Stage 6.10 rerun remains
separate and not yet run, now unblocked at the tooling level.
Stage 6.15 fixes a live burst-storm defect the first representative-acceptance
resumption (session-01, 31 live scheduler-driven high-resolution bursts in
~133s) exposed: `BurstScheduler._evaluate_recurrence`'s `stronger_temporal_
support` novelty signal compared each opportunity's monotonic per-generation
`detector_confirmation_count + tracker_support_count` against a recurrence
group's historic floor, so a recurring static object re-detected as a fresh
track generation kept re-pinning the floor near zero and read as "stronger
support" almost immediately on every rebirth; `_RecurrenceGroup` now tracks a
`support_high_water` (maximum) compared via a frozen per-(generation,
recurrence-group) baseline, and `burst_scheduler_replay.reconstruct_
opportunities` derives a real per-generation occurrence count instead of the
fixed constants it had silently used to hide the same defect offline. It
changes no detector, tracker-confirmation policy, reconnect continuity, or
monitoring policy, opens no product database, and authorizes no Stage 7
activity.
The representative-acceptance resumption itself (attempt-2/attempt-3, real
Camera Node, real CUDA, no code changes) confirmed the Stage 6.11 reconnect
fix directly (zero `provider_reset`, 40-41 of 60-63 boundaries bridged) and
found a new, independent root cause: attempt-3 directly confirmed one
genuine ~5-minute feeder-bird visit (three real 4624x3472 bursts spanning
the visit), but full-session replay still fragmented it into approximately
37 confirmed track generations purely because natural detector-confidence
dips exceeded the tracker's ordinary tight bound more often than a sustained
multi-minute visit's own real cadence tolerates -- a mechanism independent
of reconnects. Stage 6.16 adds a bounded strong/weak/tracker-only evidence
hierarchy described in
[sustained-visit-continuity-contract.md](sustained-visit-continuity-contract.md):
a matched detection below `strong_detection_threshold` but at or above a new,
reused-not-invented `weak_detector_support_floor` refreshes an already-
confirmed track's continuity without counting as a new strong confirmation,
and a confirmed track gets a widened per-frame gap tolerance (reusing the
existing `maximum_unsupported_detector_ms` budget) once graduated by any
genuinely strong hit, or for a bounded, one-time provisional window from its
own start if it never shows one -- `minimum_detector_confirmations` itself
keeps its exact pre-existing, unconditional meaning, since real attempt-3
evidence proved a genuinely continuous subject's own confirming pair is
routinely both individually weak, and gating confirmation on strength would
have hurt recall, not just continuity. Raising `maximum_unsupported_
detector_ms` itself was considered and rejected: the existing ghost-tracker-
support incorrect-merge regression test proved a materially larger value
measurably weakens that already-fixed protection. Replayed against the real
attempt-2/attempt-3 detections (a hardware-free recorded-detection-playback
harness, since this environment has no CUDA hardware, isolating the tracker
change against the unchanged, already-real-CUDA-verified detector output) and
the historical session-01-04 sessions: attempt-3 tracks started fell 63 to
47, confirmed 37 to 25, and generations geometrically relevant to the
reviewed appearance fell 47 to 36 (29 to 20 confirmed), with 25 confidence-
dip bridges and zero incorrect merges or duplicates; `appearance_recall`/
`proposal_precision` measure `0.0` before and after, proven to be the exact
same structural limitation Stage 6.11 already disclosed (attempt-3's own
export carries an empty `ExpectedVisit` list despite two real reviewed
appearances, so the visit-level matcher has nothing to match against
independent of tracker quality) rather than a sign of no improvement.
attempt-2 (real, hard-negative, no genuine wildlife) stayed safe: every
confirmed generation's `strong_detector_support_frame_count` was zero
(confirming its real clutter, which never reached the deployed 0.7 threshold
across its whole session, never left the bounded provisional tier),
confirmed-proposal count fell 38 to 28, and `proposal_precision` stayed
exactly `0.0` with zero incorrect merges. Session-01/02/03/04 fragmentation
improved or held (session-03: 81 to 61 started, 46 to 33 confirmed;
session-04: 57 to 32 started, 28 to 17 confirmed; session-01/02 unchanged,
too small to exercise the new logic) with reconnect-fix facts identical
before and after in every case. It changes no detector, detector threshold,
detector calibration, burst scheduler, reconnect continuity policy, Camera
Node transport, evidence scorer, session timeline, Privacy/Ignore
configuration, or monitoring policy, opens no product database (structural
SHA-256/size/table-count proof unchanged), and authorizes no Stage 7
activity by itself; a real-hardware repeat of the representative-acceptance
campaign, this time able to measure `appearance_recall` through a path that
does not structurally zero it out, remains the next required step before
Stage 7 can be reconsidered.
Stage 6.17 closes the measurement gap itself, independent of that hardware
rerun: temporal-review replay export's `visits` list was always empty, so
Visit-level metrics were structurally `0.0`/meaningless no matter how good
the tracker was. `temporal_annotation._expected_visits_from_appearances`
now deterministically converts each eligible, explicitly reviewed
`AppearanceInterval` into exactly one `replay.ExpectedVisit` -- never an
invented multi-appearance grouping, never inferred from detector/tracker/
product output or species identity -- excluding (and always honestly
reporting) an interval that is ambiguous, unscorable, missing session-
timeline provenance, structurally invalid, or an unresolved same-vs-
separate overlap with another appearance; see
[reviewed-visit-truth-contract.md](reviewed-visit-truth-contract.md). The
existing matcher and every matching threshold are unchanged. Re-exported and
re-scored (hardware-free, reusing each session's own already-real-CUDA-
verified proposals) against attempt-3, attempt-2, and sessions 03-04:
attempt-3's two reviewed appearances (the ~5-minute feeder-bird visit and a
separate instantaneous ground sighting) finally produce a real
`appearance_recall` of 0.5 (unchanged before/after -- the ground sighting,
a single retained frame with no repeat detection nearby, was never
confirmed into a proposal either side) and a real fragmentation count that
dropped 28 to 19 (32% fewer proposals fragmenting the one reviewed feeder-
bird Visit, `proposal_precision` 0.027 to 0.040) -- the first genuine,
non-structurally-zero evidence that Stage 6.16 improved Visit-level
outcomes, not just track counts. attempt-2 (hard negative) correctly
produced zero `ExpectedVisit`s before and after (review found no genuine
wildlife), so its unchanged 38-to-28 proposal count counts entirely as
false proposals both times, `proposal_precision` staying honestly `0.0`.
Session-03 (recall 1.0 unchanged, fragmentation 2 unchanged, precision
0.043 to 0.061) and session-04 (recall 1.0 unchanged, fragmentation 18 to
11, precision 0.107 to 0.176) both fully recalled every reviewed appearance
both before and after; session-04 also surfaced one new incorrectly-merged
proposal after Stage 6.16's widened gap tolerance that did not exist
before, honestly disclosed rather than hidden. It changes no detector,
tracker, reconnect, burst, or evidence-scoring behavior, opens no product
database, and authorizes no Stage 7 activity; representative hardware
acceptance remains the next required step.
This remains a contained observation-
subsystem strangler migration: keep the MockingBird product; replace its
observation engine through a modular migration.
`SnapshotObservationProvider` names the current timer-driven path and remains a
compatibility, fallback, and deterministic comparison provider rather than the
long-term golden path.

Observation Engine v2 sequence: (1) provider-neutral frame/detection/track/
evidence/Visit-proposal capability contracts; (2) deterministic recorded-media
replay benchmarks; (3) ONNX Runtime CUDA shadow provider with verified local RTX 4060 Ti
activation and no durable writes; (4) replay-first frame-driven detector/tracker
shadow pipeline; (5) provider-neutral Camera
Node analysis-stream/evidence-burst capabilities; (6) multi-frame evidence
scoring and old/new shadow comparison; (7) controlled proposal-authority
migration only after measured success; and (8) multi-frame interpretation after
Visit/evidence reliability. CPU remains functional and vendor-neutral through
the Snapshot compatibility path; the CUDA replay provider is optional, and
TensorRT remains only a later optimization. Privacy/Ignore masking, lineage,
side-effect-free reads, bounded recovery, and correction-as-truth are preserved.

The user-facing loop is **Observe → Discover → Understand → Confirm → Remember
→ Improve**. The internal evidence/truth architecture remains unchanged:
detectors and SpeciesSuggestions are evidence, while explicit correction is the
only reviewed truth used for confirmed species, Bird Log, exports, and history.

## WSL activation checkpoint

The active development checkout is now WSL-native at
`/home/zkelder/projects/mockingbird-active`. The cross-install restore completed
successfully, and the locally configured Windows `ffmpeg.exe`, native
DirectShow controls, fresh live frames, and one daylight 3840 x 2160 capture
were verified from WSL. Driver-managed exposure values remain outside
MockingBird and are neither readable nor persisted. Representative field-truth
collection is next; Playwright Chromium remains optional local WSL environment
setup rather than a product blocker.


## Completed foundations

- Phases 0-6 established product doctrine, the universal product model, the
  stream-first UI, local/demo media, the detection evidence model, the bird
  feeder review vertical, and broader outdoor concepts.
- Phases 7-9 established optional evidence-only model adapters, zone-aware
  motion and MotionEvidence, species suggestions, reviewed classifier
  readiness, and local export/training boundaries.
- Phases 10-16 established product-level playback/provider contracts,
  explicit external URL and folder media flows, generic webhook metadata
  evidence, retention boundaries, MVP onboarding, and disabled worker metadata.
- Phases 17-18 improved evidence review and classifier-readiness drill-down.
- Phases 19-22 added explicit in-memory camera monitoring, browser/RTSP/local
  USB playback, backend-owned live camera sessions, Zone overlays, best-frame
  evidence, and optional identification assistance.
- Phase 23 began real feeder-camera validation, camera lifecycle cleanup,
  bounded diagnostics, field calibration, and optional local MDv5 proposal
  verification.
- Phases 24A-24D added the single local runtime, verified database-and-media
  backup/restore, durable lifecycle design, and inert default-off monitoring
  policy/runtime state.
- Camera Health and Guided Camera Editing now expose saved operational state,
  safe in-place compatible camera configuration, redacted change previews, and
  bounded revision history without changing the evidence/review truth boundary.
- The optional MockingBird Camera Node is a paired local-LAN snapshot adapter
  beneath the same Source/Stream/Zone/monitoring/review loop. It remains
  default-off, synthetic-provider-tested, no-cloud, no-discovery, and no-truth.

See [roadmap-history.md](roadmap-history.md) for the concise phase record.

## Subsequent separate priority: real visual species identification

Goal: deliver the shortest complete identification loop:

saved activity -> best frame -> animal/activity crop -> real ranked species
suggestions -> Review Queue -> correction -> Bird Log

The first saved-media evaluation completed on July 16, 2026. SpeciesNet did not
clear the field-usefulness gate on the current feeder corpus. BioCLIP 2 was
better at returning bird candidates, but species accuracy remains unmeasured
because the local records have coarse bird/false-positive truth rather than
species-level corrections. Several visually questionable predictions also had
high scores, so no production runtime is selected yet.

The active gate is now representative species-level correction truth plus
substantially more non-bird activity examples from identification-quality
captures. The eventual runtime must stay optional, local, unavailable-safe, and
evidence-only.

### Step A - saved-media classifier evaluation (complete)

The completed evaluation recorded:

- SpeciesNet crop/full-frame and combined-pipeline output on saved field media
- BioCLIP 2 rankings against the same activity/detection crops
- cold-start, cached, and per-image CPU inference cost
- local runtime, dependency, model-size, and no-download behavior
- six exposure-cleanup variants against an unchanged candidate bank

SpeciesNet recognized bird as top-1 on only one of eight reviewed bird crops
and produced no species-specific top-1 result. BioCLIP 2 returned an avian
species first for the reviewed/candidate bird crops, but that result is biased
by a bird-heavy candidate bank and is not species accuracy. Automatic
post-capture exposure filters did not consistently improve either model and
cannot recover clipped image detail.

Evaluation media, model files, caches, and reports stay in ignored local paths.
Zones may provide context but must not define the crop. Use detector boxes when
credible and measured activity bounds as the fallback.

### Step B - representative species truth gate

Use the existing Review Queue correction path to build one frozen,
representative field set from identification-quality best frames and activity
crops. It must include explicit species corrections, ambiguous/unknown birds,
and enough animal/person/vehicle/blank activity to measure false suggestions
and abstention.

An explicitly triggered, one-item-at-a-time BioCLIP shadow may run during this
truth-building step. It can create ranked, candidate-relative, uncalibrated
`SpeciesSuggestion` evidence to make correction faster, but its availability
does not select the model, establish accuracy, enable automation, or create
truth. The original frame and the actual detector/activity/full-frame input
region remain visible as provenance.

The first end-to-end shadow smoke completed on July 16, 2026: one existing
saved Review Queue item used a credible animal-detection crop, returned a
plausible species as rank 1, and created one pending `SpeciesSuggestion`.
ReviewLabel, DetectionRun, DetectionProposal, export, camera, and monitoring
state remained unchanged. This validates the product boundary, not model
accuracy; the representative correction gate below still controls selection.

Phase 26A1 now provides a hard read-only field-truth evaluator over stored
BioCLIP rankings and final exact-target ReviewLabels. The current local
checkpoint has one eligible example and fifteen reviewed targets without
BioCLIP evidence, so its result is descriptive only and cannot justify model
selection. Top-1, stored top-3, crop, and reproducibility variants are available;
Phase 26A2 now durably records each future user-triggered manual attempt,
including complete candidate membership, duration, exact crop, model/runtime
provenance, successful suggestion linkage, and honest no-result, timeout,
failure, unsupported, or cancelled outcomes. Historical attempts were not
invented or backfilled. The next step is collecting the representative
30-100-example field-truth set through the existing correction flow.

Candidate labels must be genuinely local and seasonal, with explicit unknown
and non-bird choices. Rerun the leading candidate against held-out corrections
and record top-1, top-3, coverage, abstention, high-confidence mistakes, and
non-bird specificity. This uses the existing product correction flow; it does
not require a labeling or readiness page.

### Step C - bounded Review Queue shadow integration

The evaluation-only shadow from Step B processes one media-backed Visit at a
time. Phase 26B now adds a default-off post-activity assist that schedules one
bounded BioCLIP attempt for a newly completed needs-review Visit, never retries
an existing attempt, and never blocks the monitor on model execution. Manual
identification remains available. Both paths create ranked `SpeciesSuggestion`
evidence only. Review Queue shows the best
suggestion, alternatives, uncalibrated score, provenance, crop, and original
frame through the existing correction flow. Accepting or changing a suggestion
creates truth only when the user submits the correction.

No new analyzer administration page, readiness surface, or parallel species
workflow is required. Failures leave the Visit unidentified and reviewable.

### Step D - automatic post-activity inference

After saved-media accuracy and runtime behavior are acceptable, run the detector
and selected classifier automatically for each eligible completed activity.
Execution must be bounded, optional, observable, safely stoppable, and unable to
create reviewed truth. It enriches the existing review candidate; it does not
become a second event trigger or bypass Review Queue.

### Visual identification exit criteria

- a real local species model produces ranked suggestions on saved field media
- top-1/top-3, abstention, non-bird specificity, and inference cost are recorded
  against species-level reviewed labels
- unusably clipped captures are reported before their predictions are treated
  as meaningful evaluation evidence
- activity/animal-centered crops work without requiring Zones
- Review Queue exposes suggestions through the existing correction interaction
- corrections feed Bird Log and provide evaluation truth
- automatic post-activity inference fails safely without blocking capture or
  review

### Product work freeze

Until these criteria pass, do not add new admin panels, readiness screens,
provider abstractions, diagnostics surfaces, training scaffolding, or broad
refactors. Targeted extraction is allowed only where the identification path
touches an oversized component and the change delivers or protects this
vertical slice. Audio follows the working visual path; it does not delay it.

## Supporting engineering gate: Phase 24 hardening

This gate continues only where it directly reduces risk for the identification
vertical or later unattended capture. It is not the active feature backlog.
Durable supervisor work still requires the applicable lifecycle gates before
activation.

This gate improves the complete Cameras/Streams -> Zones -> monitoring -> Review
Queue -> correction -> Bird Log -> Exports flow. It does not change the product
truth boundary.

### Gate A - feedback and reproducibility

Status:

- Documentation authority, conditional routing, and repository-wide validation
  tiers are defined in [development-workflow.md](development-workflow.md).
- A hardware-free browser check covers correction -> Bird Log -> reviewed-only
  export behavior using isolated local data.
- Additional automation, formatting/type policy, and dependency reproducibility
  work is added only when it protects the active identification vertical or a
  release gate; it is not the next product feature.

Exit criteria:

- A clean checkout has one documented command or automated job for each
  non-hardware validation tier.
- Backend tests, frontend type-check/build, migration/backup compatibility, and
  the critical smoke flow run automatically at the appropriate tier.
- Hardware, models, cameras, generated media, and secrets are not required for
  normal automated checks.

### Gate B - browser and API contract safety net

Add a small hardware-free browser suite for the primary path: create/configure
a camera, reach Stream Detail, manage a Zone, exercise a deterministic
monitoring/review candidate, submit correction truth, verify Bird Log, and
verify reviewed-only export behavior.

Generate frontend API types from Pydantic/OpenAPI or enforce an automated parity
check so backend/frontend contract drift fails validation.

### Gate C - targeted architecture seams

Avoid a broad rewrite. When Phase 24E touches lifecycle behavior, extract the
relevant camera/session/supervisor routes and repository operations into focused
domain services. When primary browser flow work touches Streams or Stream
Detail, extract focused components/hooks and scoped styles.

New work should stop increasing the largest API, repository, page, and global
style concentration points. Refactoring tasks must preserve behavior, include
focused regression coverage, and avoid unrelated product features.

### Gate D - measurable field benchmark

Build an ignored/local, frozen set of representative feeder observations and
record:

- bird recall
- nuisance candidates per camera-hour
- candidate acceptance rate
- median review time
- stale/dropped frames
- CPU use and storage growth per camera-hour

Threshold, crop, focus, or analyzer comparisons should use the same benchmark.
The full source frame remains evidence context and explicit user correction
remains truth. Benchmark media and reports are never committed.

### Gate E - resilience, privacy, security, and upgrades

Before expanding live-video continuity beyond the current bounded local
supervisor, validate camera/FFmpeg loss, hung processes, disk-full and
database-locked behavior, restart during media writes, clock changes, and
backup/restore while policy is armed.

Decide and test:

- loopback-only versus LAN exposure and authentication expectations
- browser-origin/localhost request protection
- secret-file permissions and redaction
- whether Privacy Zones suppress only analysis or also persisted full-frame
  media
- every supported schema and backup upgrade path
- startup, idle-memory, per-Stream CPU, frame-freshness, database-growth, and
  media-growth budgets

### Gate F - documentation maintenance

Keep current system contracts, current roadmap, architectural decisions, and
completed history separate. Link applicable guardrails instead of copying them
into every task/design document. Product doctrine, privacy/lifecycle safety,
and the evidence-versus-truth boundary remain prominent and canonical.

### Engineering-gate sequencing

- The representative truth gate and later bounded Review Queue shadow
  integration do not wait for the durable supervisor.
- Automatic post-activity inference requires focused failure, runtime-bound,
  storage, privacy, and stop-behavior tests for that inference path.
- Phase 24E's bounded, fake-adapter-tested supervisor is implemented. Gate A
  and the relevant Gate C seam continue to govern future expansion.
- Scoped explicit live-video continuity now uses only existing backend-owned
  local session paths. Gate B and the relevant Gate E
  failure/privacy/security/upgrade decisions are required before widening
  supported adapters, automation, or field use.
- Phase 25 field-loop acceptance requires Gate D, long-run/soak results, and
  declared performance/storage budgets.
- New providers and unrelated model pathways do not take priority. The visual
  species adapter above is the explicitly scoped core product milestone.

## Deferred supporting work: Phase 24E-24G durable live continuity

### Phase 24E - supervisor foundation (implemented)

Add a bounded `DurableStreamSupervisor` foundation with fake-adapter lifecycle,
app-instance/checkpoint reconciliation, one-Stream leases, deterministic
backoff, and stop ordering.

The supervisor is app-owned and starts after persistence initialization. Its
fake-adapter lifecycle coverage exercises one-Stream leases, bounded recovery,
capacity waiting, and clean shutdown. Status reads stay side-effect free.

### Phase 24F - explicit live-video continuity (implemented, scoped)

Explicit Stream-scoped enabling is available for supported backend-owned
RTSP/local USB/Windows DirectShow live video. It reuses the existing local
camera/session path, waits for a healthy frame before evaluation, and remains
bounded to the local application process.

Persisted desired policy and actual runtime state remain separate. Every Stream
defaults off; backup, restore, migration, emergency stop, Source archive, Stop
camera, and shutdown holds prevent surprise restart. External snapshot polling
and future audio are outside this lifecycle.

### Phase 24G - bounded idempotent review handoff

Allow explicitly enabled durable monitoring to create or reuse at most one
needs-review candidate per completed activity session under storage, quiet
window, duplicate, Privacy Zone, and Ignore Zone limits.

It may create evidence and unreviewed Event/Visit context only. It never creates
ReviewLabels, marks Visits reviewed, runs identification automatically, writes
Bird Log truth, or creates analytics/export truth.

The separate optional visual-identification enrichment in Step C may run after
an eligible candidate exists. It is not part of handoff, event triggering, or
truth creation.

Design authority:

- [single-app-runtime-recovery-design.md](single-app-runtime-recovery-design.md)
- [local-backup-recovery-design.md](local-backup-recovery-design.md)
- [durable-camera-monitor-lifecycle-design.md](durable-camera-monitor-lifecycle-design.md)

## Phase 25 - dependable field loop

Harden restart recovery, bounded storage, retention controls, camera/source
health, long-run observability, support-safe diagnostics, and representative
feeder validation. Acceptance uses the frozen field benchmark and declared
performance/storage budgets from the engineering gate.

## Phase 26 - identification evidence

- Phase 26A is complete: the optional local BioCLIP adapter and durable manual
  attempt instrumentation create suggestion evidence only.
- Phase 26B is complete: a default-off automatic post-activity assist schedules
  exactly one bounded BioCLIP attempt for each newly completed eligible Visit.
  Existing attempts are never retried; explicit correction remains truth.
- Phase 26C: integrate optional local bird-audio evidence through a separately
  designed consent, microphone, privacy, retention, and dependency boundary.
- Phase 26D: combine visual, audio, time, Zone, and reviewed local history into
  ranked suggestions. Representative field-truth collection remains required
  before claiming identification accuracy.

## Phase 27 - release acceptance

Finish packaging, first-run setup, update/recovery policy, accessibility,
performance, dependency reproducibility, upgrade support, and release
acceptance for a dependable local product.

## Cross-cutting roadmap invariants

- Source adapters remain underneath Sources, Streams, Zones, Events, Visits,
  review/correction, analytics, and exports.
- MediaAssets, MotionEvidence, DetectionProposals, SpeciesSuggestions, and
  external labels remain evidence/context until explicit correction.
- Read/status/preview/dry-run routes are side-effect free. Writes are explicit,
  scoped, bounded, and tested.
- Privacy and Ignore Zones, local storage, retention, backups, and safe restart
  behavior are first-class constraints.
- Workers and durable monitoring default off, are observable and safely
  stoppable, and cannot create reviewed truth.
- Model runtimes, training dependencies, generated datasets, captured media,
  benchmark artifacts, and caches require explicit scope and ignored local
  paths.
- Each implementation task uses the task packet and validation tiers in
  [development-workflow.md](development-workflow.md).

## Roadmap non-goals

- No one-shot repository rewrite or coverage-percentage target.
- No cloud dependency or telemetry requirement for the core product.
- No new administration page merely for lifecycle or engineering controls.
- No provider, audio, or unrelated automation expansion ahead of the active
  visual identification milestone without explicit evidence and scope.
