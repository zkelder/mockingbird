import { useEffect, useState } from "react";
import { apiClient, ApiError } from "../api/client";
import type {
  DoctorCheckResult,
  DoctorOverallStatus,
  DoctorReport,
  DoctorStatus,
} from "../api/types";
import type { Page } from "../navigation";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel } from "../utils";

interface DoctorPageProps {
  onNavigate: (page: Page) => void;
}

/**
 * Product Operations & First-Observation Completion v1: the first
 * authenticated HTTP/UI surface for MockingBird Doctor
 * (`diagnostics/doctor.py`), previously CLI-only (`python -m mockingbird
 * doctor`). A thin presentation over the existing, unmodified engine's own
 * report -- this page invents no new checks, thresholds, or epistemic
 * distinctions; see docs/mockingbird-doctor-operational-health-contract.md
 * "Severity semantics" for the PASS/WARN/FAIL/SKIPPED and blocking/
 * degraded/informational vocabulary this reuses exactly.
 *
 * "Safe recovery actions" here are calm navigation links to the existing,
 * already-safe control surfaces a given check's category maps to (Local
 * Data's storage/backup controls; Cameras for Camera Node checks) -- this
 * page never adds a new mutating control of its own, and the existing
 * "Shut Down MockingBird" action already lives on Local Data, reachable
 * from the Application row below.
 */
export function DoctorPage({ onNavigate }: DoctorPageProps) {
  const [report, setReport] = useState<DoctorReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      const result = await apiClient.getDoctorReport();
      setReport(result);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not check MockingBird's health right now.",
      );
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  if (isLoading && !report) {
    return <div className="panel">Checking MockingBird's health…</div>;
  }

  if (error && !report) {
    return (
      <div className="error-panel">
        <strong>{error}</strong>
        <div className="panel-actions">
          <button className="secondary-action" onClick={() => void load()} type="button">
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!report) {
    return null;
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Diagnostics"
        title="Doctor"
        description="A calm, honest check of whether MockingBird can reliably observe wildlife right now."
        actions={
          <button className="secondary-action" disabled={isLoading} onClick={() => void load()} type="button">
            {isLoading ? "Checking…" : "Refresh"}
          </button>
        }
      />
      {error ? (
        <div className="error-panel">
          <span>Could not refresh just now: {error}</span>
        </div>
      ) : null}
      <section className="panel page-stack">
        <div className="section-heading">
          <h2>Overall</h2>
          <StatusPill label={overallLabel(report.overall_status)} tone={overallTone(report.overall_status)} />
        </div>
        <p>{overallSummary(report.overall_status)}</p>
        <span className="meta-text">
          Checked {formatDateTime(report.generated_at)} ({report.duration_ms.toFixed(0)}ms) — MockingBird{" "}
          {report.app_version}
        </span>
      </section>
      <section className="panel page-stack">
        <h2>Checks</h2>
        {report.checks.map((check) => (
          <DoctorCheckRow check={check} key={check.code} onNavigate={onNavigate} />
        ))}
      </section>
    </div>
  );
}

function overallLabel(status: DoctorOverallStatus): string {
  return { HEALTHY: "Healthy", DEGRADED: "Needs attention", UNHEALTHY: "Not working" }[status];
}

function overallTone(status: DoctorOverallStatus): "good" | "review" | "alert" {
  return { HEALTHY: "good", DEGRADED: "review", UNHEALTHY: "alert" }[status] as "good" | "review" | "alert";
}

function overallSummary(status: DoctorOverallStatus): string {
  return {
    // UI/UX & First-Run Adoption v1: a fresh install passes every check
    // while nothing is set up at all (no detector, no backup, no media), so
    // the old wording ("everything ... is working") overclaimed. Each check
    // below already says honestly when it has nothing to check yet.
    HEALTHY: "Nothing is wrong. Every check below either passed or has nothing to check yet.",
    DEGRADED: "MockingBird is working, but at least one check below could use attention.",
    UNHEALTHY: "MockingBird cannot reliably observe wildlife until at least one check below is fixed.",
  }[status];
}

function checkTone(status: DoctorStatus): "good" | "review" | "alert" | "quiet" {
  return { PASS: "good", WARN: "review", FAIL: "alert", SKIPPED: "quiet" }[status] as
    | "good"
    | "review"
    | "alert"
    | "quiet";
}

function checkLabel(status: DoctorStatus): string {
  return { PASS: "OK", WARN: "Needs attention", FAIL: "Not working", SKIPPED: "Not checked" }[status];
}

// Which existing, already-safe settings surface a non-passing check's own
// category maps to -- calm navigation only, never a new mutating control.
// Every other check code (detector/species/GPU/clock/offline-ingest/
// research-export/acoustic-runtime/media-integrity) has no single obvious
// destination page and relies on its own `user_action` text instead.
const CHECK_RECOVERY_DESTINATION: Partial<Record<string, { page: Page; label: string }>> = {
  storage: { page: "settings", label: "Open Local Data" },
  backup: { page: "settings", label: "Open Local Data" },
  database_connectivity: { page: "settings", label: "Open Local Data" },
  database_schema: { page: "settings", label: "Open Local Data" },
  camera_node: { page: "streams", label: "Open Cameras" },
  camera_node_transport: { page: "streams", label: "Open Cameras" },
};

function DoctorCheckRow({
  check,
  onNavigate,
}: {
  check: DoctorCheckResult;
  onNavigate: (page: Page) => void;
}) {
  const destination = check.status !== "PASS" ? CHECK_RECOVERY_DESTINATION[check.code] : undefined;
  const diagnosticEntries = check.diagnostic_context
    ? Object.entries(check.diagnostic_context).filter(
        ([, value]) => value !== null && value !== undefined && value !== "",
      )
    : [];

  return (
    <article className="doctor-check-row">
      <div className="section-heading">
        <strong>{check.component}</strong>
        <StatusPill label={checkLabel(check.status)} tone={checkTone(check.status)} />
      </div>
      <p>{check.summary}</p>
      {check.detail ? <p className="meta-text">{check.detail}</p> : null}
      {check.user_action ? (
        <div className="continuity-message">
          <span>
            <strong>What to do:</strong> {check.user_action}
          </span>
        </div>
      ) : null}
      {destination ? (
        <div className="panel-actions">
          <button className="secondary-action" onClick={() => onNavigate(destination.page)} type="button">
            {destination.label}
          </button>
        </div>
      ) : null}
      {diagnosticEntries.length > 0 ? (
        <details className="review-diagnostic-details">
          <summary>Advanced diagnostics</summary>
          <div className="review-diagnostic-grid">
            {diagnosticEntries.map(([key, value]) => (
              <span key={key}>
                {formatLabel(key)}: {typeof value === "object" ? JSON.stringify(value) : String(value)}
              </span>
            ))}
          </div>
        </details>
      ) : null}
    </article>
  );
}
