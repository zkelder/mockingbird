#!/usr/bin/env python3
"""Tier A -- Fast change gate: the highest-value fast unit/pure-contract tests.

Guarantees: pure computation, schemas, deterministic state transitions,
authority/admission rules, provenance, geometry, review semantics, and small
repository contracts covered by the files listed below (see
docs/test-suite-validation-tiers-contract.md for how this list was derived
and what evidence backs each file's inclusion -- module docstrings
self-declaring "hardware-free", no real subprocess/model-runtime/large-file
I/O). It does *not* replace focused RED/GREEN tests during implementation
(run the one or two closest files directly for that) or the Core gate before
calling a milestone complete.

Run this before considering any bounded, single-area change complete.
Escalate to Core (scripts/verify_core.py) for anything crossing more than
one subsystem or touching a "preserve critical contracts" area -- see
docs/test-suite-validation-tiers-contract.md's escalation rules. Do not add
a new file to FAST_FILES merely because it happens to run quickly; add it
because it belongs to this tier's *contract* (see that document's tier
definitions) -- a slow test inside an otherwise-fast file gets an individual
`@pytest.mark.slow`, not a file-level exception here.

Usage:
    python scripts/verify_fast.py [extra pytest args]

Exit code is pytest's own exit code.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests"

# Kept in one alphabetized list, one file per line, so a diff shows exactly
# what changed. See docs/test-suite-validation-tiers-contract.md for the
# evidence behind each inclusion (module docstring, fixture usage, absence
# of subprocess/real-model/large-file signals) -- do not add a file here
# without the same evidence. Deliberately excludes the untracked, parked
# `test_small_bird_benchmark.py` prototype (see docs/runtime-map.md
# "Untracked, parked prototype") even though it is currently fast and
# passing: a file this script hard-codes must exist on every checkout,
# including one without local untracked artifacts.
FAST_FILES = [
    "test_admission_policy.py",
    "test_automatic_review_identification.py",
    "test_bioclip_adapter.py",
    "test_bioclip_field_evaluation.py",
    "test_bioclip_runtime.py",
    "test_burst_scheduler.py",
    "test_burst_scheduler_replay.py",
    "test_candidate_quality_gate.py",
    "test_candidate_visit_authority.py",
    "test_classifier_input.py",
    "test_contracts_confidence_evidence.py",
    "test_counterfactual_lineage.py",
    "test_detection_quality_accounting.py",
    "test_detector_calibration_benchmark.py",
    "test_detector_calibration_benchmark_io.py",
    "test_detector_comparison.py",
    "test_detector_comparison_io.py",
    "test_detector_promotion.py",
    "test_durable_monitoring_supervisor.py",
    "test_effective_primary.py",
    "test_encounter_accounting.py",
    "test_evaluate_wildlife_stage2.py",
    "test_evaluation_governance.py",
    "test_evidence_benchmark.py",
    "test_evidence_benchmark_cli.py",
    "test_evidence_benchmark_io.py",
    "test_exact_frame_capture.py",
    "test_field_trial_launcher.py",
    "test_frame_sampler.py",
    "test_frame_tracker.py",
    "test_install_camera_node.py",
    "test_live_camera_session.py",
    "test_live_preview_leases.py",
    "test_local_activity_diagnostic.py",
    "test_localization_attribution.py",
    "test_motion_activity_crop.py",
    "test_motion_proposal_benchmark.py",
    "test_motion_proposal_cli.py",
    "test_motion_proposal_strategy.py",
    "test_motion_scoring.py",
    "test_multi_scale_benchmark.py",
    "test_multi_scale_cli.py",
    "test_multi_scale_strategy.py",
    "test_mvp_smoke_script.py",
    "test_observation_evidence_comparison.py",
    "test_observation_evidence_scoring.py",
    "test_observation_frame_driven_cli.py",
    "test_observation_md_v5_onnx.py",
    "test_observation_replay.py",
    "test_observation_replay_io.py",
    "test_observation_replay_report_contract.py",
    "test_place_activity_report.py",
    "test_reconnect_continuity.py",
    "test_replay_visit_episode_assembly.py",
    "test_review_provenance.py",
    "test_reviewed_replay_lineage.py",
    "test_scene_confusor.py",
    "test_session_timeline.py",
    "test_storage_retention_service.py",
    "test_storage_status_disk.py",
    "test_temporal_annotation.py",
    "test_temporal_capture.py",
    "test_temporal_capture_cli.py",
    "test_temporal_capture_io.py",
    "test_temporal_review_io.py",
    "test_time_utils.py",
    "test_tracked_activity.py",
    "test_unified_observation_status.py",
    "test_visit_classifier_supporting_evidence.py",
    "test_visit_episode_assembler.py",
    "test_wildlife_multiscene.py",
    "test_wildlife_stage2_checkpoint_staging.py",
    "test_wildlife_stage2_training.py",
    "test_wildlife_stage3_readiness.py",
    "test_wildlife_stage3_tranche.py",
    "test_wildlife_taxonomy.py",
    "test_wildlife_training.py",
    "test_windows_launcher_instance_identity.py",
    "test_worker_registry_contract.py",
    "test_zone_diagnostic.py",
]


def main() -> int:
    missing = [name for name in FAST_FILES if not (TESTS_DIR / name).is_file()]
    if missing:
        print(
            "[verify_fast] missing expected test file(s), refusing to give a "
            f"false-green result: {missing}",
            file=sys.stderr,
        )
        return 2

    paths = [str((TESTS_DIR / name).relative_to(ROOT)) for name in FAST_FILES]
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-m",
        "not slow",
        *paths,
        *sys.argv[1:],
    ]
    print(f"[verify_fast] {len(FAST_FILES)} files", file=sys.stderr)
    result = subprocess.run(command, cwd=ROOT)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
