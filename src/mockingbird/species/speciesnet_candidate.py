"""Pure, benchmark-only comparison logic for the SpeciesNet challenger model.

Never imported by production code (``mockingbird.repository``/``mockingbird.api``).
SpeciesNet was deliberately deferred (``docs/speciesnet-adapter-boundary-plan.md``,
Phase 9K) pending model-weight license clarity -- "App startup can remain clean
only if MockingBird uses optional dependency, lazy import" and "model-weight
license unresolved... not confirmed from static Kaggle access." That specific
blocker is now resolved for the Detection & Species Model Benchmark / Promotion
v1 milestone: the real downloaded ``google/speciesnet`` v4.0.3a Kaggle artifact's
own bundled ``README.md`` carries an explicit frontmatter declaration
(``license: apache-2.0``), independently verified by direct inspection rather
than assumed. This module supplies the deterministic, provider-neutral
comparison math a real candidate benchmark needs -- mirroring
``mockingbird.observation.detector_comparison``'s pure/impure split for the
species side: this module is pure (no filesystem, network, or model-runtime
import; every function operates on already-computed SpeciesNet/BioCLIP
prediction data), while ``scripts/benchmark_speciesnet_candidate.py`` supplies
the real local-model inference. Like every candidate-comparison tool in this
repository, nothing here creates truth, mutates a production threshold, or
selects a runtime -- it only characterizes evidence for a separate,
human-legible promotion decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SPECIESNET_TAXONOMY_FIELD_COUNT = 7
TaxonomicAgreement = Literal[
    "exact_species", "same_genus", "same_family", "same_order", "different", "no_expected_taxon"
]


class SpeciesNetCandidateError(ValueError):
    """A bounded validation failure at the SpeciesNet candidate-comparison boundary."""


@dataclass(frozen=True)
class SpeciesNetTaxon:
    """One parsed SpeciesNet label row.

    Real SpeciesNet (v4.0.3a) labels are semicolon-delimited
    ``uuid;class;order;family;genus;species;common_name`` rows -- confirmed
    directly against the downloaded label file, not assumed from documentation.
    Any taxonomic field may be empty (a genus-, family-, or order-level rollup
    row, e.g. ``";;;;;;blank"`` or ``"...;canis;;canis species"``); an empty
    field means "not resolved to this level," never "matches everything."
    """

    uuid: str
    class_: str
    order: str
    family: str
    genus: str
    species: str
    common_name: str


def parse_speciesnet_label(raw_label: str) -> SpeciesNetTaxon:
    """Parse one raw SpeciesNet taxonomy label row into its seven real fields.

    Fails closed on a malformed row rather than guessing a partial split --
    a benchmark comparison must not silently score a corrupted label.
    """
    parts = raw_label.split(";")
    if len(parts) != SPECIESNET_TAXONOMY_FIELD_COUNT:
        raise SpeciesNetCandidateError(
            f"malformed_speciesnet_label: expected {SPECIESNET_TAXONOMY_FIELD_COUNT} "
            f"';'-delimited fields, got {len(parts)}: {raw_label!r}"
        )
    uuid, class_, order, family, genus, species, common_name = parts
    return SpeciesNetTaxon(uuid, class_, order, family, genus, species, common_name)


@dataclass(frozen=True)
class SpeciesNetPrediction:
    """One already-computed SpeciesNet classifier result for one real image.

    Mirrors ``speciesnet.classifier.SpeciesNetClassifier.predict``'s real
    output shape (top-5 raw label rows plus matching softmax scores,
    highest-scoring first) without importing that runtime here.
    """

    case_id: str
    top5_labels: tuple[str, ...]
    top5_scores: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.top5_labels) != len(self.top5_scores):
            raise SpeciesNetCandidateError("speciesnet_prediction_label_score_length_mismatch")
        if not self.top5_labels:
            raise SpeciesNetCandidateError("speciesnet_prediction_empty")

    @property
    def top1_label(self) -> str:
        return self.top5_labels[0]

    @property
    def top1_score(self) -> float:
        return self.top5_scores[0]

    @property
    def top1_taxon(self) -> SpeciesNetTaxon:
        return parse_speciesnet_label(self.top1_label)

    @property
    def top1_common_name(self) -> str:
        return self.top1_taxon.common_name

    def top5_taxa(self) -> tuple[SpeciesNetTaxon, ...]:
        return tuple(parse_speciesnet_label(label) for label in self.top5_labels)


def classify_taxonomic_agreement(
    predicted: SpeciesNetTaxon | None, expected: SpeciesNetTaxon | None
) -> TaxonomicAgreement:
    """Compare a SpeciesNet prediction against a known-correct taxon.

    Coarser than a flat label match on purpose: SpeciesNet's real taxonomy
    legitimately rolls a genuinely-uncertain prediction up to genus/family/
    order rather than forcing a guessed species (unlike BioCLIP's closed,
    always-species-level 14-label pack) -- an honest genus-level answer on a
    real photo is a materially different, better outcome than a wrong
    species guess at the same confidence, and this function is what lets a
    benchmark say so instead of scoring both as flatly "wrong."
    """
    if expected is None:
        return "no_expected_taxon"
    if predicted is None:
        return "different"
    if predicted.genus and predicted.species and (predicted.genus, predicted.species) == (
        expected.genus,
        expected.species,
    ):
        return "exact_species"
    if predicted.genus and predicted.genus == expected.genus:
        return "same_genus"
    if predicted.family and predicted.family == expected.family:
        return "same_family"
    if predicted.order and predicted.order == expected.order:
        return "same_order"
    return "different"


# MockingBird's own closed "Backyard Core v1" candidate pack
# (``BUILTIN_SPECIES_CANDIDATE_TAXONOMY_IDS`` in product_repository.py), mapped
# to the real SpeciesNet v4.0.3a taxonomy row for the same species where one
# exists at species level -- verified directly against the downloaded label
# file, not fabricated. Only the taxa this milestone's real evaluation cohort
# actually exercises are populated; extend deliberately, with the same direct
# verification, rather than guessing a UUID for an unverified row.
KNOWN_BACKYARD_TAXA: dict[str, SpeciesNetTaxon] = {
    "house_finch": parse_speciesnet_label(
        "97969dd0-97f3-4562-af1c-ac1bea43badc;aves;passeriformes;fringillidae;"
        "haemorhous;mexicanus;house finch"
    ),
    "northern_cardinal": parse_speciesnet_label(
        "9f87fb6d-be1d-43b4-a144-3d4750bdf6de;aves;passeriformes;cardinalidae;"
        "cardinalis;cardinalis;northern cardinal"
    ),
    "red_bellied_woodpecker": parse_speciesnet_label(
        "941db4fe-fbf3-434f-bfb1-f765009d5e7e;aves;piciformes;picidae;"
        "melanerpes;carolinus;red-bellied woodpecker"
    ),
    "tufted_titmouse": parse_speciesnet_label(
        "2ceebb87-7f19-4aba-a1e0-4a8bcf242343;aves;passeriformes;paridae;"
        "baeolophus;bicolor;tufted titmouse"
    ),
    # No exact "Carolina Wren" (Thryothorus ludovicianus) species-level row
    # exists in the real v4.0.3a taxonomy -- only a genus-level rollup. This
    # is real, disclosed taxonomy-coverage evidence (SpeciesNet's much larger
    # label space is not a strict superset of MockingBird's 14), not a
    # placeholder; `species` is deliberately left empty so
    # `classify_taxonomic_agreement` can never report a false
    # `exact_species` match against it.
    "carolina_wren": parse_speciesnet_label(
        "c8c36fae-cd8d-4ad4-b1b5-c3554dd47088;aves;passeriformes;troglodytidae;"
        "thryothorus;;thryothorus species"
    ),
    # Real, structural non-bird classes this checkpoint supports natively --
    # BioCLIP's 14-species bird-only pack has no equivalent for any of these;
    # they exist here so a hard-negative benchmark case (e.g. a person/dog
    # Visit) can express its expected taxon precisely instead of leaving it
    # unmapped.
    "human": parse_speciesnet_label(
        "990ae9dd-7a59-4344-afcb-1b7b21368000;mammalia;primates;hominidae;homo;sapiens;human"
    ),
    "domestic_dog": parse_speciesnet_label(
        "3d80f1d6-b1df-4966-9ff4-94053c7a902a;mammalia;carnivora;canidae;"
        "canis;familiaris;domestic dog"
    ),
    "blank": parse_speciesnet_label("f1856211-cfb7-4a5b-9158-c0f72fd09ee6;;;;;;blank"),
}


@dataclass(frozen=True)
class BioClipComparisonPoint:
    """The already-recorded, real BioCLIP-2 result for the same real photo.

    Copied literally from ``scripts/benchmark_identification_eligibility.py``'s
    cited real cohort data (never re-derived), so a case can be compared
    head-to-head without re-running BioCLIP.
    """

    top1_label: str
    top1_score: float
    abstained: bool


@dataclass(frozen=True)
class SpeciesCandidateCaseResult:
    """One case's full head-to-head comparison outcome."""

    case_id: str
    expected_taxon_id: str | None
    speciesnet_top1_common_name: str
    speciesnet_top1_score: float
    speciesnet_agreement: TaxonomicAgreement
    bioclip_top1_label: str
    bioclip_top1_score: float
    bioclip_abstained: bool
    speciesnet_correct: bool | None
    bioclip_correct: bool | None
    verdict: Literal[
        "both_correct",
        "speciesnet_better",
        "bioclip_better",
        "both_wrong_or_unclear",
        "unscored_no_expected_taxon",
    ]


def compare_case(
    *,
    case_id: str,
    prediction: SpeciesNetPrediction,
    bioclip: BioClipComparisonPoint,
    expected_taxon_id: str | None,
) -> SpeciesCandidateCaseResult:
    """Deterministically compare one real case's SpeciesNet vs. BioCLIP outcome.

    "Correct" for BioCLIP means it suggested (did not abstain) the expected
    ``BUILTIN_SPECIES_CANDIDATE_TAXONOMY_IDS`` label; for SpeciesNet it means
    ``classify_taxonomic_agreement`` returned ``exact_species`` or
    ``same_genus`` against the expected taxon (a genus-level answer that is
    at least on the right branch counts as a materially useful outcome, an
    honest coarser answer rather than a wrong specific guess -- distinct from
    treating every non-exact answer as equally wrong). Correctness is
    ``None`` when no expected taxon is known for this case (a report-only
    diagnostic row, not a scored one), matching cohort D's
    ``expect_suggest=None`` convention in the existing eligibility benchmark.
    """
    expected_taxon = KNOWN_BACKYARD_TAXA.get(expected_taxon_id) if expected_taxon_id else None
    agreement = classify_taxonomic_agreement(prediction.top1_taxon, expected_taxon)

    if expected_taxon is None:
        speciesnet_correct: bool | None = None
        bioclip_correct: bool | None = None
        verdict: SpeciesCandidateCaseResult.__annotations__["verdict"] = (  # type: ignore[assignment]
            "unscored_no_expected_taxon"
        )
    else:
        speciesnet_correct = agreement in ("exact_species", "same_genus")
        bioclip_correct = (not bioclip.abstained) and bioclip.top1_label == expected_taxon_id
        if speciesnet_correct and bioclip_correct:
            verdict = "both_correct"
        elif speciesnet_correct and not bioclip_correct:
            verdict = "speciesnet_better"
        elif bioclip_correct and not speciesnet_correct:
            verdict = "bioclip_better"
        else:
            verdict = "both_wrong_or_unclear"

    return SpeciesCandidateCaseResult(
        case_id=case_id,
        expected_taxon_id=expected_taxon_id,
        speciesnet_top1_common_name=prediction.top1_common_name,
        speciesnet_top1_score=prediction.top1_score,
        speciesnet_agreement=agreement,
        bioclip_top1_label=bioclip.top1_label,
        bioclip_top1_score=bioclip.top1_score,
        bioclip_abstained=bioclip.abstained,
        speciesnet_correct=speciesnet_correct,
        bioclip_correct=bioclip_correct,
        verdict=verdict,
    )


def summarize_cases(results: tuple[SpeciesCandidateCaseResult, ...]) -> dict[str, int]:
    """Deterministic, order-independent tally across a set of case results."""
    scored = [r for r in results if r.verdict != "unscored_no_expected_taxon"]
    return {
        "n_total": len(results),
        "n_scored": len(scored),
        "n_both_correct": sum(1 for r in scored if r.verdict == "both_correct"),
        "n_speciesnet_better": sum(1 for r in scored if r.verdict == "speciesnet_better"),
        "n_bioclip_better": sum(1 for r in scored if r.verdict == "bioclip_better"),
        "n_both_wrong_or_unclear": sum(1 for r in scored if r.verdict == "both_wrong_or_unclear"),
        "n_speciesnet_correct": sum(1 for r in scored if r.speciesnet_correct),
        "n_bioclip_correct": sum(1 for r in scored if r.bioclip_correct),
    }
