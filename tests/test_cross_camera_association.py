"""Camera / Source + Multi-Camera Maturity v1, Phase I: deterministic
cross-camera (visual+visual, different-Source) association tiering. Pure
function calls only -- no repository, no database."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mockingbird.observation.cross_camera_association import (
    CrossCameraEventCandidate,
    evaluate_cross_camera_association,
)
from mockingbird.observation.temporal_evidence import event_evidence_interval

BASE = datetime(2026, 8, 23, 10, 0, 0, tzinfo=UTC)


def _interval(start_offset_s: float, end_offset_s: float):
    return event_evidence_interval(
        started_at=BASE + timedelta(seconds=start_offset_s),
        ended_at=BASE + timedelta(seconds=end_offset_s),
        clock_provenance="visual_event_range",
    )


def test_single_subject_strict_window_matching_area_is_associated() -> None:
    subject = _interval(0, 8)
    candidates = (
        CrossCameraEventCandidate(
            event_id="event-b", interval=_interval(9, 12), sibling_visit_count=1, area_name="Backyard feeder",
        ),
    )

    decisions = evaluate_cross_camera_association(
        subject,
        subject_sibling_count=1,
        subject_area_name="Backyard Feeder",  # case/whitespace-insensitive match
        candidates=candidates,
    )

    assert len(decisions) == 1
    assert decisions[0].event_id == "event-b"
    assert decisions[0].tier == "associated"
    assert decisions[0].spatial_signal == "matching_area_name"
    assert decisions[0].multi_subject is False


def test_confirmed_differing_area_is_independent_not_merely_possible() -> None:
    """Real, user-authored evidence of physical separation (two different
    named Areas) drops the candidate entirely -- proving no false merge
    (Journey 6) *without* flooding the reviewer with a noisy 'possible' hint
    for what the user has already told MockingBird are two different
    places."""

    subject = _interval(0, 8)
    non_matching = CrossCameraEventCandidate(
        event_id="event-b", interval=_interval(9, 12), sibling_visit_count=1, area_name="Driveway",
    )

    decisions = evaluate_cross_camera_association(
        subject, subject_sibling_count=1, subject_area_name="Backyard feeder", candidates=(non_matching,),
    )

    assert decisions == ()


def test_unset_area_on_either_side_is_ambiguous_possible_never_associated() -> None:
    """Do NOT use species equality alone to merge events -- and timing alone
    with genuinely unknown spatial information must cap at 'possible',
    never 'associated', and never silently drop to independent either
    (Journey 8: ambiguous overlap where automatic merging would be
    unsafe)."""

    subject = _interval(0, 8)
    unset_area = CrossCameraEventCandidate(
        event_id="event-c", interval=_interval(9, 12), sibling_visit_count=1, area_name=None,
    )

    decisions = evaluate_cross_camera_association(
        subject, subject_sibling_count=1, subject_area_name="Backyard feeder", candidates=(unset_area,),
    )

    assert len(decisions) == 1
    assert decisions[0].tier == "possible"
    assert decisions[0].spatial_signal == "unknown"

    # Symmetric: the subject itself having no unambiguous Area is the same
    # honest "unknown," not "differing."
    decisions_subject_unset = evaluate_cross_camera_association(
        subject,
        subject_sibling_count=1,
        subject_area_name=None,
        candidates=(
            CrossCameraEventCandidate(
                event_id="event-d", interval=_interval(9, 12), sibling_visit_count=1, area_name="Backyard feeder",
            ),
        ),
    )
    assert decisions_subject_unset[0].tier == "possible"
    assert decisions_subject_unset[0].spatial_signal == "unknown"


def test_differing_area_candidate_does_not_count_toward_ambiguity() -> None:
    """A confirmed-independent candidate must not be able to *suppress* a
    genuinely plausible one by making it look ambiguous -- the differing-
    Area candidate is dropped before the "how many are competing" check,
    not after."""

    subject = _interval(0, 8)
    plausible = CrossCameraEventCandidate(
        event_id="event-b", interval=_interval(9, 12), sibling_visit_count=1, area_name="Backyard feeder",
    )
    confirmed_elsewhere = CrossCameraEventCandidate(
        event_id="event-c", interval=_interval(9, 11), sibling_visit_count=1, area_name="Driveway",
    )

    decisions = evaluate_cross_camera_association(
        subject,
        subject_sibling_count=1,
        subject_area_name="Backyard feeder",
        candidates=(plausible, confirmed_elsewhere),
    )

    assert len(decisions) == 1
    assert decisions[0].event_id == "event-b"
    assert decisions[0].tier == "associated"


def test_multi_subject_either_side_caps_at_possible_even_with_matching_area() -> None:
    """Phase J: two concurrent subjects on either camera makes the pairing
    inherently ambiguous -- never confidently associated, regardless of
    timing/area agreement."""

    subject = _interval(0, 8)
    candidate_two_subjects = CrossCameraEventCandidate(
        event_id="event-b", interval=_interval(9, 12), sibling_visit_count=2, area_name="Backyard feeder",
    )

    decisions = evaluate_cross_camera_association(
        subject, subject_sibling_count=1, subject_area_name="Backyard feeder", candidates=(candidate_two_subjects,),
    )

    assert decisions[0].tier == "possible"
    assert decisions[0].multi_subject is True
    # The spatial fact is still honestly recorded even though the tier was
    # capped by the *other* gate -- a reviewer can see both facts.
    assert decisions[0].spatial_signal == "matching_area_name"

    subject_two_subjects_decisions = evaluate_cross_camera_association(
        subject,
        subject_sibling_count=2,
        subject_area_name="Backyard feeder",
        candidates=(
            CrossCameraEventCandidate(
                event_id="event-d", interval=_interval(9, 12), sibling_visit_count=1, area_name="Backyard feeder",
            ),
        ),
    )
    assert subject_two_subjects_decisions[0].tier == "possible"
    assert subject_two_subjects_decisions[0].multi_subject is True


def test_multiple_competing_candidates_never_associate_any_of_them() -> None:
    """Two different cameras both plausibly in range for the same subject
    Event -- genuinely ambiguous which one (if either) is the same
    encounter, so neither reaches 'associated', matching the reused engine's
    own built-in ambiguity conservatism."""

    subject = _interval(0, 8)
    candidates = (
        CrossCameraEventCandidate(
            event_id="event-b", interval=_interval(9, 12), sibling_visit_count=1, area_name="Backyard feeder",
        ),
        CrossCameraEventCandidate(
            event_id="event-c", interval=_interval(9, 11), sibling_visit_count=1, area_name="Backyard feeder",
        ),
    )

    decisions = evaluate_cross_camera_association(
        subject, subject_sibling_count=1, subject_area_name="Backyard feeder", candidates=candidates,
    )

    assert len(decisions) == 2
    assert all(decision.tier == "possible" for decision in decisions)


def test_outside_wider_window_is_independent_no_row_at_all() -> None:
    subject = _interval(0, 8)
    far_candidate = CrossCameraEventCandidate(
        event_id="event-b", interval=_interval(200, 205), sibling_visit_count=1, area_name="Backyard feeder",
    )

    decisions = evaluate_cross_camera_association(
        subject, subject_sibling_count=1, subject_area_name="Backyard feeder", candidates=(far_candidate,),
    )

    assert decisions == ()


def test_within_possible_but_not_strict_window_is_possible_even_with_matching_area() -> None:
    subject = _interval(0, 0)  # instant at t=0
    candidate = CrossCameraEventCandidate(
        event_id="event-b", interval=_interval(30, 30), sibling_visit_count=1, area_name="Backyard feeder",
    )  # 30s gap: beyond the 15s strict window, within the 60s possible window

    decisions = evaluate_cross_camera_association(
        subject, subject_sibling_count=1, subject_area_name="Backyard feeder", candidates=(candidate,),
    )

    assert len(decisions) == 1
    assert decisions[0].tier == "possible"
    assert decisions[0].gap_ms == 30_000
