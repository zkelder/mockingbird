"""Working App v1: Visit evidence gallery.

Real field evidence (visit-motion-204, visit-motion-211 in the development
database) showed a reviewer a saved primary "activity_crop" that was an
empty, off-target close-up, while three OTHER already-saved frames on the
exact same Visit (a `tracked_best_frame`, `pretrigger`, and
`high_resolution_original`) plainly showed the real bird. Visit Detail's
gallery must (a) always expose every already-saved frame, never inventing a
new one, and (b) default to a more useful already-saved frame when the
persisted primary is a poor pick -- without ever rewriting `is_primary` or
any other persisted evidence-selection fact.

These are API/contract tests: they pin the exact JSON shape
(`evidence_frames` + `effective_primary`) the frontend gallery
(`VisitEvidenceSequence`, `VisitDetailPage`) depends on. They do not touch
detection, tracking, or evidence-selection policy -- `effective_primary` is
a pre-existing, bounded, deterministic read
(`mockingbird.motion.effective_primary.select_effective_primary`) over
already-saved evidence, not new selection logic.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import EventModel, VisitEvidenceLinkModel, VisitModel


SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
client = TestClient(app)


@pytest.fixture
def evidence_repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    yield repository
    configure_repository(None)
    repository.close()


def _jpeg(width: int, height: int, fill: int) -> bytes:
    image = np.full((height, width, 3), fill, dtype=np.uint8)
    encoded, output = cv2.imencode(".jpg", image)
    assert encoded
    return output.tobytes()


def _seed_visit(repository: ProductRepository, visit_id: str, *, zone_id: str | None) -> None:
    with repository.session_factory() as session:
        with session.begin():
            event = EventModel(
                id=f"event-{visit_id}",
                stream_id=STREAM_ID,
                title="Live motion activity fixture",
                event_type="motion_evidence",
                started_at=datetime.now(UTC),
                ended_at=datetime.now(UTC),
                primary_zone_id=zone_id,
                review_status="needs_review",
            )
            session.add(event)
            session.add(
                VisitModel(
                    id=visit_id,
                    event_id=event.id,
                    subject_label="unknown_bird",
                    species_guess=None,
                    confidence=None,
                    reviewed_label=None,
                    review_status="needs_review",
                    representative_media_path=None,
                    zone_id=zone_id,
                    is_superseded=False,
                )
            )


def _attach_links_directly(
    repository: ProductRepository,
    visit_id: str,
    frames: list[dict[str, object]],
) -> None:
    """Persist `visit_evidence_links` rows exactly as written, bypassing
    `attach_visit_evidence_media_assets`'s own write-time
    `select_effective_primary` self-correction.

    The real production defect this milestone repairs (visit-motion-204,
    visit-motion-211) is a *persisted* `is_primary` that the read-time
    `effective_primary_preview` recommendation disagrees with -- proof that
    at least one real write path sets `is_primary` without running that same
    check. Routing every test Visit through the one helper that already
    self-corrects at write time would make that disagreement unreachable in
    a test and would silently stop covering the real bug. This mirrors the
    exact row shape already observed in the real development database.
    """

    created_at = datetime.now(UTC)
    with repository.session_factory() as session:
        with session.begin():
            for sort_order, frame in enumerate(frames):
                session.add(
                    VisitEvidenceLinkModel(
                        id=f"visit-evidence-{visit_id}-{sort_order}",
                        visit_id=visit_id,
                        media_asset_id=frame["media_asset_id"],
                        captured_at=frame["captured_at"],
                        frame_sequence=frame.get("frame_sequence"),
                        sort_order=sort_order,
                        is_primary=bool(frame["is_primary"]),
                        evidence_role=frame["evidence_role"],
                        created_at=created_at,
                    )
                )


def _build_off_target_visit(repository: ProductRepository, visit_id: str) -> dict[str, str]:
    """Reproduce the real visit-motion-204/211 evidence shape: a persisted
    `activity_crop` primary whose own padded crop box does not contain the
    track box it was supposedly cropped from (an off-target, birdless crop),
    plus a `tracked_best_frame`, `pretrigger`, and `high_resolution_original`
    that all really do cover the tracked subject.
    """

    _seed_visit(repository, visit_id, zone_id="zone-feeder")
    base = datetime(2026, 8, 2, 17, 0, 10, tzinfo=UTC)
    track_box = (0.4593, 0.6218, 0.4889, 0.6676)

    pretrigger = repository.create_live_motion_frame_media_asset(
        source_id=SOURCE_ID,
        stream_id=STREAM_ID,
        content=_jpeg(320, 240, 40),
        captured_at=base,
        frame_sequence=6919,
        evidence_role="pretrigger",
        image_width=320,
        image_height=240,
    )
    tracked = repository.create_live_motion_frame_media_asset(
        source_id=SOURCE_ID,
        stream_id=STREAM_ID,
        content=_jpeg(1920, 1440, 60),
        captured_at=base + timedelta(seconds=2.5),
        frame_sequence=6921,
        evidence_role="tracked_best_frame",
        image_width=1920,
        image_height=1440,
    )
    full = repository.create_live_motion_frame_media_asset(
        source_id=SOURCE_ID,
        stream_id=STREAM_ID,
        content=_jpeg(4624, 3472, 80),
        captured_at=base + timedelta(seconds=8.5),
        frame_sequence=6921,
        evidence_role="high_resolution_original",
        image_width=4624,
        image_height=3472,
        normalized_track_box=track_box,
        alignment_status="aligned",
    )
    # The padded crop box is nowhere near the recorded track box -- exactly
    # the real, off-target/birdless-crop defect this milestone repairs.
    crop = repository.create_live_motion_frame_media_asset(
        source_id=SOURCE_ID,
        stream_id=STREAM_ID,
        content=_jpeg(234, 271, 20),
        captured_at=base + timedelta(seconds=8.5),
        frame_sequence=6921,
        parent_media_asset_id=full.id,
        evidence_role="activity_crop",
        image_width=234,
        image_height=271,
        normalized_track_box=track_box,
        normalized_padded_crop_box=(0.02, 0.02, 0.10, 0.10),
        alignment_status="aligned",
    )

    _attach_links_directly(
        repository,
        visit_id,
        [
            {
                "media_asset_id": pretrigger.id,
                "captured_at": pretrigger.created_at,
                "frame_sequence": 6919,
                "is_primary": False,
                "evidence_role": "pretrigger",
            },
            {
                "media_asset_id": tracked.id,
                "captured_at": tracked.created_at,
                "frame_sequence": 6921,
                "is_primary": False,
                "evidence_role": "tracked_best_frame",
            },
            {
                "media_asset_id": full.id,
                "captured_at": full.created_at,
                "frame_sequence": 6921,
                "is_primary": False,
                "evidence_role": "high_resolution_original",
            },
            {
                "media_asset_id": crop.id,
                "captured_at": crop.created_at,
                "frame_sequence": 6921,
                "is_primary": True,
                "evidence_role": "activity_crop",
            },
        ],
    )
    return {
        "pretrigger": pretrigger.id,
        "tracked": tracked.id,
        "full": full.id,
        "crop": crop.id,
    }


def test_off_target_primary_crop_yields_a_useful_different_recommendation(
    evidence_repository: ProductRepository,
) -> None:
    ids = _build_off_target_visit(evidence_repository, "visit-gallery-off-target")

    response = client.get("/api/visits/visit-gallery-off-target/detail")
    assert response.status_code == 200
    body = response.json()

    # Every already-saved frame is still exposed -- nothing invented, nothing
    # dropped. The persisted primary fact is untouched.
    assert {frame["media_asset_id"] for frame in body["evidence_frames"]} == set(ids.values())
    primary_frames = [frame for frame in body["evidence_frames"] if frame["is_primary"]]
    assert [frame["media_asset_id"] for frame in primary_frames] == [ids["crop"]]

    effective_primary = body["effective_primary"]
    assert effective_primary is not None
    assert effective_primary["persisted_primary_media_asset_id"] == ids["crop"]
    assert effective_primary["recommended_effective_primary_media_asset_id"] == ids["tracked"]
    assert effective_primary["selection_reason"] == "tracked_best_frame_preferred"
    assert effective_primary["is_useful"] is True
    assert effective_primary["would_change_automatically"] is True
    assert effective_primary["historical_preview_only"] is True


def test_already_correct_primary_needs_no_override(
    evidence_repository: ProductRepository,
) -> None:
    """The mirror-image case: when the persisted primary is already the
    frame `select_effective_primary` would itself pick, the recommendation
    agrees with it and the gallery has nothing to override -- confirming
    this feature changes nothing for Visits that are already fine (the
    overwhelming majority; only 2 of 235 real development-database Visits
    surveyed while building this fix showed the disagreement it repairs).
    """

    visit_id = "visit-gallery-already-correct"
    _seed_visit(evidence_repository, visit_id, zone_id="zone-feeder")
    captured_at = datetime.now(UTC)
    tracked = evidence_repository.create_live_motion_frame_media_asset(
        source_id=SOURCE_ID,
        stream_id=STREAM_ID,
        content=_jpeg(1920, 1440, 60),
        captured_at=captured_at,
        frame_sequence=1,
        evidence_role="tracked_best_frame",
        image_width=1920,
        image_height=1440,
    )
    pretrigger = evidence_repository.create_live_motion_frame_media_asset(
        source_id=SOURCE_ID,
        stream_id=STREAM_ID,
        content=_jpeg(320, 240, 30),
        captured_at=captured_at - timedelta(seconds=2),
        frame_sequence=0,
        evidence_role="pretrigger",
        image_width=320,
        image_height=240,
    )
    _attach_links_directly(
        evidence_repository,
        visit_id,
        [
            {
                "media_asset_id": pretrigger.id,
                "captured_at": pretrigger.created_at,
                "frame_sequence": 0,
                "is_primary": False,
                "evidence_role": "pretrigger",
            },
            {
                "media_asset_id": tracked.id,
                "captured_at": tracked.created_at,
                "frame_sequence": 1,
                "is_primary": True,
                "evidence_role": "tracked_best_frame",
            },
        ],
    )

    response = client.get(f"/api/visits/{visit_id}/detail")
    assert response.status_code == 200
    effective_primary = response.json()["effective_primary"]
    assert effective_primary["persisted_primary_media_asset_id"] == tracked.id
    assert effective_primary["recommended_effective_primary_media_asset_id"] == tracked.id
    assert effective_primary["selection_reason"] == "tracked_best_frame_preferred"
    assert effective_primary["is_useful"] is True
    assert effective_primary["would_change_automatically"] is False
    assert effective_primary["historical_preview_only"] is False


def test_single_evidence_frame_visit_has_no_recommendation_to_show(
    evidence_repository: ProductRepository,
) -> None:
    """A Visit with exactly one saved frame must stay simple: one candidate
    can never disagree with itself, so the gallery has nothing to add."""

    visit_id = "visit-gallery-single-frame"
    _seed_visit(evidence_repository, visit_id, zone_id="zone-feeder")
    asset = evidence_repository.create_live_motion_frame_media_asset(
        source_id=SOURCE_ID,
        stream_id=STREAM_ID,
        content=_jpeg(640, 480, 50),
        captured_at=datetime.now(UTC),
        frame_sequence=1,
        evidence_role="tracked_best_frame",
        image_width=640,
        image_height=480,
    )
    evidence_repository.attach_visit_evidence_media_assets(
        visit_id,
        [
            {
                "media_asset_id": asset.id,
                "captured_at": asset.created_at,
                "frame_sequence": 1,
                "is_primary": True,
                "evidence_role": "tracked_best_frame",
            },
        ],
    )

    response = client.get(f"/api/visits/{visit_id}/detail")
    assert response.status_code == 200
    body = response.json()
    assert len(body["evidence_frames"]) == 1
    assert body["evidence_frames"][0]["is_primary"] is True
    effective_primary = body["effective_primary"]
    assert effective_primary["persisted_primary_media_asset_id"] == asset.id
    assert effective_primary["recommended_effective_primary_media_asset_id"] == asset.id
    assert effective_primary["would_change_automatically"] is False


def test_legacy_zero_link_visit_reports_no_effective_primary(
    evidence_repository: ProductRepository,
) -> None:
    """Older Visits with no `visit_evidence_links` rows at all (evidence
    resolved only through `representative_media_path`) legitimately have no
    `effective_primary` preview -- the gallery must treat that as "nothing to
    recommend," never crash or silently invent one.
    """

    visit_id = "visit-gallery-legacy-single"
    with evidence_repository.session_factory() as session:
        with session.begin():
            event = EventModel(
                id="event-gallery-legacy-single",
                stream_id=STREAM_ID,
                title="Legacy manual media visit",
                event_type="manual_media_import",
                started_at=datetime.now(UTC),
                ended_at=datetime.now(UTC),
                primary_zone_id=None,
                review_status="needs_review",
            )
            session.add(event)
    result = client.post(
        "/api/media/import",
        files={"file": ("legacy.jpg", _jpeg(200, 200, 90), "image/jpeg")},
        data={"stream_id": STREAM_ID, "subject_label": "unknown_bird"},
    )
    assert result.status_code == 201
    legacy_visit_id = result.json()["visit"]["id"]

    response = client.get(f"/api/visits/{legacy_visit_id}/detail")
    assert response.status_code == 200
    body = response.json()
    assert len(body["evidence_frames"]) == 1
    assert body["effective_primary"] is None


def test_missing_media_file_is_reported_unavailable_without_losing_other_frames(
    evidence_repository: ProductRepository,
) -> None:
    """One damaged/missing saved asset must degrade honestly, and must never
    take the rest of a Visit's saved evidence down with it."""

    ids = _build_off_target_visit(evidence_repository, "visit-gallery-missing-asset")
    missing_path = evidence_repository.media_file_path(ids["tracked"])
    assert missing_path is not None and missing_path.exists()
    missing_path.unlink()

    detail_response = client.get("/api/visits/visit-gallery-missing-asset/detail")
    assert detail_response.status_code == 200
    frame_ids = {frame["media_asset_id"] for frame in detail_response.json()["evidence_frames"]}
    # The Visit's evidence listing itself is unaffected by one missing file.
    assert frame_ids == set(ids.values())

    broken_preview = client.get(f"/api/media/{ids['tracked']}/preview")
    assert broken_preview.status_code == 404

    healthy_preview = client.get(f"/api/media/{ids['crop']}/preview")
    assert healthy_preview.status_code == 200
    assert healthy_preview.headers["content-type"].startswith("image/jpeg")
