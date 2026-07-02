# Stream/Source Playback Contract

## Purpose

Define how MockingBird reports what a stream can show before real source adapters
exist. The contract is product-level status for the Stream Detail experience, not
camera capture or adapter plumbing.

## Product Flow

connect source -> inspect stream playback status -> view stream panel/placeholder
-> draw zones -> future adapters feed real playback.

## Playback Contract Fields

- `stream_id`: stream being inspected.
- `source_id`: source that owns the stream.
- `status`: `demo`, `not_configured`, `unavailable`, `offline`, or `unsupported`.
- `playback_kind`: `placeholder`, `demo_panel`, `external_url`, or `media_preview`.
- `display_title`: user-facing stream title.
- `message`: honest current playback state.
- `setup_hint`: optional next-step context.
- `supports_zone_editing`: whether zones can still be drawn or managed.
- `supports_live_playback`: whether actual live playback is available now.
- `adapter_key`: optional source-adapter key.
- `last_checked_at`: optional adapter check time.
- `preview_media_asset_id`: optional local media preview reference.
- `preview_url`: optional local preview URL.

## Status Meanings

- `demo`: the app can show the local demo stream panel.
- `not_configured`: stream metadata exists, but no playback adapter is configured.
- `unavailable`: playback cannot be shown because required product context is missing.
- `offline`: the source is known but disconnected.
- `unsupported`: the source type cannot provide playback through the current contract.

## Source Connection Relationship

Source connection status is the upstream readiness contract for the Source.
Stream playback status is the stream-specific contract for what Stream Detail can
show. A Source may be demo or not configured while its Streams still support zone
editing through demo or placeholder panels.

## Source Setup Review Relationship

Source setup review can include Stream playback readiness for the Streams that
belong to a Source. It is a summary layer only and does not change playback
behavior, start live video, create evidence, or write review truth.

Stream Detail shows playback status alongside compact Source setup context and
zone editing so users understand what can be viewed, what can be zoned, and when
manual media import is the honest next path.

## Provider Configuration Relationship

Provider configuration metadata can make Source connection status more specific,
but it does not change Stream playback into live video. Streams should remain
honest about demo or placeholder playback until a real provider implementation is
explicitly added.

For `manual_media` Sources, Stream playback remains a placeholder/media-context
surface unless a future playback provider exists. The Stream still gives manual
imports zone and review context.

## What This Phase Does

- Adds a read-only playback status route for streams.
- Shows honest playback status on Stream Detail.
- Keeps zone editing available when playback is demo or placeholder.
- Documents how future source adapters should feed playback status.

## What This Phase Does Not Do

- Connect cameras or source hardware.
- Decode video or capture frames.
- Add stream workers, source adapters, or new dependencies.
- Create MotionEvidence, Events, Visits, ReviewLabels, SpeciesSuggestions, exports,
  analytics truth, or model output.

## Future Adapter Relationship

Future RTSP, USB/local camera, ESP32-CAM, browser camera, folder, webhook, or
integration adapters should normalize their state into this contract. They remain
underneath the product and should not change the core Stream, Zone, Event, Visit,
review, correction, export, and analytics loop.
The Source adapter boundary is documented in
[source-adapter-boundary-design.md](source-adapter-boundary-design.md). Stream
playback status is the product-facing playback surface for future adapters, not
an evidence or truth surface.

## Zone Editing Relationship

Zone editing can work before live playback. Demo and placeholder panels still let
users prepare feeder, birdbath, privacy, ignore, and other zones around the stream
workspace.

## MotionEvidence Relationship

Playback status is not evidence. MotionEvidence may later reference stream moments,
zones, and optional media context, but the playback contract itself is read-only
and never creates evidence or truth.

## Privacy/Ignore Relationship

Privacy and ignore zones remain user-authored product context. Future playback
adapters must respect those zones when later phases create evidence or reviewable
activity.

## Testing Expectations

- Known streams return a playback contract.
- Unknown streams return 404.
- Demo streams are honest: demo panel, no real live playback claim.
- Placeholder streams include setup guidance and still support zone editing.
- The route does not create evidence, review truth, exports, analytics truth,
  media files, model artifacts, or adapter runtime calls.

## Explicit Non-Goals

- No real live video playback.
- No camera/source connection.
- No frame capture, media decoding, worker, scheduler, or adapter implementation.
- No model inference, training, model files, or generated media.
- No changes to review/correction truth semantics.
