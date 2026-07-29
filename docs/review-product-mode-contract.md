# Product Mode Review Queue

Product Mode is the compact review surface for current, detector-qualified
outdoor activity. It improves the path from saved evidence to an explicit
correction without making detector output, a species suggestion, or a queue
category into truth.

## Default Queue

The default tab is **Animals**. It contains unresolved Visit records whose
durable MotionEvidence provenance records a MegaDetector animal observation.
Each Visit is one card, ordered newest-first and rendered in pages of at most
25 cards.

A compact card shows its primary saved evidence first, capture time, Stream and
Zone, detector evidence class and score, and the number of saved evidence
items. It says **“Animal detected — species not confirmed”** until a reviewer
takes an explicit correction action.

## Secondary Work

- **Other activity** contains detector-qualified person or vehicle evidence.
- **Unchecked** contains real-source records without enough durable detector
  provenance to classify them.
- **Legacy activity** is hidden until the reviewer enables “Show legacy and
  test activity.” It contains old motion-only and demo/test records.
- **Reviewed** is an opt-in history tab. The normal API response remains
  unresolved work only; Product Mode requests reviewed history explicitly.

The API derives these groups from persisted Source, provider, MotionEvidence,
and immutable object-track provenance. It does not infer them from a display
label or current runtime state.

## Evidence and Developer Details

The primary image is the review thumbnail; an unavailable asset is labeled
honestly. A BioCLIP result is presented as species-suggestion evidence with its
relative score, candidate pack, and a link to the full Visit evidence.
Track, media, and raw persisted detector provenance are available only in the
collapsed **Developer evidence** section. They are never a species result or a
truth-writing action.

## Truth Boundary

Detector class, score, track generation, evidence frames, and species
suggestions remain evidence. Fast Review begins with a blank correction form;
a reviewer may explicitly choose suggestion evidence to prefill it.

Only an explicit correction creates a ReviewLabel, reviewed species outcome,
Bird Log observation, analytics truth, or export truth. Skip is local UI
navigation and writes nothing.
