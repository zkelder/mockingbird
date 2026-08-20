"""`python -m mockingbird doctor` CLI: argument parsing, rendering, exit codes.

Mirrors `test_single_app_runtime.py`'s existing convention for `--check`
(direct `run(argv)` calls asserting the returned int, no subprocess) --
see "CLI test conventions" in docs/mockingbird-doctor-operational-health-
contract.md for why this convention was chosen over `mockingbird_node`'s
subprocess-based one.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mockingbird.diagnostics import doctor_cli
from mockingbird.diagnostics.doctor import (
    DoctorCheckCode,
    DoctorCheckResult,
    DoctorOverallStatus,
    DoctorReport,
    DoctorStatus,
)
from mockingbird.repository.product_repository import ProductRepository


def _report(overall: DoctorOverallStatus, checks: list[DoctorCheckResult] | None = None) -> DoctorReport:
    return DoctorReport(
        overall_status=overall,
        generated_at=datetime.now(UTC),
        app_version="0.1.0",
        duration_ms=12.3,
        checks=checks or [],
    )


def test_run_healthy_report_exits_zero(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(doctor_cli, "run_doctor", lambda **_kwargs: _report(DoctorOverallStatus.HEALTHY))
    exit_code = doctor_cli.run([])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "MockingBird Doctor" in out
    assert "Overall: HEALTHY" in out


def test_run_degraded_report_exits_one(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(doctor_cli, "run_doctor", lambda **_kwargs: _report(DoctorOverallStatus.DEGRADED))
    exit_code = doctor_cli.run([])
    assert exit_code == 1
    assert "Overall: DEGRADED" in capsys.readouterr().out


def test_run_unhealthy_report_exits_two(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(doctor_cli, "run_doctor", lambda **_kwargs: _report(DoctorOverallStatus.UNHEALTHY))
    exit_code = doctor_cli.run([])
    assert exit_code == 2
    assert "Overall: UNHEALTHY" in capsys.readouterr().out


def test_run_json_flag_prints_valid_stable_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    checks = [
        DoctorCheckResult(
            code=DoctorCheckCode.SPECIES_IDENTIFICATION,
            component="Species identification",
            status=DoctorStatus.WARN,
            summary="BioCLIP runtime unavailable.",
            detail="Wildlife Visits can still be created; species suggestions are unavailable.",
        )
    ]
    monkeypatch.setattr(doctor_cli, "run_doctor", lambda **_kwargs: _report(DoctorOverallStatus.DEGRADED, checks))

    exit_code = doctor_cli.run(["--json"])

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["overall_status"] == "DEGRADED"
    assert payload["checks"][0]["status"] == "WARN"
    assert payload["checks"][0]["component"] == "Species identification"


def test_render_human_default_output_matches_the_calm_worked_example(monkeypatch: pytest.MonkeyPatch) -> None:
    """Matches the milestone's own worked CLI example: PASS lines are bare,
    WARN/FAIL lines get indented summary/detail/action underneath."""

    checks = [
        DoctorCheckResult(code=DoctorCheckCode.DATABASE_CONNECTIVITY, component="Database", status=DoctorStatus.PASS, summary="ok"),
        DoctorCheckResult(code=DoctorCheckCode.STORAGE, component="Storage", status=DoctorStatus.PASS, summary="ok"),
        DoctorCheckResult(code=DoctorCheckCode.CAMERA_NODE, component="Camera Node", status=DoctorStatus.PASS, summary="ok"),
        DoctorCheckResult(
            code=DoctorCheckCode.SPECIES_IDENTIFICATION,
            component="Species identification",
            status=DoctorStatus.WARN,
            summary="BioCLIP runtime unavailable.",
            detail="Wildlife detection can continue.",
        ),
    ]
    text = doctor_cli.render_human(_report(DoctorOverallStatus.DEGRADED, checks))
    lines = text.splitlines()

    assert "PASS    Database" in lines
    assert "PASS    Storage" in lines
    assert "PASS    Camera Node" in lines
    assert "WARN    Species identification" in lines
    warn_index = lines.index("WARN    Species identification")
    assert "BioCLIP runtime unavailable." in lines[warn_index + 1]
    assert lines[-2] == "Overall: DEGRADED"


def test_run_end_to_end_against_a_real_isolated_installation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """One real, non-monkeypatched pass through the full CLI -> run_doctor
    -> real SQLite database pipeline, proving the pieces are actually wired
    together correctly (not just each mock in isolation)."""

    data_dir = tmp_path / "data"
    media_root = data_dir / "media" / "imports"
    media_root.mkdir(parents=True)
    repository = ProductRepository(db_url=f"sqlite:///{data_dir / 'mockingbird.sqlite3'}", media_root=media_root)
    repository.close()
    monkeypatch.setenv("MOCKINGBIRD_HOME", str(tmp_path))

    exit_code = doctor_cli.run([])

    assert exit_code == 0
    assert "Overall: HEALTHY" in capsys.readouterr().out


def test_build_argument_parser_defaults() -> None:
    parser = doctor_cli.build_argument_parser()
    args = parser.parse_args([])
    assert args.json is False
    assert args.timeout is None


def test_build_argument_parser_accepts_json_and_timeout_flags() -> None:
    parser = doctor_cli.build_argument_parser()
    args = parser.parse_args(["--json", "--timeout", "2.5"])
    assert args.json is True
    assert args.timeout == 2.5
