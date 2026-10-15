import type { CSSProperties } from "react";
import type { VisitEvidenceFrame } from "../api/types";

/**
 * Everyday Wildlife Experience & Presentation Refinement v1: how a
 * representative thumbnail is framed -- presentation only, never a new
 * selection or a claim about the animal.
 *
 * - A subject is centred only when the server already vouched for the box:
 *   `normalized_track_box` is populated solely for a frame that still spans
 *   the camera's full field of view with proven alignment (see
 *   `_frame_local_subject_box`), so it is a fraction of *this* image. A
 *   derived crop carries no track box and is already subject-centred, so it
 *   is shown as-is. Without a vouched box the whole image is shown.
 * - Centring never blows up a low-resolution source: if the zoomed region
 *   would be fewer than MIN_FRAMED_REGION_PX across, the full frame is shown.
 * - A low-resolution source (small image) is shown whole on a soft backdrop
 *   instead of being stretched to fill the card.
 */
export const MIN_FRAMED_REGION_PX = 160;
export const LOW_RESOLUTION_EDGE_PX = 360;
const MAX_FRAMING_ZOOM = 3;
// Generous padding: the tracker's box is known to be imprecise (it can sit on
// the feeder rather than the bird), so never crop tight to it.
const FRAMING_PAD_FACTOR = 4;
const MIN_FRAMING_SPAN = 0.28;

export interface ThumbnailFraming {
  className: string;
  style?: CSSProperties;
}

function validBox(box: number[] | null | undefined): [number, number, number, number] | null {
  if (!box || box.length !== 4) {
    return null;
  }
  const [left, top, right, bottom] = box;
  if (![left, top, right, bottom].every((value) => Number.isFinite(value) && value >= 0 && value <= 1)) {
    return null;
  }
  return right > left && bottom > top ? [left, top, right, bottom] : null;
}

export function thumbnailFraming(
  frame: Pick<VisitEvidenceFrame, "width" | "height" | "normalized_track_box">,
): ThumbnailFraming {
  const { width, height } = frame;
  if (width && height && Math.max(width, height) < LOW_RESOLUTION_EDGE_PX) {
    return { className: "journal-thumb-low-resolution" };
  }
  const box = validBox(frame.normalized_track_box);
  if (!box || !width || !height) {
    return { className: "" };
  }
  const [left, top, right, bottom] = box;
  const spanX = Math.min(1, Math.max(MIN_FRAMING_SPAN, (right - left) * FRAMING_PAD_FACTOR));
  const spanY = Math.min(1, Math.max(MIN_FRAMING_SPAN, (bottom - top) * FRAMING_PAD_FACTOR));
  const span = Math.max(spanX, spanY);
  const zoom = Math.min(MAX_FRAMING_ZOOM, 1 / span);
  if (zoom < 1.15 || Math.min(width, height) / zoom < MIN_FRAMED_REGION_PX) {
    return { className: "" };
  }
  const centreX = (left + right) / 2;
  const centreY = (top + bottom) / 2;
  // With `object-fit: cover`, `object-position: X% Y%` aligns the image's
  // (X%, Y%) point with the box's (X%, Y%) point -- so the subject sits at
  // (centreX, centreY) of the box. Scale about that point, then translate it
  // to the middle, clamped so a scaled edge is never pulled inside the box.
  const clampShift = (centre: number) => {
    const wanted = 0.5 - centre;
    const min = -(zoom - 1) * (1 - centre);
    const max = (zoom - 1) * centre;
    return Math.min(max, Math.max(min, wanted));
  };
  return {
    className: "journal-thumb-framed",
    style: {
      objectPosition: `${(centreX * 100).toFixed(2)}% ${(centreY * 100).toFixed(2)}%`,
      transformOrigin: `${(centreX * 100).toFixed(2)}% ${(centreY * 100).toFixed(2)}%`,
      transform: `translate(${(clampShift(centreX) * 100).toFixed(2)}%, ${(clampShift(centreY) * 100).toFixed(2)}%) scale(${zoom.toFixed(3)})`,
    },
  };
}
