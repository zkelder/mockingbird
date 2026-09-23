"""Watch a running MockingBird Host for resource growth over time.

Performance / Scale / Stability Closure v1.

Starts a real Host against a real workload, then drives it the way a user
and a Camera Node together would -- repeated UI/API reads plus continuous
observation writes -- while sampling process resident memory, CPU time,
open file descriptors, thread count, database size, media size and log
size on a fixed interval.

What it is for, and what it is not
----------------------------------
This answers "does anything grow without bound while the product is
used?" It does **not** prove 24/7 field reliability: it runs on one
machine, for however long it is told to, with synthetic ingest rather
than a real camera. The report that cites it states the actual duration
and conditions rather than generalising from them.

Growth is judged on the second half of the run, after model/import warm-up
has settled, because the first minutes of any Python process allocate
freely and a naive first-to-last delta reads that as a leak.
"""

from __future__ import annotations

import argparse
import contextlib
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import runpy
import statistics
import sys
import time

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(_ROOT / "src"))

_BENCHMARK = runpy.run_path(str(_ROOT / "scripts" / "benchmark_release_performance.py"))
_WORKLOAD = runpy.run_path(str(_ROOT / "scripts" / "performance_workload.py"))


@dataclass
class Sample:
    elapsed_seconds: float
    rss_kb: int | None
    cpu_seconds: float | None
    open_files: int | None
    threads: int | None
    database_bytes: int
    media_bytes: int
    log_bytes: int
    requests_completed: int
    visits_written: int


@dataclass
class SoakResult:
    duration_seconds: float
    interval_seconds: float
    samples: list[Sample] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def trend(self, attribute: str) -> dict[str, object]:
        """Growth over the settled second half, not over warm-up."""

        values = [
            (sample.elapsed_seconds, getattr(sample, attribute))
            for sample in self.samples
            if getattr(sample, attribute) is not None
        ]
        if len(values) < 4:
            return {"insufficient_samples": len(values)}
        midpoint = len(values) // 2
        settled = values[midpoint:]
        first_t, first_v = settled[0]
        last_t, last_v = settled[-1]
        span_hours = max((last_t - first_t) / 3600.0, 1e-9)
        return {
            "first": first_v,
            "last": last_v,
            "min": min(value for _t, value in settled),
            "max": max(value for _t, value in settled),
            "median": statistics.median(value for _t, value in settled),
            "delta_over_settled_half": last_v - first_v,
            "per_hour": round((last_v - first_v) / span_hours, 1),
            "settled_sample_count": len(settled),
        }

    def as_dict(self) -> dict[str, object]:
        return {
            "duration_seconds": round(self.duration_seconds, 1),
            "interval_seconds": self.interval_seconds,
            "sample_count": len(self.samples),
            "trends": {
                name: self.trend(name)
                for name in (
                    "rss_kb",
                    "cpu_seconds",
                    "open_files",
                    "threads",
                    "database_bytes",
                    "media_bytes",
                    "log_bytes",
                )
            },
            "samples": [asdict(sample) for sample in self.samples],
            "notes": self.notes,
        }


def _cpu_seconds(pid: int) -> float | None:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
    except (OSError, IndexError):
        return None
    ticks = os.sysconf("SC_CLK_TCK")
    # utime + stime, fields 14 and 15 of `proc(5)` (1-based) -- here index
    # 11 and 12 because the leading pid/comm have been split away.
    return (int(fields[11]) + int(fields[12])) / ticks


def _thread_count(pid: int) -> int | None:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("Threads:"):
                return int(line.split()[1])
    except OSError:
        return None
    return None


def _directory_bytes(path: Path) -> int:
    total = 0
    for entry in path.rglob("*"):
        with contextlib.suppress(OSError):
            if entry.is_file():
                total += entry.stat().st_size
    return total


def run_soak(
    root: Path,
    *,
    duration_seconds: float,
    interval_seconds: float,
    ingest_visits_per_minute: float,
) -> SoakResult:
    server_class = _BENCHMARK["_Server"]
    client_class = _BENCHMARK["_Client"]
    free_port = _BENCHMARK["_free_port"]
    operations = [
        operation
        for operation in _BENCHMARK["core_operations"]()
        # Drive the surfaces a real owner actually revisits, not the whole
        # inventory -- a soak is about trajectory, not coverage.
        if operation.key
        in {
            "dashboard",
            "review_queue",
            "bird_log",
            "analytics",
            "streams",
            "activity_library",
            "alerts",
            "yard_map",
        }
    ]

    server = server_class(root, free_port())
    server.start()
    result = SoakResult(duration_seconds=duration_seconds, interval_seconds=interval_seconds)
    result.notes.append(f"server pid {server._process.pid}")  # noqa: SLF001 - diagnostics only
    client = client_class(server.base_url)
    client.sign_in()

    repository = _WORKLOAD["open_repository"](root)

    started = time.perf_counter()
    next_sample = started
    next_ingest = started
    requests_completed = 0
    visits_written = 0
    ingest_interval = 60.0 / max(ingest_visits_per_minute, 1e-9)
    index = 0
    try:
        while True:
            now = time.perf_counter()
            elapsed = now - started
            if elapsed >= duration_seconds:
                break

            if now >= next_sample:
                pid = server._process.pid  # noqa: SLF001 - diagnostics only
                result.samples.append(
                    Sample(
                        elapsed_seconds=round(elapsed, 1),
                        rss_kb=server.rss_kb(),
                        cpu_seconds=_cpu_seconds(pid),
                        open_files=server.open_file_count(),
                        threads=_thread_count(pid),
                        database_bytes=(root / "mockingbird.sqlite3").stat().st_size,
                        media_bytes=_directory_bytes(root / "media"),
                        log_bytes=(
                            server.log_path.stat().st_size if server.log_path.exists() else 0
                        ),
                        requests_completed=requests_completed,
                        visits_written=visits_written,
                    )
                )
                next_sample = now + interval_seconds

            if now >= next_ingest and ingest_visits_per_minute > 0:
                # One day's worth of the fresh-install profile, written
                # straight through the real ORM, so the soak keeps the
                # database and media growing the way live observation does.
                written = _WORKLOAD["build_workload"](
                    repository,
                    _WORKLOAD["WorkloadProfile"](
                        key="soak",
                        title="soak increment",
                        rationale="one small ingest burst",
                        days=1,
                        streams=1,
                        visits_per_day=3,
                        reviewed_fraction=0.4,
                    ),
                    seed=20260922 + index,
                    now=datetime.now(UTC) + timedelta(seconds=index),
                    id_prefix=f"soak{index}",
                )
                visits_written += written.visits
                index += 1
                next_ingest = now + ingest_interval

            operation = operations[requests_completed % len(operations)]
            client.request(operation.method, operation.path, operation.body)
            requests_completed += 1
    finally:
        repository.close()
        server.stop()

    result.duration_seconds = time.perf_counter() - started
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--profile", default=None, help="Seed this profile into --root first.")
    parser.add_argument("--duration-seconds", type=float, default=1800.0)
    parser.add_argument("--interval-seconds", type=float, default=30.0)
    parser.add_argument("--ingest-visits-per-minute", type=float, default=6.0)
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

    result = run_soak(
        args.root,
        duration_seconds=args.duration_seconds,
        interval_seconds=args.interval_seconds,
        ingest_visits_per_minute=args.ingest_visits_per_minute,
    )
    payload = result.as_dict()
    payload["environment"] = _BENCHMARK["environment_report"]()
    text = json.dumps(payload, indent=2)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.json}", file=sys.stderr)

    print(f"\nsoak: {result.duration_seconds:.0f}s, {len(result.samples)} samples", file=sys.stderr)
    for name, trend in payload["trends"].items():
        print(f"  {name:16s} {trend}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
