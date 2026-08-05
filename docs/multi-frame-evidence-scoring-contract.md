# Multi-frame evidence scoring contract

Status: Observation Engine v2 Stage 6 provider contract.

## Boundary

`mockingbird.observation.evidence_scoring.score_proposal_evidence` ranks the bounded
`EvidenceCandidate` set already retained for one shadow `VisitProposal`. It is a pure,
side-effect-free function: no model inference, no species interpretation, no camera or
network access, and no import of a product repository. It never changes the persisted
effective-primary selection, and its output remains temporary shadow evidence with
`creates_truth=false`.

The scorer only accepts candidates whose `media_asset_id` is listed in the proposal's
`evidence_media_asset_ids` and whose `track_generation_id` matches the proposal's
generation when both are known, so evidence from a different or stale track generation
cannot attach even if an identifier were to collide.

## Signals

Scoring uses only provider-neutral, measurable facts already carried by
`EvidenceCandidate.quality_facts` or derivable from candidate/image bytes:

- track association and detector/tracker support (`track_supported`, `detector_support`,
  `tracker_support`, `supporting_frame_count`)
- subject geometry, containment, and edge clipping (normalized box against frame bounds)
- subject pixel area and area ratio
- temporal alignment (`aligned`, `uncertain`, or `rejected`, from `temporal_alignment` /
  `track_active_at_capture`)
- burst request-to-capture latency (`request_to_capture_ms`), where supplied
- decodability and dimensions (declared or measured from bytes)
- a deterministic sharpness/blur proxy (edge-response RMS over a bounded thumbnail)
- exposure/clipping facts where declared (`underexposed`/`overexposed`) or measured
  (mean-luminance proxy)
- evidence role (`pretrigger`, `detector_confirmed`, `tracked_best`, `final_supported`,
  `alternative`/`alternate`, `high_resolution_burst`, `snapshot_best_frame`,
  `snapshot_context`, `context`)

Species identity and species-model inference are never used; `score_proposal_evidence`'s
source is checked for this by a structural test.

## Selection

For each proposal, candidates are scored independently for two purposes:

- **identification score** favors tracked/high-resolution, sharp, contained, temporally
  aligned frames
- **context score** favors pretrigger/context-role frames over tight identification crops

The best identification candidate and best context candidate are chosen separately by
descending score with a stable `candidate_id` tie-break, and may coincide when only one
usable candidate exists. Up to `max_alternates` (default 3) additional eligible
candidates are retained, ranked by identification score. A bounded `sequence_frame_ids`
list (default up to 8) orders supporting frame identities by source offset for reviewer
context.

A candidate is ineligible (never selected as identification, context, or alternate) when
any hard-rejection reason applies: `candidate_unavailable`, `candidate_undecodable`,
`privacy_masked`, `burst_subject_unverified`, `subject_edge_clipped`, `subject_absent`,
or `subject_too_small`. When every candidate is ineligible, or no candidates are
retained, the selection honestly reports `no_useful_evidence=true` rather than choosing
a weak default.

Privacy/Ignore-masked subjects are excluded upstream: the frame-driven tracker discards
any detection centered inside an excluded region before a track ever forms, so no
evidence candidate is created for a masked subject in the first place. The scorer's own
`privacy_masked` fact check is an additional, currently-dormant defense for a candidate
that explicitly declares itself masked.

## Bounds

`EvidenceScoringBounds` caps candidates considered (16), decoded images (12), analysis
frame bytes (8 MiB), burst frames (3), total temporary bytes evaluated (32 MiB),
candidate metadata bytes (64 KiB), alternates (3), and sequence frames (8). Exceeding a
bound adds a stable limitation code (for example `candidate_limit_reached`,
`decoded_image_limit_reached`, `burst_frame_limit_reached`) rather than failing; scoring
always completes and remains deterministic for a given candidate set regardless of input
ordering.

## Reason and limitation codes

Stable, enumerable strings only: `candidate_unavailable`, `candidate_undecodable`,
`subject_contained`, `subject_edge_clipped`, `subject_too_small`, `track_supported`,
`tracked_frame_continuity`, `temporally_aligned`, `temporal_alignment_uncertain`,
`burst_subject_unverified`, `subject_absent`, `privacy_masked`, `image_blurred`,
`image_underexposed`, `image_overexposed`, `high_resolution_detail`, plus the bound
limitation codes above and `subject_geometry_unavailable` / `sharpness_unavailable` /
`track_support_unavailable`.

## Replay and report integration

The Stage 2 replay report (`REPORT_SCHEMA_VERSION` 3) adds `evidence_selections` (one
`EvidenceSelection` per proposal) and `evidence_fingerprint` (a fingerprint of every
selection's own fingerprint). Both are part of the semantic report and semantic
fingerprint; two replay runs over the same input produce identical selections and
fingerprints. Detector/tracker/burst latency, process/GPU resources, device/runtime
facts, absolute paths, and wall-clock duration remain non-semantic execution facts,
unchanged from Stage 2-5.

New truth-dependent metrics (`useful_identification_evidence`, `useful_context_evidence`,
`useful_primary_rate`, `evidence_subject_containment`, `evidence_clipping_rate`,
`evidence_temporal_alignment_rate`, `evidence_latency_ms`, `high_resolution_availability`,
`evidence_candidates_eligible`, `selected_identification_role_distribution`) use the
manifest's optional `evidence` annotations (`ExpectedEvidence`, keyed by candidate id) and
report `not_evaluated` when a provider does not support Visit proposals, or
`insufficient_truth` when annotations are absent, all-ambiguous, or no candidate was ever
selected against available truth.

## Provider comparison

`compare_replay_reports` classifies every compared metric as `equivalent`,
`snapshot better`, `frame-driven better`, `insufficient truth`, or
`unsupported for one provider`, without an aggregate winner score. A metric is never
silently treated as zero when a provider does not evaluate it; the comparison itself is
deterministic and reproducible for the same pair of reports.

## Authority and limitations

All outputs remain `shadow_only=true`, `creates_truth=false` shadow evidence. No Event,
Visit, MediaAsset, MotionEvidence, evidence link, primary selection, ReviewLabel,
reviewed Observation, or Dashboard/export truth is reachable from this module. Stage 6
does not change `SnapshotObservationProvider` behavior, admission thresholds, tracking
semantics, or production proposal authority; see
[frame-driven-shadow-provider-contract.md](frame-driven-shadow-provider-contract.md) and
[camera-node-live-shadow-contract.md](camera-node-live-shadow-contract.md) for the
upstream candidate-producing providers this module scores.
