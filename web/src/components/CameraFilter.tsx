import { useId } from "react";
import {
  ALL_CAMERAS_LABEL,
  UNAVAILABLE_CAMERA_LABEL,
  cameraScopeSummary,
  toggleCameraId,
  unavailableCameraIds,
  type CameraFilterOption,
} from "../cameraFilter";

/**
 * The one camera-filter control (Multi-Camera Attribution & Filter
 * Consolidation v1). `multiple` renders a checkbox group (empty = every
 * camera); otherwise a single select whose first option is "All cameras".
 * Both report `string[]` so a page can move between single and multi without
 * changing its state shape. A selected id the options no longer resolve stays
 * visible as "Unavailable camera" rather than silently widening the scope.
 */
interface CameraFilterProps {
  options: readonly CameraFilterOption[];
  value: readonly string[];
  onChange: (ids: string[]) => void;
  multiple?: boolean;
  label?: string;
  disabled?: boolean;
}

export function CameraFilter({
  options,
  value,
  onChange,
  multiple = false,
  label = multiple ? "Cameras" : "Camera",
  disabled = false,
}: CameraFilterProps) {
  const groupId = useId();
  const missing = unavailableCameraIds(value, options);

  if (multiple) {
    return (
      <fieldset className="camera-filter" aria-labelledby={`${groupId}-legend`} disabled={disabled}>
        <legend id={`${groupId}-legend`}>{label}</legend>
        <div className="camera-filter-options retention-checkbox-grid">
          {[...options, ...missing.map((id) => ({ id, label: UNAVAILABLE_CAMERA_LABEL }))].map((option) => (
            <label className="checkbox-row" key={option.id}>
              <input
                checked={value.includes(option.id)}
                onChange={() => onChange(toggleCameraId(value, option.id))}
                type="checkbox"
              />
              {option.label}
            </label>
          ))}
        </div>
        <span className="meta-text">{cameraScopeSummary(value.length, options.length)}</span>
      </fieldset>
    );
  }

  return (
    <label className="camera-filter">
      {label}
      <select
        disabled={disabled}
        onChange={(event) => onChange(event.target.value ? [event.target.value] : [])}
        value={value[0] ?? ""}
      >
        <option value="">{ALL_CAMERAS_LABEL}</option>
        {missing.map((id) => (
          <option key={id} value={id}>
            {UNAVAILABLE_CAMERA_LABEL}
          </option>
        ))}
        {options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
