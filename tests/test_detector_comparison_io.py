"""Safety and CLI-wiring tests for the Stage 6.3 detector-comparison's
filesystem I/O and command entry point. Reports are hand-built fixture JSON
files (shaped like real `detector-benchmark-report.json` output); no real
model, camera, CUDA, or product database is touched.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mockingbird.observation.detector_comparison import DetectorComparisonError
from mockingbird.observation.detector_comparison_cli import run as detector_comparison_run
from mockingbird.observation.detector_comparison_io import (
    load_detector_benchmark_report,
    write_detector_comparison_report,
)


def _report_payload(*, model_key: str = "md-v5a", manifest_fingerprint: str = "cohort-fp-1", precision: float = 0.5, recall: float = 0.5) -> dict[str, object]:
    return {
        "cohort": {"manifest_fingerprint": manifest_fingerprint, "cohort_id": "fixture-cohort", "frame_count": 70},
        "provider": {"model": {
            "key": model_key, "version": "v1", "fingerprint": "fp", "license": "MIT",
            "redistribution": "not audited", "taxonomy": "MegaDetector broad classes",
            "decoder": "megadetector_v5_yolov5_raw_v1",
        }},
        "configured_threshold": 0.1,
        "threshold_grid": [0.1],
        "threshold_sweep": [{
            "threshold": 0.1, "is_configured_threshold": True, "precision": precision, "recall": recall,
            "positive_frame_recall": 0.6, "false_positives_per_negative_frame": 0.2,
            "false_positive_frame_count": 3, "duplicate_detections": 1,
            "scene_group_breakdown": [], "subject_size_breakdown": [],
        }],
        "static_false_positive_clusters": {"clusters": []},
        "temporal_policy_simulation": [],
        "sample_sufficiency": {"sufficient_for_threshold_selection": True},
        "overall_classification": "DETECTOR_CALIBRATION_CHARACTERIZED",
        "execution": {
            "primary_execution_facts": {"latency_ms_median": 100.0},
            "model_size_bytes": 1000,
            "gpu_memory_after_mib": 500,
        },
    }


def _write_report(path: Path, **overrides: object) -> Path:
    path.write_text(json.dumps(_report_payload(**overrides)), encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# I/O safety
# --------------------------------------------------------------------------


def test_load_detector_benchmark_report_round_trips(tmp_path: Path) -> None:
    report_path = _write_report(tmp_path / "report.json")

    loaded = load_detector_benchmark_report(report_path)

    assert loaded["provider"]["model"]["key"] == "md-v5a"


def test_load_detector_benchmark_report_rejects_symlink(tmp_path: Path) -> None:
    real = _write_report(tmp_path / "real.json")
    link = tmp_path / "link.json"
    link.symlink_to(real)

    with pytest.raises(DetectorComparisonError, match="unsafe_report_path"):
        load_detector_benchmark_report(link)


def test_load_detector_benchmark_report_rejects_non_json_suffix(tmp_path: Path) -> None:
    path = tmp_path / "report.txt"
    path.write_text(json.dumps(_report_payload()), encoding="utf-8")

    with pytest.raises(DetectorComparisonError, match="unsafe_report_path"):
        load_detector_benchmark_report(path)


def test_load_detector_benchmark_report_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(DetectorComparisonError, match="unsafe_report_path"):
        load_detector_benchmark_report(tmp_path / "missing.json")


def test_load_detector_benchmark_report_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(DetectorComparisonError, match="invalid_report_json"):
        load_detector_benchmark_report(path)


def test_load_detector_benchmark_report_rejects_non_object_json(tmp_path: Path) -> None:
    path = tmp_path / "list.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(DetectorComparisonError, match="invalid_report_json"):
        load_detector_benchmark_report(path)


def test_write_report_rejects_nonempty_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "existing.txt").write_text("x")

    with pytest.raises(DetectorComparisonError, match="nonempty_output_directory"):
        write_detector_comparison_report(output, {"semantic_fingerprint": "x"}, execution={})


def test_write_report_is_atomic_and_readable(tmp_path: Path) -> None:
    output = tmp_path / "output"
    semantic = {"schema_version": 1, "semantic_fingerprint": "abc"}

    path = write_detector_comparison_report(output, semantic, execution={"runtime_facts_by_candidate": {}})

    payload = json.loads(path.read_text())
    assert payload["semantic_fingerprint"] == "abc"
    assert payload["execution"] == {"runtime_facts_by_candidate": {}}
    assert not list(output.glob(".*.tmp"))
    assert path.name == "detector-comparison-report.json"


# --------------------------------------------------------------------------
# CLI wiring
# --------------------------------------------------------------------------


def test_cli_end_to_end_is_deterministic(tmp_path: Path) -> None:
    baseline_path = _write_report(tmp_path / "mdv5-report.json", model_key="md-v5a", precision=0.5, recall=0.5)
    candidate_path = _write_report(tmp_path / "spruce-report.json", model_key="md-v1000-spruce", precision=0.6, recall=0.6)

    payloads = []
    for name in ("run-a", "run-b"):
        destination = tmp_path / name
        exit_code = detector_comparison_run([
            "--baseline-label", "mdv5",
            "--baseline-report", str(baseline_path),
            "--candidate", f"spruce={candidate_path}",
            "--output", str(destination),
        ])
        assert exit_code == 0
        payloads.append(json.loads((destination / "detector-comparison-report.json").read_text()))

    assert payloads[0]["semantic_fingerprint"] == payloads[1]["semantic_fingerprint"]
    assert payloads[0]["creates_truth"] is False
    assert payloads[0]["shadow_only"] is True
    assert payloads[0]["candidate_labels"] == ["spruce"]
    assert "execution" in payloads[0]
    assert str(tmp_path.resolve()) not in json.dumps({k: v for k, v in payloads[0].items() if k != "execution"})


def test_cli_supports_multiple_candidates(tmp_path: Path) -> None:
    baseline_path = _write_report(tmp_path / "mdv5-report.json")
    spruce_path = _write_report(tmp_path / "spruce-report.json", model_key="md-v1000-spruce")
    redwood_path = _write_report(tmp_path / "redwood-report.json", model_key="md-v1000-redwood")
    destination = tmp_path / "out"

    exit_code = detector_comparison_run([
        "--baseline-label", "mdv5",
        "--baseline-report", str(baseline_path),
        "--candidate", f"spruce={spruce_path}",
        "--candidate", f"redwood={redwood_path}",
        "--output", str(destination),
    ])

    assert exit_code == 0
    payload = json.loads((destination / "detector-comparison-report.json").read_text())
    assert payload["candidate_labels"] == ["redwood", "spruce"]


def test_cli_rejects_missing_baseline_report_cleanly(tmp_path: Path) -> None:
    candidate_path = _write_report(tmp_path / "spruce-report.json")

    exit_code = detector_comparison_run([
        "--baseline-label", "mdv5",
        "--baseline-report", str(tmp_path / "missing.json"),
        "--candidate", f"spruce={candidate_path}",
        "--output", str(tmp_path / "out"),
    ])

    assert exit_code != 0
    assert not (tmp_path / "out").exists()


def test_cli_rejects_duplicate_candidate_labels(tmp_path: Path) -> None:
    baseline_path = _write_report(tmp_path / "mdv5-report.json")
    candidate_path = _write_report(tmp_path / "spruce-report.json", model_key="md-v1000-spruce")

    exit_code = detector_comparison_run([
        "--baseline-label", "mdv5",
        "--baseline-report", str(baseline_path),
        "--candidate", f"spruce={candidate_path}",
        "--candidate", f"spruce={candidate_path}",
        "--output", str(tmp_path / "out"),
    ])

    assert exit_code != 0
    assert not (tmp_path / "out").exists()


def test_cli_rejects_malformed_candidate_argument(tmp_path: Path) -> None:
    baseline_path = _write_report(tmp_path / "mdv5-report.json")

    exit_code = detector_comparison_run([
        "--baseline-label", "mdv5",
        "--baseline-report", str(baseline_path),
        "--candidate", "no-equals-sign-here",
        "--output", str(tmp_path / "out"),
    ])

    assert exit_code != 0
    assert not (tmp_path / "out").exists()
