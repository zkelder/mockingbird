"""iNaturalist taxonomy resolution -- a credential-free, cacheable lookup
against iNaturalist's public `GET /v1/taxa` search API (see "Taxonomy
translation" in docs/ecological-interoperability-submission-v1-contract.md).
Confirmed directly this milestone (`https://api.inaturalist.org/v1/
swagger.json`, checked 2026-08-25): the `/taxa` operation carries no
`security` requirement at all, unlike `POST /observations` (OAuth2-only).

Never guesses a numeric iNaturalist taxon id from memory -- those are
opaque database ids with zero mnemonic stability (unlike eBird's published,
stable alpha species codes, irrelevant here regardless since eBird is not
an offered destination -- see the governing contract doc's "eBird
workflow"). `mockingbird.repository.product_repository` owns the bounded
reusable cache table (`EcologicalTaxonomyMappingModel`) and only ever calls
this module on a genuine cache miss, mirroring `mockingbird.environment.
weather_provider`'s identical "resolve on miss, cache, never re-ask for a
stable fact" shape -- including the same dependency-injection seam
(`TaxonomyLookupRequester`) so tests never open a real socket.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Literal, Protocol

#: Recorded on every resolved mapping (see `EcologicalTaxonomyMappingModel.
#: taxonomy_source_version`) so a future change to which iNaturalist API
#: version/endpoint this module queries is visible on already-cached rows.
INATURALIST_TAXONOMY_SOURCE_VERSION = "inaturalist-v1-taxa-api"

_TAXA_SEARCH_URL = "https://api.inaturalist.org/v1/taxa"
DEFAULT_TIMEOUT_SECONDS = 10.0

TaxonMatchStatus = Literal["matched", "ambiguous", "not_found"]


class TaxonomyLookupError(Exception):
    """Base class for a failed iNaturalist taxonomy lookup -- callers (the
    repository layer) must catch this and degrade to an honest "lookup
    failed, try again later" outcome, never let it propagate to API/UI code
    (mirrors `mockingbird.environment.weather_provider.WeatherProviderError`).
    """


class TaxonomyLookupTimeoutError(TaxonomyLookupError):
    pass


class TaxonomyLookupUnavailableError(TaxonomyLookupError):
    pass


class TaxonomyLookupMalformedResponseError(TaxonomyLookupError):
    pass


@dataclass(frozen=True)
class TaxonMatch:
    """One resolved (or honestly not-resolved) taxonomy lookup outcome.
    `taxon_id`/`scientific_name`/`display_name` are `None` whenever
    `status` is not `"matched"` -- an honest gap, never a guessed value."""

    status: TaxonMatchStatus
    taxon_id: str | None = None
    scientific_name: str | None = None
    display_name: str | None = None
    candidate_count: int = 0


class TaxonomyLookupRequester(Protocol):
    """Dependency-injection seam so tests never open a real socket -- mirrors
    `mockingbird.environment.weather_provider.WeatherRequester`'s identical
    shape."""

    def get(self, url: str, *, timeout_seconds: float) -> bytes: ...


class UrlLibTaxonomyLookupRequester:
    """The real, production `TaxonomyLookupRequester`: stdlib
    `urllib.request` only, matching `weather_provider.
    UrlLibWeatherRequester`'s identical convention -- no new HTTP-client
    dependency."""

    def get(self, url: str, *, timeout_seconds: float) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "MockingBird/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                return response.read()
        except TimeoutError as exc:
            raise TaxonomyLookupTimeoutError(
                f"iNaturalist taxonomy lookup timed out after {timeout_seconds}s"
            ) from exc
        except urllib.error.URLError as exc:
            raise TaxonomyLookupUnavailableError(
                f"iNaturalist taxonomy lookup failed: {exc.reason}"
            ) from exc


def build_taxa_search_url(query_text: str) -> str:
    """No `rank` filter -- MockingBird's own taxonomy rarely carries a
    scientific name today (see the governing contract doc's "Taxonomy
    translation": every seeded taxon ships with `scientific_name=None`), so
    a query is frequently a common name rather than a precise binomial;
    over-constraining the search would only turn a real match into a false
    `"not_found"`. Confidence instead comes from `parse_taxa_response`
    requiring exactly one result."""

    params = {"q": query_text, "is_active": "true", "per_page": "5"}
    return f"{_TAXA_SEARCH_URL}?{urllib.parse.urlencode(params)}"


def parse_taxa_response(payload_bytes: bytes, *, query_text: str) -> TaxonMatch:
    """Pure parsing, directly testable with canned JSON -- no network
    access.

    iNaturalist's own fuzzy search routinely returns several candidates
    even for an unambiguous, exactly-spelled name (subspecies, related
    species, historical synonyms) -- confirmed directly against the real
    API this milestone (a plain "Northern Cardinal" query returns more
    than one row). Requiring a *single bare result* for `"matched"` would
    therefore flag most ordinary backyard species as ambiguous, which is
    overly conservative, not honestly cautious. Instead: a candidate whose
    scientific name or preferred common name matches `query_text`
    case-insensitively, exactly, is treated as confidently resolved
    regardless of how many other, non-matching candidates also came back.
    Zero results is `"not_found"`; zero *exact-matching* results among one
    or more candidates, or more than one exact match, is honestly
    `"ambiguous"` -- never a guessed top pick (see "Taxonomy conflict" in
    the governing contract doc: ambiguity must be explicit, never silently
    resolved)."""

    try:
        payload = json.loads(payload_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise TaxonomyLookupMalformedResponseError("iNaturalist taxa response was not valid JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise TaxonomyLookupMalformedResponseError("iNaturalist taxa response is missing 'results'")

    results = payload["results"]
    if not results:
        return TaxonMatch("not_found", candidate_count=0)
    for result in results:
        if not isinstance(result, dict) or "id" not in result:
            raise TaxonomyLookupMalformedResponseError("iNaturalist taxa response result is missing 'id'")

    normalized_query = query_text.strip().casefold()
    exact_matches = [
        result
        for result in results
        if normalized_query
        in {
            str(result.get("name") or "").strip().casefold(),
            str(result.get("preferred_common_name") or "").strip().casefold(),
        }
        - {""}
    ]
    if len(exact_matches) != 1:
        return TaxonMatch("ambiguous", candidate_count=len(results))

    result = exact_matches[0]
    return TaxonMatch(
        "matched",
        taxon_id=str(result["id"]),
        scientific_name=result.get("name"),
        display_name=(result.get("preferred_common_name") or result.get("name")),
        candidate_count=len(results),
    )


def resolve_taxon(
    query_text: str,
    *,
    requester: TaxonomyLookupRequester,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> TaxonMatch:
    """One bounded HTTP call resolving one query string to (at most) one
    confident iNaturalist taxon. Raises a `TaxonomyLookupError` subclass on
    any transport failure -- callers must catch it and degrade honestly,
    never let it block the rest of an eligibility preview (mirrors
    `weather_provider.fetch_hourly_weather`)."""

    url = build_taxa_search_url(query_text)
    body = requester.get(url, timeout_seconds=timeout_seconds)
    return parse_taxa_response(body, query_text=query_text)


__all__ = [
    "INATURALIST_TAXONOMY_SOURCE_VERSION",
    "TaxonMatchStatus",
    "TaxonomyLookupError",
    "TaxonomyLookupTimeoutError",
    "TaxonomyLookupUnavailableError",
    "TaxonomyLookupMalformedResponseError",
    "TaxonMatch",
    "TaxonomyLookupRequester",
    "UrlLibTaxonomyLookupRequester",
    "build_taxa_search_url",
    "parse_taxa_response",
    "resolve_taxon",
]
