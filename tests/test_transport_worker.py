"""Tier 1: the Node's background drain loop.

Against a scripted fake `TransportClient`-shaped object (duck-typed: the
worker only ever calls `.deliver(...)`) and a real `TransportSpool` on
`tmp_path` -- no real sockets. See
tests/test_camera_node_transport_acceptance.py for the real end-to-end
proof.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from mockingbird_node.transport_client import TransportClientError
from mockingbird_node.transport_spool import TransportSpool
from mockingbird_node.transport_worker import TransportWorkerState, run_transport_worker_loop


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _spool(tmp_path) -> TransportSpool:
    return TransportSpool(
        tmp_path / "spool", max_bytes=10_000_000, max_items=100, min_free_bytes=0,
        backoff_base_seconds=0.02, backoff_cap_seconds=0.5,
    )


class _ScriptedClient:
    """`deliver(...)` outcomes keyed by item_id, consumed once per call
    unless `repeat=True`. Records every call for assertions."""

    def __init__(self) -> None:
        self.outcomes: dict[str, list[Exception | None]] = {}
        self.calls: list[str] = []

    def when(self, item_id: str, *outcomes: Exception | None) -> None:
        self.outcomes[item_id] = list(outcomes)

    def deliver(self, *, base_address, credential, node_id, item, payload, chunk_size, backlog_summary, max_bytes_per_second=0, should_abort=lambda: False):
        self.calls.append(item.item_id)
        queue = self.outcomes.get(item.item_id, [None])
        outcome = queue.pop(0) if len(queue) > 1 else queue[0]
        if outcome is not None:
            raise outcome


async def _run_until(condition, *, timeout=3.0, interval=0.02):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if condition():
            return
        await asyncio.sleep(interval)
    raise AssertionError("condition was not met in time")


async def _run_worker(spool, client, *, credential="cred", node_id="node-1", max_concurrent_uploads=1):
    state = TransportWorkerState()
    stop_event = asyncio.Event()
    task = asyncio.create_task(
        run_transport_worker_loop(
            spool=spool,
            client=client,
            state=state,
            host_base_address="http://host",
            credential_provider=lambda: credential,
            node_id=node_id,
            chunk_size=1024,
            max_concurrent_uploads=max_concurrent_uploads,
            max_bytes_per_second=0,
            stop_event=stop_event,
            idle_poll_seconds=0.02,
        )
    )
    return state, stop_event, task


async def _stop(stop_event, task) -> None:
    stop_event.set()
    await asyncio.wait_for(task, timeout=3.0)


@pytest.mark.anyio
async def test_successful_delivery_acknowledges_and_prunes_the_item(tmp_path) -> None:
    spool = _spool(tmp_path)
    item_id = spool.enqueue(kind="k", payload=b"x", media_type="t")
    client = _ScriptedClient()
    state, stop_event, task = await _run_worker(spool, client)
    try:
        await _run_until(lambda: spool.get(item_id) is None)
        assert client.calls == [item_id]
        assert state.delivered_count_total == 1
        assert state.connected is True
    finally:
        await _stop(stop_event, task)


@pytest.mark.anyio
async def test_retryable_failure_returns_item_to_failed_retryable_and_eventually_succeeds(tmp_path) -> None:
    spool = _spool(tmp_path)
    item_id = spool.enqueue(kind="k", payload=b"x", media_type="t")
    client = _ScriptedClient()
    client.when(item_id, TransportClientError("transport_host_unreachable"), None)
    state, stop_event, task = await _run_worker(spool, client)
    try:
        await _run_until(lambda: state.consecutive_failures >= 1)
        assert state.connected is False
        assert state.last_error == "transport_host_unreachable"
        await _run_until(lambda: spool.get(item_id) is None, timeout=5.0)  # backoff elapses, then succeeds
        assert state.connected is True
        assert client.calls.count(item_id) == 2
    finally:
        await _stop(stop_event, task)


@pytest.mark.anyio
async def test_terminal_failure_marks_item_terminal_and_never_retries(tmp_path) -> None:
    spool = _spool(tmp_path)
    item_id = spool.enqueue(kind="k", payload=b"x", media_type="t")
    client = _ScriptedClient()
    client.when(item_id, TransportClientError("transport_item_conflict"))
    state, stop_event, task = await _run_worker(spool, client)
    try:
        await _run_until(lambda: spool.get(item_id) is not None and spool.get(item_id).state == "failed_terminal")
        await asyncio.sleep(0.15)  # give the loop several extra ticks
        assert client.calls.count(item_id) == 1  # never attempted again
    finally:
        await _stop(stop_event, task)


@pytest.mark.anyio
async def test_sticky_diagnostic_set_on_protocol_incompatibility_and_cleared_on_next_success(tmp_path) -> None:
    spool = _spool(tmp_path)
    first_id = spool.enqueue(kind="k", payload=b"x", media_type="t")
    client = _ScriptedClient()
    client.when(first_id, TransportClientError("transport_protocol_unsupported"), None)
    state, stop_event, task = await _run_worker(spool, client)
    try:
        await _run_until(lambda: state.protocol_incompatible_since is not None)
        await _run_until(lambda: spool.get(first_id) is None, timeout=5.0)
        assert state.protocol_incompatible_since is None  # cleared by the following success
    finally:
        await _stop(stop_event, task)


@pytest.mark.anyio
async def test_no_credential_means_no_delivery_attempts(tmp_path) -> None:
    spool = _spool(tmp_path)
    spool.enqueue(kind="k", payload=b"x", media_type="t")
    client = _ScriptedClient()
    state, stop_event, task = await _run_worker(spool, client, credential=None)
    try:
        await asyncio.sleep(0.2)
        assert client.calls == []
    finally:
        await _stop(stop_event, task)


@pytest.mark.anyio
async def test_stop_event_ends_the_loop_promptly(tmp_path) -> None:
    spool = _spool(tmp_path)
    client = _ScriptedClient()
    state, stop_event, task = await _run_worker(spool, client)
    stop_event.set()
    await asyncio.wait_for(task, timeout=2.0)
    assert task.done() and not task.cancelled()


@pytest.mark.anyio
async def test_max_concurrent_uploads_bounds_batch_size(tmp_path) -> None:
    spool = _spool(tmp_path)
    for _ in range(5):
        spool.enqueue(kind="k", payload=b"x", media_type="t")

    class _BlockingClient(_ScriptedClient):
        def deliver(self, *, item, **kwargs):
            self.calls.append(item.item_id)
            # Blocks synchronously (this runs in a worker thread via
            # asyncio.to_thread), so the claimed batch size is observable
            # before any delivery completes.
            time.sleep(0.15)

    client = _BlockingClient()
    state, stop_event, task = await _run_worker(spool, client, max_concurrent_uploads=2)
    try:
        await _run_until(lambda: len(spool.list_items(("transmitting",))) > 0)
        await asyncio.sleep(0.05)
        transmitting = spool.list_items(("transmitting",))
        assert len(transmitting) <= 2
    finally:
        await _stop(stop_event, task)
