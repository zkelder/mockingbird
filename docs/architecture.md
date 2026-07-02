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
