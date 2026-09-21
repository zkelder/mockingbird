"""Canonical CSV-injection defense, shared by every CSV-producing export path.

Originally introduced (Ecological Interoperability & Submission Workflows
v1) as a private helper inside `mockingbird.repository.product_repository`.
Pre-Release Trust & Correctness Correction v1 (DI-2) found two real CSV
writers -- `ProductRepository._write_classifier_manifest_csv` and
`mockingbird.ecological.inaturalist_csv.build_inaturalist_csv` -- that never
called it, despite documentation claiming this defense was applied broadly.
Extracted to this dependency-free module (rather than duplicated) so every
CSV writer, in any module, can import the one canonical implementation
without risking a second, divergent copy.
"""

from __future__ import annotations

from typing import Any

#: Leading characters a spreadsheet application (Excel, Google Sheets,
#: LibreOffice Calc) treats as the start of a formula when a CSV cell is
#: opened -- the classic "CSV injection" class. Applies to every CSV this
#: product writes, since a user-supplied free-text field (a Camtrap DP
#: `site_name`, an ecological-submission `place_name`, a Darwin Core
#: `locality`, a reviewed species label) can end up as a cell value verbatim.
CSV_FORMULA_TRIGGER_CHARACTERS = ("=", "+", "-", "@", "\t", "\r")


def csv_injection_safe_value(value: Any) -> Any:
    """Prefix a string cell that would otherwise be interpreted as a
    formula with a single quote -- the standard, widely-used mitigation
    (OWASP's own recommended CSV-injection defense). Never touches a
    non-string value (a number, `None`, a bool) -- there is nothing to
    sanitize there, and stringifying one would silently change its type in
    the exported file. A string that starts with `-` or `+` but is itself a
    plain, valid number (a formatted negative/positive latitude/longitude,
    for example) is never a formula and must round-trip unchanged -- a
    real, caught-by-testing bug in an earlier version of this function
    corrupted every western/southern-hemisphere coordinate this way."""

    if not isinstance(value, str) or not value.startswith(CSV_FORMULA_TRIGGER_CHARACTERS):
        return value
    try:
        float(value)
    except ValueError:
        return f"'{value}"
    return value


__all__ = ["CSV_FORMULA_TRIGGER_CHARACTERS", "csv_injection_safe_value"]
