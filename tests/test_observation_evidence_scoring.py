from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from mockingbird.observation.contracts import EvidenceCandidate, VisitProposal
from mockingbird.observation.evidence_scoring import (
    EvidenceScoringBounds,
    score_proposal_evidence,
)


def _png(*, sharp: bool = True, dark: bool = False) -> bytes:
    image = Image.new("RGB", (320, 240), "black" if dark else "white")
    if sharp:
        draw = ImageDraw.Draw(image)
        for x in range(0, 320, 8):
            draw.line((x, 0, 319 - x, 239), fill="black" if not dark else "white", width=2)
    else:
        image = image.filter(ImageFilter.GaussianBlur(12))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _candidate(
    candidate_id: str,
    role: str,
    *,
    offset: int = 100,
    box: tuple[float, float, float, float] | None = (0.2, 0.2, 0.6, 0.7),
    width: int = 320,
    height: int = 240,
    facts: tuple[tuple[str, object], ...] = (),
) -> EvidenceCandidate:
    return EvidenceCandidate(
        candidate_id, "stream", role, None, candidate_id, offset, width, height,
        box, "track-1", "detector", "tracker", facts,
    )


def _proposal(*candidate_ids: str) -> VisitProposal:
    return VisitProposal(
        "proposal", "shadow", "stream", tuple(candidate_ids), "confirmed_visit",
        0, 500, track_generation_id="track-1", supporting_frame_ids=("tracked",),
    )


def test_clear_tracked_frame_outranks_late_empty_burst() -> None:
    tracked = _candidate("tracked", "tracked_best", facts=(("track_supported", True),))
    burst = _candidate("burst", "high_resolution_burst", width=1200, height=900, facts=(
        ("temporal_alignment", "late"), ("subject_visible", False),
    ))
    result = score_proposal_evidence(
        _proposal("tracked", "burst"), (tracked, burst),
        media={"tracked": _png(), "burst": _png()},
    )
    assert result.identification_candidate_id == "tracked"
    assert "burst_subject_unverified" in result.score_for("burst").reason_codes


def test_sharp_contained_supported_burst_can_outrank_analysis_frame() -> None:
    tracked = _candidate("tracked", "tracked_best", width=320, height=240, facts=(
        ("track_supported", True), ("sharpness", "usable"),
    ))
    burst = _candidate("burst", "high_resolution_burst", width=1600, height=1200, facts=(
        ("track_supported", True), ("temporal_alignment", "aligned"),
        ("track_active_at_capture", True), ("sharpness", "sharp"),
    ))
    result = score_proposal_evidence(
        _proposal("tracked", "burst"), (tracked, burst),
        media={"tracked": _png(sharp=False), "burst": _png()},
    )
    assert result.identification_candidate_id == "burst"
    assert "high_resolution_detail" in result.score_for("burst").reason_codes


def test_clipped_or_blurred_high_resolution_candidate_loses_but_is_retained() -> None:
    tracked = _candidate("tracked", "tracked_best", facts=(("track_supported", True),))
    clipped = _candidate("clipped", "high_resolution_burst", box=(0.0, 0.2, 0.4, 0.8), facts=(
        ("track_supported", True), ("temporal_alignment", "aligned"),
    ))
    blurred = _candidate("blurred", "high_resolution_burst", width=1200, height=900, facts=(
        ("track_supported", True), ("temporal_alignment", "aligned"), ("sharpness", "blurred"),
    ))
    result = score_proposal_evidence(
        _proposal("tracked", "clipped", "blurred"), (tracked, clipped, blurred),
        media={item: _png() for item in ("tracked", "clipped", "blurred")},
    )
    assert result.identification_candidate_id == "tracked"
    assert {score.candidate_id for score in result.candidate_scores} == {"tracked", "clipped", "blurred"}
    assert "subject_edge_clipped" in result.score_for("clipped").reason_codes
    assert "image_blurred" in result.score_for("blurred").reason_codes


def test_identification_and_context_are_selected_separately_and_deterministically() -> None:
    identification = _candidate("id", "tracked_best", facts=(("track_supported", True),))
    context = _candidate("context", "pretrigger", box=None, facts=(("decodable", True),))
    first = score_proposal_evidence(
        _proposal("context", "id", "id"), (context, identification, identification),
        media={"context": _png(), "id": _png()},
    )
    second = score_proposal_evidence(
        _proposal("id", "context"), (identification, context),
        media={"context": _png(), "id": _png()},
    )
    assert first.identification_candidate_id == "id"
    assert first.context_candidate_id == "context"
    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert len(first.candidate_scores) == 2


def test_bounds_and_no_useful_evidence_are_explicit() -> None:
    candidates = tuple(
        _candidate(f"candidate-{index:02d}", "alternate", facts=(("subject_visible", False),))
        for index in range(8)
    )
    result = score_proposal_evidence(
        _proposal(*(item.media_asset_id for item in candidates)), candidates,
        media={item.media_asset_id: _png() for item in candidates},
        bounds=EvidenceScoringBounds(max_candidates=4, max_decoded_images=2),
    )
    assert len(result.candidate_scores) == 4
    assert result.decoded_images_evaluated == 2
    assert result.no_useful_evidence is True
    assert "candidate_limit_reached" in result.limitations


def test_privacy_masked_unavailable_and_too_small_candidates_are_not_selected() -> None:
    masked = _candidate("masked", "tracked_best", facts=(("privacy_masked", True),))
    missing = _candidate("missing", "high_resolution_burst")
    tiny = _candidate("tiny", "alternate", box=(0.2, 0.2, 0.205, 0.205), facts=(("decodable", True),))
    result = score_proposal_evidence(
        _proposal("masked", "missing", "tiny"), (masked, missing, tiny), media={"masked": _png()},
    )
    assert result.no_useful_evidence is True
    assert "candidate_unavailable" in result.score_for("missing").reason_codes
    assert "subject_too_small" in result.score_for("tiny").reason_codes
    assert "privacy_masked" in result.score_for("masked").reason_codes


def test_scoring_uses_no_species_or_model_inference_contract() -> None:
    source = __import__("inspect").getsource(score_proposal_evidence)
    assert "species" not in source.lower()
    assert "bioclip" not in source.lower()


def test_evidence_from_a_different_track_generation_is_excluded() -> None:
    foreign = EvidenceCandidate(
        "foreign", "stream", "high_resolution_burst", None, "foreign", 100, 1600, 1200,
        (0.2, 0.2, 0.6, 0.7), "other-track", "detector", "tracker",
        (("track_supported", True), ("temporal_alignment", "aligned")),
    )
    result = score_proposal_evidence(
        _proposal("foreign"), (foreign,), media={"foreign": _png()},
    )
    assert result.identification_candidate_id is None
    assert result.context_candidate_id is None
    assert result.no_useful_evidence is True
    assert result.candidate_scores == ()


def test_alternate_candidates_are_bounded() -> None:
    candidates = tuple(
        _candidate(f"alt-{index:02d}", "alternate", facts=(("track_supported", True),))
        for index in range(6)
    )
    result = score_proposal_evidence(
        _proposal(*(item.media_asset_id for item in candidates)), candidates,
        media={item.media_asset_id: _png() for item in candidates},
        bounds=EvidenceScoringBounds(max_alternates=2),
    )
    assert len(result.alternate_candidate_ids) == 2


def test_evidence_scoring_module_has_structural_no_write_boundary() -> None:
    source = Path("src/mockingbird/observation/evidence_scoring.py").read_text(encoding="utf-8")
    forbidden = (
        "mockingbird.db", "mockingbird.repositories", "ReviewLabel", "MotionEvidence",
        "StreamMonitoringPolicy", "LiveCameraSession",
    )
    assert not any(token in source for token in forbidden)
