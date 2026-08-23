"""Deterministic transport fault-injection harness (Phase J).

Runs the real host transport router (or any WSGI-less ASGI app) over a
real TCP socket via uvicorn in a background thread, fronted by a real,
controllable HTTP-level proxy in a second background thread. Tests drive
the real `mockingbird_node.transport_client.TransportClient` (stdlib
`http.client`, exactly the production code path) against the proxy's
address and queue faults deterministically -- no arbitrary sleeps, no
mocking of the transport protocol itself.

This deliberately operates at the HTTP layer, not raw TCP: "ack loss" means
the upstream genuinely receives and durably processes the request (its
state really changes -- see Scenario 2), but the response is withheld from
the client, which is what a raw-TCP proxy cannot express as precisely.
"""

from __future__ import annotations

from dataclasses import dataclass
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import threading
import time

import uvicorn


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class RunningApp:
    def __init__(self, app, *, port: int | None = None) -> None:
        self.port = port if port is not None else free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        config = uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="critical")
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def start(self) -> "RunningApp":
        self._thread.start()
        deadline = time.monotonic() + 10.0
        while not self._server.started:
            if time.monotonic() > deadline:
                raise RuntimeError("app did not start in time")
            time.sleep(0.02)
        return self

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=10.0)


@dataclass
class _PendingFault:
    mode: str
    remaining: int
    latency_seconds: float = 0.0
    truncate_bytes: int | None = None
    bytes_per_second: int | None = None


class FaultController:
    """A queue of one-shot faults consumed in order, one per proxied request.

    An empty queue means "pass through unmodified" -- the default, healthy
    state every acceptance test starts and ends in.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._queue: list[_PendingFault] = []
        self._request_log: list[tuple[str, str]] = []

    def queue(self, mode: str, *, count: int = 1, **kwargs) -> None:
        with self._lock:
            self._queue.append(_PendingFault(mode=mode, remaining=count, **kwargs))

    def clear(self) -> None:
        with self._lock:
            self._queue.clear()

    def next_directive(self) -> _PendingFault:
        with self._lock:
            if not self._queue:
                return _PendingFault(mode="pass", remaining=1)
            head = self._queue[0]
            head.remaining -= 1
            if head.remaining <= 0:
                self._queue.pop(0)
            return head

    def log(self, method: str, path: str) -> None:
        with self._lock:
            self._request_log.append((method, path))

    def requests_seen(self) -> list[tuple[str, str]]:
        with self._lock:
            return list(self._request_log)


def _make_handler(upstream_base_url: str, controller: FaultController):
    upstream_host, upstream_port = upstream_base_url.replace("http://", "").split(":")
    upstream_port = int(upstream_port)

    class _Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib signature
            pass

        def _handle(self) -> None:
            controller.log(self.command, self.path)
            directive = controller.next_directive()
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length) if length else b""
            headers = {
                key: value
                for key, value in self.headers.items()
                if key.lower() not in {"host", "connection", "content-length"}
            }

            if directive.mode == "hang":
                # Never respond. The client's own bounded response timeout
                # must fire -- proves that real bound, not this harness.
                time.sleep(30.0)
                self.close_connection = True
                return

            if directive.mode == "latency":
                time.sleep(directive.latency_seconds)

            connection = HTTPConnection(upstream_host, upstream_port, timeout=15.0)
            try:
                connection.request(self.command, self.path, body=body, headers=headers)
                response = connection.getresponse()
                response_body = response.read()
                response_headers = dict(response.headers.items())
                status = response.status
            finally:
                connection.close()

            if directive.mode == "drop_response":
                # The upstream call above already completed for real --
                # its state is durably changed. Just never tell the client.
                self.close_connection = True
                return

            if directive.mode == "truncate_response":
                response_body = response_body[: directive.truncate_bytes or 0]
                self.close_connection = True
                self.send_response(status)
                for key, value in response_headers.items():
                    if key.lower() not in {"content-length", "connection"}:
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(response_body)))
                self.end_headers()
                self.wfile.write(response_body)
                return

            self.send_response(status)
            for key, value in response_headers.items():
                if key.lower() not in {"content-length", "connection"}:
                    self.send_header(key, value)
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()

            if directive.mode == "bandwidth_cap" and directive.bytes_per_second:
                chunk_size = max(1, directive.bytes_per_second // 10)
                for offset in range(0, len(response_body), chunk_size):
                    self.wfile.write(response_body[offset : offset + chunk_size])
                    self.wfile.flush()
                    time.sleep(chunk_size / directive.bytes_per_second)
            else:
                self.wfile.write(response_body)

        def do_GET(self) -> None:
            self._handle()

        def do_POST(self) -> None:
            self._handle()

    return _Handler


class FaultInjectingProxy:
    """A real HTTP proxy on a real socket in front of `upstream_base_url`."""

    def __init__(self, upstream_base_url: str, *, port: int | None = None) -> None:
        self.controller = FaultController()
        self.port = port if port is not None else free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._server = ThreadingHTTPServer(
            ("127.0.0.1", self.port), _make_handler(upstream_base_url, self.controller)
        )
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> "FaultInjectingProxy":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=10.0)
