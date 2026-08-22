"""Gate C -- Calm Daily Digest v1: pure, deterministic composition of an
existing Place Activity Report's own already-resolved facts into one calm
"what happened here today" recap (see docs/place-activity-report-contract.md
and the "Calm-observatory notifications" section of product-doctrine.md).

This module creates no new observational authority. It never queries a
database, never decodes an image, never calls a model or a language model,
and never persists prose -- it only ranks and captions facts every sibling
module in this package (`place_activity_report`, `historical_baseline`,
`place_change_summary`, `representative_evidence`) has already computed,
exactly the same "the repository resolves truth and facts, this module only
composes them" boundary those modules already establish. A repository-side
adapter (`mockingbird.analytics.place_activity_report_adapter`) is the only
place that touches the database or Pydantic; it builds `DigestTaxonFact`
from the exact same per-taxon facts (`TaxonReportEntry`, `SpeciesHistorical
Status`, `TaxonChangeStatus`, `TaxonPlacePattern`, `RepresentativeEvidence`)
it already assembles into `PlaceActivityReportTaxonEntry` for the plain
report -- never a second, independently-derived set of facts.

## Truth boundary (do not weaken this)

Every highlight and every name in `other_species` requires
`confirmed_visit_count > 0` -- an authority-eligible `ReviewLabel`, per
`place_activity_report._classify`'s truth precedence. A taxon backed solely
by a provisional `SpeciesSuggestion` can never appear by name here; it is
folded, anonymously, into `DailyDigest.other_activity` alongside genuinely
unresolved wildlife. This mirrors `historical_baseline`/`place_change_
summary`'s identical truth contract and product-doctrine.md's truth
boundary: human correction is the only thing that creates reviewed truth.

## Ranking (Gate C milestone brief, "I.4 Calm highlight priority")

A bounded, deterministic priority -- never model confidence, never raw
Visit count alone -- so a single common 40-Visit species can never bury a
genuine first record:

1. a first confirmed record (`historical_status` is `"new"` or
   `"first_record"` -- the same underlying fact, maturity-appropriate
   wording; see `historical_baseline.compute_species_historical_statuses`);
2. a species with a *supported* meaningful change (`change_status` is
   `"higher_recent_presence"` or `"lower_recent_presence"` -- see
   `place_change_summary`'s own strict validity gate, already enforced
   upstream);
3. a noteworthy species with strong (genuinely proven native-resolution)
   representative evidence;
4. a `"regular"` species with today's confirmed activity;
5. every other confirmed species, by today's confirmed activity.

Within a tier, ties break on confirmed Visit count (descending), then
display name, then label -- stable and fully reproducible, never database
retrieval order.

## Highlight bound

`MAX_PRIMARY_HIGHLIGHTS` keeps the digest a calm, bounded recap, never an
unbounded card wall (see "I.5 Highlight count" in the milestone brief).
Confirmed species beyond that bound are still named, compactly, in
`other_species` -- never hidden, just de-emphasized.

## Coverage semantics (see "I.10 Coverage semantics")

`_classify_coverage` distinguishes five states so a quiet or barely-
monitored day is never misread as "no wildlife visited": no monitoring at
all, sparse (real but insufficient) monitoring, useful monitoring with
zero wildlife activity of any kind, useful monitoring with only unresolved/
provisional activity, and useful monitoring with confirmed wildlife. The
first two states are keyed purely on `maturity` (see `place_activity_
report.compute_report_maturity`) -- never on how much wildlife happened to
be recorded -- exactly mirroring that function's own "coverage, never
activity count" discipline, so a sparse day never accidentally claims
"nothing happened" in the same breath as being too under-monitored to
support any conclusion at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Sequence

HistoricalStatusValue = Literal["new", "first_record", "regular", "seen_before"]
ChangeStatusValue = Literal[
    "insufficient_baseline",
    "insufficient_recent_coverage",
    "no_supported_change",
    "higher_recent_presence",
    "lower_recent_presence",
]
PlaceChangeStatusValue = Literal[
    "building_baseline",
    "insufficient_recent_coverage",
    "no_supported_change",
    "more_activity_recorded",
    "less_activity_recorded",
]
ReportMaturity = Literal["no_data", "sparse", "usable"]

HighlightReason = Literal[
    "first_confirmed_record",
    "meaningful_change",
    "strong_representative_evidence",
    "regular_activity",
    "confirmed_activity",
]

# Deliberately "approximately 3-5" per the milestone brief, resolved to one
# fixed bound: a calm recap needs a stable promise about how much it will
# ever show at once, not a number that quietly drifts with a busy day.
MAX_PRIMARY_HIGHLIGHTS = 5

# Fixed priority order -- see the module docstring's "Ranking" section. A
# tuple (not a dict) so `.index(...)` doubles as the numeric sort rank.
_TIER_ORDER: tuple[HighlightReason, ...] = (
    "first_confirmed_record",
    "meaningful_change",
    "strong_representative_evidence",
    "regular_activity",
    "confirmed_activity",
)

# I.6 "Historical wording" -- reused verbatim from the accepted Today badge
# copy (`historicalStatusBadge` in web/src/components/TodayReportPanel.tsx)
# so the same fact never reads two different ways on the same page.
# "seen_before" intentionally has no entry -- the calm, ordinary case gets
# no badge at all, matching that component's identical choice.
_HISTORICAL_NOTES: dict[HistoricalStatusValue, str] = {
    "new": "New to your reviewed history",
    "first_record": "First confirmed record so far",
    "regular": "Regular here",
}

# I.6 "Change" wording, as specified for this composed-prose surface (a full
# highlight sentence fragment, distinct from the terser existing Today pill
# text in web/src/utils.ts's `changeStatusBadge` -- same underlying fact,
# a fuller phrasing for a fuller sentence). Every other `ChangeStatusValue`
# (including "no_supported_change" and both "insufficient_*" values)
# intentionally has no entry: an unsupported or invalid comparison must
# never be presented as a change, per place_change_summary's own contract.
_CHANGE_NOTES: dict[ChangeStatusValue, str] = {
    "higher_recent_presence": "Recorded more often recently",
    "lower_recent_presence": "Recorded less often recently",
}

# I.11 "Developing installation" -- reused verbatim from the accepted
# Place-wide change message (`overallChangeMessage` in TodayReportPanel.tsx)
# so a first-day install gets exactly one calm, already-accepted baseline
# sentence rather than a new, separately-invented one.
_PLACE_CHANGE_NOTES: dict[PlaceChangeStatusValue, str] = {
    "building_baseline": "MockingBird is still building a baseline for this Place.",
    "insufficient_recent_coverage": "There wasn't enough recent monitoring to compare with history.",
    "more_activity_recorded": (
        "Wildlife activity was recorded on more monitored days recently than in the preceding weeks."
    ),
    "less_activity_recorded": (
        "Wildlife activity was recorded on fewer monitored days recently than in the preceding weeks."
    ),
}

# Reuses the exact 2-hour "enough monitoring to trust" boundary already
# established elsewhere (see place_activity_report.compute_report_maturity)
# only indirectly: this module never re-derives maturity itself, it only
# consumes the caller's already-computed `ReportMaturity`.


def _format_hour_range(hour: int) -> str:
    """One hour bucket as its own honest span (`7` -> "7-8 AM"), matching
    `formatHourRange` in web/src/components/TodayReportPanel.tsx exactly --
    never a fabricated multi-hour "peak window." Pure integer-hour
    formatting with no timezone of its own: `hour` must already be a
    resolved Place-local hour (0-23), computed upstream by `place_activity_
    report.compute_taxon_place_patterns` -- this function is agnostic to
    where that hour came from, including across a DST transition, since it
    never touches a `datetime` or a timezone itself.
    """

    def twelve_hour(value: int) -> tuple[str, str]:
        period = "AM" if value < 12 else "PM"
        twelve = 12 if value % 12 == 0 else value % 12
        return str(twelve), period

    start_label, start_period = twelve_hour(hour)
    end_label, end_period = twelve_hour((hour + 1) % 24)
    if start_period == end_period:
        return f"{start_label}–{end_label} {end_period}"
    return f"{start_label} {start_period}–{end_label} {end_period}"


def _pattern_note(zone_name: str | None, hour: int | None) -> str | None:
    """I.7 "Zone/time" -- reused verbatim from the accepted `speciesPlace
    Pattern` wording in TodayReportPanel.tsx (same reasoning as the
    historical/change notes above). `None`/`None` (no Zones configured, or
    below the minimum-support floor the caller already applied upstream --
    see `place_activity_report.MIN_REVIEWED_VISITS_FOR_MOST_ACTIVE_
    PATTERN`) is a completely valid, calm outcome: the digest omits this
    line rather than manufacturing a pattern from too little evidence."""

    if zone_name and hour is not None:
        return f"{zone_name} · {_format_hour_range(hour)}"
    if zone_name:
        return f"Mostly recorded at {zone_name}"
    if hour is not None:
        return f"Most active {_format_hour_range(hour)}"
    return None


@dataclass(frozen=True)
class DigestTaxonFact:
    """One taxon's already-resolved report facts -- exactly the subset of
    `PlaceActivityReportTaxonEntry` the digest ranks and captions by. Built
    by the repository-side adapter from the identical `TaxonReportEntry`/
    `SpeciesHistoricalStatus`/`TaxonChangeStatus`/`TaxonPlacePattern`/
    `RepresentativeEvidence` facts it already assembles for the plain
    report -- never re-derived, never independently queried.
    """

    label: str
    display_name: str
    category: str
    is_species: bool
    confirmed_visit_count: int
    provisional_visit_count: int
    first_activity_at: datetime
    last_activity_at: datetime
    # `None` under the identical truth-contract condition as `PlaceActivity
    # ReportTaxonEntry.historical_status`/`change_status`: this taxon was
    # never authoritatively confirmed (see the module docstring).
    historical_status: HistoricalStatusValue | None = None
    change_status: ChangeStatusValue | None = None
    most_active_zone_name: str | None = None
    most_active_hour: int | None = None
    # Whether this taxon has *any* representative evidence this period
    # (Representative Species Evidence v1) -- carried through only as a
    # presence flag; the digest never selects or ranks evidence itself
    # (see the module docstring). A highlight with `has_representative_
    # evidence=False` is still a completely normal highlight (see "I.8
    # Representative evidence" / "image absent still produces highlight").
    has_representative_evidence: bool = False
    # True only when that evidence's own persisted `GeometryAttribution.
    # resolution_provenance == "synchronized"` -- a genuinely proven,
    # separate higher-resolution capture (see docs/source-resolution-
    # multi-frame-species-evidence-contract.md), identical to `Evidence
    # CandidateFact.is_native_resolution`'s own definition in
    # `representative_evidence.py`. Used only for tier-3 ranking below;
    # never inferred from pixel counts or presence alone.
    has_strong_representative_evidence: bool = False


@dataclass(frozen=True)
class DigestSpeciesHighlight:
    """One named, reviewed-truth-backed species highlight."""

    label: str
    display_name: str
    category: str
    is_species: bool
    confirmed_visit_count: int
    provisional_visit_count: int
    first_activity_at: datetime
    last_activity_at: datetime
    # Which ranking tier earned this highlight its place -- a caller may
    # use this for grouping/analytics, but it is never itself rendered as
    # UI copy (the *_note fields below already carry the calm sentence).
    reason: HighlightReason
    historical_note: str | None
    change_note: str | None
    pattern_note: str | None
    has_representative_evidence: bool


@dataclass(frozen=True)
class DigestOtherSpecies:
    """One additional confirmed species beyond the primary highlight bound
    -- compact, name-only continuity (see "I.5 Highlight count"). Carries
    `category`/`is_species` (not just a bare name) so a caller can compute
    an honest confirmed-species headline count across the full confirmed
    set, not only the bounded primary highlights."""

    label: str
    display_name: str
    category: str
    is_species: bool
    confirmed_visit_count: int


@dataclass(frozen=True)
class DigestOtherActivity:
    """Wildlife activity that is not (yet) reviewed truth. Always reported
    as an anonymous count, never a species name -- see the module
    docstring's truth boundary and "I.3 Truth"."""

    provisional_visit_count: int
    unresolved_visit_count: int

    @property
    def total_visit_count(self) -> int:
        return self.provisional_visit_count + self.unresolved_visit_count


CoverageState = Literal[
    "no_monitoring",
    "sparse_monitoring",
    "no_confirmed_activity",
    "unresolved_activity_only",
    "confirmed_wildlife",
]


@dataclass(frozen=True)
class DigestCoverageSummary:
    """How much confidence today's digest may claim, and one calm sentence
    describing it -- see "I.10 Coverage semantics". `state` is purely a
    function of `maturity` plus honest activity counts, never a judgment
    about whether the *amount* of wildlife found is normal."""

    state: CoverageState
    maturity: ReportMaturity
    message: str


@dataclass(frozen=True)
class DailyDigest:
    """One calm "what happened here today" recap, composed entirely from
    an existing Place Activity Report's own already-resolved facts. See the
    module docstring; this creates no new observational authority."""

    period_start_at: datetime
    period_end_at: datetime
    generated_at: datetime
    coverage: DigestCoverageSummary
    primary_highlights: list[DigestSpeciesHighlight]
    other_species: list[DigestOtherSpecies]
    other_activity: DigestOtherActivity
    # The single Place-level baseline/change sentence, when supported --
    # see "I.11 Developing installation". `None` for the calm, ordinary
    # "no_supported_change" case (silence is the message, matching
    # `overallChangeMessage`'s identical choice in TodayReportPanel.tsx).
    place_change_note: str | None
    first_activity_at: datetime | None
    last_activity_at: datetime | None
    confirmed_wildlife_visit_count: int


def _highlight_reason(taxon: DigestTaxonFact) -> HighlightReason:
    if taxon.historical_status in ("new", "first_record"):
        return "first_confirmed_record"
    if taxon.change_status in ("higher_recent_presence", "lower_recent_presence"):
        return "meaningful_change"
    if taxon.has_strong_representative_evidence:
        return "strong_representative_evidence"
    if taxon.historical_status == "regular":
        return "regular_activity"
    return "confirmed_activity"


def _sort_key(taxon: DigestTaxonFact) -> tuple[int, int, str, str]:
    reason = _highlight_reason(taxon)
    return (
        _TIER_ORDER.index(reason),
        -taxon.confirmed_visit_count,
        taxon.display_name.lower(),
        taxon.label,
    )


def _compose_highlight(taxon: DigestTaxonFact) -> DigestSpeciesHighlight:
    historical_note = (
        _HISTORICAL_NOTES.get(taxon.historical_status) if taxon.historical_status else None
    )
    change_note = _CHANGE_NOTES.get(taxon.change_status) if taxon.change_status else None
    return DigestSpeciesHighlight(
        label=taxon.label,
        display_name=taxon.display_name,
        category=taxon.category,
        is_species=taxon.is_species,
        confirmed_visit_count=taxon.confirmed_visit_count,
        provisional_visit_count=taxon.provisional_visit_count,
        first_activity_at=taxon.first_activity_at,
        last_activity_at=taxon.last_activity_at,
        reason=_highlight_reason(taxon),
        historical_note=historical_note,
        change_note=change_note,
        pattern_note=_pattern_note(taxon.most_active_zone_name, taxon.most_active_hour),
        has_representative_evidence=taxon.has_representative_evidence,
    )


def _classify_coverage(
    *,
    maturity: ReportMaturity,
    confirmed_wildlife_visit_count: int,
    provisional_wildlife_visit_count: int,
    unresolved_visit_count: int,
) -> DigestCoverageSummary:
    # Low-maturity states are decided first and unconditionally on coverage
    # alone -- see the module docstring's "Coverage semantics" section and
    # "I.18 sparse monitoring suppresses overconfident language": even a
    # day with real confirmed activity gets the calm coverage-limited
    # sentence here, never a claim implying the whole day was observed.
    if maturity == "no_data":
        return DigestCoverageSummary(
            state="no_monitoring",
            maturity=maturity,
            message="MockingBird hasn't started monitoring here yet today.",
        )
    if maturity == "sparse":
        return DigestCoverageSummary(
            state="sparse_monitoring",
            maturity=maturity,
            message="Monitoring coverage is still limited today.",
        )

    if confirmed_wildlife_visit_count > 0:
        return DigestCoverageSummary(
            state="confirmed_wildlife",
            maturity=maturity,
            message="",
        )

    unresolved_activity = provisional_wildlife_visit_count + unresolved_visit_count
    if unresolved_activity > 0:
        return DigestCoverageSummary(
            state="unresolved_activity_only",
            maturity=maturity,
            message="Wildlife activity was recorded today, but nothing has been reviewed yet.",
        )

    # Useful monitoring, genuinely zero wildlife activity of any kind --
    # never "No wildlife visited," an observational statement about what
    # has been reviewed so far, not a conclusion about the whole day.
    return DigestCoverageSummary(
        state="no_confirmed_activity",
        maturity=maturity,
        message="No reviewed wildlife records yet today.",
    )


def compute_daily_digest(
    taxa: Sequence[DigestTaxonFact],
    *,
    period_start_at: datetime,
    period_end_at: datetime,
    generated_at: datetime,
    maturity: ReportMaturity,
    confirmed_wildlife_visit_count: int,
    provisional_wildlife_visit_count: int,
    unresolved_visit_count: int,
    first_activity_at: datetime | None,
    last_activity_at: datetime | None,
    place_change_status: PlaceChangeStatusValue | None = None,
) -> DailyDigest:
    """Compute one deterministic `DailyDigest` from already-resolved report
    facts. `taxa` may include provisional-only and unresolved-adjacent
    entries (any `PlaceActivityReportTaxonEntry`-shaped fact); only entries
    with `confirmed_visit_count > 0` are ever named -- see the module
    docstring's truth boundary. The five report-level count parameters
    should be the identical honest-accounting fields `PlaceActivityReport`
    itself already computes, not re-derived here.
    """

    confirmed = [taxon for taxon in taxa if taxon.confirmed_visit_count > 0]
    ranked = sorted(confirmed, key=_sort_key)

    primary = ranked[:MAX_PRIMARY_HIGHLIGHTS]
    remaining = ranked[MAX_PRIMARY_HIGHLIGHTS:]

    primary_highlights = [_compose_highlight(taxon) for taxon in primary]
    other_species = sorted(
        (
            DigestOtherSpecies(
                label=taxon.label,
                display_name=taxon.display_name,
                category=taxon.category,
                is_species=taxon.is_species,
                confirmed_visit_count=taxon.confirmed_visit_count,
            )
            for taxon in remaining
        ),
        key=lambda entry: (entry.display_name.lower(), entry.label),
    )

    coverage = _classify_coverage(
        maturity=maturity,
        confirmed_wildlife_visit_count=confirmed_wildlife_visit_count,
        provisional_wildlife_visit_count=provisional_wildlife_visit_count,
        unresolved_visit_count=unresolved_visit_count,
    )

    place_change_note = (
        _PLACE_CHANGE_NOTES.get(place_change_status) if place_change_status else None
    )

    return DailyDigest(
        period_start_at=period_start_at,
        period_end_at=period_end_at,
        generated_at=generated_at,
        coverage=coverage,
        primary_highlights=primary_highlights,
        other_species=other_species,
        other_activity=DigestOtherActivity(
            provisional_visit_count=provisional_wildlife_visit_count,
            unresolved_visit_count=unresolved_visit_count,
        ),
        place_change_note=place_change_note,
        first_activity_at=first_activity_at,
        last_activity_at=last_activity_at,
        confirmed_wildlife_visit_count=confirmed_wildlife_visit_count,
    )


__all__ = [
    "MAX_PRIMARY_HIGHLIGHTS",
    "ChangeStatusValue",
    "CoverageState",
    "DailyDigest",
    "DigestCoverageSummary",
    "DigestOtherActivity",
    "DigestOtherSpecies",
    "DigestSpeciesHighlight",
    "DigestTaxonFact",
    "HighlightReason",
    "HistoricalStatusValue",
    "PlaceChangeStatusValue",
    "ReportMaturity",
    "compute_daily_digest",
]
