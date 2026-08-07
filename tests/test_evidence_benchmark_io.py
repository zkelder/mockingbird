"""Safety tests for the Stage 6.13 evidence-benchmark filesystem I/O: safe
output-directory rejection, atomic report writes, native reviewed-evidence-
manifest loading, Stage 6.6 review-packet derivation wiring, replay-report
candidate/proposal reconstruction, and read-only media resolution. No real
camera, CUDA, or product database is touched; every fixture is hand-built
JSON/PNG bytes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image
import pytest

from mockingbird.observation.contracts import EvidenceCandidate, VisitProposal
from mockingbird.observation.evidence_benchmark import (
    EvidenceBenchmarkError,
    evaluate_evidence_benchmark,
)
from mockingbird.observation.evidence_benchmark_io import (
    load_replay_report_document,
    load_review_packet_manifest,
    load_reviewed_evidence_manifest,
    replay_candidates_and_proposals,
    resolve_media_mapping,
    write_evidence_benchmark_report,
    write_evidence_comparison_report,
)
from mockingbird.observation.temporal_annotation import AnnotationSet, BoxAnnotation, EvidenceUsefulness, FrameAnnotation, Provenance
from mockingbird.observation.temporal_capture import (
    CAPTURE_MANIFEST_SCHEMA_VERSION,
    STOP_DURATION_ELAPSED,
    TRIGGER_ANIMAL_ABOVE_OPERATING_POINT,
    CaptureBounds,
    CaptureSessionConfig,
    CaptureSessionManifest,
    RetainedFrameRecord,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _native_manifest_payload(**overrides) -> dict:
    payload = {
        "manifest_version": 1,
        "manifest_id": "fixture-manifest",
        "source_description": "unit-test",
        "candidates": [{
            "candidate_id": "c1", "session_id": "session-1", "role": "tracked_best",
            "track_generation_id": "track-1", "width": 320, "height": 240,
            "subject_geometry": [0.2, 0.2, 0.6, 0.7], "useful_identification": True,
        }],
        "appearances": [],
    }
    payload.update(overrides)
    return payload


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# Native reviewed-evidence-manifest loading
# --------------------------------------------------------------------------


def test_load_reviewed_evidence_manifest_round_trips(tmp_path: Path) -> None:
    path = _write_json(tmp_path / "manifest.json", _native_manifest_payload())
    manifest = load_reviewed_evidence_manifest(path)
    assert manifest.manifest_id == "fixture-manifest"
    assert manifest.candidates[0].candidate_id == "c1"
    assert manifest.candidates[0].useful_identification is True


def test_load_reviewed_evidence_manifest_rejects_symlink(tmp_path: Path) -> None:
    real = _write_json(tmp_path / "real.json", _native_manifest_payload())
    link = tmp_path / "link.json"
    link.symlink_to(real)
    with pytest.raises(EvidenceBenchmarkError, match="unsafe_manifest_path"):
        load_reviewed_evidence_manifest(link)


def test_load_reviewed_evidence_manifest_rejects_non_json_suffix(tmp_path: Path) -> None:
    path = tmp_path / "manifest.txt"
    path.write_text(json.dumps(_native_manifest_payload()), encoding="utf-8")
    with pytest.raises(EvidenceBenchmarkError, match="unsafe_manifest_path"):
        load_reviewed_evidence_manifest(path)


def test_load_reviewed_evidence_manifest_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not valid", encoding="utf-8")
    with pytest.raises(EvidenceBenchmarkError, match="invalid_manifest_json"):
        load_reviewed_evidence_manifest(path)


def test_load_reviewed_evidence_manifest_rejects_invalid_subject_visible(tmp_path: Path) -> None:
    payload = _native_manifest_payload()
    payload["candidates"][0]["reviewed_subject_visible"] = "definitely"
    path = _write_json(tmp_path / "manifest.json", payload)
    with pytest.raises(EvidenceBenchmarkError):
        load_reviewed_evidence_manifest(path)


# --------------------------------------------------------------------------
# Existing replay/evidence results
# --------------------------------------------------------------------------


def _replay_report_payload() -> dict:
    return {
        "semantic_fingerprint": "report-fp-1",
        "provider": {"provider_id": "frame-driven-onnx-cuda", "version": "v1"},
        "evidence_candidates": [{
            "media_asset_id": "replay:0", "stream_id": "stream-1", "role": "tracked_best",
            "frame_id": "frame-0", "source_offset_ms": 100, "width": 320, "height": 240,
            "subject_geometry": [0.2, 0.2, 0.6, 0.7], "track_generation_id": "track-1",
            "quality_facts": [["track_supported", True], ["temporal_alignment", "aligned"]],
        }],
        "proposals": [{
            "proposal_key": "proposal-1", "source_id": "shadow", "stream_id": "stream-1",
            "evidence_media_asset_ids": ["replay:0"], "reason": "confirmed_visit",
            "track_generation_id": "track-1",
        }],
    }


def test_load_replay_report_document_round_trips(tmp_path: Path) -> None:
    path = _write_json(tmp_path / "replay-report.json", _replay_report_payload())
    document = load_replay_report_document(path)
    assert document["semantic_fingerprint"] == "report-fp-1"


def test_replay_candidates_and_proposals_reconstructs_real_dataclasses() -> None:
    document = _replay_report_payload()
    candidates, proposals, fingerprint, provider = replay_candidates_and_proposals(document)
    assert candidates == (EvidenceCandidate(
        "replay:0", "stream-1", "tracked_best", None, "frame-0", 100, 320, 240,
        (0.2, 0.2, 0.6, 0.7), "track-1", quality_facts=(("track_supported", True), ("temporal_alignment", "aligned")),
    ),)
    assert proposals == (VisitProposal(
        "proposal-1", "shadow", "stream-1", ("replay:0",), "confirmed_visit", track_generation_id="track-1",
    ),)
    assert fingerprint == "report-fp-1"
    assert provider == {"provider_id": "frame-driven-onnx-cuda", "version": "v1"}
    # And these reconstructed dataclasses feed straight back into the real
    # benchmark evaluation, which calls the existing scorer on them.
    report = evaluate_evidence_benchmark(
        _minimal_manifest(), replay_candidates=candidates, replay_proposals=proposals,
    )
    assert report.metrics["episodes_evaluated"]["value"] == 1


def _minimal_manifest():
    from mockingbird.observation.evidence_benchmark import ReviewedEvidenceManifest
    return ReviewedEvidenceManifest(1, "m", "s", ())


# --------------------------------------------------------------------------
# Stage 6.6 review-packet derivation wiring (mechanical, no hand-copying)
# --------------------------------------------------------------------------


def _build_review_directory(tmp_path: Path) -> Path:
    review = tmp_path / "review"
    review.mkdir()
    config = CaptureSessionConfig(
        schema_version=CAPTURE_MANIFEST_SCHEMA_VERSION, capture_version="temporal-capture-session-v1",
        stream_id="s1", transport_key="camera-node-http-multipart-jpeg", provider_key="frame-driven-onnx-cuda",
        analysis_width=1000, analysis_height=1000, nominal_fps=2.0, review_score_threshold=0.02,
        shadow_operating_point=0.5, review_floor=0.1, evidence_profile_id="profile-1", bounds=CaptureBounds(),
    )
    record = RetainedFrameRecord(
        frame_id="frame-a", sequence=0, source_offset_ms=0, provider_generation="gen-1",
        content_hash="h" * 64, byte_size=1000, trigger_reasons=(TRIGGER_ANIMAL_ABOVE_OPERATING_POINT,),
        detector_observation_count=1, animal_detection_count=1, max_animal_score=0.5,
        active_track_count=1, motion_proposal_count=0, track_generation_ids=("track-1",),
        session_offset_ms=0, connection_segment_id="segment-1",
    )
    manifest = CaptureSessionManifest(
        config=config, session_id="session-1", node_session_id="node-session-1",
        start_host_time_iso="2026-08-05T20:00:00+00:00", end_host_time_iso="2026-08-05T20:01:00+00:00",
        start_source_offset_ms=0, end_source_offset_ms=1000, first_sequence=0, last_sequence=0,
        sequence_gap_count=0, dropped_frame_count=0, coalesced_frame_count=0, stale_frame_count=0,
        generation_reset_count=0, provider_generations=("gen-1",), model_fingerprint="model-fp",
        tracker_proposal_config_fingerprint="cfg-fp", frames=(record,), operator_markers=(),
        stop_condition=STOP_DURATION_ELAPSED,
    )
    document = manifest.to_semantic_dict()
    document["semantic_fingerprint"] = manifest.fingerprint
    (review / "capture-session-manifest.json").write_text(json.dumps(document), encoding="utf-8")

    annotations = AnnotationSet(
        1, "session-1", manifest.fingerprint,
        (FrameAnnotation(
            "frame-a", whole_frame_truth="yes",
            boxes=(BoxAnnotation((0.1, 0.1, 0.3, 0.3)),),
            evidence_usefulness=EvidenceUsefulness(True, True, True, False),
            provenance=Provenance("alice", "2026-08-06T00:00:00+00:00", "session-1", "detector_crop"),
        ),),
    )
    from dataclasses import asdict
    annotation_document = {
        "schema_version": annotations.schema_version,
        "capture_session_id": annotations.capture_session_id,
        "capture_manifest_fingerprint": annotations.capture_manifest_fingerprint,
        "frames": [asdict(item) for item in annotations.frames],
        "appearances": [asdict(item) for item in annotations.appearances],
    }
    (review / "annotation.json").write_text(json.dumps(annotation_document), encoding="utf-8")

    frames_directory = review / "frames"
    frames_directory.mkdir()
    Image.new("RGB", (320, 240), "white").save(frames_directory / "frame-a.jpg")
    return review


def test_load_review_packet_manifest_derives_candidates_without_hand_copying(tmp_path: Path) -> None:
    review = _build_review_directory(tmp_path)
    manifest = load_review_packet_manifest(review)
    assert len(manifest.candidates) == 1
    assert manifest.candidates[0].candidate_id == "frame-a"
    assert manifest.candidates[0].useful_identification is True
    assert manifest.candidates[0].image_path == "frames/frame-a.jpg"


def test_load_review_packet_manifest_rejects_a_directory_missing_the_capture_manifest(tmp_path: Path) -> None:
    empty = tmp_path / "empty-review"
    empty.mkdir()
    with pytest.raises(EvidenceBenchmarkError, match="invalid_review_packet"):
        load_review_packet_manifest(empty)


def test_review_packet_manifest_resolves_media_and_scores_end_to_end(tmp_path: Path) -> None:
    review = _build_review_directory(tmp_path)
    manifest = load_review_packet_manifest(review)
    media = resolve_media_mapping(review, manifest)
    assert "frame-a" in media
    report = evaluate_evidence_benchmark(manifest, media=media)
    assert report.metrics["episodes_evaluated"]["value"] == 1
    (episode,) = report.episodes
    assert episode.selection.identification_candidate_id == "frame-a"


# --------------------------------------------------------------------------
# Media resolution safety -- read-only, never mutates the source packet.
# --------------------------------------------------------------------------


def test_resolve_media_mapping_rejects_path_traversal(tmp_path: Path) -> None:
    review = _build_review_directory(tmp_path)
    manifest = load_review_packet_manifest(review)
    escaping = manifest.candidates[0].__class__(
        candidate_id="escape", session_id="session-1", role="tracked_best",
        image_path="../outside.jpg",
    )
    from mockingbird.observation.evidence_benchmark import ReviewedEvidenceManifest
    bad_manifest = ReviewedEvidenceManifest(1, "m", "s", (escaping,))
    with pytest.raises(EvidenceBenchmarkError, match="unsafe_frame_path"):
        resolve_media_mapping(review, bad_manifest)


def test_resolve_media_mapping_skips_a_missing_image_without_raising(tmp_path: Path) -> None:
    review = _build_review_directory(tmp_path)
    manifest = load_review_packet_manifest(review)
    from dataclasses import replace
    missing = replace(manifest.candidates[0], candidate_id="also-missing", image_path="frames/does-not-exist.jpg")
    from mockingbird.observation.evidence_benchmark import ReviewedEvidenceManifest
    combined = ReviewedEvidenceManifest(1, "m", "s", manifest.candidates + (missing,))
    media = resolve_media_mapping(review, combined)
    assert "also-missing" not in media
    assert "frame-a" in media


def test_input_review_media_is_never_modified(tmp_path: Path) -> None:
    review = _build_review_directory(tmp_path)
    before = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(review.rglob("*")) if path.is_file()
    }
    manifest = load_review_packet_manifest(review)
    media = resolve_media_mapping(review, manifest)
    evaluate_evidence_benchmark(manifest, media=media)
    after = {
        path: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(review.rglob("*")) if path.is_file()
    }
    assert before == after


# --------------------------------------------------------------------------
# Safe output-directory rejection
# --------------------------------------------------------------------------


def test_write_report_rejects_the_repository_root() -> None:
    with pytest.raises(EvidenceBenchmarkError, match="unsafe_output_path"):
        write_evidence_benchmark_report(_REPO_ROOT, {"semantic_fingerprint": "x"}, execution={})


def test_write_report_rejects_a_source_directory() -> None:
    with pytest.raises(EvidenceBenchmarkError, match="unsafe_output_path"):
        write_evidence_benchmark_report(_REPO_ROOT / "src" / "evidence-benchmark-out", {"semantic_fingerprint": "x"}, execution={})


def test_write_report_rejects_a_docs_directory() -> None:
    with pytest.raises(EvidenceBenchmarkError, match="unsafe_output_path"):
        write_evidence_benchmark_report(_REPO_ROOT / "docs" / "evidence-benchmark-out", {"semantic_fingerprint": "x"}, execution={})


def test_write_report_rejects_a_tests_directory() -> None:
    with pytest.raises(EvidenceBenchmarkError, match="unsafe_output_path"):
        write_evidence_benchmark_report(_REPO_ROOT / "tests" / "evidence-benchmark-out", {"semantic_fingerprint": "x"}, execution={})


def test_write_report_rejects_nonempty_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "existing.txt").write_text("x")
    with pytest.raises(EvidenceBenchmarkError, match="nonempty_output_directory"):
        write_evidence_benchmark_report(output, {"semantic_fingerprint": "x"}, execution={})


def test_write_report_rejects_a_symlinked_output_directory(tmp_path: Path) -> None:
    real = tmp_path / "real-output"
    real.mkdir()
    link = tmp_path / "linked-output"
    link.symlink_to(real)
    with pytest.raises(EvidenceBenchmarkError, match="unsafe_output_path"):
        write_evidence_benchmark_report(link, {"semantic_fingerprint": "x"}, execution={})


def test_write_report_is_atomic_and_readable(tmp_path: Path) -> None:
    output = tmp_path / "output"
    semantic = {"schema_version": 1, "semantic_fingerprint": "abc"}
    path = write_evidence_benchmark_report(output, semantic, execution={"duration_ms": 12})
    payload = json.loads(path.read_text())
    assert payload["semantic_fingerprint"] == "abc"
    assert payload["execution"] == {"duration_ms": 12}
    assert not list(output.glob(".*.tmp"))
    assert path.name == "evidence-benchmark-report.json"


def test_comparison_report_writer_uses_its_own_filename(tmp_path: Path) -> None:
    output = tmp_path / "output"
    path = write_evidence_comparison_report(output, {"semantic_fingerprint": "abc"}, execution={})
    assert path.name == "evidence-comparison-report.json"


# --------------------------------------------------------------------------
# Structural boundaries
# --------------------------------------------------------------------------


def test_evidence_benchmark_io_has_no_product_repository_dependency() -> None:
    import ast
    tree = ast.parse((_REPO_ROOT / "src" / "mockingbird" / "observation" / "evidence_benchmark_io.py").read_text(encoding="utf-8"))
    imported = {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    } | {
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    }
    forbidden = ("mockingbird.repositories", "mockingbird.api", "sqlalchemy")
    assert not any(module.startswith(prefix) for module in imported for prefix in forbidden)


def test_evidence_benchmark_io_never_opens_the_product_database() -> None:
    source = (_REPO_ROOT / "src" / "mockingbird" / "observation" / "evidence_benchmark_io.py").read_text(encoding="utf-8")
    forbidden = ("mockingbird.db", "ReviewLabel", "MotionEvidence", "StreamMonitoringPolicy", "LiveCameraSession")
    assert not any(token in source for token in forbidden)
