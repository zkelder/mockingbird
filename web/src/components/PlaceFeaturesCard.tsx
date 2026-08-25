import { useState } from "react";
import type {
  PlaceFeature,
  PlaceFeatureChangeEventCreate,
  PlaceFeatureChangeEventType,
  PlaceFeatureCreate,
  PlaceFeatureType,
  PlaceFeatureUpdate,
  PlaceFeaturesSummary,
  Zone,
} from "../api/types";
import { StatusPill } from "./StatusPill";

interface PlaceFeaturesCardProps {
  summary: PlaceFeaturesSummary | null;
  features: PlaceFeature[] | null;
  zones: Zone[] | null;
  onAddFeature: (payload: PlaceFeatureCreate) => Promise<void>;
  onUpdateFeature: (featureId: string, payload: PlaceFeatureUpdate) => Promise<void>;
  onRemoveFeature: (featureId: string) => Promise<string | null>;
  onAddChangeEvent: (payload: PlaceFeatureChangeEventCreate) => Promise<void>;
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

/**
 * Place Features & Habitat Change v2 (see docs/place-features-habitat-
 * change-v2-contract.md "Product surfaces"). A sibling of
 * `HabitatPhenologyCard`, same calm-view/inline-edit-toggle shape: a
 * restrained summary line plus active-feature tags when not editing, a
 * fuller CRUD surface (add/edit/deactivate/remove a Feature; record a
 * change) when editing. `onRemoveFeature` returns a user-safe error
 * message (never a raw exception) so a blocked hard-delete -- a Feature
 * with recorded history -- can explain "deactivate it instead" rather than
 * failing silently or throwing.
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
  onAddFeature,
  onUpdateFeature,
  onRemoveFeature,
  onAddChangeEvent,
}: PlaceFeaturesCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [featureType, setFeatureType] = useState<PlaceFeatureType>("feeder");
  const [featureName, setFeatureName] = useState("");
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

  if (summary === null && features === null) {
    return null;
  }

  const allFeatures = features ?? [];
  const activeFeatures = allFeatures.filter((feature) => feature.is_active);
  const hasAnything = allFeatures.length > 0;
  const zoneName = (zoneId: string | null | undefined) =>
    zoneId ? zones?.find((zone) => zone.id === zoneId)?.name ?? null : null;
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
        zone_id: featureZoneId || undefined,
        installed_date: featureInstalledDate || undefined,
      });
      setFeatureName("");
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
            {activeFeatures.map((feature) => (
              <span className="tag" key={feature.id}>
                {feature.name}
              </span>
            ))}
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
                {zoneName(feature.zone_id) ? (
                  <span className="meta-text">{zoneName(feature.zone_id)}</span>
                ) : null}
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
          {zones && zones.length > 0 ? (
            <label>
              Camera (optional)
              <select
                onChange={(event) => setFeatureZoneId(event.target.value)}
                value={featureZoneId}
              >
                <option value="">Not linked to a camera</option>
                {zones.map((zone) => (
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
