import { useEffect, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type {
  CameraSource,
  FolderImportEvidenceBatchCreateResponse,
  FolderImportEvidenceBatchDryRunResponse,
  FolderImportEvidenceBatchDryRunRequest,
  FolderImportPreviewRequest,
  FolderImportPreviewResponse,
  FolderImportCreatedMediaAsset,
  FolderImportRequest,
  FolderImportResponse,
  DemoDetectionRunCreate,
  DemoDetectionRunResult,
  DetectionProposalDecisionResult,
  ExternalUrlPreviewResponse,
  ExternalUrlPreviewSaveResponse,
  MediaAsset,
  MotionEvidencePromoteResponse,
  SavedPreviewMotionEvidenceResponse,
  SourceConnectionStatus,
  SourceProviderConfiguration,
  SourceProviderDefinition,
  SourceSetupReviewResponse,
  Stream,
  Zone,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel } from "../utils";

interface StreamsPageProps {
  streams: Stream[];
  sources: CameraSource[];
  onOpenImport: () => void;
  onOpenStream: (streamId: string) => void;
  onOpenMotionEvidence: (motionEvidenceId: string) => void;
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
  onOpenDetectionProposals: () => void;
  onOpenReview: () => void;
  onOpenExports: () => void;
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

function formatBytes(bytes?: number | null): string {
  if (bytes == null) {
    return "Unknown size";
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function parseIntegerAtLeast(value: string, label: string, minimum: number): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed) || parsed < minimum) {
    throw new Error(`${label} must be a whole number of at least ${minimum}.`);
  }
  return parsed;
}

function parseAllowedExtensions(value: string): string[] | null {
  const extensions = value
    .split(",")
    .map((extension) => extension.trim())
    .filter(Boolean);
  return extensions.length > 0 ? extensions : null;
}

function isReviewableZone(zone: Zone): boolean {
  return zone.is_active && zone.zone_type !== "privacy" && zone.zone_type !== "ignore";
}

function isImageMedia(asset: MediaAsset): boolean {
  return asset.media_type === "image" || asset.content_type.startsWith("image/");
}

function mediaProvenanceHint(asset: MediaAsset): string {
  const notes = asset.notes?.toLowerCase() ?? "";
  if (
    notes.includes("external_url") ||
    notes.includes("external url") ||
    notes.includes("preview")
  ) {
    return "external_url saved snapshot";
  }
  if (notes.includes("folder")) {
    return "folder import";
  }
  if (notes.includes("manual") || notes.includes("import")) {
    return "manual import";
  }
  return "local media";
}

interface TimelineMediaActionState {
  proposalResult?: DemoDetectionRunResult | null;
  proposalDecisionResult?: DetectionProposalDecisionResult | null;
  proposalMessage?: string | null;
  proposalError?: string | null;
  evidenceResult?: SavedPreviewMotionEvidenceResponse | null;
  evidenceError?: string | null;
  promotionResult?: MotionEvidencePromoteResponse | null;
  promotionError?: string | null;
  isCreatingProposal?: boolean;
  isConvertingProposal?: boolean;
  isCreatingEvidence?: boolean;
  isPromotingEvidence?: boolean;
}

const MEDIA_TIMELINE_LIMIT = 10;

export function StreamsPage({
  streams,
  sources,
  onOpenImport,
  onOpenStream,
  onOpenMotionEvidence,
  onOpenEvent,
  onOpenVisit,
  onOpenDetectionProposals,
  onOpenReview,
  onOpenExports,
}: StreamsPageProps) {
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
  const [previewResult, setPreviewResult] = useState<ExternalUrlPreviewResponse | null>(null);
  const [previewSaveResult, setPreviewSaveResult] =
    useState<ExternalUrlPreviewSaveResponse | null>(null);
  const [previewEvidenceResult, setPreviewEvidenceResult] =
    useState<SavedPreviewMotionEvidenceResponse | null>(null);
  const [previewPromotionResult, setPreviewPromotionResult] =
    useState<MotionEvidencePromoteResponse | null>(null);
  const [snapshotProposalResult, setSnapshotProposalResult] =
    useState<DemoDetectionRunResult | null>(null);
  const [snapshotProposalDecisionResult, setSnapshotProposalDecisionResult] =
    useState<DetectionProposalDecisionResult | null>(null);
  const [mediaAssets, setMediaAssets] = useState<MediaAsset[]>([]);
  const [previewZones, setPreviewZones] = useState<Zone[]>([]);
  const [selectedPreviewZoneId, setSelectedPreviewZoneId] = useState("");
  const [timelineZonesByStream, setTimelineZonesByStream] = useState<Record<string, Zone[]>>({});
  const [timelineSelectedZoneByStream, setTimelineSelectedZoneByStream] = useState<
    Record<string, string>
  >({});
  const [timelineZoneErrors, setTimelineZoneErrors] = useState<Record<string, string>>({});
  const [timelineActionState, setTimelineActionState] = useState<
    Record<string, TimelineMediaActionState>
  >({});
  const [folderPreviewResult, setFolderPreviewResult] =
    useState<FolderImportPreviewResponse | null>(null);
  const [folderImportResult, setFolderImportResult] = useState<FolderImportResponse | null>(null);
  const [folderEvidenceDryRunResult, setFolderEvidenceDryRunResult] =
    useState<FolderImportEvidenceBatchDryRunResponse | null>(null);
  const [folderEvidenceDryRunRequest, setFolderEvidenceDryRunRequest] =
    useState<FolderImportEvidenceBatchDryRunRequest | null>(null);
  const [folderEvidenceBatchCreateResult, setFolderEvidenceBatchCreateResult] =
    useState<FolderImportEvidenceBatchCreateResponse | null>(null);
  const [folderEvidenceResults, setFolderEvidenceResults] = useState<
    Record<string, SavedPreviewMotionEvidenceResponse>
  >({});
  const [folderEvidenceErrors, setFolderEvidenceErrors] = useState<Record<string, string>>({});
  const [folderRecursive, setFolderRecursive] = useState(false);
  const [folderAllowedExtensions, setFolderAllowedExtensions] = useState("jpg,jpeg,png,webp");
  const [folderMaxFiles, setFolderMaxFiles] = useState("500");
  const [folderMaxDepth, setFolderMaxDepth] = useState("1");
  const [folderImportNote, setFolderImportNote] = useState("");
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewSaveError, setPreviewSaveError] = useState<string | null>(null);
  const [previewEvidenceError, setPreviewEvidenceError] = useState<string | null>(null);
  const [previewPromotionError, setPreviewPromotionError] = useState<string | null>(null);
  const [snapshotProposalError, setSnapshotProposalError] = useState<string | null>(null);
  const [snapshotProposalMessage, setSnapshotProposalMessage] = useState<string | null>(null);
  const [previewZonesError, setPreviewZonesError] = useState<string | null>(null);
  const [mediaAssetsError, setMediaAssetsError] = useState<string | null>(null);
  const [folderPreviewError, setFolderPreviewError] = useState<string | null>(null);
  const [folderImportError, setFolderImportError] = useState<string | null>(null);
  const [folderEvidenceDryRunError, setFolderEvidenceDryRunError] = useState<string | null>(null);
  const [folderEvidenceBatchCreateError, setFolderEvidenceBatchCreateError] = useState<
    string | null
  >(null);
  const [isFetchingPreview, setIsFetchingPreview] = useState(false);
  const [isSavingPreview, setIsSavingPreview] = useState(false);
  const [isCreatingPreviewEvidence, setIsCreatingPreviewEvidence] = useState(false);
  const [isPromotingPreviewEvidence, setIsPromotingPreviewEvidence] = useState(false);
  const [isCreatingSnapshotProposal, setIsCreatingSnapshotProposal] = useState(false);
  const [isConvertingSnapshotProposal, setIsConvertingSnapshotProposal] = useState(false);
  const [isLoadingMediaAssets, setIsLoadingMediaAssets] = useState(false);
  const [isPreviewingFolderImport, setIsPreviewingFolderImport] = useState(false);
  const [isImportingFolderMedia, setIsImportingFolderMedia] = useState(false);
  const [isDryRunningFolderEvidence, setIsDryRunningFolderEvidence] = useState(false);
  const [isCreatingFolderEvidenceBatch, setIsCreatingFolderEvidenceBatch] = useState(false);
  const [folderEvidenceBatchConfirmed, setFolderEvidenceBatchConfirmed] = useState(false);
  const [folderEvidenceLoadingId, setFolderEvidenceLoadingId] = useState<string | null>(null);
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
  const selectedSourceStreamIds = selectedSourceStreams.map((stream) => stream.id).join("|");
  const selectedReviewStreams = new Map(
    (selectedSetupReview?.streams ?? []).map((stream) => [stream.stream_id, stream]),
  );
  const selectedProviderDefinition =
    providerDefinitions.find((definition) => definition.provider_key === providerKey) ??
    providerDefinitions.find(
      (definition) => definition.provider_key === selectedConfiguration?.provider_key,
    );

  useEffect(() => {
    setPreviewResult(null);
    setPreviewSaveResult(null);
    setPreviewEvidenceResult(null);
    setPreviewPromotionResult(null);
    setSnapshotProposalResult(null);
    setSnapshotProposalDecisionResult(null);
    setPreviewZones([]);
    setSelectedPreviewZoneId("");
    setPreviewError(null);
    setPreviewSaveError(null);
    setPreviewEvidenceError(null);
    setPreviewPromotionError(null);
    setSnapshotProposalError(null);
    setSnapshotProposalMessage(null);
    setPreviewZonesError(null);
    setFolderPreviewResult(null);
    setFolderImportResult(null);
    setFolderEvidenceDryRunResult(null);
    setFolderEvidenceDryRunRequest(null);
    setFolderEvidenceBatchCreateResult(null);
    setFolderPreviewError(null);
    setFolderImportError(null);
    setFolderEvidenceDryRunError(null);
    setFolderEvidenceBatchCreateError(null);
    setFolderEvidenceResults({});
    setFolderEvidenceErrors({});
    setIsFetchingPreview(false);
    setIsSavingPreview(false);
    setIsCreatingPreviewEvidence(false);
    setIsPromotingPreviewEvidence(false);
    setIsCreatingSnapshotProposal(false);
    setIsConvertingSnapshotProposal(false);
    setIsPreviewingFolderImport(false);
    setIsImportingFolderMedia(false);
    setIsDryRunningFolderEvidence(false);
    setIsCreatingFolderEvidenceBatch(false);
    setFolderEvidenceBatchConfirmed(false);
    setFolderEvidenceLoadingId(null);
  }, [selectedSourceId, selectedConfiguration?.provider_key]);

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

  useEffect(() => {
    void loadMediaAssets();
  }, []);

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

  async function loadMediaAssets(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoadingMediaAssets(true);
    }
    setMediaAssetsError(null);
    try {
      setMediaAssets(await apiClient.getMediaAssets());
    } catch (caught) {
      setMediaAssetsError(
        caught instanceof Error ? caught.message : "Could not load saved Stream media.",
      );
    } finally {
      if (showLoading) {
        setIsLoadingMediaAssets(false);
      }
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

  async function handleFetchStillImagePreview() {
    if (!selectedSourceId) {
      return;
    }

    setIsFetchingPreview(true);
    setPreviewError(null);
    setPreviewResult(null);
    setPreviewSaveError(null);
    setPreviewSaveResult(null);
    setPreviewEvidenceError(null);
    setPreviewEvidenceResult(null);
    setPreviewPromotionError(null);
    setPreviewPromotionResult(null);
    setSnapshotProposalError(null);
    setSnapshotProposalMessage(null);
    setSnapshotProposalResult(null);
    setSnapshotProposalDecisionResult(null);
    try {
      const result = await apiClient.fetchExternalUrlPreview(selectedSourceId, {});
      setPreviewResult(result);
    } catch (caught) {
      setPreviewError(
        caught instanceof Error ? caught.message : "Could not fetch still-image preview.",
      );
    } finally {
      setIsFetchingPreview(false);
    }
  }

  async function handleSaveStillImagePreview() {
    if (!selectedSourceId) {
      return;
    }

    setIsSavingPreview(true);
    setPreviewSaveError(null);
    setPreviewSaveResult(null);
    setPreviewEvidenceError(null);
    setPreviewEvidenceResult(null);
    setPreviewPromotionError(null);
    setPreviewPromotionResult(null);
    setSnapshotProposalError(null);
    setSnapshotProposalMessage(null);
    setSnapshotProposalResult(null);
    setSnapshotProposalDecisionResult(null);
    try {
      const result = await apiClient.saveExternalUrlPreview(selectedSourceId, {
        stream_id: selectedFirstStream?.id ?? null,
      });
      setPreviewSaveResult(result);
      await loadMediaAssets({ showLoading: false });
    } catch (caught) {
      setPreviewSaveError(
        caught instanceof Error ? caught.message : "Could not save still-image preview.",
      );
    } finally {
      setIsSavingPreview(false);
    }
  }

  function buildSnapshotProposalPayload(): DemoDetectionRunCreate | null {
    if (!previewSaveResult?.media_asset_id) {
      return null;
    }

    return {
      media_asset_id: previewSaveResult.media_asset_id,
      zone_id: selectedPreviewZoneId || null,
      label: "bird",
      confidence: 0.72,
      suggested_subject_label: "unknown_bird",
      suggested_species: "unknown_bird",
      notes:
        "External URL snapshot smoke path demo detector evidence only. " +
        "No model inspected the media and no reviewed truth was created.",
    };
  }

  async function handleCreateSnapshotProposal() {
    const payload = buildSnapshotProposalPayload();
    if (!payload) {
      setSnapshotProposalError("Save a snapshot as local media before creating proposal evidence.");
      return;
    }

    setIsCreatingSnapshotProposal(true);
    setSnapshotProposalError(null);
    setSnapshotProposalMessage(null);
    setSnapshotProposalDecisionResult(null);
    try {
      const result = await apiClient.createDemoDetectionRun(payload);
      setSnapshotProposalResult(result);
      setSnapshotProposalMessage(
        result.proposals.length > 0
          ? "Synthetic snapshot proposal evidence was created. Review correction still creates truth."
          : "Demo run completed without proposal evidence.",
      );
    } catch (caught) {
      setSnapshotProposalError(
        caught instanceof Error ? caught.message : "Snapshot proposal evidence could not be created.",
      );
    } finally {
      setIsCreatingSnapshotProposal(false);
    }
  }

  async function handleConvertSnapshotProposal() {
    const proposal = snapshotProposalResult?.proposals[0] ?? null;
    if (!proposal) {
      setSnapshotProposalError(
        "Create snapshot proposal evidence before converting it to Event/Visit context.",
      );
      return;
    }

    setIsConvertingSnapshotProposal(true);
    setSnapshotProposalError(null);
    setSnapshotProposalMessage(null);
    try {
      const result = await apiClient.decideDetectionProposal(proposal.id, {
        decision: "convert_to_event",
        event_title: "External URL snapshot proposal review",
        subject_label: "unknown_bird",
        species_guess: "unknown_bird",
        notes: "Converted from explicit external URL snapshot proposal action; still needs review/correction.",
      });
      setSnapshotProposalDecisionResult(result);
      setSnapshotProposalMessage(
        "Converted proposal into needs-review Event/Visit context. No ReviewLabel truth was created.",
      );
    } catch (caught) {
      setSnapshotProposalError(
        caught instanceof Error
          ? caught.message
          : "Snapshot proposal could not be converted.",
      );
    } finally {
      setIsConvertingSnapshotProposal(false);
    }
  }

  async function handleCreateMotionEvidenceFromSavedPreview() {
    if (!previewSaveResult?.media_asset_id) {
      return;
    }
    if (!selectedPreviewZoneId) {
      setPreviewEvidenceError("Choose an active reviewable Zone before creating evidence.");
      return;
    }

    setIsCreatingPreviewEvidence(true);
    setPreviewEvidenceError(null);
    setPreviewEvidenceResult(null);
    setPreviewPromotionError(null);
    setPreviewPromotionResult(null);
    try {
      const result = await apiClient.createMotionEvidenceFromMedia(
        previewSaveResult.media_asset_id,
        {
          stream_id: previewSaveResult.stream_id ?? selectedFirstStream?.id ?? null,
          zone_id: selectedPreviewZoneId,
          note: "Saved preview review handoff.",
          reason: "User requested pending evidence from saved media.",
          duplicate_policy: "skip_existing",
        },
      );
      setPreviewEvidenceResult(result);
    } catch (caught) {
      setPreviewEvidenceError(
        caught instanceof Error ? caught.message : "Could not create pending evidence.",
      );
    } finally {
      setIsCreatingPreviewEvidence(false);
    }
  }

  async function handlePromotePreviewEvidence() {
    if (!previewEvidenceResult?.motion_evidence_id) {
      return;
    }

    setIsPromotingPreviewEvidence(true);
    setPreviewPromotionError(null);
    setPreviewPromotionResult(null);
    try {
      const result = await apiClient.promoteMotionEvidence(
        previewEvidenceResult.motion_evidence_id,
        {
          event_title: "External URL snapshot review",
          visit_label_hint: "unknown_animal",
          notes: "Promoted by explicit external URL snapshot capture-to-review action.",
          create_event: true,
          create_visit: true,
          attach_snapshot_media_asset_id: previewSaveResult?.media_asset_id ?? undefined,
        },
      );
      setPreviewPromotionResult(result);
      setPreviewEvidenceResult((current) =>
        current
          ? {
              ...current,
              status: result.evidence.status,
            }
          : current,
      );
    } catch (caught) {
      setPreviewPromotionError(
        caught instanceof Error
          ? caught.message
          : "Could not promote pending evidence to reviewable Event/Visit.",
      );
    } finally {
      setIsPromotingPreviewEvidence(false);
    }
  }

  function updateTimelineActionState(mediaId: string, patch: TimelineMediaActionState) {
    setTimelineActionState((current) => ({
      ...current,
      [mediaId]: {
        ...(current[mediaId] ?? {}),
        ...patch,
      },
    }));
  }

  function timelineSelectedZoneId(asset: MediaAsset): string | null {
    return timelineSelectedZoneByStream[asset.stream_id] || null;
  }

  function buildTimelineProposalPayload(asset: MediaAsset): DemoDetectionRunCreate {
    return {
      media_asset_id: asset.id,
      zone_id: timelineSelectedZoneId(asset),
      label: "bird",
      confidence: 0.72,
      suggested_subject_label: "unknown_bird",
      suggested_species: "unknown_bird",
      notes:
        "Stream media timeline demo detector evidence only. " +
        "No model inspected the media and no reviewed truth was created.",
    };
  }

  async function handleCreateTimelineProposal(asset: MediaAsset) {
    if (!isImageMedia(asset)) {
      updateTimelineActionState(asset.id, {
        proposalError: "Only saved image media can create demo proposal evidence.",
      });
      return;
    }

    updateTimelineActionState(asset.id, {
      isCreatingProposal: true,
      proposalError: null,
      proposalMessage: null,
      proposalDecisionResult: null,
    });
    try {
      const result = await apiClient.createDemoDetectionRun(buildTimelineProposalPayload(asset));
      updateTimelineActionState(asset.id, {
        proposalResult: result,
        proposalMessage:
          result.proposals.length > 0
            ? "Synthetic timeline proposal evidence was created. Review correction still creates truth."
            : "Demo run completed without proposal evidence.",
      });
    } catch (caught) {
      updateTimelineActionState(asset.id, {
        proposalError:
          caught instanceof Error ? caught.message : "Timeline proposal evidence could not be created.",
      });
    } finally {
      updateTimelineActionState(asset.id, { isCreatingProposal: false });
    }
  }

  async function handleConvertTimelineProposal(asset: MediaAsset) {
    const proposal = timelineActionState[asset.id]?.proposalResult?.proposals[0] ?? null;
    if (!proposal) {
      updateTimelineActionState(asset.id, {
        proposalError: "Create timeline proposal evidence before converting it.",
      });
      return;
    }

    updateTimelineActionState(asset.id, {
      isConvertingProposal: true,
      proposalError: null,
      proposalMessage: null,
    });
    try {
      const result = await apiClient.decideDetectionProposal(proposal.id, {
        decision: "convert_to_event",
        event_title: "Stream media timeline proposal review",
        subject_label: "unknown_bird",
        species_guess: "unknown_bird",
        notes: "Converted from explicit Stream media timeline proposal action; still needs review/correction.",
      });
      updateTimelineActionState(asset.id, {
        proposalDecisionResult: result,
        proposalMessage:
          "Converted proposal into needs-review Event/Visit context. No ReviewLabel truth was created.",
      });
    } catch (caught) {
      updateTimelineActionState(asset.id, {
        proposalError:
          caught instanceof Error ? caught.message : "Timeline proposal could not be converted.",
      });
    } finally {
      updateTimelineActionState(asset.id, { isConvertingProposal: false });
    }
  }

  async function handleCreateTimelineEvidence(asset: MediaAsset) {
    const zoneId = timelineSelectedZoneId(asset);
    if (!isImageMedia(asset)) {
      updateTimelineActionState(asset.id, {
        evidenceError: "Only saved image media can create pending MotionEvidence.",
      });
      return;
    }
    if (!zoneId) {
      updateTimelineActionState(asset.id, {
        evidenceError: "Add an active non-privacy/non-ignore Zone before creating MotionEvidence.",
      });
      return;
    }

    updateTimelineActionState(asset.id, {
      isCreatingEvidence: true,
      evidenceError: null,
      promotionError: null,
      promotionResult: null,
    });
    try {
      const result = await apiClient.createMotionEvidenceFromMedia(asset.id, {
        stream_id: asset.stream_id,
        zone_id: zoneId,
        note: "Stream media timeline evidence handoff.",
        reason: "User requested pending evidence from saved Stream media.",
        duplicate_policy: "skip_existing",
      });
      updateTimelineActionState(asset.id, { evidenceResult: result });
    } catch (caught) {
      updateTimelineActionState(asset.id, {
        evidenceError:
          caught instanceof Error ? caught.message : "Timeline MotionEvidence could not be created.",
      });
    } finally {
      updateTimelineActionState(asset.id, { isCreatingEvidence: false });
    }
  }

  async function handlePromoteTimelineEvidence(asset: MediaAsset) {
    const currentEvidence = timelineActionState[asset.id]?.evidenceResult ?? null;
    const evidenceId = currentEvidence?.motion_evidence_id;
    if (!evidenceId) {
      return;
    }

    updateTimelineActionState(asset.id, {
      isPromotingEvidence: true,
      promotionError: null,
      promotionResult: null,
    });
    try {
      const result = await apiClient.promoteMotionEvidence(evidenceId, {
        event_title: "Stream media timeline review",
        visit_label_hint: "unknown_animal",
        notes: "Promoted by explicit Stream media timeline action.",
        create_event: true,
        create_visit: true,
        attach_snapshot_media_asset_id: asset.id,
      });
      updateTimelineActionState(asset.id, {
        promotionResult: result,
        evidenceResult: currentEvidence
          ? {
              ...currentEvidence,
              status: result.evidence.status,
            }
          : currentEvidence,
      });
    } catch (caught) {
      updateTimelineActionState(asset.id, {
        promotionError:
          caught instanceof Error ? caught.message : "Timeline MotionEvidence could not be promoted.",
      });
    } finally {
      updateTimelineActionState(asset.id, { isPromotingEvidence: false });
    }
  }

  function buildFolderPreviewRequest(): FolderImportPreviewRequest {
    return {
      recursive: folderRecursive,
      allowed_extensions: parseAllowedExtensions(folderAllowedExtensions),
      max_files: parseIntegerAtLeast(folderMaxFiles, "Max files", 1),
      max_depth: parseIntegerAtLeast(folderMaxDepth, "Max depth", 0),
    };
  }

  async function handlePreviewFolderImport() {
    if (!selectedSourceId) {
      return;
    }

    let requestPayload: FolderImportPreviewRequest;
    try {
      requestPayload = buildFolderPreviewRequest();
    } catch (caught) {
      setFolderPreviewError(
        caught instanceof Error ? caught.message : "Folder import preview settings are invalid.",
      );
      return;
    }

    setIsPreviewingFolderImport(true);
    setFolderPreviewError(null);
    setFolderImportError(null);
    setFolderPreviewResult(null);
    setFolderImportResult(null);
    setFolderEvidenceDryRunResult(null);
    setFolderEvidenceDryRunRequest(null);
    setFolderEvidenceBatchCreateResult(null);
    setFolderEvidenceDryRunError(null);
    setFolderEvidenceBatchCreateError(null);
    setFolderEvidenceBatchConfirmed(false);
    setFolderEvidenceResults({});
    setFolderEvidenceErrors({});
    setFolderEvidenceLoadingId(null);
    try {
      const result = await apiClient.previewFolderImport(selectedSourceId, requestPayload);
      setFolderPreviewResult(result);
    } catch (caught) {
      setFolderPreviewError(
        caught instanceof Error ? caught.message : "Could not preview folder import.",
      );
    } finally {
      setIsPreviewingFolderImport(false);
    }
  }

  async function handleImportPreviewedFolderFiles() {
    if (!selectedSourceId || !folderPreviewResult) {
      return;
    }
    if (folderPreviewResult.candidates.length === 0) {
      setFolderImportError("Preview has no supported files to import as MediaAssets.");
      return;
    }
    if (!selectedFirstStream) {
      setFolderImportError("Add Stream context before importing previewed files as MediaAssets.");
      return;
    }

    let previewOptions: FolderImportPreviewRequest;
    try {
      previewOptions = buildFolderPreviewRequest();
    } catch (caught) {
      setFolderImportError(
        caught instanceof Error ? caught.message : "Folder import settings are invalid.",
      );
      return;
    }

    const importPayload: FolderImportRequest = {
      ...previewOptions,
      relative_paths: folderPreviewResult.candidates.map((candidate) => candidate.relative_path),
      default_stream_id: selectedFirstStream.id,
      note: folderImportNote.trim() || null,
      copy_mode: "copy_to_media_root",
    };

    setIsImportingFolderMedia(true);
    setFolderImportError(null);
    setFolderImportResult(null);
    setFolderEvidenceDryRunResult(null);
    setFolderEvidenceDryRunRequest(null);
    setFolderEvidenceBatchCreateResult(null);
    setFolderEvidenceDryRunError(null);
    setFolderEvidenceBatchCreateError(null);
    setFolderEvidenceBatchConfirmed(false);
    setFolderEvidenceResults({});
    setFolderEvidenceErrors({});
    setFolderEvidenceLoadingId(null);
    try {
      const result = await apiClient.importFolderMedia(selectedSourceId, importPayload);
      setFolderImportResult(result);
      await loadMediaAssets({ showLoading: false });
    } catch (caught) {
      setFolderImportError(
        caught instanceof Error ? caught.message : "Could not import previewed folder files.",
      );
    } finally {
      setIsImportingFolderMedia(false);
    }
  }

  async function handleDryRunFolderEvidenceHandoff() {
    if (!folderImportResult || folderImportResult.imported.length === 0) {
      setFolderEvidenceDryRunError("Import folder media before dry-running evidence handoff.");
      return;
    }

    setIsDryRunningFolderEvidence(true);
    setFolderEvidenceDryRunError(null);
    setFolderEvidenceDryRunResult(null);
    setFolderEvidenceBatchCreateResult(null);
    setFolderEvidenceBatchCreateError(null);
    setFolderEvidenceBatchConfirmed(false);
    try {
      const requestPayload: FolderImportEvidenceBatchDryRunRequest = {
        media_asset_ids: folderImportResult.imported.map((item) => item.media_asset_id),
        duplicate_policy: "skip_existing",
        max_items: folderImportResult.imported.length,
      };
      const result = await apiClient.dryRunFolderImportEvidence(requestPayload);
      setFolderEvidenceDryRunRequest(requestPayload);
      setFolderEvidenceDryRunResult(result);
    } catch (caught) {
      setFolderEvidenceDryRunRequest(null);
      setFolderEvidenceDryRunError(
        caught instanceof Error ? caught.message : "Could not dry-run evidence handoff.",
      );
    } finally {
      setIsDryRunningFolderEvidence(false);
    }
  }

  async function handleCreateFolderEvidenceBatch() {
    if (!folderEvidenceDryRunResult || !folderEvidenceDryRunRequest) {
      setFolderEvidenceBatchCreateError("Dry-run eligible media before batch creation.");
      return;
    }
    if (!folderEvidenceBatchConfirmed) {
      setFolderEvidenceBatchCreateError("Confirm this batch before creating pending evidence.");
      return;
    }

    const eligibleMediaIds = folderEvidenceDryRunResult.items
      .filter((item) => item.would_create_motion_evidence)
      .map((item) => item.media_asset_id);
    if (eligibleMediaIds.length === 0) {
      setFolderEvidenceBatchCreateError("No eligible MediaAssets are available to create.");
      return;
    }

    setIsCreatingFolderEvidenceBatch(true);
    setFolderEvidenceBatchCreateError(null);
    setFolderEvidenceBatchCreateResult(null);
    try {
      const result = await apiClient.createFolderImportEvidenceBatch({
        ...folderEvidenceDryRunRequest,
        media_asset_ids: eligibleMediaIds,
        max_items: eligibleMediaIds.length,
        confirm: true,
        note: "Folder import batch evidence handoff.",
        reason: "User confirmed eligible folder-imported media from batch dry-run.",
      });
      setFolderEvidenceBatchCreateResult(result);
      setFolderEvidenceBatchConfirmed(false);
    } catch (caught) {
      setFolderEvidenceBatchCreateError(
        caught instanceof Error ? caught.message : "Could not create pending evidence batch.",
      );
    } finally {
      setIsCreatingFolderEvidenceBatch(false);
    }
  }

  async function handleCreateMotionEvidenceFromFolderImport(
    item: FolderImportCreatedMediaAsset,
  ) {
    setFolderEvidenceLoadingId(item.media_asset_id);
    setFolderEvidenceDryRunResult(null);
    setFolderEvidenceDryRunRequest(null);
    setFolderEvidenceBatchCreateResult(null);
    setFolderEvidenceDryRunError(null);
    setFolderEvidenceBatchCreateError(null);
    setFolderEvidenceBatchConfirmed(false);
    setFolderEvidenceErrors((current) => {
      const next = { ...current };
      delete next[item.media_asset_id];
      return next;
    });
    try {
      const result = await apiClient.createMotionEvidenceFromMedia(item.media_asset_id, {
        stream_id: item.stream_id ?? selectedFirstStream?.id ?? null,
        note: "Folder import evidence handoff.",
        reason: "User requested pending evidence from folder-imported media.",
        duplicate_policy: "skip_existing",
      });
      setFolderEvidenceResults((current) => ({
        ...current,
        [item.media_asset_id]: result,
      }));
    } catch (caught) {
      setFolderEvidenceErrors((current) => ({
        ...current,
        [item.media_asset_id]:
          caught instanceof Error ? caught.message : "Could not create pending evidence.",
      }));
    } finally {
      setFolderEvidenceLoadingId(null);
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
  const isExternalUrlProvider = selectedConfiguration?.provider_key === "external_url";
  const isFolderImportProvider =
    selectedSetupReview?.provider_key === "folder_import_future" ||
    selectedConfiguration?.provider_key === "folder_import_future";
  const isWebhookProvider =
    selectedSetupReview?.provider_key === "webhook_future" ||
    selectedConfiguration?.provider_key === "webhook_future";
  const selectedFirstStream = selectedSourceStreams[0] ?? null;

  useEffect(() => {
    let isMounted = true;

    if (selectedSourceStreams.length === 0) {
      setTimelineZonesByStream({});
      setTimelineSelectedZoneByStream({});
      setTimelineZoneErrors({});
      return () => {
        isMounted = false;
      };
    }

    async function loadTimelineZones() {
      const zoneEntries: Array<readonly [string, Zone[]]> = [];
      const errorEntries: Array<readonly [string, string]> = [];

      await Promise.all(
        selectedSourceStreams.map(async (stream) => {
          try {
            const zones = await apiClient.getStreamZones(stream.id);
            zoneEntries.push([stream.id, zones] as const);
          } catch (caught) {
            errorEntries.push([
              stream.id,
              caught instanceof Error ? caught.message : "Could not load Stream Zones.",
            ] as const);
          }
        }),
      );

      if (!isMounted) {
        return;
      }

      const nextZonesByStream = Object.fromEntries(zoneEntries);
      setTimelineZonesByStream(nextZonesByStream);
      setTimelineZoneErrors(Object.fromEntries(errorEntries));
      setTimelineSelectedZoneByStream((current) => {
        const next: Record<string, string> = {};
        for (const stream of selectedSourceStreams) {
          const reviewableZones = (nextZonesByStream[stream.id] ?? []).filter(isReviewableZone);
          const currentZoneId = current[stream.id];
          next[stream.id] =
            currentZoneId && reviewableZones.some((zone) => zone.id === currentZoneId)
              ? currentZoneId
              : reviewableZones[0]?.id ?? "";
        }
        return next;
      });
    }

    void loadTimelineZones();

    return () => {
      isMounted = false;
    };
  }, [selectedSourceStreamIds]);

  useEffect(() => {
    let isMounted = true;

    setPreviewZones([]);
    setSelectedPreviewZoneId("");
    setPreviewZonesError(null);
    if (!isExternalUrlProvider || !selectedFirstStream) {
      return () => {
        isMounted = false;
      };
    }

    async function loadPreviewZones() {
      try {
        const zones = await apiClient.getStreamZones(selectedFirstStream.id);
        if (!isMounted) {
          return;
        }
        setPreviewZones(zones);
        setSelectedPreviewZoneId(zones.find(isReviewableZone)?.id ?? "");
      } catch (caught) {
        if (isMounted) {
          setPreviewZonesError(
            caught instanceof Error ? caught.message : "Could not load Stream Zones.",
          );
        }
      }
    }

    void loadPreviewZones();

    return () => {
      isMounted = false;
    };
  }, [isExternalUrlProvider, selectedFirstStream]);

  const reviewablePreviewZones = previewZones.filter(isReviewableZone);
  const blockedPreviewZoneCount = previewZones.filter(
    (zone) => zone.is_active && !isReviewableZone(zone),
  ).length;
  const canSavePreview =
    previewResult?.status === "available" && Boolean(previewResult.preview_data_url);
  const canCreatePreviewEvidence =
    Boolean(previewSaveResult?.media_asset_id) &&
    Boolean(selectedFirstStream) &&
    Boolean(selectedPreviewZoneId);
  const canPromotePreviewEvidence = previewEvidenceResult?.status === "pending";
  const mediaAssetsByStream = new Map<string, MediaAsset[]>();
  for (const asset of mediaAssets) {
    const streamAssets = mediaAssetsByStream.get(asset.stream_id) ?? [];
    streamAssets.push(asset);
    mediaAssetsByStream.set(asset.stream_id, streamAssets);
  }
  for (const streamAssets of mediaAssetsByStream.values()) {
    streamAssets.sort(
      (left, right) =>
        new Date(right.created_at).getTime() - new Date(left.created_at).getTime(),
    );
  }
  const folderEvidenceDryRunEligibleCount =
    folderEvidenceDryRunResult?.items.filter((item) => item.would_create_motion_evidence).length ??
    0;
  const nextActionTitle = selectedSetupReview
    ? selectedSetupReview.readiness_level === "demo_ready"
      ? "Next: open Stream Detail and draw Zones."
      : isManualMediaReady
        ? "Next: import media for this Source/Stream."
        : isFolderImportProvider && selectedSetupReview.readiness_level === "needs_setup"
          ? "Next: complete folder path metadata."
        : isFolderImportProvider &&
            selectedSetupReview.readiness_level === "future_adapter_required"
          ? "Next: preview folder import explicitly."
        : isWebhookProvider && selectedSetupReview.readiness_level === "needs_setup"
          ? "Next: complete webhook shared secret metadata."
        : isWebhookProvider &&
            selectedSetupReview.readiness_level === "future_adapter_required"
          ? "Next: future webhook ingest implementation required."
        : isExternalUrlProvider && selectedSetupReview.readiness_level === "metadata_ready"
          ? "Next: fetch still-image preview explicitly."
          : selectedSetupReview.readiness_level === "needs_setup"
          ? "Next: complete setup metadata."
          : selectedSetupReview.readiness_level === "future_adapter_required"
            ? "Next: review explicit provider workflow before live playback."
            : "Next: review Source setup status."
    : "Next: load Source setup status.";
  const nextActionDetail =
    isWebhookProvider && selectedSetupReview?.readiness_level === "future_adapter_required"
      ? "Webhook UI ingest is future work."
      : isFolderImportProvider && selectedSetupReview?.readiness_level === "future_adapter_required"
      ? "Preview first, then import as MediaAssets."
      : selectedSetupReview?.next_step ?? selectedConnection?.setup_hint;

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Stream-first workspace"
        title="Streams"
        description="Connect Sources, inspect Streams, configure setup metadata, then draw Zones and review activity."
      />
      <section className="notice-panel onboarding-provider-note">
        <strong>Provider setup is metadata first</strong>
        <span>Use explicit preview, import, or evidence actions below. Live playback is future work.</span>
      </section>
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
              {isExternalUrlProvider ? (
                <div className="external-preview-panel">
                  <div className="item-title-row">
                    <h3>Snapshot capture for review</h3>
                    <StatusPill
                      label={previewResult ? formatLabel(previewResult.status) : "Explicit"}
                      tone={previewResult?.status === "available" ? "good" : "quiet"}
                    />
                  </div>
                  <p>
                    Fetch one still-image snapshot, save it as local media, then choose whether it
                    should become pending evidence for review.
                  </p>
                  <div className="source-connection-meta">
                    <span>Still-image snapshot only</span>
                    <span>Not live video</span>
                    <span>Preview creates no records</span>
                    <span>Save creates MediaAsset only</span>
                    <span>Correction creates truth</span>
                  </div>
                  <button
                    className="secondary-action"
                    disabled={isFetchingPreview}
                    onClick={handleFetchStillImagePreview}
                    type="button"
                  >
                    {isFetchingPreview ? "Fetching preview..." : "Fetch still-image preview"}
                  </button>
                  {previewError ? <div className="zone-error">{previewError}</div> : null}
                  {previewResult ? (
                    <div className="external-preview-result">
                      <strong>{previewResult.message}</strong>
                      {previewResult.warnings.length > 0 ? (
                        <div className="source-warning-list">
                          {previewResult.warnings.map((warning) => (
                            <span key={warning}>{warning}</span>
                          ))}
                        </div>
                      ) : null}
                      {previewResult.preview_data_url ? (
                        <div className="external-preview-image-frame">
                          <img
                            alt="External URL still-image preview"
                            src={previewResult.preview_data_url}
                          />
                        </div>
                      ) : null}
                      <div className="source-connection-meta">
                        {previewResult.content_type ? (
                          <span>Content: {previewResult.content_type}</span>
                        ) : null}
                        {previewResult.bytes_read !== null &&
                        previewResult.bytes_read !== undefined ? (
                          <span>Bytes read: {previewResult.bytes_read}</span>
                        ) : null}
                        <span>Not saved</span>
                        <span>No Events/Visits created</span>
                      </div>
                      {canSavePreview ? (
                        <div className="external-preview-save-actions">
                          <button
                            className="primary-action"
                            disabled={isSavingPreview}
                            onClick={handleSaveStillImagePreview}
                            type="button"
                          >
                            {isSavingPreview
                              ? "Saving preview..."
                              : "Save preview as local media"}
                          </button>
                          <span className="meta-text">
                            Saved as local media only. No Events, Visits, or truth will be created.
                          </span>
                        </div>
                      ) : null}
                      {previewSaveError ? <div className="zone-error">{previewSaveError}</div> : null}
                      {previewSaveResult ? (
                        <div className="external-preview-save-status">
                          <strong>{previewSaveResult.message}</strong>
                          <div className="source-connection-meta">
                            {previewSaveResult.media_asset_id ? (
                              <span>MediaAsset: {previewSaveResult.media_asset_id}</span>
                            ) : null}
                            {previewSaveResult.content_type ? (
                              <span>Content: {previewSaveResult.content_type}</span>
                            ) : null}
                            {previewSaveResult.file_name ? (
                              <span>File: {previewSaveResult.file_name}</span>
                            ) : null}
                            {previewSaveResult.relative_path ? (
                              <span>Path: {previewSaveResult.relative_path}</span>
                            ) : null}
                            <span>Bytes written: {previewSaveResult.bytes_written}</span>
                          </div>
                          <span className="meta-text">
                            Saved as local media only. No Events, Visits, or truth were created.
                          </span>
                          {previewSaveResult.media_asset_id ? (
                            <a
                              className="inline-link"
                              href={apiClient.mediaFileUrl(previewSaveResult.media_asset_id)}
                              rel="noreferrer"
                              target="_blank"
                            >
                              Open saved media
                            </a>
                          ) : null}
                          {previewSaveResult.media_asset_id ? (
                            <div className="external-preview-proposal-status">
                              <div className="section-heading">
                                <div>
                                  <span className="meta-text">Track B</span>
                                  <h3>Create snapshot proposal evidence</h3>
                                </div>
                                <StatusPill label="Synthetic evidence" tone="quiet" />
                              </div>
                              <p>
                                Create synthetic demo proposal evidence from this saved snapshot.
                                No model inspects the media and no reviewed truth is created.
                              </p>
                              <div className="import-flow-strip">
                                <span>Saved snapshot</span>
                                <span>DetectionProposal evidence</span>
                                <span>Review correction truth</span>
                              </div>
                              {snapshotProposalMessage ? (
                                <div className="notice-panel compact-notice">
                                  {snapshotProposalMessage}
                                </div>
                              ) : null}
                              {snapshotProposalError ? (
                                <div className="zone-error">{snapshotProposalError}</div>
                              ) : null}
                              <div className="detail-actions">
                                <button
                                  className="primary-action"
                                  disabled={
                                    isCreatingSnapshotProposal ||
                                    isConvertingSnapshotProposal
                                  }
                                  onClick={handleCreateSnapshotProposal}
                                  type="button"
                                >
                                  {isCreatingSnapshotProposal
                                    ? "Creating..."
                                    : "Create demo proposal"}
                                </button>
                                {snapshotProposalResult?.proposals[0] &&
                                !snapshotProposalDecisionResult ? (
                                  <button
                                    className="secondary-action"
                                    disabled={isConvertingSnapshotProposal}
                                    onClick={handleConvertSnapshotProposal}
                                    type="button"
                                  >
                                    {isConvertingSnapshotProposal
                                      ? "Converting..."
                                      : "Convert first proposal to Event/Visit"}
                                  </button>
                                ) : null}
                                <button
                                  className="secondary-action"
                                  onClick={onOpenDetectionProposals}
                                  type="button"
                                >
                                  Open Detection Proposals
                                </button>
                                <button
                                  className="secondary-action"
                                  onClick={onOpenReview}
                                  type="button"
                                >
                                  Open Review Queue
                                </button>
                              </div>
                              {snapshotProposalResult ? (
                                <div className="import-smoke-result-grid">
                                  <div className="data-row">
                                    <span>DetectionRun ID</span>
                                    <strong>{snapshotProposalResult.detection_run.id}</strong>
                                  </div>
                                  <div className="data-row">
                                    <span>Proposal IDs</span>
                                    <strong>
                                      {snapshotProposalResult.proposals.length > 0
                                        ? snapshotProposalResult.proposals
                                            .map((proposal) => proposal.id)
                                            .join(", ")
                                        : "none"}
                                    </strong>
                                  </div>
                                  <div className="data-row">
                                    <span>Review Queue</span>
                                    <strong>
                                      {snapshotProposalResult.review_queue_count} needs review
                                    </strong>
                                  </div>
                                  {snapshotProposalResult.proposals.map((proposal) => (
                                    <div className="data-row" key={proposal.id}>
                                      <span>{proposal.id}</span>
                                      <strong>
                                        {proposal.label} / {Math.round(proposal.confidence * 100)}
                                        % / {formatLabel(proposal.status)}
                                      </strong>
                                    </div>
                                  ))}
                                </div>
                              ) : null}
                              {snapshotProposalDecisionResult ? (
                                <div className="import-smoke-result-grid">
                                  <div className="data-row">
                                    <span>Converted proposal</span>
                                    <strong>
                                      {snapshotProposalDecisionResult.proposal.id}
                                    </strong>
                                  </div>
                                  <div className="data-row">
                                    <span>Event</span>
                                    {snapshotProposalDecisionResult.event ? (
                                      <button
                                        className="inline-link-button"
                                        onClick={() =>
                                          onOpenEvent(
                                            snapshotProposalDecisionResult.event!.id,
                                          )
                                        }
                                        type="button"
                                      >
                                        {snapshotProposalDecisionResult.event.id}
                                      </button>
                                    ) : (
                                      <strong>not created</strong>
                                    )}
                                  </div>
                                  <div className="data-row">
                                    <span>Visit</span>
                                    {snapshotProposalDecisionResult.visit ? (
                                      <button
                                        className="inline-link-button"
                                        onClick={() =>
                                          onOpenVisit(
                                            snapshotProposalDecisionResult.visit!.id,
                                          )
                                        }
                                        type="button"
                                      >
                                        {snapshotProposalDecisionResult.visit.id}
                                      </button>
                                    ) : (
                                      <strong>not created</strong>
                                    )}
                                  </div>
                                </div>
                              ) : null}
                              <div className="notice-panel compact-notice import-smoke-boundary">
                                <strong>Truth boundary</strong>
                                <ul>
                                  <li>Demo proposal is synthetic evidence.</li>
                                  <li>No model inspected the snapshot.</li>
                                  <li>No ReviewLabel truth was created.</li>
                                  <li>Correction remains explicit in the Review Queue.</li>
                                </ul>
                              </div>
                            </div>
                          ) : null}
                          {previewSaveResult.media_asset_id ? (
                            <div className="external-preview-evidence-actions">
                              <div className="section-heading">
                                <div>
                                  <span className="meta-text">Track A</span>
                                  <h3>Create MotionEvidence</h3>
                                </div>
                                <StatusPill label="Pending evidence" tone="quiet" />
                              </div>
                              <p className="meta-text">
                                This track keeps the saved snapshot attached to pending
                                MotionEvidence, with optional explicit Event/Visit promotion.
                              </p>
                              <label className="external-preview-zone-select">
                                Review zone
                                <select
                                  disabled={reviewablePreviewZones.length === 0}
                                  onChange={(event) =>
                                    setSelectedPreviewZoneId(event.target.value)
                                  }
                                  value={selectedPreviewZoneId}
                                >
                                  {reviewablePreviewZones.length > 0 ? (
                                    reviewablePreviewZones.map((zone) => (
                                      <option key={zone.id} value={zone.id}>
                                        {zone.name} ({formatLabel(zone.zone_type)})
                                      </option>
                                    ))
                                  ) : (
                                    <option value="">No reviewable Zones</option>
                                  )}
                                </select>
                              </label>
                              {previewZonesError ? (
                                <div className="zone-error">{previewZonesError}</div>
                              ) : null}
                              {!selectedFirstStream ? (
                                <div className="zone-error">
                                  Add Stream context before creating evidence.
                                </div>
                              ) : null}
                              {selectedFirstStream && reviewablePreviewZones.length === 0 ? (
                                <div className="zone-error">
                                  Draw an active reviewable Zone on the related Stream before
                                  creating evidence.
                                </div>
                              ) : null}
                              {blockedPreviewZoneCount > 0 ? (
                                <span className="meta-text">
                                  Privacy and ignore Zones are excluded from evidence creation.
                                </span>
                              ) : null}
                              <button
                                className="secondary-action"
                                disabled={isCreatingPreviewEvidence || !canCreatePreviewEvidence}
                                onClick={handleCreateMotionEvidenceFromSavedPreview}
                                type="button"
                              >
                                {isCreatingPreviewEvidence
                                  ? "Creating pending evidence..."
                                  : "Create pending evidence from saved media"}
                              </button>
                              <span className="meta-text">
                                This creates pending evidence only. It does not create Events,
                                Visits, labels, or truth.
                              </span>
                            </div>
                          ) : null}
                          {previewEvidenceError ? (
                            <div className="zone-error">{previewEvidenceError}</div>
                          ) : null}
                          {previewEvidenceResult ? (
                            <div className="external-preview-evidence-status">
                              <strong>{previewEvidenceResult.message}</strong>
                              <div className="source-connection-meta">
                                <span>
                                  MotionEvidence: {previewEvidenceResult.motion_evidence_id}
                                </span>
                                {previewEvidenceResult.zone_id ? (
                                  <span>Zone: {previewEvidenceResult.zone_id}</span>
                                ) : null}
                                <span>Status: {formatLabel(previewEvidenceResult.status)}</span>
                              </div>
                              <span className="meta-text">
                                Pending evidence is not truth. Promotion can create reviewable
                                Event/Visit records, and Review Queue correction still creates the
                                dataset label.
                              </span>
                              {previewEvidenceResult.warnings.length > 0 ? (
                                <div className="source-warning-list">
                                  {previewEvidenceResult.warnings.map((warning) => (
                                    <span key={warning}>{warning}</span>
                                  ))}
                                </div>
                              ) : null}
                              <div className="detail-actions">
                                <button
                                  className="secondary-action"
                                  onClick={() =>
                                    onOpenMotionEvidence(
                                      previewEvidenceResult.motion_evidence_id,
                                    )
                                  }
                                  type="button"
                                >
                                  Open Motion Evidence
                                </button>
                                <button
                                  className="primary-action"
                                  disabled={
                                    isPromotingPreviewEvidence || !canPromotePreviewEvidence
                                  }
                                  onClick={handlePromotePreviewEvidence}
                                  type="button"
                                >
                                  {isPromotingPreviewEvidence
                                    ? "Promoting..."
                                    : "Promote to Event/Visit"}
                                </button>
                              </div>
                              {previewPromotionError ? (
                                <div className="zone-error">{previewPromotionError}</div>
                              ) : null}
                              {previewPromotionResult ? (
                                <div className="external-preview-promotion-status">
                                  <strong>
                                    Promoted to reviewable Event/Visit evidence.
                                  </strong>
                                  <div className="source-connection-meta">
                                    {previewPromotionResult.event_id ? (
                                      <span>Event: {previewPromotionResult.event_id}</span>
                                    ) : null}
                                    {previewPromotionResult.visit_id ? (
                                      <span>Visit: {previewPromotionResult.visit_id}</span>
                                    ) : null}
                                    <span>
                                      Evidence:{" "}
                                      {formatLabel(previewPromotionResult.evidence.status)}
                                    </span>
                                  </div>
                                  <span className="meta-text">
                                    No ReviewLabel truth was created. Correct the Visit in Review
                                    Queue before using reviewed-only exports.
                                  </span>
                                  <div className="detail-actions">
                                    {previewPromotionResult.event_id ? (
                                      <button
                                        className="secondary-action"
                                        onClick={() =>
                                          onOpenEvent(previewPromotionResult.event_id!)
                                        }
                                        type="button"
                                      >
                                        Open Event
                                      </button>
                                    ) : null}
                                    {previewPromotionResult.visit_id ? (
                                      <button
                                        className="secondary-action"
                                        onClick={() =>
                                          onOpenVisit(previewPromotionResult.visit_id!)
                                        }
                                        type="button"
                                      >
                                        Open Visit
                                      </button>
                                    ) : null}
                                    <button
                                      className="primary-action"
                                      onClick={onOpenReview}
                                      type="button"
                                    >
                                      Correct in Review Queue
                                    </button>
                                    <button
                                      className="secondary-action"
                                      onClick={onOpenExports}
                                      type="button"
                                    >
                                      Open Dataset Exports
                                    </button>
                                  </div>
                                </div>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}
              {isFolderImportProvider ? (
                <div className="folder-source-import-panel">
                  <div className="item-title-row">
                    <h3>Folder import</h3>
                    <StatusPill
                      label={folderPreviewResult ? "Preview ready" : "Explicit"}
                      tone={folderPreviewResult ? "good" : "quiet"}
                    />
                  </div>
                  <p>
                    Folder import is explicit. Preview scans the configured folder and creates no
                    records. Import copies supported files into local media and creates MediaAssets
                    only.
                  </p>
                  <p className="meta-text">
                    Evidence handoff stays explicit and review-only. No Events, Visits, labels, or
                    truth are created here.
                  </p>
                  <div className="folder-import-control-grid">
                    <label className="checkbox-row">
                      <input
                        checked={folderRecursive}
                        onChange={(event) => {
                          setFolderRecursive(event.target.checked);
                          setFolderPreviewResult(null);
                          setFolderImportResult(null);
                        }}
                        type="checkbox"
                      />
                      Recursive
                    </label>
                    <label>
                      Allowed extensions
                      <input
                        onChange={(event) => {
                          setFolderAllowedExtensions(event.target.value);
                          setFolderPreviewResult(null);
                          setFolderImportResult(null);
                        }}
                        value={folderAllowedExtensions}
                      />
                    </label>
                    <label>
                      Max files
                      <input
                        min="1"
                        onChange={(event) => {
                          setFolderMaxFiles(event.target.value);
                          setFolderPreviewResult(null);
                          setFolderImportResult(null);
                        }}
                        type="number"
                        value={folderMaxFiles}
                      />
                    </label>
                    <label>
                      Max depth
                      <input
                        min="0"
                        onChange={(event) => {
                          setFolderMaxDepth(event.target.value);
                          setFolderPreviewResult(null);
                          setFolderImportResult(null);
                        }}
                        type="number"
                        value={folderMaxDepth}
                      />
                    </label>
                  </div>
                  <label>
                    Import note
                    <textarea
                      onChange={(event) => setFolderImportNote(event.target.value)}
                      placeholder="optional local media context"
                      value={folderImportNote}
                    />
                  </label>
                  <div className="folder-import-actions">
                    <button
                      className="secondary-action"
                      disabled={isPreviewingFolderImport}
                      onClick={() => void handlePreviewFolderImport()}
                      type="button"
                    >
                      {isPreviewingFolderImport
                        ? "Previewing folder import..."
                        : "Preview folder import"}
                    </button>
                    {folderPreviewResult ? (
                      <button
                        className="primary-action"
                        disabled={
                          isImportingFolderMedia ||
                          folderPreviewResult.candidates.length === 0 ||
                          !selectedFirstStream
                        }
                        onClick={() => void handleImportPreviewedFolderFiles()}
                        type="button"
                      >
                        {isImportingFolderMedia
                          ? "Importing as MediaAssets..."
                          : "Import previewed files as MediaAssets"}
                      </button>
                    ) : null}
                  </div>
                  {selectedFirstStream ? (
                    <span className="meta-text">
                      Stream context: {selectedFirstStream.name}. Local media stays linked to this
                      Source/Stream context.
                    </span>
                  ) : (
                    <span className="meta-text">
                      This Source has no related Stream yet, so import will wait for Stream context.
                    </span>
                  )}
                  {folderPreviewError ? <div className="zone-error">{folderPreviewError}</div> : null}
                  {folderImportError ? <div className="zone-error">{folderImportError}</div> : null}
                  {folderPreviewResult ? (
                    <div className="folder-import-preview-result">
                      <div className="folder-import-summary-grid">
                        <div>
                          <span>Candidates</span>
                          <strong>{folderPreviewResult.total_candidates}</strong>
                        </div>
                        <div>
                          <span>Skipped</span>
                          <strong>{folderPreviewResult.total_skipped}</strong>
                        </div>
                        <div>
                          <span>Known bytes</span>
                          <strong>{formatBytes(folderPreviewResult.total_known_bytes)}</strong>
                        </div>
                        <div>
                          <span>Unknown sizes</span>
                          <strong>{folderPreviewResult.unknown_size_count}</strong>
                        </div>
                      </div>
                      <div className="source-connection-meta">
                        <span>Scanned: {formatDateTime(folderPreviewResult.scanned_at)}</span>
                        <span>Dry run: {folderPreviewResult.dry_run ? "Yes" : "No"}</span>
                        <span>
                          Creates MediaAssets:{" "}
                          {folderPreviewResult.creates_media_assets ? "Yes" : "No"}
                        </span>
                        <span>
                          Creates Events/Visits:{" "}
                          {folderPreviewResult.creates_events ||
                          folderPreviewResult.creates_visits
                            ? "Yes"
                            : "No"}
                        </span>
                        <span>
                          Creates truth: {folderPreviewResult.creates_truth ? "Yes" : "No"}
                        </span>
                      </div>
                      <span className="meta-text">
                        Preview only: no MediaAssets, Events, Visits, labels, or truth were
                        created.
                      </span>
                      {folderPreviewResult.warnings.length > 0 ? (
                        <div className="source-warning-list">
                          {folderPreviewResult.warnings.map((warning) => (
                            <span key={warning}>{warning}</span>
                          ))}
                        </div>
                      ) : null}
                      <div className="folder-import-list-grid">
                        <div className="folder-import-list">
                          <div className="item-title-row">
                            <strong>Candidates</strong>
                            <StatusPill
                              label={`${folderPreviewResult.candidates.length} files`}
                              tone="good"
                            />
                          </div>
                          {folderPreviewResult.candidates.length > 0 ? (
                            folderPreviewResult.candidates.map((candidate) => (
                              <article
                                className="folder-import-file-card"
                                key={candidate.relative_path}
                              >
                                <strong>{candidate.file_name}</strong>
                                <span>{candidate.relative_path}</span>
                                <div className="source-connection-meta">
                                  <span>{candidate.extension}</span>
                                  <span>{candidate.planned_media_kind}</span>
                                  <span>{formatBytes(candidate.size_bytes)}</span>
                                  {candidate.modified_at ? (
                                    <span>{formatDateTime(candidate.modified_at)}</span>
                                  ) : null}
                                </div>
                                {candidate.warnings.length > 0 ? (
                                  <div className="source-warning-list">
                                    {candidate.warnings.map((warning) => (
                                      <span key={warning}>{warning}</span>
                                    ))}
                                  </div>
                                ) : null}
                              </article>
                            ))
                          ) : (
                            <span className="meta-text">No supported files in this preview.</span>
                          )}
                        </div>
                        <div className="folder-import-list">
                          <div className="item-title-row">
                            <strong>Skipped</strong>
                            <StatusPill
                              label={`${folderPreviewResult.skipped.length} skipped`}
                              tone="quiet"
                            />
                          </div>
                          {folderPreviewResult.skipped.length > 0 ? (
                            folderPreviewResult.skipped.map((skipped) => (
                              <article
                                className="folder-import-file-card"
                                key={`${skipped.relative_path ?? skipped.file_name ?? "file"}-${
                                  skipped.reason
                                }-${skipped.message}`}
                              >
                                <strong>
                                  {skipped.file_name ?? skipped.relative_path ?? "Skipped file"}
                                </strong>
                                {skipped.relative_path ? <span>{skipped.relative_path}</span> : null}
                                <div className="source-connection-meta">
                                  <span>{formatLabel(skipped.reason)}</span>
                                  <span>{skipped.message}</span>
                                </div>
                              </article>
                            ))
                          ) : (
                            <span className="meta-text">No skipped files in this preview.</span>
                          )}
                        </div>
                      </div>
                    </div>
                  ) : null}
                  {folderImportResult ? (
                    <div className="folder-import-result-panel">
                      <div className="item-title-row">
                        <strong>Import result</strong>
                        <StatusPill
                          label={`${folderImportResult.total_imported} MediaAssets`}
                          tone={folderImportResult.total_imported > 0 ? "good" : "quiet"}
                        />
                      </div>
                      <div className="folder-import-summary-grid">
                        <div>
                          <span>Imported</span>
                          <strong>{folderImportResult.total_imported}</strong>
                        </div>
                        <div>
                          <span>Skipped</span>
                          <strong>{folderImportResult.total_skipped}</strong>
                        </div>
                        <div>
                          <span>Bytes copied</span>
                          <strong>{formatBytes(folderImportResult.total_bytes_copied)}</strong>
                        </div>
                        <div>
                          <span>Copy mode</span>
                          <strong>{formatLabel(folderImportResult.copy_mode)}</strong>
                        </div>
                      </div>
                      <span className="meta-text">
                        MediaAssets only. No MotionEvidence, Events, Visits, labels, or truth were
                        created.
                      </span>
                      {folderImportResult.warnings.length > 0 ? (
                        <div className="source-warning-list">
                          {folderImportResult.warnings.map((warning) => (
                            <span key={warning}>{warning}</span>
                          ))}
                        </div>
                      ) : null}
                      {folderImportResult.imported.length > 0 ? (
                        <div className="folder-evidence-dry-run-panel">
                          <div className="item-title-row">
                            <strong>Evidence handoff dry-run</strong>
                            {folderEvidenceDryRunResult ? (
                              <StatusPill
                                label={`${folderEvidenceDryRunResult.eligible_count} eligible`}
                                tone={
                                  folderEvidenceDryRunResult.eligible_count > 0
                                    ? "good"
                                    : "quiet"
                                }
                              />
                            ) : null}
                          </div>
                          <div className="folder-evidence-action">
                            <button
                              className="secondary-action"
                              disabled={isDryRunningFolderEvidence}
                              onClick={() => void handleDryRunFolderEvidenceHandoff()}
                              type="button"
                            >
                              {isDryRunningFolderEvidence
                                ? "Dry-running evidence handoff..."
                                : "Dry-run evidence handoff"}
                            </button>
                            <span className="meta-text">
                              Dry run only. No MotionEvidence, Events, Visits, labels, or truth
                              were created.
                            </span>
                          </div>
                          {folderEvidenceDryRunError ? (
                            <div className="zone-error">{folderEvidenceDryRunError}</div>
                          ) : null}
                          {folderEvidenceDryRunResult ? (
                            <>
                              <div className="folder-import-summary-grid">
                                <div>
                                  <span>Items checked</span>
                                  <strong>{folderEvidenceDryRunResult.total_items}</strong>
                                </div>
                                <div>
                                  <span>Would create</span>
                                  <strong>{folderEvidenceDryRunResult.would_create_count}</strong>
                                </div>
                                <div>
                                  <span>Duplicates skipped</span>
                                  <strong>
                                    {folderEvidenceDryRunResult.duplicate_skipped_count}
                                  </strong>
                                </div>
                                <div>
                                  <span>Skipped</span>
                                  <strong>{folderEvidenceDryRunResult.skipped_count}</strong>
                                </div>
                              </div>
                              {folderEvidenceDryRunResult.warnings.length > 0 ? (
                                <div className="source-warning-list">
                                  {folderEvidenceDryRunResult.warnings.map((warning) => (
                                    <span key={warning}>{warning}</span>
                                  ))}
                                </div>
                              ) : null}
                              <div className="folder-evidence-dry-run-list">
                                {folderEvidenceDryRunResult.items.map((item) => (
                                  <article
                                    className="folder-import-file-card"
                                    key={`${item.media_asset_id}-${item.skip_reason ?? "eligible"}`}
                                  >
                                    <div className="item-title-row">
                                      <strong>{item.file_name ?? item.media_asset_id}</strong>
                                      <StatusPill
                                        label={
                                          item.would_create_motion_evidence
                                            ? "Would create"
                                            : formatLabel(item.skip_reason ?? "Skipped")
                                        }
                                        tone={
                                          item.would_create_motion_evidence ? "good" : "quiet"
                                        }
                                      />
                                    </div>
                                    <div className="source-connection-meta">
                                      <span>{item.media_asset_id}</span>
                                      {item.stream_id ? <span>Stream: {item.stream_id}</span> : null}
                                      {item.zone_id ? <span>Zone: {item.zone_id}</span> : null}
                                      {item.existing_motion_evidence_id ? (
                                        <span>
                                          Existing MotionEvidence:{" "}
                                          {item.existing_motion_evidence_id}
                                        </span>
                                      ) : null}
                                    </div>
                                    {item.warnings.length > 0 ? (
                                      <div className="source-warning-list">
                                        {item.warnings.map((warning) => (
                                          <span key={warning}>{warning}</span>
                                        ))}
                                      </div>
                                    ) : null}
                                  </article>
                                ))}
                              </div>
                              <div className="folder-evidence-batch-create-panel">
                                <div className="item-title-row">
                                  <strong>Confirmed batch creation</strong>
                                  <StatusPill
                                    label={`${folderEvidenceDryRunEligibleCount} eligible`}
                                    tone={
                                      folderEvidenceDryRunEligibleCount > 0 ? "good" : "quiet"
                                    }
                                  />
                                </div>
                                <label className="checkbox-row">
                                  <input
                                    checked={folderEvidenceBatchConfirmed}
                                    disabled={folderEvidenceDryRunEligibleCount === 0}
                                    onChange={(event) =>
                                      setFolderEvidenceBatchConfirmed(event.target.checked)
                                    }
                                    type="checkbox"
                                  />
                                  Confirm eligible media
                                </label>
                                <div className="folder-evidence-action">
                                  <button
                                    className="primary-action"
                                    disabled={
                                      isCreatingFolderEvidenceBatch ||
                                      !folderEvidenceBatchConfirmed ||
                                      folderEvidenceDryRunEligibleCount === 0
                                    }
                                    onClick={() => void handleCreateFolderEvidenceBatch()}
                                    type="button"
                                  >
                                    {isCreatingFolderEvidenceBatch
                                      ? "Creating pending evidence..."
                                      : "Create pending evidence for eligible media"}
                                  </button>
                                  <span className="meta-text">
                                    Creates pending MotionEvidence only. No Events, Visits, labels,
                                    or truth are created.
                                  </span>
                                </div>
                                {folderEvidenceBatchCreateError ? (
                                  <div className="zone-error">
                                    {folderEvidenceBatchCreateError}
                                  </div>
                                ) : null}
                                {folderEvidenceBatchCreateResult ? (
                                  <div className="folder-evidence-result">
                                    <strong>{folderEvidenceBatchCreateResult.message}</strong>
                                    <div className="folder-import-summary-grid">
                                      <div>
                                        <span>Created</span>
                                        <strong>
                                          {folderEvidenceBatchCreateResult.created_count}
                                        </strong>
                                      </div>
                                      <div>
                                        <span>Skipped</span>
                                        <strong>
                                          {folderEvidenceBatchCreateResult.skipped_count}
                                        </strong>
                                      </div>
                                      <div>
                                        <span>Duplicates skipped</span>
                                        <strong>
                                          {
                                            folderEvidenceBatchCreateResult.duplicate_skipped_count
                                          }
                                        </strong>
                                      </div>
                                      <div>
                                        <span>Items</span>
                                        <strong>
                                          {folderEvidenceBatchCreateResult.total_items}
                                        </strong>
                                      </div>
                                    </div>
                                    {folderEvidenceBatchCreateResult.warnings.length > 0 ? (
                                      <div className="source-warning-list">
                                        {folderEvidenceBatchCreateResult.warnings.map((warning) => (
                                          <span key={warning}>{warning}</span>
                                        ))}
                                      </div>
                                    ) : null}
                                    <div className="folder-evidence-dry-run-list">
                                      {folderEvidenceBatchCreateResult.items.map((item) => (
                                        <article
                                          className="folder-import-file-card"
                                          key={`${item.media_asset_id}-${
                                            item.motion_evidence_id ?? item.skip_reason ?? "batch"
                                          }`}
                                        >
                                          <div className="item-title-row">
                                            <strong>{item.media_asset_id}</strong>
                                            <StatusPill
                                              label={
                                                item.created
                                                  ? "Created"
                                                  : formatLabel(item.skip_reason ?? "Skipped")
                                              }
                                              tone={item.created ? "good" : "quiet"}
                                            />
                                          </div>
                                          <div className="source-connection-meta">
                                            {item.motion_evidence_id ? (
                                              <span>
                                                MotionEvidence: {item.motion_evidence_id}
                                              </span>
                                            ) : null}
                                            {item.stream_id ? (
                                              <span>Stream: {item.stream_id}</span>
                                            ) : null}
                                            {item.zone_id ? (
                                              <span>Zone: {item.zone_id}</span>
                                            ) : null}
                                            {item.existing_motion_evidence_id ? (
                                              <span>
                                                Existing MotionEvidence:{" "}
                                                {item.existing_motion_evidence_id}
                                              </span>
                                            ) : null}
                                          </div>
                                          {item.warnings.length > 0 ? (
                                            <div className="source-warning-list">
                                              {item.warnings.map((warning) => (
                                                <span key={warning}>{warning}</span>
                                              ))}
                                            </div>
                                          ) : null}
                                        </article>
                                      ))}
                                    </div>
                                    <span className="meta-text">
                                      Open Motion Evidence to review, ignore, or promote pending
                                      evidence. Use the Motion Evidence navigation item for the
                                      review step.
                                    </span>
                                  </div>
                                ) : null}
                              </div>
                            </>
                          ) : null}
                        </div>
                      ) : null}
                      <div className="folder-import-list-grid">
                        <div className="folder-import-list">
                          <div className="item-title-row">
                            <strong>Created MediaAssets</strong>
                            <StatusPill
                              label={`${folderImportResult.imported.length} created`}
                              tone="good"
                            />
                          </div>
                          {folderImportResult.imported.length > 0 ? (
                            folderImportResult.imported.map((item) => (
                              <article
                                className="folder-import-file-card"
                                key={item.media_asset_id}
                              >
                                <strong>{item.media_asset_id}</strong>
                                <span>{item.relative_source_path}</span>
                                <div className="source-connection-meta">
                                  <span>{item.file_name}</span>
                                  {item.content_type ? <span>{item.content_type}</span> : null}
                                  <span>{formatBytes(item.size_bytes)}</span>
                                  {item.stream_id ? <span>Stream: {item.stream_id}</span> : null}
                                  {item.zone_id ? <span>Zone: {item.zone_id}</span> : null}
                                </div>
                                {item.warnings.length > 0 ? (
                                  <div className="source-warning-list">
                                    {item.warnings.map((warning) => (
                                      <span key={warning}>{warning}</span>
                                    ))}
                                  </div>
                                ) : null}
                                <div className="folder-evidence-action">
                                  <button
                                    className="secondary-action"
                                    disabled={folderEvidenceLoadingId === item.media_asset_id}
                                    onClick={() =>
                                      void handleCreateMotionEvidenceFromFolderImport(item)
                                    }
                                    type="button"
                                  >
                                    {folderEvidenceLoadingId === item.media_asset_id
                                      ? "Creating pending evidence..."
                                      : "Create pending evidence"}
                                  </button>
                                  <span className="meta-text">
                                    Pending evidence only. No Events, Visits, labels, or truth were
                                    created.
                                  </span>
                                </div>
                                {folderEvidenceErrors[item.media_asset_id] ? (
                                  <div className="zone-error">
                                    {folderEvidenceErrors[item.media_asset_id]}
                                  </div>
                                ) : null}
                                {folderEvidenceResults[item.media_asset_id] ? (
                                  <div className="folder-evidence-result">
                                    <strong>
                                      MotionEvidence:{" "}
                                      {
                                        folderEvidenceResults[item.media_asset_id]
                                          .motion_evidence_id
                                      }
                                    </strong>
                                    <span>
                                      {folderEvidenceResults[item.media_asset_id]
                                        .duplicate_skipped
                                        ? "Existing evidence reused. Open Motion Evidence to review, ignore, or promote pending evidence."
                                        : "Open Motion Evidence to review, ignore, or promote pending evidence."}
                                    </span>
                                    {folderEvidenceResults[item.media_asset_id].warnings.length >
                                    0 ? (
                                      <div className="source-warning-list">
                                        {folderEvidenceResults[item.media_asset_id].warnings.map(
                                          (warning) => (
                                            <span key={warning}>{warning}</span>
                                          ),
                                        )}
                                      </div>
                                    ) : null}
                                  </div>
                                ) : null}
                              </article>
                            ))
                          ) : (
                            <span className="meta-text">No MediaAssets created.</span>
                          )}
                        </div>
                        <div className="folder-import-list">
                          <div className="item-title-row">
                            <strong>Skipped during import</strong>
                            <StatusPill
                              label={`${folderImportResult.skipped.length} skipped`}
                              tone="quiet"
                            />
                          </div>
                          {folderImportResult.skipped.length > 0 ? (
                            folderImportResult.skipped.map((skipped) => (
                              <article
                                className="folder-import-file-card"
                                key={`${skipped.relative_path ?? skipped.file_name ?? "file"}-${
                                  skipped.reason
                                }-${skipped.message}`}
                              >
                                <strong>
                                  {skipped.file_name ?? skipped.relative_path ?? "Skipped file"}
                                </strong>
                                {skipped.relative_path ? <span>{skipped.relative_path}</span> : null}
                                <div className="source-connection-meta">
                                  <span>{formatLabel(skipped.reason)}</span>
                                  <span>{skipped.message}</span>
                                </div>
                              </article>
                            ))
                          ) : (
                            <span className="meta-text">No files skipped during import.</span>
                          )}
                        </div>
                      </div>
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
                  const streamMediaAssets =
                    mediaAssetsByStream.get(stream.id)?.slice(0, MEDIA_TIMELINE_LIMIT) ?? [];
                  const streamTimelineZones = timelineZonesByStream[stream.id] ?? [];
                  const reviewableTimelineZones = streamTimelineZones.filter(isReviewableZone);
                  const selectedTimelineZoneId = timelineSelectedZoneByStream[stream.id] ?? "";
                  const blockedTimelineZoneCount = streamTimelineZones.filter(
                    (zone) => zone.is_active && !isReviewableZone(zone),
                  ).length;
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
                      <div className="stream-media-timeline">
                        <div className="item-title-row">
                          <div>
                            <strong>Saved media for this stream</strong>
                            <p className="meta-text">
                              Saved media is local evidence context. Actions below are explicit
                              and create no ReviewLabel truth.
                            </p>
                          </div>
                          <StatusPill
                            label={
                              isLoadingMediaAssets
                                ? "Loading"
                                : `${streamMediaAssets.length} recent`
                            }
                            tone="quiet"
                          />
                        </div>
                        {mediaAssetsError ? (
                          <div className="zone-error">{mediaAssetsError}</div>
                        ) : null}
                        {timelineZoneErrors[stream.id] ? (
                          <div className="zone-error">{timelineZoneErrors[stream.id]}</div>
                        ) : null}
                        {streamMediaAssets.length > 0 ? (
                          <>
                            <label className="timeline-zone-select">
                              Review zone for evidence actions
                              <select
                                disabled={reviewableTimelineZones.length === 0}
                                onChange={(event) =>
                                  setTimelineSelectedZoneByStream((current) => ({
                                    ...current,
                                    [stream.id]: event.target.value,
                                  }))
                                }
                                value={selectedTimelineZoneId}
                              >
                                {reviewableTimelineZones.length > 0 ? (
                                  reviewableTimelineZones.map((zone) => (
                                    <option key={zone.id} value={zone.id}>
                                      {zone.name} ({formatLabel(zone.zone_type)})
                                    </option>
                                  ))
                                ) : (
                                  <option value="">No reviewable Zones</option>
                                )}
                              </select>
                            </label>
                            {reviewableTimelineZones.length === 0 ? (
                              <div className="zone-error">
                                Add an active non-privacy/non-ignore Zone before creating
                                MotionEvidence.
                              </div>
                            ) : null}
                            {blockedTimelineZoneCount > 0 ? (
                              <span className="meta-text">
                                Privacy and ignore Zones are omitted from timeline evidence
                                actions.
                              </span>
                            ) : null}
                            <div className="timeline-media-list">
                              {streamMediaAssets.map((asset) => {
                                const actionState = timelineActionState[asset.id] ?? {};
                                const eligibleImage = isImageMedia(asset);
                                const proposal = actionState.proposalResult?.proposals[0] ?? null;
                                const canConvertProposal =
                                  Boolean(proposal) && !actionState.proposalDecisionResult;
                                const canPromoteEvidence =
                                  actionState.evidenceResult?.status === "pending";
                                return (
                                  <section className="timeline-media-item" key={asset.id}>
                                    <div className="item-title-row">
                                      <div>
                                        <strong>
                                          {asset.original_filename || asset.filename}
                                        </strong>
                                        <span className="meta-text">{asset.id}</span>
                                      </div>
                                      <StatusPill
                                        label={eligibleImage ? "Image actions" : "Context only"}
                                        tone={eligibleImage ? "good" : "quiet"}
                                      />
                                    </div>
                                    <div className="source-connection-meta">
                                      <span>Content: {asset.content_type}</span>
                                      <span>Type: {asset.media_type}</span>
                                      <span>Size: {formatBytes(asset.file_size_bytes)}</span>
                                      <span>Created: {formatDateTime(asset.created_at)}</span>
                                      <span>Source: {asset.source_id ?? "none"}</span>
                                      <span>Stream: {asset.stream_id}</span>
                                      <span>Provenance: {mediaProvenanceHint(asset)}</span>
                                    </div>
                                    {asset.notes ? (
                                      <p className="meta-text">{asset.notes}</p>
                                    ) : null}
                                    <div className="detail-actions">
                                      <a
                                        className="inline-link"
                                        href={apiClient.mediaFileUrl(asset.id)}
                                        rel="noreferrer"
                                        target="_blank"
                                      >
                                        Open media
                                      </a>
                                      <button
                                        className="secondary-action"
                                        disabled={
                                          !eligibleImage ||
                                          actionState.isCreatingProposal ||
                                          actionState.isConvertingProposal
                                        }
                                        onClick={() => void handleCreateTimelineProposal(asset)}
                                        type="button"
                                      >
                                        {actionState.isCreatingProposal
                                          ? "Creating..."
                                          : "Create demo proposal"}
                                      </button>
                                      {canConvertProposal ? (
                                        <button
                                          className="secondary-action"
                                          disabled={actionState.isConvertingProposal}
                                          onClick={() => void handleConvertTimelineProposal(asset)}
                                          type="button"
                                        >
                                          {actionState.isConvertingProposal
                                            ? "Converting..."
                                            : "Convert first proposal"}
                                        </button>
                                      ) : null}
                                      <button
                                        className="secondary-action"
                                        disabled={
                                          !eligibleImage ||
                                          !selectedTimelineZoneId ||
                                          actionState.isCreatingEvidence
                                        }
                                        onClick={() => void handleCreateTimelineEvidence(asset)}
                                        type="button"
                                      >
                                        {actionState.isCreatingEvidence
                                          ? "Creating..."
                                          : "Create MotionEvidence"}
                                      </button>
                                      <button
                                        className="secondary-action"
                                        onClick={onOpenDetectionProposals}
                                        type="button"
                                      >
                                        Detection Proposals
                                      </button>
                                      <button
                                        className="secondary-action"
                                        onClick={onOpenReview}
                                        type="button"
                                      >
                                        Review Queue
                                      </button>
                                      <button
                                        className="secondary-action"
                                        onClick={onOpenExports}
                                        type="button"
                                      >
                                        Dataset Exports
                                      </button>
                                    </div>
                                    {actionState.proposalMessage ? (
                                      <div className="notice-panel compact-notice">
                                        {actionState.proposalMessage}
                                      </div>
                                    ) : null}
                                    {actionState.proposalError ? (
                                      <div className="zone-error">
                                        {actionState.proposalError}
                                      </div>
                                    ) : null}
                                    {actionState.proposalResult ? (
                                      <div className="timeline-result-grid">
                                        <div className="data-row">
                                          <span>DetectionRun</span>
                                          <strong>
                                            {actionState.proposalResult.detection_run.id}
                                          </strong>
                                        </div>
                                        <div className="data-row">
                                          <span>Proposals</span>
                                          <strong>
                                            {actionState.proposalResult.proposals.length > 0
                                              ? actionState.proposalResult.proposals
                                                  .map((item) => item.id)
                                                  .join(", ")
                                              : "none"}
                                          </strong>
                                        </div>
                                        <div className="data-row">
                                          <span>Review Queue</span>
                                          <strong>
                                            {actionState.proposalResult.review_queue_count} needs
                                            review
                                          </strong>
                                        </div>
                                        {actionState.proposalResult.proposals.map((item) => (
                                          <div className="data-row" key={item.id}>
                                            <span>{item.id}</span>
                                            <strong>
                                              {item.label} /{" "}
                                              {Math.round(item.confidence * 100)}% /{" "}
                                              {formatLabel(item.status)}
                                            </strong>
                                          </div>
                                        ))}
                                      </div>
                                    ) : null}
                                    {actionState.proposalDecisionResult ? (
                                      <div className="timeline-result-grid">
                                        <div className="data-row">
                                          <span>Converted proposal</span>
                                          <strong>
                                            {actionState.proposalDecisionResult.proposal.id}
                                          </strong>
                                        </div>
                                        <div className="data-row">
                                          <span>Event</span>
                                          {actionState.proposalDecisionResult.event ? (
                                            <button
                                              className="inline-link-button"
                                              onClick={() =>
                                                onOpenEvent(
                                                  actionState.proposalDecisionResult!.event!.id,
                                                )
                                              }
                                              type="button"
                                            >
                                              {actionState.proposalDecisionResult.event.id}
                                            </button>
                                          ) : (
                                            <strong>not created</strong>
                                          )}
                                        </div>
                                        <div className="data-row">
                                          <span>Visit</span>
                                          {actionState.proposalDecisionResult.visit ? (
                                            <button
                                              className="inline-link-button"
                                              onClick={() =>
                                                onOpenVisit(
                                                  actionState.proposalDecisionResult!.visit!.id,
                                                )
                                              }
                                              type="button"
                                            >
                                              {actionState.proposalDecisionResult.visit.id}
                                            </button>
                                          ) : (
                                            <strong>not created</strong>
                                          )}
                                        </div>
                                      </div>
                                    ) : null}
                                    {actionState.evidenceError ? (
                                      <div className="zone-error">{actionState.evidenceError}</div>
                                    ) : null}
                                    {actionState.evidenceResult ? (
                                      <div className="timeline-result-grid">
                                        <div className="data-row">
                                          <span>MotionEvidence</span>
                                          <button
                                            className="inline-link-button"
                                            onClick={() =>
                                              onOpenMotionEvidence(
                                                actionState.evidenceResult!.motion_evidence_id,
                                              )
                                            }
                                            type="button"
                                          >
                                            {actionState.evidenceResult.motion_evidence_id}
                                          </button>
                                        </div>
                                        <div className="data-row">
                                          <span>Status</span>
                                          <strong>
                                            {formatLabel(actionState.evidenceResult.status)}
                                          </strong>
                                        </div>
                                        <div className="data-row">
                                          <span>Zone</span>
                                          <strong>
                                            {actionState.evidenceResult.zone_id ?? "none"}
                                          </strong>
                                        </div>
                                      </div>
                                    ) : null}
                                    {canPromoteEvidence ? (
                                      <div className="detail-actions">
                                        <button
                                          className="primary-action"
                                          disabled={actionState.isPromotingEvidence}
                                          onClick={() => void handlePromoteTimelineEvidence(asset)}
                                          type="button"
                                        >
                                          {actionState.isPromotingEvidence
                                            ? "Promoting..."
                                            : "Promote MotionEvidence"}
                                        </button>
                                      </div>
                                    ) : null}
                                    {actionState.promotionError ? (
                                      <div className="zone-error">
                                        {actionState.promotionError}
                                      </div>
                                    ) : null}
                                    {actionState.promotionResult ? (
                                      <div className="timeline-result-grid">
                                        <div className="data-row">
                                          <span>Event</span>
                                          {actionState.promotionResult.event_id ? (
                                            <button
                                              className="inline-link-button"
                                              onClick={() =>
                                                onOpenEvent(actionState.promotionResult!.event_id!)
                                              }
                                              type="button"
                                            >
                                              {actionState.promotionResult.event_id}
                                            </button>
                                          ) : (
                                            <strong>not created</strong>
                                          )}
                                        </div>
                                        <div className="data-row">
                                          <span>Visit</span>
                                          {actionState.promotionResult.visit_id ? (
                                            <button
                                              className="inline-link-button"
                                              onClick={() =>
                                                onOpenVisit(actionState.promotionResult!.visit_id!)
                                              }
                                              type="button"
                                            >
                                              {actionState.promotionResult.visit_id}
                                            </button>
                                          ) : (
                                            <strong>not created</strong>
                                          )}
                                        </div>
                                      </div>
                                    ) : null}
                                    <div className="notice-panel compact-notice import-smoke-boundary">
                                      <strong>Truth boundary</strong>
                                      <ul>
                                        <li>Saved media is local evidence context.</li>
                                        <li>Demo proposal evidence is synthetic.</li>
                                        <li>No model inspected this media.</li>
                                        <li>
                                          ReviewLabel truth only happens through Review Queue
                                          correction.
                                        </li>
                                      </ul>
                                    </div>
                                  </section>
                                );
                              })}
                            </div>
                          </>
                        ) : (
                          <div className="timeline-empty-state">
                            No saved media for this stream yet. Fetch/save an external URL
                            snapshot or import media.
                          </div>
                        )}
                      </div>
                    </section>
                  );
                })
              ) : (
                <EmptyState
                  title="No Streams for this Source"
                  description="Add Stream metadata before drawing Zones or reviewing activity."
                />
              )}
            </div>
          </section>
        </section>
      ) : (
        <EmptyState
          title="No Sources available"
          description="Create a Source before configuring provider actions."
        />
      )}
    </div>
  );
}
