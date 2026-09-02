# Review Provenance Validation & API Error Semantics v1: report

Bounded RELEASE-CORRECTNESS milestone. Closes the reproducible defect
Representative Daylight Gate A Field Acceptance v9 disclosed and worked
around: `POST /api/review-labels` with `review_origin="agent_diagnostic"`
and no `reviewer_identity` correctly raises `ReviewProvenanceError` deep in
`product_repository.py`, but `create_review_label` in `api/main.py` only
caught `ReviewRevisionConflictError`, so this well-formed validation error
reached the client as an unhandled `500` instead of a clean `400`. See
[representative-daylight-gate-a-field-acceptance-v9-report.md](representative-daylight-gate-a-field-acceptance-v9-report.md)
("Defects") for the original disclosure and its own precise next-DEV
contract, which this milestone follows.

## Starting state

Verified against `docs/release-execution-state.md` before any change:

- Branch `main`, HEAD `e18e0e8` (the reconciliation commit accepting
  Hard-Negative Visit Admission Precision & Species-Escalation Correctness
  v1) -- matches.
- Schema `58` (`CURRENT_DATABASE_SCHEMA_VERSION` in `storage/database.py`)
  -- matches, unchanged by this milestone.
- Latest accepted milestone: Hard-Negative Visit Admission Precision &
  Species-Escalation Correctness v1 -- matches (§1/§3).
- Gate A: **not** self-closed by that milestone, field-proof still
  outstanding -- matches (§3's "Remaining Gate A dependency," item 1).
- The disclosed `agent_diagnostic` review-provenance `500` is item 6/7 in
  both the v9 and Hard-Negative reconciliation entries' own "Remaining Gate
  A dependency" lists, unchanged in each -- matches "OPEN reproduced
  defect."
- Current authorization: **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
  REQUIRED** -- matches, and is exactly the authorization this bounded
  milestone was explicitly issued under.
- Not pushed: confirmed, 290 commits ahead of `origin/main` at the start of
  this milestone.

No material difference found; proceeded without stopping.

**Worktree safety:** no active writer; the seven files this milestone was
told to preserve untouched (`docs/wildlife-detector-training-contract.md
.orig`, `scripts/evaluate_small_bird_detector.py`, `scripts/materialize_
wildlife_stage2.py.orig`, `scripts/train_wildlife_stage2_rfdetr.py.orig`,
`src/mockingbird/detectors/small_bird_benchmark.py`, `src/mockingbird/
training/wildlife.py.orig`, `tests/test_small_bird_benchmark.py`) were
confirmed present and untracked both before and after this milestone's own
`git stash push -u -- <2 changed files>`/`pop` round trip (used only to
baseline `ruff`, scoped by explicit pathspec to the two files this
milestone actually touched) -- `git status --short` at the end shows
exactly those seven untracked files plus the two intentionally modified
ones, nothing else.

## Field reproducer

Built an API-level reproducer (`LegacyAuthenticatedSyncTestClient`, the
same class `tests/test_api.py` uses -- a real authenticated caller, not a
bypassed/mocked one) against the real endpoint, not the domain function
directly:

- Valid authenticated caller (the client's own automatic administrator
  session).
- Valid Visit target (`visit-bird-feeder-001`, present in the demo seed
  every fresh repository starts with).
- `review_origin="agent_diagnostic"`.
- `reviewer_identity` omitted.

```python
response = client.post(
    "/api/review-labels",
    json={
        "review_origin": "agent_diagnostic",
        "target_type": "visit",
        "target_id": "visit-bird-feeder-001",
        "label": "carolina_wren",
        "notes": "diagnostic pass",
    },
)
```

## Pre-fix RED

Ran the reproducer against the unmodified starting `HEAD`. The exception
propagated all the way out of the ASGI call, uncaught by any handler
(confirmed: the only registered `@app.exception_handler` in `api/main.py`
is for `SQLAlchemyError`, which `ReviewProvenanceError` is not) --
reproduced via the project's own pytest `TestClient` patch
(`_patch_testclient_for_pytest`, `api/main.py`), which sets `raise_server_
exceptions=True`/`raise_app_exceptions=True` specifically so an unhandled
app exception surfaces directly to the caller instead of being swallowed
-- exactly the mechanism a real deployed ASGI server (uvicorn) turns into
a bare, uncontrolled `500 Internal Server Error` for a real HTTP client.
Full traceback, captured before any code change:

```
mockingbird.review_provenance.ReviewProvenanceError: agent_diagnostic_requires_reviewer_identity

  File ".../src/mockingbird/api/main.py", line 14734, in create_review_label
    result = repository.create_review_label(payload, acting_user=current_user)
  File ".../src/mockingbird/repository/product_repository.py", line 26376, in create_review_label
    return self._create_review_label_result_in_session(...)
  File ".../src/mockingbird/repository/product_repository.py", line 26709, in _create_review_label_result_in_session
    review_label, visit, event = self._create_review_label_in_session(...)
  File ".../src/mockingbird/repository/product_repository.py", line 36303, in _create_review_label_in_session
    review_provenance.validate_review_origin(review_origin, reviewer_identity, notes=payload.notes)
  File ".../src/mockingbird/review_provenance.py", line 189, in validate_review_origin
    raise ReviewProvenanceError(f"{origin}_requires_reviewer_identity")
```

Confirms the v9 disclosure exactly: a well-formed, expected validation
error, reaching the client as an unhandled `500` with no stable code, no
actionable client-safe message.

## Root cause

Traced request DTO -> endpoint -> repository -> provenance validation ->
exception -> HTTP mapping:

1. **Where is `ReviewProvenanceError` expected to be caught?** At the
   endpoint boundary, in `create_review_label`'s own `try`/`except` block
   (`api/main.py`) -- exactly where its sibling endpoint `reclassify_
   review_label_provenance` (`POST /api/review-labels/{id}/reclassify
   -provenance`, same file, ~60 lines below) already does it:
   `except ReviewProvenanceError as error: raise HTTPException(status_code
   =400, detail=str(error)) from error`.
2. **Do sibling domain-validation exceptions already have mappings?**
   Yes. `ReviewRevisionConflictError` -> `409` (already handled in
   `create_review_label` itself); `ReviewProvenanceConflictError` -> `409`
   and `ReviewProvenanceError` -> `400` (both already handled in
   `reclassify_review_label_provenance`). `create_review_label` was
   missing only the one clause its own closest sibling already has.
3. **Is this endpoint bypassing a shared mapper?** No single shared
   mapper function exists for review-provenance errors the way
   `_camera_node_pairing_http_error` exists for Camera Node pairing
   errors -- each review endpoint maps inline. `create_review_label` is
   not bypassing a boundary so much as simply missing a clause its
   sibling already carries; introducing a new shared helper used by only
   these two call sites would not narrow anything, so the fix mirrors the
   sibling's existing inline convention exactly rather than inventing a
   new indirection.
4. **Specific to `agent_diagnostic`, or generic to provenance
   validation?** Generic. `validate_review_origin`
   (`review_provenance.py`) raises `ReviewProvenanceError` for three
   distinct causes -- `unsupported_review_origin`,
   `<origin>_requires_reviewer_identity` (`imported_curated` or
   `agent_diagnostic`), and `human_origin_conflicts_with_disclosed_non
   _human_review` -- and the endpoint caught none of them. Confirmed by
   test: the `imported_curated`-missing-identity and the `human`
   -conflicting-disclosure cases reproduce the identical unhandled-`500`
   shape pre-fix and the identical clean-`400` shape post-fix (see "Test
   matrix," below). (`unsupported_review_origin` is not reachable through
   this HTTP endpoint specifically -- `ReviewCorrectionCreate.review_
   origin` is already typed `ReviewOrigin | None`, a three-value
   `Literal`, so Pydantic itself rejects any other string with its own
   `422` before the handler body ever runs; the clause still exists for
   defense in depth and because `validate_review_origin` is also called
   from non-HTTP callers with no such type gate.)

**Scope check (§10):** traced every repository method that reaches
`review_provenance.validate_review_origin` and every endpoint that calls
one, to find any other endpoint exhibiting the identical unhandled-`500`
omission:

| Endpoint | Repository method | `ReviewProvenanceError` handling before this fix |
| --- | --- | --- |
| `POST /api/review-labels` | `create_review_label` | **None -- unhandled 500 (the reproduced defect)** |
| `POST /api/review-labels/{id}/reclassify-provenance` | `reclassify_review_label_provenance` | Already correct: explicit `except ReviewProvenanceError` -> `400` |
| `POST /api/visits/{id}/revision` | `revise_visit_review` | Already avoids `500`: a trailing `except ValueError` catch-all maps it to a generic `400` ("The reviewed Visit could not be revised.") |
| `POST /api/review-queue/fast/correct` | `create_fast_review_correction` | Same as above: trailing `except ValueError` -> generic `400` |
| `POST /api/review-queue/bulk-correct` | `bulk_correct_review_queue_items` | Same as above: trailing `except ValueError` -> generic `400` |
| `POST /api/visits/{id}/reopen` | `reopen_visit_review` | Does not call `validate_review_origin` at all -- checks `is_authority_eligible` directly and raises the already-handled `ReviewRevisionConflictError` instead |

Only `create_review_label` reproduces the identical omission (a bare,
unhandled `500`); the other three endpoints reaching the same validation
path already avoid a `500` via a pre-existing generic `except ValueError`
fallback they each independently carry, though with a less specific
message than `str(error)` would give. That is a real, minor
inconsistency (see "Remaining review/API defects"), but not "the identical
exception-mapping omission" this milestone's own scope-check instruction
(§10) asks to fix through the shared boundary, so those three endpoints
were left unmodified, per "do not audit the whole API."

## HTTP contract

Chosen: **`HTTP 400`, `detail=str(error)`** -- not chosen by intuition.
This is the exact, already-established convention for this exact
exception type at the closest sibling endpoint in the same file
(`reclassify_review_label_provenance`, `except ReviewProvenanceError as
error: raise HTTPException(status_code=400, detail=str(error)) from
error`), which is stronger, more specific repository precedent than the
alternative candidate considered (mirroring `_camera_node_pairing_http_
error`'s dict-of-friendly-messages style, which the v9 report's own
"precise next DEV contract" suggested as a general pattern reference but
which no `ReviewProvenanceError` call site in this repository actually
uses). `str(error)` on `ReviewProvenanceError` already yields a terse,
stable, machine-parseable code (`agent_diagnostic_requires_reviewer_
identity`, `imported_curated_requires_reviewer_identity`, `human_origin_
conflicts_with_disclosed_non_human_review`, `unsupported_review_origin`)
-- sufficient for a caller to correct the request, and appropriate for
this endpoint's actual non-`"human"` callers (`agent_diagnostic` is by
definition an automation/agent caller, not an interactive end user reading
prose in a form). No traceback, stack frame, file path, or SQL text is
included -- confirmed by direct test assertion (`"Traceback" not in
detail`, `".py" not in detail`) as well as by construction (the `detail`
is exactly `str(ReviewProvenanceError(...))`, a single short code string
the domain layer itself constructs). Generic auth/privacy behavior is
untouched: `current_user_or_401(request)` still runs first, unmodified,
before the new `except` clause is ever reached.

## Implementation

One `except` clause added to `create_review_label`
([main.py:14740](../src/mockingbird/api/main.py:14740)), immediately after
the existing `except ReviewRevisionConflictError`, mirroring `reclassify_
review_label_provenance`'s own identical mapping:

```python
except ReviewProvenanceError as error:
    raise HTTPException(status_code=400, detail=str(error)) from error
```

`ReviewProvenanceError` was already imported at module scope (`from
mockingbird.review_provenance import ReviewProvenanceError`, used
elsewhere in this same file) -- no new import needed. 8 lines changed in
production code, in exactly one function, zero lines changed anywhere in
`product_repository.py`, `review_provenance.py`, or any other endpoint.
No schema change, no migration, no new dependency.

Deliberately **not** done, per this milestone's own explicit instructions
(§7/§9):

- No change to `review_provenance.py` -- `validate_review_origin`,
  `IDENTITY_REQUIRED_ORIGINS`, `AUTHORITATIVE_ORIGINS` all untouched.
  `agent_diagnostic`/`imported_curated` still strictly require a named
  `reviewer_identity`; no default, no anonymous-reviewer fallback, no
  silent substitution of the authenticated account's own identity.
- No generic `except Exception` / broadened `except ValueError` added to
  `create_review_label` -- the new clause names exactly one exception
  type, so it cannot widen to catch anything this milestone did not
  intend (see "Unexpected-exception result," below).
- No change to the three sibling endpoints identified in the scope check
  that already avoid a `500` (see "Remaining review/API defects").

## Missing-identity result

`test_review_label_agent_diagnostic_without_reviewer_identity_returns_
clean_400` (`tests/test_api.py`): the exact reproduced case now returns a
clean `400` with `detail == "agent_diagnostic_requires_reviewer_identity"`
and no leaked internal detail. Confirmed via the Visit's own raw,
unfiltered `correction_history` (`GET /api/visits/{id}/detail`, backed by
`_review_label_history_models_for_visit`, which -- unlike `GET /api
/review-labels`/`detail["review_labels"]`, both of which resolve only the
current *authoritative* row per target via `_effective_review_label_
models` and would hide a leaked non-authoritative row regardless -- is
unfiltered by authority and so is the one API-visible place that can
actually prove nothing was persisted) that it is empty, and that the
Visit's `review_status`/`reviewed_label` are untouched
(`needs_review`/`null`). A second, structurally-identical case
(`imported_curated` with no `reviewer_identity`) and a third, differently
-shaped `ReviewProvenanceError` case (`human` origin whose own `notes`
self-discloses non-human review, `human_origin_conflicts_with_disclosed_
non_human_review`) both confirm the fix is generic to review-provenance
validation, not special-cased to `agent_diagnostic`.

## Valid-review result

`test_review_label_agent_diagnostic_with_reviewer_identity_is_accepted_
but_not_authoritative`: `agent_diagnostic` with a valid `reviewer_
identity` still returns `201` exactly as before this milestone (this path
was never broken -- only the *rejection* path was) and is durably
recorded (confirmed via `correction_history`, one entry, `review_origin
== "agent_diagnostic"`, `is_authoritative is False`) while the Visit's
`review_status`/`reviewed_label` stay `needs_review`/`null` -- the
provenance policy itself (a diagnostic assessment is visible but never
authoritative) is exactly as strict after this milestone as before it.
Pre-existing `"human"`-origin paths in `tests/test_api.py` (correction,
revision, dataset-export eligibility, analytics, review-queue exclusion)
and the full `imported_curated`/`human`/`legacy_unattributed` domain
-contract suite in `tests/test_review_decision_provenance.py` all continue
to pass unchanged -- "other review origins" unaffected.

## Reviewed-truth result

`test_failed_provenance_validation_does_not_overwrite_existing_reviewed_
truth`: established real Reviewed truth first (`"human"` correction,
`northern_cardinal`), then issued the exact failing `agent_diagnostic`
request against the *same* Visit. The failed request changes nothing:
`review_status` stays `"reviewed"`, `reviewed_label` stays `"northern_
cardinal"`, and the Visit's review-label history still contains exactly
the one original correction, not two. This is a direct, stronger form of
"failed validation cannot mutate Reviewed truth" than an empty-history
check alone -- it proves an invalid request cannot silently displace
*existing* truth, not merely that it cannot create new truth from
nothing. (Structurally guaranteed independent of this milestone's own
change: `validate_review_origin` runs at the very top of
`_create_review_label_in_session`, before the `ReviewLabelModel` row is
even constructed, let alone added to the session -- confirmed by direct
code inspection, not just the test.)

## Audit result

`test_failed_provenance_validation_creates_no_review_corrected_audit_
entry`: after the failed request, `isolated_repository.list_audit_log()`
contains no `"review.corrected"` entry for the target Visit. Already
structurally true before this milestone (`repository.record_audit_event(
...)` in `create_review_label` sits after the `try`/`except` block and is
unreachable whenever that block raises, by an unhandled exception before
this fix or by the new `HTTPException` after it) -- this test formalizes
and pins that property at the API level rather than changing it.

## Unexpected-exception result

`test_unexpected_review_label_exception_still_surfaces_as_a_server_
error`: monkeypatched `ProductRepository.create_review_label` to raise a
plain `RuntimeError("unexpected_repository_failure")` -- a genuinely
unrelated, unexpected exception type, nothing to do with review
provenance. It propagates unhandled exactly as before this milestone
(caught by neither the pre-existing `ReviewRevisionConflictError` clause
nor the new `ReviewProvenanceError` clause), confirmed via `pytest.raises
(RuntimeError, ...)` around the same real API call used everywhere else
in this test matrix. The new clause names exactly one exception type, so
it structurally cannot widen into "any domain call failure becomes a
`400`" -- an actual unexpected server-side bug still surfaces as an
unhandled error (a real `500` outside the test harness), not a misleading
client-error response.

## Validation

**Tier 1 -- focused review API/provenance tests.** `tests/test_api.py`
in full (not just the new tests, to catch any incidental regression
across the file's other 53 pre-existing tests): **61/61 passed.** 7 new
tests added, covering every Tier 1 matrix item from this milestone's own
instructions (missing identity, valid diagnostic review, other origins
unchanged, invalid-provenance-combination consistency, Reviewed truth,
audit, generic-exception safety).

**Tier 2 -- affected review/correction/auth/audit subsystem.** Selected
by tracing actual call graphs (the scope-check table, above) and endpoint
-level keyword search across `tests/`, not a blanket sweep:
`tests/test_review_provenance.py` (the validation module itself),
`tests/test_review_decision_provenance.py` (the full provenance-contract
milestone's own repository-level suite: `create_review_label`, revise,
reopen, bulk-correct, fast-review, reclassify, legacy backfill),
`tests/test_reviewed_observation_revision.py`, `tests/test_fast_review.py`,
`tests/test_review_queue_bulk_corrections.py` (the three sibling
endpoints identified in the scope check), `tests/test_local_identity_
multi_user.py` (auth + audit trail + `acting_user` attribution),
`tests/test_review_identification.py`, `tests/test_field_acceptance_
authentication.py` (unauthenticated `POST /api/review-labels` + audit-log
assertions), `tests/test_visit_curation.py`, `tests/test_visit_tags.py`
(both exercise `POST /api/review-labels` as setup). **206/206 passed
across 11 files (61 + 117 + 28), 0 regressions.**

**Tier 3 -- decision: not run.** Per this milestone's own instruction
("Run Core only if the fix modifies shared global API exception handling
or otherwise becomes cross-cutting"): the fix is one `except` clause,
naming one already-existing, already-imported exception type, added to
one endpoint's own local `try`/`except` block. It does not touch the
shared `SQLAlchemyError` handler, the request-correlation middleware, any
shared mapper utility, `review_provenance.py`, or any other endpoint --
not cross-cutting by the criterion this milestone itself set. Not run.

**`ruff`:** `ruff check src/mockingbird/api/main.py tests/test_api.py` ->
28 findings, all pre-existing (confirmed by `git stash`-isolating this
milestone's own two changed files against the unmodified starting `HEAD`
and re-running: identical 28 findings, none on a line this milestone
touched -- unrelated `E701`s in the tag-membership endpoints and two
long-standing unused imports (`asyncio`, `httpx`) at the top of
`tests/test_api.py`). **Zero new findings.**

## Remaining review/API defects

Not fixed here, disclosed per this milestone's own scope discipline (§10,
"do not audit the whole API"):

- **Generic-`ValueError`-fallback message quality.** `revise_visit_
  review`, `create_fast_review_correction`, and `bulk_correct_review_
  queue_items` each already avoid an unhandled `500` for a `Review
  ProvenanceError` via their own pre-existing trailing `except ValueError`
  catch-all, but that branch returns a generic message ("The reviewed
  Visit could not be revised.", etc.) rather than the specific `str(
  error)` code `create_review_label`/`reclassify_review_label_provenance`
  now both give. Not a `500`, not data-loss, not a regression -- a minor
  message-quality inconsistency across four endpoints that all reach the
  same validation function. A follow-on could add an explicit `except
  ReviewProvenanceError` clause to each of the three for message
  -consistency, but none currently reproduces this milestone's own
  acceptance bar ("HTTP 500 ... unhandled"), so it was left out of this
  narrow fix.
- Every other v9/Hard-Negative-v1-disclosed item this milestone's own
  non-goals list excludes (Gate A field-proof, the second true-latency
  cohort, the 3+-subject cohort, the two remaining ambiguous-fragmentation
  units, the ~13 untraced `blocked_missing_evidence` records, the
  Gate B detector-sourced-evidence residual) is unchanged and out of
  scope here, as instructed.

## Decision

**A.**

The v9-disclosed `HTTP 500` is reproduced through the real endpoint (not
the domain function directly), with a captured pre-fix traceback proving
`ReviewProvenanceError` as the unhandled cause. The exact missing
exception boundary is proven, not assumed (`create_review_label`'s own
`try`/`except`, missing exactly the clause its closest sibling `
reclassify_review_label_provenance` already carries). The chosen `HTTP
400`/`detail=str(error)` contract is repository precedent, not intuition
-- the identical convention already used for this identical exception
type at that sibling endpoint. Invalid provenance (three distinct
`ReviewProvenanceError` causes, across two different `review_origin`
values) now returns a clean `400` and persists nothing, confirmed via the
one API-visible surface (`correction_history`) that is not itself
filtered by the same authority rule under test. The provenance
requirement is unweakened: `agent_diagnostic`/`imported_curated` still
strictly require `reviewer_identity`, with zero changes to `review_
provenance.py`. Valid reviews (every origin) are unaffected. Reviewed
truth is proven not just absent-by-default but actively non-overwritable
by a failed request against a Visit that already carries real reviewed
truth. The audit trail creates no misleading successful-review record for
a failed request, confirmed directly. An unrelated, genuinely unexpected
exception is proven -- not assumed -- to still surface unmasked, via a
monkeypatched regression exercising the real endpoint. The scope check
traced every endpoint reaching the same validation function and found no
other endpoint reproducing the identical omission (three others already
avoid a `500`, with a disclosed, minor, out-of-scope message
-quality gap). Tier 1 clean (61/61, 7 new tests). Tier 2 clean (206/206
across 11 directly-traced files, 0 regressions). Tier 3 correctly not run,
with the "cross-cutting" decision criterion stated and satisfied against
the actual 8-line diff. Zero new `ruff` findings, confirmed via baseline
isolation. Every item in this milestone's own acceptance bar (§14) is met.

**Ready for ChatGPT acceptance review.**
