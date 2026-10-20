"""Tier 1 pure tests for Gate C -- Representative Species Evidence v1's
canonical selector (see docs/representative-species-evidence-contract.md).
No database, no FastAPI, no repository -- exactly the same posture as
tests/test_place_activity_report.py.
"""

from __future__ import annotations

from datetime import UTC, datetime

from mockingbird.analytics.representative_evidence import (
    EvidenceCandidateFact,
    select_representative_evidence,
)


def _candidate(
    visit_id: str,
    *,
    media_asset_id: str | None = None,
    captured_at: datetime = datetime(2026, 1, 1, tzinfo=UTC),
    is_native_resolution: bool = False,
    has_subject_region: bool = False,
    subject_pixel_area: int = 0,
    asset_pixel_area: int = 1000,
) -> EvidenceCandidateFact:
    return EvidenceCandidateFact(
        visit_id=visit_id,
        media_asset_id=media_asset_id or f"media-{visit_id}",
        captured_at=captured_at,
        is_native_resolution=is_native_resolution,
        has_subject_region=has_subject_region,
        subject_pixel_area=subject_pixel_area,
        asset_pixel_area=asset_pixel_area,
    )


def test_empty_candidate_list_returns_none() -> None:
    assert select_representative_evidence([]) is None


def test_single_candidate_wins_regardless_of_quality() -> None:
    only = _candidate("visit-1", asset_pixel_area=1)
    assert select_representative_evidence([only]) is only


def test_native_resolution_outranks_everything_else() -> None:
    native = _candidate("visit-native", is_native_resolution=True, asset_pixel_area=100)
    bigger_non_native = _candidate("visit-big", is_native_resolution=False, asset_pixel_area=10_000_000)
    winner = select_representative_evidence([bigger_non_native, native])
    assert winner is native


def test_subject_region_outranks_raw_full_frame_at_equal_provenance() -> None:
    cropped = _candidate("visit-crop", has_subject_region=True, subject_pixel_area=100, asset_pixel_area=100)
    full_frame = _candidate("visit-full", has_subject_region=False, asset_pixel_area=10_000)
    winner = select_representative_evidence([full_frame, cropped])
    assert winner is cropped


def test_larger_subject_pixel_area_wins_when_both_have_a_subject_region() -> None:
    small = _candidate("visit-small", has_subject_region=True, subject_pixel_area=50)
    large = _candidate("visit-large", has_subject_region=True, subject_pixel_area=5000)
    winner = select_representative_evidence([small, large])
    assert winner is large


def test_asset_pixel_area_is_the_tiebreak_when_subject_size_is_equal() -> None:
    smaller_asset = _candidate("visit-a", has_subject_region=True, subject_pixel_area=100, asset_pixel_area=1000)
    bigger_asset = _candidate("visit-b", has_subject_region=True, subject_pixel_area=100, asset_pixel_area=5000)
    winner = select_representative_evidence([smaller_asset, bigger_asset])
    assert winner is bigger_asset


def test_capture_recency_is_the_tiebreak_when_quality_signals_are_equal() -> None:
    older = _candidate("visit-old", captured_at=datetime(2026, 1, 1, tzinfo=UTC))
    newer = _candidate("visit-new", captured_at=datetime(2026, 6, 1, tzinfo=UTC))
    winner = select_representative_evidence([older, newer])
    assert winner is newer


def test_quality_signal_beats_recency() -> None:
    # A materially better, older frame must still win over a merely newer,
    # weaker one -- recency is the second-to-last tie-break, not a
    # trump card. See "Selection policy" in
    # docs/representative-species-evidence-contract.md.
    older_but_native = _candidate(
        "visit-old-native",
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        is_native_resolution=True,
    )
    newer_but_ordinary = _candidate(
        "visit-new-ordinary",
        captured_at=datetime(2026, 6, 1, tzinfo=UTC),
        is_native_resolution=False,
        asset_pixel_area=999_999,
    )
    winner = select_representative_evidence([newer_but_ordinary, older_but_native])
    assert winner is older_but_native


def test_stable_id_tiebreak_is_fully_deterministic_regardless_of_order() -> None:
    # Two candidates identical on every ranked field except id: the result
    # must not depend on which order they were supplied in.
    same_time = datetime(2026, 3, 1, tzinfo=UTC)
    a = _candidate("visit-aaa", media_asset_id="media-aaa", captured_at=same_time, asset_pixel_area=500)
    b = _candidate("visit-bbb", media_asset_id="media-bbb", captured_at=same_time, asset_pixel_area=500)
    forward = select_representative_evidence([a, b])
    backward = select_representative_evidence([b, a])
    assert forward is backward
    assert forward.visit_id == "visit-bbb"  # lexicographically larger wins, but consistently


def test_deterministic_regardless_of_input_ordering_with_many_candidates() -> None:
    candidates = [
        _candidate("visit-1", asset_pixel_area=10),
        _candidate("visit-2", has_subject_region=True, subject_pixel_area=200),
        _candidate("visit-3", is_native_resolution=True, asset_pixel_area=1),
        _candidate("visit-4", asset_pixel_area=999),
    ]
    forward = select_representative_evidence(candidates)
    reversed_order = select_representative_evidence(list(reversed(candidates)))
    assert forward is not None
    assert forward.visit_id == "visit-3"
    assert forward.visit_id == reversed_order.visit_id


# Everyday Wildlife Experience & Presentation Refinement v1: subject-region
# resolution. Boxes arrive in two different coordinate spaces; these pin the
# unit each one is measured in.

from mockingbird.analytics.representative_evidence import (  # noqa: E402
    MIN_CROP_SHORT_SIDE_PX,
    resolve_subject_region,
)


def test_frame_local_track_box_is_scaled_by_its_own_frame() -> None:
    assert resolve_subject_region(
        width=1000, height=500, normalized_track_box=[0.1, 0.2, 0.3, 0.6], normalized_crop_box=None
    ) == (True, 200 * 200)


def test_derived_crop_counts_its_own_pixels_not_the_parent_relative_fraction() -> None:
    has_region, area = resolve_subject_region(
        width=400, height=300, normalized_track_box=None, normalized_crop_box=[0.4, 0.4, 0.6, 0.6]
    )
    assert (has_region, area) == (True, 400 * 300)


def test_clean_crop_outranks_a_wide_frame_with_a_tiny_speck() -> None:
    crop_region = resolve_subject_region(
        width=400, height=300, normalized_track_box=None, normalized_crop_box=[0.4, 0.4, 0.6, 0.6]
    )
    speck_region = resolve_subject_region(
        width=1920, height=1080, normalized_track_box=[0.50, 0.50, 0.55, 0.55], normalized_crop_box=None
    )
    crop = _candidate(
        "visit-crop", has_subject_region=crop_region[0], subject_pixel_area=crop_region[1], asset_pixel_area=400 * 300
    )
    speck = _candidate(
        "visit-speck", has_subject_region=speck_region[0], subject_pixel_area=speck_region[1], asset_pixel_area=1920 * 1080
    )
    assert select_representative_evidence([speck, crop]) is crop


def test_upscaled_stub_crop_earns_no_subject_region_credit() -> None:
    assert MIN_CROP_SHORT_SIDE_PX > 32
    assert resolve_subject_region(
        width=48, height=48, normalized_track_box=None, normalized_crop_box=[0.1, 0.1, 0.5, 0.5]
    ) == (False, 0)


def test_malformed_or_missing_geometry_never_invents_a_subject() -> None:
    for box in ([0.5, 0.5, 0.4, 0.9], [0.1, 0.1, 1.2, 0.9], [0.1, 0.1, 0.2], [0.3, 0.3, 0.3, 0.8]):
        assert resolve_subject_region(
            width=800, height=600, normalized_track_box=box, normalized_crop_box=box
        ) == (False, 0)
    assert resolve_subject_region(
        width=None, height=600, normalized_track_box=[0.1, 0.1, 0.5, 0.5], normalized_crop_box=None
    ) == (False, 0)
