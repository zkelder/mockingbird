# MockingBird

MockingBird is an open, local-first, hardware-agnostic, evidence-backed
**ecosystem observatory**. It helps you notice, understand, confirm, and
remember the wildlife around a place -- bird-first, but built for wildlife in
general. Cameras, detectors, and classifiers are the instruments; the product
is a trustworthy, growing record of what actually visits your place.

It runs on your own computer. No account, no cloud service, no telemetry.

> **Not surveillance software.** MockingBird is for nature observation. It is
> not an NVR, a security-alert system, or a person-tracking tool, and it keeps
> no continuous recording archive. See [Product doctrine](docs/product-doctrine.md).

**Observe → Discover → Understand → Confirm → Remember → Improve**

| | |
|---|---|
| **Observe** | Connect an outdoor camera (or import recorded media), draw Zones that matter, and start observing. |
| **Discover** | MockingBird notices candidate animal Visits and shows the best evidence. |
| **Understand** | Today, Place Story, Bird Log, and Zone/hour patterns build context over time. |
| **Confirm** | *You* confirm or correct what a Visit is. Model output stays a labeled **suggestion** until you do. |
| **Remember** | Reviewed history is local, durable, backed up, and exportable. |
| **Improve** | Your corrections are the dataset-grade truth that analytics, exports, and future models rely on. |

## What you can trust

- **Suggestions are provisional.** Detector output and species guesses
  (MegaDetector v5a, BioCLIP 2, optional BirdNET) are evidence. Only a human
  confirmation or correction becomes reviewed truth, and Bird Log, analytics,
  and reviewed-only exports derive only from that truth. "Unknown" is a valid
  answer.
- **Local first.** Detection and species suggestion run on your computer. Data
  stays on disk you control. The cloud is optional and never required; see
  [Privacy & security](docs/privacy-and-security.md).
- **Honest about limits.** If your hardware can't run live detection, or a
  model isn't available, MockingBird says so instead of quietly degrading.
- **Hardware-agnostic by design.** A Raspberry Pi 4 is the *validated
  reference* Camera Node, not the product's identity. Network (RTSP/ONVIF),
  USB, still-image, and imported media are all first-class sources.

## What 1.0 supports

The first public release is **1.0**. Its supported scope is stated in one place:
**[Support & compatibility matrix](docs/support-matrix.md)**. In short:

- **Host:** native **Windows 10 x64** is the supported, hardware-validated Host
  (Windows 11 expected, not separately validated), as an unpack-and-run ZIP
  (not an installer, not code-signed).
- **Live wildlife detection needs a supported NVIDIA GPU.** Without one,
  review, Bird Log, import, exports, and backup still work.
- **Cameras:** MockingBird Camera Node (reference: Raspberry Pi 4), RTSP/ONVIF
  network cameras, local USB, still-image URLs, and import-only media. Legacy
  local cameras are limited to two armed Streams at a time; Camera Node is not.
- **One observatory / one Place**, multiple cameras. No multi-site, fleet
  management, native mobile app, background push, or MockingBird cloud relay.
- **Linux / macOS** are source-checkout only -- there is no packaged Linux or
  macOS Host in 1.0.
- **Optional bird-sound identification (BirdNET)** is never bundled (its model
  weights are non-commercial licensed) and has no supported add-on route for the
  Windows ZIP.

## Get started

- **Install and use MockingBird (Windows):** [Using MockingBird](docs/using-mockingbird.md)
  -- download, verify, unpack, first-run setup, add a camera, observe, review,
  back up, update.
- **Add a Camera Node** (Raspberry Pi or similar): [Camera Node install guide](docs/camera-node-install-guide.md).
- **Something wrong?** [Troubleshooting & support](docs/troubleshooting.md) and
  [SUPPORT.md](SUPPORT.md).
- **Run from source / contribute:** [Developer setup](docs/developer-setup.md)
  and [CONTRIBUTING.md](CONTRIBUTING.md).

## Backup, recovery, and updates

MockingBird keeps your data in its own local data folder (normally
`%LOCALAPPDATA%\MockingBird` on Windows), separate from the application folder.
Verified backups, rollback-safe restore, an automatic pre-upgrade backup, Doctor
health checks, and a redacted support bundle are built in. Start with
[Using MockingBird -- Backup and restore](docs/using-mockingbird.md#backup-and-restore)
and [Troubleshooting](docs/troubleshooting.md).

## Privacy and security

Local Only operation, exactly which optional features contact the network and
when, remote-access assumptions, credential handling, and what Privacy Zones do
and do not guarantee: [Privacy & security](docs/privacy-and-security.md).
Report vulnerabilities privately per [SECURITY.md](SECURITY.md).

## Documentation map

- [docs/using-mockingbird.md](docs/using-mockingbird.md): normal-user guide
- [docs/support-matrix.md](docs/support-matrix.md): **canonical** 1.0 support and compatibility statement
- [docs/troubleshooting.md](docs/troubleshooting.md): troubleshooting, Doctor, support bundle, how to file an issue
- [docs/privacy-and-security.md](docs/privacy-and-security.md): privacy and security posture
- [docs/camera-node-install-guide.md](docs/camera-node-install-guide.md): Camera Node install
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md): bundled and deliberately-not-bundled components and licenses
- [docs/developer-setup.md](docs/developer-setup.md): source checkout, optional runtimes, tests
- [docs/product-doctrine.md](docs/product-doctrine.md): product identity and truth model
- [docs/architecture.md](docs/architecture.md), [docs/runtime-map.md](docs/runtime-map.md), [docs/glossary.md](docs/glossary.md): design
- [docs/roadmap.md](docs/roadmap.md): current priorities
- [docs/owner-release-checklist.md](docs/owner-release-checklist.md): what the owner must do before publishing
- [AGENTS.md](AGENTS.md): working rules and conditional design-document routing for contributors and coding agents

Focused feature contracts remain under `docs/`.

## Status

The repository is a **pre-release** of the first public release (**1.0**),
pending final release hardening. The source tree currently reports version
`0.1.0`; the 1.0 version bump, final artifacts, and release tag are performed
during release hardening and are not yet done.

## License

MockingBird's own source code is licensed under the [MIT License](LICENSE).

This covers MockingBird's own code only. Third-party components MockingBird
redistributes or depends on -- including the bundled MDv5a and BioCLIP-2
model weights, and the optional BirdNET bird-sound identification feature
MockingBird deliberately does **not** bundle -- are licensed under their own
separate terms, not necessarily MIT, and remain governed by those terms.
See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the complete
account of what is bundled, what is not, and under what license.
