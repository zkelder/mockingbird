#!/usr/bin/env python3
"""Build a deterministic 2,000-frame local wildlife correction queue.

Detector and agent outputs influence ordering only. They never become labels:
every queued positive candidate requires human whole-frame confirmation and
human boxes, and every negative candidate requires independent full-frame
inspection before it is training eligible.
"""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterable

from mockingbird.training.wildlife import (
    WildlifeTrainingError,
    canonical_fingerprint,
    sha256_file,
)

SEED = 260812
LANE_QUOTAS = {
    "likely_positive_requires_human_boxes": 1_000,
    "static_clutter_negative_candidate": 750,
    "weather_lighting_negative_candidate": 250,
}


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument(
        "--holdout-manifest",
        type=Path,
        default=Path("data/evaluations/detector-promotion-v1/corpus-manifest.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "data/training/wildlife-stage2/local-correction-queue.json"
        ),
    )
    parser.add_argument("--seed", type=int, default=SEED)
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise WildlifeTrainingError(f"queue_input_unreadable:{path}") from error
    if not isinstance(payload, dict):
        raise WildlifeTrainingError(f"queue_input_invalid:{path}")
    return payload


def _stable_hash(*parts: object, seed: int) -> str:
    return sha256(
        ":".join([str(seed), *(str(part) for part in parts)]).encode()
    ).hexdigest()


def _annotation_signals(
    data_root: Path,
) -> tuple[set[str], set[str], dict[str, list[str]]]:
    human_reviewed: set[str] = set()
    agent_positive: set[str] = set()
    agent_reviewers: dict[str, list[str]] = {}
    for path in sorted(data_root.rglob("annotation.json")):
        payload = _load(path)
        for frame in payload.get("frames", []):
            frame_id = str(frame.get("frame_id", ""))
            provenance = frame.get("provenance") or {}
            reviewer = str(provenance.get("reviewer", ""))
            if not frame_id or not reviewer:
                continue
            if reviewer == "zkelder":
                human_reviewed.add(frame_id)
                continue
            if frame.get("whole_frame_truth") == "yes":
                agent_positive.add(frame_id)
                agent_reviewers.setdefault(frame_id, []).append(reviewer)
    return human_reviewed, agent_positive, agent_reviewers


def _frame_path(manifest_path: Path, frame: dict[str, Any]) -> Path | None:
    capture_root = manifest_path.parent
    frame_id = str(frame["frame_id"])
    candidates = (
        capture_root / "frames" / f"{frame_id}.jpg",
        capture_root / "high-resolution" / f"{frame_id}.jpg",
    )
    return next((path for path in candidates if path.is_file()), None)


def _frozen_hashes(manifest_path: Path) -> set[str]:
    payload = _load(manifest_path)
    hashes = {
        str(frame.get("content_hash"))
        for frame in payload.get("frames", [])
        if frame.get("content_hash")
    }
    if len(hashes) != 75:
        raise WildlifeTrainingError("queue_frozen_holdout_identity_invalid")
    return hashes


def _candidate_rows(
    data_root: Path,
    *,
    holdout_hashes: set[str],
    human_reviewed: set[str],
    agent_positive: set[str],
    agent_reviewers: dict[str, list[str]],
    seed: int,
) -> list[dict[str, Any]]:
    by_hash: dict[str, dict[str, Any]] = {}
    manifests = sorted(
        data_root.glob(
            "field-acceptance/**/capture-out/capture-session-manifest.json"
        )
    )
    for manifest_path in manifests:
        payload = _load(manifest_path)
        session_id = str(payload.get("capture_session_id", manifest_path.parent))
        for frame in payload.get("frames", []):
            frame_id = str(frame.get("frame_id", ""))
            content_hash = str(frame.get("content_hash", ""))
            if (
                not frame_id
                or len(content_hash) != 64
                or frame_id in human_reviewed
                or content_hash in holdout_hashes
            ):
                continue
            image_path = _frame_path(manifest_path, frame)
            if image_path is None or sha256_file(image_path) != content_hash:
                continue
            reasons = sorted(str(value) for value in frame.get("trigger_reasons", []))
            detector_count = int(frame.get("animal_detection_count") or 0)
            max_score = frame.get("max_animal_score")
            max_score = float(max_score) if max_score is not None else 0.0
            agent_signal = frame_id in agent_positive
            row = {
                "frame_id": frame_id,
                "content_hash": content_hash,
                "image": str(image_path),
                "capture_manifest": str(manifest_path),
                "capture_session_id": session_id,
                "source_capture_timestamp": frame.get("source_capture_timestamp"),
                "high_resolution": bool(frame.get("high_resolution")),
                "detector_observation_count": int(
                    frame.get("detector_observation_count") or 0
                ),
                "animal_detection_count": detector_count,
                "max_animal_score": max_score if max_score else None,
                "motion_proposal_count": int(frame.get("motion_proposal_count") or 0),
                "trigger_reasons": reasons,
                "agent_suggested_positive": agent_signal,
                "agent_signal_reviewers": sorted(
                    set(agent_reviewers.get(frame_id, []))
                ),
                "signal_authority": "agent_diagnostic_non_truth",
                "review_status": "unreviewed",
                "training_eligible": False,
                "selection_tie_break": _stable_hash(
                    session_id, frame_id, content_hash, seed=seed
                ),
            }
            existing = by_hash.get(content_hash)
            if existing is None or row["selection_tie_break"] < existing[
                "selection_tie_break"
            ]:
                by_hash[content_hash] = row
    return list(by_hash.values())


def _positive_order(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -int(row["agent_suggested_positive"]),
        -int(row["animal_detection_count"] > 0),
        -(row["max_animal_score"] or 0.0),
        -row["detector_observation_count"],
        row["selection_tie_break"],
    )


def _static_order(row: dict[str, Any]) -> tuple[Any, ...]:
    reasons = row["trigger_reasons"]
    return (
        -int("recurring_static_geometry" in reasons),
        -int(row["animal_detection_count"] > 0),
        -(row["max_animal_score"] or 0.0),
        row["selection_tie_break"],
    )


def _weather_order(row: dict[str, Any]) -> tuple[Any, ...]:
    reasons = row["trigger_reasons"]
    return (
        -int(bool(row["high_resolution"])),
        -int("high_resolution_burst" in reasons),
        -int("periodic_negative" in reasons),
        -int(row["source_capture_timestamp"] is not None),
        row["selection_tie_break"],
    )


def _take(
    rows: Iterable[dict[str, Any]],
    *,
    count: int,
    selected_hashes: set[str],
    key: Any,
    lane: str,
    required_action: str,
) -> list[dict[str, Any]]:
    eligible = [
        row for row in rows if row["content_hash"] not in selected_hashes
    ]
    ordered = sorted(eligible, key=key)
    if len(ordered) < count:
        raise WildlifeTrainingError(f"local_queue_lane_unavailable:{lane}")
    chosen = ordered[:count]
    for priority, row in enumerate(chosen, start=1):
        row["target_lane"] = lane
        row["lane_priority"] = priority
        row["required_human_action"] = required_action
        selected_hashes.add(row["content_hash"])
    return chosen


def build_queue(
    data_root: Path,
    *,
    holdout_manifest: Path,
    seed: int,
) -> dict[str, Any]:
    human_reviewed, agent_positive, agent_reviewers = _annotation_signals(data_root)
    frozen = _frozen_hashes(holdout_manifest)
    rows = _candidate_rows(
        data_root,
        holdout_hashes=frozen,
        human_reviewed=human_reviewed,
        agent_positive=agent_positive,
        agent_reviewers=agent_reviewers,
        seed=seed,
    )
    selected_hashes: set[str] = set()
    selected: list[dict[str, Any]] = []
    selected.extend(
        _take(
            rows,
            count=LANE_QUOTAS["likely_positive_requires_human_boxes"],
            selected_hashes=selected_hashes,
            key=_positive_order,
            lane="likely_positive_requires_human_boxes",
            required_action=(
                "inspect the exact full frame; if animal is present, confirm yes "
                "and draw human boxes for every animal; otherwise confirm no"
            ),
        )
    )
    selected.extend(
        _take(
            rows,
            count=LANE_QUOTAS["static_clutter_negative_candidate"],
            selected_hashes=selected_hashes,
            key=_static_order,
            lane="static_clutter_negative_candidate",
            required_action=(
                "inspect the exact full frame and independently confirm no animal; "
                "do not infer absence from detector or agent output"
            ),
        )
    )
    selected.extend(
        _take(
            rows,
            count=LANE_QUOTAS["weather_lighting_negative_candidate"],
            selected_hashes=selected_hashes,
            key=_weather_order,
            lane="weather_lighting_negative_candidate",
            required_action=(
                "inspect the exact full frame for glare, darkness, precipitation, "
                "or foliage motion; independently confirm no animal"
            ),
        )
    )
    selected.sort(key=lambda row: (
        list(LANE_QUOTAS).index(row["target_lane"]),
        row["lane_priority"],
    ))
    payload: dict[str, Any] = {
        "schema_version": 1,
        "queue_id": "mockingbird-local-wildlife-correction-v0.2",
        "seed": seed,
        "queue_size": len(selected),
        "lane_quotas": LANE_QUOTAS,
        "lane_distribution": dict(
            sorted(Counter(row["target_lane"] for row in selected).items())
        ),
        "eligible_unique_exact_capture_frames_before_selection": len(rows),
        "excluded_human_reviewed_frame_ids": len(human_reviewed),
        "excluded_frozen_holdout_hashes": len(frozen),
        "truth_policy": (
            "agent and detector signals rank review only; human full-frame review "
            "and human boxes are required before any row becomes training truth"
        ),
        "positive_candidates_reviewed_first": True,
        "current_human_boxed_positive_frames": 0,
        "current_human_reviewed_negative_frames": 18,
        "additional_human_boxed_positive_frames_to_target": 1_000,
        "additional_human_reviewed_negative_frames_to_target": 982,
        "additional_total_reviewed_frames_to_target": 1_982,
        "frames": selected,
        "creates_product_truth": False,
    }
    payload["semantic_fingerprint"] = canonical_fingerprint(payload)
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def main() -> int:
    args = _args()
    payload = build_queue(
        args.data_root.resolve(),
        holdout_manifest=args.holdout_manifest.resolve(),
        seed=args.seed,
    )
    _write_json(args.output.resolve(), payload)
    print(json.dumps({
        "output": str(args.output),
        "queue_size": payload["queue_size"],
        "lane_distribution": payload["lane_distribution"],
        "eligible_unique_exact_capture_frames_before_selection": payload[
            "eligible_unique_exact_capture_frames_before_selection"
        ],
        "semantic_fingerprint": payload["semantic_fingerprint"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WildlifeTrainingError as error:
        print(f"local correction queue failed: {error}", file=sys.stderr)
        raise SystemExit(2) from error
