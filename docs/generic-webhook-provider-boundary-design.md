# Generic Webhook Provider Boundary Design

## Purpose

The generic webhook provider exists because external systems may already detect
motion, objects, media, or event candidates before MockingBird sees them.
MockingBird should be able to accept those candidates later without coupling the
core product to Home Assistant, Frigate, Blue Iris, Scrypted, MQTT, or any other
single ecosystem first.

Webhooks can eventually feed Source, Stream, MediaAsset, and MotionEvidence
context. External labels, detections, and event claims must remain evidence or
suggestions, not reviewed truth. User review/correction remains the truth
boundary for analytics, exports, and classifier readiness.

Phase 14D was design only. Phase 14E adds `webhook_future` to provider
configuration, Source connection status, setup review, and placeholder Stream
playback contracts. Phase 14F adds an explicit payload validation/dry-run
endpoint. Phase 14G adds a confirmed, metadata-only motion payload route that
can create pending MotionEvidence only. It still adds no token/auth code, media
upload, media download, MediaAsset creation, Event/Visit creation, ReviewLabel
creation, provider implementation, dependency, worker, queue, polling, or
integration-specific behavior.
Phase 14H adds provider smoke-test hardening for the metadata webhook path:
setup/status and playback stay read-only, validation dry-run creates nothing,
explicit motion ingest creates pending MotionEvidence only, promotion creates
Event/Visit context only, and correction is the first truth write.
Phase 14I polishes the review/promote UI for webhook-origin evidence so
external event IDs, labels, and confidence remain visible as untrusted evidence
metadata, not reviewed truth.

## Product Flow

Future webhook work should preserve this flow:

generic webhook Source setup -> webhook provider configuration -> explicit
payload validation dry-run -> confirmed metadata motion payload -> pending
MotionEvidence -> explicit promote to Event/Visit -> Visit review/correction ->
ReviewLabel truth -> analytics/exports/classifier readiness.

The webhook provider boundary sits below the product loop. It may provide
evidence or media context later, but it must not create reviewed truth.

## Provider Definition

Future provider key:

- `webhook_future`

Recommended display name:

- Generic webhook ingest

Meaning:

- local-first by default
- integration boundary for external systems
- not Home Assistant-specific
- not Frigate-specific
- not MQTT
- not a cloud webhook by default
- not a truth-producing provider

The provider should represent generic inbound evidence/media intent before any
ecosystem-specific mapping is designed.

## Configuration Fields

Current provider configuration metadata:

- `endpoint_name`: optional display label.
- `shared_secret_configured`: required secret/sensitive configured marker.
- `allowed_source_name`: optional external source name filter.
- `default_stream_id`: optional Stream context.
- `default_zone_id`: optional Zone context.
- `accept_media_uploads`: optional future boolean metadata.
- `accept_media_urls`: optional future boolean metadata.
- `notes`: optional local setup notes.

Configuration rules:

- no token generation in this phase
- no general webhook/media ingest endpoint in this phase
- secrets must be redacted to configured/not-configured markers
- config/status must not imply media upload/download, real auth, or reviewed
  truth is active
- setup metadata must not accept payloads as ingest, write media, create
  evidence, or write truth

## Source Connection Status Relationship

Future Source status for `webhook_future` should report ingest readiness, not
camera connectivity or playback.

Rules:

- missing shared secret metadata means `not_configured`
- configured shared secret metadata means setup metadata is ready, but an
  ingest endpoint implementation is still future work
- `supports_live_playback` is false
- `supports_zone_editing` can be true where Stream context exists
- setup/status views must not validate external webhook delivery
- setup/status views must not accept payloads or create records

Source connection status remains read-only and product-level.

## Stream Playback Relationship

The webhook provider usually does not provide live playback. Stream playback
should remain placeholder/media/evidence context unless a separate playback
provider exists.

Future webhook ingest may attach media or evidence to Stream context, but it
must not:

- claim live playback by default
- provide a preview URL by default
- alter Stream playback status when media/evidence is created
- bypass Zone editing, MotionEvidence review, promotion, or correction

## Inbound Payload Categories

Dry-run webhook payload categories:

- metadata-only validation candidate
- media reference candidate
- media upload candidate
- motion/event candidate
- object/detection candidate
- species/label suggestion candidate
- heartbeat/status candidate

Policy:

- heartbeat/status is provider health, not activity evidence
- detection labels are not truth
- species labels become SpeciesSuggestion at most, if later implemented
- object/person/vehicle labels become DetectionProposal or evidence metadata at
  most, if later implemented
- event candidates become pending MotionEvidence at most unless explicitly
  promoted later
- all payloads remain untrusted until validated

Phase 14F candidate types:

- `metadata_only`
- `media_reference`
- `media_upload`
- `motion_event`
- `object_detection`
- `species_suggestion`
- `heartbeat`
- `unknown`

Phase 14F only reports these mappings. It creates no records and does not
authenticate, fetch media, upload media, or run models. Phase 14G can create
pending MotionEvidence from `motion_event` candidates only when the request is
explicitly confirmed and Stream/Zone context validates.

## Dry-run Validation Endpoint

Phase 14F endpoint:

```text
POST /api/sources/{source_id}/webhook/validate
```

This endpoint validates generic payload shape and Source/Stream/Zone context. It
returns `dry_run=true`, all `would_create_*` fields as false, and a candidate
mapping report when possible.

It does not:

- authenticate payloads
- compare raw secrets
- accept payloads as ingest
- write files
- create MediaAssets
- create MotionEvidence
- create Events/Visits
- create ReviewLabels/truth
- fetch media URLs
- call model or detector runtimes

## Metadata Motion Evidence Endpoint

Phase 14G endpoint:

```text
POST /api/sources/{source_id}/webhook/motion-evidence
```

This endpoint reuses the validation boundary and accepts only `type: "motion"`
payloads. `confirm=true` is required. On success it creates one pending
MotionEvidence record with safe webhook provenance and no media attachment.

It does not:

- implement real auth or token generation
- create MediaAssets
- upload, download, fetch, decode, or store media
- create Events/Visits
- create ReviewLabels/truth
- create SpeciesSuggestions or DetectionProposals
- call model or detector runtimes
- process non-motion payloads as records

## Future Webhook Endpoint Design

Future endpoint option:

```text
POST /api/webhooks/{source_id}/ingest
```

Alternative source-scoped option:

```text
POST /api/sources/{source_id}/webhook/ingest
```

Phase 14G still does not implement either general ingest endpoint.

Future behavior should include:

- authentication with shared secret or signed header
- bounded payload size
- structured validation
- no automatic truth
- no ReviewLabel creation
- no direct reviewed Visit state
- no model runtime
- no file write unless media upload is explicitly scoped
- no remote media download unless separately scoped
- safe response messages that do not echo secrets

## Media Handling Policy

Future media modes:

- JSON metadata only
- multipart upload
- local URL/reference
- remote URL fetch

Recommended first implementation path:

1. Metadata-only dry-run/validation endpoint first.
2. Media upload to MediaAsset only if needed and explicitly scoped.
3. Remote media URL fetch deferred until SSRF/security guardrails are designed.

Remote media URL fetch overlaps with the `external_url` guardrails and should
not be smuggled into webhook ingest. Local URL/reference handling should also
avoid trusting source-provided file paths.

## Evidence Mapping Policy

Future mapping rules:

- external event/motion payloads should map to pending MotionEvidence only
- external detections should map to DetectionProposal or SpeciesSuggestion, not
  truth
- external labels must not become ReviewLabel automatically
- source, stream, and zone context should be validated
- privacy and ignore zones should block or skip evidence creation by default
- duplicate candidates should be detected or reported before record creation
- provenance should record that the candidate came through webhook ingest

Phase 14G explicitly scopes metadata motion payloads to pending MotionEvidence
only. MediaAsset creation, DetectionProposal creation, and SpeciesSuggestion
creation each still need explicit future scope.

## Species/Label Policy

Webhook-provided species or object labels are untrusted suggestions.

Policy:

- species labels should become SpeciesSuggestion only if later implemented
- object, person, or vehicle labels can become DetectionProposal or evidence
  metadata only
- incoming labels must not create ReviewLabel records
- incoming labels must not mark Event/Visit reviewed
- user correction remains truth
- classifier/export readiness uses reviewed corrections only

## Security Policy

Future implementation must define security before accepting payloads.

Requirements:

- shared secret or signature design before implementation
- no anonymous ingest by default
- consider rate limiting
- require payload size limits
- no raw secrets in logs, responses, UI, docs, or tests
- no trusting source-provided file paths
- no remote URL fetching without SSRF guardrails
- no cloud upload by default
- local-network use preferred initially
- reject unknown Source ids
- reject payloads that do not match configured Source/Stream/Zone policy

## Privacy/Ignore Policy

Webhook payloads may describe sensitive outdoor activity. External systems may
not know MockingBird privacy or ignore zones, so MockingBird policy wins.

Rules:

- privacy and ignore zones must be respected before evidence creation
- if zone context is privacy or ignore, skip or reject by default
- missing zone context should be treated conservatively when policy requires it
- external detections cannot override MockingBird zone policy
- no cloud forwarding is implied

## Storage/Retention Policy

Storage policy:

- metadata-only validation writes nothing
- media uploads, if later implemented, must write under ignored local media
  paths
- webhook-created MediaAssets need retention policy
- webhook-created evidence should use the existing MotionEvidence lifecycle
- no unbounded ingest without lifecycle design
- no background queues without lifecycle design
- no generated media, datasets, model artifacts, or classifier workspaces in
  this phase

Webhook-origin media should be treated like other local media context: useful
for review, but not truth by itself.

## Relationship To Home Assistant / Frigate / Blue Iris / Scrypted

Generic webhook should come first.

Ecosystem-specific adapters can later wrap or format payloads into the generic
webhook boundary. Home Assistant, Frigate, Blue Iris, or Scrypted detections are
evidence only until MockingBird review/correction creates truth.

Future ecosystem phases should handle:

- system-specific auth/config
- payload mapping
- external camera/source identity matching
- duplicate behavior
- provenance
- error handling

Core MockingBird should not be coupled to one ecosystem first.

## Relationship To MQTT

MQTT is useful later but introduces broker, topic, subscription, lifecycle,
delivery, and deployment complexity.

Generic webhook is simpler first because it can be request/response, local, and
bounded. Future MQTT payloads should follow the same evidence-not-truth policy:
external messages can become validated candidates, not reviewed truth.

No MQTT behavior is implemented in this phase.

## Relationship To `external_url` And `folder_import_future`

`external_url` pulls one still image explicitly.

`folder_import_future` imports local files explicitly.

Webhook receives pushed candidates later.

All paths should preserve the same spine:

- Source setup/status first
- explicit provider action or validated ingest boundary
- MediaAsset and/or MotionEvidence before Event/Visit review
- explicit promotion when applicable
- user correction as truth

Webhook must not become a shortcut around review/correction.

## Testing Expectations For Future Implementation

Future tests should prove:

- missing or invalid secret is rejected
- payload size limits are enforced
- unknown Source is rejected
- stream validation works
- zone validation works
- privacy/ignore zone payloads are rejected or skipped
- metadata-only validation creates no records
- confirmed metadata motion payloads create pending MotionEvidence only
- metadata webhook smoke flow reaches correction truth only through the existing
  promote and correction routes
- media upload creates MediaAsset only if explicitly scoped
- event candidate creates pending MotionEvidence only if explicitly scoped
- species label creates SpeciesSuggestion only if explicitly scoped
- no ReviewLabel/truth is created
- no DatasetExport is created
- no model/detector runtime is called
- no remote URL fetch happens without guardrails
- no secret leakage occurs
- source-provided file paths are not trusted
- status/setup/playback routes remain read-only

## Recommended Future Phases

- Phase 14E: webhook provider configuration/status contract.
- Phase 14F: webhook payload validation/dry-run endpoint, no records.
- Phase 14G: webhook metadata event to pending MotionEvidence,
  explicit/evidence only.
- Phase 14H: webhook provider smoke-test hardening through correction truth.
- Phase 14I: webhook review/promote UI polish.
- Phase 14J: webhook media upload boundary design, or Phase 15A MVP
  source/provider readiness consolidation.
- Later: MQTT boundary design.

## Explicit Non-Goals

- no general webhook ingest implementation in this phase
- no media ingest endpoint
- no token/auth code
- no media upload
- no remote media download
- no Events/Visits
- no ReviewLabels/truth
- no ecosystem-specific integration
- no MQTT
- no workers/queues/polling
- no model/training work
