import { useId } from "react";
import type { TaxonomyLabel } from "../api/types";
import { formatLabel } from "../utils";
import { findTaxonomyLabel } from "./taxonomy";

interface TaxonomyLabelInputProps {
  labels: TaxonomyLabel[];
  value: string;
  onChange: (value: string) => void;
  label?: string;
  placeholder?: string;
  intent?: "truth" | "evidence";
}

const preferredLabels = [
  "unknown_bird",
  "unknown_animal",
  "northern_cardinal",
  "blue_jay",
  "squirrel",
  "false_positive",
];

export function TaxonomyLabelInput({
  labels,
  value,
  onChange,
  label = "Corrected label",
  placeholder = "confirmed species or event label",
  intent = "truth",
}: TaxonomyLabelInputProps) {
  const listId = useId();
  const matchedLabel = findTaxonomyLabel(value, labels);
  const quickLabels = preferredLabels
    .map((labelId) => labels.find((taxonomyLabel) => taxonomyLabel.label === labelId))
    .filter((taxonomyLabel): taxonomyLabel is TaxonomyLabel => Boolean(taxonomyLabel));

  return (
    <label>
      {label}
      <input
        list={listId}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
      />
      <datalist id={listId}>
        {labels.map((taxonomyLabel) => (
          <option key={taxonomyLabel.id} label={taxonomyLabel.label} value={taxonomyLabel.display_name} />
        ))}
      </datalist>
      <div className="taxonomy-quick-picks">
        {quickLabels.map((taxonomyLabel) => (
          <button
            aria-pressed={matchedLabel?.id === taxonomyLabel.id}
            className={matchedLabel?.id === taxonomyLabel.id ? "selected" : ""}
            key={taxonomyLabel.id}
            /* UI/UX & First-Run Adoption v1: a quick pick used to write the
               internal id ("northern_cardinal") into the field while the
               dropdown wrote the display name; `findTaxonomyLabel` resolves
               either, so both now show the readable name. */
            onClick={() => onChange(taxonomyLabel.display_name)}
            type="button"
          >
            {taxonomyLabel.display_name}
          </button>
        ))}
      </div>
      <span className="field-helper">
        {matchedLabel
          ? `${matchedLabel.display_name} ${
              intent === "truth" ? "will save" : "matches taxonomy"
            } as ${matchedLabel.label} (${formatLabel(matchedLabel.category)}${
              matchedLabel.is_species ? " species" : ""
            }).`
          : "Custom local labels are allowed when taxonomy does not have the right match yet."}
      </span>
    </label>
  );
}
