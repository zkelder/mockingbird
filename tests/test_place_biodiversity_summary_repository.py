"""Biodiversity & Place Intelligence v1: repository/API integration
coverage (see docs/biodiversity-place-intelligence-v1-contract.md).

Complements `tests/test_place_biodiversity_summary.py`'s pure-domain
coverage of `mockingbird.analytics.place_biodiversity_summary` with the
real integration path: durable SQLite state, `ProductRepository.
place_biodiversity_summary`/`wildlife_journal_history`'s new
`place_context` field, and their HTTP routes. Confirmed truth is
established through the real `create_review_label`/`create_species_
suggestion`/`revise_visit_review` write paths, matching `tests/
test_historical_baseline_repository.py`'s own established convention --
never by hand-setting `VisitModel.reviewed_label`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from tests.conftest import LegacyAuthenticatedSyncTestClient

from mockingbird.analytics.historical_baseline import (
    MIN_DISTINCT_USABLE_DAYS_FOR_REGULAR,
    MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE,
    USABLE_DAY_MONITORED_SECONDS_THRESHOLD,
)
from mockingbird.analytics.place_biodiversity_summary import RECENTLY_OBSERVED_WINDOW_DAYS
from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import (
    CurrentUser,
    EnvironmentalContextSettingsUpdate,
    PlaceHabitatFactCreate,
    PlacePhenologyObservationCreate,
    ReviewCorrectionCreate,
    SpeciesSuggestionCreateRequest,
    UserRole,
    VisitReviewRevisionCreate,
    WildlifeJournalHistoryRequest,
)
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MonitoringExposureIntervalModel,
    StreamModel,
    VisitModel,
)

SOURCE_ID = "source-biodiversity-summary"
STREAM_ID = "stream-biodiversity-summary"

# Comfortably far from the schema's own seeded demo content, and from any
# DST transition, so distinct-day/recency counts stay exact.
NOW = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)

USABLE_HOURS = USABLE_DAY_MONITORED_SECONDS_THRESHOLD / 3600.0


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    with repository.session_factory() as session:
        with session.begin():
            demo = session.get(CameraSourceModel, "source-backyard-demo")
            assert demo is not None
            demo.status = "archived"
            session.add(
                CameraSourceModel(
                    id=SOURCE_ID,
                    name="Biodiversity summary camera",
                    kind="manual_upload",
                    status="connected",
                    description="Focused biodiversity-summary fixture.",
                )
            )
            session.add(
                StreamModel(
                    id=STREAM_ID,
                    source_id=SOURCE_ID,
                    name="Yard stream",
                    description="Focused biodiversity-summary fixture.",
                    is_live=False,
                )
            )
    yield repository
    configure_repository(None)


def _acting_user() -> CurrentUser:
    return CurrentUser(
        id="user-test-admin",
        display_name="Test Admin",
        login_identity="test-admin",
        role=UserRole.administrator,
        enabled=True,
    )


def _add_visit(repository: ProductRepository, *, visit_id: str, at: datetime) -> None:
    event_id = f"event-{visit_id}"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=STREAM_ID,
                    title=f"Biodiversity summary fixture {visit_id}",
                    event_type="manual_media_import",
                    started_at=at,
                    ended_at=at + timedelta(seconds=20),
                    primary_zone_id=None,
                    review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id=visit_id,
                    event_id=event_id,
                    subject_label="unknown_bird",
                    species_guess=None,
                    confidence=None,
                    reviewed_label=None,
                    review_status="needs_review",
                    representative_media_path=None,
                    zone_id=None,
                    is_superseded=False,
                )
            )


def _confirm(repository: ProductRepository, *, visit_id: str, label: str) -> None:
    repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id=visit_id, label=label, review_origin="human")
    )


def _revise(repository: ProductRepository, *, visit_id: str, label: str) -> None:
    with repository.session_factory() as session:
        token = repository._review_state_token(session, "visit", visit_id)
    repository.revise_visit_review(
        visit_id,
        VisitReviewRevisionCreate(
            label=label,
            expected_state_token=token,
            idempotency_key=f"revise-{visit_id}-{label}",
            review_origin="human",
        ),
    )


def _suggest(repository: ProductRepository, *, visit_id: str, label: str) -> None:
    repository.create_species_suggestion(
        SpeciesSuggestionCreateRequest(
            source_id=SOURCE_ID,
            stream_id=STREAM_ID,
            event_id=f"event-{visit_id}",
            visit_id=visit_id,
            adapter_id="fixture",
            adapter_name="Fixture suggester",
            suggested_label=label,
        )
    )


def _add_usable_day(repository: ProductRepository, *, day: datetime, hours: float = USABLE_HOURS) -> None:
    interval_id = f"exposure-{day.date().isoformat()}"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MonitoringExposureIntervalModel(
                    id=interval_id,
                    stream_id=STREAM_ID,
                    source_id=SOURCE_ID,
                    runtime_generation_id=f"generation-{interval_id}",
                    started_at=day,
                    last_confirmed_fresh_at=day + timedelta(hours=hours),
                    ended_at=day + timedelta(hours=hours),
                    close_reason="provider_failure",
                    created_at=day,
                    updated_at=day + timedelta(hours=hours),
                )
            )


def _establish_baseline(repository: ProductRepository, *, before: datetime = NOW) -> None:
    for offset in range(1, 1 + MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE):
        _add_usable_day(repository, day=before - timedelta(days=offset))


def _taxa_labels(summary) -> set[str]:
    return {entry.label for entry in summary.taxa}


# 1. Empty / sparse Place states -----------------------------------------


def test_brand_new_place_has_no_taxa_and_an_honest_warning(repository: ProductRepository) -> None:
    summary = repository.place_biodiversity_summary(now=NOW)

    assert summary.taxa == []
    assert summary.distinct_species_count == 0
    assert summary.historical_baseline.maturity == "insufficient"
    assert summary.historical_baseline.total_monitored_seconds is None
    assert len(summary.warnings) == 1
    assert "No monitoring history recorded yet" in summary.warnings[0]


def test_sparse_monitoring_gets_the_softer_insufficient_warning(repository: ProductRepository) -> None:
    _add_usable_day(repository, day=NOW - timedelta(days=1))
    _add_visit(repository, visit_id="cardinal-1", at=NOW - timedelta(hours=1))
    _confirm(repository, visit_id="cardinal-1", label="northern_cardinal")

    summary = repository.place_biodiversity_summary(now=NOW)

    assert summary.historical_baseline.maturity == "insufficient"
    assert summary.historical_baseline.total_monitored_seconds is not None
    assert len(summary.warnings) == 1
    assert "Not enough monitored history" in summary.warnings[0]
    # A real confirmed sighting is still shown even while immature.
    assert "northern_cardinal" in _taxa_labels(summary)


# 2. Authoritative vs. provisional truth boundary -------------------------


def test_confirmed_species_counts_toward_authoritative_totals(repository: ProductRepository) -> None:
    _establish_baseline(repository)
    _add_visit(repository, visit_id="cardinal-1", at=NOW - timedelta(hours=1))
    _confirm(repository, visit_id="cardinal-1", label="northern_cardinal")

    summary = repository.place_biodiversity_summary(now=NOW)

    assert _taxa_labels(summary) == {"northern_cardinal"}
    assert summary.distinct_species_count == 1
    assert summary.historical_baseline.distinct_taxa_count == 1


def test_provisional_only_species_never_contaminates_authoritative_counts(
    repository: ProductRepository,
) -> None:
    _establish_baseline(repository)
    _add_visit(repository, visit_id="finch-1", at=NOW - timedelta(hours=1))
    _suggest(repository, visit_id="finch-1", label="house_finch")

    summary = repository.place_biodiversity_summary(now=NOW)

    assert summary.taxa == []
    assert summary.distinct_species_count == 0
    assert summary.new_taxa == []
    assert summary.regular_taxa == []
    provisional_labels = {entry.label for entry in summary.provisional_taxa}
    assert "house_finch" in provisional_labels
    assert all(not entry.is_confirmed for entry in summary.provisional_taxa)


# 3. New / regular / recently-observed semantics ---------------------------


def test_first_ever_confirmation_is_new_once_baseline_is_established(
    repository: ProductRepository,
) -> None:
    _establish_baseline(repository)
    _add_visit(repository, visit_id="cardinal-1", at=NOW - timedelta(hours=1))
    _confirm(repository, visit_id="cardinal-1", label="northern_cardinal")

    summary = repository.place_biodiversity_summary(now=NOW)

    assert {entry.label for entry in summary.new_taxa} == {"northern_cardinal"}
    assert summary.regular_taxa == []


def test_first_ever_confirmation_before_established_baseline_is_first_record_not_new(
    repository: ProductRepository,
) -> None:
    # No usable days seeded at all -- baseline stays "insufficient".
    _add_visit(repository, visit_id="cardinal-1", at=NOW - timedelta(hours=1))
    _confirm(repository, visit_id="cardinal-1", label="northern_cardinal")

    summary = repository.place_biodiversity_summary(now=NOW)

    [entry] = [e for e in summary.taxa if e.label == "northern_cardinal"]
    assert entry.historical_status.status == "first_record"
    # "new_taxa" still includes first_record entries (see the contract doc)
    # -- the softer wording lives on the entry itself, not the bucket.
    assert entry in summary.new_taxa


def test_regular_requires_enough_distinct_usable_days(repository: ProductRepository) -> None:
    # Reuses 3 of the 7 already-usable days `_establish_baseline` seeds
    # (offsets 1..7 before NOW) rather than adding new ones -- adding a
    # second interval on a date already covered by `_establish_baseline`
    # would collide on `_add_usable_day`'s own per-date id scheme.
    _establish_baseline(repository)
    for offset in range(1, 1 + MIN_DISTINCT_USABLE_DAYS_FOR_REGULAR):
        day = NOW - timedelta(days=offset)
        _add_visit(repository, visit_id=f"cardinal-{offset}", at=day + timedelta(hours=1))
        _confirm(repository, visit_id=f"cardinal-{offset}", label="northern_cardinal")

    summary = repository.place_biodiversity_summary(now=NOW)

    assert {entry.label for entry in summary.regular_taxa} == {"northern_cardinal"}


def test_a_single_confirmation_is_not_yet_regular(repository: ProductRepository) -> None:
    _establish_baseline(repository)
    _add_visit(repository, visit_id="cardinal-1", at=NOW - timedelta(hours=1))
    _confirm(repository, visit_id="cardinal-1", label="northern_cardinal")

    summary = repository.place_biodiversity_summary(now=NOW)

    assert summary.regular_taxa == []


def test_recently_observed_excludes_a_taxon_only_seen_before_the_window(
    repository: ProductRepository,
) -> None:
    _establish_baseline(repository)
    stale_at = NOW - timedelta(days=RECENTLY_OBSERVED_WINDOW_DAYS + 5)
    _add_usable_day(repository, day=stale_at)
    _add_visit(repository, visit_id="cardinal-1", at=stale_at + timedelta(hours=1))
    _confirm(repository, visit_id="cardinal-1", label="northern_cardinal")

    summary = repository.place_biodiversity_summary(now=NOW)

    # A real, honest fact either way: still a known taxon, just not "recent".
    assert "northern_cardinal" in _taxa_labels(summary)
    assert summary.recently_observed_taxa == []


def test_recently_observed_includes_a_taxon_seen_within_the_window(
    repository: ProductRepository,
) -> None:
    _establish_baseline(repository)
    _add_visit(repository, visit_id="cardinal-1", at=NOW - timedelta(days=1))
    _confirm(repository, visit_id="cardinal-1", label="northern_cardinal")

    summary = repository.place_biodiversity_summary(now=NOW)

    assert {entry.label for entry in summary.recently_observed_taxa} == {"northern_cardinal"}


# 4. Habitat + environmental context embedding ------------------------------


def test_habitat_and_environmental_context_are_embedded(repository: ProductRepository) -> None:
    repository.add_place_habitat_fact(
        PlaceHabitatFactCreate(category="setting", label="Woodland edge"), acting_user=_acting_user()
    )
    repository.update_environmental_context_settings(
        EnvironmentalContextSettingsUpdate(latitude=40.7, longitude=-74.0), acting_user=_acting_user()
    )

    summary = repository.place_biodiversity_summary(now=NOW)

    assert [fact.label for fact in summary.habitat_context.habitat_facts] == ["Woodland edge"]
    assert summary.environmental_context.available is True


def test_missing_habitat_and_environmental_data_degrades_gracefully(
    repository: ProductRepository,
) -> None:
    summary = repository.place_biodiversity_summary(now=NOW)

    assert summary.habitat_context.habitat_facts == []
    assert summary.environmental_context.available is False
    assert summary.environmental_context.reason == "not_configured"


# 5. Taxon Place History (`wildlife_journal_history.place_context`) --------


def test_taxon_history_place_context_uses_the_true_latest_observation(
    repository: ProductRepository,
) -> None:
    repository.update_environmental_context_settings(
        EnvironmentalContextSettingsUpdate(latitude=40.7, longitude=-74.0), acting_user=_acting_user()
    )
    older_at = NOW - timedelta(days=10)
    newer_at = NOW - timedelta(days=1)
    _add_visit(repository, visit_id="cardinal-old", at=older_at)
    _confirm(repository, visit_id="cardinal-old", label="northern_cardinal")
    _add_visit(repository, visit_id="cardinal-new", at=newer_at)
    _confirm(repository, visit_id="cardinal-new", label="northern_cardinal")

    history = repository.wildlife_journal_history(
        "northern_cardinal", WildlifeJournalHistoryRequest(), now=NOW
    )

    assert history is not None
    assert history.place_context is not None
    assert history.place_context.observed_at == newer_at
    assert history.place_context.environmental_context.available is True


def test_taxon_history_place_context_includes_current_phenology(
    repository: ProductRepository,
) -> None:
    observed_at = NOW - timedelta(days=1)
    repository.add_place_phenology_observation(
        PlacePhenologyObservationCreate(
            subject_label="Deciduous canopy",
            phenomenon="leafed out",
            observed_start_date=observed_at.date() - timedelta(days=30),
            observed_end_date=observed_at.date() + timedelta(days=30),
        ),
        acting_user=_acting_user(),
    )
    _add_visit(repository, visit_id="cardinal-1", at=observed_at)
    _confirm(repository, visit_id="cardinal-1", label="northern_cardinal")

    history = repository.wildlife_journal_history(
        "northern_cardinal", WildlifeJournalHistoryRequest(), now=NOW
    )

    assert history is not None
    assert history.place_context is not None
    phenomena = [entry.phenomenon for entry in history.place_context.phenology_context]
    assert phenomena == ["leafed out"]
    assert history.place_context.phenology_context[0].status == "current"


def test_taxon_history_with_no_confirmed_records_has_no_place_context(
    repository: ProductRepository,
) -> None:
    # A wildlife-category label the seeded taxonomy knows, but never
    # confirmed here -- `place_context` must not fabricate one.
    history = repository.wildlife_journal_history(
        "northern_cardinal", WildlifeJournalHistoryRequest(), now=NOW
    )

    assert history is not None
    assert history.observation_count == 0
    assert history.place_context is None


# 6. HTTP route ---------------------------------------------------------


def test_api_route_returns_the_summary(repository: ProductRepository) -> None:
    _establish_baseline(repository)
    _add_visit(repository, visit_id="cardinal-1", at=NOW - timedelta(hours=1))
    _confirm(repository, visit_id="cardinal-1", label="northern_cardinal")

    client = LegacyAuthenticatedSyncTestClient(app)
    response = client.get("/api/place/biodiversity-summary")

    assert response.status_code == 200
    body = response.json()
    assert body["distinct_species_count"] == 1
    assert [entry["label"] for entry in body["new_taxa"]] == ["northern_cardinal"]
    assert body["historical_baseline"]["maturity"] == "established"
    assert "habitat_context" in body
    assert "environmental_context" in body


# 7. The mandatory correction test -----------------------------------------
#
# "Prove that if a human changes an authoritative species review: Place
# biodiversity counts update correctly, old taxon history no longer treats
# the superseded identity as authoritative, new taxon history reflects the
# correction, 'new'/recurring state is recomputed correctly, no stale
# aggregate survives." -- the milestone brief's own acceptance requirement.


def test_human_correction_updates_place_biodiversity_intelligence_correctly(
    repository: ProductRepository,
) -> None:
    _establish_baseline(repository)
    corrected_at = NOW - timedelta(hours=1)
    _add_visit(repository, visit_id="mystery-1", at=corrected_at)
    _confirm(repository, visit_id="mystery-1", label="northern_cardinal")

    before = repository.place_biodiversity_summary(now=NOW)
    assert "northern_cardinal" in _taxa_labels(before)
    assert {e.label for e in before.new_taxa} == {"northern_cardinal"}
    before_history_a = repository.wildlife_journal_history(
        "northern_cardinal", WildlifeJournalHistoryRequest(), now=NOW
    )
    assert before_history_a is not None and before_history_a.observation_count == 1

    # A human reviews the correction: it was actually a House Finch.
    _revise(repository, visit_id="mystery-1", label="house_finch")

    after = repository.place_biodiversity_summary(now=NOW)
    # 1. Place biodiversity counts update correctly.
    assert _taxa_labels(after) == {"house_finch"}
    assert after.distinct_species_count == 1
    assert after.historical_baseline.distinct_taxa_count == 1
    # 4. "New"/recurring state is recomputed correctly for the corrected label.
    assert {e.label for e in after.new_taxa} == {"house_finch"}
    assert after.regular_taxa == []

    # 2. Old taxon history no longer treats the superseded identity as
    #    authoritative -- no stale aggregate survives.
    after_history_a = repository.wildlife_journal_history(
        "northern_cardinal", WildlifeJournalHistoryRequest(), now=NOW
    )
    assert after_history_a is not None
    assert after_history_a.observation_count == 0
    assert after_history_a.place_context is None
    assert after_history_a.historical_status is None

    # 3. New taxon history reflects the correction.
    after_history_b = repository.wildlife_journal_history(
        "house_finch", WildlifeJournalHistoryRequest(), now=NOW
    )
    assert after_history_b is not None
    assert after_history_b.observation_count == 1
    assert after_history_b.place_context is not None
    assert after_history_b.place_context.observed_at == corrected_at
    assert after_history_b.historical_status == "new"

    # Same proof again through the real HTTP surface, not just the
    # repository method directly.
    client = LegacyAuthenticatedSyncTestClient(app)
    api_body = client.get("/api/place/biodiversity-summary").json()
    assert [entry["label"] for entry in api_body["taxa"]] == ["house_finch"]
    journal_a = client.get("/api/bird-log/journal/northern_cardinal").json()
    assert journal_a["observation_count"] == 0
    journal_b = client.get("/api/bird-log/journal/house_finch").json()
    assert journal_b["observation_count"] == 1
    assert journal_b["historical_status"] == "new"
