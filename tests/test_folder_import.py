from pathlib import Path

import pytest
from tests.conftest import LegacyAuthenticatedSyncTestClient

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository

client = LegacyAuthenticatedSyncTestClient(app)

STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> None:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    yield
    configure_repository(None)


@pytest.fixture
def media_root(tmp_path: Path) -> Path:
    return tmp_path / "media"


@pytest.fixture
def import_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "yard-media"
    folder.mkdir()
    (folder / "feeder-cardinal.jpg").write_bytes(b"cardinal image bytes")
    (folder / "birdbath-bluejay.png").write_bytes(b"bluejay image bytes")
    (folder / "notes.txt").write_text("not media")
    (folder / "empty.webp").write_bytes(b"")
    (folder / "nested").mkdir()
    return folder


def preview_folder(folder: Path):
    return client.post("/api/media/folder-preview", json={"folder_path": str(folder)})


def import_folder_media(folder: Path, data: dict[str, object] | None = None):
    return client.post(
        "/api/media/folder-import",
        json={
            "folder_path": str(folder),
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "subject_label": "unknown_bird",
            "species_guess": "unknown_bird",
            "notes": "Local folder import for review.",
            **(data or {}),
        },
    )


def test_folder_preview_returns_supported_and_skipped_files(import_folder: Path) -> None:
    response = preview_folder(import_folder)

    assert response.status_code == 200
    preview = response.json()
    assert preview["supported_count"] == 2
    assert [candidate["filename"] for candidate in preview["supported_files"]] == [
        "birdbath-bluejay.png",
        "feeder-cardinal.jpg",
    ]
    skipped = {item["filename"]: item["reason"] for item in preview["skipped_files"]}
    assert skipped["notes.txt"] == "unsupported_content_type"
    assert skipped["empty.webp"] == "empty_file"
    assert skipped["nested"] == "not_file"


def test_folder_import_creates_product_records_and_copies_media(
    import_folder: Path,
    media_root: Path,
) -> None:
    source_file = import_folder / "feeder-cardinal.jpg"
    original_bytes = source_file.read_bytes()

    response = import_folder_media(import_folder)

    assert response.status_code == 201
    result = response.json()
    assert result["imported_count"] == 2
    assert result["skipped_count"] == 3
    assert len(result["media_assets"]) == 2
    assert len(result["events"]) == 2
    assert len(result["visits"]) == 2
    assert all(event["review_status"] == "needs_review" for event in result["events"])
    assert all(visit["review_status"] == "needs_review" for visit in result["visits"])
    assert all(event["primary_zone_id"] == FEEDER_ZONE_ID for event in result["events"])
    assert source_file.read_bytes() == original_bytes
    assert all(Path(asset["local_path"]).is_file() for asset in result["media_assets"])
    assert all(str(asset["local_path"]).startswith(str(media_root)) for asset in result["media_assets"])
    assert all(asset["local_path"] != str(import_folder / asset["original_filename"]) for asset in result["media_assets"])


def test_folder_import_limit_imports_first_supported_file(import_folder: Path) -> None:
    response = import_folder_media(import_folder, {"limit": 1})

    assert response.status_code == 201
    result = response.json()
    assert result["imported_count"] == 1
    assert result["media_assets"][0]["original_filename"] == "birdbath-bluejay.png"


def test_folder_imported_visits_flow_through_review_and_export(import_folder: Path) -> None:
    result = import_folder_media(import_folder).json()
    visit = result["visits"][0]
    media_asset = result["media_assets"][0]

    queue_response = client.get("/api/review-queue")
    correction_response = client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": visit["id"],
            "label": "blue_jay",
            "notes": "Corrected folder-imported media.",
        },
    )
    export_response = client.post(
        "/api/dataset-exports",
        json={"name": "Folder imported reviewed media"},
    )
    local_data_response = client.get("/api/settings/local-data")

    assert queue_response.status_code == 200
    queue = queue_response.json()
    queue_item = next(item for item in queue if item["visit_id"] == visit["id"])
    assert queue_item["media_asset"]["id"] == media_asset["id"]
    assert correction_response.status_code == 201
    assert correction_response.json()["visit"]["reviewed_label"] == "blue_jay"
    assert export_response.status_code == 201
    records = export_response.json()["manifest"]["records"]
    assert any(
        record["visit_id"] == visit["id"]
        and record["label"] == "blue_jay"
        and record["media_path"] == media_asset["local_path"]
        for record in records
    )
    assert local_data_response.status_code == 200
    assert local_data_response.json()["media_asset_count"] == 2


def test_folder_import_rejects_unknown_folder_path(tmp_path: Path) -> None:
    response = import_folder_media(tmp_path / "missing-folder")

    assert response.status_code == 404
    assert response.json()["detail"] == "Folder was not found."


def test_folder_import_rejects_file_path(tmp_path: Path) -> None:
    file_path = tmp_path / "not-a-folder.jpg"
    file_path.write_bytes(b"image bytes")

    response = import_folder_media(file_path)

    assert response.status_code == 400
    assert response.json()["detail"] == "Folder path must be a directory."


def test_folder_import_rejects_unknown_stream(import_folder: Path) -> None:
    response = import_folder_media(import_folder, {"stream_id": "stream-missing"})

    assert response.status_code == 404
    assert "Stream" in response.json()["detail"]


def test_folder_import_rejects_unknown_zone(import_folder: Path) -> None:
    response = import_folder_media(import_folder, {"zone_id": "zone-missing"})

    assert response.status_code == 404
    assert "Zone" in response.json()["detail"]


def test_folder_import_with_no_supported_media_returns_zero_imports(tmp_path: Path) -> None:
    folder = tmp_path / "unsupported"
    folder.mkdir()
    (folder / "notes.txt").write_text("not media")

    response = import_folder_media(folder)

    assert response.status_code == 201
    result = response.json()
    assert result["imported_count"] == 0
    assert result["skipped_count"] == 1
    assert result["skipped_files"][0]["reason"] == "unsupported_content_type"
