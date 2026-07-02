import { useEffect, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type {
  CameraSource,
  SourceConnectionStatus,
  SourceProviderConfiguration,
  SourceProviderDefinition,
  SourceSetupReviewResponse,
  Stream,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatLabel } from "../utils";

interface StreamsPageProps {
  streams: Stream[];
  sources: CameraSource[];
  onOpenImport: () => void;
  onOpenStream: (streamId: string) => void;
}

function connectionTone(status: SourceConnectionStatus["status"]): "good" | "review" | "quiet" {
  if (status === "demo" || status === "configured") {
    return "good";
  }
  if (status === "not_configured" || status === "unavailable") {
    return "review";
  }
  return "quiet";
}

function readinessTone(
  readinessLevel: SourceSetupReviewResponse["readiness_level"],
): "good" | "review" | "quiet" {
  if (readinessLevel === "demo_ready" || readinessLevel === "metadata_ready") {
    return "good";
  }
  if (readinessLevel === "needs_setup" || readinessLevel === "unavailable") {
    return "review";
  }
  return "quiet";
}

function stepTone(
  status: SourceSetupReviewResponse["steps"][number]["status"],
): "good" | "review" | "quiet" {
  if (status === "complete" || status === "available") {
    return "good";
  }
  if (status === "missing" || status === "warning" || status === "unavailable") {
    return "review";
  }
  return "quiet";
}

function draftFromConfiguration(
  definition: SourceProviderDefinition | undefined,
  configuration: SourceProviderConfiguration | null,
): Record<string, string> {
  if (!definition) {
    return {};
  }
  return Object.fromEntries(
    definition.fields.map((field) => {
      const preview = configuration?.safe_config_preview[field.key];
      const value = !field.secret && preview && preview !== "not_configured" ? preview : "";
      return [field.key, value];
    }),
  );
}

export function StreamsPage({ streams, sources, onOpenImport, onOpenStream }: StreamsPageProps) {
  const [connectionStatuses, setConnectionStatuses] = useState<
    Record<string, SourceConnectionStatus>
  >({});
  const [providerDefinitions, setProviderDefinitions] = useState<SourceProviderDefinition[]>([]);
  const [providerConfigurations, setProviderConfigurations] = useState<
    Record<string, SourceProviderConfiguration>
  >({});
  const [setupReviews, setSetupReviews] = useState<Record<string, SourceSetupReviewResponse>>({});
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(sources[0]?.id ?? null);
  const [providerKey, setProviderKey] = useState("");
  const [configDraft, setConfigDraft] = useState<Record<string, string>>({});
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [setupError, setSetupError] = useState<string | null>(null);
  const [setupMessage, setSetupMessage] = useState<string | null>(null);
  const [isSavingSetup, setIsSavingSetup] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadSourceSetup() {
      if (sources.length === 0) {
        setConnectionStatuses({});
        setProviderConfigurations({});
        setSetupReviews({});
        setConnectionError(null);
        return;
      }

      setConnectionError(null);
      try {
        const [definitions, connectionEntries, configurationEntries, reviewEntries] =
          await Promise.all([
            apiClient.getSourceProviderDefinitions(),
            Promise.all(
              sources.map(async (source) => [
                source.id,
                await apiClient.getSourceConnectionStatus(source.id),
              ] as const),
            ),
            Promise.all(
              sources.map(async (source) => [
                source.id,
                await apiClient.getSourceProviderConfiguration(source.id),
              ] as const),
            ),
            Promise.all(
              sources.map(async (source) => [
                source.id,
                await apiClient.getSourceSetupReview(source.id),
              ] as const),
            ),
          ]);
        if (isMounted) {
          setProviderDefinitions(definitions);
          setConnectionStatuses(Object.fromEntries(connectionEntries));
          setProviderConfigurations(Object.fromEntries(configurationEntries));
          setSetupReviews(Object.fromEntries(reviewEntries));
        }
      } catch (caught) {
        if (isMounted) {
          setConnectionError(
            caught instanceof Error ? caught.message : "Could not load source setup status.",
          );
        }
      }
    }

    void loadSourceSetup();

    return () => {
      isMounted = false;
    };
  }, [sources]);

  useEffect(() => {
    if (sources.length === 0) {
      setSelectedSourceId(null);
      return;
    }
    if (!selectedSourceId || !sources.some((source) => source.id === selectedSourceId)) {
      setSelectedSourceId(sources[0].id);
    }
  }, [sources, selectedSourceId]);

  const selectedSource = sources.find((source) => source.id === selectedSourceId) ?? null;
  const selectedConnection = selectedSourceId ? connectionStatuses[selectedSourceId] : null;
  const selectedConfiguration = selectedSourceId
    ? providerConfigurations[selectedSourceId] ?? null
    : null;
  const selectedSetupReview = selectedSourceId ? setupReviews[selectedSourceId] ?? null : null;
  const selectedSourceStreams = selectedSource
    ? streams.filter((stream) => stream.source_id === selectedSource.id)
    : [];
  const selectedReviewStreams = new Map(
    (selectedSetupReview?.streams ?? []).map((stream) => [stream.stream_id, stream]),
  );
  const selectedProviderDefinition =
    providerDefinitions.find((definition) => definition.provider_key === providerKey) ??
    providerDefinitions.find(
      (definition) => definition.provider_key === selectedConfiguration?.provider_key,
    );

  useEffect(() => {
    if (!selectedConfiguration) {
      return;
    }
    const definition = providerDefinitions.find(
      (item) => item.provider_key === selectedConfiguration.provider_key,
    );
    setProviderKey(selectedConfiguration.provider_key);
    setConfigDraft(draftFromConfiguration(definition, selectedConfiguration));
  }, [providerDefinitions, selectedConfiguration]);

  function handleProviderChange(nextProviderKey: string) {
    const definition = providerDefinitions.find((item) => item.provider_key === nextProviderKey);
    const matchingConfiguration =
      selectedConfiguration?.provider_key === nextProviderKey ? selectedConfiguration : null;
    setProviderKey(nextProviderKey);
    setConfigDraft(draftFromConfiguration(definition, matchingConfiguration));
    setSetupError(null);
    setSetupMessage(null);
  }

  async function handleSaveProviderConfiguration(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSourceId || !selectedProviderDefinition) {
      return;
    }

    const config: Record<string, string | null> = {};
    for (const field of selectedProviderDefinition.fields) {
      const draftValue = configDraft[field.key]?.trim() ?? "";
      const existingPreview = selectedConfiguration?.safe_config_preview[field.key];
      if (field.secret && !draftValue && existingPreview === "configured") {
        config[field.key] = "configured";
      } else {
        config[field.key] = draftValue || null;
      }
    }

    setIsSavingSetup(true);
    setSetupError(null);
    setSetupMessage(null);
    try {
      const configuration = await apiClient.updateSourceProviderConfiguration(selectedSourceId, {
        provider_key: selectedProviderDefinition.provider_key,
        config,
      });
      const [connection, setupReview] = await Promise.all([
        apiClient.getSourceConnectionStatus(selectedSourceId),
        apiClient.getSourceSetupReview(selectedSourceId),
      ]);
      setProviderConfigurations((current) => ({
        ...current,
        [selectedSourceId]: configuration,
      }));
      setConnectionStatuses((current) => ({
        ...current,
        [selectedSourceId]: connection,
      }));
      setSetupReviews((current) => ({
        ...current,
        [selectedSourceId]: setupReview,
      }));
      setSetupMessage("Source setup metadata saved.");
    } catch (caught) {
      setSetupError(caught instanceof Error ? caught.message : "Could not save source setup.");
    } finally {
      setIsSavingSetup(false);
    }
  }

  async function refreshSourceSetupStatuses() {
    try {
      const [connectionEntries, reviewEntries] = await Promise.all([
        Promise.all(
          sources.map(async (source) => [
            source.id,
            await apiClient.getSourceConnectionStatus(source.id),
          ] as const),
        ),
        Promise.all(
          sources.map(async (source) => [
            source.id,
            await apiClient.getSourceSetupReview(source.id),
          ] as const),
        ),
      ]);
      setConnectionStatuses(Object.fromEntries(connectionEntries));
      setSetupReviews(Object.fromEntries(reviewEntries));
    } catch (caught) {
      setConnectionError(
        caught instanceof Error ? caught.message : "Could not load source setup status.",
      );
    }
  }

  const selectedProviderLabel =
    selectedSetupReview?.provider_display_name ??
    selectedProviderDefinition?.display_name ??
    selectedConfiguration?.provider_key ??
    "Loading";
  const selectedLivePlaybackLabel = selectedSetupReview
    ? selectedSetupReview.supports_live_playback
      ? "Available"
      : "Not available"
    : "Loading";
  const selectedZoneEditingLabel = selectedSetupReview
    ? selectedSetupReview.supports_zone_editing
      ? "Available"
      : "Unavailable"
    : "Loading";
  const selectedReadinessLabel = selectedSetupReview
    ? formatLabel(selectedSetupReview.readiness_level)
    : "Loading";
  const isManualMediaReady =
    selectedSetupReview?.provider_key === "manual_media" &&
    selectedSetupReview.readiness_level === "metadata_ready";
  const selectedFirstStream = selectedSourceStreams[0] ?? null;
  const nextActionTitle = selectedSetupReview
    ? selectedSetupReview.readiness_level === "demo_ready"
      ? "Next: open Stream Detail and draw Zones."
      : isManualMediaReady
        ? "Next: import media for this Source/Stream."
        : selectedSetupReview.readiness_level === "needs_setup"
          ? "Next: complete setup metadata."
          : selectedSetupReview.readiness_level === "future_adapter_required"
            ? "Next: future provider implementation required before live playback."
            : "Next: review Source setup status."
    : "Next: load Source setup status.";
  const nextActionDetail = selectedSetupReview?.next_step ?? selectedConnection?.setup_hint;

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Stream-first workspace"
        title="Streams"
        description="Connect Sources, inspect Streams, configure setup metadata, then draw Zones and review activity."
      />
      {connectionError ? <div className="error-panel">{connectionError}</div> : null}
      {selectedSource ? (
        <section className="panel source-setup-panel source-workflow-panel">
          <div className="section-heading">
            <div>
              <h2>Source workflow</h2>
              <span className="meta-text">
                Setup metadata, playback status, Streams, Zones, and review stay in one flow
              </span>
            </div>
            {selectedSetupReview ? (
              <StatusPill
                label={selectedReadinessLabel}
                tone={readinessTone(selectedSetupReview.readiness_level)}
              />
            ) : selectedConnection ? (
              <StatusPill
                label={formatLabel(selectedConnection.status)}
                tone={connectionTone(selectedConnection.status)}
              />
            ) : null}
          </div>
          <div className="source-selector-row">
            <label>
              Source
              <select
                value={selectedSource.id}
                onChange={(event) => {
                  setSelectedSourceId(event.target.value);
                  setSetupError(null);
                  setSetupMessage(null);
                }}
              >
                {sources.map((source) => (
                  <option key={source.id} value={source.id}>
                    {source.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="source-summary-line">
              <strong>{selectedProviderLabel}</strong>
              <span>{selectedSetupReview?.summary ?? selectedSource.description}</span>
            </div>
          </div>
          <div className="source-overview-grid">
            <div>
              <span>Readiness</span>
              <strong>{selectedReadinessLabel}</strong>
            </div>
            <div>
              <span>Provider</span>
              <strong>{selectedProviderLabel}</strong>
            </div>
            <div>
              <span>Live playback</span>
              <strong>{selectedLivePlaybackLabel}</strong>
            </div>
            <div>
              <span>Zone editing</span>
              <strong>{selectedZoneEditingLabel}</strong>
            </div>
          </div>
          <div className="source-next-action">
            <div>
              <strong>{nextActionTitle}</strong>
              {nextActionDetail ? <span>{nextActionDetail}</span> : null}
            </div>
            <div className="source-next-action-buttons">
              {isManualMediaReady ? (
                <button className="primary-action" onClick={onOpenImport} type="button">
                  Import media
                </button>
              ) : selectedSetupReview?.readiness_level === "demo_ready" && selectedFirstStream ? (
                <button
                  className="primary-action"
                  onClick={() => onOpenStream(selectedFirstStream.id)}
                  type="button"
                >
                  Open Stream Detail
                </button>
              ) : null}
              {selectedFirstStream && selectedSetupReview?.readiness_level !== "demo_ready" ? (
                <button
                  className="secondary-action"
                  onClick={() => onOpenStream(selectedFirstStream.id)}
                  type="button"
                >
                  Open related Stream
                </button>
              ) : null}
            </div>
          </div>
          <div className="source-setup-layout">
            <div className="source-setup-summary">
              {selectedSetupReview ? (
                <div className="source-review-panel">
                  <div className="item-title-row">
                    <h3>Setup status</h3>
                    <StatusPill
                      label={formatLabel(selectedSetupReview.readiness_level)}
                      tone={readinessTone(selectedSetupReview.readiness_level)}
                    />
                  </div>
                  <div className="source-field-summary">
                    <div>
                      <strong>Configured</strong>
                      <div className="source-field-tags">
                        {selectedSetupReview.configured_fields.length > 0 ? (
                          selectedSetupReview.configured_fields.map((field) => (
                            <span key={field}>{formatLabel(field)}</span>
                          ))
                        ) : (
                          <span>None</span>
                        )}
                      </div>
                    </div>
                    <div>
                      <strong>Missing</strong>
                      <div className="source-field-tags">
                        {selectedSetupReview.missing_fields.length > 0 ? (
                          selectedSetupReview.missing_fields.map((field) => (
                            <span key={field}>{formatLabel(field)}</span>
                          ))
                        ) : (
                          <span>None</span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="source-review-step-list">
                    {selectedSetupReview.steps.map((step) => (
                      <div className="source-review-step" key={step.key}>
                        <div className="item-title-row">
                          <strong>{step.label}</strong>
                          <StatusPill
                            label={formatLabel(step.status)}
                            tone={stepTone(step.status)}
                          />
                        </div>
                        <p>{step.message}</p>
                      </div>
                    ))}
                  </div>
                  {selectedSetupReview.warnings.length > 0 ? (
                    <div className="source-warning-list">
                      {selectedSetupReview.warnings.map((warning) => (
                        <span key={warning}>{warning}</span>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
            <form className="source-setup-form" onSubmit={handleSaveProviderConfiguration}>
              <div className="item-title-row">
                <h3>Provider setup</h3>
                <StatusPill label="Metadata only" tone="quiet" />
              </div>
              <p className="meta-text">
                Provider setup stores safe metadata for this Source. It does not connect, capture,
                decode, or create truth.
              </p>
              <label>
                Provider
                <select
                  value={providerKey}
                  onChange={(event) => handleProviderChange(event.target.value)}
                >
                  {providerDefinitions.map((definition) => (
                    <option key={definition.provider_key} value={definition.provider_key}>
                      {definition.display_name}
                    </option>
                  ))}
                </select>
              </label>
              {selectedProviderDefinition ? (
                <>
                  <p className="meta-text">{selectedProviderDefinition.description}</p>
                  <div className="provider-field-grid">
                    {selectedProviderDefinition.fields.map((field) => {
                      const existingPreview = selectedConfiguration?.safe_config_preview[field.key];
                      return (
                        <label key={field.key}>
                          {field.label}
                          <input
                            placeholder={
                              field.secret && existingPreview === "configured"
                                ? "Configured marker saved"
                                : field.placeholder ?? ""
                            }
                            type={field.secret ? "password" : "text"}
                            value={configDraft[field.key] ?? ""}
                            onChange={(event) =>
                              setConfigDraft((current) => ({
                                ...current,
                                [field.key]: event.target.value,
                              }))
                            }
                          />
                          <span className="field-meta">
                            {field.required ? "Required" : "Optional"}
                            {field.secret ? " · stored as marker only" : ""}
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </>
              ) : null}
              <div className="source-setup-actions">
                <button className="primary-action" disabled={isSavingSetup} type="submit">
                  Save setup
                </button>
                <button
                  className="secondary-action"
                  onClick={refreshSourceSetupStatuses}
                  type="button"
                >
                  Refresh status
                </button>
              </div>
              {selectedConfiguration?.setup_hint ? (
                <span className="meta-text">{selectedConfiguration.setup_hint}</span>
              ) : null}
              {setupMessage ? <div className="zone-message">{setupMessage}</div> : null}
              {setupError ? <div className="zone-error">{setupError}</div> : null}
            </form>
          </div>
          <section className="source-streams-panel">
            <div className="section-heading">
              <div>
                <h3>Source Streams</h3>
                <span className="meta-text">
                  Open Stream Detail to inspect playback status and draw Zones
                </span>
              </div>
              <StatusPill label={`${selectedSourceStreams.length} streams`} tone="quiet" />
            </div>
            <div className="source-stream-grid">
              {selectedSourceStreams.length > 0 ? (
                selectedSourceStreams.map((stream) => {
                  const reviewStream = selectedReviewStreams.get(stream.id);
                  const playbackLabel = reviewStream
                    ? formatLabel(reviewStream.playback_status)
                    : stream.is_live
                      ? "Stream"
                      : "Placeholder";
                  return (
                    <section className="source-stream-card" key={stream.id}>
                      <div className="item-title-row">
                        <h4>{stream.name}</h4>
                        <StatusPill
                          label={playbackLabel}
                          tone={reviewStream?.playback_status === "demo" ? "good" : "quiet"}
                        />
                      </div>
                      <p>{reviewStream?.message ?? stream.description}</p>
                      <div className="source-connection-meta">
                        <span>
                          Playback:{" "}
                          {reviewStream ? formatLabel(reviewStream.playback_kind) : "Placeholder"}
                        </span>
                        <span>
                          Live:{" "}
                          {reviewStream?.supports_live_playback ? "Available" : "Not available"}
                        </span>
                        <span>
                          Zones:{" "}
                          {reviewStream
                            ? reviewStream.supports_zone_editing
                              ? "Available"
                              : "Unavailable"
                            : "Available"}
                        </span>
                      </div>
                      <div className="detail-actions">
                        <button
                          className="primary-action"
                          onClick={() => onOpenStream(stream.id)}
                          type="button"
                        >
                          Open Stream Detail
                        </button>
                        {isManualMediaReady ? (
                          <button
                            className="secondary-action"
                            onClick={onOpenImport}
                            type="button"
                          >
                            Import media
                          </button>
                        ) : null}
                      </div>
                    </section>
                  );
                })
              ) : (
                <EmptyState
                  title="No Streams for this Source"
                  description="Streams will become the center of Zones and review once this Source has Stream metadata."
                />
              )}
            </div>
          </section>
        </section>
      ) : (
        <EmptyState
          title="No Sources available"
          description="Sources and Streams will become the center of setup, Zones, and review."
        />
      )}
    </div>
  );
}
