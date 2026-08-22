"""A small, bounded, privacy-safe diagnostic bundle for a support conversation.

Named as a still-open capability by the roadmap itself before this
milestone (`docs/roadmap.md` Gate E, "Support bundle and tracing": *"a
privacy-safe support bundle (bounded diagnostic export -- health-check
output, redacted logs, schema/version facts, no raw media or credentials by
default) ... named, open capabilities -- neither exists today"*) and
explicitly scoped out of Doctor's own v1 (see "Non-goals" in
docs/mockingbird-doctor-operational-health-contract.md). This module is
that capability's first bounded version.

Design invariants, mirroring `diagnostics.doctor`'s own (see that module's
docstring for the full reasoning):

- **Never constructs `ProductRepository`.** Its `__init__` can run schema
  migrations in place -- exactly the side effect a diagnostic tool must
  never risk as a surprise consequence of "I just wanted to describe a
  problem to support." Every read here is a bare, read-only SQLAlchemy
  query, reusing `diagnostics.doctor.resolve_doctor_environment`/
  `create_database_engine` rather than a second environment-resolution
  implementation.
- **Reuses Doctor wholesale for the health section** (`run_doctor()`) --
  never a second, parallel health computation.
- **Structural facts only for Sources**, matching the exact fields Doctor's
  own Camera Node check already reads (`CameraSourceModel.id`/`.name`/
  `.kind`/`.status`) -- never a Source's provider configuration (URLs,
  addresses, credentials), which would require either constructing
  `ProductRepository` (ruled out above) or duplicating the
  `SourceProviderField.secret`/`_sanitize_source_provider_config` machinery
  outside the one place that owns it correctly. Disclosed as a v1 scope
  limit (see "Known v1 scope limits" below), not a silent omission.
- **Log tail is redacted defensively**, not merely assumed safe: any
  line containing a credential-shaped substring is never included verbatim.
"""

from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.engine import Engine

from mockingbird import __version__ as APP_VERSION
from mockingbird.diagnostics.doctor import (
    DoctorReport,
    resolve_doctor_environment,
    run_doctor,
)
from mockingbird.research.camtrap_dp import CAMTRAP_DP_PROFILE_VERSION
from mockingbird.research.research_export import RESEARCH_EXPORT_SCHEMA_VERSION
from mockingbird.runtime_state import LOG_FILENAME, LOG_SUBDIRECTORY
from mockingbird.storage.database import create_database_engine, sqlite_database_path
from mockingbird.storage.models import CameraSourceModel

# Mirrors `doctor._FORBIDDEN_SUBSTRINGS`' equivalent test precedent
# (`test_product_health_never_includes_credential_shaped_values`,
# `test_report_json_never_includes_sensitive_value_shaped_text`) -- applied
# here defensively to the log tail specifically, since a log line is
# free-form text this module does not otherwise control the shape of.
_CREDENTIAL_SHAPED_SUBSTRINGS = ("credential", "bearer", "password", "api_key", "secret", "token")
# Deliberately does not explain *why* using any of the forbidden substrings
# themselves (e.g. spelling out "credential-shaped") -- the placeholder text
# is scanned by the exact same safety test as everything else in the bundle
# (test_bundle_never_includes_credential_shaped_text_anywhere), so its own
# wording must stay clear of the words it exists to keep out.
_REDACTED_LOG_LINE = "[line omitted from support bundle -- looked sensitive]"

DEFAULT_LOG_TAIL_LINES = 500


class SupportBundleSourceSummary(BaseModel):
    """Structural-only Source facts -- see the module docstring's "Known v1
    scope limits" for why provider configuration is deliberately excluded."""

    id: str
    name: str
    kind: str
    status: str


class SupportBundleManifest(BaseModel):
    """The bundle's own top-level, always-present facts -- printed first so
    a support conversation can orient before reading the rest."""

    generated_at: datetime
    app_version: str
    research_export_schema_version: str
    camtrap_dp_profile_version: str
    database_path: str
    source_count: int
    log_tail_lines_included: int
    log_tail_truncated: bool
    log_tail_redacted_line_count: int


def _gather_source_summaries(engine: Engine) -> list[SupportBundleSourceSummary]:
    with engine.connect() as connection:
        rows = connection.execute(
            select(
                CameraSourceModel.id,
                CameraSourceModel.name,
                CameraSourceModel.kind,
                CameraSourceModel.status,
            )
        ).all()
    return [
        SupportBundleSourceSummary(id=row[0], name=row[1], kind=row[2], status=row[3]) for row in rows
    ]


def _redacted_log_tail(*, runtime_home: Path, max_lines: int) -> tuple[list[str], bool, int]:
    """Return `(lines, truncated, redacted_count)`. `truncated` is True when
    the log file has more than `max_lines` lines -- the bundle only ever
    carries the most recent ones, matching the already-bounded rotating log
    file this reads from (see `runtime_state.configure_file_logging`).

    Computes the log path directly from `runtime_home` (the same
    `<home>/logs/mockingbird.log` convention `configure_file_logging`
    itself writes to) rather than reading `runtime_state.current_log_path()`
    -- that function only ever reflects *this Python process's own* prior
    `configure_file_logging()` call, which the support-bundle CLI (a
    separate process invocation from the running app) never makes. Only
    the current log file is read, never its rotated `.1`/`.2`/`.3`
    backups -- a disclosed, deliberate bound, not an oversight.
    """

    log_path = runtime_home / LOG_SUBDIRECTORY / LOG_FILENAME
    if not log_path.is_file():
        return [], False, 0
    try:
        all_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return [], False, 0
    truncated = len(all_lines) > max_lines
    tail = all_lines[-max_lines:]
    redacted_count = 0
    safe_lines: list[str] = []
    for line in tail:
        lowered = line.lower()
        if any(substring in lowered for substring in _CREDENTIAL_SHAPED_SUBSTRINGS):
            safe_lines.append(_REDACTED_LOG_LINE)
            redacted_count += 1
        else:
            safe_lines.append(line)
    return safe_lines, truncated, redacted_count


def write_support_bundle(
    output_path: Path,
    *,
    runtime_home: Path | None = None,
    log_tail_lines: int = DEFAULT_LOG_TAIL_LINES,
    now: datetime | None = None,
) -> Path:
    """Assemble and write a bounded support bundle `.zip` to `output_path`.

    Contains `manifest.json` (this bundle's own facts), `doctor_report.json`
    (a full `run_doctor()` report), `sources.json` (structural-only Source
    summaries), and `log_tail.txt` (the most recent, redacted log lines).
    Returns `output_path` on success.
    """

    generated_at = now or datetime.now(UTC)
    environment = resolve_doctor_environment(runtime_home=runtime_home)
    doctor_report: DoctorReport = run_doctor(runtime_home=environment.runtime_home, now=generated_at)

    database_path = sqlite_database_path(environment.db_url)
    sources: list[SupportBundleSourceSummary] = []
    if database_path.is_file():
        engine = create_database_engine(environment.db_url)
        try:
            sources = _gather_source_summaries(engine)
        finally:
            engine.dispose()

    log_lines, log_truncated, redacted_count = _redacted_log_tail(
        runtime_home=environment.runtime_home, max_lines=log_tail_lines
    )

    manifest = SupportBundleManifest(
        generated_at=generated_at,
        app_version=APP_VERSION,
        research_export_schema_version=RESEARCH_EXPORT_SCHEMA_VERSION,
        camtrap_dp_profile_version=CAMTRAP_DP_PROFILE_VERSION,
        database_path=str(database_path),
        source_count=len(sources),
        log_tail_lines_included=len(log_lines),
        log_tail_truncated=log_truncated,
        log_tail_redacted_line_count=redacted_count,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("manifest.json", manifest.model_dump_json(indent=2))
        bundle.writestr("doctor_report.json", doctor_report.model_dump_json(indent=2))
        bundle.writestr(
            "sources.json",
            json.dumps([source.model_dump() for source in sources], indent=2, default=str),
        )
        bundle.writestr("log_tail.txt", "\n".join(log_lines))
    return output_path


def default_output_path(*, runtime_home: Path | None = None, now: datetime | None = None) -> Path:
    environment = resolve_doctor_environment(runtime_home=runtime_home)
    timestamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return environment.runtime_home / "data" / f"mockingbird-support-bundle-{timestamp}.zip"


def read_bundle_member_json(bundle_path: Path, member_name: str) -> Any:
    """Test/support convenience: read one JSON member back out of a written
    bundle without re-deriving the zip layout by hand."""

    with zipfile.ZipFile(bundle_path, "r") as bundle:
        return json.loads(bundle.read(member_name))
