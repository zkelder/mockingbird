# Final Product Release Scope Reconciliation v1

**Owner decision:** 2026-09-29. **Planning status:** governing release-scope
reconciliation. This document changes sequencing only; it does not authorize a
product implementation milestone by itself.

## Decision

MockingBird will not publish the accepted `0.1.0` candidate as a public
release. The first public product release is targeted as **`1.0.0`**, after
the named roadmap work that can be responsibly implemented and validated
without real users or unavailable physical hardware has been completed.

The accepted `d7e61c1` Windows artifact remains a valuable, frozen internal
baseline. It is **not** the final public release candidate. The repository may
keep its current internal `0.1.0` version during capability work; the version
changes to `1.0.0` only in the final versioning/build milestone so intermediate
builds cannot be mistaken for the public release.

"One final product release" means one complete first public launch rather than
an intentionally incomplete `0.1` launch or public beta. It does not promise
that software will never receive security, compatibility, defect, or product
updates after `1.0.0`.

Gate G remains **waived, not passed**. The owner remains the sole pre-release
tester unless that decision changes.

## Promotion rule

A named roadmap item moves before `1.0.0` when its product contract,
implementation, and meaningful acceptance can be completed with repository
code, deterministic fixtures/simulation, CI, local services, and available
packaged-host environments.

An item remains externally gated when its correctness or product meaning
requires one or more of:

- real users or independent usability/demand evidence;
- unavailable cameras, edge devices, cellular modems, batteries, power
  systems, specialized accelerators, or sustained field conditions;
- external credentials, institutional approval, app-store/provider access, or
  a third-party production service that cannot be honestly simulated;
- legal, trademark, signing-certificate, or other owner/external authority;
- representative reviewed/field evidence that does not yet exist.

The distinction is not "could somebody type code without hardware." Software
whose requirements or acceptance would be invented without external evidence
stays gated. Product doctrine, Local Only operation, Reviewed-truth authority,
abstention, and the existing explicit-deprioritization list remain in force.

## Audit result -- 2026-09-29

The required current-code audit is complete. Its evidence, bounded milestone
sequence, and first task contract are recorded in
[Pre-1.0 Software Gap Audit & Contract Lock v1](pre-1.0-software-gap-audit-contract-lock-v1-report.md).

Two parts of the provisional queue below were already delivered and are
removed rather than rebuilt:

- Remote/Intermittent-WAN Transport Foundation v1 already provides chunk-level
  resume, idempotency, bounded pacing/backlog, outage/restart fault injection,
  a Host ledger, and low-level diagnostics. Only operator-facing setup,
  pending-sync/backlog visibility, and data-budget controls survive as software
  work; real LTE/Pi/carrier/power acceptance remains external.
- Evidence-honest stored-acoustic soundscape analytics already exist. No
  further generic analytics milestone is authorized without a specific unmet
  question or new evidence.

The provisional queue remains below as the owner decision that initiated the
audit. The audit report and `release-execution-state.md` §3/§8 supersede it for
implementation scope and sequencing.

## Promoted pre-1.0 software queue

Every item below must first be checked against current repository evidence;
several historical roadmap gaps have already been closed by later milestones.
Do not rebuild an already-delivered capability merely because an older section
still names it.

### 1. Attention, mobile-web, accessibility, and everyday-product closure

- eliminate the duplicate always-mounted alert pollers;
- add detector/model-unavailable Observatory Health attention;
- add per-user read/dismiss state and an attention-sync diagnostics surface;
- complete the software side of closed-browser Web Push without making cloud
  mandatory; real provider/browser delivery proof remains externally gated;
- complete progressive disclosure on dense Visit, Stream, and Settings pages;
- close the named Zone-polygon keyboard-accessibility, raw-exception-copy, and
  dead-CSS findings;
- reconcile any remaining responsive/mobile-web density gaps. Native iOS or
  Android applications remain hardware/store gated.

### 2. Multi-camera, multi-site, and remote-operation software

- group Calm Attention facts coherently across cameras;
- populate Place Story wildlife-event Source/Visit attribution through the
  canonical aggregation path;
- consolidate the duplicated camera-filter controls;
- remove or replace the legacy motion pipeline's two-Stream cap without
  changing Observation/Reviewed-truth semantics;
- finish resumable/idempotent transfer granularity, explicit pending-sync
  state, bounded bandwidth/data-budget policy, extended-outage simulation,
  and remote-operator diagnostics on the existing local-first
  store-and-forward foundation;
- define and implement only the bounded multi-site software model that can be
  proven with isolated local instances while preserving one authoritative
  Host per deployment. SaaS tenancy and centrally managed fleets remain
  demand-gated.

### 3. Ecological, research, habitat, and land-management completion

- implement media-byte inclusion in research export bundles;
- add single-Visit preselection and the existing server-supported batch
  filters to Ecological Destinations;
- complete repository-testable interoperability/export workflow gaps that do
  not require a live destination credential;
- add provider-neutral environmental-sensor ingestion (bounded HTTP, MQTT, or
  import adapters) into the existing evidence/provenance architecture;
- add intervention records and the bounded habitat/land-management workflow
  already named by the canonical roadmap;
- complete remaining ecosystem UX seams: camera movement/re-baseline,
  sample-quality/eligibility, stale/missing provider state, sensor health,
  scheduled-media retention, evidence/time-series drill-down, correction,
  intervention, and sparse-state presentation where repository evidence shows
  they remain open;
- add only evidence-honest acoustic analytics over existing stored acoustic
  Visits. No model promotion, field calibration claim, or fabricated fusion.

### 4. Storage, platform, distribution, and public-product closure

- add orphan-media/no-database-owner detection with a report/dry-run-first,
  review/export-safe recovery path;
- produce a first-class end-user Linux distribution and automated Linux
  install/upgrade/recovery acceptance that does not overclaim unavailable
  hardware support;
- finish the repository-completable public documentation, website/project
  presence, Personal/Home and Organization/Research deployment guidance,
  support/security/community documentation, artifact inventory, and launch
  materials using real MockingBird evidence only;
- reconcile all user-facing version language to the final-product contract.

### 5. Final 1.0 hardening and launch candidate

After the promoted queue is accepted:

- re-run whole-product security, reliability, performance, accessibility,
  upgrade/recovery, Local Only, packaging, and clean-install closure;
- change the version single source of truth to `1.0.0`;
- build fresh Host and Camera Node artifacts from one clean source commit;
- run the complete Core/browser/package gates and the available native-host
  acceptance;
- publish only after the owner explicitly decides signing, tagging, pushing,
  artifact visibility, and announcement.

## External-dependency queue

These enter neither the pre-`1.0.0` implementation queue nor final-hardening
acceptance unless the missing dependency becomes available. Their absence
must be disclosed; they must not be described as passed.

- real LTE/modem/SIM/carrier acceptance and a real remote Pi deployment;
- solar/battery/BMS, power-loss/brownout, independent supervisor, CM4/CM5,
  custom carrier/PCB, and months-long unattended field operation;
- real RTSP/ONVIF/local-USB/specialized-camera coverage not already available;
- real GPU/driver multi-camera soak and physical bandwidth/power measurement;
- real acoustic unplug/replug, long field soak, natural simultaneous
  visual/acoustic encounters, and field calibration;
- site-specific learning or mature mammal identification that needs a larger
  representative reviewed field corpus;
- professional/research deployment claims, independent users, and hardware or
  user-diversity acceptance;
- native mobile device/store acceptance;
- live OAuth iNaturalist submission, direct GBIF institutional publication,
  provider-specific integrations, or other external-account workflows;
- BirdNET commercial-adjacent legal review, trademark/domain review, and a
  real signing certificate.

## Later, demand/evidence-gated work

The existing explicit-deprioritization list is unchanged. GenICam, GigE
Vision, USB3 Vision, radiometric thermal, specialized industrial cameras,
individual-animal recognition, population estimates, behavior prediction,
causal ecological modeling, provider-specific adapters, and large
cloud/fleet infrastructure remain gated by hardware, representative data, or
real demand. The fact that portions could be prototyped in software is not a
reason to invent their product contracts before that evidence exists.

## Sequencing

The software-gap audit is complete. Its fourteen bounded, dependency-ordered
milestones now control sequencing; only **Attention Integrity & Health
Reliability v1** is presently authorized. See the
[audit report](pre-1.0-software-gap-audit-contract-lock-v1-report.md#locked-milestone-sequence)
and `release-execution-state.md` §3/§8. Later steps do not self-authorize.
After every accepted milestone the global scheduler must be reconciled before
the next begins. Accepted work remains frozen except for a reproduced
dependency, correctness/security issue, or explicit authorization.
