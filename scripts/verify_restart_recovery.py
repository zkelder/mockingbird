"""Stop and restart a real Host under load, then check nothing was lost.

Performance / Scale / Stability Closure v1, MEASURE 10.

Drives a real Host with concurrent reads while observation work is being
written, kills it -- both politely and abruptly -- restarts it, and then
verifies the properties a restart must never break: no duplicated
observations, no Visit stranded without its Event, no queue row left
permanently claimed by a process that no longer exists, and the product
usable again immediately.

Deliberately destructive, so it only ever runs against a disposable
workload directory it is given explicitly. It never touches a real
installation.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
import runpy
import signal
import sys
import threading
import time

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(_ROOT / "src"))

_BENCHMARK = runpy.run_path(str(_ROOT / "scripts" / "benchmark_release_performance.py"))
_WORKLOAD = runpy.run_path(str(_ROOT / "scripts" / "performance_workload.py"))


@dataclass
class Census:
    """The facts a restart must preserve exactly."""

    visits: int
    events: int
    media_assets: int
    evidence_links: int
    review_labels: int
    duplicate_visit_ids: int
    visits_without_event: int
    evidence_links_without_media: int
    acoustic_runs_processing: int

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class RestartCheck:
    label: str
    stop_mode: str
    requests_before: int
    requests_after: int
    seconds_to_backend_ready: float
    seconds_to_first_useful_page: float
    census_before: Census
    census_after: Census
    problems: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "stop_mode": self.stop_mode,
            "requests_before": self.requests_before,
            "requests_after": self.requests_after,
            "seconds_to_backend_ready": round(self.seconds_to_backend_ready, 2),
            "seconds_to_first_useful_page": round(self.seconds_to_first_useful_page, 2),
            "census_before": self.census_before.as_dict(),
            "census_after": self.census_after.as_dict(),
            "problems": self.problems,
        }


def _census(root: Path) -> Census:
    import sqlite3

    connection = sqlite3.connect(f"file:{root / 'mockingbird.sqlite3'}?mode=ro", uri=True)
    try:

        def scalar(sql: str) -> int:
            return int(connection.execute(sql).fetchone()[0])

        try:
            acoustic_processing = scalar(
                "SELECT COUNT(*) FROM acoustic_analysis_runs WHERE status = 'processing'"
            )
        except sqlite3.OperationalError:
            acoustic_processing = 0
        return Census(
            visits=scalar("SELECT COUNT(*) FROM visits"),
            events=scalar("SELECT COUNT(*) FROM events"),
            media_assets=scalar("SELECT COUNT(*) FROM media_assets"),
            evidence_links=scalar("SELECT COUNT(*) FROM visit_evidence_links"),
            review_labels=scalar("SELECT COUNT(*) FROM review_labels"),
            duplicate_visit_ids=scalar(
                "SELECT COUNT(*) FROM (SELECT id FROM visits GROUP BY id HAVING COUNT(*) > 1)"
            ),
            visits_without_event=scalar(
                "SELECT COUNT(*) FROM visits v "
                "LEFT JOIN events e ON e.id = v.event_id WHERE e.id IS NULL"
            ),
            evidence_links_without_media=scalar(
                "SELECT COUNT(*) FROM visit_evidence_links l "
                "LEFT JOIN media_assets m ON m.id = l.media_asset_id WHERE m.id IS NULL"
            ),
            acoustic_runs_processing=acoustic_processing,
        )
    finally:
        connection.close()


class _LoadDriver(threading.Thread):
    """Continuous reads, so the Host is never idle when it is stopped."""

    def __init__(self, base_url: str) -> None:
        super().__init__(daemon=True)
        self._client = _BENCHMARK["_Client"](base_url)
        self._operations = [
            operation
            for operation in _BENCHMARK["core_operations"]()
            if operation.key in {"dashboard", "review_queue", "streams", "alerts"}
        ]
        self._should_stop = threading.Event()
        self.completed = 0
        self.errors: list[str] = []

    def run(self) -> None:
        try:
            self._client.sign_in()
        except Exception as exc:  # noqa: BLE001 - recorded, never swallowed
            self.errors.append(f"sign-in: {type(exc).__name__}: {exc}")
            return
        index = 0
        while not self._should_stop.is_set():
            operation = self._operations[index % len(self._operations)]
            index += 1
            try:
                self._client.request(operation.method, operation.path, operation.body, timeout=30)
                self.completed += 1
            except Exception as exc:  # noqa: BLE001
                # Errors during the stop window are expected; they are
                # recorded rather than treated as failures.
                self.errors.append(f"{operation.path}: {type(exc).__name__}")

    def stop(self) -> None:
        self._should_stop.set()


def _ingest(root: Path, index: int) -> int:
    repository = _WORKLOAD["open_repository"](root)
    try:
        written = _WORKLOAD["build_workload"](
            repository,
            _WORKLOAD["WorkloadProfile"](
                key="restart",
                title="restart increment",
                rationale="observation work in flight across a restart",
                days=1,
                streams=1,
                visits_per_day=8,
                reviewed_fraction=0.3,
            ),
            seed=771 + index,
            id_prefix=f"restart{index}",
        )
        return written.visits
    finally:
        repository.close()


def run_check(root: Path, *, stop_mode: str, index: int) -> RestartCheck:
    server_class = _BENCHMARK["_Server"]
    server = server_class(root, _BENCHMARK["_free_port"]())
    server.start()
    driver = _LoadDriver(server.base_url)
    driver.start()
    # Let real work accumulate, and write new observations while the Host
    # is serving -- a restart of an idle process proves very little.
    time.sleep(3)
    _ingest(root, index)
    time.sleep(3)

    requests_before = driver.completed
    census_before = _census(root)

    process = server._process  # noqa: SLF001 - this script exists to kill it
    assert process is not None
    if stop_mode == "abrupt":
        # No clean shutdown at all: what a power loss or an OOM kill does.
        process.send_signal(signal.SIGKILL)
        process.wait(timeout=30)
        server._process = None  # noqa: SLF001
    else:
        server.stop()
    driver.stop()
    driver.join(timeout=30)

    restarted = server_class(root, _BENCHMARK["_free_port"]())
    started_at = time.perf_counter()
    restarted.start()
    ready = time.perf_counter() - started_at
    client = _BENCHMARK["_Client"](restarted.base_url)
    client.sign_in()
    first_page_at = time.perf_counter()
    status, payload = client.request("GET", "/api/dashboard/summary")
    first_page = (time.perf_counter() - first_page_at) + ready

    problems: list[str] = []
    if status != 200:
        problems.append(f"dashboard returned {status} after restart: {payload[:200]!r}")

    census_after = _census(root)
    if census_after.duplicate_visit_ids:
        problems.append(f"{census_after.duplicate_visit_ids} duplicate Visit ids after restart")
    if census_after.visits_without_event > census_before.visits_without_event:
        problems.append("a Visit lost its Event across the restart")
    if census_after.evidence_links_without_media > census_before.evidence_links_without_media:
        problems.append("an evidence link lost its media asset across the restart")
    for name in ("visits", "events", "media_assets", "evidence_links", "review_labels"):
        before_value = getattr(census_before, name)
        after_value = getattr(census_after, name)
        if after_value < before_value:
            problems.append(f"{name} dropped from {before_value} to {after_value} across the restart")
    if census_after.acoustic_runs_processing:
        problems.append(
            f"{census_after.acoustic_runs_processing} acoustic runs still claimed as "
            "'processing' by a process that no longer exists"
        )

    # The Host must be genuinely usable again, not merely answering.
    requests_after = 0
    deadline = time.perf_counter() + 10
    while time.perf_counter() < deadline:
        code, _ = client.request("GET", "/api/review-queue")
        if code != 200:
            problems.append(f"review queue returned {code} after restart")
            break
        requests_after += 1
    restarted.stop()

    return RestartCheck(
        label=f"{stop_mode} stop under load",
        stop_mode=stop_mode,
        requests_before=requests_before,
        requests_after=requests_after,
        seconds_to_backend_ready=ready,
        seconds_to_first_useful_page=first_page,
        census_before=census_before,
        census_after=census_after,
        problems=problems,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True, help="A DISPOSABLE workload directory.")
    parser.add_argument("--profile", default=None, help="Seed this profile into --root first.")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.profile:
        import shutil

        if args.root.exists():
            shutil.rmtree(args.root)
        repository = _WORKLOAD["open_repository"](args.root)
        try:
            _WORKLOAD["build_workload"](repository, _WORKLOAD["PROFILES"][args.profile])
        finally:
            repository.close()

    checks = [
        run_check(args.root, stop_mode="graceful", index=1),
        run_check(args.root, stop_mode="abrupt", index=2),
        # A second abrupt stop, to catch damage that only shows on the
        # *next* unclean start rather than the first.
        run_check(args.root, stop_mode="abrupt", index=3),
    ]

    payload = {
        "utc": datetime.now(UTC).isoformat(),
        "environment": _BENCHMARK["environment_report"](),
        "checks": [check.as_dict() for check in checks],
        "problems": [problem for check in checks for problem in check.problems],
    }
    text = json.dumps(payload, indent=2)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.json}", file=sys.stderr)

    for check in checks:
        print(
            f"{check.label:26s} ready {check.seconds_to_backend_ready:5.2f}s  "
            f"first page {check.seconds_to_first_useful_page:5.2f}s  "
            f"visits {check.census_before.visits} -> {check.census_after.visits}  "
            f"{'OK' if not check.problems else 'PROBLEMS: ' + '; '.join(check.problems)}",
            file=sys.stderr,
        )
    return 1 if payload["problems"] else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
