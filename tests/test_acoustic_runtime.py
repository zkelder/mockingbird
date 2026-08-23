"""Acoustic Runtime & Quality v1: `acoustic_runtime` orchestration tests --
the bounded queue/idempotency/restart/retry/backpressure/retention/
consolidation runtime layered on top of the already-tested `acoustic_
ingest` primitives. Mirrors `tests/test_acoustic_ingest.py`'s conventions
exactly: real ffmpeg-decoded synthetic audio (skipped, never faked, when
genuinely unavailable), local `FakeRecording` injection for BirdNET (one
local copy per test file, this codebase's established convention)."""

from __future__ import annotations

import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.api.schemas import ReviewCorrectionCreate
from mockingbird.observation import acoustic_runtime as ar
from mockingbird.observation.audio_capture import CapturedSegment
from mockingbird.repository.product_repository import ProductRepository

STREAM_ID = "stream-backyard-feeder"

CARDINAL_DETECTION = {
    "common_name": "Northern Cardinal", "scientific_name": "Cardinalis cardinalis",
    "confidence": 0.95, "start_time": 0.0, "end_time": 3.0,
}
CHICKADEE_DETECTION = {
    "common_name": "Black-capped Chickadee", "scientific_name": "Poecile atricapillus",
    "confidence": 0.90, "start_time": 0.0, "end_time": 3.0,
}


class FakeRecording:
    """Mirrors `tests/test_acoustic_ingest.py::FakeRecording` exactly."""

    def __init__(
        self, detections: list[dict[str, object]] | None = None, *, duration: float | None = 15.0,
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


def _generate_tone(path: Path, *, duration_seconds: float = 15.0, frequency: int = 1000) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"sine=frequency={frequency}:duration={duration_seconds}:sample_rate=48000",
            "-ac", "1", str(path),
        ],
        check=True, timeout=30, capture_output=True,
    )


class ScriptedSegmentSource:
    """A minimal, hand-rolled `SegmentSource` for tests that need finer
    control than `FixtureSegmentSource`'s file-copying semantics (these
    tests generate their own throwaway tone files directly, so no
    committed fixture needs protecting from deletion)."""

    def __init__(self, stream_id: str, items: list[tuple[Path, datetime, timedelta]]) -> None:
        self.stream_id = stream_id
        self.items = items
        self.served: set[int] = set()
        self.now: datetime | None = None

    def advance_to(self, now: datetime) -> None:
        self.now = now

    def active_stream_ids(self) -> list[str]:
        return [self.stream_id]

    def poll_new_segments(self, stream_id: str) -> list[CapturedSegment]:
        if self.now is None or stream_id != self.stream_id:
            return []
        due = []
        for index, (path, started_at, duration) in enumerate(self.items):
            if index in self.served or started_at > self.now:
                continue
            self.served.add(index)
            due.append(
                CapturedSegment(path=path, sequence_index=index, started_at=started_at, ended_at=started_at + duration)
            )
        return due


T0 = datetime(2026, 8, 22, 10, 0, 0, tzinfo=UTC)


@requires_ffmpeg
class TestIngestAndBackpressure:
    def test_ingest_imports_and_enqueues_a_new_segment(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        seg_path = tmp_path / "seg.wav"
        _generate_tone(seg_path)
        source = ScriptedSegmentSource(STREAM_ID, [(seg_path, T0, timedelta(seconds=15))])
        svc = ar.AcousticRuntimeService(repository=repository, segment_source=source)

        source.advance_to(T0)
        imported = svc.ingest_available_segments(now=T0)

        assert imported == 1
        diagnostics = repository.acoustic_analysis_queue_diagnostics(T0)
        assert diagnostics.queued_count == 1
        assert not seg_path.exists()  # raw file is owned/consumed by the runtime once imported

    def test_unreadable_segment_is_dropped_and_counted_never_enqueued(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        bad_path = tmp_path / "bad.wav"
        bad_path.write_bytes(b"not a real audio file")
        source = ScriptedSegmentSource(STREAM_ID, [(bad_path, T0, timedelta(seconds=15))])
        svc = ar.AcousticRuntimeService(repository=repository, segment_source=source)

        source.advance_to(T0)
        imported = svc.ingest_available_segments(now=T0)

        assert imported == 0
        assert svc.status(now=T0).counters.segments_dropped_unreadable == 1
        assert repository.acoustic_analysis_queue_diagnostics(T0).queued_count == 0
        assert not bad_path.exists()

    def test_per_stream_intake_cap_drops_excess_segments_and_deletes_their_files(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        paths = []
        for index in range(5):
            path = tmp_path / f"seg{index}.wav"
            _generate_tone(path, duration_seconds=2.0, frequency=1000 + index)
            paths.append(path)
        source = ScriptedSegmentSource(
            STREAM_ID, [(p, T0 + timedelta(seconds=i * 2), timedelta(seconds=2)) for i, p in enumerate(paths)],
        )
        svc = ar.AcousticRuntimeService(repository=repository, segment_source=source, max_in_flight_per_stream=3)

        source.advance_to(T0 + timedelta(seconds=100))
        imported = svc.ingest_available_segments(now=T0 + timedelta(seconds=100))

        assert imported == 3
        counters = svc.status(now=T0).counters
        assert counters.segments_dropped_capacity == 2
        assert counters.segments_received == 5
        for path in paths[3:]:
            assert not path.exists()
        assert repository.acoustic_analysis_queue_diagnostics(T0).queued_count == 3

    def test_global_queue_capacity_evicts_oldest_queued_first(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        paths = []
        for index in range(4):
            path = tmp_path / f"seg{index}.wav"
            _generate_tone(path, duration_seconds=2.0, frequency=1000 + index)
            paths.append(path)
        source = ScriptedSegmentSource(
            STREAM_ID, [(p, T0 + timedelta(seconds=i * 2), timedelta(seconds=2)) for i, p in enumerate(paths)],
        )
        # A generous per-stream cap so intake itself never drops anything --
        # isolates the GLOBAL queue-depth cap this test actually exercises.
        svc = ar.AcousticRuntimeService(
            repository=repository, segment_source=source, max_in_flight_per_stream=100,
        )
        source.advance_to(T0 + timedelta(seconds=100))
        svc.ingest_available_segments(now=T0 + timedelta(seconds=100))
        assert repository.acoustic_analysis_queue_diagnostics(T0).queued_count == 4

        evicted = svc.enforce_queue_capacity(now=T0 + timedelta(seconds=101))
        # No eviction yet -- capacity not exceeded (default cap is large).
        assert evicted == []

        # Now enforce a tight capacity directly via the repository primitive
        # (proves the eviction targets the OLDEST queued rows first, and
        # marks them diagnosably `failed` rather than deleting them).
        evicted_ids = repository.enforce_acoustic_queue_capacity(max_queued=2, now=T0 + timedelta(seconds=102))
        assert len(evicted_ids) == 2
        diagnostics = repository.acoustic_analysis_queue_diagnostics(T0 + timedelta(seconds=103))
        assert diagnostics.queued_count == 2
        assert diagnostics.recent_capacity_evicted_count_24h == 2
        for evicted_id in evicted_ids:
            run = repository.get_acoustic_analysis_run(evicted_id)
            assert run.status == "failed"
            assert run.error_code == "acoustic_queue_capacity_exceeded"


@requires_ffmpeg
class TestQueueIdempotency:
    def test_enqueue_twice_for_the_same_media_asset_does_not_duplicate(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        seg_path = tmp_path / "seg.wav"
        _generate_tone(seg_path)
        source = ScriptedSegmentSource(STREAM_ID, [(seg_path, T0, timedelta(seconds=15))])
        svc = ar.AcousticRuntimeService(repository=repository, segment_source=source)
        source.advance_to(T0)
        svc.ingest_available_segments(now=T0)
        assert repository.acoustic_analysis_queue_diagnostics(T0).queued_count == 1

        run = repository.claim_next_queued_acoustic_analysis(now=T0, claimed_by="w")
        assert run is not None
        _, outcome = repository.enqueue_acoustic_analysis(
            media_asset_id=run.media_asset_id, stream_id=STREAM_ID,
            pipeline_version=run.pipeline_version, min_confidence=0.5, now=T0,
        )
        assert outcome == "already_in_flight"
        assert repository.acoustic_analysis_queue_diagnostics(T0).processing_count == 1
        assert repository.acoustic_analysis_queue_diagnostics(T0).queued_count == 0

    def test_claim_is_fifo_and_returns_none_when_nothing_eligible(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        assert repository.claim_next_queued_acoustic_analysis(now=T0, claimed_by="w") is None

        paths = [tmp_path / f"seg{i}.wav" for i in range(3)]
        for i, p in enumerate(paths):
            _generate_tone(p, duration_seconds=2.0, frequency=1000 + i)
        source = ScriptedSegmentSource(
            STREAM_ID, [(p, T0 + timedelta(seconds=i), timedelta(seconds=2)) for i, p in enumerate(paths)],
        )
        svc = ar.AcousticRuntimeService(repository=repository, segment_source=source)
        source.advance_to(T0 + timedelta(seconds=10))
        svc.ingest_available_segments(now=T0 + timedelta(seconds=10))

        first = repository.claim_next_queued_acoustic_analysis(now=T0, claimed_by="w")
        second = repository.claim_next_queued_acoustic_analysis(now=T0, claimed_by="w")
        third = repository.claim_next_queued_acoustic_analysis(now=T0, claimed_by="w")
        assert first is not None and second is not None and third is not None
        assert first.created_at <= second.created_at <= third.created_at
        assert repository.claim_next_queued_acoustic_analysis(now=T0, claimed_by="w") is None


@requires_ffmpeg
class TestRestartRecovery:
    """Phase C's mandatory exercise: segment queued -> process interrupted
    before inference -> restart -> segment analyzed once -> candidate
    created at most once."""

    def test_processing_row_is_reclaimed_and_reprocessed_exactly_once(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        seg_path = tmp_path / "seg.wav"
        _generate_tone(seg_path)
        source = ScriptedSegmentSource(STREAM_ID, [(seg_path, T0, timedelta(seconds=15))])
        svc = ar.AcousticRuntimeService(repository=repository, segment_source=source)
        source.advance_to(T0)
        svc.ingest_available_segments(now=T0)

        # Simulate "process interrupted before inference": claim the row
        # (moves it to `processing`) but never call `execute_queued_
        # acoustic_analysis` on it at all -- exactly what a crash between
        # claim and completion looks like from the database's perspective.
        claimed = repository.claim_next_queued_acoustic_analysis(now=T0, claimed_by="dead-worker")
        assert claimed is not None and claimed.status == "processing"

        # "Restart": a brand-new service instance against the SAME
        # repository -- start()'s own unconditional reclaim runs first.
        svc2 = ar.AcousticRuntimeService(
            repository=repository, segment_source=source,
            recording=FakeRecording(detections=[CARDINAL_DETECTION], duration=15.0),
        )
        reclaimed_count = svc2.reclaim_stale_work(stale_after=timedelta(0), now=T0 + timedelta(seconds=1))
        assert reclaimed_count == 1

        refreshed = repository.get_acoustic_analysis_run(claimed.id)
        assert refreshed.status == "queued"
        assert refreshed.consecutive_failure_count == 1
        assert refreshed.next_retry_at is not None
        # Not yet claimable -- bounded backoff, not an immediate hot retry.
        assert repository.claim_next_queued_acoustic_analysis(
            now=T0 + timedelta(seconds=1), claimed_by="w",
        ) is None

        result = svc2.process_next_queued(now=refreshed.next_retry_at + timedelta(seconds=1))
        assert result is not None
        assert result.status == "completed"
        assert result.species_suggestions_created == 1  # exactly once, never duplicated
        assert svc2.status().queue.queued_count == 0
        assert svc2.status().queue.processing_count == 0

    def test_a_live_manual_analyze_audio_run_is_never_reclaimed(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        """Regression test (found via review): the manual `/analyze-audio`
        path creates a `processing` row with no claim (`claimed_by`/
        `claimed_at` both `None` -- it has no claim concept, it runs
        synchronously in the same request). An earlier version of
        `reclaim_stale_acoustic_analysis_work`'s predicate matched
        `claimed_at IS NULL` unconditionally, which meant the very next
        reconcile tick after a user started a manual analysis would treat
        it as an interrupted crash leftover and requeue it out from under
        the still-running request. This must never happen, at any
        `stale_after` value including zero."""

        seg_path = tmp_path / "seg.wav"
        _generate_tone(seg_path)
        with repository.session_factory() as session:
            with session.begin():
                from mockingbird.repository.product_repository import MediaAssetModel

                session.add(
                    MediaAssetModel(
                        id="media-manual", source_id="source-backyard-demo", stream_id=STREAM_ID,
                        filename=seg_path.name, content_type="audio/wav", media_type="audio",
                        local_path=str(seg_path), original_filename=seg_path.name,
                        file_size_bytes=seg_path.stat().st_size, created_at=T0, captured_at=None,
                        notes="test",
                    )
                )
        # Exactly what the manual path's `create_acoustic_analysis_run`
        # produces: `status="processing"`, no claim.
        manual_run = repository.create_acoustic_analysis_run(
            media_asset_id="media-manual", stream_id=STREAM_ID,
            pipeline_version="birdnet-analyzer-global-6k-v2.4-v1", min_confidence=0.5, now=T0,
        )
        assert manual_run.status == "processing"
        assert manual_run.claimed_at is None

        reclaimed = repository.reclaim_stale_acoustic_analysis_work(
            now=T0, stale_after=timedelta(0),  # the most aggressive possible sweep
        )
        assert reclaimed == 0

        still_processing = repository.get_acoustic_analysis_run(manual_run.id)
        assert still_processing.status == "processing"
        assert still_processing.consecutive_failure_count == 0

    def test_a_completed_run_is_never_touched_by_reclaim(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        seg_path = tmp_path / "seg.wav"
        _generate_tone(seg_path)
        source = ScriptedSegmentSource(STREAM_ID, [(seg_path, T0, timedelta(seconds=15))])
        svc = ar.AcousticRuntimeService(
            repository=repository, segment_source=source,
            recording=FakeRecording(detections=[], duration=15.0),
        )
        source.advance_to(T0)
        svc.ingest_available_segments(now=T0)
        result = svc.process_next_queued(now=T0)
        assert result.status == "completed"

        reclaimed_count = svc.reclaim_stale_work(stale_after=timedelta(0), now=T0 + timedelta(seconds=1))
        assert reclaimed_count == 0
        refreshed = repository.get_acoustic_analysis_run(result.run_id)
        assert refreshed.status == "completed"


@requires_ffmpeg
class TestRetryBackoff:
    def test_repeated_live_failures_requeue_then_terminally_fail(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        seg_path = tmp_path / "seg.wav"
        _generate_tone(seg_path)
        source = ScriptedSegmentSource(STREAM_ID, [(seg_path, T0, timedelta(seconds=15))])
        # An unusable ffmpeg binary deterministically fails every decode
        # attempt -- a real, reproducible failure mode, not a mocked-away
        # one.
        svc = ar.AcousticRuntimeService(
            repository=repository, segment_source=source, ffmpeg_binary="mockingbird-does-not-exist",
        )
        source.advance_to(T0)
        svc.ingest_available_segments(now=T0)

        now = T0
        statuses = []
        for _ in range(3):
            result = svc.process_next_queued(now=now)
            assert result is not None
            statuses.append(result.status)
            run = repository.get_acoustic_analysis_run(result.run_id)
            if run.next_retry_at is not None:
                now = run.next_retry_at + timedelta(seconds=1)

        assert statuses == ["requeued", "requeued", "failed"]
        final_run = repository.get_acoustic_analysis_run(result.run_id)
        assert final_run.status == "failed"
        assert final_run.consecutive_failure_count == 3
        assert final_run.error_code == "ffmpeg_unavailable"
        # A terminally failed segment never gets claimed again.
        assert repository.claim_next_queued_acoustic_analysis(now=now + timedelta(days=1), claimed_by="w") is None


@requires_ffmpeg
class TestConsolidation:
    def test_three_consecutive_segments_get_distinct_sort_orders(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        """Regression test (found via review): a hardcoded `sort_order=1`
        in `extend_acoustic_candidate_visit` meant every extension past the
        second segment of one continuous encounter collided on the same
        `sort_order`. A bird calling across three consecutive segments
        must produce three evidence links with three distinct, increasing
        `sort_order` values."""

        # Short (3s), back-to-back segments, each with a detection spanning
        # virtually its whole duration -- so every consecutive pair's
        # absolute window boundary lands with zero gap, a clean, simple way
        # to construct "one continuous encounter across 3 segments"
        # deterministically without fighting simulated-clock arithmetic.
        segment_seconds = 3
        paths = [tmp_path / f"seg{i}.wav" for i in range(3)]
        for i, p in enumerate(paths):
            _generate_tone(p, duration_seconds=float(segment_seconds), frequency=1000 + i)
        source = ScriptedSegmentSource(
            STREAM_ID,
            [
                (p, T0 + timedelta(seconds=i * segment_seconds), timedelta(seconds=segment_seconds))
                for i, p in enumerate(paths)
            ],
        )
        svc = ar.AcousticRuntimeService(repository=repository, segment_source=source)
        results = []
        for i in range(3):
            svc._recording = FakeRecording(
                detections=[{**CARDINAL_DETECTION, "start_time": 0.0, "end_time": float(segment_seconds)}],
                duration=float(segment_seconds),
            )
            now = T0 + timedelta(seconds=i * segment_seconds)
            source.advance_to(now)
            svc.ingest_available_segments(now=now)
            results.append(svc.process_next_queued(now=now))

        assert all(r.status == "completed" for r in results)
        visit_id = results[0].visit_ids[0]
        assert results[1].visit_ids[0] == visit_id
        assert results[2].visit_ids[0] == visit_id  # all three consolidated onto one Visit

        with repository.session_factory() as session:
            from mockingbird.repository.product_repository import VisitEvidenceLinkModel

            links = session.query(VisitEvidenceLinkModel).filter_by(visit_id=visit_id).all()
            sort_orders = sorted(link.sort_order for link in links)
        assert sort_orders == [0, 1, 2]

    def test_same_species_adjacent_segments_extend_the_same_visit(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        seg1, seg2 = tmp_path / "seg1.wav", tmp_path / "seg2.wav"
        _generate_tone(seg1)
        _generate_tone(seg2)
        source = ScriptedSegmentSource(
            STREAM_ID,
            [(seg1, T0, timedelta(seconds=15)), (seg2, T0 + timedelta(seconds=15), timedelta(seconds=15))],
        )
        svc = ar.AcousticRuntimeService(
            repository=repository, segment_source=source,
            recording=FakeRecording(
                detections=[{**CARDINAL_DETECTION, "start_time": 12.0, "end_time": 15.0}], duration=15.0,
            ),
        )
        source.advance_to(T0)
        svc.ingest_available_segments(now=T0)
        first = svc.process_next_queued(now=T0)
        assert first.status == "completed" and first.species_suggestions_created == 1

        svc._recording = FakeRecording(
            detections=[{**CARDINAL_DETECTION, "start_time": 0.5, "end_time": 3.0}], duration=15.0,
        )
        source.advance_to(T0 + timedelta(seconds=15))
        svc.ingest_available_segments(now=T0 + timedelta(seconds=15))
        second = svc.process_next_queued(now=T0 + timedelta(seconds=16))

        assert second.status == "completed"
        assert second.visit_ids == first.visit_ids
        assert svc.status().counters.candidates_created == 1
        assert svc.status().counters.candidates_extended == 1

        suggestions = repository.list_species_suggestions(visit_id=first.visit_ids[0])
        assert len(suggestions) == 2  # original provenance preserved, not overwritten

        # Regression (found via review): an "extended" outcome must be
        # honestly reported as zero NEW Visits/Events -- the second run's
        # own `visits_created`/`events_created` must not double-count the
        # first run's already-existing Visit/Event as if it were freshly
        # created again.
        assert first.visits_created == 1
        assert first.events_created == 1
        assert second.visits_created == 0
        assert second.events_created == 0
        assert second.species_suggestions_created == 1  # a real new suggestion row, correctly counted

    def test_different_species_do_not_get_merged(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        seg1, seg2 = tmp_path / "seg1.wav", tmp_path / "seg2.wav"
        _generate_tone(seg1)
        _generate_tone(seg2)
        source = ScriptedSegmentSource(
            STREAM_ID,
            [(seg1, T0, timedelta(seconds=15)), (seg2, T0 + timedelta(seconds=15), timedelta(seconds=15))],
        )
        svc = ar.AcousticRuntimeService(
            repository=repository, segment_source=source,
            recording=FakeRecording(
                detections=[{**CARDINAL_DETECTION, "start_time": 12.0, "end_time": 15.0}], duration=15.0,
            ),
        )
        source.advance_to(T0)
        svc.ingest_available_segments(now=T0)
        first = svc.process_next_queued(now=T0)

        svc._recording = FakeRecording(
            detections=[{**CHICKADEE_DETECTION, "start_time": 0.5, "end_time": 3.0}], duration=15.0,
        )
        source.advance_to(T0 + timedelta(seconds=15))
        svc.ingest_available_segments(now=T0 + timedelta(seconds=15))
        second = svc.process_next_queued(now=T0 + timedelta(seconds=16))

        assert second.visit_ids != first.visit_ids  # two genuinely distinct encounters
        assert svc.status().counters.candidates_created == 2
        assert svc.status().counters.candidates_extended == 0

    def test_a_reviewed_visit_is_never_silently_extended(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        """Reviewed-truth preservation: once a human has reviewed the first
        candidate, a same-species adjacent segment must fall back to a
        brand-new candidate rather than silently attaching new evidence to
        (and touching) the already-reviewed Visit."""

        seg1, seg2 = tmp_path / "seg1.wav", tmp_path / "seg2.wav"
        _generate_tone(seg1)
        _generate_tone(seg2)
        source = ScriptedSegmentSource(
            STREAM_ID,
            [(seg1, T0, timedelta(seconds=15)), (seg2, T0 + timedelta(seconds=15), timedelta(seconds=15))],
        )
        svc = ar.AcousticRuntimeService(
            repository=repository, segment_source=source,
            recording=FakeRecording(
                detections=[{**CARDINAL_DETECTION, "start_time": 12.0, "end_time": 15.0}], duration=15.0,
            ),
        )
        source.advance_to(T0)
        svc.ingest_available_segments(now=T0)
        first = svc.process_next_queued(now=T0)
        visit_id = first.visit_ids[0]

        repository.create_review_label(
            ReviewCorrectionCreate(
                target_type="visit", target_id=visit_id, label="northern_cardinal", review_origin="human",
            )
        )
        reviewed_visit = repository.get_visit(visit_id)
        assert reviewed_visit.review_status.value == "reviewed"
        assert reviewed_visit.reviewed_label == "northern_cardinal"

        svc._recording = FakeRecording(
            detections=[{**CARDINAL_DETECTION, "start_time": 0.5, "end_time": 3.0}], duration=15.0,
        )
        source.advance_to(T0 + timedelta(seconds=15))
        svc.ingest_available_segments(now=T0 + timedelta(seconds=15))
        second = svc.process_next_queued(now=T0 + timedelta(seconds=16))

        assert second.status == "completed"
        assert second.visit_ids != first.visit_ids  # a NEW candidate, not an extension
        still_reviewed = repository.get_visit(visit_id)
        assert still_reviewed.review_status.value == "reviewed"
        assert still_reviewed.reviewed_label == "northern_cardinal"  # untouched


@requires_ffmpeg
class TestRetention:
    def test_non_evidence_audio_is_deleted_after_ttl_evidence_audio_never_is(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        no_bird, has_bird = tmp_path / "nobird.wav", tmp_path / "hasbird.wav"
        _generate_tone(no_bird, frequency=500)
        _generate_tone(has_bird, frequency=1500)
        source = ScriptedSegmentSource(
            STREAM_ID,
            [(no_bird, T0, timedelta(seconds=15)), (has_bird, T0 + timedelta(seconds=15), timedelta(seconds=15))],
        )
        svc = ar.AcousticRuntimeService(
            repository=repository, segment_source=source, recording=FakeRecording(detections=[], duration=15.0),
        )
        source.advance_to(T0)
        svc.ingest_available_segments(now=T0)
        no_bird_result = svc.process_next_queued(now=T0)
        assert no_bird_result.species_suggestions_created == 0
        no_bird_media_id = no_bird_result.media_asset_id

        svc._recording = FakeRecording(detections=[CARDINAL_DETECTION], duration=15.0)
        source.advance_to(T0 + timedelta(seconds=15))
        svc.ingest_available_segments(now=T0 + timedelta(seconds=15))
        has_bird_result = svc.process_next_queued(now=T0 + timedelta(seconds=16))
        assert has_bird_result.species_suggestions_created == 1
        has_bird_media_id = has_bird_result.media_asset_id

        far_future = T0 + timedelta(days=30)
        result = svc.run_retention(now=far_future, force=True)

        assert result.deleted_count == 1
        assert repository.get_media_asset(no_bird_media_id) is None  # non-evidence, gone
        assert repository.get_media_asset(has_bird_media_id) is not None  # evidence, preserved

    def test_manually_imported_audio_is_never_deleted_by_retention(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        """Regression test (found via review): a user-imported audio
        recording (`create_media_import`) never gets a `VisitEvidenceLinkModel`
        row -- its Visit links via `representative_media_path` only. An
        earlier version of the retention sweep's eligibility check was
        `media_type == "audio" and zero VisitEvidenceLinkModel rows`, which
        made every manually-imported audio recording that either has not
        been analyzed yet, or was analyzed and found nothing, eligible for
        deletion after the same 48h TTL meant only for the runtime's own
        ephemeral working segments. The explicit `acoustic_working_segment`
        marker (set only by the automatic pipeline's own import path) must
        be the only thing that makes this sweep touch a file."""

        audio_path = tmp_path / "clip.wav"
        _generate_tone(audio_path)
        import_result = repository.create_media_import(
            content=audio_path.read_bytes(), original_filename="field-recording.wav",
            content_type="audio/wav", stream_id=STREAM_ID,
        )
        media_asset_id = import_result.media_asset.id
        assert repository.get_media_asset(media_asset_id).local_path is not None

        far_future = T0 + timedelta(days=365)
        svc = ar.AcousticRuntimeService(
            repository=repository, segment_source=ScriptedSegmentSource(STREAM_ID, []),
        )
        result = svc.run_retention(now=far_future, force=True)

        assert result.deleted_count == 0
        assert repository.get_media_asset(media_asset_id) is not None
        assert Path(repository.get_media_asset(media_asset_id).local_path).is_file()

    def test_in_flight_audio_is_never_deleted_by_retention(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        seg_path = tmp_path / "seg.wav"
        _generate_tone(seg_path)
        source = ScriptedSegmentSource(STREAM_ID, [(seg_path, T0, timedelta(seconds=15))])
        svc = ar.AcousticRuntimeService(repository=repository, segment_source=source)
        source.advance_to(T0)
        svc.ingest_available_segments(now=T0)
        diagnostics = repository.acoustic_analysis_queue_diagnostics(T0)
        assert diagnostics.queued_count == 1

        result = svc.run_retention(now=T0 + timedelta(days=30), force=True)
        assert result.deleted_count == 0  # still queued -- must not be reclaimed out from under itself


@requires_ffmpeg
class TestTimestampDeterminism:
    """Phase F: deterministic conversion from segment timestamp + BirdNET
    window offset -> acoustic detection time range, proven end to end
    through the real automatic pipeline (segment.started_at -> MediaAsset.
    captured_at -> Event/SpeciesSuggestion absolute timestamps) -- not just
    the capture-layer math already covered in `test_audio_capture.py::
    TestCapturedSegmentTiming`."""

    def test_segment_start_plus_birdnet_offset_yields_the_expected_absolute_window(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        seg_path = tmp_path / "seg.wav"
        _generate_tone(seg_path)
        known_segment_start = datetime(2026, 3, 1, 6, 30, 0, tzinfo=UTC)
        source = ScriptedSegmentSource(STREAM_ID, [(seg_path, known_segment_start, timedelta(seconds=15))])
        svc = ar.AcousticRuntimeService(
            repository=repository, segment_source=source,
            recording=FakeRecording(
                detections=[
                    {
                        "common_name": "Northern Cardinal", "scientific_name": "Cardinalis cardinalis",
                        "confidence": 0.9,
                        # A deliberately non-zero, non-trivial offset within the
                        # clip -- 2.0s to 5.0s -- to prove real arithmetic, not
                        # a coincidental zero-offset pass.
                        "start_time": 2.0, "end_time": 5.0,
                    },
                ],
                duration=15.0,
            ),
        )
        source.advance_to(known_segment_start)
        svc.ingest_available_segments(now=known_segment_start)
        result = svc.process_next_queued(now=known_segment_start)
        assert result.status == "completed" and result.species_suggestions_created == 1

        media_asset = repository.get_media_asset(result.media_asset_id)
        assert media_asset.captured_at == known_segment_start

        event = repository.get_event(result.event_ids[0])
        assert event.started_at == known_segment_start + timedelta(seconds=2)
        assert event.ended_at == known_segment_start + timedelta(seconds=5)

        suggestions = repository.list_species_suggestions(visit_id=result.visit_ids[0])
        assert len(suggestions) == 1
        assert suggestions[0].window_start_ms == 2000
        assert suggestions[0].window_end_ms == 5000

    def test_unknown_capture_time_falls_back_to_the_honest_epoch_anchor_never_now(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        """A segment/MediaAsset with no known real capture time must never
        silently derive its observed time from "now" (analysis time) --
        see acoustic_ingest.EPOCH_ANCHOR's own doctrine. Exercised directly
        against the shared execution primitive since the automatic
        pipeline's own segments always know their capture time by
        construction (derived from the capture session's own start) --
        this is a defense-in-depth proof for any future segment source
        that legitimately does not know real capture time."""

        from mockingbird.observation import acoustic_ingest
        from mockingbird.repository.product_repository import MediaAssetModel

        audio_path = tmp_path / "clip.wav"
        _generate_tone(audio_path)
        with repository.session_factory() as session:
            with session.begin():
                session.add(
                    MediaAssetModel(
                        id="media-unknown-capture-time", source_id="source-backyard-demo",
                        stream_id=STREAM_ID, filename=audio_path.name, content_type="audio/wav",
                        media_type="audio", local_path=str(audio_path),
                        original_filename=audio_path.name, file_size_bytes=audio_path.stat().st_size,
                        created_at=datetime.now(UTC), captured_at=None, notes="test",
                    )
                )

        result = acoustic_ingest.run_acoustic_analysis(
            repository, media_asset_id="media-unknown-capture-time",
            recording=FakeRecording(detections=[CARDINAL_DETECTION], duration=15.0),
        )
        assert result.status == "completed"
        assert result.capture_time_known is False

        event = repository.get_event(result.event_ids[0])
        assert event.started_at == acoustic_ingest.EPOCH_ANCHOR
        assert event.started_at.year == 1970  # honestly not a real date, never "now"


@requires_ffmpeg
class TestDiagnostics:
    def test_status_combines_counters_and_durable_queue_state(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        seg_path = tmp_path / "seg.wav"
        _generate_tone(seg_path)
        source = ScriptedSegmentSource(STREAM_ID, [(seg_path, T0, timedelta(seconds=15))])
        svc = ar.AcousticRuntimeService(repository=repository, segment_source=source)

        status_before = svc.status(now=T0)
        assert status_before.queue.queued_count == 0
        assert status_before.counters.segments_received == 0

        source.advance_to(T0)
        svc.ingest_available_segments(now=T0)
        status_after = svc.status(now=T0)
        assert status_after.queue.queued_count == 1
        assert status_after.counters.segments_received == 1
        assert status_after.counters.segments_imported == 1
        assert status_after.active_stream_count == 1

    def test_oldest_queued_age_is_reported_honestly(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        assert repository.acoustic_analysis_queue_diagnostics(T0).oldest_queued_age_seconds is None

        seg_path = tmp_path / "seg.wav"
        _generate_tone(seg_path)
        source = ScriptedSegmentSource(STREAM_ID, [(seg_path, T0, timedelta(seconds=15))])
        svc = ar.AcousticRuntimeService(repository=repository, segment_source=source)
        source.advance_to(T0)
        svc.ingest_available_segments(now=T0)

        later = T0 + timedelta(minutes=7)
        diagnostics = repository.acoustic_analysis_queue_diagnostics(later)
        assert diagnostics.oldest_queued_age_seconds == pytest.approx(420.0, abs=1.0)
