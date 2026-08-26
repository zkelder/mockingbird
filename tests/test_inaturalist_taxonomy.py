"""Pure-module tests for `mockingbird.ecological.inaturalist_taxonomy` (see
docs/ecological-interoperability-submission-v1-contract.md "Taxonomy
translation"). Uses a fake `TaxonomyLookupRequester` -- never opens a real
socket, mirrors `tests/test_environmental_context*.py`'s identical
`WeatherRequester` fake convention."""

from __future__ import annotations

import json

import pytest

from mockingbird.ecological.inaturalist_taxonomy import (
    TaxonomyLookupMalformedResponseError,
    TaxonomyLookupTimeoutError,
    TaxonomyLookupUnavailableError,
    build_taxa_search_url,
    parse_taxa_response,
    resolve_taxon,
)


class _FakeRequester:
    def __init__(self, body: bytes | None = None, *, raises: Exception | None = None):
        self._body = body
        self._raises = raises
        self.requested_urls: list[str] = []

    def get(self, url: str, *, timeout_seconds: float) -> bytes:
        self.requested_urls.append(url)
        if self._raises is not None:
            raise self._raises
        assert self._body is not None
        return self._body


def _payload(results: list[dict]) -> bytes:
    return json.dumps({"results": results}).encode("utf-8")


def test_build_taxa_search_url_has_no_rank_filter_and_carries_the_query():
    url = build_taxa_search_url("Northern Cardinal")
    assert url.startswith("https://api.inaturalist.org/v1/taxa?")
    assert "q=Northern" in url or "q=Northern+Cardinal" in url
    assert "rank=" not in url


def test_parse_taxa_response_with_a_single_exactly_matching_result_is_matched():
    body = _payload([{"id": 9083, "name": "Cardinalis cardinalis", "preferred_common_name": "Northern Cardinal"}])
    match = parse_taxa_response(body, query_text="Northern Cardinal")
    assert match.status == "matched"
    assert match.taxon_id == "9083"
    assert match.scientific_name == "Cardinalis cardinalis"
    assert match.display_name == "Northern Cardinal"


def test_parse_taxa_response_matches_case_and_whitespace_insensitively():
    body = _payload([{"id": 9083, "name": "Cardinalis cardinalis", "preferred_common_name": "Northern Cardinal"}])
    match = parse_taxa_response(body, query_text="  northern cardinal  ")
    assert match.status == "matched"


def test_parse_taxa_response_matches_by_scientific_name_when_queried_by_scientific_name():
    body = _payload([{"id": 9083, "name": "Cardinalis cardinalis", "preferred_common_name": "Northern Cardinal"}])
    match = parse_taxa_response(body, query_text="Cardinalis cardinalis")
    assert match.status == "matched"
    assert match.taxon_id == "9083"


def test_parse_taxa_response_falls_back_to_scientific_name_display_when_no_common_name():
    body = _payload([{"id": 1, "name": "Sciurus carolinensis"}])
    match = parse_taxa_response(body, query_text="Sciurus carolinensis")
    assert match.status == "matched"
    assert match.display_name == "Sciurus carolinensis"


def test_parse_taxa_response_with_zero_results_is_not_found_never_guessed():
    match = parse_taxa_response(_payload([]), query_text="Northern Cardinal")
    assert match.status == "not_found"
    assert match.taxon_id is None
    assert match.candidate_count == 0


def test_a_real_world_multi_result_search_still_resolves_when_exactly_one_exact_match_exists():
    # Confirmed live against the real API (2026-08-26): a plain "Northern
    # Cardinal" query returns MORE than one candidate (the species plus
    # related/fuzzy suggestions). Requiring a single bare result would
    # wrongly flag this ordinary backyard species as ambiguous -- the
    # correct behavior is to trust the one candidate whose name is an
    # exact match, ignoring the non-matching extras.
    body = _payload(
        [
            {"id": 9083, "name": "Cardinalis cardinalis", "preferred_common_name": "Northern Cardinal"},
            {"id": 145283, "name": "Cardinalis cardinalis igneus", "preferred_common_name": "Northern Cardinal (San Lucas)"},
            {"id": 9084, "name": "Cardinalis sinuatus", "preferred_common_name": "Pyrrhuloxia"},
        ]
    )
    match = parse_taxa_response(body, query_text="Northern Cardinal")
    assert match.status == "matched"
    assert match.taxon_id == "9083"
    assert match.candidate_count == 3


def test_multiple_results_with_no_exact_match_is_ambiguous_never_a_silent_first_pick():
    body = _payload(
        [
            {"id": 1, "name": "Junco hyemalis hyemalis"},
            {"id": 2, "name": "Junco hyemalis oreganus"},
        ]
    )
    match = parse_taxa_response(body, query_text="Junco hyemalis")
    assert match.status == "ambiguous"
    assert match.taxon_id is None
    assert match.candidate_count == 2


def test_multiple_exact_matches_is_ambiguous():
    # Pathological/defensive case: two rows both exactly named the query.
    body = _payload([{"id": 1, "name": "Foo bar"}, {"id": 2, "name": "Foo bar"}])
    match = parse_taxa_response(body, query_text="Foo bar")
    assert match.status == "ambiguous"


def test_parse_taxa_response_rejects_non_json():
    with pytest.raises(TaxonomyLookupMalformedResponseError):
        parse_taxa_response(b"not json", query_text="anything")


def test_parse_taxa_response_rejects_missing_results_key():
    with pytest.raises(TaxonomyLookupMalformedResponseError):
        parse_taxa_response(json.dumps({"total_results": 0}).encode("utf-8"), query_text="anything")


def test_parse_taxa_response_rejects_a_result_missing_an_id():
    with pytest.raises(TaxonomyLookupMalformedResponseError):
        parse_taxa_response(_payload([{"name": "Junco hyemalis"}]), query_text="Junco hyemalis")


def test_resolve_taxon_calls_the_injected_requester_not_a_real_socket():
    requester = _FakeRequester(_payload([{"id": 5, "name": "Poecile atricapillus"}]))
    match = resolve_taxon("Poecile atricapillus", requester=requester)
    assert match.status == "matched"
    assert match.taxon_id == "5"
    assert len(requester.requested_urls) == 1


def test_resolve_taxon_propagates_a_timeout_as_the_typed_error():
    requester = _FakeRequester(raises=TaxonomyLookupTimeoutError("timed out"))
    with pytest.raises(TaxonomyLookupTimeoutError):
        resolve_taxon("anything", requester=requester)


def test_resolve_taxon_propagates_an_unavailable_error_distinctly_from_a_timeout():
    requester = _FakeRequester(raises=TaxonomyLookupUnavailableError("dns failed"))
    with pytest.raises(TaxonomyLookupUnavailableError):
        resolve_taxon("anything", requester=requester)
