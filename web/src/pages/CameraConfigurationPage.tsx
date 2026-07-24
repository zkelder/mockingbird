import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type {
  CameraConfigurationEditResponse,
  CameraConfigurationImpactPreview,
  CameraConfigurationSecretAction,
  CameraNodePairResponse,
} from "../api/types";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel } from "../utils";

interface CameraConfigurationPageProps {
  streamId: string;
  onCancel: () => void;
  onSaved: () => Promise<void>;
}

function idempotencyKey() {
  return `camera-configuration-${globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`}`;
}

function healthTone(state: CameraConfigurationEditResponse["health"]["state"]): "good" | "review" | "quiet" {
  if (state === "healthy") return "good";
  if (state === "starting" || state === "stopped") return "quiet";
  return "review";
}

function configurationPayload(
  configuration: CameraConfigurationEditResponse,
  values: Record<string, string>,
  secretActions: Record<string, CameraConfigurationSecretAction>,
  sourceName: string,
  streamName: string,
  nodePairing: CameraNodePairResponse | null,
  selectedNodeCameraId: string,
) {
  const config: Record<string, string | null> = {};
  if (configuration.provider_key === "camera_node" && nodePairing) {
    config.node_camera_id = selectedNodeCameraId;
    return {
      provider_key: configuration.provider_key,
      config,
      secret_actions: {},
      node_pairing_token: nodePairing.pairing_token,
      source_name: sourceName.trim() || null,
      stream_name: streamName.trim() || null,
      expected_state_token: configuration.state_token,
    };
  }
  for (const field of configuration.editable_fields) {
    const value = values[field.key]?.trim();
    if (field.secret) {
      if (secretActions[field.key] === "replace" && value) {
        config[field.key] = value;
      }
    } else if (value) {
      config[field.key] = value;
    }
  }
  return {
    provider_key: configuration.provider_key,
    config,
    secret_actions: secretActions,
    source_name: sourceName.trim() || null,
    stream_name: streamName.trim() || null,
    expected_state_token: configuration.state_token,
  };
}

export function CameraConfigurationPage({ streamId, onCancel, onSaved }: CameraConfigurationPageProps) {
  const [configuration, setConfiguration] = useState<CameraConfigurationEditResponse | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [secretActions, setSecretActions] = useState<Record<string, CameraConfigurationSecretAction>>({});
  const [sourceName, setSourceName] = useState("");
  const [streamName, setStreamName] = useState("");
  const [preview, setPreview] = useState<CameraConfigurationImpactPreview | null>(null);
  const [history, setHistory] = useState<CameraConfigurationImpactPreview["changed_fields"][]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [restartMonitoring, setRestartMonitoring] = useState(false);
  const [nodeAddress, setNodeAddress] = useState("");
  const [pairingCode, setPairingCode] = useState("");
  const [nodePairing, setNodePairing] = useState<CameraNodePairResponse | null>(null);
  const [selectedNodeCameraId, setSelectedNodeCameraId] = useState("");
  const [isPairingNode, setIsPairingNode] = useState(false);
  const [isRevokingNode, setIsRevokingNode] = useState(false);

  const canSave = Boolean(preview?.validation.can_apply && preview.changed_fields.length > 0);
  const secretFields = useMemo(
    () => configuration?.editable_fields.filter((field) => field.secret) ?? [],
    [configuration],
  );

  async function load() {
    setIsLoading(true);
    try {
      const [nextConfiguration, nextHistory] = await Promise.all([
        apiClient.getCameraConfiguration(streamId),
        apiClient.getCameraConfigurationHistory(streamId),
      ]);
      setConfiguration(nextConfiguration);
      setSourceName(nextConfiguration.source_name);
      setStreamName(nextConfiguration.stream_name);
      setValues({});
      setSecretActions(
        Object.fromEntries(
          nextConfiguration.editable_fields
            .filter((field) => field.secret)
            .map((field) => [field.key, "keep"]),
        ),
      );
      setHistory(nextHistory.items.map((item) => item.changed_fields));
      setPreview(null);
      setRestartMonitoring(false);
      setError(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Camera configuration could not be loaded.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [streamId]);

  async function previewChanges() {
    if (!configuration) return;
    setIsPreviewing(true);
    setError(null);
    setMessage(null);
    try {
      setPreview(await apiClient.previewCameraConfiguration(
        streamId,
        configurationPayload(configuration, values, secretActions, sourceName, streamName, nodePairing, selectedNodeCameraId),
      ));
    } catch (caught) {
      setPreview(null);
      setError(caught instanceof Error ? caught.message : "Camera configuration could not be previewed.");
    } finally {
      setIsPreviewing(false);
    }
  }

  async function pairNodeForRepair() {
    setIsPairingNode(true);
    setError(null);
    setPreview(null);
    try {
      const pairing = await apiClient.pairCameraNode({ base_address: nodeAddress, pairing_code: pairingCode });
      setNodePairing(pairing);
      const initialCamera = pairing.cameras.find((camera) => camera.status === "available" && camera.snapshot_supported)?.camera_id ?? "";
      setSelectedNodeCameraId(initialCamera);
      setPairingCode("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Camera Node pairing could not be completed.");
    } finally {
      setIsPairingNode(false);
    }
  }

  async function revokeNodePairing() {
    if (!configuration) return;
    setIsRevokingNode(true);
    setError(null);
    try {
      await apiClient.revokeCameraNodePairing({ stream_id: configuration.stream_id });
      setNodePairing(null);
      setPreview(null);
      setMessage("Camera Node pairing was revoked. Existing Zones, activity, evidence, reviews, and history stay intact.");
      await onSaved();
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Camera Node pairing could not be revoked.");
    } finally {
      setIsRevokingNode(false);
    }
  }

  async function save() {
    if (!configuration || !preview || !canSave) return;
    setIsSaving(true);
    setError(null);
    try {
      const result = await apiClient.applyCameraConfiguration(streamId, {
        ...configurationPayload(configuration, values, secretActions, sourceName, streamName, nodePairing, selectedNodeCameraId),
        preview_token: preview.preview_token,
        idempotency_key: idempotencyKey(),
        restart_monitoring: restartMonitoring,
      });
      setConfiguration(result.configuration);
      setSourceName(result.configuration.source_name);
      setStreamName(result.configuration.stream_name);
      setValues({});
      setSecretActions(
        Object.fromEntries(secretFields.map((field) => [field.key, "keep"])),
      );
      setMessage(result.message);
      await onSaved();
      await load();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Camera configuration could not be saved.");
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) return <div className="panel">Loading camera configuration…</div>;
  if (!configuration) return <div className="error-panel">{error ?? "Camera configuration is unavailable."}</div>;

  return (
    <div className="page-stack">
      <section className="page-header">
        <div>
          <span className="eyebrow">Guided camera setup</span>
          <h1>Edit Camera Setup</h1>
          <p>Update this existing camera in place. Its Stream, Zones, activity, evidence, reviews, map placement, alerts, and health history stay connected.</p>
        </div>
        <button className="secondary-action" onClick={onCancel} type="button">Back to Stream</button>
      </section>

      {!configuration.editable ? (
        <section className="panel"><strong>{configuration.message}</strong><p className="meta-text">Add a separate camera to use a different provider. Existing history remains unchanged.</p></section>
      ) : (
        <>
          <section className="panel page-stack">
            <div className="section-heading"><div><h2>Camera configuration</h2><span className="meta-text">{configuration.provider_display_name} is fixed for this camera. Saved values are never shown here.</span></div></div>
            <label>Camera name<input value={sourceName} onChange={(event) => { setSourceName(event.target.value); setPreview(null); }} /></label>
            <label>Stream name<input value={streamName} onChange={(event) => { setStreamName(event.target.value); setPreview(null); }} /></label>
            {configuration.provider_key === "camera_node" ? <div className="notice-panel">
              <strong>Repair or change Camera Node view</strong>
              <span>Pairing is explicit. Enter the Node’s address and one-time local code to repair pairing or choose another advertised camera from the same Node. The saved address and credential remain masked.</span>
              <label>Node address<input onChange={(event) => { setNodeAddress(event.target.value); setPreview(null); }} placeholder="http://192.168.1.50:8787" value={nodeAddress} /></label>
              <label>One-time pairing code<input onChange={(event) => setPairingCode(event.target.value)} type="password" value={pairingCode} /></label>
              <button className="secondary-action" disabled={!nodeAddress || !pairingCode || isPairingNode} onClick={() => void pairNodeForRepair()} type="button">{isPairingNode ? "Pairing…" : "Pair or repair Node"}</button>
              <button className="secondary-action" disabled={isRevokingNode} onClick={() => void revokeNodePairing()} type="button">{isRevokingNode ? "Revoking…" : "Revoke current pairing"}</button>
              {nodePairing ? <><span><strong>Node found:</strong> {nodePairing.display_name} ({nodePairing.api_version})</span>
                <label>Camera view<select onChange={(event) => { setSelectedNodeCameraId(event.target.value); setPreview(null); }} value={selectedNodeCameraId}>
                  <option value="">Choose an advertised camera</option>
                  {nodePairing.cameras.map((camera) => <option disabled={camera.status !== "available" || !camera.snapshot_supported} key={camera.camera_id} value={camera.camera_id}>{camera.display_name} — {camera.status.replace(/_/g, " ")}</option>)}
                </select></label>
              </> : <span className="meta-text">You can still rename this Camera or Stream without re-pairing.</span>}
            </div> : configuration.editable_fields.map((field) => (
              <div className="page-stack" key={field.key}>
                <label>{field.label}{field.required ? " (required)" : ""}
                  {field.secret ? (
                    <>
                      <select value={secretActions[field.key] ?? "keep"} onChange={(event) => { setSecretActions((current) => ({ ...current, [field.key]: event.target.value as CameraConfigurationSecretAction })); setPreview(null); }}>
                        <option value="keep">Keep saved value</option>
                        <option value="replace">Replace saved value</option>
                        <option value="remove">Remove saved value</option>
                      </select>
                      {secretActions[field.key] === "replace" ? <input autoComplete="new-password" onChange={(event) => { setValues((current) => ({ ...current, [field.key]: event.target.value })); setPreview(null); }} placeholder="Enter replacement" type="password" value={values[field.key] ?? ""} /> : null}
                    </>
                  ) : (
                    <input onChange={(event) => { setValues((current) => ({ ...current, [field.key]: event.target.value })); setPreview(null); }} placeholder={configuration.field_states[field.key] === "configured" ? "Configured — enter a replacement to change" : "Not configured — enter a value"} type="text" value={values[field.key] ?? ""} />
                  )}
                </label>
                <span className="meta-text">{field.description ?? (field.secret ? "Saved locally and shown only as configured or not configured." : "Enter a replacement only when you want to change this setting.")}</span>
              </div>
            ))}
            <button className="secondary-action" disabled={isPreviewing} onClick={() => void previewChanges()} type="button">{isPreviewing ? "Checking impact…" : "Validate and preview impact"}</button>
            <span className="meta-text">{configuration.provider_key === "camera_node" && nodePairing ? "Pairing contacted the Node explicitly; the impact preview does not start monitoring, save media, create activity, or create reviewed truth." : "Validation checks saved configuration only. It does not contact the camera, start monitoring, save media, create activity, or create reviewed truth."}</span>
          </section>

          {preview ? <section className="panel page-stack" aria-label="Camera configuration impact preview">
            <div className="section-heading"><div><h2>Review impact</h2><span className="meta-text">{preview.validation.message}</span></div><StatusPill label={preview.validation.status.replace(/_/g, " ")} tone={preview.validation.can_apply ? "good" : "review"} /></div>
            <span><strong>Changed settings:</strong> {preview.changed_fields.length ? preview.changed_fields.join(", ") : "None"}</span>
            <span><strong>Monitoring desired:</strong> {formatLabel(preview.monitoring_desired)} · <strong>actual:</strong> {formatLabel(preview.monitoring_actual)}</span>
            <span><strong>Open activity sessions:</strong> {preview.open_activity_session_count}</span>
            {preview.restart_required ? <div className="notice-panel"><strong>Brief preview interruption expected.</strong><span>MockingBird will stop the current local session before storing this runtime-affecting change. Existing reviewed activity and saved history are preserved.</span>{preview.requires_explicit_restart_choice ? <label><input checked={restartMonitoring} onChange={(event) => setRestartMonitoring(event.target.checked)} type="checkbox" /> Restart the already-enabled monitor after saving</label> : null}</div> : <span className="meta-text">This edit does not require a local camera restart.</span>}
            <div className="page-stack"><strong>Preserved</strong>{preview.preservation_summary.map((item) => <span className="meta-text" key={item}>{item}</span>)}</div>
            <button className="primary-action" disabled={!canSave || isSaving} onClick={() => void save()} type="button">{isSaving ? "Saving…" : preview.restart_required && restartMonitoring ? "Save and restart monitoring" : "Save camera configuration"}</button>
          </section> : null}
        </>
      )}

      {message ? <div className="notice-panel"><strong>Saved</strong><span>{message}</span></div> : null}
      {error ? <div className="error-panel">{error}</div> : null}

      <section className="panel page-stack" aria-label="Current camera health">
        <div className="section-heading"><div><h2>Camera health and next actions</h2><span className="meta-text">Saved operational state is separate from wildlife activity and review truth.</span></div><StatusPill label={formatLabel(configuration.health.state)} tone={healthTone(configuration.health.state)} /></div>
        <span><strong>Desired monitoring:</strong> {formatLabel(configuration.monitoring_policy.mode)} · <strong>actual:</strong> {formatLabel(configuration.runtime.actual_state)}</span>
        <span><strong>Open activity sessions:</strong> {configuration.health.open_activity_session_count}</span>
        <span><strong>Last good frame:</strong> {configuration.health.last_good_frame_at ? formatDateTime(configuration.health.last_good_frame_at) : "Not yet received"}</span>
        <span className="meta-text">{configuration.health.message}</span>
        <button className="secondary-action" onClick={onCancel} type="button">Open Stream Detail</button>
      </section>

      {history.length ? <section className="panel page-stack"><h2>Recent configuration history</h2>{history.map((changedFields, index) => <span className="meta-text" key={`${changedFields.join("-")}-${index}`}>{changedFields.join(", ") || "Configuration revision"}</span>)}</section> : null}
    </div>
  );
}
