"""Stage 7 offline acceptance against real reviewed/replay fixtures (see
"Offline acceptance" in docs/candidate-visit-authority-contract.md).

Reuses already-produced, real-CUDA-verified Stage 6.16 `replay-report.json`
recordings (attempt-2 hard negative, attempt-3 sustained visit, session-03,
session-04) exactly the way `visit_episode_assembler.assemble_visit_episode_
report`'s own real acceptance already established -- rebuilding real
`TrackUpdate`/`EvidenceCandidate` facts from an already-produced report and
running the *unmodified* `build_tracklets`/`assemble_visit_episodes` over
them, never re-running detection/tracking and never requiring CUDA hardware
in this environment. Every resulting `AssembledVisitProposal` is then run
through the real Stage 7 pipeline against an isolated `tmp_path` SQLite
database -- never the product database.

This data lives under `data/field-acceptance/` (local-only, gitignored, not
committed -- see AGENTS.md "Generated media, datasets, exports, caches,
model artifacts, and checkpoints stay under ignored local paths"). Every
test here skips gracefully, matching the established
`tests/test_burst_scheduler_replay.py::_real_session_available` convention,
when that local data is not present on this checkout.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mockingbird.observation.candidate_visit_adapter import CandidateVisitAuthorityAdapter
from mockingbird.observation.candidate_visit_authority import AuthorityLimits, ObservationAuthorityMode
from mockingbird.observation.contracts import EvidenceCandidate, TrackUpdate
from mockingbird.observation.evidence_benchmark_io import load_replay_report_document
from mockingbird.observation.visit_episode_assembler import (
    AssembledVisitProposal,
    Tracklet,
    assemble_visit_episodes,
    build_tracklets,
)
from mockingbird.repository.product_repository import ProductRepository

REPORTS_ROOT = Path("data/field-acceptance/2026-08-07-stage6.16-sustained-visit-continuity")
_SESSION_REPORTS = {
    "attempt-2": REPORTS_ROOT / "attempt-2-after" / "replay-report.json",
    "attempt-3": REPORTS_ROOT / "attempt-3-after" / "replay-report.json",
    "session-03": REPORTS_ROOT / "session-03-after" / "replay-report.json",
    "session-04": REPORTS_ROOT / "session-04-after" / "replay-report.json",
}
STREAM_ID = "stream-backyard-feeder"
NOW = datetime(2026, 8, 8, 12, 0, 0, tzinfo=UTC)
# A trial-realistic bound: proves boundedness against real data (including
# the hard-negative session's own genuine clutter volume) rather than an
# effectively-unlimited default.
ACCEPTANCE_LIMITS = AuthorityLimits(max_candidates_per_session=5, max_candidates_per_hour=20)
SYNTHETIC_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32 + b"\xff\xd9"


def _real_session_available(name: str) -> bool:
    return _SESSION_REPORTS[name].is_file()


@dataclass(frozen=True)
class LoadedSession:
    proposals: tuple[AssembledVisitProposal, ...]
    evidence_candidates: tuple[EvidenceCandidate, ...]
    track_updates_count: int
    raw_confirmed_generations: int


def _track_update_from_dict(raw: dict) -> TrackUpdate:
    box = raw.get("bounding_box")
    return TrackUpdate(
        track_id=raw["track_id"],
        generation_id=raw["generation_id"],
        captured_at=datetime.fromisoformat(raw["captured_at"]),
        status=raw["status"],
        lifecycle_state=raw.get("lifecycle_state", "tentative"),
        frame_id=raw.get("frame_id"),
        source_offset_ms=raw.get("source_offset_ms"),
        broad_class=raw.get("broad_class"),
        bounding_box=tuple(box) if box else None,
        supporting_frame_ids=tuple(raw.get("supporting_frame_ids") or ()),
        detector_confirmation_count=raw.get("detector_confirmation_count", 0),
        tracker_support_count=raw.get("tracker_support_count", 0),
        confidence=raw.get("confidence"),
        detector_provenance=raw.get("detector_provenance"),
        tracker_provenance=raw.get("tracker_provenance"),
        terminal_reason=raw.get("terminal_reason"),
        supporting_source_capture_frame_ids=tuple(raw.get("supporting_source_capture_frame_ids") or ()),
        weak_detector_support_count=raw.get("weak_detector_support_count", 0),
        support_state=raw.get("support_state", "temporarily_lost"),
        detector_ran=raw.get("detector_ran", False),
        ambiguous_start=raw.get("ambiguous_start", False),
    )


def _evidence_candidate_from_dict(raw: dict) -> EvidenceCandidate:
    geometry = raw.get("subject_geometry")
    return EvidenceCandidate(
        media_asset_id=raw["media_asset_id"],
        stream_id=raw.get("stream_id", STREAM_ID),
        role=raw.get("role", "context"),
        captured_at=datetime.fromisoformat(raw["captured_at"]) if raw.get("captured_at") else None,
        frame_id=raw.get("frame_id"),
        source_offset_ms=raw.get("source_offset_ms"),
        width=raw.get("width"),
        height=raw.get("height"),
        subject_geometry=tuple(geometry) if geometry else None,
        track_generation_id=raw.get("track_generation_id"),
        detector_provenance=raw.get("detector_provenance"),
        tracker_provenance=raw.get("tracker_provenance"),
        quality_facts=tuple(tuple(pair) for pair in raw.get("quality_facts") or ()),
        temporary=raw.get("temporary", True),
        shadow_only=raw.get("shadow_only", True),
        source_capture_frame_id=raw.get("source_capture_frame_id"),
        source_content_hash=raw.get("source_content_hash"),
    )


def _load_real_session(name: str) -> LoadedSession:
    document = load_replay_report_document(_SESSION_REPORTS[name])
    track_updates = tuple(_track_update_from_dict(item) for item in document.get("track_updates", ()))
    evidence_candidates = tuple(
        _evidence_candidate_from_dict(item) for item in document.get("evidence_candidates", ())
    )
    evidence_by_generation: dict[str, list[str]] = {}
    for candidate in evidence_candidates:
        if candidate.track_generation_id:
            evidence_by_generation.setdefault(candidate.track_generation_id, []).append(candidate.media_asset_id)
    tracklets = build_tracklets(
        track_updates,
        stream_id=STREAM_ID,
        evidence_candidate_ids_by_generation={key: tuple(value) for key, value in evidence_by_generation.items()},
    )
    proposals = assemble_visit_episodes(tracklets).proposals
    raw_confirmed = int(document.get("metrics", {}).get("tracks_confirmed", {}).get("value", len(tracklets)))
    return LoadedSession(proposals, evidence_candidates, len(track_updates), raw_confirmed)


def _repository(tmp_path: Path) -> ProductRepository:
    return ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")


def _run_candidate_authority(
    repository: ProductRepository, session: LoadedSession,
) -> list:
    """Run every assembled proposal from one real session through the real
    Stage 7 pipeline, in start-time order (the order a live/replay pass
    would actually observe them), using synthetic evidence bytes keyed by
    whichever candidate the scorer actually selects (this acceptance run
    proves the authority/lineage/bounding pipeline against real proposal
    shapes; real JPEG byte handling is already proven in
    tests/test_candidate_visit_adapter.py)."""

    repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit,
        stream_id=STREAM_ID,
        now=NOW,
        max_candidates_per_session=ACCEPTANCE_LIMITS.max_candidates_per_session,
        max_candidates_per_hour=ACCEPTANCE_LIMITS.max_candidates_per_hour,
    )
    adapter = CandidateVisitAuthorityAdapter(
        repository, detector_provenance="md-v5a", tracker_provenance="spatial-frame-tracker-v1",
        provider_key="frame-driven-onnx-cuda",
    )
    candidates_by_id = {item.media_asset_id: item for item in session.evidence_candidates}
    outcomes = []
    for index, proposal in enumerate(sorted(session.proposals, key=lambda item: item.start_offset_ms)):
        relevant_candidates = tuple(
            candidates_by_id[media_id] for media_id in proposal.evidence_candidate_ids if media_id in candidates_by_id
        )
        evidence_bytes = {candidate.media_asset_id: SYNTHETIC_JPEG for candidate in relevant_candidates}
        outcome = adapter.attempt_candidate(
            proposal, evidence_candidates=relevant_candidates, evidence_bytes=evidence_bytes,
            observed_at=NOW + __import__("datetime").timedelta(milliseconds=index),
        )
        outcomes.append(outcome)
    return outcomes


# --- attempt-2: hard negative ------------------------------------------------


@pytest.mark.skipif(not _real_session_available("attempt-2"), reason="real attempt-2 recorded report not present on this checkout")
def test_real_attempt2_hard_negative_candidates_remain_bounded_and_needs_review(tmp_path: Path) -> None:
    session = _load_real_session("attempt-2")
    assert session.proposals  # the hard-negative session genuinely has confirmed clutter tracklets
    repository = _repository(tmp_path)
    try:
        outcomes = _run_candidate_authority(repository, session)
        created = [outcome for outcome in outcomes if outcome.created]
        # Bounded: the session limit -- not any species/false-positive
        # judgment Stage 7 never makes -- is what caps hard-negative clutter.
        # This real hard-negative session assembles well more than the
        # bound (20 proposals against a limit of 5); every outcome is
        # accounted for by an honest, stable reason code, never silently
        # dropped.
        assert len(created) <= ACCEPTANCE_LIMITS.max_candidates_per_session
        allowed_reasons = {
            "created", "blocked_session_limit", "blocked_hourly_limit",
            "blocked_missing_evidence", "blocked_invalid_lineage", "blocked_ambiguous_boundary",
            # Scene confusor suspicion (see docs/scene-confusor-suspicion-
            # contract.md): a real, honest, stable outcome this exact
            # hard-negative session's own recurring clutter can legitimately
            # reach now -- added to the allow-list, not asserted to fire,
            # since whether it actually does depends on this session's own
            # real recurrence/spread history.
            "blocked_scene_confusor_suspected",
        }
        assert {outcome.outcome for outcome in outcomes} <= allowed_reasons

        with repository.session_factory() as session_handle:
            from sqlalchemy import func, select

            from mockingbird.repository.product_repository import ReviewLabelModel, VisitModel

            review_label_baseline = session_handle.scalar(select(func.count(ReviewLabelModel.id)))
            assert review_label_baseline == 1  # only the demo seed's own label -- Stage 7 added none
            for outcome in created:
                visit = session_handle.get(VisitModel, outcome.visit_id)
                assert visit.review_status == "needs_review"
                assert visit.reviewed_label is None
    finally:
        repository.close()


# --- attempt-3: sustained visit ---------------------------------------------


@pytest.mark.skipif(not _real_session_available("attempt-3"), reason="real attempt-3 recorded report not present on this checkout")
def test_real_attempt3_sustained_visit_gets_bounded_candidate_count(tmp_path: Path) -> None:
    session = _load_real_session("attempt-3")
    assert session.proposals
    repository = _repository(tmp_path)
    try:
        outcomes = _run_candidate_authority(repository, session)
        created = [outcome for outcome in outcomes if outcome.created]
        assert len(created) <= ACCEPTANCE_LIMITS.max_candidates_per_session
        # The Stage 6.19 assembler's entire purpose is consolidating a
        # sustained visit's raw tracker fragments; the number of assembled
        # proposals it produced should already be far below the raw
        # confirmed-generation count this real session is known to fragment
        # into (dozens, per docs/sustained-visit-continuity-contract.md).
        assert len(session.proposals) < session.raw_confirmed_generations
        for outcome in created:
            assert outcome.outcome == "created"
    finally:
        repository.close()


# --- session-04: close appearances stay separate ----------------------------


@pytest.mark.skipif(not _real_session_available("session-04"), reason="real session-04 recorded report not present on this checkout")
def test_real_session04_close_appearances_remain_separate_when_assembler_separates_them(tmp_path: Path) -> None:
    session = _load_real_session("session-04")
    assert session.proposals
    repository = _repository(tmp_path)
    try:
        outcomes = _run_candidate_authority(repository, session)
        created_ids = {outcome.proposal_id for outcome in outcomes if outcome.created}
        blocked_ambiguous = {outcome.proposal_id for outcome in outcomes if outcome.outcome == "blocked_ambiguous_boundary"}

        # The assembler's own boundary decisions are authoritative and
        # unmodified by Stage 7: whatever it kept separate remains as
        # multiple distinct proposals here, never silently re-merged by
        # this stage. A known, previously-disclosed limitation (Stage
        # 6.16's widened gap tolerance introduced one real incorrect merge
        # in this exact session -- see docs/tracklet-visit-assembly-
        # contract.md) is not hidden: if it produced an unusually long
        # single proposal, that proposal's own `limitation_facts` and span
        # remain fully visible in the ledger, not suppressed.
        assert len(session.proposals) > 1
        with repository.session_factory() as session_handle:
            from mockingbird.repository.product_repository import ObservationCandidateVisitModel

            for proposal_id in created_ids:
                ledger = session_handle.get(ObservationCandidateVisitModel, proposal_id)
                assert ledger is not None
                assert ledger.start_offset_ms <= ledger.end_offset_ms
        # Every candidate-worthy proposal is either created (bounded) or
        # explicitly, honestly accounted for (ambiguous/rate-limited) --
        # never silently dropped.
        accounted_for = created_ids | blocked_ambiguous | {
            outcome.proposal_id for outcome in outcomes
            if outcome.outcome in {
                "blocked_session_limit", "blocked_hourly_limit", "blocked_invalid_lineage",
                "blocked_missing_evidence",
                # Scene confusor suspicion (see docs/scene-confusor-
                # suspicion-contract.md): one more honest, stable outcome
                # code this real session can now legitimately reach.
                "blocked_scene_confusor_suspected",
            }
        }
        assert accounted_for == {proposal.proposal_id for proposal in session.proposals}
    finally:
        repository.close()


# --- session-03: no reviewed truth created -----------------------------------


@pytest.mark.skipif(not _real_session_available("session-03"), reason="real session-03 recorded report not present on this checkout")
def test_real_session03_creates_no_reviewed_truth(tmp_path: Path) -> None:
    session = _load_real_session("session-03")
    repository = _repository(tmp_path)
    try:
        _run_candidate_authority(repository, session)
        with repository.session_factory() as session_handle:
            from sqlalchemy import func, select

            from mockingbird.repository.product_repository import ReviewLabelModel, VisitModel

            reviewed_count = session_handle.scalar(
                select(func.count(VisitModel.id)).where(VisitModel.review_status == "reviewed")
            )
            assert reviewed_count == 1  # exactly the demo-seed graph's own pre-existing reviewed visit
            # Only the demo-seed graph's own pre-existing reviewed visit (if
            # any) -- Stage 7 itself creates zero reviewed truth regardless
            # of how many candidates it created.
            label_count = session_handle.scalar(select(func.count(ReviewLabelModel.id)))
            assert label_count == 1  # unchanged demo-seed baseline
    finally:
        repository.close()


# --- Stage 6.19 synthetic assembler scenarios --------------------------------


FIXTURES = Path("tests/fixtures/observation_stage619")


def _load_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _tracklet_from_fixture(data: dict, *, stream_id: str) -> Tracklet:
    start_box = tuple(data["start_bounding_box"])
    end_box = tuple(data["end_bounding_box"])
    envelope = (
        min(start_box[0], end_box[0]), min(start_box[1], end_box[1]),
        max(start_box[2], end_box[2]), max(start_box[3], end_box[3]),
    )
    return Tracklet(
        generation_id=data["generation_id"],
        stream_id=stream_id,
        broad_class=data.get("broad_class", "animal"),
        start_offset_ms=data["start_offset_ms"],
        end_offset_ms=data["end_offset_ms"],
        start_bounding_box=start_box,
        end_bounding_box=end_box,
        geometry_envelope=envelope,
        terminal_reason=data["terminal_reason"],
        track_ids=(f"{data['generation_id']}-track",),
        connection_segment_ids=tuple(data.get("connection_segment_ids", ())),
        negative_detector_frame_count=data.get("negative_detector_frame_count", 0),
        detector_skipped_frame_count=data.get("detector_skipped_frame_count", 0),
        last_strong_detector_offset_ms=data.get("last_strong_detector_offset_ms"),
        zone_id=data.get("zone_id"),
        # Stage 6.19's own committed fixture was built for boundary-decision
        # coverage and carries no source-capture lineage; synthesize a
        # plausible one here (never blank) so this scenario can exercise
        # Stage 7's lineage requirement at all -- a fixture proposal with
        # *no* augmentation would otherwise, correctly, always be blocked
        # `blocked_invalid_lineage`, which would prove nothing about the
        # rest of the pipeline.
        source_capture_frame_ids=(f"{data['generation_id']}-source-frame",),
    )


def _fixture_scenario(name: str) -> tuple[dict, tuple[Tracklet, ...]]:
    catalog = _load_json("tracklet_scenarios.json")
    scenario = catalog["scenarios"][name]
    tracklets = tuple(_tracklet_from_fixture(item, stream_id=STREAM_ID) for item in scenario["tracklets"])
    return scenario, tracklets


def test_stage619_synthetic_long_visit_fragmented_scenario_creates_bounded_candidates(tmp_path: Path) -> None:
    _scenario, tracklets = _fixture_scenario("long_visit_fragmented_into_many_tracklets")
    assembly = assemble_visit_episodes(tracklets)
    repository = _repository(tmp_path)
    try:
        repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)
        adapter = CandidateVisitAuthorityAdapter(repository)
        outcomes = [
            adapter.attempt_candidate(proposal, evidence_candidates=(), evidence_bytes={}, observed_at=NOW)
            for proposal in assembly.proposals
        ]
        # No evidence bytes supplied for this synthetic scenario -> every
        # attempt fails safely (missing evidence), never fabricating a
        # candidate -- proves the missing-evidence guard holds even for a
        # scenario purpose-built to fragment heavily.
        assert all(outcome.outcome == "blocked_missing_evidence" for outcome in outcomes)
    finally:
        repository.close()


def test_stage619_synthetic_two_separate_appearances_stay_separate_candidates(tmp_path: Path) -> None:
    """The assembler's own boundary decision for this scenario is
    authoritative and untouched by Stage 7: whether it judged the two
    appearances confidently separate (`keep_separate`/`incompatible`,
    yielding two independently *creatable* candidates) or genuinely
    ambiguous (conservatively blocked per "Ambiguity policy" in the
    contract doc), Stage 7 must never silently merge them into one Visit,
    and must never silently drop either without an honest reason code."""

    _scenario, tracklets = _fixture_scenario("two_separate_appearances_10_20s_apart")
    assembly = assemble_visit_episodes(tracklets)
    assert len(assembly.proposals) >= 2  # the assembler itself must not have merged them
    repository = _repository(tmp_path)
    try:
        repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)
        adapter = CandidateVisitAuthorityAdapter(repository)
        evidence_item = EvidenceCandidate(
            media_asset_id="synthetic:evidence", stream_id=STREAM_ID, role="identification", captured_at=NOW,
            quality_facts=(("decodable", True), ("temporal_alignment", "aligned")),
        )
        created_visit_ids = set()
        outcomes = []
        for index, proposal in enumerate(assembly.proposals):
            candidate = evidence_item.__class__(**{**evidence_item.__dict__, "media_asset_id": f"synthetic:evidence-{index}"})
            outcome = adapter.attempt_candidate(
                proposal, evidence_candidates=(candidate,),
                evidence_bytes={candidate.media_asset_id: SYNTHETIC_JPEG}, observed_at=NOW,
            )
            outcomes.append(outcome)
            assert outcome.outcome in {"created", "blocked_ambiguous_boundary"}
            if outcome.created:
                created_visit_ids.add(outcome.visit_id)
        # Two genuinely separate appearances must never collapse into one
        # candidate Visit, however each was individually classified.
        assert len(created_visit_ids) == sum(1 for outcome in outcomes if outcome.created)
    finally:
        repository.close()
