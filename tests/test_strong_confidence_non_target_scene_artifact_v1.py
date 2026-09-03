"""Strong-Confidence Non-Target & Scene-Artifact Visit Admission Correctness
v1.

Reopened by real field evidence: Representative Daylight Gate A Field
Acceptance v11 (docs/representative-daylight-gate-a-field-acceptance-v11-
report.md, "False Visits") found 8/18 confirmed-false Visits, all admitted
via the *strong-detection bypass*
(`candidate_quality_gate._insufficient_detector_corroboration`'s own
`strong_detection_count > 0` escape, which -- correctly, by design -- never
consults count/concentration corroboration once any single detection clears
`strong_detection_threshold`): 7 a real utility/landscaping worker
detected as MDv5's own `animal`-class false positive at genuinely high
confidence (matching the already-accepted, out-of-scope Person-Background-
False-Positive residual class -- see docs/person-background-false-positive-
attribution-v1-report.md), and 1 (Visit 018) a leaf/branch cluster at the
classic "Location A" foliage geometry (the same v8/v9/v10 coordinates
`tests/test_independent_corroboration_value_persistent_confusor_v1.py`'s own
`_LOCATION_A_BOX` already reuses) that happened to clear the strong-
detection threshold 6 times in one occurrence.

Every reproducer below drives real `DetectionObservation`/`FramePacket`
sequences through the real, unmodified production path -- identical
methodology to `tests/test_independent_corroboration_value_persistent_
confusor_v1.py` (`ProviderNeutralFrameTracker.observe()` ->
`build_tracklets`/`assemble_visit_episodes` ->
`CandidateVisitAuthorityAdapter.attempt_candidate` -> a real, isolated
`ProductRepository`) -- never a fixture that simply declares a proposal
false. See docs/strong-confidence-non-target-scene-artifact-visit-
admission-correctness-v1-report.md for the full field-evidence trace and
the locked contract this file exercises.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.observation.candidate_visit_adapter import CandidateVisitAuthorityAdapter
from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode
from mockingbird.observation.contracts import DetectionObservation, EvidenceCandidate, FramePacket, TrackUpdate
from mockingbird.observation.frame_tracker import ProviderNeutralFrameTracker, TrackerConfiguration
from mockingbird.observation.visit_episode_assembler import assemble_visit_episodes, build_tracklets
from mockingbird.repository.product_repository import ProductRepository

STREAM_ID = "stream-backyard-feeder"
ZONE_ID = "zone-feeder"
BASE_TIME = datetime(2026, 9, 2, 16, 29, 0, tzinfo=UTC)
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"1" * 128 + b"\xff\xd9"

# v11's own reported "Location A" coordinates (bbox center (0.202, 0.691) --
# see the report's "False Visits"/"Independent-corroboration field proof");
# reused unmodified from the sibling milestone's own already-established
# constant (duplicated, not imported, matching this codebase's own per-
# milestone self-contained test-file convention -- see that file's own
# disclosure for `_LOCATION_A_BOX`).
_LOCATION_A_BOX = (0.16, 0.66, 0.24, 0.74)  # center = (0.20, 0.70)

# A separate, unrelated feeder-perch location used for the "real bird"
# positive controls -- geometrically far from Location A so no test in this
# file can accidentally cross-contaminate region history between the two.
_FEEDER_BOX = (0.55, 0.40, 0.62, 0.48)

# A human-scale bounding box, distinct in both geometry and aspect ratio
# from either wildlife location above -- used only for the person-associated
# reproducer below.
_PERSON_REGION_BOX = (0.40, 0.30, 0.55, 0.75)


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    yield repo
    repo.close()


def _tracker_config(**overrides: object) -> TrackerConfiguration:
    """Mirrors the real deployed `frame_driven_provider.FrameDrivenSettings`
    defaults exactly -- identical to the sibling `test_independent_
    corroboration_value_persistent_confusor_v1.py`'s own `_tracker_config`,
    duplicated (not imported) to keep this file self-contained."""
    values: dict[str, object] = dict(
        strong_detection_threshold=0.70,
        minimum_detector_confirmations=2,
        minimum_tracker_support_frames=1,
        maximum_missed_frames=3,
        maximum_frame_gap_ms=1500,
        tracker_expiry_ms=1200,
        maximum_track_duration_ms=30_000,
        maximum_active_tracks=24,
        minimum_iou=0.05,
        maximum_centroid_distance=0.22,
        ambiguity_margin=0.01,
        maximum_unsupported_detector_ms=5000,
        negative_detector_frames_to_end=2,
        ambiguous_reentry_window_ms=1500,
        weak_detector_support_floor=0.05,
        maximum_weak_support_span_ms=15_000,
    )
    values.update(overrides)
    return TrackerConfiguration(**values)


def _tracker() -> ProviderNeutralFrameTracker:
    return ProviderNeutralFrameTracker(
        STREAM_ID, _tracker_config(), support_resolver=lambda _frame, track: track.bounding_box,
    )


def _frame(offset_ms: int) -> FramePacket:
    return FramePacket(
        stream_id=STREAM_ID, media_asset_id=f"repro:{offset_ms}",
        captured_at=BASE_TIME + timedelta(milliseconds=offset_ms),
        frame_id=f"repro-frame-{offset_ms}", source_offset_ms=offset_ms, width=1920, height=1080,
    )


def _detection(
    frame: FramePacket,
    box: tuple[float, float, float, float],
    *,
    confidence: float,
    label: str = "animal",
    is_animal: bool = True,
) -> DetectionObservation:
    return DetectionObservation(
        detector_id="onnx-cuda", label=label, confidence=confidence, captured_at=frame.captured_at,
        observation_id=f"obs:{label}:{frame.frame_id}", frame_id=frame.frame_id, provider_id="frame-driven-onnx-cuda",
        model_key="md-v5a", bounding_box=box, class_source_label=("0" if is_animal else "1"), is_animal=is_animal,
    )


def _evidence_candidates_for(generation_id: str, box: tuple[float, float, float, float]) -> tuple[EvidenceCandidate, ...]:
    return (
        EvidenceCandidate(
            media_asset_id=f"shadow-burst:{generation_id}-id", stream_id=STREAM_ID, role="high_resolution_burst",
            captured_at=BASE_TIME, frame_id=f"{generation_id}-frame-1", source_offset_ms=0, width=1920, height=1080,
            subject_geometry=box, track_generation_id=generation_id,
            quality_facts=(("decodable", True), ("temporal_alignment", "aligned"), ("track_supported", True)),
        ),
        EvidenceCandidate(
            media_asset_id=f"shadow-burst:{generation_id}-ctx", stream_id=STREAM_ID, role="context",
            captured_at=BASE_TIME, frame_id=f"{generation_id}-frame-2", source_offset_ms=0, width=1920, height=1080,
            subject_geometry=box, track_generation_id=generation_id,
            quality_facts=(("decodable", True), ("temporal_alignment", "aligned"), ("track_supported", True)),
        ),
    )


def _adapter(repository: ProductRepository) -> CandidateVisitAuthorityAdapter:
    return CandidateVisitAuthorityAdapter(
        repository, detector_provenance="onnx-cuda", tracker_provenance="frame-driven-onnx-cuda-v1",
        provider_key="frame-driven-onnx-cuda",
    )


def _activate(repository: ProductRepository, *, now: datetime = BASE_TIME) -> None:
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=now)


def _build_tracklets(updates: list[TrackUpdate], *, box_by_generation: dict[str, tuple[float, float, float, float]]) -> tuple:
    generation_ids = {update.generation_id for update in updates}
    return build_tracklets(
        tuple(updates), stream_id=STREAM_ID,
        zone_id_by_generation={generation_id: ZONE_ID for generation_id in generation_ids},
        evidence_candidate_ids_by_generation={
            generation_id: tuple(
                candidate.media_asset_id
                for candidate in _evidence_candidates_for(generation_id, box_by_generation[generation_id])
            )
            for generation_id in generation_ids
        },
    )


def _assemble_one_proposal(updates: list[TrackUpdate], *, box: tuple[float, float, float, float]):
    generation_ids = {update.generation_id for update in updates}
    tracklets = _build_tracklets(updates, box_by_generation={generation_id: box for generation_id in generation_ids})
    result = assemble_visit_episodes(tracklets)
    assert len(result.proposals) == 1, "reproducer must assemble into exactly one chained proposal"
    return result.proposals[0]


def _attempt(repository: ProductRepository, proposal, *, box: tuple[float, float, float, float], observed_at: datetime = BASE_TIME):
    _activate(repository)
    candidates = tuple(
        candidate
        for generation_id in proposal.constituent_generation_ids
        for candidate in _evidence_candidates_for(generation_id, box)
    )
    evidence_bytes = {candidate.media_asset_id: JPEG_BYTES for candidate in candidates}
    return _adapter(repository).attempt_candidate(
        proposal, evidence_candidates=candidates, evidence_bytes=evidence_bytes, observed_at=observed_at,
    )


def _weak_rejection_ticks(box: tuple[float, float, float, float], confidences: list[float]) -> list:
    """Two-detection, single-generation, never-strong occurrence -- clears
    neither corroboration axis for `N=1` (`detection_count=2` does not
    exceed `2*1+1=3`; both detections are non-consecutive, matching v11's
    own disclosed shape for Location A's real weak recurrences)."""
    ticks: list = []
    offset = 0
    for confidence in confidences:
        ticks.append((offset, (confidence, box)))
        offset += 250
        ticks.append((offset, None))
        offset += 250
    ticks.append((offset + 5500, None))
    return ticks


def _drive_at(tracker: ProviderNeutralFrameTracker, ticks: list, *, start_ms: int) -> list[TrackUpdate]:
    updates: list[TrackUpdate] = []
    for relative_offset, payload in ticks:
        offset_ms = start_ms + relative_offset
        frame = _frame(offset_ms)
        detections = () if payload is None else (_detection(frame, payload[1], confidence=payload[0]),)
        updates.extend(tracker.observe(frame, detections).updates)
    return updates


def _finalize(tracker: ProviderNeutralFrameTracker) -> list[TrackUpdate]:
    return list(tracker.finalize("end_of_replay").updates)


def _run_single_occurrence(
    repository: ProductRepository, box: tuple[float, float, float, float], confidences: list[float], *, start_ms: int,
):
    tracker = _tracker()
    updates = _drive_at(tracker, _weak_rejection_ticks(box, confidences), start_ms=start_ms)
    updates += _finalize(tracker)
    proposal = _assemble_one_proposal(updates, box=box)
    assert len(proposal.constituent_generation_ids) == 1
    return _attempt(repository, proposal, box=box, observed_at=BASE_TIME + timedelta(milliseconds=start_ms))


# ---------------------------------------------------------------------------
# Strong-confidence scene artifact -- Visit 018's own shape (a recurring,
# always-weak-before-now location that suddenly clears the strong-detection
# threshold). See "Strong-artifact result" in the milestone report for the
# full accounting of what this class of fix can and cannot close.
# ---------------------------------------------------------------------------


class TestStrongSceneArtifactAtLocationA:
    def test_three_weak_rejections_now_build_scene_confusor_history(self, repository: ProductRepository) -> None:
        """Before this milestone's fix, `_touch_scene_confusor_region` was
        reachable only once `evaluate_evidence_admission` already said
        `admit` -- a location whose every occurrence failed corroboration
        (this test's own three, matching v11's own disclosed Location-A
        confidences 0.131/0.372/weak) left *zero* trace in
        `scene_confusor_regions`, no matter how many times it recurred.
        Post-fix, each rejection still returns exactly `reject_insufficient_
        detector_corroboration` (unchanged outcome/reason -- this is
        bookkeeping only) but now durably records the occurrence."""
        outcome_1 = _run_single_occurrence(repository, _LOCATION_A_BOX, [0.120, 0.131], start_ms=0)
        outcome_2 = _run_single_occurrence(repository, _LOCATION_A_BOX, [0.372, 0.310], start_ms=300_000)
        outcome_3 = _run_single_occurrence(repository, _LOCATION_A_BOX, [0.200, 0.220], start_ms=600_000)
        for outcome in (outcome_1, outcome_2, outcome_3):
            assert outcome.outcome == "reject_insufficient_detector_corroboration"
            assert outcome.reason == "never_strong_and_minimal_detector_corroboration"

        with repository.session_factory() as session:
            regions = repository._scene_confusor_regions_for_stream(
                session, stream_id=STREAM_ID, broad_class="animal", now=BASE_TIME + timedelta(milliseconds=600_000),
            )
        assert len(regions) == 1, "all three weak rejections must resolve to the same recurring region"
        assert regions[0].occurrence_count == 3, "each rejection must now be recorded, not silently dropped"

    def test_sudden_strong_occurrence_after_weak_history_remains_open(self, repository: ProductRepository) -> None:
        """The exact residual this milestone's own investigation surfaces,
        not silently papered over: even with the history fix above in
        place, a single occurrence whose own confidence independently
        clears `strong_detection_threshold` (0.70) escapes scene-confusor
        suspicion via *two* independent, unconditional design escapes --
        `evaluate_scene_confusor_suspicion`'s step 5 ("materially stronger
        than this region's own history") and step 6 ("independently strong,
        regardless of history") -- neither of which this milestone touches
        (see docs/strong-confidence-non-target-scene-artifact-visit-
        admission-correctness-v1-report.md, "Scene-confusor interaction",
        for why weakening either is not safe to do here: the real,
        field-proven feeder-pole stationary-real-bird control in
        Representative Daylight Gate A Field Acceptance v11 relies on the
        same unconditional protection). This test documents *today's real,
        understood* behavior -- both before and after this milestone's own
        fix -- for a future, separately-evidenced milestone to close; it
        does not assert desired product behavior."""
        _run_single_occurrence(repository, _LOCATION_A_BOX, [0.120, 0.131], start_ms=0)
        _run_single_occurrence(repository, _LOCATION_A_BOX, [0.372, 0.310], start_ms=300_000)
        _run_single_occurrence(repository, _LOCATION_A_BOX, [0.200, 0.220], start_ms=600_000)

        # Visit 018's own shape: one occurrence, 6 detections, all clearing
        # `strong_detection_threshold` -- matching the report's own "cleared
        # the strong-detection threshold 6 times in this one occurrence."
        strong_confidences = [0.72, 0.75, 0.71, 0.78, 0.73, 0.76]
        outcome_4 = _run_single_occurrence(repository, _LOCATION_A_BOX, strong_confidences, start_ms=900_000)

        # Still created -- the strong-detection bypass admits on this axis
        # regardless of the region's now-real history (see module docstring
        # above), exactly matching the real, unfixed v11 Visit 018 outcome.
        assert outcome_4.outcome == "created"

    def test_weak_recurring_confusor_that_later_clears_the_count_axis_is_now_caught(
        self, repository: ProductRepository,
    ) -> None:
        """What this milestone's fix *does* close: a location whose first
        few occurrences are each individually rejected (never strong, too
        few detections) but which later accumulates *just enough* weak
        detections to clear the count-based corroboration axis outright
        (never touching the strong-detection bypass at all) -- pre-fix,
        this occurrence would see a *blank* scene-confusor history (the
        three prior rejections left no trace) and be admitted; post-fix,
        its own recorded history is real, and neither confidence escape
        applies (0.48 is far below `strong_detection_threshold`, and only
        0.13 above the region's own prior weak ceiling of 0.372 --
        comfortably under the 0.15 `stronger_confidence_delta` escape), so
        the pre-existing, unmodified scene-confusor mechanism now correctly
        recognizes the recurrence."""
        _run_single_occurrence(repository, _LOCATION_A_BOX, [0.120, 0.131], start_ms=0)
        _run_single_occurrence(repository, _LOCATION_A_BOX, [0.372, 0.310], start_ms=300_000)
        _run_single_occurrence(repository, _LOCATION_A_BOX, [0.200, 0.220], start_ms=600_000)

        # Five never-strong detections comfortably clear `2*1+1=3` on the
        # count axis alone (N=1, so the concentration check is inert) --
        # `quality.admitted` would be `True` on its own, in isolation.
        weak_but_sufficient = [0.40, 0.45, 0.42, 0.48, 0.44]
        outcome_4 = _run_single_occurrence(repository, _LOCATION_A_BOX, weak_but_sufficient, start_ms=900_000)

        assert outcome_4.outcome == "blocked_scene_confusor_suspected"
        assert outcome_4.reason == "recurring_static_scene_geometry"
        assert outcome_4.visit_id is None

    def test_real_bird_first_ever_strong_sighting_at_a_fresh_location_is_unaffected(
        self, repository: ProductRepository,
    ) -> None:
        """Self-review control: this milestone's own history fix must never
        make a genuinely novel, first-time strong real sighting anywhere
        suspicious merely because *some other*, geometrically unrelated
        location in the same Stream has accumulated rejected-occurrence
        history. A real bird's first strong appearance at `_FEEDER_BOX`
        (never touched before in this test) still admits."""
        _run_single_occurrence(repository, _LOCATION_A_BOX, [0.120, 0.131], start_ms=0)
        _run_single_occurrence(repository, _LOCATION_A_BOX, [0.372, 0.310], start_ms=300_000)
        _run_single_occurrence(repository, _LOCATION_A_BOX, [0.200, 0.220], start_ms=600_000)

        outcome = _run_single_occurrence(repository, _FEEDER_BOX, [0.82, 0.85, 0.80], start_ms=900_000)
        assert outcome.outcome == "created"

    def test_rejected_confusor_history_does_not_grant_species_inference_any_input(
        self, repository: ProductRepository,
    ) -> None:
        """Species result: a corroboration-rejected proposal never creates a
        Visit row at all (regardless of whether this milestone's own history
        fix also touched scene-confusor bookkeeping for it), so nothing
        exists for automatic species inference to run against."""
        outcome = _run_single_occurrence(repository, _LOCATION_A_BOX, [0.120, 0.131], start_ms=0)
        assert outcome.outcome == "reject_insufficient_detector_corroboration"
        assert outcome.visit_id is None
        assert outcome.event_id is None


# ---------------------------------------------------------------------------
# Person-associated non-target reproducer. See "Person result" in the
# milestone report for the exact scope this closes (same-frame class
# contradiction) and what it does not (a pure single-class misclassification
# with no co-occurring non-animal evidence at any point -- the already-
# accepted Person-Background-False-Positive residual, unchanged).
# ---------------------------------------------------------------------------


def _person_confound_ticks() -> list:
    """Two genuine, untainted weak `animal`-class detections (the person's
    very first, uncertain appearance in frame -- realistic: a new subject's
    first instant is rarely already confidently double-detected) bracketing
    six same-frame `animal`+`person` overlapping pairs (matching v11's own
    disclosed shape: a real person mostly, but not perfectly consistently,
    decoded by MDv5 as `animal`-class at genuine strong confidence, up to
    0.858) -- realistic in that a real, several-minutes-long human presence
    is not perfectly, uniformly misclassified on every single frame."""
    return [
        (0, (0.30, None)),
        (300, (0.80, 0.85)),
        (600, (0.82, 0.83)),
        (900, (0.78, 0.86)),
        (1200, (0.86, 0.81)),
        (1500, (0.81, 0.79)),
        (1800, (0.83, 0.84)),
        (2100, (0.35, None)),
    ]


def _drive_person_confound(*, tainted: bool) -> list[TrackUpdate]:
    """`tainted=True` reproduces v11's own real shape (a co-occurring
    `person`-class detection at the identical geometry on six of the eight
    frames); `tainted=False` is the isolation control -- the identical
    confidence/timing sequence with every `person`-class detection removed,
    exactly what pre-fix code already saw (it never read non-animal
    detections at all)."""
    tracker = _tracker()
    updates: list[TrackUpdate] = []
    for offset_ms, (animal_confidence, person_confidence) in _person_confound_ticks():
        frame = _frame(offset_ms)
        detections = [_detection(frame, _PERSON_REGION_BOX, confidence=animal_confidence, label="animal", is_animal=True)]
        if tainted and person_confidence is not None:
            detections.append(
                _detection(frame, _PERSON_REGION_BOX, confidence=person_confidence, label="person", is_animal=False)
            )
        updates.extend(tracker.observe(frame, tuple(detections)).updates)
    updates.extend(_finalize(tracker))
    return updates


class TestPersonAssociatedFalseVisit:
    def test_cooccurring_person_detection_denies_the_animal_track_enough_corroboration(
        self, repository: ProductRepository,
    ) -> None:
        """Deterministic RED->GREEN for the field-confirmed v11 shape: with
        the real, same-frame co-occurring `person`-class detections present
        (matching a real, extended human presence MDv5 does not perfectly,
        uniformly misclassify), `ProviderNeutralFrameTracker.observe` now
        excludes every tainted frame's `animal` detection from ever
        corroborating a track -- leaving only the two genuine, untainted,
        never-strong detections (0.30, 0.35), which are neither consecutive
        (each isolated between excluded frames) nor sufficient in count
        (`2` does not exceed `2*1+1=3`) -- correctly rejected, never a
        wildlife Visit. Verified via `git stash` against the pre-fix
        `frame_tracker.py` in the milestone report: the identical sequence
        was `created` before this fix."""
        updates = _drive_person_confound(tainted=True)
        proposal = _assemble_one_proposal(updates, box=_PERSON_REGION_BOX)
        assert len(proposal.constituent_generation_ids) == 1

        outcome = _attempt(repository, proposal, box=_PERSON_REGION_BOX)

        assert outcome.outcome == "reject_insufficient_detector_corroboration"
        assert outcome.reason == "never_strong_and_minimal_detector_corroboration"
        assert outcome.visit_id is None

    def test_isolation_control_without_cooccurring_person_detection_still_admits(
        self, repository: ProductRepository,
    ) -> None:
        """Proves the mechanism, not an incidental artifact of the synthetic
        sequence: the *identical* confidence/timing pattern, with every
        `person`-class detection removed (as if MDv5 had never double-
        detected this specific real person -- the residual this milestone
        does *not* close, matching the already-accepted Person-Background-
        False-Positive precedent), reaches the exact same strong-detection
        bypass v11's own real false Visits used, and is admitted -- exactly
        as today's production code still behaves whenever no corroborating
        non-animal evidence exists anywhere in the same frame."""
        updates = _drive_person_confound(tainted=False)
        proposal = _assemble_one_proposal(updates, box=_PERSON_REGION_BOX)
        assert len(proposal.constituent_generation_ids) == 1

        outcome = _attempt(repository, proposal, box=_PERSON_REGION_BOX)

        assert outcome.outcome == "created"


class TestBirdPersonSpatialIndependence:
    def test_bird_still_admits_while_a_person_is_concurrently_present_elsewhere(
        self, repository: ProductRepository,
    ) -> None:
        """Mandatory positive control: a real bird at `_FEEDER_BOX` and a
        person at the spatially distant `_PERSON_REGION_BOX`, in the *same*
        frames -- no IoU overlap between the two locations, so the new
        same-frame exclusion never engages for the bird's own detections.
        No whole-frame veto: the person's mere presence anywhere in frame
        must never suppress the bird."""
        tracker = _tracker()
        updates: list[TrackUpdate] = []
        for offset_ms in (0, 300, 600, 900):
            frame = _frame(offset_ms)
            bird = _detection(frame, _FEEDER_BOX, confidence=0.55, label="animal", is_animal=True)
            person = _detection(frame, _PERSON_REGION_BOX, confidence=0.90, label="person", is_animal=False)
            updates.extend(tracker.observe(frame, (bird, person)).updates)
        updates.extend(_finalize(tracker))

        bird_generation_ids = {
            update.generation_id for update in updates if update.bounding_box == _FEEDER_BOX
        }
        assert bird_generation_ids, "the bird's own track must exist independent of the person's own, untracked detections"
        # The person is `is_animal=False` throughout -- confirms the
        # pre-existing, already-correct policy this milestone reuses (see
        # docs/person-background-false-positive-attribution-v1-report.md
        # §5-6): an explicitly-classified `person` detection never even
        # starts a track, with or without this milestone's own fix.
        assert not any(update.broad_class == "person" for update in updates)

        proposal = _assemble_one_proposal(
            [update for update in updates if update.generation_id in bird_generation_ids], box=_FEEDER_BOX,
        )
        outcome = _attempt(repository, proposal, box=_FEEDER_BOX)
        assert outcome.outcome == "created"


class TestStrongAndWeakRealBirdPreserved:
    def test_strong_real_bird_admits_unchanged(self, repository: ProductRepository) -> None:
        outcome = _run_single_occurrence(repository, _FEEDER_BOX, [0.82, 0.85, 0.80], start_ms=0)
        assert outcome.outcome == "created"

    def test_weak_real_bird_admits_via_count_based_corroboration_unchanged(
        self, repository: ProductRepository,
    ) -> None:
        outcome = _run_single_occurrence(repository, _FEEDER_BOX, [0.30, 0.35, 0.32, 0.38], start_ms=0)
        assert outcome.outcome == "created"

    def test_stationary_real_bird_survives_repeated_strong_admission_at_the_same_spot(
        self, repository: ProductRepository,
    ) -> None:
        """A real, repeatedly-visited location's own strong admissions must
        never be suspected merely because this milestone's own fix now also
        records rejected occurrences elsewhere in the Stream -- and, more
        directly, never suspected at its own location either, exactly
        matching v11's own field-proven feeder-pole result."""
        for index in range(4):
            outcome = _run_single_occurrence(
                repository, _FEEDER_BOX, [0.80 + 0.01 * index, 0.83, 0.79], start_ms=index * 300_000,
            )
            assert outcome.outcome == "created"
