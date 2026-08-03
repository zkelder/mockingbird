# Observation Replay Benchmark Contract

The Stage 2 benchmark replays an ordered directory of JPEG or PNG frames through
an explicitly selected Observation Engine provider. Replay is offline,
shadow-only, deterministic, and cannot create product records or reviewed truth.

## Input

The versioned JSON manifest names relative frame paths, strictly increasing
source offsets, decoded dimensions, optional content hashes, expected appearances
and Visits, and optional thresholds. Absolute paths, traversal, symlinks,
unsupported extensions, missing or undecodable files, duplicate frame entries,
hash mismatches, dimension mismatches, and bounded-manifest violations are rejected.

Frame identity is derived from the input fingerprint, ordered index, source
offset, and content hash. It never includes an absolute path.

## Matching and metrics

The matcher classifies matched and missed expected Visits, false and duplicate
proposals, fragmented expected Visits, incorrectly merged expected Visits, and
ambiguous truth. Tie-breaking uses greatest temporal overlap, Zone agreement,
earliest stable proposal start, then stable proposal id. One proposal has one
deterministic owner.

Every metric carries `evaluated`, `not_evaluated`, or `insufficient_truth` state.
Thresholds produce `pass`, `fail`, or `unscorable`; an unscorable required
threshold makes the profile unsuccessful. Snapshot replay honestly reports no
continuous detector, tracker, rolling buffer, GPU acceleration, or proposal authority.

## Report and command

`python -m mockingbird replay-benchmark --provider snapshot --frames FRAMES
--manifest MANIFEST.json --output OUTPUT_DIRECTORY` writes one atomic
`replay-report.json` into a new or empty directory. Output is allowed outside the
repository or below ignored `data/`; tracked source, docs, tests, and the repository
root are refused.


The semantic fingerprint covers normalized replay input, manifest, provider,
proposals, matching, metrics, and thresholds. Absolute paths, output location,
host, PID, wall-clock timestamps, execution duration, and machine resource facts
belong only to the separate non-semantic execution section.
