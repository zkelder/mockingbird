"""Hardware-free tests for Multi-Scene Backyard Domain Acquisition +
Holdout v2 v1: feeder-tranche reclassification, scene identity provenance,
Holdout v2 scene/session isolation, and scene-diversity accounting.
Synthetic fixtures only -- no dependency on the real 700-frame Stage-3
tranche or real local capture data (see `scripts/select_wildlife_feeder_
correction_subset.py`/`scripts/report_wildlife_scene_diversity.py`, both
already run once against the real local corpus; see the milestone report).
"""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from mockingbird.observation.temporal_annotation import AnnotationSet, BoxAnnotation, FrameAnnotation, Provenance
from mockingbird.training.wildlife import (
    CorpusExample,
    canonical_fingerprint,
    contamination_report,
    dhash64,
    phash64,
    sha256_file,
)
from mockingbird.training.wildlife_stage3_tranche import (
    LANE_EDGE_CONDITION,
    LANE_HARD_NEGATIVE_CONFUSOR,
    LANE_SMALL_FAR_POSITIVE,
    TRANCHE_ID,
)
from mockingbird.training.wildlife_multiscene import (
    CAPTURE_PURPOSE_HOLDOUT_V2_CANDIDATE,
    CAPTURE_PURPOSE_TRAINING_CANDIDATE,
    LEGACY_FEEDER_SCENE_ID,
    SceneFrameProvenance,
    WildlifeMultiSceneError,
    annotation_counts_for_scene,
    assert_no_scene_purpose_conflict,
    assert_scene_session_holdout_isolation,
    build_scene_review_tranche,
    conflicting_purpose_scene_ids,
    feeder_subset_session_concentration,
    holdout_v2_records,
    holdout_v2_scene_ids,
    scan_scene_manifests,
    scene_capture_purposes,
    scene_diversity_report,
    scene_frame_provenance_from_manifest,
    select_feeder_correction_subset,
    training_scene_ids,
    validate_scene_id,
)


# --------------------------------------------------------------------------
# Fixture helpers (mirror tests/test_wildlife_stage3_tranche.py exactly)
# --------------------------------------------------------------------------


def _jpeg(path: Path, color: tuple[int, int, int], *, size: tuple[int, int] = (64, 48)) -> str:
    width, height = size
    x_indices = np.arange(width, dtype=np.int32)[None, :]
    y_indices = np.arange(height, dtype=np.int32)[:, None]
    array = np.zeros((height, width, 3), dtype=np.uint8)
    for channel in range(3):
        array[:, :, channel] = (color[channel] + x_indices * (4 + channel) + y_indices * (5 + channel) * 2) % 256
    image = Image.fromarray(array)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    data = buffer.getvalue()
    path.write_bytes(data)
    from hashlib import sha256
    return sha256(data).hexdigest()


def _tranche_row(tmp_path: Path, name: str, *, index: int, color: tuple[int, int, int], lane: str) -> dict[str, object]:
    image_path = tmp_path / f"{name}.jpg"
    content_hash = _jpeg(image_path, color)
    return {
        "frame_id": content_hash,
        "content_hash": content_hash,
        "image": str(image_path),
        "capture_manifest": str(tmp_path / f"session-{index}" / "capture-session-manifest.json"),
        "capture_session_id": str(tmp_path / f"session-{index}" / "capture-out"),
        "source_capture_timestamp": f"2026-08-07T21:{index % 60:02d}:00+00:00",
        "high_resolution": False,
        "detector_observation_count": 0,
        "animal_detection_count": 0,
        "max_animal_score": None,
        "motion_proposal_count": 0,
        "trigger_reasons": [],
        "review_status": "unreviewed",
        "training_eligible": False,
        "stage3_target_lane": lane,
        "priority_tier": "small_far_opportunity",
        "split_candidate": "local_train_candidate",
        "selection_tie_break": content_hash,
    }


def _tranche_payload(frames: list[dict[str, object]]) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "tranche_id": TRANCHE_ID,
        "source_queue_id": "mockingbird-local-wildlife-correction-v0.2",
        "source_queue_fingerprint": "a" * 64,
        "seed": 260812,
        "lane_targets": {LANE_SMALL_FAR_POSITIVE: 325, LANE_HARD_NEGATIVE_CONFUSOR: 275, LANE_EDGE_CONDITION: 100},
        "frames": frames,
    }
    payload["semantic_fingerprint"] = canonical_fingerprint(payload)
    return payload


def _small_tranche(tmp_path: Path, *, per_lane: int = 5) -> dict[str, object]:
    frames: list[dict[str, object]] = []
    index = 0
    for lane, base in ((LANE_SMALL_FAR_POSITIVE, 10), (LANE_HARD_NEGATIVE_CONFUSOR, 90), (LANE_EDGE_CONDITION, 170)):
        for offset in range(per_lane):
            frames.append(_tranche_row(
                tmp_path, f"{lane}-{offset}", index=index, color=(base + offset * 7, offset * 11, offset * 13), lane=lane,
            ))
            index += 1
    return _tranche_payload(frames)


_SMALL_TARGETS = {LANE_SMALL_FAR_POSITIVE: 3, LANE_HARD_NEGATIVE_CONFUSOR: 2, LANE_EDGE_CONDITION: 2}


# --------------------------------------------------------------------------
# 1. Stable scene identity
# --------------------------------------------------------------------------


def test_validate_scene_id_accepts_a_stable_lowercase_hyphenated_name() -> None:
    assert validate_scene_id("lawn-north") == "lawn-north"


@pytest.mark.parametrize("value", ["", "Lawn North", "lawn_north", "lawn north", "-lawn", "lawn-", "UPPER"])
def test_validate_scene_id_rejects_unstable_or_malformed_names(value: str) -> None:
    with pytest.raises(WildlifeMultiSceneError):
        validate_scene_id(value)


def test_scene_frame_provenance_rejects_an_invalid_scene_id() -> None:
    with pytest.raises(WildlifeMultiSceneError):
        SceneFrameProvenance(
            scene_id="Not Valid", capture_session_id="s1", source_camera="stream-1", capture_time=None,
            frame_id="f1", content_hash="a" * 64, width=100, height=100,
            capture_purpose=CAPTURE_PURPOSE_TRAINING_CANDIDATE, high_resolution=False, capture_manifest="m.json",
        )


# --------------------------------------------------------------------------
# 4. Exact-frame retention / scene provenance scanning
# --------------------------------------------------------------------------


def _synthetic_manifest_frame(frame_id: str, *, scene_id: str, content_hash: str, holdout: bool = False,
                               timestamp: str = "2026-08-12T10:00:00+00:00", width: int | None = None,
                               height: int | None = None) -> dict[str, object]:
    row: dict[str, object] = {
        "frame_id": frame_id, "content_hash": content_hash, "scene_id": scene_id,
        "holdout_v2_candidate": holdout, "source_capture_timestamp": timestamp,
        "host_received_at": timestamp, "high_resolution": False,
    }
    if width is not None and height is not None:
        row["exact_analysis"] = {"detector_input": {"width": width, "height": height}}
    return row


def _write_manifest(path: Path, *, session_id: str, frames: list[dict[str, object]],
                     stream_id: str = "stream-1", analysis_width: int = 1920, analysis_height: int = 1080) -> None:
    payload = {
        "session_id": session_id,
        "config": {"stream_id": stream_id, "analysis_width": analysis_width, "analysis_height": analysis_height},
        "frames": frames,
    }
    path.write_text(json.dumps(payload))


def test_scene_frame_provenance_reads_exact_frame_sha_and_dimensions(tmp_path: Path) -> None:
    manifest_path = tmp_path / "capture-session-manifest.json"
    _write_manifest(manifest_path, session_id="temporal-capture-20260812T100000Z", frames=[
        _synthetic_manifest_frame("f1", scene_id="lawn-north", content_hash="b" * 64, width=800, height=600),
    ])
    records = scene_frame_provenance_from_manifest(manifest_path)
    assert len(records) == 1
    record = records[0]
    assert record.scene_id == "lawn-north"
    assert record.capture_session_id == "temporal-capture-20260812T100000Z"
    assert record.content_hash == "b" * 64  # exact frame SHA, unaltered
    assert (record.width, record.height) == (800, 600)  # exact dimensions
    assert record.capture_purpose == CAPTURE_PURPOSE_TRAINING_CANDIDATE
    assert record.review_status == "unreviewed"


def test_scene_frame_provenance_falls_back_to_session_analysis_dimensions(tmp_path: Path) -> None:
    """A frame with no `--retain-exact-analysis` envelope reports the
    session's own analysis dimensions -- an honest fallback, not a
    fabricated per-frame value."""

    manifest_path = tmp_path / "capture-session-manifest.json"
    _write_manifest(
        manifest_path, session_id="s1", analysis_width=1280, analysis_height=720,
        frames=[_synthetic_manifest_frame("f1", scene_id="deck-01", content_hash="c" * 64)],
    )
    records = scene_frame_provenance_from_manifest(manifest_path)
    assert (records[0].width, records[0].height) == (1280, 720)


def test_scene_frame_provenance_skips_frames_without_an_explicit_scene_id(tmp_path: Path) -> None:
    manifest_path = tmp_path / "capture-session-manifest.json"
    _write_manifest(manifest_path, session_id="s1", frames=[
        _synthetic_manifest_frame("f1", scene_id="", content_hash="d" * 64),  # legacy/pre-scene-id frame
        _synthetic_manifest_frame("f2", scene_id="deck-01", content_hash="e" * 64),
    ])
    records = scene_frame_provenance_from_manifest(manifest_path)
    assert [record.frame_id for record in records] == ["f2"]


def test_scan_scene_manifests_reads_each_distinct_manifest_once(tmp_path: Path) -> None:
    first = tmp_path / "a" / "capture-session-manifest.json"
    first.parent.mkdir(parents=True)
    _write_manifest(first, session_id="s1", frames=[_synthetic_manifest_frame("f1", scene_id="lawn-north", content_hash="a" * 64)])
    second = tmp_path / "b" / "capture-session-manifest.json"
    second.parent.mkdir(parents=True)
    _write_manifest(second, session_id="s2", frames=[_synthetic_manifest_frame("f2", scene_id="woods-01", content_hash="b" * 64)])
    records = scan_scene_manifests([first, second, first])  # duplicate path, deduplicated internally
    assert {record.scene_id for record in records} == {"lawn-north", "woods-01"}
    assert len(records) == 2


# --------------------------------------------------------------------------
# 7. Review provenance
# --------------------------------------------------------------------------


def test_scene_frame_provenance_joins_positive_review_provenance(tmp_path: Path) -> None:
    manifest_path = tmp_path / "capture-session-manifest.json"
    _write_manifest(manifest_path, session_id="s1", frames=[_synthetic_manifest_frame("f1", scene_id="deck-01", content_hash="f" * 64)])
    annotations = AnnotationSet(
        schema_version=1, capture_session_id="s1", capture_manifest_fingerprint="fp",
        frames=(FrameAnnotation(
            frame_id="f1", whole_frame_truth="yes", boxes=(BoxAnnotation(box=(0.1, 0.1, 0.2, 0.2)),),
            provenance=Provenance(
                reviewer="zkelder", reviewed_at_iso="2026-08-12T10:05:00+00:00",
                source_capture_session="s1", truth_source="full_frame_inspection",
            ),
        ),),
    )
    records = scene_frame_provenance_from_manifest(manifest_path, annotations=annotations)
    assert records[0].review_status == "reviewed_positive"
    assert records[0].reviewer == "zkelder"
    assert records[0].reviewed_at == "2026-08-12T10:05:00+00:00"


def test_scene_frame_provenance_unreviewed_frame_carries_no_reviewer() -> None:
    status = SceneFrameProvenance(
        scene_id="deck-01", capture_session_id="s1", source_camera="stream-1", capture_time=None,
        frame_id="f1", content_hash="a" * 64, width=100, height=100,
        capture_purpose=CAPTURE_PURPOSE_TRAINING_CANDIDATE, high_resolution=False, capture_manifest="m.json",
    )
    assert status.review_status == "unreviewed"
    assert status.reviewer is None
    assert status.reviewed_at is None


def test_annotation_counts_for_scene_computes_size_buckets_from_real_dimensions() -> None:
    annotations = AnnotationSet(
        schema_version=1, capture_session_id="s1", capture_manifest_fingerprint="fp",
        frames=(
            FrameAnnotation(
                frame_id="f1", whole_frame_truth="yes",
                # A tiny normalized box against a large source frame -> very_small bucket.
                boxes=(BoxAnnotation(box=(0.0, 0.0, 0.01, 0.01)),),
            ),
            FrameAnnotation(frame_id="f2", whole_frame_truth="no"),
            FrameAnnotation(frame_id="f3", whole_frame_truth="ambiguous"),
        ),
    )
    counts = annotation_counts_for_scene(annotations, {"f1": (2000, 2000)})
    assert counts["reviewed_positive"] == 1
    assert counts["reviewed_negative"] == 1
    assert counts["ambiguous"] == 1
    assert counts["animal_boxes"] == 1
    assert counts["size_buckets"] == {"very_small": 1}


# --------------------------------------------------------------------------
# 6. Feeder-tranche reclassification / determinism / concentration
# --------------------------------------------------------------------------


def test_select_feeder_correction_subset_hits_targets(tmp_path: Path) -> None:
    tranche = _small_tranche(tmp_path)
    result = select_feeder_correction_subset(tranche, targets=_SMALL_TARGETS)
    assert result["selected_count"] == sum(_SMALL_TARGETS.values())
    for lane, target in _SMALL_TARGETS.items():
        assert result["lanes"][lane]["dedup"]["selected"] == target
    assert result["scene_id"] == LEGACY_FEEDER_SCENE_ID
    # No human truth created: every selected row keeps the source tranche's
    # own unreviewed/training-ineligible state, byte for byte.
    for row in result["frames"]:
        assert row["review_status"] == "unreviewed"
        assert row["training_eligible"] is False
        assert row["feeder_subset_scene_id"] == LEGACY_FEEDER_SCENE_ID


def test_select_feeder_correction_subset_is_deterministic(tmp_path: Path) -> None:
    tranche = _small_tranche(tmp_path)
    first = select_feeder_correction_subset(tranche, targets=_SMALL_TARGETS)
    second = select_feeder_correction_subset(tranche, targets=_SMALL_TARGETS)
    assert first["semantic_fingerprint"] == second["semantic_fingerprint"]
    assert [row["frame_id"] for row in first["frames"]] == [row["frame_id"] for row in second["frames"]]


def test_select_feeder_correction_subset_rejects_wrong_source_tranche(tmp_path: Path) -> None:
    tranche = _small_tranche(tmp_path)
    tranche["tranche_id"] = "not-the-real-tranche"
    with pytest.raises(WildlifeMultiSceneError):
        select_feeder_correction_subset(tranche, targets=_SMALL_TARGETS)


def test_select_feeder_correction_subset_rejects_a_tampered_fingerprint(tmp_path: Path) -> None:
    tranche = _small_tranche(tmp_path)
    tranche["frames"][0]["max_animal_score"] = 0.999  # mutate after fingerprinting
    with pytest.raises(WildlifeMultiSceneError):
        select_feeder_correction_subset(tranche, targets=_SMALL_TARGETS)


def test_select_feeder_correction_subset_rejects_an_already_reviewed_row(tmp_path: Path) -> None:
    tranche = _small_tranche(tmp_path)
    tranche["frames"][0]["review_status"] = "reviewed"
    tranche["semantic_fingerprint"] = canonical_fingerprint(
        {key: value for key, value in tranche.items() if key != "semantic_fingerprint"}
    )
    with pytest.raises(WildlifeMultiSceneError):
        select_feeder_correction_subset(tranche, targets=_SMALL_TARGETS)


def test_select_feeder_correction_subset_raises_when_lane_unavailable(tmp_path: Path) -> None:
    tranche = _small_tranche(tmp_path, per_lane=1)
    with pytest.raises(WildlifeMultiSceneError):
        select_feeder_correction_subset(tranche, targets=_SMALL_TARGETS)


def test_feeder_subset_session_concentration_reports_the_dominant_session(tmp_path: Path) -> None:
    tranche = _small_tranche(tmp_path)
    result = select_feeder_correction_subset(tranche, targets=_SMALL_TARGETS)
    concentration = feeder_subset_session_concentration(result)
    assert concentration["total"] == sum(_SMALL_TARGETS.values())
    assert 0.0 < concentration["most_concentrated_fraction"] <= 1.0
    assert concentration["most_concentrated_session"] in result["frames_per_session"]


# --------------------------------------------------------------------------
# 2/9. Train-vs-holdout scene isolation / holdout-v2 fail-closed behavior
# --------------------------------------------------------------------------


def test_scene_capture_purposes_groups_by_scene() -> None:
    records = (
        SceneFrameProvenance(
            scene_id="lawn-north", capture_session_id="s1", source_camera="stream-1", capture_time=None,
            frame_id="f1", content_hash="a" * 64, width=10, height=10,
            capture_purpose=CAPTURE_PURPOSE_TRAINING_CANDIDATE, high_resolution=False, capture_manifest="m1.json",
        ),
        SceneFrameProvenance(
            scene_id="woods-01", capture_session_id="s2", source_camera="stream-1", capture_time=None,
            frame_id="f2", content_hash="b" * 64, width=10, height=10,
            capture_purpose=CAPTURE_PURPOSE_HOLDOUT_V2_CANDIDATE, high_resolution=False, capture_manifest="m2.json",
        ),
    )
    purposes = scene_capture_purposes(records)
    assert holdout_v2_scene_ids(purposes) == frozenset({"woods-01"})
    assert training_scene_ids(purposes) == frozenset({"lawn-north"})
    assert conflicting_purpose_scene_ids(purposes) == frozenset()
    assert_no_scene_purpose_conflict(purposes)  # does not raise


def test_conflicting_scene_purpose_is_detected_and_fails_closed() -> None:
    records = (
        SceneFrameProvenance(
            scene_id="lawn-north", capture_session_id="s1", source_camera="stream-1", capture_time=None,
            frame_id="f1", content_hash="a" * 64, width=10, height=10,
            capture_purpose=CAPTURE_PURPOSE_TRAINING_CANDIDATE, high_resolution=False, capture_manifest="m1.json",
        ),
        SceneFrameProvenance(
            scene_id="lawn-north", capture_session_id="s2", source_camera="stream-1", capture_time=None,
            frame_id="f2", content_hash="b" * 64, width=10, height=10,
            capture_purpose=CAPTURE_PURPOSE_HOLDOUT_V2_CANDIDATE, high_resolution=False, capture_manifest="m2.json",
        ),
    )
    purposes = scene_capture_purposes(records)
    assert conflicting_purpose_scene_ids(purposes) == frozenset({"lawn-north"})
    with pytest.raises(WildlifeMultiSceneError):
        assert_no_scene_purpose_conflict(purposes)


def test_assert_scene_session_holdout_isolation_passes_disjoint_rows() -> None:
    rows = [{"scene_id": "lawn-north", "capture_session_id": "s1"}]
    assert_scene_session_holdout_isolation(rows, holdout_scene_ids=frozenset({"woods-01"}))  # does not raise


def test_assert_scene_session_holdout_isolation_fails_closed_on_scene_match() -> None:
    rows = [{"scene_id": "woods-01", "capture_session_id": "s1"}]
    with pytest.raises(WildlifeMultiSceneError):
        assert_scene_session_holdout_isolation(rows, holdout_scene_ids=frozenset({"woods-01"}))


def test_assert_scene_session_holdout_isolation_fails_closed_on_session_match_even_with_a_different_scene() -> None:
    """Defense in depth: a row whose own `scene_id` field is missing/wrong
    but whose `capture_session_id` matches a declared Holdout v2 session is
    still caught -- the isolation check does not trust one field alone."""

    rows = [{"scene_id": "unrelated-scene", "capture_session_id": "holdout-session-1"}]
    with pytest.raises(WildlifeMultiSceneError):
        assert_scene_session_holdout_isolation(rows, holdout_session_ids=frozenset({"holdout-session-1"}))


def test_assert_scene_session_holdout_isolation_ignores_rows_with_no_scene_or_session() -> None:
    rows = [{"frame_id": "f1"}]  # no scene_id/capture_session_id at all
    assert_scene_session_holdout_isolation(rows, holdout_scene_ids=frozenset({"woods-01"}))  # does not raise


# --------------------------------------------------------------------------
# 3/8. Derivative/sequence exclusion via HoldoutRecord/contamination_report reuse
# --------------------------------------------------------------------------


def test_holdout_v2_records_only_include_declared_holdout_scenes(tmp_path: Path) -> None:
    image = tmp_path / "f.jpg"
    content_hash = _jpeg(image, (1, 2, 3))
    training_row = {"frame_id": "f1", "content_hash": content_hash, "image": str(image), "scene_id": "lawn-north", "capture_session_id": "s1"}
    holdout_row = {"frame_id": "f2", "content_hash": content_hash, "image": str(image), "scene_id": "woods-01", "capture_session_id": "s2"}
    records = holdout_v2_records([training_row, holdout_row], holdout_scene_ids=frozenset({"woods-01"}))
    assert len(records) == 1
    assert records[0].frame_id == "f2"
    assert records[0].camera_id == "woods-01"
    assert records[0].sequence_id == "s2"
    assert records[0].source_identity == "mockingbird-local-scene:woods-01:f2"


def test_holdout_v2_records_catch_a_neighboring_sequence_frame_via_lineage(tmp_path: Path) -> None:
    """A local training-candidate example that shares a declared Holdout v2
    scene+session (a neighboring burst/sequence frame) is caught by
    `wildlife.contamination_report`'s existing site/camera/sequence lineage
    match -- even though its own pixels (and therefore hashes) are nothing
    alike, proving this is a real lineage check, not a hash coincidence."""

    holdout_image = tmp_path / "holdout.jpg"
    holdout_hash = _jpeg(holdout_image, (10, 10, 10))
    holdout_row = {
        "frame_id": holdout_hash, "content_hash": holdout_hash, "image": str(holdout_image),
        "scene_id": "woods-01", "capture_session_id": "session-abc",
    }
    holdout = holdout_v2_records([holdout_row], holdout_scene_ids=frozenset({"woods-01"}))

    neighbor_image = tmp_path / "neighbor.jpg"
    _jpeg(neighbor_image, (250, 5, 200))  # deliberately unrelated pixels
    example = CorpusExample(
        example_id="ex-1", source_id="local", source_version="v1", source_identity="local:neighbor",
        parent_identity=None, image="local://neighbor", source_url="local://neighbor",
        source_license="local-only", geography="unknown", width=64, height=48, split="train",
        site_id="mockingbird-local-site", camera_id="woods-01", sequence_id="session-abc",
        captured_at=None, truth_authority="human_reviewed_empty", boxes=(),
        sha256=sha256_file(neighbor_image), dhash64=dhash64(neighbor_image), phash64=phash64(neighbor_image),
        negative_kind="test_negative",
    )
    report = contamination_report([example], holdout)
    assert report["passed"] is False
    assert report["site_camera_sequence_matches"] == [{"example_id": "ex-1", "holdout_frame_id": holdout_hash}]
    # And the same two frames are honestly unrelated by content -- proving
    # this specific match came from lineage, not a hash coincidence.
    assert report["exact_sha256_matches"] == []
    assert report["near_duplicate_matches"] == []


# --------------------------------------------------------------------------
# 5. Scene concentration accounting
# --------------------------------------------------------------------------


def test_scene_diversity_report_flags_single_scene_concentration(tmp_path: Path) -> None:
    tranche = _small_tranche(tmp_path)
    feeder_subset = select_feeder_correction_subset(tranche, targets=_SMALL_TARGETS)
    report = scene_diversity_report(feeder_subset=feeder_subset)
    assert report["total_scenes"] == 1
    assert report["training_scenes"] == 1
    assert report["holdout_scenes"] == 0
    assert report["concentration"]["most_concentrated_scene"] == LEGACY_FEEDER_SCENE_ID
    assert report["concentration"]["most_concentrated_fraction"] == 1.0
    assert report["concentration"]["warning"] is True  # 100% > the 50% visibility threshold
    assert report["first_multiscene_target"]["met"] is False


def test_scene_diversity_report_counts_training_and_holdout_scenes_separately() -> None:
    records = (
        SceneFrameProvenance(
            scene_id="lawn-north", capture_session_id="s1", source_camera="stream-1", capture_time=None,
            frame_id="f1", content_hash="a" * 64, width=10, height=10,
            capture_purpose=CAPTURE_PURPOSE_TRAINING_CANDIDATE, high_resolution=False, capture_manifest="m1.json",
        ),
        SceneFrameProvenance(
            scene_id="deck-01", capture_session_id="s2", source_camera="stream-1", capture_time=None,
            frame_id="f2", content_hash="b" * 64, width=10, height=10,
            capture_purpose=CAPTURE_PURPOSE_TRAINING_CANDIDATE, high_resolution=False, capture_manifest="m2.json",
        ),
        SceneFrameProvenance(
            scene_id="woods-01", capture_session_id="s3", source_camera="stream-1", capture_time=None,
            frame_id="f3", content_hash="c" * 64, width=10, height=10,
            capture_purpose=CAPTURE_PURPOSE_HOLDOUT_V2_CANDIDATE, high_resolution=False, capture_manifest="m3.json",
        ),
    )
    report = scene_diversity_report(scene_records=records)
    assert report["total_scenes"] == 3
    assert report["training_scenes"] == 2
    assert report["holdout_scenes"] == 1
    # Concentration is computed only across *training* scenes -- a Holdout
    # v2 scene must never inflate or deflate the training-pool concentration
    # signal it is structurally excluded from.
    assert report["concentration"]["total_training_frames"] == 2
    assert report["concentration"]["most_concentrated_fraction"] == 0.5
    assert report["concentration"]["warning"] is False


def test_scene_diversity_report_surfaces_conflicting_purpose_scenes() -> None:
    records = (
        SceneFrameProvenance(
            scene_id="lawn-north", capture_session_id="s1", source_camera="stream-1", capture_time=None,
            frame_id="f1", content_hash="a" * 64, width=10, height=10,
            capture_purpose=CAPTURE_PURPOSE_TRAINING_CANDIDATE, high_resolution=False, capture_manifest="m1.json",
        ),
        SceneFrameProvenance(
            scene_id="lawn-north", capture_session_id="s2", source_camera="stream-1", capture_time=None,
            frame_id="f2", content_hash="b" * 64, width=10, height=10,
            capture_purpose=CAPTURE_PURPOSE_HOLDOUT_V2_CANDIDATE, high_resolution=False, capture_manifest="m2.json",
        ),
    )
    report = scene_diversity_report(scene_records=records)
    assert report["conflicting_purpose_scenes"] == ["lawn-north"]
    assert "conflicting" in report["first_multiscene_target"]["reasons"][-1]


def test_scene_diversity_report_meets_target_at_5_scenes_3_training_2_holdout() -> None:
    records = tuple(
        SceneFrameProvenance(
            scene_id=f"training-scene-{index}", capture_session_id=f"s{index}", source_camera="stream-1",
            capture_time=None, frame_id=f"f{index}", content_hash=f"{index:064x}", width=10, height=10,
            capture_purpose=CAPTURE_PURPOSE_TRAINING_CANDIDATE, high_resolution=False, capture_manifest=f"m{index}.json",
        )
        for index in range(3)
    ) + tuple(
        SceneFrameProvenance(
            scene_id=f"holdout-scene-{index}", capture_session_id=f"hs{index}", source_camera="stream-1",
            capture_time=None, frame_id=f"hf{index}", content_hash=f"{index + 100:064x}", width=10, height=10,
            capture_purpose=CAPTURE_PURPOSE_HOLDOUT_V2_CANDIDATE, high_resolution=False, capture_manifest=f"hm{index}.json",
        )
        for index in range(2)
    )
    report = scene_diversity_report(scene_records=records)
    assert report["total_scenes"] == 5
    assert report["training_scenes"] == 3
    assert report["holdout_scenes"] == 2
    assert report["first_multiscene_target"]["met"] is True
    assert report["first_multiscene_target"]["reasons"] == []


# --------------------------------------------------------------------------
# 7 (cont'd). Review-by-scene/session packet building, reusing the existing
# browser localization reviewer unchanged.
# --------------------------------------------------------------------------


def _scene_record(tmp_path: Path, frame_id: str, *, scene_id: str, session_id: str, color: tuple[int, int, int]) -> SceneFrameProvenance:
    manifest_dir = tmp_path / session_id
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "frames").mkdir(exist_ok=True)
    image_path = manifest_dir / "frames" / f"{frame_id}.jpg"
    content_hash = _jpeg(image_path, color)
    return SceneFrameProvenance(
        scene_id=scene_id, capture_session_id=session_id, source_camera="stream-1", capture_time=None,
        frame_id=frame_id, content_hash=content_hash, width=64, height=48,
        capture_purpose=CAPTURE_PURPOSE_TRAINING_CANDIDATE, high_resolution=False,
        capture_manifest=str(manifest_dir / "capture-session-manifest.json"),
    )


def test_build_scene_review_tranche_filters_by_scene() -> None:
    records = (
        SceneFrameProvenance(
            scene_id="lawn-north", capture_session_id="s1", source_camera="stream-1", capture_time=None,
            frame_id="f1", content_hash="a" * 64, width=10, height=10,
            capture_purpose=CAPTURE_PURPOSE_TRAINING_CANDIDATE, high_resolution=False, capture_manifest="m1.json",
        ),
        SceneFrameProvenance(
            scene_id="deck-01", capture_session_id="s2", source_camera="stream-1", capture_time=None,
            frame_id="f2", content_hash="b" * 64, width=10, height=10,
            capture_purpose=CAPTURE_PURPOSE_TRAINING_CANDIDATE, high_resolution=False, capture_manifest="m2.json",
        ),
    )
    tranche = build_scene_review_tranche(records, scene_id="lawn-north")
    assert tranche["frame_count"] == 1
    assert tranche["frames"][0]["frame_id"] == "f1"
    assert tranche["frames"][0]["priority_tier"]
    assert tranche["frames"][0]["stage3_target_lane"]
    assert tranche["creates_product_truth"] is False


def test_build_scene_review_tranche_requires_scene_or_session() -> None:
    with pytest.raises(WildlifeMultiSceneError):
        build_scene_review_tranche((), scene_id=None, session_id=None)


def test_build_scene_review_tranche_raises_on_empty_selection() -> None:
    records = (
        SceneFrameProvenance(
            scene_id="lawn-north", capture_session_id="s1", source_camera="stream-1", capture_time=None,
            frame_id="f1", content_hash="a" * 64, width=10, height=10,
            capture_purpose=CAPTURE_PURPOSE_TRAINING_CANDIDATE, high_resolution=False, capture_manifest="m1.json",
        ),
    )
    with pytest.raises(WildlifeMultiSceneError):
        build_scene_review_tranche(records, scene_id="no-such-scene")


def test_build_scene_review_tranche_packet_is_consumable_by_the_existing_reviewer(tmp_path: Path) -> None:
    """Integration proof: the *unmodified* `build_stage3_tranche_review_
    packet`/`temporal-review-validate` pipeline accepts a scene/session
    tranche exactly like a real Stage-3 tranche -- reusing the existing
    browser localization reviewer, not a second review system."""

    from mockingbird.observation.temporal_annotation import validate_annotations
    from mockingbird.observation.temporal_review_io import (
        build_stage3_tranche_review_packet,
        load_annotation_set,
        load_capture_manifest,
    )

    record = _scene_record(tmp_path, "f1", scene_id="lawn-north", session_id="session-1", color=(5, 5, 5))
    tranche = build_scene_review_tranche((record,), scene_id="lawn-north")
    tranche_path = tmp_path / "scene-tranche.json"
    tranche_path.write_text(json.dumps(tranche))

    review_directory = tmp_path / "review-out"
    summary = build_stage3_tranche_review_packet(tranche_path, review_directory)
    assert summary["frame_count"] == 1

    manifest = load_capture_manifest(review_directory)
    annotations = load_annotation_set(review_directory)
    report = validate_annotations(manifest, annotations, actual_content_hash=lambda frame_id: record.content_hash)
    assert report.ok  # a fresh, all-unreviewed packet validates cleanly
