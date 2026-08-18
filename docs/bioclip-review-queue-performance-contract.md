# BioCLIP Status / Review Queue Performance contract

Status: BioCLIP Status / Review Queue Performance v1 engineering-workflow
contract, following [v0.1 Release Hardening v1](roadmap-history.md) and
preceding v0.1 Release Candidate / Clean-Machine / Invite-Beta Acceptance.

## Problem

Real packaged Windows/GPU acceptance for the immediately preceding
hardening milestone exposed a severe pre-existing performance defect,
predating that milestone and unrelated to its own changes: with BioCLIP
enabled and a real review backlog, `GET /api/dashboard/summary` took
approximately 119.5 seconds; the direct in-process `dashboard_summary()`
call took approximately 40.6 seconds (44.9 seconds on repeat). It had been
hidden because normal packaged Windows deployments were using the
disclosed `--skip-bioclip-runtime` workaround for an unrelated, now-fixed
BioCLIP/idna packaging conflict.

## Root cause

`get_bioclip_status()` inspects local filesystem/model-bundle state
(resolves the model directory and every configured artifact path, opens
and validates the precomputed embedding-cache `.npz` archive twice,
computes SHA-256 digests of the labels and model-config files, and checks
four optional runtime packages via `importlib.util.find_spec` plus the
installed OpenCLIP distribution version via `importlib.metadata.version`,
itself an `email`-format metadata-file parse). None of this touches the
database or any per-item state -- it is pure environment/configuration
inspection.

`_review_identification_summary_for_item` (`product_repository.py`) is
built once per Review Queue item and, for each item, independently
re-resolved the *entire* model-adapter registry -- `_model_adapters()`,
which in turn calls `get_local_detector_status()`, `get_megadetector_
status()`, and `get_bioclip_status()` -- from **three separate places**:

1. `proposal_adapter = _model_adapter_for_detection_run(...)`, when the
   item has an existing `DetectionProposal`.
2. `suggestion_adapter = _model_adapter_by_id(...)`, when the item has an
   existing pending `SpeciesSuggestion`.
3. `selected_adapter = self._select_review_identification_adapter(...)`,
   **unconditionally**, even when its result goes unused (a `suggestion_
   adapter` from (2) takes priority when present).

A fourth, semantically distinct call -- `candidate_pack_setup_status =
get_bioclip_status(_bioclip_config(pack_labels))`, scoped to the item's
own Stream candidate pack -- ran once more whenever the resolved adapter
was BioCLIP. None of these four call sites were aware of each other or of
sibling items in the same request. For the real ~87-item backlog that
exposed the defect, this produced on the order of ~200 `get_bioclip_
status()` calls (confirmed independently below) in a single `dashboard_
summary()` request -- each one repeating the full filesystem/model-bundle
validation and runtime-package inspection from scratch.

`_review_queue_items()` -- the sole place that builds a `ReviewQueueItem`
with an attached `.identification` summary -- is reused by well over a
dozen call sites: `dashboard_summary()`, every `review_queue_count=len(
self._review_queue_items(session))` computation (health/status responses
and every review-mutation response), `navigate_fast_review_queue`, and
`_review_queue_item_by_target` (a single-item lookup that still recomputes
the *entire* queue -- a separate, disclosed, out-of-scope inefficiency, see
"Remaining hotspots" below). A second, independent hot loop, `prepare_
review_queue_species_suggestions` (the bulk species-suggestion batch
preflight, bounded to 25 Visits per request), called `_review_
identification_summary_for_item` once per Visit in its own `for` loop with
no shared context either.

## Fix: resolve once per operation, thread it through

`_ReviewAdapterStatusContext` (`product_repository.py`, a small `frozen`
dataclass) resolves `_model_adapters()` once and exposes a `bioclip_
status_for_candidate_pack(candidate_labels)` method that memoizes the
pack-scoped BioCLIP call by the exact candidate-label tuple. `_review_
queue_items()` and `prepare_review_queue_species_suggestions()` each
resolve one context before their loop and pass it to every `_review_
identification_summary_for_item(..., adapter_status=context)` call inside
it; `_model_adapter_by_id`, `_model_adapter_for_detection_run`, and
`_select_review_identification_adapter` each accept an optional `model_
adapters` snapshot and reuse it instead of independently calling `_model_
adapters()`. Every other call site (single-item Review Queue API routes --
`get_visit_identification_assistant`, `start_visit_identification_
assistant`, `identify_review_queue_item`, and others) omits the parameter
entirely and resolves a fresh context inline, exactly reproducing the
original always-fresh-per-call behavior with zero change.

This is deliberately **not** a process-level or persisted cache. A `_Review
AdapterStatusContext` lives for exactly the duration of one bounded
repository call and is discarded afterward; the next `_review_queue_items()`
call (the next Dashboard load, the next Review Queue poll) resolves current
status from scratch. A configuration/environment change is visible at the
next such boundary, never hidden behind a stale in-process value -- proven
directly by `test_status_change_is_visible_at_the_next_operation_boundary`.

The pack-scoped memoization is keyed on the candidate-label tuple, not
folded into the single adapter-registry-wide status, because it can
legitimately differ per Stream: a Stream-specific candidate pack
referencing a label outside the locally configured embedding bank
correctly reports unavailable even while BioCLIP itself is generically
available. `test_multi_stream_candidate_packs_resolve_independently_
within_one_operation` proves two Streams with two different packs inside
one operation each resolve their own correct, independent pack status
while the call count stays bounded (not proportional to item count).

### Why no broader/global cache was necessary

Profiling (below) showed per-operation resolution alone collapses call
count from linear-in-item-count to a small constant (2, occasionally 3 for
a multi-Stream backlog) regardless of backlog size. That single, bounded
fix fully explains and resolves the reported defect; no cross-request
cache, TTL, or invalidation policy was needed to hit the milestone's
performance acceptance bar, so none was added -- consistent with the
milestone's explicit preference for the smallest semantics-preserving
correction over a cache built to make a benchmark green.

## Correctness preserved

A byte-for-byte diff of every review item's identification fields
(`status`, `message`, `adapter_id`, `adapter_name`, `adapter_kind`,
`can_run`, `unavailable_reason`, `setup_status`, `candidate_pack_id`,
`candidate_pack_warning`, `suggestion_count`, `proposal_count`) across a
41-item hermetic backlog, computed once on the exact unmodified starting
HEAD and once on the fix, is identical. Nine new deterministic tests in
`tests/test_review_queue_bioclip_status_performance.py` cover: call count
stays bounded as backlog size grows (parametrized 3 and 12 items); `GET
/api/dashboard/summary`'s own call count; the independent `species-
suggestions/prepare` batch call count; one operation observes one coherent
status even against a status source primed to disagree with itself past a
small call budget; the negative control above; unavailable-adapter
behavior; multi-Stream/pack independence; and that a bulk correction
still writes correct `ReviewLabel` truth after status sharing. Seven of
the nine fail against the unmodified starting HEAD (confirmed directly);
the remaining two are a negative control and a pure correctness check that
were never expected to fail (neither behavior was ever broken).

## Performance results

See the final task report for exact reproduction commands and
environment. Summary:

- Hermetic (WSL, synthetic backlog): `get_bioclip_status()` call count for
  `dashboard_summary()` dropped from linear growth (19/69/152/292 calls
  for 5/20/45/87 review items, ~3.3-3.8 calls/item) to a flat 2 calls
  regardless of item count -- confirmed at every tested size.
- Real packaged Windows/GPU host, exact starting commit (`293e55c`), the
  real 87-item backlog that originally exposed the defect: `GET
  /api/dashboard/summary` measured 50.0 seconds. A single `get_bioclip_
  status()`-triggering call (`GET /api/model-adapters`) alone blocked the
  server's event loop badly enough that a concurrent, completely
  unrelated trivial endpoint (`GET /api/product/instance`, no DB access)
  took 40 seconds to respond -- direct evidence the defect was not merely
  slow, but could stall the whole single-process API for any concurrent
  request.
- Same real packaged Windows/GPU host, same real userdata (same
  `instance_id`, same 87-item backlog, confirmed via matching
  `needs_review_visit_count`/`actionable_animal_visit_count`), fixed
  commit (`a423899`): `GET /api/dashboard/summary` measured 1.96 seconds
  (cold) and 1.99 seconds (repeat) -- a 25.6x improvement. `GET
  /api/review-queue` (the full identification-summary list, not just
  headline counts) measured 3.09 seconds for the same 87 items. `POST
  /api/review-queue/species-suggestions/prepare` (the second fixed hot
  loop) measured 0.33 seconds. BioCLIP reported `status=available`,
  `runtime_available=true`, `can_run=true` throughout, and real backlog
  items correctly resolved `adapter_id=bioclip_2` with correct
  `can_run`/`status` values -- the species-suggestion path is unaffected.

## Remaining hotspots (disclosed, out of scope for this milestone)

- `_review_queue_item_by_target` resolves the *entire* review queue to
  find one item by id. This is a real, separate inefficiency (unrelated
  to BioCLIP status specifically) affecting single-item Review Queue
  lookups; it is unaffected by, and unrelated to, this fix.
- General SQLAlchemy/Pydantic per-item construction overhead inside
  `_review_queue_items()` (session queries, ORM instance construction,
  response-model validation) remains and scales with item count, as it
  must -- it is proportional, ordinary work, not a repeated-validation
  defect. Hermetic profiling after this fix still attributes the
  remaining `dashboard_summary()` time to this category, not to BioCLIP.

Neither is addressed here; per this milestone's explicit scope boundary,
fixing them would be general application performance cleanup without the
specific evidence this milestone was chartered to act on.
