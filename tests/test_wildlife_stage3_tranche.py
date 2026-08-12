"""Hardware-free tests for the Stage-3 local domain-correction Tranche A
selector: deterministic prioritization, encounter/session-level
deduplication, split isolation, and frozen-holdout contamination rejection.
Uses small synthetic queue rows and images only -- no dependency on the
real 2,000-frame local-correction queue or the real frozen benchmark.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from mockingbird.training.wildlife import HoldoutRecord, canonical_fingerprint, dhash64, phash64
from mockingbird.training.wildlife_stage3_tranche import (
    LANE_EDGE_CONDITION,
    LANE_HARD_NEGATIVE_CONFUSOR,
    LANE_SMALL_FAR_POSITIVE,
    LOCAL_TRAIN_CANDIDATE,
    LOCAL_VALIDATION_CANDIDATE,
    PRIORITY_TIER_EDGE_CONDITION,
    PRIORITY_TIER_FEEDER_HARDWARE_CONFUSOR,
    PRIORITY_TIER_HIGH_CONFIDENCE_FALSE_POSITIVE,
    PRIORITY_TIER_KNOWN_MISS_OR_LOCALIZATION_FAILURE,
    PRIORITY_TIER_SMALL_FAR_OPPORTUNITY,
    PRIORITY_TIER_VEGETATION_OR_SHADOW_CONFUSOR,
    SOURCE_QUEUE_ID,
    WildlifeStage3TrancheError,
    assert_no_split_leakage,
    assign_local_split,
    check_frozen_contamination,
    deduplicate,
    distinct_scenes,
    frozen_contamination_content_hashes,
    holdout_v2_content_hashes,
    load_queue,
    priority_tier,
    select_tranche,
)


def _jpeg(path: Path, color: tuple[int, int, int], *, size: tuple[int, int] = (64, 48)) -> str:
    """A flat solid-color fill, or a smooth monotonic gradient, is a poor
    perceptual-hash test fixture: dHash only compares *relative* adjacent-
    pixel ordering, which a same-shaped-but-offset gradient never changes
    (verified directly: two gradients differing only by a constant color
    offset hashed to dHash distance 0 regardless of how different the
    colors were) -- and JPEG quantization of a near-constant image is
    separately unpredictable at the bit level. A wraparound (modulo)
    pattern whose *phase* depends on `color` gives dHash real, color-
    dependent local structure, so "same color -> near-identical hash" and
    "clearly different color -> clearly different hash" both hold reliably,
    matching how these hashes actually behave on real photos."""

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


def _row(tmp_path: Path, name: str, *, color: tuple[int, int, int], **changes: object) -> dict[str, object]:
    image_path = tmp_path / f"{name}.jpg"
    content_hash = _jpeg(image_path, color)
    values: dict[str, object] = {
        "frame_id": content_hash,
        "content_hash": content_hash,
        "image": str(image_path),
        "capture_manifest": str(tmp_path / "capture-session-manifest.json"),
        "capture_session_id": str(tmp_path / "session-a" / "capture-out"),
        "source_capture_timestamp": "2026-08-07T21:00:00+00:00",
        "high_resolution": False,
        "detector_observation_count": 0,
        "animal_detection_count": 0,
        "max_animal_score": None,
        "motion_proposal_count": 0,
        "trigger_reasons": [],
        "agent_suggested_positive": False,
        "agent_signal_reviewers": [],
        "signal_authority": "agent_diagnostic_non_truth",
        "review_status": "unreviewed",
        "training_eligible": False,
        "selection_tie_break": content_hash,
        "target_lane": "likely_positive_requires_human_boxes",
        "lane_priority": 1,
        "required_human_action": "inspect the exact full frame",
    }
    values.update(changes)
    return values


def _queue_payload(frames: list[dict[str, object]]) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": 1,
        "queue_id": SOURCE_QUEUE_ID,
        "seed": 260812,
        "queue_size": len(frames),
        "lane_quotas": {
            "likely_positive_requires_human_boxes": 1000,
            "static_clutter_negative_candidate": 750,
            "weather_lighting_negative_candidate": 250,
        },
        "frames": frames,
    }
    payload["semantic_fingerprint"] = canonical_fingerprint(payload)
    return payload


# --------------------------------------------------------------------------
# Deterministic prioritization
# --------------------------------------------------------------------------


def test_priority_tier_known_miss_ranks_above_generic_positive(tmp_path: Path) -> None:
    miss = _row(tmp_path, "miss", color=(10, 10, 10), agent_suggested_positive=True, animal_detection_count=0)
    generic = _row(tmp_path, "generic", color=(20, 20, 20), agent_suggested_positive=False, animal_detection_count=1, max_animal_score=0.6)
    assert priority_tier(miss) == PRIORITY_TIER_KNOWN_MISS_OR_LOCALIZATION_FAILURE
    assert priority_tier(generic) == PRIORITY_TIER_SMALL_FAR_OPPORTUNITY


def test_priority_tier_weak_engagement_is_localization_failure_proxy(tmp_path: Path) -> None:
    weak = _row(
        tmp_path, "weak", color=(30, 30, 30),
        agent_suggested_positive=True, animal_detection_count=1, max_animal_score=0.1,
    )
    assert priority_tier(weak) == PRIORITY_TIER_KNOWN_MISS_OR_LOCALIZATION_FAILURE


def test_priority_tier_classifies_negative_lanes(tmp_path: Path) -> None:
    high_confidence_fp = _row(
        tmp_path, "hc", color=(40, 40, 40), target_lane="static_clutter_negative_candidate",
        max_animal_score=0.8, trigger_reasons=[],
    )
    hardware = _row(
        tmp_path, "hw", color=(50, 50, 50), target_lane="static_clutter_negative_candidate",
        max_animal_score=0.05, trigger_reasons=["recurring_static_geometry"],
    )
    vegetation = _row(
        tmp_path, "veg", color=(60, 60, 60), target_lane="static_clutter_negative_candidate",
        max_animal_score=0.05, trigger_reasons=[],
    )
    edge = _row(tmp_path, "edge", color=(70, 70, 70), target_lane="weather_lighting_negative_candidate", max_animal_score=0.05)
    assert priority_tier(high_confidence_fp) == PRIORITY_TIER_HIGH_CONFIDENCE_FALSE_POSITIVE
    assert priority_tier(hardware) == PRIORITY_TIER_FEEDER_HARDWARE_CONFUSOR
    assert priority_tier(vegetation) == PRIORITY_TIER_VEGETATION_OR_SHADOW_CONFUSOR
    assert priority_tier(edge) == PRIORITY_TIER_EDGE_CONDITION


def test_priority_tier_is_deterministic(tmp_path: Path) -> None:
    row = _row(tmp_path, "det", color=(80, 80, 80), agent_suggested_positive=True, animal_detection_count=0)
    results = {priority_tier(row) for _ in range(20)}
    assert results == {PRIORITY_TIER_KNOWN_MISS_OR_LOCALIZATION_FAILURE}


# --------------------------------------------------------------------------
# Encounter/session-level deduplication
# --------------------------------------------------------------------------


def test_deduplicate_collapses_same_session_same_time_bucket(tmp_path: Path) -> None:
    base = _row(tmp_path, "a", color=(10, 20, 30), source_capture_timestamp="2026-08-07T21:00:00+00:00")
    near_in_time = _row(tmp_path, "b", color=(200, 30, 40), source_capture_timestamp="2026-08-07T21:00:02+00:00")
    far_in_time = _row(tmp_path, "c", color=(30, 200, 40), source_capture_timestamp="2026-08-07T21:05:00+00:00")
    kept, stats = deduplicate([base, near_in_time, far_in_time])
    # `near_in_time` shares base's session+5s bucket -> collapsed to base's
    # representative even though its own pixels differ; `far_in_time` is a
    # genuinely separate temporal neighborhood and survives.
    assert [row["frame_id"] for row in kept] == [base["frame_id"], far_in_time["frame_id"]]
    assert stats.candidates_before_dedup == 3
    assert stats.removed_by_temporal_cluster == 1
    assert stats.selected == 2


def test_deduplicate_preserves_priority_order_representative(tmp_path: Path) -> None:
    """The *first* (highest-priority) row in a cluster wins -- caller order matters."""

    high_priority = _row(tmp_path, "hp", color=(10, 10, 10), source_capture_timestamp="2026-08-07T21:00:00+00:00")
    low_priority = _row(tmp_path, "lp", color=(10, 10, 11), source_capture_timestamp="2026-08-07T21:00:01+00:00")
    kept, _ = deduplicate([high_priority, low_priority])
    assert len(kept) == 1
    assert kept[0]["frame_id"] == high_priority["frame_id"]


def test_deduplicate_perceptual_layer_catches_cross_bucket_near_duplicate(tmp_path: Path) -> None:
    """Two rows far enough apart in time to land in different buckets, but
    pixel-identical, are still caught by the dual-hash layer."""

    image_path_a = tmp_path / "same-a.jpg"
    image_path_b = tmp_path / "same-b.jpg"
    Image.new("RGB", (64, 48), color=(123, 45, 67)).save(image_path_a, format="JPEG", quality=95)
    Image.new("RGB", (64, 48), color=(123, 45, 67)).save(image_path_b, format="JPEG", quality=95)
    from hashlib import sha256
    hash_a = sha256(image_path_a.read_bytes()).hexdigest()
    hash_b = sha256(image_path_b.read_bytes()).hexdigest()
    row_a = _row(tmp_path, "row-a", color=(1, 1, 1))
    row_a.update(image=str(image_path_a), content_hash=hash_a, frame_id=hash_a, selection_tie_break=hash_a,
                 source_capture_timestamp="2026-08-07T21:00:00+00:00")
    row_b = _row(tmp_path, "row-b", color=(2, 2, 2))
    row_b.update(image=str(image_path_b), content_hash=hash_b, frame_id=hash_b, selection_tie_break=hash_b,
                 source_capture_timestamp="2026-08-07T21:10:00+00:00")  # 10 minutes later: different bucket
    kept, stats = deduplicate([row_a, row_b])
    assert len(kept) == 1
    assert stats.removed_by_temporal_cluster == 0
    assert stats.removed_by_perceptual_similarity == 1


def test_deduplicate_min_keep_never_undershoots(tmp_path: Path) -> None:
    """Even when every row is a genuine near-duplicate, `min_keep` bounds
    how much the perceptual layer alone may remove."""

    rows = []
    for index in range(5):
        image_path = tmp_path / f"same-{index}.jpg"
        Image.new("RGB", (64, 48), color=(50, 60, 70)).save(image_path, format="JPEG", quality=95)
        from hashlib import sha256
        content_hash = sha256(image_path.read_bytes()).hexdigest() + f"{index:02d}"  # force distinct frame_id
        row = _row(tmp_path, f"row-{index}", color=(1, 1, 1))
        row.update(
            image=str(image_path), content_hash=content_hash, frame_id=content_hash, selection_tie_break=content_hash,
            source_capture_timestamp=f"2026-08-07T21:{index:02d}:00+00:00",  # each in a different 5s bucket
        )
        rows.append(row)
    kept, stats = deduplicate(rows, min_keep=3)
    assert len(kept) == 3
    assert stats.removed_by_perceptual_similarity == 2


def test_distinct_scenes_counts_sessions(tmp_path: Path) -> None:
    row_one = _row(tmp_path, "one", color=(1, 1, 1), capture_session_id="session-x")
    row_two = _row(tmp_path, "two", color=(2, 2, 2), capture_session_id="session-y")
    row_three = _row(tmp_path, "three", color=(3, 3, 3), capture_session_id="session-x")
    result = distinct_scenes([row_one, row_two, row_three])
    assert result["distinct_capture_sessions"] == 2
    assert result["frames_per_session"] == {"session-x": 2, "session-y": 1}


# --------------------------------------------------------------------------
# select_tranche: lane targets, holdout-v2, and contamination exclusion
# --------------------------------------------------------------------------


def _build_small_queue(tmp_path: Path, *, count_per_lane: int = 6) -> dict[str, object]:
    frames: list[dict[str, object]] = []
    lanes = [
        ("likely_positive_requires_human_boxes", 60),
        ("static_clutter_negative_candidate", 120),
        ("weather_lighting_negative_candidate", 180),
    ]
    for lane, base_color in lanes:
        for index in range(count_per_lane):
            frames.append(_row(
                tmp_path, f"{lane}-{index}", color=(base_color, index * 10, 5),
                target_lane=lane, lane_priority=index + 1,
                source_capture_timestamp=f"2026-08-0{7}T2{index}:00:00+00:00",
                capture_session_id=str(tmp_path / f"session-{lane}-{index}"),
            ))
    return _queue_payload(frames)


def test_select_tranche_hits_small_lane_targets(tmp_path: Path) -> None:
    queue_payload = _build_small_queue(tmp_path, count_per_lane=6)
    lane_targets = {LANE_SMALL_FAR_POSITIVE: 4, LANE_HARD_NEGATIVE_CONFUSOR: 4, LANE_EDGE_CONDITION: 4}
    result = select_tranche(queue_payload, lane_targets=lane_targets)
    assert len(result["frames"]) == 12
    lanes_selected = {row["stage3_target_lane"] for row in result["frames"]}
    assert lanes_selected == {LANE_SMALL_FAR_POSITIVE, LANE_HARD_NEGATIVE_CONFUSOR, LANE_EDGE_CONDITION}
    for lane, target in lane_targets.items():
        assert result["lanes"][lane]["dedup"]["selected"] == target


def test_select_tranche_raises_when_lane_cannot_reach_target(tmp_path: Path) -> None:
    queue_payload = _build_small_queue(tmp_path, count_per_lane=2)
    with pytest.raises(WildlifeStage3TrancheError):
        select_tranche(queue_payload, lane_targets={LANE_SMALL_FAR_POSITIVE: 10, LANE_HARD_NEGATIVE_CONFUSOR: 1, LANE_EDGE_CONDITION: 1})


def test_select_tranche_excludes_holdout_v2_hashes(tmp_path: Path) -> None:
    queue_payload = _build_small_queue(tmp_path, count_per_lane=6)
    reserved_hash = queue_payload["frames"][0]["content_hash"]
    result = select_tranche(
        queue_payload, holdout_v2_hashes=frozenset({reserved_hash}),
        lane_targets={LANE_SMALL_FAR_POSITIVE: 4, LANE_HARD_NEGATIVE_CONFUSOR: 4, LANE_EDGE_CONDITION: 4},
    )
    assert result["excluded_holdout_v2_hashes"] == 1
    assert reserved_hash not in {row["content_hash"] for row in result["frames"]}


def test_select_tranche_excludes_frozen_contamination_hashes(tmp_path: Path) -> None:
    queue_payload = _build_small_queue(tmp_path, count_per_lane=6)
    contaminated_hash = queue_payload["frames"][6]["content_hash"]  # first static_clutter row
    result = select_tranche(
        queue_payload, frozen_contamination_hashes=frozenset({contaminated_hash}),
        lane_targets={LANE_SMALL_FAR_POSITIVE: 4, LANE_HARD_NEGATIVE_CONFUSOR: 4, LANE_EDGE_CONDITION: 4},
    )
    assert result["excluded_frozen_contamination_hashes"] == 1
    assert contaminated_hash not in {row["content_hash"] for row in result["frames"]}


def test_load_queue_rejects_wrong_identity(tmp_path: Path) -> None:
    payload = _queue_payload([_row(tmp_path, "only", color=(1, 1, 1))])
    payload["queue_id"] = "not-the-real-queue"
    payload["semantic_fingerprint"] = canonical_fingerprint({k: v for k, v in payload.items() if k != "semantic_fingerprint"})
    path = tmp_path / "queue.json"
    import json
    path.write_text(json.dumps(payload))
    with pytest.raises(WildlifeStage3TrancheError):
        load_queue(path)


def test_load_queue_rejects_tampered_fingerprint(tmp_path: Path) -> None:
    payload = _queue_payload([_row(tmp_path, "only", color=(1, 1, 1))])
    payload["semantic_fingerprint"] = "0" * 64
    path = tmp_path / "queue.json"
    import json
    path.write_text(json.dumps(payload))
    with pytest.raises(WildlifeStage3TrancheError):
        load_queue(path)


# --------------------------------------------------------------------------
# Split isolation
# --------------------------------------------------------------------------


def test_assign_local_split_never_splits_a_session(tmp_path: Path) -> None:
    rows = []
    for session in range(4):
        for index in range(5):
            rows.append(_row(
                tmp_path, f"s{session}-{index}", color=(session, index, 0),
                capture_session_id=f"session-{session}",
            ))
    summary = assign_local_split(rows, seed=1)
    assert summary["validation_frame_count"] + summary["train_frame_count"] == len(rows)
    assert_no_split_leakage(rows)  # must not raise
    for session in range(4):
        splits = {row["split_candidate"] for row in rows if row["capture_session_id"] == f"session-{session}"}
        assert len(splits) == 1


def test_assign_local_split_is_deterministic_for_a_fixed_seed(tmp_path: Path) -> None:
    rows_a = [_row(tmp_path, f"a{i}", color=(i, 0, 0), capture_session_id=f"session-{i % 3}") for i in range(9)]
    rows_b = [_row(tmp_path, f"b{i}", color=(i, 0, 0), capture_session_id=f"session-{i % 3}") for i in range(9)]
    assign_local_split(rows_a, seed=42)
    assign_local_split(rows_b, seed=42)
    splits_a = {row["capture_session_id"]: row["split_candidate"] for row in rows_a}
    splits_b = {row["capture_session_id"]: row["split_candidate"] for row in rows_b}
    assert splits_a == splits_b


def test_assign_local_split_targets_approximately_25_percent(tmp_path: Path) -> None:
    # Eight same-size sessions: a good approximation is achievable, so the
    # closest-prefix search should land reasonably close to 25%, not
    # overshoot to ~38% the way a naive "first prefix >= target" walk would.
    rows = []
    for session in range(8):
        for index in range(10):
            rows.append(_row(tmp_path, f"s{session}-{index}", color=(session, index, 0), capture_session_id=f"session-{session}"))
    summary = assign_local_split(rows, seed=7)
    assert 0.15 <= summary["validation_fraction_achieved"] <= 0.35


def test_assert_no_split_leakage_raises_on_violation() -> None:
    rows = [
        {"capture_session_id": "session-a", "split_candidate": LOCAL_TRAIN_CANDIDATE},
        {"capture_session_id": "session-a", "split_candidate": LOCAL_VALIDATION_CANDIDATE},
    ]
    with pytest.raises(WildlifeStage3TrancheError):
        assert_no_split_leakage(rows)


# --------------------------------------------------------------------------
# Holdout v2
# --------------------------------------------------------------------------


def test_holdout_v2_content_hashes_reads_manifest_flag(tmp_path: Path) -> None:
    import json

    manifest_path = tmp_path / "capture-session-manifest.json"
    manifest_path.write_text(json.dumps({
        "frames": [
            {"content_hash": "aa" * 32, "holdout_v2_candidate": True},
            {"content_hash": "bb" * 32, "holdout_v2_candidate": False},
            {"content_hash": "cc" * 32},
        ],
    }))
    reserved = holdout_v2_content_hashes([manifest_path])
    assert reserved == {"aa" * 32}


def test_holdout_v2_content_hashes_tolerates_missing_or_invalid_manifest(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.json"
    reserved = holdout_v2_content_hashes([missing])
    assert reserved == set()


# --------------------------------------------------------------------------
# Frozen-benchmark contamination
# --------------------------------------------------------------------------


def _holdout_record_for(tmp_path: Path, name: str, color: tuple[int, int, int]) -> tuple[HoldoutRecord, Path]:
    path = tmp_path / f"holdout-{name}.jpg"
    _jpeg(path, color)
    from hashlib import sha256
    content_hash = sha256(path.read_bytes()).hexdigest()
    record = HoldoutRecord(
        frame_id=f"holdout-{name}", sha256=content_hash, dhash64=dhash64(path), phash64=phash64(path),
        source_identity=f"mockingbird-frozen:holdout-{name}", parent_identity=None,
        site_id="mockingbird-local-site", camera_id="scene", sequence_id=None,
    )
    return record, path


def test_frozen_contamination_content_hashes_flags_exact_duplicate(tmp_path: Path) -> None:
    holdout_record, holdout_path = _holdout_record_for(tmp_path, "one", (5, 6, 7))
    # A tranche row byte-identical to the holdout image.
    row = _row(tmp_path, "dup", color=(1, 1, 1))
    import shutil
    shutil.copyfile(holdout_path, row["image"])
    from hashlib import sha256
    same_hash = sha256(Path(row["image"]).read_bytes()).hexdigest()
    row.update(content_hash=same_hash, frame_id=same_hash)
    clean = _row(tmp_path, "clean", color=(250, 10, 250))

    excluded, summary = frozen_contamination_content_hashes([row, clean], holdout=(holdout_record,))
    assert excluded == {same_hash}
    assert summary["excluded_exact_match_count"] == 1
    assert summary["total_excluded_content_hashes"] == 1


def test_frozen_contamination_content_hashes_flags_near_duplicate(tmp_path: Path) -> None:
    holdout_record, holdout_path = _holdout_record_for(tmp_path, "near", (100, 120, 140))
    # A genuine near-duplicate: identical visual content, re-encoded at a
    # different JPEG quality -- byte-different, perceptually indistinguishable.
    # (A tiny flat-color RGB shift is not a reliable near-duplicate fixture:
    # JPEG quantization of a near-constant image is unpredictable at the bit
    # level, verified directly against the real dHash/pHash implementation.)
    near_duplicate = _row(tmp_path, "near-row", color=(100, 120, 140))
    with Image.open(holdout_path) as opened:
        opened.convert("RGB").save(near_duplicate["image"], format="JPEG", quality=60)
    from hashlib import sha256
    near_hash = sha256(Path(near_duplicate["image"]).read_bytes()).hexdigest()
    near_duplicate.update(content_hash=near_hash, frame_id=near_hash)
    assert near_hash != holdout_record.sha256  # byte-different, proving this is a *near* not exact match

    excluded, summary = frozen_contamination_content_hashes([near_duplicate], holdout=(holdout_record,))
    assert near_hash in excluded
    assert summary["excluded_near_duplicate_count"] == 1


def test_frozen_contamination_content_hashes_leaves_distinct_images_unflagged(tmp_path: Path) -> None:
    holdout_record, _ = _holdout_record_for(tmp_path, "distinct", (10, 10, 10))
    distinct_row = _row(tmp_path, "distinct-row", color=(245, 245, 245))
    excluded, summary = frozen_contamination_content_hashes([distinct_row], holdout=(holdout_record,))
    assert excluded == set()
    assert summary["total_excluded_content_hashes"] == 0


def test_check_frozen_contamination_passes_when_clean(tmp_path: Path) -> None:
    holdout_record, _ = _holdout_record_for(tmp_path, "clean-holdout", (10, 10, 10))
    clean_row = _row(tmp_path, "clean-selected", color=(245, 245, 245))
    report = check_frozen_contamination([clean_row], holdout=(holdout_record,))
    assert report["passed"] is True
    assert report["exact_sha256_matches"] == []
    assert report["near_duplicate_matches"] == []


def test_check_frozen_contamination_fails_on_exact_match(tmp_path: Path) -> None:
    holdout_record, holdout_path = _holdout_record_for(tmp_path, "matched", (33, 44, 55))
    row = _row(tmp_path, "matched-row", color=(1, 1, 1))
    import shutil
    shutil.copyfile(holdout_path, row["image"])
    from hashlib import sha256
    same_hash = sha256(Path(row["image"]).read_bytes()).hexdigest()
    row.update(content_hash=same_hash, frame_id=same_hash)
    report = check_frozen_contamination([row], holdout=(holdout_record,))
    assert report["passed"] is False
    assert len(report["exact_sha256_matches"]) == 1


def test_check_frozen_contamination_fails_closed_on_integrity_mismatch(tmp_path: Path) -> None:
    holdout_record, _ = _holdout_record_for(tmp_path, "integrity", (9, 9, 9))
    row = _row(tmp_path, "tampered", color=(200, 200, 200))
    row["content_hash"] = "0" * 64  # does not match the real file's sha256
    report = check_frozen_contamination([row], holdout=(holdout_record,))
    assert report["passed"] is False
    assert len(report["content_hash_integrity_failures"]) == 1
