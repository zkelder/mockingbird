# MockingBird Roadmap

This is the current planning authority. It intentionally describes completed
foundations briefly and keeps detailed historical phase narration in
[roadmap-history.md](roadmap-history.md) and the linked design documents.

## Product outcome

MockingBird is moving toward one dependable local field product:

connect Source -> view Stream -> draw Zones -> monitor outdoor activity ->
review Events/Visits -> correct labels/species -> build Bird Log, datasets,
exports, and analytics.

The current checkpoint is **Phase 24D complete**. Every Stream has default-off
monitoring policy and runtime-checkpoint records, read-only lifecycle status,
verified local backup/recovery, and one same-origin local application runtime.
No camera or monitor starts automatically.

The main missing product capability is validated automatic species
identification. MegaDetector can add animal/person/vehicle proposal evidence,
and the first BioCLIP 2 boundary can now create explicitly triggered ranked
`SpeciesSuggestion` evidence on one saved Review Queue item at a time. That
shadow path is a truth-building aid, not a selected production classifier or
automatic post-activity runtime; current `unknown_bird` suggestions remain
placeholders until replaced by real model evidence or explicit correction.

## WSL activation checkpoint

The active development checkout is now WSL-native at
`/home/zkelder/projects/mockingbird-active`. The cross-install restore completed
successfully, and the locally configured Windows `ffmpeg.exe`, native
DirectShow controls, fresh live frames, and one daylight 3840 x 2160 capture
were verified from WSL. Driver-managed exposure values remain outside
MockingBird and are neither readable nor persisted. Representative field-truth
collection is next; Playwright Chromium remains optional local WSL environment
setup rather than a product blocker.


## Completed foundations

- Phases 0-6 established product doctrine, the universal product model, the
  stream-first UI, local/demo media, the detection evidence model, the bird
  feeder review vertical, and broader outdoor concepts.
- Phases 7-9 established optional evidence-only model adapters, zone-aware
  motion and MotionEvidence, species suggestions, reviewed classifier
  readiness, and local export/training boundaries.
- Phases 10-16 established product-level playback/provider contracts,
  explicit external URL and folder media flows, generic webhook metadata
  evidence, retention boundaries, MVP onboarding, and disabled worker metadata.
- Phases 17-18 improved evidence review and classifier-readiness drill-down.
- Phases 19-22 added explicit in-memory camera monitoring, browser/RTSP/local
  USB playback, backend-owned live camera sessions, Zone overlays, best-frame
  evidence, and optional identification assistance.
- Phase 23 began real feeder-camera validation, camera lifecycle cleanup,
  bounded diagnostics, field calibration, and optional local MDv5 proposal
  verification.
- Phases 24A-24D added the single local runtime, verified database-and-media
  backup/restore, durable lifecycle design, and inert default-off monitoring
  policy/runtime state.

See [roadmap-history.md](roadmap-history.md) for the concise phase record.

## Current priority 1: real visual species identification

Goal: deliver the shortest complete identification loop:

saved activity -> best frame -> animal/activity crop -> real ranked species
suggestions -> Review Queue -> correction -> Bird Log

The first saved-media evaluation completed on July 16, 2026. SpeciesNet did not
clear the field-usefulness gate on the current feeder corpus. BioCLIP 2 was
better at returning bird candidates, but species accuracy remains unmeasured
because the local records have coarse bird/false-positive truth rather than
species-level corrections. Several visually questionable predictions also had
high scores, so no production runtime is selected yet.

The active gate is now representative species-level correction truth plus
substantially more non-bird activity examples from identification-quality
captures. The eventual runtime must stay optional, local, unavailable-safe, and
evidence-only.

### Step A - saved-media classifier evaluation (complete)

The completed evaluation recorded:

- SpeciesNet crop/full-frame and combined-pipeline output on saved field media
- BioCLIP 2 rankings against the same activity/detection crops
- cold-start, cached, and per-image CPU inference cost
- local runtime, dependency, model-size, and no-download behavior
- six exposure-cleanup variants against an unchanged candidate bank

SpeciesNet recognized bird as top-1 on only one of eight reviewed bird crops
and produced no species-specific top-1 result. BioCLIP 2 returned an avian
species first for the reviewed/candidate bird crops, but that result is biased
by a bird-heavy candidate bank and is not species accuracy. Automatic
post-capture exposure filters did not consistently improve either model and
cannot recover clipped image detail.

Evaluation media, model files, caches, and reports stay in ignored local paths.
Zones may provide context but must not define the crop. Use detector boxes when
credible and measured activity bounds as the fallback.

### Step B - representative species truth gate

Use the existing Review Queue correction path to build one frozen,
representative field set from identification-quality best frames and activity
crops. It must include explicit species corrections, ambiguous/unknown birds,
and enough animal/person/vehicle/blank activity to measure false suggestions
and abstention.

An explicitly triggered, one-item-at-a-time BioCLIP shadow may run during this
truth-building step. It can create ranked, candidate-relative, uncalibrated
`SpeciesSuggestion` evidence to make correction faster, but its availability
does not select the model, establish accuracy, enable automation, or create
truth. The original frame and the actual detector/activity/full-frame input
region remain visible as provenance.

The first end-to-end shadow smoke completed on July 16, 2026: one existing
saved Review Queue item used a credible animal-detection crop, returned a
plausible species as rank 1, and created one pending `SpeciesSuggestion`.
ReviewLabel, DetectionRun, DetectionProposal, export, camera, and monitoring
state remained unchanged. This validates the product boundary, not model
accuracy; the representative correction gate below still controls selection.

Phase 26A1 now provides a hard read-only field-truth evaluator over stored
BioCLIP rankings and final exact-target ReviewLabels. The current local
checkpoint has one eligible example and fifteen reviewed targets without
BioCLIP evidence, so its result is descriptive only and cannot justify model
selection. Top-1, stored top-3, crop, and reproducibility variants are available;
Phase 26A2 now durably records each future user-triggered manual attempt,
including complete candidate membership, duration, exact crop, model/runtime
provenance, successful suggestion linkage, and honest no-result, timeout,
failure, unsupported, or cancelled outcomes. Historical attempts were not
invented or backfilled. The next step is collecting the representative
30-100-example field-truth set through the existing correction flow.

Candidate labels must be genuinely local and seasonal, with explicit unknown
and non-bird choices. Rerun the leading candidate against held-out corrections
and record top-1, top-3, coverage, abstention, high-confidence mistakes, and
non-bird specificity. This uses the existing product correction flow; it does
not require a labeling or readiness page.

### Step C - bounded Review Queue shadow integration

The evaluation-only shadow from Step B stays manually triggered and processes
one media-backed Visit at a time. After a candidate clears the truth gate, this
same bounded seam may become the selected visual classifier path. It still
creates ranked `SpeciesSuggestion` evidence only. Review Queue shows the best
suggestion, alternatives, uncalibrated score, provenance, crop, and original
frame through the existing correction flow. Accepting or changing a suggestion
creates truth only when the user submits the correction.

No new analyzer administration page, readiness surface, or parallel species
workflow is required. Failures leave the Visit unidentified and reviewable.

### Step D - automatic post-activity inference

After saved-media accuracy and runtime behavior are acceptable, run the detector
and selected classifier automatically for each eligible completed activity.
Execution must be bounded, optional, observable, safely stoppable, and unable to
create reviewed truth. It enriches the existing review candidate; it does not
become a second event trigger or bypass Review Queue.

### Visual identification exit criteria

- a real local species model produces ranked suggestions on saved field media
- top-1/top-3, abstention, non-bird specificity, and inference cost are recorded
  against species-level reviewed labels
- unusably clipped captures are reported before their predictions are treated
  as meaningful evaluation evidence
- activity/animal-centered crops work without requiring Zones
- Review Queue exposes suggestions through the existing correction interaction
- corrections feed Bird Log and provide evaluation truth
- automatic post-activity inference fails safely without blocking capture or
  review

### Product work freeze

Until these criteria pass, do not add new admin panels, readiness screens,
provider abstractions, diagnostics surfaces, training scaffolding, or broad
refactors. Targeted extraction is allowed only where the identification path
touches an oversized component and the change delivers or protects this
vertical slice. Audio follows the working visual path; it does not delay it.

## Supporting engineering gate: Phase 24 hardening

This gate continues only where it directly reduces risk for the identification
vertical or later unattended capture. It is not the active feature backlog.
Durable supervisor work still requires the applicable lifecycle gates before
activation.

This gate improves the complete Cameras/Streams -> Zones -> monitoring -> Review
Queue -> correction -> Bird Log -> Exports flow. It does not change the product
truth boundary.

### Gate A - feedback and reproducibility

Status:

- Documentation authority, conditional routing, and repository-wide validation
  tiers are defined in [development-workflow.md](development-workflow.md).
- A hardware-free browser check covers correction -> Bird Log -> reviewed-only
  export behavior using isolated local data.
- Additional automation, formatting/type policy, and dependency reproducibility
  work is added only when it protects the active identification vertical or a
  release gate; it is not the next product feature.

Exit criteria:

- A clean checkout has one documented command or automated job for each
  non-hardware validation tier.
- Backend tests, frontend type-check/build, migration/backup compatibility, and
  the critical smoke flow run automatically at the appropriate tier.
- Hardware, models, cameras, generated media, and secrets are not required for
  normal automated checks.

### Gate B - browser and API contract safety net

Add a small hardware-free browser suite for the primary path: create/configure
a camera, reach Stream Detail, manage a Zone, exercise a deterministic
monitoring/review candidate, submit correction truth, verify Bird Log, and
verify reviewed-only export behavior.

Generate frontend API types from Pydantic/OpenAPI or enforce an automated parity
check so backend/frontend contract drift fails validation.

### Gate C - targeted architecture seams

Avoid a broad rewrite. When Phase 24E touches lifecycle behavior, extract the
relevant camera/session/supervisor routes and repository operations into focused
domain services. When primary browser flow work touches Streams or Stream
Detail, extract focused components/hooks and scoped styles.

New work should stop increasing the largest API, repository, page, and global
style concentration points. Refactoring tasks must preserve behavior, include
focused regression coverage, and avoid unrelated product features.

### Gate D - measurable field benchmark

Build an ignored/local, frozen set of representative feeder observations and
record:

- bird recall
- nuisance candidates per camera-hour
- candidate acceptance rate
- median review time
- stale/dropped frames
- CPU use and storage growth per camera-hour

Threshold, crop, focus, or analyzer comparisons should use the same benchmark.
The full source frame remains evidence context and explicit user correction
remains truth. Benchmark media and reports are never committed.

### Gate E - resilience, privacy, security, and upgrades

Before live-video continuity activation, validate camera/FFmpeg loss, hung
processes, disk-full and database-locked behavior, restart during media writes,
clock changes, and backup/restore while policy is armed.

Decide and test:

- loopback-only versus LAN exposure and authentication expectations
- browser-origin/localhost request protection
- secret-file permissions and redaction
- whether Privacy Zones suppress only analysis or also persisted full-frame
  media
- every supported schema and backup upgrade path
- startup, idle-memory, per-Stream CPU, frame-freshness, database-growth, and
  media-growth budgets

### Gate F - documentation maintenance

Keep current system contracts, current roadmap, architectural decisions, and
completed history separate. Link applicable guardrails instead of copying them
into every task/design document. Product doctrine, privacy/lifecycle safety,
and the evidence-versus-truth boundary remain prominent and canonical.

### Engineering-gate sequencing

- The representative truth gate and later bounded Review Queue shadow
  integration do not wait for the durable supervisor.
- Automatic post-activity inference requires focused failure, runtime-bound,
  storage, privacy, and stop-behavior tests for that inference path.
- Phase 24E may begin after Gate A's automated baseline and the relevant Gate C
  lifecycle seam are in place. Its supervisor remains disabled and fake-adapter
  tested.
- Explicit live-video continuity must not activate until Gate B and the relevant
  Gate E failure/privacy/security/upgrade decisions pass.
- Phase 25 field-loop acceptance requires Gate D, long-run/soak results, and
  declared performance/storage budgets.
- New providers and unrelated model pathways do not take priority. The visual
  species adapter above is the explicitly scoped core product milestone.

## Deferred supporting work: Phase 24E-24G durable live continuity

### Phase 24E - disabled supervisor foundation

Add a bounded `DurableStreamSupervisor` foundation with fake-adapter lifecycle,
app-instance/checkpoint reconciliation, one-Stream leases, deterministic
backoff, and stop ordering.

The supervisor remains unavailable for runtime activation. Tests use fake time
and fake camera/session boundaries. Status reads stay side-effect free.

### Phase 24F - explicit live-video continuity

After the engineering gates pass, add explicit Stream-scoped arming for
supported backend-owned RTSP/local USB/Windows DirectShow live video.

Persisted desired policy and actual runtime state remain separate. Every Stream
defaults off; backup, restore, migration, emergency stop, Source archive, Stop
camera, and shutdown holds prevent surprise restart. External snapshot polling
and future audio are outside this lifecycle.

### Phase 24G - bounded idempotent review handoff

Allow explicitly enabled durable monitoring to create or reuse at most one
needs-review candidate per completed activity session under storage, quiet
window, duplicate, Privacy Zone, and Ignore Zone limits.

It may create evidence and unreviewed Event/Visit context only. It never creates
ReviewLabels, marks Visits reviewed, runs identification automatically, writes
Bird Log truth, or creates analytics/export truth.

The separate optional visual-identification enrichment in Step C may run after
an eligible candidate exists. It is not part of handoff, event triggering, or
truth creation.

Design authority:

- [single-app-runtime-recovery-design.md](single-app-runtime-recovery-design.md)
- [local-backup-recovery-design.md](local-backup-recovery-design.md)
- [durable-camera-monitor-lifecycle-design.md](durable-camera-monitor-lifecycle-design.md)

## Phase 25 - dependable field loop

Harden restart recovery, bounded storage, retention controls, camera/source
health, long-run observability, support-safe diagnostics, and representative
feeder validation. Acceptance uses the frozen field benchmark and declared
performance/storage budgets from the engineering gate.

## Phase 26 - identification evidence

- Phase 26A is now the active product milestone above: evaluate and integrate an
  optional local visual identification adapter that creates ranked species
  suggestion evidence only. Phase 26A2 durable manual-attempt instrumentation
  is complete; representative field-truth collection is next.
- Phase 26B: integrate optional local bird-audio evidence through a separately
  designed consent, microphone, privacy, retention, and dependency boundary.
- Phase 26C: combine visual, audio, time, Zone, and reviewed local history into
  ranked suggestions. Explicit correction remains the only dataset-grade
  species truth.

## Phase 27 - release acceptance

Finish packaging, first-run setup, update/recovery policy, accessibility,
performance, dependency reproducibility, upgrade support, and release
acceptance for a dependable local product.

## Cross-cutting roadmap invariants

- Source adapters remain underneath Sources, Streams, Zones, Events, Visits,
  review/correction, analytics, and exports.
- MediaAssets, MotionEvidence, DetectionProposals, SpeciesSuggestions, and
  external labels remain evidence/context until explicit correction.
- Read/status/preview/dry-run routes are side-effect free. Writes are explicit,
  scoped, bounded, and tested.
- Privacy and Ignore Zones, local storage, retention, backups, and safe restart
  behavior are first-class constraints.
- Workers and durable monitoring default off, are observable and safely
  stoppable, and cannot create reviewed truth.
- Model runtimes, training dependencies, generated datasets, captured media,
  benchmark artifacts, and caches require explicit scope and ignored local
  paths.
- Each implementation task uses the task packet and validation tiers in
  [development-workflow.md](development-workflow.md).

## Roadmap non-goals

- No one-shot repository rewrite or coverage-percentage target.
- No cloud dependency or telemetry requirement for the core product.
- No new administration page merely for lifecycle or engineering controls.
- No provider, audio, or unrelated automation expansion ahead of the active
  visual identification milestone without explicit evidence and scope.
