"""Server-side evaluation of the Review Queue's tabs, filters and counts.

Review Queue Scale Closure v1.

Why this module exists
----------------------
Performance / Scale / Stability Closure v1 left one release-blocking P0
open: `GET /api/review-queue` is unbounded. At the burst/backlog profile it
returned 2,060 items, 14.9 MB, in 74.4 s -- on Review Queue mount *and*
again after every saved correction.

Bounding the response alone was not a legitimate fix, and that milestone
said so explicitly (its §Z): `ReviewQueuePage.tsx` computed **every** tab
count, triage-filter count, source/stream facet, "showing N of M"
disclosure and bulk-selection eligibility client-side over the whole
downloaded queue. Returning one page while still presenting those numbers
as totals would have turned a performance fix into a truth regression.

So the predicates have to move to the server, and they have to move
*without changing what they decide*. Everything in this module is
therefore a deliberate, literal port of a named function in
`web/src/pages/ReviewQueuePage.tsx` (or `web/src/components/taxonomy.ts`),
kept in one small pure module -- no session, no I/O, no ORM -- so the port
can be read against its original side by side and pinned by tests. The
TypeScript original of each function is named in its docstring.

What is deliberately *not* here
-------------------------------
Nothing in this module classifies review truth, admits or rejects
observations, or reads a detector's confidence. It filters, orders and
counts already-built `ReviewQueueItem` values. `product_category`,
`review_status`, `is_demo_source` and every other classification continue
to be decided exactly where they were before, by
`_review_queue_product_context` in the queue build.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from mockingbird.api.schemas import (
    DetectionProposal,
    DetectionRun,
    MotionEvidenceResponse,
    ReviewQueueEvidenceFilter,
    ReviewQueueItem,
    ReviewQueueProductTab,
    ReviewQueueSourceStreamOption,
    ReviewQueueStatusFilter,
    ReviewQueueTargetFilter,
    ReviewQueueTriageFilter,
    TaxonomyLabel,
)


def taxonomy_key(value: str) -> str:
    """Port of `taxonomyKey` (web/src/components/taxonomy.ts)."""

    normalized = value.strip().lower().replace("-", "_")
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"[^a-z0-9_]+", "", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_")


def format_label(value: str) -> str:
    """Port of `formatLabel` (web/src/utils.ts).

    Kept separate from this repository's own `_display_name_from_label`,
    which normalizes `-` and drops empty parts; this one does neither,
    because it feeds search text that must match the client's.
    """

    return " ".join(
        part[:1].upper() + part[1:] if part else part for part in value.split("_")
    )


class TaxonomyIndex:
    """`findTaxonomyLabel`/`displayTaxonomyLabel`/`isFalsePositiveLabel`, indexed.

    The client re-scans the whole taxonomy list per lookup; over a large
    queue that is quadratic, so the same matching rule is precomputed into
    one key -> label map here. Insertion order is the list's order, and
    `setdefault` keeps the *first* matching label exactly as
    `Array.prototype.find` does.
    """

    def __init__(self, labels: list[TaxonomyLabel]) -> None:
        self._by_key: dict[str, TaxonomyLabel] = {}
        for label in labels:
            candidates = [label.id, label.label, label.display_name, *label.aliases]
            for candidate in candidates:
                key = taxonomy_key(candidate)
                if key:
                    self._by_key.setdefault(key, label)

    def find(self, value: str | None) -> TaxonomyLabel | None:
        if not value:
            return None
        return self._by_key.get(taxonomy_key(value))

    def display(self, value: str | None) -> str:
        found = self.find(value)
        if found is not None:
            return found.display_name
        return format_label(value or "unknown")

    def is_false_positive(self, value: str | None) -> bool:
        found = self.find(value)
        return (
            found is not None and found.category.value == "false_positive"
        ) or taxonomy_key(value or "") == "false_positive"

    def is_bird_review_label(self, value: str | None) -> bool:
        key = taxonomy_key(value or "")
        found = self.find(value)
        return (
            key in {"bird", "unknown_bird"}
            or (found is not None and found.category.value == "bird")
        )


_TRIAGE_ANIMAL = "animal_evidence"
_TRIAGE_VEHICLE_PERSON = "vehicle_person_evidence"
_TRIAGE_NO_CLEAR = "no_clear_proposal"
_TRIAGE_NOT_ANALYZED = "not_analyzed"
_TRIAGE_FALSE_POSITIVE = "false_positives"

_TRIAGE_SORT_RANK = {
    _TRIAGE_ANIMAL: 0,
    _TRIAGE_NOT_ANALYZED: 1,
    _TRIAGE_NO_CLEAR: 2,
    _TRIAGE_VEHICLE_PERSON: 3,
    _TRIAGE_FALSE_POSITIVE: 4,
}


def triage_category_for_label(value: str | None, taxonomy: TaxonomyIndex) -> str | None:
    """Port of `triageCategoryForLabel`."""

    key = taxonomy_key(value or "")
    found = taxonomy.find(value)
    category = found.category.value if found is not None else None
    if key == "false_positive" or category == "false_positive":
        return _TRIAGE_FALSE_POSITIVE
    if key in {"person", "vehicle"} or category in {"person", "vehicle"}:
        return _TRIAGE_VEHICLE_PERSON
    if key in {"animal", "unknown_animal", "bird", "unknown_bird"} or category in {
        "bird",
        "mammal",
        "pet",
    }:
        return _TRIAGE_ANIMAL
    return None


def _triage_proposal(
    proposal: DetectionProposal,
    taxonomy: TaxonomyIndex,
) -> tuple[str, str] | None:
    """Port of `triageProposal`."""

    for value in (
        proposal.suggested_species,
        proposal.suggested_subject_label,
        proposal.label,
    ):
        category = triage_category_for_label(value, taxonomy)
        label = (value or "").strip()
        if category and label:
            return category, label
    return None


def review_queue_target_type(item: ReviewQueueItem) -> str:
    """Port of `reviewQueueTargetType`."""

    if item.target_type in {"visit", "event"}:
        return item.target_type
    return "visit" if item.visit_id else "event"


def review_queue_target_id(item: ReviewQueueItem) -> str:
    """Port of `reviewQueueTargetId`."""

    return (
        item.target_id
        or item.visit_id
        or item.event_id
        or re.sub(r"^review-queue-", "", item.id)
    )


@dataclass
class ReviewItemFilterFacts:
    """Port of `ReviewItemFilterMetadata`, for one queue item."""

    has_detection_proposal: bool
    has_media: bool
    has_motion_evidence: bool
    search_text: str
    source_id: str | None
    source_name: str | None
    stream_id: str | None
    stream_name: str | None
    triage_category: str
    triage_confidence: float | None


def _optional_number_text(value: float | int | None) -> str:
    """JavaScript's `Number.prototype.toString`, for the values that reach it.

    Only ever applied to the numeric fields `reviewQueueSearchText` joins,
    so the cases that matter are integers (`1` not `1.0`) and finite
    floats. Python's `repr` agrees with JavaScript on both for the value
    ranges these fields hold (ratios, pixel counts, thresholds).
    """

    if value is None:
        return ""
    if isinstance(value, bool):  # pragma: no cover - not reachable today
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if value == int(value) and abs(value) < 1e16:
        return str(int(value))
    return repr(value)


def _timestamp_text(value: object) -> str:
    """The item's own serialized datetime text, as the client's JSON carries it."""

    if value is None:
        return ""
    return str(value)


class ReviewQueueFilterIndex:
    """Per-item filter facts for a whole queue build.

    Port of `filterMetadataByItemId` plus the predicate helpers that read
    it. Built once per request: the client's own version rebuilds the same
    map from the same three evidence collections
    (`/api/detection-proposals`, `/api/detection-runs`,
    `/api/motion-evidence`) that it already loads in full, so this changes
    where the work happens, not how much of it there is or what it decides.
    """

    def __init__(
        self,
        items: list[ReviewQueueItem],
        *,
        proposals: list[DetectionProposal],
        detection_runs: list[DetectionRun],
        motion_evidence: list[MotionEvidenceResponse],
        taxonomy_labels: list[TaxonomyLabel],
        build_search_text: bool = True,
    ) -> None:
        self.taxonomy = TaxonomyIndex(taxonomy_labels)

        # `reviewEvidenceProposals` scans every proposal per item; index by
        # the three keys `proposalRelationForReviewItem` actually matches on.
        self._proposals_by_visit: dict[str, list[DetectionProposal]] = {}
        self._proposals_by_event: dict[str, list[DetectionProposal]] = {}
        self._unlinked_proposals_by_media: dict[str, list[DetectionProposal]] = {}
        for proposal in proposals:
            if proposal.visit_id:
                self._proposals_by_visit.setdefault(proposal.visit_id, []).append(
                    proposal
                )
            if proposal.event_id:
                self._proposals_by_event.setdefault(proposal.event_id, []).append(
                    proposal
                )
            if not proposal.event_id and not proposal.visit_id:
                self._unlinked_proposals_by_media.setdefault(
                    proposal.media_asset_id, []
                ).append(proposal)

        self._evidence_by_visit: dict[str, list[MotionEvidenceResponse]] = {}
        self._evidence_by_event: dict[str, list[MotionEvidenceResponse]] = {}
        self._evidence_by_media: dict[str, list[MotionEvidenceResponse]] = {}
        for evidence in motion_evidence:
            if evidence.promoted_visit_id:
                self._evidence_by_visit.setdefault(
                    evidence.promoted_visit_id, []
                ).append(evidence)
            if evidence.promoted_event_id:
                self._evidence_by_event.setdefault(
                    evidence.promoted_event_id, []
                ).append(evidence)
            if evidence.snapshot_media_asset_id:
                self._evidence_by_media.setdefault(
                    evidence.snapshot_media_asset_id, []
                ).append(evidence)

        self._run_media_asset_ids = {run.media_asset_id for run in detection_runs}
        self._runs_by_id = {run.id: run for run in detection_runs}

        # Search text is the one fact that costs real work per item (it
        # joins ~60 fields plus every linked proposal and MotionEvidence
        # row), and the Review Queue's search box is empty in the default
        # view. Build it only when a search is actually active; every other
        # fact is always needed, because the triage counts and the
        # source/stream facet are always displayed.
        self._build_search_text = build_search_text
        self.facts: dict[str, ReviewItemFilterFacts] = {
            item.id: self._facts_for_item(item) for item in items
        }

    # -- evidence association ------------------------------------------------

    def _proposal_evidence(
        self, item: ReviewQueueItem
    ) -> list[tuple[DetectionProposal, str]]:
        """Port of `reviewEvidenceProposals` (+ `proposalRelationForReviewItem`)."""

        linked: list[DetectionProposal] = []
        seen: set[str] = set()
        for bucket, key in (
            (self._proposals_by_visit, item.visit_id),
            (self._proposals_by_event, item.event_id),
        ):
            if not key:
                continue
            for proposal in bucket.get(key, ()):
                if proposal.id in seen:
                    continue
                seen.add(proposal.id)
                linked.append(proposal)

        same_media: list[DetectionProposal] = []
        media_asset_id = item.media_asset.id if item.media_asset is not None else None
        if media_asset_id:
            for proposal in self._unlinked_proposals_by_media.get(media_asset_id, ()):
                if proposal.id in seen:
                    continue
                seen.add(proposal.id)
                same_media.append(proposal)

        # `linked` before `same_media`, each newest-first by `created_at` --
        # the client's own comparator.
        linked.sort(key=lambda proposal: proposal.created_at, reverse=True)
        same_media.sort(key=lambda proposal: proposal.created_at, reverse=True)
        return [(proposal, "linked") for proposal in linked] + [
            (proposal, "same_media") for proposal in same_media
        ]

    def _motion_evidence(self, item: ReviewQueueItem) -> list[MotionEvidenceResponse]:
        """Port of `reviewMotionEvidenceForQueueItem`."""

        matched: list[MotionEvidenceResponse] = []
        seen: set[str] = set()
        media_asset_id = item.media_asset.id if item.media_asset is not None else None
        for bucket, key in (
            (self._evidence_by_visit, item.visit_id),
            (self._evidence_by_event, item.event_id),
            (self._evidence_by_media, media_asset_id),
        ):
            if not key:
                continue
            for evidence in bucket.get(key, ()):
                if evidence.id in seen:
                    continue
                seen.add(evidence.id)
                matched.append(evidence)
        matched.sort(key=lambda evidence: evidence.created_at, reverse=True)
        return matched

    # -- triage --------------------------------------------------------------

    def _triage(
        self,
        item: ReviewQueueItem,
        proposal_evidence: list[tuple[DetectionProposal, str]],
    ) -> tuple[str, float | None]:
        """Port of `reviewTriageSummary`, keeping only what filters/sorts read."""

        if self.taxonomy.is_false_positive(item.suggested_label):
            return _TRIAGE_FALSE_POSITIVE, None

        active: list[tuple[DetectionProposal, str]] = []
        for proposal, _relation in proposal_evidence:
            if proposal.status.value == "rejected":
                continue
            triaged = _triage_proposal(proposal, self.taxonomy)
            if triaged is None:
                continue
            active.append((proposal, triaged[0]))

        def strongest(category: str) -> DetectionProposal | None:
            matching = [
                proposal for proposal, value in active if value == category
            ]
            if not matching:
                return None
            # `Array.prototype.sort` is stable, so equal confidences keep
            # `_proposal_evidence`'s order -- `max` does the same.
            return max(matching, key=lambda proposal: proposal.confidence)

        animal = strongest(_TRIAGE_ANIMAL)
        vehicle_or_person = strongest(_TRIAGE_VEHICLE_PERSON)
        selected = animal or vehicle_or_person
        if selected is not None:
            return (
                _TRIAGE_ANIMAL if selected is animal else _TRIAGE_VEHICLE_PERSON,
                selected.confidence,
            )

        media_asset_id = item.best_media_asset_id or (
            item.media_asset.id if item.media_asset is not None else None
        )
        has_run = bool(media_asset_id and media_asset_id in self._run_media_asset_ids)
        return (_TRIAGE_NO_CLEAR if has_run else _TRIAGE_NOT_ANALYZED), None

    # -- search text ---------------------------------------------------------

    def _search_text(
        self,
        item: ReviewQueueItem,
        *,
        proposal_evidence: list[tuple[DetectionProposal, str]],
        motion_evidence: list[MotionEvidenceResponse],
        source_id: str | None,
        source_name: str | None,
        stream_id: str | None,
        stream_name: str | None,
    ) -> str:
        """Port of `reviewQueueSearchText` + the proposal/motion text around it.

        One disclosed departure: the client appends the *identification-
        assistant* run summary's own fields (adapter id/name/status, setup
        hint, assistant focus-crop labels) to an item's search text. Those
        fields exist only on a fully hydrated review card -- resolving them
        is four SQL statements per item and 46% of the old response's bytes
        -- so making search bounded means not resolving them for items that
        are only being *searched*. Every label a user actually searches for
        is still covered: the Visit's own `suggested_label`, its pending
        species suggestion, and each linked detection proposal's
        `label`/`suggested_subject_label`/`suggested_species` are all
        below. See §F of the milestone report.
        """

        suggested_label = item.suggested_label or ""
        media = item.media_asset
        focus_normalized = item.focus_crop_box_normalized
        focus_pixels = item.focus_crop_box_pixels

        parts: list[str] = [
            item.id,
            item.item_type,
            item.target_type,
            item.target_id,
            item.title,
            item.stream_id,
            item.stream_name or "",
            item.source_id or "",
            item.source_name or "",
            item.event_id or "",
            item.visit_id or "",
            item.primary_zone_id or "",
            item.primary_zone_name or "",
            item.primary_zone_type.value if item.primary_zone_type else "",
            item.zone_id or "",
            item.zone_name or "",
            item.zone_type.value if item.zone_type else "",
            item.best_media_asset_id or "",
            item.activity_session_id or "",
            _timestamp_text(item.activity_started_at),
            _timestamp_text(item.activity_last_seen_at),
            str(item.detection_count),
            _optional_number_text(item.best_frame_sequence),
            _optional_number_text(item.best_changed_ratio),
            _optional_number_text(item.best_changed_pixels),
            _optional_number_text(item.best_total_scored_pixels),
            _optional_number_text(item.effective_threshold_used),
            item.threshold_source or "",
            "fine motion applied" if item.fine_motion_applied else "",
            *item.image_quality_warnings,
            suggested_label,
            item.suggestion_id or "",
            _optional_number_text(item.suggestion_confidence),
            item.suggestion_reason or "",
            "activity focus crop" if item.focus_crop_available else "full best frame",
            item.focus_crop_source.value if item.focus_crop_source else "",
            item.focus_crop_label or "",
            (
                f"{focus_normalized.x} {focus_normalized.y} "
                f"{focus_normalized.width} {focus_normalized.height}"
                if focus_normalized is not None
                else ""
            ),
            (
                f"{focus_pixels.x} {focus_pixels.y} "
                f"{focus_pixels.width} {focus_pixels.height}"
                if focus_pixels is not None
                else ""
            ),
            *item.focus_crop_warnings,
            self.taxonomy.display(suggested_label or "unknown"),
            item.reason,
            media.id if media is not None else "",
            media.filename if media is not None else "",
            (media.original_filename or "") if media is not None else "",
            (media.notes or "") if media is not None else "",
            # `reviewItemFilterMetadata`'s own additions.
            source_id or "",
            source_name or "",
            stream_id or "",
            stream_name or "",
            media.source_id if media is not None else "",
            media.stream_id if media is not None else "",
        ]
        for proposal, _relation in proposal_evidence:
            run = self._runs_by_id.get(proposal.run_id)
            parts.extend(
                [
                    proposal.id,
                    proposal.label,
                    proposal.suggested_subject_label,
                    proposal.suggested_species or "",
                    proposal.status.value,
                    proposal.run_id,
                    run.source.value if run is not None else "",
                    (run.summary or "") if run is not None else "",
                ]
            )
        for evidence in motion_evidence:
            parts.extend(
                [
                    evidence.id,
                    evidence.status.value,
                    evidence.source_id or "",
                    evidence.stream_id or "",
                    evidence.zone_id or "",
                    evidence.snapshot_media_asset_id or "",
                    evidence.notes or "",
                ]
            )
        return " ".join(parts).lower()

    # -- per-item facts ------------------------------------------------------

    def _facts_for_item(self, item: ReviewQueueItem) -> ReviewItemFilterFacts:
        proposal_evidence = self._proposal_evidence(item)
        motion_evidence = self._motion_evidence(item)
        media = item.media_asset

        source_id = (
            item.source_id
            or (media.source_id if media is not None else None)
            or next(
                (
                    evidence.source_id
                    for evidence in motion_evidence
                    if evidence.source_id
                ),
                None,
            )
        )
        stream_id = (
            item.stream_id
            or (media.stream_id if media is not None else None)
            or next(
                (
                    evidence.stream_id
                    for evidence in motion_evidence
                    if evidence.stream_id
                ),
                None,
            )
        )
        has_media = (
            media is not None
            or any(proposal.media_asset_id for proposal, _ in proposal_evidence)
            or any(evidence.snapshot_media_asset_id for evidence in motion_evidence)
        )
        triage_category, triage_confidence = self._triage(item, proposal_evidence)
        return ReviewItemFilterFacts(
            has_detection_proposal=len(proposal_evidence) > 0,
            has_media=has_media,
            has_motion_evidence=len(motion_evidence) > 0,
            search_text=(
                self._search_text(
                    item,
                    proposal_evidence=proposal_evidence,
                    motion_evidence=motion_evidence,
                    source_id=source_id,
                    source_name=item.source_name,
                    stream_id=stream_id,
                    stream_name=item.stream_name,
                )
                if self._build_search_text
                else ""
            ),
            source_id=source_id,
            source_name=item.source_name,
            stream_id=stream_id,
            stream_name=item.stream_name,
            triage_category=triage_category,
            triage_confidence=triage_confidence,
        )

    # -- predicates ----------------------------------------------------------

    def matches_evidence_filter(
        self,
        item: ReviewQueueItem,
        evidence_filter: ReviewQueueEvidenceFilter,
    ) -> bool:
        """Port of `matchesEvidenceFilter`."""

        facts = self.facts[item.id]
        if evidence_filter is ReviewQueueEvidenceFilter.has_media:
            return facts.has_media
        if evidence_filter is ReviewQueueEvidenceFilter.has_detection_proposal:
            return facts.has_detection_proposal
        if evidence_filter is ReviewQueueEvidenceFilter.has_motion_evidence:
            return facts.has_motion_evidence
        if evidence_filter is ReviewQueueEvidenceFilter.no_proposal_evidence:
            return not facts.has_detection_proposal
        return True

    def matches_source_stream_filter(
        self,
        item: ReviewQueueItem,
        source_stream_filter: str,
    ) -> bool:
        """Port of `matchesSourceStreamFilter`."""

        if source_stream_filter == "all":
            return True
        facts = self.facts[item.id]
        if source_stream_filter.startswith("stream:"):
            return facts.stream_id == source_stream_filter[len("stream:") :]
        if source_stream_filter.startswith("source:"):
            return facts.source_id == source_stream_filter[len("source:") :]
        return True

    def matches_triage_filter(
        self,
        item: ReviewQueueItem,
        triage_filter: ReviewQueueTriageFilter,
    ) -> bool:
        if triage_filter is ReviewQueueTriageFilter.all:
            return True
        return self.facts[item.id].triage_category == triage_filter.value

    def matches_search(self, item: ReviewQueueItem, normalized_search: str) -> bool:
        if not normalized_search:
            return True
        if not self._build_search_text:  # pragma: no cover - guarded by caller
            raise RuntimeError("review queue search index was not built")
        return normalized_search in self.facts[item.id].search_text

    def triage_sort_key(self, item: ReviewQueueItem) -> tuple[int, float]:
        """Port of the `reviewSort === "triage"` comparator."""

        facts = self.facts[item.id]
        return (
            _TRIAGE_SORT_RANK[facts.triage_category],
            -(facts.triage_confidence or 0.0),
        )

    def triage_counts(self, items: list[ReviewQueueItem]) -> dict[str, int]:
        """Port of `queueCounts`."""

        counts = {
            "all": 0,
            _TRIAGE_ANIMAL: 0,
            _TRIAGE_VEHICLE_PERSON: 0,
            _TRIAGE_NO_CLEAR: 0,
            _TRIAGE_NOT_ANALYZED: 0,
            _TRIAGE_FALSE_POSITIVE: 0,
        }
        for item in items:
            counts["all"] += 1
            counts[self.facts[item.id].triage_category] += 1
        return counts

    def source_stream_options(
        self, items: list[ReviewQueueItem]
    ) -> list[ReviewQueueSourceStreamOption]:
        """Port of `sourceStreamFilterOptions`."""

        stream_counts: dict[str, tuple[int, str]] = {}
        source_counts: dict[str, tuple[int, str]] = {}
        for item in items:
            facts = self.facts[item.id]
            if facts.stream_id:
                count, label = stream_counts.get(facts.stream_id, (0, facts.stream_id))
                stream_counts[facts.stream_id] = (
                    count + 1,
                    facts.stream_name or label,
                )
            if facts.source_id:
                count, label = source_counts.get(facts.source_id, (0, facts.source_id))
                source_counts[facts.source_id] = (
                    count + 1,
                    facts.source_name or label,
                )

        options = [
            ReviewQueueSourceStreamOption(
                value="all", label="All streams/sources", count=len(items)
            )
        ]
        # `localeCompare` on identifiers: case-insensitive first, then
        # codepoint, which agrees with the browser for the ASCII
        # identifiers these are.
        for stream_id, (count, label) in sorted(
            stream_counts.items(), key=lambda entry: (entry[0].lower(), entry[0])
        ):
            options.append(
                ReviewQueueSourceStreamOption(
                    value=f"stream:{stream_id}", label=f"Stream {label}", count=count
                )
            )
        for source_id, (count, label) in sorted(
            source_counts.items(), key=lambda entry: (entry[0].lower(), entry[0])
        ):
            options.append(
                ReviewQueueSourceStreamOption(
                    value=f"source:{source_id}", label=f"Source {label}", count=count
                )
            )
        return options

    def is_species_suggestion_batch_eligible(self, item: ReviewQueueItem) -> bool:
        """Port of `isSpeciesSuggestionBatchEligible`."""

        return (
            item.target_type == "visit"
            and item.review_status.value == "needs_review"
            and self.taxonomy.is_bird_review_label(item.suggested_label)
        )


def matches_product_tab(
    item: ReviewQueueItem,
    tab: ReviewQueueProductTab,
    show_legacy_and_test_activity: bool,
) -> bool:
    """Port of `matchesProductReviewTab`.

    `ReviewQueueProductTab.all` has no client counterpart -- it is this
    endpoint's own "no tab scoping" value, used by callers (the Streams
    surfaces' per-Stream counts) that want the queue without a tab.
    """

    if tab is ReviewQueueProductTab.all:
        return True
    if tab is ReviewQueueProductTab.reviewed:
        return item.product_category == "reviewed"
    if tab is ReviewQueueProductTab.legacy_activity:
        return show_legacy_and_test_activity and item.product_category == (
            "legacy_activity"
        )
    if item.review_status.value != "needs_review":
        return False
    if tab is ReviewQueueProductTab.animals:
        return item.target_type == "visit" and item.product_category == "animal"
    if tab is ReviewQueueProductTab.other_activity:
        return item.product_category == "other_activity"
    return item.product_category == "unchecked"


def matches_status_filter(
    item: ReviewQueueItem,
    status_filter: ReviewQueueStatusFilter,
) -> bool:
    """Port of `matchesStatusFilter`."""

    if status_filter is ReviewQueueStatusFilter.all:
        return True
    if status_filter is ReviewQueueStatusFilter.reviewed:
        return item.review_status.value == "reviewed"
    return item.review_status.value == "needs_review"


def matches_target_filter(
    item: ReviewQueueItem,
    target_filter: ReviewQueueTargetFilter,
) -> bool:
    """Port of `matchesTargetFilter`."""

    if target_filter is ReviewQueueTargetFilter.all:
        return True
    return review_queue_target_type(item) == target_filter.value


def is_bulk_correction_eligible(item: ReviewQueueItem) -> bool:
    """Port of `isBulkCorrectionEligible`."""

    return item.review_status.value == "needs_review"


def product_tab_counts(items: list[ReviewQueueItem]) -> dict[str, int]:
    """Port of `productQueueCounts`.

    Note the client's own `else` branch: anything that is not animal /
    other_activity / unchecked / legacy_activity counts as `reviewed`, and
    the `animals` bucket additionally requires `target_type === "visit"`.
    Transcribed exactly, including the fact that a non-Visit item whose
    `product_category` is `animal` falls through to `reviewed`.
    """

    counts = {
        "animals": 0,
        "other_activity": 0,
        "unchecked": 0,
        "legacy_activity": 0,
        "reviewed": 0,
    }
    for item in items:
        if item.target_type == "visit" and item.product_category == "animal":
            counts["animals"] += 1
        elif item.product_category == "other_activity":
            counts["other_activity"] += 1
        elif item.product_category == "unchecked":
            counts["unchecked"] += 1
        elif item.product_category == "legacy_activity":
            counts["legacy_activity"] += 1
        else:
            counts["reviewed"] += 1
    return counts


def unique_label_values(values: list[str | None]) -> list[str]:
    """Port of `uniqueLabelValues`."""

    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        cleaned = (value or "").strip()
        if not cleaned:
            continue
        key = taxonomy_key(cleaned)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(cleaned)
    return unique
