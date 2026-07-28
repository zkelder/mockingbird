import { useEffect, useRef, useState } from "react";
import { apiClient } from "../api/client";

export type CurrentFrameState = "live" | "delayed" | "stale" | "unavailable";

export interface CurrentFrameMetadata {
  sequence: number | null;
  capturedAt: string | null;
  ageMs: number | null;
  width: number | null;
  height: number | null;
  state: CurrentFrameState;
}

interface CurrentFrameViewProps {
  active: boolean;
  alt: string;
  className?: string;
  streamId: string;
  onFrameChange?: (frame: CurrentFrameMetadata) => void;
}

const REFRESH_MS = 1_000;

function numberHeader(headers: Headers, name: string): number | null {
  const value = Number(headers.get(name));
  return Number.isFinite(value) ? value : null;
}

export function currentFrameMetadata(headers: Headers): CurrentFrameMetadata {
  const ageMs = numberHeader(headers, "X-MockingBird-Frame-Age-Ms");
  const explicitState = headers.get("X-MockingBird-Frame-State");
  const state =
    explicitState === "live" || explicitState === "delayed" || explicitState === "stale"
      ? explicitState
      : ageMs == null || ageMs > 10_000
        ? "stale"
        : ageMs > 2_500
          ? "delayed"
          : "live";
  return {
    sequence: numberHeader(headers, "X-MockingBird-Frame-Sequence"),
    capturedAt: headers.get("X-MockingBird-Frame-Captured-At"),
    ageMs,
    width: numberHeader(headers, "X-MockingBird-Frame-Width"),
    height: numberHeader(headers, "X-MockingBird-Frame-Height"),
    state,
  };
}

function ageLabel(ageMs: number | null): string {
  if (ageMs == null) return "age unavailable";
  if (ageMs < 1_000) return `${Math.max(0, Math.round(ageMs))} ms old`;
  return `${(ageMs / 1_000).toFixed(1)} sec old`;
}

function capturedLabel(capturedAt: string | null): string {
  if (!capturedAt) return "captured time unavailable";
  const parsed = new Date(capturedAt);
  return Number.isNaN(parsed.valueOf()) ? "captured time unavailable" : parsed.toLocaleTimeString();
}

/** A bounded still-image viewer for an already running local camera session. */
export function CurrentFrameView({ active, alt, className, streamId, onFrameChange }: CurrentFrameViewProps) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [frame, setFrame] = useState<CurrentFrameMetadata>({
    sequence: null,
    capturedAt: null,
    ageMs: null,
    width: null,
    height: null,
    state: "unavailable",
  });
  const latestSequenceRef = useRef<number | null>(null);
  const inFlightRef = useRef(false);
  const imageUrlRef = useRef<string | null>(null);
  const callbackRef = useRef(onFrameChange);

  useEffect(() => {
    callbackRef.current = onFrameChange;
  }, [onFrameChange]);

  useEffect(() => {
    let disposed = false;
    let timer: number | null = null;
    let controller: AbortController | null = null;

    const publish = (next: CurrentFrameMetadata) => {
      if (disposed) return;
      setFrame(next);
      callbackRef.current?.(next);
    };

    const schedule = () => {
      if (!disposed && active && !document.hidden) {
        timer = window.setTimeout(poll, REFRESH_MS);
      }
    };

    const clearImage = () => {
      if (imageUrlRef.current) URL.revokeObjectURL(imageUrlRef.current);
      imageUrlRef.current = null;
      setImageUrl(null);
    };

    const poll = async () => {
      if (disposed || !active || document.hidden || inFlightRef.current) return;
      inFlightRef.current = true;
      controller = new AbortController();
      try {
        const cacheToken = latestSequenceRef.current ?? 0;
        const response = await fetch(
          `${apiClient.liveCameraCurrentFrameUrl(streamId)}?frame=${cacheToken}-${Date.now()}`,
          { cache: "no-store", signal: controller.signal },
        );
        if (!response.ok) {
          clearImage();
          publish({ sequence: null, capturedAt: null, ageMs: null, width: null, height: null, state: "unavailable" });
          return;
        }
        const metadata = currentFrameMetadata(response.headers);
        // A delayed response may never replace a newer cached frame.
        if (
          metadata.sequence != null &&
          latestSequenceRef.current != null &&
          metadata.sequence <= latestSequenceRef.current
        ) {
          return;
        }
        const blob = await response.blob();
        if (disposed) return;
        const nextUrl = URL.createObjectURL(blob);
        if (imageUrlRef.current) URL.revokeObjectURL(imageUrlRef.current);
        imageUrlRef.current = nextUrl;
        setImageUrl(nextUrl);
        latestSequenceRef.current = metadata.sequence;
        publish(metadata);
      } catch (error) {
        if (!disposed && !(error instanceof DOMException && error.name === "AbortError")) {
          clearImage();
          publish({ sequence: null, capturedAt: null, ageMs: null, width: null, height: null, state: "unavailable" });
        }
      } finally {
        inFlightRef.current = false;
        controller = null;
        schedule();
      }
    };

    const onVisibilityChange = () => {
      if (document.hidden) {
        if (timer != null) window.clearTimeout(timer);
        controller?.abort();
        return;
      }
      void poll();
    };

    if (active) void poll();
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      disposed = true;
      if (timer != null) window.clearTimeout(timer);
      controller?.abort();
      document.removeEventListener("visibilitychange", onVisibilityChange);
      if (imageUrlRef.current) URL.revokeObjectURL(imageUrlRef.current);
      imageUrlRef.current = null;
    };
  }, [active, streamId]);

  if (!active || !imageUrl) {
    return (
      <div className="stream-live-placeholder current-frame-empty">
        <strong>{active ? "Current camera frame unavailable" : "Current camera view hidden"}</strong>
        <span>Viewing this camera never starts monitoring or saves a frame.</span>
      </div>
    );
  }

  return (
    <>
      <img alt={alt} className={className} src={imageUrl} />
      <div className={`current-frame-status is-${frame.state}`} role="status">
        <strong>{frame.state === "live" ? "Live snapshot" : frame.state === "delayed" ? "Delayed snapshot" : "Stale snapshot"}</strong>
        <span>{capturedLabel(frame.capturedAt)} · {ageLabel(frame.ageMs)}</span>
        <span>{frame.width && frame.height ? `${frame.width}×${frame.height}` : "dimensions unavailable"}</span>
      </div>
    </>
  );
}
