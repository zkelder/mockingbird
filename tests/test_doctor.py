"""MockingBird Doctor: contract, per-check, and orchestrator tests.

Every `_interpret_*` function is pure (see the "Design invariants" in
mockingbird/diagnostics/doctor.py), so most of these tests call them
directly with hand-built fixtures -- no real database, camera, GPU, or
network involved (item 14: "prefer pure probe functions"). A smaller set of
integration-level tests drive the real `run_doctor()` orchestrator against a
real, isolated `tmp_path`-backed database, matching the established
`test-repository-isolation-contract.md` pattern used throughout this suite
(an explicit `tmp_path`-backed `db_url` is the deliberate, correct way to
touch a real SQLite file in a test). Every such test passes `runtime_home`
explicitly for exactly that reason -- `run_doctor()` falls back to the real
platform-default data directory otherwise, same as the production app does.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.diagnostics import doctor
from mockingbird.diagnostics.doctor import (
    DoctorCheckCode,
    DoctorOverallStatus,
    DoctorRecoverability,
    DoctorReport,
    DoctorStatus,
    doctor_exit_code,
    resolve_doctor_environment,
    run_doctor,
)
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.database import DB_URL_ENV_VAR
from mockingbird.storage.models import CameraSourceModel, StreamModel

# Forbidden substrings mirroring the existing precedent
# (test_product_health.py::test_product_health_never_includes_credential_
# shaped_values) -- see "Privacy and security" in the contract doc.
_FORBIDDEN_SUBSTRINGS = ("credential", "bearer", "password", "api_key", "secret", "token")


def _initialized_runtime_home(tmp_path: Path) -> Path:
    """A real, fully-initialized, current-schema database + media root under
    `tmp_path`, laid out exactly the way `resolve_doctor_environment`'s own
    defaults expect (`<home>/data/mockingbird.sqlite3`,
    `<home>/data/media/imports`) -- so `run_doctor(runtime_home=tmp_path)`
    resolves to it with no environment-variable overrides needed."""

    data_dir = tmp_path / "data"
    media_root = data_dir / "media" / "imports"
    media_root.mkdir(parents=True)
    db_path = data_dir / "mockingbird.sqlite3"
    repository = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)
    repository.close()
    return tmp_path


# --------------------------------------------------------------------------
# Contract / serialization / exit codes
# --------------------------------------------------------------------------


def test_json_serialization_is_stable(tmp_path: Path) -> None:
    report = run_doctor(runtime_home=_initialized_runtime_home(tmp_path))
    payload = json.loads(report.model_dump_json())
    assert payload["overall_status"] == "HEALTHY"
    assert isinstance(payload["app_version"], str)
    # generated_at must be a plain ISO-8601 string, not a Python object leak.
    datetime.fromisoformat(payload["generated_at"])
    assert isinstance(payload["checks"], list)
    for check in payload["checks"]:
        assert check["status"] in ("PASS", "WARN", "FAIL", "SKIPPED")
        assert isinstance(check["code"], str)
        assert isinstance(check["component"], str)


@pytest.mark.parametrize(
    ("overall", "expected_exit_code"),
    [
        (DoctorOverallStatus.HEALTHY, 0),
        (DoctorOverallStatus.DEGRADED, 1),
        (DoctorOverallStatus.UNHEALTHY, 2),
    ],
)
def test_exit_codes_for_healthy_degraded_and_failed_states(
    overall: DoctorOverallStatus, expected_exit_code: int
) -> None:
    report = DoctorReport(
        overall_status=overall,
        generated_at=datetime.now(UTC),
        app_version="0.1.0",
        duration_ms=1.0,
        checks=[],
    )
    assert doctor_exit_code(report) == expected_exit_code


def test_report_json_never_includes_sensitive_value_shaped_text(tmp_path: Path) -> None:
    """Mirrors test_product_health.py's existing precedent test exactly.

    Named deliberately without any of `_FORBIDDEN_SUBSTRINGS` in the test
    function's own name: pytest's `tmp_path` fixture derives its directory
    name from the test id, and this check legitimately includes real local
    file paths (`database_path`/`media_root`, matching the established
    `ProductHealthStatus.log_path` precedent that local paths are not
    secrets on this local-only tool) in `diagnostic_context` -- an earlier
    version of this test was itself named
    ``test_secret_redaction_...``, which made pytest's own generated
    ``.../test_secret_redaction_full_rep0/...`` tmp directory the thing
    that "leaked" the substring "secret", a false positive from the test's
    own name rather than a real product defect.
    """

    report = run_doctor(runtime_home=_initialized_runtime_home(tmp_path))
    serialized = report.model_dump_json().lower()
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in serialized


# --------------------------------------------------------------------------
# _derive_overall_status
# --------------------------------------------------------------------------


def _result(status: DoctorStatus, recoverability: DoctorRecoverability | None = None) -> doctor.DoctorCheckResult:
    return doctor.DoctorCheckResult(
        code=DoctorCheckCode.CLOCK, component="Test", status=status, summary="s", recoverability=recoverability
    )


def test_derive_overall_status_all_pass_is_healthy() -> None:
    checks = [_result(DoctorStatus.PASS), _result(DoctorStatus.PASS)]
    assert doctor._derive_overall_status(checks) == DoctorOverallStatus.HEALTHY


def test_derive_overall_status_skipped_alone_stays_healthy() -> None:
    checks = [_result(DoctorStatus.PASS), _result(DoctorStatus.SKIPPED)]
    assert doctor._derive_overall_status(checks) == DoctorOverallStatus.HEALTHY


def test_derive_overall_status_warn_is_degraded() -> None:
    checks = [_result(DoctorStatus.PASS), _result(DoctorStatus.WARN, DoctorRecoverability.DEGRADED)]
    assert doctor._derive_overall_status(checks) == DoctorOverallStatus.DEGRADED


def test_derive_overall_status_non_blocking_fail_is_degraded_not_unhealthy() -> None:
    """A check that failed unexpectedly (DEGRADED recoverability) must never
    alone make the whole install read as unhealthy -- see "Only Database
    and Storage can fail blocking" in the module docstring."""

    checks = [_result(DoctorStatus.PASS), _result(DoctorStatus.FAIL, DoctorRecoverability.DEGRADED)]
    assert doctor._derive_overall_status(checks) == DoctorOverallStatus.DEGRADED


def test_derive_overall_status_blocking_fail_is_unhealthy() -> None:
    checks = [_result(DoctorStatus.PASS), _result(DoctorStatus.FAIL, DoctorRecoverability.BLOCKING)]
    assert doctor._derive_overall_status(checks) == DoctorOverallStatus.UNHEALTHY


def test_derive_overall_status_blocking_wins_over_warn() -> None:
    checks = [
        _result(DoctorStatus.WARN, DoctorRecoverability.DEGRADED),
        _result(DoctorStatus.FAIL, DoctorRecoverability.BLOCKING),
    ]
    assert doctor._derive_overall_status(checks) == DoctorOverallStatus.UNHEALTHY


# --------------------------------------------------------------------------
# Bounded timeout (item 10: "must not hang forever")
# --------------------------------------------------------------------------


def test_run_bounded_returns_promptly_when_the_call_hangs() -> None:
    def _hang() -> None:
        time.sleep(30)

    started = time.monotonic()
    result, error, timed_out = doctor._run_bounded(_hang, timeout_seconds=0.2)
    elapsed = time.monotonic() - started

    assert timed_out is True
    assert result is None
    assert error is None
    # Genuinely bounded, not merely "eventually returns": must not wait
    # anywhere near the hung call's own 30s sleep.
    assert elapsed < 5.0


def test_run_bounded_isolates_an_exception() -> None:
    def _boom() -> None:
        raise RuntimeError("synthetic probe failure")

    result, error, timed_out = doctor._run_bounded(_boom, timeout_seconds=1.0)
    assert timed_out is False
    assert result is None
    assert isinstance(error, RuntimeError)


def test_run_bounded_returns_the_real_result_on_success() -> None:
    result, error, timed_out = doctor._run_bounded(lambda: {"ok": True}, timeout_seconds=1.0)
    assert result == {"ok": True}
    assert error is None
    assert timed_out is False


def test_execute_check_timeout_and_unexpected_exception_default_to_degraded_not_blocking() -> None:
    timeout_result = doctor._execute_check(
        code=DoctorCheckCode.CLOCK,
        component="Clock",
        gather=lambda: time.sleep(5),
        interpret=lambda gathered: pytest.fail("must not be called on timeout"),
        timeout_seconds=0.1,
    )
    assert timeout_result.status == DoctorStatus.WARN
    assert timeout_result.recoverability == DoctorRecoverability.DEGRADED

    def _raise() -> dict:
        raise RuntimeError("boom")

    error_result = doctor._execute_check(
        code=DoctorCheckCode.CLOCK,
        component="Clock",
        gather=_raise,
        interpret=lambda gathered: pytest.fail("must not be called on error"),
        timeout_seconds=1.0,
    )
    assert error_result.status == DoctorStatus.FAIL
    assert error_result.recoverability == DoctorRecoverability.DEGRADED
    # The raw exception must never appear in the always-shown summary --
    # only in diagnostic_context (the advanced/JSON-only bucket).
    assert "RuntimeError" not in error_result.summary
    assert "RuntimeError" in (error_result.diagnostic_context or {}).get("exception", "")


def test_execute_check_blocking_on_failure_escalates_timeout_and_exception() -> None:
    timeout_result = doctor._execute_check(
        code=DoctorCheckCode.DATABASE_CONNECTIVITY,
        component="Database",
        gather=lambda: time.sleep(5),
        interpret=lambda gathered: pytest.fail("unreachable"),
        timeout_seconds=0.1,
        blocking_on_failure=True,
    )
    assert timeout_result.status == DoctorStatus.FAIL
    assert timeout_result.recoverability == DoctorRecoverability.BLOCKING

    def _raise() -> dict:
        raise RuntimeError("disk on fire")

    error_result = doctor._execute_check(
        code=DoctorCheckCode.DATABASE_CONNECTIVITY,
        component="Database",
        gather=_raise,
        interpret=lambda gathered: pytest.fail("unreachable"),
        timeout_seconds=1.0,
        blocking_on_failure=True,
    )
    assert error_result.status == DoctorStatus.FAIL
    assert error_result.recoverability == DoctorRecoverability.BLOCKING


def test_execute_check_skip_reason_never_calls_gather_or_interpret() -> None:
    result = doctor._execute_check(
        code=DoctorCheckCode.DATABASE_SCHEMA,
        component="Database",
        gather=lambda: pytest.fail("must not run"),
        interpret=lambda gathered: pytest.fail("must not run"),
        skip_reason="Skipped because the database is unavailable.",
    )
    assert result.status == DoctorStatus.SKIPPED
    assert result.summary == "Skipped because the database is unavailable."


# --------------------------------------------------------------------------
# Database connectivity + schema
# --------------------------------------------------------------------------


def test_interpret_database_connectivity_no_database_yet_is_informational_pass() -> None:
    result = doctor._interpret_database_connectivity({"database_exists": False}, database_path=Path("/x/db.sqlite3"))
    assert result.status == DoctorStatus.PASS
    assert result.recoverability == DoctorRecoverability.INFORMATIONAL


def test_interpret_database_connectivity_integrity_failure_is_blocking() -> None:
    result = doctor._interpret_database_connectivity(
        {"database_exists": True, "integrity_check": "corruption detected"},
        database_path=Path("/x/db.sqlite3"),
    )
    assert result.status == DoctorStatus.FAIL
    assert result.recoverability == DoctorRecoverability.BLOCKING
    assert result.user_action


def test_interpret_database_connectivity_healthy() -> None:
    result = doctor._interpret_database_connectivity(
        {"database_exists": True, "integrity_check": "ok"}, database_path=Path("/x/db.sqlite3")
    )
    assert result.status == DoctorStatus.PASS
    assert result.recoverability is None


def test_interpret_database_schema_missing_version_is_blocking() -> None:
    result = doctor._interpret_database_schema({"version": None})
    assert result.status == DoctorStatus.FAIL
    assert result.recoverability == DoctorRecoverability.BLOCKING


def test_interpret_database_schema_incompatible_future_version_is_blocking() -> None:
    result = doctor._interpret_database_schema({"version": doctor.CURRENT_DATABASE_SCHEMA_VERSION + 100})
    assert result.status == DoctorStatus.FAIL
    assert result.recoverability == DoctorRecoverability.BLOCKING


def test_interpret_database_schema_stale_but_migratable_is_degraded_warning() -> None:
    result = doctor._interpret_database_schema({"version": 2})
    assert result.status == DoctorStatus.WARN
    assert result.recoverability == DoctorRecoverability.DEGRADED


def test_interpret_database_schema_current_is_pass() -> None:
    result = doctor._interpret_database_schema({"version": doctor.CURRENT_DATABASE_SCHEMA_VERSION})
    assert result.status == DoctorStatus.PASS


# --------------------------------------------------------------------------
# Storage
# --------------------------------------------------------------------------


def test_interpret_storage_missing_root_before_first_launch_is_informational() -> None:
    result = doctor._interpret_storage({"media_root_exists": False}, database_exists=False)
    assert result.status == DoctorStatus.PASS
    assert result.recoverability == DoctorRecoverability.INFORMATIONAL


def test_interpret_storage_missing_root_on_established_install_is_blocking() -> None:
    result = doctor._interpret_storage({"media_root_exists": False}, database_exists=True)
    assert result.status == DoctorStatus.FAIL
    assert result.recoverability == DoctorRecoverability.BLOCKING


def test_interpret_storage_not_writable_is_blocking() -> None:
    result = doctor._interpret_storage(
        {"media_root_exists": True, "is_writable": False}, database_exists=True
    )
    assert result.status == DoctorStatus.FAIL
    assert result.recoverability == DoctorRecoverability.BLOCKING


def test_interpret_storage_low_disk_space_warns() -> None:
    """Reuses the existing canonical threshold (`is_low_space`) rather than
    inventing a new one -- see storage.database.LOW_DISK_FREE_BYTES_THRESHOLD/
    LOW_DISK_FREE_RATIO_THRESHOLD."""

    result = doctor._interpret_storage(
        {"media_root_exists": True, "is_writable": True, "is_low_space": True, "free_bytes": 500_000_000},
        database_exists=True,
    )
    assert result.status == DoctorStatus.WARN
    assert result.recoverability == DoctorRecoverability.DEGRADED


def test_interpret_storage_healthy() -> None:
    result = doctor._interpret_storage(
        {"media_root_exists": True, "is_writable": True, "is_low_space": False},
        database_exists=True,
    )
    assert result.status == DoctorStatus.PASS
    assert result.recoverability is None


# --------------------------------------------------------------------------
# Backup
# --------------------------------------------------------------------------


def test_interpret_backup_none_yet_is_informational() -> None:
    result = doctor._interpret_backup({"backup_count": 0}, now=datetime.now(UTC))
    assert result.status == DoctorStatus.PASS
    assert result.recoverability == DoctorRecoverability.INFORMATIONAL


def test_interpret_backup_stale_warns() -> None:
    now = datetime.now(UTC)
    old = now - timedelta(days=doctor.BACKUP_STALE_AFTER_DAYS + 5)
    result = doctor._interpret_backup(
        {"backup_count": 1, "most_recent_created_at": old.isoformat()}, now=now
    )
    assert result.status == DoctorStatus.WARN
    assert result.recoverability == DoctorRecoverability.DEGRADED


def test_interpret_backup_recent_is_pass() -> None:
    now = datetime.now(UTC)
    recent = now - timedelta(days=1)
    result = doctor._interpret_backup(
        {"backup_count": 3, "most_recent_created_at": recent.isoformat()}, now=now
    )
    assert result.status == DoctorStatus.PASS
    assert result.recoverability is None


# --------------------------------------------------------------------------
# Camera Node / Streams
# --------------------------------------------------------------------------


def test_interpret_camera_node_none_configured_is_pass() -> None:
    result = doctor._interpret_camera_node(
        {"source_count": 0, "source_kinds": [], "stream_count": 0}, now=datetime.now(UTC)
    )
    assert result.status == DoctorStatus.PASS
    assert result.recoverability is None


def test_interpret_camera_node_offline_stream_needs_attention_is_degraded_warning() -> None:
    """Actionable degraded/failure result based on existing monitoring
    semantics (`StreamRuntimeCheckpointModel.actual_state`)."""

    result = doctor._interpret_camera_node(
        {
            "source_count": 1,
            "source_kinds": ["integration"],
            "stream_count": 1,
            "currently_monitored_count": 0,
            "attention_count": 1,
        },
        now=datetime.now(UTC),
    )
    assert result.status == DoctorStatus.WARN
    assert result.recoverability == DoctorRecoverability.DEGRADED
    assert result.user_action


def test_interpret_camera_node_all_fine_is_pass() -> None:
    result = doctor._interpret_camera_node(
        {
            "source_count": 1,
            "source_kinds": ["integration"],
            "stream_count": 1,
            "currently_monitored_count": 1,
            "attention_count": 0,
        },
        now=datetime.now(UTC),
    )
    assert result.status == DoctorStatus.PASS
    assert result.diagnostic_context["camera_node_configured"] is True


def test_interpret_camera_node_stale_freshness_warns_with_last_frame_minutes() -> None:
    """Camera Node Connectivity & Recovery Diagnosis v1 (Section 12): the
    accepted camera_node Observation Engine lane never writes
    `StreamRuntimeCheckpointModel` (see `_gather_camera_node`), so before
    this fix Doctor was structurally blind to this lane's own runtime
    health -- a Stream could be silently stuck exactly like the real
    2026-08-20 field incident and Doctor would still report a bland PASS.
    A stale `last_confirmed_fresh_at` on a still-open camera_node exposure
    interval is a real, durable, read-only "Camera Node unavailable / last
    frame N minutes ago" signal."""

    now = datetime.now(UTC)
    stale = now - timedelta(seconds=doctor._CAMERA_NODE_STALE_AFTER_SECONDS + 300)
    result = doctor._interpret_camera_node(
        {
            "source_count": 1,
            "source_kinds": ["integration"],
            "stream_count": 1,
            "currently_monitored_count": 1,
            "attention_count": 0,
            "stalest_camera_node_stream_id": "stream-backyard-feeder",
            "stalest_camera_node_fresh_at": stale.isoformat(),
        },
        now=now,
    )
    assert result.status == DoctorStatus.WARN
    assert result.recoverability == DoctorRecoverability.DEGRADED
    assert "unavailable" in result.summary.lower()
    assert "minute" in result.summary.lower()
    assert result.user_action


def test_interpret_camera_node_recent_freshness_is_pass() -> None:
    """A camera_node Stream whose exposure interval checkpointed recently
    (well within the normal ~45s cadence) must not falsely WARN."""

    now = datetime.now(UTC)
    recent = now - timedelta(seconds=20)
    result = doctor._interpret_camera_node(
        {
            "source_count": 1,
            "source_kinds": ["integration"],
            "stream_count": 1,
            "currently_monitored_count": 1,
            "attention_count": 0,
            "stalest_camera_node_stream_id": "stream-backyard-feeder",
            "stalest_camera_node_fresh_at": recent.isoformat(),
        },
        now=now,
    )
    assert result.status == DoctorStatus.PASS
    assert result.recoverability is None


def test_interpret_camera_node_stale_last_seen_with_no_open_session_warns() -> None:
    """Boot Identity + Autonomous Recovery v1: closes the gap Camera Node
    Connectivity & Recovery Diagnosis v1 explicitly disclosed as open --
    "the gap between a session giving up entirely... and the next Start,"
    where no open exposure interval exists at all for the pre-existing
    check above to read. `camera_node_last_seen_at` is durable and
    session-independent, so it remains valid evidence exactly in that gap."""

    now = datetime.now(UTC)
    stale = now - timedelta(seconds=doctor._CAMERA_NODE_STALE_AFTER_SECONDS + 300)
    result = doctor._interpret_camera_node(
        {
            "source_count": 1,
            "source_kinds": ["integration"],
            "stream_count": 1,
            "currently_monitored_count": 0,
            "attention_count": 0,
            "stalest_camera_node_stream_id": None,
            "stalest_camera_node_fresh_at": None,  # no open interval at all
            "camera_node_last_seen_at": stale.isoformat(),
        },
        now=now,
    )
    assert result.status == DoctorStatus.WARN
    assert result.recoverability == DoctorRecoverability.DEGRADED
    assert "offline" in result.summary.lower()
    assert "minute" in result.summary.lower()
    assert result.user_action


def test_interpret_camera_node_recent_last_seen_with_no_open_session_is_pass() -> None:
    now = datetime.now(UTC)
    recent = now - timedelta(seconds=30)
    result = doctor._interpret_camera_node(
        {
            "source_count": 1,
            "source_kinds": ["integration"],
            "stream_count": 1,
            "currently_monitored_count": 0,
            "attention_count": 0,
            "stalest_camera_node_fresh_at": None,
            "camera_node_last_seen_at": recent.isoformat(),
        },
        now=now,
    )
    assert result.status == DoctorStatus.PASS


def test_interpret_camera_node_no_last_seen_fact_at_all_is_pass() -> None:
    """A Source that predates this milestone (or has never had a
    checkpoint) has no evidence either way -- honest silence, never a
    fabricated WARN."""

    result = doctor._interpret_camera_node(
        {
            "source_count": 1,
            "source_kinds": ["integration"],
            "stream_count": 1,
            "currently_monitored_count": 0,
            "attention_count": 0,
            "stalest_camera_node_fresh_at": None,
            "camera_node_last_seen_at": None,
        },
        now=datetime.now(UTC),
    )
    assert result.status == DoctorStatus.PASS


def test_interpret_camera_node_surfaces_boot_id_and_service_version_in_context() -> None:
    result = doctor._interpret_camera_node(
        {
            "source_count": 1,
            "source_kinds": ["integration"],
            "stream_count": 1,
            "currently_monitored_count": 1,
            "attention_count": 0,
            "stalest_camera_node_fresh_at": datetime.now(UTC).isoformat(),
            "camera_node_boot_id": "b2f1c9de-1234-5678-9abc-def012345678",
            "camera_node_service_version": "0.1.0",
        },
        now=datetime.now(UTC),
    )
    assert result.diagnostic_context["camera_node_boot_id"] == "b2f1c9de-1234-5678-9abc-def012345678"
    assert result.diagnostic_context["camera_node_service_version"] == "0.1.0"


def _boot_transitions_json(*, count: int, now: datetime, within_seconds: float) -> str:
    return json.dumps(
        [
            {
                "boot_id": f"boot-{index}",
                "first_seen_at": (now - timedelta(seconds=within_seconds * index / max(count, 1))).isoformat(),
            }
            for index in range(count)
        ]
    )


def test_interpret_camera_node_repeated_recent_reboots_suspects_instability() -> None:
    """Boot Identity + Autonomous Recovery v1: three real reboots inside
    the bounded fifteen-minute window is the "boot loop / repeated
    restart" evidence docs/camera-node-installer-design.md names as
    previously unavailable -- an operator could not tell "stuck
    restarting" apart from "simply offline" without direct device access."""

    now = datetime.now(UTC)
    result = doctor._interpret_camera_node(
        {
            "source_count": 1,
            "source_kinds": ["integration"],
            "stream_count": 1,
            "currently_monitored_count": 1,
            "attention_count": 0,
            "stalest_camera_node_fresh_at": now.isoformat(),  # even with a fresh checkpoint...
            "camera_node_recent_boot_transitions_json": _boot_transitions_json(
                count=3, now=now, within_seconds=600
            ),
        },
        now=now,
    )
    assert result.status == DoctorStatus.WARN
    assert "instability" in result.summary.lower()
    assert result.diagnostic_context["recent_boot_transition_count"] == 3


def test_interpret_camera_node_two_recent_reboots_is_not_yet_suspicious() -> None:
    """Bounded threshold: two reboots is not, by itself, treated as
    instability -- avoids over-alarming on one ordinary maintenance
    restart plus one real recovery."""

    now = datetime.now(UTC)
    result = doctor._interpret_camera_node(
        {
            "source_count": 1,
            "source_kinds": ["integration"],
            "stream_count": 1,
            "currently_monitored_count": 1,
            "attention_count": 0,
            "stalest_camera_node_fresh_at": now.isoformat(),
            "camera_node_recent_boot_transitions_json": _boot_transitions_json(
                count=2, now=now, within_seconds=600
            ),
        },
        now=now,
    )
    assert result.status == DoctorStatus.PASS


def test_interpret_camera_node_old_reboots_outside_window_are_not_suspicious() -> None:
    """A bounded window, not merely a bounded count: three reboots spread
    across days (well outside `_CAMERA_NODE_INSTABILITY_WINDOW_SECONDS`)
    is ordinary operational history, not instability evidence."""

    now = datetime.now(UTC)
    old_transitions = json.dumps(
        [
            {"boot_id": f"boot-{i}", "first_seen_at": (now - timedelta(days=i + 1)).isoformat()}
            for i in range(3)
        ]
    )
    result = doctor._interpret_camera_node(
        {
            "source_count": 1,
            "source_kinds": ["integration"],
            "stream_count": 1,
            "currently_monitored_count": 1,
            "attention_count": 0,
            "stalest_camera_node_fresh_at": now.isoformat(),
            "camera_node_recent_boot_transitions_json": old_transitions,
        },
        now=now,
    )
    assert result.status == DoctorStatus.PASS


def test_interpret_camera_node_malformed_boot_transitions_json_is_safely_ignored() -> None:
    result = doctor._interpret_camera_node(
        {
            "source_count": 1,
            "source_kinds": ["integration"],
            "stream_count": 1,
            "currently_monitored_count": 1,
            "attention_count": 0,
            "stalest_camera_node_fresh_at": datetime.now(UTC).isoformat(),
            "camera_node_recent_boot_transitions_json": "{not valid json",
        },
        now=datetime.now(UTC),
    )
    assert result.status == DoctorStatus.PASS


def test_interpret_camera_node_recent_replacement_warns_and_recommends_zone_review() -> None:
    """Reprovision / Replacement Recovery v1: a confirmed hardware swap is a
    bounded, one-time operator reminder -- lowest priority (only surfaces
    once nothing more urgent, like offline/instability, is wrong)."""

    now = datetime.now(UTC)
    result = doctor._interpret_camera_node(
        {
            "source_count": 1,
            "source_kinds": ["integration"],
            "stream_count": 1,
            "currently_monitored_count": 1,
            "attention_count": 0,
            "stalest_camera_node_fresh_at": now.isoformat(),
            "camera_node_identity_replaced_at": (now - timedelta(days=1)).isoformat(),
        },
        now=now,
    )
    assert result.status == DoctorStatus.WARN
    assert "replaced" in result.summary.lower()
    assert "zone" in result.user_action.lower()
    assert result.recoverability == DoctorRecoverability.DEGRADED


def test_interpret_camera_node_replacement_reason_surfaces_in_detail_and_context() -> None:
    now = datetime.now(UTC)
    result = doctor._interpret_camera_node(
        {
            "source_count": 1,
            "source_kinds": ["integration"],
            "stream_count": 1,
            "currently_monitored_count": 1,
            "attention_count": 0,
            "stalest_camera_node_fresh_at": now.isoformat(),
            "camera_node_identity_replaced_at": (now - timedelta(hours=2)).isoformat(),
            "camera_node_replacement_reason": "SD card failed",
        },
        now=now,
    )
    assert "SD card failed" in result.detail
    assert result.diagnostic_context["camera_node_replacement_reason"] == "SD card failed"


def test_interpret_camera_node_old_replacement_outside_review_window_is_pass() -> None:
    now = datetime.now(UTC)
    result = doctor._interpret_camera_node(
        {
            "source_count": 1,
            "source_kinds": ["integration"],
            "stream_count": 1,
            "currently_monitored_count": 1,
            "attention_count": 0,
            "stalest_camera_node_fresh_at": now.isoformat(),
            "camera_node_identity_replaced_at": (now - timedelta(days=30)).isoformat(),
        },
        now=now,
    )
    assert result.status == DoctorStatus.PASS


def test_interpret_camera_node_offline_outranks_a_recent_replacement_reminder() -> None:
    """A live fault is always more urgent than a one-time reminder about a
    past, already-completed replacement."""

    now = datetime.now(UTC)
    result = doctor._interpret_camera_node(
        {
            "source_count": 1,
            "source_kinds": ["integration"],
            "stream_count": 1,
            "currently_monitored_count": 0,
            "attention_count": 0,
            "stalest_camera_node_fresh_at": None,
            "camera_node_last_seen_at": (now - timedelta(hours=1)).isoformat(),
            "camera_node_identity_replaced_at": (now - timedelta(minutes=30)).isoformat(),
        },
        now=now,
    )
    assert result.status == DoctorStatus.WARN
    assert "offline" in result.summary.lower()
    assert "replaced" not in result.summary.lower()


def test_run_doctor_survives_a_real_open_camera_node_exposure_interval(tmp_path: Path) -> None:
    """Real-database regression guard: every test above calls
    `_interpret_camera_node` directly with a hand-built dict whose
    `stalest_camera_node_fresh_at` came from `datetime.now(UTC).isoformat()`
    -- always already timezone-aware -- so none of them ever exercised
    `_gather_camera_node`'s actual SQLite round trip. Per
    `product_repository.py`'s own documented convention ("SQLite's
    `DateTime(timezone=True)` does not itself preserve tzinfo across a
    write/read round trip"), a real `MonitoringExposureIntervalModel.
    last_confirmed_fresh_at` reads back *naive*. Before this fix,
    `_gather_camera_node` handed that naive value straight to `.isoformat()`
    with no offset, and `_interpret_camera_node` crashed the instant any
    camera_node Stream had a real, currently-open exposure interval --
    the ordinary actively-observing state, not only a stale one:
    `TypeError: can't subtract offset-naive and offset-aware datetimes`."""

    runtime_home = _initialized_runtime_home(tmp_path)
    db_path = runtime_home / "data" / "mockingbird.sqlite3"
    repository = ProductRepository(
        db_url=f"sqlite:///{db_path}", media_root=runtime_home / "data" / "media" / "imports"
    )
    try:
        with repository.session_factory() as session, session.begin():
            session.add(
                CameraSourceModel(
                    id="source-real-camera-node",
                    name="Real Camera Node",
                    kind="integration",
                    status="connected",
                    description="Real paired Camera Node fixture.",
                )
            )
            session.add(
                StreamModel(
                    id="stream-real-camera-node",
                    source_id="source-real-camera-node",
                    name="Real Camera Node stream",
                    description="Real paired Camera Node fixture.",
                    is_live=True,
                )
            )
        healthy_at = datetime.now(UTC)
        repository.record_observation_exposure_frame(
            stream_id="stream-real-camera-node",
            runtime_generation_id="generation-real",
            healthy_at=healthy_at,
            now=healthy_at,
        )
    finally:
        repository.close()

    report = run_doctor(runtime_home=runtime_home)  # must not raise TypeError
    camera_result = next(c for c in report.checks if c.code == DoctorCheckCode.CAMERA_NODE)
    # Freshly checkpointed -- well within the staleness window -- so this
    # must PASS, not WARN and not fail with an unexpected exception.
    assert camera_result.status == DoctorStatus.PASS


def test_run_doctor_reads_camera_node_last_seen_after_session_closes(tmp_path: Path) -> None:
    """Boot Identity + Autonomous Recovery v1, real-database regression
    guard: the same naive-datetime SQLite round trip as the test above, but
    for `CameraSourceModel.camera_node_last_seen_at` specifically, and
    exercised in exactly the state this milestone's new fallback branch
    targets -- the exposure interval already *closed* (no session
    currently observing), so only the durable last-seen fact remains."""

    runtime_home = _initialized_runtime_home(tmp_path)
    db_path = runtime_home / "data" / "mockingbird.sqlite3"
    repository = ProductRepository(
        db_url=f"sqlite:///{db_path}", media_root=runtime_home / "data" / "media" / "imports"
    )
    try:
        with repository.session_factory() as session, session.begin():
            session.add(
                CameraSourceModel(
                    id="source-real-camera-node",
                    name="Real Camera Node",
                    kind="integration",
                    status="connected",
                    description="Real paired Camera Node fixture.",
                )
            )
            session.add(
                StreamModel(
                    id="stream-real-camera-node",
                    source_id="source-real-camera-node",
                    name="Real Camera Node stream",
                    description="Real paired Camera Node fixture.",
                    is_live=True,
                )
            )
        healthy_at = datetime.now(UTC)
        repository.record_observation_exposure_frame(
            stream_id="stream-real-camera-node",
            runtime_generation_id="generation-real",
            healthy_at=healthy_at,
            now=healthy_at,
            node_boot_id="boot-real-1",
            node_service_version="0.1.0",
        )
        repository.close_observation_exposure(
            stream_id="stream-real-camera-node",
            close_reason="stop_requested",
            now=datetime.now(UTC),
            last_healthy_at=healthy_at,
        )
    finally:
        repository.close()

    report = run_doctor(runtime_home=runtime_home)  # must not raise TypeError
    camera_result = next(c for c in report.checks if c.code == DoctorCheckCode.CAMERA_NODE)
    assert camera_result.status == DoctorStatus.PASS
    assert camera_result.diagnostic_context["camera_node_boot_id"] == "boot-real-1"
    assert camera_result.diagnostic_context["camera_node_service_version"] == "0.1.0"


# --------------------------------------------------------------------------
# FFmpeg
# --------------------------------------------------------------------------


def test_interpret_ffmpeg_absent_and_not_needed_is_informational() -> None:
    result = doctor._interpret_ffmpeg({"available": False, "likely_needed": False})
    assert result.status == DoctorStatus.PASS
    assert result.recoverability == DoctorRecoverability.INFORMATIONAL


def test_interpret_ffmpeg_absent_and_needed_warns() -> None:
    result = doctor._interpret_ffmpeg({"available": False, "likely_needed": True})
    assert result.status == DoctorStatus.WARN
    assert result.recoverability == DoctorRecoverability.DEGRADED


def test_interpret_ffmpeg_available_is_pass() -> None:
    result = doctor._interpret_ffmpeg({"available": True, "likely_needed": None})
    assert result.status == DoctorStatus.PASS
    assert result.recoverability is None


# --------------------------------------------------------------------------
# Detector model
# --------------------------------------------------------------------------


def test_interpret_detector_model_not_configured_no_camera_node_is_informational() -> None:
    result = doctor._interpret_detector_model({"configured": False}, camera_node_configured=False)
    assert result.status == DoctorStatus.PASS
    assert result.recoverability == DoctorRecoverability.INFORMATIONAL


def test_interpret_detector_model_missing_but_camera_node_configured_warns() -> None:
    """Optional model unavailable: degraded, not total failure."""

    result = doctor._interpret_detector_model({"configured": False}, camera_node_configured=True)
    assert result.status == DoctorStatus.WARN
    assert result.recoverability == DoctorRecoverability.DEGRADED


def test_interpret_detector_model_invalid_bundle_warns_not_fails() -> None:
    result = doctor._interpret_detector_model(
        {"configured": True, "valid": False, "reason": "model_fingerprint_mismatch"},
        camera_node_configured=True,
    )
    assert result.status == DoctorStatus.WARN
    assert result.recoverability == DoctorRecoverability.DEGRADED
    assert result.diagnostic_context["reason"] == "model_fingerprint_mismatch"


def test_interpret_detector_model_valid_is_pass() -> None:
    result = doctor._interpret_detector_model(
        {"configured": True, "valid": True, "model_bundle_path": "/x/model.onnx"}, camera_node_configured=True
    )
    assert result.status == DoctorStatus.PASS


# --------------------------------------------------------------------------
# Species identification (BioCLIP)
# --------------------------------------------------------------------------


def test_interpret_species_identification_not_configured_is_informational() -> None:
    result = doctor._interpret_species_identification({"status": "not_configured"})
    assert result.status == DoctorStatus.PASS
    assert result.recoverability == DoctorRecoverability.INFORMATIONAL


def test_interpret_species_identification_unavailable_is_degraded_warning() -> None:
    """The task's own worked example: BioCLIP runtime unavailable ->
    wildlife Visits can still be created, species suggestions cannot."""

    result = doctor._interpret_species_identification({"status": "unavailable", "detail": "missing packages"})
    assert result.status == DoctorStatus.WARN
    assert result.recoverability == DoctorRecoverability.DEGRADED
    assert "Visits can still be created" in result.detail


def test_interpret_species_identification_available_is_pass() -> None:
    result = doctor._interpret_species_identification({"status": "available"})
    assert result.status == DoctorStatus.PASS
    assert result.recoverability is None


# --------------------------------------------------------------------------
# GPU / CUDA
# --------------------------------------------------------------------------


def test_interpret_gpu_cuda_unavailable_and_optional_is_not_a_blocking_failure() -> None:
    result = doctor._interpret_gpu_cuda({"cuda_available": False}, camera_node_configured=False)
    assert result.status == DoctorStatus.PASS
    assert result.recoverability == DoctorRecoverability.INFORMATIONAL


def test_interpret_gpu_cuda_unavailable_and_camera_node_configured_is_degraded() -> None:
    result = doctor._interpret_gpu_cuda({"cuda_available": False}, camera_node_configured=True)
    assert result.status == DoctorStatus.WARN
    assert result.recoverability == DoctorRecoverability.DEGRADED


def test_interpret_gpu_cuda_available_is_pass() -> None:
    result = doctor._interpret_gpu_cuda({"cuda_available": True}, camera_node_configured=True)
    assert result.status == DoctorStatus.PASS
    assert result.recoverability is None


def test_interpret_gpu_cuda_unknown_camera_node_state_is_not_alarming() -> None:
    """When the database check failed, `camera_node_configured` is `None`
    (unknown) -- Doctor must stay calm rather than guess a WARN."""

    result = doctor._interpret_gpu_cuda({"cuda_available": False}, camera_node_configured=None)
    assert result.status == DoctorStatus.PASS


# --------------------------------------------------------------------------
# Clock
# --------------------------------------------------------------------------


def test_interpret_clock_always_passes_and_discloses_camera_node_divergence_gap() -> None:
    result = doctor._interpret_clock({"zone_key": "America/New_York"})
    assert result.status == DoctorStatus.PASS
    assert "America/New_York" in result.detail
    assert "camera_node_clock_divergence" in result.diagnostic_context


def test_interpret_clock_fixed_offset_fallback_still_passes() -> None:
    result = doctor._interpret_clock({"zone_key": None})
    assert result.status == DoctorStatus.PASS


# --------------------------------------------------------------------------
# resolve_doctor_environment: cwd-independence and env-var overrides
# --------------------------------------------------------------------------


def test_resolve_doctor_environment_anchors_defaults_to_runtime_home_not_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(DB_URL_ENV_VAR, raising=False)
    monkeypatch.chdir(tmp_path)  # a real cwd change; defaults must not follow it
    other_home = tmp_path / "elsewhere"
    other_home.mkdir()

    environment = resolve_doctor_environment(runtime_home=other_home)

    assert environment.db_url == f"sqlite:///{other_home / 'data' / 'mockingbird.sqlite3'}"
    assert environment.media_root == other_home / "data" / "media" / "imports"


def test_resolve_doctor_environment_respects_db_url_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    override = tmp_path / "custom.sqlite3"
    monkeypatch.setenv(DB_URL_ENV_VAR, f"sqlite:///{override}")
    environment = resolve_doctor_environment(runtime_home=tmp_path)
    assert environment.db_url == f"sqlite:///{override}"


def test_resolve_doctor_environment_with_no_override_finds_the_real_dev_checkout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no explicit `runtime_home` and no `MOCKINGBIRD_HOME` set, Doctor
    must resolve the *real* development checkout's own `data/` directory
    (mirroring `runtime.run_preflight`'s `resolve_runtime_home(find_
    workspace_root())`) rather than silently falling back to the platform
    XDG/AppData default -- a real gap this milestone's own real-acceptance
    run against mockingbird-active surfaced and fixed."""

    monkeypatch.delenv("MOCKINGBIRD_HOME", raising=False)
    monkeypatch.delenv(DB_URL_ENV_VAR, raising=False)

    environment = resolve_doctor_environment()

    assert (environment.runtime_home / "pyproject.toml").is_file()
    assert (environment.runtime_home / "web").is_dir()
    assert str(environment.runtime_home) not in ("", str(Path.home() / ".local" / "share" / "mockingbird"))


# --------------------------------------------------------------------------
# run_doctor: end-to-end orchestration
# --------------------------------------------------------------------------


def test_healthy_installation_all_core_checks_pass(tmp_path: Path) -> None:
    report = run_doctor(runtime_home=_initialized_runtime_home(tmp_path))
    assert report.overall_status == DoctorOverallStatus.HEALTHY
    codes = {check.code for check in report.checks}
    assert codes == set(DoctorCheckCode)
    assert all(check.status in (DoctorStatus.PASS,) for check in report.checks)


def test_fresh_never_launched_install_is_healthy_not_alarming(tmp_path: Path) -> None:
    report = run_doctor(runtime_home=tmp_path)
    assert report.overall_status == DoctorOverallStatus.HEALTHY


def test_database_unavailable_produces_blocking_failure_without_crashing_doctor(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "mockingbird.sqlite3").write_bytes(b"not a real sqlite database")

    report = run_doctor(runtime_home=tmp_path)  # must not raise

    assert report.overall_status == DoctorOverallStatus.UNHEALTHY
    connectivity = next(c for c in report.checks if c.code == DoctorCheckCode.DATABASE_CONNECTIVITY)
    assert connectivity.status == DoctorStatus.FAIL
    assert connectivity.recoverability == DoctorRecoverability.BLOCKING
    # Downstream DB-derived checks must be SKIPPED, not crashed/silently missing.
    schema = next(c for c in report.checks if c.code == DoctorCheckCode.DATABASE_SCHEMA)
    camera = next(c for c in report.checks if c.code == DoctorCheckCode.CAMERA_NODE)
    assert schema.status == DoctorStatus.SKIPPED
    assert camera.status == DoctorStatus.SKIPPED
    # A broken database must not hide unrelated checks (item 11).
    application = next(c for c in report.checks if c.code == DoctorCheckCode.APPLICATION)
    clock = next(c for c in report.checks if c.code == DoctorCheckCode.CLOCK)
    assert application.status == DoctorStatus.PASS
    assert clock.status == DoctorStatus.PASS


def test_individual_probe_exception_does_not_prevent_other_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A completely unrelated check (Clock) breaking must not take down the
    rest of the report -- exercised at the real orchestrator level, not
    just `_execute_check` in isolation."""

    def _broken_gather() -> dict:
        raise RuntimeError("synthetic clock probe failure")

    monkeypatch.setattr(doctor, "_gather_clock", _broken_gather)

    report = run_doctor(runtime_home=_initialized_runtime_home(tmp_path))

    clock = next(c for c in report.checks if c.code == DoctorCheckCode.CLOCK)
    assert clock.status == DoctorStatus.FAIL
    assert clock.recoverability == DoctorRecoverability.DEGRADED
    # The overall install is degraded, not unhealthy -- Clock is not blocking.
    assert report.overall_status == DoctorOverallStatus.DEGRADED
    database = next(c for c in report.checks if c.code == DoctorCheckCode.DATABASE_CONNECTIVITY)
    assert database.status == DoctorStatus.PASS


def test_ffmpeg_absent_is_reported_and_never_blocking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(doctor, "is_ffmpeg_available", lambda: False)
    report = run_doctor(runtime_home=_initialized_runtime_home(tmp_path))
    ffmpeg = next(c for c in report.checks if c.code == DoctorCheckCode.FFMPEG)
    assert ffmpeg.status in (DoctorStatus.PASS, DoctorStatus.WARN)
    assert ffmpeg.recoverability != DoctorRecoverability.BLOCKING


def test_doctor_run_completes_quickly_for_a_healthy_installation(tmp_path: Path) -> None:
    """Item 16: "Doctor should be lightweight." Generous ceiling for a
    loaded CI host; the real acceptance run separately measures the actual
    local figure."""

    report = run_doctor(runtime_home=_initialized_runtime_home(tmp_path))
    assert report.duration_ms < 10_000
