# Source Adapter Boundary Design

## Purpose

The Source adapter boundary exists so real provider code can arrive without
moving MockingBird away from the product loop. Sources and Streams are product
concepts. Adapters are implementation details underneath them.

The app must stay centered on Streams, Zones, review, correction, analytics, and
exports. Real provider code must not bypass playback/status contracts,
review-truth boundaries, privacy/ignore semantics, or local-first storage.

## Product Flow

Future adapter work should preserve this path:

Source setup metadata -> Source connection status -> Stream playback status ->
Stream panel, placeholder, or future preview -> Zone editing -> explicit
media/evidence creation path -> Event/Visit review -> correction truth ->
analytics/exports.

## Adapter Boundary Principles

- Adapters feed existing Source connection and Stream playback contracts.
- Adapters do not create reviewed truth.
- Adapters do not mark Visits reviewed.
- Adapters do not bypass user correction.
- Adapters are optional and local-first.
- Adapters fail closed and show honest status.
- Adapters do not require heavyweight dependencies by default.
- Adapters must not make the app unusable when unavailable.

## Candidate First Adapters

| Candidate | Product value | Dependency risk | Platform risk | Complexity | Privacy/security risk | Contract fit | Zone editing without live playback |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `manual_media` baseline | Already proves explicit local import into Stream/Zone review context. | Low. | Low. | Implemented baseline. | Low when files stay local. | Strong; already uses existing Source/Stream context. | Yes. |
| `external_url` / still-image URL preview | Lets configured Sources show a bounded visual preview later. | Low if standard HTTP client only. | Low. | Low to medium. | Medium; URL handling must avoid secret leaks and unsafe network behavior. | Strong; maps to `external_url`, `preview_url`, and honest status. | Yes. |
| HTTP still-image source | Useful for simple camera endpoints and local devices. | Low. | Low to medium. | Medium. | Medium; same URL and timeout concerns. | Strong if implemented as explicit preview/status only. | Yes. |
| MJPEG-style source, future | More stream-like visual feedback. | Medium. | Medium. | Medium to high. | Medium; sustained connections need lifecycle controls. | Good later, after playback lifecycle design. | Yes. |
| RTSP source, future | Common camera protocol. | High; usually needs video decoding/runtime dependencies. | High across OS/network setups. | High. | Medium to high. | Good eventually, but not first. | Yes. |
| USB/local camera agent, future | Useful for directly attached cameras. | Medium to high. | High; OS/device permissions vary. | High. | Medium; local device access needs clear consent. | Good only through adapter boundary. | Yes. |
| ESP32-CAM style source, future | Useful for lightweight outdoor cameras. | Low to medium. | Medium. | Medium. | Medium; device URL handling still matters. | Good as HTTP-like provider, but should not define the product. | Yes. |
| Folder/trail-cam import, future | Strong fit for local-first review of existing media. | Low. | Low. | Medium. | Low to medium; local path handling and retention matter. | Strong as explicit import, not live playback. | Yes. |
| Webhook source, future | Lets outside systems submit activity/media. | Low to medium. | Medium. | Medium. | Medium to high; auth and trust boundary needed. | Good later if normalized into evidence/review. | Yes. |
| Frigate/Home Assistant/Blue Iris/Scrypted integrations, later | Valuable for existing camera ecosystems. | Medium. | Medium to high. | High. | High; external system credentials and event trust matter. | Good later through product contracts. | Yes. |

## Recommended First Real Adapter Direction

The safest first implementation after this design is a simple `external_url` /
HTTP still-image preview provider, implemented later as an explicit
user-triggered preview/status path, not a worker.
Its provider-specific contract is documented in
[external-url-still-image-provider-contract.md](external-url-still-image-provider-contract.md).

Rationale:

- Lowest dependency footprint.
- Good bridge from provider config to visible Stream preview.
- Useful for many future camera setups, including ESP32-CAM-style URLs.
- Avoids RTSP/USB OS complexity.
- Avoids video decoding.
- Can keep live playback unsupported or limited until a later phase.
- Can feed Stream playback preview fields without creating truth.

Phase 11C adds the first bounded provider behavior for this direction: explicit
still-image preview fetch, no workers, no storage, no live playback, and no
truth creation.
Phase 11E adds explicit save-as-MediaAsset for fetched previews only. Saving
preview media requires the handoff design in
[external-url-preview-media-asset-handoff-design.md](external-url-preview-media-asset-handoff-design.md)
and still must not create truth.
Phase 11G adds the explicit saved-MediaAsset-to-pending-MotionEvidence handoff.
Adapters and preview/save routes still do not create Events, Visits, reviewed
labels, exports, analytics truth, or classifier truth by themselves.
Phase 11I polishes the explicit promote/review surface for saved preview media:
Event/Visit detail can show saved local media provenance only after
MotionEvidence promotion, while correction remains the truth boundary.
Phase 12B adds a manual checklist for validating that this behavior stays
explicit and below Source/Stream contracts in the running app:
[source-stream-dev-smoke-checklist.md](source-stream-dev-smoke-checklist.md).

## Explicit Non-Recommended First Adapters

- RTSP should wait because it brings dependency and video-decoding complexity.
- USB/local camera should wait because OS device access and permissions vary.
- Browser camera should wait because frontend permission/capture semantics need
  separate design.
- ESP32-specific work should wait because it risks centering the product on one
  hardware path.
- Full MJPEG/HLS streaming should wait because it adds server/client playback
  lifecycle complexity.
- Worker-based continuous capture should wait because lifecycle, storage, and
  privacy behavior need separate design.

## Adapter Lifecycle Contract

Future adapters should report lifecycle through product-facing status:

- `not_configured`
- `configured`
- `checking`
- `available`
- `unavailable`
- `offline`
- `unsupported`
- `error`

These states should surface through Source connection and Stream playback
contracts. `checking` should be explicit and user-triggered at first. Background
checking and worker loops require separate design and are not part of this
phase.

## Configuration Handoff

Existing provider configuration should feed future adapters this way:

- `provider_key` selects the intended adapter.
- Safe config preview never exposes secrets.
- Secret values remain redacted in responses, UI, logs, docs, and tests.
- `missing_fields` drives setup review and next actions.
- Configured future providers still cannot claim live playback until an
  implementation exists.
- Provider implementation uses existing contracts instead of adding separate
  product concepts.

## Playback Handoff

Future adapters may feed:

- `supports_live_playback`
- `playback_kind`
- `preview_media_asset_id`
- `preview_url`
- `setup_hint`
- `status`
- `message`

Playback status is not evidence. Preview is not reviewed truth. Zone editing can
continue with a placeholder or preview.

## Evidence/Event Boundary

- Adapter availability does not create MotionEvidence.
- Adapter preview does not create Events or Visits.
- Adapter-created MediaAssets require explicit review/evidence handoff before
  Events, Visits, or truth.
- Automatic evidence creation requires a future explicit phase.
- Manual import remains explicit.
- Model suggestions remain SpeciesSuggestion evidence only.
- ReviewLabel correction remains truth.

## Privacy/Ignore Boundary

- Privacy and ignore zones must be respected before any future automated
  evidence or media export.
- Preview/status must not weaken privacy semantics.
- Copied/training media remains governed by classifier/media-copy design.
- Future continuous capture needs separate privacy/storage design.

## Storage Boundary

- Adapter status checks write no media unless explicitly designed later.
- Generated media must not be committed.
- Local storage must not be unbounded.
- Preview artifacts, if any later, must live under ignored local data paths.
- Cleanup and retention must be explicit before background capture exists.

## Dependency Boundary

- The first adapter should require no new heavy dependency if possible.
- RTSP/video decoding dependencies need separate approval/design.
- Optional dependencies must be lazy/import-guarded.
- The app must start and tests must pass without adapter extras.
- Source adapter work must not add model or training dependencies.

## Security Boundary

- No cloud upload by default.
- Users control URLs and credentials.
- Secrets are redacted in responses and UI.
- Raw secrets must not appear in logs, docs, or tests.
- URL/network validation must not become SSRF-prone.
- Future network calls require timeout and error-handling design.
- Local-first remains default.

## Testing Expectations For Future Implementation

Future implementation must test:

- Adapter unavailable when not configured.
- Configured fields reflected in status.
- No secret leakage.
- Explicit preview/status call makes a bounded request only when scoped.
- No Events, Visits, or ReviewLabels created by status/preview.
- No MotionEvidence created automatically.
- No model/training dependencies.
- App works without optional adapter dependency.
- Errors surface as honest playback/source status.
- No generated files unless explicitly scoped and ignored.

## Proposed Future Phases

- Phase 11B: external URL / HTTP still-image provider contract.
- Phase 11C: explicit preview fetch implementation, no workers/no truth.
- Phase 11D: preview-to-MediaAsset handoff design, still explicit.
- Phase 11E: explicit preview-to-MediaAsset save implementation, no
  Events/Visits/truth.
- Phase 11F: saved preview review/evidence handoff design.
- Phase 11G: explicit saved-preview-to-MotionEvidence creation, no
  Events/Visits/truth.
- Phase 11H: saved preview evidence UI/review polish.
- Phase 11I: external URL media review/promote flow polish.
- Phase 12A: source/stream smoke-test hardening for the explicit
  external_url preview -> MediaAsset -> MotionEvidence -> promotion ->
  correction path.
- Phase 12B: source/stream smoke-test dev checklist for manual browser/API
  validation of the same explicit path.
- Later: RTSP, USB/local camera, ESP32-CAM, and browser adapter designs
  separately.

## Explicit Non-Goals

- No adapter implementation.
- No network calls.
- No camera connections.
- No video decoding.
- No background workers.
- No generated media.
- No evidence/event creation.
- No truth creation.
- No model/training work.
- No production live-stream claims.

## Phase 12A Status

Phase 12A adds smoke coverage for the current external_url Source/Stream path.
It proves adapters stay underneath product contracts: status routes do not fetch
URLs, preview is transient, save creates MediaAsset only, saved-media handoff
creates pending MotionEvidence only, promotion creates unreviewed Event/Visit
context, and correction remains truth.

## Phase 12B Status

Phase 12B documents the manual browser/API checklist for the same path. The
checklist verifies adapter behavior remains explicit and underneath
Source/Stream contracts; it adds no adapter implementation, worker, live
playback, media decoding, generated media, or truth creation.
