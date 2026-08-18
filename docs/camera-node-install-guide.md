# Installing a MockingBird Camera Node

This is the normal-user path for installing MockingBird Camera Node as a
supervised, boot-persistent service on a Raspberry Pi or similar Linux
device with an attached camera. It assumes basic comfort with a terminal
(SSH into the device, run a command) but no Python packaging or systemd
expertise. See [camera-node-boundary-design.md](camera-node-boundary-design.md)
for what the Node is and is not, and
[camera-node-installer-design.md](camera-node-installer-design.md) for the
full technical contract this guide follows. Just want to try the Node
without installing a service? The manual `python -m mockingbird_node` path
in that document still works unchanged.

## Supported OS/hardware

Validated against Raspberry Pi OS (Debian 13 "trixie", `aarch64`) on a
Raspberry Pi 4 Model B -- this project's reference device. A generic
Debian-family Linux box works too; without a Pi camera it simply reports
`setup_required` for the PiCamera2 provider rather than failing the whole
install (see "System prerequisites" in the design document). Pi 4 is not an
architectural requirement.

## 1. Obtain the artifact

On a development machine with this repository checked out:

```sh
python3 scripts/build_camera_node_artifact.py dist/camera-node-artifact
```

This produces `dist/camera-node-artifact/` containing the wheel,
`requirements.txt`, `camera-node.env.example`, `manifest.json`, and
`SHA256SUMS`. `manifest.json`'s `provenance.git_commit` records exactly
which commit produced it. Copy that whole directory to the Node device
through any transport you trust -- `scp`, a USB drive, a shared folder.
There is no remote-fetch or `curl | sh` path; the installer only ever acts
on files already present on the device.

```sh
scp -r dist/camera-node-artifact/ your-node-device:/home/you/camera-node-artifact
```

## 2. Install

On the Node device itself, as root:

```sh
sudo python3 scripts/install_camera_node.py /home/you/camera-node-artifact
```

(If you copied only the artifact directory, not the whole repository, copy
`scripts/install_camera_node.py` alongside it too -- it needs nothing else
from the repository at install time.)

This installs missing system prerequisites, creates a dedicated
`mockingbird-node` service account, builds a virtual environment, installs
the package, writes a starting configuration (only if one does not already
exist), installs and enables the `systemd` unit, starts the service, and
prints a step-by-step summary ending in a live health check. It is safe to
re-run with the same or a newer artifact -- see "Updating," below.

## 3. Configure

The installed configuration lives at `/etc/mockingbird-camera-node/node.env`
(an `EnvironmentFile=`-format file: `KEY=value`, one per line). Edit it, then:

```sh
sudo systemctl restart mockingbird-camera-node
```

The default configuration binds `0.0.0.0` (reachable from your local
network -- required for the MockingBird host to reach it) with the
providers `picamera2,v4l2`. See "Bind address / trust boundary" in the
design document for what `0.0.0.0` actually means for who can reach the
Node. If this device sits on a shared or untrusted network, set
`MOCKINGBIRD_NODE_BIND=127.0.0.1` and reach the Node only through an SSH
tunnel.

## 4. Start/check

```sh
sudo systemctl status mockingbird-camera-node
```

`Active: active (running)` and `enabled` (survives reboot) confirm the
service is up. A quick local health probe:

```sh
curl http://127.0.0.1:8787/node/v1/health
```

Or ask the installer itself for a full report (read-only, makes no
changes):

```sh
sudo python3 scripts/install_camera_node.py --status
```

## 5. Retrieve the pairing code

```sh
sudo journalctl -u mockingbird-camera-node -n 20
```

Look for `MockingBird Camera Node pairing code: ...` and its expiry. This
line only appears once, right after the service (re)starts -- if you need a
fresh code, restart the service (`sudo systemctl restart
mockingbird-camera-node`), which generates a new one and invalidates the
old (already-expired or unused) one. **An already-completed pairing is
unaffected by a restart** -- only an outstanding, not-yet-used code is
replaced. Enter the printed LAN IP address and this code in MockingBird's
**Add Camera -> MockingBird Camera Node** flow.

## 6. Inspect health

```sh
curl http://127.0.0.1:8787/node/v1/health
```

reports `status`, `camera_count`, `available_camera_count`, and whether
pairing is still required. `sudo python3 scripts/install_camera_node.py
--status` reports the same, plus which build is installed and whether a
rollback target exists.

## 7. Inspect logs

```sh
sudo journalctl -u mockingbird-camera-node -f
```

follows the live log. A normal startup shows a line naming the bind
address/port, configured providers, and whether pairing state was already
loaded -- deterministic and independent of log verbosity. Raise verbosity
temporarily for more detail (per-request access logs) by setting
`MOCKINGBIRD_NODE_LOG_LEVEL=info` in `node.env` and restarting; the default
(`warning`) is intentionally conservative. No credential or pairing digest
ever appears in the log -- only the pairing code itself, by design.

## 8. Reboot safely

```sh
sudo reboot
```

The service starts automatically after `network-online.target` is reached
and reconnects to the paired MockingBird host without any manual step or
re-pairing.

## 9. Updating

Build a new artifact from a newer commit (step 1), copy it to the device,
and re-run the installer:

```sh
sudo python3 scripts/install_camera_node.py /home/you/new-camera-node-artifact
```

Your `node.env` and paired credential state are never touched by an update
-- only the installed package itself changes. Exactly one prior version is
retained automatically.

## 10. Recovering from a failed service/update

```sh
sudo python3 scripts/install_camera_node.py --rollback
```

swaps back to the previously installed version and restarts. It refuses
clearly if no prior version is available (a first-ever install has nothing
to roll back to). Configuration and pairing state are unaffected either way.

## 11. Distinguishing provider setup failure from host connectivity failure

- **`curl http://127.0.0.1:8787/node/v1/health` fails on the Node device
  itself** (connection refused, or the command above shows the service
  inactive): the Node process itself is not running -- check `sudo
  systemctl status mockingbird-camera-node` and `sudo journalctl -u
  mockingbird-camera-node` for why (a configuration error prints one clear
  `Camera Node configuration error: ...` line and the service will not stay
  running).
- **The health check above succeeds, but `camera_count`/
  `available_camera_count` show no usable camera**: this is a *provider*
  problem, local to the Node -- an unsupported/disconnected camera, or a
  missing optional system package (`sudo python3
  scripts/install_camera_node.py /home/you/camera-node-artifact` reports
  each optional prerequisite's install outcome; re-running it is safe and
  will retry any that failed). The Node's own HTTP surface is healthy.
- **The Node is locally healthy but MockingBird (the host) cannot pair with
  or reach it**: this is a *network/connectivity* problem between the two
  devices, not a Node or provider problem -- confirm both are on the same
  LAN, the printed IP address is correct and reachable
  (`curl http://<node-ip>:8787/node/v1/health` **from the host machine**,
  not the Node itself), and that `MOCKINGBIRD_NODE_BIND` is not set to
  `127.0.0.1` (which would make the Node unreachable from any other
  device -- see "Configure," above).

## Advanced diagnostics

- Full read-only report: `sudo python3 scripts/install_camera_node.py --status`
- Rendered systemd unit: `systemctl cat mockingbird-camera-node`
- Every environment variable the running service actually loaded:
  `systemctl show mockingbird-camera-node -p EnvironmentFiles`, then
  inspect `/etc/mockingbird-camera-node/node.env` directly (root only --
  this is deliberate, see "Configuration paths" in the design document).
- Boot-time capture readiness: `journalctl -u mockingbird-camera-node -b`
  shows this boot's log from the very start, including `libcamera`'s own
  pipeline-handler discovery messages.
