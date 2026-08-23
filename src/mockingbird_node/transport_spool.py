"""Durable local spool for Camera Node work that cannot currently reach the host.

RAM is never the source of truth: every state transition here is a
committed SQLite write (WAL journal, `synchronous=FULL`) before it is
considered to have happened, and every payload lives as its own file,
written with the same atomic create-temp/fsync/replace idiom
`app.py`'s pairing state already uses (see `atomic_io.py`). A process crash
between any two operations leaves either the state before or the state
after -- never a torn write.

This is deliberately not a message broker: one SQLite file for metadata, a
flat directory of payload files, no server, no network, sized for a
Pi-class device with a bounded number of pending items. See
docs/remote-intermittent-wan-transport-v1-design.md.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import random
import shutil
import sqlite3
import threading
import time
import uuid

from .atomic_io import atomic_write_bytes


PRIORITY_CRITICAL = 0
PRIORITY_NORMAL = 100

STATE_PENDING = "pending"
STATE_TRANSMITTING = "transmitting"
STATE_ACKNOWLEDGED = "acknowledged"
STATE_FAILED_RETRYABLE = "failed_retryable"
STATE_FAILED_TERMINAL = "failed_terminal"

_CLAIMABLE_STATES = (STATE_PENDING, STATE_FAILED_RETRYABLE)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS spool_items (
    item_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    priority INTEGER NOT NULL,
    media_type TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    content_length INTEGER NOT NULL,
    content_sha256 TEXT NOT NULL,
    state TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    next_attempt_at REAL NOT NULL,
    last_error TEXT,
    enqueued_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_spool_items_claim
    ON spool_items(state, priority, enqueued_at);
CREATE TABLE IF NOT EXISTS spool_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_META_KEYS = (
    "evicted_count_total",
    "evicted_bytes_total",
    "last_eviction_reason",
    "last_evicted_at",
    "acknowledged_count_total",
    "acknowledged_bytes_total",
)


class SpoolCapacityError(ValueError):
    """Raised when an item cannot be enqueued even after evicting everything evictable."""


@dataclass(frozen=True)
class SpoolItem:
    item_id: str
    kind: str
    priority: int
    media_type: str
    metadata: dict
    content_length: int
    content_sha256: str
    state: str
    attempt_count: int
    next_attempt_at: float
    last_error: str | None
    enqueued_at: float
    updated_at: float


@dataclass(frozen=True)
class SpoolDiagnostics:
    pending_count: int
    pending_bytes: int
    transmitting_count: int
    failed_terminal_count: int
    oldest_pending_age_seconds: float | None
    evicted_count_total: int
    evicted_bytes_total: int
    last_eviction_reason: str | None
    last_evicted_at: float | None
    acknowledged_count_total: int
    free_bytes: int | None


def _row_to_item(row: sqlite3.Row) -> SpoolItem:
    return SpoolItem(
        item_id=row["item_id"],
        kind=row["kind"],
        priority=row["priority"],
        media_type=row["media_type"],
        metadata=json.loads(row["metadata_json"]),
        content_length=row["content_length"],
        content_sha256=row["content_sha256"],
        state=row["state"],
        attempt_count=row["attempt_count"],
        next_attempt_at=row["next_attempt_at"],
        last_error=row["last_error"],
        enqueued_at=row["enqueued_at"],
        updated_at=row["updated_at"],
    )


def backoff_seconds(attempt_count: int, *, base: float, cap: float, rng: random.Random) -> float:
    """Full-jitter exponential backoff, bounded -- never a tight retry loop.

    `attempt_count` is the count *including* the attempt that just failed
    (i.e. the first retry after one failed attempt uses `attempt_count=1`).
    Uncapped attempt count is fine: `2 ** attempt_count` is clamped by `cap`
    long before it could overflow.
    """

    ceiling = min(cap, base * (2 ** min(attempt_count, 20)))
    return rng.uniform(0.0, max(base, ceiling))


class TransportSpool:
    """Durable spool: SQLite for state, one file per item's payload bytes."""

    def __init__(
        self,
        spool_dir: Path,
        *,
        max_bytes: int,
        max_items: int,
        min_free_bytes: int,
        backoff_base_seconds: float,
        backoff_cap_seconds: float,
        clock=time.time,
        rng: random.Random | None = None,
    ) -> None:
        self._dir = spool_dir
        self._items_dir = spool_dir / "items"
        self._items_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._max_bytes = max_bytes
        self._max_items = max_items
        self._min_free_bytes = min_free_bytes
        self._backoff_base_seconds = backoff_base_seconds
        self._backoff_cap_seconds = backoff_cap_seconds
        self._clock = clock
        self._rng = rng or random.Random()
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            str(spool_dir / "spool.db"), check_same_thread=False, isolation_level=None
        )
        self._connection.row_factory = sqlite3.Row
        with self._lock:
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.executescript(_SCHEMA)
            existing = {row["key"] for row in self._connection.execute("SELECT key FROM spool_meta")}
            for key in _META_KEYS:
                if key not in existing:
                    self._connection.execute(
                        "INSERT INTO spool_meta(key, value) VALUES (?, ?)", (key, "0")
                    )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    # -- meta counters --------------------------------------------------

    def _meta_get(self, key: str) -> str:
        row = self._connection.execute("SELECT value FROM spool_meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row is not None else "0"

    def _meta_set(self, key: str, value: str) -> None:
        self._connection.execute(
            "INSERT INTO spool_meta(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def _meta_increment(self, key: str, amount: int) -> None:
        self._meta_set(key, str(int(self._meta_get(key)) + amount))

    # -- capacity / eviction ---------------------------------------------

    def _current_totals(self) -> tuple[int, int]:
        row = self._connection.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(content_length), 0) AS b FROM spool_items"
        ).fetchone()
        return int(row["n"]), int(row["b"])

    def _free_bytes(self) -> int | None:
        try:
            return shutil.disk_usage(self._dir).free
        except OSError:
            return None

    def _blob_path(self, item_id: str) -> Path:
        return self._items_dir / f"{item_id}.bin"

    def _delete_item_row(self, item_id: str) -> int:
        row = self._connection.execute(
            "SELECT content_length FROM spool_items WHERE item_id = ?", (item_id,)
        ).fetchone()
        if row is None:
            return 0
        self._connection.execute("DELETE FROM spool_items WHERE item_id = ?", (item_id,))
        try:
            self._blob_path(item_id).unlink()
        except OSError:
            pass
        return int(row["content_length"])

    def _evict_oldest_evictable(self, *, reason: str) -> bool:
        """Deterministic: oldest evictable (pending/failed_retryable) item first.

        Never touches `transmitting`/`acknowledged` rows -- an
        in-flight-or-just-confirmed item is not a candidate for silent
        capacity eviction. Records counters so this is diagnosable, never a
        silent drop (Phase G: "do not silently discard... record
        counters/reasons").
        """

        row = self._connection.execute(
            f"SELECT item_id FROM spool_items WHERE state IN "
            f"({','.join('?' for _ in _CLAIMABLE_STATES)}) "
            "ORDER BY enqueued_at ASC LIMIT 1",
            _CLAIMABLE_STATES,
        ).fetchone()
        if row is None:
            return False
        freed = self._delete_item_row(row["item_id"])
        self._meta_increment("evicted_count_total", 1)
        self._meta_increment("evicted_bytes_total", freed)
        self._meta_set("last_eviction_reason", reason)
        self._meta_set("last_evicted_at", repr(self._clock()))
        return True

    def _make_room_for(self, new_item_bytes: int) -> None:
        """Evict oldest-first until the new item fits every bound, or raise.

        Preference order matches Phase G exactly: this only ever evicts
        `pending`/`failed_retryable` work (never acknowledged truth), and
        refuses outright (never silently exceeds a bound) if nothing is left
        to evict and the new item still would not fit -- "avoid total node
        failure from a full disk" wins over accepting more work.
        """

        for _ in range(self._max_items + 1):
            count, total_bytes = self._current_totals()
            free = self._free_bytes()
            over_count = count + 1 > self._max_items
            over_bytes = total_bytes + new_item_bytes > self._max_bytes
            over_disk_floor = free is not None and free - new_item_bytes < self._min_free_bytes
            if not (over_count or over_bytes or over_disk_floor):
                return
            reason = "item_cap" if over_count else ("byte_cap" if over_bytes else "disk_floor")
            if not self._evict_oldest_evictable(reason=reason):
                raise SpoolCapacityError(reason)
        raise SpoolCapacityError("item_cap")

    # -- enqueue / lifecycle ----------------------------------------------

    def enqueue(
        self,
        *,
        kind: str,
        payload: bytes,
        media_type: str,
        priority: int = PRIORITY_NORMAL,
        metadata: dict | None = None,
    ) -> str:
        """Durably persist one bounded work item; returns its item_id.

        The blob is written to disk *before* the DB row is committed, and
        the DB row is what a reader trusts exists -- so a crash between the
        two leaves, at worst, an orphaned blob file next to no row (safe:
        cleaned up by `sweep_orphaned_blobs`), never a row pointing at a
        blob that was never durably written.
        """

        item_id = uuid.uuid4().hex
        content_sha256 = hashlib.sha256(payload).hexdigest()
        now = self._clock()
        with self._lock:
            self._make_room_for(len(payload))
            atomic_write_bytes(self._blob_path(item_id), payload)
            self._connection.execute(
                "INSERT INTO spool_items ("
                "item_id, kind, priority, media_type, metadata_json, content_length, "
                "content_sha256, state, attempt_count, next_attempt_at, last_error, "
                "enqueued_at, updated_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, NULL, ?, ?)",
                (
                    item_id,
                    kind,
                    priority,
                    media_type,
                    json.dumps(metadata or {}, separators=(",", ":"), sort_keys=True),
                    len(payload),
                    content_sha256,
                    STATE_PENDING,
                    now,
                    now,
                    now,
                ),
            )
        return item_id

    def read_payload(self, item_id: str) -> bytes:
        return self._blob_path(item_id).read_bytes()

    def claim_next_batch(self, limit: int) -> list[SpoolItem]:
        """Atomically move up to `limit` due, eligible items to `transmitting`."""

        with self._lock:
            now = self._clock()
            placeholders = ",".join("?" for _ in _CLAIMABLE_STATES)
            rows = self._connection.execute(
                f"SELECT item_id FROM spool_items WHERE state IN ({placeholders}) "
                "AND next_attempt_at <= ? ORDER BY priority ASC, enqueued_at ASC LIMIT ?",
                (*_CLAIMABLE_STATES, now, limit),
            ).fetchall()
            claimed: list[SpoolItem] = []
            for row in rows:
                self._connection.execute(
                    "UPDATE spool_items SET state = ?, updated_at = ? WHERE item_id = ?",
                    (STATE_TRANSMITTING, now, row["item_id"]),
                )
                item_row = self._connection.execute(
                    "SELECT * FROM spool_items WHERE item_id = ?", (row["item_id"],)
                ).fetchone()
                claimed.append(_row_to_item(item_row))
            return claimed

    def mark_acknowledged(self, item_id: str) -> None:
        with self._lock:
            now = self._clock()
            row = self._connection.execute(
                "SELECT content_length FROM spool_items WHERE item_id = ?", (item_id,)
            ).fetchone()
            self._connection.execute(
                "UPDATE spool_items SET state = ?, updated_at = ? WHERE item_id = ?",
                (STATE_ACKNOWLEDGED, now, item_id),
            )
            if row is not None:
                self._meta_increment("acknowledged_count_total", 1)
                self._meta_increment("acknowledged_bytes_total", int(row["content_length"]))

    def prune_acknowledged(self, item_id: str) -> None:
        """Delete an acknowledged item's row and blob -- the host is now the record of truth."""

        with self._lock:
            row = self._connection.execute(
                "SELECT state FROM spool_items WHERE item_id = ?", (item_id,)
            ).fetchone()
            if row is None or row["state"] != STATE_ACKNOWLEDGED:
                return
            self._delete_item_row(item_id)

    def mark_failed_retryable(self, item_id: str, *, error: str) -> float:
        """Record a recoverable failure; returns the computed `next_attempt_at`."""

        with self._lock:
            now = self._clock()
            row = self._connection.execute(
                "SELECT attempt_count FROM spool_items WHERE item_id = ?", (item_id,)
            ).fetchone()
            attempt_count = (row["attempt_count"] if row is not None else 0) + 1
            delay = backoff_seconds(
                attempt_count,
                base=self._backoff_base_seconds,
                cap=self._backoff_cap_seconds,
                rng=self._rng,
            )
            next_attempt_at = now + delay
            self._connection.execute(
                "UPDATE spool_items SET state = ?, attempt_count = ?, next_attempt_at = ?, "
                "last_error = ?, updated_at = ? WHERE item_id = ?",
                (STATE_FAILED_RETRYABLE, attempt_count, next_attempt_at, error, now, item_id),
            )
            return next_attempt_at

    def mark_failed_terminal(self, item_id: str, *, error: str) -> None:
        """Record a non-recoverable failure (e.g. protocol incompatibility).

        Excluded from `claim_next_batch` forever after -- retrying a
        genuinely incompatible request would spin indefinitely for no
        possible benefit (Scenario 8). The row is kept, not deleted, so it
        remains diagnosable and still participates in ordinary capacity
        accounting/eviction like any other item.
        """

        with self._lock:
            now = self._clock()
            self._connection.execute(
                "UPDATE spool_items SET state = ?, last_error = ?, updated_at = ? WHERE item_id = ?",
                (STATE_FAILED_TERMINAL, error, now, item_id),
            )

    def recover_incomplete_on_startup(self) -> int:
        """Any row still `transmitting` was mid-flight when the process last stopped.

        The chunked wire protocol makes it safe to simply retry: the host
        reports how many bytes of this item_id it already durably has, so
        nothing already-delivered is re-sent, and nothing is lost either.
        See Phase I / Scenario 3.
        """

        with self._lock:
            now = self._clock()
            rows = self._connection.execute(
                "SELECT item_id, attempt_count FROM spool_items WHERE state = ?",
                (STATE_TRANSMITTING,),
            ).fetchall()
            for row in rows:
                self._connection.execute(
                    "UPDATE spool_items SET state = ?, attempt_count = ?, next_attempt_at = ?, "
                    "last_error = ?, updated_at = ? WHERE item_id = ?",
                    (
                        STATE_FAILED_RETRYABLE,
                        row["attempt_count"] + 1,
                        now,
                        "interrupted_by_restart",
                        now,
                        row["item_id"],
                    ),
                )
            return len(rows)

    def sweep_orphaned_blobs(self) -> int:
        """Delete any payload file with no corresponding DB row.

        Only possible after a crash between writing the blob and committing
        the row (see `enqueue`'s docstring) -- always safe, since a reader
        never trusts a blob file without a row pointing at it.
        """

        known = {
            row["item_id"] for row in self._connection.execute("SELECT item_id FROM spool_items")
        }
        removed = 0
        for path in self._items_dir.glob("*.bin"):
            if path.stem not in known:
                try:
                    path.unlink()
                    removed += 1
                except OSError:
                    pass
        return removed

    # -- reads --------------------------------------------------------

    def get(self, item_id: str) -> SpoolItem | None:
        # Real bug caught by acceptance testing (genuine cross-thread access
        # -- the async worker's `asyncio.to_thread` calls vs. a caller on a
        # different thread reading spool state concurrently): the shared
        # `sqlite3.Connection` (opened `check_same_thread=False` precisely
        # to allow this) still raises `InterfaceError` under truly
        # simultaneous use from two threads unless every access, reads
        # included, goes through the same lock every mutation already used.
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM spool_items WHERE item_id = ?", (item_id,)
            ).fetchone()
            return _row_to_item(row) if row is not None else None

    def list_items(self, states: tuple[str, ...] | None = None) -> list[SpoolItem]:
        with self._lock:
            if states is None:
                rows = self._connection.execute(
                    "SELECT * FROM spool_items ORDER BY priority ASC, enqueued_at ASC"
                ).fetchall()
            else:
                placeholders = ",".join("?" for _ in states)
                rows = self._connection.execute(
                    f"SELECT * FROM spool_items WHERE state IN ({placeholders}) "
                    "ORDER BY priority ASC, enqueued_at ASC",
                    states,
                ).fetchall()
            return [_row_to_item(row) for row in rows]

    def diagnostics(self) -> SpoolDiagnostics:
        with self._lock:
            now = self._clock()
            pending_rows = self._connection.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(content_length), 0) AS b, "
                "MIN(enqueued_at) AS oldest FROM spool_items WHERE state IN (?, ?)",
                (STATE_PENDING, STATE_FAILED_RETRYABLE),
            ).fetchone()
            transmitting = self._connection.execute(
                "SELECT COUNT(*) AS n FROM spool_items WHERE state = ?", (STATE_TRANSMITTING,)
            ).fetchone()
            terminal = self._connection.execute(
                "SELECT COUNT(*) AS n FROM spool_items WHERE state = ?", (STATE_FAILED_TERMINAL,)
            ).fetchone()
            oldest_age = (now - pending_rows["oldest"]) if pending_rows["oldest"] is not None else None
            last_evicted_raw = self._meta_get("last_evicted_at")
            return SpoolDiagnostics(
                pending_count=int(pending_rows["n"]),
                pending_bytes=int(pending_rows["b"]),
                transmitting_count=int(transmitting["n"]),
                failed_terminal_count=int(terminal["n"]),
                oldest_pending_age_seconds=oldest_age,
                evicted_count_total=int(self._meta_get("evicted_count_total")),
                evicted_bytes_total=int(self._meta_get("evicted_bytes_total")),
                last_eviction_reason=self._meta_get("last_eviction_reason") or None,
                last_evicted_at=float(last_evicted_raw) if last_evicted_raw and last_evicted_raw != "0" else None,
                acknowledged_count_total=int(self._meta_get("acknowledged_count_total")),
                free_bytes=self._free_bytes(),
            )
