"""Launch MockingBird as one local application."""

import sys

from mockingbird.runtime import main


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "replay-benchmark":
        from mockingbird.observation.replay_cli import run as replay_run
        raise SystemExit(replay_run(sys.argv[2:]))
    elif len(sys.argv) > 1 and sys.argv[1] == "detector-benchmark":
        from mockingbird.observation.detector_benchmark_cli import run as detector_benchmark_run
        raise SystemExit(detector_benchmark_run(sys.argv[2:]))
    elif len(sys.argv) > 1 and sys.argv[1] == "detector-comparison":
        from mockingbird.observation.detector_comparison_cli import run as detector_comparison_run
        raise SystemExit(detector_comparison_run(sys.argv[2:]))
    elif len(sys.argv) > 1 and sys.argv[1] == "multi-scale-benchmark":
        from mockingbird.observation.multi_scale_cli import run_benchmark as multi_scale_benchmark_run
        raise SystemExit(multi_scale_benchmark_run(sys.argv[2:]))
    elif len(sys.argv) > 1 and sys.argv[1] == "multi-scale-comparison":
        from mockingbird.observation.multi_scale_cli import run_comparison as multi_scale_comparison_run
        raise SystemExit(multi_scale_comparison_run(sys.argv[2:]))
    elif len(sys.argv) > 1 and sys.argv[1] == "motion-proposal-benchmark":
        from mockingbird.observation.motion_proposal_cli import run_benchmark as motion_proposal_benchmark_run
        raise SystemExit(motion_proposal_benchmark_run(sys.argv[2:]))
    elif len(sys.argv) > 1 and sys.argv[1] == "motion-proposal-decision":
        from mockingbird.observation.motion_proposal_cli import run_decision as motion_proposal_decision_run
        raise SystemExit(motion_proposal_decision_run(sys.argv[2:]))
    elif len(sys.argv) > 1 and sys.argv[1] == "temporal-capture":
        from mockingbird.observation.temporal_capture_cli import run_capture as temporal_capture_run
        raise SystemExit(temporal_capture_run(sys.argv[2:]))
    elif len(sys.argv) > 1 and sys.argv[1] == "temporal-capture-mark":
        from mockingbird.observation.temporal_capture_cli import run_mark as temporal_capture_mark_run
        raise SystemExit(temporal_capture_mark_run(sys.argv[2:]))
    elif len(sys.argv) > 1 and sys.argv[1] == "temporal-review-build":
        from mockingbird.observation.temporal_review_cli import run_build as temporal_review_build_run
        raise SystemExit(temporal_review_build_run(sys.argv[2:]))
    elif len(sys.argv) > 1 and sys.argv[1] == "temporal-review-validate":
        from mockingbird.observation.temporal_review_cli import run_validate as temporal_review_validate_run
        raise SystemExit(temporal_review_validate_run(sys.argv[2:]))
    elif len(sys.argv) > 1 and sys.argv[1] == "temporal-review-export":
        from mockingbird.observation.temporal_review_cli import run_export as temporal_review_export_run
        raise SystemExit(temporal_review_export_run(sys.argv[2:]))
    elif len(sys.argv) > 1 and sys.argv[1] == "burst-schedule-replay":
        from mockingbird.observation.burst_scheduler_replay_cli import run as burst_schedule_replay_run
        raise SystemExit(burst_schedule_replay_run(sys.argv[2:]))
    elif len(sys.argv) > 1 and sys.argv[1] == "evidence-benchmark":
        from mockingbird.observation.evidence_benchmark_cli import run_benchmark as evidence_benchmark_run
        raise SystemExit(evidence_benchmark_run(sys.argv[2:]))
    elif len(sys.argv) > 1 and sys.argv[1] == "evidence-comparison":
        from mockingbird.observation.evidence_benchmark_cli import run_comparison as evidence_comparison_run
        raise SystemExit(evidence_comparison_run(sys.argv[2:]))
    else:
        main()
