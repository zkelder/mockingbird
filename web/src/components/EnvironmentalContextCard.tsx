import { useState } from "react";
import type { PlaceEnvironmentalContext } from "../api/types";
import { formatTimeOfDay, formatWeatherLine } from "../utils";

interface EnvironmentalContextCardProps {
  context: PlaceEnvironmentalContext | null;
  onSaveLocation: (
    latitude: number | null,
    longitude: number | null,
    weatherEnabled: boolean,
  ) => Promise<void>;
}

/**
 * Environmental Context Foundation v1 (see docs/environmental-context-
 * foundation-v1-contract.md "Frontend surface"), extended by Environmental
 * Context v2 (see docs/environmental-context-v2-contract.md "Phase 16")
 * with an optional weather toggle and conditions line. The only place a
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
 * dashboard. Never phrases sunrise/sunset/daylight/weather as a cause of
 * anything ("the bird appeared because...") -- context only, matching
 * "External ecological context" in docs/product-doctrine.md. Weather is
 * resolved and rendered independently of solar's own availability -- see
 * `weatherCurrentlyEnabled`/`weatherLine`, below.
 */
export function EnvironmentalContextCard({ context, onSaveLocation }: EnvironmentalContextCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [latitudeInput, setLatitudeInput] = useState("");
  const [longitudeInput, setLongitudeInput] = useState("");
  const [weatherEnabledInput, setWeatherEnabledInput] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!context) {
    return null;
  }

  // Weather is resolved independently of solar availability (see
  // docs/environmental-context-v2-contract.md "Phase 16"), so its own
  // `status` reliably reflects the current `weather_enabled` setting even
  // on a date where solar itself is unavailable -- unlike `basis_latitude`/
  // `basis_longitude` below, which (a pre-existing v1 behavior, unchanged
  // here) are only populated when solar computation itself succeeded.
  const weatherCurrentlyEnabled =
    context.weather.status !== "disabled" && context.weather.status !== "not_configured";

  const startEditing = () => {
    setLatitudeInput(context.basis_latitude != null ? String(context.basis_latitude) : "");
    setLongitudeInput(context.basis_longitude != null ? String(context.basis_longitude) : "");
    setWeatherEnabledInput(weatherCurrentlyEnabled);
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
      await onSaveLocation(latitude, longitude, weatherEnabledInput);
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
      // Clearing location also turns weather off -- a location-less
      // installation has nothing to send a weather provider anyway, and
      // this avoids a stale "enabled" flag lingering with no coordinate.
      await onSaveLocation(null, null, false);
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
          <label className="environmental-context-weather-toggle">
            <input
              checked={weatherEnabledInput}
              onChange={(event) => setWeatherEnabledInput(event.target.checked)}
              type="checkbox"
            />
            Also fetch local weather conditions
          </label>
          <p className="meta-text">
            Sends the approximate location above to Open-Meteo.com to look up temperature,
            precipitation, and wind for this Place. Off by default; never shared or exported
            automatically.{" "}
            <a href="https://open-meteo.com/" rel="noreferrer noopener" target="_blank">
              Weather data by Open-Meteo.com
            </a>
            .
          </p>
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

  // Weather is resolved independently of solar (see docs/environmental-
  // context-v2-contract.md "Phase 16") -- it can be present here even when
  // solar itself is unavailable for this date, and absent (`null`) when
  // disabled/not configured/genuinely unavailable. Absence is silence,
  // never an error banner, matching every other optional fact on this card.
  const weatherLine = formatWeatherLine(context.weather);

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
          {weatherLine ? (
            <div className="today-report-fact">
              <span>Conditions</span>
              <strong>{weatherLine}</strong>
            </div>
          ) : null}
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
        {weatherLine ? (
          <div className="today-report-facts">
            <div className="today-report-fact">
              <span>Conditions</span>
              <strong>{weatherLine}</strong>
            </div>
          </div>
        ) : null}
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
