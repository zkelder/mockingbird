# Camera Node Installer / Service / Reboot Hardening v1

**Roadmap phase:** 1 -- Trustworthy Single-Site Observatory. The current exit
gate ("one representative installation can run for days and create
trustworthy useful history without developer babysitting") explicitly
requires proving "sustained operation, restart/recovery, [and] truthful
health/capability reporting" for "the real Camera Node path" (see
[roadmap.md](roadmap.md)). Before this milestone that path was provable only
by a developer manually SSHing into a Pi and hand-running `python -m
mockingbird_node` (or, in practice on the one real reference device, a
hand-built, unreviewed `systemd` unit assembled ad hoc across several field
sessions -- see "Relationship to the real reference device," below). This
milestone is that proof: a reproducible install/service/reboot/crash path a
non-developer operator could actually follow, on the exact hardware and OS
already validated as this project's Camera Node reference platform.

**Product flow improved:** none of the reviewed product loop (Stream ->
Zone -> Observation -> Review Queue -> correction -> Bird Log) changes. This
milestone hardens the infrastructure *underneath* one Stream type -- a paired
Camera Node staying reachable across reboots, crashes, and ordinary network
hiccups without an operator's attention or a lost pairing -- so that loop can
actually run unattended for days, which is the Phase 1 exit condition itself.

**Why this is next:** the "Camera Node Productization Reconnaissance" that
preceded this milestone (read-only, no files changed) confirmed the Camera
Node package, pairing security, and hardware-agnostic provider architecture
are already sound, but found zero install/service/OS-supervision path: no
systemd unit, no documented OS prerequisites, no boot/crash-recovery proof,
no update/rollback procedure, and no test that runs the Node as a real OS
process reachable over a real socket. That gap is exactly what stands
between "the real Camera Node path is architecturally correct" (already
true) and "a representative installation can run for days without developer
babysitting" (the actual Phase 1 exit condition).

## Phase ownership (resolving a documentation ambiguity)

[roadmap.md](roadmap.md) Phase 4 ("Install / Recovery / Appliance
Experience") also talks about "package/installer... automatic services...
golden-path setup," which could be misread as owning this work. It does not.
Phase 4's entire existing scope, as delivered by Phase 27A and documented in
[local-product-packaging-design.md](local-product-packaging-design.md), is
the **MockingBird host** application's own packaging/first-run/upgrade
experience (currently: a self-contained Windows "unpack and run" bundle).
That document explicitly *rejects* a systemd unit or Windows service for the
host, on product-identity grounds: MockingBird-the-host is local desktop
software a user unpacks and double-clicks, not an appliance daemon.

The Camera Node is a different component on different hardware with a
different product identity: a headless edge device that has no desktop
session to double-click anything in and is expected to run unattended,
indefinitely, surviving reboots -- an appliance in exactly the sense the host
is not. Proving that is what "the real Camera Node path" already named as
unfinished Phase 1 work, not a new appliance-packaging initiative. This
milestone is therefore **Phase 1** work: it finishes proving the real Camera
Node path is durable infrastructure, the same way Session-Renewal Continuity
v1 and the Capture Contention fix were. Phase 4 is updated with a one-line
cross-reference so a future reader does not need to rediscover this
distinction; see "Documentation updates," below.

## Scope boundary

This document is the installer/service/OS-supervision contract layered
*underneath* the existing Node. It does not modify, and must not be read as
superseding, [camera-node-boundary-design.md](camera-node-boundary-design.md)
(the Node's product/API/security boundary) or
[camera-node-pairing-persistence-design.md](camera-node-pairing-persistence-design.md)
(the host-side durable pairing-credential contract). Those remain the
authority for what the Node is allowed to do; this document is the authority
for how the Node's own process gets installed, supervised, configured, and
diagnosed on its host OS.

## Supported reference OS/hardware

Established empirically against the project's real reference device (see
"Relationship to the real reference device," below), not guessed from
desktop/CI package names:

- **Hardware:** Raspberry Pi 4 Model B (Rev 1.5), the project's existing
  reference device. Pi 4 remains the validated reference; this installer
  targets the underlying OS/Python contract, not Pi-4-specific behavior, so
  it is not architecturally pinned to it (see "Non-goals").
- **OS:** Raspberry Pi OS (`pi-gen`-built), currently tracking Debian 13
  ("trixie"), `aarch64`. `/etc/rpi-issue` and `/proc/device-tree/model` are
  the authoritative on-device identity facts (see "Diagnostics," below, for
  how the installer surfaces them). Camera Node has no OS-specific code
  itself (see [camera-node-boundary-design.md](camera-node-boundary-design.md));
  this installer's OS dependency is entirely in *this document's* prerequisite
  list, not in `src/mockingbird_node/`.
- **Python:** system `python3` (3.13 on the reference device), via a virtual
  environment (see "System prerequisites," below) -- never the system
  interpreter's own site-packages directly.
- A generic Debian-family Linux device without a Pi camera still installs
  and runs correctly: it gets an honest `setup_required` PiCamera2 provider
  state and, if `python3-opencv` is unavailable, the same for V4L2 -- this
  installer never fails the whole install over an optional provider
  dependency (see "System prerequisites").

## Relationship to the real reference device

The real Pi 4 this milestone validates against was **not** a fresh device:
it already had an ad hoc, hand-assembled `systemd` unit
(`/etc/systemd/system/mockingbird-camera-node.service`, running as the
interactive login user, working directory `~/mockingbird-camera-node/`),
built up by hand across several earlier field-acceptance sessions because
those sessions needed the Node to survive a terminal disconnect. It has been
paired with the real host and serving real captures continuously since
2026-08-16. That ad hoc unit is exactly the shape of undocumented,
unreviewed, `root`-adjacent, per-developer process this milestone replaces
with a reviewed, reproducible, minimally-privileged one -- and its multi-day
uptime is itself useful evidence: `Restart=on-failure`/`RestartSec=5` and
plain group-based `/dev/video*` access were already proven sufficient in
practice before this milestone tightened them further (dedicated service
user, `ProtectSystem=strict`, bounded restart-storm limits -- see "systemd
unit," below). The installer adopts this device in place rather than
requiring a re-flash; because the ad hoc install used entirely different
paths and a different service identity, adoption could not inherit its
pairing file directly and required one fresh pairing -- see "Real hardware
acceptance findings," below, for exactly what that looked like in
practice.

## Artifact/install contract

`scripts/build_camera_node_artifact.py` (existing, hardened by this
milestone -- see "Reproducibility hardening," below) produces:

- `mockingbird_camera_node-<version>-py3-none-any.whl` -- the slim package
  (`mockingbird_node/{__init__,__main__,app,config,identity,providers,
  selftest,watchdog}.py` only -- `identity.py`/`selftest.py`/`watchdog.py`
  added by Boot Identity + Autonomous Recovery v1, see below; no
  `mockingbird`, `web`, `tests`, or `data` paths; no SQLAlchemy or any main-app
  dependency -- enforced by the existing `test_camera_node_artifact_is_slim_and_launcher_checks_without_starting`).
- `requirements.txt` -- the Node's own runtime dependencies
  (`fastapi`/`pydantic`/`uvicorn[standard]`), independent of the main app's
  `pyproject.toml`. Boot identity/self-test/watchdog add no new dependency:
  `identity.py` reads `/proc` and `importlib.metadata`; `watchdog.py` speaks
  the `sd_notify` Unix-datagram-socket protocol directly, both standard
  library only.
- `camera-node.env.example` -- a starting configuration.
- `manifest.json` -- artifact identity, now including verifiable source
  provenance (see below).
- `SHA256SUMS` -- checksums of all of the above.

This seven/eight-file directory *is* "a versioned Camera Node artifact" in the
target install flow ("obtain artifact -> install dependencies -> configure
-> install/enable service"). It is produced on a developer/CI machine (this
build needs nothing beyond Python's standard library) and copied onto the
Node device by the operator through any transport they already trust (`scp`,
a USB drive, a shared network folder) -- never fetched or executed by a
remote command from the host; see "Security boundary."

### Reproducibility hardening

The existing builder accepted an arbitrary, unverified `--source-state`
string -- nothing checked it matched the actual files being packaged, and a
dirty working tree could silently produce an artifact whose `manifest.json`
claimed a clean commit it did not really come from. This milestone adds,
mirroring the equivalent, already-accepted pattern in
`scripts/build_local_product.py`
(`verify_clean_tracked_source`/`export_clean_source_tree` -- see
[windows-dev-deployment-design.md](windows-dev-deployment-design.md)) at a
scope proportionate to this builder's actual attack surface:

- `verify_clean_camera_node_source()` runs `git diff --name-only HEAD --
  src/mockingbird_node` and refuses the build (raising
  `CameraNodeArtifactError`) if that specific path has uncommitted
  modifications, then returns the resolved `git rev-parse HEAD`. Scoped to
  `src/mockingbird_node/` only -- not the whole repository -- because that is
  the builder's entire input surface and forcing an unrelated dirty tree
  elsewhere in the repository to block a Camera Node build would be
  disproportionate.
- Unlike `build_local_product.py`, this builder never needs a `git archive`
  clean-tree *export*: it already reads its five source files by fixed name
  (`NODE_FILES`), never by directory glob, so an untracked stray file
  physically present under `src/mockingbird_node/` was already structurally
  unable to enter the wheel. Only the narrower "uncommitted edit to an
  already-tracked file" ambiguity needed closing.
- `source_state` is now derived automatically (`git:<full-commit-hash>` on a
  clean tree) rather than defaulting to the meaningless `"unspecified"`;
  `--source-state` remains available as an explicit override (a
  non-git-checkout build, or deliberate re-labeling), and `--allow-dirty-source`
  (mirroring the same flag on `build_local_product.py`) opts out of the clean
  check for local iteration only, recording `"dirty:unverified-working-tree"`
  instead of a hash it cannot prove.
- `manifest.json` gains a `provenance` object alongside the existing
  human-readable `source_state` string: `{"git_commit": <hash-or-null>,
  "source_clean": <bool>, "build_id": <random-per-build-token>, "built_at":
  <ISO-8601 UTC>}`. `build_id` mirrors `BuildIdentity.build_id` in
  `build_local_product.py` -- a fresh random token per *build invocation*, so
  two independent builds of the identical commit are still distinguishable
  (the installer's update/idempotency logic depends on this; see below).

This closes the actual gap ("must make it possible to determine exactly what
source commit produced it") without introducing `build_local_product.py`'s
heavier `git archive`-to-tempdir machinery, which this builder's narrower,
fixed-file-list read pattern never needed in the first place.

## System prerequisites

Determined empirically on the real reference device (`apt-cache
policy`/`dpkg -l`/a live `pip list` inside the already-working ad hoc venv --
never guessed from desktop or CI package names), and confirmed against the
actual open file descriptors of a real, multi-day-running Camera Node
process (see "Service identity and device access," below):

| Package | Why | Optional? |
| --- | --- | --- |
| `python3-venv` | `python3 -m venv` plus its bundled `ensurepip`, so the venv gets its own local `pip` regardless of whether system `python3-pip` is installed (it is not, on the reference device -- see below) | No |
| `python3-picamera2` | PiCamera2 provider; pulls in `python3-libcamera` automatically as an apt dependency | Yes -- degrades that provider to `setup_required` |
| `python3-opencv` | V4L2 provider's OpenCV-backed capture | Yes -- degrades that provider to `setup_required` |

**The externally-managed-Python / PiCamera2 / venv interaction, established
concretely:** Raspberry Pi OS trixie marks the system interpreter
externally-managed (`/usr/lib/python3.13/EXTERNALLY-MANAGED` is present, per
PEP 668) and does not install `python3-pip` at all by default (`apt-cache
policy python3-pip` shows `Installed: (none)` on the reference device even
though PiCamera2 and a fully working venv are both present and have been
serving real traffic for weeks). Neither fact blocks this installer:
`python3 -m venv` does not need system `pip` -- it bootstraps its own,
independent copy via the standard library's `ensurepip`, which is what
`python3-venv` actually ships. **PiCamera2 and `libcamera` have no
general-purpose PyPI wheel for this platform** (they wrap a compiled,
Pi-specific `libcamera` build via apt, not a redistributable Python
package), so the *only* way to make them importable inside an isolated venv
is `python3 -m venv --system-site-packages` -- confirmed directly: the real
reference venv was created exactly this way
(`pyvenv.cfg`: `include-system-site-packages = true`), and `import
picamera2` / `import cv2` both succeed inside it while `fastapi`/`uvicorn`/
`pydantic` are separately `pip`-installed into that same venv on top,
unaffected by the system-site inheritance. This installer therefore always
creates the venv with `--system-site-packages`; on a non-Pi Debian host with
neither optional apt package installed, this is a harmless no-op (both
providers simply report `setup_required`, exactly as already designed --
see [camera-node-boundary-design.md](camera-node-boundary-design.md)'s
"missing... reports **Setup required**").

The installer attempts each optional apt package individually and reports
per-package success/failure without aborting the install if one is
unavailable (a non-Pi Debian box's package index legitimately does not carry
`python3-picamera2` at all) -- "a missing optional provider must not break
the entire Camera Node install." `python3-venv`, by contrast, is not
optional: without it there is no working install, and the installer fails
clearly rather than half-installing.

## Service identity and device access

**Established by direct inspection of the real, currently-running Camera
Node process's open file descriptors** (`/proc/<pid>/fd`), not inferred from
which groups its ad hoc account happened to already belong to. Every device
file it had open -- `/dev/video*`, `/dev/media*`, `/dev/v4l-subdev*`, and
`/dev/dma_heap/*` (PiCamera2's zero-copy buffer allocation path) -- is
`root:video`, mode `660`. None of `gpio`, `render`, `i2c`, `spi`, `dialout`,
or `plugdev` (all present in the ad hoc account's actual group list, none
ever touched) are load-bearing for camera capture.

The installer therefore creates one dedicated system account,
`mockingbird-node` (`useradd --system --no-create-home --shell
/usr/sbin/nologin`, own primary group of the same name), with exactly one
supplementary group: `video`. It owns nothing outside its state directory
(see "State paths," below); it cannot log in interactively; it has no
access to any other operator's files, GPIO, I2C/SPI buses, or serial
devices. This is a strictly narrower grant than the ad hoc install it
replaces, empirically proven sufficient rather than assumed.

## Configuration paths

`/etc/mockingbird-camera-node/node.env` -- an `EnvironmentFile=`-format file
(`KEY=value` per line, no quoting/expansion), `root:root`, mode `0600`. This
preserves the existing, already-validated `CameraNodeConfig.from_environment()`
environment-variable model unchanged (see
[camera-node-boundary-design.md](camera-node-boundary-design.md)) rather than
inventing a second configuration format; `EnvironmentFile=` is systemd's own
native bridge from a flat env file to a managed unit's process environment,
so no new parser is written.

It is deliberately **not** readable by the `mockingbird-node` service
account itself: `systemd` (running as PID 1/root) reads `EnvironmentFile=`
and sets the child process's environment before dropping privileges to
`User=`, so the file only ever needs to be readable by the process that
starts the service, never by the service itself. `node.env` carries no
secret today (the pairing *credential* is never written here -- only a
SHA-256 digest of it persists at all, in the state directory below, per the
existing `_PairingState._persist_state` design) but this ownership is a
deliberate, low-cost, defense-in-depth default that degrades gracefully if a
future field ever does carry something sensitive, not a claim that a secret
lives here today.

The installer writes this file **once**, from `camera-node.env.example`,
**only if it does not already exist**. A re-run (update, idempotent re-install)
never touches an existing `node.env` -- "an update must not overwrite
existing operator configuration" -- including on the reference device's own
adoption, whose existing hand-edited `node.env` (raised `MAX_IMAGE_*` bounds
for a higher-resolution monitoring profile than the packaged example ships)
survives untouched.

### Bind address / trust boundary

The shipped example sets `MOCKINGBIRD_NODE_BIND=0.0.0.0` (unchanged from the
existing convention already in `camera-node.env.example` and
`_configuration_example()`) because a Node bound to loopback-only cannot
serve its one purpose -- being reached by a MockingBird host elsewhere on the
LAN. This is an explicit, documented trust decision, not a default chosen
because it merely "sounds more restrictive": **every device on the local
network can attempt the one-time pairing exchange while a pairing code is
outstanding, and once paired, any device on the local network holding the
resulting bearer credential can reach the Node's authenticated endpoints**,
because the transport is plain HTTP with no TLS (see "Security boundary,"
below, and
[camera-node-boundary-design.md](camera-node-boundary-design.md)'s existing
pairing/network boundary, which this does not change). An operator on an
untrusted or shared LAN should set `MOCKINGBIRD_NODE_BIND=127.0.0.1` in
`node.env` and reach the Node only through an SSH tunnel or equivalent; the
installer does not choose this for them because it cannot know their network
trust model, and a silently loopback-bound Node would just look broken
instead of failing safely.

## State paths

`StateDirectory=mockingbird-camera-node` in the systemd unit -- resolved by
systemd itself to `/var/lib/mockingbird-camera-node/`, created and
`chown`-ed to `mockingbird-node:mockingbird-node` (mode `0750`)
automatically before every start, including under `ProtectSystem=strict`
(see "systemd unit," below). `MOCKINGBIRD_NODE_PAIRING_STATE_PATH` is set
explicitly in `node.env` to
`/var/lib/mockingbird-camera-node/pairing.json` rather than relying on the
application's own `XDG_STATE_HOME`/`$HOME`-derived default (a system service
account's `$HOME` is not a meaningful concept the way an interactive user's
is) -- an explicit, predictable, documented path rather than an inherited
guess. This is the one file that must survive every update, restart, crash,
and reboot: it holds only a SHA-256 digest of the paired credential (never
the credential itself -- see `_PairingState._persist_state` in
`src/mockingbird_node/app.py`), written atomically
(`os.O_EXCL` + `os.replace`) by the existing, unmodified pairing code. This
milestone changes nothing about that persistence mechanism; it only gives it
a stable, correctly-owned home.

## Logging behavior

`journald`, not a custom log file/rotation subsystem -- `Type=simple`'s
stdout/stderr already land in the unit's journal automatically; no
`StandardOutput=`/`StandardError=` override is needed. Concretely inspected
against the real reference device's own journal: `libcamera`'s native C++
logger writes its own INFO/WARN lines directly regardless of the Node's own
log level, and the existing unconditional `print(...,
file=sys.stderr)` for the pairing code and its expiry (see `__main__.py`)
already appear correctly. One real gap this milestone closes: uvicorn's
*own* default startup confirmation (`Uvicorn running on http://...`,
`Application startup complete`) is silenced by the Node's existing hardcoded
`log_level="warning"` (verified directly: those lines are genuinely absent
from the real reference device's journal around its last several restarts),
which would leave an operator with no journal evidence the service actually
finished starting short of a manual health probe. Two small, evidence-driven
fixes (see "Diagnostics implementation," below):

1. A new `@app.on_event("startup")` handler in `create_node_app` prints one
   deterministic, log-level-independent line summarizing exactly what the
   required-implementation list asks an operator to be able to determine:
   bind/port, which providers are configured, whether pairing state was
   already loaded (never the credential or its digest), and listening
   confirmation.
2. `MOCKINGBIRD_NODE_LOG_LEVEL` (new, optional; default `warning`, matching
   today's unchanged behavior) lets an operator raise uvicorn's own
   verbosity (e.g. to `info` for per-request access logs) while
   diagnosing, without changing the conservative default every other
   deployment keeps.

A configuration-load failure (`CameraNodeConfig.from_environment()` raising
`ValueError`) is now caught in `__main__.main()` and printed as one clear
`Camera Node configuration error: <field>_invalid` line before a clean
non-zero exit, instead of a raw Python traceback -- `systemctl status` and
`journalctl -u mockingbird-camera-node` both surface this immediately as
"why startup failed." No credential, digest, or bearer token is ever part of
any of these lines; only the pairing *code* (already deliberately local and
short-lived) is printed, unchanged from today.

## Update behavior

A "versioned Camera Node artifact" is, concretely, one output directory of
`build_camera_node_artifact.py`, identified by `manifest.json`'s
`provenance.build_id`. Re-running the installer against a newer artifact
directory:

1. Compares the new artifact's `build_id` against the currently-installed
   one (`/opt/mockingbird-camera-node/manifest.json`, placed there by the
   previous install/update).
2. If unchanged, the update is a no-op beyond ensuring the service is
   enabled/running (safe to re-run with the exact same artifact repeatedly).
3. If changed, the *current* `venv/` and `manifest.json` are renamed to
   `venv.previous/`/`manifest.json.previous` (replacing any older
   `.previous`, so exactly one prior version is retained -- see "Rollback"),
   a fresh venv is built from the new artifact, the service is restarted,
   and a bounded local health check confirms the new process actually
   answers `GET /node/v1/health`.

`node.env` and the state directory are never touched by an update -- only
`/opt/mockingbird-camera-node/{venv,manifest.json}` are replaced. This is
deliberately not a multi-release ledger like
`scripts/deploy_windows_dev.py`'s (`--keep N`, an append-only deployment
log): a single headless edge device with one operator does not need that;
"current plus exactly one prior version" is the smallest mechanism that
still gives a real rollback target, matching the installation's actual
(single-machine, single-operator) shape.

## Rollback

`--rollback` stops the service, swaps `venv`/`manifest.json` with
`venv.previous`/`manifest.json.previous`, restarts, and runs the same
bounded local health check as a normal install. It refuses clearly if no
`.previous` exists (nothing to roll back to) rather than silently doing
nothing. Because `node.env` and the state directory are never touched by an
update in the first place, a rollback never has to reconcile configuration
or pairing state -- it only ever swaps code.

## systemd unit

```ini
[Unit]
Description=MockingBird Camera Node
Documentation=https://github.com/anthropics/mockingbird/blob/main/docs/camera-node-install-guide.md
Wants=network-online.target
After=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=notify
NotifyAccess=main
User=mockingbird-node
Group=mockingbird-node
EnvironmentFile=/etc/mockingbird-camera-node/node.env
Environment=PYTHONDONTWRITEBYTECODE=1
StateDirectory=mockingbird-camera-node
WorkingDirectory=/var/lib/mockingbird-camera-node
ExecStart=/opt/mockingbird-camera-node/venv/bin/python -m mockingbird_node
Restart=on-failure
RestartSec=5
TimeoutStartSec=30
TimeoutStopSec=15
WatchdogSec=30
KillSignal=SIGTERM
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true

[Install]
WantedBy=multi-user.target
```

Design notes, most already justified above:

- **`StartLimitIntervalSec=300` / `StartLimitBurst=5`** (in `[Unit]` --
  the modern systemd location, confirmed against the reference device's own
  `systemd 257`): at most 5 restart attempts in any rolling 5-minute window,
  after which `systemd` marks the unit `failed` and stops trying on its own
  -- "do not create an infinite hot-restart failure loop," while
  `Restart=on-failure`/`RestartSec=5` (unchanged from the ad hoc unit this
  replaces, and already proven over real multi-day uptime) still recovers
  promptly from a genuine, isolated crash. A unit stuck in `failed` after
  exhausting this budget is exactly the "genuine, persistent" case an
  operator should see and act on (`systemctl status`/`journalctl`), not one
  bounded restart hiding it indefinitely.
- **`TimeoutStopSec=15`/`KillSignal=SIGTERM`**: `systemd` sends `SIGTERM`
  and waits up to 15s before escalating to `SIGKILL`. `uvicorn` already
  traps `SIGTERM` for graceful ASGI shutdown (running the existing
  `@app.on_event("shutdown")` handler, which calls `provider.close()` --
  releasing any open PiCamera2/V4L2 handle cleanly), so this is graceful
  termination without any new code. Confirmed directly (not assumed) while
  building the real-process smoke test: a real subprocess sent `SIGTERM`
  logs the complete `Shutting down` -> `Waiting for application shutdown.`
  -> `Application shutdown complete.` sequence and exits well within a
  couple of seconds -- but its OS-level exit status is *signal-terminated*
  (`-15`/143), never `0`. This is `uvicorn.Server.capture_signals`'s own
  documented, intentional behavior: it runs the full graceful sequence to
  completion, restores the original signal disposition, and only then
  re-raises the caught signal, so a process supervisor's exit-status
  accounting stays conventionally correct. `systemd` correlates this
  correctly with its own stop request (`systemctl stop`/`restart`, or a
  normal shutdown) and does not treat it as a `Restart=on-failure` trigger;
  see "Real hardware acceptance findings" for the on-device confirmation
  that a normal `systemctl restart` shows a clean `Result=success`, not a
  failure.
- **`ProtectSystem=strict`/`ProtectHome=true`/`PrivateTmp=true`/
  `NoNewPrivileges=true`**: the entire filesystem becomes read-only to the
  service except `StateDirectory=`'s own path (which `systemd` still grants
  write access to under `strict`, by design) and a private `/tmp`. This does
  not affect camera access (`/dev`, `/sys`, and `/usr/share/libcamera/...`
  configuration reads all remain unaffected -- `ProtectSystem` only removes
  *write* access to non-exempted paths) or any other observed behavior --
  verified directly on the reference device (see "Real hardware acceptance
  findings," below) rather than assumed safe from documentation alone.
  `PYTHONDONTWRITEBYTECODE=1` avoids a harmless-but-noisy repeated failed
  `.pyc`-write attempt against the now-read-only venv (the installer also
  precompiles once at install time via `compileall`, so this is a pure
  belt-and-suspenders default, not a behavior dependency).
- **No explicit `DeviceAllow=`.** systemd's device-cgroup controls could
  further scope exactly which device nodes this unit may open, but the
  camera device set is not fixed across boots (V4L2/media device numbers
  are enumerated dynamically) and the existing Unix permission bits already
  correctly gate access (`root:video`, `0660`, matched by this unit's own
  `video` supplementary group -- see "Service identity and device access").
  Duplicating that gate with a second, harder-to-verify device-cgroup
  allowlist would add real fragility (a firmware/kernel update that
  renumbers or adds a device class could silently break capture) for no
  additional access actually being denied. This is a deliberate choice, not
  an oversight.
- **`Type=notify`/`NotifyAccess=main`/`WatchdogSec=30`** (Boot Identity +
  Autonomous Recovery v1): closes a real gap `Restart=on-failure` alone
  cannot -- a *hung* process (the event loop wedged, never exits) never
  triggers `Restart=on-failure`, which only fires on process exit. Under
  `Type=notify`, `systemd` additionally requires `READY=1` within
  `TimeoutStartSec=30` (the Node sends it right after its bounded startup
  self-test runs -- see "Startup self-test," below) and, once
  `WatchdogSec=30` is set, a `WATCHDOG=1` ping at least every 15s or it
  restarts the unit exactly as if the process had crashed -- same bounded
  `RestartSec=5`/`StartLimitBurst=5` governs the respawn. See "Watchdog,"
  below, for what actually gates each ping (never a bare timer). This
  closes the "service hang" rung of the field-recovery ladder; an OS/kernel
  hang (where systemd itself cannot run either) is a different failure
  class -- see "Hardware watchdog," below.

## Boot identity

`/node/v1/health` gains additive fields (every pre-existing field is
unchanged, so an older host client parsing this response is unaffected):
`boot_id`, `os_uptime_seconds`, `service_uptime_seconds`,
`service_started_at`, `service_version`, `self_test`, `watchdog`. New
`src/mockingbird_node/identity.py`:

- `boot_id` reads `/proc/sys/kernel/random/boot_id` -- the kernel's own
  fresh random UUID every real boot, stable for the machine's entire
  uptime. `None` on any platform/permission/format problem; never
  fabricated from this process's PID or the wall clock. This is what lets
  the host tell "same node, same boot" apart from "same node, fresh
  reboot," and (via the bounded transition history below) "process restart"
  (same `boot_id`) apart from "machine reboot" (new `boot_id`).
- `os_uptime_seconds` reads `/proc/uptime`'s first field -- machine uptime,
  resets only on a real reboot, unaffected by this process's own restart.
  `service_uptime_seconds` is a separate, monotonic-clock-only measurement
  (`time.monotonic()` deltas, never wall-clock time) of how long *this
  process* has been running -- resets on both a process restart and a
  machine reboot. The two are deliberately never conflated.
- `service_version` resolves via `importlib.metadata.version(...)` against
  the real installed wheel's own `.dist-info` (present on every real
  installed Node); a development checkout that never installed the
  separate slim wheel falls back to `mockingbird_node.__version__`.
- The Node's `node_id` (pre-existing, unchanged) is already a stable
  identity distinct from the pairing credential: deterministic from
  `display_name`, so it survives reinstall/update as long as `node.env`'s
  `MOCKINGBIRD_NODE_NAME` is untouched -- which the installer already
  guarantees (`ensure_config_file` never overwrites an existing file). No
  change was needed here.

The per-part analysis-stream headers (`analysis_parts` in `app.py`) also
carry `X-MockingBird-Node-Boot-Id`/`X-MockingBird-Node-Service-Version` on
every frame, mirroring the existing per-part
`X-MockingBird-Provider-Generation`/`-Node-Session` duplication -- so a
currently-observing host learns the Node's boot identity from frames it is
already pulling, with zero extra requests (see "Host-side state," below).

## Startup self-test

New `src/mockingbird_node/selftest.py`, run once, synchronously, inside
`create_node_app` -- before the app is ever returned to `uvicorn`, so the
very first `/node/v1/health` response already carries the result. Checks,
each already fast by construction and additionally wrapped in a short
bounded timeout so a truly wedged driver call cannot hang the whole process
before it ever binds its listening socket:

- the configured provider(s) can enumerate cameras (`provider.cameras()` --
  enumeration only, never a full capture or warm-session);
- at least one camera reports `available`;
- the configured pairing-state directory is writable.

Status is `passed` or `degraded` -- **never `failed`**: the Node's own HTTP
surface (pairing, health, revocation) works regardless of camera state, so
no shape of camera trouble should ever look like the Node itself is broken
or push it toward a restart loop. Camera absence/permission problems
degrade with a bounded reason code (`no_camera_available`,
`provider_enumeration_timed_out`, `provider_enumeration_failed`,
`pairing_state_path_unwritable`), never block startup, and never crash-loop
the service.

## Watchdog

New `src/mockingbird_node/watchdog.py` -- a minimal, dependency-free
`sd_notify` client (the protocol is a handful of bytes written to a
`SOCK_DGRAM` Unix socket at the path in `$NOTIFY_SOCKET`; no
`sdnotify`/`systemd-python` package, keeping the artifact's runtime
requirements unchanged). Every function is a safe no-op off systemd (a
manual `python -m mockingbird_node` run, or any environment lacking
`NOTIFY_SOCKET`) -- never raises, never blocks.

- `READY=1` is sent once at startup, after the bounded self-test above has
  already run -- so "started," under `Type=notify`, genuinely means
  "self-test ran and the HTTP server is serving," not merely "the process
  exec'd."
- A long-lived `asyncio.Task` (started in a FastAPI startup handler,
  cancelled cleanly on shutdown) pings `WATCHDOG=1` on an interval derived
  from systemd's own `WATCHDOG_USEC` (half the configured `WatchdogSec`,
  systemd's own documented convention) -- but **only after a real, bounded
  liveness probe genuinely completes**: `provider.cameras()`, run off the
  event loop thread (`asyncio.to_thread`) with its own timeout shorter than
  the ping interval. If the probe hangs or fails, that cycle's ping is
  simply withheld; if it keeps hanging, `WatchdogSec` eventually elapses
  and `systemd` restarts the unit exactly as a crash would. This is the
  "meaningful progress" requirement stated in the milestone brief: the
  watchdog signal corresponds to real Camera Node responsiveness (the event
  loop scheduling a real off-thread call and getting an answer), never a
  bare timer thread that stays alive while the real work is dead. `service
  alive` (this) is deliberately a different fact from `camera producing
  frames` (which this milestone does not require merely to prove
  liveness).
- `/node/v1/health`'s `watchdog` object (`enabled`, `ping_interval_seconds`,
  `seconds_since_last_probe`, `last_probe_ok`, `consecutive_probe_failures`)
  exposes the watchdog's own evidence, not just "the process is still
  running" on faith.

This closes the **service hang** rung of the field-recovery ladder
(`docs/roadmap.md`'s "Camera Node field-recovery ladder"): `service hang ->
watchdog timeout -> service restart -> same boot_id` (the machine did not
reboot; only the process did). It does **not** close the **OS hang** rung --
see "Hardware watchdog," next.

## Hardware watchdog

Distinct from the service-level watchdog above: if the machine's own
*kernel* wedges, nothing running as an ordinary process -- including
`systemd` itself -- can act; only a piece of hardware that resets the SoC
regardless of software state can recover that. Raspberry Pi 4's SoC has one
(`bcm2835_wdt`), matching `docs/roadmap.md`'s "OS hang" rung.

This installer never edits Raspberry Pi OS's boot-time
`/boot/firmware/config.txt` itself: a mistake there risks the exact
powered-but-never-boots failure this whole milestone exists to diagnose --
categorically worse than leaving the hardware watchdog off, and the
opposite of what "do not enable destructive or poorly understood hardware
behavior blindly" (the milestone's own instruction) asks for.
`dtparam=watchdog=on` therefore stays a manual, documented, one-time
operator action (see the install guide) -- but once that step has made
`/dev/watchdog` appear, `scripts/install_camera_node.py
--enable-hardware-watchdog` writes the smallest safe systemd-level
configuration that pets it: a `system.conf.d/` drop-in
(`RuntimeWatchdogSec=14`, systemd's own machine-wide mechanism -- `PID 1`
pets the device directly, which is why this is not a per-unit `[Service]`
option), idempotent, refusing clearly and writing nothing if the device is
still absent. This takes effect after the next reboot or
`systemctl daemon-reexec`; `--status` reports the device's presence,
read-only, on every run.

**Disclosed limit:** this piece was implemented and hermetically tested
(the drop-in writer and capability probe, both rooted under an injectable
prefix exactly like the rest of this installer), but not live-verified
against a real hardware watchdog device -- no session validating this
milestone had access to real Pi hardware with `/dev/watchdog` enabled. It
remains a documented, capability-gated, explicitly opt-in golden path, not
something the installer enables on its own.

## Diagnostics implementation

Small, additive changes to `src/mockingbird_node/`:

- `config.py`: new `log_level: str` field (default `"warning"`), read from
  `MOCKINGBIRD_NODE_LOG_LEVEL`, validated against uvicorn's own known level
  set (`critical`/`error`/`warning`/`info`/`debug`/`trace`).
- `__main__.py`: passes `config.log_level` to `uvicorn.run(...)` instead of
  the hardcoded string; wraps `CameraNodeConfig.from_environment()` in a
  `try/except ValueError` that prints one clean `Camera Node configuration
  error: ...` line and exits `1` instead of a raw traceback.
- `app.py`: `create_node_app` registers a startup handler that prints one
  summary line (bind/port/configured providers/pairing-loaded state) at
  import-independent, log-level-independent visibility, mirroring the
  existing shutdown handler's placement and style.

None of this changes the Node's HTTP contract, credential handling, or any
product behavior in `mockingbird` (the main app) -- purely local process
diagnosability, matching this milestone's actual scope.

## Real-process smoke test

`tests/test_camera_node_real_process.py` (new) closes the one test gap the
reconnaissance identified explicitly: every existing Camera Node test drives
the FastAPI app in-process via `httpx.ASGITransport` (fast, but never proves
the package actually boots as a real OS process reachable over a real
socket). The new test builds the artifact, creates a real venv with the
*actual* runtime requirements installed (not `--no-deps`, unlike the existing
packaging test, since a real server needs `fastapi`/`uvicorn` importable),
launches `python -m mockingbird_node` as a genuine subprocess bound to an
ephemeral local port with the `synthetic` test provider, polls
`GET /node/v1/health` over a real TCP socket until it answers or a bounded
timeout elapses, asserts the payload shape, then sends `SIGTERM` and asserts
a clean, bounded-time exit -- proving graceful shutdown the same way
`systemd`'s own `TimeoutStopSec` will rely on in production. A second case
covers the configuration-failure path (an invalid env var) end-to-end
through a real process, asserting a fast, non-zero, non-hanging exit with the
new clean error message on stderr. This complements, and does not replace,
the existing fast in-process suite.

## Installer

`scripts/install_camera_node.py` (new) -- Python standard library only (no
third-party dependency, consistent with every other `scripts/*.py` build/deploy
tool in this repository), runnable with the system `python3` already present
before any venv exists. Responsibilities, in order, all idempotent:

1. Confirm running as root (required for `apt`, `useradd`, writing
   `/etc`/`/opt`/`/var/lib`, and installing the unit) and report the
   detected OS/hardware facts (`/etc/os-release`, `/proc/device-tree/model`
   if present) without requiring them to match any specific value --
   "do not architect the product around the current Raspberry Pi."
2. Best-effort install missing system prerequisites (see "System
   prerequisites"), reporting each optional package's outcome individually.
3. Create/verify the dedicated service account and its one supplementary
   group (see "Service identity and device access").
4. Create `/opt/mockingbird-camera-node/`, `/etc/mockingbird-camera-node/`
   with correct ownership/permissions if absent.
5. Build or reuse the venv (see "Update behavior" for the reuse/replace
   decision), `pip install` the artifact's wheel and `requirements.txt` into
   it, precompile with `compileall`.
6. Write `node.env` from the artifact's `camera-node.env.example`, **only if
   absent** -- see "Configuration paths."
7. Write the systemd unit (see above) -- only rewriting it, and only
   `daemon-reload`-ing, if its content actually changed, to avoid
   unnecessary churn on an already-correct install.
8. `systemctl enable --now mockingbird-camera-node.service` (or `restart`
   if already running and the venv changed).
9. Run the bounded local health check and print a clear, structured
   success/failure summary -- never a bare stack trace for an expected
   failure mode (missing prerequisite, permission problem, port already
   bound).

`--status` performs steps 1 and 9 only (fully read-only: reports OS facts,
installed/enabled/active state, current and rollback-candidate artifact
provenance, and a live health probe) and never mutates anything.
`--rollback` performs the swap described above. Every filesystem path is
computed from one small `InstallPaths` dataclass rooted at an injectable
prefix (`/` in production), and every privileged operation goes through one
injectable command-runner seam -- the same "hermetic-by-construction" shape
`scripts/deploy_windows_dev.py`'s `WindowsHost` seam already established for
this repository's other real-system-touching tooling -- so the majority of
this installer's actual decision logic (idempotency, path layout, manifest
comparison, rollback bookkeeping) is unit-tested without touching a real
system or requiring root (see "Validation," below). No remote-execution path
exists anywhere in this script: it only ever acts on the machine it is
invoked on, using a local artifact directory already present on disk --
never a URL, and never anything reachable by the MockingBird host over the
network.

## Security boundary

Unchanged from, and not a redesign of,
[camera-node-boundary-design.md](camera-node-boundary-design.md)'s existing
pairing/network contract: the Node's HTTP API is plain HTTP (no TLS), and
bearer-credential authentication is what actually protects each
authenticated endpoint. This milestone does not add, and explicitly must not
be read as adding, wire-level confidentiality. Concretely, on a shared or
untrusted local network:

- the one-time pairing *code* and the resulting bearer *credential* both
  travel in plaintext over the LAN during pairing and every subsequent
  authenticated request;
- only a SHA-256 digest of the credential is ever persisted at rest (already
  true before this milestone -- `_PairingState._persist_state`), but that
  protects the credential if the Node's *disk* is later read, not the
  credential in transit;
- anyone able to observe LAN traffic during pairing, or already holding a
  previously-observed credential, can authenticate to the Node exactly as
  the real host would, for as long as that pairing remains unrevoked.

Digest-at-rest storage is not a substitute for transport confidentiality and
must not be represented as solving it. This is an explicit, disclosed,
**unresolved** transport-security gap, carried forward into the project's
future v0.1 privacy/security release gate rather than silently accepted or
silently fixed here -- a full TLS/PKI redesign is out of scope for this
milestone (see "Non-goals"). No fixed or default credential exists anywhere
in this path (every credential is `secrets.token_urlsafe(32)`, randomly
generated at pairing time), and no credential is ever written to a log,
`node.env`, or any diagnostic output this milestone adds -- only the
deliberately local, short-lived, already-designed one-time pairing code is.

## Non-goals

Everything the milestone brief itself excludes: a full appliance/prebuilt SD
image, Raspberry Pi Imager integration, Zero 2 W characterization, edge
inference or model packaging on the Node, mDNS/discovery, cloud management,
remote command execution or remote host-triggered updates, a `.deb`/apt
repository, containers, broad TLS/PKI infrastructure, multi-camera Place
acceptance, general host installer changes, and unrelated UX/test-suite
cleanup. Additionally, and specific to this document: this installer does
not become a general Linux service-packaging framework -- it is one
purpose-built script for one package, not a reusable tool for other future
services.

## Acceptance criteria

A supported installation is accepted when, on the real reference device:

1. the installer completes successfully and is safe to re-run with no
   change in outcome;
2. `systemctl is-enabled`/`is-active` both report the service correctly
   after a normal boot with no manual intervention;
3. pairing established before an update, reboot, or crash survives it
   without re-pairing;
4. `GET /node/v1/health` and real capture/stream operation return to normal
   after each of: a normal service (re)start, an abnormal process kill, a
   full device reboot, and a bounded ordinary network interruption;
5. `journalctl -u mockingbird-camera-node` alone is enough to determine
   whether the service started, whether configuration loaded, which
   provider is active, whether pairing state loaded, and why a failure
   happened, without reading source code;
6. the measured Node recovery time against each of these events is compared
   against the host's bounded reconnect budget
   (`AnalysisStreamRetryPolicy`, `src/mockingbird/observation/
   engine_runtime.py`), with any resulting host-side change made only from
   that real measurement, never speculatively. (This criterion is exactly
   what caught the real defect this milestone found and fixed: measured
   against the *original* `backoff_seconds=2.0` default, the real Node
   recovery time -- ~55s -- exceeded the host's real worst-case retry
   window -- ~20-38s, dominated by `backoff_seconds` alone for a fully
   unreachable Node, not the ~72s a batch-duration assumption would
   predict. The corrected `backoff_seconds=12.0` was re-validated against
   this same criterion on a second real reboot. See "Real hardware
   acceptance findings," below, for the complete measurement.)

See the milestone's final report for the actual recorded measurements
against these criteria, and "Real hardware acceptance findings" below once
that pass is complete.

## Files touched

- `docs/camera-node-installer-design.md` (this document, new)
- `docs/camera-node-install-guide.md` (new -- operator-facing guide, the
  proven-on-hardware instructions)
- `docs/roadmap.md`, `AGENTS.md`, `docs/runtime-map.md`,
  `docs/camera-node-boundary-design.md`, `README.md`,
  `docs/using-mockingbird.md` (cross-references and current-state updates
  only -- see "Documentation updates")
- `scripts/build_camera_node_artifact.py` (reproducibility hardening)
- `scripts/install_camera_node.py` (new)
- `src/mockingbird_node/{app.py,config.py,__main__.py}` (diagnostics only --
  no HTTP contract or product-behavior change)
- `tests/test_camera_node_packaging.py` (extended assertions for the new
  provenance fields)
- `tests/test_install_camera_node.py` (new)
- `tests/test_camera_node_real_process.py` (new)

## Documentation updates

- `AGENTS.md`'s conditional document router gains one row routing Camera
  Node installer/service/OS-supervision work to this document.
- `roadmap.md` records this milestone's outcome under Phase 1 and adds the
  one-line Phase 4 cross-reference described in "Phase ownership," above.
- `runtime-map.md`'s existing "dev/ops tooling" entry for
  `build_camera_node_artifact.py` gains a sibling entry for
  `install_camera_node.py`, and its entry-points table gains the systemd
  unit as a new, non-Python "entry point" onto the same package.
- `camera-node-boundary-design.md`'s "Manual startup" section is corrected
  -- it currently states "The Node has no service installer or automatic
  updates," which this milestone makes no longer true. The manual
  `python -m mockingbird_node` path remains valid (development, testing, a
  non-systemd Linux host) and is kept; the section gains a link to this
  document and the install guide for the supported service path.
- `README.md`'s "Optional Camera Node" section gains one link to the new
  install guide alongside its existing manual-start instructions.

## Validation tier

Tier 3 (cross-cutting infrastructure with broad-enough blast radius to
warrant the full non-hardware gate: the complete backend suite, lint on
every touched file) plus Tier 4 (explicit hardware acceptance -- this
milestone's entire reboot/crash/network-interruption experiment set is
exactly Tier 4's "camera bridges, durable activation, ... release
acceptance" case, with the bounded question already stated in "Acceptance
criteria," above). See the milestone's final report for exact results.

## Real hardware acceptance findings

Against the project's real reference device (Raspberry Pi 4 Model B Rev
1.5, Raspberry Pi OS/Debian 13 "trixie" `aarch64`, Python 3.13.5) and the
real Windows-hosted MockingBird instance, 2026-08-18.

**Install (adopting the pre-existing ad hoc install).** First real run of
`install_camera_node.py` against a device that already had the hand-built
ad hoc unit described in "Relationship to the real reference device"
running for 40+ hours: succeeded on the first attempt, detected all three
system prerequisites already present, created the dedicated
`mockingbird-node` account (uid 999, primary group `mockingbird-node`,
supplementary group `video` only -- confirmed by inspecting the running
process's real `id` output), replaced the ad hoc unit with the reviewed
one, and reached a healthy state. Ownership/permissions matched the design
exactly: `/opt/mockingbird-camera-node` and `/etc/mockingbird-camera-node/
node.env` root-owned (`node.env` mode `0600`), `/var/lib/mockingbird-
camera-node/` owned by the service account via `StateDirectory=`. A real
functional capture (not just health/enumeration) was proven: a genuine
1920x1080 JPEG (720,243 bytes) was captured through the hardened service
identity, including the PiCamera2 warm dual-stream profile reaching
`ready`/`accepted`. One benign, non-fatal log line appears on every
PiCamera2 initialization: `libcamera`'s own `global_configuration.cpp`
logs an `ERROR` that `/home/mockingbird-node/.config/libcamera/
configuration.yaml` does not exist -- expected and harmless (`ProtectHome=
true` hides `/home` from the service, and there is no operator-supplied
libcamera override to find regardless), confirmed non-fatal by the
successful capture immediately following it in the same log. Not "fixed"
(there is nothing to fix -- creating a home directory purely to suppress
an optional-file-not-found message would trade away `ProtectHome=true`'s
real benefit for cosmetics); documented here and in the install guide's
advanced diagnostics instead.

Because the pre-existing ad hoc install used entirely different paths (a
login-user home directory, not `/etc`/`/opt`/`/var/lib`) and a different
service identity, adopting it necessarily involved one fresh Node pairing
rather than inheriting the ad hoc pairing file directly -- an expected,
disclosed, one-time consequence of migrating an unmanaged install onto the
new canonical layout, not a defect in the installer's own update-
preservation guarantee (separately proven both hermetically -- see
"Update behavior"/"Rollback," above -- and live on this device across the
crash/clean-restart/network-interruption acceptance, below, all of which
kept the *same* pairing established here intact).

**Pairing with the real host.** A fresh Node pairing code was exchanged
with the real, already-running MockingBird host through the actual product
API (`POST /api/camera-nodes/pair`, then the guided in-place camera-
configuration repair path -- `.../camera-configuration/preview` then
`.../apply`, the same mechanism "Guided Camera Editing" already provides
for a lost/revoked credential) against the pre-existing real `Pi camera 1`
Source/Stream, over the real LAN. The repair preserved the existing
Source/Stream identity, Zones, monitoring policy, and history exactly as
its own preview response promised (`preservation_summary`), changing only
the pairing credential, capability fingerprint, and evidence-profile
fields. `GET /node/v1/health` reported `pairing_required: false` and the
persisted `pairing.json` digest matched the newly issued credential.

**Reboot experiment (first pass -- found a real defect).** With a live
Observation Engine session actually running against the paired Node
(`POST /api/streams/.../observation/start` reached `state: observing`),
the device was rebooted (`systemd-run --on-active=1 systemctl reboot`, so
the triggering SSH command itself returned cleanly before the reboot
began) and both vantage points polled concurrently and independently:

| Event | Elapsed (from reboot command) |
| --- | --- |
| SSH stops responding | +8s |
| SSH reachable again | +47.2s |
| `systemctl is-active`: active | +47.7s |
| `/node/v1/health` answers 200 | **+55.2s** |
| Paired credential digest unchanged after reboot | confirmed at +56.0s |
| Host's first reconnect attempt logged | +17.8s |
| Host exhausts its 6-attempt budget, gives up | **+38.1s** (`stopped_reason=camera_unavailable`) |

The host gave up roughly **17 seconds before** the Node was actually
healthy again -- a real, measured case of exactly the failure mode the
milestone brief anticipated ("the host gives up before a normally
functioning Pi can recover"). Root cause and fix: see "backoff_seconds
raised from 2.0 to 12.0" in
[observation-session-renewal-continuity-contract.md](observation-session-renewal-continuity-contract.md).
No re-pairing was required by the reboot itself (the pairing digest survived
correctly); the defect was purely in how long the host kept trying before
giving up.

**Reboot experiment (second pass -- confirms the fix).** The Windows host
was redeployed at the corrected commit
(`git_commit=b29837af7a7f1db656a1c2c3d3229b9e771e205b`, confirmed live via
`GET /api/product/instance` after the deploy tool's own bounded
verification gave a false-negative timeout -- a previously-documented
flaky pattern, not a real failure; see "Windows redeploy," below), a fresh
Observation session started against the same real Pi 4, and the identical
reboot procedure repeated:

| Event | Elapsed (from reboot command) |
| --- | --- |
| SSH stops responding | +7.8s |
| SSH reachable again | +50.3s |
| `/node/v1/health` answers 200 | +58.0s |
| Paired credential digest unchanged after reboot | confirmed at +59.1s |
| Host's first reconnect attempt logged | +21.6s |
| Host's second attempt (spacing now ~12.1s, matching the fix exactly) | +33.7s |
| Host reconnects (`camera_connected: true`, still `observing`) | **+88.7s**, never exhausted its budget |

The host never reached `stopped`/gave up -- it stayed `observing: true`
throughout, correctly weathering the interruption and reconnecting once
the Node was genuinely ready. The inter-attempt spacing (~12.1s between
attempts 1 and 2) directly confirms the mechanism: `backoff_seconds=12.0`
is what actually governs real-world retry cadence for a fully-unreachable
Node. This closes the defect with real re-validation, not only the
hermetic regression test.

**Crash acceptance.** With the session `observing` again, the Node process
was killed abnormally (`sudo kill -9 <MainPID>`, the real "abnormal
termination" case -- distinct from the graceful-SIGTERM path
`TimeoutStopSec` governs). Measured directly from `journalctl`'s own
`systemd[1]` lifecycle lines (timestamps local, `08:04:14`/`08:04:19`):

```
08:04:14 mockingbird-camera-node.service: Main process exited, code=killed, status=9/KILL
08:04:14 mockingbird-camera-node.service: Failed with result 'signal'.
08:04:19 mockingbird-camera-node.service: Scheduled restart job, restart counter is at 1.
08:04:19 Started mockingbird-camera-node.service - MockingBird Camera Node.
```

- `systemd` waited exactly `RestartSec=5`'s configured 5 seconds, then
  respawned it (`Restart=on-failure` fired as designed, restart counter
  correctly incremented to 1); `/node/v1/health` answered again ~7s after
  the kill (the SSH-round-trip-inclusive measurement -- the service itself
  was active within the 5s restart delay plus a brief FastAPI/PiCamera2
  startup);
- the paired credential digest was **byte-identical** before and after
  (`StateDirectory=` survived the crash untouched, as expected -- the
  crash never touched the process's own already-fsync'd state file);
- `journalctl` gave an unambiguous, diagnosable sequence exactly as shown
  above -- an operator can tell precisely what happened (killed by signal
  9, respawned once) without guessing, and the unit's *current* `Result=`
  correctly reads `success` once the respawned instance is healthy (a
  systemd property of the live instance, not a permanent scar from the
  crash -- the crash itself remains visible as history in the journal
  lines above, not erased);
- the host's live Observation session survived the interruption through
  its own bounded reconnect logic (the same mechanism just re-validated
  above), never requiring a manual restart, since the crash-respawn cycle
  finished in single-digit seconds -- far inside even the *old*, pre-fix
  retry budget.

**Clean restart.** `sudo systemctl restart mockingbird-camera-node` while
paired and observing: `systemctl status` afterward showed
`Active: active (running)` with **no `failed`/`Result=signal` markers** --
confirming directly what "backoff_seconds raised..." above predicted from
the real-process test's own SIGTERM finding: `systemd` correctly
correlates a process death with its *own* stop request and does not treat
a normal, systemd-initiated restart as an `on-failure` trigger, even
though `uvicorn` still technically exits via a re-raised `SIGTERM`.
Pairing state, `node.env`, and the running Observation session all
survived identically to the crash case.

**Network interruption.** A temporary `nft` rule dropped only inbound LAN
traffic to the Node's own port, deliberately never touching `wlan0` itself
or SSH (port 22) -- this device has no wired fallback, so disabling its
own WiFi interface would have required physical access to recover (see
"Relationship to the real reference device"):

```
table inet mockingbird_test_block {
    chain input {
        type filter hook input priority 0;
        iifname != "lo" tcp dport 8787 drop
    }
}
```

The `iifname != "lo"` condition was a real, empirically-found correction --
a first attempt without it discovered that `nft`'s `input` hook sees
*loopback* traffic too, so a bare `tcp dport 8787 drop` blocked the Node's
own `curl 127.0.0.1:8787` health check exactly as much as external LAN
access, defeating the point of the experiment (proving the Node stays
healthy *independently* of external reachability specifically requires
excluding loopback from the block). With the corrected rule: external
access failed immediately (`curl` from another LAN device timed out
outright) while `curl 127.0.0.1:8787/node/v1/health` from the Pi itself
kept answering `200` throughout -- direct proof the Node process itself
never degrades merely because the network path to it is cut. The host
(already mid-reconnect from the preceding clean-restart test) correctly
progressed through its same bounded attempt sequence
(`analysis_stream_unavailable`, observed at attempt 4 of 6 while the rule
was active) and, once the rule was removed, **reconnected successfully at
attempt 5 of 6** (`camera_connected: true`, `stopped_reason: null`) --
never exhausting the budget, no manual action, no re-pairing. A bounded,
truthful, ordinary interruption handled correctly.

**Idempotency, update, and rollback (live, on the real device).** Beyond
the hermetic test suite, the full sequence was run for real: (1) re-running
the installer with the *identical* artifact reported `already exists` /
`already installed` / `existing node.env preserved untouched` / `systemd
unit: unchanged` / `already running, left untouched` for every step, with
`pairing_required: false` unaffected; (2) installing a second, freshly
-built artifact from the same commit (a different `build_id`, proving
`build_id` rather than commit or version string is what actually gates the
update decision) correctly kept exactly one prior version
(`venv.previous/`, `manifest.json.previous`) and left `node.env`'s
modification time and the pairing digest completely unchanged; (3)
`--rollback` swapped cleanly back to the first build and reported healthy;
(4) re-installing the second artifact rolled forward again just as
cleanly. Every step reported the exact provenance `build_id` it acted on,
and the paired credential digest was verified byte-identical across the
entire sequence.

## Complete validation results

Full backend suite against the final commit: **3070 passed, 30 failed**,
1:36:53 total (compared to this milestone's own starting baseline, recorded
in `docs/v01-product-flow-gap-pass-v1-findings.md`: 3038 passed, 31 failed).
The 31 new tests this milestone adds (9 in `test_camera_node_packaging.py`,
19 in `test_install_camera_node.py`, 2 in `test_camera_node_real_process.py`,
1 in `test_engine_runtime.py`) all pass; none of the 30 failures are among
them. Every failing test was individually re-run in isolation and
root-caused:

- `test_camera_node.py::test_picamera2_warm_required_pair_retries_once_
  after_resource_rejections` -- passes cleanly alone (confirmed twice, once
  earlier in this same session as part of the full Camera Node family, and
  again isolated after the full run); a timing/order-dependent flake under
  full-suite load, not a real defect, and not in a file this milestone
  changed the behavior of.
- `test_dataset_quality.py`, `test_exact_frame_capture.py`,
  `test_wildlife_journal.py`, `test_zone_diagnostic.py` (5 tests, all from
  one shared root cause: `scripts/capture_zone_diagnostic.py` importing a
  symbol, `_object_detector_zone_crop`, that no longer exists in
  `mockingbird.api.main`) -- each individually re-run and root-caused;
  none touch Camera Node, the installer, or `engine_runtime.py`, and none
  are reachable from this milestone's diff by any plausible mechanism.
- `test_stream_playback_contract.py` (20 tests, the largest cluster) --
  fails identically even fully isolated from the rest of the suite (`20
  failed, 133 passed` running only this one file). Root-caused one
  representative case directly: a Windows-DirectShow path-handling test
  expects a literal `C:\ffmpeg\bin\ffmpeg.exe` argument and instead
  observes `/mnt/c/ffmpeg/bin/ffmpeg.exe` -- a WSL-path-translation
  artifact of this sandbox's current environment, unrelated to any product
  code. Confirmed by direct proof, not inference: `git log 5518dbb..HEAD
  --stat -- src/mockingbird/playback/` returns **no commits at all** --
  every file this cluster exercises is byte-identical to the starting
  baseline, so this exact failure signature is independent of this
  milestone's diff by construction.
- `test_local_product_packaging.py::test_real_windows_bioclip_dependency_
  closure_installs_offline_with_no_duplicates` -- the same pre-existing
  `idna` pin conflict already found and disclosed in "Windows redeploy,"
  below, now additionally confirmed failing hermetically (not only in the
  live redeploy attempt).

Net reconciliation: 3100 total tests (3069 baseline + 31 new), 32 more
passes than baseline (31 new tests passing plus one previously-failing
baseline test now passing -- consistent with the already-established
"pre-existing, environmental, or order-dependent" character of this
inherited baseline, not a regression). Zero of the 30 failures are
attributable to this milestone; the ~30-test baseline itself remains
explicitly out of scope to fix (see "Non-goals").

`ruff check` on every file this milestone touched: clean, except two
findings in `tests/test_engine_runtime.py` (one unused import, one unused
local variable) independently confirmed present verbatim in the file at
`HEAD~2` -- pre-existing, not introduced by this milestone's one added
test function, and left alone per the same non-goal.

## Windows redeploy

Two incidental findings while producing a deployable build to validate the
retry-policy fix on real hardware, neither part of this milestone's own
scope:

- A first redeploy attempt failed on a **pre-existing, unrelated** defect:
  `scripts/build_local_product.py`'s `WINDOWS_BIOCLIP_RUNTIME_
  REQUIREMENTS` pins `idna==3.18`, while the core tier's loose
  `anyio>=3.7,<4.0` bound now resolves a newer `idna` release from PyPI --
  the exact "duplicate `.dist-info`" class of bug
  `verify_no_duplicate_site_packages_metadata` was already built to catch
  (see "BioCLIP durable-deployment findings" in
  [windows-dev-deployment-design.md](windows-dev-deployment-design.md)),
  and it did. Not fixed here -- out of scope for this milestone ("general
  host installer changes"), and BioCLIP is unrelated to Camera Node.
  Worked around with the existing `--skip-bioclip-runtime` flag, which
  avoids the conflicting tier entirely with zero changes to any file
  outside this milestone's scope. Left for the BioCLIP/packaging owner to
  re-pin `idna` to match -- fixed in v0.1 Release Hardening v1 (see
  "BioCLIP/idna packaging conflict" in
  [local-product-packaging-design.md](local-product-packaging-design.md)):
  an explicit `idna==3.18` pin added to `WINDOWS_RUNTIME_REQUIREMENTS`,
  matching the BioCLIP tier's own already-validated pin.
- The deploy tool's own bounded post-launch verification reported a false
  failure (`did not return a valid product-health body`) even though the
  new build was genuinely healthy seconds later -- directly confirmed via
  `GET /api/product/instance` (`git_commit` matched exactly) and `GET
  /api/product/health` (`ready: true`). This is the same previously
  -documented flaky-verification pattern noted for this sandbox's
  WSL/Windows interop (slow real CUDA/ONNX cold start racing the
  verification timeout); re-querying `--status` immediately afterward
  self-corrected. Not a defect in this milestone's own code.

## Camera Node Boot Identity + Autonomous Recovery v1 (2026-08-21)

Follow-on milestone, layered on the design above. Implements the "Bounded
additions to the Camera Node golden path" and closes most of the "Camera
Node field-recovery ladder" open items in [roadmap.md](roadmap.md) Gate D/E
-- see that document's own dated "Current status" entry for the complete
narrative and the exact 2026-08-20 incident this responds to. The design
sections above ("Boot identity," "Startup self-test," "Watchdog," "Hardware
watchdog") already describe the resulting current-state design; this
section is the validation/provenance record.

### Files touched

- `src/mockingbird_node/{identity,selftest,watchdog}.py` (new)
- `src/mockingbird_node/{app,__init__}.py` (wiring; additive
  `/node/v1/health` fields, per-part analysis-stream boot-identity headers,
  startup/shutdown event handlers, `__version__` fallback)
- `scripts/build_camera_node_artifact.py` (`NODE_FILES` gains the three new
  modules -- the one real defect this milestone found in its own work:
  the artifact silently omitted them until caught by the real-process
  test, see "Real service-level validation," below)
- `scripts/install_camera_node.py` (`Type=notify`/`WatchdogSec=30`;
  `--enable-hardware-watchdog`, `hardware_watchdog_device_present`,
  `--status` reports device presence)
- `src/mockingbird/observation/media_contracts.py`
  (`AnalysisFrameEnvelope.node_boot_id`/`node_service_version`)
- `src/mockingbird/observation/camera_node_live.py` (optional header
  parsing; `AnalysisSourceStatus` gains the same two fields, tracked in
  `CameraNodeAnalysisSource._offer`)
- `src/mockingbird/observation/engine_runtime.py`
  (`_checkpoint_observation_exposure` threads boot identity through and
  surfaces a detected transition into `advanced`)
- `src/mockingbird/repository/product_repository.py`
  (`record_observation_exposure_frame` extended;
  `_record_camera_node_boot_observation`;
  `CameraNodeBootObservationOutcome`; `StreamLivePlaybackConfig.
  camera_node_last_seen_at`)
- `src/mockingbird/storage/models.py` (`CameraSourceModel` gains five
  nullable columns)
- `src/mockingbird/storage/database.py` (schema 36 -> 37,
  `_migrate_to_camera_node_boot_identity`)
- `src/mockingbird/observation/unified_status.py`
  (`CAMERA_NODE_LAST_SEEN_STALE_AFTER_SECONDS`; `camera_node_facts` no
  longer reports `camera_connected: true` from configuration alone once
  real staleness evidence exists)
- `src/mockingbird/diagnostics/doctor.py` (imports the shared staleness
  constant rather than keeping a private copy; `_gather_camera_node`/
  `_interpret_camera_node` read the new durable facts; new restart-
  instability and no-open-session-staleness branches)
- `docs/camera-node-install-guide.md`, `docs/
  mockingbird-doctor-operational-health-contract.md`, `docs/roadmap.md`
  (this document; operator guide; Doctor contract; roadmap status)
- New tests: `tests/test_camera_node_boot_identity.py`; extended
  `tests/test_persistence.py`, `tests/test_engine_runtime.py`, `tests/
  test_observation_camera_node_live.py`, `tests/test_doctor.py`, `tests/
  test_install_camera_node.py`, `tests/test_camera_node_real_process.py`,
  `tests/test_unified_observation_status.py`
- Six pre-existing tests' hardcoded `CURRENT_DATABASE_SCHEMA_VERSION == 36`
  sentinels bumped to `37` (`test_camera_health.py`, `test_camera_node.py`,
  `test_candidate_visit_repository.py` x4, `test_visit_tags.py`, `test_
  species_candidate_packs.py`, `test_visit_collections.py`, `test_yard_
  map.py` -- 14 assertions across 8 files total), mirroring the identical,
  expected mechanical fix the schema-36 migration itself required.

### Validation

- **Tier 1/2 focused sweep** (every Camera Node/Doctor/observation-
  recovery/host-status file above, plus every file whose hardcoded schema
  sentinel needed bumping): **504 passed, 0 failed**.
- **Core gate** (`python scripts/verify_core.py`, the whole backend suite
  minus `slow`): **3569 passed, 2 skipped, 11 deselected, 11 xfailed, 0
  failed** in 540.71s (9m01s).
- **`slow`-tier Camera Node tests** (real venv + real subprocess):
  `test_camera_node_real_process.py` (extended) and `test_camera_node_
  packaging.py` (`NODE_FILES` assertion) both green.
- **Lint**: every newly-created file (`identity.py`, `selftest.py`,
  `watchdog.py`, `test_camera_node_boot_identity.py`) is `ruff check`
  clean. Every *modified* file was diffed against its own `HEAD` version's
  lint output (via a parallel checkout of just the `HEAD` copies) to
  isolate genuinely new findings from pre-existing ones at shifted line
  numbers -- one real new finding (`test_camera_node_boot_identity.py`'s
  own unused `threading` import) was found and fixed; every remaining
  finding (an unrelated pre-existing `product_repository.py` cluster,
  plus a handful of pre-existing fixture-class semicolons/unused imports
  in `test_camera_node.py`/`test_engine_runtime.py`/`test_observation_
  camera_node_live.py`) was confirmed, by `git diff`, to sit outside every
  line this milestone actually changed.

### Real service-level validation

Not performed against the real reference Pi 4 -- deliberately. That device
is currently paired, healthy, and serving the project's real ongoing field
monitoring (confirmed live via a single read-only `GET /node/v1/health`
probe at the start of this session); deploying new/experimental boot-
identity code to it, or rebooting it, was judged disproportionate to a
task that deterministic tests plus one bounded, safe, *local* service-level
check could establish just as rigorously -- see "Confirm first" in this
project's own operating guardrails. Live redeploy/reboot acceptance against
the real reference Pi remains a natural, low-risk follow-up, not performed
here without explicit direction.

Instead, this sandbox's own genuine `systemctl --user` (real `systemd
255`, not a simulation) was used directly:

1. Built a real artifact (`build_camera_node_artifact.py
   --allow-dirty-source`) and a real venv; installing it into the venv
   *first* surfaced the one real defect this milestone's own work
   introduced: `NODE_FILES` had not been updated for the three new
   modules, so the installed package raised `ModuleNotFoundError:
   No module named 'mockingbird_node.identity'` at import time. Fixed
   immediately (see "Files touched," above); every subsequent step used
   the corrected artifact.
2. Installed the corrected build as a real, temporary `Type=notify`/
   `WatchdogSec=8`/`NotifyAccess=main` user-level unit (root/system-level
   privileges are not available in this sandbox; a user unit exercises
   identical `Type=notify`/watchdog systemd semantics). `systemctl --user
   status` correctly reported `active (running)` only once the real
   process sent `READY=1`; the real journal showed the enriched startup
   line (`boot_id=... version=0.1.0 self_test=passed`) and a real `GET
   /node/v1/health` returned every new field correctly, including
   `watchdog.enabled: true, ping_interval_seconds: 4.0` (half of the
   configured `WatchdogSec=8`, exactly as designed).
3. **The core proof**: `kill -STOP` on the real main PID -- a genuine
   process hang (frozen, never exits), distinct from every crash/`kill -9`
   case already proven by the original installer milestone. Real `systemd`
   output, unedited:

   ```
   systemd[793]: mockingbird-camera-node-test.service: Watchdog timeout (limit 8s)!
   systemd[793]: mockingbird-camera-node-test.service: Killing process <pid> (python) with signal SIGABRT.
   systemd[793]: mockingbird-camera-node-test.service: Main process exited, code=dumped, status=6/ABRT
   systemd[793]: mockingbird-camera-node-test.service: Failed with result 'watchdog'.
   systemd[793]: mockingbird-camera-node-test.service: Scheduled restart job, restart counter is at 1.
   ```

   The respawned process answered `/node/v1/health` with the identical
   `boot_id` as before (the machine never rebooted, only the process did)
   -- direct, real proof of the "service hang -> watchdog timeout ->
   service restart -> same boot_id" ladder rung, not merely an assertion
   about it. `NRestarts` read back `1`; `Result 'watchdog'` is `systemd`'s
   own diagnostic, distinguishable in `journalctl` from `Result 'signal'`
   (a real crash, per the original milestone's own findings above).
4. Cleaned up completely: unit stopped, disabled, removed, `daemon-reload`d;
   `systemctl --user status` afterward reports the unit does not exist.
   No residual state left on this machine.

This is a genuine, real-`systemd`, real-process validation of exactly the
mechanism production will use -- not a simulation of one -- and is the
"one bounded service-level check" the milestone's own validation
instructions called for.

### Decision

**A -- Boot identity and autonomous service recovery implemented.** The
Camera Node exposes real boot/service identity (never fabricated),
recovers automatically from every software-level failure it actually
controls -- a process crash (pre-existing `Restart=on-failure`) and now
also a genuine process hang (new `sd_notify`/`WatchdogSec` watchdog,
real-`systemd`-verified) -- and the host now diagnoses and reconnects
correctly, including through the specific gap ("offline, last seen") the
real 2026-08-20 incident exposed. Hardware-watchdog (OS-hang) recovery is
implemented and hermetically tested but explicitly not live-verified, and
is disclosed as exactly that rather than folded into the "A" claim by
omission; per the milestone's own instructions, this does not on its own
force a "B" -- the service-level watchdog this milestone actually shipped
is real, working, and closes the failure class it targets. The Camera Node
never claims to recover a machine that never boots at all -- see "Never-
boots boundary" in [roadmap.md](roadmap.md).

## Camera Node Configuration Backup + Reprovision / Replacement Recovery v1 (2026-08-21)

Closes the two items the prior milestone's own disposition left explicitly
open: "a configuration backup/export mechanism" and "the replacement-node
workflow itself." Full contract, state inventory, and design rationale live
in
[camera-node-reprovision-recovery-design.md](camera-node-reprovision-recovery-design.md);
this section records only what changed in this document's own areas
(installer, configuration paths, atomic-write safety).

### Configuration export/import

`scripts/install_camera_node.py --export-config PATH` / `--import-config
PATH`. The exported bundle is the portable subset of `node.env` (display
name, bind, port, providers, camera/image bounds, pairing TTL,
preview-viewer cap, log level) wrapped in a small versioned JSON envelope --
never `MOCKINGBIRD_NODE_PAIRING_STATE_PATH` (recomputed fresh for whichever
install imports it) or the pairing-state directory itself (node-local,
hash-only, not portable). Import extends -- never weakens -- "Never
overwrites this file once it exists": it only ever writes `node.env` when
none exists yet, exactly like a fresh install's own default-template write.

### Configuration-write safety (audit finding)

This milestone's own instructions required auditing every pairing/config
write this work touched for atomicity. `ensure_config_file`'s `node.env`
write was found to be a plain `Path.write_text` -- not atomic. Fixed with a
new `atomic_write_text` helper (temp file in the same directory, `O_EXCL`
create, `fsync`, `os.replace`, then `chmod`), mirroring the exact shape
`mockingbird_node.app._PairingState._persist_state` already used for
`pairing.json` -- the only existing precedent in the codebase, previously
not shared/importable. Both the default-template write and an imported-
bundle write now go through it.

### Replacement confirmation (mechanism lives in product_repository.py)

`node_id`'s existing role as "opaque identity used to reject an
incompatible replacement Node" is preserved as the *default*; Guided Camera
Editing's preview/apply requests gained one new field,
`confirm_node_identity_change`, that deliberately overrides that guard for
a genuine hardware swap. See "Logical-vs-physical identity" and
"Provenance" in the linked design doc for the full mechanism -- this stays
entirely inside the existing transactional apply, not a new endpoint or a
parallel pairing path.

### Decision

**A -- Reprovision/replacement recovery implemented.** Configuration
backup/export/import, a confirmed hardware-replacement path that reattaches
new physical infrastructure to an existing logical Source/Stream, bounded
provenance, honest capability rediscovery, and a Doctor reminder to review
Zones are all implemented and tested. A real destructive Pi reprovision
against the reference device was not performed (not required by this
milestone's own validation tiers); see the milestone report for the exact
sandboxed/hermetic proof this rested on instead.

## Camera Node Upgrade & Compatibility Recovery v1 (2026-08-26)

Closes the one item explicitly left open by this document's own "Update
behavior"/"Rollback" sections above: those already gave `install_camera_
node.py` real update/rollback *mechanics* (`build_id`-keyed idempotency,
exactly-one-retained-previous-version), but not a genuine upgrade
*contract* -- no artifact-integrity verification before mutating anything,
no staged build-and-verify before touching the live install, no automatic
recovery when a newly-activated build fails its own health check, and no
Host-facing wire-protocol compatibility reporting. Full contract,
investigation, and validation record: see
[camera-node-upgrade-compatibility-recovery-v1-report.md](camera-node-upgrade-compatibility-recovery-v1-report.md).
This section records only what changed in this document's own areas.

### A real, reproduced packaging defect found first

Before any of the above could be exercised for real, this milestone's own
required investigation (`scripts/build_camera_node_artifact.py`) found that
`NODE_FILES` had silently drifted behind `app.py`'s own real imports:
Remote / Intermittent-WAN Transport Foundation v1 added `transport_client.py`/
`transport_credential.py`/`transport_log.py`/`transport_spool.py`/
`transport_worker.py`/`atomic_io.py` to `src/mockingbird_node/` without
updating this builder's file list -- the identical class of gap "Camera Node
Boot Identity + Autonomous Recovery v1," above, already found and fixed
once for `identity.py`/`selftest.py`/`watchdog.py`. Confirmed by direct
reproduction, not inference: a real venv install of the pre-fix wheel
raised `ModuleNotFoundError: No module named 'mockingbird_node.transport_
client'` at `python -m mockingbird_node` startup -- every fresh install
*and* every upgrade using the pre-fix builder was completely broken, a fact
the existing `@pytest.mark.slow` real-process tests would have caught
eventually but had not been run since the regression was introduced. Fixed
(`NODE_FILES` now lists all fourteen files) and closed durably, not just
patched: a new fast, static (no venv, no pip) test parses every packaged
file's own `from .xxx import ...` statements via `ast` and asserts the
target is itself in `NODE_FILES`, so the same class of drift cannot recur
silently between slow-tier runs. `manifest.json` also gained a `protocol`
object (`node_api_version`/`transport_protocol_version`, read via a plain
text-pattern extraction over already-read source bytes -- never an import,
keeping this builder stdlib-only) for the compatibility work below.

### Preflight, staged activation, and automatic recovery

`install_or_update_venv` no longer retires the live `venv` before the
candidate is even built. It now stages the candidate at a separate
`venv.staging`/`manifest.json.staging`, pip-installs into it, and runs the
cheapest possible real verification -- `import mockingbird_node.app` inside
that staged venv, the exact check that would have caught the packaging
defect above at install time, on every device, forever -- *before* the live
`venv`/`.previous` are touched at all. Activation then promotes the
manifest *first* (a small, now-atomic file write via the existing
`atomic_write_text` helper) and the venv *second* (two directory renames).
This ordering is deliberate, not incidental: an interim design that
activated the venv first and reconciled purely on "does `venv.staging`
still exist" was found, during this milestone's own adversarial review, to
miss the crash window *immediately after* that rename -- at that instant
`venv.staging` is already gone, so nothing detected that the manifest
still needed updating, and a subsequent retry could destroy the genuinely
-good prior build. Making the manifest the single source of truth for
"which build is meant to be live" closes that gap completely: `_recover_
staged_activation` (which every `install_or_update_venv` call runs first,
a no-op when nothing is in progress) resolves any interruption to exactly
one of three states purely by comparing the live manifest's `build_id`
against the staged one -- never started (discard and rebuild), manifest
done but venv not yet promoted (finish the venv rename -- always safe,
since staging was fully verified before activation ever began), or both
already done (just clean up the now-redundant staging marker). `install()`
itself gained a `run_preflight` gate (artifact well-formed, `SHA256SUMS`
checksums verified against `build_camera_node_artifact.py`'s own existing,
previously-unverified provenance machinery -- skipped only when the
candidate is already installed, since nothing will be staged either way --
disk space, wire-protocol compatibility; a pre-existing corrupted `node.env`
or `pairing.json` is reported but never blocking, since the upgrade neither
reads nor depends on either) that runs before any mutation and raises
cleanly on the first blocking finding; `--preflight` runs the identical
function read-only. If the newly-activated build fails its own post-update
health verification, `install()` automatically invokes the existing
`rollback()` to restore the prior known-good build (never on a first-ever
install, where nothing exists to restore to) and reports the outcome
honestly (`InstallReport.rolled_back`) rather than claiming an ordinary
success -- `main()` only treats this as a warning-worthy surprise when it
happened *inside* an `install()` call; a plain, directly-requested
`--rollback` that succeeds is an ordinary, healthy, zero-exit-code outcome,
not a masked failure. An unexpected `node_id` change during an upgrade is
never silently "fixed" by this same rollback path -- it raises distinctly,
matching this document's and the governing brief's own "do not confuse
upgrade with replacement" boundary.

### Compatibility

A small `NodeUpgradeCompatibility` classification
(`current`/`compatible_older`/`incompatible`/`unknown`), styled after the
existing `mockingbird.observation.provider_compatibility` `Literal` +
label-dict convention, compares a candidate's declared wire protocol
against the currently-installed build's -- a Node-local, static
self-comparison only; the installer has no configured Host address or
credential to call. `compatible_older` is documented as not reachable
today: the real Host gate (`NODE_API_VERSION`/`TRANSPORT_PROTOCOL_VERSION`
in `mockingbird.source_providers.camera_node`/`mockingbird.api.
camera_node_transport`) is exact-match only, a deliberate, already-accepted
pre-1.0 choice (see "Host <-> Camera Node compatibility behavior" in
docs/release-engineering-foundation-v1-report.md) not reopened here.

### Decision

See
[camera-node-upgrade-compatibility-recovery-v1-report.md](camera-node-upgrade-compatibility-recovery-v1-report.md)
for the classification and the complete acceptance record, including real
hardware acceptance and any honestly-disclosed remaining limitations.

## Storage/media-health and hardware-quality visibility (Release Reliability & First-Run Recovery v1, 2026-09-08)

Closes the two remaining named gaps in Gate E's "Field-failure acceptance
matrix" (`release-execution-state.md` §6.R at the time): "nothing today
checks the node's own free space, write pressure, or... filesystem/storage
health," and no undervoltage/throttling/CPU-temperature telemetry existed
at all. New `mockingbird_node/hardware_health.py`, mirroring `identity.py`'s
own "read-only, best-effort, never fabricate a value the real platform
cannot confirm" shape exactly:

- **Storage.** `read_storage_health(directory)` reuses the Host's own
  already-accepted graduated healthy/getting_low/action_recommended/
  critical ladder and threshold values (`mockingbird.storage.database`) --
  duplicated, not imported, matching this package's established
  cross-boundary convention (see `doctor.py`'s own `_DOCTOR_NODE_API_
  VERSION`/`_DOCTOR_TRANSPORT_PROTOCOL_VERSION` precedent): `mockingbird_
  node` is a separate, deliberately slim installable package and must not
  depend on the main `mockingbird` package. Probes the Node's own pairing/
  config state directory -- the one local storage consumer every supported
  install has regardless of whether the opt-in transport spool is
  configured (the spool already has its own independent, already-accepted
  `min_free_bytes` write-refusal for the remote/intermittent-WAN case;
  this is deliberately not that).
- **Hardware quality.** `read_hardware_quality()` reads `vcgencmd
  get_throttled`/`measure_temp`, capability-gated on `shutil.which
  ("vcgencmd")` -- `None` entirely off Raspberry Pi, matching this
  product's "unsupported is hidden or plainly explained, never shown as
  if it might work" doctrine. Distinguishes a *currently* active
  undervoltage/throttling condition from one that merely *occurred* at
  some point since boot -- only the former marks the Node degraded (a
  resolved historical event must not misreport as an ongoing problem).
  Parsing verified directly against real captured output from the
  reference Pi (`throttled=0x0`, `temp=47.7'C`) before being written, not
  guessed from documentation alone.

**Bounded, actionable storage-pressure response** (the golden-path Camera
Node has no local storage consumer of its own besides pairing/config state
and optional logs): a `critical` storage tier, or a currently-active
hardware-quality problem, now degrades `run_startup_self_test`'s own
result (new reason codes `storage_critically_low` / `hardware_quality_
critical`) -- the same already-established, already-product-visible
mechanism a missing camera already uses, not a new alerting channel. Both
facts are additionally exposed as new, freshly-probed-per-request
`storage`/`hardware` fields on `/node/v1/health` (unlike `self_test`, a
one-time startup snapshot -- storage/hardware conditions genuinely change
over a Node's uptime).

**Deliberately not built:** persisting these facts durably on the Host
(`CameraSourceModel`'s own checkpointed boot-identity columns) -- the
Host's existing Camera Node Doctor check reads only the database, never a
live `/node/v1/health` poll (confirmed directly against `doctor.py`), and
adding a new checkpoint cadence plus a schema migration for two visibility
facts was judged materially larger than this milestone's own bounded
scope. Host-side durable surfacing, if a future need for it is
demonstrated, remains open follow-up work, not silently dropped.
