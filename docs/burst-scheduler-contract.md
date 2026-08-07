# Recurrence-aware burst scheduler contract

Status: Observation Engine v2 Stage 6.9 engineering-workflow contract, extending
[camera-node-live-shadow-contract.md](camera-node-live-shadow-contract.md) and
[temporal-review-capture-contract.md](temporal-review-capture-contract.md). Stage
6.12 (below) adds late-session evidence-burst fairness and a bounded novelty
reserve on top of this same contract.

## Problem

Stage 6.7 daylight collection found that most high-resolution burst captures were
not wildlife. session-02 alone retained 393 frames, created 379 distinct track
generations, and captured 123 high-resolution bursts, but the reviewed dataset
shows only a small fraction of those bursts covered a genuine animal -- most came
from a handful of recurring static structures (a shepherd's-hook plant hanger, a
red glass hummingbird feeder, left-edge foliage) that the tracker re-detects as a
brand-new, short-lived track generation over and over. The existing burst gate in
`LiveCameraNodeShadowSession._process_frame` (Stage 5) requests at most one burst
per track generation with a single global cooldown; because a new generation alone
is sufficient to pass that gate, recurring static geometry defeats it by
definition -- every re-detection is, mechanically, a "new" generation.

Critically, the reviewed session-02 annotation shows genuine bird appearances on
the same tube-feeder perch whose boxes are sometimes near-identical to the
recurring cluster's own representative box (for example `[0.4536, 0.593, 0.4671,
0.6311]` appears both as a recurring-geometry cluster member and, at a different
moment, as an independently reviewed `whole_frame_truth: "yes"` box). Geometry
alone cannot separate the two cases; a viable scheduler must use score, temporal
support, motion, or operator context to make that call.

## Boundary

`mockingbird.observation.burst_scheduler` is pure: no CUDA, ONNX Runtime,
PiCamera2, camera-provider, transport-library, or filesystem type anywhere in its
contract, and no product-repository import. It holds only bounded, temporary,
session-scoped in-memory state and never opens the product database. Every
decision remains advisory to the existing Stage 5 evidence-burst path; the
scheduler never calls a transport, never decodes an image, and never creates
`MediaAsset`, `Event`, `Visit`, `ReviewLabel`, reviewed `Observation`, or
monitoring-policy rows. It does not change detector thresholds, tracker
confirmation policy, saved Ignore regions, evidence scoring, or production
authority.

### Burst opportunity, decision, and result are three separate concepts

- **Burst opportunity** (`BurstOpportunity`): a detector/track/operator event
  indicating that high-resolution evidence could be useful. Produced by the
  existing Stage 4/5 tracker and Camera Node live-shadow path; carries no
  authority of its own.
- **Burst scheduler decision** (`BurstDecision`): a bounded decision to issue the
  burst now, suppress a duplicate recurrence, defer for an active request or
  cooldown, reject on a session/rate budget, or allow an explicit
  engineering/operator override. `BurstScheduler.decide()` is the only place this
  decision is made.
- **Burst result**: the existing Stage 5 `EvidenceBurstResult` and temporary
  `EvidenceCandidate` facts, unchanged. The scheduler only tells a caller whether
  to *attempt* a burst; the Camera Node transport, capture success/failure, and
  evidence-candidate shape are exactly as before.

A new track generation is therefore no longer sufficient by itself to guarantee a
fresh burst. Track generations remain useful provenance (the scheduler records
`track_generation_id` on every decision), but the scheduler -- not generation
identity -- decides whether a burst is actually requested.

## `BurstOpportunity`

A frozen dataclass carrying only bounded, provider-neutral facts: opportunity id,
`stream_id`, scheduler `session_id`, Camera Node `node_session_id`,
`provider_generation`, Stage 6.8 `connection_segment_id`/`session_sequence`/
`session_offset_ms` (when known), `track_generation_id`, `trigger_frame_id`,
`source_offset_ms`, `broad_class`, normalized `subject_geometry`,
`detector_score`, `detector_confirmation_count`, `tracker_support_count`,
`motion_change_score` (bounded 0..1, `None` when unavailable),
`operator_marker_present`, `trigger_reason`, `requested_evidence_profile`,
`shadow_only` (must be `True`), and `engineering_validation_request`. No CUDA,
ONNX Runtime, PiCamera2, or transport-library object can enter this type --
enforced by a structural source-grep test, the same convention every earlier
Stage 6.x pure module uses.

`time_reference_ms` prefers `session_offset_ms` (the Stage 6.8 reconnect-safe
coordinate) and falls back to `source_offset_ms` when the caller has not attached
a session timeline (for example a bare live frame before Stage 6.8 upgrade, or a
synthetic test). All semantic scheduling decisions use this source/session-relative
value; wall-clock time never enters `decide()`.

## Session-level scheduler state

One `BurstScheduler` instance owns bounded, temporary state for one shadow
capture session: active burst requests (`max_concurrent_requests`), recently
issued bursts, recurrence groups (`max_recurrence_groups`), last-burst offset per
track generation, total issued/successful/failed/stale burst counts, an observed
burst-byte-size sample used to estimate bytes avoided, retry counters, suppression
reason counters, and a bounded decision history (`max_decision_history`). None of
it is durable product state.

`BurstScheduler.reset(reason)` clears all of it back to a fresh session, keyed by
one of four bounded reasons: `session_stop`, `provider_reset`,
`camera_node_generation_replacement`, or `engineering_reset`. The live wiring (see
below) calls this on `LiveCameraNodeShadowSession.stop()` and whenever the
provider's generation changes -- the same two points that already clear the
session's tracker/evidence state.

## Recurrence grouping

`_RecurrenceGroup` membership is a deterministic, bounded, general-purpose test
reusing the same IoU/centroid convention already established by
`detector_benchmark.cluster_static_false_positives` and
`temporal_capture.RecurringGeometryTracker`, extended with a box-size gate:

- `broad_class` equality,
- `stream_id` equality,
- `provider_generation` equality (or both unknown),
- `IoU(box, group.representative_box) >= geometry_iou_threshold` (default 0.3),
- `centroid_distance(box, group.representative_box) <= geometry_centroid_threshold`
  (default 0.05, normalized units), and
- box-area ratio within `size_change_ratio_threshold` (default 0.35) of the
  group's representative area.

No exact yard coordinate is hard-coded; every threshold is a general, relative
geometry test that behaves the same for any camera layout or feeder position. A
detection that fails any test starts (or joins) a *different* group instead of
being silently dropped -- there is no "unclustered" bucket. Groups are bounded to
`max_recurrence_groups` (default 64, matching `RecurringGeometryTracker`'s own
cap); once full, the least-recently-seen group is evicted to make room. A group
that has not matched any opportunity for `recurrence_group_expiry_ms` (default
120s of source/session-relative time) is purged before the next match attempt, so
long-idle geometry does not permanently consume a slot and a later, unrelated
reappearance at the same place starts a fresh group rather than inheriting stale
history.

The *first* opportunity that ever matches a group is never suppressed as a
recurrence (a group needs `min_recurrence_to_suppress`, default 2, occurrences
before "recurring" applies) -- this is also how significant geometry displacement,
a significant box-size change, and a different broad class "permit a new burst" in
practice: each of those differences means the opportunity does not match any
existing group, so it starts a new one and is issued (subject to the same
budgets as everything else).

## Novelty and override behavior

Once a group is genuinely recurring (>= `min_recurrence_to_suppress` occurrences)
and the current opportunity arrives within `recurrence_group_cooldown_ms` (default
60s) of that group's own last *issued* burst, `_evaluate_recurrence` still allows a
fresh burst when any of these hold, each reported as a stable novelty code on the
decision:

- `stronger_confidence`: `detector_score` exceeds the group's own historic *floor*
  score by `stronger_confidence_delta` (default 0.15).
- `motion_change_evidence`: `motion_change_score` meets `motion_change_threshold`
  (default 0.15).
- `stronger_temporal_support`: `detector_confirmation_count +
  tracker_support_count` exceeds the group's historic floor support by
  `temporal_support_delta` (default 2).
- `source_relative_time_gap`: the group's cooldown has actually elapsed (>=
  `recurrence_group_cooldown_ms` since its last issued burst) -- reported rather
  than silently treated as "not a duplicate."
- `operator_wildlife_marker`: `operator_marker_present` is set by a real operator
  marker correlated onto the trigger frame.
- `engineering_validation_request`: an explicit engineering request (see
  Overrides below).
- `bounded_retry_permitted`: the same track generation's previous burst attempt
  failed or returned stale, and `max_retries_per_opportunity` has not been
  exhausted.

The confidence/support comparisons use the group's own historic **floor** (the
minimum score/support ever observed for that group, updated from every
occurrence -- issued or suppressed -- never just its most recent issuance)
rather than "the last thing that happened to issue." Comparing only against the
last issuance is order-dependent and can under-count novelty: an earlier,
weaker novelty-driven burst (for example a time-gap escape) would otherwise
silently raise the bar for the very next genuine sighting moments later --
confirmed against real session-02 data, where two real bird sightings roughly
three seconds apart initially caused the second to read as *not* meaningfully
stronger than the first's already-elevated reference point. Comparing against
the group's stable, monotonically non-increasing floor instead asks "is this
meaningfully above what this location's static/background noise normally
scores," which is the actual question novelty needs answered.

When none apply, the decision is `suppressed_recurring_geometry`. "A recent
recurrence may be suppressed only when evidence is substantially unchanged" is
implemented literally: every dimension the task lists as evidence of change has a
corresponding, independently testable novelty check above.

### Overrides

`operator_marker_present` and `engineering_validation_request` both bypass
per-generation cooldown, recurrence-group suppression, and the rate budget --
matching "operator markers must override recurrence suppression." Neither bypasses
`max_concurrent_requests` (a real physical one-capture-at-a-time constraint on the
Node) nor the session budget outright: an override may spend into a small,
separately bounded `operator_override_reserved_bursts` allowance (default 6)
*beyond* `max_bursts_per_session`, so overrides get real headroom without being
literally unlimited. `operator_override_issued` and `engineering_override_issued`
are distinct, explicitly labeled outcomes so a reviewer can always tell an override
apart from ordinary novelty-driven issuance.

## Cooldown, rate, retry, and session bounds

`BurstSchedulerConfig` (all fields bounded and validated in `__post_init__`):

| Field | Default | Meaning |
| --- | --- | --- |
| `minimum_burst_interval_ms` | 1000 | Per-track-generation cooldown |
| `recurrence_group_cooldown_ms` | 60000 | Per-recurrence-group duplicate window |
| `recurrence_group_expiry_ms` | 120000 | Group forgotten after this much inactivity |
| `min_recurrence_to_suppress` | 2 | Occurrences before a group is "recurring" |
| `max_bursts_per_minute` | 30 | Rate budget over `rate_window_ms` |
| `rate_window_ms` | 60000 | Rolling window for the rate budget |
| `max_bursts_per_session` | 50 | Hard session cap on issued bursts |
| `operator_override_reserved_bursts` | 6 | Extra bounded allowance for overrides |
| `max_concurrent_requests` | 1 | Bounded in-flight burst requests |
| `max_retries_per_opportunity` | 1 | Bounded retry attempts after failure/stale |
| `max_decision_history` | 256 | Bounded decision log length |
| `max_recurrence_groups` | 64 | Bounded live recurrence-group count |
| `geometry_iou_threshold` | 0.3 | Recurrence-group geometry match |
| `geometry_centroid_threshold` | 0.05 | Recurrence-group geometry match |
| `size_change_ratio_threshold` | 0.35 | Recurrence-group box-size match |
| `stronger_confidence_delta` | 0.15 | Novelty: confidence increase |
| `motion_change_threshold` | 0.15 | Novelty: motion/change evidence |
| `temporal_support_delta` | 2 | Novelty: stronger detector/tracker support |
| `novelty_reserve_capacity` | 8 | Stage 6.12: bounded fairness-reserve capacity per rolling window |
| `novelty_reserve_window_ms` | 120000 | Stage 6.12: rolling window the reserve capacity replenishes over |

All are source/session-relative-time semantics; only `record_result`'s optional
wall-clock bookkeeping (used for live health/staleness display, never for a
decision) and any live caller's own resource guarding use real time. This stage
does not raise the existing Stage 6.6 `max_high_resolution_frames` capture-session
ceiling -- it reduces how often that ceiling is reached by recurring geometry in
the first place.

### Real-session tuning rationale

The rate/session/cooldown defaults above were tuned directly against real
session-02 replay, not chosen arbitrarily. An initial, more conservative
`max_bursts_per_minute=6`/`max_bursts_per_session=40`/
`recurrence_group_cooldown_ms=20000` measurably suppressed recurring static
geometry (`suppressed_recurring_geometry` fired as intended), but the *budgets*
themselves became the dominant blocker: session-02's real scene has several
distinct recurring structures whose legitimate "first sighting of a new group"
issuances alone consumed the entire rate window within the first ~10 seconds and
the entire session budget within the first ~80 seconds, after which every later
opportunity -- including the reviewed genuine appearances at 44s, 67s, and 111s
-- was rejected by budget exhaustion regardless of novelty. Recurrence-group
suppression is the mechanism actually responsible for volume reduction; the
budgets are meant as a coarser safety net against pathological device-level
flooding, not a routine pacer that fights that mechanism. `max_bursts_per_minute`
30 and `max_bursts_per_session` 50 remain real, bounded ceilings (a genuinely
runaway detector-noise flood is still caught) while leaving room for a normally
busy multi-structure feeder scene. `recurrence_group_cooldown_ms` moved from 20s
to 60s because session-02's recurring geometry is visible on roughly 71% of
retained frames -- a short cooldown let a continuously-present static structure
re-escape via `source_relative_time_gap` every single window, all session long.

## Stable decisions and reason codes

`SCHEDULER_DECISIONS`: `burst_issued`, `suppressed_same_track_generation`,
`suppressed_recurring_geometry`, `suppressed_active_request`,
`suppressed_session_budget`, `suppressed_rate_budget`, `deferred_cooldown`,
`operator_override_issued`, `engineering_override_issued`, `retry_issued`,
`burst_unavailable`. The three concurrency/cooldown-adjacent outcomes each have a
distinct, non-overlapping trigger so a reviewer never has to guess which applied:
`deferred_cooldown` fires when *this exact track generation* already has an
unresolved (issued, not yet `record_result`-ed) request in flight;
`suppressed_active_request` fires when the *global* `max_concurrent_requests` slot
count is exhausted by any generation's in-flight request; and
`suppressed_same_track_generation` fires when this generation's *most recent
resolved* request is still inside `minimum_burst_interval_ms`. Every
`BurstDecision` retains `recurrence_group_id`, `novelty_signals`,
`track_generation_id`, `provider_generation`, `time_reference_ms`,
`decision_sequence`, `is_override`, and `is_retry` -- enough provenance to explain
why a burst was or was not issued without re-deriving it.

## Interaction with tracker generations

A track generation's own facts (`detector_confirmation_count`,
`tracker_support_count`, lifecycle state) remain exactly what Stage 4/6.1 already
compute; the scheduler does not read or write tracker state. What changes is that
`LiveCameraNodeShadowSession._process_frame` (Stage 5) now asks the scheduler
before requesting a burst instead of consulting only its own
generation-id-seen-before set. A terminal/rejected generation is unaffected and
remains fully visible in tracker/replay diagnostics; the scheduler never touches
`TrackUpdate`, `DetectionObservation`, or shadow-proposal output. A stale burst
result (wrong `provider_generation` or `track_generation_id`) is still discarded
exactly as the Stage 5 contract already requires, before `record_result` is ever
called with `status="captured"` for it -- the scheduler cannot make a stale result
attach to a replacement generation because it never receives one.

## Live wiring

`LiveCameraNodeShadowSession` gains an internal `BurstScheduler` (constructible
explicitly, or defaulted from `stream_id` and the session's existing
`minimum_burst_interval_ms`/`burst_deadline_ms` constructor arguments so existing
callers are unaffected). `_process_frame` builds one `BurstOpportunity` per
"meaningful" `TrackUpdate` (the same strong-confidence-or-confirmed test Stage 5
already applies), calls `scheduler.decide(...)`, issues the existing
`EvidenceBurstRequest` only when `decision.should_issue`, and reports the result
back through `scheduler.record_result(...)`. `LiveShadowStatus` gains
`scheduler_diagnostics`/`scheduler_health` snapshots (see below); every existing
field keeps its prior meaning. Generation change and `stop()` call
`scheduler.reset(...)` alongside the existing tracker/evidence reset.
`temporal_capture_cli._request_validation_burst` (the `--validation-burst` flag)
now routes its one explicit engineering burst through
`scheduler.decide(engineering_validation_request=True)` before calling the
transport, so the CLI's existing engineering-validation mechanism is the same
`engineering_override_issued` path a unit test exercises.

## Historical decision replay

`mockingbird.observation.burst_scheduler_replay` is a pure, deterministic offline
evaluator. `reconstruct_opportunities(manifest, *, session_id)` reads an
already-loaded Stage 6.6/6.8 capture-session-manifest dict (the same shape
`temporal_capture_io.load_capture_manifest` returns), upgrades it through
`temporal_capture.upgrade_capture_manifest_timeline` for reconnect-safe
chronological ordering, and produces one `BurstOpportunity` per retained frame
whose triggers include a real track event and whose active generations have at
least one detection box, ordered by session timeline. `replay_burst_schedule(
manifest, *, session_id, config, annotation)` runs those opportunities through a
fresh `BurstScheduler` in that order and returns a `BurstScheduleReplayReport`:
current (historical) burst/opportunity/track-generation counts read directly from
the manifest, proposed (scheduler) issued/suppressed counts and reason
distribution, recurrence-group summaries, override counts, budget usage, and an
estimated high-resolution-frame/byte reduction.

### Reconstruction limitations (disclosed, not hidden)

The Stage 6.6/6.8 manifest schema records one flat `detection_boxes` list and one
`track_generation_ids` set per retained frame -- it does not record which
detection box belongs to which generation, or which generation a box belongs to.
Reconstructing one opportunity per (frame, generation) pair was tried first and
rejected: it multiplies near-identical opportunities sharing the same
substituted "best box" whenever several generations are simultaneously active on
one frame (routine on a busy real session -- session-02 frequently had 3-7
concurrently active generations per frame), inflating replay volume (1045
reconstructed opportunities, 649 issued even with unbounded budgets) well past
what the live per-generation `TrackUpdate` path would ever raise. `reconstruct_
opportunities` instead reconstructs one opportunity per retained triggering
frame: the frame's single highest-scoring detection box, attributed to one
representative generation (the lexicographically first active on that frame). A
frame whose active generations carry no detection box at all (tracker-support-
only, per `RetainedFrameRecord`'s own contract) is skipped rather than
reconstructed with no geometry, since a geometry-less opportunity can never be
evaluated for recurrence at all and would silently bypass the mechanism this
stage exists to exercise. `broad_class` is reconstructed as `"animal"` for every
opportunity (the manifest does not persist the detector's per-box label;
MegaDetector-family broad classes are `animal`/`person`/`vehicle`, and this
dataset is entirely bird-feeder animal detections). `motion_change_score` is
reconstructed from whether `TRIGGER_MOTION_PROPOSAL_GENERATED` fired on the frame
(`1.0`/`None`, not a continuous score, since the manifest does not retain the
underlying pixel-difference magnitude). `detector_confirmation_count`/
`tracker_support_count` are fixed neutral constants (1/0), not derived from the
frame's own per-frame detection/generation counts -- an earlier attempt at
deriving them from scene busy-ness measurably distorted the stronger-temporal-
support novelty signal (see the module's own limitations for the full,
programmatically-attached list; every replay report carries it verbatim so a
reader cannot mistake this for a live-fidelity replay).

The evaluator never rewrites a historical capture artifact; it only reads already
-written manifest/annotation JSON and writes a new, separate report file.

## Review/evidence reporting

`BurstScheduler.diagnostics()` returns opportunity/issued/suppressed counts, a
suppression-reason distribution, recurrence-group count, operator/engineering
override counts, successful/failed/stale burst counts, median burst latency,
estimated bytes avoided (from an observed running sample of real captured burst
sizes, falling back to a documented default estimate until at least one real
sample exists), an evidence-candidates-retained proxy (one per successful burst,
matching the Stage 5 one-frame-per-burst contract), a count of subjects that were
only ever suppressed and never issued a burst, and a bounded limitations tuple.
Nothing here claims a suppressed subject was uninteresting, and nothing claims an
issued burst was useful -- usefulness is a downstream Stage 6 evidence-scoring and
human-review question this stage does not answer.

## Health reporting

`BurstScheduler.health()` extends read-only shadow health: current active
requests, recent burst rate (issued bursts within the trailing `rate_window_ms` of
source/session-relative time), session budget remaining, active recurrence-group
count, suppression counters, a `degraded` flag (set when burst capability has been
marked unavailable or every recent attempt has failed), Camera Node burst
availability (`mark_burst_unavailable`/`mark_burst_available`, called by a live
caller when the Stage 5 burst capability itself reports unavailable), and the last
sanitized failure code. Calling `health()` or `diagnostics()` starts nothing --
both are pure snapshots of already-recorded state.

## Historical and live acceptance results

Replaying the default configuration against the two real Stage 6.7 sessions
(`python -m mockingbird burst-schedule-replay`):

| | session-01 | session-02 |
| --- | --- | --- |
| current high-resolution bursts | 32 | 123 |
| current track generations | 142 | 379 |
| reconstructed opportunities | 81 | 287 |
| proposed issued | 33 | 50 |
| suppressed as recurring static geometry | 44 | 74 |
| high-resolution frame change | +1 | -73 (-59%) |
| reviewed genuine appearances retained | 1/1 | 4/4 |
| reviewer-attributed operator-marked appearances retained | 0/0 | 3/3 |
| missed-useful-burst risk | none | none |

session-01 is a short (2m37s) session the *old* system's own
`max_high_resolution_frames` cap already truncated at 32 -- not a natural,
uncapped baseline -- so a roughly neutral change there is expected and not a
regression against the critical acceptance requirement, which is scoped to
session-02. session-02 shows a substantial, honestly-measured reduction while
retaining every reviewed genuine and reviewer-attributed operator-marked
appearance. session-02's four real operator markers do not correlate to any
specific frame in the raw manifest (a known, pre-Stage-6.8 data-completeness
gap already documented in session-timeline-contract.md -- the legacy capture
never recorded `host_received_at`); the reviewer's own annotation independently
attributes three "yes" appearances to `truth_source: "operator_marker"` from
direct knowledge of when the marker was raised, which is what
`operator_marked_appearance_*` measures here.

A bounded 90-second real Camera Node mechanics smoke on a live daylight feeder
scene reproduced the same pattern live: 72 real track generations formed, but
only 16 real bursts fired (plus one explicitly labeled engineering-override
validation burst, `engineering_override_issued`), with the product database
SHA-256 and size unchanged before and after and a clean process/GPU shutdown.

## Stage 6.12: late-session evidence-burst fairness and novelty reserve

### Problem, proven

Stage 6.10's representative acceptance campaign found that session-04's richest,
latest, two-simultaneous-bird reviewed appearance (`appearance-C`, 457-551s of a
557s session) received zero live high-resolution bursts; all 17 real bursts landed
in the session's first ~110 seconds. That finding's own root-cause hypothesis
("the recurrence-group's novelty comparison is against a historic floor score...")
was explicitly disclosed as unverified ("strongly implicated, not further
code-instrumented"). Reconstructing the complete decision timeline from the real
session-04 capture through `burst_scheduler_replay` and a fresh `BurstScheduler`
running the exact pre-Stage-6.12 configuration proved a different, more specific
mechanism: **every one of appearance-C's 46 reconstructed opportunities was
rejected with `suppressed_session_budget`, and none of them ever reached
recurrence/novelty evaluation at all**, because the session-budget gate in
`decide()` (`self._issued_count >= hard_cap`) was checked *before*
`_find_or_create_group`/`_evaluate_recurrence` ever ran. The hard cap (56 =
`max_bursts_per_session` 50 + `operator_override_reserved_bursts` 6) was reached
at session-relative offset 439,063ms -- before appearance-C even begins at
457,083ms. A diagnostic replay with only the budget/rate gates lifted (recurrence
and novelty evaluation otherwise untouched) showed 38 of appearance-C's 46
opportunities *would* pass the existing, unmodified novelty rules (mostly
`stronger_confidence`, several via the real operator marker, one via a genuinely
new recurrence group for the second, geometry-divergent bird) -- proving the
recurrence/novelty logic itself was never the defect. The real live capture's own
17-burst, first-110-seconds-only pattern is consistent with the same root
mechanism: `BurstScheduler._issued_count` increments at the moment a burst is
*decided*, not when the Camera Node transport confirms capture, so any live
request failures under this transport's real ~10s reconnect cadence would exhaust
the identical fixed budget using fewer successful captures than attempts; the
exact live decision sequence is not separately persisted in the saved capture
manifest (only successful high-resolution frames are), so this specific figure is
disclosed as consistent with, not independently re-derived from, the proven
mechanism.

The defect is therefore precisely: **a single, undifferentiated, first-come-
first-served session-budget counter, checked before novelty is ever evaluated,
has no mechanism to hold access open for later opportunities -- once early-session
activity (a mix of genuine sightings and many distinct structures' legitimate
first-ever appearances) exhausts it, every later opportunity is rejected
unconditionally regardless of novelty, for the rest of the session, however long
that turns out to be.**

### Safety budget versus fairness allocation

`max_bursts_per_session` and `operator_override_reserved_bursts` remain exactly
as absolute, bounded, and non-renewing as before this stage -- their sizes and
meaning are unchanged, and neither this stage nor any later one may satisfy a
"fix" by simply raising them (that would spend more resources rather than
allocate the existing budget more fairly, and would re-hide starvation instead of
fixing it). `max_concurrent_requests`, `max_bursts_per_minute`/`rate_window_ms`,
Camera Node burst-capability availability
(`mark_burst_unavailable`/`mark_burst_available`), and stale-generation/result
safety are also entirely unchanged and still apply unconditionally, including to
every fairness-reserve issuance. What changes is *when*, relative to those
checks, recurrence/novelty evaluation runs (now always, not short-circuited by
early budget exhaustion) and that one small, additional, explicitly bounded
allocation -- the novelty reserve -- exists for opportunities the unmodified
recurrence/novelty logic has already proven are not a suppressible recurrence.

### Reordered decision flow

`decide()` now evaluates recurrence/novelty (`_find_or_create_group`,
`_evaluate_recurrence`) unconditionally once the concurrency/rate/cooldown gates
pass, *before* any budget check. This changes only *when* a recurring, non-novel
opportunity is rejected relative to the budget/reserve checks below it -- never
*whether*: `_evaluate_recurrence` itself, its geometry thresholds, and its
score/support-floor comparisons are byte-for-byte unmodified. A beneficial side
effect: recurrence-group bookkeeping (`occurrence_count`, `score_floor`,
`support_floor`, `last_seen_offset_ms`) now keeps updating for the rest of the
session instead of freezing once the ordinary budget is exhausted, resolving a
previously disclosed replay limitation.

Only once an opportunity has been proven not a suppressible recurrence does the
scheduler decide which bounded pool of capacity it draws from:

- **Ordinary** (`max_bursts_per_session`, unchanged, absolute): the default path
  for any non-override opportunity while `issued_count < max_bursts_per_session`.
- **Override** (`operator_override_reserved_bursts`, unchanged, absolute): the
  default path for an operator-marked or engineering-validation opportunity while
  `issued_count < max_bursts_per_session + operator_override_reserved_bursts`.
- **Novelty reserve** (new, bounded, replenishing): once its own channel above is
  exhausted, a non-engineering opportunity that has already been proven
  materially novel (a genuine recurrence-novelty escape, a brand-new recurrence
  group, or a geometry-less opportunity, exactly the existing set of
  "not-suppressed" cases) may draw from `novelty_reserve_capacity` per rolling
  `novelty_reserve_window_ms` of session-relative time. An operator wildlife
  marker whose own dedicated override allowance is *also* exhausted may fall back
  to this same reserve -- proven necessary by real session-04 data, where the
  6-slot dedicated override reserve was itself fully consumed (by earlier,
  legitimately marker-correlated frames) before the session's own operator-marked
  appearance-C frames arrived. An engineering-validation request never falls back
  to the reserve; it remains a deliberately narrow, one-off validation mechanism
  bounded only by its own dedicated allowance, unchanged from Stage 6.9.

A recurring, non-novel opportunity is rejected by `_evaluate_recurrence` before
any of the above is ever reached, so it can never consume the reserve no matter
how many arrive or how late in the session they do. `DECISION_NOVELTY_RESERVE_ISSUED`
is a distinct, explicitly labeled outcome (never silently folded into
`DECISION_BURST_ISSUED` or `DECISION_OPERATOR_OVERRIDE_ISSUED`, even when an
operator marker is the reason a reserve slot was used) so a reviewer can always
tell which pool actually paid for a given burst.
`DECISION_SUPPRESSED_NOVELTY_RESERVE_EXHAUSTED` is a distinct suppression reason
for "this opportunity was proven materially novel, but every channel -- ordinary,
override, and reserve -- is currently out of capacity," kept separate from the
older, less specific `DECISION_SUPPRESSED_SESSION_BUDGET` (an override channel
exhausted with no reserve fallback available, or the pre-Stage-6.12 generic case).
`BurstSchedulerDiagnostics.novelty_reserve_issued` and
`BurstSchedulerHealth.novelty_reserve_remaining` report the reserve channel
separately from `operator_overrides`/`engineering_overrides`/`session_budget_remaining`;
the four issuance counters (`operator_overrides`, `engineering_overrides`,
`novelty_reserve_issued`, and ordinary/retry issuance) partition `issued_count`
with no double-count.

### Why a rolling reserve, not a bigger one-shot allowance

The reserve is a small, bounded *rate* (capacity per rolling window), the same
shape already established by `max_bursts_per_minute`/`rate_window_ms`, rather
than a larger fixed one-shot addition to `max_bursts_per_session`. A fixed
one-shot addition degenerates to the same failure this stage fixes for any
session long enough to exhaust it too (merely later) and would require guessing a
size large enough for an unknown future session duration -- exactly what "do not
reserve capacity based on knowing the session's final duration" rules out. A
rolling rate, by contrast, behaves identically at every point in a session
regardless of how long it has already run or will continue to run, needs no
duration parameter, and "unused reserve expires or returns" is simply what the
rolling window already does: a reserve token used at time T becomes available
again at T + `novelty_reserve_window_ms`. Because recurring/non-novel
opportunities can never reach it at all, and `novelty_reserve_capacity` (8) per
`novelty_reserve_window_ms` (120s) is a materially smaller steady-state rate than
`max_bursts_per_minute` (30/min) -- which still applies on top of it for every
non-override issuance, reserve included -- the reserve can never itself become a
burst-storm safety concern.

### Historical acceptance (Stage 6.9 baseline vs Stage 6.12 candidate)

Replayed with `python -m mockingbird burst-schedule-replay` (Stage 6.9 baseline =
identical code with `novelty_reserve_capacity=0`, which reproduces the exact
pre-Stage-6.12 issued/suppressed counts byte-for-byte; Stage 6.12 candidate =
unchanged defaults):

| | session-01 | session-02 | session-03 | session-04 |
| --- | --- | --- | --- | --- |
| reconstructed opportunities | 81 | 287 | 306 | 266 |
| issued, Stage 6.9 baseline | 33 | 50 | 56 | 56 |
| issued, Stage 6.12 candidate | 33 | 66 | 68 | 64 |
| of which via novelty reserve | 0 | 16 | 18 | 8 |
| suppressed as recurring geometry, baseline | 44 | 74 | 110 | 154 |
| suppressed as recurring geometry, Stage 6.12 | 44 | 98 | 173 | 166 |
| genuine appearances retained, baseline | 1/1 | 4/4 | 2/2 | **2/3** |
| genuine appearances retained, Stage 6.12 | 1/1 | 4/4 | 2/2 | **3/3** |
| operator-marked appearances retained, baseline | 0/0 | 3/3 | 0/0 | 1/1 |
| operator-marked appearances retained, Stage 6.12 | 0/0 | 3/3 | 0/0 | 1/1 |
| longest gap with opportunities but no issued burst | 13.2s | 247.3s → 108.9s | 153.0s → 84.6s | 112.0s → 83.6s |

session-01 never exhausts its ordinary budget (33 of 50 used), so the reserve
never activates and its behavior is byte-identical to the Stage 6.9 baseline --
the intended, inert-when-unneeded property. session-02 and session-03 already
retained every reviewed appearance under the Stage 6.9 baseline; Stage 6.12 does
not change that outcome, but measurably improves temporal distribution (longest
starved interval roughly halved in both) and, as a side effect of recurrence
bookkeeping no longer freezing at budget exhaustion, *increases* recurring-
geometry suppression accuracy rather than reducing it. session-04 is the proven
fix: `appearance-C` moves from zero issued bursts to burst-eligible, without
regressing `appearance-A`/`appearance-B`'s already-correct retention, and without
approaching anything resembling the pre-Stage-6.9 123-burst/379-generation
volume (issued count moves from 56 to 64 of 266 reconstructed opportunities, an
8-burst, reserve-attributed increase, not a cap increase).

### Reviewed wildlife detail (session-04)

| Appearance | Opportunity existed | Burst issued (baseline) | Burst issued (Stage 6.12) | Suppressing reason (Stage 6.12) | Operator marker |
| --- | --- | --- | --- | --- | --- |
| `session-04-appearance-A` | yes | yes | yes | `suppressed_same_track_generation`/`suppressed_recurring_geometry` on other frames in span | no |
| `session-04-appearance-B` | yes | yes | yes | `suppressed_recurring_geometry` on other frames in span only (no longer `suppressed_session_budget`) | yes |
| `session-04-appearance-C` | yes | **no** | **yes** | `suppressed_recurring_geometry`/`suppressed_novelty_reserve_exhausted`/`suppressed_session_budget` on the frames that did not draw the bounded reserve | yes |

Every appearance's *span* still contains individual frames that remain correctly
suppressed (recurring geometry, or the reserve's own bounded capacity already
spent within its rolling window) -- retention is scored, as in Stage 6.9, at the
appearance level (did *any* frame in the reviewed span receive a burst), not by
expecting every reviewed-positive frame of a multi-second visit to receive its
own.

### Multi-subject handling (verified, not newly built)

session-04's directly reviewed two-simultaneous-bird frame
(`e69670e61cf3...`, 547,959ms) has one box confidently identified near a
red-glass feeder structure (`[0.503, 0.558, 0.557, 0.611]`, score 0.792) and a
second, lower-confidence box at the long-recurring feeder-perch location
(`[0.445, 0.591, 0.472, 0.631]`, score 0.579) that IoU/centroid-matches the
session's own dominant recurring group. Reconstructing this frame's opportunity
(the single highest-scoring box, per `reconstruct_opportunities`'s existing,
documented one-opportunity-per-frame limitation) and replaying it confirms the
existing, *unmodified* `_matches`/`_find_or_create_group` geometry test already
starts a brand-new recurrence group for the first box rather than folding it into
the second box's long-established, suppressed group, purely from IoU/centroid/
size-ratio geometry -- no species identity, no hard-coded feeder coordinates, and
no new multi-object detector/tracker feature were added or needed. The scorable
opportunity stream's own known limitation (one reconstructed opportunity per
retained frame, not one per simultaneously active generation) means the second,
lower-scoring bird's own opportunity is invisible to this *offline replay
reconstruction* specifically -- the live per-generation `TrackUpdate` path in
`camera_node_live.py` does not share this limitation, since it already builds one
`BurstOpportunity` per meaningful generation, independently. This is disclosed
here, not hidden: the offline replay tool's reconstruction fidelity for
simultaneous multi-subject frames remains bounded by a pre-existing, unrelated
limitation this stage does not change.

### Hardware-free coverage

`tests/test_burst_scheduler.py` adds a dedicated Stage 6.12 section (early static
recurrence cannot consume reserve capacity; low-novelty recurrence never draws
it; the ordinary and override budgets remain absolute even with the reserve
enabled; the rate budget still bounds reserve issuance; a novel opportunity uses
the reserve once ordinary allocation is exhausted; an operator marker whose own
override allowance is exhausted falls back to the reserve; an engineering
override never does; the reserve requires no known session duration; its rolling
state is deterministic and session-relative-time-driven, never wall-clock; a
distilled synthetic reproduction of the exact session-04 starvation mechanism is
fixed; a genuine late opportunity is not suppressed solely for arriving late; an
ordinary late repeat with no novelty signal remains suppressed; two simultaneous,
geometry-divergent same-class opportunities remain independently eligible; reset
clears reserve state for every reset reason; a benign reconnect -- no `reset()`
call at all -- leaves it intact) alongside the unmodified Stage 6.9 suite, all of
which continues to pass. `tests/test_burst_scheduler_replay.py` adds a matching
"rescued by reserve" case beside the pre-existing "genuinely starved, reserve
disabled" one, and fixes a latent replay-reporting bug this stage surfaced: the
evaluator's own `_ISSUING_OUTCOMES` was a hand-maintained duplicate of the
scheduler's `ISSUING_DECISIONS` that had silently omitted the new outcome (now a
direct import, structurally unable to drift again).

## Hard non-goals

No Stage 7 proposal authority, no detector threshold or model change, no tracker
confirmation-policy change, no automatic Ignore region, no species inference, no
evidence-scoring redesign, no Camera Node transport replacement, no persistent
burst history, no product migration, and no Dashboard/admin UI. The scheduler
controls temporary high-resolution capture timing only; it never alters detector,
tracker, or shadow-proposal output.
