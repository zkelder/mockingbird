import type { Detection } from "../api/types";
import { formatLabel } from "../utils";
import { ConfidenceBar } from "./ConfidenceBar";
import { EvidenceBadge } from "./EvidenceBadge";

interface DetectionEvidenceCardProps {
  detection: Detection;
  zoneLabel?: string;
  statusLabel?: string;
  compact?: boolean;
}

function bboxSummary(detection: Detection): string {
  if (!detection.bbox) {
    return "No bounding box";
  }

  return `${Math.round(detection.bbox.x * 100)}%, ${Math.round(
    detection.bbox.y * 100,
  )}% / ${Math.round(detection.bbox.width * 100)}% x ${Math.round(
    detection.bbox.height * 100,
  )}%`;
}

function originLabel(detection: Detection): string {
  return detection.id.startsWith("detection-proposal")
    ? "Converted proposal evidence"
    : "Detection evidence";
}

export function DetectionEvidenceCard({
  detection,
  zoneLabel,
  statusLabel = "Evidence only",
  compact = false,
}: DetectionEvidenceCardProps) {
  return (
    <article className={compact ? "evidence-card evidence-card-compact" : "evidence-card"}>
      <div className="item-title-row">
        <div>
          <span className="meta-text">{originLabel(detection)}</span>
          <h3>{formatLabel(detection.label)}</h3>
        </div>
        <EvidenceBadge label={statusLabel} tone="evidence" />
      </div>
      <ConfidenceBar value={detection.confidence} />
      <div className="evidence-card-meta">
        <span>Zone: {zoneLabel ?? detection.zone_id ?? "Unzoned"}</span>
        <span>Box: {bboxSummary(detection)}</span>
      </div>
    </article>
  );
}
