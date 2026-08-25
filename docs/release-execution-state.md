# MockingBird Release Execution State

This file controls execution sequencing, not product doctrine.
[product-doctrine.md](product-doctrine.md) defines what MockingBird is.
[roadmap.md](roadmap.md) preserves the full roadmap. This file records
current accepted state, remaining lanes, release classification, and what
work is presently authorized.

Claude's "next natural milestone" suggestions are advisory only. They do
not authorize future work.

## 1. Current accepted state

- **Repository:** `/home/zkelder/projects/mockingbird-active`
- **Branch:** `main`
- **Accepted HEAD:** `02af3f4`
- **Schema:** `v53`
- **Latest accepted milestone:** Acoustic Productization, Licensing & Field
  Acceptance v1
- **Push state:** Local accepted state. Do not push without explicit
  authorization.
- **Production detector:** MDv5a ONNX
- **Production threshold:** `0.1`
- **Production visual species-identification system:** BioCLIP-2 +
  Identification Eligibility / Abstention

**BioCLIP 2.5.** Explicitly rejected for release promotion. Reason: it
improved positive bird identification but showed unacceptable
confident-wrong/non-abstaining behavior on real hard negatives.

**SpeciesNet.** Not production bird identification. It remains an
unpromoted broader-wildlife lead based on external-domain mammal evidence,
pending genuine MockingBird-field evidence.

## 2. Current acoustic release state

**Acoustic / BirdNET: ACCEPTED -- RELEASE-READY OPTIONAL.** The milestone
is complete and frozen unless concrete evidence exposes a defect.

Established facts:

- substantial acoustic/runtime/multimodal functionality exists;
- `birdnetlib` code is Apache-2.0;
- the BirdNET model weights used by MockingBird are CC BY-NC-SA 4.0 /
  NonCommercial;
- official MockingBird packaging must not redistribute those BirdNET model
  weights;
- a build-time guard (`verify_no_nc_licensed_acoustic_model_redistribution`
  in `scripts/build_local_product.py`) now enforces that packaging
  boundary;
- BirdNET/model acquisition remains external and optional (the
  `classifier-birdnet` pip extra -- a dependency declaration, not a
  redistribution);
- core visual MockingBird remains functional without BirdNET;
- real Windows USB microphone capture has been validated;
- real BirdNET inference over captured audio has been validated;
- concurrent visual + audio capture has been validated;
- device failure/reconnect behavior has been exercised;
- Today/Bird Log multimodal count/row contradiction was fixed;
- macOS unsupported mic behavior now fails honestly;
- the documented BirdNET confidence environment setting now actually
  works;
- an unbounded acoustic in-memory segment list was bounded.

Remaining bounded gaps -- classified as bounded product/field gaps, **not**
reasons to reopen the acoustic architecture:

- no product-facing frontend acoustic health/status surface yet;
- no true physical mid-session microphone unplug acceptance;
- no multi-hour acoustic soak;
- no natural wild-bird acoustic field session from the accepted test
  hardware;
- no audio equivalent of visual Privacy Zone redaction/exclusion beyond
  the currently documented privacy boundary.

Acoustics are optional in the first public release because of
licensing/distribution posture, not because the core implementation is
considered merely experimental.

**Licensing posture.** Commercial use of the BirdNET model weights is
**not** legally approved. Deliberately bundling/redistributing the model
into a commercially-directed distribution (paid support, a
crowdfunded/paid appliance, a hosted paid service) is not allowed under CC
BY-NC-SA 4.0 -- the clear case that license exists to restrict. Whether an
individual user's own private, non-commercial use of MockingBird+BirdNET
(the model is never redistributed by MockingBird itself) could ever be
implicated merely because the surrounding open-source project also accepts
donations or sells optional paid support remains genuinely **unresolved**;
the existing acceptance record recommends legal review before any
commercial-adjacent distribution decision actually touches the acoustic
feature, and does not resolve the question itself. This caveat is
preserved here, not relaxed.

## 3. Current authorized milestone

**NONE -- NEW PROJECT TRANSITION CHECKPOINT.**

No new implementation milestone is currently authorized. The next
milestone will be selected only after the new ChatGPT Project verifies
this execution state against the complete remaining-v0.1 queue.

Do NOT automatically authorize:

- Remote Field Productization;
- Mobile/PWA;
- Calm Notifications;
- Local Species/Taxon Prior;
- another classifier benchmark;
- Provider Integrations;
- final Release Hardening.

## 4. Product/release guardrails

MockingBird is:

- local-first;
- hardware-agnostic;
- nature-first rather than surveillance-first;
- bird-first but wildlife-native;
- evidence-backed;
- Place-centered;
- cloud-optional;
- human-correctable;
- abstention-friendly.

Canonical epistemic classes: **Measured**, **Inferred**, **Reviewed**.

Human correction is authoritative. Model inference cannot silently become
reviewed truth.

Raspberry Pi is reference Camera Node hardware, not product identity.
Native Windows remains the first end-user Host acceptance target.
WSL/Linux development success does not equal native-Windows product
acceptance.

Privacy Zones currently mean trigger-level exclusion, not guaranteed pixel
redaction of all retained frames unless future code explicitly implements
that.

User data is not the primary monetization strategy. Core functionality
must remain complete under Local Only privacy.

## 5. Frozen / substantially accepted lanes

Summarized without milestone archaeology; see `roadmap.md` and the linked
accepted-milestone docs for detail if a future task genuinely needs it.

**Observation / Reviewed Truth.** Accepted foundations include Visit →
Evidence → Review → Observation; review/correction/revision; actor
attribution; evidence lineage; Today/history truth.

**Perception / Admission.** Accepted: MDv5a production detector;
small/far-bird work; ambiguous-boundary/admission fixes; per-Stream Visit
authority; evidence-cache correction; scene-confusor suppression;
perception replay; multi-subject Visit foundations.

**Site-Specific Learning.** Accepted and frozen. Reviewed-negative
scene-confusor adaptation accumulates/evaluates reviewed evidence, is
production-disabled by default, and requires explicit per-Stream
enablement for production effect. Do not automatically build Local Taxon
Prior or calibration on top of this.

**Species Classification.** Accepted and frozen: BioCLIP-2 stays
production; BioCLIP 2.5 rejected; SpeciesNet not promoted.

**Broader Wildlife.** Accepted structurally. Non-bird review/history/
product semantics work. Automatic mammal species identification remains
limited.

**Identity / Multi-User.** Accepted: Viewer / Reviewer / Administrator;
server-side sessions; authorization; actor attribution; audit; review
concurrency; backup/restore.

**Environmental Context.** Accepted/frozen.

**Habitat & Phenology.** Accepted/frozen.

**Biodiversity & Place Intelligence.** Accepted/frozen.

**Camera / Acquisition Foundations.** Substantial accepted work: native
Camera Node path; ONVIF; RTSP/RTSPS; offline/recorded ingest; camera-trap
ingest; provider-neutral Source/Stream architecture.

**Diagnostics / Storage / Recovery Foundations.** Substantial accepted
work: health/diagnostics; Doctor/support concepts; storage health;
retention; backup/restore; recovery. Final integrated product acceptance
remains open (see Lane R, below).

**Research / Conservation.** Substantial accepted work: conservation
reporting; effort/coverage; research-safe eligibility/export; Camtrap DP;
contributor/research provenance.

## 6. Global remaining execution queue

This is the most important section. Lanes are not removed merely because
they are not next.

### A. Acoustic / BirdNET Productization

**Status:** ACCEPTED -- RELEASE-READY OPTIONAL.

Remaining bounded follow-up only: frontend acoustic health/status; longer
field soak; physical unplug/replug; natural wild-bird field evidence. Do
not schedule another acoustic architecture milestone automatically.

### B. Remote / Intermittent-WAN Field Productization

**Status:** PARTIAL -- POST-v0.1 / BEFORE-v1.0 UNLESS A NEW CORE
DEPENDENCY APPEARS.

Existing foundation includes substantial spool; store-and-forward;
transport; retry; Host consume-to-evidence behavior; diagnostics.

Remaining: real LTE/carrier acceptance; real remote Pi deployment;
bandwidth behavior; resume granularity; extended outages; unattended
recovery; remote operator experience; solar/battery/power reality.

Remote LTE/solar/custom CM4/CM5 field deployment is **not** a
first-public-v0.1 blocker.

### C. Everyday Product / Discovery UX

**Status:** PARTIAL -- HIGH v0.1 VALUE.

Remaining: Best Moments; calm daily summary; New / Regular presentation;
unknown/unresolved handling; sparse/no-wildlife states; understandable
suggestion explanations; mostly-invisible review; coherent first-hour
product experience; report-first hierarchy.

Do not turn this into a giant redesign.

### D. Calm Notifications

**Status:** OPEN -- PRE-v0.1 DECISION REQUIRED.

Need explicit decision whether first release needs them. If implemented:
meaningful change rather than raw detections; calm/digest behavior;
quiet-hours semantics where useful; no security-camera spam. Do not add
cloud push infrastructure merely to satisfy this roadmap heading.

### E. Mobile / Remote UX

**Status:** OPEN/PARTIAL -- PRE-v0.1 DECISION REQUIRED.

Distinguish: responsive web; installable PWA; secure remote access; native
mobile. Native mobile is not current scope. Do not equate responsive CSS
with full mobile support.

### F. Multi-Camera / Multi-Site

**Status:** MIXED.

Multi-camera foundations are substantial. Need integrated acceptance for:
multiple simultaneous cameras; health; backlog; performance;
duplicate/cross-camera behavior; presentation. True multi-site remains a
separate product/architecture decision. Do not silently make it v0.1
scope.

### G. Camera / Source Experience

**Status:** PARTIAL -- v0.1 CRITICAL.

Need final confidence in: Add Camera; preview; discovery/connection;
validation; credentials; capability reporting; provider-specific failure;
reconnect/recovery; user-facing health.

### H. Site-Specific Learning

**Status:** FROZEN.

No adjacent learning expansion automatically authorized.

### I. Broader Wildlife Maturity

**Status:** FROZEN STRUCTURALLY.

Real mammal field evidence remains limited. Do not create another model
campaign solely to fill the matrix.

### J. Ecological / External Workflows

**Status:** OPEN DECISION.

Potential examples: eBird-style reviewed-truth-gated workflow;
iNaturalist-style reviewed-truth-gated workflow. Do not assume existing
exports equal implemented submission workflows. Decide first-release scope
explicitly.

### K. Ecosystem / Provider Integrations

**Status:** OPEN DECISION.

Candidates previously discussed: Frigate; Blue Iris; Scrypted; Home
Assistant. Do not implement all. Decide whether a minimum useful adapter
set materially improves first-release adoption. Native Camera Node +
standards-based acquisition remain the golden path.

### L. Appliance / Update / Recovery

**Status:** PARTIAL -- v0.1 CRITICAL.

Remaining: Host upgrade workflow; Camera Node upgrade workflow; version
compatibility; rollback; interrupted update recovery; reinstall;
replacement; migration behavior; operator-facing update/recovery UX.

### M. Storage / Retention UX

**Status:** PARTIAL -- v0.1 CRITICAL.

Need integrated acceptance under: disk pressure; long-running storage
growth; cleanup; retention; DB/media consistency; backup visibility;
recovery. NAS/external-storage support remains an explicit product
decision, not an automatic blocker.

### N. Privacy / Contribution

**Status:** PARTIAL -- LOCAL-ONLY v0.1 CRITICAL.

**Local Only.** Operational/default requirement. Core product must be
complete.

**Derived Data Contribution.** Doctrine exists. Do not assume operational
implementation or cloud backend exists. Never silently include:
image/video/audio; thumbnails/crops; raw frames; embeddings/reconstructable
media-derived features; local filesystem paths; free-text notes;
faces/people/vehicle imagery; precise property/home coordinates.

**Media contribution.** Separate future consent capability. Contribution
must never become required for core operation.

### O. Platform / Runtime Portability

**Status:** PARTIAL -- RELEASE DECISION REQUIRED.

Track honestly: native Windows; Linux; macOS; CPU; NVIDIA CUDA; Apple
Silicon; AMD. Use capability states: directly validated; structurally
supported; hardware-unverified; unsupported; deferred. Native Windows
remains the first end-user Host acceptance target. Do not claim
Apple/AMD support merely because an underlying ML framework theoretically
supports it.

### P. Release Engineering Foundation / Distribution

**Status:** NOT FULLY CLOSED -- v0.1 CRITICAL.

Remaining: clean-machine installation; normal native-Windows user path;
frontend packaging; dependency closure; model acquisition; checksums;
versioning; CI; OSS licensing/notices; SECURITY documentation; upgrade
procedure; Host ↔ Camera Node compatibility; public-repo hygiene;
release-artifact smoke testing.

Release Engineering Foundation may occur before all product development is
finished. Release Engineering Foundation is not the same as final Release
Hardening.

### Q. Whole-Product UI / Accessibility / Performance

**Status:** NOT CLOSED AS AN INTEGRATED PASS -- v0.1 CRITICAL.

Eventually validate: responsive behavior; touch; keyboard; focus;
accessibility; evidence/image loading; large histories; several cameras;
large review queues; long sessions; CPU/GPU/storage-pressure presentation;
error/recovery UX; visual consistency. Includes the bounded acoustic
health/status gap (Lane A).

### R. Complete Field Acceptance

**Status:** NOT DONE -- v0.1 CRITICAL.

Component acceptance is not whole-product acceptance. Final integrated
release configuration should exercise: several cameras; visual inference;
audio if included; review; Today/history; long unattended operation;
disconnect/reconnect; Host reboot; Camera Node reboot; storage pressure;
model unavailable; backup/restore; upgrade; clean installation; actual
user operation. Remote LTE field acceptance remains separately scoped when
Remote Field is not part of v0.1.

### S. Actual Final Release Hardening

**Status:** LAST.

Only after intended v0.1 capability scope stabilizes. Then freeze major
features and focus only on: defects; reliability; performance; security;
dependency/license closure; packaging; clean-install repetition;
upgrade/uninstall; documentation; compatibility; field failures; beta;
release candidate; public OSS release. Do not add major new capabilities
during this phase without explicit authorization.

## 7. First-public-v0.1 doctrine

The first public release target is a trustworthy single-site/home
observatory with:

- dependable visual observation;
- strong Visit/evidence quality;
- reviewed Observation truth;
- Today/history usefulness;
- native Camera Node golden path;
- ONVIF + RTSP/RTSPS;
- offline/recorded/camera-trap ingest;
- professional/research acquisition metadata;
- conservation reporting;
- effort/coverage;
- research-safe export;
- Camtrap DP;
- bounded contributor/research capability;
- Local Only privacy;
- installation/onboarding/recovery;
- diagnostics;
- storage;
- backup;
- versioning;
- security;
- OSS/release presentation;
- clean-install acceptance;
- integrated field acceptance.

Acoustics may ship as the now-accepted optional capability. Remote
LTE/solar/custom field hardware are not v0.1 blockers.

## 8. Post-v0.1 / before-v1.0 queue

Explicitly keep:

- complete remote/intermittent-WAN/LTE field deployment;
- solar/battery;
- custom CM4/CM5 hardware;
- research-grade remote-field acceptance;
- broad multi-site;
- native mobile;
- advanced acoustic analytics;
- mature automatic mammal species identification.

Unless new evidence creates a dependency, do not promote these into v0.1.

## 9. Later / demand-driven queue

Examples:

- GenICam;
- GigE Vision;
- USB3 Vision;
- radiometric thermal;
- specialized industrial cameras;
- individual-animal recognition;
- population estimates;
- behavior prediction;
- causal ecological modeling;
- large cloud-first infrastructure.

## 10. Observability cross-cutting requirements

Keep visible as v0.1 requirements:

- structured error taxonomy;
- stable machine-readable codes;
- user-safe messages/actions;
- component attribution;
- recoverability;
- correlation/session identifiers where applicable;
- structured bounded logs;
- health transitions;
- reconnect/drop/failure counters;
- Visit/model/storage/coverage counters;
- support bundles;
- no uncontrolled raw/high-cardinality media telemetry.

Normal users get actionable diagnostics. Advanced support gets raw
details.

## 11. API / schema / version compatibility

Preserve:

- externally consumed schema/version discipline;
- additive compatibility where feasible;
- migration safety;
- Host ↔ Camera Node compatibility;
- upgrade/recovery semantics;
- explicit capability/version reporting.

Do not casually make breaking changes merely because all local tests can
be updated together.

## 12. Security / release questions

Keep visible:

- network exposure;
- HTTPS/TLS posture;
- secure remote-access decision;
- secret/credential storage;
- dependency/model supply chain;
- checksum/update verification;
- support-bundle disclosure;
- public SECURITY policy.

Do not claim encrypted camera/RTSP/ONVIF credentials at rest unless
current code proves it.

## 13. Development operating rules

**Bounded archaeology.** Start with governing docs and directly affected
code. Expand only when evidence reveals dependencies.

**Separate investigation and implementation.** When uncertainty is real:
(1) diagnose; (2) lock the contract; (3) implement.

**Validation tiers.** Tier 1: focused tests. Tier 2: affected subsystem
validation. Tier 3: full Core only when cross-cutting production risk
warrants it.

**Audit budget.** Default: one implementation/self-review; one acceptance
review. Additional audits require a concrete unresolved risk.

**Concurrent writers.** Never allow multiple Claude writer sessions in the
same working tree. Separate worktrees are required for parallel
implementation. Read-only agents are fine.

**Git.** Do not push without explicit user authorization. Protect the
seven preserved files (see below).

### Preserved untracked detector files

These seven known superseded/untracked detector files must remain
untouched -- not edited, deleted, renamed, staged, incorporated, or
cleaned up -- by any task working in this repository:

- `docs/wildlife-detector-training-contract.md.orig`
- `scripts/evaluate_small_bird_detector.py`
- `scripts/materialize_wildlife_stage2.py.orig`
- `scripts/train_wildlife_stage2_rfdetr.py.orig`
- `src/mockingbird/detectors/small_bird_benchmark.py`
- `src/mockingbird/training/wildlife.py.orig`
- `tests/test_small_bird_benchmark.py`

They duplicate the accepted `multi_scale_strategy.py`/
`multi_scale_benchmark.py` work and were left uncommitted on purpose
rather than cleaned up; re-verify their presence untouched at the start of
each session that touches this repository.

## 14. Validation baselines

**Latest accepted Core checkpoint (Acoustic milestone):** 4608 passed / 0
failed.

**Latest accepted Full checkpoint:** 4629 passed / 2 failed. Both failures
were in unrelated Camera Node real-subprocess tests and reproduced
identically on the clean baseline.

These counts are historical accepted checkpoints, not immutable future
expected totals.

## 15. Update protocol

At each accepted milestone closure, update only the delta:

- accepted HEAD;
- schema if changed;
- latest accepted milestone;
- affected lane status;
- newly discovered blocker;
- current validation checkpoint if applicable;
- field acceptance state;
- current authorized milestone only when explicitly authorized after
  global reconciliation.

Never copy a Claude "next natural milestone" suggestion directly into the
authorization field.

## 16. Transition checkpoint

- **Accepted HEAD:** `02af3f4`
- **Schema:** v53
- **Latest accepted milestone:** Acoustic Productization, Licensing &
  Field Acceptance v1
- **Acoustic release posture:** Release-ready optional
- **Production detector:** MDv5a ONNX @ 0.1
- **Production visual species system:** BioCLIP-2 + Eligibility/Abstention
- **Current authorized implementation milestone:** NONE
- **State:** New ChatGPT Project transition checkpoint
- **Final release hardening:** not authorized
- **Remote LTE/solar:** not a v0.1 blocker
- **Mobile/PWA:** not authorized
- **Local Species Prior:** not authorized
- **Another classifier campaign:** not authorized
- **Push:** explicit authorization required
