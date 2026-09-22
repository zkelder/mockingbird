import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type { CameraSource, Stream } from "../api/types";

// UI/UX & First-Run Adoption v1: Streams that belong to a real (non-demo)
// Source, for pages that must never offer the seeded demo Source as a
// target (media imported there is hidden by every review/history surface).
// Mirrors the backend's `_real_source_condition`: a Source's configured
// provider decides; its original `kind` only matters until that is known.
// Only `kind === "demo"` Sources need a lookup (a repurposed demo Source
// keeps `kind: "demo"` forever), so this is usually one small request.
export function useRealStreams(streams: Stream[], sources: CameraSource[]): Stream[] {
  const [repurposedDemoSourceIds, setRepurposedDemoSourceIds] = useState<Set<string>>(() => new Set());
  const demoKindSourceIds = useMemo(
    () => sources.filter((source) => source.kind === "demo").map((source) => source.id),
    [sources],
  );

  useEffect(() => {
    let isMounted = true;
    if (demoKindSourceIds.length === 0) {
      setRepurposedDemoSourceIds(new Set());
      return;
    }
    void Promise.all(
      demoKindSourceIds.map((sourceId) =>
        apiClient
          .getSourceSetupReview(sourceId)
          .then((review) => (review.provider_key === "demo" ? null : sourceId))
          .catch(() => null),
      ),
    ).then((ids) => {
      if (isMounted) {
        setRepurposedDemoSourceIds(new Set(ids.filter((id): id is string => id !== null)));
      }
    });
    return () => {
      isMounted = false;
    };
  }, [demoKindSourceIds]);

  return useMemo(() => {
    const demoSourceIds = new Set(demoKindSourceIds.filter((id) => !repurposedDemoSourceIds.has(id)));
    return streams.filter((stream) => !demoSourceIds.has(stream.source_id));
  }, [demoKindSourceIds, repurposedDemoSourceIds, streams]);
}
