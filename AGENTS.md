# Codex Guardrails

MockingBird is a local-first, hardware-agnostic, bird-first but
wildlife-native nature observatory -- not primarily an NVR, a surveillance
platform, a camera-management product, an ML demo, or a species-classifier
appliance. Streams, Zones, detectors, and classifiers are infrastructure that
produce evidence; trustworthy Observations and growing understanding of a
place are the product. See [docs/product-doctrine.md](docs/product-doctrine.md).

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

User-facing loop: Observe -> Discover -> Understand -> Confirm -> Remember ->
Improve. State task packets in these terms, not only the technical flow
below.

Technical flow: connect Source -> view Stream -> draw Zones -> analyze
outdoor activity -> review Events/Visits -> correct labels/species -> export
datasets and analytics.

Preserve these concepts: Source, Stream, Zone, Event (doctrine: Activity
Session), Visit, Detection/DetectionProposal (doctrine: Detection Proposal),
review/correction (doctrine: Review Decision), Observation (the durable
reviewed object doctrine names as the product's semantic center -- distinct
from the existing Observation Engine/Observation Control runtime, which is
infrastructure), Dataset Export, and Analytics. See
[docs/glossary.md](docs/glossary.md) for the full current-vs-doctrine-name
mapping.

- Detection, tracking, and classification are infrastructure that produce
  evidence; trustworthy Observations and growing understanding of a place are
  the product outcome. Do not organize a task around maximizing detections,
  classifier sophistication, camera integrations, or model novelty.
  Detection/encounter/Visit correctness is the harder, higher-priority v0.1
  release gate; species identification only needs to be useful and honest,
  not perfect -- see "Governing priority for v0.1" in
  [docs/roadmap.md](docs/roadmap.md).
- A candidate detector/classifier does not gain production authority merely
  because it is newer or appears better informally; require reproducible
  incumbent comparison on identical data first.
- Streams and Zones are the product center. Adapters normalize into product
  concepts; they do not define the product.
- Detections, DetectionProposals, SpeciesSuggestions, MotionEvidence, imported
  media, and external labels are evidence or context, never reviewed truth.
  Unknown and abstained outcomes are valid; never turn model, ecological-prior,
  or language-model output into reviewed truth.
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
interval analysis, debug internals, snapshot loops, one adapter, hardware
setup, or NVR/security-platform framing. Today's WSL/checkout/CLI development
mechanics are not the mature-product installation experience; see
[docs/roadmap.md](docs/roadmap.md) Phase 4.

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
| Privacy Zone or Ignore Zone semantics, copy, or enforcement | [privacy-ignore-zone-contract.md](docs/privacy-ignore-zone-contract.md) | Trigger-level exclusion only; never claim or imply pixel-level redaction unless repository evidence establishes it is actually implemented. |
| Model or detector adapter | [model-adapter-guardrails.md](docs/model-adapter-guardrails.md) and [model-selection.md](docs/model-selection.md) | Optional, lazy, local, evidence-only; no automatic downloads or truth writes; no production promotion without reproducible incumbent comparison (roadmap.md Phase 2). |
| MegaDetector runtime | [megadetector-runtime-plan.md](docs/megadetector-runtime-plan.md), [megadetector-local-setup.md](docs/megadetector-local-setup.md), and [megadetector-runtime-findings.md](docs/megadetector-runtime-findings.md) | Official-package/local-model work remains optional and proposal-only; PyTorch-Wildlife remains experimental unless explicitly reopened. |
| Species suggestions or SpeciesNet | [species-suggestion-adapter-design.md](docs/species-suggestion-adapter-design.md), then the applicable [SpeciesNet boundary plan](docs/speciesnet-adapter-boundary-plan.md) and linked investigation/source review | Suggestions remain evidence until explicit correction. |
| BioCLIP runtime | [model-adapter-guardrails.md](docs/model-adapter-guardrails.md), [model-selection.md](docs/model-selection.md), and [species-suggestion-adapter-design.md](docs/species-suggestion-adapter-design.md) | Optional, explicit local model/labels/precomputed embeddings, request-bounded and memory-isolated; ranked output is uncalibrated suggestion evidence only. |
| Source/native-resolution evidence, resolution provenance, or multi-frame species-classifier candidates | [source-resolution-multi-frame-species-evidence-contract.md](docs/source-resolution-multi-frame-species-evidence-contract.md), then [same-frame-species-evidence-contract.md](docs/same-frame-species-evidence-contract.md) and [localization-attribution-contract.md](docs/localization-attribution-contract.md) | Reuse `GeometryAttribution.resolution_provenance` (`exact_same_frame`/`synchronized`/`near_time_capture`/`fallback`) and the existing `mockingbird.motion.high_resolution_evidence.resolve_alignment` proof rather than a second alignment system; never crop a reused subject box onto a higher-resolution image without a proven FOV match; multi-frame consensus (`evaluate_multi_frame_consensus`) exists as tested infrastructure but is not wired into the live identification path -- do not promote it to unconditional production without fresh reproducible benchmark evidence (roadmap.md Phase 2 rule). |
| Classifier dataset/export/training | [custom-bird-classifier-dataset-plan.md](docs/custom-bird-classifier-dataset-plan.md), [classifier-training-manifest-design.md](docs/classifier-training-manifest-design.md), and the applicable export/training document | Reviewed corrections are training truth; dependencies, generated datasets, media bundles, and artifacts require explicit scope and ignored paths. |
| ReviewLabel/Review Decision creation, correction, provenance, Bird Log/Wildlife Journal truth semantics, or reviewed-only export/training eligibility | [review-decision-provenance-contract.md](docs/review-decision-provenance-contract.md) | `mockingbird.review_provenance.is_authority_eligible` is the only place that decides truth eligibility; never scatter a new ad hoc origin check. Omitted/agent/model provenance must never default to or be treated as human authority. |
| Place/reporting analytics (current-period Visit/species/Zone/hour facts, monitoring coverage) | [place-activity-report-contract.md](docs/place-activity-report-contract.md), then [representative-species-evidence-contract.md](docs/representative-species-evidence-contract.md) for the per-species representative-image slice | One deterministic, LLM-free computation path (`mockingbird.analytics.place_activity_report`); reuse it rather than adding a second Visit/Dashboard/history analytics path. Confirmed truth always outranks a provisional suggestion; genuinely unresolved evidence stays unresolved rather than being fabricated into a species. A representative image's taxon eligibility follows the identical truth precedence; never select one from a provisional suggestion or a sibling Visit's evidence. |
| Historical baseline maturity, new-vs-regular species status, or accumulated multi-day Place history | [historical-baseline-maturity-contract.md](docs/historical-baseline-maturity-contract.md), then [place-activity-report-contract.md](docs/place-activity-report-contract.md) | Reuse `mockingbird.analytics.historical_baseline`'s usable-day/regularity primitives rather than a second coverage-aware threshold; only an authority-eligible confirmation may establish or extend a taxon's historical record; never anomaly/change detection, "more/less than normal," or ecological rarity -- see [meaningful-change-detection-contract.md](docs/meaningful-change-detection-contract.md) for the bounded slice of that which now exists, and Phase 5 in roadmap.md for the rest. |
| Meaningful change/trend detection, recent-vs-reference presence comparison, or any "more/less often than before" claim | [meaningful-change-detection-contract.md](docs/meaningful-change-detection-contract.md), then [historical-baseline-maturity-contract.md](docs/historical-baseline-maturity-contract.md) | Reuse `mockingbird.analytics.place_change_summary`'s presence-day/window-validity primitives rather than a second comparison path; a comparison requires this module's own stricter 21-usable-day gate, not bare "established" baseline maturity alone; never a population/ecological/statistical-significance claim, never a Place-wide conclusion forced across conflicting per-species signals. |
| Stream playback or Source status/configuration | [stream-source-playback-contract.md](docs/stream-source-playback-contract.md), [source-connection-provider-contract.md](docs/source-connection-provider-contract.md), and [source-provider-configuration-contract.md](docs/source-provider-configuration-contract.md) as applicable | Status/configuration is product-level, redacted, and side-effect free. |
| New or real Source adapter | [source-adapter-boundary-design.md](docs/source-adapter-boundary-design.md) plus the provider-specific contract | Start with a scoped boundary; incoming media/events/detections remain evidence; extend provider smoke flows. |
| External URL media | [external-url-still-image-provider-contract.md](docs/external-url-still-image-provider-contract.md), then the applicable preview/media/evidence handoff design | Fetches are explicit, SSRF-safe, bounded, and no-truth; persistence and evidence handoff are separate actions. |
| Folder/trail-cam media | [folder-trailcam-provider-boundary-design.md](docs/folder-trailcam-provider-boundary-design.md) and [folder-import-evidence-handoff-design.md](docs/folder-import-evidence-handoff-design.md) | Preview is dry-run; import creates MediaAssets only; evidence handoff is explicit; no watcher/polling by accident. |
| Webhook provider | [generic-webhook-provider-boundary-design.md](docs/generic-webhook-provider-boundary-design.md) | No anonymous ingest or ecosystem coupling; external labels remain untrusted evidence. |
| Saved-media cleanup/retention | [external-url-saved-media-retention-design.md](docs/external-url-saved-media-retention-design.md) | Dry-run/report first; file deletion is separate from record deletion; protect reviewed/export context. |
| Worker, polling, watcher, queue, or background cleanup | [worker-lifecycle-boundary-design.md](docs/worker-lifecycle-boundary-design.md) | Default off, observable, bounded, local-first, safely stoppable, and unable to create reviewed truth. |
| Durable camera/monitor lifecycle | [durable-camera-monitor-lifecycle-design.md](docs/durable-camera-monitor-lifecycle-design.md) and [local-backup-recovery-design.md](docs/local-backup-recovery-design.md) | Desired policy and runtime state stay separate; explicit Stream arming; side-effect-free status; restore/stop/archive holds prevent surprise restart. Audio requires separate consent and design. |
| Observation Engine / streaming media / accelerated inference | [architecture.md](docs/architecture.md), [camera-node-boundary-design.md](docs/camera-node-boundary-design.md), and the applicable media, detector, and lifecycle contracts | Use the provider-neutral Observation Engine boundary; preserve `SnapshotObservationProvider` until controlled migration. Do not make a vendor runtime, polling architecture, or Camera Node provider define product semantics or truth. |
| Observation control UI, candidate-quality admission, or Stage 7 evidence-role presentation | [observation-engine-product-control-contract.md](docs/observation-engine-product-control-contract.md), then [candidate-visit-authority-contract.md](docs/candidate-visit-authority-contract.md), [multi-frame-evidence-scoring-contract.md](docs/multi-frame-evidence-scoring-contract.md), and [unified-observation-panel-contract.md](docs/unified-observation-panel-contract.md) | Wrap the accepted engine; do not invent a new detector/evidence threshold or a second review system. Route by existing runtime capability; never force a camera type through a runtime it does not use. |
| Recurring/persistent scene-confusor suppression, durable per-Stream geometry history, or `scene_confusor_regions` | [scene-confusor-suspicion-contract.md](docs/scene-confusor-suspicion-contract.md), then [candidate-visit-authority-contract.md](docs/candidate-visit-authority-contract.md) and [rejected-detection-attribution-contract.md](docs/rejected-detection-attribution-contract.md) | Never hard-code a coordinate or scene name; never build a permanent/irreversible blacklist; reviewed-truth protection is unconditional; invalidate durable regions on any `restart_required` camera-configuration change; keep every lookup bounded per Stream. |
| Candidate-visit authority budget/session lifecycle, or the independent field-validation frame recorder (`acceptance_recorder.py`) | [candidate-visit-authority-contract.md](docs/candidate-visit-authority-contract.md) ("Session/Stream scope," "Fresh-session activation," "Evidence-cache capacity"), then [independent-encounter-denominator-design.md](docs/independent-encounter-denominator-design.md) | Authority state is per-Stream, never a global singleton; a fresh session always gets a fresh budget; the recorder is off by default, diagnostic-only, and structurally cannot become admission evidence -- never wire it into a normal product route/UI. |
| Multi-subject Visit handling, cross-track duplicate/fragmentation behavior, or any change to `visit_episode_assembler`'s merge-boundary rule | [tracklet-visit-assembly-contract.md](docs/tracklet-visit-assembly-contract.md) ("Structural incompatibility"), [candidate-visit-authority-contract.md](docs/candidate-visit-authority-contract.md), `roadmap.md`'s "Multi-subject Visit correctness" under Gate A, then the concrete implementation design [multi-subject-visit-assembly-review-v1.md](docs/multi-subject-visit-assembly-review-v1.md) | This is now a v0.1 release-gate requirement, not a deferred nice-to-have -- but do not implement it opportunistically inside an unrelated task, and do not solve it via persistent individual ReID; preserve ambiguity over fabricated continuity. |
| Perception replay/regression harness work, offline funnel replay of recorded evidence, or adding a named regression fixture | [perception-replay-regression-harness-contract.md](docs/perception-replay-regression-harness-contract.md), then [observation-replay-benchmark-contract.md](docs/observation-replay-benchmark-contract.md) for the Stage 2 layer it extends | Reuse production computation (the real Stage 7 gates through an isolated repository); never build a second perception implementation. Admission always runs against a freshly isolated, disposable database and a `replay:`-prefixed synthetic Stream identity -- never the real product database, never a real Stream. Live field acceptance remains required for promotion; replay reduces how often a fix waits for another real bird, it does not replace that requirement. |
| Camera Node installer, systemd/OS service supervision, artifact packaging, or edge-device reboot/crash recovery | [camera-node-installer-design.md](docs/camera-node-installer-design.md), then [camera-node-boundary-design.md](docs/camera-node-boundary-design.md) | Camera Node stays lightweight capture/transport infrastructure, not durable Observation truth; no edge inference, discovery, cloud management, or remote host-triggered updates; this is Phase 1 (proving the real Camera Node path is durable), not Phase 4 (the host's own packaging). |
| Camera Node configuration backup/export, reprovisioning, or physical-hardware replacement | [camera-node-reprovision-recovery-design.md](docs/camera-node-reprovision-recovery-design.md), then [camera-node-pairing-persistence-design.md](docs/camera-node-pairing-persistence-design.md) | Camera Nodes are replaceable field infrastructure, never the system of record; a replacement reattaches to the *existing* logical Source/Stream (bounded provenance, honest live capability rediscovery, no fabricated Zone-geometry equivalence) rather than creating a duplicate camera or rewriting history to claim new hardware captured old evidence. |
| Local product packaging, first-run onboarding, storage/host-disk status, product health, or the runtime crash-marker/log location | [local-product-packaging-design.md](docs/local-product-packaging-design.md) | Compose existing Add Camera/Observation/backup capability; do not add a second implementation of any of them. Onboarding gates the dashboard route only, is seeded once from schema state, and is never inferred from current Source/Stream counts. |
| Windows dev deployment tooling (`scripts/deploy_windows_dev.py`), build/instance identity (`build_info.json`, `GET /api/product/instance`) | [windows-dev-deployment-design.md](docs/windows-dev-deployment-design.md) | Developer tooling only -- no product behavior change. Reuse `build_local_product.py`'s own functions; never duplicate or bypass its packaging/provenance/DLL-closure verification. Never touch the real `%LOCALAPPDATA%\MockingBird` user-data directory or stop a process without a fresh, live identity re-check. |
| Test/repository isolation, `tests/conftest.py`, or `get_repository()`'s default-database fallback | [test-repository-isolation-contract.md](docs/test-repository-isolation-contract.md) | An automated test must never silently fall back to the persistent development/product database; a missing fixture must fail closed or use isolated storage, never the real `data/mockingbird.sqlite3`. An explicit persistent-database integration fixture (a real `tmp_path`-backed `db_url`) remains deliberate and obvious. |
| Test suite organization, runtime, the `slow` pytest marker, or `scripts/verify_fast.py`/`verify_core.py`/`verify_full.py` | [test-suite-validation-tiers-contract.md](docs/test-suite-validation-tiers-contract.md), then [development-workflow.md](docs/development-workflow.md)'s "Backend validation gates" | A test may be slow and still essential, or fast and still redundant -- classify by the distinct behavioral contract protected, not runtime alone. Never blanket-skip/xfail to make a dashboard green; every quarantine states why. Genuine hardware/platform acceptance stays outside ordinary `pytest`, never disguised as Fast/Core coverage. |

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
