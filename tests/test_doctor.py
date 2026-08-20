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
    result = doctor._interpret_camera_node({"source_count": 0, "source_kinds": [], "stream_count": 0})
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
        }
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
        }
    )
    assert result.status == DoctorStatus.PASS
    assert result.diagnostic_context["camera_node_configured"] is True


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
