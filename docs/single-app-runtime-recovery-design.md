# Single-App Runtime and Recovery Design

## Purpose

Phase 24A turns MockingBird from two development processes into one dependable
local application runtime. It improves how the product starts, serves the web
experience, survives navigation/reloads, validates local data compatibility,
and shuts down. It does not add camera automation or reviewed truth behavior.

## Product Flow

launch MockingBird -> open the local app -> connect/view Sources and Streams ->
leave or return to the same product route -> review/correct -> stop cleanly.

## Runtime Boundary

The FastAPI process is the single local application host in production mode:

- existing `/api/*` and `/health` routes remain product/API routes
- the built React app is served from the same origin
- browser routes return the React entry document on direct load or refresh
- missing assets and unknown API routes remain honest 404 responses
- local Vite development remains available as a separate developer workflow

Same-origin hosting removes the production cross-port dependency. It does not
connect cameras, fetch providers, run analyzers, or create product records.

## Navigation and Recovery

Primary and detail screens receive stable browser paths. Browser back/forward,
refresh, and direct local links restore the current page and detail identifier.
Unknown paths recover to Overview without inventing product context.

The application shell treats Source/Stream/health loading as required product
context. Review, export, analytics, coverage, quality, and analyzer-readiness
summaries degrade independently: a temporary failure in one optional summary
must not make Cameras/Streams appear offline.

## Local Data Startup Safety

The database records a MockingBird schema version separately from product data.
Startup:

- creates the schema-version record for the current baseline
- accepts the current version
- rejects databases created by a newer unsupported MockingBird version
- refuses an older version when no explicit migration exists
- runs SQLite integrity checking before reporting the data store ready
- uses a bounded SQLite busy timeout so a brief local write does not fail at once

Schema metadata is operational context only. It is not Source, Stream, Event,
Visit, evidence, correction, analytics, or export truth.

## Launch and Shutdown

The local launcher:

- anchors relative local-data paths to the MockingBird workspace
- checks/builds the local frontend only when the development checkout lacks it
- validates the database before opening the browser
- reuses an already-running healthy local instance when possible
- opens the same-origin app after `/health` becomes ready

API shutdown cancels in-memory source monitors and stops backend-owned camera
sessions. It never restarts them automatically. Graceful shutdown (the in-app
*Shut down MockingBird* action or Ctrl+C) is bounded: uvicorn waits at most
`runtime.GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS` for open connections before the
lifespan teardown and `mark_clean_shutdown()` run, and on Windows the server
runs on a selector event loop rather than uvicorn's Proactor default (the
measured rationale is in `src/mockingbird/runtime.py`). Persisted desired monitoring,
scheduled provider actions, workers, reconnect policy, and reboot recovery are
future explicitly scoped lifecycle phases.

## Truth and Provider Boundaries

Phase 24A creates no:

- MediaAssets or MotionEvidence
- Events or Visits
- DetectionProposals or SpeciesSuggestions
- ReviewLabels or reviewed truth
- analytics/export/classifier truth
- provider fetches, folder scans, webhook processing, or model calls
- workers, schedules, polling, watchers, or automatic camera starts

## Validation

- API routes win over frontend fallback routes.
- production frontend assets and direct product routes are served same-origin.
- missing frontend builds and missing assets fail honestly.
- browser history restores primary and detail routes.
- optional summary failures leave the core camera product usable.
- current schema initialization is idempotent.
- newer/unsupported database versions are rejected without mutation.
- product records persist through application restart.
- graceful shutdown stops in-memory monitors and camera sessions.
- full backend tests and frontend production build pass.

## Follow-on Work

Phase 24B added explicit verified local backup/restore artifacts. Phase 24C now
defines opt-in persisted camera/monitor desired state, reconnect, restart,
resource limits, retention, restore holds, observable failure/backoff, and
separate future audio consent in
[durable-camera-monitor-lifecycle-design.md](durable-camera-monitor-lifecycle-design.md).
Phase 24D now adds the schema-version-2 desired-state contract with every Stream
persisted `off`/`stopped`, read-only policy/runtime APIs, a compact Stream Detail
status, and no startup camera behavior. Phase 24E should build the disabled,
fake-adapter-tested supervisor foundation before any activation control.
