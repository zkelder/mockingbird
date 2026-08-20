"""Command entry point for the Perception Replay Regression Harness v1.

Three subcommands:

  run           replay a fixture, or an explicit frames/manifest/recording
                 input, through the full additive funnel (detection/
                 tracking -> Visit episode assembly -> shadow admission) and
                 write one combined report.
  list-fixtures  print the named fixtures a registry file declares.
  compare        a deterministic baseline-vs-candidate diff of two already-
                 written reports.

Every safety property `replay_cli.py` already established still holds here:
offline-only, no camera/Camera Node/worker/model-download side effects
beyond what the selected provider itself already does, and admission (when
requested) runs only against a fresh, isolated, disposable repository this
process creates and owns for the duration of one `run` invocation -- never
the real product database.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
import tempfile
from time import perf_counter
from typing import Any

from mockingbird.observation.frame_driven_provider import (
    FRAME_DRIVEN_PROVIDER_VERSION,
    FrameDrivenObservationProvider,
    FrameDrivenProviderConfiguration,
)
from mockingbird.observation.onnx_provider import (
    PROVIDER_VERSION as ONNX_CUDA_PROVIDER_VERSION,
    OnnxCudaObservationProvider,
    OnnxModelBundle,
)
from mockingbird.observation.perception_regression import (
    compare_perception_regression_reports,
    perception_regression_report_to_json,
    run_perception_regression,
    select_time_window,
)
from mockingbird.observation.perception_regression_io import (
    RegressionFixture,
    load_acceptance_recording,
    load_fixture_registry,
)
from mockingbird.observation.replay import ReplayValidationError
from mockingbird.observation.replay_io import ReplayBundle, load_replay_bundle
from mockingbird.observation.replay_io import _safe_output_directory as _replay_safe_output_directory

_EXIT_CODES: dict[str, int] = {
    "unsupported_provider": 4,
    "provider_configuration_required": 9,
    "unknown_fixture": 20,
    "fixture_and_explicit_input_both_given": 21,
    "neither_fixture_nor_explicit_input_given": 22,
    "unsafe_output_path": 6,
    "nonempty_output_directory": 7,
}


def _configured_provider(*, provider_key: str, provider_config_path: Path | None) -> tuple[Any, tuple[str, ...]]:
    """Deliberately small, independent duplication of `replay_cli._
    configured_provider`'s own provider-selection wiring, scoped to the two
    providers that can actually produce Visit proposals worth an admission
    check -- never a modification to `replay_cli.py` itself. Only argparse-
    to-object plumbing is duplicated here; the perception computation this
    calls is the exact same shared, unmodified provider classes."""

    if provider_key == "frame-driven-onnx-cuda":
        if provider_config_path is None:
            raise ReplayValidationError("provider_configuration_required")
        configuration = FrameDrivenProviderConfiguration.load(provider_config_path)
        bundle = OnnxModelBundle.load(configuration.model_bundle_path)
        detector = OnnxCudaObservationProvider(bundle=bundle)
        provider = FrameDrivenObservationProvider(detector=detector, settings=configuration.settings)
        return provider, ("offline ordered-frame replay only", "shadow admission uses an isolated, disposable repository")
    if provider_key == "onnx-cuda":
        if provider_config_path is None:
            raise ReplayValidationError("provider_configuration_required")
        bundle = OnnxModelBundle.load(provider_config_path)
        return OnnxCudaObservationProvider(bundle=bundle), ("detection inference only", "no tracking, no Visit proposals, no admission")
    raise ReplayValidationError("unsupported_provider")


def _bundle_for_fixture(fixture: RegressionFixture) -> ReplayBundle:
    if fixture.source_kind == "acceptance_recording":
        bundle = load_acceptance_recording(
            Path(fixture.frames_path), stream_id=fixture.stream_id, input_id=fixture.fixture_id,
        )
    else:
        if fixture.manifest_path is None:
            raise ReplayValidationError("fixture_missing_manifest_path")
        bundle = load_replay_bundle(Path(fixture.frames_path), Path(fixture.manifest_path))
    if fixture.window_start_ms is not None or fixture.window_end_ms is not None:
        bundle = select_time_window(
            bundle,
            start_offset_ms=fixture.window_start_ms or 0,
            end_offset_ms=fixture.window_end_ms if fixture.window_end_ms is not None else bundle.replay.frames[-1].source_offset_ms,
        )
    return bundle


def _write_report(output_directory: Path, payload: dict[str, Any]) -> Path:
    # Reuses `replay_io.py`'s own output-directory guard verbatim rather than
    # a second, independently-maintained copy: new-or-empty only, refused
    # through a symlink, and -- the property a hand-written duplicate here
    # previously dropped -- refused anywhere under the repository root except
    # `data/` (never `src/`/`docs/`/`tests/`), so a report can never silently
    # land somewhere `git add` might later pick up.
    directory = _replay_safe_output_directory(output_directory)
    output = directory / "perception-regression-report.json"
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode() + b"\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=".perception-regression-report.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(serialized)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, output)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return output


def _run_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("run", help="Replay one fixture or explicit input through the full funnel.")
    parser.add_argument("--fixture", help="A fixture_id from --registry.")
    parser.add_argument("--registry", type=Path, help="Fixture registry JSON (required with --fixture).")
    parser.add_argument("--frames", type=Path, help="Explicit frames directory (mutually exclusive with --fixture).")
    parser.add_argument("--manifest", type=Path, help="Explicit benchmark manifest JSON.")
    parser.add_argument("--recording", type=Path, help="Explicit acceptance-recording directory (no manifest needed).")
    parser.add_argument("--stream-id", help="Required with --frames/--recording; must start with 'replay:' if admission runs.")
    parser.add_argument("--provider", default="frame-driven-onnx-cuda")
    parser.add_argument("--provider-config", type=Path)
    parser.add_argument("--window-start-ms", type=int)
    parser.add_argument("--window-end-ms", type=int)
    parser.add_argument("--base-observed-at", help="ISO-8601; defaults to 2026-01-01T00:00:00+00:00.")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--admission", dest="admission", action="store_true", default=True)
    parser.add_argument("--no-admission", dest="admission", action="store_false")
    parser.add_argument("--output", required=True, type=Path)


async def _run(args: argparse.Namespace) -> int:
    if args.fixture is not None:
        if args.frames is not None or args.recording is not None:
            raise ReplayValidationError("fixture_and_explicit_input_both_given")
        if args.registry is None:
            raise ReplayValidationError("registry_required_with_fixture")
        registry = load_fixture_registry(args.registry)
        fixture = registry.get(args.fixture)
        if fixture is None:
            raise ReplayValidationError("unknown_fixture")
        bundle = _bundle_for_fixture(fixture)
        provider_key = fixture.provider_key
        provider_config_path = Path(fixture.provider_config_path) if fixture.provider_config_path else None
        base_observed_at = fixture.base_observed_at or datetime(2026, 1, 1, tzinfo=UTC)
    else:
        if args.frames is None and args.recording is None:
            raise ReplayValidationError("neither_fixture_nor_explicit_input_given")
        if args.stream_id is None:
            raise ReplayValidationError("stream_id_required")
        if args.recording is not None:
            bundle = load_acceptance_recording(
                args.recording, stream_id=args.stream_id, input_id=args.recording.name,
                window_start_ms=args.window_start_ms, window_end_ms=args.window_end_ms,
            )
        else:
            if args.manifest is None:
                raise ReplayValidationError("manifest_required_with_frames")
            bundle = load_replay_bundle(args.frames, args.manifest)
            if args.window_start_ms is not None or args.window_end_ms is not None:
                bundle = select_time_window(
                    bundle, start_offset_ms=args.window_start_ms or 0,
                    end_offset_ms=args.window_end_ms if args.window_end_ms is not None else bundle.replay.frames[-1].source_offset_ms,
                )
        provider_key = args.provider
        provider_config_path = args.provider_config
        base_observed_at = (
            datetime.fromisoformat(args.base_observed_at) if args.base_observed_at else datetime(2026, 1, 1, tzinfo=UTC)
        )

    provider, limitations = _configured_provider(provider_key=provider_key, provider_config_path=provider_config_path)
    close = getattr(provider, "close", None)
    try:
        if isinstance(provider, (OnnxCudaObservationProvider, FrameDrivenObservationProvider)):
            provider.load()
        started = perf_counter()
        report = await run_perception_regression(
            bundle, provider=provider, provider_key=provider_key, run_admission=args.admission,
            base_observed_at=base_observed_at, seed=args.seed,
        )
        duration_ms = round((perf_counter() - started) * 1000, 3)
        payload = perception_regression_report_to_json(report)
        payload["limitations"] = sorted(limitations)
        payload["execution"] = {
            "mode": "offline", "total_execution_duration_ms": duration_ms, "frame_count": len(bundle.replay.frames),
        }
        if isinstance(provider, FrameDrivenObservationProvider):
            payload["execution"].update(provider.execution_facts())
            payload["provider_version"] = FRAME_DRIVEN_PROVIDER_VERSION
        elif isinstance(provider, OnnxCudaObservationProvider):
            payload["execution"].update(provider.execution_facts())
            payload["provider_version"] = ONNX_CUDA_PROVIDER_VERSION
        report_path = _write_report(args.output, payload)
    finally:
        if callable(close):
            close()
    print(f"Perception regression report written to {report_path}; semantic fingerprint {report.semantic_fingerprint}.")
    return 0


def _list_fixtures_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("list-fixtures", help="Print the fixtures a registry declares.")
    parser.add_argument("--registry", required=True, type=Path)


def _list_fixtures(args: argparse.Namespace) -> int:
    registry = load_fixture_registry(args.registry)
    for fixture_id in sorted(registry):
        fixture = registry[fixture_id]
        print(f"{fixture_id}\t{fixture.source_kind}\t{fixture.description}")
    return 0


def _compare_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("compare", help="Deterministic baseline-vs-candidate diff of two reports.")
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output", type=Path)


def _compare(args: argparse.Namespace) -> int:
    from mockingbird.observation.admission_replay import AdmissionReplayReport
    from mockingbird.observation.replay import ReplayReport, VisitEpisodeAssemblyReport

    def _load(path: Path) -> dict[str, Any]:
        if path.is_symlink() or not path.is_file():
            raise ReplayValidationError("unsafe_report_path")
        return json.loads(path.read_text(encoding="utf-8"))

    baseline_payload = _load(args.baseline)
    candidate_payload = _load(args.candidate)

    def _report_from_payload(payload: dict[str, Any]):
        from mockingbird.observation.perception_regression import PerceptionFunnelReport, RegressionRunProvenance

        replay = ReplayReport((), (), (), payload["replay"]["metrics"], payload["replay"]["semantic_fingerprint"],
            tuple(payload["replay"]["threshold_results"]))
        assembly = VisitEpisodeAssemblyReport((), (), {}, payload["assembly"]["assembly_metrics"],
            payload["assembly"]["visit_truth_metrics"], payload["assembly"]["semantic_fingerprint"])
        admission_payload = payload.get("admission")
        admission = None
        if admission_payload is not None:
            admission = AdmissionReplayReport(
                stream_id=admission_payload["stream_id"], outcomes=(),
                arbitration=__import__("mockingbird.observation.candidate_visit_authority", fromlist=["AmbiguousBoundaryArbitration"]).AmbiguousBoundaryArbitration(frozenset(), frozenset()),
                outcome_counts=admission_payload["outcome_counts"],
            )
        provenance = RegressionRunProvenance(**payload["provenance"])
        return PerceptionFunnelReport(replay, assembly, admission, provenance, payload["semantic_fingerprint"])

    diff = compare_perception_regression_reports(_report_from_payload(baseline_payload), _report_from_payload(candidate_payload))
    text = json.dumps(diff, sort_keys=True, indent=2, default=str)
    if args.output is not None:
        # A single named output *file*, not the `run` subcommand's own
        # new-or-empty output *directory* convention -- only refuse a
        # symlinked destination and a missing parent, never an already-
        # populated sibling directory.
        destination = args.output.expanduser()
        if destination.is_symlink():
            raise ReplayValidationError("unsafe_output_path")
        if not destination.parent.exists():
            raise ReplayValidationError("unsafe_output_path")
        destination.write_text(text + "\n", encoding="utf-8")
        print(f"Comparison written to {destination}.")
    else:
        print(text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Perception Replay Regression Harness v1.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    _run_parser(subparsers)
    _list_fixtures_parser(subparsers)
    _compare_parser(subparsers)
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "run":
            return asyncio.run(_run(args))
        if args.command == "list-fixtures":
            return _list_fixtures(args)
        if args.command == "compare":
            return _compare(args)
        raise ReplayValidationError("unknown_command")
    except ReplayValidationError as error:
        print(f"Perception regression harness rejected: {error}", file=sys.stderr)
        return _EXIT_CODES.get(str(error), 2)


def main() -> None:
    raise SystemExit(run())
