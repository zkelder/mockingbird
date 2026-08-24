import { useState } from "react";
import type {
  HabitatFactCategory,
  PlaceHabitatContext,
  PlaceHabitatFactCreate,
  PlaceHabitatFactUpdate,
  PlacePhenologyObservation,
  PlacePhenologyObservationCreate,
  PlacePhenologyObservationUpdate,
} from "../api/types";
import { StatusPill } from "./StatusPill";
import { phenologyDateRange } from "../utils";

interface HabitatPhenologyCardProps {
  context: PlaceHabitatContext | null;
  onAddHabitatFact: (payload: PlaceHabitatFactCreate) => Promise<void>;
  onUpdateHabitatFact: (factId: string, payload: PlaceHabitatFactUpdate) => Promise<void>;
  onRemoveHabitatFact: (factId: string) => Promise<void>;
  onAddPhenologyObservation: (payload: PlacePhenologyObservationCreate) => Promise<void>;
  onUpdatePhenologyObservation: (
    observationId: string,
    payload: PlacePhenologyObservationUpdate,
  ) => Promise<void>;
  onRemovePhenologyObservation: (observationId: string) => Promise<void>;
}

const HABITAT_CATEGORY_LABELS: Record<HabitatFactCategory, string> = {
  setting: "Setting",
  vegetation: "Vegetation",
  feature: "Features",
};

// Guidance, not a mandate -- matches the governing brief's own "examples of
// useful concepts... not a mandate to hard-code exactly this list." A user
// can always type something the list did not anticipate.
const HABITAT_SUGGESTIONS: Record<HabitatFactCategory, string[]> = {
  setting: ["Suburban yard", "Woodland edge", "Urban courtyard", "Rural/open land"],
  vegetation: [
    "Mature deciduous trees",
    "Conifers",
    "Shrubs/thicket",
    "Lawn/open ground",
    "Native planting",
    "Fruiting plants",
  ],
  feature: ["Water feature", "Bird feeders", "Nest boxes"],
};

const PHENOMENON_SUGGESTIONS = [
  "Flowering",
  "Fruiting/seed availability",
  "Leaf-out",
  "Leaf fall",
  "Emergence",
  "Nesting-resource availability",
  "Feeder/resource availability",
];

interface ObservationDraft {
  subjectLabel: string;
  phenomenon: string;
  startDate: string;
  endDate: string;
  note: string;
}

function draftFromObservation(observation: PlacePhenologyObservation): ObservationDraft {
  return {
    subjectLabel: observation.subject_label,
    phenomenon: observation.phenomenon,
    startDate: observation.observed_start_date,
    endDate: observation.observed_end_date ?? "",
    note: observation.note ?? "",
  };
}

/**
 * Habitat & Phenology Foundation v1 (see docs/habitat-phenology-
 * foundation-v1-contract.md "Frontend surface"). A sibling of
 * `EnvironmentalContextCard`, not nested inside it or `TodayReportPanel` --
 * a genuinely separate fetch/domain that must keep working (or stay
 * quietly absent) regardless of whether either of those loaded. This is
 * both the "quiet contextual" surface (calm view mode) and the "settings
 * editing" surface (there is no dedicated Place/settings page -- Environmental
 * Context already established the precedent of editing living inline here).
 *
 * Renders nothing while the fetch is still in flight or failed
 * (`context === null`), matching `EnvironmentalContextCard`'s identical
 * discipline. Never phrases a habitat/phenology fact as a cause of wildlife
 * activity -- context only, matching "External ecological context" in
 * docs/product-doctrine.md. Only ever shows what is recorded; absence is
 * always "nothing recorded yet," never "this Place lacks X."
 */
export function HabitatPhenologyCard({
  context,
  onAddHabitatFact,
  onUpdateHabitatFact,
  onRemoveHabitatFact,
  onAddPhenologyObservation,
  onUpdatePhenologyObservation,
  onRemovePhenologyObservation,
}: HabitatPhenologyCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [factCategory, setFactCategory] = useState<HabitatFactCategory>("setting");
  const [factLabel, setFactLabel] = useState("");
  const [isSavingFact, setIsSavingFact] = useState(false);
  const [removingFactId, setRemovingFactId] = useState<string | null>(null);
  const [editingFactId, setEditingFactId] = useState<string | null>(null);
  const [factNoteDraft, setFactNoteDraft] = useState("");
  const [isSavingFactNote, setIsSavingFactNote] = useState(false);

  const [subjectLabel, setSubjectLabel] = useState("");
  const [phenomenon, setPhenomenon] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [isSavingObservation, setIsSavingObservation] = useState(false);
  const [removingObservationId, setRemovingObservationId] = useState<string | null>(null);
  const [editingObservationId, setEditingObservationId] = useState<string | null>(null);
  const [observationDraft, setObservationDraft] = useState<ObservationDraft | null>(null);
  const [isSavingObservationEdit, setIsSavingObservationEdit] = useState(false);

  if (!context) {
    return null;
  }

  const hasHabitatFacts = context.habitat_facts.length > 0;
  const phenologyEntries = [
    ...context.current_phenology.map((observation) => ({ observation, isCurrent: true })),
    ...context.recent_phenology.map((observation) => ({ observation, isCurrent: false })),
  ];
  const hasAnything = hasHabitatFacts || phenologyEntries.length > 0;

  const addFact = async () => {
    if (!factLabel.trim()) {
      setError("Enter a label for this habitat detail.");
      return;
    }
    setIsSavingFact(true);
    setError(null);
    try {
      await onAddHabitatFact({ category: factCategory, label: factLabel.trim() });
      setFactLabel("");
    } catch {
      setError("Could not save that habitat detail. Try again.");
    } finally {
      setIsSavingFact(false);
    }
  };

  const removeFact = async (factId: string) => {
    setRemovingFactId(factId);
    setError(null);
    try {
      await onRemoveHabitatFact(factId);
    } catch {
      setError("Could not remove that habitat detail. Try again.");
    } finally {
      setRemovingFactId(null);
    }
  };

  const startEditingFactNote = (factId: string, currentNote: string | null | undefined) => {
    setEditingFactId(factId);
    setFactNoteDraft(currentNote ?? "");
    setError(null);
  };

  const saveFactNote = async (factId: string) => {
    setIsSavingFactNote(true);
    setError(null);
    try {
      // "" explicitly clears the note; see PlaceHabitatFactUpdate's own
      // docstring for this convention.
      await onUpdateHabitatFact(factId, { note: factNoteDraft });
      setEditingFactId(null);
    } catch {
      setError("Could not save that note. Try again.");
    } finally {
      setIsSavingFactNote(false);
    }
  };

  const addObservation = async () => {
    if (!subjectLabel.trim() || !phenomenon.trim() || !startDate) {
      setError("Enter a subject, what's happening, and a date.");
      return;
    }
    if (endDate && endDate < startDate) {
      setError("The end date can't be before the start date.");
      return;
    }
    setIsSavingObservation(true);
    setError(null);
    try {
      await onAddPhenologyObservation({
        subject_label: subjectLabel.trim(),
        phenomenon: phenomenon.trim(),
        observed_start_date: startDate,
        observed_end_date: endDate || null,
      });
      setSubjectLabel("");
      setPhenomenon("");
      setStartDate("");
      setEndDate("");
    } catch {
      setError("Could not save that observation. Try again.");
    } finally {
      setIsSavingObservation(false);
    }
  };

  const removeObservation = async (observationId: string) => {
    setRemovingObservationId(observationId);
    setError(null);
    try {
      await onRemovePhenologyObservation(observationId);
    } catch {
      setError("Could not remove that observation. Try again.");
    } finally {
      setRemovingObservationId(null);
    }
  };

  const startEditingObservation = (observation: PlacePhenologyObservation) => {
    setEditingObservationId(observation.id);
    setObservationDraft(draftFromObservation(observation));
    setError(null);
  };

  const saveObservationEdit = async (observation: PlacePhenologyObservation) => {
    if (!observationDraft) return;
    if (!observationDraft.subjectLabel.trim() || !observationDraft.phenomenon.trim() || !observationDraft.startDate) {
      setError("Enter a subject, what's happening, and a date.");
      return;
    }
    if (observationDraft.endDate && observationDraft.endDate < observationDraft.startDate) {
      setError("The end date can't be before the start date.");
      return;
    }
    setIsSavingObservationEdit(true);
    setError(null);
    try {
      const hadEndDate = Boolean(observation.observed_end_date);
      const clearingEndDate = hadEndDate && !observationDraft.endDate;
      await onUpdatePhenologyObservation(observation.id, {
        subject_label: observationDraft.subjectLabel.trim(),
        phenomenon: observationDraft.phenomenon.trim(),
        observed_start_date: observationDraft.startDate,
        // observed_end_date and clear_observed_end_date are mutually
        // exclusive on the wire (see PlacePhenologyObservationUpdate's own
        // docstring) -- send at most one.
        ...(clearingEndDate
          ? { clear_observed_end_date: true }
          : observationDraft.endDate
            ? { observed_end_date: observationDraft.endDate }
            : {}),
        // "" explicitly clears the note; leaving it unset would keep the
        // existing note unchanged, which is never what an edit form means.
        note: observationDraft.note,
      });
      setEditingObservationId(null);
      setObservationDraft(null);
    } catch {
      setError("Could not save that observation. Try again.");
    } finally {
      setIsSavingObservationEdit(false);
    }
  };

  if (!isEditing) {
    if (!hasAnything) {
      return (
        <section aria-label="Habitat and season" className="panel habitat-phenology-card">
          <p className="meta-text">No habitat or season details recorded yet.</p>
          <div className="today-report-footer">
            <button className="secondary-action" onClick={() => setIsEditing(true)} type="button">
              Add habitat &amp; season details
            </button>
          </div>
        </section>
      );
    }
    return (
      <section aria-label="Habitat and season" className="panel habitat-phenology-card">
        {hasHabitatFacts ? (
          <div className="tag-row">
            {context.habitat_facts.map((fact) => (
              <span className="tag" key={fact.id}>
                {fact.label}
              </span>
            ))}
          </div>
        ) : null}
        {phenologyEntries.length > 0 ? (
          <ul className="habitat-phenology-list">
            {phenologyEntries.map(({ observation, isCurrent }) => (
              <li key={observation.id}>
                <strong>{observation.subject_label}</strong> &middot; {observation.phenomenon}
                {!isCurrent ? <StatusPill label="Recently" tone="quiet" /> : null}
                <span className="meta-text">
                  {phenologyDateRange(observation.observed_start_date, observation.observed_end_date)}
                </span>
              </li>
            ))}
          </ul>
        ) : null}
        <div className="today-report-footer">
          <button className="text-action" onClick={() => setIsEditing(true)} type="button">
            Edit
          </button>
        </div>
      </section>
    );
  }

  return (
    <section aria-label="Edit habitat and season details" className="panel habitat-phenology-card">
      <fieldset className="habitat-phenology-fields">
        <legend>Habitat details</legend>
        <p className="meta-text">
          Durable details about this Place -- setting, plants, and features. Nothing recorded here
          affects wildlife identification or history.
        </p>
        {hasHabitatFacts ? (
          <div className="tag-row">
            {context.habitat_facts.map((fact) => (
              <span className="tag" key={fact.id}>
                <button
                  aria-label={`Edit note for ${fact.label}`}
                  className="tag-edit-button"
                  onClick={() => startEditingFactNote(fact.id, fact.note)}
                  title={fact.note ?? "Add a note"}
                  type="button"
                >
                  {fact.label}
                </button>
                <button
                  aria-label={`Remove ${fact.label}`}
                  className="tag-remove-button"
                  disabled={removingFactId === fact.id}
                  onClick={() => void removeFact(fact.id)}
                  type="button"
                >
                  &times;
                </button>
              </span>
            ))}
          </div>
        ) : (
          <p className="meta-text">Nothing recorded yet.</p>
        )}
        {editingFactId ? (
          <div className="detail-actions">
            <label>
              Note
              <input
                onChange={(event) => setFactNoteDraft(event.target.value)}
                placeholder="Optional note"
                type="text"
                value={factNoteDraft}
              />
            </label>
            <button className="text-action" onClick={() => setEditingFactId(null)} type="button">
              Cancel
            </button>
            <button
              className="secondary-action"
              disabled={isSavingFactNote}
              onClick={() => void saveFactNote(editingFactId)}
              type="button"
            >
              {isSavingFactNote ? "Saving…" : "Save note"}
            </button>
          </div>
        ) : null}
        <div className="detail-actions">
          <label>
            Category
            <select
              onChange={(event) => setFactCategory(event.target.value as HabitatFactCategory)}
              value={factCategory}
            >
              {(Object.keys(HABITAT_CATEGORY_LABELS) as HabitatFactCategory[]).map((category) => (
                <option key={category} value={category}>
                  {HABITAT_CATEGORY_LABELS[category]}
                </option>
              ))}
            </select>
          </label>
          <label>
            Label
            <input
              list="habitat-fact-suggestions"
              onChange={(event) => setFactLabel(event.target.value)}
              placeholder="e.g. Woodland edge"
              type="text"
              value={factLabel}
            />
            <datalist id="habitat-fact-suggestions">
              {HABITAT_SUGGESTIONS[factCategory].map((suggestion) => (
                <option key={suggestion} value={suggestion} />
              ))}
            </datalist>
          </label>
          <button className="secondary-action" disabled={isSavingFact} onClick={() => void addFact()} type="button">
            {isSavingFact ? "Adding…" : "Add"}
          </button>
        </div>
      </fieldset>

      <fieldset className="habitat-phenology-fields">
        <legend>Season / phenology</legend>
        <p className="meta-text">
          Dated observations, like flowering, fruiting, or feeder availability. A note from the
          past stays historical -- it will not be shown as happening now.
        </p>
        {phenologyEntries.length > 0 ? (
          <ul className="habitat-phenology-list">
            {phenologyEntries.map(({ observation, isCurrent }) =>
              editingObservationId === observation.id && observationDraft ? (
                <li key={observation.id}>
                  <div className="detail-actions">
                    <label>
                      Subject
                      <input
                        onChange={(event) =>
                          setObservationDraft({ ...observationDraft, subjectLabel: event.target.value })
                        }
                        type="text"
                        value={observationDraft.subjectLabel}
                      />
                    </label>
                    <label>
                      What&apos;s happening
                      <input
                        list="phenology-phenomenon-suggestions"
                        onChange={(event) =>
                          setObservationDraft({ ...observationDraft, phenomenon: event.target.value })
                        }
                        type="text"
                        value={observationDraft.phenomenon}
                      />
                    </label>
                    <label>
                      Since
                      <input
                        max={observationDraft.endDate || undefined}
                        onChange={(event) =>
                          setObservationDraft({ ...observationDraft, startDate: event.target.value })
                        }
                        type="date"
                        value={observationDraft.startDate}
                      />
                    </label>
                    <label>
                      Until (optional)
                      <input
                        min={observationDraft.startDate || undefined}
                        onChange={(event) =>
                          setObservationDraft({ ...observationDraft, endDate: event.target.value })
                        }
                        type="date"
                        value={observationDraft.endDate}
                      />
                    </label>
                    <label>
                      Note
                      <input
                        onChange={(event) =>
                          setObservationDraft({ ...observationDraft, note: event.target.value })
                        }
                        placeholder="Optional note"
                        type="text"
                        value={observationDraft.note}
                      />
                    </label>
                    <button
                      className="text-action"
                      onClick={() => {
                        setEditingObservationId(null);
                        setObservationDraft(null);
                      }}
                      type="button"
                    >
                      Cancel
                    </button>
                    <button
                      className="secondary-action"
                      disabled={isSavingObservationEdit}
                      onClick={() => void saveObservationEdit(observation)}
                      type="button"
                    >
                      {isSavingObservationEdit ? "Saving…" : "Save"}
                    </button>
                  </div>
                </li>
              ) : (
                <li key={observation.id}>
                  <strong>{observation.subject_label}</strong> &middot; {observation.phenomenon}
                  {!isCurrent ? <StatusPill label="Recently" tone="quiet" /> : null}
                  <span className="meta-text">
                    {phenologyDateRange(observation.observed_start_date, observation.observed_end_date)}
                  </span>
                  <button
                    className="text-action"
                    onClick={() => startEditingObservation(observation)}
                    type="button"
                  >
                    Edit
                  </button>
                  <button
                    className="text-action"
                    disabled={removingObservationId === observation.id}
                    onClick={() => void removeObservation(observation.id)}
                    type="button"
                  >
                    Remove
                  </button>
                </li>
              ),
            )}
          </ul>
        ) : (
          <p className="meta-text">Nothing recorded yet.</p>
        )}
        <div className="detail-actions">
          <label>
            Subject
            <input
              onChange={(event) => setSubjectLabel(event.target.value)}
              placeholder="e.g. Azalea"
              type="text"
              value={subjectLabel}
            />
          </label>
          <label>
            What&apos;s happening
            <input
              list="phenology-phenomenon-suggestions"
              onChange={(event) => setPhenomenon(event.target.value)}
              placeholder="e.g. Flowering"
              type="text"
              value={phenomenon}
            />
            <datalist id="phenology-phenomenon-suggestions">
              {PHENOMENON_SUGGESTIONS.map((suggestion) => (
                <option key={suggestion} value={suggestion} />
              ))}
            </datalist>
          </label>
          <label>
            Since
            <input
              max={endDate || undefined}
              onChange={(event) => setStartDate(event.target.value)}
              type="date"
              value={startDate}
            />
          </label>
          <label>
            Until (optional)
            <input
              min={startDate || undefined}
              onChange={(event) => setEndDate(event.target.value)}
              type="date"
              value={endDate}
            />
          </label>
          <button
            className="secondary-action"
            disabled={isSavingObservation}
            onClick={() => void addObservation()}
            type="button"
          >
            {isSavingObservation ? "Adding…" : "Add"}
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
