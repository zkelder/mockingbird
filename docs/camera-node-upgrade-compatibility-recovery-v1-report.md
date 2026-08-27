# Camera Node Upgrade & Compatibility Recovery v1

**Roadmap phase:** Lane L (Appliance / Update / Recovery), §6 of
[release-execution-state.md](release-execution-state.md). Host-side
install/upgrade/recovery was substantially closed by Release Engineering
Foundation v1 (2026-08-25); Camera Node install/reboot/reprovision/
replacement hardening was already accepted (Camera Node Installer /
Service / Reboot Hardening v1; Camera Node Boot Identity + Autonomous
Recovery v1; Camera Node Configuration Backup + Reprovision / Replacement
Recovery v1). The one remaining, explicitly-named gap was a Camera Node
**upgrade** workflow specifically -- as distinct from install/reboot/
reprovision, which already existed. This milestone closes that gap.

## 1. Identity

- **Starting HEAD:** `9dec2e5` (the reconciliation commit accepting
  Representative Multi-Camera Field Acceptance & Release-Budget Evidence
  v1; implementation commit beneath it: `ea00b3b`).
- **Schema:** v57, unchanged by this milestone (no database schema
  touched -- this is deployment/packaging tooling, not product truth).
- **Camera Node versions exercised:** see "Real acceptance," below.
- **Real hardware/process environment:** see "Real acceptance," below.

## 2. Existing state

### What was already built

`scripts/install_camera_node.py` (Camera Node Installer / Service / Reboot
Hardening v1, 2026-08-18, extended by two later milestones) already had
real, tested update/rollback *mechanics*:

- `install_or_update_venv` compared a candidate artifact's `manifest.json`
  `provenance.build_id` against the currently-installed one and treated an
  unchanged `build_id` as a no-op;
- a changed `build_id` retired the current `venv`/`manifest.json` to
  `venv.previous`/`manifest.json.previous` (exactly one retained prior
  version) and installed the new one;
- `--rollback` swapped `venv`/`manifest.json` back with the retained
  `.previous` pair and restarted the service;
- `--export-config`/`--import-config` (Camera Node Configuration Backup +
  Reprovision / Replacement Recovery v1, 2026-08-21) backed up/restored the
  portable subset of `node.env`;
- a bounded local `GET /node/v1/health` check ran after every
  install/rollback.

This is genuinely substantial -- re-running the installer with a newer
artifact was already the intended "upgrade" path, was already idempotent,
and already kept a rollback target. Investigation question 16 in the
governing brief ("is there already enough machinery... or is real
implementation missing") therefore had a real, non-trivial answer: **both**
-- the orchestration/vocabulary existed, but four concrete pieces of real
implementation were missing, and one real, previously-hidden defect was
found that would have broken every fresh install and every upgrade outright.

### Exact gaps found

1. **Artifact integrity was never verified.** `build_camera_node_
   artifact.py` has always produced `SHA256SUMS` and per-file hashes in
   `manifest.json`'s own `wheel_contents`, but `install_camera_node.py`
   never read either before installing. A corrupted copy or a tampered
   artifact would install silently.
2. **The activation swap was destructive-first, staged-never.** The
   current build was retired to `.previous` *before* the candidate was
   even built, let alone verified. A failure during `python3 -m venv`,
   `pip install`, or (see finding 4, below) an import error left the
   device with either no working `venv/` at all, or a broken one -- fine
   while the already-loaded, still-running service process stayed up, but
   a landmine for the next restart, crash, or reboot.
3. **No automatic recovery.** If the newly-activated build failed its own
   post-update health check, the installer reported failure and stopped --
   even though the previous, known-good build was sitting right there as
   `.previous`, one `--rollback` away.
4. **A real, reproduced packaging defect in `build_camera_node_
   artifact.py` itself.** `NODE_FILES` (the fixed list of files
   `scripts/build_camera_node_artifact.py` packages into the wheel) had
   silently drifted behind `app.py`'s own real imports: Remote /
   Intermittent-WAN Transport Foundation v1 added `transport_client.py`,
   `transport_credential.py`, `transport_log.py`, `transport_spool.py`,
   `transport_worker.py`, and `atomic_io.py` to `src/mockingbird_node/`
   without updating this builder's file list -- the identical class of gap
   Camera Node Boot Identity + Autonomous Recovery v1 had already found
   and fixed once for `identity.py`/`selftest.py`/`watchdog.py`. Confirmed
   by direct reproduction, not inference:

   ```
   $ python -m mockingbird_node   # inside a real venv with only the pre-fix NODE_FILES installed
   Traceback (most recent call last):
     ...
     File ".../mockingbird_node/__main__.py", line 33, in main
       from .app import create_node_app
     File ".../mockingbird_node/app.py", line 32, in <module>
       from .transport_client import TRANSPORT_PROTOCOL_VERSION, TransportClient
   ModuleNotFoundError: No module named 'mockingbird_node.transport_client'
   ```

   **Every fresh install and every upgrade produced by the accepted
   builder was completely broken** -- the Node process could not even
   start. The existing `@pytest.mark.slow` real-process tests
   (`test_camera_node_real_process.py`) would have caught this, and did
   the moment they were re-run (2 of 3 failing, `Connection refused`), but
   had not been run since the regression was introduced by an unrelated
   milestone. This is a bounded, reproduced upgrade-path defect squarely
   within this milestone's own scope to fix (see the milestone brief's own
   "do not reopen accepted work unless a reproduced defect requires a
   bounded fix").
5. **No wire-protocol compatibility reporting anywhere in the upgrade
   path.** `manifest.json` never recorded a candidate's own
   `node_api_version`/`transport_protocol_version`, so nothing could
   compare a candidate against what was currently installed.
6. **No dry-run/preflight.** There was no way to inspect what an upgrade
   would do without actually running it.

## 3. Upgrade contract

Extends `scripts/install_camera_node.py` (the established installer) --
there is no separate updater tool. `install()` is exactly the same
invocation an operator already uses for a first install; running it again
against a newer artifact directory *is* the upgrade.

### Preflight

`run_preflight(artifact_dir, paths)` -- every check is a pure read, no
privileged system command, so it never needs root and is exactly what
`--preflight` calls read-only. `install()` calls the identical function as
its own first gate, before touching prerequisites, the service account, or
the venv:

- candidate `manifest.json` present and parses as a JSON object (not merely
  "valid JSON" -- a `null`/list/string top level is reported as a failed
  check, never crashes the check itself);
- candidate `SHA256SUMS` checksums verified against the actual file bytes
  (`verify_artifact_checksums`) -- skipped, reported as
  `"skipped: already installed"`, when the candidate's `build_id` already
  matches what is installed, since nothing will be staged or mutated
  either way;
- currently-installed `manifest.json` (if any) readable;
- wire-protocol compatibility classification (see "Compatibility," below)
  -- informational, never blocking on its own;
- free disk space (`shutil.disk_usage`, injectable for tests) -- skipped
  when the candidate is already installed (nothing will be staged);
- `node.env`/`pairing.json` readability -- also informational, never
  blocking: neither is read or depended on by the upgrade mechanics (both
  are only ever preserved untouched), so a pre-existing, unrelated
  corruption in either must never refuse an otherwise-good candidate the
  operator may specifically be trying to install to recover the device.

Only the candidate's own well-formedness/checksums block `install()`
before a single mutation -- confirmed by a real end-to-end CLI run against
a tampered artifact (see "Real acceptance") and by `test_install_refuses_
a_tampered_artifact_before_touching_anything`.

### Preserve

Unchanged from the already-accepted design: `node.env` and the pairing
state directory are never touched by `install_or_update_venv`, `install()`,
or `rollback()` -- confirmed by existing and new regression tests
(`test_install_never_overwrites_existing_operator_config_or_pairing_
state`, `test_rollback_never_touches_config_or_state`, and every new
staged-activation test's own assertion that `node.env`'s content is
byte-identical before/after).

### Stage

`install_or_update_venv` now builds the candidate at a separate
`venv.staging`/`manifest.json.staging` and verifies it -- `import
mockingbird_node.app` inside that staged venv's own Python, the exact,
cheapest possible check that would have caught finding 4 above at install
time, on every device, forever -- *before* the live `venv`/`.previous` are
touched at all. If venv creation, `pip install`, or that import check
fails, the staged directory is discarded and the currently-installed build
is completely untouched.

### Activate

The manifest is promoted **first** (a small, now-atomic file write via the
existing `atomic_write_text` helper -- not a plain `shutil.copy2`, a real
finding from this milestone's own adversarial review, see below), then the
venv **second** (two directory renames, each individually atomic at the OS
level). This ordering is deliberate: it makes "does the live manifest
already name the staged candidate" a single fact that pins down exactly
which of three states applies after any interruption, regardless of which
individual step a crash landed on -- see `_recover_staged_activation`'s
own docstring for the full three-state accounting, and "Failure testing,"
below, for how an interim (ordering-reversed) design was caught missing a
real crash window during review. Exactly one systemd unit is ever running
at a time (`systemctl restart` is a single, sequential stop-then-start
from systemd's own perspective) -- never two services racing for the
camera.

### Verify

After activation and restart, `install()` re-probes `/node/v1/health` and
checks, all through the existing injectable `HealthChecker` seam (extended
from a `(bool, str)` pair to `(bool, str, payload)` so every existing
verification fact is available, not just "did it answer"):

- the service answers at all;
- `node_id` matches what was running immediately before the upgrade began
  (captured as a snapshot before any mutation) -- an unexpected mismatch
  raises distinctly and is **never** auto-"fixed" by rolling back (see
  "Do not confuse upgrade with replacement," below);
- `service_version`/`self_test`/`pairing_required`/
  `available_camera_count` are surfaced in the report's own step log.

### Recovery

If the newly-activated build fails this verification and a `.previous`
build exists (never on a first-ever install, where nothing exists to
restore to), `install()` automatically invokes the existing `rollback()`
to restore the prior known-good build, re-verifies it, and reports the
outcome honestly via a new `InstallReport.rolled_back` field --
`healthy=True, rolled_back=True` means "the service is fine, but running
the build you had before, not the one you asked for," a distinct outcome
from an ordinary successful upgrade, never collapsed into the same
boolean. If the automatic rollback's own re-verification *also* fails, the
installer fails visibly with a message that distinguishes a likely
hardware/environment problem from a bad artifact, and points at `--status`
and the service journal -- never a false claim of recovery.

## 4. Compatibility

A small `NodeUpgradeCompatibility` classification
(`current`/`compatible_older`/`incompatible`/`unknown`), styled after the
existing `mockingbird.observation.provider_compatibility` `Literal` +
label-dict convention already used elsewhere in this codebase for a
similar "how much can you trust this" question.

**Investigation answers (brief §6, Q12-14):**

- **Q12 (what Host-visible Camera Node version/capability information
  already exists):** `camera_node_service_version` (a per-Source durable
  fact, populated from live analysis-stream frame headers, surfaced on
  `GET /api/product/health` and Doctor) -- **display-only**, no
  compatibility floor, a deliberate, already-accepted decision (Release
  Engineering Foundation v1). Separately, `NODE_API_VERSION`/
  `TRANSPORT_PROTOCOL_VERSION` are hard-gated at pairing time
  (`mockingbird.source_providers.camera_node`) and transport-handshake time
  (`mockingbird.api.camera_node_transport`) respectively -- exact string
  equality, reject on mismatch.
- **Q13 (does the Host distinguish compatible/older-supported/newer-
  unknown/incompatible/unavailable):** No. Today's real gate is binary:
  exact match is accepted, anything else is rejected outright, at the
  moment of pairing/transport handshake. There is no "older but still
  accepted" tier. This is confirmed, not assumed, by reading the actual
  gate code, and it is an already-accepted, deliberate pre-1.0 choice (see
  "Host <-> Camera Node compatibility behavior" in
  [release-engineering-foundation-v1-report.md](release-engineering-foundation-v1-report.md)):
  "a deliberate and still-reasonable choice given no real version-skew
  failure mode exists in evidence for this pre-1.0 product." This
  milestone does not reopen or change that gate.
- **Q14 (can the Host safely operate against an older Node during staged
  rollout):** Yes, today, but only because `NODE_API_VERSION`/
  `TRANSPORT_PROTOCOL_VERSION` have never actually changed across this
  project's history (`"v1"`/`"transport/v1"` since the Node's very first
  commit) -- not because of any graduated-compatibility mechanism. Any
  future wire-protocol bump would immediately reject an unmatched Node/
  Host pair, by design.

**What this milestone adds:** `manifest.json` now records a candidate
artifact's own `protocol: {node_api_version, transport_protocol_version}`
(extracted from already-read source bytes via a plain literal-pattern
match -- never an import, keeping the builder stdlib-only).
`classify_node_upgrade_compatibility` compares a candidate's declared
protocol against the currently-installed build's -- a **Node-local, static
self-comparison only**: the installer has no configured Host address or
credential to call, so it can never determine live compatibility with
whatever specific Host this Node happens to be paired with. `current` means
the candidate carries the identical wire protocol as what is already
installed (safe, by definition, since nothing about wire compatibility is
changing); `incompatible` means it differs, which -- given the Host's real
exact-match gate -- would strand a Host that has not also been upgraded;
`unknown` means one side's protocol provenance is unavailable (most
commonly, the currently-installed build predates this milestone's
manifest field) and is never guessed as "current." `compatible_older` is
included in the vocabulary but documented as unreachable today, since
there is no such tier in the Host's own real gate -- a vocabulary slot for
if that gate is ever deliberately loosened, not a fabricated distinction.

This is reported, never blocking on its own: the Host's own real gate is
what actually enforces compatibility; the installer's job is to make an
operator aware of a wire-protocol change *before* they commit to it, which
`--preflight` and every `install()`/`--status` run now do.

## 5. Failure testing

Deterministic hermetic tests (`FakeCommandRunner`, `tmp_path`-rooted
`InstallPaths`, no real system touched) for every interruption point named
in the governing brief:

1. **Before service stop** (a blocking preflight failure -- a tampered
   checksum): `test_install_refuses_a_tampered_artifact_before_touching_
   anything` -- zero system commands issued, no `node.env` written.
2. **After staging but before activation:** `test_failed_staged_pip_
   install_leaves_the_running_install_untouched`, `test_failed_staged_
   import_check_leaves_the_running_install_untouched`, `test_stale_
   staging_from_an_interrupted_attempt_is_discarded_and_rebuilt` --
   the running install is byte-identical before/after in every case; a
   partially-built staging directory is discarded and rebuilt fresh on
   retry, never reused.
3. **After replacement but before restart / mid-activation:** two tests,
   covering both halves of activation's now manifest-first ordering --
   `test_interrupted_mid_activation_before_venv_promotion_is_completed_
   on_the_next_run` (manifest already promoted, venv rename not yet run)
   and `test_interrupted_mid_activation_after_venv_promotion_is_
   reconciled_on_the_next_run` (both promotions completed; only the
   now-redundant staging marker's cleanup never ran). Both confirm the
   next invocation reconciles to a fully consistent state (manifest and
   venv agree on the same build) without redoing already-verified work.
4. **Restart succeeds but health verification fails:**
   `test_failed_health_after_upgrade_triggers_automatic_rollback` (the
   prior build is restored and re-verified healthy) and `test_failed_
   health_after_upgrade_with_rollback_also_failing_is_visible_not_silent`
   (both the new and the restored build are unhealthy -- reported as a
   likely hardware/environment problem, never silently swallowed).
5. **First-ever install failing verification:** `test_failed_health_on_
   first_install_does_not_attempt_rollback` -- there is nothing to restore
   to; fails visibly, does not pretend to recover.

Additional, brief-required coverage: `test_unexpected_node_id_change_
during_upgrade_raises_clearly` (never auto-rolled-back); a full
`classify_node_upgrade_compatibility`/`node_upgrade_compatibility_label`
suite; `test_preflight_blocks_when_disk_space_is_insufficient`/
`..._is_skipped_for_an_already_up_to_date_build`; `test_rollback_refuses_
clearly_when_a_previous_rollback_attempt_was_interrupted` (a leftover
`*.rollback-swap` from an interrupted manual rollback fails with a clear,
disclosed message rather than a raw `OSError` from a colliding rename);
`test_status_surfaces_an_interrupted_upgrade_leftover`; `test_preflight_
report_never_contains_a_credential_or_pairing_digest`.

### Found and fixed by this milestone's own adversarial self-review

Before real-hardware acceptance, this implementation was put through a
5-angle adversarial review (correctness x3, reuse/simplification/
efficiency, altitude/conventions) against its own diff. Four independent
reviewers converged on the same two highest-severity findings, both fixed
before proceeding, not merely disclosed:

- **The original two-state activation-recovery design (keyed solely on
  whether `venv.staging` still existed) missed a real crash window.**
  Activating venv-first meant a crash immediately after the venv rename
  succeeded -- before the manifest was updated -- left `venv.staging`
  already gone, so nothing detected that the manifest still needed
  updating; a subsequent retry could `rmtree` the genuinely-good prior
  build while believing it was doing an ordinary upgrade. Fixed by
  reordering activation to manifest-first (see "Activate," above) and
  replacing the two-state check with `_recover_staged_activation`'s
  three-state, build-id-based reconciliation -- proven by two new tests
  covering both halves of the corrected ordering (see item 3, above).
- **A plain, successful, explicitly-requested `--rollback` was
  incorrectly reported as a failed upgrade.** `rollback()`'s
  `InstallReport.rolled_back` is `True` for *both* a direct `--rollback`
  and `install()`'s own automatic recovery, but `main()`'s original
  warning/exit-1 logic could not distinguish the two -- a deliberate,
  successful rollback printed a false "the requested build did not pass
  verification" note and exited 1. Fixed: `main()` now only treats
  `rolled_back` as a surprising outcome when it came from `install()`, not
  from a directly-requested `--rollback` -- proven by
  `test_main_direct_rollback_success_exits_cleanly_with_no_false_
  recovery_note` and a companion test guarding that the *legitimate*
  warning case (an upgrade's own automatic recovery) still fires.

Five further, lower-severity correctness gaps were found and fixed the
same pass: `status()` could crash with `KeyError` on a manifest whose
`protocol` object was missing a key (now uses `.get(...)`, and the whole
block treats a non-object `manifest.json` as a reported error rather than
an `AttributeError`); `verify_artifact_checksums`/`run_preflight` could
raise a raw `UnicodeDecodeError`/`OSError` instead of a clean
`InstallerError` on a genuinely corrupted `SHA256SUMS` or an unreadable
listed file; `_read_json_if_present` now validates the parsed value is
actually a JSON object, closing the same "non-dict crashes `.get(...)`"
class of gap everywhere it is used; `configuration_readable`/
`pairing_state_readable` were incorrectly folded into preflight's blocking
gate -- an unrelated, pre-existing corrupted `node.env`/`pairing.json`
(never read or depended on by the upgrade itself) could refuse an
otherwise-good candidate; both are now reported, never blocking. One
reuse/efficiency finding was also fixed: the final manifest-activation
write now goes through the existing `atomic_write_text` helper instead of
a plain `shutil.copy2` (the one non-atomic step in an otherwise
atomic-rename design), and checksum verification is skipped -- reported as
`"skipped: already installed"` -- when the candidate's `build_id` already
matches what is installed, since nothing will be staged or mutated either
way.

**Scope decision, disclosed:** `rollback()`'s own directory swap (`venv`
<-> `venv.previous` via a `venv.rollback-swap` temporary name) was given
the same manifest-first *ordering* as the fix above (a real, if narrower,
improvement -- see "Activate"), but not the full build-id-based
reconciliation state machine `_recover_staged_activation` provides for the
forward upgrade path. Section 10 of the governing brief scopes
"interrupted update behavior" to the forward upgrade path; a
manually-invoked `--rollback` being *itself* interrupted mid-swap is a
narrower, already-fallback operation, and both `venv`/`venv.previous` here
are already-existing, already-known-good directories (unlike staging's
build-then-verify window, there is no long-running work to interrupt --
only a handful of sequential renames). A residual gap remains: a crash
landing exactly between the venv swap completing and the manifest swap
starting leaves no `*.rollback-swap` leftover for the existing guard to
detect, so a subsequent attempt could proceed on a manifest that
transiently disagrees with the live venv. This is a disclosed, bounded
gap, not a silent one -- see "Remaining limitations."

## 6. Real acceptance

_(completed after implementation; see below)_

## 7. Validation

_(completed after implementation; see below)_

## 8. Remaining limitations

_(completed after implementation; see below)_

## 9. Decision

_(completed after implementation; see below)_
