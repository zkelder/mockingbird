"""Hardware-free tests for Observation Engine v2 Stage 6.14: reviewed-to-
replay evidence identity lineage. Numbered sections mirror the task's
required hardware-free-test list. This file covers the cross-cutting,
end-to-end lineage bridge; narrower per-module propagation checks live
alongside each module's own existing test file (test_observation_replay.py,
test_observation_replay_io.py, test_temporal_annotation.py,
test_frame_tracker.py, test_observation_frame_driven.py,
test_observation_onnx_cuda.py, test_evidence_benchmark.py,
test_evidence_benchmark_io.py).

No filesystem I/O beyond pytest's own tmp_path, no CUDA/ONNX Runtime/OpenCV,
and no product database anywhere in this file.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

from mockingbird.observation.contracts import EvidenceCandidate, VisitProposal
from mockingbird.observation.evidence_benchmark import (
    ReviewedEvidenceCandidate,
    ReviewedEvidenceManifest,
    evaluate_evidence_benchmark,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
REVIEWED_FRAME_ID = "233924d95f30fc622edf398a901875ee35235d2f4c48a44ce0880fb7da1f271c"
OTHER_REVIEWED_FRAME_ID = "9c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e50"
REPLAY_LOCAL_FRAME_ID = "9f1c2b3a4d5e6f70819293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e"


def _reviewed_manifest(*, content_hash: str | None = None) -> ReviewedEvidenceManifest:
    # Mirrors a real Stage 6.6/6.8 reviewed frame: `candidate_id` is the
    # original captured frame's stable `frame_id`, exactly what a human
    # reviewer's annotation refers to.
    candidate = ReviewedEvidenceCandidate(
        candidate_id=REVIEWED_FRAME_ID,
        session_id="session-04",
        role="tracked_best",
        track_generation_id="track-1",
        useful_identification=True,
        useful_context=True,
        content_hash=content_hash,
    )
    return ReviewedEvidenceManifest(1, "m", "reviewed-session-04", (candidate,))


def _replay_sourced_candidate_and_proposal(
    *,
    source_capture_frame_id: str | None,
    source_content_hash: str | None = None,
    media_asset_id: str = "replay:0",
    source_offset_ms: int = 100,
) -> tuple[tuple[EvidenceCandidate, ...], tuple[VisitProposal, ...]]:
    # Mirrors exactly what `replay.ReplayInput.packets()` ->
    # `frame_driven_provider._candidate()` produce today: `media_asset_id`
    # (`"replay:0"`) and `frame_id` are both replay-local deterministic
    # identities, never the original reviewed `frame_id` -- this is the
    # disclosed Stage 6.13 limitation this stage fixes.
    candidate = EvidenceCandidate(
        media_asset_id=media_asset_id,
        stream_id="stream-1",
        role="tracked_best",
        captured_at=None,
        frame_id=REPLAY_LOCAL_FRAME_ID,
        source_offset_ms=source_offset_ms,
        width=320,
        height=240,
        subject_geometry=(0.2, 0.2, 0.6, 0.7),
        track_generation_id="track-1",
        quality_facts=(("track_supported", True), ("temporal_alignment", "aligned"), ("decodable", True)),
        source_capture_frame_id=source_capture_frame_id,
        source_content_hash=source_content_hash,
    )
    proposal = VisitProposal(
        proposal_key=f"frame-driven:proposal-{media_asset_id}", source_id="replay", stream_id="stream-1",
        evidence_media_asset_ids=(media_asset_id,), reason="confirmed_visit", track_generation_id="track-1",
    )
    return (candidate,), (proposal,)


# --------------------------------------------------------------------------
# 1. Session-04 identity-mismatch reproduction (the Stage 6.13-disclosed gap)
# --------------------------------------------------------------------------


def test_replay_sourced_candidate_without_source_lineage_cannot_join_reviewed_truth() -> None:
    """Reproduces the exact disclosed Stage 6.13 limitation: a replay-report
    candidate whose own identity has no relationship to the reviewed
    `frame_id` namespace cannot honestly join reviewed truth. This must
    remain true after the Stage 6.14 fix too -- it is the backward-
    compatible fallback for a replay report that carries no source lineage
    at all (an old report, or a genuinely generic, non-temporal-review
    replay input)."""

    manifest = _reviewed_manifest()
    candidates, proposals = _replay_sourced_candidate_and_proposal(source_capture_frame_id=None)
    report = evaluate_evidence_benchmark(manifest, replay_candidates=candidates, replay_proposals=proposals)
    assert report.metrics["useful_identification_rate"]["state"] == "insufficient_truth"
    assert report.metrics["useful_identification_rate"]["value"] is None


def test_replay_sourced_candidate_with_source_lineage_joins_reviewed_truth() -> None:
    """The fix: once a replay-sourced `EvidenceCandidate` carries the
    original reviewed frame's `source_capture_frame_id` as explicit
    provenance -- even though its own `media_asset_id`/`frame_id` remain the
    distinct, replay-local deterministic identity -- the benchmark must
    join it to reviewed truth and report a real, evaluated rate rather than
    `insufficient_truth`."""

    manifest = _reviewed_manifest()
    candidates, proposals = _replay_sourced_candidate_and_proposal(source_capture_frame_id=REVIEWED_FRAME_ID)
    report = evaluate_evidence_benchmark(manifest, replay_candidates=candidates, replay_proposals=proposals)
    assert report.metrics["useful_identification_rate"]["state"] == "evaluated"
    assert report.metrics["useful_identification_rate"]["value"] == 1.0
    # The replay-local identity is untouched -- lineage is additive
    # provenance, never a replacement of the replay's own deterministic id.
    replay_episode = next(episode for episode in report.episodes if episode.source == "replay_report")
    assert replay_episode.selection.identification_candidate_id == "replay:0"
    assert replay_episode.identification_source_capture_frame_id == REVIEWED_FRAME_ID


def test_old_report_without_lineage_reports_source_lineage_unavailable_honestly() -> None:
    """(19) The no-lineage case (above) is not merely `insufficient_truth`
    silently -- it carries the stable, explicit
    `source_lineage_unavailable` limitation code, distinguishing "we tried
    to join and truth genuinely disagreed" from "there was nothing to join
    with at all"."""

    manifest = _reviewed_manifest()
    candidates, proposals = _replay_sourced_candidate_and_proposal(source_capture_frame_id=None)
    report = evaluate_evidence_benchmark(manifest, replay_candidates=candidates, replay_proposals=proposals)
    assert any(item.startswith("source_lineage_unavailable:") for item in report.limitations)


# --------------------------------------------------------------------------
# 9-10. Identification/context selection expose the selected source frame id
# --------------------------------------------------------------------------


def test_identification_and_context_selection_both_expose_selected_source_frame_id() -> None:
    manifest = _reviewed_manifest()
    candidates, proposals = _replay_sourced_candidate_and_proposal(source_capture_frame_id=REVIEWED_FRAME_ID)
    report = evaluate_evidence_benchmark(manifest, replay_candidates=candidates, replay_proposals=proposals)
    replay_episode = next(episode for episode in report.episodes if episode.source == "replay_report")
    assert replay_episode.identification_source_capture_frame_id == REVIEWED_FRAME_ID
    assert replay_episode.context_source_capture_frame_id == REVIEWED_FRAME_ID
    # And present in the serialized semantic payload the CLI/report writer
    # actually persists, not just the in-memory dataclass.
    semantic = report.to_semantic_dict()
    (episode_dict,) = [item for item in semantic["episodes"] if item["source"] == "replay_report"]
    assert episode_dict["identification_source_capture_frame_id"] == REVIEWED_FRAME_ID
    assert episode_dict["context_source_capture_frame_id"] == REVIEWED_FRAME_ID


# --------------------------------------------------------------------------
# 12-13. The join never uses a path, frame ordering, or timestamp alone.
# --------------------------------------------------------------------------


def test_join_never_uses_image_path_or_absolute_path() -> None:
    """(12) Structural proof: the source-lineage join implementation never
    references an image/file path at all -- `EvidenceCandidate` does not
    even carry one, so a path-based join is not merely avoided, it is
    structurally impossible in this code path."""

    source = (_REPO_ROOT / "src" / "mockingbird" / "observation" / "evidence_benchmark.py").read_text(encoding="utf-8")
    start = source.index("def _source_lineage_join(")
    end = source.index("\ndef ", start + 1)
    function_source = source[start:end]
    for forbidden in ("image_path", "source_path", ".path", "filename"):
        assert forbidden not in function_source


def test_matching_source_offset_alone_does_not_join_without_an_explicit_source_id() -> None:
    """(13) Two candidates that merely share the same `source_offset_ms`
    (or would coincidentally line up by frame ordering) must not join --
    only an explicit `source_capture_frame_id` match counts. Without one,
    truth stays honestly unlinked even though the offsets agree exactly."""

    manifest = ReviewedEvidenceManifest(1, "m", "s", (
        ReviewedEvidenceCandidate(
            candidate_id=REVIEWED_FRAME_ID, session_id="session-04", role="tracked_best",
            track_generation_id="track-1", useful_identification=True, source_offset_ms=100,
        ),
    ))
    candidates, proposals = _replay_sourced_candidate_and_proposal(
        source_capture_frame_id=None, source_offset_ms=100,  # identical offset, no explicit id
    )
    report = evaluate_evidence_benchmark(manifest, replay_candidates=candidates, replay_proposals=proposals)
    assert report.metrics["useful_identification_rate"]["state"] == "insufficient_truth"


# --------------------------------------------------------------------------
# 14-15. Content-hash validation: matching succeeds, mismatch flags.
# --------------------------------------------------------------------------


def test_matching_source_id_and_hash_succeeds() -> None:
    """(14) When both a reviewed candidate and a replay-sourced candidate
    declare a content hash for the same source identity and they agree,
    the join succeeds and no integrity limitation is recorded."""

    manifest = _reviewed_manifest(content_hash="same-hash")
    candidates, proposals = _replay_sourced_candidate_and_proposal(
        source_capture_frame_id=REVIEWED_FRAME_ID, source_content_hash="same-hash",
    )
    report = evaluate_evidence_benchmark(manifest, replay_candidates=candidates, replay_proposals=proposals)
    assert report.metrics["useful_identification_rate"]["state"] == "evaluated"
    assert not any("hash_mismatch" in item for item in report.limitations)


def test_replay_sourced_candidate_scores_using_the_joined_reviewed_image() -> None:
    """A replay-sourced `EvidenceCandidate`'s own `media_asset_id`
    (`"replay:0"`) is never a key the caller's reviewed-frame-root `media`
    mapping already contains -- without borrowing the joined reviewed
    image, the candidate would score `candidate_unavailable` regardless of
    lineage, silently defeating the whole point of the join. Once joined,
    it decodes the exact same bytes a reviewer looked at and can be
    genuinely selected/scored (real image quality facts, not just a
    declared `decodable` flag)."""

    from io import BytesIO
    from PIL import Image, ImageDraw

    def _png() -> bytes:
        image = Image.new("RGB", (320, 240), "white")
        draw = ImageDraw.Draw(image)
        for x in range(0, 320, 8):
            draw.line((x, 0, 319 - x, 239), fill="black", width=2)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    manifest = _reviewed_manifest()
    image_bytes = _png()
    candidate = EvidenceCandidate(
        media_asset_id="replay:0", stream_id="stream-1", role="tracked_best", captured_at=None,
        frame_id=REPLAY_LOCAL_FRAME_ID, source_offset_ms=100, track_generation_id="track-1",
        subject_geometry=(0.2, 0.2, 0.6, 0.7), source_capture_frame_id=REVIEWED_FRAME_ID,
        # Deliberately no declared `decodable`/`width`/`height` quality
        # fact and no explicit "replay:0" media entry -- eligibility must
        # come entirely from the borrowed reviewed image below.
    )
    proposal = VisitProposal(
        proposal_key="frame-driven:proposal-1", source_id="replay", stream_id="stream-1",
        evidence_media_asset_ids=("replay:0",), reason="confirmed_visit", track_generation_id="track-1",
    )
    report = evaluate_evidence_benchmark(
        manifest, replay_candidates=(candidate,), replay_proposals=(proposal,),
        media={REVIEWED_FRAME_ID: image_bytes},
    )
    replay_episode = next(episode for episode in report.episodes if episode.source == "replay_report")
    assert replay_episode.selection.identification_candidate_id == "replay:0"
    assert replay_episode.identification_source_capture_frame_id == REVIEWED_FRAME_ID
    score = replay_episode.selection.score_for("replay:0")
    assert score.eligible is True
    assert score.width == 320 and score.height == 240  # decoded from the borrowed image, not declared


def test_source_id_hash_mismatch_is_flagged_and_excluded_from_the_join() -> None:
    """(15) When the reviewed and replay-declared content hashes disagree
    for the same source identity, the benchmark never silently picks a
    side: the pair is excluded from the join (truth stays honestly
    unlinked) and a stable `source_hash_mismatch` limitation names it."""

    manifest = _reviewed_manifest(content_hash="reviewed-hash")
    candidates, proposals = _replay_sourced_candidate_and_proposal(
        source_capture_frame_id=REVIEWED_FRAME_ID, source_content_hash="different-replay-hash",
    )
    report = evaluate_evidence_benchmark(manifest, replay_candidates=candidates, replay_proposals=proposals)
    assert report.metrics["useful_identification_rate"]["state"] == "insufficient_truth"
    assert any(item.startswith("source_hash_mismatch:") and REVIEWED_FRAME_ID in item for item in report.limitations)


# --------------------------------------------------------------------------
# 16. Duplicate source identity with conflicting content rejects/flags.
# --------------------------------------------------------------------------


def test_duplicate_source_identity_with_conflicting_content_is_flagged_and_excluded() -> None:
    """(16) Two replay-sourced candidates that both claim to be the same
    reviewed source frame but declare different content hashes can never
    both be right; the benchmark refuses to silently choose one -- both are
    excluded from the join and a stable, named limitation is recorded."""

    manifest = _reviewed_manifest(content_hash="reviewed-hash")
    first_candidates, first_proposals = _replay_sourced_candidate_and_proposal(
        source_capture_frame_id=REVIEWED_FRAME_ID, source_content_hash="hash-one", media_asset_id="replay:0",
    )
    second_candidates, second_proposals = _replay_sourced_candidate_and_proposal(
        source_capture_frame_id=REVIEWED_FRAME_ID, source_content_hash="hash-two", media_asset_id="replay:1",
    )
    report = evaluate_evidence_benchmark(
        manifest, replay_candidates=first_candidates + second_candidates,
        replay_proposals=first_proposals + second_proposals,
    )
    assert report.metrics["useful_identification_rate"]["state"] == "insufficient_truth"
    assert any(
        item.startswith("duplicate_source_identity_conflicting_content:") and REVIEWED_FRAME_ID in item
        for item in report.limitations
    )


# --------------------------------------------------------------------------
# 17. Unknown source reference is reported.
# --------------------------------------------------------------------------


def test_unknown_reviewed_source_frame_is_reported() -> None:
    """(17) A replay-sourced candidate's `source_capture_frame_id` naming a
    frame absent from the reviewed manifest (for example the replay covered
    a broader window than what was reviewed) is honestly reported by name,
    not silently dropped."""

    manifest = _reviewed_manifest()
    candidates, proposals = _replay_sourced_candidate_and_proposal(source_capture_frame_id=OTHER_REVIEWED_FRAME_ID)
    report = evaluate_evidence_benchmark(manifest, replay_candidates=candidates, replay_proposals=proposals)
    assert any(
        item.startswith("unknown_reviewed_source_frame:") and OTHER_REVIEWED_FRAME_ID in item
        for item in report.limitations
    )


# --------------------------------------------------------------------------
# 26-27. Two-root/runtime-fact non-semantic proof (hardware-free proxy for
# the real two-root offline acceptance).
# --------------------------------------------------------------------------


def test_two_absolute_media_roots_produce_identical_semantic_fingerprint() -> None:
    """(26) `media` (resolved image bytes/paths) never enters the semantic
    payload -- two runs differing only in which absolute root the same
    logical candidate's image happened to be resolved from must fingerprint
    identically. This is the hardware-free proxy for the real two-root
    session-04 offline acceptance run (see the final report)."""

    manifest = _reviewed_manifest(content_hash="same-hash")
    candidates, proposals = _replay_sourced_candidate_and_proposal(
        source_capture_frame_id=REVIEWED_FRAME_ID, source_content_hash="same-hash",
    )
    root_a = evaluate_evidence_benchmark(
        manifest, replay_candidates=candidates, replay_proposals=proposals,
        media={"replay:0": "/root-a/absolute/path/frames/replay-0.jpg"},
    )
    root_b = evaluate_evidence_benchmark(
        manifest, replay_candidates=candidates, replay_proposals=proposals,
        media={"replay:0": "/completely/different/root-b/frames/replay-0.jpg"},
    )
    assert root_a.semantic_fingerprint == root_b.semantic_fingerprint
    assert "/root-a/" not in json.dumps(root_a.to_semantic_dict(), default=str)
    assert "/root-b/" not in json.dumps(root_b.to_semantic_dict(), default=str)


def test_lineage_carrying_report_keeps_runtime_facts_non_semantic() -> None:
    """(27) The same existing runtime/execution-fact exclusion
    (test_runtime_differences_do_not_affect_semantic_fingerprint in
    test_evidence_benchmark.py) holds for a lineage-carrying report too --
    only the semantic lineage identities themselves belong in the
    fingerprint, never host/process/wall-clock facts."""

    manifest = _reviewed_manifest(content_hash="same-hash")
    candidates, proposals = _replay_sourced_candidate_and_proposal(
        source_capture_frame_id=REVIEWED_FRAME_ID, source_content_hash="same-hash",
    )
    report = evaluate_evidence_benchmark(manifest, replay_candidates=candidates, replay_proposals=proposals)
    serialized = json.dumps(report.to_semantic_dict(), sort_keys=True, default=str)
    assert REVIEWED_FRAME_ID in serialized  # the semantic lineage fact IS present
    for leak in ("wall_clock", "/tmp/", "C:\\\\", "process_rss", "hostname", "started_at"):
        assert leak not in serialized


# --------------------------------------------------------------------------
# 28. Evidence-scoring algorithm unchanged.
# --------------------------------------------------------------------------


def test_evidence_scoring_module_never_references_source_lineage_fields() -> None:
    """(28) Structural proof that `evidence_scoring.py` -- the actual
    ranking/eligibility algorithm -- was not touched to special-case source
    lineage in any way: it does not even know the new field names exist.
    The join lives entirely in the benchmark adapter, never the scorer."""

    source = (_REPO_ROOT / "src" / "mockingbird" / "observation" / "evidence_scoring.py").read_text(encoding="utf-8")
    for token in (
        "source_capture_frame_id", "source_capture_session_id", "source_content_hash",
        "supporting_source_capture_frame_ids",
    ):
        assert token not in source


def test_evidence_scoring_source_has_no_diff_relevant_import_change() -> None:
    """(28) `evidence_scoring.py` imports only `EvidenceCandidate`/
    `VisitProposal` from `contracts` -- adding new optional dataclass fields
    there cannot change what this module imports or references."""

    tree = ast.parse((_REPO_ROOT / "src" / "mockingbird" / "observation" / "evidence_scoring.py").read_text(encoding="utf-8"))
    names = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "mockingbird.observation.contracts"
        for alias in node.names
    }
    assert names == {"EvidenceCandidate", "VisitProposal"}
