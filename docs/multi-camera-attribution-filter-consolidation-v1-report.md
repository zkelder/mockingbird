# Multi-Camera Attribution & Filter Consolidation v1 -- Report

Date: 2026-10-03. Start HEAD `f886400`, schema `v62` (unchanged). Contract:
[multi-camera-attribution-filter-consolidation-contract.md](multi-camera-attribution-filter-consolidation-contract.md).
Proposed classification: **A**, pending acceptance review.

## Delivered

- **Place Story attribution** through a bounded, read-only composition over
  reviewed Visits (no restructuring of the shared aggregation layer): `first_seen`,
  `diversity_milestone`, `return` entries now carry contributing cameras and
  per-camera evidence drill-down; aggregate/Feature/phenology entries remain
  honestly Place-level.
- **Filter consolidation**: one pure vocabulary + one `CameraFilter` control
  across Activity Library, Bird Log, Collections, Ecological Destinations, Place
  Report, Zone Insights; URL-restorable; stable ids; unified "All cameras" and
  stale-id ("Unavailable camera") handling; the confusable doubled Activity
  Library control collapsed.
- **Cross-camera Calm Attention grouping**: an `associated` encounter is one
  inbox/badge item with other cameras' Visits reachable; per-user
  acknowledgement and global resolution semantics intact.
- **Legacy concurrency limit documented** (README, runtime map); code evidence
  confirmed the sequencing packet's description was accurate. One refinement
  discovered: previews carry a *separate* 2-slot cap (see runtime map).

## Validation

See the closure block in [release-execution-state.md](release-execution-state.md) §3.

## Bounded remaining limitations

- Activity Library no longer offers a per-Stream picker (Source scope only); a
  Source with several Streams can still be narrowed via `?stream=` deep link.
- `regularity_change`/`noteworthy_activity` Story entries remain Place-level;
  attributing a *trend* to cameras would need a contribution rule not defined here.
- Grouping is by the existing `associated` tier only: a late-arriving third
  camera that joins an already-dismissed encounter surfaces unacknowledged for
  that user until they acknowledge the group.
- Review Queue keeps its own composite source/stream control.
- No new real-hardware campaign (accepted multi-camera field evidence frozen).
