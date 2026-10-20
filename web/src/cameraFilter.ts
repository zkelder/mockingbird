import type { CameraSource, Stream } from "./api/types";

/**
 * Multi-Camera Attribution & Filter Consolidation v1 -- the one camera-filter
 * vocabulary every applicable surface shares (see
 * docs/multi-camera-attribution-filter-consolidation-contract.md).
 *
 * Pure, DOM-free helpers so serialization/restoration and multi-select
 * semantics are testable on their own. Identity is always a stable Source or
 * Stream id; a display name is only ever a label, never authority.
 *
 * "No selection" means "all cameras" everywhere -- never an empty list sent to
 * a server that would reject it.
 */

export const ALL_CAMERAS_LABEL = "All cameras";
export const UNAVAILABLE_CAMERA_LABEL = "Unavailable camera";

export interface CameraFilterOption {
  id: string;
  label: string;
}

/** Stable, de-duplicated, trimmed ids from every `?param=` occurrence. */
export function readCameraIds(search: string | URLSearchParams, param: string): string[] {
  const params = typeof search === "string" ? new URLSearchParams(search) : search;
  const seen = new Set<string>();
  const ids: string[] = [];
  for (const raw of params.getAll(param)) {
    const id = raw.trim();
    if (id && !seen.has(id)) {
      seen.add(id);
      ids.push(id);
    }
  }
  return ids;
}

/** Replace every `param` occurrence with the given ids (none => param absent). */
export function writeCameraIds(params: URLSearchParams, param: string, ids: readonly string[]): URLSearchParams {
  params.delete(param);
  for (const id of new Set(ids.map((item) => item.trim()).filter(Boolean))) {
    params.append(param, id);
  }
  return params;
}

export function toggleCameraId(ids: readonly string[], id: string): string[] {
  return ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id];
}

/** Ids the current options cannot resolve (e.g. a stale deep link). */
export function unavailableCameraIds(ids: readonly string[], options: readonly CameraFilterOption[]): string[] {
  const known = new Set(options.map((option) => option.id));
  return ids.filter((id) => !known.has(id));
}

export function cameraScopeSummary(selected: number, total: number): string {
  if (selected === 0) return "No cameras selected -- every camera is included.";
  return `Limited to ${selected} of ${total} cameras.`;
}

function cameraLabel(name: string, flags: { archived: boolean; sample: boolean }): string {
  return `${name}${flags.sample ? " (sample)" : ""}${flags.archived ? " (archived)" : ""}`;
}

/** One option per Source -- the physical camera. */
export function sourceCameraOptions(sources: readonly CameraSource[]): CameraFilterOption[] {
  return sources.map((source) => ({
    id: source.id,
    label: cameraLabel(source.name, { archived: source.status === "archived", sample: source.kind === "demo" }),
  }));
}

/** One option per Stream; archived/sample state comes from its Source. */
export function streamCameraOptions(
  streams: readonly Stream[],
  sources: readonly CameraSource[],
): CameraFilterOption[] {
  const sourceById = new Map(sources.map((source) => [source.id, source]));
  return streams.map((stream) => {
    const source = sourceById.get(stream.source_id);
    return {
      id: stream.id,
      label: cameraLabel(stream.name, {
        archived: source?.status === "archived",
        sample: source?.kind === "demo",
      }),
    };
  });
}
