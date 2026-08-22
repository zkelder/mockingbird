from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    yield repository
    configure_repository(None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


async def configure_folder_source(
    client: httpx.AsyncClient,
    folder: Path | str | None,
    *,
    recursive: str | None = None,
    allowed_extensions: str | None = None,
) -> None:
    config: dict[str, str] = {}
    if folder is not None:
        config["folder_path"] = str(folder)
    if recursive is not None:
        config["recursive"] = recursive
    if allowed_extensions is not None:
        config["allowed_extensions"] = allowed_extensions
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "folder_import_future", "config": config},
    )
    assert response.status_code == 200


async def product_counts(client: httpx.AsyncClient) -> dict[str, int]:
    responses = {
        "events": await client.get("/api/events"),
        "visits": await client.get("/api/visits"),
        "review_labels": await client.get("/api/review-labels"),
        "media_assets": await client.get("/api/media"),
        "motion_evidence": await client.get("/api/motion/evidence"),
        "species_suggestions": await client.get("/api/species-suggestions"),
        "detection_proposals": await client.get("/api/detection-proposals"),
        "dataset_exports": await client.get("/api/dataset-exports"),
    }
    assert all(response.status_code == 200 for response in responses.values())
    return {
        "events": len(responses["events"].json()),
        "visits": len(responses["visits"].json()),
        "review_labels": len(responses["review_labels"].json()),
        "media_assets": len(responses["media_assets"].json()),
        "motion_evidence": len(responses["motion_evidence"].json()["motion_evidence"]),
        "species_suggestions": len(responses["species_suggestions"].json()["species_suggestions"]),
        "detection_proposals": len(responses["detection_proposals"].json()),
        "dataset_exports": len(responses["dataset_exports"].json()),
    }


def touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


async def test_unknown_source_folder_preview_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/sources/source-missing/folder-import/preview", json={})

    assert response.status_code == 404
    assert response.json()["detail"] == "Source 'source-missing' was not found."


async def test_non_folder_provider_preview_returns_400(client: httpx.AsyncClient) -> None:
    response = await client.post(f"/api/sources/{SOURCE_ID}/folder-import/preview", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Folder import preview requires a folder_import_future Source provider."
    )


async def test_missing_folder_path_returns_not_configured_without_scan(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_folder_source(client, None)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("Missing folder metadata must not scan")

    monkeypatch.setattr(
        "mockingbird.source_providers.folder_import_preview.preview_folder_import",
        fail_if_called,
    )

    response = await client.post(f"/api/sources/{SOURCE_ID}/folder-import/preview", json={})

    assert response.status_code == 200
    preview = response.json()
    assert preview["folder_configured"] is False
    assert preview["dry_run"] is True
    assert preview["creates_media_assets"] is False
    assert preview["creates_events"] is False
    assert preview["creates_visits"] is False
    assert preview["creates_truth"] is False
    assert preview["candidates"] == []
    assert preview["skipped"] == []
    assert "Folder path metadata is not configured" in preview["warnings"][0]


async def test_configured_folder_preview_reports_candidates_and_skips(
    client: httpx.AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = tmp_path / "trailcam"
    for name in ("bird.jpg", "jay.JPEG", "feeder.png", "night.webp"):
        touch(folder / name)
    for name in ("clip.mp4", "movie.mov", "camera.avi", "image.heic", "raw.cr2", "data.zip", "noext"):
        touch(folder / name)
    touch(folder / "nested" / "inside.jpg")
    await configure_folder_source(client, folder, allowed_extensions="jpg,jpeg,png,webp")
    before = await product_counts(client)

    def fail_if_media_opened(*_args, **_kwargs):
        raise AssertionError("Folder preview must not open media contents")

    monkeypatch.setattr(Path, "read_bytes", fail_if_media_opened)

    response = await client.post(f"/api/sources/{SOURCE_ID}/folder-import/preview", json={})

    assert response.status_code == 200
    preview = response.json()
    assert preview["source_id"] == SOURCE_ID
    assert preview["provider_key"] == "folder_import_future"
    assert preview["folder_configured"] is True
    assert preview["recursive"] is False
    assert preview["allowed_extensions"] == [".jpg", ".jpeg", ".png", ".webp"]
    assert preview["dry_run"] is True
    assert preview["creates_media_assets"] is False
    assert preview["creates_events"] is False
    assert preview["creates_visits"] is False
    assert preview["creates_truth"] is False
    assert preview["total_known_bytes"] == 0

    candidate_paths = {candidate["relative_path"] for candidate in preview["candidates"]}
    assert candidate_paths == {"bird.jpg", "feeder.png", "jay.JPEG", "night.webp"}
    assert all(not path.startswith("/") for path in candidate_paths)
    assert all(".." not in Path(path).parts for path in candidate_paths)
    assert str(folder) not in str(preview)

    skipped_reasons = {item["relative_path"]: item["reason"] for item in preview["skipped"]}
    # v0.1 Acquisition/Ingest Interoperability Closure v1 ("II.9"): video
    # extensions are now recognized/supported by the system in general
    # (see test_video_extensions_are_recognized_candidates_when_explicitly_
    # allowed below) -- this request's own explicit `allowed_extensions`
    # just does not enable them, the more precise "not allowed for this
    # request" reason, distinct from "the system has no support at all."
    assert skipped_reasons["clip.mp4"] == "extension_not_allowed"
    assert skipped_reasons["movie.mov"] == "extension_not_allowed"
    assert skipped_reasons["camera.avi"] == "extension_not_allowed"
    assert skipped_reasons["image.heic"] == "unsupported_extension"
    assert skipped_reasons["raw.cr2"] == "unsupported_extension"
    assert skipped_reasons["data.zip"] == "unsupported_extension"
    assert skipped_reasons["noext"] == "unsupported_extension"
    assert skipped_reasons["nested"] == "directory_skipped"
    assert await product_counts(client) == before


async def test_video_extensions_are_recognized_candidates_when_explicitly_allowed(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    # v0.1 Acquisition/Ingest Interoperability Closure v1 ("II.9 Camera-
    # trap / media ingest"): video files enter the same folder-import
    # preview contract as images -- opt-in only (existing callers that
    # never ask for video extensions keep their current image-only
    # behavior; see the default-`allowed_extensions` scenario above).
    folder = tmp_path / "trailcam"
    touch(folder / "bird.jpg")
    touch(folder / "clip.mp4")
    touch(folder / "movie.mov")
    await configure_folder_source(client, folder, allowed_extensions="jpg,mp4,mov")

    response = await client.post(f"/api/sources/{SOURCE_ID}/folder-import/preview", json={})

    assert response.status_code == 200
    preview = response.json()
    assert preview["allowed_extensions"] == [".jpg", ".mp4", ".mov"]
    candidates_by_path = {c["relative_path"]: c for c in preview["candidates"]}
    assert candidates_by_path["bird.jpg"]["planned_media_kind"] == "image"
    assert candidates_by_path["clip.mp4"]["planned_media_kind"] == "video"
    assert candidates_by_path["movie.mov"]["planned_media_kind"] == "video"
    assert preview["skipped"] == []


async def test_recursive_preview_scans_to_max_depth_and_skips_deeper_dirs(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    folder = tmp_path / "trailcam"
    touch(folder / "root.jpg")
    touch(folder / "level-one" / "nested.png")
    touch(folder / "level-one" / "too-deep" / "deep.jpg")
    await configure_folder_source(client, folder)

    response = await client.post(
        f"/api/sources/{SOURCE_ID}/folder-import/preview",
        json={"recursive": True, "max_depth": 1},
    )

    assert response.status_code == 200
    preview = response.json()
    candidate_paths = {candidate["relative_path"] for candidate in preview["candidates"]}
    assert candidate_paths == {"root.jpg", "level-one/nested.png"}
    skipped = {item["relative_path"]: item["reason"] for item in preview["skipped"]}
    assert skipped["level-one/too-deep"] == "max_depth_exceeded"


async def test_request_overrides_config_extensions_and_recursive(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    folder = tmp_path / "trailcam"
    touch(folder / "root.jpg")
    touch(folder / "root.png")
    touch(folder / "nested" / "nested.jpg")
    await configure_folder_source(
        client,
        folder,
        recursive="false",
        allowed_extensions="jpg,jpeg,png,webp",
    )

    response = await client.post(
        f"/api/sources/{SOURCE_ID}/folder-import/preview",
        json={"recursive": True, "allowed_extensions": ["png"], "max_depth": 1},
    )

    assert response.status_code == 200
    preview = response.json()
    assert preview["recursive"] is True
    assert preview["allowed_extensions"] == [".png"]
    candidate_paths = {candidate["relative_path"] for candidate in preview["candidates"]}
    assert candidate_paths == {"root.png"}
    skipped = {item["relative_path"]: item["reason"] for item in preview["skipped"]}
    assert skipped["root.jpg"] == "extension_not_allowed"
    assert skipped["nested/nested.jpg"] == "extension_not_allowed"


async def test_symlink_files_and_directories_are_skipped(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    folder = tmp_path / "trailcam"
    touch(folder / "target.jpg")
    target_dir = folder / "target-dir"
    target_dir.mkdir(parents=True)
    try:
        (folder / "linked.jpg").symlink_to(folder / "target.jpg")
        (folder / "linked-dir").symlink_to(target_dir, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"Symlinks are unavailable in this environment: {error}")
    await configure_folder_source(client, folder)

    response = await client.post(
        f"/api/sources/{SOURCE_ID}/folder-import/preview",
        json={"recursive": True},
    )

    assert response.status_code == 200
    preview = response.json()
    candidate_paths = {candidate["relative_path"] for candidate in preview["candidates"]}
    assert candidate_paths == {"target.jpg"}
    skipped = {item["relative_path"]: item["reason"] for item in preview["skipped"]}
    assert skipped["linked.jpg"] == "symlink"
    assert skipped["linked-dir"] == "symlink"


async def test_non_directory_folder_preview_is_rejected(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "not-a-folder.jpg"
    touch(file_path)
    await configure_folder_source(client, file_path)

    response = await client.post(f"/api/sources/{SOURCE_ID}/folder-import/preview", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "Configured folder must be a directory."


async def test_missing_folder_preview_is_rejected_safely(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    missing_folder = tmp_path / "missing-folder"
    await configure_folder_source(client, missing_folder)

    response = await client.post(f"/api/sources/{SOURCE_ID}/folder-import/preview", json={})

    assert response.status_code == 404
    assert response.json()["detail"] == "Configured folder was not found."
    assert str(missing_folder) not in str(response.json())


async def test_symlink_folder_preview_is_rejected(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    real_folder = tmp_path / "real"
    real_folder.mkdir()
    link_folder = tmp_path / "linked"
    try:
        link_folder.symlink_to(real_folder, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"Symlinks are unavailable in this environment: {error}")
    await configure_folder_source(client, link_folder)

    response = await client.post(f"/api/sources/{SOURCE_ID}/folder-import/preview", json={})

    assert response.status_code == 400
    assert response.json()["detail"] == "Configured folder must not be a symlink."


async def test_max_files_truncates_candidates_with_warning(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    folder = tmp_path / "trailcam"
    for index in range(4):
        touch(folder / f"image-{index}.jpg")
    await configure_folder_source(client, folder)

    response = await client.post(
        f"/api/sources/{SOURCE_ID}/folder-import/preview",
        json={"max_files": 2},
    )

    assert response.status_code == 200
    preview = response.json()
    assert preview["total_candidates"] == 2
    assert any("truncated at 2" in warning for warning in preview["warnings"])


async def test_status_routes_do_not_scan_folder_or_call_models(
    client: httpx.AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = tmp_path / "trailcam"
    folder.mkdir()
    await configure_folder_source(client, folder)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("Status routes must not scan folders or call model runtimes")

    monkeypatch.setattr(
        "mockingbird.source_providers.folder_import_preview.preview_folder_import",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.get_local_detector_status",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.get_megadetector_status",
        fail_if_called,
    )

    responses = [
        await client.get(f"/api/sources/{SOURCE_ID}/provider-configuration"),
        await client.get(f"/api/sources/{SOURCE_ID}/connection"),
        await client.get(f"/api/sources/{SOURCE_ID}/setup-review"),
        await client.get(f"/api/streams/{STREAM_ID}/playback"),
    ]

    assert all(response.status_code == 200 for response in responses)
    assert all(str(folder) not in str(response.json()) for response in responses)
