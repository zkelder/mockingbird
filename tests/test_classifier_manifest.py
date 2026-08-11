from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
BIRD_VISIT_ID = "visit-bird-feeder-001"


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
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


async def classifier_manifest(client: httpx.AsyncClient) -> dict:
    response = await client.get("/api/classifier-training-manifest")
    assert response.status_code == 200
    return response.json()


async def import_bird_media(
    client: httpx.AsyncClient,
    *,
    title: str = "Classifier manifest bird",
    filename: str = "classifier-manifest-bird.png",
) -> dict:
    response = await client.post(
        "/api/media/import",
        data={
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "title": title,
            "subject_label": "unknown_bird",
            "species_guess": "unknown_bird",
            "notes": "Tiny local media for classifier manifest tests.",
        },
        files={"file": (filename, b"classifier manifest image", "image/png")},
    )
    assert response.status_code == 201
    return response.json()


async def correct_visit(client: httpx.AsyncClient, visit_id: str, label: str) -> dict:
    response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": visit_id,
            "label": label,
            "notes": "Classifier manifest correction truth.",
        },
    )
    assert response.status_code == 201
    return response.json()


async def create_accepted_species_suggestion(
    client: httpx.AsyncClient,
    *,
    imported: dict,
) -> dict:
    suggestion_response = await client.post(
        "/api/species-suggestions",
        json={
            "source_id": SOURCE_ID,
            "stream_id": STREAM_ID,
            "event_id": imported["event"]["id"],
            "visit_id": imported["visit"]["id"],
            "media_asset_id": imported["media_asset"]["id"],
            "adapter_id": "mock_species_adapter",
            "adapter_name": "Mock Species Adapter",
            "suggested_label": "northern_cardinal",
            "suggested_common_name": "Northern Cardinal",
            "suggested_scientific_name": "Cardinalis cardinalis",
            "confidence": 0.84,
            "rank": 1,
            "alternatives": [],
            "notes": "Accepted suggestion remains evidence only.",
        },
    )
    assert suggestion_response.status_code == 201
    suggestion = suggestion_response.json()

    accepted_response = await client.post(
        f"/api/species-suggestions/{suggestion['id']}/status",
        json={"status": "accepted"},
    )
    assert accepted_response.status_code == 200
    return accepted_response.json()


async def create_motion_evidence(client: httpx.AsyncClient) -> dict:
    response = await client.post(
        "/api/motion/evidence",
        json={
            "zone_id": FEEDER_ZONE_ID,
            "start_frame_index": 4,
            "end_frame_index": 6,
            "best_frame_index": 5,
            "peak_changed_ratio": 0.31,
            "triggered_frame_count": 2,
            "scoring_config": {"source": "classifier_manifest_test"},
        },
    )
    assert response.status_code == 201
    return response.json()


async def local_truth_snapshot(client: httpx.AsyncClient) -> dict:
    responses = {
        "events": await client.get("/api/events"),
        "visits": await client.get("/api/visits"),
        "review_labels": await client.get("/api/review-labels"),
        "exports": await client.get("/api/dataset-exports"),
        "detection_runs": await client.get("/api/detection-runs"),
        "coverage": await client.get("/api/dataset-coverage/summary"),
    }
    for response in responses.values():
        assert response.status_code == 200

    coverage = responses["coverage"].json()
    return {
        "events": len(responses["events"].json()),
        "visits": len(responses["visits"].json()),
        "review_labels": len(responses["review_labels"].json()),
        "exports": len(responses["exports"].json()),
        "detection_runs": len(responses["detection_runs"].json()),
        "reviewed_record_count": coverage["reviewed_record_count"],
        "export_ready_count": coverage["export_ready_count"],
    }


def manifest_signature(manifest: dict) -> dict:
    return {
        "examples": manifest["examples"],
        "skipped_records": manifest["skipped_records"],
        "taxonomy": manifest["taxonomy"],
        "summary": manifest["summary"],
        "warnings": manifest["warnings"],
    }


def skipped_reasons(manifest: dict) -> list[str]:
    return [record["reason"] for record in manifest["skipped_records"]]


def skipped_by_visit(manifest: dict, visit_id: str) -> dict:
    return next(record for record in manifest["skipped_records"] if record["visit_id"] == visit_id)


def media_files(media_root: Path) -> list[str]:
    if not media_root.exists():
        return []
    return sorted(
        str(path.relative_to(media_root))
        for path in media_root.rglob("*")
        if path.is_file()
    )


async def test_classifier_manifest_shape_and_read_only_behavior(
    client: httpx.AsyncClient,
) -> None:
    truth_before = await local_truth_snapshot(client)

    first = await classifier_manifest(client)
    second = await classifier_manifest(client)

    assert manifest_signature(second) == manifest_signature(first)
    assert await local_truth_snapshot(client) == truth_before
    assert first["manifest_version"] == "classifier-training-preview-v1"
    assert first["generated_at"]
    assert first["examples"] == []
    assert first["summary"]["examples"] == 0
    assert first["summary"]["skipped"] == len(first["skipped_records"])
    assert "unreviewed" in skipped_reasons(first)
    assert "missing_media" in skipped_reasons(first)
    assert any(entry["label"] == "northern_cardinal" for entry in first["taxonomy"])
    assert first["warnings"]


async def test_reviewed_media_backed_visit_appears_as_manifest_example(
    client: httpx.AsyncClient,
) -> None:
    imported = await import_bird_media(client)
    correction = await correct_visit(client, imported["visit"]["id"], "Northern Cardinal")

    manifest = await classifier_manifest(client)
    example = next(
        record for record in manifest["examples"] if record["visit_id"] == imported["visit"]["id"]
    )

    assert example["example_id"] == f"classifier-example-{imported['visit']['id']}"
    assert example["event_id"] == imported["event"]["id"]
    assert example["media_asset_id"] == imported["media_asset"]["id"]
    assert example["source_id"] == SOURCE_ID
    assert example["stream_id"] == STREAM_ID
    assert example["zone_id"] == FEEDER_ZONE_ID
    assert example["local_media_path"] == imported["media_asset"]["local_path"]
    assert example["label"] == "northern_cardinal"
    assert example["taxonomy_id"] == "northern_cardinal"
    assert example["common_name"] == "Northern Cardinal"
    assert example["reviewed_label_id"] == correction["review_label"]["id"]
    assert example["reviewed_at"]
    assert example["created_at"]
    assert example["split"] == "train"
    assert example["quality_flags"] == []
    assert example["provenance"]["truth_source"] == "review_label"
    assert "SpeciesSuggestion" in example["provenance"]["evidence_only_sources"]
    assert manifest["summary"]["labels"]["northern_cardinal"] == 1
    assert manifest["summary"]["splits"]["train"] == 1


async def test_unreviewed_media_backed_visit_is_skipped_not_manifest_truth(
    client: httpx.AsyncClient,
) -> None:
    imported = await import_bird_media(client)

    manifest = await classifier_manifest(client)

    assert all(example["visit_id"] != imported["visit"]["id"] for example in manifest["examples"])
    skipped = skipped_by_visit(manifest, imported["visit"]["id"])
    assert skipped["reason"] == "unreviewed"
    assert skipped["media_asset_id"] is None


async def test_accepted_species_suggestion_alone_does_not_create_manifest_example(
    client: httpx.AsyncClient,
) -> None:
    imported = await import_bird_media(client)
    before = manifest_signature(await classifier_manifest(client))

    suggestion = await create_accepted_species_suggestion(client, imported=imported)
    after = manifest_signature(await classifier_manifest(client))

    assert suggestion["status"] == "accepted"
    assert after == before


async def test_motion_evidence_alone_does_not_create_manifest_example(
    client: httpx.AsyncClient,
) -> None:
    before = manifest_signature(await classifier_manifest(client))

    evidence = await create_motion_evidence(client)
    after = manifest_signature(await classifier_manifest(client))

    assert evidence["status"] == "pending"
    assert after == before


async def test_unknown_and_false_positive_reviewed_labels_are_skipped(
    client: httpx.AsyncClient,
) -> None:
    unknown_bird_import = await import_bird_media(client, title="Unknown bird")
    unknown_animal_import = await import_bird_media(client, title="Unknown animal")
    false_import = await import_bird_media(client, title="False positive")

    await correct_visit(client, unknown_bird_import["visit"]["id"], "unknown_bird")
    await correct_visit(client, unknown_animal_import["visit"]["id"], "unknown_animal")
    await correct_visit(client, false_import["visit"]["id"], "false_positive")
    manifest = await classifier_manifest(client)

    assert all(
        example["visit_id"]
        not in {
            unknown_bird_import["visit"]["id"],
            unknown_animal_import["visit"]["id"],
            false_import["visit"]["id"],
        }
        for example in manifest["examples"]
    )
    assert skipped_by_visit(manifest, unknown_bird_import["visit"]["id"])["reason"] == "unknown_label"
    assert skipped_by_visit(manifest, unknown_animal_import["visit"]["id"])["reason"] == "unknown_label"
    assert (
        skipped_by_visit(manifest, false_import["visit"]["id"])["reason"]
        == "false_positive_policy_excluded"
    )


async def test_missing_media_and_out_of_taxonomy_reviewed_labels_are_skipped(
    client: httpx.AsyncClient,
) -> None:
    await correct_visit(client, BIRD_VISIT_ID, "Northern Cardinal")
    out_of_taxonomy_import = await import_bird_media(client, title="Mystery visitor")

    await correct_visit(
        client,
        out_of_taxonomy_import["visit"]["id"],
        "mystery feeder guest",
    )
    manifest = await classifier_manifest(client)

    missing_media = skipped_by_visit(manifest, BIRD_VISIT_ID)
    out_of_taxonomy = skipped_by_visit(manifest, out_of_taxonomy_import["visit"]["id"])

    assert missing_media["reason"] == "missing_media"
    assert missing_media["label"] == "northern_cardinal"
    assert out_of_taxonomy["reason"] == "out_of_taxonomy"
    assert out_of_taxonomy["label"] == "mystery_feeder_guest"


async def test_split_assignment_is_deterministic_and_summary_counts_match(
    client: httpx.AsyncClient,
) -> None:
    labels = ["Northern Cardinal", "Blue Jay", "Carolina Wren"]
    for index, label in enumerate(labels, start=1):
        imported = await import_bird_media(
            client,
            title=f"Reviewed bird {index}",
            filename=f"classifier-manifest-bird-{index}.png",
        )
        await correct_visit(client, imported["visit"]["id"], label)

    first = await classifier_manifest(client)
    second = await classifier_manifest(client)

    assert manifest_signature(first) == manifest_signature(second)
    assert len(first["examples"]) == 3
    assert first["summary"]["examples"] == len(first["examples"])
    assert first["summary"]["skipped"] == len(first["skipped_records"])
    assert first["summary"]["labels"] == {
        "blue_jay": 1,
        "carolina_wren": 1,
        "northern_cardinal": 1,
    }
    assert sum(first["summary"]["splits"].values()) == len(first["examples"])
    assert {example["split"] for example in first["examples"]} <= {
        "train",
        "validation",
        "test",
    }


async def test_manifest_route_does_not_create_truth_or_media_artifacts(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    imported = await import_bird_media(client)
    await correct_visit(client, imported["visit"]["id"], "Blue Jay")
    media_root = tmp_path / "media"
    media_before = media_files(media_root)
    truth_before = await local_truth_snapshot(client)

    manifest = await classifier_manifest(client)
    await classifier_manifest(client)

    assert any(example["label"] == "blue_jay" for example in manifest["examples"])
    assert await local_truth_snapshot(client) == truth_before
    assert media_files(media_root) == media_before
