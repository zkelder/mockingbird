# Next Provider Boundary Decision

## Purpose

MockingBird now has two explicit provider paths:

- `external_url`: configured Source -> explicit still-image preview -> explicit
  save as MediaAsset -> explicit MotionEvidence handoff -> promote -> correct.
- `folder_import_future`: configured Source -> explicit folder preview ->
  explicit MediaAsset import -> explicit single/batch MotionEvidence handoff ->
  promote -> correct.

The next provider should be chosen deliberately before implementation. The
decision should avoid adapter-first drift, video dependency creep, and hardware
setup framing while keeping the Source, Stream, Zone, Review, and Correction
flow central.

## Current Product Spine

Current provider work should preserve this spine:

Source setup -> provider status -> explicit provider action -> MediaAsset ->
MotionEvidence -> explicit promote -> Event/Visit review -> correction truth ->
analytics/exports/classifier readiness.

Status surfaces are read-only. Provider outputs are evidence or media context,
not reviewed truth.

## Implemented Provider Paths

### `external_url`

Supports:

- provider setup metadata for a user-supplied still-image URL
- explicit still-image preview
- explicit save as one local MediaAsset
- explicit MotionEvidence handoff from saved media
- explicit promotion into unreviewed Event/Visit context
- correction as the first reviewed truth write
- saved-media retention reporting and low-risk file-only cleanup

Does not support:

- live playback
- background fetch behavior
- multipart streams
- video decoding
- automatic evidence creation
- automatic Event/Visit or ReviewLabel creation

Why it preserves truth boundaries:

- setup/status/playback routes do not fetch URLs or write records
- preview is transient until the user saves it
- save creates MediaAsset only
- MotionEvidence, promotion, and correction are separate explicit steps

### `folder_import_future`

Supports:

- provider setup metadata for a redacted local folder path
- explicit folder preview with candidate/skipped reports
- explicit import of selected supported files as MediaAssets
- explicit single or batch MotionEvidence handoff from imported media
- explicit promotion into unreviewed Event/Visit context
- correction as the first reviewed truth write

Does not support:

- live playback
- folder watching
- polling
- background import
- media decoding
- automatic evidence creation
- automatic Event/Visit or ReviewLabel creation

Why it preserves truth boundaries:

- setup/status/playback routes do not scan folders or import files
- preview is a dry run
- import creates MediaAssets only
- evidence handoff creates pending MotionEvidence only
- promotion creates unreviewed Event/Visit context only
- correction remains the dataset/export/analytics truth boundary

## Candidate Provider List

- HTTP/MJPEG preview boundary
- RTSP stream boundary
- USB/local camera agent boundary
- browser camera boundary
- webhook ingest boundary
- Home Assistant / Frigate integration boundary
- ESP32-CAM-specific boundary
- manual/mobile upload expansion
- folder watcher/import automation

## Evaluation Criteria

- product value
- dependency risk
- platform risk
- privacy/security risk
- implementation complexity
- live playback complexity
- storage risk
- fit with existing Source/Stream contracts
- ability to preserve explicit user action
- risk of adapter-first drift
- usefulness for backyard/wildlife users

## Candidate Comparison

| Candidate | Product value | Main risk | Contract fit | Recommendation |
| --- | --- | --- | --- | --- |
| HTTP/MJPEG preview boundary | Medium to high for simple IP camera endpoints. | Can become repeated fetch or stream parsing work quickly. | Good if explicit preview/status only. | Good alternate design-only next step. |
| RTSP stream boundary | High for IP cameras. | Video decoding, transcoding, playback lifecycle, platform dependencies. | Good later, but not first. | Defer to separate design. |
| USB/local camera agent boundary | Medium for local webcams, Pi, and dev setups. | OS/device permissions and hardware setup drift. | Good only through an agent boundary. | Defer. |
| Browser camera boundary | Medium for quick testing. | Frontend permission, capture, upload, and privacy semantics. | Possible as explicit local media, not live source first. | Defer to separate design. |
| Webhook ingest boundary | High for integration while avoiding video runtime. | Auth, trust, payload validation, and evidence boundaries. | Strong if evidence-only and local-first. | Recommended next boundary. |
| Home Assistant / Frigate integration boundary | High ecosystem value. | Product-specific auth/config and imported detection trust. | Good after generic webhook. | Defer behind generic webhook. |
| ESP32-CAM-specific boundary | Medium for a useful hardware path. | Centers the product on one device family. | Often fits external URL or future MJPEG. | Do not choose as product center. |
| Manual/mobile upload expansion | Medium usability value. | Less of a provider boundary. | Strong with existing import flow. | Good polish, not the next provider boundary. |
| Folder watcher/import automation | Medium convenience value. | Storage, privacy, automation, duplicate, and retention risk. | Only after stronger lifecycle design. | Defer. |

## Candidate: HTTP/MJPEG Preview Boundary

An HTTP/MJPEG boundary could serve many IP cameras and simple camera endpoints.
It overlaps with `external_url` for still images, but becomes stream-like once
multipart responses, repeated reads, reconnect behavior, or browser playback are
introduced.

Risks:

- multipart parsing
- repeated fetch behavior
- hidden polling
- long-lived connection lifecycle
- confusing preview with live playback

This candidate should not become polling, worker behavior, or live playback
without a separate lifecycle design. A reasonable near-term version would be an
MJPEG contract/design phase only, not implementation.

## Candidate: RTSP Stream Boundary

RTSP has high product value because many outdoor IP cameras support it. It also
has high implementation risk.

Risks:

- video-decoding dependency choice
- possible ffmpeg, PyAV, GStreamer, OpenCV, or transcoding decision
- platform-specific install problems
- server/client playback story
- storage and retention behavior if frames are materialized

RTSP should wait for a dedicated playback/transcoding/dependency design before
implementation.

## Candidate: USB/Local Camera Agent Boundary

USB/local camera support could be useful for webcams, Raspberry Pi setups, and
developer validation. It also carries OS, device permission, and local agent
complexity.

Risks:

- OS-specific device enumeration
- permissions and consent
- local agent lifecycle
- hardware setup becoming the product story

This should not be the first live provider unless deliberately scoped as a
local agent design that stays under Source/Stream contracts.

## Candidate: Browser Camera Boundary

Browser camera capture could be useful for quick testing and local demos. It is
not a backend Source adapter by default, and it brings browser permission,
capture, upload, and privacy concerns.

A safer shape would be explicit local media creation or upload into existing
MediaAsset/MotionEvidence paths, not live stream support. It needs separate
design before implementation.

## Candidate: Webhook Ingest Boundary

A generic webhook ingest provider is a strong next boundary candidate.

Advantages:

- useful integration path for local systems
- low dependency footprint
- avoids video decoding and live playback
- can accept media/event candidates from external systems as evidence
- can later support Home Assistant, Frigate, Blue Iris, Scrypted, MQTT bridges,
  or other local automations without coupling the product to one integration
- fits Source/Stream/MediaAsset/MotionEvidence contracts

Risks to design:

- authentication and local-network trust
- payload validation and size limits
- duplicate handling
- provenance and external event confidence
- privacy/ignore zone behavior
- never treating imported labels, objects, or events as reviewed truth

This boundary should start as design only. Any later implementation should treat
incoming media/events/detections as MediaAssets, MotionEvidence, or proposal
evidence until user review/correction.

Phase 14D follows this recommendation with the design-only generic webhook
provider boundary:
[generic-webhook-provider-boundary-design.md](generic-webhook-provider-boundary-design.md).

## Candidate: Home Assistant / Frigate Integration Boundary

Home Assistant and Frigate have strong ecosystem value. They may already know
about cameras, motion events, objects, clips, or still images.

Risks:

- external systems may provide detections that look authoritative
- auth and configuration complexity
- vendor/product-specific payload assumptions
- risk of bypassing MockingBird review/correction

The safest path is to design generic webhook ingest first, then layer
Home Assistant or Frigate-specific adapters on top once the generic evidence
boundary is proven.

## Candidate: ESP32-CAM-Specific Boundary

ESP32-CAM devices can be useful in backyard/wildlife setups, but ESP32-specific
firmware, setup, or device language should not define MockingBird.

Many ESP32-CAM deployments can fit existing `external_url` still-image behavior
or a future HTTP/MJPEG boundary. ESP32-specific work should wait until the
generic HTTP/MJPEG path exists or there is a narrowly scoped reason to design
device-specific setup.

## Candidate: Manual/Mobile Upload Expansion

Manual/mobile upload expansion is low risk and useful. It builds on the
existing explicit import flow, can improve usability, and does not require
video dependencies or provider runtime behavior.

This is good future polish, especially for field review or phone-captured yard
media, but it is not the best next provider boundary if the goal is expanding
Source/provider integration.

## Candidate: Folder Watcher/Import Automation

Folder automation builds on the existing folder import path, but it carries
high storage, privacy, duplicate, retention, and lifecycle risk.

It should wait until:

- retention and cleanup are stronger for imported folder media
- duplicate and provenance behavior is more mature
- privacy/ignore behavior for automated evidence is designed
- worker lifecycle and explicit user controls are designed

No watcher, polling, or background import should be added yet.

## Recommendation

Recommended next provider boundary:

Phase 14D - Generic webhook ingest provider boundary design.

This is the chosen next provider design direction after Phase 14C. It remains a
design boundary, not an implementation.

Rationale:

- low dependency footprint
- strong integration value
- avoids video decoding and live playback
- works with external systems like Frigate/Home Assistant later without coupling
  to them first
- can receive media/event candidates as evidence, not truth
- fits the Source/Stream/MediaAsset/MotionEvidence pipeline
- preserves local-first behavior if the initial design is local-network only by
  default

The boundary should decide payload shape, authentication posture, provenance,
deduplication, dry-run behavior, media handling, evidence mapping, and truth
guards before any endpoint is implemented.

## Alternative Near-Term Path

If the next goal is visual stream-like source expansion, Phase 14D could instead
be HTTP/MJPEG provider boundary design.

Webhook remains safer because it needs:

- no streaming parser
- no continuous fetch behavior
- no video decoding
- no server/client playback lifecycle
- simpler evidence-only mapping into existing product contracts

## Recommended Future Phases

- Phase 14D: generic webhook ingest provider boundary design.
- Phase 14E: webhook provider configuration/status contract.
- Phase 14F: webhook dry-run/validation endpoint, no records.
- Phase 14G: webhook media/event ingest to MediaAssets/MotionEvidence only.
- Later: Home Assistant/Frigate-specific adapters after generic webhook is
  proven.
- Separately: RTSP, HTTP/MJPEG, USB/local camera, and browser-camera designs
  when ready.

## Guardrails For Any Next Provider

- No provider output is reviewed truth.
- No automatic reviewed labels.
- No live playback claims unless the playback implementation exists.
- No workers or polling without explicit lifecycle design.
- No video decoding dependencies without an explicit dependency decision.
- No source-specific product centering.
- Preserve provider smoke tests: status remains read-only, provider actions are
  explicit, MediaAssets/MotionEvidence are evidence/context only, and correction
  remains truth.

## Explicit Non-Goals

- No implementation.
- No dependencies.
- No provider code.
- No live playback.
- No workers.
- No polling.
- No media decode.
- No truth creation.
- No model/training work.
