from fastapi.testclient import TestClient

from mockingbird.api.main import app


client = TestClient(app)

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
BIRD_EVENT_ID = "event-bird-feeder-001"
BIRD_VISIT_ID = "visit-bird-feeder-001"
SQUIRREL_VISIT_ID = "visit-squirrel-ground-001"


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


def test_stream_events_returns_stream_events() -> None:
    response = client.get(f"/api/streams/{STREAM_ID}/events")

    assert response.status_code == 200
    events = response.json()
    assert {event["id"] for event in events} >= {
        "event-bird-feeder-001",
        "event-squirrel-ground-001",
    }
    assert all(event["stream_id"] == STREAM_ID for event in events)


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


def test_review_queue_includes_bird_visit_needing_review() -> None:
    response = client.get("/api/review-queue")

    assert response.status_code == 200
    queue = response.json()
    bird_item = next(item for item in queue if item["visit_id"] == BIRD_VISIT_ID)
    assert bird_item["item_type"] == "visit"
    assert bird_item["stream_id"] == STREAM_ID
    assert bird_item["event_id"] == BIRD_EVENT_ID
    assert bird_item["primary_zone_id"] == FEEDER_ZONE_ID
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
        json={
            "target_type": "visit",
            "target_id": "visit-bird-feeder-001",
            "label": "northern_cardinal",
            "notes": "Confirmed during review.",
        },
    )

    assert response.status_code == 201
    label = response.json()
    assert label["target_type"] == "visit"
    assert label["target_id"] == BIRD_VISIT_ID
    assert label["label"] == "northern_cardinal"
    assert label["created_at"]

    labels_response = client.get("/api/review-labels")
    labels = labels_response.json()
    assert any(
        item["target_id"] == BIRD_VISIT_ID
        and item["label"] == "northern_cardinal"
        for item in labels
    )


def test_dataset_exports_endpoint_returns_export() -> None:
    response = client.get("/api/dataset-exports")

    assert response.status_code == 200
    exports = response.json()
    assert exports[0]["status"] == "ready"
    assert exports[0]["reviewed_only"] is True
    assert exports[0]["record_count"] >= 1


def test_analytics_summary_includes_product_counts() -> None:
    response = client.get("/api/analytics/summary")

    assert response.status_code == 200
    summary = response.json()
    assert summary["event_count"] == 2
    assert summary["visit_count"] == 2
    assert summary["needs_review_count"] >= 1
    assert summary["zone_activity_counts"][FEEDER_ZONE_ID] >= 1


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
