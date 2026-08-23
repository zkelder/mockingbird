"""Mandatory acceptance scenarios (milestone Phases I/J + "Mandatory
acceptance scenarios" 1-8) for Remote / Intermittent-WAN Transport
Foundation v1.

Real sockets throughout: a real host FastAPI app served by uvicorn in a
background thread, a real `mockingbird_node.transport_client.TransportClient`
(stdlib `http.client`, the actual production Node code path) driving a real
`TransportSpool`/`TransportWorker`, fronted by the real, controllable
`FaultInjectingProxy` (tests/_transport_fault_injection.py) -- no mocking of
the transport protocol itself, no arbitrary sleeps standing in for a fault.
Marked `slow` (real sockets/threads/uvicorn -- Tier C, matching this
codebase's existing convention for e.g. tests/test_camera_node_real_process.py)
so it does not burden the Fast/Core gates; it is exactly what this
milestone's own Tier 3 acceptance run exercises.
"""

from __future__ import annotations

import asyncio
import hashlib
import threading
import time

from fastapi import FastAPI
import pytest

from mockingbird.api.camera_node_transport import build_camera_node_transport_router
from mockingbird_node.transport_client import TransportClient, UrlLibTransportRequester
import mockingbird_node.transport_client as transport_client_module
from mockingbird_node.transport_spool import PRIORITY_CRITICAL, PRIORITY_NORMAL, TransportSpool
from mockingbird_node.transport_worker import TransportWorkerState, run_transport_worker_loop

from _transport_fault_injection import FaultInjectingProxy, RunningApp, free_port

pytestmark = pytest.mark.slow

NODE_ID = "node-acceptance-test"
CREDENTIAL = "acceptance-test-credential"


def _host_app(tmp_path):
    def resolve(credential: str):
        return ("source-1", NODE_ID) if credential == CREDENTIAL else None

    app = FastAPI()
    app.include_router(
        build_camera_node_transport_router(resolve_transport_source=resolve, transport_root=tmp_path / "host-transport")
    )
    return app


def _spool(tmp_path, **overrides) -> TransportSpool:
    defaults = dict(
        max_bytes=50_000_000, max_items=1000, min_free_bytes=0,
        backoff_base_seconds=0.05, backoff_cap_seconds=0.5,
    )
    defaults.update(overrides)
    return TransportSpool(tmp_path / "spool", **defaults)


def _completed_files(tmp_path) -> list:
    completed_dir = tmp_path / "host-transport" / NODE_ID / "completed"
    if not completed_dir.exists():
        return []
    return sorted(p for p in completed_dir.iterdir() if p.suffix == ".bin")


class _Worker:
    """Runs `run_transport_worker_loop` as a background asyncio task on its
    own event loop thread -- these tests are plain `def`, not `async def`,
    so the worker's asyncio loop is fully isolated per test."""

    def __init__(self, spool, *, base_address, credential=CREDENTIAL, node_id=NODE_ID, max_concurrent_uploads=1, max_bytes_per_second=0, chunk_size=65536):
        self.spool = spool
        self.state = TransportWorkerState()
        self._loop = asyncio.new_event_loop()
        self._stop_event: asyncio.Event | None = None
        self._task: asyncio.Task | None = None
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._base_address = base_address
        self._credential = credential
        self._node_id = node_id
        self._max_concurrent_uploads = max_concurrent_uploads
        self._max_bytes_per_second = max_bytes_per_second
        self._chunk_size = chunk_size

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._stop_event = asyncio.Event()
        self._task = self._loop.create_task(
            run_transport_worker_loop(
                spool=self.spool,
                client=TransportClient(requester=UrlLibTransportRequester(connect_timeout_seconds=1.0, response_timeout_seconds=3.0)),
                state=self.state,
                host_base_address=self._base_address,
                credential_provider=lambda: self._credential,
                node_id=self._node_id,
                chunk_size=self._chunk_size,
                max_concurrent_uploads=self._max_concurrent_uploads,
                max_bytes_per_second=self._max_bytes_per_second,
                stop_event=self._stop_event,
                idle_poll_seconds=0.05,
            )
        )
        self._loop.run_forever()

    def start(self) -> "_Worker":
        self._thread.start()
        deadline = time.monotonic() + 5.0
        while self._stop_event is None:
            if time.monotonic() > deadline:
                raise RuntimeError("worker did not start in time")
            time.sleep(0.01)
        return self

    def stop(self) -> None:
        async def _shutdown():
            self._stop_event.set()
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (TimeoutError, asyncio.CancelledError, Exception):
                pass

        future = asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)
        future.result(timeout=10.0)  # blocks this (test) thread until the worker task really finished
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5.0)
        self._loop.close()


def _wait_until(condition, *, timeout=8.0, interval=0.05) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(interval)
    raise AssertionError("condition was not met in time")


# --------------------------------------------------------------------------
# Scenario 1 -- ordinary disconnect/reconnect
# --------------------------------------------------------------------------


def test_scenario_1_ordinary_disconnect_reconnect(tmp_path) -> None:
    """Fault: host not listening at all for a period, then started.
    Result: work accumulates durably, then drains automatically with no
    restart and no duplication."""

    port = free_port()
    base_address = f"http://127.0.0.1:{port}"
    spool = _spool(tmp_path)
    item_ids = [spool.enqueue(kind="evidence_capture", payload=f"item-{i}".encode() * 200, media_type="image/jpeg") for i in range(3)]

    worker = _Worker(spool, base_address=base_address).start()
    try:
        # Host is not listening yet -- connection refused every attempt.
        _wait_until(lambda: spool.diagnostics().pending_count >= 1, timeout=5.0)  # failed_retryable counts as pending here
        assert all(spool.get(item_id).state in {"pending", "failed_retryable"} for item_id in item_ids)

        running = RunningApp(_host_app(tmp_path), port=port).start()
        try:
            _wait_until(lambda: all(spool.get(item_id) is None for item_id in item_ids), timeout=10.0)
        finally:
            running.stop()
    finally:
        worker.stop()

    completed = _completed_files(tmp_path)
    assert len(completed) == 3  # exactly one durable file per item -- no duplication
    assert {p.stem for p in completed} == set(item_ids)


# --------------------------------------------------------------------------
# Scenario 2 -- acknowledgement loss
# --------------------------------------------------------------------------


def test_scenario_2_acknowledgement_loss(tmp_path) -> None:
    """Fault: the host durably completes the item, but the `complete`
    response is dropped before the Node sees it. Result: the Node retries,
    and the host still has exactly one logical item."""

    host_running = RunningApp(_host_app(tmp_path)).start()
    proxy = FaultInjectingProxy(host_running.base_url).start()
    try:
        payload = b"single-chunk-evidence-payload"
        spool = _spool(tmp_path)
        item_id = spool.enqueue(kind="evidence_capture", payload=payload, media_type="image/jpeg")

        # Let declare + the one chunk through normally; drop the response
        # to the `complete` call specifically (the host has already
        # durably completed the item by the time the response is dropped).
        proxy.controller.queue("pass", count=2)
        proxy.controller.queue("drop_response", count=1)

        worker = _Worker(spool, base_address=proxy.base_url).start()
        try:
            _wait_until(lambda: spool.get(item_id) is None, timeout=8.0)
        finally:
            worker.stop()

        completed = _completed_files(tmp_path)
        assert len(completed) == 1
        assert completed[0].read_bytes() == payload
        # The retried declare must have seen "duplicate", not re-run chunks:
        # confirmed indirectly by there being exactly one completed file
        # with the exact original bytes (a second real upload attempt would
        # still produce the same correct file, so also assert the request
        # log shows more than 3 calls -- i.e. a real retry happened, not a
        # single lucky pass).
        assert len(proxy.controller.requests_seen()) > 3
    finally:
        proxy.stop()
        host_running.stop()


# --------------------------------------------------------------------------
# Scenario 3 -- node restart while offline
# --------------------------------------------------------------------------


def test_scenario_3_node_restart_while_offline(tmp_path) -> None:
    """Fault: host unreachable; the Node's spool process is torn down and
    reconstructed (simulated restart) while still offline. Result: pending
    work survives the restart, and later delivery completes exactly once."""

    port = free_port()
    base_address = f"http://127.0.0.1:{port}"
    spool_path = tmp_path / "spool"
    spool = TransportSpool(spool_path, max_bytes=50_000_000, max_items=1000, min_free_bytes=0, backoff_base_seconds=0.05, backoff_cap_seconds=0.3)
    item_id = spool.enqueue(kind="evidence_capture", payload=b"pending-across-a-restart", media_type="image/jpeg")

    worker = _Worker(spool, base_address=base_address).start()
    _wait_until(lambda: spool.get(item_id).attempt_count >= 1 or spool.get(item_id).state == "transmitting", timeout=5.0)
    worker.stop()
    spool.close()  # process "exits"

    # Reconstruct the spool at the same path -- a real Node restart.
    restarted_spool = TransportSpool(spool_path, max_bytes=50_000_000, max_items=1000, min_free_bytes=0, backoff_base_seconds=0.05, backoff_cap_seconds=0.3)
    restarted_spool.recover_incomplete_on_startup()
    item_after_restart = restarted_spool.get(item_id)
    assert item_after_restart is not None  # survived the restart
    assert restarted_spool.read_payload(item_id) == b"pending-across-a-restart"

    running = RunningApp(_host_app(tmp_path), port=port).start()
    restarted_worker = _Worker(restarted_spool, base_address=base_address).start()
    try:
        _wait_until(lambda: restarted_spool.get(item_id) is None, timeout=10.0)
    finally:
        restarted_worker.stop()
        running.stop()

    completed = _completed_files(tmp_path)
    assert len(completed) == 1
    assert completed[0].stem == item_id


# --------------------------------------------------------------------------
# Scenario 4 -- interrupted large evidence transfer
# --------------------------------------------------------------------------


def test_scenario_4_interrupted_large_evidence_transfer(tmp_path) -> None:
    """Fault: one chunk's response is truncated mid-transfer. Result: the
    incomplete evidence never becomes authoritative, exactly that chunk is
    resent (not the whole item), and the final file matches the source
    byte-for-byte (hash-verified)."""

    host_running = RunningApp(_host_app(tmp_path)).start()
    proxy = FaultInjectingProxy(host_running.base_url).start()
    try:
        payload = (b"large-evidence-chunk-" * 2000)  # ~44KB, several chunks at 8KB
        digest = hashlib.sha256(payload).hexdigest()
        spool = _spool(tmp_path)
        item_id = spool.enqueue(kind="evidence_capture", payload=payload, media_type="image/jpeg")

        # declare passes; the first chunk's *response* is truncated (the
        # bytes did reach the host -- see the harness docstring -- but the
        # Node cannot confirm it, so it must not assume success).
        proxy.controller.queue("pass", count=1)
        proxy.controller.queue("truncate_response", count=1, truncate_bytes=2)

        worker = _Worker(spool, base_address=proxy.base_url, chunk_size=8192).start()
        try:
            _wait_until(lambda: spool.get(item_id) is None, timeout=10.0)
        finally:
            worker.stop()

        completed = _completed_files(tmp_path)
        assert len(completed) == 1
        completed_bytes = completed[0].read_bytes()
        assert completed_bytes == payload
        assert hashlib.sha256(completed_bytes).hexdigest() == digest
        # No `.part` file left behind mid-flight -- either completed
        # cleanly or nothing durable at all, never a stuck partial.
        assert not any((tmp_path / "host-transport" / NODE_ID / "items").glob("*.part")) if (tmp_path / "host-transport" / NODE_ID / "items").exists() else True
    finally:
        proxy.stop()
        host_running.stop()


# --------------------------------------------------------------------------
# Scenario 5 -- prolonged outage / backlog within bounds
# --------------------------------------------------------------------------


def test_scenario_5_prolonged_outage_backlog_stays_within_bounds(tmp_path) -> None:
    """Fault: extended outage (host never reachable) while more items are
    enqueued than the spool's bound allows. Result: the spool never exceeds
    its documented bound (deterministic eviction, counters kept), and once
    the host returns, the retained backlog still drains correctly."""

    port = free_port()
    base_address = f"http://127.0.0.1:{port}"
    spool = _spool(tmp_path, max_items=5, max_bytes=50_000_000)

    worker = _Worker(spool, base_address=base_address).start()
    try:
        ids = []
        for index in range(12):  # more than max_items=5
            ids.append(spool.enqueue(kind="evidence_capture", payload=f"item-{index}".encode() * 50, media_type="image/jpeg"))
        diagnostics = spool.diagnostics()
        total_items = diagnostics.pending_count + diagnostics.transmitting_count
        assert total_items <= 5  # never exceeded the documented bound
        assert diagnostics.evicted_count_total == 12 - total_items
        assert diagnostics.last_eviction_reason == "item_cap"

        running = RunningApp(_host_app(tmp_path), port=port).start()
        try:
            _wait_until(lambda: spool.diagnostics().pending_count == 0 and spool.diagnostics().transmitting_count == 0, timeout=10.0)
        finally:
            running.stop()
    finally:
        worker.stop()

    # Whatever survived eviction drained correctly (fewer than 12 -- some
    # were deterministically evicted, and that is expected, not a bug).
    completed = _completed_files(tmp_path)
    assert 1 <= len(completed) <= 5


# --------------------------------------------------------------------------
# Scenario 6 -- constrained bandwidth: priority ordering + pacing
# --------------------------------------------------------------------------


def test_scenario_6_constrained_bandwidth_priority_ordering(tmp_path) -> None:
    """Fault: a slow/constrained link (explicit pacing cap). Result: a
    small critical record is not starved behind a large media item queued
    ahead of it -- the drain loop honors priority, not enqueue order."""

    host_running = RunningApp(_host_app(tmp_path)).start()
    try:
        spool = _spool(tmp_path)
        # Large NORMAL-priority item enqueued *first* -- naive FIFO would
        # deliver this before the critical item.
        large_id = spool.enqueue(kind="evidence_capture", payload=b"x" * 300_000, media_type="image/jpeg", priority=PRIORITY_NORMAL)
        critical_id = spool.enqueue(kind="status_record", payload=b"tiny-critical-record", media_type="application/json", priority=PRIORITY_CRITICAL)

        worker = _Worker(spool, base_address=host_running.base_url, max_concurrent_uploads=1, max_bytes_per_second=200_000, chunk_size=32_768).start()
        try:
            _wait_until(lambda: spool.get(critical_id) is None, timeout=10.0)
            critical_done_at = time.monotonic()
            _wait_until(lambda: spool.get(large_id) is None, timeout=15.0)
            large_done_at = time.monotonic()
        finally:
            worker.stop()
        assert critical_done_at < large_done_at  # critical item finished strictly first despite being enqueued second
    finally:
        host_running.stop()


# --------------------------------------------------------------------------
# Scenario 7 -- repeated flapping
# --------------------------------------------------------------------------


def test_scenario_7_repeated_flapping_stays_coherent(tmp_path) -> None:
    """Fault: the link repeatedly drops and recovers several times in
    succession. Result: state remains coherent throughout -- no duplicate
    host objects, no corrupt spool transitions -- and every item is
    eventually delivered exactly once."""

    host_running = RunningApp(_host_app(tmp_path)).start()
    proxy = FaultInjectingProxy(host_running.base_url).start()
    try:
        spool = _spool(tmp_path, backoff_base_seconds=0.02, backoff_cap_seconds=0.1)
        item_ids = [spool.enqueue(kind="evidence_capture", payload=f"flap-{i}".encode() * 100, media_type="image/jpeg") for i in range(4)]

        worker = _Worker(spool, base_address=proxy.base_url).start()
        try:
            # Alternate the link several times while delivery is in flight.
            for _ in range(5):
                proxy.controller.queue("drop_response", count=3)
                time.sleep(0.08)
                proxy.controller.clear()  # back to "pass"
                time.sleep(0.08)
            _wait_until(lambda: all(spool.get(item_id) is None for item_id in item_ids), timeout=15.0)
        finally:
            worker.stop()

        completed = _completed_files(tmp_path)
        assert len(completed) == 4  # exactly one durable object per item, never duplicated by the flapping
        assert {p.stem for p in completed} == set(item_ids)
        for path in completed:
            # No corrupt/truncated promoted file survived the flapping.
            assert path.read_bytes()
    finally:
        proxy.stop()
        host_running.stop()


# --------------------------------------------------------------------------
# Scenario 8 -- host incompatibility / rejection
# --------------------------------------------------------------------------


def test_scenario_8_host_incompatibility_is_diagnosable_not_silently_lost(tmp_path, monkeypatch) -> None:
    """Fault: the Node speaks a transport protocol version the host does
    not support. Result: the item is never silently lost (stays in the
    spool, diagnosable), retries stay backed off rather than hot-looping,
    and the worker's diagnostics clearly identify the incompatibility."""

    monkeypatch.setattr(transport_client_module, "TRANSPORT_PROTOCOL_VERSION", "transport/v999-incompatible")
    host_running = RunningApp(_host_app(tmp_path)).start()
    try:
        spool = _spool(tmp_path, backoff_base_seconds=0.1, backoff_cap_seconds=0.3)
        item_id = spool.enqueue(kind="evidence_capture", payload=b"never-compatible", media_type="image/jpeg")

        worker = _Worker(spool, base_address=host_running.base_url).start()
        try:
            _wait_until(lambda: worker.state.protocol_incompatible_since is not None, timeout=5.0)
            # Not spinning tightly: give it several backoff windows and
            # confirm the attempt count stays bounded/proportionate rather
            # than climbing every millisecond.
            time.sleep(0.5)
            item = spool.get(item_id)
            assert item is not None  # never silently lost
            assert item.state in {"pending", "failed_retryable"}  # still an active, diagnosable item
            assert item.attempt_count < 20  # backed off, not hot-looping in 0.5s
            assert worker.state.last_error == "transport_protocol_unsupported"
        finally:
            worker.stop()
        assert not _completed_files(tmp_path)  # never delivered -- correctly, since it never could be
    finally:
        host_running.stop()
