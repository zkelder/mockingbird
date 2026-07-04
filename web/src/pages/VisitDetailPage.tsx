import { useEffect, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type {
  MediaAsset,
  MotionEvidence,
  SpeciesSuggestion,
  TaxonomyLabel,
  VisitDetail,
} from "../api/types";
import { DetectionEvidenceCard } from "../components/DetectionEvidenceCard";
import { DetectionProposalEvidenceCard } from "../components/DetectionProposalEvidenceCard";
import { EvidenceBadge } from "../components/EvidenceBadge";
import { MediaAssetPreview } from "../components/MediaAssetPreview";
import { StatusPill } from "../components/StatusPill";
import { TaxonomyLabelInput } from "../components/TaxonomyLabelInput";
import { TaxonomyBadge } from "../components/TaxonomyBadge";
import { displayTaxonomyLabel, findTaxonomyLabel, isBirdReviewLabel } from "../components/taxonomy";
import { formatDateTime, formatLabel } from "../utils";

interface VisitDetailPageProps {
  visitId: string;
  onOpenStream: (streamId: string) => void;
  onOpenEvent: (eventId: string) => void;
  onOpenExports: () => void;
  onOpenDetectionProposals: () => void;
  onCorrectionSaved: () => Promise<void>;
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

export function VisitDetailPage({
  visitId,
  onOpenStream,
  onOpenEvent,
  onOpenExports,
  onOpenDetectionProposals,
  onCorrectionSaved,
  correctionPrefill,
}: VisitDetailPageProps) {
  const [detail, setDetail] = useState<VisitDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [speciesSuggestions, setSpeciesSuggestions] = useState<SpeciesSuggestion[]>([]);
  const [isLoadingSpeciesSuggestions, setIsLoadingSpeciesSuggestions] = useState(true);
  const [speciesSuggestionError, setSpeciesSuggestionError] = useState<string | null>(null);
  const [correctionSuggestionId, setCorrectionSuggestionId] = useState<string | null>(null);
  const [dismissedPrefillId, setDismissedPrefillId] = useState<string | null>(null);
  const [mockSuggestedLabel, setMockSuggestedLabel] = useState("");
  const [isCreatingMockSuggestion, setIsCreatingMockSuggestion] = useState(false);
  const [taxonomyLabels, setTaxonomyLabels] = useState<TaxonomyLabel[]>([]);
  const [label, setLabel] = useState("");
  const [notes, setNotes] = useState("");
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

  useEffect(() => {
    setDismissedPrefillId(null);
    if (incomingCorrectionPrefill?.speciesSuggestionId) {
      setMessage(null);
    }
    setLabel(incomingCorrectionPrefill?.label ?? "");
    setNotes("");
    setMockSuggestedLabel("");
    setCorrectionSuggestionId(incomingCorrectionPrefill?.speciesSuggestionId ?? null);
    void loadDetail({ prefillLabel: incomingCorrectionPrefill?.label });
  }, [visitId, incomingCorrectionPrefill?.speciesSuggestionId]);

  useEffect(() => {
    setMessage(null);
  }, [visitId]);

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

  if (isLoading) {
    return <div className="panel">Loading visit detail...</div>;
  }

  if (error || !detail) {
    return <div className="error-panel">{error ?? "Visit detail is unavailable."}</div>;
  }

  const visitLabel = detail.visit.reviewed_label ?? detail.visit.species_guess ?? detail.visit.subject_label;
  const runById = new Map(detail.detection_runs.map((run) => [run.id, run]));
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
          ?.suggested_label ?? activeCorrectionPrefill?.label ?? "",
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
          <strong>Promoted Motion Evidence</strong>
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
                label="MotionEvidence"
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

      <section className="panel species-review-panel">
        <div className="section-heading">
          <div>
            <h2>{isSpeciesVisit ? "Species review" : "Review correction"}</h2>
            <span className="meta-text">
              Detection evidence is only a suggestion. Corrected species is local dataset truth.
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
            {detail.review_labels.length === 0 ? (
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
            <h2>Proposal provenance</h2>
            <EvidenceBadge label="Evidence source" />
          </div>
          <p className="evidence-panel-copy">
            This visit started as proposal evidence. Use the correction form to set dataset truth;
            the proposal remains supporting evidence.
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
            <h2>Detections as evidence</h2>
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
            {detail.review_labels.map((reviewLabel) => (
              <div className="history-item" key={reviewLabel.id}>
                <strong>{displayTaxonomyLabel(reviewLabel.label, taxonomyLabels)}</strong>
                <span>
                  {formatLabel(reviewLabel.target_type)} correction -{" "}
                  {formatDateTime(reviewLabel.created_at)}
                </span>
                {reviewLabel.notes ? <p>{reviewLabel.notes}</p> : null}
              </div>
            ))}
            {detail.review_labels.length === 0 ? (
              <span className="meta-text">No correction history yet.</span>
            ) : null}
          </div>
        </div>
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
                      <span>{formatConfidence(suggestion.confidence)}</span>
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

function formatOptionalConfigValue(value: string | number | boolean | undefined): string | null {
  if (value === undefined || value === null) {
    return null;
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
  const confidenceDelta = (b.confidence ?? -1) - (a.confidence ?? -1);
  if (confidenceDelta !== 0) {
    return confidenceDelta;
  }
  return Date.parse(b.created_at) - Date.parse(a.created_at);
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
    return "No confidence";
  }
  return `${Math.round(value * 100)}% confidence`;
}
