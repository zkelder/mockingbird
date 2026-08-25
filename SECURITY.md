# Security Policy

MockingBird is local-first software: for most users, the whole product
runs on one machine on their own network, with no MockingBird-operated
cloud service in the loop. That does not make security reports less
important -- MockingBird still handles camera credentials, local network
access, and a locally-exposed web application, and we want to know about
problems quickly and fix them responsibly.

## Supported versions

MockingBird is pre-1.0 software. Until a stable 1.0 release, only the
latest commit on the `main` branch (and the most recent tagged release, if
one exists) is supported with security fixes. There is no long-term-support
branch yet.

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
- Missing security hardening that MockingBird already documents as not yet
  implemented (see `docs/roadmap.md`, "Security / release questions") --
  we would rather you tell us those are still missing than treat a
  duplicate report as new.

## What to expect

This project does not currently have a dedicated security team or a formal
SLA. As a good-faith target: an acknowledgment within a few days, and an
honest update on severity/next steps once the report has been reviewed.
Credit in the eventual fix's release notes is offered, and welcome, unless
you'd rather stay anonymous.
