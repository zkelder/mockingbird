import { useEffect, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type { TaxonomyLabel, VisitDetail } from "../api/types";
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
}

export function VisitDetailPage({
  visitId,
  onOpenStream,
  onOpenEvent,
  onOpenExports,
  onOpenDetectionProposals,
  onCorrectionSaved,
}: VisitDetailPageProps) {
  const [detail, setDetail] = useState<VisitDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [taxonomyLabels, setTaxonomyLabels] = useState<TaxonomyLabel[]>([]);
  const [label, setLabel] = useState("");
  const [notes, setNotes] = useState("");

  async function loadDetail(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoading(true);
    }
    setError(null);
    try {
      const nextDetail = await apiClient.getVisitDetail(visitId);
      setDetail(nextDetail);
      setLabel((current) =>
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

  useEffect(() => {
    setMessage(null);
    setLabel("");
    setNotes("");
    void loadDetail();
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
      setMessage(
        `${displayTaxonomyLabel(
          result.review_label.label,
          taxonomyLabels,
        )} will be used as local dataset truth.`,
      );
      await loadDetail({ showLoading: false });
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

      {isMotionEvidenceVisit ? (
        <section className="notice-panel">
          <strong>Promoted Motion Evidence</strong>
          <span>
            This visit came from promoted motion evidence. It is reviewable context only until a
            correction is saved.
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
            <span className="meta-text">Local import reference</span>
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
            <h2>Imported media</h2>
            <span className="meta-text">Local evidence for this visit review</span>
          </div>
          <MediaAssetPreview asset={detail.media_asset} />
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
