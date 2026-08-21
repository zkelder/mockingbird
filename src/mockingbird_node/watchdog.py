"""Minimal, dependency-free systemd `sd_notify` client and a bounded,
meaningful watchdog heartbeat.

No `sdnotify`/`systemd-python` dependency: the protocol is a handful of
bytes written to a `SOCK_DGRAM` Unix socket -- well within what the
intentionally slim Node runtime (fastapi/pydantic/uvicorn only, see
"Artifact/install contract" in docs/camera-node-installer-design.md) should
carry. Every function here is a safe no-op off systemd (a manual
`python -m mockingbird_node`, a non-Linux host, or any environment lacking
`NOTIFY_SOCKET`) -- never raises, never blocks the caller.

The watchdog ping only fires after a bounded, real liveness probe
completes -- never on a bare timer thread. A probe that hangs simply
forfeits that cycle's ping; if it keeps hanging, systemd's own
`WatchdogSec=` eventually elapses and restarts the unit. This is the
"meaningful progress" requirement: the health signal must correspond to
real Camera Node responsiveness, never merely "a thread stayed alive while
the real work was dead." See "Watchdog" in
docs/camera-node-installer-design.md.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import os
import socket
import time
from typing import Any, Awaitable, Callable


_MAX_DATAGRAM_BYTES = 4096
#: systemd pings at least twice per `WatchdogSec=` by convention; halving
#: the reported timeout is the documented, standard cadence (see
#: `sd_watchdog_enabled(3)`), leaving headroom for one missed/slow probe
#: before the real timeout could ever elapse.
_PING_INTERVAL_FRACTION = 0.5
_DEFAULT_PING_INTERVAL_SECONDS = 15.0
_MAXIMUM_PROBE_TIMEOUT_SECONDS = 8.0


def notify_socket_path() -> str | None:
    return os.environ.get("NOTIFY_SOCKET") or None


def watchdog_timeout_seconds() -> float | None:
    """`WATCHDOG_USEC` -- systemd's own contract for how long it waits
    between `WATCHDOG=1` pings before treating this unit as hung. Present
    only when the unit's `WatchdogSec=` is actually configured; absent for
    an ordinary manual run or a unit with no watchdog configured at all."""

    raw = os.environ.get("WATCHDOG_USEC")
    if not raw:
        return None
    try:
        microseconds = int(raw)
    except ValueError:
        return None
    return microseconds / 1_000_000 if microseconds > 0 else None


def watchdog_ping_interval_seconds() -> float | None:
    timeout = watchdog_timeout_seconds()
    return timeout * _PING_INTERVAL_FRACTION if timeout else None


def sd_notify(message: bytes, *, socket_path: str | None = None) -> bool:
    """Send one raw sd_notify datagram. Returns whether it was actually
    sent -- never raises. A `socket_path` starting with `@` is systemd's
    documented abstract-namespace convention (the leading `@` stands in
    for a NUL byte, which cannot appear in a normal Python string
    argument)."""

    path = socket_path if socket_path is not None else notify_socket_path()
    if not path:
        return False
    address = ("\0" + path[1:]) if path.startswith("@") else path
    sock: socket.socket | None = None
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.sendto(message[:_MAX_DATAGRAM_BYTES], address)
        return True
    except OSError:
        return False
    finally:
        if sock is not None:
            sock.close()


@dataclass
class WatchdogProgress:
    """The most recent bounded liveness-probe outcome -- exposed through
    `/node/v1/health` so an operator (or Doctor) can see the watchdog's own
    evidence, not just take "the process is still running" on faith. This
    is `service alive` evidence (the health loop / event loop is
    responsive), deliberately distinct from `camera producing frames` --
    see the module docstring and "Progress/heartbeat" in
    docs/camera-node-installer-design.md."""

    enabled: bool
    ping_interval_seconds: float | None = None
    last_probe_at_monotonic: float | None = None
    last_probe_ok: bool | None = None
    consecutive_probe_failures: int = 0

    def as_payload(self, *, now_monotonic: float) -> dict[str, Any]:
        seconds_since_last_probe = (
            round(now_monotonic - self.last_probe_at_monotonic, 1)
            if self.last_probe_at_monotonic is not None
            else None
        )
        return {
            "enabled": self.enabled,
            "ping_interval_seconds": self.ping_interval_seconds,
            "seconds_since_last_probe": seconds_since_last_probe,
            "last_probe_ok": self.last_probe_ok,
            "consecutive_probe_failures": self.consecutive_probe_failures,
        }


async def run_watchdog_loop(
    *,
    progress: WatchdogProgress,
    probe: Callable[[], Awaitable[Any]],
    probe_timeout_seconds: float | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    notify: Callable[[bytes], bool] = sd_notify,
    monotonic: Callable[[], float] = time.monotonic,
) -> None:
    """Ping `WATCHDOG=1` only after `probe()` genuinely completes within
    its own bound -- never on a bare timer. Intended to run as one
    long-lived `asyncio.Task`, cancelled cleanly on shutdown; cancellation
    propagates out of this loop immediately (a bare `except Exception`
    below never catches `asyncio.CancelledError`, which is a
    `BaseException`)."""

    interval = progress.ping_interval_seconds or _DEFAULT_PING_INTERVAL_SECONDS
    timeout = probe_timeout_seconds or min(_MAXIMUM_PROBE_TIMEOUT_SECONDS, interval * 0.5)
    while True:
        await sleep(interval)
        try:
            await asyncio.wait_for(probe(), timeout=timeout)
            probe_ok = True
        except Exception:  # noqa: BLE001 - a stuck/failed probe forfeits this ping, never crashes the loop
            probe_ok = False
        progress.last_probe_at_monotonic = monotonic()
        progress.last_probe_ok = probe_ok
        if probe_ok:
            progress.consecutive_probe_failures = 0
            notify(b"WATCHDOG=1\n")
        else:
            progress.consecutive_probe_failures += 1
