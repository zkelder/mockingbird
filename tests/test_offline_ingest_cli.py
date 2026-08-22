"""Tests for `python -m mockingbird analyze-recorded-media`
(`mockingbird.observation.offline_ingest_cli`). The real analysis happy
path is already exercised, with an injected fake detector, in
`tests/test_offline_ingest.py`; this file covers argument parsing,
rendering, and one real, non-monkeypatched end-to-end wiring proof --
mirroring `tests/test_doctor_cli.py::test_run_end_to_end_against_a_real_
isolated_installation`'s isolation approach, using the explicit
`MOCKINGBIRD_DB_URL`/`MOCKINGBIRD_MEDIA_ROOT` env vars `ProductRepository()`'s
own default-resolution path already respects (never the real default
database -- see `mockingbird.storage.database`'s pytest-only safety guard).
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mockingbird.observation import offline_ingest_cli
from mockingbird.observation.offline_ingest import DEFAULT_PIPELINE_VERSION, DEFAULT_SAMPLE_FPS, OfflineIngestResult
from mockingbird.repository.product_repository import MediaAssetModel, ProductRepository


def test_build_argument_parser_defaults() -> None:
    parser = offline_ingest_cli.build_argument_parser()
    args = parser.parse_args(["media-video-1"])
    assert args.media_asset_id == "media-video-1"
    assert args.sample_fps is None
    assert args.max_frames is None
    assert args.pipeline_version is None
    assert args.force_reprocess is False
    assert args.json is False


def test_build_argument_parser_accepts_all_overrides() -> None:
    parser = offline_ingest_cli.build_argument_parser()
    args = parser.parse_args([
        "media-video-1", "--sample-fps", "1.5", "--max-frames", "100",
        "--pipeline-version", "test-pipeline", "--force-reprocess", "--json",
    ])
    assert args.sample_fps == 1.5
    assert args.max_frames == 100
    assert args.pipeline_version == "test-pipeline"
    assert args.force_reprocess is True
    assert args.json is True


def test_render_human_includes_the_bounded_progress_facts() -> None:
    result = OfflineIngestResult(
        run_id="analysis-run-001", status="completed", media_asset_id="media-video-1",
        stream_id="stream-backyard-feeder", pipeline_version=DEFAULT_PIPELINE_VERSION,
        sample_fps=DEFAULT_SAMPLE_FPS, frames_considered=8, frames_analyzed=8, events_created=1,
        visits_created=1, visit_ids=("visit-1",), event_ids=("event-1",), source_duration_seconds=4.0,
        capture_time_known=True,
    )
    text = offline_ingest_cli.render_human(result)
    assert "status: completed" in text
    assert "frames_considered: 8" in text
    assert "visits_created: 1" in text
    assert "source_duration_seconds: 4.0" in text
    assert "capture_time_known: True" in text


def test_render_human_surfaces_a_failure_code() -> None:
    result = OfflineIngestResult(
        run_id="analysis-run-002", status="failed", media_asset_id="media-video-1",
        stream_id="stream-backyard-feeder", pipeline_version=DEFAULT_PIPELINE_VERSION,
        sample_fps=DEFAULT_SAMPLE_FPS, error_code="media_file_invalid",
        error_message="This recorded file could not be read as a video.",
    )
    text = offline_ingest_cli.render_human(result)
    assert "error: media_file_invalid" in text


def test_run_reports_a_clean_error_for_an_unknown_media_asset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    data_dir = tmp_path / "data"
    media_root = data_dir / "media" / "imports"
    media_root.mkdir(parents=True)
    repository = ProductRepository(db_url=f"sqlite:///{data_dir / 'mockingbird.sqlite3'}", media_root=media_root)
    repository.close()
    monkeypatch.setenv("MOCKINGBIRD_DB_URL", f"sqlite:///{data_dir / 'mockingbird.sqlite3'}")
    monkeypatch.setenv("MOCKINGBIRD_MEDIA_ROOT", str(media_root))

    exit_code = offline_ingest_cli.run(["media-does-not-exist"])
    assert exit_code == 1
    assert "media_asset_not_found" in capsys.readouterr().out


def test_run_end_to_end_against_a_real_isolated_installation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """One real, non-monkeypatched pass through the full CLI -> orchestrator
    -> real SQLite database pipeline, proving the pieces are actually wired
    together (not just each mocked in isolation). No real CUDA/model bundle
    is configured, so this reaches the same honest `engine_unavailable`
    failure `tests/test_recorded_media_analysis_api.py` proves at the API
    layer -- the point here is confirming the CLI reaches that same real
    code path, not re-proving the happy path."""

    data_dir = tmp_path / "data"
    media_root = data_dir / "media" / "imports"
    media_root.mkdir(parents=True)
    repository = ProductRepository(db_url=f"sqlite:///{data_dir / 'mockingbird.sqlite3'}", media_root=media_root)
    video_path = tmp_path / "clip.mp4"
    if shutil.which("ffmpeg") is not None:
        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                "-i", "color=c=blue:s=64x64:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video_path),
            ],
            check=True, timeout=30, capture_output=True,
        )
    else:
        video_path.write_bytes(b"placeholder")
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id="media-cli-video", source_id="source-backyard-demo", stream_id="stream-backyard-feeder",
                    filename=video_path.name, content_type="video/mp4", media_type="video",
                    local_path=str(video_path), original_filename=video_path.name,
                    file_size_bytes=video_path.stat().st_size, created_at=datetime.now(UTC),
                )
            )
    repository.close()
    monkeypatch.setenv("MOCKINGBIRD_DB_URL", f"sqlite:///{data_dir / 'mockingbird.sqlite3'}")
    monkeypatch.setenv("MOCKINGBIRD_MEDIA_ROOT", str(media_root))

    exit_code = offline_ingest_cli.run(["media-cli-video", "--json"])
    assert exit_code == 1
    output = capsys.readouterr().out
    assert '"status": "failed"' in output
