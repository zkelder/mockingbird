"""Review Decision provenance / truth-boundary authority policy (see
docs/review-decision-provenance-contract.md).

`ReviewLabel` (`product-doctrine.md`'s "Review Decision") had no durable
reviewer-origin identity at all before this module: a real `ReviewLabel`
written through the genuine `POST /api/review-labels` path by an LLM/agent's
own visual inspection was structurally indistinguishable from a genuine
human correction anywhere downstream (Bird Log, reviewed-only Dataset
Export, classifier training manifests, analytics) -- distinguishable only
by free-text prose in `notes`, which nothing enforced. See
`evaluation_governance.py` for the narrower, earlier fix that closed this
same gap for the *offline evaluation-manifest* boundary only; this module
closes it for the live product `ReviewLabel` record itself.

This module is intentionally small and dependency-free (no SQLAlchemy, no
FastAPI, no product-repository import) so it can be imported both by
`mockingbird.repository.product_repository` and by a lightweight,
ORM-free script such as `scripts/evaluate_bioclip_field_truth.py` or a
bounded maintenance command, exactly like `mockingbird.observation.
evaluation_governance`'s own import-weight discipline.

## The four provenance states

- `"human"` -- a person intentionally reviewed the evidence through a
  user-facing/product review action (the Review Queue, Fast Review, Visit
  Detail correction, bulk correction, revise/reopen). Authoritative.
- `"imported_curated"` -- truth imported from a dataset/manifest/process
  whose human-reviewed provenance is explicit and separately governed (for
  example this product's own first-run demo seed content). Authoritative
  *only* because the specific importer already vouches for it explicitly;
  see "Do not equate arbitrary imports with human truth" below. Requires a
  named `reviewer_identity`.
- `"agent_diagnostic"` -- an LLM, model, automation, test harness, or other
  non-human process assessed the evidence. Never authoritative. Requires a
  named `reviewer_identity` (which model/run/session produced it) so a
  diagnostic assessment is honestly attributable, not an anonymous blob.
- `"legacy_unattributed"` -- a row that already existed when the
  `_migrate_to_review_decision_provenance` schema migration ran, backfilled
  by that migration (never by a create request -- see
  `is_creatable_review_origin`). Reviewer origin cannot be proven from
  persisted data, but every creation path traced for this contract that
  could reach a real product database before this milestone required
  direct interactive human use, except this product's own demo-seed
  content (separately marked `imported_curated`) and the three 2026-08-10
  rows this milestone explicitly identifies and repairs to
  `agent_diagnostic` by name (see the milestone's final report). Given
  that, treating a *pre-existing* `legacy_unattributed` row as continuing
  authoritative -- deliberately, not silently -- is what "Avoid breaking
  existing users' history unnecessarily" (this milestone's own Part 9)
  requires; a *brand-new* row can never legitimately claim this origin.

`None` (no explicit origin at all) can only mean one thing going forward: a
create request made after this migration existed and omitted the field.
It is never authoritative and never backfilled to anything else -- see
`is_authority_eligible`.
"""

from __future__ import annotations

from typing import Literal

# The origins a *create* request may explicitly claim. Deliberately does not
# include `legacy_unattributed`: a brand-new row cannot honestly claim to
# predate the provenance column that its own request is using.
REVIEW_ORIGIN_VALUES: tuple[str, ...] = ("human", "imported_curated", "agent_diagnostic")
ReviewOrigin = Literal["human", "imported_curated", "agent_diagnostic"]

LEGACY_UNATTRIBUTED_ORIGIN = "legacy_unattributed"

# Every origin value this module recognizes as internally consistent when
# *reading* a stored row -- the creatable ones plus the migration-only
# legacy sentinel. API *response* schemas must type their `review_origin`
# field as `ReviewOriginStored`, not the narrower `ReviewOrigin`, or
# constructing a response for a real backfilled legacy row raises a
# Pydantic validation error -- this was caught during implementation
# specifically because a stored value is a strict superset of a creatable
# one, not the same set.
REVIEW_ORIGIN_STORED_VALUES: tuple[str, ...] = (*REVIEW_ORIGIN_VALUES, LEGACY_UNATTRIBUTED_ORIGIN)
ReviewOriginStored = Literal["human", "imported_curated", "agent_diagnostic", "legacy_unattributed"]
KNOWN_REVIEW_ORIGINS: frozenset[str] = frozenset(REVIEW_ORIGIN_STORED_VALUES)

# The only origins eligible to establish or correct durable reviewed
# Observation truth (product-doctrine.md's truth boundary). `None` is
# deliberately absent -- see `is_authority_eligible`. `legacy_unattributed`
# is deliberately present -- see the module docstring's "Legacy/
# unattributed" note; it is a documented backward-compatibility policy
# choice, not a claim that these rows are positively known to be human.
AUTHORITATIVE_ORIGINS: frozenset[str] = frozenset({"human", "imported_curated", LEGACY_UNATTRIBUTED_ORIGIN})

# Origins that must carry a named `reviewer_identity` because "who/what"
# is not otherwise self-evident the way an interactive human product action
# is. Mirrors `evaluation_governance.EvaluationExample`'s existing
# `reviewed_truth_requires_reviewer_identity` rule, applied here to the live
# `ReviewLabel` record itself instead of an offline manifest.
IDENTITY_REQUIRED_ORIGINS: frozenset[str] = frozenset({"imported_curated", "agent_diagnostic"})

# The same disclosure vocabulary `evaluation_governance._NON_HUMAN_REVIEW_
# MARKERS` established -- reused, not duplicated, so both modules agree on
# what counts as a self-disclosed non-human review. Bounded and documented,
# not a content classifier: it exists only to catch an honest existing
# disclosure (this codebase's own established convention, for example
# `notes="[AGENT VISUAL REVIEW ... not independently human-confirmed]"`),
# never to infer non-human origin from arbitrary text.
NON_HUMAN_DISCLOSURE_MARKERS: tuple[str, ...] = (
    "agent", "claude", "language model", "llm", "autonomous", "chatbot",
    "ai visual", "ai-visual", "machine visual", "model visual",
)


class ReviewProvenanceError(ValueError):
    """A bounded Review Decision provenance validation failure code."""


def is_creatable_review_origin(origin: str | None) -> bool:
    """`None` is always valid at creation time (it just is not
    authoritative -- see `is_authority_eligible`); any non-`None` value a
    *create* request supplies must be one of the three explicit origins.
    `legacy_unattributed` is intentionally rejected here even though it is
    a recognized *stored* value -- see `KNOWN_REVIEW_ORIGINS` vs.
    `REVIEW_ORIGIN_VALUES`."""

    return origin is None or origin in REVIEW_ORIGIN_VALUES


def is_authority_eligible(origin: str | None) -> bool:
    """Is a Review Decision with this origin eligible to establish or
    correct durable reviewed Observation truth?

    This is the ONE place that answers this question. Every consumer --
    creation-time gating, reviewed-only Dataset Export, classifier
    training-manifest eligibility, Detection Quality evaluation, the
    "effective current label" resolvers -- must call this rather than
    re-deriving the answer from its own string comparison (see "Do not
    scatter ad-hoc string checks" in this milestone's own instructions).

    `None` (no explicit origin: a create request made after this
    contract existed that omitted the field) is honestly **not**
    authoritative -- an automation, CLI, or future LLM integration must
    never become observational authority merely by failing to send a
    field. `legacy_unattributed` (a row that already existed when the
    provenance migration ran, and was backfilled to this exact sentinel
    by that migration, never left `None`) **is** treated as authoritative,
    as a deliberate, documented backward-compatibility policy -- see the
    module docstring's "Legacy/unattributed" note and "Avoid breaking
    existing users' history unnecessarily" in this milestone's own
    instructions. Since the migration backfills every pre-existing row
    away from `None`, `None` unambiguously means "a post-migration write
    that omitted the field" from this point forward, so this function
    needs no timestamp or activation-boundary comparison to tell the two
    apart.
    """

    return origin in AUTHORITATIVE_ORIGINS


def discloses_non_human_review(*texts: str | None) -> bool:
    """True if any given text honestly self-discloses non-human review
    provenance using this codebase's own established disclosure
    convention. Used both to validate a *new* claim (defense in depth,
    mirroring `evaluation_governance.py`) and to identify pre-existing
    rows a repair script should migrate to explicit `agent_diagnostic`
    provenance."""

    for text in texts:
        if not text:
            continue
        lowered = text.lower()
        if any(marker in lowered for marker in NON_HUMAN_DISCLOSURE_MARKERS):
            return True
    return False


def validate_review_origin(
    origin: str | None,
    reviewer_identity: str | None,
    *,
    notes: str | None = None,
) -> None:
    """Raise `ReviewProvenanceError` for an internally-inconsistent
    provenance claim. Callers should validate before persisting a new
    `ReviewLabel` row -- this never reads or writes the database itself."""

    if not is_creatable_review_origin(origin):
        raise ReviewProvenanceError("unsupported_review_origin")
    if origin in IDENTITY_REQUIRED_ORIGINS and not (reviewer_identity and reviewer_identity.strip()):
        # The one load-bearing rule this module exists to enforce for a
        # non-human-verifiable origin: nothing may claim `imported_curated`
        # or `agent_diagnostic` without naming who/what it actually is.
        raise ReviewProvenanceError(f"{origin}_requires_reviewer_identity")
    if origin == "human" and discloses_non_human_review(reviewer_identity, notes):
        # Defense in depth (mirrors evaluation_governance.py exactly): a
        # request claiming human origin whose own identity/notes text
        # self-discloses non-human review is rejected outright rather than
        # silently trusted. A careless caller (never assumed malicious)
        # copying an agent's own disclosure into notes while also claiming
        # `origin="human"` fails loudly at the API boundary instead of
        # silently becoming observational authority.
        raise ReviewProvenanceError("human_origin_conflicts_with_disclosed_non_human_review")
