"""Launch MockingBird as one local application."""

import sys

from mockingbird.runtime import main


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "replay-benchmark":
        from mockingbird.observation.replay_cli import run as replay_run
        raise SystemExit(replay_run(sys.argv[2:]))
    else:
        main()
