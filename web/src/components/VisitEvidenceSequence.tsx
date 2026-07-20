import { useEffect, useState, type ReactNode } from "react";
import { apiClient } from "../api/client";
import type { VisitEvidenceFrame } from "../api/types";
import { formatDateTime } from "../utils";

interface VisitEvidenceSequenceProps {
  frames: VisitEvidenceFrame[];
  surfaceOverlay?: ReactNode;
  keyboardControls?: boolean;
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

/** A local frame-sequence player for already-serialized Visit evidence. */
export function VisitEvidenceSequence({
  frames,
  surfaceOverlay,
  keyboardControls = false,
}: VisitEvidenceSequenceProps) {
  const initialFrameIndex = Math.max(0, frames.findIndex((frame) => frame.is_primary));
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

  const primaryFrameIndex = Math.max(0, frames.findIndex((frame) => frame.is_primary));
  const previewUrl = (frame: VisitEvidenceFrame) => `${apiClient.baseUrl}${frame.preview_url}`;
  return (
    <div className="review-evidence-sequence">
      <div className="review-evidence-sequence-image">
        {isPreviewUnavailable ? (
          <span className="review-evidence-preview-unavailable">Saved preview is unavailable.</span>
        ) : (
          <img
            alt={`Visit evidence captured ${formatDateTime(selectedFrame.captured_at)}`}
            onError={() => setIsPreviewUnavailable(true)}
            src={previewUrl(selectedFrame)}
          />
        )}
        {selectedFrame.is_primary ? surfaceOverlay : null}
      </div>
      <div className="review-evidence-sequence-meta">
        <strong>{selectedFrame.is_primary ? "Primary evidence" : "Supporting evidence"}</strong>
        <span>{formatDateTime(selectedFrame.captured_at)}</span>
        <span>{relativeLabel(selectedFrame)}</span>
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
          disabled={selectedIndex === primaryFrameIndex}
          onClick={() => setSelectedIndex(primaryFrameIndex)}
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
              {frame.is_primary ? <span>Primary</span> : null}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
