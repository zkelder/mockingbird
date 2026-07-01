interface EvidenceBadgeProps {
  label: string;
  tone?: "evidence" | "truth" | "review" | "quiet";
}

export function EvidenceBadge({ label, tone = "evidence" }: EvidenceBadgeProps) {
  return <span className={`evidence-badge evidence-badge-${tone}`}>{label}</span>;
}
