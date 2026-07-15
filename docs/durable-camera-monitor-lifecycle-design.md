# Durable Camera and Monitor Lifecycle Design

**Roadmap phase:** 24C — audio-aware durable camera/monitor lifecycle design

**Product flow improved:** configure a camera → explicitly arm monitoring →
recover monitoring while MockingBird is running → create bounded review
candidates → correct in Review Queue.

## Why this is next

MockingBird can already run one backend-owned live camera session per Stream,
evaluate user-authored Zones, group activity in a bounded in-memory burst, and
optionally create needs-review Event/Visit candidates. The single-app runtime
now starts and stops cleanly, and verified local backup/restore protects the
database and managed media.

The remaining reliability gap is intent across restarts. Today, camera session,
monitor settings, activity bursts, retry state, and diagnostics disappear when
the API process exits. A dependable field product needs to remember only the
user's desired monitoring policy, recover conservatively, and explain why the
actual runtime is running, waiting, paused, or blocked.

This phase is a design boundary. It adds no durable runtime behavior.

## Decision

The first durable lifecycle applies only to backend-owned live video sessions
for supported RTSP, local USB, and Windows DirectShow Streams. It wraps the
existing `LiveCameraSessionManager`; it does not replace the Source, Stream,
Zone, evidence, or review models.

The existing snapshot-based `SourceMonitorManager` remains explicit and
in-memory. Making repeated external URL snapshots or folder scans durable is a
provider-worker problem with separate storage, retention, and scheduling
requirements. It must not be smuggled into camera continuity.

There will be no new administration page. Desired and actual monitoring state
belongs with the camera on Stream Detail and, when useful, its camera card.

## Current baseline

- The application never starts a camera or monitor at startup.
- `LiveCameraSessionManager` owns one in-memory camera process per Stream and a
  child motion-monitor thread.
- Camera, monitor, activity burst, best-frame bytes, failure, and diagnostic
  state are process-local.
- A child camera session has a bounded runtime and stops on explicit stop,
  process failure, application shutdown, backup restore, or Source archive.
- Auto-create is a separate, explicit monitor setting. It may create
  MotionEvidence and needs-review Event/Visit candidates, but never
  ReviewLabels or reviewed truth.
- The snapshot-based Source monitor is a different in-process loop for explicit
  external URL capture and is not part of this durable-video boundary.
- Live-session status currently participates in readiness and auto-candidate
  reconciliation. The implementation phase must remove all write behavior from
  status reads.

## Product policy versus runtime state

Persisted user intent and observed process state must remain separate.

### Desired policy

| Mode | Meaning | May start after normal app restart |
| --- | --- | --- |
| `off` | Continuity is not configured. | No |
| `armed` | The user explicitly asked MockingBird to keep this Stream monitored while the app is running. | Yes, after safety checks |
| `paused` | Configuration is retained, but the user or a safety action stopped continuity. | No |

`armed` is durable consent for later restarts of MockingBird. It is not consent
to install an operating-system service, run while MockingBird is closed, record
audio, upload media, or create reviewed truth.

### Actual lifecycle

| State | Meaning |
| --- | --- |
| `stopped` | No camera process or monitor is owned by the app. |
| `starting` | The supervisor is starting the camera and waiting for a healthy frame. |
| `running` | Camera frames are healthy and the requested monitor is active. |
| `backoff` | A retryable failure occurred and a bounded retry time is visible. |
| `blocked` | Configuration, archive, storage, privacy, capacity, or safety state prevents a start. |
| `stopping` | Child monitor and camera resources are being drained and stopped. |
| `interrupted` | A previous app instance ended without recording a clean stop. |

Actual state is operational metadata, not evidence or truth. A persisted
`running` value from an old process can never prove that a process is still
running.

## Recommended persisted records

### StreamMonitoringPolicy

One product-level policy per Stream:

- `stream_id`, unique and foreign-keyed to Stream;
- `mode`: `off`, `armed`, or `paused`;
- `auto_create_review_candidates`, defaulting to false;
- bounded evaluation interval, quiet-window, and minimum-detection settings;
- `policy_revision` for compare-and-update behavior;
- `armed_at`, `paused_at`, and `updated_at` timestamps; and
- a concise user-visible pause reason when applicable.

The policy stores no raw camera URL, password, device handle, subprocess ID,
frame bytes, model result, or adapter-specific secret. Provider configuration
remains the source of connection metadata.

In the first implementation, `armed` means the camera and its Zone-aware motion
monitor are one continuity unit. A camera-only persistent mode would consume a
device without producing review activity and is not part of this scope; manual
camera start remains available for live view and calibration.

### StreamRuntimeCheckpoint

One operational checkpoint per Stream:

- observed `policy_revision`;
- actual lifecycle state;
- random app-instance and runtime-generation identifiers;
- last start attempt, last healthy frame, last clean stop, and last failure time;
- safe failure code, never arbitrary exception or credential-bearing text;
- consecutive failure count and next retry time;
- last stop reason;
- bounded counters for starts, failures, and evidence handoffs; and
- whether a global safety hold currently overrides the policy.

Checkpoints support recovery and visibility only. They are excluded from Bird
Log, analytics, exports, classifier readiness, and review truth.

### RuntimeSafetyHold

A local install-level hold prevents automatic reconciliation during sensitive
operations. Initial reasons are:

- `backup_quiesce` — temporary, while a consistent backup is assembled;
- `restore_hold` — persisted after restore until the user explicitly resumes;
- `migration_hold` — used by a future migration/recovery operation;
- `emergency_stop` — explicit local stop for all durable monitoring; and
- `shutdown` — in-memory while the app drains owned resources.

A hold overrides `armed` without silently changing the user's saved policy.

## Runtime ownership

A single application-level `DurableStreamSupervisor` should own reconciliation.
It is lifecycle infrastructure, not a general provider scheduler and not the
existing placeholder worker registry.

The supervisor:

- holds one process-local lease per Stream;
- enforces a conservative global concurrency cap;
- starts and stops child sessions only through `LiveCameraSessionManager`;
- starts motion only after the camera produces a healthy recent frame;
- observes child termination without depending on a browser poll;
- updates safe operational checkpoints;
- applies bounded retry/backoff; and
- stops all child work before the repository is closed or replaced.

The existing manager remains the owner of the camera subprocess, frame cache,
monitor thread, and in-memory activity burst. The supervisor owns policy
reconciliation and restart decisions. No second camera process may be opened
for live view, capture, or monitoring while that lease exists.

## Startup and reconciliation

Normal application startup should follow this order:

1. Validate the database schema and integrity.
2. Initialize the repository and serve application health independently of
   camera availability.
3. Do not initialize the supervisor in `--check`, migration, restore, test, or
   explicit recovery modes.
4. Assign a new app-instance identifier and mark stale nonterminal checkpoints
   from another instance as `interrupted`.
5. Start reconciliation after a short, bounded startup grace period.
6. For each `armed` policy, validate Source/Stream existence, active Source
   status, supported playback configuration, storage budget, Zone requirements,
   safety holds, and runtime capacity.
7. Acquire the Stream lease, start the camera child, and wait for a healthy
   frame within a bounded deadline.
8. Start motion monitoring with the persisted settings only after video health
   is established.
9. Record `running`, `backoff`, or a product-readable `blocked` reason without
   changing reviewed data.

Camera failure must never make the core app unhealthy. Sources, Review Queue,
Bird Log, backup, and exports remain usable when a camera is blocked or in
backoff.

## Stop and restart semantics

Stop order is the reverse of start:

1. stop new monitor evaluations and auto-candidate handoffs;
2. let an in-progress repository/media write finish within a bounded deadline;
3. stop the monitor thread;
4. stop the camera subprocess and live-frame lease;
5. clear transient frame and burst state; and
6. persist a safe stop outcome.

| Cause | Policy effect | Runtime response |
| --- | --- | --- |
| User chooses Stop/Pause | Set `paused` | Stop and do not restart |
| Source is archived | Pause or block policy | Stop immediately; restoring the Source does not silently re-arm it |
| Camera configuration changes | Keep policy but reconcile new revision | Stop, revalidate, then restart or show blocked state |
| Child runtime limit is reached | Keep `armed` | Recycle after a short bounded delay |
| Device/stream temporarily fails | Keep `armed` | Exponential backoff with a visible next retry |
| Unsupported or incomplete setup | Keep `armed` | `blocked`; wait for configuration change or explicit retry |
| Storage guardrail is reached | Keep `armed` | Stop evidence-producing monitor and show `blocked_storage` |
| Normal app shutdown | Keep `armed` | Clean stop; eligible to recover next normal launch |
| Backup restore | Keep restored policy | Apply `restore_hold`; explicit resume required |

Retries must use a fake-clock-testable schedule, add small jitter, cap their
frequency, and reset only after a meaningful healthy interval. No tight retry
loop and no unbounded process spawning is allowed.

## Storage and retention preconditions

Durable monitoring must not ship until repeated evidence writes have enforceable
budgets. The current external snapshot count guardrail is not sufficient for
continuous live activity.

The implementation must define and test:

- a per-Stream auto-created candidate/media budget;
- a global managed-media byte or free-disk floor;
- a bounded rate of automatic review candidates;
- duplicate/cooldown behavior across child-session recycle;
- protected media accounting for reviewed/export-linked context;
- a visible blocked-storage state and explicit recovery action; and
- conservative cleanup separation—durable monitoring never deletes reviewed
  media or records to make room.

Raw rolling frames and tentative near-miss bursts remain in memory and bounded.
Only the selected best frame may be persisted during an authorized review
handoff.

## Evidence, idempotency, and truth

The supervisor itself creates no product evidence. The motion monitor may use
the existing auto-create handoff only when the persisted policy explicitly has
`auto_create_review_candidates=true`.

That handoff may create or reuse:

- one best-frame MediaAsset;
- MotionEvidence; and
- an uncertain needs-review Event/Visit candidate.

It must never create a ReviewLabel, mark a Visit reviewed, update Bird Log,
write analytics/export/classifier truth, run an identification adapter, or
accept a species suggestion.

Before durable auto-create is enabled, repository handoff needs a durable
idempotency key derived from Stream, Zone, runtime generation, and activity
session identity. A crash between media/evidence creation and runtime-state
update must not create a second candidate on retry.

All `GET` status routes are strictly read-only. Readiness transitions and
auto-candidate creation belong in the explicitly armed supervisor/monitor tick,
not in `GET /live-session/status`, Dashboard loading, browser polling, or page
refresh.

## Backup, restore, and update coordination

The supervisor must expose a bounded quiesce/stop contract to the application
runtime:

- **Create backup:** temporarily block new evidence/media writes and wait for an
  in-progress handoff to finish. Camera frame reading may continue only if it
  cannot mutate managed storage. Release the temporary hold after the verified
  artifact is complete or creation fails.
- **Restore:** hard-stop monitors and camera children before repository close.
  After the restored repository opens, persist `restore_hold` before any
  reconciliation. An armed policy contained in a restored backup does not start
  until the user explicitly resumes it.
- **Application update/migration:** enter a migration hold before schema or
  managed-media mutation and require successful compatibility validation before
  reconciliation resumes.
- **Shutdown:** stop reconciliation first, then child monitors and cameras, then
  repository resources.

Backup/restore failure must leave the supervisor stopped or held, never racing a
database/media replacement.

## Audio-aware boundary

Audio is planned, but this phase does not capture, store, analyze, or model it.
The lifecycle should be extensible through independently owned components such
as `video_capture`, `motion_monitor`, future `audio_capture`, and future
`audio_suggestion` under the same Stream/Source context.

Audio requirements are intentionally stricter:

- audio requires separate, explicit consent and cannot inherit video `armed`;
- a restored video policy cannot enable a microphone;
- video privacy/ignore polygons are not sufficient audio privacy controls;
- device selection and credentials remain adapter configuration, not core
  policy fields;
- raw continuous audio retention is off by default;
- any future retained segment is bounded, local, and evidence-only;
- future BirdNET-family output is suggestion evidence, never ReviewLabel truth;
- audio failure is observable and does not stop healthy video unless a future
  explicit fusion policy requires both; and
- cloud upload is never required for the core loop.

A later audio boundary must decide its evidence/provenance model, microphone
privacy controls, segment retention, licensing, runtime dependency, and adapter
interface before implementation.

## Product/API surface

The recommended future contract is Stream-scoped:

- `GET /api/streams/{stream_id}/monitoring-policy` — desired policy, read-only;
- `PUT /api/streams/{stream_id}/monitoring-policy` — explicit arm/pause/settings
  mutation with confirmation when arming;
- `GET /api/streams/{stream_id}/runtime-status` — desired plus actual state,
  blockers, last health, and next retry; strictly read-only; and
- `POST /api/streams/{stream_id}/runtime/retry` — explicit retry request that
  does not change reviewed truth.

Existing manual start/stop endpoints remain useful during staged rollout. Once
durable mode is implemented, **Stop camera** on an armed Stream must pause the
durable policy or clearly offer that choice; it must not stop a child that the
supervisor immediately restarts behind the user's back.

Stream Detail should show one compact **Monitoring continuity** section:

- Off, Armed, Paused, Running, Waiting to retry, or Needs attention;
- “Keep monitoring while MockingBird is running, including after restart”;
- auto-create Review Queue candidates as a separate explicit choice;
- last healthy time, safe blocker, and next retry when relevant; and
- Pause, Resume, or Retry now actions.

It should not expose process IDs, ffmpeg arguments, internal thread state, or a
general worker console.

## Implementation sequence

1. **Phase 24D — desired-state contract (complete):** schema version 2 now
   persists one default-`off` policy and `stopped` checkpoint per Stream,
   exposes read-only Stream-scoped policy/runtime status, and shows a compact
   Stream Detail continuity section. It adds no supervisor or startup camera
   behavior.
2. **Phase 24E — supervisor foundation:** add fake-adapter lifecycle,
   app-instance/checkpoint, lease, stop ordering, and deterministic backoff
   tests while runtime enablement remains unavailable.
3. **Phase 24F — explicit live-video continuity:** allow confirmed arming for
   supported backend-owned video Streams, implement startup grace, pause,
   archive/config reconciliation, backup/restore holds, and side-effect-free
   status.
4. **Phase 24G — durable review handoff:** add enforceable storage/rate budgets
   and idempotent auto-candidate creation before allowing unattended evidence
   persistence across recycled sessions.
5. **Phase 25 — field reliability:** measure restart recovery, long-run health,
   storage growth, nuisance/duplicate rate, candidate usefulness, and recovery
   on real feeder cameras.

Phase 24D also moved unattended quiet-window reconciliation out of
`GET /live-session/status` and into the active in-memory monitor tick. Status
reads no longer create review candidates or instantiate camera runtime when no
session exists. Schema version 1 databases and verified backups remain accepted
only through the known version-2 migration, which backfills every Stream off.

## Validation requirements

Implementation tests must prove:

- every policy starts `off` and no migration arms existing Streams;
- `--check`, tests, restore, migration, and safety holds start no camera;
- status and Dashboard reads have no side effects;
- stale `running` checkpoints become `interrupted`, never trusted as live;
- an explicitly armed supported Stream can recover after a clean app restart;
- pause, Stop camera, Source archive, and restore hold prevent restart;
- one Stream lease prevents duplicate camera processes;
- monitor starts only after a healthy recent frame;
- retry/backoff is bounded, visible, deterministic in tests, and cancellable;
- child failure does not make the app, review, backup, or export unavailable;
- backup quiesce and restore stop ordering prevent media/database races;
- storage and rate limits block new automatic handoffs safely;
- privacy/ignore Zones continue to suppress automated activity evidence;
- auto-create is idempotent and creates needs-review evidence only;
- no ReviewLabel, reviewed Visit, Bird Log entry, export, analytics truth,
  classifier truth, or model run occurs automatically; and
- video arming never enables future audio consent or capture.

## Files allowed in this design task

- this design document;
- roadmap, architecture, glossary, development workflow, README, and guardrail
  documentation; and
- no runtime, API, schema, repository, frontend behavior, tests, or generated
  artifacts.

## Non-goals

- implementing the supervisor, persisted policy, checkpoint, or endpoints;
- starting a camera or monitor on application startup;
- an operating-system service or running while MockingBird is closed;
- making snapshot polling, folder watchers, webhook queues, or retention jobs
  durable;
- audio capture, microphones, BirdNET, audio files, or audio dependencies;
- a new admin/worker page;
- cloud sync, notifications, mobile access, or remote control;
- automatic model execution or species acceptance;
- automatic cleanup or deletion; and
- any new route that creates reviewed truth.

## Validation tier

Tier 1 design validation: verify scope, terminology, current-runtime accuracy,
truth/storage/privacy/backup boundaries, audio separation, implementation order,
cross-document links, and a clean docs-only file list.
