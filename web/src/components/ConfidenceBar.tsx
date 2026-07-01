interface ConfidenceBarProps {
  value: number;
  label?: string;
}

export function ConfidenceBar({ value, label = "Evidence confidence" }: ConfidenceBarProps) {
  const percent = Math.round(Math.max(0, Math.min(1, value)) * 100);

  return (
    <div className="confidence-meter" aria-label={`${label}: ${percent}%`}>
      <div className="confidence-meter-label">
        <span>{label}</span>
        <strong>{percent}%</strong>
      </div>
      <div className="confidence-meter-track">
        <i style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}
