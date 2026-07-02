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
  const sourceNames = new Map(sources.map((source) => [source.id, source.name]));
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

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Stream-first workspace"
        title="Streams"
        description="Open a stream to draw zones, inspect outdoor events, and start the review loop."
      />
      {sources.length > 0 ? (
        <section className="source-connection-section">
          <div className="section-heading">
            <h2>Source connection</h2>
            <span className="meta-text">Provider readiness for stream playback</span>
          </div>
          {connectionError ? <div className="error-panel">{connectionError}</div> : null}
          <div className="source-connection-grid">
            {sources.map((source) => {
              const connection = connectionStatuses[source.id];
              const sourceStreams = streams.filter((stream) => stream.source_id === source.id);
              const livePlaybackLabel = connection
                ? connection.supports_live_playback
                  ? "Supported"
                  : "Not available"
                : "Loading";
              const zoneEditingLabel = connection
                ? connection.supports_zone_editing
                  ? "Available"
                  : "Unavailable"
                : "Loading";
              return (
                <section className="source-connection-card" key={source.id}>
                  <div className="item-title-row">
                    <h3>{source.name}</h3>
                    {connection ? (
                      <StatusPill
                        label={formatLabel(connection.status)}
                        tone={connectionTone(connection.status)}
                      />
                    ) : (
                      <StatusPill label="Loading" tone="quiet" />
                    )}
                  </div>
                  <p>{connection?.message ?? source.description}</p>
                  <div className="source-connection-meta">
                    <span>{connection?.stream_ids.length ?? sourceStreams.length} streams</span>
                    <span>Live playback: {livePlaybackLabel}</span>
                    <span>Zone editing: {zoneEditingLabel}</span>
                  </div>
                  {connection?.setup_hint ? (
                    <span className="meta-text">{connection.setup_hint}</span>
                  ) : null}
                </section>
              );
            })}
          </div>
        </section>
      ) : null}
      {selectedSource ? (
        <section className="panel source-setup-panel">
          <div className="section-heading">
            <div>
              <h2>Source setup</h2>
              <span className="meta-text">Configuration metadata only</span>
            </div>
            {selectedConnection ? (
              <StatusPill
                label={formatLabel(selectedConnection.status)}
                tone={connectionTone(selectedConnection.status)}
              />
            ) : null}
          </div>
          <div className="source-setup-layout">
            <div className="source-setup-summary">
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
              <div className="source-setup-copy">
                <p>MockingBird will not connect to this Source yet.</p>
                <p>Live playback requires a future provider implementation.</p>
                <p>Zone editing can continue with placeholders/demo panels.</p>
              </div>
              {selectedSetupReview ? (
                <div className="source-review-panel">
                  <div className="item-title-row">
                    <h3>Source setup review</h3>
                    <StatusPill
                      label={formatLabel(selectedSetupReview.readiness_level)}
                      tone={readinessTone(selectedSetupReview.readiness_level)}
                    />
                  </div>
                  <p>{selectedSetupReview.summary}</p>
                  <div className="source-review-next">
                    <strong>Next step</strong>
                    <span>{selectedSetupReview.next_step}</span>
                    {selectedSetupReview.provider_key === "manual_media" &&
                    selectedSetupReview.readiness_level === "metadata_ready" ? (
                      <button className="secondary-action" onClick={onOpenImport} type="button">
                        Import media
                      </button>
                    ) : null}
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
                  {selectedSetupReview.warnings.length > 0 ? (
                    <div className="source-warning-list">
                      {selectedSetupReview.warnings.map((warning) => (
                        <span key={warning}>{warning}</span>
                      ))}
                    </div>
                  ) : null}
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
                  <div className="source-review-stream-list">
                    <strong>Related Streams</strong>
                    {selectedSetupReview.streams.length > 0 ? (
                      selectedSetupReview.streams.map((stream) => (
                        <div className="source-review-stream" key={stream.stream_id}>
                          <div className="item-title-row">
                            <span>{stream.display_name}</span>
                            <StatusPill label={formatLabel(stream.playback_status)} />
                          </div>
                          <p>{stream.message}</p>
                          <span className="meta-text">
                            Playback readiness: {formatLabel(stream.playback_kind)} · Live playback:{" "}
                            {stream.supports_live_playback ? "Available" : "Not available"} · Zone
                            editing: {stream.supports_zone_editing ? "Available" : "Unavailable"}
                          </span>
                        </div>
                      ))
                    ) : (
                      <span className="meta-text">No related Streams yet.</span>
                    )}
                  </div>
                </div>
              ) : null}
              {selectedConfiguration ? (
                <div className="source-field-summary">
                  <div>
                    <strong>Configured</strong>
                    <div className="source-field-tags">
                      {selectedConfiguration.configured_fields.length > 0 ? (
                        selectedConfiguration.configured_fields.map((field) => (
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
                      {selectedConfiguration.missing_fields.length > 0 ? (
                        selectedConfiguration.missing_fields.map((field) => (
                          <span key={field}>{formatLabel(field)}</span>
                        ))
                      ) : (
                        <span>None</span>
                      )}
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
            <form className="source-setup-form" onSubmit={handleSaveProviderConfiguration}>
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
        </section>
      ) : null}
      <div className="stream-list">
        {streams.length > 0 ? (
          streams.map((stream) => {
            const connection = connectionStatuses[stream.source_id];
            const streamLabel =
              connection?.status === "demo" ? "Demo panel" : stream.is_live ? "Stream" : "Offline";
            return (
              <section className="stream-list-item" key={stream.id}>
                <div>
                  <div className="item-title-row">
                    <h2>{stream.name}</h2>
                    <StatusPill
                      label={streamLabel}
                      tone={connection?.status === "demo" || stream.is_live ? "good" : "quiet"}
                    />
                  </div>
                  <p>{stream.description}</p>
                  <span className="meta-text">
                    Source: {sourceNames.get(stream.source_id) ?? stream.source_id}
                  </span>
                </div>
                <button className="primary-action" onClick={() => onOpenStream(stream.id)}>
                  Open stream
                </button>
              </section>
            );
          })
        ) : (
          <EmptyState
            title="No streams available"
            description="Streams will become the center of review once a source is connected."
          />
        )}
      </div>
    </div>
  );
}
