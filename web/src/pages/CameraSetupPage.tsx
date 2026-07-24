import { useEffect, useMemo, useRef, useState, type PointerEvent } from "react";
import { apiClient } from "../api/client";
import type {
  CameraSetupOption,
  CameraSetupValidationResponse,
  CameraNodePairResponse,
  Point,
  ZoneActivitySensitivity,
  ZoneType,
} from "../api/types";

interface CameraSetupPageProps {
  onComplete: (streamId: string) => void;
  onCancel: () => void;
  onSourcesChanged: () => void;
}

const defaultPolygon: Point[] = [
  { x: 0.2, y: 0.2 },
  { x: 0.8, y: 0.2 },
  { x: 0.8, y: 0.8 },
  { x: 0.2, y: 0.8 },
];
const DRAFT_KEY = "mockingbird-camera-setup-draft-v1";

interface CameraSetupDraftState {
  providerKey?: string;
  config?: Record<string, string>;
  cameraName?: string;
  streamName?: string;
  zoneName?: string;
  zoneType?: ZoneType;
  polygon?: Point[];
  sensitivity?: ZoneActivitySensitivity;
  monitoringEnabled?: boolean;
}

function readDraft(): CameraSetupDraftState {
  try {
    return JSON.parse(window.sessionStorage.getItem(DRAFT_KEY) ?? "{}") as CameraSetupDraftState;
  } catch {
    return {};
  }
}

function setupKey() {
  return `camera-setup-${crypto.randomUUID()}`;
}

export function CameraSetupPage({ onCancel, onComplete, onSourcesChanged }: CameraSetupPageProps) {
  const [initialDraft] = useState(readDraft);
  const [options, setOptions] = useState<CameraSetupOption[]>([]);
  const [providerKey, setProviderKey] = useState(initialDraft.providerKey ?? "");
  const [config, setConfig] = useState<Record<string, string>>(initialDraft.config ?? {});
  const [cameraName, setCameraName] = useState(initialDraft.cameraName ?? "");
  const [streamName, setStreamName] = useState(initialDraft.streamName ?? "");
  const [zoneName, setZoneName] = useState(initialDraft.zoneName ?? "Activity area");
  const [zoneType, setZoneType] = useState<ZoneType>(initialDraft.zoneType ?? "feeder");
  const [polygon, setPolygon] = useState<Point[]>(initialDraft.polygon ?? defaultPolygon);
  const [sensitivity, setSensitivity] = useState<ZoneActivitySensitivity>(initialDraft.sensitivity ?? "normal");
  const [monitoringEnabled, setMonitoringEnabled] = useState(initialDraft.monitoringEnabled ?? false);
  const [validation, setValidation] = useState<CameraSetupValidationResponse | null>(null);
  const [nodeAddress, setNodeAddress] = useState("");
  const [pairingCode, setPairingCode] = useState("");
  const [nodePairing, setNodePairing] = useState<CameraNodePairResponse | null>(null);
  const [selectedNodeCameraId, setSelectedNodeCameraId] = useState("");
  const [nodePreviewUrl, setNodePreviewUrl] = useState<string | null>(null);
  const [isLoadingNodePreview, setIsLoadingNodePreview] = useState(false);
  const [isPairingNode, setIsPairingNode] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isValidating, setIsValidating] = useState(false);
  const [isCompleting, setIsCompleting] = useState(false);
  const drawStart = useRef<Point | null>(null);

  const selected = useMemo(
    () => options.find((option) => option.provider_key === providerKey) ?? null,
    [options, providerKey],
  );

  useEffect(() => {
    void apiClient
      .getCameraSetupOptions()
      .then((response) => {
        setOptions(response.options);
        const first = response.options.find((option) => option.availability === "available_now");
        setProviderKey((current) => current || first?.provider_key || "");
      })
      .catch(() => setError("Camera setup options are unavailable."))
      .finally(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    window.sessionStorage.setItem(DRAFT_KEY, JSON.stringify({
      providerKey, config, cameraName, streamName, zoneName, zoneType, polygon, sensitivity, monitoringEnabled,
    }));
  }, [providerKey, config, cameraName, streamName, zoneName, zoneType, polygon, sensitivity, monitoringEnabled]);

  useEffect(() => () => {
    if (nodePreviewUrl) URL.revokeObjectURL(nodePreviewUrl);
  }, [nodePreviewUrl]);

  function pointAt(event: PointerEvent<HTMLDivElement>): Point {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
      y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)),
    };
  }

  function finishDraw(event: PointerEvent<HTMLDivElement>) {
    const start = drawStart.current;
    drawStart.current = null;
    if (!start) return;
    const end = pointAt(event);
    const left = Math.min(start.x, end.x);
    const right = Math.max(start.x, end.x);
    const top = Math.min(start.y, end.y);
    const bottom = Math.max(start.y, end.y);
    if (right - left < 0.03 || bottom - top < 0.03) return;
    setPolygon([
      { x: left, y: top }, { x: right, y: top }, { x: right, y: bottom }, { x: left, y: bottom },
    ]);
  }

  async function validateSetup() {
    if (!selected) return;
    setIsValidating(true);
    setError(null);
    try {
      setValidation(await apiClient.validateCameraSetup({
        provider_key: selected.provider_key,
        config,
        node_pairing_token: selected.provider_key === "camera_node" ? nodePairing?.pairing_token : undefined,
      }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Camera configuration could not be validated.");
    } finally {
      setIsValidating(false);
    }
  }

  async function pairNode() {
    setIsPairingNode(true);
    setError(null);
    setValidation(null);
    try {
      const pairing = await apiClient.pairCameraNode({ base_address: nodeAddress, pairing_code: pairingCode });
      setNodePairing(pairing);
      const available = pairing.cameras.find((camera) => camera.status === "available" && camera.snapshot_supported);
      const cameraId = available?.camera_id ?? "";
      setSelectedNodeCameraId(cameraId);
      setConfig({ node_camera_id: cameraId });
      if (nodePreviewUrl) URL.revokeObjectURL(nodePreviewUrl);
      setNodePreviewUrl(null);
      setPairingCode("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Camera Node pairing could not be completed.");
    } finally {
      setIsPairingNode(false);
    }
  }

  async function previewNodeCamera(cameraId = selectedNodeCameraId) {
    if (!nodePairing || !cameraId) return;
    setIsLoadingNodePreview(true);
    setError(null);
    try {
      const image = await apiClient.previewCameraNode({
        pairing_token: nodePairing.pairing_token,
        camera_id: cameraId,
      });
      const nextUrl = URL.createObjectURL(image);
      if (nodePreviewUrl) URL.revokeObjectURL(nodePreviewUrl);
      setNodePreviewUrl(nextUrl);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Camera Node preview could not be loaded.");
    } finally {
      setIsLoadingNodePreview(false);
    }
  }

  async function complete() {
    if (!selected || !validation?.can_continue) return;
    setIsCompleting(true);
    setError(null);
    try {
      const result = await apiClient.completeCameraSetup({
        camera_name: cameraName,
        stream_name: streamName || `${cameraName} view`,
        provider_key: selected.provider_key,
        config,
        node_pairing_token: selected.provider_key === "camera_node" ? nodePairing?.pairing_token : undefined,
        zones: [{
          name: zoneName,
          zone_type: zoneType,
          polygon,
          is_active: true,
          monitoring_policy: zoneType === "privacy" || zoneType === "ignore"
            ? null
            : { activity_sensitivity: sensitivity },
        }],
        enable_monitoring: monitoringEnabled,
        idempotency_key: setupKey(),
      });
      onSourcesChanged();
      window.sessionStorage.removeItem(DRAFT_KEY);
      onComplete(result.stream.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Camera setup could not be completed.");
    } finally {
      setIsCompleting(false);
    }
  }

  if (isLoading) return <div className="panel">Loading camera setup…</div>;

  return (
    <div className="page-stack">
      <section className="page-header">
        <div>
          <span className="eyebrow">Guided setup</span>
          <h1>Add Camera</h1>
          <p>Set up a camera view, mark the parts of the image that matter, then choose whether monitoring should run.</p>
        </div>
        <button className="secondary-action" onClick={() => { window.sessionStorage.removeItem(DRAFT_KEY); onCancel(); }} type="button">Discard setup</button>
      </section>
      <section className="panel page-stack">
        <h2>1. Camera configuration</h2>
        <label>Camera type<select value={providerKey} onChange={(event) => { setProviderKey(event.target.value); setConfig({}); setValidation(null); setNodePairing(null); setSelectedNodeCameraId(""); if (nodePreviewUrl) URL.revokeObjectURL(nodePreviewUrl); setNodePreviewUrl(null); }}>
          {options.map((option) => <option key={option.provider_key} disabled={option.availability !== "available_now"} value={option.provider_key}>{option.display_name}{option.availability === "available_now" ? "" : " — unavailable"}</option>)}
        </select></label>
        {selected ? <><p className="meta-text">{selected.message}</p>
          {selected.provider_key === "camera_node" ? <div className="notice-panel">
            <strong>MockingBird Camera Node</strong>
            <span>Enter the Node’s explicit LAN address and its locally displayed one-time pairing code. MockingBird does not scan your network.</span>
            <label>Node address<input onChange={(event) => setNodeAddress(event.target.value)} placeholder="http://192.168.1.50:8787" value={nodeAddress} /></label>
            <label>One-time pairing code<input onChange={(event) => setPairingCode(event.target.value)} type="password" value={pairingCode} /></label>
            <button className="secondary-action" disabled={!nodeAddress || !pairingCode || isPairingNode} onClick={() => void pairNode()} type="button">{isPairingNode ? "Pairing…" : "Pair Camera Node"}</button>
            {nodePairing ? <><span><strong>Node found:</strong> {nodePairing.display_name} ({nodePairing.api_version})</span>
              <label>Camera view<select onChange={(event) => { setSelectedNodeCameraId(event.target.value); setConfig({ node_camera_id: event.target.value }); setValidation(null); if (nodePreviewUrl) URL.revokeObjectURL(nodePreviewUrl); setNodePreviewUrl(null); }} value={selectedNodeCameraId}>
                <option value="">Choose an advertised camera</option>
                {nodePairing.cameras.map((camera) => <option disabled={camera.status !== "available" || !camera.snapshot_supported} key={camera.camera_id} value={camera.camera_id}>{camera.display_name}{camera.provider_type ? ` (${camera.provider_type})` : ""} — {camera.status.replace(/_/g, " ")}</option>)}
              </select></label>
              <button className="secondary-action" disabled={!selectedNodeCameraId || isLoadingNodePreview} onClick={() => void previewNodeCamera()} type="button">{isLoadingNodePreview ? "Loading preview…" : "Inspect preview"}</button>
              {nodePreviewUrl ? <img alt="Transient Camera Node preview" className="camera-node-preview" src={nodePreviewUrl} /> : null}
              <span className="meta-text">Preview is one explicit, transient image. It is not saved, does not create activity, and monitoring remains off until you choose otherwise.</span>
            </> : null}
          </div> : selected.fields.map((field) => <label key={field.key}>{field.label}
            <input onChange={(event) => setConfig((current) => ({ ...current, [field.key]: event.target.value }))} placeholder={field.secret ? "Leave blank to keep masked" : field.placeholder ?? ""} type={field.secret ? "password" : "text"} value={config[field.key] ?? ""} />
          </label>)}</> : null}
        <label>Camera name<input onChange={(event) => setCameraName(event.target.value)} placeholder="Backyard feeder camera" value={cameraName} /></label>
        <label>Name this view<input onChange={(event) => setStreamName(event.target.value)} placeholder="Feeder view" value={streamName} /></label>
        <button className="secondary-action" disabled={!selected || isValidating} onClick={() => void validateSetup()} type="button">{isValidating ? "Validating…" : "Validate setup"}</button>
        {validation ? <div className="notice-panel"><strong>{validation.status.replace(/_/g, " ")}</strong><span>{validation.message}</span><span>{selected?.provider_key === "camera_node" ? "Pairing contacted the chosen Node explicitly; this validation itself saves no media, creates no activity, and does not enable monitoring." : "Validation does not contact the camera, save media, create activity, or enable monitoring."}</span></div> : null}
      </section>
      <section className="panel page-stack">
        <h2>2. Zone setup</h2><p>Zones tell MockingBird which part of this camera view matters. Drag an ordinary activity Zone; Privacy and Ignore Zones stay suppression-only.</p>
        <div className="zone-drawing-canvas" onPointerDown={(event) => { drawStart.current = pointAt(event); event.currentTarget.setPointerCapture(event.pointerId); }} onPointerUp={finishDraw} role="img" aria-label="Draw an activity Zone">
          <div className="zone-drawing-rectangle" style={{ left: `${polygon[0].x * 100}%`, top: `${polygon[0].y * 100}%`, width: `${(polygon[1].x - polygon[0].x) * 100}%`, height: `${(polygon[2].y - polygon[1].y) * 100}%` }} />
          <span>Drag to draw the activity area</span>
        </div>
        <label>Zone name<input onChange={(event) => setZoneName(event.target.value)} value={zoneName} /></label>
        <label>Zone type<select value={zoneType} onChange={(event) => setZoneType(event.target.value as ZoneType)}>{["feeder", "birdbath", "ground", "perch", "yard", "driveway", "privacy", "ignore"].map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
        {zoneType !== "privacy" && zoneType !== "ignore" ? <label>Recommended monitoring sensitivity<select value={sensitivity} onChange={(event) => setSensitivity(event.target.value as ZoneActivitySensitivity)}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option></select></label> : <p className="meta-text">This suppression Zone is never a monitoring target.</p>}
      </section>
      <section className="panel page-stack"><h2>3. Monitoring</h2><p><strong>Monitoring enabled</strong> means MockingBird should monitor this view while the backend is running. <strong>Monitoring running</strong> is the current camera state.</p><label><input checked={monitoringEnabled} onChange={(event) => setMonitoringEnabled(event.target.checked)} type="checkbox" /> Enable monitoring after setup</label><span className="meta-text">Off is the safe default. Preview/readiness never enables monitoring.</span><button className="primary-action" disabled={!cameraName || !zoneName || !validation?.can_continue || isCompleting} onClick={() => void complete()} type="button">{isCompleting ? "Finishing…" : monitoringEnabled ? "Finish and enable monitoring" : "Finish without enabling"}</button>{error ? <div className="error-panel">{error}</div> : null}</section>
    </div>
  );
}
