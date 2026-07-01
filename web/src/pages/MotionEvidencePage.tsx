import { useEffect, useMemo, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type {
  CameraSource,
  MotionEvidence,
  MotionEvidenceCreateRequest,
  MotionEvidencePromoteResponse,
  MotionEvidenceStatus,
  Stream,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { EvidenceBadge } from "../components/EvidenceBadge";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel } from "../utils";

type MotionEvidenceFilter = "all" | MotionEvidenceStatus;

const statusFilters: Array<{ value: MotionEvidenceFilter; label: string }> = [
  { value: "pending", label: "Pending" },
  { value: "promoted", label: "Promoted" },
  { value: "ignored", label: "Ignored" },
  { value: "all", label: "All" },
];

interface MotionEvidencePageProps {
  streams: Stream[];
  sources: CameraSource[];
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenReview: () => void;
  onEvidenceChanged: () => Promise<void>;
}

export function MotionEvidencePage({
  streams,
  sources,
  onOpenEvent,
  onOpenVisit,
  onOpenReview,
  onEvidenceChanged,
}: MotionEvidencePageProps) {
  const [evidence, setEvidence] = useState<MotionEvidence[]>([]);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<MotionEvidenceFilter>("pending");
  const [zoneFilter, setZoneFilter] = useState("");
  const [manualZoneId, setManualZoneId] = useState("zone-feeder");
  const [manualSourceId, setManualSourceId] = useState("");
  const [manualStreamId, setManualStreamId] = useState("");
  const [manualPeakChangedRatio, setManualPeakChangedRatio] = useState("42%");
  const [manualTriggeredFrameCount, setManualTriggeredFrameCount] = useState("2");
  const [manualStartFrameIndex, setManualStartFrameIndex] = useState("10");
  const [manualEndFrameIndex, setManualEndFrameIndex] = useState("12");
  const [manualBestFrameIndex, setManualBestFrameIndex] = useState("11");
  const [manualSnapshotMediaAssetId, setManualSnapshotMediaAssetId] = useState("");
  const [manualNotes, setManualNotes] = useState("Manual evidence candidate before stream sampling.");
  const [manualScoringConfig, setManualScoringConfig] = useState(
    '{\n  "source": "manual-ui",\n  "phase": "8H"\n}',
  );
  const [eventTitle, setEventTitle] = useState("");
  const [visitLabelHint, setVisitLabelHint] = useState("unknown_animal");
  const [promotionNotes, setPromotionNotes] = useState("");
  const [lastPromotion, setLastPromotion] = useState<MotionEvidencePromoteResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const sourceById = useMemo(() => new Map(sources.map((source) => [source.id, source])), [sources]);
  const streamById = useMemo(() => new Map(streams.map((stream) => [stream.id, stream])), [streams]);
  const zoneFilteredEvidence = useMemo(
    () =>
      evidence.filter((item) =>
        zoneFilter.trim()
          ? item.zone_id.toLowerCase().includes(zoneFilter.trim().toLowerCase())
          : true,
      ),
    [evidence, zoneFilter],
  );
  const sortedEvidence = useMemo(() => {
    const statusFiltered =
      statusFilter === "all"
        ? zoneFilteredEvidence
        : zoneFilteredEvidence.filter((item) => item.status === statusFilter);
    return [...statusFiltered].sort(
      (left, right) =>
        new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
    );
  }, [statusFilter, zoneFilteredEvidence]);
  const selectedEvidence =
    sortedEvidence.find((item) => item.id === selectedEvidenceId) ?? sortedEvidence[0] ?? null;
  const evidenceCounts = useMemo(() => {
    const counts: Record<MotionEvidenceFilter, number> = {
      all: zoneFilteredEvidence.length,
      pending: 0,
      promoted: 0,
      ignored: 0,
    };
    zoneFilteredEvidence.forEach((item) => {
      counts[item.status] += 1;
    });
    return counts;
  }, [zoneFilteredEvidence]);

  async function loadEvidence(
    options: { showLoading?: boolean; selectEvidenceId?: string } = {},
  ) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoading(true);
    }
    setError(null);
    try {
      const response = await apiClient.listMotionEvidence({ status: "all" });
      setEvidence(response.motion_evidence);
      setSelectedEvidenceId((current) =>
        options.selectEvidenceId &&
        response.motion_evidence.some((item) => item.id === options.selectEvidenceId)
          ? options.selectEvidenceId
          : current && response.motion_evidence.some((item) => item.id === current)
            ? current
            : response.motion_evidence[0]?.id ?? null,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load Motion Evidence.");
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  }

  useEffect(() => {
    void loadEvidence();
  }, []);

  useEffect(() => {
    setEventTitle(
      selectedEvidence
        ? `Motion evidence in ${selectedEvidence.zone_id}`
        : "",
    );
    setVisitLabelHint("unknown_animal");
    setPromotionNotes("");
    setLastPromotion(null);
  }, [selectedEvidence?.id]);

  async function applyZoneFilter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await loadEvidence({ showLoading: false });
  }

  async function createManualEvidence(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setMessage(null);

    const zoneId = manualZoneId.trim();
    if (!zoneId) {
      setError("Add a zone_id before creating Motion Evidence.");
      return;
    }

    let peakChangedRatio: number;
    let triggeredFrameCount: number;
    let startFrameIndex: number | null;
    let endFrameIndex: number | null;
    let bestFrameIndex: number | null;
    let scoringConfig: Record<string, string | number | boolean>;
    try {
      peakChangedRatio = parsePeakChangedRatio(manualPeakChangedRatio);
      triggeredFrameCount = parsePositiveInteger(
        manualTriggeredFrameCount,
        "Triggered frame count",
      );
      startFrameIndex = parseOptionalFrameIndex(manualStartFrameIndex, "Start frame index");
      endFrameIndex = parseOptionalFrameIndex(manualEndFrameIndex, "End frame index");
      bestFrameIndex = parseOptionalFrameIndex(manualBestFrameIndex, "Best frame index");
      scoringConfig = parseScoringConfig(manualScoringConfig);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Manual evidence fields are invalid.");
      return;
    }

    const payload: MotionEvidenceCreateRequest = {
      zone_id: zoneId,
      source_id: manualSourceId || undefined,
      stream_id: manualStreamId || undefined,
      start_frame_index: startFrameIndex,
      end_frame_index: endFrameIndex,
      best_frame_index: bestFrameIndex,
      peak_changed_ratio: peakChangedRatio,
      triggered_frame_count: triggeredFrameCount,
      scoring_config: scoringConfig,
      snapshot_media_asset_id: manualSnapshotMediaAssetId.trim() || undefined,
      notes: manualNotes.trim() || undefined,
    };

    setIsCreating(true);
    try {
      const created = await apiClient.createMotionEvidence(payload);
      setStatusFilter("pending");
      setZoneFilter(created.zone_id);
      setSelectedEvidenceId(created.id);
      setMessage(
        `${created.id} created as pending Motion Evidence. Review it before promotion.`,
      );
      await loadEvidence({ showLoading: false, selectEvidenceId: created.id });
      await onEvidenceChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Manual Motion Evidence could not be created.");
    } finally {
      setIsCreating(false);
    }
  }

  async function ignoreEvidence(item: MotionEvidence) {
    setActionId(`${item.id}:ignore`);
    setError(null);
    setMessage(null);
    try {
      const ignored = await apiClient.ignoreMotionEvidence(item.id);
      setSelectedEvidenceId(ignored.id);
      setMessage(`${ignored.id} ignored as motion noise. No Event, Visit, or truth was created.`);
      await loadEvidence({ showLoading: false });
      await onEvidenceChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Motion Evidence could not be ignored.");
    } finally {
      setActionId(null);
    }
  }

  async function promoteEvidence(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedEvidence || selectedEvidence.status !== "pending") {
      return;
    }

    setActionId(`${selectedEvidence.id}:promote`);
    setError(null);
    setMessage(null);
    setLastPromotion(null);
    try {
      const result = await apiClient.promoteMotionEvidence(selectedEvidence.id, {
        event_title: eventTitle.trim() || undefined,
        visit_label_hint: visitLabelHint.trim() || undefined,
        notes: promotionNotes.trim() || undefined,
        create_event: true,
        create_visit: true,
      });
      setLastPromotion(result);
      setSelectedEvidenceId(result.evidence.id);
      setMessage(
        `${result.evidence.id} promoted to unreviewed Event/Visit evidence. Correct it before export.`,
      );
      await loadEvidence({ showLoading: false });
      await onEvidenceChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Motion Evidence could not be promoted.");
    } finally {
      setActionId(null);
    }
  }

  const hasFilters = statusFilter !== "all" || zoneFilter.trim().length > 0;

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Motion-triggered evidence"
        title="Motion Evidence Review"
        description="Motion evidence records moments where zone-aware motion scoring found activity. It is not a species label or reviewed truth."
        actions={
          <button className="secondary-action" onClick={onOpenReview}>
            Review Queue
          </button>
        }
      />

      <section className="notice-panel">
        <strong>Evidence before truth</strong>
        <span>
          Promote pending evidence only when it should become unreviewed Event/Visit context.
          User correction remains the dataset/export truth source.
        </span>
      </section>

      {message ? <div className="notice-panel">{message}</div> : null}
      {error ? <div className="error-panel">{error}</div> : null}

      <section className="panel motion-create-panel">
        <div className="section-heading">
          <div>
            <h2>Create manual motion evidence</h2>
            <span className="meta-text">
              Manual evidence creation is for local testing before stream sampling is wired in.
              It creates pending MotionEvidence only; it does not create labels, reviewed
              observations, or export-ready truth.
            </span>
          </div>
          <EvidenceBadge label="Pending evidence only" tone="review" />
        </div>
        <form className="motion-create-form" onSubmit={createManualEvidence}>
          <div className="motion-create-grid">
            <label>
              Zone ID
              <input
                required
                value={manualZoneId}
                onChange={(event) => setManualZoneId(event.target.value)}
                placeholder="zone-feeder"
              />
            </label>
            <label>
              Source
              <select
                value={manualSourceId}
                onChange={(event) => setManualSourceId(event.target.value)}
              >
                <option value="">Infer from zone</option>
                {sources.map((source) => (
                  <option key={source.id} value={source.id}>
                    {source.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Stream
              <select
                value={manualStreamId}
                onChange={(event) => setManualStreamId(event.target.value)}
              >
                <option value="">Infer from zone</option>
                {streams.map((stream) => (
                  <option key={stream.id} value={stream.id}>
                    {stream.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Peak change
              <input
                required
                value={manualPeakChangedRatio}
                onChange={(event) => setManualPeakChangedRatio(event.target.value)}
                placeholder="42% or 0.42"
              />
            </label>
            <label>
              Triggered frames
              <input
                required
                inputMode="numeric"
                value={manualTriggeredFrameCount}
                onChange={(event) => setManualTriggeredFrameCount(event.target.value)}
                placeholder="2"
              />
            </label>
            <label>
              Snapshot media asset ID
              <input
                value={manualSnapshotMediaAssetId}
                onChange={(event) => setManualSnapshotMediaAssetId(event.target.value)}
                placeholder="optional"
              />
            </label>
            <label>
              Start frame
              <input
                inputMode="numeric"
                value={manualStartFrameIndex}
                onChange={(event) => setManualStartFrameIndex(event.target.value)}
                placeholder="optional"
              />
            </label>
            <label>
              End frame
              <input
                inputMode="numeric"
                value={manualEndFrameIndex}
                onChange={(event) => setManualEndFrameIndex(event.target.value)}
                placeholder="optional"
              />
            </label>
            <label>
              Best frame
              <input
                inputMode="numeric"
                value={manualBestFrameIndex}
                onChange={(event) => setManualBestFrameIndex(event.target.value)}
                placeholder="optional"
              />
            </label>
            <label className="motion-wide-field">
              Scoring config JSON
              <textarea
                value={manualScoringConfig}
                onChange={(event) => setManualScoringConfig(event.target.value)}
              />
            </label>
            <label className="motion-wide-field">
              Notes
              <textarea
                value={manualNotes}
                onChange={(event) => setManualNotes(event.target.value)}
                placeholder="Manual evidence note"
              />
            </label>
          </div>
          <div className="motion-create-actions">
            <button className="primary-action" disabled={isCreating} type="submit">
              {isCreating ? "Creating..." : "Create pending evidence"}
            </button>
            <span className="field-helper">
              Leave source and stream blank to let the backend use the selected zone.
            </span>
          </div>
        </form>
      </section>

      <section className="panel motion-evidence-filters">
        <div className="section-heading">
          <div>
            <h2>Evidence filters</h2>
            <span className="meta-text">Review pending activity, promoted evidence, or ignored noise.</span>
          </div>
          <EvidenceBadge label={`${evidenceCounts.pending} pending`} tone="review" />
        </div>
        <div className="proposal-status-tabs" role="tablist" aria-label="Motion Evidence status filters">
          {statusFilters.map((filter) => (
            <button
              className={statusFilter === filter.value ? "selected" : ""}
              key={filter.value}
              onClick={() => setStatusFilter(filter.value)}
              type="button"
            >
              {filter.label}
              <span>{evidenceCounts[filter.value]}</span>
            </button>
          ))}
        </div>
        <form className="motion-zone-filter" onSubmit={applyZoneFilter}>
          <label>
            Zone ID
            <input
              placeholder="zone-feeder"
              value={zoneFilter}
              onChange={(event) => setZoneFilter(event.target.value)}
            />
          </label>
          <button className="secondary-action" type="submit">
            Apply
          </button>
          {zoneFilter ? (
            <button
              className="text-action"
              type="button"
              onClick={() => {
                setZoneFilter("");
              }}
            >
              Clear
            </button>
          ) : null}
        </form>
      </section>

      {isLoading ? <div className="panel">Loading Motion Evidence...</div> : null}

      {!isLoading && sortedEvidence.length === 0 ? (
        <EmptyState
          title={hasFilters ? "No Motion Evidence matches this filter." : "No Motion Evidence yet."}
          description={
            hasFilters
              ? "Try another status or zone. Future stream sampling will add new evidence automatically."
              : "Future stream sampling will create MotionEvidence automatically; current records can come from explicit backend/API creation."
          }
        />
      ) : null}

      {!isLoading && sortedEvidence.length > 0 ? (
        <div className="motion-evidence-layout">
          <section className="motion-evidence-list" aria-label="Motion Evidence list">
            {sortedEvidence.map((item) => (
              <button
                className={
                  selectedEvidence?.id === item.id
                    ? "motion-evidence-row selected"
                    : "motion-evidence-row"
                }
                key={item.id}
                onClick={() => setSelectedEvidenceId(item.id)}
                type="button"
              >
                <div className="item-title-row">
                  <div>
                    <span className="meta-text">{item.zone_id}</span>
                    <h2>{item.id}</h2>
                  </div>
                  <MotionEvidenceStatusPill status={item.status} />
                </div>
                <div className="motion-evidence-meta">
                  <span>{formatPercent(item.peak_changed_ratio)} peak change</span>
                  <span>{item.triggered_frame_count} triggered frames</span>
                  <span>{formatRange(item)}</span>
                  <span>{formatDateTime(item.created_at)}</span>
                </div>
                {item.notes ? <p>{item.notes}</p> : null}
              </button>
            ))}
          </section>

          <section className="panel motion-evidence-detail">
            {selectedEvidence ? (
              <>
                <div className="section-heading">
                  <div>
                    <span className="meta-text">Selected evidence</span>
                    <h2>{selectedEvidence.id}</h2>
                  </div>
                  <MotionEvidenceStatusPill status={selectedEvidence.status} />
                </div>

                <div className="motion-evidence-detail-grid">
                  <DetailItem label="Zone" value={selectedEvidence.zone_id} />
                  <DetailItem label="Peak change" value={formatPercent(selectedEvidence.peak_changed_ratio)} />
                  <DetailItem label="Triggered frames" value={`${selectedEvidence.triggered_frame_count}`} />
                  <DetailItem label="Frame/time range" value={formatRange(selectedEvidence)} />
                  <DetailItem label="Best frame/time" value={formatBestMoment(selectedEvidence)} />
                  <DetailItem
                    label="Source"
                    value={formatSource(selectedEvidence.source_id, sourceById)}
                  />
                  <DetailItem
                    label="Stream"
                    value={formatStream(selectedEvidence.stream_id, streamById)}
                  />
                  <DetailItem label="Created" value={formatDateTime(selectedEvidence.created_at)} />
                </div>

                <section className="motion-evidence-subsection">
                  <h3>Scoring context</h3>
                  <div className="motion-config-list">
                    {Object.entries(selectedEvidence.scoring_config).length > 0 ? (
                      Object.entries(selectedEvidence.scoring_config).map(([key, value]) => (
                        <span key={key}>
                          {formatLabel(key)}: {String(value)}
                        </span>
                      ))
                    ) : (
                      <span>No scoring configuration attached.</span>
                    )}
                  </div>
                </section>

                <section className="motion-evidence-subsection">
                  <h3>Evidence links</h3>
                  <div className="motion-evidence-links">
                    <span>Snapshot media: {selectedEvidence.snapshot_media_asset_id ?? "none"}</span>
                    <span>Promoted Event: {selectedEvidence.promoted_event_id ?? "none"}</span>
                    <span>Promoted Visit: {selectedEvidence.promoted_visit_id ?? "none"}</span>
                  </div>
                  <div className="detail-actions">
                    {selectedEvidence.promoted_event_id ? (
                      <button
                        className="text-action"
                        onClick={() => onOpenEvent(selectedEvidence.promoted_event_id!)}
                      >
                        Event detail
                      </button>
                    ) : null}
                    {selectedEvidence.promoted_visit_id ? (
                      <button
                        className="text-action"
                        onClick={() => onOpenVisit(selectedEvidence.promoted_visit_id!)}
                      >
                        Visit detail
                      </button>
                    ) : null}
                  </div>
                </section>

                <section className="notice-panel">
                  <strong>Truth boundary</strong>
                  <span>
                    Motion Evidence can explain why a moment was captured. It does not create
                    reviewed labels, species truth, exports, or dataset coverage truth.
                  </span>
                </section>

                {selectedEvidence.status === "pending" ? (
                  <section className="motion-action-panel">
                    <div className="detail-actions">
                      <button
                        className="secondary-action"
                        disabled={actionId === `${selectedEvidence.id}:ignore`}
                        onClick={() => void ignoreEvidence(selectedEvidence)}
                        type="button"
                      >
                        {actionId === `${selectedEvidence.id}:ignore` ? "Ignoring..." : "Ignore"}
                      </button>
                    </div>
                    <form className="motion-promote-form" onSubmit={promoteEvidence}>
                      <label>
                        Event title
                        <input
                          value={eventTitle}
                          onChange={(event) => setEventTitle(event.target.value)}
                          placeholder="Motion evidence in feeder"
                        />
                      </label>
                      <label>
                        Visit label hint
                        <input
                          value={visitLabelHint}
                          onChange={(event) => setVisitLabelHint(event.target.value)}
                          placeholder="unknown_animal"
                        />
                      </label>
                      <label>
                        Notes
                        <textarea
                          value={promotionNotes}
                          onChange={(event) => setPromotionNotes(event.target.value)}
                          placeholder="Why this should become reviewable evidence"
                        />
                      </label>
                      <button
                        className="primary-action"
                        disabled={actionId === `${selectedEvidence.id}:promote`}
                        type="submit"
                      >
                        {actionId === `${selectedEvidence.id}:promote` ? "Promoting..." : "Promote"}
                      </button>
                    </form>
                  </section>
                ) : null}

                {selectedEvidence.status === "promoted" ? (
                  <div className="notice-panel">
                    <strong>Promoted evidence</strong>
                    <span>
                      This Motion Evidence is now unreviewed Event/Visit evidence. Open the detail
                      records and correct labels before export.
                    </span>
                  </div>
                ) : null}

                {selectedEvidence.status === "ignored" ? (
                  <div className="notice-panel">
                    <strong>Ignored evidence</strong>
                    <span>This evidence was dismissed as noise and cannot be promoted.</span>
                  </div>
                ) : null}

                {lastPromotion ? (
                  <div className="notice-panel">
                    <strong>Created reviewable evidence</strong>
                    <span>
                      Event {lastPromotion.event_id ?? "none"} · Visit{" "}
                      {lastPromotion.visit_id ?? "none"}
                    </span>
                  </div>
                ) : null}
              </>
            ) : null}
          </section>
        </div>
      ) : null}
    </div>
  );
}

function MotionEvidenceStatusPill({ status }: { status: MotionEvidenceStatus }) {
  const tone = status === "pending" ? "review" : status === "promoted" ? "good" : "quiet";
  return <StatusPill label={formatLabel(status)} tone={tone} />;
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatRange(evidence: MotionEvidence): string {
  if (evidence.start_time || evidence.end_time) {
    return `${evidence.start_time ?? "unknown"} to ${evidence.end_time ?? "unknown"}`;
  }
  if (
    evidence.start_frame_index !== null &&
    evidence.start_frame_index !== undefined ||
    evidence.end_frame_index !== null &&
    evidence.end_frame_index !== undefined
  ) {
    return `frames ${evidence.start_frame_index ?? "?"}-${evidence.end_frame_index ?? "?"}`;
  }
  return "range unknown";
}

function parsePeakChangedRatio(value: string): number {
  const trimmed = value.trim();
  const numeric = trimmed.endsWith("%") ? Number(trimmed.slice(0, -1)) / 100 : Number(trimmed);
  const ratio = !trimmed.endsWith("%") && numeric > 1 ? numeric / 100 : numeric;
  if (!Number.isFinite(ratio) || ratio < 0 || ratio > 1) {
    throw new Error("Peak change must be a percentage from 0% to 100% or a decimal from 0 to 1.");
  }
  return ratio;
}

function parsePositiveInteger(value: string, label: string): number {
  const parsed = Number(value.trim());
  if (!Number.isInteger(parsed) || parsed < 1) {
    throw new Error(`${label} must be a whole number of at least 1.`);
  }
  return parsed;
}

function parseOptionalFrameIndex(value: string, label: string): number | null {
  if (!value.trim()) {
    return null;
  }
  const parsed = Number(value.trim());
  if (!Number.isInteger(parsed) || parsed < 0) {
    throw new Error(`${label} must be a whole number of at least 0.`);
  }
  return parsed;
}

function parseScoringConfig(rawValue: string): Record<string, string | number | boolean> {
  if (!rawValue.trim()) {
    return {};
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(rawValue);
  } catch {
    throw new Error("Scoring config must be valid JSON.");
  }

  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Scoring config must be a JSON object.");
  }

  const config: Record<string, string | number | boolean> = {};
  Object.entries(parsed).forEach(([key, value]) => {
    if (
      typeof value !== "string" &&
      typeof value !== "number" &&
      typeof value !== "boolean"
    ) {
      throw new Error("Scoring config values must be strings, numbers, or booleans.");
    }
    if (typeof value === "number" && !Number.isFinite(value)) {
      throw new Error("Scoring config number values must be finite.");
    }
    config[key] = value;
  });

  return config;
}

function formatBestMoment(evidence: MotionEvidence): string {
  if (evidence.best_frame_time) {
    return evidence.best_frame_time;
  }
  if (evidence.best_frame_index !== null && evidence.best_frame_index !== undefined) {
    return `frame ${evidence.best_frame_index}`;
  }
  return "not selected";
}

function formatSource(
  sourceId: string | null | undefined,
  sourceById: Map<string, CameraSource>,
): string {
  if (!sourceId) {
    return "none";
  }
  return sourceById.get(sourceId)?.name ?? sourceId;
}

function formatStream(
  streamId: string | null | undefined,
  streamById: Map<string, Stream>,
): string {
  if (!streamId) {
    return "none";
  }
  return streamById.get(streamId)?.name ?? streamId;
}
