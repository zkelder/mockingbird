# Security Policy

MockingBird is local-first software: for most users, the whole product
runs on one machine on their own network, with no MockingBird-operated
cloud service in the loop. That does not make security reports less
important -- MockingBird still handles camera credentials, local network
access, and a locally-exposed web application, and we want to know about
problems quickly and fix them responsibly.

## Supported versions

MockingBird does not yet have a track record of tagged releases. Until one
exists, only the latest commit on the `main` branch (and the most recent
tagged release, if one exists) is supported with security fixes. There is
no long-term-support branch yet.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for a security report.

Use GitHub's private vulnerability reporting instead:
[github.com/zkelder/mockingbird/security/advisories/new](https://github.com/zkelder/mockingbird/security/advisories/new).
This opens a private conversation with the maintainer that is not visible
to the public until a fix is ready.

If you cannot use that feature for some reason, open a normal GitHub issue
asking for a private way to reach the maintainer -- without describing the
vulnerability itself -- and we'll follow up.

Please include, where relevant:

- what you found and where (file/endpoint/component);
- the impact you believe it has;
- steps to reproduce, or a proof of concept;
- whether it requires local network access, a paired device, or remote
  access to reproduce.

## What's in scope

- The MockingBird Host application (`src/mockingbird/`) and its local web
  UI/API.
- The MockingBird Camera Node companion device software
  (`src/mockingbird_node/`).
- The release packaging/build scripts (`scripts/build_local_product.py`,
  `scripts/build_camera_node_artifact.py`, and related tooling) -- for
  example, a way to make a built release artifact silently include or
  execute something it should not.

Vulnerabilities in third-party dependencies MockingBird uses are useful to
know about too, but please report those to the dependency's own project
when the issue is in their code rather than in how MockingBird uses it.

## What's out of scope

- Reports that require physical access to an already-compromised machine.
- Denial-of-service reports against a purely local, single-user desktop
  process (see "Product boundaries" -- MockingBird is not designed as an
  internet-facing service).
- Security-relevant behavior MockingBird already discloses as a known,
  deliberate current posture rather than an oversight -- we would rather
  you know these are already tracked than treat a duplicate report as new:
  - MockingBird serves plain HTTP by default and does not add TLS itself;
    reaching it from another device is only supported over a private
    network (Tailscale/WireGuard or similar), never a router port forward
    -- see "Use MockingBird away from home" in
    [docs/using-mockingbird.md](docs/using-mockingbird.md).
  - Camera/ONVIF/RTSP credentials are stored only in MockingBird's own
    local database on your machine (never on a MockingBird-operated
    server), but are not encrypted at rest there today -- protect the
    device MockingBird runs on the same way you would any device holding
    those credentials.
  - Privacy Zones exclude marked areas from triggering evidence capture;
    they are not a guarantee that every retained frame has that area's
    pixels redacted.

## What to expect

This project does not currently have a dedicated security team or a formal
SLA. As a good-faith target: an acknowledgment within a few days, and an
honest update on severity/next steps once the report has been reviewed.
Credit in the eventual fix's release notes is offered, and welcome, unless
you'd rather stay anonymous.
