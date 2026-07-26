# Camera Node boundary

MockingBird Camera Node is a small local-LAN edge adapter for a Raspberry Pi or
ordinary Linux device with a locally attached camera. It is not a second
MockingBird application. The main application continues to own Sources,
Streams, Zones, monitoring policy, activity sessions, evidence, Visits,
review/correction truth, retention, backup, and analytics.

## Manual startup

The Node has no service installer or automatic updates. Start it manually on
the edge device after installing the existing project package:

```sh
python -m mockingbird_node
```

The launcher prints a short-lived one-time pairing code only to that local
console. The default bind address is loopback. Set `MOCKINGBIRD_NODE_BIND=0.0.0.0`
only when the Node must be reachable from the local LAN. The compact environment
contract also supports a display name, port, explicit provider allowlist
(`v4l2`, `picamera2`, or both), image bounds, pairing-code lifetime, and
preview-viewer cap. Separate optional evidence-still bounds may be higher than
the monitoring bounds for one explicit activity capture; they cannot be lower
and do not change normal monitoring snapshots. The default tries only locally supported production
providers; synthetic is test-only. It never accepts a command,
filesystem path, cloud account, or remote-management setting.

## Pairing and network boundary

In Add Camera, a user explicitly enters a local HTTP/HTTPS Node IP address and
the one-time code. The main application checks the Node, exchanges the code for
a random local credential, and stores that credential only in local Source
provider configuration. Read, status, setup-review, health, preview-impact, and
revision-history APIs expose only configured/not-configured state. Codes and
credentials never appear in URLs, logs, alerts, or API responses.

The client fixes every `/node/v1/` endpoint itself, accepts no browser-supplied
endpoint path, permits only private/loopback/link-local IP addresses, follows no
redirects, uses bounded requests and responses, and performs no LAN/mDNS scan.
Re-pairing and revocation are explicit. Revoking access preserves the existing
Source, Stream, Zones, activity, evidence, Visits, reviews, and corrections.

## Provider and frame boundary

The Node advertises provider-scoped opaque camera IDs and sanitized display
metadata. Its synthetic provider exists only for automated tests. V4L2 uses an
already-installed local capture runtime for one bounded USB/Linux still;
optional PiCamera2 does the same only when its installed Pi camera stack is
available. Either reports **Setup required** or unavailable when its local
dependency, device, permission, or usable frame is absent. The Node never
installs a dependency or driver, runs FFmpeg, accepts a device path over HTTP,
or runs a user-provided command. Camera handles are owned for one bounded
capture and released afterward.

Authenticated snapshots are bounded JPEG responses. Add Camera may request one
explicit transient JPEG after pairing and before a Zone is drawn; it is returned
directly to that browser and never becomes MediaAsset, evidence, or truth.
Running live/monitoring sessions use the existing app-owned in-memory
live-frame cache. Bounded monitoring consumes the same Source → Stream → Zone
→ activity/evidence path used by other backend-owned live Sources. Monitoring
remains default-off and explicit. A Node/API reachability failure, rejected
credential, unavailable selected camera, or unusable image stops that runtime
session and enters the existing bounded retry/restart path with a redacted,
actionable Camera Health message. Privacy/Ignore Zones remain authoritative,
and no Node action can create ReviewLabels, Bird Log truth, classifier state,
Journal truth, or cloud uploads.

MJPEG, WebRTC, HLS, audio, recording, ESP32-CAM, ONVIF, automatic discovery,
remote shell/OS administration, service installation, updates, and cloud relay
are deliberately deferred.

## Capture-profile contract

Camera Nodes may advertise a small set of provider-defined, opaque capture
profiles for a selected camera. A profile reports only safe capability metadata:
an opaque ID, allowed purpose (`monitoring`, `preview`, or `evidence`), output
dimensions, JPEG and byte bounds, warm versus reconfiguration-required capture
class, alignment-group identity, orientation/mirror state, and whether the
field of view is known to match another profile. It never exposes a device path,
sensor-mode name, driver option, shell command, or arbitrary camera setting.

The desktop stores only the selected opaque monitoring/evidence profile IDs in
the existing local Camera Node provider configuration. It rechecks those IDs
against the Node's current advertisement before asking for a frame. Nodes that
do not advertise profiles remain on the established bounded authenticated
snapshot path; pairing or monitoring is never made dependent on a profile-aware
Node.

An authenticated bounded capture request names one advertised profile ID. The
Node owns one capture at a time for that camera, validates JPEG dimensions and
bytes, and releases/reinitializes its provider safely after an attempted
reconfiguration. It keeps no still on disk. A failed optional PiCamera2 runtime
or a failed evidence capture returns a sanitized state and must not prevent the
normal monitoring profile from resuming. V4L2 and PiCamera2 remain provider
implementations beneath this contract; synthetic remains explicitly test-only.

For a warm dual-stream PiCamera2 pair, the Node evaluates its ordered candidate
profiles once in the background. Each candidate is only `untested`, `testing`,
`accepted`, or rejected by a bounded safe category; a rejected larger candidate
is released before the next candidate is tried. The first accepted pair is
cached for that Node process. Capability output may report those fixed states,
but never allocation text, pipeline details, device paths, or driver settings.
