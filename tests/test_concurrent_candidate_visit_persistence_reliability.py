"""Concurrent Candidate Visit Persistence Reliability v1 (see docs/
concurrent-candidate-visit-persistence-reliability-v1-report.md).

Multi-Camera Place Experience v2's own real, measured concurrency test
(`tests/test_multi_camera_concurrent_runtime.py`) reproduced a genuine,
occasional lost candidate-Visit under real concurrent multi-Stream SQLite
writes -- but only probabilistically, and only under real host CPU/disk
contention this sandbox does not carry by default (confirmed directly during
this milestone's own investigation: the existing test passed 10/10 times
idle, and needed real induced background load to fail even once). That test
remains valuable end-to-end evidence and is unchanged by this milestone, but
it is not a reliable *regression gate* on its own.

This file adds a **deterministic** reproduction of the exact same real
mechanism -- a genuine `sqlite3.OperationalError: database is locked` raised
mid-transaction inside `ProductRepository.create_candidate_visit_from_
proposal` -- by holding a real second SQLite connection's own write lock
(`BEGIN IMMEDIATE`) for longer than the engine's configured `busy_timeout`
(5000ms), standing in for a second Stream's own concurrent writer connection
exactly as the real multi-thread test does, without needing artificial host
load or scheduler luck. The real, unmodified production path is driven
throughout: `CandidateVisitAuthorityAdapter.attempt_candidate` ->
`ProductRepository.create_candidate_visit_from_proposal`, against a real
on-disk SQLite file, via a real, assembler-produced `AssembledVisitProposal`
(`assemble_visit_episodes`) -- never a hand-built fact or a synthetic code
path that bypasses the real repository operation.

Independently verified RED against the pre-fix implementation (`git stash`)
and GREEN after -- see the milestone report's "Tests added" for the exact
before/after result.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sqlite3
import threading
import time

from mockingbird.observation.candidate_visit_adapter import CandidateVisitAuthorityAdapter
from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode
from mockingbird.observation.contracts import EvidenceCandidate
from mockingbird.observation.visit_episode_assembler import Tracklet, assemble_visit_episodes
from mockingbird.repository.product_repository import ObservationCandidateVisitModel, ProductRepository
from mockingbird.storage.models import CameraSourceModel, StreamModel

NOW = datetime(2026, 8, 8, 12, 0, 0, tzinfo=UTC)
QUIET_STREAM_ID = "stream-quiet"
BUSY_STREAM_ID = "stream-busy"
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"1" * 128 + b"\xff\xd9"

# Comfortably longer than `create_database_engine`'s own configured
# `PRAGMA busy_timeout=5000` (src/mockingbird/storage/database.py) -- long
# enough that the quiet Stream's first attempt is guaranteed to exhaust its
# own busy-wait and raise, short enough that its bounded second attempt
# (starting well before this deadline, per `candidate_visit_adapter`'s own
# short backoff) still comfortably succeeds once the lock releases, and the
# whole test stays well under a minute.
_LOCK_HOLD_SECONDS = 5.3


def _seed_two_streams(db_url: str, media_root: Path) -> None:
    setup = ProductRepository(db_url=db_url, media_root=media_root)
    with setup.session_factory() as session:
        with session.begin():
            for stream_id in (QUIET_STREAM_ID, BUSY_STREAM_ID):
                source_id = f"source-{stream_id}"
                session.add(
                    CameraSourceModel(
                        id=source_id, name=stream_id, kind="manual_upload", status="connected",
                        description="Concurrent-persistence-reliability fixture.",
                    )
                )
                session.add(
                    StreamModel(
                        id=stream_id, source_id=source_id, name=stream_id,
                        description="Concurrent-persistence-reliability fixture.", is_live=False,
                    )
                )
    setup.close()


def _quiet_stream_proposal():
    tracklet = Tracklet(
        generation_id="gen-quiet-1",
        stream_id=QUIET_STREAM_ID,
        broad_class="animal",
        start_offset_ms=0,
        end_offset_ms=4500,
        start_bounding_box=(0.4, 0.4, 0.5, 0.5),
        end_bounding_box=(0.42, 0.42, 0.52, 0.52),
        geometry_envelope=(0.4, 0.4, 0.52, 0.52),
        terminal_reason="maximum_unsupported_duration",
        track_ids=("gen-quiet-1-track",),
        source_capture_frame_ids=("gen-quiet-1-frame-1", "gen-quiet-1-frame-2"),
        evidence_candidate_ids=("shadow-burst:quiet-id", "shadow-burst:quiet-ctx"),
        zone_id=None,
    )
    return assemble_visit_episodes((tracklet,)).proposals[0]


def _quiet_stream_evidence() -> tuple[EvidenceCandidate, ...]:
    return (
        EvidenceCandidate(
            media_asset_id="shadow-burst:quiet-id", stream_id=QUIET_STREAM_ID, role="high_resolution_burst",
            captured_at=NOW, frame_id="gen-quiet-1-frame-1", width=1920, height=1080,
            subject_geometry=(0.4, 0.4, 0.5, 0.5), track_generation_id="gen-quiet-1",
            quality_facts=(("decodable", True), ("temporal_alignment", "aligned"), ("track_supported", True)),
        ),
        EvidenceCandidate(
            media_asset_id="shadow-burst:quiet-ctx", stream_id=QUIET_STREAM_ID, role="context",
            captured_at=NOW, frame_id="gen-quiet-1-frame-2", width=1920, height=1080,
            subject_geometry=(0.35, 0.35, 0.55, 0.55), track_generation_id="gen-quiet-1",
            quality_facts=(("decodable", True), ("temporal_alignment", "aligned"), ("track_supported", True)),
        ),
    )


def test_candidate_visit_survives_a_real_concurrent_sqlite_write_lock(tmp_path: Path) -> None:
    """The demonstrated root cause, forced deterministically: while a second
    real connection (standing in for `stream-busy`'s own concurrent writer
    connection, exactly as production's one-connection-per-Stream
    architecture has it -- see `engine_runtime.py`'s module docstring and
    `main.py`'s `get_observation_engine_session_manager`) holds a real
    SQLite write lock on the same shared file for longer than the engine's
    own configured `busy_timeout`, `stream-quiet`'s own admitted candidate
    must still end up as exactly one durable Visit -- never silently lost,
    never duplicated -- via this milestone's bounded, classified retry."""

    db_url = f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}"
    media_root = tmp_path / "media"
    _seed_two_streams(db_url, media_root)

    repository = ProductRepository(db_url=db_url, media_root=media_root)
    repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=QUIET_STREAM_ID, now=NOW, fresh_session=True,
    )
    adapter = CandidateVisitAuthorityAdapter(
        repository, detector_provenance="onnx-cuda", tracker_provenance="frame-driven-onnx-cuda",
        provider_key="frame-driven-onnx-cuda",
    )
    proposal = _quiet_stream_proposal()
    evidence = _quiet_stream_evidence()
    evidence_bytes = {candidate.media_asset_id: JPEG_BYTES for candidate in evidence}

    db_path = tmp_path / "mockingbird.sqlite3"
    lock_acquired = threading.Event()

    def _hold_write_lock() -> None:
        blocker = sqlite3.connect(str(db_path))
        try:
            blocker.execute("BEGIN IMMEDIATE")
            lock_acquired.set()
            time.sleep(_LOCK_HOLD_SECONDS)
            blocker.commit()
        finally:
            blocker.close()

    holder = threading.Thread(target=_hold_write_lock, name="stream-busy:writer")
    holder.start()
    assert lock_acquired.wait(timeout=5.0), "the competing writer never acquired its own real lock"
    try:
        outcome = adapter.attempt_candidate(
            proposal, evidence_candidates=evidence, evidence_bytes=evidence_bytes, observed_at=NOW,
        )
    finally:
        holder.join(timeout=_LOCK_HOLD_SECONDS + 10.0)
    assert not holder.is_alive(), "the competing writer's own thread did not finish"

    assert outcome.created, (
        f"candidate was lost under real SQLite lock contention instead of recovering "
        f"(outcome={outcome.outcome!r}, reason={outcome.reason!r})"
    )
    assert outcome.visit_id is not None

    with repository.session_factory() as session:
        ledger = session.get(ObservationCandidateVisitModel, proposal.proposal_id)
        assert ledger is not None
        assert ledger.visit_id == outcome.visit_id
        # Stream attribution survives the contention/retry path untouched --
        # never silently attributed to the busy Stream that caused it.
        assert ledger.stream_id == QUIET_STREAM_ID

    status = repository.get_observation_authority_state(stream_id=QUIET_STREAM_ID)
    # The eventual success is the only fact of record -- a candidate that
    # recovers via retry must never also be counted as a failure.
    assert status.failure_count == 0
    repository.close()
