"""Hardware-free tests for the Stage-3 Tranche A readiness/accounting
report (`scripts/report_wildlife_stage3_readiness.py`). Never declares
readiness from a bare review-count total -- see the module docstring.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from mockingbird.observation.temporal_annotation import (
    AnnotationSet,
    BoxAnnotation,
    FrameAnnotation,
    Provenance,
)


def _module():
    path = Path("scripts/report_wildlife_stage3_readiness.py")
    spec = importlib.util.spec_from_file_location("report_wildlife_stage3_readiness", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tranche_payload(*, lane_targets: dict[str, int], frame_specs: list[dict]) -> dict:
    total = sum(lane_targets.values())
    return {
        "tranche_id": "test-tranche",
        "lane_targets": lane_targets,
        "split": {"train_frame_count": round(total * 0.75), "validation_frame_count": round(total * 0.25)},
        "contamination": {"passed": True},
        "frames": frame_specs,
    }


def _frame_spec(frame_id: str, *, lane: str, split: str, session: str) -> dict:
    return {"frame_id": frame_id, "stage3_target_lane": lane, "split_candidate": split, "capture_session_id": session}


def _provenance() -> Provenance:
    return Provenance("zkelder", "2026-08-12T00:00:00+00:00", "session-1", "full_frame_inspection")


def test_readiness_report_counts_unreviewed_as_remaining() -> None:
    module = _module()
    tranche = _tranche_payload(
        lane_targets={"lane_a": 2},
        frame_specs=[_frame_spec("f1", lane="lane_a", split="local_train_candidate", session="s1"),
                     _frame_spec("f2", lane="lane_a", split="local_train_candidate", session="s1")],
    )
    annotations = AnnotationSet(1, "session", "fp", (FrameAnnotation("f1"), FrameAnnotation("f2")))
    report = module.build_readiness_report(tranche, annotations)
    assert report["reviewed"] == 0
    assert report["remaining"] == 2
    assert report["stage3_training_ready"] is False


def test_readiness_report_counts_usable_positive_and_negative() -> None:
    module = _module()
    tranche = _tranche_payload(
        lane_targets={"lane_a": 2},
        frame_specs=[_frame_spec("pos", lane="lane_a", split="local_train_candidate", session="s1"),
                     _frame_spec("neg", lane="lane_a", split="local_train_candidate", session="s1")],
    )
    annotations = AnnotationSet(1, "session", "fp", (
        FrameAnnotation("pos", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.2, 0.2)),), provenance=_provenance()),
        FrameAnnotation("neg", whole_frame_truth="no", provenance=_provenance()),
    ))
    report = module.build_readiness_report(tranche, annotations)
    assert report["positives_usable"] == 1
    assert report["negatives_usable"] == 1
    assert report["boxes"] == 1
    assert report["reviewed"] == 2
    assert report["remaining"] == 0


def test_readiness_report_ambiguous_and_yes_but_unscorable_are_not_usable() -> None:
    module = _module()
    tranche = _tranche_payload(
        lane_targets={"lane_a": 3},
        frame_specs=[
            _frame_spec("amb", lane="lane_a", split="local_train_candidate", session="s1"),
            _frame_spec("unscorable", lane="lane_a", split="local_train_candidate", session="s1"),
            _frame_spec("neg", lane="lane_a", split="local_train_candidate", session="s1"),
        ],
    )
    annotations = AnnotationSet(1, "session", "fp", (
        FrameAnnotation("amb", whole_frame_truth="ambiguous", provenance=_provenance()),
        FrameAnnotation("unscorable", whole_frame_truth="yes", yes_but_unscorable=True, provenance=_provenance()),
        FrameAnnotation("neg", whole_frame_truth="no", provenance=_provenance()),
    ))
    report = module.build_readiness_report(tranche, annotations)
    assert report["ambiguous"] == 1
    assert report["yes_but_unscorable"] == 1
    assert report["positives_usable"] == 0
    assert report["negatives_usable"] == 1
    assert report["usable_total"] == 1


def test_readiness_never_declares_ready_from_total_review_count_alone() -> None:
    """Every frame reviewed as a plain 'no' still must not be called ready
    unless the lane/split/generic-sufficiency bars are all independently met."""

    module = _module()
    lane_targets = {"lane_a": 100}
    frame_specs = [_frame_spec(f"f{i}", lane="lane_a", split="local_train_candidate", session="s1") for i in range(100)]
    tranche = _tranche_payload(lane_targets=lane_targets, frame_specs=frame_specs)
    # All 100 reviewed, all negative, all one session -> total count is high
    # but scene-group/session diversity is not.
    frames = tuple(FrameAnnotation(f"f{i}", whole_frame_truth="no", provenance=_provenance()) for i in range(100))
    annotations = AnnotationSet(1, "session", "fp", frames)
    report = module.build_readiness_report(tranche, annotations)
    assert report["reviewed"] == 100
    assert report["stage3_training_ready"] is False
    assert any("scene/camera" in reason or "capture session" in reason for reason in report["not_ready_reasons"])


def test_readiness_ready_once_every_lane_split_and_generic_bar_clears() -> None:
    module = _module()
    lane_targets = {"lane_a": 10, "lane_b": 10}
    frame_specs = []
    for lane in ("lane_a", "lane_b"):
        for session in range(3):
            for index in range(10):
                frame_specs.append(_frame_spec(
                    f"{lane}-{session}-{index}", lane=lane,
                    split="local_validation_candidate" if session == 0 else "local_train_candidate",
                    session=f"session-{lane}-{session}",
                ))
    tranche = _tranche_payload(lane_targets=lane_targets, frame_specs=frame_specs)
    tranche["split"] = {"train_frame_count": 40, "validation_frame_count": 20}
    frames = []
    for spec in frame_specs:
        truth = "yes" if int(spec["frame_id"][-1]) % 2 == 0 else "no"
        boxes = (BoxAnnotation((0.1, 0.1, 0.2, 0.2)),) if truth == "yes" else ()
        frames.append(FrameAnnotation(spec["frame_id"], whole_frame_truth=truth, boxes=boxes, provenance=_provenance()))
    annotations = AnnotationSet(1, "session", "fp", tuple(frames))
    report = module.build_readiness_report(tranche, annotations)
    assert report["stage3_training_ready"] is True
    assert report["not_ready_reasons"] == []


def test_readiness_report_aggregates_difficulty_tags_and_box_distance() -> None:
    module = _module()
    tranche = _tranche_payload(
        lane_targets={"lane_a": 1},
        frame_specs=[_frame_spec("f1", lane="lane_a", split="local_train_candidate", session="s1")],
    )
    box = BoxAnnotation((0.1, 0.1, 0.2, 0.2), distance="far")
    annotations = AnnotationSet(1, "session", "fp", (
        FrameAnnotation("f1", whole_frame_truth="yes", boxes=(box,), difficulty_tags=("very_small", "far"), provenance=_provenance()),
    ))
    report = module.build_readiness_report(tranche, annotations)
    assert report["difficulty_tag_distribution"] == {"far": 1, "very_small": 1}
    assert report["box_distance_distribution"] == {"far": 1}


def test_readiness_report_reflects_failed_contamination_check() -> None:
    module = _module()
    tranche = _tranche_payload(
        lane_targets={"lane_a": 1},
        frame_specs=[_frame_spec("f1", lane="lane_a", split="local_train_candidate", session="s1")],
    )
    tranche["contamination"] = {"passed": False}
    annotations = AnnotationSet(1, "session", "fp", (FrameAnnotation("f1"),))
    report = module.build_readiness_report(tranche, annotations)
    assert report["contamination_passed"] is False
    assert report["stage3_training_ready"] is False
    assert any("contamination" in reason for reason in report["not_ready_reasons"])
