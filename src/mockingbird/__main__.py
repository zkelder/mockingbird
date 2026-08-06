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
    else:
        main()
