from datetime import UTC, datetime, timedelta

from mockingbird.motion.effective_primary import EvidenceCandidate, select_effective_primary


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def candidate(identifier: str, role: str, **kwargs) -> EvidenceCandidate:
    return EvidenceCandidate(identifier, role, NOW + kwargs.pop("offset", timedelta()), **kwargs)


def test_padded_crop_geometry_is_used_when_subject_continuity_is_supported() -> None:
    crop = candidate(
        "crop",
        "activity_crop",
        width=300,
        height=300,
        track_box=(0.4, 0.4, 0.5, 0.5),
        crop_box=(0.3, 0.3, 0.7, 0.7),
    )

    result = select_effective_primary([crop], support_start=NOW, support_end=NOW)

    assert (result.media_asset_id, result.reason) == (
        "crop",
        "high_resolution_temporally_aligned",
    )
    assert (result.temporally_supported, result.contained, result.edge_clipped) == (
        True,
        True,
        False,
    )


def test_tracked_evidence_is_supported_and_useful_without_crop_geometry() -> None:
    tracked = candidate("tracked", "tracked_best_frame", width=1920, height=1440)

    result = select_effective_primary([tracked])

    assert (result.media_asset_id, result.reason, result.temporally_supported) == (
        "tracked",
        "tracked_best_frame_preferred",
        True,
    )


def test_missing_temporal_metadata_is_uncertain_not_a_rejection() -> None:
    crop = candidate(
        "crop",
        "activity_crop",
        width=300,
        height=300,
        track_box=(0.4, 0.4, 0.5, 0.5),
        crop_box=(0.3, 0.3, 0.7, 0.7),
    )
    tracked = candidate("tracked", "tracked_best_frame", width=1920, height=1440)

    result = select_effective_primary([crop, tracked])

    assert (result.media_asset_id, result.reason, result.temporally_supported) == (
        "tracked",
        "tracked_best_frame_preferred",
        True,
    )


def test_affirmatively_late_crop_loses_to_tracked_evidence() -> None:
    crop = candidate(
        "crop",
        "activity_crop",
        offset=timedelta(seconds=20),
        width=300,
        height=300,
        track_box=(0.4, 0.4, 0.5, 0.5),
        crop_box=(0.3, 0.3, 0.7, 0.7),
    )
    tracked = candidate("tracked", "tracked_best_frame", width=160, height=120)

    result = select_effective_primary([crop, tracked], support_start=NOW, support_end=NOW)

    assert (result.media_asset_id, result.reason) == ("tracked", "tracked_best_frame_preferred")


def test_clipped_crop_loses_to_tracked_evidence() -> None:
    crop = candidate(
        "crop",
        "activity_crop",
        width=300,
        height=300,
        track_box=(0.4, 0.4, 0.5, 0.5),
        crop_box=(0.45, 0.4, 0.7, 0.7),
    )
    tracked = candidate("tracked", "tracked_best_frame", width=160, height=120)

    result = select_effective_primary([crop, tracked])

    assert (result.media_asset_id, result.reason, result.edge_clipped) == (
        "tracked",
        "tracked_best_frame_preferred",
        None,
    )


def test_useful_high_resolution_crop_remains_selected_when_supported() -> None:
    crop = candidate(
        "crop",
        "activity_crop",
        width=300,
        height=300,
        track_box=(0.4, 0.4, 0.5, 0.5),
        crop_box=(0.3, 0.3, 0.7, 0.7),
    )
    tracked = candidate("tracked", "tracked_best_frame", width=160, height=120)

    result = select_effective_primary([crop, tracked], support_start=NOW, support_end=NOW)

    assert (result.media_asset_id, result.reason) == ("crop", "high_resolution_temporally_aligned")


def test_weak_crop_chooses_useful_tracked_evidence() -> None:
    crop = candidate("crop", "activity_crop", width=20, height=20)
    tracked = candidate("tracked", "tracked_best_frame", width=160, height=120)

    result = select_effective_primary([crop, tracked])

    assert (result.media_asset_id, result.reason) == ("tracked", "tracked_best_frame_preferred")


def test_user_selected_and_refined_evidence_remain_authoritative() -> None:
    tracked = candidate("tracked", "tracked_best_frame", width=160, height=120)
    selected = candidate("selected", "pretrigger", user_selected=True)
    refined = candidate("refined", "user_refined_crop", user_refined=True)

    assert select_effective_primary([tracked, selected]).reason == "user_selected_primary"
    assert select_effective_primary([tracked, refined]).reason == "user_refined_primary"


def test_pretrigger_is_a_fallback_below_useful_tracked_evidence() -> None:
    tracked = candidate("tracked", "tracked_best_frame", width=160, height=120)
    pretrigger = candidate("pretrigger", "pretrigger", width=160, height=120)

    assert select_effective_primary([pretrigger, tracked]).media_asset_id == "tracked"


def test_no_useful_primary_requires_every_candidate_to_fail() -> None:
    crop = candidate("crop", "activity_crop", width=20, height=20)
    tracked = candidate("tracked", "tracked_best_frame", width=20, height=20)

    result = select_effective_primary([crop, tracked])

    assert (result.media_asset_id, result.reason) == ("tracked", "no_useful_primary_evidence")
