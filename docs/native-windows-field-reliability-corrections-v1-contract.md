# Native-Windows Field Reliability Corrections v1 -- Contract

Bounded correction milestone. Fixes exactly the two v0.1-critical defects
reproduced on real native-Windows + real Camera Node hardware during
*Field Validation Closure v1* (`docs/field-validation-closure-v1-report.md`,
findings Q-1 and Q-3). Nothing else in that report's §Q is in scope: Q-2
(stale Node startup self-test) and Q-4 (camera-re-initialisation false-Visit
burst with duplicated evidence bytes) are explicitly **not** fixed here and
were not found to be dependencies of either fix.

Starting baseline: HEAD `8a45d1a`, schema `v60`.

---

## Blocker 1 -- Windows local-time correctness

### What was actually wrong

`time_utils.resolve_host_local_timezone()` could only ever discover an
IANA zone name two ways, both POSIX-only: the `TZ` environment variable, and
the `/etc/localtime` symlink target. Native Windows satisfies neither -- it
names its zone in its own vocabulary, in the registry
(`HKLM\SYSTEM\CurrentControlSet\Control\TimeZoneInformation`,
`TimeZoneKeyName`, e.g. `"Eastern Standard Time"`), and ships no zoneinfo
database for `zoneinfo.ZoneInfo` to read. So every native-Windows Host fell
straight through to the last-resort branch: a **fixed-offset snapshot of the
current moment's offset**, then applied to every timestamp regardless of its
date.

Reproduced in the packaged Windows runtime at `d5dd1d9`:

```
resolved tz : Eastern Daylight Time | IANA key: None
tzdata      : NOT present
  2026-07-15 16:00 UTC -> 12:00 EDT-0400                          (correct)
  2026-12-15 16:00 UTC -> 12:00 "Eastern Daylight Time-0400"      (WRONG: 11:00 EST)
```

Two independent causes, and the reason "just add `tzdata`" is not the fix:

1. **No Windows -> IANA name derivation existed anywhere in the product.**
   `tzdata` supplies zone *rules*; it does not tell anything what this
   host's zone is *called* in IANA terms. With `tzdata` alone the resolver
   would still have reached the fixed-offset branch.
2. **`tzdata` genuinely was not packaged either.** Both `astral` and (now)
   `tzlocal` declare `tzdata` conditionally for Windows, but
   `build_local_product.install_windows_runtime_dependencies` resolves
   environment markers against the **Linux build host** while only the wheel
   *tags* honor `--platform win_amd64` -- the same marker-vs-tag asymmetry
   already worked around for `uvicorn[standard]`/`uvloop`. Both conditional
   requirements evaluate False at build time, so `tzdata` was silently never
   installed. Confirmed in the field, not assumed.

Both had to be fixed for either to matter.

### The contract

- A historical or future timestamp is converted using the timezone's rules
  **for that timestamp**, including DST transitions. One current UTC offset
  sampled once and reused for a range is not an acceptable substitute.
- Resolution order, most authoritative first:
  1. `TZ`, if it names a real IANA zone.
  2. The `/etc/localtime` symlink target (POSIX).
  3. **`tzlocal.get_localzone_name()`** -- platform-native lookup. On native
     Windows this is registry `TimeZoneKeyName` -> CLDR `windowsZones` ->
     IANA key. Deliberately an *established* mapping mechanism (the CLDR
     table `tzlocal` bundles and maintains), **not** a hand-written mapping
     table in this repository: there is no repository evidence justifying
     owning and ageing a ~450-entry Unicode CLDR table by hand, and a stale
     hand-copy is exactly the failure mode that produces a wrong hour again.
  4. Fixed-offset snapshot of the current offset -- the pre-existing,
     disclosed, honest degradation, now reached only when every named-zone
     path above genuinely fails.
- Steps 1 and 2 keep absolute precedence, so **no Linux/macOS deployment's
  resolution changes**; step 3 is appended, never inserted.
- The resolver still **never raises**. An absent `tzlocal`, a registry
  `OSError`, a `LookupError`, and a `TimeZoneKeyName` CLDR cannot map all
  degrade to step 4.

### What is deliberately unchanged

- **Stored UTC truth is not rewritten.** No migration, no backfill, no
  timestamp in any existing row is touched. The defect was in *derivation
  at read time*; the fix is entirely at read time.
- **API fields that intentionally serve UTC keep serving UTC.** The API
  boundary was already unambiguous (`…Z` suffix, Field Validation Closure
  v1 §N) and is untouched.
- **Frontend-side rendering is untouched.** The seven `toLocale*` call sites
  in `web/src` convert an explicit UTC instant in the viewer's own browser
  zone, which was already correct.
- **Local Only is preserved.** `tzlocal` and `tzdata` are pure-Python,
  offline, read the local registry / a bundled database, and make no network
  call. No external timezone service is introduced.

### Affected server-side local-time surfaces

Every caller of `resolve_host_local_timezone` -- all of which were wrong on
native Windows for roughly five months of the year, and are now correct:

| Surface | Call site |
| --- | --- |
| Place activity report (DST-aware hour/day bucketing) | `product_repository.place_activity_report` |
| Place Story | `product_repository.place_story` |
| Year-over-year period resolution | `product_repository._year_over_year_resolve_period` |
| Place Feature detail / Feature comparison overview | `product_repository.get_place_feature_detail`, `…get_place_feature_comparison_overview` |
| Conservation report | `product_repository.conservation_report` |
| Attention signal synchronisation | `product_repository.sync_attention_signals` |
| Folder-import local date attribution | `product_repository.import_source_folder_media_assets` |
| iNaturalist CSV observation date/time | `ecological.inaturalist_csv` |
| Doctor Clock check (`resolved_timezone`) | `diagnostics.doctor._gather_clock` |

### Licensing

`tzlocal` MIT; `tzdata` Apache-2.0 (the IANA database it carries is public
domain). Both recorded in `THIRD_PARTY_NOTICES.md`.

---

## Blocker 2 -- Host-restart observation recovery

### What was actually wrong

`CameraNodeRecoverySupervisor` resumes a Stream only when
`session_manager.status(stream_id)` reports a **stopped session whose
`stopped_reason == "camera_unavailable"`**. That status comes from the
session manager's **in-memory** `_sessions` dict.

A Camera Node outage leaves exactly that in-memory object behind, so
disconnect/reconnect and Node OS-reboot recovery both work (proven live,
Field Validation Closure v1 §G/§H).

A **Host** restart destroys the whole process. After it,
`status(stream_id)` returns `None` for every Stream, so the supervisor's
`_eligible_candidates` skips all of them and nothing ever resumes. The
legacy durable-monitoring lane cannot cover this either: arming it on a
Camera Node Stream is refused outright by design (`409`, "Camera Node
streams use the Observation Engine (Start observing) rather than legacy
durable monitoring").

So the gap was not a missing resume mechanism. **The resume mechanism
existed and worked; the product had no durable record of whether observation
was supposed to be happening at all.**

### The distinctions that matter

| State | Durable? before | Meaning |
| --- | --- | --- |
| A user intentionally started observing | **no** | observation *should* be active |
| A transient runtime session object exists | no (in-memory) | observation *is* active in this process |
| The Camera Node temporarily disconnected | in-memory (`stopped_reason`) | should still be active; already recovered |
| The Host restarted | -- | should still be active; **never recovered** |
| A user intentionally stopped observing | **no** | observation should **not** be active |

Rows 1 and 5 are the two the product could not tell apart across a restart,
and they are the two that decide whether resuming is correct or a violation.

### The durable observation-intent contract

A new, narrow table, `stream_observation_intents` (schema `v60 -> v61`):

| Column | Meaning |
| --- | --- |
| `stream_id` | PK, FK `streams.id` -- at most one intent per Stream, so no duplicate intent row is representable |
| `desired_state` | `'observing'` or `'stopped'` (CHECK-constrained) |
| `requested_reason` | why it last *changed* (`user_started`, `user_stopped`, `source_archived`, `automatic_resume`) |
| `requested_at` | when `desired_state` last actually changed |
| `updated_at` | when the row was last written |

**Why a schema change rather than reuse.** Three existing candidates were
checked against the repository, not assumed:

- `stream_monitoring_policies.mode` (`off`/`armed`/`paused`) is the *legacy*
  lane's intent, and arming it for a Camera Node Stream is the exact thing
  the `409` above forbids -- it would hand the Stream to
  `DurableMonitoringSupervisor`, a structurally different runtime
  (`docs/runtime-map.md`). Reusing it would breach an accepted boundary to
  save a table.
- `stream_runtime_checkpoints` is documented as "last-known operational
  metadata; it is never evidence or reviewed truth" and is not written by
  the Observation Engine lane at all.
- `monitoring_exposure_intervals` records healthy *exposure*, not intent,
  and a graceful shutdown closes the open interval -- so it cannot
  distinguish "stopped by the user" from "stopped because the Host went
  down", which is the entire question.

So the intent genuinely did not exist, and this is the minimal durable shape
that expresses it. It is operational intent: **never evidence, never
reviewed truth**, carries no observation content, and is safe to lose (a
lost row degrades to exactly the pre-milestone behaviour -- no auto-resume).

**Where it is written.** At the product action, not inside the runtime:

- `POST /api/streams/{id}/observation/start`, Camera Node lane ->
  `desired_state='observing'`, reason `user_started`. Recorded only when the
  engine actually accepted the start (state not `error`), so a start that
  failed outright never leaves behind an intent that would be resumed later.
  The field-acceptance compatibility preflight returns *before* the engine
  starts and therefore never records intent.
- `POST /api/streams/{id}/observation/stop`, Camera Node lane ->
  `desired_state='stopped'`, reason `user_stopped`.
- Archiving a Source -> `desired_state='stopped'`, reason `source_archived`,
  for each of its Camera Node Streams.
- **Nothing else clears it.** In particular `stop_all(reason=…)` --
  `api_shutdown`, `repository_reconfigured`, `local_backup_restore` -- is a
  *runtime* teardown and deliberately leaves intent alone. That is precisely
  what makes restart recovery work, and it is why the contract is durable
  intent rather than a clean-shutdown callback: an abrupt process kill or
  power loss writes nothing at all, and the intent from the user's original
  Start is still there. **Clean restart and crash/OS-kill restart are
  therefore covered by exactly the same mechanism**, with no separate
  crash-recovery path.

**Where it is read.** `CameraNodeRecoverySupervisor` gains a second
eligibility class, alongside the existing `camera_unavailable` one:

> a Camera Node Stream with **no in-process session at all**
> (`status(stream_id) is None`) whose durable intent is `observing`.

Everything downstream is the existing, proven path, unchanged: the same
bounded health probe, the same capped backoff schedule, the same
repository-sourced fresh `StreamLivePlaybackConfig`, the same
`session_manager.start()`. If the Node is unavailable when the Host starts,
the existing backoff simply keeps probing and resumes when it returns --
which is the "Host starts while the Node is offline" requirement, satisfied
by the accepted recovery doctrine rather than by a new scheduler.

### Safety properties this contract guarantees

- **A deliberately stopped observation stays stopped.** Its intent is
  `'stopped'`, so neither eligibility class matches, across any number of
  restarts.
- **No blind "start every Camera Node on boot".** A Stream that has never
  been started has no intent row, and an absent row is *not* treated as
  `observing`.
- **No duplicate durable session.** Intent is one row per Stream (PK), and
  `session_manager.start()` is already idempotent per Stream.
- **No duplicate Source/Stream/Place state.** The supervisor only ever
  calls `start()` on an existing Stream; it creates nothing.
- **No Reviewed-truth or evidence effect.** Resuming runs the same
  unmodified admission stack a manual Start runs; `Inferred` stays
  `Inferred`.
- **No phantom-online state.** Nothing reports observing until the engine
  itself does; a failed resume leaves an honest stopped/error status.
- **An archived Source is never resumed** (both the new intent write and the
  supervisor's pre-existing archived-Source guard).

### Out of scope, confirmed not dependencies

Camera Node pairing; ordinary disconnect/reconnect; Node OS-reboot recovery;
Doctor media integrity; performance; Review Queue; UI redesign; models;
thresholds; BirdNET; multi-site; mobile; LTE/solar; custom hardware; Q-2;
Q-4.
