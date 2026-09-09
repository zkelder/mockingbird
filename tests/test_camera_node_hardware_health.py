"""Release Reliability & First-Run Recovery v1: Camera Node storage/
media-health and hardware-quality visibility (`mockingbird_node.
hardware_health`). See that module's own docstring for the closed gap
("nothing today checks the node's own free space... or storage health"; no
undervoltage/throttling/temperature telemetry existed at all).

Real sample values (`throttled=0x0`, `temp=47.7'C`) were captured directly
from the real reference Camera Node (a Raspberry Pi) over SSH before
writing the parser -- confirmed real hardware output shape, not guessed.
The classic real-world "everything wrong" value, `0x50005` (bits 0/2/16/18
-- undervoltage and throttling, both currently active and having occurred
at some point since boot), is a well-documented `vcgencmd` reference value,
used here as a synthetic worst case this reference Pi did not happen to be
in at capture time.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from mockingbird_node import hardware_health


# --------------------------------------------------------------------------
# Storage health
# --------------------------------------------------------------------------


def test_read_storage_health_healthy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        hardware_health.shutil,
        "disk_usage",
        lambda _path: type("Usage", (), {"total": 100_000_000_000, "free": 50_000_000_000})(),
    )
    result = hardware_health.read_storage_health(tmp_path)
    assert result.storage_health_tier == "healthy"
    assert result.total_bytes == 100_000_000_000
    assert result.free_bytes == 50_000_000_000


@pytest.mark.parametrize(
    ("free_bytes", "total_bytes", "expected_tier"),
    [
        # 10% free (between the 5%/15% ratio floors), and >=5GB/>=1GB
        # absolute -- isolates the ratio-based `getting_low` path alone.
        (10_000_000_000, 100_000_000_000, "getting_low"),
        # 900MB free on a 10GB card: below the 1GB absolute
        # `action_recommended` floor, but 9% is above both ratio floors --
        # isolates the absolute-byte `action_recommended` path alone.
        (900_000_000, 10_000_000_000, "action_recommended"),
        # 100MB free: below the 200MB absolute `critical` floor outright.
        (100_000_000, 100_000_000_000, "critical"),
        # 1GB free on a 200GB card (0.5%): not below any absolute floor,
        # but below the 1% ratio `critical` floor -- isolates the
        # ratio-based `critical` path alone.
        (1_000_000_000, 200_000_000_000, "critical"),
    ],
)
def test_read_storage_health_tier_boundaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    free_bytes: int,
    total_bytes: int,
    expected_tier: str,
) -> None:
    monkeypatch.setattr(
        hardware_health.shutil,
        "disk_usage",
        lambda _path: type("Usage", (), {"total": total_bytes, "free": free_bytes})(),
    )
    result = hardware_health.read_storage_health(tmp_path)
    assert result.storage_health_tier == expected_tier


def test_read_storage_health_never_fabricates_alarm_when_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise(_path: Path) -> None:
        raise OSError("simulated unreadable filesystem")

    monkeypatch.setattr(hardware_health.shutil, "disk_usage", _raise)
    result = hardware_health.read_storage_health(tmp_path)
    assert result.storage_health_tier == "healthy"
    assert result.total_bytes == 0
    assert result.free_bytes == 0


def test_read_storage_health_probes_the_parent_when_directory_does_not_exist_yet(
    tmp_path: Path,
) -> None:
    """Mirrors the Host's own `_gather_storage` fallback -- a directory that
    has not been created yet (a brand-new install) must not itself make
    this probe fail; it falls back to the nearest existing ancestor."""

    never_created = tmp_path / "not-created-yet"
    result = hardware_health.read_storage_health(never_created)
    assert result.total_bytes > 0  # resolved via tmp_path itself, a real directory


# --------------------------------------------------------------------------
# Hardware quality (vcgencmd)
# --------------------------------------------------------------------------


def _fake_run(responses: dict[tuple[str, ...], str]):
    def run(args: list[str], **_kwargs: object) -> "subprocess.CompletedProcess[str]":
        key = tuple(args)
        if key not in responses:
            return subprocess.CompletedProcess(args, returncode=1, stdout="", stderr="not found")
        return subprocess.CompletedProcess(args, returncode=0, stdout=responses[key], stderr="")

    return run


def test_read_hardware_quality_is_none_without_vcgencmd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware_health.shutil, "which", lambda _binary: None)
    assert hardware_health.read_hardware_quality() is None


def test_read_hardware_quality_parses_real_captured_clean_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    """The real reference Pi's own actual output at capture time -- a clean
    bill of health."""

    monkeypatch.setattr(hardware_health.shutil, "which", lambda _binary: "/usr/bin/vcgencmd")
    run = _fake_run(
        {
            ("/usr/bin/vcgencmd", "get_throttled"): "throttled=0x0",
            ("/usr/bin/vcgencmd", "measure_temp"): "temp=47.7'C",
        }
    )
    result = hardware_health.read_hardware_quality(run=run)
    assert result is not None
    assert result.undervoltage_active is False
    assert result.throttled_active is False
    assert result.undervoltage_occurred is False
    assert result.throttled_occurred is False
    assert result.temperature_celsius == pytest.approx(47.7)
    assert result.is_critical is False


def test_read_hardware_quality_parses_the_classic_worst_case_bitmask(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(hardware_health.shutil, "which", lambda _binary: "/usr/bin/vcgencmd")
    run = _fake_run(
        {
            ("/usr/bin/vcgencmd", "get_throttled"): "throttled=0x50005",
            ("/usr/bin/vcgencmd", "measure_temp"): "temp=82.1'C",
        }
    )
    result = hardware_health.read_hardware_quality(run=run)
    assert result is not None
    assert result.undervoltage_active is True
    assert result.throttled_active is True
    assert result.undervoltage_occurred is True
    assert result.throttled_occurred is True
    assert result.temperature_celsius == pytest.approx(82.1)
    assert result.is_critical is True


def test_read_hardware_quality_historical_only_is_not_currently_critical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bits 16/18 alone (something happened earlier this boot, but not
    right now) must not, by themselves, mark the Node as *currently*
    degraded -- that would misreport a past, already-resolved event as an
    ongoing problem."""

    monkeypatch.setattr(hardware_health.shutil, "which", lambda _binary: "/usr/bin/vcgencmd")
    run = _fake_run({("/usr/bin/vcgencmd", "get_throttled"): "throttled=0x50000"})
    result = hardware_health.read_hardware_quality(run=run)
    assert result is not None
    assert result.undervoltage_active is False
    assert result.throttled_active is False
    assert result.undervoltage_occurred is True
    assert result.throttled_occurred is True
    assert result.is_critical is False


def test_read_hardware_quality_degrades_field_by_field_on_partial_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One command failing (a real, if unlikely, `vcgencmd` hiccup) must
    not discard the other, independently-readable fact."""

    monkeypatch.setattr(hardware_health.shutil, "which", lambda _binary: "/usr/bin/vcgencmd")
    run = _fake_run({("/usr/bin/vcgencmd", "get_throttled"): "throttled=0x0"})
    result = hardware_health.read_hardware_quality(run=run)
    assert result is not None
    assert result.undervoltage_active is False
    assert result.temperature_celsius is None


def test_read_hardware_quality_is_none_when_both_commands_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(hardware_health.shutil, "which", lambda _binary: "/usr/bin/vcgencmd")
    assert hardware_health.read_hardware_quality(run=_fake_run({})) is None


def test_read_hardware_quality_never_hangs_or_crashes_on_a_wedged_subprocess() -> None:
    def _timeout(args: list[str], **kwargs: object) -> "subprocess.CompletedProcess[str]":
        raise subprocess.TimeoutExpired(cmd=args, timeout=kwargs.get("timeout", 0))

    import shutil as real_shutil

    if real_shutil.which("vcgencmd") is None:
        pytest.skip("vcgencmd is not on PATH in this environment (expected off a real Pi)")
    result = hardware_health.read_hardware_quality(run=_timeout)
    assert result is None


def test_read_hardware_quality_rejects_a_malformed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware_health.shutil, "which", lambda _binary: "/usr/bin/vcgencmd")
    run = _fake_run(
        {
            ("/usr/bin/vcgencmd", "get_throttled"): "not the expected shape at all",
            ("/usr/bin/vcgencmd", "measure_temp"): "also not expected",
        }
    )
    assert hardware_health.read_hardware_quality(run=run) is None
