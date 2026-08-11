from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository

client = TestClient(app)

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


def import_image(
    *,
    filename: str = "feeder-bird.png",
    content: bytes = b"local image bytes",
    content_type: str = "image/png",
    data: dict[str, str] | None = None,
):
    return client.post(
        "/api/media/import",
        data={
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "title": "Imported feeder observation",
            "subject_label": "unknown_bird",
            "species_guess": "northern_cardinal",
            "notes": "Manual local import for review.",
            **(data or {}),
        },
        files={"file": (filename, content, content_type)},
    )


def test_media_import_accepts_supported_image_and_creates_product_records(media_root: Path) -> None:
    response = import_image()

    assert response.status_code == 201
    result = response.json()
    media_asset = result["media_asset"]
    event = result["event"]
    visit = result["visit"]

    assert media_asset["stream_id"] == STREAM_ID
    assert media_asset["content_type"] == "image/png"
    assert media_asset["media_type"] == "image"
    assert media_asset["file_size_bytes"] == len(b"local image bytes")
    assert Path(media_asset["local_path"]).is_file()
    assert str(media_asset["local_path"]).startswith(str(media_root))
    assert event["stream_id"] == STREAM_ID
    assert event["primary_zone_id"] == FEEDER_ZONE_ID
    assert event["review_status"] == "needs_review"
    assert visit["subject_label"] == "unknown_bird"
    assert visit["species_guess"] == "northern_cardinal"
    assert visit["review_status"] == "needs_review"
    assert visit["representative_media_path"] == media_asset["local_path"]
    assert result["review_queue_count"] >= 1


def test_imported_event_appears_in_review_queue() -> None:
    result = import_image().json()

    response = client.get("/api/review-queue")

    assert response.status_code == 200
    queue = response.json()
    imported_item = next(item for item in queue if item["visit_id"] == result["visit"]["id"])
    assert imported_item["media_asset"]["id"] == result["media_asset"]["id"]
    assert imported_item["media_asset"]["local_path"] == result["media_asset"]["local_path"]


def test_imported_media_is_visible_from_event_and_visit_detail() -> None:
    result = import_image().json()

    event_response = client.get(f"/api/events/{result['event']['id']}/detail")
    visit_response = client.get(f"/api/visits/{result['visit']['id']}/detail")

    assert event_response.status_code == 200
    assert visit_response.status_code == 200
    assert event_response.json()["media_asset"]["id"] == result["media_asset"]["id"]
    assert visit_response.json()["media_asset"]["id"] == result["media_asset"]["id"]


def test_imported_visit_can_be_corrected_and_exported() -> None:
    result = import_image().json()

    correction_response = client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": result["visit"]["id"],
            "label": "northern_cardinal",
            "notes": "Corrected imported local media.",
        },
    )
    export_response = client.post(
        "/api/dataset-exports",
        json={"name": "Imported reviewed media"},
    )

    assert correction_response.status_code == 201
    assert correction_response.json()["visit"]["reviewed_label"] == "northern_cardinal"
    assert export_response.status_code == 201
    records = export_response.json()["manifest"]["records"]
    assert any(
        record["visit_id"] == result["visit"]["id"]
        and record["label"] == "northern_cardinal"
        and record["media_path"] == result["media_asset"]["local_path"]
        for record in records
    )


def test_imported_media_is_listed_and_retrievable() -> None:
    result = import_image().json()
    media_id = result["media_asset"]["id"]

    list_response = client.get("/api/media")
    detail_response = client.get(f"/api/media/{media_id}")
    file_response = client.get(f"/api/media/{media_id}/file")

    assert list_response.status_code == 200
    assert any(asset["id"] == media_id for asset in list_response.json())
    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == media_id
    assert file_response.status_code == 200
    assert file_response.content == b"local image bytes"


def test_unsupported_content_type_returns_400() -> None:
    response = import_image(
        filename="notes.txt",
        content=b"not media",
        content_type="text/plain",
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported media content type."


def test_empty_file_returns_400() -> None:
    response = import_image(content=b"")

    assert response.status_code == 400
    assert response.json()["detail"] == "Imported media file is empty."


def test_unknown_stream_returns_404() -> None:
    response = import_image(data={"stream_id": "stream-missing"})

    assert response.status_code == 404
    assert "Stream" in response.json()["detail"]


def test_unknown_zone_returns_404() -> None:
    response = import_image(data={"zone_id": "zone-missing"})

    assert response.status_code == 404
    assert "Zone" in response.json()["detail"]


def test_local_data_status_counts_imported_media() -> None:
    import_image()

    response = client.get("/api/settings/local-data")

    assert response.status_code == 200
    assert response.json()["media_asset_count"] == 1


def test_reset_keeps_media_files_and_later_import_does_not_overwrite() -> None:
    first = import_image(content=b"first image bytes").json()["media_asset"]

    reset_response = client.post("/api/settings/reset-demo-data")
    second = import_image(content=b"second image bytes").json()["media_asset"]

    assert reset_response.status_code == 200
    assert first["local_path"] != second["local_path"]
    assert Path(first["local_path"]).read_bytes() == b"first image bytes"
    assert Path(second["local_path"]).read_bytes() == b"second image bytes"
