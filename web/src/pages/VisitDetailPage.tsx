import { useEffect, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type {
  MediaAsset,
  MotionEvidence,
  SpeciesSuggestion,
  TaxonomyLabel,
  VisitDetail,
  VisitEvidenceFrame,
  VisitIdentificationAssistantResponse,
  VisitIdentificationEvidenceMode,
  VisitOrganizationState,
  VisitCollectionSummary,
  VisitReviewHistoryEntry,
} from "../api/types";
import { DetectionEvidenceCard } from "../components/DetectionEvidenceCard";
import { DetectionProposalEvidenceCard } from "../components/DetectionProposalEvidenceCard";
import { EvidenceBadge } from "../components/EvidenceBadge";
import { IdentificationAssistant } from "../components/IdentificationAssistant";
import { MediaAssetPreview } from "../components/MediaAssetPreview";
import { StatusPill } from "../components/StatusPill";
import { speciesSuggestionMetricLabel } from "../components/speciesSuggestion";
import { TaxonomyLabelInput } from "../components/TaxonomyLabelInput";
import { TaxonomyBadge } from "../components/TaxonomyBadge";
import { VisitEvidenceSequence } from "../components/VisitEvidenceSequence";
import { displayTaxonomyLabel, findTaxonomyLabel, isBirdReviewLabel } from "../components/taxonomy";
import { formatDateTime, formatLabel } from "../utils";

interface VisitDetailPageProps {
  visitId: string;
  onOpenStream: (streamId: string) => void;
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenExports: () => void;
  onOpenDetectionProposals: () => void;
  onOpenMotionEvidence: (motionEvidenceId: string) => void;
  onCorrectionSaved: () => Promise<void>;
  onOpenCollections: () => void;
  correctionPrefill?: VisitCorrectionPrefill | null;
}

interface VisitCorrectionPrefill {
  visitId: string;
  label: string;
  speciesSuggestionId: string;
  suggestedCommonName?: string | null;
  suggestedScientificName?: string | null;
}

const visitCorrectionTruthCopy = "Corrections are the source of truth for analytics and exports.";

function newReviewRequestKey(prefix: string): string {
  const uniquePart =
    typeof crypto?.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `${prefix}-${uniquePart}`;
}

export function VisitDetailPage({
  visitId,
  onOpenStream,
  onOpenEvent,
  onOpenVisit,
  onOpenExports,
  onOpenDetectionProposals,
  onOpenMotionEvidence,
  onCorrectionSaved,
  correctionPrefill,
  onOpenCollections,
}: VisitDetailPageProps) {
  const [detail, setDetail] = useState<VisitDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [speciesSuggestions, setSpeciesSuggestions] = useState<SpeciesSuggestion[]>([]);
  const [isLoadingSpeciesSuggestions, setIsLoadingSpeciesSuggestions] = useState(true);
  const [speciesSuggestionError, setSpeciesSuggestionError] = useState<string | null>(null);
  const [identificationAssistant, setIdentificationAssistant] = useState<VisitIdentificationAssistantResponse | null>(null);
  const [identificationAssistantError, setIdentificationAssistantError] = useState<string | null>(null);
  const [isLoadingIdentificationAssistant, setIsLoadingIdentificationAssistant] = useState(false);
  const [isRunningIdentificationAssistant, setIsRunningIdentificationAssistant] = useState(false);
  const [organization, setOrganization] = useState<VisitOrganizationState | null>(null);
  const [organizationMessage, setOrganizationMessage] = useState<string | null>(null);
  const [isSavingOrganization, setIsSavingOrganization] = useState(false);
  const [collections, setCollections] = useState<VisitCollectionSummary[]>([]);
  const [visitCollections, setVisitCollections] = useState<VisitCollectionSummary[]>([]);
  const [selectedCollectionId, setSelectedCollectionId] = useState("");
  const [newCollectionName, setNewCollectionName] = useState("");
  const [collectionMessage, setCollectionMessage] = useState<string | null>(null);
  const [correctionSuggestionId, setCorrectionSuggestionId] = useState<string | null>(null);
  const [dismissedPrefillId, setDismissedPrefillId] = useState<string | null>(null);
  const [mockSuggestedLabel, setMockSuggestedLabel] = useState("");
  const [isCreatingMockSuggestion, setIsCreatingMockSuggestion] = useState(false);
  const [taxonomyLabels, setTaxonomyLabels] = useState<TaxonomyLabel[]>([]);
  const [label, setLabel] = useState("");
  const [notes, setNotes] = useState("");
  const [isEditingReviewed, setIsEditingReviewed] = useState(false);
  const [isReopening, setIsReopening] = useState(false);
  const [revisionIdempotencyKey, setRevisionIdempotencyKey] = useState<string | null>(null);
  const [reopenIdempotencyKey, setReopenIdempotencyKey] = useState<string | null>(null);
  const incomingCorrectionPrefill =
    correctionPrefill?.visitId === visitId ? correctionPrefill : null;
  const activeCorrectionPrefill =
    incomingCorrectionPrefill?.speciesSuggestionId !== dismissedPrefillId
      ? incomingCorrectionPrefill
      : null;

  async function loadDetail(options: { showLoading?: boolean; prefillLabel?: string | null } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoading(true);
    }
    setError(null);
    try {
      const nextDetail = await apiClient.getVisitDetail(visitId);
      setDetail(nextDetail);
      setLabel((current) =>
        options.prefillLabel ||
        current ||
        nextDetail.visit.reviewed_label ||
        nextDetail.visit.species_guess ||
        nextDetail.visit.subject_label,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load visit detail.");
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  }

  async function loadSpeciesSuggestions(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoadingSpeciesSuggestions(true);
    }
    setSpeciesSuggestionError(null);
    try {
      const response = await apiClient.listSpeciesSuggestions({ visit_id: visitId });
      setSpeciesSuggestions(response.species_suggestions);
    } catch (caught) {
      setSpeciesSuggestionError(
        caught instanceof Error ? caught.message : "Could not load species suggestions.",
      );
    } finally {
      if (showLoading) {
        setIsLoadingSpeciesSuggestions(false);
      }
    }
  }

  async function loadIdentificationAssistant() {
    setIsLoadingIdentificationAssistant(true);
    setIdentificationAssistantError(null);
    try {
      setIdentificationAssistant(await apiClient.getVisitIdentificationAssistant(visitId));
    } catch (caught) {
      setIdentificationAssistantError(
        caught instanceof Error ? caught.message : "Could not check Identification Assistant availability.",
      );
    } finally {
      setIsLoadingIdentificationAssistant(false);
    }
  }

  useEffect(() => {
    setDismissedPrefillId(null);
    if (incomingCorrectionPrefill?.speciesSuggestionId) {
      setMessage(null);
    }
    setLabel(incomingCorrectionPrefill?.label ?? "");
    setNotes("");
    setMockSuggestedLabel("");
    setCorrectionSuggestionId(incomingCorrectionPrefill?.speciesSuggestionId ?? null);
    setIsEditingReviewed(false);
    setRevisionIdempotencyKey(null);
    setReopenIdempotencyKey(null);
    void loadDetail({ prefillLabel: incomingCorrectionPrefill?.label });
  }, [visitId, incomingCorrectionPrefill?.speciesSuggestionId]);

  useEffect(() => {
    setMessage(null);
  }, [visitId]);

  useEffect(() => {
    void loadIdentificationAssistant();
  }, [visitId]);

  useEffect(() => {
    void apiClient.getVisitOrganization(visitId).then(setOrganization).catch(() => setOrganizationMessage("Observation notes are unavailable right now."));
  }, [visitId]);

  async function refreshCollections() {
    try {
      const [available, current] = await Promise.all([
        apiClient.getVisitCollections(),
        apiClient.getCollectionsForVisit(visitId),
      ]);
      setCollections(available);
      setVisitCollections(current.collections);
    } catch {
      setCollectionMessage("Collections are unavailable right now. Your Visit is unchanged.");
    }
  }

  useEffect(() => { void refreshCollections(); }, [visitId]);

  async function addToCollection(collection: VisitCollectionSummary) {
    setCollectionMessage(null);
    try {
      const response = await apiClient.addVisitToCollection(collection.id, visitId, {
        expected_state_token: collection.state_token,
        idempotency_key: newReviewRequestKey("visit-collection-add"),
      });
      setCollectionMessage(response.result.status === "updated" ? `Added to ${collection.name}.` : `This Visit is already in ${collection.name}.`);
      await refreshCollections();
    } catch (caught) { setCollectionMessage(caught instanceof Error ? caught.message : "Could not add this Visit to the Collection."); }
  }

  async function removeFromCollection(collection: VisitCollectionSummary) {
    setCollectionMessage(null);
    try {
      await apiClient.removeVisitFromCollection(collection.id, visitId, {
        expected_state_token: collection.state_token,
        idempotency_key: newReviewRequestKey("visit-collection-remove"),
      });
      setCollectionMessage(`Removed from ${collection.name}.`);
      await refreshCollections();
    } catch (caught) { setCollectionMessage(caught instanceof Error ? caught.message : "Could not remove this Visit from the Collection."); }
  }

  async function createAndAddCollection() {
    const name = newCollectionName.trim();
    if (!name) { setCollectionMessage("Name the new Collection first."); return; }
    try {
      const created = await apiClient.createVisitCollection({ name, idempotency_key: newReviewRequestKey("visit-collection-create") });
      setNewCollectionName("");
      await addToCollection(created);
    } catch (caught) { setCollectionMessage(caught instanceof Error ? caught.message : "Could not create this Collection."); }
  }

  async function saveOrganization(update: { is_favorite?: boolean; note?: string }) {
    if (!organization) return;
    setIsSavingOrganization(true);
    setOrganizationMessage(null);
    try {
      const idempotency_key = newReviewRequestKey("visit-organization");
      setOrganization(await apiClient.updateVisitOrganization(visitId, { ...update, expected_state_token: organization.state_token, idempotency_key }));
      setOrganizationMessage("Observation notes saved.");
    } catch (caught) {
      setOrganizationMessage(caught instanceof Error ? caught.message : "Could not save observation notes.");
    } finally { setIsSavingOrganization(false); }
  }

  useEffect(() => {
    let isMounted = true;

    async function loadSuggestions() {
      setIsLoadingSpeciesSuggestions(true);
      setSpeciesSuggestionError(null);
      try {
        const response = await apiClient.listSpeciesSuggestions({ visit_id: visitId });
        if (isMounted) {
          setSpeciesSuggestions(response.species_suggestions);
        }
      } catch (caught) {
        if (isMounted) {
          setSpeciesSuggestionError(
            caught instanceof Error ? caught.message : "Could not load species suggestions.",
          );
        }
      } finally {
        if (isMounted) {
          setIsLoadingSpeciesSuggestions(false);
        }
      }
    }

    void loadSuggestions();

    return () => {
      isMounted = false;
    };
  }, [visitId]);

  useEffect(() => {
    let isMounted = true;

    async function loadTaxonomy() {
      try {
        const labels = await apiClient.getTaxonomyLabels();
        if (isMounted) {
          setTaxonomyLabels(labels);
        }
      } catch (caught) {
        if (isMounted) {
          setMessage(caught instanceof Error ? caught.message : "Could not load taxonomy labels.");
        }
      }
    }

    void loadTaxonomy();

    return () => {
      isMounted = false;
    };
  }, []);

  function useSpeciesSuggestionAsCorrection(suggestion: SpeciesSuggestion) {
    setLabel(suggestion.suggested_label);
    setCorrectionSuggestionId(suggestion.id);
    setMessage(
      "SpeciesSuggestion prefilled the correction field. Review or edit it, then submit the correction to create truth.",
    );
  }

  function useIdentificationAssistantSuggestion(labelToUse: string, suggestionId: string) {
    setLabel(labelToUse);
    setCorrectionSuggestionId(suggestionId);
    setMessage(
      "Identification Assistant prefilled the correction field. Review or edit it, then explicitly save the correction to create truth.",
    );
  }

  async function runIdentificationAssistant(evidenceMode: VisitIdentificationEvidenceMode) {
    setIsRunningIdentificationAssistant(true);
    setIdentificationAssistantError(null);
    try {
      const result = await apiClient.startVisitIdentificationAssistant(visitId, {
        evidence_mode: evidenceMode,
        idempotency_key: newReviewRequestKey("identification-assistant"),
      });
      setIdentificationAssistant(result);
      setMessage(result.message);
      await loadSpeciesSuggestions({ showLoading: false });
    } catch (caught) {
      setIdentificationAssistantError(
        caught instanceof Error ? caught.message : "Identification Assistant could not analyze saved evidence.",
      );
    } finally {
      setIsRunningIdentificationAssistant(false);
    }
  }

  function clearCorrectionPrefill() {
    const sourceSuggestionId = activeCorrectionPrefill?.speciesSuggestionId ?? correctionSuggestionId;
    setDismissedPrefillId(sourceSuggestionId);
    setCorrectionSuggestionId(null);
    setLabel(
      detail?.visit.reviewed_label ??
        detail?.visit.species_guess ??
        detail?.visit.subject_label ??
        "",
    );
    setMessage("Suggestion prefill cleared. The correction form is ready for manual review.");
  }

  async function createMockSuggestion() {
    setIsCreatingMockSuggestion(true);
    setMessage(null);
    setSpeciesSuggestionError(null);
    try {
      const trimmedLabel = mockSuggestedLabel.trim();
      const created = await apiClient.createMockSpeciesSuggestion({
        visit_id: visitId,
        suggested_label: trimmedLabel || undefined,
      });
      setMockSuggestedLabel("");
      setMessage(
        `${displayTaxonomyLabel(
          created.suggested_label,
          taxonomyLabels,
        )} mock SpeciesSuggestion evidence created. Reviewed truth was not changed.`,
      );
      await loadSpeciesSuggestions({ showLoading: false });
    } catch (caught) {
      setSpeciesSuggestionError(
        caught instanceof Error ? caught.message : "Mock suggestion could not be created.",
      );
    } finally {
      setIsCreatingMockSuggestion(false);
    }
  }

  async function saveCorrection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedLabel = label.trim();
    if (!trimmedLabel) {
      setMessage("Add a label before saving a correction.");
      return;
    }

    setIsSaving(true);
    setMessage(null);
    setError(null);
    try {
      const result = await apiClient.createReviewLabel({
        target_type: "visit",
        target_id: visitId,
        label: trimmedLabel,
        notes: notes.trim() || undefined,
      });
      let correctionMessage = `${displayTaxonomyLabel(
        result.review_label.label,
        taxonomyLabels,
      )} will be used as local dataset truth.`;

      if (correctionSuggestionId) {
        const sourceSuggestion = speciesSuggestions.find(
          (suggestion) => suggestion.id === correctionSuggestionId,
        );
        try {
          if (sourceSuggestion?.status === "accepted") {
            correctionMessage = "Correction saved and suggestion marked accepted.";
          } else if (
            sourceSuggestion?.status === "rejected" ||
            sourceSuggestion?.status === "superseded"
          ) {
            correctionMessage = "Correction saved. Suggestion status could not be updated.";
          } else {
            const updatedSuggestion = await apiClient.updateSpeciesSuggestionStatus(
              correctionSuggestionId,
              "accepted",
            );
            setSpeciesSuggestions((current) =>
              current.map((suggestion) =>
                suggestion.id === updatedSuggestion.id ? updatedSuggestion : suggestion,
              ),
            );
            correctionMessage = "Correction saved and suggestion marked accepted.";
          }
        } catch {
          correctionMessage = "Correction saved. Suggestion status could not be updated.";
        }
      }

      setMessage(correctionMessage);
      await loadDetail({ showLoading: false });
      await loadSpeciesSuggestions({ showLoading: false });
      await onCorrectionSaved();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Correction could not be saved.");
    } finally {
      setIsSaving(false);
    }
  }

  function beginReviewedRevision() {
    if (!detail) {
      return;
    }
    setLabel(
      detail.visit.reviewed_label ?? detail.visit.species_guess ?? detail.visit.subject_label,
    );
    setNotes("");
    setCorrectionSuggestionId(null);
    setRevisionIdempotencyKey(null);
    setIsEditingReviewed(true);
    setMessage("Review the evidence and save a new identification when ready.");
  }

  function cancelReviewedRevision() {
    setIsEditingReviewed(false);
    setRevisionIdempotencyKey(null);
    setNotes("");
    setMessage("Revision canceled. The current reviewed correction is unchanged.");
  }

  async function saveReviewedRevision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedLabel = label.trim();
    if (!detail || !trimmedLabel) {
      setMessage("Add a label before saving a revised identification.");
      return;
    }

    const idempotencyKey = revisionIdempotencyKey ?? newReviewRequestKey("visit-revision");
    setRevisionIdempotencyKey(idempotencyKey);
    setIsSaving(true);
    setMessage(null);
    setError(null);
    try {
      const result = await apiClient.reviseVisitReview(visitId, {
        label: trimmedLabel,
        notes: notes.trim() || undefined,
        expected_state_token: detail.review_state_token,
        idempotency_key: idempotencyKey,
      });
      setIsEditingReviewed(false);
      setRevisionIdempotencyKey(null);
      setMessage(
        result.idempotent
          ? "The revised identification was already saved."
          : `${displayTaxonomyLabel(result.result.review_label.label, taxonomyLabels)} is now the current reviewed truth.`,
      );
      await loadDetail({ showLoading: false });
      await onCorrectionSaved();
    } catch (caught) {
      setMessage(
        caught instanceof Error
          ? caught.message
          : "The revised identification could not be saved.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  async function reopenReviewedVisit() {
    if (!detail) {
      return;
    }
    if (
      !reopenIdempotencyKey &&
      !window.confirm(
        "Reopen this Visit for review? Its current correction will remain in history but no longer count as truth.",
      )
    ) {
      return;
    }

    const idempotencyKey = reopenIdempotencyKey ?? newReviewRequestKey("visit-reopen");
    setReopenIdempotencyKey(idempotencyKey);
    setIsReopening(true);
    setMessage(null);
    setError(null);
    try {
      const result = await apiClient.reopenVisitReview(visitId, {
        expected_state_token: detail.review_state_token,
        idempotency_key: idempotencyKey,
      });
      setIsEditingReviewed(false);
      setReopenIdempotencyKey(null);
      setMessage(result.message);
      await loadDetail({ showLoading: false });
      await onCorrectionSaved();
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "The Visit could not be reopened.");
    } finally {
      setIsReopening(false);
    }
  }

  if (isLoading) {
    return <div className="panel">Loading visit detail...</div>;
  }

  if (error || !detail) {
    return <div className="error-panel">{error ?? "Visit detail is unavailable."}</div>;
  }

  const visitLabel = detail.visit.reviewed_label ?? detail.visit.species_guess ?? detail.visit.subject_label;
  const runById = new Map(detail.detection_runs.map((run) => [run.id, run]));
  const currentCorrection = detail.correction_history.find((entry) => entry.is_current) ?? null;
  const priorCorrections = detail.correction_history.filter((entry) => !entry.is_current);
  const subjectTaxonomy = findTaxonomyLabel(detail.visit.subject_label, taxonomyLabels);
  const speciesGuessTaxonomy = findTaxonomyLabel(detail.visit.species_guess, taxonomyLabels);
  const reviewedTaxonomy = findTaxonomyLabel(detail.visit.reviewed_label, taxonomyLabels);
  const isSpeciesVisit =
    isBirdReviewLabel(detail.visit.reviewed_label, taxonomyLabels) ||
    isBirdReviewLabel(detail.visit.species_guess, taxonomyLabels) ||
    isBirdReviewLabel(detail.visit.subject_label, taxonomyLabels);
  const isMotionEvidenceVisit = detail.event.event_type === "motion_evidence";
  const webhookProvenance = detail.motion_evidence
    ? getWebhookEvidenceProvenance(detail.motion_evidence)
    : null;
  const hasWebhookEvidence = Boolean(webhookProvenance?.isWebhook);
  const hasSavedPreviewMedia = isSavedPreviewMedia(detail.media_asset);
  const hasFolderImportMedia = isFolderImportMedia(detail.media_asset);
  const mediaProvenance = formatMediaProvenance(detail.media_asset);
  const mediaContextTitle = hasWebhookEvidence
    ? "Webhook metadata evidence"
    : hasFolderImportMedia
    ? "Folder-imported media"
    : hasSavedPreviewMedia
      ? "Saved preview media"
      : "Attached media";
  const mediaContextBadge = hasWebhookEvidence
    ? "Generic webhook ingest"
    : hasFolderImportMedia
    ? "Folder-imported media"
    : hasSavedPreviewMedia
      ? "Saved local media"
      : "Review before labeling";
  const promotedEvidenceCopy = hasFolderImportMedia
    ? "This Visit came from promoted evidence linked to folder-imported local media."
    : hasWebhookEvidence
      ? "This Visit came from promoted evidence linked to webhook metadata."
      : hasSavedPreviewMedia
      ? "This Visit came from promoted evidence linked to saved local media."
      : "This Visit came from promoted evidence.";
  const folderRelativePath = extractSafeRelativePath(
    detail.media_asset?.notes ?? "",
    "relative_source_path",
  );
  const folderCopyMode = extractSafeNoteValue(detail.media_asset?.notes ?? "", "copy_mode");
  const correctionPrefillLabel = activeCorrectionPrefill
    ? displayTaxonomyLabel(activeCorrectionPrefill.label, taxonomyLabels)
    : "";
  const activeSuggestionLabel = correctionSuggestionId
    ? displayTaxonomyLabel(
        speciesSuggestions.find((suggestion) => suggestion.id === correctionSuggestionId)
          ?.suggested_label ?? activeCorrectionPrefill?.label ?? label,
        taxonomyLabels,
      )
    : "";
  const sortedSpeciesSuggestions = [...speciesSuggestions].sort(compareSpeciesSuggestions);

  return (
    <div className="page-stack">
      <div className="stream-detail-heading">
        <div>
          <span className="page-eyebrow">Visit case file</span>
          <StatusPill
            label={formatLabel(detail.visit.review_status)}
            tone={detail.visit.review_status === "needs_review" ? "review" : "good"}
          />
          <h1>{displayTaxonomyLabel(visitLabel, taxonomyLabels)} visit</h1>
          <p>{detail.review_summary}</p>
        </div>
        <StatusPill
          label={
            detail.dataset_ready && isSpeciesVisit
              ? "Ready for species dataset export"
              : detail.dataset_ready
                ? "Ready for local dataset export"
                : isSpeciesVisit
                  ? "Resolve species before export"
                  : "Needs review before export"
          }
          tone={detail.dataset_ready ? "good" : "review"}
        />
      </div>

      {message ? <div className="notice-panel">{message}</div> : null}

      {activeCorrectionPrefill ? (
        <section className="prefill-notice">
          <div>
            <strong>Prefilled from SpeciesSuggestion {activeCorrectionPrefill.speciesSuggestionId}</strong>
            <span>
              {detail.visit.review_status === "needs_review"
                ? `${correctionPrefillLabel} is evidence in the correction field. Submit the correction to create reviewed truth; the suggestion is marked accepted only after save succeeds.`
                : `${correctionPrefillLabel} was passed as suggestion evidence, but this Visit is already reviewed. No truth changed.`}
            </span>
          </div>
          {detail.visit.review_status === "needs_review" ? (
            <button className="text-action" onClick={clearCorrectionPrefill} type="button">
              Clear prefill
            </button>
          ) : null}
        </section>
      ) : null}

      {isMotionEvidenceVisit ? (
        <section className="notice-panel">
          <strong>Promoted activity evidence</strong>
          <span>
            {promotedEvidenceCopy} {visitCorrectionTruthCopy}
          </span>
        </section>
      ) : null}

      {isMotionEvidenceVisit ? (
        <section className="panel promoted-review-context-panel">
          <div className="section-heading">
            <div>
              <h2>Promoted evidence context</h2>
              <span className="meta-text">
                Reviewable Event/Visit context stays separate from correction truth.
              </span>
            </div>
            <EvidenceBadge
              label={mediaContextBadge}
              tone="evidence"
            />
          </div>
          <p className="evidence-panel-copy">
            {hasWebhookEvidence
              ? "This Visit came from promoted evidence linked to webhook metadata."
              : detail.media_asset
              ? mediaProvenance
              : "This Visit came from promoted evidence without attached media."}{" "}
            {visitCorrectionTruthCopy}
          </p>
          <div className="promoted-review-context-grid">
            <ContextItem label="Source" value={detail.stream.source_id} />
            <ContextItem label="Event" value={detail.event.title} detail={detail.event.id} />
            <ContextItem label="Stream" value={detail.stream.name} detail={detail.stream.id} />
            <ContextItem
              label="Zone"
              value={
                detail.primary_zone
                  ? `${detail.primary_zone.name} (${formatLabel(detail.primary_zone.zone_type)})`
                  : "Unzoned"
              }
              detail={detail.primary_zone?.id}
            />
            <ContextItem
              label={mediaContextTitle}
              value={detail.media_asset?.original_filename ?? "No attached media"}
              detail={detail.media_asset?.id}
            />
            {detail.motion_evidence ? (
              <ContextItem
                label="Advanced evidence"
                value={detail.motion_evidence.id}
                detail={formatLabel(detail.motion_evidence.status)}
              />
            ) : null}
            {hasWebhookEvidence && webhookProvenance ? (
              <>
                <ContextItem
                  label="Provider"
                  value={webhookProvenance.providerKey ?? "webhook_future"}
                />
                <ContextItem
                  label="External event ID"
                  value={formatWebhookValue(webhookProvenance.externalEventId)}
                />
                <ContextItem
                  label="Untrusted external label"
                  value={formatWebhookValue(webhookProvenance.externalLabel)}
                  detail="Evidence metadata only"
                />
                <ContextItem
                  label="Untrusted external confidence"
                  value={formatWebhookValue(webhookProvenance.externalConfidence)}
                  detail="Not review truth"
                />
                <ContextItem
                  label="Webhook timestamp"
                  value={formatWebhookValue(webhookProvenance.externalTimestamp)}
                />
              </>
            ) : null}
            {hasFolderImportMedia ? (
              <>
                <ContextItem label="Provider" value="folder_import_future" />
                <ContextItem
                  label="Original relative path"
                  value={folderRelativePath ?? "not available"}
                />
                <ContextItem
                  label="Import context"
                  value={folderCopyMode ? formatLabel(folderCopyMode) : "Imported local media"}
                />
              </>
            ) : null}
          </div>
        </section>
      ) : null}

      {hasWebhookEvidence ? (
        <section className="notice-panel">
          <strong>Webhook metadata evidence</strong>
          <span>
            This Visit came from promoted evidence linked to webhook metadata. Untrusted external
            labels and confidence stay evidence-only; corrections are the source of truth for
            analytics and exports.
          </span>
        </section>
      ) : null}

      {detail.motion_evidence ? (
        <SourceEvidenceTracePanel
          mediaAsset={detail.media_asset}
          motionEvidence={detail.motion_evidence}
          onOpenEvent={onOpenEvent}
          onOpenMotionEvidence={onOpenMotionEvidence}
        />
      ) : null}

      {currentCorrection ? (
        <CorrectionTruthPanel
          latest={currentCorrection}
          older={priorCorrections}
          taxonomyLabels={taxonomyLabels}
        />
      ) : null}

      <section className="case-summary-grid">
        <div className="panel case-summary-card">
          <span className="meta-text">Subject</span>
          <strong>{displayTaxonomyLabel(detail.visit.subject_label, taxonomyLabels)}</strong>
          <TaxonomyBadge label={subjectTaxonomy} value={detail.visit.subject_label} />
          {detail.visit.confidence ? (
            <span className="meta-text">{Math.round(detail.visit.confidence * 100)}% confidence</span>
          ) : null}
        </div>
        <div className="panel case-summary-card">
          <span className="meta-text">Species guess</span>
          <strong>{displayTaxonomyLabel(detail.visit.species_guess ?? "unknown", taxonomyLabels)}</strong>
          <span className="meta-text">
            Reviewed:{" "}
            {detail.visit.reviewed_label
              ? displayTaxonomyLabel(detail.visit.reviewed_label, taxonomyLabels)
              : "not reviewed"}
          </span>
        </div>
        <div className="panel case-summary-card">
          <span className="meta-text">Event</span>
          <button className="text-action" onClick={() => onOpenEvent(detail.event.id)}>
            {detail.event.title}
          </button>
          <span className="meta-text">{formatDateTime(detail.event.started_at)}</span>
        </div>
        <div className="panel case-summary-card">
          <span className="meta-text">Stream and zone</span>
          <button className="text-action" onClick={() => onOpenStream(detail.stream.id)}>
            {detail.stream.name}
          </button>
          <span className="meta-text">
            {detail.primary_zone
              ? `${detail.primary_zone.name} (${formatLabel(detail.primary_zone.zone_type)})`
              : "Unzoned"}
          </span>
        </div>
        {detail.media_asset ? (
          <div className="panel case-summary-card">
            <span className="meta-text">Media</span>
            <strong>{detail.media_asset.original_filename}</strong>
            <span className="meta-text">
              {hasFolderImportMedia
                ? "Folder-imported media"
                : hasSavedPreviewMedia
                  ? "Saved preview media"
                  : "Local media reference"}
            </span>
          </div>
        ) : null}
      </section>

      <VisitCurationPanel
        detail={detail}
        onCurationChanged={onCorrectionSaved}
        onOpenVisit={onOpenVisit}
        onReload={() => loadDetail({ showLoading: false })}
      />

      <section className="panel species-review-panel">
        <div className="section-heading">
          <div>
            <h2>{isSpeciesVisit ? "Species review" : "Review correction"}</h2>
            <span className="meta-text">
              Suggestion evidence is not truth. Corrected species is local dataset truth.
            </span>
          </div>
          <EvidenceBadge
            label={detail.dataset_ready && isSpeciesVisit ? "Ready for species dataset export" : "Resolve species"}
            tone={detail.dataset_ready ? "truth" : "review"}
          />
        </div>
        <div className="species-state-grid">
          <div>
            <span className="meta-text">{isSpeciesVisit ? "Reviewed species" : "Reviewed label"}</span>
            <strong>
              {detail.visit.reviewed_label
                ? displayTaxonomyLabel(detail.visit.reviewed_label, taxonomyLabels)
                : "Not reviewed"}
            </strong>
            <TaxonomyBadge label={reviewedTaxonomy} value={detail.visit.reviewed_label} />
          </div>
          <div>
            <span className="meta-text">Species guess</span>
            <strong>
              {detail.visit.species_guess
                ? displayTaxonomyLabel(detail.visit.species_guess, taxonomyLabels)
                : "No species suggestion"}
            </strong>
            <TaxonomyBadge label={speciesGuessTaxonomy} value={detail.visit.species_guess ?? "unknown_bird"} />
          </div>
          <div>
            <span className="meta-text">Dataset export</span>
            <strong>
              {detail.dataset_ready
                ? isSpeciesVisit
                  ? "Ready for species dataset export"
                  : "Ready for local dataset export"
                : isSpeciesVisit
                  ? "Resolve species"
                  : "Needs review"}
            </strong>
            <span className="meta-text">
              {detail.dataset_ready ? "Corrected truth is available." : "Save a correction before export."}
            </span>
          </div>
        </div>
      </section>

      {detail.media_asset ? (
        <section className="panel media-evidence-panel">
          <div className="section-heading">
            <h2>{mediaContextTitle}</h2>
            <span className="meta-text">{mediaProvenance}</span>
          </div>
          <MediaAssetPreview asset={detail.media_asset} />
          <div className="attached-media-provenance">
            <strong>Correction boundary</strong>
            <span>{visitCorrectionTruthCopy}</span>
            {hasFolderImportMedia ? (
              <span>This Visit came from promoted evidence linked to folder-imported local media.</span>
            ) : null}
            <span>
              {hasFolderImportMedia ? "Folder-imported media" : "Saved media"} does not confirm a
              label before review.
            </span>
            {detail.correction_history.length === 0 ? (
              <span>No label has been confirmed yet.</span>
            ) : null}
          </div>
          {hasFolderImportMedia ? (
            <div className="promoted-review-context-grid">
              <ContextItem label="Provider" value="folder_import_future" />
              <ContextItem
                label="Original relative path"
                value={folderRelativePath ?? "not available"}
              />
              <ContextItem
                label="Import context"
                value={folderCopyMode ? formatLabel(folderCopyMode) : "Imported local media"}
              />
              <ContextItem label="Truth boundary" value="Corrections decide analytics and exports" />
            </div>
          ) : null}
        </section>
      ) : null}

      {detail.detection_proposals.length > 0 ? (
        <section className="panel">
          <div className="section-heading">
            <h2>Suggestion provenance</h2>
            <EvidenceBadge label="Evidence source" />
          </div>
          <p className="evidence-panel-copy">
            This visit started as suggestion evidence. Use the correction form to set dataset truth;
            the suggestion remains supporting evidence.
          </p>
          <div className="evidence-list">
            {detail.detection_proposals.map((proposal) => (
              <DetectionProposalEvidenceCard
                key={proposal.id}
                proposal={proposal}
                run={runById.get(proposal.run_id)}
                taxonomyLabels={taxonomyLabels}
                zoneLabel={
                  detail.primary_zone && proposal.zone_id === detail.primary_zone.id
                    ? detail.primary_zone.name
                    : undefined
                }
              />
            ))}
          </div>
          <button className="secondary-action" onClick={onOpenDetectionProposals}>
            Detection Proposals
          </button>
        </section>
      ) : null}

      <section className="split-grid">
        <div className="panel">
          <div className="section-heading">
            <h2>Suggestions as evidence</h2>
            <EvidenceBadge label="Correction wins" tone="truth" />
          </div>
          <p className="evidence-panel-copy">
            Treat these labels as supporting evidence. The corrected visit label below becomes the
            dataset-grade value used by exports and analytics.
          </p>
          <div className="evidence-list">
            {detail.detections.length > 0 ? (
              detail.detections.map((detection) => (
                <DetectionEvidenceCard
                  detection={detection}
                  key={detection.id}
                  statusLabel={detail.dataset_ready ? "Corrected truth available" : "Needs review"}
                  zoneLabel={
                    detail.primary_zone && detection.zone_id === detail.primary_zone.id
                      ? detail.primary_zone.name
                      : undefined
                  }
                />
              ))
            ) : (
              <span className="meta-text">No detections are attached to this manual media visit.</span>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="section-heading">
            <h2>Correction history</h2>
          </div>
          <div className="history-list">
            {detail.correction_history.map((entry) => (
              <CorrectionHistoryItem
                key={`${entry.created_at}-${entry.action}-${entry.label ?? ""}`}
                entry={entry}
                taxonomyLabels={taxonomyLabels}
              />
            ))}
            {detail.correction_history.length === 0 ? (
              <span className="meta-text">No correction history yet.</span>
            ) : null}
          </div>
        </div>
      </section>

      <section className="panel observation-notes">
        <div className="section-heading"><div><h2>Observation notes</h2><span className="meta-text">Private local context. Notes never change the reviewed label.</span></div><StatusPill label={detail.visit.review_status === "reviewed" ? "Reviewed" : "Needs review"} tone={detail.visit.review_status === "reviewed" ? "good" : "review"} /></div>
        {organization ? <>
          <button className="secondary-action" disabled={isSavingOrganization} onClick={() => void saveOrganization({ is_favorite: !organization.is_favorite })} type="button">{organization.is_favorite ? "Remove favorite" : "Favorite this Visit"}</button>
          <label>Note <textarea maxLength={4000} value={organization.note} onChange={(event) => setOrganization({ ...organization, note: event.target.value })} /></label>
          <span className="field-helper">{organization.note.length}/4000 characters</span>
          <button className="primary-action" disabled={isSavingOrganization} onClick={() => void saveOrganization({ note: organization.note })} type="button">{isSavingOrganization ? "Saving..." : "Save note"}</button>
          {organization.updated_at ? <span className="meta-text">Updated {formatDateTime(organization.updated_at)}</span> : null}
        </> : <span className="meta-text">Loading observation notes...</span>}
        {organizationMessage ? <span className="meta-text">{organizationMessage}</span> : null}
      </section>

      <section className="panel">
        <div className="section-heading"><div><h2>Collections</h2><span className="meta-text">Private local galleries. Membership does not duplicate media or change review truth.</span></div><button className="text-action" onClick={onOpenCollections} type="button">Manage Collections</button></div>
        {visitCollections.length > 0 ? <div className="label-helper-chips">{visitCollections.map((collection) => <span key={collection.id}><StatusPill label={collection.name} tone="quiet" /><button className="text-action" onClick={() => void removeFromCollection(collection)} type="button" aria-label={`Remove this Visit from ${collection.name}`}>Remove</button></span>)}</div> : <span className="meta-text">This Visit is not in a Collection yet.</span>}
        <label>Add to Collection <select value={selectedCollectionId} onChange={(event) => setSelectedCollectionId(event.target.value)}><option value="">Choose a Collection</option>{collections.filter((collection) => !visitCollections.some((current) => current.id === collection.id)).map((collection) => <option key={collection.id} value={collection.id}>{collection.name}</option>)}</select></label>
        <button className="secondary-action" disabled={!selectedCollectionId} onClick={() => { const collection = collections.find((item) => item.id === selectedCollectionId); if (collection) void addToCollection(collection); }} type="button">Add Visit</button>
        <label>Create and add to new Collection <input maxLength={80} value={newCollectionName} onChange={(event) => setNewCollectionName(event.target.value)} /></label><span className="field-helper">{newCollectionName.length}/80 characters</span><button className="secondary-action" onClick={() => void createAndAddCollection()} type="button">Create and add</button>
        {collectionMessage ? <span className="meta-text">{collectionMessage}</span> : null}
      </section>

      <section className="panel">
        <IdentificationAssistant
          assistant={identificationAssistant}
          error={identificationAssistantError}
          isLoading={isLoadingIdentificationAssistant}
          isRunning={isRunningIdentificationAssistant}
          onAnalyze={(mode) => void runIdentificationAssistant(mode)}
          onClearPrefill={clearCorrectionPrefill}
          onUseSuggestion={useIdentificationAssistantSuggestion}
          prefilledSuggestionId={correctionSuggestionId}
        />
      </section>

      {detail.visit.review_status === "needs_review" ? (
        <section className="panel">
          <div className="section-heading">
            <h2>{isSpeciesVisit ? "Resolve species" : "Correct visit label"}</h2>
            <EvidenceBadge label="Dataset truth" tone="truth" />
          </div>
          <p className="evidence-panel-copy">
            {isSpeciesVisit
              ? "Use reviewed species, Unknown bird, or False positive. This value becomes dataset truth for analytics and exports."
              : "Use the reviewed label that should become dataset truth for analytics and exports."}
          </p>
          <div className="correction-truth-note">
            <strong>Correction form is the truth action</strong>
            <span>
              Suggestions can prefill the label only. You can edit the label and notes before
              saving; dataset/export truth changes only after this correction is submitted.
            </span>
          </div>
          <section className="species-suggestion-review-context">
            <div className="section-heading">
              <div>
                <h3>Species Suggestions</h3>
                <span className="meta-text">
                  Suggestions are evidence only. Submitting a correction creates reviewed truth.
                </span>
              </div>
              <EvidenceBadge
                label={`${speciesSuggestions.length} suggestion${
                  speciesSuggestions.length === 1 ? "" : "s"
                }`}
                tone={speciesSuggestions.length > 0 ? "evidence" : "quiet"}
              />
            </div>
            <div className="mock-suggestion-action">
              <label>
                Mock label
                <input
                  value={mockSuggestedLabel}
                  onChange={(event) => setMockSuggestedLabel(event.target.value)}
                  placeholder="optional; defaults to unknown_bird"
                />
              </label>
              <button
                className="secondary-action"
                disabled={isCreatingMockSuggestion}
                onClick={() => void createMockSuggestion()}
                type="button"
              >
                {isCreatingMockSuggestion ? "Creating..." : "Create mock suggestion"}
              </button>
              <span className="field-helper">
                Creates demo SpeciesSuggestion evidence only. It does not run a model or create
                reviewed truth.
              </span>
            </div>
            {correctionSuggestionId ? (
              <div className="suggestion-prefill-summary">
                <div>
                  <strong>Correction prefilled from suggestion {correctionSuggestionId}</strong>
                  <span>
                    {activeSuggestionLabel} is in the correction field. Edit it if needed; status is
                    marked accepted only after the correction succeeds.
                  </span>
                </div>
                <button className="text-action" onClick={clearCorrectionPrefill} type="button">
                  Clear prefill
                </button>
              </div>
            ) : null}
            {isLoadingSpeciesSuggestions ? (
              <span className="meta-text">Loading suggestions for this visit...</span>
            ) : null}
            {speciesSuggestionError ? (
              <div className="error-panel compact-error">{speciesSuggestionError}</div>
            ) : null}
            {!isLoadingSpeciesSuggestions &&
            !speciesSuggestionError &&
            speciesSuggestions.length === 0 ? (
              <span className="meta-text">No SpeciesSuggestions are linked to this visit yet.</span>
            ) : null}
            {!isLoadingSpeciesSuggestions &&
            !speciesSuggestionError &&
            speciesSuggestions.length > 0 ? (
              <div className="visit-suggestion-list">
                {sortedSpeciesSuggestions.map((suggestion) => (
                  <article
                    className={
                      correctionSuggestionId === suggestion.id
                        ? `visit-suggestion-card visit-suggestion-${suggestion.status} selected`
                        : `visit-suggestion-card visit-suggestion-${suggestion.status}`
                    }
                    key={suggestion.id}
                  >
                    <div className="item-title-row">
                      <div>
                        <span className="meta-text">
                          {suggestion.adapter_name} - {suggestion.adapter_id}
                        </span>
                        <h4>{displayTaxonomyLabel(suggestion.suggested_label, taxonomyLabels)}</h4>
                        <span className="meta-text">Label: {suggestion.suggested_label}</span>
                        {suggestion.suggested_common_name ||
                        suggestion.suggested_scientific_name ? (
                          <span className="meta-text">
                            {[
                              suggestion.suggested_common_name,
                              suggestion.suggested_scientific_name,
                            ]
                              .filter(Boolean)
                              .join(" / ")}
                          </span>
                        ) : null}
                      </div>
                      <SpeciesSuggestionStatusBadge status={suggestion.status} />
                    </div>
                    <span className="meta-text">{speciesSuggestionStatusCopy(suggestion.status)}</span>
                    <div className="species-suggestion-meta">
                      <span>Rank {suggestion.rank}</span>
                      <span>
                        {formatConfidence(suggestion.confidence)}{" "}
                        {speciesSuggestionMetricLabel(suggestion)}
                      </span>
                      <span>{formatDateTime(suggestion.created_at)}</span>
                    </div>
                    {suggestion.notes ? (
                      <p className="species-suggestion-note">{suggestion.notes}</p>
                    ) : null}
                    {suggestion.status === "pending" || suggestion.status === "accepted" ? (
                      <div className="suggestion-action-stack">
                        <button
                          className="secondary-action"
                          onClick={() => useSpeciesSuggestionAsCorrection(suggestion)}
                          type="button"
                        >
                          Use as correction prefill
                        </button>
                        <span className="field-helper">
                          Prefills only. It does not save truth or change status before correction.
                        </span>
                      </div>
                    ) : (
                      <span className="meta-text">
                        {formatLabel(suggestion.status)} suggestion is read-only here and remains
                        separate from reviewed truth.
                      </span>
                    )}
                  </article>
                ))}
              </div>
            ) : null}
          </section>
          <form className="correction-form" onSubmit={saveCorrection}>
            <TaxonomyLabelInput
              label={isSpeciesVisit ? "Species correction" : "Corrected label"}
              labels={taxonomyLabels}
              value={label}
              onChange={setLabel}
              placeholder={
                isSpeciesVisit ? "reviewed species, unknown_bird, or false_positive" : "confirmed label"
              }
            />
            <label>
              Notes
              <textarea
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
                placeholder="optional review note"
              />
            </label>
            <button className="primary-action" disabled={isSaving} type="submit">
              {isSaving ? "Saving..." : isSpeciesVisit ? "Resolve species" : "Save correction"}
            </button>
          </form>
          <button className="secondary-action" onClick={onOpenExports}>
            Open Dataset Exports
          </button>
          {detail.detection_proposals.length > 0 ? (
            <button className="secondary-action" onClick={onOpenDetectionProposals}>
              Detection Proposals
            </button>
          ) : null}
        </section>
      ) : (
        <section className="panel case-readiness-panel">
          <div>
            <h2>Dataset readiness</h2>
            <p>{detail.review_summary}</p>
          </div>
          <div className="detail-actions">
            <button
              className="primary-action"
              disabled={isSaving || isReopening}
              onClick={beginReviewedRevision}
              type="button"
            >
              Edit identification
            </button>
            <button
              className="secondary-action"
              disabled={isSaving || isReopening}
              onClick={() => void reopenReviewedVisit()}
              type="button"
            >
              {isReopening ? "Reopening..." : "Reopen as needs review"}
            </button>
          </div>
          {isEditingReviewed ? (
            <section className="species-suggestion-review-context">
              <div className="section-heading">
                <div>
                  <h3>Revise reviewed outcome</h3>
                  <span className="meta-text">
                    The current correction stays in history. Saving creates a new reviewed truth.
                  </span>
                </div>
                <EvidenceBadge label="Explicit revision" tone="truth" />
              </div>
              <div className="correction-truth-note">
                <strong>Current reviewed correction</strong>
                <span>
                  {currentCorrection
                    ? `${displayTaxonomyLabel(currentCorrection.label ?? "unknown", taxonomyLabels)} saved ${formatDateTime(currentCorrection.created_at)}.`
                    : "No current correction is available; refresh this Visit before revising it."}
                </span>
              </div>
              <div className="promoted-review-context-grid">
                <ContextItem label="Stream" value={detail.stream.name} />
                <ContextItem
                  label="Zone"
                  value={
                    detail.primary_zone
                      ? `${detail.primary_zone.name} (${formatLabel(detail.primary_zone.zone_type)})`
                      : "Unzoned"
                  }
                />
                <ContextItem label="Visit date and time" value={formatDateTime(detail.event.started_at)} />
                <ContextItem
                  label="Suggestions"
                  value={
                    speciesSuggestions.length > 0
                      ? `${speciesSuggestions.length} evidence-only suggestion${speciesSuggestions.length === 1 ? "" : "s"}`
                      : "No suggestions"
                  }
                />
              </div>
              {detail.evidence_frames.length > 0 ? (
                <VisitEvidenceSequence frames={detail.evidence_frames} />
              ) : detail.media_asset ? (
                <MediaAssetPreview asset={detail.media_asset} />
              ) : (
                <span className="meta-text">No saved evidence frame is attached to this Visit.</span>
              )}
              <p className="evidence-panel-copy">
                Suggestions remain evidence only while revising. They are never accepted or
                promoted automatically.
              </p>
              <form className="correction-form" onSubmit={saveReviewedRevision}>
                <TaxonomyLabelInput
                  label={isSpeciesVisit ? "Revised species or outcome" : "Revised outcome"}
                  labels={taxonomyLabels}
                  value={label}
                  onChange={setLabel}
                  placeholder="supported species, non_bird, blank, ambiguous, or false_positive"
                />
                <label>
                  Revision reason
                  <textarea
                    value={notes}
                    onChange={(event) => setNotes(event.target.value)}
                    placeholder="optional short reason for this change"
                  />
                </label>
                <div className="detail-actions">
                  <button className="primary-action" disabled={isSaving} type="submit">
                    {isSaving ? "Saving..." : "Save revised identification"}
                  </button>
                  <button className="secondary-action" onClick={cancelReviewedRevision} type="button">
                    Cancel
                  </button>
                </div>
              </form>
            </section>
          ) : null}
          <button className="secondary-action" onClick={onOpenExports}>
            Open Dataset Exports
          </button>
          {detail.detection_proposals.length > 0 ? (
            <button className="secondary-action" onClick={onOpenDetectionProposals}>
              Detection Proposals
            </button>
          ) : null}
        </section>
      )}
    </div>
  );
}

function SourceEvidenceTracePanel({
  mediaAsset,
  motionEvidence,
  onOpenEvent,
  onOpenMotionEvidence,
}: {
  mediaAsset?: MediaAsset | null;
  motionEvidence: MotionEvidence;
  onOpenEvent: (eventId: string) => void;
  onOpenMotionEvidence: (motionEvidenceId: string) => void;
}) {
  const webhookProvenance = getWebhookEvidenceProvenance(motionEvidence);

  return (
    <section className="panel source-evidence-trace-panel">
      <div className="section-heading">
        <div>
          <h2>Source evidence trace</h2>
          <span className="meta-text">
            This Visit is linked back to the activity evidence that created review context.
          </span>
        </div>
        <EvidenceBadge label="Evidence trace" tone="evidence" />
      </div>
      <div className="motion-review-context-grid">
        <ContextItem
          label="Advanced evidence"
          value={motionEvidence.id}
          detail={formatLabel(motionEvidence.status)}
        />
        <ContextItem
          label="Promoted Event"
          value={motionEvidence.promoted_event_id ?? "not linked"}
        />
        <ContextItem
          label="Promoted Visit"
          value={motionEvidence.promoted_visit_id ?? "not linked"}
        />
        <ContextItem
          label="Best frame"
          value={motionEvidence.snapshot_media_asset_id ?? mediaAsset?.id ?? "none"}
        />
        <ContextItem label="Stream" value={motionEvidence.stream_id ?? "none"} />
        <ContextItem
          label="Activity area"
          value={motionEvidence.zone_id ?? "Automatic activity area"}
        />
        {webhookProvenance.isWebhook ? (
          <ContextItem
            label="Provider"
            value={webhookProvenance.providerKey ?? "webhook_future"}
            detail="Evidence metadata only"
          />
        ) : null}
      </div>
      <div className="detail-actions">
        <button
          className="secondary-action"
          onClick={() => onOpenMotionEvidence(motionEvidence.id)}
          type="button"
        >
          Open advanced evidence
        </button>
        {motionEvidence.promoted_event_id ? (
          <button
            className="secondary-action"
            onClick={() => onOpenEvent(motionEvidence.promoted_event_id!)}
            type="button"
          >
            Open Event
          </button>
        ) : null}
        <span className="field-helper">
          Correction remains truth after inspecting source evidence.
        </span>
      </div>
    </section>
  );
}

function CorrectionTruthPanel({
  latest,
  older,
  taxonomyLabels,
}: {
  latest: VisitReviewHistoryEntry;
  older: VisitReviewHistoryEntry[];
  taxonomyLabels: TaxonomyLabel[];
}) {
  return (
    <section className="panel correction-truth-panel">
      <div className="section-heading">
        <div>
          <h2>Latest correction truth</h2>
          <span className="meta-text">
            Correction history is the audit trail for analytics and exports.
          </span>
        </div>
        <EvidenceBadge label="Correction truth" tone="truth" />
      </div>
      <div className="correction-truth-latest">
        <strong>{displayTaxonomyLabel(latest.label ?? "unknown", taxonomyLabels)}</strong>
        <span>
          {latest.action} - {formatDateTime(latest.created_at)}
        </span>
        {latest.notes ? <p>{latest.notes}</p> : null}
      </div>
      {older.length > 0 ? (
        <details className="correction-history-details">
          <summary>{older.length} older correction{older.length === 1 ? "" : "s"}</summary>
          <div className="history-list">
            {older.map((entry) => (
              <CorrectionHistoryItem
                key={`${entry.created_at}-${entry.action}-${entry.label ?? ""}`}
                entry={entry}
                taxonomyLabels={taxonomyLabels}
              />
            ))}
          </div>
        </details>
      ) : null}
    </section>
  );
}

function VisitCurationPanel({
  detail,
  onReload,
  onCurationChanged,
  onOpenVisit,
}: {
  detail: VisitDetail;
  onReload: () => Promise<void>;
  onCurationChanged: () => Promise<void>;
  onOpenVisit: (visitId: string) => void;
}) {
  const [isEditingEvidence, setIsEditingEvidence] = useState(false);
  const [retainedIds, setRetainedIds] = useState<string[]>([]);
  const [primaryId, setPrimaryId] = useState<string | null>(null);
  const [splitBoundaryId, setSplitBoundaryId] = useState<string>("");
  const [splitPreview, setSplitPreview] = useState<{
    first: VisitEvidenceFrame[];
    second: VisitEvidenceFrame[];
    stateToken: string;
    implication: string;
  } | null>(null);
  const [mergeCandidates, setMergeCandidates] = useState<
    { id: string; label: string; gapSeconds: number }[]
  >([]);
  const [selectedMergeIds, setSelectedMergeIds] = useState<string[]>([]);
  const [mergePreview, setMergePreview] = useState<{
    frames: VisitEvidenceFrame[];
    stateToken: string;
    implication: string;
  } | null>(null);
  const [zoneId, setZoneId] = useState("");
  const [isLoadingCandidates, setIsLoadingCandidates] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [evidenceKey, setEvidenceKey] = useState<string | null>(null);
  const [splitKey, setSplitKey] = useState<string | null>(null);
  const [mergeKey, setMergeKey] = useState<string | null>(null);
  const [zoneKey, setZoneKey] = useState<string | null>(null);

  useEffect(() => {
    const primary = detail.evidence_frames.find((frame) => frame.is_primary)?.media_asset_id ??
      detail.evidence_frames[0]?.media_asset_id ?? null;
    setRetainedIds(detail.evidence_frames.map((frame) => frame.media_asset_id));
    setPrimaryId(primary);
    setSplitBoundaryId(detail.evidence_frames[0]?.media_asset_id ?? "");
    setSplitPreview(null);
    setMergeCandidates([]);
    setSelectedMergeIds([]);
    setMergePreview(null);
    setZoneId(detail.visit.zone_id ?? detail.primary_zone?.id ?? "");
    setEvidenceKey(null);
    setSplitKey(null);
    setMergeKey(null);
    setZoneKey(null);
  }, [detail.visit.id, detail.review_state_token]);

  const previewFrames = detail.evidence_frames
    .filter((frame) => retainedIds.includes(frame.media_asset_id))
    .map((frame) => ({ ...frame, is_primary: frame.media_asset_id === primaryId }));
  const canSplit = detail.evidence_frames.length >= 2;

  function beginEvidenceEdit() {
    setRetainedIds(detail.evidence_frames.map((frame) => frame.media_asset_id));
    setPrimaryId(
      detail.evidence_frames.find((frame) => frame.is_primary)?.media_asset_id ??
        detail.evidence_frames[0]?.media_asset_id ?? null,
    );
    setEvidenceKey(null);
    setMessage(null);
    setError(null);
    setIsEditingEvidence(true);
  }

  function toggleEvidence(mediaId: string) {
    setRetainedIds((current) => {
      if (current.includes(mediaId)) {
        if (current.length <= 1) {
          return current;
        }
        const next = current.filter((id) => id !== mediaId);
        if (primaryId === mediaId) {
          setPrimaryId(next[0] ?? null);
        }
        return next;
      }
      return detail.evidence_frames
        .map((frame) => frame.media_asset_id)
        .filter((id) => current.includes(id) || id === mediaId);
    });
  }

  async function saveEvidence() {
    if (!primaryId || previewFrames.length === 0) {
      setError("Keep at least one evidence frame and choose its primary frame.");
      return;
    }
    const idempotencyKey = evidenceKey ?? newReviewRequestKey("visit-evidence");
    setEvidenceKey(idempotencyKey);
    setIsSaving(true);
    setError(null);
    try {
      const result = await apiClient.curateVisitEvidence(detail.visit.id, {
        retained_media_asset_ids: previewFrames.map((frame) => frame.media_asset_id),
        primary_media_asset_id: primaryId,
        expected_state_token: detail.review_state_token,
        idempotency_key: idempotencyKey,
      });
      setMessage(result.message);
      setIsEditingEvidence(false);
      setEvidenceKey(null);
      await onReload();
      await onCurationChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not save Visit evidence.");
    } finally {
      setIsSaving(false);
    }
  }

  async function previewSplit() {
    if (!splitBoundaryId) {
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const result = await apiClient.previewVisitSplit(detail.visit.id, {
        boundary_after_media_asset_id: splitBoundaryId,
        expected_state_token: detail.review_state_token,
      });
      setSplitPreview({
        first: result.first.evidence_frames,
        second: result.second.evidence_frames,
        stateToken: result.state_token,
        implication: result.review_implication,
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not preview the split.");
    } finally {
      setIsSaving(false);
    }
  }

  async function saveSplit() {
    if (!splitPreview || !splitBoundaryId) {
      return;
    }
    const idempotencyKey = splitKey ?? newReviewRequestKey("visit-split");
    setSplitKey(idempotencyKey);
    setIsSaving(true);
    setError(null);
    try {
      const result = await apiClient.splitVisit(detail.visit.id, {
        boundary_after_media_asset_id: splitBoundaryId,
        expected_state_token: splitPreview.stateToken,
        idempotency_key: idempotencyKey,
      });
      setMessage(result.message);
      setSplitKey(null);
      await onCurationChanged();
      onOpenVisit(result.resulting_visits[0].id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not split this Visit.");
    } finally {
      setIsSaving(false);
    }
  }

  async function loadMergeCandidates() {
    setIsLoadingCandidates(true);
    setError(null);
    try {
      const result = await apiClient.getVisitMergeCandidates(detail.visit.id);
      setMergeCandidates(
        result.candidates.map((candidate) => ({
          id: candidate.visit.id,
          label: `${formatDateTime(candidate.visit.captured_at)} · ${candidate.visit.zone_name ?? "Zone"}`,
          gapSeconds: candidate.gap_seconds,
        })),
      );
      setSelectedMergeIds([]);
      setMergePreview(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load nearby Visits.");
    } finally {
      setIsLoadingCandidates(false);
    }
  }

  async function previewMerge() {
    if (selectedMergeIds.length === 0) {
      setError("Choose at least one nearby Visit to merge.");
      return;
    }
    setIsSaving(true);
    setError(null);
    try {
      const result = await apiClient.previewVisitMerge(detail.visit.id, {
        candidate_visit_ids: selectedMergeIds,
        expected_state_token: detail.review_state_token,
      });
      setMergePreview({
        frames: result.combined.evidence_frames,
        stateToken: result.state_token,
        implication: result.review_implication,
      });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "These Visits cannot be merged.");
    } finally {
      setIsSaving(false);
    }
  }

  async function saveMerge() {
    if (!mergePreview) {
      return;
    }
    const idempotencyKey = mergeKey ?? newReviewRequestKey("visit-merge");
    setMergeKey(idempotencyKey);
    setIsSaving(true);
    setError(null);
    try {
      const result = await apiClient.mergeVisits(detail.visit.id, {
        candidate_visit_ids: selectedMergeIds,
        expected_state_token: mergePreview.stateToken,
        idempotency_key: idempotencyKey,
      });
      setMessage(result.message);
      setMergeKey(null);
      await onCurationChanged();
      onOpenVisit(result.visit.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not merge these Visits.");
    } finally {
      setIsSaving(false);
    }
  }

  async function saveZone() {
    if (!zoneId || zoneId === (detail.visit.zone_id ?? detail.primary_zone?.id)) {
      return;
    }
    const idempotencyKey = zoneKey ?? newReviewRequestKey("visit-zone");
    setZoneKey(idempotencyKey);
    setIsSaving(true);
    setError(null);
    try {
      const result = await apiClient.reassignVisitZone(detail.visit.id, {
        zone_id: zoneId,
        expected_state_token: detail.review_state_token,
        idempotency_key: idempotencyKey,
      });
      setMessage(result.message);
      setZoneKey(null);
      await onReload();
      await onCurationChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not move this Visit to that Zone.");
    } finally {
      setIsSaving(false);
    }
  }

  if (detail.visit.is_superseded) {
    return (
      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Visit retained in history</h2>
            <span className="meta-text">This original Visit no longer counts as an active observation.</span>
          </div>
          <EvidenceBadge label="Superseded" tone="quiet" />
        </div>
        {detail.resulting_visits.length > 0 ? (
          <div className="detail-actions">
            {detail.resulting_visits.map((visit) => (
              <button className="secondary-action" key={visit.id} onClick={() => onOpenVisit(visit.id)} type="button">
                Open resulting Visit
              </button>
            ))}
          </div>
        ) : null}
        <CurationHistory entries={detail.curation_history} />
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="section-heading">
        <div>
          <h2>Visit curation</h2>
          <span className="meta-text">Structural edits organize evidence; they do not create species truth.</span>
        </div>
        <EvidenceBadge label="Review before truth" tone="evidence" />
      </div>
      {error ? <div className="error-panel compact-error">{error}</div> : null}
      {message ? <div className="notice-panel compact-notice">{message}</div> : null}

      {detail.evidence_frames.length > 0 ? (
        <section className="species-suggestion-review-context">
          <div className="section-heading">
            <div>
              <h3>Edit Visit evidence</h3>
              <span className="meta-text">Removing a frame unlinks it from this Visit; it does not delete the saved media.</span>
            </div>
            {!isEditingEvidence ? (
              <button className="secondary-action" onClick={beginEvidenceEdit} type="button">Edit evidence</button>
            ) : null}
          </div>
          {isEditingEvidence ? (
            <>
              <div className="evidence-list">
                {detail.evidence_frames.map((frame, index) => {
                  const retained = retainedIds.includes(frame.media_asset_id);
                  return (
                    <label className="history-item" key={frame.media_asset_id}>
                      <span>
                        Frame {index + 1} · {formatDateTime(frame.captured_at)}
                      </span>
                      <span className="detail-actions">
                        <input
                          checked={retained}
                          disabled={retained && retainedIds.length === 1}
                          onChange={() => toggleEvidence(frame.media_asset_id)}
                          type="checkbox"
                        />
                        Retain
                        <input
                          checked={retained && primaryId === frame.media_asset_id}
                          disabled={!retained}
                          name="visit-primary-evidence"
                          onChange={() => setPrimaryId(frame.media_asset_id)}
                          type="radio"
                        />
                        Primary
                      </span>
                    </label>
                  );
                })}
              </div>
              {previewFrames.length > 0 ? <VisitEvidenceSequence frames={previewFrames} /> : null}
              <div className="detail-actions">
                <button className="primary-action" disabled={isSaving} onClick={() => void saveEvidence()} type="button">
                  {isSaving ? "Saving..." : "Save evidence"}
                </button>
                <button
                  className="secondary-action"
                  disabled={isSaving}
                  onClick={() => { setIsEditingEvidence(false); setError(null); setMessage("Evidence edits canceled."); }}
                  type="button"
                >
                  Cancel
                </button>
              </div>
            </>
          ) : null}
        </section>
      ) : null}

      {canSplit ? (
        <section className="species-suggestion-review-context">
          <div className="section-heading"><h3>Split Visit</h3></div>
          <label>
            Split after evidence frame
            <select onChange={(event) => { setSplitBoundaryId(event.target.value); setSplitPreview(null); }} value={splitBoundaryId}>
              {detail.evidence_frames.slice(0, -1).map((frame, index) => (
                <option key={frame.media_asset_id} value={frame.media_asset_id}>Frame {index + 1} · {formatDateTime(frame.captured_at)}</option>
              ))}
            </select>
          </label>
          <div className="detail-actions">
            <button className="secondary-action" disabled={isSaving} onClick={() => void previewSplit()} type="button">Preview split</button>
          </div>
          {splitPreview ? (
            <div className="split-grid">
              <div><strong>First Visit · {splitPreview.first.length} frames</strong><VisitEvidenceSequence frames={splitPreview.first} /></div>
              <div><strong>Second Visit · {splitPreview.second.length} frames</strong><VisitEvidenceSequence frames={splitPreview.second} /></div>
              <p className="meta-text">{splitPreview.implication}</p>
              <button className="primary-action" disabled={isSaving} onClick={() => void saveSplit()} type="button">Split Visit</button>
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="species-suggestion-review-context">
        <div className="section-heading">
          <div><h3>Merge nearby Visits</h3><span className="meta-text">Only same-Stream, same-Zone Visits within the server time limit are offered.</span></div>
          <button className="secondary-action" disabled={isLoadingCandidates} onClick={() => void loadMergeCandidates()} type="button">
            {isLoadingCandidates ? "Checking..." : "Find nearby Visits"}
          </button>
        </div>
        {mergeCandidates.map((candidate) => (
          <label className="history-item" key={candidate.id}>
            <input
              checked={selectedMergeIds.includes(candidate.id)}
              onChange={() => { setSelectedMergeIds((current) => current.includes(candidate.id) ? current.filter((id) => id !== candidate.id) : [...current, candidate.id]); setMergePreview(null); }}
              type="checkbox"
            />
            {candidate.label} · {Math.round(candidate.gapSeconds / 60)} min apart
          </label>
        ))}
        {mergeCandidates.length > 0 ? <button className="secondary-action" disabled={isSaving || selectedMergeIds.length === 0} onClick={() => void previewMerge()} type="button">Preview merge</button> : null}
        {mergePreview ? (
          <div>
            <VisitEvidenceSequence frames={mergePreview.frames} />
            <p className="meta-text">{mergePreview.implication}</p>
            <button className="primary-action" disabled={isSaving} onClick={() => void saveMerge()} type="button">Merge Visits</button>
          </div>
        ) : null}
      </section>

      {detail.eligible_zones.length > 0 ? (
        <section className="species-suggestion-review-context">
          <div className="section-heading"><h3>Visit Zone</h3></div>
          <label>
            Activity Zone
            <select onChange={(event) => setZoneId(event.target.value)} value={zoneId}>
              {detail.eligible_zones.map((zone) => <option key={zone.id} value={zone.id}>{zone.name} ({formatLabel(zone.zone_type)})</option>)}
            </select>
          </label>
          <button className="secondary-action" disabled={isSaving || zoneId === (detail.visit.zone_id ?? detail.primary_zone?.id)} onClick={() => void saveZone()} type="button">Save Zone</button>
        </section>
      ) : null}
      <CurationHistory entries={detail.curation_history} />
    </section>
  );
}

function CurationHistory({ entries }: { entries: VisitDetail["curation_history"] }) {
  if (entries.length === 0) {
    return <span className="meta-text">No structural curation history yet.</span>;
  }
  return (
    <div className="history-list">
      {entries.map((entry) => <div className="history-item" key={`${entry.action}-${entry.created_at}`}><strong>{formatLabel(entry.action)}</strong><span>{entry.message} · {formatDateTime(entry.created_at)}</span></div>)}
    </div>
  );
}

function CorrectionHistoryItem({
  entry,
  taxonomyLabels,
}: {
  entry: VisitReviewHistoryEntry;
  taxonomyLabels: TaxonomyLabel[];
}) {
  return (
    <div className="history-item">
      <strong>{displayTaxonomyLabel(entry.label ?? "unknown", taxonomyLabels)}</strong>
      <span>
        {entry.action} - {formatDateTime(entry.created_at)}
        {entry.is_current ? " - Current" : ""}
      </span>
      {entry.notes ? <p>{entry.notes}</p> : null}
    </div>
  );
}

function ContextItem({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string | null;
}) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && detail !== value ? <small>{detail}</small> : null}
    </div>
  );
}

function isSavedPreviewMedia(asset: MediaAsset | null | undefined): boolean {
  const notes = asset?.notes?.toLowerCase() ?? "";
  return (
    notes.includes("saved explicit external_url still-image preview") ||
    notes.includes("provider_key=external_url")
  );
}

function isFolderImportMedia(asset: MediaAsset | null | undefined): boolean {
  const notes = asset?.notes?.toLowerCase() ?? "";
  return (
    notes.includes("provider_key=folder_import_future") ||
    notes.includes("imported explicit folder/trail-cam media as mediaasset only")
  );
}

function formatMediaProvenance(asset: MediaAsset | null | undefined): string {
  if (!asset) {
    return "No attached media is available for this Visit.";
  }
  if (isFolderImportMedia(asset)) {
    const relativePath = extractSafeRelativePath(asset.notes ?? "", "relative_source_path");
    if (relativePath) {
      return `This Visit came from promoted evidence linked to folder-imported local media from ${relativePath}.`;
    }
    return "This Visit came from promoted evidence linked to folder-imported local media.";
  }
  if (isSavedPreviewMedia(asset)) {
    const host = extractSafeNoteValue(asset.notes ?? "", "url_host");
    if (host) {
      return `This Visit came from promoted evidence linked to saved local media from external URL host ${host}.`;
    }
    return "This Visit came from promoted evidence linked to saved local media from an external URL preview.";
  }
  return "This Visit came from promoted evidence linked to saved local media.";
}

interface WebhookEvidenceProvenance {
  isWebhook: boolean;
  providerKey: string | null;
  externalEventId: string | null;
  externalLabel: string | null;
  externalConfidence: string | null;
  externalTimestamp: string | null;
}

function getWebhookEvidenceProvenance(evidence: MotionEvidence): WebhookEvidenceProvenance {
  const providerKey = formatOptionalConfigValue(evidence.scoring_config.provider_key);
  const source = formatOptionalConfigValue(evidence.scoring_config.source);
  return {
    isWebhook: providerKey === "webhook_future" || source === "webhook_metadata_motion_event",
    providerKey,
    externalEventId: formatOptionalConfigValue(evidence.scoring_config.external_event_id),
    externalLabel: formatOptionalConfigValue(evidence.scoring_config.external_label_untrusted),
    externalConfidence: formatOptionalConfigValue(
      evidence.scoring_config.external_confidence_untrusted,
    ),
    externalTimestamp: formatOptionalConfigValue(evidence.scoring_config.external_timestamp),
  };
}

function formatOptionalConfigValue(
  value: string | number | boolean | string[] | null | undefined,
): string | null {
  if (value === undefined || value === null) {
    return null;
  }
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  return String(value);
}

function formatWebhookValue(value: string | null): string {
  return value && value.trim() ? value : "not provided";
}

function extractSafeNoteValue(notes: string, key: string): string | null {
  const prefixes = [`${key}=`, `${key}:`];
  const line = notes
    .split(/\r?\n/)
    .find((entry) => prefixes.some((prefix) => entry.trim().startsWith(prefix)));
  if (!line) {
    return null;
  }

  const trimmed = line.trim();
  const prefix = prefixes.find((entry) => trimmed.startsWith(entry));
  const rawValue = prefix ? trimmed.slice(prefix.length).trim() : "";
  const safeValue = rawValue.replace(/[^A-Za-z0-9.:\[\]-]/g, "").slice(0, 120);
  return safeValue || null;
}

function extractSafeRelativePath(notes: string, key: string): string | null {
  const rawValue = extractRawNoteValue(notes, key);
  if (!rawValue) {
    return null;
  }

  const normalized = rawValue.trim().replace(/\\/g, "/");
  if (
    !normalized ||
    normalized.startsWith("/") ||
    normalized.startsWith("~/") ||
    /^[A-Za-z]:/.test(normalized)
  ) {
    return null;
  }

  const segments = normalized.split("/").filter(Boolean);
  if (segments.length === 0 || segments.some((segment) => segment === "..")) {
    return null;
  }

  return segments
    .map((segment) => segment.replace(/[^A-Za-z0-9._ -]/g, "-").slice(0, 80))
    .join("/")
    .slice(0, 180);
}

function extractRawNoteValue(notes: string, key: string): string | null {
  const prefixes = [`${key}=`, `${key}:`];
  const line = notes
    .split(/\r?\n/)
    .find((entry) => prefixes.some((prefix) => entry.trim().startsWith(prefix)));
  if (!line) {
    return null;
  }

  const trimmed = line.trim();
  const prefix = prefixes.find((entry) => trimmed.startsWith(entry));
  return prefix ? trimmed.slice(prefix.length).trim() : null;
}

function SpeciesSuggestionStatusBadge({ status }: { status: SpeciesSuggestion["status"] }) {
  return <span className={`species-status-badge species-status-${status}`}>{formatLabel(status)}</span>;
}

const speciesSuggestionStatusOrder: Record<SpeciesSuggestion["status"], number> = {
  pending: 0,
  accepted: 1,
  rejected: 2,
  superseded: 3,
};

function compareSpeciesSuggestions(a: SpeciesSuggestion, b: SpeciesSuggestion): number {
  const statusDelta = speciesSuggestionStatusOrder[a.status] - speciesSuggestionStatusOrder[b.status];
  if (statusDelta !== 0) {
    return statusDelta;
  }
  const rankDelta = a.rank - b.rank;
  if (rankDelta !== 0) {
    return rankDelta;
  }
  if (
    a.adapter_id === b.adapter_id &&
    speciesSuggestionMetricLabel(a) === speciesSuggestionMetricLabel(b)
  ) {
    const confidenceDelta = (b.confidence ?? -1) - (a.confidence ?? -1);
    if (confidenceDelta !== 0) {
      return confidenceDelta;
    }
  }
  const recencyDelta = Date.parse(b.created_at) - Date.parse(a.created_at);
  return recencyDelta !== 0 ? recencyDelta : a.id.localeCompare(b.id);
}

function speciesSuggestionStatusCopy(status: SpeciesSuggestion["status"]): string {
  switch (status) {
    case "accepted":
      return "Accepted means helpful evidence; correction still creates truth.";
    case "rejected":
      return "Rejected means dismissed evidence, not a reviewed label.";
    case "superseded":
      return "Superseded means replaced by better evidence or correction.";
    case "pending":
    default:
      return "Pending evidence can prefill the correction form.";
  }
}

function formatConfidence(value?: number | null): string {
  if (typeof value !== "number") {
    return "Unavailable";
  }
  return `${Math.round(value * 100)}%`;
}
