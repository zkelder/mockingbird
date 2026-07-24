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
contract also supports a display name, port, declared provider, image bounds,
pairing-code lifetime, and preview-viewer cap. It never accepts a command,
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

The Node advertises opaque camera IDs and sanitized display metadata. Its
synthetic provider exists only for automated tests. V4L2 and Raspberry Pi camera
providers report **Setup required** when their optional local runtime is absent;
the Node never installs a dependency, driver, FFmpeg, or model and never runs a
user-provided command.

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
