# Reviewed-to-replay evidence identity lineage contract

Status: Observation Engine v2 Stage 6.14 engineering-workflow contract, closing
the integration gap Stage 6.13's real historical acceptance disclosed: a replay
produced through `replay-benchmark` assigns each frame a new, replay-derived
identity distinct from the original reviewed `frame_id`, so reviewed truth could
not automatically link to a replay-produced `EvidenceCandidate` even when both
referred to exactly the same original captured frame. This stage fixes that
lineage only -- no detector, tracker, reconnect, burst, evidence-scoring, Camera
Node, monitoring, product-truth, or authority behavior changes.

## Three distinct identities

- **Original capture-frame identity** (`source_capture_frame_id`): the stable
  identity assigned to the actual retained Camera Node/review frame -- the
  identity a human reviewer's annotation refers to. Set once, at
  [temporal-review-capture-contract.md](temporal-review-capture-contract.md)'s
  `RetainedFrameRecord.frame_id`, and never recomputed downstream.
- **Replay frame identity** (`frame_id`/`media_asset_id` on `FramePacket`/
  `EvidenceCandidate`): the deterministic, input-fingerprint-derived identity
  [observation-replay-benchmark-contract.md](observation-replay-benchmark-contract.md)'s
  `ReplayInput.packets()` has always assigned, unchanged. Required for
  path-independent replay determinism and two-root reproducibility; never
  replaced by the source identity.
- **Derived observation identities**: `DetectionObservation`, `TrackUpdate`,
  `VisitProposal`, and `EvidenceCandidate` identities continue using
  replay-local deterministic inputs exactly as before. This stage adds
  optional, additive source-lineage *provenance* fields alongside them --
  never a substitute identity.

## Propagation

`replay.ReplayFrame` gains three optional, additive fields:
`source_capture_frame_id`, `source_capture_session_id`, `session_sequence`.
`session_offset_ms` is deliberately not duplicated: a reconnect-safe temporal-
review export already feeds the session-relative offset into the frame's own
required `source_offset_ms` (see
[session-timeline-contract.md](session-timeline-contract.md)), and
`content_hash` is already a required top-level `ReplayFrame` fact. All three
are absent (`None`) for a generic, non-temporal-review Stage 2 replay input --
never required for it to work.

`ReplayInput.packets()` copies `source_capture_frame_id` and the frame's own
`content_hash` (as `source_content_hash`) onto each produced `FramePacket`,
alongside the unchanged replay-local `frame_id`. From there:

- `DetectionObservation.source_capture_frame_id` -- set by
  `onnx_provider._observation()` from the inferred frame's own field.
- `TrackUpdate.supporting_source_capture_frame_ids` -- mirrors the existing
  `supporting_frame_ids`, independently deduplicated
  (`frame_tracker.ProviderNeutralFrameTracker._remember`), present only for
  the supporting frames that actually carried known source lineage.
- `EvidenceCandidate.source_capture_frame_id`/`source_content_hash` -- set by
  `frame_driven_provider.FrameDrivenObservationProvider._candidate()` from the
  originating frame.
- `VisitProposal.supporting_source_capture_frame_ids` -- mirrors
  `supporting_frame_ids`, taken from the terminal track's own accumulated
  source-lineage list.

None of these fields feed `evidence_scoring.score_proposal_evidence`'s ranking,
eligibility, or component-score computation -- that module is unmodified and
does not reference any of these field names (a hardware-free structural test
asserts this directly).

## Temporal-review replay export

`temporal_annotation.build_replay_export` explicitly places the original
reviewed `frame_id` into each exported replay frame's own
`source_capture_frame_id`, plus the capture session's own `session_id`
(`source_capture_session_id`) and the frame's Stage 6.8 `session_sequence` --
never only implied through the `path`/`images/<frame_id>.jpg` string, which
remains an unsafe join key (a filename). Content hash, session timeline
ordering, original capture timestamp/source-local facts, and the existing
single-resolution high-resolution-exclusion rule (with its existing honest
`high_resolution_exclusion` report) are all unchanged. Repeated export over an
unchanged review packet remains byte-identical, including the now-included
`source_lineage` block in `input_fingerprint`.

## Evidence benchmark join

`evidence_benchmark._source_lineage_join(manifest, replay_candidates)` builds a
translation from each candidate's own scorer-space identity
(`EvidenceCandidateScore.candidate_id`, i.e. `EvidenceCandidate.media_asset_id`)
to the reviewed original capture-frame identity it provably traces back to:

- A reviewed-manifest-derived candidate's join is trivial -- its own identity
  already *is* the reviewed identity by construction
  (`_to_evidence_candidate` sets `source_capture_frame_id=candidate_id`).
- A replay-sourced candidate joins only through its own explicit
  `source_capture_frame_id`. Coincidental equality between a replay-local
  `frame_id`/`media_asset_id` and a reviewed `candidate_id` is never treated
  as a match (Stage 6.13's own `no_replay_sourced_candidates_matched_
  reviewed_truth_identity` coincidental-equality fallback is removed by this
  stage in favor of this explicit-only join).

`EpisodeResult.identification_source_capture_frame_id`/
`context_source_capture_frame_id` carry each episode's translated join result
(`None` when unavailable) and are the identity every truth-dependent metric
(`useful_identification_rate`, `useful_context_rate`,
`context_subject_visible_rate`, `selected_identification_correctness`,
`selected_context_correctness`, `evidence_latency_from_appearance_ms`) matches
against reviewed truth -- never the raw scorer-space candidate id, a filename,
frame ordering, timestamp equality, or approximate geometry. Purely structural
metrics that need no truth join at all (for example
`episodes_with_identification_candidate`) continue reading the scorer's own
raw candidate id, unaffected. Both fields are also written into each episode's
serialized `episodes[]` entry in the report, so "which reviewed frame did the
selected identification/context evidence actually come from" is directly
readable from the report file.

### Media resolution for a replay-sourced candidate

A replay-sourced `EvidenceCandidate`'s own `media_asset_id` (replay-local,
e.g. `"replay:17"`) is never a key the caller's reviewed-frame-root `media`
mapping can already contain -- that mapping is built from `--review`'s own
`frames/<candidate_id>.jpg` paths, keyed by reviewed identity. Without
correcting for this, every replay-sourced candidate's own rescoring call
would see no image bytes at all and score `candidate_unavailable`
(a hard rejection) regardless of how correct its lineage is, silently
defeating the join's entire purpose -- discovered during this stage's own
real session-04 acceptance run, where it initially produced zero
successfully joined replay-sourced selections despite 282/282 evidence
candidates correctly carrying `source_capture_frame_id`.
`evaluate_evidence_benchmark` now extends `media` (via
`_media_with_source_lineage_fallback`) so a replay-sourced candidate can
decode the exact same bytes a reviewer looked at, using only a source
identity `_source_lineage_join` already verified safe -- never a raw,
unverified `source_capture_frame_id` (a hash mismatch or content-conflict
case must not silently borrow reviewed image bytes either). A
caller-supplied entry already keyed by the candidate's own `media_asset_id`
is never overwritten. This is input preparation the module's own docstring
already scopes to it ("matching candidates to annotations"), not a change
to `evidence_scoring.py`'s ranking/eligibility rules.

`evidence_latency_from_appearance_ms` additionally recovers each episode's
*real* reviewed session id from the joined truth record rather than trusting
`EpisodeResult.session_id` (which, for a replay-sourced episode, is the
replay provider's own run-mode label such as `"replay"`, not a reviewed
session id) -- a direct, low-risk correctness improvement the same join
enables, not a new join mechanism.

## Collision and integrity handling

`_source_lineage_join` never silently picks a side; every case below is
reported with a stable, colon-prefixed limitation code naming the affected
identity/identities, and the affected candidate(s) are excluded from the join
(their translated source id stays `None`) rather than guessed:

- `duplicate_source_identity_conflicting_content` -- two replay-sourced
  candidates both claim the same `source_capture_frame_id` but declare
  different `source_content_hash` values.
- `unknown_reviewed_source_frame` -- a replay-sourced candidate's
  `source_capture_frame_id` does not appear in the reviewed manifest at all
  (for example the replay covered a broader window than what was reviewed).
- `source_hash_mismatch` -- a candidate and its matched reviewed truth
  record both declare a content hash, and they disagree.
- `source_lineage_unavailable` -- replay-sourced candidates were supplied but
  none carry any `source_capture_frame_id` at all (a pre-Stage-6.14 report,
  or a genuinely generic, non-temporal-review replay input).

Separately, `replay.ReplayInput.__post_init__` rejects
(`duplicate_source_capture_frame_id`) a replay *input* that references the
same reviewed source frame more than once among its own frames -- a
structural invariant of one ordered feed, checked before any benchmark ever
runs.

## Backward compatibility

Every new field on `ReplayFrame`/`FramePacket`/`DetectionObservation`/
`TrackUpdate`/`EvidenceCandidate`/`VisitProposal` is optional and additive
with a safe default (`None`/`()`); an older replay input, replay report, or
reviewed-evidence manifest that never set them loads and scores exactly as
before Stage 6.14, byte-for-byte, with generic (non-source-linked) benchmark
behavior unchanged. `evidence_benchmark_io.py`'s dict readers use explicit
`dict.get(...)` per field, so a JSON document missing a Stage 6.14 key simply
yields the dataclass default rather than failing to load. Source-linked
evidence evaluation against such an input honestly reports
`not_evaluated`/`insufficient_truth` with the `source_lineage_unavailable`
limitation rather than guessing a mapping from timestamps or paths. No stored
product data is migrated; this stage never opens the product database.

## Semantic fingerprint

Source-frame lineage is semantic: `ReplayInput.fingerprint` includes a
per-frame `source_lineage` block (mirroring the existing Stage 6.8 `timeline`
block) whenever `source_capture_frame_id`/`source_capture_session_id`/
`session_sequence` are set, so the fingerprint changes when source frame
identity, source content hash, or the source-to-replay association changes,
and stays byte-identical to a pre-Stage-6.14 input when they are absent.
`build_replay_export`'s own `input_fingerprint` computation
(`_replay_export_source_lineage_facts`) is kept in lockstep with
`replay._replay_frame_source_lineage_facts` so a loaded export always
reproduces the same fingerprint `ReplayInput` itself would compute. Absolute
paths, output roots, wall-clock runtime, processing latency, and host/device
information remain entirely absent from every semantic payload this stage
touches -- unchanged, and covered by existing and new hardware-free tests.
Two-root replay reproducibility is preserved: `source_path`/`image_path`
values are not, and never were, part of any fingerprint.

## Real offline acceptance (session-04, two-root; session-01/02 spot-check)

`temporal-review-export --target replay` -> real RTX 4060 Ti
`replay-benchmark --provider frame-driven-onnx-cuda` -> `evidence-benchmark
--replay-report` ran end to end against the real historical session-04
reviewed packet (data/field-acceptance/2026-08-06-stage6.10-representative-
acceptance/session-04/review-out), from two independent absolute filesystem
roots (one inside the repository checkout, one outside it entirely):

- Export, replay, and evidence-benchmark semantic fingerprints were
  byte-identical across both roots at every layer.
- 451/451 replayed frames (17 high-resolution frames honestly excluded, the
  existing single-resolution rule, unchanged), 1679/1679 detections,
  282/282 evidence candidates, 305/305 track updates, and 28/28 proposals
  carried `source_capture_frame_id`/`supporting_source_capture_frame_ids`.
- Tracker/detector counts reproduced the exact pre-existing Stage 6.11/6.12
  numbers for this session (57 tracks started, 28 confirmed) -- proof by
  real-data reproduction, not just code inspection, that detector/tracker/
  reconnect/burst behavior is unchanged.
- 25/28 replay-sourced episodes' selected identification *and* context
  evidence joined directly to reviewed truth (the remaining 3 selected a
  synthetic tracker boundary frame that carries no source lineage by
  construction -- see `frame_tracker.note_reconnect_boundary`/`finalize`).
  Zero lineage-integrity limitations fired (no unknown source, hash
  mismatch, or content conflict).
- `useful_identification_rate` moved from 0.143 (informed only by the
  129 manifest-derived episodes) to 0.176 (now genuinely informed by the 25
  newly joined replay-sourced episodes too); `episodes_with_identification_
  candidate` moved from 31 to 56; `candidate_unavailable` rejections
  dropped from 140 to 17 (the media-fallback fix above).
  `selected_identification_correctness`/`selected_context_correctness`
  remained honestly `not_evaluated` -- this historical corpus never recorded
  `preferred_identification`/`preferred_context` truth, and this stage does
  not invent it.
- Session-01 (63/95 replayable frames) and session-02 (270/393) spot-checks
  confirmed the mechanism is not special-cased to session-04: 100% detection/
  evidence-candidate lineage propagation in both; session-01's single
  confirmed proposal joined identification and context truth directly;
  session-02 reproduced zero confirmed proposals byte-identical to its own
  existing Stage 6.11 replay record (18 tracks started, 0 confirmed) -- an
  unrelated, pre-existing tracker-confirmation fact this stage neither
  causes nor changes.
- A structural no-write snapshot (database SHA-256/size, all 41 tracked
  table row counts, monitoring policies, primary-selection/reviewed-visit/
  review-label fingerprints) taken before the campaign and after session-04,
  and again after session-01/02, was identical every time.

## Authority and limitations

This stage opens no product database, changes no runtime threshold, Ignore
region, or monitoring policy, and grants no Stage 7 authority. It does not
invent reviewed truth: a historical reviewed corpus that never recorded
`preferred_identification`/`preferred_context`/appearance truth still reports
`selected_identification_correctness`/`selected_context_correctness` as
`not_evaluated` after this fix, exactly as before -- lineage makes a join
*possible*, it does not manufacture the human judgment a join would compare
against. `_selection_correctness_metric`'s per-episode reviewed-truth
grouping still keys off `episode_id`, not source lineage, so a replay-sourced
episode's *own* preferred-candidate correctness cannot yet be evaluated even
once such truth exists; this is a disclosed, non-impacting limitation (no
historical reviewed session carries `preferred_*` truth today) rather than a
defect this stage introduces, and is a candidate for a future, separate,
narrowly scoped follow-up.
