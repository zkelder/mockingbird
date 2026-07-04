# Motion Evidence Promotion Design

## Purpose

MotionEvidence captures that something moved in a stream zone. Promotion is the explicit step that turns that evidence into reviewable Event/Visit context without making user truth.

## Product Flow

pending MotionEvidence -> explicit promote action -> Event/Visit evidence draft -> user review/correction -> dataset/export truth.

## Promotion Definition

Promotion means:

- converting pending MotionEvidence into reviewable Event/Visit evidence
- marking MotionEvidence as `promoted`
- linking `promoted_event_id` and `promoted_visit_id` to created product records
- preserving the original MotionEvidence as audit/evidence context

Promotion is not:

- species identification
- reviewed label creation
- dataset truth
- export readiness
- ML detection
- automatic user correction

## Phase 8F Status

Phase 8F implements the promotion API/repository foundation:

- `POST /api/motion/evidence/{evidence_id}/promote`
- pending MotionEvidence can become unreviewed Event/Visit evidence
- promoted MotionEvidence links to created product records
- ignored or already promoted evidence is rejected
- privacy and ignore zone evidence is rejected
- promotion writes no ReviewLabel, export, dataset coverage truth, species truth, model output, media files, or stream samples

The current Visit model requires an Event, so Phase 8F rejects `create_visit=true` with `create_event=false`.

## Phase 8G Status

Phase 8G exposes promotion from the Motion Evidence review surface.

The UI lets users inspect pending evidence, optionally provide an event title, label hint, and notes, then promote evidence into unreviewed Event/Visit records. The UI does not expose reviewed/species truth fields; correction remains in Review Queue and detail pages.

## Promote Request

Current fields:

- `evidence_id` path parameter
- `event_title` optional
- `visit_label_hint` optional, defaulting to `unknown_animal` or `unknown_bird` depending on future policy
- `notes` optional
- `create_event` bool, default `true`
- `create_visit` bool, default `true`
- `attach_snapshot_media_asset_id` optional
- `reviewed` always false and not client-settable
- species label not client-settable as truth

## Created Records

Event:

- copies source, stream, and zone context from MotionEvidence where available
- stays unreviewed
- records provenance as `motion_evidence`
- carries no reviewed species label

Visit:

- links to the event when an event is created
- copies zone context where available
- uses an unknown or needs-review label only if the current product model requires one
- stays unreviewed
- is not export-ready truth

MotionEvidence:

- changes status to `promoted`
- sets `promoted_event_id` and `promoted_visit_id`
- remains queryable

## Status Rules

- `pending` evidence can be promoted or ignored.
- `ignored` evidence cannot be promoted unless a future explicit restore/reopen flow exists.
- `promoted` evidence cannot be ignored as noise without a separate future unpromote/archive flow.
- Repeated promotion should return 400 instead of succeeding idempotently, because duplicate Event/Visit creation would be hard to review safely.

## Privacy And Ignore Zone Behavior

MotionEvidence in privacy or ignore zones should not be promotable by default.

Future implementation should reject promotion for privacy or ignore zones unless an explicit override is designed later. Feeder, birdbath, and ground zones are promotable. Unknown zone types should be treated conservatively.

## Snapshot/Media Behavior

`snapshot_media_asset_id` is optional. Early promotion can happen without media.

Phase 8O confirms promotion preserves `snapshot_media_asset_id` on MotionEvidence. If a Visit is created and a valid MediaAsset is available, the current Visit model carries that context through `representative_media_path`, and Event/Visit detail responses can expose the linked MediaAsset.

Saved-preview-origin MotionEvidence uses the same explicit promotion semantics.
The saved preview media reference can travel with the evidence, but promotion
still creates unreviewed Event/Visit context only.
Phase 11H surfaces saved-preview media and provenance in the Motion Evidence UI
before promotion, but does not change promotion rules or truth boundaries.
Phase 11I carries that clarity into Event/Visit detail: saved-preview-origin
promotions still use the same explicit promote route, and detail pages can show
saved media provenance while correction remains the truth boundary.
Phase 12A smoke tests verify that saved-preview-origin promotion creates only
unreviewed Event/Visit context and that correction is still the first reviewed
truth write.
Phase 12B documents the manual checklist for validating that same promotion and
correction boundary in the browser/API:
[source-stream-dev-smoke-checklist.md](source-stream-dev-smoke-checklist.md).
Phase 12C classifies promoted saved-preview media as high risk for cleanup
because deleting it can weaken Event/Visit review provenance. See
[external-url-saved-media-retention-design.md](external-url-saved-media-retention-design.md).
Phase 12D exposes that classification in the retention report and dry-run
planner. Promoted saved-preview media is high risk until reviewed correction
makes it protected, and the dry-run route does not delete files or records.
Phase 12E makes the same state visible in the Saved Media Retention UI:
promoted evidence media appears high risk, and reviewed correction context
appears protected.
Phase 12F keeps promoted evidence media out of low-risk cleanup. The file-only
cleanup route rejects promoted Event/Visit context and reviewed truth context.
Folder-origin evidence uses the same explicit promotion semantics:
folder-import MediaAssets can provide context only after an explicit evidence
action, and promotion still creates unreviewed Event/Visit context without
reviewed truth.
Phase 13F documents that evidence handoff in
[folder-import-evidence-handoff-design.md](folder-import-evidence-handoff-design.md).
Phase 13G implements the single-media pending evidence handoff. Folder-origin
MotionEvidence continues to use this promotion route: privacy/ignore zones are
rejected, promotion creates only unreviewed Event/Visit context, and ReviewLabel
correction remains the truth boundary.
Phase 13H adds a batch dry-run before any batch creation path. The dry-run can
report which folder-imported MediaAssets would be eligible, but promotion still
requires actual pending MotionEvidence and remains explicit.
Phase 13I can create those eligible pending MotionEvidence records after
confirmation. Batch-created folder evidence still uses this same explicit
promotion route; no Event, Visit, label, reviewed status, or truth is created by
batch creation itself.
Phase 13J keeps promoted folder-origin evidence understandable in Event/Visit
detail. Safe folder provenance and attached media can remain visible after
promotion, while correction remains the only analytics/export truth boundary.
Phase 14A smoke tests verify that both saved-preview-origin and folder-origin
promotion create only unreviewed Event/Visit context, and that ReviewLabel
correction remains the first dataset/export truth write.

Event-only promotion does not have a direct Event media field yet, so direct Event media propagation remains future work. Promotion itself does not decode media, create thumbnails, or create truth.

## Relationship To DetectionProposal

MotionEvidence explains why a moment was captured. DetectionProposal and species suggestions explain what may be present.

A future Event or Visit can reference both MotionEvidence and DetectionProposal evidence. Neither is reviewed truth until user correction.

## Truth Boundary

Promotion does not:

- create ReviewLabel
- mark Event or Visit reviewed
- make export-ready data
- update dataset coverage truth

User review/correction remains the only dataset/export truth source.

## API

Phase 8F endpoint:

```text
POST /api/motion/evidence/{evidence_id}/promote
```

Responses:

- 200 with promoted evidence and created event/visit references
- 404 for missing evidence
- 400 for ignored evidence
- 400 for already promoted evidence
- 400 for a request that creates neither Event nor Visit
- 400 for a Visit request without an Event, while the current Visit model requires an Event
- 400 for privacy or ignore zone evidence
- no truth writes

## Test Coverage

Phase 8F tests prove:

- promoting pending evidence creates Event/Visit evidence
- promotion marks evidence promoted
- promotion links `promoted_event_id` and `promoted_visit_id`
- promotion does not create ReviewLabel
- promotion does not create Export or dataset truth
- promoted Event/Visit records remain unreviewed
- repeated promotion is rejected
- ignored evidence promotion is rejected
- missing evidence returns 404
- privacy or ignore zone promotion is rejected
- evidence without snapshot can promote
- evidence with snapshot keeps the media reference

Phase 8O tests add:

- create/list/detail preserve `snapshot_media_asset_id`
- ignore preserves `snapshot_media_asset_id`
- missing media references fail safely
- promotion preserves or attaches `snapshot_media_asset_id`
- promoted Visit/detail surfaces expose the linked MediaAsset when supported
- media references do not create ReviewLabel, reviewed status, export truth, or dataset coverage truth

Phase 12A tests add full source/stream smoke coverage for:

- external_url status routes with no URL fetch
- transient preview with no saved records
- explicit saved MediaAsset with no evidence or truth
- saved MediaAsset -> pending MotionEvidence only
- explicit promotion to unreviewed Event/Visit context only
- ReviewLabel correction as the first dataset/analytics truth change

Phase 12B adds the companion manual checklist for browser/API validation of
those same steps.

Phase 12C adds cleanup/retention design for promoted saved-preview media:
promoted Event/Visit context is high risk, and reviewed correction context is
protected by default.

Phase 12D adds backend report/dry-run coverage for that policy without adding
cleanup/delete behavior.

Phase 12E adds frontend visibility for that report and dry-run plan without
adding cleanup/delete behavior.

## Explicit Non-Goals

- no automatic species label truth
- no SpeciesNet call
- no MegaDetector call
- no stream worker
- no media decoding
- no background scheduling
- no production detection claims
- no export truth from motion alone
