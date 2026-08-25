# MockingBird Release Execution State

This file controls execution sequencing, not product doctrine.
[product-doctrine.md](product-doctrine.md) defines what MockingBird is.
[roadmap.md](roadmap.md) preserves the full roadmap. This file records
current accepted state, remaining lanes, release classification, and what
work is presently authorized.

Claude's "next natural milestone" suggestions are advisory only. They do
not authorize future work.

## CURRENT PHASE: SUBSTANTIAL PRODUCT DEVELOPMENT

MockingBird is still in substantial product development. Representative
Field Acceptance, External Beta, and Final Release Hardening (Lanes R/S,
below) are downstream gates and must **not** become the default next
milestone while substantial product-roadmap capability remains
intentionally unfinished -- see §6, "Global remaining execution queue,"
for the complete remaining-capability picture this phase label is
protecting.

## 1. Current accepted state

- **Repository:** `/home/zkelder/projects/mockingbird-active`
- **Branch:** `main`
- **Accepted HEAD:** `1ba76b0`
- **Schema:** `v53`
- **Latest accepted milestone:** Place / Yard Intelligence v2 -- Changes,
  Trends & Actionable Understanding (see
  [place-yard-intelligence-v2-report.md](place-yard-intelligence-v2-report.md)).
  Classification **B** -- major useful capability, bounded maturity gaps
  (real accumulated history too young to validate new thresholds against;
  see the report's "Major remaining PRODUCT opportunities").
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

**NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED.**

Place / Yard Intelligence v2 (directly authorized outside this file,
reconciled here at its own closure -- see §16) is now accepted at
classification **B** (major useful capability, bounded maturity gaps --
see
[place-yard-intelligence-v2-report.md](place-yard-intelligence-v2-report.md)).
Camera / Source Experience & First-Hour Setup Closure v1 remains accepted
and closed at classification **C** (usable, bounded further closure
remains -- see Lane G, §6). No new implementation milestone is currently
authorized. The next milestone will be selected only after the governing
external process verifies this execution state against the complete
remaining-v0.1 queue **and** the remaining Place/Yard Intelligence product
opportunities (seasonality maturation against real history, weather/
habitat-change data-model decisions, a `source_quality_signals` UI
surface -- see the v2 report). Do not choose the next milestone by
adjacency to this one.

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

**Biodiversity & Place Intelligence.** Accepted; extended, not frozen --
Place / Yard Intelligence v2 (2026-08-25) added regularity narrative,
seasonal pattern, temporal pattern, per-Source activity/quality, and a
weekly digest on top of the already-accepted foundation. Substantial
product-roadmap opportunity remains (weather association, habitat
before/after change comparison, year-over-year seasonality -- see
[place-yard-intelligence-v2-report.md](place-yard-intelligence-v2-report.md)
"Major remaining PRODUCT opportunities"); do not treat this lane as
closed.

**Camera / Acquisition Foundations.** Substantial accepted work: native
Camera Node path; ONVIF; RTSP/RTSPS; offline/recorded ingest; camera-trap
ingest; provider-neutral Source/Stream architecture. First-hour product
experience materially closed (Add Camera preview, credential honesty) --
see Lane G.

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

**Status:** PARTIAL, MATERIALLY CLOSED -- v0.1 CRITICAL. Camera / Source
Experience & First-Hour Setup Closure v1 (2026-08-25) fixed two real P0
first-hour gaps and two P1s; see
[camera-source-experience-v1-report.md](camera-source-experience-v1-report.md)
for the full archaeology, gap table, and evidence. Release
classification: **C** (usable, bounded further closure remains).

Closed by this milestone: manual RTSP setup's separate "Auth username"/
"Auth password" fields were collected but silently discarded on every
write and never reached a real connection attempt -- now stored for real
and merged into the effective connection URL everywhere it's actually
used. Only Camera Node had a real "Check the picture" setup preview --
now RTSP/ONVIF/local/Windows-USB have the same bounded, non-persisting
preview capability, and `CameraSetupValidationResponse.preview_available`
is computed honestly instead of hardcoded `False`. A healthy camera's own
detail page had no persistent way back to reconfigure it; a dead,
unreachable duplicate Add-Camera form was removed.

Remaining, not closed by this pass: ongoing-monitoring failure-code
collapse for non-Camera-Node providers (once a Stream is armed and
running, a dead RTSP/local/Windows process's specific cause -- auth/
network/codec/decode -- is discarded in favor of a generic code; setup-
time validation is unaffected and stays fully distinguishing). No real,
reachable camera/RTSP/ONVIF/local-USB hardware or Camera Node was
available to prove actual video decode/preview end-to-end this session
(native-Windows evidence proves the real subprocess/HTTP/taxonomy/
credential-merge mechanics genuinely work against a real unreachable
host, not that a specific real camera's picture renders). Full
integrated multi-camera/whole-product acceptance remains Lane R.

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

**Status:** PARTIAL -- v0.1 CRITICAL. Host side substantially closed by
Release Engineering Foundation v1 (2026-08-25); Camera Node side remains
open.

Closed for the **Host**: an automatic, verified pre-migration safety
backup now runs before any in-place schema upgrade; a genuine post-
migration health check gates readiness; the upgrade fact is honestly
surfaced (console + Dashboard); restoring that automatic backup is the
documented rollback path; interrupted-upgrade behavior (backup failure,
mid-migration failure, post-migration integrity failure) all fail closed
and are regression-tested; real native-Windows evidence includes an
organically-occurring 18-schema-version migration on real pre-existing
data. Host↔Camera Node **wire-protocol** version compatibility
(`api_version`, `transport_protocol_version`) confirmed already
hard-gated; the Node's own `service_version` remains display-only by
deliberate choice (see the milestone report).

Remaining: a Camera Node **upgrade** workflow specifically (as distinct
from the already-accepted Camera Node install/reboot/reprovision
hardening); reinstall/replacement beyond what reprovisioning already
covers; broader operator-facing update/recovery UX. See
[release-engineering-foundation-v1-report.md](release-engineering-foundation-v1-report.md).

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

**Status:** SUBSTANTIALLY CLOSED, two items deliberately left open --
v0.1 CRITICAL. Release Engineering Foundation v1 (2026-08-25) closed:
upgrade procedure (see Lane L); a real, currently-live dependency-closure
defect found and fixed via genuine native-Windows deployment (`astral`
missing from the packaged bundle -- would have broken *every* launch,
clean-install included) plus a regression test against the whole class of
drift; version single-source-of-truth; artifact provenance/checksum
parity with the Camera Node build script (`source_clean`); an independent
post-build artifact verifier (`scripts/verify_release_artifact.py`); this
repository's first CI automation (`.github/workflows/ci.yml` -- Core
gate, frontend build, a real structural packaging-smoke build);
`SECURITY.md`; release-artifact smoke testing; Host ↔ Camera Node
compatibility (investigated and confirmed adequate, not a gap). See
[release-engineering-foundation-v1-report.md](release-engineering-foundation-v1-report.md)
for the complete record, including real native-Windows acceptance
evidence (Decision A).

Deliberately still open, not silently dropped: **`LICENSE`** (a
business/legal decision -- which license, and its interaction with the
still-unresolved BirdNET commercial-adjacent-distribution question in
§2, above -- outside a bounded engineering milestone's authority to
resolve unilaterally); **full ffmpeg bundling** (needs its own licensing
research, shaped like the already-completed BirdNET work -- today it is
honestly documented as a separate install step rather than silently
missing, and the recommended Camera Node golden path does not need it).
Public-repo hygiene beyond `SECURITY.md`/`CONTRIBUTING.md` (README/site
polish, brand/trademark review) remains open per "Public release
readiness" in [roadmap.md](roadmap.md), not v0.1-CRITICAL blocking.

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

**Representative Field Acceptance & Release-Budget Closure v1 (2026-08-25)
attempted, returned Gate C -- OPEN, insufficient representative evidence.**
Not a product defect: the attempt was stopped before any Observation
session started because the native-Windows dev instance now enforces real
sign-in on every endpoint the session needed (streams, observation start/
stop, Visits, counterfactual ledger -- the pytest auth bypass was removed
as part of the accepted Local Identity / Multi-User work, 2026-08-23),
no credentials exist anywhere in this repository, and the user explicitly
declined to share real admin credentials, create a temporary account, or
participate live right now. Nothing about the frozen perception/admission/
Visit/evidence/classification stack was exercised or judged. Real,
positive, non-live evidence preserved from this attempt: the reference
Camera Node (`192.168.1.112:8787`) is reachable at the network level; the
native-Windows Host dev deployment is healthy at the accepted commit
(schema v53); the full accepted acceptance-tooling chain (recorder,
motion-screen/contact-sheet review, independent encounter table,
counterfactual ledger, `run_encounter_accounting.py`) is confirmed present
and ready to reuse. See
[representative-field-acceptance-release-budget-v1-report.md](representative-field-acceptance-release-budget-v1-report.md)
for the full record, including the standing decision for future sessions:
do not ask the user again for real credentials or live participation
unless a future milestone specifically requires human acceptance and they
explicitly agree first; ordinary auth-requiring development/validation
work should instead use a fresh, isolated dev instance with a disposable
bootstrapped local Administrator account.

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

**Latest accepted Core checkpoint (Place / Yard Intelligence v2):** 4791
passed / 2 failed / 2 skipped / 23 deselected (slow-marked) / 11 xfailed
(28m23s). The 2 failures are the identical, already-documented
`test_place_biodiversity_summary_repository.py` pair immediately below --
re-confirmed via a fresh `git stash` bisection against the clean `731ee30`
baseline this same session. 173 new pure-module tests added (all passing,
zero bugs found in the modules under test); 46/46 targeted Playwright e2e
tests passed after fixing one real regression found live (a pre-existing
mock fixture predating a new additive response field -- see the milestone
report).

**Prior accepted Core checkpoint (Camera / Source Experience &
First-Hour Setup Closure v1):** 4648 passed / 2 failed / 2 skipped / 11
xfailed. The 2 failures
(`test_place_biodiversity_summary_repository.py`, an unrelated
historical-status timing case) reproduced identically against the clean
`74c192a` baseline via `git stash` bisection -- confirmed pre-existing
flakiness, not a regression.

**Prior accepted Core checkpoint (Release Engineering Foundation v1):**
4633 passed / 0 failed / 0 errors. (A first full run showed 2 teardown
errors in an unrelated file; root-caused via clean-baseline bisection to
a pytest fixture-teardown-ordering interaction this milestone's own
`tests/conftest.py` change triggered, fixed at the source -- see the
milestone report's "Validation commands/results.")

**Prior accepted Core checkpoint (Acoustic milestone):** 4608 passed / 0
failed.

**Prior accepted Full checkpoint:** 4629 passed / 2 failed. Both failures
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

- **Accepted HEAD:** `1ba76b0`
- **Schema:** v53 (unchanged)
- **Latest accepted milestone:** Place / Yard Intelligence v2 -- Changes,
  Trends & Actionable Understanding
- **Place / Yard Intelligence v2 classification:** B -- major useful
  capability, bounded maturity gaps. Six new pure analytics modules
  (regularity narrative, seasonal pattern, conditional/habitat
  association, temporal pattern, source activity/quality) composed onto
  the existing Gate C / Biodiversity foundation; a weekly digest reusing
  the existing daily-digest ranking unmodified. Zero schema migration.
  173 new tests, zero bugs found in any new module; Core 4791 passed / 2
  failed (both the pre-existing, re-confirmed
  `test_place_biodiversity_summary_repository.py` pair below) / 2 skipped
  / 11 xfailed; 46/46 targeted e2e passed. See
  [place-yard-intelligence-v2-report.md](place-yard-intelligence-v2-report.md)
  for the full record, including recorded future dependencies (weather
  association, habitat before/after change comparison, a structured
  Feeder entity, true year-over-year seasonality) deliberately not built
  by adjacency.
- **Camera / Source Experience release classification:** C -- usable,
  bounded further closure remains (ongoing-monitoring failure-code
  collapse; no real reachable camera/RTSP/ONVIF/local-USB/Camera-Node
  hardware exercised this session). See
  [camera-source-experience-v1-report.md](camera-source-experience-v1-report.md).
- **Native-Windows acceptance (this milestone):** real deployment of the
  exact commit (confirmed via `/api/product/instance`), plus a second,
  genuinely fresh isolated instance exercised end-to-end (real
  administrator creation, real sign-in, real ffmpeg 8.1.2 subprocess
  against an intentionally unreachable RTSP host, honest
  `preview_available`, correct credential masking, no leak) -- not a
  full physical-camera acceptance; see the report's Section 6/9.
- **Prior Native-Windows acceptance (Release Engineering Foundation v1):**
  Decision A -- real deployment, a real packaging defect found and fixed,
  a real organic 18-schema-version migration with verified automatic
  backup, confirmed via real HTTP. See
  [release-engineering-foundation-v1-report.md](release-engineering-foundation-v1-report.md).
- **Acoustic release posture:** Release-ready optional
- **Production detector:** MDv5a ONNX @ 0.1
- **Production visual species system:** BioCLIP-2 + Eligibility/Abstention
- **Current authorized implementation milestone:** NONE -- GLOBAL
  PRODUCT-ROADMAP RECONCILIATION REQUIRED
- **State:** Milestone-closure checkpoint
- **Final release hardening:** not authorized
- **Remote LTE/solar:** not a v0.1 blocker
- **Mobile/PWA:** not authorized
- **Local Species Prior:** not authorized
- **Another classifier campaign:** not authorized
- **LICENSE:** still genuinely absent -- open business/legal decision, not
  resolved by this milestone (see Lane P, above)
- **Representative Field Acceptance (attempted 2026-08-25):** Gate C --
  OPEN, insufficient representative evidence; deferred by explicit user
  decision before any live session started (real-authentication/consent
  boundary, not a product defect). See Lane R and
  [representative-field-acceptance-release-budget-v1-report.md](representative-field-acceptance-release-budget-v1-report.md).
  Untracked root `uv.lock` investigated (no git history on any branch, no
  `.gitignore`/`pyproject.toml`/CI/CONTRIBUTING convention, absent from all
  sibling worktrees -- clearly incidental) and removed per this milestone's
  own Decision A; working tree returned to exactly the seven preserved
  files.
- **Push:** explicit authorization required
