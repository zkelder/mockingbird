# MockingBird Architecture

MockingBird is built around a universal outdoor event model.

Source adapters feed media into the platform, but the product is not organized around adapter-specific behavior.

## Conceptual layers

## App experience

- Streams
- Zones
- Events
- Visits
- Review
- Corrections
- Analytics
- Dataset exports

## Product API

- Sources
- Source provider configuration contract
- Source setup review/status contract
- Source connection/provider status contract
- Streams
- Stream playback status contract
- Zones
- Events
- Visits
- Detections
- Review labels
- Dataset exports

## Local intelligence

- Motion/activity detection
- Sampled-frame ingestion boundary between visible streams and frame-plane evaluation
- Lightweight sampler abstraction for supplied frame-plane evaluation
- Best-frame media attachment as optional Motion Evidence context
- Local frame artifacts as future visual evidence references
- Motion Evidence between scoring/evaluation and Event/Visit creation
- Motion Evidence persistence and ignore lifecycle
- SpeciesSuggestion evidence layer between media-backed Event/Visit evidence and review/correction
- SpeciesSuggestion correction flow as a pre-correction assist, not a truth layer
- Animal detection
- Species classification
- Event grouping
- Review prioritization

## Source adapters

Examples for later phases:

- Demo stream
- Manual upload
- Folder import
- RTSP/IP camera
- USB/local camera
- ESP32-CAM
- HTTP snapshot
- Trail-cam import
- Frigate
- Home Assistant
- Blue Iris
- Scrypted
- MQTT
- Webhook

Adapters should normalize into the same source, stream, media, event, and visit model.

The source adapter boundary sits below Source provider configuration, Source
connection status, and Stream playback status. Future adapter work must follow
[source-adapter-boundary-design.md](source-adapter-boundary-design.md) so real
provider code feeds product contracts without replacing the Stream, Zone,
review, correction, export, and analytics loop.

The first recommended adapter boundary is external URL / HTTP still-image
preview/status. Its contract is documented in
[external-url-still-image-provider-contract.md](external-url-still-image-provider-contract.md)
and remains explicit, bounded, local-first, and non-truth.
The Phase 11C preview fetch is an explicit request only: no worker, no storage,
no live playback, and no evidence or truth creation.

Source provider configuration is the metadata boundary for intended provider
setup. It may store safe setup fields and configured/not-configured markers, but
it must not store raw secrets, connect to sources, decode media, create evidence,
or write review truth.

Source setup review is a read-only product/status boundary over provider
configuration, source connection readiness, and related stream playback status.
It may guide the next setup step, but it must not connect to sources, decode
media, create evidence, write review truth, or create exports.

Manual media provider integration is an explicit local import boundary. Source
setup/status may guide the user to import media for a Source/Stream, and that
import can create reviewable Events/Visits, but reviewed truth still comes only
from review/correction.

The Streams, Stream Detail, and Import Media surfaces present provider
configuration, setup review, connection readiness, playback status, zone editing,
and manual import as one product flow. This UI consolidation does not add live
playback, provider runtime behavior, media decoding, evidence creation, or truth
creation outside explicit import and review/correction paths.

Source connection status is the product boundary between source metadata and
future provider readiness. Providers may feed safe status, field readiness, and
related Stream ids later, but the contract must not connect sources, decode media,
create evidence, write review truth, or create exports by itself.

Stream playback status is the product boundary between visible streams and future
adapter playback. Adapters may feed status, preview references, or local playback
URLs later, but the contract must not create evidence, review truth, exports, or
analytics truth by itself.

## Local-first storage

MockingBird should prefer local storage for media, labels, corrections, metadata, exports, and analytics.

Cloud services may be optional later, but they should not be required for the core product loop.
