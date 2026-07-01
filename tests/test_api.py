from fastapi.testclient import TestClient

from mockingbird.api.main import app


client = TestClient(app)


def test_health_endpoint_works() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_sources_returns_demo_source() -> None:
    response = client.get("/api/sources")

    assert response.status_code == 200
    sources = response.json()
    assert sources[0]["id"] == "source-backyard-demo"
    assert sources[0]["kind"] == "demo"
    assert "product flow" in sources[0]["description"]


def test_streams_return_product_centered_stream() -> None:
    response = client.get("/api/streams")

    assert response.status_code == 200
    streams = response.json()
    assert streams[0]["source_id"] == "source-backyard-demo"
    assert streams[0]["name"] == "Backyard feeder stream"
    assert "feeder" in streams[0]["description"]
    assert streams[0]["is_live"] is True


def test_zones_include_feeder_ground_and_ignore_zones() -> None:
    response = client.get("/api/zones")

    assert response.status_code == 200
    zone_types = {zone["zone_type"] for zone in response.json()}
    assert {"feeder", "ground", "ignore"}.issubset(zone_types)


def test_events_are_reviewable_and_include_detections() -> None:
    response = client.get("/api/events")

    assert response.status_code == 200
    events = response.json()
    assert {event["review_status"] for event in events} >= {"needs_review", "reviewed"}
    assert all(event["detections"] for event in events)
    assert events[0]["detections"][0]["label"] == "unknown_bird"


def test_visits_include_bird_visit_needing_review() -> None:
    response = client.get("/api/visits")

    assert response.status_code == 200
    visits = response.json()
    bird_visits = [visit for visit in visits if visit["subject_label"] == "bird"]
    assert bird_visits
    assert bird_visits[0]["review_status"] == "needs_review"
    assert bird_visits[0]["species_guess"] == "northern_cardinal"


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
    assert label["target_id"] == "visit-bird-feeder-001"
    assert label["label"] == "northern_cardinal"
    assert label["created_at"]

    labels_response = client.get("/api/review-labels")
    labels = labels_response.json()
    assert any(
        item["target_id"] == "visit-bird-feeder-001"
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
    assert summary["visit_count"] == 1
    assert summary["needs_review_count"] >= 1
    assert summary["zone_activity_counts"]["zone-feeder"] >= 1
