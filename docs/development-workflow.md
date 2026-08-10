# Development Workflow

MockingBird work should stay scoped, product-led, reproducible, and easy to
review. [roadmap.md](roadmap.md) is the current sequencing authority;
[roadmap-history.md](roadmap-history.md) is reference history only.

## Roles

- The user owns product direction, scope approval, and final review.
- The assistant/Codex turns current roadmap work into a task packet, changes
  only the allowed files, and validates in proportion to risk.
- Commits happen only after scope, diff, and validation are clean.

## Standard task packet

Before implementation edits, state:

- roadmap phase
- product flow improved
- why this is next
- files allowed
- non-goals
- validation tier
- implementation requirements when the roadmap/design does not already define
  them

If a task needs a materially different action, dependency, network call,
provider behavior, generated artifact, or destructive operation, update the
scope before taking it.

## Validation tiers

Use the lowest tier that adequately covers the risk. Higher tiers include the
applicable lower-tier checks.

### Tier 0 - docs and scope

For documentation, comments, copy-only, or planning changes:

- inspect the changed-file list and diff
- verify links and referenced files
- check product terminology and current-state accuracy
- confirm the task packet's non-goals and allowed files
- check that doctrine is linked rather than unnecessarily duplicated

### Tier 1 - focused code checks

For small, isolated behavior changes:

- run the closest focused tests
- run the relevant frontend type-check or backend static/lint checks when the
  changed language is covered
- verify no generated/local artifact entered the worktree

### Tier 2 - domain integration and persistence

For API/repository/service changes, data writes, migrations, media handling,
provider boundaries, or backup/restore behavior:

- run focused unit and domain integration tests
- run schema migration and backup compatibility tests when persistence changes
- validate negative paths, side-effect-free reads, and evidence/truth boundaries
- run the frontend build when API shapes or shared product flows change

### Tier 3 - complete non-hardware gate

For cross-cutting product work, lifecycle foundations, release candidates, or
changes with broad blast radius:

- run the complete backend suite
- run frontend type-check and production build
- run the critical hardware-free product smoke flow
- run migration/backup compatibility checks
- run the repository's configured formatting, lint, type, and contract-parity
  checks
- run `python -m mockingbird --check` after the production frontend build when
  runtime/startup behavior is in scope

Tier 3 must not start cameras, workers, providers, model runtimes, or truth
creation merely to report readiness.

### Tier 4 - explicit hardware, failure, and soak validation

For camera bridges, durable activation, field performance, destructive
recovery drills, model/detector candidate promotion decisions, or release
acceptance:

- state the bounded question this field test/trial answers before starting
  (see the field-testing doctrine in [roadmap.md](roadmap.md)); an
  open-ended "leave it running and see what happens" session is not a Tier 4
  plan
- start only explicitly scoped hardware/runtime behavior
- run the relevant Tier 3 gate first
- use bounded fake-clock/fake-adapter checks before real hardware
- run scoped failure-injection and long-run/soak checks
- record environment, duration, representative inputs, product metrics,
  artifacts created, cleanup, and deviations
- for a candidate detector/classifier specifically, require a reproducible
  incumbent comparison on identical data before any promotion decision (see
  "Formal model lifecycle" in [architecture.md](architecture.md))

Tier 4 media, benchmark data, reports, model artifacts, and caches remain under
ignored local paths.

## Change workflow

1. Read the required current-state documents in `AGENTS.md` and the smallest
   conditional design set for the task.
2. Restate the task packet and identify the validation tier.
3. Inspect the current implementation and existing tests before editing.
4. Make the smallest coherent change that completes the scoped outcome.
5. Validate incrementally, then run the full selected tier.
6. Review the changed-file list and diff for unrelated or generated changes.
7. Report changed files, validation performed, and deviations from scope.

## Product-flow validation

When the changed area participates in the main loop, validate the nearest
applicable portion of:

Cameras/Streams -> Zones -> monitoring/evidence -> Review Queue -> explicit
correction -> Bird Log -> reviewed-only Exports.

Provider/status reads remain side-effect free. Media, MotionEvidence,
DetectionProposals, SpeciesSuggestions, and external labels remain evidence.
Explicit correction remains the first dataset-grade truth write.

Useful focused references:

- [source-stream-dev-smoke-checklist.md](source-stream-dev-smoke-checklist.md)
  for Source/Stream provider flows
- [mvp-demo-script.md](mvp-demo-script.md) for the broader local product spine
- [local-mvp-readiness-checklist.md](local-mvp-readiness-checklist.md) for the
  local demo/dev gate
- [single-app-runtime-recovery-design.md](single-app-runtime-recovery-design.md)
  for startup, navigation recovery, schema compatibility, and shutdown
- [local-backup-recovery-design.md](local-backup-recovery-design.md) for verified
  database-and-media backup/restore
- [durable-camera-monitor-lifecycle-design.md](durable-camera-monitor-lifecycle-design.md)
  for default-off durable monitoring and future activation

## Documentation maintenance

Each concept has one preferred home:

- product identity and quick start: `README.md`
- non-negotiable product doctrine: `product-doctrine.md`
- current priorities and sequence: `roadmap.md`
- completed phase summary: `roadmap-history.md`
- domain definitions: `glossary.md`
- current component and data-flow boundaries: `architecture.md`
- agent routing and universal guardrails: `AGENTS.md`
- detailed feature contract: the relevant focused design document

Do not append completed implementation diaries to README, architecture, or the
current roadmap. When work completes, update current-state facts concisely,
move phase detail to history if it remains useful, and keep design documents as
the authoritative detailed contracts.

Prefer links over repeated non-goal inventories. Repeat a guardrail only when
the local task could otherwise cross that boundary. Remove or archive stale
"next likely phase" text when the current roadmap supersedes it.
