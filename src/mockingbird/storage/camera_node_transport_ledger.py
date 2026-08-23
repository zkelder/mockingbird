"""Durable filesystem ledger for Camera Node transport delivery (host side).

Deliberately has no HTTP-framework dependency (no `fastapi`/`pydantic`) so
`mockingbird.diagnostics.doctor` can read a Node's last-reported backlog
summary without inverting this codebase's existing layering (nothing under
`diagnostics/` imports from `api/` today; see the Remote /
Intermittent-WAN Transport Foundation v1 design doc). The HTTP endpoint
layer (`mockingbird.api.camera_node_transport`) imports this module and
translates `TransportLedgerError` into `HTTPException`s at the API
boundary -- this module only ever raises the former.

Storage layout: `<root>/<node_id>/items/<item_id>.{part,meta.json}` while
incomplete, atomically promoted to `<root>/<node_id>/completed/<item_id>.
{bin,meta.json}` only after size+hash verification (never before -- an
incomplete transfer must never become authoritative). One
`<root>/<node_id>/node_status.json` holds the Node's latest self-reported
backlog summary, refreshed on every declare call. No SQL table, column, or
migration.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import threading
import time
from typing import Any


DEFAULT_TRANSPORT_ROOT = "data/camera_node_transport"
TRANSPORT_ROOT_ENV_VAR = "MOCKINGBIRD_CAMERA_NODE_TRANSPORT_ROOT"

_MAX_METADATA_BYTES = 8_000


def transport_root_from_env() -> str:
    return os.getenv(TRANSPORT_ROOT_ENV_VAR, DEFAULT_TRANSPORT_ROOT)


def resolve_transport_root(transport_root: str | Path | None = None) -> Path:
    return Path(transport_root or transport_root_from_env())


class TransportLedgerError(ValueError):
    """Carries enough for the API layer to build the right HTTP response
    without this module knowing anything about HTTP."""

    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        super().__init__(error_code)
        self.status_code = status_code
        self.error_code = error_code
        self.message = message


@dataclass(frozen=True)
class TransportItemStatus:
    item_id: str
    state: str
    received_bytes: int
    content_length: int


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    data = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{int(time.time() * 1000)}.tmp")
    with open(temporary, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return None


def _sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


class _ItemLocks:
    """One lock per (node_id, item_id) -- cheap defensiveness against a
    genuinely concurrent retry racing itself; real traffic is one Node
    sending chunks for one item sequentially, so contention is not expected
    in practice."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[tuple[str, str], threading.Lock] = {}

    def get(self, node_id: str, item_id: str) -> threading.Lock:
        key = (node_id, item_id)
        with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._locks[key] = lock
            return lock


_ITEM_LOCKS = _ItemLocks()


class TransportLedger:
    """Filesystem-backed durable ledger: in-progress items, and the
    completed-item dedup record. See this module's own docstring."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _node_dir(self, node_id: str) -> Path:
        # `node_id` is host-derived (`f"node-{sha256(...)[:16]}"`, see
        # `mockingbird_node.app`), already filesystem-safe, but validated
        # again here defensively since it becomes a directory name.
        if not node_id or "/" in node_id or "\\" in node_id or node_id in {".", ".."}:
            raise TransportLedgerError(400, "transport_node_id_invalid", "Invalid Node identity.")
        return self._root / node_id

    def _items_dir(self, node_id: str) -> Path:
        return self._node_dir(node_id) / "items"

    def _completed_dir(self, node_id: str) -> Path:
        return self._node_dir(node_id) / "completed"

    def _part_path(self, node_id: str, item_id: str) -> Path:
        return self._items_dir(node_id) / f"{item_id}.part"

    def _meta_path(self, node_id: str, item_id: str) -> Path:
        return self._items_dir(node_id) / f"{item_id}.meta.json"

    def _completed_meta_path(self, node_id: str, item_id: str) -> Path:
        return self._completed_dir(node_id) / f"{item_id}.meta.json"

    def _completed_blob_path(self, node_id: str, item_id: str) -> Path:
        return self._completed_dir(node_id) / f"{item_id}.bin"

    def is_completed(self, node_id: str, item_id: str) -> bool:
        return self._completed_meta_path(node_id, item_id).exists()

    def received_bytes(self, node_id: str, item_id: str) -> int:
        part = self._part_path(node_id, item_id)
        try:
            return part.stat().st_size
        except FileNotFoundError:
            return 0

    def declare(
        self,
        *,
        node_id: str,
        item_id: str,
        kind: str,
        priority: int,
        media_type: str,
        content_length: int,
        content_sha256: str,
        chunk_size: int,
        metadata: dict[str, Any],
    ) -> int:
        """Idempotent: a repeated declare for a known item_id with matching
        content signature just reports current progress; a *conflicting*
        signature (same item_id, different size/hash -- see the design
        doc's idempotency-key discussion) is refused rather than silently
        accepted, since resending would never converge on the original
        intent. Returns durably-received bytes so far (0 for a new item)."""

        if self.is_completed(node_id, item_id):
            existing = _read_json(self._completed_meta_path(node_id, item_id)) or {}
            if existing.get("content_sha256") != content_sha256 or existing.get("content_length") != content_length:
                raise TransportLedgerError(
                    409, "transport_item_conflict", "This item_id was already completed with different content."
                )
            return content_length
        meta_path = self._meta_path(node_id, item_id)
        existing_meta = _read_json(meta_path)
        if existing_meta is not None and (
            existing_meta.get("content_sha256") != content_sha256
            or existing_meta.get("content_length") != content_length
        ):
            raise TransportLedgerError(
                409, "transport_item_conflict", "This item_id is already in progress with different content."
            )
        metadata_json = json.dumps(metadata, separators=(",", ":"), sort_keys=True)
        if len(metadata_json) > _MAX_METADATA_BYTES:
            raise TransportLedgerError(400, "transport_metadata_too_large", "Item metadata is too large.")
        self._items_dir(node_id).mkdir(mode=0o700, parents=True, exist_ok=True)
        _atomic_write_json(
            meta_path,
            {
                "item_id": item_id,
                "kind": kind,
                "priority": priority,
                "media_type": media_type,
                "content_length": content_length,
                "content_sha256": content_sha256,
                "chunk_size": chunk_size,
                "metadata": metadata,
                "declared_at": time.time(),
            },
        )
        return self.received_bytes(node_id, item_id)

    def write_chunk(
        self, *, node_id: str, item_id: str, chunk_index: int, chunk: bytes, declared_sha256: str
    ) -> int:
        meta = _read_json(self._meta_path(node_id, item_id))
        if meta is None:
            if self.is_completed(node_id, item_id):
                # An ack for `complete` was lost; the Node is retrying a
                # chunk it thinks is still outstanding. Nothing left to do.
                completed = _read_json(self._completed_meta_path(node_id, item_id)) or {}
                return int(completed.get("content_length", 0))
            raise TransportLedgerError(404, "transport_item_unknown", "Declare this item before sending chunks.")
        if hashlib.sha256(chunk).hexdigest() != declared_sha256:
            raise TransportLedgerError(400, "transport_chunk_hash_mismatch", "Chunk integrity check failed.")
        chunk_size = meta["chunk_size"]
        expected_offset = chunk_index * chunk_size
        current = self.received_bytes(node_id, item_id)
        if expected_offset > current:
            # A gap -- an earlier chunk never arrived. Never write past a
            # hole: the client must resend from `current`, which the
            # response's `received_bytes` already tells it.
            raise TransportLedgerError(409, "transport_chunk_out_of_order", "Chunk is out of order.")
        part_path = self._part_path(node_id, item_id)
        with self._locks_for(node_id, item_id):
            current = self.received_bytes(node_id, item_id)
            if expected_offset < current:
                # Already-durably-received (a retried chunk after a lost
                # ack) -- idempotent no-op, not an error.
                return current
            with open(part_path, "ab") as handle:
                handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            return self.received_bytes(node_id, item_id)

    def _locks_for(self, node_id: str, item_id: str) -> threading.Lock:
        return _ITEM_LOCKS.get(node_id, item_id)

    def complete(self, *, node_id: str, item_id: str) -> None:
        if self.is_completed(node_id, item_id):
            return
        meta = _read_json(self._meta_path(node_id, item_id))
        if meta is None:
            raise TransportLedgerError(404, "transport_item_unknown", "Declare this item before completing it.")
        part_path = self._part_path(node_id, item_id)
        received = self.received_bytes(node_id, item_id)
        expected_length = meta["content_length"]
        if received != expected_length:
            raise TransportLedgerError(
                409, "transport_item_incomplete", f"Received {received} of {expected_length} bytes."
            )
        actual_sha256 = _sha256_of_file(part_path)
        if actual_sha256 != meta["content_sha256"]:
            # Reset so the *next* declare reports received_bytes=0 and the
            # Node re-sends cleanly -- see the design doc's "Resumability"
            # decision. Recoverable, not terminal: a flaky link can corrupt
            # bytes without the underlying evidence itself being bad.
            with self._locks_for(node_id, item_id):
                part_path.unlink(missing_ok=True)
            raise TransportLedgerError(422, "transport_item_hash_mismatch", "Content hash did not match after transfer.")
        self._completed_dir(node_id).mkdir(mode=0o700, parents=True, exist_ok=True)
        os.replace(part_path, self._completed_blob_path(node_id, item_id))
        _atomic_write_json(self._completed_meta_path(node_id, item_id), {**meta, "completed_at": time.time()})
        self._meta_path(node_id, item_id).unlink(missing_ok=True)

    def status(self, *, node_id: str, item_id: str) -> TransportItemStatus | None:
        if self.is_completed(node_id, item_id):
            meta = _read_json(self._completed_meta_path(node_id, item_id)) or {}
            length = meta.get("content_length", 0)
            return TransportItemStatus(item_id=item_id, state="completed", received_bytes=length, content_length=length)
        meta = _read_json(self._meta_path(node_id, item_id))
        if meta is None:
            return None
        return TransportItemStatus(
            item_id=item_id,
            state="in_progress",
            received_bytes=self.received_bytes(node_id, item_id),
            content_length=meta.get("content_length", 0),
        )

    def record_backlog_summary(self, *, node_id: str, summary: dict[str, Any]) -> None:
        """The Node's own self-reported backlog rides along on every
        declare call -- see the design doc's "Diagnostics": the host never
        dials out to ask for this, which would defeat the point for a
        WAN-constrained node."""

        _atomic_write_json(self._node_dir(node_id) / "node_status.json", {**summary, "reported_at": time.time()})

    def read_backlog_summary(self, node_id: str) -> dict[str, Any] | None:
        return _read_json(self._node_dir(node_id) / "node_status.json")


def read_camera_node_transport_backlog_summary(node_id: str, *, transport_root: Path | None = None) -> dict[str, Any] | None:
    """Doctor-facing read of the latest self-reported backlog summary for
    one Node -- a plain filesystem read, no network call, matching every
    other `_gather_*` in `diagnostics.doctor`'s "bounded, isolated I/O"
    convention."""

    return TransportLedger(resolve_transport_root(transport_root)).read_backlog_summary(node_id)
