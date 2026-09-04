"""Structural tests for scripts/field_acceptance_ledger_snapshot.py.

See docs/field-acceptance-evidence-integrity-storage-preflight-
correctness-v1-report.md for the governing milestone. Entirely hermetic
-- every test drives the module against a small in-memory fake
`FieldAcceptanceClient`-shaped object, never a real HTTP call.

Loaded via `runpy.run_path`, matching every other `scripts/` test file's
own established convention.
"""

from __future__ import annotations

from pathlib import Path
import runpy
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
_MODULE = runpy.run_path(str(ROOT / "scripts" / "field_acceptance_ledger_snapshot.py"))
# Deliberately *not* a second `runpy.run_path` of field_acceptance_client.py:
# that would create a second, distinct FieldAcceptanceApiError class object,
# and `except` inside the module under test (which catches its own `_fac()`
# -loaded class) would then never recognize an instance built from this
# file's own separate copy. `_MODULE["_fac"]()` reuses the module under
# test's own cached loader instead, so exceptions this test raises are
# `isinstance`-identical to what `_fetch_artifact`'s `except` actually checks.
_FAC = _MODULE["_fac"]()

take_checkpoint = _MODULE["take_checkpoint"]
run_periodic_collection = _MODULE["run_periodic_collection"]
reconcile_ledger = _MODULE["reconcile_ledger"]
build_merged_counterfactual_window = _MODULE["build_merged_counterfactual_window"]
CHECKPOINT_COMPLETE = _MODULE["CHECKPOINT_COMPLETE"]
CHECKPOINT_PARTIAL = _MODULE["CHECKPOINT_PARTIAL"]
CHECKPOINT_FAILED = _MODULE["CHECKPOINT_FAILED"]
main = _MODULE["main"]

FieldAcceptanceApiError = _FAC["FieldAcceptanceApiError"]
FieldAcceptanceInvalidParameterError = _FAC["FieldAcceptanceInvalidParameterError"]


# ---------------------------------------------------------------------------
# A small fake FieldAcceptanceClient -- scripted per-call outcomes, never a
# real network call.
# ---------------------------------------------------------------------------


class FakeClient:
    def __init__(
        self,
        *,
        ledger_responses: list[Any] | None = None,
        status_response: Any = None,
        scene_confusor_response: Any = None,
    ) -> None:
        # Each entry is either a payload dict to return, or an Exception
        # instance to raise -- one entry consumed per call, in order.
        self._ledger_responses = list(ledger_responses or [])
        self._status_response = status_response if status_response is not None else {"observing": True}
        self._scene_confusor_response = (
            scene_confusor_response if scene_confusor_response is not None
            else {"stream_id": "s1", "reviewed_evidence_enabled": False}
        )
        self.ledger_calls: list[tuple[int, int]] = []

    def observation_counterfactual(self, _stream_id: str, *, start_offset_ms: int, end_offset_ms: int) -> dict:
        self.ledger_calls.append((start_offset_ms, end_offset_ms))
        response = self._ledger_responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def observation_status(self, _stream_id: str) -> dict:
        if isinstance(self._status_response, Exception):
            raise self._status_response
        return self._status_response

    def scene_confusor_learning_status(self, _stream_id: str) -> dict:
        if isinstance(self._scene_confusor_response, Exception):
            raise self._scene_confusor_response
        return self._scene_confusor_response


def _ledger_payload(
    *,
    raw_detections: list[dict] | None = None,
    track_generations: list[dict] | None = None,
    proposal_outcomes: list[dict] | None = None,
    raw_recorded_count: int | None = None,
    track_recorded_count: int | None = None,
    proposal_recorded_count: int | None = None,
    oldest_retained_ms: int = 0,
    newest_retained_ms: int = 1000,
    session_last_offset_ms: int = 1000,
) -> dict:
    raw_detections = raw_detections or []
    track_generations = track_generations or []
    proposal_outcomes = proposal_outcomes or []

    def _coverage(records: list[dict], recorded_count: int | None) -> dict:
        resolved_recorded_count = recorded_count if recorded_count is not None else len(records)
        # Matches the real API's own honest shape (CounterfactualLedgerAccountingResponse /
        # _BoundedOffsetLedger.accounting()): oldest/newest_retained_offset_ms are None
        # whenever nothing was ever recorded for this artifact type -- never a fabricated
        # "retained window" over zero records, which would silently mask the real
        # reconcile_ledger zero-activity-artifact-type bug this test file also covers.
        retained = resolved_recorded_count > 0 or len(records) > 0
        return {
            "retained_count": len(records), "evicted_count": 0,
            "recorded_count": resolved_recorded_count,
            "oldest_retained_offset_ms": oldest_retained_ms if retained else None,
            "newest_retained_offset_ms": newest_retained_ms if retained else None,
        }

    return {
        "stream_id": "s1", "start_offset_ms": 0, "end_offset_ms": 86_400_000, "roi": None,
        "raw_detections": raw_detections, "track_generations": track_generations,
        "proposal_outcomes": proposal_outcomes,
        "raw_detection_count_in_roi": 0, "track_generation_count_in_roi": 0,
        "coverage": {
            "session_first_offset_ms": 0, "session_last_offset_ms": session_last_offset_ms,
            "raw_detections": _coverage(raw_detections, raw_recorded_count),
            "track_generations": _coverage(track_generations, track_recorded_count),
            "proposal_outcomes": _coverage(proposal_outcomes, proposal_recorded_count),
        },
        "attribution": "test", "attribution_reason": "test",
        "clock_calibrations": [], "clock_calibration_required": False, "rtt_clock_calibrations": [],
    }


# ---------------------------------------------------------------------------
# take_checkpoint(): per-artifact success/failure, checkpoint status.
# ---------------------------------------------------------------------------


def test_take_checkpoint_all_artifacts_succeed_is_complete(tmp_path: Path) -> None:
    client = FakeClient(ledger_responses=[_ledger_payload(raw_detections=[{"source_offset_ms": 1}])])

    checkpoint = take_checkpoint(
        client, stream_id="s1", index=0, start_offset_ms=0, end_offset_ms=86_400_000, output_dir=tmp_path,
    )

    assert checkpoint.status == CHECKPOINT_COMPLETE
    assert checkpoint.artifacts["raw_ledger"].success is True
    assert checkpoint.artifacts["raw_ledger"].record_count == 1
    assert checkpoint.artifacts["monitoring_status"].success is True
    assert checkpoint.artifacts["scene_confusor_state"].success is True
    assert Path(checkpoint.output_path).exists()


def test_take_checkpoint_failed_required_ledger_fetch_is_failed_never_complete(tmp_path: Path) -> None:
    """The exact governing-brief invariant: 'A checkpoint with a failed
    required raw-ledger fetch is FAILED/PARTIAL, never silently
    successful.' Reproduces v12's own 422 shape."""

    client = FakeClient(
        ledger_responses=[FieldAcceptanceApiError(422, "end_offset_ms: Field required")],
    )

    checkpoint = take_checkpoint(
        client, stream_id="s1", index=0, start_offset_ms=0, end_offset_ms=86_400_000, output_dir=tmp_path,
    )

    assert checkpoint.status == CHECKPOINT_FAILED
    assert checkpoint.artifacts["raw_ledger"].success is False
    assert "422" in checkpoint.artifacts["raw_ledger"].error
    assert checkpoint.artifacts["raw_ledger"].record_count is None
    # Auxiliary artifacts are independent -- their own outcome is still recorded even though the
    # checkpoint as a whole is FAILED.
    assert checkpoint.artifacts["monitoring_status"].success is True


def test_take_checkpoint_failed_auxiliary_artifact_is_partial_not_failed(tmp_path: Path) -> None:
    client = FakeClient(
        ledger_responses=[_ledger_payload()],
        status_response=FieldAcceptanceApiError(500, "internal error"),
    )

    checkpoint = take_checkpoint(
        client, stream_id="s1", index=0, start_offset_ms=0, end_offset_ms=86_400_000, output_dir=tmp_path,
    )

    assert checkpoint.status == CHECKPOINT_PARTIAL
    assert checkpoint.artifacts["raw_ledger"].success is True
    assert checkpoint.artifacts["monitoring_status"].success is False


def test_take_checkpoint_writes_a_self_contained_json_file(tmp_path: Path) -> None:
    import json

    client = FakeClient(ledger_responses=[_ledger_payload(raw_detections=[{"source_offset_ms": 5}])])

    checkpoint = take_checkpoint(
        client, stream_id="s1", index=3, start_offset_ms=0, end_offset_ms=86_400_000, output_dir=tmp_path,
    )

    on_disk = json.loads(Path(checkpoint.output_path).read_text(encoding="utf-8"))
    assert on_disk["checkpoint"]["index"] == 3
    assert on_disk["checkpoint"]["status"] == "complete"
    assert on_disk["payloads"]["raw_ledger"]["raw_detections"] == [{"source_offset_ms": 5}]


# ---------------------------------------------------------------------------
# run_periodic_collection(): loud failure surfacing, never auto-stopping,
# durable manifest, graceful Ctrl+C.
# ---------------------------------------------------------------------------


def test_run_periodic_collection_reports_a_failed_checkpoint_loudly_on_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture,
) -> None:
    """Governing brief §8/§10: the loop must surface an evidence-integrity
    failure while the run is still recoverable -- not silently, not only
    inferable after the fact. This is the direct fix for what the
    ad hoc, uncommitted v12 `snapshot.py` never did at all."""

    client = FakeClient(
        ledger_responses=[
            _ledger_payload(),
            FieldAcceptanceApiError(422, "end_offset_ms: Field required"),
            _ledger_payload(),
        ],
    )

    checkpoints = run_periodic_collection(
        client, stream_id="s1", output_dir=tmp_path, interval_seconds=0, end_offset_ms=86_400_000,
        max_checkpoints=3, sleep_fn=lambda _seconds: None,
    )

    assert [c.status for c in checkpoints] == [CHECKPOINT_COMPLETE, CHECKPOINT_FAILED, CHECKPOINT_COMPLETE]
    captured = capsys.readouterr()
    assert "EVIDENCE INTEGRITY WARNING" in captured.err
    assert "checkpoint 1" in captured.err


def test_run_periodic_collection_does_not_stop_for_one_transient_failure(tmp_path: Path) -> None:
    """Governing brief §8: 'Do not automatically stop a healthy
    Observation for one transient snapshot failure.' This tool has no
    authority to stop an Observation at all (it never calls
    stop_observation) -- proven here by confirming the loop keeps taking
    checkpoints past a failure rather than raising/aborting."""

    client = FakeClient(
        ledger_responses=[FieldAcceptanceApiError(422, "boom"), _ledger_payload(), _ledger_payload()],
    )

    checkpoints = run_periodic_collection(
        client, stream_id="s1", output_dir=tmp_path, interval_seconds=0, end_offset_ms=86_400_000,
        max_checkpoints=3, sleep_fn=lambda _seconds: None,
    )

    assert len(checkpoints) == 3
    assert len(client.ledger_calls) == 3


def test_run_periodic_collection_manifest_is_durable_after_every_checkpoint(tmp_path: Path) -> None:
    import json

    calls = {"count": 0}

    def sleep_and_check_manifest_exists(_seconds: float) -> None:
        calls["count"] += 1
        manifest = json.loads((tmp_path / "checkpoints-manifest.json").read_text(encoding="utf-8"))
        assert len(manifest) == calls["count"]  # up to date after every single prior checkpoint

    client = FakeClient(ledger_responses=[_ledger_payload(), _ledger_payload(), _ledger_payload()])

    run_periodic_collection(
        client, stream_id="s1", output_dir=tmp_path, interval_seconds=0, end_offset_ms=86_400_000,
        max_checkpoints=3, sleep_fn=sleep_and_check_manifest_exists,
    )

    assert calls["count"] == 2  # sleep is called between checkpoints, not after the last one


def test_run_periodic_collection_stops_gracefully_on_keyboard_interrupt(tmp_path: Path) -> None:
    def sleep_then_interrupt(_seconds: float) -> None:
        raise KeyboardInterrupt

    client = FakeClient(ledger_responses=[_ledger_payload(), _ledger_payload()])

    checkpoints = run_periodic_collection(
        client, stream_id="s1", output_dir=tmp_path, interval_seconds=0, end_offset_ms=86_400_000,
        sleep_fn=sleep_then_interrupt,
    )

    assert len(checkpoints) == 1  # one checkpoint taken, then Ctrl+C during the sleep before the second


def test_run_periodic_collection_never_passes_a_none_end_offset(tmp_path: Path) -> None:
    """Direct proof this tool cannot reproduce v12's own defect: every
    real call this loop makes carries an explicit, real end_offset_ms."""

    client = FakeClient(ledger_responses=[_ledger_payload(), _ledger_payload()])

    run_periodic_collection(
        client, stream_id="s1", output_dir=tmp_path, interval_seconds=0, end_offset_ms=6_000_000,
        max_checkpoints=2, sleep_fn=lambda _seconds: None,
    )

    assert client.ledger_calls == [(0, 6_000_000), (0, 6_000_000)]
    assert all(end is not None for _start, end in client.ledger_calls)


def test_run_periodic_collection_max_checkpoints_zero_takes_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`max_checkpoints=0` must mean 'take none at all' -- checked before
    the loop body runs even once, not just at its end (an off-by-one the
    original `while True: ...; if index >= max_checkpoints: break`
    structure got wrong: it always ran the loop body first)."""

    def _must_not_be_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("take_checkpoint must never run when max_checkpoints=0")

    client = FakeClient(ledger_responses=[_ledger_payload()])
    monkeypatch.setitem(_MODULE, "take_checkpoint", _must_not_be_called)

    checkpoints = run_periodic_collection(
        client, stream_id="s1", output_dir=tmp_path, interval_seconds=0, end_offset_ms=86_400_000,
        max_checkpoints=0, sleep_fn=lambda _seconds: None,
    )

    assert checkpoints == []


def test_fetch_artifact_lets_invalid_parameter_error_propagate_uncaught(tmp_path: Path) -> None:
    """`FieldAcceptanceInvalidParameterError` is a caller-side
    precondition bug (this module itself calling the client wrong), never
    a routine operational failure like a dropped connection -- it must
    crash loudly at the exact call site, not be silently absorbed into
    just another 'FAILED' artifact indistinguishable from a real
    transient network/API error deep in a background loop. This is the
    safety net that keeps the client-level fix (`FieldAcceptanceClient.
    observation_counterfactual`'s own None-guard) from being immediately
    undone one layer up."""

    def _raise_invalid_parameter(*_args: object, **_kwargs: object) -> None:
        raise FieldAcceptanceInvalidParameterError("boom -- a real programming bug, not an operational failure")

    client = FakeClient(ledger_responses=[_ledger_payload()])
    client.observation_counterfactual = _raise_invalid_parameter  # type: ignore[method-assign]

    with pytest.raises(FieldAcceptanceInvalidParameterError):
        take_checkpoint(client, stream_id="s1", index=0, start_offset_ms=0, end_offset_ms=86_400_000, output_dir=tmp_path)


# ---------------------------------------------------------------------------
# reconcile_ledger(): deterministic end-of-run completeness accounting.
# ---------------------------------------------------------------------------


def test_reconcile_ledger_full_coverage_with_no_gaps_is_complete() -> None:
    payload = _ledger_payload(
        raw_detections=[{"source_offset_ms": i} for i in range(5)],
        raw_recorded_count=5, oldest_retained_ms=0, newest_retained_ms=1000, session_last_offset_ms=1000,
    )

    report = reconcile_ledger([payload], stream_id="s1")

    assert report.overall_status == "COMPLETE"
    assert report.artifacts["raw_detections"].status == "COMPLETE"
    assert report.artifacts["raw_detections"].recovered_unique_count == 5
    assert report.artifacts["raw_detections"].gaps_ms == []


def test_reconcile_ledger_reproduces_the_v12_shape_partial_with_named_gap() -> None:
    """The exact v12 evidence-preservation shape: every periodic snapshot
    failed (contributes nothing), one final corrective fetch recovers
    only the retained tail -- a real, quantified, uncovered early window,
    not an assumption of completeness merely because a final fetch
    succeeded."""

    final_payload = _ledger_payload(
        raw_detections=[{"source_offset_ms": i} for i in range(600_000, 1_000_000, 1000)],  # the recovered tail
        raw_recorded_count=22_664, oldest_retained_ms=600_000, newest_retained_ms=1_000_000,
        session_last_offset_ms=1_000_000,
    )
    # 12 failed periodic snapshots contribute nothing -- reconcile_ledger only ever sees successful payloads.
    failed_snapshots: list[dict] = [None] * 12  # type: ignore[list-item]

    report = reconcile_ledger([*failed_snapshots, final_payload], stream_id="s1", included_final_snapshot=True)

    artifact = report.artifacts["raw_detections"]
    assert report.overall_status == "PARTIAL"
    assert artifact.status == "PARTIAL"
    assert artifact.final_recorded_count == 22_664
    assert artifact.recovered_unique_count == 400  # len(range(600_000, 1_000_000, 1000))
    assert artifact.gaps_ms == [(0, 600_000)]  # the exact, precisely-named missing early window
    assert "missing" in artifact.reason


def test_reconcile_ledger_never_reports_complete_for_a_genuinely_partial_recovery() -> None:
    """Governing brief §10: 'a partial checkpoint cannot be reported as
    complete.' However the numbers happen to line up, a real gap must
    never be silently rounded up to COMPLETE."""

    payload = _ledger_payload(
        raw_detections=[{"source_offset_ms": 900}],  # 1 of 2 -- a real, non-trivial gap
        raw_recorded_count=2, oldest_retained_ms=900, newest_retained_ms=1000, session_last_offset_ms=1000,
    )

    report = reconcile_ledger([payload], stream_id="s1")

    assert report.artifacts["raw_detections"].status != "COMPLETE"
    assert report.overall_status == "PARTIAL"


def test_reconcile_ledger_deduplicates_overlapping_snapshots_deterministically() -> None:
    """Governing brief §10: 'duplicate/overlap snapshots reconcile
    deterministically.' Two overlapping periodic snapshots that both
    captured the same real detection must count it once, and the result
    must not depend on which order the payloads are given in."""

    shared = {"source_offset_ms": 100, "frame_id": "f1", "detector_id": "d1", "broad_class": "bird"}
    only_in_first = {"source_offset_ms": 50, "frame_id": "f0", "detector_id": "d1", "broad_class": "bird"}
    only_in_second = {"source_offset_ms": 150, "frame_id": "f2", "detector_id": "d1", "broad_class": "bird"}
    checkpoint_a = _ledger_payload(
        raw_detections=[only_in_first, shared], raw_recorded_count=3,
        oldest_retained_ms=0, newest_retained_ms=200, session_last_offset_ms=200,
    )
    checkpoint_b = _ledger_payload(
        raw_detections=[shared, only_in_second], raw_recorded_count=3,
        oldest_retained_ms=0, newest_retained_ms=200, session_last_offset_ms=200,
    )

    forward = reconcile_ledger([checkpoint_a, checkpoint_b], stream_id="s1")
    reversed_order = reconcile_ledger([checkpoint_b, checkpoint_a], stream_id="s1")

    assert forward.artifacts["raw_detections"].recovered_unique_count == 3  # shared counted once
    assert forward.as_dict() == reversed_order.as_dict()  # order-independent


def test_reconcile_ledger_unknown_when_no_recorded_count_available() -> None:
    payload = _ledger_payload(raw_detections=[{"source_offset_ms": 1}])
    payload["coverage"]["raw_detections"]["recorded_count"] = None  # type: ignore[index]

    report = reconcile_ledger([payload], stream_id="s1")

    assert report.artifacts["raw_detections"].status == "UNKNOWN"
    assert report.overall_status == "PARTIAL"


def test_reconcile_ledger_ignores_failed_none_payloads() -> None:
    report = reconcile_ledger([None, None, _ledger_payload(raw_detections=[{"source_offset_ms": 1}], raw_recorded_count=1)])  # type: ignore[list-item]

    assert report.payloads_considered == 3
    assert report.artifacts["raw_detections"].recovered_unique_count == 1


def test_reconcile_ledger_zero_activity_artifact_is_complete_not_partial() -> None:
    """A real, common, entirely healthy shape: a genuinely quiet session
    where `raw_detections` has real activity but `track_generations`/
    `proposal_outcomes` are honestly empty all session (nothing ever
    crossed the tracker's own confirmation threshold) -- caught by
    review before acceptance: the first version of this reconciliation
    reported this as a full-session PARTIAL gap for the empty artifact
    types (0/0 'recovered', but the entire session window treated as
    'missing' merely because nothing was ever retained), dragging
    `overall_status` to PARTIAL for a session with zero real evidence
    -integrity problems."""

    payload = _ledger_payload(
        raw_detections=[{"source_offset_ms": i} for i in range(5)],
        raw_recorded_count=5, oldest_retained_ms=0, newest_retained_ms=1000, session_last_offset_ms=1000,
        # track_generations/proposal_outcomes left empty -- a genuine
        # zero, not a fetch failure -- per the fixture's own now-honest
        # None-bounds-when-nothing-recorded shape (see _ledger_payload).
    )

    report = reconcile_ledger([payload], stream_id="s1")

    assert report.overall_status == "COMPLETE"
    for artifact_type in ("track_generations", "proposal_outcomes"):
        artifact = report.artifacts[artifact_type]
        assert artifact.status == "COMPLETE"
        assert artifact.final_recorded_count == 0
        assert artifact.recovered_unique_count == 0
        assert artifact.gaps_ms == []
        assert artifact.completeness_fraction == 1.0


def test_reconcile_ledger_still_flags_a_real_gap_alongside_a_genuine_zero_artifact() -> None:
    """The zero-activity fix must not accidentally paper over a real gap
    in a *different*, genuinely non-empty artifact type in the same
    payload."""

    payload = _ledger_payload(
        raw_detections=[{"source_offset_ms": 900}],  # 1 of 2 -- a real gap
        raw_recorded_count=2, oldest_retained_ms=900, newest_retained_ms=1000, session_last_offset_ms=1000,
    )

    report = reconcile_ledger([payload], stream_id="s1")

    assert report.overall_status == "PARTIAL"
    assert report.artifacts["raw_detections"].status == "PARTIAL"
    assert report.artifacts["track_generations"].status == "COMPLETE"  # genuinely empty, unaffected


def test_merge_intervals_drops_malformed_end_before_start_intervals() -> None:
    """A corrupted/hand-edited checkpoint file's malformed interval must
    never be sorted/merged as if valid -- dropped instead."""

    assert _MODULE["_merge_intervals"]([(100, 50), (0, 10)]) == [(0, 10)]


# ---------------------------------------------------------------------------
# build_merged_counterfactual_window(): downstream reuse via
# run_gate_a_measurement_accounting.py.
# ---------------------------------------------------------------------------


def test_build_merged_counterfactual_window_dedupes_and_shapes_for_downstream_reuse() -> None:
    shared_generation = {"generation_id": "g1", "start_offset_ms": 0, "end_offset_ms": 100}
    checkpoint_a = _ledger_payload(track_generations=[shared_generation])
    checkpoint_b = _ledger_payload(
        track_generations=[shared_generation, {"generation_id": "g2", "start_offset_ms": 200, "end_offset_ms": 300}],
    )

    merged = build_merged_counterfactual_window([checkpoint_a, checkpoint_b], stream_id="s1")

    assert merged["stream_id"] == "s1"
    assert [g["generation_id"] for g in merged["track_generations"]] == ["g1", "g2"]
    assert set(merged.keys()) >= {
        "raw_detections", "track_generations", "proposal_outcomes", "coverage",
        "clock_calibrations", "clock_calibration_required", "rtt_clock_calibrations",
    }


def test_build_merged_counterfactual_window_honestly_reports_a_partial_merge() -> None:
    """Caught by review before acceptance: the first version of this
    function unconditionally set `coverage.<artifact>.recorded_count ==
    retained_count`, silently claiming perfect retention for a merge that
    `reconcile_ledger` itself would report as PARTIAL on the identical
    payload set (exactly the v12 shape: recovered only a partial tail).
    A reviewer opening the merged JSON directly -- not just the
    reconcile printout -- must be able to see the same true total and
    the same real gap between recorded and retained."""

    only_the_tail = _ledger_payload(
        raw_detections=[{"source_offset_ms": i} for i in range(600_000, 601_000, 100)],  # 10 records recovered
        raw_recorded_count=22_664, oldest_retained_ms=600_000, newest_retained_ms=601_000,
    )

    merged = build_merged_counterfactual_window([only_the_tail], stream_id="s1")

    coverage = merged["coverage"]["raw_detections"]
    assert coverage["retained_count"] == 10  # what this merge actually contains
    assert coverage["recorded_count"] == 22_664  # the true session total -- never silently claimed as 10
    assert coverage["evicted_count"] == 22_664 - 10


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_reconcile_exit_code_reflects_completeness(tmp_path: Path) -> None:
    import json

    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    payload = _ledger_payload(raw_detections=[{"source_offset_ms": 1}], raw_recorded_count=1)
    (snapshot_dir / "checkpoint-0000.json").write_text(
        json.dumps({"checkpoint": {"index": 0}, "payloads": {"raw_ledger": payload}}), encoding="utf-8",
    )

    exit_code = main(["reconcile", "--snapshot-dir", str(snapshot_dir), "--json"])

    assert exit_code == 0  # fully covered, no gaps


def test_cli_reconcile_writes_merged_output(tmp_path: Path) -> None:
    import json

    snapshot_dir = tmp_path / "snapshots"
    snapshot_dir.mkdir()
    payload = _ledger_payload(raw_detections=[{"source_offset_ms": 1}], raw_recorded_count=1)
    (snapshot_dir / "checkpoint-0000.json").write_text(
        json.dumps({"checkpoint": {"index": 0}, "payloads": {"raw_ledger": payload}}), encoding="utf-8",
    )
    merged_output = tmp_path / "merged.json"

    exit_code = main(["reconcile", "--snapshot-dir", str(snapshot_dir), "--merged-output", str(merged_output)])

    assert exit_code == 0
    merged = json.loads(merged_output.read_text(encoding="utf-8"))
    assert merged["raw_detections"] == [{"source_offset_ms": 1}]
