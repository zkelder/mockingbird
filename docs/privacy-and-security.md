# Privacy & Security

An honest description of MockingBird 1.0's privacy and security posture. It is
not a guarantee of perfect security. Vulnerability reporting is in
[SECURITY.md](../SECURITY.md); platform scope is in
[support-matrix.md](support-matrix.md). The detailed network audit behind this
page is [local-only-privacy-closure-v1-report.md](local-only-privacy-closure-v1-report.md).

## Local Only operation

MockingBird runs entirely on your own computer. Everyday use needs **no
internet access, no account with anyone, and no MockingBird-operated service**.
The core workflows (sign-in, cameras, observing, Review Queue, Bird Log,
detection, species suggestion, backup/restore, retention, Camera Node) were
accepted in an operating-system network namespace with **no internet route at
all**, and they passed. There is **no telemetry, analytics, crash reporting,
update check, or licence check**; an automated test fails if an analytics or
telemetry dependency is ever declared.

## What contacts the network, and only when

| Activity | Destination | When |
|---|---|---|
| Your cameras, Camera Node, ONVIF discovery, RTSP | Devices on **your own network** (a Camera Node may also be paired over a non-LAN address **you** chose) | The core function, when you configure and start it. ONVIF discovery refuses public addresses. |
| Weather for your Place | Open-Meteo (`api.open-meteo.com`), sends only your coordinates rounded to 4 decimals (about 11 km) | **Off by default.** Only after you turn it on; failure just shows "unavailable". Open-Meteo data is CC BY 4.0. |
| iNaturalist taxonomy lookup | iNaturalist API, sends a species name only | Only when you work the iNaturalist export workflow. Other exports are pure local file generation. |
| Still-image URL source | The URL **you** enter (public hosts allowed; loopback, link-local and metadata addresses blocked) | Only on an explicit preview/monitor action. |
| Other devices opening MockingBird | Your LAN / private overlay | **Off by default**; only if you start with `--allow-network`. |
| Model files | **None.** MegaDetector v5a and BioCLIP 2 ship in the Windows ZIP and never download | Never at runtime. A source checkout needs you to supply them ([developer-setup.md](developer-setup.md)). |
| BirdNET (optional, source checkout only) | `pip` downloads from PyPI **when you** install it | Once, by you. At runtime it needs no network. |

## Remote access

MockingBird serves **plain HTTP** and, by default, answers only the computer it
runs on. Signing in is always required, including when network access is
enabled.

- Reach it from other devices only over a **private overlay network you
  control** (for example Tailscale/WireGuard) or a Wi-Fi you trust.
- **Never forward a router port** to the internet; that would expose an
  unencrypted login to everyone. MockingBird provides no cloud relay and does
  not terminate TLS itself.
- MockingBird has local multi-user sign-in with an Administrator, login
  rate limiting, and authenticated media. It is designed as a home/LAN
  appliance, **not an internet-facing service**.

## Credentials and local data

- Camera (RTSP/ONVIF) credentials and Camera Node pairing secrets are stored
  **only in your local MockingBird database**, masked in the UI and redacted from
  status, logs and diagnostics. They are **not encrypted at rest** in that
  database. Protect the computer (disk encryption, OS account) as you would for
  anything holding those credentials.
- Your data lives in the local data folder (`%LOCALAPPDATA%\MockingBird` on
  Windows by default), apart from the application folder. **Backups contain
  everything** -- cameras and their credentials, Zones, reviewed history and
  media -- so store them as carefully as the live data.
- Generated media, datasets, exports and model files stay under local paths.

## Cameras, audio, and your responsibility

MockingBird observes **outdoor** wildlife. You are responsible for where you
point cameras and microphones and for the laws and expectations that apply
there. Audio capture needs **separate, explicit consent** and is never inherited
from video; it is off unless you set it up. MockingBird does not record
continuous video, and does not identify individual people.

**Privacy Zones and Ignore Zones are trigger-level exclusions.** They stop a
marked area from triggering or contributing evidence. They are **not a promise
that every retained frame has that area's pixels redacted.** Do not rely on
them to blank out a private area.

## Support bundles

`python -m mockingbird support-bundle` writes one `.zip` containing Doctor's
check results, a redacted tail of the log, and version facts. It **never
includes media, camera passwords, pairing secrets or auth tokens.** It **does
include local folder paths by default**, which can contain your Windows user
name. Use `--no-local-paths` to remove the database path from the manifest;
paths inside Doctor's per-check details may still appear, so **read the file
before posting it publicly**, or send it privately.

## Exports

Reviewed-only exports (dataset, Camtrap DP, Darwin Core, iNaturalist CSV)
are files **you** create and submit yourself; MockingBird never uploads them.
They can contain your place's coordinates, timestamps and (for media bundles)
images. Review the file before sharing. Machine suggestions and human-confirmed
rows stay distinct, and eBird submission is excluded by policy.

## Known limits

- No TLS or encryption at rest inside MockingBird.
- Windows release files are **not code-signed**; verify the SHA-256 checksum of
  what you download ([using-mockingbird.md](using-mockingbird.md#1-download-and-verify)).
- Denial-of-service against the local process is out of scope.
- BirdNET weights are non-commercially licensed; see
  [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
