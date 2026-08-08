# Reviewed appearance intervals as deterministic replay Visit truth

Status: Observation Engine v2 Stage 6.17 engineering-workflow contract, closing the
acceptance gap Stage 6.11/6.16 both disclosed and left unresolved: a temporal-review
replay export's `visits` list was always empty, so `appearance_recall`/`proposal_precision`
and every fragmentation/duplicate/incorrect-merge Visit-level metric were structurally
`0.0`/meaningless regardless of tracker quality. This stage converts explicit,
human-reviewed `AppearanceInterval`s into deterministic `replay.ExpectedVisit` facts. It
changes no detector, tracker, reconnect, burst, evidence-scoring, or product behavior.

## Hard truth boundary

Only an explicit, reviewed `temporal_annotation.AppearanceInterval` may create an
`ExpectedVisit`. Never: detector output, tracker output, a product `Visit` record, a
`ReviewLabel`, a burst event, a motion event, or frame-level `yes` truth scanned on its
own. Species identity is never used -- only the reviewer's own coarse `broad_class`
(from the interval's own reviewed boxes) and, when explicitly established, a Zone.

## Conversion: `temporal_annotation._expected_visits_from_appearances`

Each *eligible* `AppearanceInterval` becomes exactly one `ExpectedVisit`
(`appearance_ids=(appearance_id,)`) -- a 1:1 conversion, never an invented grouping of
multiple appearances into one Visit. `build_replay_export` calls this once, using the
same `frames_by_id` capture-manifest lookup its own `appearances` export already uses,
and returns `(visits, exclusions)`.

### Eligibility

Supported (produces a Visit):

- a normal bounded interval, an instantaneous/single-frame appearance, uncertain entry,
  uncertain exit (`AppearanceInterval.entry_uncertain`/`exit_uncertain` are retained on
  the Visit as provenance, never block export);
- a reconnect-spanning interval: start/end offsets are the Stage 6.8 session-relative
  `session_offset_ms`, exactly like the existing `appearances` export, so a Visit's
  bounds are correct even when its two endpoints came from different connections and had
  different, non-comparable raw `source_offset_ms` values;
- same-vs-separate appearance review: two appearances that overlap in session time and
  have *at least one* side marked `continuity_ambiguous=True` are a reviewer-acknowledged
  configuration -- both still export as independent Visits (the reviewer's own recorded
  intervals are respected, not merged or invented into one).

Not supported (excluded, always reported by `appearance_id` and reason in the export's
`visit_truth_exclusions`, never silent):

| Reason | Meaning |
| --- | --- |
| `ambiguous_endpoint_truth` | Either endpoint frame's own `whole_frame_truth == "ambiguous"` -- the review itself could not confirm the sighting, not merely a timeline-crossing acknowledgment. |
| `unscorable_endpoint_truth` | Either endpoint frame is `yes_but_unscorable` -- present but explicitly marked not usable as scorable truth. |
| `same_or_separate_continuity_unresolved` | This interval overlaps another in session time and *neither* side is marked `continuity_ambiguous` -- genuinely unresolved whether they are the same Visit reviewed twice or two truly separate simultaneous Visits, so neither exports rather than guessing. |
| `missing_session_timeline` | Either endpoint lacks a derived `session_offset_ms`. |
| `reversed_interval` | The derived start offset is after the end offset. |
| `invalid_endpoint` | Either `start_frame_id`/`end_frame_id` is absent from the capture manifest or the annotation set's own frames. |

A duplicate `appearance_id` within one annotation set is not a soft exclusion: it is a
structural identity corruption (two intervals would collide under the same deterministic
`visit_id`) and `_expected_visits_from_appearances` raises `TemporalAnnotationError`
(`duplicate_logical_identity`) rather than silently keeping one and dropping the other.

Deliberately *not* an exclusion: `continuity_ambiguous=True` on a *non-overlapping*
interval. That flag's pre-existing meaning (see
[session-timeline-contract.md](session-timeline-contract.md)) is a technical
acknowledgment that a long span cannot be proven continuous purely from reconnect
provenance -- not a statement that the sighting itself is doubtful. Real attempt-3
evidence (nine directly reviewed positive frames plus three real high-resolution bursts,
all at the same feeder perch, spanning the visit's start/middle/near-end) is exactly the
case this distinction exists for: treating it as ambiguous would have permanently
excluded the one appearance Stage 6.16 was built to measure.

### Why an eligible Visit is never itself `ambiguous=True`

`ExpectedVisit.ambiguous` remains in the schema (other manifest sources may still use
it), but this conversion never sets it: the matcher treats `ambiguous=True` as "set this
Visit aside, never eligible to match" (`replay._match`), which would silently reproduce
the exact structural-zero problem this stage exists to fix. Every interval confident
enough to pass eligibility is exported as a fully scorable Visit; anything not confident
enough is excluded outright and reported honestly, never exported half-committed.

## Deterministic identity

`visit_id = f"visit:{appearance_id}"` -- derived only from the reviewer's own semantic
appearance identity, never an absolute path, filesystem order, PID, or wall-clock value.
Repeated export of an unchanged review packet, and export of the identical packet from
two independent absolute filesystem roots, reproduce byte-identical `visits` content
(verified both by a hardware-free two-root test and by a real attempt-3 repeated-export
check -- see Real offline acceptance below).

## Provenance carried onto `ExpectedVisit`

Additive, optional fields (safe defaults, so any pre-Stage-6.17 manifest, or one built by
a different caller, is unaffected):

- `broad_class: str | None` -- the reviewed coarse class from the interval's start (or,
  failing that, end) frame's own primary reviewed box; `None`, never fabricated, when
  neither endpoint carries a reviewed box.
- `zone_id: str | None` -- populated only from a new, optional
  `AppearanceInterval.zone_id`. There is no other Zone concept anywhere in the Stage
  6.6+ temporal-review pipeline, so every session reviewed before this stage, and any
  appearance where a reviewer never established one, honestly stays `None`.
- `entry_uncertain`/`exit_uncertain: bool` -- mirrors the source interval.
- `source_capture_frame_ids: tuple[str, ...]` -- the interval's own start/end reviewed
  frame identities (deduplicated for an instantaneous appearance), an explicit join path
  independent of `appearance_ids`.
- `reviewer: str | None` -- the start (or end) frame's own `Provenance.reviewer`.

`replay.ExpectedVisit` and `replay_io._visit` gained these fields; `replay_io.write_replay_report`'s
existing `asdict(item)` serialization needed no change.

## Matcher and metrics: unchanged

`replay._match` is untouched. No matching threshold changed. The only metrics-side
addition is `replay._zone_attribution_metric`, an honest computation reading only
already-produced `matches`/`proposals`/`manifest.visits` (never new provider facts,
never a matcher change): `zone_attribution_accuracy` moves from a permanent
`insufficient_truth` stub to a real value once at least one matched Visit carries
`zone_id` truth, and stays `insufficient_truth` when none does -- exactly the same
truth-dependent-state convention every other metric in this module already follows.

## Evidence-benchmark and lineage compatibility

No redesign: an `ExpectedVisit` produced here joins to `VisitProposal`/`EvidenceCandidate`
exactly the way every other Visit-level fact already does -- temporal overlap for
proposal matching, and the unchanged Stage 6.14
[reviewed-replay-lineage-contract.md](reviewed-replay-lineage-contract.md)
`source_capture_frame_id` mechanism for evidence-candidate joins. `evidence_benchmark.py`
references neither `ExpectedVisit` nor `.visits` at all and needed no change.

## Real offline acceptance

`temporal-review-export --target replay` was re-run against four existing reviewed
packets (no camera run); `input_fingerprint` stayed byte-identical to each session's own
prior export for attempt-2/attempt-3 (frames genuinely unchanged, only `visits` newly
populated), and for session-03/04 differs only because their own on-disk exports
predated Stage 6.14's additive source-lineage fingerprint fields -- an unrelated,
pre-existing gap, not a Stage 6.17 regression (frame counts and reviewed truth are
identical either way). A repeated real export reproduced a byte-identical payload.

Because Visit-level replay metrics depend only on each `VisitProposal`'s own
start/end/zone -- never frame identity -- this stage's real acceptance re-scored each
session's already-real-CUDA-verified proposals (from the existing Stage 6.11/6.16
recorded reports) against the newly-populated manifests through the completely
unmodified `replay.ReplayRunner`/`_match`, with no inference and no live Camera Node.
`tracks_started`/`tracks_confirmed`/support-hierarchy counts reproduced byte-identical to
the original reports in every case, confirming the reconstruction is faithful. One
disclosed limitation: frame-identity-joined sub-metrics (`frame_level_animal_recall`,
`tracks_spanning_multiple_connection_segments`) only reproduce correctly when the
recorded report's own frame-identity root matches this stage's fresh export exactly
(true for attempt-2/attempt-3; for session-03/04 those specific sub-metrics should be
read from the original, unaffected reports instead) -- Visit-level metrics are
unaffected by this either way. See the Stage 6.17 acceptance report for full numbers.

## Authority and limitations

No command in this stage opens the product database, changes the detector, tracker,
reconnect continuity, burst scheduler, evidence scorer, session timeline, Privacy/Ignore
configuration, or monitoring policy, or grants Stage 7 authority. This remains
engineering benchmark truth, not product truth: it never reads or writes a product
`Visit`, `ReviewLabel`, or `Observation`, and a product `false_positive` label can
neither create nor suppress an `ExpectedVisit`. `temporal_annotation.py` remains on the
existing structural no-product-repository-import test list unchanged.
