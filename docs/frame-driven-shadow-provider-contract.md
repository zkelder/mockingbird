# Frame-driven detector/tracker shadow-provider contract

Observation Engine v2 Stage 4 implements `frame-driven-onnx-cuda` as a
deterministic ordered-frame replay provider. It schedules the existing local
ONNX Runtime CUDA detector from source-relative timestamps, updates a
provider-neutral tracker on every supplied analysis frame, retains bounded
portable evidence references, and emits shadow-only `VisitProposal` facts. It
does not consume a live stream or hold production proposal authority.

## Provider and scheduling boundary

The provider uses one explicit versioned configuration that points to the
existing portable ONNX model bundle by a contained relative path. Its semantic
settings declare source nominal FPS, idle and candidate detector FPS, the
single latest detector-work bound, frame-gap and tracker-expiry bounds,
occlusion tolerance, confirmation policy, active-track cap, evidence-ring cap,
and the Stage 6.1 episode-boundary bounds: maximum time since genuine detector
support before an episode ends regardless of tracker-support continuation,
consecutive explicit animal-negative detector frames required to end an
episode early, and the reentry window used only to report (never to act on) an
ambiguous restart. Source nominal FPS must agree with the replay manifest.

Scheduling uses `FramePacket.source_offset_ms`, never wall-clock time. Idle
replay runs the heavyweight detector at the baseline cadence. A tentative or
confirmed animal track selects the bounded candidate cadence. The tracker still
receives every distinct ordered analysis frame. Work is synchronous and
single-pending in Stage 4, so historical detector frames cannot accumulate
behind newer replay input. When every track terminates, cadence returns to idle
and transient track/evidence state is released.

Privacy/Ignore exclusions are normalized input facts. Their pixels are masked
before ONNX preprocessing, and any returned box centered inside an exclusion is
discarded before tracking.

## Provider-neutral tracking

`ProviderNeutralFrameTracker` exposes only normalized geometry, broad class,
source-relative time, frame identity, confidence/provenance, detector
confirmations, tracker-support count, lifecycle state, and stable generation
identity. ONNX Runtime, NVIDIA, Pillow, NumPy, and future tracker-library types
do not enter Observation Engine product contracts.

The first implementation uses deterministic one-to-one spatial association
with predicted centroid motion and a small portable patch-support adapter on
intervening frames. Association combines class compatibility, normalized box
overlap, predicted centroid displacement, and an ambiguity margin. A later
ByteTrack-class implementation may replace this adapter behind the same
contract.

Tracks are bounded and deterministic:

- `tentative`: initial animal evidence without enough temporal support;
- `confirmed`: one configured strong detection plus coherent tracker support,
  or the configured number of coherent detector confirmations;
- `temporarily_lost`: a bounded miss after tentative or confirmed support;
- `ended`: a confirmed episode closed by loss, duration, reset, or replay end;
- `rejected`: an unconfirmed episode that expired without sufficient support.

Repeated frame identities never add support. Active count, missed frames,
source-time gaps, episode duration, and association ambiguity are bounded.
A terminated generation is never revived.

### Episode boundary (Stage 6.1)

Genuine detector support and bounded tracker-support (for example a portable
patch match on intervening frames) are tracked separately. Tracker-support
alone can bridge a brief detector miss, but it can never by itself keep an
episode "supported" indefinitely: each track also records the source-relative
time of its last genuine detector confirmation and its count of consecutive
explicit animal-negative detector frames (the detector executed and found
nothing usable for that track; an idle-cadence frame the detector never
inspected is not negative evidence). Once either bound is exceeded the episode
ends even while tracker-support keeps reporting a plausible box, so a later,
unrelated appearance at a similar position starts its own generation instead
of continuing a stale one. The same Zone and broad class are never sufficient
by themselves to continue a track; spatial/motion association still governs
which detections a live track can claim, unchanged from Stage 4.

The boundary is expressed through the existing `lifecycle_state`/`status`/
`terminal_reason` facts rather than a parallel taxonomy:

- continuing an episode is `status="updated"` with `lifecycle_state` staying
  `tentative`/`confirmed` (via either genuine detector support or bounded
  tracker-support);
- temporarily losing it is `lifecycle_state="temporarily_lost"` within the
  existing miss/expiry tolerance;
- ending it is `status="ended"` with one terminal reason;
- starting a new generation is `status="started"` with a fresh, unrelated
  generation id;
- an ambiguous association is exposed as a count, never a silent merge (below).

Terminal reasons are `confirmed_visit`, `insufficient_support`, `tracker_lost`,
`maximum_duration`, `maximum_unsupported_duration`, `negative_interval_reentry`,
`ambiguous_association`, `provider_reset`, or `end_of_replay` as applicable.
`maximum_unsupported_duration` and `negative_interval_reentry` are the two
confident-split reasons: they reflect positive evidence of discontinuity
(elapsed time or explicit negative detector frames) rather than a bounded
tolerance running out. An unconfirmed episode's terminal reason is always
reported as `insufficient_support` regardless of which bound closed it.
Stage 6.11 adds two more, specifically at a reconnect boundary:
`reconnect_bridge_expired` (a bounded reconnect-bridge window closed without
reacquisition -- same bounded-tolerance shape as `tracker_lost`, not a
confident split) and reuses `provider_reset` for a confidently evidenced
source-generation change at that boundary, now distinguished from a
`"insufficient_reconnect_provenance"` safety reset when the boundary's own
provenance cannot prove which case applies. See
[reconnect-continuity-contract.md](reconnect-continuity-contract.md) for the
full benign-reconnect-vs-source-reset decision this boundary now goes
through before either reason can fire. Stage 6.16 adds a bounded
strong/weak/tracker-only evidence hierarchy so a confirmed track survives a
detector-confidence dip or brief tracker-only stretch through the *same*
existing terminal-reason vocabulary above, rather than an unconditional
tight bound treating every dip as `tracker_lost`; explicit negative-detector
intervals and true departure still close the episode exactly as before. See
[sustained-visit-continuity-contract.md](sustained-visit-continuity-contract.md)
for the full bounded-tolerance/no-immortal-track contract.

When an episode ends without a confident-split reason (for example a plain
`tracker_lost` or `maximum_duration`) and a new, class/geometry-compatible
detection starts a track within the bounded reentry window, the tracker
reports one ambiguous reentry for that start. It never revives the ended
generation or merges evidence; it only makes the tradeoff visible in replay
metrics so a reviewer or a later stage can see that continuity genuinely could
not be determined safely.

## Shadow proposal and evidence boundary

A confirmed generation produces exactly one proposal when its episode closes.
The deterministic proposal key is also its idempotency key. It records Stream,
source-relative start/end, broad class, generation, supporting frame identities,
detector/tracker provenance, provider version, evidence references, terminal
reason, and `shadow_only=true`.

Each active generation owns a bounded evidence-role map rather than the full
replay. Available roles are pretrigger context, first detector-confirmed frame,
tracked best, final supported frame, and one bounded alternative. Candidates
contain only portable frame identity/reference, timestamp, dimensions,
normalized subject geometry, provenance, and deterministic subject-area/score
facts. They are temporary shadow evidence and never create `MediaAsset`.
Stage 6 ranks these candidates; see
[multi-frame-evidence-scoring-contract.md](multi-frame-evidence-scoring-contract.md).

## Replay, metrics, and execution facts

The Stage 2 CLI accepts:

```sh
python -m mockingbird replay-benchmark \
  --provider frame-driven-onnx-cuda \
  --provider-config data/models/observation-frame-driven/provider-config.json \
  --frames data/replay/frames \
  --manifest data/replay/benchmark.json \
  --output data/replay/output
```

The semantic report includes settings, tracker version/configuration,
detections, track updates, evidence candidates, proposals, matcher output,
pipeline counts, metric states, thresholds, and limitations. Detector latency,
tracker processing time, process/GPU resources, device/runtime facts, absolute
paths, and wall-clock duration remain non-semantic execution facts.

Pipeline counts include the deterministic episode-boundary metrics
`episode_temporary_loss_count`, `episode_rejected_count`,
`episode_confirmed_split_count` (terminations via a confident-split reason),
`episode_ambiguous_reentry_count`, and `boundary_reason_distribution` (a tally
of every terminal reason observed). All are derived only from already-emitted
`TrackUpdate` facts; no tracker-library object crosses into the report.

Snapshot-versus-frame-driven comparison reports each side's state/value for
appearance recall, proposal precision, fragmentation, duplicates, incorrect
merges, evidence coverage, detector frames, and the episode-boundary metrics
above. Unsupported Snapshot metrics remain unavailable rather than being
treated as zero.

## Authority and current limitations

The provider imports no product repository and cannot create or mutate Event,
Visit, MediaAsset, MotionEvidence, evidence links, primary selections,
ReviewLabel, reviewed Observation, Dashboard/export truth, monitoring policy,
or policy revision. CUDA-only execution remains mandatory; CPU model fallback
is rejected by the Stage 3 detector boundary.

Stage 4 is replay-first continuous analysis. It does not implement live RTSP,
Camera Node analysis streams, rolling encoded buffers, high-resolution evidence
bursts, species interpretation, TensorRT, audio, monitoring workers, or
production proposal authority. Stage 5 adds the provider-neutral Camera Node
analysis-stream and evidence-burst capability boundary.
