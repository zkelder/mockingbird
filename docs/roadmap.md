# MockingBird Roadmap

This is the current planning authority. It intentionally describes completed
foundations briefly and keeps detailed historical phase narration in
[roadmap-history.md](roadmap-history.md) and the linked design documents.

## Product outcome

MockingBird is a local-first, hardware-agnostic, bird-first but
wildlife-native nature observatory that helps people notice, understand,
confirm, and remember wildlife around a place. Detection, tracking, and
classification are infrastructure; trustworthy Observations, coherent
Visits, good evidence, honest uncertainty, efficient review, meaningful
discoveries, durable history, and growing understanding of a place are the
product. See [product-doctrine.md](product-doctrine.md) for the full
doctrine this roadmap sequences.

The user-facing loop is **Observe → Discover → Understand → Confirm →
Remember → Improve**. The internal evidence/truth architecture is Source →
Stream → Zone → Activity Session → Visit → Evidence → Detection Proposal →
Interpretation → Review Decision → Observation → Export/Analytics
(product-doctrine.md; implementation vocabulary still uses
Event/Visit/Detection/ReviewLabel, see [glossary.md](glossary.md)).
Detectors and SpeciesSuggestions are evidence; explicit correction is the
only reviewed truth used for confirmed species, history, exports, and
analytics; unknown and abstained outcomes are valid.

## Current status

- **Current phase:** Phase 1 -- Trustworthy Single-Site Observatory (below).
- **Current exit gate:** one representative installation can run for days
  and create trustworthy useful history without developer babysitting.
- **Already complete** (see [roadmap-history.md](roadmap-history.md) for
  detail): the real Camera Node path; the native ONNX Runtime CUDA
  detection/tracking/evidence Observation Engine, hardened through repeated
  real field campaigns, with a default-off candidate-Visit authority mode;
  restart/recovery and durable monitoring lifecycle; admission/rejection
  observability (the July 30 cohort measured 10/10 promoted Visits as real
  birds); source-resolution evidence lineage; a self-contained Windows
  install bundle (Phase 27A); and two real-hardware defects found and fixed
  in the most recent field session (Camera Node pairing repair, and an
  Observation/live-view capture-ownership collision).
- **Remains for this phase:** confirm the two just-fixed paths against a
  real end-to-end bird Visit (not yet attempted); resolve the still-
  insufficient admission recall measured in the July 30 cohort; verify
  bounded CPU/RAM/storage behavior and truthful capability reporting against
  representative unattended field conditions, not only shadow/synthetic
  benchmarks.
- **Explicitly deferred:** Phases 2 and 5-8 below do not start in earnest
  until Phase 1's exit gate is met, except where already-shipped Phase 3/4
  capability (Today in Your Yard v1, Phase 27A packaging) made opportunistic
  progress -- see "Phase sequencing."
- **Next recommended implementation milestone:** a bounded, real Camera Node
  field session that answers one question -- does a real bird now produce
  one coherent candidate Visit end-to-end through the fixed
  capture-ownership and detection path? The last field session's fixes have
  not yet been exercised against a live bird. See "Field-testing doctrine,"
  below, for how to scope it.

## Phase sequencing

A later phase may already have partial, opportunistically-shipped capability
(noted where applicable) without changing which phase currently governs
prioritization -- that remains the lowest-numbered phase whose exit
condition is not yet met.

### Phase 1 -- Trustworthy Single-Site Observatory (current)

Finish/prove: real Camera Node path, native runtime direction, sustained
operation, restart/recovery, truthful health/capability reporting, bounded
CPU/RAM/storage behavior, admission/rejection observability, representative
field acceptance, coherent Visits, useful evidence, correct source-resolution
lineage, durable review/correction truth.

Largely proven: the real Camera Node path; the native ONNX Runtime CUDA
detection/tracking/evidence pipeline with verified CUDA-only execution;
restart/recovery; admission/rejection observability (July 30 cohort);
source-resolution lineage; durable review/correction truth. Two real defects
found through live use are fixed: Camera Node pairing repair, and an
Observation/live-view capture-ownership collision.

Still open: representative field acceptance has been mixed -- the first
campaign failed on admission precision, a later cohort passed precision with
insufficient recall, and tracker fragmentation took several real rounds of
fixes to bring under control. The two most recent fixes have not yet been
exercised against a real end-to-end bird Visit. Truthful capability
reporting covers only a narrow "no runtime available" case today (see
"Capability-aware UX" in [architecture.md](architecture.md)). Bounded
CPU/RAM/storage behavior is declared (see the former Gate E budgets, below)
but not exhaustively verified under representative unattended field
conditions.

The former "Phase 24 hardening" Gates A-F are superseded by this exit gate
and by [development-workflow.md](development-workflow.md)'s validation
tiers. Gates A and D are substantially fulfilled by development-workflow.md
itself and by the entire Observation Engine v2 benchmark suite
(architecture.md), and Gate B is substantially fulfilled by the existing
Playwright suite (`web/e2e`: onboarding, the reviewed product loop, camera
controls, the Observation panel). Gate C (targeted architecture seams) is an
ongoing practice, not a one-time gate. Gate E's resource/failure budgets are
declared but not exhaustively field-verified -- part of "still open," above.

Exit condition: one representative installation can run for days and create
trustworthy useful history without developer babysitting.

### Phase 2 -- Detection Quality & Model Lifecycle

Build: stage-level quality accounting, representative benchmark, rejection
audit, difficult-case slices, incumbent/candidate comparison, calibration,
abstention, model/version provenance, shadow evaluation, promotion/rollback
rules.

Not formally started as a phase, but substantial reusable infrastructure
already exists: a deterministic detector calibration/precision-recall
benchmark, a shadow-only incumbent-vs-candidate comparison tool (already used
to reject the `spruce` MegaDetector candidate on measured precision/recall
and licensing grounds), multi-scale and adaptive motion-proposal benchmarks,
an evidence-usefulness benchmark, and the shadow-evaluation discipline the
whole Observation Engine migration was built on. See "Detection Quality
Accounting" and "Formal model lifecycle" in [architecture.md](architecture.md).

Remains: organize this prior art into the explicit 14-stage accounting in
architecture.md instead of ad hoc benchmarks; build representative
difficult-case slices as a standing structure (common/uncommon/unknown
species, partial/occluded animals, multiple animals, small/distant subjects,
feeder obstruction, motion blur, poor lighting/dawn/dusk, non-birds, empty
backgrounds); implement abstention, which does not exist anywhere in the
pipeline today; add classifier-side calibration; formalize rejected-
candidate/counterfactual auditing as a standing, bounded record; define an
explicit promotion-decision rule, versioned deployment, monitoring, and
rollback/retirement policy; and collect the representative (30-100 example)
species-level correction truth needed to actually validate BioCLIP --
never completed under the earlier "visual species identification" priority
-- before deciding production selection or its abstention/calibration
policy.

Exit condition: we can explain quantitatively where the vision pipeline is
good, where it fails, and whether a candidate actually improves the product.

### Phase 3 -- Observation & Today in Your Yard Product Loop

Deepen: Observation semantics, Today in Your Yard, best moments, new/regular
visitors, review, evidence/confidence explanation, corrections, first/last
seen, useful history.

Partially delivered: Today in Your Yard already ships as the Dashboard
center -- detector-qualified animal Visits, reviewed discoveries, best
evidence-backed moments, Zone/hour context, bounded confirmation work, and
compact observation health.

Remains: reframe review/history around Observation as the durable semantic
object (see product-doctrine.md and the naming note in glossary.md) rather
than reviewed-Visit framing; first/last seen; new-versus-regular visitor
distinction; plain-language evidence/confidence explanation; deeper
corrections UX; Phase 26C/26D audio and multi-signal ranking.

Exit condition: opening MockingBird after being away for a day is
intrinsically useful even to someone who does not care about the underlying
ML/camera stack.

### Phase 4 -- Install / Recovery / Appliance Experience

Deliver: package/installer, automatic services, guided camera configuration,
safe upgrade, backup/recovery, storage management, understandable health,
golden-path setup, advanced controls available without dominating normal UX.

Partially delivered: Phase 27A ships a self-contained Windows "unpack and
run" bundle, a first-run setup wizard, and a consolidated product-health view
(see [local-product-packaging-design.md](local-product-packaging-design.md)).

Remains: native Windows hardware acceptance of the produced bundle (a
pending manual step outside this environment); automatic upgrade; guided
recovery; storage management as product-managed behavior rather than
developer tooling; accessibility. `scripts/deploy_windows_dev.py` stays
developer tooling only and is not this phase's product installer (see
[windows-dev-deployment-design.md](windows-dev-deployment-design.md)).

Exit condition: a technically competent non-developer can deploy MockingBird
without WSL, cloning GitHub, or understanding internal services.

### Phase 5 -- Place Intelligence

Not started. Add baselines, Zone/time preferences, meaningful changes,
returning/seasonal patterns, cautious anomalies, useful summaries, and
external ecological enrichment with provenance, once history is adequate to
support them.

Exit condition: the product becomes more useful as history accumulates.

### Phase 6 -- Mobile / Remote Convenience

Not started. Add Today, review, highlights, history, health, notifications,
and optional secure remote access, exposing the same authoritative local
Observation/history model rather than separate mobile truth semantics. Keep
cloud optional.

### Phase 7 -- Multi-Camera / Richer Wildlife

Not started, and explicitly gated behind stable single-camera Observation
semantics (Phases 1-3). Covers multiple cameras, camera-aware observations,
defensible duplicate handling, broader wildlife, behavioral proposals, and
richer habitat/Zone understanding.

### Phase 8 -- Learning / Contributor Ecosystem

Not started, and explicitly gated behind mature evidence and dataset
governance (Phase 2). Covers dataset creation, opt-in contribution,
candidate-model workflows, benchmark sharing, research exports, and broader
ecosystem integration.

## Explicit phase gates

- Do not broaden hardware integrations merely for coverage until at least one
  golden path is excellent.
- Do not promote a detector/classifier without reproducible incumbent
  comparison.
- Do not reduce abstention simply to produce more exact species labels.
- Do not turn model confidence into reviewed truth.
- Do not prioritize sophisticated behavioral interpretation before animal
  evidence, Visit coherence, and species-quality foundations.
- Do not prioritize multi-camera intelligence before stable single-camera
  Observation semantics.
- Do not prioritize NVR/live-video capability over useful history, review,
  evidence, and place understanding.
- Do not prioritize cloud architecture over local appliance quality.
- Do not build enterprise/fleet administration prematurely.
- Do not let unbounded field testing stall independent product development.
- Do not architect the product around the current Raspberry Pi even though it
  remains a primary validation adapter.

## Explicit deprioritization

Unless a specific task shows compelling near-term evidence otherwise, keep
these out of the critical path. This is the canonical, complete list; the
shorter identity-level version in
[product-doctrine.md](product-doctrine.md) "Product boundaries" is not a
second, separate inventory.

- NVR/security-platform expansion
- continuous-recording product focus
- elaborate live-view protocols for their own sake
- security alerts/person recognition
- broad camera integration counts as a goal
- mandatory cloud inference
- enterprise RBAC/fleet management
- social feeds
- gamification
- individual-animal identity
- premature behavior claims
- huge generic analytics dashboards
- plugin-framework construction
- model marketplaces
- broad smart-home automation

## Field-testing doctrine

Every extended field test should answer a bounded question -- for example
admission recall under a policy revision, Visit fragmentation over a defined
eligible sample, source-resolution crop benefit versus 1080p, restart
recovery under controlled failures, or classifier candidate ranking on a
representative cohort -- rather than "leave it running and see what happens"
as an indefinite roadmap phase. State the bounded question before starting;
see Tier 4 in [development-workflow.md](development-workflow.md). Independent
development continues whenever it does not depend on the unanswered field
question.

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
- Phases 24E-24G added a durable live-continuity supervisor, explicit
  Stream-scoped live-video enabling, and bounded idempotent review handoff,
  without automatic truth creation.
- Phase 25 hardened restart recovery and storage/retention and ran the first
  representative field-acceptance campaigns; its unattended-operation goal
  now defines the Phase 1 exit gate, above.
- Phase 26A-26B added the optional local BioCLIP species-suggestion adapter
  and a default-off automatic post-activity assist; representative
  species-level correction truth to validate its accuracy remains
  uncollected (Phase 2, above).
- Phase 27A delivered first-run setup and a self-contained Windows
  "unpack and run" bundle; native Windows hardware acceptance and
  update/recovery polish remain open (Phase 4, above).
- Observation Engine v2 (Stages 1-7, Product Vertical Slice v1, Unified
  Observation Experience v1) replaced the timer-driven snapshot observer
  with a provider-neutral, evidence-only detection/tracking/evidence-scoring
  pipeline and one bounded, default-off candidate-Visit authority mode
  reachable through a per-Stream Start/Stop Observation control, hardened
  through repeated real Camera Node field campaigns.
- Two real-hardware defects found after the above were fixed: Camera Node
  pairing repair could reject a valid unconsumed code, and starting
  Observation could collide with an already-running legacy live-view session
  for the same camera.
- Camera Health and Guided Camera Editing expose saved operational state,
  safe in-place compatible camera configuration, redacted change previews,
  and bounded revision history without changing the evidence/review truth
  boundary.
- The optional MockingBird Camera Node is a paired local-LAN snapshot adapter
  beneath the same Source/Stream/Zone/monitoring/review loop. It remains
  no-cloud, no-discovery, and no-truth.

See [roadmap-history.md](roadmap-history.md) for the concise phase record.

## Cross-cutting roadmap invariants

- Source adapters remain underneath Sources, Streams, Zones, Activity
  Sessions, Visits, review/correction, analytics, and exports.
- MediaAssets, MotionEvidence, DetectionProposals, SpeciesSuggestions, and
  external labels remain evidence/context until explicit correction; unknown
  and abstained outcomes are valid, not defects.
- Read/status/preview/dry-run routes are side-effect free. Writes are explicit,
  scoped, bounded, and tested.
- Privacy and Ignore Zones, local storage, retention, backups, and safe restart
  behavior are first-class constraints.
- Workers and durable monitoring default off, are observable and safely
  stoppable, and cannot create reviewed truth.
- Model runtimes, training dependencies, generated datasets, captured media,
  benchmark artifacts, and caches require explicit scope and ignored local
  paths.
- A candidate detector/classifier does not gain production authority without
  reproducible incumbent comparison (Phase 2).
- Track engineering truth and user value as two distinct scorecards, and
  measure whether an algorithmic component earns its cost; see "Two
  scorecards" in [product-doctrine.md](product-doctrine.md).
- Each implementation task uses the task packet and validation tiers in
  [development-workflow.md](development-workflow.md).

## Roadmap non-goals

- No one-shot repository rewrite or coverage-percentage target.
- No cloud dependency or telemetry requirement for the core product.
- No new administration page merely for lifecycle or engineering controls.
- No provider, audio, camera-integration-count, or unrelated automation
  expansion ahead of the current Phase 1 gate without explicit evidence and
  scope; see "Explicit deprioritization," above, for the complete list.

## WSL activation checkpoint

The active development checkout is WSL-native at
`/home/zkelder/projects/mockingbird-active`. A locally configured Windows
`ffmpeg.exe`, native DirectShow controls, fresh live frames, and a daylight
3840 x 2160 capture have been verified from WSL, and the packaged
Windows/CUDA product has been run and debugged against real passed-through
GPU hardware from this sandbox. Driver-managed exposure values remain outside
MockingBird and are neither readable nor persisted. This checkout remains a
development environment fact, not a product architecture constraint -- see
"Do not architect the product around the current Raspberry Pi" and the
equivalent Windows-development caution in "Explicit phase gates," above.
