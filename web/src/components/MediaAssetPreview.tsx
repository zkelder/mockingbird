import { apiClient } from "../api/client";
import type { MediaAsset } from "../api/types";
import { formatDateTime } from "../utils";

interface MediaAssetPreviewProps {
  asset: MediaAsset;
  compact?: boolean;
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

export function MediaAssetPreview({ asset, compact = false }: MediaAssetPreviewProps) {
  const fileUrl = apiClient.mediaFileUrl(asset.id);

  return (
    <div className={compact ? "media-preview media-preview-compact" : "media-preview"}>
      <div className="media-preview-surface">
        {asset.media_type === "image" ? (
          <img alt={asset.original_filename} src={fileUrl} />
        ) : asset.media_type === "video" ? (
          <video controls preload="metadata" src={fileUrl} />
        ) : (
          <span className="meta-text">{asset.local_path}</span>
        )}
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
