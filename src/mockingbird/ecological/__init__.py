"""Ecological Interoperability & Submission Workflows v1 (see
docs/ecological-interoperability-submission-v1-contract.md).

This package holds the pure, dependency-free policy and computation modules
for preparing a Reviewed MockingBird Observation for an external ecological
destination: the extra per-destination eligibility layer on top of the
already-accepted research-safe eligibility gate (`destination_eligibility.
py`), the canonical destination-scoped projection plus the static
built-in adapter boundary (`adapters.py`), iNaturalist's credential-free
taxonomy lookup (`inaturalist_taxonomy.py`), iNaturalist's own confirmed
bulk-import CSV shape (`inaturalist_csv.py`), a bounded Darwin Core
Occurrence-core exporter (`darwin_core.py`), and deterministic submission
fingerprinting (`fingerprint.py`).

Mirrors `mockingbird.research`'s own convention exactly: no SQLAlchemy/
FastAPI import anywhere in this package. `mockingbird.repository.
product_repository` owns every database session/query and hands
already-resolved facts in (including an already-built `mockingbird.
research.research_export.ResearchObservation`, which this package composes
rather than duplicates); these modules only classify, map, and reshape
already-settled truth. They never create or mutate product truth
themselves, and they never submit anything to a destination -- see
"Reviewed-truth gate" and "Authorization / secrets" in the governing
contract doc.
"""
