"""Bounded, best-effort Camera Node storage and hardware-quality facts.

Read-only, capability-driven, Raspberry Pi-first -- mirrors `identity.py`'s
own "never fabricate a value the real platform cannot actually confirm"
philosophy exactly: every reader here degrades to `None` (or a
conservative, non-alarming default) rather than guessing, on any platform,
permission, or parsing problem. See "Field-failure acceptance matrix" and
"Hardware-quality telemetry" in docs/camera-node-installer-design.md and
release-execution-state.md Gate E for why this previously did not exist:
"nothing today checks the node's own free space, write pressure, or...
storage health" and no undervoltage/throttling/CPU-temperature telemetry
existed at all.

Bounded, actionable storage-pressure response for the supported release
configuration: the golden-path Camera Node (LAN-connected, no transport
spool configured -- see `mockingbird_node.transport_spool`, which already
has its own independent, already-accepted `min_free_bytes` write-refusal
for the opt-in remote/intermittent-WAN case) has no local storage consumer
of its own besides its pairing/config state and (optional) logs. The
actionable response this module enables is visibility: a critically-low
tier degrades `run_startup_self_test`'s own result to `degraded` (see
`selftest.py`), the same already-established, already-product-visible
mechanism a missing camera already uses -- not a new alerting channel.
"""

from __future__ import annotations

from dataclasses import dataclass
import shutil
import subprocess
from pathlib import Path
from typing import Callable


# Mirrors `mockingbird.storage.database`'s own graduated
# healthy/getting_low/action_recommended/critical ladder and threshold
# values exactly -- a deliberate reuse of that already-disclosed judgment
# call (see the Host's own module-level comment: "this milestone's own
# disclosed judgment call -- no pre-existing canonical policy existed"),
# not a second, independently-derived Node-specific policy invented without
# real Node field evidence. Duplicated, not imported: `mockingbird_node` is
# a separate, deliberately slim installable package and must not depend on
# the main `mockingbird` package (see `doctor.py`'s own identical
# `_DOCTOR_NODE_API_VERSION`/`_DOCTOR_TRANSPORT_PROTOCOL_VERSION`
# duplication precedent). The ratio-based thresholds scale sensibly
# regardless of a Pi SD card's much smaller absolute capacity compared to a
# desktop/NAS drive; the absolute-byte thresholds are carried over
# unchanged for the same reason the Host's own were adopted: a defensible
# starting point, not a re-derived one.
_GETTING_LOW_FREE_BYTES = 5_000_000_000
_GETTING_LOW_FREE_RATIO = 0.15
_ACTION_RECOMMENDED_FREE_BYTES = 1_000_000_000
_ACTION_RECOMMENDED_FREE_RATIO = 0.05
_CRITICAL_FREE_BYTES = 200_000_000
_CRITICAL_FREE_RATIO = 0.01

#: Bounds each individual `vcgencmd` subprocess call. Real, measured
#: evidence against the reference Pi: a single invocation completes in low
#: tens of milliseconds; this is a generous multiple, never blocking
#: `/node/v1/health` noticeably even on a loaded system, and never hanging
#: the process indefinitely if the binary itself is somehow wedged.
VCGENCMD_TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True)
class StorageHealth:
    total_bytes: int
    free_bytes: int
    storage_health_tier: str  # "healthy" | "getting_low" | "action_recommended" | "critical"

    def as_payload(self) -> dict[str, object]:
        return {
            "total_bytes": self.total_bytes,
            "free_bytes": self.free_bytes,
            "storage_health_tier": self.storage_health_tier,
        }


def _storage_health_tier(*, free_bytes: int, total_bytes: int) -> str:
    if total_bytes <= 0:
        # Could not be read at all -- honestly "healthy" rather than
        # fabricating alarm from a fact this probe does not actually have,
        # exactly matching `LocalStorageDiskStatus.storage_health_tier`'s
        # own identical convention on the Host.
        return "healthy"
    free_ratio = free_bytes / total_bytes
    if free_bytes < _CRITICAL_FREE_BYTES or free_ratio < _CRITICAL_FREE_RATIO:
        return "critical"
    if free_bytes < _ACTION_RECOMMENDED_FREE_BYTES or free_ratio < _ACTION_RECOMMENDED_FREE_RATIO:
        return "action_recommended"
    if free_bytes < _GETTING_LOW_FREE_BYTES or free_ratio < _GETTING_LOW_FREE_RATIO:
        return "getting_low"
    return "healthy"


def read_storage_health(directory: Path) -> StorageHealth:
    """Free/total space for the filesystem holding `directory` -- the
    Node's own pairing/config state directory in production (see
    `app.py`'s own caller), never the optional transport spool, which
    already has its own independent, already-accepted free-space guard
    (`TransportSpool`'s `min_free_bytes`). `directory` need not exist yet
    (mirrors the Host's own probe, which falls back sensibly rather than
    requiring the caller to pre-create anything)."""

    probe_directory = directory if directory.is_dir() else directory.parent
    try:
        usage = shutil.disk_usage(probe_directory)
    except OSError:
        return StorageHealth(total_bytes=0, free_bytes=0, storage_health_tier="healthy")
    return StorageHealth(
        total_bytes=usage.total,
        free_bytes=usage.free,
        storage_health_tier=_storage_health_tier(free_bytes=usage.free, total_bytes=usage.total),
    )


@dataclass(frozen=True)
class HardwareQuality:
    #: Bit 0 / bit 2 of `vcgencmd get_throttled` -- true right now, at the
    #: moment this was read. `None` only when `get_throttled` itself could
    #: not be read (see `read_hardware_quality`), never when it returned a
    #: real value of zero (that is a genuine, confirmed "no" answer).
    undervoltage_active: bool | None
    throttled_active: bool | None
    #: Bit 16 / bit 18 -- "has this happened at all since boot," a
    #: separate, historical fact from the "_active" pair above (a
    #: transient undervoltage event earlier in this boot would otherwise
    #: leave zero visible trace by the time anyone looks).
    undervoltage_occurred: bool | None
    throttled_occurred: bool | None
    temperature_celsius: float | None

    def as_payload(self) -> dict[str, object]:
        return {
            "undervoltage_active": self.undervoltage_active,
            "throttled_active": self.throttled_active,
            "undervoltage_occurred": self.undervoltage_occurred,
            "throttled_occurred": self.throttled_occurred,
            "temperature_celsius": self.temperature_celsius,
        }

    @property
    def is_critical(self) -> bool:
        """A currently-active problem, right now -- never the merely
        historical "_occurred" facts alone, which do not describe the
        Node's *current* condition and must not, by themselves, degrade
        self-test (see `selftest.py`)."""

        return bool(self.undervoltage_active) or bool(self.throttled_active)


def _run_vcgencmd(binary: str, *args: str, run: Callable[..., "subprocess.CompletedProcess[str]"]) -> str | None:
    try:
        result = run(
            [binary, *args],
            capture_output=True,
            text=True,
            timeout=VCGENCMD_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _parse_throttled(raw: str | None) -> int | None:
    """`vcgencmd get_throttled` prints exactly `throttled=0x<hex>` on a real
    Pi (confirmed directly against the reference hardware). Any other
    shape is an honest "could not confirm," never a guessed bitmask."""

    if raw is None or not raw.startswith("throttled="):
        return None
    try:
        return int(raw.removeprefix("throttled="), 16)
    except ValueError:
        return None


def _parse_temperature(raw: str | None) -> float | None:
    """`vcgencmd measure_temp` prints exactly `temp=<N.N>'C` on a real Pi
    (confirmed directly against the reference hardware -- note the ASCII
    apostrophe before `C`, not a degree symbol)."""

    if raw is None or not raw.startswith("temp=") or not raw.endswith("'C"):
        return None
    try:
        return float(raw.removeprefix("temp=").removesuffix("'C"))
    except ValueError:
        return None


def read_hardware_quality(
    *, run: Callable[..., "subprocess.CompletedProcess[str]"] = subprocess.run
) -> HardwareQuality | None:
    """Undervoltage/throttling/temperature facts from `vcgencmd`, when
    available. `None` entirely off Raspberry Pi (or any host without
    `vcgencmd` on `PATH`) -- capability-driven, never fabricated, matching
    this product's established "unsupported is hidden or plainly explained,
    never shown as if it might work" doctrine (see "Capability-aware UX" in
    product-doctrine.md). Individual fields degrade to `None` independently
    if only one of the two underlying commands can be read."""

    binary = shutil.which("vcgencmd")
    if binary is None:
        return None
    throttled_bits = _parse_throttled(_run_vcgencmd(binary, "get_throttled", run=run))
    temperature = _parse_temperature(_run_vcgencmd(binary, "measure_temp", run=run))
    if throttled_bits is None and temperature is None:
        return None
    return HardwareQuality(
        undervoltage_active=(bool(throttled_bits & 0x1) if throttled_bits is not None else None),
        throttled_active=(bool(throttled_bits & 0x4) if throttled_bits is not None else None),
        undervoltage_occurred=(bool(throttled_bits & 0x10000) if throttled_bits is not None else None),
        throttled_occurred=(bool(throttled_bits & 0x40000) if throttled_bits is not None else None),
        temperature_celsius=temperature,
    )
