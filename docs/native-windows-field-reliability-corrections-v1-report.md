# Native-Windows Field Reliability Corrections v1 -- Report

Bounded correction milestone. Fixes exactly the two v0.1-critical defects
reproduced on real native-Windows + real Camera Node hardware during *Field
Validation Closure v1* (`docs/field-validation-closure-v1-report.md`, §Q-1 and
§Q-3), and re-proves both on that same real topology.

Governing contract:
[native-windows-field-reliability-corrections-v1-contract.md](native-windows-field-reliability-corrections-v1-contract.md).

This report does **not** accept Field Validation Closure v1. It records the
corrections and their real-hardware evidence so that decision can be made.

---

## A. Starting baseline

| | |
| --- | --- |
| Repository | `/home/<user>/projects/mockingbird-active`, branch `main` |
| HEAD at entry | `8a45d1a` (as expected by the brief) |
| Schema at entry | `v60` (`CURRENT_DATABASE_SCHEMA_VERSION = 60`) |
| Last accepted implementation baseline | `d5dd1d9` |
| Writer safety | No competing writer: working tree carried only the seven protected untracked detector files plus `uv.lock`; no `index.lock`, no `MERGE_HEAD`, no other session holding this tree |
| Governing documents read before implementation | `docs/release-execution-state.md` (§CURRENT PHASE, §3, §14), `docs/product-doctrine.md`, `docs/roadmap.md`, `docs/field-validation-closure-v1-report.md` (§E, §I, §N, §O, §Q, §U-§Y), plus the directly affected timezone/runtime/recovery code |

---

## B. Blocker 1 -- timezone root cause

**Two independent faults.** Either one alone leaves the defect in place, which
is why "just add `tzdata`" is not the fix.

**Fault 1 -- no Windows -> IANA name derivation existed anywhere in the
product.** `time_utils.resolve_host_local_timezone()` could discover a zone
*name* exactly two ways, both POSIX-only:

1. the `TZ` environment variable;
2. the `/etc/localtime` symlink target.

Native Windows satisfies neither. It names its zone in its own vocabulary, in
the registry (`HKLM\SYSTEM\CurrentControlSet\Control\TimeZoneInformation`,
`TimeZoneKeyName`, here literally `"Eastern Standard Time"`). So every
native-Windows Host fell through to the last-resort branch --
`datetime.now().astimezone().tzinfo`, a **fixed-offset snapshot of the current
moment** -- which was then applied to every timestamp regardless of its date.
`tzdata` supplies zone *rules*, not the host's zone *name*; with `tzdata`
alone the resolver would still have reached the fixed-offset branch.

**Fault 2 -- `tzdata` genuinely was not packaged either.** Both `astral` and
`tzlocal` declare `tzdata` conditionally for Windows
(`sys_platform == "win32"` / `platform_system == "Windows"`). But
`build_local_product.install_windows_runtime_dependencies` resolves
environment markers against the **Linux build host** while only the wheel
*tags* honor `--platform win_amd64` -- the same marker-vs-tag asymmetry that
tuple already works around for `uvicorn[standard]`/`uvloop`. Both conditions
evaluated False at build time, so `tzdata` was silently never installed.
Confirmed in the field at `d5dd1d9`, not assumed: `tzdata : NOT present`.

**Inventory of affected surfaces.** Every server-side caller of
`resolve_host_local_timezone` was wrong on native Windows for roughly five
months of the year: `place_activity_report`, `place_story`,
`_year_over_year_resolve_period`, `get_place_feature_detail`,
`get_place_feature_comparison_overview`, `conservation_report`,
`sync_attention_signals`, `import_source_folder_media_assets`,
`ecological.inaturalist_csv`, and `diagnostics.doctor._gather_clock`.

**Not affected, verified:** the API boundary (already explicit UTC with a `Z`
suffix -- Field Validation Closure v1 §N), and the frontend's seven
`toLocale*` call sites in `web/src`, which convert an explicit UTC instant in
the *viewer's own browser* zone and were already correct.

---

## C. Blocker 1 -- implementation contract

Locked before any code changed (contract document, "The contract"):

- A historical or future timestamp is converted using the timezone's rules
  **for that timestamp**, including DST transitions. One current UTC offset
  sampled once and reused across a range is not an acceptable substitute.
- Resolution order, most authoritative first: `TZ`; `/etc/localtime`;
  **`tzlocal.get_localzone_name()`**; fixed-offset snapshot.
- Steps 1-2 keep **absolute precedence**, so no Linux/macOS deployment's
  resolution changes -- step 3 is appended, never inserted.
- The resolver still **never raises**: an absent `tzlocal`, a registry
  `OSError`, a `LookupError`, and a `TimeZoneKeyName` CLDR cannot map all
  degrade to the honest fixed-offset fallback.
- Stored UTC truth is not rewritten; API fields that serve UTC keep serving
  UTC; Local Only is preserved; no external timezone service is introduced.

**Why `tzlocal` rather than a mapping table in this repository.** The brief
asked to avoid an ad-hoc hand-written mapping unless repository evidence
clearly justifies it. There is none: the Windows -> IANA mapping is the
Unicode CLDR `windowsZones` table (roughly 450 entries), which `tzlocal`
bundles and maintains. Hand-copying it would mean owning and ageing that data,
and a stale hand-copy reproduces exactly this defect class -- a wrong hour --
later and less visibly. `tzlocal` is MIT, pure Python, 18 kB, reads only the
local registry, and makes no network call.

---

## D. Blocker 1 -- the fix

| Change | What it does |
| --- | --- |
| `src/mockingbird/time_utils.py` | Adds `_platform_native_zone_name_candidates()` as resolution step 3. Also splits the `/etc/localtime` probe into its own generator -- the previous single generator **`return`ed** when `os.path.realpath` raised, which would have made any later candidate unreachable on exactly the platform that needs it. |
| `pyproject.toml` | `tzlocal>=5.2,<6.0` as a core dependency. |
| `scripts/build_local_product.py` | Mirrors `tzlocal` into `WINDOWS_RUNTIME_REQUIREMENTS`, plus an explicit `tzdata>=2024.1` with a comment recording the marker-vs-tag reason it cannot arrive conditionally. |
| `THIRD_PARTY_NOTICES.md` | `tzlocal` (MIT) and `tzdata` (Apache-2.0; the IANA database it carries is public domain). |

No migration, no backfill, no stored timestamp touched. The fix is entirely at
read time, because the defect was entirely at read time.

`Doctor`'s Clock check needed no change: it already reported `resolved_timezone`
and a detail line that distinguished a named zone from the fallback. It simply
now tells the truth on Windows (§F).

---

## E. Blocker 1 -- automated validation

`tests/test_time_utils.py`: **25 passed** (9 pre-existing, 16 new). The
native-Windows path is exercised by substituting `tzlocal.get_localzone_name`
-- the one function that reads the registry and applies CLDR -- so this Linux
suite genuinely pins the Windows contract. Every assertion is on a **converted
offset or wall-clock value**, never a zone abbreviation string: the defect was
a wrong instant, and a label reading "EST" proves nothing about the arithmetic.

| Requirement | Test |
| --- | --- |
| Windows registry zone -> real IANA zone | `test_native_windows_registry_zone_name_is_resolved_to_a_real_iana_zone` |
| Winter standard time (the reproduced case) | `..._renders_the_reproduced_december_instant_as_standard_time` |
| Summer daylight time | `..._renders_a_summer_instant_as_daylight_time` |
| One zone, both seasons correct from one resolution | `..._one_resolved_zone_serves_both_seasons_correctly` |
| Spring DST transition, both sides | `..._spring_dst_transition_is_correct_on_both_sides` |
| Fall DST transition, both sides (incl. the repeated hour and `fold`) | `..._fall_dst_transition_is_correct_on_both_sides` |
| UTC | `..._utc_zone_resolves_with_a_zero_offset_year_round` |
| Non-DST zones (`America/Phoenix`, `Asia/Kolkata` half-hour offset) | `..._non_dst_zone_has_one_offset_in_both_seasons` |
| Southern-hemisphere inversion | `test_southern_hemisphere_dst_runs_the_opposite_way` |
| Unknown/unmappable Windows zone -> fallback | `test_unmappable_windows_zone_falls_back_without_raising` |
| Registry `OSError` / `LookupError` are non-fatal | `test_platform_native_lookup_raising_any_error_is_non_fatal` |
| Absent `tzlocal` dependency -> fallback, not crash | `test_absent_tzlocal_dependency_falls_back_instead_of_crashing` |
| Ordering: POSIX sources still win | `test_posix_etc_localtime_still_wins...`, `test_tz_environment_variable_still_wins...` |

`tests/test_local_product_packaging.py`: **97 passed**, including a new
`test_windows_runtime_requirements_package_the_windows_timezone_stack` that
guards *both* halves -- `tzdata` is deliberately not a `pyproject.toml`
dependency, so the pre-existing pyproject-mirror test cannot see it at all.

---

## F. Blocker 1 -- native-Windows field validation

**Real Host**: Microsoft Windows 10 Pro, `[System.TimeZoneInfo]::Local.Id` =
`Eastern Standard Time` -- the Windows zone actually relevant to the field
system, read live from the machine.

**Run inside the deployed packaged runtime** (the release's own embedded
CPython 3.12.7 and its own packaged `site-packages`), deliberately mirroring
how §Q-1 was originally reproduced -- not a source checkout:

```
interpreter       : ...\releases\15691d9\python\python.exe
mockingbird from  : ...\releases\15691d9\python\site-packages\mockingbird
tzdata            : present
tzlocal name      : America/New_York
TimeZoneKeyName   : Eastern Standard Time
resolved tz       : America/New_York
IANA key          : America/New_York

winter  2026-12-15 16:00Z   -> 2026-12-15 11:00:00 EST-0500 dst=0:00:00  OK
winter  2026-01-15 16:00Z   -> 2026-01-15 11:00:00 EST-0500 dst=0:00:00  OK
summer  2026-07-15 16:00Z   -> 2026-07-15 12:00:00 EDT-0400 dst=1:00:00  OK
spring- 2026-03-08 06:59:59Z -> 2026-03-08 01:59:59 EST-0500 dst=0:00:00  OK
spring+ 2026-03-08 07:00:00Z -> 2026-03-08 03:00:00 EDT-0400 dst=1:00:00  OK
fall-   2026-11-01 05:59:59Z -> 2026-11-01 01:59:59 EDT-0400 dst=1:00:00  OK
fall+   2026-11-01 06:00:00Z -> 2026-11-01 01:00:00 EST-0500 dst=0:00:00  OK

VERDICT: ALL CASES CORRECT
```

Side by side with the defect as reported at `d5dd1d9`:

| Instant | `d5dd1d9` (field report §Q-1) | `15691d9` (this milestone) |
| --- | --- | --- |
| 2026-12-15 16:00 UTC | 12:00 "Eastern Daylight Time-0400" -- **wrong** | **11:00 EST-0500** |
| 2026-07-15 16:00 UTC | 12:00 EDT-0400 | 12:00 EDT-0400 |
| resolved IANA key | `None` | `America/New_York` |
| `tzdata` | NOT present | present |

**The product's own diagnostic surface, live over HTTP** (`GET
/api/product/doctor`, Administrator session against the running packaged
build):

```
[PASS] clock: Local clock is readable.
       detail: Host local timezone resolved to America/New_York.
       resolved_timezone: America/New_York
```

Before this milestone that same check could only say "Host local timezone
could not be resolved to a named zone; using a fixed UTC-offset fallback."

**Real field observations retain correct chronology and order.** The three
Events this session's own real observation created, plus the seven before
them, rendered through the packaged resolver:

```
event-observation-candidate-151  2026-09-25 14:51:56Z  -> 2026-09-25 10:51:56 EDT-0400
event-observation-candidate-150  2026-09-25 14:49:16Z  -> 2026-09-25 10:49:16 EDT-0400
event-observation-candidate-149  2026-09-25 14:47:51Z  -> 2026-09-25 10:47:51 EDT-0400
event-observation-candidate-148  2026-09-25 05:31:36Z  -> 2026-09-25 01:31:36 EDT-0400
...
event-observation-candidate-142  2026-09-19 21:10:26Z  -> 2026-09-19 17:10:26 EDT-0400

descending order preserved: True
stored values are UTC and untouched by this fix: True
```

**Blocker 1: CLOSED on real native-Windows hardware.**

---

## G. Blocker 2 -- Host-restart root cause

`CameraNodeRecoverySupervisor._eligible_candidates` resumed a Stream only when
`session_manager.status(stream_id)` reported a stopped session whose
`stopped_reason == "camera_unavailable"`. That status comes from
`ObservationEngineSessionManager`'s **in-memory** `_sessions` dict.

- A **Camera Node** outage leaves exactly that object behind, stopped, with
  that reason -- so disconnect/reconnect and Node OS-reboot recovery both work
  (proven live, Field Validation Closure v1 §G/§H).
- A **Host** restart destroys the whole process. Afterwards
  `status(stream_id)` returns `None` for every Stream, so **every** candidate
  is skipped and nothing is ever resumed.

The legacy durable-monitoring lane cannot cover it either: arming it on a
Camera Node Stream is refused outright by design (`409`, "Camera Node streams
use the Observation Engine (Start observing) rather than legacy durable
monitoring").

**So the gap was not a missing resume mechanism. The mechanism existed and
worked; the product had no durable record of whether observation was supposed
to be happening at all.**

---

## H. Blocker 2 -- durable observation-intent contract

The five states the contract distinguishes, and which were durable before:

| State | Durable before? | Meaning |
| --- | --- | --- |
| A user intentionally started observing | **no** | observation *should* be active |
| A transient runtime session object exists | no (in-memory) | observation *is* active in this process |
| The Camera Node temporarily disconnected | in-memory `stopped_reason` | should still be active; already recovered |
| The Host restarted | -- | should still be active; **never recovered** |
| A user intentionally stopped observing | **no** | observation should **not** be active |

Rows 1 and 5 are the two the product could not tell apart across a process
restart, and they are precisely the two that decide whether resuming is
correct or a truth violation.

**`stream_observation_intents`** (schema `v60 -> v61`): `stream_id` primary key
(so a duplicate intent is not representable), `desired_state` CHECK-constrained
to `'observing'`/`'stopped'`, `requested_reason`, `requested_at` (advances only
when the state actually changes), `updated_at`.

**Why a schema change rather than reuse.** Three existing candidates were
checked against the repository, not assumed:

- `stream_monitoring_policies.mode` is the *legacy* lane's intent, and arming
  it for a Camera Node Stream is exactly what the `409` above forbids -- it
  would hand the Stream to `DurableMonitoringSupervisor`, a structurally
  different runtime (`docs/runtime-map.md`). Reusing it would breach an
  accepted boundary to save a table.
- `stream_runtime_checkpoints` is documented as "last-known operational
  metadata; it is never evidence or reviewed truth" and is not written by the
  Observation Engine lane at all.
- `monitoring_exposure_intervals` records healthy *exposure*, not intent, and
  a graceful shutdown closes the open interval -- so it cannot distinguish
  "stopped by the user" from "stopped because the Host went down", which is
  the entire question.

It is operational intent: never evidence, never reviewed truth, carrying no
observation content. Losing the row degrades to exactly the pre-milestone
behaviour (no auto-resume), never to a wrong one.

**Written only at a product action:** Start observing -> `observing`
(`user_started`); Stop observing -> `stopped` (`user_stopped`); archiving a
Source -> `stopped` (`source_archived`) for each of its Streams. **Nothing else
clears it** -- in particular `stop_all(reason=…)` (`api_shutdown`,
`repository_reconfigured`, `local_backup_restore`) is a *runtime* teardown and
deliberately leaves intent alone.

**Clean and crash restarts are therefore one mechanism, not two.** Because the
record is durable rather than a clean-shutdown callback, an abrupt process or
OS kill writes nothing at all and the user's original Start intent is simply
still there. No separate crash-recovery path exists, and none is needed --
proven in the field, §J.

---

## I. Blocker 2 -- the fix

| Change | What it does |
| --- | --- |
| `src/mockingbird/storage/models.py` | `StreamObservationIntentModel`. |
| `src/mockingbird/storage/database.py` | `CURRENT_DATABASE_SCHEMA_VERSION` 60 -> 61, plus `_migrate_to_durable_observation_intent` -- purely additive, `IF NOT EXISTS`, skipped safely if `streams` does not exist yet (migrations run before `create_all`), and creating **zero** intent rows. |
| `src/mockingbird/repository/product_repository.py` | `StreamObservationIntent`, `record_stream_observation_intent`, `get_stream_observation_intent`, `streams_intended_observing` (one query, not an N+1 on the supervisor's per-Stream loop). |
| `src/mockingbird/api/main.py` | Records intent in the Camera Node lane of `observation/start` and `observation/stop`, and on Source archive. |
| `src/mockingbird/observation/camera_node_recovery.py` | Second eligibility class: **no in-process session at all** plus durable intent `observing`. Everything downstream -- health probe, capped backoff, fresh repository-sourced `StreamLivePlaybackConfig`, `session_manager.start()` -- is the existing proven path, unchanged. Backoff bookkeeping keys off the intent's `requested_at` for this class, since it has no `stopped_at` to read. The structured log line now carries `recovery_class` so an operator can tell the two apart. |

**Deliberate non-generalisations.** No new scheduler. No change to
`AnalysisStreamRetryPolicy`, to the legacy `live_monitoring` lane, or to
anything inside a running session. The existing `camera_unavailable` class's
behaviour is byte-for-byte unchanged -- all 18 pre-existing recovery tests
pass untouched except for the fake repository gaining the two new methods.

**Honest limits, disclosed.** A resumed session that fails with a
non-`camera_unavailable` `error` (for example a model-load failure) is not
retried: no eligibility class matches once a session object exists, and the
product reports an honest error state a human can see. That matches the
accepted recovery doctrine rather than extending it. Separately, nothing
restarts the supervisor after `_stop_runtime_activity` (e.g. a local-backup
restore) until the next process start -- pre-existing for the
`camera_unavailable` class too, unchanged here, and noted rather than silently
widened.

### Automated validation

- `tests/test_camera_node_recovery.py`: **30 passed** (18 pre-existing, 12
  new) -- resume on intent; deliberately-stopped stays stopped and is not even
  probed; no intent row is never treated as `observing`; Node unavailable at
  Host start then returning; one start per intent across repeated passes; a
  re-failed resume handing over to the `camera_unavailable` class; a Stop
  landing during the health probe winning the race; a concurrent manual Start
  not being raced; archived Source; lost pairing; non-Camera-Node Stream;
  `shutdown()` quiescing the new class.
- `tests/test_durable_observation_intent.py`: **18 passed** -- schema/migration
  (v60 upgrade creates the table with zero rows and loses nothing; idempotent
  re-run), persistence semantics (`requested_at` stability, PK uniqueness,
  unknown Stream, invalid state, survival across a reopen), and the product
  actions (start records, stop clears, stop with no in-process session still
  clears, no-runtime start records nothing, archive clears).

---

## J. Blocker 2 -- field results

**Topology: the same real Host + real Camera Node used by Field Validation
Closure v1**, deliberately reused rather than rebuilt (a fresh instance would
have forced a disruptive Camera Node re-pair).

| | |
| --- | --- |
| Host | Microsoft Windows 10 Pro (10.0.19045), packaged local product, embedded CPython 3.12.7 |
| Build under test | `15691d9`, confirmed via the product's own `GET /api/product/instance` (`git_commit 15691d9ce5262c6439092c1251df056c0d1e0406`, `build_id 15122a26d0a2a526`), **not** via any deploy helper's claim |
| Detector | MDv5a ONNX, `onnx-cuda` provider active on the real GPU |
| Camera Node | Raspberry Pi 4 (`node-<id>`, `<node-ip>:8787`), real `ov64a40` CSI camera, pairing pre-existing (`pairing_required: false`) |
| Data home | the disposable dev instance carrying real prior field data |
| Schema | migrated **v60 -> v61** on this real field database during deployment |

**Deployment integrity.** Entry counts vs. immediately after the v60 -> v61
migration, read from the real database:

| | before | after migration |
| --- | --- | --- |
| schema | 60 | **61** |
| `stream_observation_intents` table | absent | present |
| intent rows | -- | **0** |
| visits / candidates / media | 169 / 167 / 343 | 169 / 167 / 343 |
| streams / sources / reviewed | 2 / 2 / 2 | 2 / 2 / 2 |

Zero intent rows after upgrading a real installation is the contract's own
requirement: an upgrade must not spontaneously start observing anywhere.

### Clean restart (brief steps A-I)

| Step | Time (UTC) | Observation |
| --- | --- | --- |
| A -- `POST .../observation/start` | 14:45:50 | `state=starting`; intent row written `observing / user_started / 14:45:50.748` |
| B -- real frames processed | 14:46:36 | `state=observing`, `last_healthy_frame_at 14:46:36`, `track_updates_observed 46`, `evidence_candidates_observed 26`, `proposals_observed 2`, `detector_provider_key onnx-cuda` |
| B (continued) | 14:48:51 | 259 track updates, 166 evidence candidates, 19 proposals, **1 real candidate Visit created** |
| C -- `POST /api/product/shutdown` | 14:49:49 | `{"accepted": true}`; port 8000 **FREE** at 14:49:49 |
| -- intent survived the graceful shutdown | 14:49:58 | still `observing / user_started / 14:45:50.748` -- `stop_all("api_shutdown")` correctly did not clear it |
| -- relaunch (`Start MockingBird.vbs`, correct `MOCKINGBIRD_HOME`) | 14:50:01 | `LAUNCHER-OK` |
| D -- **no manual observation start issued** | -- | none, at any point |
| E -- Host answering | 14:50:22 | responding |
| F -- node reconnected | -- | `camera_connected: true`, "Connected to the Camera Node." |
| G -- **observation resumed automatically** | **14:50:12.9** | `state=observing`, fresh `started_at` -- ~12 s after relaunch |
| H -- fresh frames processed | 14:55:55 | `last_healthy_frame_at 14:55:55`, 598 track updates / 263 evidence candidates / 31 proposals / 3 candidates in the resumed session |
| I -- no duplicate state | 14:55:59 | streams **2**, sources **2**, reviewed Visits **2**, intent rows **1**, distinct intent streams **1** -- all identical to entry |

### Intentionally stopped, then restarted (brief steps J-L)

| Step | Time (UTC) | Observation |
| --- | --- | --- |
| J -- `POST .../observation/stop` | 14:56:22 | `state=stopped`, `stopped_reason=user_stopped`; intent rewritten `stopped / user_stopped / 14:56:22.284` |
| K -- Host restarted again | 14:56:29 -> 14:56:42 | graceful shutdown, port free, relaunched |
| L -- **stayed stopped** | 14:56:52 -> 15:02:43 | **20 consecutive polls over ~6 minutes**, every one `state=stopped, observing=false`; intent still `stopped / user_stopped` |

No resume was attempted and the Camera Node was never even probed for this
Stream -- the deliberate Stop held.

### Host starts while the Camera Node is unavailable (brief steps M-P)

| Step | Time (UTC) | Observation |
| --- | --- | --- |
| M -- observation started intentionally | 15:03:23 | `observing` confirmed 15:04:00; intent `observing / user_started` |
| -- Host shut down gracefully | 15:04:13 | port free 15:04:26; intent still `observing` |
| N -- Camera Node taken **offline** | 15:04:27 | `systemctl stop mockingbird-camera-node.service`; node confirmed **unreachable** 15:04:48 |
| N -- Host relaunched with the Node down | 15:04:57 | `LAUNCHER-OK`; **no manual observation start** |
| -- honest non-resume while unreachable | 15:05:14 -> 15:07:33 | 10 consecutive polls, all `state=stopped`; intent still `observing` (the supervisor probing on its capped backoff) |
| O -- Camera Node brought back | 15:07:45 | service `active`; node reachable again **15:08:09** |
| P -- **resumed automatically** | **15:08:38.5** | `starting` at 15:08:38.5 (~29 s after the Node returned), `observing` confirmed 15:09:00 -- no manual intervention |

Credentials and pairing remained valid throughout; only transport was
unavailable. Recovery came from the existing retry/recovery doctrine, not a
new scheduler.

### Crash restart (abrupt process/OS-style kill)

The contract claims clean and abrupt restarts are covered by the same
mechanism; proven rather than asserted.

| Step | Time (UTC) | Observation |
| --- | --- | --- |
| observing, real frames | 15:10:21 | `observing`, `last_healthy_frame_at 15:10:13` |
| **`Stop-Process -Id 42820 -Force`** | 15:10:23 | no graceful shutdown, no `stop_all`, no shutdown callback |
| intent after the crash | 15:10:26 | `observing / user_started / updated_at 15:03:23.287` -- **unchanged**, i.e. the dying process wrote nothing |
| relaunch, no manual start | 15:10:36 | `LAUNCHER-OK` |
| **resumed automatically** | **15:10:41.0** | `observing` confirmed 15:10:55 |

Doctor correctly reported `[WARN] application: The previous MockingBird run did
not shut down cleanly` afterwards -- honest about the kill, and not confused by
it into losing the intent.

---

## K. Truth / data-safety verification

Across **four Host restarts** (two graceful, one graceful-with-Node-offline,
one abrupt kill) on a real field database:

| Property | Result |
| --- | --- |
| Database integrity | `PRAGMA quick_check` -> **ok** |
| Duplicate Streams / Sources | none: **2 / 2** throughout, identical to entry |
| Duplicate durable observation session | not representable: **1** intent row, **1** distinct intent Stream |
| Duplicate Visit ids | **0** |
| Reviewed truth | **2** reviewed Visits and **2** review labels, unchanged -- no Inferred -> Reviewed promotion, nothing fabricated |
| Evidence / media loss | none: 343 -> **359** assets, growth only from real new observation; `[PASS] media_integrity` |
| Existing UTC event truth | unaltered; stored values still UTC, ordering preserved (§F) |
| Intentionally stopped observation restarted | **never** (§J, steps J-L) |
| Phantom-online state | none -- `state=stopped` was reported honestly while the Node was unreachable, and nothing claimed observing until the engine did |
| Schema | **v61**, `[PASS] database_schema: Database schema is current.` |

Final Doctor on the fixed build: `clock` **PASS** (`America/New_York`),
`media_integrity` **PASS**, `database_schema` **PASS**, `camera_node` **PASS**,
`detector_model` / `species_identification` / `gpu_cuda` **PASS**. Two WARNs,
both correct: `application` (the last restart genuinely was an abrupt kill) and
`storage` (15.1 GB free -- the pre-existing, already-disclosed low-disk
condition).

---

## L. Validation summary

**Tier 1 -- directly relevant, run fresh:**

| Suite | Result |
| --- | --- |
| `tests/test_time_utils.py` | 25 passed |
| `tests/test_durable_observation_intent.py` | 18 passed |
| `tests/test_camera_node_recovery.py` | 30 passed |
| `tests/test_local_product_packaging.py` | 97 passed |

**Tier 2 -- 26 affected suites** (timezone/local-time consumers, observation
sessions, Camera Node recovery, Host startup/shutdown, health/diagnostics,
schema/migration, the five schema-guard files): **804 passed, 1 failed**.

The single failure is
`test_environmental_context.py::test_temperature_band_established_once_enough_days_are_cached`
-- **re-confirmed pre-existing** by direct `git stash` bisection against the
unmodified baseline in this same session (identical assertion failure with the
milestone's changes fully stashed), and already recorded in
`docs/release-execution-state.md` §14's accepted Core checkpoint as one of its
five known failures.

`ruff` on every changed file: **81 findings before and 81 after** on the
identical file set -- zero new findings.

**Tier 3 -- full Core**: run, because this milestone changes restart semantics
and the schema. Result recorded in §M below.

---

## M. Tier 3 Core result

**Run:** `.venv/bin/python -m pytest -m "not slow"` (the full Core gate) at this
milestone's implementation HEAD.

```
11 failed, 6205 passed, 4 skipped, 35 deselected, 11 xfailed,
284 warnings in 2460.46s (0:41:00)
```

**Failures attributable to this milestone: ZERO.** That is not asserted from the
names -- every one of the eleven was classified against a real baseline:

1. **All eleven reproduce deterministically when run in isolation** (4.77 s, same
   eleven). None is order-dependent and none is flaky, so "flaky" was rejected as
   a label rather than used as one.
2. **All eleven fail identically at the pre-correction baseline `8a45d1a`** --
   this milestone's own starting commit, checked out and re-run (4.25 s, same
   eleven, same assertions). This is the decisive evidence: the failure set is
   bit-for-bit the same before and after the corrections, so no correction in
   this milestone caused, unmasked or worsened any of them.

This mattered rather than being a formality: the milestone *did* change
`src/mockingbird/time_utils.py`, and six of the eleven are local-day/`Today`
assertions. Attribution was genuinely plausible and had to be disproved, not
waved away.

### Group 1 -- the established recorded pre-existing set (4 of 11)

Already of record in
[performance-scale-stability-closure-v1-report.md](performance-scale-stability-closure-v1-report.md)
§X and re-confirmed by
[review-queue-scale-closure-v1-report.md](review-queue-scale-closure-v1-report.md)
§W:

| Test | Status |
| --- | --- |
| `test_doctor_camera_node_transport.py::test_interpret_no_transport_configured_anywhere_is_pass` | pre-existing, of record |
| `test_doctor_camera_node_transport.py::test_interpret_ignores_sources_without_transport_configured` | pre-existing, of record |
| `test_environmental_context.py::test_temperature_band_established_once_enough_days_are_cached` | pre-existing, of record |
| `test_place_change_summary_repository.py::test_api_round_trip_exposes_change_detection_fields` | pre-existing, of record (that file's own long-documented date-sensitive fixture) |

Two members of that recorded six-set did **not** fail here
(`test_place_biodiversity_summary_repository.py`, both cases), so this run is a
strict improvement on that set, not a regression of it.

### Group 2 -- pre-existing, but NOT previously recorded (7 of 11)

These seven are new relative to the recorded set, so "pre-existing" was not
accepted on the baseline run alone -- the first bad commit was located:

| Test |
| --- |
| `test_canonical_new_regular_species_consistency.py::test_today_and_bird_log_agree_on_new_species` |
| `test_dashboard_today.py::test_today_summary_uses_selected_local_day_and_current_reviewed_truth` |
| `test_dashboard_today.py::test_today_summary_regulars_require_usable_day_coverage_and_exclude_non_nature_records` |
| `test_dashboard_today.py::test_today_summary_new_today_is_wildlife_inclusive_not_bird_only` |
| `test_dashboard_today.py::test_today_summary_counts_a_confirmed_kind_level_mammal_as_real_activity` |
| `test_dashboard_today.py::test_today_summary_best_moments_caps_one_species_and_stays_diverse` |
| `test_dashboard_today.py::test_today_summary_moves_from_likely_to_confirmed_without_duplication` |

**Bisected:** `73dbcd4` **PASS** -> `3d78f8a` **FAIL**, and `73dbcd4` is
`3d78f8a`'s direct parent, so the attribution is exact. First bad commit:
`3d78f8a` *"Review Queue Scale Closure v1 (1/n): bulk-preload the queue build's
last three per-item reads"* (2026-09-23) -- **two milestones before this one**,
and already broken at this milestone's `8a45d1a` baseline.

**Root cause, read from the code rather than inferred from the symptom.**
`_preloaded_motion_evidence_for_review_queue_item` returns an *authoritative*
`None` -- not its own `_PRELOAD_MISS` sentinel -- for any Visit/Event that is
simply absent from the preloaded set. Its guards check only that the cache
exists and that a Visit/Event id was supplied; they never check whether *this*
target is one the preload actually covered. `_read_only_build_cache`'s contract
is that "nested builds share the outermost cache and never clear it early", and
`dashboard_summary` opens that outermost cache, calls
`_visible_review_queue_items` **first** (which runs `_preload_review_queue_rows`
and so populates `review_queue_motion_evidence` for the *queue's* member set
only), and **then** calls `_dashboard_today_summary`, whose counting loop calls
`_motion_evidence_for_review_queue_item` for Today's Visits. Reviewed/confirmed
Visits are not queue members, so they receive `evidence=None`, which makes
`_review_queue_product_context` classify `detector_class != "animal"`, and
`detector_qualified_animal_visit_count` collapses toward 0.

Every symptom matches: counts collapse to `0`, the "New Today" maps come back
empty, and all seven failing cases add their Visits with `reviewed_label=`.

**This is a real user-facing truth regression, not a test artifact** -- the
affected field is what the landing page's Today panel reports. It is recorded in
§O as a newly-identified pre-existing release-blocker candidate. It was **not
fixed here**: it belongs to a different milestone's change, and fixing it is
outside this milestone's authorized scope (fix exactly the two field blockers
and their direct dependencies).

---

## Closure confirmations (durable intent, migration safety, field integrity)

Recorded explicitly so the acceptance decision does not have to re-derive them.
Each line cites existing evidence; nothing here was re-run for its own sake.

### Durable observation-intent semantics -- confirmed

The `stream_observation_intents` table (schema v61) means exactly this, and each
clause is covered by a named, currently-passing test:

| Contract clause | Evidence |
| --- | --- |
| Intentional **Start Observing** -> durable intent **ACTIVE** (`observing`) | `test_start_observing_records_durable_observing_intent`; field step A (intent row written `observing / user_started / 14:45:50.748`) |
| Runtime teardown/restart does **not** clear that intent | `test_stopping_clears_the_intent_without_deleting_the_row` + §H's `stop_all` boundary; field: intent survived `POST /api/product/shutdown` and survived an abrupt `Stop-Process -Force` with `updated_at` unchanged |
| Intentional **Stop Observing** -> durable intent **STOPPED** | `test_stop_observing_records_durable_stopped_intent`, `test_stop_observing_clears_intent_even_with_no_session_in_this_process` |
| Restart restores **only** ACTIVE intent | `test_host_restart_resumes_a_stream_whose_durable_intent_is_observing`, `test_host_restart_leaves_a_deliberately_stopped_stream_stopped`, `test_host_restart_never_starts_a_stream_with_no_recorded_intent` (an absent row is never read as observing) |
| An **offline Node at Host startup** stays recoverable when it returns | `test_host_restart_with_an_unavailable_node_resumes_once_it_returns`; field steps M-P (resumed ~29 s after the Node returned, no manual action) |
| **No legacy monitoring supervisor** is activated for Camera Node Streams | `test_host_restart_never_resumes_a_non_camera_node_stream`, `test_non_camera_node_stream_is_ignored`, `test_host_restart_never_resumes_a_stream_that_lost_its_pairing`, `test_host_restart_never_resumes_an_archived_sources_stream`; §H's explicit rejection of `stream_monitoring_policies.mode` reuse, and `camera_node_recovery.py`'s docstring: the legacy `live_monitoring` lane and `DurableMonitoringSupervisor` are not touched at all |

Re-confirmed green at the final HEAD:
`test_durable_observation_intent.py`, `test_camera_node_recovery.py`,
`test_time_utils.py`, `test_unified_observation_status.py` -> **103 passed**.

### v60 -> v61 migration safety -- confirmed

Covered by tests **and** by the real field deployment; not repeated here.

| Requirement | Evidence |
| --- | --- |
| v60 -> v61 migration succeeds | `test_schema_61_registers_the_intent_migration_and_stays_reachable`, `test_upgrading_from_schema_60_creates_the_table_and_no_intent_rows`, `test_a_fresh_install_has_the_intent_table`, `test_the_migration_is_idempotent`; field: real field database migrated 60 -> **61** during deployment |
| Sources / Streams / Visits / Reviews / media intact | field (§J): visits/candidates/media **169 / 167 / 343 -> 169 / 167 / 343**; streams/sources/reviewed **2 / 2 / 2 -> 2 / 2 / 2** |
| Backup / migration safeguards still functional | field: pre-migration safety backup taken as part of deployment; `[PASS] database_schema`, `[PASS] media_integrity`, `PRAGMA quick_check` **ok** |
| Migration creates **no** accidental ACTIVE intent | field: **0 intent rows** immediately after the upgrade; `test_upgrading_from_schema_60_creates_the_table_and_no_intent_rows` asserts the same invariant. An upgrade must not spontaneously start observing anywhere -- and did not |

### Final field-integrity check -- already obtained, restated

From §J and §K on the real native-Windows Host + real Camera Node. **Not
re-run**: no correction in this closure pass changed any of these paths.

| Check | Result |
| --- | --- |
| Graceful Host restart while ACTIVE | **resumes automatically**, ~12 s (14:50:12.9), fresh frames confirmed |
| Deliberate STOP, then restart | **stays stopped** -- 20 polls / ~6 min, Node never probed |
| Host starts while Node offline | honest `stopped` while unreachable, then **resumes automatically** ~29 s after the Node returned (15:08:38.5) |
| Abrupt process kill while ACTIVE | **resumes automatically** (15:10:41); dying process wrote nothing |
| Duplicate Visit ids | **0** |
| Duplicate Reviewed truth | none -- 2 reviewed Visits / 2 labels throughout; no Inferred -> Reviewed promotion |
| Source/Stream relationships | unchanged -- 2 / 2 throughout; 1 intent row, 1 distinct intent Stream |
| Media loss | none -- 343 -> 359 assets, growth only from real new observation; `[PASS] media_integrity` |
| Local Only preserved | yes -- no external timezone service, no network dependency added; timezone resolved from CLDR data packaged offline |
| Database integrity | `PRAGMA quick_check` **ok**; schema **v61** `[PASS]` |

---

## N. Final HEAD / schema / protected files / push

| | |
| --- | --- |
| Correction implementation commit | `15691d9` |
| Field-evidence commit | `2cdb39b` |
| Acceptance-closure commit | this report's own commit (Tier 3 classification, the `camera_connected` disposition and these confirmations); no source file changed in it |
| Schema | **v61** (`v60 -> v61`, one additive table); `CURRENT_DATABASE_SCHEMA_VERSION = 61` |
| Version | `0.1.0`, unchanged |
| Protected files | all seven verified **present, untracked, byte-identical** to their entry hashes at every commit boundary -- re-verified again at closure, see the table below; `uv.lock` untouched and still untracked |
| Staging | explicit full paths only; no `git add -A`, no `git add .` |
| Push | **not pushed.** No tag, no publish, no remote operation |

**Protected-file re-verification at closure**, against the hashes of record in
[field-validation-closure-v1-report.md](field-validation-closure-v1-report.md) §B:

| File | SHA-256 (first 16) | Match | Tracked? |
| --- | --- | --- | --- |
| `docs/wildlife-detector-training-contract.md.orig` | `63f9e5ba142069da` | yes | untracked |
| `scripts/evaluate_small_bird_detector.py` | `81cdff0423f12112` | yes | untracked |
| `scripts/materialize_wildlife_stage2.py.orig` | `ade97d9d46f44661` | yes | untracked |
| `scripts/train_wildlife_stage2_rfdetr.py.orig` | `a24aa6e294c04df1` | yes | untracked |
| `src/mockingbird/detectors/small_bird_benchmark.py` | `e85a2315fbe1487e` | yes | untracked |
| `src/mockingbird/training/wildlife.py.orig` | `548f0706b5498b02` | yes | untracked |
| `tests/test_small_bird_benchmark.py` | `abad318b8df14c20` | yes | untracked |

`uv.lock` (`f36f26ba9fffcbd8`) also untouched and untracked. The working tree
carries these eight untracked files and **nothing else** -- no modified tracked
file at any point in this closure pass.

The baseline comparison in §M required checking out `8a45d1a` in a detached
HEAD and returning to `main`; that is a read-only navigation of committed
history, it cannot touch untracked files, and the hashes above were re-taken
afterwards to prove it did not.

---

## O. Remaining v0.1 field blockers

**None.** Both blockers this milestone was authorized to fix are closed with
real native-Windows + real Camera Node evidence.

Two findings from Field Validation Closure v1 remain **deliberately unfixed**,
exactly as the brief directed, and neither proved to be a dependency of either
fix:

- **Q-2** -- the Camera Node's startup self-test is served stale for the
  service's lifetime. Still present (observed again live this session:
  `self_test: degraded / provider_enumeration_timed_out` on a Node whose
  camera then worked perfectly). Invisible in the product -- the Host never
  reads it -- and pessimistic in direction. Not a blocker.
- **Q-4** -- a false-Visit burst during camera re-initialisation, with
  duplicated evidence bytes. Within accepted, disclosed product behaviour
  (human review is the product's answer to false Visits).

One observation worth recording for a future milestone, not fixed here and not
a blocker: while the Camera Node was genuinely unreachable, the observation
status projection still reported `camera_connected: true` from its stale
last-seen value. Nothing acted on it -- the supervisor probes live health, and
Doctor's own `camera_node` check reported the staleness honestly -- but the
Stream-level field is optimistic in that window. It is a pre-existing status
projection this milestone did not touch.

### The stale `camera_connected` field -- traced and dispositioned

The observation above (`camera_connected: true` while the real Camera Node was
genuinely unreachable) was given one bounded producer/consumer trace. Findings:

**Producer.** Two, both in `src/mockingbird/observation/`:
`engine_runtime.py` owns `_camera_connected` for a *live* session, and
`unified_status.py` projects it for every lane. The field observation came from
`camera_node_facts()`'s **no-session** branch
([unified_status.py:233-272](../src/mockingbird/observation/unified_status.py)),
which derives connectivity from `config.camera_node_last_seen_at`.

**Consumers.** Outside the two producers, `camera_connected` is read in exactly
three places, all **display-only**: `api/schemas.py:1557` (the wire field),
`api/main.py:10930` (choosing which of two messages to show),
`api/main.py:11909` (pass-through). One further use,
`unified_status.py:210`, gates the `edit_camera_setup` UI link. **No recovery,
resume, admission or control-flow path reads it** -- `camera_node_recovery.py`
does not reference it at all, which is why the field run's supervisor still
recovered correctly while the field was optimistic.

**Is it user-facing? Yes -- this must be recorded plainly rather than
dismissed.** `web/src/components/ObservationControlPanel.tsx:267` renders
`<strong>Camera</strong> {status.camera_connected ? "Healthy" : "Needs
attention"}`, and that panel is embedded by **`StreamDetailPage.tsx:4151`** (the
Stream detail release surface) and **`OnboardingWizard.tsx:435`**. It is the
only consumer, and it renders that line *only* when `state !== "observing"` --
precisely the stopped/no-session branch the stale path feeds. So during the
outage window a user on Stream detail did read "Camera Healthy". It is **not**
surfaced on Cameras, Dashboard or Doctor, and Doctor's own `camera_node` check
reports staleness honestly and independently.

**Is it documented as last-seen state, or presented as current connectivity?**
Presented as current (`"Camera Node is paired and ready."`), **but bounded and
deliberate, not unbounded staleness.** `CAMERA_NODE_LAST_SEEN_STALE_AFTER_SECONDS
= 300.0`; past it the same branch returns `camera_connected=False` with
`"Camera Node offline -- last seen N minute(s) ago."` Both halves are existing,
passing regression tests introduced by Camera Node Boot Identity + Autonomous
Recovery v1:
`test_camera_node_never_started_with_stale_last_seen_reports_offline` (60 min ->
offline) and `test_camera_node_never_started_with_fresh_last_seen_reports_connected`
(2 min -> connected, "a deliberate, disclosed scope boundary").

**The field observation fell inside that window.** Node stopped 15:04:27,
confirmed unreachable 15:04:48, polls ran 15:05:14 -> 15:07:33 -- at most ~186 s
against a 300 s threshold. Nothing was observed outside it.

**Disposition: nonblocking deferred field-quality issue. Not fixed.** The
brief's rule A and rule B do not cleanly cover this case, so the reasoning is
stated rather than a branch merely claimed:

- Rule A's premise does **not** fully hold -- the value *is* on a user-facing
  product surface. That half of A is not claimed here.
- Rule B's condition is literally met for up to five minutes, but what it targets
  -- a stale last-seen value masquerading indefinitely as live connectivity --
  is **not** what exists. What exists is a heartbeat freshness window with an
  explicit threshold, an honest post-threshold message, and regression tests
  asserting both sides.
- Decisively: "fixing" it would mean **reversing an explicitly accepted product
  decision** encoded in a currently-passing test
  (`..._with_fresh_last_seen_reports_connected`). Narrowing the window or
  rewording the fresh-window copy is a product change to an accepted trade-off,
  not a narrow defect repair, and is therefore outside this milestone's
  authorized scope (fix exactly the two blockers and their direct dependencies).

No live-probe or recovery behaviour was altered, and no Node self-test behaviour
was touched. If the owner judges a 300 s optimistic window unacceptable on
Stream detail, the narrowest available change is to the fresh-window *wording*
(state last-seen age rather than "paired and ready"), which leaves the threshold,
the probe and the recovery path untouched -- offered as an option, not taken
here.

### Newly identified: a pre-existing Dashboard/Today truth regression (NOT this milestone's)

Found while classifying the Core run (§M), not by a health audit, and reported
because leaving a known user-facing truth defect unrecorded would be worse than
reporting one outside this milestone's scope.

`dashboard_summary`'s Today counts collapse toward `0` for **reviewed/confirmed**
Visits, because a review-queue bulk preload populated earlier in the *same shared
read cache* answers Today's motion-evidence lookups with an authoritative `None`
for Visits the queue never covered. Full mechanism, bisect and first bad commit
(`3d78f8a`, Review Queue Scale Closure v1, 2026-09-23) are in §M.

- **Attribution:** a prior milestone. Present and identical at this milestone's
  `8a45d1a` baseline; nothing here caused or touched it.
- **Severity:** the landing page's Today panel under-reports confirmed activity
  -- a truth regression on a primary release surface, not cosmetic.
- **Status:** **not fixed** (outside authorized scope). Recorded as a
  **release-blocker candidate for the owner's decision**, and it is the one item
  in this report that may bear on whether v0.1 is shippable.
- **Caveat on scope of proof:** seven tests and the code path are the evidence.
  The blast radius beyond `dashboard_summary` was deliberately **not** swept --
  the same authoritative-`None` shape could in principle affect any builder that
  runs inside a shared cache after a queue preload. Establishing that is the
  fixing milestone's job, and this report does not claim it is confined to Today.

---

## P. Scheduler position

Field Validation Closure v1 remains **executed but not accepted**. This
milestone claims no global acceptance of it -- only that the two field
corrections it was blocked on are now implemented and re-proven on the same
real hardware.
