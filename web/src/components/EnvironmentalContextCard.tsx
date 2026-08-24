import { useState } from "react";
import type { PlaceEnvironmentalContext } from "../api/types";
import { formatTimeOfDay } from "../utils";

interface EnvironmentalContextCardProps {
  context: PlaceEnvironmentalContext | null;
  onSaveLocation: (latitude: number | null, longitude: number | null) => Promise<void>;
}

/**
 * Environmental Context Foundation v1 (see docs/environmental-context-
 * foundation-v1-contract.md "Frontend surface"). The only place a
 * coordinate is ever entered -- no new page, no new nav entry. A sibling
 * of `TodayReportPanel`, not nested inside it: that component's own
 * early-return states (loading/unavailable report) are about Place
 * Activity Report truth specifically, and this is a genuinely independent
 * fetch that must keep working (or stay quietly absent) regardless of
 * whether the report itself loaded.
 *
 * Renders nothing while the fetch is still in flight or failed
 * (`context === null`) rather than a loading/error state of its own --
 * this is a small, optional annotation, never a blocking part of the
 * dashboard. Never phrases sunrise/sunset/daylight as a cause of anything
 * ("the bird appeared because...") -- context only, matching "External
 * ecological context" in docs/product-doctrine.md.
 */
export function EnvironmentalContextCard({ context, onSaveLocation }: EnvironmentalContextCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [latitudeInput, setLatitudeInput] = useState("");
  const [longitudeInput, setLongitudeInput] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!context) {
    return null;
  }

  const startEditing = () => {
    setLatitudeInput(context.basis_latitude != null ? String(context.basis_latitude) : "");
    setLongitudeInput(context.basis_longitude != null ? String(context.basis_longitude) : "");
    setError(null);
    setIsEditing(true);
  };

  const save = async () => {
    const latitude = Number.parseFloat(latitudeInput);
    const longitude = Number.parseFloat(longitudeInput);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
      setError("Enter both a latitude and a longitude, or Clear location to remove it.");
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      await onSaveLocation(latitude, longitude);
      setIsEditing(false);
    } catch {
      setError("Could not save your location. Try again.");
    } finally {
      setIsSaving(false);
    }
  };

  const clearLocation = async () => {
    setIsSaving(true);
    setError(null);
    try {
      await onSaveLocation(null, null);
      setIsEditing(false);
    } catch {
      setError("Could not update your location. Try again.");
    } finally {
      setIsSaving(false);
    }
  };

  if (isEditing) {
    return (
      <section aria-label="Environmental context location" className="panel environmental-context-card">
        <fieldset className="environmental-context-location-fields">
          <legend>Approximate location (optional)</legend>
          <p className="meta-text">
            Used only to compute local sunrise/sunset on this device. Rounded to about 11&nbsp;km
            (never a precise address). Never shared, exported, or sent anywhere.
          </p>
          <label>
            Latitude
            <input
              aria-label="Latitude"
              inputMode="decimal"
              max={90}
              min={-90}
              onChange={(event) => setLatitudeInput(event.target.value)}
              placeholder="e.g. 40.7"
              step="0.1"
              type="number"
              value={latitudeInput}
            />
          </label>
          <label>
            Longitude
            <input
              aria-label="Longitude"
              inputMode="decimal"
              max={180}
              min={-180}
              onChange={(event) => setLongitudeInput(event.target.value)}
              placeholder="e.g. -74.0"
              step="0.1"
              type="number"
              value={longitudeInput}
            />
          </label>
        </fieldset>
        {error ? (
          <div aria-live="polite" className="notice-panel">
            {error}
          </div>
        ) : null}
        <div className="detail-actions">
          <button className="text-action" disabled={isSaving} onClick={() => setIsEditing(false)} type="button">
            Cancel
          </button>
          {context.available || context.reason === "unavailable_for_date" ? (
            <button className="text-action" disabled={isSaving} onClick={() => void clearLocation()} type="button">
              Clear location
            </button>
          ) : null}
          <button className="primary-action" disabled={isSaving} onClick={() => void save()} type="button">
            {isSaving ? "Saving…" : "Save location"}
          </button>
        </div>
      </section>
    );
  }

  if (context.available && context.sunrise_at && context.sunset_at) {
    return (
      <section aria-label="Today's daylight context" className="panel environmental-context-card">
        <div className="today-report-facts">
          <div className="today-report-fact">
            <span>Sunrise</span>
            <strong>{formatTimeOfDay(context.sunrise_at)}</strong>
          </div>
          <div className="today-report-fact">
            <span>Sunset</span>
            <strong>{formatTimeOfDay(context.sunset_at)}</strong>
          </div>
          <div className="today-report-fact">
            <span>Right now</span>
            <strong>{context.daylight_state === "day" ? "Daylight" : "Night"}</strong>
          </div>
        </div>
        <div className="today-report-footer">
          <button className="text-action" onClick={startEditing} type="button">
            Edit location
          </button>
        </div>
      </section>
    );
  }

  if (context.reason === "unavailable_for_date") {
    return (
      <section aria-label="Today's daylight context" className="panel environmental-context-card">
        <p className="meta-text">No sunrise or sunset today at your configured location.</p>
        <div className="today-report-footer">
          <button className="text-action" onClick={startEditing} type="button">
            Edit location
          </button>
        </div>
      </section>
    );
  }

  return (
    <section aria-label="Today's daylight context" className="panel environmental-context-card">
      <p className="meta-text">
        Add your approximate location to see local sunrise/sunset context alongside today's activity.
      </p>
      <div className="today-report-footer">
        <button className="secondary-action" onClick={startEditing} type="button">
          Set approximate location
        </button>
      </div>
    </section>
  );
}
