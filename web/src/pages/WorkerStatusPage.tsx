import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type {
  ExternalUrlWorkerDryRunItem,
  ExternalUrlWorkerDryRunResponse,
  WorkerStatusItem,
  WorkerStatusResponse,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel } from "../utils";

type WorkerCreateFlagKey =
  | "can_create_media_assets"
  | "can_create_motion_evidence"
  | "can_create_events"
  | "can_create_visits"
  | "can_create_review_labels"
  | "can_create_truth";

const createFlagLabels: Array<[WorkerCreateFlagKey, string]> = [
  ["can_create_media_assets", "MediaAssets"],
  ["can_create_motion_evidence", "MotionEvidence"],
  ["can_create_events", "Events"],
  ["can_create_visits", "Visits"],
  ["can_create_review_labels", "ReviewLabels"],
  ["can_create_truth", "Truth"],
];

type DryRunFlagKey =
  | "would_fetch"
  | "would_create_media_asset"
  | "would_create_motion_evidence"
  | "would_create_event"
  | "would_create_visit"
  | "would_create_review_label"
  | "would_create_truth";

const dryRunFlagLabels: Array<[DryRunFlagKey, string]> = [
  ["would_fetch", "Fetch"],
  ["would_create_media_asset", "MediaAsset"],
  ["would_create_motion_evidence", "MotionEvidence"],
  ["would_create_event", "Event"],
  ["would_create_visit", "Visit"],
  ["would_create_review_label", "ReviewLabel"],
  ["would_create_truth", "Truth"],
];

function yesNo(value: boolean): string {
  return value ? "Yes" : "No";
}

function WorkerWarnings({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) {
    return null;
  }

  return (
    <div className="worker-warning-list">
      {warnings.map((warning) => (
        <span key={warning}>{warning}</span>
      ))}
    </div>
  );
}

function WorkerStatusCard({ worker }: { worker: WorkerStatusItem }) {
  return (
    <article className="worker-status-card">
      <div className="section-heading">
        <div>
          <h3>{worker.display_name}</h3>
          <span className="meta-text">{worker.worker_key}</span>
        </div>
        <StatusPill label={formatLabel(worker.state)} tone="quiet" />
      </div>

      <p>{worker.message}</p>

      <div className="worker-status-grid">
        <div>
          <span>Category</span>
          <strong>{formatLabel(worker.category)}</strong>
        </div>
        <div>
          <span>Provider</span>
          <strong>{worker.provider_key ?? "None"}</strong>
        </div>
        <div>
          <span>Implemented</span>
          <strong>{yesNo(worker.implemented)}</strong>
        </div>
        <div>
          <span>Enabled</span>
          <strong>{yesNo(worker.enabled)}</strong>
        </div>
        <div>
          <span>Source</span>
          <strong>{worker.source_id ?? "None"}</strong>
        </div>
        <div>
          <span>Stream</span>
          <strong>{worker.stream_id ?? "None"}</strong>
        </div>
        <div>
          <span>Last run</span>
          <strong>{worker.last_run_at ? formatDateTime(worker.last_run_at) : "Never"}</strong>
        </div>
        <div>
          <span>Next run</span>
          <strong>{worker.next_run_at ? formatDateTime(worker.next_run_at) : "None"}</strong>
        </div>
      </div>

      <div className="worker-create-flag-grid">
        {createFlagLabels.map(([key, label]) => (
          <div key={key}>
            <span>{label}</span>
            <strong>{yesNo(Boolean(worker[key]))}</strong>
          </div>
        ))}
      </div>

      <div className="notice-panel compact-notice worker-truth-note">
        <strong>Create/truth flags are false</strong>
        <span>{worker.last_error ?? "No worker runtime exists for this placeholder."}</span>
      </div>

      <WorkerWarnings warnings={worker.warnings} />
    </article>
  );
}

function WorkerDryRunPlanItem({ item }: { item: ExternalUrlWorkerDryRunItem }) {
  return (
    <article className="worker-dry-run-card">
      <div className="section-heading">
        <div>
          <h3>{item.source_name}</h3>
          <span className="meta-text">{item.source_id}</span>
        </div>
        <StatusPill label={item.eligible ? "Eligible" : "Ineligible"} tone={item.eligible ? "good" : "quiet"} />
      </div>

      <div className="worker-status-grid">
        <div>
          <span>State</span>
          <strong>{formatLabel(item.state)}</strong>
        </div>
        <div>
          <span>Provider</span>
          <strong>{item.provider_key}</strong>
        </div>
        <div>
          <span>Worker</span>
          <strong>{item.worker_key}</strong>
        </div>
        <div>
          <span>Eligible</span>
          <strong>{yesNo(item.eligible)}</strong>
        </div>
      </div>

      <div className="worker-create-flag-grid">
        {dryRunFlagLabels.map(([key, label]) => (
          <div key={key}>
            <span>{label}</span>
            <strong>{yesNo(Boolean(item[key]))}</strong>
          </div>
        ))}
      </div>

      <WorkerWarnings warnings={item.reasons} />
      <WorkerWarnings warnings={item.warnings} />
    </article>
  );
}

function ExternalUrlDryRunPlanSection({
  dryRunPlan,
  error,
  isLoading,
  onRetry,
}: {
  dryRunPlan: ExternalUrlWorkerDryRunResponse | null;
  error: string | null;
  isLoading: boolean;
  onRetry: () => void;
}) {
  if (isLoading) {
    return <section className="panel worker-status-summary">Loading external URL dry-run plan...</section>;
  }

  if (error) {
    return (
      <section className="error-panel">
        <strong>External URL dry-run plan is unavailable.</strong>
        <span>{error}</span>
        <button className="secondary-action" onClick={onRetry} type="button">
          Retry dry-run plan
        </button>
      </section>
    );
  }

  if (!dryRunPlan) {
    return <section className="panel worker-status-summary">External URL dry-run plan is unavailable.</section>;
  }

  return (
    <section className="panel worker-dry-run-panel">
      <div className="section-heading">
        <div>
          <h2>External URL dry-run plan</h2>
          <span className="meta-text">Generated {formatDateTime(dryRunPlan.generated_at)}</span>
        </div>
        <StatusPill
          label={dryRunPlan.read_only && dryRunPlan.dry_run ? "Dry run" : "Check status"}
          tone="good"
        />
      </div>

      <div className="notice-panel compact-notice worker-truth-note">
        <strong>Dry run only</strong>
        <span>No fetches or records are created. Future scheduler is disabled.</span>
      </div>

      <div className="worker-status-grid">
        <div>
          <span>Worker</span>
          <strong>{dryRunPlan.worker_key}</strong>
        </div>
        <div>
          <span>Provider</span>
          <strong>{dryRunPlan.provider_key}</strong>
        </div>
        <div>
          <span>Read-only</span>
          <strong>{yesNo(dryRunPlan.read_only)}</strong>
        </div>
        <div>
          <span>Dry run</span>
          <strong>{yesNo(dryRunPlan.dry_run)}</strong>
        </div>
      </div>

      <section className="metric-grid">
        <MetricCard
          label="Sources"
          value={dryRunPlan.summary.total_sources_considered}
          detail="external_url"
        />
        <MetricCard label="Eligible" value={dryRunPlan.summary.eligible_sources} detail="configured" />
        <MetricCard label="Ineligible" value={dryRunPlan.summary.ineligible_sources} detail="needs config" />
        <MetricCard label="Would fetch" value={dryRunPlan.summary.would_fetch_count} detail="must stay zero" />
      </section>

      <section className="metric-grid">
        <MetricCard
          label="MediaAssets"
          value={dryRunPlan.summary.would_create_media_asset_count}
          detail="would create"
        />
        <MetricCard
          label="MotionEvidence"
          value={dryRunPlan.summary.would_create_motion_evidence_count}
          detail="would create"
        />
        <MetricCard
          label="Truth"
          value={dryRunPlan.summary.would_create_truth_count}
          detail="would create"
        />
        <MetricCard label="Read-only" value={yesNo(dryRunPlan.read_only)} detail="plan route" />
      </section>

      <WorkerWarnings warnings={dryRunPlan.summary.warnings} />

      <div className="worker-dry-run-list">
        {dryRunPlan.items.length > 0 ? (
          dryRunPlan.items.map((item) => (
            <WorkerDryRunPlanItem key={`${item.worker_key}:${item.source_id}`} item={item} />
          ))
        ) : (
          <EmptyState
            title="No external URL sources"
            description="The dry-run plan considers external_url Sources only."
          />
        )}
      </div>
    </section>
  );
}

export function WorkerStatusPage() {
  const [status, setStatus] = useState<WorkerStatusResponse | null>(null);
  const [dryRunPlan, setDryRunPlan] = useState<ExternalUrlWorkerDryRunResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isDryRunLoading, setIsDryRunLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dryRunError, setDryRunError] = useState<string | null>(null);

  async function loadStatus(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoading(true);
    }
    setError(null);
    try {
      setStatus(await apiClient.getWorkerStatus());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load worker status.");
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  }

  async function loadDryRunPlan(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsDryRunLoading(true);
    }
    setDryRunError(null);
    try {
      setDryRunPlan(await apiClient.getExternalUrlWorkerDryRunPlan());
    } catch (caught) {
      setDryRunError(caught instanceof Error ? caught.message : "Could not load dry-run plan.");
    } finally {
      if (showLoading) {
        setIsDryRunLoading(false);
      }
    }
  }

  useEffect(() => {
    void loadStatus();
    void loadDryRunPlan();
  }, []);

  const allCreateFlagsFalse = useMemo(() => {
    if (!status) {
      return false;
    }
    return status.workers.every((worker) =>
      createFlagLabels.every(([key]) => worker[key] === false),
    );
  }, [status]);

  if (isLoading) {
    return <div className="panel">Loading worker status...</div>;
  }

  if (error) {
    return (
      <div className="error-panel">
        <strong>Worker status is unavailable.</strong>
        <span>{error}</span>
        <button className="secondary-action" onClick={() => void loadStatus()} type="button">
          Retry
        </button>
      </div>
    );
  }

  if (!status) {
    return <div className="panel">Worker status is unavailable.</div>;
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Future automation"
        title="Worker Status"
        description="Future automation status only. No workers run from this page."
        actions={
          <button
            className="secondary-action"
            onClick={() => {
              void loadStatus({ showLoading: false });
              void loadDryRunPlan({ showLoading: false });
            }}
            type="button"
          >
            Refresh status
          </button>
        }
      />

      <section className="notice-panel worker-status-boundary">
        <strong>Read-only status contract</strong>
        <span>No worker runtime, provider execution, media creation, evidence creation, or truth writes.</span>
      </section>

      <section className="metric-grid">
        <MetricCard label="Workers" value={status.summary.total_workers} detail="future placeholders" />
        <MetricCard
          label="Implemented"
          value={status.summary.implemented_workers}
          detail="runtime workers"
        />
        <MetricCard label="Enabled" value={status.summary.enabled_workers} detail="configured to run" />
        <MetricCard
          label="Truth creators"
          value={status.summary.truth_creating_workers}
          detail="must stay zero"
        />
      </section>

      <section className="metric-grid">
        <MetricCard label="Running" value={status.summary.running_workers} detail="active workers" />
        <MetricCard label="Failed" value={status.summary.failed_workers} detail="failed workers" />
        <MetricCard label="Read-only" value={yesNo(status.read_only)} detail="status route" />
        <MetricCard label="Create flags" value={allCreateFlagsFalse ? "False" : "Check"} detail="all workers" />
      </section>

      <section className="panel worker-status-summary">
        <div className="section-heading">
          <div>
            <h2>Status summary</h2>
            <span className="meta-text">Generated {formatDateTime(status.generated_at)}</span>
          </div>
          <StatusPill label={status.read_only ? "Read-only" : "Check status"} tone="good" />
        </div>
        <WorkerWarnings warnings={status.summary.warnings} />
      </section>

      <ExternalUrlDryRunPlanSection
        dryRunPlan={dryRunPlan}
        error={dryRunError}
        isLoading={isDryRunLoading}
        onRetry={() => void loadDryRunPlan()}
      />

      <section className="worker-status-list">
        {status.workers.length > 0 ? (
          status.workers.map((worker) => (
            <WorkerStatusCard key={worker.worker_key} worker={worker} />
          ))
        ) : (
          <EmptyState
            title="No worker placeholders"
            description="Worker visibility starts with future placeholder status before runtime work."
          />
        )}
      </section>
    </div>
  );
}
