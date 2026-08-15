"""Wildlife eligibility semantics for `api.schemas.LabelCategory` (see
"Wildlife-native semantics" in product-doctrine.md and "Wildlife
classification boundary" in docs/place-activity-report-contract.md).

MockingBird is bird-first but wildlife-native: the taxonomy category
vocabulary is expected to grow beyond today's `bird`/`mammal` pair --
reptiles, amphibians, bats, visible invertebrates, and other legitimate
wildlife categories are all in scope over time (product-doctrine.md).
A reporting or retention feature that hardcodes "wildlife means
`category in {"bird", "mammal"}`" silently stops recognizing real wildlife
the moment the taxonomy grows, and needs its own rewrite to catch up. This
module is the one place that answers "is this taxonomy category a wildlife
taxon category?" so that growth never requires a second place to change.

## The eligibility rule

Deliberately a *denylist*, not an allowlist: every category is wildlife
*unless* it is one of the specific, currently-known non-wildlife categories
below. A brand-new wildlife category (for example a future "reptile") is
therefore recognized automatically the moment it is added to
`LabelCategory` -- no caller of `is_wildlife_category` needs to change. A
brand-new *non*-wildlife category (hypothetically), by contrast, does need
one small addition to `NON_WILDLIFE_LABEL_CATEGORIES` -- made at the same
review moment the category itself is introduced, in this one shared
location, rather than rediscovered independently by every caller.

This is safe specifically because `TaxonomyLabel.category` is already a
closed `LabelCategory` enum (`api.schemas.LabelCategory`): a value can only
ever reach this predicate by a deliberate, reviewed code change adding a
new enum member, never from unvalidated free text (see "Do not create
species truth from names or strings" in this module's own callers' scope
-- this predicate only ever inspects an already-resolved taxonomy
category, never a raw label string).

- `"pet"` -- a domestic animal (the seed taxonomy files "cat"/"dog" here,
  distinct from "mammal" -- api/demo_data.py). A real animal, but not
  wildlife activity at this Place.
- `"person"`, `"vehicle"`, `"object"` -- not an animal at all.
- `"false_positive"` -- explicitly not real activity.
- `"unknown"` -- a human confirmed *some* animal was present but abstained
  on species/kind (`unknown_bird`/`unknown_animal`). This genuinely is
  wildlife activity, but it is a distinct, separately-tracked concept (a
  confirmed-but-species-unresolved encounter, never fabricated into a
  taxon entry) -- callers that need to recognize it as wildlife activity
  do so through their own dedicated "confirmed but unresolved" handling
  (for example `mockingbird.analytics.place_activity_report`'s
  `confirmed_species_unresolved_visit_count`), not by asking this
  predicate, which only answers "does this category identify a concrete
  wildlife *taxon*?"
"""

from __future__ import annotations

# Every category NOT in this set is treated as a wildlife taxon category --
# see the module docstring for why this is a denylist rather than an
# allowlist, and why each of these specific categories is excluded.
NON_WILDLIFE_LABEL_CATEGORIES: frozenset[str] = frozenset(
    {"pet", "person", "vehicle", "object", "false_positive", "unknown"}
)


def is_wildlife_category(category: str) -> bool:
    """Does this taxonomy category identify a concrete wildlife taxon?

    Accepts a plain `str` (an `api.schemas.LabelCategory` member is itself
    `str`-valued and compares equal, so passing one works transparently)
    to stay dependency-free -- importable from a pure analytics module that
    deliberately does not import `api.schemas`
    (`mockingbird.analytics.place_activity_report`) as well as from
    `mockingbird.repository.product_repository`.

    `"unknown"` deliberately returns `False` here -- see the module
    docstring's note on why that category is handled as its own distinct
    concept by callers that care about it, not folded into this predicate.
    """

    return category not in NON_WILDLIFE_LABEL_CATEGORIES
