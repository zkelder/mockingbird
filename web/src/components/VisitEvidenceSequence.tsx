import { useEffect, useState, type ReactNode } from "react";
import { apiClient } from "../api/client";
import type { VisitEvidenceFrame } from "../api/types";
import { EvidenceBadge } from "./EvidenceBadge";
import { EvidenceZoomControls, EvidenceZoomViewport, useEvidenceZoom } from "./EvidenceImageViewer";
import { formatDateTime } from "../utils";

interface VisitEvidenceSequenceProps {
  frames: VisitEvidenceFrame[];
  surfaceOverlay?: ReactNode;
  keyboardControls?: boolean;
  /**
   * A different already-saved frame (by media_asset_id) worth showing first,
   * e.g. because the auto-selected primary crop is empty or off-target. Pure
   * presentation: never sent back to the server, never changes `is_primary`
   * or any other persisted evidence-selection state. Ignored if it does not
   * match one of `frames`.
   */
  recommendedMediaAssetId?: string | null;
  /** Plain-language reason shown alongside the recommendation, if any. */
  recommendationNote?: string | null;
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  return (
    target.isContentEditable ||
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    target instanceof HTMLSelectElement
  );
}

function relativeLabel(frame: VisitEvidenceFrame): string {
  return `${Math.round(frame.relative_position * 100)}% through visit`;
}

function evidenceRoleLabel(frame: VisitEvidenceFrame): string {
  // Everyday Product / Discovery UX Closure v1: an acoustic candidate Visit
  // (create_acoustic_candidate_visit) uses these same Observation Engine
  // evidence_role values, but "image" wording misdescribes a BirdNET clip.
  const isAudio = frame.content_type.startsWith("audio/");
  const labels: Record<string, string> = {
    user_refined_crop: "User-refined high-resolution crop",
    activity_crop: "High-resolution activity crop",
    high_resolution_original: "Full-resolution original",
    pretrigger: "Pre-trigger context",
    tracked_best_frame: "Tracked monitoring frame",
    // Observation Engine candidate evidence roles.
    identification: isAudio ? "Best identification clip" : "Best identification image",
    context: isAudio ? "Context clip" : "Context image",
    alternate: isAudio ? "Alternate clip" : "Alternate image",
    // Visit Same-Frame Classifier Evidence Visibility v1: only ever appears
    // via the dedicated `classifier_supporting_evidence` panel below, never
    // in this gallery itself (the role is structurally excluded from
    // `evidence_frames`) -- kept here so that panel's own `VisitEvidenceSequence`
    // instance gets a real, specific caption instead of the generic fallback.
    classifier_same_frame: "Frame used for species suggestion",
  };
  return labels[frame.evidence_role] ?? (isAudio ? "Monitoring audio" : "Monitoring context");
}

/** A local frame-sequence player for already-serialized Visit evidence. */
export function VisitEvidenceSequence({
  frames,
  surfaceOverlay,
  keyboardControls = false,
  recommendedMediaAssetId,
  recommendationNote,
}: VisitEvidenceSequenceProps) {
  const persistedPrimaryIndex = Math.max(0, frames.findIndex((frame) => frame.is_primary));
  const recommendedIndex = recommendedMediaAssetId
    ? frames.findIndex((frame) => frame.media_asset_id === recommendedMediaAssetId)
    : -1;
  // The persisted primary is still what the detector/tracker selected; a
  // recommendation only changes which frame opens first, never that fact.
  const initialFrameIndex = recommendedIndex >= 0 ? recommendedIndex : persistedPrimaryIndex;
  const [selectedIndex, setSelectedIndex] = useState(initialFrameIndex);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [isPreviewUnavailable, setIsPreviewUnavailable] = useState(false);
  const frameIdentity = frames.map((frame) => frame.media_asset_id).join(",");
  const selectedFrame = frames[selectedIndex] ?? frames[initialFrameIndex];
  const canPlay = frames.length > 1;

  useEffect(() => {
    setSelectedIndex(initialFrameIndex);
    setIsPlaying(false);
  }, [frameIdentity, initialFrameIndex]);

  useEffect(() => {
    setIsPreviewUnavailable(false);
  }, [selectedFrame?.media_asset_id]);

  useEffect(() => {
    if (!isPlaying || !canPlay) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      setSelectedIndex((current) => (current + 1) % frames.length);
    }, 1000 / playbackSpeed);
    return () => window.clearInterval(timer);
  }, [canPlay, frames.length, isPlaying, playbackSpeed]);

  useEffect(() => {
    if (!keyboardControls || !canPlay) {
      return undefined;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (isTypingTarget(event.target)) {
        return;
      }
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        setSelectedIndex((current) => (current - 1 + frames.length) % frames.length);
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        setSelectedIndex((current) => (current + 1) % frames.length);
      } else if (event.code === "Space") {
        event.preventDefault();
        setIsPlaying((playing) => !playing);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [canPlay, frames.length, keyboardControls]);

  if (!selectedFrame) {
    return null;
  }

  const isViewingRecommended =
    recommendedIndex >= 0 && selectedIndex === recommendedIndex && recommendedIndex !== persistedPrimaryIndex;
  const previewUrl = (frame: VisitEvidenceFrame) => `${apiClient.baseUrl}${frame.preview_url}`;
  const fullResolutionUrl = (frame: VisitEvidenceFrame) =>
    `${apiClient.baseUrl}/api/media/${frame.media_asset_id}/full-resolution`;
  // One shared zoom/pan/focus state for the currently-selected frame. The
  // viewport (pannable image) and controls (toolbar) render from it in two
  // different places below -- see the module comment in EvidenceImageViewer.
  const zoom = useEvidenceZoom({
    alt: `Visit evidence captured ${formatDateTime(selectedFrame.captured_at)}`,
    frameKey: selectedFrame.media_asset_id,
    fullResolutionSrc: fullResolutionUrl(selectedFrame),
    naturalHeight: selectedFrame.height,
    naturalWidth: selectedFrame.width,
    onPreviewError: () => setIsPreviewUnavailable(true),
    previewSrc: previewUrl(selectedFrame),
    subjectBox: selectedFrame.normalized_track_box,
  });
  // Acoustic / BirdNET Observation Foundation v1: audio evidence has no
  // pixels to zoom/pan -- render a plain player instead of the image
  // zoom viewport for this frame. Real evidence content either way, never
  // a fabricated waveform/thumbnail standing in for the image case.
  const isAudioFrame = selectedFrame.content_type.startsWith("audio/");
  return (
    <div className="review-evidence-sequence">
      <div className="review-evidence-sequence-image">
        {isAudioFrame && isPreviewUnavailable ? (
          <span className="review-evidence-preview-unavailable">Saved audio evidence is unavailable.</span>
        ) : isAudioFrame ? (
          <div className="media-preview-audio-stage">
            <span className="media-preview-audio-icon" aria-hidden="true">🔊</span>
            <audio
              controls
              preload="metadata"
              src={previewUrl(selectedFrame)}
              onError={() => setIsPreviewUnavailable(true)}
            />
          </div>
        ) : isPreviewUnavailable ? (
          <span className="review-evidence-preview-unavailable">Saved preview is unavailable.</span>
        ) : (
          <EvidenceZoomViewport zoom={zoom} />
        )}
        {selectedFrame.is_primary ? surfaceOverlay : null}
      </div>
      {isAudioFrame || isPreviewUnavailable ? null : <EvidenceZoomControls zoom={zoom} />}
      {recommendedIndex >= 0 && recommendedIndex !== persistedPrimaryIndex ? (
        <div className="review-evidence-recommendation">
          <EvidenceBadge label="Recommended view" tone="evidence" />
          <span>
            {recommendationNote ??
              "A different saved frame from this Visit may show the subject more clearly than the auto-selected primary crop."}
          </span>
          {selectedIndex !== recommendedIndex ? (
            <button
              className="text-action"
              onClick={() => { setSelectedIndex(recommendedIndex); setIsPlaying(false); }}
              type="button"
            >
              View recommended frame
            </button>
          ) : null}
        </div>
      ) : null}
      <div className="review-evidence-sequence-meta">
        <strong>
          {selectedFrame.is_primary
            ? "Primary evidence"
            : isViewingRecommended
              ? "Recommended view (supporting evidence)"
              : "Supporting evidence"}
        </strong>
        <span>{formatDateTime(selectedFrame.captured_at)}</span>
        <span>{relativeLabel(selectedFrame)}</span>
        <span>{evidenceRoleLabel(selectedFrame)}</span>
        {selectedFrame.width && selectedFrame.height ? (
          <span>{selectedFrame.width} × {selectedFrame.height}</span>
        ) : null}
      </div>
      <div className="review-evidence-sequence-controls">
        <button
          className="secondary-action"
          disabled={!canPlay}
          onClick={() =>
            setSelectedIndex((current) => (current - 1 + frames.length) % frames.length)
          }
          type="button"
          title="Previous evidence frame (Left Arrow in Fast Review)"
        >
          Previous
        </button>
        <button
          className="secondary-action"
          disabled={!canPlay}
          onClick={() => setIsPlaying((playing) => !playing)}
          type="button"
          title="Play or pause evidence (Space in Fast Review)"
        >
          {isPlaying ? "Pause" : "Play"}
        </button>
        <button
          className="secondary-action"
          disabled={!canPlay}
          onClick={() => setSelectedIndex((current) => (current + 1) % frames.length)}
          type="button"
          title="Next evidence frame (Right Arrow in Fast Review)"
        >
          Next
        </button>
        <button
          className="text-action"
          disabled={selectedIndex === persistedPrimaryIndex}
          onClick={() => setSelectedIndex(persistedPrimaryIndex)}
          type="button"
        >
          Primary
        </button>
        <label className="review-evidence-speed">
          Speed
          <select
            aria-label="Evidence playback speed"
            onChange={(event) => setPlaybackSpeed(Number(event.target.value))}
            value={playbackSpeed}
          >
            <option value={0.5}>0.5×</option>
            <option value={1}>1×</option>
            <option value={2}>2×</option>
          </select>
        </label>
        <span className="meta-text">{selectedIndex + 1} / {frames.length}</span>
      </div>
      {frames.length > 1 ? (
        <div aria-label="Visit evidence frames" className="review-evidence-thumbnail-strip">
          {frames.map((frame, index) => (
            <button
              aria-label={`View evidence frame ${index + 1}`}
              aria-pressed={index === selectedIndex}
              className={index === selectedIndex ? "is-selected" : ""}
              key={frame.media_asset_id}
              onClick={() => {
                setSelectedIndex(index);
                setIsPlaying(false);
              }}
              type="button"
            >
              <img alt="" src={previewUrl(frame)} />
              <span>
                {frame.is_primary
                  ? "Primary"
                  : recommendedMediaAssetId && frame.media_asset_id === recommendedMediaAssetId
                    ? "Recommended"
                    : evidenceRoleLabel(frame)}
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
