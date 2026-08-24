import hashlib
from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.database import CURRENT_DATABASE_SCHEMA_VERSION, create_database_engine
from mockingbird.storage.models import StreamSpeciesCandidatePackSelectionModel
from tests.conftest import LegacyAuthenticatedTestClient


pytestmark = pytest.mark.anyio

STREAM_ID = "stream-backyard-feeder"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path):
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
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


async def test_builtin_pack_preserves_exact_legacy_members_and_stream_default(
    client: httpx.AsyncClient,
) -> None:
    packs = await client.get("/api/species-candidate-packs")
    selection = await client.get(f"/api/streams/{STREAM_ID}/species-candidate-pack")

    assert packs.status_code == 200
    builtin = next(pack for pack in packs.json() if pack["id"] == "backyard-core")
    assert builtin["version"] == 1
    assert builtin["is_builtin"] is True
    assert builtin["candidate_count"] == 14
    assert [member["id"] for member in builtin["members"]] == [
        "northern_mockingbird",
        "carolina_wren",
        "mourning_dove",
        "american_robin",
        "northern_cardinal",
        "blue_jay",
        "tufted_titmouse",
        "carolina_chickadee",
        "house_finch",
        "eastern_bluebird",
        "red_bellied_woodpecker",
        "downy_woodpecker",
        "brown_thrasher",
        "gray_catbird",
    ]
    assert builtin["content_sha256"] == hashlib.sha256(
        "\n".join(member["id"] for member in builtin["members"]).encode("utf-8")
    ).hexdigest()
    assert selection.status_code == 200
    assert selection.json()["selected_pack_id"] is None
    assert selection.json()["effective_pack"]["id"] == "backyard-core"
    assert selection.json()["warning"] is None


async def test_user_pack_validation_versioning_archive_and_stream_persistence(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    duplicate = await client.post(
        "/api/species-candidate-packs",
        json={"display_name": "Bad", "taxonomy_label_ids": ["tufted_titmouse", "tufted_titmouse"]},
    )
    non_bird = await client.post(
        "/api/species-candidate-packs",
        json={"display_name": "Bad bird", "taxonomy_label_ids": ["tufted_titmouse", "squirrel"]},
    )
    too_small = await client.post(
        "/api/species-candidate-packs",
        json={"display_name": "Small", "taxonomy_label_ids": ["tufted_titmouse"]},
    )
    too_large = await client.post(
        "/api/species-candidate-packs",
        json={"display_name": "Large", "taxonomy_label_ids": ["tufted_titmouse"] * 201},
    )
    cloned = await client.post("/api/species-candidate-packs/backyard-core/clone", json={})

    assert duplicate.status_code == 400
    assert non_bird.status_code == 400
    assert too_small.status_code == 422
    assert too_large.status_code == 422
    assert cloned.status_code == 200
    first = cloned.json()
    assert first["is_builtin"] is False
    assert first["version"] == 1

    selected = await client.put(
        f"/api/streams/{STREAM_ID}/species-candidate-pack",
        json={"candidate_pack_id": first["id"]},
    )
    edited = await client.put(
        f"/api/species-candidate-packs/{first['id']}",
        json={
            "display_name": first["display_name"],
            "taxonomy_label_ids": [member["id"] for member in first["members"][:-2]],
            "description": "Narrow local feeder pack.",
        },
    )

    assert selected.status_code == 200
    assert edited.status_code == 200
    second = edited.json()
    assert second["version"] == 2
    assert second["candidate_count"] == 12
    assert second["content_sha256"] != first["content_sha256"]
    assert (await client.get(f"/api/species-candidate-packs/{first['id']}")).json()["status"] == "archived"
    persisted = ProductRepository(db_url=isolated_repository.db_url, media_root=isolated_repository.media_root)
    try:
        restored_selection = persisted.get_stream_species_candidate_pack_selection(STREAM_ID)
        assert restored_selection is not None
        assert restored_selection.selected_pack_id == second["id"]
        assert restored_selection.effective_pack.content_sha256 == second["content_sha256"]
    finally:
        persisted.close()


async def test_archived_selection_falls_back_without_creating_truth(
    client: httpx.AsyncClient,
) -> None:
    created = await client.post(
        "/api/species-candidate-packs",
        json={
            "display_name": "Temporary feeder pack",
            "taxonomy_label_ids": ["tufted_titmouse", "carolina_chickadee"],
        },
    )
    pack_id = created.json()["id"]
    selected = await client.put(
        f"/api/streams/{STREAM_ID}/species-candidate-pack",
        json={"candidate_pack_id": pack_id},
    )
    archived = await client.post(f"/api/species-candidate-packs/{pack_id}/archive")
    review = await client.get("/api/review-queue")
    labels = await client.get("/api/review-labels")

    assert selected.status_code == 200
    assert archived.status_code == 200
    assert review.status_code == 200
    item = next(item for item in review.json() if item["stream_id"] == STREAM_ID)
    assert item["identification"]["candidate_pack"]["id"] == "backyard-core"
    assert "archived" in item["identification"]["candidate_pack_warning"].lower()
    assert labels.status_code == 200
    assert {label["id"] for label in labels.json()} == {"review-label-squirrel-001"}


async def test_missing_selection_falls_back_without_creating_truth(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    created = await client.post(
        "/api/species-candidate-packs",
        json={
            "display_name": "Missing fallback pack",
            "taxonomy_label_ids": ["tufted_titmouse", "carolina_chickadee"],
        },
    )
    assert created.status_code == 200
    selected = await client.put(
        f"/api/streams/{STREAM_ID}/species-candidate-pack",
        json={"candidate_pack_id": created.json()["id"]},
    )
    assert selected.status_code == 200
    with isolated_repository.session_factory() as session:
        with session.begin():
            persisted_selection = session.get(
                StreamSpeciesCandidatePackSelectionModel,
                STREAM_ID,
            )
            assert persisted_selection is not None
            persisted_selection.candidate_pack_id = "missing-candidate-pack"
    selection = await client.get(f"/api/streams/{STREAM_ID}/species-candidate-pack")
    review = await client.get("/api/review-queue")
    labels = await client.get("/api/review-labels")

    assert selection.status_code == 200
    assert selection.json()["effective_pack"]["id"] == "backyard-core"
    assert "missing" in selection.json()["warning"].lower()
    assert review.status_code == 200
    item = next(item for item in review.json() if item["stream_id"] == STREAM_ID)
    assert item["identification"]["candidate_pack"]["id"] == "backyard-core"
    assert "missing" in item["identification"]["candidate_pack_warning"].lower()
    assert labels.status_code == 200
    assert {label["id"] for label in labels.json()} == {"review-label-squirrel-001"}


async def test_schema_v24_migrates_candidate_pack_storage_and_defaults_existing_stream(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "schema-v24.sqlite3"
    repository = ProductRepository(
        db_url=f"sqlite:///{db_path}",
        media_root=tmp_path / "media",
    )
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE stream_species_candidate_pack_selections")
        connection.exec_driver_sql("DROP TABLE species_candidate_pack_members")
        connection.exec_driver_sql("DROP TABLE species_candidate_packs")
        connection.exec_driver_sql(
            "UPDATE mockingbird_schema SET version = 24 WHERE singleton_id = 1"
        )
    engine.dispose()

    migrated = ProductRepository(
        db_url=f"sqlite:///{db_path}",
        media_root=tmp_path / "media",
    )
    try:
        selection = migrated.get_stream_species_candidate_pack_selection(STREAM_ID)
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION == 53
        assert selection is not None
        assert selection.selected_pack_id is None
        assert selection.effective_pack.id == "backyard-core"
        assert selection.effective_pack.candidate_count == 14
    finally:
        migrated.close()
