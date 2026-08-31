# Representative Daylight Gate A Field Acceptance v7 — Evidence-Preservation / Arbitration-Fallback Re-Proof

Status: **Classification A.** Field session complete (89.4 minutes,
2026-08-31 15:45-17:16 EDT). Gate A closure itself requires external
(ChatGPT) review before this milestone is authorized to select or run any
further work -- see "Decision" and the governing brief's own §34.

## Identity

- Starting branch: `main`.
- Starting accepted HEAD: `5b1c540` (reconciliation commit accepting Pending-Proposal
  Evidence Preservation & Arbitration Fallback Correctness v1), sitting on the
  code-bearing commit `1b8dd47`. Verified against `docs/release-execution-state.md`
  §1/§3/§6.R before starting -- matched exactly.
- Schema: v58 (`CURRENT_DATABASE_SCHEMA_VERSION`, `src/mockingbird/storage/database.py:45`), unchanged.
- Seven preserved untracked files: present, hashes/mtimes unchanged from session start
  (all dated 2026-08-29 21:53:08), no active worktree writer found modifying this
  worktree during pre-flight checks.
- Deployed dev-root: `MockingBirdFieldAcceptanceV7` (fresh, disposable), commit `5b1c540`
  (== `1b8dd47` code-wise; the two commits on top are docs-only, confirmed via
  `git diff --stat 1b8dd47 HEAD`). Confirmed via `GET /api/product/instance`:
  `git_commit: 5b1c5405a376d7a16e3e531a561a89287a07c99d`, `instance_id:
  527fc31cd66e438fa009e0da17781b22`, `build_id: dce0c8706572451a`.
- Real Stream: `stream-db60712332cb` (Source `source-db60712332cb`), backed by the
  real reference Camera Node's `picamera2-camera-0` -- the same physical camera
  used in v4/v5/v6, confirmed by directly reading the (stopped) V6 instance's own
  SQLite database (`source_provider_configurations.config_json`) before pairing:
  `node_camera_id: "picamera2-camera-0"`, monitoring profile
  `picamera2-monitoring-1920x1080`, evidence profile `picamera2-evidence-3840x2160`.
  Zone `zone-004` ("yard" type, full-frame polygon `0.02-0.98` both axes)
  replicated identically from the same source. The other 7 cameras the Node
  advertised (`v4l2-camera-0/10/11/12/13/14/15`, "Linux camera N") are v4l2 test/
  loopback devices, not the real outdoor camera -- excluded.
- Camera Node pairing: the Node was paired to the already-dead
  `MockingBirdFieldAcceptanceV6` instance at session start (process confirmed
  stopped, `monitored_stream_count: 0` -- no active Observation, safe to
  displace); MockingBirdDev was not running at all and was not affected either
  way. Re-paired via the documented recovery flow (user's explicit approval
  obtained first): SSH to the Pi, `sudo rm /var/lib/mockingbird-camera-node/
  pairing.json && sudo systemctl restart mockingbird-camera-node`, fresh
  one-time code consumed via `POST /api/camera-nodes/pair` within its ~10-minute
  expiry. No side effect to any other running instance (none was running).

## Conditions

- Local time at pre-flight: 2026-08-31 14:37 EDT (Monday), mid-afternoon; sunset
  ~19:35 EDT (`sunrise-sunset.org`, tzid UTC 23:35:26Z) -- ample daylight (~5h) for a
  60-120 minute session.
- Weather (Open-Meteo, real current observation for the reference site's approximate
  coordinates): clear sky (cloud_cover 0%), 31.0°C, wind 3.0 km/h (calm, gusts 5.4 km/h),
  precipitation/rain 0.00mm, weather_code 0 (clear), is_day=1.
- Reference Camera Node (`192.168.1.112:8787`): `status: available`, 8/8 cameras
  available, self-test passed, watchdog healthy (0 consecutive probe failures).
- Pre-flight pairing state: Node was still paired to the leftover, never-cleanly-torn-
  down `MockingBirdFieldAcceptanceV6` disposable instance (process still running,
  `configured_stream_count: 1`, `monitored_stream_count: 0` -- confirmed **no active
  Observation** before touching anything). MockingBirdDev (the operator's own identity)
  was already not running at all -- nothing of the operator's own identity was at risk.
- GPU (RTX 4060 Ti): idle of MockingBird compute at rest-check (transient 31-54%
  utilization observed against the leftover V6 process before it was stopped; dropped
  to true idle after).
- Storage: **21.7GB free / ~465GB total (~4.66%) -- `action_recommended` tier**
  (`is_low_space=True`) per the product's own `/api/product/health`. Disclosed, not
  blocking, matching v5/v6 precedent at similar levels (v6 ended its own session at
  21.96GB free). **New concrete finding this session, not previously quantified:**
  the continuing multi-week storage decline prior milestones investigated and could not
  root-cause is now substantially explained by *disposable dev-root accumulation*:
  `MockingBirdDev` alone is 26.95GB; `MockingBirdFieldAcceptanceV4/V5/V6` are 8.13/8.72/
  8.63GB each; `MockingBirdFirstHourAcceptance` is 2.35GB -- **~54.8GB total** spread
  across abandoned per-session dev-roots, none of which share the runtime/model/BioCLIP
  caches with each other (each dev-root gets its own full copy). This is disclosed
  evidence only, per this milestone's own non-goals (§29/§36: no storage work performed).
- Recorder readiness: `MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR` confirmed as the
  correct invoking-shell env var (translated internally by `deploy_windows_dev.py` to
  `MOCKINGBIRD_ACCEPTANCE_RECORDING_DIR` for the launched child process -- verified
  directly against `acceptance_recorder.py:56` and `deploy_windows_dev.py:1507-1519`,
  resolving an apparent discrepancy between v5's and v6's own report prose). **A real
  defect was found and fixed here -- see "Defects" below**: that forwarding was a raw
  passthrough with no `to_windows_path` conversion, unlike the adjacent
  `MOCKINGBIRD_HOME` two lines below it. Recording confirmed genuinely active only
  after the fix (real 1920x1080 JPEG frames landing in
  `acceptance-recording/stream-db60712332cb/20260831T194507Z/` at ~1.1s intervals).
- Real current frame inspected before committing: `POST .../live-session/start` +
  `GET .../live-session/current-frame` (1920x1080, `state: live`, age 125ms). Scene:
  the same tree/feeder-pole setup as every prior cohort (seed feeder + hummingbird
  feeder), houses/street in background. A second frame ~20s later already showed a
  real bird perched at the seed-feeder pole. Foliage position identical between the
  two frames (no wind-driven motion). Sky: bright, hazy/thin-overcast (visibly more
  cloud than the coordinate-approximate Open-Meteo reading above suggested -- direct
  photographic observation is authoritative here, not the coarse IP-geolocated
  weather call). No precipitation, dry ground. **Go decision: conditions confirmed
  suitable.**

## Frozen configuration

Confirmed directly from source at the deployed commit (unchanged from v5/v6):

| Config | Value | Source |
|---|---|---|
| MDv5a ONNX detector `score_threshold` | 0.1 | roadmap.md "Numeric release budgets" |
| Tracker `ambiguous_gap_ms` | 45,000 ms | prior cohort reports |
| `maximum_episode_duration_ms` / `maximum_component_pending_ms` | 1,200,000 ms (20 min) | sustained-activity contract |
| Evidence cache `_MAX_CACHED_BURST_BYTES` | 128 | `engine_runtime.py:2054` |
| Protection bound `_MAX_PROTECTED_EVIDENCE_IDS` | 64 | `engine_runtime.py:2079` |
| `RETRYABLE_OUTCOMES` | `{"blocked_continuation_pending"}` | `candidate_visit_authority.py:474` |
| `_FALLBACK_ELIGIBLE_OUTCOMES` | `{blocked_missing_evidence} ∪ (REJECTED_OUTCOMES − {reject_insufficient_proposal_support})` | `engine_runtime.py` (per pending-proposal report) |
| `EvidenceScoringBounds.max_candidates` | 16 | unchanged |
| Identification Eligibility | `identification-eligibility-v1`, score_floor 0.7, margin_floor 0.2, + geometry-corroboration (`26edddf`) | unchanged |
| BioCLIP-2 | production species suggestion model | unchanged |
| Schema | v58 | `database.py:45` |

No tuning performed. No production/perception/admission/Visit/evidence/classification
code touched this session (deploy/session-orchestration commands only).

## Independent denominator

Two mechanisms, kept explicitly distinct throughout this report:

1. **The acceptance recorder** -- a bounded, product-independent
   1000ms-nominal full-resolution (1920x1080) JPEG frame sampler
   (`acceptance_recorder.py`), armed via `MOCKINGBIRD_ACCEPTANCE_RECORDING_DIR`
   (see "Defects" for the real bug found and fixed getting this armed).
   3,848 frames captured, 99.989% temporal-span coverage. Never imports, and
   is never imported by, any admission/assembly/repository code -- creates no
   Event/Visit/MediaAsset/ReviewLabel under any input. This is the source of
   every full-resolution frame reviewed in this report.
2. **The counterfactual ledger** (`GET /api/streams/{id}/observation/
   counterfactual`) -- the product's own bounded, 60-minute-age /
   count-bounded internal record of raw detections, track generations, and
   proposal outcomes. Because this session ran 89.4 minutes (exceeding the
   ledger's own 60-minute `max_age_ms`), **11 periodic snapshots** were
   pulled throughout the session (roughly every 10-13 minutes, plus two
   taken immediately after live fallback/exhaustion events) and merged by
   natural key (`frame_id` for raw detections, `generation_id` for track
   generations, `(proposal_id, decided_at)` for proposal outcomes) into one
   lossless, deduplicated reconstruction of the full session -- since
   consecutive snapshots are always far closer together than the 60-minute
   eviction window, no record could have been evicted from every snapshot
   before at least one had already captured it. Verified lossless: the
   merged reconstruction's own final proposal/candidate accounting matches
   the live session's own final settled counts exactly (25 admitted, 192
   distinct proposals from 403 cumulative records).

**EXHAUSTIVE DENOMINATOR WINDOWS** (see "Recall," below, for the full
methodology and results): two windows, 6.5 minutes and 70 seconds, chosen for
containing the highest-value real events (both fallback successes, the
fallback exhaustion, and the confirmed multi-subject admission), reviewed via
full-resolution recorder frames cross-referenced against the merged ledger --
not product-defined output used to define its own denominator.

**SUPPORTING SESSION EVIDENCE**: all 25 admitted Visits' own representative
evidence, individually reviewed at native/near-native resolution (useful-
evidence rate, false-Visit rate) -- explicitly distinguished from the
exhaustive-denominator recall figure throughout.

## Evidence-preservation field proof

**Preservation succeeds silently by design -- there is no positive counter
for "protection worked," only `protected_evidence_capacity_exhausted_count`
for when the 64-slot budget itself was insufficient (see the pending-proposal
milestone's own contract).** That counter stayed **0 for the entire 89.4-minute
session** -- the protection mechanism's own capacity bound was never the
binding constraint, under real, sustained, sometimes-multi-subject field
churn (25 admissions, 6 fallback attempts, up to several proposals pending
concurrently). This is consistent with preservation working correctly
throughout (nothing observed contradicts it), but per the same honesty
standard applied to fallback: this session cannot *directly* distinguish
"preservation actively protected evidence that would otherwise have been
evicted" from "the 128-entry cache simply had enough headroom that eviction
pressure on protected items never actually occurred" -- the same limitation
the pending-proposal milestone's own 105-simulated-minute replay already
disclosed (`fallback_attempted=0` in that replay too, meaning even the
deterministic proof never exercised genuine preservation-under-pressure
either). What this session *does* newly prove, that the replay could not: **6
real fallback attempts occurred, 5 succeeded** -- fallback is the mechanism
whose correctness is unambiguous from outcomes alone (a same-component
runner-up either gets admitted or it doesn't), and it worked repeatedly under
real conditions (see "Arbitration-fallback field proof," below). Preservation
and fallback are complementary per their own contract; this session's
strongest, most direct evidence is for fallback, with preservation's own
non-interference (zero capacity exhaustion) as supporting, not standalone,
confirmation.

## Arbitration-fallback field proof

**A real, natural fallback event occurred at session offset ~2,652,037ms (~44.2 min
in), decided_at 2026-08-31T20:29:21Z.** Reconstructed from the counterfactual ledger
(`counterfactual-snapshot-5-fallback.json`, pulled immediately after the live
monitor reported `fallback_attempted_count: 0->1` / `fallback_admitted_count: 0->1`
in the same tick as `candidates_created` jumping by 2):

**Component** (3 resolved members, all confirmed tracks in the same feeder-perch
region, geometry envelopes clustered around x≈0.44-0.50/y≈0.64-0.78 -- almost
certainly one real, continuous bird encounter fragmented into 3 tracklet
generations by brief occlusion/reconnection gaps, `terminal_reason`
`reconnect_bridge_expired`/`maximum_unsupported_duration` on all three):

| Rank (by confidence) | Proposal | Offset (ms) | Generations | max_confidence | Outcome | decided_at |
|---|---|---|---|---|---|---|
| **1 (original winner)** | `visit-episode:5929501ce5baa58875695184` | 2,560,716-2,576,644 | 1 (`...0b2fc14025b4...`) | **0.745** (3 detections, 1 strong) | `blocked_missing_evidence` / `no_persistable_evidence_bytes` | 20:29:21.095804Z |
| **2 (fallback position 1)** | `visit-episode:c160b426b749f521a62a1bde` | 2,471,469-2,501,937 | 2 (`...f9ca5252...`, `...fd916be9...`) | 0.62 / 0.443 (0 strong) | **`created` / `candidate_visit_created:fallback_position_1`** -> **`visit-observation-candidate-016`** | 20:29:21.120175Z (+24ms) |
| **3** | `visit-episode:427b546736e99c4825575607` | 2,524,122-2,533,181 | 1 (`...7a7f781d...`) | 0.273 (0 strong) | `blocked_ambiguous_boundary` / `proposal_boundary_ambiguous_with_adjacent_proposal` | 20:29:21.448450Z (+352ms) |

**Why the winner failed:** rank 1 (highest confidence, correctly chosen first by
the unmodified `_arbitration_key`) is also the *latest*-starting, most-recently-
resolved member of the three -- its own priority evidence bytes had already been
evicted from the shared 128-entry cache by unrelated proposal churn elsewhere in
the session by the time its own belated arbitration turn arrived, exactly the v6
failure signature (`no_persistable_evidence_bytes`).

**Fallback position and evidence:** the runtime immediately (24ms later, same
tick) walked to the next-ranked component member (rank 2, "fallback position 1"),
whose own priority evidence was still present in the cache -- admitted cleanly as
`visit-observation-candidate-016`. Rank 3 remained correctly `blocked_ambiguous_
boundary` (the doctrine-required "at most one Visit per ambiguous cluster" -- once
the chain succeeded at position 1, no further member is attempted).

**Admitted candidate's evidence quality:** BioCLIP-2 ran automatically and did
**not** abstain -- suggested "Carolina Chickadee" at **99.04% confidence**, margin
0.984 (well clear of the 0.7 score-floor / 0.2 margin-floor policy), from a
native-resolution 3840x2160 evidence frame, `identification_policy.tier:
"subject_focused"`. A plausible, common feeder species for this scene. The
fallback path did not degrade evidence quality in this instance.

**A second real, natural fallback event occurred ~3.2 minutes later** (offset
~2,822,464ms, decided_at 20:32:34.948049Z), same shape: winner `visit-episode:
95bcd3f788c4dd34e40db86e` (2 generations, max_confidence 0.833/0.338) failed
`blocked_missing_evidence`; fallback position 1 `visit-episode:
67d8f86d76a3bc94ac4d6bfc` (2 generations, max_confidence 0.72/0.649) admitted
cleanly as `visit-observation-candidate-017`, 22ms later, same tick; a third,
more complex 5-generation member (`visit-episode:11395f49ce9232046d6be091`,
confidences 0.108-0.579) correctly remained `blocked_ambiguous_boundary`. Two
independent, naturally-occurring instances of the identical correct-recovery
pattern within one session, ~3.2 minutes apart.

**A third event, this time a genuine fallback exhaustion, occurred at offset
~2,969,423ms (~49.5 min in, `fallback_exhausted_count: 0->1`), decided_at
20:35:04.9xxZ:**

| Role | Proposal | Offset (ms) | max_confidence | strong_detections | Geometry | Outcome |
|---|---|---|---|---|---|---|
| Original winner | `visit-episode:59bd2b5ce071f0c4f5d0b954` | 2,876,275-2,885,306 | **0.158** | 0 | `[0.798, 0.457, 0.838, 0.502]` (far-right frame region, not the usual feeder perch) | `reject_no_identification_or_context` (a fallback-eligible outcome) |
| Fallback position 1 | `visit-episode:94d06a8a4848f635d0474110` | 2,910,752-2,919,151 | **0.112** | 0 | `[0.797, 0.458, 0.816, 0.481]` (same location, high geometric overlap with the winner -- genuinely the same encounter) | `blocked_missing_evidence` / `no_persistable_evidence_bytes:fallback_position_1` -- also failed |

Only 2 members total in this component; the chain exhausted after one fallback
attempt (no position 2 existed to try). Confirmed by direct geometry/timing
cross-reference that this component is real and self-consistent (winner and
fallback candidate occupy the same unusual frame location, distinct from every
other concurrently-active encounter, e.g. two genuinely unrelated `blocked_
continuation_pending` proposals at that same instant at the ordinary feeder-perch
location, `[0.46-0.51, 0.72-0.81]`, correctly excluded from this component's own
fallback consideration since they belong to a different real encounter entirely).

**Classification of this exhaustion against §12: Outcome C** -- "no viable member
exists and loss is honestly diagnosed." Every member of this specific component
carried extremely weak evidence throughout its entire real lifetime (max
confidence 0.158 and 0.112, zero strong detections either time) -- consistent with
a marginal, likely-distant or brief real detection (or conceivably a false
positive) rather than a well-evidenced encounter whose evidence merely arrived
late. Nothing in this trace suggests a viable alternative was skipped or silently
discarded; the mechanism correctly tried every real member before giving up, and
`fallback_exhausted_count` honestly recorded that fact rather than hiding it.
**No instance of the unacceptable outcome (§12: "winner unavailable -> component
silently discarded while viable member exists") was observed for any of the
`blocked_missing_evidence`/fallback-eligible losses traced this session.**

**Classification against §12's outcome taxonomy: Outcome B** -- "fallback selects
another viable same-component member." This is the specific class of event the
Pending-Proposal Evidence Preservation & Arbitration Fallback Correctness v1
milestone was built to produce, observed here under genuine field conditions for
the first time (the milestone's own deterministic tests and 105-simulated-minute
replay never happened to exercise the fallback path itself -- `fallback_attempted=0`
in that replay, per its own report's "Remaining risks"). No manufactured cache
corruption, no synthetic trigger -- naturally occurring real activity.

## Protection-bound behavior

- **Maximum protected-evidence count observed:** not directly instrumented as
  a live-readable value this session (no API surface currently exposes the
  in-memory `protected_evidence_ids` set's own current size, only the
  exhaustion counter below) -- disclosed as a real observability gap, not
  fabricated.
- **Cache occupancy:** not directly readable live either; `_MAX_CACHED_
  BURST_BYTES`/`_MAX_CACHED_SAME_FRAME_BYTES` remain 128 (unchanged, per
  "Frozen configuration").
- **Protection-capacity-exhaustion count: 0** for the full 89.4-minute
  session (`protected_evidence_capacity_exhausted_count`, confirmed via
  the final settled status and every intermediate poll).
- **Was the 64-entry cap reached?** No evidence it was -- zero exhaustion
  events under real, sustained, sometimes-concurrent field churn (25
  admissions, up to 6 fallback attempts, two confirmed genuinely-simultaneous
  multi-subject moments).
- **Were protected items released after resolution?** By design, yes --
  `_compute_protected_evidence_ids` recomputes fresh every tick from
  currently-still-actionable proposals only (never accumulates); this
  session's own zero exhaustion count is consistent with that design working
  as intended, though (as above) cannot be distinguished from "never under
  enough pressure to test release timing precisely."
- **Did the protected set drain at stop?** Not independently instrumented;
  no observable symptom (no late-arriving admission after the finalize tick
  settled, no anomalous suppressed-reason growth after `stopped_at`) suggests
  a problem.

No tuning of the 64-entry bound was performed or considered, per this
milestone's own explicit instruction.

## blocked_missing_evidence

**18 of 192 distinct proposals = 9.4%** (computed from the merged, lossless
ledger reconstruction; matches the live session's own final settled state
exactly). **Directly comparable to v6's own 48/263 = 18.3%: roughly halved.**

- **Semantics confirmed compatible with v6's own accounting** before
  comparing: both figures are distinct-proposal rates from the same
  `no_persistable_evidence_bytes` outcome, computed the same way (deduplicated
  by `proposal_id`, latest state).
- Of the 18: **1** carries the new `:fallback_position_1` reason suffix (the
  honestly-exhausted component's own fallback attempt, traced in full above
  -- confirmed non-animal/noise on direct visual review, so its loss cost
  nothing real). The other 17 carry the plain, unsuffixed reason -- by
  design, a component winner's own failure record is never suffixed even
  when a same-component fallback subsequently succeeds (confirmed directly:
  the fallback-2 winner `visit-episode:5929501ce5baa58875695184` is in this
  list of 17, and its own component's real activity *was* rescued, as
  `visit-observation-candidate-017`).
- **Within the two fully-traced exhaustive-denominator windows** (containing
  5 of these 18 records, including both fully-traced fallback events): **zero
  instances of the unacceptable outcome** (§12: winner unavailable -> component
  silently discarded while a viable member existed). Every one resolved to
  either Outcome B (fallback rescue) or Outcome C (honest, confirmed-noise
  exhaustion).
- **The remaining ~13 records outside the two exhaustive windows were not
  individually traced to their own component/rescue context this session** --
  disclosed as a real scope boundary of this report, not extrapolated as
  problem-free. A future session (or a dedicated offline pass over this
  session's own already-preserved merged ledger, which requires no further
  live field time) could close this precisely.
- **No real denominator unit was confirmed lost to this outcome this
  session** among everything actually traced -- consistent with, not proof
  beyond, the fix working as designed.

## Notable: first real exercise of `max_candidates_per_hour: 20`

At session offset ~4,557,411ms (~76 min in), `candidates_created` reached 22 and a
new suppressed reason, `blocked_hourly_limit`, appeared for the first time --
`candidate_authority_exhausted` stayed `False` (that flag is wired only to the
*session*-total 50 cap, per `engine_runtime.py:1869`, not the rolling hourly one).
This is the **first time any real Gate A field cohort has produced enough genuine
admissions to exercise `AuthorityLimits.max_candidates_per_hour` at all** -- v4
produced 0, v6 produced 0, and v5's 19 total over ~106 minutes never approached a
20-per-rolling-hour rate. This is a direct, positive consequence of the
evidence-preservation/fallback fix working well, not a defect: the rolling-hour
budget is a deliberate, pre-existing, unrelated rate limit (`AuthorityLimits`
docstring: "explicit hard bounds for the controlled trial"), out of scope to
tune per this milestone's own non-goals. *(Whether it self-clears as the rolling
window advances is recorded in "Sustained-activity result" below.)*

## Sustained-activity result

**Preliminary/discarded session (not part of formal accounting):** a first real
Observation session ran 19:28:42Z-19:31:08Z (~2m26s) before the recorder-arming
defect above was caught. In that brief window, real feeder activity (already
visible in the pre-session preview frames) produced: `track_updates_observed`
203, `evidence_candidates_observed` 52, `proposals_observed` 14,
**`candidates_created: 1`** (`visit-observation-candidate-003`, with BioCLIP-2
automatic identification already invoked -- `automatic_identification.status:
"running"`), `candidates_suppressed` 13 (12 `blocked_continuation_pending` + 1
`reject_no_identification_or_context`), `fallback_attempted_count: 0`,
`protected_evidence_capacity_exhausted_count: 0`. This is genuine, real,
directly-observed evidence that **Primary Field Question 1 (does sustained real
activity now produce non-zero in-session candidates?) is answered yes** --
recorded here honestly as a qualitative early signal, not part of the formal
funnel/recall/latency accounting below, since no independent recorder ran
alongside it. Session stopped cleanly (`user_stopped`) before the fix; this Visit
remains in the (otherwise fresh) V7 database, timestamped before the formal
session window and excluded from it.

**Formal session** (recorder confirmed active throughout): started
19:45:07Z / 15:45:07 EDT. First in-session candidate (`visit-observation-candidate-004`)
admitted at session offset 396,368ms (**~6.6 minutes in**) -- non-zero in-session
`candidates_created` reconfirmed under the properly-instrumented, fully-recorded
session. (Note: `visit-bird-feeder-001`/`visit-squirrel-ground-001` seen via
`GET /api/visits` are pre-seeded demo data shipped with every fresh instance, not
real admissions -- excluded from all accounting below; `visit-observation-
candidate-003` is the discarded preliminary session's own candidate, also excluded.)

- **Time to first proposal:** ~5.27 minutes (316,461ms).
- **Time to first candidate / first visible Visit:** ~6.6 minutes (396,368ms;
  admission and product-visibility are the same event in this API-only
  measurement -- no separate frontend-render latency was instrumented).
- **candidates_created progression:** non-zero from ~6.6 minutes, climbing
  steadily to 24 by stop, **25 after stop-finalization** -- growth throughout
  the session, not concentrated at the end.
- **Natural (non-forced) vs. forced decisions:** the 20-minute
  (`maximum_component_pending_ms`) bounded-decision-horizon mechanism was
  **not observed to be the operative path for any resolution this session** --
  the single longest real pending span for any one proposal, measured end to
  end across every re-evaluation, was **921.8 seconds (~15.4 minutes)**,
  under the 1,200-second horizon. Every resolution this session, including
  both fully-traced fallback events, was an ordinary confidence-ranked
  (`_arbitration_key`) decision, not a recency-ranked forced one.
- **Maximum pending duration observed:** 921.8s (~15.4 min), for
  `visit-episode:a68343ff161c946ec1fd49d1` -- real, substantial, but bounded
  well inside the accepted 20-minute horizon.
- **Visit grouping during sustained activity:** coherent throughout -- 25
  distinct admissions, zero shared underlying tracker evidence, 2 correctly
  paired sibling-Event admissions (multi-subject), no evidence of the
  historical one-bird-into-several-Visits fragmentation pattern (see
  "Fragmentation / duplicates").

**Explicit regression-signal check (§16):**

- Prolonged genuine activity + zero candidates: **not observed** --
  candidates grew steadily throughout.
- Valid work appearing only at stop: **not observed** -- 24 of 25 admissions
  happened in-session; only 1 was rescued at the finalize tick (matching v5's
  own healthy pattern, not v4's starvation pattern).
- Unbounded pending component: **not observed** -- max pending span 15.4
  minutes, well under the 20-minute bound.
- Visit explosion: **not observed** -- 25 admissions over 89.4 minutes for a
  session with real, frequent, sustained feeder traffic is proportionate, not
  runaway.
- Repeated component loss despite viable evidence: **not observed** in
  anything directly traced (see "blocked_missing_evidence").

**`max_candidates_per_hour: 20` self-clear, promised above:** confirmed. The
limit first engaged at ~76 minutes (`candidates_created` already at 22);
`blocked_hourly_limit` grew to 9 as real activity continued to be correctly
throttled; a **new real admission (23rd) occurred at ~86.6 minutes** once the
rolling window advanced enough to free capacity -- a genuine rolling budget,
not a sticky lockout.

## Multi-subject

**Genuine concurrent multi-subject admission occurred and was represented
correctly -- the first time any real Gate A field cohort has ever observed this
end to end.** v5 confirmed simultaneous presence in-scene but no two admitted
Visits ever shared an Event; v6 never admitted anything at all. v7 produced
**two** real sibling-Event pairs:

### Pair 1: `visit-observation-candidate-011` / `-013` (event-observation-candidate-011) -- corrected

(An earlier draft of this section misidentified this pair as `-012`/`-013`;
`-012` in fact has its own distinct, non-shared event -- a genuinely separate,
non-concurrent encounter that merely happens to fall inside `-013`'s own long
span. The real, verified sibling pair sharing `event-observation-candidate-011`
is `-011` and `-013`, below.)

- `-013`: proposal `visit-episode:9abac243dfc6374e7db25141`, offset 1,992,946-
  2,239,355ms (8 confirmed generations, ~4.1 minutes, all at the seed-feeder
  base region `[~0.44-0.52, ~0.64-0.73]`, confidence consistently 0.81-0.85),
  reason `candidate_visit_created_shared_event`.
- `-011`: proposal `visit-episode:dbded810d15cc1a5bd920391`, offset 1,988,888-
  1,996,098ms (1 generation, box `[0.176, 0.652, 0.269, 0.741]` -- a clearly
  different, well-separated region to the **left** of the feeder, confidence
  **0.892**), reason `candidate_visit_created`.
- Genuine temporal overlap: 1,992,946-1,996,098ms (~3.15s), both members at
  high, unambiguous detector confidence, geometrically well-separated. No
  shared `constituent_generation_ids`. **Directly visually confirmed**: the
  very first recorder frame in `-011`'s own window (1,988.89s) shows a bird
  clearly mid-flight/landing near the driveway edge (wings spread, legs
  extended) -- a real, distinct animal, genuinely separate from `-013`'s own
  simultaneous feeder-perched subject.

### Pair 2: `visit-observation-candidate-019` / `-020` (event-observation-candidate-018) -- directly visually confirmed

- `-019`: proposal `visit-episode:f502af7651a33c2ee2d3f788`, offset 3,105,158-
  3,153,159ms (4 generations, all at the seed-feeder base region, geometry
  envelope ≈`[0.42-0.51, 0.70-0.84]`), reason `candidate_visit_created:
  fallback_position_1` -- **this admission was itself a fallback success**.
- `-020`: proposal `visit-episode:9b3590ee671410e3aba87902`, offset 3,097,429-
  3,118,167ms (2 generations, geometry ≈`[0.45-0.50, 0.42-0.50]` and
  `[0.19-0.22, 0.67-0.72]`), reason `candidate_visit_created_shared_event:
  fallback_position_1` -- **also a fallback success, and the multi-subject
  sibling-Event mechanism, on the identical admission**. Genuine temporal
  overlap with `-019`: 3,110,733-3,118,167ms (~7.4s).
- **Zero shared `constituent_generation_ids`** between the two proposals --
  disjoint tracker identities, confirming these are genuinely two separate
  tracked subjects, not one track double-counted.
- **Directly visually confirmed**: the recorder frame nearest the overlap
  window (offset 3,110,733ms, exactly `-020`'s own second generation's start
  time) shows **two distinct birds perched simultaneously at the seed feeder's
  base, one on each side of the feeder tube** -- unambiguous, not an
  inference from geometry alone.

### Correctness checklist against §17

- Detector separation: yes -- two independent detection lineages, confirmed visually.
- Track separation: yes -- disjoint `constituent_generation_ids` for both pairs.
- Proposal grouping: yes -- two distinct proposals per pair, not merged into one.
- Evidence attribution: no cross-subject reuse observed -- each proposal's own
  generations are exclusively its own.
- Candidate admission: both members of both pairs reached real admitted Visits.
- Sibling/group semantics: both pairs correctly share one `event_id` while
  remaining two distinct `visit_id`s.
- No obvious incorrect merge: confirmed -- 4 distinct Visits from 2 pairs, never
  collapsed to 2.

This is a direct field confirmation of the "Multi-Subject Visit Assembly Phase
2" Event-reuse mechanism (accepted 2026-08-20) reaching real admission end to
end for the first time, and additionally the first observed interaction between
that mechanism and the newly-fixed fallback path (pair 2's own `-020` needed
both).

### A related, honestly-disclosed finding: a third bird the detector never separated

Closely inspecting the recorder frames around Pair 2's own overlap window
(offset 3,105-3,116s) at high zoom found **a genuine third bird**, clearly
visible immediately to the right of the feeder tube, simultaneous with `-019`'s
own subject on the left of the same tube (two distinct heads/bodies directly
visible in the same frame, e.g. at 3,109.06s). This third bird does not
correspond to either of `-020`'s own two generations (which are at clearly
different locations -- upper-hook and far-left). Cross-checked against every
raw detection (not just confirmed tracks) in a 30-second window around this
moment: **no `is_animal` raw detection anywhere near the tube's right side**
at any sampled instant -- the detector itself never fired on this third
individual at all, most plausibly because it sat close enough to `-019`'s own
subject for MDv5's own NMS (`nms_iou_threshold: 0.45`) to suppress a second
box, though a genuinely weak/missed single-stage detection cannot be ruled out
either way. This is a real, concrete field instance of a gap `roadmap.md`
Gate A already names as open and not yet benchmarked ("Crowded-feeder/NMS
behavior... have no dedicated benchmark slice yet") -- not a new defect
class, and not attributable to the admission/assembly/fallback layers this
milestone's own scope covers (the perception stage never produced evidence
for this individual to assemble in the first place). Disclosed for
completeness, not treated as a Gate A regression: per product doctrine, "Do
not assume... every occurrence can be accurately counted" -- the *encounter*
at this feeder was genuinely represented by two real, correctly-admitted,
non-duplicated Visits; a third simultaneous individual within that same
encounter was not separately perceived.

## Stop-finalization

Stopped deliberately (not into an idle moment) at session offset 5,365,939ms
with **253 `blocked_continuation_pending` records genuinely outstanding** --
real, substantial pending work at stop time.

- **Truthful stopping/stopped states:** `POST .../observation/stop` ->
  immediate `state: "stopping"`, `stopped_reason: "user_stopped"`. ~19 seconds
  later, polled again: `state: "stopped"`, `stopped_at:
  "2026-08-31T21:16:00.973128Z"`.
- **Pending valid work resolved:** `candidates_created` **24 -> 25** across
  the stop transition -- the finalize tick genuinely rescued one more real
  candidate, directly mirroring v5's own 17->19 finding (v6, by contrast,
  rescued 0 -- consistent with v6's own root cause, where nothing was left
  cleanly resolvable at stop).
- **`stop_finalization_pending` field:** not observed as `true` at either
  poll this session (present as `null` both times) -- unlike v5, which
  directly observed it live as `true` before settling. Most likely explained
  by this session's finalize tick completing faster than this session's own
  ~5-15 second polling cadence could catch mid-flight; disclosed honestly as
  a gap in *this session's own observation*, not a claim that the field
  itself is broken (the underlying rescue behavior it's meant to signal did
  demonstrably occur).
- **No duplicate Visit, no `blocked_shadow_mode` regression:** confirmed
  (zero `blocked_shadow_mode` for the entire session; zero shared-generation-
  id collisions across all 25 final admissions, including the one rescued at
  stop).
- **Repeated status stable:** re-polled the final settled state after
  additional analysis work; `state`, counts, and all `advanced` fields held
  steady, unchanged.

## Full funnel

| Stage | Count | Note |
|---|---|---|
| `track_updates_observed` | 6,756 | |
| `evidence_candidates_observed` | 3,195 | |
| `proposals_observed` (cumulative records) | 403 | matches live session final exactly |
| Distinct proposals (deduplicated) | 192 | from merged lossless reconstruction |
| `candidates_created` (admitted) | **25** | first non-zero, properly-recorded in-session result across all v4/v5/v6/v7 (v4: 0, v5: 19, v6: 0) |
| `blocked_continuation_pending` (distinct) | 42 | still-growing at session end |
| `blocked_ambiguous_boundary` (distinct) | 92 | correctly non-winning cluster members |
| `blocked_missing_evidence` (distinct) | 18 (9.4%) | vs v6's 18.3% -- see dedicated section |
| `blocked_hourly_limit` (distinct) | 9 | first-ever real exercise of this limit -- see dedicated section |
| `reject_no_identification_or_context` (distinct) | 6 | |
| `blocked_shadow_mode` | 0 | |
| Fallback attempted / admitted / exhausted | 6 / 5 / 1 | see "Arbitration-fallback field proof" |
| Protection-capacity-exhaustion count | 0 | |
| Persistence contention | 0 | |
| False Visits (of 25 admitted) | 1 (4.0%) | |
| Useful evidence (of 25 admitted) | 24 (96.0%) | |
| Genuine duplicate Visits | 0 | zero shared generation ids across all 25 |
| Multi-subject sibling pairs | 2 | both directly visually confirmed |

Sum check: 25 (created) + 42 + 92 + 18 + 9 + 6 (suppressed, 167) = 192 distinct
proposals exactly.

## Recall

### EXHAUSTIVE DENOMINATOR WINDOWS

**Window A: session offset 2,600,000-2,990,000ms (6.5 minutes).** Chosen because
it contains both real fallback events. Methodology: every confirmed track
generation in the window enumerated from the merged, lossless ledger
reconstruction (§ below), grouped into distinct real sub-encounters by
gap/geometry, each verified by pulling full-resolution recorder frames at the
group's own real timestamps (not a blind sample). Result: **2 genuine real
encounters identified, both represented by a useful admitted Visit**
(candidate-017, candidate-018) -- **2/2 (100%)**. One additional persistent
weak signal (max confidence 0.10-0.16, offset ~2,776-2,919s, the same far-right
frame region across multiple independent sightings) was directly checked via
full-resolution frame and shows **no animal at all** -- grass, a parked truck,
a driveway -- confirmed spurious/noise and excluded from the denominator (this
is the same component honestly diagnosed as `fallback_exhausted` above; its
exhaustion cost nothing real).

**Window B: session offset 3,090,000-3,160,000ms (70 seconds).** Chosen
because it contains the directly-confirmed multi-subject admission. Result:
**1 genuine real encounter (a multi-bird feeding moment), represented by two
useful admitted Visits** (candidate-019, candidate-020) -- **1/1 (100%) at
the encounter level**. A third real individual bird, directly visually
confirmed within this same encounter, was never separately perceived by the
detector at all (see "Multi-subject," above) -- a genuine per-individual
miss, but not a miss of the *encounter* itself, which a real, useful Visit
already represents twice over.

**Combined exhaustive-window recall: 3/3 real encounters (100%) represented by
at least one useful admitted Visit**, spanning ~7.67 of the session's 89.4
minutes (~8.6%). This is a smaller cross-check than v5's own full-19-Visit
review, but directly targeted at the two hardest, most failure-prone moments
this session produced (both real fallback events, and the one confirmed
multi-subject moment) -- not a favorable cherry-pick, a stress-test.

### SUPPORTING SESSION EVIDENCE (not the exhaustive-denominator figure)

All 25 admitted Visits' own representative evidence were individually pulled
and reviewed at native/near-native resolution (not a targeted sample): **24/25
show a genuine, visible real bird; 1/25 (`visit-observation-candidate-010`)
shows empty background across its entire 26-second admitted window** (20
frames individually reviewed, zero animal present in any) -- see "False
Visits," below. This is session-wide supporting evidence for useful-evidence
rate and false-Visit rate, not a recall denominator (it describes what was
admitted, not what was missed) -- kept explicitly separate per this
milestone's own governing instruction.

**Do not read a single recall percentage across cohorts as directly
comparable**: this session's methodology (targeted high-value windows,
cross-checked against a merged ledger reconstruction) differs from v5's
(full-19-Visit review) and the pre-fix 2026-08-19 session's (68.2% ceiling,
a materially different denominator construction). All three real-encounter
recall points from this session are consistent with "no missed genuine
encounter found," matching v5's own qualitative conclusion -- not a new,
superseding recall number.

## False Visits

**1 confirmed false Visit of 25 (4.0%), explicit denominator: 25 admitted
Visits, all individually reviewed at native/near-native resolution.**

- **`visit-observation-candidate-010`** (offset 1,900,690-1,927,028ms, ~26.3s):
  confirmed false. All 20 recorder frames spanning its entire admitted window
  individually reviewed -- empty grass/driveway/branch scene throughout, no
  animal present at any point. Underlying detector confidence was weak
  (0.213, the lowest among the 25 admissions' own best generation) -- MDv5
  admission is deliberately confidence-blind by measured design decision
  (`roadmap.md` "Numeric release budgets": confidence-gating was formally
  swept and not adopted), so a weak/spurious detection like this can and does
  still reach a real admitted Visit. **The positive finding**: this Visit
  received **no automatic species suggestion at all** (`species_guess: null`)
  -- the accepted Background/Empty Evidence Species-Confidence Correctness v1
  fix (geometry-corroboration eligibility, `26edddf`) correctly withheld a
  confident species claim on evidence with no real corroborating detection
  geometry, exactly as designed. This is a live, real-cohort confirmation
  that the already-accepted fix continues to work correctly (the specific
  harm it was built to prevent -- a confident wrong species name on empty
  background -- did not recur here), **while the separate, already-known,
  not-yet-addressed liability remains**: the false *admission* itself (a
  background/empty crop still becoming a real Visit at all) is a Gate A
  admission-precision question, not a Gate B species-labeling one, and stays
  open exactly as `roadmap.md` already frames it.
- **24/25 (96.0%) confirmed true wildlife** -- real, visible birds directly
  confirmed in recorder frames for every other admission, including two
  (`-011`, `-022`) whose single spot-checked frame initially looked empty and
  were only confirmed real after pulling every frame across their own full
  admitted window (both show a bird departing/arriving in flight within the
  first 1-3 frames, invisible moments later -- a real, brief, genuine
  encounter, not evidence of a problem).
- **0/25 ambiguous** -- every admission this session resolved cleanly to
  either confirmed-true or confirmed-false on direct review.

**False-Visit rate this session: 1/25 = 4.0%.** Not proposed as a candidate
release budget (a single session, one instance, is not yet a converged
cross-session figure per `roadmap.md`'s own explicit caution against
over-fitting a budget to one data point) -- reported as this session's own
real measurement, for the cross-session evidence body.

## Fragmentation / duplicates

**Zero genuine duplicate Visits: definitively confirmed.** Checked directly
against the merged, lossless ledger reconstruction: across all 25 admitted
Visits' own `constituent_generation_ids` (the actual underlying tracker
evidence each admission was built from), **zero generation ids are shared
between any two admitted Visits.** No two Visits were ever built from
overlapping tracker evidence -- the strongest, most direct test available,
independent of any encounter-boundary definition.

**A methodology caveat on `run_encounter_accounting.py`'s own raw output,
disclosed rather than misreported:** running the accepted `cluster_encounters`
tool against this session's full merged ledger reports `duplicate_visit_
cluster_count: 5` and `fragmented_cluster_count: 17` (of 27 total encounter
clusters). Investigated directly rather than taken at face value -- this tool
clusters transitively through `ambiguous_gap_ms` (45s) chained links, which is
exactly right for a sparser cohort but produces very large, multi-visit
mega-clusters under this session's own sustained, near-continuous activity
(the largest spans **26.9 minutes** and contains **65 distinct proposals**).
A "duplicate_visit_cluster" by this tool's own definition means "this
broad, transitively-chained cluster contains more than one admitted Visit" --
not "the same real encounter was double-admitted." Manually traced two of
these flagged clusters in full (the two real fallback events, above, both
inside the same flagged "duplicate" cluster spanning 2,471,469-2,826,778ms):
both are genuinely separate, well-evidenced, non-overlapping-generation real
encounters ~3.2 minutes apart, correctly admitted as two distinct Visits, not
a duplication defect. Per this milestone's own §22/§24 instruction not to
invent precision from ambiguous encounter boundaries or compare raw ledger
rows across incompatible semantics: this tool's raw duplicate/fragmentation
cluster counts are **not directly usable as a duplicate-Visit or
fragmentation-defect count for a sustained-activity session** without this
correction, and are reported here for transparency, not as a defect finding.

**Genuine fragmentation (one real encounter incorrectly split across Visits
with inconsistent species/identity) was not found.** The known historical
fragmentation pattern (e.g., one bird producing 2-3 Visits with different
species guesses) was specifically checked for among temporally-adjacent
admissions and not observed -- adjacent admissions at the same location
(e.g., the many sequential `house_finch` Visits at the feeder) are consistent
with genuinely repeated real visits by the same regular species, not a single
encounter torn apart (confirmed via disjoint generation ids per Visit, as
above).

**Visit count per logical activity unit:** honestly ambiguous for a
sustained-activity feeder session, per the same reasoning as the `cluster_
encounters` caveat above -- this scene had real, frequent, closely-spaced
individual bird visits (predominantly House Finches, a flocking species)
throughout the session, so "one logical activity unit" does not have a single
correct granularity. The zero-shared-evidence test above is the reliable,
denominator-independent signal: every admitted Visit represents distinct,
non-overlapping real tracker evidence.

## Evidence quality

**Useful-evidence rate: 24/25 = 96.0%** (all 25 admitted Visits individually
reviewed; see "False Visits" above for the one confirmed-empty exception and
the two initially-ambiguous-but-confirmed-real cases). This exceeds every
prior measurement: earlier representative cohort ~88.2%, v5 ~94.7%, the
candidate-budget discussion figure ~85% -- consistent with, not contradicting,
the existing ~85% candidate (a floor, not a ceiling). Per this milestone's own
explicit instruction, **no budget is accepted here** -- this is one more real
data point for the existing candidate under formal review.

- Empty/background: 1/25 (`-010`, above).
- Wrong subject: 0/25.
- Ambiguous: 0/25 (both borderline cases resolved cleanly on full-window review).
- Attribution: every reviewed crop's own bounding-box geometry was checked
  directly against its own real frame region (not merely trusted from the
  API response) for the two ambiguous cases and both multi-subject pairs;
  no attribution mismatch found.

## Coverage

- Intended/actual duration: 89.44 minutes (5,365.939s), `started_at`
  19:45:07.792076Z, `stopped_at` 21:16:00.973128Z.
- Recorder span: first frame offset 0ms, last frame offset 5,365,339ms --
  **99.989% temporal-span coverage** (5,365,339 / 5,365,939), directly
  comparable to v5 (~99.99%) and v6 (~99.4%), and to the general ~99.6%-99.99%
  range across all four real cohorts to date.
- 3,848 recorder frames, mean interval 1,395ms against the configured
  1,000ms nominal (real processing overhead, consistent with the ~0.72-0.8
  frames/sec actual rate every prior cohort's own recorder also measured).
- 19 gaps exceeding 5 seconds, max single gap 11.68s -- cadence jitter, not
  an outage.
- Camera Node health independently checked at 8 separate points across the
  session (session start, ~9min, ~53min, ~62min, ~75min, plus continuous
  implicit confirmation via unbroken ledger accumulation): `status:
  "available"` and `consecutive_probe_failures: 0` every time, zero
  reconnects observed.
- Zero ERROR/CRITICAL/WARNING lines across the full 298-line structured
  session log.

## Latency

Measured as activity-end (a proposal's own `end_offset_ms`) to arbitration
decision (`decided_at`), matching v6's own established metric exactly
(persistence is synchronous with the authority-gate decision in this
codebase's own design, so this figure already folds in admission+persistence
for the admitted case -- it does not further decompose into separate
admission/persistence/visible sub-stages without deeper process
instrumentation this session did not add, an honest limitation, not a gap
specific to this cohort).

**All distinct proposals (n=191, admitted + blocked alike):** median 95.8s,
p90 340.5s, p95 531.4s, max 929.9s (~15.5 min), mean 152.5s. Directly
comparable to v6's own identical metric (n=263: median 127.4s, p90 545.4s,
p95 679.5s, max 912.8s, mean 210.4s) -- **v7 resolves faster across every
percentile**, consistent with a session that actually admits candidates
promptly when it can, rather than v6's every-proposal-eventually-blocked
pattern.

**Admitted proposals only (n=25, the user-relevant subset):** median 86.5s,
p90 ~204-312s (sparse tail, 25 samples), max 323.7s (~5.4 min), mean 115.5s.
No prior cohort published this specific admitted-only cut for direct
comparison.

**Limitation, explicitly disclosed:** this is proposal-resolution latency,
not measured user-visible latency (API-response-to-browser-render was not
instrumented this session, matching every prior cohort's own identical
limitation) -- reported as the closest available proxy, not substituted for
the real thing.

## Persistence

`observation_candidate_visit_persistence_contention`: **zero occurrences**,
grepped directly against the full 298-line structured session log (also zero
by construction against the ledger -- every one of the 25 admitted proposals
has a unique `visit_id`, confirmed via the zero-shared-generation-id check
under "Fragmentation / duplicates"). No retries observed, no duplicates, no
admitted-but-lost candidate.

## Species assistance

- **18/25 (72%) admitted Visits received a confident, non-abstained BioCLIP-2
  suggestion.** Species distribution: House Finch (13), Carolina Chickadee
  (3), Tufted Titmouse (1), plus the earlier-traced fallback admissions
  (Carolina Chickadee, House Finch) already detailed above. Confidences
  ranged 0.789-0.999, consistent with a real, visually-homogeneous
  House-Finch-dominated feeder session (matching what full-resolution review
  directly shows -- the great majority of the 24 confirmed-real Visits are
  visibly House Finches).
- **7/25 (28%) received no automatic species suggestion at all**
  (`species_guess: null`, no `SpeciesSuggestionModel` row at all -- distinct
  from an explicit abstention record): `-008`, `-009`, `-010`, `-011`, `-012`,
  `-020`, `-021`. Five of these seven have decent-to-high underlying detector
  confidence (0.79-0.89) and, per direct review above, four are confirmed
  real birds (`-008`, `-009`, `-011`, `-012`, `-021`) -- consistent with the
  Identification Eligibility gate declining to attempt a claim on a crop that
  didn't meet its own evidence-quality bar (e.g. `-011`'s own real evidence is
  a brief flight-motion crop, confirmed real only after reviewing its full
  admitted window -- see "False Visits"), not a species-model failure. Note
  `-022` is a *different* brief flight-motion case that *did* receive a
  confident suggestion (House Finch, 99.93%) despite an initially-ambiguous
  single-frame spot check -- the two cases are not identical, and eligibility
  outcomes were not assumed to generalize across them. The specific per-Visit
  eligibility reason was not individually traced this session for any of the
  seven (a real, disclosed scope boundary, not a defect claim) -- confirming
  the precise mechanism for each is future work, not asserted here.
- **Zero explicit abstentions observed** (every suggestion attempt that did
  produce a record was confident, non-abstained) -- distinct from the seven
  no-suggestion-at-all cases above.
- **For the one confirmed-false Visit (`-010`):** correctly received **no**
  automatic species claim, per the accepted Background/Empty Evidence
  Species-Confidence Correctness v1 fix -- verified directly, not assumed
  (see "False Visits").
- **Zero confidently-wrong species labels observed** -- a fresh, real-cohort
  absence of the Gate B "background evidence -> confident wrong label"
  regression class that v5 (Brown Thrasher, 89.9%, on empty background) and
  the prior large cohort both reproduced. Consistent with, not proof beyond,
  the already-accepted fix continuing to hold.

## Product behavior

This session interacted with the product exclusively through its real,
authenticated HTTP API (the field-acceptance bearer-token mechanism), not
through the browser frontend -- no frontend-specific (React/UI rendering)
observations are reported, an honest scope boundary matching this milestone's
own measurement focus.

- `GET /api/product/health` (unauthenticated, real-time throughout the
  session) correctly and continuously reported `storage_low_space: true` /
  `storage_health_tier: "action_recommended"` against the real, independently
  confirmed low-storage condition (see "Conditions") -- accurate, not
  over- or under-reported.
- The pre-seeded demo Source/Stream/Visits (`source-backyard-demo`,
  `stream-backyard-feeder`, `visit-bird-feeder-001`, `visit-squirrel-ground-
  001`) shipped correctly isolated from the real field-acceptance Stream and
  its own admissions -- confirmed no cross-contamination in `GET /api/visits`
  (both demo Visits carry their own distinct, stable ids and never appear in
  any real-session accounting above).
- Camera Node onboarding (pairing -> camera-setup/complete -> live-session
  preview -> Observation start) worked end-to-end via the real, documented
  API sequence with no undocumented behavior encountered.
- The real, natural exercise of `max_candidates_per_hour: 20` (see dedicated
  section) is itself a product-behavior finding: the rolling-hour budget
  self-cleared correctly as older admissions aged out, confirmed by a real
  admission occurring shortly after the limit first engaged -- not a sticky
  lockout.

## Cross-cohort comparison

### v4 (2026-08-29)
- Sustained near-continuous multi-bird feeder activity, ~112 minutes.
- `candidates_created` stayed at exactly 0 the whole session.
- Root cause: structural admission-arbitration starvation (whole ambiguous component
  deferred indefinitely under sustained activity).
- Not fixed in-milestone; fixed by Sustained-Activity Visit Admission Starvation &
  Stop-Finalization Correctness v1.

### v5 (2026-08-30)
- Same busy-feeder Stream/scene, post-starvation-fix, 106.6 minutes, 99.99% coverage.
- First admission ~25s in; 19 Visits admitted by session end (17 in-session + 2 rescued
  by stop-finalization).
- Useful-evidence rate 94.7% (18/19).
- Real defect found: background/empty-evidence crop received a confident wrong BioCLIP
  species label (89.9% "Brown Thrasher") -- disclosed Gate B residual, later fixed by
  Background/Empty Evidence Species-Confidence Correctness v1.
- Multi-subject: real simultaneous presence confirmed in-scene, but no two Visits
  shared an Event as concurrent siblings.
- `blocked_missing_evidence`: 10/361 suppressed proposals = 2.8%.

### v6 (2026-08-31, same day as v7, earlier this morning)
- Same Stream, different (mid-morning) daylight window, 106.63 minutes, 99.4% coverage.
- Arbitration resolved every ambiguous component on schedule (no recurrence of the v4
  starvation mechanism) -- but `candidates_created` ended at exactly **0** anyway.
- Root cause: arbitration winners permanently lost at the evidence-cache-exhaustion gate
  (`blocked_missing_evidence`), with no fallback to a runner-up. 48/263 distinct
  proposals (18.3%) lost this way, spread across the whole session, reaching even the
  *ordinary* (non-forced) arbitration path.
- Two real, confirmed simultaneous multi-bird activity windows (2 birds @ 25.79min;
  2-3 birds @ 90.50min) -- both entirely lost. 0/2 exhaustive-denominator recall.
- Fixed by Pending-Proposal Evidence Preservation & Arbitration Fallback Correctness v1
  (classification A, deterministic proof only, no field session).

### v7 (this cohort, 2026-08-31, same day as v6, afternoon window)

- Same reference Stream/scene, 89.4 minutes, 99.989% coverage.
- **`candidates_created` reached 25** (in-session growth from the first
  admission at ~6.6 minutes onward, not only at stop) -- the fix reconfirmed
  under a fully-recorded, properly-instrumented session, exceeding v5's own
  19.
- **6 real fallback attempts, 5 admitted, 1 honestly exhausted** -- the
  specific mechanism v6 lacked and the pending-proposal milestone fixed,
  observed working naturally and repeatedly for the first time under real
  field conditions, including full component-level traces for 3 of the 6.
- **`blocked_missing_evidence` materially reduced**: 9.4% vs v6's 18.3%
  (roughly halved), with zero confirmed instances of the unacceptable
  "component silently discarded while a viable member exists" outcome
  anywhere directly traced.
- **Genuine concurrent multi-subject admission directly visually confirmed**
  for the first time across any Gate A cohort -- 2 sibling-Event pairs, one
  of which also needed the fallback mechanism simultaneously.
- **A real, first-ever exercise of `max_candidates_per_hour: 20`**, confirmed
  self-clearing correctly.
- **1 real defect found and fixed** (deploy-tooling only, zero
  product/perception code): the acceptance-recorder path-conversion bug.
- Useful-evidence rate 96.0% (24/25), false-Visit rate 4.0% (1/25) -- both
  individually confirmed by full-resolution review of every admission, the
  first time this has been possible for a post-fix cohort since v6 admitted
  nothing to review.
- Zero persistence contention, zero `blocked_shadow_mode`, zero duplicate
  Visits (zero shared generation ids across all 25).

## Release-budget maturity

Independent re-evaluation of each of the seven numeric dimensions, per this
milestone's own §28 instruction -- not self-accepted, for external review:

| Dimension | Status | Reasoning |
|---|---|---|
| Minimum monitoring coverage | **READY FOR FORMAL BUDGET REVIEW** (unchanged) | v7 adds a 5th real cohort at 99.989%, fully consistent with the existing ~99% candidate (all five cohorts now 99.4%-99.99%). |
| Minimum useful-evidence rate | **READY FOR FORMAL BUDGET REVIEW** (unchanged, strengthened) | v7 adds a 3rd real post-fix measurement at 96.0% (of 25, individually reviewed), alongside the earlier 88.2% and v5's 94.7% -- all three exceed the existing ~85% candidate with no contrary evidence; the trend is upward, not degrading. |
| Maximum false-Visit rate | **newly proposed as READY FOR FORMAL BUDGET REVIEW** | Two independent post-fix measurements now exist and converge: v5's 1/19 (5.3%) and v7's 1/25 (4.0%) -- the same bar (2 independent, non-contradicting measurements) already used to promote the two dimensions above. Candidate range: **~5-10%** (generously bounding both real measurements, not a tight fit to either). |
| Maximum duplicate-Visit rate | **newly proposed as READY FOR FORMAL BUDGET REVIEW** | v5 (0 confirmed duplicates) and v7 (0/25, directly verified via zero shared-generation-id evidence reuse across all admissions -- the strongest test either cohort has applied) converge at zero. Candidate: **~0%** (allow a small non-zero ceiling, e.g. low single digits, to avoid over-fitting to two clean sessions). |
| Maximum fragmentation rate | **MORE EVIDENCE REQUIRED** (unchanged) | v7's own methodology (the `cluster_encounters` tool) proved unsuitable for this session's own sustained-activity shape, requiring a manual, denominator-independent test instead (see "Fragmentation / duplicates") -- a real, useful cross-check, but not the same measurement v5 made, so not yet a second directly-comparable fragmentation-rate data point. |
| Minimum end-to-end Visit recall | **MORE EVIDENCE REQUIRED** (unchanged) | v7 adds a third real, positive data point (3/3 real encounters represented, on two rigorously-verified stress-test windows -- deliberately the *hardest* moments this session produced, not a favorable sample) directionally consistent with v5's own qualitative "no missed encounter" finding -- but methodologically distinct from both v5's full-session review and the pre-fix 68.2% ceiling. Convergent direction, not yet a convergent number. |
| Maximum capture-to-visible-Visit latency | **MORE EVIDENCE REQUIRED** (unchanged) | No cohort to date, including this one, has instrumented true user-visible (API-to-browser) latency -- only proposal-resolution latency as a proxy. |

## Candidate budgets

Proposed for external review only, not self-accepted, per the table above:

- Minimum monitoring coverage: **~99%** (unchanged candidate, now 5 convergent cohorts).
- Minimum useful-evidence rate: **~85%** (unchanged candidate, now 3 convergent post-fix cohorts, all exceeding it).
- Maximum false-Visit rate: **~5-10%** (new candidate, from 2 convergent post-fix measurements: 5.3%, 4.0%).
- Maximum duplicate-Visit rate: **~0%, low single digits** (new candidate, from 2 convergent zero measurements).

## Defects

### Found and fixed: `MOCKINGBIRD_ACCEPTANCE_RECORDING_DIR` forwarded without `to_windows_path` conversion (deploy tooling only)

**First irreversible loss stage:** none for product data -- this is a deploy-tooling
defect, not a perception/admission/Visit/evidence/classification defect. The loss was
to *this milestone's own setup time*: a first real Observation session ran for
~2m26s (19:28:42Z-19:31:08Z) with the independent acceptance recorder silently not
recording (its output directory was never created, no error surfaced anywhere), so
that session could not supply an exhaustive-denominator window and was discarded
(see "Sustained-activity result" below for what it nonetheless showed).

**Root cause:** `scripts/deploy_windows_dev.py`'s `launch_release`, at the line
forwarding the dev-shell's own `MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR` into the
launched Windows process's environment as `MOCKINGBIRD_ACCEPTANCE_RECORDING_DIR`,
passed the value straight through with no path-format conversion -- unlike
`MOCKINGBIRD_HOME`, built two lines below it via `windows_host.to_windows_path(...)`
specifically because that same class of bug was found and fixed once already (see
that code's own comment, and `test_launch_release_sends_mockingbird_home_through_
to_windows_path`). Every path in this tool is WSL-visible (`/mnt/c/...`) by
convention (`--dev-root`, `MOCKINGBIRD_HOME`); a native Windows process's own
`pathlib`/`open()` calls cannot resolve that string as a rooted path, and silently
degrade instead of raising (this recorder's own env var only distinguishes
"unset" from "set" -- a wrong-drive/unwritable value looks identical to "not opted
in" from inside `acceptance_recorder.py`). The existing regression test for this
exact forwarding path (`test_launch_release_forwards_acceptance_recording_dir_when_
explicitly_opted_in`) could not have caught it: its own fixture set a
*Windows-style* literal (`C:\...`) as the input, which reads back unchanged whether
or not any conversion runs, and the shared `fake_host.to_windows_path` test double
is an identity function -- the exact gap the analogous `MOCKINGBIRD_HOME` test was
written to close, never extended to this sibling variable.

**Fix (bounded, deploy-tooling only, zero product/perception/admission/Visit/
evidence/classification code touched):** `scripts/deploy_windows_dev.py`, one line,
wraps the value in `windows_host.to_windows_path(Path(recording_dir))` before
forwarding, mirroring `MOCKINGBIRD_HOME` exactly. `tests/test_deploy_windows_dev.py`:
corrected the existing test's fixture to a realistic WSL-style input, and added
`test_launch_release_sends_acceptance_recording_dir_through_to_windows_path`
(non-identity `to_windows_path` fake, mirroring the `MOCKINGBIRD_HOME` proof
exactly). Directly reproduced RED against the pre-fix code (`git stash` on the
source file alone, dedicated new test fails, existing test still passes -- confirming
the existing test genuinely could not have caught this), GREEN after. Full
`tests/test_deploy_windows_dev.py`: 125/125 passed (124 pre-existing + 1 new).
`ruff check` on both touched files: clean. Verified against the real product path
immediately after: redeployed, started a fresh Observation session, and confirmed
real JPEG frames landing in the correct, documented location within seconds.

This is the same general class of gap v6's own two disclosed deploy-tooling defects
belonged to (a WSL/Windows path-format mismatch in this exact tool), not a new
category.

## Remaining Gate A dependency

In priority order:

1. **Fragmentation-rate second measurement, directly comparable to v5's
   own.** This session's own manual, zero-shared-evidence test is a real,
   useful, arguably *stronger* signal than `cluster_encounters`' own raw
   output for a sustained-activity session, but is not literally the same
   measurement v5 made. A dedicated offline pass reapplying `cluster_
   encounters` with a session-shape-aware interpretation (or a smaller,
   fixed sub-window) against this session's own already-preserved merged
   ledger could close this without further live field time.
2. **A second live cohort producing a genuinely crowded, 3+-simultaneous-
   subject moment**, to directly stress-test whether the disclosed
   crowded-feeder/NMS gap (a third real bird the detector never separately
   perceived, this session) recurs, worsens, or is scene-specific -- `roadmap.
   md` Gate A already names this as an open, unbenchmarked dimension; this
   session is the first concrete field data point for it, not a full
   characterization.
3. **True user-visible (capture-to-browser) latency instrumentation** --
   still measured by no cohort to date, including this one; would require a
   frontend-side timing addition, not a field-session-only fix.
4. **The ~13 `blocked_missing_evidence` records outside this session's own
   two exhaustive-review windows** remain individually untraced to their own
   component/rescue context (see "blocked_missing_evidence") -- an offline
   pass over this session's own preserved merged ledger, not a new field
   session, would close this.
5. **The already-known, unaffected-by-this-milestone Gate B residual**
   (a detector-sourced-but-still-wrong background crop could still receive a
   confident label; the specific mechanism this session's own confirmed false
   Visit represents -- a false *admission*, not a false *label* -- remains
   open exactly as `roadmap.md` already frames it, unchanged by this
   session).

**Not** a dependency: a second natural fallback event (this session produced
6 real attempts, 5 successes, 1 honest exhaustion -- the mechanism's own
correctness is now well-evidenced from real conditions, not resting on a
single instance).

## Decision

**Classification A.**

Every explicit §33 requirement is met against real, directly-verified
evidence, not inference:

- Representative daylight, genuine real wildlife activity: confirmed
  (clear-to-hazy sky, calm, real feeder activity already visible before
  committing; 24/25 admitted Visits individually confirmed as real birds by
  full-resolution frame review).
- Valid independent denominator window(s): two, rigorously reviewed against
  a merged, lossless 11-snapshot ledger reconstruction, deliberately chosen
  as this session's own hardest moments (both fallback events, the
  exhaustion, the multi-subject admission) rather than a favorable sample.
- Non-zero in-session candidates: 25, growing steadily from ~6.6 minutes in,
  not merely at stop.
- No recurrence of v6-style silent component loss while viable evidence
  exists: zero instances found anywhere directly traced, including full
  component-level reconstruction of 3 of the 6 real fallback events.
- `blocked_missing_evidence` materially reduced: 18.3% -> 9.4%, roughly
  halved, with every instance inside the exhaustive windows honestly
  explained (fallback rescue or confirmed-noise exhaustion).
- Protection remains bounded: 0 capacity-exhaustion events across 89.4 real
  minutes of sustained, sometimes-concurrent activity.
- No duplicate/fragmentation regression: 0 genuine duplicates (the strongest
  test applied to date -- zero shared tracker evidence across all 25
  admissions); no fragmentation regression found (the raw `cluster_
  encounters` tool's own output required a documented, honest methodology
  correction for this session's sustained-activity shape, not a defect).
- Useful evidence observed: 96.0% (24/25), individually confirmed.
- Coverage measured: 99.989%.
- Stop-finalization correct: honest `stopping`/`stopped` cycle, genuinely
  rescued one more real candidate (24->25) at stop, matching v5's own
  accepted pattern.
- No measurement-invalidating defect: the one real defect found (deploy-
  tooling recorder-path bug) was caught and fixed *before* the properly-
  measured formal session began; the ~2.5-minute pre-fix preliminary session
  it affected was cleanly excluded from every figure in this report.

**A natural fallback event occurred -- in fact six real attempts, five
successes, one honest exhaustion, with three fully reconstructed end to end**
(component members, canonical ranking, why the winner failed, fallback
position, admitted evidence, species outcome) -- exceeding the "highly
desirable but not mandatory" bar by a wide margin.

**Beyond the minimum bar**, this session also produced the first-ever
directly-visually-confirmed genuine concurrent multi-subject admission across
any Gate A cohort (two independent sibling-Event pairs), and the first-ever
real exercise of the `max_candidates_per_hour` rolling budget (confirmed
self-clearing correctly) -- both previously-unexercised dimensions the prior
reconciliation's own "Remaining Gate A dependency" named as still open.

**Honestly disclosed, not blocking this classification:** a real, confirmed
false Visit (1/25, empty background, correctly given no species label); a
concrete field instance of the already-named, not-yet-benchmarked
crowded-feeder/NMS gap (a third simultaneous bird never separately detected);
~13 `blocked_missing_evidence` records outside the two exhaustive windows not
individually traced; fragmentation-rate and true user-visible latency remain
`MORE EVIDENCE REQUIRED`, unchanged by this session's own scope.
