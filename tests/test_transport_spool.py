"""Tier 1: Camera Node durable transport spool.

Covers Phase B/D/G's mandatory lifecycle, bounds/eviction, backoff, and
restart-recovery requirements directly against `TransportSpool` -- no
network, no FastAPI, no asyncio; see docs/remote-intermittent-wan
-transport-v1-design.md.
"""

from __future__ import annotations

import random

import pytest

from mockingbird_node.transport_spool import (
    PRIORITY_CRITICAL,
    PRIORITY_NORMAL,
    STATE_ACKNOWLEDGED,
    STATE_FAILED_RETRYABLE,
    STATE_FAILED_TERMINAL,
    STATE_PENDING,
    STATE_TRANSMITTING,
    SpoolCapacityError,
    TransportSpool,
    backoff_seconds,
)


def _spool(tmp_path, *, clock=None, **overrides) -> TransportSpool:
    defaults = dict(
        max_bytes=10_000_000,
        max_items=100,
        min_free_bytes=0,
        backoff_base_seconds=1.0,
        backoff_cap_seconds=60.0,
    )
    defaults.update(overrides)
    kwargs = {"clock": clock} if clock is not None else {}
    return TransportSpool(tmp_path / "spool", **defaults, **kwargs)


def test_enqueue_persists_metadata_and_computes_hash(tmp_path) -> None:
    spool = _spool(tmp_path)
    item_id = spool.enqueue(kind="evidence_capture", payload=b"hello world", media_type="image/jpeg", metadata={"camera_id": "cam-1"})
    item = spool.get(item_id)
    assert item is not None
    assert item.state == STATE_PENDING
    assert item.content_length == len(b"hello world")
    assert item.content_sha256 == __import__("hashlib").sha256(b"hello world").hexdigest()
    assert item.metadata == {"camera_id": "cam-1"}
    assert item.priority == PRIORITY_NORMAL
    assert spool.read_payload(item_id) == b"hello world"


def test_claim_orders_by_priority_then_enqueued_at(tmp_path) -> None:
    clock = _FakeClock(start=1000.0)
    spool = _spool(tmp_path, clock=clock.now)
    low = spool.enqueue(kind="k", payload=b"a", media_type="t", priority=PRIORITY_NORMAL)
    clock.advance(1)
    critical = spool.enqueue(kind="k", payload=b"b", media_type="t", priority=PRIORITY_CRITICAL)
    clock.advance(1)
    another_normal = spool.enqueue(kind="k", payload=b"c", media_type="t", priority=PRIORITY_NORMAL)

    claimed = spool.claim_next_batch(10)
    assert [item.item_id for item in claimed] == [critical, low, another_normal]
    assert all(item.state == STATE_TRANSMITTING for item in claimed)


def test_claim_respects_limit(tmp_path) -> None:
    spool = _spool(tmp_path)
    for _ in range(5):
        spool.enqueue(kind="k", payload=b"x", media_type="t")
    claimed = spool.claim_next_batch(2)
    assert len(claimed) == 2
    remaining_pending = spool.list_items((STATE_PENDING,))
    assert len(remaining_pending) == 3


def test_ack_then_prune_removes_row_and_blob(tmp_path) -> None:
    spool = _spool(tmp_path)
    item_id = spool.enqueue(kind="k", payload=b"payload-bytes", media_type="t")
    spool.claim_next_batch(1)
    spool.mark_acknowledged(item_id)
    acknowledged = spool.get(item_id)
    assert acknowledged is not None and acknowledged.state == STATE_ACKNOWLEDGED

    spool.prune_acknowledged(item_id)
    assert spool.get(item_id) is None
    diagnostics = spool.diagnostics()
    assert diagnostics.acknowledged_count_total == 1
    assert diagnostics.pending_count == 0


def test_failed_retryable_sets_future_next_attempt_and_is_not_immediately_reclaimable(tmp_path) -> None:
    clock = _FakeClock(start=5000.0)
    spool = _spool(tmp_path, clock=clock.now, backoff_base_seconds=10.0, backoff_cap_seconds=100.0)
    item_id = spool.enqueue(kind="k", payload=b"x", media_type="t")
    spool.claim_next_batch(1)
    next_attempt_at = spool.mark_failed_retryable(item_id, error="transport_host_unreachable")
    assert next_attempt_at > clock.now()

    # Not due yet -- claim_next_batch must not return it.
    assert spool.claim_next_batch(10) == []

    clock.set(next_attempt_at + 0.01)
    reclaimed = spool.claim_next_batch(10)
    assert [item.item_id for item in reclaimed] == [item_id]
    assert reclaimed[0].attempt_count == 1
    assert reclaimed[0].last_error == "transport_host_unreachable"


def test_backoff_grows_and_is_bounded_by_cap() -> None:
    rng = random.Random(1234)
    small = backoff_seconds(1, base=2.0, cap=300.0, rng=rng)
    large_attempt = backoff_seconds(30, base=2.0, cap=300.0, rng=rng)
    assert 0.0 <= small <= 4.0
    assert 0.0 <= large_attempt <= 300.0
    # A very large attempt count must never exceed the cap -- no unbounded growth.
    for attempt in (5, 10, 20, 50, 1000):
        assert backoff_seconds(attempt, base=2.0, cap=300.0, rng=rng) <= 300.0


def test_failed_terminal_is_never_reclaimed(tmp_path) -> None:
    spool = _spool(tmp_path)
    item_id = spool.enqueue(kind="k", payload=b"x", media_type="t")
    spool.claim_next_batch(1)
    spool.mark_failed_terminal(item_id, error="transport_item_conflict")
    item = spool.get(item_id)
    assert item is not None and item.state == STATE_FAILED_TERMINAL
    assert spool.claim_next_batch(10) == []
    # Still diagnosable, still present -- not silently dropped.
    diagnostics = spool.diagnostics()
    assert diagnostics.failed_terminal_count == 1


def test_recover_incomplete_on_startup_resets_transmitting_items(tmp_path) -> None:
    path = tmp_path / "spool"
    spool = TransportSpool(
        path, max_bytes=10_000_000, max_items=100, min_free_bytes=0,
        backoff_base_seconds=1.0, backoff_cap_seconds=60.0,
    )
    item_id = spool.enqueue(kind="k", payload=b"mid-flight", media_type="t")
    spool.claim_next_batch(1)
    assert spool.get(item_id).state == STATE_TRANSMITTING
    spool.close()  # simulates the process dying mid-delivery, no clean shutdown

    reopened = TransportSpool(
        path, max_bytes=10_000_000, max_items=100, min_free_bytes=0,
        backoff_base_seconds=1.0, backoff_cap_seconds=60.0,
    )
    recovered_count = reopened.recover_incomplete_on_startup()
    assert recovered_count == 1
    item = reopened.get(item_id)
    assert item.state == STATE_FAILED_RETRYABLE
    assert item.last_error == "interrupted_by_restart"
    assert reopened.read_payload(item_id) == b"mid-flight"  # payload survived the "crash" intact


def test_sweep_orphaned_blobs_removes_files_with_no_row(tmp_path) -> None:
    spool = _spool(tmp_path)
    orphan = spool._items_dir / "orphan-item.bin"
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_bytes(b"leftover")
    removed = spool.sweep_orphaned_blobs()
    assert removed == 1
    assert not orphan.exists()


def test_item_count_bound_evicts_oldest_pending_first(tmp_path) -> None:
    clock = _FakeClock(start=0.0)
    spool = _spool(tmp_path, clock=clock.now, max_items=3, max_bytes=10_000_000)
    ids = []
    for index in range(3):
        ids.append(spool.enqueue(kind="k", payload=b"x", media_type="t"))
        clock.advance(1)
    newest = spool.enqueue(kind="k", payload=b"x", media_type="t")
    assert spool.get(ids[0]) is None  # oldest evicted
    assert spool.get(newest) is not None
    diagnostics = spool.diagnostics()
    assert diagnostics.evicted_count_total == 1
    assert diagnostics.last_eviction_reason == "item_cap"


def test_byte_bound_evicts_until_new_item_fits(tmp_path) -> None:
    spool = _spool(tmp_path, max_items=100, max_bytes=25)
    first = spool.enqueue(kind="k", payload=b"a" * 10, media_type="t")
    spool.enqueue(kind="k", payload=b"b" * 10, media_type="t")
    spool.enqueue(kind="k", payload=b"c" * 10, media_type="t")  # forces eviction of `first`
    assert spool.get(first) is None
    diagnostics = spool.diagnostics()
    assert diagnostics.pending_bytes <= 25
    assert diagnostics.last_eviction_reason == "byte_cap"


def test_disk_floor_triggers_eviction(tmp_path, monkeypatch) -> None:
    spool = _spool(tmp_path, max_items=100, max_bytes=10_000_000, min_free_bytes=1000)
    first = spool.enqueue(kind="k", payload=b"a" * 10, media_type="t")

    # Simulates real disk pressure that eviction actually relieves: below
    # the floor while `first` still occupies the spool, above it once
    # evicted -- distinguishing "eviction helped" from "the disk is simply
    # externally full and nothing the spool does will ever admit more work"
    # (see test_capacity_error_when_item_alone_exceeds_bound for that case).
    class _Usage:
        def __init__(self, free: int) -> None:
            self.free = free

    def fake_disk_usage(_dir):
        return _Usage(500 if spool.get(first) is not None else 2000)

    monkeypatch.setattr("mockingbird_node.transport_spool.shutil.disk_usage", fake_disk_usage)
    spool.enqueue(kind="k", payload=b"b" * 10, media_type="t")
    assert spool.get(first) is None
    diagnostics = spool.diagnostics()
    assert diagnostics.last_eviction_reason == "disk_floor"


def test_capacity_error_when_item_alone_exceeds_bound(tmp_path) -> None:
    spool = _spool(tmp_path, max_items=100, max_bytes=5)
    with pytest.raises(SpoolCapacityError):
        spool.enqueue(kind="k", payload=b"way too big", media_type="t")
    # Refusing the new item must not have evicted anything that didn't exist.
    diagnostics = spool.diagnostics()
    assert diagnostics.evicted_count_total == 0


def test_acknowledged_and_transmitting_items_are_never_evicted(tmp_path) -> None:
    spool = _spool(tmp_path, max_items=2, max_bytes=10_000_000)
    acknowledged_id = spool.enqueue(kind="k", payload=b"x", media_type="t")
    spool.claim_next_batch(1)
    spool.mark_acknowledged(acknowledged_id)
    transmitting_id = spool.enqueue(kind="k", payload=b"x", media_type="t")
    spool.claim_next_batch(1)
    assert spool.get(transmitting_id).state == STATE_TRANSMITTING

    # A third enqueue would need to evict to respect max_items=2, but
    # neither existing item is evictable (acknowledged / transmitting) --
    # must raise rather than touch either.
    with pytest.raises(SpoolCapacityError):
        spool.enqueue(kind="k", payload=b"x", media_type="t")
    assert spool.get(acknowledged_id) is not None
    assert spool.get(transmitting_id) is not None


class _FakeClock:
    def __init__(self, *, start: float) -> None:
        self._now = start

    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds

    def set(self, value: float) -> None:
        self._now = value
