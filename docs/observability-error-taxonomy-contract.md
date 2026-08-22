# Observability: Error Taxonomy, Correlation IDs, Structured Logging v1

**Roadmap phase:** Gate E (Reliability / Recovery / Observability); closes
the "structured error/diagnostics doctrine" gap alongside
[mockingbird-doctor-operational-health-contract.md](mockingbird-doctor-operational-health-contract.md)'s
own health-check contract -- see First-Hour Onboarding + Whole-Product
Observability Closure v1 in [roadmap-history.md](roadmap-history.md).

**Product flow improved:** when something fails, a user or a support
conversation can answer "what failed, which component, is it recoverable,
what can I do, and what evidence exists" from one stable, structured shape
-- instead of a raw exception string with no code, no component, and no
way to correlate it with anything else.

**Why this is next:** confirmed by direct code archaeology before this
work: no shared error/diagnostic-code taxonomy existed anywhere in the
codebase (every subsystem defined its own bare `XxxError(ValueError)` with
a free-form string "code," decoded only by `str(error)` at whatever API
boundary happened to catch it -- `diagnostics.doctor.DoctorCheckCode`'s own
docstring already said so, for Doctor's narrower surface). Structured
logging was effectively absent product-wide (two log call sites total,
both host-startup-failure). Correlation IDs and a support bundle were both
named as still-open Gate E capabilities in `roadmap.md`.

## Scope boundary

This is additive, not a rewrite. It does not replace any existing
`XxxError(ValueError)` exception class or its already-correct user-facing
text -- rewriting ~20 independent, already-tested error hierarchies would
be a large, risky change for no behavioral gain. It gives the
highest-value existing codes one shared, additive *shape* they can be
reported through at an API boundary or a structured log line, and a small,
honestly incomplete registry that reuses each code's existing user-facing
text verbatim. Adding a new component's codes to the registry as they are
touched is expected and welcome; this is not a requirement that every
error in the codebase be migrated at once.

## Error taxonomy (`diagnostics/error_taxonomy.py`)

```text
ErrorComponent: host_api | camera_node | acquisition_provider |
  observation_engine | model_runtime | database | media_storage |
  offline_ingest | export_research | frontend

ErrorRecoverability: blocking | degraded | informational
  (reuses Doctor's own DoctorRecoverability vocabulary -- see "Severity
  semantics" in the Doctor contract doc -- rather than inventing a second
  one)

StructuredError
  code                  -- stable snake_case identifier
  component             -- ErrorComponent
  timestamp
  message                -- always user-safe
  recoverability
  retryable
  correlation            -- ErrorCorrelation (all fields optional)
  diagnostic             -- bounded dict, advanced-only, never the primary message

ErrorCorrelation
  request_id / correlation_id / observation_session_id / source_id /
  stream_id / event_id / visit_id -- every field optional; a caller
  supplies only the identifiers it actually has, never all seven merely
  because the shape allows it.
```

`ERROR_TAXONOMY: dict[str, ErrorTaxonomyEntry]` is the registry -- seeded
with the highest-value codes already in active use across every component
group at the time of this milestone (Camera Node pairing, ONVIF discovery,
RTSPS refusal, Observation Engine start failure categories, BioCLIP
attempt-error codes, offline-ingest decode errors, a new
`storage_write_failed` for the previously-uncovered database-write-failure
case, and `camtrap_dp_export_directory_exists` replacing one non-conforming
full-sentence `ValueError` message found during this milestone's own
investigation). `resolve_error(code, ...)` falls back to a safe, honest,
non-leaking default for any code with no registry entry -- the registry
being incomplete must never mean an unregistered code produces an unsafe
response.

`bounded_exception_detail(error)` is a dependency-light, independent copy
of `diagnostics.doctor._bounded_exception_detail`'s exact contract (type
name + truncated message, capped at 200 characters) -- kept separate from
`doctor.py` deliberately, since that module's own import graph (ONNX,
BioCLIP, the Observation Engine) is too heavy for this widely-imported,
request-path module to carry.

## Correlation IDs

`api/main.py` adds one request-scoped `X-Request-Id` (generated, or
echoed back verbatim if a caller supplies one within a bounded length) via
an HTTP middleware, stored on `request.state.request_id` for handlers to
fold into a `StructuredError.correlation`/structured log line. This is
deliberately the *one* universal identifier every request gets;
`stream_id`/`source_id`/`event_id`/`visit_id` stay route-specific, added
to a correlation/log call only where a handler already has them -- never
forced onto every log line (see the milestone brief's own "do not make
every log line carry all IDs"). `observation_session_id` remains an
unfilled field in `ErrorCorrelation` today: no durable, session-spanning
identity exists yet for an Observation Engine session (see "Where the
chain breaks" below) -- naming the field now, rather than adding it later,
keeps the shape stable for when that identity exists.

A companion `X-MockingBird-Api-Version` response header (the running
`mockingbird.__version__`) is added by the same middleware -- independent
of the FastAPI app's own static `version="0.1.0"` constructor argument,
which only ever fed OpenAPI docs metadata and was never response-visible
otherwise.

**Where the chain still breaks**, disclosed rather than silently
incomplete: the Rejected/Suppressed Detection Attribution counterfactual
ledger (`observation.counterfactual_lineage`) remains entirely in-process/
in-memory -- a host restart still breaks that specific chain by design (see
that module's own contract). A `stream_id`/`source_id` correlates a
failure to a Source/Stream; it does not yet correlate to a specific
Observation Engine *session* (a stopped-and-restarted session has no
distinct durable identity today).

## Structured logging (`diagnostics/structured_log.py`)

`log_event(component, event, **fields)` emits one JSON-encoded record
through a dedicated `mockingbird.events` child logger, which propagates to
the root logger's own handlers by ordinary `logging` propagation -- so it
reaches the *same*, already-correctly-bounded rotating log file
`runtime_state.configure_file_logging` installs (5 MB x 4 files), with no
second log destination, no new retention policy to define, and no new
config to wire up. `log_error_event(component, event, *, code, exception=None, **fields)`
adds a stable `code` and, only in this bounded, advanced-log-only place, a
`bounded_exception_detail(exception)` summary -- never in a user-facing
message.

Wired into a representative, high-value subset of previously-unlogged
operational events as of this milestone: a shared `SQLAlchemyError`
handler (every database write/read failure that reaches the API boundary
uncaught -- previously zero such handling existed anywhere in the 32k-line
repository module); the two confirmed raw-exception-leak fixes in
`monitoring/source_monitor.py`/`playback/live_camera_session.py` (see
"User-safe actions," below); and, in
`observation/engine_runtime.py`, Observation Engine session start/stop
(`ObservationEngineSessionManager.start`/`.stop`), model-load failure (the
same classification `_engine_failure_message` already computes for the
basic-tier status message), and analysis-stream reconnect recovery (the
same event the existing in-memory `analysis_stream_reconnect_recoveries`
counter already tracks); and, in
`repository/product_repository.py`'s `_sync_camera_health_incident`, a new
Camera Node health incident being opened (fires once per genuinely new
condition -- not on that same method's own routine occurrence_count/
severity refresh of an already-open incident, and not yet on resolution;
see "Not yet covered," below). Each of these four is purely additive -- no
lifecycle, authority, retry, or health-state-machine behavior changed;
verified by real, repeated (2-4x) full-file runs of
`tests/test_engine_runtime.py` showing no change in pass rate before/
after, plus a clean full Core gate. Not yet covered: host startup/shutdown
beyond the existing crash-marker mechanism, frame-decode failures,
camera-health-incident *resolution* transitions (only opening a new
incident is logged today), coverage-accounting failures (confirmed absent
of any durable evidence
today, not just a log line), and evidence-persistence failures beyond the
existing `CameraHealthIncidentCategory.evidence_persistence_degraded`
durable fact -- disclosed gaps, not silent ones; see the milestone's final
report for the complete list. Do not log every frame, image bytes, or a
high-cardinality model vector -- the same discipline this module's own
docstring states directly.

## User-safe actions -- the leak this milestone fixed

`monitoring/source_monitor.py`'s `_run` and
`playback/live_camera_session.py`'s `_monitor_loop`/`_reader_loop` used to
put a raw `str(error)` directly into `last_error` -- a basic-tier,
always-shown field `StreamsPage.tsx` renders verbatim as "Last error:
{...}" with no truncation or curation. Confirmed live and traced end to
end during this milestone's own investigation. Fixed: `last_error` is now
a safe, plain-language, actionable sentence; the real exception detail
still reaches the bounded structured log via `log_error_event`, never
silently discarded -- matching this contract's own "keep raw details
available to an advanced/support surface" principle.

## Files touched

- `src/mockingbird/diagnostics/error_taxonomy.py` (new)
- `src/mockingbird/diagnostics/structured_log.py` (new)
- `src/mockingbird/api/main.py` (request-correlation/API-version
  middleware, shared `SQLAlchemyError` handler)
- `src/mockingbird/monitoring/source_monitor.py`,
  `src/mockingbird/playback/live_camera_session.py` (the two leak fixes)
- `src/mockingbird/observation/engine_runtime.py` (three additive log call
  sites -- see above; no detector/tracker/authority/retry logic touched)
- `src/mockingbird/repository/product_repository.py` (one additive log
  call site in `_sync_camera_health_incident`; no health-state-machine
  logic touched)
- `tests/test_request_correlation_and_error_handling.py`,
  `tests/test_source_monitor_error_handling.py`,
  `tests/test_live_camera_session.py`,
  `tests/test_engine_runtime.py`,
  `tests/test_camera_health.py` (new tests)
- this document

## Non-goals

- Rewriting every existing `XxxError` exception class onto
  `StructuredError` -- additive registry adoption only (see "Scope
  boundary," above).
- A durable, session-spanning `observation_session_id` -- the field exists
  in `ErrorCorrelation` for shape-stability; populating it durably is
  future work, not scoped here.
- Full causal tracing of one Visit's complete capture-through-admission
  path across every log line -- `request_id` plus the existing
  `stream_id`/`source_id`/`event_id`/`visit_id` keys narrow, but do not
  by themselves reconstruct, that full path; see "Support bundle and
  tracing" in `roadmap.md` for what remains open.
- A metrics/counters service or `/metrics` endpoint -- durable per-event
  rows already exist for several of the milestone's named counters
  (camera health incidents, BioCLIP attempts, offline-ingest runs, dataset
  exports); Doctor's own bounded `diagnostic_context` on the relevant
  checks is the chosen surface for recency-bounded aggregates, not a
  second always-on metrics system.

## Validation tier

Tier 2 -- focused unit/integration tests for the middleware, the shared
exception handler (both a real HTTP round trip and a direct handler-level
call), and the two leak fixes (a direct, synchronous unit test per fix
rather than driving the real background thread/asyncio loop, mirroring
this repository's own existing "prefer pure/direct calls over incidental
timing" test convention where reaching the real code path directly is
possible).
