# MockingBird Architecture

MockingBird is a local-first outdoor event platform organized around a shared
product model. Source adapters and optional analyzers feed evidence into that
model; they do not redefine the product.

## Product and truth flow

```text
Source -> Stream -> Zone-aware activity -> evidence -> Event/Visit review
       -> explicit correction -> Bird Log / analytics / exports / datasets
```

Evidence includes MediaAssets, MotionEvidence, DetectionProposals,
SpeciesSuggestions, best-frame context, and untrusted external metadata.
Evidence can be pending, ignored, promoted, accepted, rejected, or superseded
without becoming dataset truth.

ReviewLabel correction is the dataset-grade truth boundary. Reviewed-only Bird
Log, analytics, classifier readiness, and exports derive from corrections, not
raw model/provider output.

## Conceptual layers

### App experience

- Cameras/Sources and Streams
- Live view and Zone editing
- monitoring and evidence handoff
- Review Queue, Event Detail, and Visit Detail
- Bird Log, Analytics, Dataset Exports, and Classifier Readiness
- Local Data backup/recovery and Storage & Retention

The primary navigation flow is Cameras/Streams -> Review Queue -> Bird Log ->
Exports. Advanced evidence, provider diagnostics, and optional analyzers support
that flow without becoming the product center. Product Mode makes current
detector-qualified animal Visits the compact default review task while keeping
legacy activity and developer provenance secondary; see
[review-product-mode-contract.md](review-product-mode-contract.md).

### Product API

The FastAPI layer exposes product contracts for:

- Sources, provider configuration, setup review, and connection status
- Streams, playback status, live camera sessions, and lifecycle status
- Zones
- MediaAssets and MotionEvidence
- Events, Visits, DetectionProposals, and SpeciesSuggestions
- review/correction, Bird Log, analytics, and exports
- retention, schema readiness, and backup/recovery

Read/status/preview/dry-run routes are side-effect free unless their contract
explicitly defines a bounded write. Unknown product ids return product-level
errors rather than leaking adapter behavior.

### Product repository and storage

SQLAlchemy models persist product metadata in local SQLite. The product
repository owns product-level reads/writes and must preserve Source/Stream/Zone
relationships, evidence provenance, correction truth, and export context.

Schema compatibility is explicit and versioned. Startup checks integrity and
schema version. Known migrations are forward-only and tested; unsupported newer
or unmigrated older schemas are rejected safely.

Managed media lives under configured local roots. Database and managed media
form one backup graph: backup/restore verifies paths, sizes, hashes, SQLite
integrity, and schema compatibility before mutation. Restore creates a verified
pre-restore safety backup and can roll database and media back together.

Storage & Retention remains local and policy-led: defaults are disabled, server
previews select only validated eligible assets, and confirmed cleanup moves files
to managed recovery before unlinking eligible evidence associations. Primary,
unresolved, reviewed wildlife, export-referenced, incomplete, symlinked, and
otherwise ambiguous media fails closed. Automatic maintenance is bounded to one
app-owned worker, uses a fresh policy pass rather than a browser preview, and
shares its maintenance window with backup and restore.

### Local intelligence

- deterministic zone-aware motion scoring
- frame sampling and bounded activity sessionization
- Privacy/Ignore suppression
- one-best-frame evidence selection
- optional DetectionProposal or SpeciesSuggestion adapters
- review prioritization and explicit correction

Motion and analyzer output are evidence. Optional analyzers are lazy, local,
user-configured, and unavailable-safe. No model file or runtime download is
required for the core product.

### Observation Engine v2 boundary

Stage 1 is implemented: provider-neutral evidence contracts, an explicit active-provider registry, and a read-only health/capability surface wrap the established timer-driven observer as `SnapshotObservationProvider`. The compatibility provider delegates to the existing bounded snapshot monitor; it creates no parallel runtime, detector, or truth path.
Stage 2 adds the deterministic, shadow-only ordered-frame replay host described in
[observation-replay-benchmark-contract.md](observation-replay-benchmark-contract.md).
It performs no durable product or truth writes. Stage 3 adds the optional
`onnx-cuda` replay provider described in
[onnx-cuda-shadow-provider-contract.md](onnx-cuda-shadow-provider-contract.md).
It performs explicit local-model GPU detection only: no live video, tracking,
evidence selection, Visit proposals, or proposal authority. Stage 4 adds the
distinct replay-first `frame-driven-onnx-cuda` provider described in
[frame-driven-shadow-provider-contract.md](frame-driven-shadow-provider-contract.md).
It schedules that detector from source-relative timestamps, updates a provider-
neutral bounded tracker on each analysis frame, retains portable evidence
candidates, and emits idempotent shadow-only Visit proposals. Stage 5 adds the
paired, authenticated, bounded multipart-JPEG analysis stream and one-frame
high-resolution evidence burst described in
[camera-node-live-shadow-contract.md](camera-node-live-shadow-contract.md). The PC
source validates sequence, generation, timing, dimensions, and hashes; applies
Privacy/Ignore masking before inference; coalesces to newest work under bounded
backpressure; and attaches only generation-correct temporary burst evidence. CUDA
and tracker runtime types remain behind provider boundaries. The live path has no
product repository dependency or production proposal authority; product records
still contain only provider-neutral evidence and correction-derived truth. Stage 6
adds bounded, deterministic multi-frame evidence scoring and old/new shadow
comparison described in
[multi-frame-evidence-scoring-contract.md](multi-frame-evidence-scoring-contract.md).
For each shadow track episode it ranks retained evidence candidates on
provider-neutral signals only, choosing a best identification candidate and a best
context candidate separately, a bounded alternate set, and an honest
no-useful-evidence state when nothing is eligible; it never uses species identity
or species-model inference. Snapshot-versus-frame-driven replay comparison
classifies each metric as equivalent, better for one side, insufficient truth, or
unsupported for one provider rather than producing an aggregate score. Stage 6
remains shadow-only with no production proposal authority. Stage 6.1 clarifies
the provider-neutral episode boundary inside the frame-driven tracker: a
generation's own genuine detector support and bounded tracker-support are
tracked separately, so an episode closes on positive evidence of
discontinuity rather than surviving indefinitely on tracker-support alone,
while brief misses, occlusion, and ordinary cadence gaps remain one coherent
episode. See
[frame-driven-shadow-provider-contract.md](frame-driven-shadow-provider-contract.md)
for the bounded decision inputs, settings, and stable reason codes. Stage 6.2
adds an offline, deterministic detector precision/recall calibration
benchmark described in
[detector-calibration-benchmark-contract.md](detector-calibration-benchmark-contract.md).
It scores the existing `onnx-cuda` provider's already-decoded observations
against a reviewed local image cohort across a bounded score-threshold grid
without re-running inference per threshold, clusters recurring static
false-positive geometry, simulates bounded temporal confirmation policies
over recorded detections only, and classifies candidate follow-up actions
with no aggregate winner score. It opens no product database, changes no
runtime threshold, Ignore region, or tracker configuration, and grants no
production authority. Stage 6.3 adds a deterministic, shadow-only
detector-candidate comparison described in
[detector-candidate-comparison-contract.md](detector-candidate-comparison-contract.md).
It compares one or more replacement candidates against the MDv5 baseline
using already-produced Stage 6.2 reports scored on the identical reviewed
cohort, preserving each model's own threshold grid, score distribution, and
operating-point interpretation rather than comparing raw confidence values
across models. Runtime and resource facts -- including the
acceptable/degraded/unacceptable classification derived from them -- are
reported only in a separate non-semantic section and never influence the
comparison's semantic fingerprint or its deterministic recommendation, which
a two-root real-CUDA run confirmed by reproducing byte-identical comparison
fingerprints despite genuinely different measured latency between roots. It
opens no product database and grants no production authority; a
`candidate_ready_for_live_shadow_trial` classification characterizes
accuracy, static-scene, temporal, and licensing evidence only and does not
by itself authorize a live shadow trial. Stage 6.4 adds a deterministic,
provider-neutral multi-scale inference-window benchmark described in
[multi-scale-detector-benchmark-contract.md](multi-scale-detector-benchmark-contract.md).
It characterizes whether a bounded uniform-tile strategy alongside the
existing full-frame pass recovers small/distant subjects, mapping each
window's detections back into source-frame coordinates and running one
deterministic, input-order-independent cross-window duplicate-suppression
pass before reusing the unmodified Stage 6.2 precision/recall/clustering
pipeline. On the unchanged 70-frame reviewed cohort, real CUDA results
showed tiling measurably raises recall (0.357 to 0.5) at a real precision
cost (0.270 to 0.035) and a large increase in recurring static
false-positive clusters (4 to 66); the tool's own verdict was `continue_
tiled_strategy_offline_evaluation`, not a live-shadow-trial recommendation.
It opens no product database, changes no runtime threshold, Ignore region,
tracker, or default-provider configuration, and grants no production
authority. Stage 6.5 adds a deterministic, provider-neutral adaptive
motion-proposal strategy described in
[adaptive-motion-proposal-benchmark-contract.md](adaptive-motion-proposal-benchmark-contract.md).
It derives a small bounded number of temporal-change-guided high-resolution
windows (deterministic frame differencing over a fixed-size downsampled
grayscale plane, bounded 8-connected region extraction and merge, padding,
aspect-ratio normalization, and ranking -- no OpenCV, CUDA, or ONNX Runtime
type anywhere in the strategy contract) from ordered source-relative frame
pairs instead of a fixed uniform tile grid, with stable reason codes for
every case temporal evidence cannot honestly support (no predecessor,
sequence/generation boundary, duplicate frame, excessive time gap) and
bounded rejection when a whole-frame brightness shift or broad camera
motion is detected, so neither can produce a grid of proposal windows. A
finalized proposal is geometrically a Stage 6.4 tile
(`window_kind="tile"`), so cross-window duplicate suppression, coordinate
mapping, and the reused Stage 6.2/6.4 report pipeline -- including the
existing, unmodified strategy-comparison function -- apply unchanged. Real
CUDA results across two absolute roots reproduced byte-identical semantic
fingerprints for every strategy/cohort combination and every decision
report; on both the unchanged 70-frame cohort and a new, separate,
ignored, local-only 38-frame reviewed temporal cohort (built from
already-reviewed real local material only), the adaptive strategy matched
the full-frame baseline almost exactly -- proposal windows essentially
never fired, and the one that did neither recovered nor introduced a
detection. Both cohorts' decision reports reached `insufficient_temporal_
data`, an honest evidence-insufficiency verdict rather than a confident
positive or negative one. It opens no product database, changes no runtime
threshold, Ignore region, tracker, or default-provider configuration, and
grants no production authority; Stage 7 remains blocked.

Stage 6.6 adds a reviewed temporal capture and active-learning dataset
pipeline described in
[temporal-review-capture-contract.md](temporal-review-capture-contract.md),
split the same pure/io/cli way as every prior stage:
`temporal_capture`/`temporal_annotation` hold dataclasses and pure
functions only (no filesystem, CUDA, ONNX, OpenCV, or product-repository
import -- structurally enforced by a parametrized source-grep test across
all six new modules); `temporal_capture_io`/`temporal_review_io` do safe,
atomic, bounded local filesystem work only; `temporal_capture_cli`/
`temporal_review_cli` wire real Camera Node/provider/annotation objects
together. It deliberately reuses two upstream capabilities unchanged rather
than reimplementing them: Stage 5's `CameraNodeAnalysisSource`/
`CameraNodeHttpTransport`/`LiveCameraNodeShadowSession` for the live
connection, and Stage 6.5's `motion_proposal_strategy.generate_proposals`
for live per-frame proposal generation -- this stage adds no new detector
or proposal strategy. `temporal-capture`/`temporal-capture-mark` retain
only bounded, triggered frames (detector events, shadow track events,
high-resolution bursts, privacy-boundary interaction, recurring static
geometry, generation/sequence discontinuity, periodic negative sampling,
pretrigger/post-trigger context, and an engineering-only, five-kind
operator marker that never asserts species or product truth) behind
thirteen hard ceilings, writing a capture-session manifest whose semantic
fingerprint carries no absolute path, hostname, credential, or bearer
token (those stay in a separate, caller-only connection config).
`temporal-review-build`/`-validate`/`-export` turn a capture directory into
a self-contained review packet (contact sheet, per-detection crops, copied
source frames, no OCR or remote service), a human whole-frame/box/
temporal-appearance annotation contract with stable rejection/flag codes,
and three export targets that reuse existing schemas without inventing
fields: Stage 6.2's `CalibrationManifest`/`ReviewedBox` (detector-
calibration and motion-proposal targets) and Stage 2's `replay.
BenchmarkManifest` family (replay target, always with an empty `visits`
list -- this stage never invents Visit grouping). A product Visit-level
`false_positive` label is carried only as descriptive provenance
(`product_review_label`, `whole_frame_independently_confirmed`) and a
dedicated validation code rejects any annotation that lets it stand in for
independently reviewed whole-frame negative truth. A bounded real Camera
Node mechanics smoke surfaced a transport-boundary lesson applicable to any
future live Camera Node consumer, not just this stage: on this Node, one
`iter_analysis_frames` batch is one HTTP connection, and one HTTP
connection is a hard discontinuity boundary -- its sequence header resets
per connection even though `provider_generation` does not, so a
long-lived, cross-batch `CameraNodeAnalysisSource`/provider live-tracker
pair must be rebuilt/restarted at every batch boundary (not just treated
as a rare reconnect), and any elapsed-time bookkeeping (periodic sampling,
marker correlation) must key off the host receive clock rather than
`source_offset_ms`, which that same rebuild re-zeroes. All three fixes are
regression-tested with fakes and were then verified together on the real
Node: a 60-second bounded capture retained 18 frames with zero credential/
hostname/path leakage into the manifest and an identical structural
no-write proof before and after. It creates no product record, database
row, or reviewed truth of any kind, and authorizes no Stage 7 activity.
Daylight collection with two real Camera Node sessions (95 and 393 retained
frames) found that the real Node resets its per-connection transport
sequence and source-relative offset bookkeeping on every HTTP reconnection
(13 and 53 times respectively) while `provider_generation` stays unchanged --
the normal case on this transport, not a rare failure -- which broke
cross-connection `AppearanceInterval` validation, review/export ordering,
and full-session replay export. Stage 6.8 adds a reconnect-safe session
timeline described in
[session-timeline-contract.md](session-timeline-contract.md):
`mockingbird.observation.session_timeline` derives a deterministic, monotonic,
engineering-only `session_sequence`/`session_offset_ms` coordinate for every
retained frame -- natively from real per-connection identity and host
receive time for a Stage 6.8 capture, or reconstructed deterministically from
connection-local sequence numbers for an older manifest, explicitly
classified `native_session_timeline`/`derived_session_timeline`/
`insufficient_temporal_provenance` -- while original source-local facts
remain unchanged, separate provenance. `AppearanceInterval` validation,
review-packet/export ordering, and `replay.ReplayInput`'s existing strict
`ordered_timestamps` check (unmodified) all use this timeline; a
`frame-driven-onnx-cuda` replay ends the current tracker generation at a
reported reconnect boundary rather than silently continuing a track across
it. Both real Stage 6.7 sessions upgrade, validate, and replay end to end
with no manually selected connection-safe sub-window and byte-identical
repeated-export fingerprints. It opens no product database and changes no
detector, tracker confirmation policy, evidence scoring, burst policy, or
monitoring policy; Stage 7 remains blocked.

Stage 6.9 adds a provider-neutral, bounded, recurrence-aware burst scheduler
described in
[burst-scheduler-contract.md](burst-scheduler-contract.md). Session-02
daylight collection showed most high-resolution bursts came from a small
number of recurring static structures (a shepherd's-hook plant hanger, a
red-glass hummingbird feeder, left-edge foliage) each re-detected as a
brand-new, short-lived track generation -- 379 generations across 393
retained frames produced 123 bursts, since Stage 5's own gate requests at
most one burst per generation and a new generation alone is sufficient to
pass it. `mockingbird.observation.burst_scheduler` sits between that
"meaningful" `TrackUpdate` (a burst *opportunity*, carrying no authority of
its own) and the existing evidence-burst request: `BurstScheduler.decide()`
is the only place that decides to issue, suppress a duplicate recurrence,
defer for an active request or per-generation cooldown, reject on a bounded
session/rate budget, or allow an explicit operator/engineering override,
using bounded, session-scoped recurrence groups (the same IoU/centroid
convention as `RecurringGeometryTracker`/`cluster_static_false_positives`,
extended with a box-size gate) and stable novelty signals (confidence/
temporal-support materially above the group's own historic floor, motion/
change evidence, a genuine time gap, an operator marker, an engineering
request, or a bounded retry). `LiveCameraNodeShadowSession` now consults it
before every burst request instead of only a generation-id-seen-before set;
`temporal_capture_cli`'s `--validation-burst` engineering path routes through
the same `decide()`/`record_result()` calls. A deterministic offline replay
evaluator (`burst_scheduler_replay`, `python -m mockingbird
burst-schedule-replay`) reconstructs opportunities from an already-captured
manifest and replays them with no product-database or capture-artifact
write; against the real Stage 6.7 sessions it measured a 59% high-resolution
burst reduction on session-02 (123 to 50, 74 explicitly suppressed as
recurring static geometry) while every reviewed genuine and
reviewer-attributed operator-marked appearance retained burst eligibility, a
result reproduced live in a bounded 90-second real Camera Node mechanics
smoke (72 real track generations, 16 real bursts, one labeled engineering
override, unchanged product database hash, clean shutdown). It changes no
detector, tracker confirmation policy, saved Ignore region, evidence
scoring, or monitoring policy, opens no product database, and authorizes no
Stage 7 activity.

A representative shadow-operations acceptance campaign (two new full-length
real daylight sessions, session-03 and session-04, alongside the existing
Stage 6.7 sessions) closed as a measured failure at tracker/Visit assembly:
full-session frame-driven replay produced 129 and 78 tracker generations for
only 2 and 3 reviewed genuine appearances respectively, with
`boundary_reason_distribution` showing the confirmed episodes were being cut
off by `provider_reset` almost every time. The root cause was architectural,
not a detector or evidence defect: this Camera Node reconnects roughly every
ten seconds under real load, and Stage 6.8's session timeline correctly
flags every reconnect boundary as a `temporal_discontinuity` regardless of
whether `provider_generation` (the durable camera/provider identity) changed
-- but the frame-driven replay host treated any discontinuity signal as an
unconditional source reset, mechanically shredding one continuous real
appearance into many independently "confirmed" episodes at every benign HTTP
reconnect. Stage 6.11 adds a reconnect-safe tracker-continuity decision
described in
[reconnect-continuity-contract.md](reconnect-continuity-contract.md):
`mockingbird.observation.reconnect_continuity` distinguishes a benign
transport reconnect (Stream/provider-generation/analysis-profile unchanged,
a genuine new connection segment, a bounded source-relative gap and
temporal uncertainty) from a confidently evidenced source-generation reset
or insufficient bridge provenance, using only already-available Stage 6.8
provenance and never species identity. `ProviderNeutralFrameTracker` gains a
bounded per-track reconnect-bridge budget (`note_reconnect_boundary`):
active tracks are marked temporarily lost, pending bounded reacquisition,
rather than terminated outright; reconnect survival by itself never creates
detector/tracker-support evidence; a track not reacquired within its own
bounded window still terminates, with a distinct `reconnect_bridge_expired`
reason. Replayed against the real session-03/04 data with the identical
provider settings and unchanged human-reviewed truth, tracker generations
started dropped from 129/78 to 81/57, confirmed proposals from 67/27 to
46/28, `provider_reset` terminations dropped from 67/29 to zero in both, and
50/29 tracks (38/23 confirmed proposals) now honestly span more than one
transport connection segment (previously always exactly one, by
construction) -- with zero incorrect merges in either session, before or
after. `appearance_recall`/`proposal_precision` stay at their pre-existing
0.0 in both sessions independent of tracker quality -- the temporal-review-
capture replay export always emits an empty `ExpectedVisit` list by its own
prior, documented design, so nothing can structurally ever match through
this specific benchmark path; the fragmentation and cross-segment metrics
above are the honest evidence of improvement. The existing Stage 6.7
session-01/02 sessions predate Stage 6.8 and carry only reconstructed
(`derived_session_timeline`) provenance with a fixed, deliberately
conservative 30-second `temporal_uncertainty_ms` per reconnect boundary; run
through the identical replay unchanged, every one of their reconnects
correctly fails the bridge's uncertainty bound and still resets exactly as
before this stage -- a clean, real-data confirmation that the new bridging
capability activates only where native, Stage-6.8-quality timeline
provenance actually supports it. Genuine source resets (provider-generation,
camera, Stream, or analysis-profile changes; excessive gaps or uncertainty)
are unaffected and still terminate tracking exactly as before. This stage
changes no detector, detector threshold, burst-scheduler, or evidence-scoring
behavior, opens no product database, and authorizes no Stage 7 activity; live
Camera Node wiring
(`CameraNodeAnalysisSource`/`LiveCameraNodeShadowSession`/
`temporal_capture_cli`) is unchanged, and a separately identified
burst-placement gap for late/sustained appearances remains a distinct,
not-yet-addressed issue.

Stage 6.11B closes that live-wiring gap, reusing the same
`reconnect_continuity` decision module rather than a second policy:
`CameraNodeAnalysisSource` recognizes a new connection segment under an
unchanged `provider_generation` as a benign reconnect, keeping the
session-relative `source_offset_ms` the tracker consumes continuous across
it (only the connection-local anchors reset), and
`FrameDrivenObservationProvider.observe_live_frame` classifies each
boundary and bridges the live tracker exactly as `replay_frames` already
did, instead of `temporal_capture_cli._CaptureLoop` rebuilding the
transport source and restarting the whole live generation on every
ordinary reconnect. `LiveCameraNodeShadowSession` reacts only to a genuine
reset (via the provider's own `live_reset_count`) rather than every
reconnect, so Stage 6.9 burst-scheduler recurrence state now also survives
a benign reconnect. A bounded 180-second real Camera Node session showed 7
real reconnects, all classified benign with zero provider resets, and an
unchanged product database; the burst-placement gap remains separate and
not yet addressed.

Stage 6.12 closes that burst-placement gap. Reconstructing the complete
decision timeline for the real session-04 capture (`burst_scheduler_replay`
against a fresh `BurstScheduler` running the unmodified Stage 6.9
configuration) proved the exact mechanism: the session-budget gate in
`decide()` was checked before recurrence/novelty evaluation ever ran, so
once early-session activity exhausted the fixed 56-slot budget (at
session-relative 439s, before the 457-551s `appearance-C` even begins),
every later opportunity -- all 46 of `appearance-C`'s reconstructed
opportunities -- was rejected unconditionally, regardless of novelty. A
diagnostic replay with only that budget/rate gate lifted showed the
existing, unmodified recurrence/novelty logic correctly recognized 38 of
those 46 as materially novel, disproving the earlier, disclosed-as-
unverified hypothesis that recurrence-floor bookkeeping itself was at
fault. `mockingbird.observation.burst_scheduler` now runs
recurrence/novelty evaluation unconditionally before any budget check
(changing only *when*, never *whether*, a non-novel recurrence is
rejected) and adds one small, bounded, session-relative-time rolling
fairness reserve (`novelty_reserve_capacity` per
`novelty_reserve_window_ms`, default 8 per 120s) that only an opportunity
already proven not a suppressible recurrence may draw from once the
ordinary or operator-override budget is exhausted -- a recurring,
non-novel opportunity is rejected before ever reaching it and can never
consume it, and engineering-validation overrides never fall back to it.
`max_bursts_per_session`, `operator_override_reserved_bursts`,
`max_concurrent_requests`, and `max_bursts_per_minute` remain exactly as
absolute as before. Replayed against the real session-01-04 sessions with
`novelty_reserve_capacity=0` reproducing the exact Stage 6.9 baseline
byte-for-byte: session-01 (never exhausts its ordinary budget) is
unaffected; session-02/03 already retained every reviewed appearance and
gain materially better temporal distribution (longest starved interval
roughly halved in both) with recurring-geometry suppression counts
unchanged or higher; session-04's `appearance-C` moves from zero issued
bursts to burst-eligible (genuine appearances retained: 2/3 to 3/3) while
`appearance-A`/`appearance-B` retention is unaffected, with issued-burst
counts moving only modestly (56 to 64 of 266 reconstructed opportunities)
-- nowhere near the pre-Stage-6.9 123-burst/379-generation volume. It
changes no detector, tracker confirmation policy, reconnect continuity,
Camera Node transport, evidence scoring, saved Ignore region, or
monitoring policy, opens no product database, and authorizes no Stage 7
activity.

Stage 6.13 closes a standalone tooling gap Stage 6.7/6.10 acceptance work
repeatedly disclosed: there was no standalone evidence-scoring benchmark CLI,
so evidence usefulness was sometimes reported with bounded descriptive
analysis instead of the same deterministic benchmark/report machinery already
established for detector, tracker, multi-scale, and burst evaluation.
`mockingbird.observation.evidence_benchmark`
(`python -m mockingbird evidence-benchmark`/`evidence-comparison`, see
[evidence-benchmark-contract.md](evidence-benchmark-contract.md)) evaluates a
reviewed evidence manifest by calling the existing Stage 6
`evidence_scoring.score_proposal_evidence` scorer once per reconstructed
episode -- never a second ranking algorithm -- against reviewed truth whose
fields mirror Stage 6.6 temporal-review annotation fields, deriving that
manifest directly from an already-built review packet (`--review`) so a
caller never hand-copies data that already exists in the reviewed packet. It
optionally supplements reviewed-manifest episodes with real candidates/
proposals reconstructed from an already-produced replay report. Every metric
reports `evaluated`/`not_evaluated`/`insufficient_truth`/`unsupported` rather
than a fabricated zero, and `evidence-comparison` classifies each metric
`baseline better`/`candidate better`/`equivalent`/`insufficient truth`/
`unsupported for one side` without an aggregate winner score, mirroring
`compare_replay_reports`'s established shape exactly. Real evaluation against
four historical reviewed Camera Node sessions (session-01, the high-burst
session-02, session-03, and the late-appearance session-04 from Stage
6.8/6.10 -- 41/146/114/129 reconstructed episodes respectively) found useful
identification evidence only among the minority of episodes that selected any
identification candidate at all (12/41, 6/146, 24/114, 31/129), a useful-
identification rate of 0.25/0.5/0.25/0.14 among those, and zero episodes
across all four sessions where a high-resolution burst frame -- rather than
an ordinary tracked analysis frame -- was the selected identification
evidence; useful-context rate read 1.0 in all four, which reflects the
underlying Stage 6.6 annotation convention (broad context usefulness was
recorded liberally) as much as it reflects evidence quality. Because the
Stage 6.6 review-packet derivation path does not independently record
temporal alignment, every selected candidate's temporal-alignment metric
reads `uncertain` in all four sessions -- an honest limitation of this
specific offline reconstruction path, not a measurement that the live system
never produces temporally aligned evidence. `selected_identification_
correctness`/`selected_context_correctness` read `not_evaluated` throughout
because this historical corpus never recorded a reviewer's preferred-
candidate truth. Combining session-04's review packet with its own already-
produced Stage 6.11 replay report surfaced a genuine, disclosed, pre-existing
limitation rather than a defect this stage introduces: a replay produced
through `replay-benchmark` assigns each frame a new, replay-derived identity
distinct from the original reviewed `frame_id`, so truth could not link to
any replay-sourced candidate -- honestly reported as a limitation rather than
a silent zero. It opens no product database (a structural no-write proof
found an unchanged SQLite hash/size and every tracked table row count before
and after), changes no detector, tracker, reconnect, burst-scheduler, or
evidence-scoring behavior, and authorizes no Stage 7 activity; the
representative Stage 6.10 rerun this tool is meant to support remains a
separate, not-yet-run step.

Stage 6.14 closes that exact gap, described in
[reviewed-replay-lineage-contract.md](reviewed-replay-lineage-contract.md).
`replay.ReplayFrame` gains optional, additive reviewed-source-lineage fields
(`source_capture_frame_id`, `source_capture_session_id`, `session_sequence`),
which `temporal_annotation.build_replay_export` now explicitly populates from
the original reviewed `frame_id`/session/session-sequence rather than only
implying identity through the `path` string; `ReplayInput.packets()` carries
`source_capture_frame_id`/`source_content_hash` onto each `FramePacket`
alongside its own unchanged replay-local `frame_id`, and every downstream
provider-neutral fact (`DetectionObservation`, `TrackUpdate`,
`EvidenceCandidate`, `VisitProposal`) gains the matching optional provenance
field, all absent by default so a pre-Stage-6.14 input or report is
unaffected. `evidence_benchmark._source_lineage_join` then joins a
replay-sourced candidate to reviewed truth through this explicit identity --
never coincidental equality, filename, frame ordering, timestamp, or
geometry -- refusing rather than guessing on a detected hash mismatch,
content conflict, or unknown source reference, each with its own stable
limitation code; a companion fix lets the benchmark's own rescoring of a
replay-sourced candidate decode the exact reviewed image bytes that
identity provably traces back to, without which no replay-sourced candidate
could ever be eligible for selection regardless of lineage. Real evaluation
against the historical session-04 reviewed packet combined with a freshly
produced Stage 6.14 replay (real RTX 4060 Ti CUDA execution, run from two
independent absolute filesystem roots) reproduced byte-identical semantic
fingerprints at the export, replay, and evidence-benchmark layers across both
roots, and reproduced the exact pre-existing tracker/detector counts already
established by Stage 6.11/6.12 (57 tracks started, 28 confirmed) -- proving
no detector, tracker, reconnect, or burst behavior changed. All 451 replayed
frames, 1679 detections, 282 evidence candidates, 305 track updates, and 28
proposals carried source lineage; 25 of 28 replay-sourced episodes' selected
identification and context evidence joined directly to reviewed truth (the
remaining 3 selected a synthetic boundary frame carrying no source lineage by
construction), moving `episodes_with_identification_candidate` from 31 to 56
and `useful_identification_rate` from a manifest-only-informed 0.143 to a
0.176 now genuinely reflecting replay-sourced evidence too.
`selected_identification_correctness`/`selected_context_correctness` remain
honestly `not_evaluated`: this historical corpus never recorded a reviewer's
preferred-candidate truth, and lineage makes a join possible without
inventing the human judgment it would be compared against. Session-01 and
session-02 spot-checks confirmed the mechanism is not special-cased to
session-04 (100% detection/evidence-candidate lineage propagation in both;
session-01's one confirmed proposal joined truth directly; session-02
reproduced zero confirmed proposals byte-identical to its own existing
Stage 6.11 replay record, an unrelated pre-existing tracker-confirmation
fact). A structural no-write proof taken before and after the entire
campaign found an unchanged SQLite hash/size and every tracked table row
count. It opens no product database, changes no detector, tracker,
reconnect, burst-scheduler, or evidence-scoring behavior, and authorizes no
Stage 7 activity; the representative Stage 6.10 rerun remains a separate,
not-yet-run step, now unblocked at the tooling level.

Stage 6.15 fixes a live burst-storm defect (`BurstScheduler`'s novelty
signal compared a monotonic per-generation counter against a recurrence
group's historic floor instead of a frozen high-water baseline, so a
recurring static object re-detected as a fresh generation read as
"stronger support" almost immediately on every rebirth). The representative
shadow-acceptance resumption that followed (real Camera Node, real CUDA,
no code changes) confirmed the Stage 6.11 reconnect fix directly and found
a new, independent root cause: a real, directly confirmed ~5-minute
feeder-bird visit still fragmented into approximately 37 confirmed track
generations because natural detector-confidence dips exceeded the
tracker's ordinary tight bound more often than a sustained multi-minute
visit's own real cadence tolerates. Stage 6.16 adds a bounded strong/weak/
tracker-only evidence hierarchy described in
[sustained-visit-continuity-contract.md](sustained-visit-continuity-contract.md):
a matched detection below `strong_detection_threshold` but above a reused
`weak_detector_support_floor` refreshes an already-confirmed track's
continuity without counting as a new strong confirmation, and a confirmed
track earns a widened per-frame gap tolerance (reusing the existing
`maximum_unsupported_detector_ms` budget, never a new ceiling) once
anchored by any genuinely strong hit, or for a bounded one-time
provisional window from its own start if it never shows one.
`minimum_detector_confirmations` itself keeps its exact pre-existing,
unconditional meaning -- real evidence proved a genuinely continuous
subject's own confirming pair is routinely both individually weak, so
gating confirmation on strength would have hurt recall, not just
continuity. Replayed against the real attempt-2/attempt-3 sessions (a
hardware-free recorded-detection-playback harness, since real CUDA
hardware was unavailable in this environment, isolating the tracker change
against the unchanged, already-real-CUDA-verified detector output) and
historical sessions 01-04: fragmentation fell or held in every session
(attempt-3 tracks started 63 to 47, confirmed 37 to 25) with zero incorrect
merges or duplicates and reconnect-fix facts identical before and after;
the real hard-negative session's every confirmed generation stayed in the
bounded provisional tier (zero strong hits, matching its own real
sub-threshold maximum score) with confirmed-proposal count falling, not
rising. It opens no product database, changes no detector, detector
threshold, burst scheduler, reconnect continuity, Camera Node transport,
evidence scorer, session timeline, or monitoring policy, and authorizes no
Stage 7 activity by itself; a real-hardware repeat of the representative-
acceptance campaign remains the next required step.

Stage 6.19 adds a shadow `VisitEpisodeAssembler` described in
[tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md),
separating track lifetime from Visit lifetime: the frame-driven tracker
stays unmodified, conservative, and allowed to fragment, while a new,
optional, later pass decides -- from bounded evidence density and geometry
stability alone, never species identity or wall-clock time -- whether
temporally-adjacent confirmed tracklets belong to one sustained appearance.
It is a pure module with no product-repository import, remains shadow-only
with `shadow_only=true` enforced on every output, and by itself authorizes
no Stage 7 activity.

Stage 7 adds the first Observation Engine v2 authority migration described
in
[candidate-visit-authority-contract.md](candidate-visit-authority-contract.md):
one explicit, default-off `ObservationAuthorityMode` (`shadow` or
`candidate_visit`) gates a narrow persistence adapter --
`mockingbird.observation.candidate_visit_adapter`, the one module that
imports both the shadow assembler's output type and the product repository
-- that may turn one accepted Stage 6.19 `AssembledVisitProposal` into at
most one bounded, needs-review candidate Visit through the existing
`VisitModel`/`EventModel` schema. `VisitEpisodeAssembler` itself remains
completely product-repository-independent; `ProductRepository.create_
candidate_visit_from_proposal` is the one transactional, idempotent,
concurrency-safe seam where a proposal may actually become a product
record, gated by a durable activation boundary (so enabling authority never
retroactively promotes historical shadow output), bounded session/hourly
rate limits, and Privacy/Ignore Zone safety. It can never create a
`ReviewLabel`, mark a Visit reviewed, or write species/analytics/export
truth; only the exact existing, unmodified correction path can. A bounded
real Camera Node trial (`python -m mockingbird candidate-authority-trial`,
hard-capped at 10 minutes and 3 candidates) provides live round-trip
validation without a live incremental assembler -- the trial periodically
reruns the same bounded, post-hoc `build_tracklets`/`assemble_visit_
episodes` pass over the live session's own accumulated track updates.

Product Vertical Slice v1 makes this engine reachable from the app itself,
described in
[observation-engine-product-control-contract.md](observation-engine-product-control-contract.md):
`mockingbird.observation.engine_runtime.ObservationEngineSessionManager` is
an app-owned, per-Stream background session (mirroring
`LiveCameraSessionManager`'s lifecycle convention) that reuses this same
construction long-running and stoppable instead of trial-bounded, activating
`candidate_visit` authority on Start and reverting to `shadow` on Stop or
any session end. A new conservative candidate-quality admission boundary
(`mockingbird.observation.candidate_quality_gate`) sits between an
authority-approved proposal and its actual persistence, composed only from
already-produced Stage 6/6.19 facts. Existing Review Queue effective-primary
and product-category classification logic, previously tuned only to legacy
motion-evidence roles, was extended additively to also recognize Stage 7's
`identification`/`context`/`alternate` roles. It changes no detector,
tracker, burst-scheduler, evidence-scoring, or authority-gate behavior.

Unified Observation Experience v1 makes that same app control's product
contract (`GET/POST /api/streams/{id}/observation/status|start|stop`)
consistent across every currently-supported Stream type, described in
[unified-observation-panel-contract.md](unified-observation-panel-contract.md):
`mockingbird.observation.unified_status` is a pure, side-effect-free
composition layer that picks one existing runtime per Stream -- this engine
for a paired Camera Node, the existing durable `StreamMonitoringPolicy` +
`DurableMonitoringSupervisor` + `LiveCameraSessionManager` path for RTSP/
local USB/Windows DirectShow, the existing `SourceMonitorManager` for a
remaining `external_url` Source, or an honest unavailable status otherwise
-- and normalizes each into the same basic state/health vocabulary. It adds
no new runtime, detector, tracker, or candidate authority; it only decides
which already-accepted runtime a Stream's Start/Stop/Status action reaches,
and each runtime keeps its own existing authority semantics unchanged.

The Stream-to-proposed-Visit subsystem will be reworked through a strangler
migration, not a product rewrite. A provider-neutral Observation Engine consumes
Stream capabilities and emits only evidence-side `FramePacket`,
`DetectionObservation`, `TrackUpdate`, `EvidenceCandidate`, and `VisitProposal`
facts plus bounded capability/health state. Media pipeline providers own decode,
timestamps, identities, rolling buffers, and high-resolution requests; inference
providers own model execution only; MockingBird tracking and Visit assembly own
temporal continuity, evidence scoring, and proposal semantics. Interpretation is
downstream of assembled Visits; correction remains the first truth write.

`SnapshotObservationProvider` names the current timer-driven path. It remains a
privacy-preserving compatibility provider for lower-capability hardware,
deterministic comparison, and fallback. Future CPU and other accelerated
providers must conform to the same contract; the implemented ONNX Runtime CUDA
provider is replay-only and shadow-only. A completely functional
CPU path and the provider contract remain open and vendor-neutral. Proprietary
acceleration may improve performance but cannot define MockingBird data, truth,
or product behavior. The Raspberry Pi validates one Camera Node provider path;
it does not define the product architecture.

The first visual species-classifier seam is request-bound to one saved Review
Queue image. It chooses a padded credible animal-detection box, then measured
activity bounds, then a full-frame fallback only when no active Privacy/Ignore
Zone would be analyzed. BioCLIP inference is isolated from the long-lived app
process and database transactions, then writes one ranked `SpeciesSuggestion`
atomically after success. Detector evidence, the original frame, and the actual
classifier crop remain separate provenance. A nonblocking single-flight guard
is acquired before image decode, the disposable worker has a hard timeout, and
artifact digests plus OpenCLIP/PyTorch versions are retained without exposing
local paths. On Windows, the spawn arguments carry only bounded metadata and a
shared-memory descriptor; full RGB bytes are not serialized into process
startup.

### Source adapters

Implemented product paths include demo/manual media, explicit external still
images, explicit folder/trail-cam import, metadata-only webhook evidence,
browser-playable streams, RTSP, Linux local USB, Windows DirectShow, and the
paired local-LAN Camera Node snapshot adapter.

Adapters sit below provider configuration, Source connection status, and Stream
playback status. They normalize into Source/Stream/MediaAsset/MotionEvidence or
proposal evidence. Provider status does not run providers. Incoming labels or
events do not bypass Review Queue correction.

Guided Camera Editing changes an existing compatible Source/Stream in place.
Its read, validation, impact-preview, and bounded revision-history contracts
redact provider values and credentials; provider type remains fixed. An
application service coordinates a runtime-affecting save with the existing
session manager and durable supervisor, preserving desired monitoring intent,
Zones, Events, Visits, evidence, corrections, organization, map placement,
alerts, and health history. A restart is requested only after explicit
confirmation for an already-armed Stream; capacity remains a waiting state
rather than disabling monitoring.

Provider-specific security, storage, and evidence contracts remain in focused
design documents routed by [AGENTS.md](../AGENTS.md).

Camera Node is an edge adapter, not a parallel product runtime. Its explicit
one-time pairing creates a locally stored masked credential and one selected
opaque camera ID beneath the existing Source/Stream. The main app owns all
Zones, monitoring intent, activity/evidence, Visits, correction truth, backup,
and retention. Node requests are fixed-path, private-LAN-IP-only, bounded, and
redirect-free. Add Camera can request one transient bounded JPEG before a Zone
is drawn; running live/monitoring snapshots use the in-memory frame cache.
Neither preview form is persisted. See
[camera-node-boundary-design.md](camera-node-boundary-design.md).

## Live camera ownership

`LiveCameraSessionManager` owns bounded process-local camera resources for
supported backend-served live video:

- one camera subprocess/session per Stream
- latest-frame cache used by Live view, explicit capture, and monitoring
- bounded monitor state and activity bursts
- explicit start/stop and graceful application shutdown

The current session manager does not survive process restart. It starts only
after explicit user action and creates no reviewed truth. A browser closing or
status poll does not implicitly define camera policy.

Browser-direct MJPEG/video/HLS playback is separate from backend capture and
monitoring. The external URL snapshot monitor is a separate in-memory provider
path and is not part of durable live-video supervision.

## Durable lifecycle boundary

Three concerns remain separate:

- `StreamMonitoringPolicy`: durable user intent, defaulting to off
- `StreamRuntimeCheckpoint`: operational last-known state, never proof that an
  old process is still running
- `LiveCameraSessionManager`: current-process camera and monitoring resources

`DurableMonitoringSupervisor` reconciles explicitly enabled supported
live-video Streams with current-process sessions. It is app-owned, starts only
after local persistence initialization, respects one-Stream leases and a small
concurrency cap, waits for a healthy frame before motion evaluation, and uses
deterministic bounded backoff. The persisted policy remains desired state;
runtime checkpoints expose the last-known actual state and are invalidated when
a prior app process ends.

Backup, restore, migration, emergency stop, Source archive, Stop camera, and
shutdown override active runtime. Stop camera also disables durable intent so
it cannot immediately restart. Status reads remain side-effect free. External
snapshot polling and general provider workers remain separate. Future audio
requires its own consent, privacy, retention, dependency, and evidence design;
video arming never enables a microphone.

## Worker boundary

Workers, polling, watchers, queues, and background cleanup are optional
infrastructure underneath explicit provider actions. They begin disabled,
observable, bounded, local-first, and safely stoppable. They may create evidence
only when explicitly scoped and can never create ReviewLabels, mark Visits
reviewed, or create analytics/export truth.

## Dependency direction

Preferred dependency direction:

```text
frontend -> product API -> domain services -> product repository/storage
                              ^
                              |
                 adapters / camera sessions / analyzers
```

Adapters and runtime components depend on product contracts. Product models do
not depend on adapter-specific payloads, FFmpeg details, model outputs, or one
camera ecosystem.

Phase 24 engineering hardening uses targeted extraction rather than a broad
rewrite: lifecycle work should move touched camera/supervisor behavior toward
focused services, and primary frontend work should move touched page behavior
toward focused components/hooks and scoped styles. Refactoring preserves
behavior and remains separate from unrelated features.

## Local product packaging and lifecycle

MockingBird's runtime architecture -- one FastAPI process serving both the
product API and the built frontend from the same origin, backed by local
SQLite -- is host-neutral by construction; nothing about it is
Windows-specific. Phase 27 (see
[local-product-packaging-design.md](local-product-packaging-design.md))
packages that same architecture as a self-contained "unpack and run" bundle
with a real embedded Python runtime, first on Windows, without introducing a
second UI runtime, a container, or a service-manager dependency.

First-run state (`app_setup_state`, schema 29) is ordinary product state,
seeded once from the one-time "was this database just created" fact
`initialize_database` already computes, never recomputed from current
Source/Stream counts. A small `runtime_state` module (deliberately dependent
on neither `runtime.py` nor `api/main.py`, which already depend on each
other in narrow, deferred ways) tracks the previous-shutdown marker and the
fixed local log location; both are best-effort local facts, never required
for startup to proceed.

## Architecture invariants

- Streams and Zones remain central even when playback is unavailable.
- Detections and suggestions are evidence; correction is truth.
- Provider and status reads are side-effect free.
- Persisted intent and actual runtime state are not conflated.
- Privacy/Ignore Zones, retention, backup/recovery, and storage budgets apply
  before unattended behavior.
- Generated datasets, media, models, benchmarks, and caches stay ignored/local.
- Release acceptance includes contract parity, schema/backup upgrades,
  hardware-free browser coverage, failure injection, and field performance
  budgets from [roadmap.md](roadmap.md).
