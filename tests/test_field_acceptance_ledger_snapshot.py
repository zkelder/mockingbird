"""Structural tests for scripts/field_acceptance_ledger_snapshot.py.

See docs/field-acceptance-evidence-integrity-storage-preflight-
correctness-v1-report.md for the governing milestone. Entirely hermetic
-- every test drives the module against a small in-memory fake
`FieldAcceptanceClient`-shaped object, never a real HTTP call.

Loaded via `runpy.run_path`, matching every other `scripts/` test file's
own established convention.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import runpy
from typing import Any

import pytest

from mockingbird.observation.counterfactual_lineage import CounterfactualLedger, CounterfactualRetentionConfig
from mockingbird.observation.visit_episode_assembler import AssembledVisitProposal

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
_proposal_outcome_identity = _MODULE["_proposal_outcome_identity"]
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


def test_reconcile_ledger_equal_recovered_and_recorded_counts_still_reports_partial_when_a_real_gap_exists() -> None:
    """Field Acceptance Tooling Correctness & Preflight Closure v1
    (governing brief §6): 'Require an explicit completeness verdict based
    on actual snapshot coverage, not merely equal record counts.' Two
    non-corroborating checkpoints together recover exactly as many unique
    records as the session's own true final total (5 == 5) -- a naive
    'recovered count == recorded count' check would call this COMPLETE --
    but their own reported retained-offset windows ([0, 400] and [600,
    1000]) leave a real, unproven 200ms gap between them. The count
    matching is coincidental (the two payloads' own `recorded_count`
    values deliberately do *not* independently corroborate the same final
    total -- 3 and 5 -- so the 'two-or-more-independent-payloads-agree'
    trailing-rule shortcut in `_accumulate_artifact` never fires here);
    only the interval-gap analysis -- already the real, pre-existing logic
    this asserts, not a change -- catches it."""

    payload_a = _ledger_payload(
        raw_detections=[{"source_offset_ms": 50}, {"source_offset_ms": 150}, {"source_offset_ms": 350}],
        raw_recorded_count=3, oldest_retained_ms=0, newest_retained_ms=400, session_last_offset_ms=1000,
    )
    payload_b = _ledger_payload(
        raw_detections=[{"source_offset_ms": 650}, {"source_offset_ms": 950}],
        raw_recorded_count=5, oldest_retained_ms=600, newest_retained_ms=1000, session_last_offset_ms=1000,
    )

    report = reconcile_ledger([payload_a, payload_b], stream_id="s1")

    artifact = report.artifacts["raw_detections"]
    assert artifact.recovered_unique_count == 5
    assert artifact.final_recorded_count == 5  # counts are equal ...
    assert artifact.gaps_ms == [(400, 600)]  # ... but a real, uncovered window still exists
    assert artifact.status == "PARTIAL"  # never rounded up to COMPLETE merely because the counts matched
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


# ---------------------------------------------------------------------------
# Proposal-Outcome Ledger Retention & Field-Reconciliation Completeness v1:
# `proposal_outcomes` is an append-only decision-EVENT log (a retryable
# `blocked_continuation_pending` proposal legitimately accumulates several
# independent decision events over a session), not a per-proposal state
# table -- `proposal_id` alone was the wrong reconciliation identity for
# this one artifact type. Everything below exercises the fix directly
# against dict fixtures (fast, focused unit coverage) and, for the
# highest-value proofs, against the REAL `CounterfactualLedger` (real
# production retention config, real `record_proposal_outcome`/`query`) so
# the retention/eviction/query mechanism itself is genuinely exercised,
# never assumed. See docs/proposal-outcome-ledger-retention-field
# -reconciliation-completeness-v1-report.md.
# ---------------------------------------------------------------------------


def test_reconcile_ledger_proposal_outcomes_retryable_decisions_all_recovered_are_complete() -> None:
    """The direct fix, at unit scale: one `proposal_id` decided three
    times (two `blocked_continuation_pending` retries, one terminal) --
    all three are distinct, legitimate decision events, and completeness
    must be judged against that event count (3), never silently
    collapsed to a per-proposal count (1) that would make a fully-
    recovered session look like a 33%-complete one."""

    def _decision(decided_at: str, outcome: str) -> dict:
        return {
            "proposal_id": "p1", "broad_class": "animal", "zone_id": None,
            "start_offset_ms": 1_000, "end_offset_ms": 3_000, "constituent_generation_ids": ["gen-1"],
            "outcome": outcome, "reason": "test", "admitted": outcome == "created", "visit_id": None,
            "decided_at": decided_at,
        }

    payload = _ledger_payload(
        proposal_outcomes=[
            _decision("2026-09-04T19:30:00.000Z", "blocked_continuation_pending"),
            _decision("2026-09-04T19:30:10.000Z", "blocked_continuation_pending"),
            _decision("2026-09-04T19:30:20.000Z", "blocked_missing_evidence"),
        ],
        proposal_recorded_count=3, oldest_retained_ms=0, newest_retained_ms=3_000, session_last_offset_ms=3_000,
    )

    report = reconcile_ledger([payload], stream_id="s1")

    artifact = report.artifacts["proposal_outcomes"]
    assert artifact.final_recorded_count == 3
    assert artifact.recovered_unique_count == 3  # all three events, never collapsed to 1
    assert artifact.recovered_distinct_entity_count == 1  # informational: one underlying proposal
    assert artifact.completeness_fraction == 1.0
    assert artifact.status == "COMPLETE"
    assert "distinct proposal_ids" in artifact.reason


def test_reconcile_ledger_proposal_outcomes_genuinely_missing_event_is_still_partial() -> None:
    """The fix must not swing to the opposite failure mode: if a real
    decision event for an already-seen `proposal_id` was never captured
    by any checkpoint, that is still a real, honestly-reported gap -- the
    new `(proposal_id, decided_at)` identity must not accidentally treat
    'we already have *a* record for this proposal' as 'we have *every*
    record for this proposal.'"""
    payload = _ledger_payload(
        proposal_outcomes=[
            {
                "proposal_id": "p1", "broad_class": "animal", "zone_id": None,
                "start_offset_ms": 1_000, "end_offset_ms": 3_000, "constituent_generation_ids": ["gen-1"],
                "outcome": "blocked_continuation_pending", "reason": "test", "admitted": False, "visit_id": None,
                "decided_at": "2026-09-04T19:30:00.000Z",
            },
        ],
        proposal_recorded_count=2,  # the ledger's own truth: 2 decision events actually happened for p1
        oldest_retained_ms=1_000, newest_retained_ms=3_000, session_last_offset_ms=3_000,
    )

    report = reconcile_ledger([payload], stream_id="s1")

    artifact = report.artifacts["proposal_outcomes"]
    assert artifact.final_recorded_count == 2
    assert artifact.recovered_unique_count == 1
    assert artifact.recovered_distinct_entity_count == 1
    assert artifact.status == "PARTIAL"
    assert report.overall_status == "PARTIAL"


def test_reconcile_ledger_raw_detections_and_track_generations_report_no_distinct_entity_count() -> None:
    """`recovered_distinct_entity_count` is specific to `proposal_
    outcomes` -- for the other two artifact types, identity already *is*
    the entity, so a separate count would be meaningless noise, not a new
    fact. Must stay `None`, not silently `0` or equal to `recovered_
    unique_count`."""
    payload = _ledger_payload(
        raw_detections=[{"source_offset_ms": i} for i in range(3)], raw_recorded_count=3,
    )

    report = reconcile_ledger([payload], stream_id="s1")

    assert report.artifacts["raw_detections"].recovered_distinct_entity_count is None
    assert report.artifacts["track_generations"].recovered_distinct_entity_count is None


def test_reconcile_ledger_zero_activity_proposal_outcomes_reports_zero_distinct_entities() -> None:
    """The prior accepted zero-activity fix must keep working unchanged --
    and the new entity count must honestly report zero, not `None`, for a
    genuinely-empty `proposal_outcomes` artifact (identity is still
    meaningful for this artifact type; there are simply no records)."""
    payload = _ledger_payload(
        raw_detections=[{"source_offset_ms": 1}], raw_recorded_count=1,
    )

    report = reconcile_ledger([payload], stream_id="s1")

    artifact = report.artifacts["proposal_outcomes"]
    assert artifact.status == "COMPLETE"
    assert artifact.recovered_distinct_entity_count == 0


def test_build_merged_counterfactual_window_preserves_full_proposal_outcome_history() -> None:
    """`build_merged_counterfactual_window` shares `_accumulate_artifact`
    with `reconcile_ledger` by design (see that helper's own docstring) --
    confirms the fix applies to the merged-output path too, not only the
    reconciliation percentage. The accepted downstream consumer
    (`encounter_accounting.cluster_encounters`, see `tests/test_encounter
    _accounting.py::test_proposal_outcomes_populate_cluster_lineage_
    deduplicated_by_proposal_id`) is already specifically designed to
    receive this full, undeduplicated history and reduce it itself via
    its own established `_decision_offset`-latest-wins rule -- this merge
    step must never pre-empt that reduction with a cruder, checkpoint
    -iteration-order-dependent one of its own."""
    pending = {
        "proposal_id": "p1", "broad_class": "animal", "zone_id": None,
        "start_offset_ms": 1_000, "end_offset_ms": 3_000, "constituent_generation_ids": ["gen-1"],
        "outcome": "blocked_continuation_pending", "reason": "test", "admitted": False, "visit_id": None,
        "decided_at": "2026-09-04T19:30:00.000Z",
    }
    created = {**pending, "outcome": "created", "admitted": True, "visit_id": "visit-1", "decided_at": "2026-09-04T19:30:10.000Z"}
    payload = _ledger_payload(proposal_outcomes=[pending, created], proposal_recorded_count=2)

    merged = build_merged_counterfactual_window([payload], stream_id="s1")

    assert len(merged["proposal_outcomes"]) == 2  # both survive -- never collapsed by proposal_id alone
    outcomes = {item["decided_at"]: item["outcome"] for item in merged["proposal_outcomes"]}
    assert outcomes["2026-09-04T19:30:00.000Z"] == "blocked_continuation_pending"
    assert outcomes["2026-09-04T19:30:10.000Z"] == "created"
    assert merged["coverage"]["proposal_outcomes"]["recorded_count"] == 2
    assert merged["coverage"]["proposal_outcomes"]["retained_count"] == 2


# --- Real-ledger, v13-shaped high-churn reproduction ------------------------


_V13_STREAM_ID = "stream-v13-shaped"
_V13_SESSION_MS = 6_081_819  # v13's own real session_last_offset_ms
_V13_CHECKPOINT_INTERVAL_MS = 300_000  # v13's own real 5-minute collection cadence
_V13_TICK_MS = 10_000  # engine_runtime._ASSEMBLY_TICK_SECONDS


def _window_to_payload(window: Any) -> dict:
    """Minimal, hand-rolled mirror of `mockingbird.api.main._counterfactual_
    window_response`'s own field mapping -- only the subset `reconcile_
    ledger`/`build_merged_counterfactual_window` actually read. Deliberately
    not an import of `mockingbird.api.main` (a large, FastAPI-app-importing
    module with its own heavy dependency closure) -- this keeps the
    real-ledger tests below fast and focused precisely on the
    `counterfactual_lineage` <-> field-acceptance-tool boundary this
    milestone is about."""

    def _accounting(accounting: Any) -> dict:
        return {
            "retained_count": accounting.retained_count, "evicted_count": accounting.evicted_count,
            "recorded_count": accounting.recorded_count,
            "oldest_retained_offset_ms": accounting.oldest_retained_offset_ms,
            "newest_retained_offset_ms": accounting.newest_retained_offset_ms,
        }

    return {
        "stream_id": window.stream_id, "start_offset_ms": window.start_offset_ms,
        "end_offset_ms": window.end_offset_ms, "roi": None,
        "raw_detections": [], "track_generations": [],
        "proposal_outcomes": [
            {
                "proposal_id": item.proposal_id, "stream_id": item.stream_id, "broad_class": item.broad_class,
                "zone_id": item.zone_id, "start_offset_ms": item.start_offset_ms, "end_offset_ms": item.end_offset_ms,
                "constituent_generation_ids": list(item.constituent_generation_ids),
                "outcome": item.outcome, "reason": item.reason, "admitted": item.admitted,
                "visit_id": item.visit_id, "decided_at": item.decided_at.isoformat(),
            }
            for item in window.proposal_outcomes
        ],
        "raw_detection_count_in_roi": 0, "track_generation_count_in_roi": 0,
        "coverage": {
            "session_first_offset_ms": window.coverage.session_first_offset_ms,
            "session_last_offset_ms": window.coverage.session_last_offset_ms,
            "raw_detections": _accounting(window.coverage.raw_detection_retention),
            "track_generations": _accounting(window.coverage.track_generation_retention),
            "proposal_outcomes": _accounting(window.coverage.proposal_outcome_retention),
        },
        "attribution": "test", "attribution_reason": "test",
        "clock_calibrations": [], "clock_calibration_required": False, "rtt_clock_calibrations": [],
    }


def _v13_shaped_proposal_plan() -> list[int]:
    """The exact per-proposal decision-event-count histogram independently
    reconstructed from Representative Daylight Gate A Field Acceptance
    v13's own archived `raw-periodic-snapshots` (union across all 21 real
    checkpoints, `data/field-acceptance/2026-09-04-gate-a-v13-intact
    -ledger-budget-convergence/`, not committed -- see the governing
    report for the full derivation): 156 distinct proposals -- 92 decided
    exactly once, 11 decided twice, 7 three times, 15 four times, 31 five
    times. 92+11+7+15+31=156 proposals; 92+22+21+60+155=350 total decision
    events -- matching v13's own real `proposals_observed`/ledger
    `recorded_count` exactly."""
    plan: list[int] = [1] * 92 + [2] * 11 + [3] * 7 + [4] * 15 + [5] * 31
    assert len(plan) == 156
    assert sum(plan) == 350
    return plan


def _make_proposal(proposal_id: str, generation_id: str, *, start_offset_ms: int) -> AssembledVisitProposal:
    return AssembledVisitProposal(
        proposal_id=proposal_id, stream_id=_V13_STREAM_ID, broad_class="animal",
        start_offset_ms=start_offset_ms, end_offset_ms=start_offset_ms + 2_000,
        constituent_generation_ids=(generation_id,), constituent_track_ids=(f"{generation_id}-track",),
        supporting_frame_ids=(), source_capture_frame_ids=(), evidence_candidate_ids=(),
        assembly_decisions=(),
    )


def _run_v13_shaped_session(
    *, ledger: CounterfactualLedger | None = None, checkpoint_interval_ms: int = _V13_CHECKPOINT_INTERVAL_MS,
) -> tuple[CounterfactualLedger, list[dict]]:
    """Drives the REAL `CounterfactualLedger` (production retention config
    by default) through a deterministic, v13-shaped high-churn session --
    156 distinct proposals spread across the real session span, each
    re-decided per `_v13_shaped_proposal_plan`'s own real histogram (every
    non-final decision `blocked_continuation_pending`, one real assembly
    -tick apart; the final decision `blocked_missing_evidence`, matching
    v13's own 88.5%-dominant real outcome) -- with periodic-checkpoint
    queries genuinely *interleaved* with live appends (never built after
    the fact against an already-complete ledger), exactly mirroring how a
    real live session and a real detached periodic collector run
    concurrently. Deterministic: proposal start offsets are evenly spaced
    across the real session span -- the real session's own bursty
    clustering is not needed to prove the identity/retention mechanism,
    only its real event-count/multiplicity shape (see the burst-churn test
    below for an explicitly bursty scenario)."""
    ledger = ledger or CounterfactualLedger(stream_id=_V13_STREAM_ID)
    plan = _v13_shaped_proposal_plan()
    now = datetime(2026, 9, 4, 19, 25, 22, tzinfo=UTC)
    spacing_ms = _V13_SESSION_MS // len(plan)

    events: list[tuple[int, AssembledVisitProposal, str, str]] = []
    for index, decision_count in enumerate(plan):
        # index 0 starts at offset 0 deliberately -- this fixture is about
        # proving the identity/count fix, not about the separate,
        # pre-existing, unrelated "no activity before the first-ever
        # decision" leading-gap convention `_gaps_in`'s own `window_start=0`
        # anchor already applies (matching v13's own real report, which
        # similarly never treated its own pre-first-encounter window as a
        # defect for any artifact).
        proposal = _make_proposal(f"proposal-{index:04d}", f"gen-{index:04d}", start_offset_ms=spacing_ms * index)
        for attempt in range(decision_count):
            decided_offset_ms = proposal.start_offset_ms + attempt * _V13_TICK_MS
            is_final = attempt == decision_count - 1
            outcome = "blocked_missing_evidence" if is_final else "blocked_continuation_pending"
            reason = "no_persistable_evidence_bytes" if is_final else "episode_boundary_not_yet_final"
            events.append((decided_offset_ms, proposal, outcome, reason))
    events.sort(key=lambda item: item[0])  # strict chronological decision order, matching real tick order

    def _record(decided_offset_ms: int, proposal: AssembledVisitProposal, outcome: str, reason: str) -> None:
        ledger.record_proposal_outcome(
            proposal, outcome=outcome, reason=reason, visit_id=None,
            decided_at=now + timedelta(milliseconds=decided_offset_ms), known_horizon_ms=decided_offset_ms,
        )

    payloads: list[dict] = []
    event_index = 0
    next_checkpoint_ms = checkpoint_interval_ms
    while event_index < len(events):
        decided_offset_ms, proposal, outcome, reason = events[event_index]
        if decided_offset_ms <= next_checkpoint_ms:
            _record(decided_offset_ms, proposal, outcome, reason)
            event_index += 1
            continue
        # This checkpoint's own fixed-cadence boundary has arrived --
        # take it now, before advancing further, mirroring the real
        # collector's own wall-clock timer, indifferent to how much/little
        # decision activity happened in this particular interval.
        payloads.append(_window_to_payload(ledger.query(start_offset_ms=0, end_offset_ms=86_400_000)))
        next_checkpoint_ms += checkpoint_interval_ms
    for decided_offset_ms, proposal, outcome, reason in events[event_index:]:
        _record(decided_offset_ms, proposal, outcome, reason)
    # The final checkpoint, matching v13's own real "the last one landing
    # exactly at the stop moment" precedent.
    payloads.append(_window_to_payload(ledger.query(start_offset_ms=0, end_offset_ms=86_400_000)))
    return ledger, payloads


def test_reconcile_ledger_v13_shaped_high_churn_session_is_fully_complete() -> None:
    """Proposal-Outcome Ledger Retention & Field-Reconciliation
    Completeness v1's own primary reproducer (governing brief §17): the
    real `CounterfactualLedger`, real production retention config
    (`CounterfactualRetentionConfig()` defaults, unmodified), real
    v13-shaped churn (156 distinct proposals / 350 decision events, using
    v13's own real per-proposal decision-count histogram), a real
    300-second periodic-checkpoint cadence -- reconciled through the fixed
    `reconcile_ledger`. Before this milestone's fix (independently
    confirmed via `git stash` bisection against the pre-fix `proposal_id`
    -only identity -- see the governing report's "V13-shaped RED->GREEN"
    section), this exact fixture reconciled to a misleadingly PARTIAL
    result matching v13's own real 44.6%-completeness shape; the session
    itself has genuinely zero data loss (every one of the 350 real
    decision events is recoverable across the real checkpoint cadence --
    the 60-minute retention window is never even approached being outrun
    by the 5-minute cadence), and the fixed tool now says so."""
    _ledger, payloads = _run_v13_shaped_session()

    report = reconcile_ledger(payloads, stream_id=_V13_STREAM_ID)

    artifact = report.artifacts["proposal_outcomes"]
    assert artifact.final_recorded_count == 350
    assert artifact.recovered_unique_count == 350
    assert artifact.recovered_distinct_entity_count == 156
    assert artifact.completeness_fraction == 1.0
    assert artifact.gaps_ms == []
    assert artifact.status == "COMPLETE"
    assert report.overall_status == "COMPLETE"

    merged = build_merged_counterfactual_window(payloads, stream_id=_V13_STREAM_ID)
    assert len(merged["proposal_outcomes"]) == 350
    assert merged["coverage"]["proposal_outcomes"]["recorded_count"] == 350
    assert merged["coverage"]["proposal_outcomes"]["retained_count"] == 350
    assert merged["coverage"]["proposal_outcomes"]["evicted_count"] == 0


def test_reconcile_ledger_v13_shaped_session_pre_fix_identity_reproduces_44_percent_shape() -> None:
    """Direct, permanent proof of the historical defect shape -- calling
    the *old*, `proposal_id`-only identity function against the identical
    v13-shaped fixture reproduces the exact misleading-PARTIAL failure
    class (not the specific 44.6% figure, which depends on v13's own real
    session timing/offsets this synthetic fixture does not reproduce
    byte-for-byte -- see the governing report for the real-data
    confirmation of the literal 44.6%). Guards against ever silently
    reintroducing `proposal_id`-only identity for this artifact type."""
    _ledger, payloads = _run_v13_shaped_session()

    def _old_proposal_id_only_identity(record: dict) -> Any:
        return record.get("proposal_id")

    _MODULE["_IDENTITY_FN"]["proposal_outcomes"] = _old_proposal_id_only_identity
    try:
        report = reconcile_ledger(payloads, stream_id=_V13_STREAM_ID)
    finally:
        _MODULE["_IDENTITY_FN"]["proposal_outcomes"] = _proposal_outcome_identity

    artifact = report.artifacts["proposal_outcomes"]
    assert artifact.recovered_unique_count == 156  # collapsed to distinct proposal_ids, the historical bug shape
    assert artifact.final_recorded_count == 350
    assert artifact.status == "PARTIAL"  # a fully-intact, zero-loss session misreported as PARTIAL
    assert artifact.completeness_fraction is not None and artifact.completeness_fraction < 0.5


def test_reconcile_ledger_burst_churn_no_accidental_event_collapse() -> None:
    """Burst-churn proof (governing brief §18): 200 single-shot decisions
    inside one ~10-second window (a fallback-chain-shaped burst, matching
    v13's own real 'one chain tried at least 27 ranked positions' shape,
    scaled up) plus one proposal that churns `blocked_continuation_
    pending` across three separate, overlapping 300-second checkpoint
    intervals before finally resolving -- proves no accidental identity
    -driven collapse under load, using the real ledger and the fixed
    identity."""
    ledger = CounterfactualLedger(stream_id="stream-burst")
    now = datetime(2026, 9, 4, 12, 0, 0, tzinfo=UTC)

    # Build the full event schedule up front, then append in strict
    # chronological (offset) order -- the real ledger's own bounded
    # retention (`_BoundedOffsetLedger`) assumes non-decreasing append
    # offsets, exactly as a real live session always produces (`known_
    # horizon_ms` only ever advances); appending out of that order is a
    # fixture bug, never a real production shape.
    events: list[tuple[int, AssembledVisitProposal, str, str]] = []
    for i in range(200):
        offset_ms = 900_000 + i * 50
        events.append((
            offset_ms, _make_proposal(f"burst-{i:04d}", f"burst-gen-{i:04d}", start_offset_ms=offset_ms),
            "blocked_missing_evidence", "no_persistable_evidence_bytes",
        ))
    # Starts at offset 0 deliberately -- see `_run_v13_shaped_session`'s own
    # comment on why this fixture avoids the separate, pre-existing,
    # unrelated "no activity before the first-ever decision" leading-gap
    # convention rather than conflating it with what this test is about.
    churning = _make_proposal("burst-churn", "burst-churn-gen", start_offset_ms=0)
    churn_offsets = [0, 300_000, 600_000, 890_000]
    for offset_ms in churn_offsets[:-1]:
        events.append((offset_ms, churning, "blocked_continuation_pending", "episode_boundary_not_yet_final"))
    events.append((churn_offsets[-1], churning, "blocked_missing_evidence", "no_persistable_evidence_bytes"))
    events.sort(key=lambda item: item[0])

    for offset_ms, proposal, outcome, reason in events:
        ledger.record_proposal_outcome(
            proposal, outcome=outcome, reason=reason, visit_id=None,
            decided_at=now + timedelta(milliseconds=offset_ms), known_horizon_ms=offset_ms,
        )

    # Five overlapping checkpoints, all taken after every event above --
    # governing brief §18's own "overlapping checkpoints" case: identical,
    # fully-overlapping payloads must reconcile to the same real total,
    # never inflate or deflate it.
    payloads = [_window_to_payload(ledger.query(start_offset_ms=0, end_offset_ms=86_400_000)) for _ in range(5)]

    report = reconcile_ledger(payloads, stream_id="stream-burst")
    artifact = report.artifacts["proposal_outcomes"]

    assert artifact.final_recorded_count == 204  # 200 single-shot + 4 for the churning proposal
    assert artifact.recovered_unique_count == 204
    assert artifact.recovered_distinct_entity_count == 201  # 200 + the one churning proposal
    assert artifact.status == "COMPLETE"
    assert artifact.gaps_ms == []


def test_reconcile_ledger_deliberately_exceeded_retention_is_honest_partial_never_complete() -> None:
    """Bounded-eviction proof (governing brief §19): deliberately
    configure a retention window shorter than the checkpoint interval (a
    genuinely mis-configured/adversarial pairing -- the opposite of this
    milestone's own locked-safe default, where the interval is a small
    fraction of the retention window) and confirm the fixed reconciler
    still correctly reports PARTIAL with a real, non-empty gap and an
    accurate missing count -- proving the identity fix does not
    accidentally mask a genuine retention/cadence shortfall. Memory/
    storage stays bounded throughout (the real `_BoundedOffsetLedger`,
    unmodified); only the *test's own* deliberately adversarial config/
    cadence pairing is new."""
    tiny_retention = CounterfactualRetentionConfig(max_age_ms=100_000)  # 100s -- far shorter than the 300s interval below
    ledger = CounterfactualLedger(stream_id="stream-exceeded", config=tiny_retention)
    now = datetime(2026, 9, 4, 12, 0, 0, tzinfo=UTC)
    checkpoint_interval_ms = 300_000  # far coarser than the 100s retention window above
    spacing_ms = 250_000
    total_proposals = 20

    payloads: list[dict] = []
    next_checkpoint_ms = checkpoint_interval_ms
    for index in range(total_proposals):
        offset_ms = index * spacing_ms
        proposal = _make_proposal(f"exceeded-{index:04d}", f"exceeded-gen-{index:04d}", start_offset_ms=offset_ms)
        ledger.record_proposal_outcome(
            proposal, outcome="blocked_missing_evidence", reason="no_persistable_evidence_bytes",
            visit_id=None, decided_at=now + timedelta(milliseconds=offset_ms), known_horizon_ms=offset_ms,
        )
        while offset_ms >= next_checkpoint_ms:
            payloads.append(_window_to_payload(ledger.query(start_offset_ms=0, end_offset_ms=86_400_000)))
            next_checkpoint_ms += checkpoint_interval_ms
    payloads.append(_window_to_payload(ledger.query(start_offset_ms=0, end_offset_ms=86_400_000)))

    report = reconcile_ledger(payloads, stream_id="stream-exceeded")
    artifact = report.artifacts["proposal_outcomes"]

    assert artifact.final_recorded_count == total_proposals
    assert artifact.recovered_unique_count < total_proposals  # genuine, real loss -- never masked
    assert artifact.status == "PARTIAL"
    assert artifact.gaps_ms  # a real, non-empty missing window is named, never silently absorbed
    assert report.overall_status == "PARTIAL"


def test_reconcile_ledger_zero_activity_still_complete_alongside_real_v13_shaped_activity() -> None:
    """The prior accepted zero-activity fix (§20) must survive alongside
    this milestone's own change: a session where `proposal_outcomes` is
    genuinely, honestly busy (v13-shaped) but `track_generations` is
    genuinely empty must still report `track_generations` as COMPLETE,
    never PARTIAL merely because `proposal_outcomes` is large."""
    _ledger, payloads = _run_v13_shaped_session()

    report = reconcile_ledger(payloads, stream_id=_V13_STREAM_ID)

    assert report.artifacts["track_generations"].status == "COMPLETE"
    assert report.artifacts["track_generations"].final_recorded_count == 0
    assert report.artifacts["raw_detections"].status == "COMPLETE"
    assert report.artifacts["raw_detections"].final_recorded_count == 0
