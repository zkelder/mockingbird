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

# Anchored to the real wall clock, not a fixed calendar date. `place_
# biodiversity_summary`/`wildlife_journal_history` are deliberately "live
# view" endpoints (see their own docstrings and docs/biodiversity-place-
# intelligence-v1-contract.md's "a live view, not a fixed report period") --
# `historical_status`/`new_taxa` reads "new" only while the confirmation's
# own timestamp still falls on the *current* Place-local day, and neither
# HTTP route accepts a way to inject a test clock (unlike `place_activity_
# report`'s explicit `start_at`/`end_at`, used by the sibling `test_
# historical_baseline_repository.py::test_api_round_trip_...` test for the
# identical "new" assertion). A fixed past constant here made every
# HTTP-route assertion of "new"/"seen_before" correct on only the one real
# calendar day matching that constant, and silently wrong (a genuine
# first-ever confirmation misread as "seen_before") every day after --
# reproduced, and independently re-confirmed pre-existing across nine-plus
# prior full-Core checkpoints in docs/release-execution-state.md, never
# before given its own dedicated fix. Pinned to noon UTC (not the literal
# instant) so it stays safely inside one local calendar day regardless of
# host timezone, preserving the original constant's own "stay exact"
# discipline while tracking the day the suite actually runs on.
NOW = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0)

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


def test_subsequent_confirmation_of_an_already_confirmed_species_reads_seen_before(
    repository: ProductRepository,
) -> None:
    """Historical Species-Status ("New" vs. "Seen Before") Correctness v1
    -- the required "subsequent occurrence" case (see docs/historical-
    species-status-new-seen-before-correctness-v1-report.md): a species
    confirmed once already, then confirmed again later, must read
    "seen_before" (not "new"/"first_record") for the later confirmation --
    proven through both live-view endpoints and the real HTTP surface, the
    same pair the two reproduced defects this milestone closes were found
    through."""

    _establish_baseline(repository)
    _add_visit(repository, visit_id="cardinal-first", at=NOW - timedelta(days=2))
    _confirm(repository, visit_id="cardinal-first", label="northern_cardinal")
    _add_visit(repository, visit_id="cardinal-second", at=NOW - timedelta(hours=1))
    _confirm(repository, visit_id="cardinal-second", label="northern_cardinal")

    summary = repository.place_biodiversity_summary(now=NOW)

    [entry] = [e for e in summary.taxa if e.label == "northern_cardinal"]
    assert entry.historical_status.status == "seen_before"
    assert {e.label for e in summary.new_taxa} == set()
    # Only one usable day confirmed (2 days ago) -- not yet enough distinct
    # usable days to be "regular" either.
    assert {e.label for e in summary.regular_taxa} == set()

    history = repository.wildlife_journal_history(
        "northern_cardinal", WildlifeJournalHistoryRequest(), now=NOW
    )
    assert history is not None
    assert history.historical_status == "seen_before"

    # Same proof again through the real HTTP surface, not just the
    # repository methods directly -- both product endpoints must agree.
    client = LegacyAuthenticatedSyncTestClient(app)
    api_body = client.get("/api/place/biodiversity-summary").json()
    [api_entry] = [t for t in api_body["taxa"] if t["label"] == "northern_cardinal"]
    assert api_entry["historical_status"]["status"] == "seen_before"
    assert "northern_cardinal" not in [t["label"] for t in api_body["new_taxa"]]
    api_history = client.get("/api/bird-log/journal/northern_cardinal").json()
    assert api_history["historical_status"] == "seen_before"


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


# 7b. Human correction to a species this Place has already seen before -----
#
# Historical Species-Status ("New" vs. "Seen Before") Correctness v1's
# required "correction to previously-seen species" case: the mandatory
# correction test above proves a correction TO a genuinely new species; this
# proves the opposite direction -- a correction to a species that already
# has a real, earlier confirmed record must read "seen_before", not "new"
# just because the row itself was recently (re-)reviewed.


def test_human_correction_to_a_previously_confirmed_species_reads_seen_before(
    repository: ProductRepository,
) -> None:
    _establish_baseline(repository)
    # House Finch already has a genuine, earlier confirmed record.
    _add_visit(repository, visit_id="finch-established", at=NOW - timedelta(days=2))
    _confirm(repository, visit_id="finch-established", label="house_finch")

    # A second, later Visit is initially reviewed as a Northern Cardinal...
    corrected_at = NOW - timedelta(hours=1)
    _add_visit(repository, visit_id="mystery-2", at=corrected_at)
    _confirm(repository, visit_id="mystery-2", label="northern_cardinal")

    # ...then corrected: it was actually another House Finch -- a species
    # this Place has already seen before, not a fresh debut.
    _revise(repository, visit_id="mystery-2", label="house_finch")

    after = repository.place_biodiversity_summary(now=NOW)
    [entry] = [e for e in after.taxa if e.label == "house_finch"]
    assert entry.historical_status.status == "seen_before"
    assert {e.label for e in after.new_taxa} == set()

    # Two real, distinct House Finch records now exist -- correcting one
    # Visit must not duplicate or lose either.
    history = repository.wildlife_journal_history(
        "house_finch", WildlifeJournalHistoryRequest(), now=NOW
    )
    assert history is not None
    assert history.observation_count == 2
    assert history.historical_status == "seen_before"

    # No stale Northern Cardinal identity survives the correction.
    stale_history = repository.wildlife_journal_history(
        "northern_cardinal", WildlifeJournalHistoryRequest(), now=NOW
    )
    assert stale_history is not None
    assert stale_history.observation_count == 0
    assert stale_history.historical_status is None

    # Same proof again through the real HTTP surface -- both product
    # endpoints must agree.
    client = LegacyAuthenticatedSyncTestClient(app)
    api_body = client.get("/api/place/biodiversity-summary").json()
    [api_entry] = [t for t in api_body["taxa"] if t["label"] == "house_finch"]
    assert api_entry["historical_status"]["status"] == "seen_before"
    api_history = client.get("/api/bird-log/journal/house_finch").json()
    assert api_history["observation_count"] == 2
    assert api_history["historical_status"] == "seen_before"


# 8. Broader Wildlife Maturity v1 -------------------------------------------
#
# Same mandatory correction property as section 7, and the same Journey 8
# "Place memory" acceptance, proven for the milestone's representative
# non-bird cohort rather than a second bird pair -- see
# docs/broader-wildlife-maturity-v1-contract.md. Reuses the identical real
# write paths (`create_review_label`/`revise_visit_review`); no separate
# "mammal" code path exists to test.


def test_human_correction_updates_place_biodiversity_intelligence_correctly_for_a_non_bird_taxon(
    repository: ProductRepository,
) -> None:
    """Journey 4: a provisional mammal identity, corrected to a different
    taxon, updates every downstream authoritative surface -- the identical
    property already proven for two bird species above, proven again for
    two of this milestone's newly-seeded mammal taxa (docs/broader-
    wildlife-maturity-v1-contract.md P0 #2)."""

    _establish_baseline(repository)
    corrected_at = NOW - timedelta(hours=1)
    _add_visit(repository, visit_id="mammal-mystery-1", at=corrected_at)
    _confirm(repository, visit_id="mammal-mystery-1", label="squirrel")

    before = repository.place_biodiversity_summary(now=NOW)
    assert "squirrel" in _taxa_labels(before)

    # A human reviews the correction: it was actually a raccoon, not a squirrel.
    _revise(repository, visit_id="mammal-mystery-1", label="raccoon")

    after = repository.place_biodiversity_summary(now=NOW)
    assert _taxa_labels(after) == {"raccoon"}
    assert after.historical_baseline.distinct_taxa_count == 1
    assert {e.label for e in after.new_taxa} == {"raccoon"}

    # Old taxon identity no longer treats itself as authoritative -- no
    # stale aggregate survives the correction.
    stale_history = repository.wildlife_journal_history(
        "squirrel", WildlifeJournalHistoryRequest(), now=NOW
    )
    assert stale_history is not None
    assert stale_history.observation_count == 0

    corrected_history = repository.wildlife_journal_history(
        "raccoon", WildlifeJournalHistoryRequest(), now=NOW
    )
    assert corrected_history is not None
    assert corrected_history.observation_count == 1
    assert corrected_history.historical_status == "new"

    # Same proof again through the real HTTP surface.
    client = LegacyAuthenticatedSyncTestClient(app)
    api_body = client.get("/api/place/biodiversity-summary").json()
    assert [entry["label"] for entry in api_body["taxa"]] == ["raccoon"]


def test_representative_wildlife_cohort_is_remembered_and_a_pet_is_honestly_excluded(
    repository: ProductRepository,
) -> None:
    """Journey 8 (Place memory) across this milestone's representative
    cohort in one Place: squirrel, deer, raccoon, opossum, fox, and rabbit
    (all newly-seeded kind-level mammal taxa) are all remembered correctly
    alongside a bird (regression control) -- and a confirmed cat is
    honestly, deliberately excluded from wildlife biodiversity, not a bug
    (`LabelCategory.pet` is not wildlife by product design -- see the
    contract doc's "Cat is a deliberate case, not a defect")."""

    _establish_baseline(repository)
    cohort = ("squirrel", "deer", "raccoon", "opossum", "fox", "rabbit", "northern_cardinal")
    for label in cohort:
        visit_id = f"cohort-{label}"
        _add_visit(repository, visit_id=visit_id, at=NOW - timedelta(hours=1))
        _confirm(repository, visit_id=visit_id, label=label)
    _add_visit(repository, visit_id="cohort-cat", at=NOW - timedelta(hours=1))
    _confirm(repository, visit_id="cohort-cat", label="cat")

    summary = repository.place_biodiversity_summary(now=NOW)

    assert _taxa_labels(summary) == set(cohort)
    assert "cat" not in _taxa_labels(summary)
    assert summary.historical_baseline.distinct_taxa_count == len(cohort)
    # distinct_species_count is species-level only (see the contract doc's
    # identification-maturity section) -- every cohort mammal here is
    # kind-level (is_species=False), so only the bird raises it.
    assert summary.distinct_species_count == 1
    for label in cohort:
        entry = next(e for e in summary.taxa if e.label == label)
        assert entry.historical_status.status in ("new", "first_record")

    # Same proof again through the real HTTP surface -- and confirms a
    # confirmed cat Visit is real, queryable product data (just not
    # wildlife), not silently dropped or erroring anywhere in the pipeline.
    client = LegacyAuthenticatedSyncTestClient(app)
    api_labels = {entry["label"] for entry in client.get("/api/place/biodiversity-summary").json()["taxa"]}
    assert api_labels == set(cohort)
    cat_visit = client.get("/api/visits/cohort-cat").json()
    assert cat_visit["reviewed_label"] == "cat"


def test_human_overrides_a_wrong_machine_species_suggestion_with_a_correct_mammal(
    repository: ProductRepository,
) -> None:
    """Phase 8 mandatory journey 2 ("classifier proposes squirrel, human
    corrects rabbit"), made honest: BioCLIP cannot actually propose
    "squirrel" -- its candidate pack is closed to bird species only (see
    docs/broader-wildlife-maturity-v1-contract.md "Identification
    maturity") -- so the real, achievable version of this journey is a
    provisional *bird* suggestion (what BioCLIP would actually produce on
    any admitted animal Visit today) corrected by a human to the true,
    non-bird taxon. Proves the correction is fully authoritative: the
    machine's suggestion never contaminates biodiversity truth, whether it
    arrived before or was never even looked at."""

    _establish_baseline(repository)
    _add_visit(repository, visit_id="wrongly-suggested-1", at=NOW - timedelta(hours=1))
    _suggest(repository, visit_id="wrongly-suggested-1", label="house_finch")

    before = repository.place_biodiversity_summary(now=NOW)
    assert before.taxa == []
    assert {e.label for e in before.provisional_taxa} == {"house_finch"}

    _confirm(repository, visit_id="wrongly-suggested-1", label="rabbit")

    after = repository.place_biodiversity_summary(now=NOW)
    assert _taxa_labels(after) == {"rabbit"}
    assert "house_finch" not in _taxa_labels(after)
    house_finch_history = repository.wildlife_journal_history(
        "house_finch", WildlifeJournalHistoryRequest(), now=NOW
    )
    assert house_finch_history is not None
    assert house_finch_history.observation_count == 0


def test_human_selects_unknown_animal_over_a_wrong_machine_species_suggestion(
    repository: ProductRepository,
) -> None:
    """Phase 8 mandatory journey 3 ("classifier proposes a species but
    reviewer selects unknown mammal/broader taxon"): a reviewer is not
    forced to pick a specific taxon just because the machine suggested
    one -- "unknown_animal" is a fully legitimate, authoritative correction
    (see the contract doc's TAXON TRUTH section), counted honestly as real
    wildlife activity without fabricating a species (mirrors
    tests/test_place_activity_report_repository.py::
    test_confirmed_animal_with_unresolved_species_counts_without_
    fabricating_a_taxon, proven here through the Biodiversity surface and
    starting from a real wrong machine suggestion instead of no suggestion
    at all)."""

    _establish_baseline(repository)
    _add_visit(repository, visit_id="wrongly-suggested-2", at=NOW - timedelta(hours=1))
    _suggest(repository, visit_id="wrongly-suggested-2", label="house_finch")

    _confirm(repository, visit_id="wrongly-suggested-2", label="unknown_animal")

    after = repository.place_biodiversity_summary(now=NOW)
    # unknown_animal is confirmed-but-species-unresolved, not a taxon in its
    # own right -- correctly absent from the taxa roster (see
    # wildlife_taxonomy.py's own documented boundary), and never silently
    # replaced by the machine's wrong house_finch guess.
    assert after.taxa == []
    assert "house_finch" not in {e.label for e in after.provisional_taxa}
