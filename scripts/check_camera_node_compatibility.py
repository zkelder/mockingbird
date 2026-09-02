#!/usr/bin/env python3
"""Host <-> Camera Node Release-Compatibility Preflight v1: a small, bounded
command-line tool that answers "is this Host and this Camera Node
compatible for the capability this Host intends to use," reusing the exact
production `mockingbird.observation.node_compatibility.probe_node_
compatibility` function -- never a second implementation of health
fetching, camera-availability checking, or RTT-bounded clock calibration
(see docs/host-camera-node-release-compatibility-preflight-v1-report.md,
Section 20 of the governing milestone brief).

## What this is (and is not)

This closes the "exercise the preflight against the actual reference
Camera Node now, without starting a long Observation session" need
(Section 25) and formalizes what every prior Representative Daylight Gate
A field-acceptance report has so far done by hand -- "5 real calibration
batches run directly against the Node via the exact unmodified production
functions" (see e.g. the v9 report's own "RTT calibration") -- into one
reusable, scriptable step. It is **not** a field-session launcher: it
never starts, stops, or configures an Observation session, never mutates
Camera Node state, and never SSHes into or upgrades anything (Section 16).
The real *enforcement* for a field-acceptance credential's own Observation
start already runs automatically and unconditionally inside `POST
/api/streams/{stream_id}/observation/start` (see `api/main.py`'s own
`start_stream_observation`) -- this script exists for ad hoc verification
and for Doctor's own diagnostic pointer (`diagnostics/doctor.py`'s
`camera_node` check), not as a replacement for that enforcement.

## Usage

Bounded reachability/RTT check only, no pairing credential needed --
`/node/v1/health` itself requires none (mirrors `CameraNodeClient.health`/
`sample_clock_round_trip` exactly):

    python scripts/check_camera_node_compatibility.py --base-address http://192.168.1.112:8787

Full field-acceptance check against an already-paired camera, including
live camera availability (needs the Source's own stored pairing
credential -- never hold this in shell history; pass it via the
`MOCKINGBIRD_NODE_CREDENTIAL` environment variable instead of `--credential`
when scripting this):

    python scripts/check_camera_node_compatibility.py \\
        --base-address http://192.168.1.112:8787 \\
        --camera-id opaque-camera-1 --credential "$MOCKINGBIRD_NODE_CREDENTIAL"

Ordinary-monitoring profile (only confirms the Node's health protocol
answers at all -- an old, pre-RTT Node is expected to pass this):

    python scripts/check_camera_node_compatibility.py --base-address http://192.168.1.112:8787 --profile ordinary_monitoring

Exit code is 0 for `compatible`, 1 for any other state -- safe to use as a
fail-closed gate in a field-acceptance shell sequence."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import datetime

from mockingbird import __version__ as APP_VERSION
from mockingbird.observation.clock_calibration import RttClockCalibrationRecord
from mockingbird.observation.node_compatibility import (
    DEFAULT_FIELD_ACCEPTANCE_RTT_PROBE_BATCH_SIZE,
    CompatibilityProfile,
    NodeCompatibilityResult,
    probe_node_compatibility,
)
from mockingbird.runtime_state import resolve_build_identity
from mockingbird.source_providers.camera_node import CameraNodeClient

CREDENTIAL_ENV_VAR = "MOCKINGBIRD_NODE_CREDENTIAL"


def _result_to_json(result: NodeCompatibilityResult) -> dict[str, object]:
    payload = asdict(result)
    calibration = payload.get("rtt_calibration")
    if isinstance(calibration, dict):
        # `asdict` recurses into the nested `RttClockCalibrationRecord`
        # dataclass but leaves its own `calibrated_at` field as a real
        # `datetime` (asdict only converts dataclass/list/tuple/dict
        # structure, never an arbitrary leaf value) -- the one field this
        # thin JSON layer must serialize by hand.
        calibrated_at = calibration.get("calibrated_at")
        if isinstance(calibrated_at, datetime):
            calibration["calibrated_at"] = calibrated_at.isoformat()
    return payload


def _print_human(result: NodeCompatibilityResult) -> None:
    print(f"profile:              {result.profile}")
    print(f"state:                {result.state}")
    print(f"compatible:           {result.compatible}")
    print(f"node_reachable:       {result.node_reachable}")
    print(f"required_capabilities: {', '.join(result.required_capabilities)}")
    print(f"missing_capabilities:  {', '.join(result.missing_capabilities) or '(none)'}")
    print(f"host_app_version:     {result.host_app_version}")
    print(f"host_git_commit:      {result.host_git_commit or '(dev checkout -- not a packaged build)'}")
    print(f"node_api_version:     {result.node_api_version}")
    print(f"node_service_version: {result.node_service_version}")
    print(f"camera_available:     {result.camera_available if result.camera_available is not None else '(not checked)'}")
    if result.version_skew_detected:
        print("version_skew_detected: True (informational only -- see the module docstring's own honest disclosure)")
    calibration: RttClockCalibrationRecord | None = result.rtt_calibration
    if calibration is not None:
        print(
            f"rtt_calibration:      state={calibration.state} "
            f"valid_samples={calibration.valid_sample_count}/{calibration.sample_count}"
        )
        if calibration.state == "calibrated":
            print(
                f"  offset_ms={calibration.offset_ms:.1f} "
                f"[{calibration.offset_min_ms:.1f}, {calibration.offset_max_ms:.1f}] "
                f"rtt_ms={calibration.rtt_ms:.1f}"
            )
    print(f"message:              {result.message}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-address", required=True, help="Camera Node base address, e.g. http://192.168.1.112:8787")
    parser.add_argument(
        "--profile", choices=("ordinary_monitoring", "field_acceptance"), default="field_acceptance",
        help="Compatibility profile to evaluate (default: field_acceptance).",
    )
    parser.add_argument("--credential", default=None, help=f"Node pairing credential (prefer {CREDENTIAL_ENV_VAR} instead).")
    parser.add_argument("--camera-id", default=None, help="Expected opaque camera_id this Stream is configured to use.")
    parser.add_argument("--stream-id", default="manual-compatibility-check", help="Label recorded on the RTT calibration result.")
    parser.add_argument("--rtt-batch-size", type=int, default=DEFAULT_FIELD_ACCEPTANCE_RTT_PROBE_BATCH_SIZE)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON instead of a human-readable summary.")
    args = parser.parse_args(argv)

    credential = args.credential or os.environ.get(CREDENTIAL_ENV_VAR)
    if args.camera_id and not credential:
        # `probe_node_compatibility` treats this combination as "camera
        # check not attempted" (it needs both to call the authenticated
        # `/node/v1/cameras` endpoint) -- honest, never a crash, but silent
        # enough from a CLI that a caller who intended a specific-camera
        # check should be told outright rather than seeing an
        # unexpectedly-`None` `camera_available` in the output below.
        print(f"warning: --camera-id given without a credential ({CREDENTIAL_ENV_VAR} unset) -- camera availability will not be checked.", file=sys.stderr)
    git_commit, _ = resolve_build_identity()
    profile: CompatibilityProfile = args.profile
    result = probe_node_compatibility(
        CameraNodeClient(),
        stream_id=args.stream_id,
        profile=profile,
        base_address=args.base_address,
        credential=credential,
        expected_camera_id=args.camera_id,
        host_app_version=APP_VERSION,
        host_git_commit=git_commit,
        rtt_batch_size=args.rtt_batch_size,
    )

    if args.json:
        print(json.dumps(_result_to_json(result), indent=2, default=str))
    else:
        _print_human(result)

    return 0 if result.compatible else 1


if __name__ == "__main__":
    sys.exit(main())
