import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Manual zoom/pan/focus for one already-saved Visit evidence image.
 *
 * This is presentation only: it never selects, crops, or re-derives any
 * media. It reuses whatever `previewSrc`/`fullResolutionSrc` the caller
 * already resolved from existing `/api/media/*` endpoints, and (when given
 * one) reads an already-computed `subjectBox` purely to aim the viewport --
 * it never invents or transforms geometry itself.
 *
 * `useEvidenceZoom` owns all state; `EvidenceZoomViewport` (the pannable
 * image, meant to fill an existing fixed-box image container) and
 * `EvidenceZoomControls` (the button toolbar, meant to sit *outside* that
 * fixed box as ordinary page flow) both render from it. They are split
 * because the existing evidence image container other callers already
 * position badges/overlays against (`surfaceOverlay` in
 * VisitEvidenceSequence) is a fixed-aspect-ratio, `overflow: hidden` box --
 * a toolbar cannot safely share that box without either being clipped or
 * squeezing the image, and overlaying it on top of the photo would itself
 * obscure the animal it exists to help find.
 */

const MIN_SCALE = 1;
const MAX_SCALE = 8;
// Tolerance for float drift when comparing a live scale against MIN/MAX_SCALE.
const SCALE_EPSILON = 0.01;
const WHEEL_ZOOM_SENSITIVITY = 0.0018;
const BUTTON_ZOOM_STEP = 1.5;
const DOUBLE_CLICK_ZOOM_SCALE = 3;
// Mirrors `_MEDIA_PREVIEW_MAX_DIMENSION` in mockingbird/api/main.py: above
// this, the inline preview is a downsized, re-compressed JPEG, so a deep
// zoom is worth upgrading to the untouched original bytes.
const PREVIEW_MAX_DIMENSION = 1600;
// A saved track box in this product has real, measured off-target error
// (see docs and tests/test_visit_evidence_gallery.py). Padding the focus
// viewport generously -- well beyond the box's own size -- keeps a mildly
// off-target box from framing out the actual subject; a tight crop to the
// box's exact edges would not survive that real-world imprecision.
const FOCUS_PADDING_MULTIPLIER = 6;
const FOCUS_MIN_SPAN = 0.22;

export interface UseEvidenceZoomOptions {
  /** Identity of the currently displayed frame; changing it resets the viewport. */
  frameKey: string;
  previewSrc: string;
  fullResolutionSrc?: string | null;
  alt: string;
  naturalWidth?: number | null;
  naturalHeight?: number | null;
  /**
   * Normalized [left, top, right, bottom] subject box, already validated by
   * the backend as belonging to this exact frame -- or null/undefined when
   * none exists. This hook draws no overlay and offers no Focus control
   * when absent; it never falls back to a box from another frame.
   */
  subjectBox?: number[] | null;
  onPreviewError?: () => void;
}

interface Viewport {
  scale: number;
  originX: number;
  originY: number;
}

const FIT_VIEWPORT: Viewport = { scale: MIN_SCALE, originX: 0.5, originY: 0.5 };

function clamp(value: number, lower: number, upper: number): number {
  return Math.max(lower, Math.min(upper, value));
}

function clampOrigin(origin: number, halfSpan: number): number {
  if (halfSpan >= 0.5) {
    return 0.5;
  }
  return clamp(origin, halfSpan, 1 - halfSpan);
}

function normalizeViewport(scale: number, originX: number, originY: number): Viewport {
  const clampedScale = clamp(scale, MIN_SCALE, MAX_SCALE);
  const halfSpan = 0.5 / clampedScale;
  return {
    scale: clampedScale,
    originX: clampOrigin(originX, halfSpan),
    originY: clampOrigin(originY, halfSpan),
  };
}

function distance(a: { x: number; y: number }, b: { x: number; y: number }): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function midpoint(a: { x: number; y: number }, b: { x: number; y: number }): { x: number; y: number } {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

/** The image's own displayed box at scale 1 ("contain"-fit within the container), before zoom. */
function stageBaseSize(
  containerWidth: number,
  containerHeight: number,
  naturalWidth: number | null,
  naturalHeight: number | null,
): { width: number; height: number } {
  if (containerWidth <= 0 || containerHeight <= 0) {
    return { width: containerWidth, height: containerHeight };
  }
  const imageAspect =
    naturalWidth && naturalHeight && naturalWidth > 0 && naturalHeight > 0
      ? naturalWidth / naturalHeight
      : containerWidth / containerHeight;
  const containerAspect = containerWidth / containerHeight;
  if (imageAspect > containerAspect) {
    return { width: containerWidth, height: containerWidth / imageAspect };
  }
  return { width: containerHeight * imageAspect, height: containerHeight };
}

export interface EvidenceZoomState {
  alt: string;
  /**
   * A callback ref, not a plain ref object: the viewport `<div>` this
   * attaches to unmounts and remounts (e.g. whenever the preview toggles
   * between broken and available), and a plain `useRef` + mount-only effect
   * would keep observing/listening on the node from the *first* mount
   * forever, silently going blank on every later remount.
   */
  containerRef: (node: HTMLDivElement | null) => void;
  handleDoubleClick: (event: React.MouseEvent<HTMLDivElement>) => void;
  handlePointerDown: (event: React.PointerEvent<HTMLDivElement>) => void;
  handlePointerMove: (event: React.PointerEvent<HTMLDivElement>) => void;
  endPointer: (event: React.PointerEvent<HTMLDivElement>) => void;
  hasMeasuredSize: boolean;
  hasValidSubjectBox: boolean;
  subjectBox?: number[] | null;
  stageLeft: number;
  stageTop: number;
  renderedWidth: number;
  renderedHeight: number;
  displaySrc: string;
  onImageLoad: (event: React.SyntheticEvent<HTMLImageElement>) => void;
  onPreviewError?: () => void;
  overlayVisible: boolean;
  setOverlayVisible: (visible: boolean) => void;
  isZoomed: boolean;
  scalePercent: number;
  zoomInStep: () => void;
  zoomOutStep: () => void;
  resetViewport: () => void;
  focusOnEvidence: () => void;
  canZoomIn: boolean;
  fullResolutionSrc?: string | null;
}

/** All zoom/pan/focus state and behavior for one evidence frame. */
export function useEvidenceZoom({
  frameKey,
  previewSrc,
  fullResolutionSrc,
  alt,
  naturalWidth,
  naturalHeight,
  subjectBox,
  onPreviewError,
}: UseEvidenceZoomOptions): EvidenceZoomState {
  const [containerNode, setContainerNode] = useState<HTMLDivElement | null>(null);
  // Stable identity across renders -- an inline `(node) => ...` here would
  // make React detach/reattach it (with a real null in between) on every
  // render, not just on real mount/unmount.
  const containerRef = useCallback((node: HTMLDivElement | null) => {
    setContainerNode(node);
  }, []);
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  const [viewport, setViewport] = useState<Viewport>(FIT_VIEWPORT);
  const [loadedNaturalSize, setLoadedNaturalSize] = useState<{ width: number; height: number } | null>(null);
  const [upgradedSrc, setUpgradedSrc] = useState<string | null>(null);
  const [overlayVisible, setOverlayVisible] = useState(false);
  const pointersRef = useRef(new Map<number, { x: number; y: number }>());
  const dragRef = useRef<{ originX: number; originY: number; x: number; y: number } | null>(null);
  const pinchRef = useRef<{ distance: number } | null>(null);

  // A new frame is a new image: never carry the previous frame's pan/zoom,
  // overlay choice, or upgraded-source state onto it. Resetting inside a
  // `useEffect` would still commit and paint one frame of the *new* image
  // under the *old* viewport/overlay state first; adjusting state directly
  // during render (React's documented pattern for this) discards that
  // stale render before it ever paints.
  const [renderedFrameKey, setRenderedFrameKey] = useState(frameKey);
  if (renderedFrameKey !== frameKey) {
    setRenderedFrameKey(frameKey);
    setViewport(FIT_VIEWPORT);
    setLoadedNaturalSize(null);
    setUpgradedSrc(null);
    setOverlayVisible(false);
    pointersRef.current.clear();
    dragRef.current = null;
    pinchRef.current = null;
  }

  const hasValidSubjectBox =
    Array.isArray(subjectBox) &&
    subjectBox.length === 4 &&
    subjectBox.every((value) => Number.isFinite(value)) &&
    subjectBox[2] > subjectBox[0] &&
    subjectBox[3] > subjectBox[1];

  useEffect(() => {
    if (!containerNode || typeof ResizeObserver === "undefined") {
      return undefined;
    }
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) {
        return;
      }
      setContainerSize({ width: entry.contentRect.width, height: entry.contentRect.height });
    });
    observer.observe(containerNode);
    return () => observer.disconnect();
  }, [containerNode]);

  const effectiveNaturalWidth = naturalWidth ?? loadedNaturalSize?.width ?? null;
  const effectiveNaturalHeight = naturalHeight ?? loadedNaturalSize?.height ?? null;

  // Wheel-to-zoom needs a real preventDefault, which React's synthetic
  // onWheel cannot reliably deliver (root listeners are passive); attach a
  // native, non-passive listener instead. `zoomToward` reads the viewport
  // to zoom from via the `setViewport` updater's own `current` argument
  // (never a closed-over `viewport` variable), so this effect only needs
  // to rebind when the DOM node or the image's own aspect ratio changes --
  // not on every zoom step.
  useEffect(() => {
    if (!containerNode) {
      return undefined;
    }
    const handleWheel = (event: WheelEvent) => {
      event.preventDefault();
      const factor = Math.exp(-event.deltaY * WHEEL_ZOOM_SENSITIVITY);
      zoomToward((currentScale) => currentScale * factor, event.clientX, event.clientY);
    };
    containerNode.addEventListener("wheel", handleWheel, { passive: false });
    return () => containerNode.removeEventListener("wheel", handleWheel);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [containerNode, effectiveNaturalWidth, effectiveNaturalHeight]);

  const offersFullResolutionUpgrade = Boolean(
    fullResolutionSrc &&
      ((effectiveNaturalWidth ?? 0) > PREVIEW_MAX_DIMENSION ||
        (effectiveNaturalHeight ?? 0) > PREVIEW_MAX_DIMENSION),
  );

  // Zoomed in past the preview's own resolution: fetch the untouched
  // original once in the background and swap only after it has fully
  // decoded, so the crisper preview never flashes to blank mid-zoom.
  useEffect(() => {
    if (!offersFullResolutionUpgrade || upgradedSrc || viewport.scale <= MIN_SCALE || !fullResolutionSrc) {
      return undefined;
    }
    let cancelled = false;
    const preload = new Image();
    preload.onload = () => {
      if (!cancelled) {
        setUpgradedSrc(fullResolutionSrc);
      }
    };
    preload.src = fullResolutionSrc;
    return () => {
      cancelled = true;
    };
  }, [offersFullResolutionUpgrade, upgradedSrc, viewport.scale, fullResolutionSrc]);

  /**
   * Zoom to a scale derived from whatever the *current* scale turns out to
   * be when this actually commits -- never a scale value captured earlier
   * in a render closure -- while keeping the same image point under
   * (clientX, clientY) fixed on screen. This makes rapid-fire input (wheel
   * ticks, pinch deltas) compose correctly even across several calls that
   * land before React re-renders in between them.
   */
  function zoomToward(
    nextScaleFor: (currentScale: number) => number,
    clientX: number,
    clientY: number,
  ) {
    const rect = containerNode?.getBoundingClientRect();
    setViewport((current) => {
      const clampedScale = clamp(nextScaleFor(current.scale), MIN_SCALE, MAX_SCALE);
      if (!rect || rect.width <= 0 || rect.height <= 0) {
        return normalizeViewport(clampedScale, current.originX, current.originY);
      }
      const stage = stageBaseSize(rect.width, rect.height, effectiveNaturalWidth, effectiveNaturalHeight);
      const px = clientX - rect.left;
      const py = clientY - rect.top;
      const renderedW = stage.width * current.scale;
      const renderedH = stage.height * current.scale;
      const fx = current.originX + (px - rect.width / 2) / renderedW;
      const fy = current.originY + (py - rect.height / 2) / renderedH;
      const nextRenderedW = stage.width * clampedScale;
      const nextRenderedH = stage.height * clampedScale;
      const nextOriginX = fx - (px - rect.width / 2) / nextRenderedW;
      const nextOriginY = fy - (py - rect.height / 2) / nextRenderedH;
      return normalizeViewport(clampedScale, nextOriginX, nextOriginY);
    });
  }

  function applyViewport(nextScale: number, originX: number, originY: number) {
    setViewport(normalizeViewport(nextScale, originX, originY));
  }

  function zoomInStep() {
    applyViewport(viewport.scale * BUTTON_ZOOM_STEP, viewport.originX, viewport.originY);
  }

  function zoomOutStep() {
    applyViewport(viewport.scale / BUTTON_ZOOM_STEP, viewport.originX, viewport.originY);
  }

  function resetViewport() {
    setViewport(FIT_VIEWPORT);
  }

  function focusOnEvidence() {
    if (!hasValidSubjectBox || !subjectBox) {
      return;
    }
    const [left, top, right, bottom] = subjectBox;
    const centerX = (left + right) / 2;
    const centerY = (top + bottom) / 2;
    const spanX = Math.max((right - left) * FOCUS_PADDING_MULTIPLIER, FOCUS_MIN_SPAN);
    const spanY = Math.max((bottom - top) * FOCUS_PADDING_MULTIPLIER, FOCUS_MIN_SPAN);
    const span = Math.max(spanX, spanY);
    applyViewport(1 / span, centerX, centerY);
  }

  function handlePointerDown(event: React.PointerEvent<HTMLDivElement>) {
    if (pointersRef.current.size >= 2) {
      // Never track more than two contact points; a third finger just rides along.
      return;
    }
    event.currentTarget.setPointerCapture(event.pointerId);
    pointersRef.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointersRef.current.size === 1) {
      dragRef.current = {
        originX: viewport.originX,
        originY: viewport.originY,
        x: event.clientX,
        y: event.clientY,
      };
      pinchRef.current = null;
    } else if (pointersRef.current.size === 2) {
      const [a, b] = Array.from(pointersRef.current.values());
      pinchRef.current = { distance: Math.max(1, distance(a, b)) };
      dragRef.current = null;
    }
  }

  function handlePointerMove(event: React.PointerEvent<HTMLDivElement>) {
    if (!pointersRef.current.has(event.pointerId)) {
      return;
    }
    pointersRef.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const rect = containerNode?.getBoundingClientRect();
    if (!rect || rect.width <= 0 || rect.height <= 0) {
      return;
    }

    if (pointersRef.current.size === 2) {
      const [a, b] = Array.from(pointersRef.current.values());
      const currentDistance = Math.max(1, distance(a, b));
      const previous = pinchRef.current;
      pinchRef.current = { distance: currentDistance };
      if (previous) {
        const factor = currentDistance / previous.distance;
        const center = midpoint(a, b);
        zoomToward((currentScale) => currentScale * factor, center.x, center.y);
      }
      return;
    }

    const drag = dragRef.current;
    if (!drag || pointersRef.current.size !== 1) {
      return;
    }
    const stage = stageBaseSize(rect.width, rect.height, effectiveNaturalWidth, effectiveNaturalHeight);
    const renderedW = stage.width * viewport.scale;
    const renderedH = stage.height * viewport.scale;
    const dxFraction = (event.clientX - drag.x) / renderedW;
    const dyFraction = (event.clientY - drag.y) / renderedH;
    applyViewport(viewport.scale, drag.originX - dxFraction, drag.originY - dyFraction);
  }

  function endPointer(event: React.PointerEvent<HTMLDivElement>) {
    pointersRef.current.delete(event.pointerId);
    if (pointersRef.current.size === 1) {
      const [remaining] = Array.from(pointersRef.current.entries());
      dragRef.current = {
        originX: viewport.originX,
        originY: viewport.originY,
        x: remaining[1].x,
        y: remaining[1].y,
      };
    } else {
      dragRef.current = null;
    }
    pinchRef.current = null;
  }

  const isZoomed = viewport.scale > MIN_SCALE + SCALE_EPSILON;

  function handleDoubleClick(event: React.MouseEvent<HTMLDivElement>) {
    if (isZoomed) {
      resetViewport();
    } else {
      zoomToward(() => DOUBLE_CLICK_ZOOM_SCALE, event.clientX, event.clientY);
    }
  }

  const stage = stageBaseSize(containerSize.width, containerSize.height, effectiveNaturalWidth, effectiveNaturalHeight);
  const renderedWidth = stage.width * viewport.scale;
  const renderedHeight = stage.height * viewport.scale;
  const stageLeft = containerSize.width / 2 - viewport.originX * renderedWidth;
  const stageTop = containerSize.height / 2 - viewport.originY * renderedHeight;
  const hasMeasuredSize = containerSize.width > 0 && containerSize.height > 0;
  const displaySrc = upgradedSrc ?? previewSrc;

  return {
    alt,
    containerRef,
    handleDoubleClick,
    handlePointerDown,
    handlePointerMove,
    endPointer,
    hasMeasuredSize,
    hasValidSubjectBox,
    subjectBox,
    stageLeft,
    stageTop,
    renderedWidth,
    renderedHeight,
    displaySrc,
    onImageLoad: (event) => {
      const element = event.currentTarget as HTMLImageElement;
      if (element.naturalWidth > 0 && element.naturalHeight > 0) {
        setLoadedNaturalSize({ width: element.naturalWidth, height: element.naturalHeight });
      }
    },
    onPreviewError,
    overlayVisible,
    setOverlayVisible,
    isZoomed,
    scalePercent: Math.round(viewport.scale * 100),
    zoomInStep,
    zoomOutStep,
    resetViewport,
    focusOnEvidence,
    canZoomIn: viewport.scale < MAX_SCALE - SCALE_EPSILON,
    fullResolutionSrc,
  };
}

/** The pannable image itself; render this to fill an existing fixed-box image container. */
export function EvidenceZoomViewport({ zoom }: { zoom: EvidenceZoomState }) {
  return (
    <div
      aria-label={zoom.alt}
      className={`evidence-zoom-viewport${zoom.isZoomed ? " is-zoomed" : ""}`}
      onDoubleClick={zoom.handleDoubleClick}
      onPointerCancel={zoom.endPointer}
      onPointerDown={zoom.handlePointerDown}
      onPointerMove={zoom.handlePointerMove}
      onPointerUp={zoom.endPointer}
      ref={zoom.containerRef}
      role="img"
      style={{ touchAction: zoom.isZoomed ? "none" : "pan-y" }}
    >
      {zoom.hasMeasuredSize ? (
        <div
          className="evidence-zoom-stage"
          style={{ left: zoom.stageLeft, top: zoom.stageTop, width: zoom.renderedWidth, height: zoom.renderedHeight }}
        >
          <img
            alt=""
            aria-hidden="true"
            draggable={false}
            onError={zoom.onPreviewError}
            onLoad={zoom.onImageLoad}
            src={zoom.displaySrc}
          />
          {zoom.overlayVisible && zoom.hasValidSubjectBox && zoom.subjectBox ? (
            <div
              aria-hidden="true"
              className="evidence-zoom-subject-box"
              style={{
                left: `${zoom.subjectBox[0] * 100}%`,
                top: `${zoom.subjectBox[1] * 100}%`,
                width: `${(zoom.subjectBox[2] - zoom.subjectBox[0]) * 100}%`,
                height: `${(zoom.subjectBox[3] - zoom.subjectBox[1]) * 100}%`,
              }}
            >
              <span>Tracked region</span>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** The zoom/pan/focus toolbar; render this outside the fixed-box image container. */
export function EvidenceZoomControls({ zoom }: { zoom: EvidenceZoomState }) {
  return (
    <div className="evidence-zoom-controls">
      <button
        aria-label="Zoom out"
        className="secondary-action"
        disabled={!zoom.isZoomed}
        onClick={zoom.zoomOutStep}
        type="button"
      >
        −
      </button>
      <span aria-live="polite" className="evidence-zoom-level">
        {zoom.scalePercent}%
      </span>
      <button
        aria-label="Zoom in"
        className="secondary-action"
        disabled={!zoom.canZoomIn}
        onClick={zoom.zoomInStep}
        type="button"
      >
        +
      </button>
      <button
        className="secondary-action"
        disabled={!zoom.isZoomed}
        onClick={zoom.resetViewport}
        type="button"
      >
        Reset view
      </button>
      {zoom.hasValidSubjectBox ? (
        <button className="secondary-action" onClick={zoom.focusOnEvidence} type="button">
          Focus on evidence
        </button>
      ) : null}
      {zoom.hasValidSubjectBox ? (
        <label className="evidence-zoom-overlay-toggle">
          <input
            checked={zoom.overlayVisible}
            onChange={(event) => zoom.setOverlayVisible(event.target.checked)}
            type="checkbox"
          />
          Show tracked region
        </label>
      ) : null}
      {zoom.fullResolutionSrc ? (
        <a className="text-action" href={zoom.fullResolutionSrc} rel="noreferrer" target="_blank">
          Full resolution ↗
        </a>
      ) : null}
    </div>
  );
}
