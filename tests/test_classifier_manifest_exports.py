from pathlib import Path
import csv
import json

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> Path:
    export_root = tmp_path / "classifier_manifest_exports"
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
        classifier_manifest_export_root=export_root,
    )
    configure_repository(repository)
    yield export_root
    configure_repository(None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


async def classifier_manifest(client: httpx.AsyncClient) -> dict:
    response = await client.get("/api/classifier-training-manifest")
    assert response.status_code == 200
    return response.json()


async def create_reviewed_bird_example(
    client: httpx.AsyncClient,
    *,
    label: str = "Northern Cardinal",
    filename: str = "classifier-export-bird.png",
) -> dict:
    import_response = await client.post(
        "/api/media/import",
        data={
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "title": "Classifier export bird",
            "subject_label": "unknown_bird",
            "species_guess": "unknown_bird",
            "notes": "Tiny local media for classifier manifest export tests.",
        },
        files={"file": (filename, b"classifier manifest export image", "image/png")},
    )
    assert import_response.status_code == 201
    imported = import_response.json()

    correction_response = await client.post(
        "/api/review-labels",
        json={
            "target_type": "visit",
            "target_id": imported["visit"]["id"],
            "label": label,
            "notes": "Classifier export correction truth.",
            "review_origin": "human",
        },
    )
    assert correction_response.status_code == 201
    return imported


async def local_truth_snapshot(client: httpx.AsyncClient) -> dict:
    responses = {
        "events": await client.get("/api/events"),
        "visits": await client.get("/api/visits"),
        "review_labels": await client.get("/api/review-labels"),
        "exports": await client.get("/api/dataset-exports"),
        "coverage": await client.get("/api/dataset-coverage/summary"),
    }
    for response in responses.values():
        assert response.status_code == 200

    coverage = responses["coverage"].json()
    visits = responses["visits"].json()
    return {
        "events": len(responses["events"].json()),
        "visits": len(visits),
        "review_labels": len(responses["review_labels"].json()),
        "exports": len(responses["exports"].json()),
        "reviewed_visits": sum(visit["review_status"] == "reviewed" for visit in visits),
        "reviewed_record_count": coverage["reviewed_record_count"],
        "export_ready_count": coverage["export_ready_count"],
    }


def read_jsonl(path: Path) -> list[dict]:
    if path.read_text(encoding="utf-8") == "":
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def export_file_names(export_dir: Path) -> set[str]:
    return {path.name for path in export_dir.iterdir() if path.is_file()}


async def test_classifier_manifest_export_dry_run_plans_files_without_writing(
    client: httpx.AsyncClient,
    isolated_repository: Path,
) -> None:
    await create_reviewed_bird_example(client)
    preview = await classifier_manifest(client)
    truth_before = await local_truth_snapshot(client)

    response = await client.post(
        "/api/classifier-training-manifest/exports",
        json={"dry_run": True, "include_csv": True, "output_name": "dry-run-preview"},
    )

    assert response.status_code == 201
    export = response.json()
    assert export["dry_run"] is True
    assert export["output_directory"] is None
    assert export["examples"] == len(preview["examples"])
    assert export["skipped"] == len(preview["skipped_records"])
    assert {file["name"] for file in export["files"]} == {
        "manifest.jsonl",
        "taxonomy.json",
        "skipped_records.jsonl",
        "summary.json",
        "manifest.csv",
    }
    assert all(file["size_bytes"] is None for file in export["files"])
    assert export["media_policy"] == "reference_only"
    assert export["planned_media_files"] == []
    assert export["skipped_media"] == []
    assert export["total_planned_media_bytes"] is None
    assert not isolated_repository.exists()
    assert await local_truth_snapshot(client) == truth_before


async def test_classifier_manifest_copy_media_dry_run_plans_media_without_writing(
    client: httpx.AsyncClient,
    isolated_repository: Path,
) -> None:
    imported = await create_reviewed_bird_example(
        client,
        filename="private-yard/classifier-export-bird.png",
    )
    preview = await classifier_manifest(client)
    truth_before = await local_truth_snapshot(client)
    source_path = Path(imported["media_asset"]["local_path"])
    source_size = source_path.stat().st_size

    response = await client.post(
        "/api/classifier-training-manifest/exports",
        json={
            "dry_run": True,
            "include_csv": True,
            "media_policy": "copy_media",
            "output_name": "copy-media-dry-run",
        },
    )

    assert response.status_code == 201
    export = response.json()
    planned = export["planned_media_files"]
    expected_example = preview["examples"][0]

    assert export["dry_run"] is True
    assert export["media_policy"] == "copy_media"
    assert export["output_directory"] is None
    assert export["examples"] == len(preview["examples"])
    assert export["skipped"] == len(preview["skipped_records"])
    assert len(planned) == 1
    assert planned[0]["example_id"] == expected_example["example_id"]
    assert planned[0]["media_asset_id"] == expected_example["media_asset_id"]
    assert planned[0]["source_path"] == str(source_path)
    assert planned[0]["planned_relative_path"] == (
        f"media/{expected_example['example_id']}.png"
    )
    assert not Path(planned[0]["planned_relative_path"]).is_absolute()
    assert ".." not in Path(planned[0]["planned_relative_path"]).parts
    assert Path(planned[0]["planned_relative_path"]).parts == (
        "media",
        f"{expected_example['example_id']}.png",
    )
    assert "classifier-export-bird" not in planned[0]["planned_relative_path"]
    assert planned[0]["size_bytes"] == source_size
    assert planned[0]["reason"] is None
    assert export["skipped_media"] == []
    assert export["total_planned_media_bytes"] == source_size
    assert not isolated_repository.exists()
    assert not (isolated_repository / planned[0]["planned_relative_path"]).exists()
    assert await local_truth_snapshot(client) == truth_before


async def test_classifier_manifest_export_writes_metadata_files_matching_preview(
    client: httpx.AsyncClient,
    isolated_repository: Path,
) -> None:
    await create_reviewed_bird_example(client)
    preview = await classifier_manifest(client)
    truth_before = await local_truth_snapshot(client)

    response = await client.post(
        "/api/classifier-training-manifest/exports",
        json={"output_name": "reviewed-bird-export"},
    )

    assert response.status_code == 201
    export = response.json()
    output_dir = Path(export["output_directory"])
    assert output_dir.is_dir()
    assert output_dir.parent == isolated_repository.resolve()
    assert export["dry_run"] is False
    assert export["examples"] == len(preview["examples"])
    assert export["skipped"] == len(preview["skipped_records"])
    assert {file["name"] for file in export["files"]} == {
        "manifest.jsonl",
        "taxonomy.json",
        "skipped_records.jsonl",
        "summary.json",
    }
    assert export_file_names(output_dir) == {
        "manifest.jsonl",
        "taxonomy.json",
        "skipped_records.jsonl",
        "summary.json",
    }
    assert read_jsonl(output_dir / "manifest.jsonl") == preview["examples"]
    assert read_jsonl(output_dir / "skipped_records.jsonl") == preview["skipped_records"]
    assert json.loads((output_dir / "taxonomy.json").read_text(encoding="utf-8")) == preview[
        "taxonomy"
    ]

    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["examples"] == len(preview["examples"])
    assert summary["skipped"] == len(preview["skipped_records"])
    assert summary["labels"] == preview["summary"]["labels"]
    assert summary["splits"] == preview["summary"]["splits"]
    assert summary["media_policy"] == "reference_only"
    assert export["media_policy"] == "reference_only"
    assert export["planned_media_files"] == []
    assert export["skipped_media"] == []
    assert export["total_planned_media_bytes"] is None
    assert await local_truth_snapshot(client) == truth_before
    assert all(
        path.suffix not in {".onnx", ".pt", ".pth", ".weights", ".engine", ".ckpt"}
        for path in isolated_repository.rglob("*")
        if path.is_file()
    )


async def test_classifier_manifest_export_csv_option_and_summary_omission(
    client: httpx.AsyncClient,
) -> None:
    await create_reviewed_bird_example(client, label="Blue Jay")

    response = await client.post(
        "/api/classifier-training-manifest/exports",
        json={"include_csv": True, "include_summary": False},
    )

    assert response.status_code == 201
    export = response.json()
    output_dir = Path(export["output_directory"])
    assert export_file_names(output_dir) == {
        "manifest.jsonl",
        "taxonomy.json",
        "skipped_records.jsonl",
        "manifest.csv",
    }
    rows = list(csv.DictReader((output_dir / "manifest.csv").open(encoding="utf-8")))
    assert any(row["label"] == "blue_jay" for row in rows)


def test_write_classifier_manifest_csv_neutralizes_formula_leading_cell_values(tmp_path: Path) -> None:
    """Pre-Release Trust & Correctness Correction v1 (DI-2): `manifest.csv`
    never called the shared CSV-injection sanitizer `_write_csv` uses --
    every field, including `label`, is free text at the schema level
    (`ClassifierManifestExample.label: str`, no controlled-vocabulary
    constraint), even though the accepted review-label taxonomy normally
    keeps real corrections to a closed set. Calls the writer directly with a
    hand-built manifest so this proves the writer's own sanitization,
    independent of whatever the real HTTP review-label path happens to
    normalize upstream."""

    from mockingbird.api.schemas import (
        ClassifierManifestExample,
        ClassifierManifestSummary,
        ClassifierTrainingManifestResponse,
    )

    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    try:
        example = ClassifierManifestExample(
            example_id="example-1", visit_id="visit-1", media_asset_id="media-1",
            label="=cmd|' /C calc'!A1", common_name="+HYPERLINK(\"http://evil.example\")",
            scientific_name="-2+3", split="train",
        )
        manifest = ClassifierTrainingManifestResponse(
            manifest_version="1", generated_at="2026-09-21T00:00:00Z", examples=[example],
            skipped_records=[], taxonomy=[],
            summary=ClassifierManifestSummary(examples=1, skipped=0, labels={}, splits={}),
        )
        output_path = tmp_path / "manifest.csv"
        repository._write_classifier_manifest_csv(output_path, manifest)
        rows = list(csv.DictReader(output_path.open(encoding="utf-8")))
    finally:
        repository.close()

    assert len(rows) == 1
    row = rows[0]
    assert row["label"] == "'=cmd|' /C calc'!A1"
    assert row["common_name"] == "'+HYPERLINK(\"http://evil.example\")"
    # "-2+3" starts with a trigger character (`-`) but, unlike a real
    # negative coordinate, is not itself a valid float -- must be sanitized.
    assert row["scientific_name"] == "'-2+3"


async def test_classifier_manifest_export_rejects_non_dry_run_media_copy_and_unsafe_input(
    client: httpx.AsyncClient,
    isolated_repository: Path,
) -> None:
    media_copy_response = await client.post(
        "/api/classifier-training-manifest/exports",
        json={"media_policy": "copy_media"},
    )
    invalid_policy_response = await client.post(
        "/api/classifier-training-manifest/exports",
        json={"media_policy": "unknown_policy", "dry_run": True},
    )
    traversal_response = await client.post(
        "/api/classifier-training-manifest/exports",
        json={"output_name": "../outside"},
    )

    assert media_copy_response.status_code == 422
    assert "copy_media export is dry-run only in this phase." in json.dumps(
        media_copy_response.json()["detail"]
    )
    assert invalid_policy_response.status_code == 422
    assert "media_policy must be 'reference_only' or 'copy_media'" in json.dumps(
        invalid_policy_response.json()["detail"]
    )
    assert traversal_response.status_code == 422
    assert not isolated_repository.exists()


async def test_classifier_manifest_copy_media_dry_run_reports_stale_media_reference(
    client: httpx.AsyncClient,
    isolated_repository: Path,
) -> None:
    imported = await create_reviewed_bird_example(
        client,
        filename="classifier-stale-media.png",
    )
    source_path = Path(imported["media_asset"]["local_path"])
    source_path.unlink()
    truth_before = await local_truth_snapshot(client)

    response = await client.post(
        "/api/classifier-training-manifest/exports",
        json={"dry_run": True, "media_policy": "copy_media"},
    )

    assert response.status_code == 201
    export = response.json()
    assert export["planned_media_files"] == []
    assert len(export["skipped_media"]) == 1
    assert export["skipped_media"][0]["media_asset_id"] == imported["media_asset"]["id"]
    assert export["skipped_media"][0]["source_path"] == str(source_path)
    assert export["skipped_media"][0]["reason"] == "stale_media_reference"
    assert export["total_planned_media_bytes"] == 0
    assert not isolated_repository.exists()
    assert await local_truth_snapshot(client) == truth_before


async def test_classifier_manifest_copy_media_dry_run_reports_unsupported_extension(
    client: httpx.AsyncClient,
    isolated_repository: Path,
) -> None:
    imported = await create_reviewed_bird_example(
        client,
        filename="classifier-export-bird.txt",
    )
    source_path = Path(imported["media_asset"]["local_path"])
    truth_before = await local_truth_snapshot(client)

    response = await client.post(
        "/api/classifier-training-manifest/exports",
        json={"dry_run": True, "media_policy": "copy_media"},
    )

    assert response.status_code == 201
    export = response.json()
    assert export["planned_media_files"] == []
    assert len(export["skipped_media"]) == 1
    assert export["skipped_media"][0]["media_asset_id"] == imported["media_asset"]["id"]
    assert export["skipped_media"][0]["source_path"] == str(source_path)
    assert export["skipped_media"][0]["reason"] == "unsupported_media_type"
    assert export["total_planned_media_bytes"] == 0
    assert source_path.exists()
    assert not isolated_repository.exists()
    assert await local_truth_snapshot(client) == truth_before


async def test_classifier_manifest_exports_are_unique_and_do_not_create_truth(
    client: httpx.AsyncClient,
    isolated_repository: Path,
) -> None:
    await create_reviewed_bird_example(client, filename="classifier-export-bird-1.png")
    truth_before = await local_truth_snapshot(client)

    first = await client.post(
        "/api/classifier-training-manifest/exports",
        json={"output_name": "repeatable-name"},
    )
    second = await client.post(
        "/api/classifier-training-manifest/exports",
        json={"output_name": "repeatable-name"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["export_id"] != second.json()["export_id"]
    assert first.json()["output_directory"] != second.json()["output_directory"]
    assert Path(first.json()["output_directory"]).is_dir()
    assert Path(second.json()["output_directory"]).is_dir()
    assert await local_truth_snapshot(client) == truth_before
    assert all(
        export_file_names(path)
        <= {"manifest.jsonl", "taxonomy.json", "skipped_records.jsonl", "summary.json"}
        for path in isolated_repository.iterdir()
        if path.is_dir()
    )
