"""Native-Windows socket/process acceptance for the runtime shutdown and
listener fixes (Native-Windows Runtime Shutdown & Listener Resilience
Correction v1, findings F-1 and F-2).

Developer acceptance tooling, never product behavior. Runs on native Windows
with the standard library only, so the packaged runtime's own `python.exe`
can run it. It drives one disposable MockingBird instance (an explicit
`--home` and a non-8000 `--port`) and reports JSON facts:

* ``burst``: the exact F-2 reproducer from the Internal Release Candidate
  acceptance -- bursts of back-to-back ``Connection: close`` requests, each
  aborted with RST (``SO_LINGER 0``), with a health probe after each burst.
* ``resets``: keep-alive requests then an abortive close, the organic F-1
  trigger shape (a peer reset of an established server connection).
* ``shutdown``: sign in, ``POST /api/product/shutdown``, then time the
  drain, lifespan teardown and process exit by polling the instance log,
  and read the crash marker.
* ``ctrl-c``: deliver a real console Ctrl+C to a console-launched instance.
* ``processes``: every process whose command line names this port, plus
  their children, so a surviving process or second instance is visible.

Nothing here writes outside ``--home``; the port-8000 field instance and the
user's own data directory are never touched.
"""

from __future__ import annotations

import argparse
import ctypes
import http.cookiejar
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request


_SCRUBBED_ENV_VARS = (
    # Persistent developer variables on the reference host that would
    # silently redirect a packaged instance away from its own bundle.
    "MOCKINGBIRD_BIOCLIP_MODEL_PATH",
    "MOCKINGBIRD_BIOCLIP_LABELS_PATH",
    "MOCKINGBIRD_BIOCLIP_EMBEDDING_CACHE_PATH",
    "MOCKINGBIRD_BIOCLIP_DEVICE",
    "MOCKINGBIRD_MEGADETECTOR_MODEL_PATH",
    "MOCKINGBIRD_ACCEPTANCE_RECORDING_DIR",
)
_CTRL_C_EVENT = 0
_CREATE_NEW_CONSOLE = 0x00000010


def _emit(payload: dict) -> None:
    print(json.dumps(payload, sort_keys=True))


def _health_ok(port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as client:
            client.sendall(b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
            return client.recv(20).startswith(b"HTTP/1.1 200")
    except OSError:
        return False


def _abortive_close(client: socket.socket) -> None:
    client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("hh", 1, 0))
    client.close()


def _clean_env(home: Path) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in _SCRUBBED_ENV_VARS}
    env["MOCKINGBIRD_HOME"] = str(home)
    return env


def _log_path(home: Path) -> Path:
    return home / "logs" / "mockingbird.log"


def _marker(home: Path) -> str | None:
    try:
        return json.loads((home / "runtime_state.json").read_text(encoding="utf-8")).get("state")
    except (OSError, ValueError):
        return None


def _processes_for_port(port: int) -> list[dict]:
    """Processes whose command line carries ``--port <port>`` and their
    direct children, via CIM (no third-party dependency)."""

    script = (
        "$all = Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine;"
        "$all | ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        check=False,
    )
    rows = json.loads(completed.stdout or "[]")
    if isinstance(rows, dict):
        rows = [rows]
    marker = f"--port {port}"
    quoted_marker = f'"--port" "{port}"'
    owners = [
        row
        for row in rows
        if row.get("CommandLine")
        and (marker in row["CommandLine"] or quoted_marker in row["CommandLine"])
        and row.get("ProcessId") != os.getpid()
        and str(row.get("Name", "")).lower().startswith("python")
    ]
    owner_ids = {row["ProcessId"] for row in owners}
    children = [row for row in rows if row.get("ParentProcessId") in owner_ids]
    return [
        {"pid": row["ProcessId"], "name": row["Name"], "role": role}
        for role, group in (("instance", owners), ("child", children))
        for row in group
    ]


def _wait_ready(port: int, timeout_seconds: float) -> float | None:
    started = time.monotonic()
    while time.monotonic() - started < timeout_seconds:
        if _health_ok(port, timeout=1.0):
            return round(time.monotonic() - started, 2)
        time.sleep(0.25)
    return None


def cmd_launch(args: argparse.Namespace) -> int:
    """Start the packaged product exactly as a user does (the shipped
    ``Start MockingBird.vbs`` through ``wscript``), with a scrubbed
    environment and an explicit disposable home."""

    home = Path(args.home)
    home.mkdir(parents=True, exist_ok=True)
    vbs = Path(args.release) / "Start MockingBird.vbs"
    subprocess.Popen(
        ["wscript.exe", str(vbs), "--port", str(args.port), "--no-browser"],
        env=_clean_env(home),
    )
    ready_after = _wait_ready(args.port, args.timeout)
    _emit(
        {
            "command": "launch",
            "port": args.port,
            "home": str(home),
            "ready_after_seconds": ready_after,
            "processes": _processes_for_port(args.port),
        }
    )
    return 0 if ready_after is not None else 1


def cmd_burst(args: argparse.Namespace) -> int:
    total = 0
    refused = 0
    deaths: list[int] = []
    for burst in range(1, args.bursts + 1):
        for _ in range(args.size):
            try:
                client = socket.create_connection(("127.0.0.1", args.port), timeout=5)
                client.sendall(b"GET / HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
                _abortive_close(client)
            except OSError:
                # A refused/reset connect mid-burst is itself the symptom of
                # a closed listener; the health probe below decides.
                refused += 1
            total += 1
        time.sleep(0.5)
        if not _health_ok(args.port):
            deaths.append(burst)
            break
    _emit(
        {
            "command": "burst",
            "port": args.port,
            "abortive_connections": total,
            "connections_refused_or_reset": refused,
            "listener_dead_after_burst": deaths[0] if deaths else None,
            "health_reachable_at_end": _health_ok(args.port),
        }
    )
    return 1 if deaths else 0


def cmd_resets(args: argparse.Namespace) -> int:
    answered = 0
    for _ in range(args.count):
        client = socket.create_connection(("127.0.0.1", args.port), timeout=5)
        client.sendall(b"GET /api/product/health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: keep-alive\r\n\r\n")
        if client.recv(64).startswith(b"HTTP/1.1"):
            answered += 1
        _abortive_close(client)
    time.sleep(0.5)
    _emit(
        {
            "command": "resets",
            "port": args.port,
            "keep_alive_then_reset": args.count,
            "answered": answered,
            "health_reachable_at_end": _health_ok(args.port),
        }
    )
    return 0


def _signed_in_opener(port: int, user: str, password: str):
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    base = f"http://127.0.0.1:{port}"

    def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        request = urllib.request.Request(
            base + path,
            method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with opener.open(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode() or "{}")

    state = call("GET", "/api/setup/state")[1]
    if not state.get("completed") and state.get("current_step") in ("welcome", "account"):
        try:
            call(
                "POST",
                "/api/setup/administrator",
                {"display_name": "Acceptance", "login_identity": user, "password": password},
            )
        except urllib.error.HTTPError:
            pass
    call("POST", "/api/auth/sign-in", {"login_identity": user, "password": password})
    return call


def _time_shutdown_phases(home: Path, port: int, log_offset: int, started: float, timeout: float) -> dict:
    """Poll the instance log and process table; uvicorn's own log lines carry
    no timestamps, so observed arrival time is the measurement."""

    phases = {
        "drain_complete": "Waiting for application shutdown.",
        "teardown_complete": "Application shutdown complete.",
        "server_finished": "Finished server process",
        "graceful_timeout_fired": "timeout graceful shutdown exceeded",
    }
    seen: dict[str, float] = {}
    exited_after = None
    last_process_check = 0.0
    while time.monotonic() - started < timeout:
        try:
            with _log_path(home).open("rb") as log:
                log.seek(log_offset)
                tail = log.read().decode("utf-8", errors="replace")
        except OSError:
            tail = ""
        now = round(time.monotonic() - started, 2)
        for name, needle in phases.items():
            if name not in seen and needle in tail:
                seen[name] = now
        if time.monotonic() - last_process_check > 1.0 or "server_finished" in seen:
            last_process_check = time.monotonic()
            if not _processes_for_port(port):
                exited_after = round(time.monotonic() - started, 2)
                break
        time.sleep(0.05)
    return {"phases_seconds": seen, "process_exited_after_seconds": exited_after}


def cmd_shutdown(args: argparse.Namespace) -> int:
    home = Path(args.home)
    call = _signed_in_opener(args.port, args.user, args.password)
    log_offset = _log_path(home).stat().st_size if _log_path(home).exists() else 0
    started = time.monotonic()
    status, body = call("POST", "/api/product/shutdown")
    timing = _time_shutdown_phases(home, args.port, log_offset, started, args.timeout)
    remaining = _processes_for_port(args.port)
    result = {
        "command": "shutdown",
        "port": args.port,
        "http_status": status,
        "accepted": body.get("accepted"),
        **timing,
        "remaining_processes": remaining,
        "marker_after_exit": _marker(home),
        "port_free_after_exit": not _health_ok(args.port, timeout=1.0),
    }
    _emit(result)
    ok = timing["process_exited_after_seconds"] is not None and not remaining and result["marker_after_exit"] == "clean"
    return 0 if ok else 1


def _send_console_ctrl_c(pid: int) -> None:
    """Attach to the target's console and raise a real CTRL_C_EVENT there --
    the only way to deliver the same event a user's Ctrl+C keypress does."""

    kernel32 = ctypes.windll.kernel32
    kernel32.FreeConsole()
    if not kernel32.AttachConsole(pid):
        raise OSError(f"AttachConsole({pid}) failed: {ctypes.GetLastError()}")
    kernel32.SetConsoleCtrlHandler(None, True)
    try:
        if not kernel32.GenerateConsoleCtrlEvent(_CTRL_C_EVENT, 0):
            raise OSError(f"GenerateConsoleCtrlEvent failed: {ctypes.GetLastError()}")
        time.sleep(1.0)
    finally:
        kernel32.FreeConsole()


def cmd_send_ctrl_c(args: argparse.Namespace) -> int:
    _send_console_ctrl_c(args.pid)
    return 0


def cmd_ctrl_c(args: argparse.Namespace) -> int:
    """Launch the packaged console runtime (``python.exe -m mockingbird``) in
    its own console, optionally reset connections, then deliver Ctrl+C."""

    home = Path(args.home)
    home.mkdir(parents=True, exist_ok=True)
    python_exe = Path(args.release) / "python" / "python.exe"
    command = [str(python_exe), *(["-c", args.bootstrap] if args.bootstrap else ["-m", "mockingbird"])]
    process = subprocess.Popen(
        [*command, "--port", str(args.port), "--no-browser"],
        env=_clean_env(home),
        cwd=str(Path(args.release)),
        creationflags=_CREATE_NEW_CONSOLE,
    )
    ready_after = _wait_ready(args.port, args.timeout)
    if ready_after is None:
        process.kill()
        _emit({"command": "ctrl-c", "error": "instance never became ready"})
        return 1
    for _ in range(args.resets):
        client = socket.create_connection(("127.0.0.1", args.port), timeout=5)
        client.sendall(b"GET /api/product/health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: keep-alive\r\n\r\n")
        client.recv(64)
        _abortive_close(client)
    log_offset = _log_path(home).stat().st_size if _log_path(home).exists() else 0
    started = time.monotonic()
    subprocess.run([sys.executable, __file__, "send-ctrl-c", "--pid", str(process.pid)], check=True)
    try:
        return_code = process.wait(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        return_code = None
    timing = _time_shutdown_phases(home, args.port, log_offset, started, 5.0)
    remaining = _processes_for_port(args.port)
    result = {
        "command": "ctrl-c",
        "port": args.port,
        "ready_after_seconds": ready_after,
        "resets_before_ctrl_c": args.resets,
        "exited": return_code is not None,
        "exit_after_seconds": round(time.monotonic() - started, 2) if return_code is not None else None,
        "return_code": return_code,
        **timing,
        "remaining_processes": remaining,
        "marker_after_exit": _marker(home),
    }
    _emit(result)
    if return_code is None:
        process.kill()
    return 0 if return_code is not None and not remaining and result["marker_after_exit"] == "clean" else 1


def cmd_processes(args: argparse.Namespace) -> int:
    _emit({"command": "processes", "port": args.port, "processes": _processes_for_port(args.port)})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    def instance(p: argparse.ArgumentParser, *, needs_home: bool = False) -> None:
        p.add_argument("--port", type=int, required=True)
        if needs_home:
            p.add_argument("--home", required=True)

    launch = sub.add_parser("launch")
    instance(launch, needs_home=True)
    launch.add_argument("--release", required=True, help="Extracted MockingBird-windows-x64 folder.")
    launch.add_argument("--timeout", type=float, default=180.0)
    launch.set_defaults(func=cmd_launch)

    burst = sub.add_parser("burst")
    instance(burst)
    burst.add_argument("--bursts", type=int, default=10)
    burst.add_argument("--size", type=int, default=30)
    burst.set_defaults(func=cmd_burst)

    resets = sub.add_parser("resets")
    instance(resets)
    resets.add_argument("--count", type=int, default=20)
    resets.set_defaults(func=cmd_resets)

    shutdown = sub.add_parser("shutdown")
    instance(shutdown, needs_home=True)
    shutdown.add_argument("--user", required=True)
    shutdown.add_argument("--password", required=True)
    shutdown.add_argument("--timeout", type=float, default=90.0)
    shutdown.set_defaults(func=cmd_shutdown)

    ctrl_c = sub.add_parser("ctrl-c")
    instance(ctrl_c, needs_home=True)
    ctrl_c.add_argument("--release", required=True)
    ctrl_c.add_argument("--resets", type=int, default=20)
    ctrl_c.add_argument("--timeout", type=float, default=90.0)
    ctrl_c.add_argument(
        "--bootstrap",
        default=None,
        help="Optional `python -c` bootstrap instead of `-m mockingbird` (pre-rebuild overlay runs only).",
    )
    ctrl_c.set_defaults(func=cmd_ctrl_c)

    send = sub.add_parser("send-ctrl-c")
    send.add_argument("--pid", type=int, required=True)
    send.set_defaults(func=cmd_send_ctrl_c)

    processes = sub.add_parser("processes")
    instance(processes)
    processes.set_defaults(func=cmd_processes)
    return parser


def main(argv: list[str] | None = None) -> int:
    if os.name != "nt":
        print("This acceptance procedure runs on native Windows only.", file=sys.stderr)
        return 2
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
