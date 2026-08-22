"""Tier 1 pure tests for Gate C -- Calm Daily Digest v1
(`mockingbird.analytics.daily_digest`). No database, no FastAPI, no
repository -- exactly the same posture as tests/test_place_activity_report.py
and tests/test_representative_evidence.py. See docs/place-activity-report-
contract.md for the underlying truth-precedence facts this module composes.
"""

from __future__ import annotations

from datetime import UTC, datetime

from mockingbird.analytics.daily_digest import (
    DigestTaxonFact,
    compute_daily_digest,
)

_PERIOD_START = datetime(2026, 8, 21, 0, 0, tzinfo=UTC)
_PERIOD_END = datetime(2026, 8, 22, 0, 0, tzinfo=UTC)
_GENERATED_AT = datetime(2026, 8, 21, 20, 0, tzinfo=UTC)


def _taxon(
    label: str,
    display_name: str,
    *,
    category: str = "bird",
    is_species: bool = True,
    confirmed_visit_count: int = 1,
    provisional_visit_count: int = 0,
    first_activity_at: datetime = _PERIOD_START,
    last_activity_at: datetime = _PERIOD_START,
    historical_status: str | None = None,
    change_status: str | None = None,
    most_active_zone_name: str | None = None,
    most_active_hour: int | None = None,
    has_representative_evidence: bool = False,
    has_strong_representative_evidence: bool = False,
) -> DigestTaxonFact:
    return DigestTaxonFact(
        label=label,
        display_name=display_name,
        category=category,
        is_species=is_species,
        confirmed_visit_count=confirmed_visit_count,
        provisional_visit_count=provisional_visit_count,
        first_activity_at=first_activity_at,
        last_activity_at=last_activity_at,
        historical_status=historical_status,
        change_status=change_status,
        most_active_zone_name=most_active_zone_name,
        most_active_hour=most_active_hour,
        has_representative_evidence=has_representative_evidence,
        has_strong_representative_evidence=has_strong_representative_evidence,
    )


def _digest(taxa, **overrides):
    params = dict(
        period_start_at=_PERIOD_START,
        period_end_at=_PERIOD_END,
        generated_at=_GENERATED_AT,
        maturity="usable",
        confirmed_wildlife_visit_count=sum(t.confirmed_visit_count for t in taxa),
        provisional_wildlife_visit_count=0,
        unresolved_visit_count=0,
        first_activity_at=_PERIOD_START,
        last_activity_at=_PERIOD_START,
    )
    params.update(overrides)
    return compute_daily_digest(taxa, **params)


# -- I.13.1: first confirmed record outranks ordinary high-count Regular ----


def test_first_confirmed_record_outranks_high_count_regular() -> None:
    common_regular = _taxon(
        "northern_cardinal", "Northern Cardinal", confirmed_visit_count=40, historical_status="regular"
    )
    first_record = _taxon(
        "painted_bunting", "Painted Bunting", confirmed_visit_count=1, historical_status="first_record"
    )
    digest = _digest([common_regular, first_record])
    assert [h.label for h in digest.primary_highlights] == ["painted_bunting", "northern_cardinal"]
    assert digest.primary_highlights[0].reason == "first_confirmed_record"


# -- I.13.2: established New wording correct ---------------------------------


def test_established_new_wording() -> None:
    taxon = _taxon("blue_jay", "Blue Jay", historical_status="new")
    digest = _digest([taxon])
    assert digest.primary_highlights[0].historical_note == "New to your reviewed history"
    assert digest.primary_highlights[0].reason == "first_confirmed_record"


# -- I.13.3: immature baseline does not say New -------------------------------


def test_immature_baseline_first_record_wording() -> None:
    taxon = _taxon("blue_jay", "Blue Jay", historical_status="first_record")
    digest = _digest([taxon])
    note = digest.primary_highlights[0].historical_note
    assert note == "First confirmed record so far"
    assert note != "New to your reviewed history"


# -- I.13.4: meaningful higher/lower state reused correctly ------------------


def test_higher_and_lower_change_wording() -> None:
    higher = _taxon("house_finch", "House Finch", change_status="higher_recent_presence")
    lower = _taxon("mourning_dove", "Mourning Dove", change_status="lower_recent_presence")
    digest = _digest([higher, lower])
    notes = {h.label: h.change_note for h in digest.primary_highlights}
    assert notes["house_finch"] == "Recorded more often recently"
    assert notes["mourning_dove"] == "Recorded less often recently"


def test_no_supported_change_has_no_change_note() -> None:
    taxon = _taxon("house_finch", "House Finch", change_status="no_supported_change")
    digest = _digest([taxon])
    assert digest.primary_highlights[0].change_note is None


# -- I.13.5: immature baseline gets one calm baseline-building message ------


def test_building_baseline_place_change_note() -> None:
    taxon = _taxon("blue_jay", "Blue Jay")
    digest = _digest([taxon], place_change_status="building_baseline")
    assert digest.place_change_note == "MockingBird is still building a baseline for this Place."


def test_no_supported_change_place_note_is_none() -> None:
    taxon = _taxon("blue_jay", "Blue Jay")
    digest = _digest([taxon], place_change_status="no_supported_change")
    assert digest.place_change_note is None


# -- I.13.6 / I.13.7: Zone/time pattern presence and absence -----------------


def test_pattern_note_without_zone() -> None:
    taxon = _taxon("blue_jay", "Blue Jay", most_active_hour=7)
    digest = _digest([taxon])
    assert digest.primary_highlights[0].pattern_note == "Most active 7–8 AM"


def test_pattern_note_with_zone_and_hour() -> None:
    taxon = _taxon("blue_jay", "Blue Jay", most_active_zone_name="Feeder", most_active_hour=7)
    digest = _digest([taxon])
    assert digest.primary_highlights[0].pattern_note == "Feeder · 7–8 AM"


def test_pattern_note_zone_only() -> None:
    taxon = _taxon("blue_jay", "Blue Jay", most_active_zone_name="Feeder")
    digest = _digest([taxon])
    assert digest.primary_highlights[0].pattern_note == "Mostly recorded at Feeder"


# -- I.13.8: low-support pattern omitted -------------------------------------


def test_pattern_note_omitted_when_upstream_withholds_support() -> None:
    # The minimum-support floor (place_activity_report.
    # MIN_REVIEWED_VISITS_FOR_MOST_ACTIVE_PATTERN) is enforced upstream; the
    # digest only ever sees `None`/`None` once that floor is not met, and
    # must not manufacture a pattern from that absence.
    taxon = _taxon("blue_jay", "Blue Jay", most_active_zone_name=None, most_active_hour=None)
    digest = _digest([taxon])
    assert digest.primary_highlights[0].pattern_note is None


# -- I.13.9 / I.13.10: representative evidence presence/absence -------------


def test_highlight_carries_representative_evidence_flag() -> None:
    taxon = _taxon("blue_jay", "Blue Jay", has_representative_evidence=True)
    digest = _digest([taxon])
    assert digest.primary_highlights[0].has_representative_evidence is True


def test_highlight_without_representative_evidence_still_produced() -> None:
    taxon = _taxon("blue_jay", "Blue Jay", has_representative_evidence=False)
    digest = _digest([taxon])
    assert len(digest.primary_highlights) == 1
    assert digest.primary_highlights[0].has_representative_evidence is False


def test_strong_representative_evidence_ranks_above_plain_confirmed_activity() -> None:
    plain = _taxon("mourning_dove", "Mourning Dove", confirmed_visit_count=9)
    noteworthy = _taxon(
        "pileated_woodpecker",
        "Pileated Woodpecker",
        confirmed_visit_count=1,
        has_representative_evidence=True,
        has_strong_representative_evidence=True,
    )
    digest = _digest([plain, noteworthy])
    assert digest.primary_highlights[0].label == "pileated_woodpecker"
    assert digest.primary_highlights[0].reason == "strong_representative_evidence"


# -- I.13.11: usable coverage + zero wildlife vs. no monitoring -------------


def test_usable_zero_activity_distinct_from_no_monitoring() -> None:
    usable_empty = _digest(
        [],
        maturity="usable",
        confirmed_wildlife_visit_count=0,
        provisional_wildlife_visit_count=0,
        unresolved_visit_count=0,
        first_activity_at=None,
        last_activity_at=None,
    )
    no_data = _digest(
        [],
        maturity="no_data",
        confirmed_wildlife_visit_count=0,
        provisional_wildlife_visit_count=0,
        unresolved_visit_count=0,
        first_activity_at=None,
        last_activity_at=None,
    )
    assert usable_empty.coverage.state == "no_confirmed_activity"
    assert usable_empty.coverage.message == "No reviewed wildlife records yet today."
    assert no_data.coverage.state == "no_monitoring"
    assert no_data.coverage.message != usable_empty.coverage.message


# -- I.13.12 / I.13.13: unresolved/provisional activity never named ---------


def test_unresolved_activity_never_named() -> None:
    digest = _digest(
        [],
        confirmed_wildlife_visit_count=0,
        provisional_wildlife_visit_count=0,
        unresolved_visit_count=3,
    )
    assert digest.primary_highlights == []
    assert digest.other_activity.unresolved_visit_count == 3
    assert digest.coverage.state == "unresolved_activity_only"


def test_provisional_only_taxon_excluded_from_highlights() -> None:
    provisional_only = _taxon("cedar_waxwing", "Cedar Waxwing", confirmed_visit_count=0, provisional_visit_count=5)
    digest = _digest(
        [provisional_only],
        confirmed_wildlife_visit_count=0,
        provisional_wildlife_visit_count=5,
        unresolved_visit_count=0,
    )
    assert digest.primary_highlights == []
    assert digest.other_species == []
    assert digest.other_activity.provisional_visit_count == 5
    assert digest.coverage.state == "unresolved_activity_only"


# -- I.13.14: corrected review changes output --------------------------------


def test_correction_that_zeroes_confirmed_count_removes_the_highlight() -> None:
    before_correction = _taxon("blue_jay", "Blue Jay", confirmed_visit_count=1)
    digest_before = _digest([before_correction])
    assert [h.label for h in digest_before.primary_highlights] == ["blue_jay"]

    # A reviewer corrects the label away from Blue Jay (e.g. to a
    # false-positive/different species) -- the taxon's own confirmed count
    # for this label drops to zero, and the digest is a pure function of
    # current facts, so it must stop naming it on the very next call.
    after_correction = _taxon("blue_jay", "Blue Jay", confirmed_visit_count=0)
    digest_after = _digest(
        [after_correction],
        confirmed_wildlife_visit_count=0,
        provisional_wildlife_visit_count=0,
        unresolved_visit_count=0,
    )
    assert digest_after.primary_highlights == []
    assert digest_after.other_species == []


# -- I.13.15: multi-subject Event can produce independent highlights --------


def test_multi_subject_event_produces_independent_highlights() -> None:
    # Two distinct taxa confirmed from sibling Visits under one Event,
    # sharing the same activity timestamp -- the digest has no Event/
    # Visit concept of its own, so this is simply two independent
    # DigestTaxonFact entries, each ranked on its own merits.
    cardinal = _taxon(
        "northern_cardinal", "Northern Cardinal", first_activity_at=_PERIOD_START, last_activity_at=_PERIOD_START
    )
    finch = _taxon("house_finch", "House Finch", first_activity_at=_PERIOD_START, last_activity_at=_PERIOD_START)
    digest = _digest([cardinal, finch])
    labels = {h.label for h in digest.primary_highlights}
    assert labels == {"northern_cardinal", "house_finch"}


# -- I.13.16: highlight count bounded -----------------------------------------


def test_highlight_count_bounded_to_five() -> None:
    taxa = [_taxon(f"species_{i}", f"Species {i}", confirmed_visit_count=10 - i) for i in range(8)]
    digest = _digest(taxa)
    assert len(digest.primary_highlights) == 5
    assert len(digest.other_species) == 3


# -- I.13.17: deterministic ordering ------------------------------------------


def test_ordering_is_deterministic_and_stable_on_repeated_calls() -> None:
    taxa = [
        _taxon("house_finch", "House Finch", confirmed_visit_count=6),
        _taxon("mourning_dove", "Mourning Dove", confirmed_visit_count=6),
        _taxon("blue_jay", "Blue Jay", confirmed_visit_count=9),
    ]
    first = _digest(list(taxa))
    second = _digest(list(reversed(taxa)))
    assert [h.label for h in first.primary_highlights] == [h.label for h in second.primary_highlights]
    # Equal confirmed counts (House Finch/Mourning Dove) break the tie by
    # display name, never input order.
    assert [h.label for h in first.primary_highlights] == ["blue_jay", "house_finch", "mourning_dove"]


# -- I.13.18: sparse monitoring suppresses overconfident language -----------


def test_sparse_monitoring_message_even_with_confirmed_activity() -> None:
    taxon = _taxon("blue_jay", "Blue Jay", confirmed_visit_count=2)
    digest = _digest([taxon], maturity="sparse", confirmed_wildlife_visit_count=2)
    assert digest.coverage.state == "sparse_monitoring"
    assert digest.coverage.message == "Monitoring coverage is still limited today."
    # The real, reviewed highlight still appears -- sparse coverage caveats
    # the day's confidence, it does not hide genuine reviewed truth.
    assert [h.label for h in digest.primary_highlights] == ["blue_jay"]


def test_no_monitoring_message_even_if_taxa_somehow_supplied() -> None:
    taxon = _taxon("blue_jay", "Blue Jay", confirmed_visit_count=1)
    digest = _digest([taxon], maturity="no_data", confirmed_wildlife_visit_count=1)
    assert digest.coverage.state == "no_monitoring"
    assert digest.coverage.message == "MockingBird hasn't started monitoring here yet today."


# -- I.13.19: local-day boundary ----------------------------------------------


def test_period_boundaries_pass_through_unchanged() -> None:
    start = datetime(2026, 3, 8, 0, 0, tzinfo=UTC)  # a real US DST spring-forward local day
    end = datetime(2026, 3, 9, 0, 0, tzinfo=UTC)
    digest = _digest([], period_start_at=start, period_end_at=end, confirmed_wildlife_visit_count=0)
    assert digest.period_start_at == start
    assert digest.period_end_at == end


# -- I.13.20: DST-affected hour formatting stays correct ---------------------


def test_hour_range_formatting_is_dst_agnostic() -> None:
    # `most_active_hour` is already a resolved local wall-clock hour by the
    # time it reaches this module (see place_activity_report.compute_taxon_
    # place_patterns); formatting it is pure integer arithmetic with no
    # timezone of its own, so the ambiguous (fall-back) and skipped
    # (spring-forward) local hours format identically to any other hour --
    # there is no separate DST branch to silently get wrong.
    one_am = _taxon("blue_jay", "Blue Jay", most_active_hour=1)
    two_am = _taxon("house_finch", "House Finch", most_active_hour=2)
    digest = _digest([one_am, two_am])
    notes = {h.label: h.pattern_note for h in digest.primary_highlights}
    assert notes["blue_jay"] == "Most active 1–2 AM"
    assert notes["house_finch"] == "Most active 2–3 AM"


# -- Additional coverage of the module's own branches ------------------------


def test_regular_species_gets_regular_here_wording() -> None:
    taxon = _taxon("house_finch", "House Finch", historical_status="regular")
    digest = _digest([taxon])
    assert digest.primary_highlights[0].historical_note == "Regular here"
    assert digest.primary_highlights[0].reason == "regular_activity"


def test_seen_before_has_no_historical_note() -> None:
    taxon = _taxon("house_finch", "House Finch", historical_status="seen_before")
    digest = _digest([taxon])
    assert digest.primary_highlights[0].historical_note is None
    assert digest.primary_highlights[0].reason == "confirmed_activity"


def test_empty_input_produces_empty_digest() -> None:
    digest = _digest([], confirmed_wildlife_visit_count=0)
    assert digest.primary_highlights == []
    assert digest.other_species == []
    assert digest.other_activity.total_visit_count == 0


def test_other_species_sorted_alphabetically_not_by_rank() -> None:
    # Five higher-count taxa fill the primary highlights; the two lowest-
    # count taxa fall to `other_species`, in *rank* order (Zebra Finch,
    # count 5, before American Robin, count 4) unless this function
    # re-sorts alphabetically for the compact "Also recorded" readout.
    top_five = [_taxon(f"species_{i}", f"Species {i}", confirmed_visit_count=20 - i) for i in range(5)]
    remaining = [
        _taxon("zebra_finch", "Zebra Finch", confirmed_visit_count=5),
        _taxon("american_robin", "American Robin", confirmed_visit_count=4),
    ]
    digest = _digest(top_five + remaining)
    assert [entry.display_name for entry in digest.other_species] == ["American Robin", "Zebra Finch"]


def test_confirmed_wildlife_state_has_empty_message() -> None:
    taxon = _taxon("blue_jay", "Blue Jay")
    digest = _digest([taxon])
    assert digest.coverage.state == "confirmed_wildlife"
    assert digest.coverage.message == ""
