#!/usr/bin/env python3
"""Identification Eligibility + Abstention v1 -- empirical benchmark.

Runs the real, production `mockingbird.species.identification_eligibility`
policy against a bounded cohort of *real*, already-recovered MockingBird
field evidence -- never synthetic/invented scores -- and reports coverage,
correctness, and abstention behavior per milestone step 19 ("run the
candidate eligibility/abstention policy against the bounded real evaluation
cohort... before finalizing the production policy").

Every numeric fact below is copied from an already-committed source, cited
inline, exactly like `tests/test_human_background_admission_hard_negative_
2026_08_20.py` already does for Visits 139/140. `data/` is gitignored
project-wide (per every prior field-acceptance session's own convention), so
this script never reads from it at run time -- every real number is a
literal here, not a re-derived path into gitignored evidence.

Cohort composition:

- **A -- mandatory hard negatives**: Visits 139/140 (person + dog, real
  MDv5 `animal`-class false detection), from
  docs/person-background-false-positive-attribution-v1-report.md S2-3/S9.
- **B -- mandatory difficult cases**: the real 2026-08-11/2026-08-14
  full-frame "Red-bellied Woodpecker bias" cohort (8 real Visits,
  011-018), from data/field-acceptance/2026-08-14-subject-centric-
  species-crop/FINAL-REPORT.md S5 (the "Full-frame" column -- today's/
  historical real production classification path for these Visits, before
  Same-Frame Species Evidence v1 existed). These are this milestone's
  concrete "apparent nuthatch" difficult positives: real evidence,
  confidently wrong or ambiguous full-frame answers.
- **B-supplement -- illustrative positive control**: the *same* 8 Visits'
  paired diagnostic subject-crop reproduction (4/8 visually confirmed to
  actually contain the bird -- House Finch), same source, S4/S5. Explicitly
  labeled "unsafe/exploratory" by that report (stale-box crop, never wired
  into production) -- included only to show what a *good* subject crop's
  score distribution looks like on the same real photographs, not as a
  live-production claim.
- **C -- positive controls**: one real authoritative reviewed Visit
  (Northern Cardinal, local dev DB `visit-motion-005`), one real production
  same-frame Visit (`visit-observation-candidate-019`, House Finch 93.7%,
  data/field-acceptance/2026-08-14-same-frame-species-evidence/
  FINAL-REPORT.md), and 7 real reviewed-real Visits from the independently
  re-adjudicated 70-Visit cohort (`data/evaluations/scene-confusor-
  suspicion-v1/`, `ground_truth.py` + `70-visit-cohort-compact-
  summary.jsonl`) -- includes a real Carolina Wren, satisfying this
  milestone's requested species diversity.
- **D -- real background/false-positive cohort**: the same 70-Visit
  cohort's 13 `GROUND_TRUTH=False` Visits that nonetheless received a real
  BioCLIP suggestion -- the residual this policy is measured against, not
  assumed solved.

Known, disclosed data limitations (see the milestone final report for the
full discussion): the 70-Visit cohort's compact summary does not retain
per-suggestion `alternatives`, so cohort C/D entries carry only a top-1
score; this script represents them as a single-candidate ranking, which
makes `evaluate_classification_abstention`'s margin term fall back to the
score itself (a conservative, not favorable, substitution -- see that
function's docstring). Visit 019/idx=19 is deliberately flagged: Same-Frame
Species Evidence v1's own direct visual review (2026-08-14) found a real
bird in that crop, while the independent 2026-08-19 re-adjudication marked
the same Visit `GROUND_TRUTH=False` -- a genuine disagreement between two
independent human reviews, preserved rather than silently resolved one way.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from mockingbird.species.identification_eligibility import (
    ClassifierInputTier,
    ScoredCandidate,
    evaluate_classification_abstention,
    evaluate_identification_eligibility,
)


@dataclass(frozen=True)
class CohortCase:
    cohort: str
    case_id: str
    tier: ClassifierInputTier
    candidates: tuple[ScoredCandidate, ...]
    expect_suggest: bool | None  # None = report-only, not a hard pass/fail
    note: str


def _c(label: str, score: float) -> ScoredCandidate:
    return ScoredCandidate(label=label, score=score)


COHORT_A_HARD_NEGATIVES: tuple[CohortCase, ...] = (
    CohortCase(
        "A", "visit-139-person-dog", "subject_focused",
        (_c("brown_thrasher", 0.5275),),
        expect_suggest=False,
        note="Real person+dog passage, classifier_same_frame crop; "
        "person-background-false-positive-attribution-v1-report.md S2.",
    ),
    CohortCase(
        "A", "visit-140-person-dog", "subject_focused",
        (_c("red_bellied_woodpecker", 0.5986),),
        expect_suggest=False,
        note="Same real passage, second tracklet, highest max_confidence "
        "(0.877) of any Visit real or false in the session; same source.",
    ),
)

# Real full-frame classification (today's fallback path, and the exact
# historical path for these archived Visits) -- FINAL-REPORT.md S5, the
# "Full-frame top-3 (A, current behavior)" column.
COHORT_B_DIFFICULT_FULL_FRAME: tuple[CohortCase, ...] = (
    CohortCase("B", "visit-011-full-frame", "full_frame",
               (_c("red_bellied_woodpecker", 0.796), _c("downy_woodpecker", 0.068)),
               expect_suggest=False, note="Crop diagnostic: bird barely in frame (sliver only)."),
    CohortCase("B", "visit-012-full-frame", "full_frame",
               (_c("red_bellied_woodpecker", 0.817), _c("carolina_chickadee", 0.066)),
               expect_suggest=False, note="Crop diagnostic: bird barely in frame (sliver only)."),
    CohortCase("B", "visit-013-full-frame", "full_frame",
               (_c("red_bellied_woodpecker", 0.616), _c("carolina_chickadee", 0.129)),
               expect_suggest=False, note="Crop diagnostic confirmed real bird = House Finch; full-frame answer wrong."),
    CohortCase("B", "visit-014-full-frame", "full_frame",
               (_c("tufted_titmouse", 0.369), _c("red_bellied_woodpecker", 0.269)),
               expect_suggest=False, note="Crop diagnostic confirmed real bird = House Finch; full-frame answer wrong (low score+margin)."),
    CohortCase("B", "visit-015-full-frame", "full_frame",
               (_c("red_bellied_woodpecker", 0.529), _c("carolina_chickadee", 0.195)),
               expect_suggest=False, note="Crop diagnostic: bare tree bark, no bird anywhere."),
    CohortCase("B", "visit-016-full-frame", "full_frame",
               (_c("red_bellied_woodpecker", 0.645), _c("tufted_titmouse", 0.130)),
               expect_suggest=False, note="Crop diagnostic confirmed real bird = House Finch; full-frame answer wrong."),
    CohortCase("B", "visit-017-full-frame", "full_frame",
               (_c("red_bellied_woodpecker", 0.779), _c("gray_catbird", 0.047)),
               expect_suggest=False, note="Crop diagnostic confirmed real bird = House Finch; full-frame answer wrong."),
    CohortCase("B", "visit-018-full-frame", "full_frame",
               (_c("red_bellied_woodpecker", 0.338), _c("carolina_chickadee", 0.274)),
               expect_suggest=False, note="Crop diagnostic: empty feeder, no bird visible."),
)

# Same 8 real photographs, diagnostic subject-crop reproduction -- FINAL-
# REPORT.md S5 "Diagnostic subject-crop" column, the 4/8 visually-confirmed-
# correct cases only. Illustrative supplement, not a live-production claim.
COHORT_B_SUPPLEMENT_CLEAN_CROP: tuple[CohortCase, ...] = (
    CohortCase("B-supplement", "visit-013-diagnostic-crop", "subject_focused",
               (_c("house_finch", 0.998), _c("eastern_bluebird", 0.0007)),
               expect_suggest=True, note="Diagnostic/exploratory crop, visually confirmed correct."),
    CohortCase("B-supplement", "visit-014-diagnostic-crop", "subject_focused",
               (_c("house_finch", 0.997), _c("eastern_bluebird", 0.0017)),
               expect_suggest=True, note="Diagnostic/exploratory crop, visually confirmed correct."),
    CohortCase("B-supplement", "visit-016-diagnostic-crop", "subject_focused",
               (_c("house_finch", 0.999), _c("eastern_bluebird", 0.0005)),
               expect_suggest=True, note="Diagnostic/exploratory crop, visually confirmed correct."),
    CohortCase("B-supplement", "visit-017-diagnostic-crop", "subject_focused",
               (_c("house_finch", 0.925), _c("northern_cardinal", 0.043)),
               expect_suggest=True, note="Diagnostic/exploratory crop, visually confirmed correct."),
)

COHORT_C_POSITIVE_CONTROLS: tuple[CohortCase, ...] = (
    CohortCase(
        "C", "visit-motion-005-cardinal", "subject_focused",
        (_c("northern_cardinal", 0.8906447291374207), _c("brown_thrasher", 0.06705698370933533)),
        expect_suggest=True,
        note="Real authoritative reviewed Visit (local dev DB), megadetector crop_source.",
    ),
    CohortCase(
        "C", "visit-observation-candidate-019-house-finch", "subject_focused",
        (_c("house_finch", 0.9374827742576599),),
        expect_suggest=True,
        note="Real production same-frame capture; Same-Frame Species Evidence v1's own "
        "direct visual review confirmed the bird. NOTE: the independent 2026-08-19 "
        "re-adjudication (ground_truth.py, idx=19) instead marked this Visit False -- "
        "a genuine disagreement between two real human reviews, disclosed not resolved.",
    ),
    # Real reviewed-real Visits from the independently re-adjudicated 70-Visit cohort
    # (ground_truth.py GROUND_TRUTH[idx] is True), single-candidate (compact summary
    # does not retain alternatives -- margin falls back to score, conservatively).
    CohortCase("C", "visit-observation-candidate-021", "subject_focused", (_c("house_finch", 0.9793668389320374),), True, "70-cohort real, idx=21."),
    CohortCase("C", "visit-observation-candidate-023", "subject_focused", (_c("house_finch", 0.9340747594833374),), True, "70-cohort real, idx=23."),
    CohortCase("C", "visit-observation-candidate-025", "subject_focused", (_c("house_finch", 0.9615039825439453),), True, "70-cohort real, idx=25."),
    CohortCase("C", "visit-observation-candidate-033", "subject_focused", (_c("house_finch", 0.783930778503418),), True, "70-cohort real, idx=33 -- lowest real score in cohort."),
    CohortCase("C", "visit-observation-candidate-035", "subject_focused", (_c("house_finch", 0.9624731540679932),), True, "70-cohort real, idx=35."),
    CohortCase("C", "visit-observation-candidate-037", "subject_focused", (_c("house_finch", 0.9526965022087097),), True, "70-cohort real, idx=37."),
    CohortCase("C", "visit-observation-candidate-038-wren", "subject_focused", (_c("carolina_wren", 0.9054259061813354),), True, "70-cohort real, idx=38 -- real Carolina Wren."),
)

# 70-Visit cohort's real GROUND_TRUTH=False Visits that nonetheless received a
# real BioCLIP suggestion -- the residual this policy is measured against, not
# assumed solved. expect_suggest=None: reported, not hard-asserted, because
# score-only separation from real positives is this policy's known, disclosed
# limit for genuinely confusable static background regions (see final report).
COHORT_D_REAL_BACKGROUND: tuple[CohortCase, ...] = (
    CohortCase("D", "visit-observation-candidate-019-background-view", "subject_focused", (_c("house_finch", 0.9374827742576599),), None, "idx=19 -- see the Visit-019 disclosure above."),
    CohortCase("D", "visit-observation-candidate-020", "subject_focused", (_c("house_finch", 0.4518977999687195),), None, "idx=20."),
    CohortCase("D", "visit-observation-candidate-022", "subject_focused", (_c("house_finch", 0.9910910129547119),), None, "idx=22."),
    CohortCase("D", "visit-observation-candidate-024", "subject_focused", (_c("house_finch", 0.968093991279602),), None, "idx=24."),
    CohortCase("D", "visit-observation-candidate-026", "subject_focused", (_c("house_finch", 0.9818552732467651),), None, "idx=26."),
    CohortCase("D", "visit-observation-candidate-027", "subject_focused", (_c("house_finch", 0.9514702558517456),), None, "idx=27."),
    CohortCase("D", "visit-observation-candidate-028", "subject_focused", (_c("carolina_chickadee", 0.5980521440505981),), None, "idx=28."),
    CohortCase("D", "visit-observation-candidate-029", "subject_focused", (_c("tufted_titmouse", 0.23434536159038544),), None, "idx=29."),
    CohortCase("D", "visit-observation-candidate-030", "subject_focused", (_c("tufted_titmouse", 0.20652459561824799),), None, "idx=30."),
    CohortCase("D", "visit-observation-candidate-031", "subject_focused", (_c("northern_mockingbird", 0.2737233638763428),), None, "idx=31."),
    CohortCase("D", "visit-observation-candidate-032", "subject_focused", (_c("house_finch", 0.9515441656112671),), None, "idx=32."),
    CohortCase("D", "visit-observation-candidate-034", "subject_focused", (_c("tufted_titmouse", 0.3861255347728729),), None, "idx=34."),
    CohortCase("D", "visit-observation-candidate-036", "subject_focused", (_c("mourning_dove", 0.9949748516082764),), None, "idx=36."),
)

ALL_COHORTS: tuple[tuple[str, tuple[CohortCase, ...]], ...] = (
    ("A -- mandatory hard negatives (Visits 139/140)", COHORT_A_HARD_NEGATIVES),
    ("B -- mandatory difficult cases (full-frame woodpecker/titmouse bias)", COHORT_B_DIFFICULT_FULL_FRAME),
    ("B-supplement -- illustrative clean-crop positive control", COHORT_B_SUPPLEMENT_CLEAN_CROP),
    ("C -- positive controls (real reviewed/production suggestions)", COHORT_C_POSITIVE_CONTROLS),
    ("D -- real background cohort (residual measurement, not hard-asserted)", COHORT_D_REAL_BACKGROUND),
)


def run_benchmark() -> dict:
    report: dict = {"cohorts": {}, "mandatory_failures": []}
    for cohort_label, cases in ALL_COHORTS:
        results = []
        for case in cases:
            decision = evaluate_classification_abstention(case.candidates, tier=case.tier)
            actual_suggest = not decision.abstained
            passed = case.expect_suggest is None or actual_suggest == case.expect_suggest
            if case.expect_suggest is not None and not passed:
                report["mandatory_failures"].append(case.case_id)
            results.append(
                {
                    "case_id": case.case_id,
                    "tier": case.tier,
                    "top1_label": decision.top1_label,
                    "top1_score": decision.top1_score,
                    "margin": decision.margin,
                    "abstained": decision.abstained,
                    "reason_code": decision.reason_code,
                    "expected_suggest": case.expect_suggest,
                    "actual_suggest": actual_suggest,
                    "pass": passed,
                    "note": case.note,
                }
            )
        n = len(results)
        n_suggested = sum(1 for r in results if r["actual_suggest"])
        report["cohorts"][cohort_label] = {
            "n": n,
            "n_suggested": n_suggested,
            "n_abstained": n - n_suggested,
            "suggestion_rate": round(n_suggested / n, 3) if n else None,
            "cases": results,
        }

    # Stage-1 evidence-eligibility floor: no real case in this cohort exercises
    # it (every real crop/frame recovered so far is well above the structural
    # floor -- see the final report), so this is exercised with an honestly
    # labeled synthetic-but-architecturally-real case: a crop smaller than
    # BioCLIP's own 224x224 internal resize would ever produce real signal for.
    degenerate = evaluate_identification_eligibility(classifier_input_width=6, classifier_input_height=6)
    normal = evaluate_identification_eligibility(classifier_input_width=180, classifier_input_height=140)
    report["eligibility_floor_check"] = {
        "degenerate_6x6px": {"eligible": degenerate.eligible, "reason_code": degenerate.reason_code},
        "normal_180x140px": {"eligible": normal.eligible, "reason_code": normal.reason_code},
    }
    return report


def render_report(report: dict) -> str:
    lines = ["# Identification Eligibility + Abstention v1 -- Benchmark Report", ""]
    for cohort_label, summary in report["cohorts"].items():
        lines.append(f"## {cohort_label}")
        lines.append(
            f"n={summary['n']}  suggested={summary['n_suggested']}  "
            f"abstained={summary['n_abstained']}  suggestion_rate={summary['suggestion_rate']}"
        )
        for case in summary["cases"]:
            mark = "PASS" if case["pass"] else "**FAIL**"
            expected = case["expected_suggest"]
            expected_text = "report-only" if expected is None else ("suggest" if expected else "abstain")
            lines.append(
                f"  [{mark}] {case['case_id']}: top1={case['top1_label']!r} "
                f"score={case['top1_score']:.4f} margin={case['margin']:.4f} tier={case['tier']} "
                f"-> {'suggest' if case['actual_suggest'] else 'abstain'}"
                f" (expected={expected_text}, reason={case['reason_code']})"
            )
        lines.append("")
    lines.append("## Stage-1 evidence-eligibility floor check")
    lines.append(json.dumps(report["eligibility_floor_check"], indent=2))
    lines.append("")
    if report["mandatory_failures"]:
        lines.append(f"MANDATORY CASE FAILURES: {report['mandatory_failures']}")
    else:
        lines.append("All mandatory (hard-asserted) cases passed.")
    return "\n".join(lines)


if __name__ == "__main__":
    result = run_benchmark()
    print(render_report(result))
    if result["mandatory_failures"]:
        raise SystemExit(1)
