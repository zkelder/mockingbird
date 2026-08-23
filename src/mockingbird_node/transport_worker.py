"""Background drain loop: claims due spool items and delivers them to the host.

Recovery begins automatically -- there is no "resume" button an operator
must press. The loop itself *is* the connectivity detector: it does not
ping the host separately, it just keeps trying due work and derives
connected/disconnected from whether the most recent attempt succeeded (see
`TransportWorkerState`).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import time
from typing import Callable

from .transport_client import TransportClient, TransportClientError, classify_error
from .transport_log import log_error_event, log_event
from .transport_spool import SpoolItem, TransportSpool


@dataclass
class TransportWorkerState:
    """In-memory, per-process diagnostics -- always rebuilt from the durable
    spool + a fresh probe on restart, never itself relied on as the source
    of truth for whether work is safe (see `transport_spool.py`)."""

    connected: bool = False
    active_uploads: int = 0
    last_contact_attempt_at: float | None = None
    last_contact_success_at: float | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    delivered_count_total: int = 0
    protocol_incompatible_since: float | None = None
    authentication_rejected_since: float | None = None

    def record_attempt_start(self, *, now: float) -> None:
        self.active_uploads += 1
        self.last_contact_attempt_at = now

    def record_success(self, *, now: float) -> None:
        self.active_uploads -= 1
        self.connected = True
        self.last_contact_success_at = now
        self.last_error = None
        self.consecutive_failures = 0
        self.delivered_count_total += 1
        self.protocol_incompatible_since = None
        self.authentication_rejected_since = None

    def record_failure(self, code: str, *, now: float) -> None:
        self.active_uploads -= 1
        self.connected = False
        self.last_error = code
        self.consecutive_failures += 1
        if code == "transport_protocol_unsupported" and self.protocol_incompatible_since is None:
            self.protocol_incompatible_since = now
        if code == "authentication_rejected" and self.authentication_rejected_since is None:
            self.authentication_rejected_since = now


async def _sleep_or_stop(stop_event: asyncio.Event, seconds: float) -> None:
    try:
        await asyncio.wait_for(stop_event.wait(), timeout=seconds)
    except TimeoutError:
        pass


def _backlog_summary(spool: TransportSpool, state: TransportWorkerState) -> dict[str, object]:
    diagnostics = spool.diagnostics()
    return {
        "pending_count": diagnostics.pending_count,
        "pending_bytes": diagnostics.pending_bytes,
        "failed_terminal_count": diagnostics.failed_terminal_count,
        "last_error": state.last_error,
    }


async def _deliver_one(
    item: SpoolItem,
    *,
    spool: TransportSpool,
    client: TransportClient,
    state: TransportWorkerState,
    host_base_address: str,
    credential: str,
    node_id: str,
    chunk_size: int,
    max_bytes_per_second: int,
    stop_event: asyncio.Event,
    clock: Callable[[], float],
) -> None:
    payload = await asyncio.to_thread(spool.read_payload, item.item_id)
    backlog_summary = _backlog_summary(spool, state)
    state.record_attempt_start(now=clock())
    try:
        await asyncio.to_thread(
            client.deliver,
            base_address=host_base_address,
            credential=credential,
            node_id=node_id,
            item=item,
            payload=payload,
            chunk_size=chunk_size,
            backlog_summary=backlog_summary,
            max_bytes_per_second=max_bytes_per_second,
            should_abort=stop_event.is_set,
        )
    except TransportClientError as error:
        code = str(error)
        state.record_failure(code, now=clock())
        if classify_error(error) == "terminal":
            await asyncio.to_thread(spool.mark_failed_terminal, item.item_id, error=code)
            log_error_event(
                "camera_node_transport", "item_delivery_terminal", code=code, item_id=item.item_id
            )
        else:
            next_attempt_at = await asyncio.to_thread(
                spool.mark_failed_retryable, item.item_id, error=code
            )
            log_error_event(
                "camera_node_transport",
                "item_delivery_failed",
                code=code,
                item_id=item.item_id,
                next_attempt_in_seconds=round(next_attempt_at - clock(), 1),
            )
        return
    state.record_success(now=clock())
    await asyncio.to_thread(spool.mark_acknowledged, item.item_id)
    await asyncio.to_thread(spool.prune_acknowledged, item.item_id)
    log_event("camera_node_transport", "item_delivered", item_id=item.item_id, kind=item.kind)


async def run_transport_worker_loop(
    *,
    spool: TransportSpool,
    client: TransportClient,
    state: TransportWorkerState,
    host_base_address: str,
    credential_provider: Callable[[], str | None],
    node_id: str,
    chunk_size: int,
    max_concurrent_uploads: int,
    max_bytes_per_second: int,
    stop_event: asyncio.Event,
    idle_poll_seconds: float = 2.0,
    clock: Callable[[], float] = time.time,
) -> None:
    recovered = await asyncio.to_thread(spool.recover_incomplete_on_startup)
    orphaned = await asyncio.to_thread(spool.sweep_orphaned_blobs)
    if recovered or orphaned:
        log_event(
            "camera_node_transport",
            "spool_recovered_on_startup",
            recovered_transmitting=recovered,
            swept_orphaned_blobs=orphaned,
        )
    while not stop_event.is_set():
        credential = credential_provider()
        if credential is None:
            await _sleep_or_stop(stop_event, idle_poll_seconds)
            continue
        claimed = await asyncio.to_thread(spool.claim_next_batch, max_concurrent_uploads)
        if not claimed:
            await _sleep_or_stop(stop_event, idle_poll_seconds)
            continue
        await asyncio.gather(
            *(
                _deliver_one(
                    item,
                    spool=spool,
                    client=client,
                    state=state,
                    host_base_address=host_base_address,
                    credential=credential,
                    node_id=node_id,
                    chunk_size=chunk_size,
                    max_bytes_per_second=max_bytes_per_second,
                    stop_event=stop_event,
                    clock=clock,
                )
                for item in claimed
            )
        )
