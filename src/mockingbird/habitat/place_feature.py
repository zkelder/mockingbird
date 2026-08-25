"""Pure vocabulary for Place Features and Place Feature Change Events -- see
docs/place-features-habitat-change-v2-contract.md "Data model". Parallel to
`mockingbird.habitat.phenology` (the Habitat & Phenology Foundation v1
domain this milestone extends): same package, same "no database access, no
network access" discipline, same closed-vocabulary-as-a-plain-string-in-the-
DB / `Literal`-at-the-API-layer split.

A Place Feature is a durable, named, physically meaningful thing around the
observation site (a feeder, a bird bath, a nest box, a planting area) --
distinct from a `PlaceHabitatFactModel` tag: a Feature has its own identity
and lifecycle, so "the sunflower feeder" can be referred to as one thing
over time rather than re-described as a fresh, untracked fact on every
mention. A Place Feature Change Event is a dated, typed, human-recorded
fact about something that happened to one Feature (or, when `feature_id` is
absent, a Place-level habitat change not tied to any tracked Feature) --
distinct from a `PlacePhenologyObservationModel` interval, which describes
a *recurring biological phenomenon* ("azaleas flowering"), not a discrete
one-time change ("planted the azaleas"). Confirmed absent before this
milestone: no discrete before/after change-event concept existed anywhere
in this codebase -- see `habitat_association.py`'s own docstring and
"Archaeology" in docs/place-features-habitat-change-v2-report.md.
"""

from __future__ import annotations

from typing import Literal

FEATURE_INFORMATION_CLASS = "reviewed"
FEATURE_PROVENANCE_MANUAL_ENTRY = "user_manual_entry"

# Deliberately bounded (Phase 3 of the governing brief: "keep the taxonomy
# small and extensible"). Ordinary yard vocabulary the brief itself uses
# ("Back hedge," "Brush pile," "Native flower bed") is carried by the
# free-text `name` field, exactly the same "category is closed, label is
# free text" split `PlaceHabitatFactModel` already uses -- not by growing
# this list. "other" is the deliberate escape hatch so a user is never
# blocked from recording something this list did not anticipate.
PlaceFeatureType = Literal[
    "feeder",
    "water",
    "nest_box",
    "vegetation_patch",
    "structure",
    "habitat_area",
    "other",
]
PLACE_FEATURE_TYPES: tuple[PlaceFeatureType, ...] = (
    "feeder",
    "water",
    "nest_box",
    "vegetation_patch",
    "structure",
    "habitat_area",
    "other",
)

# Bounded from the governing brief's longer candidate list (Phase 4):
# "habitat_restored" deliberately folds into "modified"/"vegetation_changed"
# plus a free-text note rather than earning its own value -- "do not expose
# all of these unless useful."
PlaceFeatureChangeEventType = Literal[
    "added",
    "removed",
    "moved",
    "modified",
    "replenished",
    "food_changed",
    "vegetation_changed",
    "other",
]
PLACE_FEATURE_CHANGE_EVENT_TYPES: tuple[PlaceFeatureChangeEventType, ...] = (
    "added",
    "removed",
    "moved",
    "modified",
    "replenished",
    "food_changed",
    "vegetation_changed",
    "other",
)

# Change-event types whose recording also updates the Feature's own
# current-state row, in the same transaction (Phase 5's "dual-write, not
# event sourcing" -- see "Feature state vs change history" in the contract
# doc). Every other event type is timeline-only and never mutates
# `PlaceFeatureModel`. A plain `frozenset`, not a mapping to a specific
# field, because the repository layer already knows exactly which field
# each of these two types touches; this constant exists so a caller can
# cheaply ask "could recording/editing/deleting this event change the
# Feature's current state" without duplicating the event-type list.
DERIVED_STATE_EVENT_TYPES: frozenset[str] = frozenset({"removed", "food_changed"})


__all__ = [
    "FEATURE_INFORMATION_CLASS",
    "FEATURE_PROVENANCE_MANUAL_ENTRY",
    "PlaceFeatureType",
    "PLACE_FEATURE_TYPES",
    "PlaceFeatureChangeEventType",
    "PLACE_FEATURE_CHANGE_EVENT_TYPES",
    "DERIVED_STATE_EVENT_TYPES",
]
