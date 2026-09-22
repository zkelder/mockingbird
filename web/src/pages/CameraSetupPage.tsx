import { useEffect, useMemo, useRef, useState, type PointerEvent } from "react";
import { apiClient } from "../api/client";
import type {
  CameraSetupOption,
  CameraSetupValidationResponse,
  CameraNodeAdvertisedCamera,
  CameraNodePendingSetupDraftUpdate,
  CameraNodePendingSetupResponse,
  OnvifDiscoverProfilesResponse,
  OnvifDiscoveredProfile,
  Point,
  ZoneActivitySensitivity,
  ZoneType,
} from "../api/types";
import { formatLabel, withTimeout } from "../utils";

interface CameraSetupPageProps {
  onComplete: (streamId: string) => void;
  onCancel: () => void;
  onSourcesChanged: () => void;
  // UI/UX & First-Run Adoption v1: inside the first-run wizard this page
  // rendered its own "Guided setup / Add Camera" page header directly under
  // the wizard's own "Welcome to MockingBird" one -- three stacked headings
  // for one step. The wizard passes `embedded` so only its own header shows.
  embedded?: boolean;
  onImportInstead?: () => void;
}

const defaultPolygon: Point[] = [
  { x: 0.2, y: 0.2 },
  { x: 0.8, y: 0.2 },
  { x: 0.8, y: 0.8 },
  { x: 0.2, y: 0.8 },
];
const DRAFT_KEY = "mockingbird-camera-setup-draft-v1";
const DEFAULT_CAMERA_NAME = "My camera";

// Bounded waits so a slow or unreachable local device turns into a clear
// message instead of a button left gray forever -- see "Progress and
// failure behavior" in docs/camera-node-pairing-persistence-design.md.
const OPTIONS_LOAD_TIMEOUT_MS = 8_000;
const NODE_RESUME_CHECK_TIMEOUT_MS = 6_000;
const NODE_PAIR_TIMEOUT_MS = 12_000;
const NODE_PREVIEW_TIMEOUT_MS = 15_000;
const SETUP_PREVIEW_TIMEOUT_MS = 15_000;
const NODE_DRAFT_SAVE_TIMEOUT_MS = 6_000;
const NODE_FORGET_TIMEOUT_MS = 10_000;
const VALIDATE_TIMEOUT_MS = 10_000;
const COMPLETE_TIMEOUT_MS = 12_000;
// ONVIF discovery is up to four sequential real network round trips
// (capabilities -> device info -> profiles -> stream URI per profile),
// bounded but longer than a single request -- see onvif_client.py's own
// module docstring.
const ONVIF_DISCOVER_TIMEOUT_MS = 20_000;

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

function errorMessage(caught: unknown, fallback: string): string {
  return caught instanceof Error ? caught.message : fallback;
}

function firstAvailableCamera(cameras: CameraNodeAdvertisedCamera[]): CameraNodeAdvertisedCamera | undefined {
  return cameras.find((camera) => camera.status === "available" && camera.snapshot_supported);
}

// v0.1 Acquisition/Ingest Interoperability Closure v1 ("II.4 ONVIF"):
// mirrors mockingbird.source_providers.onvif_client.embed_credentials_in_
// uri exactly -- the ONVIF discovery response never carries credentials
// (see docs/source-provider-configuration-contract.md "Secret/Redaction
// policy"); this browser-side embedding is what turns the bare, camera-
// provided stream URI into one the existing RTSP bridge can authenticate
// with, using the same username/password the user already typed into
// this form, never sent anywhere new.
function embedOnvifCredentials(uri: string, username: string, password: string): string {
  if (!username && !password) return uri;
  const match = uri.match(/^([a-zA-Z][a-zA-Z0-9+.-]*:\/\/)(.*)$/);
  if (!match) return uri;
  const [, schemeAndSlashes, rest] = match;
  if (rest.includes("@")) return uri;
  const userinfo = `${encodeURIComponent(username)}:${encodeURIComponent(password)}@`;
  return `${schemeAndSlashes}${userinfo}${rest}`;
}

function onvifDeviceSummary(discovery: OnvifDiscoverProfilesResponse | null): string {
  if (!discovery) return "";
  return [discovery.device_manufacturer, discovery.device_model].filter(Boolean).join(" ");
}

export function CameraSetupPage({ onCancel, onComplete, onSourcesChanged, embedded = false, onImportInstead }: CameraSetupPageProps) {
  const [initialDraft] = useState(readDraft);
  const [options, setOptions] = useState<CameraSetupOption[]>([]);
  const [providerKey, setProviderKey] = useState(initialDraft.providerKey ?? "");
  const [config, setConfig] = useState<Record<string, string>>(initialDraft.config ?? {});

  // Required-field UX: real, editable defaults in state -- never a
  // placeholder standing in for a value that was never actually set (see
  // "Required-field UX" in docs/camera-node-pairing-persistence-design.md).
  const [cameraName, setCameraName] = useState(initialDraft.cameraName || DEFAULT_CAMERA_NAME);
  const cameraNameIsDefault = useRef(!initialDraft.cameraName);
  const [streamName, setStreamName] = useState(initialDraft.streamName ?? "");
  const streamNameIsDefault = useRef(!initialDraft.streamName);

  const [zoneName, setZoneName] = useState(initialDraft.zoneName ?? "Activity area");
  const [zoneType, setZoneType] = useState<ZoneType>(initialDraft.zoneType ?? "feeder");
  const [polygon, setPolygon] = useState<Point[]>(initialDraft.polygon ?? defaultPolygon);
  const [sensitivity, setSensitivity] = useState<ZoneActivitySensitivity>(initialDraft.sensitivity ?? "normal");
  const [monitoringEnabled, setMonitoringEnabled] = useState(initialDraft.monitoringEnabled ?? false);
  const [validation, setValidation] = useState<CameraSetupValidationResponse | null>(null);

  // Camera Node pairing: durable and resumable server-side the instant a
  // pairing succeeds, never held only here for the rest of setup -- see
  // "Core design correction" in docs/camera-node-pairing-persistence-design.md.
  const [nodeSetup, setNodeSetup] = useState<CameraNodePendingSetupResponse | null>(null);
  const [isCheckingNodeResume, setIsCheckingNodeResume] = useState(true);
  const [nodeAddress, setNodeAddress] = useState("");
  const [pairingCode, setPairingCode] = useState("");
  const [selectedNodeCameraId, setSelectedNodeCameraId] = useState("");
  const [nodePreviewUrl, setNodePreviewUrl] = useState<string | null>(null);
  const [isLoadingNodePreview, setIsLoadingNodePreview] = useState(false);
  // Camera / Source Experience & First-Hour Setup Closure v1: the same
  // transient "check the picture" confirmation Camera Node already has,
  // now also for manually-entered RTSP/ONVIF-resolved and local/Windows
  // USB cameras -- previously only Camera Node ever showed an actual
  // picture during setup.
  const [setupPreviewUrl, setSetupPreviewUrl] = useState<string | null>(null);
  const [isLoadingSetupPreview, setIsLoadingSetupPreview] = useState(false);
  const [isPairingNode, setIsPairingNode] = useState(false);
  const [isForgettingNode, setIsForgettingNode] = useState(false);
  const [draftSaveStatus, setDraftSaveStatus] = useState<"idle" | "saving" | "failed">("idle");

  // v0.1 Acquisition/Ingest Interoperability Closure v1 ("II.4 ONVIF"):
  // transient discovery state only -- once a profile is chosen, the
  // credential-embedded stream URI lands in the same `config` state every
  // other provider already uses (`live_stream_url`/`live_stream_type`),
  // so this Source completes setup as an ordinary provider_key=
  // "external_url" RTSP camera; see `effectiveProviderKey` below.
  const [onvifDiscovery, setOnvifDiscovery] = useState<OnvifDiscoverProfilesResponse | null>(null);
  const [onvifSelectedProfileToken, setOnvifSelectedProfileToken] = useState("");
  const [isDiscoveringOnvif, setIsDiscoveringOnvif] = useState(false);

  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isValidating, setIsValidating] = useState(false);
  const [isCompleting, setIsCompleting] = useState(false);
  const drawStart = useRef<Point | null>(null);

  const selected = useMemo(
    () => options.find((option) => option.provider_key === providerKey) ?? null,
    [options, providerKey],
  );

  // v0.1 Acquisition/Ingest Interoperability Closure v1 ("II.4 ONVIF"):
  // the dropdown/UI-facing choice stays "onvif" throughout this page, but
  // every actual validate/complete call submits "external_url" once a
  // profile is selected -- the backend's own provider-definition allow-
  // list never accepts "onvif" itself (see record_onvif_profile's own
  // docstring: an ONVIF-configured Source is, from that point on,
  // completely indistinguishable from a manually-entered RTSP camera).
  const effectiveProviderKey = selected?.provider_key === "onvif" ? "external_url" : selected?.provider_key;

  function loadCameraSetupOptions() {
    setIsLoading(true);
    setError(null);
    void withTimeout(apiClient.getCameraSetupOptions(), OPTIONS_LOAD_TIMEOUT_MS, "Loading camera types")
      .then((response) => {
        setOptions(response.options);
        // First-Hour Onboarding + Whole-Product Observability Closure v1
        // ("A4 golden path priority"): a genuinely first-time user (no
        // current selection yet) previously defaulted to whichever
        // provider happened to sort first in the backend's own definition
        // order -- "Manual media," not the documented reference/golden
        // path. Native Camera Node is preferred explicitly here when it is
        // actually selectable; every other available provider still falls
        // back to the prior "first available" behavior unchanged.
        const goldenPath = response.options.find(
          (option) => option.provider_key === "camera_node" && option.availability === "available_now",
        );
        const first = response.options.find((option) => option.availability === "available_now");
        setProviderKey((current) => current || goldenPath?.provider_key || first?.provider_key || "");
      })
      .catch((caught) => setError(errorMessage(caught, "Camera setup options are unavailable.")))
      .finally(() => setIsLoading(false));
  }

  useEffect(() => {
    loadCameraSetupOptions();
  }, []);

  // Resume behavior: a reload, a closed tab, or a full application restart
  // can all recover an already-successful pairing the same way -- this
  // never depends on anything the browser remembered on its own. See
  // "Resume behavior" in docs/camera-node-pairing-persistence-design.md.
  useEffect(() => {
    let cancelled = false;
    void withTimeout(
      apiClient.getCameraNodePendingSetup(),
      NODE_RESUME_CHECK_TIMEOUT_MS,
      "Checking for a paired Camera Node",
    )
      .then((resumed) => {
        if (cancelled) return;
        setNodeSetup(resumed);
        setProviderKey("camera_node");
        const cameraId = resumed.selected_camera_id ?? "";
        setSelectedNodeCameraId(cameraId);
        setConfig({ node_camera_id: cameraId });
        if (resumed.camera_name) {
          setCameraName(resumed.camera_name);
          cameraNameIsDefault.current = false;
        }
        if (resumed.stream_name) {
          setStreamName(resumed.stream_name);
          streamNameIsDefault.current = false;
        }
        if (resumed.zone_name) setZoneName(resumed.zone_name);
        if (resumed.zone_type) setZoneType(resumed.zone_type);
        if (resumed.polygon && resumed.polygon.length >= 3) setPolygon(resumed.polygon);
        if (resumed.sensitivity) setSensitivity(resumed.sensitivity);
        setMonitoringEnabled(resumed.monitoring_enabled);
      })
      .catch(() => {
        // Nothing resumable (a plain 404) or the check itself failed --
        // either way this fails open into a normal fresh setup, exactly
        // like the setup-state gate a level up. Never blocks onboarding.
      })
      .finally(() => {
        if (!cancelled) setIsCheckingNodeResume(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    window.sessionStorage.setItem(DRAFT_KEY, JSON.stringify({
      providerKey, config, cameraName, streamName, zoneName, zoneType, polygon, sensitivity, monitoringEnabled,
    }));
  }, [providerKey, config, cameraName, streamName, zoneName, zoneType, polygon, sensitivity, monitoringEnabled]);

  useEffect(() => () => {
    if (nodePreviewUrl) URL.revokeObjectURL(nodePreviewUrl);
  }, [nodePreviewUrl]);

  useEffect(() => () => {
    if (setupPreviewUrl) URL.revokeObjectURL(setupPreviewUrl);
  }, [setupPreviewUrl]);

  function applyCameraNameDefault(candidate: string | undefined) {
    if (!candidate) return;
    if (cameraNameIsDefault.current || !cameraName.trim()) {
      setCameraName(candidate);
      cameraNameIsDefault.current = true;
    }
  }

  function saveNodeDraft(patch: CameraNodePendingSetupDraftUpdate) {
    if (!nodeSetup) return;
    setDraftSaveStatus("saving");
    void withTimeout(
      apiClient.updateCameraNodePendingSetup(nodeSetup.pairing_token, patch),
      NODE_DRAFT_SAVE_TIMEOUT_MS,
      "Saving setup progress",
    )
      .then((updated) => {
        setNodeSetup(updated);
        setDraftSaveStatus("idle");
      })
      .catch(() => setDraftSaveStatus("failed"));
  }

  // A rejected Validate/Preview/Finish call against a paired Node's stored
  // credential is how a genuine revocation is actually discovered; re-read
  // the durable record so the banner catches up without a manual reload.
  function refreshNodeSetupAfterRejection() {
    void apiClient
      .getCameraNodePendingSetup()
      .then((resumed) => setNodeSetup(resumed))
      .catch(() => {});
  }

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
    const nextPolygon = [
      { x: left, y: top }, { x: right, y: top }, { x: right, y: bottom }, { x: left, y: bottom },
    ];
    setPolygon(nextPolygon);
    saveNodeDraft({ polygon: nextPolygon });
  }

  async function validateSetup() {
    if (!selected || !effectiveProviderKey) return;
    setIsValidating(true);
    setError(null);
    try {
      setValidation(
        await withTimeout(
          apiClient.validateCameraSetup({
            provider_key: effectiveProviderKey,
            config,
            node_pairing_token: selected.provider_key === "camera_node" ? nodeSetup?.pairing_token : undefined,
          }),
          VALIDATE_TIMEOUT_MS,
          "Checking the camera",
        ),
      );
    } catch (caught) {
      setError(errorMessage(caught, "Camera configuration could not be checked."));
      if (selected.provider_key === "camera_node") refreshNodeSetupAfterRejection();
    } finally {
      setIsValidating(false);
    }
  }

  // Client-side visibility only -- a lightweight mirror of the backend's
  // own `_camera_setup_preview_available` capability check (including its
  // "an rtsp:// URL counts even with Live stream type left blank"
  // inference), never the authority on whether a picture check will
  // actually succeed. Clicking it early (an incomplete config) gets the
  // same honest, specific failure "Check camera settings" already gives
  // for the same underlying reason -- this only avoids showing a button
  // that provably cannot work for a still-image-only or import-only
  // provider.
  const setupPreviewSupported = (() => {
    if (effectiveProviderKey === "external_url") {
      const url = (config.live_stream_url ?? "").trim();
      const type = (config.live_stream_type ?? "").trim().toLowerCase();
      const lowerUrl = url.toLowerCase();
      const isRtsp = lowerUrl.startsWith("rtsp://") || lowerUrl.startsWith("rtsps://") || type === "rtsp";
      return isRtsp && Boolean(url);
    }
    if (effectiveProviderKey === "local_usb") {
      return Boolean(config.local_camera_device?.trim() || config.windows_camera_name?.trim());
    }
    return false;
  })();

  async function previewSetupFrame() {
    if (!selected || !effectiveProviderKey) return;
    setIsLoadingSetupPreview(true);
    setError(null);
    try {
      const image = await withTimeout(
        apiClient.previewCameraSetupFrame({ provider_key: effectiveProviderKey, config }),
        SETUP_PREVIEW_TIMEOUT_MS,
        "Loading the camera picture",
      );
      const nextUrl = URL.createObjectURL(image);
      if (setupPreviewUrl) URL.revokeObjectURL(setupPreviewUrl);
      setSetupPreviewUrl(nextUrl);
    } catch (caught) {
      setError(errorMessage(caught, "The camera picture could not be loaded."));
    } finally {
      setIsLoadingSetupPreview(false);
    }
  }

  async function pairNode() {
    setIsPairingNode(true);
    setError(null);
    setValidation(null);
    const renewing = nodeSetup?.status === "needs_renewal" ? nodeSetup.pairing_token : undefined;
    try {
      const pairing = await withTimeout(
        apiClient.pairCameraNode({
          base_address: nodeAddress,
          pairing_code: pairingCode,
          renews_pairing_token: renewing,
        }),
        NODE_PAIR_TIMEOUT_MS,
        "Pairing with the Camera Node",
      );
      const initialCamera = firstAvailableCamera(pairing.cameras);
      const initialCameraId = initialCamera?.camera_id ?? "";
      setNodeSetup({
        pairing_token: pairing.pairing_token,
        status: "active",
        node_id: pairing.node_id,
        display_name: pairing.display_name,
        api_version: pairing.api_version,
        cameras: pairing.cameras,
        selected_camera_id: initialCameraId || null,
        camera_name: cameraNameIsDefault.current ? null : cameraName,
        stream_name: streamNameIsDefault.current ? null : streamName,
        zone_name: zoneName,
        zone_type: zoneType,
        polygon,
        sensitivity,
        monitoring_enabled: monitoringEnabled,
        message: pairing.message,
      });
      setSelectedNodeCameraId(initialCameraId);
      setConfig({ node_camera_id: initialCameraId });
      applyCameraNameDefault(initialCamera?.display_name);
      if (nodePreviewUrl) URL.revokeObjectURL(nodePreviewUrl);
      setNodePreviewUrl(null);
      setPairingCode("");
    } catch (caught) {
      setError(errorMessage(caught, "Camera Node pairing could not be completed."));
    } finally {
      setIsPairingNode(false);
    }
  }

  function selectNodeCamera(cameraId: string) {
    setSelectedNodeCameraId(cameraId);
    setConfig({ node_camera_id: cameraId });
    setValidation(null);
    if (nodePreviewUrl) URL.revokeObjectURL(nodePreviewUrl);
    setNodePreviewUrl(null);
    applyCameraNameDefault(nodeSetup?.cameras.find((camera) => camera.camera_id === cameraId)?.display_name);
    saveNodeDraft({ selected_camera_id: cameraId });
  }

  async function previewNodeCamera(cameraId = selectedNodeCameraId) {
    if (!nodeSetup || !cameraId) return;
    setIsLoadingNodePreview(true);
    setError(null);
    try {
      const image = await withTimeout(
        apiClient.previewCameraNode({ pairing_token: nodeSetup.pairing_token, camera_id: cameraId }),
        NODE_PREVIEW_TIMEOUT_MS,
        "Loading the camera picture",
      );
      const nextUrl = URL.createObjectURL(image);
      if (nodePreviewUrl) URL.revokeObjectURL(nodePreviewUrl);
      setNodePreviewUrl(nextUrl);
    } catch (caught) {
      setError(errorMessage(caught, "The camera picture could not be loaded."));
      refreshNodeSetupAfterRejection();
    } finally {
      setIsLoadingNodePreview(false);
    }
  }

  async function forgetNode() {
    if (!nodeSetup) return;
    setIsForgettingNode(true);
    setError(null);
    try {
      await withTimeout(
        apiClient.revokeCameraNodePendingSetup({ pairing_token: nodeSetup.pairing_token }),
        NODE_FORGET_TIMEOUT_MS,
        "Forgetting this Camera Node",
      );
      setNodeSetup(null);
      setSelectedNodeCameraId("");
      setConfig({});
      setValidation(null);
      if (nodePreviewUrl) URL.revokeObjectURL(nodePreviewUrl);
      setNodePreviewUrl(null);
    } catch (caught) {
      setError(errorMessage(caught, "This Camera Node could not be forgotten right now."));
    } finally {
      setIsForgettingNode(false);
    }
  }

  async function discoverOnvif() {
    setIsDiscoveringOnvif(true);
    setError(null);
    setOnvifDiscovery(null);
    setOnvifSelectedProfileToken("");
    try {
      const result = await withTimeout(
        apiClient.discoverOnvifProfiles({
          onvif_host: config.onvif_host ?? "",
          onvif_port: config.onvif_port ? Number(config.onvif_port) : undefined,
          onvif_username: config.onvif_username ?? "",
          onvif_password: config.onvif_password ?? "",
        }),
        ONVIF_DISCOVER_TIMEOUT_MS,
        "Discovering this camera",
      );
      setOnvifDiscovery(result);
    } catch (caught) {
      setError(errorMessage(caught, "This camera could not be discovered through ONVIF."));
    } finally {
      setIsDiscoveringOnvif(false);
    }
  }

  function selectOnvifProfile(profile: OnvifDiscoveredProfile) {
    setOnvifSelectedProfileToken(profile.profile_token);
    const embedded = embedOnvifCredentials(
      profile.stream_uri,
      config.onvif_username ?? "",
      config.onvif_password ?? "",
    );
    setConfig((current) => ({ ...current, live_stream_url: embedded, live_stream_type: "rtsp" }));
    setValidation(null);
    applyCameraNameDefault(onvifDeviceSummary(onvifDiscovery) || undefined);
  }

  async function complete() {
    if (!selected || !effectiveProviderKey || !validation?.can_continue) return;
    setIsCompleting(true);
    setError(null);
    try {
      const result = await withTimeout(
        apiClient.completeCameraSetup({
          camera_name: cameraName,
          stream_name: streamName || `${cameraName} view`,
          provider_key: effectiveProviderKey,
          config,
          node_pairing_token: selected.provider_key === "camera_node" ? nodeSetup?.pairing_token : undefined,
          zones: [{
            name: zoneName,
            zone_type: zoneType,
            polygon,
            is_active: true,
            monitoring_policy: zoneType === "privacy" || zoneType === "ignore"
              ? null
              : { activity_sensitivity: sensitivity },
          }],
          // Camera Node uses the Observation Engine (Start observing on the
          // Stream page), never this guided setup's legacy durable-
          // monitoring checkbox -- the backend rejects enable_monitoring
          // for camera_node (`_reject_camera_node_legacy_monitoring_
          // enable`, see "Camera ownership" in docs/runtime-map.md), and
          // the checkbox itself is hidden below for this provider. Forced
          // false here too so a stale sessionStorage draft saved before
          // switching providers can never submit the rejected combination.
          enable_monitoring: selected.provider_key === "camera_node" ? false : monitoringEnabled,
          idempotency_key: setupKey(),
        }),
        COMPLETE_TIMEOUT_MS,
        "Finishing setup",
      );
      onSourcesChanged();
      window.sessionStorage.removeItem(DRAFT_KEY);
      onComplete(result.stream.id);
    } catch (caught) {
      setError(errorMessage(caught, "Camera setup could not be completed."));
      if (selected.provider_key === "camera_node") refreshNodeSetupAfterRejection();
    } finally {
      setIsCompleting(false);
    }
  }

  // Finish button: never silently gray. Every prerequisite below has a
  // plain-language reason shown right next to the button -- see "Finish
  // button" in docs/camera-node-pairing-persistence-design.md.
  const finishBlockers = useMemo(() => {
    const blockers: string[] = [];
    if (!selected) {
      blockers.push("Choose a camera type.");
      return blockers;
    }
    if (selected.provider_key === "camera_node") {
      if (!nodeSetup) {
        blockers.push("Pair a Camera Node.");
      } else if (nodeSetup.status === "needs_renewal") {
        blockers.push("Pairing needs to be renewed.");
      } else if (!selectedNodeCameraId) {
        blockers.push("Choose a camera the Node can see.");
      }
    }
    if (selected.provider_key === "onvif" && !config.live_stream_url) {
      blockers.push("Discover this camera and choose a video profile.");
    }
    if (!cameraName.trim()) blockers.push("Enter a camera name.");
    if (!zoneName.trim()) blockers.push("Name the area to watch.");
    if (!validation?.can_continue) blockers.push("Check the camera first.");
    return blockers;
  }, [selected, nodeSetup, selectedNodeCameraId, cameraName, zoneName, validation, config.live_stream_url]);

  if (isLoading) return <div className="panel">Loading camera setup…</div>;
  if (!options.length && error) {
    return (
      <div className="panel page-stack">
        <div className="error-panel">{error}</div>
        <button className="secondary-action" onClick={loadCameraSetupOptions} type="button">Try again</button>
      </div>
    );
  }

  const skipButton = (
    <button className="secondary-action" onClick={() => { window.sessionStorage.removeItem(DRAFT_KEY); onCancel(); }} type="button">
      {embedded ? "Skip — I'll add a camera later" : "Do this later"}
    </button>
  );

  return (
    <div className="page-stack">
      {embedded ? (
        <div className="panel-actions camera-setup-embedded-actions">{skipButton}</div>
      ) : (
        <section className="page-header">
          <div>
            <span className="eyebrow">Guided setup</span>
            <h1>Add Camera</h1>
            <p>Add your camera, check the picture, then choose the area to watch.</p>
          </div>
          {skipButton}
        </section>
      )}
      <section className="notice-panel camera-setup-requirements">
        <strong>What you&rsquo;ll need</strong>
        <span>
          One of: a MockingBird Camera Node (a small networked camera device — a Raspberry Pi with
          a camera is the reference design), a network (IP/ONVIF/RTSP) camera, or a USB webcam
          attached to this computer. Have its address and sign-in details handy.
        </span>
        <span className="meta-text">
          No camera yet? You can skip this and import photos or video from a trail camera or phone
          instead — MockingBird looks at imported media the same way.
        </span>
        {onImportInstead ? (
          <button className="text-action" onClick={onImportInstead} type="button">
            Import photos instead
          </button>
        ) : null}
      </section>
      <section className="panel page-stack source-setup-form">
        <h2>1. Add your camera</h2>
        <label>Camera type<select value={providerKey} onChange={(event) => { setProviderKey(event.target.value); setConfig({}); setValidation(null); setSelectedNodeCameraId(""); setOnvifDiscovery(null); setOnvifSelectedProfileToken(""); if (nodePreviewUrl) URL.revokeObjectURL(nodePreviewUrl); setNodePreviewUrl(null); if (setupPreviewUrl) URL.revokeObjectURL(setupPreviewUrl); setSetupPreviewUrl(null); }}>
          {/* UI/UX & First-Run Adoption v1: not-yet-available providers were
              listed as disabled "— unavailable" entries, which read like
              MockingBird was broken rather than like a roadmap. */}
          {options.filter((option) => option.availability === "available_now").map((option) => <option key={option.provider_key} value={option.provider_key}>{option.display_name} — {option.compatibility_label}</option>)}
        </select></label>
        {selected ? <><p className="meta-text">{selected.message}</p>
          <div className="source-connection-meta">
            <span>{selected.supports_live_playback ? "Live preview available" : "No live preview"}</span>
          </div>
          {selected.provider_key === "camera_node" ? <div className="notice-panel">
            <strong>MockingBird Camera Node</strong>
            {isCheckingNodeResume ? (
              <span className="meta-text">Checking whether a Camera Node is already paired…</span>
            ) : nodeSetup && nodeSetup.status === "active" ? (
              <>
                <span><strong>Camera Node paired</strong> — continue setup below.</span>
                <span className="meta-text">{nodeSetup.display_name}</span>
                <label>Camera view<select onChange={(event) => selectNodeCamera(event.target.value)} value={selectedNodeCameraId}>
                  <option value="">Choose a camera</option>
                  {nodeSetup.cameras.map((camera) => <option disabled={camera.status !== "available" || !camera.snapshot_supported} key={camera.camera_id} value={camera.camera_id}>{camera.display_name} — {formatLabel(camera.status)}</option>)}
                </select></label>
                <button className="secondary-action" disabled={!selectedNodeCameraId || isLoadingNodePreview} onClick={() => void previewNodeCamera()} type="button">{isLoadingNodePreview ? "Loading picture…" : "Check the picture"}</button>
                {nodePreviewUrl ? <img alt="Camera Node picture" className="camera-node-preview" src={nodePreviewUrl} /> : null}
                <span className="meta-text">This picture is one explicit, transient check. It is not saved, does not create activity, and monitoring stays off until you choose otherwise.</span>
                <button className="secondary-action" disabled={isForgettingNode} onClick={() => void forgetNode()} type="button">{isForgettingNode ? "Forgetting…" : "Forget this Camera Node"}</button>
                {draftSaveStatus === "saving" ? <span className="meta-text">Saving…</span> : null}
                {draftSaveStatus === "failed" ? <span className="meta-text">Progress could not be saved just now; your pairing is still safe and setup keeps working.</span> : null}
              </>
            ) : <>
              {nodeSetup && nodeSetup.status === "needs_renewal" ? (
                <div className="error-panel">
                  <strong>Pairing needs to be renewed</strong>
                  <span>MockingBird can no longer use its saved pairing for this Camera Node. Start the Node again for a new one-time code, then pair again below — your camera name, view name, and area to watch are still saved.</span>
                </div>
              ) : (
                <span>Enter the Camera Node’s address on your network and its one-time pairing code. Both are printed in the Camera Node’s own setup output — see the Camera Node install guide if you haven’t set one up yet. MockingBird never scans your network for it.</span>
              )}
              <label>Node address<input autoCapitalize="off" autoCorrect="off" inputMode="url" onChange={(event) => setNodeAddress(event.target.value)} placeholder="http://192.168.1.50:8787" value={nodeAddress} /></label>
              <label>One-time pairing code<input autoComplete="one-time-code" onChange={(event) => setPairingCode(event.target.value)} type="password" value={pairingCode} /></label>
              <button className="secondary-action" disabled={!nodeAddress || !pairingCode || isPairingNode} onClick={() => void pairNode()} type="button">{isPairingNode ? "Pairing…" : nodeSetup?.status === "needs_renewal" ? "Renew pairing" : "Pair Camera Node"}</button>
            </>}
          </div> : selected.provider_key === "onvif" ? <div className="notice-panel">
            <strong>ONVIF network camera</strong>
            <span className="meta-text">Enter this camera's local address and account, then discover its available video profiles. MockingBird never scans your network for it.</span>
            {selected.fields.map((field) => <label key={field.key}>{field.label}
              <input onChange={(event) => { setConfig((current) => ({ ...current, [field.key]: event.target.value })); setOnvifDiscovery(null); setOnvifSelectedProfileToken(""); }} placeholder={field.secret ? "Leave blank to keep masked" : field.placeholder ?? ""} type={field.secret ? "password" : "text"} value={config[field.key] ?? ""} />
            </label>)}
            <button className="secondary-action" disabled={!config.onvif_host?.trim() || isDiscoveringOnvif} onClick={() => void discoverOnvif()} type="button">{isDiscoveringOnvif ? "Discovering…" : "Discover this camera"}</button>
            {onvifDiscovery ? (
              onvifDiscovery.status === "available" && onvifDiscovery.profiles.length > 0 ? (
                <>
                  <span className="meta-text">{onvifDeviceSummary(onvifDiscovery) || "Camera found"} — {onvifDiscovery.profiles.length} video profile{onvifDiscovery.profiles.length === 1 ? "" : "s"}</span>
                  <label>Video profile<select onChange={(event) => { const chosen = onvifDiscovery.profiles.find((profile) => profile.profile_token === event.target.value); if (chosen) selectOnvifProfile(chosen); }} value={onvifSelectedProfileToken}>
                    <option value="">Choose a profile</option>
                    {onvifDiscovery.profiles.map((profile) => <option key={profile.profile_token} value={profile.profile_token}>{profile.profile_name ?? profile.profile_token}{profile.advertised_width && profile.advertised_height ? ` — ${profile.advertised_width}×${profile.advertised_height}` : ""}</option>)}
                  </select></label>
                  {config.live_stream_url ? <span className="meta-text">Profile selected. This camera will play through MockingBird's RTSP bridge, the same as a manually-entered RTSP camera.</span> : null}
                </>
              ) : (
                <div className="error-panel">{onvifDiscovery.message}</div>
              )
            ) : null}
          </div> : selected.fields.map((field) => <label key={field.key}>{field.label}
            <input onChange={(event) => setConfig((current) => ({ ...current, [field.key]: event.target.value }))} placeholder={field.secret ? "Leave blank to keep masked" : field.placeholder ?? ""} type={field.secret ? "password" : "text"} value={config[field.key] ?? ""} />
          </label>)}</> : null}
        <label>Camera name<input onChange={(event) => { setCameraName(event.target.value); cameraNameIsDefault.current = false; }} onBlur={() => saveNodeDraft({ camera_name: cameraName })} value={cameraName} /></label>
        <label>Name this view<input onChange={(event) => { setStreamName(event.target.value); streamNameIsDefault.current = false; }} onBlur={() => saveNodeDraft({ stream_name: streamName })} placeholder={streamNameIsDefault.current ? `${cameraName} view` : ""} value={streamName} /></label>
        <button className="secondary-action" disabled={!selected || isValidating} onClick={() => void validateSetup()} type="button">{isValidating ? "Checking…" : "Check camera settings"}</button>
        {validation ? <div className="notice-panel"><strong>{formatLabel(validation.status)}</strong><span>{validation.message}</span></div> : null}
        {setupPreviewSupported ? <>
          <button className="secondary-action" disabled={isLoadingSetupPreview} onClick={() => void previewSetupFrame()} type="button">{isLoadingSetupPreview ? "Loading picture…" : "Check the picture"}</button>
          <span className="meta-text">This picture is one explicit, transient check. It is not saved, does not create activity, and monitoring stays off until you choose otherwise.</span>
          {setupPreviewUrl ? <img alt="Camera picture" className="camera-node-preview" src={setupPreviewUrl} /> : null}
        </> : null}
      </section>
      <section className="panel page-stack source-setup-form">
        <h2>2. Choose the area to watch</h2><p>Draw the part of this camera’s view that matters. Privacy and Ignore areas won’t trigger monitoring on their own, but can still appear in a photo saved because of activity elsewhere in view.</p>
        <div className="zone-drawing-canvas" onPointerDown={(event) => { drawStart.current = pointAt(event); event.currentTarget.setPointerCapture(event.pointerId); }} onPointerUp={finishDraw} role="img" aria-label="Draw the area to watch">
          <div className="zone-drawing-rectangle" style={{ left: `${polygon[0].x * 100}%`, top: `${polygon[0].y * 100}%`, width: `${(polygon[1].x - polygon[0].x) * 100}%`, height: `${(polygon[2].y - polygon[1].y) * 100}%` }} />
          <span>Drag to draw the area to watch</span>
        </div>
        <label>Area name<input onChange={(event) => setZoneName(event.target.value)} onBlur={() => saveNodeDraft({ zone_name: zoneName })} value={zoneName} /></label>
        <label>Area type<select value={zoneType} onChange={(event) => { const value = event.target.value as ZoneType; setZoneType(value); saveNodeDraft({ zone_type: value }); }}>{["feeder", "birdbath", "ground", "perch", "yard", "driveway", "privacy", "ignore"].map((value) => <option key={value} value={value}>{formatLabel(value)}</option>)}</select></label>
        {zoneType !== "privacy" && zoneType !== "ignore" ? <label>Sensitivity<select value={sensitivity} onChange={(event) => { const value = event.target.value as ZoneActivitySensitivity; setSensitivity(value); saveNodeDraft({ sensitivity: value }); }}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option></select></label> : <p className="meta-text">Activity in this area won’t start or trigger monitoring by itself. If activity elsewhere starts monitoring, a saved photo can still show this area.</p>}
      </section>
      <section className="panel page-stack source-setup-form">
        <h2>3. Start watching</h2>
        {selected?.provider_key === "camera_node" ? (
          // Camera Node monitoring is exclusively the accepted Observation
          // Engine, started per-camera from the Stream page -- never this
          // guided setup's legacy durable-monitoring checkbox (see "Camera
          // Node monitoring-ownership rule" in docs/runtime-map.md). No
          // checkbox is offered here, so there is nothing this page could
          // submit that the backend would reject.
          <>
            <p>
              {embedded
                ? "Finishing setup never starts watching by itself — you'll choose when to start on the next step."
                : "Finishing setup never starts watching by itself."}
            </p>
            <span className="meta-text">
              {embedded
                ? "Nothing is saved until you start observing, and you can stop any time."
                : "When you're ready, open this camera from Cameras and choose Start observing. You can stop any time."}
            </span>
          </>
        ) : (
          <>
            <p><strong>Start watching</strong> means MockingBird watches this area while it is running. You can turn this on or off any time after setup too.</p>
            <label><input checked={monitoringEnabled} onChange={(event) => { setMonitoringEnabled(event.target.checked); saveNodeDraft({ monitoring_enabled: event.target.checked }); }} type="checkbox" /> Start watching once setup finishes</label>
            <span className="meta-text">Off is the safe default. Checking the camera never turns watching on.</span>
          </>
        )}
        <button className="primary-action" disabled={finishBlockers.length > 0 || isCompleting} onClick={() => void complete()} type="button">
          {isCompleting
            ? "Finishing…"
            : selected?.provider_key === "camera_node"
              ? (embedded ? "Continue" : "Finish setup")
              : monitoringEnabled
                ? "Finish and start watching"
                : "Finish without watching yet"}
        </button>
        {finishBlockers.length > 0 ? <div className="meta-text"><span>Before you can continue:</span><ul className="finish-blockers">{finishBlockers.map((reason) => <li key={reason}>{reason}</li>)}</ul></div> : null}
        {error ? <div className="error-panel">{error}</div> : null}
      </section>
    </div>
  );
}
