# External URL / HTTP Still-image Provider Contract

## Purpose

The `external_url` provider is the safest first real Source path after manual
media. In Phase 11C it lets a configured Source provide an explicit still-image
preview without video decoding, workers, storage, or live-stream claims.

This provider bridges Source setup metadata to explicit still-image preview and
optional local MediaAsset save while keeping MockingBird centered on Sources,
Streams, Zones, Review, Corrections, and Exports.

## Product Flow

external_url provider configuration -> Source setup review -> Source connection
status -> explicit preview/status request -> transient Stream/source preview cue
-> optional explicit save as local MediaAsset -> Zone editing context ->
optional explicit pending MotionEvidence handoff -> Event/Visit review ->
correction truth.

## Provider Definition

- Provider key: `external_url`
- Recommended display name: External URL / HTTP still-image

This provider is for user-provided local or network image URLs and still-image
endpoints. It is not RTSP, continuous video, a worker, or live playback. It
should not be framed as ESP32-specific, even though some ESP32-CAM-style
still-image endpoints may eventually fit this generic contract.

## Configuration Fields

Designed provider configuration fields:

- `url`: required, non-secret.
- `label` or `display_name`: optional, non-secret.
- `auth_username`: optional, sensitive or secret depending on storage policy.
- `auth_password`: optional, secret.
- `refresh_hint_seconds`: optional metadata only; not scheduling behavior.
- `notes`: optional, non-secret.

Provider configuration stores metadata only. Secret values must be redacted.
Only the explicit preview route fetches a URL. Setup review, connection status,
and playback status do not fetch URLs, validate by network call, or schedule
background refresh behavior.

## Source Connection Status Relationship

Future source connection behavior should follow these rules:

- Missing `url` reports `not_configured`.
- Configured `url` can report `configured` but not necessarily `available`.
- Explicit preview/status requests can read bounded availability.
- No live playback is claimed until implementation intentionally supports it.
- `setup_hint` should guide missing URL setup or future preview availability.

## Stream Playback Status Relationship

Future playback handoff may use:

- `playback_kind`: eventually `external_url` or `media_preview`.
- `preview_url`: only when policy allows safe direct browser rendering.
- `preview_media_asset_id`: only if a future explicit fetch stores media under
  ignored local data paths.
- `supports_live_playback`: remains false unless a future implementation
  intentionally supports live playback.
- `supports_zone_editing`: can remain true through placeholder or preview
  context.

## Explicit Preview/Status Request

Implemented route:

`POST /api/sources/{source_id}/external-url/preview`

Behavior:

- Explicit and user-triggered only.
- Bounded by a timeout.
- No background polling.
- No worker.
- No automatic evidence or event creation.
- Returns status and optional transient preview metadata.
- Does not store a preview MediaAsset unless the user calls the explicit save
  route.
- Does not create truth.

The save boundary is documented in
[external-url-preview-media-asset-handoff-design.md](external-url-preview-media-asset-handoff-design.md).
The preview route remains transient and unsaved.
Manual browser/API validation for preview, save, evidence handoff, promotion,
and correction is documented in
[source-stream-dev-smoke-checklist.md](source-stream-dev-smoke-checklist.md).

## Explicit Save Request

Implemented route:

`POST /api/sources/{source_id}/external-url/preview/save`

Behavior:

- Explicit and user-triggered only.
- Reuses preview URL/security/content-type/timeout/byte guardrails.
- Writes one local still-image file under ignored media storage on success.
- Creates one MediaAsset on success.
- Links the MediaAsset to Source and Stream context.
- Creates no Events, Visits, MotionEvidence, ReviewLabels, or truth.
- Does not mark anything reviewed.

Defaults:

- `timeout_seconds`: 3.0, clamped from 0.5 to 10.0.
- `max_bytes`: 5 MB, clamped to at most 10 MB.

## Network/Security Policy

- No cloud upload by default.
- User controls the URL.
- Secrets are redacted in API, UI, and logs.
- Raw credentials must not appear in docs or tests.
- Implementation uses bounded timeouts.
- Unsafe URL targets are blocked before fetch.
- SSRF risk is addressed conservatively before network access.
- Redirects are disabled unless explicitly scoped later.
- Internal metadata endpoints must not be fetched.
- Errors must not echo credentials.
- Local-first remains default.
- Private RFC1918 LAN addresses are allowed for local-first camera/still-image
  URLs.
- Loopback, multicast, unspecified, reserved, link-local, and
  `169.254.169.254` metadata-style targets are blocked.

## Privacy/Ignore Policy

- Preview/status is not evidence.
- Preview/status does not weaken privacy or ignore semantics.
- Future automated evidence from this provider requires separate design.
- Privacy and ignore zones must apply before future evidence or media export.
- Users should understand that URL previews may show outdoor camera imagery
  locally.

## Storage Policy

- The transient preview route stores no media.
- The explicit save route may store one bounded local still-image MediaAsset.
- Storage must not be unbounded.
- Generated preview artifacts must live under ignored local data paths.
- Cleanup and retention are required before storing fetched media.
- Generated media must not be committed.

Preview-to-MediaAsset behavior must follow
[external-url-preview-media-asset-handoff-design.md](external-url-preview-media-asset-handoff-design.md).

## Dependency Policy

- This implementation requires no new dependency.
- It uses Python standard library HTTP utilities.
- Still-image preview must not add OpenCV, ffmpeg, or video libraries.
- Optional dependencies must be justified and lazy.
- The app must start without provider extras.

## Evidence/Event/Truth Boundary

- Configuring a URL does not create MotionEvidence.
- Fetching a preview does not create MotionEvidence, Events, or Visits.
- Saving a preview creates a MediaAsset only.
- Fetching or saving a preview does not create ReviewLabels.
- Adapter status does not mark Visits reviewed.
- Saved preview MediaAssets may enter review only through an explicit
  evidence handoff such as pending MotionEvidence.
- Phase 11G adds that explicit saved-media-to-pending-MotionEvidence handoff;
  it still creates no Events, Visits, ReviewLabels, or truth.
- Phase 11I clarifies the later review surface: saved media can appear in
  Event/Visit detail only after explicit MotionEvidence promotion, and
  correction remains truth.
- Future automated conversion to evidence requires a separately designed phase.
- ReviewLabel correction remains truth.

## Failure/Status Behavior

Future statuses:

- `not_configured`: missing URL.
- `configured`: metadata present.
- `checking`: explicit preview/status in progress.
- `available`: explicit preview/status succeeded.
- `unavailable`: request failed or timed out.
- `unsupported`: URL or content type is not supported.
- `error`: bounded failure with a safe message.

## Content-type Policy

Allowed content:

- `image/jpeg`
- `image/png`
- `image/webp`

Initially unsupported:

- `image/gif`
- `video/mjpeg`
- multipart stream responses
- HTML or text responses

MJPEG or multipart stream handling belongs in a later MJPEG phase.

## Testing Expectations

Implementation tests cover:

- Missing URL reports `not_configured`.
- Configured URL does not claim live playback.
- Explicit preview call is the only network path.
- Setup review, connection status, and playback status do not fetch URLs.
- Timeout/error returns safe `unavailable` status.
- No secret leakage.
- Unsafe URL is blocked or rejected according to the security policy.
- Unsupported content type is rejected safely.
- No Events, Visits, ReviewLabels, or MotionEvidence are created.
- Save route creates one local MediaAsset only on success.
- App works without extra dependencies.

## Relationship To ESP32-CAM-style Sources

Some ESP32-CAM-style still-image URLs may fit this provider later. The provider
must stay generic: `external_url` / HTTP still-image. ESP32-specific setup,
firmware, or device assumptions belong in a later adapter/design. Do not center
MockingBird on ESP32.

## Relationship To RTSP/USB/MJPEG

- RTSP needs separate video-decoding design.
- USB/local camera needs separate OS/device design.
- MJPEG needs separate stream handling design.
- Browser camera needs separate frontend permission/capture design.
- External URL still-image must not quietly become any of those.

## Proposed Future Phases

Recommended next phases:

- Phase 11D: preview-to-MediaAsset handoff design.
- Phase 11E: explicit preview-to-MediaAsset save implementation, no
  Events/Visits/truth.
- Phase 11F: saved preview review/evidence handoff design.
- Phase 11G: explicit saved-preview-to-MotionEvidence creation, no
  Events/Visits/truth.
- Phase 11H: saved preview evidence UI/review polish.
- Phase 11I: external URL media review/promote flow polish.
- Phase 12A: source/stream smoke-test hardening for explicit
  preview/fetch/save/handoff/promotion/correction boundaries.
- Phase 12B: source/stream smoke-test dev checklist for manual preview, save,
  evidence, promotion, and correction validation.
- Later: MJPEG, RTSP, USB/local camera, ESP32-CAM, and browser camera designs
  separately.

## Explicit Non-Goals

- No automatic URL fetch.
- No background URL fetch.
- No live playback.
- No video decoding.
- No workers.
- No camera connection.
- No automatic media storage.
- No evidence/event creation.
- No truth creation.
- No model/training work.
- No ESP32-specific implementation.
- No RTSP, USB, MJPEG, or browser camera implementation.

## Phase 12A Status

Phase 12A covers the explicit external_url Source/Stream chain in backend smoke
tests. Setup review, connection status, playback status, Event/Visit detail,
and MotionEvidence reads do not fetch the URL. Preview remains transient, save
creates MediaAsset only, handoff creates pending MotionEvidence only, promotion
creates unreviewed Event/Visit context only, and correction remains truth.

## Phase 12B Status

Phase 12B adds the manual developer checklist for validating the same
external_url chain in the running browser/API without adding provider behavior,
automatic fetch behavior, live playback, media decoding, dependencies, or truth
writes before correction.
