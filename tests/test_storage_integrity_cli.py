from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from mockingbird.diagnostics import storage_integrity_cli
from mockingbird.repository.product_repository import ProductRepository


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ProductRepository:
    db = tmp_path / "data" / "mockingbird.sqlite3"
    media = tmp_path / "data" / "media" / "imports"
    monkeypatch.setenv("MOCKINGBIRD_HOME", str(tmp_path))
    monkeypatch.setenv("MOCKINGBIRD_DB_URL", f"sqlite:///{db}")
    monkeypatch.setenv("MOCKINGBIRD_MEDIA_ROOT", str(media))
    return ProductRepository(db_url=f"sqlite:///{db}", media_root=media)


def _orphan(repo: ProductRepository, name: str) -> Path:
    path = repo.media_root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")
    old = time.time() - 3 * 3600
    os.utime(path, (old, old))
    return path


def test_default_is_report_only_with_exit_codes(home: ProductRepository, capsys) -> None:
    assert storage_integrity_cli.run(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "clean"
    orphan = _orphan(home, "lost.jpg")
    assert storage_integrity_cli.run(["--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "orphans_found" and report["findings"][0]["relative_path"] == "lost.jpg"
    assert orphan.exists()  # a scan never moves anything


def test_quarantine_needs_yes_and_restore_round_trips(home: ProductRepository, capsys) -> None:
    orphan = _orphan(home, "lost.jpg")
    assert storage_integrity_cli.run(["--quarantine", "lost.jpg"]) == 3 and orphan.exists()
    capsys.readouterr()
    assert storage_integrity_cli.run(["--quarantine", "lost.jpg", "--yes", "--json"]) == 0
    batch = json.loads(capsys.readouterr().out)["batch_id"]
    assert not orphan.exists()
    assert storage_integrity_cli.run(["--restore", batch]) == 3 and not orphan.exists()
    assert storage_integrity_cli.run(["--restore", batch, "--yes"]) == 0 and orphan.exists()


def test_incomplete_check_has_its_own_exit_code(home: ProductRepository, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _orphan(home, "lost.jpg")
    monkeypatch.setenv("MOCKINGBIRD_DB_URL", f"sqlite:///{tmp_path / 'data' / 'missing-empty.sqlite3'}")
    assert storage_integrity_cli.run([]) == 2
