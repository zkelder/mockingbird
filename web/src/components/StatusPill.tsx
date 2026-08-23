interface StatusPillProps {
  label: string;
  tone?: "good" | "review" | "alert" | "quiet";
}

export function StatusPill({ label, tone = "quiet" }: StatusPillProps) {
  return <span className={`status-pill status-${tone}`}>{label}</span>;
}
