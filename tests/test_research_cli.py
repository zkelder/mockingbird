"""Tests for `python -m mockingbird export-research`, `export-camtrap-dp`,
and `conservation-report` (`mockingbird.research.research_cli`). The real
eligibility/export/report behavior is already exercised thoroughly in
`tests/test_research_export_repository.py`; this file covers argument
parsing and real, non-monkeypatched end-to-end wiring -- mirroring
`tests/test_offline_ingest_cli.py`'s identical isolation approach via the
explicit `MOCKINGBIRD_DB_URL`/`MOCKINGBIRD_MEDIA_ROOT` env vars
`ProductRepository()`'s own default-resolution path already respects (never
the real default database). Every end-to-end invocation here uses
`--dry-run` so it never depends on (or pollutes) a relative `data/
research_exports` directory."""

from __future__ import annotations

from pathlib import Path

import pytest

from mockingbird.research import research_cli


@pytest.fixture(autouse=True)
def isolated_database_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCKINGBIRD_DB_URL", f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}")
    monkeypatch.setenv("MOCKINGBIRD_MEDIA_ROOT", str(tmp_path / "media"))


def test_filters_from_args_round_trip() -> None:
    parser_args = research_cli._add_filter_arguments
    import argparse

    parser = argparse.ArgumentParser()
    parser_args(parser)
    args = parser.parse_args(
        [
            "--start-at", "2026-08-01T00:00:00Z", "--end-at", "2026-08-08T00:00:00Z",
            "--stream-id", "stream-a", "--stream-id", "stream-b",
            "--taxon", "northern_cardinal", "--acquisition-scope", "offline",
            "--collection-id", "research-collection-001",
        ]
    )
    filters = research_cli._filters_from_args(args)
    assert filters.stream_ids == ["stream-a", "stream-b"]
    assert filters.taxon_labels == ["northern_cardinal"]
    assert filters.acquisition_scope == "offline"
    assert filters.collection_id == "research-collection-001"


def test_export_research_dry_run_end_to_end(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = research_cli.run_export_research(["--dry-run", "--json"])
    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"dry_run": true' in output
    assert '"schema_version": "research-export-v1"' in output


def test_export_camtrap_dp_dry_run_end_to_end(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = research_cli.run_export_camtrap_dp(["--dry-run"])
    assert exit_code == 0
    output = capsys.readouterr().out
    assert "profile_version: 1.0.2" in output
    assert "validation: valid=True" in output


def test_export_camtrap_dp_accepts_explicit_site_override() -> None:
    exit_code = research_cli.run_export_camtrap_dp(
        ["--dry-run", "--site-name", "Test Yard", "--latitude", "40.0", "--longitude", "-105.0"]
    )
    assert exit_code == 0


def test_export_darwin_core_dry_run_end_to_end(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = research_cli.run_export_darwin_core(["--dry-run", "--json"])
    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"dry_run": true' in output
    assert '"schema_version": "darwin-core-archive-v1"' in output


def test_export_darwin_core_accepts_explicit_site_override() -> None:
    exit_code = research_cli.run_export_darwin_core(
        ["--dry-run", "--site-name", "Test Yard", "--latitude", "40.0", "--longitude", "-105.0"]
    )
    assert exit_code == 0


def test_conservation_report_end_to_end(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = research_cli.run_conservation_report(
        ["--start-at", "2026-08-01T00:00:00Z", "--end-at", "2026-08-08T00:00:00Z"]
    )
    assert exit_code == 0
    output = capsys.readouterr().out
    assert "maturity:" in output
    assert "population" not in output.lower()
    assert "abundance" not in output.lower()


def test_conservation_report_json_output_is_well_formed(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = research_cli.run_conservation_report(
        ["--start-at", "2026-08-01T00:00:00Z", "--end-at", "2026-08-08T00:00:00Z", "--json"]
    )
    assert exit_code == 0
    import json

    payload = json.loads(capsys.readouterr().out)
    assert "maturity" in payload
    assert "confirmed_species" in payload
