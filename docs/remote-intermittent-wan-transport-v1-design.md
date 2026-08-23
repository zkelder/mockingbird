# Remote / Intermittent-WAN Transport Foundation v1 — architecture decisions

Branch `remote-intermittent-wan-v1`, from accepted baseline `2907516`. This
document is Phase A's required output: concise architecture decisions,
written *before* implementation, based on bounded archaeology of the
existing Camera Node ↔ host protocol.

## The one fact that shapes everything else

**The Camera Node has zero outbound networking today.** It is a passive
HTTP server (`create_node_app`, `src/mockingbird_node/app.py`); every
existing exchange — pairing, health, capabilities, cameras, snapshot,
capture, evidence-burst, analysis-stream — is opened *by the host*. Nothing
in `src/mockingbird_node/` imports an HTTP client library. The one thing
resembling a "push" (the multipart analysis stream) is still a single
long-lived response to a host-opened connection, re-opened by the host
every ~10s.

A node that can only be *pulled from* cannot tolerate WAN unavailability —
if the host can't reach it, nothing happens, and nothing is retained. So
this milestone is not "harden an existing retry path"; it is "add a new
capability the product has never had": the Node autonomously producing
bounded work, holding it durably, and *pushing* it out when a path to the
host exists. Everything below follows from that.

## Decisions

**Unit of queued transport work — "spool item."** One opaque record: small
JSON metadata (`kind`, `priority`, `content_sha256`, `content_length`,
`media_type`, a bounded free-form metadata dict) plus a bytes payload
(today: one JPEG from the existing `provider.snapshot()` path, captured via
a new, additive Node endpoint `POST /node/v1/queue/evidence` that reuses
the existing profile/provider/`camera_busy` machinery unchanged and enqueues
instead of returning synchronously). The spool does not know or care what
the bytes mean — it is not a second Evidence/Observation pipeline, and it
does not create Visits, Events, or MediaAssets. That keeps this branch
inside its owned surface (transport) and out of Observation authority,
review, and Evidence/Source schema, which stay untouched.

**Spool representation — SQLite for metadata/state, files for payload
bytes.** `sqlite3` is stdlib (no new Pi-class dependency), gives crash-safe
atomic state transitions via ordinary transactions, and is the same
technology the host already uses — familiar, not a new idiom. Payload bytes
live as separate files (`items/<item_id>.bin`) referenced by path from the
DB row, avoiding SQLite page bloat for multi-megabyte images. This is
explicitly *not* a message broker: one local file, one table, no network
service, no external process.

**Durability.** WAL-mode SQLite + `synchronous=FULL` for the metadata store;
payload files written with the exact atomic-write idiom already
established in this codebase (`_PairingState._persist_state`:
`O_CREAT|O_EXCL` temp file, `flush`+`fsync`, `os.replace`) — factored into a
shared helper so it isn't hand-rolled a second time. On startup, any item
found in `transmitting` (was mid-flight when the process last stopped) is
reset to `pending`; the chunked wire protocol (below) makes this safe
because the host reports how many bytes it already has, so nothing is
resent from scratch needlessly and nothing is lost.

**Idempotency key — `(node_id, item_id)`.** `item_id` is a fresh UUID4
minted once at enqueue time and stored in the spool row; `node_id` is the
Node's existing durable pairing identity. Both are already durable
(`node_id` via existing pairing persistence; `item_id` via the new spool
DB). No counter to keep monotonic across restarts, no clock dependency,
collision probability negligible. The host's dedup ledger is keyed on this
exact pair; a retried declare/chunk/complete for the same key is always
safe to repeat.

**Acknowledgement semantics — explicit three-call protocol, not
fire-and-forget.**
1. `POST /transport/items` (declare): node_id (via credential) + item_id +
   content_sha256 + content_length + chunk_size + kind/priority/metadata.
   Host replies `duplicate` (already completed — nothing more to send) or
   `accepted` with `received_bytes` (0 for new, >0 to resume a
   previously-interrupted upload of the *same* item_id).
2. `POST /transport/items/{item_id}/chunks/{index}` (repeatable, bounded
   chunk size): host appends/validates and is a no-op if that chunk was
   already durably received.
3. `POST /transport/items/{item_id}/complete`: host verifies total size and
   sha256 *before* promoting the item from a `.part` temp file to its final
   durable location; only then is the item "acknowledged." A lost response
   to any of these three calls is always safe to retry — that is Phase C's
   proof (Scenario 2).

**Authentication for the new direction.** The existing pairing credential
is Node-*minted*, host-*held*, and presented host→node; the Node itself
never persists its plaintext (`_PairingState` stores only a SHA-256
digest — "survives a Node restart without storing its bearer"). Node→host
calls need the inverse (Node presents, host verifies), which cannot be done
from a digest alone. Rather than weaken that existing, deliberate property,
this adds one new, separately-scoped **transport credential**: minted by
the Node at pairing time, returned as an additive optional field on the
existing `/node/v1/pair` response (old Nodes simply omit it; the host then
knows transport is unavailable for that Node — pure additive
compatibility, matching this codebase's existing `capability_fingerprint`
precedent), and persisted in *plaintext* by the Node (it must be able to
present it after a restart with no human back on-site — Phase I is
unconditional on this). This is the one new plaintext secret-at-rest this
milestone introduces; it is written 0o600 into the same hardened
`StateDirectory=` the existing pairing digest already relies on, atomic
Same as pairing state. Documented as a known, deliberate, bounded trade-off
in the final report rather than hidden. The host stores it the same way it
already stores `node_credential` today — one more key in the existing
per-source `SourceProviderConfigurationModel.config_json` blob (zero schema
change) — and resolves an inbound transport call to "which paired source"
by a bounded scan of configured `camera_node` sources' stored transport
credentials with `hmac.compare_digest` (a handful of cameras per
installation; no new index needed).

**Retry/backoff.** Full-jitter exponential backoff per item
(`base=2s, cap=300s`), tracked per-item (`attempt_count`,
`next_attempt_at`) so it survives a restart — an item due for retry in 40s
when the process stops is still due in ~40s (not immediately, not never)
after it restarts, because `next_attempt_at` is a wall-clock column, not
in-memory state. Unlike the host's existing `AnalysisStreamRetryPolicy`
(bounded to 6 attempts, then terminal — correct for a *live session*, where
giving up and starting fresh is cheap), a spool item represents evidence
the product doctrine says to preserve; recoverable failures are retried
indefinitely (capped interval, never capped count) and only capacity
pressure (Phase G) or an explicit terminal classification (protocol
incompatibility, Phase L) ends an item's active life.

**Resumability — chunk-level, not byte-range.** True HTTP byte-range resume
would need conditional-request/range-header protocol work this codebase
has no precedent for anywhere (confirmed: no chunked/resumable upload
exists today, even outside the Camera Node surface). The three-call
protocol above gives resume at chunk granularity (default 256 KiB) for a
fraction of the complexity: an interrupted transfer resumes at the next
un-received chunk index, never from byte zero, and an incomplete transfer
can never become authoritative (`complete` verifies size+hash before the
atomic promote). Documented limitation: a transfer interrupted *mid-chunk*
re-sends that one chunk, not the whole item — bounded re-work, not full
restart-from-zero, and not true sub-chunk byte resume.

**Ordering / bandwidth-aware policy.** Drain order is
`priority ASC, enqueued_at ASC`. `priority` is a plain int field on every
item (`CRITICAL=0`, `NORMAL=100`); a small, urgent record and a large media
item are independent, self-contained spool items (no forced pairing), so a
burst of large media never blocks a fresh critical item from being picked
next. Config adds (Node-side, all new, no existing knob touched):
`transport_max_concurrent_uploads` (default 1), `transport_chunk_size_bytes`
(default 262144), `transport_max_bytes_per_second` (optional pacing cap,
disabled by default), `transport_backoff_base_seconds` /
`transport_backoff_cap_seconds`.

**Bounds / eviction (Phase G).** Mandatory capacity bounds:
`transport_spool_max_bytes` (default 512 MiB), `transport_spool_max_items`
(default 2000), plus a live free-disk floor
(`transport_spool_min_free_bytes`, default 100 MiB via `shutil.disk_usage`).
Exceeding any bound evicts the single oldest `pending`/`failed_retryable`
item (deterministic, FIFO-oldest-first); an `acknowledged` item is deleted
promptly on ack (not retained, not "evicted" — it's already durably on the
host). `transmitting`-at-crash items are recovered to `pending`, not
specially protected from eviction — they're ordinary pending items once
recovered. Eviction increments durable counters
(`evicted_count_total`, `evicted_bytes_total`, `last_eviction_reason`,
`last_evicted_at`) in a small `spool_meta` table so "how much have we
silently dropped, and why" survives a restart and is diagnosable — never
just deleted with no trace. TTL-based (age) eviction is intentionally
**not** enabled by default — the doctrine's "do not silently discard
acknowledged truth" reads, for *unacknowledged* evidence too, as "don't
time-box it away just because it's old"; only real capacity/disk pressure
evicts.

**Compatibility/version handling.** A new `transport_protocol_version`
constant (`"transport/v1"`) is sent on every declare call and checked with
strict equality, mirroring the existing `NODE_API_VERSION` precedent
exactly. A mismatch gets a distinct, explicit HTTP 400
`transport_protocol_unsupported` response (not a generic 5xx a client might
retry blindly) — the Node's worker classifies that specific code as
per-item terminal (stop retrying that item, surface it prominently in
diagnostics) rather than folding it into the open-ended retryable path,
directly satisfying Scenario 8.

**Diagnostics.** Node-local: `GET /node/v1/transport/status` (paired-only),
same shape family as `/node/v1/health`. Host-side, *without* a new
host-initiated network call (which would defeat the point for a
WAN-constrained node): the Node's own declare calls carry a small
self-reported backlog summary (pending count/bytes, last error) the same
way `X-MockingBird-Node-Service-Version` already rides along on analysis
frames today; the host durably records the latest one per source
(filesystem, alongside the transport ledger) and a new Doctor check
(`DoctorCheckCode.CAMERA_NODE_TRANSPORT`, following the existing
`_gather_*`/`_interpret_*` pattern exactly) reads it — giving "last known
backlog," "last contact," and staleness without Doctor ever dialing out
itself.

**No host schema migration.** The concurrent Acoustic Runtime lane has
already claimed migration slot 44 (`_migrate_to_acoustic_runtime_queue`,
confirmed in the authoritative repo's in-progress `storage/database.py`).
Every durable host-side fact this design needs (transport credential,
per-item dedup ledger, per-source backlog summary) fits inside either the
existing `SourceProviderConfigurationModel.config_json` blob (one more key,
exactly like `node_credential` today) or a new filesystem tree
(`MOCKINGBIRD_CAMERA_NODE_TRANSPORT_ROOT`, default
`data/camera_node_transport/`, resolved the same way
`resolve_media_root()` already resolves `data/media/imports/`). Zero rows,
columns, or tables added to the SQL schema; `CURRENT_DATABASE_SCHEMA_VERSION`
stays `43`.

**Host-side new surface is one small, separately-owned module.** Every
existing Camera Node host endpoint lives directly on `main.py`'s single
`FastAPI()` instance (no `APIRouter` precedent exists anywhere in this
codebase). Rather than add ~4 new endpoint functions and ~6 new Pydantic
models inline into the 13,000-line `main.py`/large `schemas.py` — both
under concurrent, active edit by the Acoustic Runtime lane right now — this
adds one new file, `src/mockingbird/api/camera_node_transport.py`, holding
its own `APIRouter` (FastAPI's normal, supported composition mechanism),
and touches `main.py` with exactly one import + one
`app.include_router(...)` line. This is the minimal-diff way to extend the
existing protocol surface without colliding, line-for-line, with a
same-file concurrent lane.
