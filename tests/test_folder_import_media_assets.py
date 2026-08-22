from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import SourceKind, SourceStatus
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import CameraSourceModel, StreamModel, ZoneModel

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
IGNORE_ZONE_ID = "zone-ignore-driveway-edge"


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
    default_stream_id: str | None = None,
    default_zone_id: str | None = None,
) -> None:
    config: dict[str, str] = {}
    if folder is not None:
        config["folder_path"] = str(folder)
    if recursive is not None:
        config["recursive"] = recursive
    if allowed_extensions is not None:
        config["allowed_extensions"] = allowed_extensions
    if default_stream_id is not None:
        config["default_stream_id"] = default_stream_id
    if default_zone_id is not None:
        config["default_zone_id"] = default_zone_id
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


def write_file(path: Path, content: bytes = b"image bytes") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


async def import_folder(client: httpx.AsyncClient, payload: dict | None = None) -> httpx.Response:
    return await client.post(
        f"/api/sources/{SOURCE_ID}/folder-import",
        json=payload or {},
    )


async def media_by_id(client: httpx.AsyncClient) -> dict[str, dict]:
    response = await client.get("/api/media")
    assert response.status_code == 200
    return {item["id"]: item for item in response.json()}


async def test_unknown_source_folder_import_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/sources/source-missing/folder-import", json={})

    assert response.status_code == 404
    assert response.json()["detail"] == "Source 'source-missing' was not found."


async def test_non_folder_provider_folder_import_returns_400(client: httpx.AsyncClient) -> None:
    response = await import_folder(client)

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Folder import requires a folder_import_future Source provider."
    )


async def test_missing_folder_path_returns_400_without_scan(
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

    response = await import_folder(client)

    assert response.status_code == 400
    assert response.json()["detail"] == "Folder path metadata is required."


async def test_folder_import_creates_media_assets_only(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    tmp_path: Path,
) -> None:
    folder = tmp_path / "trailcam"
    source_files = {
        "bird.jpg": b"jay bytes",
        "feeder.png": b"feeder bytes",
        "night.webp": b"night bytes",
        "perch.jpeg": b"perch bytes",
    }
    for name, content in source_files.items():
        write_file(folder / name, content)
    write_file(folder / "clip.mp4", b"video bytes")
    write_file(folder / "nested" / "nested.jpg", b"nested bytes")
    await configure_folder_source(
        client,
        folder,
        allowed_extensions="jpg,jpeg,png,webp",
        default_stream_id=STREAM_ID,
        default_zone_id=FEEDER_ZONE_ID,
    )
    before = await product_counts(client)

    response = await import_folder(client, {"note": "SD-card batch 7"})

    assert response.status_code == 201
    result = response.json()
    assert result["source_id"] == SOURCE_ID
    assert result["provider_key"] == "folder_import_future"
    assert result["copy_mode"] == "copy_to_media_root"
    assert result["total_imported"] == 4
    assert result["creates_media_assets"] is True
    assert result["creates_motion_evidence"] is False
    assert result["creates_events"] is False
    assert result["creates_visits"] is False
    assert result["creates_truth"] is False
    assert str(folder) not in str(result)

    imported_paths = {item["relative_source_path"] for item in result["imported"]}
    assert imported_paths == set(source_files)
    skipped = {item["relative_path"]: item["reason"] for item in result["skipped"]}
    # v0.1 Acquisition/Ingest Interoperability Closure v1 ("II.9"): video
    # is now a recognized extension in general, just not enabled by this
    # request's own explicit `allowed_extensions=jpg,jpeg,png,webp`.
    assert skipped["clip.mp4"] == "extension_not_allowed"
    assert skipped["nested"] == "directory_skipped"

    media = await media_by_id(client)
    media_root = isolated_repository.media_root.resolve()
    for item in result["imported"]:
        asset = media[item["media_asset_id"]]
        local_path = Path(asset["local_path"])
        assert local_path.is_file()
        assert local_path.resolve().is_relative_to(media_root)
        assert local_path.read_bytes() == source_files[item["relative_source_path"]]
        assert asset["source_id"] == SOURCE_ID
        assert asset["stream_id"] == STREAM_ID
        assert asset["original_filename"] == item["file_name"]
        assert "provider_key=folder_import_future" in asset["notes"]
        assert f"relative_source_path={item['relative_source_path']}" in asset["notes"]
        assert str(folder) not in asset["notes"]

    assert all((folder / name).read_bytes() == content for name, content in source_files.items())
    after = await product_counts(client)
    assert after["media_assets"] == before["media_assets"] + 4
    assert after["events"] == before["events"]
    assert after["visits"] == before["visits"]
    assert after["review_labels"] == before["review_labels"]
    assert after["motion_evidence"] == before["motion_evidence"]
    assert after["species_suggestions"] == before["species_suggestions"]
    assert after["detection_proposals"] == before["detection_proposals"]
    assert after["dataset_exports"] == before["dataset_exports"]


async def test_relative_paths_imports_selected_files_only(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    folder = tmp_path / "trailcam"
    write_file(folder / "bird.jpg", b"bird bytes")
    write_file(folder / "feeder.png", b"feeder bytes")
    write_file(folder / "nested" / "inside.jpg", b"nested bytes")
    write_file(folder / "notes.txt", b"notes")
    await configure_folder_source(client, folder)

    response = await import_folder(
        client,
        {
            "relative_paths": [
                "nested/inside.jpg",
                "../outside.jpg",
                "notes.txt",
            ]
        },
    )

    assert response.status_code == 201
    result = response.json()
    assert {item["relative_source_path"] for item in result["imported"]} == {
        "nested/inside.jpg"
    }
    skipped = {item["reason"] for item in result["skipped"]}
    assert "unsafe_relative_path" in skipped
    assert "unsupported_extension" in skipped


async def test_default_non_recursive_and_recursive_depth_behavior(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    folder = tmp_path / "trailcam"
    write_file(folder / "root.jpg", b"root bytes")
    write_file(folder / "level-one" / "nested.png", b"nested bytes")
    write_file(folder / "level-one" / "too-deep" / "deep.jpg", b"deep bytes")
    await configure_folder_source(client, folder)

    default_response = await import_folder(client)
    recursive_response = await import_folder(
        client,
        {"recursive": True, "max_depth": 1, "relative_paths": None},
    )

    assert default_response.status_code == 201
    assert {item["relative_source_path"] for item in default_response.json()["imported"]} == {
        "root.jpg"
    }
    assert recursive_response.status_code == 201
    recursive = recursive_response.json()
    assert {item["relative_source_path"] for item in recursive["imported"]} == {
        "level-one/nested.png"
    }
    skipped = {item["relative_path"]: item["reason"] for item in recursive["skipped"]}
    assert skipped["root.jpg"] == "already_imported"
    assert skipped["level-one/too-deep"] == "max_depth_exceeded"


async def test_max_files_limits_folder_import(client: httpx.AsyncClient, tmp_path: Path) -> None:
    folder = tmp_path / "trailcam"
    for index in range(4):
        write_file(folder / f"image-{index}.jpg", f"image {index}".encode())
    await configure_folder_source(client, folder)

    response = await import_folder(client, {"max_files": 2})

    assert response.status_code == 201
    result = response.json()
    assert result["total_imported"] == 2
    assert any("truncated at 2" in warning for warning in result["warnings"])


async def test_duplicate_import_is_skipped(client: httpx.AsyncClient, tmp_path: Path) -> None:
    folder = tmp_path / "trailcam"
    write_file(folder / "bird.jpg", b"bird bytes")
    await configure_folder_source(client, folder)

    first = await import_folder(client)
    before_second = await product_counts(client)
    second = await import_folder(client)
    after_second = await product_counts(client)

    assert first.status_code == 201
    assert second.status_code == 201
    result = second.json()
    assert result["total_imported"] == 0
    assert result["skipped"][0]["reason"] == "already_imported"
    assert after_second["media_assets"] == before_second["media_assets"]


async def test_symlink_files_and_directories_are_skipped(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    folder = tmp_path / "trailcam"
    write_file(folder / "target.jpg", b"target bytes")
    target_dir = folder / "target-dir"
    target_dir.mkdir(parents=True)
    try:
        (folder / "linked.jpg").symlink_to(folder / "target.jpg")
        (folder / "linked-dir").symlink_to(target_dir, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"Symlinks are unavailable in this environment: {error}")
    await configure_folder_source(client, folder)

    response = await import_folder(client, {"recursive": True})

    assert response.status_code == 201
    result = response.json()
    assert {item["relative_source_path"] for item in result["imported"]} == {"target.jpg"}
    skipped = {item["relative_path"]: item["reason"] for item in result["skipped"]}
    assert skipped["linked.jpg"] == "symlink"
    assert skipped["linked-dir"] == "symlink"


async def test_invalid_folder_paths_are_rejected(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "not-a-folder.jpg"
    write_file(file_path)
    await configure_folder_source(client, file_path)

    non_directory = await import_folder(client)
    await configure_folder_source(client, tmp_path / "missing-folder")
    missing = await import_folder(client)

    assert non_directory.status_code == 400
    assert non_directory.json()["detail"] == "Configured folder must be a directory."
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Configured folder was not found."
    assert str(tmp_path / "missing-folder") not in str(missing.json())


def add_other_source(repository: ProductRepository) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id="source-other",
                    name="Other source",
                    kind=SourceKind.manual_upload.value,
                    status=SourceStatus.connected.value,
                    description="Other source.",
                )
            )
            session.add(
                StreamModel(
                    id="stream-other",
                    source_id="source-other",
                    name="Other stream",
                    description="Other stream.",
                    is_live=False,
                )
            )
            session.add(
                StreamModel(
                    id="stream-side-yard",
                    source_id=SOURCE_ID,
                    name="Side yard",
                    description="Second stream for zone mismatch checks.",
                    is_live=False,
                )
            )
            session.add(
                ZoneModel(
                    id="zone-side-yard",
                    stream_id="stream-side-yard",
                    name="Side yard zone",
                    zone_type="yard",
                    polygon_json="[]",
                    is_active=True,
                )
            )


async def test_stream_and_zone_validation(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    tmp_path: Path,
) -> None:
    folder = tmp_path / "trailcam"
    write_file(folder / "bird.jpg", b"bird bytes")
    add_other_source(isolated_repository)
    await configure_folder_source(client, folder)

    wrong_stream = await import_folder(client, {"default_stream_id": "stream-other"})
    wrong_zone = await import_folder(
        client,
        {"default_stream_id": STREAM_ID, "default_zone_id": "zone-side-yard"},
    )
    blocked_zone = await import_folder(
        client,
        {"default_stream_id": STREAM_ID, "default_zone_id": IGNORE_ZONE_ID},
    )

    assert wrong_stream.status_code == 400
    assert wrong_stream.json()["detail"] == (
        "Selected stream does not belong to the folder import Source."
    )
    assert wrong_zone.status_code == 400
    assert "Selected zone does not belong" in wrong_zone.json()["detail"]
    assert blocked_zone.status_code == 400
    assert blocked_zone.json()["detail"] == "Folder import cannot assign privacy or ignore zones."


async def test_folder_import_does_not_call_models_or_status_routes_scan(
    client: httpx.AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    folder = tmp_path / "trailcam"
    write_file(folder / "bird.jpg", b"bird bytes")
    await configure_folder_source(client, folder)

    def fail_model_call(*_args, **_kwargs):
        raise AssertionError("Folder import must not call model runtimes")

    monkeypatch.setattr(
        "mockingbird.repository.product_repository.get_local_detector_status",
        fail_model_call,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.get_megadetector_status",
        fail_model_call,
    )

    import_response = await import_folder(client)
    assert import_response.status_code == 201

    def fail_scan(*_args, **_kwargs):
        raise AssertionError("Status routes must not scan folders")

    monkeypatch.setattr(
        "mockingbird.source_providers.folder_import_preview.preview_folder_import",
        fail_scan,
    )
    responses = [
        await client.get(f"/api/sources/{SOURCE_ID}/provider-configuration"),
        await client.get(f"/api/sources/{SOURCE_ID}/connection"),
        await client.get(f"/api/sources/{SOURCE_ID}/setup-review"),
        await client.get(f"/api/streams/{STREAM_ID}/playback"),
    ]

    assert all(response.status_code == 200 for response in responses)
    assert all(str(folder) not in str(response.json()) for response in responses)
