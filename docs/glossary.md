# MockingBird Glossary

Where current implementation vocabulary and the target doctrine chain in
[product-doctrine.md](product-doctrine.md) (Source → Stream → Zone → Activity
Session → Visit → Evidence → Detection Proposal → Interpretation → Review
Decision → Observation → Export/Analytics) diverge, each entry below names
both. Renaming schema, API, or UI to the doctrine vocabulary is a future
implementation task, not something already done.

## Camera

A user-facing outdoor camera concept.

## Source

An adapter-backed input that can provide video, images, clips, or stream data.

## Source Provider Configuration

Safe metadata describing the intended provider contract for a Source. It is not a
provider implementation, connection attempt, evidence, or reviewed truth.

## Camera Node

A separately started local-LAN edge adapter that advertises sanitized local
camera views and serves authenticated bounded snapshots to one paired
MockingBird Source. It is not a second product database, monitor policy, review
system, model runtime, retention service, cloud relay, or remote shell.

## Manual Media Source

A Source/provider path for explicit local media import into Stream and Zone
context. Imports can create reviewable Events/Visits, but corrections remain the
source of truth.

## Folder / Trail-cam Import Provider

A Source provider configuration/status contract for future explicit local
folder, SD-card dump, NAS folder, or exported image batch import. The current
implementation stores redacted setup intent and supports an explicit dry-run
preview plus explicit import to MediaAssets only. It is not live playback, a
watcher, polling loop, evidence, Events/Visits, or reviewed truth.

## Folder Import MediaAsset

A supported image copied from a configured folder/trail-cam Source into local
MockingBird media storage through explicit user action. It has safe relative
source provenance and Stream context, but it is not MotionEvidence, an
Event/Visit, or reviewed truth.

## Folder Import UI

The Streams page surface for explicitly previewing configured folder candidates
and importing previewed files as MediaAssets only, dry-running evidence handoff
for imported items, and confirming eligible pending-evidence creation. It does
not watch folders, provide live playback, create Events/Visits, or create
reviewed truth.

## Folder Import Evidence Handoff

An explicit action that can turn one folder-imported MediaAsset into pending
MotionEvidence with attached media context. It does not create Events, Visits,
ReviewLabels, or reviewed truth.

## Folder Import Batch Evidence Dry-run

A read-only report over already-imported folder MediaAssets that shows which
items would be eligible for pending MotionEvidence and which would be skipped.
It creates no MotionEvidence, Events, Visits, labels, or reviewed truth.

## Batch Folder Evidence Creation

A confirmed action that creates pending MotionEvidence for eligible
folder-imported MediaAssets from the batch dry-run boundary. It creates no
Events, Visits, ReviewLabels, reviewed status, or truth.

## Folder Import Evidence

Pending MotionEvidence created from one folder-imported MediaAsset or a
confirmed eligible batch. It points to the imported MediaAsset as
`snapshot_media_asset_id`, can show safe folder-import provenance and attached
media in review UI, and remains evidence until explicit promotion and later
review/correction.

## Source Connection Status

A read-only product contract describing Source provider readiness and related
Streams. It is not a provider implementation, evidence, or reviewed truth.

## Source Adapter Boundary

The design boundary that keeps real provider code underneath Source connection
and Stream playback contracts. It prevents adapters from creating truth,
skipping review, leaking secrets, or redefining the product flow.

## Provider Smoke Flow

Automated backend validation that an implemented provider path stays under the
Source/Stream contract: status routes are read-only, provider work requires
explicit user action, MediaAssets and MotionEvidence are evidence/context only,
and ReviewLabel correction is the first reviewed truth write.

## Provider Workflow

A Source/provider path shown as setup readiness, playback honesty, zone-editing
availability, and the next explicit user action. It is product status, not
provider execution.

## Next Action Cue

A read-only UI prompt that sends the user to an explicit workflow such as
Streams, Import Media, Motion Evidence, Retention, or Review. It does not run
providers, create evidence, or create reviewed truth.

## Today in Your Yard

The bounded, read-only daily Dashboard projection for detector-qualified animal
Visits, reviewed birds and species, evidence-backed best moments, first
confirmed species, recent regulars, Zone/hour activity, confirmation work, and
compact observation health. Detector and SpeciesSuggestion evidence can guide a
Visit into this surface, but only explicit correction counts as confirmed truth.

## MVP Readiness Overview

A read-only Dashboard summary of current provider workflows, support level, next
safe action, live playback status, evidence/review state, and correction/export
readiness. It does not fetch URLs, scan folders, process webhook payloads,
create media, create evidence, promote Events/Visits, or create reviewed truth.

## Onboarding Surface

A read-only first-run or sparse-data UI surface that explains the next safe
MockingBird action. It can point to Streams, Import Media, Motion Evidence,
Review Queue, Analytics, Exports, Classifier Readiness, or Retention, but it
does not run providers, create evidence, promote review context, or write truth.

## Empty State

Copy shown when a list or report has no current records. In MockingBird, empty
states should explain the product path and truth boundary instead of treating
missing data as an error.

## External URL Still-image Provider

An `external_url` Source provider contract for explicit HTTP still-image
preview/status. It is not RTSP, continuous video, a worker, evidence, or reviewed
truth.

## Generic Webhook Provider

A Source provider configuration/status contract for local systems that may
submit media or event candidates into MockingBird later through
`webhook_future`. The current layer stores metadata and redacted shared-secret
readiness, explicit payload validation/dry-run, and confirmed metadata motion
payloads to pending MotionEvidence only. It has no media ingest endpoint, no
real auth/token generation, creates no Events/Visits or truth, and must not
treat incoming labels, detections, or events as reviewed truth.

## Webhook Payload Validation

An explicit dry-run API for `webhook_future` Sources that checks generic payload
shape and Source/Stream/Zone context. It can report candidate mappings such as
heartbeat, motion event, object detection, species suggestion, or media
reference, but it creates no records, fetches no media, authenticates no
payloads, and writes no reviewed truth.

## Webhook Motion Evidence

Pending MotionEvidence created from an explicit confirmed metadata-only webhook
motion payload. It preserves safe webhook provenance, untrusted external
label/confidence metadata, and Stream/Zone context, but creates no MediaAsset,
Event, Visit, ReviewLabel, or reviewed truth.

## Webhook Provider Smoke Flow

Backend smoke coverage for the metadata-only `webhook_future` path:
configuration/status and playback stay read-only, validation dry-run creates no
records, confirmed motion ingest creates pending MotionEvidence only, explicit
promotion creates Event/Visit context only, and correction creates reviewed
truth.

## Still-image Preview

A transient, explicit image preview fetched from an `external_url` Source. It is
not saved media, live playback, evidence, an Event/Visit, or reviewed truth.

## Saved Preview MediaAsset

An explicitly saved still-image preview linked to Source/Stream context. It is
local media context, not MotionEvidence, an Event/Visit, or reviewed truth.

## Saved Preview Evidence Handoff

An explicit action that turns a saved preview MediaAsset into pending
MotionEvidence. The Motion Evidence UI can show its attached saved media and
safe provenance, but it does not create Events, Visits, ReviewLabels, or truth.

## Saved Preview Retention

The future policy/reporting layer for deciding how saved preview MediaAssets are
kept, archived, or cleaned up without silently deleting reviewed truth or
breaking MotionEvidence/Event/Visit provenance.

## Retention Report

A read-only saved media summary that lists saved preview MediaAssets, linkage,
size metadata, warnings, and cleanup risk. It does not delete files, delete
records, fetch URLs, create evidence, or mutate truth.

## Cleanup Dry Run

A read-only preview of what a future cleanup action might affect. It reports
candidate files or records and protected skips, but deletes nothing and changes
no review truth.

## Saved Media Retention UI

A frontend view of saved preview media retention status, risk levels, warnings,
cleanup dry-run results, and confirmed low-risk file cleanup. It must not delete
records or reviewed truth.

## File-only Cleanup

An explicit local storage action that deletes an eligible saved preview media
file while leaving the MediaAsset record, evidence, Events, Visits, labels,
exports, and reviewed truth intact.

## Retention Risk Level

A cleanup classification for saved media, such as low, medium, high, or
protected, based on whether the MediaAsset is unlinked, attached to evidence,
promoted into Event/Visit context, or linked to reviewed correction truth.

## Source Setup Review

A read-only product summary of provider configuration, Source connection
readiness, and related Stream playback readiness. It does not connect, capture,
decode, create evidence, or write reviewed truth.

## Readiness Level

A user-facing setup state such as demo ready, metadata ready, needs setup, future
adapter required, or unavailable.

## Stream

The central video experience shown in the app.

## Stream Playback Status

A read-only product contract describing whether a stream can show a demo panel,
placeholder, preview, or future playback surface. It is not evidence or reviewed
truth.

## Zone

A user-drawn area on a stream that gives outdoor activity context.

## Feeder Zone

A zone around a bird feeder.

## Birdbath Zone

A zone around a birdbath or water source.

## Privacy Zone

A zone whose activity does not independently trigger detection, capture, or
review -- trigger-level exclusion only. It does not redact, crop, or remove
this area's pixels from evidence saved because activity elsewhere in the same
frame triggered capture; MockingBird does not implement pixel-level redaction
today. See [privacy-ignore-zone-contract.md](privacy-ignore-zone-contract.md).

## Ignore Zone

A zone where activity should not create normal review events. Enforced
identically to a Privacy Zone (same trigger-level exclusion, same absence of
pixel redaction) -- the two names exist for the user's own organizational use
(privacy-sensitive areas versus routine unwanted motion), not a difference in
implemented behavior. See
[privacy-ignore-zone-contract.md](privacy-ignore-zone-contract.md).

## Event / Activity Session

A meaningful outdoor activity record, before it is known whether an animal
was involved or how many. `product-doctrine.md` names this concept "Activity
Session"; `EventModel` remains the implementation name.

## Visit

A reviewable animal-centered event, especially around feeders, birdbaths,
perches, or yard zones. A Visit represents captured activity. An Observation
(below) represents what MockingBird believes happened, after evidence and
review of that Visit -- a distinct, more durable concept even though no
separate `Observation` product record exists yet.

## Detection / Detection Proposal

A machine-generated observation that may be right or wrong; not final truth,
only evidence for user review. `product-doctrine.md` names this concept
"Detection Proposal"; the implementation already uses both `DetectionModel`
and `DetectionProposalModel`/`DetectionProposal` for it.

## Interpretation

A proposed reading of what evidence means beyond raw identification --
behavior, counts, relationships between Visits. Not yet implemented.
Interpretation begins as a proposal/evidence, the same as a Detection
Proposal, and remains appropriately uncertain until reviewed; it is never
automatically truth. See "Wildlife-native semantics" in
[product-doctrine.md](product-doctrine.md).

## Motion Candidate

A debounced motion signal from scored frame differences in a user Zone or an
automatic activity area on a Stream.

## Best Frame

The candidate frame most useful for review context or later species suggestion; it is evidence context, not truth.

## Local Frame Artifact

A future local visual evidence reference for a selected frame; it is distinct from frame planes and is not truth.

## Sampled Frame

A lightweight local representation of a stream or media moment that can become a frame plane for motion scoring; it is not reviewed truth.

## Frame Plane

A rectangular 2D array of numeric grayscale values used for zone-aware motion scoring.

## Sampler

A local component that can produce frame planes from configured stream or media context; it is not a source adapter, detector, or truth source.

## Motion Evidence

Local evidence that a motion candidate occurred on a Stream. A user Zone is
optional semantic context; automatic activity can reach review without creating
a fake Zone. Motion Evidence is not reviewed truth.

## Motion Evidence Promotion

An explicit action that turns pending Motion Evidence into unreviewed Event/Visit evidence; it does not create reviewed truth.

## Promoted Saved Preview Evidence

Reviewable Event/Visit context created by explicitly promoting MotionEvidence
that was linked to saved preview media. It can show saved local media provenance,
but correction remains truth.

## SpeciesSuggestion

Local classifier evidence that a media item or crop may contain a species or taxon; its pending/accepted/rejected/superseded status is not reviewed truth.

## SpeciesSuggestionAdapter

A local optional adapter that creates SpeciesSuggestion evidence from media-backed Event/Visit context without creating labels, exports, or dataset truth.

## Apply Suggestion As Correction

A future explicit user action that pre-fills the existing correction flow from a SpeciesSuggestion; truth is created only when the correction is submitted.

## Review

The user process of confirming, correcting, merging, hiding, or rejecting events.

## Correction / Review Decision

A user-provided truth label, correction, or explicit abstention that improves
the local dataset. `product-doctrine.md` names this concept "Review
Decision"; `ReviewLabelModel` remains the implementation name. This is the
only dataset-grade truth write in the system -- but only when its own
provenance is authority-eligible; see Review Decision Provenance, below.

## Review Decision Provenance

The structured, model-neutral fact recorded on every `ReviewLabel` row
answering "who or what produced this Review Decision, and is it
observationally authoritative?" (`review_origin`/`reviewer_identity`,
`mockingbird.review_provenance`). Distinguishes human review, imported
curated truth (explicitly governed, provenance-known imports such as this
product's own demo seed content), agent/model diagnostic assessment (an
LLM, model, automation, or test harness -- never authoritative), and
legacy/unattributed (a pre-migration row of unprovable origin, deliberately
still treated as authoritative for backward compatibility). Only an
authority-eligible Review Decision can establish or correct durable
reviewed Observation truth; see
[review-decision-provenance-contract.md](review-decision-provenance-contract.md).

## Dataset Export

A local export of reviewed media, labels, corrections, and metadata.

## Analytics

Local summaries of outdoor activity over time.

## Research Export

A local, provider-neutral export of research-safe reviewed Observations
(generic CSV/JSON/manifest, or a Camtrap DP package). Consumes reviewed
truth; never creates it. Only a record whose `ResearchExportEligibility` is
eligible (`confirmed_taxon` or `confirmed_unidentified_wildlife`) is
included -- a provisional suggestion, unresolved Visit, rejected record, or
superseded truth is excluded, never exported as trusted data. See
[research-conservation-export-contract.md](research-conservation-export-contract.md).

## Research-safe Eligibility

The one policy decision (`mockingbird.research.eligibility.evaluate_
research_export_eligibility`) answering whether a reviewed record may enter
a trusted research/conservation export, and as what -- distinguishing
confirmed named taxon, confirmed unidentified wildlife, non-wildlife,
provisional suggestion, unresolved, rejected, and superseded, each with
explicit required (blocking) vs. recommended (disclosed, non-blocking)
reason codes.

## Acquisition Effort

The offline/recorded-media counterpart to live monitoring coverage
(`MonitoringExposureIntervalModel`): bounded, honest counts of recorded-
video analyzed duration and still-image capture opportunities, never
summed with live coverage and never used to infer deployment uptime from
gaps between imported files. See "Effort accounting" in
[research-conservation-export-contract.md](research-conservation-export-contract.md).

## Conservation Report

A bounded, coverage-aware natural-history summary for an explicit period --
confirmed species with occurrence-day counts, confirmed unidentified
wildlife, review backlog, and effort denominators. Never claims abundance,
population size, occupancy, a biodiversity index, or a decline/increase
trend.

## Camtrap DP Export

A Camtrap DP-interoperable package (target spec v1.0.2) mapped from
research-eligible Observations: `deployments.csv`, `media.csv`,
`observations.csv`, `datapackage.json`. Human-reviewed truth and
machine-classification (`SpeciesSuggestion`) provenance are always
distinct, never-blended observation rows.

## Research Collection

A named, bounded set of explicit Visit ids assembled for research export
(`ResearchCollectionModel`), with free-text curator attribution mirroring
`ReviewLabelModel.reviewer_identity`'s convention. Membership is never
cached truth -- every read/export re-resolves eligibility through the
ordinary review boundary. Curating a collection never grants review or
taxonomic authority.

## Observation (product object)

The target durable semantic product object from
[product-doctrine.md](product-doctrine.md): what MockingBird believes
happened, after evidence and review of a Visit. Not yet a distinct
implementation object -- today's closest equivalent is a reviewed Visit
(a Bird Log entry). Do not confuse this with "Observation Engine" or
"Observation Control," below: those name the capture/detection runtime and
its UI control, which produce evidence, never an Observation by themselves.
This naming collision is intentional doctrine vocabulary landing on an
already-used implementation word; resolving it (for example by renaming the
runtime) is a future implementation decision, not something this glossary
update performs.

## Observation Engine

The provider-neutral detection/tracking/evidence-scoring runtime described in
[architecture.md](architecture.md) (frame/detection/track/evidence/
Visit-proposal capability contracts). It is infrastructure: it emits evidence
and shadow/candidate proposals, never reviewed truth, and never an
Observation (above) by itself.

## Observation Control

The Stream-page **Start observing** / **Stop observing** action and its
compact camera/observation health, unified across every currently-supported
Stream type (Unified Observation Experience v1). A paired Camera Node
reuses the accepted frame-driven Observation Engine directly from the app;
an RTSP, Linux local USB, or Windows DirectShow Stream reuses the existing
durable monitoring policy; a Source configured with a plain still-image URL
reuses the existing Snapshot monitor; a Stream with no integrated runtime
reports that honestly instead of a Start button that would only fail. No
CLI acceptance tool is required for any of them. Stopping is bounded, works
the same way for every lane, and a Camera Node Stream stopping always
disables candidate authority. It never exposes internal Stage numbers,
CUDA, ONNX, or runtime-provider vocabulary in its basic state; that detail
stays in its collapsed advanced diagnostics. See
[unified-observation-panel-contract.md](unified-observation-panel-contract.md).

## Stream Monitoring Policy

Durable, user-authored intent for whether a supported live-video Stream should
remain off, armed, or paused while MockingBird is running. It is configuration,
not proof that a camera process is active, evidence, or reviewed truth.

## Runtime Checkpoint

Operational last-known lifecycle metadata for one Stream, such as interrupted,
starting, running, backoff, blocked, or stopped. A checkpoint from an older app
instance is stale until reconciled and is never product evidence or truth.

## Durable Stream Supervisor

A future application-level lifecycle owner that reconciles explicitly armed
Stream Monitoring Policies with bounded backend-owned live camera sessions. It
is not a Source adapter, general provider scheduler, model runtime, or truth
source.

## Runtime Safety Hold

An install-level operational stop that overrides armed monitoring during backup
quiesce, restore, migration/recovery, emergency stop, or shutdown. A restore
hold requires explicit resume so restored policy cannot unexpectedly start a
camera.
