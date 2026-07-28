import { useEffect, useMemo, useRef, useState } from "react";
import { apiClient } from "../api/client";
import type { RefinedCropResponse, VisitEvidenceFrame } from "../api/types";

type CropBox = { left: number; top: number; right: number; bottom: number };
type DragMode = "move" | "nw" | "ne" | "sw" | "se";

const DEFAULT_BOX: CropBox = { left: 0.12, top: 0.12, right: 0.88, bottom: 0.88 };

function clamp(value: number, lower: number, upper: number): number {
  return Math.max(lower, Math.min(upper, value));
}

function validBox(box: CropBox, minWidth: number, minHeight: number): boolean {
  const area = (box.right - box.left) * (box.bottom - box.top);
  return (
    box.left >= 0 && box.top >= 0 && box.right <= 1 && box.bottom <= 1 &&
    box.right - box.left >= minWidth && box.bottom - box.top >= minHeight && area <= 0.9
  );
}

function coerceBox(value: number[] | null | undefined, minWidth: number, minHeight: number): CropBox {
  if (!value || value.length !== 4) return DEFAULT_BOX;
  const [left, top, right, bottom] = value;
  const candidate = { left, top, right, bottom };
  return validBox(candidate, minWidth, minHeight) ? candidate : DEFAULT_BOX;
}

export function RefinedCropEditor({
  visitId,
  fullFrame,
  initialBounds,
  onSaved,
}: {
  visitId: string;
  fullFrame: VisitEvidenceFrame | null;
  initialBounds?: number[] | null;
  onSaved: (response: RefinedCropResponse) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [box, setBox] = useState<CropBox>(DEFAULT_BOX);
  const [message, setMessage] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const dragRef = useRef<{ mode: DragMode; start: CropBox; x: number; y: number } | null>(null);
  const minWidth = useMemo(() => Math.max(0.02, 64 / (fullFrame?.width ?? 1600)), [fullFrame?.width]);
  const minHeight = useMemo(() => Math.max(0.02, 64 / (fullFrame?.height ?? 1000)), [fullFrame?.height]);
  const fullUrl = fullFrame
    ? `${apiClient.baseUrl}/api/media/${fullFrame.media_asset_id}/full-resolution`
    : null;

  useEffect(() => {
    if (!isOpen) setBox(coerceBox(initialBounds, minWidth, minHeight));
  }, [initialBounds, isOpen, minHeight, minWidth]);

  if (!fullFrame || !fullUrl) return null;

  function startDrag(event: React.PointerEvent<HTMLElement>, mode: DragMode) {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    const rect = imageRef.current?.getBoundingClientRect();
    if (!rect) return;
    dragRef.current = {
      mode,
      start: box,
      x: (event.clientX - rect.left) / rect.width,
      y: (event.clientY - rect.top) / rect.height,
    };
  }

  function moveDrag(event: React.PointerEvent<HTMLElement>) {
    const drag = dragRef.current;
    const rect = imageRef.current?.getBoundingClientRect();
    if (!drag || !rect) return;
    const x = clamp((event.clientX - rect.left) / rect.width, 0, 1);
    const y = clamp((event.clientY - rect.top) / rect.height, 0, 1);
    const dx = x - drag.x;
    const dy = y - drag.y;
    let next = { ...drag.start };
    if (drag.mode === "move") {
      const width = next.right - next.left;
      const height = next.bottom - next.top;
      next.left = clamp(drag.start.left + dx, 0, 1 - width);
      next.top = clamp(drag.start.top + dy, 0, 1 - height);
      next.right = next.left + width;
      next.bottom = next.top + height;
    } else {
      if (drag.mode.includes("n")) next.top = clamp(y, 0, drag.start.bottom - minHeight);
      if (drag.mode.includes("s")) next.bottom = clamp(y, drag.start.top + minHeight, 1);
      if (drag.mode.includes("w")) next.left = clamp(x, 0, drag.start.right - minWidth);
      if (drag.mode.includes("e")) next.right = clamp(x, drag.start.left + minWidth, 1);
    }
    setBox(next);
  }

  function endDrag() {
    dragRef.current = null;
  }

  function setEdge(edge: keyof CropBox, raw: string) {
    const value = Number(raw);
    if (!Number.isFinite(value)) return;
    setBox((current) => {
      const next = { ...current, [edge]: clamp(value, 0, 1) };
      if (edge === "left") next.left = Math.min(next.left, next.right - minWidth);
      if (edge === "right") next.right = Math.max(next.right, next.left + minWidth);
      if (edge === "top") next.top = Math.min(next.top, next.bottom - minHeight);
      if (edge === "bottom") next.bottom = Math.max(next.bottom, next.top + minHeight);
      return next;
    });
  }

  async function save() {
    if (!validBox(box, minWidth, minHeight)) {
      setMessage("Keep the crop inside the image and above the visible minimum size.");
      return;
    }
    setIsSaving(true);
    setMessage(null);
    try {
      const response = await apiClient.createRefinedVisitCrop(visitId, box);
      onSaved(response);
      setMessage(response.message);
      setIsOpen(false);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not save the refined crop.");
    } finally {
      setIsSaving(false);
    }
  }

  const width = box.right - box.left;
  const height = box.bottom - box.top;
  const approxWidth = Math.round((fullFrame.width ?? 0) * width);
  const approxHeight = Math.round((fullFrame.height ?? 0) * height);
  const previewStyle = {
    width: `${100 / width}%`,
    maxWidth: "none",
    transform: `translate(${-box.left * 100}%, ${-box.top * 100}%)`,
    transformOrigin: "top left",
  };

  return (
    <div className="refined-crop-control">
      <button className="secondary-action" onClick={() => { setBox(coerceBox(initialBounds, minWidth, minHeight)); setMessage(null); setIsOpen(true); }} type="button">
        Adjust crop
      </button>
      {message && !isOpen ? <span aria-live="polite" className="meta-text">{message}</span> : null}
      {isOpen ? (
        <section aria-label="Adjust high-resolution crop" aria-modal="true" className="panel refined-crop-editor" role="dialog">
          <div className="detail-actions"><div><h3>Adjust crop</h3><p className="meta-text">The original full-resolution image stays unchanged. Saving creates new evidence only.</p></div><button className="text-action" disabled={isSaving} onClick={() => setIsOpen(false)} type="button">Cancel</button></div>
          <div className="refined-crop-workspace">
            <div className="refined-crop-source" onPointerMove={moveDrag} onPointerUp={endDrag}>
              <img alt="Full-resolution source for crop adjustment" ref={imageRef} src={fullUrl} />
              <div
                aria-label="Crop selection. Use numeric controls for keyboard adjustment."
                className="refined-crop-selection"
                onPointerDown={(event) => startDrag(event, "move")}
                style={{ left: `${box.left * 100}%`, top: `${box.top * 100}%`, width: `${width * 100}%`, height: `${height * 100}%` }}
                tabIndex={0}
              >
                {(["nw", "ne", "sw", "se"] as DragMode[]).map((handle) => <button aria-label={`Resize crop ${handle}`} className={`refined-crop-handle refined-crop-handle-${handle}`} key={handle} onPointerDown={(event) => startDrag(event, handle)} type="button" />)}
              </div>
            </div>
            <div className="refined-crop-preview"><strong>Live preview</strong><div className="refined-crop-preview-image"><img alt="Selected crop preview" src={fullUrl} style={previewStyle} /></div><span>{approxWidth} × {approxHeight} px approximately</span></div>
          </div>
          <fieldset className="refined-crop-coordinates"><legend>Crop bounds (normalized source coordinates)</legend>{(["left", "top", "right", "bottom"] as (keyof CropBox)[]).map((edge) => <label key={edge}>{edge}<input aria-label={`Crop ${edge}`} max="1" min="0" onChange={(event) => setEdge(edge, event.target.value)} step="0.001" type="number" value={box[edge].toFixed(3)} /></label>)}</fieldset>
          {message ? <div aria-live="polite" className="notice-panel">{message}</div> : null}
          <div className="detail-actions"><button className="text-action" disabled={isSaving} onClick={() => setIsOpen(false)} type="button">Cancel</button><button className="primary-action" disabled={isSaving || !validBox(box, minWidth, minHeight)} onClick={() => void save()} type="button">{isSaving ? "Saving…" : "Save refined crop"}</button></div>
        </section>
      ) : null}
    </div>
  );
}
