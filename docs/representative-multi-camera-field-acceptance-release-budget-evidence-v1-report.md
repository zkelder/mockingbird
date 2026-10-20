# Representative Multi-Camera Field Acceptance & Release-Budget Evidence v1

**Status: B — NO REPRESENTATIVE FIELD SESSION EXECUTED (environmental
conditions unsuitable at session start); full execution-readiness for the
next daylight session established instead, per this milestone's own §14
"No representative conditions" path, including one real, reproduced,
fixed release-engineering defect found while proving that readiness.**

This is an acceptance/evidence milestone, not a feature-development
milestone. It did not add a new field cohort to the Gate A evidence body.
It did remove a concrete, previously-unknown blocker (a broken Windows
build) that would otherwise have cost the *next* daylight session its own
archaeology/debugging time, and it re-verified every other precondition a
live session needs.

## Identity

- **Starting HEAD:** `db8588c` (Reconcile release-execution-state.md:
  accept Concurrent Candidate Visit Persistence Reliability v1) — verified
  via `git rev-parse HEAD`/`git log` at session start, matching the
  instructed starting state exactly. Accepted implementation HEAD
  immediately beneath it: `790513e`.
- **Ending HEAD:** this report's own implementation commit (a real hash
  cannot be written accurately inside its own commit's file content — see
  `git log` for the authoritative value, matching the identical, already-
  accepted convention the immediately-prior milestone's own report used)
  plus a separate reconciliation commit updating
  `docs/release-execution-state.md` only.
- **Schema:** `v57 → v57, unchanged.` No table added, changed, or migrated.
- **Production configuration (frozen throughout, never touched):** MDv5a
  ONNX @ `score_threshold=0.1`, CUDA execution provider; BioCLIP-2 +
  Identification Eligibility/Abstention; Acoustic/BirdNET accepted,
  release-ready optional; candidate-Visit authority/evidence-cache/scene-
  confusor/SQLite timeout/retry policy exactly as accepted at `790513e`.
- **Real Sources/Streams used:** **none.** No Observation session was ever
  opened — see "Representativeness decision," below.
- **Date/time:** 2026-08-26, session start 20:26 EDT (`America/New_York`,
  the same timezone this repository's own prior field-acceptance sessions
  have consistently treated as the applicable local time for the paired
  Camera Node's real physical site — confirmed via `timedatectl`, NTP-
  synchronized).
- **Environmental conditions:** after sunset at a Northeast-US latitude in
  late August, where sunset falls roughly 7:30–7:45 PM EDT this time of
  year — 20:26 local is at or past the end of civil twilight, i.e. low
  light shading into full darkness (exact site coordinates are not
  recorded in this repository; this is the same timezone/region every
  prior session's own daylight/darkness judgment has used).
- **Actual live field session duration:** 0 minutes.
- **Conditions judged representative:** **NO.**

## Worktree safety (§3)

- `git status --short` at session start showed exactly the seven preserved
  untracked files and nothing else (matches the pre-supplied gitStatus
  snapshot); re-checked again mid-session (before/after the packaging
  fix) and at the point of writing this report — identical every time,
  same seven files, same sizes/mtimes, nothing staged or modified beyond
  this session's own two tracked changes
  (`scripts/build_local_product.py`, this report).
- `git log --oneline -3` stable at every check (`db8588c` → `790513e` →
  `dc2043a`) — HEAD never moved out from under this session.
- `ListAgents` showed 266 peer entries; all but two are `Remote Control`
  and reported `offline`. The two `interactive` peers sharing this
  environment (`mockingbird-active-35`, started 16m before this session;
  `mockingbird-active-c6`, started 2h before) showed no evidence of
  writing to this worktree — `git status`/`git log` never drifted between
  any of this session's repeated checks, the same "no unexpected
  working-tree drift" standard the immediately-prior field-acceptance
  attempt (2026-08-25) used and documented. Treated as idle/non-writers,
  not automatically a blocker, per standing convention.
- `deploy_windows_dev.py --status` at session start reported **port 8000:
  free** — no dev server process was already running, so there was no
  live session state to accidentally disturb.

## Representativeness decision (§5) — why no live session was attempted

Checked, in order, before committing to a long session:

1. **Local time/daylight.** 20:26–20:27 EDT on 2026-08-26 — after sunset.
   This repository's own accepted field-acceptance history has already
   demonstrated, twice, exactly what happens when a bird-recall session is
   started this late: the 2026-08-19 post-sunset attempt produced 32.8
   real minutes with **zero** track generations, zero proposals, zero
   candidates (2268 raw low-confidence MDv5 detections, correctly never
   promoted — IR/sensor noise, not birds); a first 2026-08-20 attempt
   (nighttime) was independently recorded as "Decision D, wrong
   time-of-day." This milestone's own governing instruction names this
   *exact* scenario as the canonical "do not manufacture a field result"
   case. Decisive by itself.
2. **Camera reachability.** Reference Camera Node `<node-ip>:8787`:
   ICMP ping 3/3 succeeded (40–212 ms), raw TCP connect to 8787 succeeded.
   Reachable — but reachability was never the blocking factor tonight.
3. **Host/GPU/detector availability.** Checked and found healthy despite
   the time-of-day block (see "Preflight," below) — because a live session
   was never going to be attempted regardless, this instead became direct
   verification that *nothing else* would have blocked the next daylight
   attempt either.
4. **Standing authentication/live-participation gate.** The immediately
   preceding field-acceptance milestone
   ([representative-field-acceptance-release-budget-v1-report.md](representative-field-acceptance-release-budget-v1-report.md),
   2026-08-25) recorded an explicit, standing user decision: do not ask
   again for real administrator credentials or live human participation
   unless a future milestone specifically requires human acceptance and
   the user explicitly agrees first; a genuine field-acceptance session
   additionally needs real human review participation, which a disposable
   dev instance cannot supply. This governing instruction *is* that
   explicit request for this specific milestone, so the credential
   question was not re-litigated by asking the user again — but no
   attempt was made to sign in or drive a live session tonight either,
   since the time-of-day gate alone was already dispositive, and doing so
   in the dark would only have produced the same "clean but useless"
   precision-only data point 2026-08-19's post-sunset attempt already
   recorded once.

**Decision: conditions are clearly unsuitable. Executing §14 ("No
representative conditions path") instead of opening a long, known-
low-value nighttime session.**

## Preflight performed this session

### 1. Build / deployed-code identity — a real defect found and fixed

`deploy_windows_dev.py --status` showed the last tool-deployed commit
(`f609c89`) and 23 retained releases, **none matching current accepted
HEAD** (`db8588c`/`790513e` — the real SQLite-retry code change sits
between the newest retained release and HEAD, so no existing artifact was
runtime-equivalent). A fresh `python3 scripts/deploy_windows_dev.py
--commit db8588c` (full fidelity — GPU/CUDA and BioCLIP dependency
closures included, nothing skipped) was run to produce one, and it
**failed**, reproducibly, with a genuine build-breaking defect:

```
LocalProductBuildError: Windows dependency verification failed: site-packages
has more than one installed version of the same package -- click:
click-8.4.2.dist-info, click-8.5.0.dist-info.
```

**Root cause, proven not inferred:** identical mechanism to an already-
documented, already-fixed defect class in this exact file (the `idna` pin,
added for the same reason). `WINDOWS_RUNTIME_REQUIREMENTS` (the core-tier
installer) has no wheel cache and always does a live online `pip install`
resolve; `click` is not a direct MockingBird dependency there (pulled in
transitively by `uvicorn`'s CLI entry point) and was never pinned, so it
silently resolved to whatever was newest on PyPI at build time (8.5.0,
today). `WINDOWS_BIOCLIP_RUNTIME_REQUIREMENTS` (the optional BioCLIP-
closure installer) already explicitly pins `click==8.4.2` (a transitive
need of `huggingface_hub`'s own CLI, installed offline from this host's
local wheel cache). Both tiers `pip install --target` into the same flat
site-packages; pip leaves the first version's real code untouched but
still writes a second, differently-versioned `.dist-info/` — exactly the
corruption class `verify_no_duplicate_site_packages_metadata` exists to
catch, and did.

**Fix:** one additive line, `"click==8.4.2"`, added to
`WINDOWS_RUNTIME_REQUIREMENTS` immediately after the existing `idna`
pin, with a comment matching that pin's own documented shape — see
[build_local_product.py](scripts/build_local_product.py). No schema
change, no product/runtime logic touched, no new architecture.

**Validation (RED→GREEN, an existing test — no new test file needed):**
`tests/test_local_product_packaging.py::test_real_windows_bioclip_dependency_closure_installs_offline_with_no_duplicates`
already exercises exactly this three-tier install sequence against this
host's real wheel caches and already asserts
`verify_no_duplicate_site_packages_metadata` does not raise — it was
simply never run against *today's* live PyPI state before this session
(it is `@pytest.mark.slow`, network- and multi-GB-wheel-cache-dependent,
not part of ordinary fast test runs).

- **RED, pre-fix** (`git stash push -u -- scripts/build_local_product.py`,
  confirmed the stash held only this file's change): test failed in
  72.31s with the identical `LocalProductBuildError`/`click-8.4.2.dist-
  info, click-8.5.0.dist-info` message as the real build failure above —
  not a different or contrived failure.
- **GREEN, post-fix** (`git stash pop`): test passed in 42.03s; the real
  deploy's own install log for this run shows `click-8.4.2` installed by
  the core tier directly (the explicit pin resolves cleanly on live PyPI
  too) and the BioCLIP tier's own `click-8.4.2` install becomes a genuine
  no-op (`WARNING: Target directory .../click-8.4.2.dist-info already
  exists`), never a second version.
- **Tier 2 (directly affected subsystem):** full
  `tests/test_local_product_packaging.py` — 66 passed (fast tier, `-m "not
  slow"`), plus all 4 `@pytest.mark.slow` tests in the same file (129.25s)
  — all passing, no other test in this file regressed.
- **`ruff check` on the touched file:** clean, zero findings.
- **Tier 3:** not run — this change touches only Windows build/packaging
  tooling (`scripts/build_local_product.py`), has zero import relationship
  to the API/observation/repository code the Core suite exercises, and
  the milestone's own §19 explicitly does not require a full Core re-run
  for a change this narrowly scoped when Tier 1/2 evidence is this direct.
- **Re-deploy after the fix:** a second `deploy_windows_dev.py --commit
  db8588c` run was launched; see "Live deployment result," below, for its
  outcome.

This is classified as an **acceptance-tool / release-engineering defect**,
not a Gate A perception/admission/Visit defect — it blocks *building* a
deployable artifact of the accepted product, not anything the frozen
production stack itself does once running. Fixing it falls squarely inside
this milestone's own §14/§15 "the preflight itself reproduces a real
correctness problem" allowance, not the excluded "general Windows
packaging" campaign (a one-line, precedented, fully-validated dependency
pin, not new packaging architecture).

### 2. Live deployment result

The second attempt (fix applied) **succeeded**: `DEPLOYED db8588c`,
`Runtime: C:\Users\<user>\AppData\Local\MockingBirdDev\releases\db8588c`,
`BioCLIP species suggestions: available`. Independently re-verified via
direct HTTP (never trusting the deploy tool's own report alone, matching
established doctrine) — both routes are confirmed unauthenticated directly
in source (`get_product_health`/`get_product_instance_identity` in
`api/main.py` take no auth dependency):

```
GET /api/product/instance
  {"instance_id":"19280dbc9f60ebf0cc8fc4425390b891","app_version":"0.1.0",
   "git_commit":"db8588c90b35b701ea4467b7c92a0f9d9d1383b6",
   "build_id":"88eb7043e4abbf3d"}

GET /api/product/health
  {"ready":true,"database_schema_version":57,"database_migrated_from_version":53,
   "observation":{"configured_stream_count":1,"monitored_stream_count":0},
   "log_path":"C:\\Users\\<user>\\AppData\\Local\\MockingBirdDev\\userdata\\logs\\mockingbird.log",
   "storage_health_tier":"getting_low","storage_low_space":false,
   "backup":{"has_backup":true,"last_backup_verified":true},
   "previous_shutdown_clean":false, ...}
```

`git_commit` matches current accepted HEAD exactly; schema `57` matches;
this dev instance's own userdata carries a real prior migration history
(`migrated_from_version: 53`), not a fresh empty database. `log_path`
independently confirms the exact rotating-log location predicted in
"Logging/correlation," below, from source alone — first-hand proof, not
an assumption. `previous_shutdown_clean: false` is the same pre-existing,
already-disclosed historical WARN prior sessions have recorded (nothing
this session did caused it — no dev process was running at this session's
own start). The stopped instance's own retained `ReleaseRecord` was
inspected directly and confirms `click-8.4.2.dist-info` as the *only*
`click` entry across every junctioned site-packages path — no
`click-8.5.0` survives anywhere in the deployed artifact.

After this verification, the deployment was **stopped cleanly** via
`deploy_windows_dev.py`'s own internal `stop_verified_deployment` (a live
identity re-check before stopping, not a bare PID kill), returning the
host to its pre-session idle state (`--status` confirms `Port 8000:
free.` again). `db8588c` is now a retained, ledger-verified release —
the next daylight session can relaunch it instantly via
`deploy_windows_dev.py --artifact` against that retained release, with
**no rebuild needed**.

One real, additional fact learned honestly through this unauthenticated
health check (not by making any authenticated call): `configured_
stream_count: 1` — confirming, definitively rather than by inference, the
finding in "Simultaneous real-camera capability," below.

### 3. Camera Node

Reachable at the network level throughout (ICMP + raw TCP to
`<node-ip>:8787`, re-checked at session start and again before writing
this report — no change). Node-side health/pairing/self-test state was
**not** re-verified against the live product this session (that requires
an authenticated `GET /api/streams`/Camera Node status call, deferred to
the next live session per the standing decision in "Representativeness
decision," above) — recorded honestly as unverified, not assumed healthy.

### 4. GPU / detector

`nvidia-smi` via the Windows host: **NVIDIA GeForce RTX 4060 Ti**, driver
`610.62`, `8188 MiB` total VRAM, `1804 MiB` used, **0% utilization** at
check time — the same GPU this product's accepted MDv5/CUDA path has
already been validated against, idle and available, comfortable headroom
for a live session's own detector + BioCLIP worker.

### 5. Storage

- Sandbox (`/`): 844 GB free (12% used) — not a constraint.
- Windows host `C:`: **27.47 GB free** (`Get-PSDrive C`) — down from the
  43.07 GB free the 2026-08-20 cache-128 daylight session recorded. The
  live, deployed product's own `GET /api/product/health` independently
  agrees this is now worth watching: `storage_health_tier: "getting_low"`
  (though `storage_low_space: false` — the less severe of the two tiers,
  not yet the blocking one). Still comfortably above the
  acceptance-recorder's own established ~4.95 GB session budget (that same
  2026-08-20 session actually wrote 3.63 GB over 90m23s) plus ordinary
  product DB/media growth, with several times that in margin — but this
  is now a real, product-flagged trend, not only this session's own manual
  reading. Retained release directories are **not** the cause: all 24
  releases (23 pre-existing + this session's own new `db8588c`) total only
  ~1.24 GB combined (each ~30–55 MB; the heavy CUDA/BioCLIP dependency
  closures live outside the per-release directory, junctioned/shared).
  Non-blocking, not acted on this session — worth checking again, and
  worth investigating what else on this Windows host is consuming space,
  before the *next* session if the trend continues.

### 6. Acceptance-recorder capacity/settings

`AcceptanceRecorderConfig` defaults confirmed directly in source
(`sample_interval_ms=3000`, `max_frames=2400`, `max_total_bytes=
2_500_000_000`) — but the two most recent real full-daylight cohorts both
deliberately overrode these via the documented environment variables to
reach a denser, longer-duration profile validated against real measured
frame sizes:

```
MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_INTERVAL_MS=1000
MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_MAX_FRAMES=5500
MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_MAX_BYTES=4950000000
```

This gives ~90+ minutes of ~1.17s-cadence coverage at the real observed
~790–840 KB/frame analysis-resolution JPEG size, with the 4.95 GB byte cap
never binding in either of the last two real sessions (peak actual usage
3.63 GB). **Reuse this exact configuration unchanged for the next
session** — it is already validated against this exact deployment's real
frame sizes, not a guess.

### 7. Simultaneous real-camera capability

**Confirmed definitively, not inferred:** this exact dev instance's own
`GET /api/product/health` (unauthenticated, see "Live deployment result,"
above) reports `configured_stream_count: 1` — only **one** real Stream is
currently configured, almost certainly the paired reference Camera Node
(`<node-ip>:8787`, the `frame-driven-onnx-cuda` provider). A
**second** real camera Source does exist in this project's own recent
field-acceptance history and is worth wiring up before the next session
defaults to single-camera by assumption: a real **EMEET SmartCam S600 USB
webcam+mic on the Windows Host itself** was hardware-validated for
concurrent visual + acoustic capture during Acoustic Productization,
Licensing & Field Acceptance v1 (2026-08-24) — a genuine second,
already-supported (Windows-local/USB provider, no new adapter needed)
real Source that simply is not configured as a Stream in *this* dev
instance's userdata yet. **Next session's first action, in daylight,
should be adding it as a second Stream** (an existing, already-supported
provider, not new architecture) before falling back to a single-camera
session — that is genuine, low-risk setup work squarely inside §8's "use
[additional real cameras] if doing so does not compromise evidence
quality or require unrelated setup work," not the excluded "add a new
provider" case. If it is not framed usefully or the added setup risks
delaying the start of daylight capture, a single real Camera Node remains
the strongest practical fallback already supported.

No real hardware multi-camera GPU/CUDA concurrent-inference measurement
exists anywhere in this project's evidence body yet — Multi-Camera Place
Experience v2's own concurrency proof used synthetic `threading.Thread`s
against fixture data, explicitly disclosing "real GPU/CUDA-driver-level
concurrent-inference measurement... needs real hardware this sandbox does
not have" as an open question. A genuine two-real-camera daylight session
(Camera Node + Windows USB webcam, if confirmed available) would be the
first evidence closing that specific gap.

### 8. Logging/correlation for the persistence fix

Confirmed directly in source, not assumed:

- The exact retryable-contention code:
  `_PERSISTENCE_CONTENTION_CODE = "observation_candidate_visit_
  persistence_contention"`
  ([candidate_visit_adapter.py:51](src/mockingbird/observation/candidate_visit_adapter.py)).
- Bounded retry: `_MAX_PERSISTENCE_ATTEMPTS = 3`,
  `_PERSISTENCE_RETRY_DELAYS_SECONDS = (0.05, 0.15)` — a retry-exhausted
  contention failure gets a distinguishable `...:retries_exhausted` suffix
  on `last_failure_code`.
- **Where an operator actually observes this live:** `log_error_event`
  writes through `mockingbird.events`, which propagates to the root
  logger's own rotating file handler
  (`runtime_state.configure_file_logging`) at
  `<MOCKINGBIRD_HOME>/logs/mockingbird.log` (5 MB × 4 files) — for this
  dev deployment, `%LOCALAPPDATA%\MockingBirdDev\userdata\logs\
  mockingbird.log`. The packaged launcher (`Start MockingBird.vbs`) is a
  windowless fire-and-forget launch, so this rotating file — **not** a
  console/terminal — is the only place these structured events are
  actually visible in this dev-deployment shape.
- Per-Stream `failure_count`/`last_failure_code` also live directly on
  `observation_authority_settings`
  (`ProductRepository.get_observation_authority_state`), the same field
  `candidate_visit_authority_cli.py`'s own separate, bounded trial tool
  already surfaces — but **no ordinary product API route currently
  exposes these fields** (`GET /api/streams/{stream_id}` does not include
  them). The next session's own post-run accounting should therefore grep
  the rotating log file for `observation_candidate_visit_persistence_
  contention` directly, rather than expect to find it through the normal
  product UI/API — a real, disclosed, non-blocking observability gap
  (recorded under "Findings," below), not something this milestone builds
  a new surface for.

### 9. Doctor / host health

Not run live this session (would require the deployment to be up and
healthy first — see "Live deployment result"). The established command
for the next session's own preflight/post-run check is unchanged:
`python -m mockingbird doctor --json` against the deployed release.

## Exact procedure for the next daylight session (§14.8–.9)

1. **Preflight (repeat of this session's own checks, ~2 minutes):**
   confirm local daylight (start only in full daylight, stop proactively
   once light visibly dims — never force exactly a fixed clock duration
   into dusk); `git status --short`/`git log -3` for worktree safety;
   `deploy_windows_dev.py --status`; `nvidia-smi`; `Get-PSDrive C`; ping/
   TCP to the reference Camera Node.
2. **Relaunch the already-verified `db8588c` artifact** materialized by
   this session (`deploy_windows_dev.py --status` already lists it as a
   retained release) via `deploy_windows_dev.py --artifact
   <path-to-the-db8588c-release-dir>` — **do not rebuild**, the commit is
   unchanged and the artifact is already ledger-verified; this mirrors the
   exact "smallest supported mechanism" pattern the 2026-08-20 cache-128
   session established. Confirm identity/health via `GET
   /api/product/instance` (`git_commit` exact match to `db8588c...`) and
   `GET /api/product/health` (`ready: true`, `database_schema_version:
   57`) — both intentionally public, no authentication needed for this
   step, confirmed directly in source this session.
3. **Authenticate** (the one step this session deliberately did not take,
   per "Representativeness decision," above) — `POST /api/auth/sign-in`
   with the existing dev-instance administrator session, obtained the
   way the standing decision already specifies for non-live-field
   development work if a fresh disposable instance is used instead, *or*
   the real credentialed dev instance if this is the actual authorized
   live-field session and the user has agreed to participate.
4. **Add the second real camera** — this session's own unauthenticated
   health check already confirmed `configured_stream_count: 1` (only the
   reference Camera Node), so the Windows-native USB webcam (EMEET
   SmartCam S600, already hardware-validated in this exact deployment
   shape for the acoustic milestone) is **not yet** a Stream here. Add it
   as a second Stream in daylight — real framing/positioning needs to be
   seen to be set up correctly — before starting observation, so this
   session's own §6 second question (does the concurrent-persistence fix
   hold under genuine *multi-camera* load) can actually be answered with
   two real cameras, not one.
5. **Set the acceptance-recorder environment variables** exactly as in
   "Acceptance-recorder capacity/settings," above, before launch (they
   must be set in the launched process's environment — if the deployment
   from step 2 was already running without them, stop and relaunch with
   them set, matching the cache-128 session's own documented relaunch
   step).
6. **Start observation** on every intended Stream:
   `POST /api/streams/{stream_id}/observation/start` — once per Stream
   for a genuine multi-camera session.
7. **Run for a minimum of ~90 minutes** of confirmed daylight (matching
   both real full accepted cohorts: 92 min on 2026-08-19, 90m23s on
   2026-08-20) — stop earlier only if light visibly dims first (verified
   via the recorder's own saved frames, not the clock), never extend into
   dusk chasing a round number.
8. **Pull the counterfactual ledger proactively, more than once during
   the session** (`GET /api/streams/{stream_id}/observation/
   counterfactual`, a generous `end_offset_ms`) — its own rolling
   retention destroys early records over a long session; merge multiple
   pulls into one cumulative dataset, as the cache-128 session did.
9. **Stop observation** per Stream
   (`POST /api/streams/{stream_id}/observation/stop`), confirm
   `stopped_reason` and clean shutdown via `GET .../observation/status`.
10. **Build the independent encounter denominator blind**, before opening
    the product's own Visit list — motion-screen objective flagging +
    full-session contact-sheet backstop + full-resolution zoom on every
    candidate (never thumbnail-only), disclosing ambiguous cases rather
    than forcing a label, exactly the established methodology in
    [independent-encounter-denominator-design.md](independent-encounter-denominator-design.md).
11. **Extract funnel accounting**:
    `python scripts/run_encounter_accounting.py --input
    <saved-counterfactual.json> --output
    data/evaluations/encounter-accounting/<session-name>/` — produces
    `encounter-funnel-report.json` plus a stdout summary
    (`tracking_recall`/`proposal_recall`/`admission_recall`, fragmented/
    multi-proposal/duplicate-Visit cluster counts, plausibility tiers).
12. **Grep the rotating log file** for
    `observation_candidate_visit_persistence_contention` and any
    `:retries_exhausted` suffix, per "Logging/correlation," above — this
    is the concrete, direct answer to this milestone's own §13 question
    ("does the just-accepted fix hold under genuine multi-camera field
    load"), and the single most important thing the *next* session's own
    report should lead with if any occurrence exists.
13. **Run `python -m mockingbird doctor --json`** against the deployed
    release, post-session, matching every prior accepted cohort's own
    closing health check.
14. Reconcile the new cohort against every prior real cohort in the table
    below — do not silently merge an incomparable session.

## Comparison to prior real field cohorts

| Session | Date | Duration | Cameras | Independent denominator | End-to-end recall | False-Visit rate | Evidence survival | Outcome |
|---|---|---|---|---|---|---|---|---|
| Observational Quality Closure v1 | 2026-08-18/19 | 4 real days | 1 | 70 admitted Visits, independently adjudicated | n/a (precision study) | 52.9% of admitted Visits false | n/a | Closed by Scene Confusor Suppression v1 |
| End-to-End Bird Encounter Recall Closure v1 | 2026-08-19 | 92 min | 1 | 22 genuine encounters | 68.2% (15/22) | 9.5% (2/21) | 88.2% (15/17) | Standing methodology; 3 concrete gaps named |
| Cache-128 attempt 1 | 2026-08-19 (night) | 32.8 min | 1 | 0 (post-sunset) | n/a | n/a | n/a | Decision D — wrong time of day |
| Cache-128 attempt 2 | 2026-08-20 (morning) | ~4.08 min | 1 | n/a | n/a | n/a | n/a | Decision D — real Camera Node connectivity failure |
| Cache-128 Live Daylight Acceptance v1 | 2026-08-20 | 90m23s | 1 | ≥10 encounters (conservative; more likely within 2 long spans) | not separately restated (cache-focused) | 2 likely-false of 12 created Visits (pre-existing detector-precision class, not cache-related) | 6/10 traceable created Visits survived genuine delayed handling, up to 324.2s | **Decision A — cache-128 proof passes**, 1 disclosed ambiguous case |
| Representative Field Acceptance & Release-Budget Closure v1 | 2026-08-25 | 0 min | 0 | 0 | n/a | n/a | n/a | Gate C — OPEN; blocked pre-session by authentication, no product exercised |
| **This session** | **2026-08-26** | **0 min live** | **0 live; preflight only** | **0** | n/a | n/a | n/a | **No live session (darkness); execution-readiness re-established + one real build defect found and fixed** |

No new field-cohort data is added to the Gate A evidence body by this
session. The body of real, representative daylight evidence remains
exactly the two 2026-08-19/2026-08-20 sessions it was before this
session started.

## Product metrics (§11)

**Not applicable — no live session ran.** Every Gate A metric (recall,
false-Visit rate, fragmentation, duplication, evidence survival, latency,
coverage) remains at its pre-session value; see the comparison table
above and `roadmap.md`'s own "Numeric release budgets" section, unchanged
by this milestone.

## Multi-camera / persistence (§13)

**Not exercised live this session.** The concurrent candidate-Visit
persistence fix (`790513e`) was not run under genuine multi-camera field
load this session — no Observation session was opened at all. Its Tier
1/2/3 test evidence (see
[concurrent-candidate-visit-persistence-reliability-v1-report.md](concurrent-candidate-visit-persistence-reliability-v1-report.md))
stands unchanged: root cause captured directly, deterministic RED→GREEN
reproduction, 231/231 Tier 2 passing, 5109/5112 Tier 3 passing (3
independently-confirmed pre-existing/unrelated). The exact log signature
and query mechanism to check this live (§13's own explicit ask) are now
documented precisely in "Logging/correlation for the persistence fix,"
above, ready for the next session to actually check.

## Species (§12)

**Not applicable — no live session ran.** No BioCLIP suggestion/
abstention behavior was exercised or observed this session. No classifier
work of any kind was performed, matching §12/§18's explicit instruction.

## Release-budget disposition (§16)

**Insufficient representative evidence — unchanged from before this
session.** This session added zero field-cohort minutes, so it cannot
responsibly move the evidence body's own sufficiency judgment in either
direction. The standing picture remains exactly what `roadmap.md`'s own
"Numeric release budgets" section already states: two real, carefully-
measured daylight sessions (68.2% recall/9.5% false-Visit/88.2% evidence
survival on 2026-08-19; a cache-capacity-focused Decision-A pass with
≥10 encounters on 2026-08-20) are real, valid evidence points, but "one
session, however carefully independently validated, is not a
representative body of evidence on its own" — and two sessions,
one of them scoped narrowly to a single mechanism (cache capacity) rather
than the full funnel, does not yet change that. **No candidate release
budgets are proposed in this report.** The next genuine daylight session
— ideally the first one to exercise two real simultaneous cameras and the
concurrent-persistence fix together — is the evidence this milestone's
own roadmap already identifies as still needed before that judgment can
responsibly change.

## Findings

**Product defect:** none reproduced this session (no live session ran;
nothing in the frozen perception/admission/Visit/evidence/classification
stack was exercised).

**Acceptance-tool / release-engineering defect (found and fixed):** the
Windows core-tier `click` dependency-pin gap — see "Preflight performed
this session, §1," above. Real, reproduced, root-caused, fixed, RED→GREEN
validated, zero new architecture, matches an already-established fix
pattern in the same file.

**Environmental limitation:** session start (20:26 EDT) was after sunset
— the primary, decisive reason no live session was attempted, matching
this project's own already-twice-demonstrated "post-sunset bird-recall
session produces a clean but useless zero-track-generation result"
precedent. Compounding, not independently decisive tonight: the standing
authentication/live-human-participation gate from the 2026-08-25 attempt
remains real for any *future* live session and was not re-litigated.

**Non-blocking observations (recorded, not acted on):**

- Windows host `C:` free space has dropped from 43.07 GB (2026-08-20) to
  27.47 GB, and the live product's own health check now independently
  agrees (`storage_health_tier: "getting_low"`, not yet `storage_low_
  space`) — still comfortable headroom for a session, not from
  retained-release bloat (only ~1.24 GB total across 24 releases), worth
  investigating (what else on the host is growing) before it becomes a
  blocker for a future session.
- No ordinary product API route exposes per-Stream
  `failure_count`/`last_failure_code` (the concurrent-persistence
  diagnostic fields) — an operator must read the rotating log file or
  query the repository directly. Real, disclosed; not a defect in the
  fix itself, and not something this acceptance-only milestone builds a
  new surface for.
- The packaged Windows launcher (`Start MockingBird.vbs`) is a
  windowless, fire-and-forget launch with no captured console output —
  confirmed while tracing the logging question above. This is
  by-design (matches the appliance-style packaging doctrine), recorded
  here only because it is the reason the log file, not a console, is the
  right place to look.

## Classification: **B**

Matches this milestone's own explicit guidance for the "No representative
conditions" path exactly: "implementation/release configuration ready;
representative acceptance evidence still outstanding because
environmental conditions were unsuitable. That is an acceptable outcome."
Not A: no new field cohort was gathered, and Gate A/Lane R remain exactly
as open as before this session. Not C/D: this was not merely a repeated
archaeology pass with no new verified fact — a genuinely new, real,
build-blocking defect was found, root-caused, fixed, and validated
(RED→GREEN) during the preflight itself, and every other precondition a
live session needs (Camera Node reachability, GPU/detector availability,
storage headroom, recorder settings, logging mechanism, exact
command/API sequence, minimum duration) was concretely re-verified rather
than assumed or restated from memory.

## Git / closure (§21)

This milestone produced code (the click-pin fix) plus this report — the
implementation-commit + reconciliation-commit pattern applies:

1. **Implementation commit:** `scripts/build_local_product.py` (the fix)
   + this report, together.
2. **Reconciliation commit:** `docs/release-execution-state.md`, updated
   only for the actual delta (accepted HEAD → this milestone's own
   implementation commit; latest accepted milestone entry; Lane R
   evidence-state note; no schema change; current authorized milestone
   reaffirmed as `NONE — GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED`).

`roadmap.md` is **not** edited — nothing in the governing roadmap itself
changed; this session only re-verified execution-readiness and fixed a
build-tooling defect.

**Not pushed.** Local accepted state only, per standing instruction.
