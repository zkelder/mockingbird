# Representative Daylight Field Acceptance & Gate A Evidence v2

**Date:** 2026-08-28, session start ~15:20 EDT (America/New_York).
**Starting HEAD:** `80e1bb3` (accept commit for Whole-Product UI / Accessibility /
Performance Closure v1); implementation commit beneath it `18a0025`.
**Schema:** v57 (unchanged by this milestone).
**Classification: B** -- no new live field session executed; the blocker is a
confirmed, unresolved authentication precondition, not a product defect and
not (for the first time in three consecutive attempts) an environmental one.
Full execution-readiness re-verified against current accepted HEAD, and the
outstanding blocker is now isolated more precisely than either prior attempt
could isolate it.

## 1. Governing sources read

In order, per the governing brief: `docs/release-execution-state.md` (full,
2349 lines), `docs/product-doctrine.md` (full), `docs/roadmap.md` (full, 3812
lines). Then bounded archaeology on: the two most recent "Representative
Field Acceptance"-family reports
([representative-field-acceptance-release-budget-v1-report.md](representative-field-acceptance-release-budget-v1-report.md),
2026-08-25, and
[representative-multi-camera-field-acceptance-release-budget-evidence-v1-report.md](representative-multi-camera-field-acceptance-release-budget-evidence-v1-report.md),
2026-08-26); the latest end-to-end bird/Visit acceptance reports
([end-to-end-bird-encounter-recall-closure-v1-report.md](end-to-end-bird-encounter-recall-closure-v1-report.md),
2026-08-19, and its direct live-proof follow-up
[cache-128-live-daylight-acceptance-v1-report.md](cache-128-live-daylight-acceptance-v1-report.md),
2026-08-20); [multi-camera-place-experience-v2-report.md](multi-camera-place-experience-v2-report.md);
[concurrent-candidate-visit-persistence-reliability-v1-report.md](concurrent-candidate-visit-persistence-reliability-v1-report.md);
[whole-product-ui-accessibility-performance-closure-v1-report.md](whole-product-ui-accessibility-performance-closure-v1-report.md);
the acceptance-recorder module and methodology
([independent-encounter-denominator-design.md](independent-encounter-denominator-design.md),
`src/mockingbird/observation/acceptance_recorder.py`); and
[detection-quality-accounting-contract.md](detection-quality-accounting-contract.md)
plus `roadmap.md`'s own "Numeric release budgets" section as the closest
things this repository has to a "Gate A measurement/accounting contract" (no
file by that exact name exists -- see §7).

## 2. Verified current accepted state (before any action)

All matched the brief's expected state exactly:

- Branch: `main`.
- Accepted HEAD: `80e1bb3ea96ab2a15c2269859273717ee2e18a12`, implementation
  commit beneath it `18a0025b6a0f17c0db6beb7875acf5872e3ea52e` (direct git-log
  parent, confirmed).
- Schema: `57` (`CURRENT_DATABASE_SCHEMA_VERSION` in
  `src/mockingbird/storage/database.py:45`).
- Latest accepted milestone: Whole-Product UI / Accessibility / Performance
  Closure v1, Classification A, closes Lane Q.
- Release doctrine: one public launch (One-Release Roadmap & Scheduler
  Reconciliation v1).
- Authorization before this instruction: **NONE -- GLOBAL PRODUCT-ROADMAP
  RECONCILIATION REQUIRED**.
- Production detector: MDv5a ONNX, `score_threshold: 0.1`.
- Production species ID: BioCLIP-2 + Identification Eligibility / Abstention.
- Camera Node upgrade gap: closed (Camera Node Upgrade & Compatibility
  Recovery v1, Classification A).
- Concurrent candidate-Visit persistence defect: closed (Concurrent Candidate
  Visit Persistence Reliability v1, Classification A).
- Repository not pushed (`main` is 217 commits ahead of `origin/main`, zero
  behind).

## 3. Worktree safety

No other active writer found: `git rev-parse HEAD` returned the same
`80e1bb3` both before and after this session's own checks; `git status
--porcelain=v2` showed zero tracked changes throughout; no lock files newer
than the repository's own docs were found. The seven preserved untracked
files were confirmed present, with unchanged sizes/mtimes, both at session
start and again at report time:

- `docs/wildlife-detector-training-contract.md.orig`
- `scripts/evaluate_small_bird_detector.py`
- `scripts/materialize_wildlife_stage2.py.orig`
- `scripts/train_wildlife_stage2_rfdetr.py.orig`
- `src/mockingbird/detectors/small_bird_benchmark.py`
- `src/mockingbird/training/wildlife.py.orig`
- `tests/test_small_bird_benchmark.py`

None were edited, staged, or incorporated. Nothing was pushed.

## 4. Are conditions representative? -- decisive finding

This session's environmental/infrastructure preconditions were checked
**independently of, and before,** the authentication question, specifically
to determine whether the outstanding blocker from the prior two attempts was
finally isolated to one cause. It was:

| Precondition | Prior attempts | This session (2026-08-28, ~15:20 EDT) |
|---|---|---|
| Daylight | 2026-08-25: unknown (never reached); 2026-08-26: **NO** (20:26 EDT, after sunset) | **YES** -- mid-afternoon, America/New_York, several hours before civil twilight in late August |
| Reference Camera Node reachable | Confirmed both prior sessions | **YES** -- ICMP 44.8-57.2ms RTT, TCP 8787 open, `GET /node/v1/health`: `status: "available"`, `camera_count: 8`, `available_camera_count: 8`, `pairing_required: false`, `self_test.status: "passed"` (`providers_initialized: true`, `camera_available: true`, `pairing_state_writable: true`), `watchdog.enabled: true`, `watchdog.last_probe_ok: true`, `watchdog.consecutive_probe_failures: 0`, `os_uptime_seconds: 686439.09` (~7d22h), `service_uptime_seconds: 145699.37` (~1d16h, since `2026-08-27T02:52:34Z`) |
| GPU/detector health | Confirmed both prior sessions | **YES** -- `nvidia-smi.exe`: RTX 4060 Ti, WDDM driver 610.62, CUDA UMD 13.3, 1220MiB/8188MiB used, 14W/160W (idle), zero MockingBird compute process (nothing was deployed yet at check time) |
| Storage headroom | 2026-08-26: `C:` at 27.47GB free, `storage_health_tier: "getting_low"` | `C:` 21.8GB free pre-deploy -> 18.8GB free post-deploy (WSL side: 843GB free / 1007GB, 12% used); the product's own `GET /api/product/health` now reports `storage_health_tier: "action_recommended"`, `storage_low_space: true` -- one tier worse than 2026-08-26, see §14 |
| Acceptance-recorder readiness | Confirmed present both prior sessions | **YES** -- module confirmed present, off-by-default, structurally isolated from product truth (see §9) |
| **Authenticated session access** (start/stop Observation, view Visits, review) | 2026-08-25: **BLOCKED** (401 on every session-relevant endpoint); 2026-08-26: not tested (moot, darkness already blocked) | **BLOCKED, re-confirmed today** (see §5) |

**Decisive finding:** this is the first of three consecutive attempts
(2026-08-25, 2026-08-26, 2026-08-28) where every environmental and
infrastructure precondition is simultaneously satisfied. The single
remaining blocker -- confirmed fresh against today's actual deployed build,
not assumed from three-day-old evidence -- is the identical authentication
precondition first documented 2026-08-25. This session's distinct
contribution is isolating that fact cleanly: darkness and authentication are
two independent blockers that have never yet been simultaneously absent, and
today proves the non-authentication half of that pair is fully clear.

Per the governing brief's §4/§15, this is treated as "conditions unsuitable
for a representative wildlife denominator" -- not because wildlife activity
or weather is unsuitable (unknown; camera preview itself is behind the same
authentication boundary, see §5), but because **no Observation session can
be opened, and no Visit can be reviewed, at all**, regardless of how
favorable daylight/weather/activity are. Per the brief's own instruction: do
not manufacture a cohort, do not run a long empty session, do not classify a
quiet session as useful Gate A evidence. None of those apply here either --
no session was opened at all, quiet or otherwise. The bounded readiness path
(§15) was executed instead.

## 5. The authentication precondition -- re-verified today, not assumed

First documented 2026-08-25
([representative-field-acceptance-release-budget-v1-report.md](representative-field-acceptance-release-budget-v1-report.md)):
every session-relevant endpoint (`GET /api/streams`, `.../observation/status`,
`.../observation/start`, `.../observation/counterfactual`, `GET
/api/visits`) returns `401` on the real dev instance, since the accepted
Local Identity / Multi-User work (2026-08-23) removed the pytest auth
bypass. No credentials for this instance exist anywhere in this repository,
and none were introduced.

**Empirically re-confirmed today, against the freshly rebuilt and
redeployed current accepted HEAD (`80e1bb3`)**, not merely assumed from
three-day-old evidence: `GET http://127.0.0.1:8000/api/streams` -> `401`;
`GET http://127.0.0.1:8000/api/visits` -> `401`. Both read-only, both made
with no credentials, matching exactly the class of check the 2026-08-25
report already performed and disclosed -- this session repeated it, did not
extend it, and did not attempt any authenticated call.

Standing user policy (session memory, corroborated verbatim by
`release-execution-state.md`'s own Lane R record of the 2026-08-25 attempt):
never ask the user again for real admin credentials, nor to interactively
sign in, start/stop monitoring, or review Visits/UI, unless a future
milestone specifically requires human acceptance and the user explicitly
agrees to participate first; a genuine representative field-acceptance
session cannot be satisfied by a fresh disposable instance (it lacks the real
paired Camera Node's pairing, the real accumulated Place history, and the
real continuity this milestone's own §13 asks to compare against); do not
modify or weaken production authentication to route around this. This
milestone's own brief does not carry, and this session does not treat itself
as having received, the user's explicit live-participation agreement. No
credentials were requested. No fresh disposable instance was substituted for
the real one. Production authentication was not touched.

## 6. Camera/Stream configuration

Unchanged since the 2026-08-26 attempt (re-confirmed via the same
unauthenticated health path): **one real Stream** -- the reference Camera
Node (`192.168.1.112:8787`) -- is configured in this dev instance. A second
real, already-supported Source (an EMEET SmartCam S600 USB webcam+mic,
hardware-validated during the 2026-08-24 acoustic milestone) remains
identified but not wired as a Stream. Per the governing brief's §5, wiring up
an existing, already-supported Source through existing configuration paths
would have been preferable to delaying evidence -- but doing so requires the
identical authenticated Stream-configuration path blocked in §5, so it
remains open for the same reason the live session itself does. No new
provider work was performed or considered, matching the brief's explicit
instruction not to build one this milestone.

## 7. Production configuration (frozen; not touched)

No code was edited this session, so every value below is frozen by
construction. Re-confirmed directly against current HEAD (`80e1bb3`), with
file:line references, specifically so this report does not merely assert
"nothing changed" without having actually looked:

| Setting | Value | Location |
|---|---|---|
| MDv5 `score_threshold` | `0.1` | `data/models/observation-onnx-cuda/model-bundle.json` |
| MDv5 NMS IOU / max detections | `0.45` / `300` (`max_observations_per_frame: 300`, `max_decode_candidates: 102000`) | same file |
| Tracker `strong_detection_threshold` | `0.7` | `data/models/observation-onnx-cuda/frame-driven-provider-config.json`; matches `FrameDrivenSettings` default at `src/mockingbird/observation/frame_driven_provider.py:67` |
| Tracker `weak_detector_support_floor` / `minimum_iou` / `maximum_centroid_distance` / `ambiguity_margin` | `0.05` / `0.05` / `0.22` / `0.01` (all defaults, not overridden) | `frame_driven_provider.py:77-86` |
| Evidence-cache `_MAX_CACHED_BURST_BYTES` / `_MAX_CACHED_SAME_FRAME_BYTES` | `128` / `128` (unchanged since the 32->128 fix) | `src/mockingbird/observation/engine_runtime.py:1705-1706` |
| `max_candidates_per_session` / `max_candidates_per_hour` | `50` / `20` | `src/mockingbird/observation/candidate_visit_authority.py:293-294` |
| `max_evidence_items_per_candidate` / `max_evidence_bytes_per_candidate` | `4` / `8,000,000` | `candidate_visit_authority.py:295-296` |
| Scene-confusor policy default | **Disabled** (`scene_confusor_reviewed_evidence_enabled = False`) | `src/mockingbird/repository/product_repository.py:2763-2764`; deliberate, matches [[site-specific-learning-local-adaptation-v1-2026-08-24]] |
| BioCLIP model identifier | `bioclip_2` / "BioCLIP 2 local" / `bioclip-2-vit-l-14` | `src/mockingbird/species/bioclip_adapter.py:34,37-38`; confirmed zero `bioclip_2.5`/`bioclip25` references anywhere in `src/` |
| SQLite `busy_timeout` | `5000` ms | `src/mockingbird/storage/database.py:1956,2063` |
| SQLite `journal_mode` | Default rollback journal (**not** WAL) | confirmed via repo-wide grep, zero `journal_mode` pragma in `src/mockingbird/` |
| `candidate_visit_adapter.attempt_candidate` retry | 3 total attempts, backoff `(0.05, 0.15)`s + jitter | `src/mockingbird/observation/candidate_visit_adapter.py:57-58` |

The current Gate A measurement/accounting contract remains
[detection-quality-accounting-contract.md](detection-quality-accounting-contract.md)
(no file literally named a "Gate A ... contract" exists in this repository;
this is the closest and correct artifact -- it self-describes as "a
measurement and shadow-evaluation contract, not a new production gate," and
its "Production authority gate" section's 2026-08-19 verdict, quoted there,
remains current and unsuperseded). Its condition-2/3 sweep result (0.3
rejects 29% of false positives while losing 19% of real animals; 0.7 rejects
67% while losing 45%) is why production admission stays confidence-blind --
unchanged this session, per this milestone's own explicit freeze
instruction. `roadmap.md`'s own "Numeric release budgets" section is the
other half of this same governing contract for Gate A specifically (see
§13, below).

## 8. Independent denominator

Not exercised. No Observation session was opened (§4-§5), so no acceptance
recording exists for this date, and no independent encounter review was
possible or performed. Zero genuine encounters, zero ambiguous cases -- not
because none occurred at the real site, but because no observation was made.

## 9. Funnel accounting

Not exercised, for the same reason. The full thirteen-stage funnel this
milestone's brief specifies cannot be traced without at least one genuine
encounter and at least one admitted or rejected candidate.

## 10. Cohort metrics

None produced this session. Gate A's evidence body remains exactly the two
real daylight cohorts it has held since 2026-08-20 -- unchanged for the third
consecutive milestone attempt. See §12 for the full comparison table.

## 11. Concurrent-persistence live acceptance

Not exercised live -- no session ran, so no contention could occur. Statically
re-confirmed the accepted fix is unchanged and traced its exact emission
mechanics for the next session's benefit:

- `_PERSISTENCE_CONTENTION_CODE = "observation_candidate_visit_persistence_contention"`
  (`src/mockingbird/observation/candidate_visit_adapter.py:51`).
- Constructed and logged once per failing attempt inside
  `create_candidate_visit_from_proposal`'s `except OperationalError` handler
  (`src/mockingbird/repository/product_repository.py:6694-6705`):
  classified as contention when the driver error text contains "locked" or
  "busy", logged via `log_error_event` (WARNING, logger
  `"mockingbird.events"`) to the rotating file handler at
  `<MOCKINGBIRD_HOME>/logs/mockingbird.log` (dev deployment:
  `%LOCALAPPDATA%\MockingBirdDev\userdata\logs\mockingbird.log`).
- The caller (`candidate_visit_adapter.attempt_candidate:213`) retries only
  this code, up to `_MAX_PERSISTENCE_ATTEMPTS = 3` total attempts,
  backoff `(0.05, 0.15)` seconds plus jitter -- unchanged from the accepted
  fix.
- On exhaustion, a separate durable fact
  (`last_failure_code = f"{code}:retries_exhausted"`) is written to
  `observation_authority_settings` (`product_repository.py:9675-9696`) --
  not a second log line. No product API currently surfaces
  `last_failure_code`/`failure_count`; an operator must grep the log file
  directly (a disclosed, pre-existing gap, not new to this session).

A successful session with zero contention would still be valid evidence per
this milestone's own brief; this session produced neither zero-contention
evidence nor contention evidence, because no session ran at all. No admitted
candidate was silently lost, because none was attempted.

## Product observations

Not exercised. No Observation session was opened and no authenticated page
(Today, Visit detail/case file, Review Queue, Bird Log/history, camera
attribution, mixed camera health, acoustic health/status, habitat/
environment context, storage/backup health) was reachable without the
credentials this session correctly declined to obtain (§5). The only
product-facing surface touched was the unauthenticated `GET
/api/product/health` / `GET /api/product/instance` pair, covered in §4/§6.
No release-impacting product observation is reported here because none
could be made.

## 12. Prior-cohort comparison (unchanged; reproduced for continuity)

| Session | Date | Duration | Cameras | Independent denominator | End-to-end recall | False-Visit rate | Evidence survival | Outcome |
|---|---|---|---|---|---|---|---|---|
| Observational Quality Closure v1 | 2026-08-18/19 | 4 real days | 1 | 70 admitted Visits, independently adjudicated | n/a (precision study) | 52.9% of admitted Visits false | n/a | Closed by Scene Confusor Suppression v1 |
| End-to-End Bird Encounter Recall Closure v1 | 2026-08-19 | 92.20 min | 1 | 22 genuine encounters | 68.2% (15/22, disclosed ceiling) | 9.5% (2/21) | 88.2% (15/17) | B -- standing methodology; evidence-cache 32->128 fix |
| Cache-128 attempt 1 | 2026-08-19 (night) | 32.8 min | 1 | 0 (post-sunset) | n/a | n/a | n/a | D -- wrong time of day |
| Cache-128 attempt 2 | 2026-08-20 (morning) | ~4.08 min | 1 | n/a | n/a | n/a | n/a | D -- real Camera Node connectivity failure |
| Cache-128 Live Daylight Acceptance v1 | 2026-08-20 | 90m23s | 1 | >=10 encounters (conservative) | not separately restated (cache-focused) | 2 likely-false of 12 created Visits | 6/10 traceable Visits survived genuine delay, up to 324.2s | **A** -- cache-128 proof passes; 1 disclosed ambiguous case |
| Representative Field Acceptance & Release-Budget Closure v1 | 2026-08-25 | 0 min | 0 | 0 | n/a | n/a | n/a | C -- OPEN; blocked pre-session by authentication |
| Representative Multi-Camera Field Acceptance & Release-Budget Evidence v1 | 2026-08-26 | 0 min live | 0 live | 0 | n/a | n/a | n/a | B -- no live session (darkness); readiness re-established + 1 build defect fixed |
| **This session (Representative Daylight Field Acceptance & Gate A Evidence v2)** | **2026-08-28** | **0 min live** | **0 live** | **0** | n/a | n/a | n/a | **B -- no live session (authentication, environmental conditions otherwise fully clear); readiness re-verified against current accepted HEAD** |

Gate A's evidence body (per `roadmap.md`'s own "Numeric release budgets"
section, read in full and quoted directly): still exactly the 2026-08-19 and
2026-08-20 cohorts. No new cohort was added by this session. This is now the
**third consecutive milestone attempt** to add Gate A field evidence without
succeeding -- 2026-08-25 (auth), 2026-08-26 (darkness), 2026-08-28 (auth
again) -- the same authentication precondition accounts for two of the three.

## 13. Release-budget disposition

**Insufficient representative evidence -- unchanged, not regressed.** The
evidence body is exactly the same two cohorts it was after the 2026-08-26
attempt; this session neither added nor lost evidence. Per `roadmap.md`'s own
explicit standing text (quoted directly): "one session, however carefully
independently validated, is not a representative body of evidence on its
own... Do not adopt 'looks pretty good' as a substitute for a stated number,
and do not invent a precise-sounding target... that no field cohort has
actually justified." No candidate release-budget numbers are proposed here,
consistent with that standing instruction and with both immediately-prior
attempts reaching the identical conclusion.

## Readiness for the next viable session (bounded readiness path, §15)

Documented explicitly so the next attempt does not have to re-derive it:

- **Acceptance recorder** (`src/mockingbird/observation/acceptance_recorder.py`):
  off by default; armed only by setting `MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR`
  (plus optionally `_INTERVAL_MS`/`_MAX_FRAMES`/`_MAX_BYTES`) in the **WSL
  shell environment before invoking** `deploy_windows_dev.py` -- it forwards
  these to the launched Windows process as
  `MOCKINGBIRD_ACCEPTANCE_RECORDING_DIR`/`_INTERVAL_MS`/`_MAX_FRAMES`/`_MAX_BYTES`
  (`scripts/deploy_windows_dev.py:1421-1449`). This session did **not** set
  these (no session was ever going to be started regardless), so today's
  deployed process has recording off. The last two real sessions' proven
  values: `_INTERVAL_MS=1000`, `_MAX_FRAMES=5500`, `_MAX_BYTES=4950000000`
  (dataclass defaults are `3000`/`2400`/`2_500_000_000`).
- **Exact API sequence** (no dedicated wrapper script exists for this step --
  confirmed): `POST /api/streams/{stream_id}/observation/start`, poll `GET
  .../observation/counterfactual?...end_offset_ms=...` periodically through
  the session, `POST .../observation/stop`, then `GET .../observation/status`
  to confirm `stopped_reason`. All require an authenticated session (§5).
- **Post-session accounting**: `python scripts/run_encounter_accounting.py
  --input <saved-counterfactual.json> --output
  data/evaluations/encounter-accounting/<session-name>/`.
- **Contention log location**: `%LOCALAPPDATA%\MockingBirdDev\userdata\logs\mockingbird.log`
  -- grep for `observation_candidate_visit_persistence_contention` (see
  §11); no product API surfaces this today.
- **Second camera**: an EMEET SmartCam S600 USB webcam+mic (hardware
  -validated 2026-08-24) remains available but unwired; adding it needs the
  same authenticated Stream-configuration path blocked in §5.
- **A dedicated single-command field-session launcher does not exist** --
  the path is deploy + manual REST calls + a separate post-hoc accounting
  script. `scripts/mockingbird-field-trial` (tmux-based) is a *different,
  unrelated* local dev launcher with no relationship to the acceptance
  recorder or the real Camera Node; do not reach for it by name-similarity.
  Not fixed here (would be tooling/feature work, out of this milestone's
  bounded scope), but worth naming as a recurring source of session
  -to-session friction across at least three attempts now.

## 14. Findings

**Acceptance-tool finding, not a new product defect (cold-start
false-negative, previously documented, recurred):** the fresh
`deploy_windows_dev.py` invocation (default `--timeout 90.0`) reported
verification failure: `ERROR: Deployment verification failed:
http://127.0.0.1:8000/api/product/health did not return a valid
product-health body.` The underlying process was, in fact, healthy the
entire time -- `Get-Process` showed it running
(`MockingBirdDev\releases\80e1bb3\python\pythonw.exe`, `Responding: true`)
and listening on port 8000 throughout. A direct, immediate manual probe
(`GET /api/product/health`) returned `200`, `"ready": true`,
`"database_schema_version": 57`; `GET /api/product/instance` confirmed
`"git_commit": "80e1bb3ea96ab2a15c2269859273717ee2e18a12"` -- an exact
match to accepted HEAD. A follow-up `deploy_windows_dev.py --status` then
also correctly reported `"verified dev release 80e1bb3 running"`. This is
the same cold-start-slower-than-the-tool's-own-verification-window pattern
already documented at least twice before in this project's history
(2026-08-17, 2026-08-18 -- see [[sandbox-has-windows-gpu-interop]]): real
CUDA/ONNX/BioCLIP cold start has previously measured up to ~3m41s, longer
than the tool's fixed 90-second default. Per established precedent, this
was verified manually rather than treated as a code defect to fix -- no
prior occurrence of this exact pattern has ever been "fixed" by raising the
default, and this session found no new reason to change that. The
deployment itself was completely healthy; only the deploy tool's own
bounded verification window was too short this particular time.

**Investigated and ruled out (not the cause):** hypothesized that 25
accumulated retained Windows dev releases might explain the storage-tier
downgrade above (each release potentially duplicating the full multi-GB
CUDA/BioCLIP runtime closure). Checked directly: each retained release
directory is only ~29MB (confirmed for `80e1bb3`, `db8588c`, `f609c89`);
25 releases total roughly 700MB-750MB, nowhere near enough to explain the
observed ~24GB decline since 2026-08-20. An interrupted `--cleanup`
attempt (killed by a 60-second foreground timeout before completing --
itself slow for the same reason large WSL<->Windows file-count-bound
copies/deletes are slow in this sandbox, see
[[sandbox-has-windows-gpu-interop]]) left no directory partially deleted,
confirmed by a full per-release file-count listing immediately after (all
25 directories intact). No cleanup was completed and none was needed --
the hypothesis did not pan out, so nothing was deleted. The real cause of
the `C:` free-space decline remains genuinely open, exactly as 2026-08-26
already disclosed; this session narrows it by ruling out one plausible
mechanism rather than resolving it.

**Acceptance/process finding (not a product defect):** the real dev
instance's authentication requirement -- itself a correct, intended
consequence of the accepted Local Identity / Multi-User work (2026-08-23) --
has now blocked two of the last three field-acceptance attempts outright,
with no code-level or process-level remediation available inside this
milestone's authority (per explicit user policy, see §5). This is the
single highest-leverage open item standing between the current evidence body
and Gate A closure: environmental conditions were fully representative today
and the infrastructure was fully healthy, and still no evidence could be
gathered. Two paths exist to unblock a future attempt, neither
implementable unilaterally in a bounded acceptance milestone: (a) the user
opts into live participation for a specific scheduled session, or (b) a
deliberate, separately-reviewed decision provisions a durable, narrowly
-scoped, non-interactive credential or service-account for exactly this
recurring measurement need. This report recommends flagging this for the
next global product-roadmap reconciliation rather than treating it as
self-evidently resolved by another unattended retry.

**No product defects found or reproduced this session** (none could be,
without an open session).

**Environmental limitation:** none -- conditions were representative for the
first time in three attempts; see §4.

**Acceptance-tool/documentation defect (not a product defect):**
`release-execution-state.md`'s own §16 "Transition checkpoint" section
carries its own separate "Accepted HEAD" snapshot, currently frozen at
`763fe22` (Multi-Camera Place Experience v2's implementation commit, 2026
-08-26) -- it was not updated by Camera Node Upgrade & Compatibility
Recovery v1, One-Release Roadmap & Scheduler Reconciliation v1, or
Whole-Product UI / Accessibility / Performance Closure v1, all three
accepted after it and all three correctly reflected in §1 instead. This is
pre-existing document-maintenance drift, not something this session
introduced or was asked to reconcile -- noted here rather than silently
worked around, since a future reconciliation pass should know §16 is stale
and §1 is the authoritative section.

## 15. Decision

**B** -- conditions were, for the first time, environmentally and
infrastructurally fully representative, but the identical authentication
precondition first found 2026-08-25 remains unresolved and blocks any live
session outright. Bounded readiness work was completed correctly: current
accepted HEAD (`80e1bb3`) was rebuilt and redeployed fresh end to end,
independently confirmed healthy and identity-exact
(`git_commit == 80e1bb3ea96ab2a15c2269859273717ee2e18a12`, schema 57,
`ready: true`) despite one cold-start false-negative from the deploy
tool's own bounded verification window (§14 -- a known, previously
-documented pattern, not a new defect), then stopped cleanly, leaving
`80e1bb3` a retained, ledger-verified release ready for instant relaunch.
Host/Node/GPU/storage health was independently re-confirmed, and the
outstanding blocker was isolated more precisely than either prior attempt
could isolate it. No new Gate A field evidence was produced. No product
code was changed. No production configuration was touched.
