# Codex Guardrails

MockingBird is a local-first outdoor video intelligence platform. Video streams
are central.

## Required reading

Before implementation work, read these current-state documents completely:

- [README.md](README.md)
- [docs/product-doctrine.md](docs/product-doctrine.md)
- [docs/roadmap.md](docs/roadmap.md)
- [docs/glossary.md](docs/glossary.md)
- [docs/architecture.md](docs/architecture.md)

Read only the conditional design documents routed below for the task at hand.
Completed-phase history is available in
[docs/roadmap-history.md](docs/roadmap-history.md) but is not required reading.

## Product invariants

Core product flow:

connect Source -> view Stream -> draw Zones -> analyze outdoor activity ->
review Events/Visits -> correct labels/species -> export datasets and analytics.

Preserve these concepts: Source, Stream, Zone, Event, Visit, Detection,
review/correction, Dataset Export, and Analytics.

- Streams and Zones are the product center. Adapters normalize into product
  concepts; they do not define the product.
- Detections, DetectionProposals, SpeciesSuggestions, MotionEvidence, imported
  media, and external labels are evidence or context, never reviewed truth.
- Explicit user correction creates dataset-grade ReviewLabel truth. Bird Log,
  reviewed analytics, classifier readiness, and reviewed-only exports derive
  from that truth.
- Read/status/preview/dry-run routes are side-effect free unless a task
  explicitly scopes a write. Provider actions and destructive actions are
  explicit and bounded.
- Local-first storage, redacted secrets, Privacy Zones, Ignore Zones, retention,
  backup/recovery, and safe restart behavior are product constraints.
- Generated media, datasets, exports, caches, model artifacts, and checkpoints
  stay under ignored local paths and are never committed.

Do not center the product on Windows USB, PowerShell, CLI tools, ROI wording,
interval analysis, debug internals, snapshot loops, one adapter, or hardware
setup.

## Task packet

Every implementation task must restate before edits:

- roadmap phase
- product flow improved
- why this is next
- files allowed
- non-goals
- validation tier

Follow [docs/development-workflow.md](docs/development-workflow.md) for tier
definitions, validation reporting, and documentation maintenance rules.

### Required implementation operating order

1. Verify the repository root, branch, HEAD/worktree state, and staged state.
2. Read the applicable `AGENTS.md` files.
3. Read [docs/development-workflow.md](docs/development-workflow.md).
4. Read only the smallest conditional-document set routed for the task.
5. Inspect the existing implementation and closest tests.
6. Add a failing focused test before fixing a defect.
7. Implement the smallest complete capability.
8. Run focused validation at the selected tier.
9. Inspect the exact staged diff.
10. Commit without pushing.

### Workspace and instruction boundaries

- The native WSL checkout is authoritative. Stop rather than proceed when the
  repository root is under `/mnt/c`.
- Preserve a dirty worktree unless the user explicitly authorizes the exact
  recovery or cleanup action.
- Nested `AGENTS.md` files may add narrower instructions, but they may not
  weaken these repository-root safety boundaries.

### Implementation-first Phase Gate

Before feature implementation, state the concrete capability, why it matters to
the core product loop, code areas touched, tests proving it, and the minimal
documentation required. Documentation is a guardrail, not a phase deliverable.

## Conditional document router

Read the smallest applicable set before working in one of these areas.

| Work area | Required design documents | Boundary to preserve |
| --- | --- | --- |
| Motion trigger or MotionEvidence | [stream-motion-trigger-plan.md](docs/stream-motion-trigger-plan.md) and the directly applicable motion/evidence design | Motion is evidence; promotion is review context; correction creates truth. |
| Model or detector adapter | [model-adapter-guardrails.md](docs/model-adapter-guardrails.md) and [model-selection.md](docs/model-selection.md) | Optional, lazy, local, evidence-only; no automatic downloads or truth writes. |
| MegaDetector runtime | [megadetector-runtime-plan.md](docs/megadetector-runtime-plan.md), [megadetector-local-setup.md](docs/megadetector-local-setup.md), and [megadetector-runtime-findings.md](docs/megadetector-runtime-findings.md) | Official-package/local-model work remains optional and proposal-only; PyTorch-Wildlife remains experimental unless explicitly reopened. |
| Species suggestions or SpeciesNet | [species-suggestion-adapter-design.md](docs/species-suggestion-adapter-design.md), then the applicable [SpeciesNet boundary plan](docs/speciesnet-adapter-boundary-plan.md) and linked investigation/source review | Suggestions remain evidence until explicit correction. |
| BioCLIP runtime | [model-adapter-guardrails.md](docs/model-adapter-guardrails.md), [model-selection.md](docs/model-selection.md), and [species-suggestion-adapter-design.md](docs/species-suggestion-adapter-design.md) | Optional, explicit local model/labels/precomputed embeddings, request-bounded and memory-isolated; ranked output is uncalibrated suggestion evidence only. |
| Classifier dataset/export/training | [custom-bird-classifier-dataset-plan.md](docs/custom-bird-classifier-dataset-plan.md), [classifier-training-manifest-design.md](docs/classifier-training-manifest-design.md), and the applicable export/training document | Reviewed corrections are training truth; dependencies, generated datasets, media bundles, and artifacts require explicit scope and ignored paths. |
| Stream playback or Source status/configuration | [stream-source-playback-contract.md](docs/stream-source-playback-contract.md), [source-connection-provider-contract.md](docs/source-connection-provider-contract.md), and [source-provider-configuration-contract.md](docs/source-provider-configuration-contract.md) as applicable | Status/configuration is product-level, redacted, and side-effect free. |
| New or real Source adapter | [source-adapter-boundary-design.md](docs/source-adapter-boundary-design.md) plus the provider-specific contract | Start with a scoped boundary; incoming media/events/detections remain evidence; extend provider smoke flows. |
| External URL media | [external-url-still-image-provider-contract.md](docs/external-url-still-image-provider-contract.md), then the applicable preview/media/evidence handoff design | Fetches are explicit, SSRF-safe, bounded, and no-truth; persistence and evidence handoff are separate actions. |
| Folder/trail-cam media | [folder-trailcam-provider-boundary-design.md](docs/folder-trailcam-provider-boundary-design.md) and [folder-import-evidence-handoff-design.md](docs/folder-import-evidence-handoff-design.md) | Preview is dry-run; import creates MediaAssets only; evidence handoff is explicit; no watcher/polling by accident. |
| Webhook provider | [generic-webhook-provider-boundary-design.md](docs/generic-webhook-provider-boundary-design.md) | No anonymous ingest or ecosystem coupling; external labels remain untrusted evidence. |
| Saved-media cleanup/retention | [external-url-saved-media-retention-design.md](docs/external-url-saved-media-retention-design.md) | Dry-run/report first; file deletion is separate from record deletion; protect reviewed/export context. |
| Worker, polling, watcher, queue, or background cleanup | [worker-lifecycle-boundary-design.md](docs/worker-lifecycle-boundary-design.md) | Default off, observable, bounded, local-first, safely stoppable, and unable to create reviewed truth. |
| Durable camera/monitor lifecycle | [durable-camera-monitor-lifecycle-design.md](docs/durable-camera-monitor-lifecycle-design.md) and [local-backup-recovery-design.md](docs/local-backup-recovery-design.md) | Desired policy and runtime state stay separate; explicit Stream arming; side-effect-free status; restore/stop/archive holds prevent surprise restart. Audio requires separate consent and design. |
| Observation Engine / streaming media / accelerated inference | [architecture.md](docs/architecture.md), [camera-node-boundary-design.md](docs/camera-node-boundary-design.md), and the applicable media, detector, and lifecycle contracts | Use the provider-neutral Observation Engine boundary; preserve `SnapshotObservationProvider` until controlled migration. Do not make a vendor runtime, polling architecture, or Camera Node provider define product semantics or truth. |
| Observation control UI, candidate-quality admission, or Stage 7 evidence-role presentation | [observation-engine-product-control-contract.md](docs/observation-engine-product-control-contract.md), then [candidate-visit-authority-contract.md](docs/candidate-visit-authority-contract.md) and [multi-frame-evidence-scoring-contract.md](docs/multi-frame-evidence-scoring-contract.md) | Wrap the accepted engine; do not invent a new detector/evidence threshold or a second review system. |

When a routed document links a more specific design for the exact task, read
that linked design too. Do not load unrelated history or every document in the
same category.

## Implementation standards

- Prefer tests for behavior changes and regression fixes.
- Add useful comments for non-obvious lifecycle, concurrency, persistence,
  security, or geometry behavior; do not narrate syntax.
- Do not run a broad unrelated test suite unless the task packet specifically
  justifies it.
- Preserve provider smoke flows: status reads do nothing, provider writes are
  explicit, and correction remains truth.
- Do not add network calls, capture/decoding, workers, dependencies, model
  files, generated media, or destructive cleanup unless the task packet
  explicitly scopes them.
- Comments should explain product intent, domain meaning, non-obvious safety
  constraints, or why a decision prevents product drift. Do not narrate syntax.
- Source setup and Dashboard/readiness surfaces guide users; they do not run
  providers/models or create evidence/truth.
- Adapter-specific models must not leak into the core product model.

## Validation and reporting

- Run the task packet's validation tier in proportion to risk.
- Docs-only work checks scope, links, terminology, current-state accuracy, and
  duplication.
- Every final task report lists changed files, validation performed, and any
  deviation from scope.
