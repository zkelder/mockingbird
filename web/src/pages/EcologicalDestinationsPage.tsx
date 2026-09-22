import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type {
  EcologicalDestinationInfo,
  EcologicalDestinationKey,
  EcologicalEligibilityPreviewResponse,
  EcologicalLocationChoice,
  EcologicalMediaPolicy,
  EcologicalSubmissionRecord,
  ExportEcologicalSubmissionsResponse,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { MetricCard } from "../components/MetricCard";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel } from "../utils";

interface EcologicalDestinationsPageProps {
  onOpenVisit: (visitId: string) => void;
}

function statusTone(status: string): "good" | "review" | "alert" | "quiet" {
  if (status === "eligible" || status === "prepared" || status === "exported" || status === "submitted") {
    return "good";
  }
  if (status === "needs_input") {
    return "review";
  }
  if (status === "excluded") {
    return "quiet";
  }
  return "quiet";
}

function reasonSentence(reasons: string[]): string {
  return reasons.map(formatLabel).join("; ");
}

export function EcologicalDestinationsPage({ onOpenVisit }: EcologicalDestinationsPageProps) {
  const [destinations, setDestinations] = useState<EcologicalDestinationInfo[] | null>(null);
  const [destination, setDestination] = useState<EcologicalDestinationKey>("inaturalist");
  const [startAt, setStartAt] = useState("");
  const [endAt, setEndAt] = useState("");

  const [preview, setPreview] = useState<EcologicalEligibilityPreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [selectedVisitIds, setSelectedVisitIds] = useState<Set<string>>(new Set());

  const [locationChoice, setLocationChoice] = useState<EcologicalLocationChoice>("none");
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [placeName, setPlaceName] = useState("");
  const [mediaPolicy, setMediaPolicy] = useState<EcologicalMediaPolicy>("none");
  const [mediaAssetId, setMediaAssetId] = useState("");

  const [prepareLoading, setPrepareLoading] = useState(false);
  const [prepareError, setPrepareError] = useState<string | null>(null);
  const [prepareMessage, setPrepareMessage] = useState<string | null>(null);

  const [submissions, setSubmissions] = useState<EcologicalSubmissionRecord[]>([]);
  const [selectedSubmissionIds, setSelectedSubmissionIds] = useState<Set<string>>(new Set());
  const [exportLoading, setExportLoading] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportResult, setExportResult] = useState<ExportEcologicalSubmissionsResponse | null>(null);

  const [resultDrafts, setResultDrafts] = useState<Record<string, { externalId: string; externalUrl: string }>>({});
  const [recordingResultId, setRecordingResultId] = useState<string | null>(null);

  async function loadDestinations() {
    try {
      setDestinations(await apiClient.getEcologicalDestinations());
    } catch (caught) {
      setPreviewError(caught instanceof Error ? caught.message : "Could not load destinations.");
    }
  }

  async function loadSubmissions() {
    try {
      setSubmissions(await apiClient.listEcologicalSubmissions({ destination }));
    } catch {
      // Non-fatal: the prepared-submissions list is a convenience view: an
      // eligibility preview and prepare can both still proceed offline-safe
      // from already-local data even if this refresh fails.
    }
  }

  useEffect(() => {
    void loadDestinations();
  }, []);

  useEffect(() => {
    void loadSubmissions();
    setSelectedVisitIds(new Set());
    setPreview(null);
  }, [destination]);

  const activeDestination = useMemo(
    () => destinations?.find((entry) => entry.key === destination) ?? null,
    [destinations, destination],
  );

  async function runPreview() {
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const result = await apiClient.previewEcologicalEligibility({
        destination,
        filters: {
          start_at: startAt ? new Date(startAt).toISOString() : null,
          end_at: endAt ? new Date(endAt).toISOString() : null,
        },
      });
      setPreview(result);
      setSelectedVisitIds(new Set(result.items.filter((item) => item.status !== "excluded").map((item) => item.visit_id)));
    } catch (caught) {
      setPreviewError(caught instanceof Error ? caught.message : "Could not preview eligibility.");
    } finally {
      setPreviewLoading(false);
    }
  }

  function toggleVisitSelection(visitId: string) {
    setSelectedVisitIds((current) => {
      const next = new Set(current);
      if (next.has(visitId)) {
        next.delete(visitId);
      } else {
        next.add(visitId);
      }
      return next;
    });
  }

  async function prepareSelected() {
    if (selectedVisitIds.size === 0 || !activeDestination?.offered) {
      return;
    }
    let parsedLatitude: number | null = null;
    let parsedLongitude: number | null = null;
    if (locationChoice !== "none") {
      // An empty string coerces to 0 via Number(), which would silently
      // submit a real (0, 0) coordinate rather than the honest "no location
      // supplied yet" this ought to be -- require a real, non-empty value.
      parsedLatitude = latitude.trim() === "" ? NaN : Number(latitude);
      parsedLongitude = longitude.trim() === "" ? NaN : Number(longitude);
      if (!Number.isFinite(parsedLatitude) || !Number.isFinite(parsedLongitude)) {
        setPrepareError("Enter a real latitude and longitude, or choose \"No location\".");
        return;
      }
    }
    setPrepareLoading(true);
    setPrepareError(null);
    setPrepareMessage(null);
    try {
      const records = await apiClient.prepareEcologicalSubmissions({
        visit_ids: Array.from(selectedVisitIds),
        destination,
        location: {
          choice: locationChoice,
          latitude: parsedLatitude,
          longitude: parsedLongitude,
          place_name: placeName.trim() ? placeName.trim() : null,
        },
        media: {
          policy: mediaPolicy,
          media_asset_id: mediaPolicy === "none" ? null : mediaAssetId.trim() || null,
        },
      });
      const readyCount = records.filter((record) => record.status === "prepared").length;
      setPrepareMessage(
        `Prepared ${records.length} record(s) for ${activeDestination.display_name} — `
          + `${readyCount} ready, ${records.length - readyCount} need attention.`,
      );
      await loadSubmissions();
    } catch (caught) {
      setPrepareError(caught instanceof Error ? caught.message : "Could not prepare the selected observations.");
    } finally {
      setPrepareLoading(false);
    }
  }

  function toggleSubmissionSelection(submissionId: string) {
    setSelectedSubmissionIds((current) => {
      const next = new Set(current);
      if (next.has(submissionId)) {
        next.delete(submissionId);
      } else {
        next.add(submissionId);
      }
      return next;
    });
  }

  async function exportSelected() {
    if (selectedSubmissionIds.size === 0) {
      return;
    }
    const locationSummary = locationChoice === "none" ? "No location" : `${locationChoice} location`;
    const confirmed = window.confirm(
      `Prepare a file for ${activeDestination?.display_name ?? destination} with `
        + `${selectedSubmissionIds.size} record(s)?\n\n`
        + `Location: ${locationSummary}\nMedia: ${mediaPolicy === "none" ? "None" : "Reference only, no photo bytes"}\n\n`
        + "This writes a local file only — MockingBird never submits it anywhere on its own. "
        + "You still upload it yourself.",
    );
    if (!confirmed) {
      return;
    }
    setExportLoading(true);
    setExportError(null);
    setExportResult(null);
    try {
      const result = await apiClient.exportEcologicalSubmissions({
        submission_ids: Array.from(selectedSubmissionIds),
      });
      setExportResult(result);
      await loadSubmissions();
    } catch (caught) {
      setExportError(caught instanceof Error ? caught.message : "Could not export the selected submissions.");
    } finally {
      setExportLoading(false);
    }
  }

  async function submitResult(submissionId: string) {
    const draft = resultDrafts[submissionId];
    if (!draft?.externalId && !draft?.externalUrl) {
      return;
    }
    setRecordingResultId(submissionId);
    try {
      await apiClient.recordEcologicalSubmissionResult(submissionId, {
        external_id: draft.externalId.trim() || null,
        external_url: draft.externalUrl.trim() || null,
      });
      await loadSubmissions();
    } catch (caught) {
      setExportError(caught instanceof Error ? caught.message : "Could not record the submission result.");
    } finally {
      setRecordingResultId(null);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Reviewed truth, leaving on your terms"
        title="Ecological Destinations"
        description="Prepare your reviewed observations for an external ecological service. Nothing leaves this Host until you explicitly export it, and MockingBird never submits anything on its own."
      />

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Destination</h2>
            <span className="meta-text">Choose where you want to prepare observations for.</span>
          </div>
        </div>
        <div className="detail-actions">
          {(destinations ?? []).map((entry) => (
            <button
              className={entry.key === destination ? "primary-action" : "secondary-action"}
              disabled={!entry.offered}
              key={entry.key}
              onClick={() => setDestination(entry.key)}
              title={entry.offered_reason ?? undefined}
              type="button"
            >
              {entry.display_name}
              {!entry.offered ? " (not offered)" : ""}
            </button>
          ))}
        </div>
        {(destinations ?? [])
          .filter((entry) => !entry.offered)
          .map((entry) => (
            // Shown for every not-offered destination unconditionally -- not
            // gated on it being the currently-selected one, since a disabled
            // destination button can never actually become selected. A
            // curious user asking "why can't I use eBird" deserves a real,
            // persistently visible answer, not one hidden behind a hover-only
            // title tooltip on a button they can't click (Phase 23).
            <div className="notice-panel" key={entry.key}>
              <strong>{entry.display_name} is not offered</strong>
              <span>{entry.offered_reason}</span>
            </div>
          ))}
      </section>

      {activeDestination?.offered ? (
        <>
          <section className="panel">
            <div className="section-heading">
              <div>
                <h2>1. Preview eligibility</h2>
                <span className="meta-text">
                  See exactly which Reviewed observations qualify before anything is prepared.
                </span>
              </div>
            </div>
            <div className="manifest-export-form">
              <label>
                From
                <input onChange={(event) => setStartAt(event.target.value)} type="date" value={startAt} />
              </label>
              <label>
                To
                <input onChange={(event) => setEndAt(event.target.value)} type="date" value={endAt} />
              </label>
            </div>
            <div className="detail-actions">
              <button className="primary-action" disabled={previewLoading} onClick={() => void runPreview()} type="button">
                {previewLoading ? "Checking..." : "Preview eligibility"}
              </button>
            </div>
            {previewError ? <div className="error-panel">{previewError}</div> : null}

            {preview ? (
              <>
                <section className="metric-grid">
                  <MetricCard label="Ready" value={preview.eligible_count} />
                  <MetricCard label="Need attention" value={preview.needs_input_count} />
                  <MetricCard label="Excluded" value={preview.excluded_count} />
                </section>
                {preview.items.length > 0 ? (
                  <div className="manifest-file-list" role="table" aria-label="Ecological eligibility preview">
                    <div className="manifest-file-row manifest-file-head" role="row">
                      <span role="columnheader">Select</span>
                      <span role="columnheader">Observation</span>
                      <span role="columnheader">Status</span>
                      <span role="columnheader">Why</span>
                    </div>
                    {preview.items.map((item) => (
                      <div className="manifest-file-row" key={item.visit_id} role="row">
                        <span role="cell">
                          <input
                            checked={selectedVisitIds.has(item.visit_id)}
                            disabled={item.status === "excluded"}
                            onChange={() => toggleVisitSelection(item.visit_id)}
                            type="checkbox"
                          />
                        </span>
                        <span role="cell">
                          <button className="text-action" onClick={() => onOpenVisit(item.visit_id)} type="button">
                            {item.taxon_display_name ?? formatLabel(item.classification)}
                          </button>
                          <br />
                          <small>{formatDateTime(item.captured_at)}</small>
                        </span>
                        <span role="cell">
                          <StatusPill label={formatLabel(item.status)} tone={statusTone(item.status)} />
                        </span>
                        <span role="cell">
                          {reasonSentence([...item.needs_input_reasons, ...item.excluded_reasons]) || "—"}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    title="Nothing in range"
                    description="No Visits match this date range yet."
                  />
                )}
              </>
            ) : null}
          </section>

          <section className="panel">
            <div className="section-heading">
              <div>
                <h2>2. Location and media</h2>
                <span className="meta-text">
                  Explicit every time — never reused from your weather/environment coordinate.
                </span>
              </div>
            </div>
            <div className="manifest-export-form">
              <label>
                Location
                <select
                  onChange={(event) => setLocationChoice(event.target.value as EcologicalLocationChoice)}
                  value={locationChoice}
                >
                  <option value="none">No location</option>
                  <option value="coarse">Approximate (shared as "obscured" where the destination supports it)</option>
                  <option value="exact">Exact coordinate</option>
                </select>
              </label>
              {locationChoice !== "none" ? (
                <>
                  <label>
                    Latitude
                    <input onChange={(event) => setLatitude(event.target.value)} type="number" value={latitude} />
                  </label>
                  <label>
                    Longitude
                    <input onChange={(event) => setLongitude(event.target.value)} type="number" value={longitude} />
                  </label>
                  <label>
                    Place name (optional)
                    <input onChange={(event) => setPlaceName(event.target.value)} value={placeName} />
                  </label>
                </>
              ) : null}
              <label>
                Media
                <select
                  onChange={(event) => setMediaPolicy(event.target.value as EcologicalMediaPolicy)}
                  value={mediaPolicy}
                >
                  <option value="none">None</option>
                  <option value="metadata_only">Reference an existing evidence photo (no bytes copied yet)</option>
                </select>
              </label>
              {mediaPolicy === "metadata_only" ? (
                <label>
                  Evidence media ID
                  <input onChange={(event) => setMediaAssetId(event.target.value)} value={mediaAssetId} />
                </label>
              ) : null}
            </div>
            {locationChoice === "coarse" ? (
              <div className="notice-panel">
                <strong>"Obscured" is a display setting on the destination, not a transmission setting</strong>
                <span>
                  iNaturalist still receives and stores the exact coordinate you enter here — "obscured" only
                  hides it from other users. Enter an already-rounded location yourself if you want the
                  destination's own servers to never see your precise coordinate.
                </span>
              </div>
            ) : null}
            {mediaPolicy === "metadata_only" ? (
              <div className="notice-panel">
                <strong>Privacy Zones do not redact pixels</strong>
                <span>
                  A Privacy or Ignore Zone keeps activity there from triggering a Visit, but it does not black
                  out or crop that part of the frame if another part of the scene caused this photo to be
                  saved. Review the photo yourself before including it anywhere.
                </span>
              </div>
            ) : null}
          </section>

          <section className="panel">
            <div className="section-heading">
              <div>
                <h2>3. Prepare</h2>
                <span className="meta-text">{selectedVisitIds.size} observation(s) selected above.</span>
              </div>
            </div>
            <div className="detail-actions">
              <button
                className="primary-action"
                disabled={prepareLoading || selectedVisitIds.size === 0}
                onClick={() => void prepareSelected()}
                type="button"
              >
                {prepareLoading ? "Preparing..." : `Prepare ${selectedVisitIds.size} selected`}
              </button>
            </div>
            {prepareMessage ? <div className="notice-panel">{prepareMessage}</div> : null}
            {prepareError ? <div className="error-panel">{prepareError}</div> : null}
          </section>
        </>
      ) : null}

      <section className="panel">
        <div className="section-heading">
          <div>
            <h2>Prepared for {activeDestination?.display_name ?? destination}</h2>
            <span className="meta-text">
              Select prepared records to export a file, or record what the destination gave you back.
            </span>
          </div>
        </div>
        {submissions.length > 0 ? (
          <>
            <div className="manifest-file-list" role="table" aria-label="Prepared ecological submissions">
              <div className="manifest-file-row manifest-file-head" role="row">
                <span role="columnheader">Select</span>
                <span role="columnheader">Observation</span>
                <span role="columnheader">Status</span>
                <span role="columnheader">Result</span>
              </div>
              {submissions.map((record) => (
                <div className="manifest-file-row" key={record.id} role="row">
                  <span role="cell">
                    <input
                      checked={selectedSubmissionIds.has(record.id)}
                      disabled={record.status === "needs_input" || record.status === "excluded"}
                      onChange={() => toggleSubmissionSelection(record.id)}
                      type="checkbox"
                    />
                  </span>
                  <span role="cell">
                    <button className="text-action" onClick={() => onOpenVisit(record.visit_id)} type="button">
                      {record.taxon_label ? formatLabel(record.taxon_label) : "Unidentified wildlife"}
                    </button>
                  </span>
                  <span role="cell">
                    <StatusPill label={formatLabel(record.status)} tone={statusTone(record.status)} />
                    {record.is_stale ? (
                      <>
                        <br />
                        <small>MockingBird has been corrected since this was prepared — re-prepare it.</small>
                      </>
                    ) : null}
                  </span>
                  <span role="cell">
                    {record.external_id || record.external_url ? (
                      <span>
                        {record.external_url ? (
                          <a href={record.external_url} rel="noreferrer" target="_blank">
                            {record.external_id ?? record.external_url}
                          </a>
                        ) : (
                          record.external_id
                        )}
                      </span>
                    ) : record.status === "exported" ? (
                      <span className="manifest-export-form">
                        <input
                          onChange={(event) =>
                            setResultDrafts((current) => ({
                              ...current,
                              [record.id]: { externalId: event.target.value, externalUrl: current[record.id]?.externalUrl ?? "" },
                            }))
                          }
                          placeholder="Destination record id/link"
                          value={resultDrafts[record.id]?.externalId ?? ""}
                        />
                        <button
                          className="secondary-action"
                          disabled={recordingResultId === record.id}
                          onClick={() => void submitResult(record.id)}
                          type="button"
                        >
                          Save
                        </button>
                      </span>
                    ) : (
                      "—"
                    )}
                  </span>
                </div>
              ))}
            </div>
            <div className="detail-actions">
              <button
                className="primary-action"
                disabled={exportLoading || selectedSubmissionIds.size === 0}
                onClick={() => void exportSelected()}
                type="button"
              >
                {exportLoading ? "Preparing file..." : `Export ${selectedSubmissionIds.size} selected`}
              </button>
            </div>
            {exportError ? <div className="error-panel">{exportError}</div> : null}
            {exportResult ? (
              <div className="notice-panel">
                <strong>
                  {exportResult.included_count} record(s) written
                  {exportResult.output_directory ? ` to ${exportResult.output_directory}` : ""}.
                </strong>
                {exportResult.skipped.length > 0 ? (
                  <span>
                    {exportResult.skipped.length} skipped:{" "}
                    {exportResult.skipped.map((skip) => `${skip.submission_id} (${formatLabel(skip.reason)})`).join(", ")}
                  </span>
                ) : null}
              </div>
            ) : null}
          </>
        ) : (
          <EmptyState
            title="Nothing prepared yet"
            description="Preview eligibility above, then prepare the observations you want to send."
          />
        )}
      </section>
    </div>
  );
}
