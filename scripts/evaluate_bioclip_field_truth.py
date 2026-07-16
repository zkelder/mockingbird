#!/usr/bin/env python3
"""Evaluate stored BioCLIP evidence against ReviewLabel truth without inference."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from typing import Any, Mapping, Sequence
from urllib.parse import unquote

from mockingbird.species.bioclip_adapter import BIOCLIP_ADAPTER_ID
from mockingbird.species.bioclip_evaluation import (
    BioClipFieldTruthReport,
    EvaluationConfig,
    StoredReviewLabel,
    StoredSpeciesSuggestion,
    TaxonomyDescriptor,
    evaluate_bioclip_field_truth,
    render_terminal_report,
)
from mockingbird.storage.database import (
    CURRENT_DATABASE_SCHEMA_VERSION,
    DB_URL_ENV_VAR,
    DEFAULT_DB_URL,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class EvaluationCommandError(RuntimeError):
    """A safe, user-facing failure from the read-only evaluation boundary."""


@dataclass(frozen=True)
class EvaluationDatabaseRecords:
    review_labels: tuple[StoredReviewLabel, ...]
    species_suggestions: tuple[StoredSpeciesSuggestion, ...]
    taxonomy: tuple[TaxonomyDescriptor, ...]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Read the local SQLite database in hard read-only mode and compare "
            "already-stored BioCLIP suggestions with final ReviewLabel corrections. "
            "No model runs and no product or operational state is changed."
        )
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv(DB_URL_ENV_VAR, DEFAULT_DB_URL),
        help=(
            "Local sqlite:/// database URL. Defaults to MOCKINGBIRD_DB_URL or "
            "data/mockingbird.sqlite3."
        ),
    )
    parser.add_argument(
        "--minimum-examples",
        type=_positive_int,
        default=30,
        help="Minimum eligible reviewed examples before the descriptive gate is met.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        default=None,
        help="Optional JSON path under the ignored local data/ directory.",
    )
    return parser.parse_args(argv)


def resolve_sqlite_database_path(
    database_url: str,
    *,
    project_root: Path = PROJECT_ROOT,
) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise EvaluationCommandError(
            "The field evaluator supports only a local sqlite:/// database URL."
        )
    raw_path = database_url[len(prefix) :]
    if not raw_path or raw_path == ":memory:" or "?" in raw_path or "#" in raw_path:
        raise EvaluationCommandError(
            "The field evaluator requires one existing local SQLite database file."
        )
    path = Path(unquote(raw_path)).expanduser()
    if not path.is_absolute():
        path = project_root / path
    resolved = path.resolve()
    if not resolved.is_file():
        raise EvaluationCommandError(
            f"The configured SQLite database file does not exist ({resolved.name})."
        )
    return resolved


def safe_database_identifier(database_path: Path) -> str:
    fingerprint = hashlib.sha256(
        str(database_path.resolve()).encode("utf-8")
    ).hexdigest()[:12]
    return f"{database_path.name}#{fingerprint}"


def load_evaluation_records(database_path: Path) -> EvaluationDatabaseRecords:
    """Read one coherent SQLite snapshot through a query-only connection."""

    uri = f"{database_path.resolve().as_uri()}?mode=ro"
    try:
        connection = sqlite3.connect(uri, uri=True, timeout=10)
    except sqlite3.Error as error:
        raise EvaluationCommandError(
            "Could not open the configured SQLite database in read-only mode."
        ) from error

    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only = ON")
        query_only = connection.execute("PRAGMA query_only").fetchone()
        if query_only is None or query_only[0] != 1:
            raise EvaluationCommandError(
                "SQLite did not confirm the required query-only safety mode."
            )
        connection.execute("BEGIN")
        _validate_schema(connection)
        review_rows = connection.execute(
            """
            SELECT id, target_type, target_id, label, created_at
            FROM review_labels
            ORDER BY created_at, id
            """
        ).fetchall()
        suggestion_rows = connection.execute(
            """
            SELECT
                id,
                event_id,
                visit_id,
                adapter_id,
                suggested_label,
                suggested_scientific_name,
                confidence,
                rank,
                alternatives_json,
                evidence_region_json,
                status,
                created_at
            FROM species_suggestions
            WHERE adapter_id = ?
            ORDER BY created_at, rank, id
            """,
            (BIOCLIP_ADAPTER_ID,),
        ).fetchall()
        taxonomy_rows = connection.execute(
            """
            SELECT label, category, is_species
            FROM taxonomy_labels
            ORDER BY label
            """
        ).fetchall()
    except EvaluationCommandError:
        raise
    except sqlite3.Error as error:
        raise EvaluationCommandError(
            "The local database could not provide the stored evaluation records."
        ) from error
    finally:
        connection.close()

    return EvaluationDatabaseRecords(
        review_labels=tuple(_review_label_from_row(row) for row in review_rows),
        species_suggestions=tuple(
            _species_suggestion_from_row(row) for row in suggestion_rows
        ),
        taxonomy=tuple(_taxonomy_from_row(row) for row in taxonomy_rows),
    )


def build_report(
    database_path: Path,
    *,
    minimum_examples: int,
    generated_at: datetime | None = None,
) -> BioClipFieldTruthReport:
    records = load_evaluation_records(database_path)
    return evaluate_bioclip_field_truth(
        records.review_labels,
        records.species_suggestions,
        records.taxonomy,
        generated_at=generated_at or datetime.now(UTC),
        database_identifier=safe_database_identifier(database_path),
        config=EvaluationConfig(minimum_examples=minimum_examples),
    )


def resolve_json_output_path(
    requested_path: Path,
    *,
    project_root: Path = PROJECT_ROOT,
) -> Path:
    path = requested_path.expanduser()
    if not path.is_absolute():
        path = project_root / path
    resolved = path.resolve()
    data_root = (project_root / "data").resolve()
    if not resolved.is_relative_to(data_root):
        raise EvaluationCommandError(
            "JSON reports must stay under the ignored local data/ directory."
        )
    if resolved.suffix.lower() != ".json":
        raise EvaluationCommandError("JSON report output must use a .json extension.")
    return resolved


def write_json_report(
    report: BioClipFieldTruthReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            dir=output_path.parent,
            delete=False,
        ) as temporary:
            temporary.write(report.to_json())
            temporary.write("\n")
            temporary_path = Path(temporary.name)
        temporary_path.replace(output_path)
    except OSError as error:
        raise EvaluationCommandError(
            "The JSON report could not be written under the local data directory."
        ) from error
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        database_path = resolve_sqlite_database_path(
            args.database_url,
            project_root=PROJECT_ROOT,
        )
        report = build_report(
            database_path,
            minimum_examples=args.minimum_examples,
        )
        json_output = (
            resolve_json_output_path(args.json_output, project_root=PROJECT_ROOT)
            if args.json_output is not None
            else None
        )
        if json_output is not None:
            write_json_report(report, json_output)
    except EvaluationCommandError as error:
        print(f"BioCLIP field evaluation failed: {error}", file=sys.stderr)
        return 1

    print(render_terminal_report(report))
    if json_output is not None:
        print()
        print(f"JSON report: {json_output.relative_to(PROJECT_ROOT)}")
    return 0


def _validate_schema(connection: sqlite3.Connection) -> None:
    table = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'mockingbird_schema'
        """
    ).fetchone()
    if table is None:
        raise EvaluationCommandError(
            "The database has no MockingBird schema record; start the app normally "
            "before evaluating it."
        )
    row = connection.execute(
        "SELECT version FROM mockingbird_schema WHERE singleton_id = 1"
    ).fetchone()
    if row is None or row[0] != CURRENT_DATABASE_SCHEMA_VERSION:
        found = "missing" if row is None else str(row[0])
        raise EvaluationCommandError(
            "Database schema version is not current "
            f"(found {found}, expected {CURRENT_DATABASE_SCHEMA_VERSION}). "
            "The evaluator will not migrate it."
        )


def _review_label_from_row(row: sqlite3.Row) -> StoredReviewLabel:
    return StoredReviewLabel(
        id=str(row["id"]),
        target_type=str(row["target_type"]),
        target_id=str(row["target_id"]),
        label=str(row["label"]),
        created_at=_stored_datetime(row["created_at"]),
    )


def _species_suggestion_from_row(row: sqlite3.Row) -> StoredSpeciesSuggestion:
    return StoredSpeciesSuggestion(
        id=str(row["id"]),
        event_id=_optional_text(row["event_id"]),
        visit_id=_optional_text(row["visit_id"]),
        adapter_id=str(row["adapter_id"]),
        suggested_label=str(row["suggested_label"]),
        suggested_scientific_name=_optional_text(
            row["suggested_scientific_name"]
        ),
        confidence=(
            float(row["confidence"]) if row["confidence"] is not None else None
        ),
        rank=int(row["rank"]),
        alternatives=_stored_alternatives(row["alternatives_json"]),
        evidence_region=_stored_mapping(row["evidence_region_json"]),
        status=str(row["status"]),
        created_at=_stored_datetime(row["created_at"]),
    )


def _taxonomy_from_row(row: sqlite3.Row) -> TaxonomyDescriptor:
    return TaxonomyDescriptor(
        label=str(row["label"]),
        category=str(row["category"]),
        is_species=bool(row["is_species"]),
    )


def _stored_alternatives(value: Any) -> tuple[Mapping[str, Any], ...] | None:
    parsed = _stored_json(value)
    if not isinstance(parsed, list):
        return None
    return tuple(
        item if isinstance(item, dict) else {"invalid_stored_value": item}
        for item in parsed
    )


def _stored_mapping(value: Any) -> Mapping[str, Any] | None:
    parsed = _stored_json(value)
    return parsed if isinstance(parsed, dict) else None


def _stored_json(value: Any) -> Any:
    if not isinstance(value, str):
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _stored_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise EvaluationCommandError(
            "A stored evaluation record has an invalid creation timestamp."
        )
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise EvaluationCommandError(
            "A stored evaluation record has an invalid creation timestamp."
        ) from error
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _optional_text(value: Any) -> str | None:
    return str(value).strip() if value is not None and str(value).strip() else None


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be at least 1")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
