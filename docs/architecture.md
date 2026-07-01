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
- Streams
- Zones
- Events
- Visits
- Detections
- Review labels
- Dataset exports

## Local intelligence

- Motion/activity detection
- Motion Evidence between scoring/evaluation and Event/Visit creation
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

## Local-first storage

MockingBird should prefer local storage for media, labels, corrections, metadata, exports, and analytics.

Cloud services may be optional later, but they should not be required for the core product loop.
