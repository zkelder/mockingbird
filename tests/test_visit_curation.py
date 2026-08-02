from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import (
    EventModel,
    MediaAssetModel,
    ReviewLabelModel,
    VisitEvidenceLinkModel,
    VisitModel,
    ZoneModel,
)


STREAM_ID = "stream-backyard-feeder"
SOURCE_ID = "source-backyard-demo"
FEEDER_ZONE_ID = "zone-feeder"
GROUND_ZONE_ID = "zone-ground"

pytestmark = pytest.mark.anyio


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


def add_visit(
    repository: ProductRepository,
    *,
    visit_id: str,
    event_id: str,
    zone_id: str = FEEDER_ZONE_ID,
    captured_at: datetime | None = None,
    frame_count: int = 3,
    shared_media_ids: list[str] | None = None,
) -> list[str]:
    """Create bounded local evidence without writing any real media files."""

    started_at = captured_at or datetime.now(UTC)
    media_ids = shared_media_ids or [f"media-{visit_id}-{index}" for index in range(frame_count)]
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=STREAM_ID,
                    title=f"Curation fixture {visit_id}",
                    event_type="motion_evidence",
                    started_at=started_at,
                    ended_at=started_at + timedelta(seconds=frame_count - 1),
                    primary_zone_id=zone_id,
                    review_status="needs_review",
                )
            )
            for index, media_id in enumerate(media_ids):
                if session.get(MediaAssetModel, media_id) is None:
                    session.add(
                        MediaAssetModel(
                            id=media_id,
                            source_id=SOURCE_ID,
                            stream_id=STREAM_ID,
                            filename=f"{media_id}.jpg",
                            content_type="image/jpeg",
                            media_type="image",
                            local_path=f"fixture/{media_id}.jpg",
                            original_filename=f"{media_id}.jpg",
                            file_size_bytes=12,
                            created_at=started_at + timedelta(seconds=index),
                            notes="Curation fixture evidence.",
                        )
                    )
            session.add(
                VisitModel(
                    id=visit_id,
                    event_id=event_id,
                    subject_label="bird",
                    species_guess="northern_cardinal",
                    confidence=None,
                    reviewed_label=None,
                    review_status="needs_review",
                    representative_media_path=f"fixture/{media_ids[0]}.jpg",
                    zone_id=zone_id,
                    is_superseded=False,
                )
            )
            for index, media_id in enumerate(media_ids):
                session.add(
                    VisitEvidenceLinkModel(
                        id=f"link-{visit_id}-{media_id}",
                        visit_id=visit_id,
                        media_asset_id=media_id,
                        captured_at=started_at + timedelta(seconds=index),
                        frame_sequence=index,
                        sort_order=index,
                        is_primary=index == 0,
                        created_at=started_at,
                    )
                )
    return media_ids


async def visit_detail(client: httpx.AsyncClient, visit_id: str) -> dict:
    response = await client.get(f"/api/visits/{visit_id}/detail")
    assert response.status_code == 200
    return response.json()


async def review_visit(client: httpx.AsyncClient, visit_id: str, label: str) -> None:
    response = await client.post(
        "/api/review-labels",
        json={"target_type": "visit", "target_id": visit_id, "label": label},
    )
    assert response.status_code == 201


async def test_evidence_curation_changes_primary_everywhere_and_unlinks_only(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    media_ids = add_visit(
        isolated_repository,
        visit_id="visit-evidence",
        event_id="event-evidence",
    )
    before = await visit_detail(client, "visit-evidence")
    payload = {
        "retained_media_asset_ids": [media_ids[0], media_ids[2]],
        "primary_media_asset_id": media_ids[2],
        "expected_state_token": before["review_state_token"],
        "idempotency_key": "evidence-primary-third",
    }
    updated = await client.post("/api/visits/visit-evidence/evidence-curation", json=payload)
    assert updated.status_code == 200
    assert [frame["media_asset_id"] for frame in updated.json()["evidence_frames"]] == [
        media_ids[0],
        media_ids[2],
    ]
    assert [frame["media_asset_id"] for frame in updated.json()["evidence_frames"] if frame["is_primary"]] == [
        media_ids[2]
    ]
    repeated = await client.post("/api/visits/visit-evidence/evidence-curation", json=payload)
    assert repeated.status_code == 200
    assert repeated.json()["idempotent"] is True

    with isolated_repository.session_factory() as session:
        assert session.get(MediaAssetModel, media_ids[1]) is not None
        links = session.scalars(
            select(VisitEvidenceLinkModel).where(
                VisitEvidenceLinkModel.visit_id == "visit-evidence"
            )
        ).all()
        assert {link.media_asset_id for link in links} == {media_ids[0], media_ids[2]}

    stream_visits = await client.get(f"/api/streams/{STREAM_ID}/visits")
    assert stream_visits.status_code == 200
    summary = next(item for item in stream_visits.json() if item["id"] == "visit-evidence")
    assert summary["primary_evidence"]["media_asset_id"] == media_ids[2]
    queue = await client.get("/api/review-queue")
    queue_item = next(item for item in queue.json() if item.get("visit_id") == "visit-evidence")
    assert queue_item["best_media_asset_id"] == media_ids[2]

    stale = await client.post(
        "/api/visits/visit-evidence/evidence-curation",
        json={**payload, "idempotency_key": "evidence-stale"},
    )
    assert stale.status_code == 409


async def test_effective_primary_preview_is_identical_in_detail_and_queue_and_is_read_only(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    add_visit(
        isolated_repository,
        visit_id="visit-effective-primary-preview",
        event_id="event-effective-primary-preview",
    )
    with isolated_repository.session_factory() as session:
        before = (
            session.scalar(select(func.count(VisitModel.id))),
            session.scalar(select(func.count(VisitEvidenceLinkModel.id))),
            session.scalar(select(func.count(MediaAssetModel.id))),
            session.scalar(select(func.count(ReviewLabelModel.id))),
        )

    detail = await visit_detail(client, "visit-effective-primary-preview")
    queue = await client.get("/api/review-queue")
    assert queue.status_code == 200
    queue_item = next(
        item
        for item in queue.json()
        if item.get("visit_id") == "visit-effective-primary-preview"
    )
    assert detail["effective_primary"] == queue_item["effective_primary"]
    assert set(detail["effective_primary"]) >= {
        "temporally_supported",
        "temporal_status",
        "width",
        "height",
    }

    with isolated_repository.session_factory() as session:
        after = (
            session.scalar(select(func.count(VisitModel.id))),
            session.scalar(select(func.count(VisitEvidenceLinkModel.id))),
            session.scalar(select(func.count(MediaAssetModel.id))),
            session.scalar(select(func.count(ReviewLabelModel.id))),
        )
    assert after == before


async def test_split_supersedes_reviewed_truth_and_returns_two_active_review_visits(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    media_ids = add_visit(
        isolated_repository,
        visit_id="visit-split",
        event_id="event-split",
    )
    await review_visit(client, "visit-split", "northern_cardinal")
    before = await visit_detail(client, "visit-split")
    organization = await client.get("/api/visits/visit-split/organization")
    assert organization.status_code == 200
    saved_organization = await client.put(
        "/api/visits/visit-split/organization",
        json={
            "is_favorite": True,
            "note": "Split context",
            "expected_state_token": organization.json()["state_token"],
            "idempotency_key": "split-organization",
        },
    )
    assert saved_organization.status_code == 200
    split_collection = await client.post(
        "/api/collections",
        json={"name": "Split curation", "idempotency_key": "split-collection-create"},
    )
    assert split_collection.status_code == 201
    added_to_collection = await client.post(
        f"/api/collections/{split_collection.json()['id']}/visits/visit-split",
        json={
            "expected_state_token": split_collection.json()["state_token"],
            "idempotency_key": "split-collection-add",
        },
    )
    assert added_to_collection.status_code == 200
    split_tag = await client.post(
        "/api/tags",
        json={"name": "Split context", "idempotency_key": "split-tag-create"},
    )
    assert split_tag.status_code == 201
    added_tag = await client.post(
        f"/api/tags/{split_tag.json()['id']}/visits/visit-split",
        json={
            "expected_state_token": split_tag.json()["state_token"],
            "idempotency_key": "split-tag-add",
        },
    )
    assert added_tag.status_code == 200
    preview = await client.post(
        "/api/visits/visit-split/split/preview",
        json={
            "boundary_after_media_asset_id": media_ids[0],
            "expected_state_token": before["review_state_token"],
        },
    )
    assert preview.status_code == 200
    assert preview.json()["first"]["evidence_count"] == 1
    assert preview.json()["second"]["evidence_count"] == 2
    split = await client.post(
        "/api/visits/visit-split/split",
        json={
            "boundary_after_media_asset_id": media_ids[0],
            "expected_state_token": preview.json()["state_token"],
            "idempotency_key": "split-reviewed-visit",
        },
    )
    assert split.status_code == 200
    results = split.json()["resulting_visits"]
    assert len(results) == 2
    assert all(result["review_status"] == "needs_review" for result in results)
    assert all(not result["reviewed_label"] for result in results)
    for result in results:
        inherited = await client.get(f"/api/visits/{result['id']}/organization")
        assert inherited.status_code == 200
        assert inherited.json()["is_favorite"] is True
        assert inherited.json()["note"] == "Split context"
        assert inherited.json()["inherited_from_visit_id"] == "visit-split"
        inherited_collections = await client.get(f"/api/visits/{result['id']}/collections")
        assert [item["name"] for item in inherited_collections.json()["collections"]] == ["Split curation"]
        inherited_tags = await client.get(f"/api/visits/{result['id']}/tags")
        assert [item["name"] for item in inherited_tags.json()["tags"]] == ["Split context"]
    active_collection = await client.get(f"/api/collections/{split_collection.json()['id']}")
    assert active_collection.json()["active_visit_count"] == 2

    original = await visit_detail(client, "visit-split")
    assert original["visit"]["is_superseded"] is True
    assert len(original["resulting_visits"]) == 2
    visits = await client.get("/api/visits")
    assert "visit-split" not in {visit["id"] for visit in visits.json()}
    labels = await client.get("/api/review-labels")
    assert all(label["target_id"] != "visit-split" for label in labels.json())
    analytics = await client.get("/api/analytics/summary")
    assert "northern_cardinal" not in analytics.json()["species_counts"]
    queue = await client.get("/api/review-queue")
    queued_ids = {item.get("visit_id") for item in queue.json()}
    assert {result["id"] for result in results}.issubset(queued_ids)


async def test_merge_rules_and_zone_reassignment_preserve_correction_history(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    start = datetime.now(UTC)
    shared = ["media-shared", "media-left-only"]
    add_visit(
        isolated_repository,
        visit_id="visit-merge-left",
        event_id="event-merge-left",
        captured_at=start,
        shared_media_ids=shared,
    )
    add_visit(
        isolated_repository,
        visit_id="visit-merge-right",
        event_id="event-merge-right",
        captured_at=start + timedelta(seconds=10),
        shared_media_ids=["media-shared", "media-right-only"],
    )
    await review_visit(client, "visit-merge-left", "northern_cardinal")
    await review_visit(client, "visit-merge-right", "northern_cardinal")
    for visit_id, favorite, note in [
        ("visit-merge-left", False, "Left context"),
        ("visit-merge-right", True, "Right context"),
    ]:
        organization = await client.get(f"/api/visits/{visit_id}/organization")
        assert organization.status_code == 200
        updated = await client.put(
            f"/api/visits/{visit_id}/organization",
            json={
                "is_favorite": favorite,
                "note": note,
                "expected_state_token": organization.json()["state_token"],
                "idempotency_key": f"merge-organization-{visit_id}",
            },
        )
        assert updated.status_code == 200
    merge_collections = []
    for name, visit_id in [("Merge left", "visit-merge-left"), ("Merge right", "visit-merge-right")]:
        collection = await client.post(
            "/api/collections",
            json={"name": name, "idempotency_key": f"create-{name}"},
        )
        assert collection.status_code == 201
        membership = await client.post(
            f"/api/collections/{collection.json()['id']}/visits/{visit_id}",
            json={
                "expected_state_token": collection.json()["state_token"],
                "idempotency_key": f"add-{name}",
            },
        )
        assert membership.status_code == 200
        merge_collections.append(name)
    merge_tag_names = []
    for name, visit_id in [("Merge tag left", "visit-merge-left"), ("Merge tag right", "visit-merge-right")]:
        tag = await client.post(
            "/api/tags",
            json={"name": name, "idempotency_key": f"create-{name}"},
        )
        assert tag.status_code == 201
        membership = await client.post(
            f"/api/tags/{tag.json()['id']}/visits/{visit_id}",
            json={
                "expected_state_token": tag.json()["state_token"],
                "idempotency_key": f"add-{name}",
            },
        )
        assert membership.status_code == 200
        merge_tag_names.append(name)
    left = await visit_detail(client, "visit-merge-left")
    candidates = await client.get("/api/visits/visit-merge-left/merge-candidates")
    assert candidates.status_code == 200
    assert any(candidate["visit"]["id"] == "visit-merge-right" for candidate in candidates.json()["candidates"])
    preview = await client.post(
        "/api/visits/visit-merge-left/merge/preview",
        json={
            "candidate_visit_ids": ["visit-merge-right"],
            "expected_state_token": left["review_state_token"],
        },
    )
    assert preview.status_code == 200
    assert preview.json()["combined"]["evidence_count"] == 3
    merged = await client.post(
        "/api/visits/visit-merge-left/merge",
        json={
            "candidate_visit_ids": ["visit-merge-right"],
            "expected_state_token": preview.json()["state_token"],
            "idempotency_key": "merge-matching-reviewed",
        },
    )
    assert merged.status_code == 200
    result = merged.json()["visit"]
    assert result["review_status"] == "reviewed"
    assert result["reviewed_label"] == "northern_cardinal"
    merged_organization = await client.get(f"/api/visits/{result['id']}/organization")
    assert merged_organization.status_code == 200
    assert merged_organization.json()["is_favorite"] is True
    assert merged_organization.json()["note"] == "Left context\n\nRight context"
    merged_collections = await client.get(f"/api/visits/{result['id']}/collections")
    assert [item["name"] for item in merged_collections.json()["collections"]] == merge_collections
    merged_tags = await client.get(f"/api/visits/{result['id']}/tags")
    assert [item["name"] for item in merged_tags.json()["tags"]] == merge_tag_names
    for name in merge_collections:
        collection = next(item for item in (await client.get("/api/collections")).json() if item["name"] == name)
        assert collection["active_visit_count"] == 1
    assert (await visit_detail(client, "visit-merge-left"))["visit"]["is_superseded"] is True
    assert (await visit_detail(client, "visit-merge-right"))["visit"]["is_superseded"] is True

    merged_detail = await visit_detail(client, result["id"])
    privacy_id = "zone-curation-privacy"
    with isolated_repository.session_factory() as session:
        with session.begin():
            session.add(
                ZoneModel(
                    id=privacy_id,
                    stream_id=STREAM_ID,
                    name="Private nesting area",
                    zone_type="privacy",
                    polygon_json="[]",
                    is_active=True,
                    monitoring_policy_json=None,
                )
            )
    rejected = await client.post(
        f"/api/visits/{result['id']}/zone",
        json={
            "zone_id": privacy_id,
            "expected_state_token": merged_detail["review_state_token"],
            "idempotency_key": "move-to-privacy",
        },
    )
    assert rejected.status_code == 400
    moved = await client.post(
        f"/api/visits/{result['id']}/zone",
        json={
            "zone_id": GROUND_ZONE_ID,
            "expected_state_token": merged_detail["review_state_token"],
            "idempotency_key": "move-to-ground",
        },
    )
    assert moved.status_code == 200
    assert moved.json()["visit"]["zone_id"] == GROUND_ZONE_ID
    with isolated_repository.session_factory() as session:
        labels = session.scalars(
            select(ReviewLabelModel).where(ReviewLabelModel.target_id == result["id"])
        ).all()
        assert len(labels) == 1


async def test_merge_rejects_a_tag_union_over_the_visit_limit(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    started_at = datetime.now(UTC)
    add_visit(
        isolated_repository,
        visit_id="visit-tag-limit-left",
        event_id="event-tag-limit-left",
        captured_at=started_at,
        shared_media_ids=["media-tag-limit-shared", "media-tag-limit-left"],
    )
    add_visit(
        isolated_repository,
        visit_id="visit-tag-limit-right",
        event_id="event-tag-limit-right",
        captured_at=started_at + timedelta(seconds=10),
        shared_media_ids=["media-tag-limit-shared", "media-tag-limit-right"],
    )
    await review_visit(client, "visit-tag-limit-left", "northern_cardinal")
    await review_visit(client, "visit-tag-limit-right", "northern_cardinal")
    for index in range(21):
        tag = await client.post(
            "/api/tags",
            json={"name": f"Merge limit {index}", "idempotency_key": f"merge-limit-create-{index}"},
        )
        assert tag.status_code == 201
        visit_id = "visit-tag-limit-left" if index < 11 else "visit-tag-limit-right"
        membership = await client.post(
            f"/api/tags/{tag.json()['id']}/visits/{visit_id}",
            json={
                "expected_state_token": tag.json()["state_token"],
                "idempotency_key": f"merge-limit-add-{index}",
            },
        )
        assert membership.status_code == 200
    left = await visit_detail(client, "visit-tag-limit-left")
    preview = await client.post(
        "/api/visits/visit-tag-limit-left/merge/preview",
        json={
            "candidate_visit_ids": ["visit-tag-limit-right"],
            "expected_state_token": left["review_state_token"],
        },
    )
    assert preview.status_code == 200
    rejected = await client.post(
        "/api/visits/visit-tag-limit-left/merge",
        json={
            "candidate_visit_ids": ["visit-tag-limit-right"],
            "expected_state_token": preview.json()["state_token"],
            "idempotency_key": "merge-tag-limit",
        },
    )
    assert rejected.status_code == 409
    assert "more than 20 combined tags" in rejected.json()["detail"]
