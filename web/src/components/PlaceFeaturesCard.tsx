import { useState } from "react";
import type {
  CameraSource,
  PlaceFeature,
  PlaceFeatureChangeEventCreate,
  PlaceFeatureChangeEventType,
  PlaceFeatureCreate,
  PlaceFeatureObservationLinkCreate,
  PlaceFeatureType,
  PlaceFeatureUpdate,
  PlaceFeaturesSummary,
  Stream,
  Zone,
} from "../api/types";
import { StatusPill } from "./StatusPill";

interface PlaceFeaturesCardProps {
  summary: PlaceFeaturesSummary | null;
  features: PlaceFeature[] | null;
  zones: Zone[] | null;
  sources: CameraSource[] | null;
  streams: Stream[] | null;
  onAddFeature: (payload: PlaceFeatureCreate) => Promise<void>;
  onUpdateFeature: (featureId: string, payload: PlaceFeatureUpdate) => Promise<void>;
  onRemoveFeature: (featureId: string) => Promise<string | null>;
  onAddChangeEvent: (payload: PlaceFeatureChangeEventCreate) => Promise<void>;
  onAddObservationLink: (
    featureId: string,
    payload: PlaceFeatureObservationLinkCreate,
  ) => Promise<string | null>;
  onRemoveObservationLink: (featureId: string, linkId: string) => Promise<string | null>;
  // Place Story Deep Dives & Representative Evidence v1: tapping a Feature
  // name in the calm view opens its own Feature Story -- optional so this
  // card still renders (as a plain, non-interactive tag) for any caller
  // that has not wired navigation.
  onOpenFeatureStory?: (featureId: string) => void;
}

const FEATURE_TYPE_LABELS: Record<PlaceFeatureType, string> = {
  feeder: "Feeder",
  water: "Water",
  nest_box: "Nest box",
  vegetation_patch: "Vegetation patch",
  structure: "Structure",
  habitat_area: "Habitat area",
  other: "Other",
};

const CHANGE_EVENT_TYPE_LABELS: Record<PlaceFeatureChangeEventType, string> = {
  added: "Added",
  removed: "Removed",
  moved: "Moved",
  modified: "Modified",
  replenished: "Replenished",
  food_changed: "Food changed",
  vegetation_changed: "Vegetation changed",
  other: "Other",
};

// Matches `StreamsPage.tsx`'s own canonical archived-camera option copy
// exactly (" (archived)" appended to the name) -- the one established
// precedent for showing an archived camera in a picker without hiding it.
function sourceOptionLabel(source: CameraSource): string {
  return source.status === "archived" ? `${source.name} (archived)` : source.name;
}

/**
 * Place Features & Habitat Change v2 (see docs/place-features-habitat-
 * change-v2-contract.md "Product surfaces"), extended by Multi-Camera Place
 * Feature Linking & Cross-View Habitat Context v1 to let one Feature be
 * "Observed by" more than one camera/Zone view. A sibling of
 * `HabitatPhenologyCard`, same calm-view/inline-edit-toggle shape: a
 * restrained summary line plus active-feature tags when not editing, a
 * fuller CRUD surface (add/edit/deactivate/remove a Feature; manage its
 * observation links; record a change) when editing. `onRemoveFeature`/
 * `onAddObservationLink`/`onRemoveObservationLink` return a user-safe error
 * message (never a raw exception) so a blocked operation can explain itself
 * rather than failing silently or throwing.
 *
 * Renders nothing while both fetches are still in flight (`summary` and
 * `features` both `null`), matching `HabitatPhenologyCard`'s identical
 * absence-safety discipline -- a failed/slow fetch here must never block
 * the rest of the Dashboard.
 */
export function PlaceFeaturesCard({
  summary,
  features,
  zones,
  sources,
  streams,
  onAddFeature,
  onUpdateFeature,
  onRemoveFeature,
  onAddChangeEvent,
  onAddObservationLink,
  onRemoveObservationLink,
  onOpenFeatureStory,
}: PlaceFeaturesCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [featureType, setFeatureType] = useState<PlaceFeatureType>("feeder");
  const [featureName, setFeatureName] = useState("");
  const [featureSourceId, setFeatureSourceId] = useState("");
  const [featureZoneId, setFeatureZoneId] = useState("");
  const [featureInstalledDate, setFeatureInstalledDate] = useState("");
  const [isSavingFeature, setIsSavingFeature] = useState(false);
  const [busyFeatureId, setBusyFeatureId] = useState<string | null>(null);

  const [changeFeatureId, setChangeFeatureId] = useState("");
  const [changeEventType, setChangeEventType] = useState<PlaceFeatureChangeEventType>("modified");
  const [changeDate, setChangeDate] = useState("");
  const [changeNote, setChangeNote] = useState("");
  const [changeNewValue, setChangeNewValue] = useState("");
  const [isSavingChange, setIsSavingChange] = useState(false);

  // Multi-view observation-link editing: at most one Feature's own
  // "add another view" mini-form is open at a time (mirrors this codebase's
  // established one-thing-expanded-at-a-time convention, e.g. the Place
  // Report page's own single `expandedFeatureId`).
  const [addingViewForFeatureId, setAddingViewForFeatureId] = useState<string | null>(null);
  const [newViewSourceId, setNewViewSourceId] = useState("");
  const [newViewZoneId, setNewViewZoneId] = useState("");
  const [isSavingView, setIsSavingView] = useState(false);
  const [busyLinkId, setBusyLinkId] = useState<string | null>(null);

  if (summary === null && features === null) {
    return null;
  }

  const allFeatures = features ?? [];
  const activeFeatures = allFeatures.filter((feature) => feature.is_active);
  const hasAnything = allFeatures.length > 0;
  const allSources = sources ?? [];
  const allStreams = streams ?? [];
  const zonesForSource = (sourceId: string) =>
    !sourceId
      ? []
      : (zones ?? []).filter((zone) =>
          allStreams.some((stream) => stream.id === zone.stream_id && stream.source_id === sourceId),
        );
  const showsNewValueField = changeEventType === "food_changed" || changeEventType === "vegetation_changed";

  const addFeature = async () => {
    if (!featureName.trim()) {
      setError("Give this feature a name.");
      return;
    }
    setIsSavingFeature(true);
    setError(null);
    try {
      await onAddFeature({
        feature_type: featureType,
        name: featureName.trim(),
        source_id: featureSourceId || undefined,
        zone_id: featureZoneId || undefined,
        installed_date: featureInstalledDate || undefined,
      });
      setFeatureName("");
      setFeatureSourceId("");
      setFeatureZoneId("");
      setFeatureInstalledDate("");
    } catch {
      setError("Could not save that feature. Try again.");
    } finally {
      setIsSavingFeature(false);
    }
  };

  const toggleActive = async (feature: PlaceFeature) => {
    setBusyFeatureId(feature.id);
    setError(null);
    try {
      await onUpdateFeature(feature.id, { is_active: !feature.is_active });
    } catch {
      setError("Could not update that feature. Try again.");
    } finally {
      setBusyFeatureId(null);
    }
  };

  const removeFeature = async (feature: PlaceFeature) => {
    setBusyFeatureId(feature.id);
    setError(null);
    const blockedReason = await onRemoveFeature(feature.id);
    if (blockedReason) {
      setError(blockedReason);
    }
    setBusyFeatureId(null);
  };

  const startAddingView = (featureId: string) => {
    setAddingViewForFeatureId(featureId);
    setNewViewSourceId("");
    setNewViewZoneId("");
    setError(null);
  };

  const addView = async (featureId: string) => {
    if (!newViewSourceId && !newViewZoneId) {
      setError("Choose a camera or Zone to link.");
      return;
    }
    setIsSavingView(true);
    setError(null);
    const blockedReason = await onAddObservationLink(featureId, {
      source_id: newViewSourceId || undefined,
      zone_id: newViewZoneId || undefined,
    });
    setIsSavingView(false);
    if (blockedReason) {
      setError(blockedReason);
      return;
    }
    setAddingViewForFeatureId(null);
    setNewViewSourceId("");
    setNewViewZoneId("");
  };

  const removeView = async (featureId: string, linkId: string) => {
    setBusyLinkId(linkId);
    setError(null);
    const blockedReason = await onRemoveObservationLink(featureId, linkId);
    if (blockedReason) {
      setError(blockedReason);
    }
    setBusyLinkId(null);
  };

  const addChange = async () => {
    if (!changeDate) {
      setError("Choose a date for this change.");
      return;
    }
    setIsSavingChange(true);
    setError(null);
    try {
      await onAddChangeEvent({
        feature_id: changeFeatureId || null,
        event_type: changeEventType,
        effective_date: changeDate,
        note: changeNote || null,
        new_value: showsNewValueField && changeNewValue ? changeNewValue : null,
      });
      setChangeDate("");
      setChangeNote("");
      setChangeNewValue("");
    } catch {
      setError("Could not save that change. Try again.");
    } finally {
      setIsSavingChange(false);
    }
  };

  if (!isEditing) {
    if (!hasAnything) {
      return (
        <section aria-label="Place features" className="panel place-features-card">
          <p className="meta-text">No feeders, water features, or other Place features recorded yet.</p>
          <div className="today-report-footer">
            <button className="secondary-action" onClick={() => setIsEditing(true)} type="button">
              Add a feature
            </button>
          </div>
        </section>
      );
    }
    return (
      <section aria-label="Place features" className="panel place-features-card">
        {summary?.highlight ? <p className="meta-text">{summary.highlight}</p> : null}
        {activeFeatures.length > 0 ? (
          <div className="tag-row">
            {activeFeatures.map((feature) =>
              onOpenFeatureStory ? (
                <button
                  className="tag"
                  key={feature.id}
                  onClick={() => onOpenFeatureStory(feature.id)}
                  type="button"
                >
                  {feature.name}
                </button>
              ) : (
                <span className="tag" key={feature.id}>
                  {feature.name}
                </span>
              ),
            )}
          </div>
        ) : (
          <p className="meta-text">No active features right now.</p>
        )}
        <div className="today-report-footer">
          <button className="text-action" onClick={() => setIsEditing(true)} type="button">
            Manage features
          </button>
        </div>
      </section>
    );
  }

  return (
    <section aria-label="Manage Place features" className="panel place-features-card">
      <fieldset className="habitat-phenology-fields">
        <legend>Features</legend>
        <p className="meta-text">
          Feeders, water features, nest boxes, and other things around this Place worth tracking over
          time.
        </p>
        {hasAnything ? (
          <ul className="habitat-phenology-list">
            {allFeatures.map((feature) => (
              <li key={feature.id}>
                <strong>{feature.name}</strong> &middot; {FEATURE_TYPE_LABELS[feature.feature_type]}
                {!feature.is_active ? <StatusPill label="Inactive" tone="quiet" /> : null}
                <button
                  className="text-action"
                  disabled={busyFeatureId === feature.id}
                  onClick={() => void toggleActive(feature)}
                  type="button"
                >
                  {feature.is_active ? "Deactivate" : "Activate"}
                </button>
                <button
                  className="text-action"
                  disabled={busyFeatureId === feature.id}
                  onClick={() => void removeFeature(feature)}
                  type="button"
                >
                  Remove
                </button>
                <div className="place-feature-observed-by">
                  <span className="meta-text">Observed by:</span>
                  {feature.observation_links.length > 0 ? (
                    <div className="tag-row">
                      {feature.observation_links.map((link) => (
                        <span className="tag" key={link.id}>
                          {link.source_name}
                          {link.source_archived ? " (archived)" : ""}
                          {link.zone_name ? ` — ${link.zone_name}` : ""}
                          <button
                            aria-label={`Stop observing ${feature.name} from ${link.source_name}`}
                            className="tag-remove-button"
                            disabled={busyLinkId === link.id}
                            onClick={() => void removeView(feature.id, link.id)}
                            type="button"
                          >
                            &times;
                          </button>
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="meta-text">No camera linked — Place knowledge only.</span>
                  )}
                  {addingViewForFeatureId === feature.id ? (
                    <div className="detail-actions">
                      <label>
                        Camera to add
                        <select
                          onChange={(event) => {
                            setNewViewSourceId(event.target.value);
                            setNewViewZoneId("");
                          }}
                          value={newViewSourceId}
                        >
                          <option value="">Choose a camera</option>
                          {allSources.map((source) => (
                            <option key={source.id} value={source.id}>
                              {sourceOptionLabel(source)}
                            </option>
                          ))}
                        </select>
                      </label>
                      {newViewSourceId ? (
                        <label>
                          Zone to add
                          <select
                            onChange={(event) => setNewViewZoneId(event.target.value)}
                            value={newViewZoneId}
                          >
                            <option value="">Whole camera (no specific Zone)</option>
                            {zonesForSource(newViewSourceId).map((zone) => (
                              <option key={zone.id} value={zone.id}>
                                {zone.name}
                              </option>
                            ))}
                          </select>
                        </label>
                      ) : null}
                      <button
                        className="secondary-action"
                        disabled={isSavingView}
                        onClick={() => void addView(feature.id)}
                        type="button"
                      >
                        {isSavingView ? "Adding…" : "Add view"}
                      </button>
                      <button
                        className="text-action"
                        onClick={() => setAddingViewForFeatureId(null)}
                        type="button"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      className="text-action"
                      onClick={() => startAddingView(feature.id)}
                      type="button"
                    >
                      + Add another view
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="meta-text">Nothing recorded yet.</p>
        )}
        <div className="detail-actions">
          <label>
            Type
            <select
              onChange={(event) => setFeatureType(event.target.value as PlaceFeatureType)}
              value={featureType}
            >
              {(Object.keys(FEATURE_TYPE_LABELS) as PlaceFeatureType[]).map((type) => (
                <option key={type} value={type}>
                  {FEATURE_TYPE_LABELS[type]}
                </option>
              ))}
            </select>
          </label>
          <label>
            Name
            <input
              onChange={(event) => setFeatureName(event.target.value)}
              placeholder="e.g. Sunflower feeder"
              type="text"
              value={featureName}
            />
          </label>
          {allSources.length > 0 ? (
            <label>
              Camera (optional)
              <select
                onChange={(event) => {
                  setFeatureSourceId(event.target.value);
                  setFeatureZoneId("");
                }}
                value={featureSourceId}
              >
                <option value="">Not linked to a camera</option>
                {allSources.map((source) => (
                  <option key={source.id} value={source.id}>
                    {sourceOptionLabel(source)}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {featureSourceId ? (
            <label>
              Zone (optional)
              <select
                onChange={(event) => setFeatureZoneId(event.target.value)}
                value={featureZoneId}
              >
                <option value="">Whole camera (no specific Zone)</option>
                {zonesForSource(featureSourceId).map((zone) => (
                  <option key={zone.id} value={zone.id}>
                    {zone.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <label>
            Added (optional)
            <input
              onChange={(event) => setFeatureInstalledDate(event.target.value)}
              type="date"
              value={featureInstalledDate}
            />
          </label>
          <button
            className="secondary-action"
            disabled={isSavingFeature}
            onClick={() => void addFeature()}
            type="button"
          >
            {isSavingFeature ? "Adding…" : "Add"}
          </button>
        </div>
      </fieldset>

      <fieldset className="habitat-phenology-fields">
        <legend>Record a change</legend>
        <p className="meta-text">
          Added, moved, or changed something? Record it here so MockingBird can later compare
          activity before and after.
        </p>
        <div className="detail-actions">
          <label>
            Feature
            <select onChange={(event) => setChangeFeatureId(event.target.value)} value={changeFeatureId}>
              <option value="">General (not a specific feature)</option>
              {allFeatures.map((feature) => (
                <option key={feature.id} value={feature.id}>
                  {feature.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            What changed
            <select
              onChange={(event) => setChangeEventType(event.target.value as PlaceFeatureChangeEventType)}
              value={changeEventType}
            >
              {(Object.keys(CHANGE_EVENT_TYPE_LABELS) as PlaceFeatureChangeEventType[]).map((type) => (
                <option key={type} value={type}>
                  {CHANGE_EVENT_TYPE_LABELS[type]}
                </option>
              ))}
            </select>
          </label>
          <label>
            Date
            <input onChange={(event) => setChangeDate(event.target.value)} type="date" value={changeDate} />
          </label>
          {showsNewValueField ? (
            <label>
              New food/vegetation
              <input
                onChange={(event) => setChangeNewValue(event.target.value)}
                placeholder="e.g. Black-oil sunflower"
                type="text"
                value={changeNewValue}
              />
            </label>
          ) : null}
          <label>
            Note (optional)
            <input
              onChange={(event) => setChangeNote(event.target.value)}
              placeholder="Optional note"
              type="text"
              value={changeNote}
            />
          </label>
          <button
            className="secondary-action"
            disabled={isSavingChange}
            onClick={() => void addChange()}
            type="button"
          >
            {isSavingChange ? "Saving…" : "Record change"}
          </button>
        </div>
      </fieldset>

      {error ? (
        <div aria-live="polite" className="notice-panel">
          {error}
        </div>
      ) : null}
      <div className="detail-actions">
        <button className="primary-action" onClick={() => setIsEditing(false)} type="button">
          Done
        </button>
      </div>
    </section>
  );
}
