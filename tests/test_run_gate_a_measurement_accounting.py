"""Gate A Measurement Closure v1: focused, hardware-free test for the new
combined acceptance-tooling command (see
scripts/run_gate_a_measurement_accounting.py and this milestone's own
governing brief §26 "Tooling UX") -- a real, temp-directory invocation of
`main(...)` against a small, saved ledger-JSON-shaped fixture, asserting on
the three written report files, not merely on the pure functions
underneath (those already have their own dedicated test files)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "run_gate_a_measurement_accounting.py"

STREAM_ID = "stream-test"


def _generation(generation_id: str, *, start_ms: int, end_ms: int, start_captured_at: str | None = None) -> dict:
    box = [0.47, 0.58, 0.51, 0.63]
    return {
        "generation_id": generation_id, "stream_id": STREAM_ID, "broad_class": "animal",
        "track_ids": [f"{generation_id}-track"], "start_offset_ms": start_ms, "end_offset_ms": end_ms,
        "start_bounding_box": box, "end_bounding_box": box, "geometry_envelope": box, "confirmed": True,
        "terminal_reason": "maximum_unsupported_duration",
        "confidence_evidence": {"detection_count": 1, "max_confidence": 0.6, "strong_detection_count": 0},
        "start_captured_at": start_captured_at, "end_captured_at": start_captured_at,
    }


def _outcome(proposal_id: str, *, generation_ids: list[str], visit_id: str, decided_at: str) -> dict:
    return {
        "proposal_id": proposal_id, "stream_id": STREAM_ID, "broad_class": "animal", "zone_id": None,
        "start_offset_ms": 0, "end_offset_ms": 2_000, "constituent_generation_ids": generation_ids,
        "outcome": "created", "reason": "eligible_assembled_proposal", "admitted": True,
        "visit_id": visit_id, "decided_at": decided_at,
    }


def _write_ledger(path: Path) -> None:
    window = {
        "stream_id": STREAM_ID, "start_offset_ms": 0, "end_offset_ms": 10_000,
        "track_generations": [
            _generation("gen-1", start_ms=0, end_ms=2_000, start_captured_at="2026-08-31T19:45:00Z"),
        ],
        "proposal_outcomes": [
            _outcome("p-1", generation_ids=["gen-1"], visit_id="visit-1", decided_at="2026-08-31T19:45:08Z"),
        ],
        "coverage": {},
    }
    path.write_text(json.dumps(window), encoding="utf-8")


def test_combined_accounting_command_writes_all_three_reports(tmp_path: Path) -> None:
    ledger_path = tmp_path / "counterfactual.json"
    _write_ledger(ledger_path)
    output_dir = tmp_path / "out"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--input", str(ledger_path), "--output", str(output_dir)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr

    encounter = json.loads((output_dir / "encounter-funnel-report.json").read_text(encoding="utf-8"))
    assert encounter["funnel"]["total_encounter_clusters"] == 1
    assert encounter["funnel"]["clusters_with_visit"] == 1

    fragmentation = json.loads((output_dir / "fragmentation-accounting-report.json").read_text(encoding="utf-8"))
    assert fragmentation["report"]["total_units"] == 1
    assert fragmentation["report"]["correctly_represented_count"] == 1
    assert fragmentation["report"]["fragmentation_rate"] == {"state": "evaluated", "value": 0.0}
    assert len(fragmentation["denominator_units"]) == 1

    latency = json.loads((output_dir / "latency-report.json").read_text(encoding="utf-8"))
    assert latency["summary"]["sample_count"] == 1
    assert latency["summary"]["measured_count"] == 1
    assert latency["summary"]["median_ms"] == 8_000.0
    assert len(latency["samples"]) == 1
    assert latency["samples"][0]["t0_source"] == "earliest_constituent_generation_start_captured_at"


def test_dispositions_override_is_applied_and_visits_export_enables_sibling_classification(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "counterfactual.json"
    window = {
        "stream_id": STREAM_ID, "start_offset_ms": 0, "end_offset_ms": 10_000,
        "track_generations": [
            _generation("gen-a", start_ms=0, end_ms=2_000),
            _generation("gen-b", start_ms=2_010, end_ms=4_000),
        ],
        "proposal_outcomes": [
            _outcome("p-a", generation_ids=["gen-a"], visit_id="visit-a", decided_at="2026-08-31T19:45:08Z"),
            _outcome("p-b", generation_ids=["gen-b"], visit_id="visit-b", decided_at="2026-08-31T19:45:10Z"),
        ],
        "coverage": {},
    }
    ledger_path.write_text(json.dumps(window), encoding="utf-8")
    output_dir = tmp_path / "out"

    # First pass: no dispositions supplied -- the pair must be ambiguous.
    first = subprocess.run(
        [sys.executable, str(SCRIPT), "--input", str(ledger_path), "--output", str(output_dir)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    assert first.returncode == 0, first.stderr
    fragmentation = json.loads((output_dir / "fragmentation-accounting-report.json").read_text(encoding="utf-8"))
    assert fragmentation["report"]["ambiguous_count"] == 1
    unit_id = fragmentation["denominator_units"][0]["denominator_unit_id"]

    dispositions_path = tmp_path / "dispositions.json"
    dispositions_path.write_text(
        json.dumps([{
            "denominator_unit_id": unit_id, "disposition": "fragmented",
            "reviewer_note": "Confirmed one continuous bird across both Visits via recorder frames.",
        }]),
        encoding="utf-8",
    )

    second = subprocess.run(
        [
            sys.executable, str(SCRIPT), "--input", str(ledger_path), "--output", str(output_dir),
            "--dispositions", str(dispositions_path),
        ],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    assert second.returncode == 0, second.stderr
    fragmentation_reviewed = json.loads(
        (output_dir / "fragmentation-accounting-report.json").read_text(encoding="utf-8")
    )
    assert fragmentation_reviewed["report"]["fragmented_count"] == 1
    assert fragmentation_reviewed["report"]["ambiguous_count"] == 0
    assert fragmentation_reviewed["report"]["fragmentation_rate"] == {"state": "evaluated", "value": 1.0}


def test_rtt_clock_calibration_wiring_end_to_end_through_the_cli(tmp_path: Path) -> None:
    """Camera Node <-> Host RTT-Bounded Clock Calibration v1: a saved
    ledger snapshot that says `clock_calibration_required: true` and
    carries one calibrated `rtt_clock_calibrations` entry must normalize T0
    through that RTT-bounded interval before computing latency -- proven
    through the real CLI subprocess, not only the in-process pure
    functions (those have their own dedicated test files). The one-way
    `clock_calibrations` key alone (Camera Node -> Host Clock Normalization
    v1) is deliberately *not* supplied here -- it can no longer normalize
    anything on its own (see capture_to_visible_latency.py's own
    docstring)."""
    ledger_path = tmp_path / "counterfactual.json"
    window = {
        "stream_id": STREAM_ID, "start_offset_ms": 0, "end_offset_ms": 10_000,
        "track_generations": [
            _generation("gen-1", start_ms=0, end_ms=2_000, start_captured_at="2026-08-31T19:45:00Z"),
        ],
        "proposal_outcomes": [
            _outcome("p-1", generation_ids=["gen-1"], visit_id="visit-1", decided_at="2026-08-31T19:45:12Z"),
        ],
        "coverage": {},
        "clock_calibration_required": True,
        "rtt_clock_calibrations": [{
            "stream_id": STREAM_ID, "source_offset_ms": 0, "calibrated_at": "2026-08-31T19:45:00Z",
            "sample_count": 5, "valid_sample_count": 5, "state": "calibrated",
            "offset_ms": 2_000.0, "offset_min_ms": 1_985.0, "offset_max_ms": 2_015.0,
            "uncertainty_ms": 15.0, "rtt_ms": 30.0, "clock_jump_detected": False,
        }],
    }
    ledger_path.write_text(json.dumps(window), encoding="utf-8")
    output_dir = tmp_path / "out"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--input", str(ledger_path), "--output", str(output_dir)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert (
        "Clock calibration (RTT-bounded, absolute anchor): 1 batches recorded "
        "(1 calibrated, 0 insufficient_samples, 0 inconsistent_samples, 0 clock jump(s) detected)"
    ) in result.stdout

    latency = json.loads((output_dir / "latency-report.json").read_text(encoding="utf-8"))
    sample = latency["samples"][0]
    assert sample["clock_calibration_state"] == "normalized"
    assert sample["clock_offset_ms"] == 2_000.0
    assert sample["clock_offset_min_ms"] == 1_985.0
    assert sample["clock_offset_max_ms"] == 2_015.0
    assert sample["state"] == "measured"
    # Raw gap is 12s (19:45:00 -> 19:45:12); the 2s calibrated offset is
    # subtracted, leaving 10s -- proof the CLI actually normalized T0
    # rather than falling back to the raw subtraction.
    assert sample["latency_ms"] == 10_000.0
    assert sample["latency_min_ms"] == pytest.approx(9_985.0)
    assert sample["latency_max_ms"] == pytest.approx(10_015.0)


def test_one_way_calibration_alone_is_insufficient_to_normalize(tmp_path: Path) -> None:
    """The one-way estimator can never itself produce a defensible bound
    (this milestone's own entire problem statement) -- a snapshot carrying
    `clock_calibrations` (one-way) but no `rtt_clock_calibrations` must
    honestly report `invalid_clock_mapping`, never silently substitute the
    weaker estimator."""
    ledger_path = tmp_path / "counterfactual.json"
    window = {
        "stream_id": STREAM_ID, "start_offset_ms": 0, "end_offset_ms": 10_000,
        "track_generations": [
            _generation("gen-1", start_ms=0, end_ms=2_000, start_captured_at="2026-08-31T19:45:00Z"),
        ],
        "proposal_outcomes": [
            _outcome("p-1", generation_ids=["gen-1"], visit_id="visit-1", decided_at="2026-08-31T19:45:12Z"),
        ],
        "coverage": {},
        "clock_calibration_required": True,
        "clock_calibrations": [{
            "stream_id": STREAM_ID, "source_offset_ms": 0, "calibrated_at": "2026-08-31T19:45:00Z",
            "sample_count": 5, "state": "calibrated", "offset_ms": 2_000.0, "uncertainty_ms": 15.0,
            "clock_jump_detected": False,
        }],
    }
    ledger_path.write_text(json.dumps(window), encoding="utf-8")
    output_dir = tmp_path / "out"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--input", str(ledger_path), "--output", str(output_dir)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    latency = json.loads((output_dir / "latency-report.json").read_text(encoding="utf-8"))
    sample = latency["samples"][0]
    assert sample["clock_calibration_state"] == "no_calibration"
    assert sample["state"] == "invalid_clock_mapping"
    assert sample["latency_ms"] is None


def test_old_ledger_snapshot_without_clock_calibration_metadata_still_runs_cleanly(tmp_path: Path) -> None:
    """Compatibility: a snapshot saved before this milestone has neither
    `rtt_clock_calibrations` nor `clock_calibration_required` at all -- the
    CLI must not crash, and must fall back to this module's own
    pre-existing, unaffected default (`clock_calibration_required=False`)."""
    ledger_path = tmp_path / "counterfactual.json"
    _write_ledger(ledger_path)  # no clock_calibration* keys at all
    output_dir = tmp_path / "out"

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--input", str(ledger_path), "--output", str(output_dir)],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "Clock calibration (one-way, relative monitoring): required=False, 0 attempts recorded" in result.stdout
    assert "Clock calibration (RTT-bounded, absolute anchor): 0 batches recorded" in result.stdout
    latency = json.loads((output_dir / "latency-report.json").read_text(encoding="utf-8"))
    assert latency["samples"][0]["clock_calibration_state"] == "not_required"
    assert latency["samples"][0]["state"] == "measured"
