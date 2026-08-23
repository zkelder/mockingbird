"""CLI entry point for `python -m mockingbird support-bundle`.

Mirrors `diagnostics.doctor_cli`'s own dispatch/argument-parsing shape
exactly -- see that module's docstring for why this convention (a lazy
`__main__.py` import + `run(argv)` returning an int exit code) rather than
`argparse.add_subparsers()`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from mockingbird.diagnostics.support_bundle import (
    DEFAULT_LOG_TAIL_LINES,
    default_output_path,
    write_support_bundle,
)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mockingbird support-bundle",
        description=(
            "Write a small, bounded, privacy-safe diagnostic bundle (health check, "
            "structural Source facts, redacted recent logs, version/schema facts) "
            "to share in a support conversation. Never includes camera passwords, "
            "pairing secrets, auth tokens, or media. Includes local folder paths "
            "(which can embed your OS username) unless --no-local-paths is given."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output .zip path (default: a timestamped file in the data folder).",
    )
    parser.add_argument(
        "--log-lines",
        type=int,
        default=DEFAULT_LOG_TAIL_LINES,
        help=f"Maximum recent log lines to include (default: {DEFAULT_LOG_TAIL_LINES}).",
    )
    parser.add_argument(
        "--no-local-paths",
        action="store_true",
        help=(
            "Redact the database folder path from the bundle's manifest. Some paths "
            "may still appear inside the detailed diagnostic report section."
        ),
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    output_path = args.output or default_output_path()
    try:
        written_path = write_support_bundle(
            output_path,
            log_tail_lines=args.log_lines,
            include_local_paths=not args.no_local_paths,
        )
    except OSError as error:
        print(f"Could not write the support bundle: {error}")
        return 1
    print(f"Support bundle written to {written_path}")
    print("This file is safe to share for support -- it never includes passwords, tokens, or media.")
    if not args.no_local_paths:
        print("It does include local folder paths (which can show your OS username) -- use --no-local-paths to redact those.")
    return 0
