# Privacy / Ignore Zone contract

**Status:** current-state truth, written for v0.1 Release Hardening v1 after a
release audit found user-facing copy overclaiming this feature's guarantees.
This document is the one authoritative description of what a Privacy or
Ignore Zone actually does; other docs should link here rather than
re-describing the mechanism.

## The actual contract

A Privacy or Ignore Zone is **trigger-level exclusion only**:

- Activity whose *only* location is inside a Privacy or Ignore Zone never
  independently creates a detection, track, MotionEvidence, Event, or Visit.
- Activity elsewhere in the same camera view can still legitimately trigger
  capture and review, exactly as if the zone did not exist.
- The evidence image saved for that other trigger is the full, unmasked
  source frame. **MockingBird does not crop, black out, blur, or otherwise
  redact a Privacy or Ignore Zone's pixels from a persisted image.** If a
  Privacy Zone covers part of the frame and a bird triggers capture at the
  feeder elsewhere in view, the saved photo can still show whatever is
  physically in the Privacy Zone at that moment.

Plainly: **a Privacy or Ignore Zone prevents activity there from being used
to trigger wildlife monitoring, but it does not redact or remove that part of
the image when another part of the scene causes evidence to be saved.**

This is enforced by masking the excluded region only in transient,
in-memory copies of a frame before that copy is handed to a motion model or
detector (`onnx_provider._preprocess`, `tracked_activity.py`'s foreground
mask, `_object_detector_monitoring_frame`) -- the masked copy is discarded
after inference and is never what gets written to disk. The one exception,
narrower than "storage," is that when the *triggering* zone itself is
Privacy/Ignore, `ProductRepository._create_candidate_visit_locked` refuses
before any MediaAsset file is written (`blocked_privacy_zone`) -- that
protects against *that* candidate being created at all, not against zone
pixels appearing in a *different*, legitimately triggered candidate's saved
frame.

## Privacy Zone and Ignore Zone are the same mechanism

Every enforcement point in the code (motion masking, detector-input masking,
candidate admission, Visit reassignment, classifier suppression, export
eligibility, webhook/folder-import rejection) treats `ZoneType.privacy` and
`ZoneType.ignore` identically. There is no implemented behavioral difference
between the two -- only different diagnostic labels and framing. The two
names exist for a user's own organizational clarity (mark an area "Privacy"
for something privacy-sensitive like a window or doorway, or "Ignore" for
routine unwanted motion like a feeder swinging in the wind), not because
MockingBird enforces a stronger guarantee for one than the other.

## Is "Privacy Zone" the wrong name?

Considered and decided **no** for v0.1 -- the name is kept, with the
explanation above made prominent at the point of use (zone creation on
`CameraSetupPage.tsx`, and the Zone panel on `StreamDetailPage.tsx`) rather
than renamed.

"Privacy Zone"/"privacy mask" is an established term in the camera/NVR
industry for exactly this shape of feature -- an excluded region that
suppresses analysis/recording over an area, not a promise that footage
elsewhere in the same frame can never show it. Renaming the concept would
touch the persisted `zone_type` enum value, the API schema, roughly forty
backend call sites, and every UI label, for a problem that is actually in
the surrounding *copy*, not the name itself -- a truthful, prominent
explanation at the exact place a user configures the zone is the smaller,
equally effective fix, and doctrine already permits it ("If the name can
remain with clear, prominent explanation, preserve it").

## What was corrected

Several places described this feature in stronger terms than the
implementation provides -- naming "storage" specifically, or claiming the
area is "never watched." These were corrected as part of this pass to match
the contract above:

- `web/src/pages/CameraSetupPage.tsx` -- the zone-drawing step's intro copy
  and its privacy/ignore-specific explanatory text (both previously said
  "never watched").
- `web/src/pages/StreamDetailPage.tsx` -- the Zone panel's "Suppression
  only" callout and the Privacy/Ignore legend (previously claimed Privacy
  Zones "restrict... storage").
- [glossary.md](glossary.md)'s Privacy Zone / Ignore Zone entries (previously
  said storage "should be limited").

Docs that already matched this contract exactly and needed no change:
[candidate-visit-authority-contract.md](candidate-visit-authority-contract.md)
("Privacy / Ignore" section),
[multi-frame-evidence-scoring-contract.md](multi-frame-evidence-scoring-contract.md),
[stream-motion-trigger-plan.md](stream-motion-trigger-plan.md),
[megadetector-runtime-plan.md](megadetector-runtime-plan.md), and
[megadetector-runtime-findings.md](megadetector-runtime-findings.md).

## Explicitly out of scope

Image redaction, masking, or storage rewriting that would make this
document's contract stronger (i.e., actually remove Privacy/Ignore Zone
pixels from a saved evidence image) is not implemented and was not added by
this pass. Repository evidence does not establish that pixel-level redaction
is intended v0.1 architecture. Zone geometry is normalized and already
available at the exact point the Observation Engine writes an evidence file
(`stream_privacy_ignore_regions`, `_normalized_box_intersects_zone_polygon`),
so a future redaction feature would be a bounded, additive change if the
product ever decides to build it -- but that is a future decision, not this
one.

## No audio analog exists (disclosed, Acoustic Productization, Licensing & Field Acceptance v1)

This entire contract is expressed in terms of camera geometry: a Privacy or
Ignore Zone is a 2D polygon in one Stream's image space, and the mechanism
(`_normalized_box_intersects_zone_polygon`) can only ever suppress activity
whose evidence carries a bounding box. A `microphone` Source's captured audio
has no geometry at all -- an acoustic candidate Visit's `zone_id` is always
`None`, by honest design (see docs/acoustic-birdnet-observation-foundation-v1-contract.md:
"every geometry-shaped field on an audio-original Visit/MediaAsset stays
genuinely `None`, never fabricated"), not merely unset. There is consequently
**no way to draw a Privacy or Ignore Zone that also excludes a microphone's
captured audio** -- every finalized capture segment from an armed/consented
microphone Source is imported and analyzed regardless of any Zone drawn on
any camera's Stream, including one that happens to observe the same physical
space.

This was not previously disclosed anywhere. A user who draws a Privacy Zone
over part of a camera's view reasonably expects that physical area's
activity to be excluded from evidence capture; a co-located microphone gives
them no equivalent control, because there is no image-space region to draw
one onto. This is a real product-level privacy gap, not a code defect --
`create_acoustic_candidate_visit` behaves exactly as its own docstring says.
Closing it with new audio-zone geometry (e.g. a schedule/location-scoped
"quiet hours" or "do not analyze" toggle for a microphone Source) is
explicitly not attempted here -- it would be the kind of generalized new
mechanism this milestone's own brief says not to build merely because the
gap exists. The bounded fix taken instead: disclose the limitation here, and
surface it directly to the user at the one point they grant microphone
capture consent (the `microphone` Source provider's `capture_consent`
field/UI), so the absence of Zone-based privacy for audio is a known,
accepted tradeoff rather than a silent one. See docs/acoustic-
productization-licensing-field-acceptance-v1-contract.md for the full
Phase 11 privacy audit this finding came from.

## Diagnostic metadata exposure (disclosed, Appliance / Storage / Privacy / Recovery v1)

The counterfactual/rejected-evidence ledger (`GET /api/streams/{stream_id}
/observation/counterfactual`, see
[rejected-detection-attribution-contract.md](rejected-detection-attribution-contract.md))
never stores or exposes pixels, thumbnails, or file paths -- but it *does*
durably record real bounding-box geometry, timing, and confidence for every
detection outcome, including one rejected specifically as
`blocked_privacy_zone`. A caller with access to this diagnostic endpoint can
therefore learn that activity occurred inside a specific Privacy or Ignore
Zone, approximately where and when, purely from geometry retained because
the detection was rejected there.

This is not wildlife evidence -- no Visit, Event, Observation, review-queue
item, or export row is ever created from a privacy-zone rejection -- and
reaching it requires deliberately querying a diagnostic API, not ordinary
product use. But a user who drew a Privacy or Ignore Zone specifically so
that area's activity leaves *no trace at all* would reasonably want this
disclosed, and no prior document addressed it. Recorded here rather than
changed: narrowing what the counterfactual ledger retains would weaken a
separate, already-accepted diagnostic capability, and this exposure's own
severity is bounded (geometry/metadata only, diagnostic-access only) -- a
future pass could scope the ledger to omit `blocked_privacy_zone`/
`blocked_ignore_zone` outcomes specifically if this is ever judged to need
tightening further.

## Regression coverage

`tests/test_candidate_visit_repository.py::test_evidence_from_a_non_privacy_zone_is_not_redacted_for_a_coexisting_privacy_zone`
locks in the persistence half of this contract: a candidate whose own
triggering zone is *not* Privacy/Ignore still gets created, and its
persisted `MediaAsset` bytes are byte-identical to the source evidence even
when an active Privacy Zone also exists on the same Stream. The existing
`test_privacy_zone_candidate_is_blocked`/`test_ignore_zone_candidate_is_blocked`
(`tests/test_candidate_visit_repository.py`) remain the negative control for
the trigger-suppression half.
