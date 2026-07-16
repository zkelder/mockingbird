import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { apiClient } from "../api/client";
import type { MediaAsset } from "../api/types";
import { formatDateTime } from "../utils";

interface MediaAssetPreviewProps {
  asset: MediaAsset;
  compact?: boolean;
  surfaceOverlay?: ReactNode;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  const kib = bytes / 1024;
  if (kib < 1024) {
    return `${kib.toFixed(1)} KiB`;
  }

  return `${(kib / 1024).toFixed(1)} MiB`;
}

export function MediaAssetPreview({
  asset,
  compact = false,
  surfaceOverlay,
}: MediaAssetPreviewProps) {
  const [previewFailed, setPreviewFailed] = useState(false);
  const [imageDimensions, setImageDimensions] = useState<{
    width: number;
    height: number;
  } | null>(null);
  const fileUrl = apiClient.mediaFileUrl(asset.id);
  const canPreview = !previewFailed && (asset.media_type === "image" || asset.media_type === "video");
  const imageStageStyle: CSSProperties | undefined = imageDimensions
    ? {
        aspectRatio: `${imageDimensions.width} / ${imageDimensions.height}`,
        width: `min(100%, ${Math.min(
          imageDimensions.width,
          (compact ? 220 : 420) * (imageDimensions.width / imageDimensions.height),
        )}px)`,
      }
    : undefined;

  useEffect(() => {
    setPreviewFailed(false);
    setImageDimensions(null);
  }, [asset.id]);

  return (
    <div className={compact ? "media-preview media-preview-compact" : "media-preview"}>
      <div className="media-preview-surface">
        {canPreview && asset.media_type === "image" ? (
          <div className="media-preview-image-stage" style={imageStageStyle}>
            <img
              alt={asset.original_filename}
              onError={() => setPreviewFailed(true)}
              onLoad={(event) =>
                setImageDimensions({
                  width: event.currentTarget.naturalWidth,
                  height: event.currentTarget.naturalHeight,
                })
              }
              src={fileUrl}
            />
            {surfaceOverlay}
          </div>
        ) : canPreview && asset.media_type === "video" ? (
          <video
            controls
            onError={() => setPreviewFailed(true)}
            preload="metadata"
            src={fileUrl}
          />
        ) : (
          <div className="media-preview-fallback">
            <strong>{asset.original_filename}</strong>
            <span>{asset.content_type}</span>
            <span>{asset.local_path}</span>
          </div>
        )}
        {canPreview && asset.media_type === "video" ? surfaceOverlay : null}
      </div>
      <div className="media-preview-meta">
        <strong>{asset.original_filename}</strong>
        <span>{asset.content_type}</span>
        <span>{formatBytes(asset.file_size_bytes)}</span>
        <span>{formatDateTime(asset.created_at)}</span>
      </div>
    </div>
  );
}
