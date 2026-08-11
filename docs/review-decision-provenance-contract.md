# Review Decision Provenance / Truth Boundary v1 contract

Status: Phase 1 "Trustworthy Single-Site Observatory" milestone (see
[roadmap.md](roadmap.md)), motivated by a real truth-boundary gap the
2026-08-10 Detection Quality Accounting v1 and Visit Continuity milestones'
own Part 7 audits surfaced: `ReviewLabel` (`product-doctrine.md`'s "Review
Decision") had no durable reviewer-origin identity at all. A real
`ReviewLabel` an LLM/agent wrote through the genuine `POST /api/review-labels`
path -- exactly what the 2026-08-10 fresh-cohort candidate-004/005/006
labels were -- was structurally indistinguishable anywhere downstream (Bird
Log, reviewed-only Dataset Export, classifier training manifests, analytics)
from a genuine human correction, distinguishable only by free-text prose in
`notes`, which nothing enforced. See the
`visit-continuity-provisional-admission-fix-v1` and
`observation-engine-false-positive-admission-2026-08-10` project memories
for that finding's own record.

## Boundary

This closes the gap for the *live product* `ReviewLabel` record. It does
**not** create a second review system, a user-account/identity system, or
roles/permissions. `Review Decision` (implemented as `ReviewLabel`) remains
the one product concept; this contract adds provenance/authority semantics
to it. It also does not tune MDv5, change the 0.1 production threshold,
promote a shadow admission policy, or revisit Visit assembly -- see
"Explicit non-goals" in the milestone instructions this contract implements.

## The provenance model

`mockingbird.review_provenance` (pure, dependency-free: no SQLAlchemy, no
FastAPI, no product-repository import -- importable from both
`product_repository.py` and a lightweight script) is the one place that
defines and answers "who/what produced this Review Decision, and is it
observationally authoritative?":

- **`"human"`** -- a person intentionally reviewed the evidence through a
  user-facing/product review action (Review Queue correction, Fast Review,
  Visit Detail correction, bulk correction, revise, reopen). Authoritative.
- **`"imported_curated"`** -- truth imported from a dataset/manifest/process
  whose human-reviewed provenance is explicit and separately governed. The
  only current user of this origin is this product's own first-run demo
  seed content (`ProductRepository._seed_session`, `reviewer_identity=
  "mockingbird_demo_seed_data"`) -- illustrative, product-authored fixture
  content, not a live claim about a real animal at a real site. Authoritative
  *only* because the specific importer already vouches for it explicitly
  (see "Do not equate arbitrary imports with human truth" below); requires a
  named `reviewer_identity`.
- **`"agent_diagnostic"`** -- an LLM, model, automation, test harness, or
  other non-human process assessed the evidence. Never authoritative.
  Requires a named `reviewer_identity` (which model/run/session produced it)
  so a diagnostic assessment is honestly attributable, not an anonymous
  blob.
- **`"legacy_unattributed"`** -- a row that already existed when the
  `_migrate_to_review_decision_provenance` schema migration (v31 → v32) ran,
  backfilled to this explicit sentinel by that migration. Reviewer origin
  cannot be *proven* from persisted data, but the exhaustive Part 1 creation-
  path trace this milestone performed found no path that could reach a real
  product database before this milestone existed except: direct interactive
  human use (the only path the product's own UI ever exercised), demo-seed
  content (separately marked `imported_curated`), and the specific rows this
  milestone identifies and repairs by name (see "The three 2026-08-10 rows"
  below). Given that, treating a *pre-existing* `legacy_unattributed` row as
  continuing to be authoritative is a deliberate, documented backward-
  compatibility policy choice -- not a claim that it is positively known to
  be human -- required by "Avoid breaking existing users' history
  unnecessarily" in this milestone's own instructions. A **new** row can
  never claim this origin (`is_creatable_review_origin` rejects it); it only
  ever comes from the migration's own one-time backfill.
- **`None`** (no explicit origin) -- a create request made after this
  contract existed that omitted the field. Never authoritative. Because the
  migration backfills every pre-existing row away from `None` to
  `legacy_unattributed`, `None` unambiguously means "omitted at creation
  time" from this point forward -- `is_authority_eligible` needs no
  activation-boundary timestamp to distinguish a genuinely legacy row from
  a new one that simply didn't send the field.

`is_authority_eligible(origin) -> bool` is the one function every consumer
calls; nothing re-derives the answer from its own string comparison.
`AUTHORITATIVE_ORIGINS = {"human", "imported_curated", "legacy_unattributed"}`.

Provenance is separate from outcome: `origin` never changes the `label`
vocabulary itself (`northern_cardinal`, `false_positive`, `unknown_bird`,
...), and an agent's diagnostic label carries exactly the same vocabulary a
human correction would -- only its eligibility to become truth differs.

## Schema (v31 → v32)

`review_labels` gains two nullable `TEXT` columns, `review_origin` and
`reviewer_identity`, added by `_migrate_to_review_decision_provenance`
(`src/mockingbird/storage/database.py`). The migration:

- backfills every pre-existing row's `review_origin` to
  `"legacy_unattributed"` (never `NULL`, never a fabricated `"human"`);
- never touches an existing row's already-established `review_status`/
  `reviewed_label` -- continuity of existing reviewed history is a property
  of the migration's own non-retroactivity, not a claim this contract makes
  about who reviewed a row;
- is defensive against a database that reaches this migration before
  `review_labels` exists at all (`has_table` check) -- true for a real
  upgrading database only in the sense that the table has existed since
  schema v1, but this guards the same class of minimal-synthetic-fixture
  case `_read_recorded_schema_version` already guards for the schema-version
  table itself (see `tests/test_camera_health.py`'s v20/v21 migration-chain
  fixtures, which intentionally create only the tables their own scenario
  touches).

No CHECK constraint restricts `review_origin`'s values at the SQL layer,
matching this codebase's existing convention: new columns added to an
*existing* table (`fast_review_reversals`, `review_label_revisions`,
`observation_confidence_evidence`) are validated at the application layer,
not retrofitted with SQL constraints that SQLite cannot cheaply add to an
existing table.

## Authority gating: one choke point

`ProductRepository._create_review_label_in_session` is the sole place that
ever sets `VisitModel.review_status`/`reviewed_label` to `"reviewed"` or
`EventModel.review_status` to `"reviewed"` (confirmed by an exhaustive Part 1
trace: no other code path writes these fields to `"reviewed"`). It now:

1. validates the caller-supplied `review_origin`/`reviewer_identity`
   (`review_provenance.validate_review_origin` -- rejects an unsupported
   origin, a non-human-verifiable origin missing an identity, or a `"human"`
   claim whose own identity/notes self-discloses non-human origin);
2. always persists the `ReviewLabelModel` row, carrying its provenance,
   regardless of authority ("do not delete or pretend they never happened");
3. mutates Visit/Event truth **only** when `is_authority_eligible(origin)`
   is `True`. A non-authoritative Review Decision is recorded as a visible,
   auditable row, but the Visit/Event it targets is left exactly as it
   already was -- no `review_status` flip, no alert sync
   (`_sync_review_alert`/`_sync_journal_milestone_alert`, both already fully
   reconciling in either direction so calling them only on the authoritative
   path is sufficient, not merely safe).

Because every downstream consumer (Bird Log/Wildlife Journal/Insights,
Dataset Export, classifier training manifests, `dataset_ready`) keys off
`review_status`/`reviewed_label` -- never off raw `ReviewLabel` row
existence -- gating this one write choke point is sufficient to make all of
them correct without touching their own read paths. Defense in depth is
still applied at a few read-side "resolve the effective label" helpers
(`_latest_label`, `_effective_review_label_models`,
`_current_effective_review_label_model_for_visit`, the `has_conflicting_
corrections`/`latest_label_model` closures inside dataset-quality/
classifier-readiness/classifier-manifest reporting, and `_visit_is_dataset_
ready`/`_event_is_dataset_ready`'s own fallback existence checks) so a
future code path that (incorrectly) sets `review_status` some other way
still cannot make a non-authoritative row appear as truth in these specific
resolvers.

`revise_visit_review`/`reopen_visit_review` are a deliberate exception:
unlike plain create/Fast Review/bulk correction (which have a meaningful
"recorded but not applied" non-authoritative behavior), a revision or reopen
exists *only* to mutate already-established truth, so a non-authoritative
attempt is rejected outright (`ReviewRevisionConflictError`,
`review_revision_requires_authority`/`review_reopen_requires_authority`,
mapped to `400 Bad Request`) rather than silently no-op'ing.

## API surface

`ReviewCorrectionCreate`, `VisitReviewRevisionCreate`,
`VisitReviewReopenCreate`, `FastReviewCorrectionCreate`, and
`ReviewQueueBulkCorrectionRequest` each gain optional `review_origin: Review
Origin | None = None` and `reviewer_identity: str | None = None` fields.
Omitting `review_origin` **never** defaults to `"human"` at the API/
repository boundary -- see `review_provenance.is_authority_eligible`'s own
docstring. The product's own interactive frontend (`web/src/api/client.ts`)
is the one place that explicitly stamps `review_origin: "human"` on every
request its review-correction functions issue, because that client code
path *is* the product's interactive review UI -- an explicit assertion by
the surface that legitimately represents human use, not a server-side
default applied to a caller that stayed silent. Any other HTTP caller
(a script, a future automation, an LLM agent) gets no such stamp.

`ReviewLabel` (the response shape) gains `review_origin: ReviewOriginStored
| None`, `reviewer_identity: str | None`, and a server-computed
`is_authoritative: bool` -- never client-supplied directly, so a caller
cannot simply assert authority without an eligible origin.
`VisitReviewHistoryEntry` gains the same `review_origin`/`is_authoritative`
pair (fail-safe default `is_authoritative=False`) so the Visit correction-
history view can distinguish a diagnostic entry without the frontend
re-implementing the policy.

`ReviewOrigin` (the 3 creatable values) and `ReviewOriginStored` (those 3
plus `"legacy_unattributed"`) are deliberately two different Pydantic
`Literal` types: a *create* schema field uses the narrower one (a new row
can never claim to be legacy); a *response* schema field uses the wider one
(a real backfilled legacy row must round-trip through the API without a
validation error).

### Bounded maintenance endpoint

`POST /api/review-labels/{review_label_id}/reclassify-provenance`
(`ReviewLabelProvenanceReclassifyRequest`) is not part of the interactive
product flow and is not called by the frontend. It exists so a bounded,
auditable script (`scripts/repair_review_label_provenance.py`) can durably
repair one already-identified row's provenance without direct database
surgery. `ProductRepository.reclassify_review_label_provenance`:

1. optionally checks `expected_current_review_origin` (an idempotency-style
   safety check -- fails loudly with `ReviewProvenanceConflictError`/`409`
   if the row already changed since it was last inspected, rather than
   silently re-deriving state from an already-repaired row);
2. updates `review_origin`/`reviewer_identity`;
3. re-derives the target Visit's (or Event's) `review_status`/
   `reviewed_label` from scratch from its own remaining authoritative rows
   (`_recompute_visit_review_truth`/`_recompute_event_only_review_truth`) --
   a row that turns out non-authoritative can no longer justify a
   "reviewed" status it previously (incorrectly) established; if another
   authoritative row already exists for the same target, that one becomes
   effective instead;
4. reconciles the "ready for review"/journal-milestone alerts the same way
   a live correction would (`_sync_review_alert`/`_sync_journal_milestone_
   alert`, safe to call unconditionally in either direction).

It never deletes the row, its `label`, or its `notes`.

## Part 8: the three 2026-08-10 rows

Identified with direct, verified evidence (a live, reachable Windows dev
deployment's real `GET /api/review-labels`, not assumption from documentation
alone): exactly three real `ReviewLabel` rows exist in that database,
`review-label-001`/`review-label-002`/`review-label-003`, targeting
`visit-observation-candidate-004`/`-005`/`-006` (the "fresh cohort" session;
see the `fresh-cohort-detection-quality-2026-08-10` project memory), each
`notes` field carrying the established disclosure convention
(`"[AGENT VISUAL REVIEW -- 2026-08-10 fresh-cohort field session, not
independently human-confirmed] ..."`). No rows for the *original* three
candidates (001/002/003 from the earlier 25.3-minute smoke) were found in
this database -- direct evidence against `detection-quality-accounting-
contract.md`'s own prose claiming both sets were written through the real
API; that prose is more likely describing the offline `DIAGNOSTIC_EXAMPLES`
manifest registration (`scripts/run_detection_quality_accounting.py`), not a
real persisted `ReviewLabel`. See the milestone's final report for exactly
what was repaired and verified.

`scripts/repair_review_label_provenance.py --base-url <url>` (dry run by
default; `--apply` to write) discovers candidates generically: any
currently-effective `ReviewLabel` whose own `notes` self-discloses non-human
origin via `review_provenance.discloses_non_human_review` -- not a hardcoded
ID list -- so it also covers any other row this same disclosure convention
might exist for, without rewriting anything that does not self-disclose.

## Agent-assisted field-testing workflow (Part 10)

A future Claude/LLM-assisted Camera Node cohort uses the *same* `POST
/api/review-labels` endpoint a human correction uses -- no second review
product -- but explicitly sets `review_origin: "agent_diagnostic"` and a
named `reviewer_identity` (for example `"claude-agent-visual-inspection-
<date>"`, continuing this codebase's own established disclosure
convention in `notes` too, for human-readable redundancy). This:

- durably records the diagnostic assessment (inspection notes, suspected
  false positives, localization problems) as a visible, auditable
  `ReviewLabel` row;
- never flips the target Visit/Event to `"reviewed"`;
- is excluded from reviewed-only Dataset Export, classifier training
  eligibility, and Bird Log/Wildlife Journal by construction;
- remains fully available to Detection Quality Accounting's own
  `evaluation_governance.EvaluationExample(status="diagnostic_only", ...)`
  representation for qualitative diagnosis, exactly as the three 2026-08-10
  rows already are.

A genuine human Review Decision through the normal product review UI is
completely unaffected and remains the only way to establish or correct
durable reviewed Observation truth.

## Observation relationship chain (Part 11)

Source → Stream → Zone → Activity Session → Visit → Evidence → Detection
Proposal → Interpretation → **Review Decision** → Observation →
Export/Analytics (`product-doctrine.md`). This contract's authority gate is
exactly the boundary between "Review Decision" and "Observation": only an
authority-eligible Review Decision can establish or correct the durable
reviewed truth the doctrine calls Observation (implemented today as a
reviewed Visit). An agent/model Interpretation or diagnostic assessment can
support a human reviewer (a suggestion, a hard-negative flag, a QA note) but
cannot itself cross that boundary. This milestone does not implement a
wholesale `Observation` object migration -- the current `VisitModel`/
`EventModel` `review_status`/`reviewed_label` fields remain the
implementation of that durable truth, per the documented mapping in
[glossary.md](glossary.md).

## Authority and limitations

No auth/account/identity system was introduced, and none is required by
this contract: "human" provenance is asserted by the interactive product
surface that legitimately represents human use (the frontend client), not
verified against a signed-in identity. This matches the product's existing
security model (local-first, single-user, no auth anywhere else in the
product either) and the milestone's own explicit non-goal ("'Human review'
does not require a full identity system yet"). Consequently, any raw HTTP
caller with no auth boundary at all could technically claim `review_origin:
"human"` directly against the API; the threat model this contract addresses
is architectural/accidental conflation (an agent's own diagnostic output
silently becoming authoritative through the *normal* product code path),
not adversarial spoofing over an unauthenticated local API surface -- the
same limitation the rest of this local-first product already has.

`imported_curated` is deliberately narrow in practice: the schema/API
technically accept it from any caller (with a required identity), but the
only real, trusted user of it today is this product's own demo-seed code.
"Imported curated truth may be eligible only where its provenance contract
explicitly supports that use" is enforced by *convention and code review*
for this origin specifically, not by a runtime authorization check -- a
disclosed, deliberate limitation, not an oversight.
