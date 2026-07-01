import type { DetectionProposalStatus } from "../api/types";
import { formatLabel } from "../utils";
import { EvidenceBadge } from "./EvidenceBadge";

interface ProposalStatusBadgeProps {
  status: DetectionProposalStatus;
}

export function ProposalStatusBadge({ status }: ProposalStatusBadgeProps) {
  const tone = status === "rejected" ? "quiet" : status === "proposed" ? "review" : "truth";
  const suffix =
    status === "proposed"
      ? "needs decision"
      : status === "rejected"
        ? "dismissed"
        : "review case created";

  return <EvidenceBadge label={`${formatLabel(status)} - ${suffix}`} tone={tone} />;
}
