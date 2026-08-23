"""Acoustic / BirdNET Observation Foundation v1: `acoustic_ingest`
orchestrator tests. Mirrors `tests/test_offline_ingest.py`'s structure:
real ffmpeg-decoded synthetic audio for the bounded transcode step
(skipped, never faked, when genuinely unavailable), `FakeRecording`
injection (see `tests/test_birdnet_adapter.py`) for the BirdNET analysis
step -- no dependency on the real, optional `classifier-birdnet` stack."""

from __future__ import annotations

import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mockingbird.api.schemas import ReviewCorrectionCreate
from mockingbird.observation import acoustic_ingest
from mockingbird.repository.product_repository import MediaAssetModel, ProductRepository
STREAM_ID = "stream-backyard-feeder"


class FakeRecording:
    """Mirrors `tests/test_birdnet_adapter.py::FakeRecording` -- a
    deterministic stand-in for `birdnetlib.Recording` (this codebase's
    established convention is one local copy per test file rather than a
    cross-test-file import, matching `test_offline_ingest.py`'s own
    `_FakeDetector`)."""

    def __init__(
        self, detections: list[dict[str, object]] | None = None, *, duration: float | None = 9.0,
    ) -> None:
        self.detections = detections or []
        self.duration = duration

    def analyze(self) -> None:
        pass


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    yield repo
    repo.close()


def _has_real_ffmpeg_suite() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


requires_ffmpeg = pytest.mark.skipif(
    not _has_real_ffmpeg_suite(), reason="real ffmpeg/ffprobe not available on this host"
)


def _generate_tone(path: Path, *, duration_seconds: float = 6.0) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"sine=frequency=1000:duration={duration_seconds}:sample_rate=44100",
            "-ac", "1", str(path),
        ],
        check=True, timeout=30, capture_output=True,
    )


def _seed_audio_media_asset(
    repository: ProductRepository,
    *,
    media_asset_id: str,
    audio_path: Path,
    captured_at: datetime | None = None,
    stream_id: str = STREAM_ID,
) -> None:
    """Directly seed one imported-audio MediaAsset row, mirroring
    `test_offline_ingest._seed_media_asset`'s identical shape for video."""

    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id=media_asset_id, source_id="source-backyard-demo", stream_id=stream_id,
                    filename=audio_path.name, content_type="audio/wav", media_type="audio",
                    local_path=str(audio_path), original_filename=audio_path.name,
                    file_size_bytes=audio_path.stat().st_size, created_at=datetime.now(UTC),
                    captured_at=captured_at, notes="Test-seeded audio MediaAsset.",
                )
            )


CARDINAL_DETECTION = {
    "common_name": "Northern Cardinal", "scientific_name": "Cardinalis cardinalis",
    "confidence": 0.95, "start_time": 0.0, "end_time": 3.0,
}


@requires_ffmpeg
class TestRunAcousticAnalysis:
    def test_positive_detection_creates_a_needs_review_visit(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        audio_path = tmp_path / "clip.wav"
        _generate_tone(audio_path)
        _seed_audio_media_asset(repository, media_asset_id="media-audio-1", audio_path=audio_path)

        result = acoustic_ingest.run_acoustic_analysis(
            repository, media_asset_id="media-audio-1",
            recording=FakeRecording(detections=[CARDINAL_DETECTION], duration=9.0),
        )

        assert result.status == "completed"
        assert result.visits_created == 1
        assert result.events_created == 1
        assert result.species_suggestions_created == 1
        assert result.detections_above_threshold == 1
        assert result.windows_analyzed == 3
        assert len(result.visit_ids) == 1

        visit = repository.get_visit(result.visit_ids[0])
        assert visit is not None
        assert visit.subject_label == "bird"
        assert visit.species_guess == "northern_cardinal"
        assert visit.review_status.value == "needs_review"

        suggestions = repository.list_species_suggestions(visit_id=result.visit_ids[0])
        assert len(suggestions) == 1
        assert suggestions[0].adapter_id == "birdnet"
        assert suggestions[0].window_start_ms == 0
        assert suggestions[0].window_end_ms == 3000
        assert suggestions[0].model_provenance is not None
        assert suggestions[0].model_provenance["model_version"] == "BirdNET_GLOBAL_6K_V2.4"

    def test_no_detection_creates_no_visit_but_records_an_honest_run(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        audio_path = tmp_path / "clip.wav"
        _generate_tone(audio_path)
        _seed_audio_media_asset(repository, media_asset_id="media-audio-1", audio_path=audio_path)

        result = acoustic_ingest.run_acoustic_analysis(
            repository, media_asset_id="media-audio-1",
            recording=FakeRecording(detections=[], duration=6.0),
        )

        assert result.status == "completed"
        assert result.visits_created == 0
        assert result.events_created == 0
        assert result.windows_analyzed == 2
        assert result.detections_above_threshold == 0

        runs = repository.list_acoustic_analysis_runs_for_media_asset("media-audio-1")
        assert len(runs) == 1
        assert runs[0].status == "completed"
        assert runs[0].windows_analyzed == 2

    def test_same_species_consecutive_windows_merge_into_one_visit(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        audio_path = tmp_path / "clip.wav"
        _generate_tone(audio_path, duration_seconds=12.0)
        _seed_audio_media_asset(repository, media_asset_id="media-audio-1", audio_path=audio_path)

        detections = [
            {**CARDINAL_DETECTION, "start_time": 0.0, "end_time": 3.0, "confidence": 0.80},
            {**CARDINAL_DETECTION, "start_time": 3.0, "end_time": 6.0, "confidence": 0.99},
            {**CARDINAL_DETECTION, "start_time": 6.0, "end_time": 9.0, "confidence": 0.85},
        ]
        result = acoustic_ingest.run_acoustic_analysis(
            repository, media_asset_id="media-audio-1",
            recording=FakeRecording(detections=detections, duration=12.0),
        )

        assert result.visits_created == 1  # not 3 -- merged, not fragmented
        assert result.detections_above_threshold == 3
        visit = repository.get_visit(result.visit_ids[0])
        assert visit.confidence == pytest.approx(0.99)  # peak confidence across the merge
        suggestion = repository.list_species_suggestions(visit_id=result.visit_ids[0])[0]
        assert suggestion.window_start_ms == 0
        assert suggestion.window_end_ms == 9000  # spans earliest start to latest end

    def test_two_distinct_species_in_one_clip_create_two_visits(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        audio_path = tmp_path / "clip.wav"
        _generate_tone(audio_path, duration_seconds=6.0)
        _seed_audio_media_asset(repository, media_asset_id="media-audio-1", audio_path=audio_path)

        detections = [
            CARDINAL_DETECTION,
            {
                "common_name": "Blue Jay", "scientific_name": "Cyanocitta cristata",
                "confidence": 0.88, "start_time": 3.0, "end_time": 6.0,
            },
        ]
        result = acoustic_ingest.run_acoustic_analysis(
            repository, media_asset_id="media-audio-1",
            recording=FakeRecording(detections=detections, duration=6.0),
        )

        assert result.visits_created == 2
        assert result.events_created == 2  # no artificial Event-sharing in v1 (see module docstring)
        species_guesses = {repository.get_visit(vid).species_guess for vid in result.visit_ids}
        assert species_guesses == {"northern_cardinal", "blue_jay"}

    def test_idempotent_by_default(self, repository: ProductRepository, tmp_path: Path) -> None:
        audio_path = tmp_path / "clip.wav"
        _generate_tone(audio_path)
        _seed_audio_media_asset(repository, media_asset_id="media-audio-1", audio_path=audio_path)

        first = acoustic_ingest.run_acoustic_analysis(
            repository, media_asset_id="media-audio-1",
            recording=FakeRecording(detections=[CARDINAL_DETECTION], duration=9.0),
        )
        assert first.status == "completed"

        second = acoustic_ingest.run_acoustic_analysis(
            repository, media_asset_id="media-audio-1",
            recording=FakeRecording(detections=[CARDINAL_DETECTION], duration=9.0),
        )
        assert second.status == "already_processed"
        assert second.visit_ids == ()  # not re-reported as newly created

        runs = repository.list_acoustic_analysis_runs_for_media_asset("media-audio-1")
        assert len(runs) == 1  # never duplicated

    def test_force_reprocess_runs_again_but_stays_idempotent_at_the_visit_layer(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        audio_path = tmp_path / "clip.wav"
        _generate_tone(audio_path)
        _seed_audio_media_asset(repository, media_asset_id="media-audio-1", audio_path=audio_path)

        acoustic_ingest.run_acoustic_analysis(
            repository, media_asset_id="media-audio-1",
            recording=FakeRecording(detections=[CARDINAL_DETECTION], duration=9.0),
        )
        second = acoustic_ingest.run_acoustic_analysis(
            repository, media_asset_id="media-audio-1", force_reprocess=True,
            recording=FakeRecording(detections=[CARDINAL_DETECTION], duration=9.0),
        )
        assert second.status == "completed"
        assert second.species_suggestions_created == 0  # same window -- idempotent_repeat at the Visit layer
        runs = repository.list_acoustic_analysis_runs_for_media_asset("media-audio-1")
        assert len(runs) == 2  # a genuine, distinct new run attempt

    def test_capture_time_unknown_falls_back_to_epoch_anchor_honestly(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        audio_path = tmp_path / "clip.wav"
        _generate_tone(audio_path)
        _seed_audio_media_asset(
            repository, media_asset_id="media-audio-1", audio_path=audio_path, captured_at=None,
        )

        result = acoustic_ingest.run_acoustic_analysis(
            repository, media_asset_id="media-audio-1",
            recording=FakeRecording(detections=[CARDINAL_DETECTION], duration=9.0),
        )
        assert result.capture_time_known is False
        visit_evidence = repository.list_species_suggestions(visit_id=result.visit_ids[0])[0]
        assert visit_evidence.created_at == acoustic_ingest.EPOCH_ANCHOR

    def test_capture_time_known_offsets_from_real_capture_start(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        audio_path = tmp_path / "clip.wav"
        _generate_tone(audio_path, duration_seconds=9.0)
        capture_start = datetime(2026, 8, 20, 7, 30, 0, tzinfo=UTC)
        _seed_audio_media_asset(
            repository, media_asset_id="media-audio-1", audio_path=audio_path, captured_at=capture_start,
        )

        detection = {**CARDINAL_DETECTION, "start_time": 6.0, "end_time": 9.0}
        result = acoustic_ingest.run_acoustic_analysis(
            repository, media_asset_id="media-audio-1",
            recording=FakeRecording(detections=[detection], duration=9.0),
        )
        assert result.capture_time_known is True
        suggestion = repository.list_species_suggestions(visit_id=result.visit_ids[0])[0]
        assert suggestion.created_at.hour == 7
        assert suggestion.created_at.minute == 30
        assert suggestion.created_at.second == 6  # capture_start + 6000ms offset

    def test_full_review_flow_reaches_bird_log_and_today_unmodified(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        """The most important proof: nothing about review/Bird Log/Today
        needed to change for an audio-original Visit."""

        audio_path = tmp_path / "clip.wav"
        _generate_tone(audio_path)
        _seed_audio_media_asset(repository, media_asset_id="media-audio-1", audio_path=audio_path)

        result = acoustic_ingest.run_acoustic_analysis(
            repository, media_asset_id="media-audio-1",
            recording=FakeRecording(detections=[CARDINAL_DETECTION], duration=9.0),
        )
        correction = repository.create_review_label(
            ReviewCorrectionCreate(
                target_type="visit", target_id=result.visit_ids[0],
                label="northern_cardinal", review_origin="human",
            )
        )
        assert correction.review_label.is_authoritative is True

        visit_after = repository.get_visit(result.visit_ids[0])
        assert visit_after.review_status.value == "reviewed"
        assert visit_after.reviewed_label == "northern_cardinal"

        from mockingbird.api.schemas import WildlifeJournalOverviewRequest

        journal = repository.wildlife_journal_overview(WildlifeJournalOverviewRequest())
        assert any(label.label == "northern_cardinal" for label in journal.labels)

        dashboard = repository.dashboard_summary()
        matching = [v for v in dashboard.recent_activity if v.id == result.visit_ids[0]]
        assert len(matching) == 1
        assert matching[0].reviewed_label == "northern_cardinal"
        assert matching[0].primary_evidence.content_type == "audio/wav"


@requires_ffmpeg
class TestNonAvianSoundscapeFiltering:
    """Acoustic Runtime & Quality v1, Phase H (benchmark-discovered): BirdNET's
    own non-avian "soundscape" classes must never become a fabricated
    "bird" candidate. See `acoustic_ingest.NON_AVIAN_SOUNDSCAPE_LABELS`'s
    own docstring for exactly how/why this was found (a real, CC-licensed
    lawnmower recording scoring `Engine` at 0.607 -- above the *default*
    0.5 floor -- with real BirdNET inference; the acceptance proof for that
    real fixture lives in `test_acoustic_ingest_real_model.py`, this class
    covers the same policy hermetically via `FakeRecording`)."""

    def test_every_corpus_confusor_label_is_denylisted(self) -> None:
        # A cheap, direct sanity check that the exact 13 labels this
        # module's own docstring cites are really in the denylist --
        # catches an accidental typo/omission independent of any BirdNET
        # inference at all.
        assert acoustic_ingest.NON_AVIAN_SOUNDSCAPE_LABELS == {
            "Dog", "Engine", "Environmental", "Fireworks", "Gryllus assimilis",
            "Gun", "Human non-vocal", "Human vocal", "Human whistle",
            "Miogryllus saussurei", "Noise", "Power tools", "Siren",
        }

    def test_non_avian_only_detection_creates_no_candidate_but_reports_honestly(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        audio_path = tmp_path / "clip.wav"
        _generate_tone(audio_path)
        _seed_audio_media_asset(repository, media_asset_id="media-audio-1", audio_path=audio_path)
        review_queue_count_before = len(repository.review_queue_items())

        result = acoustic_ingest.run_acoustic_analysis(
            repository, media_asset_id="media-audio-1",
            recording=FakeRecording(
                detections=[
                    {
                        "common_name": "Engine", "scientific_name": "Engine",
                        "confidence": 0.61, "start_time": 0.0, "end_time": 3.0,
                    },
                    {
                        "common_name": "Power tools", "scientific_name": "Power tools",
                        "confidence": 0.53, "start_time": 3.0, "end_time": 6.0,
                    },
                ],
                duration=9.0,
            ),
        )

        assert result.status == "completed"
        # Honest raw BirdNET facts are preserved -- these two windows really
        # did fire above the confidence floor.
        assert result.detections_above_threshold == 2
        assert result.windows_analyzed == 3
        # But zero fabricated "bird" candidates.
        assert result.species_suggestions_created == 0
        assert result.visits_created == 0
        assert result.events_created == 0
        assert result.visit_ids == ()
        assert len(repository.review_queue_items()) == review_queue_count_before

    def test_mixed_bird_and_non_avian_creates_only_the_bird_candidate(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        audio_path = tmp_path / "clip.wav"
        _generate_tone(audio_path)
        _seed_audio_media_asset(repository, media_asset_id="media-audio-1", audio_path=audio_path)

        result = acoustic_ingest.run_acoustic_analysis(
            repository, media_asset_id="media-audio-1",
            recording=FakeRecording(
                detections=[
                    CARDINAL_DETECTION,
                    {
                        "common_name": "Siren", "scientific_name": "Siren",
                        "confidence": 0.72, "start_time": 3.0, "end_time": 6.0,
                    },
                ],
                duration=9.0,
            ),
        )

        assert result.status == "completed"
        assert result.detections_above_threshold == 2
        assert result.species_suggestions_created == 1
        assert result.visits_created == 1
        assert len(result.visit_ids) == 1

        visit = repository.get_visit(result.visit_ids[0])
        assert visit is not None
        assert visit.species_guess == "northern_cardinal"


class TestRunAcousticAnalysisErrorHandling:
    def test_missing_media_asset_raises(self, repository: ProductRepository) -> None:
        with pytest.raises(acoustic_ingest.AcousticIngestError, match="media_asset_not_found"):
            acoustic_ingest.run_acoustic_analysis(repository, media_asset_id="does-not-exist")

    def test_non_audio_media_asset_raises(self, repository: ProductRepository, tmp_path: Path) -> None:
        image_path = tmp_path / "photo.jpg"
        image_path.write_bytes(b"not-a-real-image-but-a-real-file")
        with repository.session_factory() as session:
            with session.begin():
                session.add(
                    MediaAssetModel(
                        id="media-image-1", source_id="source-backyard-demo", stream_id=STREAM_ID,
                        filename="photo.jpg", content_type="image/jpeg", media_type="image",
                        local_path=str(image_path), original_filename="photo.jpg",
                        file_size_bytes=image_path.stat().st_size, created_at=datetime.now(UTC),
                    )
                )
        with pytest.raises(acoustic_ingest.AcousticIngestError, match="media_asset_not_audio"):
            acoustic_ingest.run_acoustic_analysis(repository, media_asset_id="media-image-1")

    @requires_ffmpeg
    def test_decode_failure_is_recorded_as_a_failed_run(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        bad_path = tmp_path / "corrupt.wav"
        bad_path.write_bytes(b"this is not a real audio container at all")
        _seed_audio_media_asset(repository, media_asset_id="media-audio-1", audio_path=bad_path)

        result = acoustic_ingest.run_acoustic_analysis(
            repository, media_asset_id="media-audio-1", recording=FakeRecording(),
        )
        assert result.status == "failed"
        assert result.error_code is not None
        assert result.visits_created == 0

        runs = repository.list_acoustic_analysis_runs_for_media_asset("media-audio-1")
        assert runs[0].status == "failed"
        assert runs[0].error_code == result.error_code
