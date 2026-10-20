# Pre-1.0 Software Gap Audit & Contract Lock v1

**Status:** completed 2026-09-29. **Type:** documentation-only global
sequencing audit. **Starting HEAD:** `2f7f35f`. **Version/schema:** `0.1.0` /
`v61`. No product code, tests, artifact, package, release tag, or external
system changed.

## Purpose and decision

The owner has chosen one complete first public release, targeted as `1.0.0`,
rather than publishing the accepted `0.1.0` candidate. This audit checks the
promoted software queue against the implementation, removes stale work, splits
the surviving work into bounded milestones, and selects the first milestone.

The result is not "everything on the historical roadmap before release."
MockingBird will complete the named work whose product contract and meaningful
acceptance can be established without inventing user, field, hardware, legal,
or third-party evidence. Product doctrine remains unchanged: Local Only is
complete, one authoritative Host owns each observatory, human-reviewed truth is
authoritative, inference stays provisional, and abstention is valid.

## Audit corrections

### Already delivered -- remove from the implementation queue

1. **Remote/intermittent-WAN transport foundation.** Commit `bf7ba27`
   already delivered durable bounded spooling, idempotent declaration/chunk/
   completion, chunk-level resume, bandwidth pacing, bounded backlog and
   eviction, a Host ledger, Doctor diagnostics, and real-socket fault-injection
   coverage for outage, reconnect, interruption, restart, flapping, and
   incompatibility. The accepted design is
   [remote-intermittent-wan-transport-v1-design.md](remote-intermittent-wan-transport-v1-design.md).
   The earlier promoted bullets for resume granularity, bandwidth policy,
   outage simulation, and low-level diagnostics are therefore stale. What
   remains is ordinary product/operator configuration and pending-sync/data-
   budget visibility; real LTE, Pi, carrier, power, and field acceptance stays
   externally gated.
2. **Evidence-honest soundscape analytics.** The stored-acoustic analytics
   named by the promoted queue already exist in
   `src/mockingbird/analytics/soundscape.py`, the
   `/api/analytics/soundscape-summary` endpoint, its web client, and focused
   repository/API tests. No additional generic "acoustic analytics" milestone
   is justified without a specific unmet product question or new field
   evidence.
3. **Precise alert navigation.** Product-alert actions already carry taxon,
   Feature, and Story-kind context into the canonical deep-dive routes. This is
   not reopened.
4. **Ecological batch selection.** Ecological Destinations already supports a
   preview followed by explicit multi-Visit selection. The remaining seam is
   Visit-to-destination preselection and exposing the filters already supported
   by the export API, not rebuilding batch selection.

Accepted detector, classifier, Visit, truth, Place-intelligence, Camera Node,
Windows-package, security, and recovery work remains frozen.

### Confirmed surviving software gaps

| Area | Repository evidence | Bounded disposition |
| --- | --- | --- |
| Attention correctness | `ProductAlertModel.read_at` and `dismissed_at` are global while notification preferences are per-user; alert mutation methods do not take a user. `AlertsControl` polls unread state while `TodayAttentionSummary` fetches it independently. `AttentionSyncService` swallows reconciliation failure without last-success/error state. | First milestone: per-user acknowledgement, one shared app-shell refresh source, model/runtime-unavailable health attention, and bounded sync diagnostics. |
| Background notification transport | `foregroundNotifications.ts` is page-level only and `web/public/sw.js` explicitly implements no push. | Separate optional milestone after attention correctness. Core Local Only operation must not depend on push or a MockingBird cloud. Real provider delivery proof remains external. |
| Everyday UX/accessibility | Visit/Stream/Settings retain dense secondary sections; the setup zone canvas at `CameraSetupPage.tsx:732` is pointer-only; raw exception copy and unused Bird Log CSS remain. | One evidence-bounded UX/accessibility closure; no redesign campaign. |
| Research/export workflow | `ResearchExportRequest.include_media` exists, but `research_export.py` deliberately fingerprints metadata rather than copying media bytes. Server-side stream/source/taxon/acquisition/collection filters exist, while the Ecological Destinations UI primarily exposes date range and manual Visit selection. | Safe media-inclusive bundles, Visit deep-link preselection, and the existing bounded filters; no live external submission. |
| Environmental measurements | Weather-derived `EnvironmentalContextRecordModel` exists, but no provider-neutral local sensor-ingest contract exists. | Sensor-ingestion foundation first: measured values, units, provenance, calibration/quality, bounded import/HTTP and optional local MQTT adapter. |
| Intervention/habitat outcomes | Place Features, phenology, change events, and comparisons exist; no durable user-authored intervention record/workflow exists. | Follow sensor foundation with reviewed intervention records and honest before/after comparison; no causal or prescriptive claim. |
| Ecosystem UX seams | The canonical roadmap still names movement/re-baseline, quality/eligibility, provider health, time-series/evidence, correction, intervention, retention, and sparse-state seams. | Audit each against then-current code after the data foundations; implement only reproduced residuals. |
| Multi-camera attribution and controls | Place Story wildlife aggregation does not preserve complete Source/Visit attribution through every canonical path; camera filter state is repeated across several product surfaces. | One attribution/grouping/filter-consolidation milestone. |
| Legacy local-camera concurrency | `durable_supervisor.py` still defaults the legacy local/RTSP pipeline to two concurrent Streams. This is separate from the Camera Node Observation Engine. | Remove or replace the arbitrary software cap with resource-aware behavior and deterministic overload tests; hardware throughput claims remain gated. |
| Remote operator experience | Transport internals are accepted, but Camera Node transport setup remains configuration-oriented and lacks one ordinary product surface for backlog/pending sync/data-budget policy. | Productize the existing foundation only; do not rewrite transport or claim LTE/Pi acceptance. |
| Multi-observatory software model | The product has local identity and one authoritative Host per observatory, but no bounded multi-observatory identity/exchange model. | Architecture-first local-instance model. No SaaS tenancy, cloud control plane, or centrally managed fleet. |
| Media-file integrity | The accepted storage closure proves DB-row-to-missing-file checks exist, but `storage-retention-disk-pressure-recovery-closure-v1-report.md:130-134` confirms no reverse media-file-to-database-owner scan. | Report/dry-run-first sampled scan, explicit exclusions, reviewed quarantine/recovery, never automatic deletion. |
| Linux end-user distribution | `docs/using-mockingbird.md:21` says Linux is a development checkout only and has no packaged unpack-and-run download. | First-class Linux Host bundle/service lifecycle and clean-host acceptance, without claiming unavailable camera/GPU hardware coverage. |
| Public product presence | Core OSS/security/contribution documents exist; the full website, deployment-profile guidance, support/community plan, public artifact inventory, and evidence-backed launch material do not. | Late pre-release documentation/site milestone. Brand, trademark, signing, and externally owned decisions remain gated. |

## Locked milestone sequence

The sequence is dependency-ordered, not permission to implement everything at
once. After each accepted milestone, the scheduler must be reconciled before
the next one is authorized.

1. **Attention Integrity & Health Reliability v1** -- authorized below.
2. **Everyday UX & Accessibility Closure v1.**
3. **Orphan Media Integrity & Recovery v1.**
4. **Research Export & Ecological Workflow Completion v1.**
5. **Environmental Sensor Ingestion Foundation v1.**
6. **Intervention & Habitat Outcomes v1.**
7. **Ecosystem UX Closure v1** -- only residuals reproduced after 5-6.
8. **Multi-Camera Attribution & Filter Consolidation v1.**
9. **Legacy Local-Camera Concurrency & Remote Operator UX v1.**
10. **Multi-Observatory Software Model v1.**
11. **Optional Background Notification Transport v1.**
12. **Linux Host Distribution & Service Lifecycle v1.**
13. **Public Product, Deployment & Support Closure v1.**
14. **Final 1.0 Hardening & Launch Candidate.**

This order puts an existing multi-user correctness defect first, closes data
integrity before adding new data domains, builds sensors before interventions,
stabilizes one-observatory multi-camera behavior before multi-observatory
exchange, and leaves platform/public packaging until the capability contract is
settled. Later items can be re-sequenced only from new repository evidence or
an explicit owner decision.

## First authorized implementation milestone

### Attention Integrity & Health Reliability v1

- **Phase:** PRE-1.0 PRODUCT COMPLETION -- SOFTWARE-FIRST.
- **Product flow:** Discover → Understand → Improve. Attention must describe
  current product state accurately and must not let one local user's action
  erase another user's unread state.
- **Why next:** the accepted product already supports multiple local users,
  while alert acknowledgement is stored globally. This is a concrete
  correctness gap in existing behavior, not speculative capability work. The
  same bounded area contains duplicated app-shell fetching, silent sync
  failure, and an absent model/runtime-unavailable health alert even though the
  underlying health facts already exist.
- **Expected compatibility shape:** schema `v62`. Alert condition, resolution,
  deduplication, and evidence remain observatory-global; acknowledgement
  (`read`/`dismissed`) becomes per-user. The upgrade must define an explicit,
  tested treatment of legacy global acknowledgement rather than silently
  resetting or sharing state.

#### Required outcomes

1. Add per-user read/dismiss persistence with uniqueness and referential
   integrity. Unread/recent reads and read/dismiss mutations use the signed-in
   current user. One user's action has no effect on another user's view.
2. Preserve observatory-global alert lifecycle and avoid copying condition,
   evidence, resolution, or deduplication state into per-user rows.
3. Replace the separate app-shell unread/recent fetch paths with one shared
   source consumed by the header/inbox control and Today summary. Inbox page
   pagination may remain independently fetched. No read endpoint gains a write
   side effect.
4. Create a sustained, deduplicated, automatically resolving Observatory
   Health alert for unavailable configured production detector/model/runtime,
   using existing runtime/Doctor facts. Its action leads to the relevant
   Doctor or Stream recovery surface. It never converts a diagnostic inference
   into Reviewed truth.
5. Record bounded attention-sync diagnostics: last attempt, last success,
   current/last error code and safe message, consecutive failure count, and a
   success/failure counter. Reconciliation remains non-blocking; the health or
   Doctor surface exposes enough state to distinguish "no alerts" from "alert
   reconciliation is failing."
6. Keep current quiet-hours, foreground notification, alert severity,
   resolution, pagination, and deep-link semantics unless a failing test shows
   a necessary compatibility correction.

#### Files in scope

Only directly affected alert persistence/migration, repository, API/auth,
attention-sync/runtime wiring, alert client/types, app-shell attention
components, health/Doctor presentation, focused tests, and this milestone's
contract/closure records. Expected areas are `src/mockingbird/storage/`,
`src/mockingbird/repository/product_repository.py`, `src/mockingbird/api/`,
`src/mockingbird/monitoring/attention_sync_service.py`, the closest runtime
wiring, `web/src/api/`, `web/src/components/AlertsInbox.tsx`,
`web/src/components/TodayAttentionSummary.tsx`, the closest health/Doctor
surface, and directly related tests.

#### Explicit non-goals

- Web Push, VAPID keys, subscription persistence, or any external push service;
- cross-camera attention grouping or broader Place Story changes;
- dense-page redesign, responsive cleanup, or zone-editor accessibility;
- detector/classifier/model/threshold/Visit/truth-policy changes;
- Camera Node, LTE, Pi, GPU, or other hardware acceptance;
- public packaging, version bump, signing, tagging, pushing, or release.

#### Validation and acceptance

Use **Tier 2 affected-subsystem validation** plus the normal Core gate because
the milestone crosses schema, auth, repository, API, runtime service, and web
state. Acceptance requires focused migration/upgrade, multi-user isolation,
repository/API authorization, deduplication/resolution, sync-failure/recovery,
frontend state, type/build, and browser tests. It also requires proof that
GET/status routes remain side-effect free, existing alert deep links still
work, and all pre-existing alert behavior outside the locked changes remains
green. No hardware validation is required or claimed.

## External boundary retained

Gate G remains waived, not passed, and the owner remains the only pre-release
tester. No item in this audit converts unavailable hardware, representative
field experience, independent-user evidence, external credentials, legal
review, signing authority, or production third-party delivery into a software
test claim. Those items remain disclosed in the external-dependency queue.
