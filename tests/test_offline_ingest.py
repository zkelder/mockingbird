"""Tier 2 tests for `mockingbird.observation.offline_ingest` -- Offline /
Recorded Observation Ingest v1. Drives the real, unmodified detection/
tracking/assembly/admission stack against an isolated `tmp_path` repository
and a real ffmpeg-decoded synthetic clip, with an injected fake detector
(mirroring `tests/test_observation_frame_driven.py::FakeDetector` -- no real
CUDA/model bundle is available in this environment, matching this
codebase's established hardware-adjacent testing convention).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.api.schemas import ReviewCorrectionCreate
from mockingbird.observation import offline_ingest
from mockingbird.observation.contracts import DetectionObservation, FramePacket
from mockingbird.observation.frame_driven_provider import FrameDrivenObservationProvider
from mockingbird.repository.product_repository import MediaAssetModel, ProductRepository, VisitEvidenceLinkModel
from mockingbird.storage.models import MonitoringExposureIntervalModel, ZoneModel

pytestmark = pytest.mark.anyio

STREAM_ID = "stream-backyard-feeder"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    yield repo
    repo.close()


def _has_real_ffmpeg_suite() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _generate_clip(path: Path, *, duration_seconds: float, creation_time: str | None = None) -> None:
    command = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c=blue:s=128x128:d={duration_seconds}",
    ]
    if creation_time is not None:
        command += ["-metadata", f"creation_time={creation_time}"]
    command += ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)]
    subprocess.run(command, check=True, timeout=30, capture_output=True)


def _seed_media_asset(
    repository: ProductRepository,
    *,
    media_asset_id: str,
    video_path: Path,
    captured_at: datetime | None = None,
    stream_id: str = STREAM_ID,
) -> None:
    """Directly seed one imported-video MediaAsset row, mirroring the exact
    shape the existing folder-import path already produces (this module's
    own correctness is exercised by `tests/test_folder_import_media_assets.py`;
    this only needs an already-imported row to analyze)."""

    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id=media_asset_id, source_id="source-backyard-demo", stream_id=stream_id,
                    filename=video_path.name, content_type="video/mp4", media_type="video",
                    local_path=str(video_path), original_filename=video_path.name,
                    file_size_bytes=video_path.stat().st_size, created_at=datetime.now(UTC),
                    captured_at=captured_at, notes="Test-seeded folder-import video MediaAsset.",
                )
            )


class _FakeDetector:
    """Mirrors `tests/test_observation_frame_driven.py::FakeDetector` --
    the established injected-detector convention for this codebase's
    hardware-adjacent Observation Engine tests (no real CUDA/model bundle
    available in this environment)."""

    def __init__(self, detections_by_frame_id: dict[str, tuple[DetectionObservation, ...]]) -> None:
        self.detections_by_frame_id = detections_by_frame_id
        self.loaded = False

    def probe(self) -> dict[str, object]:
        return {"cuda_available": True, "model_bundle_compatible": True, "runtime_available": True}

    def load(self) -> None:
        self.loaded = True

    async def infer_frame(self, frame: FramePacket) -> tuple[DetectionObservation, ...]:
        assert self.loaded
        return self.detections_by_frame_id.get(frame.frame_id or "", ())

    def finalize_replay(self) -> None:
        pass

    def close(self) -> None:
        self.loaded = False

    def report_metadata(self) -> dict[str, object]:
        return {"model": {"key": "fake", "version": "1"}}

    def execution_facts(self) -> dict[str, object]:
        return {}


def _subject(frame: FramePacket, box: tuple[float, float, float, float]) -> DetectionObservation:
    return _detection_for_frame_id(frame.frame_id, box, captured_at=frame.captured_at)


def _detection_for_frame_id(
    frame_id: str, box: tuple[float, float, float, float], *, captured_at: datetime | None = None,
) -> DetectionObservation:
    return DetectionObservation(
        detector_id="fake:1", label="animal", confidence=0.9,
        captured_at=captured_at or datetime(2024, 5, 1, tzinfo=UTC),
        observation_id=f"detection:{frame_id}:{box}", frame_id=frame_id,
        provider_id="fake", model_key="fake", generation_id=None, bounding_box=box,
        class_source_label="animal", is_animal=True,
    )


def _fake_provider_loader_factory(detections_by_frame_id: dict[str, tuple[DetectionObservation, ...]]):
    fake = _FakeDetector(detections_by_frame_id)

    def _loader(_config_path):
        provider = FrameDrivenObservationProvider(detector=fake)
        provider.load()
        return provider, fake

    return _loader, fake


@pytest.fixture
def four_second_clip(tmp_path: Path) -> Path:
    if not _has_real_ffmpeg_suite():
        pytest.skip("ffmpeg/ffprobe not available in this environment")
    path = tmp_path / "clip.mp4"
    _generate_clip(path, duration_seconds=4.0)
    return path


def _peek_sampled_frame_ids(
    video_path: Path,
    *,
    sample_fps: float,
    stream_id: str = STREAM_ID,
    media_asset_id_prefix: str = "media-video-under-test",
) -> tuple[str, ...]:
    """Small test-only helper: decode once (outside the module under test)
    just to learn what frame ids `run_offline_video_ingest` will itself
    construct, so a test's fake detector can key its canned detections by
    the real, correct frame ids without duplicating the pipeline's own
    decode/id-assignment logic. `media_asset_id_prefix` must match whatever
    `media_asset_id` the real `run_offline_video_ingest` call actually uses
    -- the orchestrator always uses the real MediaAsset id as this prefix."""

    from mockingbird.observation.recorded_video_source import (
        frame_packets_from_recorded_video,
        sample_recorded_video_frames,
    )

    sampling = sample_recorded_video_frames(video_path, sample_fps=sample_fps)
    packets = frame_packets_from_recorded_video(
        sampling, stream_id=stream_id, media_asset_id_prefix=media_asset_id_prefix, capture_start=None,
    )
    return tuple(packet.frame_id for packet in packets)


async def test_offline_ingest_produces_a_visit_from_a_real_decoded_video(
    repository: ProductRepository, four_second_clip: Path,
) -> None:
    _seed_media_asset(repository, media_asset_id="media-video-under-test", video_path=four_second_clip)
    frame_ids = _peek_sampled_frame_ids(four_second_clip, sample_fps=2.0)
    detections = {frame_id: (_subject_for_id(frame_id),) for frame_id in frame_ids}
    loader, _fake = _fake_provider_loader_factory(detections)

    result = await offline_ingest.run_offline_video_ingest(
        repository, media_asset_id="media-video-under-test", sample_fps=2.0, provider_loader=loader,
    )

    assert result.status == "completed"
    assert result.visits_created == 1
    assert result.events_created == 1
    assert result.frames_considered >= 7
    assert result.frames_analyzed == result.frames_considered
    assert len(result.visit_ids) == 1

    visit = repository.get_visit(result.visit_ids[0])
    assert visit.review_status.value == "needs_review"
    # Provisional species remains provisional -- never fabricated on creation.
    assert visit.species_guess is None
    assert visit.reviewed_label is None


def _subject_for_id(frame_id: str) -> DetectionObservation:
    return _detection_for_frame_id(frame_id, (0.2, 0.2, 0.4, 0.4))


async def test_offline_ingest_produces_sibling_visits_for_two_simultaneous_subjects(
    repository: ProductRepository, four_second_clip: Path,
) -> None:
    """Mandatory multi-subject regression (Offline / Recorded Observation
    Ingest v1, "Multi-subject correctness"): two simultaneous, non-
    overlapping subjects throughout one recorded clip must become two
    sibling Visits sharing one Event -- never one collapsed Visit, never
    borrowed sibling evidence."""

    _seed_media_asset(repository, media_asset_id="media-video-under-test", video_path=four_second_clip)
    frame_ids = _peek_sampled_frame_ids(four_second_clip, sample_fps=2.0)
    # Both boxes deliberately sit clear of the demo-seeded Stream's own
    # excluded-region strip (x in [0, 0.18]) -- this test is about
    # multi-subject assembly/admission, not privacy/ignore exclusion (see
    # the dedicated `test_offline_ingest_respects_privacy_zone` for that).
    detections = {
        frame_id: (
            _subject_for_id_at(frame_id, (0.3, 0.05, 0.5, 0.25)),  # "cardinal" -- stationary
            _subject_for_id_at(frame_id, (0.7, 0.7, 0.9, 0.9)),  # "finch" -- stationary
        )
        for frame_id in frame_ids
    }
    loader, _fake = _fake_provider_loader_factory(detections)

    result = await offline_ingest.run_offline_video_ingest(
        repository, media_asset_id="media-video-under-test", sample_fps=2.0, provider_loader=loader,
    )

    assert result.status == "completed"
    assert result.events_created == 1, "both simultaneous subjects must share one Event"
    assert result.visits_created == 2, "two simultaneous distinct subjects must never collapse to one Visit"

    visit_ids = result.visit_ids
    assert len(visit_ids) == 2
    event_ids = {repository.get_visit(visit_id).event_id for visit_id in visit_ids}
    assert len(event_ids) == 1, "sibling Visits must share exactly one Event"

    # Sibling evidence isolation: each Visit's own evidence geometry must
    # reflect only its own subject's box, never the other sibling's.
    boxes_by_visit: dict[str, set[tuple[float, ...]]] = {}
    with repository.session_factory() as session:
        for visit_id in visit_ids:
            links = session.query(VisitEvidenceLinkModel).filter(
                VisitEvidenceLinkModel.visit_id == visit_id
            ).all()
            assert links, f"{visit_id} must have its own persisted evidence"
            boxes = set()
            for link in links:
                media = session.get(MediaAssetModel, link.media_asset_id)
                assert media is not None and media.normalized_track_box_json is not None
                boxes.add(tuple(json.loads(media.normalized_track_box_json)))
            boxes_by_visit[visit_id] = boxes
    first_visit_boxes, second_visit_boxes = boxes_by_visit.values()
    assert not (first_visit_boxes & second_visit_boxes), "siblings must never share/borrow each other's evidence box"


def _subject_for_id_at(frame_id: str, box: tuple[float, float, float, float]) -> DetectionObservation:
    return _detection_for_frame_id(frame_id, box)


async def test_offline_ingest_creates_no_monitoring_exposure_intervals(
    repository: ProductRepository, four_second_clip: Path,
) -> None:
    """Critical invariant: offline ingest must never create ordinary live
    monitoring exposure -- a 4-second clip does not mean the yard was
    monitored, in the live-continuous sense, for 4 seconds."""

    _seed_media_asset(repository, media_asset_id="media-video-under-test", video_path=four_second_clip)
    frame_ids = _peek_sampled_frame_ids(four_second_clip, sample_fps=2.0)
    loader, _fake = _fake_provider_loader_factory(
        {frame_id: (_subject_for_id(frame_id),) for frame_id in frame_ids}
    )

    result = await offline_ingest.run_offline_video_ingest(
        repository, media_asset_id="media-video-under-test", sample_fps=2.0, provider_loader=loader,
    )
    assert result.status == "completed"

    with repository.session_factory() as session:
        count = session.query(MonitoringExposureIntervalModel).count()
    assert count == 0


def test_still_image_import_creates_no_monitoring_exposure_intervals(repository: ProductRepository, tmp_path: Path) -> None:
    """The complementary still-image case, for completeness: importing one
    still (via the existing, unmodified MediaAsset creation path this
    module never touches) must likewise never create ordinary live
    monitoring exposure -- a single photograph does not create a monitored
    day. This exercises only pre-existing behavior; no offline_ingest code
    runs here at all, since a still has no frames to decode."""

    image_path = tmp_path / "trailcam-still.jpg"
    image_path.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 32 + b"\xff\xd9")
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id="media-still-image", source_id="source-backyard-demo", stream_id=STREAM_ID,
                    filename=image_path.name, content_type="image/jpeg", media_type="image",
                    local_path=str(image_path), original_filename=image_path.name,
                    file_size_bytes=image_path.stat().st_size, created_at=datetime.now(UTC),
                )
            )

    with repository.session_factory() as session:
        count = session.query(MonitoringExposureIntervalModel).count()
    assert count == 0


async def test_offline_ingest_preserves_capture_time_and_offset_when_known(
    repository: ProductRepository, tmp_path: Path,
) -> None:
    if not _has_real_ffmpeg_suite():
        pytest.skip("ffmpeg/ffprobe not available in this environment")
    video_path = tmp_path / "historical-clip.mp4"
    _generate_clip(video_path, duration_seconds=4.0, creation_time="2024-05-01T14:23:01.000000Z")
    from mockingbird.source_providers import media_provenance

    probe = media_provenance.probe_video_metadata(video_path)
    assert probe is not None and probe.captured_at is not None
    _seed_media_asset(
        repository, media_asset_id="media-video-under-test", video_path=video_path, captured_at=probe.captured_at,
    )
    frame_ids = _peek_sampled_frame_ids(video_path, sample_fps=2.0)
    loader, _fake = _fake_provider_loader_factory(
        {frame_id: (_subject_for_id(frame_id),) for frame_id in frame_ids}
    )

    result = await offline_ingest.run_offline_video_ingest(
        repository, media_asset_id="media-video-under-test", sample_fps=2.0, provider_loader=loader,
    )
    assert result.status == "completed"
    assert result.capture_time_known is True

    visit_id = result.visit_ids[0]
    detail = repository.get_visit(visit_id)
    event = repository.get_event(detail.event_id)
    # The historical capture time -- not real "now" -- must be what the
    # persisted Event actually shows.
    assert event.started_at.year == 2024
    assert event.started_at.month == 5
    assert event.started_at < datetime(2024, 5, 1, 15, 0, tzinfo=UTC)
    assert event.started_at >= datetime(2024, 5, 1, 14, 23, 1, tzinfo=UTC)


async def test_offline_ingest_does_not_fabricate_absolute_time_when_capture_start_unknown(
    repository: ProductRepository, four_second_clip: Path,
) -> None:
    """A recording with no defensible capture-start fact must never be
    reported as happening "now" (real processing wall-clock) -- the
    existing epoch-anchor honesty convention applies instead of a
    fabricated recent date."""

    _seed_media_asset(
        repository, media_asset_id="media-video-under-test", video_path=four_second_clip, captured_at=None,
    )
    frame_ids = _peek_sampled_frame_ids(four_second_clip, sample_fps=2.0)
    loader, _fake = _fake_provider_loader_factory(
        {frame_id: (_subject_for_id(frame_id),) for frame_id in frame_ids}
    )
    before = datetime.now(UTC) - timedelta(minutes=1)

    result = await offline_ingest.run_offline_video_ingest(
        repository, media_asset_id="media-video-under-test", sample_fps=2.0, provider_loader=loader,
    )
    assert result.status == "completed"
    assert result.capture_time_known is False

    visit_id = result.visit_ids[0]
    detail = repository.get_visit(visit_id)
    event = repository.get_event(detail.event_id)
    assert event.started_at < before, "must never read as real processing 'now'"
    assert event.started_at.year < 2000, "honest epoch-anchored disclosure, not a fabricated recent date"


async def test_offline_ingest_historical_capture_imported_today_is_not_reported_as_today(
    repository: ProductRepository, tmp_path: Path,
) -> None:
    """Import time != observation time: a historical clip imported (i.e.
    analyzed) today must not appear as captured today merely because
    analysis happened today."""

    if not _has_real_ffmpeg_suite():
        pytest.skip("ffmpeg/ffprobe not available in this environment")
    video_path = tmp_path / "old-clip.mp4"
    _generate_clip(video_path, duration_seconds=2.0, creation_time="2020-01-15T09:00:00.000000Z")
    from mockingbird.source_providers import media_provenance

    probe = media_provenance.probe_video_metadata(video_path)
    _seed_media_asset(
        repository, media_asset_id="media-video-under-test", video_path=video_path, captured_at=probe.captured_at,
    )
    frame_ids = _peek_sampled_frame_ids(video_path, sample_fps=2.0)
    loader, _fake = _fake_provider_loader_factory(
        {frame_id: (_subject_for_id(frame_id),) for frame_id in frame_ids}
    )

    result = await offline_ingest.run_offline_video_ingest(
        repository, media_asset_id="media-video-under-test", sample_fps=2.0, provider_loader=loader,
    )
    assert result.status == "completed"

    today = datetime.now(UTC).date()
    summary = repository.dashboard_summary({}, now=datetime.now(UTC))
    assert "northern_mockingbird" not in {o.label for o in summary.today_observations}
    visit_id = result.visit_ids[0]
    detail = repository.get_visit(visit_id)
    event = repository.get_event(detail.event_id)
    assert event.started_at.date() != today


async def test_offline_ingest_respects_privacy_zone(repository: ProductRepository, four_second_clip: Path) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                ZoneModel(
                    id="zone-privacy-test", stream_id=STREAM_ID, name="Window", zone_type="privacy",
                    polygon_json="[[0.0,0.0],[0.3,0.0],[0.3,0.3],[0.0,0.3]]", is_active=True,
                )
            )
    _seed_media_asset(repository, media_asset_id="media-video-under-test", video_path=four_second_clip)
    frame_ids = _peek_sampled_frame_ids(four_second_clip, sample_fps=2.0)
    # The only subject present sits entirely inside the Privacy Zone.
    loader, _fake = _fake_provider_loader_factory(
        {frame_id: (_subject_for_id_at(frame_id, (0.05, 0.05, 0.2, 0.2)),) for frame_id in frame_ids}
    )
    baseline_visit_count = len(repository.list_visits())

    result = await offline_ingest.run_offline_video_ingest(
        repository, media_asset_id="media-video-under-test", sample_fps=2.0, provider_loader=loader,
    )
    assert result.status == "completed"
    assert result.visits_created == 0
    assert len(repository.list_visits()) == baseline_visit_count


async def test_offline_ingest_works_with_no_zones_configured(repository: ProductRepository, four_second_clip: Path) -> None:
    with repository.session_factory() as session:
        with session.begin():
            existing_zones = session.query(ZoneModel).filter(ZoneModel.stream_id == STREAM_ID).all()
            for zone in existing_zones:
                session.delete(zone)
    _seed_media_asset(repository, media_asset_id="media-video-under-test", video_path=four_second_clip)
    frame_ids = _peek_sampled_frame_ids(four_second_clip, sample_fps=2.0)
    loader, _fake = _fake_provider_loader_factory(
        {frame_id: (_subject_for_id(frame_id),) for frame_id in frame_ids}
    )

    result = await offline_ingest.run_offline_video_ingest(
        repository, media_asset_id="media-video-under-test", sample_fps=2.0, provider_loader=loader,
    )
    assert result.status == "completed"
    assert result.visits_created == 1


async def test_offline_ingest_is_idempotent_for_the_same_pipeline_version(
    repository: ProductRepository, four_second_clip: Path,
) -> None:
    _seed_media_asset(repository, media_asset_id="media-video-under-test", video_path=four_second_clip)
    frame_ids = _peek_sampled_frame_ids(four_second_clip, sample_fps=2.0)
    loader, _fake = _fake_provider_loader_factory(
        {frame_id: (_subject_for_id(frame_id),) for frame_id in frame_ids}
    )
    baseline_visit_count = len(repository.list_visits())

    first = await offline_ingest.run_offline_video_ingest(
        repository, media_asset_id="media-video-under-test", sample_fps=2.0, provider_loader=loader,
    )
    assert first.status == "completed"
    assert len(repository.list_visits()) == baseline_visit_count + 1

    second = await offline_ingest.run_offline_video_ingest(
        repository, media_asset_id="media-video-under-test", sample_fps=2.0, provider_loader=loader,
    )
    assert second.status == "already_processed"
    assert len(repository.list_visits()) == baseline_visit_count + 1, (
        "reprocessing the same file/pipeline must never duplicate Visits"
    )


async def test_offline_ingest_reprocessing_identical_content_under_a_new_pipeline_version_stays_idempotent(
    repository: ProductRepository, four_second_clip: Path,
) -> None:
    """`force_reprocess`/a new `pipeline_version` controls only whether this
    module's own run-tracking short-circuit is bypassed -- it never
    overrides the deeper, content-addressed `proposal_id` idempotency
    `ObservationCandidateVisitModel` already enforces (see "Idempotency" in
    docs/offline-recorded-media-observation-contract.md). Reprocessing
    genuinely identical decoded content under a nominally "newer" pipeline
    label must still resolve as idempotent -- never a duplicate Visit for
    the same real encounter -- and must never touch already-reviewed
    historical truth from the first run."""

    _seed_media_asset(repository, media_asset_id="media-video-under-test", video_path=four_second_clip)
    frame_ids = _peek_sampled_frame_ids(four_second_clip, sample_fps=2.0)
    loader, _fake = _fake_provider_loader_factory(
        {frame_id: (_subject_for_id(frame_id),) for frame_id in frame_ids}
    )
    baseline_visit_count = len(repository.list_visits())

    first = await offline_ingest.run_offline_video_ingest(
        repository, media_asset_id="media-video-under-test", sample_fps=2.0, provider_loader=loader,
        pipeline_version="offline-video-ingest-v1",
    )
    assert first.status == "completed"

    reviewed_label = repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit", target_id=first.visit_ids[0], label="northern_cardinal",
            review_origin="human",
        )
    )
    assert reviewed_label is not None

    # A distinct pipeline_version means this is a real, explicit
    # reprocessing attempt, not blocked by this module's own "already
    # processed" short-circuit (contrast with the identical-pipeline-
    # version idempotency test above, which never even reaches the engine).
    second = await offline_ingest.run_offline_video_ingest(
        repository, media_asset_id="media-video-under-test", sample_fps=2.0, provider_loader=loader,
        pipeline_version="offline-video-ingest-v2-newer-detector",
    )
    assert second.status == "completed"
    assert second.outcome_counts.get("idempotent_repeat") == 1
    assert second.visits_created == 0, "identical underlying content must never mint a duplicate Visit"

    # Reviewed historical truth from the first pipeline run must survive
    # completely untouched.
    original_visit = repository.get_visit(first.visit_ids[0])
    assert original_visit.review_status.value == "reviewed"
    assert original_visit.reviewed_label == "northern_cardinal"
    assert len(repository.list_visits()) == baseline_visit_count + 1


async def test_offline_ingest_reprocessing_with_genuinely_different_detection_creates_a_new_visit(
    repository: ProductRepository, four_second_clip: Path,
) -> None:
    """The complementary case: when a newer pipeline genuinely produces
    different detections (a real detector/model upgrade), reprocessing is
    not blocked and can legitimately add a new Visit -- reprocessing
    research is never structurally prevented."""

    _seed_media_asset(repository, media_asset_id="media-video-under-test", video_path=four_second_clip)
    frame_ids = _peek_sampled_frame_ids(four_second_clip, sample_fps=2.0)
    first_loader, _fake1 = _fake_provider_loader_factory(
        {frame_id: (_subject_for_id(frame_id),) for frame_id in frame_ids}
    )
    baseline_visit_count = len(repository.list_visits())

    first = await offline_ingest.run_offline_video_ingest(
        repository, media_asset_id="media-video-under-test", sample_fps=2.0, provider_loader=first_loader,
        pipeline_version="offline-video-ingest-v1",
    )
    assert first.status == "completed"

    # A materially different detection box shape/position produces a
    # different tracker generation id, and therefore a genuinely different,
    # non-idempotent `proposal_id`.
    second_loader, _fake2 = _fake_provider_loader_factory(
        {frame_id: (_subject_for_id_at(frame_id, (0.55, 0.05, 0.75, 0.25)),) for frame_id in frame_ids}
    )
    second = await offline_ingest.run_offline_video_ingest(
        repository, media_asset_id="media-video-under-test", sample_fps=2.0, provider_loader=second_loader,
        pipeline_version="offline-video-ingest-v2-newer-detector",
    )
    assert second.status == "completed"
    assert second.visits_created == 1
    assert len(repository.list_visits()) == baseline_visit_count + 2


async def test_offline_ingest_malformed_video_fails_closed_with_no_partial_truth(
    repository: ProductRepository, tmp_path: Path,
) -> None:
    bogus_path = tmp_path / "bogus.mp4"
    bogus_path.write_bytes(b"not a real video" * 20)
    _seed_media_asset(repository, media_asset_id="media-video-under-test", video_path=bogus_path)
    baseline_visit_count = len(repository.list_visits())

    result = await offline_ingest.run_offline_video_ingest(
        repository, media_asset_id="media-video-under-test", sample_fps=2.0,
    )
    assert result.status == "failed"
    assert result.error_code == "media_file_invalid"
    assert len(repository.list_visits()) == baseline_visit_count

    run = repository.get_recorded_media_analysis_run(result.run_id)
    assert run is not None
    assert run.status == "failed"
    assert run.error_code == "media_file_invalid"


async def test_offline_ingest_unsupported_codec_gives_a_stable_bounded_failure(
    repository: ProductRepository, tmp_path: Path,
) -> None:
    if not _has_real_ffmpeg_suite():
        pytest.skip("ffmpeg/ffprobe not available in this environment")
    audio_only = tmp_path / "audio-only.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:a", "aac", str(audio_only),
        ],
        check=True, timeout=30, capture_output=True,
    )
    _seed_media_asset(repository, media_asset_id="media-video-under-test", video_path=audio_only)
    baseline_visit_count = len(repository.list_visits())

    result = await offline_ingest.run_offline_video_ingest(
        repository, media_asset_id="media-video-under-test", sample_fps=2.0,
    )
    assert result.status == "failed"
    assert result.error_code == "unsupported_codec"
    assert len(repository.list_visits()) == baseline_visit_count


async def test_offline_ingest_rejects_a_media_asset_that_is_not_video(repository: ProductRepository, tmp_path: Path) -> None:
    image_path = tmp_path / "not-a-video.jpg"
    image_path.write_bytes(b"\xff\xd8\xff\xe0" + b"0" * 32 + b"\xff\xd9")
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id="media-image-not-video", source_id="source-backyard-demo", stream_id=STREAM_ID,
                    filename=image_path.name, content_type="image/jpeg", media_type="image",
                    local_path=str(image_path), original_filename=image_path.name,
                    file_size_bytes=image_path.stat().st_size, created_at=datetime.now(UTC),
                )
            )

    with pytest.raises(offline_ingest.OfflineIngestError, match="media_asset_not_video"):
        await offline_ingest.run_offline_video_ingest(repository, media_asset_id="media-image-not-video")


async def test_offline_ingest_rejects_an_unknown_media_asset(repository: ProductRepository) -> None:
    with pytest.raises(offline_ingest.OfflineIngestError, match="media_asset_not_found"):
        await offline_ingest.run_offline_video_ingest(repository, media_asset_id="media-does-not-exist")


async def test_offline_ingest_reverts_authority_to_shadow_after_completion(
    repository: ProductRepository, four_second_clip: Path,
) -> None:
    _seed_media_asset(repository, media_asset_id="media-video-under-test", video_path=four_second_clip)
    frame_ids = _peek_sampled_frame_ids(four_second_clip, sample_fps=2.0)
    loader, _fake = _fake_provider_loader_factory(
        {frame_id: (_subject_for_id(frame_id),) for frame_id in frame_ids}
    )

    await offline_ingest.run_offline_video_ingest(
        repository, media_asset_id="media-video-under-test", sample_fps=2.0, provider_loader=loader,
    )
    state = repository.get_observation_authority_state(stream_id=STREAM_ID)
    assert state.mode == "shadow"


async def test_offline_ingest_processing_order_is_deterministic_across_reruns(
    repository: ProductRepository, four_second_clip: Path,
) -> None:
    """Two simultaneous subjects are always attempted in the same
    (start_offset_ms, proposal_id) order, so which one mints the shared
    Event and which one reuses it is stable across repeated, independently
    decoded runs -- never an artifact of dict/set iteration order or
    incidental scheduling."""

    def _detections_for(frame_ids: tuple[str, ...]) -> dict[str, tuple]:
        return {
            frame_id: (
                _subject_for_id_at(frame_id, (0.3, 0.05, 0.5, 0.25)),
                _subject_for_id_at(frame_id, (0.7, 0.7, 0.9, 0.9)),
            )
            for frame_id in frame_ids
        }

    _seed_media_asset(repository, media_asset_id="media-video-a", video_path=four_second_clip)
    frame_ids_a = _peek_sampled_frame_ids(
        four_second_clip, sample_fps=2.0, media_asset_id_prefix="media-video-a",
    )
    loader_a, _fake_a = _fake_provider_loader_factory(_detections_for(frame_ids_a))
    first = await offline_ingest.run_offline_video_ingest(
        repository, media_asset_id="media-video-a", sample_fps=2.0, provider_loader=loader_a,
    )
    assert first.status == "completed"
    first_outcomes = tuple(sorted(first.outcome_counts.items()))

    _seed_media_asset(repository, media_asset_id="media-video-b", video_path=four_second_clip)
    frame_ids_b = _peek_sampled_frame_ids(
        four_second_clip, sample_fps=2.0, media_asset_id_prefix="media-video-b",
    )
    loader_b, _fake_b = _fake_provider_loader_factory(_detections_for(frame_ids_b))
    second = await offline_ingest.run_offline_video_ingest(
        repository, media_asset_id="media-video-b", sample_fps=2.0, provider_loader=loader_b,
    )
    assert second.status == "completed"
    second_outcomes = tuple(sorted(second.outcome_counts.items()))

    assert first_outcomes == second_outcomes == (("created", 2),)
