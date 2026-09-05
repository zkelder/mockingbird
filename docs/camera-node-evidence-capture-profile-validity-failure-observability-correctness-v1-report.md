# Camera Node Evidence-Capture Profile Validity & Failure Observability Correctness v1

Bounded, release-critical correctness milestone. Follows Representative
Daylight Gate A Field Acceptance v13 (accepted, classification B), which
reproduced a severe field failure: 101.8 minutes of representative daylight
monitoring, substantial independently-confirmed real bird activity, 350
proposals, zero admitted Visits, every recovered proposal decision dying at
`no_persistable_evidence_bytes`, and no `EvidenceCandidate` ever created. v13
root-caused this to the Observation Engine's automatic evidence-burst path
(`CameraNodeHttpTransport.request_evidence_burst`) collapsing every distinct
failure into one opaque, unlogged generic code, and identified two candidate
triggers -- silent Node-side profile renaming, and a Host timeout too short
for a legitimate slow capture -- without determining which one (or both)
actually fired.

This milestone's job: reproduce the failure, identify the exact first
irreversible error, make evidence-profile validity/recovery correct, make
evidence-burst failure causally observable, and prove real evidence bytes
again flow into the normal Visit pipeline. It does **not** close Gate A and
does not authorize any further work.

## Starting state

Verified before any change:

- Branch `main`, HEAD `be74130` (the reconciliation commit recording v13;
  per this repository's own established "Accepted HEAD" convention, the
  accepted product-code commit remains `eb02d51`, the report commit for
  Ambiguous-Boundary Real-Subject Recall Correctness v1 -- v13 itself
  changed zero production code).
- Schema `v58`, unchanged.
- `docs/release-execution-state.md`'s v13 entry (§3 and §6 Lane R) confirmed
  present and matching this milestone's own briefing exactly: 101.8 minutes,
  350 proposals, 0 admitted Visits, `CameraNodeHttpTransport.request_
  evidence_burst` named as the causal site, two candidate triggers recorded,
  neither confirmed, item (14) recorded as the new, most urgent Gate A
  dependency. The document's own top-of-§1 "Accepted HEAD" bullet is a
  separately pre-existing, already self-disclosed staleness (three
  milestones behind, explicitly flagged by v13 itself as "not the right
  occasion for a multi-milestone historical §1 rewrite") -- confirmed
  harmless documentation lag, not a product-state conflict, and left exactly
  as v13 left it (out of scope for this milestone too).
- Worktree: the seven files this session must preserve untouched
  (`docs/wildlife-detector-training-contract.md.orig`,
  `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`) were present, untracked, and
  confirmed byte-identical/untouched at both the start and the end of this
  session. No other writer was active in this worktree.

## v13 failure reconstruction

From `representative-daylight-gate-a-field-acceptance-v13-report.md` and
direct code tracing (no new claims invented beyond what that report already
established):

- Configured Stream/source identity: a real Camera Node Source against the
  reference Pi (`node-76ec8e53ae586dd0`), evidence profile persisted at
  camera-setup time (e.g. `picamera2-evidence-3840x2160`).
- First known `no_persistable_evidence_bytes` occurrence: effectively
  session-wide, from the first proposal onward -- v13's own numbers show
  0% recall against 19 conservatively-confirmed real encounters.
- Whether any successful evidence burst existed: v13's own `evidence_
  harvest_misses` counter stayed 0 for the full 101.8 minutes, which that
  counter's own governing contract (Harvested Evidence Issuance / Missing-
  Evidence Closure v1) proves means nothing was ever successfully captured
  in the first place -- ruling out a captured-then-lost race, consistent
  with this milestone's own live finding below.
- Host logs: v13 confirmed zero `logger`/`logging` calls anywhere in
  `camera_node_live.py` -- no underlying HTTP status/exception ever reached
  a log line. Node-side logs from that session do not survive (a different,
  since-cycled Node process).
- Request timeout configuration: `response_timeout_seconds=10.0` (class
  default) plus `connect_timeout_seconds=2.0` (hardcoded in the call site) =
  ~12s total budget, confirmed unchanged in the current codebase before this
  milestone's own edits.
- Evidence-profile lifecycle: not established by v13 (out of its own bounded
  field-collection scope) -- this is exactly what this milestone establishes
  below, live.

This milestone does not claim a specific v13 HTTP status/timeout beyond what
v13 itself recorded; the root-cause work below is a fresh, independent,
live investigation, not a re-assertion of v13's own unconfirmed hypotheses.

## Current evidence-burst architecture

Traced end to end, `src/mockingbird/observation/camera_node_live.py` and
`src/mockingbird_node/{app.py,providers.py}`:

```
proposal needs evidence
  -> LiveCameraNodeShadowSession._process_frame (burst opportunity decided by BurstScheduler)
  -> CameraNodeHttpTransport.request_evidence_burst
  -> POST /node/v1/cameras/{camera_id}/evidence-burst
  -> mockingbird_node.app.evidence_burst -> capture_response -> capture_image
       -> camera lookup / camera.status check (no X-MockingBird-Node-Error header)
       -> live `provider.capture_profiles(camera_id)` lookup by profile_id
            -> 409 + X-MockingBird-Node-Error: profile_not_advertised  if missing
       -> provider.snapshot(camera_id, profile_id=...)
            -> ValueError mapped to a specific (code, status, X-MockingBird-Node-Error) triple
  -> Host reads only response.status (never the header) -> generic failure_code
  -> EvidenceBurstResult(status="failed", failure_code="evidence_burst_unavailable")
  -> no EvidenceCandidate constructed, no bytes ever cached
  -> proposal reaches product_repository's items_with_content check empty
  -> blocked_missing_evidence / no_persistable_evidence_bytes
```

**Confirmed pre-fix collapse points** (`camera_node_live.py:583-584,617-618`
before this milestone's edit): a `409 profile_not_advertised`, a `503`
session failure, a raw socket timeout, and a connection reset all produced
the *identical* `failure_code="evidence_burst_unavailable"`, with zero
logging. The Node, however, *already* reports the specific cause via
`X-MockingBird-Node-Error` for every path except the earliest "camera
missing/not available" check -- the Host was simply discarding information
it already had, mirroring exactly what `source_providers.camera_node.
CameraNodeClient.capture`/`.snapshot` (the older, manual/legacy path) already
correctly parses for the sibling `/capture` endpoint. The modern automatic
path had **strictly less observability** than the legacy path it was meant
to replace -- confirmed directly, not assumed.

## Profile identity lifecycle

Traced in `src/mockingbird_node/providers.py` (`PiCamera2Provider`):

1. `capture_profiles(camera_id)` first computes **cold** profiles from real
   sensor modes: `profile_id=f"picamera2-evidence-{w}x{h}"`,
   `capture_class="reconfiguration_required"`.
2. The same call kicks off `_schedule_warm_proof` -- a background thread
   (`_prove_warm_profiles`) that tests candidate monitoring/evidence pairs
   live on the real camera hardware.
3. On success, the accepted evidence profile is **replaced**:
   `profile_id=f"picamera2-warm-evidence-{w}x{h}"`,
   `capture_class="warm_concurrent"` -- same width/height/purposes/
   `geometry_group`/`same_fov`, but a **different opaque id**, and the old
   cold id is explicitly excluded from the new cache
   (`providers.py`, the `_profile_cache[camera_id] = tuple([...])`
   assignment in `_prove_warm_profiles`) -- **gone from the Node's
   advertised list for the rest of that process's life**, until the Node
   process itself restarts.

Answers to the milestone's lifecycle questions:

1. Is `profile_id` intended to be durable identity? No -- it is explicitly
   documented as "opaque" and provider-controlled
   (`NodeCaptureProfile`/`CaptureRequest` docstrings).
2. Is that guaranteed by the protocol? No.
3. Can the Node legitimately replace/rename it? Yes -- proven live, below.
4. Does Host Stream configuration currently assume permanence? Yes -- the
   persisted `camera_node_evidence_profile_id` was used verbatim, forever,
   with no re-validation.
5. Is the profile semantically identifiable by stable properties even if the
   id changes? Yes -- width, height, `purposes`, and `geometry_group` are
   all preserved across the cold->warm rename (confirmed both by reading
   `_start_highest_warm_session`'s construction of `warm_evidence` and by
   live observation below).
6. Can multiple profiles match the same semantic contract? Yes, in general
   (a camera can advertise several evidence resolutions) -- reconciliation
   below fails closed rather than guessing when that happens.
7. Is there already a protocol capability to validate the configured
   profile? Yes -- `GET /node/v1/cameras` already returns each camera's full
   live `capture_profiles` list, already fetched elsewhere in this exact
   codebase (`engine_runtime._default_capture_profile_alignment`, at
   session start) via the already-bounded-timeout `CameraNodeClient.
   cameras()`. No new Node-facing HTTP mechanism was built.

## Timeout / reconfiguration investigation

Independently measured, live, on the real reference Camera Node (Pi,
`node-76ec8e53ae586dd0`), using the real, unmodified `CameraNodeHttpTransport.
request_evidence_burst`:

| Condition | Real measured elapsed | Host budget |
|---|---|---|
| Already-warm matching profile | 0.285s - 0.385s | ~12s (2s connect + 10s response) |
| First cold `reconfiguration_required` capture (forces reset -> reinit -> capture -> restore-monitoring) | 5.659s | ~12s |
| A second, back-to-back cold capture (camera re-reset again by the same mechanism) | 7.870s | ~12s |
| Warm capture immediately after the cold ones (self-heals via `_reopen_accepted_warm_session`) | 5.751s | ~12s |

Every measured cold-path capture stayed comfortably under budget (4-6
seconds of real headroom even in the least favorable case measured,
including a fully forced reset+reinit+capture+monitoring-restore cycle
back-to-back). The provider's own capture lock (`CAPTURE_LOCK_TIMEOUT_
SECONDS=0.5`) fails fast on contention rather than queuing, so ordinary
concurrent monitoring-stream load converts into a distinguishable
`camera_busy`/`node_camera_unavailable` response, not a slow timeout.
**Conclusion: the timeout hypothesis is not supported by real measurement on
this hardware. The timeout was not changed.** This does not prove no Node,
under no conditions, could ever exceed the budget -- only that this
milestone found no live evidence for it, and did not invent a fix for an
unproven cause.

## Live pre-fix reproduction

Using the real reference Camera Node (a user-authorized, non-destructive
Node-side pairing reset, matching the precedent used by prior milestones --
credential never logged, backed up before each reset following the
established `pairing.json.pre-<milestone>-reset.bak` convention):

**Node pairing/health at start**: `node_id=node-76ec8e53ae586dd0`,
`boot_id=4239527b-...` (stable throughout), `service_version=0.1.0`,
`self_test.status=passed`, `camera_available=true`, providers
`picamera2,v4l2`.

**Step 1 -- live cold->warm promotion, timed.** Immediately after a fresh
pairing, `picamera2-evidence-3840x2160` (`capture_class=
"reconfiguration_required"`) was the only live evidence profile. Polling
`GET /node/v1/cameras` every 0.5s:

- `t=0.00s`: cold profile present, `capture_readiness=warming`.
- `t=4.18s`: **cold profile id gone from the advertised list entirely**;
  `picamera2-warm-evidence-3840x2160` (`capture_class=warm_concurrent`,
  identical width/height/`geometry_group`/`same_fov`) now advertised;
  `capture_readiness=ready`. Confirmed stable for 19+ further seconds of
  polling.

**Step 2 -- exercising the real, unmodified `request_evidence_burst`.**

- Requesting the now-stale cold id: `status='failed'
  failure_code='evidence_burst_unavailable'` -- the exact opaque code the
  milestone and v13 both describe, reproduced against real hardware with
  the pre-fix code.
- Requesting the current live warm id directly: `status='captured'`,
  3840x2160, 1,170,681 real JPEG bytes, 0.385s.

This is a clean, direct, live reproduction of the exact v13 mechanism using
the exact named production method, not an inference from symptoms.

## First irreversible error

`CameraNodeHttpTransport.request_evidence_burst` receiving the Node's `409`
response with header `X-MockingBird-Node-Error: profile_not_advertised` and
discarding it -- collapsing a fully-diagnosable, already-communicated cause
into the same generic code used for a timeout, a connection reset, or a
malformed response, with zero logging. Everything downstream of that one
discarded header (the `_burst_failures` counter increment, the scheduler's
"failed" recording, the proposal's eventual `blocked_missing_evidence`) is a
faithful, correct consequence of that first information loss -- not a
separate defect.

## Root-cause classification

**B -- profile recreation/rename not reconciled**, proven live (not merely
inferred): the Node's own async warm-proof promotion silently retires a
`reconfiguration_required` evidence profile id and replaces it with a
differently-named `warm_concurrent` one carrying an identical capture
contract, ~4.2 real seconds after pairing/Node start on the reference
hardware; the Host never re-validated the persisted id against the Node's
live profile set before using it, so once the pre-existing Add-Camera setup
flow happened to capture the id before promotion completed, every
subsequent burst for the life of that Node process failed identically,
matching v13's own "every proposal died at the evidence gate" shape exactly.

The timeout hypothesis (D) was independently investigated and is **not
supported** by real measurement (see above) -- not classified as a
contributing cause, and not "fixed" by raising a number that was never shown
to be wrong.

## Locked implementation contract

Written before any production edit, and followed exactly:

1. **Observability**: `request_evidence_burst` reads the Node's own
   `X-MockingBird-Node-Error` header (mirroring the already-established,
   already-tested `CameraNodeClient.capture`/`.snapshot` alias table
   verbatim, so the identical Node-side cause is named identically
   everywhere) to classify a non-200 response into a specific failure code,
   falling back to the pre-existing generic `evidence_burst_unavailable`
   only when the Node sends no recognized header. A raw transport exception
   (timeout, connection refused/reset, DNS) is additionally classified via
   the already-existing, previously-unused-here `_classify_analysis_stream_
   transport_error`, attached as a new, additive `failure_class` field.
2. **Stale-profile reconciliation, bounded to exactly one retry**: on a
   first-attempt failure specifically classified as the Node's own
   "profile not advertised" code, fetch the Node's live profile list once
   (reusing the already-bounded-timeout `CameraNodeClient.cameras()`,
   already used elsewhere in this exact runtime) and deterministically pick
   the live evidence profile for this camera **only if exactly one
   unambiguous candidate exists** -- preferring `capture_class ==
   "warm_concurrent"` (the identical "proven ready" signal `api.main._
   camera_node_profile_selection` already prefers at setup time), falling
   back to "exactly one evidence-purposed profile of any class" only when no
   warm one yet exists. If reconciliation finds one match: update the
   transport's own `evidence_profile_id`, retry the identical logical burst
   once, and report `reconciled_profile_id` on the result so the calling
   session adopts the corrected id too (avoiding the pre-existing
   session/transport mismatch guard tripping on the very next opportunity).
   If reconciliation is ambiguous, empty, or itself fails for any reason:
   fail closed, return the original classified failure, no guess.
3. **No blind retries**: reconciliation is triggered by exactly one failure
   classification (the Node's own explicit "not advertised" signal), never
   by any other cause (auth, camera-busy, session-failure, timeout,
   connection failure) -- each of those keeps its own distinct code and is
   never treated as a profile-recovery opportunity.
4. **Timeout**: unchanged (see investigation above).
5. **Observability surfacing**: `LiveShadowStatus`'s existing `burst_
   requests`/`burst_captures`/`burst_failures`/`stale_bursts` counters --
   confirmed by direct code search to be computed but never once read by
   `engine_runtime.py`, and therefore never reaching `observation/status`'s
   `advanced` payload in production -- are now read once per batch (the
   same cadence as the existing exposure checkpoint) into that same
   already-untyped `advanced` dict, alongside two new counters
   (`evidence_profile_reconciliation_count`, and the last classified burst
   failure code/time). No pydantic schema change was required (`advanced:
   dict[str, object]` is already a free-form pass-through end to end).
6. **No false health**: general Node health/`camera_connected` semantics are
   untouched; the new counters are additive diagnostics alongside, never a
   redefinition.
7. **Scope**: MDv5, threshold, NMS, tracker, candidate authority, ambiguous-
   boundary arbitration, dead-anchor promotion, candidate quality gate,
   `classifier_same_frame` fallback, detector/independent corroboration,
   scene-confusor, evidence quality/ranking, Visit grouping, BioCLIP,
   Identification Eligibility, and Reviewed truth are untouched -- confirmed
   by the final diff touching only `camera_node_live.py`, `media_contracts.py`
   (two new optional dataclass fields), and one additive, best-effort
   diagnostics block in `engine_runtime.py`.

## Implementation

- `src/mockingbird/observation/media_contracts.py`: `EvidenceBurstResult`
  gains `failure_class: str | None = None` and `reconciled_profile_id: str
  | None = None`, both additive with bounded `__post_init__` validation
  (mirrors `CameraNodeClientError.failure_class`'s own established pattern;
  never used for control flow outside this milestone's own new code).
- `src/mockingbird/observation/camera_node_live.py`:
  - New module-level `_classify_node_error_header` plus a small, local
    `_NODE_ERROR_TO_BURST_FAILURE_CODE` alias table (deliberately a local
    duplication of `source_providers.camera_node`'s private, underscore-
    prefixed constants -- mirroring this file's own existing precedent of a
    small, obviously-correct duplication over a cross-module reach into
    another module's internals, e.g. `_default_capture_profile_alignment`'s
    own documented reasoning for the identical choice).
  - `CameraNodeHttpTransport.request_evidence_burst` now orchestrates: the
    existing closed/mismatch guards, one attempt via new `_attempt_
    evidence_burst` (the prior method's HTTP body, factored out unchanged
    except for the header-based classification and transport `failure_
    class`), and -- only on the specific stale-profile code -- one
    reconciliation (`_reconcile_evidence_profile`) plus one retried attempt.
  - `LiveShadowStatus` and `LiveCameraNodeShadowSession` gain the
    reconciliation-count/last-failure diagnostics described above;
    `_process_frame` adopts a returned `reconciled_profile_id` into the
    session's own `evidence_profile_id`.
- `src/mockingbird/observation/engine_runtime.py`: `_EngineSession._run_
  async`'s existing per-batch checkpoint block now also reads `session.
  status()` into `self._advanced`, wrapped in the same "diagnostics must
  never break observation" `try/except Exception: pass` discipline this
  file already uses for `report_metadata` -- a real regression this exact
  choice caught and fixed (see RED->GREEN below).

No other file was modified.

## Failure taxonomy / observability

`EvidenceBurstResult.failure_code`, after this milestone, distinguishes
(where the Node's own protocol actually permits it):

| failure_code | Meaning | Source |
|---|---|---|
| `transport_closed` | Transport already closed | pre-existing |
| `evidence_profile_mismatch` | Session/transport id desync (programming guard) | pre-existing |
| `authentication_rejected` | 401 | pre-existing |
| `node_capture_profile_unavailable` | Node's profile not advertised (stale/renamed) -- **now the reconciliation trigger** | Node header, newly read |
| `node_camera_unavailable` | Camera busy/setup-required at capture time | Node header, newly read |
| `node_camera_warmup_timeout` | Camera warm-up timed out | Node header, newly read |
| `node_snapshot_invalid` | Node reports the captured frame invalid | Node header, newly read |
| `node_snapshot_timeout` | Node's own capture timed out | Node header, newly read |
| `provider_reset_required` / `provider_session_failed` | Node-side provider/session failure | Node header, newly read |
| `evidence_burst_invalid` | Malformed/incomplete HTTP response body | pre-existing |
| `evidence_burst_unavailable` | Fallback: no recognized header, or a raw transport failure -- `failure_class` (`connect_refused`/`connection_reset`/`timeout`/`dns_unresolved`/`os_error`) distinguishes the latter | pre-existing code, newly sub-classified |

**Disclosed, honest limitation, not invented away**: the Node's very
earliest checks in `capture_image` (camera entirely missing from `provider.
cameras()`, or present but `status != "available"`) do not set `X-
MockingBird-Node-Error` at all -- these still collapse into
`evidence_burst_unavailable`. This is a genuine Node-protocol gap, not a
Host oversight, and touching it would mean modifying and redeploying the
separate `mockingbird_camera_node` wheel -- out of this milestone's bounded
scope (see "Residual risk").

Bounded, low-cardinality counters now reach `GET /api/streams/{id}/
observation/status`'s existing `advanced` dict with zero schema change:
`evidence_burst_requests`, `evidence_burst_captures`, `evidence_burst_
failures`, `evidence_burst_stale`, `evidence_profile_reconciliation_count`,
and (once any failure has occurred) `evidence_burst_last_failure_code`/
`evidence_burst_last_failure_at`.

No credential, pairing code, raw response body, or full URL is ever logged
or surfaced by any of this.

## Retry / reconciliation safety

- Bounded to exactly one extra live "list profiles" call and one retried
  burst POST per failed attempt -- never a loop.
- Triggered only by the Node's own explicit "profile not advertised"
  signal; every other failure code (auth, camera-busy, session-failure,
  transport exception) returns immediately, proven by both the code
  structure and dedicated tests.
- Reconciliation itself fails closed (returns `None`, never raises) on an
  ambiguous match, zero candidates, or any live-lookup failure (Node
  unreachable, authentication rejected) -- proven live and by test.
- Structurally cannot duplicate evidence: a failed attempt produces zero
  frames; the retry either produces the one allowed frame or none.

## RED->GREEN

Nine new tests added to `tests/test_observation_camera_node_live.py`,
exercising the real, unmodified wire protocol end to end (`mockingbird_
node.app.create_node_app` over a real socket via the established `_transport_
fault_injection.RunningApp` uvicorn-in-a-thread harness, real pairing, real
`CameraNodeHttpTransport` HTTP calls) plus two focused unit/session-level
tests and one pure-function test:

- `test_stale_profile_burst_reconciles_to_the_single_live_warm_replacement_and_retries_once`
  (the v13-shaped reproducer)
- `test_ambiguous_live_replacement_fails_closed_without_guessing`
- `test_camera_busy_is_distinguishable_and_never_treated_as_profile_recovery`
- `test_authentication_rejected_is_distinguishable_and_never_treated_as_profile_recovery`
- `test_real_connection_refused_during_evidence_burst_is_distinguishable_from_profile_failure`
- `test_real_timeout_during_evidence_burst_is_distinguishable_from_profile_failure`
  (a real TCP server that accepts but never responds -- the actual
  production timeout path, not a mock)
- `test_node_unreachable_during_reconciliation_fails_closed_without_crashing`
- `test_live_shadow_session_adopts_reconciled_profile_id_and_counts_it`
- `test_classify_node_error_header_maps_known_codes_and_falls_back_honestly`

**Genuine RED, proven by bisection**: `git stash push -u` on only the three
production files (leaving the new tests in the working tree) reproduced 9/9
new-test failures against the pre-fix code -- for the right reasons (spot-
checked: the core reproducer failed `'failed' != 'captured'`; the pure-
function test failed with a real `ImportError` for the not-yet-existing
helper). `git stash pop` restored the fix; all 53 tests in the file
(44 pre-existing + 9 new) passed.

One real regression was found and fixed during this same RED->GREEN pass:
the new `engine_runtime.py` per-batch `session.status()` read initially
broke `test_engine_runtime.py::test_batch_internal_burst_capture_no_longer_
starves_an_early_generations_evidence`, whose minimal fake provider fixture
does not implement `replay_semantic_facts()`/`active_track_count` (nothing
had ever called `session.status()` from `_run_async` before this milestone,
so the gap was latent). Fixed by wrapping the new diagnostics read in the
same `try/except Exception: pass` discipline this file already uses
elsewhere for exactly this reason ("diagnostics must never break
observation") -- re-run clean afterward.

## V13-shaped reproducer

Before the fix (live, Section "Live pre-fix reproduction" above): a real
evidence-burst request naming a profile the Node has since silently
retired fails with the generic pre-fix code, zero bytes, zero
`EvidenceCandidate`.

After the fix (live, Section "Real Camera Node post-fix proof" below, and
`test_stale_profile_burst_reconciles_...`): the identical shape of request
reconciles automatically and the proposal receives real evidence bytes. No
claim is made, or needed, that the proposal becomes a Visit -- precision
gates are untouched and remain authoritative.

## Non-recoverable controls

- Real hardware: a deliberately wrong credential against the real Node ->
  `status='failed' failure_code='authentication_rejected'`, zero frames, no
  reconciliation attempted, transport's `evidence_profile_id` untouched, no
  crash.
- Unit/integration: `test_camera_busy_...` (a currently-advertised, never-
  stale profile whose capture is transiently busy) and `test_ambiguous_
  live_replacement_...` (two live `warm_concurrent` evidence candidates,
  no discriminator) both fail with their own distinct, honest codes,
  `reconciled_profile_id is None`, `frames == ()`, and the transport's own
  `evidence_profile_id` left unchanged -- no fabricated evidence, no
  fabricated recovery.

## Real Camera Node post-fix proof

Two independent live proofs, both against the real reference Camera Node,
both using a fresh, legitimate, user-authorized pairing (the Node's own
accepted build, `service_version=0.1.0`, unchanged throughout this
milestone; `self_test.status=passed`):

**A. Full production pipeline** (`ObservationEngineSessionManager` ->
`_EngineSession._run_async` -> `LiveCameraNodeShadowSession` -> the fixed
`CameraNodeHttpTransport`, entirely real and unmodified; only the
*detector* was substituted for the exact deterministic fixture this
project's own test suite already uses (`_LiveDetector`, a fixed high-
confidence "animal" detection every frame) -- MDv5/threshold/tracker stay
completely uninvolved, matching this milestone's freeze list exactly. A
real temp-file SQLite `ProductRepository` backed the session):

- Configured the session with the cold, pre-promotion evidence profile id
  (the exact v13-shaped staleness condition), confirmed gone from the
  Node's live set before starting.
- Within 13 real seconds: `evidence_burst_requests=1, evidence_burst_
  captures=1, evidence_burst_failures=0, evidence_profile_reconciliation_
  count=1` -- the real `advanced` status API, unmodified consumer path,
  showing the self-heal happened and the burst ultimately succeeded.
- A real `EvidenceCandidate(role="high_resolution_burst", ...)` was
  therefore constructed with real Pi bytes inside the real, unmodified
  `_process_frame` -- the exact code path v13 proved was structurally
  unreachable all session long, now proven reached. No Visit was admitted
  in this bounded ~24-second smoke (not required by this milestone; `Evidence
  Candidate.temporary=True`/`shadow_only=True` on every candidate confirms
  this is the correct, by-design behavior for a not-yet-decided candidate --
  durable `media_assets`/file persistence is gated on Visit admission, which
  requires the deliberately untouched downstream precision gates this
  milestone must not bypass, independently and extensively re-verified
  unaffected by the full Tier 2 run below).
- `resolution_alignment_status` stayed `not_checked` for this run --
  `engine_runtime._default_capture_profile_alignment` was deliberately left
  untouched (it feeds `fov_alignment_proven`/geometry lineage, explicitly
  frozen territory) and, like the pre-fix code, still silently degrades
  rather than self-healing when the *alignment* check's own profile lookup
  is stale at session start. This is a disclosed, pre-existing, out-of-
  scope gap, not a regression -- evidence capture itself worked correctly
  regardless (see "Residual risk").

**B. Direct transport-level, multiple sequential bursts** (the fixed
`CameraNodeHttpTransport`, a fresh pairing/cold-profile episode): three
back-to-back real burst requests, all against the real Pi --

```
[1-stale-profile-configured] elapsed=0.450s status='captured' reconciled='picamera2-warm-evidence-3840x2160' bytes=1109436
[2-already-corrected]        elapsed=0.285s status='captured' reconciled=None                                 bytes=1102108
[3-already-corrected]        elapsed=0.306s status='captured' reconciled=None                                 bytes=1094980
```

All three real JPEGs decoded at the expected 3840x2160 dimensions. The
first call self-healed (reconciliation + one retry, 0.450s total); the
next two used the corrected id directly with no further reconciliation
needed, proving the fix is sticky for the life of the transport, not a
one-shot fluke.

## Observation smoke

Covered by proof A above: a real, bounded (~24s) Observation session
against the real Camera Node, real analysis-stream frames, real tracker
activity (via the deterministic fixture detector), real burst scheduling,
one real evidence-burst opportunity that self-healed and captured real
bytes, zero crashes, zero duplicate evidence, and the session's own
`advanced` diagnostics correctly and accurately showing the successful
capture and the reconciliation that made it possible. No Visit flood (one
opportunity, one capture); no field recall/precision claim is made.

## Credential / privacy safety

- No bearer credential, pairing code, or raw Node response body appears in
  any log line, source file, test, or this report.
- Every pairing code/credential used during live investigation lived only
  in short-lived local scratchpad files, deleted at the end of the session;
  none were committed.
- Three Node-side pairing resets were performed during this milestone (pre-
  fix investigation, post-fix full-pipeline proof, post-fix multi-burst
  proof), each backed up first following the repository's own established
  `pairing.json.pre-<milestone>-reset.bak` convention, each superseded by
  the next. The Node was left genuinely unpaired
  (`pairing_required=true`), healthy, and on its unchanged accepted build
  at the end of this session -- no lingering test credential.

## V13 ledger-cadence finding

v13 disclosed only 44.6% `proposal_outcomes` decision-event recovery in its
own snapshot tooling. This milestone did **not** need that ledger tool at
all: validation used direct transport-level real-hardware tests, the real
production `advanced` status API, and raw SQLite/filesystem inspection of a
fresh temp-file repository -- none of which depend on the field-acceptance
ledger snapshot cadence. **Conclusion: the ledger-cadence gap does not block
validating this fix, and remains exactly what v13 left it as -- a separate,
already-disclosed Gate A evidence-integrity dependency, not touched or
widened by this milestone.**

## Tier 1

RED->GREEN as described above. Final: 53/53 passed in
`tests/test_observation_camera_node_live.py` (44 pre-existing + 9 new).

## Tier 2

Full affected Camera Node / Observation Engine / live-camera-session
subsystem, 24 files:

```
tests/test_camera_node.py tests/test_camera_node_boot_identity.py
tests/test_camera_node_capture_contention.py tests/test_camera_node_config_transport.py
tests/test_camera_node_packaging.py tests/test_camera_node_pairing_persistence.py
tests/test_camera_node_real_process.py tests/test_camera_node_repair_pairing.py
tests/test_camera_node_reprovision.py tests/test_camera_node_response_parsing.py
tests/test_camera_node_transport_acceptance.py tests/test_camera_node_transport_consumption.py
tests/test_camera_node_transport_ledger.py tests/test_camera_node_transport_router.py
tests/test_camera_node_transport_wiring.py tests/test_doctor_camera_node_transport.py
tests/test_install_camera_node.py tests/test_node_compatibility_api.py
tests/test_observation_camera_node_live.py tests/test_engine_runtime.py
tests/test_unified_observation_status.py tests/test_stream_playback_contract.py
tests/test_multi_camera_concurrent_runtime.py tests/test_live_camera_session.py
```

Final: **686 passed, 11 xfailed, 0 failed attributable to this change**
(three full runs). One unrelated, pre-existing flake was found and
isolation-confirmed: `test_camera_node_transport_acceptance.py` (a
real-thread/real-socket harness exercising the separate Remote/
Intermittent-WAN transport spool/worker, zero shared code with this
milestone's diff) failed on a different scenario in two of three full-batch
runs (`test_scenario_1_ordinary_disconnect_reconnect` once, `test_scenario_
8_host_incompatibility_is_diagnosable_not_silently_lost` twice) -- both are
background-worker retry-timing races (`next_attempt_in_seconds` scheduling
vs. the test's own polling), the classic signature of load-induced
flakiness in a real-thread test file run inside a large batch. Isolation
runs: the full file 8/8 three separate times pre-fix (via `git stash push
-u` bisection) and the specific failing test 1/1 four times in a row
post-fix. Confirmed pre-existing and unrelated, matching this project's own
long-documented "load-induced flake, isolation-confirmed clean" pattern.

`ruff check` on all four changed files: zero new findings (one pre-existing,
out-of-scope unused import in the test file, confirmed via `git diff` to
predate this milestone, left untouched).

## Tier 3 decision

**Not run.** The final production diff is narrowly confined to the Camera
Node evidence-capture transport (`camera_node_live.py`), two additive
dataclass fields (`media_contracts.py`), and one additive, best-effort
diagnostics read in `engine_runtime.py`'s existing per-batch loop -- no
admission, Visit-assembly, species, review, schema, or UI code was touched.
Tier 2's 686 tests already cover every real consumer of every changed
symbol (all Camera Node subsystem tests, the full Observation Engine
runtime suite, the multi-camera concurrent runtime suite, and the unified
observation-status surface). This matches the identical bounded-blast-radius
reasoning the immediately-comparable prior Camera Node hardware-validation
milestone used for the same decision.

## Residual risk

- The Node's earliest "camera missing/not available" checks still collapse
  into the generic `evidence_burst_unavailable` code at the wire level (no
  `X-MockingBird-Node-Error` header exists there) -- a genuine, disclosed
  Node-protocol gap, not fixed here because it requires touching and
  redeploying the separate `mockingbird_camera_node` package, out of this
  milestone's bounded Host-side scope.
- `engine_runtime._default_capture_profile_alignment`'s own live profile
  lookup (feeding `fov_alignment_proven`/geometry lineage) still silently
  degrades to `not_checked` rather than self-healing when the persisted
  evidence profile is stale at session start -- deliberately left untouched
  (frozen geometry-lineage territory); evidence capture itself is
  unaffected, proven live above.
- The historical v13 trigger was not directly forensically recovered (that
  Node process has long since cycled); this milestone instead established
  the identical failure class live, on the same real hardware, via full
  code tracing and direct reproduction/timing -- the strongest available
  equivalent.
- Reconciliation depends on there being exactly one unambiguous live
  evidence candidate; a Node that genuinely advertises multiple equally
  plausible warm evidence profiles for one camera will still fail closed
  and require a real Stream reconfiguration, by design (Section 13).

## Gate A effect

This milestone does **not** close Gate A.

- **Evidence-capture profile validity / failure observability: CLOSED /
  READY FOR REPRESENTATIVE FIELD RE-PROOF.**
- **Recall + evidence survival: still REOPENED / WAITING FOR FIELD
  RE-PROOF** -- unchanged by this milestone; only a representative field
  cohort with this fix in place can re-measure them.
- The pre-existing Gate A dependency list (items (1)-(13), unchanged in
  substance) and the separate proposal-outcome ledger-cadence dependency
  (Section "V13 ledger-cadence finding") are untouched and remain exactly
  as v13 left them.
- No numeric release budget is invented or advanced by this milestone.

## Decision

**A.**

- Exact v13 symptom chain reconstructed from its own report and direct code
  tracing.
- Live failure reproduced directly on the real reference Camera Node, using
  the exact named production method.
- First irreversible error established precisely (a discarded, already-
  available Node header).
- Root cause classified (B) and proven live, not merely inferred; the
  competing timeout hypothesis was independently measured and found
  unsupported.
- Implementation contract locked before any production edit, and followed
  exactly; the correction sits at the causal layer only.
- No generic/blind retries; stale-profile recovery is deterministic and
  fails closed on ambiguity; unrecoverable failures remain conservative
  (proven live and by test).
- Underlying failure causes are now observable (a real, bounded taxonomy;
  bounded counters reaching the existing `advanced` status payload with no
  schema change).
- No credential leakage; the reference Node was left healthy, unpaired, and
  on its unchanged accepted build.
- Real Camera Node evidence bursts succeed after the fix, repeatedly, both
  through the full unmodified production pipeline and directly at the
  transport layer; real bytes decode correctly; a real `EvidenceCandidate`
  is constructed with real bytes via the exact code path v13 proved
  unreachable.
- A short Observation smoke proves proposals can move beyond universal
  `no_persistable_evidence_bytes` failure, without a field recall/precision
  claim.
- No evidence duplication, structurally and by test.
- Tier 1 green (RED->GREEN proven by bisection, including one real
  regression found and fixed during the same pass); Tier 2 green (686/0,
  one unrelated pre-existing flake isolation-confirmed); Tier 3 correctly
  not run and justified.
- No admission/species/truth semantics changed -- confirmed against the
  full freeze list.
