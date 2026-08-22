"""Research / Conservation / Export Interoperability (see
docs/research-conservation-export-contract.md).

This package holds the pure, dependency-free policy and computation modules
for that milestone: research-safe export eligibility (`eligibility.py`),
live-vs-offline acquisition-effort accounting (`acquisition_effort.py`),
bounded conservation/natural-history reporting (`conservation_report.py`),
the provider-neutral exported-Observation shape plus generic CSV/JSON export
(`research_export.py`), and Camtrap DP mapping/validation (`camtrap_dp.py`).

Mirrors `mockingbird.review_provenance` and `mockingbird.species.
identification_eligibility`'s own convention: no SQLAlchemy/FastAPI import
anywhere in this package. `mockingbird.repository.product_repository` owns
every database session/query and hands already-resolved facts in; these
modules only classify, aggregate, and reshape already-settled truth. They
never create or mutate product truth themselves -- see "Research truth
invariant" in the governing milestone brief.
"""
