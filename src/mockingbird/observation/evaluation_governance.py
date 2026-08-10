"""Detection Quality Accounting v1 -- reviewed-truth / evaluation-set
governance (see docs/detection-quality-accounting-contract.md).

The truth boundary (product-doctrine.md) applies to benchmark/evaluation
data exactly as it applies to product data: a detector benchmark's own
manifests already distinguish reviewed truth from unreviewed input (see
docs/detector-calibration-benchmark-contract.md's `animal_present`/
`scorable` fields), but nothing before this module named
the distinction this milestone needs explicitly: an agent's own visual
inspection of a candidate Visit -- however carefully done, however correct
-- is not the same thing as a human Review Decision, and must never be
silently promoted into reviewed truth eligible for evaluation or training
(see "Explicit user correction creates dataset-grade ReviewLabel truth" in
AGENTS.md and "Reviewed truth may become valuable training data... Dataset
eligibility is a separate, governed decision" in product-doctrine.md).

This module is intentionally small: one status vocabulary, one manifest
shape, and the loader/validators needed to keep evaluation code honest about
which examples it is allowed to treat as ground truth. It does not itself
compute metrics (see `mockingbird.observation.admission_policy`) and does
not open the product database -- reviewed truth here means "the repository
already has evidence this example was human-reviewed," never a live
ReviewLabel query.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

MANIFEST_SCHEMA_VERSION = 1

EvaluationExampleStatus = Literal[
    # A human reviewer explicitly confirmed this example's ground truth
    # (for example the Stage 6.17 reviewed-Visit-truth manifests, or a
    # `detector-calibration-benchmark` cohort's own reviewed `animal_
    # present`/box annotations). The only status eligible for evaluation
    # metrics that claim to measure precision/recall against truth, and the
    # only status a future dataset-eligibility decision may ever consider
    # (see "Models earn trust; they do not inherit it" /
    # custom-bird-classifier-dataset-plan.md -- eligibility itself remains a
    # separate, further-governed decision even for `reviewed_truth` rows).
    "reviewed_truth",
    # A genuinely useful example for qualitative diagnosis (a known-hard
    # confusor, a documented failure case) that has NOT been through human
    # Review Decision -- most commonly an agent's own visual inspection of
    # a candidate Visit. Valuable, but never a precision/recall denominator
    # and never training-eligible.
    "diagnostic_only",
    # A raw, unreviewed, machine-produced candidate/proposal with no
    # asserted truth value at all -- present in a manifest only for
    # completeness/counting (e.g. "how many unreviewed candidates exist"),
    # never for any accuracy claim.
    "auto_generated_unreviewed",
]

TRAINING_ELIGIBLE_STATUSES: frozenset[EvaluationExampleStatus] = frozenset({"reviewed_truth"})
EVALUATION_METRIC_ELIGIBLE_STATUSES: frozenset[EvaluationExampleStatus] = frozenset({"reviewed_truth"})


class EvaluationGovernanceError(ValueError):
    """A bounded evaluation-manifest validation failure code."""


# Visit Continuity / Provisional Admission Fix v1, Part 7 audit (see
# docs/tracklet-visit-assembly-contract.md and the fresh-cohort field
# report's own governance note): a defense-in-depth check, not the only
# safeguard -- the load-bearing rule is still procedural ("only a script a
# human runs, over material a human actually reviewed, may ever construct a
# `reviewed_truth` example"). But `reviewed_by`/`source` are free text, and
# this codebase already has a real, established convention of writing an
# honest self-disclosure into exactly this kind of field when an agent's own
# visual inspection produced the record (see `DIAGNOSTIC_EXAMPLES` in
# scripts/run_detection_quality_accounting.py: `source="agent-visual-
# inspection-2026-08-10"`; and the real `ReviewLabel.notes` disclosure
# `"[AGENT VISUAL REVIEW ... not independently human-confirmed]"` the
# 2026-08-10 fresh cohort wrote through the real product review path).
# Catching that same honest disclosure here means a future manifest-
# generation script that carelessly (never maliciously) copies an agent's
# own disclosure straight into `reviewed_by`/`source` while also claiming
# `status="reviewed_truth"` fails loudly at construction time instead of
# silently entering a training/evaluation corpus. Bounded and explicit by
# design -- this is not a content-moderation classifier, only a known,
# documented vocabulary already used *by this codebase's own convention*.
_NON_HUMAN_REVIEW_MARKERS: tuple[str, ...] = (
    "agent", "claude", "language model", "llm", "autonomous", "chatbot",
    "ai visual", "ai-visual", "machine visual", "model visual",
)


def _discloses_non_human_review(*texts: str | None) -> bool:
    for text in texts:
        if not text:
            continue
        lowered = text.lower()
        if any(marker in lowered for marker in _NON_HUMAN_REVIEW_MARKERS):
            return True
    return False


@dataclass(frozen=True)
class EvaluationExample:
    """One governed entry: a proposal/Visit/frame this evaluation corpus
    knows about, plus its honest review status and provenance -- never the
    example's own pixel/media content (that stays wherever it already lives,
    for example a field-acceptance replay export or the product database).
    """

    example_id: str
    status: EvaluationExampleStatus
    source: str
    description: str
    # A pointer into where this fact actually came from -- a manifest
    # fingerprint, a `proposal_key`, a file path relative to the repository
    # root, or similar. Free text by design (this module does not resolve
    # or verify it); it exists so a later reader can trace the claim back
    # to its origin instead of trusting this manifest blindly.
    provenance_ref: str | None = None
    reviewed_by: str | None = None
    reviewed_at_iso: str | None = None

    def __post_init__(self) -> None:
        if not self.example_id.strip() or not self.source.strip() or not self.description.strip():
            raise EvaluationGovernanceError("evaluation_example_missing_required_text")
        if self.status == "reviewed_truth" and not (self.reviewed_by and self.reviewed_by.strip()):
            # The one load-bearing rule this module exists to enforce:
            # nothing may claim `reviewed_truth` without naming who/what
            # reviewed it. An agent's own visual inspection is honestly
            # `diagnostic_only`, never this.
            raise EvaluationGovernanceError("reviewed_truth_requires_reviewer_identity")
        if self.status == "reviewed_truth" and _discloses_non_human_review(self.reviewed_by, self.source):
            # Defense in depth (see `_NON_HUMAN_REVIEW_MARKERS`): the
            # reviewer-identity text itself honestly says this was not a
            # human. Language-model inspection must never silently become
            # observational authority or training truth (product-doctrine.md
            # "the truth boundary") -- this is honestly `diagnostic_only`.
            raise EvaluationGovernanceError("reviewed_truth_requires_human_reviewer")

    @property
    def training_eligible(self) -> bool:
        return self.status in TRAINING_ELIGIBLE_STATUSES

    @property
    def evaluation_metric_eligible(self) -> bool:
        return self.status in EVALUATION_METRIC_ELIGIBLE_STATUSES


@dataclass(frozen=True)
class EvaluationManifest:
    schema_version: int
    examples: tuple[EvaluationExample, ...]

    def __post_init__(self) -> None:
        if self.schema_version != MANIFEST_SCHEMA_VERSION:
            raise EvaluationGovernanceError("unsupported_evaluation_manifest_version")
        ids = [item.example_id for item in self.examples]
        if len(ids) != len(set(ids)):
            raise EvaluationGovernanceError("duplicate_evaluation_example_id")

    def by_status(self, status: EvaluationExampleStatus) -> tuple[EvaluationExample, ...]:
        return tuple(item for item in self.examples if item.status == status)

    @property
    def reviewed_truth(self) -> tuple[EvaluationExample, ...]:
        return self.by_status("reviewed_truth")

    @property
    def diagnostic_only(self) -> tuple[EvaluationExample, ...]:
        return self.by_status("diagnostic_only")

    @property
    def counts_by_status(self) -> dict[str, int]:
        return {
            status: len(self.by_status(status))
            for status in ("reviewed_truth", "diagnostic_only", "auto_generated_unreviewed")
        }


def require_evaluation_metric_eligible(examples: tuple[EvaluationExample, ...]) -> tuple[EvaluationExample, ...]:
    """Filter to only the examples honestly eligible to feed a precision/
    recall-style metric, dropping (never silently promoting) anything else.
    A caller computing a metric should call this explicitly rather than
    trusting an unfiltered example list -- see "Do not print misleading
    precision/recall numbers when the denominator is not actually known" in
    this milestone's own instructions."""
    return tuple(item for item in examples if item.evaluation_metric_eligible)


def _example_from_dict(value: dict[str, object]) -> EvaluationExample:
    try:
        return EvaluationExample(
            example_id=str(value["example_id"]),
            status=value["status"],  # type: ignore[arg-type]
            source=str(value["source"]),
            description=str(value["description"]),
            provenance_ref=(str(value["provenance_ref"]) if value.get("provenance_ref") is not None else None),
            reviewed_by=(str(value["reviewed_by"]) if value.get("reviewed_by") is not None else None),
            reviewed_at_iso=(str(value["reviewed_at_iso"]) if value.get("reviewed_at_iso") is not None else None),
        )
    except KeyError as error:
        raise EvaluationGovernanceError("evaluation_example_missing_field") from error


def load_evaluation_manifest(path: Path) -> EvaluationManifest:
    """Load a local, caller-owned evaluation-governance manifest. This is a
    trusted local repository/diagnostic file, not user- or network-facing
    input -- unlike the benchmark manifest loaders under `*_io.py`, no path-
    traversal/SSRF hardening is needed here, only structural validation."""
    import json

    if path.is_symlink() or not path.is_file():
        raise EvaluationGovernanceError("invalid_evaluation_manifest_path")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise EvaluationGovernanceError("invalid_evaluation_manifest_json") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("examples"), list):
        raise EvaluationGovernanceError("invalid_evaluation_manifest_shape")
    examples = tuple(_example_from_dict(item) for item in payload["examples"] if isinstance(item, dict))
    if len(examples) != len(payload["examples"]):
        raise EvaluationGovernanceError("invalid_evaluation_manifest_shape")
    return EvaluationManifest(schema_version=payload.get("schema_version", MANIFEST_SCHEMA_VERSION), examples=examples)
