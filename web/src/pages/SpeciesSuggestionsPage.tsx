import { useEffect, useMemo, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type {
  MediaAsset,
  SpeciesCandidatePack,
  SpeciesSuggestion,
  SpeciesSuggestionCreateRequest,
  SpeciesSuggestionStatus,
  TaxonomyLabel,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { EvidenceBadge } from "../components/EvidenceBadge";
import { MediaAssetPreview } from "../components/MediaAssetPreview";
import { PageHeader } from "../components/PageHeader";
import { speciesSuggestionMetricLabel } from "../components/speciesSuggestion";
import { formatDateTime, formatLabel } from "../utils";

type SpeciesSuggestionFilter = "all" | SpeciesSuggestionStatus;

interface SpeciesSuggestionFilters {
  status: SpeciesSuggestionFilter;
  suggested_label?: string;
  visit_id?: string;
  event_id?: string;
  media_asset_id?: string;
}

const statusOptions: Array<{ value: SpeciesSuggestionFilter; label: string }> = [
  { value: "all", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "accepted", label: "Accepted" },
  { value: "rejected", label: "Rejected" },
  { value: "superseded", label: "Superseded" },
];

const statusActions: Array<{ status: Exclude<SpeciesSuggestionStatus, "pending">; label: string }> =
  [
    { status: "accepted", label: "Accept evidence" },
    { status: "rejected", label: "Reject evidence" },
    { status: "superseded", label: "Supersede evidence" },
  ];

interface SpeciesSuggestionsPageProps {
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenReview: () => void;
  onUseAsCorrection: (suggestion: SpeciesSuggestion) => void;
}

export function SpeciesSuggestionsPage({
  onOpenEvent,
  onOpenVisit,
  onOpenReview,
  onUseAsCorrection,
}: SpeciesSuggestionsPageProps) {
  const [suggestions, setSuggestions] = useState<SpeciesSuggestion[]>([]);
  const [mediaAssets, setMediaAssets] = useState<MediaAsset[]>([]);
  const [selectedSuggestionId, setSelectedSuggestionId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<SpeciesSuggestionFilter>("pending");
  const [suggestedLabelFilter, setSuggestedLabelFilter] = useState("");
  const [visitIdFilter, setVisitIdFilter] = useState("");
  const [eventIdFilter, setEventIdFilter] = useState("");
  const [mediaAssetIdFilter, setMediaAssetIdFilter] = useState("");
  const [adapterId, setAdapterId] = useState("manual_species_suggestion");
  const [adapterName, setAdapterName] = useState("Manual species suggestion");
  const [suggestedLabel, setSuggestedLabel] = useState("");
  const [suggestedCommonName, setSuggestedCommonName] = useState("");
  const [suggestedScientificName, setSuggestedScientificName] = useState("");
  const [confidence, setConfidence] = useState("");
  const [rank, setRank] = useState("1");
  const [visitId, setVisitId] = useState("");
  const [eventId, setEventId] = useState("");
  const [mediaAssetId, setMediaAssetId] = useState("");
  const [motionEvidenceId, setMotionEvidenceId] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [streamId, setStreamId] = useState("");
  const [alternativesJson, setAlternativesJson] = useState("[]");
  const [evidenceRegionJson, setEvidenceRegionJson] = useState("");
  const [notes, setNotes] = useState(
    "Manual suggestion for local review workflow testing.",
  );
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [candidatePacks, setCandidatePacks] = useState<SpeciesCandidatePack[]>([]);
  const [candidatePackSearch, setCandidatePackSearch] = useState("");
  const [candidateTaxonomyMatches, setCandidateTaxonomyMatches] = useState<TaxonomyLabel[]>([]);
  const [candidatePackName, setCandidatePackName] = useState("");
  const [candidatePackDescription, setCandidatePackDescription] = useState("");
  const [candidatePackMemberIds, setCandidatePackMemberIds] = useState<string[]>([]);
  const [editingCandidatePackId, setEditingCandidatePackId] = useState<string | null>(null);
  const [isSavingCandidatePack, setIsSavingCandidatePack] = useState(false);

  const mediaById = useMemo(
    () => new Map(mediaAssets.map((asset) => [asset.id, asset])),
    [mediaAssets],
  );
  const selectedSuggestion =
    suggestions.find((suggestion) => suggestion.id === selectedSuggestionId) ??
    suggestions[0] ??
    null;
  const selectedMediaAsset = selectedSuggestion?.media_asset_id
    ? mediaById.get(selectedSuggestion.media_asset_id) ?? null
    : null;
  const formMediaAsset = mediaAssetId ? mediaById.get(mediaAssetId) ?? null : null;
  const hasFilters =
    statusFilter !== "all" ||
    suggestedLabelFilter.trim().length > 0 ||
    visitIdFilter.trim().length > 0 ||
    eventIdFilter.trim().length > 0 ||
    mediaAssetIdFilter.trim().length > 0;
  const editingCandidatePack =
    candidatePacks.find((pack) => pack.id === editingCandidatePackId) ?? null;
  const candidatePackMemberLabels = candidatePackMemberIds.map((memberId) => {
    const member =
      editingCandidatePack?.members.find((label) => label.id === memberId) ??
      candidateTaxonomyMatches.find((label) => label.id === memberId);
    return { id: memberId, label: member?.display_name ?? memberId };
  });

  function currentFilters(): SpeciesSuggestionFilters {
    return {
      status: statusFilter,
      suggested_label: suggestedLabelFilter.trim() || undefined,
      visit_id: visitIdFilter.trim() || undefined,
      event_id: eventIdFilter.trim() || undefined,
      media_asset_id: mediaAssetIdFilter.trim() || undefined,
    };
  }

  async function loadSuggestions(
    options: {
      showLoading?: boolean;
      selectSuggestionId?: string;
      filters?: SpeciesSuggestionFilters;
    } = {},
  ) {
    const showLoading = options.showLoading ?? true;
    const filters = options.filters ?? currentFilters();
    if (showLoading) {
      setIsLoading(true);
    }
    setError(null);
    try {
      const [response, nextMediaAssets] = await Promise.all([
        apiClient.listSpeciesSuggestions({
          status: filters.status,
          suggested_label: filters.suggested_label,
          visit_id: filters.visit_id,
          event_id: filters.event_id,
          media_asset_id: filters.media_asset_id,
        }),
        apiClient.getMediaAssets(),
      ]);
      setSuggestions(response.species_suggestions);
      setMediaAssets(nextMediaAssets);
      setSelectedSuggestionId((current) =>
        options.selectSuggestionId &&
        response.species_suggestions.some(
          (suggestion) => suggestion.id === options.selectSuggestionId,
        )
          ? options.selectSuggestionId
          : current &&
              response.species_suggestions.some((suggestion) => suggestion.id === current)
            ? current
            : response.species_suggestions[0]?.id ?? null,
      );
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not load species suggestions.",
      );
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  }

  async function loadCandidatePacks(): Promise<SpeciesCandidatePack[]> {
    try {
      const packs = await apiClient.listSpeciesCandidatePacks(true);
      setCandidatePacks(packs);
      return packs;
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load candidate packs.");
      return [];
    }
  }

  useEffect(() => {
    void loadSuggestions();
    void loadCandidatePacks();
  }, []);

  function startNewCandidatePack() {
    setEditingCandidatePackId(null);
    setCandidatePackName("");
    setCandidatePackDescription("");
    setCandidatePackMemberIds([]);
    setCandidatePackSearch("");
    setCandidateTaxonomyMatches([]);
  }

  function editCandidatePack(pack: SpeciesCandidatePack) {
    setEditingCandidatePackId(pack.id);
    setCandidatePackName(pack.display_name);
    setCandidatePackDescription(pack.description ?? "");
    setCandidatePackMemberIds(pack.members.map((member) => member.id));
    setCandidatePackSearch("");
    setCandidateTaxonomyMatches([]);
  }

  async function searchCandidateTaxonomy() {
    const query = candidatePackSearch.trim();
    if (!query) {
      setCandidateTaxonomyMatches([]);
      return;
    }
    try {
      const matches = await apiClient.getTaxonomySuggestions({ category: "bird", query });
      setCandidateTaxonomyMatches(matches.filter((label) => label.is_species));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not search the bird taxonomy.");
    }
  }

  function addCandidatePackMember(label: TaxonomyLabel) {
    setCandidatePackMemberIds((current) =>
      current.includes(label.id) ? current : [...current, label.id],
    );
  }

  async function saveCandidatePack(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (candidatePackMemberIds.length < 2 || candidatePackMemberIds.length > 200) {
      setError("A candidate pack needs between 2 and 200 bird species.");
      return;
    }
    if (editingCandidatePack?.is_builtin) {
      setError("Clone Backyard Core before editing it.");
      return;
    }
    setIsSavingCandidatePack(true);
    setError(null);
    try {
      const payload = {
        display_name: candidatePackName.trim(),
        description: candidatePackDescription.trim() || undefined,
        taxonomy_label_ids: candidatePackMemberIds,
      };
      const saved = editingCandidatePack
        ? await apiClient.updateSpeciesCandidatePack(editingCandidatePack.id, payload)
        : await apiClient.createSpeciesCandidatePack(payload);
      await loadCandidatePacks();
      editCandidatePack(saved);
      setMessage(
        editingCandidatePack
          ? `${saved.display_name} v${saved.version} created as the immutable successor. Existing evidence was preserved.`
          : `${saved.display_name} v${saved.version} created with ${saved.candidate_count} bird candidates.`,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save the candidate pack.");
    } finally {
      setIsSavingCandidatePack(false);
    }
  }

  async function cloneCandidatePack(pack: SpeciesCandidatePack) {
    setIsSavingCandidatePack(true);
    setError(null);
    try {
      const cloned = await apiClient.cloneSpeciesCandidatePack(pack.id);
      await loadCandidatePacks();
      editCandidatePack(cloned);
      setMessage(`${cloned.display_name} v${cloned.version} cloned. Edit its ordered bird members, then save a successor.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not clone the candidate pack.");
    } finally {
      setIsSavingCandidatePack(false);
    }
  }

  async function archiveCandidatePack(pack: SpeciesCandidatePack) {
    if (pack.is_builtin) {
      return;
    }
    setIsSavingCandidatePack(true);
    setError(null);
    try {
      await apiClient.archiveSpeciesCandidatePack(pack.id);
      const packs = await loadCandidatePacks();
      if (editingCandidatePackId === pack.id) {
        const refreshed = packs.find((candidate) => candidate.id === pack.id);
        if (refreshed) {
          editCandidatePack(refreshed);
        }
      }
      setMessage(`${pack.display_name} v${pack.version} archived. Streams safely fall back if it was selected.`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not archive the candidate pack.");
    } finally {
      setIsSavingCandidatePack(false);
    }
  }

  async function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await loadSuggestions({ showLoading: false });
  }

  async function clearFilters() {
    const nextFilters: SpeciesSuggestionFilters = { status: "all" };
    setStatusFilter("all");
    setSuggestedLabelFilter("");
    setVisitIdFilter("");
    setEventIdFilter("");
    setMediaAssetIdFilter("");
    await loadSuggestions({ showLoading: false, filters: nextFilters });
  }

  async function createManualSuggestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    const trimmedLabel = suggestedLabel.trim();
    if (!trimmedLabel) {
      setError("Add a suggested label before creating a suggestion.");
      return;
    }

    let parsedConfidence: number | undefined;
    let parsedRank: number;
    let parsedAlternatives: Array<Record<string, unknown>>;
    let parsedEvidenceRegion: Record<string, unknown> | undefined;
    try {
      parsedConfidence = parseOptionalConfidence(confidence);
      parsedRank = parseRank(rank);
      parsedAlternatives = parseJsonArray(alternativesJson, "Alternatives");
      parsedEvidenceRegion = parseOptionalJsonObject(evidenceRegionJson, "Evidence region");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Suggestion fields are invalid.");
      return;
    }

    const payload: SpeciesSuggestionCreateRequest = {
      adapter_id: adapterId.trim() || "manual_species_suggestion",
      adapter_name: adapterName.trim() || "Manual species suggestion",
      suggested_label: trimmedLabel,
      suggested_common_name: suggestedCommonName.trim() || undefined,
      suggested_scientific_name: suggestedScientificName.trim() || undefined,
      confidence: parsedConfidence,
      rank: parsedRank,
      alternatives: parsedAlternatives,
      evidence_region: parsedEvidenceRegion,
      visit_id: visitId.trim() || undefined,
      event_id: eventId.trim() || undefined,
      media_asset_id: mediaAssetId.trim() || undefined,
      motion_evidence_id: motionEvidenceId.trim() || undefined,
      source_id: sourceId.trim() || undefined,
      stream_id: streamId.trim() || undefined,
      notes: notes.trim() || undefined,
    };

    setIsCreating(true);
    try {
      const created = await apiClient.createSpeciesSuggestion(payload);
      setStatusFilter("pending");
      setSuggestedLabelFilter("");
      setVisitIdFilter("");
      setEventIdFilter("");
      setMediaAssetIdFilter("");
      setSelectedSuggestionId(created.id);
      setSuggestedLabel("");
      setSuggestedCommonName("");
      setSuggestedScientificName("");
      setConfidence("");
      setRank("1");
      setAlternativesJson("[]");
      setEvidenceRegionJson("");
      setMessage(
        `${created.id} created as pending species suggestion evidence. It did not create correction truth.`,
      );
      await loadSuggestions({
        showLoading: false,
        selectSuggestionId: created.id,
        filters: { status: "pending" },
      });
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Manual species suggestion could not be created.",
      );
    } finally {
      setIsCreating(false);
    }
  }

  async function updateStatus(suggestion: SpeciesSuggestion, status: SpeciesSuggestionStatus) {
    setActionId(`${suggestion.id}:${status}`);
    setError(null);
    setMessage(null);
    try {
      const updated = await apiClient.updateSpeciesSuggestionStatus(suggestion.id, status);
      setSelectedSuggestionId(updated.id);
      setMessage(
        `${updated.id} marked ${formatLabel(updated.status)} as suggestion evidence only. Reviewed truth was not changed.`,
      );
      await loadSuggestions({ showLoading: false, selectSuggestionId: updated.id });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Suggestion status could not be updated.");
    } finally {
      setActionId(null);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Developer tool"
        title="Species Suggestions"
        description="Inspect classifier or manual suggestion evidence for review testing. Suggestions do not create reviewed labels, dataset truth, or export-ready observations."
        actions={
          <button className="secondary-action" onClick={onOpenReview}>
            Review Queue
          </button>
        }
      />

      <section className="notice-panel">
        <strong>Developer tool — evidence before truth</strong>
        <span>
          Accept means useful evidence only; reject means dismissed evidence; supersede means
          replaced evidence. Save a correction in review before exports, coverage, or analytics
          treat a species label as truth.
        </span>
      </section>

      {message ? <div className="notice-panel">{message}</div> : null}
      {error ? <div className="error-panel">{error}</div> : null}

      <section className="panel">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Stream-scoped model context</span>
            <h2>Species candidate packs</h2>
            <span className="meta-text">
              Ordered existing bird taxonomy only - 2-200 candidates - edits create an immutable successor.
            </span>
          </div>
          <button className="secondary-action" onClick={startNewCandidatePack} type="button">
            New pack
          </button>
        </div>

        <div className="review-identification-grid">
          {candidatePacks.map((pack) => (
            <div className="data-row" key={pack.id}>
              <span>{pack.status === "active" ? "Active" : "Archived"}</span>
              <strong>{pack.display_name} v{pack.version}</strong>
              <small>
                {pack.candidate_count} bird species - {pack.is_builtin ? "Built-in and immutable" : "User pack"}
              </small>
              <div className="detail-actions">
                <button className="text-action" onClick={() => editCandidatePack(pack)} type="button">
                  Inspect
                </button>
                {pack.is_builtin ? (
                  <button
                    className="text-action"
                    disabled={isSavingCandidatePack}
                    onClick={() => void cloneCandidatePack(pack)}
                    type="button"
                  >
                    Clone
                  </button>
                ) : pack.status === "active" ? (
                  <>
                    <button className="text-action" onClick={() => editCandidatePack(pack)} type="button">
                      Edit
                    </button>
                    <button
                      className="text-action"
                      disabled={isSavingCandidatePack}
                      onClick={() => void archiveCandidatePack(pack)}
                      type="button"
                    >
                      Archive
                    </button>
                  </>
                ) : null}
              </div>
            </div>
          ))}
        </div>

        {editingCandidatePack?.is_builtin ? (
          <div className="notice-panel">
            <strong>{editingCandidatePack.display_name} v{editingCandidatePack.version}</strong>
            <span>
              This immutable built-in pack preserves the legacy candidate scope. Clone it to change
              its ordered bird members.
            </span>
          </div>
        ) : (
          <form className="species-suggestion-form" onSubmit={saveCandidatePack}>
            <div className="section-heading">
              <div>
                <h3>{editingCandidatePack ? "Edit user pack" : "Create user pack"}</h3>
                <span className="meta-text">
                  {editingCandidatePack
                    ? `Saving creates v${editingCandidatePack.version + 1} and archives this active version.`
                    : "New packs are active immediately and can then be selected per Stream."}
                </span>
              </div>
              {editingCandidatePack ? (
                <span className="meta-text">{editingCandidatePack.status}</span>
              ) : null}
            </div>
            <div className="species-suggestion-form-grid">
              <label>
                Pack name
                <input
                  maxLength={80}
                  onChange={(event) => setCandidatePackName(event.target.value)}
                  required
                  value={candidatePackName}
                />
              </label>
              <label>
                Short description
                <input
                  maxLength={280}
                  onChange={(event) => setCandidatePackDescription(event.target.value)}
                  value={candidatePackDescription}
                />
              </label>
            </div>
            <div className="review-bulk-actions">
              <label>
                Search bird taxonomy
                <input
                  onChange={(event) => setCandidatePackSearch(event.target.value)}
                  placeholder="e.g. titmouse"
                  value={candidatePackSearch}
                />
              </label>
              <button
                className="secondary-action"
                onClick={() => void searchCandidateTaxonomy()}
                type="button"
              >
                Search
              </button>
            </div>
            {candidateTaxonomyMatches.length > 0 ? (
              <div className="label-helper-chips">
                {candidateTaxonomyMatches.map((label) => (
                  <button
                    disabled={candidatePackMemberIds.includes(label.id)}
                    key={label.id}
                    onClick={() => addCandidatePackMember(label)}
                    type="button"
                  >
                    Add {label.display_name}
                  </button>
                ))}
              </div>
            ) : null}
            <div className="data-row">
              <span>Ordered members</span>
              <strong>{candidatePackMemberIds.length} / 2-200</strong>
              <div className="label-helper-chips">
                {candidatePackMemberLabels.map((member) => (
                  <button
                    key={member.id}
                    onClick={() =>
                      setCandidatePackMemberIds((current) =>
                        current.filter((candidateId) => candidateId !== member.id),
                      )
                    }
                    type="button"
                  >
                    Remove {member.label}
                  </button>
                ))}
              </div>
              <small>Order is preserved as shown; no free-text labels are accepted.</small>
            </div>
            <div className="detail-actions">
              <button
                className="primary-action"
                disabled={isSavingCandidatePack || editingCandidatePack?.status === "archived"}
                type="submit"
              >
                {isSavingCandidatePack
                  ? "Saving..."
                  : editingCandidatePack
                    ? "Create successor"
                    : "Create pack"}
              </button>
              {editingCandidatePack ? (
                <button className="text-action" onClick={startNewCandidatePack} type="button">
                  Cancel edit
                </button>
              ) : null}
            </div>
          </form>
        )}
      </section>

      <section className="panel species-suggestion-create-panel">
        <div className="section-heading">
          <div>
            <h2>Create manual suggestion</h2>
            <span className="meta-text">
              Manual suggestions are for local review workflow testing before SpeciesNet or a
              custom classifier is wired in.
            </span>
          </div>
          <EvidenceBadge label="Pending evidence only" tone="review" />
        </div>
        <form className="species-suggestion-form" onSubmit={createManualSuggestion}>
          <div className="species-suggestion-form-grid">
            <label>
              Adapter ID
              <input
                required
                value={adapterId}
                onChange={(event) => setAdapterId(event.target.value)}
              />
            </label>
            <label>
              Adapter name
              <input
                required
                value={adapterName}
                onChange={(event) => setAdapterName(event.target.value)}
              />
            </label>
            <label>
              Suggested label
              <input
                required
                value={suggestedLabel}
                onChange={(event) => setSuggestedLabel(event.target.value)}
                placeholder="northern_cardinal"
              />
            </label>
            <label>
              Confidence
              <input
                inputMode="decimal"
                value={confidence}
                onChange={(event) => setConfidence(event.target.value)}
                placeholder="0.81"
              />
            </label>
            <label>
              Rank
              <input
                inputMode="numeric"
                value={rank}
                onChange={(event) => setRank(event.target.value)}
                placeholder="1"
              />
            </label>
            <label>
              Common name
              <input
                value={suggestedCommonName}
                onChange={(event) => setSuggestedCommonName(event.target.value)}
                placeholder="Northern Cardinal"
              />
            </label>
            <label>
              Scientific name
              <input
                value={suggestedScientificName}
                onChange={(event) => setSuggestedScientificName(event.target.value)}
                placeholder="Cardinalis cardinalis"
              />
            </label>
            <label>
              Visit ID
              <input
                value={visitId}
                onChange={(event) => setVisitId(event.target.value)}
                placeholder="visit-bird-feeder-001"
              />
            </label>
            <label>
              Event ID
              <input
                value={eventId}
                onChange={(event) => setEventId(event.target.value)}
                placeholder="event-bird-feeder-001"
              />
            </label>
            <label>
              Media asset
              <select
                value={mediaAssetId}
                onChange={(event) => setMediaAssetId(event.target.value)}
              >
                <option value="">No media asset</option>
                {[...mediaAssets].reverse().map((asset) => (
                  <option key={asset.id} value={asset.id}>
                    {asset.original_filename} - {asset.id}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Motion evidence ID
              <input
                value={motionEvidenceId}
                onChange={(event) => setMotionEvidenceId(event.target.value)}
                placeholder="motion-evidence-001"
              />
            </label>
            <label>
              Source ID
              <input
                value={sourceId}
                onChange={(event) => setSourceId(event.target.value)}
                placeholder="source-backyard-demo"
              />
            </label>
            <label>
              Stream ID
              <input
                value={streamId}
                onChange={(event) => setStreamId(event.target.value)}
                placeholder="stream-backyard-feeder"
              />
            </label>
            <label className="species-wide-field">
              Alternatives JSON
              <textarea
                value={alternativesJson}
                onChange={(event) => setAlternativesJson(event.target.value)}
                placeholder='[{"label":"house_finch","confidence":0.12}]'
              />
            </label>
            <label className="species-wide-field">
              Evidence region JSON
              <textarea
                value={evidenceRegionJson}
                onChange={(event) => setEvidenceRegionJson(event.target.value)}
                placeholder='{"x":0.42,"y":0.28,"width":0.2,"height":0.3}'
              />
            </label>
            <label className="species-wide-field">
              Notes
              <textarea value={notes} onChange={(event) => setNotes(event.target.value)} />
            </label>
          </div>
          {formMediaAsset ? (
            <div className="species-suggestion-media-preview">
              <MediaAssetPreview asset={formMediaAsset} compact />
            </div>
          ) : null}
          <div className="species-form-actions">
            <button className="primary-action" disabled={isCreating} type="submit">
              {isCreating ? "Creating..." : "Create pending suggestion"}
            </button>
            <span className="field-helper">
              Create stores suggestion evidence only. It does not create labels, reviewed visits,
              exports, coverage truth, or analytics truth.
            </span>
          </div>
        </form>
      </section>

      <section className="panel species-suggestion-filters">
        <div className="section-heading">
          <div>
            <h2>Suggestion filters</h2>
            <span className="meta-text">
              Filter by status, label, and linked Event/Visit/media evidence.
            </span>
          </div>
          <EvidenceBadge label={`${suggestions.length} shown`} tone="evidence" />
        </div>
        <form className="species-suggestion-filter-grid" onSubmit={applyFilters}>
          <label>
            Status
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as SpeciesSuggestionFilter)}
            >
              {statusOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Suggested label
            <input
              value={suggestedLabelFilter}
              onChange={(event) => setSuggestedLabelFilter(event.target.value)}
              placeholder="blue_jay"
            />
          </label>
          <label>
            Visit ID
            <input
              value={visitIdFilter}
              onChange={(event) => setVisitIdFilter(event.target.value)}
              placeholder="visit-bird-feeder-001"
            />
          </label>
          <label>
            Event ID
            <input
              value={eventIdFilter}
              onChange={(event) => setEventIdFilter(event.target.value)}
              placeholder="event-bird-feeder-001"
            />
          </label>
          <label>
            Media asset ID
            <input
              value={mediaAssetIdFilter}
              onChange={(event) => setMediaAssetIdFilter(event.target.value)}
              placeholder="media-asset-001"
            />
          </label>
          <div className="species-filter-actions">
            <button className="secondary-action" type="submit">
              Apply
            </button>
            {hasFilters ? (
              <button className="text-action" onClick={() => void clearFilters()} type="button">
                Clear
              </button>
            ) : null}
          </div>
        </form>
      </section>

      {isLoading ? <div className="panel">Loading species suggestions...</div> : null}

      {!isLoading && suggestions.length === 0 ? (
        <EmptyState
          title={hasFilters ? "No species suggestions match this filter." : "No species suggestions yet."}
          description={
            hasFilters
              ? "Try another status, label, or linked product ID."
              : "Create a manual suggestion to exercise the review-evidence flow before classifier runtime work."
          }
        />
      ) : null}

      {!isLoading && suggestions.length > 0 ? (
        <div className="species-suggestion-layout">
          <section className="species-suggestion-list" aria-label="Species suggestion list">
            {suggestions.map((suggestion) => (
              <button
                className={
                  selectedSuggestion?.id === suggestion.id
                    ? "species-suggestion-row selected"
                    : "species-suggestion-row"
                }
                key={suggestion.id}
                onClick={() => setSelectedSuggestionId(suggestion.id)}
                type="button"
              >
                <div className="item-title-row">
                  <div>
                    <span className="meta-text">{suggestion.adapter_name}</span>
                    <h2>{formatLabel(suggestion.suggested_label)}</h2>
                    {suggestion.suggested_common_name ||
                    suggestion.suggested_scientific_name ? (
                      <span className="meta-text">
                        {[suggestion.suggested_common_name, suggestion.suggested_scientific_name]
                          .filter(Boolean)
                          .join(" / ")}
                      </span>
                    ) : null}
                  </div>
                  <SuggestionStatusBadge status={suggestion.status} />
                </div>
                <div className="species-suggestion-meta">
                  <span>Rank {suggestion.rank}</span>
                  <span>
                    {formatConfidence(suggestion.confidence)}{" "}
                    {speciesSuggestionMetricLabel(suggestion)}
                  </span>
                  <span>{formatDateTime(suggestion.created_at)}</span>
                </div>
                <div className="species-suggestion-links">
                  <span>Event: {suggestion.event_id ?? "none"}</span>
                  <span>Visit: {suggestion.visit_id ?? "none"}</span>
                  <span>Media: {suggestion.media_asset_id ?? "none"}</span>
                </div>
              </button>
            ))}
          </section>

          <section className="panel species-suggestion-detail">
            {selectedSuggestion ? (
              <>
                <div className="section-heading">
                  <div>
                    <span className="meta-text">Selected suggestion</span>
                    <h2>{formatLabel(selectedSuggestion.suggested_label)}</h2>
                  </div>
                  <SuggestionStatusBadge status={selectedSuggestion.status} />
                </div>

                <div className="species-suggestion-detail-grid">
                  <DetailItem label="Suggestion ID" value={selectedSuggestion.id} />
                  <DetailItem label="Adapter" value={selectedSuggestion.adapter_name} />
                  <DetailItem label="Adapter ID" value={selectedSuggestion.adapter_id} />
                  <DetailItem label="Suggested label" value={selectedSuggestion.suggested_label} />
                  <DetailItem
                    label="Common name"
                    value={selectedSuggestion.suggested_common_name ?? "none"}
                  />
                  <DetailItem
                    label="Scientific name"
                    value={selectedSuggestion.suggested_scientific_name ?? "none"}
                  />
                  <DetailItem
                    label={
                      speciesSuggestionMetricLabel(selectedSuggestion) === "uncalibrated score"
                        ? "Uncalibrated score"
                        : "Confidence"
                    }
                    value={formatConfidence(selectedSuggestion.confidence)}
                  />
                  <DetailItem label="Rank" value={`${selectedSuggestion.rank}`} />
                  <DetailItem label="Created" value={formatDateTime(selectedSuggestion.created_at)} />
                </div>

                <section className="notice-panel compact-notice">
                  <strong>{formatLabel(selectedSuggestion.status)} suggestion evidence</strong>
                  <span>{suggestionStatusCopy(selectedSuggestion.status)}</span>
                </section>

                <section className="species-suggestion-subsection">
                  <h3>Evidence context</h3>
                  <div className="species-suggestion-detail-grid">
                    <DetailItem label="Source" value={selectedSuggestion.source_id ?? "none"} />
                    <DetailItem label="Stream" value={selectedSuggestion.stream_id ?? "none"} />
                    <DetailItem label="Event" value={selectedSuggestion.event_id ?? "none"} />
                    <DetailItem label="Visit" value={selectedSuggestion.visit_id ?? "none"} />
                    <DetailItem
                      label="Media asset"
                      value={selectedSuggestion.media_asset_id ?? "none"}
                    />
                    <DetailItem
                      label="Motion evidence"
                      value={selectedSuggestion.motion_evidence_id ?? "none"}
                    />
                  </div>
                  <div className="detail-actions">
                    {selectedSuggestion.event_id ? (
                      <button
                        className="text-action"
                        onClick={() => onOpenEvent(selectedSuggestion.event_id!)}
                        type="button"
                      >
                        Open Event
                      </button>
                    ) : null}
                    {selectedSuggestion.visit_id ? (
                      <button
                        className="text-action"
                        onClick={() => onOpenVisit(selectedSuggestion.visit_id!)}
                        type="button"
                      >
                        Open Visit
                      </button>
                    ) : null}
                    {selectedSuggestion.visit_id &&
                    selectedSuggestion.status !== "rejected" &&
                    selectedSuggestion.status !== "superseded" ? (
                      <button
                        className="primary-action"
                        onClick={() => onUseAsCorrection(selectedSuggestion)}
                        type="button"
                      >
                        Use as correction prefill
                      </button>
                    ) : null}
                    {!selectedSuggestion.visit_id ? (
                      <span className="meta-text">
                        Link a Visit before this suggestion can prefill correction.
                      </span>
                    ) : null}
                    {selectedSuggestion.media_asset_id ? (
                      <a
                        className="text-action"
                        href={apiClient.mediaFileUrl(selectedSuggestion.media_asset_id)}
                        rel="noreferrer"
                        target="_blank"
                      >
                        Open media file
                      </a>
                    ) : null}
                  </div>
                </section>

                {selectedMediaAsset ? (
                  <section className="species-suggestion-subsection">
                    <h3>Media evidence</h3>
                    <MediaAssetPreview asset={selectedMediaAsset} compact />
                  </section>
                ) : null}

                <section className="species-suggestion-subsection">
                  <h3>Alternatives</h3>
                  {selectedSuggestion.alternatives.length > 0 ? (
                    <div className="species-json-summary">
                      {selectedSuggestion.alternatives.map((alternative, index) => (
                        <span key={`${selectedSuggestion.id}:alternative:${index}`}>
                          {formatJsonSummary(alternative)}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="meta-text">No alternatives attached.</span>
                  )}
                </section>

                <section className="species-suggestion-subsection">
                  <h3>Evidence region</h3>
                  {selectedSuggestion.evidence_region ? (
                    <div className="species-json-summary">
                      <span>{formatJsonSummary(selectedSuggestion.evidence_region)}</span>
                    </div>
                  ) : (
                    <span className="meta-text">No region or crop context attached.</span>
                  )}
                </section>

                {selectedSuggestion.notes ? (
                  <section className="species-suggestion-subsection">
                    <h3>Notes</h3>
                    <p>{selectedSuggestion.notes}</p>
                  </section>
                ) : null}

                <section className="notice-panel">
                  <strong>Truth boundary</strong>
                  <span>
                    This suggestion is evidence only. It does not create reviewed labels, mark a
                    Visit reviewed, update dataset coverage, or make exports ready. Submitting the
                    correction creates reviewed truth; status is marked accepted only after that
                    correction succeeds.
                  </span>
                </section>

                {selectedSuggestion.visit_id &&
                selectedSuggestion.status !== "rejected" &&
                selectedSuggestion.status !== "superseded" ? (
                  <section className="notice-panel">
                    <strong>Correction prefill available</strong>
                    <span>
                      This opens Visit Detail and pre-fills the correction field. It does not save
                      truth or change status until correction succeeds.
                    </span>
                  </section>
                ) : null}

                {selectedSuggestion.status === "pending" ? (
                  <section className="species-suggestion-actions">
                    {statusActions.map((action) => (
                      <button
                        className={
                          action.status === "accepted" ? "primary-action" : "secondary-action"
                        }
                        disabled={actionId === `${selectedSuggestion.id}:${action.status}`}
                        key={action.status}
                        onClick={() => void updateStatus(selectedSuggestion, action.status)}
                        type="button"
                      >
                        {actionId === `${selectedSuggestion.id}:${action.status}`
                          ? "Saving..."
                          : action.label}
                      </button>
                    ))}
                    <span className="field-helper">
                      These actions update suggestion status only. Use as correction opens the
                      existing correction form and marks accepted only after submit succeeds.
                    </span>
                  </section>
                ) : (
                  <section className="notice-panel">
                    <strong>{formatLabel(selectedSuggestion.status)} suggestion</strong>
                    <span>
                      This terminal status is read-only here. It still is not reviewed truth; use
                      Visit Detail correction to create dataset truth.
                    </span>
                  </section>
                )}
              </>
            ) : (
              <EmptyState
                title="No selected suggestion"
                description="Choose a suggestion to inspect its evidence context."
              />
            )}
          </section>
        </div>
      ) : null}
    </div>
  );
}

function SuggestionStatusBadge({ status }: { status: SpeciesSuggestionStatus }) {
  return <span className={`species-status-badge species-status-${status}`}>{formatLabel(status)}</span>;
}

function suggestionStatusCopy(status: SpeciesSuggestionStatus): string {
  switch (status) {
    case "accepted":
      return "Accepted means this was useful suggestion evidence. It is not reviewed truth by itself.";
    case "rejected":
      return "Rejected means dismissed evidence. It does not create or change a reviewed label.";
    case "superseded":
      return "Superseded means replaced by better evidence or correction history.";
    case "pending":
    default:
      return "Pending evidence can prefill correction when a Visit is linked.";
  }
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function parseOptionalConfidence(value: string): number | undefined {
  if (!value.trim()) {
    return undefined;
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0 || parsed > 1) {
    throw new Error("Confidence must be a number from 0 to 1.");
  }
  return parsed;
}

function parseRank(value: string): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1) {
    throw new Error("Rank must be a whole number of 1 or greater.");
  }
  return parsed;
}

function parseJsonArray(value: string, label: string): Array<Record<string, unknown>> {
  const trimmed = value.trim();
  if (!trimmed) {
    return [];
  }
  const parsed = JSON.parse(trimmed) as unknown;
  if (!Array.isArray(parsed)) {
    throw new Error(`${label} must be a JSON array.`);
  }
  if (
    parsed.some(
      (item) => typeof item !== "object" || item === null || Array.isArray(item),
    )
  ) {
    throw new Error(`${label} must contain JSON objects.`);
  }
  return parsed as Array<Record<string, unknown>>;
}

function parseOptionalJsonObject(
  value: string,
  label: string,
): Record<string, unknown> | undefined {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }
  const parsed = JSON.parse(trimmed) as unknown;
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error(`${label} must be a JSON object.`);
  }
  return parsed as Record<string, unknown>;
}

function formatConfidence(value?: number | null): string {
  if (typeof value !== "number") {
    return "Unavailable";
  }
  return `${Math.round(value * 100)}%`;
}

function formatJsonSummary(value: Record<string, unknown>): string {
  return Object.entries(value)
    .map(([key, item]) => `${formatLabel(key)}: ${String(item)}`)
    .join(" · ");
}
