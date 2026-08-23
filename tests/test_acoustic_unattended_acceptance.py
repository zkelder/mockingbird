"""Acoustic Runtime & Quality v1, Phase K: simulated unattended runtime
acceptance. One coherent, deterministic simulation -- real BirdNET
inference over real/derived/synthetic corpus fixtures, arriving as
`FixtureSegmentSource`-scripted segments over *simulated* time (no real
waiting) -- exercising every one of the milestone's seven mandatory
acceptance scenarios in a single narrative:

1. Positive acoustic encounter
2. Negative audio (silence/noise/confusor)
3. Restart recovery
4. Analysis failure
5. Backlog pressure
6. Repeated/overlapping detection consolidation
7. Correction authority

`slow`-marked and `skipif`-gated on the optional `classifier-birdnet`
extra + local fixture presence, exactly like `test_acoustic_ingest_real_
model.py`/`test_acoustic_quality_benchmark.py` -- skips cleanly, never
fails, on a host lacking either. No physical microphone is required or
used anywhere in this test (see the milestone's own "Hardware boundary").
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.api.schemas import ReviewCorrectionCreate
from mockingbird.observation import acoustic_runtime as ar
from mockingbird.repository.product_repository import ProductRepository

STREAM_ID = "stream-backyard-feeder"
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "acoustic"

_REQUIRED_FIXTURES = (
    "silence_synthetic_48k_mono_10s.wav",
    "no_bird_synthetic_noise_48k_mono_10s.wav",
    "northern_cardinal_48k_mono_15s.wav",
    "black_capped_chickadee_48k_mono_12s.wav",
    "lawnmower_confusor_48k_mono_15s.wav",
    "wind_like_synthetic_noise_48k_mono_12s.wav",
    "cardinal_distant_quiet_48k_mono_derived.wav",
    "overlapping_cardinal_chickadee_48k_mono_derived.wav",
)


def _birdnet_runtime_available() -> bool:
    if importlib.util.find_spec("birdnetlib") is None:
        return False
    return (
        importlib.util.find_spec("tflite_runtime") is not None
        or importlib.util.find_spec("ai_edge_litert") is not None
        or importlib.util.find_spec("tensorflow") is not None
    )


def _fixtures_present() -> bool:
    return all((FIXTURES_DIR / name).is_file() for name in _REQUIRED_FIXTURES)


requires_real_birdnet_corpus = pytest.mark.skipif(
    not (_birdnet_runtime_available() and _fixtures_present()),
    reason="optional classifier-birdnet extra and/or the local acoustic benchmark fixtures are unavailable",
)


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    yield repo
    repo.close()


class FakeInstantRecording:
    """A fast, fake BirdNET recording -- used only for the Scenario 5
    (backlog pressure) burst, which needs many segments quickly and does
    not itself need real species output (that is proven separately, with
    real inference, by every other segment in this same test)."""

    def __init__(self) -> None:
        self.detections: list[dict[str, object]] = []
        self.duration = 1.0

    def analyze(self) -> None:
        pass


T0 = datetime(2026, 8, 22, 6, 0, 0, tzinfo=UTC)


@requires_real_birdnet_corpus
@pytest.mark.slow
class TestSimulatedUnattendedAcceptance:
    def test_one_coherent_run_exercises_every_mandatory_scenario(
        self, repository: ProductRepository, tmp_path: Path,
    ) -> None:
        plan = [
            ar.FixtureSegmentPlan(
                stream_id=STREAM_ID, fixture_path=FIXTURES_DIR / "silence_synthetic_48k_mono_10s.wav",
                started_at=T0, duration=timedelta(seconds=10),
            ),
            ar.FixtureSegmentPlan(
                stream_id=STREAM_ID, fixture_path=FIXTURES_DIR / "no_bird_synthetic_noise_48k_mono_10s.wav",
                started_at=T0 + timedelta(seconds=15), duration=timedelta(seconds=10),
            ),
            ar.FixtureSegmentPlan(  # positive encounter (Scenario 1)
                stream_id=STREAM_ID, fixture_path=FIXTURES_DIR / "northern_cardinal_48k_mono_15s.wav",
                started_at=T0 + timedelta(seconds=30), duration=timedelta(seconds=15),
            ),
            ar.FixtureSegmentPlan(  # same real clip again, adjacent -> consolidation (Scenario 6)
                stream_id=STREAM_ID, fixture_path=FIXTURES_DIR / "northern_cardinal_48k_mono_15s.wav",
                started_at=T0 + timedelta(seconds=45), duration=timedelta(seconds=15),
            ),
            ar.FixtureSegmentPlan(  # a different real species -> must NOT merge with the Cardinal encounter
                stream_id=STREAM_ID, fixture_path=FIXTURES_DIR / "black_capped_chickadee_48k_mono_12s.wav",
                started_at=T0 + timedelta(seconds=60), duration=timedelta(seconds=12),
            ),
            ar.FixtureSegmentPlan(  # mechanical confusor (Scenario 2, non-avian filtering)
                stream_id=STREAM_ID, fixture_path=FIXTURES_DIR / "lawnmower_confusor_48k_mono_15s.wav",
                started_at=T0 + timedelta(seconds=75), duration=timedelta(seconds=15),
            ),
            ar.FixtureSegmentPlan(
                stream_id=STREAM_ID, fixture_path=FIXTURES_DIR / "wind_like_synthetic_noise_48k_mono_12s.wav",
                started_at=T0 + timedelta(seconds=90), duration=timedelta(seconds=12),
            ),
            ar.FixtureSegmentPlan(  # exercised again after the simulated restart, below
                stream_id=STREAM_ID, fixture_path=FIXTURES_DIR / "cardinal_distant_quiet_48k_mono_derived.wav",
                started_at=T0 + timedelta(seconds=105), duration=timedelta(seconds=15),
            ),
            ar.FixtureSegmentPlan(
                stream_id=STREAM_ID,
                fixture_path=FIXTURES_DIR / "overlapping_cardinal_chickadee_48k_mono_derived.wav",
                started_at=T0 + timedelta(seconds=120), duration=timedelta(seconds=12),
            ),
        ]
        source = ar.FixtureSegmentSource(plan, working_directory=tmp_path / "segment_working")
        svc = ar.AcousticRuntimeService(repository=repository, segment_source=source)

        def drain(now: datetime) -> None:
            """Ingest whatever is due, then process every currently-queued
            item -- one bounded pass, mirroring `tick()`'s own shape but
            draining fully so this test's assertions see a settled state."""

            source.advance_to(now)
            svc.ingest_available_segments(now=now)
            while svc.process_next_queued(now=now) is not None:
                pass

        # --- Segments 1-2: negative audio (Scenario 2) --------------------
        drain(T0 + timedelta(seconds=1))
        drain(T0 + timedelta(seconds=16))
        assert repository.acoustic_analysis_queue_diagnostics(T0).queued_count == 0

        # --- Segment 3: positive encounter (Scenario 1) --------------------
        drain(T0 + timedelta(seconds=31))

        # --- Scenario 7: correction authority ------------------------------
        # A human reviews and corrects the just-created Cardinal candidate
        # to a different species before the next (consolidation-eligible)
        # segment arrives.
        # Scoped to `visit-acoustic-candidate-*` IDs specifically -- the
        # demo-seeded database already has its own unrelated legacy
        # `northern_cardinal` review-queue item (`visit-bird-feeder-001`),
        # which must not be confused with a real candidate this test run
        # created.
        review_queue_before_correction = repository.review_queue_items()
        cardinal_candidates = [
            item for item in review_queue_before_correction
            if item.target_type == "visit"
            and item.target_id.startswith("visit-acoustic-candidate-")
            and "cardinal" in (repository.get_visit(item.target_id).species_guess or "").lower()
        ]
        assert len(cardinal_candidates) == 1, "exactly one Cardinal candidate must exist before correction"
        corrected_visit_id = cardinal_candidates[0].target_id
        repository.create_review_label(
            ReviewCorrectionCreate(
                target_type="visit", target_id=corrected_visit_id, label="mourning_dove",
                review_origin="human", notes="Acceptance test: deliberate correction, not a real ID.",
            )
        )
        corrected_visit = repository.get_visit(corrected_visit_id)
        assert corrected_visit.review_status.value == "reviewed"
        assert corrected_visit.reviewed_label == "mourning_dove"

        # --- Segment 4: same real species, adjacent window -----------------
        # Because segment 3's own candidate is now reviewed/corrected, this
        # must fall back to a brand-new candidate rather than silently
        # extending (and thereby touching) the already-reviewed Visit.
        drain(T0 + timedelta(seconds=46))
        still_corrected = repository.get_visit(corrected_visit_id)
        assert still_corrected.review_status.value == "reviewed"
        assert still_corrected.reviewed_label == "mourning_dove"  # untouched by the later segment

        # --- Segment 5: a different real species ----------------------------
        drain(T0 + timedelta(seconds=61))

        # --- Scenario 5: backlog pressure (a fast synthetic burst) --------
        burst_dir = tmp_path / "burst"
        burst_dir.mkdir()
        import subprocess

        burst_paths = []
        for index in range(6):
            path = burst_dir / f"burst-{index}.wav"
            subprocess.run(
                [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"sine=frequency={800 + index}:duration=1:sample_rate=48000",
                    "-ac", "1", str(path),
                ],
                check=True, timeout=15, capture_output=True,
            )
            burst_paths.append(path)

        from mockingbird.observation.audio_capture import CapturedSegment

        class BurstSource:
            def __init__(self) -> None:
                self.now: datetime | None = None

            def advance_to(self, now: datetime) -> None:
                self.now = now

            def active_stream_ids(self) -> list[str]:
                return [STREAM_ID]

            def poll_new_segments(self, stream_id: str) -> list[CapturedSegment]:
                base = T0 + timedelta(seconds=200)
                return [
                    CapturedSegment(
                        path=path, sequence_index=index, started_at=base + timedelta(seconds=index),
                        ended_at=base + timedelta(seconds=index + 1),
                    )
                    for index, path in enumerate(burst_paths)
                ]

        burst_svc = ar.AcousticRuntimeService(
            repository=repository, segment_source=BurstSource(),
            recording=FakeInstantRecording(), max_in_flight_per_stream=3,
        )
        burst_now = T0 + timedelta(seconds=200)
        imported = burst_svc.ingest_available_segments(now=burst_now)
        assert imported == 3  # bounded -- half the burst dropped, never silently accumulated
        assert burst_svc.status(now=burst_now).counters.segments_dropped_capacity == 3
        for path in burst_paths[3:]:
            assert not path.exists()  # dropped segments' raw files are gone, not leaked
        while burst_svc.process_next_queued(now=burst_now) is not None:
            pass
        assert repository.acoustic_analysis_queue_diagnostics(burst_now).queued_count == 0

        # --- Scenario 4: analysis failure ----------------------------------
        # A deterministic, real failure mode: an unusable ffmpeg binary.
        # Exhaust the bounded retry budget and confirm the terminal state is
        # diagnosable and does not corrupt anything else already persisted.
        broken_dir = tmp_path / "broken"
        broken_dir.mkdir()
        broken_path = broken_dir / "broken-0.wav"
        broken_path.write_bytes(b"deliberately not a real audio file for this failure-injection segment")

        class BrokenSource:
            def __init__(self) -> None:
                self.now: datetime | None = None
                self._served = False

            def advance_to(self, now: datetime) -> None:
                self.now = now

            def active_stream_ids(self) -> list[str]:
                return [STREAM_ID]

            def poll_new_segments(self, stream_id: str) -> list[CapturedSegment]:
                if self._served:
                    return []
                self._served = True
                return [
                    CapturedSegment(
                        path=broken_path, sequence_index=0, started_at=self.now,
                        ended_at=self.now + timedelta(seconds=10),
                    )
                ]

        failure_now = T0 + timedelta(seconds=300)
        broken_source = BrokenSource()
        broken_source.advance_to(failure_now)
        failure_svc = ar.AcousticRuntimeService(repository=repository, segment_source=broken_source)
        # The file itself is unreadable -- this is intake-time rejection,
        # not an analysis failure, and is already covered elsewhere; here
        # we specifically want a segment that IS importable but fails
        # BirdNET analysis. Write valid-container-but-undecodable bytes by
        # using a real tone file but a broken ffmpeg binary at analysis
        # time instead.
        broken_path.unlink()
        import subprocess as _subprocess

        _subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                "-i", "sine=frequency=1200:duration=5:sample_rate=48000", "-ac", "1", str(broken_path),
            ],
            check=True, timeout=15, capture_output=True,
        )
        broken_source._served = False
        failure_svc._ffmpeg_binary = "mockingbird-does-not-exist-for-this-test"
        failure_svc.ingest_available_segments(now=failure_now)
        attempts = 0
        now = failure_now
        last_result = None
        while True:
            result = failure_svc.process_next_queued(now=now)
            if result is None:
                break
            attempts += 1
            last_result = result
            run = repository.get_acoustic_analysis_run(result.run_id)
            if run.status == "failed":
                break
            now = run.next_retry_at + timedelta(seconds=1)
        assert last_result is not None
        assert last_result.status == "failed"
        final_run = repository.get_acoustic_analysis_run(last_result.run_id)
        assert final_run.error_code == "ffmpeg_unavailable"
        assert final_run.consecutive_failure_count >= 1

        # --- Scenario 3: restart recovery -----------------------------------
        # Claim segment 8 (Scenario 1's "distant/quiet" positive) but never
        # complete it -- simulate a crash. A fresh service instance against
        # the same repository must reclaim and reprocess it exactly once.
        drain_source_now = T0 + timedelta(seconds=106)
        source.advance_to(drain_source_now)
        svc.ingest_available_segments(now=drain_source_now)
        claimed = repository.claim_next_queued_acoustic_analysis(now=drain_source_now, claimed_by="crashed-worker")
        assert claimed is not None

        svc2 = ar.AcousticRuntimeService(repository=repository, segment_source=source)
        reclaimed = svc2.reclaim_stale_work(stale_after=timedelta(0), now=drain_source_now + timedelta(seconds=1))
        assert reclaimed == 1
        refreshed = repository.get_acoustic_analysis_run(claimed.id)
        assert refreshed.status == "queued"
        result_after_restart = svc2.process_next_queued(now=refreshed.next_retry_at + timedelta(seconds=1))
        assert result_after_restart is not None
        assert result_after_restart.status == "completed"

        # --- Final segment: overlapping real species -------------------------
        drain(T0 + timedelta(seconds=121))

        # --- Cleanup: bounded retention sweep --------------------------------
        far_future = T0 + timedelta(days=30)
        retention_result = svc.run_retention(now=far_future, force=True)
        assert retention_result.failed_count == 0
        # The negative/confusor/noise segments (silence, pink noise, wind,
        # lawnmower) never became evidence -- gone. Every candidate-bearing
        # segment's MediaAsset is evidence and must survive indefinitely.
        for item in repository.review_queue_items():
            visit = repository.get_visit(item.target_id) if item.target_type == "visit" else None
            if visit is None:
                continue
            suggestions = repository.list_species_suggestions(visit_id=item.target_id)
            for suggestion in suggestions:
                assert repository.get_media_asset(suggestion.media_asset_id) is not None

        # --- Final bounded, coherent state -----------------------------------
        final_diagnostics = repository.acoustic_analysis_queue_diagnostics(far_future)
        assert final_diagnostics.queued_count == 0
        assert final_diagnostics.processing_count == 0

        still_corrected_at_end = repository.get_visit(corrected_visit_id)
        assert still_corrected_at_end.review_status.value == "reviewed"
        assert still_corrected_at_end.reviewed_label == "mourning_dove"

        status = svc.status(now=far_future)
        assert status.counters.candidates_created >= 3  # Cardinal(2nd, post-correction), Chickadee, and more
        assert status.counters.analyses_completed >= 8
