"""Multi-Camera Place Experience v2 -- Phase 22/23/24/37: a genuine,
*measured* concurrent multi-Stream Observation Engine exercise, not a
theoretical claim. Per this milestone's own instruction ("Use deterministic
multi-camera fixtures/emulation where possible... Real hardware is useful if
conveniently available, but NOT required"), this drives the real
`_EngineSession._run_assembly_tick` admission/assembly path directly --
bypassing the detector/transport layer, following the same pattern
`test_engine_runtime.py::_tick_session`/`_tick_adapter`/`_tick_track_updates`/
`_tick_evidence` already established (this file's own `_varied_track_updates`/
`_varied_evidence` vary geometry/image content per encounter -- see their
docstrings for why: those originals' fixed single-encounter fixtures read as
a genuine, correctly-suppressed recurring static scene once reused across
many encounters) -- under REAL concurrent `threading.Thread`s, one per
Stream, matching production's own one-thread-per-Stream architecture (see
`engine_runtime.py`'s module docstring).

Deliberately, honestly bounded: this proves the admission/assembly layer's
own cross-Stream isolation and non-blocking behavior under real concurrent
writes to one shared SQLite file (each thread gets its own `ProductRepository`
instance/connection against the same `db_url`, matching production's actual
`repository_factory()` per-session construction -- see `main.py`'s
`get_observation_engine_session_manager` docstring -- rather than the
shared-instance shortcut most of `test_engine_runtime.py`'s own tests use).
It does NOT and cannot measure real GPU/CUDA-driver-level contention between
concurrent ONNX inference sessions on one physical GPU -- that remains a
genuinely open question needing real multi-camera hardware (see the
"Concurrent runtime" section of docs/multi-camera-place-experience-v2-report.md).
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

from PIL import Image

from mockingbird.observation import engine_runtime
from mockingbird.observation.candidate_visit_adapter import CandidateVisitAuthorityAdapter
from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode
from mockingbird.observation.contracts import EvidenceCandidate, TrackUpdate
from mockingbird.repository.product_repository import ProductRepository, StreamLivePlaybackConfig
from mockingbird.storage.models import CameraSourceModel, StreamModel

NOW = datetime(2026, 8, 8, 12, 0, 0, tzinfo=UTC)


def _stream_config(stream_id: str) -> StreamLivePlaybackConfig:
    return StreamLivePlaybackConfig(
        stream_id=stream_id, source_id=f"source-{stream_id}", provider_key="camera_node",
        live_stream_url=None, live_stream_type="camera_node",
        camera_node_base_address="http://192.168.1.50:8787", camera_node_credential="fixture-credential",
        camera_node_camera_id="cam-1", camera_node_id="node-1",
        camera_node_monitoring_profile_id="monitoring-profile", camera_node_evidence_profile_id="evidence-profile",
    )


def _tick_session_for(repository: ProductRepository, stream_id: str) -> engine_runtime._EngineSession:
    return engine_runtime._EngineSession(
        stream_id=stream_id,
        playback_config=_stream_config(stream_id),
        provider_config_path=Path("unused-for-this-test"),
        privacy_ignore_regions=(),
        repository_factory=lambda: repository,
    )


def _tick_adapter_for(repository: ProductRepository, stream_id: str) -> CandidateVisitAuthorityAdapter:
    return CandidateVisitAuthorityAdapter(
        repository, detector_provenance="onnx-cuda", tracker_provenance="frame-driven-onnx-cuda",
        provider_key="frame-driven-onnx-cuda",
    )


def _grid_box(index: int) -> tuple[float, float, float, float]:
    """A deterministic, non-repeating position on an 8x8 grid (64 distinct,
    non-overlapping cells) -- comfortably above this file's largest single
    workload (40), so no two encounters within one Stream's own run ever
    land on the same (or an adjacent, overlapping) region. See
    `_varied_track_updates`'s docstring for why a small cycle of positions
    is not enough."""

    row, col = (index // 8) % 8, index % 8
    x0, y0 = 0.05 + col * 0.1125, 0.05 + row * 0.1125
    return (x0, y0, x0 + 0.08, y0 + 0.08)


def _varied_track_updates(generation_id: str, start_ms: int, end_ms: int, *, index: int) -> tuple[TrackUpdate, TrackUpdate]:
    """Mirrors `test_engine_runtime.py::_tick_track_updates` exactly, except
    the bounding box moves a little per encounter. `_tick_track_updates`'s
    own fixed box is fine for its own single-encounter tests, but reusing
    one identical box across many synthetic encounters on the same Stream
    is a genuinely unrealistic fixture for *this* file's purpose (measuring
    concurrent throughput/isolation) -- it triggers Scene Confusor
    Suppression v1's real, correct, already-accepted `blocked_scene_
    confusor_suspected`/`recurring_static_scene_geometry` behavior after 3
    repeats at one exact geometry (schema 34; see docs/scene-confusor-
    suppression-v1-contract.md), silently capping every workload at 3
    candidates regardless of intended count -- a real product protection
    working exactly as designed, not a concurrency artifact, and not what
    this file is measuring."""

    box = _grid_box(index)
    return (
        TrackUpdate(
            track_id=f"{generation_id}-track", generation_id=generation_id,
            captured_at=NOW + timedelta(milliseconds=start_ms), status="started", lifecycle_state="confirmed",
            frame_id=f"frame-{generation_id}-start", source_offset_ms=start_ms, broad_class="animal",
            bounding_box=box, supporting_frame_ids=(f"frame-{generation_id}-start",),
            support_state="weak_detector_supported", detector_ran=True,
        ),
        TrackUpdate(
            track_id=f"{generation_id}-track", generation_id=generation_id,
            captured_at=NOW + timedelta(milliseconds=end_ms), status="ended", lifecycle_state="ended",
            frame_id=f"frame-{generation_id}-end", source_offset_ms=end_ms, broad_class="animal",
            bounding_box=box, supporting_frame_ids=(f"frame-{generation_id}-end",),
            support_state="weak_detector_supported", detector_ran=True,
            terminal_reason="maximum_unsupported_duration",
        ),
    )


def _varied_evidence(
    generation_id: str, role: str, suffix: str, *, stream_id: str, index: int
) -> tuple[EvidenceCandidate, bytes]:
    """Mirrors `test_engine_runtime.py::_tick_evidence`, except both the
    evidence's own `subject_geometry` (a field separate from `TrackUpdate.
    bounding_box` above -- Scene Confusor Suppression evaluates this one)
    and the image content itself vary per encounter. `_tick_evidence`'s
    fixed geometry/uniform green image are fine for its own single-
    encounter tests; reused across many synthetic encounters here, they
    are indistinguishable "recurring static scene" evidence to the real
    suppression logic -- see `_varied_track_updates`'s own docstring."""

    geometry = _grid_box(index)
    candidate = EvidenceCandidate(
        media_asset_id=f"shadow-burst:{suffix}", stream_id=stream_id, role=role, captured_at=NOW,
        frame_id=f"frame-{generation_id}-start", subject_geometry=geometry,
        track_generation_id=generation_id,
    )
    # A procedurally-varying color per index (not a short repeating cycle)
    # -- belt-and-suspenders alongside `_grid_box`'s own 64-cell spread, in
    # case image-content similarity is also part of what a real scene-
    # confusor signal considers.
    color = ((index * 37) % 256, (index * 71) % 256, (index * 113) % 256)
    buffer = BytesIO()
    Image.new("RGB", (1920, 1080), color=color).save(buffer, format="JPEG")
    return candidate, buffer.getvalue()


def _drive_one_encounter(
    session: engine_runtime._EngineSession,
    adapter: CandidateVisitAuthorityAdapter,
    *,
    stream_id: str,
    index: int,
) -> None:
    """One complete, independent, well-separated encounter -- start_ms
    offsets spaced 200s apart so no two encounters on the same Stream ever
    fall inside `merge_gap_ms` (15s) and get treated as one continuation."""

    generation_id = f"gen-{stream_id}-{index}"
    start_ms = index * 200_000
    updates = list(_varied_track_updates(generation_id, start_ms, start_ms + 4_000, index=index))
    evidence, media_bytes = _varied_evidence(
        generation_id, "high_resolution_burst", f"{stream_id}-{index}", stream_id=stream_id, index=index
    )
    session._run_assembly_tick(
        all_track_updates=updates,
        all_evidence_candidates=[evidence],
        attempted_proposal_ids=set(),
        burst_bytes_cache={evidence.media_asset_id: media_bytes},
        adapter=adapter,
        finalize=True,
    )


def _run_stream_workload(
    *, db_url: str, media_root: Path, stream_id: str, encounter_count: int, results: dict, errors: dict
) -> None:
    """The actual per-thread body -- its own repository/connection, its own
    session/adapter, exactly one real OS thread, mirroring `_EngineSession.
    start()`'s own `threading.Thread(target=self._run, ...)` shape."""

    started_at = time.monotonic()
    try:
        repository = ProductRepository(db_url=db_url, media_root=media_root)
        # `max_candidates_per_hour` (default 20) is a real, correct, already-
        # accepted per-Stream authority budget -- not a concurrency concern.
        # All of a synthetic workload's encounters land within the same real
        # wall-clock hour bucket regardless of their own synthetic
        # `captured_at` spacing, so a >20-encounter workload needs this
        # raised explicitly (exactly the documented override
        # `set_observation_authority_mode` exists for) to isolate what this
        # file actually measures -- cross-Stream concurrency, not this
        # unrelated, already-covered budget (see candidate-visit-authority-
        # contract.md and its own dedicated tests).
        repository.set_observation_authority_mode(
            ObservationAuthorityMode.candidate_visit, stream_id=stream_id, now=NOW, fresh_session=True,
            max_candidates_per_hour=max(20, encounter_count * 2),
        )
        session = _tick_session_for(repository, stream_id)
        adapter = _tick_adapter_for(repository, stream_id)
        for index in range(encounter_count):
            _drive_one_encounter(session, adapter, stream_id=stream_id, index=index)
        results[stream_id] = {
            "candidates_created": session._counts.candidates_created,
            "elapsed_seconds": time.monotonic() - started_at,
        }
        repository.close()
    except Exception as caught:  # pragma: no cover -- surfaced via assertion below
        errors[stream_id] = caught


def _run_concurrently(workloads: dict[str, int], *, tmp_path: Path) -> dict[str, dict]:
    db_url = f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}"
    media_root = tmp_path / "media"
    # Create the schema once, synchronously, before any concurrent writer --
    # exactly the real-world case of Streams starting at slightly different
    # moments, never the literal same nanosecond; the interesting concurrency
    # question is the tick-processing phase below, not schema migration
    # itself racing against itself. Each synthetic Stream also needs a real
    # CameraSourceModel/StreamModel row up front (candidate-Visit creation
    # is FK-backed) -- unlike test_engine_runtime.py's own STREAM_ID, which
    # deliberately reuses the auto-seeded demo Source/Stream, these are
    # genuinely separate cameras, matching this milestone's own subject.
    setup_repository = ProductRepository(db_url=db_url, media_root=media_root)
    with setup_repository.session_factory() as session:
        with session.begin():
            for stream_id in workloads:
                source_id = f"source-{stream_id}"
                session.add(
                    CameraSourceModel(
                        id=source_id, name=stream_id, kind="manual_upload",
                        status="connected", description="Concurrent-runtime measurement fixture.",
                    )
                )
                session.add(
                    StreamModel(
                        id=stream_id, source_id=source_id, name=stream_id,
                        description="Concurrent-runtime measurement fixture.", is_live=False,
                    )
                )
    setup_repository.close()

    results: dict[str, dict] = {}
    errors: dict[str, Exception] = {}
    threads = [
        threading.Thread(
            target=_run_stream_workload,
            kwargs=dict(
                db_url=db_url, media_root=media_root, stream_id=stream_id,
                encounter_count=count, results=results, errors=errors,
            ),
            name=f"observation-engine:{stream_id}",
        )
        for stream_id, count in workloads.items()
    ]
    overall_started_at = time.monotonic()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60.0)
    overall_elapsed = time.monotonic() - overall_started_at

    assert not errors, f"Concurrent Stream workload(s) raised: {errors}"
    assert all(not thread.is_alive() for thread in threads), "A Stream's workload did not finish within 60s"
    results["_overall_elapsed_seconds"] = overall_elapsed
    return results


def test_two_cameras_ordinary_concurrent_load_stays_isolated(tmp_path: Path) -> None:
    """2-camera ordinary topology (this milestone's own minimum bar):
    moderate, roughly balanced activity on both, run genuinely concurrently
    on real threads against one shared SQLite file. Each Stream's own
    candidate count must be exactly its own workload -- zero cross-Stream
    leakage -- and neither Stream may silently fail to make progress."""

    results = _run_concurrently({"stream-camera-a": 10, "stream-camera-b": 10}, tmp_path=tmp_path)

    assert results["stream-camera-a"]["candidates_created"] == 10
    assert results["stream-camera-b"]["candidates_created"] == 10
    # Concurrent wall-clock should not regress to "may as well have been
    # sequential" -- a generous bound (not a tight performance assertion,
    # per this milestone's own "measure, do not chase a number" instruction)
    # that would fail loudly if the two threads were secretly serializing
    # end-to-end rather than genuinely overlapping.
    sequential_upper_bound = results["stream-camera-a"]["elapsed_seconds"] + results["stream-camera-b"]["elapsed_seconds"]
    assert results["_overall_elapsed_seconds"] < sequential_upper_bound


def test_four_cameras_asymmetric_load_quiet_streams_are_not_starved_by_a_busy_one(tmp_path: Path) -> None:
    """4-camera topology, deliberately asymmetric (this milestone's own
    "Camera A busy / Camera B quiet / Camera C intermittent" shape,
    extended to 4 to also gesture at the "4-camera stress" topology):
    one busy Stream (40 encounters) running concurrently with three
    quieter Streams (3/5/8 encounters). The critical correctness property
    is zero cross-Stream contamination under real concurrent writes to one
    shared SQLite file; the critical fairness property is that the quiet
    Streams are never *blocked* by the busy one -- each must still finish
    within a bounded time, not stall indefinitely behind it."""

    workloads = {
        "stream-busy": 40,
        "stream-quiet-1": 3,
        "stream-quiet-2": 5,
        "stream-quiet-3": 8,
    }
    results = _run_concurrently(workloads, tmp_path=tmp_path)

    for stream_id, expected_count in workloads.items():
        assert results[stream_id]["candidates_created"] == expected_count, (
            f"{stream_id} created {results[stream_id]['candidates_created']} candidates, "
            f"expected exactly its own {expected_count} -- any deviation would mean cross-Stream "
            f"contamination or lost work under concurrent load."
        )

    # None of the quiet Streams may take materially longer than the busy
    # Stream itself -- if a quiet Stream were being starved behind the busy
    # one (e.g. blocked on a coarse lock the busy Stream holds for most of
    # its own runtime), its own elapsed time would balloon toward the busy
    # Stream's, not stay close to what running alone would cost.
    busy_elapsed = results["stream-busy"]["elapsed_seconds"]
    for stream_id in ("stream-quiet-1", "stream-quiet-2", "stream-quiet-3"):
        quiet_elapsed = results[stream_id]["elapsed_seconds"]
        assert quiet_elapsed < busy_elapsed, (
            f"{stream_id} (elapsed {quiet_elapsed:.3f}s) took as long as or longer than the busy "
            f"Stream (elapsed {busy_elapsed:.3f}s) despite doing far less work -- a possible "
            f"starvation signal worth a bounded fix, per this milestone's own \"measure, then fix "
            f"boundedly if a real fairness bug exists\" instruction."
        )
