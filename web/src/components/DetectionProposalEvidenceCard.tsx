import type { DetectionProposal, DetectionRun, TaxonomyLabel } from "../api/types";
import { formatDateTime, formatLabel } from "../utils";
import { ConfidenceBar } from "./ConfidenceBar";
import { EvidenceBadge } from "./EvidenceBadge";
import { ProposalStatusBadge } from "./ProposalStatusBadge";
import { displayTaxonomyLabel } from "./taxonomy";

interface DetectionProposalEvidenceCardProps {
  proposal: DetectionProposal;
  run?: DetectionRun;
  taxonomyLabels?: TaxonomyLabel[];
  zoneLabel?: string;
  compact?: boolean;
}

export function DetectionProposalEvidenceCard({
  proposal,
  run,
  taxonomyLabels = [],
  zoneLabel,
  compact = false,
}: DetectionProposalEvidenceCardProps) {
  return (
    <article className={compact ? "proposal-evidence-card compact" : "proposal-evidence-card"}>
      <div className="item-title-row">
        <div>
          <span className="meta-text">
            {run ? `${formatLabel(run.source)} source` : "Proposal evidence"} -{" "}
            {formatDateTime(proposal.created_at)}
          </span>
          <h3>{displayTaxonomyLabel(proposal.label, taxonomyLabels)}</h3>
        </div>
        <ProposalStatusBadge status={proposal.status} />
      </div>
      <div className="proposal-truth-strip">
        <EvidenceBadge label="Proposal evidence" />
        <span>Reviewed correction remains dataset truth.</span>
      </div>
      <ConfidenceBar value={proposal.confidence} />
      <div className="detection-proposal-meta">
        <div className="data-row">
          <span>Zone</span>
          <strong>{zoneLabel ?? proposal.zone_id ?? "Unzoned"}</strong>
        </div>
        <div className="data-row">
          <span>Suggested subject/species</span>
          <strong>
            {displayTaxonomyLabel(
              proposal.suggested_species ?? proposal.suggested_subject_label,
              taxonomyLabels,
            )}
          </strong>
        </div>
        <div className="data-row">
          <span>Run</span>
          <strong>{run ? `${formatLabel(run.source)} / ${formatLabel(run.status)}` : proposal.run_id}</strong>
        </div>
      </div>
      {proposal.notes ? <p>{proposal.notes}</p> : null}
    </article>
  );
}
