# Codex Guardrails

MockingBird is a local-first outdoor video intelligence platform. Video streams are central.

Before implementation work, Codex must read:

- [README.md](README.md)
- [docs/product-doctrine.md](docs/product-doctrine.md)
- [docs/roadmap.md](docs/roadmap.md)
- [docs/glossary.md](docs/glossary.md)
- [docs/architecture.md](docs/architecture.md)

## Core Doctrine

Users connect outdoor camera/video sources, view streams in the app, draw zones, MockingBird analyzes video for animals/outdoor events, creates reviewable visits/events, users correct labels/species, and corrections build dataset exports and analytics over time.

Core product loop:

connect source → view stream → draw zones → analyze outdoor activity → review visits/events → correct labels/species → export datasets and analytics.

Preserve these product concepts:

- Source
- Stream
- Zone
- Event
- Visit
- Detection
- Review/correction
- Dataset export
- Analytics

Source adapters are underneath the product. They normalize media and activity into product-level concepts instead of defining the product.

## Product Drift To Avoid

Do not center MockingBird on:

- Windows USB
- PowerShell
- CLI tools
- ROI wording
- interval analysis
- debug internals
- snapshot loops
- a single camera adapter
- hardware setup as the main product

## Task Packet

Every future implementation task must restate:

- roadmap phase
- product flow improved
- why this is next
- files allowed
- non-goals
- validation tier

## Architecture Guidance

- Build the product model first, adapters later.
- Build stream-first UX assumptions into the API/frontend.
- Treat detections as evidence, not final truth.
- Treat user corrections as dataset-grade labels.
- Keep local-first storage/export assumptions in mind.
- Respect privacy and ignore zones as first-class product concepts when those features are implemented.
- Avoid adapter-specific models leaking into core product models.

## Comment Standard

When implementation code is added later, include clear comments where they help future maintainers understand product intent, domain meaning, non-obvious constraints, or decisions that prevent product drift.

Good comments explain:

- product intent
- domain meaning
- why a model, endpoint, or workflow exists
- non-obvious constraints
- decisions that prevent product drift
- validation assumptions

Avoid comments that merely repeat obvious syntax.

Useful future comment examples:

- Source adapters normalize into Streams/Events rather than defining the product.
- Detection is model evidence, not user-confirmed truth.
- ReviewLabel or equivalent correction models represent dataset-grade user truth.
- Privacy and Ignore zones affect event creation/review behavior.
- Demo data exists to prove the product flow before real camera adapters.

## Validation Expectations

- Prefer tests for implementation work.
- For docs-only changes, validate by checking scope, file list, and product language.
- Every task report should include changed files, validation performed, and deviations from scope.
