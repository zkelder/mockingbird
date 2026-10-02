import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type {
  CameraConfigurationEditResponse,
  CameraConfigurationImpactPreview,
  CameraConfigurationSecretAction,
  CameraNodeHardwareHealthResponse,
  CameraNodePairResponse,
} from "../api/types";
import { StatusPill } from "../components/StatusPill";
import { cameraHealthLabel, cameraHealthTone, formatBytes, formatDateTime, formatLabel, userFacingErrorMessage } from "../utils";

// Product Operations & First-Observation Completion v1: the same graduated
// storage-tier labels ProductHealthPanel.tsx already uses for the Host's
// own disk -- duplicated, not imported (each surface reads a different
// underlying fact: the Host's own disk there, a Camera Node's own disk
// here), matching this product's established cross-boundary convention
// (see mockingbird_node/hardware_health.py's own identical duplication of
// the Host's threshold values, for the same reason).
const CAMERA_NODE_STORAGE_TIER_LABEL: Record<string, string> = {
  healthy: "Healthy",
  getting_low: "Getting low",
  action_recommended: "Action recommended",
  critical: "Critically low",
};

interface CameraConfigurationPageProps {
  streamId: string;
  onCancel: () => void;
  onSaved: () => Promise<void>;
}

function idempotencyKey() {
  return `camera-configuration-${globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`}`;
}

// Multi-Camera Place Experience v2: this page used to define its own
// local, 3-tone `healthTone` (no "alert" tone) and render the state via
// generic `formatLabel` (Title Case) -- so `camera_unavailable`/`no_
// recent_frame` rendered as merely "review" here instead of "alert," and
// the same state's label text literally differed between pages ("Camera
// Unavailable" here vs. "Camera unavailable" on Dashboard/Yard Map).
// Reuses the canonical `cameraHealthTone`/`cameraHealthLabel` (utils.ts)
// every other health surface already converged on, rather than a third
// drifting copy.

function configurationPayload(
  configuration: CameraConfigurationEditResponse,
  values: Record<string, string>,
  secretActions: Record<string, CameraConfigurationSecretAction>,
  sourceName: string,
  streamName: string,
  nodePairing: CameraNodePairResponse | null,
  selectedNodeCameraId: string,
  confirmReplacement: boolean,
  replacementReason: string,
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
      confirm_node_identity_change: confirmReplacement,
      replacement_reason: replacementReason.trim() || null,
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
  const [isCheckingNodeResume, setIsCheckingNodeResume] = useState(false);
  const [nodePairingNeedsRenewal, setNodePairingNeedsRenewal] = useState(false);
  const [isCancelingNodePairing, setIsCancelingNodePairing] = useState(false);
  // Reprovision / Replacement Recovery v1: deliberate, operator-confirmed
  // override for a genuine Camera Node hardware swap -- see
  // docs/camera-node-reprovision-recovery-design.md.
  const [confirmReplacement, setConfirmReplacement] = useState(false);
  const [replacementReason, setReplacementReason] = useState("");
  // Product Operations & First-Observation Completion v1: bounded, live,
  // on-demand -- never polled automatically, matching "Check the picture"'s
  // own established human-initiated pattern in CameraSetupPage.tsx.
  const [hardwareHealth, setHardwareHealth] = useState<CameraNodeHardwareHealthResponse | null>(null);
  const [isCheckingHardwareHealth, setIsCheckingHardwareHealth] = useState(false);
  const [hardwareHealthError, setHardwareHealthError] = useState<string | null>(null);

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
      setConfirmReplacement(false);
      setReplacementReason("");
      setError(null);
    } catch (caught) {
      setError(userFacingErrorMessage(caught, "Camera configuration could not be loaded."));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [streamId]);

  async function checkHardwareHealth() {
    setIsCheckingHardwareHealth(true);
    setHardwareHealthError(null);
    try {
      setHardwareHealth(await apiClient.getStreamCameraNodeHardwareHealth(streamId));
    } catch (caught) {
      setHardwareHealthError(
        userFacingErrorMessage(caught, "Could not check the Camera Node right now."),
      );
    } finally {
      setIsCheckingHardwareHealth(false);
    }
  }

  // Repair's "Pair or repair Node" durably persists its credential the
  // instant the Node accepts it -- before this page ever gets a chance to
  // save it onto the Stream (see create_camera_node_pending_setup). Without
  // resuming it here, a refresh, a closed tab, or simply not reaching Save
  // yet orphans that already-consumed one-time code: the only visible
  // recourse would be re-entering it, which the Node correctly (and
  // permanently) refuses a second time. Mirrors first-run's own resume
  // check in CameraSetupPage.tsx; scoped to this Stream's own Camera Node
  // identity so an unrelated in-progress Add Camera pairing is never
  // surfaced here as if it belonged to this repair.
  useEffect(() => {
    if (!configuration || !configuration.editable || configuration.provider_key !== "camera_node") return;
    let cancelled = false;
    setIsCheckingNodeResume(true);
    void apiClient.getCameraConfigurationPendingPairing(streamId)
      .then((resumed) => {
        if (cancelled) return;
        if (resumed.status === "needs_renewal") {
          setNodePairingNeedsRenewal(true);
          setNodePairing(null);
          return;
        }
        setNodePairingNeedsRenewal(false);
        setNodePairing({
          pairing_token: resumed.pairing_token,
          node_id: resumed.node_id,
          display_name: resumed.display_name,
          api_version: resumed.api_version,
          cameras: resumed.cameras,
          message: resumed.message,
        });
        setSelectedNodeCameraId(resumed.selected_camera_id ?? "");
        setPairingCode("");
      })
      .catch(() => {
        // Nothing resumable (a plain 404) or the check itself failed --
        // either way this fails open into the normal "enter a code" form,
        // exactly like first-run's own resume check. Never blocks the page.
      })
      .finally(() => {
        if (!cancelled) setIsCheckingNodeResume(false);
      });
    return () => {
      cancelled = true;
    };
  }, [streamId, configuration?.provider_key, configuration?.editable]);

  async function previewChanges() {
    if (!configuration) return;
    setIsPreviewing(true);
    setError(null);
    setMessage(null);
    try {
      setPreview(await apiClient.previewCameraConfiguration(
        streamId,
        configurationPayload(configuration, values, secretActions, sourceName, streamName, nodePairing, selectedNodeCameraId, confirmReplacement, replacementReason),
      ));
    } catch (caught) {
      setPreview(null);
      setError(userFacingErrorMessage(caught, "Camera configuration could not be previewed."));
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
      setNodePairingNeedsRenewal(false);
      const initialCamera = pairing.cameras.find((camera) => camera.status === "available" && camera.snapshot_supported)?.camera_id ?? "";
      setSelectedNodeCameraId(initialCamera);
      setPairingCode("");
    } catch (caught) {
      setError(userFacingErrorMessage(caught, "Camera Node pairing could not be completed."));
    } finally {
      setIsPairingNode(false);
    }
  }

  async function cancelNodePairingAttempt() {
    if (!nodePairing) return;
    setIsCancelingNodePairing(true);
    setError(null);
    try {
      await apiClient.revokeCameraNodePendingSetup({ pairing_token: nodePairing.pairing_token });
      setNodePairing(null);
      setSelectedNodeCameraId("");
      setNodePairingNeedsRenewal(false);
    } catch (caught) {
      setError(userFacingErrorMessage(caught, "This pairing attempt could not be canceled right now."));
    } finally {
      setIsCancelingNodePairing(false);
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
      setError(userFacingErrorMessage(caught, "Camera Node pairing could not be revoked."));
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
        ...configurationPayload(configuration, values, secretActions, sourceName, streamName, nodePairing, selectedNodeCameraId, confirmReplacement, replacementReason),
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
      setConfirmReplacement(false);
      setReplacementReason("");
      setMessage(result.message);
      await onSaved();
      await load();
    } catch (caught) {
      setError(userFacingErrorMessage(caught, "Camera configuration could not be saved."));
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
              <span>Pairing is explicit. Enter the Node’s address and one-time local code to repair pairing, replace this camera's hardware, or choose another advertised camera from the same Node. The saved address and credential remain masked.</span>
              {configuration.hardware_replacement ? <div className="notice-panel">
                <strong>Hardware replaced {formatDateTime(configuration.hardware_replacement.replaced_at)}</strong>
                <span>This camera's Zones, monitoring history, and reviewed truth stayed attached across the swap. MockingBird could not verify the replacement camera's framing matches the original — review Zones if you have not already.{configuration.hardware_replacement.reason ? ` Reason given: ${configuration.hardware_replacement.reason}` : ""}</span>
              </div> : null}
              {configuration.node_expected_display_name ? <span className="meta-text">Reinstalling the same Node? Give it the name “{configuration.node_expected_display_name}” to reattach automatically without confirming a hardware replacement below.</span> : null}
              {isCheckingNodeResume ? <span className="meta-text">Checking for an already-paired repair attempt…</span> : null}
              {nodePairingNeedsRenewal ? <div className="error-panel">
                <strong>Pairing needs to be renewed</strong>
                <span>MockingBird found an earlier repair pairing for this Camera Node, but it is no longer accepted. Pair again below with a new one-time code.</span>
              </div> : null}
              <label>Node address<input onChange={(event) => { setNodeAddress(event.target.value); setPreview(null); }} placeholder="http://192.168.1.50:8787" value={nodeAddress} /></label>
              <label>One-time pairing code<input autoComplete="one-time-code" onChange={(event) => setPairingCode(event.target.value)} type="password" value={pairingCode} /></label>
              <button className="secondary-action" disabled={!nodeAddress || !pairingCode || isPairingNode} onClick={() => void pairNodeForRepair()} type="button">{isPairingNode ? "Pairing…" : "Pair or repair Node"}</button>
              <button className="secondary-action" disabled={isRevokingNode} onClick={() => void revokeNodePairing()} type="button">{isRevokingNode ? "Revoking…" : "Revoke current pairing"}</button>
              {nodePairing ? <><span><strong>Node found:</strong> {nodePairing.display_name} ({nodePairing.api_version})</span>
                <label>Camera view<select onChange={(event) => { setSelectedNodeCameraId(event.target.value); setPreview(null); }} value={selectedNodeCameraId}>
                  <option value="">Choose an advertised camera</option>
                  {nodePairing.cameras.map((camera) => <option disabled={camera.status !== "available" || !camera.snapshot_supported} key={camera.camera_id} value={camera.camera_id}>{camera.display_name}{camera.provider_type ? ` (${camera.provider_type})` : ""} — {camera.status.replace(/_/g, " ")}</option>)}
                </select></label>
                <label><input checked={confirmReplacement} onChange={(event) => { setConfirmReplacement(event.target.checked); setPreview(null); }} type="checkbox" /> This is a different physical Camera Node (hardware replacement), not the same device</label>
                {confirmReplacement ? <label>Reason (optional)<input onChange={(event) => { setReplacementReason(event.target.value); setPreview(null); }} placeholder="e.g. SD card failed, upgraded to a new Pi" value={replacementReason} /></label> : null}
                <button className="secondary-action" disabled={isCancelingNodePairing} onClick={() => void cancelNodePairingAttempt()} type="button">{isCancelingNodePairing ? "Canceling…" : "Cancel this pairing attempt"}</button>
                <span className="meta-text">Canceling revokes this not-yet-saved pairing at the Camera Node so it stops advertising it as paired; a new one-time code will be needed afterward.</span>
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
            {preview.node_identity_replacement ? <div className="notice-panel"><strong>Camera Node hardware replacement</strong><span>{preview.node_identity_replacement.message}</span></div> : null}
            <div className="page-stack"><strong>Preserved</strong>{preview.preservation_summary.map((item) => <span className="meta-text" key={item}>{item}</span>)}</div>
            <button className="primary-action" disabled={!canSave || isSaving} onClick={() => void save()} type="button">{isSaving ? "Saving…" : preview.restart_required && restartMonitoring ? "Save and restart monitoring" : "Save camera configuration"}</button>
          </section> : null}
        </>
      )}

      {message ? <div className="notice-panel"><strong>Saved</strong><span>{message}</span></div> : null}
      {error ? <div className="error-panel">{error}</div> : null}

      <section className="panel page-stack" aria-label="Current camera health">
        <div className="section-heading"><div><h2>Camera health and next actions</h2><span className="meta-text">Saved operational state is separate from wildlife activity and review truth.</span></div><StatusPill label={cameraHealthLabel(configuration.health.state)} tone={cameraHealthTone(configuration.health.state)} /></div>
        <span><strong>Desired monitoring:</strong> {formatLabel(configuration.monitoring_policy.mode)} · <strong>actual:</strong> {formatLabel(configuration.runtime.actual_state)}</span>
        <span><strong>Open activity sessions:</strong> {configuration.health.open_activity_session_count}</span>
        <span><strong>Last good frame:</strong> {configuration.health.last_good_frame_at ? formatDateTime(configuration.health.last_good_frame_at) : "Not yet received"}</span>
        <span className="meta-text">{configuration.health.message}</span>
        <button className="secondary-action" onClick={onCancel} type="button">Open Stream Detail</button>
      </section>

      {configuration.provider_key === "camera_node" ? (
        <section className="panel page-stack" aria-label="Camera Node hardware">
          <div className="section-heading">
            <div>
              <h2>Camera Node hardware</h2>
              <span className="meta-text">
                A live, on-demand check of this Camera Node's own storage and hardware quality --
                separate from the camera health above.
              </span>
            </div>
          </div>
          <button
            className="secondary-action"
            disabled={isCheckingHardwareHealth}
            onClick={() => void checkHardwareHealth()}
            type="button"
          >
            {isCheckingHardwareHealth ? "Checking…" : "Check Camera Node hardware"}
          </button>
          {hardwareHealthError ? <div className="error-panel">{hardwareHealthError}</div> : null}
          {hardwareHealth && !hardwareHealthError ? (
            !hardwareHealth.reachable ? (
              <span className="meta-text">{hardwareHealth.message}</span>
            ) : (
              <div className="monitoring-continuity-facts">
                {hardwareHealth.storage ? (
                  <span>
                    <strong>Storage</strong>{" "}
                    {CAMERA_NODE_STORAGE_TIER_LABEL[hardwareHealth.storage.storage_health_tier] ??
                      formatLabel(hardwareHealth.storage.storage_health_tier)}{" "}
                    ({formatBytes(hardwareHealth.storage.free_bytes)} free of{" "}
                    {formatBytes(hardwareHealth.storage.total_bytes)})
                  </span>
                ) : (
                  <span className="meta-text">Storage: not available for this Node.</span>
                )}
                {hardwareHealth.hardware ? (
                  <>
                    <span>
                      <strong>Power</strong>{" "}
                      {hardwareHealth.hardware.undervoltage_active ? "Undervoltage detected" : "Normal"}
                    </span>
                    <span>
                      <strong>Temperature</strong>{" "}
                      {hardwareHealth.hardware.temperature_celsius !== null
                        ? `${hardwareHealth.hardware.temperature_celsius.toFixed(1)}°C`
                        : "Unknown"}
                    </span>
                  </>
                ) : (
                  <span className="meta-text">Hardware quality: not available for this Node.</span>
                )}
                <span className="meta-text">Checked {formatDateTime(hardwareHealth.checked_at)}</span>
              </div>
            )
          ) : null}
        </section>
      ) : null}

      {history.length ? <section className="panel page-stack"><h2>Recent configuration history</h2>{history.map((changedFields, index) => <span className="meta-text" key={`${changedFields.join("-")}-${index}`}>{changedFields.join(", ") || "Configuration revision"}</span>)}</section> : null}
    </div>
  );
}
