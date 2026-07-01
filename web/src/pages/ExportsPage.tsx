import type { DatasetExport } from "../api/types";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel } from "../utils";

interface ExportsPageProps {
  exports: DatasetExport[];
}

export function ExportsPage({ exports }: ExportsPageProps) {
  return (
    <div className="page-stack">
      <div className="section-heading">
        <h1>Dataset Exports</h1>
      </div>
      <div className="panel">
        <div className="table-like">
          {exports.map((datasetExport) => (
            <div className="table-row" key={datasetExport.id}>
              <div>
                <strong>{datasetExport.name}</strong>
                <span>Local reviewed data from corrected events and visits</span>
              </div>
              <span>{datasetExport.record_count} records</span>
              <span>{formatDateTime(datasetExport.created_at)}</span>
              <StatusPill
                label={formatLabel(datasetExport.status)}
                tone={datasetExport.status === "ready" ? "good" : "quiet"}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
