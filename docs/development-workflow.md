# Development Workflow

MockingBird work should stay scoped, product-led, and easy to review.

## Roles

- ChatGPT acts as product architect, task writer, and review partner.
- Codex edits files and runs validation.
- The user reviews the diff and test output before commit.
- Commit only after scope and validation are clean.

## Standard Task Packet

Each implementation task should include:

- roadmap phase
- product flow improved
- why this is next
- files allowed
- non-goals
- validation tier
- implementation requirements
- validation commands/report

## Intended Build Order

- Phase 0: product doctrine and repo framing
- Phase 0B: Codex guardrails and development workflow
- Phase 1A: core product API skeleton
- Phase 1B: product contract tests and demo data
- Phase 2: stream-first frontend shell
- Phase 3: local/demo media adapters
- Phase 4: detection pipeline
- Phase 5: bird feeder species review vertical
- Phase 6: broader outdoor intelligence

Camera/source adapters come after the core product model and UI loop. They should normalize into Sources, Streams, Zones, Events, Visits, Detections, Review/corrections, Dataset exports, and Analytics rather than defining the product shape.

For source/stream work around the current external_url path, use
[source-stream-dev-smoke-checklist.md](source-stream-dev-smoke-checklist.md)
as the manual browser/API validation companion to the automated smoke test.

For a full local MVP walkthrough across Dashboard readiness, provider workflows,
Motion Evidence, review/correction, analytics, exports, classifier readiness,
and saved media retention, use
[mvp-demo-script.md](mvp-demo-script.md).

For first-run and sparse-data copy, use
[onboarding-empty-state-polish.md](onboarding-empty-state-polish.md). These
surfaces are read-only guidance and must not run provider actions or create
truth.

Before treating the current app as local MVP demo-ready, use
[local-mvp-readiness-checklist.md](local-mvp-readiness-checklist.md). It is a
local demo/dev gate, not a production release claim.

For product-like launch, reload/navigation recovery, local data compatibility,
and graceful shutdown, use
[single-app-runtime-recovery-design.md](single-app-runtime-recovery-design.md).
Validate the single runtime with `python -m mockingbird --check` after the
frontend production build. This validation must not start camera sessions,
monitoring, providers, workers, or models.

Before durable camera, monitoring, visual-model, or audio lifecycle work, use
[local-backup-recovery-design.md](local-backup-recovery-design.md). Backup and
restore belong on the existing Local Data page and must preserve the database
and managed media as one verified product graph. Restore must verify before
mutation, create a verified pre-restore safety backup, stop process-owned camera
activity, and roll both database and media back if the restored repository
cannot reopen. Backup artifacts remain under ignored local data paths and do
not create or reinterpret evidence, reviewed truth, analytics, or exports.

Keep docs practical and concise. Link to [README.md](../README.md), [docs/product-doctrine.md](product-doctrine.md), [docs/roadmap.md](roadmap.md), [docs/glossary.md](glossary.md), and [docs/architecture.md](architecture.md) instead of duplicating the full doctrine in every file.
