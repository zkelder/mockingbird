from __future__ import annotations

import json
from pathlib import Path

from mockingbird.observation.replay import (
    BenchmarkManifest,
    ReplayFrame,
    ReplayInput,
    ReplayReport,
)
from mockingbird.observation.replay_io import write_replay_report


def test_versioned_report_separates_semantic_and_execution_contracts(tmp_path: Path) -> None:
    replay = ReplayInput("input", "stream", 1, 1, 1.0, (
        ReplayFrame(0, 0, "a"), ReplayFrame(1, 1000, "b"),
    ))
    manifest = BenchmarkManifest(1, "benchmark", replay.fingerprint, (), ())
    report = ReplayReport(
        replay.packets(), (), (),
        {"appearance_recall": "not_evaluated", "appearance_recall_state": "insufficient_truth"},
        "semantic-fingerprint",
    )
    output = tmp_path / "report-directory"
    report_path = write_replay_report(
        output, report, replay=replay, manifest=manifest,
        provider={"provider_id": "snapshot", "version": "compatibility", "capabilities": {}},
        limitations=("offline",), execution={"started_at": "non-semantic"},
    )
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_path == output / "replay-report.json"
    assert payload["schema_version"] == 3
    assert payload["benchmark"]["id"] == "benchmark"
    assert payload["benchmark"]["manifest_fingerprint"] == manifest.fingerprint
    assert payload["replay"]["input_fingerprint"] == replay.fingerprint
    assert payload["replay"]["frame_identity_version"] == "ordered-frame-v1"
    assert payload["matcher_version"] == "temporal-zone-v1"
    assert payload["provider"]["provider_id"] == "snapshot"
    assert len(payload["semantic_fingerprint"]) == 64
    assert payload["execution"] == {"started_at": "non-semantic"}
    assert "started_at" not in json.dumps(payload["semantic"])
