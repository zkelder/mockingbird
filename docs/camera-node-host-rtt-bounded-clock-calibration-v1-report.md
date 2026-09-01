# Camera Node <-> Host RTT-Bounded Clock Calibration v1

RELEASE-CRITICAL Gate A measurement-correctness milestone. Does not reopen
fragmentation accounting, does not optimize pipeline latency, does not run
a wildlife field cohort, does not change detector/model behavior. Closes
the gap the accepted Camera Node -> Host Clock Normalization v1 disclosed
but did not solve: its one-way estimator (`received_at_host -
captured_at_node`) equals `true_clock_offset + unknown_one_way_transport_
delay`, and therefore `offset_ms = min(deltas)` is only ever a one-sided
upper bound on the true offset -- never a defensible two-sided error
bound, however tight its own observed jitter spread looks.

## Starting state

Verified before touching anything: branch `main`, HEAD `d25134b` (the
reconciliation commit accepting Camera Node -> Host Clock Normalization
v1 -- matches `git rev-parse HEAD` and `release-execution-state.md` §1's
own "Accepted HEAD" field). Schema `v58`, confirmed unchanged by this
milestone throughout (nothing here is persisted to SQLAlchemy -- every new
type is a pure dataclass in `clock_calibration.py`/`counterfactual_
lineage.py`, or an additive Pydantic response field). `git status
--porcelain` at the start showed exactly the seven preserved untracked
detector files (`docs/wildlife-detector-training-contract.md.orig`,
`scripts/evaluate_small_bird_detector.py`, `scripts/materialize_wildlife_
stage2.py.orig`, `scripts/train_wildlife_stage2_rfdetr.py.orig`, `src/
mockingbird/detectors/small_bird_benchmark.py`, `src/mockingbird/
training/wildlife.py.orig`, `tests/test_small_bird_benchmark.py`),
untouched throughout this milestone and re-verified byte-identical at
close. No active writer process was found (`git status` showed no other
in-progress changes; no `.git/index.lock`). `git log origin/main..HEAD`
confirmed 278 local, unpushed commits -- no push performed, matching this
milestone's own explicit instruction. Every "Expected" starting-state fact
this milestone's own governing brief named (Gate A/Lane R open,
fragmentation READY FOR FORMAL BUDGET REVIEW, clock-domain provenance/
drift/jump-detection/normalization-instrumentation closed, absolute Node
<-> Host offset/error bound OPEN, true capture-to-visible latency not yet
release-budget valid, authorization NONE, not pushed) was independently
confirmed against `docs/release-execution-state.md` §1/§3 before any edit.

## Existing protocol investigation

Read in full before designing anything, per this milestone's own explicit
"determine whether the existing Camera Node connection already has a
request/response operation suitable for calibration" (§5):

- `GET /node/v1/health` (`mockingbird_node/app.py`) -- a genuine, existing,
  synchronous request/response operation, requiring no pairing credential
  (`require_pairing` is not applied to this route). Before this milestone
  it returned `service_started_at` (a one-time absolute stamp, fixed for
  the process lifetime), `boot_id`, and monotonic `os_uptime_seconds`/
  `service_uptime_seconds` -- **never the Node's own current wall-clock
  time as of the response**. This is the exact gap this milestone closes.
- `POST /node/v1/pair`, `GET /node/v1/capabilities`, `GET /node/v1/
  cameras` -- all request/response, but one-shot pairing/metadata calls,
  never repeated during a live session; unsuitable for periodic
  calibration.
- `GET /node/v1/cameras/{id}/snapshot`, `POST /node/v1/cameras/{id}/
  capture` -- request/response, but each triggers a real camera capture
  (expensive, disruptive to run every few minutes purely for clock
  calibration) and requires a pairing credential.
- `GET /node/v1/transport/status` -- request/response, requires pairing,
  reports transport-layer facts, not designed to carry a fresh Node
  timestamp.
- `GET /node/v1/cameras/{id}/analysis-stream` -- **not** request/response;
  a one-way, long-lived multipart-JPEG push (the Node captures and
  streams; the Host never round-trips a request against it). Correctly
  identified as such by the accepted prior milestone.
- Host-side: `CameraNodeClient.health(base_address)` already exists as
  the request-side counterpart, and is called exactly once today, at
  pairing-precheck time (`POST /api/camera-nodes/pair` in `api/main.py`)
  -- never periodically during a live session.

**Decision (per this milestone's own explicit preference, §5): reuse `GET
/node/v1/health`, adding two additive response fields, rather than
inventing a dedicated time-sync protocol.** `node_receive_time` (sampled
at the very top of the handler, before any work -- `Nrecv`) and
`node_time` (sampled immediately before the response dict is returned --
`Nsend`/`N1`) were added; every pre-existing field is unchanged, so an old
Host client parsing this response is unaffected, and an old Node's
response simply lacks both new keys (see "Compatibility," below).

**Correction, disclosed rather than silently fixed:** the accepted prior
milestone's own module docstring in `clock_calibration.py` ("Why not a
textbook NTP round trip") stated "the Camera Node analysis-stream protocol
has no [request/response] exchange" -- correct for the analysis stream
specifically, but implicitly generalized (there, and in `docs/camera-node
-live-shadow-contract.md`) to "no round trip exists anywhere in the Camera
Node protocol," which does not hold. Both documents are corrected in place
in this milestone (see their own new sections) rather than silently
superseded, matching this codebase's own established practice of
disclosing a correction to a prior claim instead of quietly overwriting
it.

## Why one-way mapping was insufficient

Re-derived directly, not merely re-asserted: for one delivered analysis
-stream frame, `delta_ms = received_at - captured_at = true_offset_ms +
one_way_transit_ms`, and `one_way_transit_ms >= 0` always (a frame cannot
arrive before it is sent). Therefore `true_offset_ms <= min(deltas)`
always holds -- but there is no corresponding *lower* bound derivable from
one-way samples alone; `one_way_transit_ms` could in principle be
arbitrarily close to zero, so `min(deltas)` could already equal (or sit
arbitrarily close to) the true offset, or could still carry meaningful
transit-delay contamination -- one-way observation alone cannot
distinguish these cases. `uncertainty_ms = max(deltas) - min(deltas)` (the
accepted prior milestone's own honest disclosure) is a *quality* signal
(how much worse the other samples were), never a defensible two-sided
error bound on `min(deltas)` itself. A product that needs to say "the true
offset lies within this bounded interval, with this much justified
confidence" cannot get that from a one-way estimator at any jitter
tightness -- this is a structural limitation of the measurement shape, not
a tuning problem.

## Calibration exchange

`CameraNodeClient.sample_clock_round_trip(base_address, *, clock=None)`
(new method, `source_providers/camera_node.py`) performs one bracketed
measurement: `host_send_at = clock()` immediately before dispatch, the
existing `_request(base_address=..., path="/node/v1/health")` call
(unmodified), then `host_receive_at = clock()` immediately on receipt.
`node_receive_time`/`node_response_time` are parsed from the response body
via a new `_parse_node_timestamp` helper (`datetime.fromisoformat`,
rejecting anything that is not a genuine tz-aware timestamp -- never a
guess, never a crash). No pairing credential is sent or required, mirroring
`health()` itself. Returns a new `CameraNodeRoundTripSample` dataclass
(plain data; deliberately does *not* import from `observation.clock_
calibration`, preserving this codebase's existing `observation ->
source_providers` dependency direction rather than reversing it -- a
caller with both types converts).

A live session (`engine_runtime._EngineSession._perform_rtt_clock_
calibration`) collects a batch of 5 (`_RTT_CALIBRATION_BATCH_SIZE`)
such round trips **concurrently** (`asyncio.gather(..., return_
exceptions=True)` over `asyncio.to_thread(...)` calls -- verified
thread-safe: `UrlLibCameraNodeRequester` holds no shared mutable state,
constructing a fresh `HTTPConnection`/`HTTPSConnection` per call), converts
each surviving sample into a `clock_calibration.RttRoundTrip`, and calls
`CounterfactualLedger.record_rtt_clock_calibration(...)` -- the RTT-bounded
sibling of the accepted `record_clock_calibration`, same jump-comparison
pattern, same bounded ledger shape (a new `_BoundedOffsetLedger`, capacity
100 -- see "Drift / recalibration," below, for the sizing rationale).

**A real regression found and fixed during this milestone's own testing:**
the first implementation ran the batch's 5 attempts *sequentially*. Against
an unreachable Node, this cost `batch_size * NODE_CONNECT_TIMEOUT_SECONDS`
(5 x 2.0s = 10s) of real wall-clock delay, discovered when it caused a real
end-to-end fixture test (`test_end_to_end_creates_one_candidate_and_
activates_authority`) to time out -- the RTT batch, run once (unguarded)
before the main frame-processing loop even started, ate the test's entire
10-second budget. Fixed two ways: (1) the batch's own attempts now run
concurrently, bounding worst-case latency to roughly one connect timeout
regardless of batch size; (2) the "session start" trigger was redesigned
to not require a separate, loop-blocking call at all -- `_last_rtt_
calibration_tick is None` (never yet recalibrated) is itself one of the
four recalibration triggers evaluated at the first ordinary ~10-second
tick, so the very first calibration attempt happens *inside* the already
-async tick loop, concurrently with ordinary frame processing, never
gating frame capture on Node-health-request latency -- consistent with
this codebase's own established capture-first backpressure priority
(`roadmap.md` "Gate A").

## Timestamp semantics

**Node-side** (`mockingbird_node/app.py`): `node_receive_time` is sampled
literally as the first statement inside the `health()` handler, before
`provider.cameras()` (camera enumeration) runs; `node_time` is sampled
immediately before the response dict is constructed and returned. The gap
between them is this handler's own real processing time (camera
enumeration), preserved for the four-timestamp form rather than discarded
(this milestone's own §8 "avoid a timestamp generated far before network
send without accounting for processing delay"). Both use `datetime.
now(UTC)`, the same canonical read every other Node timestamp in this
codebase already uses.

**Host-side** (`CameraNodeClient.sample_clock_round_trip`): `host_send_at`
is read immediately before `self._request(...)` dispatches; `host_
receive_at` immediately after it returns. No unrelated application
processing sits inside that bracket. The `clock` parameter defaults to
`datetime.now(UTC)` and accepts an injected callable, mirroring `_Engine
Session`'s own established `clock=` convention (`engine_runtime.py`), so
the live session passes its own `self._clock` -- the same canonical clock
every other Host-domain timestamp in this session already uses -- making
the whole exchange deterministically testable without a real wall-clock
wait.

## Offset interval derivation

Documented in full in `clock_calibration.py`'s own docstring ("Camera Node
<-> Host RTT-Bounded Clock Calibration v1" / "The interval bound"); the
core argument, restated here:

Let `true_offset_ms` be the value such that `host_time = node_time +
true_offset_ms` at the same real instant (the same sign convention the
accepted one-way estimator already uses). Two honest, one-directional
consequences of "a request/response can only travel forward in time"
(never an assumption of symmetric transit delay -- this milestone's own
explicit "do not blindly copy NTP formulas if transport semantics
differ"):

- The request cannot have reached the Node before it left the Host:
  `true_offset_ms >= host_send_at - node_receive_at`.
- The response cannot have reached the Host before the Node sent it:
  `true_offset_ms <= host_receive_at - node_response_at`.

So `[host_send_at - node_receive_at, host_receive_at - node_response_at]`
is a rigorously justified two-sided bound. In the two-timestamp form
(`node_receive_at` unavailable, defaults to `node_response_at`), this
reduces exactly to `[H0, H1] - N1`, width `RTT`, radius `RTT/2` -- matching
the governing brief's own preferred floor exactly. In the four-timestamp
form, the width is `RTT - node_processing_ms` -- strictly tighter by
exactly the Node's own disclosed processing time, a genuine, non
-fabricated refinement (proven, not merely asserted --
`test_rtt_calibration_four_timestamp_form_tightens_using_node_processing_
time` constructs an identical-RTT (202ms) pair, one two-timestamp and one
four-timestamp, and asserts `101.0` vs `1.0`ms uncertainty respectively).
The reported point estimate (`offset_ms`) is this interval's own midpoint
-- reported for convenience and API/field-name continuity with the prior
milestone, **never represented as exact** (every docstring, every field
comment, and this milestone's own governing brief's own explicit
instruction agree on this).

This is *not* the classical NTP symmetric-delay offset formula (which
would assume `one_way_out ~= one_way_back` and derive a single point plus
a separately-modeled delay term); it is a strictly weaker, honest
inequality that holds regardless of transit-delay asymmetry -- see
"Asymmetry limitation," below.

## RTT / uncertainty model

`uncertainty_ms` is the interval's own half-width (radius) -- at minimum
`RTT/2` (two-timestamp form), tighter when Node processing time is known.
Never conflated with the one-way estimator's own jitter-spread quality
signal, which remains a distinct, unrelated number on a distinct record
type.

**Quality gating** (this milestone's own §14, disclosed as engineering
bounds, not release budgets): `DEFAULT_MAX_ACCEPTABLE_RTT_MS = 1000.0` --
every real deployment is LAN-local (product-doctrine.md; this milestone's
own explicit Local Only requirement), so an ordinary round trip to a
Raspberry Pi Camera Node is expected in the single-digit milliseconds; 1
second is generously wide of that (absorbing real scheduling jitter/GC
pauses on a Pi) while still rejecting a genuinely wedged Node or saturated
network path. A sample whose own measured RTT exceeds this ceiling is
excluded from the batch *before* the intersection step -- never blended
into a falsely precise combined estimate (this milestone's own explicit
"do not average high-RTT samples into a falsely precise estimate"; proven
by `test_rtt_calibration_high_rtt_samples_are_excluded_never_averaged_in`).
`MINIMUM_RTT_CALIBRATION_SAMPLES = 3` -- the governing brief's own "3-7
samples" lower bound; fewer surviving samples produces a real, auditable
`state="insufficient_samples"` record, never a fabricated number (mirrors
the accepted one-way estimator's own `MINIMUM_CALIBRATION_SAMPLES`
precedent exactly). Both are disclosed, deliberate judgment calls in the
module's own docstring, changeable if real field evidence ever calls for
different limits -- explicitly not claimed as derived or as release
budgets.

## Multi-sample selection

A batch's combined interval is the **intersection** of every RTT-filtered
valid sample's own interval: `combined_min = max(sample mins)`,
`combined_max = min(sample maxes)` -- a rigorous, generally-tighter bound
than any single sample alone, since the same true offset must satisfy
every sample's own inequality simultaneously over a short, back-to-back
batch (proven: `test_rtt_calibration_multiple_samples_intersection_
tightens_the_bound`). If the survivors' own intervals do not overlap at
all (`combined_min > combined_max`) -- which subsumes detecting a clock
jump *during* the batch itself, since a genuine mid-batch jump is exactly
what produces mutually-inconsistent per-sample intervals, with no second,
redundant jump-during-batch mechanism needed -- the batch honestly reports
`state="inconsistent_samples"`, distinct from `insufficient_samples`,
never silently resolved by picking one sample's interval over another's
(proven: `test_rtt_calibration_inconsistent_samples_do_not_overlap`, which
simulates exactly this by constructing two sub-batches 30 seconds apart
with a deliberate 30-second offset shift between them). The single
lowest-RTT survivor is separately reported (`rtt_ms`/`node_processing_ms`)
as the calibration's own "best sample," for diagnostics -- proven not to
be an average across the batch (`test_rtt_calibration_reports_the_lowest_
rtt_sample_never_an_average`).

## Drift / recalibration

The accepted one-way per-frame estimator is **not discarded** (this
milestone's own explicit instruction) -- it is entirely unchanged in
`clock_calibration.py` (all 26 of its own pre-existing tests pass
byte-for-byte unmodified) and continues to be fed by `_EngineSession`'s
own ~10-second per-tick loop exactly as before. Its role changes,
disclosed explicitly in its own module docstring ("Composing with the
one-way per-frame monitor"): it no longer feeds `capture_to_visible_
latency.py`'s T0 normalization at all (a one-sided bound can never
honestly become a defensible two-sided one no matter how it is consumed
downstream) -- its new and only role is cheap, frequent *relative*
drift/jump monitoring that decides *when* a live session should spend the
cost of a fresh, more expensive RTT-bounded batch.

Combined model, exactly as this milestone's own §15/§16 describe: the
RTT-bounded anchor is the bounded absolute anchor; the one-way monitor is
the ongoing relative monitoring layer that feeds one of the RTT anchor's
own recalibration triggers. `_rtt_recalibration_due` (new, pure, directly
unit-tested `_EngineSession` method -- extracted specifically so the
decision logic is testable without a live loop) is the single decision
point for all four triggers:

1. **Session start**: `self._last_rtt_calibration_tick is None` -- true
   only before this session's very first ordinary tick.
2. **Bounded periodic cadence**: `_RTT_RECALIBRATION_INTERVAL_SECONDS =
   300.0` (5 minutes) -- a disclosed, deliberate judgment call (this
   milestone's own §17 "do not run a network calibration per frame";
   comfortably bounds drift-induced error between refreshes while adding
   at most five tiny LAN requests every five minutes, negligible against
   the analysis stream's own steady ~10-second HTTP cadence). Not derived
   from a measured real-world drift rate -- none has been field-measured
   yet (see "Remaining field proof," below); changeable if real evidence
   calls for a different cadence.
3. **Reconnect**: `AnalysisSourceStatus.transport_reconnect_count`
   (already computed, previously unread by `_EngineSession`) changed since
   the last RTT batch.
4. **One-way jump**: the one-way monitor's own `_refresh_clock_
   calibration` (now returning its own recorded sample rather than
   discarding it) reports `clock_jump_detected=True` this tick.

The RTT ledger's own retention bound (`max_rtt_clock_calibration_records
= 100`, new field on `CounterfactualRetentionConfig`) is sized with the
same generous-headroom rationale as every sibling cap in that class: RTT
batches are far rarer than one-way per-tick entries (session start,
~5-minute cadence, occasional reconnect/jump), so 100 comfortably exceeds
any real bounded session's own count.

## Clock-jump behavior

Re-proves the accepted epoch model at the RTT-anchor level, not only the
one-way level. `active_rtt_calibration_for_offset` is the RTT-bounded
sibling of the accepted `active_calibration_for_offset` -- both now
delegate to one shared, generic `_select_governing_calibration` helper
(a genuine internal refactor, not a behavior change: `active_calibration_
for_offset`'s own 26 pre-existing tests continue to pass unmodified,
proving the refactor is behavior-preserving), so the exact same
epoch-boundary/no-backward-extrapolation guarantees apply to both
calibration methods without duplicating the algorithm twice. `detect_
clock_jump`/`compute_drift` were relaxed from `ClockCalibrationRecord`
-specific type hints to a small structural `_CalibrationSample` protocol
(both record types share the `state`/`offset_ms`/`calibrated_at`
attributes those two functions need) -- reused unchanged for RTT records,
proven directly (`test_detect_clock_jump_and_compute_drift_are_reused_
for_rtt_records`).

Deterministic scenario re-proved end to end (this milestone's own §27):
`test_active_rtt_calibration_for_offset_honors_clock_jump_boundaries`
constructs a valid pre-jump RTT anchor, a post-jump RTT anchor flagged
`clock_jump_detected=True`, and confirms an offset at or after the jump
never resolves to the pre-jump anchor (and vice versa) -- old anchor
invalidated for post-jump offsets, new RTT-bounded calibration restores
validity, exactly this milestone's own required scenario.

## Reconnect behavior

After a detected reconnect, the live session does **not** blindly reuse
the prior calibration's own *cadence* -- the reconnect trigger above forces
a fresh RTT batch at the very next tick, regardless of how recently the
last one ran. Whether that fresh batch actually creates a new *epoch*
(invalidating the pre-reconnect anchor) is governed by `detect_clock_jump`
comparing the new batch's own offset against the immediately-preceding
one: an ordinary benign network-level reconnect that did not change the
Node's actual clock relationship correctly produces a near-identical
offset and **no** epoch boundary (the old anchor remains validly usable
for the offsets it always covered -- forcibly invalidating a still-correct
calibration would itself be dishonest); a reconnect that *did* coincide
with a real clock change (a Node reboot without a battery-backed RTC, a
manual clock correction) produces a materially different offset, which
`detect_clock_jump` correctly flags, creating a new epoch the old anchor
cannot bridge into. This composes the two concerns this milestone's own
§18 asks for ("obtain a new bounded sample" and "start a new clock epoch
if needed") without conflating them into one unconditional invalidation.

**Disclosed, bounded limitation:** between the instant of reconnect and
the completed post-reconnect RTT batch (bounded to roughly one connect
-timeout window, given the concurrent-attempt fix above), any T0 in that
narrow gap is still governed by whichever calibration the epoch model
already selects for it -- if the clock genuinely changed inside that exact
window, honest detection is delayed until the fresh batch completes, not
instantaneous. This is not a new class of limitation this milestone
introduces; it is the same inherent latency any periodic/reactive (rather
than continuous) calibration scheme has, already present in the accepted
one-way monitor's own ~10-second tick-driven jump detection.

## Latency interval computation

`capture_to_visible_latency.py`'s `build_latency_samples` now takes
`rtt_calibrations: Sequence[RttClockCalibrationRecord]` -- **replacing**
(deliberately renamed, not silently retyped) the prior `clock_
calibrations: Sequence[ClockCalibrationRecord]` parameter, so every
existing caller must consciously migrate rather than risk a confusingly
-wrong-shaped argument passing type-checking by name alone. `LatencySample`
gains `t0_captured_at_normalized_min`/`_max`, `clock_offset_min_ms`/
`_max_ms`, `latency_min_ms`/`_max_ms` -- additive fields alongside the
existing point-estimate fields (`t0_captured_at_normalized`, `clock_
offset_ms`, `latency_ms`), never collapsing the interval into the point
estimate alone (this milestone's own explicit §21).

**The inversion, gotten right and directly tested:** latency is `decided_
at - t0`, a *decreasing* function of t0 -- so the *earliest* possible
normalized t0 (`t0_captured_at_normalized_min`) yields the *largest*
possible latency (`latency_max_ms`), and the *latest* possible t0 yields
the *smallest* possible latency (`latency_min_ms`). Verified at two
layers: the isolated `clock_calibration.py` unit test (`test_normalize_
capture_time_with_bound_direction_is_not_inverted`) and the full
end-to-end `capture_to_visible_latency.py` pipeline (`test_cross_domain_
valid_calibration_produces_measured_latency_from_normalized_t0`'s own
`latency_max_ms == latency_ms + 20.0` / `latency_min_ms == latency_ms -
20.0` assertions, derived independently from the test's own input values,
not merely "it runs").

**Impossible-result policy (this milestone's own explicit §22), applied
honestly, not defensively-overbroad:** only `latency_max_ms < 0`
(impossible even under the single most charitable -- fastest-t0 --
reading) is rejected as `invalid_negative`; only `latency_min_ms >
max_plausible_latency_ms` (still implausible even under the most
charitable -- latest-t0 -- reading) is rejected as `implausible`. A
sample whose interval merely *straddles* zero (a negative lower bound,
non-negative upper bound) is **not** impossible -- it is an honestly
wide-but-plausible measurement, reported as `measured` with its true
(possibly negative) bounds intact, never clamped (`test_cross_domain_
interval_straddling_zero_is_still_measured_honestly` proves this
distinction concretely: `latency_min_ms == -100.0`, unclamped, alongside
`state == "measured"`). This reuses all five existing `LatencyState`
values with generalized, interval-aware semantics -- zero new states
introduced, minimizing new vocabulary.

`LatencySummary` gains `mean_uncertainty_ms` (mean per-sample interval
half-width across `measured, normalized` samples) and bumps its own
internal `schema_version` 2 -> 3 (a dataclass-shape marker, unrelated to
and never confused with the database's own `v58`) -- a single number for
"how tight was calibration across this whole window," per this
milestone's own §23 reporting requirement, without requiring a reader to
inspect every sample individually.

## Fallback result

Re-proved directly against the exact discriminating scenario this
milestone's own §24 names: winner fails at the evidence-availability gate,
fallback member (a different generation, a different `source_offset_ms`)
is admitted instead, and a clock jump separates the winner's own epoch
from the fallback's own epoch. `test_fallback_latency_after_clock_
normalization_uses_the_admitted_members_own_capture_time_not_the_failed_
winners` (migrated from the accepted one-way test, same discriminating
shape, same wrong-vs-right numbers: 18s from the wrong epoch vs. the
correct 11s) now additionally asserts the *interval* too (`clock_offset_
min_ms == 8_980.0`, `clock_offset_max_ms == 9_020.0`, `latency_max_ms ==
11_020.0`, `latency_min_ms == 10_980.0`) -- a bug that silently selected
the winner's own epoch would produce a materially different interval too
(centered near 18s), not merely a different point estimate, per this
milestone's own explicit "produces the fallback member's latency
interval."

## Stop-finalization result

`test_stop_finalized_candidate_still_normalizes_correctly_under_clock_
calibration` re-proves a proposal resolved only at session stop (after
`blocked_continuation_pending` for minutes) still normalizes from its own
true first-capture time via its own governing RTT-bounded calibration,
unaffected by *when* the decision was finally reached -- no special
-casing exists or is needed, mirroring the accepted, unmodified stop
-finalization proof in `test_engine_runtime.py`. Now additionally asserts
the interval (`latency_min_ms == 176_980.0`, `latency_max_ms ==
177_020.0`), per this milestone's own explicit "latency interval reflects
the real wait."

## Multi-subject result

`test_multi_subject_siblings_each_get_their_own_correctly_normalized_
capture_time` re-proves two concurrent sibling proposals (a feeder subject
and a perch subject, 2 seconds apart, sharing one stream's RTT calibration
-- this milestone's own §26 "same stream calibration where appropriate")
each retain their own correctly-normalized capture time and, now, their
own correctly-shifted, independent latency *interval* -- `visit-feeder`'s
own `[4_980.0, 5_020.0]` and `visit-perch`'s own `[5_980.0, 6_020.0]`,
never shared or cross-contaminated between siblings despite drawing from
the identical shared calibration record.

## Compatibility

**Zero changes to the Camera Node/wire protocol's own required shape.**
Every existing field on `GET /node/v1/health`'s response is unchanged;
`node_receive_time`/`node_time` are purely additive. An old Node's
response simply lacks both keys -- `_parse_node_timestamp` returns `None`
for a missing/malformed/non-tz-aware value (never a crash, never a
guessed default); `_round_trip_bound` excludes such a sample from its own
batch entirely (contributing to `insufficient_samples` if too many are
like this) -- proven directly (`test_sample_clock_round_trip_degrades_
gracefully_for_an_old_node_response`, `test_rtt_calibration_missing_node_
timestamp_old_node_degrades_to_insufficient`, `test_rtt_calibration_
mixed_old_and_new_node_samples_uses_only_the_valid_ones`). Monitoring and
the analysis stream itself are entirely unaffected -- this milestone adds
no new requirement to basic observation (this milestone's own explicit
§19).

**A saved ledger snapshot from before this milestone** (no `rtt_clock_
calibrations` key at all): the CLI (`run_gate_a_measurement_accounting.py`)
parses this the same honest way every prior additive-field migration in
this codebase already established -- absence means "the old codepath
applies" via `.get(..., ())`, never a crash (`test_old_ledger_snapshot_
without_clock_calibration_metadata_still_runs_cleanly`). **A snapshot that
carries the *prior* milestone's own one-way `clock_calibrations` key but
no `rtt_clock_calibrations`** is now, correctly, `invalid_clock_mapping`
-- a deliberate, disclosed tightening, not a regression (`test_one_way_
calibration_alone_is_insufficient_to_normalize`): the whole point of this
milestone is that the one-way estimator alone was never a defensible
source for this claim, so a snapshot that only has it can no longer be
treated as normalized.

**Doctor**: its Clock check's diagnostic string was updated (content only,
same key, `camera_node_clock_divergence`) to point at the new, stronger
`rtt_clock_calibrations` fact rather than the superseded one-way `clock_
calibrations` -- Doctor still cannot read a live session's in-memory state
from a standalone process (unchanged constraint, unrelated to this
milestone), and still never fails core monitoring over it.

## Local Only

Every new function operates only on timestamp pairs the existing Camera
Node <-> Host connection already exchanges during ordinary operation --
`GET /node/v1/health` is the same LAN-local connection the Host already
maintains for pairing/status; no external NTP server, no internet
reachability, no cloud service is read or required anywhere in this
milestone's own new code. Verified structurally, the same way the accepted
prior milestone verified it: grepped every new/modified file for
`socket`/external-host construction beyond the existing, already-audited
`CameraNodeClient`/`UrlLibCameraNodeRequester` machinery -- none found. The
Node and Host may each still independently run NTP against their own
configured servers (a system-administration concern, unaffected by and
entirely outside this module), but calibration *correctness* here never
depends on either one reaching the internet.

## Validation

**Tier 1** (every directly touched/new file):

| File | Result |
|---|---|
| `tests/test_clock_calibration.py` | 56 passed (26 pre-existing unchanged + 30 new) |
| `tests/test_capture_to_visible_latency.py` | 24 passed (11 pre-existing unaffected + 9 migrated to the new contract, 3 further strengthened with interval assertions + 4 new) |
| `tests/test_counterfactual_lineage.py` | 29 passed (23 pre-existing unchanged + 1 updated surface-allowlist + 5 new) |
| `tests/test_camera_node.py` | 44 passed (39 pre-existing unchanged + 5 new) |
| `tests/test_camera_node_boot_identity.py` | 27 passed (26 pre-existing unchanged + 1 new) |
| `tests/test_engine_runtime.py` | 112 passed (104 pre-existing unchanged + 8 new) |
| `tests/test_run_gate_a_measurement_accounting.py` | 5 passed (2 pre-existing unchanged + 1 migrated to the new contract + 1 updated for the new print line + 1 new) |
| `tests/test_doctor.py` | 107 passed (unchanged; covers the one updated diagnostic string) |

**Tier 1 total: 404 passed, 0 failed.**

**Tier 2** (per this milestone's own §32 subsystem list -- Camera Node
request/response handling, Camera Node client, clock calibration, stream
ingest, tracking timing, Visit assembly, fallback, persistence/query
visibility, latency accounting, acceptance tooling, compatibility --
reusing every Tier 1 file above plus `test_acceptance_recorder.py`,
`test_candidate_visit_adapter.py`, `test_candidate_visit_authority.py`,
`test_candidate_visit_authority_acceptance.py`, `test_candidate_visit_
review_workflow.py`, `test_candidate_visit_rollback.py`, `test_concurrent_
candidate_visit_persistence_reliability.py`, `test_observation_session_
api.py`, `test_time_utils.py`, `test_visit_episode_assembler.py`,
`test_field_acceptance_authentication.py`, `test_observation_camera_node_
live.py`):

**Combined Tier 1 + Tier 2: 670 passed, 0 failed, run together in one
invocation to rule out cross-file interaction, across 20 test files.**

**Ruff:** compared directly against a baseline (`git stash push` on the 11
modified tracked source files -- no brand-new files this milestone, every
change is a modification to an existing tracked file -- ran ruff, restored).
Baseline and after: **27 findings, identical set, identical content --
every diff line a pure line-number shift** from this milestone's own
inserted import lines in `api/main.py` (confirmed by direct line-content
diff, not merely a count match: every changed diff hunk is a paired
`<`/`>` line-number-only change, zero unpaired added/removed findings).
Zero new findings.

## Tier 3

**Run, and warranted -- unlike the accepted immediately-prior milestone.**
That milestone's own Tier 3 decision rested on every production-code
change being either brand-new (zero pre-existing callers) or gated behind
a parameter defaulting to exactly pre-milestone behavior, with zero new
runtime I/O. This milestone is more invasive to the live engine: `_run_
async`'s own main tick loop now makes genuinely new, periodic outbound
network requests during ordinary live operation (the RTT calibration
batch) -- a "runtime connection behavior change" per this milestone's own
explicit §33 criterion for running Tier 3. `scripts/verify_core.py`
(`pytest -m "not slow"`, this codebase's own canonical Core gate):

**5487 passed, 3 failed, 3 skipped, 23 deselected, 11 xfailed (27m38s).**

All 3 failures independently confirmed unrelated to this milestone by
fresh `git stash` bisection (every one of this milestone's own 19
modified tracked files stashed aside, the 3 tests re-run against the
exact accepted baseline `d25134b` unmodified, restored after) --
byte-for-byte identical failure messages and assertion values on both the
baseline and this milestone's own working tree, not merely "looks similar":

- `tests/test_place_biodiversity_summary_repository.py::test_api_route_
  returns_the_summary` and `::test_human_correction_updates_place_
  biodiversity_intelligence_correctly` -- the same pre-existing pair this
  file's own history has independently reconfirmed across at least three
  prior milestones (Multi-Camera Place Experience v2, Concurrent Candidate
  Visit Persistence Reliability v1, among others) -- unrelated to Camera
  Node/clock calibration in every respect.
- `tests/test_stream_playback_contract.py::test_dashboard_summary_uses_
  reviewed_truth_and_bounded_safe_visits` -- a real-clock/local-day
  -boundary-sensitive test (asserts `reviewed_observation_count_today`
  against a `local_now`/`local_day` computed relative to the actual wall
  clock); this milestone's own 27m38s Core run happened to cross the
  actual local-midnight boundary into 2026-09-01 mid-run, and the failure
  reproduces identically on the unmodified baseline -- a genuine,
  pre-existing environmental-timing flake, not a regression, and not
  previously encountered simply because no prior milestone's own Core run
  happened to straddle midnight while this exact test executed.

Zero failures attributable to this milestone.

## Self-review

Performed against every item in this milestone's own §34 checklist:

- **RTT midpoint treated as exact** -- never; `offset_min_ms`/`offset_max_
  ms`/`latency_min_ms`/`latency_max_ms` are threaded through every layer
  (calibration record -> `LatencySample` -> API response -> CLI JSON
  output), and every docstring states the midpoint is a convenience, not a
  claim of exactness.
- **Jitter treated as absolute accuracy** -- the one-way estimator's own
  jitter-spread `uncertainty_ms` no longer feeds latency computation at
  all (see "Drift / recalibration"); the RTT-bounded estimator's own
  `uncertainty_ms` is a genuine, rigorously-derived two-sided radius, not
  a jitter proxy.
- **Node processing time ignored** -- captured and used to tighten the
  bound when available (four-timestamp form), disclosed as the honest
  `RTT/2` floor when not (see "Offset interval derivation").
- **High RTT accepted** -- filtered per-sample before the intersection
  step against a disclosed engineering ceiling, never blended in (see "RTT
  / uncertainty model").
- **Stale calibration after reconnect** -- a fresh RTT batch is forced at
  the next tick; a genuine clock change is caught by jump detection
  against the immediately-preceding batch, never blindly bridged (see
  "Reconnect behavior").
- **Clock jump not invalidating anchor** -- the shared epoch-selection
  model (refactored, not duplicated, from the accepted one-way version)
  applies identically to RTT anchors, directly tested (see "Clock-jump
  behavior").
- **Fallback using winner timestamp** -- re-proved with a deliberately
  discriminating jump-separated-epoch test, now additionally asserting the
  interval, not only the point estimate.
- **Sibling timestamp contamination** -- re-proved; each sibling's own
  independent, correctly-shifted interval confirmed by direct assertion.
- **Old Node compatibility** -- exercised at every layer (Node response
  shape, Host parsing, per-sample batch filtering, ledger/API/CLI
  snapshot parsing).
- **Local Only accidentally depending on external NTP** -- every new
  function operates solely on timestamps the existing Camera Node <-> Host
  connection already exchanges; verified structurally.
- **Uncertainty dropped before final latency output** -- threaded through
  every layer explicitly, never truncated to the point estimate alone at
  any boundary (dataclass, Pydantic response, CLI JSON `asdict()` output).

**Additional findings from this milestone's own adversarial pass, found
and fixed before this report was written (not merely disclosed):**

1. A real sequential-batch startup-latency regression (see "Calibration
   exchange," above) -- found via a genuinely failing pre-existing
   end-to-end test, not by inspection alone; fixed by making the batch's
   own attempts concurrent and moving the first calibration off the
   session-start critical path entirely.
2. A redundant exception-type check (`CameraNodeClientError` is already a
   `ValueError` subclass) in the batch's own failure handling -- corrected
   for clarity, not a behavioral bug.

No other adversarial finding survived investigation.

## Remaining field proof

Not self-authorized by this milestone (per its own explicit instruction).
The next daylight cohort run against post-this-milestone accepted HEAD
should collect:

1. Real RTT calibration samples against the real reference Camera Node --
   the offset interval(s)/uncertainty actually observed, whether the batch
   ever degrades to `insufficient_samples`/`inconsistent_samples` in
   practice, and the real measured RTT distribution on that LAN.
2. Whether the 5-minute periodic cadence is well-matched to real observed
   drift, or needs adjustment from actual evidence (not yet available).
3. Whether a real reconnect or clock jump is naturally encountered, and
   whether the recalibration triggers behave as designed under real
   conditions (not merely simulated ones).
4. The first defensible true T0 -> T5 latency distribution with real,
   `state == "measured"` samples whose `clock_calibration_state ==
   "normalized"` -- every historical cohort (2026-08-19, v6, v7) still
   predates `rtt_clock_calibrations` entirely and cannot be retroactively
   fixed (the same historical-data limitation the accepted prior milestone
   already disclosed, unchanged and restated here, not newly discovered).
5. Everything already named in the accepted prior milestone's own
   "Remaining field proof": a stronger recall denominator; a directly
   comparable fragmentation rate; 3+-simultaneous-subject activity if
   naturally available (the disclosed, not-yet-benchmarked crowded-feeder/
   NMS gap); continued false-Visit/useful-evidence/duplicate measurements;
   residual `blocked_missing_evidence` traces; the already-known Gate B
   admission-precision residual.

## Decision

**Classification A.**

- Absolute Node<->Host clock calibration now has a rigorously-derived,
  defensible bounded interval (`[offset_min_ms, offset_max_ms]`), reusing
  the existing `/node/v1/health` request/response operation rather than a
  new protocol.
- RTT uncertainty is explicit on every calibration record and every
  affected latency sample; the midpoint is never represented as exact --
  every field name, docstring, and API/CLI projection carries the full
  interval alongside the point estimate.
- Poor-quality/high-RTT/mutually-inconsistent samples degrade honestly
  (`insufficient_samples`/`inconsistent_samples`), never averaged into a
  falsely precise estimate.
- Drift is monitored (the accepted one-way estimator, unchanged, now
  scoped to exactly this) and clock jumps invalidate/recalibrate
  appropriately at both the data-model (epoch selection) and live-session
  (recalibration trigger) layers, proven in both directions.
- Reconnect does not blindly reuse a stale mapping -- a fresh RTT batch is
  forced at the next tick, with a disclosed, bounded (sub-2-second) gap
  before that batch completes, honestly documented rather than hidden.
- Latency is represented with real uncertainty bounds end to end (dataclass
  -> API response -> CLI JSON output), including the correctly-derived
  min/max inversion, verified at two independent layers.
- Fallback timestamp provenance is preserved under RTT normalization,
  re-proved with a deliberately discriminating jump-separated-epoch test
  now also asserting the interval.
- Stop-finalization and multi-subject sibling isolation are both correct
  under RTT normalization, re-proved with interval assertions.
- Old Node compatibility is graceful in every direction checked -- a
  missing/malformed Node timestamp degrades to an honest, auditable state,
  never a crash, at every layer (Node response, Host parsing, batch
  filtering, ledger/API/CLI snapshot parsing).
- Local Only holds -- every new function operates solely on timestamps the
  existing Camera Node <-> Host connection already exchanges; no external
  NTP/cloud dependency introduced.
- Tier 1 clean (404/404). Tier 2 clean (670/670, combined). Tier 3 run
  (warranted by this milestone's own genuinely new runtime network I/O)
  and clean: 5487 passed, 3 failed, all 3 independently confirmed
  pre-existing/unrelated by fresh baseline bisection, zero regressions
  attributable to this milestone. Zero new ruff findings.
- One real regression (sequential-batch startup-latency blocking live
  frame processing for up to ~10 seconds against an unreachable Node) was
  found via a genuinely failing pre-existing test during this milestone's
  own work, root-caused, and fixed -- not merely disclosed.
