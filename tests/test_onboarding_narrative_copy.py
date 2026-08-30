"""Lane C Sparse-State Honesty & First-Hour Narrative Closure v1: Defect B.

`web/src/components/OnboardingWizard.tsx` had two stale paragraphs telling
first-time users that a sighting "appears in your Review Queue for you to
confirm" (Welcome step) or "lands in Review Queue" (post-camera-setup
Observe step) -- both predating the shipped review-optional design (see
product-doctrine.md "Measured, Inferred, and Reviewed": Inferred output
must be useful immediately, without requiring human confirmation first;
and "Core flow": Observe -> Discover -> Understand -> Confirm -> Remember
-> Improve, where discovery happens in Today/Bird Log/Visit detail, not
only in a review-first queue).

This is a lightweight static-source-text regression, not a new frontend
unit-test framework, matching this repository's own established approach
for this class of copy (`web/e2e/onboarding.spec.ts` already asserts on
rendered Welcome-step body text the same way). It exists specifically to
catch the Observe-step paragraph too: reaching that step in a real browser
requires completing the full guided camera-pairing flow embedded in the
wizard, which is disproportionate machinery for two paragraphs of copy --
see the milestone's own governing brief, "Do not build a frontend
unit-test framework solely for two paragraphs."
"""

from __future__ import annotations

import re
from pathlib import Path

_ONBOARDING_WIZARD_PATH = (
    Path(__file__).resolve().parent.parent / "web" / "src" / "components" / "OnboardingWizard.tsx"
)


def _source() -> str:
    """JSX text wraps across source lines at the formatter's discretion, so
    checks below normalize whitespace rather than matching raw source
    (which would be brittle against a harmless reflow)."""

    return re.sub(r"\s+", " ", _ONBOARDING_WIZARD_PATH.read_text(encoding="utf-8"))


def test_onboarding_no_longer_frames_review_queue_as_the_normal_discovery_destination() -> None:
    source = _source()

    # The two stale phrasings this milestone closes -- neither may silently
    # return.
    assert "appears in your Review Queue for you to confirm" not in source
    assert "Anything worth a look lands in Review Queue" not in source
    assert "lands in Review Queue" not in source


def test_onboarding_names_the_real_discovery_surfaces() -> None:
    source = _source()

    # Both rewritten paragraphs point first-time users at the actual
    # discovery surfaces (Today, Bird Log), matching canonical terminology
    # already established on those pages (BirdLogPage.tsx's "Likely
    # sightings" / "Not yet confirmed"; VisitDetailPage.tsx's Likely/
    # Confirmed tone badges) rather than inventing new vocabulary.
    assert "Today and Bird Log" in source
    assert source.count("Today and Bird Log") >= 2


def test_onboarding_still_discloses_review_queue_as_available_not_required() -> None:
    source = _source()

    # Review Queue remains a real, useful, named destination for deliberate
    # batch review -- just not framed as where sightings "land" or
    # "appear." This guards against over-correcting to zero mention, which
    # would leave a first-time user unable to find it later.
    assert "Review Queue" in source
    assert "any time you want to work through suggestions" in source
