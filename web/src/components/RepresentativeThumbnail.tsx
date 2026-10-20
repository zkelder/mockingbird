import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type { VisitEvidenceFrame } from "../api/types";
import { thumbnailFraming } from "./subjectFraming";

/**
 * Place Story Deep Dives & Representative Evidence v1: one representative
 * evidence image, rendered the same calm way across every surface that
 * shows one -- mirrors BirdLogPage.tsx's own established `JournalThumbnail`
 * convention (fallback copy, `onError` handling, and the honest "heard, not
 * seen" audio case) without duplicating that already-accepted, tested
 * component's own internals. Deliberately accepts only a bare
 * `VisitEvidenceFrame` (never a taxon- or Feature-specific response shape),
 * since Today/Bird Log's `WildlifeJournalRepresentative` and a Place
 * Feature's own `RepresentativeEvidence` wrap the identical frame two
 * different ways -- this component is the one place that actually renders
 * it, so a Taxon Story and a Feature Story page never invent two different
 * "how do I show a representative photo" conventions.
 *
 * `alt` must already be composed by the caller from Reviewed-truth context
 * (see docs/representative-species-evidence-contract.md and
 * product-doctrine.md's "Do not use taxon identification as alt text if
 * that would overstate truth") -- this component never fabricates one.
 */
interface RepresentativeThumbnailProps {
  evidence: VisitEvidenceFrame | null | undefined;
  alt: string;
  fallbackText?: string;
}

export function RepresentativeThumbnail({
  evidence,
  alt,
  fallbackText = "No image available",
}: RepresentativeThumbnailProps) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [evidence?.media_asset_id]);

  if (!evidence || failed) {
    return <div className="journal-thumbnail-fallback">{fallbackText}</div>;
  }
  // Acoustic / BirdNET Observation Foundation v1: an honest "heard, not
  // seen" state, never the same copy a genuinely missing image uses.
  if (evidence.content_type.startsWith("audio/")) {
    return (
      <div aria-label={alt} className="journal-thumbnail-fallback journal-thumbnail-audio">
        🔊 Heard
      </div>
    );
  }
  const framing = thumbnailFraming(evidence);
  return (
    <img
      alt={alt}
      className={framing.className || undefined}
      style={framing.style}
      loading="lazy"
      onError={() => setFailed(true)}
      src={`${apiClient.baseUrl}${evidence.preview_url}`}
    />
  );
}
