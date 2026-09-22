from datetime import UTC, datetime, timedelta
from pathlib import Path
import asyncio

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import EventModel
from tests.conftest import LegacyAuthenticatedSyncTestClient, de_demo_seeded_source

client = LegacyAuthenticatedSyncTestClient(app)

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
BIRD_EVENT_ID = "event-bird-feeder-001"
BIRD_VISIT_ID = "visit-bird-feeder-001"
SQUIRREL_VISIT_ID = "visit-squirrel-ground-001"
SEED_EXPORT_ID = "dataset-export-reviewed-yard-001"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}")
    de_demo_seeded_source(repository)
    configure_repository(repository)
    yield repository
    configure_repository(None)


def test_health_endpoint_works() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_sources_returns_demo_source() -> None:
    response = client.get("/api/sources")

    assert response.status_code == 200
    sources = response.json()
    assert sources[0]["id"] == SOURCE_ID
    assert sources[0]["kind"] == "demo"
    assert "product flow" in sources[0]["description"]


def test_source_detail_returns_demo_source() -> None:
    response = client.get(f"/api/sources/{SOURCE_ID}")

    assert response.status_code == 200
    source = response.json()
    assert source["id"] == SOURCE_ID
    assert source["name"] == "Backyard demo source"


def test_unknown_source_id_returns_404() -> None:
    response = client.get("/api/sources/source-missing")

    assert response.status_code == 404
    assert "Source 'source-missing' was not found." == response.json()["detail"]


def test_source_streams_returns_demo_stream() -> None:
    response = client.get(f"/api/sources/{SOURCE_ID}/streams")

    assert response.status_code == 200
    streams = response.json()
    assert [stream["id"] for stream in streams] == [STREAM_ID]
    assert streams[0]["source_id"] == SOURCE_ID


def test_streams_return_product_centered_stream() -> None:
    response = client.get("/api/streams")

    assert response.status_code == 200
    streams = response.json()
    assert streams[0]["source_id"] == SOURCE_ID
    assert streams[0]["name"] == "Backyard feeder stream"
    assert "feeder" in streams[0]["description"]
    assert streams[0]["is_live"] is True


def test_stream_detail_returns_product_centered_stream() -> None:
    response = client.get(f"/api/streams/{STREAM_ID}")

    assert response.status_code == 200
    stream = response.json()
    assert stream["id"] == STREAM_ID
    assert stream["source_id"] == SOURCE_ID
    assert stream["is_live"] is True


def test_zones_include_feeder_ground_and_ignore_zones() -> None:
    response = client.get("/api/zones")

    assert response.status_code == 200
    zone_types = {zone["zone_type"] for zone in response.json()}
    assert {"feeder", "ground", "ignore"}.issubset(zone_types)


def test_zone_detail_returns_feeder_zone() -> None:
    response = client.get(f"/api/zones/{FEEDER_ZONE_ID}")

    assert response.status_code == 200
    zone = response.json()
    assert zone["id"] == FEEDER_ZONE_ID
    assert zone["stream_id"] == STREAM_ID
    assert zone["zone_type"] == "feeder"


def test_stream_zones_include_feeder_ground_and_ignore_zones() -> None:
    response = client.get(f"/api/streams/{STREAM_ID}/zones")

    assert response.status_code == 200
    zones = response.json()
    zone_types = {zone["zone_type"] for zone in zones}
    assert {"feeder", "ground", "ignore"}.issubset(zone_types)
    assert all(zone["stream_id"] == STREAM_ID for zone in zones)


def test_post_zones_creates_zone_for_existing_stream() -> None:
    response = client.post(
        "/api/zones",
        json={
            "stream_id": STREAM_ID,
            "name": "Birdbath corner",
            "zone_type": "birdbath",
            "polygon": [
                {"x": 0.68, "y": 0.18},
                {"x": 0.88, "y": 0.18},
                {"x": 0.88, "y": 0.42},
                {"x": 0.68, "y": 0.42},
            ],
            "is_active": True,
        },
    )

    assert response.status_code == 201
    result = response.json()
    assert result["zone"]["stream_id"] == STREAM_ID
    assert result["zone"]["name"] == "Birdbath corner"
    assert result["zone"]["zone_type"] == "birdbath"
    assert result["zone"]["is_active"] is True
    assert result["zone"] in result["zones"]


def test_created_zone_appears_in_stream_zones() -> None:
    create_response = client.post(
        "/api/zones",
        json={
            "stream_id": STREAM_ID,
            "name": "Perch rail",
            "zone_type": "perch",
            "polygon": [
                {"x": 0.24, "y": 0.32},
                {"x": 0.36, "y": 0.32},
                {"x": 0.36, "y": 0.46},
                {"x": 0.24, "y": 0.46},
            ],
        },
    )
    created_zone_id = create_response.json()["zone"]["id"]

    response = client.get(f"/api/streams/{STREAM_ID}/zones")

    assert response.status_code == 200
    assert any(zone["id"] == created_zone_id for zone in response.json())


def test_zone_mutations_do_not_leak_between_tests() -> None:
    response = client.get(f"/api/streams/{STREAM_ID}/zones")

    assert response.status_code == 200
    assert len(response.json()) == 3


def test_post_zones_returns_404_for_unknown_stream() -> None:
    response = client.post(
        "/api/zones",
        json={
            "stream_id": "stream-missing",
            "name": "Missing stream zone",
            "zone_type": "yard",
            "polygon": [
                {"x": 0.1, "y": 0.1},
                {"x": 0.2, "y": 0.1},
                {"x": 0.2, "y": 0.2},
            ],
        },
    )

    assert response.status_code == 404
    assert "Stream 'stream-missing' was not found." == response.json()["detail"]


def test_post_zones_returns_400_for_invalid_polygon() -> None:
    response = client.post(
        "/api/zones",
        json={
            "stream_id": STREAM_ID,
            "name": "Invalid zone",
            "zone_type": "yard",
            "polygon": [
                {"x": 0.1, "y": 0.1},
                {"x": 0.2, "y": 0.2},
            ],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Zone polygon must contain at least 3 points."


def test_patch_zones_updates_name_type_and_active_state() -> None:
    response = client.patch(
        f"/api/zones/{FEEDER_ZONE_ID}",
        json={
            "name": "Feeder perch",
            "zone_type": "perch",
            "is_active": False,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["zone"]["id"] == FEEDER_ZONE_ID
    assert result["zone"]["name"] == "Feeder perch"
    assert result["zone"]["zone_type"] == "perch"
    assert result["zone"]["is_active"] is False
    assert any(zone["id"] == FEEDER_ZONE_ID for zone in result["zones"])


def test_patch_zones_returns_404_for_unknown_zone() -> None:
    response = client.patch("/api/zones/zone-missing", json={"name": "Missing zone"})

    assert response.status_code == 404
    assert "Zone 'zone-missing' was not found." == response.json()["detail"]


def test_patch_zones_returns_400_for_invalid_polygon() -> None:
    response = client.patch(
        f"/api/zones/{FEEDER_ZONE_ID}",
        json={
            "polygon": [
                {"x": 0.1, "y": 0.1},
                {"x": 0.2, "y": 0.2},
            ],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Zone polygon must contain at least 3 points."


def test_stream_events_returns_stream_events() -> None:
    response = client.get(f"/api/streams/{STREAM_ID}/events")

    assert response.status_code == 200
    events = response.json()
    assert {event["id"] for event in events} >= {
        "event-bird-feeder-001",
        "event-squirrel-ground-001",
    }
    assert all(event["stream_id"] == STREAM_ID for event in events)


def test_stream_events_are_bounded_and_newest_first(isolated_repository: ProductRepository) -> None:
    """v0.1 Product Flow Gap Pass v1: a Stream with substantial real history
    must not render every event ever recorded (unbounded growth -- a real
    Camera Node history reproduced a 55,000px Stream Detail page from this
    exact gap), and must surface the newest activity first rather than
    requiring a user to scroll past months of old events to reach it --
    matching `GET /api/streams/{id}/visits`' own already-correct bounded,
    newest-first convention right next to this one on Stream Detail."""

    base = datetime(2099, 1, 1, tzinfo=UTC)
    with isolated_repository.session_factory() as session:
        with session.begin():
            session.add_all(
                [
                    EventModel(
                        id=f"event-history-bulk-{index:03d}",
                        stream_id=STREAM_ID,
                        title="Live motion activity",
                        event_type="motion_evidence",
                        started_at=base + timedelta(minutes=index),
                        review_status="reviewed",
                    )
                    for index in range(60)
                ]
            )

    response = client.get(f"/api/streams/{STREAM_ID}/events")
    assert response.status_code == 200
    events = response.json()

    assert len(events) <= 50
    bulk_ids = [event["id"] for event in events if event["id"].startswith("event-history-bulk-")]
    assert len(bulk_ids) == 50
    # Newest (highest index / latest started_at) first.
    assert bulk_ids[0] == "event-history-bulk-059"
    assert bulk_ids[-1] == "event-history-bulk-010"

    limited = client.get(f"/api/streams/{STREAM_ID}/events", params={"limit": 5})
    assert limited.status_code == 200
    assert len(limited.json()) == 5
    assert limited.json()[0]["id"] == "event-history-bulk-059"

    invalid_limit = client.get(f"/api/streams/{STREAM_ID}/events", params={"limit": 101})
    assert invalid_limit.status_code == 422


def test_events_are_reviewable_and_include_detections() -> None:
    response = client.get("/api/events")

    assert response.status_code == 200
    events = response.json()
    assert {event["review_status"] for event in events} >= {"needs_review", "reviewed"}
    assert all(event["detections"] for event in events)
    assert events[0]["detections"][0]["label"] == "unknown_bird"


def test_event_detail_returns_reviewable_event() -> None:
    response = client.get(f"/api/events/{BIRD_EVENT_ID}")

    assert response.status_code == 200
    event = response.json()
    assert event["id"] == BIRD_EVENT_ID
    assert event["primary_zone_id"] == FEEDER_ZONE_ID
    assert event["review_status"] == "needs_review"


def test_event_detail_route_returns_review_case_file() -> None:
    response = client.get(f"/api/events/{BIRD_EVENT_ID}/detail")

    assert response.status_code == 200
    detail = response.json()
    assert detail["event"]["id"] == BIRD_EVENT_ID
    assert detail["stream"]["id"] == STREAM_ID
    assert detail["primary_zone"]["id"] == FEEDER_ZONE_ID
    assert [visit["id"] for visit in detail["visits"]] == [BIRD_VISIT_ID]
    assert detail["review_labels"] == []
    assert detail["dataset_ready"] is False
    assert "Needs review before export" in detail["review_summary"]


def test_event_visits_returns_visits_for_event() -> None:
    response = client.get(f"/api/events/{BIRD_EVENT_ID}/visits")

    assert response.status_code == 200
    visits = response.json()
    assert [visit["id"] for visit in visits] == [BIRD_VISIT_ID]
    assert visits[0]["event_id"] == BIRD_EVENT_ID


def test_visits_include_bird_visit_needing_review() -> None:
    response = client.get("/api/visits")

    assert response.status_code == 200
    visits = response.json()
    bird_visits = [visit for visit in visits if visit["subject_label"] == "bird"]
    assert bird_visits
    assert bird_visits[0]["review_status"] == "needs_review"
    assert bird_visits[0]["species_guess"] == "northern_cardinal"


def test_visit_detail_returns_bird_visit() -> None:
    response = client.get(f"/api/visits/{BIRD_VISIT_ID}")

    assert response.status_code == 200
    visit = response.json()
    assert visit["id"] == BIRD_VISIT_ID
    assert visit["event_id"] == BIRD_EVENT_ID
    assert visit["review_status"] == "needs_review"


def test_visit_detail_route_returns_review_case_file() -> None:
    response = client.get(f"/api/visits/{BIRD_VISIT_ID}/detail")

    assert response.status_code == 200
    detail = response.json()
    assert detail["visit"]["id"] == BIRD_VISIT_ID
    assert detail["event"]["id"] == BIRD_EVENT_ID
    assert detail["stream"]["id"] == STREAM_ID
    assert detail["primary_zone"]["id"] == FEEDER_ZONE_ID
    assert detail["detections"][0]["label"] == "unknown_bird"
    assert detail["review_labels"] == []
    assert detail["dataset_ready"] is False
    assert "Detections are evidence" in detail["review_summary"]


def test_unknown_event_and_visit_detail_return_404() -> None:
    unknown_detail_paths = [
        "/api/events/event-missing/detail",
        "/api/visits/visit-missing/detail",
    ]

    for path in unknown_detail_paths:
        response = client.get(path)
        assert response.status_code == 404
        assert "was not found" in response.json()["detail"]


def test_correcting_visit_makes_visit_detail_dataset_ready() -> None:
    client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": BIRD_VISIT_ID,
            "label": "carolina_wren",
            "notes": "Corrected from detail review.",
        },
    )

    response = client.get(f"/api/visits/{BIRD_VISIT_ID}/detail")

    assert response.status_code == 200
    detail = response.json()
    assert detail["dataset_ready"] is True
    assert detail["visit"]["reviewed_label"] == "carolina_wren"
    assert detail["review_labels"][0]["target_id"] == BIRD_VISIT_ID
    assert "Ready for local dataset export" in detail["review_summary"]


def test_correcting_visit_adds_event_detail_correction_history() -> None:
    client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": BIRD_VISIT_ID,
            "label": "northern_cardinal",
            "notes": "Confirmed from event case file.",
        },
    )

    response = client.get(f"/api/events/{BIRD_EVENT_ID}/detail")

    assert response.status_code == 200
    detail = response.json()
    assert detail["dataset_ready"] is True
    assert any(
        label["target_type"] == "visit"
        and label["target_id"] == BIRD_VISIT_ID
        and label["label"] == "northern_cardinal"
        for label in detail["review_labels"]
    )
    assert "Ready for local dataset export" in detail["review_summary"]


def test_detail_mutations_do_not_leak_between_tests() -> None:
    response = client.get(f"/api/visits/{BIRD_VISIT_ID}/detail")

    assert response.status_code == 200
    detail = response.json()
    assert detail["dataset_ready"] is False
    assert detail["review_labels"] == []


def test_review_queue_includes_bird_visit_needing_review() -> None:
    response = client.get("/api/review-queue")

    assert response.status_code == 200
    queue = response.json()
    bird_item = next(item for item in queue if item["visit_id"] == BIRD_VISIT_ID)
    assert bird_item["item_type"] == "visit"
    assert bird_item["stream_id"] == STREAM_ID
    assert bird_item["event_id"] == BIRD_EVENT_ID
    assert bird_item["primary_zone_id"] == FEEDER_ZONE_ID
    assert bird_item["primary_zone_name"] == "Feeder"
    assert bird_item["primary_zone_type"] == "feeder"
    assert bird_item["suggested_label"] == "northern_cardinal"
    assert bird_item["review_status"] == "needs_review"
    assert "Confirm or correct" in bird_item["reason"]


def test_review_queue_excludes_reviewed_squirrel_visit() -> None:
    response = client.get("/api/review-queue")

    assert response.status_code == 200
    queue = response.json()
    assert all(item["visit_id"] != SQUIRREL_VISIT_ID for item in queue)
    assert all(item["review_status"] == "needs_review" for item in queue)


def test_post_review_labels_creates_correction_label() -> None:
    response = client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": "visit-bird-feeder-001",
            "label": "northern_cardinal",
            "notes": "Confirmed during review.",
        },
    )

    assert response.status_code == 201
    result = response.json()
    label = result["review_label"]
    assert label["target_type"] == "visit"
    assert label["target_id"] == BIRD_VISIT_ID
    assert label["label"] == "northern_cardinal"
    assert label["created_at"]
    assert result["visit"]["review_status"] == "reviewed"
    assert result["visit"]["reviewed_label"] == "northern_cardinal"
    assert result["event"]["review_status"] == "reviewed"

    labels_response = client.get("/api/review-labels")
    labels = labels_response.json()
    assert any(
        item["target_id"] == BIRD_VISIT_ID
        and item["label"] == "northern_cardinal"
        for item in labels
    )


def test_visit_correction_updates_queue_and_analytics() -> None:
    before_analytics = client.get("/api/analytics/summary").json()

    response = client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": BIRD_VISIT_ID,
            "label": "carolina_wren",
            "notes": "Corrected after reviewing feeder visit.",
        },
    )

    assert response.status_code == 201
    result = response.json()
    assert result["review_queue_count"] == 0
    assert result["analytics"]["needs_review_count"] < before_analytics["needs_review_count"]
    assert result["analytics"]["species_counts"]["carolina_wren"] == 1
    assert "northern_cardinal" not in result["analytics"]["species_counts"]

    visit_response = client.get(f"/api/visits/{BIRD_VISIT_ID}")
    visit = visit_response.json()
    assert visit["review_status"] == "reviewed"
    assert visit["reviewed_label"] == "carolina_wren"

    event_response = client.get(f"/api/events/{BIRD_EVENT_ID}")
    assert event_response.json()["review_status"] == "reviewed"

    queue_response = client.get("/api/review-queue")
    assert all(item["visit_id"] != BIRD_VISIT_ID for item in queue_response.json())

    analytics_response = client.get("/api/analytics/summary")
    analytics = analytics_response.json()
    assert analytics["needs_review_count"] < before_analytics["needs_review_count"]
    assert analytics["species_counts"]["carolina_wren"] == 1


def test_unsupported_review_target_type_returns_400() -> None:
    response = client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "stream",
            "target_id": STREAM_ID,
            "label": "not_a_review_target",
        },
    )

    assert response.status_code == 400
    assert "Unsupported review target_type 'stream'" in response.json()["detail"]


def test_missing_review_target_returns_404() -> None:
    response = client.post(
        "/api/review-labels",
        json={"review_origin": "human",
            "target_type": "visit",
            "target_id": "visit-missing",
            "label": "carolina_wren",
        },
    )

    assert response.status_code == 404
    assert "Visit 'visit-missing' was not found." == response.json()["detail"]


# Review Provenance Validation & API Error Semantics v1: the v9 field
# session found that `POST /api/review-labels` with `review_origin=
# "agent_diagnostic"` and no `reviewer_identity` correctly raises
# `ReviewProvenanceError` deep in `product_repository.py`, but the endpoint
# only caught `ReviewRevisionConflictError`, so this well-formed validation
# error reached the client as an unhandled `500` instead of a clean `400`.
# These tests exercise the real HTTP endpoint end to end (not the domain
# function directly -- see `tests/test_review_decision_provenance.py` for
# that coverage) so a regression here is caught at the boundary that
# actually broke.


def test_review_label_agent_diagnostic_without_reviewer_identity_returns_clean_400() -> None:
    response = client.post(
        "/api/review-labels",
        json={
            "review_origin": "agent_diagnostic",
            "target_type": "visit",
            "target_id": BIRD_VISIT_ID,
            "label": "carolina_wren",
            "notes": "diagnostic pass, no reviewer_identity supplied",
        },
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail == "agent_diagnostic_requires_reviewer_identity"
    # No traceback/internal exception plumbing leaked to the client.
    assert "Traceback" not in detail
    assert ".py" not in detail

    # The rejected request never persisted a row or touched Reviewed truth.
    # `detail["review_labels"]`/`GET /api/review-labels` both only resolve
    # the current *authoritative* row per target (see `_effective_review_
    # label_models`'s own docstring) -- a leaked `agent_diagnostic` row
    # would never appear there even if one existed. `correction_history`
    # (`_review_label_history_models_for_visit`) is the raw, unfiltered-by
    # -authority per-Visit history, so it is the one API-visible place that
    # can actually prove nothing was persisted.
    detail = client.get(f"/api/visits/{BIRD_VISIT_ID}/detail").json()
    assert detail["review_labels"] == []
    assert detail["correction_history"] == []
    visit = detail["visit"]
    assert visit["review_status"] == "needs_review"
    assert visit["reviewed_label"] is None


def test_review_label_agent_diagnostic_with_reviewer_identity_is_accepted_but_not_authoritative() -> None:
    response = client.post(
        "/api/review-labels",
        json={
            "review_origin": "agent_diagnostic",
            "reviewer_identity": "claude-review-agent-v1",
            "target_type": "visit",
            "target_id": BIRD_VISIT_ID,
            "label": "carolina_wren",
            "notes": "diagnostic pass",
        },
    )

    assert response.status_code == 201
    result = response.json()
    label = result["review_label"]
    assert label["review_origin"] == "agent_diagnostic"
    assert label["reviewer_identity"] == "claude-review-agent-v1"
    assert label["is_authoritative"] is False
    # Provenance requirement stays strict even once satisfied: a diagnostic
    # assessment is durably recorded but never becomes Reviewed truth.
    assert result["visit"]["review_status"] == "needs_review"
    assert result["visit"]["reviewed_label"] is None

    # `detail["review_labels"]` only resolves the current *authoritative*
    # row per target (see `_effective_review_label_models`'s own
    # docstring), so the non-authoritative diagnostic row just created is
    # correctly absent from it by design -- it is still durably recorded,
    # visible instead in this Visit's own raw, unfiltered `correction_
    # history` (`_review_label_history_models_for_visit`).
    detail = client.get(f"/api/visits/{BIRD_VISIT_ID}/detail").json()
    assert detail["review_labels"] == []
    assert len(detail["correction_history"]) == 1
    entry = detail["correction_history"][0]
    assert entry["review_origin"] == "agent_diagnostic"
    assert entry["is_authoritative"] is False
    assert entry["label"] == "carolina_wren"


def test_review_label_imported_curated_without_reviewer_identity_returns_clean_400() -> None:
    # Same `ReviewProvenanceError` boundary, a different `IDENTITY_REQUIRED_
    # ORIGINS` member -- confirms the fix is generic to review-provenance
    # validation, not a special case for `agent_diagnostic` alone.
    response = client.post(
        "/api/review-labels",
        json={
            "review_origin": "imported_curated",
            "target_type": "visit",
            "target_id": BIRD_VISIT_ID,
            "label": "carolina_wren",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "imported_curated_requires_reviewer_identity"
    assert all(label["target_id"] != BIRD_VISIT_ID for label in client.get("/api/review-labels").json())


def test_review_label_human_origin_conflicting_with_disclosed_non_human_notes_returns_clean_400() -> None:
    response = client.post(
        "/api/review-labels",
        json={
            "review_origin": "human",
            "target_type": "visit",
            "target_id": BIRD_VISIT_ID,
            "label": "carolina_wren",
            "notes": "[AGENT VISUAL REVIEW: looks like a Carolina Wren, not independently human-confirmed]",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "human_origin_conflicts_with_disclosed_non_human_review"
    assert all(label["target_id"] != BIRD_VISIT_ID for label in client.get("/api/review-labels").json())


def test_failed_provenance_validation_does_not_overwrite_existing_reviewed_truth() -> None:
    valid = client.post(
        "/api/review-labels",
        json={
            "review_origin": "human",
            "target_type": "visit",
            "target_id": BIRD_VISIT_ID,
            "label": "northern_cardinal",
            "notes": "Confirmed by the operator.",
        },
    )
    assert valid.status_code == 201

    failed = client.post(
        "/api/review-labels",
        json={
            "review_origin": "agent_diagnostic",
            "target_type": "visit",
            "target_id": BIRD_VISIT_ID,
            "label": "carolina_wren",
        },
    )
    assert failed.status_code == 400

    visit = client.get(f"/api/visits/{BIRD_VISIT_ID}").json()
    assert visit["review_status"] == "reviewed"
    assert visit["reviewed_label"] == "northern_cardinal"

    labels = client.get("/api/review-labels").json()
    bird_labels = [label for label in labels if label["target_id"] == BIRD_VISIT_ID]
    assert len(bird_labels) == 1
    assert bird_labels[0]["label"] == "northern_cardinal"


def test_failed_provenance_validation_creates_no_review_corrected_audit_entry(
    isolated_repository: ProductRepository,
) -> None:
    response = client.post(
        "/api/review-labels",
        json={
            "review_origin": "agent_diagnostic",
            "target_type": "visit",
            "target_id": BIRD_VISIT_ID,
            "label": "carolina_wren",
        },
    )
    assert response.status_code == 400

    audit_entries = isolated_repository.list_audit_log()
    assert not any(
        entry.action == "review.corrected" and entry.target_id == BIRD_VISIT_ID
        for entry in audit_entries
    )


def test_unexpected_review_label_exception_still_surfaces_as_a_server_error(
    monkeypatch: pytest.MonkeyPatch, isolated_repository: ProductRepository,
) -> None:
    """The new `except ReviewProvenanceError` clause must not widen into a
    generic `except Exception` -> 400. An unrelated, genuinely unexpected
    exception from the repository call must remain unmasked."""

    def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("unexpected_repository_failure")

    monkeypatch.setattr(isolated_repository, "create_review_label", _boom)

    with pytest.raises(RuntimeError, match="unexpected_repository_failure"):
        client.post(
            "/api/review-labels",
            json={
                "review_origin": "agent_diagnostic",
                "reviewer_identity": "claude-review-agent-v1",
                "target_type": "visit",
                "target_id": BIRD_VISIT_ID,
                "label": "carolina_wren",
            },
        )


def test_dataset_exports_endpoint_returns_export() -> None:
    response = client.get("/api/dataset-exports")

    assert response.status_code == 200
    exports = response.json()
    assert exports[0]["status"] == "ready"
    assert exports[0]["reviewed_only"] is True
    assert exports[0]["record_count"] >= 1


def test_post_dataset_exports_creates_export() -> None:
    response = client.post(
        "/api/dataset-exports",
        json={
            "name": "Reviewed local dataset",
            "reviewed_only": True,
            "include_detections": True,
            "include_zone_context": True,
        },
    )

    assert response.status_code == 201
    detail = response.json()
    assert detail["export"]["name"] == "Reviewed local dataset"
    assert detail["export"]["status"] == "ready"
    assert detail["export"]["reviewed_only"] is True
    assert detail["export"]["record_count"] == len(detail["manifest"]["records"])
    assert detail["manifest"]["skipped_reasons"]["needs_review"] == 1


def test_dataset_export_manifest_includes_reviewed_squirrel_record() -> None:
    response = client.get(f"/api/dataset-exports/{SEED_EXPORT_ID}/manifest")

    assert response.status_code == 200
    manifest = response.json()
    squirrel_record = next(
        record for record in manifest["records"] if record["visit_id"] == SQUIRREL_VISIT_ID
    )
    assert squirrel_record["label"] == "squirrel"
    assert squirrel_record["subject_label"] == "squirrel"
    assert squirrel_record["reviewed"] is True
    assert squirrel_record["dataset_ready"] is True
    assert squirrel_record["media_path"] == "demo://backyard-feeder/squirrel-ground-001.jpg"


def test_dataset_export_detail_returns_manifest() -> None:
    response = client.get(f"/api/dataset-exports/{SEED_EXPORT_ID}")

    assert response.status_code == 200
    detail = response.json()
    assert detail["export"]["id"] == SEED_EXPORT_ID
    assert detail["manifest"]["export"]["id"] == SEED_EXPORT_ID
    assert detail["manifest"]["records"]


def test_dataset_export_manifest_skips_visit_still_needing_review() -> None:
    response = client.get(f"/api/dataset-exports/{SEED_EXPORT_ID}/manifest")

    assert response.status_code == 200
    manifest = response.json()
    assert all(record["visit_id"] != BIRD_VISIT_ID for record in manifest["records"])
    assert manifest["skipped_count"] == 1
    assert manifest["skipped_reasons"]["needs_review"] == 1


def test_corrected_visit_appears_in_new_dataset_export_manifest() -> None:
    client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": BIRD_VISIT_ID,
            "label": "northern_cardinal",
            "notes": "Confirmed for export.",
        },
    )

    response = client.post(
        "/api/dataset-exports",
        json={"name": "Reviewed birds and yard"},
    )

    assert response.status_code == 201
    manifest = response.json()["manifest"]
    assert manifest["skipped_count"] == 0
    assert any(
        record["visit_id"] == BIRD_VISIT_ID
        and record["label"] == "northern_cardinal"
        and record["dataset_ready"] is True
        for record in manifest["records"]
    )


def test_dataset_export_manifest_includes_zone_context() -> None:
    response = client.get(f"/api/dataset-exports/{SEED_EXPORT_ID}/manifest")

    assert response.status_code == 200
    manifest = response.json()
    squirrel_record = next(
        record for record in manifest["records"] if record["visit_id"] == SQUIRREL_VISIT_ID
    )
    assert squirrel_record["zone_id"] == "zone-ground"
    assert squirrel_record["zone_name"] == "Ground below feeder"
    assert squirrel_record["zone_type"] == "ground"


def test_dataset_export_manifest_includes_detections_when_requested() -> None:
    response = client.get(f"/api/dataset-exports/{SEED_EXPORT_ID}/manifest")

    assert response.status_code == 200
    manifest = response.json()
    squirrel_record = next(
        record for record in manifest["records"] if record["visit_id"] == SQUIRREL_VISIT_ID
    )
    assert squirrel_record["detections"][0]["label"] == "squirrel"
    assert squirrel_record["detections"][0]["confidence"] == 0.91


def test_dataset_export_manifest_omits_detections_when_disabled() -> None:
    response = client.post(
        "/api/dataset-exports",
        json={
            "name": "Reviewed labels only",
            "include_detections": False,
        },
    )

    assert response.status_code == 201
    manifest = response.json()["manifest"]
    assert manifest["records"]
    assert all(record["detections"] == [] for record in manifest["records"])


def test_unknown_dataset_export_detail_and_manifest_return_404() -> None:
    unknown_export_paths = [
        "/api/dataset-exports/dataset-export-missing",
        "/api/dataset-exports/dataset-export-missing/manifest",
    ]

    for path in unknown_export_paths:
        response = client.get(path)
        assert response.status_code == 404
        assert "Dataset export 'dataset-export-missing' was not found." == response.json()["detail"]


def test_dataset_export_mutations_do_not_leak_between_tests() -> None:
    response = client.get("/api/dataset-exports")

    assert response.status_code == 200
    assert [dataset_export["id"] for dataset_export in response.json()] == [SEED_EXPORT_ID]


def test_analytics_summary_includes_product_counts() -> None:
    response = client.get("/api/analytics/summary")

    assert response.status_code == 200
    summary = response.json()
    assert summary["event_count"] == 2
    assert summary["visit_count"] == 2
    assert summary["needs_review_count"] >= 1
    assert summary["zone_activity_counts"][FEEDER_ZONE_ID] >= 1


def test_local_data_status_reports_persisted_product_counts() -> None:
    response = client.get("/api/settings/local-data")

    assert response.status_code == 200
    status = response.json()
    assert status["database_ready"] is True
    assert status["database_schema_version"] == status["database_schema_current_version"]
    assert status["database_integrity_check"] == "ok"
    assert status["seed_data_present"] is True
    assert status["using_default_database"] is False
    assert status["database_url"].startswith("sqlite:///")
    assert status["database_path"].endswith("mockingbird.sqlite3")
    assert status["source_count"] == 1
    assert status["stream_count"] == 1
    assert status["zone_count"] == 3
    assert status["event_count"] == 2
    assert status["visit_count"] == 2
    assert status["media_asset_count"] == 0
    assert status["review_label_count"] == 1
    assert status["dataset_export_count"] == 1
    assert status["needs_review_count"] >= 1
    assert "stored here on this device" in status["local_first_note"]


def test_reset_demo_data_restores_seed_state_after_mutations() -> None:
    created_zone = client.post(
        "/api/zones",
        json={
            "stream_id": STREAM_ID,
            "name": "Temporary yard zone",
            "zone_type": "yard",
            "polygon": [
                {"x": 0.12, "y": 0.12},
                {"x": 0.24, "y": 0.12},
                {"x": 0.24, "y": 0.24},
            ],
        },
    ).json()["zone"]
    client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": BIRD_VISIT_ID,
            "label": "carolina_wren",
        },
    )
    temporary_export = client.post(
        "/api/dataset-exports",
        json={"name": "Temporary reviewed dataset"},
    ).json()["export"]

    mutated_status = client.get("/api/settings/local-data").json()
    assert mutated_status["zone_count"] == 4
    assert mutated_status["review_label_count"] == 2
    assert mutated_status["dataset_export_count"] == 2

    response = client.post("/api/settings/reset-demo-data")

    assert response.status_code == 200
    status = response.json()
    assert status["database_ready"] is True
    assert status["seed_data_present"] is True
    assert status["zone_count"] == 3
    assert status["review_label_count"] == 1
    assert status["dataset_export_count"] == 2
    # Analytics & Local Data Truth Consistency v1: `needs_review_count` is
    # reused from `_analytics_summary`, which excludes the seeded demo
    # Source's own activity -- the reseeded demo bird Visit's raw
    # `review_status` genuinely is restored to `needs_review` (proven
    # directly below), but it must not surface as real outstanding work on
    # a reset-to-demo-only install with zero real cameras.
    assert status["needs_review_count"] == 0

    zones = client.get(f"/api/streams/{STREAM_ID}/zones").json()
    assert all(zone["id"] != created_zone["id"] for zone in zones)
    assert client.get(f"/api/visits/{BIRD_VISIT_ID}").json()["review_status"] == "needs_review"
    assert {item["id"] for item in client.get("/api/dataset-exports").json()} == {
        SEED_EXPORT_ID,
        temporary_export["id"],
    }


def test_reset_demo_data_does_not_duplicate_seed_rows() -> None:
    first_response = client.post("/api/settings/reset-demo-data")
    second_response = client.post("/api/settings/reset-demo-data")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    status = second_response.json()
    assert status["source_count"] == 1
    assert status["stream_count"] == 1
    assert status["zone_count"] == 3
    # Analytics & Local Data Truth Consistency v1: `event_count`/
    # `visit_count` are reused from `_analytics_summary`, which excludes
    # the seeded demo Source's own activity -- always 0 on a demo-only
    # install regardless of how many times it is reseeded. Non-duplication
    # itself is still fully proven by `zone_count`/`review_label_count`
    # above/below, neither of which is demo-filtered.
    assert status["event_count"] == 0
    assert status["visit_count"] == 0
    assert status["media_asset_count"] == 0
    assert status["review_label_count"] == 1
    assert status["dataset_export_count"] == 1


def test_unknown_event_visit_and_zone_ids_return_404() -> None:
    unknown_paths = [
        "/api/events/event-missing",
        "/api/visits/visit-missing",
        "/api/zones/zone-missing",
    ]

    for path in unknown_paths:
        response = client.get(path)
        assert response.status_code == 404
        assert "was not found" in response.json()["detail"]


def test_unknown_nested_route_parents_return_404() -> None:
    unknown_parent_paths = [
        "/api/sources/source-missing/streams",
        "/api/streams/stream-missing/zones",
        "/api/streams/stream-missing/events",
        "/api/events/event-missing/visits",
    ]

    for path in unknown_parent_paths:
        response = client.get(path)
        assert response.status_code == 404
        assert "was not found" in response.json()["detail"]
