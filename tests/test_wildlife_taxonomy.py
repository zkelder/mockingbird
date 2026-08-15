"""`mockingbird.wildlife_taxonomy.is_wildlife_category` (see "Wildlife
classification boundary" in docs/place-activity-report-contract.md and the
module's own docstring)."""

from __future__ import annotations

import pytest

from mockingbird.wildlife_taxonomy import NON_WILDLIFE_LABEL_CATEGORIES, is_wildlife_category


@pytest.mark.parametrize("category", ["bird", "mammal"])
def test_current_wildlife_categories_are_recognized(category: str) -> None:
    assert is_wildlife_category(category) is True


@pytest.mark.parametrize(
    "category", ["pet", "person", "vehicle", "object", "false_positive", "unknown"]
)
def test_current_non_wildlife_categories_are_excluded(category: str) -> None:
    assert is_wildlife_category(category) is False


@pytest.mark.parametrize("category", ["reptile", "amphibian", "bat", "invertebrate", "insect"])
def test_a_future_wildlife_category_is_recognized_without_a_code_change(category: str) -> None:
    """The whole point of the denylist design: a taxonomy category that
    does not exist in today's vocabulary at all must still be treated as
    wildlife by default, so the taxonomy can grow (product-doctrine.md's
    "Wildlife-native semantics") without a second rewrite of every
    wildlife-classification call site."""

    assert category not in NON_WILDLIFE_LABEL_CATEGORIES
    assert is_wildlife_category(category) is True


def test_label_category_enum_members_are_accepted_transparently() -> None:
    """`api.schemas.LabelCategory` is a `str` Enum, so passing a member
    directly (not just its `.value`) must compare correctly against the
    denylist without requiring every caller to unwrap `.value` first."""

    from mockingbird.api.schemas import LabelCategory

    assert is_wildlife_category(LabelCategory.bird) is True
    assert is_wildlife_category(LabelCategory.mammal) is True
    assert is_wildlife_category(LabelCategory.pet) is False
    assert is_wildlife_category(LabelCategory.person) is False
    assert is_wildlife_category(LabelCategory.vehicle) is False
    assert is_wildlife_category(LabelCategory.object) is False
    assert is_wildlife_category(LabelCategory.false_positive) is False
    assert is_wildlife_category(LabelCategory.unknown) is False


def test_non_wildlife_categories_denylist_matches_documented_membership() -> None:
    """Locks in the exact denylist membership so a future accidental
    addition/removal is caught here, in one place, rather than discovered
    indirectly through an unrelated report test failing."""

    assert NON_WILDLIFE_LABEL_CATEGORIES == frozenset(
        {"pet", "person", "vehicle", "object", "false_positive", "unknown"}
    )
