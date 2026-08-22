"""Research/export truth-eligibility policy (see "Research-safe eligibility"
in docs/research-conservation-export-contract.md).

Consolidates every "may this record enter a research-safe / conservation
export, and as what" decision behind one function,
`evaluate_research_export_eligibility`, so no exporter (generic CSV/JSON,
Camtrap DP, conservation report) invents its own truth rule. Mirrors
`mockingbird.review_provenance` and `mockingbird.species.
identification_eligibility`'s own "one pure, dependency-free policy module"
convention: no SQLAlchemy/FastAPI import, importable from a pure analytics
module and from `product_repository` alike.

## The core distinction this module exists to prevent collapsing

A `SpeciesSuggestion` (or any provisional/unresolved evidence) must never
become a "trusted/research-safe named-species" export row merely because a
caller forgot to check review state first -- see product-doctrine.md's truth
boundary and "Research truth invariant" in the governing milestone brief.
This module never re-derives *what* the reviewed truth is (that remains
`ProductRepository._stream_visit_summary_from_models`/`_visit_review_outcome`,
exactly as `mockingbird.analytics.place_activity_report` already requires);
it only classifies an already-resolved fact and decides what it may become
in a research export.

## Required vs. recommended

`required_reasons` block eligibility outright (the record is not a trusted
research-safe row of the classification a caller might have hoped for).
`recommended_reasons` are disclosed completeness gaps on an otherwise-
eligible record -- a legacy free-text label with no resolvable scientific
name, an epoch-anchored timestamp placeholder, missing evidence media, or
unknown resolution provenance never blocks export; see "Research-safe
external sharing" in the governing milestone brief for why not every missing
optional field should.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mockingbird.wildlife_taxonomy import is_wildlife_category

# Mirrors `mockingbird.analytics.place_activity_report`'s own module-private
# constants -- kept here too since this module is deliberately independent
# (no import between the two pure packages).
_UNKNOWN_CATEGORY = "unknown"
_FALSE_POSITIVE_CATEGORY = "false_positive"

#: Bumped only when this module's own classification/eligibility *rule*
#: changes -- recorded on every research export manifest (see "Versioning /
#: reproducibility" in the governing milestone brief) so a downstream
#: researcher can tell whether two exports used the same policy.
RESEARCH_ELIGIBILITY_POLICY_VERSION = "research-eligibility-v1"

ResearchRecordClassification = Literal[
    "confirmed_taxon",
    "confirmed_unidentified_wildlife",
    "non_wildlife",
    "provisional_suggestion",
    "unresolved",
    "rejected",
    "superseded",
]

# Reason codes a caller (an eligibility report, an export skip-reasons
# summary, a "why can't I export this" UI hint) can act on directly.
REQUIRED_REASONS = frozenset(
    {
        "not_yet_reviewed",
        "provisional_suggestion_only",
        "rejected_false_positive",
        "not_wildlife",
        "taxon_unresolved",
        "no_authoritative_review",
        "structurally_superseded_visit",
        "superseded_by_later_review",
        "privacy_restricted",
    }
)
RECOMMENDED_REASONS = frozenset(
    {
        "taxon_identity_incomplete",
        "capture_timestamp_uncertain",
        "no_evidence_media",
        "resolution_provenance_unknown",
    }
)


@dataclass(frozen=True)
class ResearchExportEligibility:
    """One record's research-export verdict. Never a bare bool: a caller
    needs to know *what this record honestly is* (see
    `ResearchRecordClassification`) even when it is not eligible, so an
    export skip report can disclose "3 provisional suggestions excluded"
    rather than a single opaque "not eligible" count."""

    classification: ResearchRecordClassification
    eligible_as_named_taxon: bool
    eligible_as_unidentified_wildlife: bool
    required_reasons: tuple[str, ...] = ()
    recommended_reasons: tuple[str, ...] = ()

    @property
    def eligible(self) -> bool:
        """Eligible for *some* trusted research-safe export row (named taxon
        or honestly-unidentified wildlife) -- never a provisional,
        unresolved, rejected, non-wildlife, or superseded one."""

        return self.eligible_as_named_taxon or self.eligible_as_unidentified_wildlife


def evaluate_research_export_eligibility(
    *,
    review_status: str,
    is_authoritative_review: bool,
    is_structurally_superseded: bool,
    taxon_category: str | None,
    has_scientific_name: bool,
    has_suggestion: bool,
    capture_timestamp_known: bool = True,
    has_evidence_media: bool = True,
    resolution_provenance_known: bool = True,
    is_current_effective: bool = True,
    is_privacy_restricted: bool = False,
) -> ResearchExportEligibility:
    """Classify one already-resolved record and decide its research-export
    eligibility.

    All truth inputs must already come from the canonical resolver
    (`review_status`/`is_authoritative_review` from `ReviewStatus`/
    `mockingbird.review_provenance.is_authority_eligible`, `taxon_category`
    from a real `TaxonomyLabelModel` lookup on the *current* effective
    label) -- this function never queries anything itself.

    `is_current_effective` distinguishes the current-truth export table
    (always `True` -- `ProductRepository` reads `VisitModel.reviewed_label`,
    which a correction already keeps current, per `_create_review_label_in_
    session`) from an explicit audit/history export walking older rows
    (`False` for every non-current row in that history -- see "Corrections
    and supersession" in the governing milestone brief: an audit export may
    include a superseded historical decision, but never in the same table as
    current truth).
    """

    if is_structurally_superseded:
        return ResearchExportEligibility(
            "superseded", False, False, ("structurally_superseded_visit",), ()
        )
    if not is_current_effective:
        return ResearchExportEligibility(
            "superseded", False, False, ("superseded_by_later_review",), ()
        )

    recommended: list[str] = []
    required: list[str] = []

    if review_status == "rejected":
        classification: ResearchRecordClassification = "rejected"
        required.append("rejected_false_positive")
    elif review_status != "reviewed":
        if has_suggestion:
            classification = "provisional_suggestion"
            required.append("provisional_suggestion_only")
        else:
            classification = "unresolved"
            required.append("not_yet_reviewed")
    elif not is_authoritative_review:
        # A reviewed-looking row whose provenance is not authority-eligible
        # (an agent-diagnostic assessment, or omitted provenance) must never
        # read as confirmed truth -- mirrors `_visit_is_dataset_ready`'s own
        # defense-in-depth re-check.
        classification = "unresolved"
        required.append("no_authoritative_review")
    elif taxon_category is None:
        # Reviewed and authoritative, but the label did not resolve to any
        # taxonomy row (a legacy free-text correction) -- honestly
        # unresolved, never guessed at.
        classification = "unresolved"
        required.append("taxon_unresolved")
        recommended.append("taxon_identity_incomplete")
    elif taxon_category == _FALSE_POSITIVE_CATEGORY:
        classification = "rejected"
        required.append("rejected_false_positive")
    elif taxon_category == _UNKNOWN_CATEGORY:
        classification = "confirmed_unidentified_wildlife"
    elif is_wildlife_category(taxon_category):
        classification = "confirmed_taxon"
        if not has_scientific_name:
            recommended.append("taxon_identity_incomplete")
    else:
        # pet / person / vehicle / object: a real reviewed non-wildlife
        # record, never a false positive and never fabricated wildlife.
        classification = "non_wildlife"
        required.append("not_wildlife")

    if not capture_timestamp_known:
        recommended.append("capture_timestamp_uncertain")
    if not has_evidence_media:
        recommended.append("no_evidence_media")
    if not resolution_provenance_known:
        recommended.append("resolution_provenance_unknown")

    eligible_as_named = classification == "confirmed_taxon"
    eligible_as_unidentified = classification == "confirmed_unidentified_wildlife"

    if is_privacy_restricted and (eligible_as_named or eligible_as_unidentified):
        # Defense in depth (mirrors `_create_candidate_visit_locked`'s own
        # "never trust the upstream Privacy/Ignore exclusion alone" pattern):
        # an otherwise-eligible record stays honestly classified as what it
        # is, but privacy withholds it from export.
        required.append("privacy_restricted")
        eligible_as_named = False
        eligible_as_unidentified = False

    return ResearchExportEligibility(
        classification=classification,
        eligible_as_named_taxon=eligible_as_named,
        eligible_as_unidentified_wildlife=eligible_as_unidentified,
        required_reasons=tuple(required),
        recommended_reasons=tuple(recommended),
    )
