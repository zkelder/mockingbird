# Source Connection/Provider Contract

## Purpose

Define how MockingBird reports Source readiness before real source providers
exist. The contract is product-level status for Sources and Streams, not provider
implementation, media decoding, or camera connection.

## Product Flow

Source -> configuration metadata -> setup review -> connection status -> Stream
playback contract -> zone editing -> future provider implementation.

## Source Connection Contract Fields

- `source_id`: source being inspected.
- `status`: `demo`, `not_configured`, `configured`, `unavailable`, `offline`, or
  `unsupported`.
- `provider_kind`: `demo`, `placeholder`, `future_adapter`, `manual_media`, or
  `external_url`.
- `display_title`: user-facing source title.
- `message`: honest current provider/readiness state.
- `setup_hint`: optional next-step context.
- `supports_streams`: whether this source has or can expose product Streams.
- `supports_live_playback`: whether actual live playback is available now.
- `supports_zone_editing`: whether related streams can still be zoned.
- `adapter_key`: optional source/provider key.
- `configured_fields`: safe high-level fields already present.
- `missing_fields`: safe high-level fields still needed.
- `stream_ids`: related Stream ids.
- `last_checked_at`: optional provider check time.

## Status Meanings

- `demo`: seeded local demo source used to prove the product loop.
- `not_configured`: source metadata exists, but provider setup is missing.
- `configured`: provider setup is complete, but this phase does not use it.
- `unavailable`: provider readiness cannot be determined from current product
  metadata.
- `offline`: source is known but unavailable for playback.
- `unsupported`: source kind cannot feed this contract yet.

## Provider Kind Meanings

- `demo`: local demo metadata and demo stream panels.
- `placeholder`: source can only show placeholder state.
- `future_adapter`: future RTSP, USB/local camera, ESP32-CAM, browser, webhook,
  or integration provider boundary.
- `manual_media`: manual upload or folder-style media source boundary.
- `external_url`: future local or user-provided playback URL boundary.

For `manual_media`, connection readiness means the Source is ready for explicit
local import/review workflows. It is not a camera connection and does not imply
live playback.

For `folder_import_future`, future connection readiness means local folder
import metadata is present and explicit preview/import workflows may be
available. It is not a camera connection, folder watcher, polling loop, or live
playback claim.
Phase 13B reports missing `folder_path` as `not_configured` and configured
folder metadata as `configured`/future-provider-ready. Phase 13C adds an
explicit dry-run preview route, but connection status itself still must not scan
folders, validate paths, import files, or create records.
Phase 13D adds an explicit import route that creates MediaAssets only; source
connection status still does not call it or imply imported media exists.
Phase 13E adds a Streams page UI for those explicit preview/import actions.
Source connection status remains metadata/status only and still does not scan
folders, import media, or create MediaAssets.
Phase 13F designs a future explicit handoff from folder-imported MediaAssets to
pending MotionEvidence. Source status still must not imply evidence exists or
create evidence itself.

For `external_url`, connection readiness remains metadata/status-only. A
configured URL can point users to explicit still-image preview fetch, but
connection status itself must not trigger network calls or claim live playback.
Source connection status also must not persist preview media or imply saved
media exists; saved preview files belong behind the explicit MediaAsset handoff.

For generic webhook ingest, connection readiness remains status/evidence
oriented. Phase 14E reports missing `shared_secret_configured` metadata as
`not_configured` and configured metadata as metadata-ready for future ingest
work. Source status must not expose an active ingest URL, accept payloads,
create MediaAssets, create MotionEvidence, promote Events/Visits, or treat
incoming labels as truth. See
[next-provider-boundary-decision.md](next-provider-boundary-decision.md).
Phase 14D defines the webhook boundary in
[generic-webhook-provider-boundary-design.md](generic-webhook-provider-boundary-design.md).
Webhook Source status is ingest readiness, not live connection, playback, or
reviewed truth. Until implementation exists, configured metadata still surfaces
as future-adapter-required in setup review.
Phase 14F adds an explicit webhook payload validation/dry-run endpoint, but
Source connection status remains readiness only. Status routes do not parse
webhook payloads, authenticate, fetch media, create records, or update provider
state.
Phase 14G adds an explicit confirmed metadata motion payload route that can
create pending MotionEvidence only. Source connection status still does not
process payloads, create evidence, create Events/Visits, create labels, or write
truth.
Phase 14H smoke-tests that read-only boundary: provider configuration reads,
connection status, setup review, and Stream playback status do not validate
payloads or create records; validation dry-run and explicit evidence handoff are
separate actions.
Phase 14I shows webhook-origin evidence provenance in review UI after evidence
exists, but Source status still does not process payloads, create evidence,
promote Events/Visits, or write truth.

## Provider Configuration Relationship

Source provider configuration is the metadata layer underneath connection
status. Connection status reports the selected provider key, configured fields,
and missing fields, but it still does not connect to a Source or claim live
playback.

## Source Setup Review Relationship

Source setup review combines provider configuration, this connection status, and
related Stream playback status into a read-only user-facing readiness summary. It
does not create evidence, write truth, connect to sources, inspect media, or run
provider/model code.

The frontend surfaces connection readiness through setup review and the selected
Source next-action area so connection status does not feel separate from Stream
Detail, zone editing, or explicit manual import.

## Relationship To Stream Playback Contract

Source connection status explains upstream provider readiness. Stream playback
status remains stream-specific and explains what the Stream Detail panel can show.
Neither contract creates evidence, review truth, exports, or analytics truth.

## What This Phase Does

- Adds a read-only source connection status route.
- Shows compact source connection readiness on the Streams page.
- Keeps Stream playback and zone editing as the center of the product flow.
- Documents how future providers should feed product-level status.

## What This Phase Does Not Do

- Connect cameras or hardware.
- Decode media or capture frames.
- Add providers, stream workers, schedulers, or new dependencies.
- Run models or training.
- Create MotionEvidence, Events, Visits, ReviewLabels, SpeciesSuggestions,
  exports, analytics truth, or dataset truth.

## Future Adapter Relationship

Future source providers should feed this contract with safe readiness fields and
related Stream ids. They must stay underneath the Source/Stream/Zone/Event/Visit,
review/correction, export, and analytics loop.
The Source adapter boundary is documented in
[source-adapter-boundary-design.md](source-adapter-boundary-design.md).
Source connection status is the product-facing adapter status surface; adapters
should not introduce a separate user-facing product model.
External URL still-image behavior is further constrained by
[external-url-still-image-provider-contract.md](external-url-still-image-provider-contract.md).
Future saved preview behavior is designed in
[external-url-preview-media-asset-handoff-design.md](external-url-preview-media-asset-handoff-design.md).
Saved preview review/evidence handoff is designed in
[saved-preview-review-evidence-handoff-design.md](saved-preview-review-evidence-handoff-design.md).
Folder/trail-cam import behavior is designed in
[folder-trailcam-provider-boundary-design.md](folder-trailcam-provider-boundary-design.md).
The folder-import evidence handoff boundary is designed in
[folder-import-evidence-handoff-design.md](folder-import-evidence-handoff-design.md).

## Zone Editing Relationship

Zone editing can remain available when a Source is demo or not configured, as
long as related Streams exist. Users can prepare zones before live playback
exists.

## MotionEvidence Relationship

Source connection status is not evidence. Later phases may create MotionEvidence
from explicit stream/media evaluation paths, but this contract is read-only and
does not create evidence or truth.

## Privacy/Ignore Relationship

Privacy and ignore zones remain stream-level user intent. Future providers should
respect those zones when later phases create evidence or reviewable activity.

## Testing Expectations

- Known sources return connection/provider status.
- Unknown sources return 404.
- Demo sources are honest: demo status, no real live playback claim.
- Related Stream ids are included.
- Safe configured/missing field lists are present.
- Folder/trail-cam status never exposes raw `folder_path`.
- Generic webhook status never exposes raw shared secret text.
- Generic webhook status does not call the webhook payload validator.
- Generic webhook status does not call webhook motion evidence creation.
- Generic webhook status participates in the smoke-tested provider spine without
  creating MotionEvidence, Events/Visits, labels, or truth.
- Folder/trail-cam status does not call the explicit folder preview scanner.
- Folder/trail-cam status does not import folder media or create MediaAssets.
- The route does not call provider runtimes, inspect media, create artifacts, or
  mutate product state.
- Source connection status never creates evidence, review truth, exports, or
  analytics truth.

## Explicit Non-Goals

- No real live video playback.
- No real camera/source connection.
- No frame capture, media decoding, worker, scheduler, or provider
  implementation.
- No model inference, training, model files, or generated media.
- No changes to review/correction truth semantics.
