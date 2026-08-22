"""Hardware-free tests for the pure SpeciesNet candidate-comparison module."""
from __future__ import annotations

from mockingbird.species.speciesnet_candidate import (
    KNOWN_BACKYARD_TAXA,
    BioClipComparisonPoint,
    SpeciesNetCandidateError,
    SpeciesNetPrediction,
    classify_taxonomic_agreement,
    compare_case,
    parse_speciesnet_label,
    summarize_cases,
)
import pytest


HOUSE_FINCH_ROW = (
    "97969dd0-97f3-4562-af1c-ac1bea43badc;aves;passeriformes;fringillidae;"
    "haemorhous;mexicanus;house finch"
)
RBW_ROW = (
    "941db4fe-fbf3-434f-bfb1-f765009d5e7e;aves;piciformes;picidae;"
    "melanerpes;carolinus;red-bellied woodpecker"
)
BLANK_ROW = "f1856211-cfb7-4a5b-9158-c0f72fd09ee6;;;;;;blank"


class TestParseSpeciesNetLabel:
    def test_parses_all_seven_fields(self) -> None:
        taxon = parse_speciesnet_label(HOUSE_FINCH_ROW)
        assert taxon.uuid == "97969dd0-97f3-4562-af1c-ac1bea43badc"
        assert taxon.class_ == "aves"
        assert taxon.order == "passeriformes"
        assert taxon.family == "fringillidae"
        assert taxon.genus == "haemorhous"
        assert taxon.species == "mexicanus"
        assert taxon.common_name == "house finch"

    def test_parses_rollup_row_with_empty_fields(self) -> None:
        taxon = parse_speciesnet_label(BLANK_ROW)
        assert taxon.class_ == ""
        assert taxon.genus == ""
        assert taxon.common_name == "blank"

    def test_wrong_field_count_fails_closed(self) -> None:
        with pytest.raises(SpeciesNetCandidateError, match="malformed_speciesnet_label"):
            parse_speciesnet_label("too;few;fields")

    def test_extra_semicolon_also_fails_closed(self) -> None:
        with pytest.raises(SpeciesNetCandidateError):
            parse_speciesnet_label(HOUSE_FINCH_ROW + ";extra")


class TestClassifyTaxonomicAgreement:
    def test_exact_species_match(self) -> None:
        finch = parse_speciesnet_label(HOUSE_FINCH_ROW)
        assert classify_taxonomic_agreement(finch, finch) == "exact_species"

    def test_same_genus_different_species_is_not_exact(self) -> None:
        expected = parse_speciesnet_label(HOUSE_FINCH_ROW)
        predicted = parse_speciesnet_label(
            "x;aves;passeriformes;fringillidae;haemorhous;purpureus;purple finch"
        )
        assert classify_taxonomic_agreement(predicted, expected) == "same_genus"

    def test_same_family_different_genus(self) -> None:
        expected = parse_speciesnet_label(HOUSE_FINCH_ROW)
        predicted = parse_speciesnet_label(
            "x;aves;passeriformes;fringillidae;spinus;tristis;american goldfinch"
        )
        assert classify_taxonomic_agreement(predicted, expected) == "same_family"

    def test_genus_only_rollup_is_still_same_genus(self) -> None:
        expected = parse_speciesnet_label(HOUSE_FINCH_ROW)
        predicted = parse_speciesnet_label("x;aves;passeriformes;fringillidae;haemorhous;;haemorhous species")
        assert classify_taxonomic_agreement(predicted, expected) == "same_genus"

    def test_wholly_different_family_is_different(self) -> None:
        finch = parse_speciesnet_label(HOUSE_FINCH_ROW)
        woodpecker = parse_speciesnet_label(RBW_ROW)
        assert classify_taxonomic_agreement(woodpecker, finch) == "different"

    def test_blank_prediction_against_real_expected_is_different_not_a_crash(self) -> None:
        finch = parse_speciesnet_label(HOUSE_FINCH_ROW)
        blank = parse_speciesnet_label(BLANK_ROW)
        assert classify_taxonomic_agreement(blank, finch) == "different"

    def test_no_expected_taxon_reports_that_explicitly(self) -> None:
        finch = parse_speciesnet_label(HOUSE_FINCH_ROW)
        assert classify_taxonomic_agreement(finch, None) == "no_expected_taxon"

    def test_none_predicted_is_different_never_a_crash(self) -> None:
        finch = parse_speciesnet_label(HOUSE_FINCH_ROW)
        assert classify_taxonomic_agreement(None, finch) == "different"

    def test_two_genus_only_rollups_never_false_positive_exact_species(self) -> None:
        # Two different rollup rows both carrying an empty `species` field must
        # never register as `exact_species`/`same_genus`/`same_family` just
        # because "" == "" -- these two really do share an order
        # (passeriformes), which the cascade correctly reports, but must not
        # be conflated with matching at any finer level than that.
        a = parse_speciesnet_label("x;aves;passeriformes;troglodytidae;thryothorus;;thryothorus species")
        b = parse_speciesnet_label("y;aves;passeriformes;paridae;baeolophus;;baeolophus species")
        assert classify_taxonomic_agreement(a, b) == "same_order"

    def test_two_empty_species_rollups_in_different_orders_are_different(self) -> None:
        bird_rollup = parse_speciesnet_label("x;aves;passeriformes;troglodytidae;thryothorus;;thryothorus species")
        mammal_rollup = parse_speciesnet_label("y;mammalia;carnivora;canidae;canis;;canis species")
        assert classify_taxonomic_agreement(bird_rollup, mammal_rollup) == "different"


class TestKnownBackyardTaxa:
    def test_house_finch_entry_matches_real_row(self) -> None:
        assert KNOWN_BACKYARD_TAXA["house_finch"] == parse_speciesnet_label(HOUSE_FINCH_ROW)

    def test_carolina_wren_has_no_species_level_row_disclosed_honestly(self) -> None:
        # Real, disclosed taxonomy-coverage gap: this checkpoint has no exact
        # Carolina Wren species row, only a genus-level rollup -- the mapping
        # must not fabricate a species field to paper over that.
        assert KNOWN_BACKYARD_TAXA["carolina_wren"].species == ""
        assert KNOWN_BACKYARD_TAXA["carolina_wren"].genus == "thryothorus"

    def test_non_bird_hard_negative_taxa_present(self) -> None:
        assert KNOWN_BACKYARD_TAXA["human"].common_name == "human"
        assert KNOWN_BACKYARD_TAXA["domestic_dog"].common_name == "domestic dog"
        assert KNOWN_BACKYARD_TAXA["blank"].common_name == "blank"


class TestSpeciesNetPrediction:
    def test_top1_properties(self) -> None:
        pred = SpeciesNetPrediction(
            case_id="case-1",
            top5_labels=(HOUSE_FINCH_ROW, RBW_ROW),
            top5_scores=(0.9, 0.05),
        )
        assert pred.top1_label == HOUSE_FINCH_ROW
        assert pred.top1_score == 0.9
        assert pred.top1_common_name == "house finch"
        assert len(pred.top5_taxa()) == 2

    def test_mismatched_lengths_fail_closed(self) -> None:
        with pytest.raises(SpeciesNetCandidateError):
            SpeciesNetPrediction(case_id="c", top5_labels=(HOUSE_FINCH_ROW,), top5_scores=(0.9, 0.1))

    def test_empty_prediction_fails_closed(self) -> None:
        with pytest.raises(SpeciesNetCandidateError):
            SpeciesNetPrediction(case_id="c", top5_labels=(), top5_scores=())


class TestCompareCase:
    def test_both_correct(self) -> None:
        pred = SpeciesNetPrediction(case_id="c", top5_labels=(HOUSE_FINCH_ROW,), top5_scores=(0.95,))
        bioclip = BioClipComparisonPoint(top1_label="house_finch", top1_score=0.99, abstained=False)
        result = compare_case(case_id="c", prediction=pred, bioclip=bioclip, expected_taxon_id="house_finch")
        assert result.verdict == "both_correct"
        assert result.speciesnet_correct is True
        assert result.bioclip_correct is True

    def test_speciesnet_better_when_bioclip_abstains_but_speciesnet_right(self) -> None:
        pred = SpeciesNetPrediction(case_id="c", top5_labels=(HOUSE_FINCH_ROW,), top5_scores=(0.95,))
        bioclip = BioClipComparisonPoint(top1_label="red_bellied_woodpecker", top1_score=0.6, abstained=True)
        result = compare_case(case_id="c", prediction=pred, bioclip=bioclip, expected_taxon_id="house_finch")
        assert result.verdict == "speciesnet_better"

    def test_bioclip_better_when_speciesnet_wrong_family(self) -> None:
        pred = SpeciesNetPrediction(case_id="c", top5_labels=(RBW_ROW,), top5_scores=(0.4,))
        bioclip = BioClipComparisonPoint(top1_label="house_finch", top1_score=0.9, abstained=False)
        result = compare_case(case_id="c", prediction=pred, bioclip=bioclip, expected_taxon_id="house_finch")
        assert result.verdict == "bioclip_better"

    def test_both_wrong_when_bioclip_abstains_and_speciesnet_wrong(self) -> None:
        pred = SpeciesNetPrediction(case_id="c", top5_labels=(RBW_ROW,), top5_scores=(0.4,))
        bioclip = BioClipComparisonPoint(top1_label="red_bellied_woodpecker", top1_score=0.6, abstained=True)
        result = compare_case(case_id="c", prediction=pred, bioclip=bioclip, expected_taxon_id="house_finch")
        assert result.verdict == "both_wrong_or_unclear"

    def test_no_expected_taxon_is_unscored_not_wrong(self) -> None:
        pred = SpeciesNetPrediction(case_id="c", top5_labels=(HOUSE_FINCH_ROW,), top5_scores=(0.9,))
        bioclip = BioClipComparisonPoint(top1_label="house_finch", top1_score=0.9, abstained=False)
        result = compare_case(case_id="c", prediction=pred, bioclip=bioclip, expected_taxon_id=None)
        assert result.verdict == "unscored_no_expected_taxon"
        assert result.speciesnet_correct is None
        assert result.bioclip_correct is None

    def test_genus_level_speciesnet_answer_still_counts_correct(self) -> None:
        # A genus-only rollup on the right genus is a materially useful,
        # honest outcome -- not penalized the same as a wrong family guess.
        genus_only = "x;aves;passeriformes;fringillidae;haemorhous;;haemorhous species"
        pred = SpeciesNetPrediction(case_id="c", top5_labels=(genus_only,), top5_scores=(0.7,))
        bioclip = BioClipComparisonPoint(top1_label="red_bellied_woodpecker", top1_score=0.6, abstained=True)
        result = compare_case(case_id="c", prediction=pred, bioclip=bioclip, expected_taxon_id="house_finch")
        assert result.speciesnet_correct is True
        assert result.speciesnet_agreement == "same_genus"


class TestSummarizeCases:
    def test_tally_is_order_independent(self) -> None:
        pred_right = SpeciesNetPrediction(case_id="a", top5_labels=(HOUSE_FINCH_ROW,), top5_scores=(0.9,))
        pred_wrong = SpeciesNetPrediction(case_id="b", top5_labels=(RBW_ROW,), top5_scores=(0.4,))
        bioclip_abstain = BioClipComparisonPoint(top1_label="red_bellied_woodpecker", top1_score=0.6, abstained=True)
        r1 = compare_case(case_id="a", prediction=pred_right, bioclip=bioclip_abstain, expected_taxon_id="house_finch")
        r2 = compare_case(case_id="b", prediction=pred_wrong, bioclip=bioclip_abstain, expected_taxon_id="house_finch")
        forward = summarize_cases((r1, r2))
        backward = summarize_cases((r2, r1))
        assert forward == backward
        assert forward["n_total"] == 2
        assert forward["n_scored"] == 2
        assert forward["n_speciesnet_better"] == 1
        assert forward["n_both_wrong_or_unclear"] == 1

    def test_unscored_cases_excluded_from_scored_tallies(self) -> None:
        pred = SpeciesNetPrediction(case_id="a", top5_labels=(HOUSE_FINCH_ROW,), top5_scores=(0.9,))
        bioclip = BioClipComparisonPoint(top1_label="house_finch", top1_score=0.9, abstained=False)
        scored = compare_case(case_id="a", prediction=pred, bioclip=bioclip, expected_taxon_id="house_finch")
        unscored = compare_case(case_id="b", prediction=pred, bioclip=bioclip, expected_taxon_id=None)
        summary = summarize_cases((scored, unscored))
        assert summary["n_total"] == 2
        assert summary["n_scored"] == 1


def test_module_has_no_product_repository_filesystem_or_model_runtime_import() -> None:
    """This module is pure benchmark-comparison math, mirroring
    mockingbird.observation.detector_comparison's own pure/impure split: it
    must never be able to reach the product database, a filesystem path, or
    a model runtime, so a benchmark comparison structurally cannot mutate
    reviewed truth or silently start depending on real inference to import
    (matching the same structural guarantee
    test_acceptance_recorder.py::test_module_has_no_product_repository_or_
    admission_pipeline_import already enforces for the acceptance recorder)."""

    import ast
    from pathlib import Path as _Path

    source = _Path("src/mockingbird/species/speciesnet_candidate.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    forbidden_prefixes = (
        "mockingbird.repository",
        "mockingbird.storage",
        "mockingbird.api",
        "speciesnet",
        "open_clip",
        "torch",
        "PIL",
        "pathlib",
        "sqlite3",
        "requests",
        "urllib",
    )
    for module_name in imported_modules:
        assert not module_name.startswith(forbidden_prefixes), (
            f"speciesnet_candidate.py imports {module_name!r} -- this module must stay pure "
            "(no product repository, filesystem, network, or model-runtime access)"
        )
