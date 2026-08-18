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
  (`mockingbird_node/{__init__,__main__,app,config,providers}.py` only; no
  `mockingbird`, `web`, `tests`, or `data` paths; no SQLAlchemy or any main-app
  dependency -- enforced by the existing `test_camera_node_artifact_is_slim_and_launcher_checks_without_starting`).
- `requirements.txt` -- the Node's own runtime dependencies
  (`fastapi`/`pydantic`/`uvicorn[standard]`), independent of the main app's
  `pyproject.toml`.
- `camera-node.env.example` -- a starting configuration.
- `manifest.json` -- artifact identity, now including verifiable source
  provenance (see below).
- `SHA256SUMS` -- checksums of all of the above.

This four/five-file directory *is* "a versioned Camera Node artifact" in the
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
Type=simple
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
- `docs/roadmap.md`, `docs/AGENTS.md`, `docs/runtime-map.md`,
  `docs/camera-node-boundary-design.md`, `README.md` (cross-references and
  current-state updates only -- see "Documentation updates")
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
  re-pin `idna` to match.
- The deploy tool's own bounded post-launch verification reported a false
  failure (`did not return a valid product-health body`) even though the
  new build was genuinely healthy seconds later -- directly confirmed via
  `GET /api/product/instance` (`git_commit` matched exactly) and `GET
  /api/product/health` (`ready: true`). This is the same previously
  -documented flaky-verification pattern noted for this sandbox's
  WSL/Windows interop (slow real CUDA/ONNX cold start racing the
  verification timeout); re-querying `--status` immediately afterward
  self-corrected. Not a defect in this milestone's own code.
