# Species Suggestion Correction Flow

## Purpose

Species suggestions can make review faster, but they are still evidence. Applying
a suggestion needs an explicit correction flow so user review remains the only
source of dataset/export truth.

This design defines how a `SpeciesSuggestion` can help a user create a normal
correction without letting suggestion status become truth by itself.

## Phase 9E Status

Phase 9E implements the frontend-first prefill path. The Species Suggestions page
can open Visit Detail with `suggested_label` prefilled in the existing correction
form when the suggestion has `visit_id` context.

No backend apply-as-correction endpoint was added. SpeciesSuggestion status is
not changed automatically; status polish remains deferred. Submitting the
existing correction form remains the only truth-creating action.

## Phase 9F Status

Phase 9F marks eligible SpeciesSuggestion evidence accepted only after the
existing Visit correction submit succeeds. Clicking "Use as correction" and
navigating to Visit Detail still create no truth and do not change suggestion
status.

If the correction save succeeds but the suggestion status update fails, the
correction remains saved. The UI reports the status update failure as
non-blocking evidence workflow metadata.

## Phase 9G Status

Phase 9G shows Visit-linked SpeciesSuggestion evidence directly in Visit Detail
near the existing correction form. Reviewers can use a pending or accepted
suggestion to prefill the correction label in place, edit it, and then submit
the normal correction form.

Rejected and superseded suggestions stay read-only in the review context. Review
Queue and Event Detail suggestion cues remain deferred unless they can be added
without broad data-shape changes.

## Product Flow

SpeciesSuggestion pending or accepted
-> user selects "Use as correction"
-> existing Visit/Event review context opens or receives the suggested label
-> user confirms or edits the correction
-> `ReviewLabel` or user correction is created
-> eligible suggestion status may be marked accepted as evidence metadata
-> Visit/Event review state updates according to existing correction behavior
-> dataset/export truth updates only from that correction

## Key Distinction

- Accepted suggestion: the user found the suggestion useful as evidence.
- Applied correction: the user explicitly created reviewed label/truth through
  the correction flow.

Accepted suggestion alone must not:

- create `ReviewLabel`
- mark Visit reviewed
- update dataset coverage truth
- make an export-ready record

## Suggested Future UI Behavior

- The Species Suggestions page shows "Use as correction" only when a
  suggestion has enough `visit_id` or `event_id` context for correction.
- Visit Detail receives suggestion prefill near the correction form.
- Visit Detail can show Visit-linked suggestions as review evidence before the
  user chooses one.
- The button pre-fills the correction label with `suggested_label`.
- The user can edit the label before submitting.
- The correction form remains the final truth action.
- Rejected or superseded suggestions should not offer a primary apply action.
- Accepted suggestions still require explicit correction submission before
  dataset/export truth changes.

## Suggested Future API Behavior

Option A:

- The frontend uses the existing correction endpoint with `suggested_label`
  prefilled.
- SpeciesSuggestion status may be updated to accepted only after the correction
  succeeds.

Option B:

- Add a future endpoint such as
  `POST /api/species-suggestions/{id}/apply-as-correction`.
- The endpoint internally calls the same correction service/path.
- It must require explicit user action.
- It must return the created correction/review result.
- It must update suggestion status only after correction succeeds.

Recommendation: start with Option A. It is safer because it keeps one truth
writer, one review form, and one correction API path. Option B is reasonable
later only if it wraps the existing correction behavior and tests prove it does
not duplicate truth logic.

## Recommended Implementation Approach

Start with frontend-only prefill if the existing correction APIs support it:

- Link from a suggestion to Visit Detail or Event Detail.
- Pass the suggested label in UI state, query state, or local component state if
  practical.
- Let the user submit the existing correction form.

If backend implementation is needed later:

- Wrap existing correction behavior.
- Do not duplicate review/truth logic.
- Tests must prove the same correction path is used.

## Status Lifecycle Interaction

- A pending suggestion can be applied as correction, then may become accepted
  after the correction succeeds.
- An accepted suggestion is still not truth until correction is submitted.
- A rejected suggestion should not be applied without reopening or an explicit
  override policy.
- A superseded suggestion should remain historical evidence.
- A correction may supersede other suggestions for the same Visit/media later,
  but only with explicit policy.

## Relationship To Taxonomy

- `suggested_label` should map to taxonomy labels when possible.
- Out-of-taxonomy suggestions should require review and may become freeform only
  if the existing correction flow allows it.
- Taxonomy suggestions should assist correction, not bypass validation.

## Relationship To Review Queue And Visit Detail

- Suggestions are most useful near Visit Detail and Review Queue.
- Suggestions should show confidence, rank, adapter, and provenance.
- Reviewed truth should be visually separate from suggestions.

## Truth Boundary Requirements

- Suggestion status updates do not create truth.
- Apply action must use the correction/review path.
- Correction remains auditable.
- Exports and dataset coverage rely on reviewed correction only.

## Error And Failure Cases

- Suggestion has no `visit_id` or `event_id`: show evidence detail, but no
  primary apply action.
- Referenced Visit/Event is missing: show a safe error and do not update status
  or truth.
- Suggested label is not in taxonomy: require user review; allow freeform only
  if the correction form already allows it.
- Suggestion is rejected or superseded: do not primary-apply it.
- Correction fails: do not update suggestion status.
- Correction succeeds but status update fails: keep the correction, report the
  status failure, and do not roll back truth.
- Multiple suggestions conflict: show them as competing evidence and let the
  user choose or type the correction.
- User edits label before submitting: store the edited label as truth.

## Test Plan For Future Implementation

- Accepted suggestion alone creates no `ReviewLabel`.
- Use-as-correction requires explicit action.
- Correction endpoint creates `ReviewLabel` using suggested label only after
  submit.
- User can edit suggested label before correction.
- Rejected/superseded suggestions cannot be primary-applied.
- Dataset coverage/export truth changes only after correction.
- Suggestion status updates after successful correction, if implemented.
- Failed status updates do not undo successful corrections.
- Failures do not partially update suggestion/truth.
- No model runtime is required.

## Explicit Non-Goals

- no SpeciesNet runtime
- no model dependency
- no automatic correction
- no reviewed labels from suggestions alone
- no export truth from suggestions alone
- no stream capture
- no media decoding
- no cloud upload
- no production accuracy claims
