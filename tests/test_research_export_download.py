"""Research export download: id-only, managed-root-confined, symlink-safe,
deterministic, authenticated (see docs/research-export-ecological-workflow-
completion-v1-contract.md, "Download")."""

from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.research.export_archive import (
    ExportArchiveNotFound,
    build_export_archive,
    resolve_export_directory,
)
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def export_root(tmp_path: Path) -> Path:
    root = tmp_path / "research_exports"
    root.mkdir()
    return root


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path, export_root: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
        research_export_root=export_root,
    )
    configure_repository(repository)
    yield repository
    configure_repository(None)


def _make_export(root: Path, name: str = "research-export-20260101T000000000000Z-abcd1234") -> Path:
    directory = root / name
    (directory / "media").mkdir(parents=True)
    (directory / "observations.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (directory / "media" / "m1.jpg").write_bytes(b"\xff\xd8photo")
    return directory


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


async def test_download_returns_a_zip_with_safe_relative_members(client: httpx.AsyncClient, export_root: Path) -> None:
    directory = _make_export(export_root)
    response = await client.get(f"/api/research/exports/{directory.name}/download")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert f"{directory.name}.zip" in response.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        names = archive.namelist()
        assert names == sorted(names)
        assert set(names) == {
            f"{directory.name}/media/m1.jpg", f"{directory.name}/observations.csv",
        }
        for name in names:
            assert not name.startswith("/") and ".." not in name.split("/")
            assert str(export_root) not in name
        assert archive.read(f"{directory.name}/media/m1.jpg") == b"\xff\xd8photo"


async def test_download_requires_sign_in(export_root: Path) -> None:
    directory = _make_export(export_root)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as anonymous:
        response = await anonymous.get(f"/api/research/exports/{directory.name}/download")
    assert response.status_code in (401, 403)
    assert b"observations" not in response.content


@pytest.mark.parametrize(
    "export_id",
    ["..", "../secret", "%2e%2e%2fsecret", "a/b", "a%2Fb", ".hidden", ".x.tmp", "nope", "x" * 300],
)
async def test_traversal_and_unknown_ids_are_not_found(
    client: httpx.AsyncClient, export_root: Path, tmp_path: Path, export_id: str
) -> None:
    (tmp_path / "secret").mkdir()
    (tmp_path / "secret" / "leak.txt").write_text("x")
    _make_export(export_root)
    response = await client.get(f"/api/research/exports/{export_id}/download")
    assert response.status_code in (404, 405)
    assert "leak" not in response.text


async def test_absolute_host_path_is_not_accepted(client: httpx.AsyncClient, export_root: Path) -> None:
    directory = _make_export(export_root)
    response = await client.get(f"/api/research/exports/{str(directory).replace('/', '%2F')}/download")
    assert response.status_code == 404


async def test_stale_export_is_a_clean_404_without_a_path(client: httpx.AsyncClient, export_root: Path) -> None:
    directory = _make_export(export_root)
    for child in sorted(directory.rglob("*"), reverse=True):
        child.unlink() if child.is_file() else child.rmdir()
    directory.rmdir()
    response = await client.get(f"/api/research/exports/{directory.name}/download")
    assert response.status_code == 404
    assert str(export_root) not in response.text


async def test_symlinked_export_directory_is_refused(
    client: httpx.AsyncClient, export_root: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    (export_root / "linked-export").symlink_to(outside, target_is_directory=True)
    response = await client.get("/api/research/exports/linked-export/download")
    assert response.status_code == 404


async def test_symlinked_members_are_never_archived(
    client: httpx.AsyncClient, export_root: Path, tmp_path: Path
) -> None:
    directory = _make_export(export_root)
    (tmp_path / "secret.txt").write_text("secret")
    os.symlink(tmp_path / "secret.txt", directory / "leak.txt")
    os.symlink(tmp_path, directory / "linkdir", target_is_directory=True)
    response = await client.get(f"/api/research/exports/{directory.name}/download")
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert not any("leak" in n or "linkdir" in n for n in archive.namelist())
        assert b"secret" not in response.content


def test_archive_bytes_are_deterministic(export_root: Path) -> None:
    directory = _make_export(export_root)
    first, _ = build_export_archive(export_root, directory.name)
    os.utime(directory / "observations.csv", (1, 1))
    second, _ = build_export_archive(export_root, directory.name)
    try:
        assert first.read_bytes() == second.read_bytes()
    finally:
        first.unlink()
        second.unlink()


def test_resolution_is_confined_to_the_root(export_root: Path, tmp_path: Path) -> None:
    (tmp_path / "sibling").mkdir()
    for bad in ("../sibling", "/etc", "sibling/..", ""):
        with pytest.raises(ExportArchiveNotFound):
            resolve_export_directory(export_root, bad)


async def test_temporary_archive_is_removed_after_response(client: httpx.AsyncClient, export_root: Path) -> None:
    import tempfile

    directory = _make_export(export_root)
    before = set(Path(tempfile.gettempdir()).glob("mockingbird-export-*.zip"))
    await client.get(f"/api/research/exports/{directory.name}/download")
    assert set(Path(tempfile.gettempdir()).glob("mockingbird-export-*.zip")) <= before
