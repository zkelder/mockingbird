"""Support bundle: contract, redaction, and real-database acceptance tests
(First-Hour Onboarding + Whole-Product Observability Closure v1, "B11").

Mirrors `tests/test_doctor.py`'s own `_initialized_runtime_home` real,
isolated `tmp_path`-backed database convention -- no mocking of the
database layer itself.
"""

from __future__ import annotations

import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mockingbird.diagnostics.support_bundle import (
    default_output_path,
    read_bundle_member_json,
    write_support_bundle,
)
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.runtime_state import LOG_FILENAME, LOG_SUBDIRECTORY

_FORBIDDEN_SUBSTRINGS = ("credential", "bearer", "password", "api_key", "secret", "token")


def _initialized_runtime_home(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    media_root = data_dir / "media" / "imports"
    media_root.mkdir(parents=True)
    db_path = data_dir / "mockingbird.sqlite3"
    repository = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)
    repository.close()
    return tmp_path


def test_write_support_bundle_produces_a_real_zip_with_expected_members(tmp_path: Path) -> None:
    runtime_home = _initialized_runtime_home(tmp_path)
    output_path = tmp_path / "bundle.zip"

    written = write_support_bundle(output_path, runtime_home=runtime_home)

    assert written == output_path
    assert output_path.is_file()
    with zipfile.ZipFile(output_path) as bundle:
        names = set(bundle.namelist())
    assert names == {"manifest.json", "doctor_report.json", "sources.json", "log_tail.txt"}


def test_bundle_manifest_carries_stable_version_facts(tmp_path: Path) -> None:
    runtime_home = _initialized_runtime_home(tmp_path)
    output_path = tmp_path / "bundle.zip"
    write_support_bundle(output_path, runtime_home=runtime_home)

    manifest = read_bundle_member_json(output_path, "manifest.json")
    assert manifest["research_export_schema_version"] == "research-export-v1"
    assert manifest["camtrap_dp_profile_version"] == "1.0.2"
    assert manifest["app_version"]


def test_bundle_sources_are_structural_only_never_provider_configuration(tmp_path: Path) -> None:
    """See the module's "Known v1 scope limits": Source entries carry only
    id/name/kind/status -- never a URL, address, or credential field."""

    from mockingbird.storage.models import CameraSourceModel

    runtime_home = _initialized_runtime_home(tmp_path)
    repository = ProductRepository(
        db_url=f"sqlite:///{runtime_home / 'data' / 'mockingbird.sqlite3'}",
        media_root=runtime_home / "data" / "media" / "imports",
    )
    try:
        with repository.session_factory() as session, session.begin():
            session.add(
                CameraSourceModel(
                    id="source-real",
                    name="Backyard camera",
                    kind="integration",
                    status="connected",
                    description="Real paired Camera Node fixture.",
                    camera_node_service_version="1.4.0",
                )
            )
    finally:
        repository.close()

    output_path = tmp_path / "bundle.zip"
    write_support_bundle(output_path, runtime_home=runtime_home)

    sources = read_bundle_member_json(output_path, "sources.json")
    # A fresh ProductRepository auto-seeds one demo Source (`seed_if_empty`)
    # alongside the one added here -- assert on the real one specifically.
    real_source = next(source for source in sources if source["id"] == "source-real")
    assert set(real_source.keys()) == {"id", "name", "kind", "status"}
    assert real_source["kind"] == "integration"


def test_bundle_never_includes_credential_shaped_text_anywhere(tmp_path: Path) -> None:
    """Mirrors the exact precedent test in test_doctor.py/test_product_health.py."""

    runtime_home = _initialized_runtime_home(tmp_path)
    log_dir = runtime_home / LOG_SUBDIRECTORY
    log_dir.mkdir(parents=True)
    (log_dir / LOG_FILENAME).write_text(
        "INFO ordinary startup line\n"
        "WARNING pairing failed: credential rejected for node 192.168.1.50\n"
        "INFO another ordinary line\n",
        encoding="utf-8",
    )

    output_path = tmp_path / "bundle.zip"
    write_support_bundle(output_path, runtime_home=runtime_home)

    with zipfile.ZipFile(output_path) as bundle:
        full_text = "".join(bundle.read(name).decode("utf-8", errors="replace") for name in bundle.namelist()).lower()

    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in full_text, f"found forbidden substring {forbidden!r} in bundle"
    # The redaction was real, not a coincidence of no matching lines existing:
    with zipfile.ZipFile(output_path) as bundle:
        log_tail = bundle.read("log_tail.txt").decode("utf-8")
    assert "[line omitted" in log_tail
    assert "ordinary startup line" in log_tail
    manifest = read_bundle_member_json(output_path, "manifest.json")
    assert manifest["log_tail_redacted_line_count"] == 1


def test_bundle_log_tail_is_bounded_and_reports_truncation(tmp_path: Path) -> None:
    runtime_home = _initialized_runtime_home(tmp_path)
    log_dir = runtime_home / LOG_SUBDIRECTORY
    log_dir.mkdir(parents=True)
    (log_dir / LOG_FILENAME).write_text("\n".join(f"line {i}" for i in range(1000)), encoding="utf-8")

    output_path = tmp_path / "bundle.zip"
    write_support_bundle(output_path, runtime_home=runtime_home, log_tail_lines=50)

    manifest = read_bundle_member_json(output_path, "manifest.json")
    assert manifest["log_tail_lines_included"] == 50
    assert manifest["log_tail_truncated"] is True
    with zipfile.ZipFile(output_path) as bundle:
        log_tail = bundle.read("log_tail.txt").decode("utf-8")
    # Only the most recent lines are kept.
    assert "line 999" in log_tail
    assert "line 0" not in log_tail.split("\n")


def test_bundle_with_no_log_file_yet_is_not_an_error(tmp_path: Path) -> None:
    runtime_home = _initialized_runtime_home(tmp_path)
    output_path = tmp_path / "bundle.zip"

    write_support_bundle(output_path, runtime_home=runtime_home)  # must not raise

    manifest = read_bundle_member_json(output_path, "manifest.json")
    assert manifest["log_tail_lines_included"] == 0


def test_default_output_path_is_timestamped_and_under_the_data_folder(tmp_path: Path) -> None:
    runtime_home = _initialized_runtime_home(tmp_path)
    now = datetime(2026, 8, 22, 12, 30, 0, tzinfo=UTC)

    path = default_output_path(runtime_home=runtime_home, now=now)

    assert path.parent == runtime_home / "data"
    assert path.name == "mockingbird-support-bundle-20260822T123000Z.zip"


def test_support_bundle_cli_writes_a_real_bundle_and_prints_its_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """One real, non-monkeypatched pass through the full CLI -> write_
    support_bundle -> real SQLite database pipeline, mirroring test_doctor_
    cli.py's own `MOCKINGBIRD_HOME`-isolated end-to-end convention exactly
    -- this must never touch the real, persistent development database."""

    from mockingbird.diagnostics import support_bundle_cli

    _initialized_runtime_home(tmp_path)
    monkeypatch.setenv("MOCKINGBIRD_HOME", str(tmp_path))
    output_path = tmp_path / "cli-bundle.zip"

    exit_code = support_bundle_cli.run(["--output", str(output_path)])

    assert exit_code == 0
    assert output_path.is_file()
    captured = capsys.readouterr()
    assert str(output_path) in captured.out
    assert "safe to share" in captured.out
