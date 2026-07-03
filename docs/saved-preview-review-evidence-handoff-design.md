# Saved Preview Review Evidence Handoff Design

## Purpose

Phase 11E can save an `external_url` preview as one local MediaAsset. That saved
MediaAsset is reusable local media context, not evidence or truth by itself.

This design defines the explicit path from saved preview media into pending
MotionEvidence while preserving Source, Stream, Zone, privacy, ignore, and
correction boundaries.

## Product Flow

external_url Source setup -> explicit still-image preview fetch -> explicit save
as local MediaAsset -> user creates pending MotionEvidence -> optional
MotionEvidence promotion to Event/Visit -> Visit/Event review -> user correction
-> ReviewLabel truth -> analytics/exports/classifier readiness.

## Current Behavior Through Phase 11I

- Preview fetch is explicit.
- Save preview is explicit.
- Saved preview creates one MediaAsset.
- Saved preview has Source/Stream provenance when supplied or inferable.
- Saved preview creates no MotionEvidence automatically.
- Saved preview MediaAsset can become pending MotionEvidence only through
  explicit user action.
- Pending MotionEvidence creation creates no Event.
- Pending MotionEvidence creation creates no Visit.
- Pending MotionEvidence creation creates no ReviewLabel.
- Pending MotionEvidence creation creates no truth.
- The Motion Evidence UI shows attached saved preview media, safe provenance
  copy, Source/Stream/Zone context, and pending/ignored/promoted state.
- Ignore and promote remain explicit user actions; saved preview media does not
  become Event/Visit context until promotion, and correction remains truth.
- Phase 11I keeps saved-preview-origin context visible after explicit promotion:
  Event and Visit detail can show saved media/provenance while labels remain
  unconfirmed until review/correction.

## Recommended Handoff Path

Recommended path:

saved preview MediaAsset -> explicit "Create MotionEvidence from this media" ->
pending MotionEvidence with `snapshot_media_asset_id` -> user reviews
MotionEvidence -> explicit promote to Event/Visit -> user correction on Visit ->
ReviewLabel truth.

MotionEvidence is the right first handoff because it already represents evidence
before Event/Visit truth, supports pending/ignored/promoted lifecycle, can
reference media, has explicit promotion behavior, and keeps saved media from
becoming an Event or Visit automatically.

## Alternative Handoff Paths Considered

- Saved preview directly to Event/Visit: rejected as the default because media
  alone should not be treated as activity.
- Saved preview directly to ReviewLabel: invalid because labels require reviewed
  Visit/Event context.
- Saved preview directly to classifier training: invalid because training truth
  requires reviewed correction.
- Saved preview directly to SpeciesSuggestion: invalid because suggestions are
  model evidence, not user media review.
- Automatic evidence creation on save: deferred until automation, privacy, and
  storage lifecycle design exists.

## Implemented Explicit Action

Implemented route:

`POST /api/media/{media_asset_id}/create-motion-evidence`

The action:

- Require explicit user action.
- Validate the MediaAsset exists.
- Validate Source/Stream context when available.
- Create pending MotionEvidence only.
- Set `snapshot_media_asset_id`.
- Preserve available `external_url` preview provenance.
- Allow note/context fields.
- Not create Event/Visit.
- Not create ReviewLabel.
- Not mark anything reviewed.
- Not create classifier/export truth.

## Request Fields

Request:

- `stream_id`, optional if inferable from MediaAsset
- `zone_id`, optional
- `reason`, optional
- `note`, optional

No model inference happens here. Zone id is context, not truth.

## Response Fields

Response:

- `motion_evidence_id`
- `media_asset_id`
- `source_id`
- `stream_id`
- `zone_id`
- `status`: `pending`
- `creates_event`: false
- `creates_visit`: false
- `creates_truth`: false
- `message`
- `warnings`

## Source/Stream/Zone Relationship

Source/Stream provenance from the MediaAsset should be reused when available.
Stream context helps zone review. Zone assignment can be optional or
user-selected.

Privacy Zone and Ignore Zone handling must be explicit. Zone context alone does
not create species, activity, or review truth.

## Privacy And Ignore Boundary

Saved preview media may contain sensitive outdoor imagery. The user must
explicitly choose to create evidence from saved media.

Privacy Zones should block or warn before evidence creation when selected.
Ignore Zones should default to "do not create evidence". Future automation must
separately prove privacy/ignore handling. No cloud upload happens by default.

## Evidence/Event Boundary

MotionEvidence is evidence, not truth. Pending MotionEvidence is not Event or
Visit. Promoted MotionEvidence can create Event/Visit only through explicit
promote action.

Event/Visit still requires review/correction. ReviewLabel remains truth.
Analytics, exports, and classifier readiness use reviewed corrections, not raw
saved previews.

## MediaAsset Boundary

MediaAsset is local media context. It is not an observation by itself.

MediaAsset can be attached to MotionEvidence or Visit/Event context, and it can
be reused in manual workflows. Deleting and cleanup policy must be clear before
larger automation exists.

## UI Design

The Streams page can show `Create pending evidence from saved media` after a
preview is saved as local media.

Copy should say: "This creates pending evidence only. It does not create Events,
Visits, labels, or truth."

The Motion Evidence page shows saved-preview-origin evidence with the attached
media preview/file link, safe saved-local-media provenance, Source/Stream/Zone
context, and explicit pending/ignored/promoted state. Promotion remains
separate. Correction remains separate.

After explicit promotion, Event Detail and Visit Detail can surface that the
case came from promoted MotionEvidence and show saved preview media provenance
when available. Detail pages still frame the Event/Visit as reviewable context;
correction remains the truth action.

Manual validation for this handoff is documented in
[source-stream-dev-smoke-checklist.md](source-stream-dev-smoke-checklist.md).

Avoid:

- `auto-detect`
- `mark as bird`
- `confirm visit`
- `train model`
- `capture stream`
- `record`
- `start stream`

## Relationship To Manual Media Import

Manual import can already create reviewable Events/Visits by explicit import
behavior. Saved external_url preview currently creates MediaAsset only.

Future saved-preview-to-MotionEvidence should be a separate explicit path. Both
workflows must preserve correction truth. Manual media import remains useful for
user-supplied files.

## Relationship To Classifier/Export Pipeline

- Saved previews are not classifier examples by themselves.
- MotionEvidence is not classifier truth.
- Event/Visit without correction is not classifier truth.
- Classifier readiness/export requires reviewed media-backed corrections.
- SpeciesSuggestion remains model evidence only.
- ReviewLabel correction remains training truth.

## Relationship To Future Automation

Automatic evidence from the `external_url` provider requires separate design.
Scheduled or continuous fetch requires separate worker, storage, and privacy
design. Motion scoring on fetched previews requires a separate explicit phase.
No background capture is implied by saved preview handoff.

## Storage And Cleanup Expectations

Saved preview files can accumulate. MotionEvidence creation should not duplicate
media unnecessarily.

Cleanup should distinguish original saved MediaAsset records from derived
evidence records. Future bulk cleanup must not delete reviewed evidence/media
without explicit confirmation. Generated media remains under ignored local data
paths.

Retention risk policy for saved preview media is documented in
[external-url-saved-media-retention-design.md](external-url-saved-media-retention-design.md).
Media linked to pending, promoted, or reviewed evidence needs warnings before
cleanup, and reviewed truth-linked media is protected by default.
Phase 12D exposes that policy through a read-only report and dry-run planner:
pending/ignored evidence is medium risk, promoted Event/Visit context is high
risk, and reviewed correction context is protected.

## Testing Expectations For Future Implementation

Future tests should prove:

- Create evidence from saved preview requires explicit action.
- MediaAsset must exist.
- Source/Stream provenance is preserved.
- Optional zone context is stored safely.
- Privacy/ignore zones block or warn as designed.
- One pending MotionEvidence is created.
- No Event/Visit is created.
- No ReviewLabel is created.
- Visits are not marked reviewed.
- No SpeciesSuggestion, DetectionProposal, or DatasetExport is created.
- Classifier readiness/export is unchanged.
- Saved media file is not duplicated unnecessarily.
- No model/detector runtime is called.
- No network fetch is required for handoff.
- No secrets leak.

## Recommended Future Phases

- Phase 11G: implement explicit saved-preview-to-MotionEvidence creation, no
  Event/Visit/truth.
- Phase 11H: saved preview evidence UI/review polish.
- Phase 11I: explicit MotionEvidence-to-Event/Visit flow polish for
  external_url media.
- Phase 12A: source/stream smoke-test hardening for MediaAsset ->
  MotionEvidence -> promotion -> correction boundaries.
- Phase 12B: source/stream smoke-test dev checklist for manual evidence handoff
  validation.
- Phase 12C: external_url saved media cleanup/retention design.
- Later: automated external_url sampling/motion design, if ever.

## Explicit Non-Goals

- No automatic MotionEvidence creation.
- No media writes in the handoff route.
- No MediaAsset creation in the handoff route.
- No Events/Visits.
- No ReviewLabels.
- No truth creation.
- No live playback.
- No workers.
- No scheduled fetch.
- No video decoding.
- No model/training work.
- No automatic labels.

## Phase 12A Status

Phase 12A smoke tests verify that saved preview MediaAsset handoff creates
pending MotionEvidence only. Event/Visit records appear only after the explicit
promote route, and reviewed labels, analytics truth, and dataset truth appear
only after the existing correction route.

## Phase 12B Status

Phase 12B documents manual validation for saved preview MediaAsset ->
MotionEvidence -> promotion -> correction. It keeps evidence creation explicit
and verifies truth appears only after the existing correction route.

## Phase 12C Status

Phase 12C defines cleanup risk states for saved preview media linked to
MotionEvidence, promoted Event/Visit context, and reviewed corrections. Cleanup
must warn before weakening evidence context and must not delete reviewed truth
or export/classifier readiness context by default.
