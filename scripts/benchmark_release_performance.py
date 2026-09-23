"""Measure v0.1 release performance contracts against a realistic workload.

Performance / Scale / Stability Closure v1.

Starts a **real** MockingBird HTTP server (uvicorn, the same ASGI app the
packaged product runs) against a workload built by
`scripts/performance_workload.py`, signs in the way a real browser does,
and measures the operations a real owner performs. It reports median and
tail wall-clock per operation, the response byte size, and -- for the
surfaces where it matters -- the SQL statement count the request actually
issued, so an N+1 shows up as a number rather than an intuition.

Reproducibility
---------------
Every run records the dataset shape, the host/environment, the exact
command, per-operation samples (not just a summary), and the repeat count,
so a "before" and an "after" can be compared honestly. Single-run precision
is deliberately not reported: `--repeat` defaults to 5 and the report
carries min/median/p90/max, because one sample of a SQLite-backed local
request says very little.

Usage
-----
    python scripts/benchmark_release_performance.py \\
        --root /path/to/workload --profile b --json before.json

`--root` may point at an already-generated workload (measure only) or an
empty directory (`--seed` generates the profile first).
"""

from __future__ import annotations

import argparse
import atexit
import contextlib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(_ROOT / "src"))


_LOGIN_IDENTITY = "performance-owner"
_PASSWORD = "performance-benchmark-passphrase"
ADMIN_BOOTSTRAP = {
    "display_name": "Performance Owner",
    "login_identity": _LOGIN_IDENTITY,
    "password": _PASSWORD,
}
SIGN_IN = {"login_identity": _LOGIN_IDENTITY, "password": _PASSWORD}


@dataclass
class Operation:
    """One user-facing operation worth a release performance claim."""

    key: str
    label: str
    method: str
    path: str
    body: dict | None = None
    # Operations a real owner performs constantly are held to a stricter
    # expectation than ones they perform rarely; see `CONTRACT_BUDGETS`.
    tier: str = "ordinary"


def core_operations() -> list[Operation]:
    """The operations a real owner actually performs, by page.

    Routes are the real ones the shipped frontend calls -- verified against
    `mockingbird.api.main`, not assumed from page names.
    """

    return [
        Operation("dashboard", "Dashboard / Today", "GET", "/api/dashboard/summary"),
        Operation("health", "Product health", "GET", "/api/product/health"),
        Operation("streams", "Camera / Stream status", "GET", "/api/streams"),
        Operation("sources", "Sources list", "GET", "/api/sources"),
        Operation("review_queue", "Review Queue", "GET", "/api/review-queue"),
        Operation("bird_log", "Bird Log (journal)", "GET", "/api/bird-log/journal"),
        Operation("bird_log_likely", "Bird Log (likely species)", "GET", "/api/bird-log/likely"),
        Operation("analytics", "Analytics", "GET", "/api/analytics/summary"),
        Operation("local_data", "Local Data", "GET", "/api/settings/local-data"),
        Operation("dataset_coverage", "Dataset coverage", "GET", "/api/dataset-coverage/summary"),
        Operation("dataset_quality", "Dataset quality", "GET", "/api/dataset-quality/summary"),
        Operation("yard_map", "Yard Map", "GET", "/api/yard-map"),
        Operation(
            "activity_library",
            "Activity Library (first page)",
            "POST",
            "/api/activity-library/search",
            body={"page_size": 24, "offset": 0},
        ),
        Operation(
            "activity_library_filtered",
            "Activity Library (species filter)",
            "POST",
            "/api/activity-library/search",
            body={"page_size": 24, "offset": 0, "confirmed_label": "Northern Cardinal"},
        ),
        Operation(
            "activity_library_search",
            "Activity Library (free-text search)",
            "POST",
            "/api/activity-library/search",
            body={"page_size": 24, "offset": 0, "search": "cardinal"},
        ),
        Operation(
            "activity_library_deep",
            "Activity Library (deep page, offset 2000)",
            "POST",
            "/api/activity-library/search",
            body={"page_size": 24, "offset": 2000},
            tier="heavy",
        ),
        Operation("alerts", "Alerts / notifications", "GET", "/api/alerts"),
        Operation("collections", "Collections", "GET", "/api/collections"),
        Operation("storage_retention", "Storage retention summary", "GET", "/api/settings/storage-retention/summary"),
        Operation("workers", "Background worker status", "GET", "/api/workers/status"),
        Operation("place_biodiversity", "Place biodiversity summary", "GET", "/api/place/biodiversity-summary", tier="heavy"),
        Operation("place_story", "Place Story", "GET", "/api/place/story", tier="heavy"),
        Operation("place_year_over_year", "Place year-over-year", "GET", "/api/place/year-over-year", tier="heavy"),
        # Deliberately last: the surfaces the pre-release audit flagged as
        # unbounded. Measured, not assumed.
        Operation("visits_all", "GET /api/visits (unbounded surface)", "GET", "/api/visits", tier="heavy"),
        Operation("events_all", "GET /api/events", "GET", "/api/events", tier="heavy"),
        Operation("media_all", "GET /api/media", "GET", "/api/media", tier="heavy"),
        Operation("zones_all", "GET /api/zones", "GET", "/api/zones", tier="heavy"),
        Operation("species_suggestions_all", "GET /api/species-suggestions", "GET", "/api/species-suggestions", tier="heavy"),
        Operation("detection_proposals_all", "GET /api/detection-proposals", "GET", "/api/detection-proposals", tier="heavy"),
        Operation("detection_runs_all", "GET /api/detection-runs", "GET", "/api/detection-runs", tier="heavy"),
        Operation("review_labels_all", "GET /api/review-labels", "GET", "/api/review-labels", tier="heavy"),
        Operation("motion_evidence_all", "GET /api/motion/evidence", "GET", "/api/motion/evidence", tier="heavy"),
    ]


@dataclass
class Measurement:
    key: str
    label: str
    method: str
    path: str
    status: int
    samples_ms: list[float]
    response_bytes: int
    item_count: int | None = None
    sql_statements: int | None = None
    error: str | None = None

    @property
    def median_ms(self) -> float:
        return statistics.median(self.samples_ms) if self.samples_ms else float("nan")

    def summary(self) -> dict[str, object]:
        ordered = sorted(self.samples_ms)
        p90 = ordered[min(len(ordered) - 1, int(round(0.9 * (len(ordered) - 1))))] if ordered else None
        return {
            "key": self.key,
            "label": self.label,
            "request": f"{self.method} {self.path}",
            "status": self.status,
            "median_ms": round(self.median_ms, 1) if ordered else None,
            "min_ms": round(ordered[0], 1) if ordered else None,
            "p90_ms": round(p90, 1) if p90 is not None else None,
            "max_ms": round(ordered[-1], 1) if ordered else None,
            "samples_ms": [round(value, 1) for value in self.samples_ms],
            "response_bytes": self.response_bytes,
            "item_count": self.item_count,
            "sql_statements": self.sql_statements,
            "error": self.error,
        }


@dataclass
class StartupMeasurement:
    """Startup broken into the phases a user can actually perceive."""

    process_start_to_port_bound_ms: float | None = None
    port_bound_to_backend_ready_ms: float | None = None
    process_start_to_backend_ready_ms: float | None = None
    process_start_to_first_useful_page_ms: float | None = None
    database_open_ms: float | None = None
    notes: list[str] = field(default_factory=list)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


_LIVE_SERVERS: list["_Server"] = []


def _stop_all_servers() -> None:
    for server in list(_LIVE_SERVERS):
        with contextlib.suppress(Exception):
            server.stop()


atexit.register(_stop_all_servers)


class _Server:
    """A real uvicorn process serving the workload under measurement.

    Every instance registers itself for `atexit` cleanup. An orphaned
    server holding a deleted SQLite file open makes the *next* run's
    schema creation fail with a bare "disk I/O error" -- observed directly
    during development, and worth preventing rather than diagnosing twice.
    """

    def __init__(self, root: Path, port: int, *, env_extra: dict[str, str] | None = None) -> None:
        self.root = root
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"
        self._process: subprocess.Popen | None = None
        self._env_extra = env_extra or {}
        self.log_path = root / "server.log"
        self.launched_at: float | None = None
        self.port_bound_at: float | None = None
        self.ready_at: float | None = None

    def env(self) -> dict[str, str]:
        env = dict(os.environ)
        env.update(
            {
                "PYTHONPATH": str(_ROOT / "src"),
                "MOCKINGBIRD_DB_URL": f"sqlite:///{self.root / 'mockingbird.sqlite3'}",
                "MOCKINGBIRD_MEDIA_ROOT": str(self.root / "media"),
                "MOCKINGBIRD_BACKUP_ROOT": str(self.root / "backups"),
                "PYTHONUNBUFFERED": "1",
            }
        )
        env.update(self._env_extra)
        return env

    def start(self, *, timeout_seconds: float = 180.0) -> None:
        # Launch through a tiny generated bootstrap rather than
        # `python -m uvicorn` with `PYTHONPATH` set. MockingBird's own
        # packaged Windows runtime is an embeddable CPython, which ignores
        # `PYTHONPATH` entirely -- without this the child silently imported
        # the *packaged* `mockingbird` from its own `site-packages` instead
        # of the tree under measurement, and failed on a schema mismatch.
        # Prepending the path inside the child is unambiguous on every
        # platform.
        bootstrap = self.root / "_serve.py"
        bootstrap.write_text(
            "import sys\n"
            f"sys.path.insert(0, {str(_ROOT / 'src')!r})\n"
            "import uvicorn\n"
            "uvicorn.run("
            "'mockingbird.api.main:app', "
            f"host='127.0.0.1', port={self.port}, log_level='warning')\n",
            encoding="utf-8",
        )
        command = [sys.executable, str(bootstrap)]
        self.launched_at = time.perf_counter()
        _LIVE_SERVERS.append(self)
        log = open(self.log_path, "ab")
        self._process = subprocess.Popen(
            command, cwd=str(_ROOT), env=self.env(), stdout=log, stderr=log
        )
        deadline = self.launched_at + timeout_seconds
        while time.perf_counter() < deadline:
            if self._process.poll() is not None:
                raise RuntimeError(
                    f"server exited early ({self._process.returncode}); see {self.log_path}"
                )
            if self.port_bound_at is None:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                    probe.settimeout(0.2)
                    if probe.connect_ex(("127.0.0.1", self.port)) == 0:
                        self.port_bound_at = time.perf_counter()
            if self.port_bound_at is not None:
                try:
                    with urllib.request.urlopen(f"{self.base_url}/api/product/instance", timeout=5):
                        self.ready_at = time.perf_counter()
                        return
                except (urllib.error.URLError, OSError, TimeoutError):
                    pass
            time.sleep(0.02)
        raise TimeoutError(f"server never became ready; see {self.log_path}")

    def stop(self) -> None:
        if self._process is None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=30)
        self._process = None
        with contextlib.suppress(ValueError):
            _LIVE_SERVERS.remove(self)

    def rss_kb(self) -> int | None:
        if self._process is None:
            return None
        status = Path(f"/proc/{self._process.pid}/status")
        try:
            for line in status.read_text().splitlines():
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
        except OSError:
            return None
        return None

    def open_file_count(self) -> int | None:
        if self._process is None:
            return None
        try:
            return len(list(Path(f"/proc/{self._process.pid}/fd").iterdir()))
        except OSError:
            return None


class _Client:
    """A minimal cookie-carrying HTTP client -- no test-only shortcuts."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self._cookie: str | None = None

    def request(self, method: str, path: str, body: dict | None = None, *, timeout: float = 300.0):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = urllib.request.Request(self.base_url + path, data=data, method=method)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        if self._cookie:
            request.add_header("Cookie", self._cookie)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
                for key, value in response.getheaders():
                    if key.lower() == "set-cookie":
                        self._cookie = value.split(";", 1)[0]
                return response.status, payload
        except urllib.error.HTTPError as error:
            return error.code, error.read()

    def sign_in(self) -> None:
        status, _ = self.request("POST", "/api/setup/administrator", ADMIN_BOOTSTRAP)
        if status == 201:
            return
        status, payload = self.request("POST", "/api/auth/sign-in", SIGN_IN)
        if status != 200:
            raise RuntimeError(f"could not authenticate: {status} {payload[:200]!r}")


def _item_count(payload: bytes) -> int | None:
    try:
        parsed = json.loads(payload)
    except (ValueError, UnicodeDecodeError):
        return None
    if isinstance(parsed, list):
        return len(parsed)
    if isinstance(parsed, dict):
        for key in ("items", "results", "entries", "visits", "records"):
            value = parsed.get(key)
            if isinstance(value, list):
                return len(value)
    return None


def measure_operations(
    client: _Client, operations: list[Operation], *, repeat: int
) -> list[Measurement]:
    results: list[Measurement] = []
    for operation in operations:
        samples: list[float] = []
        status = 0
        payload = b""
        error: str | None = None
        # One warm-up call: the first request to any route pays FastAPI's
        # own response-model construction cost once, which is real but is
        # not what a user experiences on their tenth Dashboard visit.
        try:
            client.request(operation.method, operation.path, operation.body)
        except Exception as exc:  # noqa: BLE001 - recorded, never swallowed
            error = f"{type(exc).__name__}: {exc}"
        for _ in range(repeat):
            started = time.perf_counter()
            try:
                status, payload = client.request(operation.method, operation.path, operation.body)
            except Exception as exc:  # noqa: BLE001
                error = f"{type(exc).__name__}: {exc}"
                break
            samples.append((time.perf_counter() - started) * 1000.0)
        results.append(
            Measurement(
                key=operation.key,
                label=operation.label,
                method=operation.method,
                path=operation.path,
                status=status,
                samples_ms=samples,
                response_bytes=len(payload),
                item_count=_item_count(payload),
                error=error,
            )
        )
    return results


def count_sql_statements(root: Path, operations: list[Operation]) -> dict[str, int]:
    """Count SQL statements per operation, in-process, via an engine hook.

    Runs the same ASGI app through an in-process transport so SQLAlchemy's
    `before_cursor_execute` event can be attached to the live engine. This
    is a *structural* measurement -- an N+1 is a statement count, not a
    wall-clock number -- so the in-process path is the right tool and its
    timing is deliberately not reported.
    """

    os.environ["MOCKINGBIRD_DB_URL"] = f"sqlite:///{root / 'mockingbird.sqlite3'}"
    os.environ["MOCKINGBIRD_MEDIA_ROOT"] = str(root / "media")
    os.environ["MOCKINGBIRD_BACKUP_ROOT"] = str(root / "backups")

    from sqlalchemy import event

    from mockingbird.api import main as api_main
    from mockingbird.repository.product_repository import ProductRepository

    repository = ProductRepository(
        db_url=f"sqlite:///{root / 'mockingbird.sqlite3'}", media_root=root / "media"
    )
    api_main.configure_repository(repository)

    counter = {"n": 0}

    def _on_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        counter["n"] += 1

    event.listen(repository.engine, "before_cursor_execute", _on_execute)

    from starlette.testclient import TestClient

    counts: dict[str, int] = {}
    try:
        with TestClient(api_main.app) as client:
            bootstrap = client.post("/api/setup/administrator", json=ADMIN_BOOTSTRAP)
            if bootstrap.status_code != 201:
                client.post("/api/auth/sign-in", json=SIGN_IN)
            for operation in operations:
                # Warm up, then count a single clean request.
                client.request(operation.method, operation.path, json=operation.body)
                counter["n"] = 0
                client.request(operation.method, operation.path, json=operation.body)
                counts[operation.key] = counter["n"]
    finally:
        event.remove(repository.engine, "before_cursor_execute", _on_execute)
        api_main.configure_repository(None)
    return counts


def measure_startup(root: Path, *, warm: bool) -> tuple[StartupMeasurement, _Server]:
    """Start a server and attribute the wait to its perceivable phases."""

    measurement = StartupMeasurement()
    port = _free_port()
    server = _Server(root, port)
    server.start()
    assert server.launched_at is not None and server.ready_at is not None
    if server.port_bound_at is not None:
        measurement.process_start_to_port_bound_ms = (
            server.port_bound_at - server.launched_at
        ) * 1000.0
        measurement.port_bound_to_backend_ready_ms = (
            server.ready_at - server.port_bound_at
        ) * 1000.0
    measurement.process_start_to_backend_ready_ms = (
        server.ready_at - server.launched_at
    ) * 1000.0

    client = _Client(server.base_url)
    client.sign_in()
    started = time.perf_counter()
    client.request("GET", "/api/dashboard/summary")
    measurement.process_start_to_first_useful_page_ms = (
        (server.ready_at - server.launched_at) + (time.perf_counter() - started)
    ) * 1000.0
    measurement.notes.append("warm restart" if warm else "cold start (first open of this database)")
    return measurement, server


def environment_report() -> dict[str, object]:
    cpu_count = os.cpu_count()
    mem_total_kb = None
    with contextlib.suppress(OSError, ValueError):
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                mem_total_kb = int(line.split()[1])
                break
    return {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "cpu_count": cpu_count,
        "memory_total_kb": mem_total_kb,
        "utc": datetime.now(UTC).isoformat(),
        "git_head": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=_ROOT, capture_output=True, text=True
        ).stdout.strip(),
    }


def directory_bytes(path: Path) -> int:
    total = 0
    for entry in path.rglob("*"):
        with contextlib.suppress(OSError):
            if entry.is_file():
                total += entry.stat().st_size
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--profile", default=None, help="Seed this profile into --root first.")
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument(
        "--memory-passes",
        type=int,
        default=2,
        help=(
            "Extra full operation passes used only to detect per-request "
            "retention. Set to 0 for a lean before/after comparison -- at a "
            "large library each pass costs as much as the measured pass "
            "itself, and memory trajectory is better measured by --soak."
        ),
    )
    parser.add_argument("--media-bytes", type=int, default=0)
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--skip-sql-counts", action="store_true")
    parser.add_argument("--label", default="", help="Free-text run label, e.g. 'before' / 'after'.")
    args = parser.parse_args(argv)

    import runpy

    workload = runpy.run_path(str(_ROOT / "scripts" / "performance_workload.py"))

    dataset: dict[str, object] = {}
    if args.profile:
        _stop_all_servers()
        if args.root.exists():
            shutil.rmtree(args.root)
        profile = workload["PROFILES"][args.profile]
        repository = workload["open_repository"](args.root)
        try:
            result = workload["build_workload"](
                repository, profile, media_bytes=args.media_bytes, progress=True
            )
        finally:
            repository.close()
        dataset = result.as_dict()
        dataset["title"] = profile.title
        dataset["rationale"] = profile.rationale

    report: dict[str, object] = {
        "label": args.label,
        "environment": environment_report(),
        "command": " ".join([Path(sys.argv[0]).name, *(argv or sys.argv[1:])]),
        "repeat": args.repeat,
        "dataset": dataset,
    }

    operations = core_operations()

    # Cold start: first open of this database by this process.
    cold, server = measure_startup(args.root, warm=False)
    try:
        client = _Client(server.base_url)
        client.sign_in()
        report["memory_after_startup_kb"] = server.rss_kb()
        report["open_files_after_startup"] = server.open_file_count()
        measurements = measure_operations(client, operations, repeat=args.repeat)
        report["memory_after_operations_kb"] = server.rss_kb()
        report["open_files_after_operations"] = server.open_file_count()
        # Extra full passes detect per-request retention that a single pass
        # cannot distinguish from ordinary warm-up allocation. Optional:
        # each one costs a full measured pass, which at a large library is
        # substantial, so a lean before/after comparison passes 0 and reads
        # memory trajectory from `--soak` instead.
        for _ in range(max(0, args.memory_passes)):
            measure_operations(client, operations, repeat=args.repeat)
        report["memory_passes"] = args.memory_passes
        report["memory_after_extra_passes_kb"] = server.rss_kb()
        report["open_files_after_extra_passes"] = server.open_file_count()
    finally:
        server.stop()

    warm_server: _Server | None = None
    try:
        warm, warm_server = measure_startup(args.root, warm=True)
    finally:
        if warm_server is not None:
            warm_server.stop()

    report["startup"] = {"cold": asdict(cold), "warm": asdict(warm)}
    report["operations"] = [measurement.summary() for measurement in measurements]

    if not args.skip_sql_counts:
        try:
            counts = count_sql_statements(args.root, operations)
            for entry in report["operations"]:
                entry["sql_statements"] = counts.get(entry["key"])
        except Exception as exc:  # noqa: BLE001 - reported, never fatal
            report["sql_count_error"] = f"{type(exc).__name__}: {exc}"

    db_path = args.root / "mockingbird.sqlite3"
    report["storage"] = {
        "database_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "media_bytes": directory_bytes(args.root / "media"),
        "total_bytes": directory_bytes(args.root),
    }

    text = json.dumps(report, indent=2)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.json}", file=sys.stderr)
    else:
        print(text)

    print(
        f"\n{'operation':44s} {'median':>9s} {'p90':>9s} {'max':>9s} {'bytes':>10s} {'sql':>6s}",
        file=sys.stderr,
    )
    for entry in report["operations"]:
        print(
            f"{entry['label'][:44]:44s} "
            f"{entry['median_ms'] or 0:>8.1f}ms "
            f"{entry['p90_ms'] or 0:>8.1f}ms "
            f"{entry['max_ms'] or 0:>8.1f}ms "
            f"{entry['response_bytes']:>10,d} "
            f"{entry['sql_statements'] if entry['sql_statements'] is not None else '-':>6}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
