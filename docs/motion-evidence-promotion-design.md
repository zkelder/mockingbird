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

`snapshot_media_asset_id` is optional. Early promotion can happen without a snapshot.

Later frame sampler or media capture work should attach a best-frame MediaAsset when available. Promotion itself should not decode media.

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

## Explicit Non-Goals

- no automatic species label truth
- no SpeciesNet call
- no MegaDetector call
- no stream worker
- no media decoding
- no background scheduling
- no production detection claims
- no export truth from motion alone
