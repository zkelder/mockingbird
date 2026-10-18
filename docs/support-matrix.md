# MockingBird 1.0 Support & Compatibility Matrix

This is the **one canonical statement** of what MockingBird 1.0 supports. Every
other document (README, [using-mockingbird.md](using-mockingbird.md),
[camera-node-install-guide.md](camera-node-install-guide.md), SECURITY.md)
points here instead of making its own support claim. If another document
disagrees with this one, this one is right and the other is a bug -- please
report it.

## How to read the evidence labels

| Label | Meaning |
|---|---|
| **Supported (validated)** | Built, run, and accepted on real hardware of this kind, repeatedly. This is the release path. |
| **Source/developer path** | Works from a source checkout and is exercised by automated tests, but has no packaged download and no real-hardware acceptance. Use at your own risk. |
| **Structurally compatible** | The code has no known reason it would not work (for example a cross-platform library), but nothing has been run on it. Not a support claim. |
| **Unvalidated / unsupported** | No evidence either way, or known not to work. Not part of 1.0. |

A dependency being *able* to run somewhere is never treated as MockingBird
being validated there.

## Host computer (runs MockingBird, stores your data)

| Platform | 1.0 status | Evidence and caveats |
|---|---|---|
| **Windows 10, 64-bit (x64)** | **Supported (validated)** -- the only supported 1.0 Host. | The packaged `MockingBird-windows-x64.zip` was built and accepted on real hardware: Windows 10 Pro `10.0.19045`, NVIDIA GeForce RTX 4060 Ti. |
| **Windows 11, 64-bit (x64)** | **Expected to work; not separately validated.** | No Windows 11 machine appears in the acceptance evidence. The same x64 Windows packaging applies, but this project does not claim a Windows 11 test it has not run. |
| Windows on ARM, 32-bit Windows | **Unsupported.** | The package is x64 only. |
| **Linux** | **Source/developer path only. No packaged 1.0 Linux Host.** | `./start-mockingbird.sh` / `python -m mockingbird` from a checkout. Automated tests run on Linux in CI. No Linux hardware acceptance of the product as a Host has been performed. Linux is **not** equivalent to Windows for 1.0. (The Camera Node, a separate component, does run on Linux -- see below.) |
| **macOS** | **Unvalidated; not part of 1.0.** | Nothing has been run on a Mac. Microphone capture for bird-sound identification is known not to work on macOS and says so. |

The Windows package is a **ZIP archive you unpack**, not an installer. There is
no MSI/EXE installer, no Start-menu entry and no uninstaller (see
[using-mockingbird.md](using-mockingbird.md)). It is **not code-signed**, so
Windows SmartScreen will warn on first run.

No minimum NVIDIA driver version, RAM size, or disk size has been measured and
recorded by this project, so none is stated. The validated machine is the only
data point.

## Accelerators

| Accelerator | Wildlife detection (finds the animal) | Species suggestion (BioCLIP 2) | Bird-sound ID (BirdNET, optional) |
|---|---|---|---|
| **NVIDIA GPU (CUDA)** | **Required for live detection. Supported (validated)** on Windows with a current NVIDIA driver; the package carries the CUDA/cuDNN runtime. Only an RTX 4060 Ti has been tested. | Runs on the CPU by design (no GPU needed). | Runs on the CPU by design. |
| **CPU only** (no supported NVIDIA GPU) | **Live detection is deliberately unavailable** -- **Start observing** says so rather than silently running degraded. Review, Bird Log, import, exports, backup and restore all still work. | Supported on any CPU. | Supported on any CPU (when set up). |
| **AMD GPU** | **Not supported.** Not tested. | n/a (CPU) | n/a (CPU) |
| **Apple Silicon** | **Not supported.** Not tested. | n/a | n/a |

The detector is **MegaDetector v5a (ONNX)**; species suggestions come from
**BioCLIP 2**. Both are bundled in the official Windows package (see
[Models](#models-and-what-is-bundled) below). Species identification is
**bird-only** in 1.0; the detector and review model are wildlife-wide.

## Ways to bring in a camera or media

| Path | 1.0 status | Notes |
|---|---|---|
| **MockingBird Camera Node** (paired, on your LAN) | **Supported (validated)** on the reference hardware. | Reference device: **Raspberry Pi 4 Model B** with a CSI camera, Raspberry Pi OS (Debian 13 "trixie", aarch64). Install, reboot, upgrade, replacement/reprovision and recovery were tested end to end on that device. Other Debian-family Linux devices (for example with a USB camera) are **structurally compatible but unvalidated**. The Pi is *reference hardware*, not the product's identity. Camera Node runs the full Observation Engine and is **not** subject to the two-stream limit below. |
| **Network camera over RTSP** (`rtsp://`) | **Supported**, needs a system `ffmpeg` on the PATH (not bundled). | `rtsps://` (encrypted RTSP) is **refused with an explanation**, never silently downgraded to plain RTSP. Setup runs a bounded live probe only when you explicitly ask. |
| **ONVIF** | **Supported for LAN discovery and configuration** of host, port and credentials, which then feeds the same RTSP path. | Discovery refuses public (non-LAN) addresses. Camera-by-camera behavior varies; only the RTSP result matters for observing. |
| **Local USB / built-in camera on the Host** | **Supported where the Host exposes it** (Windows DirectShow; Linux video device), needs `ffmpeg`. | Real mid-session camera acceptance of this path was limited; treat as the legacy local-camera path (see limits below). |
| **Still-image URL** | **Supported** as an explicit snapshot source. | URLs are fetched only when you preview or the snapshot monitor runs; loopback/link-local/metadata addresses are blocked. |
| **Import: recorded video, images, folder / trail-cam** | **Supported** (import-only, no live camera). Video import needs `ffmpeg`. | Imported media is evidence; offline capture time never counts as live monitoring coverage. |
| **Webhook (metadata only)** | **Supported as untrusted evidence only.** | No anonymous ingest. External labels stay evidence until you confirm. |
| **Home Assistant, Frigate, Blue Iris, Scrypted, cloud cameras, other providers** | **Not part of 1.0.** | No integration exists. |

### Concurrency limits that actually apply (as of this milestone)

- **Legacy local-camera monitoring (RTSP, local USB, Windows DirectShow):** at
  most **2 armed Streams at a time** on one Host
  (`DEFAULT_MAX_CONCURRENT_STREAMS = 2` in
  `monitoring/durable_supervisor.py`). A third armed Stream shows **"Waiting for
  capacity"** and starts when a slot frees; after five minutes waiting it raises
  an Observatory Health alert.
- **Backend live-preview slots (same legacy cameras):** also **2 at a time**,
  counted **independently** of the monitoring limit, so a Host can briefly hold
  two monitors *and* two previews.
- **Camera Node Streams are exempt from both.** Each Node Stream is its own
  bounded Observation Engine session and is never counted against either limit.
- These are documented 1.0 limits, **not hardware throughput measurements**.
  No claim is made about how many cameras a given PC can sustain. Details:
  [runtime-map.md](runtime-map.md#legacy-local-camera-concurrency-limit).

## Multi-camera

Supported for **one observatory / one Place**, within the acquisition limits
above. **Multi-site, multi-observatory, fleet management and a dynamic local
camera scheduler are not part of 1.0.** Overlapping or adjacent cameras
produce separate Streams; Review and Today can filter and group by camera.

## Remote access

MockingBird serves plain HTTP on the Host and answers only that computer unless
you start it with `--host 0.0.0.0 --allow-network`. Sign-in is always required.

- **Supported way to reach it from elsewhere:** a private overlay network
  between your own devices (for example Tailscale or another WireGuard-based
  tool). See [using-mockingbird.md](using-mockingbird.md#use-mockingbird-away-from-home).
- **Not supported:** forwarding a router port to the public internet; any
  MockingBird-operated cloud relay (none exists); a hosted service; TLS
  termination inside MockingBird.
- **Phone:** works in a phone browser and can be "added to home screen". There
  is **no native mobile app and no background push notification** in 1.0.

## Models and what is bundled

| Component | Role | In the official Windows ZIP? | License |
|---|---|---|---|
| MegaDetector v5a (ONNX) | Wildlife detection | **Yes**, SHA-256 verified at build. | MIT (copyright Microsoft Corporation) |
| BioCLIP 2 (`imageomics/bioclip-2` 1.0.0) | Species suggestions (provisional) | **Yes**, with its runtime. | MIT (model card) |
| ONNX Runtime GPU + NVIDIA CUDA/cuDNN | Run the detector | **Yes** | onnxruntime MIT; NVIDIA libraries under NVIDIA's own terms |
| **BirdNET** (`birdnetlib` + GLOBAL_6K_V2.4 weights) | Optional bird-sound ID | **No. Never bundled.** | Code Apache-2.0; **model weights CC BY-NC-SA 4.0 (NonCommercial)** |
| FFmpeg | RTSP, USB, video import | **No `ffmpeg` executable is bundled.** (The bundled OpenCV wheel carries its own FFmpeg libraries under its shipped `LICENSE-3RD-PARTY.txt`; MockingBird does not use them for camera or video-import decoding.) | Whatever your own ffmpeg distribution uses |

Model **suggestions are always provisional**; only your own confirmation or
correction becomes reviewed truth. A "development checkout" must supply its own
model files; see [developer-setup.md](developer-setup.md).

## Acoustics (optional)

Entirely optional; everything else works without it. Because the BirdNET model
weights are licensed non-commercially and are not separable from the
`birdnetlib` wheel, **official MockingBird artifacts never contain them**.

| Path | 1.0 status |
|---|---|
| Windows ZIP | **No supported add-on route.** The packaged runtime has no `pip`, and its interpreter is sealed to its own `site-packages`. Enabling BirdNET on the ZIP is **not a supported 1.0 path.** |
| Source checkout (Windows or Linux) | **Source/developer path:** `pip install -e ".[classifier-birdnet]"` in your own virtual environment, which downloads `birdnetlib` and the weights directly from PyPI under upstream's terms. Requires a microphone/audio source and `ffmpeg`. |
| macOS microphone capture | Does not work; says so. |

Using BirdNET is between you and its license. Whether a private user's
on-device use could be affected because the surrounding project also accepts
donations or paid support is a **genuinely unresolved legal question** this
project does not answer -- see [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md).
This is not legal advice.

## What 1.0 deliberately does not do

- Not surveillance/NVR software: no recording archive, no person tracking or
  identification, no security alerts.
- No cloud accounts, telemetry, or MockingBird-operated service.
- No native mobile app, background push, multi-site/fleet, or sensors/MQTT.
- No third-party ecosystem integrations (Home Assistant, Frigate, Blue Iris,
  Scrypted). Ecological export exists for **iNaturalist CSV, Darwin Core and
  Camtrap DP** files you submit yourself; eBird is excluded by policy.
- No claim that a model suggestion is a species identification until you
  confirm it. No claim that Privacy Zones redact pixels
  ([privacy-ignore-zone-contract.md](privacy-ignore-zone-contract.md)).
- No packaged Linux or macOS Host.

## Directly validated vs. structurally supported (summary)

| Directly validated on real hardware | Structurally supported only |
|---|---|
| Windows 10 x64 Host + RTX 4060 Ti, packaged ZIP | Windows 11 Host |
| Raspberry Pi 4 Camera Node (install/reboot/upgrade/reprovision) | Other Debian devices as Camera Node |
| MDv5a + BioCLIP 2 fully offline | Linux/macOS as a Host |
| Backup, restore, migration across schema versions | AMD / Apple Silicon accelerators |
| Camera Node over LAN | RTSP/ONVIF/USB cameras: protocol-tested, with limited mid-session camera acceptance |
| | BirdNET on any platform (tested from a source checkout, not as a packaged product) |

Source-version note: the current repository source version string is `0.1.0`.
The first public release is **1.0**; the version bump, final artifacts and tag
are performed during release hardening, not by this document.
